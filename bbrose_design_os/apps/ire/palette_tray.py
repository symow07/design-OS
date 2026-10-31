"""[His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 2: "The title says "— compact lid". A palette design must
include the whole palette: the lid AND the open tray with its 18 pans in 3 rows of 6, each shade name from my brief
printed under its pan. Tell me if today it only designs the lid, and build the tray if so."]

Until this goal a compact was drawn closed: its lid in plan and its base, the pan field "deliberately absent" as geometry
inside the case, never printed (§BH55(a), the executor's reading, LIVE — superseded for the tray by these words of his).
This module is the open tray:

- WHAT IT HOLDS (``read_tray``, $0): read from his brief's own words — "18 square pans in 3 rows of 6", the "Shade names"
  rows ("Row 1: Petal Frost, Moonlit Rose, …"), else a count of pans, else the product record's shades — the grid, the
  pans' shape and each pan's name, row by row, left to right. A brief that names no pans draws no tray, and says so.
- WHAT IS DRAWN (``compose_open_tray``): the tray's printed insert at the size it prints — the case's inside, inset by its
  wall — in the design's own colours: its ground, a frame round the pans in a gradient through the design's colours
  (the "glowing edge" his brief asks for, in its own colours), each pan a well cut through the insert (its keyline on
  its own layer, the pan itself shown and never printed), and each shade's name in clean capitals under its pan, all at
  one size the longest name fits.
"""
from __future__ import annotations

import math
import re

from apps.ire.container_text_floor import FALLBACK_FLOOR_PT

#: the brief's grid: "18 square pans in 3 rows of 6"
GRID_RE = re.compile(r"(\d+)\s+(?:(square|round|rectangular|oval)\s+)?(?:pans?|wells?)\s+in\s+(\d+)\s+rows?\s+of\s+"
                     r"(\d+)", re.I)
#: … else its count: "18 square pans", "Capacity: 18 pans"
COUNT_RE = re.compile(r"(\d+)\s+(?:(square|round|rectangular|oval)\s+)?(?:pans?|wells?)\b", re.I)
#: the line that opens his shade names, and each row under it
SHADES_RE = re.compile(r"^\s*shade\s+names?\b[^:\n]*:\s*(.*)$", re.I)
ROW_RE = re.compile(r"^\s*row\s*(\d+)\s*:\s*(.*)$", re.I)
#: a line another field's label opens — where his shade names end
FIELD_RE = re.compile(r"^\s*[A-Za-z][A-Za-z ]{0,30}:")
#: the case's wall, round its inside (mm) — the insert is the inside of the case
WALL_MM = 3.0
#: the pans' margin inside the frame, the gap between pans, and the frame's width — shares of a pan's side
MARGIN_SHARE = 0.22
GAP_SHARE = 0.14
FRAME_SHARE = 0.06
#: … and the insert's own ground kept round the frame
INSET_SHARE = 0.18
#: a name's size: as large as the longest name fits under its pan, never past NAME_MAX_PT — and never under the print
#: floor that judges it (``container_text_floor``: no print method is recorded for the tray's insert, so its disclosed
#: fallback): a name too long for its pan at that floor breaks at its space onto two lines under it, NAME_LEADING apart
NAME_MAX_PT = 7.0
NAME_MIN_PT = FALLBACK_FLOOR_PT
NAME_LEADING = 1.15
NAME_FILL = 0.92
NAME_TRACKING_EM = 0.06
#: the band under each pan its name stands in, in ems of the name's size
NAME_BAND_EM = 1.9
#: how a pan is shown on the sheet — a pan of pressed colour, never printed
PAN_SHOWN = "#D8D2CF"
PAN_KEYLINE = "#8A8480"
#: [his goal of 2026-10-12, (11): "Pan rims follow the tray picture (soft gold), not grey"; (12): "the holographic
#: edge around the pans, as the tray picture shows"] where the tray picture was read: each pan framed by its RIM,
#: RIM_SHARE of its side wide inside its edge, in the picture's rim ink (its cut line in it too, never grey); round it
#: the picture's GLOW, GLOW_STEPS rings out to GLOW_REACH of its side, fading from GLOW_ALPHA
RIM_SHARE = 0.045
GLOW_REACH = 0.07
GLOW_STEPS = 6
GLOW_ALPHA = 0.55
#: [his goal of 2026-10-12, (13): "Pan names readable (check the size against the print floor)"] the names set in the
#: picture's ink where it stands at least NAME_CONTRAST_DE (CIE76) from the tray's ground, else in the design's ink
NAME_CONTRAST_DE = 35.0


