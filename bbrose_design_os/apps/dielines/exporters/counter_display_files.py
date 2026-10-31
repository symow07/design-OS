"""The one die writer. The counter display 1.0's files, as a die-maker's (owner, 2026-10-28): a layered PDF at true 1:1
mm (CUT, CREASE, PERF, GLUE, BLEED, ARTWORK, DIMENSIONS; the cut and crease on their CutContour and Crease spot plates),
DXF and CF2 for the die shop, the flat nested on a standard board sheet with its yield, and a dimensioned assembly
drawing (flat, folded front and side, exploded) a converter can quote from. And a carton's files (the consolidation of
2026-10-29, from production_pdf, svg_exporter and ai_exporter): its CMYK production PDF at 1:1, its print SVG, its .ai,
and the same DXF and CF2 as the stand's."""
from __future__ import annotations

import base64
import logging
import math
import os
import shutil
import tempfile
from datetime import date
from pathlib import Path

import svgwrite
from reportlab.lib.colors import CMYKColor, CMYKColorSep
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from shapely.geometry import Polygon

from apps.dielines.geometry import counter_display as cd
from apps.dielines.geometry.coordinates import DielineCoordinates
from apps.dielines.geometry.primitives import CubicSeg, LineSeg, path_to_svg_d

logger = logging.getLogger(__name__)

LAYERS = ("ARTWORK", "CUT", "CREASE", "PERF", "HALF-CUT", "GLUE", "SAFE", "BLEED", "DIMENSIONS")
NON_PRINTING = ("GLUE", "SAFE", "BLEED", "DIMENSIONS")
PT = 72 / 25.4
#: DXF layer colours (AutoCAD colour index) and CF2 line types (1 cut, 2 crease, 3 perforation, 4 score: no code for a
#: half-cut was found, so it goes out as a score and a shop can remap it: docs/research/stands/rules/_common.json)
DXF_COLOURS = {"CUT": 6, "CREASE": 4, "PERF": 2, "HALF-CUT": 5, "GLUE": 3, "SAFE": 1, "BLEED": 8, "DIMENSIONS": 7}
CF2_TYPES = {"CUT": 1, "CREASE": 2, "PERF": 3, "HALF-CUT": 4}
GUTTER_MM, SHEET_MARGIN_MM, GRIPPER_MM = 6.0, 10.0, 12.0


def layers(die, record):
    """Every layer's polylines in sheet millimetres (y down): the die's own, the dimension lines and the grain arrow."""
    geo = cd.layer_geometry(die)
    out = {"CUT": geo["cut"], "CREASE": geo["crease"], "PERF": geo["perf"], "HALF-CUT": geo["half_cut"], "GLUE": geo["glue"],
           "SAFE": geo["safe"], "BLEED": geo["bleed"], "ARTWORK": [], "DIMENSIONS": []}
    words = []
    tray = next(part for part in die.parts if part.name == "tray")
    x0, y0, x1, y1 = tray.outline().bounds
    out["DIMENSIONS"] += _dimension(x0, y1 + 8, x1, y1 + 8, "%.1f" % (x1 - x0), words)
    out["DIMENSIONS"] += _dimension(x1 + 8, y0, x1 + 8, y1, "%.1f" % (y1 - y0), words, vertical=True)
    floor = next(f for n, f, _ in tray.faces if n == "floor")
    fx0, fy0, fx1, fy1 = floor.bounds
    out["DIMENSIONS"] += _dimension(fx0, fy0 + 6, fx1, fy0 + 6, "floor %.1f" % (fx1 - fx0), words)
    out["DIMENSIONS"] += _dimension(fx0 + 6, fy0, fx0 + 6, fy1, "floor %.1f" % (fy1 - fy0), words, vertical=True)
    gx, gy = fx1 - 12, fy0 + 10
    out["DIMENSIONS"] += [[(gx, gy), (gx, gy + 30)], [(gx - 3, gy + 5), (gx, gy), (gx + 3, gy + 5)],
                          [(gx - 3, gy + 25), (gx, gy + 30), (gx + 3, gy + 25)]]
    words.append(("GRAIN: " + record["production"]["grain"], (gx - 60, gy + 36), 3.0))
    return out, words


def _dimension(xa, ya, xb, yb, text, words, vertical=False):
    """A dimension line with its ticks and its words."""
    tick = 2.5
    lines = [[(xa, ya), (xb, yb)]]
    if vertical:
        lines += [[(xa - tick, ya), (xa + tick, ya)], [(xb - tick, yb), (xb + tick, yb)]]
        words.append((text, (xa + 2, (ya + yb) / 2), 3.0))
    else:
        lines += [[(xa, ya - tick), (xa, ya + tick)], [(xb, yb - tick), (xb, yb + tick)]]
        words.append((text, ((xa + xb) / 2 - 6, ya - 1.5), 3.0))
    return lines


def write_pdf(die, record, path, artwork=None):
    """The die on one page the size of its sheet, true 1:1 mm, each layer its optional content group; CUT, CREASE
    and PERF on their spot plates; GLUE, BLEED and DIMENSIONS seen on screen and never printed. ``artwork``: the
    painted flat raster ``{"path", "box_mm"}`` on the ARTWORK layer at its box (flat_box_mm), 1:1."""
    from reportlab.lib.colors import CMYKColorSep, Color
    from reportlab.pdfgen import canvas
    path = Path(path)
    regular, _bold = _resolve_fonts()
    c = canvas.Canvas(str(path), pagesize=(die.sheet_w * PT, die.sheet_h * PT), invariant=1, initialFontName=regular)
    c.setTitle(die.title)
    lines, words = layers(die, record)
    colour = {"CUT": spot("CUT"), "CREASE": spot("CREASE"),
              "PERF": CMYKColorSep(0, .6, 1, 0, spotName="Perf", density=1.0),
              "HALF-CUT": CMYKColorSep(.5, .8, 0, 0, spotName="HalfCut", density=1.0),
              "GLUE": Color(.2, .7, .3), "SAFE": Color(0, .7, .8), "BLEED": Color(.55, .55, .55), "DIMENSIONS": Color(0, .63, .89)}
    for layer in LAYERS:
        begin(c, layer)
        if layer == "ARTWORK" and artwork:
            x0, y0, x1, y1 = artwork["box_mm"]
            c.drawImage(str(artwork["path"]), x0 * PT, (die.sheet_h - y1) * PT, (x1 - x0) * PT, (y1 - y0) * PT,
                        mask="auto")
        if layer in colour:
            c.setStrokeColor(colour[layer])
            c.setLineWidth(.25 if layer != "DIMENSIONS" else .2)
            c.setDash(*((3, 1.6) if layer == "CREASE" else (1, 1) if layer == "PERF" else ([5, 1.5, 1, 1.5], 0) if layer == "HALF-CUT" else ()))
            for poly in lines[layer]:
                p = c.beginPath()
                p.moveTo(poly[0][0] * PT, (die.sheet_h - poly[0][1]) * PT)
                for x, y in poly[1:]:
                    p.lineTo(x * PT, (die.sheet_h - y) * PT)
                c.drawPath(p, stroke=1, fill=0)
            c.setDash()
        if layer == "DIMENSIONS":
            c.setFillColor(colour["DIMENSIONS"])
            for text, (x, y), size in words + [(label, xy, size) for label, xy, size in die.labels]:
                c.setFont(regular, size * PT)
                c.drawString(x * PT, (die.sheet_h - y) * PT, text)
            bx, by, length = die.bar
            c.line(bx * PT, (die.sheet_h - by) * PT, (bx + length) * PT, (die.sheet_h - by) * PT)
            c.setFont(regular, 3 * PT)
            c.drawString(bx * PT, (die.sheet_h - by + 2) * PT, "50 mm — print at 100 %")
        end(c)
    c.showPage()
    c.save()
    return apply_layers(str(path), LAYERS, order=LAYERS, non_printing=NON_PRINTING)


def write_dxf(die, record, path):
    """AutoCAD R12 ASCII DXF in millimetres (y up, as DXF is): one LINE per segment, on layers named as the PDF's."""
    lines, _words = layers(die, record)
    return _write_dxf(lines, die.sheet_w, die.sheet_h, path)


def _write_dxf(lines, sheet_w, sheet_h, path):
    """The DXF of ``lines`` (``{layer: [polyline in sheet mm, y down]}``) on a ``sheet_w`` × ``sheet_h`` sheet."""
    out = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$MEASUREMENT", "70", "1",
           "9", "$EXTMIN", "10", "0.0", "20", "0.0", "9", "$EXTMAX", "10", "%.3f" % sheet_w, "20",
           "%.3f" % sheet_h, "0", "ENDSEC", "0", "SECTION", "2", "TABLES",
           "0", "TABLE", "2", "LTYPE", "70", "1", "0", "LTYPE", "2", "CONTINUOUS", "70", "0", "3", "Solid line",
           "72", "65", "73", "0", "40", "0.0", "0", "ENDTAB", "0", "TABLE", "2", "LAYER", "70", str(len(DXF_COLOURS))]
    for name, colour in DXF_COLOURS.items():
        out += ["0", "LAYER", "2", name, "70", "0", "62", str(colour), "6", "CONTINUOUS"]
    out += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    count = 0
    for layer in DXF_COLOURS:
        for poly in lines.get(layer, []):
            for (xa, ya), (xb, yb) in zip(poly, poly[1:]):
                if math.dist((xa, ya), (xb, yb)) < 1e-6:
                    continue
                out += ["0", "LINE", "8", layer, "10", "%.4f" % xa, "20", "%.4f" % (sheet_h - ya), "30", "0.0",
                        "11", "%.4f" % xb, "21", "%.4f" % (sheet_h - yb), "31", "0.0"]
                count += 1
    out += ["0", "ENDSEC", "0", "EOF"]
    Path(path).write_text("\r\n".join(out) + "\r\n", encoding="ascii")
    return {"entities": count, "layers": list(DXF_COLOURS), "units": "mm", "version": "R12 (AC1009)"}


def write_cf2(die, record, path):
    """CF2 (Common Format 2) for the die shop: millimetres (UM), one MAIN with its lower-left and upper-right
    corners, one L line per segment — pointage 2, type 1 cut, 2 crease, 3 perforation, no bridges set (the die maker
    places the nicks). Opened in no die maker's CAD here: the shop's import is the check."""
    lines, _words = layers(die, record)
    template = record.get("template") or {}
    name = "%s_%s" % (template.get("id", cd.TEMPLATE_ID), template.get("version", cd.VERSION).replace(".", "_"))
    return _write_cf2(lines, die.sheet_w, die.sheet_h, name, path)


def _write_cf2(lines, sheet_w, sheet_h, name, path):
    """The CF2 of ``lines`` (``{layer: [polyline in sheet mm, y down]}``), its MAIN named ``name``."""
    out = ["$BOF", "V2", "ORDER", name, "END", "MAIN," + name, "UM", "LL,0.0,0.0",
           "UR,%.3f,%.3f" % (sheet_w, sheet_h), "SCALE,1,1"]
    count = 0
    for layer, kind in CF2_TYPES.items():
        for poly in lines.get(layer, []):
            for (xa, ya), (xb, yb) in zip(poly, poly[1:]):
                if math.dist((xa, ya), (xb, yb)) < 1e-6:
                    continue
                out.append("L,2,%d,0,%.3f,%.3f,%.3f,%.3f,0,0" % (kind, xa, sheet_h - ya, xb, sheet_h - yb))
                count += 1
    out += ["END", "$EOF"]
    Path(path).write_text("\n".join(out) + "\n", encoding="ascii")
    return {"lines": count, "types": CF2_TYPES, "units": "mm", "verified_by_a_die_shop": False}


