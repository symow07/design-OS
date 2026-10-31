"""[His test blocker on design 122, 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md), items 2 and 4: "Never show me a concept the
system can't draw. Check each picture's readability BEFORE showing it; if one fails, redraw it automatically (e.g. the
same design straight-on on a clearly contrasting plain background) and only show it when it passes." "If even the redraw
fails, never a dead end: offer me in words what I can do (redraw for $X, draw this concept from the template, or pick
another), each with a button."]

Each container concept, once drawn and checked, is read by its design map BEFORE it is shown — the same steps his finding
on design 119 put at approval (``targets.container.map_drawable``): the trace finds the one standing product (local,
nothing paid), its parts are named (one vision call, kept on the picture so approval pays nothing again), each part is
traced and drawn (local). A concept the trace cannot cut from its ground is redrawn once, automatically: the same design,
straight-on, on a plain backdrop that contrasts with it in lightness (``backdrop_for``) — and read again. What is shown is
said on the concept (``CHECK_KEY``): drawable; drawable after its redraw; or not drawable yet, why in words, and his three
offers, each a button. MEASURED on 122: 147 and 148, pale pink tubes on pale pink-peach grounds, the trace found no
product; 149, on white, read, and five of its parts — a framed oval window, its outline, three lines of type with no
measured ink — that no redraw of its background can make drawable.
"""
from __future__ import annotations
from apps.pipeline.services.spend_reservation import paid_operation

import hashlib

#: what the check found, kept on the concept (``reference_provenance``)
CHECK_KEY = "concept_readable/1.0"
DRAWABLE = "DRAWABLE"
NOT_DRAWABLE = "NOT_DRAWABLE"
UNCHECKED = "UNCHECKED"
#: a concept redrawn so it can be read, kept on the concept: the picture it replaced, the backdrop, what it cost
REDRAWN_KEY = "concept_redrawn/1.0"
#: the stop his finding on design 119 set at approval — one source of truth for "cannot be drawn" on the page
FROM_TEMPLATE_KEY = "draw_from_template/1.0"
#: a stop at approval the concept's own later check found drawable, kept beside (his go of 2026-10-08)
STOP_LIFTED_KEY = "design_map_stop_lifted/1.0"

#: the words a redraw is asked in — the same design, read: never a new one
REDRAW_PROMPT = ("Redraw this exact product design so it can be read: the SAME product, the same colours, the same "
                 "lettering, motifs and layout on it — nothing added, removed or restyled — standing upright, "
                 "straight-on, whole and uncropped, alone on a plain seamless {backdrop} backdrop that contrasts clearly "
                 "with the product, evenly lit, no props, no scene, no reflection on the floor.")
#: [his item 4, for a concept whose blocker is a part the drawing cannot draw yet — no backdrop removes it] the same
#: design with only those parts left out, by his button: the redraw that can make it drawable
REDRAW_WITHOUT_PROMPT = ("Redraw this exact product design so it can be read: the SAME product, the same colours, the "
                         "same lettering, motifs and layout on it, with ONLY these parts left out, their place left as "
                         "the plain surface around them: {parts}. Nothing else added, removed or restyled — standing "
                         "upright, straight-on, whole and uncropped, alone on a plain seamless {backdrop} backdrop that "
                         "contrasts clearly with the product, evenly lit, no props, no scene, no reflection on the "
                         "floor.")
#: [his item 3] the backdrop a concept is redrawn on, by the product's lightness: a light product on a deep neutral,
#: a dark one on white — never the product's own colour family
LIGHT_PRODUCT_L = 55.0
BACKDROPS = {"light": ("deep charcoal-grey", "#2F2D2C"), "dark": ("clean white", "#FFFFFF")}


def backdrop_for(pic: bytes) -> dict:
    """The backdrop a concept is redrawn on — ``{"words", "hex", "product_l"}`` — by its product's lightness, measured:
    the median lightness of the picture's middle (where the product stands), its border left out."""
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(pic, np.uint8), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    middle = img[int(h * 0.25):int(h * 0.80), int(w * 0.35):int(w * 0.65)]
    lightness = float(np.median(cv2.cvtColor(middle, cv2.COLOR_BGR2LAB)[..., 0])) * 100.0 / 255.0
    words, hex_ = BACKDROPS["light" if lightness >= LIGHT_PRODUCT_L else "dark"]
    return {"words": words, "hex": hex_, "product_l": round(lightness, 1)}


