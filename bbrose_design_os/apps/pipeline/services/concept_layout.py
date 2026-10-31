"""§BH67(d)1 — THE CONCEPT IMAGE BECOMES THE ART DIRECTION: a vision step reads the approved concept and returns its
layout as structure.

OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md, LIVE): "A vision step reads the approved concept and returns its
layout as structure — each element (name, wordmark, Arabic line, motif, window, ring, rule, finishes), its position and
size as fractions of the surface, its alignment, the margins and the balance. Cost per concept is cents; report it. …
Where the vision step cannot read an element, it says so and the fixed slot is used — reported, never silent."

WHAT IT READS: the run's OWN approved concept — a GeneratedImage, the system's output — and never a REFERENCE byte
(the transcription read "the tier line" as §BH55(6)'s tier record and placement line): an image the tier record holds
as anything but PRODUCTION, or one under a reference folder, is refused by name before any call.

WHAT IT RETURNS, ``container_concept_layout/1.0``: the surface it read (its box in the picture, its shape), and each
printed element on it — its kind, the words it SAW where it is text (``seen_text``), its box as FRACTIONS OF THE
SURFACE (0..1, x right, y down, as if the surface were seen flat), its alignment, and the model's confidence; the
margins (the least fraction
between any element and each edge); the balance (the centre of the elements' boxes, weighted by area); the elements
the concept's own words name that the picture does not show (UNREAD, by name); the model, the tokens and the cost in
dollars, read from the cost ledger's own price table.

``seen_text`` IS A READING, NEVER COPY: it names what the picture shows so a person can check the read; nothing draws
it — the face prints the record's own words (§BH67(b)2, ``display_name``), and the follow pass reads only each
element's kind, box and shape. It is not named ``text`` because the brand-strings guard (§AV2/§AU5) reads a dict of
``kind`` and ``text`` as a brand tier, and a reading of a picture is not one; that guard, and the two kinds it rules
out by name, are exactly as they were.

HOW IT IS READ, CALIBRATED BEFORE IT WAS WRITTEN: the model is shown a COPY of the concept with a pixel grid drawn over
it (a line every 50 px, labelled every 100) and reads every box in pixels against the grid; the service turns them into
fractions of the surface itself. Measured on task 91's concept against its ink measured by hand (the mark 437-615 px,
'Focus' 435-632, 'فوكس' 477-600): the FAST model asked for fractions read the mark at 0.44 of the lid where its ink is
0.21, and on the grid it was still ~80 px out; the HEAVY model on the grid read the mark within ~5 px, the Arabic within
~15, the name's width within ~10 and its height ~25 px low. So the HEAVY model reads, on the grid: $0.065 on task 91 —
cents, as the ruling asks.

HOW IT IS SPENT: one call per approved concept image — cached on the spec by the image's sha256, the prompt version and
the model, so a re-confirmed profile reads the record, never the model again. The call is bound to the task, so the
cost ledger holds it under §BH55(2)'s ceilings.

WHAT IT NEVER DOES: decide a position. The record is evidence the composer reads (§BH67(d)2) under every standing rule;
a failed call, an unparseable answer or a refused image is its own state with its reason, and every element then keeps
its fixed slot — reported, never silent.
"""
from __future__ import annotations
from apps.pipeline.services.cost_ledger import BudgetExceededError as _RescueBudgetError

import hashlib
import math
import os
import tempfile
from pathlib import Path

SCHEMA = "container_concept_layout/1.0"
GOVERNED_BY = "§BH67(d)1"
PROMPT_VERSION = "3"
#: the grid drawn over the copy the model reads: a line every GRID_PX pixels, labelled every 2 * GRID_PX
GRID_PX = 50
OPERATION = "container_concept_layout"
SPEC_KEY = SCHEMA
#: §BH67(e)'s layout measure, written beside the read: each element drawn against the concept, a number per element
MEASURE_SCHEMA = "container_layout_measure/1.0"

READ, UNREAD, REFUSED, FAILED = "READ", "UNREAD", "REFUSED", "FAILED"
LAYOUT_UNREAD = "CONTAINER_CONCEPT_LAYOUT_UNREAD"
LAYOUT_REFUSED_REFERENCE = "CONTAINER_CONCEPT_LAYOUT_REFUSED_REFERENCE_IMAGE"

#: the kinds of element the reader names — the ruling's own list, with the text tiers the composer draws
ELEMENTS = ("mark", "name", "name_ar", "descriptor", "other_text", "window", "ring", "motif", "rule", "band", "finish")
ALIGNMENTS = ("left", "centre", "right")
SHAPES = ("round", "oval", "rounded_rect", "rect", "other")

