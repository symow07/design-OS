# BEFORE MODIFYING ANY GEOMETRY:
# Read apps/dielines/docs/geometry_decisions.md AND the coordinate
# contract below. Every coordinate is derived from the contract — no
# ratios, no angles not listed in the contract, no magic numbers.
"""Straight Tuck End (STE) carton — exact coordinate-driven geometry.

Inputs: width W, depth D, height H, glue_tab G, bleed, safe_margin,
board_thickness, thickness_compensation.

Coordinate system: origin at the far-left glue-tab edge. The body
starts at x1 = G.

ABSOLUTE X (contract; t = board_thickness when
construction.thickness_compensation is True, else t = 0):
    x0 = 0                       (glue tab left edge)
    x1 = G                       (fold 1: glue tab / back)
    x2 = x1 + W + 2t             (fold 2: back / side-L)
    x3 = x2 + D + t              (fold 3: side-L / front)
    x4 = x3 + W                  (fold 4: front / side-R)
    x5 = x4 + D + t              (side-R panel right edge)

ABSOLUTE Y (contract):
    y0 = 0
    y1 = top_tuck_h           (= W × 1.227)
    y2 = top_tuck_h + H
    y3 = top_tuck_h + H + bottom_tuck_h   (= top_tuck_h)

BOARD-THICKNESS ALLOWANCES (Milestone 9.2, opt-in):
    construction.thickness_compensation = False (the default) keeps the
    legacy layout: board_thickness_mm feeds only the inner/outer spec
    table, panel widths are the raw G+W+D+W+D sums, and the output is
    byte-identical to the measured engine reference snapshot
    (apps/dielines/docs/28x28x120_engine_reference.json).

    With thickness_compensation = True and t = board_thickness_mm the
    engine applies the standard folding-carton (ECMA) allowance rule:
    score-to-score panel widths grow so the glued tube closes square
    around a W × D manufacture cross-section —
        front panel  = W        (reference panel, carries bottom tuck)
        side panels  = D + t    (each wrap adds one board thickness)
        back panel   = W + 2t   (carries the glue joint — closes
                                 outermost, so it wraps two thicknesses)
        glue tab     = G        (unchanged; the tab laps, it does not wrap)
    flat_width therefore grows by exactly 4t. Vertical (height)
    allowances are intentionally NOT applied: tuck and dust flap lengths
    are measured ratios from the reference file (DECISION-016) and
    already include working clearance.

    The same flag activates the DECISION-015 shoulder lock notches:
    a (2t × 2t) square cut notch at each base corner of both active
    tuck flaps, so the tuck clears the side panels' board thickness
    without tearing the shoulder on first fold.
"""
from __future__ import annotations

import math
from dataclasses import dataclass as _dataclass
from dataclasses import replace as _dataclasses_replace

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from .coordinates import DielineCoordinates, DimensionSet
from .panels import Panel
from .primitives import CubicSeg, LineSeg, Primitive, sample_path
from ..validators.schema import DielineInputJSON


# ---------------------------------------------------------------------------
# Errors and guard assertions
# ---------------------------------------------------------------------------

class GeometryError(ValueError):
    """A generated dieline violated a post-generation physical invariant.

    Raised after geometry construction when the result could not be
    physically die-cut or folded (e.g. the cut path escaping the
    declared flat sheet). Callers must treat this as fatal — garbage
    geometry never exports.
    """


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
# DECISION-017 slit web guard helpers
# ---------------------------------------------------------------------------

def _shoulder_inset_at_y(
    y_from_tip: float, curve_h: float, tuck_inset: float,
    k: float, samples: int = 96,
) -> float:
    """Horizontal inset of the tuck-flap side edge at a given height,
    measured down from the flap tip, along the DECISION-016 shoulder
    cubic.

    Local curve (one shoulder): starts on the flap side at
    (0, curve_h) with a vertical tangent and ends on the flat top at
    (tuck_inset, 0) with a horizontal tangent — control points at
    (0, curve_h − k·curve_h) and (tuck_inset − k·tuck_inset, 0).
    Returns 0.0 at/below the curve start (the flap side is vertical
    there) and up to tuck_inset at the very tip. y(t) is monotonic for
    this control layout, so a sampled linear interpolation is exact to
    well under 0.01 mm at 96 samples.
    """
    if y_from_tip >= curve_h:
        return 0.0
    k_v = k * curve_h
    k_h = k * tuck_inset
    pts: list[tuple[float, float]] = [(0.0, curve_h)]
    for i in range(1, samples + 1):
        t = i / samples
        u = 1.0 - t
        # p0 = (0, curve_h), c1 = (0, curve_h - k_v),
        # c2 = (tuck_inset - k_h, 0), p1 = (tuck_inset, 0)
        x = 3 * u * t * t * (tuck_inset - k_h) + t * t * t * tuck_inset
        y = u * u * u * curve_h + 3 * u * u * t * (curve_h - k_v)
        pts.append((x, y))
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if y1 <= y_from_tip <= y0:
            if y0 == y1:
                return x1
            f = (y0 - y_from_tip) / (y0 - y1)
            return x0 + f * (x1 - x0)
    return tuck_inset


