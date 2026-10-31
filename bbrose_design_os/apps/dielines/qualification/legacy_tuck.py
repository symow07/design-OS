"""Legacy STE 1.1 qualification (2A-9C slice 1).

``straight_tuck_end_carton/1.1`` is the locked engine geometry
(DECISION-016 ratio formulas measured from a square 28×28×120 reference).
Qualification derives its HONEST domain from the engine's own rules — and
that domain is narrow, because two ratio formulas fail the engine's own
folded-collision checks outside a band:

  * dust flaps are D-derived (0.631·D each) but fold across the W
    opening: they collide whenever W < 1.262·D — INCLUDING the measured
    28×28×120 reference itself (overlap 7.3 mm);
  * the tuck is W-derived (1.227·W) because the square reference could
    not distinguish W from D: on wide-short cartons the lip
    (1.227·W − D) exceeds H/2 — including the historical 90×25×92 STE
    die once offered to task #50.

Per the versioning rule these defects are NOT fixed here: 1.1 stays
byte-stable for historical reproduction; the qualified domain simply
excludes the defective regions, and the correction (D-derived closure,
DECISION-019-style) is proposed as version 1.2 — a review decision.

IMPORTANT semantic difference from the opposing-tuck archetype: the 1.1
GENERATOR does not fail closed on domain violations (historical jobs must
regenerate exactly). DIMENSION_COMBINATION_UNSUPPORTED is enforced at the
qualification layer, the qualify_dimensions endpoint and the dimension-
gate UI — every path that creates NEW dies.
"""
from __future__ import annotations

from apps.dielines.geometry.ecma_ste import paths_content_hash
from apps.dielines.qualification.contract import (
    KIND_ALLOWANCE,
    KIND_CONSTANT,
    KIND_DERIVED,
    KIND_USER,
    ParameterContract,
    ParameterEntry,
)
from apps.dielines.qualification.domain import _Constraint, _rng

TEMPLATE_ID = "straight_tuck_end_carton"
TEMPLATE_VERSION = "1.1"

_TUCK_F = 1.227
_DUST_F = 0.631
_LIP_MIN_NOTE = "engine reconciliation rule: lip < H/2 (strict)"

STE_CONTRACT = ParameterContract(
    schema_version="dieline_parameter_contract/1.0",
    template_key="straight_tuck_end_carton/1.1",
    entries=(
        ParameterEntry("width_mm", KIND_USER, "mm",
                       "MANUFACTURE main-panel width (score to score)",
                       12.0, 300.0),
        ParameterEntry("depth_mm", KIND_USER, "mm",
                       "MANUFACTURE side-panel width", 12.0, 300.0),
        ParameterEntry("height_mm", KIND_USER, "mm",
                       "MANUFACTURE body height", 60.0, 600.0),
        ParameterEntry("board_thickness_mm", KIND_USER, "mm",
                       "board caliper t (compensated mode)", 0.3, 1.0,
                       default=0.35),
        ParameterEntry("glue_tab_mm", KIND_USER, "mm", "glue-flap width",
                       6.0, 15.0, default=10.0),
        ParameterEntry("bleed_mm", KIND_USER, "mm", "bleed", 2.0, 5.0,
                       default=3.0),
        ParameterEntry("safe_margin_mm", KIND_USER, "mm", "safe inset",
                       3.0, 8.0, default=4.0),
        ParameterEntry("tuck_height_factor", KIND_CONSTANT, "ratio",
                       "tuck total height = W x factor (DECISION-016; "
                       "W-derived because the square reference hid the "
                       "W/D distinction)", value=_TUCK_F),
        ParameterEntry("tuck_inset_factor", KIND_CONSTANT, "ratio",
                       "shoulder inset = W x factor", value=0.227),
        ParameterEntry("tuck_curve_factor", KIND_CONSTANT, "ratio",
                       "shoulder vertical span = W x factor", value=0.218),
        ParameterEntry("dust_height_factor", KIND_CONSTANT, "ratio",
                       "dust height = D x factor", value=_DUST_F),
        ParameterEntry("slit_width_factor", KIND_CONSTANT, "ratio",
                       "friction slit = W x factor (PROVISIONAL, "
                       "DECISION-017)", value=0.327),
        ParameterEntry("shoulder_k", KIND_CONSTANT, "ratio",
                       "cubic shoulder tangent factor (PROVISIONAL)",
                       value=0.55228474983),
        ParameterEntry("dust_base_notch_mm", KIND_CONSTANT, "mm",
                       "dust base-corner notch", value=3.0),
        ParameterEntry("dust_top_chamfer_mm", KIND_CONSTANT, "mm",
                       "dust top chamfer (adaptive floor 3 mm)", value=6.0),
        ParameterEntry("slit_height_mm", KIND_CONSTANT, "mm",
                       "stadium slit height", value=1.5),
        ParameterEntry("min_slit_web_mm", KIND_CONSTANT, "mm",
                       "solid board beside each slit end", value=2.0),
        ParameterEntry("tuck_total_mm", KIND_DERIVED, "mm",
                       "tuck flap height", formula="W x 1.227"),
        ParameterEntry("tuck_lip_mm", KIND_DERIVED, "mm",
                       "lip past the opening", formula="W x 1.227 - D"),
        ParameterEntry("dust_height_mm", KIND_DERIVED, "mm",
                       "dust flap height", formula="D x 0.631"),
        ParameterEntry("friction_slit_mm", KIND_DERIVED, "mm",
                       "slit width", formula="max(5, W x 0.327)"),
        ParameterEntry("lock_notch_mm", KIND_ALLOWANCE, "mm",
                       "DECISION-015 shoulder lock notch",
                       formula="2t (compensated mode)"),
        ParameterEntry("panel_allowances", KIND_ALLOWANCE, "mm",
                       "back +2t, sides +t each, front reference",
                       formula="ECMA main-panel reference"),
        ParameterEntry("score_compression_mm", KIND_ALLOWANCE, "mm",
                       "not modelled", value=0.0),
    ),
)


