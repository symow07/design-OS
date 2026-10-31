"""[His final goal, 2026-10-05 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 32e9aaf), B1: "INSIDE AND TOP PRINTING. Never
leave the inside blank or white. Do NOT search my past designs for it. An "Inside reference" picture slot beside the
inspiration box (one or more pictures). The brief may describe it in words ("Inside: ..."). The inside is drawn in vector
following the reference and the brief's words, in the design's own colours; followed in pattern and style, never pasted
or copied 1:1. With neither given, it uses the concept's own motif and colours. The flaps carry design (logo or
pattern). Two artboards, OUTSIDE and INSIDE. At the size step he chooses per design: as referenced (default), solid
colour, or plain."]

A carton's inside print, planned and drawn:

- WHAT IT FOLLOWS (``plan``): his Inside reference pictures, each read ONCE into a pattern and a style
  (``read_picture``: the kind of pattern, its direction, its density, whether its ground is the dark or the light tone,
  its character in words — never its pixels, never its colours as codes; a picture read before costs nothing), and his
  brief's "Inside:" words, read here for the same things ($0; ``spec_from_words``) — his words win over a picture where
  both say a thing. With neither, the concept's own motif: the front's traced shape repeated. Nothing is searched for in
  his past designs or the materials.
- ITS COLOURS: the design's own — the ground the concept's map reads, and the front's ink that stands out most from it;
  the dark tone grounds the inside where the pattern is light on dark, as a picture or his words say, and by default.
- WHAT IS DRAWN (``inside_group``): the whole sheet's inside, in vector — its ground, the pattern as one compound path
  in the other tone — clipped to the die's bleed outline, with the strip the glue tab is glued onto left unprinted, and
  mirrored, as the sheet is seen from its inside; the die's lines over it for the printer. "Solid" draws the dark tone
  alone; "plain" draws nothing but the lines (his choice at the size step).
- THE FLAPS (``flap_nodes``): the lid carries the house mark, turned to read from the front when the carton is closed;
  the dust flaps and the bottom tuck carry the concept's own motif, else the mark — never a pattern the design does not
  have (his goal of 2026-10-06, item 10), on the outside."""
from __future__ import annotations

import math
import re

KIND = "inside_reference"
OPERATION = "inside_read"
MODES = ("referenced", "solid", "plain")
DEFAULT_MODE = "referenced"
PATTERNS = ("stripes", "dots", "waves", "checks", "chevrons", "motif", "grid", "solid")
#: what a word of his says of the pattern — the first kind his words name leads
PATTERN_WORDS = (
    ("waves", ("wave", "waves", "wavy", "swirl", "swirls", "swirling", "liquid", "ripple", "ripples", "flowing",
               "marble", "marbled")),
    ("stripes", ("stripe", "stripes", "striped", "pinstripe", "pinstripes", "lines", "bands", "banded")),
    ("dots", ("dot", "dots", "dotted", "polka", "spot", "spots", "spotted", "confetti", "halftone")),
    ("checks", ("check", "checks", "checked", "checker", "checkerboard", "gingham", "plaid")),
    ("chevrons", ("chevron", "chevrons", "zigzag", "zig-zag", "zigzags", "herringbone")),
    ("motif", ("motif", "logo", "logos", "monogram", "silhouette", "silhouettes", "icon", "icons", "repeat",
               "repeated", "scattered", "flowers", "floral", "hearts", "stars", "petals")),
    ("grid", ("grid", "lattice", "tiles", "tiled")),
    ("solid", ("solid", "flat")),
)
#: the pattern's pitch (mm) by its density
PITCH_MM = {"dense": 4.0, "medium": 6.0, "sparse": 9.0}
#: an inside reference read into its pattern and style (``apps/pipeline/services/inside_read.py``): what the reader is
#: asked
SYSTEM = """You read ONE picture of the INSIDE print a designer wants for a cosmetics folding carton at BBROSE. Read its
PATTERN and STYLE so a NEW vector pattern can be drawn in the design's own colours — never a copy of the picture.

Return ONE JSON object and nothing else:
{
  "pattern": "one of: stripes, dots, waves, checks, chevrons, motif, grid, solid",
  "direction": "one of: diagonal, vertical, horizontal, none",
  "density": "one of: sparse, medium, dense",
  "tone": "dark if the pattern's ground is darker than its pattern, else light",
  "motif_words": "if the pattern repeats a shape: what the shape is, under 10 words; else empty",
  "style": "the pattern's character, under 25 words — rhythm, scale, edges, spacing",
  "take": "one sentence: what the new inside print should take from this picture, as qualities",
  "seen_not_taken": ["each brand name, logo, trademark or line of text you can see — NEVER reproduced"]
}
Rules: describe qualities, never an object to reproduce; no hex codes; no brand names outside seen_not_taken."""
READ_MAX_TOKENS = 500
FIELDS = ("pattern", "direction", "density", "tone", "motif_words", "style", "take")
#: the lid's mark spans this share of the lid's width
LID_MARK_SHARE = 0.55


def brief_inside_words(brief: str) -> str:
    """His brief's "Inside: ..." words — the line, and the lines under it until a blank line or another heading."""
    lines = str(brief or "").splitlines()
    out, on = [], False
    for line in lines:
        m = re.match(r"^\s*inside(?:\s+print)?\s*:\s*(.*)$", line, re.IGNORECASE)
        if m:
            out, on = [m.group(1).strip()], True
            continue
        if on:
            if not line.strip() or re.match(r"^\s*[A-Z][\w ]{0,30}:", line):
                break
            out.append(line.strip())
    return " ".join(w for w in out if w).strip()


