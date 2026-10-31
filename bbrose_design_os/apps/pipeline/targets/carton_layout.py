"""[His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (1): "NO GUESSED
PANELS. After I pick a concept, draw ONE more picture of the same design as a flat carton layout (front, both sides,
back, flaps, same style), ~$0.25, never printed, read into the map like the front. Every panel is drawn from it."]

The carton's layout picture — drawn once from the concept he chose, kept on it, never printed (his finding on 119:
"KILL THE RASTER PATH": no picture is ever placed on a carton) — and its read: each panel's box and the parts printed on
it, each panel a map as the front's is (``concept_design_map.carton_record``), checked against the carton's own die
before any panel is drawn from it; a panel the picture does not give continues the front (his (2)), said why."""
from __future__ import annotations
from apps.pipeline.services.cost_ledger import BudgetExceededError as _RescueBudgetError
from apps.pipeline.services.spend_reservation import paid_operation

import hashlib

#: what the layout picture, its read and its panels are kept under on the concept (``reference_provenance``)
LAYOUT_KEY = "carton_layout/1.0"
LAYOUT_MAP_KEY = "carton_layout_map/1.0"
LAYOUT_PROMPT_VERSION = "layout-1"
#: the image service's landscape size: the sheet is wider than it is tall
LAYOUT_SIZE = "1536x1024"
#: the ledger's names for the picture and its read
LAYOUT_OPERATION = "image:carton layout:%s"
LAYOUT_READ_OPERATION = "carton_layout_parts"
#: the panels the picture lays out: one row, left to right; a flap above and one below the front
ROW = ("back", "side_left", "front", "side_right")
FLAPS = ("top_flap", "bottom_flap")
#: a panel's box in the picture is taken where its width against the front's is within this share of the die's own
#: (a back as wide as the front, a side as the die's depth against its width), and its height within HEIGHT_SHARE
WIDTH_SHARE = 0.35
HEIGHT_SHARE = 0.2

LAYOUT_PROMPT = (
    "Redraw THIS design as its flat printed sheet, laid flat and seen straight on: ONE row of four tall panels, left "
    "to right — the BACK, the LEFT SIDE, the FRONT, the RIGHT SIDE — the back as wide as the front, each side {side}% "
    "as wide as the front, every panel {tall} times as tall as the front is wide; the top flap above the front and the "
    "bottom flap below it. The FRONT exactly as the picture shows it; the back, the sides and the flaps in the same "
    "style, colours, pattern and lettering, continuing the design round, the back carrying a plain area for the "
    "information label. Each panel a clean flat rectangle with straight edges, a thin white gap between the panels, on "
    "a plain white background. No 3D, no perspective, no shadow, no mockup, no hands, no props, no extra words.")


#: [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (2): "A palette or compact lies flat: its box's front is the
#: lid's face (landscape)."] the sheet of a box lying flat, as it is seen: its panels one above the other, each wide
LAYOUT_PROMPT_FLAT = (
    "Redraw THIS design as its flat printed sheet, laid flat and seen straight on: ONE column of four wide panels, top "
    "to bottom — the BACK, the TOP SIDE, the FRONT, the BOTTOM SIDE — the back as wide and as tall as the front, each "
    "side {side}% as tall as the front, every panel {wide} times as wide as the front is tall; the end flaps at the "
    "left and at the right of the front. The FRONT exactly as the picture shows it, wide; the back, the sides and the "
    "flaps in the same style, colours, pattern and lettering, continuing the design round, the back carrying a plain "
    "area for the information label. Each panel a clean flat rectangle with straight edges, a thin white gap between "
    "the panels, on a plain white background. No 3D, no perspective, no shadow, no mockup, no hands, no props, no extra "
    "words.")
LAYOUT_SIZE_FLAT = "1024x1536"
LAYOUT_PROMPT_VERSION_FLAT = "layout-flat-1"


def lies_flat(dims) -> bool:
    """[His goal of 2026-10-13, (2).] Whether a carton of ``dims`` lies flat (its size step's own word for it)."""
    return isinstance(dims, dict) and dims.get("orientation") == "flat"


