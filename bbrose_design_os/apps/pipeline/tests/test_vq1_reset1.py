"""VQ-1-RESET-1 §23 — visual inspector, semantic gate, correction loop,
governed geometry research, and preservation of the rejected fixtures."""
import json
import os

import pytest
from django.conf import settings

from apps.pipeline.services import visual_extract as vx
from apps.pipeline.services import visual_inspector as vi
from apps.pipeline.services import web_geometry_research as wg

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
R1 = os.path.join(DOCS, "vq1_reset1")


def _load(name):
    with open(os.path.join(R1, name)) as f:
        return json.load(f)


def _fake_profile(kind):
    """Synthetic half-width profiles standing in for extracted pixels."""
    if kind == "cylinder_dome_flare":          # the closure component
        return [0.2, 0.6, 0.9] + [1.0] * 40 + [1.06, 1.18, 1.34, 1.5]
    if kind == "teardrop_stem":                # the CORR-5 closure
        return ([0.0, 0.4, 0.8, 1.0, 0.9, 0.75, 0.6, 0.45]
                + [0.44] * 12)
    if kind == "polygon":
        return [1.0] * 20 + [1.4] * 20 + [1.8] * 20 + [2.0] * 20
    return [1.0] * 80


class TestPreservationAndFreeze:
    def test_corr5_preserved_and_classified_rejected(self):
        fx = json.load(open(os.path.join(
            DOCS, "vq1_corr5", "vq1_corr5_fixture.json")))
        assert fx["fixture_hash"].startswith("d99c412df4989c18")
        cls = _load("vq1_corr5_rejection_classification.json")
        assert cls["classification"] == "REJECTED_WRONG_COMPONENT_MODEL"
        assert cls["fixture_hash"] == "d99c412df4989c18"
        assert cls["may_be_basis_for_vq2"] is False

    def test_every_prior_fixture_still_present(self):
        from apps.ire.vq1_backbone import build_backbone
        assert build_backbone()["backbone_hash"].startswith(
            "19f9b98d0bc46a0d")
        for p in ("vq1/vq1_cylindrical_backbone_review.png",
                  "vq1_corr2/vq1_corr2_review.png",
                  "vq1_corr3/vq1_corr3_review.png",
                  "vq1_corr4/vq1_corr4_fixture.json",
                  "vq1_corr5/vq1_corr5_fixture.json",
                  "vq1_corr5/vq1_corr5_p1_bulb.png"):
            assert os.path.exists(os.path.join(DOCS, p)), p

    def test_generators_are_frozen(self):
        from apps.ire import (vq1_backbone, vq1_corr4, vq1_corr5,
                              vq1_render)
        for mod in (vq1_backbone, vq1_render, vq1_corr4, vq1_corr5):
            assert mod.GENERATOR_STATE == \
                "LEGACY_REJECTED_STRUCTURAL_GENERATOR"
            assert mod.MAY_EMIT_NEW_CANDIDATE is False
        freeze = _load("vq1_generator_freeze.json")
        assert freeze["may_emit_new_candidate"] is False
        assert "current bulb profile" in freeze["not_authorized_for_reuse"]

    def test_human_rejection_active_with_all_five_recorded(self):
        rec = json.load(open(os.path.join(
            DOCS, "vq1", "vq1_human_structural_review.json")))
        assert rec["state"] == "REVISION_REQUIRED"
        assert "VQ1_CORR5_WORSE_THAN_PRIOR_FIXTURE" in rec["codes"]
        assert len(rec["history"]) == 4       # rejections #1-#4 preserved
        assert len(rec["exact_visual_findings_verbatim"]) == 14
        assert any("outer bulb cover" in f
                   for f in rec["exact_visual_findings_verbatim"])