def spec_from_words(words: str) -> dict | None:
    """His words read for the pattern ($0): the kind they name, its direction, density and tone; None where they name
    none of these."""
    text = " %s " % re.sub(r"[^\w\- ]", " ", str(words or "").lower())
    spec = {}
    for kind, names in PATTERN_WORDS:
        if any(" %s " % n in text for n in names):
            spec["pattern"] = kind
            break
    if re.search(r" (diagonal|diagonally|slanted|angled|bias) ", text):
        spec["direction"] = "diagonal"
    elif re.search(r" (vertical|vertically|upright) ", text):
        spec["direction"] = "vertical"
    elif re.search(r" (horizontal|horizontally|across) ", text):
        spec["direction"] = "horizontal"
    if re.search(r" (dense|tight|close|thin|small|fine|busy|tiny) ", text):
        spec["density"] = "dense"
    elif re.search(r" (sparse|airy|large|big|bold|wide|loose) ", text):
        spec["density"] = "sparse"
    if re.search(r" (dark|deep|rich|night) ", text):
        spec["tone"] = "dark"
    elif re.search(r" (light|pale|soft|white|cream|airy) ", text):
        spec["tone"] = "light"
    if " logo " in text or " logos " in text or " monogram " in text:
        spec["motif"] = "logo"
    return spec or None


def plan(mode: str, readings: list, words: str, map_front: dict | None) -> dict:
    """What the inside prints: ``{"mode", "pattern", "direction", "density", "tone", "motif", "source", "words",
    "dark", "light"}`` — in "referenced" mode his pictures' readings (the first leading) under his words, else the
    concept's own motif; "solid" the dark tone alone; "plain" nothing printed. The colours are the design's own."""
    from apps.ire.compose import _TINT, contrast_ink
    from apps.ire.graph import Color
    mode = mode if mode in MODES else DEFAULT_MODE
    ground = Color.from_hex((map_front or {}).get("ground") or _TINT)
    ink = contrast_ink(map_front or {}, ground)
    out = {"mode": mode, "dark": ink.to_hex(), "light": ground.to_hex(), "words": words or "",
           "pictures": len(readings)}
    if lum(ink) > lum(ground):
        out["dark"], out["light"] = ground.to_hex(), ink.to_hex()
    # [His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 10: "INSIDE: still round blobs on off-white. Follow the inside reference: five long, pointed petals per flower, soft painted feel, deep berry on a bright pink ground, varied sizes and turns."]
    # the inside his reference paints: its own two colours, measured from it (``reference_colours``) — its ink the
    # dark, its ground the light — where he gives one and it is followed
    measured = next((r["colours"] for r in readings if isinstance(r, dict) and isinstance(r.get("colours"), dict)),
                    None) if mode == "referenced" else None
    if measured is not None:
        pair = sorted((Color.from_hex(measured["ink"]), Color.from_hex(measured["ground"])), key=lum)
        out["dark"], out["light"] = pair[0].to_hex(), pair[1].to_hex()
        out["colours_from"] = "his inside reference's own colours, measured from it"
    if mode != "referenced":
        out["source"] = {"solid": "his choice: one solid colour", "plain": "his choice: plain"}[mode]
        return out
    spec = {"pattern": "", "direction": "none", "density": "medium", "tone": "dark", "motif": "concept"}
    sources = []
    shape_words = []
    for reading in readings:
        for k in ("pattern", "direction", "density", "tone"):
            v = str(reading.get(k) or "").strip().lower()
            if v and not (k == "pattern" and v not in PATTERNS):
                spec[k] = v
        shape_words.append(str(reading.get("motif_words") or ""))
        sources.append("his inside reference")
        break
    said = spec_from_words(words)
    if said:
        spec.update(said)
        sources.append("his brief's words")
    # [His review of 127, 130, 131 and 132, 2026-10-15, C (2): "never printed broken"] the concept's own motif where it
    # has one drawn whole (``compose._concept_motif``: never a shape its trace breaks; a motif redrawn flat, its clean
    # outlines) — 132's lily, redrawn, where its broken flower had been the inside's repeat
    from apps.ire.compose import _concept_motif
    has_shape = _concept_motif(map_front) is not None
    if not spec["pattern"]:
        spec["pattern"] = "motif" if has_shape else "waves"
        sources.append("the concept's own motif" if has_shape else "the concept's own colours")
    # [his test blocker on design 123, 2026-10-09, (3): "The carton's inside follows the inside reference (the berry
    # petal flowers)"] a repeat his reference or his words say is of flowers is drawn as our own petal flower — never the
    # concept's traced shape in their place, and never the reference's own
    petals = flower_petals(" ".join(shape_words + [words or ""])) if spec["pattern"] == "motif" else None
    if petals is not None and spec.get("motif") != "logo":
        spec.update(motif="flower", petals=petals)
        sources.append("drawn as our own %d-petal flower" % petals)
    if spec["pattern"] == "motif" and spec.get("motif") == "concept" and not has_shape:
        spec["motif"] = "logo"
    out.update(spec, source=" and ".join(sources))
    return out


#: [His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (3): "The
#: carton's inside follows the inside reference (the berry petal flowers), and its flaps/sides repeat 122's line art."]
#: His brief for 123: "Inside: bold berry petal flowers on pink, like the inside reference, redrawn in our own shapes."
#: The words — a reading's or his — that name a flower; the petals a word counts; a flower's petals where none is counted.
FLOWER_WORDS = re.compile(r"\b(flower|flowers|floral|florals|petal|petals|blossom|blossoms|bloom|blooms|daisy|"
                          r"daisies)\b", re.IGNORECASE)
