"""Complete Product parent/child model (Phase C1, 2026-07-09).

Selecting Complete Product creates a DesignProject + a first-stage container
child; it does NOT auto-advance to packaging yet (C2). Single-target
packaging/container creation is unchanged (project=None, stage="").
"""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.core.models import Brand
from apps.pipeline.models import DesignProject, DesignTask
from apps.pipeline.permissions import ROLE_DESIGNER
from apps.pipeline.targets import DesignTarget
from apps.pipeline.targets.composite import (
    create_composite_project,
    first_stage,
    is_composite,
)


class RecipeTests(TestCase):
    def test_complete_product_is_composite(self):
        assert is_composite(DesignTarget.COMPLETE_PRODUCT.value)
        assert not is_composite(DesignTarget.PACKAGING.value)
        assert not is_composite(DesignTarget.PRODUCT_CONTAINER.value)

    def test_first_stage_is_container(self):
        label, target = first_stage(DesignTarget.COMPLETE_PRODUCT.value)
        assert label == "container"
        assert target == DesignTarget.PRODUCT_CONTAINER.value


class CreateHelperTests(TestCase):
    def test_creates_project_and_container_child_only(self):
        brand = Brand.objects.create(name="B", master_brief="x")
        project, task = create_composite_project(
            brand=brand, product=None, brief="a full product",
            created_by=None, target=DesignTarget.COMPLETE_PRODUCT.value)
        assert project.status == "container"
        assert project.design_target == DesignTarget.COMPLETE_PRODUCT.value
        # exactly one child so far — the container stage
        children = list(project.tasks.all())
        assert len(children) == 1
        assert task.design_target == DesignTarget.PRODUCT_CONTAINER.value
        assert task.stage == "container"
        assert task.project_id == project.id
        assert task.task_text == "a full product"


class CreateViewCompositeTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        group, _ = Group.objects.get_or_create(name=ROLE_DESIGNER)
        self.user = User.objects.create_user("d", "d@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)

    def _create(self, **body):
        with patch("apps.core.health.worker_available", return_value=True), \
             patch("apps.pipeline.services.cost_ledger.daily_budget_exceeded",
                   return_value=False), \
             patch("apps.pipeline.tasks.run_aria_pipeline.delay") as delay:
            resp = self.client.post("/api/tasks/create/",
                                    {"design_target": "packaging", "task_text": "make a full product", **body})
            return resp, delay

    def test_complete_product_creates_project_plus_container_child(self):
        resp, delay = self._create(
            design_target=DesignTarget.COMPLETE_PRODUCT.value)
        assert resp.status_code == 201
        body = resp.json()
        assert "project_id" in body and "task_id" in body
        project = DesignProject.objects.get(id=body["project_id"])
        assert project.status == "container"
        task = DesignTask.objects.get(id=body["task_id"])
        assert task.design_target == DesignTarget.PRODUCT_CONTAINER.value
        assert task.stage == "container" and task.project_id == project.id
        delay.assert_called_once_with(task.id)     # container stage enqueued
        # no packaging child yet (no auto-advance in C1)
        assert project.tasks.count() == 1

    def test_packaging_creation_unchanged_no_project(self):
        resp, _ = self._create(design_target=DesignTarget.PACKAGING.value)
        assert resp.status_code == 201
        task = DesignTask.objects.get(id=resp.json()["task_id"])
        assert task.project_id is None and task.stage == ""
        assert DesignProject.objects.count() == 0

    def test_product_container_single_creation_unchanged_no_project(self):
        resp, _ = self._create(design_target=DesignTarget.PRODUCT_CONTAINER.value)
        assert resp.status_code == 201
        task = DesignTask.objects.get(id=resp.json()["task_id"])
        assert task.project_id is None and task.stage == ""
        assert DesignProject.objects.count() == 0