SYSTEM = """You read a photographic CONCEPT render of a cosmetics container and return, as structure, the layout of the
artwork printed on ONE named surface of it. You measure what the picture shows; you invent nothing and you do not
design. Where you cannot see an element clearly, you leave it out and name it under "unread".

The picture is drawn over with a PIXEL GRID: blue vertical lines every 50 px (labelled every 100 px along the top),
orange horizontal lines every 50 px (labelled every 100 px down the left). Its size is given with the request. Read
EVERY coordinate AGAINST THE GRID LINES — never guess. Every box is [x0, y0, x1, y1] in PIXELS of the picture, x to the
right, y down, tight around the element's visible ink.
- "surface_box": the named surface's box.
- each element's "box": its own box, inside the surface.

Elements — use exactly these kinds:
  "mark"       the brand wordmark/lockup (e.g. BBROSE)
  "name"       the product name in Latin letters — give the exact words you see as "seen_text"
  "name_ar"    the product name in Arabic letters — give the exact words you see as "seen_text"
  "descriptor" a supporting line (what the product is)
  "other_text" any other printed text (a shade name, a number) — give the words you see as "seen_text"
  "window"     a framed panel or cartouche holding the motif
  "ring"       a line ring running round the surface or an element
  "motif"      the decorative drawing (petals, drops, lines) — its whole extent
  "rule"       a single straight line
  "band"       a filled stripe or band
  "finish"     a distinct finish area (foil, gloss) not already covered — say which in "finish"
For each element: "kind", "box", "align" ("left" | "centre" | "right" — how it sits across the surface),
"seen_text" (text elements only: the words exactly as the picture shows them), "finish" (e.g. "rose-gold foil",
"none"), "shape" (for window/ring: "oval", "round", "rounded_rect", "rect"), "confidence" 0..1.

Also give: "surface_shape" ("round" | "oval" | "rounded_rect" | "rect" | "other"); "unread": the element kinds the
concept's words below name that you cannot find in the picture; "notes": one short line.

Respond ONLY with valid JSON:
{"surface": "<the surface named>", "surface_box": [x0,y0,x1,y1], "surface_shape": "...",
 "elements": [{"kind": "...", "box": [x0,y0,x1,y1], "align": "...", "seen_text": "...", "finish": "...",
               "shape": "...",
               "confidence": 0.0}],
 "unread": ["..."], "notes": "..."}"""


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _px_box(value, size) -> list[float] | None:
    """A pixel box inside the picture of ``size`` (w, h), or None."""
    try:
        x0, y0, x1, y1 = (float(v) for v in value)
    except (TypeError, ValueError):
        return None
    w, h = size
    if not (0.0 <= x0 < x1 <= w and 0.0 <= y0 < y1 <= h):
        return None
    return [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)]


def _gridded_copy(image_path: str, scratch: str) -> tuple[str, tuple[int, int]]:
    """A COPY of the concept with the pixel grid drawn over it, in the caller's ``scratch`` directory — the concept
    itself is never written. Returns (the copy's path, the picture's (width, height))."""
    from PIL import Image, ImageDraw
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    d = ImageDraw.Draw(img)
    for x in range(0, w, GRID_PX):
        d.line([(x, 0), (x, h)], fill=(0, 140, 255) if x % (2 * GRID_PX) == 0 else (120, 200, 255), width=1)
        if x % (2 * GRID_PX) == 0:
            d.text((x + 2, 2), str(x), fill=(0, 60, 200))
    for y in range(0, h, GRID_PX):
        d.line([(0, y), (w, y)], fill=(255, 120, 0) if y % (2 * GRID_PX) == 0 else (255, 200, 140), width=1)
        if y % (2 * GRID_PX) == 0:
            d.text((2, y + 2), str(y), fill=(200, 60, 0))
    path = os.path.join(scratch, "concept_layout_grid.png")
    img.save(path)
    return path, (w, h)


