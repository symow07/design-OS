"""VQ-1-RESET-1A §15 — evidence authority, referent separation, conflict
preservation, semantic adjudication and the no-geometry boundary."""
import json
import os

import pytest
from django.conf import settings

from apps.pipeline.services import geometry_evidence as ge

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
R1A = os.path.join(DOCS, "vq1_reset1a")
PACKET = json.load(open(os.path.join(
    R1A, "vq1_geometry_evidence_review.json")))


class TestEvidenceAuthority:
    def test_only_tiers_1_to_3_authorize_alone(self):
        assert [t for t in ge.AUTHORITY_TIERS
                if ge.may_authorize_alone(t)] == [1, 2, 3]
        assert ge.AUTHORITY_TIERS[4]["requires_corroboration"] is True
        for t in (4, 5, 6):
            assert ge.may_authorize_alone(t) is False

    def test_marketplace_and_stock_are_tier_6(self):
        for d in ("www.amazon.com", "aliexpress.com", "pinterest.com",
                  "shutterstock.com", "www.etsy.com"):
            assert ge.authority_tier(d) == 6
            assert ge.may_authorize_alone(ge.authority_tier(d)) is False

    def test_drawings_promote_to_tier_1(self):
        assert ge.authority_tier("www.example.com",
                                 "30ml bottle technical drawing") == 1
        assert ge.authority_tier("www.panyuepacking.com",
                                 "Neck Finish Dimensions") == 1

    def test_distributors_are_tier_3(self):
        assert ge.authority_tier("www.sks-bottle.com", "droppers") == 3

    def test_packet_sources_carry_their_tier_and_permissions(self):
        for group in ("section_2_primary_bottle_sources",
                      "section_3_primary_closure_sources",
                      "alternates", "section_4_technical_drawings"):
            for s in PACKET[group]:
                assert s["source_id"].startswith("WS-")
                assert s["authority_tier"] in ge.AUTHORITY_TIERS
                assert s["may_authorize_alone"] == \
                    ge.may_authorize_alone(s["authority_tier"])
                assert set(s["actions_available"]) == set(ge.SOURCE_ACTIONS)

    def test_shortlist_is_bounded_as_specified(self):
        assert 3 <= len(PACKET["section_2_primary_bottle_sources"]) <= 5
        assert 2 <= len(PACKET["section_3_primary_closure_sources"]) <= 4
        assert len(PACKET["alternates"]) <= 3
        assert len(PACKET["section_4_technical_drawings"]) >= 1


class TestSnippetsAreNotEvidence:
    def test_snippet_measurements_are_demoted(self):
        demoted = PACKET["section_5_measurements"]["snippet_derived_demoted"]
        assert demoted
        for m in demoted:
            assert m["evidence_class"] == ge.SNIPPET_NOT_EVIDENCE
            assert m["component_referent"] == "REFERENT_UNRESOLVED"
            assert m["may_support_concept_geometry"] is False
            assert m["confidence"] == 0.0

    def test_fetched_measurements_record_their_extraction(self):
        for m in PACKET["section_5_measurements"]["from_governed_fetch"]:
            assert m["extraction"] == "GOVERNED_PAGE_FETCH"
            assert m["source_url"] and m["source_domain"]
            assert m["human_decision"] == "PENDING"
            assert m["verification_state"] == "UNVERIFIED"

    def test_no_dimensional_referent_currently_qualifies(self):
        """The honest state: only capacity and neck finish survived."""
        refs = PACKET["section_5_measurements"]["qualified_referents"]
        assert set(refs) == {"NECK_FINISH", "NOMINAL_CAPACITY"}
        assert "no measurement candidate can currently guide concept " \
               "geometry" in PACKET["section_5_measurements"]["consequence"]


