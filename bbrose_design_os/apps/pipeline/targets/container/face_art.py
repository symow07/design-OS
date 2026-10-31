"""[His goal for the pitch, 2026-10-15 (OWNER_BLOCKER_CLEARANCE.md), A (4): "DEPTH AND DETAIL: layered backgrounds,
textures, several colours, gradients, rich illustration and things happening behind the hero, all still clean vector
and faithful to the concept"; B (7): "Colours from the flat redraw, never from shadows"; B (9): "Shapes from the
concept"] THE FACE'S ART — a product drawn standing (a bottle, a jar, a lipstick, a tube) drawn from its concept's
printed face as its lid's art is drawn on a palette (``lid_art``): the product cut from its concept picture exactly as
its map reads it (``concept_outline.standing_pixels``, the map's ``product_box_px``), redrawn ONCE as flat artwork — the
same layout, colours and gradients, the light and the curve taken off, the ground left plain where words and the mark
print — a paid picture kept on the concept (``FACE_ART_KEY``); then traced in colour at $0 (``lid_art.trace_art``: its
ground a smooth field, its shapes in their colours, its geometric lines drawn), checked where the concept draws (its
type's ground left plain, ``lid_art.registration``), and drawn over the whole product clipped to its traced outline,
the map's lines of type and its mark set over it, live.

What it replaces, where it stands: the map's fields, bands, motifs, frames and rules (each read off the photo, a band's
colour its box's median — 127's drip band read yellow), never its type or its mark. Where the art is not made, not
traced or does not stand where the concept does, the drawing is the map's as before, and that is said beside Approve —
never silently."""
from __future__ import annotations
from apps.pipeline.services.cost_ledger import BudgetExceededError as _RescueBudgetError
from apps.pipeline.services.spend_reservation import paid_operation

import hashlib

FACE_ART_KEY = "container_face_art/1.0"
FACE_ART_PROMPT_VERSION = "face-art-4"           # face-art-3: every face is its body, below its closure
# face-art-4: [his goal after the pitch page, 2026-10-15, A (4): "COMPLETENESS: every element in the concept is drawn
# (... 127's drip highlights)."] a glossy element the print itself pictures keeps its highlights and its shade as flat
# shapes in its own colours, as an illustrator draws it — 127's redraw painted its drips' highlights in the drips' own
# yellow, so its trace could not keep them
FACE_ART_OPERATION = "image:face art:%s"
FACE_ART_WORDS = "Redraw ONLY the printed design of this"
FACE_ART_PROMPT = (
    FACE_ART_WORDS + " {product}, straight-on, as flat artwork for print: its front exactly as pictured — every coloured "
    "area, band, drip, pattern, texture, illustration and line in the same place, at the same size and in the same "
    "colours, with the same smooth gradients where it shows them — with the photograph's lighting, shading, shine, "
    "reflections and the curve of the product taken off, as if its print were scanned flat. Where the print itself "
    "pictures a glossy or rounded element (a drip, a droplet, a ribbon, a gem), keep it reading as that element the way "
    "an illustrator draws it flat: its highlights as crisp lighter shapes and its shade as a darker shape, in the "
    "element's own colours, exactly where the concept shows them. This picture is the product "
    "already filling the frame edge to edge, the frame {shape}: keep its outline and its layout exactly as they are — "
    "nothing moved, enlarged, added or carried into empty ground. Where words, numbers or the logo are printed, leave "
    "only the plain ground behind them, as plain as the ground around them: no text, no letters, no numbers, no logo. "
    "Clean vector-style artwork with crisp edges; no photo texture, no shadow, no backdrop.")
REDRAWN, REFUSED = "REDRAWN", "REFUSED"
FACE_ART_NOT_MADE = "CONTAINER_FACE_ART_NOT_MADE"
FACE_ART_NOT_DRAWN = "CONTAINER_FACE_ART_NOT_DRAWN"
#: what he can do about a face drawn from its map alone
FACE_ART_OPTIONS = ("ask for changes to have the face redrawn (about $0.25)", "choose another concept at Gate 1")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def face_top(spec: dict) -> float:
    """Where the printed face begins, a share of the product's height from its top: below its closure, as the concept's
    map finds it — the closure (a cap, a lid, a dropper) drawn by the engine in its own lit colour with its mark set on
    it; a redraw asked for the whole product redraws its label alone (128's dropper, 130's gold lid, each left blank).
    0 where the map names no closure."""
    from apps.pipeline.services import concept_design_map as dm
    closures = [p for p in (spec.get(dm.SCHEMA) or {}).get("parts") or []
                if p.get("kind") == "closure" and p.get("box")]
    top = [p for p in closures if (float(p["box"][1]) + float(p["box"][3])) / 2.0 <= 0.5]
    if not top:
        return float(0)
    return max(0.0, min(0.6, max(float(p["box"][3]) for p in top)))


