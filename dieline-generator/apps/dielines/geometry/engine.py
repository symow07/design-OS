# BEFORE MODIFYING ANY GEOMETRY:
# Read docs/geometry_decisions.md AND the coordinate contract below.
# Every coordinate is derived from the contract — no ratios, no angles
# not listed in the contract, no magic numbers.
"""Straight Tuck End (STE) carton — exact coordinate-driven geometry.

Inputs: width W, depth D, height H, glue_tab G, bleed, safe_margin,
board_thickness.

Coordinate system: origin at the far-left glue-tab edge. The body
starts at x1 = G.

ABSOLUTE X (contract):
    x0 = 0                   (glue tab left edge)
    x1 = G                   (fold 1: glue tab / back)
    x2 = G + W               (fold 2: back / side-L)
    x3 = G + W + D           (fold 3: side-L / front)
    x4 = G + W + D + W       (fold 4: front / side-R)
    x5 = G + W + D + W + D   (side-R panel right edge)

ABSOLUTE Y (contract):
    y0 = 0
    y1 = top_tuck_h           (= W × 1.227)
    y2 = top_tuck_h + H
    y3 = top_tuck_h + H + bottom_tuck_h   (= top_tuck_h)
"""
from __future__ import annotations

import math

from shapely.geometry import Polygon
from shapely.ops import unary_union

from .coordinates import DielineCoordinates, DimensionSet
from .panels import Panel
from .primitives import CubicSeg, LineSeg, Primitive, sample_path
from ..validators.schema import DielineInputJSON


# ---------------------------------------------------------------------------
# Guard assertions
# ---------------------------------------------------------------------------

def _assert_ge(name: str, value: float, minimum: float) -> None:
    if value < minimum:
        raise ValueError(
            f"Geometry guard violated: {name} = {value:.4f} mm "
            f"is below the minimum of {minimum:.4f} mm"
        )


# ---------------------------------------------------------------------------
# Bezier sampling (for shoulder curves — kept inside the cut polygon)
# ---------------------------------------------------------------------------

def _cubic_bezier_points(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    segments: int = 24,
    include_start: bool = False,
) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    first = 0 if include_start else 1
    for i in range(first, segments + 1):
        t = i / segments
        u = 1.0 - t
        x = (u * u * u * p0[0]
             + 3 * u * u * t * p1[0]
             + 3 * u * t * t * p2[0]
             + t * t * t * p3[0])
        y = (u * u * u * p0[1]
             + 3 * u * u * t * p1[1]
             + 3 * u * t * t * p2[1]
             + t * t * t * p3[1])
        out.append((x, y))
    return out


def _arc_points(
    cx: float, cy: float, radius: float,
    start_angle_deg: float, end_angle_deg: float,
    segments: int = 24,
) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for i in range(1, segments + 1):
        t = i / segments
        ang = math.radians(start_angle_deg + (end_angle_deg - start_angle_deg) * t)
        pts.append((cx + radius * math.cos(ang), cy + radius * math.sin(ang)))
    return pts


# ---------------------------------------------------------------------------
# Stadium polygon (for friction slit + lock slot)
# ---------------------------------------------------------------------------

def _stadium_polygon(
    *, cx: float, cy: float, width: float, height: float,
    arc_segments: int = 16,
) -> Polygon:
    r = height / 2.0
    if width < height:
        width = height
    half = (width - height) / 2.0
    pts: list[tuple[float, float]] = []
    pts.append((cx - half, cy - r))
    pts.append((cx + half, cy - r))
    pts.extend(_arc_points(
        cx=cx + half, cy=cy, radius=r,
        start_angle_deg=-90, end_angle_deg=90, segments=arc_segments,
    ))
    pts.append((cx - half, cy + r))
    pts.extend(_arc_points(
        cx=cx - half, cy=cy, radius=r,
        start_angle_deg=90, end_angle_deg=270, segments=arc_segments,
    ))
    return Polygon(pts)


# ---------------------------------------------------------------------------
# Top-level engine — coordinate contract only
# ---------------------------------------------------------------------------

