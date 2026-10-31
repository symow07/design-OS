"""Phase 2B-2 slice 5 — bottle/jar/tube native golden fixtures (§14).

Runs the full native pipeline end to end (no DB, no provider) and asserts the
frozen deterministic result for each archetype: zero decorative rasters, live
text present, all placements contained, deterministic projection + hashes, and
a three-state fidelity of MEASURED_PASS. A drift here means the native
reconstruction changed and the fixture must be reviewed, not silently updated.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.ire import container_fidelity as cf
from apps.ire.compose_container import (
    compose_container_graph,
    container_design_graph_record,
)
from apps.pipeline.services import container_contract as cc
from apps.pipeline.services import container_projection as cp
from apps.pipeline.services import container_visual_graph as cvg
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile,
    build_backbone,
)

pytest.importorskip("fitz")

_GOLDEN = json.loads(
    (Path(__file__).parent / "fixtures" / "container_native_golden.json").read_text())
_ARCHES = ("bottle", "jar", "tube")

# first-pass concept: no structured record → record-only axes are UNMEASURED
_VG = {"schema_version": cvg.SCHEMA, "fields": {
    "logo_zone": {"value": None, "verification": cc.MISSING},
    "product_name_zone": {"value": None, "verification": cc.MISSING},
    "motif_family": {"value": None, "verification": cc.MISSING}}}


def _run(name):
    g = _GOLDEN[name]
    prof = cc.build_inferred_profile(g["archetype"], estimates={
        "body_width_mm": float(g["width_mm"]),
        "body_height_mm": float(g["height_mm"])})
    zones = cc.propose_zones(prof)
    bb = build_backbone(ContainerProfile(
        archetype=g["archetype"], width_mm=g["width_mm"],
        height_mm=g["height_mm"]))
    doc = compose_container_graph(bb, product_name="Rose Nectar",
                                  name_lines=["Rose Nectar"], zones=zones,
                                  native=True)
    census = container_design_graph_record(
        doc, zones_consumed=[z["zone_id"] for z in zones], mode="native")
    proj = cp.project_zones(zones, prof)
    cont = cp.validate_zone_containment(
        doc.metadata.get("placements") or [], zones, prof)
    fid = cf.measure_fidelity(doc, _VG, name_lines=["Rose Nectar"],
                              census=census["primitives"])
    return prof, zones, census, proj, cont, fid


@pytest.mark.parametrize("name", _ARCHES)
def test_native_golden(name):
    g = _GOLDEN[name]
    prof, zones, census, proj, cont, fid = _run(name)
    # deterministic identity
    assert prof["profile_hash"] == g["profile_hash"]
    assert cc.zone_set_hash(zones) == g["zone_set_hash"]
    # native reconstruction census — ZERO decorative rasters, live text present
    assert census["mode"] == "native"
    assert census["decorative_raster_count"] == 0
    assert census["primitives"]["live_text"] == g["census"]["live_text"]
    assert census["primitives"]["vector_paths"] == g["census"]["vector_paths"]
    # multi-surface emission (§5): every confirmed non-front surface got a group
    assert census["surface_groups"] == g["surface_groups"]
    # projection deterministic + never review-required for the confirmed set
    assert proj["review_required"] is False
    assert sorted({z["method"] for z in proj["zones"]}) == g["projection_methods"]
    # every placement contained
    assert cont == []
    # three-state fidelity: name present, record-only axes UNMEASURED, no fail
    assert fid["overall"] == g["fidelity_overall"]
    assert fid["failures"] == []
    assert fid["counts"]["unmeasured"] >= 3


@pytest.mark.parametrize("name", _ARCHES)
def test_native_golden_is_reproducible(name):
    a = _run(name)
    b = _run(name)
    assert a[2] == b[2]        # census identical
    assert a[3] == b[3]        # projection identical
    assert a[5] == b[5]        # fidelity identical


def _run_motif(name):
    from apps.ire import container_motif as cm
    from apps.ire import container_motif_fidelity as cmf
    g = _GOLDEN[name]
    mg = g["motif"]
    prof = cc.build_inferred_profile(g["archetype"], estimates={
        "body_width_mm": float(g["width_mm"]),
        "body_height_mm": float(g["height_mm"])})
    zones = cc.propose_zones(prof)
    structured = {"verified": True, "variation_id": "v",
                  "motif_signature": mg["signature"]}
    motif_spec = cm.build_motif_spec(structured, {"fields": {}}, zones, prof)
    bb = build_backbone(ContainerProfile(
        archetype=g["archetype"], width_mm=g["width_mm"],
        height_mm=g["height_mm"]))
    doc = compose_container_graph(bb, product_name="Rose Nectar",
                                  name_lines=["Rose Nectar"], zones=zones,
                                  native=True, motif_spec=motif_spec)
    census = container_design_graph_record(doc, zones_consumed=[], mode="native")
    cont = cp.validate_zone_containment(
        doc.metadata.get("placements") or [], zones, prof)
    mf = cmf.validate_motif_fidelity(doc, motif_spec)
    return motif_spec, census, cont, mf


@pytest.mark.parametrize("name", _ARCHES)
def test_native_golden_motif(name):
    """§13: each archetype reconstructs its recognized motif natively —
    family preserved, zero decorative rasters, contained, fidelity passes."""
    g = _GOLDEN[name]
    mg = g["motif"]
    motif_spec, census, cont, mf = _run_motif(name)
    assert motif_spec["rendered_via"] == mg["rendered_via"]     # family preserved
    assert census["motif_groups"] == mg["motif_groups"]         # emitted natively
    assert census["primitives"]["vector_paths"] == mg["vector_paths"]
    assert census["decorative_raster_count"] == 0               # zero rasters
    assert cont == []                                           # contained
    assert mf["overall"] == mg["motif_fidelity"] and mf["failures"] == []
    assert census["primitives"]["live_text"] >= 1               # live text kept


@pytest.mark.parametrize("name", _ARCHES)
def test_native_golden_motif_is_reproducible(name):
    a = _run_motif(name)
    b = _run_motif(name)
    assert a[1] == b[1] and a[3] == b[3]     # census + motif fidelity identical


def _motif_setup(name):
    """(profile, zones, emitted motif doc) for an archetype's golden motif."""
    from apps.ire import container_motif as cm
    g = _GOLDEN[name]
    prof = cc.build_inferred_profile(g["archetype"], estimates={
        "body_width_mm": float(g["width_mm"]),
        "body_height_mm": float(g["height_mm"])})
    zones = cc.propose_zones(prof)
    motif_spec = cm.build_motif_spec(
        {"verified": True, "motif_signature": g["motif"]["signature"]},
        {"fields": {}}, zones, prof)
    bb = build_backbone(ContainerProfile(
        archetype=g["archetype"], width_mm=g["width_mm"], height_mm=g["height_mm"]))
    doc = compose_container_graph(bb, product_name="Rose Nectar",
                                  name_lines=["Rose Nectar"], zones=zones,
                                  native=True, motif_spec=motif_spec)
    return prof, zones, doc


