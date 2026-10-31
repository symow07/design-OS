"""M5 §1-§8 — the MATERIAL_CHARACTERIZATION_PROTOCOL.

One lighting setup cannot characterize every physical material class. A
dielectric lobe is read against darkness; a metal is read against what it
reflects; a transmissive material is read against what stands behind it.
Demanding that a single rig answer all three questions is how a metal
ended up at 0.114 scene-linear in a black room.

So the protocol is three fixed sub-rigs, each selected by the PHYSICAL
QUESTION being asked — never by the desired answer:

* ``DIELECTRIC_LOBE_RIG`` — matte / satin / glossy plastic. This is the
  already-validated matte-vs-satin rig, unchanged.
* ``REFLECTIVE_MATERIAL_RIG`` — metallic against glossy plastic, in a
  deterministic neutral panel environment that gives a reflection
  something to be OF.
* ``TRANSMISSION_RIG`` — opaque / transparent / translucent, against a
  deterministic bar target whose visibility through the material is the
  measurement.

Every validity condition and pass bar in this module is declared here,
in code, before the corresponding measurement is run. The matte/satin
thresholds and the 2-axis pass law are untouched.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile

from apps.pipeline.services import geometry_validation_render as gvr
from apps.pipeline.services import palette_characterization_rig as DRIG
from apps.pipeline.services import palette_material_swatch as SW

SCHEMA = "material_characterization_protocol/1.0"
VERSION = 1

SCRIPT = os.path.join(os.path.dirname(gvr.SCRIPT),
                      "material_characterization.py")

# ==========================================================================
# sub-rig A — dielectric lobe (the validated matte/satin rig, by reference)
# ==========================================================================

DIELECTRIC_LOBE_RIG = {
    "name": "DIELECTRIC_LOBE_RIG",
    "scope": ["ABS_MATTE", "ABS_SATIN", "ABS_GLOSSY", "PP_MATTE",
              "PP_SATIN"],
    "question": "how wide and how tall is the specular lobe of a "
                "dielectric surface",
    "implementation": "palette_characterization_rig (unchanged)",
    "validity": {"peak_scene_linear_window": [0.35, 0.92],
                 "maximum_clipped_samples": 0},
    "status_basis": "validated by the matte/satin ruling: pass law, seven "
                    "negative controls and eight perturbations",
}

# ==========================================================================
# sub-rig B — reflective material
# ==========================================================================

#: §3 — the neutral reflection environment. Deterministic panels with
#: pinned luminances; no HDRI, no colour, no beauty scene. The bright
#: strip is what gives a coherent reflection a recognisable feature.
REFLECTIVE_MATERIAL_RIG = {
    "name": "REFLECTIVE_MATERIAL_RIG",
    "scope": ["METAL_METALLIC", "ABS_GLOSSY_COMPARISON"],
    "question": "does the surface reflect its environment coherently, "
                "the way a metal does, or diffusely soften it, the way a "
                "glossy plastic does",
    "environment_panels": [
        {"name": "white_panel", "azimuth": -70.0, "elevation": 20.0,
         "distance": 420.0, "size": [360.0, 360.0], "emission": 2.2},
        {"name": "grey_panel", "azimuth": 40.0, "elevation": 15.0,
         "distance": 420.0, "size": [300.0, 300.0], "emission": 0.9},
        {"name": "black_panel", "azimuth": 130.0, "elevation": 10.0,
         "distance": 400.0, "size": [300.0, 300.0], "emission": 0.03},
        {"name": "bright_strip", "azimuth": -15.0, "elevation": 55.0,
         "distance": 380.0, "size": [30.0, 420.0], "emission": 9.0},
    ],
    "floor_panel": {"z_offset": -30.0, "size": 900.0, "grey": 0.35},
    "fill_source": {"size": 260.0, "distance": 480.0, "azimuth": 165.0,
                    "elevation": 30.0, "energy": 6.0e3},
    "camera": dict(DRIG.RIG["camera"]),
    "backdrop_colour": [0.05, 0.05, 0.055],
    "backdrop_strength": 0.15,
    "samples": 64, "clamp_indirect": 4.0, "resolution": [1200, 1200],
    "seed": 0, "exposure": 0.0, "view_transform": "Standard",

    #: §2 — validity conditions for THIS rig, declared before any
    #: metallic measurement under it. There is no universal peak window:
    #: a mirror-like surface is judged by whether the environment reads
    #: in it, not by how bright its lobe is.
    "validity": {
        "maximum_clipped_subject_samples": 0,
        #: commissioning gate: a perfect mirror reference must see the
        #: panel structure. Contrast is (p95-p5)/median of the planar
        #: region grid — exposure-invariant by construction.
        "mirror_reference_min_pattern_contrast": 0.20,
        "min_subject_peak_scene_linear": 0.05,
        "robustness_required": True,
    },
}

#: The mirror commissioning reference — rig apparatus, not a material
#: under test. A perfect reflector proves the environment produces
#: readable structure before any real material is judged in it.
MIRROR_REFERENCE_SPEC = {"display_rgb": [1.0, 1.0, 1.0],
                         "roughness": 0.02, "metallic": 1.0,
                         "transmission": 0.0}

#: §4 — the reflective axes, with their independence declared up front.
#: Correlation-type axes use an ABSOLUTE difference bar (a relative bar
#: explodes near zero); amplitude axes use the same 25% relative bar as
#: the dielectric law. Declared before measurement.
REFLECTIVE_AXES = {
    "REFLECTED_PATTERN_CONTRAST": {
        "kind": "relative", "bar": 0.25,
        "formula": "(p95-p5)/median of the PLANAR region grid",
        "independent": True},
    "REFLECTION_EDGE_SHARPNESS": {
        "kind": "relative", "bar": 0.25,
        "formula": "p95 of adjacent-cell gradient of the CONTRAST-"
                   "NORMALISED planar grid",
        "independent": True,
        "note": "normalising by contrast decorrelates it from amplitude"},
    "REFLECTION_COHERENCE": {
        "kind": "absolute", "bar": 0.25,
        "formula": "fraction of planar-grid variance captured by an 8x8 "
                   "low-frequency downsample — coherent bands score high, "
                   "speckle scores low",
        "independent": True},
    "SPECULAR_TO_DIFFUSE_RESPONSE": {
        "kind": "relative", "bar": 0.25,
        "formula": "scene-linear p99.9/median on the QUARTER_CYLINDER",
        "independent": True},
    "ENVIRONMENT_CORRELATION": {
        "kind": "absolute", "bar": 0.25,
        "formula": "Pearson correlation of the normalised planar grid "
                   "with the MIRROR REFERENCE planar grid",
        "independent": True},
    "GRAZING_REFLECTION_RESPONSE": {
        "kind": "relative", "bar": 0.25,
        "formula": "(p95-p5)/median of the GRAZING region grid",
        "independent": False,
        "note": "same formula as REFLECTED_PATTERN_CONTRAST on another "
                "region; counted as SUPPORTING, never as the second "
                "independent axis"},
}

REFLECTIVE_REQUIRED_AXES = 2

# ==========================================================================
# sub-rig C — transmission
# ==========================================================================

TRANSMISSION_RIG = {
    "name": "TRANSMISSION_RIG",
    "scope": ["ABS_MATTE_OPAQUE", "ACRYLIC_TRANSPARENT",
              "ACRYLIC_TRANSLUCENT"],
    "fixture": "CLOSED_PLATES — an open zero-thickness sheet BENDS a "
               "transmitted ray permanently where a real plate offsets "
               "it, so a sheet measures a refraction artefact rather "
               "than the material. One plate fixture for all three "
               "materials in the comparison.",
    "question": "how much of a known target survives passage through "
                "the material",
    #: the deterministic bar target, BEHIND the swatch relative to the
    #: camera: alternating bright/dark strips
    #: the target sits on the CONTINUATION of the camera's sight line —
    #: azimuth +180, elevation negated — so the camera sees it exactly
    #: through the swatch. The commissioning gate caught the first
    #: placement (elevation +24) delivering 0.0 reference contrast: the
    #: target was simply not behind the swatch from the camera's view.
    #: Two commissioning defects shaped this target, both caught by the
    #: rig's own gates rather than by a review:
    #: 1. at 26 mm pitch the 40 mm planar window saw ~1.5 bars, so there
    #:    was almost no detail to transmit;
    #: 2. a PERIODIC pattern decorrelates under the lateral shift a
    #:    refracting plate applies — correlation went blind to a shift
    #:    of half a pitch. The luminance sequence is now APERIODIC, so a
    #:    shifted view still correlates with the reference.
    #: The axes and their bars are untouched.
    "background_strips": [
        {"name": "bar_target", "azimuth": 210.0, "elevation": -28.0,
         "distance": 200.0, "count": 33, "pitch": 8.0,
         "strip_width": 4.0, "strip_height": 420.0,
         "bright": 2.0, "dark": 0.02,
         "pattern": [1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 0, 1,
                     0, 0, 1, 1, 0, 1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 1,
                     0]},
    ],
    "fill_source": {"size": 240.0, "distance": 460.0, "azimuth": -30.0,
                    "elevation": 40.0, "energy": 9.0e3},
    "camera": dict(DRIG.RIG["camera"]),
    "backdrop_colour": [0.05, 0.05, 0.055],
    "backdrop_strength": 0.15,
    "samples": 64, "clamp_indirect": 4.0, "resolution": [1200, 1200],
    "seed": 0, "exposure": 0.0, "view_transform": "Standard",
    "validity": {
        "maximum_clipped_subject_samples": 0,
        #: commissioning gate: the bar target must be visible where the
        #: swatch will stand, measured on a reference pass with the
        #: swatch hidden.
        "reference_min_pattern_contrast": 0.30,
        "robustness_required": False,
    },
}

TRANSMISSION_AXES = {
    "TRANSMITTED_CONTRAST": {
        "kind": "relative", "bar": 0.25,
        "formula": "(p95-p5)/median of the PLANAR grid with the target "
                   "behind the swatch", "independent": True},
    "BACKGROUND_VISIBILITY": {
        "kind": "absolute", "bar": 0.25,
        "formula": "Pearson correlation of the normalised planar grid "
                   "with the NO-SWATCH reference grid",
        "independent": True},
    "TRANSMITTED_DETAIL": {
        "kind": "relative", "bar": 0.25,
        "formula": "p95 gradient of the contrast-normalised planar grid",
        "independent": True},
    "SCATTERING_OR_BLUR": {
        "kind": "relative", "bar": 0.25,
        "formula": "1 minus the high-frequency variance fraction of the "
                   "planar grid",
        "independent": False,
        "note": "mathematically tied to TRANSMITTED_DETAIL; reported, "
                "never counted as a second independent axis"},
    "EDGE_TRANSMISSION": {
        "kind": "absolute", "bar": 0.25,
        "formula": "correlation of the GRAZING grid with the reference "
                   "GRAZING grid", "independent": True},
}

TRANSMISSION_REQUIRED_AXES = 2


class ProtocolError(RuntimeError):
    """Raised when the protocol cannot measure honestly."""


def protocol_identity() -> str:
    payload = json.dumps(
        {"dielectric": DIELECTRIC_LOBE_RIG,
         "reflective": REFLECTIVE_MATERIAL_RIG,
         "transmission": TRANSMISSION_RIG,
         "reflective_axes": REFLECTIVE_AXES,
         "transmission_axes": TRANSMISSION_AXES,
         "version": VERSION}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def reflective_rig_identity() -> str:
    return hashlib.sha256(json.dumps(
        REFLECTIVE_MATERIAL_RIG, sort_keys=True).encode()).hexdigest()[:16]


def transmission_rig_identity() -> str:
    return hashlib.sha256(json.dumps(
        TRANSMISSION_RIG, sort_keys=True).encode()).hexdigest()[:16]


# ==========================================================================
# rendering under a sub-rig
# ==========================================================================

def _swatch_meshes(td, fixture="sheets"):
    regions = (SW.build_swatch_regions() if fixture == "sheets"
               else SW.build_transmission_plates())
    meshes = {}
    for name, mesh in regions.items():
        path = os.path.join(td, f"{name}.obj")
        gvr.export_obj(mesh, path)
        meshes[name] = path
    return meshes


def _run(cfg, td):
    p = os.path.join(td, "cfg.json")
    json.dump(cfg, open(p, "w"))
    r = subprocess.run(
        [gvr.BLENDER, "-b", "--factory-startup", "-noaudio", "-P",
         SCRIPT, "--", p], capture_output=True, text=True, timeout=5400)
    if "MATERIAL_CHARACTERIZATION_OK" not in r.stdout:
        raise ProtocolError(r.stdout[-1500:] + r.stderr[-500:])


def _rig_cfg(rig, td, overrides=None, fixture="sheets"):
    o = overrides or {}
    r = json.loads(json.dumps(rig))
    for key in ("fill_source", "camera"):
        if key in r:
            r[key].update(o.get(key, {}))
    panels = r.get("environment_panels", [])
    for pn in panels:
        pn.update(o.get(pn["name"], {}))
    lo, hi = SW.swatch_bounds()
    return {
        "meshes": _swatch_meshes(td, fixture),
        "smooth_regions": ["SHALLOW_CURVE", "QUARTER_CYLINDER", "BEVEL"],
        "centre": ((lo + hi) / 2.0).tolist(),
        "resolution": list(r["resolution"]),
        "samples": o.get("samples", r["samples"]),
        "clamp_indirect": r["clamp_indirect"],
        "backdrop_colour": r["backdrop_colour"],
        "backdrop_strength": r["backdrop_strength"],
        "environment_panels": panels,
        "background_strips": r.get("background_strips", []),
        "floor_panel": r.get("floor_panel"),
        "fill_source": r.get("fill_source"),
        # the characterization script requires named sources; the
        # panel-lit rigs use only the fill, so the other two are zeroed
        "diffuse_source": r.get("diffuse_source",
                                {"size": 1.0, "distance": 500.0,
                                 "azimuth": 0.0, "elevation": 45.0,
                                 "energy": 0.0}),
        "specular_source": r.get("specular_source",
                                 {"size": 1.0, "distance": 500.0,
                                  "azimuth": 0.0, "elevation": 45.0,
                                  "energy": 0.0}),
        "camera": r["camera"],
        "region_colours": SW.REGION_COLOURS,
        "region_grids": True,
        "lighting_contract_identity": hashlib.sha256(
            json.dumps(r, sort_keys=True).encode()).hexdigest()[:16],
        "geometry_identity": SW.build_swatch()["swatch_geometry_identity"],
        "camera_identity": hashlib.sha256(
            json.dumps(r["camera"], sort_keys=True).encode()
        ).hexdigest()[:16],
    }


def plate_region_indices(rig, out_dir) -> dict:
    """A mask for the PLATE fixture — its silhouette differs from the
    sheets, so the sheet mask would misattribute pixels."""
    os.makedirs(out_dir, exist_ok=True)
    meas = os.path.join(out_dir, "_region_mask_plates.json")
    if not os.path.exists(meas):
        with tempfile.TemporaryDirectory() as td:
            cfg = _rig_cfg(rig, td, fixture="plates")
            cfg.update({"mask_mode": True,
                        "png": os.path.join(out_dir,
                                            "region_mask_plates.png"),
                        "exr": os.path.join(td, "mask.exr"),
                        "measurements": meas, "samples": 8})
            _run(cfg, td)
    data = json.load(open(meas))
    idx = {r: [] for r in ("PLANAR", "GRAZING")}
    for i, (r, g, b) in enumerate(data["rgb"]):
        for name in idx:
            colour = SW.REGION_COLOURS[name]
            if (abs(r - colour[0]) < 0.25 and abs(g - colour[1]) < 0.25
                    and abs(b - colour[2]) < 0.25 and (r + g + b) > 0.3):
                idx[name].append(i)
                break
    thin = {k: v for k, v in idx.items() if len(v) >= 200}
    if len(thin) < 2:
        raise ProtocolError(
            f"the plate mask resolved only {sorted(thin)}")
    return thin


def measure_under(rig, material_spec, out_dir, label, *, overrides=None,
                  samples=None, hide_swatch=False,
                  fixture="sheets") -> dict:
    """One measurement under one sub-rig."""
    os.makedirs(out_dir, exist_ok=True)
    png = os.path.join(out_dir, f"{label}.png")
    exr = os.path.join(out_dir, f"{label}.exr")
    meas = os.path.join(out_dir, f"{label}.json")
    idx = (DRIG.region_indices(out_dir) if fixture == "sheets"
           else plate_region_indices(rig, out_dir))
    with tempfile.TemporaryDirectory() as td:
        cfg = _rig_cfg(rig, td, overrides, fixture)
        cfg.update({
            "material": material_spec, "png": png, "exr": exr,
            "measurements": meas, "region_indices": idx,
            "hide_swatch": hide_swatch,
            "material_identity": hashlib.sha256(
                json.dumps(material_spec, sort_keys=True).encode()
            ).hexdigest()[:16],
            "render_identity": hashlib.sha256(
                (label + cfg["lighting_contract_identity"]).encode()
            ).hexdigest()[:16],
        })
        if samples:
            cfg["samples"] = samples
        _run(cfg, td)
    data = json.load(open(meas))
    data["png"], data["exr"], data["label"] = png, exr, label
    return data


# ==========================================================================
# grid mathematics — shared by the reflective and transmission axes
# ==========================================================================

def _flat(grid):
    return [v for row in grid for v in row if v > 0.0]


def grid_pattern_contrast(grid):
    """(p95 - p5) / median — exposure-invariant by construction, so an
    exposure-only change cannot masquerade as a material difference."""
    vals = sorted(_flat(grid))
    if len(vals) < 16:
        return 0.0
    n = len(vals)
    p5, p50, p95 = vals[int(n * 0.05)], vals[n // 2], vals[int(n * 0.95)]
    return (p95 - p5) / p50 if p50 > 1e-9 else 0.0


def _normalised(grid):
    """(normalised grid, occupancy mask).

    Empty cells are 0.0 in the RAW grid, so occupancy must be decided
    BEFORE normalisation: normalising first maps every minimum-value cell
    to exactly 0.0 and a raw>0 filter then silently drops them — which
    made a perfectly correlated bar pattern score 0.0, because only its
    identical bright cells survived. Caught by the negative-control test,
    not by inspection.
    """
    mask = [[v > 0.0 for v in row] for row in grid]
    vals = [v for row in grid for v in row if v > 0.0]
    if not vals:
        return grid, mask
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1e-9
    return ([[(v - lo) / rng if m else 0.0
              for v, m in zip(row, mrow)]
             for row, mrow in zip(grid, mask)], mask)


def grid_edge_sharpness(grid):
    """p95 adjacent-cell gradient of the contrast-normalised grid."""
    g, mask = _normalised(grid)
    n = len(g)
    grads = []
    for r in range(n):
        for c in range(n):
            if not mask[r][c]:
                continue
            if c + 1 < n and mask[r][c + 1]:
                grads.append(abs(g[r][c + 1] - g[r][c]))
            if r + 1 < n and mask[r + 1][c]:
                grads.append(abs(g[r + 1][c] - g[r][c]))
    if len(grads) < 16:
        return 0.0
    grads.sort()
    return grads[int(len(grads) * 0.95)]


def grid_coherence(grid):
    """Fraction of variance captured by an 8x8 low-frequency downsample.

    A coherent reflection is bands and shapes; speckle is high-frequency
    noise. This is scale-invariant, so exposure cancels."""
    g, mask = _normalised(grid)
    n = len(g)
    step = max(1, n // 8)
    low = [[0.0] * n for _ in range(n)]
    for r0 in range(0, n, step):
        for c0 in range(0, n, step):
            block = [g[r][c] for r in range(r0, min(r0 + step, n))
                     for c in range(c0, min(c0 + step, n))
                     if mask[r][c]]
            m = sum(block) / len(block) if block else 0.0
            for r in range(r0, min(r0 + step, n)):
                for c in range(c0, min(c0 + step, n)):
                    low[r][c] = m
    cells = [(g[r][c], low[r][c]) for r in range(n) for c in range(n)
             if mask[r][c]]
    if len(cells) < 16:
        return 0.0
    mean = sum(v for v, _ in cells) / len(cells)
    total = sum((v - mean) ** 2 for v, _ in cells)
    low_var = sum((lv - mean) ** 2 for _, lv in cells)
    return low_var / total if total > 1e-12 else 0.0


def grid_correlation(a, b):
    """Pearson correlation of two normalised grids."""
    (ga, ma), (gb, mb) = _normalised(a), _normalised(b)
    pairs = [(ga[r][c], gb[r][c]) for r in range(len(ga))
             for c in range(len(ga[0]))
             if ma[r][c] and mb[r][c]]
    if len(pairs) < 16:
        return 0.0
    n = len(pairs)
    ma = sum(x for x, _ in pairs) / n
    mb = sum(y for _, y in pairs) / n
    cov = sum((x - ma) * (y - mb) for x, y in pairs)
    va = sum((x - ma) ** 2 for x, _ in pairs)
    vb = sum((y - mb) ** 2 for _, y in pairs)
    denom = (va * vb) ** 0.5
    return cov / denom if denom > 1e-12 else 0.0


def _region_grid(measurement, region):
    grid = measurement["regions"].get(region, {}).get("grid")
    if not grid:
        raise ProtocolError(f"no grid for region {region!r} in "
                            f"{measurement.get('label')}")
    return grid


def _clipped_subject(measurement):
    return sum(r.get("clipped_sample_count", 0)
               for r in measurement["regions"].values())


# ==========================================================================
# axis extraction per sub-rig
# ==========================================================================

def reflective_axes(measurement, mirror_reference) -> dict:
    planar = _region_grid(measurement, "PLANAR")
    grazing = _region_grid(measurement, "GRAZING")
    mirror_planar = _region_grid(mirror_reference, "PLANAR")
    q = measurement["regions"].get("QUARTER_CYLINDER", {})
    return {
        "REFLECTED_PATTERN_CONTRAST": grid_pattern_contrast(planar),
        "REFLECTION_EDGE_SHARPNESS": grid_edge_sharpness(planar),
        "REFLECTION_COHERENCE": grid_coherence(planar),
        "SPECULAR_TO_DIFFUSE_RESPONSE":
            float(q.get("specular_to_diffuse_ratio", 0.0)),
        "ENVIRONMENT_CORRELATION": grid_correlation(planar, mirror_planar),
        "GRAZING_REFLECTION_RESPONSE": grid_pattern_contrast(grazing),
    }


def transmission_axes(measurement, reference) -> dict:
    planar = _region_grid(measurement, "PLANAR")
    grazing = _region_grid(measurement, "GRAZING")
    ref_planar = _region_grid(reference, "PLANAR")
    ref_grazing = _region_grid(reference, "GRAZING")
    detail = grid_edge_sharpness(planar)
    coherence = grid_coherence(planar)
    return {
        "TRANSMITTED_CONTRAST": grid_pattern_contrast(planar),
        "BACKGROUND_VISIBILITY": grid_correlation(planar, ref_planar),
        "TRANSMITTED_DETAIL": detail,
        "SCATTERING_OR_BLUR": coherence,
        "EDGE_TRANSMISSION": grid_correlation(grazing, ref_grazing),
    }


def apply_pass_law(axes_a, axes_b, axis_spec, required, label_a,
                   label_b) -> dict:
    """The predeclared pass law: independent axes only count once, and
    the correlation-type axes use an absolute bar."""
    rows, clearing, supporting = {}, [], []
    for axis, spec in axis_spec.items():
        va, vb = float(axes_a[axis]), float(axes_b[axis])
        if spec["kind"] == "absolute":
            effect = abs(va - vb)
        else:
            mean = (abs(va) + abs(vb)) / 2.0
            effect = abs(va - vb) / mean if mean > 1e-9 else 0.0
        clears = effect >= spec["bar"]
        rows[axis] = {"a": round(va, 6), "b": round(vb, 6),
                      "effect": round(effect, 6), "bar": spec["bar"],
                      "kind": spec["kind"], "clears": bool(clears),
                      "independent": spec["independent"]}
        if clears and spec["independent"]:
            clearing.append(axis)
        elif clears:
            supporting.append(axis)
    ok = len(clearing) >= required
    return {"a": label_a, "b": label_b, "axes": rows,
            "independent_axes_clearing": clearing,
            "supporting_axes_clearing": supporting,
            "axes_required": required,
            "verdict": "PASS" if ok else "FAIL"}


# ==========================================================================
# §4/§5/§6 — the reflective validation
# ==========================================================================

def _spec(material, finish, rgb=(0.62, 0.62, 0.63)):
    from apps.pipeline.services import palette_material_engine as ME
    return ME.MaterialAssignment("*", material, finish,
                                 ME.Colour(rgb=rgb)).resolved()


REFLECTIVE_CONTROLS = (
    ("METAL_vs_identical_METAL", ("METAL", "METALLIC"),
     ("METAL", "METALLIC"), {}),
    ("GLOSSY_vs_identical_GLOSSY", ("ABS", "GLOSSY"),
     ("ABS", "GLOSSY"), {}),
    ("METAL_vs_METAL_renamed", ("METAL", "METALLIC"),
     ("METAL", "METALLIC"), {"rename": True}),
    ("METAL_vs_METAL_exposure_only", ("METAL", "METALLIC"),
     ("METAL", "METALLIC"), {"exposure_scale": 1.5}),
    ("METAL_vs_METAL_environment_intensity", ("METAL", "METALLIC"),
     ("METAL", "METALLIC"),
     {"white_panel": {"emission": 2.2 * 1.2}}),
)

REFLECTIVE_PERTURBATIONS = (
    ("panel_intensity_plus_5pct", {"white_panel": {"emission": 2.2 * 1.05},
                                   "bright_strip": {"emission": 9.0 * 1.05}}),
    ("panel_intensity_minus_5pct", {"white_panel": {"emission": 2.2 * 0.95},
                                    "bright_strip": {"emission": 9.0 * 0.95}}),
    ("strip_angle_plus_2deg", {"bright_strip": {"elevation": 57.0}}),
    ("strip_angle_minus_2deg", {"bright_strip": {"elevation": 53.0}}),
    ("camera_plus_1deg", {"camera": {"elevation": 29.0}}),
    ("camera_minus_1deg", {"camera": {"elevation": 27.0}}),
    ("panel_distance_plus_5pct", {"white_panel": {"distance": 441.0}}),
    ("panel_distance_minus_5pct", {"white_panel": {"distance": 399.0}}),
)


def _exposure_override(scale):
    """Scale every panel and the fill — an exposure change, nothing else."""
    o = {"fill_source": {"energy": REFLECTIVE_MATERIAL_RIG["fill_source"]
                         ["energy"] * scale}}
    for pn in REFLECTIVE_MATERIAL_RIG["environment_panels"]:
        o[pn["name"]] = {"emission": pn["emission"] * scale}
    return o


def validate_reflective(out_dir, *, samples=48) -> dict:
    """§4/§5/§6 — the whole reflective sub-rig validation."""
    os.makedirs(out_dir, exist_ok=True)
    mirror = measure_under(REFLECTIVE_MATERIAL_RIG, MIRROR_REFERENCE_SPEC,
                           out_dir, "mirror_reference", samples=samples)
    v = REFLECTIVE_MATERIAL_RIG["validity"]
    commissioning = {
        "mirror_pattern_contrast": round(
            grid_pattern_contrast(_region_grid(mirror, "PLANAR")), 6),
        "gate": v["mirror_reference_min_pattern_contrast"],
        "clipped_subject_samples": _clipped_subject(mirror),
        "verdict": "PASS"
        if (grid_pattern_contrast(_region_grid(mirror, "PLANAR"))
            >= v["mirror_reference_min_pattern_contrast"]
            and _clipped_subject(mirror)
            <= v["maximum_clipped_subject_samples"]) else "FAIL",
    }

    glossy = measure_under(REFLECTIVE_MATERIAL_RIG,
                           _spec("ABS", "GLOSSY"), out_dir,
                           "reflective_ABS_GLOSSY", samples=samples)
    metal = measure_under(REFLECTIVE_MATERIAL_RIG,
                          _spec("METAL", "METALLIC"), out_dir,
                          "reflective_METAL_METALLIC", samples=samples)
    windows = {}
    for label, m in (("ABS_GLOSSY", glossy), ("METAL_METALLIC", metal)):
        peak = max(r.get("scene_linear_peak", 0.0)
                   for r in m["regions"].values())
        windows[label] = {
            "subject_peak": round(peak, 6),
            "min_required": v["min_subject_peak_scene_linear"],
            "clipped": _clipped_subject(m),
            "verdict": "PASS"
            if (peak >= v["min_subject_peak_scene_linear"]
                and _clipped_subject(m)
                <= v["maximum_clipped_subject_samples"]) else "FAIL"}

    pair = apply_pass_law(
        reflective_axes(glossy, mirror), reflective_axes(metal, mirror),
        REFLECTIVE_AXES, REFLECTIVE_REQUIRED_AXES,
        "ABS GLOSSY", "METAL METALLIC")

    controls = []
    for name, (ma, fa), (mb, fb), flags in REFLECTIVE_CONTROLS:
        ov = None
        if "exposure_scale" in flags:
            ov = _exposure_override(flags["exposure_scale"])
        elif not flags.get("rename"):
            ov = {k: v2 for k, v2 in flags.items()} or None
        a = measure_under(REFLECTIVE_MATERIAL_RIG, _spec(ma, fa), out_dir,
                          f"rctl_{name}_a", samples=samples)
        b = measure_under(REFLECTIVE_MATERIAL_RIG, _spec(mb, fb), out_dir,
                          f"rctl_{name}_b", overrides=ov, samples=samples)
        rep = apply_pass_law(reflective_axes(a, mirror),
                             reflective_axes(b, mirror),
                             REFLECTIVE_AXES, REFLECTIVE_REQUIRED_AXES,
                             f"{ma} {fa}", f"{mb} {fb}")
        rep["control"] = name
        rep["expected"] = "FAIL"
        rep["behaved"] = rep["verdict"] == "FAIL"
        controls.append(rep)

    robustness = []
    for name, override in REFLECTIVE_PERTURBATIONS:
        a = measure_under(REFLECTIVE_MATERIAL_RIG, _spec("ABS", "GLOSSY"),
                          out_dir, f"rrb_{name}_glossy",
                          overrides=json.loads(json.dumps(override)),
                          samples=samples)
        b = measure_under(REFLECTIVE_MATERIAL_RIG,
                          _spec("METAL", "METALLIC"), out_dir,
                          f"rrb_{name}_metal",
                          overrides=json.loads(json.dumps(override)),
                          samples=samples)
        rep = apply_pass_law(reflective_axes(a, mirror),
                             reflective_axes(b, mirror),
                             REFLECTIVE_AXES, REFLECTIVE_REQUIRED_AXES,
                             "ABS GLOSSY", "METAL METALLIC")
        rep["perturbation"] = name
        robustness.append(rep)

    misbehaved = [c["control"] for c in controls if not c["behaved"]]
    unstable = [r["perturbation"] for r in robustness
                if r["verdict"] != "PASS"]
    ok = (commissioning["verdict"] == "PASS"
          and all(w["verdict"] == "PASS" for w in windows.values())
          and pair["verdict"] == "PASS" and not misbehaved
          and not unstable)
    return {
        "record_type": "reflective_metric_report/1.0",
        "rig_identity": reflective_rig_identity(),
        "commissioning": commissioning,
        "operating_windows": windows,
        "glossy_vs_metallic": pair,
        "negative_controls": controls,
        "controls_misbehaved": misbehaved,
        "robustness": robustness,
        "robustness_unstable": unstable,
        "REFLECTIVE_MATERIAL_RIG": "PASS" if ok else
        ("FAIL_OVERFITTED" if unstable and pair["verdict"] == "PASS"
         else "FAIL"),
    }


# ==========================================================================
# §7 — the transmission validation
# ==========================================================================

def validate_transmission(out_dir, *, samples=48) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    reference = measure_under(TRANSMISSION_RIG, _spec("ABS", "MATTE"),
                              out_dir, "transmission_reference",
                              samples=samples, hide_swatch=True,
                              fixture="plates")
    v = TRANSMISSION_RIG["validity"]
    ref_contrast = grid_pattern_contrast(_region_grid(reference, "PLANAR"))
    commissioning = {
        "reference_pattern_contrast": round(ref_contrast, 6),
        "gate": v["reference_min_pattern_contrast"],
        "verdict": "PASS"
        if ref_contrast >= v["reference_min_pattern_contrast"] else "FAIL",
    }

    measured = {}
    for label, material, finish in (
            ("OPAQUE", "ABS", "MATTE"),
            ("TRANSPARENT", "ACRYLIC", "TRANSPARENT"),
            ("TRANSLUCENT", "ACRYLIC", "TRANSLUCENT")):
        measured[label] = measure_under(
            TRANSMISSION_RIG, _spec(material, finish), out_dir,
            f"transmission_{label}", samples=samples, fixture="plates")

    pairs = []
    for a, b in (("OPAQUE", "TRANSPARENT"), ("OPAQUE", "TRANSLUCENT"),
                 ("TRANSPARENT", "TRANSLUCENT")):
        rep = apply_pass_law(
            transmission_axes(measured[a], reference),
            transmission_axes(measured[b], reference),
            TRANSMISSION_AXES, TRANSMISSION_REQUIRED_AXES, a, b)
        rep["pair"] = f"{a}_vs_{b}"
        pairs.append(rep)

    # exposure control: opaque against itself, brighter — must FAIL
    brighter = measure_under(
        TRANSMISSION_RIG, _spec("ABS", "MATTE"), out_dir,
        "transmission_exposure_control",
        overrides={"fill_source": {"energy":
                                   TRANSMISSION_RIG["fill_source"]
                                   ["energy"] * 1.5}},
        samples=samples, fixture="plates")
    control = apply_pass_law(
        transmission_axes(measured["OPAQUE"], reference),
        transmission_axes(brighter, reference),
        TRANSMISSION_AXES, TRANSMISSION_REQUIRED_AXES,
        "OPAQUE", "OPAQUE brighter")
    control["control"] = "OPAQUE_vs_OPAQUE_exposure_only"
    control["expected"] = "FAIL"
    control["behaved"] = control["verdict"] == "FAIL"

    failed = [p["pair"] for p in pairs if p["verdict"] != "PASS"]
    ok = (commissioning["verdict"] == "PASS" and not failed
          and control["behaved"])
    return {
        "record_type": "transmission_metric_report/1.0",
        "rig_identity": transmission_rig_identity(),
        "commissioning": commissioning,
        "pairs": pairs,
        "failed_pairs": failed,
        "exposure_control": control,
        "TRANSMISSION_RIG": "PASS" if ok else "FAIL",
    }
