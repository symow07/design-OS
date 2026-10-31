"""VQ-1-RESET-1B §18 — product-variant requirement, exact referents,
component separation, drawing provenance and the no-geometry boundary."""
import json
import os

import pytest
from django.conf import settings

from apps.pipeline.services import technical_geometry_research as tg

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
R1B = os.path.join(DOCS, "vq1_reset1b")
PACKET = json.load(open(os.path.join(
    R1B, "vq1_technical_geometry_evidence_v2.json")))
SESSION = json.load(open(os.path.join(R1B, "_session.json")))


def _src(url, title, text="", tier=2, cls=None):
    c = cls or tg.page_class(url, title, text)
    return {"source_id": "TS-01", "url": url, "domain": "example.com",
            "title": title, "authority_tier": tier, **c}


class TestSnippetsStayRejected:
    def test_prior_snippet_measurements_remain_rejected(self):
        prior = json.load(open(os.path.join(
            DOCS, "vq1_reset1a", "vq1_geometry_evidence_review.json")))
        for m in prior["section_5_measurements"]["snippet_derived_demoted"]:
            assert m["evidence_class"] == "SNIPPET_NOT_TECHNICAL_EVIDENCE"
            assert m["may_support_concept_geometry"] is False
        assert tg.VQ_SNIPPET_MEASUREMENTS_REJECTED in PACKET["findings"]

    def test_every_source_marks_its_snippet_as_non_evidence(self):
        for s in SESSION["sources"]:
            assert s["snippet_not_evidence"] is True

    def test_extraction_never_uses_a_snippet(self):
        for m in PACKET["section_6_measurements_by_referent"]:
            assert m["extraction_method"] == \
                "GOVERNED_FETCH_EXPLICIT_REFERENT"


class TestProductVariantRequirement:
    def test_generic_marketing_pages_cannot_authorize_dimensions(self):
        for url, title in (
                ("https://x.com/blog/serum-guide", "Serum Bottle Guide"),
                ("https://x.com/wholesale", "Wholesale Manufacturers"),
                ("https://x.com/collection/bottles", "Bottle Collection")):
            c = tg.page_class(url, title)
            assert c["may_authorize_dimensions"] is False
            assert c["page_class"] == "GENERIC_MARKETING_OR_CATEGORY_PAGE"
            assert c["reason"] == tg.VQ_PRODUCT_VARIANT_PAGE_REQUIRED

    def test_marketplace_and_stock_are_disallowed_outright(self):
        for url in ("https://www.amazon.com/dp/B01", "https://pinterest.com/x",
                    "https://www.alibaba.com/p/1"):
            c = tg.page_class(url, "30ml dropper bottle 32 mm")
            assert c["page_class"] == "DISALLOWED_SOURCE_TYPE"
            assert c["may_authorize_dimensions"] is False

    def test_variant_pages_and_technical_documents_may_authorize(self):
        assert tg.page_class(
            "https://x.com/product/glass-bottle-30ml-abc1",
            "30ml bottle")["page_class"] == "PRODUCT_VARIANT_PAGE"
        assert tg.page_class(
            "https://x.com/files/drawing.pdf",
            "Technical drawing")["page_class"] == "TECHNICAL_DOCUMENT"
        assert tg.page_class(
            "https://x.com/p1", "Bottle",
            "dimension specification height diameter capacity "
            "32 mm 78 mm 18 mm")["page_class"] == "DIMENSION_TABLE_PAGE"

    def test_out_of_product_family_sources_are_screened(self):
        r = tg.relevance("A_bottle", "documents.thermofisher.com",
                         "Bottle dimensions", "u")
        assert r["relevant"] is False
        assert "laboratory" in r["relevance_note"]
        r2 = tg.relevance("A_bottle", "www.example.com",
                          "30ml serum dropper bottle", "u")
        assert r2["relevant"] is True