def _part_words(part: dict) -> str:
    kind, name, why = part.get("kind"), part.get("name"), part.get("why")
    return "%s (%s)" % (name, why) if kind != "window" else "%s — a framed window, which it cannot draw yet" % name


def why_in_words(found: dict) -> str:
    """Why a concept cannot be drawn, in a designer's words — never an engine code — and why its redraw did not help,
    where one could not be made."""
    if found.get("background"):
        why = "the product can't be told apart from its background, so its shape can't be cut out"
    elif found.get("parts"):
        parts = found["parts"]
        why = "%d of its parts can't be drawn yet: %s" % (len(parts), "; ".join(_part_words(p) for p in parts))
    else:
        why = found.get("why") if found.get("why") else "its picture could not be read"
    return why + ("; " + found["redraw_failed"] if found.get("redraw_failed") else "")


def check(aria, image) -> dict:
    """One concept read by its design map, as approval would read it: ``{"state", ...}`` — DRAWABLE; NOT_DRAWABLE with
    why (``background`` where the trace found no product against its ground, ``parts`` the drawing cannot draw); or
    UNCHECKED where it could not be checked now (``map_read_refused``: no key, a spending cap; a read that named no
    part; a check that raised) — such a concept is shown, and its drawing is checked again when it is chosen. The read
    is kept on the picture (``container_design_map/1.0``), so choosing it pays nothing again. One concept's check never
    stops the design."""
    from apps.pipeline.services import cost_ledger
    from apps.pipeline.targets.container import _concept_bytes, _is_face, _map_bytes, form_of_task
    # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2): "ONE ENGINE"] a face form's concept read from its lid
    # stood square; a lid its trace cannot cut from its ground is a background to redraw, as a standing product's is
    form = form_of_task(aria.task)
    pic = _map_bytes(image, form)
    if not pic:
        if _is_face(form) and _concept_bytes(image):
            return {"state": NOT_DRAWABLE, "background": True, "why": "its lid could not be cut from its ground"}
        return {"state": UNCHECKED, "why": "its picture could not be opened"}
    try:
        return _check(aria, image, pic)
    except cost_ledger.BudgetExceededError:
        raise
    except Exception as exc:  # noqa: BLE001 — one concept's check never stops the design: it is shown, said unchecked
        aria.log("ARIA: '%s' could not be checked just now — it is shown, and its drawing is checked again when you "
                 "choose it" % image.direction_name, level="warning",
                 payload={"error": "%s: %s" % (type(exc).__name__, str(exc)[:300])})
        return {"state": UNCHECKED, "why": "its check could not run just now"}


def _check(aria, image, pic: bytes) -> dict:
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.targets.container import drawable_verdict, map_read_refused
    prov = dict(image.reference_provenance or {})
    # [his second test blocker on design 123, 2026-10-09, (2)] a carton's concept read as approval reads it — by its
    # front panel (``targets.packaging.read_carton_map``) — and kept on the picture, so approval reads nothing again
    from apps.pipeline.targets import get_target
    carton = getattr(get_target(aria.task.design_target), "reads_carton_map", False) is True
    from apps.pipeline.targets.container import _is_face, form_of_task
    face = _is_face(form_of_task(aria.task))
    held = dm.held_lid_parts if face else (dm.held_carton_parts if carton else dm.held_parts)
    rec = held(prov.get(dm.SCHEMA), pic) if pic else None
    paid = "0"
    if rec is None:
        why = map_read_refused(aria.task, pic)
        if why:
            return {"state": UNCHECKED, "why": why}
        words = prov.get("container_variation_contract") or {}
        rec = (dm.read_lid_parts(aria.task, pic) if face else dm.read_carton_parts(aria.task, pic) if carton
               else dm.read_parts(aria.task, pic, structured=words))
        paid = (rec.get("cost") or {}).get("usd") or "0"
        prov[dm.SCHEMA] = rec
        image.reference_provenance = prov
        image.save(update_fields=["reference_provenance"])
    if rec.get("state") != dm.MAP_READ:
        background = rec.get("reason") == dm.MAP_NO_PRODUCT
        return {"state": NOT_DRAWABLE, "background": background, "why": "its product could not be read from the picture",
                "paid_usd": paid}
    if not rec.get("parts"):
        # a read that raised or did not parse keeps the trace and names no part: never taken for "nothing to draw"
        return {"state": UNCHECKED, "why": "its parts could not be read just now", "paid_usd": paid}
    verdict = drawable_verdict(aria.task, rec, pic)            # [his second blocker on 123, (2)] the one check
    if verdict["shapes"].get("state") != dm.SHAPES_TRACED:
        return {"state": NOT_DRAWABLE, "why": "its parts could not be traced from the picture", "paid_usd": paid}
    undrawn = verdict["undrawn"]
    if undrawn:
        return {"state": NOT_DRAWABLE, "parts": undrawn, "paid_usd": paid}
    return {"state": DRAWABLE, "paid_usd": paid}


