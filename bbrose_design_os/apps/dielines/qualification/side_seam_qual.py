"""Skynte side-seam 1.0 qualification (2A-9C slice 2).

``skynte_foundation_tuck_carton/1.0`` reconstructs the task-#47 Skynte
Foundation manufacturing reference (glue | side | main | side | main;
tuck on the two MAIN panels). Unlike STE 1.1 it uses the CORRECT D-derived
closure (tuck = D + fixed lip, DECISION-019), so it carries no
lip-vs-height defect.

Its domain is nonetheless BOUNDED by two real limits, derived from the
generator's own rules:

  * dust flaps are D-derived (0.631·D) and fold across the W opening —
    they collide when W < 1.262·D (same family as STE; the generator does
    NOT fail closed on this, so the qualification layer enforces it);
  * the shoulder curve is W-derived (0.218·W) but the tuck lip is a FIXED
    16 mm constant, so the curve stops fitting inside the lip at
    W ≥ 16/0.218 ≈ 73.4 mm — the GENERATOR already fails closed here
    (GeometryError), a hard LIMITATION, not silent distortion.

Task #47 is the golden regression fixture: the reference geometry
(42×32×140, t=0.30) and its hashes are pinned and must never move. This
module qualifies WITHOUT touching 1.0 — the generator, panel order, slit
positions and notch dimensions are unchanged.

No version bump is proposed: 1.0 is defect-free within its bounded domain.
A future 1.1 COULD widen the width cap (a parametric lip or a D-derived
shoulder curve) — recorded as a candidate improvement, not a required fix.
"""
from __future__ import annotations