class TestExactReferents:
    def test_referent_must_be_stated_explicitly(self):
        s = _src("https://x.com/files/d.pdf", "Technical drawing")
        assert tg.extract_exact("the product measures 32 mm overall", s,
                                "A_bottle") == []
        got = tg.extract_exact("Body diameter 32 mm", s, "A_bottle")
        assert got and got[0]["component_referent"] == \
            "BODY_OUTSIDE_DIAMETER"

    def test_unit_must_match_the_referent_dimension_family(self):
        s = _src("https://x.com/files/d.pdf", "Technical drawing")
        assert tg.extract_exact("pipette length 30 ml", s, "B_closure") == []
        got = tg.extract_exact("pipette length 78 mm", s, "B_closure")
        assert got and got[0]["component_referent"] == "PIPETTE_LENGTH"
        assert tg.unit_matches_referent("GLASS_WEIGHT", "g") is True
        assert tg.unit_matches_referent("GLASS_WEIGHT", "mm") is False

    def test_bottle_and_closure_referents_never_merge(self):
        assert not set(tg.BOTTLE_REFERENTS) & set(tg.CLOSURE_REFERENTS)
        s = _src("https://x.com/files/d.pdf", "Technical drawing")
        rows = tg.extract_exact(
            "Body diameter 32 mm. Collar diameter 19 mm.", s, "A_bottle")
        comps = {r["component_referent"]: r["component"] for r in rows}
        assert comps["BODY_OUTSIDE_DIAMETER"] == "bottle"
        assert comps["COLLAR_OUTSIDE_DIAMETER"] == "closure"

    def test_total_height_states_closure_inclusion(self):
        s = _src("https://x.com/files/d.pdf", "Technical drawing")
        row = tg.extract_exact("overall height 96 mm", s, "A_bottle")[0]
        assert row["component_referent"] == "TOTAL_HEIGHT_WITH_CLOSURE"
        assert row["closure_included"] is True
        row2 = tg.extract_exact("bottle height without cap 78 mm", s,
                                "A_bottle")[0]
        assert row2["closure_included"] is False

    def test_every_measurement_carries_full_provenance(self):
        for m in PACKET["section_6_measurements_by_referent"]:
            for field in ("raw_source_text", "raw_value", "original_unit",
                          "normalized_value", "normalized_unit",
                          "component_referent", "source_id", "source_url",
                          "product_code", "variant_identity",
                          "closure_included", "source_tier",
                          "extraction_method", "confidence",
                          "verification_state", "conflict_state"):
                assert field in m, field


class TestDrawingsAndConflicts:
    def test_drawings_preserve_page_and_title_block_provenance(self):
        for d in PACKET["all_drawings"]:
            assert d["schema_version"] == "technical_drawing_record/1.0"
            assert d["crop_policy"] == \
                "FULL_PAGE_RENDER_TITLE_BLOCK_PRESERVED"
            assert os.path.exists(d["original_document"])
            assert d["sha256_16"] and d["byte_count"] > 0
            assert "variant_specific" in d and "revision_or_date" in d
            for p in d["pages"]:
                assert p["page_number"] >= 1
                assert p["render_dpi"] >= 150
                assert os.path.exists(p["render"])

    def test_bottle_and_closure_drawings_are_classified_separately(self):
        assert isinstance(PACKET["section_2_bottle_drawings"], list)
        assert isinstance(PACKET["section_4_closure_drawings"], list)
        for d in PACKET["section_2_bottle_drawings"]:
            assert d["component_class"] == "bottle"
        for d in PACKET["section_4_closure_drawings"]:
            assert d["component_class"] == "closure"

    def test_conflicts_are_never_averaged(self):
        rows = [{"component": "bottle",
                 "component_referent": "BODY_OUTSIDE_DIAMETER",
                 "normalized_value": v, "variant_identity": f"v{v}",
                 "source_id": f"S{v}", "closure_included": "UNSTATED"}
                for v in (32.0, 33.5)]
        c = tg.conflicts_by_referent(rows)
        assert c and c[0]["values_mm"] == [32.0, 33.5]
        assert c[0]["auto_resolved"] is False
        assert c[0]["required_human_action"] == "PENDING"


class TestSufficiency:
    def test_checklist_cannot_pass_vacuously(self):
        empty = {"sources": [], "drawings": [], "measurements": []}
        s = tg.sufficiency(empty)
        assert s["sufficient"] is False
        assert s["checks"]["at_least_1_dimensional_measurement"] is False
        assert s["checks"]["every_measurement_has_exact_referent"] is False
        assert s["state"] == tg.VQ_PHYSICAL_GEOMETRY_EVIDENCE_INCOMPLETE

    def test_recorded_state_is_incomplete(self):
        suf = PACKET["section_11_sufficiency"]
        assert suf["sufficient"] is False
        assert suf["state"] == tg.VQ_PHYSICAL_GEOMETRY_EVIDENCE_INCOMPLETE
        assert suf["counts"]["dimensional_measurements"] == 0
        assert PACKET["packet_complete"] is False

    def test_compatibility_evidence_is_a_required_condition(self):
        assert "at_least_1_compatibility_source" in \
            PACKET["section_11_sufficiency"]["checks"]

    def test_session_limits_were_respected(self):
        lim = SESSION["limits"]
        assert SESSION["provider_calls"] <= lim["max_searches"]
        assert len(SESSION["sources"]) <= lim["max_retained_results"]
        assert SESSION["fetches"] <= lim["max_fetched_pages"]
        assert SESSION["pdfs"] <= lim["max_pdfs"]


