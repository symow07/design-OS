"""M6 §13/§14/§15 — the GLITTER_PARTICLE_RIG: discrete-event census.

The canonical SHIMMER-vs-GLITTER question is structural: a CONTINUOUS
fine particulate response versus DISCRETE RESOLVABLE particles. The
census below answers it by counting connected bright components in the
PLANAR region of the characterization swatch — actual resolved events
in pixels, never particle-size metadata (§15 forbids passing on
metadata alone).

Everything that could be tuned is declared here, before measurement:

- a bright pixel exceeds EVENT_LUMINANCE_FACTOR x the region median;
- an event is a connected component of bright pixels with area between
  EVENT_MIN_AREA_PX (below it, sub-pixel sparkle and noise — the
  continuous regime) and EVENT_MAX_AREA_PX (above it, a highlight
  band, not a particle);
- GLITTER must produce >= GLITTER_MIN_EVENTS;
- the zero-particle control (POWDER_MATTE) must produce
  <= CONTROL_MAX_EVENTS, and SHIMMER must sit at control level too —
  that is what CONTINUOUS means in pixels;
- the rig is only valid when the declared particle size resolves to
  >= MIN_RESOLVABLE_PARTICLE_PX at the rig's px/mm.

Axes (pass law = the protocol's 2 independent axes):
- DISCRETE_EVENT_COUNT (independent) — the census itself;
- MEDIAN_EVENT_AREA_PX (independent) — the size census, defined only
  when both sides have events, else it reports the count side alone;
- EVENT_LUMINANCE_DOMINANCE (supporting — derived from the same bright
  mask, never counted as a second independent axis).
"""
from __future__ import annotations

import json
import os

import numpy as np
from PIL import Image

from apps.pipeline.services import palette_characterization_rig as CR
from apps.pipeline.services import palette_powder_engine as PE
from apps.pipeline.services import palette_powder_protocol as PP
from apps.pipeline.services import palette_firing_trace as FT

SCHEMA = "glitter_particle_rig/1.0"

#: the swatch renders 84 mm across 1200 px
PX_PER_MM = 1200.0 / 84.0

EVENT_LUMINANCE_FACTOR = 1.8
EVENT_MIN_AREA_PX = 4
EVENT_MAX_AREA_PX = 2000
#: M6-ENSEMBLE-CONVENTION-DECLARATION (2026-08-15): the glitter EVENT
#: ensemble rule — the census trio re-measured at six member indices.
#: Member 0 is the committed trio (GLITTER 61 / MATTE_CONTROL 62 /
#: SHIMMER 63); member k (1-5) shifts each trio seed by the same
#: decimal-block rule the other conventions use (610+k-1 / 620+k-1 /
#: 630+k-1). Event counts and both controls run per member; the
#: event-count spread across members IS the census's replicate spread —
#: the quantity every GLITTER row recorded as NEVER measured.
GLITTER_EVENT_ENSEMBLE = tuple(
    (61, 62, 63) if k == 0 else (609 + k, 619 + k, 629 + k)
    for k in range(6))

GLITTER_MIN_EVENTS = 25
CONTROL_MAX_EVENTS = 5
MIN_RESOLVABLE_PARTICLE_PX = PP.SUB_RIGS[
    "GLITTER_PARTICLE_RIG"]["validity"]["min_resolvable_particle_px"]

GLITTER_AXES = {
    "DISCRETE_EVENT_COUNT": {"independent": True},
    "MEDIAN_EVENT_AREA_PX": {"independent": True},
    "EVENT_LUMINANCE_DOMINANCE": {"independent": False,
                                  "why": "derived from the same bright "
                                         "mask as the count"},
}


class GlitterRigError(RuntimeError):
    """Raised when the rig cannot honestly measure."""