class TestMeasurementReferents:
    def test_referent_vocabulary_is_explicit(self):
        for required in ("BODY_OUTSIDE_DIAMETER",
                         "BOTTLE_HEIGHT_WITHOUT_CLOSURE",
                         "TOTAL_HEIGHT_WITH_CLOSURE", "NECK_FINISH",
                         "COLLAR_OUTSIDE_DIAMETER",
                         "DARK_COMPONENT_MAXIMUM_WIDTH",
                         "DARK_COMPONENT_VISIBLE_HEIGHT", "PIPETTE_LENGTH",
                         "OVERFLOW_CAPACITY", "GLASS_WEIGHT"):
            assert required in ge.REFERENTS

    def test_extractor_assigns_referents_and_preserves_units(self):
        src = {"domain": "d", "url": "u", "authority_tier": 1,
               "may_authorize_alone": True}
        rows = ge.extract_referenced(
            "Body outside diameter: 32.5 mm. Neck finish 18/415. "
            "Collar 19.2 mm. Pipette length 78 mm.", src)
        got = {r["component_referent"]: r for r in rows}
        assert got["BODY_OUTSIDE_DIAMETER"]["raw_value"] == "32.5"
        assert got["COLLAR_OUTSIDE_DIAMETER"]["original_unit"] == "mm"
        assert got["NECK_FINISH"]["raw_value"] == "18/415"

    def test_inch_values_keep_their_original_unit(self):
        src = {"domain": "d", "url": "u", "authority_tier": 1,
               "may_authorize_alone": True}
        rows = ge.extract_referenced("Bottle diameter 1.5 in overall", src)
        row = [r for r in rows
               if r["component_referent"] == "BODY_OUTSIDE_DIAMETER"][0]
        assert row["original_unit"] == "in"
        assert row["raw_value"] == "1.5"
        assert row["value_mm_converted"] == 38.1
        assert row["unit_preserved"] is True

    def test_one_value_is_never_filed_under_two_referents(self):
        src = {"domain": "d", "url": "u", "authority_tier": 1,
               "may_authorize_alone": True}
        rows = ge.extract_referenced("Overall height 78 mm", src)
        heights = [r for r in rows if r["raw_value"] == "78"]
        assert len(heights) == 1
        assert heights[0]["component_referent"] == "REFERENT_UNRESOLVED"
        assert heights[0]["referent_ambiguous"] is True
        assert heights[0]["may_support_concept_geometry"] is False


class TestConflicts:
    def test_all_six_conflicts_are_presented_unresolved(self):
        rows = PACKET["section_6_conflicts"]
        assert len(rows) == 6
        for c in rows:
            assert c["auto_resolved"] is False
            assert c["required_human_action"] == "PENDING"
            assert set(c["allowed_actions"]) == set(ge.CONFLICT_ACTIONS)
            assert c["likely_explanation"]
            assert c["one_source_includes_closure"] == "UNKNOWN"
            assert len(c["raw_values"]) >= 2

    def test_conflicting_values_are_never_averaged(self):
        c = ge.enrich_conflict(
            {"component_referent": "COLLAR_OUTSIDE_DIAMETER",
             "values_mm": [18.0, 19.5], "sources": ["a", "b"]}, [])
        assert c["raw_values"] == [18.0, 19.5]
        assert "average" not in json.dumps(c).lower() or \
            c["auto_resolved"] is False


class TestSeparatePermissions:
    def test_seven_rights_are_separate_and_default_deny(self):
        r = ge.rights_default()
        assert set(r) == {"retrieval_permission", "reference_view_permission",
                          "fact_source_permission",
                          "concept_geometry_permission",
                          "provider_input_permission",
                          "artwork_reuse_permission",
                          "design_memory_permission"}
        assert r["fact_source_permission"] is False
        assert r["concept_geometry_permission"] is False
        assert r["artwork_reuse_permission"] is False
        assert r["design_memory_permission"] is False
        assert r["provider_input_permission"] is False

    def test_analog_approval_does_not_imply_fact_or_geometry_approval(self):
        for s in PACKET["section_2_primary_bottle_sources"]:
            d = s["human_decision"]
            assert d["APPROVE_AS_PHYSICAL_ANALOG"] == "PENDING"
            assert d["APPROVE_AS_FACT_SOURCE"] == "PENDING"
            assert d["APPROVE_MEASUREMENTS_FOR_CONCEPT_GEOMETRY"] == \
                "PENDING"
            assert s["rights"]["fact_source_permission"] is False
            assert s["rights"]["concept_geometry_permission"] is False

    def test_phase_rights_boundary_recorded(self):
        rb = PACKET["rights_boundary"]
        assert rb["artwork_reuse"] is False
        assert rb["design_memory"] is False
        assert rb["image_provider_input"] is False


class TestSemanticAdjudication:
    def test_all_six_options_present_and_none_selected(self):
        mx = PACKET["section_10_component_semantic_matrix"]
        assert set(mx["options"]) == set("ABCDEF")
        assert mx["preselected"] is None
        for o in mx["options"].values():
            assert o["selected"] is False
            assert o["definition"]
            assert "reference_pixel_evidence" in o
        assert mx["current_recorded_state"] == "UNCERTAIN"
        assert mx["blocker"] == \
            "VQ_COMPONENT_SEMANTICS_HUMAN_CONFIRMATION_REQUIRED"

    def test_options_record_whether_a_hidden_mechanism_is_required(self):
        opts = PACKET["section_10_component_semantic_matrix"]["options"]
        assert opts["C"]["internal_hidden_mechanism_required"] is True
        assert opts["D"]["internal_hidden_mechanism_required"] is True
        assert opts["A"]["internal_hidden_mechanism_required"] is False

    def test_each_option_has_a_structural_consequence(self):
        cons = {c["if_selected"]
                for c in PACKET["section_12_next_structural_consequences"]}
        assert cons == set("ABCDEF")