def face_foot(spec: dict) -> float:
    """[His goal after the pitch page, B (10): the lotion tube, 139, stood on its cap — its face cut BELOW its cap, the
    cream band and the cap alone, its honey dipper, oats and drips never drawn] where the printed face ends, a share of
    the product's height from its top: above a closure the concept stands it on, as its map finds it; 1 where its
    closures are at its top, or it names none."""
    from apps.pipeline.services import concept_design_map as dm
    foot = [p for p in (spec.get(dm.SCHEMA) or {}).get("parts") or []
            if p.get("kind") == "closure" and p.get("box") and (float(p["box"][1]) + float(p["box"][3])) / 2.0 > 0.5]
    if not foot:
        return float(1)
    edge = min(float(p["box"][1]) for p in foot)
    # [his last goal before the pitch, Step 2, 139] a band of the cap's colour the body prints across its edge is the
    # face's: the face runs to the band's far side, where the drawn cap begins (``closure_edge``)
    cap = next(p for p in foot if float(p["box"][1]) == edge)
    for band in (spec.get(dm.SCHEMA) or {}).get("parts") or []:
        if (band.get("kind") == "band" and band.get("box") and band.get("colour") and cap.get("colour")
                and float(band["box"][1]) < edge < float(band["box"][3])
                and _hex_lab_distance(band["colour"], cap["colour"]) < dm.SHAPE_PARAMS["closure_de"]):
            edge = float(band["box"][3])
    return min(1.0, max(0.4, edge))


def _hex_lab_distance(a: str, b: str) -> float:
    """CIE76 between two hex colours."""
    from apps.ire.legibility import colour_distance
    return colour_distance(a, b)


def face_picture(pic: bytes, spec: dict) -> dict | None:
    """The product's printed face cut from its concept picture in the frame its map reads (``standing_pixels`` at its
    read scale, the map's ``product_box_px``), from ``face_top`` down: ``{"png", "box_px", "size", "top"}`` — None
    where the picture does not stand or the map gives no box."""
    import cv2

    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import concept_outline as co
    box = (spec.get(dm.SCHEMA) or {}).get("product_box_px")
    stood = co.standing_pixels(pic) if pic else None
    if not box or stood is None:
        return None
    img = stood[0]
    h, w = img.shape[:2]
    x0, y0, x1, y1 = (int(round(float(v))) for v in box)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    top, foot = face_top(spec), face_foot(spec)
    y0, y1 = int(round(y0 + top * (y1 - y0))), int(round(y0 + foot * (y1 - y0)))
    if x1 - x0 < 16 or y1 - y0 < 16:
        return None
    ok, buf = cv2.imencode(".png", img[y0:y1, x0:x1])
    return {"png": buf.tobytes(), "box_px": [x0, y0, x1, y1], "size": [x1 - x0, y1 - y0],
            "top": round(top, 4), "foot": round(foot, 4)} if ok else None


def kept_face_art(image, spec: dict | None = None) -> dict | None:
    """The face's flat redraw kept on the concept, made from THIS picture under THIS prompt (a face-art-1 redraw, of the
    whole product, still stands for a product whose face is the whole product); else None."""
    from . import lid_art as _la
    prov = image.reference_provenance if isinstance(image.reference_provenance, dict) else {}
    record = prov.get(FACE_ART_KEY)
    if not isinstance(record, dict):
        return None
    # a redraw of the face as it is cut now stands, whichever prompt made it: the body below the closure (face-art-2,
    # where its closure was a dropper's, cut so), or the whole product where no closure is named (face-art-1)
    kept = record.get("prompt_version") == FACE_ART_PROMPT_VERSION
    if spec is not None and (kept or record.get("prompt_version") in ("face-art-1", "face-art-2")):
        # [his goal after the pitch page, B (10)] a redraw of a face cut otherwise than it is cut now (139's, cut below
        # the cap its tube stands on) is never this face's
        from . import _concept_bytes
        now = face_picture(_concept_bytes(image), spec)
        kept = now is not None and list(record.get("box_px") or []) == list(now["box_px"])
    if not kept:
        return None
    if record.get("concept_sha256") != _la._concept_sha(image):
        return None
    return record


