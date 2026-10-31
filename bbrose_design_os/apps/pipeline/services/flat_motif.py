"""[His test finding on design 122's drawing, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 3e965d0), A and B.]

A. "THE MOTIF IS UNREADABLE ... Never trace motifs from the concept photo. First redraw the motif as a FLAT, front-on,
high-resolution artwork ... with the image model, matching the concept's pattern, style and detail. This picture is never
printed; it only feeds the tracer. Trace it as OUTLINES (not centre-lines), keeping thick-and-thin strokes and the fine
detail, then smooth ... Wrap the clean motif onto the form at the concept's layout. The self-check fails a motif with
broken strokes or fragments."

B. "COLOURS ARE OFF ... The photo's warm lighting is being measured as colour. Measure colours from the flat, evenly lit
redraw (not the shaded photo), correct for lighting, and check each drawn colour against the concept by eye-level
difference (ΔE), failing any that drift."

MEASURED at his finding: 122's concept 149 is a 1,024 x 1,536 px photograph of the tube; its motif was thinned to
one-pixel centre-lines (``line_art.trace_lines``) and drawn at one width, 1,724 strokes at about 0.18 mm; its ink measured
off the photo's pixels, #BA5C5D, its body #F7E9E4.

Each line-art motif of the chosen concept is redrawn ONCE by the image model as flat artwork (``redraw_flat``, a paid
picture, kept on the concept — ``SCHEMA`` — so the design drawn again pays nothing), read for its ground and its ink
(``read_flat``), checked whole (``whole``) and traced by potrace as filled OUTLINES (``trace_flat``) — the stroke's own
thick-and-thin kept, never a centre-line — placed in the part's box where the concept lays it. The photo's other colours
(its cap, its type) are corrected for its lighting by the gain that takes the photo's body to the redraw's evenly lit
ground (``lit_gain``), and every colour drawn is checked against the concept by CIEDE2000 (``delta_e``, ``colour_check``).
"""
from __future__ import annotations
from apps.pipeline.services.spend_reservation import paid_operation

import math

#: kept on the concept picture's provenance: each line-art part's flat redraw — ``{part name: record}``
SCHEMA = "container_flat_motif/1.0"
#: kept on the drawing's record: each colour drawn against the concept's, by ΔE
COLOUR_CHECK_SCHEMA = "container_colour_check/1.0"
#: the redraw's own words — how the image service's stand-in knows it
FLAT_WORDS = "Redraw ONLY the"
#: [His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (4): "a
#: standalone carton gets the same flat redraw before tracing".] its words name no form: "no product" says it for every
#: one — a carton's redraw was asked for "no tube" (122's form), and the wiring check names another product's noun
FLAT_PROMPT = (FLAT_WORDS + " {part} printed on this product, as flat, front-on artwork for print: the same pattern, "
               "the same drawing style, the same density and every fine detail — the hatching and the fine lines "
               "inside each shape, every small mark — drawn as clean, crisp, continuous ink lines that keep their own "
               "thick-and-thin, in exactly the colours the product prints it — one ink where it is one ink, every colour "
               "and every soft gradient where it is illustrated — on a perfectly plain, flat, "
               "evenly lit ground of the product's own body colour. Fill the whole frame edge to edge with the pattern "
               "as it covers the product, as if its print were unrolled flat and scanned straight on, the frame "
               "{shape}. No product, no cap, no window, no frame, no text, no logo, no lighting, "
               "no shadow, no reflection, no photo texture, no paper grain.")
#: a motif whose box holds less of the product than this is ONE motif (148's rosebud on its cap), redrawn alone and
#: centred — never an all-over pattern squeezed into its box
SINGLE_SHARE = 0.15
FLAT_PROMPT_SINGLE = (FLAT_WORDS + " {part} printed on this product, as flat, front-on artwork for print: the ONE motif "
                      "alone, centred, filling most of the frame, in the same drawing style and with every fine detail "
                      "it shows, drawn as clean, crisp, continuous lines and shapes that keep their own thick-and-thin, in "
                      "exactly the colours the product prints it, on a perfectly plain, flat, evenly lit ground "
                      "of the colour it is printed on, the frame {shape}. No product, no cap, no other motif, "
                      "no text, no logo, no lighting, no shadow, no reflection, no photo texture.")
#: the image service's three sizes, by the shape of the part's box (width over height)
SIZES = (("1024x1536", 0.83, "taller than it is wide, two by three"), ("1536x1024", 1.2, "wider than it is tall, "
                                                                                              "three by two"))
SQUARE = ("1024x1024", "square")
#: the tracer's numbers, kept on every trace: read at ``upscale`` times the redraw's size, a pixel ink where it stands
#: ``ink_de`` from the ground (CIEDE76 in L*a*b*) — low enough to keep a hairline's faint hatching whole — and every
#: stroke then thinned by ``thin_px`` (at that size) off its soft edge, so a line filled in its pure ink weighs what it
#: shows (MEASURED on 122's 149: unthinned, its lines covered 19.8% of its roses in pure ink where its photo's soft lines
#: covered 21%, and read heavy and dark; thinned, 12.8%, whole; cut at half each line's own strength instead, its
#: hairlines broke into dashes — 47% of their ink in fragments); its colour read on its darkest ``core_share`` (a
#: hairline never reaches its pure ink); the ground
#: read on the outer ``border_share`` of the frame; a piece of ink smaller on the product than ``fragment_mm2`` — the
#: self-check's own speck (``self_check.SPECK_MM2``), or than ``fragment_box_share`` of a small motif's own box — is a
#: fragment, and the motif is broken where fragments hold more
#: than ``fragment_share_max`` of its ink. MEASURED on 122's 149: the strokes traced from its photo held 60% of their ink
#: in fragments, its flat redraw 5%. potrace drops a piece under ``turdsize`` pixels and joins curves at ``opttolerance``
FLAT = {"version": 5, "upscale": 3, "ink_de": 12.0, "thin_px": 1, "core_share": 0.02, "border_share": 0.03,
        "fragment_mm2": 0.3, "fragment_box_share": 0.0005, "fragment_share_max": 0.15, "turdsize": 9,
        "alphamax": 1.0, "opttolerance": 0.2}


