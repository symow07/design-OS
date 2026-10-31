"""M6 — MARBLING_STRUCTURE_RIG: chromatic-spatial structure.

Both attached jobs, in one node:
1. the rig — deterministic spatial multi-colour structure, with
   illumination that must not add structure of its own (validity
   illumination_uniformity_max_deviation 0.08, MEASURED as a number on
   a smooth uniform reference at commissioning);
2. the audit discharge — MARBLED is the common microtexture block's
   only consumer; the realization audit already measured the block
   REALIZED for MARBLED and dead for the other eight families, and
   this record carries the pre-committed reading of that outcome.

COLOUR AUTHORITY, in the verdict and not discoverable later: the
marble component colours are DERIVED, not chosen, so the measured
chroma contrast IS the product of the derivation's coefficients. A PASS
here certifies spatial structure produced by those coefficients on
whatever shade was supplied — never a statement about a declared
palette.

SUPERSEDED IN PLACE 2026-08-13: this paragraph read "derived by x0.55
(darker) and x1.35+0.05 (lighter) — two coefficients that exist only in
builder code". That was true PRE-REPAIR. The C6 chromatic repair
replaced the scalar form with PER_CHANNEL_ASYMMETRIC_CHROMATIC, now
declared in palette_powder_engine (params.shader.component_derivation)
rather than existing only in builder code, and enforced by
powder_materials._derived_components, which raises on any other form.
The live coefficients are in DERIVED_COEFFICIENTS below. Every chroma
number this rig measured BEFORE the repair was produced by the scalar
form, which is why the SOLID_VS_MARBLED FAIL carries
VOIDED_BY_REPAIR_2026_08_08.

SHADE-INVARIANCE is a required negative control: the SOLID_VS_MARBLED
distinction must hold under a different provisional shade assignment,
or it is a fact about which placeholders were chosen rather than
about marbling as a structure.

AXES, declared before any frame (chroma measured scene-linear RGB
from the EXR through the same provenance assertions):
- MARBLE_CHROMA_SPAN (independent): p95 - p5 of the chroma channel
  (R - B) / (R + G + B + eps) over PLANAR — the amplitude of colour
  separation between marble components.
- MARBLE_CHROMA_COHERENCE (independent): fraction of chroma variance
  captured by an 8x8 block-mean downsample — spatial REGIONS score
  high, per-pixel speckle scores low. Different formula, different
  normalisation.
"""
from __future__ import annotations

import hashlib
import json
import os

import numpy as np

from apps.pipeline.services import palette_characterization_rig as CR
from apps.pipeline.services import palette_powder_engine as PE
from apps.pipeline.services import palette_powder_protocol as PP
from apps.pipeline.services import palette_powder_texture_axes as TX

SCHEMA = "marbling_structure_rig/1.0"

UNIFORMITY_MAX = PP.SUB_RIGS["MARBLING_STRUCTURE_RIG"][
    "validity"]["illumination_uniformity_max_deviation"]

#: flat even illumination: one broad overhead source, minimal fill —
#: the question is chromatic-spatial, so the light must be boring
RIG_OVERRIDES = {
    "diffuse_source": {"azimuth": 0.0, "elevation": 80.0,
                       "distance": 420.0, "size": 400.0,
                       "energy": 5.0e4},
    "specular_source": {"energy": 0.0},
    "fill_source": {"energy": 0.0},
}

MARBLE_AXES = {
    "MARBLE_CHROMA_SPAN": {"independent": True},
    "MARBLE_CHROMA_COHERENCE": {"independent": True},
}
FLOOR_SEEDS = (500, 501, 502, 503, 504, 505)
SEPARATION_MARGIN = 2.0
PASS_BAR = 0.25

#: SUPERSEDED IN PLACE 2026-08-13. The text below read "component
#: colours derived by x0.55 (darker) and x1.35+0.05 (lighter)". That was
#: ACCURATE PRE-REPAIR and is now false: the C6 chromatic repair replaced
#: the scalar form, and blender_scripts/powder_materials.py
#: _derived_components now RAISES ValueError unless
#: form == "PER_CHANNEL_ASYMMETRIC_CHROMATIC". Retained as the claim
#: under which every pre-repair chroma number on this rig was computed,
#: including the SOLID_VS_MARBLED FAIL that VOIDED_BY_REPAIR_2026_08_08
#: withdrew. A correction, not an error — the constant described the
#: builder it was written against.
DERIVED_COEFFICIENTS = (
    "component colours derived PER CHANNEL: darker = rgb x "
    "[0.45, 0.55, 0.70]; lighter = rgb x [1.45, 1.30, 1.15] + "
    "[0.08, 0.05, 0.02]. Form PER_CHANNEL_ASYMMETRIC_CHROMATIC, enforced "
    "in powder_materials._derived_components, which raises on any other "
    "form. Declared in palette_powder_engine params.shader."
    "component_derivation. NOTE: marbling.components defaults to 2, so "
    "_derived_components returns [base, darker] and THE ADDITIVE OFFSETS "
    "NEVER ENTER at default — the lighter component with its offsets is "
    "reached only at components == 3. Both terms in play are per-channel "
    "MULTIPLICATIVE, and (R-B)/(R+G+B) is scale-invariant, so the chroma "
    "separation between the mixed components does not change with "
    "lightness. SUPERSEDES the pre-repair scalar x0.55 / x1.35+0.05, "
    "which is retained in the comment above.")


