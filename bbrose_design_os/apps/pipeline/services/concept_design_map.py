"""[HIS ANSWER AFTER TEST DAY FINDING 3, 2026-09-30 (OWNER_BLOCKER_CLEARANCE.md, the block of that date, transcribed at
23d4375)]: "the same strategy we used with that [the product's shape] … to identify the designs on … the generated image
so basically what it does it tries to uh, highlight each um, part of the design, each motif, and um, try to identify its
color, the shape and everything, and it tries to measure it. And the same way, draw it." And his narrowing: "it
shouldn't care about shadowing, background, the lighting on the bottle, it should ignore those things, the system should
be smart enough to detect those things and ignore them by choice."

``container_design_map/1.0`` — THE MAP: the chosen concept picture's design read from its own pixels. This module is its
LOCAL HALF — free and pure (numpy and OpenCV on the picture's bytes; no ORM, no provider, nothing written):

* THE PRODUCT, cut from its ground and stood as the picture stands it (``concept_outline.standing_pixels`` — the cut two
  seeds agree on, the elevation trace's own); a picture the trace refuses is refused here, by the trace's reason;
* THE LIGHT, detected, marked and left out:
  - the GROUND, everything outside the product;
  - the SHINE, a pixel near-white, near-grey and lighter than its own surroundings (a specular streak) — a cream print
    is as light as the cream around it, and a gold letter is coloured, so neither is shine;
  - the EDGE FALL-OFF, each row's outer share, where a curved surface turns from the light;
* THE COLOURS: the product's remaining pixels clustered in Lab, clusters nearer than MAP_PARAMS["merge_de"] merged, each
  measured as the median of its own pixels, with its share of the product;
* THE REGIONS: each colour's connected parts larger than MAP_PARAMS["min_region"] of the product, each with its box as
  fractions of the product's own box (x right, y down) and its share.

THE READ (``read_parts``), the map's paid half: one vision call names each PART of the design — its kind (field, band,
closure, mark, type, rule, motif, window), a name in plain words, its box on a pixel grid drawn over the standing
product, the count of a motif, the words and the lettering of type — and the LIGHT it sees, which is never a part. Every
part's COLOUR is then taken from the map's own measured colours, never from the concept's words (his ruling (1)): a
surface's, the colour most of its evenly lit middle holds; an ink's, the colour most of its box holds that is not its
ground. The read's cost is stated from the ledger's own price table, on the design's own ledger.

THE SCORE (``score``, over ``product_png``): the drawing against the concept, part by part — each part the map names
measured on the drawn product exactly as the map measured it on the concept, its colour set beside the concept's in ΔE,
its place beside the concept's in millimetres where the drawing records it; a part passes only under both of the bars
told him (SCORE_BARS), and a part whose place is not recorded does not pass.

WHAT IT NEVER DOES: draw. The numbers in MAP_PARAMS are the executor's, new with this module, recorded in every map; they
decide only what is read as light, and no ruled number moves.
"""
from __future__ import annotations

import hashlib
import io
import math
import re

SCHEMA = "container_design_map/1.0"
MAP_READ = "READ"
MAP_UNREAD = "UNREAD"
MAP_NO_PRODUCT = "DESIGN_MAP_NO_PRODUCT"          # the trace found no one standing product to read

MAP_PARAMS = {
    "version": "concept_design_map_params/1.3",   # 1.3: [his review, C (3)] a surface clear of the surfaces inside it; 1.2: [his goal for the pitch] never the backdrop; 1.1: the ink of a thin or small part
    "edge_share": 0.08,        # each row's outer share, each side, read as the curved surface's fall-off
    "shine_l_min": 80.0,       # a shine pixel is at least this light (L*) …
    "shine_c_max": 15.0,       # … no more coloured than this (chroma) …
    "shine_lift": 8.0,         # … and this much lighter than the median of its surroundings
    "shine_window_px": 31,     # the surroundings: a median over this square, at the trace's scale
    "clusters": 10,            # the colours the product's pixels are first split into
    "cluster_seed": 20260930,  # the random state the split starts from, so the same bytes give the same map
    "merge_de": 10.0,          # two colours nearer than this (CIE76) are one printed colour, lit differently
    # [his goal for the pitch, 2026-10-15, B (7)] a surface's colour is never one within this (CIE76) of the backdrop
    # outside the product, where at least this share of its pixels are the product's own
    "backdrop_de": 12.0, "backdrop_least": 0.15,
    "min_region": 0.002,       # a region smaller than this share of the product is left unlisted
    "shade_hue_deg": 8.0,      # two colours of one hue within this angle (a*, b*) … (light keeps a colour's hue)
    "shade_chroma": 1.6,       # … whose chromas lie within this ratio are one colour under two lights
    "second_ink": 0.25,        # a part's second ink holds at least this share of its first (a contour round a fill)
    # [His review of 127, 130, 131 and 132, 2026-10-15, C (3)] a standing product's surface is read in its middle clear
    # of every other surface held inside its box (130's white body round its cobalt oval); where that leaves less than
    # this share of its middle, on the whole of its box clear of them
    "surface_clear_least": 0.2,
}


def _lab(img):
    """(L*, a*, b*) of a BGR picture as floats, L* 0..100."""
    import cv2
    import numpy as np
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    return lab[..., 0] * 100.0 / 255.0, lab[..., 1] - 128.0, lab[..., 2] - 128.0


def is_gold_hex(hex_: str) -> bool:
    """[His rule of 2026-10-02, "Gold in the picture is foil", and his goal of 2026-10-12, (4).] One drawn colour judged
    by the test the map's tracers find the picture's gold with (``_gold``): yellow over red, lit or in its shade."""
    import numpy as np
    h = str(hex_).lstrip("#")
    L, A, B = _lab(np.uint8([[[int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)]]]))
    L, A, B = float(L[0, 0]), float(A[0, 0]), float(B[0, 0])
    return B > SHAPE_PARAMS["gold_b_min"] and B > A + SHAPE_PARAMS["gold_b_over_a"] and L > SHAPE_PARAMS["gold_l_min"]


def _hex(lab_px) -> str:
    """The hex of one (L*, a*, b*)."""
    import cv2
    import numpy as np
    px = np.uint8([[[np.clip(lab_px[0] * 2.55, 0, 255), np.clip(lab_px[1] + 128, 0, 255),
                     np.clip(lab_px[2] + 128, 0, 255)]]])
    b, g, r = cv2.cvtColor(px, cv2.COLOR_LAB2BGR)[0, 0]
    return "#%02X%02X%02X" % (int(r), int(g), int(b))


def light(img, mask) -> dict:
    """The light on the product, detected — ``{"shine": bool array, "edge": bool array}`` over the picture: the shine
    a pixel near-white, near-grey and lighter than the median around it; the edge fall-off each row's outer
    MAP_PARAMS["edge_share"] of the product's width, each side."""
    import cv2
    import numpy as np
    L, A, B = _lab(img)
    chroma = np.hypot(A, B)
    inside = mask > 0
    k = int(MAP_PARAMS["shine_window_px"]) | 1
    around = cv2.medianBlur(np.clip(L * 2.55, 0, 255).astype(np.uint8), k).astype(np.float32) / 2.55
    shine = inside & (L >= MAP_PARAMS["shine_l_min"]) & (chroma <= MAP_PARAMS["shine_c_max"]) \
        & (L - around >= MAP_PARAMS["shine_lift"])
    edge = np.zeros(mask.shape, bool)
    for y in range(mask.shape[0]):
        xs = np.nonzero(mask[y])[0]
        if len(xs) < 4:
            continue
        x0, x1 = int(xs.min()), int(xs.max())
        e = max(1, int(MAP_PARAMS["edge_share"] * (x1 - x0)))
        edge[y, x0:x0 + e] = True
        edge[y, x1 - e + 1:x1 + 1] = True
    return {"shine": shine, "edge": edge & inside}


def read_pixels(img, mask) -> tuple[dict, object]:
    """The map's local half over one product's pixels — ``(record, label image)``: the light's shares, the design's
    colours (merged, measured, largest first) and each colour's regions; the label image gives each pixel its colour's
    index, -1 where it is ground or light."""
    import cv2
    import numpy as np
    inside = mask > 0
    lit = light(img, mask)
    use = inside & ~lit["shine"] & ~lit["edge"]
    L, A, B = _lab(img)
    X = np.stack([L[use], A[use] * 1.5, B[use] * 1.5], 1).astype(np.float32)
    k = min(int(MAP_PARAMS["clusters"]), max(1, len(X)))
    cv2.setRNGSeed(int(MAP_PARAMS["cluster_seed"]))
    _c, labels, _centres = cv2.kmeans(X, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.5), 4,
                                      cv2.KMEANS_PP_CENTERS)
    labels = labels.ravel()
    lab_px = np.stack([L[use], A[use], B[use]], 1)
    medians = [np.median(lab_px[labels == i], axis=0) if (labels == i).any() else None for i in range(k)]
    # merge colours nearer than merge_de, largest first: a printed colour lit two ways is one colour
    order = sorted(range(k), key=lambda i: -int((labels == i).sum()))
    parent = {}
    for i in order:
        if medians[i] is None:
            continue
        for j in [p for p in order if p in parent and parent[p] == p]:
            if float(np.linalg.norm(medians[i] - medians[j])) < MAP_PARAMS["merge_de"]:
                parent[i] = j
                break
        else:
            parent[i] = i
    roots = [i for i in order if parent.get(i) == i]
    lut = np.array([roots.index(parent[i]) if i in parent else -1 for i in range(k)])
    merged = lut[labels]
    label_img = np.full(mask.shape, -1, int)
    label_img[use] = merged
    total = float(inside.sum())
    ys, xs = np.nonzero(inside)
    px0, py0, px1, py1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    pw, ph = float(px1 - px0), float(py1 - py0)
    colours = []
    for n, _root in enumerate(roots):
        mine = merged == n
        med = np.median(lab_px[mine], axis=0)
        regions = []
        count, comp, stats, _cent = cv2.connectedComponentsWithStats((label_img == n).astype(np.uint8), 8)
        for c in range(1, count):
            share = float(stats[c, cv2.CC_STAT_AREA]) / total
            if share < MAP_PARAMS["min_region"]:
                continue
            x, y, w, h = (int(v) for v in stats[c, :4])
            regions.append({"box": [round((x - px0) / pw, 4), round((y - py0) / ph, 4), round((x + w - px0) / pw, 4),
                                    round((y + h - py0) / ph, 4)], "share": round(share, 4)})
        regions.sort(key=lambda r: -r["share"])
        colours.append({"hex": _hex(med), "share": round(float(mine.sum()) / total, 4),
                        "lab": [round(float(v), 1) for v in med], "regions": regions})
    record = {"light": {"shine_share": round(float(lit["shine"].sum()) / total, 4),
                        "edge_share": round(float(lit["edge"].sum()) / total, 4),
                        "ground": "every pixel outside the product"},
              "product_box_px": [px0, py0, px1, py1], "colours": colours}
    # [his goal for the pitch, 2026-10-15, B (7)] the backdrop the product stands on, well clear of it — a surface's
    # colour is never read in it where the product's own mask reaches past its edge (132's ivory carton read #4D4B4C)
    outside = ~cv2.dilate(inside.astype(np.uint8), np.ones((15, 15), np.uint8)).astype(bool)
    if outside.any():
        record["backdrop_lab"] = [round(float(v), 1) for v in np.median(np.stack([L[outside], A[outside], B[outside]],
                                                                                   1), axis=0)]
    return record, label_img


def read_map(image_bytes: bytes) -> dict:
    """``container_design_map/1.0``'s local half for a concept picture: READ with the product's light, colours and
    regions, or UNREAD with the reason by name (no picture; no one standing product the trace confirms)."""
    from apps.pipeline.services import concept_outline as co
    rec = {"schema_version": SCHEMA, "params": dict(MAP_PARAMS),
           "source_sha256": hashlib.sha256(image_bytes).hexdigest() if image_bytes else None}
    got = co.standing_pixels(image_bytes)
    if got is None:
        return {**rec, "state": MAP_UNREAD, "reason": MAP_NO_PRODUCT,
                "detail": "the trace confirms no one standing product in the picture"}
    img, mask, read = got
    body, _labels = read_pixels(img, mask)
    return {**rec, "state": MAP_READ, "turned_deg": read["turned_deg"], **body}


def overlay_png(image_bytes: bytes, record: dict | None = None) -> bytes | None:
    """The map as a picture for a person to check, PNG bytes: the product as the picture shows it, beside its map —
    each measured colour painted flat, the shine in cyan, the edge fall-off in grey, the ground dark — and a legend of
    the colours, their hexes and shares; with a ``record`` of ``read_parts``, every part it names outlined on the
    product with its number, and listed with its kind, its name and its colour. None where the map is unread."""
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw
    from apps.pipeline.services import concept_outline as co
    got = co.standing_pixels(image_bytes)
    if got is None:
        return None
    img, mask = got[0], got[1]
    body, labels = read_pixels(img, mask)
    lit = light(img, mask)
    flat = np.full(img.shape, 40, np.uint8)
    for n, c in enumerate(body["colours"]):
        h = c["hex"]
        flat[labels == n] = (int(h[5:7], 16), int(h[3:5], 16), int(h[1:3], 16))
    flat[lit["edge"]] = (110, 110, 110)
    flat[lit["shine"]] = (255, 255, 0)
    x0, y0, x1, y1 = body["product_box_px"]
    pad = 12
    crop = (max(0, x0 - pad), max(0, y0 - pad), min(img.shape[1], x1 + pad), min(img.shape[0], y1 + pad))
    left = cv2.cvtColor(img[crop[1]:crop[3], crop[0]:crop[2]], cv2.COLOR_BGR2RGB)
    right = cv2.cvtColor(flat[crop[1]:crop[3], crop[0]:crop[2]], cv2.COLOR_BGR2RGB)
    h, w = left.shape[:2]
    legend_w = 260
    sheet = Image.new("RGB", (2 * w + legend_w + 30, max(h, 40 + 22 * len(body["colours"]))), (250, 248, 246))
    sheet.paste(Image.fromarray(left), (0, 0))
    sheet.paste(Image.fromarray(right), (w + 10, 0))
    d = ImageDraw.Draw(sheet)
    parts = record["parts"] if record is not None and record.get("parts") else []
    px0, py0, px1, py1 = body["product_box_px"]
    for i, part in enumerate(parts):
        bx0, by0, bx1, by1 = part["box"]
        box = (px0 - crop[0] + bx0 * (px1 - px0), py0 - crop[1] + by0 * (py1 - py0),
               px0 - crop[0] + bx1 * (px1 - px0), py0 - crop[1] + by1 * (py1 - py0))
        d.rectangle(box, outline=(0, 200, 90), width=2)
        d.text((box[0] + 2, box[1] + 1), str(i + 1), fill=(0, 120, 50))
    if parts:
        sheet2 = Image.new("RGB", (sheet.width + 420, max(sheet.height, 40 + 20 * len(parts))), (250, 248, 246))
        sheet2.paste(sheet, (0, 0))
        sheet, d = sheet2, ImageDraw.Draw(sheet2)
        tx = sheet.width - 410
        d.text((tx, 8), "parts the read names, their colours from the map", fill=(40, 40, 40))
        for i, part in enumerate(parts):
            y = 30 + 20 * i
            if part.get("colour"):
                d.rectangle((tx, y, tx + 14, y + 14), fill=part["colour"], outline=(60, 60, 60))
            label = "%d  %s - %s  %s" % (i + 1, part["kind"], part["name"], part["colour"] if part.get("colour") else "no colour")
            if part.get("second_colour"):
                label += " + " + part["second_colour"]
            if part.get("count"):
                label += "  x%d" % part["count"]
            d.text((tx + 22, y + 1), label[:62], fill=(40, 40, 40))
    lx = 2 * w + 25
    d.text((lx, 8), "colours, largest first", fill=(40, 40, 40))
    for i, c in enumerate(body["colours"]):
        y = 30 + 22 * i
        d.rectangle((lx, y, lx + 16, y + 16), fill=c["hex"], outline=(60, 60, 60))
        d.text((lx + 24, y + 2), "%s  %.1f %%" % (c["hex"], 100 * c["share"]), fill=(40, 40, 40))
    y = 40 + 22 * len(body["colours"])
    for label, colour in (("shine, left out", (0, 255, 255)), ("edge fall-off, left out", (110, 110, 110)),
                          ("ground, left out", (40, 40, 40))):
        d.rectangle((lx, y, lx + 16, y + 16), fill=colour, outline=(60, 60, 60))
        d.text((lx + 24, y + 2), label, fill=(40, 40, 40))
        y += 22
    buf = io.BytesIO()
    sheet.save(buf, "PNG")
    return buf.getvalue()


# --- THE READ: the map's paid half — each part named, its colour and box taken from the map ------------------------------

PARTS_PROMPT_VERSION = "3"
PARTS_OPERATION = "container_design_map_parts"
PARTS_GRID_PX = 50
#: the standing product is shown to the model at this many times the trace's scale, so its small print is legible
PARTS_UPSCALE = 2
PART_KINDS = ("field", "band", "closure", "mark", "type", "rule", "motif", "window")
#: the kinds whose colour is the ground they cover; every other kind is ink on a ground
SURFACE_KINDS = ("field", "band", "closure", "window")
LIGHT_KINDS = ("shine", "shadow", "reflection", "background")
PARTS_UNREAD = "DESIGN_MAP_PARTS_UNREAD"

#: [His goal after the pitch page, 2026-10-15 (OWNER_BLOCKER_CLEARANCE.md), A (1): "TYPOGRAPHY: every drawing falls back
#: to a plain sans. Classify the concept's lettering (serif / sans / script / condensed / display, weight, letter-spacing,
#: case, colour) and set each line in the closest granted face with the same weight, spacing, size and colour."] every
#: line of type is read for its lettering's style as well as its words — what the drawing sets it in
#: (``ire.lettering_faces``); every read names the same seven things
TYPE_STYLE_CLASSES = ("serif", "sans", "script", "condensed", "display")
TYPE_STYLE_SERIFS = ("high-contrast", "old-style", "transitional", "slab", "flared", "none")
TYPE_STYLE_WEIGHTS = ("thin", "light", "regular", "medium", "semibold", "bold", "black")
TYPE_STYLE_WIDTHS = ("condensed", "normal", "wide")
TYPE_STYLE_CASES = ("upper", "lower", "mixed", "small-caps")
TYPE_STYLE_SPACINGS = ("tight", "normal", "wide", "very wide")
TYPE_STYLE_WORDS = """For every "type" part also give "style", its lettering as a typographer would name it, so it can be
set in the closest face: {"class": "serif" | "sans" | "script" | "condensed" | "display", "serif": "high-contrast" (a
fashion didone, thin hairlines) | "old-style" (a soft garamond) | "transitional" | "slab" | "flared" (a glyphic,
chiselled roman) | "none", "weight": "thin" | "light" | "regular" | "medium" | "semibold" | "bold" | "black", "italic":
true | false, "width": "condensed" | "normal" | "wide", "case": "upper" | "lower" | "mixed" | "small-caps", "spacing":
"tight" | "normal" | "wide" | "very wide" (how far apart its letters stand)}. Look closely at each line: serifs, stroke
contrast and weight are the design; never call a serif line sans.

For the ground ("field") and every "illustration", "band" and "motif" part also give "texture": "grain" (a fine printed
grain or sand-like noise over its colour), "speckle" (visible dots or flecks) or "none" (clean flat or smooth colour) —
the print's own texture, never the photograph's."""
#: [his review of 127-132, 2026-10-15, C (5): "keep the concept's detail: 131's sky grain"] the print's texture a part is
#: read with (``TYPE_STYLE_WORDS``), drawn as a fine vector stipple measured from the concept (``ire.grain``)
TEXTURES = ("grain", "speckle", "none")


PARTS_SYSTEM = """You read a photographic CONCEPT render of ONE cosmetics product, cut out and standing, and name the
parts of the DESIGN printed or moulded on it — each part and each motif — so that the design can be drawn exactly as the
picture shows it. You measure what the picture shows; you invent nothing and you do not design.

THE LIGHT IS NOT DESIGN. Glossy streaks and highlights, shadows and shading, reflections and the background are the
photograph, not the design: never name them as parts; list them under "light" instead.

The picture is drawn over with a PIXEL GRID: blue vertical lines every 50 px (labelled every 100 px along the top),
orange horizontal lines every 50 px (labelled every 100 px down the left). Read EVERY coordinate AGAINST THE GRID
LINES — never guess. Every box is [x0, y0, x1, y1] in PIXELS of the picture, x right, y down, tight around the part.

Parts — use exactly these kinds:
  "field"    a large area of one printed colour on the body (e.g. the upper colour of a two-tone body)
  "band"     a stripe or band across the body (e.g. a band of drips)
  "closure"  the cap, lid, pump or other closure, as one part
  "mark"     the brand wordmark or lockup (e.g. BBROSE)
  "type"     any other printed text: one part per line or block — give the exact words you see as "seen_text", and
             the lettering as "lettering": "script" | "serif" | "sans" | "display" | "arabic"
  "rule"     a thin line (e.g. a gold line framing a band)
  "motif"    a drawn decoration (drips, sparkles, petals, stars): one part per kind of motif, its whole extent, with
             "count": how many of it you see
  "window"   a framed panel or cartouche
For each part: "kind", "name" (a few plain words: "hot pink upper field", "cream drip band", "script product name"),
"box", "count" (motifs only), "seen_text" (type and mark only), "lettering" and "style" (type only), "finish" (e.g.
"gold foil", "gloss", "none"), "confidence" 0..1.
""" + TYPE_STYLE_WORDS + """

"light": each light area — {"kind": "shine" | "shadow" | "reflection" | "background", "box": [x0, y0, x1, y1]}.
"notes": one short line.

Respond ONLY with valid JSON:
{"parts": [{"kind": "...", "name": "...", "box": [x0,y0,x1,y1], "count": 0, "seen_text": "...", "lettering": "...",
            "style": {"class": "...", "serif": "...", "weight": "...", "italic": false, "width": "...", "case": "...",
                      "spacing": "..."}, "texture": "...", "finish": "...", "confidence": 0.0}],
 "light": [{"kind": "...", "box": [x0,y0,x1,y1]}], "notes": "..."}"""


def _parts_picture(img, body) -> tuple[bytes, tuple[int, int], tuple[int, int]]:
    """The standing product for the model to read — PNG bytes of its crop, upscaled PARTS_UPSCALE times, with the pixel
    grid drawn over it; returns (the bytes, the crop's (x0, y0) in the map's pixels, the copy's (w, h))."""
    import cv2
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = body["product_box_px"]
    pad = 10
    cx0, cy0 = max(0, x0 - pad), max(0, y0 - pad)
    cx1, cy1 = min(img.shape[1], x1 + pad), min(img.shape[0], y1 + pad)
    crop = cv2.cvtColor(img[cy0:cy1, cx0:cx1], cv2.COLOR_BGR2RGB)
    up = cv2.resize(crop, None, fx=PARTS_UPSCALE, fy=PARTS_UPSCALE, interpolation=cv2.INTER_CUBIC)
    pic = Image.fromarray(up)
    w, h = pic.size
    d = ImageDraw.Draw(pic)
    for x in range(0, w, PARTS_GRID_PX):
        d.line([(x, 0), (x, h)], fill=(0, 140, 255) if x % (2 * PARTS_GRID_PX) == 0 else (120, 200, 255), width=1)
        if x % (2 * PARTS_GRID_PX) == 0:
            d.text((x + 2, 2), str(x), fill=(0, 60, 200))
    for y in range(0, h, PARTS_GRID_PX):
        d.line([(0, y), (w, y)], fill=(255, 120, 0) if y % (2 * PARTS_GRID_PX) == 0 else (255, 200, 140), width=1)
        if y % (2 * PARTS_GRID_PX) == 0:
            d.text((2, y + 2), str(y), fill=(200, 60, 0))
    buf = io.BytesIO()
    pic.save(buf, "PNG")
    return buf.getvalue(), (cx0, cy0), (w, h)


def _map_box(box, origin, size) -> list[int] | None:
    """A box the model read on the upscaled crop, in the map's own pixels; None where it is not a box inside the
    crop."""
    try:
        x0, y0, x1, y1 = (float(v) for v in box)
    except (TypeError, ValueError):
        return None
    w, h = size
    if not (0.0 <= x0 < x1 <= w and 0.0 <= y0 < y1 <= h):
        return None
    ox, oy = origin
    return [int(round(ox + x0 / PARTS_UPSCALE)), int(round(oy + y0 / PARTS_UPSCALE)),
            int(round(ox + x1 / PARTS_UPSCALE)), int(round(oy + y1 / PARTS_UPSCALE))]


def _one_colour_under_two_lights(a_lab, b_lab) -> bool:
    """Two measured colours are one printed colour lit two ways: light and shade keep a colour's HUE and scale its
    chroma, so their hues within MAP_PARAMS["shade_hue_deg"] and their chromas within MAP_PARAMS["shade_chroma"] of
    each other, whatever their lightness. Measured on 117: the soft pink and the soft pink in shade (5.6°, 1.5), the
    hot pink and the cap at the base (6.8°, 0.9) are one colour each; the hot pink and the soft pink (a ratio of 0.3),
    the gold and the brown type (21.6°) are two."""
    ca, cb = math.hypot(a_lab[1], a_lab[2]), math.hypot(b_lab[1], b_lab[2])
    if min(ca, cb) <= 0.0:
        return False
    turn = abs(math.degrees(math.atan2(a_lab[2], a_lab[1]) - math.atan2(b_lab[2], b_lab[1]))) % 360.0
    return (min(turn, 360.0 - turn) <= MAP_PARAMS["shade_hue_deg"]
            and max(ca, cb) / min(ca, cb) <= MAP_PARAMS["shade_chroma"])


def _colour_parts(parts: list, labels, body, shade, flat: bool = False) -> None:
    """Every part's colour from the map, in place (``part["_px"]``: its box in the map's pixels) — the SURFACES first
    (field, band, closure, window: the colour most of its middle two-fifths holds, the named light left out), then the
    INKS (mark, type, rule, motif): the colours its box holds that are not its ground (the colour most of a band
    around it holds), not the colour of any surface its box overlaps or touches, and not either of those under
    another light (``_one_colour_under_two_lights``: the same hue, its chroma scaled) — the most of them its colour, and the next its second colour
    where it holds at least MAP_PARAMS["second_ink"] of the first (a gold contour round a cream fill).
    [The owner's finding on design 119, 2026-10-03 (transcribed at 32898c7).] ``flat``: a carton's front panel, a flat
    printed face pictured square to the camera and lit one way — a surface's colour is the one most of its box holds
    CLEAR OF every other part's box [the clean-up's wiring check, 2026-10-04 (W3): every part printed ON it — never
    the ground whose box holds it whole] (119's middle two-fifths is the berry silhouette printed on its cream: measured, the
    middle read #56111B, the panel clear of its parts #F1D2C0), and no colour is taken for another under a second light
    (a pale pink name on a deep berry of its own hue is two inks: 7.6° apart on the synthetic panel, 9.1° on 119)."""
    import numpy as np
    colours = body["colours"]
    n = len(colours)
    labs = [c["lab"] for c in colours]
    surfaces = []
    for part in parts:
        if part["kind"] not in SURFACE_KINDS:
            continue
        x0, y0, x1, y1 = part["_px"]
        w = x1 - x0
        cut = (slice(y0, y1), slice(x0 + int(0.3 * w), x1 - int(0.3 * w)))
        sub = labels[cut]
        keep = sub[(sub >= 0) & ~shade[cut]]
        # [His review of 127, 130, 131 and 132, 2026-10-15, C (3): "130's jar ..."] a standing product's surface is
        # never read on another surface its box holds: 130's body field's middle two-fifths is all its cobalt oval
        # window, so its matte white body was read navy. Clear of every surface inside it — its middle, else the whole
        # of its box (MAP_PARAMS["surface_clear_least"])
        held = [o["_px"] for o in parts if o is not part and o["kind"] in SURFACE_KINDS
                and o["_px"][0] >= x0 and o["_px"][1] >= y0 and o["_px"][2] <= x1 and o["_px"][3] <= y1
                and o["_px"] != part["_px"]]
        if held and not flat:
            clear = np.ones((y1 - y0, x1 - x0), bool)
            for ox0, oy0, ox1, oy1 in held:
                clear[oy0 - y0:oy1 - y0, ox0 - x0:ox1 - x0] = False
            whole = labels[y0:y1, x0:x1]
            open_ = (whole >= 0) & ~shade[y0:y1, x0:x1] & clear
            middle = np.zeros(open_.shape, bool)
            middle[:, int(0.3 * w):w - int(0.3 * w)] = True
            if (open_ & middle).sum() >= MAP_PARAMS["surface_clear_least"] * max(1, keep.size):
                keep = whole[open_ & middle]
            elif open_.any():
                keep = whole[open_]
        if flat:
            free = np.ones((y1 - y0, x1 - x0), bool)
            for other in parts:
                ox0, oy0, ox1, oy1 = other["_px"]
                # [the clean-up's wiring check, 2026-10-04, its finding W3] clear of the parts printed ON it — never of
                # a part whose box holds it whole, the ground it is printed on (the ground's box is the whole panel)
                beneath = ox0 <= x0 and oy0 <= y0 and ox1 >= x1 and oy1 >= y1
                if other is not part and not beneath:
                    free[max(0, oy0 - y0):max(0, oy1 - y0), max(0, ox0 - x0):max(0, ox1 - x0)] = False
            sub = labels[y0:y1, x0:x1]
            keep = sub[(sub >= 0) & ~shade[y0:y1, x0:x1] & free]
        if keep.size and body.get("backdrop_lab") is not None:
            # never the backdrop's colour where the product's own colours are there to read
            ground = np.array(body["backdrop_lab"], dtype=float)
            behind = [c for c in range(n) if float(np.linalg.norm(np.array(labs[c], dtype=float) - ground))
                      < MAP_PARAMS["backdrop_de"]]
            mine = keep[~np.isin(keep, behind)] if behind else keep
            if mine.size >= MAP_PARAMS["backdrop_least"] * keep.size:
                keep = mine
        if keep.size == 0:
            part.update(colour=None, colour_from="no measured pixel in its middle")
            continue
        k = int(np.bincount(keep, minlength=n).argmax())
        part.update(colour=colours[k]["hex"], colour_from=(
            "the map colour most of its evenly lit box holds clear of every other part" if flat
            else "the map colour most of its evenly lit middle holds"))
        surfaces.append((part["_px"], k))
    for part in parts:
        if part["kind"] in SURFACE_KINDS:
            continue
        x0, y0, x1, y1 = part["_px"]
        sub = labels[y0:y1, x0:x1]
        keep = sub[(sub >= 0) & ~shade[y0:y1, x0:x1]]
        if keep.size == 0:
            part.update(colour=None, colour_from="no measured pixel in its box")
            continue
        pad = max(3, int(0.15 * min(x1 - x0, y1 - y0)))
        ry0, rx0 = max(0, y0 - pad), max(0, x0 - pad)
        ring = labels[ry0:y1 + pad, rx0:x1 + pad].copy()
        ring[y0 - ry0:y1 - ry0, x0 - rx0:x1 - rx0] = -1
        ring = ring[ring >= 0]
        out = {int(np.bincount(ring, minlength=n).argmax())} if ring.size else set()
        out |= {k for (sx0, sy0, sx1, sy1), k in surfaces if sx0 <= x1 and x0 <= sx1 and sy0 <= y1 and y0 <= sy1}
        counts = np.bincount(keep, minlength=n).astype(float)
        for c in range(n):
            if c in out or (not flat and any(_one_colour_under_two_lights(labs[c], labs[e]) for e in out)):
                counts[c] = 0.0
        if counts.sum() == 0:
            part.update(colour=None, colour_from="its box holds only its ground's colours")
            continue
        order = [int(c) for c in np.argsort(-counts)]
        part.update(colour=colours[order[0]]["hex"],
                    colour_from=("its ink: the map colour most of its box holds that is neither its ground, nor a "
                                 "surface it lies on, nor either under another light"))
        if len(order) > 1 and counts[order[1]] > 0 and counts[order[1]] >= MAP_PARAMS["second_ink"] * counts[order[0]]:
            part["second_colour"] = colours[order[1]]["hex"]


def recolour(image_bytes: bytes, record: dict) -> dict:
    """A map on record coloured again from its picture, with no new read: the local half measured afresh under
    MAP_PARAMS as they stand, and every part the record names coloured from it (``_colour_parts``) at the box the record
    holds; the light the read named kept. The record's read — its parts, their names and boxes, its cost — is as it
    was."""
    import numpy as np
    from apps.pipeline.services import concept_outline as co
    # [the owner's finding on design 119, 2026-10-03] a carton's map, measured again on the front panel its read named
    got = _face_pixels(image_bytes, record) if record.get("face_box_px") else co.standing_pixels(image_bytes)
    if got is None or record.get("state") != MAP_READ:
        return record
    img, mask, _read = got
    body, labels = read_pixels(img, mask)
    px0, py0, px1, py1 = body["product_box_px"]
    pw, ph = float(px1 - px0), float(py1 - py0)

    def px(box):
        return [int(round(px0 + box[0] * pw)), int(round(py0 + box[1] * ph)), int(round(px0 + box[2] * pw)),
                int(round(py0 + box[3] * ph))]
    shade = np.zeros(mask.shape, bool)
    for item in record.get("light_named") or []:
        x0, y0, x1, y1 = px(item["box"])
        shade[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = True
    parts = []
    for part in record.get("parts") or []:
        x0, y0, x1, y1 = px(part["box"])
        clean = {k: v for k, v in part.items() if k not in ("colour", "second_colour", "colour_from")}
        parts.append(dict(clean, _px=[max(0, x0), max(0, y0), min(mask.shape[1], x1), min(mask.shape[0], y1)]))
    _colour_parts(parts, labels, body, shade, flat=bool(record.get("face_box_px")))
    for part in parts:
        part.pop("_px")
    return dict(record, params=dict(MAP_PARAMS), light=body["light"], product_box_px=body["product_box_px"],
                colours=body["colours"], parts=parts)


def read_parts(task, image_bytes: bytes, *, structured: dict | None = None, call=None) -> dict:
    """``container_design_map/1.0`` WHOLE: the local half (``read_map``) and each part of the design the read names —
    its kind and name, its box as fractions of the product, its colour taken from the map (never from the concept's
    words), its count, the words and the lettering it carries — the light the read names beside the light measured, and
    the read's cost from the ledger's own price table. One vision call; ``call`` stands in for
    ``claude_service.call_claude`` (tests). A read that fails is its own state, the local half kept."""
    import numpy as np
    from django.conf import settings
    from apps.pipeline.services import concept_outline as co
    model = settings.CLAUDE_MODEL_HEAVY
    rec = read_map(image_bytes)
    rec.update(parts_prompt_version=PARTS_PROMPT_VERSION, model=model, parts=[], light_named=[], light_beside=[],
               problems=[], cost={"usd": "0.000000", "input_tokens": 0, "output_tokens": 0, "calls": 0})
    if rec["state"] != MAP_READ:
        return rec
    img, mask, _read = co.standing_pixels(image_bytes)
    body, labels = read_pixels(img, mask)
    picture, origin, size = _parts_picture(img, body)
    from apps.pipeline.services import claude_service as cs
    from apps.pipeline.services.cost_ledger import BudgetExceededError, claude_cost_usd, task_cost_context
    words = "\n".join("%s: %s" % (k, (structured or {}).get(k)) for k in (
        "motif_signature", "color_field_signature", "composition_signature", "decoration_zone_signature",
        "typography_signature", "cap_body_signature") if (structured or {}).get(k))
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                            "data": __import__("base64").b64encode(picture).decode()}},
               {"type": "text", "text": ("THE PICTURE is %d x %d pixels.\n\nThe concept's own words, for naming what "
                                         "you see (never for placing it — place only what the picture shows):\n%s\n\n"
                                         "Return the JSON now." % (size[0], size[1], words))}]
    try:
        with task_cost_context(task):
            response = (call or cs.call_claude)(PARTS_SYSTEM, content, max_tokens=3000, model=model,
                                                operation=PARTS_OPERATION)
        tin, tout = int(response.usage.input_tokens), int(response.usage.output_tokens)
    except BudgetExceededError:
        raise                     # [his go of 2026-10-02] a spending cap stops the read, as it stops every paid step
    except Exception as exc:  # noqa: BLE001 — the record says what failed; the local half stands
        rec["problems"].append("%s: the read raised %s: %s" % (PARTS_UNREAD, type(exc).__name__, str(exc)[:200]))
        return rec
    rec["cost"] = {"usd": str(claude_cost_usd(model, tin, tout)), "input_tokens": tin, "output_tokens": tout,
                   "calls": 1, "source": "cost_ledger.claude_cost_usd — the ledger's own price table"}
    try:
        payload = cs.loads_tolerant(cs.extract_text(response))
    except Exception as exc:  # noqa: BLE001
        rec["problems"].append("%s: the answer did not parse (%s)" % (PARTS_UNREAD, str(exc)[:160]))
        return rec
    shade = np.zeros(mask.shape, bool)
    for item in (payload.get("light") if isinstance(payload, dict) else None) or []:
        box = _map_box((item or {}).get("box"), origin, size) if isinstance(item, dict) else None
        if box is None or item.get("kind") not in LIGHT_KINDS:
            continue
        # [his test blocker on design 122, 2026-10-07, item 5] the background is never the product's own light, as a
        # carton's is not (carton_record): the trace's mask already holds the ground out, and a box cannot say "around"
        # — on 122's concept 149 the read named the background by a box over the whole picture, the shade hid every
        # pixel of the tube, and all nine of its parts were read with no colour
        if item["kind"] == "background":
            rec["light_beside"].append({"kind": item["kind"], "box": _fractions(box, body),
                                        "why": "the ground around the product: not applied to its colours"})
            continue
        shade[box[1]:box[3], box[0]:box[2]] = True
        rec["light_named"].append({"kind": item["kind"], "box": _fractions(box, body)})
    for item in (payload.get("parts") if isinstance(payload, dict) else None) or []:
        if not isinstance(item, dict) or item.get("kind") not in PART_KINDS:
            rec["problems"].append("a part of no declared kind was left out: %r" % (item,)[:120])
            continue
        box = _map_box(item.get("box"), origin, size)
        if box is None:
            rec["problems"].append("%s %r carries no box inside the picture" % (item["kind"], item.get("name")))
            continue
        part = {"kind": item["kind"], "name": str(item.get("name") or item["kind"])[:80], "box": _fractions(box, body),
                "_px": box}
        if item["kind"] == "motif" and isinstance(item.get("count"), int):
            part["count"] = item["count"]
        if item["kind"] in ("type", "mark") and item.get("seen_text"):
            part["seen_text"] = str(item["seen_text"])[:200]
        if item["kind"] == "type" and item.get("lettering"):
            part["lettering"] = str(item["lettering"])[:20]
        if item["kind"] == "type" and type_style(item):
            part["style"] = type_style(item)            # [his goal after the pitch page, A (1)]
        if str(item["texture"] if "texture" in item else "").lower() in TEXTURES:
            part["texture"] = str(item["texture"]).lower()     # [his review of 127-132, C (5)]
        if item.get("finish"):
            part["finish"] = str(item["finish"])[:40]
        rec["parts"].append(part)
    _colour_parts(rec["parts"], labels, body, shade)
    for part in rec["parts"]:
        part.pop("_px")
    if not rec["parts"]:
        rec["problems"].append("%s: the read named no part" % PARTS_UNREAD)
    return rec