def ink_mask(de, scale: int):
    """Where ``de`` (each pixel's distance from the ground) is ink, at ``scale`` times the redraw: FLAT["ink_de"] off the
    ground, thinned by FLAT["thin_px"] off its soft edge where ``scale`` is the tracer's own."""
    import cv2
    import numpy as np
    mask = (de > FLAT["ink_de"]).astype(np.uint8)
    if scale > 1 and int(FLAT["thin_px"]):
        mask = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3)), iterations=int(FLAT["thin_px"]))
    return mask.astype(bool)
TRACED = "TRACED"
REFUSED = "REFUSED"
#: a colour drawn this far (CIEDE2000) from the concept's fails
COLOUR_DE_MAX = 6.0
COLOUR_DRIFTS = "CONTAINER_COLOUR_DRIFTS_FROM_CONCEPT"
MOTIF_BROKEN = "CONTAINER_MOTIF_STROKES_BROKEN"
FLAT_REFUSED = "CONTAINER_FLAT_MOTIF_NOT_MADE"


class FlatMotifRefused(Exception):
    """A flat redraw that could not be made — its words say why."""


def size_for(width_mm: float, height_mm: float) -> tuple:
    """``(the image service's size, its shape in words)`` nearest the part's box."""
    aspect = width_mm / height_mm
    if aspect < SIZES[0][1]:
        return SIZES[0][0], SIZES[0][2]
    if aspect > SIZES[1][1]:
        return SIZES[1][0], SIZES[1][2]
    return SQUARE


def prompt_for(part: str, width_mm: float, height_mm: float, product_mm: tuple) -> str:
    """The redraw's words: an all-over pattern as it covers the product; a small motif (``SINGLE_SHARE``) alone."""
    single = width_mm * height_mm < SINGLE_SHARE * float(product_mm[0]) * float(product_mm[1])
    return (FLAT_PROMPT_SINGLE if single else FLAT_PROMPT).format(part=part, shape=size_for(width_mm, height_mm)[1])


def redraw_flat(aria, image, part: str, width_mm: float, height_mm: float, product_mm: tuple) -> dict:
    """The motif ``part`` of the concept ``image`` redrawn once as flat artwork — a paid picture, on the ledger as
    "image:flat motif:<part>", its file and what it cost kept on the concept (``SCHEMA``). A spending cap already reached
    refuses it before anything is paid (``BudgetExceededError``)."""
    import base64
    import hashlib
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
    if cost_ledger.daily_budget_exceeded():
        raise cost_ledger.BudgetExceededError("the day's spending cap is reached")
    cost_ledger.check_task_budget(aria.task)
    with image.image_file.open("rb") as fh:
        concept = fh.read()
    kind = mimetypes.guess_type(image.image_file.name)[0]
    sent = (os.path.basename(image.image_file.name), concept, kind if kind else "image/png")
    size, _shape = size_for(width_mm, height_mm)
    started = time.monotonic()
    from apps.pipeline.services.cost_ledger import before_paid_call   # [his goal of 2026-10-13, (2)]
    before_paid_call("a picture", fidelity=True)   # [his goal for the pitch, B (6)] fidelity is paid for
    response = paid_operation(openai.images.edit, provider='openai', operation='flat_motif', model=settings.IMAGE_MODEL, image=[sent],
                                  prompt=prompt_for(part, width_mm, height_mm, product_mm),
                                  size=size, quality=settings.IMAGE_QUALITY_CONCEPTS, n=1, timeout=180)
    operation = "image:flat motif:%s" % part
    if _capped(record_image, settings.IMAGE_MODEL, operation, aria.task,
               {"provider_request_id": provider_request_id(response),
                "latency_ms": int((time.monotonic() - started) * 1000), "concept_image_id": image.pk, "part": part}):
        aria.log("ARIA: the flat redraw of '%s' reached this design's spending cap — it is kept, it is paid for" % part,
                 level="warning")
    row = ApiCallRecord.objects.filter(task=aria.task, operation=operation).order_by("-pk").first()
    flat = base64.b64decode(response.data[0].b64_json)
    name = default_storage.save("concepts/task_%d_flat_%d_%s.png" % (aria.task.pk, image.pk,
                                                                     hashlib.sha256(part.encode()).hexdigest()[:8]),
                                ContentFile(flat))
    record = {"part": part, "file": name, "sha256": hashlib.sha256(flat).hexdigest(),
              "product_mm": [round(float(product_mm[0]), 3), round(float(product_mm[1]), 3)],
              "concept_sha256": hashlib.sha256(concept).hexdigest(), "size": size, "model": settings.IMAGE_MODEL,
              "cost_usd": str(row.cost_usd) if row is not None else "0", "at": timezone.now().isoformat(),
              "why": "his test finding on design 122's drawing, A: the motif traced from a flat redraw, never the photo"}
    prov = dict(image.reference_provenance or {})
    kept = dict(prov[SCHEMA]) if isinstance(prov.get(SCHEMA), dict) else {}
    kept[part] = record
    prov[SCHEMA] = kept
    image.reference_provenance = prov
    image.save(update_fields=["reference_provenance"])
    aria.log("ARIA: the motif '%s' redrawn flat for tracing — never printed — $%s" % (part, record["cost_usd"]))
    return record


def _capped(record_image, model: str, operation: str, task, metadata: dict) -> bool:
    """The paid picture put on the ledger — True where that took the design past its spending cap (it is paid for)."""
    from apps.pipeline.services import cost_ledger
    try:
        record_image(model, operation=operation, image_count=1, task=task, metadata=metadata)
    except cost_ledger.BudgetExceededError:
        raise
        return True
    return False


def same_shape(drawn_mm, face_mm) -> bool:
    """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (2).] Whether a picture drawn for a face ``drawn_mm`` (w, h)
    fits the face ``face_mm`` it would be drawn on: both wide, both tall, or both square, and their proportions within a
    sixth of each other — a picture drawn for a box standing is never laid on a box lying flat."""
    if not drawn_mm or not face_mm:
        return True
    a, b = float(drawn_mm[0]) / float(drawn_mm[1]), float(face_mm[0]) / float(face_mm[1])
    return (a >= 1.0) == (b >= 1.0) and abs(a / b - 1.0) <= SAME_SHAPE_SHARE


#: [his goal of 2026-10-13, (2)] a kept picture's proportions may stand this far from its face's and be reused
SAME_SHAPE_SHARE = 1.0 / 6.0


