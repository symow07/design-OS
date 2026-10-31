"""M6 — FLAKE_REFLECTION_RIG: SHIMMER vs POWDER_METALLIC.

Built on the repaired machinery from the start, and the sub-pixel
defect is handled AT DECLARATION, before any render:

FLAKE SCALE IN PIXELS, first-class: SHIMMER 0.055mm = 0.786px,
POWDER_METALLIC 0.040mm = 0.571px at the rig's 14.2857 px/mm —
both flake fields are SUB-PIXEL (glitter's 0.70mm = 10px for
comparison, and the sibling rig demands >= 3px of itself). Measured
corroboration: the confirmed glitter census reads SHIMMER at 0
discrete events. Any axis that works by resolving spatial flake
structure would therefore report the renderer's sampling and pixel
filter — SURFACE_AUTOCORRELATION_MM arriving in a new rig.

ROUTE DECISION (recorded, explicit): this rig takes ROUTE 1 — it does
NOT need to resolve flakes. The declared physical question is "what
does a flake field reflect of a structured environment, and how
coherently?", which is a property of the REFLECTED PANEL PATTERN, not
of individual flakes. metallic_response 0.45 vs 0.90 and roughness
0.55 vs 0.42 express themselves in exactly that quantity. REJECTION
RULE: any candidate axis whose sensitivity depends on resolving
individual flakes is rejected at declaration. No validity block of
the protocol is edited; identity 087c7f64317910fb is untouched.

The axes are the protocol's own REFLECTIVE_AXES (hashed at
declaration, measured from Blender-side scene-linear region grids —
no display frame anywhere in the path). Per the diffuse baseline's
recorded exposure, the verdict may not rest on one axis: the pass law
already requires two, and this record names which.

Unplumbed parameters (parameter_plumbing_audit.json): the rig may not
claim flake_orientation or sparkle_distribution sensitivity — both
render bit-identical frames and are DECLARED_NOT_REALIZED.
"""
from __future__ import annotations

import hashlib
import json
import os

from apps.pipeline.services import palette_characterization_protocol as PR
from apps.pipeline.services import palette_characterization_rig as DRIG
from apps.pipeline.services import palette_powder_engine as PE
from apps.pipeline.services import palette_powder_protocol as PP
from apps.pipeline.services import palette_powder_texture_axes as TX

SCHEMA = "flake_reflection_rig/1.0"

PX_PER_MM = 1200.0 / 84.0

FLAKE_SCALE_PX = {
    "SHIMMER": round(0.055 * PX_PER_MM, 3),
    "POWDER_METALLIC": round(0.040 * PX_PER_MM, 3),
    "GLITTER_reference": round(0.70 * PX_PER_MM, 1),
}

#: declared before measurement: the pair seeds, the floor ensemble and
#: the controls. Floors come from a SHIMMER seed-varied ensemble; the
#: pair members use the first seed of each family's declared range.
PAIR_SEEDS = {"SHIMMER": 130, "POWDER_METALLIC": 140}
FLOOR_SEEDS = (130, 131, 132, 133, 134, 135)
#: M6-ENSEMBLE-CONVENTION-DECLARATION (2026-08-15): POWDER_METALLIC's
#: 6-member ensemble, same declared derivation as the texture families
#: (member 0 = the pair seed; members 1-5 = the base*10 contiguous
#: block; no collision with 130-135 / 140 / the 991-992 replicates).
#: SHIMMER's set stays FLOOR_SEEDS — resolved from records at 93f0202,
#: not re-declared here.
METALLIC_ENSEMBLE_SEEDS = (140, 1400, 1401, 1402, 1403, 1404)
#: M6 attempt-4 (2026-08-15, glitter_flake_member_set_declaration.json):
#: GLITTER's flake member set. The records do NOT determine it — the
#: historical committed member's seed is unrecorded ('committed member',
#: phase3_measurements.json) and its identity is non-recomputable (A143
#: class) — so member 0 is a NEW declared seed continuing the rig's
#: decade geography (130 SHIMMER, 140 METALLIC, 150 GLITTER); members
#: 1-5 the base*10 block. The MvG legs therefore re-base on member 0
#: (new terms, inheriting nothing) per the declaration record.
GLITTER_FLAKE_ENSEMBLE_SEEDS = (150, 1500, 1501, 1502, 1503, 1504)
SEPARATION_MARGIN = 2.0   # same declared margin as R4
PASS_BAR = 0.25           # the unmoved law bar