def held_parts(held: dict | None, image_bytes: bytes) -> dict | None:
    """[His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): "build the map path to run on its own
    for every new design".] ``held`` — a map on record — when it READ the parts of THIS picture under THIS prompt and
    model and named at least one; else None, and a new read is the only way to one. Pure; nothing paid."""
    return _held(held, image_bytes, PARTS_PROMPT_VERSION)


def _held(held: dict | None, image_bytes: bytes, version: str) -> dict | None:
    """``held`` where it READ the parts of THIS picture under the prompt ``version`` and this model and named at least
    one part; else None."""
    from django.conf import settings
    if not held or not image_bytes:
        return None
    if (held.get("state") != MAP_READ or held.get("source_sha256") != hashlib.sha256(image_bytes).hexdigest()
            or held.get("parts_prompt_version") not in (version,) + EARLIER_READS_HELD[version]
            or held.get("model") != settings.CLAUDE_MODEL_HEAVY
            or not held.get("parts")):
        return None
    return held


#: [His goal after the pitch page, A (1)] a read made under the prompt before its lines' style was asked names the same
#: parts in the same words: it is held as it stands, never paid for again — only its lines' style is unread, and they
#: keep the face they had (``ire.lettering_faces.choose``); a design that wants its style read is read afresh
EARLIER_READS_HELD = {PARTS_PROMPT_VERSION: ("1", "2"), "carton-3": ("carton-1", "carton-2"), "lid-3": ("lid-1", "lid-2")}


def type_style(item) -> dict:
    """[His goal after the pitch page, A (1)] a type part's "style" as its read gives it — only the words the read may use
    (``TYPE_STYLE_WORDS``), each kept where it is one of them; {} where the read gave none."""
    given = item.get("style") if isinstance(item, dict) else None
    if not isinstance(given, dict):
        return {}
    out = {}
    for key, allowed in (("class", TYPE_STYLE_CLASSES), ("serif", TYPE_STYLE_SERIFS), ("weight", TYPE_STYLE_WEIGHTS),
                         ("width", TYPE_STYLE_WIDTHS), ("case", TYPE_STYLE_CASES), ("spacing", TYPE_STYLE_SPACINGS)):
        word = str(given[key]).strip().lower() if key in given else ""
        if word in allowed:
            out[key] = word
    if isinstance(given.get("italic"), bool):
        out["italic"] = given["italic"]
    return out


def _fractions(box, body) -> list[float]:
    """A box in the map's pixels as fractions of the product's own box."""
    px0, py0, px1, py1 = body["product_box_px"]
    pw, ph = float(px1 - px0), float(py1 - py0)
    x0, y0, x1, y1 = box
    return [round((x0 - px0) / pw, 4), round((y0 - py0) / ph, 4), round((x1 - px0) / pw, 4),
            round((y1 - py0) / ph, 4)]


# --- THE CARTON'S READ: a carton's FRONT PANEL, named by the read itself --------------------------------------------------
# [The owner's finding on design 119, 2026-10-03 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 32898c7): "DESIGN 119 IS
# BROKEN WIRING ... nothing of my concept (silhouette, "Rose Glaze"); no vectors".] The map cuts ONE standing product from
# its ground (``concept_outline.standing_pixels``). On 119 the cream carton stood on a cream ground, and the cut took the
# berry vial silhouette PRINTED on the carton for the product — no part the read named then held a colour, and the front
# was ruled. A carton's front is a flat printed panel: its read names the panel itself ("face") beside the parts printed
# on it, and the panel's own pixels are measured.

CARTON_READ = "carton front panel"
CARTON_PARTS_PROMPT_VERSION = "carton-3"
CARTON_PART_KINDS = ("field", "shape", "band", "mark", "type", "rule", "motif", "window")
#: the light the read names that is left out of the panel's colours: a carton's front is pictured square to the camera
#: (``targets.packaging.CARTON_MAP_DIRECTIVE``); the background is never the panel, and a shadow the read names is the
#: carton's own cast on its ground — 119's ran over the panel's foot line, where the picture shows none — so each is said
#: beside the map and not applied
CARTON_FACE_LIGHT = ("shine", "reflection")
CARTON_NO_FACE = "DESIGN_MAP_NO_FACE"
#: type the picture prints turned: 0 reads left to right, 90 bottom to top, -90 top to bottom
TYPE_ROTATIONS = (0, 90, -90)

CARTON_PARTS_SYSTEM = """You read a photographic CONCEPT render of a folding CARTON (a box) and name the parts of the DESIGN
printed on its FRONT PANEL, so that the panel can be drawn exactly as the picture shows it. You measure what the picture
shows; you invent nothing and you do not design.

FIRST, THE FRONT PANEL: "face" is the box [x0, y0, x1, y1] of the carton's FRONT PANEL ONLY — the large face square to
the camera, the one that carries the name. Never its sides, its top, its flaps, its shadow, or anything beside or in
front of the carton (flowers, petals, the product, a stand, the floor).

THE LIGHT IS NOT DESIGN. Glossy streaks and highlights, shadows and shading, reflections and the background are the
photograph, not the design: never name them as parts; list them under "light" instead.

The picture is drawn over with a PIXEL GRID: blue vertical lines every 50 px (labelled every 100 px along the top),
orange horizontal lines every 50 px (labelled every 100 px down the left). Read EVERY coordinate AGAINST THE GRID
LINES — never guess. Every box is [x0, y0, x1, y1] in PIXELS of the picture, x right, y down, tight around the part.

Parts of the FRONT PANEL's design — use exactly these kinds, every box inside "face":
  "field"    the panel's ground colour, or a large area of one printed colour on it (one part each)
  "shape"    a solid printed graphic in one colour — a silhouette, a big flat shape (e.g. "deep berry vial silhouette")
  "band"     a stripe or band across the panel
  "mark"     the brand wordmark or lockup (e.g. BBROSE)
  "type"     any other printed text: one part per line or block — give the exact words you see as "seen_text", the
             lettering as "lettering": "script" | "serif" | "sans" | "display" | "arabic", and "rotation": 0 when it
             reads left to right, 90 when it reads bottom to top, -90 when it reads top to bottom
  "rule"     a thin line
  "motif"    a drawn decoration repeated (dots, sparkles, petals, stars): one part per kind, its whole extent, "count"
  "window"   a framed panel or cartouche
For each part: "kind", "name" (a few plain words), "box", "count" (motifs only), "seen_text" (type and mark only),
"lettering", "style" and "rotation" (type only), "finish" (e.g. "gold foil", "gloss", "none"), "confidence" 0..1.
""" + TYPE_STYLE_WORDS + """

"light": each light area — {"kind": "shine" | "shadow" | "reflection" | "background", "box": [x0, y0, x1, y1]}.
"notes": one short line.

Respond ONLY with valid JSON:
{"face": [x0,y0,x1,y1],
 "parts": [{"kind": "...", "name": "...", "box": [x0,y0,x1,y1], "count": 0, "seen_text": "...", "lettering": "...",
            "style": {"class": "...", "serif": "...", "weight": "...", "italic": false, "width": "...", "case": "...",
                      "spacing": "..."}, "rotation": 0, "texture": "...", "finish": "...", "confidence": 0.0}],
 "light": [{"kind": "...", "box": [x0,y0,x1,y1]}], "notes": "..."}"""


def _face_pixels(image_bytes: bytes, record: dict):
    """``(the picture at the map's scale, its front panel's mask, None)`` for a carton's map — the panel its read named
    (``face_box_px``); None where the picture does not open."""
    import numpy as np

    from apps.pipeline.services import concept_outline as co
    img, _s = co._read(image_bytes)
    if img is None:
        return None
    x0, y0, x1, y1 = record["face_box_px"]
    mask = np.zeros(img.shape[:2], np.uint8)
    mask[y0:y1, x0:x1] = 1
    return img, mask, None


def _carton_unread(image_bytes: bytes, model: str, cost: dict, reason: str, detail: str, *, read: str = CARTON_READ,
                   version: str = CARTON_PARTS_PROMPT_VERSION) -> dict:
    """A carton's map that did not read, by name, with what its read cost — [his test blocker on design 124, (2)] or a
    compact lid's (``read``, ``version``)."""
    return {"schema_version": SCHEMA, "read": read, "parts_prompt_version": version,
            "model": model, "source_sha256": hashlib.sha256(image_bytes).hexdigest() if image_bytes else None,
            "state": MAP_UNREAD, "reason": reason, "detail": detail, "parts": [], "light_named": [], "problems": [],
            "cost": cost}


def read_carton_parts(task, image_bytes: bytes, *, call=None) -> dict:
    """[The owner's finding on design 119, 2026-10-03.] ``container_design_map/1.0`` of a CARTON's concept, read by its
    front panel: one vision call (``CARTON_PARTS_SYSTEM``) on the whole picture at the map's scale, upscaled
    PARTS_UPSCALE times under the parts read's own grid, names the front panel and each part printed on it; the panel's
    own pixels then give each part its colour (``carton_record``). The read's cost from the ledger's own price table, on
    this design's ledger. ``call`` stands in for ``claude_service.call_claude`` (tests). A spending cap stops the read,
    as it stops every paid step; a read that fails is UNREAD, by name."""
    import base64

    from django.conf import settings

    from apps.pipeline.services import claude_service as cs
    from apps.pipeline.services import concept_outline as co
    from apps.pipeline.services.cost_ledger import BudgetExceededError, claude_cost_usd, task_cost_context
    model = settings.CLAUDE_MODEL_HEAVY
    nothing = {"usd": "0.000000", "input_tokens": 0, "output_tokens": 0, "calls": 0}
    img, _s = co._read(image_bytes)
    if img is None:
        return _carton_unread(image_bytes, model, nothing, CARTON_NO_FACE, "the picture could not be opened")
    picture, _origin, size = _parts_picture(img, {"product_box_px": [0, 0, img.shape[1], img.shape[0]]})
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                            "data": base64.b64encode(picture).decode()}},
               {"type": "text", "text": "THE PICTURE is %d x %d pixels.\n\nReturn the JSON now." % size}]
    try:
        with task_cost_context(task):
            response = (call or cs.call_claude)(CARTON_PARTS_SYSTEM, content, max_tokens=3000, model=model,
                                                operation=PARTS_OPERATION)
        tin, tout = int(response.usage.input_tokens), int(response.usage.output_tokens)
    except BudgetExceededError:
        raise
    except Exception as exc:  # noqa: BLE001 — the record says what failed
        return _carton_unread(image_bytes, model, nothing, PARTS_UNREAD,
                              "the read raised %s: %s" % (type(exc).__name__, str(exc)[:200]))
    cost = {"usd": str(claude_cost_usd(model, tin, tout)), "input_tokens": tin, "output_tokens": tout, "calls": 1,
            "source": "cost_ledger.claude_cost_usd — the ledger's own price table"}
    try:
        payload = cs.loads_tolerant(cs.extract_text(response))
    except Exception as exc:  # noqa: BLE001
        return _carton_unread(image_bytes, model, cost, PARTS_UNREAD, "the answer did not parse (%s)" % str(exc)[:160])
    return carton_record(image_bytes, payload, model=model, cost=cost)


def carton_record(image_bytes: bytes, payload, *, model: str, cost: dict, read: str = CARTON_READ,
                  version: str = CARTON_PARTS_PROMPT_VERSION, kinds: tuple = CARTON_PART_KINDS) -> dict:
    """[The owner's finding on design 119, 2026-10-03.] A carton's map from its read's answer — pure, nothing paid: the
    front panel the answer names ("face", a box inside the picture) is what the map measures (``read_pixels`` on its own
    pixels, read square to the camera); each part the answer names inside it is kept with its box as fractions of the
    panel, its words, lettering and turn, and its colour from the panel's pixels (``_colour_parts``, flat: each surface
    clear of the parts printed on it, no colour another under a second light); the panel's own light (CARTON_FACE_LIGHT) is left out of its colours, every other light
    the answer names is said beside the map and not applied; a part mostly outside the panel is left out by name.
    UNREAD, by name, where the answer names no front panel inside the picture. [His test blocker on design 124, (2)]
    ``read``, ``version`` and ``kinds`` a compact lid's where its read is (``read_lid_parts``)."""
    import numpy as np

    from apps.pipeline.services import concept_outline as co
    img, _s = co._read(image_bytes)
    if img is None:
        return _carton_unread(image_bytes, model, cost, CARTON_NO_FACE, "the picture could not be opened", read=read,
                              version=version)
    origin, size = (0, 0), (img.shape[1] * PARTS_UPSCALE, img.shape[0] * PARTS_UPSCALE)
    face = _map_box(payload.get("face"), origin, size) if isinstance(payload, dict) else None
    if face is None:
        return _carton_unread(image_bytes, model, cost, CARTON_NO_FACE,
                              "the read named no front panel inside the picture", read=read, version=version)
    fx0, fy0, fx1, fy1 = face
    mask = np.zeros(img.shape[:2], np.uint8)
    mask[fy0:fy1, fx0:fx1] = 1
    body, labels = read_pixels(img, mask)
    rec = {"schema_version": SCHEMA, "read": read, "params": dict(MAP_PARAMS),
           "source_sha256": hashlib.sha256(image_bytes).hexdigest(), "state": MAP_READ, "turned_deg": 0.0,
           "turned_by": "the front panel, read square to the camera as its concept is pictured", "face_box_px": face,
           **body, "parts_prompt_version": version, "model": model, "parts": [], "light_named": [],
           "light_beside": [], "problems": [], "cost": cost,
           **({"notes": payload["notes"][:200]} if isinstance(payload.get("notes"), str) else {})}
    shade = np.zeros(mask.shape, bool)
    for item in payload.get("light") or []:
        box = _map_box(item.get("box"), origin, size) if isinstance(item, dict) else None
        if box is None or item.get("kind") not in LIGHT_KINDS:
            continue
        on = [max(box[0], fx0), max(box[1], fy0), min(box[2], fx1), min(box[3], fy1)]
        if item["kind"] in CARTON_FACE_LIGHT and on[0] < on[2] and on[1] < on[3]:
            shade[on[1]:on[3], on[0]:on[2]] = True
            rec["light_named"].append({"kind": item["kind"], "box": _fractions(on, body)})
        else:
            rec["light_beside"].append({"kind": item["kind"], "box": _fractions(box, body),
                                        "why": "not the front panel's own light: not applied to its colours"})
    for item in payload.get("parts") or []:
        if not isinstance(item, dict) or item.get("kind") not in kinds:
            rec["problems"].append("a part of no declared kind was left out: %r" % (item,)[:120])
            continue
        box = _map_box(item.get("box"), origin, size)
        if box is None:
            rec["problems"].append("%s %r carries no box inside the picture" % (item["kind"], item.get("name")))
            continue
        on = [max(box[0], fx0), max(box[1], fy0), min(box[2], fx1), min(box[3], fy1)]
        inside = max(0, on[2] - on[0]) * max(0, on[3] - on[1])
        if inside * 2 < (box[2] - box[0]) * (box[3] - box[1]):
            rec["problems"].append("%s %r lies mostly outside the front panel: left out" % (item["kind"],
                                                                                         item.get("name")))
            continue
        part = {"kind": item["kind"], "name": str(item.get("name") or item["kind"])[:80], "box": _fractions(on, body),
                "_px": on}
        if item["kind"] == "motif" and isinstance(item.get("count"), int):
            part["count"] = item["count"]
        if item["kind"] in ("type", "mark") and item.get("seen_text"):
            part["seen_text"] = str(item["seen_text"])[:200]
        if item["kind"] == "type" and item.get("lettering"):
            part["lettering"] = str(item["lettering"])[:20]
        if item["kind"] == "type" and item.get("rotation") in TYPE_ROTATIONS:
            part["rotation"] = int(item["rotation"])
        if item["kind"] == "type" and item.get("spacing") in ("tight", "normal", "wide"):
            part["spacing"] = item["spacing"]                 # [his test blocker on design 124, (6)] as the read sees it
        if item["kind"] == "type" and type_style(item):
            part["style"] = type_style(item)                  # [his goal after the pitch page, A (1)]
        if str(item["texture"] if "texture" in item else "").lower() in TEXTURES:
            part["texture"] = str(item["texture"]).lower()           # [his review of 127-132, C (5)]
        if item.get("finish"):
            part["finish"] = str(item["finish"])[:40]
        rec["parts"].append(part)
    _colour_parts(rec["parts"], labels, body, shade, flat=True)
    for part in rec["parts"]:
        part.pop("_px")
    if not rec["parts"]:
        rec["problems"].append("%s: the read named no part" % PARTS_UNREAD)
    return rec


# [His test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2): "ONE ENGINE:
# palettes and compacts run the same map-first path as the tube and carton".] A compact's map is read as a carton's front
# panel is, from its lid stood square (``concept_outline.lid_picture``): the WHOLE picture is the lid, so its face is the
# frame; the read names its ground, its illustration (the scene the lid's art draws whole — ``targets.container.lid_art``,
# never a template), its mark and its lines of type, set as every map's are.

LID_READ = "compact lid"
LID_PARTS_PROMPT_VERSION = "lid-3"
LID_PART_KINDS = ("field", "illustration", "mark", "type", "rule", "band", "window")
#: drawn by the lid's art, whole: a map's part of this kind is drawn where the art traced (``undrawn_parts``)
ILLUSTRATION = "illustration"

LID_PARTS_SYSTEM = """You read a CONCEPT picture of the LID of a cosmetic PALETTE or COMPACT, seen square from above: the
WHOLE picture is the lid's face, edge to edge. Name the parts of the DESIGN printed on it, so that the lid can be drawn
exactly as the picture shows it. You measure what the picture shows; you invent nothing and you do not design.

THE LIGHT IS NOT DESIGN. Glossy streaks and highlights, shadows and shading, reflections are the photograph, not the
design: never name them as parts; list them under "light" instead. A glow the design itself paints (a halo of colour
round a drawn arch) IS design: part of its illustration.

The picture is drawn over with a PIXEL GRID: blue vertical lines every 50 px (labelled every 100 px along the top),
orange horizontal lines every 50 px (labelled every 100 px down the left). Read EVERY coordinate AGAINST THE GRID
LINES — never guess. Every box is [x0, y0, x1, y1] in PIXELS of the picture, x right, y down, tight around the part.

Parts — use exactly these kinds:
  "field"        the lid's ground: its own colour or its sky, under everything (ONE part)
  "illustration" a drawn scene or picture printed on the lid — figures, plants, shapes, a frame, a glow, a landscape —
                 one part per separate group of it, its whole extent
  "mark"         the brand wordmark or lockup (e.g. BBROSE)
  "type"         every other printed text: one part per line — give the exact words you see as "seen_text", the
                 lettering as "lettering": "script" | "serif" | "sans" | "display" | "arabic", "spacing": "tight" |
                 "normal" | "wide" (how far apart its letters stand), and "rotation": 0 when it reads left to right, 90
                 bottom to top, -90 top to bottom
  "rule"         a thin line on its own
  "band"         a stripe across the lid
  "window"       a framed panel or cartouche with nothing drawn inside it but type
For each part: "kind", "name" (a few plain words), "box", "seen_text" (type and mark only), "lettering", "spacing",
"style" and "rotation" (type only), "finish" (e.g. "gold foil", "gloss", "none"), "confidence" 0..1.
""" + TYPE_STYLE_WORDS + """

"light": each light area — {"kind": "shine" | "shadow" | "reflection" | "background", "box": [x0, y0, x1, y1]}.
"notes": one short line.

Respond ONLY with valid JSON:
{"parts": [{"kind": "...", "name": "...", "box": [x0,y0,x1,y1], "seen_text": "...", "lettering": "...",
            "spacing": "...", "style": {"class": "...", "serif": "...", "weight": "...", "italic": false,
                                        "width": "...", "case": "...", "spacing": "..."},
            "rotation": 0, "texture": "...", "finish": "...", "confidence": 0.0}],
 "light": [{"kind": "...", "box": [x0,y0,x1,y1]}], "notes": "..."}"""


def read_lid_parts(task, lid_png: bytes, *, call=None) -> dict:
    """[His test blocker on design 124, (2).] ``container_design_map/1.0`` of a compact's lid, stood square: one vision
    call (``LID_PARTS_SYSTEM``) on the lid picture under the parts read's own grid names each part printed on it; its
    own pixels then give each part its colour (``carton_record``, its face the whole frame). The read's cost from the
    ledger's own price table, on this design's ledger; ``call`` stands in for ``claude_service.call_claude`` (tests). A
    read that fails is UNREAD, by name; a spending cap stops it as it stops every paid step."""
    import base64

    from django.conf import settings

    from apps.pipeline.services import claude_service as cs
    from apps.pipeline.services import concept_outline as co
    from apps.pipeline.services.cost_ledger import BudgetExceededError, claude_cost_usd, task_cost_context
    model = settings.CLAUDE_MODEL_HEAVY
    nothing = {"usd": "0.000000", "input_tokens": 0, "output_tokens": 0, "calls": 0}
    img, _s = co._read(lid_png)
    if img is None:
        return _carton_unread(lid_png, model, nothing, CARTON_NO_FACE, "the lid picture could not be opened",
                              read=LID_READ, version=LID_PARTS_PROMPT_VERSION)
    picture, _origin, size = _parts_picture(img, {"product_box_px": [0, 0, img.shape[1], img.shape[0]]})
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                            "data": base64.b64encode(picture).decode()}},
               {"type": "text", "text": "THE PICTURE is %d x %d pixels.\n\nReturn the JSON now." % size}]
    try:
        with task_cost_context(task):
            response = (call or cs.call_claude)(LID_PARTS_SYSTEM, content, max_tokens=3000, model=model,
                                                operation=PARTS_OPERATION)
        tin, tout = int(response.usage.input_tokens), int(response.usage.output_tokens)
    except BudgetExceededError:
        raise
    except Exception as exc:  # noqa: BLE001 — the record says what failed
        return _carton_unread(lid_png, model, nothing, PARTS_UNREAD,
                              "the read raised %s: %s" % (type(exc).__name__, str(exc)[:200]),
                              read=LID_READ, version=LID_PARTS_PROMPT_VERSION)
    cost = {"usd": str(claude_cost_usd(model, tin, tout)), "input_tokens": tin, "output_tokens": tout, "calls": 1,
            "source": "cost_ledger.claude_cost_usd — the ledger's own price table"}
    try:
        payload = cs.loads_tolerant(cs.extract_text(response))
    except Exception as exc:  # noqa: BLE001
        return _carton_unread(lid_png, model, cost, PARTS_UNREAD, "the answer did not parse (%s)" % str(exc)[:160],
                              read=LID_READ, version=LID_PARTS_PROMPT_VERSION)
    if not isinstance(payload, dict):
        return _carton_unread(lid_png, model, cost, PARTS_UNREAD, "the answer was not a JSON object",
                              read=LID_READ, version=LID_PARTS_PROMPT_VERSION)
    # the whole picture is the lid: its face the frame the read was shown
    payload = dict(payload, face=[0, 0, size[0], size[1]])
    return carton_record(lid_png, payload, model=model, cost=cost, read=LID_READ, version=LID_PARTS_PROMPT_VERSION,
                         kinds=LID_PART_KINDS)


def held_lid_parts(held: dict | None, lid_png: bytes) -> dict | None:
    """``held`` — a compact's map on record — where it READ THIS lid picture under THIS prompt and model and named at
    least one part; else None. Pure; nothing paid."""
    if not held or held.get("read") != LID_READ:
        return None
    return _held(held, lid_png, LID_PARTS_PROMPT_VERSION)


def held_carton_parts(held: dict | None, image_bytes: bytes) -> dict | None:
    """[The owner's finding on design 119, 2026-10-03.] ``held`` — a carton's map on record — where it READ the front
    panel of THIS picture under THIS prompt and model and named at least one part; else None. Pure; nothing paid."""
    if not held or held.get("read") != CARTON_READ:
        return None
    return _held(held, image_bytes, CARTON_PARTS_PROMPT_VERSION)


# --- THE SCORE: the drawing against the concept, part by part ------------------------------------------------------------

# --- THE SHAPES: a part's own shape, traced from the picture at its full size ---------------------------------------
# [His answer after test day finding 3, 2026-09-30, transcribed at 23d4375: each part's "color, the shape and
# everything ... and the same way, draw it".] The map gives each part a box; the drawing needs its SHAPE. Traced on the
# picture at its own full size (the map is read at TRACE_PARAMS["scale_px"]), within the product the map measured, as
# fractions of that product's box — so a drawing of any size lays it where the picture lays it.

SHAPES_SCHEMA = "container_design_shapes/1.0"
SHAPES_TRACED = "TRACED"
SHAPES_REFUSED = "DESIGN_SHAPES_REFUSED"
SHAPE_PARAMS = {
    "version": "concept_design_shapes_params/1.30",  # 1.1: a scattered motif prints in one ink; 1.2: a script closed;
    #                                                  1.3: a band's outline and edge smoothed; 1.4: one sparkle fitted;
    #                                                  1.5: a script's lettering layered; 1.6: the raised gold;
    #                                                  1.7: the arches' gradient; 1.8: the letter snapped and cleaned;
    #                                                  1.9: the band's edge snapped; 1.10: the band redrawn as clean
    #                                                  curves, its gold open at a rule; 1.11: a band or a
    #                                                  rule the picture runs edge to edge run into the bleed;
    #                                                  1.12: a script's lettering set in the closest face;
    #                                                  1.13: a drip the edge cuts kept whole in the bleed;
    #                                                  1.14: a solid printed shape traced (a carton's silhouette);
    #                                                  1.15: a display or turned line traced and set;
    #                                                  1.16: a plain stripe traced (a band with no gold edge);
    #                                                  1.17: a display line set in the brief's words (his rule 1);
    #                                                  1.18: the granted display faces tried before tracing (his rule 3);
    #                                                  1.19: a solid shape's edge as clean curves (his rule 4);
    #                                                  1.20: a granted display face set as it is drawn (his rule 3);
    #                                                  1.21: a type line's weight and its letters' core ink (his review 4);
    #                                                  1.22: the rim round a solid shape (his review 5);
    #                                                  1.23: a shape's box the full extent it draws (his review 4);
    #                                                  1.24: a line or a mark set in its box (his go of 2026-10-08, 3);
    #                                                  1.25: line art, frames and windows in any ink (his go, 1 and 2);
    #                                                  1.26: a line of capitals its letters' own band (his goal of
    #                                                        2026-10-12, 7)
    #                                                  1.27: a window's named frame traced, a shape's second
    #                                                        ink its layer (his goal after the pitch page, A (4))
    #                                                  1.28: a line traced as a sliver of its read set in its read's
    #                                                        box; a rule round a box traced as the frame it is, a
    #                                                        motif in a window traced on it (his review of 127-132, C)
    #                                                  1.29: a name's lines set in one face; a line's ink read
    #                                                        off its letters (his last goal before the pitch)
    #                                                  1.30: a faint rule runs its read's width (126); a tall
    #                                                        line read turned (142)
    "pad": 0.015,             # a part's box read this share of the product wider on every side
    # [his goal of 2026-10-13, (7)-(9)] a window's arch, field and glow (``line_art.WINDOW``)
    "window": "window_shape/1.0",
    "gold_b_min": 28.0,       # a gold ink pixel: b* above this …
    "gold_b_over_a": 4.0,     # … above its own a* by this …
    "gold_l_min": 45.0,       # … and L* above this (a gold foil, its shade included, never the pink or the cream)
    "bridge_px": 5,           # a break in a gold line up to this many full-size pixels is bridged (a shine on the foil)
    "inset_px": 5,            # the band is read this far inside the product's own edge (the edge's fall-off)
    "approx_px": 0.75,        # an outline simplified to within this many full-size pixels
    # [his look at 117 drawn from its map, 2026-10-02: "everything should be smooth"] a band's outline and its edge are
    # the contour smoothed along its length over this many full-size pixels — a Gaussian of this sigma applied twice
    # over ("twicing": twice the smoothed less the smoothed again), which takes the pixel steps and the shade's wobble
    # on the gold line and keeps a drip's tip where a single pass pulls it in (measured on 117's own drip edge: 8.5
    # turns of direction back on itself per 100 px as simplified, 1.85 smoothed, its drips' foot moved 0.01 px) …
    "smooth_px": 4.5,
    "smooth_step_px": 4.0,    # … and resampled every this many pixels along it
    "tip_prominence": 0.15,   # a drip's tip stands this share of the band's depth below the nearer of its two rises
    "rule_rows": 0.5,         # a rule's row holds gold across at least this share of the rule's middle
    # [his answer after test day finding 3: a scattered motif — 117's sparkle stars] read across the product's width,
    # its box this share of the height taller each way; a shape among another part's (type, mark) is that part's
    "scatter_pad": 0.05,
    "star_core_max": 0.06,    # a star's gold core is at most a star's own largest size (never a band's edge)
    "star_reach": 0.009,      # … grown at most this share of the width along the paler gold it fades through …
    "star_pale_b_over_a": 2.0,  # … that paler gold: b* above a* by this, b* above star_pale_b_min, L* above gold_l_min
    "star_pale_b_min": 10.0,
    "star_size": (0.012, 0.06),   # a star spans this share of the product's width, smallest to largest
    "star_aspect": (0.6, 1.6),    # about as tall as it is wide
    "star_fill_max": 0.6,         # a four-point star fills well under its own box
    # [his look at 117 drawn from its map, 2026-10-02: the sparkles "match the reference exactly" and small designs never
    # "inconsistent"] each sparkle found is measured as the one sparkle shape (apps/ire/sparkle_glyph.py): on its
    # difference from the ground round it (CIE76), an arm reaches as far as that difference stays above this share of
    # the sparkle's own strongest …
    "star_arm_share": 0.2,
    # … and the pinch its arms show is the one, of these, whose arms are as wide as its gold's — its yellowness above
    # the ground, so never its pale halo — a quarter and half way out, less the picture's own softening (this many
    # pixels, taken out in quadrature); the motif draws the median, with the house's fine tip
    "star_pinches": (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95),
    "star_soften_px": 1.2,
    "star_arm_at": (0.25, 0.5),
    "star_arm_reach": 0.75,   # an arm reaches at most this share of the box its sparkle was found in, from its centre
    # [the executor's proposal before his go: the small copy typed from the brief at the picture's place]
    "type_ink_de": 22.0,      # a type line's pixel is within this (CIE76) of its measured ink
    "type_row_gap": 2,        # rows of no ink, at full size, that end a run of a line's rows
    "type_ink_min_height": 0.4,   # a line's traced ink shorter or narrower than this share of the line its read saw is
    #                               not its letters (a rule of its ink): the read's box stands — [his review, C (6)]
    # … where its shape is no line of those words: its width over its height beyond this factor of the words' own
    # (``type_em_per_char`` an em a character) either way — a loose read's box round real letters keeps their trace
    "type_sliver_aspect": 3.0, "type_em_per_char": 0.6,
    # [his goal after the pitch page, B (10)] a read ink within this (CIE76) of its line's ground is not its letters'
    # [his last goal before the pitch, Step 2] a line of a name set in its other lines' face where it lays this share of
    # the lettering bar on its letters
    "lettering_same_name": 0.6, "lettering_block_gap": 0.6,
    # [his word of 2026-10-17 on 142] a line read with no turn, its box this many times taller than wide, of at least
    # this many letters, is read turned
    "type_turn_aspect": 2.5, "type_turn_letters": 4,
    # [his D (11)] a rule's gold under this share of its read's width runs the read's width; never under this thick (px)
    "rule_span_least": 0.6, "rule_min_px": 2.0,
    # … or where it covers this share of them (IoU): one name, one face, before each line's own closest
    "lettering_same_name_iou": 0.45,
    "type_ink_ground_de": 20.0, "type_ground_ring": 0.15,
    # a line its words name white (black) printed in its box's lightest (darkest) share where its read is under
    # (over) this lightness (L*, 0-100)
    "type_named_share": 0.05, "type_white_l": 80.0, "type_black_l": 30.0,
    "type_caps_band": 0.6,    # a line of capitals: the rows round its densest holding at least this share of its ink
    # [his review of 119, 2026-10-05, point 4: "Set it in the concept's weight (bold, berry)."] a line's ink read from
    # its letters' cores where its strokes are thin, the picture's blur lightening them toward the ground (119's Arabic
    # line read #783F3F; its cores #53120F, the berry it prints in); and a capitals line's weight — its strokes' width
    # (twice its ink, each pixel counted by how far it stands from the ground toward the ink, over the outline of the
    # pixels more ink than ground) over its capitals' height: Noto Sans set and blurred as a picture prints it reads
    # 0.107 regular and 0.179 bold at 20 and 40 px; 119's "LIP GLOSS" 0.155. A line in lower case, or capitals under
    # type_weight_min_px tall, is not judged — the measure is calibrated on capitals of a readable height
    "type_thin_stroke_px": 3.0,   # a line whose strokes are thinner than this is read from its cores …
    "type_core_share": 0.3,       # … the share of its ink pixels farthest from the ground round it
    "type_bold_stroke_em": 0.14,  # a capitals line whose strokes are at least this share of their height is set bold
    "type_weight_min_px": 12,     # … judged only where its capitals stand at least this tall
    # [his answer after test day finding 3, (3): the script lettering traced] potrace on the line's ink at full size
    "script_upscale": 2,      # the ink read at this many times its full size before it is traced (smoother curves)
    # [measured on 117 at 300 dpi: its outline ring carries a pale highlight line, and traced as read it broke into 121
    # fragments; closed first, 43 clean rings] a gap in the ink this many (upscaled) pixels across is closed before tracing
    "script_close_px": 3,
    "potrace_turdsize": 10,   # a traced speck smaller than this many (upscaled) pixels is dropped
    "potrace_alphamax": 1.0,  # potrace's corner threshold
    "potrace_opttolerance": 0.4,  # potrace's curve-joining tolerance
    # [his look at 117 drawn from its map, 2026-10-02: the script's edges "not constant", its highlighting "not looking
    # good"] the lettering's layers, rebuilt from one smooth letter shape (``trace_lettering``): read this many times
    # finer than the picture …
    "lettering_upscale": 4,
    # … its gold ring found as the tracer's gold, lit, or in its bronze shade (b* above a* less 2, above this, at an
    # L* between these) …
    "lettering_shade_b_min": 15.0,
    "lettering_shade_l": (35.0, 70.0),
    "lettering_close_px": 9,        # … a gap in the ring this many (fine) pixels across closed …
    "lettering_body_min_px": 20.0,   # … a letter's body a region the ring encloses of at least this many picture pixels
    "lettering_smooth_px": 0.8,     # … smoothed over this many picture pixels (a Gaussian) — one smooth letter shape …
    # [his second look at 117, 2026-10-02: the script "not as smooth as the reference", "holes in the text"] … its edge
    # snapped, within this many picture pixels of the ring's, to the picture's own: where its lightness — read finer
    # by a smooth (bicubic) interpolation — passes half way from the ring's to the letter's; held solid this far
    # inside; a notch narrower than lettering_notch_px each side closed; a hole whose widest point is narrower than
    # lettering_hole_px each side (the slit a broken inner stroke line leaves) filled — a letter's eye is wider …
    "lettering_snap_px": 2.0,
    "lettering_core_px": 1.5,
    "lettering_notch_px": 1.0,
    "lettering_hole_px": 1.6,
    # … and each layer an even offset of it, measured in shells this many picture pixels deep: the ring as far as gold
    # holds this share of a shell; a pale line, where it stands this much lighter (L*) than what lies beyond it, as far
    # as a shell stays lighter than half way between them
    "lettering_shell_px": 0.5,
    # [his rules for cloning a design from a picture, 2026-10-02, rule 1: "LETTERING IS SET, NOT TRACED ... trace only
    # when no font comes close, and say so"] a face comes close when the picture's words set in it, fitted for size, place
    # and weight, lay their outline on the picture's letters' — this share of each within 1.5 picture pixels of the other
    # (F1) — the executor's bar, told to him, his to change. Measured before it was set: a face's own lettering, set in
    # it, 0.94, every other face on it 0.45 or less; 117's script against the closest face the house holds (Grand Hotel)
    # 0.34; four plain blocks 0.31 — where the letters' areas alone would let any dense run of text cover a block (0.76)
    # [his answers after 117 was redrawn on his rules, 2026-10-02 (a18911a), answer 1: the font set granted, "Then set
    # 117's name in the closest one" — the closest, not only the same face: 0.70 → 0.40, the floor that still tells
    # lettering from a block (blocks 0.31); measured on 117 with the set on file: Cookie 0.43, the closest]
    "lettering_set_outline": 0.40,
    # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (6): "The script
    # name: set in the granted face closest to the concept's script"] letters whose stroke's half-width is under this
    # share of their line's height are FINE (a hairline copperplate). Measured on 124's "Enchanted Rose" (0.014): at the
    # coarse measure's scale their strokes vanish (Great Vibes 29th of 62, 0.42), and a face grown to their weight reads
    # like any other (Poppins Light Italic 0.658, Great Vibes 0.650) — so every face is measured finely, each as it
    # draws (Great Vibes 0.733, Damion 0.706: the closest), never a shortlist of six. The executor's number, told him.
    "lettering_fine_stroke": 0.03,
    # [his look at 117 drawn from its map, 2026-10-02: the edges "not looking 3D"] the band's gold edge in its relief,
    # read this many times finer than the picture and in shells of lettering_shell_px: its lit middle where its
    # lightness stands above half way from its bronze to its lightest; the pale line inside it as the lettering's is
    "relief_upscale": 4,
    # [his look at 117 drawn from its map, 2026-10-02] the arches between a band's drips: their colour measured row by
    # row down the picture (rows of at least arch_row_px of their pixels, outside the band and its gold edge), drawn
    # as a gradient of this many stops from the band's top to its drips' foot
    "arch_row_px": 3,
    "arch_stops": 6,
    "relief_body": 0.35,      # the raised line's gold body: lighter than this share of the way from its bronze up
    "relief_crest": 0.75,     # its bright crest: lighter than this share of the way
    "relief_smooth_px": 18.0,  # each layer's outline smoothed over this many picture pixels (smooth_px's twicing): a
    #                           drip's broad tip keeps its reach, a notch the shine leaves in the gold line goes (7 at
    #                           785eba6; 18 since his second look, measured on 117 at 400 dpi: the bumps gone, the
    #                           eight drips' tips where they were)
    # [his second look at 117, 2026-10-02: the drips "still zigzaggy a bit"] the band's edge snapped, within this many
    # picture pixels of the traced one, to the picture's own: where its lightness — read finer by a smooth (bicubic)
    # interpolation — passes half way from the gold's to the band's; held solid this far inside; a notch narrower than
    # relief_notch_px each side closed
    "relief_snap_px": 2.0,
    "relief_core_px": 1.5,
    "relief_notch_px": 1.0,
    "relief_spur_px": 1.5,
    # [his rules for cloning a design from a picture, 2026-10-02, rule 2: "SHAPES ARE REDRAWN AS CLEAN CURVES: refit
    # drips, waves, arches and ribbons with the fewest points; even widths, round ends, no wobble"] a band's layers are
    # exact offsets of ONE clean band shape (its snapped edge smoothed once, over relief_smooth_px), each boundary refit
    # as the fewest cubic Béziers that keep within this many picture pixels of it (Schneider's fit, tangent-continuous)
    "curve_tol_px": 0.35,
    "curve_dense_px": 0.5,    # … the clean shape read as the smooth curve through its points, this many pixels apart
    # [his rules for cloning a design from a picture, 2026-10-02, rule 3: "EDGE TO EDGE MEANS BLEED: anything touching the
    # edge in the picture runs past the outline into the bleed; never a gap"] a part whose side lies within this many
    # pixels of the product's own edge on its own rows touches that edge (measured on 117: its band 0–3 px from the
    # tube's edge down both sides, its rule 0–2 px) …
    "edge_touch_px": 4,
    # … and is run past it by this share of the product's width — far past any drawn outline, so the bleed the drawing
    # gets is measured on the drawing, never assumed
    "bleed_reach": 0.1,
    # [his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010): "Make that part drawable"] a solid shape whose box runs to
    # within this share of the product's left and right edges runs edge to edge: into the bleed (his rule 3)
    "shape_edge_share": 0.02,
    # [his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (2): "a
    # concept shown as drawable must draw"] a traced solid more than this share of whose pixels the picture prints
    # nearer its ground's colour than its own ink paints over its ground (``_ground_share``): most of it. Measured: 123's
    # Garden Wrap's band 0.0 (both reads), 119's berry vial 0.37, Stem Journey's band 0.41, Blossom Arch's oval 0.81
    "shape_ground_share": 0.5,
    "rule_seam_px": 3.0,      # a band a rule closes runs this far up under it (measured on 117: a 2 px seam between)
    "lettering_ring_share": 0.5,
    "lettering_bright_l": 1.5,
    # [his answer after test day finding 3: the cap as the picture shows it] where the closure's colour begins
    "closure_de": 15.0,       # a field pixel is within this (CIE76) of the field beside the closure …
    "closure_field_row": 0.5,  # … a row is the field's while this much of its middle two fifths is …
    "closure_run": 5,         # … and the closure begins at the first of this many rows in a row that are not, full size
    # [his goal after the pitch page, B (9): 138's black cap on its deep plum body, too near in colour to tell apart, its
    # edge read 0.7 % down the product] an edge is the closure's only on the body's side of its map box — no farther from
    # the box's body edge than this share of the box's height; else the box's own edge stands, said
    "closure_edge_band": 0.5,
    "type_match": 0.6,        # a source phrase is a line's words when they share this much with what the picture shows
    # [the owner's finding on design 119, 2026-10-03: "Every panel is vector, drawn from the concept's map"] a solid shape
    "shape_ink_de": 22.0,     # a shape's pixel is within this (CIE76) of its measured ink, and a hole's of the ground
    "shape_min_share": 0.02,  # a piece of it at least this share of its largest piece is kept (a wand apart from its vial)
    "shape_smooth_px": 1.5,   # its outline smoothed over this many full-size pixels: a vial's thread ridges kept
    "shape_hole_px": 4,       # a hole at least this many pixels square, the ground's colour and under no part, is kept
    # [his review of 119, 2026-10-05, point 5: "The silhouette keeps the concept's details: 119's neck threads under the
    # wand are missing."] The threads are traced — the drawn edge lies within 0.5 px of the picture's on every row
    # through the neck; what the drawing lacked is the pale rim the picture draws round the whole shape (an embossed
    # edge: about 2 px of pale pink, #F4C8C4 to #F9D6CD on 119, round 70 % of it), which makes the threads read and
    # closes the gap between the wand and the neck — and, outside it, the edge's shadow (#E0AD9F, about 2 px), the line
    # that makes it read on the card. Read in one-pixel rings outward from the filled shape's edge, past its own blur: a
    # rim where the first ring is at least shape_rim_share neither ground nor ink; a band as wide as the rings that stay
    # so and stay its colour; at most two bands, the second where the colour moves on
    "shape_rim_de": 8.0,          # a rim pixel is this far (CIE76) from both the ground and the shape's ink …
    "shape_rim_share": 0.6,       # … the first ring at least this share of them, each ring after at least half …
    "shape_rim_ring_de": 8.0,     # … and each within this of the first ring's colour …
    "shape_rim_max_px": 6,        # … for at most this many rings
    # [his rule 4 for 119 and every design, 2026-10-05: "Smooth the silhouette's edge into clean curves."] its edge's true
    # corners kept, every stretch between them smoothed on its own and refit as fewer cubics
    "shape_corner_deg": 45.0, # a corner: the edge turns by at least this much …
    "shape_corner_px": 5,     # … across this many full-size pixels either side of it
    "shape_clean_px": 4.0,    # each stretch between corners smoothed over this many full-size pixels (one Gaussian):
    #                           measured, 3 left a pixel-stepped circle's flat runs bent the wrong way, 4 none
    "shape_curve_tol_px": 0.75,  # and refit as cubics within this many pixels of the smoothed edge
    # [his answer of 2026-10-05, W2: "build it. Plain stripes are basic."] a band with no gold edge: a plain stripe
    "band_row_share": 0.8,    # a row is the stripe's where its colour holds this share of its box's width …
    "band_foot_px": 3,        # … and its top and its foot run straight across to within this many full-size pixels
    "band_bent_share": 0.2,   # … on all but this share of its columns, its colour holding less than this share of
    #                           a row past its top and its foot (a drip, a wave runs on)
}