def kept_flat(image, part: str, face_mm=None) -> dict | None:
    """The flat redraw kept on the concept for ``part``, where it was made from THIS picture — [his goal of 2026-10-13,
    (2)] and, where the face it will be drawn on is given (``face_mm``), for a face of its shape (``same_shape``); else
    None."""
    import hashlib
    prov = image.reference_provenance if isinstance(image.reference_provenance, dict) else {}
    kept = prov.get(SCHEMA)
    record = kept.get(part) if isinstance(kept, dict) else None
    if not isinstance(record, dict):
        return None
    with image.image_file.open("rb") as fh:
        if hashlib.sha256(fh.read()).hexdigest() != record.get("concept_sha256"):
            return None
    if face_mm is not None and not same_shape(record.get("product_mm"), face_mm):
        return None
    return record


def flat_bytes(record: dict) -> bytes:
    from django.core.files.storage import default_storage
    with default_storage.open(record["file"], "rb") as fh:
        return fh.read()


# --------------------------------------------------------------------------------------------- reading the flat redraw

def _lab(img):
    import cv2
    import numpy as np
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    return np.stack([lab[..., 0] * 100.0 / 255.0, lab[..., 1] - 128.0, lab[..., 2] - 128.0], -1)


def _hex_of_bgr(px) -> str:
    return "#%02X%02X%02X" % (int(px[2]), int(px[1]), int(px[0]))


def read_flat(png: bytes, width_mm: float, height_mm: float) -> dict:
    """The flat redraw read: cropped about its centre to the part's box's shape (never stretched), its ground (the median
    of its outer ``border_share``), its ink mask (pixels ``ink_de`` from the ground), its ink's colour (the median of its
    core, ``core_de`` from the ground), its stroke width in pixels (twice the 75th percentile of the ink's distance to
    the ground) — ``{"img", "mask", "ground", "ink", "stroke_px", "crop"}``."""
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    want = width_mm / height_mm
    if w / h > want:
        cw, ch = int(round(h * want)), h
    else:
        cw, ch = w, int(round(w / want))
    x0, y0 = (w - cw) // 2, (h - ch) // 2
    img = img[y0:y0 + ch, x0:x0 + cw]
    b = max(2, int(round(min(cw, ch) * FLAT["border_share"])))
    ring = np.concatenate([img[:b].reshape(-1, 3), img[-b:].reshape(-1, 3), img[:, :b].reshape(-1, 3),
                           img[:, -b:].reshape(-1, 3)])
    lab = _lab(img)
    ring_lab = _lab(ring.reshape(1, -1, 3))[0]
    # the ground is the colour most of the border is — its pixels nearer the border's median than the ink is
    med = np.median(ring_lab, 0)
    near = np.sqrt(((ring_lab - med) ** 2).sum(-1)) < FLAT["ink_de"]
    ground_lab = np.median(ring_lab[near], 0)
    ground_bgr = np.median(ring[near], 0)
    de = np.sqrt(((lab - ground_lab) ** 2).sum(-1)).astype(np.float32)
    mask = ink_mask(de, 1)
    core = de >= np.quantile(de[mask], 1.0 - FLAT["core_share"]) if mask.any() else mask
    ink_bgr = np.median(img[core], 0) if core.any() else ground_bgr
    dist = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 3)
    stroke = float(2.0 * np.percentile(dist[mask], 75)) if mask.any() else float(mask.sum())
    return {"img": img, "de": de, "mask": mask, "ground": _hex_of_bgr(ground_bgr), "ink": _hex_of_bgr(ink_bgr),
            "stroke_px": round(stroke, 3), "crop": [x0, y0, cw, ch], "size": [w, h]}


def whole(mask, mm2_per_px: float, fragment_mm2: float) -> dict:
    """[His A4: "The self-check fails a motif with broken strokes or fragments."] How whole the motif's ink is, on the
    product (``mm2_per_px``): its pieces (8-connected), its fragments — pieces smaller than ``fragment_mm2``, a speck or a
    stroke broken into bits — and the share of its ink they hold. ``ok`` where that share is within its limit."""
    import cv2
    import numpy as np
    n, _labels, stats, _c = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA].astype(float) * float(mm2_per_px)
    total = float(areas.sum())
    small = areas < fragment_mm2
    share = float(areas[small].sum()) / max(total, 1e-9)
    pieces = int(n - 1)
    return {"pieces": pieces, "fragments": int(small.sum()), "fragment_share": round(share, 4),
            "fragment_mm2": round(fragment_mm2, 4), "ok": bool(pieces > 0 and share <= FLAT["fragment_share_max"])}


def whole_words(measure: dict) -> str:
    """Why a motif is not whole, in words."""
    if measure["pieces"] == 0:
        return "its flat redraw holds no ink to trace"
    return ("its strokes are broken — %d fragments, each under %g mm² on the product, hold %.0f%% of its ink"
            % (measure["fragments"], measure["fragment_mm2"], 100.0 * measure["fragment_share"]))


