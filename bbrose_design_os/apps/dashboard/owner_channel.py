"""§BH54(b) (k) 3 — THE ONE DOOR an acceptance is written through.

Every refusal has a name and comes BEFORE anything is written, in this order: identity, the time, the sha256, the
picture, the task's spec. "An acceptance that lacks any of the three fields is refused by name." The machine has no other
path: nothing in the pipeline, the gates or the reconstruction calls this module, and a test proves they write no row.
"""
from __future__ import annotations

import datetime
import hashlib
import re

from . import explorations
from .models import DesignAcceptance, OwnerAcceptance, OwnerCopy

ACCEPTANCE_REFUSED_NO_IDENTITY = "ACCEPTANCE_REFUSED_NO_IDENTITY"
ACCEPTANCE_REFUSED_NOT_THE_OWNER = "ACCEPTANCE_REFUSED_NOT_THE_OWNER"
ACCEPTANCE_REFUSED_NO_TIME = "ACCEPTANCE_REFUSED_NO_TIME"
ACCEPTANCE_REFUSED_NO_SHA256 = "ACCEPTANCE_REFUSED_NO_SHA256"
ACCEPTANCE_REFUSED_DECISION = "ACCEPTANCE_REFUSED_DECISION"
ACCEPTANCE_REFUSED_PICTURE = "ACCEPTANCE_REFUSED_PICTURE"
ACCEPTANCE_REFUSED_NOT_THESE_BYTES = "ACCEPTANCE_REFUSED_NOT_THESE_BYTES"
ACCEPTANCE_REFUSED_SPEC_STALE = "ACCEPTANCE_REFUSED_SPEC_STALE"

VERIFIED = "VERIFIED — the picture's bytes are the accepted bytes"
VOID_DRIFT = "VOID — the picture's bytes are not the bytes this act names"
VOID_GONE = "VOID — the picture is no longer in the store"

_SHA = re.compile(r"^[0-9a-f]{64}$")


class ChannelRefused(Exception):
    def __init__(self, code: str, detail: str, cite: str = "§BH54(b) (k) 3"):
        self.code = code
        super().__init__(f"{code}: REFUSED — {detail} ({cite})")


def _picture_bytes(study: str, picture: str):
    path = explorations.picture_file(study, picture)
    return path.read_bytes() if path is not None else None


def record_acceptance(*, user, decided_at, task, study: str, picture: str, picture_sha256: str, decision: str,
                      note: str = "") -> OwnerAcceptance:
    """Write ONE act, or refuse it by name. `user` is his identity, `decided_at` the time, `picture_sha256` the sha256
    of exactly what he accepted — the three fields; each is checked before anything is read or written."""
    if user is None or not getattr(user, "is_authenticated", False):
        raise ChannelRefused(ACCEPTANCE_REFUSED_NO_IDENTITY, "an acceptance carries the identity of who accepted; none was given")
    refusal = explorations.owner_refusal(user)
    if refusal:
        raise ChannelRefused(ACCEPTANCE_REFUSED_NOT_THE_OWNER,
                             f"acceptance is the owner's act alone; {user.get_username()} is not the owner account")
    if not isinstance(decided_at, datetime.datetime) or decided_at.tzinfo is None:
        raise ChannelRefused(ACCEPTANCE_REFUSED_NO_TIME, "an acceptance carries the time it was made; none was given")
    if not isinstance(picture_sha256, str) or not _SHA.match(picture_sha256):
        raise ChannelRefused(ACCEPTANCE_REFUSED_NO_SHA256,
                             "an acceptance carries the sha256 of exactly what was accepted; none was given")
    if decision not in (OwnerAcceptance.ACCEPTED, OwnerAcceptance.REJECTED):
        raise ChannelRefused(ACCEPTANCE_REFUSED_DECISION, f"{decision!r} is neither ACCEPTED nor REJECTED")
    found = explorations.study(study) if explorations.store_is_outside_governed_roots() else None
    shown = next((p for p in (found or {}).get("pictures", []) if p["picture"] == picture and not p["refused"]), None)
    data = _picture_bytes(study, picture) if shown else None
    if shown is None or data is None or shown["record"].get("task") != task.pk:
        raise ChannelRefused(ACCEPTANCE_REFUSED_PICTURE, f"{study}/{picture} is not a picture of task {task.pk} in the store")
    if hashlib.sha256(data).hexdigest() != picture_sha256:
        raise ChannelRefused(ACCEPTANCE_REFUSED_NOT_THESE_BYTES,
                             f"{study}/{picture} is not the bytes named {picture_sha256[:16]}…; nothing is accepted by a name alone")
    from apps.ire.container_production_readiness import spec_staleness
    output = task.packaging_outputs.exclude(spec_sheet=None).order_by("-pk").first()
    stale = spec_staleness((output.spec_sheet or {}) if output is not None else {})
    if stale["stale"]:
        raise ChannelRefused(ACCEPTANCE_REFUSED_SPEC_STALE,
                             "SPEC_STALE_REDERIVE_REQUIRED — the task's saved verdict predates "
                             f"{len(stale['checks_predate'])} of today's checks (latest {stale['latest_since']}); a stale spec "
                             "is re-derived before anything of it is accepted (§BH54(d))")
    return OwnerAcceptance.objects.create(
        task=task, study=study, picture=picture, decision=decision, decided_by=user, decided_at=decided_at,
        picture_sha256=picture_sha256, inputs_sha256=str(shown["record"].get("inputs_sha256") or ""),
        knobs=shown["record"].get("knobs") or {}, note=note[:2000])


