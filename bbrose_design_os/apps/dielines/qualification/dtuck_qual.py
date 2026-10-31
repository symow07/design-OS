"""D-derived STE/RTE 1.2 qualification (2A-9D commits 2 & 3).

`straight_tuck_end_carton/1.2` and `reverse_tuck_end_carton/1.2` share the
D-derived closure (major tuck reach = D + 16 mm lip, shoulder span = 0.5 x
lip). STE 1.2 keeps the straight attachment (top=back, bottom=front); RTE
1.2 is the mirror (top=front, bottom=back) and carries an independent
mirror audit.

The honest domain is 1.1's MINUS the two defects the D-derived model
removes:
  * lip-vs-height: the lip is a fixed 16 mm < H/2 for any H >= 60, so it
    never binds — wide-short cartons (incl. 90x25x92, which 1.1 rejected)
    are now supported;
  * dust clamp: the D+16 tuck zone always exceeds the 0.631 D dust, so the
    DECISION-004 clamp never engages.
The W >= 1.262 D dust-clearance edge is UNCHANGED from 1.1 (shared with the
validated Skynte model) — 1.2 widens only in the wide-short direction.
"""
from __future__ import annotations

from apps.dielines.geometry.ecma_ste import paths_content_hash
from apps.dielines.geometry.engine import (
    _D_DERIVED_CURVE_RATIO,
    _D_DERIVED_LIP_MM,
)
from apps.dielines.qualification.contract import (
    KIND_ALLOWANCE,
    KIND_CONSTANT,
    KIND_DERIVED,
    KIND_USER,
    ParameterContract,
    ParameterEntry,
    register_contract,
)
from apps.dielines.qualification.domain import _Constraint, _rng

_DUST_F = 0.631
_LIP = _D_DERIVED_LIP_MM              # 16.0
_CURVE_H = _D_DERIVED_CURVE_RATIO * _LIP   # 8.0 (lip-derived, fixed)


def _dtuck_slit_web_unreduced(p: dict) -> str | None:
    """DECISION-017 slit-web edge computed with the 1.2 (lip-derived)
    shoulder span — NOT the W-ratio curve. The friction slit must fit
    without the web-guard reduction."""
    from apps.dielines.geometry.engine import (
        _apply_slit_web_guard,
        _shoulder_inset_at_y,
        _MIN_SLIT_WIDTH_MM,
        _SLIT_FROM_TIP_MM,
        _SLIT_WIDTH_FACTOR,
        _TUCK_INSET_FACTOR,
        _TUCK_SHOULDER_K,
    )
    W = p["width_mm"]
    slit_w = max(_MIN_SLIT_WIDTH_MM, W * _SLIT_WIDTH_FACTOR)
    inset = _shoulder_inset_at_y(_SLIT_FROM_TIP_MM, _CURVE_H,
                                 W * _TUCK_INSET_FACTOR, _TUCK_SHOULDER_K)
    try:
        _, _web, reduced = _apply_slit_web_guard(slit_w, W, inset)
    except Exception as exc:  # noqa: BLE001 — the guard itself refused
        return f"SLIT_WEB_UNREDUCED: {exc}"
    if reduced:
        return (f"SLIT_WEB_UNREDUCED: nominal slit {slit_w:.2f} mm would be "
                f"reduced to keep a 2 mm web at W = {W:g}")
    return None