def _full_size(image_bytes: bytes, record: dict):
    """(the picture at its own size as BGR, the product's mask at that size, the product's box (x0, y0, x1, y1) in its
    pixels) for a map READ on a product the picture stands upright; or (None, None, why) — a product the read had to
    turn is not traced at full size, by name."""
    import cv2
    import numpy as np

    from apps.pipeline.services import concept_outline as co
    if record.get("face_box_px"):
        # [the owner's finding on design 119, 2026-10-03] a carton's front panel, as its read named it, at full size —
        # never the one standing product a cut finds (on 119, the silhouette printed on the panel)
        img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR) if image_bytes else None
        if img is None:
            return None, None, "the picture could not be opened"
        k = max(1.0, max(img.shape[:2]) / float(co.TRACE_PARAMS["scale_px"]))
        x0, y0, x1, y1 = (float(v) * k for v in record["face_box_px"])
        mask = np.zeros(img.shape[:2], np.uint8)
        mask[int(round(y0)):int(round(y1)), int(round(x0)):int(round(x1))] = 1
        return img, mask, (x0, y0, x1, y1)
    turned = record.get("turned_deg")
    if turned is None:
        return None, None, "the map records no turn for its product"
    turned = float(turned) % 180.0
    if min(turned, 180.0 - turned) > 1.0:
        return None, None, "the product stands turned %.0f° in the picture; its shapes are not traced at full size" % (
            turned)
    box = record.get("product_box_px")
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR) if image_bytes else None
    got = co.standing_pixels(image_bytes) if img is not None else None
    if img is None or not box or got is None:
        return None, None, "no product the map measured to trace"
    k = max(img.shape[:2]) / float(co.TRACE_PARAMS["scale_px"])
    mask = (np.asarray(got[1]) > 0).astype(np.uint8)
    if mask.shape[:2] != img.shape[:2]:
        mask = cv2.resize(mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
    return img, mask, tuple(float(v) * k for v in box)


def _gold(img):
    """A gold ink's pixels — yellow over red, lit or in shade."""
    L, A, B = _lab(img)
    return ((B > SHAPE_PARAMS["gold_b_min"]) & (B > A + SHAPE_PARAMS["gold_b_over_a"])
            & (L > SHAPE_PARAMS["gold_l_min"]))


def _crop(img, pbox, box):
    """The part's box, padded, in the picture's pixels: (x0, y0, x1, y1) clipped to the picture."""
    x0, y0, x1, y1 = pbox
    w, h, pad = x1 - x0, y1 - y0, SHAPE_PARAMS["pad"]
    return (max(0, int(x0 + (box[0] - pad) * w)), max(0, int(y0 + (box[1] - pad) * h)),
            min(img.shape[1], int(x0 + (box[2] + pad) * w)), min(img.shape[0], int(y0 + (box[3] + pad) * h)))


def _smooth(points, closed: bool, sigma: float):
    """[His look at 117 drawn from its map, 2026-10-02: "everything should be smooth".] A traced contour — its every
    pixel, in order — smoothed along its own length (a Gaussian of ``sigma`` picture pixels, twiced: twice the
    smoothed less the smoothed again, so a curve keeps its reach) and resampled every smooth_step_px: the line through
    the pixels, not their steps."""
    import numpy as np
    p = np.asarray(points, dtype=float)
    r = int(3 * sigma)
    kernel = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    kernel = kernel / kernel.sum()

    def blur(q):
        if closed:
            padded = np.concatenate([q[-r:], q, q[:r]])
        else:
            padded = np.concatenate([np.repeat(q[:1], r, axis=0), q, np.repeat(q[-1:], r, axis=0)])
        return np.stack([np.convolve(padded[:, k], kernel, mode="valid") for k in range(2)], axis=1)
    once = blur(p)
    smooth = 2.0 * once - blur(once)
    src = np.vstack([smooth, smooth[:1]]) if closed else smooth
    along = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(src, axis=0).T))])
    count = max(4, int(along[-1] / SHAPE_PARAMS["smooth_step_px"]))
    at = np.linspace(0.0, along[-1], count, endpoint=not closed)
    return np.stack([np.interp(at, along, src[:, k]) for k in range(2)], axis=1)


def _fit_cubics(points, tol: float) -> list:
    """[His rules for cloning a design from a picture, 2026-10-02, rule 2: "the fewest points ... no wobble".] A closed
    contour (``points`` in order, the first not repeated) as the fewest cubic Béziers that keep within ``tol`` of every
    point — Schneider's fit (Graphics Gems, 1990): the handles' lengths by least squares along tangents held fixed, the
    points' places on the curve refined by Newton's method, a curve that misses split at its worst point with one
    tangent shared either side, so the ring turns smoothly at every join. ``[[x0, y0], [c1x, c1y, c2x, c2y, x, y], …]``,
    the last segment ending where the first began."""
    import numpy as np
    p = np.asarray(points, float)
    if len(p) < 4:
        return []

    def bez(c, u, d):
        m = 1.0 - u
        if d == 0:
            return ((m ** 3)[:, None] * c[0] + (3 * m * m * u)[:, None] * c[1] + (3 * m * u * u)[:, None] * c[2]
                    + (u ** 3)[:, None] * c[3])
        if d == 1:
            return ((3 * m * m)[:, None] * (c[1] - c[0]) + (6 * m * u)[:, None] * (c[2] - c[1])
                    + (3 * u * u)[:, None] * (c[3] - c[2]))
        return (6 * m)[:, None] * (c[2] - 2 * c[1] + c[0]) + (6 * u)[:, None] * (c[3] - 2 * c[2] + c[1])

    def unit(v):
        n = float(np.hypot(*v))
        return v / n if n > 1e-12 else v

    def handles(q, u, t1, t2):
        m = 1.0 - u
        a1, a2 = t1[None] * (3 * m * m * u)[:, None], t2[None] * (3 * m * u * u)[:, None]
        rest = q - (q[0][None] * (m ** 3 + 3 * m * m * u)[:, None] + q[-1][None] * (3 * m * u * u + u ** 3)[:, None])
        c00, c01, c11 = (a1 * a1).sum(), (a1 * a2).sum(), (a2 * a2).sum()
        x0, x1 = (a1 * rest).sum(), (a2 * rest).sum()
        det = c00 * c11 - c01 * c01
        seg = float(np.hypot(*(q[-1] - q[0])))
        if abs(det) <= 1e-12:
            return np.array([q[0], q[0] + t1 * seg / 3.0, q[-1] + t2 * seg / 3.0, q[-1]])   # no least squares: thirds
        l1, l2 = (x0 * c11 - x1 * c01) / det, (c00 * x1 - c01 * x0) / det
        if l1 < 1e-6 * seg or l2 < 1e-6 * seg:
            l1 = l2 = seg / 3.0                    # a handle pointing backwards: the chord's thirds (Schneider's own)
        return np.array([q[0], q[0] + t1 * l1, q[-1] + t2 * l2, q[-1]])

    def worst(c, q, u):
        d = ((bez(c, u, 0) - q) ** 2).sum(axis=1)
        i = int(d.argmax())
        return float(d[i]), i

    out = []

    def turning(q):
        # the data's own turning, read over three pixels each way: its sign where it bends, 0 where it runs straight
        if len(q) < 8:
            return np.zeros(max(len(q), 0))
        a, b = q[6:] - q[3:-3], q[3:-3] - q[:-6]
        cross = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
        cross = cross / (np.hypot(*a.T) * np.hypot(*b.T) + 1e-12)
        sign = np.where(np.abs(cross) > np.sin(np.radians(1.0)), np.sign(cross), 0.0)
        return np.concatenate([np.zeros(3), sign, np.zeros(3)])

    def bends_alone(c, q):
        # the cubic inflects inside itself where its data turns one way only
        seen = {v for v in turning(q) if v}
        if len(seen) != 1:
            return False
        u = np.linspace(0.05, 0.95, 37)
        d1, d2 = bez(c, u, 1), bez(c, u, 2)
        cr = d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]
        return bool((cr > 1e-9).any() and (cr < -1e-9).any())

    def fit(q, t1, t2, depth):
        if len(q) == 2 or depth > 40:
            seg = float(np.hypot(*(q[-1] - q[0]))) / 3.0
            out.append(np.array([q[0], q[0] + t1 * seg, q[-1] + t2 * seg, q[-1]]))
            return
        along = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(q, axis=0).T))])
        u = along / along[-1]
        c = handles(q, u, t1, t2)
        err, i = worst(c, q, u)
        if err > tol * tol and err <= (4 * tol) ** 2:
            for _ in range(20):
                f, f1, f2 = bez(c, u, 0) - q, bez(c, u, 1), bez(c, u, 2)
                den = (f1 * f1).sum(axis=1) + (f * f2).sum(axis=1)
                safe = np.where(np.abs(den) > 1e-12, den, 1.0)
                u = np.clip(np.where(np.abs(den) > 1e-12, u - (f * f1).sum(axis=1) / safe, u), 0.0, 1.0)
                c = handles(q, u, t1, t2)
                err, i = worst(c, q, u)
                if err <= tol * tol:
                    break
        if err <= tol * tol and not (len(q) > 8 and bends_alone(c, q)):
            out.append(c)
            return
        if err <= tol * tol:
            i = len(q) // 2                                   # a bend its data does not have: split it in two
        i = min(max(i, 1), len(q) - 2)
        tc = unit(q[max(i - 4, 0)] - q[min(i + 4, len(q) - 1)])   # the tangent read over four pixels each way
        fit(q[:i + 1], t1, tc, depth + 1)
        fit(q[i:], -tc, t2, depth + 1)
    k = int(np.argmax(p[:, 1]))                     # begun at the ring's lowest point: a drip's tip, a smooth place
    p = np.roll(p, -k, axis=0)
    loop = np.vstack([p, p[:1]])
    sign = turning(np.vstack([p[-3:], p, p[:4]]))[3:-4]            # the closed ring's own turning, point by point
    marked = [j for j in range(len(p)) if sign[j]]
    cuts = [marked[n] for n in range(len(marked)) if sign[marked[n]] != sign[marked[n - 1]]] if marked else []
    if len(cuts) < 2:
        t1 = unit(p[min(4, len(p) - 1)] - p[-min(4, len(p) - 1)])
        fit(loop, t1, -t1, 0)
    else:
        # split where the ring's curvature changes sign — each span bends one way — and fit each span on its own
        p = np.roll(p, -cuts[0], axis=0)
        cuts = [(j - cuts[0]) % len(p) for j in cuts] + [len(p)]
        q_all = np.vstack([p, p[:1]])
        for a, b in zip(cuts, cuts[1:]):
            q = q_all[a:b + 1]
            if len(q) < 2:
                continue
            ta = unit(q_all[min(a + 4, len(q_all) - 1)] - q_all[a - 4 if a >= 4 else a - 4 + len(p)])
            tb = unit(q_all[b - 4] - q_all[(b + 4) % len(p)])
            fit(q, ta, tb, 0)
    return [[round(float(out[0][0][0]), 3), round(float(out[0][0][1]), 3)]] + [
        [round(float(v), 3) for v in (c[1][0], c[1][1], c[2][0], c[2][1], c[3][0], c[3][1])] for c in out]


def _dense(points, step: float):
    """[His rules, 2026-10-02, rule 2: "no wobble".] A closed contour's points (in order, the first not repeated) as the
    smooth curve through them — each span a cubic whose handles follow its neighbours (Catmull-Rom, the curve the
    composer draws through points) — sampled about ``step`` picture pixels apart: never the chain of straight steps
    between them, whose corners a fit of fewer curves would follow."""
    import numpy as np
    p = np.asarray(points, float)
    n = len(p)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = p[(i - 1) % n], p[i], p[(i + 1) % n], p[(i + 2) % n]
        c1, c2 = p1 + (p2 - p0) / 6.0, p2 - (p3 - p1) / 6.0
        m = max(2, int(np.hypot(*(p2 - p1)) / step))
        u = np.linspace(0.0, 1.0, m, endpoint=False)[:, None]
        v = 1.0 - u
        out.append(v ** 3 * p1 + 3 * v * v * u * c1 + 3 * v * u * u * c2 + u ** 3 * p2)
    return np.vstack(out)


def _offset(base, d: float):
    """[His rules, 2026-10-02, rule 2: "even widths".] ``base`` (a shapely shape, picture pixels) grown by ``d`` pixels
    (shrunk where negative) — exactly, its corners round."""
    return base.buffer(d, quad_segs=16, join_style="round") if d else base


def _clean_ring(points):
    """[His rule 4 for 119 and every design, 2026-10-05: "Smooth the silhouette's edge into clean curves."] A traced
    shape's closed edge — every pixel of it, in order — as clean curves: its true corners found (where it turns by
    shape_corner_deg or more across shape_corner_px either side, the sharpest of each run), every stretch between two of
    them smoothed on its own (one Gaussian of shape_clean_px, its ends held at the corners, a straight run kept straight
    to its end), a ring with no corner smoothed whole; resampled every smooth_step_px. The pixels' steps and the picture's
    jitter go; a corner, a neck, a vial's shoulder stays."""
    import numpy as np
    p = np.asarray(points, dtype=float)
    n, w = len(p), int(SHAPE_PARAMS["shape_corner_px"])
    sigma, step = SHAPE_PARAMS["shape_clean_px"], SHAPE_PARAMS["smooth_step_px"]
    r = int(3 * sigma)
    kernel = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    kernel = kernel / kernel.sum()

    def resample(q, closed):
        src = np.vstack([q, q[:1]]) if closed else q
        along = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(src, axis=0).T))])
        count = max(2, int(along[-1] / step))
        if not closed:
            count += 1                                  # an open stretch keeps its far end
        at = np.linspace(0.0, along[-1], count, endpoint=not closed)
        return np.stack([np.interp(at, along, src[:, k]) for k in range(2)], axis=1)

    if n < 4 * w + 8:
        return _smooth(p, True, SHAPE_PARAMS["shape_smooth_px"])
    a = p - np.roll(p, w, axis=0)
    b = np.roll(p, -w, axis=0) - p
    turn = np.degrees(np.abs(np.arctan2(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0], (a * b).sum(axis=1))))
    corners = []
    for i in np.nonzero(turn >= SHAPE_PARAMS["shape_corner_deg"])[0]:
        window = turn[[(i + j) % n for j in range(-w, w + 1)]]
        if turn[i] >= window.max() and not (corners and i - corners[-1] <= w):
            corners.append(int(i))
    if len(corners) > 1 and corners[0] + n - corners[-1] <= w:
        corners.pop()
    if not corners:
        padded = np.concatenate([p[-r:], p, p[:r]])
        smooth = np.stack([np.convolve(padded[:, k], kernel, mode="valid") for k in range(2)], axis=1)
        return resample(smooth, True)
    pieces = []
    for c0, c1 in zip(corners, corners[1:] + [corners[0] + n]):
        span = p[[k % n for k in range(c0, c1 + 1)]]
        if len(span) > 2 * r + 2:
            # odd reflection about each end: a straight run stays straight to its corner
            head = 2 * span[0] - span[1:r + 1][::-1]
            tail = 2 * span[-1] - span[-r - 1:-1][::-1]
            padded = np.concatenate([head, span, tail])
            span = np.stack([np.convolve(padded[:, k], kernel, mode="valid") for k in range(2)], axis=1)
            span[0], span[-1] = p[c0 % n], p[c1 % n]
        pieces.append(resample(span, False)[:-1])
    return np.vstack(pieces)


def _cubic_rings(geom, tol: float) -> list:
    """Each polygon of ``geom`` as its rings refit as cubics (``_fit_cubics``) — its outside first, then its holes; the
    rings resampled every picture pixel along them before they are fitted. A polygon smaller than a pixel is left out."""
    import numpy as np
    polys = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    out = []
    for poly in polys:
        if poly.geom_type != "Polygon" or poly.is_empty or poly.area < 1.0:
            continue
        rings = []
        for ring in [poly.exterior] + list(poly.interiors):
            q = np.asarray(ring.coords, float)[:-1]
            loop = np.vstack([q, q[:1]])
            along = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(loop, axis=0).T))])
            at = np.linspace(0.0, along[-1], max(8, int(along[-1])), endpoint=False)
            fitted = _fit_cubics(np.stack([np.interp(at, along, loop[:, j]) for j in range(2)], axis=1), tol)
            if fitted:
                rings.append(fitted)
        if rings:
            out.append(rings)
    return out


def _ring_points(rings, step: float) -> list:
    """The outside of the largest polygon ``_cubic_rings`` gave, as points along its curves about ``step`` apart — the
    layer's outline, read by what measures it."""
    import numpy as np
    if not rings:
        return []
    pts = []
    ring = max(rings, key=lambda poly: len(poly[0]))[0]
    x, y = ring[0]
    for seg in ring[1:]:
        c = np.array([[x, y], seg[0:2], seg[2:4], seg[4:6]], float)
        u = np.linspace(0.0, 1.0, 64, endpoint=False)[:, None]
        m = 1.0 - u
        pts.append(m ** 3 * c[0] + 3 * m * m * u * c[1] + 3 * m * u * u * c[2] + u ** 3 * c[3])
        x, y = seg[4], seg[5]
    q = np.vstack(pts + [pts[0][:1]])
    along = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(q, axis=0).T))])
    at = np.arange(0.0, along[-1], step)          # evenly along the curve, never bunched where its pieces are short
    return np.stack([np.interp(at, along, q[:, j]) for j in range(2)], axis=1)


def _pick(lab_px, q: float) -> str:
    """The colour of a band of pixels by its ``q``-th percentile of lightness: the median of those within 3 L* of it —
    a band two or three pixels wide blends its neighbours at its edges, so its lit colour is its lightest and its shade
    its darkest."""
    import numpy as np
    cut = np.percentile(lab_px[:, 0], q)
    return _hex(np.median(lab_px[np.abs(lab_px[:, 0] - cut) <= 3.0], axis=0))


def _edge_sides(part, product, slack: float) -> dict:
    """[His rules for cloning a design from a picture, 2026-10-02, rule 3: "EDGE TO EDGE MEANS BLEED".] The sides of the
    product a part reaches, each with the first and last of the rows it reaches it on: a row where the part's own
    outermost pixel lies within ``slack`` pixels of the product's on that side. A side reached on fewer than three rows
    is not reached. ``{"left" | "right": [first row, last row]}`` in the pixels of ``part``."""
    import numpy as np
    rows = np.nonzero(part.any(axis=1) & product.any(axis=1))[0]
    out = {}
    for side in ("left", "right"):
        hits = []
        for y in rows:
            xs, ps = np.nonzero(part[y])[0], np.nonzero(product[y])[0]
            gap = (xs.min() - ps.min()) if side == "left" else (ps.max() - xs.max())
            if gap <= slack:
                hits.append(int(y))
        if len(hits) >= 3:
            out[side] = [min(hits), max(hits)]
    return out


def _band_relief(crop, inside, gold, width_px: float, fill: str | None, top_closed: bool, sides: dict,
                 reach_px: float) -> dict | None:
    """[His look at 117 drawn from its map, 2026-10-02: "The edges are not um, looking 3D".] A band's gold edge as the
    picture lights it, each layer an EVEN offset of the band (``inside``, its pixels): measured outward from it in shells
    of lettering_shell_px — the gold (``gold``, the tracer's) from the first shell it holds half of to the last; inside
    the gold, its body and its bright crest where its lightness stands above relief_body and relief_crest of the way
    from its bronze to its lightest; before the gold,
    the pale line the cream shows along it where it stands lettering_bright_l lighter than the cream. ``{"layers":
    [{"name", "outline" (pixels of ``crop``, smoothed), "ink"}] back to front — the bronze edge, its gold body, its
    crest, the body and the bronze on its inner side, the pale line, the band's fill — "widths_px"}``; None where the
    edge holds no gold or no light
    of its own.
    [His rules for cloning a design from a picture, 2026-10-02, rule 2: "SHAPES ARE REDRAWN AS CLEAN CURVES".] Each layer
    is an EXACT offset of one clean band shape — the snapped edge's contour smoothed once — its gold a ring cut where
    the gold ends inside, open at the band's top where a rule closes it (``top_closed``), each boundary refit as the
    fewest cubics (``cubics``; ``outline`` the points along its outside, for what measures it)."""
    import cv2
    import numpy as np
    k = int(SHAPE_PARAMS["relief_upscale"])
    big = cv2.resize(inside.astype(np.uint8) * 255, None, fx=k, fy=k, interpolation=cv2.INTER_LINEAR)
    big = (cv2.GaussianBlur(big, (0, 0), 0.5 * k) > 127).astype(np.uint8)
    # [his second look at 117, 2026-10-02: the drips "still zigzaggy a bit"] the band's edge the picture's own: where
    # its lightness, read finer by a smooth interpolation, passes half way from the gold's to the band's
    lightness = _lab(crop)[0]
    near_gold = gold & (cv2.dilate(inside.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0)
    if near_gold.any():
        edge_l = (float(np.median(lightness[near_gold])) + float(np.median(lightness[inside > 0]))) / 2.0
        fine_l = cv2.resize(lightness.astype(np.float32), None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)

        def disc(px):
            r = max(1, int(round(px * k)))
            return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
        snapped = ((fine_l > edge_l).astype(np.uint8) & cv2.dilate(big, disc(SHAPE_PARAMS["relief_snap_px"]))) | \
            cv2.erode(big, disc(SHAPE_PARAMS["relief_core_px"]))
        nn, sc = cv2.connectedComponents(snapped, connectivity=4)
        held_by = np.unique(sc[big > 0])
        snapped = np.isin(sc, held_by[held_by > 0]).astype(np.uint8)
        big = cv2.morphologyEx(snapped, cv2.MORPH_CLOSE, disc(SHAPE_PARAMS["relief_notch_px"]))
        # a spur narrower than relief_spur_px each side — the band reaching into a gap the shine leaves in the gold — cut
        big = cv2.morphologyEx(big, cv2.MORPH_OPEN, disc(SHAPE_PARAMS["relief_spur_px"]))
    out = cv2.distanceTransform(1 - big, cv2.DIST_L2, 5) / k
    inn = cv2.distanceTransform(big, cv2.DIST_L2, 5) / k
    small = (crop.shape[1], crop.shape[0])
    out_px, in_px = cv2.resize(out, small, interpolation=cv2.INTER_AREA), cv2.resize(inn, small, interpolation=cv2.INTER_AREA)
    lab = np.stack(_lab(crop), -1)
    shell = SHAPE_PARAMS["lettering_shell_px"]
    shells = []
    for d0 in np.arange(0.0, width_px + 3.0, shell):
        m = (out_px > d0) & (out_px <= d0 + shell)
        if m.any():
            shells.append((float(d0), float(gold[m].mean()), float(np.median(lab[..., 0][m]))))
    held = [d0 for d0, share, _lv in shells if share >= 0.5]
    if not held or held[0] > 3.0:
        return None
    gold_from, gold_to = held[0], held[0]
    for d0, share, _lv in shells:
        if d0 >= gold_from and share >= 0.5:
            gold_to = d0 + shell
        elif d0 > gold_from:
            break
    across = [(d0, lv) for d0, _share, lv in shells if gold_from <= d0 < gold_to]
    darkest, lightest = min(lv for _d, lv in across), max(lv for _d, lv in across)
    if lightest - darkest < SHAPE_PARAMS["lettering_bright_l"]:
        return None
    # its body where the gold stands above RELIEF_BODY of the way from its bronze to its lightest, its highlight above
    # RELIEF_HIGHLIGHT — the picture's raised line: bronze sides, a gold body, a thin bright crest
    body_band = [d0 for d0, lv in across if lv >= darkest + SHAPE_PARAMS["relief_body"] * (lightest - darkest)]
    crest = [d0 for d0, lv in across if lv >= darkest + SHAPE_PARAMS["relief_crest"] * (lightest - darkest)]
    body_from, body_to = min(body_band), max(body_band) + shell
    lit_from, lit_to = min(crest), max(crest) + shell
    cream = float(np.median(lab[..., 0][in_px > 4.0])) if (in_px > 4.0).any() else None
    pale = cream is not None and any(lv >= cream + SHAPE_PARAMS["lettering_bright_l"]
                                     for d0, _share, lv in shells if d0 < gold_from)
    # [his second look] the band's edge snapped to the gold's own, the pale line along it lies inside: measured inward,
    # from its lightest shell while it stays lighter than half way to the cream
    inline_in = 0.0
    if cream is not None and not pale:
        inward = [(d0, float(np.median(lab[..., 0][(in_px > d0) & (in_px <= d0 + shell)])))
                  for d0 in np.arange(0.0, 3.0, shell) if ((in_px > d0) & (in_px <= d0 + shell)).any()]
        if inward and max(lv for _d, lv in inward) >= cream + SHAPE_PARAMS["lettering_bright_l"]:
            half = (max(lv for _d, lv in inward) + cream) / 2.0
            top = max((lv, d0) for d0, lv in inward)[1]
            for d0, lv in inward:
                if d0 >= top and lv < half:
                    break
                inline_in = d0 + shell
    band_gold = lab[(out_px > gold_from) & (out_px <= gold_to)]
    shade, body_ink, lit_ink = _pick(band_gold, 15.0), _pick(band_gold, 55.0), _pick(band_gold, 92.0)

    # [his rules, 2026-10-02, rule 2] ONE clean band shape: the snapped edge's contour, smoothed once …
    from shapely.geometry import Point, Polygon, box
    cs, _ = cv2.findContours(big.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    base = Polygon(_dense(_smooth(max(cs, key=cv2.contourArea)[:, 0, :] / float(k), True,
                                  SHAPE_PARAMS["relief_smooth_px"]), SHAPE_PARAMS["curve_dense_px"])).buffer(0)
    if base.geom_type != "Polygon":
        base = max(base.geoms, key=lambda g: g.area)
    # [his rules, 2026-10-02, rule 3: "EDGE TO EDGE MEANS BLEED"; his word the same day (a18911a): "where the picture shows
    # a shape whole (117's edge drips with round tips), keep it whole inside the bleed; don't cut it flat"] on a side the
    # band reaches the product's own edge on (``sides``), each row it reaches it on carried on past that edge by its own
    # width there — the run from the edge to where the band first opens — mirrored about the edge, and never further than
    # ``reach_px``: the solid top runs out the whole bleed, and a drip the edge cuts runs on past it as the drip it is,
    # narrowing to its round tip as the picture's narrows — never a ledge cut flat under it
    made_whole = []
    for side, (ya, yb) in sides.items():
        rows = []
        for y in range(int(ya), int(yb) + 1):
            xs = np.nonzero(inside[y])[0]
            if not len(xs):
                continue
            gaps = np.nonzero(np.diff(xs) > 1)[0]
            if side == "left":
                at, run = float(xs.min()) + 1.0, float(xs[gaps[0]] + 1 - xs.min()) if len(gaps) else float(len(xs))
            else:
                at, run = float(xs.max()), float(xs.max() - xs[gaps[-1] + 1] + 1) if len(gaps) else float(len(xs))
            rows.append((float(y), at, min(run, reach_px)))
        if len(rows) < 3:
            continue
        # each row's width the median of the five about it, so a pixel's grain along the drip's inner side is not drawn
        runs = [float(np.median([r[2] for r in rows[max(0, k - 2):k + 3]])) for k in range(len(rows))]
        rows = [(y, at, run) for (y, at, _raw), run in zip(rows, runs)]
        out = [(at - run if side == "left" else at + run, y) for y, at, run in rows]
        back = [(at, y) for y, at, _run in reversed(rows)]
        base = base.union(Polygon([(out[0][0], out[0][1] - 0.5)] + out + [(out[-1][0], out[-1][1] + 0.5)] + back)
                          .buffer(0))
        drip_rows = [y for y, _at, run in rows if run < reach_px]
        if drip_rows:
            # where the drip leaves the edge its end is rounded across it, as wide as it is there: its tip, never a ledge
            y_end, at_end, run_end = rows[-1]
            base = base.union(Point(at_end, y_end).buffer(run_end, quad_segs=16))
            made_whole.append({"side": side, "rows_px": [int(min(drip_rows)), int(max(drip_rows))]})
    if sides:
        base = base.buffer(2.0, quad_segs=16, join_style="round").buffer(-2.0, quad_segs=16, join_style="round")
        if base.geom_type != "Polygon":
            base = max(base.geoms, key=lambda g: g.area)
    # … every layer an exact offset of it: the gold rings cut where the gold ends inside (the pale line's edge), open
    # at the band's top where a rule closes it; the pale line and the fill solid
    cap = None
    if top_closed:
        from shapely.ops import unary_union

        def facing_up(shape, reach):
            # each step of ``shape``'s outline whose outward side faces up, swept outward ``reach``; and its middle's row
            pts = np.asarray(shape.exterior.coords, float)
            quads, rows = [], []
            for p0, p1 in zip(pts[:-1], pts[1:]):
                t = p1 - p0
                n = float(np.hypot(*t))
                if n < 1e-9:
                    continue
                nx, ny = t[1] / n, -t[0] / n
                mid = (p0 + p1) / 2.0
                if shape.contains(Point(mid[0] + 0.5 * nx, mid[1] + 0.5 * ny)):
                    nx, ny = -nx, -ny                               # the outward side
                if ny < -0.5:
                    quads.append(Polygon([p0, p1, (p1[0] + nx * reach, p1[1] + ny * reach),
                                          (p0[0] + nx * reach, p0[1] + ny * reach)]).buffer(0.25))
                    rows.append(float(mid[1]))
            return quads, rows
        # where a rule closes the band's top the band runs up under it rule_seam_px along all of its top — the rule is
        # drawn over it — so no seam of what lies behind shows between the rule's traced foot and the band's traced top:
        # the band joined to itself moved up that far, which raises its top and leaves its drips and arches where they are
        from shapely import affinity
        base = base.union(affinity.translate(base, 0.0, -SHAPE_PARAMS["rule_seam_px"]))
        if base.geom_type != "Polygon":
            base = max(base.geoms, key=lambda g: g.area)
        # the band's top — its edge that faces up, where the rule lies over it — carries none of its gold: each step of
        # its outline whose outward side faces up, swept outward past the gold's reach — an arch's top faces down and
        # keeps its gold — and nothing of it above the band's top line (the median of that edge): where the smoothed
        # outline rounds the band's top corners its gold would otherwise rise past the line, into the rule
        quads, tops = facing_up(base, gold_to + 1.0)
        if tops:
            bx0, by0, bx1, by1 = base.bounds
            quads.append(box(bx0 - 1e4, by0 - 1e4, bx1 + 1e4, float(np.median(tops))))
        cap = unary_union(quads) if quads else None
    plan = []                                  # (name, the shape drawn, the solid shape it is cut from, ink)
    for name, reach, ink in (("edge-shade", gold_to, shade), ("edge-body", body_to, body_ink),
                             ("edge-lit", lit_to, lit_ink), ("edge-body-inner", lit_from, body_ink),
                             ("edge-inner", body_from, shade)):
        solid = _offset(base, reach)
        ring = solid.difference(_offset(base, gold_from))
        plan.append((name, ring.difference(cap) if cap is not None else ring, solid, ink))
    if pale:
        plan.append(("inline", _offset(base, gold_from), _offset(base, gold_from),
                     _pick(lab[(out_px > 0.0) & (out_px <= gold_from)], 90.0)))
        if fill:
            plan.append(("fill", base, base, fill))
    elif inline_in:
        plan.append(("inline", _offset(base, gold_from), _offset(base, gold_from),
                     _pick(lab[(in_px > 0.0) & (in_px <= inline_in)], 90.0)))
        if fill:
            plan.append(("fill", _offset(base, -inline_in), _offset(base, -inline_in), fill))
    elif fill:
        plan.append(("fill", _offset(base, gold_from), _offset(base, gold_from), fill))
    layers = []
    for name, shape, solid, ink in plan:
        rings = _cubic_rings(shape, SHAPE_PARAMS["curve_tol_px"])
        if rings:
            # ``outline``: the layer's solid outer edge — a gold ring's reach, as every layer's was before it was a
            # ring — what the instruments read; the shape drawn is ``cubics``
            layers.append({"name": name, "cubics": rings, "ink": ink,
                           "outline": _ring_points(_cubic_rings(solid, SHAPE_PARAMS["curve_tol_px"]),
                                                   SHAPE_PARAMS["smooth_step_px"])})
    widths = {"edge": round(gold_to - gold_from, 2),
              "body": [round(body_from - gold_from, 2), round(body_to - gold_from, 2)],
              "lit": [round(lit_from - gold_from, 2), round(lit_to - gold_from, 2)]}
    if pale:
        widths["inline"] = round(gold_from, 2)                 # the pale line: from the cream to the gold
    elif inline_in:
        widths["inline"] = round(inline_in + gold_from, 2)     # … inside the snapped edge, and up to the gold
    return {"layers": layers, "widths_px": widths, **({"edge_drips_whole": made_whole} if made_whole else {})}


def _arch_colours(crop, product, inside, width_px: float, below: str | None) -> dict | None:
    """[His look at 117 drawn from its map, 2026-10-02.] The colour of the arches between a band's drips, down the
    picture: from the band's own top to its drips' foot, each row's median of the pixels inside the product and outside
    the band and its gold edge (rows with fewer than SHAPE_PARAMS["arch_row_px"] of them skipped), read at
    arch_stops evenly spaced rows, the last the colour of the field the drips hang into (``below``, the map's) where it
    is known, so the arches meet it without a seam — ``{"rows": [first, last] (pixels of ``crop``), "stops": [[offset,
    hex]]}``; None where no row holds arches."""
    import cv2
    import numpy as np
    ys = np.nonzero(inside.any(axis=1))[0]
    if not len(ys):
        return None
    reach = int(np.ceil(width_px)) + 2
    edge = cv2.dilate(inside, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * reach + 1, 2 * reach + 1)))
    arch = (product > 0) & (edge == 0)
    top, foot = int(ys.min()), int(ys.max())
    lab = np.stack(_lab(crop), -1)
    rows = [(y, np.median(lab[y][arch[y]], axis=0)) for y in range(top, foot + 1)
            if int(arch[y].sum()) >= SHAPE_PARAMS["arch_row_px"]]
    if len(rows) < 2:
        return None
    first, last = rows[0][0], rows[-1][0]
    n = int(SHAPE_PARAMS["arch_stops"])
    stops = []
    for k in range(n):
        at = first + (last - first) * k / float(n - 1)
        near = [v for y, v in rows if abs(y - at) <= 2.5]
        if near:
            stops.append([round(k / float(n - 1), 4), _hex(np.median(np.stack(near), axis=0))])
    if below and len(stops) >= 2:
        stops[-1] = [1.0, str(below).upper()]                 # the field it hangs into, meeting it without a seam
    return {"rows": [first, last], "stops": stops} if len(stops) >= 2 else None