class MarblingRigError(RuntimeError):
    pass


def load_scene_linear_rgb(exr_path):
    """RGB variant of the R1 loader — same assertions, same flip."""
    import cv2
    arr = cv2.imread(exr_path, cv2.IMREAD_UNCHANGED)
    if arr is None:
        raise TX.FrameProvenanceError("frame unreadable")
    if arr.dtype == np.uint8 or not np.issubdtype(arr.dtype,
                                                  np.floating):
        raise TX.FrameProvenanceError(f"refused dtype {arr.dtype}")
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise TX.FrameProvenanceError(f"shape {arr.shape}")
    # cv2 is BGR; flip channels to RGB and rows to index order
    return arr[..., :3][..., ::-1][::-1].astype(np.float64)


def _measure(spec_or_plain, out_dir, label, *, samples=48):
    if isinstance(spec_or_plain, dict):
        d = None
        # plain (non-powder) uniform reference through the same rig
        import tempfile
        png = os.path.join(out_dir, f"{label}.png")
        exr = os.path.join(out_dir, f"{label}.exr")
        meas = os.path.join(out_dir, f"{label}.json")
        idx = CR.region_indices(out_dir)
        with tempfile.TemporaryDirectory() as td:
            cfg = CR._base_cfg(td, RIG_OVERRIDES)
            cfg.update({"material": spec_or_plain, "png": png,
                        "exr": exr, "measurements": meas,
                        "region_indices": idx, "samples": samples,
                        "material_identity": "uniform_reference",
                        "render_identity": hashlib.sha256(
                            label.encode()).hexdigest()[:16]})
            CR._run(cfg, td)
        d = json.load(open(meas))
        d["png"], d["exr"], d["label"] = png, exr, label
        return d
    return CR.characterize_powder(spec_or_plain, out_dir, label=label,
                                  overrides=RIG_OVERRIDES,
                                  samples=samples)


