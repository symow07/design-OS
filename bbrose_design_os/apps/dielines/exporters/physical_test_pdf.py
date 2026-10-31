"""100%-scale physical-test PDF (Phase 2A-9 §6).

A printable, exact-scale sheet for folding a real board sample of a
PROVISIONAL structure. This is a diagnostic deliverable, never a production
file: it carries the provisional warnings, a 50 x 50 mm calibration square,
the cut/crease legend, panel names, the glue area, the measured inner
dimensions, the board-thickness note, the template identity and the
deterministic geometry hash.

Scale discipline: the page is sized to the geometry so nothing is scaled to
fit; the calibration square proves at the printer that no "fit to page"
shrink happened.
"""
from __future__ import annotations

import os

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

_MARGIN_MM = 12.0
_LEGEND_W_MM = 78.0
_CAL_MM = 50.0

_CUT = (0.0, 0.0, 1.0)      # blue, matching the reference legend
_CREASE = (1.0, 0.0, 0.0)   # red
_BLEED = (0.0, 0.65, 0.2)   # green
_GLUE_FILL = (0.88, 0.88, 0.88)

_ASSEMBLY = (
    "1. Cut along every solid blue line (incl. the short slits at the "
    "tuck folds).",
    "2. Score and fold every dashed red line.",
    "3. Fold the side panels and glue the flap behind the free back edge.",
    "4. Fold both dust-flap pairs in, then close each tuck: the curved "
    "shoulders should slide in and the 2t ears lock in the slits.",
    "5. Record the result in the physical-validation record "
    "(FIT_PASS / bounded failure codes) with measured corrections in mm.",
)