def trace_band(img, mask, pbox, band: dict) -> dict:
    """A band that hangs from its top and ends in a gold edge (117's cream drip band): the band as everything joined to
    its own top without crossing that edge, inside the product; returns its outline, its edge as open lines (the band's
    outline less its top), the edge's width and ink, and its drips — the edge's tips — counted; or ``{"refused": why}``
    when the edge is open (the band reaches the foot of its box)."""
    import cv2
    import numpy as np
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    cx0, cy0, cx1, cy1 = _crop(img, pbox, band["box"])
    crop = img[cy0:cy1, cx0:cx1]
    gold = _gold(crop).astype(np.uint8)
    k = SHAPE_PARAMS["bridge_px"]
    barrier = cv2.dilate(cv2.morphologyEx(gold, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8)), np.ones((3, 3), np.uint8))
    i = SHAPE_PARAMS["inset_px"]
    allowed = (1 - barrier) & cv2.erode(mask[cy0:cy1, cx0:cx1], np.ones((i, i), np.uint8))
    n, cc, stats, _c = cv2.connectedComponentsWithStats(allowed.astype(np.uint8), 4)
    # a row inside the band's own top, below its rule — the band is what joins it
    seed = min(cc.shape[0] - 1, max(0, int(y0 + (band["box"][1] + 0.15 * (band["box"][3] - band["box"][1])) * h) - cy0))
    counts = np.bincount(cc[seed], minlength=n)
    counts[0] = 0
    best = int(counts.argmax())
    if not counts[best]:
        return {"refused": "nothing of the band at its own top"}
    if stats[best, cv2.CC_STAT_TOP] + stats[best, cv2.CC_STAT_HEIGHT] >= cc.shape[0]:
        # [his answer of 2026-10-05, W2] no gold edge closes it: a plain stripe, read as one
        return _plain_band(img, mask, pbox, band, (cx0, cy0, cx1, cy1))
    inside = (cc == best).astype(np.uint8)
    cnts, _ = cv2.findContours(cv2.morphologyEx(inside, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)),
                               cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    inside = np.zeros_like(inside)
    cv2.drawContours(inside, [max(cnts, key=cv2.contourArea)], -1, 1, -1)
    ring = (cv2.dilate(inside, np.ones((15, 15), np.uint8)) > 0) & (inside == 0) & (gold > 0)
    dist = cv2.distanceTransform(ring.astype(np.uint8), cv2.DIST_L2, 3)
    ridge = (dist >= cv2.dilate(dist, np.ones((3, 3), np.uint8)) - 1e-6) & (dist > 0.5)
    if not ridge.any():
        # [his answer of 2026-10-05, W2] no gold round it: a plain stripe, read as one
        return _plain_band(img, mask, pbox, band, (cx0, cy0, cx1, cy1))
    width_px = float(np.median(dist[ridge]) * 2.0)
    half = max(1, int(round(width_px / 2.0)))

    def outline(m):
        # [his look at 117 drawn from its map, 2026-10-02: "everything should be smooth"] the smooth line through the
        # contour's pixels, where a simplified polygon kept their steps (117's drip edge: zigzag at print size)
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        return _smooth(max(cs, key=cv2.contourArea)[:, 0, :], True, SHAPE_PARAMS["smooth_px"])
    centre = outline(cv2.dilate(inside, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * half + 1,) * 2)))
    whole = outline(cv2.dilate(inside, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (4 * half + 1,) * 2)))

    def frac(pts):
        return [[round((cx0 + px - x0) / w, 5), round((cy0 + py - y0) / h, 5)] for px, py in pts]
    top = centre[:, 1].min()
    low = centre[:, 1] > top + max(3.0, 2.0 * width_px)
    runs, cur = [], []
    for j in range(len(centre)):
        if low[j]:
            cur.append(centre[j])
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        if runs and low[0]:
            runs[0] = cur + runs[0]
        else:
            runs.append(cur)
    runs = [r for r in runs if len(r) > 3]
    tips = 0
    if runs:
        ys = np.array([p[1] for p in max(runs, key=len)])
        prom = SHAPE_PARAMS["tip_prominence"] * (ys.max() - top)
        for j in range(1, len(ys) - 1):
            if ys[j] >= ys[j - 1] and ys[j] > ys[j + 1] and ys[j] - max(ys[:j].min(), ys[j + 1:].min()) > prom:
                tips += 1
    lab = np.stack(_lab(crop), -1)[ring]
    ink = _hex(np.median(lab, axis=0)) if len(lab) else None
    # [his look at 117 drawn from its map, 2026-10-02: the edges "not looking 3D"] its edge as the picture lights it
    # [his rules, 2026-10-02, rule 3] the sides of the product the band reaches, in the picture
    sides = _edge_sides(inside, mask[cy0:cy1, cx0:cx1], SHAPE_PARAMS["edge_touch_px"])
    relief = _band_relief(crop, inside, gold > 0, width_px, band.get("colour"), top_closed=bool(band.get("rule_above")),
                          sides=sides, reach_px=SHAPE_PARAMS["bleed_reach"] * w)
    # [his look at 117 drawn from its map, 2026-10-02] the arches between its drips, their colour down the picture
    arches = _arch_colours(crop, mask[cy0:cy1, cx0:cx1], inside, width_px, band.get("field_below"))
    if arches is not None:
        arches["rows"] = [round((cy0 + arches["rows"][0] - y0) / h, 5), round((cy0 + arches["rows"][1] - y0) / h, 5)]
    def frac_cubics(polys):
        return [[[frac([ring[0]])[0]] + [[v for pair in frac([seg[0:2], seg[2:4], seg[4:6]]) for v in pair]
                                         for seg in ring[1:]] for ring in poly] for poly in polys]
    layered = ({"relief": {"layers": [dict(layer, outline=frac(layer["outline"]),
                                           **({"cubics": frac_cubics(layer["cubics"])} if layer.get("cubics") else {}))
                                      for layer in relief["layers"]],
                           "widths_px": relief["widths_px"]}} if relief else {})
    return {"part": band.get("name"), "fill": band.get("colour"), "outline": frac(whole), "edge": [frac(r) for r in runs],
            "edge_width": round(width_px / w, 5), "edge_ink": ink, "drips": tips, **layered,
            **({"arches": arches} if arches is not None else {}),
            # [his word of 2026-10-02: a shape the picture shows whole kept whole in the bleed] the edge drips made whole
            **({"edge_drips_whole": relief["edge_drips_whole"]} if relief and "edge_drips_whole" in relief else {}),
            # [his rules, 2026-10-02, rule 3] the sides it runs edge to edge on, the rows it reaches them on, and how far
            # past them it is drawn (a share of the product's width)
            **({"edges": {side: [round((cy0 + a - y0) / h, 5), round((cy0 + b - y0) / h, 5)]
                          for side, (a, b) in sides.items()},
                "bleed_reach": SHAPE_PARAMS["bleed_reach"]} if sides else {})}


def _plain_band(img, mask, pbox, band: dict, crop_box) -> dict:
    """[His answer of 2026-10-05, W2: "build it. Plain stripes are basic."] A band with no gold edge — a stripe of one
    colour across the product — traced as the picture prints it: the rows where its colour (within shape_ink_de of its
    measured colour) holds band_row_share of its box's width, one run of them; its ends, the columns its colour holds in
    those rows; its top and foot straight across to within band_foot_px on all but band_bent_share of its columns — else
    it is a band whose gold edge the picture breaks, refused and never drawn flat. Its outline the rectangle those make,
    pushed into the bleed on a side it runs edge to edge on (his rules, rule 3), sampled straight so the smooth line
    the front draws through it stays straight. A band with no edge: ``edge`` empty and no ink, so no motif is expected
    of it (``undrawn_parts``)."""
    import cv2
    import numpy as np
    if not band.get("colour"):
        return {"refused": "a band with no gold edge and no measured colour: not read as a plain stripe"}
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    cx0, cy0, cx1, cy1 = crop_box
    lab = np.stack(_lab(img[cy0:cy1, cx0:cx1]), -1)
    hx = band["colour"]
    rgb = np.array([int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)], np.uint8).reshape(1, 1, 3)[..., ::-1]
    target = np.stack(_lab(np.ascontiguousarray(rgb)), -1)[0, 0]
    on = (np.sqrt(((lab - target) ** 2).sum(-1)) < SHAPE_PARAMS["shape_ink_de"]) & (mask[cy0:cy1, cx0:cx1] > 0)
    bx0 = max(0, int(x0 + band["box"][0] * w) - cx0)
    bx1 = min(on.shape[1], int(x0 + band["box"][2] * w) - cx0)
    if bx1 - bx0 < 3:
        return {"refused": "a plain stripe's box is narrower than three pixels"}
    # what is printed ON the stripe (a name, a mark) is a hole its colour surrounds: the stripe's own, filled
    n_, holes = cv2.connectedComponents((~on).astype(np.uint8), connectivity=4)
    edge = set(np.unique(np.concatenate([holes[0], holes[-1], holes[:, 0], holes[:, -1]])).tolist())
    on = on | ~np.isin(holes, sorted(edge))
    cov = on[:, bx0:bx1].mean(axis=1)
    full = cov >= SHAPE_PARAMS["band_row_share"]
    ys = np.nonzero(full)[0]
    if not len(ys):
        return {"refused": "no gold edge, and no row of its colour across its box: not a plain stripe"}
    run = max(np.split(ys, np.nonzero(np.diff(ys) > 1)[0] + 1), key=len)
    r0, r1 = int(run[0]), int(run[-1])

    def spill(rows):
        n = 0
        for y in rows:
            if cov[y] < SHAPE_PARAMS["band_bent_share"]:
                break
            n += 1
        return n
    # its colour running on past its top or its foot — a drip, a wave — is a band whose edge the picture breaks
    spilled = max(spill(range(r1 + 1, on.shape[0])), spill(range(r0 - 1, -1, -1)))
    if spilled > SHAPE_PARAMS["band_foot_px"]:
        return {"refused": "its gold edge is open and its top or foot is not straight across: its colour runs on %d "
                           "pixels past it — not a plain stripe" % spilled}
    cols = np.nonzero(on[r0:r1 + 1].mean(axis=0) >= 0.5)[0]
    c0, c1 = int(cols.min()), int(cols.max())
    sub_ = on[r0:r1 + 1, c0:c1 + 1]
    held = sub_.any(axis=0)
    first = np.argmax(sub_, axis=0)
    last = sub_.shape[0] - 1 - np.argmax(sub_[::-1], axis=0)
    bent = ((first > SHAPE_PARAMS["band_foot_px"]) | (last < sub_.shape[0] - 1 - SHAPE_PARAMS["band_foot_px"])) & held
    if bent.mean() > SHAPE_PARAMS["band_bent_share"]:
        return {"refused": "its gold edge is open and its top or foot is not straight across: not a plain stripe "
                           "(%.0f %% of its columns bend)" % (100 * bent.mean())}
    inside = np.zeros(on.shape, np.uint8)
    inside[r0:r1 + 1, c0:c1 + 1] = 1
    sides = _edge_sides(inside, mask[cy0:cy1, cx0:cx1], SHAPE_PARAMS["edge_touch_px"])
    left, right = float(c0), float(c1 + 1)
    if "left" in sides:                                # [his rules, rule 3] edge to edge: into the bleed
        left -= SHAPE_PARAMS["bleed_reach"] * w
    if "right" in sides:
        right += SHAPE_PARAMS["bleed_reach"] * w
    top, foot = float(r0), float(r1 + 1)
    step = SHAPE_PARAMS["smooth_step_px"]

    def along(a, b):
        n = max(2, int(np.hypot(b[0] - a[0], b[1] - a[1]) / step) + 1)
        return [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for t in np.linspace(0.0, 1.0, n)][:-1]
    corners = [(left, top), (right, top), (right, foot), (left, foot)]
    pts = [p for i in range(4) for p in along(corners[i], corners[(i + 1) % 4])]

    def frac(p):
        return [round(float(cx0 + p[0] - x0) / w, 5), round(float(cy0 + p[1] - y0) / h, 5)]
    return {"part": band.get("name"), "fill": band.get("colour"), "outline": [frac(p) for p in pts], "edge": [],
            "drips": 0, "plain": True,
            **({"edges": {side: [round(float(cy0 + a - y0) / h, 5), round(float(cy0 + b - y0) / h, 5)]
                          for side, (a, b) in sides.items()},
                "bleed_reach": SHAPE_PARAMS["bleed_reach"]} if sides else {})}


def trace_rule(img, mask, pbox, rule: dict) -> dict:
    """A gold rule across the product (117's under its upper field): its rows — the rows of its box where gold holds
    the rule's middle — and its ends — the gold of those rows, inside the product; its ink measured; or
    ``{"refused": why}``."""
    import numpy as np
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    cx0, cy0, cx1, cy1 = _crop(img, pbox, rule["box"])
    crop = img[cy0:cy1, cx0:cx1]
    gold = _gold(crop) & (mask[cy0:cy1, cx0:cx1] > 0)
    mid = slice(int(0.3 * gold.shape[1]), int(0.7 * gold.shape[1]))
    rows = np.nonzero(gold[:, mid].mean(axis=1) >= SHAPE_PARAMS["rule_rows"])[0]
    if not len(rows):
        return {"refused": "no row of its box is gold across its middle"}
    r0, r1 = int(rows.min()), int(rows.max())
    cols = np.nonzero(gold[r0:r1 + 1].any(axis=0))[0]
    lab = np.stack(_lab(crop), -1)[r0:r1 + 1][gold[r0:r1 + 1]]
    c0, c1 = int(cols.min()), int(cols.max())
    # [his rules, 2026-10-02, rule 3: "EDGE TO EDGE MEANS BLEED"] the sides of the product its gold reaches, and its box
    # run past them by bleed_reach of the product's width
    held = np.zeros_like(gold)
    held[r0:r1 + 1] = gold[r0:r1 + 1]
    sides = _edge_sides(held, mask[cy0:cy1, cx0:cx1] > 0, SHAPE_PARAMS["edge_touch_px"])
    box_ = [round(float(cx0 + c0 - x0) / w, 5), round(float(cy0 + r0 - y0) / h, 5),
            round(float(cx0 + c1 + 1 - x0) / w, 5), round(float(cy0 + r1 + 1 - y0) / h, 5)]
    # [his last goal before the pitch, 2026-10-16, Step 2; his D (11) for 126: "the two gold frame lines" — its hairline
    # passing the gold test only across its middle, traced a quarter of the label long and 0.12 mm thick] a rule whose
    # gold runs under rule_span_least of the read's own box runs the read's width, and never thinner than rule_min_px
    if (c1 - c0 + 1) < SHAPE_PARAMS["rule_span_least"] * (float(rule["box"][2]) - float(rule["box"][0])) * w:
        box_[0], box_[2] = round(float(rule["box"][0]), 5), round(float(rule["box"][2]), 5)
    if (r1 - r0 + 1) < SHAPE_PARAMS["rule_min_px"]:
        middle = (box_[1] + box_[3]) / 2.0
        half = SHAPE_PARAMS["rule_min_px"] / 2.0 / h
        box_[1], box_[3] = round(middle - half, 5), round(middle + half, 5)
    run = [box_[0] - SHAPE_PARAMS["bleed_reach"] * ("left" in sides), box_[1],
           box_[2] + SHAPE_PARAMS["bleed_reach"] * ("right" in sides), box_[3]]
    return {"part": rule.get("name"), **({"edges": sorted(sides), "drawn_box": [round(v, 5) for v in run]}
                                         if sides else {}),
            "box": box_,
            "ink": _hex(np.median(lab, axis=0)),
            # [his look at 117 drawn from its map, 2026-10-02] its light and its shade, as the picture lights it
            "ink_lit": _pick(lab, 85.0), "ink_shade": _pick(lab, 20.0)}


def trace_scatter(img, mask, pbox, motif: dict, others: list) -> dict:
    """A motif scattered as small gold shapes (117's four-point sparkle stars), read across the product's width over its
    box's height padded by SHAPE_PARAMS["scatter_pad"]: each shape found by a small gold core (the tracer's own gold, at
    most star_core_max of the width — never a band's long edge) and grown at most star_reach along the paler gold it fades
    through, so a faint star keeps its rays and a pale highlight with no gold core is never one; kept when its size,
    proportion and fill are a star's, it is not cut by the read's edge and its centre is not inside another part's box
    (``others``: the type and the mark). Each: its outline and its core's ink, as fractions of the product."""
    import cv2
    import numpy as np
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    pad = SHAPE_PARAMS["scatter_pad"]
    rx0, rx1 = int(x0), int(x1)
    ry0 = max(0, int(y0 + (motif["box"][1] - pad) * h))
    ry1 = min(img.shape[0], int(y0 + (motif["box"][3] + pad) * h))
    crop = img[ry0:ry1, rx0:rx1]
    L, A, B = _lab(crop)
    inside = mask[ry0:ry1, rx0:rx1] > 0
    core = _gold(crop) & inside
    pale = ((B > A + SHAPE_PARAMS["star_pale_b_over_a"]) & (B > SHAPE_PARAMS["star_pale_b_min"])
            & (L > SHAPE_PARAMS["gold_l_min"]) & inside)
    nc, ccc, cst, _c = cv2.connectedComponentsWithStats(core.astype(np.uint8), 8)
    small = np.isin(ccc, [i for i in range(1, nc) if max(cst[i, cv2.CC_STAT_WIDTH], cst[i, cv2.CC_STAT_HEIGHT])
                          <= SHAPE_PARAMS["star_core_max"] * w])
    reach = max(3, int(round(SHAPE_PARAMS["star_reach"] * w)))
    grown = (pale & (cv2.dilate(small.astype(np.uint8), np.ones((2 * reach + 1,) * 2, np.uint8)) > 0)) | small
    n, cc, st, cent = cv2.connectedComponentsWithStats(grown.astype(np.uint8), 8)
    lo, hi = SHAPE_PARAMS["star_size"]
    a_lo, a_hi = SHAPE_PARAMS["star_aspect"]
    stars, cores = [], []
    for i in range(1, n):
        bw, bh = int(st[i, cv2.CC_STAT_WIDTH]), int(st[i, cv2.CC_STAT_HEIGHT])
        top, left = int(st[i, cv2.CC_STAT_TOP]), int(st[i, cv2.CC_STAT_LEFT])
        if top == 0 or left == 0 or top + bh >= crop.shape[0] or left + bw >= crop.shape[1]:
            continue                                                   # cut by the read's edge: part of something else
        if not (lo * w <= max(bw, bh) <= hi * w and a_lo <= bw / float(bh) <= a_hi):
            continue
        if st[i, cv2.CC_STAT_AREA] > SHAPE_PARAMS["star_fill_max"] * bw * bh:
            continue
        fx, fy = (rx0 + cent[i][0] - x0) / w, (ry0 + cent[i][1] - y0) / h
        if any(o["box"][0] <= fx <= o["box"][2] and o["box"][1] <= fy <= o["box"][3] for o in others):
            continue                                                   # among another part's: that part's own
        fit = _sparkle_fit(img, rx0 + cent[i][0], ry0 + cent[i][1], hi * w, (bw, bh))
        if fit is None:
            continue
        cores.append(np.stack(_lab(crop), -1)[(cc == i) & core])
        stars.append({"centre": [round((fit["cx"] - x0) / w, 5), round((fit["cy"] - y0) / h, 5)],
                      "half": [round(fit["half_w"] / w, 5), round(fit["half_h"] / h, 5)], "pinch_fit": fit["pinch"]})
    if not stars:
        return {"refused": "no small gold shape with a gold core in its reach"}
    # [his look: small designs never "inconsistent"] one motif, one sparkle: the pinch its sparkles share, the median of
    # theirs; each drawn as that shape at its own centre and reach, its outline sampled from it
    from apps.ire import sparkle_glyph
    pinch = float(np.median([st["pinch_fit"] for st in stars]))
    for st in stars:
        (fcx, fcy), (fhw, fhh) = st["centre"], st["half"]
        st["outline"] = [[round(px, 5), round(py, 5)]
                         for px, py in sparkle_glyph.outline(fcx, fcy, fhw, fhh, pinch, sparkle_glyph.HOUSE_TIP, 6)]
    # [his narrowing: "it shouldn't care about ... the lighting"] one motif, one gold under different lights: ONE ink,
    # the median over every shape's core — each star read alone gave 117 nine inks, #B47A52 to #F2CB87
    ink = _hex(np.median(np.concatenate(cores), axis=0))
    for star in stars:
        star["ink"] = ink
    # [his look at 117 drawn from its map, 2026-10-02: "3D"] its darker rim and its lit heart, over all its cores
    lit_ink, shade_ink = _pick(np.concatenate(cores), 85.0), _pick(np.concatenate(cores), 20.0)
    return {"part": motif.get("name"), "stars": stars, "count": len(stars), "count_read": motif.get("count"),
            "ink": ink, "ink_lit": lit_ink, "ink_shade": shade_ink,
            "glyph": {"kind": "four-point sparkle", "pinch": round(pinch, 3), "tip": sparkle_glyph.HOUSE_TIP,
                                  "by": "the median of its sparkles' own, each fitted on the picture"}}


def _sparkle_fit(img, cx: float, cy: float, reach: float, found: tuple) -> dict | None:
    """[His look at 117 drawn from its map, 2026-10-02.] One sparkle of the picture round ``(cx, cy)`` (its pixels), as
    the one sparkle shape (apps/ire/sparkle_glyph.py): on its difference from the ground round it, its centre where its
    arms cross and each arm as far as the difference holds SHAPE_PARAMS["star_arm_share"] of the sparkle's strongest,
    unbroken from the centre and never past star_arm_reach of the box ``found`` it was found in ((width, height),
    pixels: a sparkle beside a drip's gold line is never read into the line); and the pinch, of star_pinches, whose arms are as wide as its gold's at star_arm_at of
    their reach — its yellowness above the ground, so never its pale halo, less the picture's own softening
    (star_soften_px, in quadrature). None where no arm stands out."""
    import cv2
    import numpy as np

    from apps.ire import sparkle_glyph
    r = int(reach / 2.0) + 3
    x0, y0 = int(round(cx)) - r, int(round(cy)) - r
    if x0 < 0 or y0 < 0 or x0 + 2 * r + 1 > img.shape[1] or y0 + 2 * r + 1 > img.shape[0]:
        return None
    lab = np.stack(_lab(img[y0:y0 + 2 * r + 1, x0:x0 + 2 * r + 1]), -1)
    ground = np.median(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]), axis=0)
    diff = np.sqrt(((lab - ground) ** 2).sum(axis=-1))
    peak = float(diff[r - 2:r + 3, r - 2:r + 3].max())
    if peak <= 0.0:
        return None
    on = diff >= SHAPE_PARAMS["star_arm_share"] * peak
    n, cc, _st, _c = cv2.connectedComponentsWithStats(on.astype(np.uint8), 8)
    centre = cc[r - 2:r + 3, r - 2:r + 3]
    if not (centre > 0).any():
        return None
    mine = cc == int(np.bincount(centre[centre > 0]).argmax())
    ys, xs = np.nonzero(mine)
    weight = diff[mine]
    col, row = int(round(float(np.average(xs, weights=weight)))), int(round(float(np.average(ys, weights=weight))))

    def run(line, at, most):
        a = b = at
        while a > 0 and line[a - 1] and at - a < most:
            a -= 1
        while b < len(line) - 1 and line[b + 1] and b - at < most:
            b += 1
        return a, b
    if not mine[row, col]:
        return None
    va, vb = run(mine[:, col], row, int(SHAPE_PARAMS["star_arm_reach"] * found[1]))
    ha, hb = run(mine[row, :], col, int(SHAPE_PARAMS["star_arm_reach"] * found[0]))
    half_w, half_h = (hb - ha + 1) / 2.0, (vb - va + 1) / 2.0
    fx, fy = (ha + hb + 1) / 2.0, (va + vb + 1) / 2.0
    gold = np.clip(lab[..., 2] - ground[2], 0.0, None).astype(np.float32)
    soften = SHAPE_PARAMS["star_soften_px"]
    widths = []
    for along in SHAPE_PARAMS["star_arm_at"]:
        for sx, sy, own, across, upright in ((0, -1, half_h, half_w, True), (0, 1, half_h, half_w, True),
                                             (1, 0, half_w, half_h, False), (-1, 0, half_w, half_h, False)):
            px, py = fx - 0.5 + sx * own * along, fy - 0.5 + sy * own * along
            vals = np.array([cv2.getRectSubPix(gold, (1, 1), ((px + t, py) if upright else (px, py + t)))[0, 0]
                             for t in range(-3, 4)], dtype=float)
            if vals.max() > 0.0:
                seen = vals.sum() / vals.max()
                widths.append((along, own, across, max(seen * seen - soften * soften, 0.0) ** 0.5))
    if not widths:
        return None
    best = None
    for pinch in SHAPE_PARAMS["star_pinches"]:
        err = sum((sparkle_glyph.arm_width(across, own, pinch, sparkle_glyph.HOUSE_TIP, along) - w) ** 2
                  for along, own, across, w in widths)
        if best is None or err < best[0]:
            best = (err, pinch)
    return {"cx": x0 + fx - 0.5, "cy": y0 + fy - 0.5, "half_w": half_w, "half_h": half_h, "pinch": best[1]}


def _ground_share(lab, keep, ink: str, ground: str | None) -> float:
    """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (2): "a
    concept shown as drawable must draw".] The share of a traced solid's pixels the picture prints nearer its ground's
    colour than the solid's own ink — 0.0 where no ground is read. A solid in a pale ink close to its ground takes the
    ground in with it (both inside shape_ink_de): Blossom Arch's oval, read in its line art's pink, traced as the whole
    pale ground round its rose."""
    import numpy as np
    if not ground:
        return 0.0

    def target(hx):
        rgb = np.array([int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)], np.uint8).reshape(1, 1, 3)[..., ::-1]
        return np.stack(_lab(np.ascontiguousarray(rgb)), -1)[0, 0]
    inside = keep.astype(bool)
    px = lab[inside]
    if not len(px):
        return 0.0
    to_ink = np.sqrt(((px - target(ink)) ** 2).sum(-1))
    to_ground = np.sqrt(((px - target(ground)) ** 2).sum(-1))
    return round(float((to_ground < to_ink).mean()), 4)


