"""Complete Product stage orchestration (Phase C2, 2026-07-09).

advance_project runs the recipe stage-by-stage: container completion spawns
the packaging stage with the container design fed forward as references;
packaging completion completes the project. Idempotent + failure-aware, and
inert for single-target (project-less) tasks.
"""
from __future__ import annotations

import base64
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.test import TestCase

from apps.core.models import Brand, Product
from apps.pipeline.agents.aria import ARIAAgent
from apps.pipeline.models import (
    DesignProject,
    DesignTask,
    GeneratedImage,
    PackagingOutput,
    TaskReference,
)
from apps.pipeline.targets import DesignTarget
from apps.pipeline.targets.composite import advance_project, create_composite_project

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4"
    "z8Dwn4EBAAT/Af9jZv5kAAAAAElFTkSuQmCC")


class _Base(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-1", name="Rose Nectar",
            category="CO", year=2026, product_type="lip gloss")

    def _project_with_completed_container(self, with_logo=False):
        project, container = create_composite_project(
            brand=self.brand, product=self.product, brief="a full product",
            created_by=None, target=DesignTarget.COMPLETE_PRODUCT.value)
        img = GeneratedImage.objects.create(
            task=container, direction_name="D", prompt_used="p", variation_number=1)
        img.image_file.save("concept.png", ContentFile(_PNG), save=True)
        out = PackagingOutput.objects.create(
            task=container, approved_image=img, spec_sheet={"backend": "container", "container_human_visual_acceptance": {"state": "ACCEPTED", "decided_by": "u", "decided_at": "2026-07-24"}})
        out.design_preview.save("preview.png", ContentFile(_PNG), save=True)
        if with_logo:
            lref = TaskReference(task=container, kind="logo")
            lref.image.save("logo.png", ContentFile(_PNG), save=True)
        container.status = "completed"
        container.save()
        return project, container


class AdvanceSpawnsPackagingTests(_Base):
    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_container_completion_spawns_packaging_with_handoff(self, delay):
        project, container = self._project_with_completed_container(with_logo=True)
        advance_project(project)

        project.refresh_from_db()
        assert project.status == "packaging"
        pkg = project.tasks.get(stage="packaging")
        assert pkg.design_target == DesignTarget.PACKAGING.value
        assert pkg.project_id == project.id
        assert "Match the approved container design" in pkg.task_text
        # handoff references: rendered preview + approved concept + carried logo
        kinds = sorted(r.kind for r in pkg.references.all())
        assert kinds == ["container", "inspiration", "logo"]
        for r in pkg.references.all():
            assert r.image and r.image.size > 0        # real copied files
        delay.assert_called_once_with(pkg.id)          # packaging stage enqueued

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_advance_is_idempotent(self, delay):
        project, _ = self._project_with_completed_container()
        advance_project(project)
        advance_project(project)                       # second call must not duplicate
        assert project.tasks.filter(stage="packaging").count() == 1
        assert delay.call_count == 1

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_packaging_producer_consumes_handoff_grounding(self, delay):
        # Closes the loop: the handoff TaskReferences aren't just rows — the
        # packaging concept run's ImageProducer must actually surface them as
        # grounding inputs (reuses B4b _reference_inputs, the whole point of C2).
        from apps.pipeline.agents.image_producer import ImageProducerAgent

        project, _ = self._project_with_completed_container(with_logo=True)
        advance_project(project)
        pkg = project.tasks.get(stage="packaging")

        paths, has_logo = ImageProducerAgent(pkg, prompts={})._reference_inputs()
        assert has_logo                                # carried logo surfaced
        names = [p.rsplit("/", 1)[-1] for p in paths]
        cid = project.tasks.get(stage="container").id
        # the fed-forward container preview + approved concept reach generation
        # (storage may append a suffix on name collisions across runs → prefix)
        assert any(n.startswith(f"handoff_{cid}_preview") for n in names)
        assert any(n.startswith(f"handoff_{cid}_concept") for n in names)


class CompletionTests(_Base):
    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_packaging_completion_completes_project(self, delay):
        project, _ = self._project_with_completed_container()
        advance_project(project)                       # spawns packaging
        pkg = project.tasks.get(stage="packaging")
        pkg.status = "completed"
        pkg.save()
        # 2C-1 §7: packaging's human decision (Gate-2 approve) is required
        from apps.pipeline.models import GateDecision
        GateDecision.objects.create(task=pkg, gate="gate_2",
                                    decision="approve")
        advance_project(project)
        project.refresh_from_db()
        assert project.status == "completed"
        assert project.failed_stage == ""
        # a further advance is a harmless no-op
        advance_project(project)
        assert project.tasks.count() == 2


