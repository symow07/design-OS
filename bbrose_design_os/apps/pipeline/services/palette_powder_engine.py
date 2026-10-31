"""M6 §3 — the versioned PowderMaterialSpec and its three identities.

A powder family is a STRUCTURE, not a name pointing at a generic shader,
so the contract carries the structural parameters each family actually
needs and refuses parameters that belong to a different structure — a
GLITTER particle census on a MATTE spec is a category error, not a
default to be ignored.

Three identities, kept apart on purpose:

- POWDER_GEOMETRY_IDENTITY — the geometry-affecting subset (fill depth,
  recess, crown/dome, edge profile). BAKED changes it; a colour change
  cannot. It never includes the metal pan: a domed powder sits in an
  unchanged pan.
- POWDER_MATERIAL_IDENTITY — family, shade, seed and every shader-side
  parameter. Material-only changes move this and nothing else.
- POWDER_EVIDENCE_IDENTITY — the pair of a rendered mesh identity and a
  material identity, same law as M5: two materials on one mesh are two
  pieces of evidence.

Colour authority: every shade names its authority. Two are admitted —
PROVISIONAL_VISUALIZATION_SHADE and, since 2026-08-13,
OWNER_CHOSEN_DESIGN_INTENT for ES3083's settled twelve. Anything
stronger (a Pantone specification, a measured Lab) is not admitted
because it is not held. Pantone tokens stay symbolic and FB3090 stays
UNSOURCED.

COLOUR SPACE rides on the AUTHORITY, via COLOUR_SPACE_BY_AUTHORITY, and
is resolved in realize() alone. That is deliberate: `authority` is
already inside shade.to_dict() and therefore already inside
material_identity(), so the input governing the shader value sits
INSIDE the identity chain (3aa) without a new field and without moving
one recorded identity.

KNOWN HOLE — defect class 23, PROVENANCE_ASSERTED_BUT_NOT_CONTENT_BOUND.
The authority is CALLER-ASSERTED. Nothing in PowderShade inspects a
triple to check it is really sRGB, and no such check is wanted: a
validator that guesses whether numbers "look like" sRGB would be a
fabricated measurement. So a caller could construct an
OWNER_CHOSEN_DESIGN_INTENT shade from raw values and have it silently
transferred. That hole is UNREACHABLE from inside this repository —
es3083_owner_shade_set() is the only construction site and it builds
every triple through hex_to_srgb_triple — and the test that pins that,
with its search extent, is
OwnerShadeSetTests.test_the_class_23_hole_is_unreachable_in_this_tree.
It is stated here rather than hidden because the guarantee is about
this tree, not about the class.
"""
from __future__ import annotations

import hashlib
import json

from apps.pipeline.services import palette_powder_protocol as PP

SCHEMA = "powder_material_spec/1.0"
VERSION = 1

PROVISIONAL_VISUALIZATION_SHADE = "PROVISIONAL_VISUALIZATION_SHADE"
NOT_OWNER_COLOUR_AUTHORITY = "NOT_OWNER_COLOUR_AUTHORITY"

#: The owner chose these hexes as a design decision. CHOOSING IS NOT
#: MEASURING: nothing here matches a physical chip, a Pantone number or
#: a spectrophotometer reading. This is the weakest of the four tiers
#: the programme recognises and it is enough to render, to make artwork
#: and to put a deliverable in front of a client. It is NOT
#: manufacturing colour authority and must never be read as one.
OWNER_CHOSEN_DESIGN_INTENT = "OWNER_CHOSEN_DESIGN_INTENT"

#: What a shade at that authority reports for owner_colour_authority.
#: The wording is the whole point of the record: the owner chose, and
#: choosing is not measuring.
OWNER_DESIGN_INTENT_NOT_MEASURED = "OWNER_DESIGN_INTENT_NOT_MEASURED"

#: the complete set of admitted shade authorities. Adding to this tuple
#: is a decision about evidence, not a refactor.
#:
#: DELIBERATELY ABSENT: OWNER_CONFIRMED, PANTONE_SPECIFIED,
#: MEASURED_LAB. Those tiers are real and each is STRONGER than
#: OWNER_CHOSEN_DESIGN_INTENT, but the owner does not hold them yet, and
#: a constant that exists is a constant something will eventually be
#: stamped with.
SHADE_AUTHORITIES = (PROVISIONAL_VISUALIZATION_SHADE,
                     OWNER_CHOSEN_DESIGN_INTENT)

#: what each authority reports downstream. A dict rather than a chain of
#: ifs, so an authority admitted above without a decision made here
#: raises at construction instead of defaulting to the safe-looking
#: string — a lookup carrying a default is how a chosen colour would
#: quietly report as a measured one.
OWNER_COLOUR_AUTHORITY_BY_AUTHORITY = {
    PROVISIONAL_VISUALIZATION_SHADE: NOT_OWNER_COLOUR_AUTHORITY,
    OWNER_CHOSEN_DESIGN_INTENT: OWNER_DESIGN_INTENT_NOT_MEASURED,
}

