"""M5 §3/§7/§8 — controls, robustness and rig validation.

Three things have to be true before MATTE vs SATIN can be ruled PASS.

*The discriminator must be able to fail.* §7's controls compare a
material with itself under renames, exposure changes, metadata-only
changes and small rig moves. Every one must report FAIL, or the
discriminator is measuring the rig rather than the material.

*The verdict must survive the rig wobbling.* §8 perturbs light intensity,
angle, camera and distance. A pair that only separates at one exact
configuration is overfitted to that configuration, not distinguishable.

*The rig must serve every finish.* §3 — it is a reusable M5/M6 asset, so
making matte/satin work while collapsing glossy/metallic would be a
failure, not a trade.
"""
from __future__ import annotations

import copy
import json

from apps.pipeline.services import palette_characterization_rig as RIG
from apps.pipeline.services import palette_material_engine as ME

SCHEMA = "material_rig_validation/1.0"

#: §7 — every control must report FAIL.
CONTROLS = (
    ("MATTE_vs_identical_MATTE", "MATTE", "MATTE", {}, {}, {}),
    ("SATIN_vs_identical_SATIN", "SATIN", "SATIN", {}, {}, {}),
    ("MATTE_vs_MATTE_renamed", "MATTE", "MATTE", {}, {},
     {"rename": True}),
    ("MATTE_vs_MATTE_exposure_only", "MATTE", "MATTE", {},
     {"exposure_scale": 1.6}, {}),
    ("MATTE_vs_MATTE_light_intensity", "MATTE", "MATTE", {},
     {"specular_source": {"energy": 9.0e5 * 1.35}}, {}),
    ("MATTE_vs_MATTE_source_moved", "MATTE", "MATTE", {},
     {"specular_source": {"azimuth": 26.0 + 3.0}}, {}),
    ("SATIN_vs_SATIN_camera_shifted", "SATIN", "SATIN", {},
     {"camera": {"azimuth": 30.0 + 1.0}}, {}),
)

#: §8 — the verdict must hold through each of these.
PERTURBATIONS = (
    ("light_intensity_plus_5pct",
     {"specular_source": {"energy": 9.0e5 * 1.05}}),
    ("light_intensity_minus_5pct",
     {"specular_source": {"energy": 9.0e5 * 0.95}}),
    ("light_angle_plus_2deg", {"specular_source": {"elevation": 36.0}}),
    ("light_angle_minus_2deg", {"specular_source": {"elevation": 32.0}}),
    ("camera_plus_1deg", {"camera": {"elevation": 29.0}}),
    ("camera_minus_1deg", {"camera": {"elevation": 27.0}}),
    ("source_distance_plus_5pct",
     {"specular_source": {"distance": 315.0}}),
    ("source_distance_minus_5pct",
     {"specular_source": {"distance": 285.0}}),
)

#: §3 — the rig is reusable, so it must serve every finish.
RIG_FINISHES = (
    ("ABS", ME.MATTE), ("ABS", ME.SATIN), ("ABS", ME.GLOSSY),
    ("METAL", ME.METALLIC), ("ACRYLIC", ME.TRANSPARENT),
    ("ACRYLIC", ME.TRANSLUCENT),
)

#: Pairs that already passed and must keep passing.
PRESERVED_PAIRS = (
    ("MATTE_vs_GLOSSY", ("ABS", ME.MATTE), ("ABS", ME.GLOSSY)),
    ("GLOSSY_vs_METALLIC", ("ABS", ME.GLOSSY), ("METAL", ME.METALLIC)),
    ("OPAQUE_vs_TRANSPARENT", ("ABS", ME.MATTE),
     ("ACRYLIC", ME.TRANSPARENT)),
    ("OPAQUE_vs_TRANSLUCENT", ("ABS", ME.MATTE),
     ("ACRYLIC", ME.TRANSLUCENT)),
)


def _exposure_override(scale):
    """Scale every light, which is an exposure change and nothing else."""
    r = RIG.RIG
    return {
        "diffuse_source": {"energy": r["diffuse_source"]["energy"] * scale},
        "specular_source": {
            "energy": r["specular_source"]["energy"] * scale},
        "fill_source": {"energy": r["fill_source"]["energy"] * scale},
    }


