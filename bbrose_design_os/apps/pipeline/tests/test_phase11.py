from apps.pipeline.tests.quality_fixtures import critique, reviewed
"""Phase 11 tests — roles/permissions, gate audit trail, multi-brand,
revision workflow (audit H2, H3, H9, H10).
"""
import json
import tempfile
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings

from apps.core.models import STATUS_CANONICAL, Brand, ColorSystem, Product
from apps.pipeline.models import (
    AgentLog,
    DesignTask,
    GateDecision,
    GeneratedImage,
)
from apps.pipeline.permissions import ROLE_ADMIN, ROLE_DESIGNER, ROLE_REVIEWER


def make_user(username, *roles, superuser=False):
    """Create a user, optionally in one or more role groups."""
    if superuser:
        return User.objects.create_superuser(username, f"{username}@t.com", "pw")
    user = User.objects.create_user(username, f"{username}@t.com", "pw")
    for role in roles:
        group, _ = Group.objects.get_or_create(name=role)
        user.groups.add(group)
    return user


# §BH57(a)3: NO brand logo for these — they never meant to have one. The default BRAND_LOGO_PATH resolves
# to the REAL media/brand/logo.png, which these tests were silently reading; a lone logo now reaches the
# provider, so that accident would change their branch. This is what they always assumed.
@override_settings(BRAND_LOGO_PATH="/nonexistent/bh57/no-logo.png")
class Phase11TestBase(TestCase):
    def setUp(self):
        self.designer = make_user("designer", ROLE_DESIGNER)
        self.reviewer = make_user("reviewer", ROLE_REVIEWER)
        self.brand = Brand.objects.create(name="B", master_brief="x")

    def _task(self, status, **kw):
        kw.setdefault("brand", self.brand)
        return DesignTask.objects.create(task_text="t", status=status, **kw)

    def _image(self, task, prompt="p", **kw):
        return reviewed(GeneratedImage.objects.create(
            task=task, direction_name="d", prompt_used=prompt, image_url="u", **kw
        ))


# --------------------------------------------------------------------------
# 11.1 — roles + permissions
# --------------------------------------------------------------------------

class RolePermissionTests(Phase11TestBase):
    def test_designer_cannot_approve_gate1(self):
        task = self._task("awaiting_gate_1")
        img = self._image(task)
        self.client.force_login(self.designer)
        res = self.client.post(
            f"/api/tasks/{task.id}/gate1_approve/", {"image_id": img.id}
        )
        self.assertEqual(res.status_code, 403)
        task.refresh_from_db()
        self.assertEqual(task.status, "awaiting_gate_1")
        self.assertEqual(GateDecision.objects.count(), 0)

    def test_designer_cannot_reject_gate1(self):
        task = self._task("awaiting_gate_1")
        self.client.force_login(self.designer)
        res = self.client.post(
            f"/api/tasks/{task.id}/gate1_reject/", {"notes": "no"}
        )
        self.assertEqual(res.status_code, 403)

    @patch("apps.pipeline.tasks.resume_aria_gate1.delay")
    def test_reviewer_can_approve_gate1(self, mock_delay):
        task = self._task("awaiting_gate_1")
        img = self._image(task)
        self.client.force_login(self.reviewer)
        res = self.client.post(
            f"/api/tasks/{task.id}/gate1_approve/", {"image_id": img.id}
        )
        self.assertEqual(res.status_code, 200)
        mock_delay.assert_called_once()

    @patch("apps.pipeline.tasks.resume_aria_gate2.delay")
    def test_admin_role_can_approve_gate2(self, mock_delay):
        admin = make_user("adminrole", ROLE_ADMIN)
        task = self._task("awaiting_gate_2")
        from apps.pipeline.models import PackagingOutput
        output = PackagingOutput.objects.create(
            task=task, spec_sheet={}, approved_image=self._image(task)
        )
        self.client.force_login(admin)
        res = self.client.post(
            f"/api/tasks/{task.id}/gate2_approve/",
            {"packaging_output_id": output.id},
        )
        self.assertEqual(res.status_code, 200)

    def test_user_without_role_cannot_create_task(self):
        nobody = make_user("nobody")
        self.client.force_login(nobody)
        res = self.client.post("/api/tasks/create/", {"design_target": "packaging", "task_text": "hi"})
        self.assertEqual(res.status_code, 403)

    def test_reviewer_cannot_create_task(self):
        self.client.force_login(self.reviewer)
        res = self.client.post("/api/tasks/create/", {"design_target": "packaging", "task_text": "hi"})
        self.assertEqual(res.status_code, 403)

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_designer_creates_task_with_created_by(self, mock_delay):
        self.client.force_login(self.designer)
        # B4b-1 §8: the pipeline is dispatched on_commit now, so the callback
        # must run for the enqueue assertion below to be meaningful.
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post("/api/tasks/create/", {"design_target": "packaging", "task_text": "hi"})
        self.assertEqual(res.status_code, 201)
        task = DesignTask.objects.get(id=res.json()["task_id"])
        self.assertEqual(task.created_by, self.designer)
        mock_delay.assert_called_once()

    def test_anonymous_gets_401_or_403(self):
        task = self._task("awaiting_gate_1")
        res = self.client.post(f"/api/tasks/{task.id}/gate1_approve/", {"image_id": 1})
        self.assertIn(res.status_code, (302, 401, 403))