class FailureResumeTests(_Base):
    def test_fail_marks_project_failed_then_retry_advances(self):
        project, container = create_composite_project(
            brand=self.brand, product=self.product, brief="p",
            created_by=None, target=DesignTarget.COMPLETE_PRODUCT.value)
        aria = ARIAAgent(container.id)
        aria._fail("boom")
        project.refresh_from_db()
        assert project.status == "failed" and project.failed_stage == "container"

        # retry succeeds: container completes → advance proceeds to packaging
        img = GeneratedImage.objects.create(
            task=container, direction_name="D", prompt_used="p", variation_number=1)
        img.image_file.save("c.png", ContentFile(_PNG), save=True)
        out = PackagingOutput.objects.create(task=container, approved_image=img,
                                             spec_sheet={"backend": "container", "container_human_visual_acceptance": {"state": "ACCEPTED", "decided_by": "u", "decided_at": "2026-07-24"}})
        out.design_preview.save("p.png", ContentFile(_PNG), save=True)
        container.status = "completed"
        container.save()
        with patch("apps.pipeline.tasks.run_aria_pipeline.delay"):
            advance_project(project)
        project.refresh_from_db()
        assert project.status == "packaging" and project.failed_stage == ""


class ParityTests(_Base):
    def test_single_target_completion_never_touches_a_project(self):
        # a project-less task completing must not create/advance any project
        task = DesignTask.objects.create(
            brand=self.brand, task_text="a box", status="awaiting_gate_2")
        img = GeneratedImage.objects.create(
            task=task, direction_name="D", prompt_used="p", variation_number=1)
        out = PackagingOutput.objects.create(task=task, approved_image=img,
                                             spec_sheet={
        "container_human_visual_acceptance": {
            "state": "ACCEPTED", "decided_by": "u",
            "decided_at": "2026-07-24"}})
        ARIAAgent(task.id).resume_after_gate_2(out.id)
        task.refresh_from_db()
        assert task.status == "completed"
        assert DesignProject.objects.count() == 0

    def test_fail_on_project_less_task_is_inert(self):
        task = DesignTask.objects.create(brand=self.brand, task_text="x",
                                         status="running")
        ARIAAgent(task.id)._fail("nope")
        assert DesignProject.objects.count() == 0