# Contract constants
# DECISION-016 (measured from professional AI file):
# Tuck flap height is W-derived (not D-derived). Dust flap is D-derived.
_TUCK_HEIGHT_FACTOR  = 1.227    # tuck total_h = W × 1.227
_TUCK_INSET_FACTOR   = 0.227    # tuck inset   = W × 0.227 (each side)
_TUCK_CURVE_H_FACTOR = 0.218    # tuck shoulder vertical span = W × 0.218
_DUST_HEIGHT_FACTOR  = 0.631    # dust height  = D × 0.631
_DUST_BASE_NOTCH_MM  = 3.0      # fixed 3 mm base-corner notch step
_DUST_TOP_CHAMFER_MM = 6.0      # fixed 6 mm top chamfer each side
_SLIT_WIDTH_FACTOR   = 0.327    # friction slit width = W × 0.327 (provisional; see TODO)
# Cubic-Bezier quarter-arc tangent-length factor. For control points
# placed at (k * leg) along each tangent of a right-angle corner, k =
# 0.55228... produces a near-perfect quarter-ellipse — the standard CAD
# approximation used by Adobe Illustrator's "Convert to Curve" tool for
# rectangle corners. Provisional until the real Pacdora control points
# are measured (see TODO below).
_TUCK_SHOULDER_K     = 0.55228474983
_MIN_SLIT_WIDTH_MM   = 5.0
_SLIT_HEIGHT_MM      = 1.5
_SLIT_FROM_TIP_MM    = 3.0
_GLUE_CORNER_FACTOR  = 0.3
_GLUE_CORNER_CAP_MM  = 4.0

# TODO(DECISION-NNN): _SLIT_WIDTH_FACTOR is provisional. The old form
# `max(5.0, W * 0.545 * 0.6)` collapses to W × 0.327; this needs to be
# re-measured from SLIMMING_CREAM_R-108-A.ai and recorded as a locked
# decision before the engine can claim Pacdora-grade slit proportions.
#
# TODO(DECISION-NNN): _TUCK_SHOULDER_K = 0.5523 is the quarter-arc CAD
# approximation. DECISION-016 specifies tangent *directions* but not
# tangent *lengths*; the real Pacdora control-point offsets from the
# source AI file must be measured and recorded before the shoulder
# curve can be claimed as exactly matching the reference.