PETAL_COUNTS = {"three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
FLOWER_PETALS = 5


def flower_petals(words: str) -> int | None:
    """The petals ``words`` name a flower with ("five-petal", "6 petals"), the house's ``FLOWER_PETALS`` where they name
    a flower and count none; None where they name no flower."""
    text = str(words or "")
    if not FLOWER_WORDS.search(text):
        return None
    m = re.search(r"\b(three|four|five|six|seven|eight|[3-8])[\s-]*(?:petal|petals|petalled)\b", text, re.IGNORECASE)
    if m:
        said = m.group(1).lower()
        return PETAL_COUNTS[said] if said in PETAL_COUNTS else int(said)
    return FLOWER_PETALS


def petal_flower(petals: int = FLOWER_PETALS) -> list:
    """[His test blocker on design 123, (3); his brief: "redrawn in our own shapes".] Our own petal flower — ``petals``
    round petals about a round heart, a ring of the ground between them — as rings in its unit box (the inside's repeat
    shape, ``pattern_segments``): drawn from the reference's words, never from its picture."""
    rings = []
    r0, r1 = 0.16, 0.5                          # each petal from the heart's ring to the box's edge
    half = min(0.2, math.sin(math.pi / petals) * r1 * 0.95)
    for i in range(petals):
        a = 2.0 * math.pi * i / petals - math.pi / 2.0
        ca, sa = math.cos(a), math.sin(a)

        def at(u, v):
            return [0.5 + u * ca - v * sa, 0.5 + u * sa + v * ca]
        base, tip = at(r0, 0.0), at(r1, 0.0)
        rings.append([base, at(r0 + 0.02, half * 1.15) + at(r1, half * 1.3) + tip,
                      at(r1, -half * 1.3) + at(r0 + 0.02, -half * 1.15) + base])
    k = 0.5523 * 0.1                            # the heart, a tenth of the box in radius: four quarter arcs
    rings.append([[0.6, 0.5], [0.6, 0.5 + k, 0.5 + k, 0.6, 0.5, 0.6], [0.5 - k, 0.6, 0.4, 0.5 + k, 0.4, 0.5],
                  [0.4, 0.5 - k, 0.5 - k, 0.4, 0.5, 0.4], [0.5 + k, 0.4, 0.6, 0.5 - k, 0.6, 0.5]])
    return rings


#: [His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (5).] our own
#: flowers strewn loose: each this share of the pattern's pitch apart before it is moved off its place by up to
#: SCATTER_JITTER of it, its size from SCATTER_SIZES (times the pitch), turned anywhere, each petal's length, width and
#: angle varied by PETAL_VARY; drawn in three layers at these strengths, so they overlap as painted petals do
SCATTER_PITCH = 1.15
SCATTER_JITTER = 0.45
SCATTER_SIZES = (0.9, 2.1)
PETAL_VARY = 0.18
#: [His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 10: "INSIDE: still round blobs on off-white. Follow the inside reference: five long, pointed petals per flower, soft painted feel, deep berry on a bright pink ground, varied sizes and turns."]
#: the reference's flowers are bold — the pitch at least this share of the inside's shorter side; each flower's petals
#: in one of these strengths of the ink, its heart pooled darker as paint pools (the petals again, CORE_SCALE of their
#: reach, at CORE_STRENGTH over them); a petal LONG — its widest half-width PETAL_HALF of the flower, widest
#: PETAL_WIDEST along it — and POINTED, from a narrow base to its tip
SCATTER_BOLD_SHARE = 0.16
SCATTER_LAYERS = (0.82, 0.92, 1.0)
CORE_SCALE = 0.5
CORE_STRENGTH = 0.4
PETAL_HALF = 0.1
PETAL_WIDEST = 0.62
#: a colour his reference paints at least this share of itself in may be its ink
REFERENCE_INK_SHARE = 0.08


def reference_colours(data: bytes) -> dict | None:
    """[His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 10: "INSIDE: still round blobs on off-white. Follow the inside reference: five long, pointed petals per flower, soft painted feel, deep berry on a bright pink ground, varied sizes and turns."]
    His inside reference's own two colours, measured from its pixels at $0: ``{"ground": the colour it paints most of,
    "ink": of the colours it paints at least REFERENCE_INK_SHARE of itself in, the one standing furthest from that
    ground, "shares": their shares}`` — None for a picture that will not open or shows one colour."""
    import io
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as im:
            img = im.convert("RGB")
            img.thumbnail((200, 200))
            q = img.quantize(colors=6)
            palette = q.getpalette()
            counts = sorted(q.getcolors(), reverse=True)
    except Exception:  # noqa: BLE001 — a picture that will not open gives no colours, said by None
        return None
    if len(counts) < 2:
        return None
    total = float(sum(n for n, _i in counts))
    found = [(n / total, tuple(palette[3 * i:3 * i + 3])) for n, i in counts]

    def lum(rgb):
        return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    # its ground the largest colour; its ink, of the colours it paints a real share in, the one standing furthest from
    # the ground — so two shades of its pink are never taken for ground and ink
    ground = found[0]
    painted = [c for c in found[1:] if c[0] >= REFERENCE_INK_SHARE]
    if not painted:
        return None
    ink = max(painted, key=lambda c: abs(lum(c[1]) - lum(ground[1])))
    if abs(lum(ground[1]) - lum(ink[1])) < 24:
        return None
    hexed = ["#%02X%02X%02X" % c[1] for c in (ground, ink)]
    return {"ground": hexed[0], "ink": hexed[1], "shares": [round(ground[0], 3), round(ink[0], 3)]}


def strewn_flowers(box: tuple, spec: dict, petals: int = FLOWER_PETALS) -> list:
    """[His test findings on design 123, 2026-10-09 (transcribed at cbdf721), (5): "Inside: follow the inside
    reference's character: loose, overlapping, painterly petals in deep berry on pink, varied sizes and rotations; never
    a rigid grid of identical stamps."]
    Our own petal flowers strewn over ``box`` (x0, y0, x1, y1 mm) — never a grid: each moved off its place, at its own
    size and turn, its petals each a little different, the flowers overlapping — as ``[(its layer's strength, its
    segments)]``, one compound path a layer; the same strew wherever the same inside is drawn again."""
    import hashlib
    import random
    x0, y0, x1, y1 = box
    pitch = PITCH_MM.get(spec.get("density"), PITCH_MM["medium"]) * 1.4 * SCATTER_PITCH
    # [his goal of 2026-10-10, item 10] the reference's flowers are bold: never smaller than a share of the inside
    pitch = max(pitch, SCATTER_BOLD_SHARE * min(x1 - x0, y1 - y0))
    seed = hashlib.sha256(("%s|%s|%s|%.1f|%.1f" % (spec.get("motif_words"), spec.get("density"), petals,
                                                    x1 - x0, y1 - y0)).encode()).hexdigest()
    rnd = random.Random(int(seed[:16], 16))
    layers = [[] for _ in SCATTER_LAYERS]
    cores = []
    rows, cols = int((y1 - y0) / pitch) + 3, int((x1 - x0) / pitch) + 3
    for j in range(rows):
        for i in range(cols):
            cx = x0 + (i - 1 + (0.5 if j % 2 else 0.0)) * pitch + rnd.uniform(-1.0, 1.0) * SCATTER_JITTER * pitch
            cy = y0 + (j - 1) * pitch * 0.9 + rnd.uniform(-1.0, 1.0) * SCATTER_JITTER * pitch
            size = pitch * rnd.uniform(*SCATTER_SIZES) / 1.4
            turn = rnd.uniform(0.0, 360.0)
            rings = loose_flower(petals, rnd)
            layers[rnd.randrange(len(SCATTER_LAYERS))] += _motif_segments(
                [[_turned(pt, turn) for pt in ring] for ring in rings], cx - size / 2.0, cy - size / 2.0, size)
            # [his goal of 2026-10-10, item 10: "soft painted feel"] its heart pooled darker, as paint pools
            core = size * CORE_SCALE
            cores += _motif_segments([[_turned(pt, turn) for pt in ring] for ring in rings], cx - core / 2.0,
                                     cy - core / 2.0, core)
    out = [(strength, segs) for strength, segs in zip(SCATTER_LAYERS, layers) if segs]
    return out + ([(CORE_STRENGTH, cores)] if cores else [])


def _turned(pt: list, deg: float) -> list:
    """A unit-box point (or a cubic's three) turned ``deg`` about the box's centre."""
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for k in range(0, len(pt), 2):
        x, y = pt[k] - 0.5, pt[k + 1] - 0.5
        out += [0.5 + x * ca - y * sa, 0.5 + x * sa + y * ca]
    return out


def loose_flower(petals: int, rnd) -> list:
    """One of our petal flowers drawn loose: each petal's reach, width and angle varied by up to PETAL_VARY, so no two
    flowers are stamped alike.
    [His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 10: "INSIDE: still round blobs on off-white. Follow the inside reference: five long, pointed petals per flower, soft painted feel, deep berry on a bright pink ground, varied sizes and turns."]
    Each petal LONG and POINTED, as his reference paints them: from a narrow base at the heart, widening to its widest
    PETAL_WIDEST of the way out (PETAL_HALF of the flower each side), then narrowing to its tip — no round heart drawn:
    the petals meet there, and the heart is pooled darker (``strewn_flowers``)."""
    rings = []
    r0 = 0.02
    for i in range(petals):
        a = 2.0 * math.pi * (i + rnd.uniform(-PETAL_VARY, PETAL_VARY) * 0.5) / petals - math.pi / 2.0
        r1 = 0.5 * (1.0 - rnd.uniform(0.0, PETAL_VARY))
        half = PETAL_HALF * (1.0 + rnd.uniform(-PETAL_VARY, PETAL_VARY))
        ca, sa = math.cos(a), math.sin(a)

        def at(u, v):
            return [0.5 + u * ca - v * sa, 0.5 + u * sa + v * ca]
        base, tip = at(r0, 0.0), at(r1, 0.0)
        widest = r0 + PETAL_WIDEST * (r1 - r0)
        rings.append([base, at(widest * 0.55, half * 1.05) + at(widest + 0.45 * (r1 - widest), half * 1.25) + tip,
                      at(widest + 0.45 * (r1 - widest), -half * 1.25) + at(widest * 0.55, -half * 1.05) + base])
    return rings


def lum(c) -> float:
    return 0.299 * c.r + 0.587 * c.g + 0.114 * c.b


# ---------------------------------------------------------------------------------------------------------- geometry

def _rotate(pts, angle_deg, cx, cy):
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca) for x, y in pts]


