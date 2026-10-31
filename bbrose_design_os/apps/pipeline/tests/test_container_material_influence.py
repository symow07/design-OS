"""Phase 2B-3C §15-§17 — influence plan/1.1, per-reference attribution,
similarity risk.

Each reference claims only the dimensions its metadata supports (a palette
reference does not claim cap orientation); distinct references therefore get
distinct realization records. A load-bearing claim with no emitted evidence
fails; a reference that realizes many dimensions flags similarity review.
"""
from __future__ import annotations

from apps.ire.compose_container import compose_container_graph
from apps.ire.graph import Document, Group
from apps.pipeline.services import container_material_influence as cmi
from apps.pipeline.services import container_contract as cc
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile,
    build_backbone,
)


class _Row:
    def __init__(self, pk, title, description=""):
        self.pk = pk
        self.library_item_id = f"materials:{title}"
        self.title = title
        self.description = description
        self.permission_status = "USER_APPROVED_FOR_CONCEPT_REFERENCE"


class _Task:
    pk = 3


def _doc(motif=True):
    prof = cc.build_inferred_profile("bottle", estimates={
        "body_width_mm": 40.0, "body_height_mm": 110.0})
    zones = cc.propose_zones(prof)
    ms = None
    if motif:
        from apps.ire import container_motif as cm
        ms = cm.build_motif_spec({"verified": True,
                                  "motif_signature": "powder constellation"},
                                 {"fields": {}}, zones, prof)
    bb = build_backbone(ContainerProfile(archetype="bottle", width_mm=40,
                                         height_mm=110))
    return compose_container_graph(bb, product_name="Rose Nectar",
                                   name_lines=["Rose Nectar"], zones=zones,
                                   native=True, motif_spec=ms)


def test_references_claim_only_supported_dimensions():
    palette_ref = _Row(1, "blush gold palette")
    motif_ref = _Row(2, "floral botanical pattern")
    plan = cmi.build_container_influence_plan(_Task(), [palette_ref, motif_ref])
    claims = {r["reference_id"]: r["claimed_dimensions"] for r in plan["references"]}
    assert "palette" in claims[1] and "motif" not in claims[1]
    assert "motif" in claims[2]
    assert plan["schema_version"] == "material_influence_plan/1.1"


def test_distinct_references_get_distinct_realizations():
    palette_ref = _Row(1, "blush gold palette")
    motif_ref = _Row(2, "floral botanical pattern")
    plan = cmi.build_container_influence_plan(_Task(), [palette_ref, motif_ref])
    rep = cmi.build_container_realization(_Task(), _doc(motif=True), plan)
    r1 = next(r for r in rep["references"] if r["reference_id"] == 1)
    r2 = next(r for r in rep["references"] if r["reference_id"] == 2)
    assert r1["dimensions"] != r2["dimensions"]        # NOT identical (§16)
    assert "palette" in r1["dimensions"]
    assert r1["dimensions"]["palette"]["status"] == cmi.REALIZED


def test_load_bearing_claim_without_evidence_not_realized():
    typ_ref = _Row(5, "editorial condensed typography")
    plan = cmi.build_container_influence_plan(_Task(), [typ_ref])
    empty = Document(page_w=210, page_h=297,
                     root=Group(name="Artwork", role="artwork", children=[]))
    rep = cmi.build_container_realization(_Task(), empty, plan)
    assert rep["references"][0]["dimensions"]["typography"]["status"] == \
        cmi.NOT_REALIZED
    assert cmi.NOT_REALIZED_CODE in rep["codes"]


def test_similarity_review_flags_over_claiming_reference():
    # one reference claiming many dimensions that all realize → similarity risk
    big = _Row(9, "floral gold logo cap wrap editorial pattern palette front back")
    plan = cmi.build_container_influence_plan(_Task(), [big])
    rep = cmi.build_container_realization(_Task(), _doc(motif=True), plan)
    sim = cmi.similarity_risk(rep, threshold=3)
    assert 9 in sim["flagged_reference_ids"]
    assert cmi.SIMILARITY_REVIEW in sim["codes"]


def test_no_approved_references_is_not_applicable():
    rep = cmi.not_applicable_realization(_Task())
    assert rep["state"] == "NO_APPROVED_REFERENCES" and rep["codes"] == []