#: The state of the provisional fixture's triples, named honestly. They
#: were authored as raw 0..1 values and NEVER declared a space. This
#: constant asserts nothing about what they are; it records that nobody
#: said. They are not transformed, and the reason is that NOTHING IS
#: KNOWN about them — not that they are known to be scene-linear.
AUTHORED_COLOUR_SPACE_UNDECLARED = "AUTHORED_COLOUR_SPACE_UNDECLARED"
AUTHORED_SRGB = "sRGB_IEC_61966_2_1"
SCENE_LINEAR = "SCENE_LINEAR"

#: Which space each authority's stored triple is IN.
#:
#: The colour space rides on the AUTHORITY rather than on a new
#: PowderShade field, and that is the whole design: `authority` is
#: already inside shade.to_dict(), which is already digested by
#: material_identity(), so the input that governs the shader value sits
#: INSIDE the identity chain (3aa) and not one material identity moves.
#: A colour_space field would have been more precise per shade and
#: would have moved all 671 recorded identities to say something that
#: today has exactly two values.
#:
#: TOTAL over SHADE_AUTHORITIES, and read by SUBSCRIPT — an authority
#: admitted without a space decided here raises rather than defaulting.
COLOUR_SPACE_BY_AUTHORITY = {
    PROVISIONAL_VISUALIZATION_SHADE: AUTHORED_COLOUR_SPACE_UNDECLARED,
    OWNER_CHOSEN_DESIGN_INTENT: AUTHORED_SRGB,
}

#: Whether a triple in that space is transferred on the way to the
#: shader. Same subscript discipline, same reason.
TRANSFORM_TO_SCENE_LINEAR = {
    AUTHORED_SRGB: True,
    AUTHORED_COLOUR_SPACE_UNDECLARED: False,
}

#: re-exported so callers speak one vocabulary
FAMILIES = PP.POWDER_FAMILIES


class PowderSpecError(ValueError):
    """Raised when a powder spec is structurally wrong. Never repaired."""


# --------------------------------------------------------------------------
# parameter schema — common core + per-family structural blocks
# --------------------------------------------------------------------------

#: Geometry-affecting parameters: these rebuild the powder VOLUME (and
#: only the powder volume — the metal pan identity is untouchable from
#: here). Everything else is material-only by construction.
GEOMETRY_AFFECTING = ("fill_depth_mm", "powder_recess_mm",
                      "crown_height_mm", "edge_profile")

#: Parameters every family carries.
COMMON_PARAMS = {
    "fill_depth_mm": 2.5,
    "powder_recess_mm": 0.3,
    "crown_height_mm": 0.25,
    "edge_profile": "SOFT_ROUNDED",
    "surface_roughness": 0.85,
    "microtexture": {"scale_mm": 0.16, "strength": 0.30},
    "macrotexture": {"scale_mm": 2.4, "strength": 0.06},
}