def trace_flat(png: bytes, box: list, product_mm: tuple, colour: bool = True) -> dict:
    """The flat redraw of a motif traced as OUTLINES: read (``read_flat``) at the shape of ``box`` — the part's box as
    fractions of the product, clipped to it — checked whole (``whole``), its ink read at ``upscale`` times its size and
    traced by potrace as filled shapes, so each stroke keeps its own thick-and-thin; ``{"state": TRACED, "outlines":
    {"svg", "frame"}, "ink", "ground", "whole", "box", "params"}`` — a point (u, v) of the SVG lying at (fx0 + u * kx, fy0
    + v * ky) of the product — or ``{"state": REFUSED, "why", ...}``."""
    import shutil

    import cv2

    bx0, by0 = max(0.0, float(box[0])), max(0.0, float(box[1]))
    bx1, by1 = min(1.0, float(box[2])), min(1.0, float(box[3]))
    width_mm, height_mm = (bx1 - bx0) * float(product_mm[0]), (by1 - by0) * float(product_mm[1])
    read = read_flat(png, width_mm, height_mm)
    colours = ink_colours(read) if colour else []
    if len(colours) >= COLOUR_ART["least_colours"]:
        # [his goal for the pitch, 2026-10-15, A (4): "several colours, gradients, rich illustration ... all still clean
        # vector and faithful to the concept"; B (7): "a traced motif keeps its colours"] an illustrated motif is traced
        # in its own colours, as a lid's art is — never pressed into one ink
        art = colour_art(png, read)
        if art.get("state") == "TRACED":
            return {"state": TRACED, "art": art, "colours": colours, "ink": colours[0], "ground": read["ground"],
                    "box": [bx0, by0, bx1, by1], "whole": {"ok": True, "pieces": len(art["regions"]),
                                                           "fragments": 0, "fragment_share": 0.0},
                    "ink_share": round(float(read["mask"].mean()), 4), "stroke_mm": 0.0,
                    "params": dict(FLAT, colour_art=dict(COLOUR_ART))}
    k = int(FLAT["upscale"])
    up = ink_mask(cv2.resize(read["de"], None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC), k)
    measure = whole(up, (width_mm / (k * read["crop"][2])) ** 2,
                    min(FLAT["fragment_mm2"], FLAT["fragment_box_share"] * width_mm * height_mm))
    # [his goal for the pitch, B (7): "126's gold rose came out black/brown"] its ink the purest colour its lines are
    # drawn in (``ink_colours``), never their darkest few pixels, where a gold line reads brown
    ink = (ink_colours(read) or [read["ink"]])[0]
    out = {"ink": ink, "ground": read["ground"], "whole": measure, "box": [bx0, by0, bx1, by1],
           "stroke_mm": round(read["stroke_px"] * width_mm / read["crop"][2], 4), "params": dict(FLAT)}
    if not measure["ok"]:
        return dict(out, state=REFUSED, why=whole_words(measure))
    binary = shutil.which("potrace")
    if binary is None:
        return dict(out, state=REFUSED, why="potrace is not on this machine")
    svg = _potrace(binary, up)
    cw, ch = read["crop"][2], read["crop"][3]
    return dict(out, state=TRACED, outlines={"svg": svg, "frame": [bx0, by0, (bx1 - bx0) / (k * cw),
                                                                      (by1 - by0) / (k * ch)]},
                ink_share=round(float(up.mean()), 4))


#: [his goal for the pitch, A (4)] a flat redraw is an illustration, traced in colour, where its ink holds at least
#: ``least_colours`` colours each ``least_share`` of the ink or more and ``apart_de`` (CIEDE76) from one another
COLOUR_ART = {"version": 2, "least_colours": 2, "least_share": 0.06, "apart_de": 18.0, "blend_de": 10.0, "clusters": 6,
              "ground_de": 6.0}


def ink_colours(read) -> list:
    """The distinct colours a flat redraw's ink is drawn in, most first — k-means over its ink pixels in L*a*b*, the
    clusters holding ``least_share`` of the ink, merged where they stand within ``apart_de``."""
    import cv2
    import numpy as np
    mask = read["mask"]
    if not mask.any():
        return []
    # the ink's own body, never the soft edge where it fades into the ground (a hairline's edge is no second colour)
    de = read["de"]
    # each pixel against the strongest ink around it: a pixel well short of it is a line's soft edge
    local = cv2.dilate(de, np.ones((5, 5), np.uint8))
    core = mask & (de >= 0.75 * local)
    px = read["img"][core].astype(np.float32)
    if len(px) > 40000:
        px = px[np.random.default_rng(7).choice(len(px), 40000, replace=False)]
    k = min(COLOUR_ART["clusters"], len(px))
    _c, labels, centres = cv2.kmeans(px, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 2,
                                     cv2.KMEANS_PP_CENTERS)
    shares = np.bincount(labels.ravel(), minlength=k) / float(len(labels))
    lab = _lab(centres.reshape(1, -1, 3).astype(np.uint8))[0]
    g = np.array(_lab_of(read["ground"]), dtype=float)
    # the purest ink first: the colours farthest from the ground — a colour lying between one of them and the ground is
    # that ink blended into the ground at a fine line's edge, never a colour of its own (122's red hairlines read a
    # pink beside their red)
    order = sorted((int(i) for i in range(k)), key=lambda i: -float(np.sqrt(((lab[i] - g) ** 2).sum())))
    # [his goal after the pitch page, B (10): the designer's eye on 140, "concept has many orange honey droplets ...
    # drawing omits them"] each colour's share the share of every cluster that is that colour — its shades within
    # ``apart_de`` of it and its blends into the ground — before a colour too small to be one is left out: 140's orange
    # drops were read as two clusters of 4.6% and 4.2% of the ink, each under ``least_share``, together 8.8%, and the
    # field was traced in its cream alone, its drops cream
    # — each colour drawn, as before, in its purest cluster that holds ``least_share`` on its own, else its purest
    groups = []
    for i in order:
        near = [grp for grp in groups if np.sqrt(((lab[i] - lab[grp[0]]) ** 2).sum()) < COLOUR_ART["apart_de"]
                or _off_segment(lab[i], lab[grp[0]], g) < COLOUR_ART["blend_de"]]
        if near:
            near[0].append(i)
            continue
        groups.append([i])
    out = []
    for grp in groups:
        if sum(float(shares[m]) for m in grp) < COLOUR_ART["least_share"]:
            continue
        whole = [m for m in grp if shares[m] >= COLOUR_ART["least_share"]]
        out.append(_hex_of_bgr(centres[(whole + grp)[0]]))
    return out


def _offset(text) -> float:
    """A path's translation, as vtracer writes it — none written is none moved."""
    return float(text) if text else float(0)


def _off_segment(p, a, b) -> float:
    """How far ``p`` stands (CIEDE76) from the straight run between ``a`` and ``b`` in L*a*b*."""
    import numpy as np
    ab = b - a
    t = float(np.clip(np.dot(p - a, ab) / max(float(np.dot(ab, ab)), 1e-9), 0.0, 1.0))
    return float(np.sqrt(((p - (a + t * ab)) ** 2).sum()))