def layout_prompt(dims: dict) -> str:
    """The picture's words for a carton of ``dims`` (its confirmed size): its sides' and its height's share of its
    front's width — [his goal of 2026-10-13, (2)] a box lying flat as it is seen, its front wide."""
    width, depth, height = (float(dims[k]) for k in ("width_mm", "depth_mm", "height_mm"))
    if lies_flat(dims):
        return LAYOUT_PROMPT_FLAT.format(side=int(round(100.0 * depth / width)), wide=round(height / width, 1))
    return LAYOUT_PROMPT.format(side=int(round(100.0 * depth / width)), tall=round(height / width, 1))


def _concept_sha(image) -> str:
    with image.image_file.open("rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def kept_layout(image, dims=None) -> dict | None:
    """The layout picture kept on the concept, where it was drawn from THIS picture — [his goal of 2026-10-13, (2)] and,
    where the carton's size is given, for a box lying as it lies (a picture of the box standing is never laid on a box
    lying flat); else None."""
    prov = getattr(image, "reference_provenance", None)
    prov = prov if isinstance(prov, dict) else {}
    record = prov.get(LAYOUT_KEY)
    if not isinstance(record, dict) or record.get("concept_sha256") != _concept_sha(image):
        return None
    if dims is not None and (record.get("orientation") == "flat") != lies_flat(dims):
        return None
    return record


def layout_bytes(record: dict) -> bytes:
    from django.core.files.storage import default_storage
    with default_storage.open(record["file"], "rb") as fh:
        return fh.read()


def make_layout(aria, image, dims: dict) -> dict:
    """The layout picture drawn once from the concept ``image`` — a paid picture, on the ledger as "image:carton
    layout:<its direction>", its file and what it cost kept on the concept (``LAYOUT_KEY``), never printed. A spending
    cap already reached refuses it before anything is paid (``BudgetExceededError``)."""
    import base64
    import mimetypes
    import os
    import time

    import openai
    from django.conf import settings
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from django.utils import timezone

    from apps.pipeline.models import ApiCallRecord
    from apps.pipeline.services import cost_ledger
    from apps.pipeline.services.cost_ledger import provider_request_id, record_image
    from apps.pipeline.services.flat_motif import _capped
    if cost_ledger.daily_budget_exceeded():
        raise cost_ledger.BudgetExceededError("the day's spending cap is reached")
    cost_ledger.check_task_budget(aria.task)
    with image.image_file.open("rb") as fh:
        concept = fh.read()
    kind = mimetypes.guess_type(image.image_file.name)[0]
    sent = (os.path.basename(image.image_file.name), concept, kind if kind else "image/png")
    started = time.monotonic()
    from apps.pipeline.services.cost_ledger import before_paid_call   # [his goal of 2026-10-13, (2)]
    before_paid_call("a picture", fidelity=True)   # [his goal for the pitch, B (6)] fidelity is paid for
    response = paid_operation(openai.images.edit, provider='openai', operation='carton_layout', model=settings.IMAGE_MODEL, image=[sent], prompt=layout_prompt(dims),
                                  size=LAYOUT_SIZE_FLAT if lies_flat(dims) else LAYOUT_SIZE,
                                  quality=settings.IMAGE_QUALITY_CONCEPTS, n=1, timeout=180)
    operation = LAYOUT_OPERATION % image.direction_name
    if _capped(record_image, settings.IMAGE_MODEL, operation, aria.task,
               {"provider_request_id": provider_request_id(response),
                "latency_ms": int((time.monotonic() - started) * 1000), "concept_image_id": image.pk}):
        aria.log("ARIA: the carton's layout picture reached this design's spending cap — it is kept, it is paid for",
                 level="warning")
    row = ApiCallRecord.objects.filter(task=aria.task, operation=operation).order_by("-pk").first()
    drawn = base64.b64decode(response.data[0].b64_json)
    name = default_storage.save("concepts/task_%d_layout_%d.png" % (aria.task.pk, image.pk), ContentFile(drawn))
    record = {"file": name, "sha256": hashlib.sha256(drawn).hexdigest(),
              "concept_sha256": hashlib.sha256(concept).hexdigest(),
              "size": LAYOUT_SIZE_FLAT if lies_flat(dims) else LAYOUT_SIZE,
              "dims": {k: float(dims[k]) for k in ("width_mm", "depth_mm", "height_mm")},
              **({"orientation": "flat"} if lies_flat(dims) else {}),
              "prompt_version": LAYOUT_PROMPT_VERSION_FLAT if lies_flat(dims) else LAYOUT_PROMPT_VERSION,
              "model": settings.IMAGE_MODEL,
              "cost_usd": str(row.cost_usd) if row is not None else "0", "at": timezone.now().isoformat(),
              "why": "his test findings on design 123, (1): every panel drawn from one more picture of the design, "
                     "never printed"}
    prov = dict(image.reference_provenance or {})
    prov[LAYOUT_KEY] = record
    prov.pop(LAYOUT_MAP_KEY, None)                 # the read was of another picture
    image.reference_provenance = prov
    image.save(update_fields=["reference_provenance"])
    aria.log("ARIA: the carton's layout picture drawn from '%s' — its back, sides and flaps, never printed — $%s"
             % (image.direction_name, record["cost_usd"]))
    return record


LAYOUT_SYSTEM = """You read ONE picture: the FLAT PRINTED SHEET of a folding carton's design, its panels laid out flat and
seen straight on, and name each PANEL and the parts of the DESIGN printed on it, so that each panel can be drawn exactly
as the picture shows it. You measure what the picture shows; you invent nothing and you do not design.

THE PANELS: one row of four tall panels, left to right — "back", "side_left", "front", "side_right" — and the flaps:
"top_flap" above the front, "bottom_flap" below it. For each panel you can see, its "box" [x0, y0, x1, y1]: the panel
ONLY, tight to its edges — never the white around it or a gap between panels. Leave out a panel you cannot see.

The picture is drawn over with a PIXEL GRID: blue vertical lines every 50 px (labelled every 100 px along the top),
orange horizontal lines every 50 px (labelled every 100 px down the left). Read EVERY coordinate AGAINST THE GRID
LINES — never guess. Every box is [x0, y0, x1, y1] in PIXELS of the picture, x right, y down.

Parts of each panel's design — use exactly these kinds, every box inside its panel's box:
  "field"    the panel's ground colour, or a large area of one printed colour on it (one part each)
  "shape"    a solid printed graphic in one colour — a silhouette, a big flat shape
  "band"     a stripe or band across the panel
  "mark"     the brand wordmark or lockup (e.g. BBROSE)
  "type"     any other printed text: one part per line or block — the exact words you see as "seen_text", the
             lettering as "lettering": "script" | "serif" | "sans" | "display" | "arabic", and "rotation": 0 when it
             reads left to right, 90 when it reads bottom to top, -90 when it reads top to bottom
  "rule"     a thin line
  "motif"    a drawn decoration — line art, repeated flowers, dots, sparkles: one part per kind, its whole extent
  "window"   a framed panel or cartouche, or a plain area left for a label
For each part: "kind", "name" (a few plain words), "box", "seen_text" (type and mark only), "lettering" and "rotation"
(type only), "finish" (e.g. "gold foil", "none"), "confidence" 0..1.

Respond ONLY with valid JSON:
{"panels": [{"panel": "...", "box": [x0,y0,x1,y1],
             "parts": [{"kind": "...", "name": "...", "box": [x0,y0,x1,y1], "seen_text": "...", "lettering": "...",
                        "rotation": 0, "finish": "...", "confidence": 0.0}]}],
 "notes": "..."}"""


LAYOUT_SYSTEM_FLAT = LAYOUT_SYSTEM.replace(
    """THE PANELS: one row of four tall panels, left to right — "back", "side_left", "front", "side_right" — and the flaps:
"top_flap" above the front, "bottom_flap" below it.""",
    """THE PANELS: one column of four wide panels, top to bottom — "back", "side_left" (the top side), "front",
"side_right" (the bottom side) — and the flaps: "top_flap" at the right of the front, "bottom_flap" at its left.""")


def read_layout(task, picture: bytes, dims: dict, *, call=None) -> dict:
    """The layout picture read — one vision call (``LAYOUT_SYSTEM``) on the picture at the map's scale under the parts
    read's own grid, its cost on this design's ledger — and each panel it names made a map as the front's is
    (``carton_record``: its box the face, each part's box a fraction of it, its colours from its own pixels), then
    checked against the carton's die (``check_panels``). ``{"panels": {name: map}, "checked": {name: why or None},
    "cost", "sha256"}``; a read that fails is kept so, by name, and every panel continues the front."""
    import base64

    from django.conf import settings

    from apps.pipeline.services import claude_service as cs
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import concept_outline as co
    from apps.pipeline.services.cost_ledger import BudgetExceededError, claude_cost_usd, task_cost_context
    model = settings.CLAUDE_MODEL_HEAVY
    sha = hashlib.sha256(picture).hexdigest()
    out = {"schema_version": LAYOUT_MAP_KEY, "sha256": sha, "model": model, "panels": {}, "checked": {},
           "cost": {"usd": "0.000000", "calls": 0}}
    img, _s = co._read(picture)
    if img is None:
        return dict(out, unread="the layout picture could not be opened")
    grid, _origin, size = dm._parts_picture(img, {"product_box_px": [0, 0, img.shape[1], img.shape[0]]})
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                            "data": base64.b64encode(grid).decode()}},
               {"type": "text", "text": "THE PICTURE is %d x %d pixels.\n\nReturn the JSON now." % size}]
    try:
        with task_cost_context(task):
            response = (call or cs.call_claude)(LAYOUT_SYSTEM_FLAT if lies_flat(dims) else LAYOUT_SYSTEM, content,
                                                max_tokens=6000, model=model, operation=LAYOUT_READ_OPERATION)
        tin, tout = int(response.usage.input_tokens), int(response.usage.output_tokens)
    except BudgetExceededError:
        raise
        raise
    except Exception as exc:  # noqa: BLE001 — the record says what failed; every panel continues the front
        if isinstance(exc, _RescueBudgetError):
            raise
        return dict(out, unread="the read raised %s: %s" % (type(exc).__name__, str(exc)[:200]))
    out["cost"] = {"usd": str(claude_cost_usd(model, tin, tout)), "input_tokens": tin, "output_tokens": tout,
                   "calls": 1, "source": "cost_ledger.claude_cost_usd — the ledger's own price table"}
    try:
        payload = cs.loads_tolerant(cs.extract_text(response))
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, _RescueBudgetError):
            raise
        return dict(out, unread="the answer did not parse (%s)" % str(exc)[:160])
    named = {}
    for item in (payload.get("panels") if isinstance(payload, dict) else None) or []:
        if isinstance(item, dict) and item.get("panel") in ROW + FLAPS and item["panel"] not in named:
            named[item["panel"]] = item
    for panel, item in named.items():
        rec = dm.carton_record(picture, {"face": item.get("box"), "parts": item.get("parts") or [], "light": []},
                               model=model, cost={"usd": "0", "calls": 0, "of": LAYOUT_READ_OPERATION})
        out["panels"][panel] = rec
    out["checked"] = check_panels(out["panels"], dims)
    return out