def trace_shape(img, mask, pbox, part: dict, ground: str | None, others: list, exact: bool = False) -> dict:
    """[The owner's finding on design 119, 2026-10-03 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 32898c7): "Every panel
    is vector, drawn from the concept's map: front as the concept shows it".] A solid graphic the picture prints in one
    colour (119's berry vial silhouette), traced: the pixels within SHAPE_PARAMS["shape_ink_de"] of its measured ink
    inside its box, padded, on the product; its pieces of at least shape_min_share of the largest; a hole in it kept
    where it is at least shape_hole_px square, holds the ground's colour (``ground``) and lies under none of ``others``
    (the parts printed on it: a name, a mark — they are drawn over it), else filled; its outline smoothed over
    shape_smooth_px and refit as the fewest cubics (``_cubic_rings``). ``{"part", "ink", "box", "cubics",
    "holes_kept", "holes_filled"}`` in the product's fractions, or ``{"refused": why}``.
    [His goal after the pitch page, 2026-10-15, A (4).] ``exact`` — a further ink of a shape (``shape_layers``): its
    pixels inside the part's own box only, never in its pad, and none inside ``others``' boxes (132's flower's blue
    took the tops of the CITRUS beneath it)."""
    import cv2
    import numpy as np
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    if not part.get("colour"):
        return {"refused": "no measured ink"}
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    cx0, cy0, cx1, cy1 = _crop(img, pbox, part["box"])
    lab = np.stack(_lab(img[cy0:cy1, cx0:cx1]), -1)

    def near(hx):
        rgb = np.array([int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)], np.uint8).reshape(1, 1, 3)[..., ::-1]
        target = np.stack(_lab(np.ascontiguousarray(rgb)), -1)[0, 0]
        return np.sqrt(((lab - target) ** 2).sum(-1)) < SHAPE_PARAMS["shape_ink_de"]
    ink = (near(part["colour"]) & (mask[cy0:cy1, cx0:cx1] > 0)).astype(np.uint8)
    if exact:
        own = np.zeros(ink.shape, bool)
        own[max(0, int(y0 + part["box"][1] * h) - cy0):max(0, int(y0 + part["box"][3] * h) - cy0 + 1),
            max(0, int(x0 + part["box"][0] * w) - cx0):max(0, int(x0 + part["box"][2] * w) - cx0 + 1)] = True
        for other in others:
            own[max(0, int(y0 + other["box"][1] * h) - cy0):max(0, int(y0 + other["box"][3] * h) - cy0),
                max(0, int(x0 + other["box"][0] * w) - cx0):max(0, int(x0 + other["box"][2] * w) - cx0)] = False
        ink = (ink.astype(bool) & own).astype(np.uint8)
    n, cc, st, _cent = cv2.connectedComponentsWithStats(ink, 8)
    if n < 2:
        return {"refused": "no pixel of its ink in its box"}
    big = st[1:, cv2.CC_STAT_AREA].max()
    keep = np.isin(cc, [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= SHAPE_PARAMS["shape_min_share"] * big])
    keep = keep.astype(np.uint8)
    ground_px = near(ground) if ground else np.zeros(keep.shape, bool)
    under = np.zeros(keep.shape, bool)
    for other in others:
        ox0, oy0 = int(x0 + other["box"][0] * w) - cx0, int(y0 + other["box"][1] * h) - cy0
        ox1, oy1 = int(x0 + other["box"][2] * w) - cx0, int(y0 + other["box"][3] * h) - cy0
        under[max(0, oy0):max(0, oy1), max(0, ox0):max(0, ox1)] = True
    m, holes = cv2.connectedComponents((1 - keep).astype(np.uint8), connectivity=4)
    border = set(np.unique(np.concatenate([holes[0], holes[-1], holes[:, 0], holes[:, -1]])).tolist())
    kept = filled = 0
    side = SHAPE_PARAMS["shape_hole_px"]
    for i in range(1, m):
        if i in border:
            continue
        hole = holes == i
        if hole.sum() >= side * side and ground_px[hole].mean() > 0.5 and under[hole].mean() < 0.5:
            kept += 1
            continue
        keep[hole] = 1
        filled += 1
    contours, tree = cv2.findContours(keep, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    polys = []
    for i, c in enumerate(contours):
        if tree[0][i][3] != -1 or len(c) < 8:
            continue
        rings, j = [], tree[0][i][2]
        while j != -1:
            if len(contours[j]) >= 8:
                rings.append(_clean_ring(contours[j][:, 0, :] + 0.5))         # [his rule 4] clean curves
            j = tree[0][j][0]
        poly = Polygon(_clean_ring(c[:, 0, :] + 0.5), rings).buffer(0)
        if not poly.is_empty:
            polys.append(poly)
    if not polys:
        return {"refused": "nothing of its ink large enough to trace"}
    geom = unary_union(polys)
    fitted = _cubic_rings(geom, SHAPE_PARAMS["shape_curve_tol_px"])                # [his rule 4] fewer, cleaner cubics

    def frac(p):
        return [round((cx0 + float(p[0]) - x0) / w, 5), round((cy0 + float(p[1]) - y0) / h, 5)]

    def as_cubics(rings_):
        return [[[frac(ring[0])] + [frac(seg[0:2]) + frac(seg[2:4]) + frac(seg[4:6]) for seg in ring[1:]]
                 for ring in poly] for poly in rings_]
    # [his review of 119, 2026-10-05, point 5] the rim the picture draws round the shape, read in rings past its blur
    rim = None
    if ground:
        whole = np.zeros_like(keep)
        cv2.drawContours(whole, cv2.findContours(keep, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0], -1, 1, -1)
        dt = cv2.distanceTransform((1 - whole).astype(np.uint8), cv2.DIST_L2, 5)

        def target_lab(hx):
            rgb = np.array([int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)], np.uint8).reshape(1, 1, 3)[..., ::-1]
            return np.stack(_lab(np.ascontiguousarray(rgb)), -1)[0, 0]
        far_g = np.sqrt(((lab - target_lab(ground)) ** 2).sum(-1)) > SHAPE_PARAMS["shape_rim_de"]
        far_i = np.sqrt(((lab - target_lab(part["colour"])) ** 2).sum(-1)) > SHAPE_PARAMS["shape_rim_de"]
        other = far_g & far_i & (mask[cy0:cy1, cx0:cx1] > 0)
        bands, first_share = [], 0.0                  # [(its first ring's colour, its pixels, its rings)]
        for d in range(1, int(SHAPE_PARAMS["shape_rim_max_px"]) + 1):
            ring = (dt >= d + 0.5) & (dt < d + 1.5)
            if not ring.any() or float(other[ring].mean()) < 0.5:
                break
            colour = np.median(lab[ring & other], axis=0)
            if not bands:
                if float(other[ring].mean()) < SHAPE_PARAMS["shape_rim_share"]:
                    break
                first_share = float(other[ring].mean())
                bands.append([colour, np.zeros(other.shape, bool), 0])
            elif float(np.sqrt(((colour - bands[-1][0]) ** 2).sum())) > SHAPE_PARAMS["shape_rim_ring_de"]:
                if len(bands) == 2:
                    break
                bands.append([colour, np.zeros(other.shape, bool), 0])
            bands[-1][1] |= ring & other
            bands[-1][2] += 1
        if bands:
            drawn_bands, reach = [], 0.5              # from the shape's own edge outward, band by band
            for _colour, pixels, rings_n in bands:
                reach += rings_n
                band = geom.buffer(reach, quad_segs=16)
                drawn_bands.append({"ink": _hex(np.median(lab[pixels], axis=0)), "width": round(reach / w, 5),
                                    "width_px": reach,
                                    "cubics": as_cubics(_cubic_rings(band, SHAPE_PARAMS["shape_curve_tol_px"]))})
            rim = dict(drawn_bands[0], share=round(first_share, 2))
            if len(drawn_bands) == 2:
                rim["outer"] = drawn_bands[1]           # the edge's shadow, outside the rim
    cubics = as_cubics(fitted)
    # [his review of 119, 2026-10-05, point 4: "Nothing inside the safe margin"] the shape's box is everything it draws —
    # its rim's outer band where it has one, every point of its cubics, their control points too (the curve never
    # leaves their hull): measured on 119, the geometric outline's box left the shadow band's curves 0.12 mm past the
    # front's safe margin once fitted to it
    drawn = cubics
    if rim is not None:
        drawn = rim["cubics"]
        if "outer" in rim:
            drawn = rim["outer"]["cubics"]
    xs = [float(seg[i]) for poly in drawn for ring in poly for seg in ring for i in range(0, len(seg), 2)]
    ys = [float(seg[i]) for poly in drawn for ring in poly for seg in ring for i in range(1, len(seg), 2)]
    return {"part": part.get("name"), "ink": part["colour"],
            "box": [round(min(xs), 5), round(min(ys), 5), round(max(xs), 5), round(max(ys), 5)],
            "cubics": cubics, **({"rim": rim} if rim is not None else {}),
            "holes_kept": kept, "holes_filled": filled, "ground_share": _ground_share(lab, keep, part["colour"], ground)}


def shape_layers(img, mask, pbox, part: dict, ground: str | None, others: list) -> tuple:
    """[His goal after the pitch page, 2026-10-15, A (4): "every element in the concept is drawn (132's centre
    flower …)".] A shape the read gives a second ink (132's flower: its gold disc, its blue outline and leaves) traced in
    that ink too, as a layer drawn over its first — ``([{"ink", "cubics", "box"}], [problems])``. None where the second
    ink is the first under another light (``_one_colour_under_two_lights``: "colours never from shadow"), or the
    ground's own colour (the petals are left the ground's colour, as the picture prints them on it)."""
    second = part.get("second_colour")
    if not second or not part.get("colour"):
        return [], []
    second_lab, first_lab = _hex_lab(second), _hex_lab(part["colour"])
    if _one_colour_under_two_lights(first_lab, second_lab):
        return [], []
    if ground and math.dist(_hex_lab(ground), second_lab) < SHAPE_PARAMS["shape_ink_de"]:
        return [], []
    got = trace_shape(img, mask, pbox, dict(part, colour=second), None,
                      [p for p in others if p.get("box") and not _inside(part["box"], p["box"])], exact=True)
    if "refused" in got:
        return [], ["shape %r, its second ink %s: %s" % (part.get("name"), second, got["refused"])]
    return [{"ink": second, "cubics": got["cubics"], "box": got["box"]}], []


def _hex_lab(hx: str) -> tuple:
    """(L*, a*, b*) of one hex colour, as ``_lab`` reads a pixel."""
    import numpy as np
    h = str(hx).lstrip("#")
    lab = _lab(np.uint8([[[int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)]]]))
    return tuple(float(c[0, 0]) for c in lab)


#: [His go of 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md), item 3: "Small text lines never need reading off the picture:
#: product name, type line, Arabic, size and the logo are SET from my brief and the approved logo, placed where the
#: picture shows them."] a line or a mark whose ink the map cannot measure is set in the box the read gave it — its ink
#: the pixels of that box that stand apart from its surface (at least SET_INK_DE from the box's median), their core,
#: where SET_MIN_PX of them stand; else the nearest traced line's
SET_INK_DE = 14.0
SET_MIN_PX = 6
SET_CORE_SHARE = 0.3
#: … and said so on the line
SET_FROM_BOX = ("set where the picture shows it, in the box the read gave it — its letters too small to measure "
                "(his go of 2026-10-08, item 3)")


def _set_in_box(img, mask, pbox, part: dict) -> dict:
    """[His go of 2026-10-08, item 3.] A part placed in the box the read gave it, never traced from the picture's
    letters: ``{"box", "ink" (or None), "set"}`` — its ink the core of the box's pixels that stand apart from its
    surface, where enough of them do."""
    import numpy as np
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    bx0, by0, bx1, by1 = part["box"]
    cx0, cx1 = max(0, int(x0 + bx0 * w)), min(img.shape[1], int(x0 + bx1 * w) + 1)
    cy0, cy1 = max(0, int(y0 + by0 * h)), min(img.shape[0], int(y0 + by1 * h) + 1)
    out = {"box": [round(float(v), 5) for v in part["box"]], "ink": None, "set": SET_FROM_BOX}
    if cx1 <= cx0 or cy1 <= cy0:
        return out
    lab = np.stack(_lab(img[cy0:cy1, cx0:cx1]), -1)
    on = mask[cy0:cy1, cx0:cx1] > 0
    if not on.any():
        return out
    surface = np.median(lab[on], axis=0)
    far = np.sqrt(((lab - surface) ** 2).sum(-1))
    apart = (far >= SET_INK_DE) & on
    if int(apart.sum()) < SET_MIN_PX:
        return out
    mine, dist = lab[apart], far[apart]
    core = mine[dist >= np.percentile(dist, 100.0 * (1.0 - SET_CORE_SHARE))]
    out["ink"] = _hex(np.median(core, axis=0))
    return out


#: [his go of 2026-10-08] two set lines are one where their rows share at least this much of the shorter's height and
#: the gap between them is at most JOIN_GAP of the product's width
JOIN_ROW_SHARE = 0.5
JOIN_GAP = 0.03


def _join_rows(types: list) -> None:
    """[His go of 2026-10-08.] Each set line (``SET_FROM_BOX``) that shares its row with the set line before it and
    touches it joined to it, in place: the first takes both boxes and both readings ("seen"); the second is said
    ``joined_to`` the first, and set with it."""
    lines = sorted((t for t in types if t.get("set") and t.get("box")),
                   key=lambda t: (round((float(t["box"][1]) + float(t["box"][3])) / 2.0, 2), float(t["box"][0])))
    head = None
    for t in lines:
        if head is not None:
            share = min(float(head["box"][3]), float(t["box"][3])) - max(float(head["box"][1]), float(t["box"][1]))
            tall = min(float(head["box"][3]) - float(head["box"][1]), float(t["box"][3]) - float(t["box"][1]))
            gap = float(t["box"][0]) - float(head["box"][2])
            if tall > 0 and share >= JOIN_ROW_SHARE * tall and gap <= JOIN_GAP:
                head["seen"] = "%s %s" % (head.get("seen"), t.get("seen"))
                head["box"] = [min(head["box"][0], t["box"][0]), min(head["box"][1], t["box"][1]),
                               max(head["box"][2], t["box"][2]), max(head["box"][3], t["box"][3])]
                t["joined_to"] = head["part"]
                continue
        head = t


def _ink_beside(part: dict, traced: list):
    """The ink of the traced line or mark nearest ``part`` (by the middles of their boxes, up and down first) — what a
    set line takes where its own box holds none; None where nothing is traced."""
    inked = [t for t in traced if t.get("ink") and t.get("box") and t is not part]
    if not inked:
        return None
    my = (float(part["box"][1]) + float(part["box"][3])) / 2.0
    mx = (float(part["box"][0]) + float(part["box"][2])) / 2.0
    near = min(inked, key=lambda t: (abs((float(t["box"][1]) + float(t["box"][3])) / 2.0 - my),
                                     abs((float(t["box"][0]) + float(t["box"][2])) / 2.0 - mx)))
    return near["ink"]


def trace_mark(img, mask, pbox, mark: dict) -> dict:
    """The house mark as the picture prints it (117's gold BBROSE): the box of its gold ink inside its box, padded — the
    shape is never taken from the picture, only its place and size (the mark is drawn from its approved master)."""
    import numpy as np
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    cx0, cy0, cx1, cy1 = _crop(img, pbox, mark["box"])
    gold = _gold(img[cy0:cy1, cx0:cx1]) & (mask[cy0:cy1, cx0:cx1] > 0)
    words = " ".join(str(mark[k]) for k in ("finish", "name") if mark.get(k)).lower()
    # its own ink named gold or foil — never the gold it stands on (130's "cobalt ink on gold")
    named_gold = re.search(r"(?<!on )\b(gold|foil)\b", words) is not None
    if mark.get("colour") and not is_gold_hex(mark["colour"]) and not named_gold:
        # [his goal after the pitch page, B (10): the lotion tube's red-brown BBROSE on its sunny yellow, drawn yellow —
        # its ground passed the gold test] a mark the map reads in another ink — and never names gold or foil (124's
        # "gold foil" mark, its ink read mauve) — is never its ground's gold
        gold = np.zeros(gold.shape, bool)
    if not gold.any() and mark.get("colour"):
        # [the owner's finding on design 119, 2026-10-03: every printed part drawn, or the design stops] a mark the
        # picture prints in another ink: the pixels of its own measured ink
        hx = mark["colour"]
        rgb = np.array([int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)], np.uint8).reshape(1, 1, 3)[..., ::-1]
        target = np.stack(_lab(np.ascontiguousarray(rgb)), -1)[0, 0]
        lab_crop = np.stack(_lab(img[cy0:cy1, cx0:cx1]), -1)
        gold = (np.sqrt(((lab_crop - target) ** 2).sum(-1)) < SHAPE_PARAMS["type_ink_de"]) & (
            mask[cy0:cy1, cx0:cx1] > 0)
    ys, xs = np.nonzero(gold)
    if not len(xs):
        # [his go of 2026-10-08, item 3: "the logo ... SET from ... the approved logo, placed where the picture shows
        # it"] the approved logo in the box the read gave it, never refused for the ink the map cannot measure
        return {"part": mark.get("name"), **_set_in_box(img, mask, pbox, mark)}
    lab = np.stack(_lab(img[cy0:cy1, cx0:cx1]), -1)[gold]
    return {"part": mark.get("name"), "box": [round(float(cx0 + xs.min() - x0) / w, 5), round(float(cy0 + ys.min() - y0) / h, 5),
                                              round(float(cx0 + xs.max() + 1 - x0) / w, 5),
                                              round(float(cy0 + ys.max() + 1 - y0) / h, 5)],
            "ink": _hex(np.median(lab, axis=0))}


def _named_ink(lab, inside, read: str, part: dict) -> str | None:
    """[His last goal before the pitch, 2026-10-16, Step 2: "fonts, metals and colours as the concept shows" — 128's
    "GLASS", read "white screen-print", its ink measured #A1A5A8, the grey of its thin white strokes blended into the
    aqua] a line whose map words name it white (or black) in its finish or its name is printed in its box's lightest
    (or darkest) pixels — SHAPE_PARAMS["type_named_share"] of them — where its read ink plainly is not (L* under
    ``type_white_l``, or over ``type_black_l``); else None."""
    import numpy as np
    words = " ".join(str(part[k]) for k in ("finish", "name") if part.get(k)).lower()
    white, black = re.search(r"\bwhite\b", words) is not None, re.search(r"\bblack\b", words) is not None
    if white == black or not inside.any():
        return None
    rgb = np.array([int(read[1:3], 16), int(read[3:5], 16), int(read[5:7], 16)], np.uint8).reshape(1, 1, 3)[..., ::-1]
    level = float(np.stack(_lab(np.ascontiguousarray(rgb)), -1)[0, 0][0])
    mine = lab[inside]
    share = 100.0 * SHAPE_PARAMS["type_named_share"]
    if white and level < SHAPE_PARAMS["type_white_l"]:
        return _hex(np.median(mine[mine[:, 0] >= np.percentile(mine[:, 0], 100.0 - share)], axis=0))
    if black and level > SHAPE_PARAMS["type_black_l"]:
        return _hex(np.median(mine[mine[:, 0] <= np.percentile(mine[:, 0], share)], axis=0))
    return None


def _ink_off_its_ground(img, mask, crop, lab, read: str) -> str | None:
    """[His goal after the pitch page, B (10): the lotion tube's "Comfort", its read ink #DCB975 — the honey dipper's —
    within a few ΔE of its sunny yellow ground, so its letters were drawn near-yellow where the concept prints them dark
    brown] the letters' own ink where the read's is not theirs: the box's ground the median of a ring just outside it
    (``type_ground_ring`` of its height, inside the product — a tight box's own border lies on its letters); the
    letters the median of the box's pixels farthest from that ground (``type_core_share`` of them); the read not theirs
    where it lies within SHAPE_PARAMS["type_ink_ground_de"] of the ground and the letters twice that far, or far from
    the letters, which stand farther from the ground than it by that much. Else None (the read stands)."""
    import numpy as np
    cx0, cy0, cx1, cy1 = crop
    inside = mask[cy0:cy1, cx0:cx1] > 0
    pad = max(2, int(round(SHAPE_PARAMS["type_ground_ring"] * (cy1 - cy0))))
    H, W = mask.shape[:2]
    ox0, oy0, ox1, oy1 = max(0, cx0 - pad), max(0, cy0 - pad), min(W, cx1 + pad), min(H, cy1 + pad)
    outer = np.stack(_lab(img[oy0:oy1, ox0:ox1]), -1)
    ring = (mask[oy0:oy1, ox0:ox1] > 0).copy()
    ring[cy0 - oy0:cy1 - oy0, cx0 - ox0:cx1 - ox0] = False
    if not ring.any() or not inside.any():
        return None
    ground = np.median(outer[ring], axis=0)
    rgb = np.array([int(read[1:3], 16), int(read[3:5], 16), int(read[5:7], 16)], np.uint8).reshape(1, 1, 3)[..., ::-1]
    target = np.stack(_lab(np.ascontiguousarray(rgb)), -1)[0, 0]
    bar = SHAPE_PARAMS["type_ink_ground_de"]
    mine = lab[inside]
    far = np.sqrt(((mine - ground) ** 2).sum(-1))
    core = mine[far >= np.percentile(far, 100.0 * (1.0 - SHAPE_PARAMS["type_core_share"]))]
    letters = np.median(core, axis=0)
    read_off = float(np.sqrt(((target - ground) ** 2).sum()))
    letters_off = float(np.sqrt(((letters - ground) ** 2).sum()))
    # the read lies on the ground; or it lies far from the letters, which stand much farther from the ground than it
    # (139's "Comfort": its read tan 38 from the yellow, its dark brown letters 55 or more)
    on_ground = read_off < bar and letters_off >= 2.0 * bar
    elsewhere = float(np.sqrt(((target - letters) ** 2).sum())) >= 2.0 * bar and letters_off >= read_off + bar
    if not (on_ground or elsewhere):
        return None
    return _hex(letters)


def trace_type(img, mask, pbox, part: dict) -> dict:
    """``_trace_type``, every answer keeping the turn its part is read at (142's tall script, its read giving no ink —
    an early answer had dropped its turn)."""
    got = _trace_type(img, mask, pbox, part)
    if part.get("rotation") in (90, -90) and "rotation" not in got:
        got = dict(got, rotation=part["rotation"])
    return got


def _trace_type(img, mask, pbox, part: dict) -> dict:
    """A type line's place and size as the picture prints it: the box of its ink — the pixels within
    SHAPE_PARAMS["type_ink_de"] of its measured ink — inside its box, padded; its words are never read here
    (``type_sources``)."""
    import numpy as np
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    cx0, cy0, cx1, cy1 = _crop(img, pbox, part["box"])
    lab = np.stack(_lab(img[cy0:cy1, cx0:cx1]), -1)
    # its own measured ink only: a second ink (a contour round a fill) can lie as near the ground as the ink lies to
    # it — 117's script's #D8A089 is within the bar of its soft pink ground over 78 % of its box
    inks = [c for c in (part.get("colour"),) if c]
    if not inks:
        # [his go of 2026-10-08, item 3] set where the picture shows it, in its source's words (``type_sources``)
        return {"part": part.get("name"), "lettering": part.get("lettering"), "seen": part.get("seen_text"),
                "ink_read": part.get("colour"), **_style_of(part), **_set_in_box(img, mask, pbox, part)}
    reread = _ink_off_its_ground(img, mask, (cx0, cy0, cx1, cy1), lab, inks[0])
    if reread is not None:
        inks = [reread]
    named = _named_ink(lab, mask[cy0:cy1, cx0:cx1] > 0, inks[0], part)
    if named is not None:
        inks = [named]
    near = np.zeros(lab.shape[:2], bool)
    for hx in inks:
        rgb = np.array([int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)], np.uint8).reshape(1, 1, 3)[..., ::-1]
        target = np.stack(_lab(np.ascontiguousarray(rgb)), -1)[0, 0]
        near |= np.sqrt(((lab - target) ** 2).sum(-1)) < SHAPE_PARAMS["type_ink_de"]
    near &= mask[cy0:cy1, cx0:cx1] > 0
    # the line's own ink, both ways: its rows — the runs of inked rows (SHAPE_PARAMS["type_row_gap"] blank rows end one)
    # lying mostly inside the read's rows, so a neighbouring line of the same ink is not this line's — and its shapes —
    # each (a letter, a dot) centred within the read's rows, so a star above or a line below touching its rows is not
    import cv2
    top, foot = y0 + part["box"][1] * h - cy0, y0 + part["box"][3] * h - cy0
    rows = near.sum(axis=1) > 0
    keep = np.zeros_like(rows)
    i, gap = 0, SHAPE_PARAMS["type_row_gap"]
    while i < len(rows):
        if not rows[i]:
            i += 1
            continue
        j, last = i, i
        while j < len(rows) and (rows[j] or j - last <= gap):
            if rows[j]:
                last = j
            j += 1
        if max(0.0, min(last + 1, foot) - max(i, top)) >= 0.5 * (last + 1 - i):
            keep[i:last + 1] = True
        i = last + 1
    n, cc, _st, cent = cv2.connectedComponentsWithStats(near.astype(np.uint8), 8)
    near = near & keep[:, None] & np.isin(cc, [k for k in range(1, n) if top <= cent[k][1] <= foot])
    caps_rows = None
    seen_caps = [ch for ch in (part.get("seen_text") if isinstance(part.get("seen_text"), str) else "") if ch.isalpha()]
    if (seen_caps and all(ch.isascii() and ch.isupper() for ch in seen_caps)
            and part.get("lettering") not in ("script", "display") and part.get("rotation") not in (90, -90)):
        # [his goal of 2026-10-12, (7): ""EYESHADOW PALETTE" as small spaced capitals, as the concept shows"] a line of
        # capitals stands in one band of rows its letters fill — the densest — never the ground its ink's tolerance
        # also takes in round it (124's pink sky round its mauve capitals: 49 rows read for its 12)
        counts = near.sum(axis=1)
        if counts.any():
            peak = int(counts.argmax())
            floor = SHAPE_PARAMS["type_caps_band"] * counts[peak]
            a, b = peak, peak
            while a > 0 and counts[a - 1] >= floor:
                a -= 1
            while b < len(counts) - 1 and counts[b + 1] >= floor:
                b += 1
            band = np.zeros(len(counts), bool)
            band[a:b + 1] = True
            caps_rows = band                     # its box only: its ink and its weight read as before
    ys, xs = np.nonzero(near)
    if not len(xs):
        # [his go of 2026-10-08, item 3] its ink not where the read measured it (149's size line, read in the cap's
        # colour): set where the picture shows it, its ink the pixels that stand apart in its box
        return {"part": part.get("name"), "lettering": part.get("lettering"), "seen": part.get("seen_text"),
                "ink_read": part.get("colour"), **_style_of(part), **_set_in_box(img, mask, pbox, part)}
    # [his review of 119, 2026-10-05, point 4: "Set it in the concept's weight (bold, berry)."] its ink and its weight as
    # its letters print them
    edge = sum(cv2.arcLength(c, True) for c in cv2.findContours(near.astype(np.uint8), cv2.RETR_LIST,
                                                                  cv2.CHAIN_APPROX_NONE)[0])
    stroke = 2.0 * float(near.sum()) / max(float(edge), 1.0)
    ink = inks[0]
    ground = None
    if (~near).any():
        ground = np.median(lab[~near], axis=0)
    # a line set as type, read thin — never a script's or a display line's lettering, drawn in its own layers' inks
    plain = part.get("lettering") not in ("script", "display") and part.get("rotation") not in (90, -90)
    if plain and stroke < SHAPE_PARAMS["type_thin_stroke_px"] and ground is not None:
        mine = lab[near]
        far = np.sqrt(((mine - ground) ** 2).sum(-1))
        core = mine[far >= np.percentile(far, 100.0 * (1.0 - SHAPE_PARAMS["type_core_share"]))]
        ink = _hex(np.median(core, axis=0))
    seen = part.get("seen_text")
    if not isinstance(seen, str):
        seen = ""
    letters = [ch for ch in seen if ch.isalpha()]
    weight, stroke_em = None, None
    if ground is not None and letters and all(ch.isascii() and ch.isupper() for ch in letters):
        rgb = np.array([int(ink[1:3], 16), int(ink[3:5], 16), int(ink[5:7], 16)], np.uint8).reshape(1, 1, 3)[..., ::-1]
        target = np.stack(_lab(np.ascontiguousarray(rgb)), -1)[0, 0]
        span = float(np.sqrt(((target - ground) ** 2).sum()))
        rows_on = keep[:, None] & np.ones(near.shape, bool)
        alpha = np.clip(np.sqrt(((lab - ground) ** 2).sum(-1)) / max(span, 1e-6), 0.0, 1.0) * rows_on
        alpha[alpha < 0.15] = 0.0
        half = (alpha >= 0.5).astype(np.uint8)
        rows = np.nonzero(half.any(axis=1))[0]
        if len(rows) and rows.max() - rows.min() + 1 >= SHAPE_PARAMS["type_weight_min_px"]:
            outline = sum(cv2.arcLength(c, True) for c in cv2.findContours(half, cv2.RETR_LIST,
                                                                             cv2.CHAIN_APPROX_NONE)[0])
            stroke_em = 2.0 * float(alpha.sum()) / max(float(outline), 1.0) / float(rows.max() - rows.min() + 1)
            weight = "regular"
            if stroke_em >= SHAPE_PARAMS["type_bold_stroke_em"]:
                weight = "bold"
    box = _ink_box(near if caps_rows is None else near & caps_rows[:, None], cx0, cy0, x0, y0, w, h)
    share = SHAPE_PARAMS["type_ink_min_height"]
    sliver = part.get("rotation") not in (90, -90) and (
        (box[3] - box[1]) < share * (float(part["box"][3]) - float(part["box"][1]))
        or (box[2] - box[0]) < share * (float(part["box"][2]) - float(part["box"][0])))
    words = str(part.get("seen_text")).strip()
    if sliver and part.get("seen_text"):
        # a shrunk trace whose shape is a line of its words (a loose read's box round real letters) is its letters
        whole = _ink_box(near, cx0, cy0, x0, y0, w, h)                  # all its ink, never only its capitals' band
        aspect = (whole[2] - whole[0]) * w / max(1e-6, (whole[3] - whole[1]) * h)
        natural = SHAPE_PARAMS["type_em_per_char"] * len(words)
        factor = SHAPE_PARAMS["type_sliver_aspect"]
        sliver = not (natural / factor <= aspect <= natural * factor)
        if not sliver:
            # [his goal after the pitch page, B (9): 138's very wide-spaced light capitals, their densest rows one
            # crossbar high — its name boxed 0.08 % of the product tall and its front's type never set] the letters' own
            # box, all their ink, where their capitals' band is a sliver of them
            box = whole
    if sliver:
        # [his review of 127, 130, 131 and 132, 2026-10-15, C (6): "132's name is tiny and split"] ink a sliver of the
        # line the read saw — a thin rule of the same ink, never its letters (132's "CITRUS": 0.8 % of the front read
        # for 7 %) — the line is set in the read's own box, at its size
        held = _set_in_box(img, mask, pbox, part)
        return {"part": part.get("name"), "lettering": part.get("lettering"), "seen": part.get("seen_text"),
                "ink": held["ink"] if held["ink"] else ink, "ink_read": part.get("colour"), **_style_of(part),
                "box": held["box"], "set": held["set"], "ink_sliver": [round(float(v), 5) for v in box]}
    return {"part": part.get("name"), "lettering": part.get("lettering"), "seen": part.get("seen_text"),
            "ink": ink, "ink_read": part.get("colour"), "second_ink": part.get("second_colour"),
            **({"weight": weight, "stroke_em": round(stroke_em, 3)} if weight else {}),
            **({"rotation": part["rotation"]} if part.get("rotation") in (90, -90) else {}), **_style_of(part),
            "box": box}


def _style_of(part) -> dict:
    """[His goal after the pitch page, A (1)] the line's lettering style and spacing as its read named them, carried to
    the drawing that sets it (``ire.lettering_faces``)."""
    out = {}
    if isinstance(part.get("style"), dict) and part["style"]:
        out["style"] = dict(part["style"])
    if part.get("spacing") in TYPE_STYLE_SPACINGS:
        out["spacing"] = part["spacing"]
    return out


def _ink_box(near, cx0, cy0, x0, y0, w, h) -> list:
    """The box of a line's ink, in the product's shares."""
    import numpy as np
    ys, xs = np.nonzero(near)
    return [round(float(cx0 + xs.min() - x0) / w, 5), round(float(cy0 + ys.min() - y0) / h, 5),
            round(float(cx0 + xs.max() + 1 - x0) / w, 5), round(float(cy0 + ys.max() + 1 - y0) / h, 5)]