def nest(die, record):
    """The parts nested on each standard sheet for the board — shelf packing of their rectangles, turned where that
    fits better, with a 6 mm gutter, a 10 mm margin and a 12 mm gripper edge; whole sets only. Returns every sheet
    tried, best yield first. True-shape nesting would do better; this is the floor the converter can beat."""
    board = record["board"]["preset"]
    if record["production"].get("grain_axis"):
        return true_shape_nest(die, record)
    parts = []
    for part in die.parts:
        x0, y0, x1, y1 = part.outline().buffer(cd.DIE_BLEED_MM, join_style=2).bounds
        parts.append({"name": part.name, "w": x1 - x0, "h": y1 - y0, "area": part.outline().area})
    # a die that declares its grain keeps every part the way the grain runs: the sheet's flutes are one direction
    turns = (False,) if record["production"].get("grain_axis") else (False, True)
    results = []
    for sheet_w, sheet_h in cd.STANDARD_SHEETS[board]:
        usable_w, usable_h = sheet_w - 2 * SHEET_MARGIN_MM, sheet_h - SHEET_MARGIN_MM - GRIPPER_MM
        best = None
        for turn in turns:
            sets, placements = _shelf(parts, usable_w, usable_h, turn)
            if best is None or sets > best[0]:
                best = (sets, placements, turn)
        sets, placements, turn = best
        used = sets * sum(part["area"] for part in parts)
        results.append({"sheet_mm": [sheet_w, sheet_h], "sets": sets, "parts_placed": len(placements),
                        "yield": round(used / (sheet_w * sheet_h), 4), "turned": turn, "margin_mm": SHEET_MARGIN_MM, "gripper_mm": GRIPPER_MM,
                        "placements": [{"part": name, "x_mm": round(x, 2), "y_mm": round(y, 2), "w_mm": round(w, 2), "h_mm": round(h, 2)}
                                       for name, x, y, w, h in placements],
                        "method": "shelf packing of the parts' bleed rectangles; whole sets only"})
    results.sort(key=lambda row: (-row["yield"], row["sheet_mm"][0] * row["sheet_mm"][1]))
    return {"board": record["board"]["name"], "sheets": results, "best": results[0] if results else None}


def true_shape_nest(die, record):
    """Whole sets on each standard sheet by their true outlines, bleed and gutter included: largest part first, each at the
    lowest, then leftmost, free place, so the small parts go in the tray's waste corners. Parts keep the sheet's grain: a half
    turn is allowed, a quarter turn never. Done on a 2 mm occupancy grid, so it is deterministic and a little cautious."""
    import numpy as np
    from PIL import Image, ImageDraw
    from scipy.signal import fftconvolve
    from shapely.affinity import rotate

    cell = 2.0
    grown = []
    for part in sorted(die.parts, key=lambda p: -p.outline().area):
        outline = part.outline().buffer(cd.DIE_BLEED_MM, join_style=2)
        area = part.outline().area
        for turned in (False, True):
            shape = rotate(outline, 180, origin="centroid") if turned else outline
            x0, y0, x1, y1 = shape.bounds
            w, h = int(math.ceil((x1 - x0) / cell)) + 1, int(math.ceil((y1 - y0) / cell)) + 1
            image = Image.new("L", (w, h), 0)
            draw = ImageDraw.Draw(image)
            for piece in getattr(shape, "geoms", [shape]):
                draw.polygon([((x - x0) / cell, (y - y0) / cell) for x, y in piece.exterior.coords], fill=1, outline=1)
            grown.append({"name": part.name, "area": area, "turned": turned, "mask": np.asarray(image, np.float32), "w_mm": x1 - x0, "h_mm": y1 - y0})
    names = list(dict.fromkeys(row["name"] for row in grown))
    results = []
    gutter = int(math.ceil(GUTTER_MM / cell))
    for sheet_w, sheet_h in cd.STANDARD_SHEETS[record["board"]["preset"]]:
        W, H = int((sheet_w - 2 * SHEET_MARGIN_MM) / cell), int((sheet_h - SHEET_MARGIN_MM - GRIPPER_MM) / cell)
        taken = np.zeros((H, W), np.float32)
        placed, sets = [], 0
        while True:
            trial, grid, ok = [], taken.copy(), True
            for name in names:
                best = None
                for row in (r for r in grown if r["name"] == name):
                    mask = row["mask"]
                    if mask.shape[0] > H or mask.shape[1] > W:
                        continue
                    grow = np.ones((2 * gutter + 1, 2 * gutter + 1), np.float32)
                    swollen = fftconvolve(mask, grow, mode="same") > .5
                    hits = fftconvolve(grid, swollen[::-1, ::-1].astype(np.float32), mode="valid")
                    free = np.argwhere(hits < .5)
                    if len(free):
                        y, x = free[np.lexsort((free[:, 1], free[:, 0]))][0]
                        if best is None or (y, x) < best[:2]:
                            best = (int(y), int(x), row)
                if best is None:
                    ok = False
                    break
                y, x, row = best
                grid[y:y + row["mask"].shape[0], x:x + row["mask"].shape[1]] += row["mask"]
                trial.append({"part": name, "x_mm": x * cell, "y_mm": y * cell, "w_mm": round(row["w_mm"], 2), "h_mm": round(row["h_mm"], 2), "half_turn": row["turned"]})
            if not ok:
                break
            taken, placed, sets = grid, placed + trial, sets + 1
        used = sets * sum(part.outline().area for part in die.parts)
        results.append({"sheet_mm": [sheet_w, sheet_h], "sets": sets, "parts_placed": len(placed), "yield": round(used / (sheet_w * sheet_h), 4),
                        "turned": False, "margin_mm": SHEET_MARGIN_MM, "gripper_mm": GRIPPER_MM, "placements": placed,
                        "method": "true outlines on a 2 mm grid, largest first, lowest free place, grain kept; whole sets only"})
    results.sort(key=lambda row: (-row["yield"], row["sheet_mm"][0] * row["sheet_mm"][1]))
    best = results[0] if results else None
    area = sum(part.outline().area for part in die.parts)
    return {"board": record["board"]["name"], "sheets": results, "best": best, "board_area_mm2": round(area),
            "one_set": {"note": "a set's board against the sheet it nests on", "sheet_share": round(best["yield"] / max(best["sets"], 1), 4) if best else None}}


def _shelf(parts, width, height, turn):
    """Whole sets placed shelf by shelf, tallest first; returns (sets, placements)."""
    placements, sets = [], 0
    x = y = shelf = 0.0
    while True:
        trial = list(placements)
        tx, ty, tshelf = x, y, shelf
        fitted = True
        for part in sorted(parts, key=lambda p: -max(p["w"], p["h"])):
            w, h = (part["h"], part["w"]) if turn and part["h"] > part["w"] else (part["w"], part["h"])
            if w > width or h > height:
                return sets, placements
            if tx + w > width:
                tx, ty, tshelf = 0.0, ty + tshelf + GUTTER_MM, 0.0
            if ty + h > height:
                fitted = False
                break
            trial.append((part["name"], tx, ty, w, h))
            tx += w + GUTTER_MM
            tshelf = max(tshelf, h)
        if not fitted:
            return sets, placements
        placements, x, y, shelf, sets = trial, tx, ty, tshelf, sets + 1


def assembly_drawing(die, record, path):
    """A3 landscape, one page, true numbers in millimetres: the flat (scaled, its overall size), the folded front and
    side elevations with every height, and an exploded view (the insert above the tray, the header leaf unfolded)."""
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.pdfgen import canvas
    v, g = record["inputs"], record["geometry"]
    W, D, H, t = (v[k] for k in ("width_mm", "depth_mm", "height_mm", "board_mm"))
    front, back, header = (g[k] for k in ("front_panel_height_mm", "back_panel_height_mm", "header_height_mm"))
    page_w, page_h = landscape(A3)
    c = canvas.Canvas(str(path), pagesize=(page_w, page_h), invariant=1)
    c.setTitle("Counter display 1.0 — assembly drawing")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(28, page_h - 30, "Counter display %s · %s · board: %s · all sizes in mm" % (
        cd.VERSION, "%d × %d %s" % (record["layout"]["rows"], record["layout"]["columns"], record["product"]),
        record["board"]["name"]))
    cells = [(28, page_h / 2 + 10, page_w / 2 - 40, page_h / 2 - 60), (page_w / 2 + 10, page_h / 2 + 10, page_w / 2 - 40, page_h / 2 - 60),
             (28, 30, page_w / 2 - 40, page_h / 2 - 60), (page_w / 2 + 10, 30, page_w / 2 - 40, page_h / 2 - 60)]

    def frame(cell, title, w_mm, h_mm):
        x, y, w, h = cell
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x, y + h + 8, title)
        k = min(w / w_mm, h / h_mm)
        return k, x, y

    def dim(xa, ya, xb, yb, text):
        c.setLineWidth(.3)
        c.line(xa, ya, xb, yb)
        c.setFont("Helvetica", 7)
        c.drawCentredString((xa + xb) / 2 + (8 if xa == xb else 0), (ya + yb) / 2 + (2 if ya == yb else 0), text)

    # 1. flat
    k, x, y = frame(cells[0], "1 · Flat die (sheet %d × %d)" % (die.sheet_w, die.sheet_h), die.sheet_w, die.sheet_h)
    c.setLineWidth(.4)
    for part in die.parts:
        for line in cd.cut_polygons(part):
            pts = list(line.coords)
            p = c.beginPath()
            p.moveTo(x + pts[0][0] * k, y + (die.sheet_h - pts[0][1]) * k)
            for px, py in pts[1:]:
                p.lineTo(x + px * k, y + (die.sheet_h - py) * k)
            c.drawPath(p)
        c.setDash(2, 1.5)
        for _name, crease in part.creases:
            (xa, ya), (xb, yb) = crease.coords[0], crease.coords[-1]
            c.line(x + xa * k, y + (die.sheet_h - ya) * k, x + xb * k, y + (die.sheet_h - yb) * k)
        c.setDash()
    dim(x, y - 8, x + die.sheet_w * k, y - 8, "%d" % die.sheet_w)
    # 2. front elevation
    k, x, y = frame(cells[1], "2 · Folded, front", W, H)
    c.rect(x, y, W * k, H * k)
    c.rect(x, y, W * k, (front + t) * k)
    c.line(x, y + (H - header) * k, x + W * k, y + (H - header) * k)
    dim(x, y - 8, x + W * k, y - 8, "W %.1f" % W)
    dim(x - 10, y, x - 10, y + H * k, "H %.1f" % H)
    dim(x + W * k + 10, y + (H - header) * k, x + W * k + 10, y + H * k, "header %.1f" % header)
    dim(x + W * k + 10, y, x + W * k + 10, y + (front + t) * k, "front %.1f" % (front + t))
    # 3. side elevation
    k, x, y = frame(cells[2], "3 · Folded, side (shopper to the left)", D + 20, H)
    p = c.beginPath()
    p.moveTo(x, y)
    p.lineTo(x, y + (front + t) * k)
    p.lineTo(x + D * k, y + (back + t) * k)
    p.lineTo(x + D * k, y)
    p.close()
    c.drawPath(p)
    c.rect(x + (D - 2 * t) * k, y, 2 * t * k, H * k)
    dim(x, y - 8, x + D * k, y - 8, "D %.1f" % D)
    dim(x + D * k + 12, y, x + D * k + 12, y + (back + t) * k, "back %.1f" % (back + t))
    # 4. exploded (oblique, 45°, half depth)
    k, x, y = frame(cells[3], "4 · Exploded: the insert lifted, the header leaf open", W + D * .5 + 20, H + 60)
    ox, oy = D * .35 * k, D * .35 * k

    def box3(x0, y0, w, h):
        c.rect(x + x0 * k, y + y0 * k, w * k, h * k)
        c.rect(x + x0 * k + ox, y + y0 * k + oy, w * k, h * k)
        for dx, dy in ((0, 0), (w, 0), (0, h), (w, h)):
            c.line(x + (x0 + dx) * k, y + (y0 + dy) * k, x + (x0 + dx) * k + ox, y + (y0 + dy) * k + oy)
    box3(0, 0, W, front + t)
    c.rect(x + ox, y + oy, W * k, (H - header) * k)
    c.setDash(2, 1.5)
    c.rect(x + ox, y + oy + (H - header) * k, W * k, header * k)
    c.rect(x + ox, y + oy + H * k, W * k, (header - t) * k)
    c.setDash()
    lift = front + 30
    if g.get("holder_mm"):
        pw, pd = g["holder_mm"]
        c.rect(x + (W - pw) / 2 * k + ox / 2, y + lift * k + oy / 2, pw * k, pd * .35 * k)
        c.setFont("Helvetica", 7)
        c.drawString(x + W * k + ox + 6, y + lift * k + oy / 2, "insert: tabs into the side walls' slots")
    c.drawString(x + W * k + ox + 6, y + oy + H * k, "header leaf: folds down the shopper side; tab into the slot")
    c.showPage()
    c.save()
    return {"views": ["flat", "folded front", "folded side", "exploded"], "units": "mm"}