class FlakeRigError(RuntimeError):
    pass


def declaration() -> dict:
    return {
        "record_type": SCHEMA,
        "flake_scale_px": FLAKE_SCALE_PX,
        "route": "ROUTE_1_REFLECTED_ENVIRONMENT_STRUCTURE",
        "rejection_rule": "axes that depend on resolving individual "
                          "flakes are rejected at declaration",
        "axes": PR.REFLECTIVE_AXES,
        "pass_law": {"required_independent_axes":
                     PR.REFLECTIVE_REQUIRED_AXES, "bar": PASS_BAR},
        "pair_seeds": PAIR_SEEDS,
        "floor_seeds": list(FLOOR_SEEDS),
        "separation_margin": SEPARATION_MARGIN,
        "unplumbed_parameters_not_claimed": ["flake_orientation",
                                            "sparkle_distribution"],
        "protocol_identity_untouched": PP.protocol_identity(),
    }


#: A173/2x — the composite below is SPLIT. Its payload embedded
#: PP.protocol_identity(), so it moved on every protocol amendment
#: (twenty-nine so far) whether or not this declaration's own content
#: moved: one bit where a citing path needs two. Two identities now,
#: named so the difference is in the name, each recipe co-located per
#: 2w in the docstring beside it.

_LAW_ERA_KEY = "protocol_identity_untouched"


def declaration_content_identity() -> str:
    """Identity of THIS declaration's content alone.

    RECIPE: sha256(json.dumps(declaration() minus the
    'protocol_identity_untouched' key, sort_keys=True, default=str))
    .hexdigest()[:16]. Moves iff the flake declaration's own content
    moves — axes, seeds, bars, route, rejection rule. A protocol
    amendment cannot move it.
    """
    payload = {k: v for k, v in declaration().items()
               if k != _LAW_ERA_KEY}
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, default=str
    ).encode()).hexdigest()[:16]


def declaration_law_era_identity() -> str:
    """Identity of the LAW ERA this declaration was read under.

    RECIPE: sha256(json.dumps({'protocol_identity_untouched':
    declaration()['protocol_identity_untouched']}, sort_keys=True))
    .hexdigest()[:16]. Moves iff the protocol identity moves. Cite it
    beside the content identity, never instead of it: content
    unchanged with era moved is AGREEMENT_ACROSS_LAW_CHANGE, a named
    state, not freshness and not staleness.
    """
    return hashlib.sha256(json.dumps(
        {_LAW_ERA_KEY: declaration()[_LAW_ERA_KEY]}, sort_keys=True
    ).encode()).hexdigest()[:16]


def declaration_identity() -> str:
    """SUPERSEDED IN PLACE per 2k/2x (A173, 2026-08-11) — retained
    because committed records carry values it produced.

    RECIPE (unchanged): sha256(json.dumps(declaration(),
    sort_keys=True, default=str)).hexdigest()[:16] — a COMPOSITE over
    content AND law era. It answers only 'did anything move'. Use
    declaration_content_identity() and declaration_law_era_identity();
    this one is not a staleness instrument.

    NOTE: the frozen record identity 31b04a6c1eff8de2 in
    flake_independence_readjudication_declaration.json was NEVER
    produced by this function — it is that record's self-hash (a
    different identity system sharing the name), established
    era-correctly at a163_flake_classification.json.
    """
    return hashlib.sha256(json.dumps(
        declaration(), sort_keys=True, default=str
    ).encode()).hexdigest()[:16]