def trace_script(img, mask, pbox, line: dict) -> dict:
    """[His answer after test day finding 3, (3): "the script lettering also traced from the picture".] A type line the
    picture letters in script, traced: its measured ink inside its traced box (``trace_type``), read at
    SHAPE_PARAMS["script_upscale"] times full size and traced by potrace — ``{"svg": potrace's own SVG, "frame": [fx0,
    fy0, kx, ky]}``, a point (u, v) of the SVG's outlines lying at ``(fx0 + u * kx, fy0 + v * ky)`` of the product's
    box; or ``{"refused": why}`` (no potrace on this machine, or nothing traced)."""
    import shutil
    import subprocess
    import tempfile

    import cv2
    import numpy as np
    binary = shutil.which("potrace")
    if binary is None:
        return {"refused": "potrace is not on this machine"}
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    pad = 4
    cx0, cy0 = max(0, int(x0 + line["box"][0] * w) - pad), max(0, int(y0 + line["box"][1] * h) - pad)
    cx1 = min(img.shape[1], int(x0 + line["box"][2] * w) + pad)
    cy1 = min(img.shape[0], int(y0 + line["box"][3] * h) + pad)
    lab = np.stack(_lab(img[cy0:cy1, cx0:cx1]), -1)
    hx = line["ink"]
    rgb = np.array([int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)], np.uint8).reshape(1, 1, 3)[..., ::-1]
    target = np.stack(_lab(np.ascontiguousarray(rgb)), -1)[0, 0]
    ink = (np.sqrt(((lab - target) ** 2).sum(-1)) < SHAPE_PARAMS["type_ink_de"]) & (mask[cy0:cy1, cx0:cx1] > 0)
    if not ink.any():
        return {"refused": "no pixel of its ink to trace"}
    k = int(SHAPE_PARAMS["script_upscale"])
    up = cv2.resize(ink.astype(np.uint8) * 255, None, fx=k, fy=k, interpolation=cv2.INTER_LINEAR)
    r = int(SHAPE_PARAMS["script_close_px"])
    if r:
        up = cv2.morphologyEx(up, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    up = up > 127
    with tempfile.TemporaryDirectory() as d:
        with open(d + "/ink.pbm", "wb") as f:
            f.write(("P4\n%d %d\n" % (up.shape[1], up.shape[0])).encode()
                    + np.packbits(up.astype(np.uint8), axis=1).tobytes())
        subprocess.run([binary, "-s", "--flat", "-t", str(SHAPE_PARAMS["potrace_turdsize"]),
                        "-a", str(SHAPE_PARAMS["potrace_alphamax"]), "-O", str(SHAPE_PARAMS["potrace_opttolerance"]),
                        d + "/ink.pbm", "-o", d + "/ink.svg"], check=True, capture_output=True, timeout=60)
        with open(d + "/ink.svg", encoding="utf-8") as f:
            svg = f.read()
    return {"svg": svg, "frame": [round((cx0 - x0) / w, 6), round((cy0 - y0) / h, 6), 1.0 / (k * w), 1.0 / (k * h)]}


def _potrace(binary, mask) -> str:
    """potrace's own SVG of ``mask`` (True is ink), with the tracer's parameters."""
    import subprocess
    import tempfile

    import numpy as np
    with tempfile.TemporaryDirectory() as d:
        with open(d + "/ink.pbm", "wb") as f:
            f.write(("P4\n%d %d\n" % (mask.shape[1], mask.shape[0])).encode()
                    + np.packbits(mask.astype(np.uint8), axis=1).tobytes())
        subprocess.run([binary, "-s", "--flat", "-t", str(SHAPE_PARAMS["potrace_turdsize"]),
                        "-a", str(SHAPE_PARAMS["potrace_alphamax"]), "-O", str(SHAPE_PARAMS["potrace_opttolerance"]),
                        d + "/ink.pbm", "-o", d + "/ink.svg"], check=True, capture_output=True, timeout=60)
        with open(d + "/ink.svg", encoding="utf-8") as f:
            return f.read()


def _holes(mask) -> int:
    """How many holes ``mask`` (1 is the letter) encloses."""
    import cv2
    import numpy as np
    inv = (1 - mask).astype(np.uint8)
    n, cc = cv2.connectedComponents(inv, connectivity=4)
    border = set(np.unique(np.concatenate([cc[0], cc[-1], cc[:, 0], cc[:, -1]]).tolist()))
    return len([i for i in range(1, n) if i not in border])


def _fill_thin_holes(mask, widest: float) -> tuple:
    """``(mask, how many filled)``: every hole ``mask`` encloses whose widest point (its inscribed circle's radius, in
    ``mask``'s pixels) is under ``widest``, filled — a slit; a hole wider, kept — an eye."""
    import cv2
    import numpy as np
    inv = (1 - mask).astype(np.uint8)
    n, cc = cv2.connectedComponents(inv, connectivity=4)
    border = set(np.unique(np.concatenate([cc[0], cc[-1], cc[:, 0], cc[:, -1]]).tolist()))
    reach = cv2.distanceTransform(inv, cv2.DIST_L2, 5)
    out, filled = mask.copy(), 0
    for i in range(1, n):
        if i in border:
            continue
        hole = cc == i
        if float(reach[hole].max()) < widest:
            out[hole] = 1
            filled += 1
    return out, filled


#: [his look at 117 drawn from its map, 2026-10-02] a script's layers, drawn in this order, back to front
LETTERING_LAYERS = ("outer", "ring", "ring-shade", "inline", "body")


def trace_lettering(img, mask, pbox, line: dict) -> dict:
    """[His look at 117 drawn from its map, 2026-10-02: "the edges of the text, it's looking not um, constant ... The
    highlighting is not looking good".] A script line's lettering as the picture layers it, rebuilt from ONE smooth
    letter shape: the letters' bodies are the regions the gold ring encloses (found on the ring closed, at least
    lettering_body_min_px each, grown back to the ring, smoothed over lettering_smooth_px), and every layer is an EVEN
    offset of them, measured on the picture in shells round that shape — the gold ring as far as gold holds
    lettering_ring_share of a shell, split where its lightness passes half way from its bronze to its lit side; the pale
    outer line and the pale inline, where they stand lettering_bright_l lighter than what lies beyond, as far as a shell
    stays lighter than half way between them. Each layer
    traced by potrace at lettering_upscale and coloured by the picture's own pixels in its band (the lit ring and the
    pale lines by their lightest, the bronze by its darkest — a band two or three pixels wide blends its neighbours at
    its edges; the letter by its median). ``{"layers": [{"name", "ink", "svg"}] (LETTERING_LAYERS, back to front),
    "frame", "widths_px"}`` in trace_script's frame, or ``{"refused": why}``."""
    import shutil

    import cv2
    import numpy as np
    binary = shutil.which("potrace")
    if binary is None:
        return {"refused": "potrace is not on this machine"}
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    pad = 8
    cx0, cy0 = max(0, int(x0 + line["box"][0] * w) - pad), max(0, int(y0 + line["box"][1] * h) - pad)
    cx1 = min(img.shape[1], int(x0 + line["box"][2] * w) + pad)
    cy1 = min(img.shape[0], int(y0 + line["box"][3] * h) + pad)
    crop = img[cy0:cy1, cx0:cx1]
    L, A, B = _lab(crop)
    lo, hi = SHAPE_PARAMS["lettering_shade_l"]
    gold = _gold(crop) | ((B > SHAPE_PARAMS["lettering_shade_b_min"]) & (B > A - 2.0) & (L > lo) & (L < hi))
    k = int(SHAPE_PARAMS["lettering_upscale"])
    ring = cv2.GaussianBlur(cv2.resize(gold.astype(np.uint8) * 255, None, fx=k, fy=k,
                                       interpolation=cv2.INTER_LINEAR), (0, 0), 0.3 * k) > 127
    c = int(SHAPE_PARAMS["lettering_close_px"])
    ring = cv2.morphologyEx(ring.astype(np.uint8), cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (c, c)))
    free = (1 - ring).astype(np.uint8)
    n, cc, st, _c = cv2.connectedComponentsWithStats(cv2.erode(free, cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (c - 2, c - 2))), connectivity=4)
    edge = set(np.unique(np.concatenate([cc[0], cc[-1], cc[:, 0], cc[:, -1]]).tolist()))
    least = SHAPE_PARAMS["lettering_body_min_px"] * k * k
    body = np.isin(cc, [i for i in range(1, n) if i not in edge and st[i, cv2.CC_STAT_AREA] >= least])
    if not body.any():
        return {"refused": "no letter the gold ring encloses"}
    body = body.astype(np.uint8)
    for _ in range(c // 2):
        body = cv2.dilate(body, np.ones((3, 3), np.uint8)) & free                  # grown back to the ring
    body, filled = _fill_thin_holes(body, SHAPE_PARAMS["lettering_hole_px"] * k)
    # [his second look at 117: "not as smooth as the reference"] the letter's edge the picture's own: where its
    # lightness, read finer by a smooth interpolation, passes half way from the ring's to the letter's
    fine_l = cv2.resize(L.astype(np.float32), None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
    small_body = cv2.resize(body, (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_AREA) > 0.5
    edge_l = (float(np.median(L[gold])) + float(np.median(L[small_body & ~gold]))) / 2.0

    def disc(px):
        r = max(1, int(round(px * k)))
        return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    snapped = ((fine_l > edge_l).astype(np.uint8) & cv2.dilate(body, disc(SHAPE_PARAMS["lettering_snap_px"]))) | \
        cv2.erode(body, disc(SHAPE_PARAMS["lettering_core_px"]))
    nn, sc = cv2.connectedComponents(snapped, connectivity=4)
    held = np.unique(sc[body > 0])
    snapped = np.isin(sc, held[held > 0]).astype(np.uint8)            # never an island of light off a letter
    snapped = cv2.morphologyEx(snapped, cv2.MORPH_CLOSE, disc(SHAPE_PARAMS["lettering_notch_px"]))
    snapped, refilled = _fill_thin_holes(snapped, SHAPE_PARAMS["lettering_hole_px"] * k)
    body = (cv2.GaussianBlur(snapped.astype(float), (0, 0), SHAPE_PARAMS["lettering_smooth_px"] * k) > 0.5)
    body = body.astype(np.uint8)
    eyes = _holes(body)
    out = cv2.distanceTransform(1 - body, cv2.DIST_L2, 5) / k               # picture px outside the letter
    inn = cv2.distanceTransform(body, cv2.DIST_L2, 5) / k                    # … and inside it
    small = (crop.shape[1], crop.shape[0])
    out_px = cv2.resize(out, small, interpolation=cv2.INTER_AREA)
    in_px = cv2.resize(inn, small, interpolation=cv2.INTER_AREA)
    shell = SHAPE_PARAMS["lettering_shell_px"]
    bright = SHAPE_PARAMS["lettering_bright_l"]

    def shells(dist, upto):
        return [(d0, (dist > d0) & (dist <= d0 + shell)) for d0 in np.arange(0.0, upto, shell)]
    near = cv2.dilate(body, np.ones((16 * k + 1, 16 * k + 1), np.uint8))   # 8 px round the letters: what lies beyond
    near = cv2.resize(near, small, interpolation=cv2.INTER_NEAREST) > 0
    beyond = float(np.median(L[near & (out_px > 6.0)]))
    ring_out, profile = 0.0, []
    for d0, m in shells(out_px, 6.0):
        m = m & near
        if not m.any():
            break
        profile.append((d0, float(gold[m].mean()), float(np.median(L[m]))))
    start = None
    for d0, share, _l in profile:
        if share >= SHAPE_PARAMS["lettering_ring_share"]:
            start = d0 if start is None else start
            ring_out = d0 + shell
        elif start is not None or d0 >= 2.0:
            break                  # the ring is the gold just outside the letter: unbroken, within two pixels of it
    if start is None:
        return {"refused": "no gold ring round the letters to measure"}
    in_ring = [(d0, lv) for d0, share, lv in profile if start <= d0 < ring_out]
    mid = (min(lv for _d, lv in in_ring) + max(lv for _d, lv in in_ring)) / 2.0
    split = next((d0 for d0, lv in in_ring if lv >= mid), ring_out / 2.0)
    pale_out = ring_out
    past = [lv for d0, _share, lv in profile if ring_out <= d0 < ring_out + 3.0]
    if past and max(past) >= beyond + bright:
        half = (max(past) + beyond) / 2.0                       # the pale line's edge: half way to what lies beyond
        top = max((lv, d0) for d0, _share, lv in profile if ring_out <= d0 < ring_out + 3.0)[1]
        for d0, _share, lv in profile:
            if d0 >= top:                                     # from its lightest shell outward, while it holds
                if lv < half:
                    break
                pale_out = d0 + shell
    letter = float(np.median(L[in_px > 3.0])) if (in_px > 3.0).any() else float(np.median(L[in_px > 1.0]))
    inline = 0.0
    inside = [(d0, float(np.median(L[m]))) for d0, m in shells(in_px, 3.0) if m.any()]
    if inside and max(lv for _d, lv in inside) >= letter + bright:
        half = (max(lv for _d, lv in inside) + letter) / 2.0       # the inline's edge: half way to the letter
        top = max((lv, d0) for d0, lv in inside)[1]
        for d0, lv in inside:
            if d0 >= top and lv < half:                       # from its lightest shell inward, while it holds
                break
            inline = d0 + shell
    # the pale inline reaches out to where the ring begins: the letter's own edge, as the smoothing put it, lies in it
    inline += start
    lab = np.stack((L, A, B), -1)

    def pick(m, q):
        v = lab[m]
        cut = np.percentile(v[:, 0], q)
        return _hex(np.median(v[np.abs(v[:, 0] - cut) <= 3.0], axis=0))
    edge_in = inline - start                                     # the inline's depth inside the letter's edge
    bands = {"outer": ((out_px > ring_out) & (out_px <= pale_out), 90.0),
             "ring": ((out_px > split) & (out_px <= ring_out), 80.0),
             "ring-shade": ((out_px > start) & (out_px <= split), 20.0),
             "inline": (((in_px > 0.0) & (in_px <= edge_in)) | ((out_px > 0.0) & (out_px <= start)), 90.0),
             "body": (in_px > edge_in, 50.0)}
    fine = {"outer": out <= pale_out, "ring": out <= ring_out, "ring-shade": out <= split,
            "inline": out <= start, "body": inn > edge_in}
    layers = []
    for name in LETTERING_LAYERS:
        band, q = bands[name]
        if not band.any() or not fine[name].any():
            continue
        layers.append({"name": name, "ink": pick(band, q), "svg": _potrace(binary, fine[name])})

    # [his rules for cloning a design from a picture, 2026-10-02, rule 1: "LETTERING IS SET, NOT TRACED"] the letters set
    # in the face that comes closest, in the words the picture shows — the composer draws them only where those are the
    # record's own words — each layer as even an offset of them as the picture layers its own; or why they are traced
    def frac(p):
        return [round((cx0 + float(p[0]) - x0) / w, 5), round((cy0 + float(p[1]) - y0) / h, 5)]
    lettering_set = _set_lettering(body, k, line["seen"] if "seen" in line else "",
                                   {"outer": pale_out, "ring": ring_out, "split": float(split), "inline": start,
                                    "body": edge_in},
                                   {layer["name"]: layer["ink"] for layer in layers}, frac)
    return {"layers": layers, "frame": [round((cx0 - x0) / w, 6), round((cy0 - y0) / h, 6), 1.0 / (k * w),
                                        1.0 / (k * h)],
            "widths_px": {"ring": round(ring_out - start, 2), "ring_split": round(float(split) - start, 2),
                          "outer": round(pale_out - ring_out, 2), "inline": round(inline, 2)},
            "edge_l": round(edge_l, 1), "slits_filled": filled + refilled, "eyes": eyes, "set": lettering_set}


#: [his rules for cloning a design from a picture, 2026-10-02, rule 1: "LETTERING IS SET, NOT TRACED: closest real script
#: font (granted, or a licensed one proposed), exact words, then the picture's outline, fill, colours, size and placement;
#: trace only when no font comes close, and say so"] what the lettering's record says it was drawn from
LETTERING_SET = "SET"
LETTERING_TRACED = "TRACED"


def _glyph_contours(font, gname: str) -> list:
    """A glyph's contours in font units (y up), each a list of points, its curves flattened."""
    from fontTools.pens.basePen import BasePen

    class Flat(BasePen):
        def __init__(self, glyphs):
            super().__init__(glyphs)
            self.contours, self.cur = [], []

        def _moveTo(self, p):
            self.cur = [p]

        def _lineTo(self, p):
            self.cur.append(p)

        def _curveToOne(self, p1, p2, p3):
            p0 = self.cur[-1]
            for j in range(1, 9):
                u, v = j / 8.0, 1.0 - j / 8.0
                self.cur.append((v ** 3 * p0[0] + 3 * v * v * u * p1[0] + 3 * v * u * u * p2[0] + u ** 3 * p3[0],
                                 v ** 3 * p0[1] + 3 * v * v * u * p1[1] + 3 * v * u * u * p2[1] + u ** 3 * p3[1]))

        def _qCurveToOne(self, p1, p2):
            p0 = self.cur[-1]
            for j in range(1, 7):
                u, v = j / 6.0, 1.0 - j / 6.0
                self.cur.append((v * v * p0[0] + 2 * v * u * p1[0] + u * u * p2[0],
                                 v * v * p0[1] + 2 * v * u * p1[1] + u * u * p2[1]))

        def _closePath(self):
            if len(self.cur) >= 3:
                self.contours.append(self.cur)
            self.cur = []

        _endPath = _closePath
    glyphs = font.getGlyphSet()
    pen = Flat(glyphs)
    glyphs[gname].draw(pen)
    return pen.contours


def _pair_kerning(font) -> dict:
    """``{(left glyph, right glyph): x advance}`` — the font's GPOS pair adjustments (formats 1 and 2) under its 'kern'
    feature; empty where it has none."""
    out = {}
    if "GPOS" not in font:
        return out
    table = font["GPOS"].table
    if not table.FeatureList or not table.LookupList:
        return out
    wanted = {i for rec in table.FeatureList.FeatureRecord if rec.FeatureTag == "kern" for i in rec.Feature.LookupListIndex}
    order = list(font.getGlyphOrder())
    for li in sorted(wanted):
        lookup = table.LookupList.Lookup[li]
        if lookup.LookupType not in (2, 9):
            continue
        subs = [s.ExtSubTable for s in lookup.SubTable] if lookup.LookupType == 9 else list(lookup.SubTable)
        for st in subs:
            if not hasattr(st, "Format") or not hasattr(st, "Coverage"):
                continue
            # [Day 7, D-D7-1] the GRANTED pool brought faces whose pair subtables are incomplete (a Format 1 subtable
            # without PairSet, class records shorter than their class definitions): such a subtable contributes no
            # kerning rather than failing the whole measurement — the line is then measured with the pairs the font does
            # carry, as the emitter would set it
            if st.Format == 1:
                for first, pairs in zip(st.Coverage.glyphs, getattr(st, "PairSet", None) or []):
                    for rec in getattr(pairs, "PairValueRecord", None) or []:
                        v = rec.Value1
                        if v is not None and hasattr(v, "XAdvance") and v.XAdvance:
                            out.setdefault((first, rec.SecondGlyph), v.XAdvance)
            elif st.Format == 2:
                if not all(hasattr(st, a) for a in ("ClassDef1", "ClassDef2", "Class1Record")):
                    continue
                # a glyph a class definition does not list is in class 0, by the OpenType specification
                c1 = {g: 0 for g in st.Coverage.glyphs}
                c1.update(st.ClassDef1.classDefs)
                c2 = {g: 0 for g in order}
                c2.update(st.ClassDef2.classDefs)
                for first in st.Coverage.glyphs:
                    if c1[first] >= len(st.Class1Record):
                        continue
                    row = st.Class1Record[c1[first]]
                    for second in order:
                        if c2[second] >= len(row.Class2Record):
                            continue
                        v = row.Class2Record[c2[second]].Value1
                        if v is not None and hasattr(v, "XAdvance") and v.XAdvance:
                            out.setdefault((first, second), v.XAdvance)
    return out


def _set_line(font, kern: dict, text: str):
    """``text`` set in ``font`` — its glyphs at their advances, the font's pair kerning between them — as one shape in
    font units, y down from the baseline; None where a character has no glyph in it."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    x, prev, glyphs = 0.0, None, []
    for ch in text:
        if ord(ch) not in cmap:
            return None
        g = cmap[ord(ch)]
        if prev is not None and (prev, g) in kern:
            x += kern[(prev, g)]
        outers, holes = [], []
        for c in _glyph_contours(font, g):
            pts = [(px + x, -py) for px, py in c]
            area = 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))
            poly = Polygon(pts).buffer(0)
            if not poly.is_empty:
                # an outline's outside runs clockwise with y up, so the other way once y points down; a hole the reverse
                (outers if area > 0 else holes).append(poly)
        if outers:
            # each glyph's own counters cut from that glyph alone — where script letters overlap, one letter's eye
            # never cuts into the next
            glyph = unary_union(outers)
            glyphs.append(glyph.difference(unary_union(holes)) if holes else glyph)
        x += hmtx[g][0]
        prev = g
    if not glyphs:
        return None
    return unary_union(glyphs)


def _fill(shape, size, scale: float, dx: float, dy: float):
    """``shape`` scaled by ``scale`` about the origin and moved by (dx, dy), filled on a grid of ``size`` (h, w)."""
    import cv2
    import numpy as np
    out = np.zeros(size, np.uint8)
    polys = list(shape.geoms) if hasattr(shape, "geoms") else [shape]
    for poly in sorted(polys, key=lambda p: -p.area):
        if poly.geom_type != "Polygon" or poly.is_empty:
            continue
        cv2.fillPoly(out, [(np.asarray(poly.exterior.coords) * scale + (dx, dy)).round().astype(np.int32)], 1)
        for hole in poly.interiors:
            cv2.fillPoly(out, [(np.asarray(hole.coords) * scale + (dx, dy)).round().astype(np.int32)], 0)
    return out


def _fit_set(target, shape, fine: bool, as_drawn: bool = False) -> tuple:
    """How closely ``shape`` (a line set in a face: font units, y down) covers ``target`` (the picture's letters on that
    line, a mask): scaled so its width is the letters' ink width (and four per cent either side), centred on them,
    grown by up to 32 mask pixels for the picture's weight, moved a little — the best IoU, and where it was found.
    ``as_drawn`` (his rule 3, 2026-10-05): a face that is not the picture's own is set as the face draws it — never
    grown, and scaled to the narrower of the letters' ink width and height, so it never stands taller than they do."""
    import cv2
    import numpy as np
    ys, xs = np.nonzero(target)
    tx0, ty0, tx1, ty1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    gx0, gy0, gx1, gy1 = shape.bounds
    t = target.astype(bool)
    best = (0.0, {})
    grows = range(0, 33, 4)
    if as_drawn:
        grows = (0,)
    for ds in ((0.96, 1.0, 1.04) if fine else (1.0,)):
        s = (tx1 - tx0) / (gx1 - gx0)
        if as_drawn:
            s = min(s, (ty1 - ty0) / (gy1 - gy0))
        s *= ds
        dx0 = (tx0 + tx1) / 2.0 - s * (gx0 + gx1) / 2.0
        dy0 = (ty0 + ty1) / 2.0 - s * (gy0 + gy1) / 2.0
        base = _fill(shape, target.shape, s, dx0, dy0)
        for r in grows:
            g = cv2.dilate(base, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))) if r else base
            for dy in ((-12, -6, 0, 6, 12) if fine else (0,)):
                for dx in ((-12, -6, 0, 6, 12) if fine else (0,)):
                    m = np.roll(np.roll(g, dy, axis=0), dx, axis=1).astype(bool)
                    inter, union = int((m & t).sum()), int((m | t).sum())
                    if union and inter / union > best[0]:
                        best = (inter / union, {"scale": s, "dx": dx0 + dx, "dy": dy0 + dy, "grow": r, "inter": inter,
                                                "union": union, "mask": m})
    if best[1]:
        best[1]["outline"] = _outline_agreement(best[1].pop("mask"), t, 1.5 * SHAPE_PARAMS["lettering_upscale"])
    return best


def _outline_agreement(a, b, tol: float) -> float:
    """How much of two masks' outlines lie on each other: the share of each one's outline within ``tol`` mask pixels of
    the other's, the two shares' harmonic mean (F1) — a letter's own shape, where an overlap of areas lets any dense run
    of text cover a block."""
    import cv2
    import numpy as np
    k3 = np.ones((3, 3), np.uint8)
    ea = cv2.morphologyEx(a.astype(np.uint8), cv2.MORPH_GRADIENT, k3) > 0
    eb = cv2.morphologyEx(b.astype(np.uint8), cv2.MORPH_GRADIENT, k3) > 0
    if not ea.any() or not eb.any():
        return 0.0
    da = cv2.distanceTransform((~ea).astype(np.uint8), cv2.DIST_L2, 5)
    db = cv2.distanceTransform((~eb).astype(np.uint8), cv2.DIST_L2, 5)
    precision, recall = float((da[eb] <= tol).mean()), float((db[ea] <= tol).mean())
    if precision + recall <= 0.0:
        return precision                                    # no outline on the other's: none agrees
    return 2 * precision * recall / (precision + recall)


def _letter_lines(body, n: int) -> list:
    """``body``'s rows split into ``n`` lines at the emptiest row of each gap between them (its row sums, smoothed)."""
    import numpy as np
    rows = body.sum(axis=1).astype(float)
    ys = np.nonzero(rows)[0]
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    smooth = np.convolve(rows, np.ones(9) / 9.0, "same")
    cuts = []
    for j in range(1, n):
        span = np.arange(int(y0 + (y1 - y0) * (j - 0.5) / n), int(y0 + (y1 - y0) * (j + 0.5) / n))
        cuts.append(int(span[np.argmin(smooth[span])]))
    edges = [y0] + cuts + [y1]
    return list(zip(edges[:-1], edges[1:]))


#: [his rule 3 for 119 and every design, 2026-10-05: "Try setting the name in the granted display faces (Bagel Fat One,
#: Shrikhand, Chango, Fredoka) before tracing it."] the four chunky display faces he granted on 2026-10-02, by their stems
#: in the font layer's catalogue — tried, the closest of them chosen, before a name is traced
DISPLAY_FACES_FIRST = ("BagelFatOne-Regular", "Shrikhand-Regular", "Chango-Regular", "Fredoka[wdth,wght]")


def _set_lettering(body, k: int, seen: str, reach: dict, inks: dict, frac, only: str | None = None) -> dict:
    """[His rules for cloning a design from a picture, 2026-10-02, rule 1: "LETTERING IS SET, NOT TRACED".] The picture's
    letters (``body``, its mask at ``k`` times the picture) set in the face that comes closest: the words the picture
    shows, in as many lines as its letters stand in (one, two or three — the emptiest rows between them), its words
    broken where the lines' widths say; every Latin face the house's font layer verifies (`font_roles.verify_candidate`) set in
    them — its glyphs at their advances and its own pair kerning — fitted to the letters line by line for size, place and
    weight, and scored by how much of its outline lies on the letters' (``_outline_agreement``; their areas' overlap,
    IoU, beside it); the best three measured again more finely. Where the best reaches lettering_set_outline the
    letters ARE that face's, grown to the picture's weight, and every layer is an even
    offset of them as the picture layers its lettering (``reach``: picture pixels out of the letter's edge; ``inks``),
    each refit as the fewest cubics, in the product's fractions (``frac``). ``{"state": SET | TRACED, "words", "lines",
    "face", "iou", "outline", "bar", "faces_measured" ([face, IoU, outline]), "layers" (SET), "why" (TRACED)}``."""
    import numpy as np
    from fontTools.ttLib import TTFont
    from shapely import affinity

    from apps.ire import font_roles
    words = seen.split()
    bar = SHAPE_PARAMS["lettering_set_outline"]
    if not words or not body.any():
        return {"state": LETTERING_TRACED, "words": seen, "bar": bar, "why": "no words the picture shows to set"}
    rows = body.sum(axis=1)
    gaps = 0
    ink = rows > 0.15 * float(np.median(rows[rows > 0]))
    for a, b in zip(ink[:-1], ink[1:]):
        gaps += int(a and not b)
    n = max(1, min(3, len(words), gaps))
    lines = _letter_lines(body, n)
    widths = []
    for a, b in lines:
        xs = np.nonzero(body[a:b].any(axis=0))[0]
        if not len(xs):
            return {"state": LETTERING_TRACED, "words": seen, "bar": bar,
                    "why": "a line of the picture's letters holds no ink to set its words in"}
        widths.append(float(xs.max() - xs.min() + 1))
    best_split, best_miss = None, None
    from itertools import combinations
    for cut in combinations(range(1, len(words)), n - 1):
        parts = [" ".join(words[i:j]) for i, j in zip((0,) + cut, cut + (len(words),))]
        miss = sum(abs(np.log(len(p) / sum(len(q) for q in parts)) - np.log(wd / sum(widths)))
                   for p, wd in zip(parts, widths))
        if best_miss is None or miss < best_miss:
            best_split, best_miss = parts, miss
    # only a face the house's font layer verifies for production through the grant channel — never one merely on file
    from apps.ire.container_font_authority import VERIFIED_FOR_PRODUCTION
    faces = []
    display_first = {}
    from apps.ire import font_pool as _font_pool
    pool_unverified = []
    for stem, entry in sorted(font_roles.catalogue().items()):
        if only is not None and stem != only:
            continue
        if entry.get("origin") == _font_pool.ORIGIN:
            # [D-D7-1, Day 7 §4] a pool face is verified through the seam only when the pool is consulted (below):
            # verifying 328 faces on every line re-hashed their evidence for a record that could not change the outcome
            if entry.get("latin"):
                pool_unverified.append((stem, entry["path"]))
            continue
        record = font_roles.verify_candidate("display", stem) if entry.get("latin") else None
        if record is not None and record["verification"] == VERIFIED_FOR_PRODUCTION:
            faces.append((stem, entry["path"]))
            if stem in DISPLAY_FACES_FIRST:
                # [his rule 3] measured and set at its display weight — a variable face's pinned instance (Fredoka's
                # default instance is its lightest)
                inst = font_roles.instance_for(stem, "display") if entry.get("variable") else None
                display_first[stem] = inst["path"] if inst else entry["path"]

    # [D-D7-1, Day 7 §4] the GRANTED pool of the materials library joins the candidate set AFTER the house's faces: its
    # faces are measured the same way and recorded; one sets a line only where no house face — not the closest, not the
    # four display faces of his rule 3 — can, before tracing. A pool face that measures closer than the house face chosen
    # is recorded for the owner (pool_face_closer), not applied.
    pool_faces = pool_unverified

    def measure(path, fine, as_drawn=False):
        font = TTFont(path)
        kern = _pair_kerning(font)
        inter = union = 0
        fits, agree = [], 0.0
        for (a, b), text in zip(lines, best_split):
            shape = _set_line(font, kern, text)
            if shape is None or shape.is_empty:
                return None
            score, how = _fit_set(body[a:b], shape, fine, as_drawn)
            if not how:
                return None
            inter, union = inter + how["inter"], union + how["union"]
            agree += how["outline"] * how["union"]
            fits.append((shape, a, how))
        if not union:
            return None
        return inter / union, agree / union, fits
    coarse = []
    for stem, path in faces:
        got = measure(path, False)
        if got is not None:
            coarse.append((got[0], stem, path, got[1]))
    coarse.sort(key=lambda r: -r[3])                        # by how well its outline lies on the letters
    # [his test blocker on design 124, (6)] fine letters measured finely in every face, each as the face draws it; others,
    # the six closest coarse, grown to the picture's weight as before
    import cv2
    _outline = sum(cv2.arcLength(c, True) for c in cv2.findContours(body.astype(np.uint8), cv2.RETR_LIST,
                                                                     cv2.CHAIN_APPROX_NONE)[0])
    _rows = np.nonzero(body.any(axis=1))[0]
    stroke = (float(body.sum()) / _outline) / float(_rows.max() - _rows.min() + 1)     # the letters hold ink: said above
    fine_letters = stroke < SHAPE_PARAMS["lettering_fine_stroke"]
    finer = []
    for _score, stem, path, _agree in (coarse if fine_letters else coarse[:6]):
        got = measure(path, True, as_drawn=fine_letters)
        if got is not None:
            finer.append((got[0], stem, got[2], got[1]))
    finer.sort(key=lambda r: -r[3])
    measured = [[stem, round(score, 3), round(agree, 3)] for score, stem, _f, agree in finer] + [
        [stem, round(score, 3), round(agree, 3)] for score, stem, _p, agree in coarse[3:8]]
    out = {"words": seen, "lines": best_split, "bar": bar, "faces_measured": measured,
           "measured_finely": ("every face (%d), each as it draws: the letters are fine, their stroke %.3f of their "
                               "height" % (len(finer), stroke) if fine_letters else
                               "the six closest at the coarse measure, grown to the picture's weight")}
    finer_pool = []

    def measure_pool():
        # the pool is measured only where it can set the line (no house face, no display face): measuring 328 faces on
        # every line multiplied the wiring tests' time several-fold for a record that could not change the outcome
        coarse_pool = []
        for stem_, path_ in pool_faces:
            record_ = font_roles.verify_candidate("display", stem_)
            if record_ is None or record_["verification"] != VERIFIED_FOR_PRODUCTION:
                continue
            got_ = measure(path_, False)
            if got_ is not None:
                coarse_pool.append((got_[0], stem_, path_, got_[1]))
        coarse_pool.sort(key=lambda r: -r[3])
        for _score, stem_, path_, _agree in (coarse_pool if fine_letters else coarse_pool[:6]):
            got_ = measure(path_, True, as_drawn=fine_letters)
            if got_ is not None:
                finer_pool.append((got_[0], stem_, got_[2], got_[1]))
        finer_pool.sort(key=lambda r: -r[3])
        out["pool_faces_measured"] = [[s_, round(sc, 3), round(ag, 3)] for sc, s_, _f, ag in finer_pool]
        out["pool_consulted"] = True
    out["pool_consulted"] = False
    if only is not None and not finer and pool_faces:
        measure_pool(); finer = finer_pool                    # a name whose other lines were set from the pool
    chosen = finer[0] if finer and finer[0][3] >= bar else None
    if only is not None:
        # [his last goal before the pitch, Step 2: "fonts ... as the concept shows" — 140's "Comfort" set in Fredoka under
        # "Oat &" and "Honey" in a condensed face] a line of a name set in the face its other lines are set in, where it
        # lays SHAPE_PARAMS["lettering_same_name"] of the bar on its letters
        chosen = finer[0] if finer and (finer[0][3] >= SHAPE_PARAMS["lettering_same_name"] * bar
                                        or finer[0][0] >= SHAPE_PARAMS["lettering_same_name_iou"]) else None
        if chosen is None:
            return dict(out, state=LETTERING_TRACED, why="the name's own face does not come close enough to this line")
        out["set_by"] = "the face its name's other lines are set in, %s" % only
    if chosen is None:
        # [his rule 3, 2026-10-05: "Try setting the name in the granted display faces ... before tracing it."] no face is
        # the picture's own: the words are set in the closest of the four display faces he granted, measured as every
        # face is; traced only where none of them can set them (a glyph none of them holds)
        tried = []
        for stem_ in DISPLAY_FACES_FIRST:
            # measured and set as the face draws it — never grown to the picture's weight, which made a fat face's
            # letters run into one another (119, 2026-10-05: Bagel Fat One grown 32 px read as blobs)
            got = measure(display_first[stem_], True, as_drawn=True) if stem_ in display_first else None
            if got is not None:
                tried.append((got[0], stem_, got[2], got[1]))
        tried.sort(key=lambda r: -r[3])
        out["display_faces_measured"] = [[s_, round(sc, 3), round(ag, 3)] for sc, s_, _f, ag in tried]
        if not tried and pool_faces and not out["pool_consulted"]:
            measure_pool()
        if not tried and finer_pool and finer_pool[0][3] >= bar:
            # [D-D7-1, Day 7 §4] none of the house's faces sets these words and no display face can: the closest face of
            # the GRANTED pool sets them, before tracing
            chosen = finer_pool[0]
            out["set_by"] = ("D-D7-1 (Day 7 §4): no house face sets these words and none of the four display faces can; set "
                             "in the closest face of the GRANTED pool, %s, its outline %.2f on the picture's letters (the bar "
                             "%.2f)" % (chosen[1], chosen[3], bar))
            out["grown_px"] = [how["grow"] for _shape, _row, how in chosen[2]]
        elif tried:
            chosen = tried[0]
            closest = "no other face sets these words"
            if finer:
                closest = "the closest, %s, at %.2f of the %.2f bar" % (finer[0][1], finer[0][3], bar)
            out["set_by"] = ("his rule 3, 2026-10-05: \"Try setting the name in the granted display faces (Bagel Fat One, "
                             "Shrikhand, Chango, Fredoka) before tracing it.\" — no face is the picture's own (%s); set in "
                             "the closest of the four, %s, as the face draws it (never grown), its outline %.2f on the "
                             "picture's letters (the bar %.2f)" % (closest, chosen[1], chosen[3], bar))
            out["grown_px"] = [how["grow"] for _shape, _row, how in chosen[2]]
        elif not finer:
            return dict(out, state=LETTERING_TRACED, why="no face the house holds sets these words")
        else:
            top = finer[0]
            return dict(out, state=LETTERING_TRACED, face=top[1], iou=round(top[0], 3), outline=round(top[3], 3),
                        why="no face the house holds comes close: the closest, %s, lays %.2f of its outline on the "
                            "picture's letters' (and covers %.2f of them) where the bar is %.2f — and none of the granted "
                            "display faces (his rule 3) can set these words — traced" % (top[1], top[3], top[0], bar))
    if out["pool_consulted"] and finer_pool and finer_pool[0][3] > chosen[3] and finer_pool[0][1] != chosen[1]:
        out["pool_face_closer"] = {"face": finer_pool[0][1], "outline": round(finer_pool[0][3], 3), "iou": round(finer_pool[0][0], 3),
                                   "chosen_outline": round(chosen[3], 3),
                                   "not_applied": "his rule 3 keeps the house's faces first; D-D7-1's pool sets a line only where no "
                                                  "house face can, before tracing — recorded for the owner"}
    score, stem, fits, agree = chosen
    letters = None
    for shape, top_row, how in fits:
        placed = affinity.translate(affinity.scale(shape, how["scale"], how["scale"], origin=(0, 0)), how["dx"],
                                    how["dy"] + top_row)
        if how["grow"]:
            placed = placed.buffer(how["grow"], quad_segs=16, join_style="round")
        placed = affinity.scale(placed, 1.0 / k, 1.0 / k, origin=(0, 0))          # the picture's own pixels
        letters = placed if letters is None else letters.union(placed)
    # as the traced letters are cleaned: a notch the grown strokes nearly shut closed (lettering_notch_px each side), and
    # a counter narrower than lettering_hole_px each side filled — a slit, never an eye; a letter's own eyes are kept
    # — never on a face set as it is drawn (his rule 3): its notches and counters are the face's own
    from shapely.geometry import Polygon as _Polygon
    from shapely.ops import unary_union as _union
    if "set_by" not in out:
        notch = SHAPE_PARAMS["lettering_notch_px"]
        letters = letters.buffer(notch, quad_segs=16).buffer(-notch, quad_segs=16)
        kept = []
        for poly in (list(letters.geoms) if hasattr(letters, "geoms") else [letters]):
            if poly.geom_type == "Polygon":
                kept.append(_Polygon(poly.exterior, [ring for ring in poly.interiors if not _Polygon(ring).buffer(
                    -SHAPE_PARAMS["lettering_hole_px"]).is_empty]))
        letters = _union(kept)
    # the pale inline as deep, for the set strokes' half-width, as the picture's is for its own — its depth a share of the
    # traced letters' half-width (area over outline) — and never deeper than half the set strokes' own half-width, so a
    # letter keeps its core (a thin stroke's inline reads deeper in the picture than it is drawn: its edges blur)
    import cv2
    outline_px = sum(cv2.arcLength(c, True) for c in cv2.findContours(body.astype(np.uint8), cv2.RETR_LIST,
                                                                        cv2.CHAIN_APPROX_NONE)[0])
    depth = reach["body"]
    if outline_px and letters.length:
        half_traced = float(body.sum()) / outline_px / k
        half_set = letters.area / letters.length
        depth = min(reach["body"] * min(1.0, half_set / half_traced), 0.5 * half_set)
    plan = (("outer", letters.buffer(reach["outer"], quad_segs=16)),
            ("ring", letters.buffer(reach["ring"], quad_segs=16).difference(letters.buffer(reach["inline"], quad_segs=16))),
            ("ring-shade", letters.buffer(reach["split"], quad_segs=16).difference(
                letters.buffer(reach["inline"], quad_segs=16))),
            ("inline", letters.buffer(reach["inline"], quad_segs=16)),
            ("body", letters.buffer(-depth, quad_segs=16)))
    layers = []
    for name, shape in plan:
        rings = _cubic_rings(shape, SHAPE_PARAMS["curve_tol_px"])
        if rings and name in inks:
            layers.append({"name": name, "ink": inks[name], "cubics": [[[frac(ring[0])] + [
                frac(seg[0:2]) + frac(seg[2:4]) + frac(seg[4:6]) for seg in ring[1:]] for ring in poly] for poly in rings]})
    return dict(out, state=LETTERING_SET, face=stem, iou=round(score, 3), outline=round(agree, 3), layers=layers)


#: [the owner's finding on design 119, 2026-10-03] a display line's lettering is ONE layer — the letters themselves
DISPLAY_REACH = {"outer": 0.0, "ring": 0.0, "split": 0.0, "inline": 0.0, "body": 0.0}


def _outline_of(line: dict) -> float:
    """How much of a set line's face lies on its letters (``_set_lettering``'s outline), 0 where it says none."""
    got = line["lettering_set"].get("outline")
    if got is None:
        return float(0)
    return float(got)


def _one_face_for_the_name(types: list, sources, img, mask, pbox) -> None:
    """[His last goal before the pitch, 2026-10-16, Step 2: "fonts, metals and colours as the concept shows"; his goal of
    2026-10-10, item 6: the name in ONE colour, its lines in one family] display lines the picture stacks as one block —
    each set as lettering, in one ink (within SHAPE_PARAMS["closure_de"]), each under the last within
    ``lettering_block_gap`` of its height and overlapping it across — set in ONE face: the face of the line whose
    letters it fits best, where it lays ``lettering_same_name`` of the bar on each other line's letters; a line it
    cannot set stays as it was. In place (140's "Oat &", "Honey" and "Comfort": Barlow Condensed, Oswald, Fredoka)."""
    from apps.ire.legibility import colour_distance
    lines = sorted([t for t in types if (t.get("lettering_set") or {}).get("state") == LETTERING_SET and t.get("ink")
                    and t.get("box") and t.get("rotation") not in (90, -90)], key=lambda t: float(t["box"][1]))
    blocks, cur = [], []
    for t in lines:
        if cur:
            last = cur[-1]
            gap = float(t["box"][1]) - float(last["box"][3])
            tall = min(float(t["box"][3]) - float(t["box"][1]), float(last["box"][3]) - float(last["box"][1]))
            across = min(float(t["box"][2]), float(last["box"][2])) - max(float(t["box"][0]), float(last["box"][0]))
            narrow = min(float(t["box"][2]) - float(t["box"][0]), float(last["box"][2]) - float(last["box"][0]))
            if (gap <= SHAPE_PARAMS["lettering_block_gap"] * tall and across >= 0.5 * narrow
                    and colour_distance(t["ink"], last["ink"]) < SHAPE_PARAMS["closure_de"]):
                cur.append(t)
                continue
            blocks.append(cur)
        cur = [t]
    if cur:
        blocks.append(cur)
    for block in blocks:
        if len(block) < 2 or len({t["lettering_set"].get("face") for t in block}) < 2:
            continue
        best = max(block, key=_outline_of)
        face = best["lettering_set"]["face"]
        for t in block:
            if t is best or t["lettering_set"].get("face") == face:
                continue
            again = set_display(img, mask, pbox, t, only=face)
            if again.get("state") == LETTERING_SET:
                t["lettering_set"] = dict(again, was=t["lettering_set"].get("face"))


def set_display(img, mask, pbox, line: dict, only: str | None = None) -> dict:
    """[The owner's finding on design 119, 2026-10-03 (transcribed at 32898c7): "front as the concept shows it"; his
    rules for cloning a design from a picture, 2026-10-02, rule 1: "LETTERING IS SET, NOT TRACED ... exact words".] A
    line the picture letters in a display face, or turns, set in the face that comes closest: its measured ink inside its
    traced box, read at lettering_upscale, turned to read left to right (``rotation`` 90 reads bottom to top, -90 top to
    bottom), and set and measured as a script's letters are (``_set_lettering``) — one layer, the letters themselves, in
    the line's ink (DISPLAY_REACH) — every point turned back onto the product. ``_set_lettering``'s record and the turn
    it was read at; TRACED, with why, where no face the house holds comes close."""
    import cv2
    import numpy as np
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    pad = 8
    cx0, cy0 = max(0, int(x0 + line["box"][0] * w) - pad), max(0, int(y0 + line["box"][1] * h) - pad)
    cx1 = min(img.shape[1], int(x0 + line["box"][2] * w) + pad)
    cy1 = min(img.shape[0], int(y0 + line["box"][3] * h) + pad)
    lab = np.stack(_lab(img[cy0:cy1, cx0:cx1]), -1)
    hx = line["ink"]
    rgb = np.array([int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)], np.uint8).reshape(1, 1, 3)[..., ::-1]
    target = np.stack(_lab(np.ascontiguousarray(rgb)), -1)[0, 0]
    ink = (np.sqrt(((lab - target) ** 2).sum(-1)) < SHAPE_PARAMS["type_ink_de"]) & (mask[cy0:cy1, cx0:cx1] > 0)
    k = int(SHAPE_PARAMS["lettering_upscale"])
    body = cv2.GaussianBlur(cv2.resize(ink.astype(np.uint8) * 255, None, fx=k, fy=k, interpolation=cv2.INTER_LINEAR),
                            (0, 0), 0.3 * k) > 127
    body, _slits = _fill_thin_holes(body.astype(np.uint8), SHAPE_PARAMS["lettering_hole_px"] * k)
    ch, cw = ink.shape
    turn = line.get("rotation")
    if turn == 90:
        body = np.rot90(body, -1)                    # turned clockwise: its foot, where it begins, to the left

        def back(p):
            return float(p[1]), ch - float(p[0])
    elif turn == -90:
        body = np.rot90(body, 1)                     # turned the other way: its head, where it begins, to the left

        def back(p):
            return cw - float(p[1]), float(p[0])
    else:
        def back(p):
            return float(p[0]), float(p[1])

    def frac(p):
        bx, by = back(p)
        return [round((cx0 + bx - x0) / w, 5), round((cy0 + by - y0) / h, 5)]
    got = _set_lettering(np.ascontiguousarray(body), k,
                         line["words"] if line.get("words") else line["seen"] if "seen" in line else "", DISPLAY_REACH,
                         {"body": hx}, frac, only=only)
    return dict(got, read_turned=turn in (90, -90))