from apps.dielines.geometry.ecma_ste import paths_content_hash
from apps.dielines.geometry.side_seam import (
    SKYNTE_FOUNDATION_TUCK_CARTON_V1 as _SPEC,
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

TEMPLATE_ID = "skynte_foundation_tuck_carton"
TEMPLATE_VERSION = "1.0"

_DUST_F = _SPEC.dust_height_factor          # 0.631
_CURVE_F = _SPEC.tuck_shoulder_curve_factor  # 0.218
_INSET_F = _SPEC.tuck_shoulder_inset_factor  # 0.227
_LIP = _SPEC.top_tuck_lip_mm                 # 16.0
_ENTRY = _SPEC.entry_slit_mm                 # 5.0
_WIDTH_CAP = _LIP / _CURVE_F                  # ≈ 73.39

SKYNTE_CONTRACT = ParameterContract(
    schema_version="dieline_parameter_contract/1.0",
    template_key="skynte_foundation_tuck_carton/1.0",
    entries=(
        ParameterEntry("width_mm", KIND_USER, "mm",
                       "MANUFACTURE MAIN-panel width (42 mm on the "
                       "reference)", 12.0, 300.0),
        ParameterEntry("depth_mm", KIND_USER, "mm",
                       "MANUFACTURE SIDE-panel width (32 mm)", 12.0, 300.0),
        ParameterEntry("height_mm", KIND_USER, "mm",
                       "MANUFACTURE body height (140 mm)", 60.0, 600.0),
        ParameterEntry("board_thickness_mm", KIND_USER, "mm",
                       "board caliper t", 0.3, 1.0, default=0.30),
        ParameterEntry("glue_tab_mm", KIND_USER, "mm", "glue-flap width",
                       6.0, 15.0, default=10.0),
        ParameterEntry("bleed_mm", KIND_USER, "mm", "bleed", 2.0, 5.0,
                       default=3.0),
        ParameterEntry("safe_margin_mm", KIND_USER, "mm", "safe inset",
                       3.0, 8.0, default=4.0),
        ParameterEntry("top_tuck_lip_mm", KIND_CONSTANT, "mm",
                       "tuck lip past the D fold-over (FIXED; caps width "
                       "via the shoulder-fit rule)", value=_LIP),
        ParameterEntry("bottom_tuck_lip_mm", KIND_CONSTANT, "mm",
                       "bottom tuck lip", value=_SPEC.bottom_tuck_lip_mm),
        ParameterEntry("tuck_shoulder_inset_factor", KIND_CONSTANT, "ratio",
                       "shoulder inset = W x factor", value=_INSET_F),
        ParameterEntry("tuck_shoulder_curve_factor", KIND_CONSTANT, "ratio",
                       "shoulder curve span = W x factor", value=_CURVE_F),
        ParameterEntry("dust_height_factor", KIND_CONSTANT, "ratio",
                       "dust height = D x factor", value=_DUST_F),
        ParameterEntry("slit_width_factor", KIND_CONSTANT, "ratio",
                       "friction slit = W x factor", value=_SPEC.slit_width_factor),
        ParameterEntry("entry_slit_mm", KIND_CONSTANT, "mm",
                       "DECISION-020 tuck-base entry slit per fold end",
                       value=_ENTRY),
        ParameterEntry("glue_corner_factor", KIND_CONSTANT, "ratio",
                       "glue-tab corner cut = G x factor",
                       value=_SPEC.glue_corner_factor),
        ParameterEntry("glue_corner_cap_mm", KIND_CONSTANT, "mm",
                       "glue-tab corner cut cap", value=_SPEC.glue_corner_cap_mm),
        ParameterEntry("tuck_total_mm", KIND_DERIVED, "mm",
                       "tuck flap height (D-derived, DECISION-019)",
                       formula="D + lip"),
        ParameterEntry("dust_height_mm", KIND_DERIVED, "mm",
                       "dust flap height", formula="D x 0.631"),
        ParameterEntry("shoulder_curve_mm", KIND_DERIVED, "mm",
                       "shoulder curve span", formula="W x 0.218"),
        ParameterEntry("lock_notch_mm", KIND_ALLOWANCE, "mm",
                       "DECISION-015 shoulder lock notch",
                       formula="2t (compensated mode)"),
        ParameterEntry("panel_allowances", KIND_ALLOWANCE, "mm",
                       "sides +t each, back +2t (glue joint), front "
                       "reference", formula="ECMA main-panel reference"),
        ParameterEntry("score_compression_mm", KIND_ALLOWANCE, "mm",
                       "not modelled", value=0.0),
    ),
)


SKYNTE_DOMAIN = (
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
        "SHOULDER_FITS_LIP", f"W x {_CURVE_F} < {_LIP:g}",
        "the W-derived shoulder curve must fit inside the FIXED tuck lip; "
        f"the generator fails closed at W >= {_WIDTH_CAP:.1f} mm (a hard "
        "width cap — a candidate 1.1 improvement, not a defect)",
        lambda p: None if _CURVE_F * p["width_mm"] < _LIP else
        f"SHOULDER_FITS_LIP: shoulder curve {_CURVE_F * p['width_mm']:.2f} "
        f"mm >= lip {_LIP:g} mm (W must be < {_WIDTH_CAP:.1f} mm)"),
    _Constraint(
        "DUST_PAIR_CLEARANCE", "W - 2 x 0.631 D >= 0",
        "FOLDED (engine reconciliation): D-derived dust flaps collide "
        "across the W opening when W < 1.262 D (generator does not fail "
        "closed on this — enforced here)",
        lambda p: None if p["width_mm"] - 2 * _DUST_F * p["depth_mm"] >= 0.0
        else
        f"DUST_PAIR_CLEARANCE: folded dust clearance = "
        f"{p['width_mm'] - 2 * _DUST_F * p['depth_mm']:.2f} mm < 0 "
        f"(needs W >= {2 * _DUST_F:g} x D)"),
    _Constraint(
        "ENTRY_SLIT_HINGE", "2(entry + 2t) <= 0.6(W + 2t)",
        "entry slits + lock notches must not consume >60% of the tuck "
        "base or the hinge tears (generator fails closed)",
        lambda p: None
        if 2.0 * (_ENTRY + 2 * p["board_thickness_mm"])
        <= 0.6 * (p["width_mm"] + 2 * p["board_thickness_mm"]) else
        f"ENTRY_SLIT_HINGE: slits+notches consume >60% of the "
        f"{p['width_mm'] + 2 * p['board_thickness_mm']:.1f} mm tuck base"),
)