def export_physical_test_pdf(
    coords, job_id: str, *, template_key: str, geometry_hash: str,
    output_dir: str = "exports", notes: str = "",
) -> str:
    """Render the physical-test sheet; returns the file path."""
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir,
                            f"{job_id}_PROVISIONAL_physical_test.pdf")

    bminx, bminy, bmaxx, bmaxy = coords.bleed_polygon.bounds
    geom_w, geom_h = bmaxx - bminx, bmaxy - bminy
    page_w = _MARGIN_MM * 2 + geom_w + _LEGEND_W_MM + 8.0
    page_h = _MARGIN_MM * 2 + max(geom_h, _CAL_MM + 150.0) + 14.0

    ox = _MARGIN_MM
    oy = page_h - _MARGIN_MM - 10.0        # top of the geometry block

    def TX(x):
        return (ox + (x - bminx)) * mm

    def TY(y):
        return (oy - (y - bminy)) * mm     # dieline y-down -> PDF y-up

    c = canvas.Canvas(out_path, pagesize=(page_w * mm, page_h * mm))
    c.setTitle(f"{job_id} — PROVISIONAL physical test sheet (100% scale)")
    c.setCreator("bbrose-design-os / dielines (Phase 2A-9)")

    # --- banner --------------------------------------------------------
    c.setFillColorRGB(0.75, 0.0, 0.0)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(_MARGIN_MM * mm, (page_h - 8.0) * mm,
                 "PROVISIONAL STRUCTURE — PHYSICAL SAMPLE REQUIRED — "
                 "NOT APPROVED FOR MASS PRODUCTION")

    # --- geometry: bleed, glue fill, cut, creases, slits ----------------
    def draw_ring(ring, color, width_mm, dash=None):
        c.setStrokeColorRGB(*color)
        c.setLineWidth(width_mm * mm)
        c.setDash(dash or [])
        path = c.beginPath()
        pts = list(ring.coords)
        path.moveTo(TX(pts[0][0]), TY(pts[0][1]))
        for x, y in pts[1:]:
            path.lineTo(TX(x), TY(y))
        path.close()
        c.drawPath(path, stroke=1, fill=0)

    # glue area shading beneath the linework
    c.setFillColorRGB(*_GLUE_FILL)
    gp = c.beginPath()
    gpts = list(coords.glue_tab_polygon.exterior.coords)
    gp.moveTo(TX(gpts[0][0]), TY(gpts[0][1]))
    for x, y in gpts[1:]:
        gp.lineTo(TX(x), TY(y))
    gp.close()
    c.drawPath(gp, stroke=0, fill=1)

    draw_ring(coords.bleed_polygon.exterior, _BLEED, 0.2,
              dash=[3.0 * mm, 1.6 * mm])
    draw_ring(coords.cut_polygon.exterior, _CUT, 0.35)
    c.setStrokeColorRGB(*_CUT)
    c.setLineWidth(0.35 * mm)
    c.setDash([])
    for (x1, y1, x2, y2) in coords.slit_lines:
        c.line(TX(x1), TY(y1), TX(x2), TY(y2))
    c.setStrokeColorRGB(*_CREASE)
    c.setLineWidth(0.3 * mm)
    c.setDash([2.2 * mm, 1.4 * mm])
    for (x1, y1, x2, y2) in coords.fold_lines:
        c.line(TX(x1), TY(y1), TX(x2), TY(y2))
    c.setDash([])

    # panel names
    c.setFillColorRGB(0.45, 0.45, 0.45)
    c.setFont("Helvetica", 8)
    for panel in coords.panels:
        cx, cy = panel.center
        c.drawCentredString(TX(cx), TY(cy), panel.name.upper())
    c.setFont("Helvetica", 6)
    gcx, gcy = coords.glue_tab_polygon.centroid.coords[0]
    c.drawCentredString(TX(gcx), TY(gcy) - 3.5 * mm, "(glue area)")

    # --- legend column ---------------------------------------------------
    lx = (_MARGIN_MM + geom_w + 8.0)
    ly = page_h - _MARGIN_MM - 14.0

    def text(line, *, bold=False, size=7.5, gap=3.6, color=(0, 0, 0)):
        nonlocal ly
        c.setFillColorRGB(*color)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(lx * mm, ly * mm, line)
        ly -= gap

    text("PHYSICAL TEST SHEET — PRINT AT 100% SCALE", bold=True, size=9,
         gap=5.0)
    text("Do NOT use 'fit to page' / 'shrink to printable area'.",
         bold=True, color=(0.75, 0, 0))
    text("Verify the calibration square measures exactly "
         f"{_CAL_MM:g} x {_CAL_MM:g} mm before folding.", gap=6.0)

    text("Legend:", bold=True)
    c.setStrokeColorRGB(*_CUT)
    c.setLineWidth(0.35 * mm)
    c.line(lx * mm, (ly + 1) * mm, (lx + 10) * mm, (ly + 1) * mm)
    text("          cut (die knife), incl. tuck-fold slits")
    c.setStrokeColorRGB(*_CREASE)
    c.setDash([2.2 * mm, 1.4 * mm])
    c.line(lx * mm, (ly + 1) * mm, (lx + 10) * mm, (ly + 1) * mm)
    c.setDash([])
    text("          crease / score (fold, never cut)")
    c.setStrokeColorRGB(*_BLEED)
    c.setDash([3.0 * mm, 1.6 * mm])
    c.line(lx * mm, (ly + 1) * mm, (lx + 10) * mm, (ly + 1) * mm)
    c.setDash([])
    text("          bleed contour (ignore for the fold test)", gap=6.0)

    text("Assembly sequence:", bold=True)
    for step in _ASSEMBLY:
        for chunk in _wrap(step, 52):
            text(chunk, size=7, gap=3.2)
    ly -= 2.5

    inner = coords.dimensions.inner
    text("Structure:", bold=True)
    text(f"template: {template_key}", size=7, gap=3.2)
    text(f"geometry hash: {geometry_hash}", size=7, gap=3.2)
    text(f"inner dimensions: {inner[0]:g} x {inner[1]:g} x {inner[2]:g} mm",
         size=7, gap=3.2)
    text(f"board thickness: {coords.board_thickness_mm:g} mm — use "
         "representative stock", size=7, gap=3.2)
    text(f"flat size: {coords.flat_width_mm:g} x {coords.flat_height_mm:g} "
         "mm", size=7, gap=6.0)
    if notes:
        for chunk in _wrap(notes, 52):
            text(chunk, size=7, gap=3.2)

    # --- calibration square ----------------------------------------------
    cal_x, cal_y = lx, _MARGIN_MM + 8.0
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.3 * mm)
    c.rect(cal_x * mm, cal_y * mm, _CAL_MM * mm, _CAL_MM * mm,
           stroke=1, fill=0)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 7)
    c.drawCentredString((cal_x + _CAL_MM / 2) * mm, (cal_y - 4.0) * mm,
                        f"calibration square — must measure {_CAL_MM:g} x "
                        f"{_CAL_MM:g} mm when printed")

    c.showPage()
    c.save()
    return out_path


def _wrap(line: str, width: int) -> list[str]:
    words, out, cur = line.split(), [], ""
    for word in words:
        if len(cur) + len(word) + 1 > width and cur:
            out.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        out.append(cur)
    return out


__all__ = ["export_physical_test_pdf"]
