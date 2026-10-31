"""M6 Phase 2 — R4 per-axis noise floors and R5 measured independence.

R4: every axis acquires a MEASURED seed-only noise floor from a
same-family, same-parameter, seed-varied ensemble. An axis whose floor
sits at or above the 25% pass bar is INELIGIBLE to carry a pair, and a
clearing result must exceed its own floor by the declared margin of
2.0. The bar does not move — this is an eligibility precondition on
the INSTRUMENT, in the same spirit as enlarging the light source
rather than lowering a threshold.

R5: independence stops being a docstring word. Absolute Spearman rank
correlation is computed between every axis pair across the family
census; two axes above the declared 0.80 ceiling may not BOTH count
toward the same pair's two-axis requirement.

Both thresholds (margin 2.0, ceiling 0.80) were declared in the repair
protocol 1e198aed8d86ed9c BEFORE any ensemble or correlation was
computed, and are frozen inputs here.
"""
from __future__ import annotations

import json
import os

import numpy as np

from apps.pipeline.services import palette_characterization_rig as CR
from apps.pipeline.services import palette_powder_engine as PE
from apps.pipeline.services import palette_powder_protocol as PP
from apps.pipeline.services import palette_statistics as ST
from apps.pipeline.services import palette_powder_texture_axes as TX

SCHEMA = "axis_eligibility/1.0"

PASS_BAR = 0.25           # frozen — the law's bar, not this module's
SEPARATION_MARGIN = 2.0   # declared in R4 before measurement
INDEPENDENCE_CEILING = 0.80  # declared in R5 before measurement

LOBE_AXES = ("HIGHLIGHT_FWHM", "HIGHLIGHT_PEAK",
             "SPECULAR_TO_DIFFUSE_RATIO", "GRAZING_RESPONSE",
             "SHEEN_REGION_RESPONSE", "EDGE_HIGHLIGHT_RESPONSE")

#: the seed-varied ensemble: same family, same parameters, seeds only.
#: Six members give fifteen seed-only pairings per axis. Seed 99 is
#: REQUIRED membership: the F4 finding's recorded excursion (EDGE
#: 0.27991, seeds 40 vs 99) is data, and a floor computed on an
#: ensemble that omits a known recorded excursion would be selected by
#: seed choice — the rule is that every seed with a seed-only
#: measurement on record belongs to the ensemble.
ENSEMBLE_SEEDS = (40, 81, 82, 83, 84, 99)


class EligibilityError(RuntimeError):
    pass


def _effect(a, b):
    mean = (abs(a) + abs(b)) / 2.0
    return abs(a - b) / mean if mean > 1e-9 else 0.0


def _lobe_axes_of(measurement):
    axes = CR.normalized(CR.axes_from(measurement))
    return {k: float(axes[k]) for k in LOBE_AXES}


def measure_noise_floors(out_dir, *, samples=64) -> dict:
    """R4 — seed-only ensemble on POWDER_MATTE, both instruments.

    The floor per axis is the MAXIMUM seed-only relative effect across
    all ensemble pairings: a clearing result must beat the worst noise
    excursion by the margin, not the average one.
    """
    os.makedirs(out_dir, exist_ok=True)
    shade = PE.PowderShade("prov_char_neutral", (0.62, 0.55, 0.48),
                           PE.PROVISIONAL_VISUALIZATION_SHADE)

    lobe_members = []
    for seed in ENSEMBLE_SEEDS:
        spec = PE.PowderMaterialSpec(PP.POWDER_MATTE, shade, seed=seed)
        d = CR.characterize_powder(spec, out_dir,
                                   label=f"ens_lobe_{seed}",
                                   samples=samples)
        lobe_members.append(_lobe_axes_of(d))

    # texture ensemble at one calibrated energy: calibrate once on the
    # first member, reuse for all (identical family and parameters)
    tex_members = []
    first = PE.PowderMaterialSpec(PP.POWDER_MATTE, shade,
                                  seed=ENSEMBLE_SEEDS[0])
    cal = TX.characterize_texture_pair(
        first, PE.PowderMaterialSpec(PP.POWDER_MATTE, shade,
                                     seed=ENSEMBLE_SEEDS[1]),
        out_dir, label_a=f"ens_tex_{ENSEMBLE_SEEDS[0]}",
        label_b=f"ens_tex_{ENSEMBLE_SEEDS[1]}", samples=samples)
    energy = cal["_calibration"]["per_member"][
        f"ens_tex_{ENSEMBLE_SEEDS[0]}"]["energy"]
    tex_members.append(cal[f"ens_tex_{ENSEMBLE_SEEDS[0]}"])
    tex_members.append(cal[f"ens_tex_{ENSEMBLE_SEEDS[1]}"])
    for seed in ENSEMBLE_SEEDS[2:]:
        pair = TX.measured_pair_at(
            first, PE.PowderMaterialSpec(PP.POWDER_MATTE, shade,
                                         seed=seed),
            out_dir, label_a=f"ens_tex_a_{seed}",
            label_b=f"ens_tex_{seed}", energy=energy, samples=samples)
        tex_members.append(pair[f"ens_tex_{seed}"])

    floors = {}
    for axis in LOBE_AXES:
        effs = [_effect(lobe_members[i][axis], lobe_members[j][axis])
                for i in range(len(lobe_members))
                for j in range(i + 1, len(lobe_members))]
        floors[axis] = {"instrument": "DIFFUSE_LOBE_RIG",
                        "pairings": len(effs),
                        "max_seed_only_effect": round(max(effs), 5),
                        "mean_seed_only_effect": round(
                            float(np.mean(effs)), 5)}
    for axis in TX.TEXTURE_AXES:
        effs = [_effect(float(tex_members[i][axis]),
                        float(tex_members[j][axis]))
                for i in range(len(tex_members))
                for j in range(i + 1, len(tex_members))]
        floors[axis] = {"instrument": "MIRROR_SOURCE_TEXTURE_RIG",
                        "pairings": len(effs),
                        "max_seed_only_effect": round(max(effs), 5),
                        "mean_seed_only_effect": round(
                            float(np.mean(effs)), 5)}

    for axis, row in floors.items():
        floor = row["max_seed_only_effect"]
        row["floor"] = floor
        row["eligible"] = bool(floor < PASS_BAR)
        row["required_clearing_effect"] = round(
            max(PASS_BAR, floor * SEPARATION_MARGIN), 5)
    return {
        "record_type": SCHEMA + ":noise_floors",
        "ensemble": {"family": "POWDER_MATTE",
                     "seeds": list(ENSEMBLE_SEEDS)},
        "separation_margin": SEPARATION_MARGIN,
        "pass_bar_unmoved": PASS_BAR,
        "floors": floors,
        "ineligible_axes": [a for a, r in floors.items()
                            if not r["eligible"]],
    }