def redraw(aria, image, backdrop: dict, leave_out: tuple = ()) -> str:
    """The concept redrawn once on ``backdrop`` — the same design, its picture replaced on the same concept (its
    variation, its prompt and its direction kept, so approval finds it as it was planned); the picture it replaced and
    what it cost kept on it (``REDRAWN_KEY``); its earlier read and stop dropped (they were the old picture's). Returns
    the cost, in dollars. ``leave_out``: the parts it is redrawn without, by name (his button's choice). A spending cap already reached refuses it before anything is paid
    (``BudgetExceededError``); a redraw that reaches the cap is kept — it is paid for — and its check then says so."""
    import base64
    import mimetypes
    import os
    import time

    import openai
    from django.conf import settings
    from django.core.files.base import ContentFile
    from django.utils import timezone

    from apps.pipeline.models import ApiCallRecord
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import cost_ledger
    from apps.pipeline.services.cost_ledger import provider_request_id, record_image
    if cost_ledger.daily_budget_exceeded():
        raise cost_ledger.BudgetExceededError("the day's spending cap is reached")
    cost_ledger.check_task_budget(aria.task)
    before = image.image_file.name
    with image.image_file.open("rb") as fh:
        old = fh.read()
    started = time.monotonic()
    # the picture as the image service takes a file: its name, its bytes and its type (a Django file field is refused —
    # MEASURED on 122's first redraw, 2026-10-07)
    kind = mimetypes.guess_type(before)[0]
    sent = (os.path.basename(before), old, kind if kind else "image/png")
    from apps.pipeline.services.cost_ledger import before_paid_call   # [his goal of 2026-10-13, (2)]
    before_paid_call("a picture")
    response = paid_operation(openai.images.edit, provider='openai', operation='readable', model=settings.IMAGE_MODEL, image=[sent],
                                  prompt=(REDRAW_WITHOUT_PROMPT.format(parts="; ".join(leave_out),
                                                                       backdrop=backdrop["words"]) if leave_out
                                          else REDRAW_PROMPT.format(backdrop=backdrop["words"])),
                                  size=settings.IMAGE_SIZE, quality=settings.IMAGE_QUALITY_CONCEPTS, n=1, timeout=180)
    operation = "image:redrawn so it can be read:%s" % image.direction_name
    try:
        record_image(settings.IMAGE_MODEL, operation=operation, image_count=1, task=aria.task,
                     metadata={"provider_request_id": provider_request_id(response),
                               "latency_ms": int((time.monotonic() - started) * 1000),
                               "redrawn_image_id": image.pk, "backdrop": backdrop["words"]})
    except cost_ledger.BudgetExceededError:
        aria.log("ARIA: the redraw of '%s' reached this design's spending cap — it is kept, it is paid for"
                 % image.direction_name, level="warning")
    row = ApiCallRecord.objects.filter(task=aria.task, operation=operation).order_by("-pk").first()
    data = response.data[0]
    new = base64.b64decode(data.b64_json)
    image.image_file.save("task_%d_var_%d_readable.png" % (aria.task.pk, image.variation_number), ContentFile(new),
                          save=False)
    prov = dict(image.reference_provenance or {})
    for gone in (dm.SCHEMA, dm.MAP_STOP_KEY, CHECK_KEY):
        prov.pop(gone, None)
    cost = str(row.cost_usd) if row is not None else "0"
    prov[REDRAWN_KEY] = {"at": timezone.now().isoformat(), "from_file": before,
                         "from_sha256": hashlib.sha256(old).hexdigest(),
                         "sha256": hashlib.sha256(new).hexdigest(), "backdrop": backdrop, "cost_usd": cost,
                         "left_out": list(leave_out),
                         "why": "his test blocker on design 122: the same design, on a backdrop it can be read on"}
    image.reference_provenance = prov
    image.save()
    return cost


