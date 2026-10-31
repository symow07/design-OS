"""CMYK production / prepress PDF for STE dielines.

This is the *factory-ready* deliverable that the text-free SVG deliberately is
not. Where ``svg_exporter`` emits an RGB Illustrator artboard with no text (the
designer's working file), this sheet is what you hand a die-cut house: a 1:1
CMYK plate with a named **CutContour** spot separation for the knife, a
**Crease** spot for the creasing rules, registration marks, dimensioned
callouts, and a title block.

It is drawn **directly from** ``DielineCoordinates`` with reportlab (already a
dependency) — it does NOT go through SVG, so it never touches the dead
svglib/cairo path. Text is welcome here: it is a production document, not the
print dieline itself.

Output: ``{output_dir}/{job_id}_production.pdf`` (path returned). Production
callers pass an absolute ``output_dir`` (Milestone 10.1 — no CWD pinning);
the relative ``exports`` default exists only for the pure-function tests.

Milestone 9.5 prepress notes:
- Registration marks are drawn in an ``/All`` Separation colorant (the classic
  registration color) so they appear on every plate, including the CutContour
  and Crease die plates — a plain 100/100/100/100 process color would only
  print on the four process plates.
- Text is set in an embedded TrueType face (DejaVu Sans) when available so the
  file has no unembedded-font dependency at the print shop; if the TTF is not
  on this machine we fall back to the built-in Helvetica (one of the 14
  standard PDF fonts every RIP ships).
- TrimBox is set to the cut-polygon bounds and BleedBox to the bleed-polygon
  bounds, so imposition software picks up the real trim/bleed geometry.
- KNOWN GAP (documented, not fixed here): this is not a full PDF/X file —
  reportlab's public canvas API has no way to attach an ICC OutputIntent, so
  we cannot claim PDF/X-1a/PDF/X-4 conformance. All other PDF/X-style
  requirements we can meet (CMYK-only ink, embedded fonts, TrimBox/BleedBox,
  named spot separations) are met.
"""
from __future__ import annotations

import logging
import math
import os
from datetime import date

from reportlab.lib.colors import CMYKColor, CMYKColorSep
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ..geometry.coordinates import DielineCoordinates
from ..geometry.primitives import CubicSeg, LineSeg

logger = logging.getLogger(__name__)

# --- spot + process colors ------------------------------------------------
# A spot separation turns the color into a PDF Separation colorant — exactly
# what a die-cut house expects to find on its own plate. CutContour (the knife)
# and Crease (the creasing rules) are the two industry-standard die separations.
#
# IMPORTANT: this MUST be CMYKColorSep, not a plain CMYKColor with a spotName.
# reportlab's canvas only routes a colour through PDFDocument.addColor() (which
# writes the real ``[/Separation /CutContour /DeviceCMYK …]`` object) when the
# colour is a CMYKColorSep instance — see _PDFColorSetter._checkSeparation.
# A plain CMYKColor carrying a spotName is silently flattened to process CMYK
# (a ``k``/``K`` operator), so the die plates would never appear. Using the
# Sep class is what makes a die-cutter find CutContour/Crease on their own plate.
CUT = CMYKColorSep(0, 1, 0, 0, spotName="CutContour", density=1)
CREASE = CMYKColorSep(1, 0, 0, 0, spotName="Crease", density=1)
# Bleed + safe are process-gray guides (informational, not a die plate).
BLEED = CMYKColor(0, 0, 0, 0.45)
SAFE = CMYKColor(0, 0, 0, 0.28)
INK = CMYKColor(0, 0, 0, 1)        # body text / dimension lines
# "All separations" — the classic registration colorant (prints on every
# plate). Milestone 9.5: this MUST be a CMYKColorSep with spotName "All", not
# a plain 100/100/100/100 CMYKColor. A process color only reaches the four
# process plates; the /All separation is the PDF registration colorant that
# also lands on the CutContour and Crease die plates, which is what makes the
# marks usable for aligning the die to the printed sheet.
REG = CMYKColorSep(1, 1, 1, 1, spotName="All", density=1)

# --- fonts ------------------------------------------------------------------
# Milestone 9.5: embed a real TrueType face so the PDF carries its own font
# program (print shops reject files with unembedded non-standard fonts).
# 2026-07-07: repo-bundled Noto fonts (static/fonts/, OFL) are preferred so
# every environment ships identical embeddable faces — incl. the Arabic face
# for the trilingual sticker. DejaVu (Linux system TTF) is the next fallback,
# then the built-in Helvetica (standard-14) — graceful degradation, never a
# crash.
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


# --- layout constants (mm) ------------------------------------------------
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


