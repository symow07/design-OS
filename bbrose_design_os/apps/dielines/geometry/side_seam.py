# BEFORE MODIFYING ANY GEOMETRY:
# Read apps/dielines/docs/geometry_decisions.md AND the coordinate
# contract below. Every coordinate is derived from the contract — no
# ratios, no angles not listed in the contract, no magic numbers.
"""Side-seam straight tuck carton — parametric archetype (DECISION-018).

The reusable structural archetype behind the ``skynte_foundation_tuck_carton``
template: a straight-tuck-end carton whose glue seam leads a SIDE panel, so
the flat reads

    glue tab | side-L (A) | main (B) | side-R (A) | main (B)

matching the supplied Skynte Foundation manufacturing reference
(glue flap + 32 + 42 + 32 + 42), instead of the locked STE engine's
main-panel-first order (glue | back W | side D | front W | side D).

Nothing in apps/dielines/geometry/engine.py is modified: the STE reference
geometry stays byte-identical. This module has its own coordinate contract
and its own parameter set; shared physical helpers (stadium slits, shoulder
cubic sampling, slit web guard) are imported from the engine so the two
implementations cannot drift.

COORDINATE CONTRACT (t = board_thickness when thickness_compensation is
True, else t = 0; W = main/display panel width, D = side panel width):

    x0 = 0                       (glue tab left edge)
    x1 = G                       (fold 1: glue tab / side-L)
    x2 = x1 + D + t              (fold 2: side-L / front)
    x3 = x2 + W                  (fold 3: front / side-R)
    x4 = x3 + D + t              (fold 4: side-R / back)
    x5 = x4 + W + 2t             (back panel right edge — free edge that
                                  receives the glue tab when the tube closes)

    y0 = 0
    y1 = D + top_tuck_lip_mm     (top zone: the tuck folds over the D-deep
                                  opening, then its lip tucks down inside)
    y2 = y1 + H
    y3 = y2 + D + bottom_tuck_lip_mm

    flat_width  = G + 2D + 2W + 4t   (same ECMA total as the STE engine)
    flat_height = y3

ECMA BOARD-THICKNESS ALLOWANCES (same physical rule as the STE engine,
re-expressed for the side-seam panel order): front = W is the reference
panel; each side wraps one thickness (D + t); the back closes outermost and
carries the glue joint (W + 2t); the glue tab laps, it does not wrap (G).

TUCK HEIGHT MODEL (DECISION-019): the STE engine's measured factor
(W × 1.227) came from a square-section 28×28×120 reference where W = D, so
it cannot distinguish the fold-over span from the lip. Physically the tuck
folds across the D-deep opening and then tucks a lip down the inside face:

    tuck_total_h = D + tuck_lip_mm        (per end, parametric)

TUCK-BASE ENTRY SLITS (DECISION-020): at each end of a tuck flap's base
fold, a short segment is CUT rather than creased (``entry_slit_mm``), so the
shoulder corners spring free and lock behind the panel edge on closing. The
base crease is emitted only over the remaining middle span; the engine
publishes the cut segments in ``coords.slit_lines``. Horizontal creases are
therefore per-panel segments — a crease is never drawn along an edge that is
actually a cut (the front panel's top edge and the back panel's bottom edge
are plain cut edges in this closure and get no crease at all).
"""
from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..validators.schema import DielineInputJSON
from .coordinates import DielineCoordinates, DimensionSet
from .engine import (
    _DUST_BASE_NOTCH_MM,
    _DUST_MIN_TOP_WIDTH_MM,
    _DUST_TOP_CHAMFER_MM,
    _DUST_TUCK_CLEARANCE_MM,
    _MIN_SLIT_WIDTH_MM,
    _SLIT_FROM_TIP_MM,
    _SLIT_HEIGHT_MM,
    _TUCK_SHOULDER_K,
    _apply_slit_web_guard,
    _assert_ge,
    _shoulder_inset_at_y,
    _stadium_polygon,
    GeometryError,
)
from .panels import Panel
from .primitives import CubicSeg, LineSeg, Primitive, sample_path

