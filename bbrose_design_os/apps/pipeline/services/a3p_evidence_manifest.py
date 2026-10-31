"""PALT-M4B-A3P §5 — the authoritative required-evidence manifest.

The 41 diagnostic filenames were specified in the approved owner
directives that authorized A3F and A3M. A previous checkpoint recorded
them as ``NOT_ENUMERATED_IN_REPOSITORY``; that was wrong. The directives
name every file, and the list below is transcribed from them verbatim —
13 A3R, 16 A3F, 12 A3M.

Every entry is bound to a FROZEN geometry, and both frozen geometries
rebuild bit-for-bit from the kernel that still ships:

* A3R historical — cup_offset_mode RADIAL, cup_wall 1.00 mm, geometry
  identity ``743ead2beceb7fe5`` (legacy alias ``26c817b8c113851a``). This
  is the FAILED candidate C and its images must show the 0.600738 mm
  floor-fillet failure, labelled as historical.
* A3F corrected — cup_offset_mode TRUE_NORMAL, cup_wall 1.20 mm, geometry
  identity ``7c0558062fde67a7`` (legacy alias ``6c23c5417ef93dbb``).

Presenting a historical image as current output is one of the eight
failure conditions, so the milestone-to-geometry binding is data here and
is checked, not left to the person assembling the package.
"""
from __future__ import annotations

SCHEMA = "a3p_required_evidence_manifest/1.0"

A3R, A3F, A3M = "A3R", "A3F", "A3M"

#: Frozen geometry each milestone's evidence must be rendered from.
GEOMETRY_BINDING = {
    A3R: {
        "role": "HISTORICAL_FAILED_CANDIDATE_C",
        "mesh_geometry_identity": "743ead2beceb7fe5",
        "legacy_alias": "26c817b8c113851a",
        "core_overrides": {"cup_offset_mode": "RADIAL", "cup_wall_mm": 1.0},
        "status": "HISTORICAL",
        "shows": "the 0.600738 mm floor-fillet failure",
    },
    A3F: {
        "role": "CORRECTED_TRUE_NORMAL_1_20",
        "mesh_geometry_identity": "7c0558062fde67a7",
        "legacy_alias": "6c23c5417ef93dbb",
        "core_overrides": {"cup_offset_mode": "TRUE_NORMAL",
                           "cup_wall_mm": 1.2},
        "status": "CURRENT",
        "shows": "the corrected true-normal cup wall",
    },
    A3M: {
        "role": "CORRECTED_TRUE_NORMAL_1_20",
        "mesh_geometry_identity": "7c0558062fde67a7",
        "legacy_alias": "6c23c5417ef93dbb",
        "core_overrides": {"cup_offset_mode": "TRUE_NORMAL",
                           "cup_wall_mm": 1.2},
        "status": "CURRENT",
        "shows": "the 11.83 mm maximum and its long-path classification",
    },
}

#: Labels the directives require on every image of a milestone.
REQUIRED_LABELS = {
    A3R: ("HISTORICAL A3R FAILURE EVIDENCE",
          "FROZEN GEOMETRY 26c817b8c113851a",
          "0.600738 MM FLOOR-FILLET FAILURE"),
    A3F: ("A3F CORRECTED GEOMETRY",
          "TRUE-NORMAL CUP OFFSET 1.20 MM",
          "GEOMETRY 7c0558062fde67a7"),
    A3M: ("A3M MAXIMUM-THICKNESS DIAGNOSTIC",
          "GEOMETRY 7c0558062fde67a7",
          "LOCAL WALL IS NOT LONGEST MATERIAL PATH"),
}