#: Structural blocks a family REQUIRES beyond the common core. A block
#: named here may not appear on any family that does not declare it.
#: Under-declared builder constants, reconciled into the contract by
#: M6-CONTRACT-INTEGRITY-REPAIR (value-preserving half): every value
#: below is EXACTLY the literal the builder realized before the
#: repair, now declared and consumed. Census:
#: docs/roadmap/palt_m6/builder_constant_census.json (+ the six
#: census-supplement constants recorded in the repair node).
_LAW = "AMPLITUDE_TIMES_SCALE_MM"
SHADER_BLOCKS = {
    PP.POWDER_MATTE: {
        "specular_ior_level": 0.18, "noise_distortion": 0.0, "noise_detail_base": 3.0,
        "noise_detail_variance_coeff": 3.0,
        "compression_noise_detail": 2.0, "compression_seed_offset": 1,
        "roughness_variation_coeff": 0.08, "mottle_detail": 2.0,
        "mottle_seed_offset": 5, "bump_distance_law": _LAW},
    PP.POWDER_SATIN: {
        "specular_ior_level": 0.28, "noise_distortion": 0.0, "noise_detail_base": 2.0,
        "noise_detail_variance_coeff": 2.0, "roughness_base": 0.48,
        "roughness_smoothing_coeff": 0.10,
        "mottle_strength_factor": 0.5, "mottle_detail": 2.0,
        "mottle_seed_offset": 5, "bump_distance_law": _LAW},
    PP.SHIMMER: {
        "specular_ior_level": 0.28, "noise_distortion": 0.0, "flake_roughness_base": 0.18,
        "flake_roughness_metallic_coeff": 0.25,
        "facet_jitter_per_sparkle": 1.0, "mottle_detail": 2.0,
        "mottle_seed_offset": 5},
    PP.POWDER_METALLIC: {
        "specular_ior_level": 0.28, "noise_distortion": 0.0, "flake_roughness_base": 0.18,
        "flake_roughness_metallic_coeff": 0.25,
        "facet_jitter_per_sparkle": 1.0, "mottle_detail": 2.0,
        "mottle_seed_offset": 5},
    PP.GLITTER: {
        "specular_ior_level": 0.28, "noise_distortion": 0.0, "particle_roughness": 0.05,
        "jitter_denominator_deg": 90.0,
        "voronoi_distance": "CHEBYCHEV", "mottle_detail": 2.0,
        "mottle_seed_offset": 5},
    PP.BAKED: {
        "specular_ior_level": 0.28, "noise_distortion": 0.0, "crust_noise_scale_mm": 0.5,
        "crust_noise_detail": 5.0, "crust_distortion": 0.8,
        "baked_roughness": 0.38, "coat_gloss_factor": 0.5,
        "mottle_detail": 2.0, "mottle_seed_offset": 5,
        "bump_distance_law": _LAW},
    PP.MARBLED: {
        #: C6 — the component derivation is GENUINELY CHROMATIC:
        #: per-channel asymmetric coefficients break the R:G:B
        #: preservation that made the marble luminance-only
        #: (census L305). Values remain PROVISIONAL_VISUALIZATION
        #: derived — NOT owner colour authority.
        "component_derivation": {
            "form": "PER_CHANNEL_ASYMMETRIC_CHROMATIC",
            "darker_rgb_coeffs": [0.45, 0.55, 0.70],
            "lighter_rgb_coeffs": [1.45, 1.30, 1.15],
            "lighter_rgb_offsets": [0.08, 0.05, 0.02]},
        "specular_ior_level": 0.28, "noise_distortion": 0.0, "vein_detail": 4.0,
        "vein_distortion": 1.2, "vein2_scale_factor": 0.6,
        "vein2_seed_offset": 11, "ramp_width_2comp": 0.10,
        "ramp_width_3comp": 0.08, "micro_noise_detail": 4.0,
        "micro_seed_offset": 2, "microtexture_strength_factor": 0.8,
        "bump_distance_law": _LAW},
    PP.PRESSED_POWDER: {
        "specular_ior_level": 0.28, "noise_distortion": 0.0, "micro_noise_detail": 4.0,
        "packed_roughness_compaction_coeff": 0.35,
        "ring_gaussian_falloff": -250.0, "mottle_flatness_coeff": 0.5,
        "mottle_detail": 2.0, "mottle_seed_offset": 5,
        "bump_distance_law": _LAW},
    PP.CREAM: {
        "specular_ior_level": 0.28, "noise_distortion": 0.0, "swell_scale_mm": 6.0,
        "swell_amplitude": 0.015, "swell_detail": 1.0,
        "bump_distance_law": _LAW},
}