def _apply_slit_web_guard(
    slit_w: float, panel_w: float, edge_inset: float,
) -> tuple[float, float, bool]:
    """DECISION-017: keep ≥ _MIN_SLIT_WEB_MM of solid board between each
    friction-slit end and the tuck-flap side edge, measured at the
    slit's own height (a slit end closer than that to a free edge tears
    through on first use — narrow W ≤ 15 mm cartons are the at-risk
    family).

    Returns (slit_w, web_mm, reduced). When the nominal slit leaves too
    little web, the slit is scaled down to preserve the 2 mm web; if
    that would push the slit below the _ABS_MIN_SLIT_MM functional
    floor, the carton cannot carry a friction slit at all and the
    engine refuses with a GeometryError.
    """
    available = panel_w - 2.0 * edge_inset
    web = (available - slit_w) / 2.0
    if web >= _MIN_SLIT_WEB_MM:
        return slit_w, web, False
    reduced = available - 2.0 * _MIN_SLIT_WEB_MM
    if reduced < _ABS_MIN_SLIT_MM:
        raise GeometryError(
            f"friction slit cannot fit: after preserving a {_MIN_SLIT_WEB_MM} mm "
            f"web on each side only {reduced:.2f} mm remains, below the "
            f"{_ABS_MIN_SLIT_MM} mm functional floor for a friction lock"
        )
    return reduced, _MIN_SLIT_WEB_MM, True


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
_DUST_TOP_CHAMFER_MM = 6.0      # nominal 6 mm top chamfer each side (max)
_DUST_MIN_TOP_WIDTH_MM = 3.0    # floor for the dust-flap top edge; chamfer scales to hold it
_SLIT_WIDTH_FACTOR   = 0.327    # friction slit width = W × 0.327 (provisional; measuring it needs a physical sample — docs/roadmap/AFTER_THE_TEST_DAY.md)
# Cubic-Bezier quarter-arc tangent-length factor. For control points
# placed at (k * leg) along each tangent of a right-angle corner, k =
# 0.55228... produces a near-perfect quarter-ellipse — the standard CAD
# approximation used by Adobe Illustrator's "Convert to Curve" tool for
# rectangle corners. Provisional until the real Pacdora control points
# are measured (on docs/roadmap/AFTER_THE_TEST_DAY.md: measuring it needs a physical sample).
_TUCK_SHOULDER_K     = 0.55228474983
_MIN_SLIT_WIDTH_MM   = 5.0
_SLIT_HEIGHT_MM      = 1.5
_SLIT_FROM_TIP_MM    = 3.0
_GLUE_CORNER_FACTOR  = 0.3
_GLUE_CORNER_CAP_MM  = 4.0

# Milestone 9.1 guards
# DECISION-004 requires the dust flaps to stay shorter than the tuck
# flaps (dust folds first). On deep-narrow cartons D × 0.631 can exceed
# the W-derived tuck zone; the engine clamps the dust height to the
# tuck zone minus this safety clearance and annotates the result.
_DUST_TUCK_CLEARANCE_MM = 2.0
# Post-generation bounding-box invariant tolerance: the cut polygon must
# lie inside [0, flat_width] × [0, flat_height] to within this epsilon.
_BBOX_EPSILON_MM = 0.01

# DECISION-017 web guard (Milestone 9.3): keep at least this much solid
# board between each friction-slit end and the tuck-flap side edge,
# measured at the slit's own height. Below _ABS_MIN_SLIT_MM a friction
# slit no longer locks — the engine refuses rather than emit one.
_MIN_SLIT_WEB_MM = 2.0
_ABS_MIN_SLIT_MM = 3.0
# [His final goal, 2026-10-05, B2: "A PRINT-READY DIELINE. Cut lines solid; crease lines dashed on EVERY fold, including
# flap hinges and the tuck fold. Proper dust-flap shapes, tuck-lock slits and a thumb notch."] v1.3: the tuck fold — the
# hinge between the lid (as deep as the carton) and its tongue — creased; a lock slit cut along it from each side edge,
# which the dust flaps' shoulders catch; a half-round thumb notch in the top edge of the panel the lid closes onto
_LOCK_SLIT_MIN_MM = 2.0
_LOCK_SLIT_MAX_MM = 4.0
_LOCK_SLIT_SHARE = 0.15         # of the tuck's width
_MIN_TONGUE_MM = 8.0            # a tongue shorter than this has no tuck fold to crease
_THUMB_NOTCH_SHARE = 0.22       # its radius: this share of the panel's width
_THUMB_NOTCH_MAX_R_MM = 9.0

# DECISION-017 (see apps/dielines/docs/geometry_decisions.md):
# _SLIT_WIDTH_FACTOR and _TUCK_SHOULDER_K remain PROVISIONAL. Milestone
# 9.3 attempted to re-derive both from the measured dump
# (apps/dielines/docs/28x28x120_coordinate_dump.json), but that dump
# predates DECISION-010/012/014/016 — its tuck flaps are rounded
# rectangles (corner radius ≈ W × 0.107, tuck height W × 0.9) with
# straight slit LINES, so it contains none of the DECISION-016-era
# points needed to derive either constant. The exact coordinates still
# required from SLIMMING_CREAM_R-108-A.ai are listed in
# apps/dielines/docs/MEASUREMENT_NEEDED.md. Until they are measured the
# engine cannot claim Pacdora-grade slit/shoulder proportions.


# ---------------------------------------------------------------------------
# Carton-style configuration & dispatch (Milestone 12.1)
# ---------------------------------------------------------------------------
#
# Straight-tuck-end (STE) is the only style with a measured reference file, so
# its geometry is LOCKED and byte-identical to the engine reference snapshot.
# Reverse-tuck-end and tuck-top-auto-bottom have NO measured reference; their
# constants are inherited from the STE contract and their layout follows
# standard ECMA folding-carton practice. Both are flagged ``provisional`` —
# the AI contract requires a human to confirm the structure at the dimension
# gate before either is sent to a print shop.
#
# A style differs from STE only in:
#   * which body panel carries the top / bottom tuck flap (STE: top on back,
#     bottom on front; reverse: swapped), and
#   * how the bottom closes ("tuck" flap vs "auto_lock" crash-lock base).
# Everything else (dust flaps on the two side panels, slit, shoulder cubic,
# thickness compensation, guards, invariants) is shared.