def colour_art(png: bytes, read) -> dict:
    """The flat redraw, cut to the part's shape (``read``'s crop), traced in colour with the lid's own tracer settings
    (vtracer, ``lid_art.TRACE``): every region in its colour, each region in the ground's own colour (within
    ``ground_de``) left out — the drawing's own ground shows between the shapes. A large flat shape is a shape, never
    ground (the lid's sky-fit would take it for sky)."""
    import re

    import cv2
    import vtracer

    from apps.pipeline.targets.container import lid_art as _la
    img = read["img"]
    h, w = img.shape[:2]
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        return {"state": REFUSED, "why": "the redraw could not be cut"}
    T = _la.TRACE
    svg = vtracer.convert_raw_image_to_svg(buf.tobytes(), img_format="png", colormode="color", hierarchical="cutout",
                                            mode="spline", filter_speckle=max(4, int(round(T["speckle_px"] * max(w, h)
                                                                                           / 1536.0))),
                                            color_precision=T["colour_precision"],
                                            layer_difference=T["layer_difference"],
                                            corner_threshold=T["corner_threshold"],
                                            length_threshold=T["length_threshold"],
                                            splice_threshold=T["splice_threshold"], path_precision=T["path_precision"])
    regions, left = [], 0
    for d, fill, tx, ty in re.findall(
            r'<path d="([^"]+)" fill="(#[0-9A-Fa-f]{6})"(?: transform="translate\(([-\d.]+),([-\d.]+)\)")?', svg):
        if delta_e(fill.upper(), read["ground"]) < COLOUR_ART["ground_de"]:
            left += 1
            continue
        rings = _la._rings(d, _offset(tx), _offset(ty), w, h)
        if rings:
            regions.append({"fill": fill.upper(), "rings": rings})
    if not regions:
        return {"state": REFUSED, "why": "its colour trace holds nothing but its ground"}
    return {"state": TRACED, "size_px": [int(w), int(h)], "round": False, "sky": {"rows": []}, "regions": regions,
            "measured": {"regions": len(regions), "left_out_as_ground": left}, "params": dict(T)}


def _potrace(binary: str, mask) -> str:
    """potrace's own SVG of ``mask`` (True is ink), with this tracer's numbers (``FLAT``)."""
    import subprocess
    import tempfile

    import numpy as np
    with tempfile.TemporaryDirectory() as d:
        with open(d + "/ink.pbm", "wb") as f:
            f.write(("P4\n%d %d\n" % (mask.shape[1], mask.shape[0])).encode()
                    + np.packbits(mask.astype(np.uint8), axis=1).tobytes())
        subprocess.run([binary, "-s", "--flat", "-t", str(FLAT["turdsize"]), "-a", str(FLAT["alphamax"]),
                        "-O", str(FLAT["opttolerance"]), d + "/ink.pbm", "-o", d + "/ink.svg"], check=True,
                       capture_output=True, timeout=120)
        with open(d + "/ink.svg", encoding="utf-8") as f:
            return f.read()


# ------------------------------------------------------------------------------------------------- colour, by ΔE

def _srgb_lin(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lin_srgb(v: float) -> int:
    v = min(1.0, max(0.0, v))
    c = 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
    return int(round(c * 255.0))


def _rgb(hx: str) -> tuple:
    return int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)


#: a solid part read on its evenly lit face: its pixels between these luminance quantiles — its shaded side below, its
#: shine above, left out; the product told from the photo's backdrop where it stands ``backdrop_de`` from it
LIT_FACE = {"low": 0.5, "high": 0.85, "backdrop_de": 6.0}


def lit_face(pic: bytes, box: list, mapped_px=None) -> str | None:
    """[His B: "The photo's warm lighting is being measured as colour ... correct for lighting".] A solid part of the
    concept photo — its cap — read on its evenly lit face: the product found in the photo by where it stands apart from
    its backdrop (the photo's corners), the part's box (fractions of the product) cut from it, and the median of its
    pixels between LIT_FACE's luminance quantiles — never its shaded side (MEASURED on 122's 149: the map read its cap
    #EDC3BF over shade and light; its lit face is #F4CEC9). None where the box holds no pixel of the product. The product
    is the map's own where it is given (``mapped_px``, ``_product_frame``)."""
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(pic, np.uint8), cv2.IMREAD_COLOR)
    lab = _lab(img)
    found = _product_frame(img, lab, mapped_px)
    if found is None:
        return None
    (px0, py0, px1, py1), product = found
    x0, x1 = int(px0 + max(0.0, box[0]) * (px1 - px0)), int(px0 + min(1.0, box[2]) * (px1 - px0))
    y0, y1 = int(py0 + max(0.0, box[1]) * (py1 - py0)), int(py0 + min(1.0, box[3]) * (py1 - py0))
    part = img[y0:y1, x0:x1][product[y0:y1, x0:x1]]
    if not len(part):
        return None
    lum = lab[y0:y1, x0:x1][product[y0:y1, x0:x1]][:, 0]
    lo, hi = np.quantile(lum, LIT_FACE["low"]), np.quantile(lum, LIT_FACE["high"])
    face = part[(lum >= lo) & (lum <= hi)]
    return _hex_of_bgr(np.median(face if len(face) else part, 0))


#: [His goal after the pitch page, 2026-10-15, A (2): "METALS: gold and chrome are drawn as metallic (highlights and
#: shadows as the concept shows), never flat tan or grey"] how a part's light runs across it, read off the concept photo:
#: each column of the part's box holding at least ``least_px`` of the product's pixels read as their median L*; the
#: columns smoothed by a running median ``smooth_share`` of their count wide, then read at ``stops`` evenly spaced places
#: from the part's left edge to its right, and at its brightest and its darkest column. ``spread`` is the columns' L*
#: between their ``spread_q`` quantiles — how far the light runs from its shade to its shine. The executor's, new.
#: [His review of 127, 130, 131 and 132, 2026-10-15, D (11): the collar "dark where the concept shows bright silver"]
#: light_run/1.1: the run read at the fewest places that keep every column within ``tolerance_l`` L* of it (at most
#: ``most_stops``, the tolerance doubled until they are) — a narrow reflection drawn as narrow as the concept shows it,
#: never spread to the next of nine evenly spaced places (128's collar: a dark band a tenth of its width drawn across a
#: quarter of it)
LIGHT_RUN = {"version": "light_run/1.1", "least_px": 3, "smooth_share": 0.04, "stops": 9, "spread_q": (0.05, 0.95),
             "tolerance_l": 4.0, "most_stops": 24}


