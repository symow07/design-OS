"""Coordinator read-model for the Complete Product UX (Phase C3, 2026-07-09).

build_project_summary is recipe ⋈ children: canonical stages from the recipe,
overlaid with each existing child. It feeds the breadcrumb, cross-stage
navigation and the project-completed summary — all N-stage generic. Single
tasks never reach it: the status endpoint returns project=None for them.
"""
from __future__ import annotations

import base64

from django.contrib.auth.models import Group, User
from django.core.files.base import ContentFile
from django.test import TestCase

from apps.core.models import Brand, Product
from apps.pipeline.models import (
    DesignTask,
    GateDecision,
    GeneratedImage,
    PackagingOutput,
)
from apps.pipeline.permissions import ROLE_DESIGNER
from apps.pipeline.targets import DesignTarget
from apps.pipeline.targets.composite import (
    build_project_summary,
    create_composite_project,
)

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4"
    "z8Dwn4EBAAT/Af9jZv5kAAAAAElFTkSuQmCC")


class _Base(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-1", name="Rose Nectar",
            category="CO", year=2026, product_type="lip gloss")

    def _project(self):
        return create_composite_project(
            brand=self.brand, product=self.product, brief="a full product",
            created_by=None, target=DesignTarget.COMPLETE_PRODUCT.value)

    def _complete(self, task, *, dieline=False):
        img = GeneratedImage.objects.create(
            task=task, direction_name="D", prompt_used="p", variation_number=1)
        img.image_file.save("c.png", ContentFile(_PNG), save=True)
        spec = {"backend": "x"}
        if task.design_target == DesignTarget.PRODUCT_CONTAINER.value:
            # VQR-6: container result surfaces are contract-driven — a stage
            # advertises only artifacts its confirmed-profile lifecycle
            # vouches for, so completed container children carry the
            # confirmation evidence the real flow persists.
            spec["container_confirmation"] = {
                "combined_hash": "c0ffee" * 8, "confirmed_by": "summary",
                "confirmed_at": "2026-08-01T00:00:00+00:00",
                "authority": "HUMAN_CONFIRMED_CONCEPT_ONLY"}
            spec["container_resume"] = {
                "celery_task_id": "celery-summary",
                "requested_at": "2026-08-01T00:00:01+00:00",
                "requested_by": "summary", "kind": "INITIAL_CONFIRMATION"}
            GateDecision.objects.create(
                task=task, gate="container_profile", decision="approve")
        out = PackagingOutput.objects.create(
            task=task, approved_image=img, spec_sheet=spec)
        out.design_preview.save("prev.png", ContentFile(_PNG), save=True)
        out.design_preview_ai.save("design.ai", ContentFile(b"%PDF-ai"), save=True)
        if dieline:
            out.dieline_ai_file.save("die.ai", ContentFile(b"%PDF-die"), save=True)
        task.status = "completed"
        task.save()
        return out


class ShapeTests(_Base):
    def test_recipe_join_children_with_pending_downstream(self):
        # Fresh project: only the container child exists; packaging is pending.
        project, container = self._project()
        summ = build_project_summary(project)

        assert summ["id"] == project.id
        assert summ["target"] == "Complete Product"
        assert summ["status"] == "container"
        assert [s["label"] for s in summ["stages"]] == ["container", "packaging"]

        c, p = summ["stages"]
        assert c["task_id"] == container.id
        assert c["target"] == "Product Container"
        assert c["is_current"] is True           # project.status names container
        # packaging not spawned yet → pending, no task to navigate to
        assert p["task_id"] is None
        assert p["status"] == "pending"
        assert p["target"] == "Packaging"
        assert p["is_current"] is False

    def test_deliverable_labels_follow_child_target(self):
        # container structural file is labelled a "Container Structure", not a
        # generic "dieline"; packaging's is a "Dieline".
        project, container = self._project()
        self._complete(container, dieline=True)
        # spawn + complete packaging so both stages carry deliverables
        pkg = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="box",
            design_target=DesignTarget.PACKAGING.value, stage="packaging",
            project=project, status="queued")
        self._complete(pkg, dieline=True)

        summ = build_project_summary(project)
        c, p = summ["stages"]
        c_labels = {d["label"] for d in c["deliverables"]}
        p_labels = {d["label"] for d in p["deliverables"]}
        assert "Container Structure .ai" in c_labels
        assert "Dieline .ai" not in c_labels
        assert "Dieline .ai" in p_labels
        assert "Container Structure .ai" not in p_labels
        # both stages expose the editable design + hero preview + spec sheet
        for stage in (c, p):
            labels = {d["label"] for d in stage["deliverables"]}
            assert "Editable Design .ai" in labels
            assert "Spec Sheet PDF" in labels
            assert stage["hero_url"]

    def test_completed_project_marks_no_current_stage(self):
        project, container = self._project()
        self._complete(container)
        pkg = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="box",
            design_target=DesignTarget.PACKAGING.value, stage="packaging",
            project=project, status="queued")
        self._complete(pkg)
        project.status = "completed"
        project.save()

        summ = build_project_summary(project)
        assert summ["status"] == "completed"
        assert all(not s["is_current"] for s in summ["stages"])
        assert all(s["status"] == "completed" for s in summ["stages"])


class StatusEndpointTests(_Base):
    def setUp(self):
        super().setUp()
        group, _ = Group.objects.get_or_create(name=ROLE_DESIGNER)
        self.user = User.objects.create_user("d", "d@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)

    def test_project_child_status_carries_project_block(self):
        project, container = self._project()
        resp = self.client.get(f"/api/tasks/{container.id}/status/")
        assert resp.status_code == 200
        proj = resp.json()["project"]
        assert proj is not None
        assert proj["id"] == project.id
        assert [s["label"] for s in proj["stages"]] == ["container", "packaging"]

    def test_single_target_task_status_project_is_null(self):
        # Parity: a project-less task's status payload adds only project=None,
        # everything else unchanged.
        task = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="just a box",
            design_target=DesignTarget.PACKAGING.value, status="queued")
        resp = self.client.get(f"/api/tasks/{task.id}/status/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["project"] is None
        assert "review_board" in body        # existing keys intact