def _names(text: str) -> list:
    """His shade names, row by row: ``[[name, …], …]`` — each "Row N:" line and the lines that run on from it, to a
    blank line or another field's label; one row where he lists them on the heading's own line. [] where he names none."""
    rows, on, current = [], False, None
    for line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        head = SHADES_RE.match(line)
        if head:
            on = True
            if head.group(1).strip():
                current = [head.group(1)]
                rows.append(current)
            continue
        if not on:
            continue
        row = ROW_RE.match(line)
        if row:
            current = [row.group(2)]
            rows.append(current)
            continue
        if not line.strip() or (FIELD_RE.match(line) and current is not None):
            break
        if current is not None:
            current.append(line)
    out = []
    for parts in rows:
        names = [" ".join(n.split()).strip(" .;") for n in " ".join(parts).split(",")]
        names = [n for n in names if n]
        if names:
            out.append(names)
    return out


def read_tray(text: str, shades=()) -> dict | None:
    """What the open tray holds, from his brief's own words: ``{"rows", "cols", "shape", "names": [[…]], "source"}`` —
    its grid ("18 square pans in 3 rows of 6"), else the rows his shade names come in, else a count of pans laid out as
    near a square as the count allows; each pan's name from his brief's shade names, else the product record's
    (``shades``: its ``shade_names`` entries' English). None where nothing names a pan."""
    text = str(text or "")
    names = _names(text)
    source = "his brief"
    if not names and shades:
        flat = [str(s["en"]).strip() if isinstance(s, dict) and s.get("en") else str(s).strip() for s in shades]
        names = [[n for n in flat if n]] if any(flat) else []
        source = "the product record"
    grid = GRID_RE.search(text)
    count = COUNT_RE.search(text)
    shape = "square"
    if grid and grid.group(2):
        shape = grid.group(2).lower()
    elif count and count.group(2):
        shape = count.group(2).lower()
    if grid:
        rows, cols = int(grid.group(3)), int(grid.group(4))
    elif len(names) > 1:
        rows, cols = len(names), max(len(r) for r in names)
    else:
        n = int(count.group(1)) if count else sum(len(r) for r in names)
        if n <= 0:
            return None
        rows = max(1, int(math.floor(math.sqrt(n / 2.0))))
        cols = int(math.ceil(n / float(rows)))
    flat = [n for r in names for n in r]
    by_row = [r[:cols] for r in names] if len(names) == rows else [flat[i * cols:(i + 1) * cols] for i in range(rows)]
    by_row = [r + [""] * (cols - len(r)) for r in by_row]
    return {"rows": rows, "cols": cols, "shape": shape if shape in ("square", "round") else "square",
            "names": by_row, "source": source if flat else "none named",
            "named": len([n for r in by_row for n in r if n])}