def check_panels(panels: dict, dims: dict) -> dict:
    """``{panel: None where its map is drawn from, else why it continues the front}`` — each of the row's panels and
    each flap checked against the carton's die: read, inside the picture, the row's in order left to right, none on
    another, its width against the front's within WIDTH_SHARE of the die's (the back the front's, a side its depth's)
    and its height within HEIGHT_SHARE of the front's. The front is always the concept's own: never drawn from here."""
    from apps.pipeline.services.concept_design_map import MAP_READ
    width, depth = float(dims["width_mm"]), float(dims["depth_mm"])
    want = {"back": 1.0, "side_left": depth / width, "side_right": depth / width}
    flat = lies_flat(dims)      # [his goal of 2026-10-13, (2)] a column: a side's height against the front's, by y
    out = {}
    front = panels.get("front")
    fbox = front.get("face_box_px") if isinstance(front, dict) and front.get("state") == MAP_READ else None
    for name in ("back", "side_left", "side_right") + FLAPS:
        rec = panels.get(name)
        if not isinstance(rec, dict) or rec.get("state") != MAP_READ:
            out[name] = "the layout picture's read did not find it" if rec is None else (
                "its read did not take: %s" % rec.get("detail"))
            continue
        if fbox is None:
            out[name] = "the read found no front to measure it against"
            continue
        box = rec["face_box_px"]
        fw, fh = fbox[2] - fbox[0], fbox[3] - fbox[1]
        bw, bh = box[2] - box[0], box[3] - box[1]
        if flat:                    # the picture's column, measured as the row is: its across the die, its along
            fw, fh, bw, bh = fh, fw, bh, bw
        if name in want:
            got = bw / max(fw, 1)
            if abs(got / want[name] - 1.0) > WIDTH_SHARE:
                out[name] = "it stands %.2f as wide as the front in the picture, the die %.2f" % (got, want[name])
                continue
            if abs(bh / max(fh, 1) - 1.0) > HEIGHT_SHARE:
                out[name] = "it stands %.2f as tall as the front in the picture" % (bh / max(fh, 1))
                continue
        out[name] = None
    # the row in order, none on another
    lo, hi = (1, 3) if flat else (0, 2)
    xs = [(panels[n]["face_box_px"][lo], panels[n]["face_box_px"][hi], n) for n in ROW
          if isinstance(panels.get(n), dict) and panels[n].get("state") == MAP_READ]
    order = [n for _x0, _x1, n in sorted(xs)]
    expected = [n for n in ROW if n in order]
    if order != expected:
        for n in ROW:
            if n != "front" and out.get(n) is None:
                out[n] = "the picture lays the panels out of order (%s)" % ", ".join(order)
    for (a0, a1, a), (b0, b1, b) in zip(sorted(xs), sorted(xs)[1:]):
        if a1 > b0 + 2:
            for n in (a, b):
                if n != "front" and out.get(n) is None:
                    out[n] = "it lies on the %s in the picture" % (b if n == a else a)
    return out


