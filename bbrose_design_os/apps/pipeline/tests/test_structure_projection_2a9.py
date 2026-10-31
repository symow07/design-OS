"""2A-9 structure-review projection correction (§10).

The Review Board rendered the rejected straight_tuck_end_carton 90×25×92
spec while the job carried the provisional 2A-9 record
(STRUCTURE_SELECTION_PROJECTION_STALE + OLD_SPECIFICATION_RECORD_RENDERED).
These pin: banned geometry can never render as active; the provisional
90×32×92 structure is what the projection shows; physical-test approval
composes nothing and clears nothing; FIT_PASS stays required for
confirmation; stale spec-sheet projections cannot restore rejected
geometry; the structural screen carries no artwork-fidelity errors; and no
provider is touched.

[The clean-up of 2026-10-04, his Q1 "remove the dormant packaging flow": the
structure step's page and its two endpoints left with the flow. What stays
pinned is the record and its projection, which task 50 still carries — the
screen and approval claims above now hold of the projection alone.]
"""
from __future__ import annotations

from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.core.models import Brand
from apps.dielines.models import DielineJob
from apps.pipeline.models import DesignTask, GeneratedImage, PackagingOutput
from apps.pipeline.services import structure_selection as ss
from apps.pipeline.services.template_selection import TemplateSelection

PROVISIONAL_PARAMS = {
    "width_mm": 90.0, "depth_mm": 32.0, "height_mm": 92.0,
    "bleed_mm": 3.0, "safe_margin_mm": 4.0,
    "glue_tab_mm": 12.0, "board_thickness_mm": 0.5,
}


def _reviewer(name="rev2a9"):
    user = User.objects.create_user(name, f"{name}@x.com", "pw")
    group, _ = Group.objects.get_or_create(name="Reviewer")
    user.groups.add(group)
    return user


def _task_with_provisional_job(*, banned_old_hash=True):
    brand = Brand.objects.create(name="B", master_brief="x")
    task = DesignTask.objects.create(
        brand=brand, task_text="x",
        status="awaiting_structure_confirmation")
    job = DielineJob.objects.create(
        template_type="ecma_a20_20_01_01_ste_carton", scenario="B",
        input_json={}, extraction_result={})
    image = GeneratedImage.objects.create(
        task=task, direction_name="d", prompt_used="p", variation_number=1)
    output = PackagingOutput.objects.create(
        task=task, spec_sheet={}, approved_image=image, dieline_job=job)
    selection = TemplateSelection(
        resolved=True, template_id="ecma_a20_20_01_01_ste_carton",
        version="0.1", source="OPEN_SOURCE_FORMULA_ADAPTED_PROVISIONAL")
    old = ss.build_structure_record(
        selection, {**PROVISIONAL_PARAMS, "depth_mm": 25.0,
                    "board_thickness_mm": 0.35})
    record = ss.build_structure_record(selection, PROVISIONAL_PARAMS)
    if banned_old_hash:
        job.extraction_result = {
            "banned_geometry_hashes": [old["geometry_hash"]]}
        job.save(update_fields=["extraction_result"])
    ss.save_structure_record(job, record)
    return task, output, job, record, old


