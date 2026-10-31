"""M6 §§2-7 — the diffuse-pair axis diagnosis.

Three pairs sit at one-of-two axes and the cause is UNRESOLVED between
MATERIAL_MODEL_INSUFFICIENT and CHARACTERIZATION_AXIS_INSUFFICIENT. The
family shaders are FROZEN for this study: the instrument is a set of
synthetic fixtures in which exactly ONE physical property changes, and
the question is which of the six existing axes can even see each
property. An axis that cannot respond to the property it is supposed to
measure must not be used to judge that property — and a family must not
be re-tuned to please an axis that is blind to it.

The sensitivity criterion is the pass law's own bar (25% relative
effect), declared here before any fixture renders. Every fixture pair
shares its seed, so the ONLY difference is the named property.
"""
from __future__ import annotations

import json
import os

from apps.pipeline.services import palette_characterization_rig as CR
from apps.pipeline.services import palette_powder_engine as PE
from apps.pipeline.services import palette_powder_protocol as PP
from apps.pipeline.services import palette_firing_trace as FT

SCHEMA = "diffuse_axis_sensitivity_study/1.0"

#: the sensitivity criterion IS the pass law's effect bar — an axis
#: that cannot produce a passable effect from a strong single-property
#: change cannot carry that property in a real pair either
SENSITIVITY_BAR = 0.25

AXES = ("HIGHLIGHT_FWHM", "HIGHLIGHT_PEAK", "SPECULAR_TO_DIFFUSE_RATIO",
        "GRAZING_RESPONSE", "SHEEN_REGION_RESPONSE",
        "EDGE_HIGHLIGHT_RESPONSE")

_SHADE = ("prov_diag_neutral", (0.62, 0.55, 0.48))


def _spec(family, seed, overrides):
    shade = PE.PowderShade(_SHADE[0], _SHADE[1],
                           PE.PROVISIONAL_VISUALIZATION_SHADE)
    return PE.PowderMaterialSpec(family, shade, seed=seed,
                                 overrides=overrides)


#: §4 — six single-property perturbation pairs. Same family, same seed,
#: same everything except the named property.
FIXTURES = {
    "MICRO_NORMAL_AMPLITUDE": {
        "property": "micro-normal field amplitude (grain strength)",
        "family": PP.POWDER_MATTE, "seed": 70,
        "low": {"milling": {"micronormal_amplitude": 0.10}},
        "high": {"milling": {"micronormal_amplitude": 0.34}},
    },
    "MICRO_NORMAL_CORRELATION": {
        "property": "grain scale / correlation length",
        "family": PP.POWDER_MATTE, "seed": 71,
        "low": {"milling": {"microparticle_scale_mm": 0.21,
                            "micronormal_amplitude": 0.22}},
        "high": {"milling": {"microparticle_scale_mm": 0.42,
                             "micronormal_amplitude": 0.22}},
    },
    "MICROTEXTURE_VARIANCE": {
        "property": "uniform versus heterogeneous powder structure",
        "family": PP.POWDER_MATTE, "seed": 72,
        "low": {"milling": {"microparticle_variance": 0.10}},
        "high": {"milling": {"microparticle_variance": 0.90}},
    },
    "COMPACTION": {
        "property": "uncompacted versus highly compacted surface",
        "family": PP.PRESSED_POWDER, "seed": 73,
        "low": {"compaction": {"compaction_level": 0.0,
                               "surface_flatness": 0.0}},
        "high": {"compaction": {"compaction_level": 0.90,
                                "surface_flatness": 0.90}},
    },
    "SURFACE_CONTINUITY": {
        "property": "granular powder versus continuous surface",
        "family": PP.POWDER_MATTE, "seed": 74,
        #: 0.005 was so smooth its brightness under the mirror source
        #: sat 3.2x from the rough side — outside any single-energy
        #: window — and the guard refused to measure it. 0.02 remains a
        #: 17x single-property contrast the rig CAN hold in-window: a
        #: fixture the rig cannot see is a broken fixture, not a
        #: broken law (the transmission-target precedent).
        "low": {"milling": {"micronormal_amplitude": 0.02}},
        "high": {"milling": {"micronormal_amplitude": 0.34}},
    },
    "ROUGHNESS_ONLY": {
        "property": "roughness constant alone (identifies axes that "
                    "are merely roughness detectors)",
        "family": PP.POWDER_MATTE, "seed": 75,
        "low": {"surface_roughness": 0.65},
        "high": {"surface_roughness": 0.95},
    },
}


def run_study(out_dir, *, samples=64) -> dict:
    """Render every fixture pair on the FROZEN rig and fill the
    AXIS x PROPERTY sensitivity matrix."""
    os.makedirs(out_dir, exist_ok=True)
    matrix = {}
    detail = {}
    for name, fx in FIXTURES.items():
        row = {}
        axes = {}
        for side in ("low", "high"):
            spec = _spec(fx["family"], fx["seed"], fx[side])
            d = CR.characterize_powder(
                spec, out_dir, label=f"sens_{name}_{side}",
                samples=samples)
            axes[side] = CR.axes_from(d)
        norm = {s: CR.normalized(a) for s, a in axes.items()}
        for axis in AXES:
            va, vb = float(norm["low"][axis]), float(norm["high"][axis])
            mean = (abs(va) + abs(vb)) / 2.0
            effect = abs(va - vb) / mean if mean > 1e-9 else FT.traced_zero("palette_powder_axis_diagnosis.py:run_study", "guard")
            row[axis] = {"low": round(va, 5), "high": round(vb, 5),
                         "relative_effect": round(effect, 4),
                         "detects": bool(effect >= SENSITIVITY_BAR)}
        matrix[name] = {a: row[a]["detects"] for a in AXES}
        detail[name] = {"property": fx["property"], "axes": row}

    blind_properties = [name for name, dets in matrix.items()
                        if name != "ROUGHNESS_ONLY"
                        and not any(dets.values())]
    roughness_detectors = [a for a in AXES
                           if matrix["ROUGHNESS_ONLY"][a]]
    return {
        "record_type": SCHEMA,
        "protocol_identity": PP.protocol_identity(),
        "sensitivity_bar": SENSITIVITY_BAR,
        "shaders_frozen": True,
        "matrix": matrix,
        "detail": detail,
        "properties_no_axis_detects": blind_properties,
        "axes_that_are_roughness_detectors": roughness_detectors,
        "reading": "an axis that cannot respond to a property must not "
                   "judge that property; a property no axis detects is "
                   "CHARACTERIZATION_AXIS_INSUFFICIENT by measurement",
    }


def write_study(out_dir, record):
    path = os.path.join(out_dir, "axis_sensitivity_matrix.json")
    with open(path, "w") as fh:
        json.dump(record, fh, indent=2)
    return path