def _poly_segments(pts):
    from apps.ire.graph import ClosePath, LineTo, MoveTo
    segs = [MoveTo(x=pts[0][0], y=pts[0][1])]
    segs += [LineTo(x=x, y=y) for x, y in pts[1:]]
    segs.append(ClosePath())
    return segs


def _circle_segments(cx, cy, r):
    from apps.ire.graph import ClosePath, CubicTo, MoveTo
    k = 0.5523 * r
    return [MoveTo(x=cx + r, y=cy),
            CubicTo(x1=cx + r, y1=cy + k, x2=cx + k, y2=cy + r, x=cx, y=cy + r),
            CubicTo(x1=cx - k, y1=cy + r, x2=cx - r, y2=cy + k, x=cx - r, y=cy),
            CubicTo(x1=cx - r, y1=cy - k, x2=cx - k, y2=cy - r, x=cx, y=cy - r),
            CubicTo(x1=cx + k, y1=cy - r, x2=cx + r, y2=cy - k, x=cx + r, y=cy),
            ClosePath()]


def pattern_segments(spec: dict, box: tuple, motif=None) -> list:
    """The pattern over ``box`` (x0, y0, x1, y1 mm) as one compound path's segments: each repeat a closed subpath.
    ``motif``: the repeated shape's rings, ``[[[x, y], [c1x, c1y, c2x, c2y, x, y], …], …]`` in its own unit box."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    half = math.hypot(x1 - x0, y1 - y0) / 2.0 + 2.0
    p = PITCH_MM.get(spec.get("density"), PITCH_MM["medium"])
    kind = spec.get("pattern")
    angle = {"diagonal": 45.0, "vertical": 90.0}.get(spec.get("direction"), 0.0)
    segs = []
    if kind in ("stripes", "grid"):
        width = p / 2.0 if kind == "stripes" else 0.35
        n = int(half * 2 / p) + 2
        for i in range(n):
            t = -half + i * p
            bands = [(t, t + width)]
            for a0, a1 in bands:
                pts = [(cx - half, cy + a0), (cx + half, cy + a0), (cx + half, cy + a1), (cx - half, cy + a1)]
                segs += _poly_segments(_rotate(pts, angle, cx, cy))
                if kind == "grid":
                    segs += _poly_segments(_rotate(pts, angle + 90.0, cx, cy))
    elif kind == "dots":
        r = p * 0.2
        rows = int(half * 2 / p) + 2
        for j in range(rows):
            for i in range(rows):
                lx = -half + i * p + (p / 2.0 if j % 2 else 0.0)
                ly = -half + j * p
                (px, py), = _rotate([(cx + lx, cy + ly)], angle, cx, cy)
                if x0 - r <= px <= x1 + r and y0 - r <= py <= y1 + r:
                    segs += _circle_segments(px, py, r)
    elif kind == "waves":
        amp, wl, thick = p * 0.35, p * 3.0, p * 0.42
        n = int(half * 2 / p) + 2
        steps = int(half * 2 / 0.6) + 1
        for i in range(n):
            base = -half + i * p
            top = [(-half + k * 0.6, base + amp * math.sin(2 * math.pi * (-half + k * 0.6) / wl)) for k in range(steps)]
            bottom = [(x, y + thick) for x, y in reversed(top)]
            pts = [(cx + x, cy + y) for x, y in top + bottom]
            segs += _poly_segments(_rotate(pts, angle, cx, cy))
    elif kind == "checks":
        s = p / 2.0
        n = int(half * 2 / s) + 2
        for j in range(n):
            for i in range(n):
                if (i + j) % 2:
                    continue
                lx, ly = -half + i * s, -half + j * s
                pts = [(cx + lx, cy + ly), (cx + lx + s, cy + ly), (cx + lx + s, cy + ly + s), (cx + lx, cy + ly + s)]
                segs += _poly_segments(_rotate(pts, angle, cx, cy))
    elif kind == "chevrons":
        thick = p * 0.35
        n = int(half * 2 / p) + 2
        zig = int(half * 2 / p) + 2
        for i in range(n):
            base = -half + i * p
            top = [(-half + k * p, base + (p * 0.4 if k % 2 else 0.0)) for k in range(zig + 1)]
            pts = [(cx + x, cy + y) for x, y in top + [(x, y + thick) for x, y in reversed(top)]]
            segs += _poly_segments(_rotate(pts, angle, cx, cy))
    elif kind == "motif" and motif:
        size = p * 1.4
        motif = drawn_at(motif, size)       # [his goal after the pitch page, B (10)] drawn for the size it prints at
        pitch = size * 1.5
        rows = int(half * 2 / pitch) + 2
        for j in range(rows):
            for i in range(rows):
                lx = -half + i * pitch + (pitch / 2.0 if j % 2 else 0.0)
                ly = -half + j * pitch
                (px, py), = _rotate([(cx + lx, cy + ly)], angle, cx, cy)
                if not (x0 - size <= px <= x1 + size and y0 - size <= py <= y1 + size):
                    continue
                segs += _motif_segments(motif, px - size / 2.0, py - size / 2.0, size)
    return segs


def unit_motif(cubics, aspect: float = 1.0) -> list:
    """A traced shape's rings (``[[[x, y], [c1x, c1y, c2x, c2y, x, y], …], …]`` per polygon, in the product's
    fractions) in its own unit box, its aspect kept — ``aspect`` the product's height over its width, so a fraction of
    the height and one of the width are the lengths they are."""
    rings = [[[v * aspect if k % 2 else v for k, v in enumerate(pt)] for pt in ring] for poly in cubics for ring in poly]
    xs = [v for ring in rings for pt in ring for v in pt[0::2]]
    ys = [v for ring in rings for pt in ring for v in pt[1::2]]
    if not xs:
        return []
    bx0, by0 = min(xs), min(ys)
    span = max(max(xs) - bx0, max(ys) - by0) or 1.0
    ox, oy = (1.0 - (max(xs) - bx0) / span) / 2.0, (1.0 - (max(ys) - by0) / span) / 2.0
    out = []
    for ring in rings:
        out.append([[(v - bx0) / span + ox if k % 2 == 0 else (v - by0) / span + oy for k, v in enumerate(pt)]
                    for pt in ring])
    return out


#: [His goal after the pitch page, B (10): 140's carton .ai was 116 MB — an earlier one 20 to 35.] A motif repeated is
#: drawn for the size it prints at: its traced redraw (potrace at three times the redraw's size: 140's dipper, 2,627
#: rings and 34,375 cubics, printed some hundred times about 8 mm tall on the inside) keeps every ring no smaller than
#: the self-check's own speck (``self_check.SPECK_MM2``) at that size, each run along within MOTIF_TOLERANCE_MM of its
#: curve (each cubic followed in steps no longer than MOTIF_STEP_MM) — a ring already drawn in fewer steps kept as it is
MOTIF_TOLERANCE_MM = 0.02
MOTIF_STEP_MM = 0.25


def drawn_at(motif, size_mm: float) -> list:
    """``motif`` (``unit_motif``'s rings) as it is drawn ``size_mm`` across: its specks left out, each ring followed
    within MOTIF_TOLERANCE_MM — the look kept at that size, the cubics a printer's file need not carry dropped."""
    import math as _m

    from shapely.geometry import LineString

    from apps.ire.self_check import SPECK_MM2
    size = float(size_mm)
    if size <= 0:
        return list(motif)
    out = []
    for ring in motif:
        xs = [ring[0][0]] + [c[4] for c in ring[1:]] + [v for c in ring[1:] for v in c[0:4:2]]
        ys = [ring[0][1]] + [c[5] for c in ring[1:]] + [v for c in ring[1:] for v in c[1:4:2]]
        if (max(xs) - min(xs)) * (max(ys) - min(ys)) * size * size < SPECK_MM2:
            continue
        pts, at = [(ring[0][0], ring[0][1])], (ring[0][0], ring[0][1])
        for c in ring[1:]:
            reach = (_m.hypot(c[0] - at[0], c[1] - at[1]) + _m.hypot(c[2] - c[0], c[3] - c[1])
                     + _m.hypot(c[4] - c[2], c[5] - c[3])) * size
            n = max(1, min(16, int(_m.ceil(reach / MOTIF_STEP_MM))))
            for k in range(1, n + 1):
                t = k / float(n)
                u = 1.0 - t
                pts.append((u ** 3 * at[0] + 3 * u * u * t * c[0] + 3 * u * t * t * c[2] + t ** 3 * c[4],
                            u ** 3 * at[1] + 3 * u * u * t * c[1] + 3 * u * t * t * c[3] + t ** 3 * c[5]))
            at = (c[4], c[5])
        if len(pts) < 4:
            out.append(ring)
            continue
        run = list(LineString(pts + [pts[0]]).simplify(MOTIF_TOLERANCE_MM / size, preserve_topology=False).coords)
        run = run[:-1] if len(run) > 1 and run[0] == run[-1] else run
        if len(run) < 3 or len(run) >= len(ring) - 1:
            out.append(ring)                       # drawn as few steps as it is, or too few to stand: kept as it is
            continue
        out.append([[run[0][0], run[0][1]]] + [[a[0], a[1], b[0], b[1], b[0], b[1]]
                                               for a, b in zip(run, run[1:] + run[:1])])
    return out


def _motif_segments(motif, x, y, size):
    from apps.ire.graph import ClosePath, CubicTo, MoveTo
    segs = []
    for ring in motif:
        sx, sy = ring[0][0], ring[0][1]
        segs.append(MoveTo(x=x + sx * size, y=y + sy * size))
        for c in ring[1:]:
            segs.append(CubicTo(x1=x + c[0] * size, y1=y + c[1] * size, x2=x + c[2] * size, y2=y + c[3] * size,
                                x=x + c[4] * size, y=y + c[5] * size))
        segs.append(ClosePath())
    return segs


def mirrored(segs: list, axis_x: float) -> list:
    """``segs`` mirrored about the vertical line x = ``axis_x`` (the sheet seen from its inside)."""
    out = []
    for s in segs:
        d = s.model_dump()
        for k in ("x", "x1", "x2"):
            if k in d:
                d[k] = 2 * axis_x - d[k]
        out.append(type(s)(**d))
    return out


# ------------------------------------------------------------------------------------------------- the inside sheet

def _clip_of(coords, gx, gy, axis):
    """The bleed outline, mirrored, with the strip the glue tab is glued onto cut out of it (even-odd): no ink where
    the glue holds."""
    from apps.ire.graph import ClosePath, LineTo, MoveTo
    pts = [(2 * axis - gx(x), gy(y)) for x, y in coords.bleed_polygon.exterior.coords]
    segs = [MoveTo(x=pts[0][0], y=pts[0][1])] + [LineTo(x=x, y=y) for x, y in pts[1:]] + [ClosePath()]
    strip = glue_strip(coords)
    if strip is not None:
        x0, y0, x1, y1 = strip
        segs += _poly_segments([(2 * axis - gx(x0), gy(y0)), (2 * axis - gx(x1), gy(y0)), (2 * axis - gx(x1), gy(y1)),
                                (2 * axis - gx(x0), gy(y1))])
    return segs


def glue_strip(coords):
    """The strip of the inside the glue tab is glued onto — on the panel at the far end of the body from the tab, as
    wide as the tab — ``(x0, y0, x1, y1)`` in the die's millimetres, or None where the die has no glue tab."""
    tab = getattr(coords, "glue_tab_polygon", None)
    body = next((poly for name, poly in getattr(coords, "components", []) or [] if name == "main-body"), None)
    if tab is None or body is None:
        return None
    tx0, _ty0, tx1, _ty1 = tab.bounds
    bx0, by0, bx1, by1 = body.bounds
    width = tx1 - tx0
    if tx1 <= bx0 + 1e-6:                       # the tab on the body's left: glued onto its right end, inside
        return (bx1 - width, by0, bx1, by1)
    return (bx0, by0, bx0 + width, by1)


def inside_group(coords, gx, gy, spec: dict, *, motif_cubics=None, motif_aspect: float = 1.0, structure=None):
    """[His final goal, B1: "Two artboards, OUTSIDE and INSIDE."] The INSIDE artboard's artwork: the sheet seen from its
    inside — mirrored about the flat's centre — its ground in the dark tone (the light one where the pattern is dark on
    light), the pattern over it as ONE compound path in the other tone, clipped to the bleed outline with the glue strip
    left unprinted; "solid" the ground alone, "plain" nothing printed; the die's lines (``structure``, the outside's
    own) mirrored over it for the printer. [His second goal of 2026-10-06, item 1: "Never printed inside the box"] the
    label is never printed here (the offer that put it here, his final goal's C5, is gone)."""
    from apps.ire.graph import Color, Group, Path, SolidFill
    bx0, by0, bx1, by1 = coords.bleed_polygon.bounds
    axis = (gx(bx0) + gx(bx1)) / 2.0
    box = (gx(bx0), gy(by0), gx(bx1), gy(by1))
    printed = []
    if spec.get("mode") != "plain":
        dark, light = Color.from_hex(spec["dark"]), Color.from_hex(spec["light"])
        ground, ink = (light, dark) if spec.get("tone") == "light" else (dark, light)
        if spec.get("mode") == "solid":
            ground = dark
        printed.append(Path(name="inside-ground", fill=SolidFill(color=ground), segments=_poly_segments(
            [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])])))
        if spec.get("mode") == "referenced":
            motif = unit_motif(motif_cubics, motif_aspect) if spec.get("pattern") == "motif" and motif_cubics else None
            if spec.get("pattern") == "motif" and spec.get("motif") == "flower":
                # [his test findings on design 123, 2026-10-09, (5): "loose, overlapping, painterly petals ... varied
                # sizes and rotations; never a rigid grid of identical stamps"] our own flowers strewn, in layers
                for n, (strength, segs) in enumerate(strewn_flowers(box, spec, int(spec["petals"]))):
                    printed.append(Path(name="inside-pattern" if n == 0 else "inside-pattern-%d" % n,
                                        fill=SolidFill(color=ink, opacity=strength), fill_rule="nonzero",
                                        segments=mirrored(segs, axis)))
                motif = None
            drawn = dict(spec, pattern="dots") if spec.get("pattern") == "motif" and not motif else spec
            segs = [] if spec.get("motif") == "flower" and spec.get("pattern") == "motif" else pattern_segments(
                drawn, box, motif)
            if segs:
                printed.append(Path(name="inside-pattern", fill=SolidFill(color=ink), fill_rule="nonzero",
                                    segments=mirrored(segs, axis)))
    children = []
    if printed:
        children.append(Group(name="Inside print", role="background", clip=_clip_of(coords, gx, gy, axis),
                              children=printed))
    cut, crease = [], []
    for node in structure or []:
        turned = node.model_copy(update={"segments": mirrored(node.segments, axis)})
        (crease if str(node.name).startswith("fold") else cut).append(turned)
    # [his final goal, B2] the inside's die on the same named layers as the outside's
    if cut:
        children.append(Group(name="CUT", role="structure", children=cut))
    if crease:
        children.append(Group(name="CREASE", role="structure", children=crease))
    return Group(name="INSIDE", role="artwork", children=children)