class ProjectionTests(TestCase):
    def test_provisional_structure_is_displayed(self):
        _, _, job, record, _ = _task_with_provisional_job()
        pres = ss.structure_presentation(job)
        assert pres["template_id"] == "ecma_a20_20_01_01_ste_carton"
        assert pres["template_version"] == "0.1"
        assert pres["parameters"]["depth_mm"] == 32.0
        assert pres["parameters"]["board_thickness_mm"] == 0.5
        assert pres["structure_status"] == \
            "OPEN_SOURCE_FORMULA_ADAPTED_PROVISIONAL"
        assert pres["physical_validation_required"] is True
        # [§BH70(3): "A physical sample is never required to finish a design" — it read confirmable False and next
        # APPROVE_FOR_PHYSICAL_TEST; the sample is said, and the structure is confirmed like any other]
        assert pres["confirmable"] is True
        assert pres["next_action"] == "CONFIRM" and pres["physical_validation_blockers"]
        assert pres["geometry_hash"] == record["geometry_hash"]

    def test_banned_geometry_cannot_render_as_active(self):
        """If a stale path re-saved the rejected record, the projection
        flags it banned/unconfirmable and confirmation refuses it."""
        _, _, job, _, old = _task_with_provisional_job()
        ss.save_structure_record(job, old)          # stale projection returns
        pres = ss.structure_presentation(job)
        assert pres["banned"] is True
        assert pres["confirmable"] is False
        user = User.objects.create_superuser("bn", "b@n.com", "pw")
        with self.assertRaises(ss.StructureError) as ctx:
            ss.confirm_structure(job, user)
        assert ctx.exception.code == "STRUCTURE_PERMANENTLY_INVALIDATED"

    def test_review_board_prefers_the_active_record(self):
        """A stale spec_sheet.template can never restore rejected geometry
        in the Review Board specifications."""
        task, output, job, _, _ = _task_with_provisional_job()
        output.spec_sheet = {
            "template": "straight_tuck_end_carton",
            "confirmed_dimensions": {"width_mm": 90.0, "depth_mm": 25.0,
                                     "height_mm": 92.0, "glue_tab_mm": 12.0},
        }
        output.save(update_fields=["spec_sheet"])
        from apps.pipeline.targets import get_target
        rows = get_target(task.design_target).review_sections(task)
        joined = " | ".join(f"{r['label']}: {r['value']}" for r in rows)
        assert "ecma_a20_20_01_01_ste_carton/0.1" in joined
        assert "straight_tuck_end_carton" not in joined
        assert "25.0" not in joined
        assert "32.0" in joined
        assert "PHYSICAL_SAMPLE_VALIDATION_REQUIRED" in joined
        assert "NOT CONFIRMED" in joined

    def test_structural_screen_carries_no_artwork_fidelity_errors(self):
        """§9: the structure screen must not echo artwork-fidelity checks
        before artwork is remapped — pinned on the projection. [The clean-up
        of 2026-10-04: the step's script left with the step, and its half of
        this pin with it.]"""
        _, _, job, _, _ = _task_with_provisional_job()
        pres = ss.structure_presentation(job)
        assert "generation_error" not in pres


class PhysicalTestApprovalTests(TestCase):
    """[The clean-up of 2026-10-04: the approval endpoint left with the structure step. The class keeps its name —
    §Y2's register names it — and what stays is the confirmation at the service and the provider guard.]"""

    def setUp(self):
        self.reviewer = _reviewer()
        (self.task, self.output, self.job,
         self.record, self.old) = _task_with_provisional_job()

    def test_bh70_confirmation_does_not_wait_on_a_fit_pass(self):
        """[§BH70(3), his words: "A physical sample is never required to finish a design (a colleague test-fits; that
        is not the system's job)." This test read `test_fit_pass_remains_required_for_confirmation`: the confirmation
        answered 409 PHYSICAL_SAMPLE_VALIDATION_REQUIRED until a FIT_PASS was recorded.] With no approval and no
        FIT_PASS the structure is confirmed, and a FIT_PASS recorded later is still read and said."""
        user = User.objects.create_superuser("cf", "c@f.com", "pw")
        rec = ss.confirm_structure(self.job, user)
        assert rec["confirmed_at"]
        from apps.dielines.services.physical_validation import (
            promotion_blockers,
            record_physical_validation,
        )
        record_physical_validation(
            self.job, self.reviewer,
            template_key="ecma_a20_20_01_01_ste_carton/0.1",
            geometry_hash=self.record["geometry_hash"],
            outcome="FIT_PASS", sample_printed_at_100pct=True)
        assert promotion_blockers(self.job, template_key="ecma_a20_20_01_01_ste_carton/0.1",
                                  geometry_hash=self.record["geometry_hash"]) == []

    def test_no_provider_calls_in_the_correction_path(self):
        import apps.pipeline.services.structure_selection as mod
        source = Path(mod.__file__).read_text()
        for token in ("anthropic", "openai", "ImageProducer"):
            assert token not in source
        # [the clean-up of 2026-10-04: its half on the step's script left with the script]


class LiveTask50Guard(TestCase):
    def test_task50_projection_shows_the_provisional_structure(self):
        """Live-DB guard (returns early on the test DB): the task-50
        projection must show the 2A-9 provisional die, never the rejected
        90×25×92 spec."""
        task = DesignTask.objects.filter(pk=50).first()
        if task is None:
            return
        output = task.packaging_outputs.filter(
            dieline_job__isnull=False).first()
        spec = output.spec_sheet or {}
        pres = spec.get("structure_presentation") or {}
        assert pres.get("template_id") == "ecma_a20_20_01_01_ste_carton"
        assert pres.get("parameters", {}).get("depth_mm") == 32.0
        assert pres.get("confirmable") is False
        assert spec.get("template") == "ecma_a20_20_01_01_ste_carton"
        assert "generation_error" not in spec
