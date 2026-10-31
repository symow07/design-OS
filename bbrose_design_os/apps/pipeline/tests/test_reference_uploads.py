"""Reference uploads (Phase B4b, 2026-07-09).

Optional per-task uploads: ingested at creation, shown on the Review Board as
"Reference Only", fed into concept grounding, and preferred over defaults
during container reconstruction. Isolated — packaging (no uploads) unchanged.
"""
from __future__ import annotations

import base64
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.core.models import Brand, Product
from apps.pipeline.agents.image_producer import ImageProducerAgent
from apps.pipeline.models import DesignTask, GeneratedImage, TaskReference
from apps.pipeline.permissions import ROLE_DESIGNER
from apps.pipeline.review_board import build_review_board
from apps.pipeline.targets import DesignTarget

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4"
    "z8Dwn4EBAAT/Af9jZv5kAAAAAElFTkSuQmCC")


def _upload(name="r.png"):
    return SimpleUploadedFile(name, _PNG, content_type="image/png")


class CreateWithUploadsTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        group, _ = Group.objects.get_or_create(name=ROLE_DESIGNER)
        self.user = User.objects.create_user("d", "d@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)

    def test_multipart_create_ingests_references_before_enqueue(self):
        with patch("apps.core.health.worker_available", return_value=True), \
             patch("apps.pipeline.services.cost_ledger.daily_budget_exceeded",
                   return_value=False), \
             patch("apps.pipeline.tasks.run_aria_pipeline.delay") as delay:
            # B4b-1 §8: dispatch moved to transaction.on_commit, so a task
            # whose reference persistence failed can never be enqueued. The
            # callback has to be executed for the assertion below to mean
            # anything.
            with self.captureOnCommitCallbacks(execute=True):
                # [the owner's answer of 2026-09-27: a gloss named with no container is asked at the door — "wand
                # vial or squeeze tube?" — and his answer rides the brief; it read "rose gloss" alone]
                resp = self.client.post("/api/tasks/create/", {
                    "task_text": "rose gloss\n\n[Container type: wand vial]", "brand_id": self.brand.id,
                    "design_target": DesignTarget.PRODUCT_CONTAINER.value,
                    "container": _upload("c.png"), "logo": _upload("l.png"),
                    "inspiration": [_upload("i1.png"), _upload("i2.png")],
                })
        assert resp.status_code == 201
        task = DesignTask.objects.get(id=resp.json()["task_id"])
        kinds = sorted(r.kind for r in task.references.all())
        assert kinds == ["container", "inspiration", "inspiration", "logo"]
        delay.assert_called_once()          # enqueued after refs attached

    def test_packaging_json_create_has_no_references(self):
        with patch("apps.core.health.worker_available", return_value=True), \
             patch("apps.pipeline.services.cost_ledger.daily_budget_exceeded",
                   return_value=False), \
             patch("apps.pipeline.tasks.run_aria_pipeline.delay"):
            resp = self.client.post("/api/tasks/create/",
                                    {"design_target": "packaging", "task_text": "a box"}, content_type="application/json")
        task = DesignTask.objects.get(id=resp.json()["task_id"])
        assert task.references.count() == 0


class ReviewBoardReferenceTests(TestCase):
    def test_uploads_show_as_reference_only(self):
        brand = Brand.objects.create(name="B", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="x")
        r = TaskReference(task=task, kind="container")
        r.image.save("c.png", ContentFile(_PNG), save=True)
        board = build_review_board(task)
        assert len(board.references) == 1
        assert board.references[0].label == "Reference Only"
        # B4b-3A §3: the owner-facing category label, shared with the
        # creation UI — no longer the raw model choice label
        assert board.references[0].name == "Container Reference"

    def test_no_uploads_empty_references(self):
        brand = Brand.objects.create(name="B", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="x")
        assert build_review_board(task).references == []


class GroundingUploadTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.task = DesignTask.objects.create(
            brand=self.brand, task_text="gloss",
            design_target=DesignTarget.PRODUCT_CONTAINER.value)

    @override_settings(MAX_DESIGN_REFERENCES=4)
    def test_uploads_ground_generation_and_logo_is_preferred(self):
        # B4b-3B: grounding is manifest-driven, so rows carry the full B4b-1
        # metadata every real creation path persists (an untyped legacy row
        # is not attachment-eligible — its content cannot be verified)
        for kind in ("logo", "container", "color"):
            r = TaskReference(task=self.task, kind=kind,
                              original_filename=f"{kind}.png",
                              media_type="image/png",
                              file_size=len(_PNG))
            r.image.save(f"{kind}.png", ContentFile(_PNG), save=True)
        agent = ImageProducerAgent(self.task, [])
        with patch("apps.pipeline.services.reference_index.select_references",
                   return_value=[]):
            paths, has_logo = agent._reference_inputs()
        assert has_logo                     # uploaded logo → grounding leads with it
        # container + colour are grounding inputs (logo separate)
        assert len(paths) == 3              # logo + container + color
        up = agent._uploaded_reference_paths()
        assert up["logo"] and len(up["grounding"]) == 2

    def test_no_uploads_leaves_grounding_unchanged(self):
        # a task with no uploads → helper is empty → packaging path intact
        agent = ImageProducerAgent(self.task, [])
        up = agent._uploaded_reference_paths()
        assert up == {"logo": None, "grounding": []}


class ReconstructPrefersUploadsTests(TestCase):
    @override_settings(OPENAI_API_KEY="")
    def test_reconstruct_uses_uploaded_logo_and_label(self):
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.targets.container import ProductContainerTarget

        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        product = Product.objects.create(
            brand=brand, product_id="CO-1", name="Rose Nectar",
            category="CO", year=2026, product_type="lip gloss")
        task = DesignTask.objects.create(
            brand=brand, product=product, task_text="gloss",
            status="gate_1_approved",
            design_target=DesignTarget.PRODUCT_CONTAINER.value)
        img = GeneratedImage.objects.create(
            task=task, direction_name="D", prompt_used="p", variation_number=1)
        img.image_file.save("c.png", ContentFile(_PNG), save=True)
        for kind in ("logo", "label"):
            r = TaskReference(task=task, kind=kind)
            r.image.save(f"{kind}.png", ContentFile(_PNG), save=True)

        aria = ARIAAgent(task.id)
        ProductContainerTarget().begin_output(aria, img)
        out = task.packaging_outputs.first()
        # the uploaded label is used (label path present in the emit) [the flat-artwork extraction it once
        # short-circuited was removed in the clean-up of 2026-10-04, E1]
        aria.resume_after_container_profile(out.id, {"archetype": "bottle"})
        out.refresh_from_db()
        assert out.design_preview_ai