# --------------------------------------------------------------------------
# 11.1 — GateDecision audit trail  /  11.3 — notes cleared on approval
# --------------------------------------------------------------------------

class GateDecisionAuditTests(Phase11TestBase):
    @patch("apps.pipeline.tasks.resume_aria_gate1.delay")
    def test_gate1_approve_writes_decision_with_actor(self, mock_delay):
        task = self._task("awaiting_gate_1")
        img = self._image(task)
        self.client.force_login(self.reviewer)
        res = self.client.post(
            f"/api/tasks/{task.id}/gate1_approve/", {"image_id": img.id}
        )
        self.assertEqual(res.status_code, 200)
        decision = GateDecision.objects.get(task=task)
        self.assertEqual(decision.gate, "gate_1")
        self.assertEqual(decision.decision, "approve")
        self.assertEqual(decision.decided_by, self.reviewer)

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_gate1_reject_writes_decision_and_actor_log(self, mock_delay):
        task = self._task("awaiting_gate_1")
        self.client.force_login(self.reviewer)
        res = self.client.post(
            f"/api/tasks/{task.id}/gate1_reject/", {"notes": "too cold"}
        )
        self.assertEqual(res.status_code, 200)
        decision = GateDecision.objects.get(task=task)
        self.assertEqual(decision.decision, "reject")
        self.assertEqual(decision.notes, "too cold")
        self.assertEqual(decision.decided_by, self.reviewer)
        log = AgentLog.objects.filter(task=task, actor=self.reviewer)
        self.assertTrue(log.exists())

    @patch("apps.pipeline.tasks.resume_aria_gate1.delay")
    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_notes_cleared_on_approval_but_preserved_in_decision(
        self, mock_run, mock_resume
    ):
        task = self._task("awaiting_gate_1")
        img = self._image(task)
        self.client.force_login(self.reviewer)

        # 1) reject with notes → notes stored on the task AND in GateDecision
        res = self.client.post(
            f"/api/tasks/{task.id}/gate1_reject/", {"notes": "push warmth"}
        )
        self.assertEqual(res.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.gate_1_notes, "push warmth")

        # 2) pipeline re-runs and reaches Gate 1 again (simulated)
        DesignTask.objects.filter(id=task.id).update(status="awaiting_gate_1")

        # 3) approve → task notes cleared (H10), history preserved
        res = self.client.post(
            f"/api/tasks/{task.id}/gate1_approve/", {"image_id": img.id}
        )
        self.assertEqual(res.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.gate_1_notes, "")
        reject_row = GateDecision.objects.get(task=task, decision="reject")
        self.assertEqual(reject_row.notes, "push warmth")
        self.assertEqual(GateDecision.objects.filter(task=task).count(), 2)

    @patch("apps.pipeline.tasks.resume_aria_gate2.delay")
    def test_gate2_approve_clears_notes(self, mock_delay):
        task = self._task("awaiting_gate_2", gate_2_notes="old feedback")
        from apps.pipeline.models import PackagingOutput
        output = PackagingOutput.objects.create(
            task=task, spec_sheet={}, approved_image=self._image(task)
        )
        self.client.force_login(self.reviewer)
        res = self.client.post(
            f"/api/tasks/{task.id}/gate2_approve/",
            {"packaging_output_id": output.id},
        )
        self.assertEqual(res.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.gate_2_notes, "")
        self.assertTrue(
            GateDecision.objects.filter(task=task, gate="gate_2",
                                        decision="approve").exists()
        )

    def test_retry_records_actor(self):
        superuser = make_user("root", superuser=True)
        task = self._task("failed", error_message="boom")
        self.client.force_login(superuser)
        with patch("apps.pipeline.tasks.run_aria_pipeline.delay"):
            res = self.client.post(f"/api/tasks/{task.id}/retry/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            AgentLog.objects.filter(task=task, actor=superuser).exists()
        )

    def test_status_payload_exposes_owner_and_decisions(self):
        task = self._task("awaiting_gate_1", created_by=self.designer)
        GateDecision.objects.create(
            task=task, gate="gate_1", decision="reject",
            notes="n", decided_by=self.reviewer,
        )
        self.client.force_login(self.reviewer)
        res = self.client.get(f"/api/tasks/{task.id}/status/")
        data = res.json()
        self.assertEqual(data["created_by"], "designer")
        self.assertEqual(len(data["gate_decisions"]), 1)
        self.assertEqual(data["gate_decisions"][0]["decided_by"], "reviewer")