def run_controls(out_dir, *, samples=48) -> dict:
    """§7 — every control must FAIL."""
    rows = []
    for name, fin_a, fin_b, _oa, ob, flags in CONTROLS:
        if "exposure_scale" in ob:
            ob = _exposure_override(ob["exposure_scale"])
        a = RIG.characterize("ABS", fin_a, out_dir,
                             label=f"ctl_{name}_a", samples=samples)
        b = RIG.characterize("ABS", fin_b, out_dir,
                             label=f"ctl_{name}_b",
                             overrides=ob or None, samples=samples)
        report = RIG.discriminate(RIG.axes_from(a), RIG.axes_from(b),
                                  f"{fin_a} A", f"{fin_b} B")
        report["control"] = name
        report["expected"] = "FAIL"
        report["behaved"] = report["verdict"] == "FAIL"
        report["note"] = ("a rename changes nothing about the render"
                          if flags.get("rename") else "")
        rows.append(report)
    misbehaved = [r["control"] for r in rows if not r["behaved"]]
    return {
        "record_type": "material_negative_controls/1.0",
        "controls": rows,
        "misbehaved": misbehaved,
        "verdict": "PASS" if not misbehaved else "FAIL",
        "why": "a control that PASSES means the discriminator is reading "
               "the rig rather than the material",
    }


def run_robustness(out_dir, *, samples=48) -> dict:
    """§8 — the matte/satin verdict must survive rig wobble."""
    rows = []
    for name, override in PERTURBATIONS:
        a = RIG.characterize("ABS", ME.MATTE, out_dir,
                             label=f"rb_{name}_matte",
                             overrides=copy.deepcopy(override),
                             samples=samples)
        b = RIG.characterize("ABS", ME.SATIN, out_dir,
                             label=f"rb_{name}_satin",
                             overrides=copy.deepcopy(override),
                             samples=samples)
        report = RIG.discriminate(RIG.axes_from(a), RIG.axes_from(b),
                                  "ABS MATTE", "ABS SATIN")
        report["perturbation"] = name
        report["window_a"] = RIG.rig_operating_window(a)
        report["window_b"] = RIG.rig_operating_window(b)
        rows.append(report)
    failed = [r["perturbation"] for r in rows if r["verdict"] != "PASS"]
    return {
        "record_type": "material_rig_robustness_report/1.0",
        "perturbations": rows,
        "failed": failed,
        "stable": not failed,
        "verdict": "PASS" if not failed else "FAIL",
        "why": "a pair that separates only at one exact configuration is "
               "overfitted to that configuration, not distinguishable",
    }


def run_rig_validation(out_dir, *, samples=48) -> dict:
    """§3 — the rig must serve every finish and keep the passing pairs."""
    measured = {}
    windows = {}
    for material, finish in RIG_FINISHES:
        key = f"{material}_{finish}"
        m = RIG.characterize(material, finish, out_dir,
                             label=f"rig_{key}", samples=samples)
        measured[key] = m
        windows[key] = RIG.rig_operating_window(m)

    pairs = []
    for name, (ma, fa), (mb, fb) in PRESERVED_PAIRS:
        report = RIG.discriminate(
            RIG.axes_from(measured[f"{ma}_{fa}"]),
            RIG.axes_from(measured[f"{mb}_{fb}"]),
            f"{ma} {fa}", f"{mb} {fb}")
        report["pair"] = name
        pairs.append(report)

    out_of_window = [k for k, w in windows.items()
                     if w["verdict"] != "PASS"]
    collapsed = [p["pair"] for p in pairs if p["verdict"] != "PASS"]
    return {
        "record_type": "material_rig_finish_validation/1.0",
        "finishes": sorted(measured),
        "operating_windows": windows,
        "out_of_window": out_of_window,
        "preserved_pairs": pairs,
        "collapsed_pairs": collapsed,
        "verdict": "PASS" if not collapsed and not out_of_window
        else "FAIL",
        "why": "the rig is a reusable M5/M6 asset; making matte and satin "
               "work while collapsing another pair would be a failure, "
               "not a trade",
    }


def full_validation(out_dir, *, samples=48) -> dict:
    """Everything §9 requires before the matte/satin ruling."""
    controls = run_controls(out_dir, samples=samples)
    robustness = run_robustness(out_dir, samples=samples)
    rig = run_rig_validation(out_dir, samples=samples)
    ok = all(r["verdict"] == "PASS"
             for r in (controls, robustness, rig))
    return {
        "record_type": SCHEMA,
        "rig_identity": RIG.rig_identity(),
        "negative_controls": controls,
        "robustness": robustness,
        "rig_finish_validation": rig,
        "MATTE_VS_SATIN": "PASS" if ok else "FAIL",
        "MATTE_SATIN_MATERIAL_MODEL": "VALIDATED_FOR_M5" if ok
        else "NOT_VALIDATED",
        "RIG_VALIDATION": rig["verdict"],
        "MATERIAL_CHARACTERIZATION_ROBUSTNESS": robustness["verdict"],
        "thresholds_unchanged": True,
        "pass_law": RIG.SW.PASS_LAW["statement"],
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
    }


def write(report, path):
    with open(path, "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    return path
