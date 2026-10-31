"""Design Review Board — structured approval data (RB1, 2026-07-08).

Pins the renderer-agnostic contract: build_review_board(task) assembles the
six sections from real task data (packaging), stays safe on early-stage
tasks, and is exposed additively on the task-status endpoint without
disturbing the existing keys or the gate flow.
"""
from __future__ import annotations

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.core.models import Brand, Product
from apps.pipeline.models import (
    DesignTask,
    GateDecision,
    GeneratedImage,
    PackagingOutput,
)
from apps.pipeline.permissions import ROLE_REVIEWER
from apps.pipeline.review_board import ReviewBoardData, build_review_board
from apps.pipeline.targets import DesignTarget
from apps.pipeline.targets.packaging import PackagingTarget


class BuildReviewBoardTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-1", name="Rose Nectar",
            category="CO", year=2026, product_type="lip gloss")
        self.user = User.objects.create_user("rev", "r@t.com", "pw")

    def _task(self, **kw):
        kw.setdefault("status", "awaiting_gate_1")
        return DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="a box", **kw)

    def test_header_reflects_brand_product_and_target(self):
        board = build_review_board(self._task())
        assert board.header.brand == "BBROSE"
        assert board.header.product == "Rose Nectar"
        assert board.header.target == "Packaging"           # default target label
        assert board.header.version.startswith("Design #")      # §BH55 Phase 3: was "Task #"
        assert board.header.ai_version                        # model ids present

    def test_concepts_come_from_current_images(self):
        task = self._task()
        from apps.pipeline.tests.quality_fixtures import reviewed
        for i in range(3):
            image = GeneratedImage.objects.create(task=task, direction_name=f"D{i}", prompt_used="p", variation_number=i+1)
            reviewed(image, 9 if i == 0 else 5)
        board = build_review_board(task)
        assert len(board.concepts) == 1
        assert board.concepts[0].direction_name == 'D0'

    def test_selected_and_specifications_from_packaging_output(self):
        task = self._task(status="awaiting_gate_2")
        img = GeneratedImage.objects.create(
            task=task, direction_name="D", prompt_used="p", variation_number=1,
            is_approved=True)
        PackagingOutput.objects.create(
            task=task, approved_image=img, spec_sheet={
                "template": "straight_tuck_end_carton",
                "confirmed_dimensions": {"width_mm": 35, "depth_mm": 25,
                                         "height_mm": 95, "glue_tab_mm": 12}})
        board = build_review_board(task)
        assert board.selected.approved_concept_id == img.id
        labels = {r.label for r in board.specifications}
        assert "Template" in labels and "Dimensions" in labels
        dim = next(r for r in board.specifications if r.label == "Dimensions")
        assert dim.value == "35 × 25 × 95 mm"

    def test_the_comparison_is_captioned_in_words(self):
        # §BH55 Phase 3: the captions read "Selected concept #N · <its variation code>" and "Current native
        # reconstruction"
        task = self._task(status="awaiting_gate_2")
        img = GeneratedImage.objects.create(
            task=task, direction_name="D", prompt_used="p", variation_number=1,
            is_approved=True, image_file="generated/c.png")
        PackagingOutput.objects.create(task=task, approved_image=img, spec_sheet={},
                                       design_preview="packaging/p.png")
        board = build_review_board(task)
        assert board.comparison.selected_caption == "The concept you chose"
        assert board.comparison.reconstruction_caption == "The design made from it"

    def test_approval_history_from_gate_decisions(self):
        task = self._task()
        GateDecision.objects.create(
            task=task, gate="gate_1", decision="approve",
            notes="looks good", decided_by=self.user)
        board = build_review_board(task)
        assert board.approval.status == "awaiting_gate_1"
        assert len(board.approval.history) == 1
        ev = board.approval.history[0]
        assert ev.gate == "gate_1" and ev.decision == "approve"
        assert ev.decided_by == "rev"

    def test_references_are_flagged_reference_only(self):
        board = build_review_board(self._task())
        assert all(r.label == "Reference Only" for r in board.references)

    def test_safe_on_early_stage_task_with_no_output_or_images(self):
        board = build_review_board(self._task(status="queued"))
        assert isinstance(board, ReviewBoardData)
        assert board.concepts == [] and board.specifications == []
        assert board.selected.approved_concept_id is None

    def test_container_target_gets_no_packaging_specs(self):
        # a non-packaging target simply yields its own (here empty) specs,
        # proving the section is target-driven, not hardcoded
        task = self._task(design_target=DesignTarget.PRODUCT_CONTAINER.value)
        board = build_review_board(task)
        assert board.header.target == "Product Container"
        assert board.specifications == []       # container specs land in B3


class PackagingReviewSectionsTests(TestCase):
    def test_empty_when_no_output_yet(self):
        brand = Brand.objects.create(name="B", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="x")
        assert PackagingTarget().review_sections(task) == []


class TaskStatusPayloadTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        group, _ = Group.objects.get_or_create(name=ROLE_REVIEWER)
        self.user = User.objects.create_user("u", "u@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)

    def test_review_board_is_additive_on_task_status(self):
        task = DesignTask.objects.create(brand=self.brand, task_text="a box",
                                         status="awaiting_gate_1")
        resp = self.client.get(f"/api/tasks/{task.id}/status/")
        assert resp.status_code == 200
        data = resp.json()
        # existing keys untouched (parity)
        for key in ("id", "status", "images", "packaging_output",
                    "gate_decisions", "panel_info"):
            assert key in data
        # new additive key with the six sections (+ the B4b-3A flag telling
        # the renderer whether this target accepts reference uploads)
        assert "review_board" in data
        assert set(data["review_board"]) == {
            "header", "concepts", "selected", "comparison", "references",
            "references_expected", "specifications", "approval"}