class TestCarriedDecisions:
    def test_capacity_is_not_a_geometry_approval(self):
        cd = PACKET["carried_decisions"]["NOMINAL_CAPACITY"]
        assert cd["value"] == "30" and cd["unit"] == "ml"
        assert cd["authority"] == "PRODUCT_CONCEPT_REQUIREMENT"
        assert cd["is_physical_geometry_approval"] is False

    def test_neck_finish_stays_unresolved(self):
        cd = PACKET["carried_decisions"]["NECK_FINISH_CANDIDATES"]
        assert cd["selected"] is None
        assert cd["state"] == "UNRESOLVED"
        assert set(cd["values"]) == {"18/415", "18/410", "20/410", "24/410"}
        assert len(cd["selection_requires"]) == 4

    def test_ws20_is_reference_only(self):
        cd = PACKET["carried_decisions"]["WS-20"]
        assert cd["classification"] == "NECK_FINISH_REFERENCE_ONLY"
        assert cd["state"] == "NEEDS_VERIFICATION"
        assert cd["is_sufficient_complete_drawing"] is False
        for banned in ("bottle diameter", "collar diameter", "bulb geometry",
                       "total assembled height",
                       "structural backbone generation"):
            assert banned in cd["does_not_authorize"]

    def test_human_decision_record_is_persisted(self):
        rec = json.load(open(os.path.join(
            R1B, "vq1_reset1a_human_evidence_decision.json")))
        assert rec["decisions"]["MEASUREMENT_APPROVAL"] == "NONE"
        assert rec["decisions"]["COMPONENT_SEMANTICS"] == "UNCERTAIN"
        assert rec["decisions"]["NEXT_ACTION"] == "RESEARCH_AGAIN"
        assert rec["evidence_quality_threshold"] == "NOT_MET"


class TestSemanticsAndVisualizer:
    def test_semantic_selection_remains_pending(self):
        assert tg.VQ_COMPONENT_SEMANTICS_UNRESOLVED in PACKET["findings"]
        sem = json.load(open(os.path.join(
            DOCS, "vq1_reset1", "component_semantic_finding.json")))
        assert sem["resolved_classification"] == "UNCERTAIN"
        assert sem["generation_blocked"] is True

    def test_visualizer_limits_are_recorded(self):
        v = PACKET["section_10_visualizer"]
        assert v["calls_spent_this_slice"] == 0
        for banned in ("invent dimensions", "override technical drawings",
                       "select final component semantics",
                       "authorize a structural model"):
            assert banned in v["may_not"]
        assert v["standing_conflict"] == \
            "VQ_MULTIMODAL_NUMERIC_CLAIM_CONFLICT"

    def test_pixel_evidence_stays_concept_visual(self):
        px = PACKET["section_9_image97_pixel_evidence"]
        assert "NOT A PHYSICAL DIMENSION" in px["banner"]
        assert px["bilateral_symmetry_asserted"] is False


class TestBoundaries:
    def test_no_geometry_was_generated(self):
        assert PACKET["geometry_generated"] is False
        assert tg.VQ_STRUCTURAL_GENERATION_BLOCKED in PACKET["findings"]
        src = open(tg.__file__).read()
        for banned in ("canonical_geometry", "draw_fixture", "CubicTo",
                       "build_backbone", "BACKBONE_REGISTRY"):
            assert banned not in src

    def test_no_image_generation_call_occurred(self):
        assert PACKET["image_generation_calls"] == 0
        src = open(tg.__file__).read().lower()
        for banned in ("images.generate", "dall-e", "generate_image",
                       "image_producer"):
            assert banned not in src

    def test_web_access_is_ledgered_not_apicallrecord(self):
        src = open(tg.__file__).read()
        assert "WebAccessRecord.objects.create" in src
        # the LLM/image ledger may be NAMED in prose but never written to
        assert "ApiCallRecord.objects" not in src
        assert "from apps.pipeline.models import ApiCallRecord" not in src

    @pytest.mark.django_db
    def test_live_pilot_records_untouched(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for tid, status in ((52, "container_stage_visually_rejected"),
                            (51, "awaiting_gate_2")):
            t = DesignTask.objects.filter(id=tid).first()
            assert t is None or t.status == status
        p = DesignProject.objects.filter(id=7).first()
        assert p is None or p.status == "container_rejected"

    def test_packet_artifacts_are_servable(self):
        from apps.pipeline.vq_views import ARTIFACTS
        for key in ("reset1b-packet-png", "reset1b-packet-p2-png",
                    "reset1b-packet-p3-png", "reset1b-packet-pdf",
                    "reset1b-packet-json", "reset1b-decision"):
            assert key in ARTIFACTS
            rel, _m = ARTIFACTS[key]
            assert os.path.exists(os.path.join(DOCS, "vq1", rel)), key
