"""M6 — one-parameter-at-a-time realization audit, every family.

The flake block audit found two dead parameters out of six in the one
place anyone had looked. This module runs the same instrument across
EVERY declared parameter of EVERY family: vary the parameter alone at
fixed seed, render, and record the scene-linear frame delta. A
parameter that produces a bit-identical frame is DECLARED_NOT_REALIZED
— found before it can shape a verdict or reach a supplier.

Classes:
- REALIZED — frame delta above the R2 floor;
- DECLARED_NOT_REALIZED — bit-identical (or sub-floor) frame;
- GEOMETRY_DECLARED_CONSUMER_PENDING — fill_depth_mm, powder_recess_mm,
  crown_height_mm, edge_profile and the BAKED dome block target the
  powder VOLUME builder, which does not consume them yet (the BAKED
  geometry node is the declared consumer); a render audit cannot see
  them by design and rendering them would manufacture a false DEAD.

Findings are REPORTED, never fixed here. Anything load-bearing for a
banked verdict is a separate flagged node. The coverage test asserts
every declared parameter carries a recorded audit entry, so a new
parameter cannot join a family without demonstrating what it does.
"""
from __future__ import annotations

import json
import os

from apps.pipeline.services import palette_characterization_rig as CR
from apps.pipeline.services import palette_powder_engine as PE
from apps.pipeline.services import palette_powder_protocol as PP
from apps.pipeline.services import palette_powder_texture_axes as TX

SCHEMA = "parameter_realization_audit/1.0"

GEOMETRY_PENDING = ("fill_depth_mm", "powder_recess_mm",
                    "crown_height_mm", "edge_profile", "dome")


def _leaves(d, prefix=""):
    for k, v in d.items():
        path = f"{prefix}{k}"
        if isinstance(v, dict):
            yield from _leaves(v, path + ".")
        else:
            yield path, v


def _vary(value):
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value * 1.6 if value else 0.3
    if isinstance(value, str):
        return value + "_PROBE"
    if isinstance(value, list):
        n = len(value)
        return [round(1.0 / n, 6)] * n if n else value
    return value


def _override_for(path, new_value):
    keys = path.split(".")
    node = {keys[-1]: new_value}
    for k in reversed(keys[:-1]):
        node = {k: node}
    return node


def audit_family(family, out_dir, *, seed, samples=24) -> dict:
    shade = PE.PowderShade("prov_realize_audit", (0.62, 0.55, 0.48),
                           PE.PROVISIONAL_VISUALIZATION_SHADE)
    base_spec = PE.PowderMaterialSpec(family, shade, seed=seed)
    base = CR.characterize_powder(base_spec, out_dir,
                                  label=f"ra_{family}_base",
                                  samples=samples)
    idx = CR.region_indices(out_dir)
    base_frame = TX.load_scene_linear(base["exr"])
    rows = {}
    for path, value in sorted(_leaves(base_spec.params)):
        root = path.split(".")[0]
        if root in GEOMETRY_PENDING:
            rows[path] = {"class": "GEOMETRY_DECLARED_CONSUMER_PENDING",
                          "declared_consumer": "the BAKED powder-volume "
                                               "geometry node (pending)"}
            continue
        varied = _vary(value)
        if varied == value:
            rows[path] = {"class": "UNVARIABLE", "value": value}
            continue
        try:
            spec = PE.PowderMaterialSpec(
                family, shade, seed=seed,
                overrides=_override_for(path, varied))
        except PE.PowderSpecError as exc:
            # validator-coupled parameters get a compliant variation
            try:
                spec = PE.PowderMaterialSpec(
                    family, shade, seed=seed,
                    overrides=_override_for(
                        path, value * 0.5
                        if isinstance(value, (int, float)) else varied))
            except PE.PowderSpecError:
                rows[path] = {"class": "VALIDATOR_COUPLED",
                              "error": str(exc)[:80]}
                continue
        label = f"ra_{family}_{path.replace('.', '_')}"
        d = CR.characterize_powder(spec, out_dir, label=label,
                                   samples=samples)
        frame = TX.load_scene_linear(d["exr"])
        r = TX.stimulus_realization(base_frame, frame, idx)
        rows[path] = {
            "class": ("REALIZED" if r["realized"]
                      else "DECLARED_NOT_REALIZED"),
            "rms_over_mean": r["rms_over_mean"],
            "varied": f"{value!r} -> {varied!r}"[:60],
        }
    return rows


def run_audit(out_dir, *, samples=24) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    report = {"record_type": SCHEMA,
              "method": "one parameter varied alone at fixed seed; "
                        "scene-linear frame delta against the family "
                        "base through the R2 machinery",
              "families": {}, "dead": [], "geometry_pending": []}
    for i, family in enumerate(PP.POWDER_FAMILIES):
        rows = audit_family(family, out_dir, seed=200 + i,
                            samples=samples)
        report["families"][family] = rows
        for path, row in rows.items():
            if row["class"] == "DECLARED_NOT_REALIZED":
                report["dead"].append(f"{family}.{path}")
            elif row["class"] == "GEOMETRY_DECLARED_CONSUMER_PENDING":
                report["geometry_pending"].append(f"{family}.{path}")
        with open(os.path.join(out_dir, "realization_audit.json"),
                  "w") as fh:
            json.dump(report, fh, indent=2)
    report["findings_reported_not_fixed"] = True
    report["owner_approved"] = False
    with open(os.path.join(out_dir, "realization_audit.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    return report