def make_face_art(aria, image, face: dict, product_words: str) -> dict:
    """The face redrawn once as flat artwork — a paid picture on the ledger as "image:face art:<direction>", its file and
    what it cost kept on the concept (``FACE_ART_KEY``). Fidelity is paid for: never held at $0 (his B (6))."""
    import base64
    import time

    import openai
    from django.conf import settings
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from django.utils import timezone

    from apps.pipeline.models import ApiCallRecord
    from apps.pipeline.services import cost_ledger
    from apps.pipeline.services.cost_ledger import before_paid_call, provider_request_id, record_image

    from . import lid_art as _la
    if cost_ledger.daily_budget_exceeded():
        raise cost_ledger.BudgetExceededError("the day's spending cap is reached")
    cost_ledger.check_task_budget(aria.task)
    size, shape = _la.size_for(face["size"][0], face["size"][1], False)
    prompt = FACE_ART_PROMPT.format(product=product_words, shape=shape)
    sent = _la.framed(face["png"], size)
    started = time.monotonic()
    before_paid_call("a picture", fidelity=True)
    response = paid_operation(openai.images.edit, provider='openai', operation='face_art', model=settings.IMAGE_MODEL, image=[("face.png", sent, "image/png")], prompt=prompt,
                                  size=size, quality=settings.IMAGE_QUALITY_CONCEPTS, n=1, timeout=180)
    operation = FACE_ART_OPERATION % image.direction_name
    try:
        record_image(settings.IMAGE_MODEL, operation=operation, image_count=1, task=aria.task,
                     metadata={"provider_request_id": provider_request_id(response),
                               "latency_ms": int((time.monotonic() - started) * 1000), "concept_image_id": image.pk})
    except cost_ledger.BudgetExceededError:
        raise
        aria.log("ARIA: the face's flat redraw reached this design's spending cap — it is kept, it is paid for",
                 level="warning")
    row = ApiCallRecord.objects.filter(task=aria.task, operation=operation).order_by("-pk").first()
    art = base64.b64decode(response.data[0].b64_json)
    name = default_storage.save("concepts/task_%d_face_art_%d.png" % (aria.task.pk, image.pk), ContentFile(art))
    record = {"state": REDRAWN, "file": name, "sha256": _sha(art), "size": size, "prompt_version": FACE_ART_PROMPT_VERSION,
              "prompt": prompt, "face_sha256": _sha(face["png"]), "box_px": face["box_px"], "top": face["top"],
              "foot": face["foot"],
              "concept_sha256": _la._concept_sha(image), "model": settings.IMAGE_MODEL,
              "cost_usd": str(row.cost_usd) if row is not None else "0", "at": timezone.now().isoformat(),
              "why": "his goal for the pitch, A (4) and B (7): the face redrawn flat, then traced in colour"}
    prov = dict(image.reference_provenance or {})
    prov[FACE_ART_KEY] = record
    image.reference_provenance = prov
    image.save(update_fields=["reference_provenance"])
    aria.log("ARIA: the product's printed face redrawn flat for tracing — never printed — $%s" % record["cost_usd"])
    return record


def face_art_bytes(record: dict) -> bytes:
    from django.core.files.storage import default_storage
    with default_storage.open(record["file"], "rb") as fh:
        return fh.read()


def ensure_face_art(aria, output, archetype: str) -> dict:
    """The face's flat redraw for the approved concept — kept (nothing paid), else made now; ``{"state": REFUSED,
    "why"}`` where it could not be, said beside Approve and the face drawn from its map — never silently."""
    from apps.pipeline.services import cost_ledger

    from . import _concept_bytes, brief_text, product_in_form
    image = output.approved_image
    kept = kept_face_art(image, output.spec_sheet or {})
    if kept is not None:
        aria.log("ARIA: the product's flat face redraw is on record for this concept — kept, nothing spent")
        return kept
    face = face_picture(_concept_bytes(image), output.spec_sheet or {})
    if face is None:
        return {"state": REFUSED, "why": "the product could not be cut from its concept picture where its map reads it"}
    words = product_in_form(archetype, brief_text(aria.task)) or str(archetype).replace("_", " ")
    try:
        return make_face_art(aria, image, face, words)
    except cost_ledger.BudgetExceededError as exc:
        raise
        return {"state": REFUSED, "why": "the spending cap: %s" % exc}
    except Exception as exc:  # noqa: BLE001 — said by name beside Approve; the face drawn from its map
        if isinstance(exc, _RescueBudgetError):
            raise
        return {"state": REFUSED, "why": "the picture service could not make it just now (%s: %s)"
                                        % (type(exc).__name__, str(exc)[:160])}