def kept_layout_read(image, dims=None) -> dict | None:
    """The layout picture's read kept on the concept, where it read the picture kept on it; else None."""
    record = kept_layout(image, dims)
    if record is None:
        return None
    read = image.reference_provenance.get(LAYOUT_MAP_KEY)
    if not isinstance(read, dict) or read.get("sha256") != record.get("sha256"):
        return None
    return read


#: [his goal of 2026-10-13, (1) and (2)] the carton's layout picture not made: its back, sides and flaps continue its
#: front — said beside Approve, with why
LAYOUT_NOT_MADE = "CARTON_LAYOUT_PICTURE_NOT_MADE"


def ensure_layout(aria, image, dims: dict, said: list | None = None) -> dict | None:
    """[His test findings on design 123, (1).] The concept's layout picture and its read, each made once and kept on the
    concept — a design drawn again pays nothing — or None, said in the design's log, where either cannot be made now (a
    spending cap, the picture service, the read): every panel then continues the front, never refused."""
    from apps.pipeline.services.cost_ledger import BudgetExceededError
    try:
        record = kept_layout(image, dims)
        if record is None:
            if kept_layout(image) is not None:      # [his goal of 2026-10-13, (2)] drawn for the box lying otherwise
                aria.log("ARIA: the carton's layout picture kept on the concept was drawn for the box lying otherwise — "
                         "it is not used, and is drawn for this one", level="warning")
            record = make_layout(aria, image, dims)
        read = kept_layout_read(image, dims)
        if read is None:
            read = read_layout(aria.task, layout_bytes(record), dims)
            prov = dict(image.reference_provenance or {})
            prov[LAYOUT_MAP_KEY] = read
            image.reference_provenance = prov
            image.save(update_fields=["reference_provenance"])
            aria.log("ARIA: the carton's layout picture read — %s — $%s" % (
                "; ".join("%s: %s" % (name, "drawn from it" if why is None else "continues the front (%s)" % why)
                          for name, why in sorted((read.get("checked") or {}).items())) or read.get("unread"),
                read["cost"]["usd"]))
        return read
    except BudgetExceededError as exc:
        raise
        from apps.pipeline.services.cost_ledger import spend_held
        why = ("this design's spending is held at $0 (about $0.30 to draw and read it)" if spend_held(exc)
               else "this design's spending cap is reached")
        aria.log("ARIA: the carton's layout picture was not made — %s; its back, sides and flaps continue its front" % why,
                 level="warning")
    except Exception as exc:  # noqa: BLE001 — never a refusal: the panels continue the front, said
        if isinstance(exc, _RescueBudgetError):
            raise
        why = "the picture service could not make it just now"
        aria.log("ARIA: the carton's layout picture could not be made just now — its back, sides and flaps continue "
                 "its front", level="warning", payload={"error": "%s: %s" % (type(exc).__name__, str(exc)[:300])})
    if said is not None:              # [his goal of 2026-10-13, (1)] for the caller to say beside Approve
        said.append(why)
    return None