# --- THE STOP: a concept the map cannot draw is never drawn some other way ------------------------------------------------
# [The owner's finding on design 119, 2026-10-03 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 32898c7): "NO SILENT
# FALLBACK. If the map can't read the concept, STOP and tell me why, with options. Never hand me a different design."]

#: the code a stopped design carries, in its log and on its concept
MAP_STOP = "DESIGN_MAP_STOP"
#: where the stop is kept on the concept the design stopped at
MAP_STOP_KEY = "design_map_stop/1.0"
#: what he can do, in the Gate 1 page's own words for its three actions
STOP_OPTIONS = ("choose another of the concepts", "draw these concepts again",
                "ask for changes, in your own words")


def undrawn_parts(record: dict, shapes: dict, sources: list) -> list:
    """Each part the map ``record`` names that its drawing would not draw as the picture prints it — ``[{"kind", "name",
    "why"}]``, empty when every part is drawn: its shape traced (``shapes``, ``trace_shapes``), and a type line given
    the words a source on record or the picture itself gives it (``type_sources`` over ``sources``). Drawn by the form
    itself: the ground (the first field), a standing product's other fields (its body's colour fields) and its closure
    (its cap); a band's drips (its traced gold edge). On a carton's panel every field after its ground is a traced
    shape. Pure."""
    # [his test blocker on design 124, (2)] a compact lid's illustration drawn whole by its art, where the art traced
    traced = {item.get("part") for key in ("bands", "rules", "marks", "types", "shapes", "scatters", "lines", "frames",
                                           "windows", "illustrations")
              for item in shapes.get(key) or []}
    # [his answers after the fixes for design 122, (2)] a size line left out because no size is on record is drawn as his
    # rule draws it — not at all — and never blocks the concept
    worded = {t.get("part") for t in type_sources(shapes.get("types") or [], sources)
              if t.get("words") or t.get("size") or t.get("joined")}
    carton = bool(record.get("face_box_px"))
    out, fields = [], 0
    for part in record.get("parts") or []:
        kind, name = part.get("kind"), part.get("name")
        if kind == "field":
            fields += 1
            if fields == 1 or not carton:
                continue
        if kind == "closure" and not carton:
            continue
        # [his answer of 2026-10-05, W2] only a band that carries a gold edge draws a drip motif — a plain stripe draws none
        if kind == "motif" and "drip" in str(name).lower() and any(b.get("edge") for b in shapes.get("bands") or []):
            continue
        if name in traced and (kind != "type" or name in worded):
            continue
        said = [p.split(": ", 1)[-1] for p in shapes.get("problems") or [] if repr(name) in p]
        if kind == "type" and name in traced:
            why = "no source on record carries the words the picture prints"
        elif said:
            why = said[0]
        elif kind == "window":
            why = "no tracer draws a framed panel yet"
        else:
            why = "not traced"
        out.append({"kind": kind, "name": name, "why": why})
    return out


#: [his rule 1 for 119 and every design, 2026-10-05: "the Arabic ملمّع as my brief writes it"] the Arabic marks a read
#: drops or keeps as it happens to see them (the harakat, the shadda, the dagger alif) — folded away for MATCHING only;
#: the brief's own words, marks and all, are what is printed
_ARABIC_MARKS = r"[\u064b-\u065f\u0670]"


def _words(text) -> set:
    """A line's words for matching: lower case, its separators and signs (• / | · ℮ , - +) as spaces, its Arabic marks
    folded away; a lone Latin letter dropped (the read's "e" for ℮); numbers and Arabic kept."""
    import re
    cleaned = re.sub(r"[•/|·℮,\-+()\[\]\"'“”:;]", " ", re.sub(_ARABIC_MARKS, "", str(text).lower()))
    return {t for t in cleaned.split() if not (len(t) == 1 and t.isascii() and t.isalpha())}


def _squashed(text) -> str:
    """[His rule 1, 2026-10-05: "'Rose Glaze' with a space".] A line's letters and digits alone, lower case, its Arabic
    marks folded away — so a picture that runs its words together ("RoseGlaze") is the brief's spaced words."""
    import re
    return "".join(ch for ch in re.sub(_ARABIC_MARKS, "", str(text).lower()) if ch.isalnum())


def script_halves(text) -> list:
    """[His rules 1 and 2, 2026-10-05: the brief's words, and "keep the '·' between 'LIP GLOSS' and the Arabic".] A phrase
    that sets an English run beside an Arabic one ("LIP GLOSS · ملمّع الشفاه") as its two halves, each a line the picture
    may print on its own — the English first, with the separator between them kept at its end ("LIP GLOSS ·"), as the
    side panel sets it (``compose_container._script_runs``); ``[]`` for a phrase in one script."""
    t = " ".join(str(text).split())
    first_ar = next((i for i, ch in enumerate(t) if ch.isalpha() and not ch.isascii()), None)
    if first_ar is None or not any(ch.isalpha() and ch.isascii() for ch in t[:first_ar]):
        return []
    if any(ch.isalpha() and ch.isascii() for ch in t[first_ar:]):
        return []
    latin, arabic = t[:first_ar].rstrip(), t[first_ar:].strip()
    return [half for half in (latin, arabic) if half]


#: [his rule 1, 2026-10-05] a brief's own front lines, beside its "Front copy:": what its carton's front and its vial
#: print, as he writes them ("Carton front: BBROSE logo, \"Rose Glaze\", …"; "Vial copy: …")
BRIEF_FRONT_FIELDS = (("carton front", "the brief's carton front"), ("vial copy", "the brief's vial copy"))


def brief_front_fields(brief) -> list:
    """``[(phrase, where it is on record)]`` — the phrases of each field BRIEF_FRONT_FIELDS names, to the line's end and
    the lines that run on from it, split at commas outside quotes, each stripped of its quotes and its last full stop
    (as ``brief_side_copy`` reads "Carton side:")."""
    import re
    text = str(brief).replace("\r\n", "\n")
    out = []
    for label, origin in BRIEF_FRONT_FIELDS:
        m = re.search(r"^[ \t]*%s[ \t]*:[ \t]*(.+?)(?:\n[ \t]*\n|\n[ \t]*[A-Za-z][A-Za-z ]{0,30}:|\Z)" % re.escape(label),
                      text, re.I | re.M | re.S)
        if not m:
            continue
        cur, quoted, parts = "", False, []
        for ch in " ".join(m.group(1).split()):
            if ch in "\"“”":
                quoted = not quoted
                continue
            if ch == "," and not quoted:
                parts.append(cur)
                cur = ""
                continue
            cur += ch
        parts.append(cur)
        out += [(p.strip().rstrip(".").strip(), origin) for p in parts if p.strip().rstrip(".").strip()]
    return out


#: the longest phrase a brief's quotes give its copy (a longer quote is a sentence about the design, never its copy)
BRIEF_QUOTE_MAX = 60


def brief_front_copy(brief) -> list:
    """The phrases of a brief's "Front copy:" section — after the words up to the first blank line, the next
    "... copy:", or [his test blocker on design 124, 2026-10-11] the full stop that ends a line the next line of which
    opens with its own label (124's "... 27 g ℮ 0.95 oz." then "Shade names (row by row, left to right):", read as one
    phrase, its size lost) — split at commas outside quotes, each stripped of its quotes and its last full stop. Its
    lines end as his New design form ends them ("\\r\\n", 124's brief) or plainly, alike."""
    import re
    text = str(brief).replace("\r\n", "\n").replace("\r", "\n")
    # [his goal for the pitch, 2026-10-15] a palette's or a compact's brief names its copy for its lid, a label's for
    # its label — each the piece's front, read alike
    m = re.search(r"(?:front|lid|label|face) copy\s*:\s*(.+?)(?:\n\s*\n|\n\s*[a-z ]+ copy\s*:|(?<=\.)[ \t]*\n(?=[ \t]*[^\n:]{1,60}:)|$)",
                  text, re.I | re.S)
    if not m and re.search(r"^[ \t]*[a-z][a-z ]{0,30}(?:copy|front|side|back)[ \t]*:", text, re.I | re.M):
        return []
    if not m:
        # [his goal after the pitch page, B (9)-(11): three brand-new briefs, written as a client writes — 138's "Name on
        # the front, then "Eau de Parfum" and "50 ml / 1.7 fl oz" small underneath"] a brief with no copy field at all
        # (no "Front copy:", "Carton front:", "Vial copy:" …) quotes the words it wants printed: each quoted phrase is its copy, in its order (a line takes one only where
        # the picture prints its words — ``type_sources``)
        return [" ".join(q.split()).strip().rstrip(".").strip()
                for q in re.findall(r"[\"“]([^\"“”\n]{1,%d})[\"”]" % BRIEF_QUOTE_MAX, text)
                if " ".join(q.split()).strip().rstrip(".").strip()]
    # [his goal for the pitch, 2026-10-15] a phrase he quotes is the quote alone — words after its closing quote
    # ("3.5 g". English and Arabic.) are the brief's, never printed copy
    out, cur, inside, quoted = [], "", "", False
    for ch in " ".join(m.group(1).split()):
        if ch in "\"“”":
            quoted = not quoted
            continue
        if ch == "," and not quoted:
            out.append(inside if inside.strip() else cur)
            cur, inside = "", ""
            continue
        cur += ch
        if quoted:
            inside += ch
    out.append(inside if inside.strip() else cur)
    return [p.strip().rstrip(".").strip() for p in out if p.strip().rstrip(".").strip()]


#: [his rules for cloning a design from a picture, 2026-10-02, rule 5: "THE BACK IS DRAWN"] a back copy's phrase that names
#: the place its batch code goes
BATCH_CODE_PLACE = r"(?<![a-z])batch[ \t]*code(?![a-z])"
#: … and who gave the back its words
BRIEF_BACK_COPY = "the brief's back copy"


def brief_back_copy(brief) -> dict:
    """[His rules for cloning a design from a picture, 2026-10-02, rule 5: "replace the placeholders ... with the
    brief's back copy: how to use, ingredients, batch code place, Made in UAE".] The items of a brief's "Back copy:"
    field — to a blank line, or to the next line that begins with a field's label ("Carton: …") where the line before it
    does not end in "/" — set apart by " / ": each "Heading: words" a section under its own heading, in his words; a
    bare phrase a section without one; a phrase naming the batch code its place (``batch_code_place``, his words).
    ``{"sections": [{"heading", "text", "source"}], "batch_code_place": str | None}``."""
    import re
    text = str(brief).replace("\r\n", "\n").replace("\r", "\n")
    # [the owner's finding on design 119, 2026-10-03: "The back panel fills from my brief"] 119's brief labels it
    # "Carton back:" — read as his "Back copy:" is
    m = re.search(r"^[ \t]*(?:back copy|carton back|back)[ \t]*:[ \t]*", text, re.I | re.M)
    if not m:
        return {"sections": [], "batch_code_place": None}
    body, prev = [], ""
    for k, line in enumerate(text[m.end():].split("\n")):
        if k and (not line.strip() or (re.match(r"^[ \t]*[A-Za-z][A-Za-z ]{0,30}:", line)
                                       and not prev.rstrip().endswith("/"))):
            break
        body.append(line)
        prev = line
    sections, place = [], None
    for item in re.split(r"[ \t]+/[ \t]+|[ \t]*/[ \t]*$", " ".join(" ".join(body).split())):
        item = item.strip()
        if not item:
            continue
        if re.search(BATCH_CODE_PLACE, item, re.I):
            place = item
            continue
        head = re.match(r"^([A-Za-z][A-Za-z ]{0,30}):[ \t]*(.+)$", item)
        sections.append({"heading": head.group(1).strip() if head else "",
                         "text": (head.group(2) if head else item).strip(), "source": BRIEF_BACK_COPY})
    return {"sections": sections, "batch_code_place": place}


def brief_side_copy(brief) -> list:
    """[The owner's finding on design 119, 2026-10-03: "sides, back and flaps continue the concept's own ground, colours
    and graphics".] The phrases of a brief's "Carton side:" (or "Side copy:") field, to the line's end and the lines
    that run on from it — split at commas outside quotes, each stripped of its quotes and its last full stop; 119's:
    "LIP GLOSS · ملمّع الشفاه", "8 ml ℮ / 0.27 fl oz"."""
    import re
    m = re.search(r"^[ \t]*(?:carton side|side copy|side)[ \t]*:[ \t]*(.+?)(?:\n[ \t]*\n|\n[ \t]*[A-Za-z][A-Za-z ]{0,30}:|\Z)",
                  str(brief).replace("\r\n", "\n"), re.I | re.M | re.S)
    if not m:
        return []
    out, cur, quoted = [], "", False
    for ch in " ".join(m.group(1).split()):
        if ch in "\"“”":
            quoted = not quoted
            continue
        if ch == "," and not quoted:
            out.append(cur)
            cur = ""
            continue
        cur += ch
    out.append(cur)
    return [p.strip().rstrip(".").strip() for p in out if p.strip().rstrip(".").strip()]


#: [his second look at 117, 2026-10-02: "add the Arabic lines"; his rules for cloning a design from a picture, the same day,
#: rule 1: "exact words"; his answer 4: designs "read the brief's colours and copy" — measured on 117 after the executor
#: had told him its brief carried no words for these lines: it carries both] a brief's own one-line fields that give a
#: front's lines their words, and how each is said
BRIEF_LINE_FIELDS = (("arabic name", "the brief's Arabic name"), ("scent line", "the brief's scent line"))


def brief_line_fields(brief) -> list:
    """``[(text, where it is on record)]`` — each one-line field of the brief BRIEF_LINE_FIELDS names ("Arabic name: …",
    "Scent line: … | …"): its words after the colon to the line's end, split at "|" into the phrases it sets side by
    side (a scent line's English and its Arabic), each stripped of its last full stop."""
    import re
    out = []
    for label, origin in BRIEF_LINE_FIELDS:
        m = re.search(r"^[ \t]*%s[ \t]*:[ \t]*(.+?)[ \t]*\r?$" % re.escape(label), str(brief), re.I | re.M)
        if not m:
            continue
        for phrase in m.group(1).split("|"):
            phrase = " ".join(phrase.split()).rstrip(".").strip()
            if phrase:
                out.append((phrase, origin))
    return out


#: [his review of 119, 2026-10-05, point 3: "One ground all round the carton, taken from the concept's own colour (119's
#: concept is a light cream/blush, not peach)."] A concept is a photograph: its light colours every surface in it — 119's
#: is warm, and its cream card photographs peach (#F2D4C1 on its face; the map's own read names the field "cream panel").
#: The light is read from the picture's brightest pixels (the white patch) and its cast taken out of the ground by a share
#: of it — a von Kries step of degree ``adapt`` — only where those pixels are bright and near neutral, so a coloured
#: highlight (a gold foil's shine) is never taken for the light.
GROUND_LIGHT = {
    "white_share": 0.005,       # the picture's brightest pixels, this share of all of them, read as its light …
    "white_l_min": 90.0,        # … only where they are at least this light (L*) …
    "white_chroma_max": 20.0,   # … and no more coloured than this (C*ab)
    "adapt": 0.5,               # the share of the light's cast taken out: measured on 119 against his words — the whole
    #                             cast (1.0) reads lilac-pink (#F2D9DC), half (0.5) the cream/blush he names (#F2D6CE),
    #                             none (0.0) the peach he refused (#F1D2C0); 117's hot pink moves 2 ΔE at 1.0, less at 0.5
}


def light_corrected(image_bytes: bytes, hex_colour: str) -> dict:
    """[His review of 119, 2026-10-05, point 3.] ``hex_colour`` as the concept's own colour: its picture's light read
    from its brightest pixels (``GROUND_LIGHT``) and that light's cast taken out of it by ``adapt`` — ``{"hex", "photographed",
    "light", "method"}``, or the colour as photographed with ``"why"`` where the brightest pixels are too dark or too
    coloured to be the light."""
    import cv2
    import numpy as np
    out = {"hex": hex_colour, "photographed": hex_colour}
    img = None
    if image_bytes and hex_colour:
        img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        out["why"] = "no picture to read its light from"
        return out
    rgb = img[..., ::-1].reshape(-1, 3).astype(float)
    count = max(1, int(round(GROUND_LIGHT["white_share"] * len(rgb))))
    top = rgb[np.argsort(rgb.mean(axis=1), kind="stable")[-count:]]       # exactly the brightest share, ties or none
    light = np.median(top, axis=0)
    l_star, a_star, b_star = (float(v[0, 0]) for v in _lab(np.uint8(np.round(light[::-1])).reshape(1, 1, 3)))
    out["light"] = "#%02X%02X%02X" % tuple(int(round(v)) for v in light)
    if l_star < GROUND_LIGHT["white_l_min"] or float(np.hypot(a_star, b_star)) > GROUND_LIGHT["white_chroma_max"]:
        out["why"] = ("the picture's brightest pixels (%s, L* %.1f, C* %.1f) are too dark or too coloured to be its light"
                      % (out["light"], l_star, float(np.hypot(a_star, b_star))))
        return out
    seen = np.array([int(hex_colour[1:3], 16), int(hex_colour[3:5], 16), int(hex_colour[5:7], 16)], float)
    gain = (255.0 / np.maximum(light, 1.0)) ** GROUND_LIGHT["adapt"]
    own = np.clip(np.round(seen * gain), 0, 255)
    out["hex"] = "#%02X%02X%02X" % tuple(int(v) for v in own)
    out["method"] = ("the picture's light read from its brightest %.1f%% of pixels (%s) and %.0f%% of its cast taken out "
                     "(von Kries)" % (100.0 * GROUND_LIGHT["white_share"], out["light"], 100.0 * GROUND_LIGHT["adapt"]))
    return out


#: [his look at 117 drawn from its map, 2026-10-02: "And about the English words, they need to be added."] where a line
#: the picture prints in English takes its words when no record carries them
PICTURE_ENGLISH = ("the picture's own English words, as the map read them — on his word: \"about the English words, "
                   "they need to be added\" (his look at 117 drawn from its map, 2026-10-02)")
#: [his second look at 117, 2026-10-02: "add the Arabic lines"] where a line the picture prints in Arabic takes its words
#: when no record carries them
PICTURE_ARABIC = ("the picture's own Arabic words, as the map read them — on his word: \"add the Arabic lines\" (his "
                  "second look at 117, 2026-10-02)")
#: the marks a line's phrases are set apart by
SEPARATORS = "•·|/"


def _english(text) -> bool:
    """Every letter of ``text`` a Latin one, and at least one letter."""
    letters = [ch for ch in str(text) if ch.isalpha()]
    return bool(letters) and all(ch.isascii() for ch in letters)


def _arabic(text) -> bool:
    """Every letter of ``text`` an Arabic one, and at least one letter."""
    letters = [ch for ch in str(text) if ch.isalpha()]
    return bool(letters) and all("\u0600" <= ch <= "\u06ff" or "\u0750" <= ch <= "\u077f"
                                 or "\ufb50" <= ch <= "\ufeff" for ch in letters)


def _as_pictured(text: str, seen) -> str:
    """``text`` with the separator between its phrases the one the picture prints, where the picture prints one kind."""
    shown = {ch for ch in str(seen) if ch in SEPARATORS}
    if len(shown) != 1:
        return text
    mark = shown.pop()
    return "".join(mark if ch in SEPARATORS else ch for ch in text)


#: [His answers after the fixes for design 122, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md), (2): "the drawing must always
#: print my brief's size (60 ml), never the picture's text. Confirm that holds for every design."] a quantity a size is
#: stated in — millilitres, centilitres, grams, kilograms, ounces, fluid ounces
SIZE_QUANTITY = r"\d+(?:[.,]\d+)?\s*(?:fl\.?\s*oz|ml|cl|kg|g|oz)\.?(?![a-z])"
#: … and a size as it is printed: one quantity, or several set apart by ℮, "e", "/", "·" or "|", a ℮ after them
SIZE_STATED = re.compile(r"%s(?:(?:\s*(?:℮|e(?=\s)|/|·|\|))*\s*%s)*(?:\s*℮)?" % (SIZE_QUANTITY, SIZE_QUANTITY), re.I)
#: where his brief's size stands, said with it
BRIEF_SIZE_FRONT = "his brief's size, in its front copy"
BRIEF_SIZE_FIELD = "his brief's size, in the words it gives a piece to print"
BRIEF_SIZE_LINE = "his brief's size, on its Size line"
BRIEF_SIZE_OPENING = "his brief's size, as its opening line names the product"
BRIEF_SIZE_CAPACITY = "his brief's size, the capacity his New design form wrote into it"


def size_stated(text):
    """The span of ``text`` that states a size ("100 ml / 3.38 fl. oz."), or None."""
    if not text:
        return None
    return SIZE_STATED.search(str(text))


def is_size(text) -> bool:
    """``text`` states a size and nothing more ("60 ml ℮ 2 fl oz")."""
    if not text:
        return False
    return SIZE_STATED.fullmatch(" ".join(str(text).split()).strip(" .")) is not None


def brief_size(brief):
    """[His answers after the fixes for design 122, (2).] His brief's size in his brief's own words, and where it stands —
    ``(words, origin)``: its front copy's size ("60 ml ℮ 2 fl oz"), else the size among the words it gives a piece to
    print ("Carton front:", "Vial copy:", "Carton side:" — 119's "8 ml ℮ / 0.27 fl oz"), else its "Size:" line's ("60 ml
    ℮ / 2 fl oz"), else the capacity his New design form writes into it ("Capacity: 60 ml"); None where it gives none.
    Pure."""
    for phrase in brief_front_copy(brief):
        if is_size(phrase):
            return " ".join(phrase.split()).strip(" ."), BRIEF_SIZE_FRONT
    for phrase in [f[0] for f in brief_front_fields(brief)] + brief_side_copy(brief):
        if is_size(phrase):
            return " ".join(phrase.split()).strip(" ."), BRIEF_SIZE_FIELD
    # [his goal after the pitch page, B (11): the blush's "Powder Blush 6 g" — its size within a phrase of its copy, its
    # line never printed for "no size on record"] the size a phrase of its copy states among its words
    for phrase in brief_front_copy(brief):
        inner = SIZE_STATED.search(" ".join(phrase.split()))
        if inner:
            return inner.group(0).strip(" ."), BRIEF_SIZE_FRONT
    text = str(brief)
    line = re.search(r"^[ \t]*size[ \t]*:[ \t]*(.+)$", text, re.I | re.M)
    stated = SIZE_STATED.match(line.group(1).strip()) if line else None
    if stated:
        return stated.group(0).strip(" ."), BRIEF_SIZE_LINE
    capacity = re.search(r"capacity[ \t]*:[ \t]*(%s)" % SIZE_QUANTITY, text, re.I)
    if capacity:
        return capacity.group(1).strip(" ."), BRIEF_SIZE_CAPACITY
    # [his last goal before the pitch, 2026-10-16, Step 2; his D (11) for 126: ""30 ml" printed from the brief" — "BBROSE
    # Rose Glow Face Serum, 30 ml glass dropper bottle."] the size its opening line names the product at
    opening = re.split(r"\n\s*\n|\bstyle\s*:|\[", text, maxsplit=1, flags=re.I)[0]
    stated = SIZE_STATED.search(opening)
    if stated:
        return stated.group(0).strip(" ."), BRIEF_SIZE_OPENING
    return None


def _size_line(t: dict, stated, size) -> dict:
    """[His answers after the fixes for design 122, (2): "never the picture's text".] A line the picture prints a size on:
    his size where the picture's stood — the line his size alone where it carries nothing else — never the picture's
    figures; left out by name where no size is on record (a size the drawing cannot state is never drawn)."""
    seen = str(t["seen"])
    if size is None:
        return dict(t, words=None, source=None, size=True,
                    left_out="no size on record: the picture's own size is never printed")
    rest = seen[:stated.start()] + seen[stated.end():]
    words = size[0] if not any(ch.isalpha() for ch in rest) else seen[:stated.start()] + size[0] + seen[stated.end():]
    return dict(t, words=" ".join(words.split()), source=size[1], match=1.0, size=True)


def _part_of(text: str, seen: set) -> str:
    """The run of ``text``'s own words the picture shows (``seen``), with the marks between them ("Oat & Honey" of
    "Oat & Honey Comfort") — ``text`` itself where its shown words do not stand together."""
    tokens = text.split()
    kept = [i for i, tok in enumerate(tokens) if _words(tok) and _words(tok) <= seen]
    if not kept:
        return text
    run = tokens[kept[0]:kept[-1] + 1]
    if any(_words(tok) and not _words(tok) <= seen for tok in run):
        return text                              # its shown words stand apart in the phrase: the phrase as it is
    return " ".join(run)


def type_sources(types: list, sources: list) -> list:
    """Each traced type line with the words it prints: the source phrase — ``sources``: ``[(text, where it is on
    record)]`` — whose words share at least SHAPE_PARAMS["type_match"] with the words the picture shows (the share of
    their union), the best of them, its phrases set apart by the separator the picture prints; a line the picture prints
    in English that no source matches, in the picture's own words as the map read them (PICTURE_ENGLISH, his word of
    2026-10-02), and so a line it prints in Arabic (PICTURE_ARABIC, his second word that day); any other line no
    source matches carries none, and is left out by name. [His answers after the fixes for design 122, (2)] a line that
    states a size carries the first size on record (``_size_line``) — his brief's, as ``sources`` order them — never the
    picture's figures."""
    out = []
    size = next(((text, origin) for text, origin in sources if is_size(text)), None)
    for t in types:
        if t.get("joined_to"):
            # [his go of 2026-10-08] set on one line with the line before it on its row
            out.append(dict(t, words=None, source=None, joined=True,
                            left_out="set on one line with %r" % t["joined_to"]))
            continue
        stated = size_stated(t.get("seen"))
        if stated is not None:
            out.append(_size_line(t, stated, size))
            continue
        seen = _words(t["seen"]) if t.get("seen") else set()
        best, score = None, 0.0
        for text, origin in sources:
            words = _words(text)
            union = seen | words
            if not union:
                continue
            share = len(seen & words) / float(len(union))
            # [his rule 1] the picture's letters run together ("RoseGlaze") are the brief's spaced words ("Rose Glaze")
            if t.get("seen") and _squashed(t["seen"]) and _squashed(t["seen"]) == _squashed(text):
                share = 1.0
            if share > score:
                best, score = (text, origin), share
        if best is not None and score >= SHAPE_PARAMS["type_match"]:
            text = best[0]
            if seen and seen < _words(text):
                # [his review of 127-132, C (4); the second brand-new brief's carton, 136: "Oat & Honey Comfort" printed
                # whole on the first of its two lines and "Comfort" again on the second] a line that shows part of a
                # phrase prints that part, in the phrase's own spelling
                text = _part_of(text, seen)
            out.append(dict(t, words=_as_pictured(text, t.get("seen")), source=best[1], match=round(score, 4)))
        elif t.get("seen") and _english(t["seen"]) and str(t.get("lettering")).lower() != "script":
            out.append(dict(t, words=" ".join(str(t["seen"]).split()), source=PICTURE_ENGLISH, match=1.0))
        elif t.get("seen") and _arabic(t["seen"]) and str(t.get("lettering")).lower() != "script":
            out.append(dict(t, words=" ".join(str(t["seen"]).split()), source=PICTURE_ARABIC, match=1.0))
        else:
            out.append(dict(t, words=None, source=None, left_out="no source on record carries what the picture shows"))
    # [his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010)] the half of
    # a phrase the picture prints on a row of its own — 123's "Hand Cream" stacked over its "كريم اليدين" — takes no
    # separator at its end where the picture prints none there; a half the picture sets beside the other on one row keeps
    # it ("LIP GLOSS ·", his rule 2 for 119), as does a line the picture prints with it, and a row the front's fit breaks
    # drops it there (his final goal, C8)
    for line in out:
        words, seen = line.get("words"), line.get("seen")
        if not isinstance(words, str) or words.rstrip()[-1:] not in SEPARATORS or not line.get("box"):
            continue
        if isinstance(seen, str) and seen.rstrip()[-1:] in SEPARATORS:
            continue
        y0, y1 = float(line["box"][1]), float(line["box"][3])
        beside = [o for o in out if o is not line and o.get("words") and o.get("box")
                  and min(y1, float(o["box"][3])) - max(y0, float(o["box"][1]))
                  > 0.5 * min(y1 - y0, float(o["box"][3]) - float(o["box"][1]))]
        if not beside:
            line["words"] = words.rstrip()[:-1].rstrip()
    return out


def _band_on_the_body(record: dict, closure: dict, foot: bool, edge: float, lab_of) -> float | None:
    """[His last goal before the pitch, 2026-10-16, Step 2: "the hero is never lost: caps and closures" — 139's tube stood
    on its cream flip-cap under a cream band its body prints: the two one colour, read as one closure, so no cap was
    drawn] where a band the map reads in the closure's colour (within SHAPE_PARAMS["closure_de"]) runs across the edge
    found between body and closure, the band is the body's: the closure begins at its far side. None where none does."""
    import numpy as np
    want = lab_of(closure["colour"])
    for band in record.get("parts") or []:
        if band.get("kind") != "band" or not band.get("box") or not band.get("colour"):
            continue
        b0, b1 = float(band["box"][1]), float(band["box"][3])
        if not (b0 < edge < b1):
            continue
        if float(np.sqrt(((lab_of(band["colour"]) - want) ** 2).sum())) >= SHAPE_PARAMS["closure_de"]:
            continue
        if foot:
            return b1
        return b0
    return None


def closure_edge(image_bytes: bytes, record: dict) -> dict:
    """[His answer after test day finding 3; his check of the map: the cap "as the picture shows it".] Where the
    picture's closure meets its body, as a share of the product's height in the map's own frame (the product as the
    picture stands it): across the middle two fifths of each row of the closure's box, padded, the body's field — the
    map's field beside the closure — ends where SHAPE_PARAMS["closure_run"] rows in a row are no longer the field and
    lie nearer the closure's colour than the field's, read from the body's side — so a line of type across the middle
    is never the edge, and the closure's lit rim is the closure's. ``{"part", "edge", "side"}`` or ``{"refused": why}``."""
    import numpy as np
    if record.get("state") != MAP_READ or record.get("source_sha256") != (
            hashlib.sha256(image_bytes).hexdigest() if image_bytes else None):
        return {"refused": "no map READ of this picture"}
    closure = next((p for p in record.get("parts") or [] if p.get("kind") == "closure" and p.get("box")
                    and p.get("colour")), None)
    if closure is None:
        return {"refused": "the map names no closure with its colour"}
    img, mask, pbox = _full_size(image_bytes, record)
    if img is None:
        return {"refused": pbox}
    _x0, y0, _x1, y1 = pbox
    h = y1 - y0
    cx0, cy0, cx1, cy1 = _crop(img, pbox, closure["box"])
    mid = slice(int(0.3 * (cx1 - cx0)), int(0.7 * (cx1 - cx0)))
    lab = np.stack(_lab(img[cy0:cy1, cx0:cx1]), -1)[:, mid]
    def lab_of(hx):
        rgb = np.array([int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)], np.uint8).reshape(1, 1, 3)[..., ::-1]
        return np.stack(_lab(np.ascontiguousarray(rgb)), -1)[0, 0]
    foot = (closure["box"][1] + closure["box"][3]) / 2.0 > 0.5        # a closure at the foot meets the body at its top
    # the body ends where the field beside the closure ends: a row is the field's while most of its middle lies within
    # closure_de of the field's colour (a line of type on it never fills a row); the closure begins at the first of
    # SHAPE_PARAMS["closure_run"] rows in a row that are not — its lit rim and its shade are the closure's alike
    fields = [p for p in record.get("parts") or [] if p.get("kind") == "field" and p.get("box") and p.get("colour")]
    if not fields:
        return {"refused": "the map names no field beside its closure"}
    beside = min(fields, key=lambda f: abs((f["box"][3] if foot else f["box"][1])
                                           - (closure["box"][1] if foot else closure["box"][3])))
    d_field = np.sqrt(((lab - lab_of(beside["colour"])) ** 2).sum(-1))
    d_closure = np.sqrt(((lab - lab_of(closure["colour"])) ** 2).sum(-1))
    # … and nearer the closure's colour than the field's over most of it — a line of type across the middle is neither
    rows = (((d_field < SHAPE_PARAMS["closure_de"]).mean(axis=1) < SHAPE_PARAMS["closure_field_row"])
            & ((d_closure < d_field).mean(axis=1) >= SHAPE_PARAMS["closure_field_row"]))
    order = range(len(rows)) if foot else range(len(rows) - 1, -1, -1)
    run, n = None, int(SHAPE_PARAMS["closure_run"])
    seq = list(order)
    for i, r in enumerate(seq):
        if all(rows[k] for k in seq[i:i + n]) and len(seq[i:i + n]) == n:
            run = r
            break
    if run is None:
        return {"refused": "no run of rows holds the closure's colour"}
    edge = (cy0 + run - y0) / h if foot else (cy0 + run + 1 - y0) / h
    body_edge = float(closure["box"][1] if foot else closure["box"][3])
    banded = _band_on_the_body(record, closure, foot, float(edge), lab_of)
    end = "top"
    if foot:
        end = "foot"
    if banded is not None:
        return {"part": closure.get("name"), "edge": round(banded, 5), "side": end,
                "by": "the far edge of the band of its colour the body prints where the closure meets it"}
    band = SHAPE_PARAMS["closure_edge_band"] * (float(closure["box"][3]) - float(closure["box"][1]))
    if abs(float(edge) - body_edge) > band:
        # the closure's colour too near the body's to find where it begins: its map box's own edge
        return {"part": closure.get("name"), "edge": round(body_edge, 5), "side": "foot" if foot else "top",
                "by": "its map box's edge — where its colour begins was read %s, too far inside the closure to be its "
                      "edge (its colour too near the body's)" % round(float(edge), 4)}
    return {"part": closure.get("name"), "edge": round(float(edge), 5), "side": "foot" if foot else "top"}


def sources_sha256(sources: list | None) -> str | None:
    """The identity of the words on record a trace was given (``type_sources_for``), or None for none."""
    import json
    if not sources:
        return None
    return hashlib.sha256(json.dumps([[str(v) for v in s] for s in sources], ensure_ascii=False).encode("utf-8")).hexdigest()