def _run_places(smooth: list, tolerance: float) -> list:
    """The indices of ``smooth`` (L* by column) a polyline through which keeps every column within ``tolerance`` L* —
    its two ends always, and every place it turns (Douglas-Peucker on the L* each column reads)."""
    n = len(smooth)
    keep = {0, n - 1}
    todo = [(0, n - 1)]
    while todo:
        a, b = todo.pop()
        if b - a < 2:
            continue
        far, at = -1.0, a
        for j in range(a + 1, b):
            line = smooth[a] + (smooth[b] - smooth[a]) * (j - a) / float(b - a)
            if abs(smooth[j] - line) > far:
                far, at = abs(smooth[j] - line), j
        if far > tolerance:
            keep.add(at)
            todo += [(a, at), (at, b)]
    return sorted(keep)


def light_run(pic: bytes, box: list, mapped_px=None) -> dict | None:
    """[His goal after the pitch page, 2026-10-15, A (2)] The light across a part of the concept photo (``LIGHT_RUN``) —
    ``{"lightness": [[offset 0..1 across the part, L* 0..100], ...], "spread": L*, "version"}`` — read on the product's own
    pixels inside the part's box (fractions of the product, as ``lit_face`` reads them; the product the map's own where
    it is given, ``mapped_px``), from the leftmost column holding the product to the rightmost: where its highlights and
    its shadows stand. None where fewer than two columns hold the product."""
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(pic, np.uint8), cv2.IMREAD_COLOR)
    lab = _lab(img)
    found = _product_frame(img, lab, mapped_px)
    if found is None:
        return None
    (px0, py0, px1, py1), product = found
    x0, x1 = int(px0 + max(0.0, box[0]) * (px1 - px0)), int(px0 + min(1.0, box[2]) * (px1 - px0))
    y0, y1 = int(py0 + max(0.0, box[1]) * (py1 - py0)), int(py0 + min(1.0, box[3]) * (py1 - py0))
    held = product[y0:y1, x0:x1]
    light = lab[y0:y1, x0:x1, 0]
    cols = [float(np.median(light[:, j][held[:, j]])) for j in range(held.shape[1])
            if int(held[:, j].sum()) >= LIGHT_RUN["least_px"]]
    if len(cols) < 2:
        return None
    k = max(1, int(round(LIGHT_RUN["smooth_share"] * len(cols))))
    smooth = [float(np.median(cols[max(0, j - k):j + k + 1])) for j in range(len(cols))]
    last = len(smooth) - 1
    # [His review of 127, 130, 131 and 132, 2026-10-15, D (11)] where the run turns, as narrow as it turns — and the
    # part's brightest and darkest columns themselves — a narrow shine is never stepped over, nor a narrow shade spread
    tolerance = float(LIGHT_RUN["tolerance_l"])
    places = _run_places(smooth, tolerance)
    while len(places) > int(LIGHT_RUN["most_stops"]):
        tolerance *= 2.0
        places = _run_places(smooth, tolerance)
    at = sorted({round(j / last, 4) for j in places} | {round(int(np.argmax(smooth)) / last, 4),
                                                        round(int(np.argmin(smooth)) / last, 4)})
    run = [[o, round(smooth[int(round(o * last))], 2)] for o in at]
    lo, hi = np.quantile(np.array(smooth), LIGHT_RUN["spread_q"])
    return {"lightness": run, "spread": round(float(hi - lo), 2), "version": LIGHT_RUN["version"]}


def _product_frame(img, lab, mapped_px):
    """[His goal of 2026-10-13, (10): "colour drift".] The product in a photo as the concept's map found it: its box
    (``mapped_px``, the map's ``product_box_px``, at the outline's read scale — ``concept_outline.TRACE_PARAMS
    ["scale_px"]`` on the long side) in the photo's own pixels, and the mask of what stands LIT_FACE["backdrop_de"] from
    the backdrop right beside it, either side — never from the photo's corners, which a vignette darkens (126's bottle,
    on a dark ground falling off to black, was found as the whole picture: its cap read in its shadow, its gold rose's
    lines read black). Where no map's box is given, the corners' reading (``_product_box``)."""
    import numpy as np
    if mapped_px is None:
        return _product_box(img, lab)
    from apps.pipeline.services.concept_outline import TRACE_PARAMS
    h, w = img.shape[:2]
    s = min(1.0, float(TRACE_PARAMS["scale_px"]) / max(h, w))
    x0, y0, x1, y1 = (int(round(float(v) / s)) for v in mapped_px)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    pad = max(4, (x1 - x0) // 12)
    beside = np.concatenate([lab[y0:y1, max(0, x0 - 3 * pad):max(0, x0 - pad)].reshape(-1, 3),
                             lab[y0:y1, min(w, x1 + pad):min(w, x1 + 3 * pad)].reshape(-1, 3)])
    if not len(beside):
        return _product_box(img, lab)               # the product fills the picture: nothing beside it to read
    product = np.sqrt(((lab - np.median(beside, 0)) ** 2).sum(-1)) > LIT_FACE["backdrop_de"]
    return (x0, y0, x1, y1), product


def _product_box(img, lab):
    """The product in a photo: where it stands LIT_FACE["backdrop_de"] from its backdrop (its corners) — its box, in
    pixels, and that mask; None where nothing stands apart."""
    import numpy as np
    h, w = img.shape[:2]
    b = max(4, min(h, w) // 40)
    corners = np.concatenate([img[:b, :b].reshape(-1, 3), img[:b, -b:].reshape(-1, 3), img[-b:, :b].reshape(-1, 3),
                              img[-b:, -b:].reshape(-1, 3)])
    backdrop = np.median(_lab(corners.reshape(1, -1, 3))[0], 0)
    product = np.sqrt(((lab - backdrop) ** 2).sum(-1)) > LIT_FACE["backdrop_de"]
    ys, xs = np.nonzero(product)
    if not len(xs):
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1), product


def photo_line_ink(pic: bytes, box: list, ground_hex: str, mapped_px=None) -> str | None:
    """The concept photo's own reading of a motif's ink — the darkest FLAT["core_share"] of its lines inside the part's
    box (fractions of the product), as ``read_flat`` reads the flat redraw's — the colour the flat redraw's ink is checked
    against: the product's own pixels only, never the backdrop beside it (``_product_frame``, the map's own box where it
    is given). None where the box holds no line."""
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(pic, np.uint8), cv2.IMREAD_COLOR)
    lab = _lab(img)
    found = _product_frame(img, lab, mapped_px)
    if found is None:
        return None
    (px0, py0, px1, py1), product = found
    x0, x1 = int(px0 + max(0.0, box[0]) * (px1 - px0)), int(px0 + min(1.0, box[2]) * (px1 - px0))
    y0, y1 = int(py0 + max(0.0, box[1]) * (py1 - py0)), int(py0 + min(1.0, box[3]) * (py1 - py0))
    de = np.sqrt(((lab[y0:y1, x0:x1] - np.array(_lab_of(ground_hex))) ** 2).sum(-1)).astype(np.float32)
    mask = ink_mask(de, 1) & product[y0:y1, x0:x1]
    if not mask.any():
        return None
    core = de >= np.quantile(de[mask], 1.0 - FLAT["core_share"])
    return _hex_of_bgr(np.median(img[y0:y1, x0:x1][core], 0))