def flap_nodes(coords, gx, gy, spec: dict, *, ground_hex: str, logo_master=None, motif_cubics=None,
               motif_aspect: float = 1.0, safe_mm: float = 4.0, motif_ink: str | None = None,
               motif_cap_mm: float | None = None) -> list:
    """[His final goal, B1: "The flaps carry design (logo or pattern)."] On the outside: the lid — the top tuck flap's
    panel — carries the house mark, turned 180° so it reads from the front when the carton is closed (where an approved
    vector master is on file). [His goal of 2026-10-06, item 10 (transcribed at a9ac953): "Flaps use the concept's own
    motif or the logo, never an invented pattern: 119's outside flaps have polka dots that are in neither the concept nor
    my brief."] The dust flaps and the bottom tuck carry the concept's own motif — the shape its front's map traced, the
    one the inside repeats — in the dark tone on the carton's ground; where the concept gives no motif, the house mark (a
    top flap's turned as the lid's is); where neither, nothing. They fell back to dots wherever the inside's pattern was
    the motif or a solid — a pattern the design never had. [Executor, the same goal, read on 119's drawn flaps: the motif
    laid as a repeat and clipped to each flap cut its vials in half at the die's edge and across the tuck's fold — his
    "whole drips" of 2026-10-03 says a shape of the design is never cut.] Each flap's motif or mark now stands ONCE and
    WHOLE inside ``flap_area`` — the flap inside the carton's safe margin, a tuck on its own panel — as large as it fits up
    to the inside's own repeat size; a flap where it would stand under ``FLAP_MOTIF_MIN_MM`` carries nothing.
    [His test blocker on design 123, 2026-10-09, (3): "its flaps/sides repeat 122's line art".] ``motif_ink`` — a carton
    continuing its approved container carries the container's rose (``compose._concept_motif``) in the container's own
    ink, up to ``motif_cap_mm`` — its own size — where the flap holds it, so its hairlines still print."""
    from apps.ire.graph import Color, Group, Path, SolidFill
    nodes = []
    comps = dict((name, poly) for name, poly in getattr(coords, "components", []) or [])
    made = getattr(getattr(coords, "dimensions", None), "manufacture", None)
    depth = float(made[1]) if made else 0.0               # (width, depth, height): the lid is as deep as the carton
    body_top = getattr(coords, "body_top_y", None)
    # the design's tone that stands out from the carton's ground — its dark on a light ground, its light on a dark one
    tones = [Color.from_hex(spec[k]) for k in ("dark", "light") if spec.get(k)]
    ground = Color.from_hex(ground_hex)

    def _lum(c):
        return 0.299 * c.r + 0.587 * c.g + 0.114 * c.b
    ink = max(tones, key=lambda c: abs(_lum(c) - _lum(ground))) if tones else None
    if motif_ink:
        ink = Color.from_hex(motif_ink)                  # [his test blocker on design 123, (3)] the container's own
    motif = unit_motif(motif_cubics, motif_aspect) if motif_cubics else None
    if motif:
        xs = [v for ring in motif for pt in ring for v in pt[0::2]]
        ys = [v for ring in motif for pt in ring for v in pt[1::2]]
        mx0, my0, mw, mh = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    for name, poly in comps.items():
        if name == "main-body" or name == "glue-tab":
            continue
        x0, y0, x1, y1 = poly.bounds
        lid = name.startswith("top") and "tuck" in name and logo_master is not None and depth and body_top is not None
        if lid:
            ly0, ly1 = lid_span(coords, name) or (float(body_top) - depth, float(body_top))
            nodes.append(_mark_on(logo_master, "lid-mark", x0, x1, ly0, ly1, gx, gy, LID_MARK_SHARE, turned=True))
            continue
        if spec.get("mode") == "plain":
            continue
        area = flap_area(name, poly, coords, safe_mm)
        if motif and ink is not None:
            cap = motif_cap_mm or PITCH_MM["sparse"] * 1.4    # the inside's own repeat size (``pattern_segments``)
            fit = fit_in(area, mw, mh, cap)
            if fit is None:
                continue
            cx, cy, size = fit
            # [his goal after the pitch page, B (10)] drawn for the size it prints at on this flap
            segs = _motif_segments(drawn_at(motif, size), gx(cx) - (mx0 + mw / 2.0) * size,
                                   gy(cy) - (my0 + mh / 2.0) * size, size)
            clip = _poly_segments([(gx(x), gy(y)) for x, y in list(poly.exterior.coords)[:-1]])
            nodes.append(Group(name="flap-%s" % name, role="decoration", clip=clip, children=[
                Path(name="flap-%s-motif" % name, segments=segs, fill=SolidFill(color=ink), fill_rule="nonzero",
                     opacity=0.85)]))
        elif logo_master is not None:
            fit = fit_in(area, 1.0, logo_master.aspect, (x1 - x0) * FLAP_MARK_SHARE)
            if fit is None:
                continue
            cx, cy, w = fit
            h = w * logo_master.aspect
            nodes.append(_mark_on(logo_master, "flap-%s-mark" % name, cx - w / 2.0, cx + w / 2.0, cy - h / 2.0,
                                  cy + h / 2.0, gx, gy, 1.0, turned=name.startswith("top"), hold=1.0))
    return nodes