def write_all(record, folder, artwork=None):
    """Every file for one record into ``folder``; returns their names and the reports. ``artwork``: as write_pdf's."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    die = cd.build_die(record)
    if record.get("schema") == cd.TEMPLATE_SCHEMA:
        return write_template(die, record, folder, artwork)
    out = {"pdf_layers": write_pdf(die, record, folder / "die.pdf", artwork),
           "dxf": write_dxf(die, record, folder / "die.dxf"), "cf2": write_cf2(die, record, folder / "die.cf2"),
           "nest": nest(die, record), "assembly": assembly_drawing(die, record, folder / "assembly.pdf")}
    out["files"] = ["die.pdf", "die.dxf", "die.cf2", "assembly.pdf"]
    return out


#: the file's law for a die alone: the print layers, empty, under DIE, locked, with its sub-layers (round_files_export's LAYERS and DIE_SUBLAYERS)
AI_LAYERS = ("GROUND", "MOTIFS", "RELIEF", "FOIL", "WORDS", "DIE")
AI_SUBLAYERS = ("BLEED", "SAFE", "GLUE", "HALF-CUT", "PERF", "CREASE", "CUT")
AI_COLOURS = {"CUT": (0, 100, 0, 0), "CREASE": (100, 0, 0, 0), "PERF": (0, 60, 100, 0), "HALF-CUT": (50, 80, 0, 0), "GLUE": (70, 0, 80, 0), "SAFE": (60, 0, 20, 0), "BLEED": (0, 0, 0, 45)}
_AI_JSX = """var D=__DATA__;var R={saved:false};try{app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;var k=72/25.4;var W=D.w*k,H=D.h*k;
var doc=app.documents.add(DocumentColorSpace.CMYK,W,H);doc.artboards[0].artboardRect=[0,H,W,0];var tops={};
for(var i=0;i<D.layers.length;i++){var L=i===0?doc.layers[0]:doc.layers.add();L.name=D.layers[i];tops[D.layers[i]]=L;}
for(var i=0;i<D.subs.length;i++){var S=tops.DIE.layers.add();S.name=D.subs[i];var c=new CMYKColor(),v=D.colours[D.subs[i]];c.cyan=v[0];c.magenta=v[1];c.yellow=v[2];c.black=v[3];var rows=D.lines[D.subs[i]]||[];
for(var j=0;j<rows.length;j++){var P=S.pathItems.add();var pts=[];for(var m=0;m<rows[j].length;m++)pts.push([rows[j][m][0]*k,H-rows[j][m][1]*k]);P.setEntirePath(pts);P.filled=false;P.stroked=true;P.strokeColor=c;P.strokeWidth=.5;P.name=D.subs[i]+' '+(j+1);}}
tops.DIE.locked=true;var o=new IllustratorSaveOptions();o.pdfCompatible=true;doc.saveAs(new File(D.path),o);doc.close(SaveOptions.DONOTSAVECHANGES);
var d=app.open(new File(D.path));R.layers=[];var die=d.layers.getByName('DIE');R.die_locked=die.locked;for(var i=0;i<d.layers.length;i++)R.layers.push(d.layers[i].name);R.subs=[];for(var i=0;i<die.layers.length;i++)R.subs.push(die.layers[i].name+':'+die.layers[i].pathItems.length);d.close(SaveOptions.DONOTSAVECHANGES);R.saved=true;}catch(e){R.error=String(e);}
var f=new File(D.report);f.encoding='UTF-8';f.open('w');f.write(R.toSource());f.close();'{}';"""


def native_die_ai(die, record, ai_path):
    """The die as Illustrator's own .ai by the file's law, every line drawn in place, saved and opened again, on a copy: its layers read back.
    Illustrator is never quit: it may be the owner's. Returns the record; ``native`` False, with why, leaves the PDF-compatible .ai standing."""
    import json
    from apps.ire.handoff.illustrator_exec import run_jsx
    lines, _words = layers(die, record)
    data = {"w": die.sheet_w, "h": die.sheet_h, "layers": list(AI_LAYERS), "subs": list(AI_SUBLAYERS), "colours": AI_COLOURS,
            "lines": {name: [[list(point) for point in row] for row in lines.get(name, [])] for name in AI_SUBLAYERS}}
    with tempfile.TemporaryDirectory() as folder:
        report, candidate, script = Path(folder) / "report.txt", Path(folder) / "die.ai", Path(folder) / "die.jsx"
        data.update(path=str(candidate), report=str(report))
        script.write_text(_AI_JSX.replace("__DATA__", json.dumps(data)))
        run = run_jsx(str(script), timeout_s=300)
        said = report.read_text(encoding="utf8") if report.exists() else ""
        if candidate.exists() and "saved:true" in said and "die_locked:true" in said and all(name + ":" in said for name in AI_SUBLAYERS):
            shutil.copyfile(candidate, ai_path)
            return {"format": "Illustrator's own .ai, by the file's law", "native": True, "read_back": said, "bytes": Path(ai_path).stat().st_size}
        return {"format": "PDF-compatible .ai", "native": False, "why": (said or str(run))[:300]}


def write_ai(pdf_path, ai_path):
    """The die's .ai before Illustrator: a PDF-compatible file under this name, which Illustrator opens with its layers flattened. The
    worker and the proof tool then give it Illustrator's own (native_die_ai)."""
    shutil.copyfile(pdf_path, ai_path)
    return {"format": "PDF-compatible .ai", "native": False, "bytes": Path(ai_path).stat().st_size}


def opens(folder):
    """Each export read back by a real reader, not by what wrote it: PDF and .ai by PyMuPDF, DXF by ezdxf, CF2 by the strict reader
    below (no die maker's CAD is here). Returns a row per file and ``all_open``."""
    import fitz
    import ezdxf
    folder = Path(folder)
    rows = {}
    for name in ("die.pdf", "die.ai", "fold-up.pdf", "assembly.pdf", "cut-and-fold-1to1.pdf", "nest.pdf"):
        with fitz.open(folder / name) as doc:
            rows[name] = {"opens": doc.page_count >= 1 and not doc.is_encrypted, "pages": doc.page_count,
                          "fonts_embedded": all(font[3] != "" and font[1] != "n/a" for page in doc for font in page.get_fonts())}
    doc = ezdxf.readfile(folder / "die.dxf")
    auditor = doc.audit()
    modelspace = doc.modelspace()
    rows["die.dxf"] = {"opens": not auditor.has_errors, "reader": "ezdxf " + ezdxf.__version__, "entities": len(modelspace),
                       "layers": sorted(layer.dxf.name for layer in doc.layers)}
    rows["die.cf2"] = read_cf2(folder / "die.cf2")
    return {"files": rows, "all_open": all(row["opens"] for row in rows.values())}


def read_cf2(path):
    """A strict reader of the CF2 we write: its frame, its unit, each line's fields and that it lies on the sheet. Our own: no
    die maker's CAD is on this machine, so a shop's import stays the last check."""
    lines = Path(path).read_text(encoding="ascii").splitlines()
    ok = lines[:2] == ["$BOF", "V2"] and lines[-1] == "$EOF" and "UM" in lines
    ur = next((row for row in lines if row.startswith("UR,")), None)
    kinds = {}
    if ur is None:
        return {"opens": False, "reader": "our own strict reader"}
    w, h = (float(v) for v in ur.split(",")[1:])
    for row in lines:
        if row.startswith("L,"):
            fields = row.split(",")
            if len(fields) != 10:
                ok = False
                continue
            xa, ya, xb, yb = (float(v) for v in fields[4:8])
            ok = ok and all(-1e-6 <= v <= w + 1e-6 for v in (xa, xb)) and all(-1e-6 <= v <= h + 1e-6 for v in (ya, yb))
            kinds[fields[2]] = kinds.get(fields[2], 0) + 1
    return {"opens": bool(ok and kinds), "reader": "our own strict reader; no die maker's CAD here", "lines_by_type": kinds}


def write_template(die, record, folder, artwork=None, *, native=None):
    """A stand template's whole file set, its reports with it. ``native``: Illustrator's own .ai; by default wherever a test is not running."""
    import sys
    from apps.dielines.exporters import stand_sheets
    from apps.dielines.geometry import stand_templates as templates
    report = templates.qualify(record, die)
    nesting = nest(die, record)
    report["better_than_house"] = templates.better_than_house(record, report, nesting)
    out = {"pdf_layers": write_pdf(die, record, folder / "die.pdf", artwork), "ai": write_ai(folder / "die.pdf", folder / "die.ai"),
           "dxf": write_dxf(die, record, folder / "die.dxf"), "cf2": write_cf2(die, record, folder / "die.cf2"),
           "nest": nesting, "qualification": report}
    out.update(stand_sheets.write_sheets(die, record, report, folder, nesting))
    stand_sheets.die_preview(die, record, folder / "die.png")
    out["files"] = ["die.pdf", "die.ai", "die.dxf", "die.cf2", "fold-up.pdf", "assembly.pdf", "cut-and-fold-1to1.pdf", "nest.pdf",
                    "die.png", "fold-up.png", "assembly.png", "nest.png"]
    if native if native is not None else "pytest" not in sys.modules:
        out["ai"] = native_die_ai(die, record, folder / "die.ai") or out["ai"]
    out["open_check"] = opens(folder)
    return out


# --- the flat template: the die first, the design painted on it (owner, 2026-10-28) -----------------------------------
#
# The stand is designed flat: the engine draws the die, the image model paints only inside its printed faces, and the
# die is applied again to what comes back. One millimetre-to-pixel transform (flat_frame) serves the template, the
# painting, the re-application, every check and the files.

FLAT_CANVASES = ((1536, 1024), (1024, 1536))       # gpt-image-2's full-resolution edit canvases
FLAT_MARGIN_PX = 24
FLAT_GREY = (200, 200, 200)                        # an unprinted part: the inside faces, the flaps, the tabs
FLAT_LINE = (96, 96, 96)
SHOPPER = ("front panel", "header front")          # the faces the shopper sees
UP_VECTORS = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}   # a face turned this many quarters clockwise onto the die


def flat_frame(die, part="tray"):
    """The printed part, its bleed included, at the largest scale a gpt-image-2 canvas holds it, centred."""
    from shapely.ops import unary_union
    piece = cd.piece_of(die, part)
    x0, y0, x1, y1 = unary_union([piece.outline(), cd.bleed_area(piece)]).bounds
    W, H, k = max(((W, H, min((W - 2 * FLAT_MARGIN_PX) / (x1 - x0), (H - 2 * FLAT_MARGIN_PX) / (y1 - y0)))
                   for W, H in FLAT_CANVASES), key=lambda row: row[2])
    k = round(k, 6)
    return {"schema": "counter_display_flat_frame/1", "part": part, "size": "%dx%d" % (W, H), "canvas_px": [W, H],
            "px_per_mm": k, "frame_mm": [x0, y0, x1, y1],
            "offset_px": [round((W - (x1 - x0) * k) / 2, 3), round((H - (y1 - y0) * k) / 2, 3)],
            "dpi_at_1to1": round(k * 25.4, 1)}


def flat_px(frame, x, y):
    k, (ox, oy), (x0, y0) = frame["px_per_mm"], frame["offset_px"], frame["frame_mm"][:2]
    return ox + (x - x0) * k, oy + (y - y0) * k


def flat_box_mm(frame):
    """The whole canvas's box on the die sheet (mm): where the painted raster stands at 1:1."""
    k, (W, H), (ox, oy), (x0, y0) = frame["px_per_mm"], frame["canvas_px"], frame["offset_px"], frame["frame_mm"][:2]
    return [x0 - ox / k, y0 - oy / k, x0 + (W - ox) / k, y0 + (H - oy) / k]


def _fill(draw, frame, geometry, value, hole=0):
    for poly in getattr(geometry, "geoms", [geometry]):
        if poly.is_empty:
            continue
        draw.polygon([flat_px(frame, *p) for p in poly.exterior.coords], fill=value)
        for ring in poly.interiors:
            draw.polygon([flat_px(frame, *p) for p in ring.coords], fill=hole)


def flat_masks(die, frame):
    """Per canvas pixel: ``paint`` — inside a printed face or its bleed (counter_display.bleed_area, the engine's own);
    ``owner`` — the printed face it belongs to (1-based, in ``names``' order; a bleed pixel goes to the nearest printed
    face), 0 where nothing is painted."""
    import numpy as np
    from PIL import Image, ImageDraw
    from scipy import ndimage
    piece = cd.piece_of(die, frame["part"])
    W, H = frame["canvas_px"]
    paint = Image.new("L", (W, H), 0)
    _fill(ImageDraw.Draw(paint), frame, cd.bleed_area(piece), 255)
    paint = np.asarray(paint) > 0
    printed = [(name, face) for name, face, is_printed in piece.faces if is_printed]
    owner = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(owner)
    for index, (_name, face) in enumerate(printed, 1):
        _fill(draw, frame, face, index)
    owner = np.asarray(owner)
    _distance, (iy, ix) = ndimage.distance_transform_edt(owner == 0, return_indices=True)
    owner = np.where(paint, np.where(owner > 0, owner, owner[iy, ix]), 0).astype(np.uint8)
    return {"paint": paint, "owner": owner, "names": [name for name, _face in printed]}