def _slit_web_unreduced(p: dict) -> str | None:
    """DECISION-017 numeric edge: the nominal friction slit must fit
    without reduction — a reduced slit is a silently altered formula."""
    from apps.dielines.geometry.engine import (
        _apply_slit_web_guard,
        _shoulder_inset_at_y,
        _MIN_SLIT_WIDTH_MM,
        _SLIT_FROM_TIP_MM,
        _SLIT_WIDTH_FACTOR,
        _TUCK_CURVE_H_FACTOR,
        _TUCK_INSET_FACTOR,
        _TUCK_SHOULDER_K,
    )
    W = p["width_mm"]
    slit_w = max(_MIN_SLIT_WIDTH_MM, W * _SLIT_WIDTH_FACTOR)
    inset = _shoulder_inset_at_y(
        _SLIT_FROM_TIP_MM, W * _TUCK_CURVE_H_FACTOR,
        W * _TUCK_INSET_FACTOR, _TUCK_SHOULDER_K)
    try:
        _, web, reduced = _apply_slit_web_guard(slit_w, W, inset)
    except Exception as exc:  # noqa: BLE001 — the guard itself refused
        return f"SLIT_WEB_UNREDUCED: {exc}"
    if reduced:
        return (f"SLIT_WEB_UNREDUCED: nominal slit {slit_w:.2f} mm would "
                f"be reduced to keep a 2 mm web at W = {W:g} — a reduced "
                "slit is an altered formula, outside the qualified domain")
    return None