def _em(line: str, face: str) -> float:
    """A line's width at 1 pt, in capitals and tracked."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    return stringWidth(line, face, 1.0) + NAME_TRACKING_EM * len(line)


def _two_lines(name: str, face: str) -> list:
    """A name broken at the space that leaves its two lines most alike in width; one word stays one line."""
    words = name.upper().split()
    if len(words) < 2:
        return [name.upper()]
    cut = min(range(1, len(words)),
              key=lambda i: abs(_em(" ".join(words[:i]), face) - _em(" ".join(words[i:]), face)))
    return [" ".join(words[:cut]), " ".join(words[cut:])]


def _fit_pt(names: list, pan_mm: float, face: str, band_mm: float):
    """``(size, lines)`` — the one size every name is set at, and each name's lines: the largest size at which the
    longest, in capitals and tracked, fits its pan on one line; where that is under NAME_MIN_PT, the longest broken onto
    two lines (``_two_lines``, each pair inside the band under its pan) and only the names too long at that size broken;
    never under NAME_MIN_PT — a single word wider than its pan even there is set at the floor and said so."""
    from apps.ire.back_panel import MM_PER_PT
    named = [n for n in names if n]
    if not named:
        return NAME_MAX_PT, {}
    room = pan_mm * NAME_FILL

    def size_for(lines):
        return math.floor(room / (max(_em(line, face) for line in lines) * MM_PER_PT) * 4.0) / 4.0
    one = size_for([n.upper() for n in named])
    if one >= NAME_MIN_PT:
        pt = min(NAME_MAX_PT, one)
        return pt, {n: [n.upper()] for n in named}
    two = size_for([line for n in named for line in _two_lines(n, face)])
    pair_fits = math.floor(band_mm / (2.0 * NAME_LEADING * MM_PER_PT) * 4.0) / 4.0
    pt = max(NAME_MIN_PT, min(NAME_MAX_PT, two, pair_fits))
    return pt, {n: ([n.upper()] if _em(n.upper(), face) * pt * MM_PER_PT <= room else _two_lines(n, face))
                for n in named}


def layout(tray: dict, case_w_mm: float, case_h_mm: float) -> dict:
    """The insert and its pans, in mm from the insert's top left: ``{"insert": (w, h), "pan": side, "gap", "margin",
    "frame", "band_mm", "pans": [(row, col, x, y)], "field": (x0, y0, x1, y1)}`` — every pan one size, the largest the
    insert holds with its names under them, the grid centred."""
    w, h = case_w_mm - 2.0 * WALL_MM, case_h_mm - 2.0 * WALL_MM
    rows, cols = tray["rows"], tray["cols"]
    from apps.ire.back_panel import MM_PER_PT
    band = NAME_BAND_EM * NAME_MAX_PT * MM_PER_PT
    # side s: cols*s + (cols-1)*gap*s + rim*s <= w; rows*(s+band) + (rows-1)*gap*s + rim*s <= h
    rim = 2.0 * (MARGIN_SHARE + FRAME_SHARE + INSET_SHARE)
    across = cols + (cols - 1) * GAP_SHARE + rim
    down = rows + (rows - 1) * GAP_SHARE + rim
    side = min(w / across, (h - rows * band) / down)
    gap, margin = GAP_SHARE * side, MARGIN_SHARE * side
    grid_w = cols * side + (cols - 1) * gap
    grid_h = rows * (side + band) + (rows - 1) * gap
    x0, y0 = (w - grid_w) / 2.0, (h - grid_h) / 2.0
    pans = [(r, c, x0 + c * (side + gap), y0 + r * (side + band + gap)) for r in range(rows) for c in range(cols)]
    return {"insert": (w, h), "pan": side, "gap": gap, "margin": margin, "frame": FRAME_SHARE * side, "band_mm": band,
            "pans": pans, "field": (x0 - margin, y0 - margin, x0 + grid_w + margin, y0 + grid_h + margin)}


def _pan_segments(shape: str, x: float, y: float, side: float) -> list:
    from apps.ire.graph import ClosePath, CubicTo, LineTo, MoveTo
    if shape == "round":
        k, r = 0.5523 * side / 2.0, side / 2.0
        cx, cy = x + r, y + r
        return [MoveTo(x=cx + r, y=cy), CubicTo(x1=cx + r, y1=cy + k, x2=cx + k, y2=cy + r, x=cx, y=cy + r),
                CubicTo(x1=cx - k, y1=cy + r, x2=cx - r, y2=cy + k, x=cx - r, y=cy),
                CubicTo(x1=cx - r, y1=cy - k, x2=cx - k, y2=cy - r, x=cx, y=cy - r),
                CubicTo(x1=cx + k, y1=cy - r, x2=cx + r, y2=cy - k, x=cx + r, y=cy), ClosePath()]
    rr = 0.08 * side
    k = 0.5523 * rr
    return [MoveTo(x=x + rr, y=y), LineTo(x=x + side - rr, y=y),
            CubicTo(x1=x + side - rr + k, y1=y, x2=x + side, y2=y + rr - k, x=x + side, y=y + rr),
            LineTo(x=x + side, y=y + side - rr),
            CubicTo(x1=x + side, y1=y + side - rr + k, x2=x + side - rr + k, y2=y + side, x=x + side - rr, y=y + side),
            LineTo(x=x + rr, y=y + side),
            CubicTo(x1=x + rr - k, y1=y + side, x2=x, y2=y + side - rr + k, x=x, y=y + side - rr),
            LineTo(x=x, y=y + rr), CubicTo(x1=x, y1=y + rr - k, x2=x + rr - k, y2=y, x=x + rr, y=y), ClosePath()]


def _ring(x0, y0, x1, y1, width) -> list:
    from apps.ire.graph import ClosePath, LineTo, MoveTo
    outer = [MoveTo(x=x0 - width, y=y0 - width), LineTo(x=x1 + width, y=y0 - width),
             LineTo(x=x1 + width, y=y1 + width), LineTo(x=x0 - width, y=y1 + width), ClosePath()]
    inner = [MoveTo(x=x0, y=y0), LineTo(x=x0, y=y1), LineTo(x=x1, y=y1), LineTo(x=x1, y=y0), ClosePath()]
    return outer + inner


#: a pan's finish, as it is shown — every one vector, never a raster:
#: [his goal of 2026-10-12, (9): "SHIMMER pans: a soft, subtle sheen (light glow toward one corner), never a hard
#: left-to-right stripe."] a shimmer pan's light: a glow centred toward its upper left (SHEEN_CENTRE of its side in from
#: the corner) reaching SHEEN_REACH of its side, fading through SHEEN_STOPS — (offset, share towards white) — into the
#: shade itself; never a straight blend across the pan
SHEEN_CENTRE = 0.3
SHEEN_REACH = 1.0
SHEEN_STOPS = ((0.0, 0.3), (0.35, 0.13), (0.7, 0.04), (1.0, 0.0))
#: [his goal of 2026-10-12, (10): "GLITTER pans: fine, dense sparkle, never a few big white dots."] a glitter pan's
#: flakes: SPARKLES of them, one in each cell of an even grid over the pan (so the sparkle is dense everywhere, never
#: bunched), each a fleck SPARKLE_RADIUS of the side across and lifted SPARKLE_LIFT towards white — some the shade's
#: own light, some near white — at SPARKLE_ALPHA, as fine flakes of pressed glitter catch the light
SPARKLES = 144
SPARKLE_RADIUS = (0.004, 0.011)
SPARKLE_LIFT = (0.35, 0.95)
SPARKLE_ALPHA = (0.55, 1.0)
SPARKLE_INSET = 0.06


def _towards_white(hx: str, share: float) -> str:
    r, g, b = (int(hx[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02X%02X%02X" % tuple(int(round(v + (255 - v) * share)) for v in (r, g, b))


def _pan_shown(pan: dict, segs: list, x: float, y: float, side: float, name: str) -> list:
    """[his test blocker on design 124, 2026-10-11, (5): "Every pan gets a real shade colour and finish (matte / shimmer / glitter) ... No grey pans."]
    A pan as it is shown: its shade's own colour, and its finish — MATTE flat, SHIMMER a sheen across it, GLITTER fine
    specks strewn on it (the same specks wherever the same pan is drawn)."""
    import random

    from apps.ire.graph import ClosePath, Color, CubicTo, GradientFill, GradientStop, MoveTo, Path, SolidFill

    def circle(cx, cy, rr):
        k = 0.5523 * rr
        return [MoveTo(x=cx + rr, y=cy), CubicTo(x1=cx + rr, y1=cy + k, x2=cx + k, y2=cy + rr, x=cx, y=cy + rr),
                CubicTo(x1=cx - k, y1=cy + rr, x2=cx - rr, y2=cy + k, x=cx - rr, y=cy),
                CubicTo(x1=cx - rr, y1=cy - k, x2=cx - k, y2=cy - rr, x=cx, y=cy - rr),
                CubicTo(x1=cx + k, y1=cy - rr, x2=cx + rr, y2=cy - k, x=cx + rr, y=cy), ClosePath()]
    colour = Color.from_hex(pan["hex"])
    if pan["finish"] == "shimmer":
        # [his goal of 2026-10-12, (9)] a soft light toward one corner, fading into the shade
        fill = GradientFill(kind="radial", cx=x + side * SHEEN_CENTRE, cy=y + side * SHEEN_CENTRE, r=side * SHEEN_REACH,
                            stops=[GradientStop(offset=at, color=Color.from_hex(_towards_white(pan["hex"], lift)))
                                   for at, lift in SHEEN_STOPS])
    else:
        fill = SolidFill(color=colour)
    out = [Path(name=name, segments=segs, fill=fill)]
    if pan["finish"] == "glitter":
        # [his goal of 2026-10-12, (10)] fine flakes, one in every cell of an even grid — dense, never bunched
        rnd = random.Random("%s|%s" % (name, pan["hex"]))
        cells = int(round(math.sqrt(SPARKLES)))
        span = side * (1.0 - 2.0 * SPARKLE_INSET)
        for k in range(cells * cells):
            row, col = divmod(k, cells)
            fx = x + side * SPARKLE_INSET + span * (col + rnd.uniform(0.1, 0.9)) / cells
            fy = y + side * SPARKLE_INSET + span * (row + rnd.uniform(0.1, 0.9)) / cells
            fleck = Color.from_hex(_towards_white(pan["hex"], rnd.uniform(*SPARKLE_LIFT)))
            radius = side * rnd.uniform(*SPARKLE_RADIUS)
            out.append(Path(name="%s-speck-%d" % (name, k), segments=circle(fx, fy, radius),
                            fill=SolidFill(color=fleck, opacity=round(rnd.uniform(*SPARKLE_ALPHA), 3))))
    return out


#: [his goal of 2026-10-12, (12)] the open lid's hinge, between its inside and the insert, on the sheet
HINGE_GAP_MM = 3.0


def _lid_inside_group(trace: dict, x: float, y: float, w: float, h: float):
    """``(Group, record)`` — the inside of the lid at ``w`` x ``h`` mm from (x, y): the tray picture's strip traced
    (``lid_art.art_group``) along its foot — the hinge — at the picture's own proportion, the picture's sky carried up
    over the rest of the lid, its top band's colours."""
    from apps.ire.graph import Color, GradientFill, GradientStop, Group, Rect
    from apps.pipeline.targets.container import lid_art as _la
    sw, sh = trace["size_px"]
    strip_h = min(h, w * float(sh) / float(sw))
    top = trace["sky"]["rows"][0]
    stops = [GradientStop(offset=k / float(len(top) - 1), color=Color.from_hex(c)) for k, c in enumerate(top)]
    above = Rect(name="lid-inside-sky", x=x, y=y, w=w, h=h - strip_h + 0.5,
                 fill=GradientFill(kind="linear", stops=stops, x1=x, y1=y, x2=x + w, y2=y))
    clip = Rect(name="lid-inside-outline", x=x, y=y, w=w, h=h)
    from apps.ire.emitters.pdf_ai import _rect_segments
    art = _la.art_group(trace, x, y + h - strip_h, w, strip_h, clip=_rect_segments(clip), prefix="lid-inside",
                        name="LID INSIDE ART")         # its own names: never the lid's "lid-art-*" the finishes read
    return (Group(name="LID INSIDE", role="decoration", children=[above, art]),
            {"panel_mm": [round(w, 2), round(h, 2)], "strip_mm": round(strip_h, 2),
             "regions": len(trace["regions"]), "from": "the tray picture"})