def mirror_source_overrides() -> dict:
    """The rig correction, computed — never hand-positioned.

    The first commissioning run detected ZERO events on the positive
    fixture because the dielectric rig's compact source (az 26, el 34)
    sits on the camera's side (az 30, el 28): no specular condition
    exists on the horizontal PLANAR region, so no facet can glint. For
    a horizontal surface the mirror of the camera direction about +Z
    keeps the elevation and rotates the azimuth by 180 degrees — the
    same mirror law M5 proved on the closed lid. Size, distance and
    energy stay verbatim from the proven compact apparatus.
    """
    cam = CR.RIG["camera"]
    src = CR.RIG["specular_source"]
    return {"specular_source": {
        "azimuth": (cam["azimuth"] + 180.0) % 360.0,
        "elevation": cam["elevation"],
        "size": src["size"], "distance": src["distance"],
        "energy": src["energy"],
    }}


def glitter_rig_overrides() -> dict:
    """The mirror placement with the DERIVED source size — only the
    solid angle differs from the placement contract."""
    over = mirror_source_overrides()
    over["specular_source"]["size"] = \
        derive_source_size()["calculated_source_size_mm"]
    return over


def _spherical_vector(az_deg, el_deg):
    import math
    az, el = math.radians(az_deg), math.radians(el_deg)
    return (math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az),
            math.sin(el))


def placement_record() -> dict:
    """§1 — every quantity of the mirror placement, recorded."""
    cam = CR.RIG["camera"]
    over = mirror_source_overrides()["specular_source"]
    cam_vec = _spherical_vector(cam["azimuth"], cam["elevation"])
    refl_vec = (-cam_vec[0], -cam_vec[1], cam_vec[2])
    centre = CR._swatch_centre()
    src_pos = [round(centre[i] + over["distance"] * refl_vec[i], 3)
               for i in range(3)]
    return {
        "surface_point": [round(v, 3) for v in centre],
        "surface_normal": [0.0, 0.0, 1.0],
        "camera_vector_surface_to_camera":
            [round(v, 6) for v in cam_vec],
        "reflection_vector": [round(v, 6) for v in refl_vec],
        "source_position": src_pos,
        "source_orientation_deg": [90.0 - over["elevation"], 0.0,
                                   over["azimuth"]],
        "source_dimensions_mm": [over["size"], over["size"]],
        "source_intensity": over["energy"],
        "source_spherical": {"azimuth": over["azimuth"],
                             "elevation": over["elevation"],
                             "distance": over["distance"]},
        "camera_identity": __import__("hashlib").sha256(
            json.dumps(cam, sort_keys=True).encode()).hexdigest()[:16],
        "measurement_region": "PLANAR",
        "mirror_law": "horizontal surface: elevation preserved, azimuth "
                      "+180 — the M5 closed-lid law in the "
                      "characterization script's spherical convention",
        "sanity": {"elevations_equal":
                   over["elevation"] == cam["elevation"],
                   "azimuth_delta_deg": round(
                       (over["azimuth"] - cam["azimuth"]) % 360.0, 3),
                   "reflection_z_positive": refl_vec[2] > 0},
    }


def _connected_components(bright):
    """4-connected labelling with a flood fill — no scipy. Returns
    {label: (size, bbox)} with bbox = (y0, x0, y1, x1)."""
    h, w = bright.shape
    labels = np.zeros((h, w), dtype=int)
    comps = {}
    next_label = 0
    for y in range(h):
        row = bright[y]
        if not row.any():
            continue
        for x in np.nonzero(row)[0]:
            if labels[y, x]:
                continue
            next_label += 1
            stack = [(y, x)]
            labels[y, x] = next_label
            size = 0
            y0 = y1 = y
            x0 = x1 = x
            while stack:
                cy, cx = stack.pop()
                size += 1
                y0, y1 = min(y0, cy), max(y1, cy)
                x0, x1 = min(x0, cx), max(x1, cx)
                for ny, nx in ((cy - 1, cx), (cy + 1, cx),
                               (cy, cx - 1), (cy, cx + 1)):
                    if (0 <= ny < h and 0 <= nx < w and bright[ny, nx]
                            and not labels[ny, nx]):
                        labels[ny, nx] = next_label
                        stack.append((ny, nx))
            comps[next_label] = (size, (int(y0), int(x0),
                                        int(y1), int(x1)))
    return comps