#: the panels a layout picture may draw on the carton: the back and its two sides (the front is always the concept's;
#: a flap is drawn as before — the read is kept for it)
DRAWN_PANELS = ("back", "side_left", "side_right")
#: a band or edge-to-edge shape a panel's picture prints in the ink of one the front draws (within this ΔE) is the
#: front's own, continued: drawn as the front draws it, never traced again from the layout picture's smaller panel —
#: measured on Garden Wrap's: its scallops, 115 x 410 px a side at the map's scale, traced ragged
SAME_PART_DE = 15.0
#: what a panel drawn from the layout picture says, and what one that continues the front says before why
FROM_LAYOUT = "the layout picture"
CONTINUES = "continues the front: %s"


def panel_fronts(task, image, sources: list, front_shapes: dict | None = None, dims=None) -> dict:
    """``{panel: its map front}`` — each panel of DRAWN_PANELS the kept layout read checked clean, as a front is drawn
    from its map: its shapes traced from the layout picture (``concept_design_map.trace_shapes``); its type in words a
    source on record gives — never the picture's own lettering (his rule 1) — and on the back none (the sticker carries
    its information); its line art never traced from the picture (his finding on 122's drawing, A1) but said, so the
    front's own field continues there; a band the front draws (``front_shapes``, SAME_PART_DE) continued as the front
    draws it, never traced again; laid out at its own proportions in the picture (``face_aspect``). A panel the read did
    not give, or its check refused, is ``{"continues": why}``; ``{}`` where no layout read is kept."""
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import flat_motif as fm
    held = front_shapes if isinstance(front_shapes, dict) else {}
    front_inks = [sh["ink"] for sh in held.get("shapes") or [] if sh.get("ink") and sh.get("edges")] + [
        b["fill"] for b in held.get("bands") or [] if b.get("fill")]

    def the_fronts(part, ink):
        return bool(ink) and any(fm.delta_e(ink, mine) <= SAME_PART_DE for mine in front_inks) and (
            bool(part.get("edges")) or float(part["box"][3]) > 0.85)
    read = kept_layout_read(image, dims) if image is not None else None
    if read is None:
        return {}
    picture = layout_bytes(kept_layout(image, dims))
    out = {}
    for name in DRAWN_PANELS:
        why = (read.get("checked") or {}).get(name, "the layout picture's read did not find it")
        rec = (read.get("panels") or {}).get(name)
        if why is not None or not isinstance(rec, dict):
            out[name] = {"continues": why if why else "the layout picture's read did not find it"}
            continue
        shapes = dm.trace_shapes(picture, rec, sources=sources)
        if shapes.get("state") != dm.SHAPES_TRACED:
            out[name] = {"continues": "its parts could not be traced from the layout picture"}
            continue
        typed = [] if name == "back" else [
            t for t in dm.type_sources(shapes.get("types") or [], sources)
            if t.get("words") and t.get("source") not in (dm.PICTURE_ENGLISH, dm.PICTURE_ARABIC)]
        line_art = bool(shapes.get("lines")) or any(p.get("kind") == "motif" for p in rec.get("parts") or [])
        own = [sh for sh in shapes.get("shapes") or [] if not the_fronts(sh, sh.get("ink"))]
        bands = [b for b in shapes.get("bands") or [] if not the_fronts(b, b.get("fill"))]
        carried = len(own) < len(shapes.get("shapes") or []) or len(bands) < len(shapes.get("bands") or [])
        fb = rec["face_box_px"]
        out[name] = {"shapes": dict(shapes, types=typed, lines=[], scatters=[], shapes=own, bands=bands),
                     "line_art": line_art, "bands_from_front": carried,
                     "face_aspect": (fb[2] - fb[0]) / max(fb[3] - fb[1], 1), "edge_part": None,
                     "drawn_from": FROM_LAYOUT}
    return out
