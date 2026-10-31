"""2C-2 live-pilot container-stage failure closeout — final human authority.
No provider; no Packaging; terminal but reviewable."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.core.models import Brand, Product
from django.core.files.base import ContentFile

from apps.pipeline.models import (
    ApiCallRecord,
    DesignProject,
    DesignTask,
    GateDecision,
    GeneratedImage,
    PackagingOutput,
)

from apps.pipeline.services import pilot_closeout as pc
from apps.pipeline.services import visual_quality_program as vqp
from apps.pipeline.targets.composite import stage_human_acceptance

User = get_user_model()

_PNG = __import__("base64").b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4"
    "z8Dwn4EBAAT/Af9jZv5kAAAAAElFTkSuQmCC")


class CloseoutTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        product = Product.objects.create(
            brand=brand, product_id="BBR-SK-201", name="RD", category="SK",
            year=2026)
        self.user = User.objects.create_superuser("closeop", password="x")
        self.project = DesignProject.objects.create(
            brand=brand, product=product, brief="b",
            design_target="complete_product", status="container")
        self.task = DesignTask.objects.create(
            brand=brand, product=product, task_text="t",
            design_target="product_container", stage="container",
            project=self.project, status="awaiting_gate_2",
            created_by=self.user)
        img = GeneratedImage.objects.create(
            task=self.task, direction_name="D", prompt_used="p",
            variation_number=1, is_approved=True)
        img.image_file.save("c.png", ContentFile(_PNG), save=True)
        self.output = PackagingOutput.objects.create(
            task=self.task, approved_image=img, spec_sheet={
                "backend": "container",
                "container_reconstruction_rejected_a": {"s": 1},
                "container_reconstruction_rejected_b": {"s": 2},
                "container_reconstruction_rejected_c": {"s": 3},
                "container_concept_fidelity/1.0": {"failures": []},
            })

    def _close(self):
        return pc.close_container_stage(
            self.task, actor=self.user, now_iso=timezone.now().isoformat())

    def test_final_rejection_is_terminal_reviewable_and_idempotent(self):
        tasks0 = DesignTask.objects.count()
        calls0 = ApiCallRecord.objects.count()
        rec = self._close()
        self.task.refresh_from_db()
        self.project.refresh_from_db()
        self.output.refresh_from_db()
        assert self.task.status == pc.TERMINAL_STATUS
        assert self.project.status == pc.PROJECT_STATUS
        assert self.project.failed_stage == "container"
        assert rec["human_design_acceptance"] == "REJECTED"
        assert rec["revision_state"] == \
            "DEFERRED_TO_FINAL_VISUAL_QUALITY_PROGRAM"
        assert rec["production_approval"] == "BLOCKED"
        assert "TASK_SPECIFIC_CORRECTION_LIMIT_REACHED" in rec["codes"]
        assert len(rec["final_visual_findings"]) == 10
        # §5 pilot result recorded on the project
        result = self.project.metadata[pc.RESULT_META_KEY]
        assert result["result"]["final_pilot_result"] == \
            "CONTAINER_STAGE_FAILED_VISUAL_FIDELITY"
        assert result["result"]["packaging_stage_creation"] == \
            "CORRECTLY PREVENTED"
        # all prior outputs preserved + the final record
        spec = self.output.spec_sheet
        rejected = [k for k in spec
                    if k.startswith("container_reconstruction_rejected")]
        assert len(rejected) == 4 and pc.FINAL_REJECTION_KEY in spec
        # idempotent: no duplicate records or decisions
        again = self._close()
        assert again == rec
        assert GateDecision.objects.filter(
            task=self.task, gate="gate_2", decision="reject").count() == 1
        # no packaging, no provider, no new reconstruction scheduled
        assert DesignTask.objects.count() == tasks0
        assert ApiCallRecord.objects.count() == calls0
        from apps.pipeline.views import TaskRetryView
        assert pc.TERMINAL_STATUS not in TaskRetryView.RETRYABLE

    def test_automated_fidelity_cannot_clear_the_rejection(self):
        self._close()
        # a passing fidelity report exists in the spec — HDA stays rejected
        self.task.refresh_from_db()
        hda = stage_human_acceptance(self.task)
        assert hda["state"].startswith("REJECTED")

    def test_visual_regression_fixtures_registered(self):
        ids = {f["task_id"] for f in vqp.VISUAL_REGRESSION_FIXTURES}
        assert ids == {51, 52}
        f52 = [f for f in vqp.VISUAL_REGRESSION_FIXTURES
               if f["task_id"] == 52][0]
        assert f52["role"] == "REJECTED_LIVE_PILOT_FIXTURE"
        assert f52["never_an_accepted_fixture"] is True
        assert len(vqp.ENGINE_BACKLOG) == 10


class VQ0DiagnosticTests(TestCase):
    """VQ-0 — visual failure baseline + improvement architecture.
    Pure, deterministic, no provider, no task/project modification."""

    def test_program_record_is_deterministic_and_complete(self):
        a = vqp.build_program_record()
        b = vqp.build_program_record()
        assert a["program_hash"] == b["program_hash"]
        assert a["schema_version"] == "final_visual_quality_program/1.0"
        assert a["status"] == "BASELINE_AND_ARCHITECTURE"
        fixtures = {f["task_id"]: f for f in a["fixtures"]}
        assert fixtures[51]["selected_image_id"] == 95
        assert fixtures[52]["selected_image_id"] == 97
        for f in fixtures.values():
            assert "HUMAN_REJECTED" in f["state"]
            assert "NEVER_ACCEPTED_FIXTURE" in f["state"]
        assert set(a["failure_taxonomy"]) == {
            "REFERENCE_INTERPRETATION", "STRUCTURAL_FORM",
            "MATERIAL_REALIZATION", "TYPOGRAPHY", "COMPOSITION",
            "VALIDATION"}
        assert len(a["decomposition_components"]) == 18
        assert len(a["workstreams"]) == 9
        assert len(a["success_criteria"]) == 11
        # scorecard critical minimums per §11
        sc = a["scorecard"]
        assert sc["structural_form"]["critical_min"] == 14
        assert sc["material_realization"]["critical_min"] == 14
        assert sc["selected_concept_preservation"]["critical_min"] == 7

    def test_diagnostic_seeds_detect_the_pilot_failure_classes(self):
        # photographic condensation is STYLING, never print (task #51)
        assert vqp.classify_reference_region("condensation droplets") == \
            "PHOTOGRAPHIC_STYLING_NOT_PRINTED_ARTWORK"
        assert vqp.classify_reference_region("printed wordmark") == \
            "CANDIDATE_DESIGN_CONTENT"
        # cylinder-as-rounded-rectangle (task #52 first render)
        assert "VQ_CYLINDER_AS_ROUNDED_RECTANGLE" in \
            vqp.perceived_form_findings(
                {"curve_segments": 4, "top_width_ratio": 1.0,
                 "has_shoulder_transition": False})
        assert vqp.perceived_form_findings(
            {"curve_segments": 5, "top_width_ratio": 0.30,
             "has_shoulder_transition": True}) == []
        # flat-pink metal is rejected
        assert "VQ_METAL_AS_FLAT_COLOR" in vqp.material_realization_findings(
            "POLISHED_ROSE_GOLD",
            [{"shape": "rect", "paint": "solid", "role": "base"}])
        assert vqp.material_realization_findings(
            "POLISHED_ROSE_GOLD",
            [{"shape": "path_curved", "paint": "gradient", "role": "base"},
             {"shape": "path_curved", "paint": "solid",
              "role": "highlight"},
             {"shape": "path_curved", "paint": "solid",
              "role": "shadow"}]) == []
        # stripe-only frosted glass is rejected
        assert "VQ_FROST_AS_STRIPES" in vqp.material_realization_findings(
            "FROSTED_GLASS", [{"shape": "rect", "opacity": 0.5}])
        # opaque-only frosted glass is rejected
        assert "VQ_TRANSPARENT_RENDERED_OPAQUE" in \
            vqp.material_realization_findings(
                "FROSTED_GLASS",
                [{"shape": "path_curved", "opacity": 1.0},
                 {"shape": "path_curved", "opacity": 0.98}])
        # split Rose / Damascena fails even with both live runs present
        assert vqp.typography_grouping_findings(
            [{"kind": "product_name", "y": 10.0, "size_pt": 9.0},
             {"kind": "product_name", "y": 30.0, "size_pt": 9.0}]) == \
            ["VQ_NAME_GROUPING_FAILED"]
        assert vqp.typography_grouping_findings(
            [{"kind": "product_name", "y": 10.0, "size_pt": 9.0},
             {"kind": "product_name", "y": 20.5, "size_pt": 9.0}]) == []

    def test_nominal_geometry_cannot_self_certify_and_human_overrides(self):
        # nominal PASS + perceived failure → visual failure, never a pass
        assert vqp.visual_verdict(
            perceived=["VQ_CYLINDER_AS_ROUNDED_RECTANGLE"], material=[],
            typography=[], nominal_ok=True,
            human_state="") == "VISUAL_FIDELITY_FAILED"
        # everything clean still only reaches PENDING HUMAN REVIEW
        assert vqp.visual_verdict(
            perceived=[], material=[], typography=[], nominal_ok=True,
            human_state="") == "PASSES_PENDING_HUMAN_REVIEW"
        # a human rejection is authoritative over every automated result
        assert vqp.visual_verdict(
            perceived=[], material=[], typography=[], nominal_ok=True,
            human_state="REJECTED / REVISION_REQUIRED") == \
            "REJECTED_BY_HUMAN"