def particle_census(source, region_idx, *, event_map_path=None,
                    annotate_source=None) -> dict:
    """Discrete bright events in the PLANAR region, in pixels.

    ``source`` is an EXR path — measured scene-linear through the R1
    provenance-asserting loader (Phase 4: the original 87-event PASS
    was read from a display-encoded frame, the exact condition its own
    justifying comment named as invalidating). A pre-loaded float
    frame is also accepted. The census law (1.8x median, 4-2000px,
    >=25 / <=5) is unchanged; the threshold is a RATIO of the region
    median, defined on whatever frame is measured. With
    ``event_map_path`` an annotated copy of ``annotate_source`` is
    written with every detected event boxed — §2's visual
    correspondence evidence.
    """
    if isinstance(source, str):
        # lazy import: TX imports this module for rig geometry
        from apps.pipeline.services import (
            palette_powder_texture_axes as TX)
        arr = TX.load_scene_linear(source)
    else:
        arr = source
    mask = np.zeros(arr.size, dtype=bool)
    mask[np.asarray(region_idx["PLANAR"], dtype=int)] = True
    region = mask.reshape(arr.shape)
    median = float(np.median(arr[region]))
    if median <= 0:
        raise GlitterRigError("PLANAR region is black — degenerate "
                              "output, the rig cannot measure")
    bright = region & (arr > median * EVENT_LUMINANCE_FACTOR)
    comps = _connected_components(bright)
    events = {k: v for k, v in comps.items()
              if EVENT_MIN_AREA_PX <= v[0] <= EVENT_MAX_AREA_PX}
    if event_map_path:
        from PIL import ImageDraw
        if annotate_source is None:
            raise GlitterRigError("an event map needs an 8-bit review "
                                  "frame to annotate")
        img = Image.open(annotate_source).convert("RGB")
        draw = ImageDraw.Draw(img)
        for size, (y0, x0, y1, x1) in events.values():
            draw.rectangle([x0 - 3, y0 - 3, x1 + 3, y1 + 3],
                           outline=(220, 40, 30), width=2)
        draw.text((14, 10), f"{len(events)} events "
                            f">= {EVENT_MIN_AREA_PX}px at "
                            f">= {EVENT_LUMINANCE_FACTOR}x median",
                  fill=(220, 40, 30))
        img.save(event_map_path)
    areas = [v[0] for v in events.values()]
    return {
        "median_luminance": round(median, 2),
        "threshold": round(median * EVENT_LUMINANCE_FACTOR, 2),
        "raw_components": len(comps),
        "event_count": len(events),
        "median_event_area_px": (float(np.median(areas))
                                 if areas else FT.traced_zero("palette_powder_rigs.py:particle_census", "guard")),
        "bright_pixel_fraction": round(float(bright.mean()), 6),
        "event_map": event_map_path,
    }