def acts_for(task) -> list[dict]:
    """His acts on this task, newest first, each RE-VERIFIED against the picture's bytes as they are now: an act whose
    picture has drifted or gone reads VOID — shown, and never a pass."""
    acts = []
    for row in OwnerAcceptance.objects.filter(task=task).select_related("decided_by"):
        data = _picture_bytes(row.study, row.picture)
        if data is None:
            state = VOID_GONE
        else:
            state = VERIFIED if hashlib.sha256(data).hexdigest() == row.picture_sha256 else VOID_DRIFT
        acts.append({"row": row, "who": row.decided_by.get_username(), "verification": state,
                     "void": state != VERIFIED})
    return acts


# ---------------------------------------------------------------------------------------------------------------------
# §BH54(b) (k) 4 — THE COPY CHANNEL. "I type the six pieces into the product from the loop page, each piece's room shown
# as I type, an over-room warning that informs rather than refuses, and the words landing as my act with the same three
# fields." The same door, the same order of refusals, the same re-verification on every read. There is no character
# limit here and nothing is cut (§W1(d)): what the panel cannot hold is the back panel's finding, never this door's.
COPY_CITE = "§BH54(b) (k) 4"
COPY_REFUSED_NO_IDENTITY = "COPY_REFUSED_NO_IDENTITY"
COPY_REFUSED_NOT_THE_OWNER = "COPY_REFUSED_NOT_THE_OWNER"
COPY_REFUSED_NO_TIME = "COPY_REFUSED_NO_TIME"
COPY_REFUSED_NO_SHA256 = "COPY_REFUSED_NO_SHA256"
COPY_REFUSED_NO_PRODUCT = "COPY_REFUSED_NO_PRODUCT"
COPY_REFUSED_NOT_A_PIECE = "COPY_REFUSED_NOT_A_PIECE"
COPY_REFUSED_NO_WORDS = "COPY_REFUSED_NO_WORDS"
COPY_REFUSED_NOT_THESE_WORDS = "COPY_REFUSED_NOT_THESE_WORDS"
COPY_VERIFIED = "VERIFIED — the words are the words this act names"
COPY_VOID = "VOID — the stored words are not the words this act names"


