"""M4B-B-EVIDENCE-LEGIBILITY §3 — the pinned evidence render contract.

The six failing elevations were grey-on-grey: a 0.42-albedo clay part on a
0.55 world backdrop, which under this rig lands at almost the same
luminance. A flat elevation has no shading gradient to rescue it, so the
silhouette simply disappeared.

The correction is separation between product and background, not a softer
bar. The backdrop drops well below the clay so every silhouette reads,
and the numbers live here — versioned, deterministic and shared by both
families — rather than being tuned per image by eye.

Nothing here touches geometry. This module cannot change a mesh identity;
it only decides how a mesh is photographed.
"""
from __future__ import annotations

import hashlib
import json

SCHEMA = "palette_evidence_render_contract/1.0"
VERSION = 1

#: Predeclared, before any image was measured against it.
MINIMUM_MODAL_BACKGROUND_SUBJECT_COVERAGE = 0.05

#: Also predeclared: the rendered subject and backdrop must differ by at
#: least this much in 0-255 luminance. A coverage bar alone can be met by
#: a large subject that still blends into its background.
MINIMUM_LUMINANCE_CONTRAST = 40.0

#: The contrast test asks whether the subject blends into its backdrop.
#: That question only has an answer while there IS a backdrop: once the
#: subject occupies most of the frame it cannot be said to disappear into
#: the remainder. Above this share, coverage alone establishes legibility.
#: Neither bar moves — this states where the contrast bar applies.
CONTRAST_APPLIES_BELOW_COVERAGE = 0.50

CONTRACT = {
    "schema": SCHEMA,
    "version": VERSION,
    "purpose": "TECHNICAL_FORM_LEGIBILITY_NOT_CLIENT_PRESENTATION_BEAUTY",

    # --- surfaces ------------------------------------------------------
    "clay_albedo": [0.42, 0.42, 0.425],
    "clay_roughness": 0.62,
    "beauty_colour": False,
    "cosmetic_artwork": False,
    "material_styling": False,

    # --- background ----------------------------------------------------
    "backdrop_colour": [0.055, 0.055, 0.062],
    "backdrop_strength": 0.55,
    "why_dark": "the clay is a mid grey; a mid-grey backdrop leaves a flat "
                "elevation with no silhouette. A dark backdrop separates "
                "every view without touching the part.",

    # --- lighting ------------------------------------------------------
    "key_light": {"loc": [-160, -220, 260], "rot_deg": [42, 0, -36],
                  "size": [260, 260], "energy": 5.2e5},
    "fill_light": {"loc": [200, -180, 130], "rot_deg": [66, 0, 48],
                   "size": [220, 220], "energy": 1.5e5},
    # The side elevation faces away from the key, so its separation comes
    # almost entirely from the rim. At 4.8e5 it reached 28 against a
    # predeclared bar of 40 — the bar stays and the light does the work.
    "rim_light": {"loc": [90, 230, 200], "rot_deg": [52, 0, 160],
                  "size": [60, 240], "energy": 1.15e6,
                  "role": "edge separation against the dark backdrop"},
    "second_rim_light": {"loc": [-230, 120, 170],
                         "rot_deg": [58, 0, -110],
                         "size": [60, 240], "energy": 9.0e5,
                         "role": "separation for the opposite elevation"},
    "dramatic_lighting": False,
    "depth_of_field": False,

    # --- render --------------------------------------------------------
    "engine": "CYCLES", "device": "CPU", "seed": 0,
    "samples": 40, "denoising": False,
    "view_transform": "Standard", "exposure": 0.0, "gamma": 1.0,
    "colour_depth": "8", "film_transparent": False,
    "resolution": [1500, 1500],
    "camera_mode": "ORTHOGRAPHIC",
    "contact_shading": "AREA_LIGHT_SOFT_SHADOW_NO_POST_AO",
    "post_processing": "NONE",
    "edge_enhancement": False,
    "silhouette_altering_post": False,

    # --- thresholds ----------------------------------------------------
    "minimum_subject_coverage":
        MINIMUM_MODAL_BACKGROUND_SUBJECT_COVERAGE,
    "minimum_luminance_contrast": MINIMUM_LUMINANCE_CONTRAST,
    "thresholds_predeclared": True,
}

#: M5 material comparison is a SEPARATE view category with its own
#: deterministic policy, shared by all six variants.
#:
#: The M4B-B legibility rig drives highlights to clipping — matte measured
#: p99 253.7 of 255. Specular behaviour is exactly what separates matte
#: from satin from gloss, and a clipped highlight carries none of it, so
#: every material rendered the same. This policy trades some silhouette
#: punch for highlight headroom. It does not change either legibility bar,
#: and it does not apply to the M4B-B review set.
M5_MATERIAL_POLICY = {
    "why": "specular discrimination needs unclipped highlights",
    "key_energy": 1.4e5,
    "fill_energy": 5.0e4,
    "rim_energy": 1.6e5,
    "second_rim_energy": 1.1e5,
    "backdrop_colour": [0.055, 0.055, 0.062],
    "backdrop_strength": 0.55,
    "identical_across_all_variants": True,
}


def m5_material_config() -> dict:
    """The M5 comparison rig — one policy, all six variants."""
    p = M5_MATERIAL_POLICY
    return {
        "backdrop_colour": p["backdrop_colour"],
        "backdrop_strength": p["backdrop_strength"],
        "key_energy": p["key_energy"],
        "fill_energy": p["fill_energy"],
        "rim_energy": p["rim_energy"],
        "rim2": {**CONTRACT["second_rim_light"],
                 "energy": p["second_rim_energy"]},
        "render_contract_version": VERSION,
    }


#: §4 — framing authority. A frame is derived from what the view shows.
FRAME_RULES = {
    "CLOSED_STATE_FRAME": "derived from the CLOSED assembly bounds",
    "OPEN_STATE_FRAME": "derived from the articulated open assembly bounds",
    "DETAIL_FRAME": "derived from the selected component bounds plus a "
                    "deterministic margin",
    "PAN_LAYOUT_FRAME": "derived from the tray and pan-field bounds",
}

FRAME_MARGIN = 1.18

#: Elevations are thin by nature — an open side view of a flat palette is
#: two bars seen edge-on. An 18% margin spends a fifth of the frame on
#: emptiness there, so elevations get a tighter deterministic margin.
#: Applied uniformly to every front and side view of both families; this
#: changes framing, not either legibility bar.
ELEVATION_FRAME_MARGIN = 1.04

DETAIL_MARGIN_MM = 8.0


def contract_identity() -> str:
    return hashlib.sha256(
        json.dumps(CONTRACT, sort_keys=True).encode()).hexdigest()[:16]


def blender_config() -> dict:
    """The subset the render script consumes."""
    c = CONTRACT
    return {
        "backdrop_colour": c["backdrop_colour"],
        "backdrop_strength": c["backdrop_strength"],
        "rim_energy": c["rim_light"]["energy"],
        "rim2": c["second_rim_light"],
        "samples": c["samples"],
        "resolution": list(c["resolution"]),
        "render_contract_version": VERSION,
    }


def record() -> dict:
    return {"record_type": SCHEMA, "version": VERSION,
            "contract": dict(CONTRACT),
            "frame_rules": dict(FRAME_RULES),
            "frame_margin": FRAME_MARGIN,
            "detail_margin_mm": DETAIL_MARGIN_MM,
            "contract_identity": contract_identity(),
            "changes_geometry": False,
            "owner_approved": False}