#: a pixel of a line's padded box farther than this (CIE76) from the ground round the box is its lettering, painted out
WORDS_PAINT_DE = 12.0


def words_painted_out(png: bytes, boxes: list) -> bytes:
    """``png`` with the lettering inside each box (shares of its frame, padded by ``lid_art.WORDS_PAD`` of its height) —
    its pixels standing WORDS_PAINT_DE from the median of a ring round the box — painted out from what surrounds it."""
    import cv2
    import numpy as np

    from . import lid_art as _la
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return png
    hgt, wid = img.shape[:2]
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[..., 0] *= 100.0 / 255.0
    lab[..., 1:] -= 128.0
    mask = np.zeros((hgt, wid), np.uint8)
    for b in boxes:
        x0, y0, x1, y1 = (float(v) for v in b)
        pad = _la.WORDS_PAD * (y1 - y0)
        X0, Y0 = max(0, int((x0 - pad) * wid)), max(0, int((y0 - pad) * hgt))
        X1, Y1 = min(wid, int((x1 + pad) * wid) + 1), min(hgt, int((y1 + pad) * hgt) + 1)
        if X1 - X0 < 4 or Y1 - Y0 < 4:
            continue
        ring = np.ones((Y1 - Y0, X1 - X0), bool)
        ring[2:-2, 2:-2] = False
        ground = np.median(lab[Y0:Y1, X0:X1][ring], axis=0)
        far = np.sqrt(((lab[Y0:Y1, X0:X1] - ground) ** 2).sum(-1)) > WORDS_PAINT_DE
        mask[Y0:Y1, X0:X1][far] = 255
    if not mask.any():
        return png
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8))
    ok, buf = cv2.imencode(".png", cv2.inpaint(img, mask, 5, cv2.INPAINT_TELEA))
    return buf.tobytes() if ok else png


def _inks_of(read, traced):
    """A line's inks, as ``lid_art.without_words`` reads them: the read's and the traced letters', where they differ."""
    inks = [hx for hx in (read, traced) if hx]
    if not inks:
        return None
    return inks


def traced_face(image, spec: dict) -> dict | None:
    """The kept face redraw traced in colour (``lid_art.trace_art``) and checked against the map — its type and mark on
    the ground the concept prints them on (``lid_art.registration``) — ``trace`` with its registration, or
    ``{"state": REFUSED, "why"}``; None where no redraw is kept."""
    from apps.pipeline.services import concept_design_map as dm

    from . import _concept_bytes
    from . import lid_art as _la
    kept = kept_face_art(image, spec) if image is not None else None
    if kept is None:
        return None
    art = face_art_bytes(kept)
    face = face_picture(_concept_bytes(image), spec)
    aligned = aligned_to(art, face["png"]) if face is not None else None
    if aligned is not None:
        art = aligned["png"]
    paper = None
    if face is not None:
        # [His review of 127, 130, 131 and 132, 2026-10-15, C (3), D (11)] the redraw's own paper never drawn as the face
        art, paper = without_paper(art, face["png"], backdrop_of(_concept_bytes(image)))
    top = face["top"] if face is not None else face_top(spec)
    foot = face["foot"] if face is not None else face_foot(spec)
    # the map's type and mark, in the face's own frame (from its top to its foot)
    parts = []
    for p in (spec.get(dm.SCHEMA) or {}).get("parts") or []:
        if p.get("kind") in ("type", "mark") and p.get("box") and float(p["box"][3]) > top and float(p["box"][1]) < foot:
            x0, y0, x1, y1 = (float(v) for v in p["box"])
            parts.append(dict(p, box=[x0, (max(y0, top) - top) / (foot - top), x1, (min(y1, foot) - top) / (foot - top)]))
    traced = trace_face(art)
    if traced.get("state") != _la.TRACED:
        return {"state": REFUSED, "why": "its flat redraw could not be traced in colour — %s" % traced.get("why")}
    if not traced.get("flat") and parts:
        # [his last goal before the pitch, Step 2, 139: "no duplicate or ghost text" — its graded face's smooth ground
        # sampled the redraw's own lettering, a soft ghost of its name under the live one] a graded face's ground fitted
        # on the redraw with its lettering painted out; its regions traced from the redraw as it is
        clean = trace_face(words_painted_out(art, [p["box"] for p in parts]))
        if clean.get("state") == _la.TRACED and clean.get("sky"):
            traced = dict(traced, sky=clean["sky"])
    # [his review of 127-132, C (4)] the redraw's own lettering, where it kept the photo's, never printed under the live
    # words
    # each line's inks: the map's read and the traced letters' own (``trace_type`` reads them again where the read is
    # not theirs)
    lines = {t.get("part"): t.get("ink") for t in (spec.get(dm.SHAPES_SCHEMA) or {}).get("types") or []}
    traced = _la.without_words(traced, [p["box"] for p in parts],
                               [_inks_of(p.get("colour"), lines.get(p.get("name"))) for p in parts])
    if face is not None:
        traced = without_side(traced)
    if face is not None:
        held = registration(art, face["png"], parts)
        if held["state"] != "REGISTERED":
            return {"state": REFUSED, "why": "its flat redraw does not stand where the concept does — %s" % held["why"]}
        traced = dict(traced, registration=held)
    # [his review of 127-132, C (5)] the print's own grain, where the map reads one, over the face's art
    if face is not None:
        from . import _grain_of
        traced = dict(traced, **_grain_of(face["png"], spec, top, foot))
    return dict(traced, top=top, foot=foot, face_art={"file": kept["file"], "cost_usd": kept["cost_usd"]},
                aligned=({k: v for k, v in aligned.items() if k != "png"} if aligned is not None else None),
                paper=paper)