class TheContainerSizesTheCartonTests(_Base):
    """§BH55 PHASE 1 — "The target ships: container and packaging as one multi-stage project." Until now the packaging
    stage of a project estimated its carton FROM SCRATCH — a paid guess that had never heard of the bottle it was
    boxing. It reads the container stage's own confirmed dimensions now, plus the fit the owner's own record shows."""

    PROFILE = {"fields": {"body_width_mm": {"value": 33.0}, "body_depth_mm": {"value": 33.0},
                          "body_height_mm": {"value": 68.0}, "cap_height_mm": {"value": 14.0}}}

    def _packaging_stage(self, spec_extra):
        project, container = self._project_with_completed_container()
        out = container.packaging_outputs.first()
        out.spec_sheet = {**out.spec_sheet, **spec_extra}
        out.save(update_fields=["spec_sheet"])
        with patch("apps.pipeline.tasks.run_aria_pipeline.delay"):
            advance_project(project)
        return project.tasks.get(stage="packaging")

    def test_the_carton_is_sized_from_the_container_stage_with_no_paid_guess(self):
        from apps.pipeline.agents import dieline_agent as da
        pkg = self._packaging_stage({"container_profile/1.0": self.PROFILE,
                                     "container_drawing_source/1.0": {"geometry": {"total_height_mm": 96.306}}})
        with patch.object(da.DielineAgent, "_call_claude", side_effect=AssertionError("a paid estimate was asked for")):
            result, job = da.DielineAgent(pkg).run()
        # product 5's own record, reproduced: 33 × 33 drawn 96.306 tall → the 40 × 40 × 110 carton he recorded
        assert (result.width_mm.value, result.depth_mm.value, result.height_mm.value) == (40.0, 40.0, 110.0)
        assert {f.source for f in (result.width_mm, result.depth_mm, result.height_mm)} == {"container"}
        assert result.width_mm.confidence == 0.85 and result.can_proceed and result.scenario == "A"
        assert job.scenario == "A" and job.product_id == pkg.product_id
        # with no drawn total on the record the height is body + cap, and says so by being shorter
        pkg2 = self._packaging_stage({"container_profile/1.0": self.PROFILE})
        result2, _job = da.DielineAgent(pkg2).run()
        assert result2.height_mm.value == round(68.0 + 14.0 + 2 * da.CONTAINER_FIT_END_MM, 2)

    def test_bh70_a_compacts_carton_lies_flat_on_the_same_die_and_fits_the_tuck_end(self):
        """§BH70(1), items 8 and 16 of the list the owner was sent: a compact's record holds its lid seen from above and
        its closed thickness; read as a standing bottle's, its carton came out 117 x 25 x 108.7 mm, wider than tall, and
        the straight tuck-end carton it defaults to refused it. Stood on its edge it is 102 x 25 x 123.7 mm, says so,
        and the tuck-end holds it. The fit margins — measured on a dropper, frozen by §BH55(3) — are not touched.
        [His goal of 2026-10-13, (2): "A palette or compact lies flat: its box's front is the lid's face (landscape)."]
        The same die — its tucks on the narrow ends — is the box lying flat, its front the lid's face; it says so."""
        from apps.dielines.validators.schema import DielineInputJSON
        from apps.pipeline.agents import dieline_agent as da
        compact = {"archetype": "compact", "fields": {"body_width_mm": {"value": 110.0}, "body_depth_mm": {"value": 18.0},
                                                      "body_height_mm": {"value": 95.0}}}
        pkg = self._packaging_stage({"container_profile/1.0": compact})
        with patch.object(da.DielineAgent, "_call_claude", side_effect=AssertionError("a paid estimate was asked for")):
            result, _job = da.DielineAgent(pkg).run()
        dims = {k: getattr(result, k).value for k in ("width_mm", "depth_mm", "height_mm")}
        assert dims == {"width_mm": 95.0 + 2 * da.CONTAINER_FIT_SIDE_MM, "depth_mm": 18.0 + 2 * da.CONTAINER_FIT_SIDE_MM,
                        "height_mm": round(110.0 + 2 * da.CONTAINER_FIT_END_MM, 2)}, dims
        assert {getattr(result, k).source for k in dims} == {"container lying flat"} and result.orientation == "flat"
        DielineInputJSON.model_validate({"template": "straight_tuck_end_carton", "unit": "mm", "dimensions": dims,
                                         "print_settings": {}, "construction": {},
                                         "metadata": {"product_name": "x", "product_type": "carton"}})

    def test_bh71_a_tins_and_a_sachets_carton_is_raised_to_the_smallest_the_tuck_end_makes(self):
        """§BH71 PART 3, the owner's goal of 2026-09-28: \"Add each as a shape the system can draw.\" A tin 42 mm across,
        stood on its edge, came to a carton 55.7 mm tall, and a sachet 3 mm thin to one 10 mm deep — under the carton
        template's own hard minimums (60 mm tall, 12 mm wide and deep), so the straight tuck-end refused the carton it
        was proposed (the bottle audit's items 8 and 16, re-opened by the new forms). Each side under its minimum is
        raised to it and the activity says which, from what, to what; the tuck-end holds it; the fit margins are not
        touched, and a carton over its minimums is as it was (the dropper's and the compact's, above)."""
        from apps.dielines.validators.schema import DielineInputJSON
        from apps.pipeline.agents import dieline_agent as da
        assert da.carton_minimums() == {"width_mm": 12.0, "depth_mm": 12.0, "height_mm": 60.0}
        cases = (
            ({"archetype": "tin", "variant": "round", "fields": {
                "body_width_mm": {"value": 42.0}, "body_depth_mm": {"value": 18.0}, "body_height_mm": {"value": 42.0}}},
             {"width_mm": 42.0 + 2 * da.CONTAINER_FIT_SIDE_MM, "depth_mm": 18.0 + 2 * da.CONTAINER_FIT_SIDE_MM,
              "height_mm": 60.0}, "height 55.7 → 60 mm"),
            ({"archetype": "sachet", "variant": "three_side", "fields": {
                "body_width_mm": {"value": 125.0}, "body_depth_mm": {"value": 3.0}, "body_height_mm": {"value": 180.0}}},
             {"width_mm": 125.0 + 2 * da.CONTAINER_FIT_SIDE_MM, "depth_mm": 12.0,
              "height_mm": round(180.0 + 2 * da.CONTAINER_FIT_END_MM, 2)}, "depth 10.0 → 12 mm"))
        for record, want, words in cases:
            pkg = self._packaging_stage({"container_profile/1.0": record})
            said = []
            with patch.object(da.DielineAgent, "_call_claude", side_effect=AssertionError("a paid estimate was asked for")):
                result, _job = da.DielineAgent(pkg, log_fn=lambda msg, *a, **k: said.append(msg)).run()
            dims = {k: getattr(result, k).value for k in ("width_mm", "depth_mm", "height_mm")}
            assert dims == want, (record["archetype"], dims)
            assert any("raised to the smallest the carton template makes" in m and words in m for m in said), said
            DielineInputJSON.model_validate({"template": "straight_tuck_end_carton", "unit": "mm", "dimensions": dims,
                                             "print_settings": {}, "construction": {},
                                             "metadata": {"product_name": "x", "product_type": "carton"}})

    def test_the_products_own_carton_dimensions_win_and_a_lone_packaging_task_is_unchanged(self):
        from apps.pipeline.agents import dieline_agent as da
        pkg = self._packaging_stage({"container_profile/1.0": self.PROFILE})
        self.product.width_mm, self.product.depth_mm, self.product.height_mm = 45, 45, 120
        self.product.save()
        pkg.refresh_from_db()
        result, _job = da.DielineAgent(pkg).run()
        assert (result.width_mm.value, result.width_mm.source) == (45.0, "db")          # his own record wins
        lone = DesignTask.objects.create(task_text="t", brand=self.brand, design_target="packaging")
        assert da.DielineAgent(lone)._container_dimensions() is None                    # no project: the old path