def commission_and_discriminate(out_dir, *, samples=64) -> dict:
    """§14 commissioning + the canonical §15 distinction in one record.

    Positive fixture GLITTER, zero-particle control POWDER_MATTE, and
    the continuous contrast SHIMMER — all on the same swatch, same rig,
    same census.
    """
    os.makedirs(out_dir, exist_ok=True)
    shade = PE.PowderShade("prov_census_neutral", (0.62, 0.55, 0.48),
                           PE.PROVISIONAL_VISUALIZATION_SHADE)

    glitter_spec = PE.PowderMaterialSpec(PP.GLITTER, shade, seed=61)
    particle_px = (glitter_spec.params["particles"]["particle_size_mm"]
                   * PX_PER_MM)
    if particle_px < MIN_RESOLVABLE_PARTICLE_PX:
        raise GlitterRigError(
            f"declared particle {particle_px:.1f}px does not resolve at "
            f"this rig's {PX_PER_MM:.1f}px/mm — fix the rig, not the "
            f"powder")

    idx = CR.region_indices(out_dir)
    derivation = derive_source_size(out_dir)
    overrides = glitter_rig_overrides()

    # rig energy calibration, analytic and recorded. The frame is lit
    # by THREE sources, so scaling only the compact source scales only
    # its own contribution — a one-render calibration left base +
    # scaled-specular above 1.0 and the clip guard caught it. Two
    # renders of the brightest fixture (SHIMMER) solve it exactly on
    # the conservative side: one with the compact source OFF measures
    # the base peak, one at reference energy measures the total, and
    # E = E0 * (target - base_peak) / reference_peak. One energy for
    # all three fixtures; the census law is ratio-based and untouched.
    # the calibration fixture is MEASURED, not assumed: under a narrow
    # source shimmer's dense 0.45-response field is brightest, but a
    # wide source lets glitter's mirror-aligned unit-reflectance facets
    # out-peak it — assuming either one is how a calibration silently
    # under-corrects. Both specular-capable fixtures render once at
    # reference and the brighter one calibrates the rig.
    candidates = {}
    for fam, seed in ((PP.SHIMMER, 63), (PP.GLITTER, 61)):
        d = CR.characterize_powder(
            PE.PowderMaterialSpec(fam, shade, seed=seed), out_dir,
            label=f"energy_ref_{fam}", overrides=overrides,
            samples=samples)
        candidates[fam] = float(
            d["regions"]["PLANAR"]["scene_linear_peak"])
    bright_fam = max(candidates, key=candidates.get)
    bright_seed = 63 if bright_fam == PP.SHIMMER else 61
    bright_spec = PE.PowderMaterialSpec(bright_fam, shade,
                                        seed=bright_seed)
    peak = candidates[bright_fam]
    base_over = json.loads(json.dumps(overrides))
    base_over["specular_source"]["energy"] = 0.0
    base = CR.characterize_powder(bright_spec, out_dir,
                                  label="energy_base",
                                  overrides=base_over, samples=samples)
    base_peak = float(base["regions"]["PLANAR"]["scene_linear_peak"])
    shimmer_spec = bright_spec
    ref_energy = overrides["specular_source"]["energy"]
    if base_peak >= 0.92:
        raise GlitterRigError(
            f"base lighting alone peaks at {base_peak} — no compact "
            "energy can bring the rig into the window; fix the base rig")
    # the linear solve is conservative but the brightest PIXEL can
    # switch identity as the source dims (a near-mirror facet firefly),
    # so the SAME law iterates to the SAME predeclared target — a
    # fixed-point of the declared calibration, never a new threshold.
    energy = ref_energy
    iterations = []
    for _ in range(4):
        energy = energy * (0.92 - base_peak) / max(peak, 0.92)
        it = CR.characterize_powder(
            shimmer_spec, out_dir, label="energy_iteration",
            overrides={**json.loads(json.dumps(overrides)),
                       "specular_source":
                       {**overrides["specular_source"],
                        "energy": energy}},
            samples=samples)
        pl = it["regions"]["PLANAR"]
        peak = float(pl["scene_linear_peak"])
        iterations.append({"energy": energy, "peak": peak,
                           "clipped": pl["clipped_sample_count"]})
        if pl["clipped_sample_count"] == 0 and peak <= 0.92:
            break
    else:
        raise GlitterRigError(
            f"calibration did not converge in 4 iterations: {iterations}")
    overrides = json.loads(json.dumps(overrides))
    overrides["specular_source"]["energy"] = energy
    calibration = {"reference_energy": ref_energy,
                   "calibration_fixture": f"{bright_fam} (measured "
                                          f"brightest of {candidates})",
                   "base_peak_specular_off": base_peak,
                   "target_linear": 0.92,
                   "iterations": iterations,
                   "calibrated_energy": energy,
                   "law": "E_{n+1} = E_n * (target - base_peak) / peak_n "
                          "iterated to the fixed predeclared target"}

    census = {}
    for label, family, seed in (("GLITTER", PP.GLITTER, 61),
                                ("MATTE_CONTROL", PP.POWDER_MATTE, 62),
                                ("SHIMMER", PP.SHIMMER, 63)):
        spec = PE.PowderMaterialSpec(family, shade, seed=seed)
        d = CR.characterize_powder(spec, out_dir,
                                   label=f"census_{label}",
                                   overrides=overrides,
                                   samples=samples)
        census[label] = particle_census(
            d["exr"], idx,
            event_map_path=os.path.join(out_dir,
                                        f"event_map_{label}.png"),
            annotate_source=d["png"])
        census[label]["png"] = d["png"]
        census[label]["material_identity"] = spec.material_identity()
        pl = d["regions"]["PLANAR"]
        census[label]["scene_linear_peak"] = pl["scene_linear_peak"]
        census[label]["clipped_sample_count"] = pl["clipped_sample_count"]
        if pl["clipped_sample_count"]:
            raise GlitterRigError(
                f"{label} clipped even after calibration — the "
                "calibration procedure itself failed")

    commissioning = {
        "particle_resolves": True,
        "particle_px": round(particle_px, 1),
        "positive_fixture_events": census["GLITTER"]["event_count"],
        "zero_particle_control_events":
            census["MATTE_CONTROL"]["event_count"],
        "positive_has_signal":
            census["GLITTER"]["event_count"] >= GLITTER_MIN_EVENTS,
        "control_is_quiet":
            census["MATTE_CONTROL"]["event_count"] <= CONTROL_MAX_EVENTS,
    }
    rig_ok = (commissioning["positive_has_signal"]
              and commissioning["control_is_quiet"])

    shimmer_continuous = (census["SHIMMER"]["event_count"]
                          <= CONTROL_MAX_EVENTS)
    glitter_discrete = (census["GLITTER"]["event_count"]
                        >= GLITTER_MIN_EVENTS)
    axes_clearing = []
    if glitter_discrete and shimmer_continuous:
        axes_clearing.append("DISCRETE_EVENT_COUNT")
        if census["GLITTER"]["median_event_area_px"] >= \
                MIN_RESOLVABLE_PARTICLE_PX ** 2 * 0.5:
            axes_clearing.append("MEDIAN_EVENT_AREA_PX")
    verdict = ("PASS" if rig_ok and len(axes_clearing)
               >= PP.PASS_LAW["required_independent_axes"] else "FAIL")
    return {
        "record_type": SCHEMA,
        "protocol_identity": PP.protocol_identity(),
        "source_placement": placement_record(),
        "source_solid_angle": derivation,
        "predicted_vs_observed_events": {
            "predicted": derivation["predicted_events"],
            "observed": census["GLITTER"]["event_count"],
        },
        "energy_calibration": calibration,
        "axes": GLITTER_AXES,
        "predeclared": {
            "EVENT_LUMINANCE_FACTOR": EVENT_LUMINANCE_FACTOR,
            "EVENT_MIN_AREA_PX": EVENT_MIN_AREA_PX,
            "EVENT_MAX_AREA_PX": EVENT_MAX_AREA_PX,
            "GLITTER_MIN_EVENTS": GLITTER_MIN_EVENTS,
            "CONTROL_MAX_EVENTS": CONTROL_MAX_EVENTS,
        },
        "commissioning": commissioning,
        "GLITTER_PARTICLE_RIG": "PASS" if rig_ok else "FAIL",
        "census": census,
        "SHIMMER_is_continuous": shimmer_continuous,
        "GLITTER_is_discrete": glitter_discrete,
        "axes_clearing": axes_clearing,
        "SHIMMER_VS_GLITTER": verdict,
        "measured_in": "resolved pixel events, never particle metadata",
    }


