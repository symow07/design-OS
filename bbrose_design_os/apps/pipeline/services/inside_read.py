"""[His final goal, 2026-10-05 (transcribed at 32e9aaf), B1: "An "Inside reference" picture slot beside the inspiration
box (one or more pictures) ... followed in pattern and style, never pasted or copied 1:1."] An inside reference read ONCE
into its pattern and its style (``apps.ire.inside_print.SYSTEM``) — [B3: "Custom sticker: follows a sticker reference
picture"] and a sticker reference into its shape, fill and border (``apps.ire.back_info.SYSTEM``) — the picture goes to
this read and nowhere else:
never to the direction planner, never to the image service, never placed. A picture read before is answered from its
stored reading (its own digest, apart from the same picture read as inspiration) and costs nothing; each read is on the
spend ledger against its design, or unbound until the design it was made for is started."""
from __future__ import annotations
from apps.pipeline.services.spend_reservation import paid_operation

import hashlib
import json

from apps.ire import back_info
from apps.ire.inside_print import FIELDS, KIND, OPERATION, PATTERNS, READ_MAX_TOKENS, SYSTEM, spec_from_words

__all__ = ["KIND", "STICKER_KIND", "KINDS", "known_reading", "read_picture", "words_of", "payload", "task_readings"]

STICKER_KIND = back_info.KIND
#: each kind of picture read here: its reader's words, its fields, its ledger row's name
READERS = {KIND: (SYSTEM, FIELDS, OPERATION), STICKER_KIND: (back_info.SYSTEM, back_info.FIELDS, "sticker_read")}
KINDS = tuple(READERS)


def _text(value) -> str:
    """A reading's field as text — an absent field is empty, never a guess."""
    return "" if value is None else str(value).strip()


def digest(data: bytes, kind: str = KIND) -> str:
    """The key a reference's reading is kept under — its own for its kind, apart from the picture read as inspiration."""
    return hashlib.sha256(kind.encode("ascii") + b"\0" + data).hexdigest()


def known_reading(data: bytes, kind: str = KIND):
    """The stored reading of this picture as a reference of ``kind``, or None."""
    from apps.pipeline.models import InspirationReading
    return InspirationReading.objects.filter(sha256=digest(data, kind)).first()


def _parsed(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def read_picture(data: bytes, *, task=None, user=None, kind: str = KIND):
    """One reference of ``kind`` read — an inside reference into its pattern and style, a sticker reference into its
    shape, fill and border: the stored reading when this picture was read before (nothing spent), else ONE paid read on
    the ledger — against ``task`` when there is one. ``(row, spent)``."""
    system, fields, operation = READERS[kind]
    import base64

    from django.conf import settings

    from apps.pipeline.models import ApiCallRecord, InspirationReading
    from apps.pipeline.services import cost_ledger, inspiration
    from apps.pipeline.services.claude_service import _get_client
    known = known_reading(data, kind)
    if known is not None:
        return known, False
    if cost_ledger.daily_budget_exceeded():
        raise inspiration.InspirationReadRefused(
            "DAILY_BUDGET_EXCEEDED", "The last 24 hours have spent the daily limit, so the picture was not read.")
    if not settings.ANTHROPIC_API_KEY:
        raise inspiration.InspirationReadRefused("NO_READING_KEY",
                                                 "The reading service has no key, so the picture was not read.")
    try:
        png, width, height = inspiration.downscaled(data)
    except Exception as exc:  # noqa: BLE001 — an unreadable picture is refused by name, never sent
        raise inspiration.InspirationReadRefused("INSPIRATION_PICTURE_UNREADABLE",
                                                 "This file could not be opened as a picture.") from exc
    model = inspiration.read_model()
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                            "data": base64.standard_b64encode(png).decode("ascii")}},
               {"type": "text", "text": "Read this %s. Return the JSON object only." % kind.replace("_", " ")}]
    response = paid_operation(_get_client().messages.create, provider='anthropic', task=task, operation='inside_read', model=model, max_tokens=READ_MAX_TOKENS, system=system,
                                             messages=[{"role": "user", "content": content}])
    tin, tout = int(response.usage.input_tokens), int(response.usage.output_tokens)
    cost = cost_ledger.claude_cost_usd(model, tin, tout)
    call = ApiCallRecord.objects.create(
        task=task, provider="anthropic", model=model, operation=operation, input_tokens=tin, output_tokens=tout,
        cost_usd=cost, metadata={"sha256": digest(data, kind), "sent_px": [width, height],
                                 "provider_request_id": cost_ledger.provider_request_id(response)})
    found = _parsed("".join(b.text for b in response.content if b.type == "text"))
    reading = {k: _text(found.get(k))[:300] for k in fields}
    if kind == KIND and reading["pattern"] not in PATTERNS:
        said = spec_from_words(reading["style"])
        reading["pattern"] = said["pattern"] if said and "pattern" in said else ""
    seen = found["seen_not_taken"] if isinstance(found.get("seen_not_taken"), list) else []
    reading["seen_not_taken"] = [_text(s)[:120] for s in seen if _text(s)][:20]
    reading["kind"] = kind
    signed_in = user is not None and user.is_authenticated
    row = InspirationReading.objects.create(sha256=digest(data, kind), reading=reading, model=model, cost_usd=cost,
                                            api_call=call, created_by=user if signed_in else None)
    if task is not None:
        cost_ledger.check_task_budget(task)
    return row, True