# Post-generation bounding-box invariant tolerance (same as the STE engine).
_BBOX_EPSILON_MM = 0.01


# ---------------------------------------------------------------------------
# Parameter set — the complete structural vocabulary of the archetype.
# A template VERSION is a frozen instance of this spec; user input supplies
# only the six schema fields (dims, bleed, safe margin, glue tab) plus board
# thickness/compensation. Flap geometry stays engine-owned (DECISION-007) —
# tuning it means publishing a new template version, not editing a request.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SideSeamTuckSpec:
    """Frozen parameter set for one published template version."""
    template: str
    version: str
    # Closure depths (DECISION-019): tuck reach past the D fold-over span.
    top_tuck_lip_mm: float = 16.0
    bottom_tuck_lip_mm: float = 16.0
    # DECISION-016 shoulder form, parametric on the tuck panel width W.
    tuck_shoulder_inset_factor: float = 0.227
    tuck_shoulder_curve_factor: float = 0.218
    # Dust flaps (DECISION-016 form, parametric).
    dust_height_factor: float = 0.631        # of D
    dust_base_notch_mm: float = _DUST_BASE_NOTCH_MM
    dust_top_chamfer_mm: float = _DUST_TOP_CHAMFER_MM
    # Friction slit (DECISION-010/012/017).
    slit_width_factor: float = 0.327          # of W
    # Tuck-base entry slits (DECISION-020): cut length at each fold end.
    entry_slit_mm: float = 5.0
    # Glue tab taper: corner cut on the free (outer) edge.
    glue_corner_factor: float = 0.3
    glue_corner_cap_mm: float = 4.0
    # Which main panel carries which tuck (STE closure: both openings face
    # the same way; the back panel takes the top tuck).
    top_tuck_panel: str = "back"
    bottom_tuck_panel: str = "front"
    # Free-text assumptions published with every generated dieline so a
    # reviewer sees exactly which values were NOT supplied by the customer.
    assumptions: tuple[str, ...] = ()


#: skynte_foundation_tuck_carton/1.0 — the Skynte Foundation 32×42×140
#: reference reconstruction. Dimensions arrive from the dimension gate as
#: manufacturing W=42, D=32, H=140 with board_thickness_mm = 0.30 (the
#: supplied inner dimensions 41.4/31.4 equal manufacture − 2t only at
#: t = 0.3 mm). Values below that the customer did NOT supply are recorded
#: as explicit assumptions — they are reported, never silently invented.
SKYNTE_FOUNDATION_TUCK_CARTON_V1 = SideSeamTuckSpec(
    template="skynte_foundation_tuck_carton",
    version="1.0",
    top_tuck_lip_mm=16.0,
    bottom_tuck_lip_mm=16.0,
    entry_slit_mm=5.0,
    assumptions=(
        "top/bottom tuck lip depth 16.0 mm: closure depths are not stated in "
        "the supplied dimension tables and cannot be taken from screenshot "
        "pixels; 16 mm is standard practice for a 32 mm-deep cosmetic carton "
        "and is a published template parameter, not a customer dimension",
        "tuck-base entry slit length 5.0 mm per end: not stated in the "
        "supplied tables; standard shoulder-lock practice",
        "shoulder/dust/slit proportions inherit the measured DECISION-016 "
        "reference ratios pending a measured Skynte die",
    ),
)

_SPEC_REGISTRY: dict[str, SideSeamTuckSpec] = {
    SKYNTE_FOUNDATION_TUCK_CARTON_V1.template: SKYNTE_FOUNDATION_TUCK_CARTON_V1,
}