FAMILY_PARAMS = {
    PP.POWDER_MATTE: {
        "compression_texture": {"scale_mm": 0.6, "strength": 0.12},
        #: loose-milled: broad particle distribution, strong incoherent
        #: micro-normal field — the structure behind a broad dull lobe
        #: scales sit ABOVE the rig's resolvable limit (>=3px at
        #: 14.3px/mm = 0.21mm) — the bump-realization diagnosis proved
        #: sub-resolution grain renders as nothing at all
        "milling": {"microparticle_scale_mm": 0.35,
                    "microparticle_variance": 0.60,
                    "micronormal_amplitude": 0.34,
                    "micronormal_correlation_mm": 0.35,
                    "surface_smoothing": 0.0},
    },
    PP.POWDER_SATIN: {
        "sheen_response": {"sheen": 0.45, "tint": 0.15},
        "compression_texture": {"scale_mm": 0.6, "strength": 0.10},
        #: finer-milled: small uniform grain, LOW-amplitude micro-normal
        #: field — a satin powder is smoother powder, never glossy
        #: plastic; the coherent sheen rides on that uniformity
        "milling": {"microparticle_scale_mm": 0.21,
                    "microparticle_variance": 0.20,
                    "micronormal_amplitude": 0.10,
                    "micronormal_correlation_mm": 0.21,
                    "surface_smoothing": 0.50},
    },
    PP.SHIMMER: {
        "flakes": {"flake_scale_mm": 0.055, "flake_density": 0.85,
                   "flake_orientation": "ISOTROPIC",
                   "metallic_response": 0.45,
                   "sparkle_intensity": 0.35,
                   "sparkle_distribution": "CONTINUOUS_FINE"},
    },
    PP.POWDER_METALLIC: {
        "flakes": {"flake_scale_mm": 0.04, "flake_density": 0.97,
                   "flake_orientation": "ISOTROPIC",
                   "metallic_response": 0.90,
                   "sparkle_intensity": 0.20,
                   "sparkle_distribution": "CONTINUOUS_DENSE"},
    },
    PP.GLITTER: {
        "particles": {"particle_size_mm": 0.70,
                      "size_distribution": "UNIFORM_0.5_TO_0.9",
                      "coverage": 0.10,
                      "orientation_jitter_deg": 35.0,
                      "shape_class": "IRREGULAR_FLAKE",
                      "reflectance": 1.0,
                      "depth_distribution": "SURFACE_BIASED"},
    },
    PP.BAKED: {
        "dome": {"crown_height_mm": 1.2, "edge_transition_mm": 1.6,
                 "lid_clearance_required_mm": 0.5},
        "crust": {"gloss": 0.30, "baked_microtexture_strength": 0.18},
    },
    PP.MARBLED: {
        "marbling": {"components": 2, "vein_scale_mm": 5.5,
                     "directional_bias_deg": 20.0,
                     "mixing_ratio": [0.65, 0.35],
                     "coordinate_mapping": "OBJECT_ATTACHED"},
    },
    PP.PRESSED_POWDER: {
        "press": {"ring_radius_frac": 0.88, "ring_strength": 0.10,
                  "compressed_scale_mm": 0.25,
                  "compressed_strength": 0.22},
        #: §6 — compaction is the FAMILY, not an inherited roughness:
        #: a pressed surface is packed, flatter, finer and denser than
        #: loose-milled powder, and every one of those is a parameter
        "compaction": {"compaction_level": 0.80,
                       "surface_flatness": 0.85,
                       "compression_texture_scale_mm": 0.25,
                       "compression_texture_amplitude": 0.10,
                       "edge_packing": 0.90,
                       "surface_density": 0.90},
    },
    PP.CREAM: {
        "continuity": {"granularity_forbidden": True,
                       "soft_specular_roughness": 0.32},
    },
}

for _fam, _blk in SHADER_BLOCKS.items():
    FAMILY_PARAMS[_fam]["shader"] = _blk

#: CREAM is a continuous emulsion — granular powder microstructure on a
#: cream spec is a contradiction the validator refuses.
CREAM_MAX_MICROTEXTURE_STRENGTH = 0.02

#: Parameters DECLARED in family definitions that the render provably
#: does not consume — established by the one-parameter-at-a-time
#: realization audit (bit-identical frames). They stay in the contract
#: (identities frozen) but NO downstream reader — designer, supplier,
#: rig — may take them as effective, and no rig may claim sensitivity
#: to them. Plumbing any of these is a flagged family-revision node
#: that voids dependent controls; it is never a silent fix. The
#: realization-coverage test asserts every declared parameter carries
#: a recorded audit delta, so a new parameter cannot join a family
#: without demonstrating it does something.
#: Engine-wide family-scoped dead marking (M6-CONTRACT-INTEGRITY-REPAIR): every DECLARED_NOT_REALIZED instance from the realization audit, declared in the contract so no reader can take one as effective.
NOT_REALIZED_IN_RENDER_BY_FAMILY = {
    "BAKED:edge_profile":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "BAKED:microtexture.scale_mm":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "BAKED:microtexture.strength":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "BAKED:surface_roughness":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "CREAM:edge_profile":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "CREAM:macrotexture.scale_mm":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "CREAM:macrotexture.strength":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "CREAM:microtexture.scale_mm":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "CREAM:microtexture.strength":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "CREAM:surface_roughness":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "GLITTER:edge_profile":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "GLITTER:microtexture.scale_mm":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "GLITTER:microtexture.strength":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "GLITTER:particles.depth_distribution":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "GLITTER:particles.shape_class":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "GLITTER:particles.size_distribution":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "MARBLED:edge_profile":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "MARBLED:macrotexture.scale_mm":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "MARBLED:macrotexture.strength":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "MARBLED:marbling.coordinate_mapping":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_MATTE:edge_profile":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_MATTE:microtexture.scale_mm":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_MATTE:microtexture.strength":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_MATTE:milling.micronormal_correlation_mm":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_MATTE:milling.surface_smoothing":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_METALLIC:edge_profile":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_METALLIC:flakes.flake_orientation":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_METALLIC:flakes.sparkle_distribution":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_METALLIC:microtexture.scale_mm":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_METALLIC:microtexture.strength":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_SATIN:compression_texture.scale_mm":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_SATIN:compression_texture.strength":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_SATIN:edge_profile":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_SATIN:microtexture.scale_mm":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_SATIN:microtexture.strength":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_SATIN:milling.micronormal_correlation_mm":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "POWDER_SATIN:surface_roughness":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "PRESSED_POWDER:compaction.edge_packing":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "PRESSED_POWDER:compaction.surface_density":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "PRESSED_POWDER:edge_profile":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "PRESSED_POWDER:microtexture.scale_mm":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "PRESSED_POWDER:microtexture.strength":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "PRESSED_POWDER:press.compressed_scale_mm":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "PRESSED_POWDER:press.compressed_strength":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "SHIMMER:edge_profile":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "SHIMMER:flakes.flake_orientation":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "SHIMMER:flakes.sparkle_distribution":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "SHIMMER:microtexture.scale_mm":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
    "SHIMMER:microtexture.strength":
        "audit DECLARED_NOT_REALIZED — marked by M6-CONTRACT-INTEGRITY-REPAIR; plumbing is a flagged family-revision node paying its void list",
}