def write_record(out_dir, record):
    path = os.path.join(out_dir, "glitter_particle_rig_report.json")
    with open(path, "w") as fh:
        json.dump(record, fh, indent=2)
    return path


# --------------------------------------------------------------------------
# §1 — the source solid-angle derivation, from the shader's own math
# --------------------------------------------------------------------------

def derive_source_size(out_dir=None) -> dict:
    """Source size derived from the declared facet-jitter geometry.

    The shader adds (voronoi_colour - 0.5) * (jitter_deg / 90) to the
    normal, so each tilt axis is uniform on ±jitter/180 (in small-angle
    radians-equivalent). A facet glints when the reflected camera ray —
    deviated by TWICE the tilt — lands on the source, widened by the
    facet lobe. The aligned fraction is the probability that a uniform
    point in the tilt square falls inside that disc, and the source is
    sized so the predicted event count clears the unchanged 25-event
    bar with margin at the low end of the census uncertainty.
    """
    import math
    p = PE.FAMILY_PARAMS[PP.GLITTER]["particles"]
    jitter_axis = (p["orientation_jitter_deg"] / 90.0) / 2.0
    distance = CR.RIG["specular_source"]["distance"]
    lobe = 0.05
    planar_px = 99133
    planar_mm2 = planar_px / PX_PER_MM ** 2
    cells = planar_mm2 / (p["particle_size_mm"] ** 2)
    particles = cells * p["coverage"]

    def aligned_fraction(size_mm):
        theta_s = math.atan(size_mm / 2.0 / distance)
        rho = (theta_s + lobe) / 2.0
        rho = min(rho, jitter_axis * math.sqrt(2.0))
        square = (2.0 * jitter_axis) ** 2
        if rho <= jitter_axis:
            return math.pi * rho * rho / square
        return min(1.0, math.pi * rho * rho / square)

    target_events = GLITTER_MIN_EVENTS
    uncertainty = 0.30
    size = 40.0
    while size < 400.0:
        predicted = particles * aligned_fraction(size)
        if predicted * (1.0 - uncertainty) >= target_events * 1.1:
            break
        size += 10.0
    predicted = particles * aligned_fraction(size)
    record = {
        "record_type": "glitter_source_solid_angle_derivation/1.0",
        "jitter_distribution": {
            "shader_law": "(voronoi_colour - 0.5) * jitter_deg/90 added "
                          "to the normal; per-axis uniform",
            "per_axis_halfwidth_rad": round(jitter_axis, 4),
            "orientation_jitter_deg": p["orientation_jitter_deg"],
        },
        "source_distance_mm": distance,
        "facet_lobe_rad": lobe,
        "particle_census": {"planar_area_mm2": round(planar_mm2, 1),
                            "cells": round(cells, 0),
                            "coverage": p["coverage"],
                            "particles": round(particles, 0)},
        "event_threshold": target_events,
        "calculated_source_size_mm": size,
        "target_angular_halfwidth_deg": round(math.degrees(
            math.atan(size / 2.0 / distance)), 2),
        "predicted_aligned_fraction": round(aligned_fraction(size), 4),
        "predicted_events": round(predicted, 1),
        "predicted_event_range": [round(predicted * 0.7, 1),
                                  round(predicted * 1.3, 1)],
        "uncertainty": "±30% on the cell census (region shape, edge "
                       "cells, lobe-width approximation)",
        "SOURCE_SIZE_AUTHORITY": "CALCULATED_CHARACTERIZATION_DEFAULT",
        "not_authority_for": ["MATERIAL_PROPERTY",
                              "MANUFACTURER_STANDARD"],
    }
    if out_dir:
        with open(os.path.join(
                out_dir, "glitter_source_solid_angle_derivation.json"),
                "w") as fh:
            json.dump(record, fh, indent=2)
    return record