def _contract(template_key: str, mirror: bool) -> ParameterContract:
    attach = (("top tuck FRONT / bottom tuck BACK (mirror)") if mirror
              else ("top tuck BACK / bottom tuck FRONT (straight)"))
    return ParameterContract(
        schema_version="dieline_parameter_contract/1.0",
        template_key=template_key,
        entries=(
            ParameterEntry("width_mm", KIND_USER, "mm",
                           "MANUFACTURE main-panel width", 12.0, 300.0),
            ParameterEntry("depth_mm", KIND_USER, "mm",
                           "MANUFACTURE side-panel width", 12.0, 300.0),
            ParameterEntry("height_mm", KIND_USER, "mm",
                           "MANUFACTURE body height", 60.0, 600.0),
            ParameterEntry("board_thickness_mm", KIND_USER, "mm",
                           "board caliper t", 0.3, 1.0, default=0.35),
            ParameterEntry("glue_tab_mm", KIND_USER, "mm", "glue-flap width",
                           6.0, 15.0, default=10.0),
            ParameterEntry("bleed_mm", KIND_USER, "mm", "bleed", 2.0, 5.0,
                           default=3.0),
            ParameterEntry("safe_margin_mm", KIND_USER, "mm", "safe inset",
                           3.0, 8.0, default=4.0),
            ParameterEntry("tuck_lip_mm", KIND_CONSTANT, "mm",
                           "explicit tuck lip (D-derived reach = D + lip)",
                           value=_LIP),
            ParameterEntry("shoulder_curve_ratio", KIND_CONSTANT, "ratio",
                           "shoulder span = lip x ratio (lip-derived; "
                           "always fits, no W-derived shoulder)",
                           value=_D_DERIVED_CURVE_RATIO),
            ParameterEntry("tuck_inset_factor", KIND_CONSTANT, "ratio",
                           "shoulder inset = W x factor (FLAP-WIDTH "
                           "geometry: the main-panel tuck is W wide; NOT a "
                           "closure-depth dependency)", value=0.227),
            ParameterEntry("dust_height_factor", KIND_CONSTANT, "ratio",
                           "dust height = D x factor (D-derived, unchanged)",
                           value=_DUST_F),
            ParameterEntry("slit_width_factor", KIND_CONSTANT, "ratio",
                           "friction slit = W x factor (flap-width)",
                           value=0.327),
            ParameterEntry("attachment", KIND_CONSTANT, "panels",
                           attach, value=None),
            ParameterEntry("tuck_total_mm", KIND_DERIVED, "mm",
                           "tuck reach", formula="D + 16 (D-derived)"),
            ParameterEntry("tuck_lip_derived_mm", KIND_DERIVED, "mm",
                           "lip past the depth fold-over", formula="16 (fixed)"),
            ParameterEntry("shoulder_curve_mm", KIND_DERIVED, "mm",
                           "shoulder span", formula="0.5 x lip = 8"),
            ParameterEntry("dust_height_mm", KIND_DERIVED, "mm",
                           "dust flap height", formula="D x 0.631"),
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


def _domain():
    return (
        _rng("board_thickness_mm", 0.3, 1.0, "BOARD_RANGE",
             "manufacturing caliper range"),
        _rng("width_mm", 12.0, 300.0, "WIDTH_RANGE", "print-shop budget"),
        _rng("depth_mm", 12.0, 300.0, "DEPTH_RANGE", "print-shop budget"),
        _rng("height_mm", 60.0, 600.0, "HEIGHT_RANGE", "print-shop budget"),
        _rng("glue_tab_mm", 6.0, 15.0, "GLUE_RANGE", "adhesive practice"),
        _rng("bleed_mm", 2.0, 5.0, "BLEED_RANGE", "prepress practice"),
        _rng("safe_margin_mm", 3.0, 8.0, "SAFE_RANGE", "prepress practice"),
        _Constraint(
            "HEIGHT_GT_WIDTH", "H > W", "schema tuck-carton proportion rule",
            lambda p: None if p["height_mm"] > p["width_mm"] else
            f"HEIGHT_GT_WIDTH: H = {p['height_mm']:g} must exceed "
            f"W = {p['width_mm']:g}"),
        _Constraint(
            "HEIGHT_GT_DEPTH", "H > D", "schema tuck-carton proportion rule",
            lambda p: None if p["height_mm"] > p["depth_mm"] else
            f"HEIGHT_GT_DEPTH: H = {p['height_mm']:g} must exceed "
            f"D = {p['depth_mm']:g}"),
        _Constraint(
            "DEPTH_VS_WIDTH_RATIO", "D <= 2.5 W", "schema Milestone 9.1 rule",
            lambda p: None if p["depth_mm"] <= 2.5 * p["width_mm"] else
            f"DEPTH_VS_WIDTH_RATIO: D = {p['depth_mm']:g} exceeds 2.5 x W"),
        _Constraint(
            "GLUE_VS_SIDE", "D + t >= G + 3",
            "the glue flap laps inside the side span",
            lambda p: None if p["depth_mm"] + p["board_thickness_mm"]
            >= p["glue_tab_mm"] + 3.0 else
            f"GLUE_VS_SIDE: side span "
            f"{p['depth_mm'] + p['board_thickness_mm']:g} mm must be >= "
            f"G + 3 = {p['glue_tab_mm'] + 3.0:g} mm"),
        _Constraint(
            "DUST_PAIR_CLEARANCE", "W - 2 x 0.631 D >= 0",
            "FOLDED: D-derived dust flaps collide across the W opening when "
            "W < 1.262 D. UNCHANGED from 1.1 — 1.2 widens only in the "
            "wide-short (lip) direction, not here.",
            lambda p: None
            if p["width_mm"] - 2 * _DUST_F * p["depth_mm"] >= 0.0 else
            f"DUST_PAIR_CLEARANCE: folded dust clearance = "
            f"{p['width_mm'] - 2 * _DUST_F * p['depth_mm']:.2f} mm < 0 "
            f"(needs W >= {2 * _DUST_F:g} x D)"),
        # NOTE: no TUCK_LIP_VS_HEIGHT constraint — the fixed 16 mm lip is
        # < H/2 for every H >= 60, so the 1.1 defect cannot occur.
        # NOTE: no DUST_CLAMP_BOUNDARY — the D+16 tuck zone always exceeds
        # the 0.631 D dust, so the clamp never engages.
        _Constraint(
            "SLIT_WEB_UNREDUCED",
            "web >= 2 mm at the nominal slit width (1.2 shoulder)",
            "friction slit must fit without the web-guard reduction "
            "(computed with the lip-derived shoulder span)",
            _dtuck_slit_web_unreduced),
    )


def _base_checks(coords, checks, add):
    d = coords.derived
    W, D, H = coords.dimensions.manufacture
    dust = float(d.get("dust_flap_height_mm", 0.0))
    tuck = float(d.get("tuck_flap_height_mm", 0.0))
    lip = max(tuck - D, 0.0)
    add("tuck_is_depth_derived", abs(tuck - (D + _LIP)) < 0.05,
        f"tuck {tuck:g} mm == D + {_LIP:g} = {D + _LIP:g} mm (D-derived)")
    add("lip_is_fixed_under_half_height", abs(lip - _LIP) < 0.05
        and lip < H / 2.0,
        f"fixed lip {lip:g} mm < H/2 = {H / 2.0:g} mm (no 1.1 lip defect)")
    add("shoulder_fits_lip",
        float(d.get("tuck_curve_h_mm", 0.0)) < lip,
        f"shoulder span {d.get('tuck_curve_h_mm')} mm < lip {lip:g} mm")
    add("folded_dust_flap_pair_clearance", W - 2 * dust >= 0.0,
        f"dust reach {dust:g} mm each across the {W:g} mm opening -> "
        f"{W - 2 * dust:.2f} mm gap")
    add("dust_below_tuck_zone", tuck - dust >= 2.0,
        f"tuck {tuck:g} mm vs dust {dust:g} mm")
    add("dust_unclamped", not d.get("dust_flap_clamped"),
        "dust flap at nominal height (D+16 zone never clamps)")
    add("friction_slits_present", len(coords.stadium_cutouts) == 2,
        f"{len(coords.stadium_cutouts)} stadium slits")
    add("slit_unreduced", not d.get("slit_reduced"),
        f"slit {d.get('slit_width_mm')} mm at nominal width")
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


def collision_report_ste(coords) -> dict:
    d = coords.derived
    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("straight_attachment_preserved",
        d.get("top_tuck_panel") == "back"
        and d.get("bottom_tuck_panel") == "front",
        f"top tuck on {d.get('top_tuck_panel')}, bottom on "
        f"{d.get('bottom_tuck_panel')}")
    _base_checks(coords, checks, add)
    return {"checks": checks, "all_ok": all(c["ok"] for c in checks)}


def collision_report_rte(coords) -> dict:
    """RTE 1.2 with an INDEPENDENT mirror audit (not inherited from STE)."""
    d = coords.derived
    panels = {p.name: p for p in coords.panels}
    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("reverse_attachment_preserved",
        d.get("top_tuck_panel") == "front"
        and d.get("bottom_tuck_panel") == "back",
        f"top tuck on {d.get('top_tuck_panel')}, bottom on "
        f"{d.get('bottom_tuck_panel')} (mirror: front/back)")
    top_tuck, bottom_tuck = coords.tuck_flap_polygons
    front, back = panels["front"], panels["back"]
    add("top_tuck_over_front_column",
        front.x - 0.5 <= top_tuck.centroid.x <= front.right + 0.5,
        f"top-tuck centroid x={top_tuck.centroid.x:.1f} within front")
    add("bottom_tuck_over_back_column",
        back.x - 0.5 <= bottom_tuck.centroid.x <= back.right + 0.5,
        f"bottom-tuck centroid x={bottom_tuck.centroid.x:.1f} within back")
    slit_ids = [s[0] for s in coords.stadium_cutouts]
    add("slits_on_mirrored_panels",
        any("front" in s for s in slit_ids)
        and any("back" in s for s in slit_ids),
        f"stadium slits {slit_ids}")
    _base_checks(coords, checks, add)
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


def sample_in_domain(rng) -> dict | None:
    """Deterministic in-domain sampler — the D-derived band (no lip cap;
    only the W >= 1.262 D dust edge and the schema rules)."""
    t = rng.choice([0.3, 0.4, 0.5, 0.7, 0.8, 1.0])
    glue = rng.choice([6.0, 10.0, 12.0, 15.0])
    d_min = max(12.0, glue + 3.0 - t)
    depth = round(rng.uniform(d_min, 200.0), 1)
    w_min = max(12.0, 2 * _DUST_F * depth + 0.2)
    w_max = min(300.0, 2.5 * 300.0)
    if w_min >= w_max - 0.5:
        return None
    width = round(rng.uniform(w_min, w_max), 1)
    if depth > 2.5 * width:
        return None
    user = {"width_mm": width, "depth_mm": depth,
            "board_thickness_mm": t, "glue_tab_mm": glue,
            "bleed_mm": rng.choice([2.0, 3.0, 5.0]),
            "safe_margin_mm": rng.choice([3.0, 4.0, 8.0])}
    user["height_mm"] = round(rng.uniform(max(width, depth) + 0.3, 600.0), 1)
    if user["height_mm"] <= 60.0:
        return None
    if _dtuck_slit_web_unreduced(user):
        return None
    return user


def ste_12_adapter():
    from apps.dielines.qualification.closure import STE_LEGACY_CLOSURE
    from apps.dielines.qualification.runner import ArchetypeAdapter
    return ArchetypeAdapter(
        template="straight_tuck_end_carton", version="1.2",
        panel_sequence=["glue_tab", "back", "side_left", "front",
                        "side_right"],
        closure=STE_LEGACY_CLOSURE,
        domain_constraints=_domain(),
        dims_semantics="manufacture",
        in_domain_sampler=sample_in_domain,
        _collision=collision_report_ste,
        _hashes=geometry_content_hashes,
    )


def rte_12_adapter():
    from apps.dielines.qualification.closure import RTE_LEGACY_CLOSURE
    from apps.dielines.qualification.runner import ArchetypeAdapter
    return ArchetypeAdapter(
        template="reverse_tuck_end_carton", version="1.2",
        panel_sequence=["glue_tab", "back", "side_left", "front",
                        "side_right"],
        closure=RTE_LEGACY_CLOSURE,
        domain_constraints=_domain(),
        dims_semantics="manufacture",
        in_domain_sampler=sample_in_domain,
        _collision=collision_report_rte,
        _hashes=geometry_content_hashes,
    )


STE_12_CONTRACT = _contract("straight_tuck_end_carton/1.2", mirror=False)
RTE_12_CONTRACT = _contract("reverse_tuck_end_carton/1.2", mirror=True)
register_contract(STE_12_CONTRACT)
register_contract(RTE_12_CONTRACT)


__all__ = ["ste_12_adapter", "rte_12_adapter", "collision_report_ste",
           "collision_report_rte", "geometry_content_hashes",
           "sample_in_domain", "STE_12_CONTRACT", "RTE_12_CONTRACT"]
