"""Phase 2B-3V-CORR-3 — selected container concept visual fidelity.

Task #51's Gate-2 output rendered the selected Dewdrop Constellation as
diagonal ruled lines: build_motif_spec took rendered_via from a SECOND
whole-text lexical vote (three substring hits of "line/rule/graphic" outvoted
seven occurrences of "constellation") instead of the family→language map, and
the fidelity gate validated rendered-vs-rendered labels. These tests pin the
correction. No provider call anywhere."""
from __future__ import annotations

import random

from apps.ire import container_motif as cm
from apps.ire import container_motif_fidelity as cmf
from apps.ire import design_language as dl
from apps.ire.compose_container import compose_container_graph
from apps.pipeline.services import container_contract as cc
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile,
    build_backbone,
)

_C_STRUCT = {
    "verified": True, "variation_id": "C_DEWDROP_CONSTELLATION",
    "title": "Dewdrop Constellation",
    "motif_signature": ("22-30 isolated closed Bézier dewdrop forms in three "
                        "size classes arcing from the lower-left edge to an "
                        "upper-right density peak"),
    "composition_signature": "asymmetric diagonal, flush-left editorial stack",
    "decorative_coverage_pct": 20,
}


def _zones():
    rec = cc.build_inferred_profile("bottle", "slim", estimates={
        "body_width_mm": 35.0, "body_height_mm": 95.0, "body_depth_mm": 25.0})
    return cc.propose_zones(rec), rec


def _doc(motif_spec, transparency=None):
    zones, _ = _zones()
    bb = build_backbone(ContainerProfile(archetype="bottle", width_mm=35,
                                         height_mm=95))
    return compose_container_graph(
        bb, product_name="Rosé Nectar", name_lines=["Rosé Nectar"],
        zones=zones, native=True, motif_spec=motif_spec,
        transparency=transparency)


# --- §2 resolver -------------------------------------------------------------

def test_dewdrop_signature_classifies_and_routes_to_dewdrop_generator():
    zones, rec = _zones()
    spec = cm.build_motif_spec(_C_STRUCT, {"fields": {}}, zones, rec)
    assert spec["requested_family"] == "DEWDROP_CONSTELLATION"
    assert spec["rendered_via"] == "dewdrop_constellation"
    assert spec["reconstruction_capability"] == cm.CAP_SUPPORTED


def test_powder_constellation_can_never_resolve_to_ruled_field():
    assert cm._FAMILY_TO_LANGUAGE["POWDER_CONSTELLATION"] == \
        "powder_constellation"
    assert cm._FAMILY_TO_LANGUAGE["DEWDROP_CONSTELLATION"] == \
        "dewdrop_constellation"
    # a signature drowning in editorial vocabulary still routes by family
    noisy = dict(_C_STRUCT)
    noisy["composition_signature"] = ("editorial rule line graphic grid "
                                      "stripe pinstripe")
    zones, rec = _zones()
    spec = cm.build_motif_spec(noisy, {"fields": {}}, zones, rec)
    assert spec["rendered_via"] != "ruled_field"


def test_unclassifiable_signature_fails_closed_not_substituted():
    zones, rec = _zones()
    spec = cm.build_motif_spec(
        {"verified": True, "variation_id": "X",
         "motif_signature": "iridescent holographic prism refraction"},
        {"fields": {}}, zones, rec)
    assert spec["reconstruction_capability"] == cm.CAP_REVIEW_REQUIRED
    assert spec.get("review_code") == cm.VECTOR_RECONSTRUCTION_REVIEW_REQUIRED


# --- §3 generator ------------------------------------------------------------

def test_dewdrop_generator_emits_droplet_geometry():
    lang = dl.get_language("dewdrop_constellation")
    params = dl.LanguageParameters(swatches=dl.DEWDROP_CONSTELLATION_SWATCHES,
                                   density=1.0)
    groups = lang.generators[0]((0, 0, 24.5, 57.0), params,
                                random.Random(51), lambda x: x, lambda y: y)
    names = {g.name for g in groups}
    assert {"dewdrop-core", "dewdrop-drift", "dewdrop-highlights"} <= names
    all_nodes = [n for g in groups for n in g.children]
    kinds = [str(n.name).rsplit("-", 1)[-1] for n in all_nodes]
    assert any(k == "teardrop" for k in kinds)       # droplet-like, not circles
    assert any(k in ("bead", "elongated") for k in kinds)
    assert not any("rule" in str(n.name) for n in all_nodes)


# --- §8/§11 fidelity ---------------------------------------------------------

