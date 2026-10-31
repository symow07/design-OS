"""IT6 record normalization — canonical blocker, supporting finding, and
the VQ-3 material deferral. No geometry is touched by this slice."""
import json
import os

import pytest
from django.conf import settings

from apps.ire import vq1_reset2 as r2

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
R2D = os.path.join(DOCS, "vq1_reset2")
REV = os.path.join(DOCS, "vq1_it6_review")
BC = json.load(open(os.path.join(REV, "vq1_it6_blocker_classification.json")))
PACKET = json.load(open(os.path.join(
    REV, "vq1_it6_collar_neck_review.json")))

CANON = "VQ_DARK_CLOSURE_LOWER_INTERFACE_FAILED"
SUPPORT = "VQ_COLLAR_NECK_JUNCTION_DEVIATION"
DEFERRED = "VQ_COLLAR_METALLIC_REALIZATION_DEFERRED_TO_VQ3"
SYNONYM = "VQ_DARK_FLARE_COLLAR_JUNCTION_FAILED"


class TestCanonicalBlocker:
    def test_canonical_code_is_the_stable_generator_code(self):
        b = BC["active_structural_blockers"][0]
        assert b["code"] == CANON
        assert b["canonical"] is True
        assert b["blocks_vq1_structural_acceptance"] is True
        assert hasattr(r2, "VQ_DARK_CLOSURE_LOWER_INTERFACE_FAILED")
        assert r2.VQ_DARK_CLOSURE_LOWER_INTERFACE_FAILED == CANON
        assert PACKET["active_vq1_structural_blocker"] == CANON

    def test_no_third_synonymous_code_is_introduced(self):
        # the synonym may be NAMED only in the rejection list; it must never
        # appear as an active blocker, finding or deferred code
        assert BC["synonymous_codes_rejected"] == [SYNONYM]
        active = ([b["code"] for b in BC["active_structural_blockers"]]
                  + [f["code"] for f in
                     BC["supporting_deterministic_findings"]]
                  + [d["code"] for d in BC["deferred_material_findings"]])
        assert SYNONYM not in active
        assert PACKET["active_vq1_structural_blocker"] != SYNONYM
        assert PACKET["supporting_deterministic_finding"] != SYNONYM
        assert PACKET["deferred_to_vq3"] != SYNONYM
        # every remaining mention must be inside a rejection list
        stripped = json.dumps(BC).replace(
            json.dumps(BC["synonymous_codes_rejected"]), "")
        assert SYNONYM not in stripped
        for f in os.listdir(R2D):
            if f.endswith(".json"):
                assert SYNONYM not in open(os.path.join(R2D, f)).read(), f
        src = open(r2.__file__).read()
        assert SYNONYM not in src

    def test_supporting_relationship_is_persisted(self):
        rel = BC["relationship"]
        assert rel["blocker"] == CANON
        assert rel["relation"] == "supported_by"
        assert rel["finding"] == SUPPORT
        assert SUPPORT in BC["active_structural_blockers"][0]["supported_by"]

    def test_deterministic_finding_preserved_and_does_not_replace(self):
        f = BC["supporting_deterministic_findings"][0]
        assert f["code"] == SUPPORT
        assert f["supports"] == CANON
        assert f["replaces_canonical_blocker"] is False
        assert f["max_junction_contour_distance"] == 0.16176
        assert f["permitted_maximum"] == 0.070
        assert f["measured_on"] == "ACTUAL_EMITTED_PNG"
        assert PACKET["supporting_deterministic_finding"] == SUPPORT