def _shade():
    return PE.PowderShade("prov_flake_neutral", (0.62, 0.55, 0.48),
                          PE.PROVISIONAL_VISUALIZATION_SHADE)


def _measure(family, seed, out_dir, label, *, samples, overrides=None):
    spec = PE.PowderMaterialSpec(family, _shade(), seed=seed)
    d = PR.measure_under(PR.REFLECTIVE_MATERIAL_RIG, spec.realize(),
                         out_dir, label, overrides=overrides,
                         samples=samples)
    return d


def _axis_effect(spec_row, a, b):
    if spec_row["kind"] == "absolute":
        return abs(a - b)
    mean = (abs(a) + abs(b)) / 2.0
    return abs(a - b) / mean if mean > 1e-9 else 0.0


def run_flake_rig(out_dir, *, samples=48) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    idx = DRIG.region_indices(out_dir)

    # -- commissioning: mirror reference + subject windows -------------
    mirror = PR.measure_under(PR.REFLECTIVE_MATERIAL_RIG,
                              PR.MIRROR_REFERENCE_SPEC, out_dir,
                              "flake_mirror_reference", samples=samples)
    v = PR.REFLECTIVE_MATERIAL_RIG["validity"]
    mirror_contrast = PR.grid_pattern_contrast(
        PR._region_grid(mirror, "PLANAR"))
    commissioning = {
        "mirror_pattern_contrast": round(mirror_contrast, 6),
        "gate": v["mirror_reference_min_pattern_contrast"],
        "mirror_frames": ["flake_mirror_reference.png",
                          "flake_mirror_reference.exr"],
        "clipped": PR._clipped_subject(mirror),
    }
    if mirror_contrast < v["mirror_reference_min_pattern_contrast"] or \
            commissioning["clipped"] > 0:
        raise FlakeRigError(f"mirror commissioning failed: "
                            f"{commissioning}")

    members = {}
    for family, seed in PAIR_SEEDS.items():
        d = _measure(family, seed, out_dir, f"flake_{family}",
                     samples=samples)
        peak = max(r.get("scene_linear_peak", 0.0)
                   for r in d["regions"].values())
        if peak < v["min_subject_peak_scene_linear"]:
            raise FlakeRigError(
                f"{family} peak {peak:.4f} below the declared window")
        if PR._clipped_subject(d) > 0:
            raise FlakeRigError(f"{family} clipped — refused")
        members[family] = d
        commissioning[f"{family}_subject_peak"] = round(peak, 6)

    # -- R2: the pair must have realized differently -------------------
    frame_a = TX.load_scene_linear(members["SHIMMER"]["exr"])
    frame_b = TX.load_scene_linear(members["POWDER_METALLIC"]["exr"])
    TX.region_alignment_assertion(frame_a, idx, members["SHIMMER"])
    realization = TX.stimulus_realization(frame_a, frame_b, idx)
    if not realization["realized"]:
        return {"record_type": SCHEMA,
                "verdict": "REFUSED_STIMULUS_NOT_REALIZED",
                "stimulus": realization}

    # -- R4: per-axis seed-only floors from the SHIMMER ensemble -------
    ensemble = []
    for seed in FLOOR_SEEDS:
        if seed == PAIR_SEEDS["SHIMMER"]:
            d = members["SHIMMER"]
        else:
            d = _measure("SHIMMER", seed, out_dir,
                         f"flake_floor_{seed}", samples=samples)
        ensemble.append(PR.reflective_axes(d, mirror))
    floors = {}
    for axis, spec_row in PR.REFLECTIVE_AXES.items():
        effs = [_axis_effect(spec_row, float(ensemble[i][axis]),
                             float(ensemble[j][axis]))
                for i in range(len(ensemble))
                for j in range(i + 1, len(ensemble))]
        floor = max(effs)
        floors[axis] = {"floor": round(floor, 5),
                        "pairings": len(effs),
                        "eligible": bool(floor < PASS_BAR),
                        "required": round(max(PASS_BAR,
                                              floor * SEPARATION_MARGIN),
                                          5)}

    # -- the pair, adjudicated with floors + declared independence -----
    axes_a = PR.reflective_axes(members["SHIMMER"], mirror)
    axes_b = PR.reflective_axes(members["POWDER_METALLIC"], mirror)
    rows = {}
    counted = []
    for axis, spec_row in PR.REFLECTIVE_AXES.items():
        eff = _axis_effect(spec_row, float(axes_a[axis]),
                           float(axes_b[axis]))
        fl = floors[axis]
        reasons = []
        if not fl["eligible"]:
            reasons.append(f"INELIGIBLE_FLOOR_{fl['floor']}")
        if eff < fl["required"]:
            reasons.append("BELOW_REQUIRED")
        if not spec_row.get("independent", False):
            reasons.append("SUPPORTING_NEVER_COUNTS")
        if not reasons:
            counted.append(axis)
        rows[axis] = {"shimmer": round(float(axes_a[axis]), 5),
                      "metallic": round(float(axes_b[axis]), 5),
                      "effect": round(eff, 5),
                      "floor": fl["floor"], "counts": not reasons,
                      "reasons": reasons}

    # -- negative controls ---------------------------------------------
    controls = {}
    ident_axes = PR.reflective_axes(members["SHIMMER"], mirror)
    controls["identical_measurement"] = {
        "effects_all_zero": all(
            _axis_effect(PR.REFLECTIVE_AXES[a], float(ident_axes[a]),
                         float(axes_a[a])) == 0.0
            for a in PR.REFLECTIVE_AXES),
        "behaved": True}
    seed_axes = ensemble[1]
    seed_clearing = [a for a, s in PR.REFLECTIVE_AXES.items()
                     if s.get("independent")
                     and _axis_effect(s, float(axes_a[a]),
                                      float(seed_axes[a]))
                     >= floors[a]["required"]]
    controls["seed_only_pair_law"] = {
        "clearing_axes": seed_clearing,
        "behaved": len(seed_clearing) < PR.REFLECTIVE_REQUIRED_AXES}
    expo = _measure("SHIMMER", PAIR_SEEDS["SHIMMER"], out_dir,
                    "flake_ctl_exposure", samples=samples,
                    overrides=PR._exposure_override(1.5))
    expo_axes = PR.reflective_axes(expo, mirror)
    expo_clearing = [a for a, s in PR.REFLECTIVE_AXES.items()
                     if s.get("independent")
                     and _axis_effect(s, float(axes_a[a]),
                                      float(expo_axes[a]))
                     >= floors[a]["required"]]
    controls["exposure_only_pair_law"] = {
        "clearing_axes": expo_clearing,
        "behaved": len(expo_clearing) < PR.REFLECTIVE_REQUIRED_AXES}

    misbehaved = [k for k, c in controls.items() if not c["behaved"]]
    verdict = ("PASS" if len(counted) >= PR.REFLECTIVE_REQUIRED_AXES
               and not misbehaved else "FAIL")
    return {
        "record_type": SCHEMA,
        "declaration_identity": declaration_identity(),
        "declaration_content_identity": declaration_content_identity(),
        "declaration_law_era_identity": declaration_law_era_identity(),
        "declaration": declaration(),
        "commissioning": commissioning,
        "stimulus": realization,
        "noise_floors": floors,
        "pair": rows,
        "counted_axes": counted,
        "not_one_axis_concentration": len(counted) >= 2,
        "negative_controls": controls,
        "controls_misbehaved": misbehaved,
        "SHIMMER_VS_POWDER_METALLIC": verdict,
        "independence_note": (
            "within-rig mutual independence rests on the protocol's "
            "hashed per-axis declarations (different formulas on "
            "different normalisations, supporting axes never counted); "
            "cross-rig Spearman needs a reflective census of N>=4 and "
            "is a recorded obligation, not claimable at N=2"),
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
    }