@_dataclass(frozen=True)
class _StyleConfig:
    structure_type: str
    top_tuck: str        # "back" | "front" — which panel carries the top tuck
    bottom_tuck: str     # "back" | "front" — bottom tuck panel (tuck mode only)
    bottom_mode: str = "tuck"   # "tuck" | "auto_lock"
    provisional: bool = False
    version: str = "1.0"
    # DECISION-021. False = the frozen v1.0 form: two full-width horizontal
    # creases, which run over the flapless panel's cut edge and through the
    # lock notches. True = one crease per real hinge (v1.1, corrected).
    per_hinge_creases: bool = False
    # 2A-9D closure model. "w_ratio" = the DECISION-016 W-derived tuck
    # (v1.0/v1.1). "d_derived" = the v1.2 correction: tuck reaches across
    # the depth (D + lip), shoulder span is lip-derived. The ONLY geometry
    # difference between 1.1 and 1.2.
    closure_model: str = "w_ratio"
    # [his final goal, 2026-10-05, B2] v1.3: the tuck folds creased, their lock slits and the thumb notch. False — every
    # version before it — draws exactly as before.
    print_ready: bool = False


# Keyed by (template_id, version). v1.0 entries are FROZEN — they reproduce
# the historical output byte-for-byte, including the DECISION-021 crease
# defect, so a historical job regenerates exactly as it shipped. v1.1 is the
# corrected, production-eligible geometry.
_STYLE_CONFIG_VERSIONED: dict[tuple[str, str], _StyleConfig] = {}


def _register_style(cfg: _StyleConfig) -> _StyleConfig:
    _STYLE_CONFIG_VERSIONED[(cfg.structure_type, cfg.version)] = cfg
    return cfg


_STYLE_CONFIG: dict[str, _StyleConfig] = {
    "straight_tuck_end_carton": _StyleConfig(
        structure_type="straight_tuck_end_carton",
        top_tuck="back", bottom_tuck="front", bottom_mode="tuck",
        provisional=False,
    ),
    "reverse_tuck_end_carton": _StyleConfig(
        structure_type="reverse_tuck_end_carton",
        # Reverse: top and bottom tucks hinge from opposite panels to STE, so
        # the two openings face opposite directions (cheaper to run, slight
        # panel offset). Mirror of the STE column assignment.
        top_tuck="front", bottom_tuck="back", bottom_mode="tuck",
        provisional=True,
    ),
    "tuck_top_auto_bottom_carton": _StyleConfig(
        structure_type="tuck_top_auto_bottom_carton",
        # Tuck top like STE; bottom is a four-flap crash-lock base for heavier
        # products. PROVISIONAL ECMA approximation (no reference .ai).
        top_tuck="back", bottom_tuck="front", bottom_mode="auto_lock",
        provisional=True,
    ),
}

# v1.0 (frozen, defective creases) + v1.1 (corrected per-hinge creases).
for _base in _STYLE_CONFIG.values():
    _register_style(_base)
    _register_style(_dataclasses_replace(
        _base, version="1.1", per_hinge_creases=True))

# 2A-9D v1.2 (D-derived closure) — registered ONLY for the straight- and
# reverse-tuck styles. Auto-bottom gets no 1.2 (MEASURED_REFERENCE_REQUIRED).
# 1.2 is 1.1 with per_hinge_creases + the d_derived closure model; nothing
# else changes.
for _tid in ("straight_tuck_end_carton", "reverse_tuck_end_carton"):
    _register_style(_dataclasses_replace(
        _STYLE_CONFIG[_tid], version="1.2",
        per_hinge_creases=True, closure_model="d_derived"))

# [his final goal, 2026-10-05, B2: "It must go to a printer without being edited."] v1.3 — 1.2's tuck across the depth
# with the tuck folds creased, their lock slits and the thumb notch. The version a new design is drawn at
# (targets: carton_template_version); an unpinned caller still gets the current one below.
for _tid in ("straight_tuck_end_carton", "reverse_tuck_end_carton"):
    _register_style(_dataclasses_replace(
        _STYLE_CONFIG[_tid], version="1.3",
        per_hinge_creases=True, closure_model="d_derived", print_ready=True))

#: The version an unpinned caller gets. v1.0 stays reachable ONLY by an
#: explicit pin, so historical jobs reproduce exactly while nothing new is
#: built on the defective creases.
_CURRENT_STYLE_VERSION = "1.1"

# DECISION-004 requires dust flaps to fold before (shorter than) the tuck.
# For the auto-lock base the four lock flaps take the place of the bottom
# tuck+dust; their reach is bounded by the tuck zone for the same reason.
_AUTO_BOTTOM_FACTOR = 0.75   # lock-flap depth = min(W, D) × factor (provisional)

# 2A-9D D-derived closure constants (v1.2). Informed by the validated
# Skynte DECISION-019 model (lip 16 mm) but the STE/RTE formulas are
# derived here independently: the major tuck reaches across the DEPTH and
# tucks an explicit lip; the shoulder span is a fraction of the lip so it
# always fits inside it (no W-derived shoulder, hence no Skynte width cap).
_D_DERIVED_LIP_MM = 16.0
_D_DERIVED_CURVE_RATIO = 0.5   # shoulder span = lip × ratio (always < lip)