def edge_to_edge(got: dict, pw: float, ph: float) -> dict:
    """[his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010): "Make that part drawable (it's 122's own look: line-art rose field, oval, scallop
    band, type)".] A solid shape the picture runs edge to edge — its box within SHAPE_PARAMS["shape_edge_share"] of the
    product's left and its right edge, as 123's Garden Wrap's scalloped pink base band, however the read named it —
    runs out past the outline into the bleed (his rule 3, "EDGE TO EDGE MEANS BLEED ... Never a gap."): every point of
    it within that share of an edge it meets, its foot's too, carried SHAPE_PARAMS["bleed_reach"] of the product's
    width past it; ``edges`` the rows it meets each side at, as a band's (``trace_band``) — so the front's fit leaves it
    where the picture prints it, and the sides continue it. Any other shape is returned as it was. ``pw``, ``ph``: the
    product's size in pixels."""
    tol = SHAPE_PARAMS["shape_edge_share"]
    bx0, by0, bx1, by1 = (float(v) for v in got.get("box") or (0.5, 0.5, 0.5, 0.5))
    if bx0 > tol or bx1 < 1.0 - tol:
        return got
    reach_x = SHAPE_PARAMS["bleed_reach"]
    reach_y = reach_x * pw / ph                       # the same length, as a share of the height
    foot = by1 >= 1.0 - tol
    left_rows, right_rows = [], []

    def carried(x, y):
        if x <= bx0 + tol:
            left_rows.append(y)
            x = min(x, bx0) - reach_x
        elif x >= bx1 - tol:
            right_rows.append(y)
            x = max(x, bx1) + reach_x
        if foot and y >= by1 - tol:
            y = max(y, by1) + reach_y
        return round(x, 5), round(y, 5)

    def walk(v):
        if isinstance(v, list) and v and all(isinstance(n, (int, float)) for n in v) and len(v) % 2 == 0:
            out = []
            for i in range(0, len(v), 2):
                out.extend(carried(float(v[i]), float(v[i + 1])))
            return out
        if isinstance(v, list):
            return [walk(e) for e in v]
        return v
    edges = {}
    cubics = walk(got.get("cubics") or [])
    if left_rows:
        edges["left"] = [round(min(left_rows), 5), round(max(left_rows), 5)]
    if right_rows:
        edges["right"] = [round(min(right_rows), 5), round(max(right_rows), 5)]
    box = [round(bx0 - reach_x, 5), by0, round(bx1 + reach_x, 5), round(by1 + reach_y, 5) if foot else by1]
    return dict(got, cubics=cubics, box=box, edges=edges, bleed_reach=reach_x, picture_box=[bx0, by0, bx1, by1])


def _turned_if_tall(part: dict, pbox) -> dict:
    """[His word of 2026-10-17 on 142: "A vertical script name is set vertically in a matching script face, whole and
    inside the panel (it came out horizontal sans, cut off)"] a line of type its read gives no turn, whose box stands
    SHAPE_PARAMS["type_turn_aspect"] times taller than it is wide in the picture's own pixels and holds at least
    ``type_turn_letters`` letters, is read turned — up the side, bottom to top (90) — said; any other part as it is."""
    if part.get("kind") != "type" or part.get("rotation") in (90, -90) or not part.get("box"):
        return part
    seen = part.get("seen_text")
    if not isinstance(seen, str) or len([ch for ch in seen if ch.isalpha()]) < SHAPE_PARAMS["type_turn_letters"]:
        return part
    x0, y0, x1, y1 = pbox
    wide = (float(part["box"][2]) - float(part["box"][0])) * (x1 - x0)
    tall = (float(part["box"][3]) - float(part["box"][1])) * (y1 - y0)
    if wide <= 0 or tall < SHAPE_PARAMS["type_turn_aspect"] * wide:
        return part
    return dict(part, rotation=90, rotation_from="its box stands %.1f times taller than wide" % (tall / wide))


def trace_shapes(image_bytes: bytes, record: dict, sources: list | None = None) -> dict:
    """``container_design_shapes/1.0`` for the picture the map ``record`` READ: the shape of each part this module
    traces — a band that ends in a gold edge (``trace_band``) and a gold rule (``trace_rule``) — beside the box the map
    gives it; a part it refuses is listed with its reason. Pure; nothing written, nothing paid.
    [The owner's finding on design 119, 2026-10-03.] And each solid shape (``trace_shape``) — on a carton's panel, each
    field after its ground too."""
    from apps.pipeline.services import line_art
    rec = {"schema_version": SHAPES_SCHEMA, "params": dict(SHAPE_PARAMS),
           "source_sha256": hashlib.sha256(image_bytes).hexdigest() if image_bytes else None, "problems": [],
           # [his rule 1, 2026-10-05] the words on record a display line is set in — the trace is made again when they change
           "sources_sha256": sources_sha256(sources)}
    if record.get("state") != MAP_READ or record.get("source_sha256") != rec["source_sha256"]:
        return {**rec, "state": SHAPES_REFUSED, "reason": "no map READ of this picture"}
    img, mask, pbox = _full_size(image_bytes, record)
    if img is None:
        return {**rec, "state": SHAPES_REFUSED, "reason": pbox}
    parts = [_turned_if_tall(p, pbox) for p in record.get("parts") or []]
    # [his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010): "Make that
    # part drawable (it's 122's own look: line-art rose field, oval, scallop band, type)"] a band that is neither
    # gold-edged nor a straight stripe — its top or foot shaped, a scallop, a wave — is traced below as the shape it is
    shaped_bands = []
    for kind, tracer in (("band", trace_band), ("rule", trace_rule), ("mark", trace_mark), ("type", trace_type)):
        for part in (p for p in parts if p.get("kind") == kind and p.get("box")):
            if kind == "band":
                # [his look at 117 drawn from its map, 2026-10-02] the field its drips hang into, by the map's boxes
                into = [f for f in parts if f.get("kind") == "field" and f.get("box") and f.get("colour")
                        and f["box"][1] <= part["box"][3] <= f["box"][3]]
                part = dict(part, field_below=into[0]["colour"]) if into else part
                # [his rules, 2026-10-02, rule 2] a rule the map gives at the band's top closes it there: its gold edge
                # runs along its drips, not under the rule
                closed = [r for r in parts if r.get("kind") == "rule" and r.get("box")
                          and abs(float(r["box"][3]) - float(part["box"][1])) <= 0.02]
                part = dict(part, rule_above=closed[0].get("name")) if closed else part
            framed = kind == "rule" and min(part["box"][2] - part["box"][0],
                                             part["box"][3] - part["box"][1]) >= FRAME_MIN_SHARE
            if framed:
                # [His review of 127, 130, 131 and 132, 2026-10-15, C: the designer's eye on 132, "no gold inner frame
                # round the label"] a rule the read boxes round a box both ways (132's "gold cartouche frame", read a
                # rule the size of its cartouche, in the blue of the tiles beside it) is the frame it is — traced as a
                # window's named frame is (``window_frame``: round its box widened, in the picture's gold where its
                # name or finish says gold); the straight rule only where no frame is found. It was traced as one
                # straight gold line along the cartouche's top
                other = window_frame(img, mask, pbox, part, rec.get("frames") or [])
                if other is not None and "refused" not in other:
                    # … and the window it rings (its box within reach of the frame's) is what the frame holds
                    # (``line_art.trace_window``): 132's cartouche read 0.80 deep where its frame stands at 0.76
                    rings = [p.get("name") for p in parts if p.get("kind") == "window" and p.get("box") and all(
                        abs(float(a) - float(b)) <= WINDOW_FRAME_REACH for a, b in zip(p["box"], other["box"]))]
                    rec.setdefault("frames", []).append(dict(other, part=part.get("name"),
                                                             window=rings[0] if rings else part.get("name")))
                    continue
            got = tracer(img, mask, pbox, part)
            if kind == "rule" and "refused" in got:
                # [his go of 2026-10-08, item 1: "Trace line art and frames in ANY colour (not only gold) ... thin frames,
                # borders"] a frame or a border round a box (``line_art.trace_frame``), else a line in its own ink
                framed = min(part["box"][2] - part["box"][0], part["box"][3] - part["box"][1]) >= FRAME_MIN_SHARE
                other = (line_art.trace_frame(img, mask, pbox, part) if framed
                         else line_art.trace_lines(img, mask, pbox, part, []))
                if "refused" not in other:
                    rec.setdefault("frames" if framed else "lines", []).append(other)
                    continue
                got = {"refused": "%s; in any ink: %s" % (got["refused"], other["refused"])}
            if kind == "band" and "refused" in got and "plain stripe" in got["refused"]:
                # [his second test blocker on design 123] 123's Garden Wrap, read twice: its scalloped pink base band
                # was named a "shape" by one read (traced, drawn) and a "band" by the other (refused as no plain stripe,
                # its colour running on 12 pixels past its straight rows) — the same band, traced the same way either way
                shaped_bands.append((part, got["refused"]))
                continue
            if kind == "band" and part.get("rule_above") and "refused" not in got:
                got["rule_above"] = part["rule_above"]
            if kind == "rule" and "refused" not in got:
                # [his rules, 2026-10-02, rule 3] a rule that closes a band the picture runs edge to edge runs edge to
                # edge with it, where its own gold fades before the product's side (117's, shaded on the right)
                with_band = {side for b in rec.get("bands") or [] if b.get("rule_above") == part.get("name")
                             for side in b.get("edges") or {}}
                if with_band - set(got.get("edges") or []):
                    sides = sorted(with_band | set(got.get("edges") or []))
                    bx0, by0, bx1, by1 = got["box"]
                    got = dict(got, edges=sides, drawn_box=[
                        round(bx0 - SHAPE_PARAMS["bleed_reach"] * ("left" in sides), 5), by0,
                        round(bx1 + SHAPE_PARAMS["bleed_reach"] * ("right" in sides), 5), by1],
                        edges_with=[b["part"] for b in rec.get("bands") or [] if b.get("rule_above") == part.get("name")])
            if "refused" in got:
                rec["problems"].append("%s %r: %s" % (kind, part.get("name"), got["refused"]))
            else:
                rec.setdefault(kind + "s", []).append(got)
    # [his go of 2026-10-08, item 3] a line or a mark set in its box whose box holds no ink of its own takes the ink of
    # the traced line beside it
    traced = (rec.get("types") or []) + (rec.get("marks") or [])
    for got in traced:
        if got.get("set") and not got.get("ink"):
            got["ink"] = _ink_beside(got, traced)
    # [his go of 2026-10-08] set lines on one row that touch are one line (148's "Hand Cream /" and "كريم اليدين", read as
    # two boxes end to end): set together, in the words on record for the whole line, never over each other
    _join_rows(rec.get("types") or [])
    # [his answer after test day finding 3, (3)] a line the picture letters in script, traced too
    for line in rec.get("types") or []:
        if line.get("set"):
            continue                       # [his go of 2026-10-08, item 3] set, never traced from the picture's letters
        if str(line.get("lettering")).lower() == "script":
            got = trace_script(img, mask, pbox, line)
            if "refused" in got:
                rec["problems"].append("type %r traced: %s" % (line.get("part"), got["refused"]))
            else:
                line["outlines"] = got
            # [his look at 117 drawn from its map, 2026-10-02] and its lettering layered, each layer even
            layered = trace_lettering(img, mask, pbox, line)
            if "refused" in layered:
                rec["problems"].append("type %r layered: %s" % (line.get("part"), layered["refused"]))
            else:
                line["lettering_layers"] = layered
            # [his test blocker on design 124, 2026-10-11, (6): "The script name: set in the granted face closest to the
            # concept's script"] a script whose letters are their own ink — 124's fine gold script, read by the ring's
            # reading as the four loops its gold ring encloses (Chango, 0.10) — read as its ink as a display line's
            # letters are, and set in the face closest to THAT where it comes closer than the ring's reading on both
            # measures (Great Vibes, 0.17 and 0.49); 117's ringed letters keep their ring's reading
            solid = set_display(img, mask, pbox, line)
            ringed = layered["set"] if "refused" not in layered and "set" in layered else None
            if solid.get("state") == "SET" and (ringed is None or ringed.get("state") != "SET" or (
                    float(solid["iou"]) > float(ringed["iou"]) and float(solid["outline"]) > float(ringed["outline"]))):
                line["lettering_set"] = solid
    # [the owner's finding on design 119, 2026-10-03] a line the picture letters in a display face, or turns, traced
    # (``trace_script``) and set in the closest face (``set_display``): drawn as the picture letters it, never typed
    # across where the picture stands it on end
    for line in rec.get("types") or []:
        # [his answers after the fixes for design 122, (2)] a line that states a size is set in his size's words, never
        # traced from the picture's own figures
        if size_stated(line.get("seen")) is not None or line.get("set"):
            continue
        if str(line.get("lettering")).lower() == "script" or not (
                str(line.get("lettering")).lower() == "display" or line.get("rotation") in (90, -90)):
            continue
        got = trace_script(img, mask, pbox, line)
        if "refused" in got:
            rec["problems"].append("type %r traced: %s" % (line.get("part"), got["refused"]))
            continue
        line["outlines"] = got
        # [his rule 1, 2026-10-05: "My brief's words win over the picture's text"] the line is set in the words a source
        # on record gives it ("Rose Glaze", where the picture letters "RoseGlaze"), never the picture's own spelling
        found = type_sources([line], sources)[0] if sources else {}
        if found.get("words") and found.get("source") not in (PICTURE_ENGLISH, PICTURE_ARABIC):
            line["words"] = found["words"]
        line["lettering_set"] = set_display(img, mask, pbox, line)
    _one_face_for_the_name(rec.get("types") or [], sources, img, mask, pbox)
    # [the owner's finding on design 119, 2026-10-03] each solid shape the picture prints — and on a carton's panel each
    # field after its ground, a large area of one colour on it — traced, the parts printed on it drawn over it
    fields = [p for p in parts if p.get("kind") == "field" and p.get("box")]
    solid = [p for p in parts if p.get("kind") == "shape" and p.get("box")]
    if record.get("face_box_px"):
        solid += fields[1:]
    ground = fields[0].get("colour") if fields else None
    inks = [p for p in parts if p.get("kind") in ("type", "mark", "motif", "rule", "band", "window") and p.get("box")]
    pw, ph = float(pbox[2] - pbox[0]), float(pbox[3] - pbox[1])
    for part in solid:
        got = trace_shape(img, mask, pbox, part, ground, inks)
        if "refused" in got:
            rec["problems"].append("%s %r: %s" % (part.get("kind"), part.get("name"), got["refused"]))
        else:
            layers, said = shape_layers(img, mask, pbox, part, ground, [p for p in inks if p.get("kind") != "window"])
            rec["problems"] += said
            if layers:
                # the shape's box everything it draws (his review of 119, point 4): its layers' too
                boxes = [got["box"]] + [layer["box"] for layer in layers]
                got = dict(got, layers=layers, box=[min(b[0] for b in boxes), min(b[1] for b in boxes),
                                                    max(b[2] for b in boxes), max(b[3] for b in boxes)])
            rec.setdefault("shapes", []).append(edge_to_edge(got, pw, ph))
    for part, as_band in shaped_bands:
        # [his second test blocker on design 123] the shaped band, as the shape it is — the parts printed over it drawn
        # over it, never itself
        got = trace_shape(img, mask, pbox, part, ground, [p for p in inks if p.get("name") != part.get("name")])
        if "refused" in got:
            rec["problems"].append("band %r: %s; as a shape: %s" % (part.get("name"), as_band, got["refused"]))
        else:
            rec.setdefault("shapes", []).append(edge_to_edge(dict(got, shaped_band=True), pw, ph))
    drips = [p for p in parts if p.get("kind") == "motif" and "drip" in str(p.get("name")).lower()]
    if drips and rec.get("bands"):
        rec["bands"][0]["drips_read"] = drips[0].get("count")       # the map's read beside the trace's count
    # [His goal after the pitch page, 2026-10-15, A (4): "132's … gold double-rule frame was missing".] the frame a read
    # names in its window's own words ("ivory cartouche with gold frame", finished "gold foil") — never a part of its
    # own, so never traced — traced round the window, in its gold where it is gold
    for part in (p for p in parts if p.get("kind") == "window" and p.get("box")):
        got = window_frame(img, mask, pbox, part, rec.get("frames") or [])
        if got is not None and "refused" in got:
            rec["problems"].append("window %r, its frame: %s" % (part.get("name"), got["refused"]))
        elif got is not None:
            rec.setdefault("frames", []).append(got)
    # [his go of 2026-10-08, item 1] a cleared window, inside the frame that rings it
    for part in (p for p in parts if p.get("kind") == "window" and p.get("box")):
        got = line_art.trace_window(img, mask, pbox, part, rec.get("frames") or [])
        if "refused" in got:
            rec["problems"].append("window %r: %s" % (part.get("name"), got["refused"]))
        else:
            rec.setdefault("windows", []).append(got)
    # [his answer after test day finding 3] every other motif: scattered small shapes (117's sparkle stars) where the read
    # names them so — [his go of 2026-10-08, item 1] else line art in its own ink (stems, leaves, buds, outlines): 149's
    # red rose engraving had been taken for one gold sparkle
    others = [p for p in parts if p.get("kind") in ("type", "mark") and p.get("box")]
    kept_out = [{"box": p["box"], "kind": p.get("kind"), "colour": p.get("colour"),
                 "oval": p.get("kind") == "window" and line_art.oval_named(p)}
                for p in parts if p.get("kind") in ("type", "mark", "window", "closure") and p.get("box")]
    for part in (p for p in parts if p.get("kind") == "motif" and p.get("box") and p not in drips):
        if any(word in str(part.get("name")).lower() for word in SCATTER_WORDS):
            got = trace_scatter(img, mask, pbox, part, others)
            if "refused" in got:
                rec["problems"].append("motif %r: %s" % (part.get("name"), got["refused"]))
            else:
                rec.setdefault("scatters", []).append(got)
            continue
        # a motif on the closure keeps the closure; every other keeps out the parts beside it, and the frames' lines
        # [His review of 127, 130, 131 and 132, 2026-10-15, C: the designer's eye on 132, "the flower emblem under
        # BBROSE"] and a motif printed ON a window — its box inside the window's — keeps that window: 132's lily, in its
        # cartouche, was refused as "nothing of the product outside its other parts"
        avoid = [a for a in kept_out if not (a["kind"] in ("closure", "window") and _inside(part["box"], a["box"]))]
        # never the gold scatter in its place: a line-art motif read as a sparkle is a wrong drawing (149's engraving)
        got = line_art.trace_lines(img, mask, pbox, part, avoid + [{"frame": f} for f in rec.get("frames") or []])
        if "refused" in got:
            rec["problems"].append("motif %r: %s" % (part.get("name"), got["refused"]))
        else:
            rec.setdefault("lines", []).append(got)
    return {**rec, "state": SHAPES_TRACED}


#: [His goal after the pitch page, 2026-10-15, A (4).] the words a read names a window's own frame with ("ivory
#: cartouche with gold frame") …
FRAME_WORDS = ("frame", "border", "rule", "edged", "outline", "trim")
#: … never a window the read names an arch (its gold rim is traced as its arch: his goal of 2026-10-13, (7)) …
ARCH_WORDS = ("arch", "dome")
#: … and the frame found for it lies within this share of the product of the window's box on every side (132's, read
#: 0.019 outside it): never a straight run of the pattern further out
WINDOW_FRAME_REACH = 0.04


def window_frame(img, mask, pbox, part: dict, frames: list) -> dict | None:
    """[His goal after the pitch page, 2026-10-15, A (4).] The frame round a window ``part`` that the read names in the
    window's own words (FRAME_WORDS in its name, or a gold finish): ``line_art.trace_frame`` round its box widened by
    WINDOW_FRAME_REACH, in the picture's gold where its name or finish says gold, kept where it lies within that reach of
    the box on every side — ``{... the frame, "window": its name}``; ``{"refused": why}`` where its name names one;
    None where the read names no frame, the window is an oval or an arch, or a frame already traced rings it."""
    from apps.pipeline.services import line_art
    words = (str(part.get("name")) + " " + str(part.get("finish"))).lower()
    gold = "gold" in words
    named = any(word in str(part.get("name")).lower() for word in FRAME_WORDS)
    if not (gold or named):
        return None
    # an oval window's ring and an arched window's gold rim are traced as what they are (``line_art.trace_window``):
    # never boxed by a four-sided frame (125's arch, his goal of 2026-10-13, (7))
    if line_art.oval_named(part) or any(word in str(part.get("name")).lower() for word in ARCH_WORDS):
        return None
    bx0, by0, bx1, by1 = (float(v) for v in part["box"])
    reach = WINDOW_FRAME_REACH
    for f in (f for f in frames if f.get("box")):
        if all(abs(float(a) - float(b)) <= reach for a, b in zip(f["box"], (bx0, by0, bx1, by1))):
            return None
    wide = dict(part, colour=None, box=[max(0.0, bx0 - reach), max(0.0, by0 - reach), min(1.0, bx1 + reach),
                                        min(1.0, by1 + reach)])
    got = line_art.trace_frame(img, mask, pbox, wide, gold=gold)
    if "refused" in got:
        return got if named else None          # a gold finish alone names no frame: none found is nothing missing
    if not all(abs(float(a) - float(b)) <= reach for a, b in zip(got["box"], (bx0, by0, bx1, by1))):
        return {"refused": "the frame found lies further than %g of the product from its box" % reach}
    return dict(got, part=str(part.get("name")) + " — its frame", window=part.get("name"))


#: [his go of 2026-10-08, item 1] the words a read names a motif of small scattered shapes with (117's sparkle stars) —
#: every other motif is line art
SCATTER_WORDS = ("sparkle", "star", "glint", "twinkle", "glitter", "spark")
#: … and a rule whose box is at least this share of the product both ways is a frame or a border round it
FRAME_MIN_SHARE = 0.04


def _inside(box, outer) -> bool:
    """``box`` within ``outer``, to a hundredth of the product."""
    return (box[0] >= outer[0] - 0.01 and box[1] >= outer[1] - 0.01 and box[2] <= outer[2] + 0.01
            and box[3] <= outer[3] + 0.01)


SCORE_SCHEMA = "container_design_score/1.0"
#: the bars "one hundred percent" is read against — the executor's, told to him before his "go" (OWNER_BLOCKER_CLEARANCE.md,
#: the block of his answer after test day finding 3, transcribed at 23d4375), his to change; no ruled number moves
SCORE_BARS = {"delta_e": 3.0, "mm": 1.0}
#: the drawn product is read at this many pixels a millimetre — fine enough for a 0.30 mm rule to hold pixels of its own
PRODUCT_PX_PER_MM = 6.0


def product_png(doc, px_per_mm: float = PRODUCT_PX_PER_MM) -> bytes | None:
    """The drawn product ALONE as a picture — PNG bytes of the document's product group (``Container``: the body, the
    cap and everything printed on them) on a transparent ground, cropped to the body's own outline; the sheet around it
    (the reference, the panels, the swatches, the titles) is not drawn. None where the document holds no product."""
    import os
    import tempfile

    import fitz
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Document, Group, Path
    product = next((n for n, _ in doc.walk() if isinstance(n, Group) and n.name == "Container"), None)
    body = next((n for n, _ in doc.walk() if isinstance(n, Path) and n.name == "body"), None)
    if product is None or body is None:
        return None
    xs = [p.x for p in body.segments if hasattr(p, "x")]
    ys = [p.y for p in body.segments if hasattr(p, "y")]
    alone = Document(page_w=doc.page_w, page_h=doc.page_h, title="product", root=Group(name="root",
                                                                                       children=[product]))
    with tempfile.TemporaryDirectory(prefix="design_score_") as scratch:
        pdf = emit_pdf_ai(alone, os.path.join(scratch, "product.ai"))
        # rendered at px_per_mm with its ground transparent (the preview's rasteriser, sips, draws at 72 dpi whatever
        # it is asked, too coarse for a thin rule)
        with fitz.open(pdf) as book:
            zoom = px_per_mm * 25.4 / 72.0
            pix = book[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=True)
        from PIL import Image
        im = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
        box = (int(min(xs) * px_per_mm), int(min(ys) * px_per_mm), int(max(xs) * px_per_mm) + 1,
               int(max(ys) * px_per_mm) + 1)
        buf = io.BytesIO()
        im.crop(box).save(buf, "PNG")
        return buf.getvalue()


#: [his answer 3 of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6badb27): "The score's yardstick is a full-size
#: trace of the concept, so it can say 'matches' without my eye."] the score against the concept's full-size trace
SCORE_TRACED_SCHEMA = "container_design_score/2.0"
#: the yardstick, in words
SCORE_YARDSTICK = "the concept's full-size trace (container_design_shapes/1.0), part by part"
#: how near a pixel's colour lies to a part's ink to count as that ink — for how much of its traced box the picture inks,
#: which is how many of the drawn pixels its drawn ink is read from, and for the overlap figure; and how fine the drawing
#: is read for it, so a 6 pt letter's strokes hold pixels of their own — the executor's working figures, recorded on
#: every score, no ruled number
SCORE_INK_DE = 12.0
SCORE_PX_PER_MM = 24.0
#: a box's coordinate on each side a part can run edge to edge on (x0 on the left, x1 on the right)
SIDE_X_INDEX = {"left": 0, "right": 2}


def _lab_of(bgr):
    """CIE L*a*b* of BGR pixels (uint8), L in 0..100."""
    import cv2
    import numpy as np
    return cv2.cvtColor((np.asarray(bgr, np.float32) / 255.0).reshape(-1, 1, 3), cv2.COLOR_BGR2LAB).reshape(-1, 3)


def _traced_parts(shapes: dict) -> list:
    """Every part the full-size trace drew — ``{"part", "kind", "box", "ink"}``, its box in fractions of the product,
    held inside it — bands by their outline, rules, scattered motifs by all their shapes, type lines and marks."""
    out = []

    def add(part, kind, pts_or_box, ink, is_box=False):
        if not pts_or_box or not ink:
            return
        if is_box:
            x0, y0, x1, y1 = (float(v) for v in pts_or_box)
        else:
            xs, ys = [float(p[0]) for p in pts_or_box], [float(p[1]) for p in pts_or_box]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        box = [max(0.0, x0), max(0.0, y0), min(1.0, x1), min(1.0, y1)]
        if box[2] > box[0] and box[3] > box[1]:
            out.append({"part": part, "kind": kind, "box": [round(v, 5) for v in box], "ink": ink})
    for band in shapes.get("bands") or []:
        add(band["part"], "band", band.get("outline"), band.get("fill"))
    for rule in shapes.get("rules") or []:
        add(rule["part"], "rule", rule.get("box"), rule.get("ink"), is_box=True)
    for scatter in shapes.get("scatters") or []:
        add(scatter["part"], "motif", [p for star in scatter.get("stars") or [] for p in star["outline"]],
            scatter.get("ink"))
    # [his go of 2026-10-08, item 1] line art by its strokes, a frame and a window by their boxes
    for line in shapes.get("lines") or []:
        add(line["part"], "motif", [p for s in line.get("strokes") or [] for p in s["points"]], line.get("ink"))
    for frame in shapes.get("frames") or []:
        add(frame["part"], "rule", frame.get("box"), frame.get("ink"), is_box=True)
    for window in shapes.get("windows") or []:
        add(window["part"], "window", window.get("box"), window.get("fill"), is_box=True)
    for line in shapes.get("types") or []:
        add(line["part"], "type", line.get("box"), line.get("ink"), is_box=True)
    for mark in shapes.get("marks") or []:
        add(mark["part"], "mark", mark.get("box"), mark.get("ink"), is_box=True)
    return out


def score_traced(shapes: dict, image_bytes: bytes, record: dict, drawn_png: bytes, *, drawn_boxes: dict,
                 size_mm, edge_to_edge: list | None = None) -> dict:
    """[His answer 3 of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6badb27): "The score's yardstick is a
    full-size trace of the concept, so it can say 'matches' without my eye."] ``container_design_score/2.0`` — the
    drawing (``drawn_png``: ``product_png``) against the concept's FULL-SIZE TRACE (``shapes``: ``trace_shapes`` of
    ``image_bytes``, the picture the map ``record`` READ), part by part (``_traced_parts``): the drawn part's box as the
    drawing records it (``drawn_boxes``) beside its traced box, in millimetres at the product's size (``size_mm``: width,
    height) — on each side a part the drawing runs edge to edge (``edge_to_edge``: the map front's own record) no place is
    measured: it is drawn past the product's side, cut by its outline (his rule 3); the drawn ink — the median of as
    many of the drawn pixels in its traced box, nearest its traced ink, as the picture's box holds of that ink (a pixel
    within SCORE_INK_DE of it), so a letter is read on its strokes and a band on its fill — beside the traced ink, in
    CIE76 ΔE, the drawing read at SCORE_PX_PER_MM so a small letter's strokes hold pixels of their own; and, a figure with no
    bar, the overlap of the two inks' pixels in that box, the drawing's box read at the picture's full size. A part
    MATCHES under both bars (SCORE_BARS); the drawing MATCHES its concept when every traced part does. Nothing is
    written."""
    import cv2
    import numpy as np
    from PIL import Image
    rec = {"schema_version": SCORE_TRACED_SCHEMA, "yardstick": SCORE_YARDSTICK, "bars": dict(SCORE_BARS),
           "figures": {"ink_de": SCORE_INK_DE, "px_per_mm": SCORE_PX_PER_MM}, "parts": [], "passed": 0, "of": 0,
           "matches": False}
    img, _mask, pbox = _full_size(image_bytes, record)
    if img is None or shapes.get("state") != SHAPES_TRACED:
        rec["unread"] = "no full-size trace of the concept to measure against: %s" % (
            pbox if img is None else "its shapes were not traced")
        return rec
    rgba = np.asarray(Image.open(io.BytesIO(drawn_png)).convert("RGBA"))
    drawn = cv2.cvtColor(rgba[..., :3].copy(), cv2.COLOR_RGB2BGR)
    dh, dw = drawn.shape[:2]
    px0, py0, px1, py1 = pbox
    w_mm, h_mm = size_mm
    sides = {e["part"]: [side for side in e.get("sides") or [] if side in ("left", "right")]
             for e in edge_to_edge or [] if e.get("part")}
    for part in _traced_parts(shapes):
        fx0, fy0, fx1, fy1 = part["box"]
        ink = np.asarray(_lab_of(np.array([[[int(part["ink"][5:7], 16), int(part["ink"][3:5], 16),
                                              int(part["ink"][1:3], 16)]]], np.uint8))[0])
        cx0, cx1 = int(px0 + fx0 * (px1 - px0)), max(int(px0 + fx0 * (px1 - px0)) + 1, int(px0 + fx1 * (px1 - px0)))
        cy0, cy1 = int(py0 + fy0 * (py1 - py0)), max(int(py0 + fy0 * (py1 - py0)) + 1, int(py0 + fy1 * (py1 - py0)))
        dx0, dx1 = int(fx0 * dw), max(int(fx0 * dw) + 1, int(fx1 * dw))
        dy0, dy1 = int(fy0 * dh), max(int(fy0 * dh) + 1, int(fy1 * dh))
        seen = drawn[dy0:dy1, dx0:dx1][rgba[dy0:dy1, dx0:dx1, 3] > 127]
        row = {"part": part["part"], "kind": part["kind"], "traced_box": part["box"], "traced_ink": part["ink"]}
        concept = img[cy0:cy1, cx0:cx1]
        a = (np.linalg.norm(_lab_of(concept.reshape(-1, 1, 3)) - ink, axis=1) <= SCORE_INK_DE)
        row["traced_ink_share"] = round(float(a.mean()), 4)
        if len(seen):
            lab = _lab_of(seen.reshape(-1, 1, 3))
            near = np.argsort(np.linalg.norm(lab - ink, axis=1))[:max(1, int(round(float(a.mean()) * len(lab))))]
            got = np.median(lab[near], axis=0)
            row["drawn_ink"] = _hex(got)
            row["delta_e"] = round(float(np.linalg.norm(got - ink)), 1)
            ours = cv2.resize(drawn[dy0:dy1, dx0:dx1], (concept.shape[1], concept.shape[0]),
                              interpolation=cv2.INTER_AREA)
            b = (np.linalg.norm(_lab_of(ours.reshape(-1, 1, 3)) - ink, axis=1) <= SCORE_INK_DE)
            union = int((a | b).sum())
            row["ink_overlap"] = round(float((a & b).sum()) / union, 3) if union else None
        else:
            row["drawn_ink"], row["delta_e"], row["ink_overlap"] = None, None, None
        placed = drawn_boxes.get(part["part"])
        if placed is not None:
            held = [max(0.0, min(1.0, float(v))) for v in placed]
            # his rule 3: a side the drawing runs edge to edge is drawn past the product's side, cut by its outline —
            # its place there is the product's own edge, not a place measured
            skip = {SIDE_X_INDEX[side] for side in sides.get(part["part"]) or []}
            row["drawn_box"] = [round(v, 5) for v in held]
            row["offset_mm"] = round(max(abs(a_ - b_) * (w_mm if i % 2 == 0 else h_mm)
                                         for i, (a_, b_) in enumerate(zip(held, part["box"])) if i not in skip), 1)
            if skip:
                row["edge_to_edge"] = sorted(sides[part["part"]])
        else:
            row["offset_mm"] = None
            row["place"] = "not recorded: the drawing does not draw this part where the trace puts it"
        row["matches"] = bool(row["delta_e"] is not None and row["delta_e"] <= SCORE_BARS["delta_e"]
                              and row["offset_mm"] is not None and row["offset_mm"] <= SCORE_BARS["mm"])
        rec["parts"].append(row)
    rec["of"] = len(rec["parts"])
    rec["passed"] = sum(1 for r in rec["parts"] if r["matches"])
    rec["matches"] = bool(rec["of"]) and rec["passed"] == rec["of"]
    return rec


def score(record: dict, drawn_png: bytes, *, drawn_boxes: dict | None = None, size_mm=None) -> dict:
    """``container_design_score/1.0`` — the drawing against the concept's map, part by part: each part the map names is
    measured on the drawn product (``product_png``) exactly as the map measured it on the concept (``read_pixels`` over
    the drawn pixels, ``_colour_parts`` at the part's own box), and its drawn colour set beside the concept's, in CIE76
    ΔE; where the drawing records where it drew a part (``drawn_boxes``: name → its box as fractions of the product)
    and the product's size is given (``size_mm``: width, height), the part's place and size beside the concept's, in
    millimetres; each part PASSES only under both bars (SCORE_BARS), and a part whose place is not recorded does not
    pass. Nothing is written."""
    import numpy as np
    from PIL import Image
    from apps.ire.container_brand_usage import _delta_e_hex
    rec = {"schema_version": SCORE_SCHEMA, "bars": dict(SCORE_BARS), "parts": [], "passed": 0, "of": 0}
    im = Image.open(io.BytesIO(drawn_png)).convert("RGBA")
    rgba = np.asarray(im)
    mask = (rgba[..., 3] > 127).astype(np.uint8)
    if not mask.any() or record.get("state") != MAP_READ:
        rec["unread"] = "no drawn product, or no map read, to set side by side"
        return rec
    import cv2
    img = cv2.cvtColor(rgba[..., :3].copy(), cv2.COLOR_RGB2BGR)
    body, labels = read_pixels(img, mask)
    px0, py0, px1, py1 = body["product_box_px"]
    pw, ph = float(px1 - px0), float(py1 - py0)
    parts = []
    for part in record.get("parts") or []:
        x0, y0, x1, y1 = part["box"]
        parts.append({"kind": part["kind"], "name": part["name"],             # its box, held inside the picture
                      "_px": [max(0, int(round(px0 + x0 * pw))), max(0, int(round(py0 + y0 * ph))),
                              min(mask.shape[1], int(round(px0 + x1 * pw))), min(mask.shape[0], int(round(py0 + y1 * ph)))]})
    _colour_parts(parts, labels, body, np.zeros(mask.shape, bool))
    for concept, drawn in zip(record.get("parts") or [], parts):
        row = {"name": concept["name"], "kind": concept["kind"], "concept": concept.get("colour"),
               "drawn": drawn.get("colour")}
        de = (_delta_e_hex(concept["colour"], drawn["colour"]) if concept.get("colour") and drawn.get("colour")
              else None)
        row["delta_e"] = round(de, 1) if de is not None else None
        placed = (drawn_boxes or {}).get(concept["name"])
        if placed is not None and size_mm is not None:
            w, h = size_mm
            row["offset_mm"] = round(max(abs(a - b) * (w if i % 2 == 0 else h)
                                         for i, (a, b) in enumerate(zip(placed, concept["box"]))), 1)
        else:
            row["offset_mm"] = None
            row["place"] = "not recorded: the drawing does not draw this part where the map puts it"
        row["passes"] = bool(row["delta_e"] is not None and row["delta_e"] <= SCORE_BARS["delta_e"]
                             and row["offset_mm"] is not None and row["offset_mm"] <= SCORE_BARS["mm"])
        rec["parts"].append(row)
    rec["of"] = len(rec["parts"])
    rec["passed"] = sum(1 for r in rec["parts"] if r["passes"])
    return rec