class TestVisualizerAuthority:
    def test_deterministic_governs_numeric_claims(self):
        rule = ge.visualizer_authority_rule()
        assert rule["multimodal_may_override_measured_ratios"] is False
        assert rule["conflict_finding"] == \
            ge.VQ_MULTIMODAL_NUMERIC_CLAIM_CONFLICT

    def test_the_recorded_numeric_conflict_is_flagged(self):
        conf = PACKET["section_9_deterministic_vs_multimodal"]["conflicts"]
        assert conf
        c = conf[0]
        assert c["conflict"] is True
        assert c["finding"] == ge.VQ_MULTIMODAL_NUMERIC_CLAIM_CONFLICT
        assert c["governs"] == "DETERMINISTIC_MEASUREMENT"
        assert c["multimodal_status"] == "SEMANTIC_HYPOTHESIS_ONLY"
        assert c["model_claim"] == 1.3
        assert abs(c["deterministic_measurement"] - 0.5023) < 0.01

    def test_agreeing_claims_are_not_flagged(self):
        out = ge.numeric_conflicts(
            {"ratio": 0.50}, [{"metric": "ratio", "model_value": 0.52}])
        assert out[0]["conflict"] is False
        assert out[0]["finding"] is None

    def test_pixel_evidence_is_labelled_concept_only(self):
        pe = PACKET["section_7_reference_pixel_evidence"]
        assert "NOT A PHYSICAL DIMENSION" in pe["banner"]
        assert pe["authority"] == "CONCEPT_VISUAL_ONLY_NOT_PHYSICAL"
        assert pe["bilateral_symmetry_asserted"] is False
        assert pe["symmetry_claim"] == \
            "NOT_MEASURABLE_FROM_THIS_PHOTOGRAPH"
        assert "carton" in pe["occlusion"]


class TestDecisionFormAndBoundary:
    def test_seven_independent_decisions_all_pending(self):
        form = PACKET["section_11_human_decision_form"]
        assert len(form["decisions"]) == 7
        assert form["all_pending"] is True
        for d in form["decisions"]:
            assert d["state"] == "PENDING"
            assert d["selected"] == []
        assert "each decision is independent" in form["bundling_prohibited"]

    def test_no_geometry_was_generated(self):
        assert PACKET["geometry_generated"] is False
        assert PACKET["status"] == "AWAITING_HUMAN_EVIDENCE_DECISIONS"
        src = open(ge.__file__).read()
        for banned in ("canonical_geometry", "draw_fixture", "CubicTo",
                       "MoveTo", "build_backbone"):
            assert banned not in src

    def test_no_image_generation_call_occurred(self):
        assert PACKET["image_generation_calls"] == 0
        log = json.load(open(os.path.join(
            DOCS, "vq1_reset1", "provider_call_log.json")))
        assert log["calls_by_type"]["image_generation"] == 0

    def test_prior_state_is_preserved(self):
        rec = json.load(open(os.path.join(
            DOCS, "vq1", "vq1_human_structural_review.json")))
        assert rec["state"] == "REVISION_REQUIRED"
        assert len(rec["history"]) == 4
        sem = json.load(open(os.path.join(
            DOCS, "vq1_reset1", "component_semantic_finding.json")))
        assert sem["resolved_classification"] == "UNCERTAIN"
        assert sem["generation_blocked"] is True
        fx = json.load(open(os.path.join(
            DOCS, "vq1_corr5", "vq1_corr5_fixture.json")))
        assert fx["fixture_hash"].startswith("d99c412df4989c18")

    def test_packet_artifacts_are_servable(self):
        from apps.pipeline.vq_views import ARTIFACTS
        for key in ("reset1a-packet-png", "reset1a-packet-p2-png",
                    "reset1a-packet-p3-png", "reset1a-packet-pdf",
                    "reset1a-packet-json"):
            assert key in ARTIFACTS
            rel, _m = ARTIFACTS[key]
            assert os.path.exists(os.path.join(
                DOCS, "vq1", rel)), key

    @pytest.mark.django_db
    def test_live_pilot_records_untouched(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for tid, status in ((52, "container_stage_visually_rejected"),
                            (51, "awaiting_gate_2")):
            t = DesignTask.objects.filter(id=tid).first()
            assert t is None or t.status == status
        p = DesignProject.objects.filter(id=7).first()
        assert p is None or p.status == "container_rejected"