def measure_independence(swatch_dir, tex_census) -> dict:
    """R5 — Spearman correlation across the family census.

    The census rows are the measured families; each axis is a rank
    vector across them. |rho| above the ceiling groups two axes so
    only one of the group may count toward a pair.
    """
    families = sorted(tex_census)
    lobe_rows = {}
    for fam in families:
        meas = json.load(open(os.path.join(
            swatch_dir, f"swatch_powder_{fam}.json")))
        lobe_rows[fam] = _lobe_axes_of(meas)
    tex_axes = sorted({k for row in tex_census.values() for k in row})
    all_axes = list(LOBE_AXES) + tex_axes
    matrix = {}
    for fam in families:
        row = dict(lobe_rows[fam])
        row.update({a: float(tex_census[fam][a]) for a in tex_axes})
        matrix[fam] = row

    def spearman(xs, ys):
        # 1g — delegates to the guarded implementation; identical on
        # non-degenerate input, and the refusal semantics this module
        # already had are preserved for its callers
        try:
            return ST.guarded_spearman(xs, ys)
        except ST.DegenerateStatisticError as exc:
            raise EligibilityError(
                f"degenerate rank vector — refusing to call two axes "
                f"independent on it ({exc})")

    correlations = {}
    over = []
    for i, a in enumerate(all_axes):
        for b in all_axes[i + 1:]:
            xs = np.array([matrix[f][a] for f in families])
            ys = np.array([matrix[f][b] for f in families])
            rho = abs(spearman(xs, ys))
            correlations[f"{a}|{b}"] = round(rho, 4)
            if rho > INDEPENDENCE_CEILING:
                over.append((a, b, round(rho, 4)))
    return {
        "record_type": SCHEMA + ":independence",
        "census_families": families,
        "ceiling": INDEPENDENCE_CEILING,
        "abs_spearman": correlations,
        "over_ceiling_pairs": over,
        "note": "two axes above the ceiling may not both count toward "
                "one pair's two-axis requirement",
    }


def adjudicate(rulings, floors, independence) -> dict:
    """Re-adjudicate every pair with eligibility + independence applied.

    The pass law is unchanged: 2 axes at >= 25%. An axis counts only
    when it is ELIGIBLE (floor < bar), its effect exceeds its own
    floor by the margin, and it is not grouped with an already-counted
    axis above the independence ceiling.
    """
    grouped = {}
    for a, b, _rho in independence["over_ceiling_pairs"]:
        grouped.setdefault(a, set()).add(b)
        grouped.setdefault(b, set()).add(a)
    fl = floors["floors"]
    out = {}
    for label, ruling in rulings.items():
        axes_effects = {}
        for axis, row in ruling.get("lobe_axes", {}).items():
            axes_effects[axis] = float(row["relative_effect"])
        for axis, row in ruling.get("texture_axes", {}).items():
            axes_effects[axis] = float(row["relative_effect"])
        counted = []
        detail = {}
        for axis, eff in sorted(axes_effects.items(),
                                key=lambda kv: -kv[1]):
            row = fl.get(axis)
            if row is None:
                raise EligibilityError(
                    f"{label}: axis {axis} has no recorded noise floor "
                    f"— a ruling may not use it (R4 assertion)")
            reasons = []
            if not row["eligible"]:
                reasons.append(f"INELIGIBLE_FLOOR_{row['floor']}")
            if eff < PASS_BAR:
                reasons.append("BELOW_BAR")
            elif eff < row["floor"] * SEPARATION_MARGIN:
                reasons.append(
                    f"WITHIN_NOISE_MARGIN_{row['floor']}x{SEPARATION_MARGIN}")
            if any(c in grouped.get(axis, set()) for c in counted):
                reasons.append("CORRELATED_WITH_COUNTED_AXIS")
            if not reasons:
                counted.append(axis)
            detail[axis] = {"effect": round(eff, 4),
                            "floor": row["floor"],
                            "counts": not reasons,
                            "reasons": reasons}
        out[label] = {
            "counted_axes": counted,
            "axes": detail,
            "verdict": "PASS" if len(counted) >= 2 else "FAIL",
        }
    return {
        "record_type": SCHEMA + ":adjudication",
        "pass_law_unmoved": "2 independent axes at >= 0.25",
        "rulings": out,
    }