STE_DOMAIN = (
    _rng("board_thickness_mm", 0.3, 1.0, "BOARD_RANGE",
         "manufacturing caliper range (compensated mode; the t = 0 legacy "
         "layout is covered by the byte-stability snapshot, not this "
         "domain)"),
    _rng("width_mm", 12.0, 300.0, "WIDTH_RANGE", "print-shop budget"),
    _rng("depth_mm", 12.0, 300.0, "DEPTH_RANGE", "print-shop budget"),
    _rng("height_mm", 60.0, 600.0, "HEIGHT_RANGE", "print-shop budget"),
    _rng("glue_tab_mm", 6.0, 15.0, "GLUE_RANGE", "adhesive practice"),
    _rng("bleed_mm", 2.0, 5.0, "BLEED_RANGE", "prepress practice"),
    _rng("safe_margin_mm", 3.0, 8.0, "SAFE_RANGE", "prepress practice"),
    _Constraint(
        "HEIGHT_GT_WIDTH", "H > W",
        "schema tuck-carton proportion rule",
        lambda p: None if p["height_mm"] > p["width_mm"] else
        f"HEIGHT_GT_WIDTH: H = {p['height_mm']:g} must exceed "
        f"W = {p['width_mm']:g}"),
    _Constraint(
        "HEIGHT_GT_DEPTH", "H > D",
        "schema tuck-carton proportion rule",
        lambda p: None if p["height_mm"] > p["depth_mm"] else
        f"HEIGHT_GT_DEPTH: H = {p['height_mm']:g} must exceed "
        f"D = {p['depth_mm']:g}"),
    _Constraint(
        "DEPTH_VS_WIDTH_RATIO", "D <= 2.5 W",
        "schema Milestone 9.1 rule (dust flap collapse beyond)",
        lambda p: None if p["depth_mm"] <= 2.5 * p["width_mm"] else
        f"DEPTH_VS_WIDTH_RATIO: D = {p['depth_mm']:g} exceeds 2.5 x W"),
    _Constraint(
        "GLUE_VS_SIDE", "D + t >= G + 3",
        "the glue flap laps inside the side span",
        lambda p: None if p["depth_mm"] + p["board_thickness_mm"]
        >= p["glue_tab_mm"] + 3.0 else
        f"GLUE_VS_SIDE: side span {p['depth_mm'] + p['board_thickness_mm']:g}"
        f" mm must be >= G + 3 = {p['glue_tab_mm'] + 3.0:g} mm"),
    _Constraint(
        "DUST_PAIR_CLEARANCE", "W - 2 x 0.631 D >= 0",
        "FOLDED (engine's own reconciliation rule): D-derived dust flaps "
        "fold across the W opening; W < 1.262 D collides — the measured "
        "28x28x120 reference itself violates this (overlap 7.3 mm)",
        lambda p: None if p["width_mm"] - 2 * _DUST_F * p["depth_mm"]
        >= 0.0 else
        f"DUST_PAIR_CLEARANCE: folded dust clearance = "
        f"{p['width_mm'] - 2 * _DUST_F * p['depth_mm']:.2f} mm < 0 "
        f"(needs W >= {2 * _DUST_F:g} x D)"),
    _Constraint(
        "TUCK_LIP_VS_HEIGHT", "1.227 W - D < H / 2",
        "FOLDED (engine's own reconciliation rule): the W-derived tuck "
        "lip must stay far shorter than the body — wide-short cartons "
        "(incl. the historical 90x25x92 STE die) violate this",
        lambda p: None
        if _TUCK_F * p["width_mm"] - p["depth_mm"] < p["height_mm"] / 2.0
        else
        f"TUCK_LIP_VS_HEIGHT: lip = "
        f"{_TUCK_F * p['width_mm'] - p['depth_mm']:.2f} mm must be < "
        f"H/2 = {p['height_mm'] / 2.0:g} mm"),
    _Constraint(
        "DUST_CLAMP_BOUNDARY", "0.631 D <= 1.227 W - 2",
        "EXPLICIT clamp edge (mandated): beyond it the engine clamps the "
        "dust height — a clamped flap is an altered formula, outside the "
        "qualified domain",
        lambda p: None if _DUST_F * p["depth_mm"]
        <= _TUCK_F * p["width_mm"] - 2.0 else
        f"DUST_CLAMP_BOUNDARY: nominal dust {_DUST_F * p['depth_mm']:.2f} "
        f"mm exceeds the tuck zone minus 2 mm "
        f"({_TUCK_F * p['width_mm'] - 2.0:.2f})"),
    _Constraint(
        "SLIT_WEB_UNREDUCED",
        "web >= 2 mm at the nominal slit width (numeric, DECISION-017)",
        "the friction slit must fit without the web-guard reduction",
        _slit_web_unreduced),
)