def _dashed(draw, points, fill, width, dash=9.0, gap=6.0):
    for (xa, ya), (xb, yb) in zip(points, points[1:]):
        length = math.hypot(xb - xa, yb - ya)
        at = 0.0
        while at < length:
            end = min(at + dash, length)
            draw.line([(xa + (xb - xa) * at / length, ya + (yb - ya) * at / length),
                       (xa + (xb - xa) * end / length, ya + (yb - ya) * end / length)], fill=fill, width=width)
            at = end + gap


def _margin_marks(draw, frame, piece, paint, occupied, up):
    """On the template's white margin only (never where paint goes; the die's re-application restores the margin):
    a fold tick past each end of every crease, as a print sheet carries, and each printed face's name with its way
    up, joined by a short leader that stops at the bleed's edge."""
    from PIL import ImageFont
    free = (occupied.min(axis=-1) == 255) & ~paint
    H, W = paint.shape
    for _name, line in piece.creases:
        (xa, ya), (xb, yb) = flat_px(frame, *line.coords[0]), flat_px(frame, *line.coords[-1])
        length = math.hypot(xb - xa, yb - ya)
        ux, uy = (xb - xa) / length, (yb - ya) / length
        for (x, y), sign in (((xa, ya), -1), ((xb, yb), 1)):
            step = 0
            while step < 60 and 0 <= int(y + sign * uy * step) < H and 0 <= int(x + sign * ux * step) < W and \
                    not free[int(y + sign * uy * step), int(x + sign * ux * step)]:
                step += 1
            start = (x + sign * ux * (step + 3), y + sign * uy * (step + 3))
            end = (start[0] + sign * ux * 14, start[1] + sign * uy * 14)
            if all(0 <= int(v) < lim and free[int(start[1]), int(start[0])] for v, lim in ((end[0], W), (end[1], H))):
                _dashed(draw, [start, end], FLAT_LINE, 2, dash=5, gap=3)
    font = ImageFont.load_default(size=16)
    for name, face, printed in piece.faces:
        if not printed:
            continue
        x0, y0 = flat_px(frame, *face.bounds[:2])
        x1, y1 = flat_px(frame, *face.bounds[2:])
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        text = name.upper() + ("  (shopper side)" if name in SHOPPER else "")
        tw, th = draw.textlength(text, font=font), 18
        for lx, ly, tx, ty in ((x0 - gap - tw, cy - th / 2, x0 - 4, cy) if side == 0 else
                               (x1 + gap, cy - th / 2, x1 + 4, cy) if side == 1 else
                               (cx - tw / 2, y0 - gap - 4 - th, cx, y0 - 4) if side == 2 else
                               (cx - tw / 2, y1 + gap + 4, cx, y1 + 4)
                               for gap in (30, 70) for side in range(4)):
            box = [int(lx) - 4, int(ly) - 4, int(lx + tw) + 28, int(ly + th) + 4]
            if box[0] < 0 or box[1] < 0 or box[2] >= W or box[3] >= H or not free[box[1]:box[3], box[0]:box[2]].all():
                continue
            draw.text((lx, ly), text, fill=FLAT_LINE, font=font)
            # the leader runs to the face's edge; the part of it inside the paint is blanked with the paint itself
            start = (box[2] if tx >= box[2] else box[0] if tx <= box[0] else (box[0] + box[2]) / 2,
                     box[3] if ty >= box[3] else box[1] if ty <= box[1] else (box[1] + box[3]) / 2)
            draw.line([start, (tx, ty)], fill=FLAT_LINE, width=1)
            if name in up:
                dx, dy = UP_VECTORS[up[name] % 4]
                bx, by = lx + tw + 14, ly + th / 2
                tip = (bx + dx * 7, by + dy * 7)
                draw.line([(bx - dx * 7, by - dy * 7), tip], fill=FLAT_LINE, width=2)
                draw.polygon([tip, (tip[0] - dx * 5 - dy * 4, tip[1] - dy * 5 + dx * 4),
                              (tip[0] - dx * 5 + dy * 4, tip[1] - dy * 5 - dx * 4)], fill=FLAT_LINE)
            free[box[1]:box[3], box[0]:box[2]] = False
            break