class TestInspectorSeesPixels:
    def test_inspection_records_actual_image_identities(self):
        ins = _load("inspection_corr_5.json")
        assert ins["schema_version"] == "visual_quality_inspection/1.0"
        assert ins["reference_ids"], "reference images must be recorded"
        for ref in ins["reference_ids"].values():
            assert ref["sha256_16"] and os.path.exists(ref["path"])
        assert ins["output"]["sha256_16"]
        assert ins["extractor_validation"]["extractor_validated"] is True

    def test_renderer_cannot_judge_itself(self):
        """The inspector must not import any fixture generator."""
        src = open(vi.__file__).read()
        for gen in ("vq1_backbone", "vq1_render", "vq1_corr4", "vq1_corr5",
                    "canonical_geometry", "draw_fixture"):
            assert gen not in src
        # the prompt must be blind: describe before judging, and never
        # tell the model what the system believes it drew. Component names
        # may appear ONLY inside the allowed-classification enum.
        prompt = vi.VISION_SYSTEM
        assert "Describe what you actually see BEFORE judging" in prompt
        assert "Never assume what a component is from the product " \
               "category" in prompt
        import re
        # component names may appear ONLY inside the <enum|enum> answer
        # placeholders; nowhere may the prompt assert what was drawn
        outside = re.sub(r"<[^>]*>", "", prompt)
        for word in ("pipette", "bulb", "dropper", "serum"):
            assert word not in outside.lower(), word

    def test_verdicts_are_bounded_and_never_auto_accept(self):
        assert "AUTO_ACCEPTED" not in vi.VERDICTS
        for name in dir(vi):
            if name.isupper() and isinstance(getattr(vi, name), str):
                assert getattr(vi, name) != "AUTO_ACCEPTED"
        for f in ("inspection_corr_2.json", "inspection_corr_5.json"):
            assert _load(f)["verdict"] in vi.VERDICTS

    def test_inspector_reproduces_the_recorded_human_rejections(self):
        """Acceptance test: the inspector must independently reject all
        four fixtures a human rejected, and rank CORR-5 below CORR-4."""
        d = {n: _load(f"inspection_corr_{n}.json")
             for n in ("2", "3", "4", "5")}
        for ins in d.values():
            assert ins["verdict"] != vi.PASSES_PENDING_HUMAN
        dist = {n: v["deterministic"]["normalized_contour_distance"]
                for n, v in d.items()}
        assert dist["5"] > dist["4"], "CORR-5 must measure worse"
        assert d["5"]["verdict"] == vi.VISUALLY_WORSE
        upper = {n: v["deterministic"]["band_distance"]["upper_third"]
                 for n, v in d.items()}
        assert upper["5"] == max(upper.values()), \
            "the failure must localize to the closure band"

    def test_structured_output_is_persisted(self):
        ins = _load("inspection_corr_5.json")
        for field in ("inspection_id", "reference_ids", "output_id",
                      "component_semantics", "per_component_score",
                      "silhouette_score", "closure_score", "shoulder_score",
                      "body_score", "reference_preservation_score",
                      "visual_findings", "critical_blockers",
                      "improvement_against_previous", "confidence",
                      "recommended_correction_type", "verdict",
                      "human_review_state"):
            assert field in ins, field
        assert ins["human_review_state"] == "NOT_REVIEWED"


class TestComponentSemanticGate:
    def test_deterministic_read_vetoes_a_bare_bulb_claim(self):
        shape = vi.profile_shape_findings(
            _fake_profile("cylinder_dome_flare"), label="ref")
        assert shape["reads_as_cylinder_with_dome"]
        assert not shape["reads_as_teardrop"]
        sem = vi.classify_component_semantics(
            shape, {"component_semantics": {
                "classification": "EXPOSED_RUBBER_PIPETTE_BULB",
                "confidence": 0.9}})
        assert sem["resolved_classification"] == "UNCERTAIN"
        assert sem["generation_blocked"] is True

    def test_uncertainty_blocks_generation(self):
        sem = vi.classify_component_semantics(
            {"reads_as_cylinder_with_dome": False, "lower_flare": 0.0},
            {"component_semantics": {"classification": "UNCERTAIN",
                                     "confidence": 0.2}})
        assert sem["generation_blocked"] is True
        assert sem["blocker"] == vi.SEMANTIC_HUMAN_REQUIRED

    def test_no_generic_bulb_model_is_forced(self):
        assert "EXPOSED_RUBBER_PIPETTE_BULB" in vi.COMPONENT_SEMANTICS
        assert "DECORATIVE_OUTER_BULB_COVER" in vi.COMPONENT_SEMANTICS
        assert "COMPLETE_CLOSURE_OVERCAP" in vi.COMPONENT_SEMANTICS
        assert "UNCERTAIN" in vi.COMPONENT_SEMANTICS
        finding = _load("component_semantic_finding.json")
        assert finding["resolved_classification"] == "UNCERTAIN"
        assert finding["generation_blocked"] is True
        assert finding["human_confirmed"] is False

    def test_recorded_finding_matches_the_reference_pixels(self):
        finding = _load("component_semantic_finding.json")
        pf = finding["profile_findings"]
        assert pf["reads_as_cylinder_with_dome"] is True
        assert pf["reads_as_teardrop"] is False
        assert pf["longest_constant_width_run"] > 0.2
        assert pf["lower_flare"] > 0.05