def marble_axes(exr_path, region_idx) -> dict:
    rgb = load_scene_linear_rgb(exr_path)
    lum = rgb.mean(axis=2)
    mask = np.zeros(lum.size, dtype=bool)
    mask[np.asarray(region_idx["PLANAR"], dtype=int)] = True
    mask = mask.reshape(lum.shape)
    eps = 1e-6
    chroma = (rgb[..., 0] - rgb[..., 2]) / (rgb.sum(axis=2) + eps)
    vals = chroma[mask]
    if vals.size < 1000:
        raise MarblingRigError("PLANAR region too small for chroma")
    span = float(np.percentile(vals, 95) - np.percentile(vals, 5))

    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    crop = np.where(mask, chroma, np.nan)[y0:y1 + 1, x0:x1 + 1]
    H, W = crop.shape
    bh, bw = max(H // 8, 1), max(W // 8, 1)
    blocks = []
    for i in range(8):
        for j in range(8):
            cell = crop[i * bh:(i + 1) * bh, j * bw:(j + 1) * bw]
            if np.isfinite(cell).sum() > 10:
                blocks.append(float(np.nanmean(cell)))
    total_var = float(np.nanvar(crop))
    if total_var <= 1e-12:
        raise MarblingRigError("zero chroma variance — refusing to "
                               "report coherence of nothing")
    block_var = float(np.var(blocks))
    coherence = min(block_var / total_var, 1.0)
    return {"MARBLE_CHROMA_SPAN": round(span, 6),
            "MARBLE_CHROMA_COHERENCE": round(coherence, 6)}


def _effect(a, b):
    mean = (abs(a) + abs(b)) / 2.0
    return abs(a - b) / mean if mean > 1e-9 else 0.0


def commission_marbling(out_dir, *, samples=48) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    idx = CR.region_indices(out_dir)

    # (1) illumination uniformity, measured as a number
    uniform = _measure({"display_rgb": [0.7, 0.7, 0.7],
                        "roughness": 0.8, "metallic": 0.0},
                       out_dir, "mb_uniform_reference",
                       samples=samples)
    r = uniform["regions"]["PLANAR"]
    deviation = (float(r["percentiles"]["95"])
                 - float(r["percentiles"]["5"])) \
        / float(r["scene_linear_median"])
    commissioning = {"illumination_uniformity_deviation":
                     round(deviation, 5),
                     "gate": UNIFORMITY_MAX,
                     "frames": ["mb_uniform_reference.png"]}
    if deviation > UNIFORMITY_MAX:
        raise MarblingRigError(f"illumination adds structure: "
                               f"{deviation:.4f} > {UNIFORMITY_MAX}")

    warm = PE.PowderShade("prov_dark_warm_sienna", (0.38, 0.22, 0.14),
                          PE.PROVISIONAL_VISUALIZATION_SHADE)
    cool = PE.PowderShade("prov_dark_cool_plum", (0.30, 0.18, 0.26),
                          PE.PROVISIONAL_VISUALIZATION_SHADE)

    # (2) floors from a marbled seed ensemble
    ensemble = {}
    for seed in FLOOR_SEEDS:
        d = _measure(PE.PowderMaterialSpec(PP.MARBLED, warm, seed=seed),
                     out_dir, f"mb_ens_{seed}", samples=samples)
        ensemble[seed] = marble_axes(d["exr"], idx)
    floors = {}
    for axis in MARBLE_AXES:
        vals = [ensemble[s][axis] for s in FLOOR_SEEDS]
        effs = [_effect(vals[i], vals[j])
                for i in range(len(vals))
                for j in range(i + 1, len(vals))]
        floors[axis] = {"floor": round(max(effs), 5),
                        "eligible": bool(max(effs) < PASS_BAR),
                        "required": round(max(PASS_BAR, max(effs)
                                              * SEPARATION_MARGIN), 5)}

    def adjudicate(marbled_axes_v, solid_axes_v):
        rows, counted = {}, []
        for axis in MARBLE_AXES:
            eff = _effect(marbled_axes_v[axis], solid_axes_v[axis])
            fl = floors[axis]
            reasons = []
            if not fl["eligible"]:
                reasons.append(f"INELIGIBLE_{fl['floor']}")
            if eff < fl["required"]:
                reasons.append("BELOW_REQUIRED")
            if not reasons:
                counted.append(axis)
            rows[axis] = {"marbled": marbled_axes_v[axis],
                          "solid": solid_axes_v[axis],
                          "effect": round(eff, 5),
                          "counts": not reasons, "reasons": reasons}
        return rows, counted

    # (3) SOLID_VS_MARBLED, warm shade
    marbled_w = ensemble[FLOOR_SEEDS[0]]
    solid_w_d = _measure(PE.PowderMaterialSpec(PP.POWDER_MATTE, warm,
                                               seed=FLOOR_SEEDS[0]),
                         out_dir, "mb_solid_warm", samples=samples)
    solid_w = marble_axes(solid_w_d["exr"], idx)
    rows_w, counted_w = adjudicate(marbled_w, solid_w)

    # (4) shade-invariance: the same pair under a DIFFERENT
    # provisional assignment must hold
    marbled_c_d = _measure(PE.PowderMaterialSpec(PP.MARBLED, cool,
                                                 seed=FLOOR_SEEDS[0]),
                           out_dir, "mb_marbled_cool", samples=samples)
    marbled_c = marble_axes(marbled_c_d["exr"], idx)
    solid_c_d = _measure(PE.PowderMaterialSpec(PP.POWDER_MATTE, cool,
                                               seed=FLOOR_SEEDS[0]),
                         out_dir, "mb_solid_cool", samples=samples)
    solid_c = marble_axes(solid_c_d["exr"], idx)
    rows_c, counted_c = adjudicate(marbled_c, solid_c)

    verdict_w = "PASS" if len(counted_w) >= 2 else "FAIL"
    verdict_c = "PASS" if len(counted_c) >= 2 else "FAIL"
    shade_invariant = verdict_w == verdict_c == "PASS"

    audit = json.load(open("docs/roadmap/palt_m6/realization_audit/"
                           "realization_audit.json"))
    micro_rows = {k: v for k, v in
                  audit["families"]["MARBLED"].items()
                  if k.startswith("microtexture")}
    micro_live = all(v.get("class") == "REALIZED"
                     for v in micro_rows.values())

    record = {
        "record_type": SCHEMA,
        "commissioning": commissioning,
        "floors": floors,
        "derived_coefficients_in_the_verdict": DERIVED_COEFFICIENTS,
        "colour_authority": ("every shade PROVISIONAL_VISUALIZATION_"
                            "SHADE, NO_AUTHORITATIVE_SOURCE — this "
                            "verdict is about spatial structure and "
                            "is never readable as a palette decision"),
        "pair_warm": rows_w, "verdict_warm": verdict_w,
        "pair_cool_shade_swap": rows_c, "verdict_cool": verdict_c,
        "shade_invariance": ("HOLDS — the distinction is about "
                            "structure, not about which placeholders "
                            "were chosen" if shade_invariant else
                            "FAILS — the distinction is a fact about "
                            "one placeholder pair; recorded before M7 "
                            "could inherit it"),
        "SOLID_VS_MARBLED": ("PASS" if shade_invariant else "FAIL"),
        "microtexture_block_discharge": {
            "pre_committed": "live -> engine count stands at 49/123; "
                             "dead -> rises",
            "audit_rows": micro_rows,
            "outcome": ("LIVE_FOR_ITS_ONLY_CONSUMER — the count "
                        "stands at 49 of 123" if micro_live else
                        "DEAD_ENGINE_WIDE — the fraction rises"),
        },
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
    }
    with open(os.path.join(out_dir, "marbling_commissioning.json"),
              "w") as fh:
        json.dump(record, fh, indent=2)
    return record