#: [His review of 127, 130, 131 and 132, 2026-10-15, C (3): "parts meet as the concept shows (127 has a gap between the
#: cap and the body)"; D (11): 128's "white fade at the body's bottom corners"] a redraw asked for the face edge to edge
#: may still draw it as a card — its corners rounded, a rim round it, white paper outside (127's, 128's). That paper is
#: never the face: the solid near-white (L* over ``white_l``, chroma under ``white_chroma``; no line thinner than
#: ``solid_share`` of its long side) the redraw holds joined to its own edge within ``band_share`` of its short side
#: of its top or its foot,
#: where the concept's face at the same place is plainly not white (its chroma over ``concept_chroma`` — the glass's
#: colour, a cap's — or its backdrop beside the product, within ``backdrop_l`` L*) — so a face whose ground IS white
#: (130's label, shaded or not) keeps it — and a product whose own ground at its top and foot is white (``own_white`` of
#: it, 130's jar) keeps all of its white — and a fine white line (128's mesh) is never paper — taken with the redraw's
#: rim beside it (``rim_share`` of its long side) and round its very edge (``edge_share``), and filled from the art
#: nearest it, so the face runs out to the product's own outline as the concept's does. The executor's, new.
FACE_PAPER = {"version": 1, "white_l": 90.0, "white_chroma": 8.0, "solid_share": 0.004, "band_share": 0.12,
              "backdrop_l": 12.0, "concept_chroma": 15.0, "rim_share": 0.025, "edge_share": 0.008, "own_white": 0.5}


#: [His fixes to 142 (Cherry Kiss), 2026-10-17, (4): "No stray dark stripes."] a redraw may draw the product's own side
#: beside its face (142's: a solid dark band down its left edge, 10% of its width — the concept photo's shading of the
#: box's side, which a flat print never carries). That side is never the face's print: a region joined to the face's left
#: or right edge down ``rows`` of its height, no wider than ``share`` of it, solid (``solid`` of its box), a shade of the
#: face's ground — its hue within ``hue_deg`` of the ground's, darker by ``darker_l`` L* — printed in the ground; a band
#: of another colour is the face's own and kept. The executor's, new.
FACE_SIDE = {"version": 1, "rows": 0.97, "share": 0.15, "solid": 0.9, "darker_l": 8.0, "hue_deg": 15.0}


def without_side(trace: dict) -> dict:
    """``trace`` with the product's own side its redraw drew (``FACE_SIDE``) printed in its ground, and ``side`` saying
    what was taken — or ``trace`` as it was, where it holds none."""
    import math

    import numpy as np

    from apps.pipeline.services.concept_design_map import _hex_lab as hex_to_lab

    from . import lid_art as _la
    regions = trace.get("regions") or []
    if len(regions) < 2:
        return trace
    p = FACE_SIDE
    areas = [_la._rings_area(r["rings"]) for r in regions]
    ground = regions[int(np.argmax(areas))]
    gl, ga, gb = hex_to_lab(ground["fill"])
    taken, out = [], []
    for r, area in zip(regions, areas):
        x0, y0, x1, y1 = _la._ring_box(r["rings"])
        side = (r is not ground and y1 - y0 >= p["rows"] and x1 - x0 <= p["share"] and (x0 <= 0.0 or x1 >= 1.0)
                and area >= p["solid"] * (x1 - x0) * (y1 - y0))
        if side:
            rl, ra, rb = hex_to_lab(r["fill"])
            turn = abs((math.degrees(math.atan2(rb, ra) - math.atan2(gb, ga)) + 180.0) % 360.0 - 180.0)
            side = rl < gl - p["darker_l"] and turn <= p["hue_deg"]
        if side:
            taken.append({"fill": r["fill"], "box": [round(v, 4) for v in (x0, y0, x1, y1)]})
            r = dict(r, fill=ground["fill"])
        out.append(r)
    if not taken:
        return trace
    return dict(trace, regions=out, side={"taken": taken, "ground": ground["fill"], "params": dict(p)})