NOT_REALIZED_IN_RENDER = {
    "flakes.flake_orientation":
        "audit rms 0.000000 (parameter_plumbing_audit.json) — SHIMMER "
        "ISOTROPIC vs POWDER_METALLIC ISOTROPIC declares no distinction "
        "anyway, but the parameter reaches no node",
    "flakes.sparkle_distribution":
        "audit rms 0.000000 — CONTINUOUS_FINE vs CONTINUOUS_DENSE is a "
        "DECLARED family distinction with NO physical realization; a "
        "reader of the family definition must not take it as effective",
}

#: Family-level corrections to the common core, applied BEFORE user
#: overrides so the defaults are self-consistent (a default that trips
#: the family's own guard is a broken contract, not a user error).
FAMILY_COMMON_OVERRIDES = {
    PP.CREAM: {"microtexture": {"scale_mm": 0.16, "strength": 0.0},
               "surface_roughness": 0.32},
    PP.POWDER_METALLIC: {"surface_roughness": 0.42},
    PP.SHIMMER: {"surface_roughness": 0.55},
}


class PowderShade:
    """A shade with an explicit colour authority. No authority, no shade."""

    def __init__(self, name, rgb, authority):
        if authority not in SHADE_AUTHORITIES:
            raise PowderSpecError(
                f"unknown colour authority {authority!r} — the admitted "
                f"set is {list(SHADE_AUTHORITIES)}. Anything stronger "
                "(a Pantone specification, a measured Lab value) is not "
                "admitted because it is not held; adding to that set is "
                "a decision about evidence, not a refactor")
        if "PANTONE" in name.upper():
            raise PowderSpecError(
                "a provisional shade may not carry a Pantone name — that "
                "would read as a fabricated conversion")
        if not (isinstance(rgb, (tuple, list)) and len(rgb) == 3
                and all(0.0 <= float(v) <= 1.0 for v in rgb)):
            raise PowderSpecError(f"shade rgb {rgb!r} is not a 0..1 triple")
        self.name = name
        self.rgb = tuple(round(float(v), 4) for v in rgb)
        self.authority = authority

    def to_dict(self):
        # branched on the authority, not stamped unconditionally: the
        # old constant reported NOT_OWNER_COLOUR_AUTHORITY for every
        # shade, which became false the moment twelve owner-chosen
        # shades existed. Subscript, never a lookup carrying a default —
        # an unmapped authority raises here rather than reporting the
        # reassuring value.
        return {"name": self.name, "rgb": list(self.rgb),
                "authority": self.authority,
                "owner_colour_authority":
                    OWNER_COLOUR_AUTHORITY_BY_AUTHORITY[self.authority]}


def _merge(base, override, path, allowed):
    out = dict(base)
    for key, value in (override or {}).items():
        if key not in base:
            raise PowderSpecError(
                f"unknown parameter {path}{key!r} for this family — a "
                f"structural block belongs only to the family that "
                f"declares it (allowed: {sorted(allowed)})")
        if isinstance(base[key], dict):
            out[key] = _merge(base[key], value, f"{path}{key}.",
                              set(base[key]))
        else:
            out[key] = value
    return out