def spec_for_template(template: str) -> SideSeamTuckSpec | None:
    return _SPEC_REGISTRY.get(template)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def calculate_side_seam_tuck(
    params: DielineInputJSON, spec: SideSeamTuckSpec,
) -> DielineCoordinates:
    """Deterministic geometry for the side-seam straight-tuck archetype."""
    d = params.dimensions
    pset = params.print_settings
    c = params.construction

    W = d.width_mm          # main/display panel width (B)
    D = d.depth_mm          # side panel width (A)
    H = d.height_mm
    G = c.glue_tab_mm

    bleed_mm = pset.bleed_mm
    safe_margin_mm = pset.safe_margin_mm
    board_thickness = c.board_thickness_mm

    comp = c.thickness_compensation
    t = board_thickness if comp else 0.0
    lock_notch = 2.0 * t                      # DECISION-015

    # ---- Derived closure geometry (contract + spec) ----
    top_tuck_h = D + spec.top_tuck_lip_mm
    bottom_tuck_h = D + spec.bottom_tuck_lip_mm
    tuck_inset = W * spec.tuck_shoulder_inset_factor
    curve_h = W * spec.tuck_shoulder_curve_factor
    slit_w = max(_MIN_SLIT_WIDTH_MM, W * spec.slit_width_factor)
    corner_cut = min(G * spec.glue_corner_factor, spec.glue_corner_cap_mm)
    entry_slit = spec.entry_slit_mm

    # ---- Guards ----
    _assert_ge("width_mm", W, 12.0)
    _assert_ge("depth_mm", D, 12.0)
    _assert_ge("height_mm", H, 60.0)
    _assert_ge("top_tuck_lip_mm", spec.top_tuck_lip_mm, 10.0)
    _assert_ge("bottom_tuck_lip_mm", spec.bottom_tuck_lip_mm, 10.0)
    _assert_ge("tuck_inset", tuck_inset, 1.5)
    _assert_ge("tuck_curve_h", curve_h, 1.5)
    # The shoulder cubic must fit inside the lip (the curve belongs to the
    # tucked portion, above the fold-over span).
    if curve_h >= min(spec.top_tuck_lip_mm, spec.bottom_tuck_lip_mm):
        raise GeometryError(
            f"tuck shoulder curve ({curve_h:.2f} mm) does not fit inside the "
            f"tuck lip ({min(spec.top_tuck_lip_mm, spec.bottom_tuck_lip_mm):.2f} mm)"
            " — increase the lip or reduce the curve factor"
        )

    # DECISION-017 web guard on the friction slit.
    slit_edge_inset = _shoulder_inset_at_y(
        _SLIT_FROM_TIP_MM, curve_h, tuck_inset, _TUCK_SHOULDER_K,
    )
    slit_w, slit_web, slit_reduced = _apply_slit_web_guard(slit_w, W, slit_edge_inset)

    # Adaptive dust-flap top chamfer (same floor rule as the STE engine).
    top_chamfer = min(
        spec.dust_top_chamfer_mm, (D - _DUST_MIN_TOP_WIDTH_MM) / 2.0,
    )
    _assert_ge("dust_top_chamfer", top_chamfer, 1.0)

    # ---- Contract X coordinates ----
    side_w = D + t
    front_w = W
    back_w = W + 2.0 * t
    x0 = 0.0
    x1 = G
    x2 = x1 + side_w
    x3 = x2 + front_w
    x4 = x3 + side_w
    x5 = x4 + back_w

    # ---- Contract Y coordinates ----
    y0 = 0.0
    y1 = top_tuck_h
    y2 = y1 + H
    y3 = y2 + bottom_tuck_h

    flat_w = x5 - x0
    flat_h = y3 - y0

    # Entry-slit guard: the crease that remains between the two cut ends
    # must keep a working hinge (≥ 40 % of the flap base).
    tuck_base_w = back_w  # widest tuck base (back column)
    if 2.0 * (entry_slit + lock_notch) > 0.6 * tuck_base_w:
        raise GeometryError(
            f"entry slits ({entry_slit:.2f} mm) plus lock notches consume more "
            "than 60% of the tuck base — the hinge would tear on first fold"
        )

    # ---- Main body ----
    body_rect = Polygon([(x1, y1), (x5, y1), (x5, y2), (x1, y2)])

    # ---- Glue tab (tapered trapezoid, corners cut on the free edge) ----
    glue_poly = Polygon([
        (x0, y1 + corner_cut),
        (x1, y1),
        (x1, y2),
        (x0, y2 - corner_cut),
    ])

    # ---- Tuck flap paths (DECISION-016 cubic shoulders, DECISION-015
    #      lock notches; same primitive form as the STE engine) ----
    k_v = _TUCK_SHOULDER_K * curve_h
    k_h = _TUCK_SHOULDER_K * tuck_inset

    def _tuck_top_path(x_l: float, x_r: float) -> list[Primitive]:
        top_l = x_l + tuck_inset
        top_r = x_r - tuck_inset
        n = lock_notch
        path: list[Primitive] = []
        if n > 0.0:
            path.append(LineSeg((x_l + n, y1), (x_l + n, y1 - n)))
            path.append(LineSeg((x_l + n, y1 - n), (x_l, y1 - n)))
            path.append(LineSeg((x_l, y1 - n), (x_l, y0 + curve_h)))
        else:
            path.append(LineSeg((x_l, y1), (x_l, y0 + curve_h)))
        path.append(CubicSeg(
            p0=(x_l, y0 + curve_h),
            c1=(x_l, y0 + curve_h - k_v),
            c2=(top_l - k_h, y0),
            p1=(top_l, y0),
        ))
        if top_r > top_l:
            path.append(LineSeg((top_l, y0), (top_r, y0)))
        path.append(CubicSeg(
            p0=(top_r, y0),
            c1=(top_r + k_h, y0),
            c2=(x_r, y0 + curve_h - k_v),
            p1=(x_r, y0 + curve_h),
        ))
        if n > 0.0:
            path.append(LineSeg((x_r, y0 + curve_h), (x_r, y1 - n)))
            path.append(LineSeg((x_r, y1 - n), (x_r - n, y1 - n)))
            path.append(LineSeg((x_r - n, y1 - n), (x_r - n, y1)))
            path.append(LineSeg((x_r - n, y1), (x_l + n, y1)))
        else:
            path.append(LineSeg((x_r, y0 + curve_h), (x_r, y1)))
            path.append(LineSeg((x_r, y1), (x_l, y1)))
        return path

    def _tuck_bot_path(x_l: float, x_r: float) -> list[Primitive]:
        top_l = x_l + tuck_inset
        top_r = x_r - tuck_inset
        n = lock_notch
        path: list[Primitive] = []
        if n > 0.0:
            path.append(LineSeg((x_l + n, y2), (x_l + n, y2 + n)))
            path.append(LineSeg((x_l + n, y2 + n), (x_l, y2 + n)))
            path.append(LineSeg((x_l, y2 + n), (x_l, y3 - curve_h)))
        else:
            path.append(LineSeg((x_l, y2), (x_l, y3 - curve_h)))
        path.append(CubicSeg(
            p0=(x_l, y3 - curve_h),
            c1=(x_l, y3 - curve_h + k_v),
            c2=(top_l - k_h, y3),
            p1=(top_l, y3),
        ))
        if top_r > top_l:
            path.append(LineSeg((top_l, y3), (top_r, y3)))
        path.append(CubicSeg(
            p0=(top_r, y3),
            c1=(top_r + k_h, y3),
            c2=(x_r, y3 - curve_h + k_v),
            p1=(x_r, y3 - curve_h),
        ))
        if n > 0.0:
            path.append(LineSeg((x_r, y3 - curve_h), (x_r, y2 + n)))
            path.append(LineSeg((x_r, y2 + n), (x_r - n, y2 + n)))
            path.append(LineSeg((x_r - n, y2 + n), (x_r - n, y2)))
            path.append(LineSeg((x_r - n, y2), (x_l + n, y2)))
        else:
            path.append(LineSeg((x_r, y3 - curve_h), (x_r, y2)))
            path.append(LineSeg((x_r, y2), (x_l, y2)))
        return path

    # Panel columns for the side-seam order.
    _cols = {"front": (x2, x3), "back": (x4, x5)}
    ttl, ttr = _cols[spec.top_tuck_panel]
    btl, btr = _cols[spec.bottom_tuck_panel]

    tuck_top_primitives = _tuck_top_path(ttl, ttr)
    tuck_top_raw = Polygon(sample_path(tuck_top_primitives, cubic_segments=20))
    top_slit_cx = (ttl + ttr) / 2.0
    slit_top_cy = y0 + _SLIT_FROM_TIP_MM + _SLIT_HEIGHT_MM / 2.0
    tuck_top_poly = tuck_top_raw.difference(_stadium_polygon(
        cx=top_slit_cx, cy=slit_top_cy, width=slit_w, height=_SLIT_HEIGHT_MM,
    ))
    if not tuck_top_poly.is_valid:
        raise ValueError("top tuck polygon invalid after stadium-slit cutout")

    tuck_bot_primitives = _tuck_bot_path(btl, btr)
    tuck_bot_raw = Polygon(sample_path(tuck_bot_primitives, cubic_segments=20))
    bot_slit_cx = (btl + btr) / 2.0
    slit_bot_cy = y3 - _SLIT_FROM_TIP_MM - _SLIT_HEIGHT_MM / 2.0
    tuck_bot_poly = tuck_bot_raw.difference(_stadium_polygon(
        cx=bot_slit_cx, cy=slit_bot_cy, width=slit_w, height=_SLIT_HEIGHT_MM,
    ))
    if not tuck_bot_poly.is_valid:
        raise ValueError("bottom tuck polygon invalid after stadium-slit cutout")

    # ---- Dust flaps (DECISION-016 6-vertex form) on the side columns ----
    dust_h_nominal = D * spec.dust_height_factor
    dust_h_max = min(top_tuck_h, bottom_tuck_h) - _DUST_TUCK_CLEARANCE_MM
    dust_clamped = dust_h_nominal > dust_h_max
    dust_h = min(dust_h_nominal, dust_h_max)
    base_notch = spec.dust_base_notch_mm
    _assert_ge("dust_flap_height", dust_h, base_notch + 1.0)

    def _dust_flap(x_l: float, x_r: float, y_base: float, y_tip: float) -> Polygon:
        sign = 1.0 if y_tip > y_base else -1.0
        return Polygon([
            (x_r, y_base),
            (x_r - base_notch, y_base + sign * base_notch),
            (x_r - top_chamfer, y_tip),
            (x_l + top_chamfer, y_tip),
            (x_l + base_notch, y_base + sign * base_notch),
            (x_l, y_base),
        ])

    dust_sl_top = _dust_flap(x1, x2, y_base=y1, y_tip=y1 - dust_h)
    dust_sr_top = _dust_flap(x3, x4, y_base=y1, y_tip=y1 - dust_h)
    dust_sl_bot = _dust_flap(x1, x2, y_base=y2, y_tip=y2 + dust_h)
    dust_sr_bot = _dust_flap(x3, x4, y_base=y2, y_tip=y2 + dust_h)

    # ---- Union into the full cut polygon ----
    cut_polygon = unary_union([
        body_rect, glue_poly, tuck_top_poly, tuck_bot_poly,
        dust_sl_top, dust_sr_top, dust_sl_bot, dust_sr_bot,
    ])
    if cut_polygon.geom_type != "Polygon":
        raise ValueError(
            f"cut_polygon must be a single Polygon, got {cut_polygon.geom_type}"
        )
    if not cut_polygon.is_valid:
        raise ValueError("cut_polygon is invalid after union")

    bb_minx, bb_miny, bb_maxx, bb_maxy = cut_polygon.bounds
    if (
        bb_minx < -_BBOX_EPSILON_MM
        or bb_miny < -_BBOX_EPSILON_MM
        or bb_maxx > flat_w + _BBOX_EPSILON_MM
        or bb_maxy > flat_h + _BBOX_EPSILON_MM
    ):
        raise GeometryError(
            "cut polygon escapes the declared flat sheet: bbox "
            f"({bb_minx:.3f}, {bb_miny:.3f}, {bb_maxx:.3f}, {bb_maxy:.3f}) vs "
            f"sheet 0..{flat_w:.3f} × 0..{flat_h:.3f} — refusing to export"
        )

    # ---- Bleed and safe area ----
    bleed_polygon = cut_polygon.buffer(bleed_mm, join_style=1, quad_segs=16)
    if not bleed_polygon.is_valid:
        raise ValueError("bleed_polygon invalid after buffer")
    safe_polygon = Polygon([
        (x1 + safe_margin_mm, y1 + safe_margin_mm),
        (x5 - safe_margin_mm, y1 + safe_margin_mm),
        (x5 - safe_margin_mm, y2 - safe_margin_mm),
        (x1 + safe_margin_mm, y2 - safe_margin_mm),
    ])

    # ---- Fold lines: per-panel segments (DECISION-020) ----
    # Vertical creases at every panel fold; horizontal creases only where a
    # hinge physically exists. The tuck base creases are shortened by the
    # entry slits (+ lock notches), whose cut segments go to slit_lines.
    def _tuck_base_fold(x_l: float, x_r: float, y: float):
        start = x_l + lock_notch + entry_slit
        end = x_r - lock_notch - entry_slit
        fold = (start, y, end, y)
        cuts = [
            (x_l + lock_notch, y, start, y),
            (end, y, x_r - lock_notch, y),
        ]
        return fold, cuts

    top_fold, top_cuts = _tuck_base_fold(ttl, ttr, y1)
    bot_fold, bot_cuts = _tuck_base_fold(btl, btr, y2)

    fold_lines: list[tuple[float, float, float, float]] = [
        (x1, y1, x1, y2),         # glue / side-L
        (x2, y1, x2, y2),         # side-L / front
        (x3, y1, x3, y2),         # front / side-R
        (x4, y1, x4, y2),         # side-R / back
        (x1, y1, x2, y1),         # top dust hinge (side-L)
        (x3, y1, x4, y1),         # top dust hinge (side-R)
        top_fold,                 # top tuck hinge (shortened)
        (x1, y2, x2, y2),         # bottom dust hinge (side-L)
        (x3, y2, x4, y2),         # bottom dust hinge (side-R)
        bot_fold,                 # bottom tuck hinge (shortened)
    ]
    slit_lines: list[tuple[float, float, float, float]] = top_cuts + bot_cuts

    # ---- Panels ----
    panels = [
        Panel("glue_tab",   x=x0, y=y1, width=G,       height=y2 - y1),
        Panel("side_left",  x=x1, y=y1, width=side_w,  height=y2 - y1),
        Panel("front",      x=x2, y=y1, width=front_w, height=y2 - y1),
        Panel("side_right", x=x3, y=y1, width=side_w,  height=y2 - y1),
        Panel("back",       x=x4, y=y1, width=back_w,  height=y2 - y1),
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

    top_tuck_id = f"top-{spec.top_tuck_panel}-tuck"
    bottom_tuck_id = f"bottom-{spec.bottom_tuck_panel}-tuck"
    components = [
        ("main-body",          body_rect),
        ("glue-tab",           glue_poly),
        (top_tuck_id,          tuck_top_poly),
        ("top-left-dust",      dust_sl_top),
        ("top-right-dust",     dust_sr_top),
        (bottom_tuck_id,       tuck_bot_poly),
        ("bottom-left-dust",   dust_sl_bot),
        ("bottom-right-dust",  dust_sr_bot),
    ]
    stadium_cutouts = [
        (f"top-{spec.top_tuck_panel}-slit", top_slit_cx, slit_top_cy,
         slit_w, _SLIT_HEIGHT_MM),
        (f"bottom-{spec.bottom_tuck_panel}-slit", bot_slit_cx, slit_bot_cy,
         slit_w, _SLIT_HEIGHT_MM),
    ]
    component_paths = {
        top_tuck_id: tuck_top_primitives,
        bottom_tuck_id: tuck_bot_primitives,
    }

    # ---- Notes + published assumptions ----
    notes: list[str] = []
    if dust_clamped:
        notes.append(
            f"dust flap reduced from {dust_h_nominal:.2f} mm to {dust_h:.2f} mm "
            f"to stay {_DUST_TUCK_CLEARANCE_MM:g} mm below the tuck zone "
            "(DECISION-004 clamp)"
        )
    if slit_reduced:
        notes.append(
            f"friction slit reduced to {slit_w:.2f} mm to preserve a 2 mm web "
            "beside each slit end (DECISION-017)"
        )
    if comp and t > 0.0:
        notes.append(
            f"board-thickness compensation active (t = {t:g} mm): "
            f"back +{2.0 * t:g} mm, sides +{t:g} mm each, "
            f"lock notches {lock_notch:g} mm (DECISION-015)"
        )
    for a in spec.assumptions:
        notes.append(f"ASSUMPTION ({spec.template}/{spec.version}): {a}")

    coords = DielineCoordinates(
        flat_width_mm=round(flat_w, 4),
        flat_height_mm=round(flat_h, 4),
        panels=panels,
        fold_lines=fold_lines,
        cut_polygon=cut_polygon,
        bleed_polygon=bleed_polygon,
        safe_polygon=safe_polygon,
        tuck_flap_polygons=[tuck_top_poly, tuck_bot_poly],
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
            "structure_type": spec.template,
            "template_version": spec.version,
            "archetype": "side_seam_straight_tuck_carton",
            "provisional": False,
            "bottom_mode": "tuck",
            "panel_order": [p.name for p in panels],
            "top_tuck_panel": spec.top_tuck_panel,
            "bottom_tuck_panel": spec.bottom_tuck_panel,
            "top_tuck_height_mm": top_tuck_h,
            "bottom_tuck_height_mm": bottom_tuck_h,
            "tuck_flap_height_mm": top_tuck_h,   # exporter compatibility
            "top_tuck_lip_mm": spec.top_tuck_lip_mm,
            "bottom_tuck_lip_mm": spec.bottom_tuck_lip_mm,
            "dust_flap_height_mm": dust_h,
            "dust_flap_height_nominal_mm": dust_h_nominal,
            "dust_flap_clamped": dust_clamped,
            "dust_flap_top_chamfer_mm": top_chamfer,
            "dust_flap_top_width_mm": D - 2 * top_chamfer,
            "dust_flap_base_notch_mm": base_notch,
            "tuck_inset_mm": tuck_inset,
            "tuck_curve_h_mm": curve_h,
            "slit_width_mm": slit_w,
            "slit_web_mm": slit_web,
            "slit_reduced": slit_reduced,
            "entry_slit_mm": entry_slit,
            "glue_tab_corner_cut_mm": corner_cut,
            "kerf_mm": c.kerf_mm,
            "thickness_compensation": comp,
            "panel_allowance_back_mm": 2.0 * t,
            "panel_allowance_side_mm": t,
            "lock_notch_mm": lock_notch,
            "assumptions": list(spec.assumptions),
            "parameters": _spec_parameters(spec),
            "notes": notes,
        },
    )
    coords.validate()
    return coords