def backdrop_of(pic: bytes | None):
    """The concept photo's backdrop, ``(L*, chroma)``: the median of its frame's edge — None where it cannot be read."""
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(pic, np.uint8), cv2.IMREAD_COLOR) if pic else None
    if img is None:
        return None
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    edge = np.median(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]), axis=0)
    return float(edge[0]) * 100.0 / 255.0, float(np.hypot(edge[1] - 128.0, edge[2] - 128.0))


def without_paper(art_png: bytes, face_png: bytes, backdrop=None) -> tuple:
    """``(the redraw's png, what was taken)`` — the redraw with its paper (``FACE_PAPER``) filled from the art nearest it,
    and ``{"share", "params"}`` — or the redraw as it was, and None, where it holds none. ``backdrop`` the concept photo's
    (``backdrop_of``): where the concept face shows it, the product is not there."""
    import cv2
    import numpy as np
    art = cv2.imdecode(np.frombuffer(art_png, np.uint8), cv2.IMREAD_COLOR)
    face = cv2.imdecode(np.frombuffer(face_png, np.uint8), cv2.IMREAD_COLOR)
    if art is None or face is None:
        return art_png, None
    h, w = art.shape[:2]
    face = cv2.resize(face, (w, h), interpolation=cv2.INTER_AREA)
    p = FACE_PAPER

    def lab_of(img):
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        return lab[..., 0] * 100.0 / 255.0, np.hypot(lab[..., 1] - 128.0, lab[..., 2] - 128.0)
    art_l, art_c = lab_of(art)
    face_l, face_c = lab_of(face)

    def disc(share, side):
        r = max(1, int(round(share * side)))
        return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    band = np.zeros((h, w), np.uint8)
    b = max(1, int(round(p["band_share"] * min(h, w))))
    band[:b, :] = band[-b:, :] = 1                      # its top and its foot, corners and all — never its sides,
                                                        # where a face's own art may run out to its edge
    white = ((art_l > p["white_l"]) & (art_c < p["white_chroma"])).astype(np.uint8)
    white = cv2.morphologyEx(white, cv2.MORPH_OPEN, disc(p["solid_share"], max(h, w))) & band
    n, labels = cv2.connectedComponents(white, connectivity=4)
    edge = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])).tolist()) - {0}
    if not edge:
        return art_png, None
    # the concept plainly not white there: its own colour, or its backdrop beside the product — never a white product's
    # own shading (130's jar falls to L* 50 at its sides)
    not_white = face_c > p["concept_chroma"]
    backdrop_here = np.zeros((h, w), bool)
    if backdrop is not None:
        backdrop_here = (np.abs(face_l - backdrop[0]) < p["backdrop_l"]) & (face_c < p["concept_chroma"])
        not_white |= backdrop_here
    # a product whose own ground is white (130's jar, round its label): its redraw's white at its top and its foot is
    # the product's own, never paper — read where the concept shows the product there, not its backdrop
    own = (band > 0) & ~backdrop_here
    if own.any() and float(((art_l > p["white_l"]) & (art_c < p["white_chroma"]))[own].mean()) >= p["own_white"]:
        return art_png, None
    paper = np.isin(labels, sorted(edge)) & not_white
    if not paper.any():
        return art_png, None
    taken = (cv2.dilate(paper.astype(np.uint8), disc(p["rim_share"], max(h, w))) > 0) & not_white
    # the rim a card is drawn with runs round its very edge (127's, a thin tan line under its cap): that edge is the art
    # beside it, carried out
    rim = max(1, int(round(p["edge_share"] * max(h, w))))
    taken[:rim, :] = taken[-rim:, :] = taken[:, :rim] = taken[:, -rim:] = True
    if taken.all():
        return art_png, None
    # each pixel taken: the colour of the art nearest it that is not
    _d, nearest = cv2.distanceTransformWithLabels(taken.astype(np.uint8), cv2.DIST_L2, 5,
                                                  labelType=cv2.DIST_LABEL_PIXEL)
    ys, xs = np.nonzero(~taken)
    lut = np.zeros((int(nearest.max()) + 1, 3), np.uint8)
    lut[nearest[ys, xs]] = art[ys, xs]
    out = art.copy()
    out[taken] = lut[nearest[taken]]
    ok, buf = cv2.imencode(".png", out)
    if not ok:
        return art_png, None
    return buf.tobytes(), {"share": round(float(taken.mean()), 4), "params": dict(p)}


