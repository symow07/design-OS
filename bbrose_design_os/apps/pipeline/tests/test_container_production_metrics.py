"""Phase 2B-3C §11-§14 — coverage, registration, complete colour count, density.

Coverage is measured per method/zone against the permitted maximum; the
complete colour count includes spot inks + underbase (not just process hexes)
and excludes technical guides; registration returns REVIEW_REQUIRED when
registered separations interact and manufacturer capability is unverified
(never a pretended production-safe geometry).
"""
from __future__ import annotations

from apps.ire import container_production_method as pm
from apps.ire import container_production_metrics as met
from apps.ire import container_separations as sepmod
from apps.ire.compose_container import compose_container_graph
from apps.pipeline.services import container_contract as cc
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile,
    build_backbone,
)


def _setup(archetype="bottle", w=40, h=110):
    prof = cc.build_inferred_profile(archetype, estimates={
        "body_width_mm": float(w), "body_height_mm": float(h),
        "cap_width_mm": 20.0, "cap_height_mm": 13.0})
    zones = cc.propose_zones(prof)
    from apps.ire import container_motif as cm
    ms = cm.build_motif_spec({"verified": True,
                              "motif_signature": "powder constellation"},
                             {"fields": {}}, zones, prof)
    bb = build_backbone(ContainerProfile(archetype=archetype, width_mm=w,
                                         height_mm=h))
    doc = compose_container_graph(bb, product_name="Rose Nectar",
                                  name_lines=["Rose Nectar"], zones=zones,
                                  native=True, motif_spec=ms)
    methods = pm.build_production_methods(zones, prof)
    seps = sepmod.build_separations(methods, doc, zones, prof)
    return doc, methods, seps, zones, prof


def test_coverage_measured_per_method_and_zone():
    doc, methods, seps, zones, _ = _setup()
    cov = met.measure_coverage(doc, methods, zones)
    assert cov["per_zone"]
    for e in cov["per_zone"]:
        assert "measured" in e and "permitted" in e


def test_coverage_exceeded_fires_when_over_cap():
    doc, methods, seps, zones, _ = _setup()
    # pin a tiny cap on one method so the emitted artwork exceeds it
    methods["methods"][0]["maximum_coverage"] = 0.01
    cov = met.measure_coverage(doc, methods, zones)
    assert met.MAXIMUM_COVERAGE_EXCEEDED in cov["codes"]


def test_complete_color_count_includes_spots_not_technical():
    doc, methods, seps, zones, _ = _setup()
    cc_rep = met.complete_color_count(methods, seps)
    screen = next(e for e in cc_rep["per_method"]
                  if e["method_type"] == "SCREEN_PRINT")
    # screen counts its spot inks (+ limited-process), never LABEL_* guides
    assert any("SCREEN_INK" in s for s in screen["counted"])
    assert not any("LABEL_" in s for s in screen["counted"])


def test_color_count_exceeded_when_over_limit():
    doc, methods, seps, zones, _ = _setup()
    # CAP_PRINT permits 2; give it a hard 1-colour cap so its spots exceed
    capm = next(m for m in methods["methods"] if m["method_type"] == "CAP_PRINT")
    capm["permitted_color_count"] = 0
    cc_rep = met.complete_color_count(methods, seps)
    assert met.COLOR_COUNT_EXCEEDED in cc_rep["codes"]


def test_registration_reviews_when_capability_unverified():
    doc, methods, seps, zones, _ = _setup()
    # bottle screen front has SCREEN_INK_1 + SCREEN_INK_2 → an interaction
    reg = met.measure_registration(methods, seps)
    assert reg["state"] == "REVIEW_REQUIRED"
    assert met.REGISTRATION_REVIEW_REQUIRED in reg["codes"]


def test_label_density_reports_role_by_surface():
    doc, methods, seps, zones, _ = _setup()
    den = met.measure_label_density(doc, zones, {})
    roles = {e["surface"]: e["role"] for e in den["per_zone"]}
    assert roles.get("BODY_BACK") == "back"      # regulatory role, not hero
    assert roles.get("BODY_FRONT") == "front"


def test_build_production_metrics_aggregates():
    doc, methods, seps, zones, _ = _setup()
    m = met.build_production_metrics(doc, methods, seps, zones, {})
    assert m["schema_version"] == "container_production_metrics/1.0"
    assert "coverage" in m and "registration" in m and "color_count" in m
    assert met.REGISTRATION_REVIEW_REQUIRED in m["codes"]