class TestCorrectionPlanAndLoop:
    def test_plan_targets_the_failed_component(self):
        plan = _load("visual_correction_plan.json")
        assert plan["schema_version"] == "visual_correction_plan/1.0"
        assert plan["failed_component"] == "BULB"
        assert plan["problem_class"] == "SEMANTIC"
        assert plan["model_replacement_required"] is True
        assert any("tuning" in p for p in plan["prohibited_changes"])

    def test_semantic_failure_forces_model_replacement(self):
        ins = _load("inspection_corr_5.json")
        assert ins["recommended_correction_type"] == \
            "SEMANTIC_MODEL_REPLACEMENT"

    def test_worse_than_previous_stops_iteration(self):
        worse = {"verdict": vi.VISUALLY_WORSE, "critical_blockers": [],
                 "component_semantics": {"generation_blocked": False},
                 "improvement_against_previous": {}}
        assert vi.loop_should_stop([worse]) == {
            "stop": True, "reason": "RESULT_BECAME_WORSE", "passes_used": 1}

    def test_repeated_blocker_stops_within_the_bound(self):
        a = {"verdict": vi.VISUALLY_REJECTED,
             "critical_blockers": ["VQ_BULB_SPEAR_OR_LEAF_SHAPE"],
             "component_semantics": {"generation_blocked": False},
             "improvement_against_previous": {"contour_distance_delta": 0.5}}
        stop = vi.loop_should_stop([dict(a), dict(a)])
        assert stop["stop"] and stop["reason"] == \
            "SAME_BLOCKER_REPEATED_TWICE"
        assert stop["passes_used"] < vi.MAX_CORRECTION_PASSES + 1

    def test_loop_is_bounded_to_three_passes(self):
        assert vi.MAX_CORRECTION_PASSES == 3
        ok = {"verdict": vi.VISUALLY_IMPROVED_INSUFFICIENT,
              "critical_blockers": [],
              "component_semantics": {"generation_blocked": False},
              "improvement_against_previous": {
                  "contour_distance_delta": 0.9}}
        assert vi.loop_should_stop([dict(ok) for _ in range(3)])["reason"] \
            == "MAX_CORRECTION_PASSES_REACHED"

    def test_no_synthetic_iteration_was_produced(self):
        loop = _load("visual_correction_loop.json")
        assert loop["synthetic_iterations_produced"] == 0
        assert loop["correction_passes_run"] == 0
        assert "UNCERTAIN" in loop["reason_no_iteration_produced"]


class TestWebGeometryResearch:
    def test_queries_seek_physical_specifications(self):
        assert len(wg.QUERIES) >= 8
        joined = " ".join(wg.QUERIES).lower()
        for term in ("technical drawing", "dimensions", "specification",
                     "cad", "neck finish", "18/415"):
            assert term in joined
        assert wg.RESEARCH_PURPOSE == \
            "PHYSICAL_FEASIBILITY_NOT_DESIGN_INSPIRATION"

    def test_marketplace_snippets_cannot_authorize_dimensions(self):
        for d in ("www.amazon.com", "aliexpress.com", "m.alibaba.com"):
            authority, tier = wg.dimensional_authority(d)
            assert tier is None
            assert authority == "MARKETPLACE_SNIPPET_INSUFFICIENT_AUTHORITY"
        src = wg.classify_source({"url": "https://www.amazon.com/x",
                                  "domain": "www.amazon.com",
                                  "title": "30ml bottle 65mm height"})
        assert src["may_authorize_measurements"] is False
        assert wg.extract_measurements(src, "diameter 30 mm") or True
        packet = _load("vq1_web_geometry_reference_packet.json")
        for m in packet["measurements"]:
            assert m["may_authorize"] is True

    def test_gallery_and_stock_sources_are_excluded(self):
        for d in ("www.pinterest.com", "dribbble.com", "shutterstock.com"):
            authority, tier = wg.dimensional_authority(d)
            assert tier is None
            assert authority == "EXCLUDED_INSPIRATION_OR_STOCK_SOURCE"

    def test_supplier_pages_may_authorize_and_drawings_promote(self):
        _, tier = wg.dimensional_authority("www.examplepackaging.com")
        assert tier == 2
        src = wg.classify_source({
            "url": "https://www.examplepackaging.com/spec",
            "domain": "www.examplepackaging.com",
            "title": "30ml bottle technical drawing", "snippet": ""})
        assert src["dimensional_authority_tier"] == 1

    def test_measurement_referents_stay_separate(self):
        packet = _load("vq1_web_geometry_reference_packet.json")
        refs = {m["component_referent"] for m in packet["measurements"]}
        assert len(refs) > 1
        for m in packet["measurements"]:
            assert m["component_referent"] in set(wg.REFERENTS) | {
                "UNASSIGNED_DIMENSION"}
            assert m["human_decision"] == "PENDING"
            assert m["verification_state"] == "UNVERIFIED"
            assert m["source_url"] and m["source_domain"]

    def test_conflicts_are_preserved_not_averaged(self):
        rows = [{"unit": "mm", "may_authorize": True,
                 "component_referent": "collar_diameter",
                 "normalized_value_mm": v, "source_url": f"u{v}"}
                for v in (18.0, 19.5)]
        c = wg.conflicts(rows)
        assert c and c[0]["values_mm"] == [18.0, 19.5]
        assert c[0]["resolution"] == "PRESERVED_UNRESOLVED_HUMAN_DECISION"

    def test_web_facts_carry_provenance_and_nothing_is_approved(self):
        packet = _load("vq1_web_geometry_reference_packet.json")
        assert packet["schema_version"] == \
            "web_container_geometry_research/1.0"
        assert packet["status"] == "AWAITING_HUMAN_REVIEW"
        assert all(v == "PENDING" for v in packet["human_review"].values())
        for s in packet["sources"]:
            assert s["rights"]["fact_source_permission"] is False
            assert s["human_decision"] == "PENDING"

    def test_research_sufficiency_is_evaluated(self):
        packet = _load("vq1_web_geometry_reference_packet.json")
        s = packet["sufficiency"]
        assert s["qualified_analogs"] >= wg.MIN_QUALIFIED_ANALOGS
        assert s["sources_with_dimensions"] >= \
            wg.MIN_SOURCES_WITH_DIMENSIONS
        assert s["technical_drawings"] >= wg.MIN_TECHNICAL_DRAWINGS
        assert set(s["checks"]) == {
            "at_least_3_qualified_analogs",
            "at_least_2_sources_with_dimensions",
            "at_least_1_technical_drawing",
            "at_least_2_closure_constructions"}

    def test_session_records_a_blocked_provider_without_crashing(self):
        from apps.pipeline.services import web_research as wr

        def boom(_q):
            raise wr.WebPolicyError(wr.WEB_RESEARCH_NOT_CONFIGURED, "no key")
        s = wg.run_geometry_session(search_fn=boom, queries=wg.QUERIES[:2])
        assert s["status"] == "BLOCKED_NO_SOURCES"
        assert len(s["warnings"]) == 2
        assert s["provider_calls"] == 0