@pytest.mark.parametrize("name", _ARCHES)
def test_native_golden_wrap_geometry(name):
    """§7-§10 (2B-3C): deterministic true-wrap production geometry per
    archetype — frozen wrap-set hash + surfaces, no projection review."""
    from apps.ire import container_wrap_geometry as wgmod
    g, p = _GOLDEN[name], _GOLDEN[name]["production"]
    prof = cc.build_inferred_profile(g["archetype"], estimates={
        "body_width_mm": float(g["width_mm"]),
        "body_height_mm": float(g["height_mm"])})
    zones = cc.propose_zones(prof)
    geo = wgmod.build_wrap_geometry(zones, prof)
    assert geo["wrap_set_hash"] == p["wrap_set_hash"]
    assert sorted(w["surface"] for w in geo["wraps"]) == p["wrap_surfaces"]
    assert geo["review_required"] is False


def test_2b3c_coverage_target_miss_fires_and_blocks_readiness():
    """§3 (2B-3C): a VERIFIED coverage target the emission misses is a real
    MEASURED_FAIL → production-readiness finding (not a reconstruction blocker)."""
    from apps.ire import container_motif as cm
    from apps.ire import container_quant_fidelity as qf
    prof, zones, doc = _motif_setup("bottle")
    ms = cm.build_motif_spec({"verified": True,
                              "motif_signature": "powder constellation"},
                             {"fields": {}}, zones, prof)
    vg = {"fields": {"decoration_coverage": {"value": 90, "verification": "VERIFIED"}}}
    rep = qf.measure_quantitative_fidelity(doc, vg, ms)
    assert qf.MOTIF_COVERAGE_FAILED in rep["failures"]


def test_2b3c_distinct_reference_attribution():
    """§16 (2B-3C): references claiming different dimensions get different
    realization records (not the 2B-3A shared-verdict model)."""
    from apps.pipeline.services import container_material_influence as cmi

    class _R:
        def __init__(self, pk, title):
            self.pk = pk
            self.library_item_id = f"materials:{title}"
            self.title = title
            self.description = ""
            self.permission_status = "USER_APPROVED_FOR_CONCEPT_REFERENCE"

    class _T:
        pk = 1
    _, _, doc = _motif_setup("bottle")
    plan = cmi.build_container_influence_plan(
        _T(), [_R(1, "blush gold palette"), _R(2, "floral botanical motif")])
    rep = cmi.build_container_realization(_T(), doc, plan)
    r1 = next(r for r in rep["references"] if r["reference_id"] == 1)
    r2 = next(r for r in rep["references"] if r["reference_id"] == 2)
    assert r1["dimensions"] != r2["dimensions"]


@pytest.mark.parametrize("name", _ARCHES)
def test_native_golden_production(name):
    """§16: deterministic production methods + separations per archetype —
    method/separation hashes frozen, authority UNVERIFIED, underbase REVIEW,
    zero decorative rasters."""
    from apps.ire import container_production_method as pm
    from apps.ire import container_separations as sepmod
    p = _GOLDEN[name]["production"]
    prof, zones, doc = _motif_setup(name)
    methods = pm.build_production_methods(zones, prof)
    assert sorted(m["method_type"] for m in methods["methods"]) == p["method_types"]
    assert methods["method_set_hash"] == p["method_set_hash"]
    assert methods["all_manufacturer_verified"] is False       # UNVERIFIED
    val = pm.validate_production_methods(methods, zones, prof, doc)
    assert "CONTAINER_TECHNIQUE_UNVERIFIED" in val["codes"]     # gate blocked
    seps = sepmod.build_separations(methods, doc, zones, prof)
    assert seps["separation_set_hash"] == p["separation_set_hash"]
    assert sorted({s["name"] for s in seps["separations"]}) == p["separation_names"]
    assert seps["white_underbase"]["state"] == p["underbase_state"]
    assert sepmod.combined_production_hash(methods, seps)