def words_of(reading: dict) -> str:
    """A reading in his words, for the page: its pattern, direction and density (a sticker's shape, fill and border),
    and its character."""
    if reading.get("kind") == STICKER_KIND:
        head = " ".join(_text(reading.get(k)) for k in ("shape", "fill", "border") if _text(reading.get(k)))
        style = _text(reading.get("style")).rstrip(".")
        return ("%s — %s." % (head, style) if style else head + ".").strip()
    direction = _text(reading.get("direction"))
    parts = [_text(reading.get("pattern")), direction if direction not in ("", "none") else "",
             _text(reading.get("density"))]
    head = " ".join(p for p in parts if p)
    style = _text(reading.get("style")).rstrip(".")
    return ("%s — %s." % (head, style) if style else head + ".").strip()


def payload(row, *, spent: bool) -> dict:
    """What a page is told of one read inside reference: what was taken, what was seen and never taken, and what reading
    it cost — nothing when it was read before."""
    reading = row.reading if isinstance(row.reading, dict) else {}
    seen = reading["seen_not_taken"] if isinstance(reading.get("seen_not_taken"), list) else []
    fields = READERS[STICKER_KIND][1] if reading.get("kind") == STICKER_KIND else FIELDS
    return {"sha256": row.sha256, "words": words_of(reading), "taken": {k: _text(reading.get(k)) for k in fields},
            "seen_not_taken": list(seen), "cost_usd": str(row.cost_usd) if spent else "0", "read_before": not spent}


def _bytes_of(ref):
    """A reference's file, or None where it is gone."""
    try:
        with ref.image.open("rb") as fh:
            return fh.read()
    except (OSError, ValueError):
        return None


def task_readings(task, *, read_missing: bool = True, kind: str = KIND) -> list:
    """The readings of a design's references of ``kind``, in their order — each read once, on the start page or here."""
    out = []
    for ref in task.references.filter(kind=kind).order_by("ordering", "id"):
        data = _bytes_of(ref)
        if data is None:
            continue
        row = known_reading(data, kind)
        if row is None and read_missing:
            row, _spent = read_picture(data, task=task, kind=kind)
        if row is not None:
            reading = row.reading if isinstance(row.reading, dict) else {}
            # [his goal of 2026-10-10, item 10: "deep berry on a bright pink ground"] the reference's own two colours,
            # measured from its pixels at $0 — never read as codes by the reader
            from apps.ire.inside_print import reference_colours
            out.append(dict(reading, sha256=row.sha256, colours=reference_colours(data)))
    return out
