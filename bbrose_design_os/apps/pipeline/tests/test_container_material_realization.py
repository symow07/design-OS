"""Phase 2B-3A §5 — material-influence realization.

Maps each approved reference's claimed influence to an emitted manifestation.
REALIZED only when tied to a concrete emitted swatch/text/group; NOT_REALIZED
only for a specific claim the doc demonstrably lacks; finish/texture
NOT_APPLICABLE (deferred to 2B-3B); NOT_APPLICABLE overall when there are no
approved references. The report is locator-free.
"""
from __future__ import annotations

from apps.ire.compose_container import compose_container_graph
from apps.ire.graph import Document, Group
from apps.pipeline.services import container_contract as cc
from apps.pipeline.services import container_material_realization as cmr
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile,
    build_backbone,
)


def _doc(motif=False):
    bb = build_backbone(ContainerProfile(archetype="bottle", height_mm=110,
                                         width_mm=40))
    zones = cc.propose_zones(cc.build_inferred_profile("bottle"))
    motif_spec = None
    if motif:
        from apps.ire import container_motif as cm
        motif_spec = cm.build_motif_spec(
            {"verified": True, "motif_signature": "powder constellation"},
            {"fields": {}}, zones, None)
    return compose_container_graph(bb, product_name="Rose Nectar",
                                   name_lines=["Rose Nectar"], zones=zones,
                                   native=True, motif_spec=motif_spec)


class _T:                       # minimal task stand-in (pk only)
    pk = 7


_PLAN = {
    "schema_version": "material_influence_plan/1.0", "plan_hash": "abc123",
    "references": [{"reference_id": 11, "library_item_id": "rose_pattern",
                    "permission": "USER_APPROVED_FOR_CONCEPT_REFERENCE"}]}


def test_no_approved_references_is_not_applicable():
    rep = cmr.not_applicable_realization(_T())
    assert rep["state"] == "NO_APPROVED_REFERENCES"
    assert rep["references"] == [] and rep["codes"] == []


def test_realized_when_emitted_manifestations_exist():
    rep = cmr.build_realization(_T(), _doc(motif=True), _PLAN)
    inf = rep["references"][0]["influences"]
    assert inf["palette"]["status"] == cmr.REALIZED          # named swatches
    assert inf["typography"]["status"] == cmr.REALIZED       # live text
    assert inf["motif"]["status"] == cmr.REALIZED            # motif group
    assert inf["texture"]["status"] == cmr.NOT_APPLICABLE    # deferred 2B-3B
    assert inf["finishing"]["status"] == cmr.NOT_APPLICABLE
    assert inf["composition"]["status"] == cmr.REVIEW_REQUIRED
    assert rep["codes"] == []                                # nothing missing
    assert rep["influence_plan_hash"] == "abc123"


def test_motif_absent_is_review_not_failure():
    # a first-pass (no motif) concept: motif is principle-level → REVIEW, not
    # a NOT_REALIZED failure
    rep = cmr.build_realization(_T(), _doc(motif=False), _PLAN)
    assert rep["references"][0]["influences"]["motif"]["status"] == \
        cmr.REVIEW_REQUIRED
    assert rep["codes"] == []


def test_missing_live_text_is_not_realized():
    empty = Document(page_w=210, page_h=297,
                     root=Group(name="Artwork", role="artwork", children=[]))
    rep = cmr.build_realization(_T(), empty, _PLAN)
    assert rep["references"][0]["influences"]["typography"]["status"] == \
        cmr.NOT_REALIZED
    assert cmr.MATERIAL_INFLUENCE_NOT_REALIZED in rep["codes"]


def test_report_is_locator_free():
    # a plan/report carrying a file path must raise, not ship
    import pytest
    bad = dict(_PLAN)
    bad["references"] = [{"reference_id": 1,
                          "library_item_id": "materials/rose.png"}]
    with pytest.raises(AssertionError):
        cmr.build_realization(_T(), _doc(), bad)
