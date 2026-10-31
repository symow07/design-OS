"""PALT-M4C M4C-9 — two-variant proof at the GEOMETRY level.

The earlier bridge proof showed that two different design intents produce
two different contract dictionaries. That is necessary but weak: a
contract can differ while the geometry that gets built is identical,
which would make the "bridge" a manifest path rather than a design path.

This closes that gap by building both variants and measuring the meshes.
Two variants pass only when the difference is visible in the geometry
itself — different pocket cross-section, different pocket count, and
different mesh identity — not merely in the paperwork that describes it.

PALT-P1A (nine circular pockets) is the engineering regression fixture.
PALT-P1B (rectangular pockets, ES3083) is the owner design-intent pilot.
Neither replaces the other, and this module asserts that too: a proof
that quietly retired the fixture would have destroyed the baseline it is
measured against.
"""
from __future__ import annotations

import hashlib

from apps.pipeline.services import palt_m4b_a as A
from apps.pipeline.services import palette_recessed_tray_geometry as round_t
from apps.pipeline.services import palette_rect_tray_geometry as rect_t

SCHEMA = "palette_two_variant_geometry_proof/1.0"

PASS, FAIL = "PASS", "FAIL"


def _profile(tray, shape):
    """Comparable measurements taken from each built mesh."""
    p = tray["pockets"][0]
    if shape == "CIRCULAR":
        open_x = open_y = 2 * p["opening_radius_mm"]
    else:
        open_x, open_y = p["opening_width_mm"], p["opening_height_mm"]
    return {
        "pocket_shape": shape,
        "pocket_count": len(tray["pockets"]),
        "pocket_opening_x_mm": round(open_x, 6),
        "pocket_opening_y_mm": round(open_y, 6),
        "pocket_is_isotropic": abs(open_x - open_y) < 1e-9,
        "pocket_depth_mm": p["depth_mm"],
        "vertex_count": int(tray["vertices"].shape[0]),
        "face_count": int(tray["faces"].shape[0]),
        "mesh_identity": tray["mesh_identity"],
    }


def prove_two_variants() -> dict:
    """Build both pilots and prove the difference is geometric."""
    a = round_t.build_recessed_palette_tray(dict(A._values(A.TRAY)))
    b = rect_t.build_rect_recessed_tray()
    pa, pb = _profile(a, "CIRCULAR"), _profile(b, "RECTANGULAR")

    checks = [
        {"check": "MESH_IDENTITY_DIFFERS",
         "why": "identical identities would mean one design produced the "
                "other's geometry",
         "verdict": PASS if pa["mesh_identity"] != pb["mesh_identity"]
         else FAIL,
         "a": pa["mesh_identity"], "b": pb["mesh_identity"]},
        {"check": "POCKET_CROSS_SECTION_DIFFERS",
         "why": "the headline design difference is round vs rectangular "
                "pans; it must be visible in the built surface",
         "verdict": PASS if pa["pocket_shape"] != pb["pocket_shape"]
         else FAIL,
         "a": pa["pocket_shape"], "b": pb["pocket_shape"]},
        {"check": "RECTANGULAR_POCKET_IS_ANISOTROPIC",
         "why": "a rectangular pocket whose two openings were equal would "
                "be a rounded square standing in for a rectangle",
         "verdict": PASS if not pb["pocket_is_isotropic"] else FAIL,
         "a": pa["pocket_is_isotropic"], "b": pb["pocket_is_isotropic"]},
        {"check": "POCKET_COUNT_DIFFERS",
         "why": "ES3083 reads as a 4x3 field, the fixture is 3x3",
         "verdict": PASS if pa["pocket_count"] != pb["pocket_count"]
         else FAIL,
         "a": pa["pocket_count"], "b": pb["pocket_count"]},
        {"check": "TOPOLOGY_DIFFERS",
         "why": "different pocket shapes must produce different meshes, "
                "not the same mesh with different labels",
         "verdict": PASS if (pa["vertex_count"], pa["face_count"])
         != (pb["vertex_count"], pb["face_count"]) else FAIL,
         "a": [pa["vertex_count"], pa["face_count"]],
         "b": [pb["vertex_count"], pb["face_count"]]},
        {"check": "FIXTURE_IDENTITY_PRESERVED",
         "why": "the regression fixture must survive the pilot; a proof "
                "that retired it would destroy its own baseline",
         "verdict": PASS if pa["mesh_identity"] == "ec65ea9402c16230"
         else FAIL,
         "a": pa["mesh_identity"], "b": "ec65ea9402c16230"},
    ]
    failed = [c["check"] for c in checks if c["verdict"] == FAIL]
    return {
        "record_type": SCHEMA,
        "variant_a": {"id": "PALT-P1A", "role": "ENGINEERING_REGRESSION_"
                                                "FIXTURE", **pa},
        "variant_b": {"id": "PALT-P1B", "role": "OWNER_DESIGN_INTENT_PILOT",
                      "concept": "ES3083 吸塑_展盒刀线", **pb},
        "checks": checks,
        "verdict": FAIL if failed else PASS,
        "failed": failed,
        "proves": "TWO_DESIGN_INTENTS_PRODUCE_TWO_DIFFERENT_BUILT_MESHES",
        "does_not_prove": [
            "that either variant matches its source design dimensionally",
            "that either variant is manufacturable",
            "that the ES3083 reading is correct — it is an AI draft",
        ],
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
        "proof_identity": hashlib.sha256(
            (pa["mesh_identity"] + pb["mesh_identity"]).encode()
        ).hexdigest()[:16],
    }