def lit_gain(photo_hex: str, flat_hex: str) -> tuple:
    """The photo's lighting, as the gain per channel (linear light) that takes the photo's own body to the flat redraw's
    evenly lit ground — the cast the shaded photo puts on every colour it shows."""
    return tuple(_srgb_lin(f) / max(_srgb_lin(p), 1e-6) for p, f in zip(_rgb(photo_hex), _rgb(flat_hex)))


def corrected(hx: str, gain: tuple) -> str:
    """``hx`` as the photo shows it, its lighting taken off by ``gain``."""
    return "#%02X%02X%02X" % tuple(_lin_srgb(_srgb_lin(c) * g) for c, g in zip(_rgb(hx), gain))


def _lab_of(hx: str) -> tuple:
    r, g, b = (_srgb_lin(c) for c in _rgb(hx))
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def delta_e(hx1: str, hx2: str) -> float:
    """CIEDE2000 between two colours — about 1 the least difference an eye sees, about 5 plainly another colour."""
    L1, a1, b1 = _lab_of(hx1)
    L2, a2, b2 = _lab_of(hx2)
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    dh = h2p - h1p
    if C1p * C2p == 0:
        dh = 0.0
    elif dh > 180:
        dh -= 360
    elif dh < -180:
        dh += 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dh / 2))
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    hsum = h1p + h2p
    if C1p * C2p == 0:
        hbp = hsum
    elif abs(h1p - h2p) <= 180:
        hbp = hsum / 2
    elif hsum < 360:
        hbp = (hsum + 360) / 2
    else:
        hbp = (hsum - 360) / 2
    T = (1 - 0.17 * math.cos(math.radians(hbp - 30)) + 0.24 * math.cos(math.radians(2 * hbp))
         + 0.32 * math.cos(math.radians(3 * hbp + 6)) - 0.20 * math.cos(math.radians(4 * hbp - 63)))
    dtheta = 30 * math.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
    Sl = 1 + (0.015 * (Lbp - 50) ** 2) / math.sqrt(20 + (Lbp - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cbp, 1 + 0.015 * Cbp * T
    Rt = -math.sin(math.radians(2 * dtheta)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def colour_check(drawn: dict, concept: dict) -> dict:
    """[His B: "check each drawn colour against the concept by eye-level difference (ΔE), failing any that drift."] Each
    colour drawn (``drawn``: ``{role: hex}``) against the concept's (``concept``: ``{role: (hex, how it was read)}``), by
    CIEDE2000 — a role the concept gives no colour for said so, never passed; ``COLOUR_DRIFTS`` with the roles past
    COLOUR_DE_MAX."""
    rows, drifted = {}, []
    for role, hx in drawn.items():
        if role not in concept:
            rows[role] = {"drawn": hx, "state": "NOT_IN_THE_CONCEPT"}
            continue
        ref, how = concept[role]
        de = round(delta_e(hx, ref), 2)
        state = "HELD" if de <= COLOUR_DE_MAX else "DRIFTS"
        rows[role] = {"drawn": hx, "concept": ref, "read": how, "delta_e": de, "state": state}
        if state == "DRIFTS":
            drifted.append(role)
    return {"schema_version": COLOUR_CHECK_SCHEMA, "limit_delta_e": COLOUR_DE_MAX, "roles": rows,
            "codes": ["%s: %s" % (COLOUR_DRIFTS, ", ".join("%s ΔE %.1f" % (r, rows[r]["delta_e"]) for r in drifted))]
            if drifted else []}


# ------------------------------------------------------------------------- a solid motif traced from the photo, judged
#: [His review of 127, 130, 131 and 132, 2026-10-15, C (2): "NO BROKEN MOTIFS: a motif that can't be traced cleanly
#: (132's side and flap flower, which looks like a fidget spinner) is redrawn flat and traced again; never printed
#: broken."] A solid motif traced from the concept photo (``concept_design_map.trace_shape``, and its further inks,
#: ``shape_layers``) is whole where its drawing, every ink in its own colour, agrees with the picture it was traced from:
#: each pixel of the motif's own box, read as the colour nearest it of the ground and the motif's inks, the same colour
#: the drawing paints there in at least ``agree_min`` of the motif's ink (each ink's overlap over its union with the
#: picture's, weighted by the picture's ink) — the parts printed over it (a name, a mark: smaller boxes inside its own)
#: and everything outside the product left out; no ink of it broken into more than ``pieces_max`` separate pieces; and
#: pieces smaller than ``fragment_box_share`` of its box holding at most FLAT["fragment_share_max"] of its ink.
#: MEASURED on the shapes on record: 119's berry vial silhouette agrees 0.94 (2 pieces), 123's scalloped band 0.91 (2
#: pieces); 132's flower 0.64 in its two inks (gold 0.77, blue 0.56 — its petals' outlines and its top petal lost; 11
#: and 10 pieces), and its gold alone, the flaps' "fidget spinner", 11 pieces.
SHAPE_WHOLE = {"version": "shape_whole/1.0", "agree_min": 0.85, "pieces_max": 6, "fragment_box_share": 0.002,
               "curve_steps": 10}
#: … and said so, on the motif, beside Approve
SHAPE_BROKEN = "CONTAINER_MOTIF_TRACE_BROKEN"


def _rings_px(cubics, to_px, steps: int) -> list:
    """A traced shape's rings (``[[start], [c1x, c1y, c2x, c2y, x, y], …]`` per polygon) as pixel polygons, each curve
    walked in ``steps``; ``to_px`` takes a point of the product's fractions to the picture's pixels."""
    import numpy as np
    out = []
    for poly in cubics:
        for ring in poly:
            at = (float(ring[0][0]), float(ring[0][1]))
            pts = [to_px(at)]
            for seg in ring[1:]:
                for i in range(1, steps + 1):
                    t = i / float(steps)
                    u = 1.0 - t
                    if len(seg) == 6:
                        pt = (u ** 3 * at[0] + 3 * u * u * t * seg[0] + 3 * u * t * t * seg[2] + t ** 3 * seg[4],
                              u ** 3 * at[1] + 3 * u * u * t * seg[1] + 3 * u * t * t * seg[3] + t ** 3 * seg[5])
                    else:
                        pt = (u * at[0] + t * seg[0], u * at[1] + t * seg[1])
                    pts.append(to_px(pt))
                at = (float(seg[-2]), float(seg[-1]))
            out.append(np.round(np.array(pts, float) * 4.0).astype(np.int32))
    return out


def shape_whole(image_bytes: bytes, record: dict, shape: dict) -> dict:
    """[His review of 127, 130, 131 and 132, 2026-10-15, C (2).] How whole a solid motif traced from the concept photo
    is (``SHAPE_WHOLE``): ``{"ok", "agreement", "inks" (each ink's agreement), "pieces", "fragment_share", "why",
    "params"}``; one that cannot be measured (its picture not read as the map read it) is ``measured`` False and kept as
    it is drawn. Pure: nothing paid, nothing written."""
    import cv2
    import numpy as np

    from apps.pipeline.services import concept_design_map as dm
    params = dict(SHAPE_WHOLE)
    if not image_bytes:
        return {"ok": True, "measured": False, "why": "no picture to measure it against", "params": params}
    img, mask, pbox = dm._full_size(image_bytes, record)
    if img is None:
        return {"ok": True, "measured": False, "why": "its picture could not be read as the map read it: %s" % pbox,
                "params": params}
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    b = [float(v) for v in shape["box"]]
    cx0, cy0 = max(0, int(x0 + b[0] * w)), max(0, int(y0 + b[1] * h))
    cx1, cy1 = min(img.shape[1], int(math.ceil(x0 + b[2] * w))), min(img.shape[0], int(math.ceil(y0 + b[3] * h)))
    if cx1 - cx0 < 4 or cy1 - cy0 < 4:
        return {"ok": True, "measured": False, "why": "its box holds too few of the picture's pixels to measure",
                "params": params}
    crop = img[cy0:cy1, cx0:cx1]
    H, W = crop.shape[:2]
    lab = np.stack(dm._lab(crop), -1)

    def to_px(pt):
        return (x0 + float(pt[0]) * w - cx0, y0 + float(pt[1]) * h - cy0)
    inks = [(shape["ink"], shape["cubics"])] + [(layer["ink"], layer["cubics"]) for layer in shape.get("layers") or []]
    drawn = np.zeros((H, W), np.int32)
    for i, (_ink, cubics) in enumerate(inks):
        paint = np.zeros((H, W), np.uint8)
        for ring in _rings_px(cubics, to_px, int(params["curve_steps"])):
            one = np.zeros_like(paint)
            cv2.fillPoly(one, [ring], 1, shift=2)
            paint ^= one                                           # its holes its own (even-odd), as it is drawn
        drawn[paint > 0] = i + 1
    # the ground it stands on: the map's field, else the colour round its box
    fields = [p for p in record.get("parts") or [] if p.get("kind") == "field" and p.get("colour")]
    if fields:
        ground = np.array(dm._hex_lab(fields[0]["colour"]))
    else:
        ground = np.median(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]), 0)
    refs = [ground] + [np.array(dm._hex_lab(ink)) for ink, _c in inks]
    seen = np.stack([np.sqrt(((lab - ref) ** 2).sum(-1)) for ref in refs], -1).argmin(-1)
    # the parts printed over it — smaller boxes than its own — and what lies outside the product are not its to match
    keep = mask[cy0:cy1, cx0:cx1] > 0
    own = (b[2] - b[0]) * (b[3] - b[1])
    for part in record.get("parts") or []:
        ob = part.get("box")
        if not ob or part.get("name") == shape.get("part") or part.get("kind") == "field":
            continue
        if (float(ob[2]) - float(ob[0])) * (float(ob[3]) - float(ob[1])) >= own:
            continue
        ox0, oy0 = int(x0 + float(ob[0]) * w) - cx0, int(y0 + float(ob[1]) * h) - cy0
        ox1, oy1 = int(x0 + float(ob[2]) * w) - cx0, int(y0 + float(ob[3]) * h) - cy0
        keep[max(0, oy0):max(0, oy1), max(0, ox0):max(0, ox1)] = False
    per, weighted, weight = [], 0.0, 0
    for i in range(1, len(refs)):
        pic_i, drawn_i = (seen == i) & keep, (drawn == i) & keep
        union = int((pic_i | drawn_i).sum())
        iou = float((pic_i & drawn_i).sum()) / max(union, 1)
        per.append(round(iou, 3))
        weighted += iou * int(pic_i.sum())
        weight += int(pic_i.sum())
    agreement = weighted / max(weight, 1)
    pieces, small, total = [], 0, 0
    for i in range(1, len(refs)):
        n, _cc, stats, _cent = cv2.connectedComponentsWithStats((drawn == i).astype(np.uint8), connectivity=8)
        areas = stats[1:, cv2.CC_STAT_AREA]
        pieces.append(int(n - 1))
        total += int(areas.sum())
        small += int(areas[areas < params["fragment_box_share"] * H * W].sum())
    share = small / float(max(total, 1))
    why = []
    if agreement < params["agree_min"]:
        why.append("its trace agrees with the picture on only %.0f%% of its ink" % (100.0 * agreement))
    if max(pieces) > params["pieces_max"]:
        why.append("it is broken into %s pieces" % " and ".join(str(n) for n in pieces))
    if share > FLAT["fragment_share_max"]:
        why.append("fragments hold %.0f%% of its ink" % (100.0 * share))
    return {"ok": not why, "measured": True, "agreement": round(agreement, 3), "inks": per, "pieces": pieces,
            "fragment_share": round(share, 4), "why": "; ".join(why), "params": params}