def flat_template(die, frame, folder, *, up=None):
    """The two pictures the flat method draws from one transform, into ``folder``:

    - ``template.png`` — the painting's input and its mask: white paper, the part's unprinted faces grey with their cut
      and crease lines, and every printed face with its bleed TRANSPARENT and empty. Nothing at all is drawn inside a
      painted area (no name, line or mark): whatever stands there is painted into the art (stop 15).
    - ``sheet.png`` — the owner's template sheet: every face outlined and named, the bleed band shown, the unprinted
      faces greyed, the creases dashed with their fold direction, each printed face's way up (``up``: face name → the
      quarters it is turned clockwise onto the die), and the shopper's faces marked FRONT.

    Returns the record: the frame, the files, the faces with their pixel boxes, and what each picture holds."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    up = up or {}
    piece = cd.piece_of(die, frame["part"])
    W, H = frame["canvas_px"]
    masks = flat_masks(die, frame)
    cuts = [[flat_px(frame, *p) for p in line.coords] for line in cd.cut_polygons(piece)]
    creases = [(name, [flat_px(frame, *p) for p in line.coords]) for name, line in piece.creases]

    base = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(base)
    for _name, face, printed in piece.faces:
        if not printed:
            _fill(draw, frame, face, FLAT_GREY, hole=(255, 255, 255))
    for points in cuts:
        draw.line(points, fill=FLAT_LINE, width=2)
    for _name, points in creases:
        _dashed(draw, points, FLAT_LINE, 2)
    _margin_marks(draw, frame, piece, masks["paint"], np.asarray(base).copy(), up)
    rgb = np.asarray(base).copy()
    rgb[masks["paint"]] = 255
    template = np.dstack([rgb, np.where(masks["paint"], 0, 255).astype(np.uint8)])
    Image.fromarray(template, "RGBA").save(folder / "template.png")
    np.save(folder / "owner.npy", masks["owner"])

    sheet = Image.new("RGB", (W, H + 64), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    _fill(draw, frame, cd.bleed_area(piece), (247, 214, 214))
    small, label = ImageFont.load_default(size=12), ImageFont.load_default(size=15)
    faces = []
    for name, face, printed in piece.faces:
        _fill(draw, frame, face, (252, 249, 242) if printed else FLAT_GREY, hole=(255, 255, 255))
        x0, y0 = flat_px(frame, *face.bounds[:2])
        x1, y1 = flat_px(frame, *face.bounds[2:])
        faces.append({"name": name, "printed": printed, "box_px": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
                      "box_mm": [round(v, 3) for v in face.bounds], "shopper": name in SHOPPER})
    for points in cuts:
        draw.line(points, fill=(17, 17, 17), width=2)
    for _name, points in creases:
        _dashed(draw, points, (42, 110, 187), 2)
    for name, face, printed in piece.faces:
        cx, cy = flat_px(frame, face.centroid.x, face.centroid.y)
        x0, y0, x1, y1 = (v for row in (flat_px(frame, *face.bounds[:2]), flat_px(frame, *face.bounds[2:])) for v in row)
        font = label if printed and min(x1 - x0, y1 - y0) > 40 else small
        text = name.upper() if printed else name
        draw.text((cx, cy), text, fill=(20, 20, 20) if printed else (70, 70, 70), font=font, anchor="mm")
        if name in SHOPPER:
            draw.text((cx, cy + 16), "FRONT: the shopper sees this", fill=(176, 32, 32), font=small, anchor="mm")
        if printed and name in up:
            dx, dy = UP_VECTORS[up[name] % 4]
            reach = min(x1 - x0, y1 - y0) * 0.3
            ax, ay = cx - dx * reach * 0.2, cy - dy * reach * 0.2 + (30 if name in SHOPPER else 0)
            tip = (ax + dx * reach, ay + dy * reach)
            draw.line([(ax, ay), tip], fill=(176, 32, 32), width=2)
            draw.polygon([tip, (tip[0] - dx * 7 - dy * 5, tip[1] - dy * 7 + dx * 5),
                          (tip[0] - dx * 7 + dy * 5, tip[1] - dy * 7 - dx * 5)], fill=(176, 32, 32))
            draw.text((tip[0] + dx * 10, tip[1] + dy * 10), "up", fill=(176, 32, 32), font=small, anchor="mm")
    for _name, points in creases:
        (xa, ya), (xb, yb) = points[0], points[-1]
        draw.text(((xa + xb) / 2, (ya + yb) / 2 - 8), "fold", fill=(42, 110, 187), font=small, anchor="mm")
    legend = ("Solid = cut. Dashed blue = crease: every crease folds away from you, so the printed side ends outside. "
              "Pink band = 3 mm bleed. Grey = not printed (inside faces, glue flaps, tabs). "
              "Scale %.2f px/mm (%.0f dpi at 1:1)." % (frame["px_per_mm"], frame["dpi_at_1to1"]))
    draw.text((FLAT_MARGIN_PX, H + 10), legend, fill=(40, 40, 40), font=small)
    sheet.save(folder / "sheet.png")
    return {"schema": "counter_display_flat_template/1", "frame": frame, "template": "template.png",
            "sheet": "sheet.png", "owner_map": "owner.npy", "faces": faces, "printed": masks["names"], "up": up,
            "template_holds": "white paper; unprinted faces grey with their cut and crease lines; every printed face "
                              "and its bleed transparent and empty",
            "sheet_holds": "faces outlined and named, bleed band, unprinted faces greyed, creases dashed with the fold "
                           "direction, each printed face's way up, the shopper's faces marked FRONT"}


def apply_die(raw, template, paint):
    """The die applied again to a painting, exactly: inside each printed face and its bleed the painting stands, and
    every other pixel is the template's own, byte for byte. ``raw`` RGB and ``template`` RGBA arrays of one canvas.
    Returns (flat RGB: the art on the template's unprinted parts, art RGBA: the painted faces alone)."""
    import numpy as np
    flat = np.where(paint[..., None], raw[..., :3], template[..., :3]).astype(np.uint8)
    art = np.dstack([np.where(paint[..., None], raw[..., :3], 255), np.where(paint, 255, 0)]).astype(np.uint8)
    return flat, art


def die_view(flat, die, frame):
    """The flat art with the engine's own cut and crease lines drawn over it, through the same transform."""
    from PIL import Image, ImageDraw
    piece = cd.piece_of(die, frame["part"])
    view = Image.fromarray(flat).convert("RGB")
    draw = ImageDraw.Draw(view)
    for line in cd.cut_polygons(piece):
        draw.line([flat_px(frame, *p) for p in line.coords], fill=(17, 17, 17), width=1)
    for _name, line in piece.creases:
        _dashed(draw, [flat_px(frame, *p) for p in line.coords], (42, 110, 187), 1, dash=6, gap=4)
    return view


def die_proof(raw, template, flat, paint, owner, names, *, search_px=12, threshold=28):
    """The die-match proof, measured, not assumed:

    - ``registration``: where the model's own paint stops (pixels it changed from the template by more than
      ``threshold``) against the engine's paint mask, at every shift within ``search_px``: the best shift is the
      painting's drift before the die was applied again (it is never moved; what lies off the mask is cut);
    - ``outside``: after re-application, every pixel off the printed faces and their bleed compared with the
      template's, byte for byte — the count that differ must be 0, so the die's own lines there stand at zero offset;
    - ``coverage``: per printed face, the share of its pixels the painting changed from the empty template."""
    import numpy as np
    tpl = template[..., :3].astype(np.int16)
    changed = np.abs(raw[..., :3].astype(np.int16) - tpl).max(axis=-1) > threshold
    ys, xs = np.nonzero(paint)
    y0, y1 = max(ys.min() - search_px, 0), min(ys.max() + search_px + 1, paint.shape[0])
    x0, x1 = max(xs.min() - search_px, 0), min(xs.max() + search_px + 1, paint.shape[1])
    mask, seen = paint[y0:y1, x0:x1], changed[y0:y1, x0:x1]
    scores = {}
    for dy in range(-search_px, search_px + 1):
        shifted_y = np.roll(seen, -dy, axis=0)
        for dx in range(-search_px, search_px + 1):
            shifted = np.roll(shifted_y, -dx, axis=1)
            inter = np.count_nonzero(shifted & mask)
            scores[dx, dy] = inter / max(np.count_nonzero(shifted | mask), 1)
    best = max(scores, key=scores.get)
    outside = ~paint
    differing = int(np.count_nonzero(np.any(flat[outside] != template[..., :3][outside], axis=-1)))
    coverage = {name: round(float(changed[owner == index].mean()), 4) for index, name in enumerate(names, 1)}
    return {"schema": "counter_display_die_proof/1",
            "registration": {"best_shift_px": list(best), "iou_at_zero": round(scores[0, 0], 4),
                             "iou_at_best": round(scores[best], 4), "search_px": search_px,
                             "note": "the painting's own drift before the die was applied again"},
            "outside": {"pixels": int(np.count_nonzero(outside)), "differing_from_template": differing,
                        "zero_offset": differing == 0},
            "coverage": coverage, "threshold": threshold}


def pdf_readback(pdf_path, die, record, artwork_box_mm):
    """The written 1:1 PDF read back: every CUT and CREASE vertex against the engine's own (largest distance, mm),
    and the ARTWORK raster's placed box against the box it was given (mm)."""
    import fitz
    expected = {"CUT": cd.layer_geometry(die)["cut"], "CREASE": cd.layer_geometry(die)["crease"]}
    found = {"CUT": [], "CREASE": []}
    with fitz.open(str(pdf_path)) as doc:
        page = doc[0]
        for drawing in page.get_drawings():
            layer = drawing.get("layer")
            if layer not in found:
                continue
            for item in drawing["items"]:
                if item[0] == "l":
                    corners = [item[1], item[2]]
                elif item[0] == "qu":
                    corners = [item[1].ul, item[1].ur, item[1].lr, item[1].ll]
                elif item[0] == "re":
                    corners = [item[1].tl, item[1].tr, item[1].br, item[1].bl]
                else:
                    continue
                found[layer] += [(p.x / PT, p.y / PT) for p in corners]
        images = page.get_image_info()
    out = {}
    for layer, polylines in expected.items():
        points = [tuple(p) for line in polylines for p in line]
        if not found[layer]:
            out[layer] = {"vertices": len(points), "read_back": 0, "max_mm": None}
            continue
        worst = max(min(math.hypot(x - u, y - v) for u, v in found[layer]) for x, y in points)
        out[layer] = {"vertices": len(points), "read_back": len(found[layer]), "max_mm": round(worst, 4)}
    if images:
        x0, y0, x1, y1 = images[0]["bbox"]
        placed = [x0 / PT, y0 / PT, x1 / PT, y1 / PT]
        out["ARTWORK"] = {"box_mm": [round(v, 4) for v in placed],
                          "max_mm": round(max(abs(a - b) for a, b in zip(placed, artwork_box_mm)), 4)}
    return out


def fold_pairs(die, frame, *, depth_mm=1.0, step_mm=1.0):
    """Where printed art meets printed art, as pixel pairs to compare (the colour is the caller's to measure): every
    boundary two printed faces share — over a crease, or on the same board with no fold (the back panel running into
    the header) — a point either side of it, ``depth_mm`` in; and each folded corner of the tray (a wall's edge against
    its neighbour's, at the same height above the floor). Returns ``[{"seam", "kind", "pairs": [((xa, ya), (xb, yb))]}]``
    in canvas pixels."""
    from shapely.geometry import Point
    piece = cd.piece_of(die, frame["part"])
    printed = [(name, face) for name, face, is_printed in piece.faces if is_printed]
    creases = [line for _name, line in piece.creases]

    def px(x, y):
        u, v = flat_px(frame, x, y)
        return int(round(u)), int(round(v))

    seams = []
    for i, (a_name, a) in enumerate(printed):
        for b_name, b in printed[i + 1:]:
            shared = a.boundary.intersection(b.boundary)
            lines = [g for g in getattr(shared, "geoms", [shared]) if g.geom_type == "LineString" and g.length > step_mm]
            for line in lines:
                (xa, ya), (xb, yb) = line.coords[0], line.coords[-1]
                length = line.length
                nx, ny = -(yb - ya) / length, (xb - xa) / length
                pairs = []
                for k in range(1, int(length // step_mm)):
                    x, y = xa + (xb - xa) * k * step_mm / length, ya + (yb - ya) * k * step_mm / length
                    p, q = (x + nx * depth_mm, y + ny * depth_mm), (x - nx * depth_mm, y - ny * depth_mm)
                    if a.contains(Point(q)) and b.contains(Point(p)):
                        p, q = q, p
                    if a.contains(Point(p)) and b.contains(Point(q)):
                        pairs.append((px(*p), px(*q)))
                folded = any(line.hausdorff_distance(crease) < 1e-3 for crease in creases)
                if pairs:
                    seams.append({"seam": "%s | %s" % (a_name, b_name), "pairs": pairs,
                                  "kind": "crease" if folded else "same board, no fold"})
    faces = dict(printed)
    floor = next((face for name, face, _printed in piece.faces if name == "floor"), None)
    if floor is not None:
        fx0, fy0, fx1, fy1 = floor.bounds
        walls = {"front panel": ((fx0, fy0), (fx1, fy0), (0, -1)), "back panel": ((fx0, fy1), (fx1, fy1), (0, 1)),
                 "left side": ((fx0, fy0), (fx0, fy1), (-1, 0)), "right side": ((fx1, fy0), (fx1, fy1), (1, 0))}
        # a wall's own crease where the die names it: a template sets a side wall's in from the floor's corner
        for wall, crease_name in (("front panel", "floor / front"), ("back panel", "floor / back"), ("left side", "floor / left"), ("right side", "floor / right")):
            line = dict(piece.creases).get(crease_name)
            if line is not None:
                walls[wall] = (tuple(line.coords[0]), tuple(line.coords[-1]), walls[wall][2])
        for a_name, b_name in (("front panel", "left side"), ("front panel", "right side"),
                               ("back panel", "left side"), ("back panel", "right side")):
            if a_name not in faces or b_name not in faces:
                continue
            (a0, a1, ua), (b0, b1, ub) = walls[a_name], walls[b_name]
            corner_a, corner_b = min(((end_a, end_b) for end_a in (a0, a1) for end_b in (b0, b1)), key=lambda ends: math.dist(*ends))
            far_a, far_b = (a1 if corner_a == a0 else a0), (b1 if corner_b == b0 else b0)
            ea = [(q - c) / math.dist(far_a, corner_a) for q, c in zip(far_a, corner_a)]
            eb = [(q - c) / math.dist(far_b, corner_b) for q, c in zip(far_b, corner_b)]
            pairs, h = [], step_mm / 2
            while True:
                p = (corner_a[0] + ua[0] * h + ea[0] * depth_mm, corner_a[1] + ua[1] * h + ea[1] * depth_mm)
                q = (corner_b[0] + ub[0] * h + eb[0] * depth_mm, corner_b[1] + ub[1] * h + eb[1] * depth_mm)
                if not (faces[a_name].contains(Point(p)) and faces[b_name].contains(Point(q))):
                    break
                pairs.append((px(*p), px(*q)))
                h += step_mm
            if pairs:
                seams.append({"seam": "%s | %s" % (a_name, b_name), "kind": "folded corner", "pairs": pairs})
    return seams


# --- a PDF's named layers (from pdf_layers and the 0.1 sheets' apply_layers, the consolidation of 2026-10-28) --
#
# Each part drawn inside its layer's marked content (``begin`` / ``end``); the file given its optional content groups
# after it is written (``apply_layers``): the guides seen on screen and never printed, CUT and CREASE their spot
# plates. One writer for the stand die and the carton.

CARTON_LAYERS = ("ARTWORK", "CUT", "CREASE", "GLUE", "BLEED", "SAFE", "DIMENSIONS")
CARTON_NON_PRINTING = ("GLUE", "BLEED", "SAFE", "DIMENSIONS")
#: the spot plates the die is cut and creased from, and the screen tint each is shown in
SPOT_PLATES = {"CUT": ("CutContour", (0.0, 1.0, 0.0, 0.0)), "CREASE": ("Crease", (1.0, 0.0, 0.0, 0.0))}
#: the colour the guides are drawn in on screen
GUIDE_HEX = "#00A0E3"


def tag(layer: str) -> str:
    return "OC_" + layer


def begin(c, layer: str) -> None:
    """Open ``layer``'s marked content on the canvas."""
    c._code.append("/OC /%s BDC" % tag(layer))


def end(c) -> None:
    c._code.append("EMC")


def spot(layer: str):
    """The spot colour a die layer is drawn in (reportlab's separation), or None."""
    if layer not in SPOT_PLATES:
        return None
    from reportlab.lib.colors import CMYKColorSep
    name, (cy, ma, ye, k) = SPOT_PLATES[layer]
    return CMYKColorSep(cy, ma, ye, k, spotName=name, density=1.0)


def apply_layers(path: str, layers, order=CARTON_LAYERS, non_printing=CARTON_NON_PRINTING, pages=None) -> list:
    """Give the written file at ``path`` an optional content group for each of ``layers``, in ``order``, each page in
    ``pages`` (all, when None) its /Properties for them, view on; the ``non_printing`` layers (the guides) never print.
    The carton's layers by default (production_pdf and the .ai emitter); the stand die's writer passes its own.
    Returns the layers given."""
    import os

    import fitz
    names = [name for name in order if name in set(layers)]
    if not names:
        return []
    doc = fitz.open(path)
    xrefs = {name: doc.add_ocg(name, on=True) for name in names}
    for name in non_printing:
        if name in xrefs:
            doc.xref_set_key(xrefs[name], "Usage", "<</Print <</PrintState /OFF>> /View <</ViewState /ON>>>>")
    props = "<<%s>>" % " ".join("/%s %d 0 R" % (tag(n), x) for n, x in xrefs.items())
    for pno in range(doc.page_count) if pages is None else pages:
        doc.xref_set_key(doc[pno].xref, "Resources/Properties", props)
    guides = [xrefs[n] for n in non_printing if n in xrefs]
    if guides:
        doc.xref_set_key(doc.pdf_catalog(), "OCProperties/D/AS", "[<</Event /Print /OCGs [%s] /Category [/Print]>>]"
                         % " ".join("%d 0 R" % x for x in guides))
    tmp = path + ".layers"
    # no_new_id: keep the trailer /ID reportlab's invariant canvas wrote, so die.pdf regenerates byte for byte
    # (the sheet verifier's minor: a new /ID on every save)
    doc.save(tmp, garbage=0, deflate=True, no_new_id=True)
    doc.close()
    os.replace(tmp, path)
    return names


def layers_of(path: str) -> dict:
    """``{layer name: {"prints": bool}}`` as the written file declares them."""
    import fitz
    doc = fitz.open(path)
    out = {}
    for xref, info in doc.get_ocgs().items():
        usage = doc.xref_get_key(xref, "Usage")[1] or ""
        out[info["name"]] = {"prints": "/PrintState/OFF" not in usage.replace(" ", "")}
    return out


# --- a carton's files (from production_pdf, svg_exporter and ai_exporter: the consolidation of 2026-10-29) ------------
#
# The carton's CMYK production / prepress PDF: the factory-ready deliverable the text-free SVG deliberately is not.
# Where the SVG is an RGB Illustrator artboard with no text (the designer's working file), this sheet is what a die-cut
# house is handed: a 1:1 CMYK plate with a named CutContour spot separation for the knife, a Crease spot for the
# creasing rules, registration marks, dimensioned callouts and a title block. Drawn directly from
# ``DielineCoordinates`` with reportlab, never through SVG. Text is welcome here: it is a production document, not the
# print dieline itself.
#
# Milestone 9.5 prepress notes:
# - Registration marks are drawn in an ``/All`` Separation colorant (the classic registration colour) so they appear on
#   every plate, the CutContour and Crease die plates included — a plain 100/100/100/100 process colour would print
#   only on the four process plates.
# - Text is set in an embedded TrueType face (the repo's Noto, else DejaVu Sans) so the file has no unembedded-font
#   dependency at the print shop; without either it falls back to the built-in Helvetica (one of the 14 standard PDF
#   fonts every RIP ships). The canvas starts in that face, so no unused Helvetica is declared beside it.
# - TrimBox is the cut polygon's bounds and BleedBox the bleed polygon's, so imposition software picks up the real
#   trim and bleed.
# - KNOWN GAP: not a full PDF/X file — reportlab cannot attach an ICC OutputIntent; output_intent attaches one when the
#   print shop's profile is configured. Every other PDF/X-style requirement (CMYK-only ink, embedded fonts,
#   TrimBox/BleedBox, named spot separations) is met.

# A spot separation turns the colour into a PDF Separation colorant: CutContour (the knife) and Crease (the creasing
# rules), the two industry-standard die separations, are the stand die's own plates (``spot``). It MUST be a
# CMYKColorSep: reportlab routes a colour through PDFDocument.addColor() (the real ``[/Separation /CutContour
# /DeviceCMYK …]`` object) only for that class; a plain CMYKColor with a spotName is flattened to process CMYK.
CUT = spot("CUT")
CREASE = spot("CREASE")
# Bleed + safe are process-grey guides (informational, not a die plate).
BLEED = CMYKColor(0, 0, 0, 0.45)
SAFE = CMYKColor(0, 0, 0, 0.28)
INK = CMYKColor(0, 0, 0, 1)        # body text / dimension lines
# "All separations", the registration colorant: it also lands on the CutContour and Crease die plates, which is what
# makes the marks usable for aligning the die to the printed sheet.
REG = CMYKColorSep(1, 1, 1, 1, spotName="All", density=1)

# --- fonts --------------------------------------------------------------------------------------------------------------
# Milestone 9.5: a real TrueType face embedded, so the PDF carries its own font program (print shops reject files with
# unembedded non-standard fonts). 2026-07-07: the repo-bundled Noto fonts (static/fonts/, OFL) are preferred so every
# environment ships identical embeddable faces — the Arabic face for the trilingual sticker included. DejaVu (a Linux
# system TTF) is the next fallback, then the built-in Helvetica (standard-14): graceful degradation, never a crash.
_DEJAVU_DIR = "/usr/share/fonts/truetype/dejavu"
_FONT_REGULAR_TTF = os.path.join(_DEJAVU_DIR, "DejaVuSans.ttf")
_FONT_BOLD_TTF = os.path.join(_DEJAVU_DIR, "DejaVuSans-Bold.ttf")
_fonts_cache: tuple[str, str] | None = None
_ar_font_cache: str | None | bool = False   # False = unresolved sentinel


def _repo_font(filename: str) -> str:
    from django.conf import settings
    return str(settings.BASE_DIR / "static" / "fonts" / filename)


def _register_ttf(name: str, path: str) -> bool:
    try:
        if os.path.exists(path):
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            pdfmetrics.registerFont(TTFont(name, path))
            return True
    except Exception:  # noqa: BLE001 — any registration failure → fallback
        pass
    return False


def _resolve_fonts() -> tuple[str, str]:
    """Return (regular, bold) font names, registering embedded TTFs if found."""
    global _fonts_cache
    if _fonts_cache is not None:
        return _fonts_cache
    if (_register_ttf("NotoSans", _repo_font("NotoSans-Regular.ttf"))
            and _register_ttf("NotoSans-Bold", _repo_font("NotoSans-Bold.ttf"))):
        _fonts_cache = ("NotoSans", "NotoSans-Bold")
    elif _register_ttf("DejaVuSans", _FONT_REGULAR_TTF):
        bold = ("DejaVuSans-Bold"
                if _register_ttf("DejaVuSans-Bold", _FONT_BOLD_TTF) else "DejaVuSans")
        _fonts_cache = ("DejaVuSans", bold)
    else:
        _fonts_cache = ("Helvetica", "Helvetica-Bold")
    return _fonts_cache


def _resolve_arabic_font() -> str | None:
    """Registered Arabic-capable font name, or None (sticker degrades to EN/ES)."""
    global _ar_font_cache
    if _ar_font_cache is not False:
        return _ar_font_cache
    _ar_font_cache = (
        "NotoNaskhArabic"
        if _register_ttf("NotoNaskhArabic", _repo_font("NotoNaskhArabic-Regular.ttf"))
        else None
    )
    return _ar_font_cache

_ar_bold_cache: str | None | bool = False


def _resolve_arabic_bold_font() -> str | None:
    """[His goal of 2026-10-06, item 6 (transcribed at a9ac953): "Approve Noto Naskh Arabic Bold (SIL OFL, from
    google/fonts, licence and provenance recorded) for Arabic headings; no outline bolding."] The registered Bold, or
    None where its file is missing (docs/fonts/NotoNaskhArabic-Bold.provenance.json says where it came from)."""
    global _ar_bold_cache
    if _ar_bold_cache is not False:
        return _ar_bold_cache
    _ar_bold_cache = ("NotoNaskhArabic-Bold"
                      if _register_ttf("NotoNaskhArabic-Bold", _repo_font("NotoNaskhArabic-Bold.ttf")) else None)
    return _ar_bold_cache


# --- the production sheet's layout (mm) -------------------------------------------------------------------------------
_MARGIN = 16.0            # page edge → registration-mark band
_DIM_GUTTER_L = 17.0      # reserved left of bleed for the height dimension
_DIM_GUTTER_B = 16.0      # reserved below bleed for the width dimension
_DIM_OFFSET = 8.0         # cut edge → dimension line
_TITLE_H = 44.0           # title block height
_GAP = 8.0               # title block → dieline area
_MIN_PAGE_W = 210.0       # never narrower than A4 (keeps the title block legible)

# stroke weights (points)
_LW_CUT = 0.5
_LW_CREASE = 0.4
_LW_GUIDE = 0.35
_LW_DIM = 0.4


def _stadium_points(cx, cy, width, height, seg=18):
    """Polyline samples of a stadium (matches engine._stadium_polygon)."""
    r = height / 2.0
    if width < height:
        width = height
    half = (width - height) / 2.0
    pts = [(cx - half, cy - r), (cx + half, cy - r)]
    for i in range(1, seg + 1):
        a = math.radians(-90 + 180 * i / seg)
        pts.append((cx + half + r * math.cos(a), cy + r * math.sin(a)))
    pts.append((cx - half, cy + r))
    for i in range(1, seg + 1):
        a = math.radians(90 + 180 * i / seg)
        pts.append((cx - half + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _fmt(v):
    return f"{v:g}"


def write_carton_pdf(
    coords: DielineCoordinates,
    job_id: str,
    *,
    product_name: str = "",
    product_type: str = "",
    bleed_mm: float = 3.0,
    safe_margin_mm: float = 4.0,
    glue_tab_mm: float = 10.0,
    board_thickness_mm: float | None = None,
    notes: str = "",
    output_dir: str = "exports",
) -> str:
    """Render the carton's CMYK production PDF to ``{output_dir}/{job_id}_production.pdf`` and return its path.

    ``output_dir`` should be an ABSOLUTE path in production code (Milestone 10.1: exporters take explicit output paths —
    never rely on the process CWD). The relative default exists only for the pure-function test suite.

    [The clean-up of 2026-10-04 (E2), approved by the owner: the RGB artwork underlay of 2026-07-07 (full design on the
    front, motif on every other surface, the sticker on the back) is removed — no caller had passed it a picture since
    the owner's finding on design 119.]
    """
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{job_id}_production.pdf")

    if board_thickness_mm is None:
        board_thickness_mm = coords.board_thickness_mm

    # --- geometry bounds (mm) ------------------------------------------------------------------------------------------
    bminx, bminy, bmaxx, bmaxy = coords.bleed_polygon.bounds
    cminx, cminy, cmaxx, cmaxy = coords.cut_polygon.bounds
    bleed_w = bmaxx - bminx
    bleed_h = bmaxy - bminy

    draw_area_w = _DIM_GUTTER_L + bleed_w
    draw_area_h = bleed_h + _DIM_GUTTER_B

    page_w = max(_MIN_PAGE_W, _MARGIN * 2 + draw_area_w)
    page_h = _MARGIN * 2 + _TITLE_H + _GAP + draw_area_h

    # horizontal: centre the draw area; bleed sits a left-gutter in from there
    region_left = (page_w - draw_area_w) / 2.0
    ox = region_left + _DIM_GUTTER_L          # page-from-left mm of dieline x=bminx
    oy = _MARGIN + _TITLE_H + _GAP + _DIM_GUTTER_B  # page-from-bottom mm of dieline y=bmaxy

    def TX(x):
        return (ox + (x - bminx)) * mm

    def TY(y):
        # flip: dieline Y grows downward, PDF Y grows upward
        return (oy + (bmaxy - y)) * mm

    c = canvas.Canvas(out_path, pagesize=(page_w * mm, page_h * mm), initialFontName=_resolve_fonts()[0])
    c.setTitle(f"{job_id} — production dieline")
    c.setSubject("CMYK prepress dieline (CutContour + Crease separations)")
    c.setCreator("bbrose-design-os / dielines")
    c.setAuthor("BBROSE Design OS")

    _draw_registration(c, page_w, page_h)
    _draw_geometry(c, coords, TX, TY)
    begin(c, "DIMENSIONS")
    _draw_dimensions(c, coords, TX, TY, cminx, cminy, cmaxx, cmaxy)
    end(c)
    _draw_title_block(
        c, page_w, job_id, coords,
        product_name=product_name, product_type=product_type,
        bleed_mm=bleed_mm, safe_margin_mm=safe_margin_mm,
        glue_tab_mm=glue_tab_mm, board_thickness_mm=board_thickness_mm,
    )

    # Milestone 9.5: real prepress page boxes so imposition software finds the actual trim/bleed geometry. TrimBox =
    # cut-polygon bounds, BleedBox = bleed-polygon bounds. TY flips the y axis (dieline y grows downward), so the
    # dieline's max-y maps to the page's lower edge.
    c.setTrimBox((TX(cminx), TY(cmaxy), TX(cmaxx), TY(cminy)))
    c.setBleedBox((TX(bminx), TY(bmaxy), TX(bmaxx), TY(bminy)))

    c.showPage()
    c.save()
    # [his final goal, 2026-10-05, B2] its layers named, the guides never printed
    apply_layers(out_path, ("CUT", "CREASE", "GLUE", "BLEED", "SAFE", "DIMENSIONS"))

    # PDF/X OutputIntent (Phase 2A-6): reportlab cannot attach one, so the finished file is post-processed when the print
    # shop's ICC profile is configured. Without it the file is unchanged and the Gate-2 validator reports
    # MISSING_OUTPUT_INTENT — never a guessed colour space.
    try:
        from apps.dielines.exporters.output_intent import (
            PREVIEW_ONLY_NO_OUTPUT_INTENT,
            attach_output_intent,
        )
        attached, identity = attach_output_intent(out_path)
        if not attached:
            logger.info("%s — %s: %s", PREVIEW_ONLY_NO_OUTPUT_INTENT,
                        identity.validation_result, identity.detail)
    except Exception:  # noqa: BLE001 — never fail a valid plate file
        logger.exception("OutputIntent post-processing failed")
    return out_path


# --- the production sheet's drawing ------------------------------------------------------------------------------------

def _poly_path(c, poly, TX, TY):
    p = c.beginPath()
    rings = [list(poly.exterior.coords)] + [list(r.coords) for r in poly.interiors]
    for ring in rings:
        if not ring:
            continue
        x0, y0 = ring[0]
        p.moveTo(TX(x0), TY(y0))
        for x, y in ring[1:]:
            p.lineTo(TX(x), TY(y))
        p.close()
    c.drawPath(p, stroke=1, fill=0)


def _primitive_path(c, prims, TX, TY):
    p = c.beginPath()
    x0, y0 = prims[0].p0
    p.moveTo(TX(x0), TY(y0))
    for seg in prims:
        if isinstance(seg, LineSeg):
            x, y = seg.p1
            p.lineTo(TX(x), TY(y))
        elif isinstance(seg, CubicSeg):
            p.curveTo(
                TX(seg.c1[0]), TY(seg.c1[1]),
                TX(seg.c2[0]), TY(seg.c2[1]),
                TX(seg.p1[0]), TY(seg.p1[1]),
            )
    p.close()
    c.drawPath(p, stroke=1, fill=0)


def _polyline(c, pts, TX, TY, close=True):
    p = c.beginPath()
    x0, y0 = pts[0]
    p.moveTo(TX(x0), TY(y0))
    for x, y in pts[1:]:
        p.lineTo(TX(x), TY(y))
    if close:
        p.close()
    c.drawPath(p, stroke=1, fill=0)


def _draw_geometry(c, coords, TX, TY):
    """[His final goal, 2026-10-05, B2: "A PRINT-READY DIELINE ... Each on its own named layer ... It must go to a
    printer without being edited."] Each part on its named layer: the bleed and the safe area as guides that never
    print; the glue area marked; every fold on the Crease plate; the cut on the CutContour plate as the die's ONE
    outline — its holes and its open slits — never a component's own edge, which ran a cut along every flap hinge."""
    begin(c, "BLEED")
    c.setStrokeColor(BLEED)
    c.setLineWidth(_LW_GUIDE)
    c.setDash([2.2 * mm, 1.6 * mm])
    _poly_path(c, coords.bleed_polygon, TX, TY)
    end(c)

    begin(c, "SAFE")
    c.setStrokeColor(SAFE)
    c.setLineWidth(_LW_GUIDE)
    c.setDash([1.4 * mm, 1.4 * mm])
    _poly_path(c, coords.safe_polygon, TX, TY)
    end(c)

    tab = getattr(coords, "glue_tab_polygon", None)
    if tab is not None:
        begin(c, "GLUE")
        c.setStrokeColor(SAFE)
        c.setLineWidth(_LW_GUIDE)
        c.setDash([0.8 * mm, 0.8 * mm])
        _poly_path(c, tab, TX, TY)
        gx0, gy0, gx1, gy1 = tab.bounds
        c.saveState()
        c.setFillColor(SAFE)
        c.setFont(_resolve_fonts()[0], 5)
        c.translate(TX((gx0 + gx1) / 2.0) + 1.5, TY((gy0 + gy1) / 2.0))
        c.rotate(90)
        c.drawCentredString(0, 0, "GLUE")
        c.restoreState()
        end(c)

    begin(c, "CREASE")
    c.setStrokeColor(CREASE)
    # [his second goal of 2026-10-06, item 2: the trade's rule E1] the die's lines overprint the artwork under them
    c.setStrokeOverprint(True)
    c.setLineWidth(_LW_CREASE)
    c.setDash([3.0 * mm, 1.6 * mm])
    for x1, y1, x2, y2 in coords.fold_lines:
        c.line(TX(x1), TY(y1), TX(x2), TY(y2))
    end(c)

    begin(c, "CUT")
    c.setStrokeColor(CUT)
    c.setStrokeOverprint(True)
    c.setLineWidth(_LW_CUT)
    c.setDash()
    _poly_path(c, coords.cut_polygon, TX, TY)
    # Open cut segments (DECISION-020 tuck-base entry slits; the tuck folds' lock slits) on the CutContour plate — cut
    # lines that interrupt a crease.
    for sx1, sy1, sx2, sy2 in coords.slit_lines:
        c.line(TX(sx1), TY(sy1), TX(sx2), TY(sy2))
    end(c)


def _reg_mark(c, cx, cy, r=4.0 * mm):
    c.setStrokeColor(REG)
    c.setLineWidth(0.3)
    c.setDash()
    c.circle(cx, cy, r * 0.55, stroke=1, fill=0)
    c.line(cx - r, cy, cx + r, cy)
    c.line(cx, cy - r, cx, cy + r)


def _draw_registration(c, page_w, page_h):
    inset = _MARGIN * 0.5 * mm
    for cx, cy in (
        (inset, inset),
        (page_w * mm - inset, inset),
        (inset, page_h * mm - inset),
        (page_w * mm - inset, page_h * mm - inset),
    ):
        _reg_mark(c, cx, cy)


def _arrow(c, tipx, tipy, dirx, diry, color, size=2.4 * mm):
    bx = tipx - dirx * size
    by = tipy - diry * size
    px, py = -diry, dirx
    half = size * 0.42
    p = c.beginPath()
    p.moveTo(tipx, tipy)
    p.lineTo(bx + px * half, by + py * half)
    p.lineTo(bx - px * half, by - py * half)
    p.close()
    c.setFillColor(color)
    c.drawPath(p, stroke=0, fill=1)


def _draw_dimensions(c, coords, TX, TY, cminx, cminy, cmaxx, cmaxy):
    f_reg, _ = _resolve_fonts()
    c.setDash()
    left, right = TX(cminx), TX(cmaxx)
    top, bottom = TY(cminy), TY(cmaxy)   # top is higher on page, bottom lower

    # --- overall flat WIDTH (below the cut) ---
    dim_y = bottom - _DIM_OFFSET * mm
    c.setStrokeColor(INK)
    c.setLineWidth(_LW_DIM)
    c.line(left, bottom, left, dim_y - 1.5 * mm)     # left witness
    c.line(right, bottom, right, dim_y - 1.5 * mm)   # right witness
    c.line(left, dim_y, right, dim_y)
    _arrow(c, left, dim_y, -1, 0, INK)
    _arrow(c, right, dim_y, 1, 0, INK)
    c.setFont(f_reg, 7.5)
    c.setFillColor(INK)
    c.drawCentredString((left + right) / 2.0, dim_y - 3.4 * mm,
                        f"flat width  {_fmt(coords.flat_width_mm)} mm")

    # --- overall flat HEIGHT (left of the cut) ---
    dim_x = left - _DIM_OFFSET * mm
    c.line(left, top, dim_x + 1.5 * mm, top)         # top witness
    c.line(left, bottom, dim_x + 1.5 * mm, bottom)   # bottom witness
    c.line(dim_x, top, dim_x, bottom)
    _arrow(c, dim_x, top, 0, 1, INK)
    _arrow(c, dim_x, bottom, 0, -1, INK)
    c.saveState()
    c.translate(dim_x - 2.6 * mm, (top + bottom) / 2.0)
    c.rotate(90)
    c.drawCentredString(0, 0, f"flat height  {_fmt(coords.flat_height_mm)} mm")
    c.restoreState()


def _draw_title_block(
    c, page_w, job_id, coords, *,
    product_name, product_type, bleed_mm, safe_margin_mm,
    glue_tab_mm, board_thickness_mm,
):
    f_reg, f_bold = _resolve_fonts()
    x0 = _MARGIN * mm
    y0 = _MARGIN * mm
    x1 = (page_w - _MARGIN) * mm
    y1 = (_MARGIN + _TITLE_H) * mm
    midx = (x0 + x1) / 2.0

    c.setStrokeColor(INK)
    c.setLineWidth(0.6)
    c.setDash()
    c.rect(x0, y0, x1 - x0, y1 - y0, stroke=1, fill=0)
    c.line(midx, y0, midx, y1)

    W, D, H = coords.dimensions.manufacture
    iw, idp, ih = coords.dimensions.inner
    ow, od, oh = coords.dimensions.outer

    # left column — job identity
    lx = x0 + 5 * mm
    ty = y1 - 8 * mm
    c.setFillColor(INK)
    c.setFont(f_bold, 10)
    c.drawString(lx, ty, (product_name or "Untitled carton")[:46])
    c.setFont(f_reg, 7.5)
    derived = coords.derived or {}
    structure = derived.get("structure_type", "straight_tuck_end_carton")
    # [his second goal of 2026-10-06, item 2] a die drawn to the trade's rules names its style by its ECMA code, and
    # says its grain and the side shown (TRADE_RULES.md R1, E3)
    lines = [
        f"Type: {product_type or 'n/a'}",
        f"Template: {derived.get('style_words', '').split(':')[0] or structure.replace('_', ' ').title()}",
        f"Job ID: {job_id}",
        f"Date: {date.today().isoformat()}    Scale: 1:1",
        f"Units: mm    Board: {_fmt(board_thickness_mm)} mm",
    ]
    for i, ln in enumerate(lines):
        c.drawString(lx, ty - (5.6 * mm) * (i + 1), ln)

    # Hardening 2026-07-04: provisional styles carry an unmissable warning on the production sheet itself — the last
    # line of defence before a die order is placed from unmeasured geometry.
    if derived.get("provisional"):
        c.setFillColorRGB(0.75, 0.0, 0.0)
        c.setFont(f_bold, 8)
        c.drawString(
            lx, ty - (5.6 * mm) * (len(lines) + 1),
            "PROVISIONAL GEOMETRY — TEST-FOLD A SAMPLE BEFORE PRODUCTION",
        )
        c.setFillColor(INK)
        c.setFont(f_reg, 7.5)

    # right column — engineering spec table
    rx = midx + 5 * mm
    ry = y1 - 7 * mm
    c.setFont(f_bold, 8)
    c.drawString(rx, ry, "Specification")
    c.setFont(f_reg, 7.5)
    inside = derived.get("dimension_semantics") == "inside"
    spec = [
        ("Creases (W×D×H)" if inside else "Manufacture (W×D×H)", f"{_fmt(W)} × {_fmt(D)} × {_fmt(H)}"),
        ("Inside (W×D×H)" if inside else "Inner (W×D×H)", f"{_fmt(iw)} × {_fmt(idp)} × {_fmt(ih)}"),
        ("Outer (W×D×H)", f"{_fmt(ow)} × {_fmt(od)} × {_fmt(oh)}"),
        ("Flat size (W×H)", f"{_fmt(coords.flat_width_mm)} × {_fmt(coords.flat_height_mm)}"),
        ("Bleed / Safe", f"{_fmt(bleed_mm)} / {_fmt(safe_margin_mm)}"),
        ("Glue tab", f"{_fmt(glue_tab_mm)}"),
    ]
    if inside:
        spec += [("Grain", "parallel to the height (confirm)"), ("Side shown", "print side")]
    # Milestone 9.5: surface engine geometry notes (dust-flap clamp, slit reduction, thickness compensation) on the
    # production sheet so the die house sees any deviation from nominal ratios.
    derived_notes = list((coords.derived or {}).get("notes") or [])
    if derived_notes:
        summary = "; ".join(n.split(" (")[0] for n in derived_notes)
        spec.append(("Geometry notes", summary[:52]))
    # the rows fill the block and never pass its foot (3 mm clear): 4.9 mm apart, closer where there are more of them
    pitch = min(4.9, (_TITLE_H - 7.0 - 3.0) / max(1, len(spec)))
    for i, (label, val) in enumerate(spec):
        yy = ry - (pitch * mm) * (i + 1)
        c.drawString(rx, yy, label)
        c.drawRightString(x1 - 5 * mm, yy, val)

    # legend strip along the bottom of the left column
    _draw_legend(c, lx, y0 + 3.5 * mm, avail=midx - lx - 3 * mm)


def _draw_legend(c, x, y, avail=None):
    """The line legend along the foot of the title block's left column. [His second goal of 2026-10-06, item 2: "no
    room for mistakes"] it stays inside its column (``avail`` points wide): its samples and gaps closer where the column
    is narrow, its words smaller only if that is not enough — its last word ran over the column's divide."""
    f_reg, _ = _resolve_fonts()
    items = [
        (CUT, "CutContour (cut)"),
        (CREASE, "Crease (fold)"),
        (BLEED, "Bleed"),
        (SAFE, "Safe"),
    ]
    size, sample, lead, gap = 6.5, 6 * mm, 7 * mm, 6 * mm

    def width(size, sample, lead, gap):
        return sum(lead + c.stringWidth(label, f_reg, size) for _c, label in items) + gap * (len(items) - 1)
    if avail is not None and width(size, sample, lead, gap) > avail:
        sample, lead, gap = 4 * mm, 5 * mm, 3 * mm
        while width(size, sample, lead, gap) > avail and size > 5.0:
            size = round(size - 0.25, 2)
    c.setFont(f_reg, size)
    cx = x
    for color, label in items:
        c.setStrokeColor(color)
        c.setLineWidth(1.2)
        c.setDash()
        c.line(cx, y, cx + sample, y)
        c.setFillColor(INK)
        c.drawString(cx + lead, y - 1.6, label)
        cx += lead + c.stringWidth(label, f_reg, size) + gap


# --- the carton's print SVG (from svg_exporter) ---------------------------------------------------------------------
#
# Four and only four layer groups, in this order: g#bleed (grey dashed, offset outline, #8C8C8C), g#cut-lines (magenta
# solid, the full cut outline, #EC008C), g#fold-lines (cyan dashed, every crease, #00AEEF), g#safe-area (light grey
# short-dashed, inward inset, #B3B3B3). [His second goal of 2026-10-06, item 2: "TOP-TIER DIELINES".] The colours are
# the die plates' own — the knife's CutContour (magenta) and the creasing rules' Crease (cyan), as the production PDF,
# the design .ai and the native .ai draw them; the guides grey, as the production PDF draws them. No colour is a trade
# standard (apps/dielines/docs/TRADE_RULES.md E2: printers' schemes differ); what is universal is a solid cut and a
# dashed crease. No text, no labels, no legend: designers add typography in Illustrator.

def _polygon_to_d(
    poly: Polygon, dx: float = 0.0, dy: float = 0.0,
    include_interiors: bool = True,
) -> str:
    """Convert a shapely.Polygon to an SVG path `d`, translating by (dx, dy).

    When `include_interiors=False`, only the exterior ring is emitted — used for component polygons whose interior holes
    are drawn separately as stadium paths with real SVG `A` (elliptical-arc) commands.
    """
    parts: list[str] = []
    rings = [list(poly.exterior.coords)]
    if include_interiors:
        rings += [list(r.coords) for r in poly.interiors]
    for ring in rings:
        if not ring:
            continue
        x0, y0 = ring[0]
        parts.append(f"M {x0 + dx:.4f} {y0 + dy:.4f}")
        for x, y in ring[1:]:
            parts.append(f"L {x + dx:.4f} {y + dy:.4f}")
        parts.append("Z")
    return " ".join(parts)


def _stadium_to_d(
    cx: float, cy: float, width: float, height: float,
    dx: float = 0.0, dy: float = 0.0,
) -> str:
    """SVG path for a stadium using `A` (elliptical-arc) commands.

    `width` is the total horizontal extent (long axis). The two semicircular ends have radius `height / 2`.
    """
    r = height / 2.0
    half = (width - height) / 2.0
    cx += dx
    cy += dy
    x_left  = cx - half
    x_right = cx + half
    y_top    = cy - r
    y_bottom = cy + r
    # Start at top-left of the straight, go right along top, arc down the right end, go left along bottom, arc back up
    # the left end.
    return (
        f"M {x_left:.4f} {y_top:.4f} "
        f"L {x_right:.4f} {y_top:.4f} "
        f"A {r:.4f} {r:.4f} 0 0 1 {x_right:.4f} {y_bottom:.4f} "
        f"L {x_left:.4f} {y_bottom:.4f} "
        f"A {r:.4f} {r:.4f} 0 0 1 {x_left:.4f} {y_top:.4f} Z"
    )


_STROKE = {
    "cut":   0.5,
    "fold":  0.25,
    "bleed": 0.25,
    "safe":  0.25,
}

_PAGE_MARGIN_MM = 1.0

_LAYER_LABELS = {
    "bleed": "Bleed",
    "cut-lines": "Cut Lines",
    "fold-lines": "Fold Lines",
    "safe-area": "Safe Area",
}


def write_carton_svg(
    coords: DielineCoordinates, job_id: str, output_dir: str = "exports",
) -> str:
    """Render the carton's print SVG, write it to ``output_dir/{job_id}.svg`` and return it.

    ``output_dir`` should be an ABSOLUTE path in production code (Milestone 10.1: exporters take explicit output paths —
    never rely on the process CWD). The relative default exists only for the pure-function test suite.
    """
    # Page/artboard bounds must include the full bleed outline. The cut-line geometry still emits in absolute contract
    # coordinates; only the viewBox is expanded so the bleed is not clipped by the SVG canvas.
    min_x, min_y, max_x, max_y = coords.bleed_polygon.bounds
    view_x = min_x - _PAGE_MARGIN_MM
    view_y = min_y - _PAGE_MARGIN_MM
    view_w = (max_x - min_x) + 2 * _PAGE_MARGIN_MM
    view_h = (max_y - min_y) + 2 * _PAGE_MARGIN_MM
    dx = dy = 0.0

    dwg = svgwrite.Drawing(
        filename=os.path.join(output_dir, f"{job_id}.svg"),
        size=(f"{view_w:.4f}mm", f"{view_h:.4f}mm"),
        viewBox=f"{view_x:.4f} {view_y:.4f} {view_w:.4f} {view_h:.4f}",
        profile="full",
        debug=False,
    )

    dwg.attribs["xmlns:inkscape"] = "http://www.inkscape.org/namespaces/inkscape"
    dwg.attribs["xmlns:sodipodi"] = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd"
    dwg.attribs["xmlns:xlink"] = "http://www.w3.org/1999/xlink"
    dwg.attribs["shape-rendering"] = "crispEdges"

    # --- bleed (grey dashed) -----------------------------------------------------------------------------------------
    g_bleed = dwg.g(id="bleed", fill="none",
                    stroke="#8C8C8C", stroke_width=_STROKE["bleed"],
                    stroke_dasharray="3 2")
    g_bleed.attribs["inkscape:label"] = _LAYER_LABELS["bleed"]
    g_bleed.attribs["vector-effect"] = "non-scaling-stroke"
    g_bleed.add(dwg.path(d=_polygon_to_d(coords.bleed_polygon, dx, dy)))
    dwg.add(g_bleed)

    # --- cut lines (magenta solid: the CutContour plate) ---------------------------------------------------------------
    g_cut = dwg.g(id="cut-lines", fill="none",
                  stroke="#EC008C", stroke_width=_STROKE["cut"])
    g_cut.attribs["inkscape:label"] = _LAYER_LABELS["cut-lines"]
    g_cut.attribs["vector-effect"] = "non-scaling-stroke"
    # Each carton component as its own closed <path>; interiors (friction slits, lock slot) are drawn separately below
    # with real arc commands for clean prepress geometry.
    for component_id, poly in coords.components:
        primitives = coords.component_paths.get(component_id)
        if primitives:
            d = path_to_svg_d(primitives, dx, dy)
        else:
            d = _polygon_to_d(poly, dx, dy, include_interiors=False)
        g_cut.add(dwg.path(id=component_id, d=d))
    # Stadium cutouts (friction-lock slits + auto-bottom lock slot).
    for slot_id, cx, cy, sw, sh in coords.stadium_cutouts:
        g_cut.add(dwg.path(
            id=slot_id,
            d=_stadium_to_d(cx, cy, sw, sh, dx, dy),
        ))
    # Open cut segments (DECISION-020 tuck-base entry slits): cut lines that interrupt a crease, drawn on the cut layer
    # as open paths.
    for i, (sx1, sy1, sx2, sy2) in enumerate(coords.slit_lines):
        g_cut.add(dwg.line(id=f"entry-slit-{i}",
                           start=(sx1 + dx, sy1 + dy), end=(sx2 + dx, sy2 + dy)))
    dwg.add(g_cut)

    # --- fold (crease) lines (cyan dashed: the Crease plate) -----------------------------------------------------------
    g_fold = dwg.g(id="fold-lines", fill="none",
                   stroke="#00AEEF", stroke_width=_STROKE["fold"],
                   stroke_dasharray="5 2")
    g_fold.attribs["inkscape:label"] = _LAYER_LABELS["fold-lines"]
    g_fold.attribs["vector-effect"] = "non-scaling-stroke"
    for x1, y1, x2, y2 in coords.fold_lines:
        g_fold.add(dwg.line(start=(x1 + dx, y1 + dy), end=(x2 + dx, y2 + dy)))
    dwg.add(g_fold)

    # --- safe area (light grey short-dashed) ---------------------------------------------------------------------------
    g_safe = dwg.g(id="safe-area", fill="none",
                   stroke="#B3B3B3", stroke_width=_STROKE["safe"],
                   stroke_dasharray="2 2")
    g_safe.attribs["inkscape:label"] = _LAYER_LABELS["safe-area"]
    g_safe.attribs["vector-effect"] = "non-scaling-stroke"
    g_safe.add(dwg.path(d=_polygon_to_d(coords.safe_polygon, dx, dy)))
    dwg.add(g_safe)

    svg_string = dwg.tostring()

    header = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN"\n'
        '  "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n'
    )
    full_svg = header + svg_string
    write_svg(full_svg, job_id, output_dir)
    return full_svg


def write_svg(svg_string: str, job_id: str, output_dir: str = "exports") -> str:
    path = os.path.join(output_dir, f"{job_id}.svg")
    os.makedirs(output_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg_string)
    return path


# --- the carton's .ai (from ai_exporter) --------------------------------------------------------------------------------

def _svg_metadata_keyword(svg_string: str) -> str:
    encoded = base64.b64encode(svg_string.encode("utf-8")).decode("ascii")
    return f"svg_source_base64:{encoded}"


def _export_with_reportlab(svg_string: str, output_path: str, job_id: str) -> None:
    from reportlab.graphics import renderPDF
    from svglib.svglib import svg2rlg

    output_dir = os.path.dirname(output_path) or "."
    with tempfile.NamedTemporaryFile(
        "w", suffix=".svg", encoding="utf-8", dir=output_dir, delete=False,
    ) as tmp:
        tmp.write(svg_string)
        tmp_path = tmp.name

    try:
        drawing = svg2rlg(tmp_path)
        if drawing is None:
            raise ValueError("could not parse SVG for AI export")

        pdf = canvas.Canvas(output_path, pagesize=(drawing.width, drawing.height))
        pdf.setTitle(f"{job_id}.ai")
        pdf.setSubject("Illustrator-compatible PDF generated from SVG")
        pdf.setCreator("dieline-generator")
        pdf.setKeywords(_svg_metadata_keyword(svg_string))
        renderPDF.draw(drawing, pdf, 0, 0)
        pdf.save()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def carton_ai_from_pdf(
    pdf_path: str, job_id: str, output_dir: str = "exports",
) -> str:
    """Create ``{output_dir}/{job_id}.ai`` from the carton's CMYK production PDF and return its path.

    Milestone 9.5 (audit H6): modern .ai files are PDF-compatible internally, so the correct source for the Illustrator
    deliverable is the CMYK production PDF — it already carries the CutContour/Crease Separation colorants, embedded
    fonts and TrimBox/BleedBox. The SVG round-trip (``carton_ai_from_svg``) produces an RGB preview with no spot plates
    and is used only as a labeled preview-grade fallback when the production PDF could not be built.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)
    output_path = os.path.join(output_dir, f"{job_id}.ai")
    os.makedirs(output_dir, exist_ok=True)
    shutil.copyfile(pdf_path, output_path)
    return output_path


def carton_ai_from_svg(svg_string: str, job_id: str, output_dir: str = "exports") -> str:
    """Convert the carton's SVG to an Illustrator-compatible .ai file and return its path.

    PREVIEW-GRADE ONLY (Milestone 9.5 / audit H6): this path renders the RGB SVG to PDF, so the result has no
    CutContour/Crease spot separations and RGB ink — fine for a designer preview, NOT a factory deliverable. Prefer
    ``carton_ai_from_pdf`` whenever the CMYK production PDF exists; callers using this fallback must label the output as
    preview-grade. CairoSVG is used when native Cairo is available; ReportLab/Svglib is the local fallback where the
    Python package is installed but libcairo is not.
    """
    output_path = os.path.join(output_dir, f"{job_id}.ai")
    os.makedirs(output_dir, exist_ok=True)

    try:
        import cairosvg

        cairosvg.svg2pdf(
            bytestring=svg_string.encode("utf-8"),
            write_to=output_path,
            output_width=None,
            output_height=None,
        )
    except (ImportError, OSError):
        _export_with_reportlab(svg_string, output_path, job_id)

    return output_path


# --- the carton's DXF and CF2: the stand die's encoders on the carton's lines -----------------------------------------

CARTON_SHEET_MARGIN_MM = 10.0


def carton_lines(coords: DielineCoordinates):
    """The bridge: a carton's ``DielineCoordinates`` as the die writer's layers — ``{layer: [polyline]}`` in sheet
    millimetres (y down), the bleed's top-left ``CARTON_SHEET_MARGIN_MM`` in from the sheet's — and the sheet's size.
    CUT: the die's one outline (its rings, holes among them) and its open slits, as the production PDF draws them;
    CREASE: every fold; GLUE: the glue tab; BLEED: the bleed outline. Returns ``(lines, sheet_w, sheet_h)``."""
    bminx, bminy, bmaxx, bmaxy = coords.bleed_polygon.bounds
    dx, dy = CARTON_SHEET_MARGIN_MM - bminx, CARTON_SHEET_MARGIN_MM - bminy

    def ring(points):
        return [(x + dx, y + dy) for x, y in points]

    cut = [ring(coords.cut_polygon.exterior.coords)] + [ring(r.coords) for r in coords.cut_polygon.interiors]
    cut += [ring(((x1, y1), (x2, y2))) for x1, y1, x2, y2 in coords.slit_lines]
    tab = getattr(coords, "glue_tab_polygon", None)
    lines = {"CUT": cut, "CREASE": [ring(((x1, y1), (x2, y2))) for x1, y1, x2, y2 in coords.fold_lines],
             "PERF": [], "GLUE": [ring(tab.exterior.coords)] if tab is not None else [],
             "BLEED": [ring(coords.bleed_polygon.exterior.coords)], "DIMENSIONS": []}
    return lines, (bmaxx - bminx) + 2 * CARTON_SHEET_MARGIN_MM, (bmaxy - bminy) + 2 * CARTON_SHEET_MARGIN_MM


def write_carton_dxf(coords: DielineCoordinates, path) -> dict:
    """The carton's die as the stand's DXF: R12, millimetres, one LINE per segment on its named layer."""
    lines, sheet_w, sheet_h = carton_lines(coords)
    return _write_dxf(lines, sheet_w, sheet_h, path)


def write_carton_cf2(coords: DielineCoordinates, path) -> dict:
    """The carton's die as the stand's CF2: millimetres, one L line per segment, type 1 cut and 2 crease."""
    lines, sheet_w, sheet_h = carton_lines(coords)
    name = ((coords.derived or {}).get("structure_type") or "carton").replace(".", "_")
    return _write_cf2(lines, sheet_w, sheet_h, name, path)