def collision_report(coords) -> dict:
    """Folded + flat checks for the side-seam straight-tuck closure,
    measured from the emitted geometry (friction slits + 2t lock notches +
    DECISION-020 tuck-base entry slits)."""
    d = coords.derived
    W, D, H = coords.dimensions.manufacture
    dust = float(d.get("dust_flap_height_mm", 0.0))
    tuck = float(d.get("tuck_flap_height_mm", 0.0))
    lip = float(d.get("top_tuck_lip_mm", 0.0)) or max(tuck - D, 0.0)
    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("side_seam_attachment_preserved",
        d.get("top_tuck_panel") == "back"
        and d.get("bottom_tuck_panel") == "front",
        f"top tuck on {d.get('top_tuck_panel')}, bottom on "
        f"{d.get('bottom_tuck_panel')}")
    add("tuck_is_depth_derived", abs(tuck - (D + lip)) < 0.05,
        f"tuck {tuck:g} mm == D + lip = {D + lip:g} mm (DECISION-019)")
    add("folded_dust_flap_pair_clearance", W - 2 * dust >= 0.0,
        f"dust reach {dust:g} mm each across the {W:g} mm opening -> "
        f"{W - 2 * dust:.2f} mm gap")
    add("dust_below_tuck_zone", tuck - dust >= 2.0,
        f"tuck {tuck:g} mm vs dust {dust:g} mm")
    add("lip_vs_height", lip < H / 2.0,
        f"fixed lip {lip:g} mm vs H/2 = {H / 2.0:g} mm")
    add("shoulder_fits_lip",
        float(d.get("tuck_curve_h_mm", 0.0)) < lip,
        f"shoulder curve {d.get('tuck_curve_h_mm')} mm < lip {lip:g} mm")
    add("friction_slits_present", len(coords.stadium_cutouts) == 2,
        f"{len(coords.stadium_cutouts)} stadium friction slits")
    add("entry_slits_present", len(coords.slit_lines) > 0,
        f"{len(coords.slit_lines)} DECISION-020 entry-slit cut segments")
    add("slit_unreduced", not d.get("slit_reduced"),
        f"friction slit {d.get('slit_width_mm')} mm at nominal width")
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
    """Deterministic in-domain sampler (bounded W cap + dust clearance)."""
    t = rng.choice([0.3, 0.4, 0.5, 0.7, 0.8, 1.0])
    glue = rng.choice([6.0, 10.0, 12.0, 15.0])
    # W is capped by the shoulder-fits-lip rule and floored by the entry
    # hinge; D is bounded above by W / 1.262 (dust clearance)
    w_lo = max(12.0, (2 * (_ENTRY + 2 * t)) / 0.6 - 2 * t + 0.2)
    w_hi = _WIDTH_CAP - 0.1
    if w_lo >= w_hi:
        return None
    width = round(rng.uniform(w_lo, w_hi), 1)
    d_hi = min(300.0, width / (2 * _DUST_F), 2.5 * width)
    d_lo = max(12.0, width / 2.5)
    if d_lo >= d_hi:
        return None
    depth = round(rng.uniform(d_lo, d_hi), 1)
    height = round(rng.uniform(max(width, depth) + 0.3, 600.0), 1)
    if height <= 60.0:
        return None
    return {"width_mm": width, "depth_mm": depth, "height_mm": height,
            "board_thickness_mm": t, "glue_tab_mm": glue,
            "bleed_mm": rng.choice([2.0, 3.0, 5.0]),
            "safe_margin_mm": rng.choice([3.0, 4.0, 8.0])}


def skynte_adapter():
    from apps.dielines.qualification.closure import SKYNTE_CLOSURE
    from apps.dielines.qualification.runner import ArchetypeAdapter
    return ArchetypeAdapter(
        template=TEMPLATE_ID, version=TEMPLATE_VERSION,
        panel_sequence=["glue_tab", "side_left", "front", "side_right",
                        "back"],
        closure=SKYNTE_CLOSURE,
        domain_constraints=SKYNTE_DOMAIN,
        dims_semantics="manufacture",
        in_domain_sampler=sample_in_domain,
        _collision=collision_report,
        _hashes=geometry_content_hashes,
    )


register_contract(SKYNTE_CONTRACT)


__all__ = ["SKYNTE_CONTRACT", "SKYNTE_DOMAIN", "skynte_adapter",
           "collision_report", "geometry_content_hashes", "sample_in_domain",
           "TEMPLATE_ID", "TEMPLATE_VERSION", "_WIDTH_CAP"]