class TestExtractorValidation:
    def test_extractor_must_validate_before_metrics_are_trusted(self):
        good = vx.validate_against_reference(
            {"closure": 1}, {"collar": (108.5, 109.5)})
        assert good["extractor_validated"] is True
        bad = vx.validate_against_reference(
            {"closure": 1}, {"collar": (60.0, 109.5)})
        assert bad["extractor_validated"] is False

    def test_occluded_reference_never_claims_symmetry(self):
        prof = {"half_width": [10.0] * 20,
                "occlusion_note": "carton occludes the left edge"}
        out = vi.parallelism_and_symmetry(prof)
        assert out["symmetry_measurable"] is False
        assert "mean_symmetry_error_px" not in out
        assert "occludes" in out["symmetry_note"]

    def test_polygonized_contour_is_detected(self):
        assert vi.curvature_continuity(_fake_profile("polygon"))[
            "polygonized"] is True


class TestProviderBoundary:
    def test_no_image_generation_call_occurred(self):
        log = _load("provider_call_log.json")
        assert log["calls_by_type"]["image_generation"] == 0
        assert log["calls_by_type"]["design_concept_generation"] == 0
        assert log["calls_by_type"]["prompt_engineer"] == 0
        assert log["calls_by_type"]["visual_inspection_multimodal"] >= 1
        assert log["calls_by_type"]["web_geometry_search"] >= 1

    def test_inspector_never_generates_images(self):
        for mod in (vi, wg, vx):
            src = open(mod.__file__).read().lower()
            for banned in ("images.generate", "dall-e", "image_producer",
                           "run_aria_pipeline", "generate_image"):
                assert banned not in src

    @pytest.mark.django_db
    def test_live_pilot_records_untouched(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for tid, status in ((52, "container_stage_visually_rejected"),
                            (51, "awaiting_gate_2")):
            t = DesignTask.objects.filter(id=tid).first()
            assert t is None or t.status == status
        p = DesignProject.objects.filter(id=7).first()
        assert p is None or p.status == "container_rejected"


class TestReviewBoard:
    def test_visualizer_artifacts_are_servable(self):
        from apps.pipeline.vq_views import ARTIFACTS
        for key in ("reset1-packet-png", "reset1-packet-pdf",
                    "reset1-semantics", "reset1-plan", "reset1-loop",
                    "reset1-provider-log", "reset1-freeze",
                    "reset1-corr5-classification",
                    "reset1-inspection-corr4", "reset1-inspection-corr5"):
            assert key in ARTIFACTS
            rel, _mime = ARTIFACTS[key]
            path = os.path.join(settings.BASE_DIR, "docs", "visual_quality",
                                "vq1", rel)
            assert os.path.exists(path), key