def words_sha256(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def record_copy(*, user, typed_at, product, piece: str, text: str, text_sha256: str) -> OwnerCopy:
    """Write ONE piece of copy as the owner's act, or refuse it by name — identity, the time, the sha256, in that order,
    each before anything is written. Over its room a piece is still written: the page informs, it never refuses."""
    if user is None or not getattr(user, "is_authenticated", False):
        raise ChannelRefused(COPY_REFUSED_NO_IDENTITY, "copy lands as the act of whoever typed it; no identity was given",
                             COPY_CITE)
    if explorations.owner_refusal(user):
        raise ChannelRefused(COPY_REFUSED_NOT_THE_OWNER,
                             f"the product's copy is the owner's to type; {user.get_username()} is not the owner account",
                             COPY_CITE)
    if not isinstance(typed_at, datetime.datetime) or typed_at.tzinfo is None:
        raise ChannelRefused(COPY_REFUSED_NO_TIME, "copy carries the time it was typed; none was given", COPY_CITE)
    if not isinstance(text_sha256, str) or not _SHA.match(text_sha256):
        raise ChannelRefused(COPY_REFUSED_NO_SHA256, "copy carries the sha256 of exactly the words typed; none was given",
                             COPY_CITE)
    if getattr(product, "pk", None) is None:
        raise ChannelRefused(COPY_REFUSED_NO_PRODUCT, "copy is typed INTO a product; this task has none", COPY_CITE)
    if piece not in OwnerCopy.PIECES:
        raise ChannelRefused(COPY_REFUSED_NOT_A_PIECE, f"{piece!r} is not one of the six pieces", COPY_CITE)
    if not str(text or "").strip():
        raise ChannelRefused(COPY_REFUSED_NO_WORDS, f"{piece} was given no words", COPY_CITE)
    if words_sha256(text) != text_sha256:
        raise ChannelRefused(COPY_REFUSED_NOT_THESE_WORDS,
                             f"the words given for {piece} are not the words named {text_sha256[:16]}…", COPY_CITE)
    return OwnerCopy.objects.create(product=product, piece=piece, text=text, typed_by=user, typed_at=typed_at,
                                    text_sha256=text_sha256)


def copy_for(product) -> dict:
    """The product's copy as typed — per piece its NEWEST row, re-verified on this read: words that no longer hash to
    the act's sha256 read VOID and are not copy (never an older row in their place: the newest act is his last word)."""
    found: dict = {}
    if getattr(product, "pk", None) is None:
        return found
    for row in OwnerCopy.objects.filter(product=product).select_related("typed_by").order_by("typed_at", "pk"):
        ok = words_sha256(row.text) == row.text_sha256
        found[row.piece] = {"row": row, "text": row.text, "sha256": row.text_sha256, "who": row.typed_by.get_username(),
                            "when": row.typed_at, "verification": COPY_VERIFIED if ok else COPY_VOID, "void": not ok}
    return {piece: found[piece] for piece in OwnerCopy.PIECES if piece in found}


def written_copy(product) -> dict:
    """{piece: words} for the pieces the governed path may print: the newest row of each, and only while VERIFIED."""
    return {piece: entry["text"] for piece, entry in copy_for(product).items() if not entry["void"]}


# ---------------------------------------------------------------------------------------------------------------------
# §BH55 PHASE 1 — HIS ACCEPTANCE OF A GOVERNED DESIGN. The design a pipeline stage produced (a container's reconstruction,
# a carton's artwork) waits at its gate for his eye. Nothing in the product wrote the container acceptance a Complete
# Product project waits for, so no project could ever reach its packaging stage. This is that door: his act alone, the
# three fields, the sha256 of the exact preview he looked at — re-hashed from its bytes before anything is written, and
# re-verified on every read. The executor never calls it.
DESIGN_CITE = "§BH55 Phase 1"
DESIGN_REFUSED_NO_IDENTITY = "DESIGN_ACCEPTANCE_REFUSED_NO_IDENTITY"
DESIGN_REFUSED_NOT_THE_OWNER = "DESIGN_ACCEPTANCE_REFUSED_NOT_THE_OWNER"
DESIGN_REFUSED_NO_TIME = "DESIGN_ACCEPTANCE_REFUSED_NO_TIME"
DESIGN_REFUSED_NO_SHA256 = "DESIGN_ACCEPTANCE_REFUSED_NO_SHA256"
DESIGN_REFUSED_DECISION = "DESIGN_ACCEPTANCE_REFUSED_DECISION"
DESIGN_REFUSED_NO_DESIGN = "DESIGN_ACCEPTANCE_REFUSED_NO_DESIGN"
DESIGN_REFUSED_NOT_AT_ITS_GATE = "DESIGN_ACCEPTANCE_REFUSED_NOT_AT_ITS_GATE"
DESIGN_REFUSED_NOT_THESE_BYTES = "DESIGN_ACCEPTANCE_REFUSED_NOT_THESE_BYTES"
DESIGN_REFUSED_SPEC_STALE = "DESIGN_ACCEPTANCE_REFUSED_SPEC_STALE"
DESIGN_VERIFIED = "VERIFIED — the preview's bytes are the bytes this act names"
DESIGN_VOID_DRIFT = "VOID — the preview is no longer the bytes this act names"
#: the one state a design waits for his eye in
DESIGN_GATE_STATUS = "awaiting_gate_2"


def preview_sha256(output):
    """(sha256, name) of the output's preview PNG as it is NOW, or (None, "") when it has none."""
    f = getattr(output, "design_preview", None)
    if not f or not getattr(f, "name", ""):
        return None, ""
    try:
        with f.open("rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest(), f.name
    except (OSError, ValueError):
        return None, f.name


def record_design_acceptance(*, user, decided_at, task, output, preview_sha256_given: str, decision: str,
                             note: str = "") -> DesignAcceptance:
    """Write ONE act on a governed design, or refuse it by name — each refusal before anything is written: identity,
    the owner account, the time, the sha256, the decision, a design with a preview, the design at its gate, these bytes,
    and a spec that is not stale. For a CONTAINER the act is also written where the governed readers read it
    (`container_human_visual_acceptance` on the output's record), with the sha256, in the same transaction."""
    from django.db import transaction

    from apps.ire.container_production_readiness import ACCEPTANCE_KEY, spec_staleness
    if user is None or not getattr(user, "is_authenticated", False):
        raise ChannelRefused(DESIGN_REFUSED_NO_IDENTITY, "an acceptance carries the identity of who accepted; none was given",
                             DESIGN_CITE)
    if explorations.owner_refusal(user):
        raise ChannelRefused(DESIGN_REFUSED_NOT_THE_OWNER,
                             f"accepting a design is the owner's act alone; {user.get_username()} is not the owner account",
                             DESIGN_CITE)
    if not isinstance(decided_at, datetime.datetime) or decided_at.tzinfo is None:
        raise ChannelRefused(DESIGN_REFUSED_NO_TIME, "an acceptance carries the time it was made; none was given", DESIGN_CITE)
    if not isinstance(preview_sha256_given, str) or not _SHA.match(preview_sha256_given):
        raise ChannelRefused(DESIGN_REFUSED_NO_SHA256,
                             "an acceptance carries the sha256 of exactly the design accepted; none was given", DESIGN_CITE)
    if decision not in (DesignAcceptance.ACCEPTED, DesignAcceptance.REJECTED):
        raise ChannelRefused(DESIGN_REFUSED_DECISION, f"{decision!r} is neither ACCEPTED nor REJECTED", DESIGN_CITE)
    now_sha, name = preview_sha256(output) if output is not None else (None, "")
    if output is None or output.task_id != task.pk or now_sha is None:
        raise ChannelRefused(DESIGN_REFUSED_NO_DESIGN, f"task {task.pk} has no design with a preview to look at", DESIGN_CITE)
    if task.status != DESIGN_GATE_STATUS:
        raise ChannelRefused(DESIGN_REFUSED_NOT_AT_ITS_GATE,
                             f"task {task.pk} is {task.status}; a design is accepted at its gate ({DESIGN_GATE_STATUS})",
                             DESIGN_CITE)
    if now_sha != preview_sha256_given:
        raise ChannelRefused(DESIGN_REFUSED_NOT_THESE_BYTES,
                             f"the preview is not the bytes named {preview_sha256_given[:16]}…; nothing is accepted by a "
                             "name alone", DESIGN_CITE)
    spec = dict(output.spec_sheet or {})
    stale = spec_staleness(spec)
    if stale["stale"]:
        raise ChannelRefused(DESIGN_REFUSED_SPEC_STALE,
                             "SPEC_STALE_REDERIVE_REQUIRED — the design's saved verdict predates "
                             f"{len(stale['checks_predate'])} of today's checks; it is re-derived before it is accepted",
                             DESIGN_CITE)
    with transaction.atomic():
        act = DesignAcceptance.objects.create(
            task=task, output=output, decision=decision, decided_by=user, decided_at=decided_at,
            preview_sha256=now_sha, preview_name=name, note=note[:2000])
        if task.design_target == "product_container" or spec.get("backend") == "container":
            spec[ACCEPTANCE_KEY] = {
                "state": decision, "decided_by": user.get_username(), "decided_at": decided_at.isoformat(),
                "preview_sha256": now_sha, "preview_name": name, "output_id": output.pk, "act_id": act.pk,
                "channel": "apps/dashboard/owner_channel.record_design_acceptance (%s)" % DESIGN_CITE}
            output.spec_sheet = spec
            output.save(update_fields=["spec_sheet"])
    return act


def design_acts_for(task) -> list[dict]:
    """His acts on this task's designs, newest first, each RE-VERIFIED against its preview's bytes as they are now."""
    acts = []
    for row in DesignAcceptance.objects.filter(task=task).select_related("decided_by", "output"):
        now_sha, _name = preview_sha256(row.output)
        ok = now_sha == row.preview_sha256
        acts.append({"row": row, "who": row.decided_by.get_username(),
                     "verification": DESIGN_VERIFIED if ok else DESIGN_VOID_DRIFT, "void": not ok})
    return acts


def design_acceptance_payload(task, user) -> dict | None:
    """What the task's status payload carries for the acceptance control: the newest output's preview sha256 (computed
    here, from the bytes), whether the viewer is the owner, the design's state, and his acts, each re-verified."""
    output = task.packaging_outputs.exclude(design_preview="").order_by("-pk").first()
    if output is None:
        return None
    sha, name = preview_sha256(output)
    return {"output_id": output.pk, "preview_sha256": sha, "preview_name": name,
            "at_its_gate": task.status == DESIGN_GATE_STATUS,
            "viewer_is_owner": bool(user is not None and getattr(user, "is_authenticated", False)
                                    and not explorations.owner_refusal(user)),
            "url": "/dashboard/history/tasks/%d/accept-design/" % task.pk,
            "acts": [{"decision": a["row"].decision, "who": a["who"], "when": a["row"].decided_at.isoformat(),
                      "preview_sha256": a["row"].preview_sha256, "verification": a["verification"], "void": a["void"],
                      "note": a["row"].note}
                     for a in design_acts_for(task)]}