#: (filename, milestone, purpose, feature the image must expose)
REQUIRED = (
    # --- 13 A3R, transcribed from the A3F and A3M directives ------------
    ("controlling_face_pair.png", A3R,
     "the two faces that define the failing 0.600738 mm interval",
     "FACE_PAIR"),
    ("minimum_location_top.png", A3R,
     "where the minimum sits, seen from above", "MINIMUM_MARKER"),
    ("minimum_location_underside.png", A3R,
     "the same location from the underside", "MINIMUM_MARKER"),
    ("minimum_location_wireframe.png", A3R,
     "the minimum against the mesh topology", "WIREFRAME"),
    ("minimum_location_normals.png", A3R,
     "the surface normals used to measure it", "NORMALS"),
    ("minimum_cross_section_primary.png", A3R,
     "a true section through the minimum", "SECTION"),
    ("minimum_cross_section_orthogonal.png", A3R,
     "the orthogonal section through the same point", "SECTION"),
    ("analytical_vs_ray_vs_section.png", A3R,
     "the three independent methods side by side", "METHOD_COMPARISON"),
    ("convergence_plot.png", A3R,
     "the density-convergence study", "CONVERGENCE"),
    ("adaptive_refinement_map.png", A3R,
     "adaptive refinement around the detected minimum", "REFINEMENT"),
    ("opposing_surface_pair_map.png", A3R,
     "which surface each sample was paired against", "PAIR_MAP"),
    ("thickness_definition_diagram.png", A3R,
     "what each thickness definition means and why they differ",
     "DEFINITION_DIAGRAM"),
    ("false_pairing_diagnostic.png", A3R,
     "how an incorrect opposing-surface pair would present",
     "FALSE_PAIRING"),

    # --- 16 A3F ---------------------------------------------------------
    ("radial_offset_vs_normal_offset_diagram.png", A3F,
     "why a radial offset does not preserve local normal thickness",
     "OFFSET_COMPARISON"),
    ("offset_strategy_matrix.png", A3F,
     "the 1.00 / 1.10 / 1.20 / 1.30 mm strategy matrix", "STRATEGY_MATRIX"),
    ("corrected_profile_control_points.png", A3F,
     "the corrected meridional profile and its control points",
     "PROFILE"),
    ("corrected_floor_fillet_closeup.png", A3F,
     "the floor fillet that previously collapsed", "FILLET_CLOSEUP"),
    ("corrected_tray_top.png", A3F, "the corrected tray from above",
     "TRAY_VIEW"),
    ("corrected_tray_underside.png", A3F,
     "the corrected tray underside showing the core", "TRAY_VIEW"),
    ("corrected_tray_wireframe.png", A3F, "the corrected mesh topology",
     "WIREFRAME"),
    ("corrected_tray_normals.png", A3F, "the corrected surface normals",
     "NORMALS"),
    ("corrected_minimum_location.png", A3F,
     "where the corrected minimum now sits", "MINIMUM_MARKER"),
    ("corrected_minimum_cross_section.png", A3F,
     "a true section through the corrected minimum", "SECTION"),
    ("analytical_vs_ray_corrected.png", A3F,
     "analytical against ray measurement on the corrected geometry",
     "METHOD_COMPARISON"),
    ("A3_vs_A3F_thickness_comparison.png", A3F,
     "the failed and corrected thickness fields side by side",
     "COMPARISON"),
    ("corrected_thickness_map.png", A3F, "the corrected thickness field",
     "THICKNESS_MAP"),
    ("corrected_thickness_histogram.png", A3F,
     "the corrected thickness distribution", "HISTOGRAM"),
    ("corrected_sink_risk_map.png", A3F, "moulding sink risk",
     "RISK_MAP"),
    ("corrected_warpage_risk_map.png", A3F, "moulding warpage risk",
     "RISK_MAP"),

    # --- 12 A3M ---------------------------------------------------------
    ("maximum_location_top.png", A3M,
     "where the reported maximum sits, from above", "MAXIMUM_MARKER"),
    ("maximum_location_underside.png", A3M,
     "the same location from the underside", "MAXIMUM_MARKER"),
    ("maximum_location_wireframe.png", A3M,
     "the maximum against the mesh topology", "WIREFRAME"),
    ("maximum_location_normals.png", A3M,
     "the source and opposing normals at the maximum", "NORMALS"),
    ("maximum_controlling_face_pair.png", A3M,
     "the face pair the ray actually connected", "FACE_PAIR"),
    ("maximum_cross_section_primary.png", A3M,
     "a true section through the maximum", "SECTION"),
    ("maximum_cross_section_orthogonal.png", A3M,
     "the orthogonal section through the same point", "SECTION"),
    ("maximum_candidate_intersections.png", A3M,
     "every candidate intersection, not only the selected hit",
     "CANDIDATES"),
    ("maximum_method_comparison.png", A3M,
     "the three independent methods at the maximum",
     "METHOD_COMPARISON"),
    ("maximum_convergence_plot.png", A3M,
     "adaptive convergence around the maximum", "CONVERGENCE"),
    ("local_wall_vs_long_path_diagram.png", A3M,
     "why 11.83 mm is a long material path and not a local wall",
     "DEFINITION_DIAGRAM"),
    ("below_1_20_region_map.png", A3M,
     "every region below the 1.20 mm target, classified", "REGION_MAP"),
)

COUNTS = {A3R: 13, A3F: 16, A3M: 12}
TOTAL = sum(COUNTS.values())

assert len(REQUIRED) == TOTAL == 41, "manifest must hold exactly 41 entries"
for _m, _n in COUNTS.items():
    assert sum(1 for r in REQUIRED if r[1] == _m) == _n, _m
assert len({r[0] for r in REQUIRED}) == TOTAL, "filenames must be unique"

#: The eight conditions the directive says must FAIL the package.
FAILURE_CONDITIONS = (
    "IMAGE_ABSENT",
    "FILENAME_NOT_IN_MANIFEST",
    "WRONG_SOURCE_GEOMETRY",
    "HISTORICAL_PRESENTED_AS_CURRENT",
    "REQUIRED_LABEL_MISSING",
    "PIXEL_HASH_MISSING",
    "EVIDENCE_VISUALLY_BLANK",
    "REQUIRED_FEATURE_NOT_EXPOSED",
)


def required_manifest() -> dict:
    """The authoritative list, as a durable record."""
    return {
        "record_type": SCHEMA,
        "total_required": TOTAL,
        "counts": dict(COUNTS),
        "source": "transcribed verbatim from the approved owner directives "
                  "that authorized PALT-M4B-A3F and PALT-M4B-A3M",
        "corrects": "a previous checkpoint recorded these names as "
                    "NOT_ENUMERATED_IN_REPOSITORY. That was wrong — the "
                    "directives name every file.",
        "geometry_binding": {k: dict(v) for k, v in
                             GEOMETRY_BINDING.items()},
        "required_labels": {k: list(v) for k, v in REQUIRED_LABELS.items()},
        "failure_conditions": list(FAILURE_CONDITIONS),
        "entries": [
            {"filename": n, "milestone": m, "purpose": p,
             "required_feature": f,
             "source_geometry_identity":
                 GEOMETRY_BINDING[m]["mesh_geometry_identity"],
             "status": GEOMETRY_BINDING[m]["status"],
             "required_labels": list(REQUIRED_LABELS[m])}
            for n, m, p, f in REQUIRED],
    }


def entries_for(milestone: str):
    return [r for r in REQUIRED if r[1] == milestone]
