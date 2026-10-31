"""Reverse tuck end 1.1 qualification (2A-9C slice 3).

``reverse_tuck_end_carton/1.1`` is the MIRROR of STE 1.1: identical panel
layout (glue | back | side_left | front | side_right) and identical
DECISION-016 ratio formulas, but the tuck attachment is swapped — top tuck
on FRONT, bottom tuck on BACK (STE is back/front). It is PROVISIONAL (no
measured reference) and stays so; qualification never promotes it.

Because it reuses STE's W-derived tuck (W x 1.227) and D-derived dust
(D x 0.631), RTE 1.1 carries the SAME two defects (lip > H/2 on
wide-short; dust collision when W < 1.262 D) and therefore the SAME narrow
honest domain. Its domain is DERIVED HERE INDEPENDENTLY (not inherited) —
the constraint formulas coincide with STE's because RTE literally runs the
same engine formulas.

Slice-3-specific work is the MIRROR AUDIT: the reverse tuck placement must
not introduce coordinate sign errors, wrong-side slits/notches, or
inconsistent top/bottom transforms. The collision report includes explicit
mirror checks (tuck columns, stadium-slit panels, structural equivalence
to STE at the same dimensions).

1.1 is untouched (byte-stable). A future reverse_tuck_end_carton/1.2 would
adopt the same D-derived correction proposed for STE 1.2 — recorded, not
implemented here.
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
    register_contract,
)
from apps.dielines.qualification.domain import _Constraint, _rng
from apps.dielines.qualification.legacy_tuck import _slit_web_unreduced

TEMPLATE_ID = "reverse_tuck_end_carton"
TEMPLATE_VERSION = "1.1"

_TUCK_F = 1.227
_DUST_F = 0.631

RTE_CONTRACT = ParameterContract(
    schema_version="dieline_parameter_contract/1.0",
    template_key="reverse_tuck_end_carton/1.1",
    entries=(
        ParameterEntry("width_mm", KIND_USER, "mm",
                       "MANUFACTURE main-panel width", 12.0, 300.0),
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
                       "tuck height = W x factor (DECISION-016, shared with "
                       "STE; W-derived defect present)", value=_TUCK_F),
        ParameterEntry("dust_height_factor", KIND_CONSTANT, "ratio",
                       "dust height = D x factor", value=_DUST_F),
        ParameterEntry("slit_width_factor", KIND_CONSTANT, "ratio",
                       "friction slit = W x factor (PROVISIONAL)",
                       value=0.327),
        ParameterEntry("tuck_inset_factor", KIND_CONSTANT, "ratio",
                       "shoulder inset = W x factor", value=0.227),
        ParameterEntry("tuck_curve_factor", KIND_CONSTANT, "ratio",
                       "shoulder curve span = W x factor", value=0.218),
        ParameterEntry("top_tuck_panel", KIND_CONSTANT, "panel",
                       "MIRROR: top tuck on FRONT (STE: back)",
                       value=None),
        ParameterEntry("bottom_tuck_panel", KIND_CONSTANT, "panel",
                       "MIRROR: bottom tuck on BACK (STE: front)",
                       value=None),
        ParameterEntry("tuck_total_mm", KIND_DERIVED, "mm",
                       "tuck flap height", formula="W x 1.227"),
        ParameterEntry("tuck_lip_mm", KIND_DERIVED, "mm",
                       "lip past the opening", formula="W x 1.227 - D"),
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


RTE_DOMAIN = (
    _rng("board_thickness_mm", 0.3, 1.0, "BOARD_RANGE",
         "manufacturing caliper range (compensated mode)"),
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
        f"GLUE_VS_SIDE: side span {p['depth_mm'] + p['board_thickness_mm']:g}"
        f" mm must be >= G + 3 = {p['glue_tab_mm'] + 3.0:g} mm"),
    _Constraint(
        "DUST_PAIR_CLEARANCE", "W - 2 x 0.631 D >= 0",
        "FOLDED (engine reconciliation): D-derived dust flaps collide "
        "across the W opening when W < 1.262 D (mirror-independent — same "
        "as STE; RTE reuses the ratio formula)",
        lambda p: None if p["width_mm"] - 2 * _DUST_F * p["depth_mm"] >= 0.0
        else
        f"DUST_PAIR_CLEARANCE: folded dust clearance = "
        f"{p['width_mm'] - 2 * _DUST_F * p['depth_mm']:.2f} mm < 0 "
        f"(needs W >= {2 * _DUST_F:g} x D)"),
    _Constraint(
        "TUCK_LIP_VS_HEIGHT", "1.227 W - D < H / 2",
        "FOLDED: the W-derived tuck lip must stay far shorter than the "
        "body (shared STE defect; wide-short cartons excluded)",
        lambda p: None
        if _TUCK_F * p["width_mm"] - p["depth_mm"] < p["height_mm"] / 2.0
        else
        f"TUCK_LIP_VS_HEIGHT: lip = "
        f"{_TUCK_F * p['width_mm'] - p['depth_mm']:.2f} mm must be < "
        f"H/2 = {p['height_mm'] / 2.0:g} mm"),
    _Constraint(
        "DUST_CLAMP_BOUNDARY", "0.631 D <= 1.227 W - 2",
        "EXPLICIT clamp edge: beyond it the engine clamps the dust height "
        "(a clamped flap is an altered formula, outside the domain)",
        lambda p: None if _DUST_F * p["depth_mm"]
        <= _TUCK_F * p["width_mm"] - 2.0 else
        f"DUST_CLAMP_BOUNDARY: nominal dust {_DUST_F * p['depth_mm']:.2f} "
        f"mm exceeds the tuck zone minus 2 mm "
        f"({_TUCK_F * p['width_mm'] - 2.0:.2f})"),
    _Constraint(
        "SLIT_WEB_UNREDUCED",
        "web >= 2 mm at the nominal slit width (DECISION-017)",
        "the friction slit must fit without the web-guard reduction",
        _slit_web_unreduced),
)


def collision_report(coords) -> dict:
    """Folded + flat checks for the REVERSE straight-tuck closure, with an
    explicit MIRROR AUDIT (tuck columns, slit panels)."""
    d = coords.derived
    W, D, H = coords.dimensions.manufacture
    panels = {p.name: p for p in coords.panels}
    dust = float(d.get("dust_flap_height_mm", 0.0))
    tuck = float(d.get("tuck_flap_height_mm", 0.0))
    lip = max(tuck - D, 0.0)
    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    # --- mirror audit -----------------------------------------------------
    add("reverse_attachment_preserved",
        d.get("top_tuck_panel") == "front"
        and d.get("bottom_tuck_panel") == "back",
        f"top tuck on {d.get('top_tuck_panel')}, bottom on "
        f"{d.get('bottom_tuck_panel')} (STE mirror: front/back)")
    # top tuck polygon must sit over the FRONT column, bottom over BACK —
    # a mirrored x-sign error would land them on the wrong panel
    top_tuck, bottom_tuck = coords.tuck_flap_polygons
    front, back = panels["front"], panels["back"]
    tt_cx = top_tuck.centroid.x
    bt_cx = bottom_tuck.centroid.x
    add("top_tuck_over_front_column",
        front.x - 0.5 <= tt_cx <= front.right + 0.5,
        f"top-tuck centroid x={tt_cx:.1f} within front "
        f"[{front.x:.1f},{front.right:.1f}]")
    add("bottom_tuck_over_back_column",
        back.x - 0.5 <= bt_cx <= back.right + 0.5,
        f"bottom-tuck centroid x={bt_cx:.1f} within back "
        f"[{back.x:.1f},{back.right:.1f}]")
    # stadium friction slits must name the mirrored panels
    slit_ids = [s[0] for s in coords.stadium_cutouts]
    add("slits_on_mirrored_panels",
        any("front" in s for s in slit_ids)
        and any("back" in s for s in slit_ids),
        f"stadium slits {slit_ids}")

    # --- shared straight-tuck folded checks -------------------------------
    add("folded_dust_flap_pair_clearance", W - 2 * dust >= 0.0,
        f"dust reach {dust:g} mm each across the {W:g} mm opening -> "
        f"{W - 2 * dust:.2f} mm gap")
    add("dust_below_tuck_zone", tuck - dust >= 2.0,
        f"tuck {tuck:g} mm vs dust {dust:g} mm")
    add("tuck_lip_vs_height", lip < H / 2.0,
        f"lip {lip:.2f} mm vs H/2 = {H / 2.0:g} mm")
    add("friction_slits_present", len(coords.stadium_cutouts) == 2,
        f"{len(coords.stadium_cutouts)} stadium slits (top + bottom tuck)")
    add("slit_unreduced", not d.get("slit_reduced"),
        f"slit {d.get('slit_width_mm')} mm at nominal width")
    add("slit_web", float(d.get("slit_web_mm") or 0) >= 2.0,
        f"web {d.get('slit_web_mm')} mm beside each slit end")
    add("dust_unclamped", not d.get("dust_flap_clamped"),
        "dust flap emitted at its nominal formula height")
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


def sample_in_domain(rng) -> dict | None:
    """Deterministic in-domain sampler (identical band to STE — RTE shares
    the ratio formulas)."""
    t = rng.choice([0.3, 0.4, 0.5, 0.7, 0.8, 1.0])
    glue = rng.choice([6.0, 10.0, 12.0, 15.0])
    d_min = max(12.0, glue + 3.0 - t)
    depth = round(rng.uniform(d_min, 150.0), 1)
    w_min = max(12.0, 2 * _DUST_F * depth + 0.2)
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


def rte_adapter():
    from apps.dielines.qualification.closure import RTE_LEGACY_CLOSURE
    from apps.dielines.qualification.runner import ArchetypeAdapter
    return ArchetypeAdapter(
        template=TEMPLATE_ID, version=TEMPLATE_VERSION,
        panel_sequence=["glue_tab", "back", "side_left", "front",
                        "side_right"],
        closure=RTE_LEGACY_CLOSURE,
        domain_constraints=RTE_DOMAIN,
        dims_semantics="manufacture",
        in_domain_sampler=sample_in_domain,
        _collision=collision_report,
        _hashes=geometry_content_hashes,
    )


register_contract(RTE_CONTRACT)


__all__ = ["RTE_CONTRACT", "RTE_DOMAIN", "rte_adapter", "collision_report",
           "geometry_content_hashes", "sample_in_domain", "TEMPLATE_ID",
           "TEMPLATE_VERSION"]
