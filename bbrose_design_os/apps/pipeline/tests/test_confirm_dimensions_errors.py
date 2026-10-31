"""Dimension-gate error surfacing (2026-07-07).

The Amber Hour palette entered landscape dimensions (150w x 105h), which the
straight_tuck_end_carton template rightly rejects (height must exceed width) —
but the 400 response crashed while serializing pydantic v2's error dicts
(ctx carries the raised ValueError object), so the user saw a bare
"Generation failed" 500 instead of the actual rule.
"""
from __future__ import annotations

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.core.models import Brand
from apps.dielines.models import DielineJob
from apps.pipeline.models import DesignTask, GeneratedImage, PackagingOutput
from apps.pipeline.permissions import ROLE_REVIEWER


class ConfirmDimensionsErrorTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        group, _ = Group.objects.get_or_create(name=ROLE_REVIEWER)
        self.user = User.objects.create_user("r", "r@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)
        self.task = DesignTask.objects.create(
            brand=self.brand, task_text="palette carton",
            status="awaiting_dimensions",
        )
        job = DielineJob.objects.create(
            template_type="straight_tuck_end_carton", scenario="B",
            input_json={},
        )
        img = GeneratedImage.objects.create(
            task=self.task, direction_name="d", prompt_used="p",
            variation_number=1,
        )
        PackagingOutput.objects.create(
            task=self.task, dieline_job=job, spec_sheet={}, approved_image=img,
        )

    def test_structural_rule_reaches_the_ui_as_json(self):
        resp = self.client.post(
            f"/api/tasks/{self.task.id}/confirm_dimensions/",
            {"dimensions": {"width_mm": 150, "depth_mm": 20, "height_mm": 105}},
            content_type="application/json",
        )
        assert resp.status_code == 400          # not a 500
        data = resp.json()                      # serializable
        assert data["error"] == "Invalid dimensions"
        assert any("height_mm" in d["msg"] and "width_mm" in d["msg"]
                   for d in data["details"])

    def test_his_findings_123_his_confirmed_size_is_kept_before_anything_is_drawn_and_both_checks_use_it(self):
        """[His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (7): "The
        concept check and drawing check use the confirmed size once known."] His 57 x 37 x 123 kept on the output as he
        confirms it — 123's was kept only in the log and its stop's words once the drawing's check stopped it — shown
        again at the size step, and the front's copy settled at it where it is drawn (his (4)), never at the size
        proposed."""
        from unittest import mock

        from apps.pipeline.agents.dieline_agent import DielineAgent
        from apps.pipeline.targets import container as C
        with mock.patch("apps.pipeline.tasks.resume_aria_dimensions.delay") as resume:
            resp = self.client.post(f"/api/tasks/{self.task.id}/confirm_dimensions/",
                                    {"dimensions": {"width_mm": 57, "depth_mm": 37, "height_mm": 123}},
                                    content_type="application/json")
        assert resp.status_code == 200, resp.content
        assert resume.called
        kept = PackagingOutput.objects.get(task=self.task).spec_sheet[C.CONFIRMED_SIZE_KEY]["dims"]
        assert (kept["width_mm"], kept["depth_mm"], kept["height_mm"]) == (57.0, 37.0, 123.0)
        from apps.pipeline.targets.packaging import PackagingTarget
        measured = []
        with mock.patch.object(PackagingTarget, "carton_front", return_value={"shapes": {}}), \
                mock.patch.object(DielineAgent, "proposed_without_ai", side_effect=AssertionError("the proposal")), \
                mock.patch("apps.pipeline.targets.packaging.settle_front_copy",
                           side_effect=lambda task, front, dims: measured.append(dims) or front):
            PackagingTarget().carton_map_front(self.task, PackagingOutput.objects.get(task=self.task))
        assert (measured[0]["width_mm"], measured[0]["height_mm"]) == (57.0, 123.0)

    def _sized_product(self):
        from apps.core.models import Product
        product = Product.objects.create(brand=self.brand, product_id="HC-120", name="Rose Blossom", category="SK",
                                         year=2026, product_type="hand cream", width_mm=42, depth_mm=27, height_mm=120)
        self.task.product = product
        self.task.save()

    def test_his_findings_123_a_size_impossible_for_the_product_is_flagged_and_refused_in_words(self):
        """[His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (6):
        "Flag impossible sizes at the size step (I typed 1123 mm for a 120 mm product; it accepted it)."] 1123 mm for a
        120 mm product is no carton the die makes; 100 mm would not hold it; 300 mm is more than twice what it needs —
        said, never refused; 123 mm is none of these. As he types (size_flags) and at confirmation, in words."""
        from unittest import mock

        from apps.pipeline.agents.dieline_agent import size_flags
        self._sized_product()
        flags = {h: size_flags(self.task, {"width_mm": 42, "depth_mm": 27, "height_mm": h}) for h in (1123, 100, 300, 123)}
        assert [(f["side"], f["level"]) for f in flags[1123]] == [("height_mm", "impossible")]
        assert flags[1123][0]["words"] == ("1123 mm tall is not a carton this die makes: it makes cartons 60 to 600 mm "
                                           "tall — the product is 120 mm tall")
        assert [f["level"] for f in flags[100]] == ["impossible"] and "would not go in" in flags[100][0]["words"]
        assert [f["level"] for f in flags[300]] == ["far"] and "more than twice" in flags[300][0]["words"]
        assert flags[123] == []
        resp = self.client.post(f"/api/tasks/{self.task.id}/size_flags/",
                                {"dimensions": {"width_mm": 42, "depth_mm": 27, "height_mm": 1123}},
                                content_type="application/json")
        assert resp.status_code == 200 and resp.json()["flags"] == flags[1123]
        with mock.patch("apps.pipeline.tasks.resume_aria_dimensions.delay") as resume:
            refused = self.client.post(f"/api/tasks/{self.task.id}/confirm_dimensions/",
                                       {"dimensions": {"width_mm": 42, "depth_mm": 27, "height_mm": 1123}},
                                       content_type="application/json")
            too_small = self.client.post(f"/api/tasks/{self.task.id}/confirm_dimensions/",
                                         {"dimensions": {"width_mm": 42, "depth_mm": 27, "height_mm": 100}},
                                         content_type="application/json")
        # outside the die's range: refused as before, now in his words too; a die it makes, too small: refused in words
        assert refused.status_code == 400 and refused.json()["error"] == "Invalid dimensions", refused.content
        assert refused.json()["words"] == flags[1123][0]["words"]
        assert too_small.status_code == 400 and too_small.json()["error"] == "SIZE_IMPOSSIBLE", too_small.content
        assert too_small.json()["words"] == flags[100][0]["words"]
        assert not resume.called
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_dimensions"                # nothing moved