#: a flap's motif or mark never stands smaller than this (mm, its longer side): a flap too small for it carries nothing
FLAP_MOTIF_MIN_MM = 3.0
#: the step (mm) the placement of a flap's motif is searched at
FLAP_FIT_STEP_MM = 0.5


def flap_area(name: str, poly, coords, safe_mm: float):
    """Where a flap's motif may stand: the flap inside the carton's safe margin — a tuck flap on its own panel only (the
    lid's face or the bottom's, as deep as the carton), never across its fold onto its tongue. A shapely polygon, or
    None where nothing is left."""
    from shapely.geometry import box as _box
    made = getattr(getattr(coords, "dimensions", None), "manufacture", None)
    depth = float(made[1]) if made else 0.0
    x0, _y0, x1, _y1 = poly.bounds
    area = poly
    span = lid_span(coords, name) if "tuck" in name else None
    if span is not None:
        area = poly.intersection(_box(x0, span[0], x1, span[1]))
    elif "tuck" in name and depth:
        top, bottom = getattr(coords, "body_top_y", None), getattr(coords, "body_bottom_y", None)
        if name.startswith("top") and top is not None:
            area = poly.intersection(_box(x0, float(top) - depth, x1, float(top)))
        elif name.startswith("bottom") and bottom is not None:
            area = poly.intersection(_box(x0, float(bottom), x1, float(bottom) + depth))
    area = area.buffer(-safe_mm, join_style=2)
    return None if area.is_empty else area