def test_dewdrop_document_passes_strengthened_fidelity():
    zones, rec = _zones()
    spec = cm.build_motif_spec(_C_STRUCT, {"fields": {}}, zones, rec)
    doc = _doc(spec)
    mf = cmf.validate_motif_fidelity(doc, spec)
    # §BH50(f)(5): the family, density, scale and position are measured and
    # pass; coverage and continuation are unmeasured, and a pass never
    # outvotes them — this line asserted MEASURED_PASS until the ruling
    assert mf["overall"] == "UNMEASURED_BLOCKING", mf["failures"]
    assert mf["failures"] == []
    for axis in ("motif_family", "motif_density", "motif_scale",
                 "motif_position"):
        assert mf["axes"][axis]["state"] == "MEASURED_PASS", axis
    census = cmf.dewdrop_census(doc)
    assert census["droplet_count"] >= 8
    assert census["core_mean_y"] < census["drift_mean_y"]   # dense above sparse


def test_ruled_lines_fail_dewdrop_family_fidelity():
    # a spec whose family is DEWDROP but whose emitted geometry is a ruled
    # field (the rejected output's shape) MUST fail on geometry
    zones, rec = _zones()
    spec = cm.build_motif_spec(_C_STRUCT, {"fields": {}}, zones, rec)
    forged = dict(spec, rendered_via="ruled_field")
    from apps.ire.container_motif import language_for_spec
    doc = _doc(forged)          # composes with the ruled_field generator
    mf = cmf.validate_motif_fidelity(doc, forged)
    assert mf["overall"] == "MEASURED_FAIL"
    assert cmf.MOTIF_FAMILY_MISMATCH in mf["failures"] \
        or cmf.MOTIF_MISSING in mf["failures"]
    assert cmf.SELECTED_CONCEPT_FIDELITY_FAILED in mf["failures"]
    assert language_for_spec(forged) is not None    # it really rendered ruled


def test_missing_droplets_fail():
    zones, rec = _zones()
    spec = cm.build_motif_spec(_C_STRUCT, {"fields": {}}, zones, rec)
    doc = _doc(dict(spec, rendered_via="quiet_ground"))   # no droplets emitted
    mf = cmf.validate_motif_fidelity(doc, spec if False else dict(
        spec, rendered_via="quiet_ground"))
    assert mf["overall"] == "MEASURED_FAIL"


# --- §6 transparency ---------------------------------------------------------

def test_transparent_body_is_separate_from_product_fill():
    zones, rec = _zones()
    spec = cm.build_motif_spec(_C_STRUCT, {"fields": {}}, zones, rec)
    doc = _doc(spec, transparency={"state": "TRANSPARENT",
                                   "product_color": "#F2C4CE"})
    names = [str(n.name) for n, _ in doc.walk()]
    assert "body-transparent-wall" in names
    assert "product-peach-rose-fill" in names
    assert "body" not in names                       # no opaque collapse
    # named swatch registry present
    joined = " ".join(names)
    for sw in ("container_transparent_body", "product_peach_rose_fill",
               "cap_blush", "dewdrop_clear", "spot_uv_dewdrops"):
        assert f"swatch-{sw}" in joined


def test_opaque_composition_unchanged_without_transparency():
    zones, rec = _zones()
    spec = cm.build_motif_spec(_C_STRUCT, {"fields": {}}, zones, rec)
    doc = _doc(spec)                                  # no transparency param
    names = [str(n.name) for n, _ in doc.walk()]
    assert "body" in names and "body-transparent-wall" not in names


# --- §7 typography -----------------------------------------------------------

def test_typography_hierarchy_gate():
    zones, rec = _zones()
    spec = cm.build_motif_spec(_C_STRUCT, {"fields": {}}, zones, rec)
    doc = _doc(spec)
    rep = cmf.validate_typography_hierarchy(doc, "Rosé Nectar")
    assert rep["overall"] == "MEASURED_PASS", rep["failures"]
    # a document with no product name fails, not passes-by-existence
    rep2 = cmf.validate_typography_hierarchy(doc, "Nonexistent Product")
    assert rep2["overall"] == "MEASURED_FAIL"
    assert cmf.TYPOGRAPHY_HIERARCHY_FAILED in rep2["failures"]
    assert cmf.SELECTED_CONCEPT_FIDELITY_FAILED in rep2["failures"]


# --- census sanity -----------------------------------------------------------

def test_no_decorative_rasters_in_dewdrop_document():
    from apps.ire.compose_container import container_design_graph_record
    zones, rec = _zones()
    spec = cm.build_motif_spec(_C_STRUCT, {"fields": {}}, zones, rec)
    doc = _doc(spec, transparency={"state": "TRANSPARENT"})
    census = container_design_graph_record(doc, zones_consumed=[],
                                           mode="native")
    assert census["decorative_raster_count"] == 0
    assert census["primitives"]["live_text"] >= 1