def _pans_drawn(shown: list, side: float) -> dict:
    """[His goal of 2026-10-12, (9) and (10).] The pans' finishes as drawn, measured from their own nodes: each shimmer
    pan's gradient (its kind, its lightest stop's lift towards white over its shade, the steepest fall of that lift per
    share of its run) and each glitter pan's flakes (how many, the largest a share of the pan's side)."""
    from apps.ire.graph import GradientFill
    out = {"shimmer": [], "glitter": []}
    by_pan: dict = {}
    for node in shown:
        name = node.name or ""
        base = name.split("-speck-")[0]
        by_pan.setdefault(base, []).append(node)
    for base, nodes in by_pan.items():
        pan = next((n for n in nodes if n.name == base), None)
        flakes = [n for n in nodes if n.name != base]
        if pan is not None and isinstance(pan.fill, GradientFill):
            shade = pan.fill.stops[-1].color

            def lift(c):
                return max((getattr(c, k) - getattr(shade, k)) / max(1.0 - getattr(shade, k), 1e-6) for k in "rgb")
            lifts = [(s.offset, lift(s.color)) for s in pan.fill.stops]
            steep = max(((a[1] - b[1]) / max(b[0] - a[0], 1e-6) for a, b in zip(lifts, lifts[1:])), default=0.0)
            out["shimmer"].append({"pan": base, "kind": pan.fill.kind, "max_lift": round(max(v for _o, v in lifts), 3),
                                   "steepest": round(steep, 3)})
        if flakes:
            from apps.ire.emitters.pdf_ai import _segments_box
            widest = max(b[2] - b[0] for b in (_segments_box(n.segments) for n in flakes))
            out["glitter"].append({"pan": base, "flakes": len(flakes), "largest_share": round(widest / side, 4)})
    return out