def validate(payload, size=(1, 1)) -> tuple[dict, list[str]]:
    """The model's answer, kept to what can be vouched for: the surface's pixel box inside the picture of ``size``;
    every element of a declared kind with a pixel box inside it, turned into FRACTIONS OF THE SURFACE (``box``; the
    pixels kept as ``box_px``); everything else dropped and NAMED. Returns (the kept structure, the problems)."""
    problems: list[str] = []
    if not isinstance(payload, dict):
        return {}, ["the answer is not a JSON object"]
    surface_px = _px_box(payload.get("surface_box"), size)
    if surface_px is None:
        problems.append("surface_box missing or not a box inside the picture")
    shape = payload.get("surface_shape") if payload.get("surface_shape") in SHAPES else "other"
    kept = []
    for i, e in enumerate(payload.get("elements") or []):
        if not isinstance(e, dict):
            problems.append(f"elements[{i}] is not an object")
            continue
        kind, px = e.get("kind"), _px_box(e.get("box"), size)
        if kind not in ELEMENTS:
            problems.append(f"elements[{i}] kind {kind!r} is not one of the declared kinds")
            continue
        box = None
        if px is not None and surface_px is not None:
            sx0, sy0, sx1, sy1 = surface_px
            fr = [(px[0] - sx0) / (sx1 - sx0), (px[1] - sy0) / (sy1 - sy0),
                  (px[2] - sx0) / (sx1 - sx0), (px[3] - sy0) / (sy1 - sy0)]
            # a box may graze the surface's edge by the read's own slack; one mostly outside it is not on it
            inside = (min(fr[2], 1.0) - max(fr[0], 0.0)) * (min(fr[3], 1.0) - max(fr[1], 0.0))
            area = (fr[2] - fr[0]) * (fr[3] - fr[1])
            if area > 0 and inside >= 0.5 * area:
                box = [round(min(max(v, 0.0), 1.0), 4) for v in fr]
        if box is None:
            problems.append(f"elements[{i}] ({kind}) box {e.get('box')!r} is not a box on the surface")
            continue
        raw = e.get("confidence")
        confidence = round(float(raw), 2) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None
        if raw is not None and confidence is None:          # an answer the model shaped wrongly is named, never a crash
            problems.append(f"elements[{i}] ({kind}) confidence {raw!r} is not a number")
        row = {"kind": kind, "box": box, "box_px": px,
               "align": e.get("align") if e.get("align") in ALIGNMENTS else "centre",
               "confidence": confidence}
        for k in ("seen_text", "finish", "shape"):
            if isinstance(e.get(k), str) and e[k].strip():
                row[k] = e[k].strip()[:80]
        kept.append(row)
    unread = sorted({str(u) for u in (payload.get("unread") or []) if str(u) in ELEMENTS})
    return {"surface_box": surface_px, "surface_shape": shape, "elements": kept, "unread": unread,
            "notes": payload["notes"][:240] if isinstance(payload.get("notes"), str) else None}, problems


def margins_and_balance(elements: list[dict]) -> tuple[dict | None, dict | None]:
    """The least fraction between any element and each edge, and the area-weighted centre of the elements."""
    if not elements:
        return None, None
    margins = {"left": min(e["box"][0] for e in elements), "top": min(e["box"][1] for e in elements),
               "right": min(1.0 - e["box"][2] for e in elements), "bottom": min(1.0 - e["box"][3] for e in elements)}
    total = sum((e["box"][2] - e["box"][0]) * (e["box"][3] - e["box"][1]) for e in elements)
    if total <= 0:
        return {k: round(v, 4) for k, v in margins.items()}, None      # no area: no centre to weigh
    cx = sum((e["box"][0] + e["box"][2]) / 2.0 * (e["box"][2] - e["box"][0]) * (e["box"][3] - e["box"][1])
             for e in elements) / total
    cy = sum((e["box"][1] + e["box"][3]) / 2.0 * (e["box"][2] - e["box"][0]) * (e["box"][3] - e["box"][1])
             for e in elements) / total
    return ({k: round(v, 4) for k, v in margins.items()},
            {"x": round(cx, 4), "y": round(cy, 4), "horizontal": "centred" if abs(cx - 0.5) <= 0.05 else
             ("left" if cx < 0.5 else "right")})


def refused_reason(image_path: str) -> str | None:
    """Why this image may not be read into a layout, or None: a REFERENCE-class folder, or a tier-record row other than
    PRODUCTION — the §BH54(b) (k) 3 door the exploration render uses, decided on the bytes."""
    try:
        from apps.dashboard import history
        resolved = Path(image_path).resolve()
        folder = history.reference_folder(resolved, history.media_root())
        if folder:
            return "under media/%s, a REFERENCE-class directory" % folder
        row = history.tiers_by_sha().get(history.sha256_of(resolved))
        if row and row != ["PRODUCTION"]:
            return "tier %s by the tier record" % " + ".join(row)
    except Exception as exc:  # noqa: BLE001 — a door that cannot be checked is not open
        if isinstance(exc, _RescueBudgetError):
            raise
        return "the tier record could not be read (%s: %s) — not read, rather than read unchecked" % (
            type(exc).__name__, str(exc)[:120])
    return None