# --------------------------------------------------------------------------
# §4 — DIFFUSE_MICROTEXTURE_RIG pairs, on the committed measurements
# --------------------------------------------------------------------------

#: the diffuse-rig distinctions the protocol assigns to this rig
DIFFUSE_PAIRS = (
    (PP.POWDER_MATTE, PP.POWDER_SATIN),
    (PP.POWDER_MATTE, PP.SHIMMER),
    (PP.POWDER_SATIN, PP.SHIMMER),
    (PP.PRESSED_POWDER, PP.POWDER_MATTE),
    (PP.POWDER_SATIN, PP.CREAM),
)


def _load_swatch(swatch_dir, family):
    path = os.path.join(swatch_dir, f"swatch_powder_{family}.json")
    if not os.path.exists(path):
        raise GlitterRigError(f"no committed measurement for {family} — "
                              f"render the swatch first")
    return json.load(open(path))


def diffuse_powder_pairs(swatch_dir, out_dir, *, samples=64) -> dict:
    """§4 pairs + §12 controls on the SAME rig and law as M5's
    corrected dielectric machinery (independent region-width axes,
    exposure-normalised). Powder-specific measurements — nothing is
    reused from packaging conclusions except the proven rig and law.
    """
    os.makedirs(out_dir, exist_ok=True)
    axes = {fam: CR.axes_from(_load_swatch(swatch_dir, fam))
            for fam in {f for pair in DIFFUSE_PAIRS for f in pair}}

    pairs = {}
    for fam_a, fam_b in DIFFUSE_PAIRS:
        pairs[f"{fam_a}_vs_{fam_b}"] = CR.discriminate(
            axes[fam_a], axes[fam_b], fam_a, fam_b)

    # §12 negative controls — both must FAIL family differentiation.
    shade = PE.PowderShade("prov_char_neutral", (0.62, 0.55, 0.48),
                           PE.PROVISIONAL_VISUALIZATION_SHADE)
    seed_only = CR.characterize_powder(
        PE.PowderMaterialSpec(PP.POWDER_MATTE, shade, seed=99),
        out_dir, label="ctl_matte_seed99", samples=samples)
    exposure_only = CR.characterize_powder(
        PE.PowderMaterialSpec(PP.POWDER_MATTE, shade, seed=40),
        out_dir, label="ctl_matte_bright",
        overrides={"diffuse_source": {"energy":
                   CR.RIG["diffuse_source"]["energy"] * 1.35}},
        samples=samples)
    controls = {
        "MATTE_vs_MATTE_seed_only": CR.discriminate(
            axes[PP.POWDER_MATTE], CR.axes_from(seed_only),
            "matte_seed40", "matte_seed99"),
        "MATTE_vs_MATTE_exposure_only": CR.discriminate(
            axes[PP.POWDER_MATTE], CR.axes_from(exposure_only),
            "matte", "matte_brighter"),
    }
    misbehaved = [k for k, v in controls.items()
                  if v["verdict"] != "FAIL"]
    failed_pairs = [k for k, v in pairs.items() if v["verdict"] != "PASS"]
    return {
        "record_type": "diffuse_microtexture_rig_pairs/1.0",
        "protocol_identity": PP.protocol_identity(),
        "rig": "DIFFUSE_MICROTEXTURE_RIG — the validated M5 dielectric "
               "apparatus, reused because the physical question is the "
               "same; measurements and verdicts are powder-specific",
        "independence": "axes are the M5-corrected set: per-region lobe "
                        "WIDTHS plus one height and one ratio — never "
                        "five transforms of one scalar",
        "pairs": pairs,
        "negative_controls": controls,
        "controls_misbehaved": misbehaved,
        "failed_pairs": failed_pairs,
        "DIFFUSE_MICROTEXTURE_RIG":
            "PASS" if not misbehaved else "FAIL",
        "verdict": ("PASS" if not failed_pairs and not misbehaved
                    else "FAIL"),
    }