def export_production_pdf(
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
    """Render the CMYK production PDF and return its path.

    ``output_dir`` should be an ABSOLUTE path in production code (Milestone
    10.1: exporters take explicit output paths — never rely on the process
    CWD). The relative default exists only for the pure-function test suite.

    [The clean-up of 2026-10-04 (E2), approved by the owner: the RGB artwork
    underlay of 2026-07-07 (full design on the front, motif on every other
    surface, the sticker on the back) is removed — no caller had passed it a
    picture since the owner's finding on design 119.]
    """
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{job_id}_production.pdf")

    if board_thickness_mm is None:
        board_thickness_mm = coords.board_thickness_mm

    # --- geometry bounds (mm) --------------------------------------------
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

    c = canvas.Canvas(out_path, pagesize=(page_w * mm, page_h * mm))
    c.setTitle(f"{job_id} — production dieline")
    c.setSubject("CMYK prepress dieline (CutContour + Crease separations)")
    c.setCreator("bbrose-design-os / dielines")
    c.setAuthor("BBROSE Design OS")

    _draw_registration(c, page_w, page_h)
    _draw_geometry(c, coords, TX, TY)
    from apps.dielines.exporters import counter_display_files as _layers
    _layers.begin(c, "DIMENSIONS")
    _draw_dimensions(c, coords, TX, TY, cminx, cminy, cmaxx, cmaxy)
    _layers.end(c)
    _draw_title_block(
        c, page_w, job_id, coords,
        product_name=product_name, product_type=product_type,
        bleed_mm=bleed_mm, safe_margin_mm=safe_margin_mm,
        glue_tab_mm=glue_tab_mm, board_thickness_mm=board_thickness_mm,
    )

    # Milestone 9.5: real prepress page boxes so imposition software finds the
    # actual trim/bleed geometry. TrimBox = cut-polygon bounds, BleedBox =
    # bleed-polygon bounds. TY flips the y axis (dieline y grows downward),
    # so the dieline's max-y maps to the page's lower edge.
    c.setTrimBox((TX(cminx), TY(cmaxy), TX(cmaxx), TY(cminy)))
    c.setBleedBox((TX(bminx), TY(bmaxy), TX(bmaxx), TY(bminy)))

    c.showPage()
    c.save()
    # [his final goal, 2026-10-05, B2] its layers named, the guides never printed
    _layers.apply_layers(out_path, ("CUT", "CREASE", "GLUE", "BLEED", "SAFE", "DIMENSIONS"))

    # PDF/X OutputIntent (Phase 2A-6): reportlab cannot attach one, so the
    # finished file is post-processed when the print shop's ICC profile is
    # configured. Without it the file is unchanged and the Gate-2 validator
    # reports MISSING_OUTPUT_INTENT — never a guessed colour space.
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


# --------------------------------------------------------------------------
# drawing helpers
# --------------------------------------------------------------------------

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
    printer without being edited."] Each part on its named layer (``counter_display_files``' layer writer): the bleed and the safe area as guides
    that never print; the glue area marked; every fold on the Crease plate; the cut on the CutContour plate as the die's
    ONE outline — its holes and its open slits — never a component's own edge, which ran a cut along every flap hinge."""
    from apps.dielines.exporters import counter_display_files as _layers
    _layers.begin(c, "BLEED")
    c.setStrokeColor(BLEED)
    c.setLineWidth(_LW_GUIDE)
    c.setDash([2.2 * mm, 1.6 * mm])
    _poly_path(c, coords.bleed_polygon, TX, TY)
    _layers.end(c)

    _layers.begin(c, "SAFE")
    c.setStrokeColor(SAFE)
    c.setLineWidth(_LW_GUIDE)
    c.setDash([1.4 * mm, 1.4 * mm])
    _poly_path(c, coords.safe_polygon, TX, TY)
    _layers.end(c)

    tab = getattr(coords, "glue_tab_polygon", None)
    if tab is not None:
        _layers.begin(c, "GLUE")
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
        _layers.end(c)

    _layers.begin(c, "CREASE")
    c.setStrokeColor(CREASE)
    # [his second goal of 2026-10-06, item 2: the trade's rule E1] the die's lines overprint the artwork under them
    c.setStrokeOverprint(True)
    c.setLineWidth(_LW_CREASE)
    c.setDash([3.0 * mm, 1.6 * mm])
    for x1, y1, x2, y2 in coords.fold_lines:
        c.line(TX(x1), TY(y1), TX(x2), TY(y2))
    _layers.end(c)

    _layers.begin(c, "CUT")
    c.setStrokeColor(CUT)
    c.setStrokeOverprint(True)
    c.setLineWidth(_LW_CUT)
    c.setDash()
    _poly_path(c, coords.cut_polygon, TX, TY)
    # Open cut segments (DECISION-020 tuck-base entry slits; the tuck folds' lock slits) on the CutContour plate — cut
    # lines that interrupt a crease.
    for sx1, sy1, sx2, sy2 in coords.slit_lines:
        c.line(TX(sx1), TY(sy1), TX(sx2), TY(sy2))
    _layers.end(c)


# --- registration marks ---------------------------------------------------

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


# --- dimension callouts ---------------------------------------------------

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


# --- title block ----------------------------------------------------------

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

    # Hardening 2026-07-04: provisional styles carry an unmissable warning on
    # the production sheet itself — the last line of defence before a die
    # order is placed from unmeasured geometry.
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
    # Milestone 9.5: surface engine geometry notes (dust-flap clamp, slit
    # reduction, thickness compensation) on the production sheet so the die
    # house sees any deviation from nominal ratios.
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