#: [his goal for the pitch, A (4)] a face redraw is FLAT where few of its pixels change softly (``is_flat``) — drawn region
#: by region, crisp, its fine dots kept (``speckle_px`` at 1536 px); else it carries real gradients, and its ground is
#: drawn as the lid's sky is, one smooth mesh (``lid_art.trace_art``) — [his goal of 2026-10-13, (9)] never in bands
FACE_TRACE = {"version": 2, "soft_step": (0.1, 1.5), "soft_share": 0.35, "speckle_px": 2}


def is_flat(img) -> bool:
    """Whether a redraw is flat colour, never a smooth gradient: the share of its pixels whose colour changes a little
    from one pixel to the next (``soft_step`` CIEDE76 a pixel, read on the picture at half size, softened) stays under
    ``soft_share`` — flat fills change nowhere, a smooth gradient everywhere. MEASURED: 127's flat face 0.19, 128's
    aqua-to-lilac face 0.52, 124's lid 0.58."""
    import cv2
    import numpy as np
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    small = cv2.resize(lab, (max(32, img.shape[1] // 2), max(32, img.shape[0] // 2)), interpolation=cv2.INTER_AREA)
    soft = cv2.GaussianBlur(small, (0, 0), 2)
    gx = cv2.Sobel(soft, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(soft, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    step = np.sqrt((gx ** 2 + gy ** 2).sum(-1))
    lo, hi = FACE_TRACE["soft_step"]
    return float(((step > lo) & (step < hi)).mean()) < FACE_TRACE["soft_share"]


def trace_face(png: bytes) -> dict:
    """The face redraw traced: a flat one region by region in its colours, ground and all, crisp, its fine dots kept;
    one with gradients by the lid's own tracer (``lid_art.trace_art``) — its ground a smooth mesh."""
    import re

    import cv2
    import numpy as np
    import vtracer

    from . import lid_art as _la
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR) if png else None
    if img is None:
        return {"state": _la.REFUSED, "why": "the redraw could not be opened"}
    if not is_flat(img):
        return dict(_la.trace_art(png, False), face_trace="gradients — its ground a smooth mesh")
    h, w = img.shape[:2]
    T = _la.TRACE
    svg = vtracer.convert_raw_image_to_svg(png, img_format="png", colormode="color", hierarchical="cutout",
                                            mode="spline",
                                            filter_speckle=max(2, int(round(FACE_TRACE["speckle_px"] * max(w, h)
                                                                            / 1536.0))),
                                            color_precision=T["colour_precision"],
                                            layer_difference=T["layer_difference"],
                                            corner_threshold=T["corner_threshold"],
                                            length_threshold=T["length_threshold"],
                                            splice_threshold=T["splice_threshold"], path_precision=T["path_precision"])
    regions = []
    for d, fill, tx, ty in re.findall(
            r'<path d="([^"]+)" fill="(#[0-9A-Fa-f]{6})"(?: transform="translate\(([-\d.]+),([-\d.]+)\)")?', svg):
        rings = _la._rings(d, float(tx) if tx else float(0), float(ty) if ty else float(0), w, h)
        if rings:
            regions.append({"fill": fill.upper(), "rings": rings})
    if not regions:
        return {"state": _la.REFUSED, "why": "its colour trace holds no region"}
    return {"schema_version": _la.LID_ART_TRACE_KEY, "state": _la.TRACED, "size_px": [int(w), int(h)], "round": False,
            "sky": {"rows": []}, "regions": regions, "flat": True, "face_trace": "flat — every region crisp",
            "measured": {"regions": len(regions)}, "params": dict(FACE_TRACE)}


#: [his goal for the pitch, A (4)] a face's type stands on what lies under it: plain where ``plain_share`` of the box is
#: within ``plain_de`` (CIEDE76) of its own main colour — a panel or a ground, never a picture grown under the words; the
#: redraw's box may be ``busier_by`` busier than the concept's (the photo's light makes its own ground uneven)
FACE_REGISTER = {"version": 1, "plain_de": 12.0, "busier_by": 0.3, "busy_floor": 0.4}


def _busy(img, box) -> float:
    """How busy a box of a picture is: the share of its pixels farther than ``plain_de`` from its own main colour."""
    import numpy as np

    from . import lid_art as _la
    h, w = img.shape[:2]
    x0, y0, x1, y1 = (min(max(float(v), 0.0), 1.0) for v in box)
    cut = img[int(y0 * h):max(int(y0 * h) + 1, int(y1 * h)), int(x0 * w):max(int(x0 * w) + 1, int(x1 * w))]
    lab = _la._lab(cut).reshape(-1, 3)
    main = np.median(lab, 0)
    return float((np.sqrt(((lab - main) ** 2).sum(-1)) > FACE_REGISTER["plain_de"]).mean())


def registration(art_png: bytes, face_png: bytes, parts: list) -> dict:
    """The face's redraw checked where its concept prints type and the mark: each on a ground or a panel as plain as
    the concept's (``FACE_REGISTER``) — never a picture grown under the words. ``{"state", "boxes", "why"}``."""
    import cv2
    import numpy as np
    art = cv2.imdecode(np.frombuffer(art_png, np.uint8), cv2.IMREAD_COLOR)
    face = cv2.imdecode(np.frombuffer(face_png, np.uint8), cv2.IMREAD_COLOR)
    face = cv2.resize(face, (art.shape[1], art.shape[0]), interpolation=cv2.INTER_AREA)
    boxes, off = {}, []
    for p in parts:
        a, c = _busy(art, p["box"]), _busy(face, p["box"])
        boxes[p["name"]] = {"kind": p["kind"], "art": round(a, 3), "concept": round(c, 3)}
        if a > FACE_REGISTER["busy_floor"] and a > c + FACE_REGISTER["busier_by"]:
            off.append("%s %r — the redraw draws a picture under it (%d %% of its box busy, the concept %d %%)"
                       % (p["kind"], p["name"], round(100 * a), round(100 * c)))
    return {"state": "REFUSED" if off else "REGISTERED", "boxes": boxes, "params": dict(FACE_REGISTER),
            "why": "; ".join(off)}


#: [his goal for the pitch, A (4)] a redraw keeps the concept's scene but not always its exact places (130's oval drawn
#: higher and shorter): it is laid on the concept's face by the affine that best matches the two (ECC on their softened
#: grey), kept only where that match is better than none by ``gain`` and moves nothing past ``most_shift`` of the frame
ALIGN = {"version": 1, "side": 384, "blur": 3, "iterations": 200, "gain": 0.02, "most_shift": 0.15, "most_scale": 0.25}


def aligned_to(art_png: bytes, face_png: bytes) -> dict | None:
    """The redraw warped onto the concept's face — ``{"png", "matrix", "match_before", "match_after"}`` — or None where
    no better fit is found."""
    import cv2
    import numpy as np
    art = cv2.imdecode(np.frombuffer(art_png, np.uint8), cv2.IMREAD_COLOR)
    face = cv2.imdecode(np.frombuffer(face_png, np.uint8), cv2.IMREAD_COLOR)
    if art is None or face is None:
        return None
    h, w = art.shape[:2]
    k = ALIGN["side"] / float(max(h, w))
    sw, sh = max(16, int(w * k)), max(16, int(h * k))

    def grey(img):
        g = cv2.cvtColor(cv2.resize(img, (sw, sh), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
        return cv2.GaussianBlur(g, (0, 0), ALIGN["blur"])
    a, f = grey(art), grey(face)
    warp = np.eye(2, 3, dtype=np.float32)
    try:
        before = float(cv2.computeECC(f, a))
        after, warp = cv2.findTransformECC(f, a, warp, cv2.MOTION_AFFINE,
                                           (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, ALIGN["iterations"], 1e-5),
                                           None, 5)
    except cv2.error:
        return None
    sx, sy = float(np.hypot(warp[0, 0], warp[1, 0])), float(np.hypot(warp[0, 1], warp[1, 1]))
    shift = max(abs(float(warp[0, 2])) / sw, abs(float(warp[1, 2])) / sh)
    if (after < before + ALIGN["gain"] or shift > ALIGN["most_shift"]
            or max(abs(sx - 1.0), abs(sy - 1.0)) > ALIGN["most_scale"]):
        return None
    full = warp.copy()
    full[:, 2] /= k
    out = cv2.warpAffine(art, full, (w, h), flags=cv2.INTER_CUBIC + cv2.WARP_INVERSE_MAP,
                         borderMode=cv2.BORDER_REPLICATE)
    ok, buf = cv2.imencode(".png", out)
    return {"png": buf.tobytes(), "matrix": [[round(float(v), 5) for v in row] for row in full],
            "match_before": round(before, 4), "match_after": round(float(after), 4)} if ok else None