def calculate_straight_tuck_end(params: DielineInputJSON) -> DielineCoordinates:
    d = params.dimensions
    pset = params.print_settings
    c = params.construction

    W = d.width_mm
    D = d.depth_mm
    H = d.height_mm
    G = c.glue_tab_mm

    bleed_mm       = pset.bleed_mm
    safe_margin_mm = pset.safe_margin_mm
    board_thickness = c.board_thickness_mm

    # ---- Contract-derived heights (DECISION-016: measured from AI file) ----
    top_tuck_h    = W * _TUCK_HEIGHT_FACTOR
    bottom_tuck_h = W * _TUCK_HEIGHT_FACTOR
    tuck_inset    = W * _TUCK_INSET_FACTOR
    slit_w        = max(_MIN_SLIT_WIDTH_MM, W * _SLIT_WIDTH_FACTOR)
    corner_cut    = min(G * _GLUE_CORNER_FACTOR, _GLUE_CORNER_CAP_MM)

    # ---- Guards ----
    _assert_ge("width_mm",        W,            12.0)
    _assert_ge("depth_mm",        D,            12.0)
    _assert_ge("height_mm",       H,            60.0)
    _assert_ge("top_tuck_h",      top_tuck_h,   12.0)
    _assert_ge("slit_width",      slit_w,        _MIN_SLIT_WIDTH_MM)
    _assert_ge("tuck_inset",      tuck_inset,    1.5)
    if _DUST_TOP_CHAMFER_MM * 2 + 2.0 > D:
        raise ValueError(
            f"dust-flap chamfer {_DUST_TOP_CHAMFER_MM} too large for depth {D}: "
            f"top width would drop below 2 mm"
        )

    # ---- Contract X coordinates ----
    x0 = 0.0
    x1 = G
    x2 = G + W
    x3 = G + W + D
    x4 = G + W + D + W
    x5 = G + W + D + W + D

    # ---- Contract Y coordinates ----
    y0 = 0.0
    y1 = top_tuck_h
    y2 = top_tuck_h + H
    y3 = top_tuck_h + H + bottom_tuck_h

    flat_w = x5 - x0    # = G + 2D + 2W
    flat_h = y3 - y0    # = top_tuck_h + H + bottom_tuck_h

    # ---- Main body (x1..x5, y1..y2) ----
    body_rect = Polygon([(x1, y1), (x5, y1), (x5, y2), (x1, y2)])

    # ---- Glue tab (4-vertex trapezoid) ----
    # Per contract: corners cut on the FAR-LEFT (outer) edge, not at the fold.
    glue_poly = Polygon([
        (x0,              y1 + corner_cut),  # far-left top
        (x1,              y1),                # right top  (at fold)
        (x1,              y2),                # right bottom
        (x0,              y2 - corner_cut),  # far-left bottom
    ])

    # ---- Tuck flaps (bezier shoulders per DECISION-016) ----

    def _quad_bezier_points(
        p0: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
        segments: int = 24,
        include_start: bool = False,
    ) -> list[tuple[float, float]]:
        out: list[tuple[float, float]] = []
        first = 0 if include_start else 1
        for i in range(first, segments + 1):
            t = i / segments
            u = 1.0 - t
            x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
            y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
            out.append((x, y))
        return out

    # DECISION-016: tuck shoulder is a cubic bezier with a vertical tangent
    # at the curve-start point and a horizontal tangent at the flat-top point
    # (the PDF "v" and "y" operators in the source AI file).
    #
    # total_h = W × 1.227   (== top_tuck_h)
    # inset   = W × 0.227   (== tuck_inset)
    # curve_h = W × 0.218   (vertical span of the shoulder)
    curve_h = W * _TUCK_CURVE_H_FACTOR

    # Control-point tangent offsets for the shoulder quarter-arc cubic.
    # Vertical leg = curve_h, horizontal leg = tuck_inset. The cubic
    # leaves the curve start with a vertical tangent (p1 offset along
    # ±y) and arrives at the flat top with a horizontal tangent
    # (p2 offset along ±x). With k ≈ 0.5523 the curve traces a
    # near-perfect quarter-ellipse fitted to the corner.
    k_v = _TUCK_SHOULDER_K * curve_h
    k_h = _TUCK_SHOULDER_K * tuck_inset

    def _tuck_top_path(x_l: float, x_r: float) -> list[Primitive]:
        """Primitive path for a top tuck flap, traversed clockwise.

        Order: base-left → up-the-left-side → left-shoulder cubic →
        (optional flat top) → right-shoulder cubic → down-the-right-side
        → base-right → close (back to base-left).
        """
        top_l = x_l + tuck_inset
        top_r = x_r - tuck_inset
        path: list[Primitive] = []
        path.append(LineSeg((x_l, y1), (x_l, y0 + curve_h)))
        path.append(CubicSeg(
            p0=(x_l,         y0 + curve_h),
            c1=(x_l,         y0 + curve_h - k_v),
            c2=(top_l - k_h, y0),
            p1=(top_l,       y0),
        ))
        if top_r > top_l:
            path.append(LineSeg((top_l, y0), (top_r, y0)))
        path.append(CubicSeg(
            p0=(top_r,       y0),
            c1=(top_r + k_h, y0),
            c2=(x_r,         y0 + curve_h - k_v),
            p1=(x_r,         y0 + curve_h),
        ))
        path.append(LineSeg((x_r, y0 + curve_h), (x_r, y1)))
        path.append(LineSeg((x_r, y1), (x_l, y1)))
        return path

    def _tuck_bot_path(x_l: float, x_r: float) -> list[Primitive]:
        """Mirror of _tuck_top_path across y = (y2 + y3) / 2."""
        top_l = x_l + tuck_inset
        top_r = x_r - tuck_inset
        path: list[Primitive] = []
        path.append(LineSeg((x_l, y2), (x_l, y3 - curve_h)))
        path.append(CubicSeg(
            p0=(x_l,         y3 - curve_h),
            c1=(x_l,         y3 - curve_h + k_v),
            c2=(top_l - k_h, y3),
            p1=(top_l,       y3),
        ))
        if top_r > top_l:
            path.append(LineSeg((top_l, y3), (top_r, y3)))
        path.append(CubicSeg(
            p0=(top_r,       y3),
            c1=(top_r + k_h, y3),
            c2=(x_r,         y3 - curve_h + k_v),
            p1=(x_r,         y3 - curve_h),
        ))
        path.append(LineSeg((x_r, y3 - curve_h), (x_r, y2)))
        path.append(LineSeg((x_r, y2), (x_l, y2)))
        return path

    def _tuck_top(x_l: float, x_r: float) -> Polygon:
        return Polygon(sample_path(_tuck_top_path(x_l, x_r), cubic_segments=20))

    def _tuck_bot(x_l: float, x_r: float) -> Polygon:
        return Polygon(sample_path(_tuck_bot_path(x_l, x_r), cubic_segments=20))

    # Build primitive paths and the matching sampled polygons. The
    # primitive paths are preserved so the SVG exporter can emit real
    # cubic-Bezier C commands; the polygons feed Shapely for the union
    # and bleed-buffer operations downstream.
    tuck_back_top_primitives = _tuck_top_path(x1, x2)
    tuck_front_bot_primitives = _tuck_bot_path(x3, x4)
    tuck_back_top_raw = _tuck_top(x1, x2)
    tuck_front_bot_raw = _tuck_bot(x3, x4)

    # Stadium friction slits (top + bottom front tuck)
    back_cx = (x1 + x2) / 2.0
    front_cx = (x3 + x4) / 2.0
    slit_top_cy = y0 + _SLIT_FROM_TIP_MM + _SLIT_HEIGHT_MM / 2.0
    slit_bot_cy = y3 - _SLIT_FROM_TIP_MM - _SLIT_HEIGHT_MM / 2.0
    slit_top_stadium = _stadium_polygon(
        cx=back_cx, cy=slit_top_cy, width=slit_w, height=_SLIT_HEIGHT_MM,
    )
    slit_bot_stadium = _stadium_polygon(
        cx=front_cx, cy=slit_bot_cy, width=slit_w, height=_SLIT_HEIGHT_MM,
    )
    tuck_back_top = tuck_back_top_raw.difference(slit_top_stadium)
    tuck_front_bot = tuck_front_bot_raw.difference(slit_bot_stadium)
    if not tuck_back_top.is_valid or not tuck_front_bot.is_valid:
        raise ValueError("tuck polygon invalid after stadium-slit cutout")

    # ---- Dust flaps (DECISION-016, measured from AI file) ----
    # 6-vertex shape: 3 mm base-corner notch step, 6 mm top chamfer each side.
    # Height = D × 0.631. Top width = D - 2·top_chamfer.
    dust_h         = D * _DUST_HEIGHT_FACTOR
    base_notch     = _DUST_BASE_NOTCH_MM
    top_chamfer    = _DUST_TOP_CHAMFER_MM

    def _dust_flap(x_l: float, x_r: float, y_base: float, y_tip: float) -> Polygon:
        # y_tip is on the opposite side of y_base relative to the body.
        # Vertical direction from base toward tip:
        sign = 1.0 if y_tip > y_base else -1.0
        # 6 vertices, clockwise starting bottom-right:
        pts = [
            (x_r,                          y_base),                          # outer base-right
            (x_r - base_notch,             y_base + sign * base_notch),     # notch step (right)
            (x_r - top_chamfer,            y_tip),                          # top-right
            (x_l + top_chamfer,            y_tip),                          # top-left
            (x_l + base_notch,             y_base + sign * base_notch),     # notch step (left)
            (x_l,                          y_base),                          # outer base-left
        ]
        return Polygon(pts)

    def _dust_top(x_l: float, x_r: float) -> Polygon:
        return _dust_flap(x_l, x_r, y_base=y1, y_tip=y1 - dust_h)

    def _dust_bot(x_l: float, x_r: float) -> Polygon:
        return _dust_flap(x_l, x_r, y_base=y2, y_tip=y2 + dust_h)

    dust_sl_top = _dust_top(x2, x3)
    dust_sr_top = _dust_top(x4, x5)
    dust_sl_bot = _dust_bot(x2, x3)
    dust_sr_bot = _dust_bot(x4, x5)

    # ---- Union into the full cut polygon ----
    cut_polygon = unary_union([
        body_rect, glue_poly,
        tuck_back_top, tuck_front_bot,
        dust_sl_top, dust_sr_top,
        dust_sl_bot, dust_sr_bot,
    ])
    if cut_polygon.geom_type != "Polygon":
        raise ValueError(
            f"cut_polygon must be a single Polygon, got {cut_polygon.geom_type}"
        )
    if not cut_polygon.is_valid:
        raise ValueError("cut_polygon is invalid after union")

    # ---- Bleed: outward buffer with round joins ----
    bleed_polygon = cut_polygon.buffer(bleed_mm, join_style=1, quad_segs=16)
    if not bleed_polygon.is_valid:
        raise ValueError("bleed_polygon invalid after buffer")

    # ---- Safe area: inner rectangle of body only ----
    safe_polygon = Polygon([
        (x1 + safe_margin_mm, y1 + safe_margin_mm),
        (x5 - safe_margin_mm, y1 + safe_margin_mm),
        (x5 - safe_margin_mm, y2 - safe_margin_mm),
        (x1 + safe_margin_mm, y2 - safe_margin_mm),
    ])

    # ---- Fold lines (4 vertical, 2 horizontal) ----
    fold_lines: list[tuple[float, float, float, float]] = [
        (x1, y1, x1, y2),
        (x2, y1, x2, y2),
        (x3, y1, x3, y2),
        (x4, y1, x4, y2),
        (x1, y1, x5, y1),
        (x1, y2, x5, y2),
    ]

    slit_lines: list[tuple[float, float, float, float]] = []

    # ---- Panels ----
    panels = [
        Panel("glue_tab",   x=x0, y=y1, width=G, height=y2 - y1),
        Panel("back",       x=x1, y=y1, width=W, height=y2 - y1),
        Panel("side_left",  x=x2, y=y1, width=D, height=y2 - y1),
        Panel("front",      x=x3, y=y1, width=W, height=y2 - y1),
        Panel("side_right", x=x4, y=y1, width=D, height=y2 - y1),
    ]

    dim_set = DimensionSet(
        manufacture=(W, D, H),
        inner=(
            round(W - 2 * board_thickness, 4),
            round(D - 2 * board_thickness, 4),
            round(H - 2 * board_thickness, 4),
        ),
        outer=(
            round(W + 2 * board_thickness, 4),
            round(D + 2 * board_thickness, 4),
            round(H + 2 * board_thickness, 4),
        ),
    )

    components = [
        ("main-body",          body_rect),
        ("glue-tab",           glue_poly),
        ("top-back-tuck",      tuck_back_top),
        ("top-left-dust",      dust_sl_top),
        ("top-right-dust",     dust_sr_top),
        ("bottom-front-tuck",  tuck_front_bot),
        ("bottom-left-dust",   dust_sl_bot),
        ("bottom-right-dust",  dust_sr_bot),
    ]

    stadium_cutouts = [
        ("top-back-slit",     back_cx,  slit_top_cy,  slit_w,       _SLIT_HEIGHT_MM),
        ("bottom-front-slit", front_cx, slit_bot_cy,  slit_w,       _SLIT_HEIGHT_MM),
    ]

    # Primitive paths only for components whose outline includes curves.
    # The exporter uses these to emit true `C` Bezier commands; every
    # other component falls back to polygon-to-polyline.
    component_paths = {
        "top-back-tuck":     tuck_back_top_primitives,
        "bottom-front-tuck": tuck_front_bot_primitives,
    }

    coords = DielineCoordinates(
        flat_width_mm=round(flat_w, 4),
        flat_height_mm=round(flat_h, 4),
        panels=panels,
        fold_lines=fold_lines,
        cut_polygon=cut_polygon,
        bleed_polygon=bleed_polygon,
        safe_polygon=safe_polygon,
        tuck_flap_polygons=[tuck_back_top, tuck_front_bot],
        dust_flap_polygons=[dust_sl_top, dust_sr_top, dust_sl_bot, dust_sr_bot],
        glue_tab_polygon=glue_poly,
        body_polygon=body_rect,
        slit_lines=slit_lines,
        components=components,
        component_paths=component_paths,
        stadium_cutouts=stadium_cutouts,
        dimensions=dim_set,
        board_thickness_mm=board_thickness,
        body_top_y=y1,
        body_bottom_y=y2,
        derived={
            "x0": x0, "x1": x1, "x2": x2, "x3": x3, "x4": x4, "x5": x5,
            "y0": y0, "y1": y1, "y2": y2, "y3": y3,
            "tuck_flap_height_mm": top_tuck_h,
            "dust_flap_height_mm": dust_h,
            "dust_flap_top_chamfer_mm": top_chamfer,
            "dust_flap_top_width_mm": D - 2 * top_chamfer,
            "dust_flap_base_notch_mm": base_notch,
            "tuck_inset_mm": tuck_inset,
            "tuck_curve_h_mm": curve_h,
            "slit_width_mm": slit_w,
            "glue_tab_corner_cut_mm": corner_cut,
            "kerf_mm": c.kerf_mm,
        },
    )
    coords.validate()
    return coords