def lid_span(coords, name: str):
    """``(y0, y1)`` of a tuck's lid — between its hinge and its tuck fold — where the die records them (1.4, whose lid
    hinges one caliper outside the body: apps/dielines/geometry/trade_tuck.py), else None."""
    end = "top" if name.startswith("top") else "bottom"
    panel = name.split("-")[1] if name.count("-") >= 2 else None
    for tuck in (getattr(coords, "derived", None) or {}).get("tucks") or []:
        if tuck.get("end") == end and tuck.get("panel") == panel:
            return tuple(sorted((float(tuck["hinge_y"]), float(tuck["fold_y"]))))
    return None


def fit_in(area, w: float, h: float, cap: float):
    """``(cx, cy, size)``: the largest a box of ``w`` × ``h`` (in units of ``size``) stands whole inside ``area``, up to
    ``size == cap`` — of the centres that hold the largest, the one nearest the area's middle; None where it would stand
    under ``FLAP_MOTIF_MIN_MM`` on its longer side."""
    from shapely.geometry import box as _box
    from shapely.prepared import prep
    if area is None or w <= 0 or h <= 0:
        return None
    held = prep(area)
    ax0, ay0, ax1, ay1 = area.bounds
    mid = area.centroid
    best = None
    ny = int((ay1 - ay0) / FLAP_FIT_STEP_MM) + 1
    nx = int((ax1 - ax0) / FLAP_FIT_STEP_MM) + 1
    for j in range(ny):
        for i in range(nx):
            cx, cy = ax0 + i * FLAP_FIT_STEP_MM, ay0 + j * FLAP_FIT_STEP_MM
            lo, hi = 0.0, cap
            if held.contains(_box(cx - w * hi / 2, cy - h * hi / 2, cx + w * hi / 2, cy + h * hi / 2)):
                lo = hi
            else:
                for _ in range(14):
                    m = (lo + hi) / 2.0
                    if held.contains(_box(cx - w * m / 2, cy - h * m / 2, cx + w * m / 2, cy + h * m / 2)):
                        lo = m
                    else:
                        hi = m
            key = (round(lo, 2), -((cx - mid.x) ** 2 + (cy - mid.y) ** 2))
            if best is None or key > best[0]:
                best = (key, cx, cy, lo)
    if best is None or best[3] * max(w, h) < FLAP_MOTIF_MIN_MM:
        return None
    return best[1], best[2], best[3]