def collision_report(coords) -> dict:
    """Folded + flat checks for the legacy straight-tuck closure, measured
    from the emitted geometry (stadium friction slits + 2t lock notches)."""
    d = coords.derived
    W, D, H = coords.dimensions.manufacture
    dust = float(d.get("dust_flap_height_mm", 0.0))
    tuck = float(d.get("tuck_flap_height_mm", 0.0))
    lip = max(tuck - D, 0.0)
    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("straight_attachment_preserved",
        d.get("top_tuck_panel") == "back"
        and d.get("bottom_tuck_panel") == "front",
        f"top tuck on {d.get('top_tuck_panel')}, bottom on "
        f"{d.get('bottom_tuck_panel')}")
    add("folded_dust_flap_pair_clearance", W - 2 * dust >= 0.0,
        f"dust reach {dust:g} mm each across the {W:g} mm opening -> "
        f"{W - 2 * dust:.2f} mm gap")
    add("dust_below_tuck_zone", tuck - dust >= 2.0,
        f"tuck zone {tuck:g} mm vs dust {dust:g} mm")
    add("dust_unclamped", not d.get("dust_flap_clamped"),
        "dust flap emitted at its nominal formula height")
    add("tuck_lip_vs_height", lip < H / 2.0,
        f"lip {lip:.2f} mm vs H/2 = {H / 2.0:g} mm")
    add("friction_slits_present", len(coords.stadium_cutouts) == 2,
        f"{len(coords.stadium_cutouts)} stadium slits (top + bottom tuck)")
    add("slit_unreduced", not d.get("slit_reduced"),
        f"slit {d.get('slit_width_mm')} mm at the nominal formula width")
    add("slit_web", float(d.get("slit_web_mm") or 0) >= 2.0,
        f"web {d.get('slit_web_mm')} mm beside each slit end")
    add("lock_notches_when_compensated",
        (not d.get("thickness_compensation"))
        or float(d.get("lock_notch_mm") or 0) > 0,
        f"lock notch {d.get('lock_notch_mm')} mm (2t)")
    comps = coords.components
    worst = 0.0
    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            worst = max(worst, comps[i][1].intersection(comps[j][1]).area)
    add("component_area_overlap", worst < 1e-6,
        f"largest pairwise flat overlap {worst:.8f} mm^2")
    add("cut_contour_closed_valid",
        coords.cut_polygon.is_valid
        and coords.cut_polygon.geom_type == "Polygon",
        "cut contour is one valid closed region")
    cb, bb = coords.cut_polygon.bounds, coords.bleed_polygon.bounds
    grow = min(cb[0] - bb[0], cb[1] - bb[1], bb[2] - cb[2], bb[3] - cb[3])
    add("bleed_contour_complete", grow > 0,
        f"bleed offset outward on every side (min growth {grow:.3f} mm)")
    return {"checks": checks, "all_ok": all(c["ok"] for c in checks)}


def geometry_content_hashes(coords) -> dict:
    cut_paths = [list(coords.cut_polygon.exterior.coords)]
    cut_paths += [[(a, b), (cx, dy)] for (a, b, cx, dy) in coords.slit_lines]
    crease_paths = [[(a, b), (cx, dy)]
                    for (a, b, cx, dy) in coords.fold_lines]
    bleed_paths = [list(coords.bleed_polygon.exterior.coords)]
    return {
        "cut_path_hash": paths_content_hash(cut_paths),
        "crease_path_hash": paths_content_hash(crease_paths),
        "bleed_path_hash": paths_content_hash(bleed_paths),
    }


def ste_adapter():
    from apps.dielines.qualification.closure import STE_LEGACY_CLOSURE
    from apps.dielines.qualification.runner import ArchetypeAdapter
    return ArchetypeAdapter(
        template=TEMPLATE_ID, version=TEMPLATE_VERSION,
        panel_sequence=["glue_tab", "back", "side_left", "front",
                        "side_right"],
        closure=STE_LEGACY_CLOSURE,
        domain_constraints=STE_DOMAIN,
        dims_semantics="manufacture",
        in_domain_sampler=sample_in_domain,
        _collision=collision_report,
        _hashes=geometry_content_hashes,
    )


def sample_in_domain(rng) -> dict | None:
    """Deterministic in-domain sampler for the STE 1.1 sweep."""
    t = rng.choice([0.3, 0.4, 0.5, 0.7, 0.8, 1.0])
    glue = rng.choice([6.0, 10.0, 12.0, 15.0])
    d_min = max(12.0, glue + 3.0 - t)
    depth = round(rng.uniform(d_min, 150.0), 1)
    w_min = max(12.0, 2 * _DUST_F * depth + 0.2)
    # leave room for H <= 600 under the lip rule: H > 2*(1.227W - D)
    w_max = min(300.0, (depth + 299.0) / _TUCK_F, 2.5 * 300.0)
    if w_min >= w_max - 0.5:
        return None
    width = round(rng.uniform(w_min, w_max), 1)
    if depth > 2.5 * width:
        return None
    user = {"width_mm": width, "depth_mm": depth,
            "board_thickness_mm": t, "glue_tab_mm": glue,
            "bleed_mm": rng.choice([2.0, 3.0, 5.0]),
            "safe_margin_mm": rng.choice([3.0, 4.0, 8.0])}
    h_min = max(width, depth, 2 * (_TUCK_F * width - depth)) + 0.3
    if h_min >= 599.0:
        return None
    user["height_mm"] = round(rng.uniform(max(h_min, 60.1), 600.0), 1)
    if _slit_web_unreduced(user):
        return None
    return user


# contract available whenever the adapter is importable
from apps.dielines.qualification.contract import register_contract  # noqa: E402

register_contract(STE_CONTRACT)


__all__ = ["STE_CONTRACT", "STE_DOMAIN", "ste_adapter", "collision_report",
           "geometry_content_hashes", "TEMPLATE_ID", "TEMPLATE_VERSION"]