def offers(task, parts: list) -> list:
    """His three offers for a concept that cannot be drawn yet, in words, each its own button — what a redraw costs as
    every other click's cost is said (``spend_estimates``, measured on this system's own ledger): one picture, its
    quality check and its map's read. Where ``parts`` the drawing cannot draw yet are the blocker, the redraw leaves
    them out, by name; else it stands the same design on a plain contrasting backdrop."""
    from apps.pipeline.spend_estimates import measured_costs
    from apps.pipeline.targets import get_target
    costs = measured_costs()
    redraw_usd = costs["image_usd"] + costs["qa_per_image_usd"] + costs["steps"]["design_map_read"]["usd"]
    # the parts are named in the reason above the buttons; the button counts them (named in it, 149's four overran it)
    words = ("Redraw it without the %s that can't be drawn yet" % ("part" if len(parts) == 1 else "%d parts" % len(parts))
             if parts else "Redraw it on a plain contrasting backdrop")
    offered = [
        {"key": "redraw", "cost_usd": "%.2f" % redraw_usd, "words": words},
        {"key": "template", "cost_usd": "0.00",
         "words": "Draw it from %s standard layout, with your brief's words — not this picture's design"
                  % _form_words(task)},
        {"key": "another", "cost_usd": "0.00", "words": "Choose another concept"},
    ]
    # [his second test blocker on design 123, (2)] a carton has no container's standard layout to draw from
    if getattr(get_target(task.design_target), "reads_carton_map", False) is True:
        offered = [o for o in offered if o["key"] != "template"]
    return offered


def _form_words(task) -> str:
    """The design's form, as the offer names it — "the tube's" — or "its form's" where none is known."""
    from apps.pipeline.targets.container import archetypes, form_of_task
    form = form_of_task(task)
    if not archetypes.is_known(form):
        return "its form's"
    return "the %s's" % archetypes.vocabulary_of(form)["label"].lower().replace(" / ", " or ")


def _after_redraw(aria, image) -> None:
    """A redrawn concept's quality checked again and its near-copies of the trend pictures read again — the score and
    the flag shown are the shown picture's."""
    from apps.pipeline.agents.qa_reviewer import QAReviewerAgent
    from apps.pipeline.services import trend_board
    QAReviewerAgent([image], aria.brand_id, log_fn=aria._log_for('QAReviewer'),
                    product_profile=aria._product_profile()).run()
    trend_board.mark_near_copies(aria.task, [image])


def _redraw_and_check(aria, image, found: dict, leave_out: tuple = ()) -> tuple:
    """``(found again, the redraw)`` — the concept redrawn on its contrasting backdrop (without ``leave_out``, by name)
    and checked again; the redraw None where a spending cap refused it (said in ``found``)."""
    from apps.pipeline.services.cost_ledger import BudgetExceededError
    from apps.pipeline.targets.container import _concept_bytes
    try:
        backdrop = backdrop_for(_concept_bytes(image))
        cost = redraw(aria, image, backdrop, leave_out)
    except BudgetExceededError:
        return {**found, "redraw_failed": "a redraw would take this design past its spending cap"}, None
    except Exception as exc:  # noqa: BLE001 — a redraw that fails changes nothing: the concept keeps its offers
        from apps.pipeline.services.pipeline_errors import is_billing_error
        aria.log("ARIA: the redraw of '%s' could not be made just now — nothing was changed" % image.direction_name,
                 level="warning", payload={"error": "%s: %s" % (type(exc).__name__, str(exc)[:300])})
        # [MEASURED on 122, 2026-10-07: the picture service's account had no credits left] said as a new design's stop
        # says it (words.PLAIN_STOP_WORDS "billing limit reached"), with what he can do
        why = ("its redraw was refused: the picture service's spending limit is reached — add credits at "
               "platform.openai.com, then press Redraw" if is_billing_error(exc)
               else "its redraw could not be made just now")
        return {**found, "redraw_failed": why}, None
    aria.log("ARIA: '%s' redrawn on a plain %s backdrop so it can be read%s — $%s"
             % (image.direction_name, backdrop["words"], (", without %s" % "; ".join(leave_out)) if leave_out else "",
                cost))
    _after_redraw(aria, image)
    return check(aria, image), {"cost_usd": cost, "backdrop": backdrop, "left_out": list(leave_out)}