#: the house mark on a flap with no motif of the concept's: this share of the flap's width (held inside half its height)
FLAP_MARK_SHARE = 0.45


def _mark_on(logo_master, name, x0, x1, y0, y1, gx, gy, share, turned=False, hold=0.5):
    """The house mark centred on the box (x0..x1, y0..y1 mm): ``share`` of its width, held inside ``hold`` of its
    height — ``turned`` 180° about its centre so a flap that folds over reads from the front, as the lid's."""
    from apps.ire import brand_mark
    from apps.ire.graph import Color, Path, SolidFill
    w = (x1 - x0) * share
    h = w * logo_master.aspect
    if h > (y1 - y0) * hold:
        h = (y1 - y0) * hold
        w = h / logo_master.aspect
    cx, cy = gx((x0 + x1) / 2.0), gy((y0 + y1) / 2.0)
    segs = brand_mark.placed_segments(logo_master, cx - w / 2.0, cy - h / 2.0, w, h)
    if turned:
        out = []
        for s in segs:
            d = s.model_dump()
            for kx, ky in (("x", "y"), ("x1", "y1"), ("x2", "y2")):
                if kx in d:
                    d[kx], d[ky] = 2 * cx - d[kx], 2 * cy - d[ky]
            out.append(type(s)(**d))
        segs = out
    return Path(name=name, segments=segs, fill=SolidFill(color=Color.from_hex(logo_master.fill)), fill_rule="nonzero")