def _spec_parameters(spec: SideSeamTuckSpec) -> dict:
    """The full published parameter table for the spec sheet / comparison page."""
    return {
        "template": spec.template,
        "version": spec.version,
        "top_tuck_lip_mm": spec.top_tuck_lip_mm,
        "bottom_tuck_lip_mm": spec.bottom_tuck_lip_mm,
        "tuck_shoulder_inset_factor": spec.tuck_shoulder_inset_factor,
        "tuck_shoulder_curve_factor": spec.tuck_shoulder_curve_factor,
        "dust_height_factor": spec.dust_height_factor,
        "dust_base_notch_mm": spec.dust_base_notch_mm,
        "dust_top_chamfer_mm": spec.dust_top_chamfer_mm,
        "slit_width_factor": spec.slit_width_factor,
        "entry_slit_mm": spec.entry_slit_mm,
        "glue_corner_factor": spec.glue_corner_factor,
        "glue_corner_cap_mm": spec.glue_corner_cap_mm,
        "top_tuck_panel": spec.top_tuck_panel,
        "bottom_tuck_panel": spec.bottom_tuck_panel,
    }


__all__ = [
    "SideSeamTuckSpec",
    "SKYNTE_FOUNDATION_TUCK_CARTON_V1",
    "calculate_side_seam_tuck",
    "spec_for_template",
]