def _closure_heights(cfg, W, D):
    """(top_tuck_h, bottom_tuck_h, curve_h, tuck_inset) for the style.

    w_ratio returns the exact legacy expressions (byte-identical to
    v1.0/v1.1). d_derived returns the v1.2 depth-derived reach + lip-derived
    shoulder span; the shoulder INSET stays W-based because it is the flap's
    OWN width (main-panel tucks are W wide) — that is flap-width geometry,
    not a closure-depth dependency.
    """
    if getattr(cfg, "closure_model", "w_ratio") == "d_derived":
        lip = _D_DERIVED_LIP_MM
        reach = D + lip                       # spans the depth, tucks the lip
        curve_h = _D_DERIVED_CURVE_RATIO * lip
        return reach, reach, curve_h, W * _TUCK_INSET_FACTOR
    top = W * _TUCK_HEIGHT_FACTOR
    return top, top, W * _TUCK_CURVE_H_FACTOR, W * _TUCK_INSET_FACTOR


def calculate_dieline(params: DielineInputJSON) -> DielineCoordinates:
    """Dispatch to the engine for ``params.template`` at its version.

    ``params.template_version`` selects the geometry generation. None means
    the CURRENT published version, so a caller that pins 1.0 reproduces the
    historical (defective-crease) output exactly, while everything else gets
    the corrected geometry (DECISION-021).
    """
    version = getattr(params, "template_version", None)
    # [his second goal of 2026-10-06, item 2: "TOP-TIER DIELINES"] 1.4 — the straight and the reverse tuck end drawn to
    # the trade's written rules (apps/dielines/docs/TRADE_RULES.md), in their own module; 1.0–1.3 below are untouched
    from .trade_tuck import calculate_trade_tuck, is_trade
    if is_trade(params.template, version):
        return calculate_trade_tuck(params)
    if version is not None:
        cfg = _STYLE_CONFIG_VERSIONED.get((params.template, version))
        if cfg is not None:
            return _calculate_carton(params, cfg)
        if params.template in _STYLE_CONFIG:
            raise ValueError(
                f"unknown version {version!r} for carton style "
                f"{params.template!r}; published: "
                f"{sorted(v for (t, v) in _STYLE_CONFIG_VERSIONED if t == params.template)}"
            )
    else:
        cfg = _STYLE_CONFIG_VERSIONED.get(
            (params.template, _CURRENT_STYLE_VERSION))
        if cfg is not None:
            return _calculate_carton(params, cfg)
    # Side-seam parametric archetype templates (DECISION-018) live in their
    # own module so the LOCKED STE reference geometry above stays untouched.
    from .side_seam import calculate_side_seam_tuck, spec_for_template
    spec = spec_for_template(params.template)
    if spec is not None:
        return calculate_side_seam_tuck(params, spec)
    # Phase 2A-9 open-source-adapted STE archetype — its own module, its own
    # coordinate contract; the historical STE 1.0/1.1 geometry is untouched.
    from .ecma_ste import calculate_ecma_ste
    from .ecma_ste import spec_for_template as ecma_spec_for_template
    ecma_spec = ecma_spec_for_template(params.template)
    if ecma_spec is not None:
        return calculate_ecma_ste(params, ecma_spec)
    # 2A-9-CORR-2 reference-matched opposing-tuck archetype.
    from .opposed_tuck import calculate_opposed_tuck
    from .opposed_tuck import spec_for_template as opp_spec_for_template
    opp_spec = opp_spec_for_template(params.template)
    if opp_spec is not None:
        return calculate_opposed_tuck(params, opp_spec)
    raise ValueError(f"unknown carton style: {params.template!r}")


# The three helpers below are pinned to v1.0 ON PURPOSE: they exist so the
# measured reference snapshot stays byte-identical. They are NOT the current
# production geometry — v1.0 carries the DECISION-021 crease defect. New work
# goes through calculate_dieline(), which resolves the CURRENT version.

def calculate_straight_tuck_end(params: DielineInputJSON) -> DielineCoordinates:
    """Straight tuck end at v1.0 — LOCKED reference geometry (byte-identical).

    Historical reproduction only; see DECISION-021.
    """
    return _calculate_carton(params, _STYLE_CONFIG["straight_tuck_end_carton"])


def calculate_reverse_tuck_end(params: DielineInputJSON) -> DielineCoordinates:
    """Reverse tuck end at v1.0 — PROVISIONAL, historical reproduction only."""
    return _calculate_carton(params, _STYLE_CONFIG["reverse_tuck_end_carton"])


def calculate_tuck_top_auto_bottom(params: DielineInputJSON) -> DielineCoordinates:
    """Tuck top / crash-lock bottom at v1.0 — historical reproduction only."""
    return _calculate_carton(params, _STYLE_CONFIG["tuck_top_auto_bottom_carton"])


def _hinge_creases(
    columns: dict[str, tuple[float, float]],
    y1: float, y2: float, cfg: _StyleConfig,
    lock_notch: float, has_bottom_tuck: bool,
) -> list[tuple[float, float, float, float]]:
    """DECISION-021: one crease per REAL hinge, never over a cut edge.

    A horizontal crease may exist only where a flap actually hinges off the
    body at that end, and only across the material that is still there:

      * the tuck-carrying column creases from ``x_l + lock_notch`` to
        ``x_r - lock_notch`` — the DECISION-015 corner notches are cut away,
        so a crease through them would score a hole;
      * the two side columns carry dust flaps whose base edge spans the full
        column, so they crease edge to edge;
      * the opposite main panel carries NO flap at that end: its top (or
        bottom) edge is a plain cut edge and gets no crease at all;
      * the glue tab never creases (DECISION-008).

    For the auto-lock bottom every body column carries a lock flap, so all
    four crease across their full width.

    Returns the horizontal creases only; zero-length segments are dropped so
    a degenerate column can never emit a duplicate or empty crease.
    """
    out: list[tuple[float, float, float, float]] = []

    def add(x_l: float, x_r: float, y: float) -> None:
        if x_r - x_l > 1e-9:
            out.append((x_l, y, x_r, y))

    # --- top edge (y1) -----------------------------------------------------
    for name, (x_l, x_r) in columns.items():
        if name == cfg.top_tuck:                      # tuck hinge, notched
            add(x_l + lock_notch, x_r - lock_notch, y1)
        elif name in ("side_left", "side_right"):     # dust hinge, full span
            add(x_l, x_r, y1)
        # the other main panel: free cut edge, no crease

    # --- bottom edge (y2) --------------------------------------------------
    for name, (x_l, x_r) in columns.items():
        if not has_bottom_tuck:                       # auto-lock: all hinge
            add(x_l, x_r, y2)
        elif name == cfg.bottom_tuck:
            add(x_l + lock_notch, x_r - lock_notch, y2)
        elif name in ("side_left", "side_right"):
            add(x_l, x_r, y2)
    return out