class PowderMaterialSpec:
    """One family, one shade, one seed — fully validated at construction."""

    def __init__(self, family, shade, *, seed, overrides=None):
        if family not in FAMILIES:
            raise PowderSpecError(f"unknown powder family {family!r}")
        if not isinstance(shade, PowderShade):
            raise PowderSpecError("shade must be a PowderShade")
        if not isinstance(seed, int):
            raise PowderSpecError("deterministic seed must be an int")
        self.family, self.shade, self.seed = family, shade, int(seed)

        base = dict(COMMON_PARAMS)
        for key, value in FAMILY_COMMON_OVERRIDES.get(family, {}).items():
            base[key] = ({**base[key], **value}
                         if isinstance(base[key], dict) else value)
        for block, defaults in FAMILY_PARAMS[family].items():
            base[block] = defaults
        allowed = set(base)
        self.params = _merge(base, overrides, "", allowed)

        if family == PP.BAKED:
            # the dome IS the crown for a baked pan; keeping two crown
            # numbers would let them silently disagree
            self.params["crown_height_mm"] = \
                self.params["dome"]["crown_height_mm"]
        if family == PP.CREAM:
            strength = self.params["microtexture"]["strength"]
            if strength > CREAM_MAX_MICROTEXTURE_STRENGTH:
                raise PowderSpecError(
                    f"CREAM is a continuous emulsion — granular "
                    f"microtexture strength {strength} contradicts the "
                    f"family (max {CREAM_MAX_MICROTEXTURE_STRENGTH})")
        if family == PP.MARBLED:
            m = self.params["marbling"]
            if m["components"] not in (2, 3):
                raise PowderSpecError(
                    "marbling supports 2 or 3 colour components")
            if len(m["mixing_ratio"]) != m["components"]:
                raise PowderSpecError(
                    "mixing_ratio length must equal components")
            if abs(sum(m["mixing_ratio"]) - 1.0) > 1e-6:
                raise PowderSpecError("mixing_ratio must sum to 1.0")

    # -- identities ------------------------------------------------------

    def geometry_params(self) -> dict:
        geo = {k: self.params[k] for k in GEOMETRY_AFFECTING}
        if self.family == PP.BAKED:
            geo["dome"] = self.params["dome"]
        return geo

    def geometry_state_identity(self) -> str:
        """Identity of the REQUESTED powder-volume geometry state.

        The realized mesh gets its own mesh identity from the builder;
        this pins what was asked for, so a material-only change (same
        geometry params) provably cannot move it.
        """
        payload = json.dumps({"schema": SCHEMA, "version": VERSION,
                              "geometry": self.geometry_params()},
                             sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def material_identity(self) -> str:
        payload = json.dumps({
            "schema": SCHEMA, "version": VERSION,
            "family": self.family, "seed": self.seed,
            "shade": self.shade.to_dict(), "params": self.params,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    # -- realization -----------------------------------------------------

    def realize(self) -> dict:
        """The shader-side block consumed by the production render script.

        THE COLOUR SPACE IS RESOLVED HERE AND NOWHERE ELSE. The shader
        socket is scene-linear; a shade authored in sRGB is transferred
        on the way to it, and a shade whose space was never declared is
        passed through untouched. This is the only place the transfer
        happens, so PowderShade, to_dict(), material_identity() and the
        frozen builder are all unmoved.

        FIELD NAMING. `display_rgb` was a lie the moment any value on
        that path became scene-linear, and a field whose name
        contradicts its contents is how this defect happened the first
        time. It is NOT renamed away, because
        blender_scripts/powder_materials.py reads spec["display_rgb"] in
        nine places and is the FROZEN INSTRUMENT — renaming it would
        KeyError the render path, and editing it is
        M6-CONTRACT-INTEGRITY-REPAIR's jurisdiction. So the honest names
        are ADDED and `display_rgb` is retained as an explicit
        frozen-contract alias carrying the same values. Every new
        consumer reads shader_input_rgb.
        """
        space = COLOUR_SPACE_BY_AUTHORITY[self.shade.authority]
        authored = list(self.shade.rgb)
        transform = TRANSFORM_TO_SCENE_LINEAR[space]
        shader = ([srgb_to_linear(c) for c in authored] if transform
                  else list(authored))
        return {
            "powder_family": self.family,
            "shader_input_rgb": shader,
            # only claimed where it was earned: an untransformed triple
            # is still in whatever space nobody declared
            "shader_input_colour_space": (SCENE_LINEAR if transform
                                          else space),
            "authored_rgb": authored,
            "authored_colour_space": space,
            "colour_transform_applied": transform,
            "colour_transform": (SRGB_TRANSFER_FUNCTION if transform
                                 else "NONE"),
            #: FROZEN-CONTRACT ALIAS of shader_input_rgb. The name is
            #: wrong and is kept only because the frozen builder reads
            #: this key. Do not read it in new code.
            "display_rgb": shader,
            "shade": self.shade.to_dict(),
            "seed": self.seed,
            "params": self.params,
            "material_identity": self.material_identity(),
            "geometry_state_identity": self.geometry_state_identity(),
        }

    def to_dict(self) -> dict:
        return {
            "record_type": SCHEMA, "version": VERSION,
            "family": self.family,
            "shade": self.shade.to_dict(),
            "seed": self.seed,
            "params": self.params,
            "POWDER_GEOMETRY_IDENTITY": self.geometry_state_identity(),
            "POWDER_MATERIAL_IDENTITY": self.material_identity(),
            "geometry_affecting": sorted(
                set(GEOMETRY_AFFECTING)
                | ({"dome"} if self.family == PP.BAKED else set())),
            "owner_approved": False,
            "manufacturing_authority": "NOT_ESTABLISHED",
        }


def powder_evidence_identity(mesh_geometry_identity, spec) -> str:
    """Same law as M5: evidence is the (mesh, material) pair."""
    return hashlib.sha256(
        (mesh_geometry_identity + spec.material_identity())
        .encode()).hexdigest()[:16]


# --------------------------------------------------------------------------
# §19 — the ES3083 provisional 12-shade test set
# --------------------------------------------------------------------------

def es3083_provisional_shade_set() -> list:
    """Twelve deterministic (pan, shade, family) rows for the 4x3 grid.

    Every shade is PROVISIONAL_VISUALIZATION_SHADE — chosen to exercise
    light/medium/dark and warm/cool across the families, and NEVER a
    claim about ES3083's commercial assortment.
    """
    def s(name, rgb):
        return PowderShade(name, rgb, PROVISIONAL_VISUALIZATION_SHADE)

    rows = [
        (1, s("prov_light_warm_ivory", (0.88, 0.80, 0.68)),
         PP.POWDER_MATTE),
        (2, s("prov_light_cool_rose", (0.85, 0.72, 0.74)),
         PP.POWDER_SATIN),
        (3, s("prov_light_champagne", (0.87, 0.78, 0.62)), PP.SHIMMER),
        (4, s("prov_medium_warm_copper", (0.62, 0.38, 0.24)),
         PP.POWDER_METALLIC),
        (5, s("prov_medium_terracotta", (0.60, 0.36, 0.28)),
         PP.POWDER_MATTE),
        (6, s("prov_medium_cool_mauve", (0.52, 0.40, 0.48)),
         PP.POWDER_SATIN),
        (7, s("prov_medium_bronze", (0.48, 0.34, 0.20)), PP.BAKED),
        (8, s("prov_medium_gold_glitter", (0.68, 0.52, 0.24)),
         PP.GLITTER),
        (9, s("prov_dark_warm_sienna", (0.38, 0.22, 0.14)),
         PP.POWDER_MATTE),
        (10, s("prov_dark_cool_plum", (0.30, 0.18, 0.26)), PP.MARBLED),
        (11, s("prov_dark_espresso", (0.24, 0.16, 0.12)),
         PP.POWDER_SATIN),
        (12, s("prov_dark_graphite_shimmer", (0.22, 0.22, 0.25)),
         PP.SHIMMER),
    ]
    return [{"pan": pan, "spec": PowderMaterialSpec(fam, shade, seed=pan)}
            for pan, shade, fam in rows]


#: sRGB, IEC 61966-2-1. The hex the owner chose IS the authority; this
#: is the transfer that makes it usable by a scene-linear consumer, and
#: it is code rather than a table of magic numbers so the derivation
#: carries an identity (3aa).
SRGB_TRANSFER_FUNCTION = "IEC_61966_2_1_sRGB_EOTF"


def srgb_to_linear(channel: float) -> float:
    """One sRGB-encoded 0..1 channel to scene-linear."""
    c = float(channel)
    if not 0.0 <= c <= 1.0:
        raise PowderSpecError(f"channel {channel!r} is not 0..1")
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(channel: float) -> float:
    """The inverse transfer — the sRGB OETF, the display encode.

    Needed to STATE what an unconverted value arrives as, in code
    rather than in prose (3aa). It is strictly ABOVE the identity on
    (0, 1), which is why feeding an sRGB value to a scene-linear socket
    can only ever arrive LIGHTER, never darker.
    """
    L = float(channel)
    if not 0.0 <= L <= 1.0:
        raise PowderSpecError(f"channel {channel!r} is not 0..1")
    return L * 12.92 if L <= 0.0031308 else 1.055 * (L ** (1 / 2.4)) - 0.055


def hex_to_srgb_triple(hex_value: str) -> tuple:
    """#RRGGBB to a 0..1 sRGB triple at 4dp. The hex is the authority
    and the triple is DERIVED from it, never entered alongside it."""
    h = hex_value.lstrip("#")
    if len(h) != 6:
        raise PowderSpecError(f"{hex_value!r} is not #RRGGBB")
    return tuple(round(int(h[i:i + 2], 16) / 255, 4) for i in (0, 2, 4))


#: The owner's settled twelve for ES3083, light to deep, in grid order.
#: Decided 2026-08-13; seven ACCEPT, four RECOLOUR, one REPLACE.
#: SHADE_AUTHORITY_PROPOSAL.md is the decision, this is the data.
#:
#: GLITTER and CREAM are unused by this palette. That is a plain fact
#: about a palette designed for commerce, and it is not a shortfall.
ES3083_OWNER_SHADES = (
    {"pan": 1, "grid_pos": "R1C1", "name": "Petal Veil",
     "hex": "#F2E3D8", "family": PP.POWDER_MATTE,
     "role": "brow-bone / all-over base"},
    {"pan": 2, "grid_pos": "R1C2", "name": "First Light",
     "hex": "#E9CBAE", "family": PP.POWDER_SATIN,
     "role": "inner corner, warm wash"},
    {"pan": 3, "grid_pos": "R1C3", "name": "Dew",
     "hex": "#E4D8D4", "family": PP.SHIMMER,
     "role": "warm pearl highlight"},
    {"pan": 4, "grid_pos": "R1C4", "name": "Damascena",
     "hex": "#D9A2A6", "family": PP.POWDER_MATTE,
     "role": "soft rose transition"},
    {"pan": 5, "grid_pos": "R2C1", "name": "Blush Hour",
     "hex": "#C57E82", "family": PP.POWDER_SATIN,
     "role": "mid rose lid"},
    {"pan": 6, "grid_pos": "R2C2", "name": "Attar",
     "hex": "#C9916B", "family": PP.BAKED,
     "role": "antique rose-gold lid"},
    {"pan": 7, "grid_pos": "R2C3", "name": "Copper Leaf",
     "hex": "#A85B33", "family": PP.POWDER_METALLIC,
     "role": "copper statement"},
    {"pan": 8, "grid_pos": "R2C4", "name": "Sage Stem",
     "hex": "#7F846E", "family": PP.POWDER_MATTE,
     "role": "olive-taupe, ties to the case"},
    {"pan": 9, "grid_pos": "R3C1", "name": "Old Rose",
     "hex": "#8D5459", "family": PP.PRESSED_POWDER,
     "role": "crease depth"},
    {"pan": 10, "grid_pos": "R3C2", "name": "Thorn",
     "hex": "#5D3A42", "family": PP.POWDER_MATTE,
     "role": "outer-V plum brown"},
    {"pan": 11, "grid_pos": "R3C3", "name": "Moss Garden",
     "hex": "#48583F", "family": PP.MARBLED,
     "role": "deep olive hero pan",
     "finish_note": (
         "MARBLED here means restrained antique-gold and olive "
         "marbling, NOT bright gold veining. A renderer that reads the "
         "family without this note will produce the thing the owner "
         "rejected.")},
    {"pan": 12, "grid_pos": "R3C4", "name": "Midnight Bloom",
     "hex": "#4A2E3B", "family": PP.POWDER_METALLIC,
     "role": "deep plum depth shade",
     "finish_note": (
         "POWDER_METALLIC, chosen by the owner over SHIMMER because "
         "#4A2E3B is dark enough that a soft pearl load disappears into "
         "its own base. Shares its family with Copper Leaf (pan 7); "
         "they sit at opposite ends of the depth run. The duplication "
         "is recorded, not hidden.")},
)


def es3083_owner_shade_set(seed_base=None) -> list:
    """The owner's settled twelve, at OWNER_CHOSEN_DESIGN_INTENT.

    THIS IS THE ONE SANCTIONED CONSTRUCTION SITE for owner shades
    (class-23 guard). ``seed_base`` lets a declared consumer (the M6
    products node, seeds 700+pan) obtain the same engine-canonical
    shades at its own declared seeds; the default None keeps seed=pan,
    so every existing caller's identities are untouched.

    Return shape is the fixture's, exactly — {"pan", "spec"} with
    seed = pan — so this is a drop-in wherever the fixture was read.
    The descriptive fields (grid_pos, hex, role, finish_note) live in
    ES3083_OWNER_SHADES rather than in the returned rows, so the shape
    stays a match and no consumer has to learn a second one.

    THE SHADE rgb IS sRGB, derived from the hex, and it STAYS sRGB
    here — the stored triple is the authority. The transfer to the
    shader's scene-linear socket is applied in
    PowderMaterialSpec.realize(), which resolves the space through
    COLOUR_SPACE_BY_AUTHORITY and emits shader_input_rgb. As of beb1fe5
    the engine DOES apply srgb_to_linear on that path; an earlier
    revision of this docstring said it did not, and that is withdrawn.
    """
    rows = []
    for row in ES3083_OWNER_SHADES:
        shade = PowderShade(row["name"], hex_to_srgb_triple(row["hex"]),
                            OWNER_CHOSEN_DESIGN_INTENT)
        if seed_base is None:
            seed = row["pan"]
        else:
            seed = seed_base + row["pan"]
        rows.append({"pan": row["pan"],
                     "spec": PowderMaterialSpec(row["family"], shade,
                                                seed=seed)})
    return rows


def fb3093_pressed_spec() -> PowderMaterialSpec:
    """The FB3093 pilot powder: PRESSED_POWDER, provisional shade."""
    return PowderMaterialSpec(
        PP.PRESSED_POWDER,
        PowderShade("prov_pressed_natural_beige", (0.80, 0.68, 0.56),
                    PROVISIONAL_VISUALIZATION_SHADE),
        seed=93)