def _concept_words(structured: dict | None) -> str:
    keep = ("typography_signature", "composition_signature", "decoration_zone_signature", "motif_signature",
            "finish_signature")
    return "\n".join(f"{k}: {structured.get(k)}" for k in keep if (structured or {}).get(k))


def read_layout(task, *, image_path: str, surface: str, surface_words: str, structured: dict | None,
                call=None) -> dict:
    """One vision read of the approved concept — the record, whatever happened. ``call`` stands in for
    ``claude_service.call_claude`` (tests); it returns the provider response."""
    from django.conf import settings
    model = settings.CLAUDE_MODEL_HEAVY          # calibrated: the only model that read task 91's boxes on the grid
    record = {"schema_version": SCHEMA, "governed_by": GOVERNED_BY, "prompt_version": PROMPT_VERSION,
              "model": model, "surface": surface, "image": {"path": str(image_path), "sha256": None},
              "state": UNREAD, "elements": [], "unread": [], "problems": [], "codes": [],
              "cost": {"usd": "0.000000", "input_tokens": 0, "output_tokens": 0, "calls": 0}}
    if not image_path or not Path(image_path).exists():
        record.update(state=UNREAD, why="no approved concept image on this run")
        record["codes"].append(f"{LAYOUT_UNREAD}: no approved concept image")
        return record
    record["image"]["sha256"] = _sha256(image_path)
    refused = refused_reason(image_path)
    if refused:
        record.update(state=REFUSED, why=refused)
        record["codes"].append(f"{LAYOUT_REFUSED_REFERENCE}: {refused}")
        return record
    from apps.pipeline.services import claude_service as cs
    from apps.pipeline.services.cost_ledger import claude_cost_usd, task_cost_context
    # the gridded copy lives only inside this directory, which is removed on every way out of it
    with tempfile.TemporaryDirectory(prefix="concept_layout_", ignore_cleanup_errors=True) as scratch:
        try:
            gridded, size = _gridded_copy(str(image_path), scratch)
        except Exception as exc:  # noqa: BLE001 — a picture that cannot be opened is not read
            if isinstance(exc, _RescueBudgetError):
                raise
            record.update(state=UNREAD, why="the approved concept could not be opened (%s)" % str(exc)[:160])
            record["codes"].append(f"{LAYOUT_UNREAD}: the concept could not be opened")
            return record
        record["image"]["size_px"] = list(size)
        content = [cs.image_block_from_file(gridded),
                   {"type": "text", "text": ("THE PICTURE is %d x %d pixels. THE SURFACE TO READ: %s — %s.\n\nThe "
                                             "concept's own words, for naming what you see (never for placing it — "
                                             "place only what the picture shows):\n%s\n\nReturn the JSON now."
                                             % (size[0], size[1], surface, surface_words,
                                                _concept_words(structured)))}]
        try:
            with task_cost_context(task):
                response = (call or cs.call_claude)(SYSTEM, content, max_tokens=2500, model=model,
                                                    operation=OPERATION)
        except Exception as exc:  # noqa: BLE001 — the record says what failed; the fixed slots are used
            if isinstance(exc, _RescueBudgetError):
                raise
            record.update(state=FAILED, why="the vision call raised %s: %s" % (type(exc).__name__, str(exc)[:200]))
            record["codes"].append(f"{LAYOUT_UNREAD}: the vision call failed")
            return record
    try:
        tin, tout = int(response.usage.input_tokens), int(response.usage.output_tokens)
    except (AttributeError, TypeError, ValueError) as exc:
        record.update(state=FAILED, why="the answer carries no token usage (%s) — its cost cannot be stated, so it is "
                                        "not read" % type(exc).__name__)
        record["codes"].append(f"{LAYOUT_UNREAD}: the answer carries no token usage")
        return record
    record["cost"] = {"usd": str(claude_cost_usd(model, tin, tout)), "input_tokens": tin, "output_tokens": tout,
                      "calls": 1, "source": "cost_ledger.claude_cost_usd — the ledger's own price table"}
    try:
        payload = cs.loads_tolerant(cs.extract_text(response))
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, _RescueBudgetError):
            raise
        record.update(state=FAILED, why="the answer did not parse as JSON (%s)" % str(exc)[:160])
        record["codes"].append(f"{LAYOUT_UNREAD}: the answer did not parse")
        return record
    kept, problems = validate(payload, size)
    record.update(kept)
    record["problems"] = problems
    margins, balance = margins_and_balance(kept.get("elements") or [])
    record.update(margins=margins, balance=balance)
    if kept.get("surface_box") is None or not kept.get("elements"):
        record.update(state=UNREAD, why="the answer holds no surface box or no element inside it")
        record["codes"].append(f"{LAYOUT_UNREAD}: nothing readable on the surface")
        return record
    record["state"] = READ
    record["codes"] += [f"{LAYOUT_UNREAD}: {kind}" for kind in kept.get("unread") or []]
    return record