def _calculate_carton(
    params: DielineInputJSON, cfg: _StyleConfig,
) -> DielineCoordinates:
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

    # ---- Contract-derived heights ----
    # w_ratio (v1.0/v1.1, DECISION-016): tuck reach + shoulder span scale
    # with W (measured from the square 28x28x120 reference that hid the
    # W/D distinction). d_derived (v1.2, 2A-9D): the tuck reaches across
    # the DEPTH (D + explicit lip) and the shoulder span is lip-derived, so
    # the lip-vs-height defect is structurally gone. The branch is the ONLY
    # geometry difference — everything else (dust, slits, notches, glue,
    # bleed, creases, panel order) is shared, so 1.0/1.1 stay byte-identical.
    top_tuck_h, bottom_tuck_h, curve_h, tuck_inset = _closure_heights(cfg, W, D)
    # Auto-lock base depth (auto_bottom style only; provisional ECMA approx).
    auto_h        = min(W, D) * _AUTO_BOTTOM_FACTOR
    slit_w        = max(_MIN_SLIT_WIDTH_MM, W * _SLIT_WIDTH_FACTOR)
    corner_cut    = min(G * _GLUE_CORNER_FACTOR, _GLUE_CORNER_CAP_MM)
    # Dust-flap top chamfer scales down on shallow cartons so the flap's top
    # edge always holds at least _DUST_MIN_TOP_WIDTH_MM — a fixed 6 mm chamfer
    # would invert the flap on a 12–14 mm depth. Normal cartons (D ≥ 15 mm)
    # keep the nominal 6 mm, so this is byte-identical for typical sizes.
    top_chamfer   = min(_DUST_TOP_CHAMFER_MM, (D - _DUST_MIN_TOP_WIDTH_MM) / 2.0)

    # DECISION-017 web guard: the slit sits _SLIT_FROM_TIP_MM below the
    # flap tip; measure the flap's side-edge inset at that height along
    # the shoulder cubic and keep ≥ 2 mm of web beside each slit end.
    # Scales the slit down (never below 3 mm) instead of tearing.
    slit_edge_inset = _shoulder_inset_at_y(
        _SLIT_FROM_TIP_MM, curve_h, tuck_inset, _TUCK_SHOULDER_K,
    )
    slit_w, slit_web, slit_reduced = _apply_slit_web_guard(slit_w, W, slit_edge_inset)

    # ---- Guards ----
    _assert_ge("width_mm",        W,            12.0)
    _assert_ge("depth_mm",        D,            12.0)
    _assert_ge("height_mm",       H,            60.0)
    _assert_ge("top_tuck_h",      top_tuck_h,   12.0)
    if not slit_reduced:
        _assert_ge("slit_width",  slit_w,        _MIN_SLIT_WIDTH_MM)
    else:
        # Web guard already enforced the ≥ 3 mm functional floor.
        _assert_ge("slit_width",  slit_w,        _ABS_MIN_SLIT_MM)
    _assert_ge("tuck_inset",      tuck_inset,    1.5)
    # With the adaptive chamfer this holds for any depth ≥ the 12 mm floor; the
    # guard stays as a defensive invariant on the resulting flap geometry.
    _assert_ge("dust_top_chamfer", top_chamfer,  1.0)

    # ---- Board-thickness compensation (opt-in; see module docstring) ----
    # t_comp = 0 keeps the legacy raw-sum layout byte-identical to the
    # engine reference snapshot; with compensation on, the ECMA rule is
    # front = W, sides = D + t each, back = W + 2t (glue-joint panel).
    comp = c.thickness_compensation
    t_comp = board_thickness if comp else 0.0
    back_w  = W + 2.0 * t_comp
    side_w  = D + t_comp
    front_w = W
    # DECISION-015: shoulder lock notch = board_thickness × 2, cut at
    # each base corner of the two active tuck flaps. Zero when
    # compensation is off (legacy geometry).
    lock_notch = 2.0 * t_comp

    # ---- Contract X coordinates ----
    x0 = 0.0
    x1 = G
    x2 = x1 + back_w
    x3 = x2 + side_w
    x4 = x3 + front_w
    x5 = x4 + side_w

    # ---- Contract Y coordinates ----
    y0 = 0.0
    y1 = top_tuck_h
    y2 = top_tuck_h + H
    # Bottom zone depth: a mirrored tuck flap (STE/reverse) or the crash-lock
    # base (auto_bottom). y3 is the bottom edge of the flat.
    bottom_zone = bottom_tuck_h if cfg.bottom_mode == "tuck" else auto_h
    y3 = top_tuck_h + H + bottom_zone

    flat_w = x5 - x0    # = G + 2D + 2W (+ 4t with compensation)
    flat_h = y3 - y0    # = top_tuck_h + H + bottom_tuck_h

    # ---- Main body (x1..x5, y1..y2) ----
    body_rect = Polygon([(x1, y1), (x5, y1), (x5, y2), (x1, y2)])
    # [his final goal, B2] the thumb notch: half round, in the middle of the top edge of the panel the lid closes onto
    thumb_notch = None
    if cfg.print_ready:
        _closes = {"back": (x3, x4), "front": (x1, x2)}[cfg.top_tuck]
        _r = min(_THUMB_NOTCH_MAX_R_MM, _THUMB_NOTCH_SHARE * (_closes[1] - _closes[0]))
        _cx = (_closes[0] + _closes[1]) / 2.0
        body_rect = Polygon(body_rect.difference(Point(_cx, y1).buffer(_r, quad_segs=16)).exterior.coords)
        thumb_notch = {"panel": "front" if cfg.top_tuck == "back" else "back", "cx": _cx, "y": y1, "r": _r}

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
    # curve_h = W × 0.218   (vertical span of the shoulder; computed in
    #                        the derived-heights block above)

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

        With thickness compensation on (lock_notch > 0), a DECISION-015
        square lock notch of side ``lock_notch`` is cut into each base
        corner: the side edges stop ``lock_notch`` above the base and
        step inward before rejoining the (shortened) base edge. The
        n = 0 branches reproduce the legacy path byte-for-byte.
        """
        top_l = x_l + tuck_inset
        top_r = x_r - tuck_inset
        n = lock_notch
        path: list[Primitive] = []
        if n > 0.0:
            # left base corner notch (open toward the flap side edge)
            path.append(LineSeg((x_l + n, y1), (x_l + n, y1 - n)))
            path.append(LineSeg((x_l + n, y1 - n), (x_l, y1 - n)))
            path.append(LineSeg((x_l, y1 - n), (x_l, y0 + curve_h)))
        else:
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
        if n > 0.0:
            # right base corner notch
            path.append(LineSeg((x_r, y0 + curve_h), (x_r, y1 - n)))
            path.append(LineSeg((x_r, y1 - n), (x_r - n, y1 - n)))
            path.append(LineSeg((x_r - n, y1 - n), (x_r - n, y1)))
            path.append(LineSeg((x_r - n, y1), (x_l + n, y1)))
        else:
            path.append(LineSeg((x_r, y0 + curve_h), (x_r, y1)))
            path.append(LineSeg((x_r, y1), (x_l, y1)))
        return path

    def _tuck_bot_path(x_l: float, x_r: float) -> list[Primitive]:
        """Mirror of _tuck_top_path across y = (y2 + y3) / 2."""
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
        if n > 0.0:
            path.append(LineSeg((x_r, y3 - curve_h), (x_r, y2 + n)))
            path.append(LineSeg((x_r, y2 + n), (x_r - n, y2 + n)))
            path.append(LineSeg((x_r - n, y2 + n), (x_r - n, y2)))
            path.append(LineSeg((x_r - n, y2), (x_l + n, y2)))
        else:
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
    # Per-style panel assignment. STE: top tuck on back, bottom on front.
    # Reverse: swapped. The two side panels always carry dust flaps.
    _cols = {"back": (x1, x2), "front": (x3, x4)}
    ttl, ttr = _cols[cfg.top_tuck]        # top tuck panel columns
    btl, btr = _cols[cfg.bottom_tuck]     # bottom tuck panel columns (tuck mode)
    has_bottom_tuck = cfg.bottom_mode == "tuck"

    # Top tuck flap (present in every style).
    tuck_back_top_primitives = _tuck_top_path(ttl, ttr)
    tuck_back_top_raw = _tuck_top(ttl, ttr)
    top_slit_cx = (ttl + ttr) / 2.0
    slit_top_cy = y0 + _SLIT_FROM_TIP_MM + _SLIT_HEIGHT_MM / 2.0
    slit_top_stadium = _stadium_polygon(
        cx=top_slit_cx, cy=slit_top_cy, width=slit_w, height=_SLIT_HEIGHT_MM,
    )
    tuck_back_top = tuck_back_top_raw.difference(slit_top_stadium)
    if not tuck_back_top.is_valid:
        raise ValueError("top tuck polygon invalid after stadium-slit cutout")

    # Bottom tuck flap + friction slit — tuck styles only. The auto-lock
    # base (below) replaces both the bottom tuck and the bottom dust flaps.
    tuck_front_bot_primitives = None
    tuck_front_bot = None
    bot_slit_cx = None
    slit_bot_cy = None
    if has_bottom_tuck:
        tuck_front_bot_primitives = _tuck_bot_path(btl, btr)
        tuck_front_bot_raw = _tuck_bot(btl, btr)
        bot_slit_cx = (btl + btr) / 2.0
        slit_bot_cy = y3 - _SLIT_FROM_TIP_MM - _SLIT_HEIGHT_MM / 2.0
        slit_bot_stadium = _stadium_polygon(
            cx=bot_slit_cx, cy=slit_bot_cy, width=slit_w, height=_SLIT_HEIGHT_MM,
        )
        tuck_front_bot = tuck_front_bot_raw.difference(slit_bot_stadium)
        if not tuck_front_bot.is_valid:
            raise ValueError("bottom tuck polygon invalid after stadium-slit cutout")

    # ---- Dust flaps (DECISION-016, measured from AI file) ----
    # 6-vertex shape: 3 mm base-corner notch step, 6 mm top chamfer each side.
    # Height = D × 0.631, CLAMPED (Milestone 9.1 / audit C4) so the dust
    # flaps always stay _DUST_TUCK_CLEARANCE_MM below the tuck zone: on
    # deep-narrow cartons (D > ~1.945·W) the raw D-derived height would
    # exceed the W-derived tuck flaps and escape the sheet top —
    # violating DECISION-004 and producing an unfoldable die. Square
    # products never clamp (0.631·W < 1.227·W − 2 for all W ≥ 12), so
    # the reference geometry is untouched. Top width = D − 2·top_chamfer.
    dust_h_nominal = D * _DUST_HEIGHT_FACTOR
    dust_h_max     = top_tuck_h - _DUST_TUCK_CLEARANCE_MM
    dust_clamped   = dust_h_nominal > dust_h_max
    dust_h         = min(dust_h_nominal, dust_h_max)
    base_notch     = _DUST_BASE_NOTCH_MM
    # Shape validity: the 6-vertex dust flap degenerates if its height
    # drops to the base-notch step. Unreachable within schema bounds
    # (W ≥ 12 → dust_h_max ≥ 12.7); kept as a defensive invariant.
    _assert_ge("dust_flap_height", dust_h, base_notch + 1.0)
    # top_chamfer computed adaptively in the guards block above (scales down on
    # shallow cartons); reused here so the flap geometry matches the guard.

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
    # Bottom dust flaps (tuck styles) OR crash-lock base (auto_bottom).
    dust_sl_bot = None
    dust_sr_bot = None
    auto_lock_flaps: list[Polygon] = []
    if has_bottom_tuck:
        dust_sl_bot = _dust_bot(x2, x3)
        dust_sr_bot = _dust_bot(x4, x5)
    else:
        # PROVISIONAL crash-lock auto-bottom: one downward lock flap per body
        # panel, each a trapezoid with a glue-lap chamfer, folding toward the
        # centre. Real crash-lock geometry needs a measured reference file
        # (see MEASUREMENT_NEEDED.md); until then this is a foldable, bounds-
        # valid ECMA approximation the dimension gate flags for human review.
        def _lock_flap(x_l: float, x_r: float) -> Polygon:
            ch = min(_DUST_TOP_CHAMFER_MM, (x_r - x_l - _DUST_MIN_TOP_WIDTH_MM) / 2.0)
            return Polygon([
                (x_l,      y2),
                (x_r,      y2),
                (x_r - ch, y2 + auto_h),
                (x_l + ch, y2 + auto_h),
            ])
        auto_lock_flaps = [
            _lock_flap(x1, x2), _lock_flap(x2, x3),
            _lock_flap(x3, x4), _lock_flap(x4, x5),
        ]

    # ---- Union into the full cut polygon ----
    _parts = [body_rect, glue_poly, tuck_back_top, dust_sl_top, dust_sr_top]
    if has_bottom_tuck:
        _parts += [tuck_front_bot, dust_sl_bot, dust_sr_bot]
    else:
        _parts += auto_lock_flaps
    cut_polygon = unary_union(_parts)
    if cut_polygon.geom_type != "Polygon":
        raise ValueError(
            f"cut_polygon must be a single Polygon, got {cut_polygon.geom_type}"
        )
    if not cut_polygon.is_valid:
        raise ValueError("cut_polygon is invalid after union")

    # ---- Post-generation invariant (Milestone 9.1 / audit C4) ----
    # The cut path must lie on the declared flat sheet. Anything outside
    # [0, flat_w] × [0, flat_h] (± epsilon) cannot be die-cut from the
    # sheet the spec table promises — refuse to hand it downstream.
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

    # ---- Fold lines ----
    # Four vertical body creases are unconditional (DECISION-001/008: body
    # height only, starting at the glue-tab edge).
    fold_lines: list[tuple[float, float, float, float]] = [
        (x1, y1, x1, y2),
        (x2, y1, x2, y2),
        (x3, y1, x3, y2),
        (x4, y1, x4, y2),
    ]
    # Horizontal creases: see DECISION-021. cfg.per_hinge_creases False
    # reproduces the defective full-width v1.0 form byte-for-byte.
    _columns = {
        "back": (x1, x2), "side_left": (x2, x3),
        "front": (x3, x4), "side_right": (x4, x5),
    }
    if cfg.per_hinge_creases:
        fold_lines += _hinge_creases(
            _columns, y1, y2, cfg, lock_notch, has_bottom_tuck)
    else:
        fold_lines += [(x1, y1, x5, y1), (x1, y2, x5, y2)]

    slit_lines: list[tuple[float, float, float, float]] = []
    # [his final goal, B2] each tuck fold creased between its two lock slits, cut along it from the flap's side edges
    tuck_folds = []
    if cfg.print_ready:
        lid = side_w                     # the lid closes across the carton's depth: as deep as a side panel
        for where, (xl, xr), height, y_fold in (
                ("top", (ttl, ttr), top_tuck_h, y1 - lid),
                *((("bottom", (btl, btr), bottom_tuck_h, y2 + lid),) if has_bottom_tuck else ())):
            if height - lid < _MIN_TONGUE_MM:
                continue
            sl = min(_LOCK_SLIT_MAX_MM, max(_LOCK_SLIT_MIN_MM, _LOCK_SLIT_SHARE * (xr - xl)))
            fold_lines.append((xl + sl, y_fold, xr - sl, y_fold))
            slit_lines += [(xl, y_fold, xl + sl, y_fold), (xr - sl, y_fold, xr, y_fold)]
            tuck_folds.append({"tuck": where, "y": y_fold, "x_l": xl, "x_r": xr, "slit_mm": sl,
                               "tongue_mm": round(height - lid, 3)})

    # ---- Panels ----
    # Widths carry the per-panel thickness allowances (equal to the raw
    # W/D manufacture dimensions when compensation is off).
    panels = [
        Panel("glue_tab",   x=x0, y=y1, width=G,       height=y2 - y1),
        Panel("back",       x=x1, y=y1, width=back_w,  height=y2 - y1),
        Panel("side_left",  x=x2, y=y1, width=side_w,  height=y2 - y1),
        Panel("front",      x=x3, y=y1, width=front_w, height=y2 - y1),
        Panel("side_right", x=x4, y=y1, width=side_w,  height=y2 - y1),
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

    # Component ids follow the panel that carries each flap so the reverse
    # style is labelled honestly (top-front-tuck / bottom-back-tuck). STE
    # keeps its original ids (top-back-tuck / bottom-front-tuck).
    top_tuck_id = f"top-{cfg.top_tuck}-tuck"
    components = [
        ("main-body",          body_rect),
        ("glue-tab",           glue_poly),
        (top_tuck_id,          tuck_back_top),
        ("top-left-dust",      dust_sl_top),
        ("top-right-dust",     dust_sr_top),
    ]
    stadium_cutouts = [
        (f"top-{cfg.top_tuck}-slit", top_slit_cx, slit_top_cy, slit_w, _SLIT_HEIGHT_MM),
    ]
    # Primitive paths only for components whose outline includes curves.
    # The exporter uses these to emit true `C` Bezier commands; every
    # other component falls back to polygon-to-polyline.
    component_paths = {top_tuck_id: tuck_back_top_primitives}

    if has_bottom_tuck:
        bottom_tuck_id = f"bottom-{cfg.bottom_tuck}-tuck"
        components += [
            (bottom_tuck_id,     tuck_front_bot),
            ("bottom-left-dust",  dust_sl_bot),
            ("bottom-right-dust", dust_sr_bot),
        ]
        stadium_cutouts.append(
            (f"bottom-{cfg.bottom_tuck}-slit", bot_slit_cx, slit_bot_cy,
             slit_w, _SLIT_HEIGHT_MM)
        )
        component_paths[bottom_tuck_id] = tuck_front_bot_primitives
    else:
        components += [
            ("bottom-back-lock",  auto_lock_flaps[0]),
            ("bottom-sl-lock",    auto_lock_flaps[1]),
            ("bottom-front-lock", auto_lock_flaps[2]),
            ("bottom-sr-lock",    auto_lock_flaps[3]),
        ]

    # ---- Human-readable geometry notes (surfaced on the spec sheet) ----
    notes: list[str] = []
    if dust_clamped:
        notes.append(
            f"dust flap reduced from {dust_h_nominal:.2f} mm to {dust_h:.2f} mm "
            f"to stay {_DUST_TUCK_CLEARANCE_MM:g} mm below the tuck zone "
            "(DECISION-004 clamp)"
        )
    if slit_reduced:
        notes.append(
            f"friction slit reduced to {slit_w:.2f} mm to preserve a "
            f"{_MIN_SLIT_WEB_MM:g} mm web beside each slit end (DECISION-017)"
        )
    if comp and t_comp > 0.0:
        notes.append(
            f"board-thickness compensation active (t = {t_comp:g} mm): "
            f"back +{2.0 * t_comp:g} mm, sides +{t_comp:g} mm each, "
            f"lock notches {lock_notch:g} mm (DECISION-015)"
        )
    if cfg.provisional:
        notes.append(
            f"{cfg.structure_type} geometry is PROVISIONAL (no measured "
            "reference file) — confirm the structure at the dimension gate "
            "before releasing to production"
        )

    coords = DielineCoordinates(
        flat_width_mm=round(flat_w, 4),
        flat_height_mm=round(flat_h, 4),
        panels=panels,
        fold_lines=fold_lines,
        cut_polygon=cut_polygon,
        bleed_polygon=bleed_polygon,
        safe_polygon=safe_polygon,
        tuck_flap_polygons=[
            p for p in (tuck_back_top, tuck_front_bot) if p is not None
        ],
        dust_flap_polygons=[
            p for p in (dust_sl_top, dust_sr_top, dust_sl_bot, dust_sr_bot)
            if p is not None
        ],
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
            # Milestone 12.1 — carton style
            "structure_type": cfg.structure_type,
            # Which published geometry version produced this die. Consumers
            # (structural checklist, Gate-2 validator) resolve the registry
            # against it, so a v1.0 job is checked against v1.0's contract.
            "template_version": cfg.version,
            "per_hinge_creases": cfg.per_hinge_creases,
            # [his final goal, B2] the tuck folds, their slits and the thumb notch (v1.3; none before it)
            "tuck_folds": tuck_folds,
            "thumb_notch": thumb_notch,
            "provisional": cfg.provisional,
            "bottom_mode": cfg.bottom_mode,
            "top_tuck_panel": cfg.top_tuck,
            "bottom_tuck_panel": cfg.bottom_tuck if has_bottom_tuck else None,
            "auto_bottom_height_mm": auto_h if not has_bottom_tuck else None,
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
            # Milestone 9.1 — dust clamp annotation (spec sheet notes it)
            "dust_flap_height_nominal_mm": dust_h_nominal,
            "dust_flap_clamped": dust_clamped,
            # Milestone 9.3 — DECISION-017 slit web guard
            "slit_web_mm": slit_web,
            "slit_reduced": slit_reduced,
            # Milestone 9.2 — board-thickness compensation (DECISION-015)
            "thickness_compensation": comp,
            "panel_allowance_back_mm": 2.0 * t_comp,
            "panel_allowance_side_mm": t_comp,
            "lock_notch_mm": lock_notch,
            "notes": notes,
        },
    )
    coords.validate()
    return coords