# --------------------------------------------------------------------------
# 11.2 — multi-brand
# --------------------------------------------------------------------------

class MultiBrandTests(Phase11TestBase):
    def setUp(self):
        super().setUp()
        self.brand2 = Brand.objects.create(name="B2", master_brief="y")
        self.product2 = Product.objects.create(
            brand=self.brand2, product_id="B2-CO-001", name="Other brand product",
            category="CO", year=2026,
        )
        self.client.force_login(self.designer)

    def test_multiple_brands_require_brand_id(self):
        res = self.client.post("/api/tasks/create/", {"design_target": "packaging", "task_text": "hi"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("brand_id", res.json()["error"])

    def test_unknown_brand_id_is_400(self):
        res = self.client.post(
            "/api/tasks/create/", {"design_target": "packaging", "task_text": "hi", "brand_id": 999999}
        )
        self.assertEqual(res.status_code, 400)

    def test_cross_brand_product_is_400(self):
        res = self.client.post("/api/tasks/create/", {"design_target": "packaging",
            "task_text": "hi",
            "brand_id": self.brand.id,
            "product_id": self.product2.id,  # belongs to brand2
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("product_id", res.json()["error"])

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_explicit_brand_and_matching_product_succeed(self, mock_delay):
        res = self.client.post("/api/tasks/create/", {"design_target": "packaging",
            "task_text": "hi",
            "brand_id": self.brand2.id,
            "product_id": self.product2.id,
        })
        self.assertEqual(res.status_code, 201)
        task = DesignTask.objects.get(id=res.json()["task_id"])
        self.assertEqual(task.brand, self.brand2)
        self.assertEqual(task.product, self.product2)

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_sole_brand_is_default(self, mock_delay):
        self.brand2.delete()
        res = self.client.post("/api/tasks/create/", {"design_target": "packaging", "task_text": "hi"})
        self.assertEqual(res.status_code, 201)
        task = DesignTask.objects.get(id=res.json()["task_id"])
        self.assertEqual(task.brand, self.brand)


class DashboardBrandTests(Phase11TestBase):
    def setUp(self):
        super().setUp()
        self.brand2 = Brand.objects.create(name="B2", master_brief="y")
        ColorSystem.objects.create(
            brand=self.brand, name="Blush Core", system_id="CS-001",
            palette=[{"role": "Primary", "hex": "#F2C4CE"}],
            image_generation_context="blush", status=STATUS_CANONICAL,
        )
        self._task("completed")
        self._task("queued", brand=self.brand2)
        self.client.force_login(self.designer)

    def test_palette_panel_non_empty_for_canonical_seed(self):
        """Audit H9: the panel used to filter status='active' → empty."""
        # [the owner's answer to the UI directions of 2026-09-25: the palette panel left with the old page; the brand's
        # colour systems are the Library's, read by the same canonical filter (apps/dashboard/brand_library.py)]
        from apps.dashboard import brand_library
        self.assertEqual([c["name"] for c in brand_library.colour_systems(self.brand)], ["Blush Core"])
        res = self.client.get(f"/dashboard/brand/?brand={self.brand.id}")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Blush Core")

    def test_brand_switcher_scopes_tasks_and_stats(self):
        # [the owner's answer to the UI directions of 2026-09-25: the start page starts a design under the chosen brand
        # and offers that brand's products; the board is every design (his data has one brand with designs)]
        from apps.core.models import Product
        mine = Product.objects.create(brand=self.brand, product_id="P11-A", name="Brand one's", category="CO", year=2026)
        theirs = Product.objects.create(brand=self.brand2, product_id="P11-B", name="Brand two's", category="CO",
                                        year=2026)
        res = self.client.get(f"/dashboard/new/classic/?brand={self.brand2.id}")
        self.assertEqual(res.context["brand"].id, self.brand2.id)
        self.assertEqual([p.pk for p in res.context["products"]], [theirs.pk])
        self.assertNotIn(mine, res.context["products"])
        # selection is remembered in the session
        res2 = self.client.get("/dashboard/new/classic/")
        self.assertEqual(res2.context["brand"].id, self.brand2.id)

    def test_default_brand_is_deterministic_first_by_id(self):
        res = self.client.get("/dashboard/new/classic/")
        self.assertEqual(res.context["brand"].id, self.brand.id)


# --------------------------------------------------------------------------
# 11.3 — revision workflow: prompt edit, image-only rerun, superseded
# --------------------------------------------------------------------------

def _claude_response(json_data):
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(json_data)
    resp = MagicMock()
    resp.content = [block]
    return resp


@override_settings(ANTHROPIC_API_KEY="test-key", OPENAI_API_KEY="test-key")
class RevisionWorkflowTests(Phase11TestBase):
    def setUp(self):
        super().setUp()
        self.task = self._task("awaiting_gate_1")
        self.img1 = self._image(self.task, prompt="prompt one")
        self.img2 = self._image(self.task, prompt="prompt two")
        self.client.force_login(self.reviewer)

    # --- prompt editing -----------------------------------------------------

    def test_update_prompt(self):
        res = self.client.post(
            f"/api/images/{self.img1.id}/update_prompt/",
            {"prompt": "warmer blush, rose gold hero"},
        )
        self.assertEqual(res.status_code, 200)
        self.img1.refresh_from_db()
        self.assertEqual(self.img1.prompt_used, "warmer blush, rose gold hero")
        self.assertTrue(
            AgentLog.objects.filter(task=self.task, actor=self.reviewer).exists()
        )

    def test_update_prompt_designer_forbidden(self):
        self.client.force_login(self.designer)
        res = self.client.post(
            f"/api/images/{self.img1.id}/update_prompt/", {"prompt": "x"}
        )
        self.assertEqual(res.status_code, 403)

    def test_update_prompt_blocked_outside_gate1(self):
        DesignTask.objects.filter(id=self.task.id).update(status="running")
        res = self.client.post(
            f"/api/images/{self.img1.id}/update_prompt/", {"prompt": "x"}
        )
        self.assertEqual(res.status_code, 409)

    def test_update_prompt_blocked_for_superseded_image(self):
        self.img1.superseded = True
        self.img1.save()
        res = self.client.post(
            f"/api/images/{self.img1.id}/update_prompt/", {"prompt": "x"}
        )
        self.assertEqual(res.status_code, 409)

    # --- image-only rerun ---------------------------------------------------

    def _run_image_rerun(self, mock_gen, mock_get, mock_qa):
        reviewed(self.img1, 4)
        reviewed(self.img2, 4)
        mock_data = MagicMock()
        mock_data.url = "https://example.com/new.png"
        openai_resp = MagicMock()
        openai_resp.data = [mock_data]
        mock_gen.return_value = openai_resp
        mock_get.return_value = MagicMock(status_code=200, content=b"fake_png")
        mock_qa.return_value = _claude_response(critique(8))
        with tempfile.TemporaryDirectory() as tmp, override_settings(MEDIA_ROOT=tmp):
            return self.client.post(f"/api/tasks/{self.task.id}/rerun_images/")

    @patch("apps.pipeline.agents.qa_reviewer.call_claude")
    @patch("apps.pipeline.agents.image_producer.requests.get")
    @patch("apps.pipeline.agents.image_producer.openai.images.generate")
    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    @patch("apps.pipeline.agents.creative_director.call_claude")
    def test_rerun_images_skips_creative_and_prompt_stages(
        self, mock_cd, mock_pe, mock_gen, mock_get, mock_qa
    ):
        res = self._run_image_rerun(mock_gen, mock_get, mock_qa)
        self.assertEqual(res.status_code, 200)

        # The whole point: NO Claude text stages ran (Milestone 11.3).
        mock_cd.assert_not_called()
        mock_pe.assert_not_called()
        # Images were regenerated from the stored prompts.
        self.assertEqual(mock_gen.call_count, 2)
        prompts_sent = {c.kwargs["prompt"] for c in mock_gen.call_args_list}
        self.assertEqual(prompts_sent, {"prompt one", "prompt two"})

        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "awaiting_gate_1")
        self.assertEqual(self.task.image_rerun_count, 1)

    @patch("apps.pipeline.agents.qa_reviewer.call_claude")
    @patch("apps.pipeline.agents.image_producer.requests.get")
    @patch("apps.pipeline.agents.image_producer.openai.images.generate")
    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    @patch("apps.pipeline.agents.creative_director.call_claude")
    def test_rerun_supersedes_old_images_and_default_payload_hides_them(
        self, mock_cd, mock_pe, mock_gen, mock_get, mock_qa
    ):
        res = self._run_image_rerun(mock_gen, mock_get, mock_qa)
        self.assertEqual(res.status_code, 200)

        self.img1.refresh_from_db()
        self.img2.refresh_from_db()
        self.assertTrue(self.img1.superseded)
        self.assertTrue(self.img2.superseded)
        # History kept: 2 old + 2 new rows, 2 current.
        self.assertEqual(GeneratedImage.objects.filter(task=self.task).count(), 4)
        current = GeneratedImage.objects.filter(task=self.task, superseded=False)
        self.assertEqual(current.count(), 2)

        # API: current set by default, full history behind the flag.
        data = self.client.get(f"/api/tasks/{self.task.id}/status/").json()
        self.assertEqual(len(data["images"]), 2)
        self.assertTrue(all(not i["superseded"] for i in data["images"]))
        data_all = self.client.get(
            f"/api/tasks/{self.task.id}/status/?include_superseded=1"
        ).json()
        self.assertEqual(len(data_all["images"]), 4)

    def test_rerun_images_respects_cap(self):
        from django.conf import settings
        DesignTask.objects.filter(id=self.task.id).update(
            image_rerun_count=settings.MAX_REVISION_PASSES
        )
        res = self.client.post(f"/api/tasks/{self.task.id}/rerun_images/")
        self.assertEqual(res.status_code, 409)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "awaiting_gate_1")

    def test_rerun_images_designer_forbidden(self):
        self.client.force_login(self.designer)
        res = self.client.post(f"/api/tasks/{self.task.id}/rerun_images/")
        self.assertEqual(res.status_code, 403)

    def test_rerun_images_conflict_when_not_at_gate1(self):
        DesignTask.objects.filter(id=self.task.id).update(status="running")
        res = self.client.post(f"/api/tasks/{self.task.id}/rerun_images/")
        self.assertEqual(res.status_code, 409)



class HisSku122Tests(TestCase):
    """[His answers after 122 was redrawn, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 0b0c7e7), (1): "Add an
    optional SKU field on New design and at Gate 2 so I can fill it in any time. The same for 117."] The SKU travels with
    New design; at Gate 2 he gives it at any time — kept on the design and its project, written onto the drawing's record
    at once — and a design whose product record carries its SKU keeps that one."""

    def setUp(self):
        from apps.core.models import Brand
        self.brand = Brand.objects.create(name="B-sku", master_brief="x")
        self.designer = make_user("skudesigner", ROLE_DESIGNER)
        self.reviewer = make_user("skureviewer", ROLE_REVIEWER)

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_new_design_keeps_the_sku_he_types_and_none_when_he_types_none(self, _delay):
        self.client.force_login(self.designer)
        with self.captureOnCommitCallbacks(execute=True):
            given = self.client.post("/api/tasks/create/", {"design_target": "packaging", "task_text": "a rose hand cream", "sku": "  BBR-HC  122 "})
            bare = self.client.post("/api/tasks/create/", {"design_target": "packaging", "task_text": "a rose hand cream"})
        self.assertEqual((given.status_code, bare.status_code), (201, 201))
        self.assertEqual(DesignTask.objects.get(id=given.json()["task_id"]).sku, "BBR-HC 122")
        self.assertEqual(DesignTask.objects.get(id=bare.json()["task_id"]).sku_on_record(), "")

    def test_at_gate_2_he_gives_it_any_time_and_every_piece_of_the_project_reads_it(self):
        from apps.pipeline.models import DesignProject, PackagingOutput
        project = DesignProject.objects.create(brand=self.brand, brief="x", design_target="complete_product",
                                               metadata={})
        tube = DesignTask.objects.create(brand=self.brand, task_text="x", status="awaiting_gate_2",
                                         design_target="product_container", project=project, stage="container")
        from apps.pipeline.models import GeneratedImage
        image = GeneratedImage.objects.create(task=tube, direction_name="d", prompt_used="p", variation_number=1,
                                              is_approved=True)
        out = PackagingOutput.objects.create(task=tube, approved_image=image,
                                             spec_sheet={"backend": "container", "sku": ""})
        self.client.force_login(self.designer)
        self.assertEqual(self.client.post("/api/tasks/%d/sku/" % tube.pk, {"sku": "X"}).status_code, 403)
        self.client.force_login(self.reviewer)
        r = self.client.post("/api/tasks/%d/sku/" % tube.pk, {"sku": "BBR-HC-122"}, content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("printed the next time the design is drawn", r.json()["words"])
        tube.refresh_from_db()
        out.refresh_from_db()
        project.refresh_from_db()
        self.assertEqual((tube.sku, out.spec_sheet["sku"], project.metadata["sku"]), ("BBR-HC-122",) * 3)
        carton = DesignTask.objects.create(brand=self.brand, task_text="x", status="queued",
                                           design_target="packaging", project=project, stage="packaging")
        self.assertEqual(carton.sku_on_record(), "BBR-HC-122")        # a piece started after reads it too
        status_ = self.client.get("/api/tasks/%d/status/" % tube.pk).json()
        self.assertEqual((status_["sku"], status_["sku_from_product"]), ("BBR-HC-122", False))
        self.client.post("/api/tasks/%d/sku/" % tube.pk, {"sku": ""}, content_type="application/json")
        tube.refresh_from_db()
        self.assertEqual(tube.sku_on_record(), "")

    def test_a_product_records_sku_stands(self):
        from apps.core.models import Product
        product = Product.objects.create(brand=self.brand, product_id="CO-122", name="Rose", category="CO", year=2026)
        task = DesignTask.objects.create(brand=self.brand, product=product, task_text="x", status="awaiting_gate_2",
                                         design_target="product_container")
        self.client.force_login(self.reviewer)
        r = self.client.post("/api/tasks/%d/sku/" % task.pk, {"sku": "OTHER"}, content_type="application/json")
        self.assertEqual(r.status_code, 409)
        self.assertIn("CO-122", r.json()["words"])
        self.assertEqual(task.sku_on_record(), "CO-122")