def cached(spec: dict, image_path) -> tuple[dict | None, str]:
    """THE ONE CACHE CHECK: the spec's record when it read THIS image under THIS prompt and model, as
    ``(dict(record, cached=True), "")``, or ``(None, why not)`` in plain words. ``cached_or_read`` reads the picture
    afresh when this finds nothing, which is a paid vision call. The design loop never pays, so it refuses by name
    instead (apps/dashboard/exploration_render.py). [The owner's goal of 2026-09-25, "THE UI, DESIGNED THIS TIME", rule
    (d): "The library is usable WHILE designing, not a separate trip." — and §BH51's goal state, LIVE: "no generation
    spend without my word".]"""
    from django.conf import settings
    held = (spec or {}).get(SPEC_KEY) or {}
    if not held:
        return None, "no reading of the concept picture is on the design's record"
    if not (image_path and Path(image_path).exists()):
        return None, "the design has no approved concept picture on disk to match its reading to"
    if held.get("prompt_version") != PROMPT_VERSION or held.get("model") != settings.CLAUDE_MODEL_HEAVY:
        return None, ("the reading on the record was made under another prompt or model (prompt %s, %s), not the "
                      "ones the governed path reads with now" % (held.get("prompt_version"), held.get("model")))
    if (held.get("image") or {}).get("sha256") != _sha256(image_path):
        return None, "the reading on the record is of another picture, not the design's approved concept"
    if held.get("state") not in (READ, REFUSED):
        return None, "the last attempt did not read the picture (it ended %s)" % held.get("state")
    return dict(held, cached=True), ""


def cached_or_read(task, spec: dict, **kw) -> dict:
    """The spec's record when it read THIS image under THIS prompt and model; a new read otherwise."""
    held, _why = cached(spec, kw.get("image_path"))
    return held if held is not None else read_layout(task, **kw)


def measure(layout: dict | None, drawn: dict[str, list[float]]) -> list[dict]:
    """§BH67(e)'s layout measure: each element's position and size in the DRAWN file against the concept's, as
    fractions of the surface. ``drawn`` is {kind: [x0, y0, x1, y1]} in surface fractions. Per element: the centre's
    offset (dx, dy), the distance between the centres, and the width and height ratios drawn / concept."""
    rows = []
    concept = {}
    for e in (layout or {}).get("elements") or []:
        concept.setdefault(e["kind"], e["box"])
    for kind in sorted(set(concept) | set(drawn)):
        c, d = concept.get(kind), drawn.get(kind)
        if not c or not d:
            rows.append({"element": kind, "state": "NOT_IN_CONCEPT" if not c else "NOT_DRAWN",
                         "concept": c, "drawn": d})
            continue
        ccx, ccy = (c[0] + c[2]) / 2.0, (c[1] + c[3]) / 2.0
        dcx, dcy = (d[0] + d[2]) / 2.0, (d[1] + d[3]) / 2.0
        rows.append({"element": kind, "state": "MEASURED", "concept": c, "drawn": d,
                     "dx": round(dcx - ccx, 4), "dy": round(dcy - ccy, 4),
                     "distance": round(math.hypot(dcx - ccx, dcy - ccy), 4),
                     "width_ratio": round((d[2] - d[0]) / (c[2] - c[0]), 3),
                     "height_ratio": round((d[3] - d[1]) / (c[3] - c[1]), 3)})
    return rows


__all__ = ["SCHEMA", "GOVERNED_BY", "PROMPT_VERSION", "OPERATION", "SPEC_KEY", "MEASURE_SCHEMA", "READ", "UNREAD", "REFUSED", "FAILED",
           "LAYOUT_UNREAD", "LAYOUT_REFUSED_REFERENCE", "ELEMENTS", "SYSTEM", "validate", "margins_and_balance",
           "refused_reason", "read_layout", "cached", "cached_or_read", "measure"]