def _record(aria, image, found: dict, redrawn) -> str:
    """What the check found, kept on the concept (``CHECK_KEY``) — returns its count's name."""
    from django.utils import timezone
    record = {"state": found["state"], "at": timezone.now().isoformat(), "redrawn": redrawn is not None}
    if redrawn is not None:
        record["redraw"] = redrawn
    if found["state"] == NOT_DRAWABLE:
        record.update(why=why_in_words(found), parts=found.get("parts") or [],
                      offers=offers(aria.task, [] if found.get("background") else found.get("parts") or []))
        name = "not_drawable"
    elif found["state"] == UNCHECKED:
        record["why"] = found["why"]
        name = "unchecked"
    else:
        name = "redrawn" if redrawn is not None else "drawable"
    prov = dict(image.reference_provenance or {})
    prov[CHECK_KEY] = record
    if found["state"] == DRAWABLE:
        # [his go of 2026-10-08] a stop at approval this picture's own check now finds drawable no longer holds (122's
        # 149, stopped before line art could be drawn): kept beside, under its own key, never shown as a refusal
        from apps.pipeline.services import concept_design_map as dm
        if dm.MAP_STOP_KEY in prov:
            prov[STOP_LIFTED_KEY] = dict(prov.pop(dm.MAP_STOP_KEY), lifted_at=record["at"])
    image.reference_provenance = prov
    image.save(update_fields=["reference_provenance"])
    return name


def redraw_one(aria, image) -> str:
    """[His item 4: "redraw for $X"] one concept redrawn by his button — without the parts its check or its stop at
    approval named, where those were the blocker — and checked again; returns its count's name."""
    from apps.pipeline.services import concept_design_map as dm
    prov = image.reference_provenance or {}
    held = prov.get(CHECK_KEY) or {}
    parts = (held.get("parts") if held.get("state") == NOT_DRAWABLE else None) or (prov.get(dm.MAP_STOP_KEY) or {}).get(
        "parts") or []
    found, redrawn = _redraw_and_check(aria, image, {"state": NOT_DRAWABLE}, tuple(p["name"] for p in parts))
    return _record(aria, image, found, redrawn)


def check_concepts(aria, images) -> dict:
    """[His items 2 and 4.] Every concept checked before it is shown; one the trace cannot cut from its ground redrawn
    once on a contrasting backdrop and checked again; what was found kept on each concept (``CHECK_KEY``) and said in the
    design's log — opened and ended by its own lines, the step the status shows. ``{"drawable", "redrawn",
    "not_drawable", "unchecked"}``. With the map read switched off (as under the suite's own tests), nothing is checked.
    [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2): "ONE ENGINE"] A face form's concepts are checked too,
    each read from its lid stood square — they were skipped, their lids drawn from their own reading."""
    from django.conf import settings

    counts = {"drawable": 0, "redrawn": 0, "not_drawable": 0, "unchecked": 0}
    if not settings.DESIGN_MAP_READ:
        return counts
    aria.log("ARIA: checking each concept can be drawn before it is shown")
    for image in images:
        found, redrawn = check(aria, image), None
        # Rescue: inspection only. Repairs append children through ARIA's shared allowance.
        counts[_record(aria, image, found, redrawn)] += 1
    aria.log("ARIA: each concept checked before it is shown — %d can be drawn, %d redrawn so they can, %d cannot be "
             "drawn yet (what you can do is beside each), %d not checked" % (
                 counts["drawable"], counts["redrawn"], counts["not_drawable"], counts["unchecked"]),
             payload=counts)
    return counts