def _de(a: str, b: str) -> float:
    """CIE76 between two hexes."""
    import cv2
    import numpy as np
    px = np.uint8([[[int(h[5:7], 16), int(h[3:5], 16), int(h[1:3], 16)] for h in (a, b)]])
    lab = cv2.cvtColor(px, cv2.COLOR_BGR2LAB).astype(float)
    lab[..., 0] *= 100.0 / 255.0
    lab[..., 1:] -= 128.0
    return float(np.sqrt(((lab[0, 0] - lab[0, 1]) ** 2).sum()))


def compose_open_tray(tray: dict, case_w_mm: float, case_h_mm: float, x: float, y: float, *, ground_hex: str,
                      ink_hex: str, edge_hexes: list, face: str, pans: list | None = None, rim_hex: str | None = None,
                      glow_hex: str | None = None, name_hex: str | None = None, lid_inside: dict | None = None):
    """``(Group, record)`` — the open tray's printed insert at print size, its top left at (x, y) on the sheet: its
    ground, the frame round its pans in a gradient through ``edge_hexes`` (the design's own colours), each pan a well
    cut through it (its keyline on its own group, the pan shown and never printed) and each name in capitals under its
    pan, at the one size the longest fits (``face``: the face its names are measured in). [His test blocker on design
    124, (5)] ``pans`` — ``tray_picture.pans_for`` — each pan shown in its shade's own colour and finish."""
    from apps.ire.graph import Color, GradientFill, GradientStop, Group, Path, Rect, SolidFill, Stroke, TextRun
    at = layout(tray, case_w_mm, case_h_mm)
    w, h = at["insert"]
    # [his goal of 2026-10-12, (12): "Draw the inside of the lid (roses + arch above the pans)"] the lid's inside at its
    # print size above the insert — the tray picture's strip at its hinge, the picture's own sky carried up above it —
    # the insert under it, a hinge apart
    lid_group, lid_record, y_lid = None, None, y
    if lid_inside:
        lid_group, lid_record = _lid_inside_group(lid_inside, x, y, w, h)
        y = y + h + HINGE_GAP_MM
    side, band = at["pan"], at["band_mm"]
    names = [n for row in tray["names"] for n in row]
    pt, lines_of = _fit_pt(names, side, face, band)
    from apps.ire.back_panel import MM_PER_PT
    lead = NAME_LEADING * pt * MM_PER_PT
    # [his goal of 2026-10-12, (13)] the names in the picture's ink where it reads against the ground, else the design's
    name_ink = name_hex if (name_hex and _de(name_hex, ground_hex) >= NAME_CONTRAST_DE) else ink_hex
    ink = Color.from_hex(name_ink)
    kids = [Rect(name="tray-insert-ground", x=x, y=y, w=w, h=h, radius_mm=2.0, fill=SolidFill(color=Color.from_hex(
        ground_hex)))]
    fx0, fy0, fx1, fy1 = at["field"]
    if glow_hex is None:
        # no tray picture read: the frame round the pans in the design's own colours, as before
        edges = [Color.from_hex(c) for c in edge_hexes if c] or [ink]
        if len(edges) == 1:
            edges = edges * 2
        stops = [GradientStop(offset=i / float(len(edges) - 1), color=c) for i, c in enumerate(edges)]
        kids.append(Path(name="tray-pan-field-edge", fill_rule="evenodd", segments=_ring(
            x + fx0, y + fy0, x + fx1, y + fy1, at["frame"]), fill=GradientFill(
            kind="linear", stops=stops, x1=x + fx0, y1=y + fy0, x2=x + fx1, y2=y + fy1)))
    wells, shown, words, rims, glows = [], [], [], [], []
    for (r, c, px, py) in at["pans"]:
        segs = _pan_segments(tray["shape"], x + px, y + py, side)
        if pans is not None:
            shown.extend(_pan_shown(pans[r][c], segs, x + px, y + py, side, "pan-%d-%d" % (r + 1, c + 1)))
        else:
            shown.append(Path(name="pan-%d-%d" % (r + 1, c + 1), segments=segs, fill=SolidFill(color=Color.from_hex(
                PAN_SHOWN))))
        wells.append(Path(name="pan-well-%d-%d" % (r + 1, c + 1), segments=segs, stroke=Stroke(
            color=Color.from_hex(rim_hex or PAN_KEYLINE), width_mm=0.25)))
        if glow_hex is not None:
            # [his goal of 2026-10-12, (12)] the picture's glow round the pan, fading outward
            step = side * GLOW_REACH / GLOW_STEPS
            for k in range(GLOW_STEPS):
                glows.append(Path(name="pan-glow-%d-%d-%d" % (r + 1, c + 1, k), fill_rule="evenodd",
                                  segments=_ring(x + px - k * step, y + py - k * step, x + px + side + k * step,
                                                 y + py + side + k * step, step),
                                  fill=SolidFill(color=Color.from_hex(glow_hex),
                                                 opacity=round(GLOW_ALPHA * (1.0 - k / float(GLOW_STEPS)), 3))))
        if rim_hex is not None:
            # [his goal of 2026-10-12, (11)] the pan framed in the picture's soft gold, never a grey line
            w_rim = side * RIM_SHARE
            rims.append(Path(name="pan-rim-%d-%d" % (r + 1, c + 1), fill_rule="evenodd",
                             segments=_ring(x + px + w_rim, y + py + w_rim, x + px + side - w_rim,
                                            y + py + side - w_rim, w_rim),
                             fill=SolidFill(color=Color.from_hex(rim_hex))))
        name = tray["names"][r][c] if r < len(tray["names"]) and c < len(tray["names"][r]) else ""
        if name:
            # one line, or two (the second named "-2"), centred in the band under its own pan
            lines = lines_of[name]
            top = y + py + side + band * 0.62 - lead * (len(lines) - 1) / 2.0
            for i, line in enumerate(lines):
                words.append(TextRun(name="shade-name-%d-%d%s" % (r + 1, c + 1, "-2" if i else ""), text=line,
                                     x=x + px + side / 2.0, y=top + i * lead, size_pt=pt, color=ink, font="regular",
                                     align="center"))
    group = Group(name="OPEN TRAY", role="decoration", children=([lid_group] if lid_group else []) + kids + (
        [Group(name="PAN GLOWS", role="decoration", children=glows)] if glows else []) + [
        Group(name="PANS (shown, not printed)", role="generic", children=shown)] + (
        [Group(name="PAN RIMS", role="decoration", children=rims)] if rims else []) + [
        Group(name="PAN WELLS (cut)", role="generic", children=wells),
        Group(name="SHADE NAMES", role="typography", children=words)])
    record = {"schema": SCHEMA, "rows": tray["rows"], "cols": tray["cols"], "shape": tray["shape"],
              **({"pans": [[{k: pan[k] for k in ("name", "hex", "finish", "source")} for pan in row] for row in pans]}
                 if pans is not None else {}),
              "insert_mm": [round(w, 2), round(h, 2)], "pan_mm": round(side, 2), "name_pt": pt,
              # [his goal of 2026-10-12, (11)–(13)] the tray's inks as drawn, and the names against their floor
              "pans_drawn": _pans_drawn(shown, at["pan"]),              # [his goal of 2026-10-12, (9), (10)]
              "rim_hex": rim_hex, "glow_hex": glow_hex, "name_hex": name_ink, "name_floor_pt": NAME_MIN_PT,
              "lid_inside": lid_record, "drawn_h_mm": round((y - y_lid) + h, 2),
              "name_contrast_de": round(_de(name_ink, ground_hex), 1),
              "names_on_two_lines": sorted(n for n, lines in lines_of.items() if len(lines) > 1),
              "wider_than_pan": sorted(n for n, lines in lines_of.items()
                                       if max(_em(line, face) for line in lines) * pt * MM_PER_PT > side),
              "names": tray["names"], "named": tray["named"], "source": tray["source"],
              "printed": "the insert's ground, the frame and the names; the pans are wells cut through it"}
    return group, record


#: kept on the drawing's record
SCHEMA = "palette_open_tray/1.0"