class TestMaterialDeferral:
    def test_metallic_realization_is_nonblocking_for_vq1(self):
        d = BC["deferred_material_findings"][0]
        assert d["code"] == DEFERRED
        assert d["category"] == "MATERIAL_REALIZATION"
        assert d["current_workstream_relevance"] == \
            "NONBLOCKING_FOR_VQ1_STRUCTURE"
        assert d["blocks_vq1_structural_acceptance"] is False
        assert PACKET["deferred_to_vq3"] == DEFERRED

    def test_vq3_may_not_start_before_vq1_acceptance(self):
        assert BC["deferred_material_findings"][0][
            "vq3_may_start_before_vq1_structural_acceptance"] is False
        assert PACKET["vq3_may_start_before_vq1_acceptance"] is False

    def test_original_visualizer_wording_preserved_for_audit(self):
        orig = BC["original_visualizer_critical_blockers_verbatim"]
        assert len(orig) == 4
        v = json.load(open(os.path.join(R2D, "vision_iteration_6.json")))
        assert orig == v["critical_blockers"]
        deferred = BC["deferred_material_findings"][0][
            "original_visualizer_wording_preserved_for_audit"]
        for w in deferred:
            assert w in orig

    def test_every_observation_is_explicitly_assigned(self):
        assign = BC["visualizer_observation_assignment"]
        assert len(assign) == len(
            BC["original_visualizer_critical_blockers_verbatim"])
        assert BC["assignment_method"] == "EXPLICIT_PER_OBSERVATION"
        for a in assign:
            assert a["category"] in ("STRUCTURAL", "MATERIAL_REALIZATION")
            assert a["rationale"]
            assert a["blocks_vq1_structural_acceptance"] == \
                (a["category"] == "STRUCTURAL")

    def test_the_flare_observation_stays_structural(self):
        """It names the metal sleeve but describes the canonical blocker."""
        flare = [a for a in BC["visualizer_observation_assignment"]
                 if "flare" in a["observation"].lower()]
        assert flare and flare[0]["category"] == "STRUCTURAL"
        assert flare[0]["blocks_vq1_structural_acceptance"] is True
        assert "keyword pass" in BC["assignment_note"]

    def test_material_findings_are_separated_from_active_blockers(self):
        active = {b["code"] for b in BC["active_structural_blockers"]}
        assert DEFERRED not in active
        deferred_words = BC["deferred_material_findings"][0][
            "original_visualizer_wording_preserved_for_audit"]
        for w in deferred_words:
            assert w not in BC["structural_visualizer_observations_retained"]


class TestNothingElseChanged:
    def test_it6_geometry_is_byte_identical(self):
        import hashlib

        def sha(p):
            return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
        expected = {
            "concept_visual_envelope_it6.json": "48655142a19f5e47",
            "concept_visual_envelope_it5.json": "0bddf2639ecc6fca",
            "iteration_5.png": "cef8e1ab2618a978",
            "it6_reference_collar_pixels.json": "08827877424777c0",
            "vision_iteration_6.json": "8c60282ec0add4a0",
        }
        for f, h in expected.items():
            assert sha(os.path.join(R2D, f)) == h, f

    def test_metrics_and_verdict_unchanged(self):
        m = PACKET["metrics"]
        assert m["max_collar_junction_distance"] == 0.16176
        assert m["collar_outer_contour_iou"] == 0.97179
        assert m["visible_contour_steps"] == 0
        assert m["gates_pass"] is False
        assert PACKET["visualizer"]["verdict"] == \
            "VISUALLY_IMPROVED_BUT_INSUFFICIENT"

    def test_states_held(self):
        assert PACKET["vq1_state"] == "REVISION_REQUIRED"
        assert PACKET["it7_generated"] is False
        assert PACKET["assembly_released"] is False
        assert BC["geometry_changed"] is False
        assert BC["it7_generated"] is False
        rec = json.load(open(os.path.join(
            DOCS, "vq1", "vq1_human_structural_review.json")))
        assert rec["state"] == "REVISION_REQUIRED"

    def test_no_provider_call_and_no_supplier_send(self):
        assert BC["provider_calls_this_slice"] == 0
        assert BC["supplier_requests_sent"] is False
        out = json.load(open(os.path.join(
            R2D, "vq1_supplier_specification_outreach.json")))
        for s in out["suppliers"]:
            assert s["sent"] is False
            assert s["status"] == "DRAFTED_READY_FOR_HUMAN_SEND"

    def test_iterations_preserved(self):
        for n in (1, 2, 3, 4, 5, 6):
            assert os.path.exists(
                os.path.join(R2D, f"iteration_{n}_metrics.json"))

    def test_blocker_record_is_servable(self):
        from apps.pipeline.vq_views import ARTIFACTS
        assert "it6-blockers" in ARTIFACTS
        rel, _m = ARTIFACTS["it6-blockers"]
        assert os.path.exists(os.path.join(DOCS, "vq1", rel))

    @pytest.mark.django_db
    def test_live_pilot_records_untouched(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for tid, status in ((52, "container_stage_visually_rejected"),
                            (51, "awaiting_gate_2")):
            t = DesignTask.objects.filter(id=tid).first()
            assert t is None or t.status == status
        p = DesignProject.objects.filter(id=7).first()
        assert p is None or p.status == "container_rejected"
