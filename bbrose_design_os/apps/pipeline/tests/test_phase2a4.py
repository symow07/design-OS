"""Phase 2A-4 — direction review, selection, and Gate-1 resume.

The properties that matter: the pause is durable and restart-safe, selection binds to the
stable direction id and is idempotent, resume renders exactly three variations of the ONE
chosen direction with zero Creative Director calls, unselected directions never reach the
render path, legacy tasks are untouched, and nothing here creates authority.
"""
from __future__ import annotations
from apps.pipeline.tests.quality_fixtures import critique, reviewed

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase, override_settings

from apps.core.models import Brand, Product
from apps.pipeline.agents.aria import ARIAAgent
from apps.pipeline.models import (
    AgentLog, CreativeBrief, DesignTask, GeneratedImage, TrendBoard)
from apps.pipeline.views import select_design_direction

from .direction_fixtures import valid_document


def _drawing_recorded(calls):
    """[His final goal, 2026-10-05, B4, re-pinned: "NO PROMPT STEP"] the drawing step that follows the plan, recorded:
    each call counted, the design left at Gate 1 as a drawn design rests (its own tests draw it for real)."""
    def drawn(agent, feedback=None):
        calls.append(feedback)
        agent.task.status = "awaiting_gate_1"
        agent.task.save()
    return drawn


def _legacy_pause(agent, feedback=None):
    """[His final goal, 2026-10-05, B4, re-pinned] a design planned before B4 rests at the direction pause — the
    selection door still serves it; the selection tests plan one and leave it there."""
    agent.task.status = "awaiting_direction_selection"
    agent.task.save()

MOCK_VARIATION_PROMPTS = [
    {"direction_name": "Porcelain Verse",
     "full_prompt": f"variation {n}: porcelain carton, serif name, rose gold",
     "aspect_ratio": "9:21", "notes": f"v{n}"}
    for n in (1, 2, 3)
]


def _claude(payload):
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)
    response = MagicMock()
    response.content = [block]
    return response


def _openai_image():
    data = MagicMock()
    data.url = "https://example.com/img.png"
    response = MagicMock()
    response.data = [data]
    return response


# §BH57(a)3: NO brand logo for these — they never meant to have one. The default BRAND_LOGO_PATH resolves
# to the REAL media/brand/logo.png, which these tests were silently reading; a lone logo now reaches the
# provider, so that accident would change their branch. This is what they always assumed.
@override_settings(ANTHROPIC_API_KEY="test-key", OPENAI_API_KEY="test-key",
                   BRAND_LOGO_PATH="/nonexistent/bh57/no-logo.png")
class DirectionSelectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("t2a4", "t@t.com", "password")
        self.brand = Brand.objects.create(name="BBROSE", master_brief="brief")
        self.product = Product.objects.create(
            brand=self.brand, product_id="P-1", name="Dew Serum", category="SK", year=2026)
        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product,
            task_text="Serum carton concept", status="queued",
            created_by=self.user)

    # --- planning pause -----------------------------------------------------------

    @patch("apps.pipeline.agents.image_producer.openai.images.generate")
    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    @patch("apps.pipeline.agents.creative_director.call_claude")
    def test_run_plans_persists_and_pauses_without_rendering(
            self, mock_cd, mock_pe, mock_gen):
        """[His final goal, 2026-10-05, B4, re-pinned: "NO PROMPT STEP"] the pause is gone: planning persists the
        validated plan and hands it to the drawing step once; planning itself still prompts and draws nothing."""
        mock_cd.return_value = _claude(valid_document())
        drawn = []
        with patch.object(ARIAAgent, "_render_each_direction", _drawing_recorded(drawn)):
            ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()

        self.assertEqual(drawn, [None])
        self.assertEqual(self.task.status, "awaiting_gate_1")
        brief = CreativeBrief.objects.get(task=self.task)
        self.assertEqual(len(brief.directions), 3)
        self.assertEqual(brief.design_intent["schema_version"], "design_intent/1.2")
        self.assertNotIn("directions", brief.design_intent)
        self.assertEqual(brief.selected_direction_id, "")
        self.assertIsNone(brief.direction_selected_at)
        # nothing rendered, nothing prompted
        mock_pe.assert_not_called()
        mock_gen.assert_not_called()
        self.assertEqual(GeneratedImage.objects.filter(task=self.task).count(), 0)

    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    @patch("apps.pipeline.agents.creative_director.call_claude")
    def test_restart_while_paused_replans_nothing(self, mock_cd, mock_pe):
        """[His final goal, B4, re-pinned] a restart re-enters run(): the plan is never made again — its directions are
        drawn again, from the same plan."""
        mock_cd.return_value = _claude(valid_document())
        drawn = []
        with patch.object(ARIAAgent, "_render_each_direction", _drawing_recorded(drawn)):
            ARIAAgent(self.task.id).run()
            calls_after_planning = mock_cd.call_count
            ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()
        self.assertEqual(drawn, [None, None])
        self.assertEqual(self.task.status, "awaiting_gate_1")
        self.assertEqual(mock_cd.call_count, calls_after_planning)
        mock_pe.assert_not_called()

    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    @patch("apps.pipeline.agents.image_producer.openai.images.generate")
    @patch("apps.pipeline.agents.creative_director.call_claude")
    def test_failed_planning_persists_no_partial_set_and_renders_nothing(
            self, mock_cd, mock_gen, mock_pe):
        # [re-pinned by his test blocker on design 123, 2026-10-09, (2): a duplicate design axis is a "not distinct"
        # check, shown with a note] — [re-pinned by his goal of 2026-10-10, item 1: "NO planner check ever stops a
        # design"] what still stops is an answer that is never three directions: four, twice
        broken = valid_document()
        broken["directions"].append(dict(broken["directions"][0], direction_id="d4", name="Extra"))
        mock_cd.return_value = _claude(broken)      # repair returns the same → fail
        ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "failed")
        self.assertIn("DIRECTION_COUNT_INVALID", self.task.error_message)
        self.assertFalse(CreativeBrief.objects.filter(task=self.task).exists())
        mock_gen.assert_not_called()

    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    @patch("apps.pipeline.agents.creative_director.call_claude")
    def test_his_blocker_123_a_plan_too_alike_twice_goes_on_to_be_drawn_with_its_note(self, mock_cd, mock_pe):
        """[His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (2): "Every
        "not distinct" check: it never stops a design. On failure it retries once with the reason; if it still fails, it
        shows me the three anyway with a note, and I choose."]
        Design 123 stopped at its directions — "emotional tone not distinct", twice, $0.38. A plan too alike twice is
        kept and drawn, its planning record carrying the codes, and the page says so beside the three in words."""
        from apps.dashboard.words import alike_words
        from apps.pipeline.direction_signature import SHOWN_ALIKE_KEY
        alike = valid_document()
        alike["directions"][1]["design_axis"] = alike["directions"][0]["design_axis"]
        mock_cd.return_value = _claude(alike)
        drawn = []
        with patch.object(ARIAAgent, "_render_each_direction", _drawing_recorded(drawn)):
            ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "awaiting_gate_1")
        self.assertEqual(drawn, [None])
        self.assertEqual(mock_cd.call_count, 2)                  # retried once with the reason
        self.assertTrue(CreativeBrief.objects.filter(task=self.task).exists())
        note = AgentLog.objects.get(task=self.task, action="ARIA: structured directions validated").payload[
            SHOWN_ALIKE_KEY]
        self.assertTrue(note["codes"][0].startswith("DUPLICATE_DESIGN_AXIS"))
        self.assertEqual((note["alike_attempts"], note["attempts"]), ([1, 2], 2))
        self.assertEqual(alike_words(self.task), [
            "Shown anyway: the three directions came back too alike twice — two of them had the same idea, word for "
            "word; made once more with that reason, they did not change. You choose."])
        clean = valid_document()
        mock_cd.return_value = _claude(clean)
        CreativeBrief.objects.filter(task=self.task).delete()
        DesignTask.objects.filter(pk=self.task.pk).update(status="queued")
        with patch.object(ARIAAgent, "_render_each_direction", _drawing_recorded(drawn)):
            ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()
        self.assertEqual(alike_words(self.task), [])             # a later plan that passed says nothing

    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    @patch("apps.pipeline.agents.creative_director.call_claude")
    def test_goal_1010_item1_a_plan_refused_twice_goes_on_with_a_plain_note(self, mock_cd, mock_pe):
        """[His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 1: "NO planner check ever stops a design (not only
        "not distinct"): on failure it retries once with the reason; if it still fails, it shows me the three directions
        with a plain note, and I choose."] A plan refused twice by a check that is not "not distinct" goes on to be
        drawn; the page says why in words, never a code."""
        from apps.dashboard.words import alike_words
        broken = valid_document()
        broken["directions"][1]["imagery_approach"] = "a full-bleed photograph of real peonies printed across the front"
        mock_cd.return_value = _claude(broken)
        drawn = []
        with patch.object(ARIAAgent, "_render_each_direction", _drawing_recorded(drawn)):
            ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()
        self.assertEqual((self.task.status, drawn, mock_cd.call_count), ("awaiting_gate_1", [None], 2))
        self.assertFalse(self.task.error_message)
        self.assertEqual(alike_words(self.task), [
            "Shown anyway: the three directions failed their checks twice — a direction needed a photographic "
            "picture, which can't go into print-ready artwork; made once more with that reason, they still did. "
            "You choose."])

    # --- selection service ----------------------------------------------------------

    def _plan(self):
        # [his final goal, B4, re-pinned] a design planned before B4, at the pause the selection door serves
        with patch("apps.pipeline.agents.creative_director.call_claude",
                   return_value=_claude(valid_document())), \
                patch.object(ARIAAgent, "_render_each_direction", _legacy_pause):
            ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()
        return CreativeBrief.objects.get(task=self.task)

    def test_selection_binds_the_stable_id_and_enqueues_once(self):
        brief = self._plan()
        payload, http_status = select_design_direction(self.task, self.user, "d2")
        self.assertEqual(http_status, 200, payload)
        brief.refresh_from_db()
        self.task.refresh_from_db()
        self.assertEqual(brief.selected_direction_id, "d2")
        self.assertIsNotNone(brief.direction_selected_at)
        self.assertEqual(self.task.status, "queued")

    def test_selection_rejects_indexes_unknown_ids_and_forged_objects(self):
        self._plan()
        for bad in ("0", "1", "nope", "", None, {"direction_id": "d1"}):
            payload, http_status = select_design_direction(self.task, self.user, bad)
            self.assertEqual(http_status, 400, (bad, payload))
        brief = CreativeBrief.objects.get(task=self.task)
        self.assertEqual(brief.selected_direction_id, "")

    def test_selection_is_idempotent_and_conflicts_fail_closed(self):
        brief = self._plan()
        first, _ = select_design_direction(self.task, self.user, "d1")
        brief.refresh_from_db()
        stamp = brief.direction_selected_at
        # same choice again: reported, nothing changes, nothing re-enqueued
        self.task.refresh_from_db()
        again, http_status = select_design_direction(self.task, self.user, "d1")
        self.assertEqual(http_status, 200)
        self.assertIn("already", again["message"].lower())
        brief.refresh_from_db()
        self.assertEqual(brief.direction_selected_at, stamp)
        # a different choice after binding: refused with a stable reason
        conflict, http_status = select_design_direction(self.task, self.user, "d3")
        self.assertEqual(http_status, 409)
        self.assertEqual(conflict["error"], "DIRECTION_ALREADY_SELECTED")
        brief.refresh_from_db()
        self.assertEqual(brief.selected_direction_id, "d1")

    def test_selection_requires_the_paused_state(self):
        _, http_status = select_design_direction(self.task, self.user, "d1")
        self.assertEqual(http_status, 409)      # no plan exists yet

    def test_endpoint_enforces_method_auth_and_csrf(self):
        self._plan()
        url = f"/api/tasks/{self.task.id}/select_direction/"
        # unauthenticated
        response = self.client.post(url, {"direction_id": "d1"},
                                    content_type="application/json")
        self.assertIn(response.status_code, (401, 403))
        # authenticated reviewer
        self.client.login(username="t2a4", password="password")
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url, json.dumps({"direction_id": "d1"}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)

    # --- resume ---------------------------------------------------------------------

    def _select_and_resume(self, direction_id="d1", pe_payload=None):
        self._plan()
        select_design_direction(self.task, self.user, direction_id)
        with patch("apps.pipeline.agents.creative_director.call_claude") as mock_cd, \
                patch("apps.pipeline.agents.prompt_engineer.call_claude",
                      return_value=_claude(
                          pe_payload or {"prompts": MOCK_VARIATION_PROMPTS})) as mock_pe, \
                patch("apps.pipeline.agents.qa_reviewer.call_claude",
                      return_value=_claude(critique(9))), \
                patch("apps.pipeline.agents.image_producer.openai.images.generate",
                      return_value=_openai_image()), \
                patch("apps.pipeline.agents.image_producer.requests.get",
                      return_value=MagicMock(status_code=200, content=b"png")):
            ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()
        return mock_cd, mock_pe

    def test_resume_renders_three_variations_of_only_the_selected_direction(self):
        mock_cd, mock_pe = self._select_and_resume("d2")
        self.assertEqual(self.task.status, "awaiting_gate_1")
        mock_cd.assert_not_called()                       # zero Creative Director calls
        self.assertEqual(mock_pe.call_count, 1)           # one variation call
        system, content = mock_pe.call_args.args[0], mock_pe.call_args.args[1]
        self.assertIn("VARIATIONS WITHIN", system)
        self.assertIn("Botanical Meridian", content)      # d2 present
        self.assertNotIn("Porcelain Verse", content)      # unselected d1 absent
        self.assertNotIn("Still Water Relief", content)   # unselected d3 absent
        images = GeneratedImage.objects.filter(task=self.task)
        self.assertEqual(images.count(), 3)

    def test_resume_is_reproducible_after_restart_without_new_planning(self):
        self._select_and_resume("d1")
        first_images = set(GeneratedImage.objects.filter(
            task=self.task).values_list("id", flat=True))
        # gate-1 reject re-runs the pipeline: same persisted direction, no CD
        self.task.status = "queued"
        self.task.gate_1_notes = "push warmth"
        self.task.save()
        mock_cd, mock_pe = None, None
        with patch("apps.pipeline.agents.creative_director.call_claude") as mock_cd, \
                patch("apps.pipeline.agents.prompt_engineer.call_claude",
                      return_value=_claude({"prompts": MOCK_VARIATION_PROMPTS})) as mock_pe, \
                patch("apps.pipeline.agents.qa_reviewer.call_claude",
                      return_value=_claude(critique(9))), \
                patch("apps.pipeline.agents.image_producer.openai.images.generate",
                      return_value=_openai_image()) as mock_gen, \
                patch("apps.pipeline.agents.image_producer.requests.get",
                      return_value=MagicMock(status_code=200, content=b"png")):
            ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "awaiting_gate_1")
        mock_cd.assert_not_called()
        mock_pe.assert_not_called()
        self.assertEqual(mock_gen.call_count, 3)
        self.assertTrue(all("push warmth" in c.kwargs["prompt"] for c in mock_gen.call_args_list))
        # prior images superseded, not deleted
        for image_id in first_images:
            self.assertTrue(GeneratedImage.objects.get(id=image_id).superseded)

    def test_wrong_variation_count_fails_closed_before_any_image(self):
        with patch("apps.pipeline.agents.image_producer.openai.images.generate") as gen:
            self._select_and_resume(
                "d1", pe_payload={"prompts": MOCK_VARIATION_PROMPTS[:2]})
            gen.assert_not_called()
        self.assertEqual(self.task.status, "failed")
        self.assertIn("exactly 3", self.task.error_message)
        self.assertEqual(GeneratedImage.objects.filter(task=self.task).count(), 0)

    def test_invalid_persisted_selection_fails_closed_with_no_fallback(self):
        self._plan()
        brief = CreativeBrief.objects.get(task=self.task)
        brief.selected_direction_id = "d9"                 # unknown id, forced in
        brief.save()
        with patch("apps.pipeline.agents.creative_director.call_claude") as mock_cd, \
                patch("apps.pipeline.agents.prompt_engineer.call_claude") as mock_pe:
            ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "failed")
        mock_cd.assert_not_called()
        mock_pe.assert_not_called()

    # --- legacy compatibility --------------------------------------------------------

    @patch("apps.pipeline.agents.image_producer.requests.get")
    @patch("apps.pipeline.agents.image_producer.openai.images.generate")
    @patch("apps.pipeline.agents.qa_reviewer.call_claude")
    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    @patch("apps.pipeline.agents.creative_director.call_claude")
    def test_a_pre_2a_brief_is_refused_by_name_and_spends_nothing(
            self, mock_cd, mock_pe, mock_qa, mock_gen, mock_get):
        """THE CLEAN-UP OF 2026-10-04 (E8): the pre-2A path — a directions-only brief run straight to Gate 1 —
        is removed. A run of such a design fails BY NAME before anything is asked: no planning, no prompt, no
        picture, no review, nothing spent; its brief stays as it was, and its page says why in words."""
        from apps.dashboard.words import stop_words
        from apps.pipeline.agents.aria import PRE_2A_BRIEF_RETIRED
        CreativeBrief.objects.create(
            task=self.task,
            directions=[{"name": "Velvet Petal", "prompt_seed": "s"}])
        ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "failed")
        self.assertTrue(self.task.error_message.startswith(PRE_2A_BRIEF_RETIRED), self.task.error_message)
        for mock in (mock_cd, mock_pe, mock_qa, mock_gen, mock_get):
            mock.assert_not_called()
        brief = CreativeBrief.objects.get(task=self.task)
        self.assertEqual((brief.design_intent, brief.directions),
                         ({}, [{"name": "Velvet Petal", "prompt_seed": "s"}]))
        words = stop_words(self.task)
        self.assertNotIn(PRE_2A_BRIEF_RETIRED, words)
        self.assertIn("before directions were planned", words)

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_a_retry_of_a_pre_2a_design_is_refused_by_name_and_nothing_moves(self, delay):
        """E8: Retry of such a design answers 409 with the code in its own field and plain words, before
        the daily-cap check, any transition, log row or dispatch — nothing is spent."""
        from apps.pipeline.agents.aria import PRE_2A_BRIEF_RETIRED
        CreativeBrief.objects.create(task=self.task, directions=[{"name": "Velvet Petal"}])
        DesignTask.objects.filter(pk=self.task.pk).update(status="failed", error_message="its old reason")
        logs = AgentLog.objects.filter(task=self.task).count()
        self.client.login(username="t2a4", password="password")
        res = self.client.post(f"/api/tasks/{self.task.id}/retry/")
        self.assertEqual(res.status_code, 409, res.content)
        self.assertEqual(res.json()["code"], PRE_2A_BRIEF_RETIRED)
        self.assertNotIn(PRE_2A_BRIEF_RETIRED, res.json()["error"])
        self.task.refresh_from_db()
        self.assertEqual((self.task.status, self.task.error_message), ("failed", "its old reason"))
        self.assertEqual(AgentLog.objects.filter(task=self.task).count(), logs)
        delay.assert_not_called()

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_a_gate1_reject_of_a_pre_2a_design_is_refused_before_anything_is_written(self, delay):
        """E8: a pre-2A design standing at Gate 1 (where its old path ended) cannot be sent back for a revision
        its removed path would make: refused by name before the decision row, the log row or the dispatch."""
        from apps.pipeline.agents.aria import PRE_2A_BRIEF_RETIRED
        from apps.pipeline.models import GateDecision
        CreativeBrief.objects.create(task=self.task, directions=[{"name": "Velvet Petal"}])
        DesignTask.objects.filter(pk=self.task.pk).update(status="awaiting_gate_1")
        logs = AgentLog.objects.filter(task=self.task).count()
        self.client.login(username="t2a4", password="password")
        res = self.client.post(f"/api/tasks/{self.task.id}/gate1_reject/",
                               json.dumps({"notes": "warmer, please"}), content_type="application/json")
        self.assertEqual(res.status_code, 409, res.content)
        self.assertEqual(res.json()["code"], PRE_2A_BRIEF_RETIRED)
        self.task.refresh_from_db()
        self.assertEqual((self.task.status, self.task.gate_1_notes), ("awaiting_gate_1", ""))
        self.assertFalse(GateDecision.objects.filter(task=self.task).exists())
        self.assertEqual(AgentLog.objects.filter(task=self.task).count(), logs)
        delay.assert_not_called()

    def test_legacy_serialization_survives_null_new_fields(self):
        from apps.pipeline.serializers import DesignTaskSerializer
        CreativeBrief.objects.create(
            task=self.task, directions=[{"name": "Velvet Petal"}])
        data = DesignTaskSerializer(self.task).data
        self.assertEqual(data["brief"]["design_intent"], {})
        self.assertEqual(data["brief"]["selected_direction_id"], "")
        self.assertIsNone(data["brief"]["direction_selected_at"])

    # --- separation -------------------------------------------------------------------

    def test_the_workflow_creates_no_authority(self):
        from apps.accounts.models import DecisionEvent
        from apps.intelligence.models import (
            GovernanceDecisionProjection, OperationalPermissionProjection,
        )
        self._plan()
        select_design_direction(self.task, self.user, "d1")
        self.assertEqual(DecisionEvent.objects.count(), 0)
        self.assertEqual(OperationalPermissionProjection.objects.count(), 0)
        self.assertEqual(GovernanceDecisionProjection.objects.count(), 0)


class Migration0016Tests(TransactionTestCase):
    """pipeline.0016 is additive: forward, rollback and re-application must preserve
    every legacy CreativeBrief row and never rewrite directions data."""

    def setUp(self):
        # it ends at 0016 (and its rollback drops the dashboard tables a later pipeline migration carries); the
        # cleanup returns every app to its latest, even when the test fails (the clean-up of 2026-10-04)
        from apps.core.migration_head import restore_head
        self.addCleanup(restore_head)

    def _migrate(self, target):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([("pipeline", target)])
        executor.loader.build_graph()

    def test_forward_rollback_reapply_preserve_legacy_data(self):
        user = User.objects.create_user("mig2a4")
        brand = Brand.objects.create(name="B", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="legacy", status="queued",
                                         created_by=user)
        legacy = [{"name": "Velvet Petal", "prompt_seed": "s"}]
        CreativeBrief.objects.create(task=task, directions=legacy)

        previous = "0015_designtask_assigned_to_and_more"
        import os
        names = sorted(f[:-3] for f in os.listdir("apps/pipeline/migrations")
                       if f[0].isdigit())
        previous = names[names.index("0016_direction_selection") - 1]

        self._migrate(previous)                       # rollback drops only the new columns
        self._migrate("0016_direction_selection")     # forward again

        brief = CreativeBrief.objects.get(task=task)
        self.assertEqual(brief.directions, legacy)    # legacy data untouched
        self.assertEqual(brief.design_intent, {})
        self.assertEqual(brief.selected_direction_id, "")
        self.assertIsNone(brief.direction_selected_at)
        # [his answers after 122 was redrawn, 2026-10-08: DesignTask.sku, migration 0041] a database at 0016 has none of
        # the columns added since — the row is read by the one column this checks (it read the whole row)
        self.assertEqual(DesignTask.objects.filter(id=task.id).values_list("status", flat=True).get(), "queued")


@override_settings(ANTHROPIC_API_KEY="test-key", OPENAI_API_KEY="test-key")
class TaskStatusEndpointTests(TestCase):
    """Phase 2A-5-CORR-2: the dashboard polls /api/tasks/<id>/status/, not the DRF
    task serializer — the smoke test found the direction panel rendering empty because
    this payload had no brief block."""

    def setUp(self):
        self.user = User.objects.create_superuser("t2a5", "t@t.com", "password")
        self.brand = Brand.objects.create(name="BBROSE", master_brief="brief")
        self.task = DesignTask.objects.create(
            brand=self.brand, task_text="Skynte carton", status="queued",
            created_by=self.user)

    def test_status_endpoint_carries_the_direction_plan_while_paused(self):
        # [his final goal, B4, re-pinned] a design planned before B4, at its pause
        with patch("apps.pipeline.agents.creative_director.call_claude",
                   return_value=_claude(valid_document())), \
                patch.object(ARIAAgent, "_render_each_direction", _legacy_pause):
            ARIAAgent(self.task.id).run()
        self.client.login(username="t2a5", password="password")
        data = self.client.get(f"/api/tasks/{self.task.id}/status/").json()
        self.assertEqual(data["status"], "awaiting_direction_selection")
        self.assertEqual(
            [d["direction_id"] for d in data["brief"]["directions"]],
            ["d1", "d2", "d3"])
        self.assertEqual(data["brief"]["design_intent"]["schema_version"],
                         "design_intent/1.2")
        self.assertEqual(data["brief"]["selected_direction_id"], "")

    def test_status_endpoint_tolerates_tasks_without_a_brief(self):
        self.client.login(username="t2a5", password="password")
        data = self.client.get(f"/api/tasks/{self.task.id}/status/").json()
        self.assertIsNone(data["brief"])


# ---------------------------------------------------------------------------
# §BH57(a)4 — THE WIRE ITSELF, WHICH LANDED WITHOUT A TEST AND DID NOT WORK.
#
# The other four wires each carry their own tests; this one did not, and the
# try/except around it meant a suite could stay green while the wire failed on
# every run. It did: task 85, the re-run of the owner's own Phase 1 brief,
# logged "house library unavailable" while `build_candidates` had sixteen
# candidates ready for that exact task. The cause was `self.product_profile`,
# which is not an attribute of ARIAAgent.
#
# So these assert the claim the commit message actually made — that the
# context REACHES the Creative Director — rather than that the call did not
# raise.
# ---------------------------------------------------------------------------


def _trend_board(task, *, status="READY", pictures=2, deadline=None, confirmed_used=None):
    """A trend board as ``trend_board.build`` leaves it: ``pictures`` read pictures, ticked, and one link card."""
    from apps.pipeline.models import InspirationReading, TrendBoard, TrendPick
    board = TrendBoard.objects.create(task=task, status=status, subject="cosmetic compact packaging",
                                      review_deadline=deadline)
    picks = []
    for n in range(1, pictures + 1):
        sha = ("%x" % (task.id * 16 + n)).rjust(64, "0")
        InspirationReading.objects.get_or_create(sha256=sha, defaults={"reading": {
            "layout": "layout %d" % n, "mood": "", "finish": "", "type_style": "", "colour_words": "",
            "take": "the take of picture %d" % n, "seen_not_taken": ["ACME"]}})
        picks.append(TrendPick.objects.create(board=board, number=n, kind=TrendPick.PICTURE, platform="dribbble",
                                              page_url="https://dribbble.com/shots/%d" % n, title="ACME %d" % n,
                                              image_url="https://cdn.dribbble.com/%d.png" % n, sha256=sha,
                                              used=True))
    TrendPick.objects.create(board=board, number=pictures + 1, kind=TrendPick.LINK, platform="pinterest",
                             # [his goal of 2026-10-10, item 3] a link shown only where it names the product: a compact,
                             # or a carton's box
                             page_url="https://www.pinterest.com/pin/1/", title="a pressed powder compact box")
    if confirmed_used is not None:
        board.used_at_confirm = [picks[i].pk for i in confirmed_used]
        board.save()
    return board, picks


@override_settings(ANTHROPIC_API_KEY="test-key", OPENAI_API_KEY="test-key", WEB_INSPIRATION_IN_GENERATION=True,
                   TREND_REVIEW_WINDOW_S=120)
class TrendStepTests(TestCase):
    """§BH71 PART 2 — ARIA's trend step: "Show the found pictures on the design page before directions. They are
    used by default; I can untick any I dislike in one click." Before its directions a design builds its trend board
    and waits at awaiting_trend_review while the review window is open; a restart re-arms the window and never
    searches again; a window that closed while nothing ran moves it on; a batch run uses every picture without
    waiting; a board with nothing to choose from, or one that failed, waits for nothing; the spend cap stops it."""

    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(brand=self.brand, task_text="a pressed powder compact",
                                              status="queued", design_target="product_container")

    def _run(self, build=None):
        from apps.pipeline.services import trend_board
        kw = {"side_effect": AssertionError("no search on this run")} if build is None else {"side_effect": build}
        with patch.object(trend_board, "build", **kw) as built, \
                patch.object(trend_board, "schedule_close") as close, \
                patch.object(ARIAAgent, "_run_direction_planning") as plan:
            ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()
        return built, close, plan

    def test_a_new_design_builds_its_board_and_waits_with_its_pictures_ticked(self):
        def build(task, log=None):
            return _trend_board(task)[0]
        built, close, plan = self._run(build)
        self.assertEqual(self.task.status, "awaiting_trend_review")
        board = TrendBoard.objects.get(task=self.task)
        self.assertIsNotNone(board.review_deadline)
        close.assert_called_once_with(self.task.id, 120)
        plan.assert_not_called()                                           # no direction before the pictures
        self.assertTrue(all(p.used for p in board.picks.filter(kind="picture")))

    def test_a_restart_while_it_waits_searches_nothing_and_rearms_the_close(self):
        from datetime import timedelta

        from django.utils import timezone
        from apps.pipeline.models import ApiCallRecord
        _trend_board(self.task, deadline=timezone.now() + timedelta(seconds=90))
        self.task.status = "awaiting_trend_review"
        self.task.save()
        built, close, plan = self._run()
        built.assert_not_called()
        self.assertEqual(self.task.status, "awaiting_trend_review")
        self.assertEqual(close.call_count, 1)
        self.assertLessEqual(close.call_args.args[1], 91)
        plan.assert_not_called()
        self.assertEqual(ApiCallRecord.objects.count(), 0)                  # nothing spent on a restart

    def test_a_window_that_closed_while_nothing_ran_moves_the_design_on(self):
        from datetime import timedelta

        from django.utils import timezone
        from apps.pipeline.services import trend_board
        _trend_board(self.task, deadline=timezone.now() - timedelta(seconds=5))
        _built, close, plan = self._run()
        plan.assert_called_once()
        close.assert_not_called()
        self.assertEqual(TrendBoard.objects.get(task=self.task).confirmed_how, trend_board.BY_THE_WINDOW)

    def test_a_batch_design_uses_every_picture_without_waiting(self):
        from apps.pipeline.models import BatchRun
        from apps.pipeline.services import trend_board
        self.task.batch = BatchRun.objects.create(brand=self.brand)
        self.task.save()

        def build(task, log=None):
            return _trend_board(task)[0]
        _built, close, plan = self._run(build)
        plan.assert_called_once()
        close.assert_not_called()
        board = TrendBoard.objects.get(task=self.task)
        self.assertEqual(board.confirmed_how, trend_board.BY_BATCH)
        self.assertEqual(len(board.used_at_confirm), 2)

    def test_a_board_with_nothing_to_choose_from_or_that_failed_waits_for_nothing(self):
        from apps.pipeline.services import trend_board

        def empty(task, log=None):
            return _trend_board(task, pictures=0)[0]
        _built, close, plan = self._run(empty)
        plan.assert_called_once()
        self.assertEqual(TrendBoard.objects.get(task=self.task).confirmed_how, trend_board.BY_NOTHING_TO_CHOOSE)
        other = DesignTask.objects.create(brand=self.brand, task_text="a compact", status="queued")
        self.task = other

        def failed(task, log=None):
            board = _trend_board(task, status="FAILED", pictures=0)[0]
            board.failure = "OutboundCallRefused"
            board.save()
            return board
        _built, close, plan = self._run(failed)
        plan.assert_called_once()
        close.assert_not_called()

    @override_settings(WEB_INSPIRATION_IN_GENERATION=False)
    def test_with_the_switch_off_no_board_is_built(self):
        built, close, plan = self._run()
        built.assert_not_called()
        plan.assert_called_once()
        self.assertFalse(TrendBoard.objects.filter(task=self.task).exists())

    def test_the_designs_cap_reached_while_building_stops_the_design(self):
        from apps.pipeline.services.cost_ledger import BudgetExceededError

        def capped(task, log=None):
            raise BudgetExceededError("task budget exceeded: $5.01 spent, cap is $5.00")
        _built, close, plan = self._run(capped)
        self.assertEqual(self.task.status, "failed")
        self.assertIn("task budget exceeded", self.task.error_message)
        plan.assert_not_called()

    def test_only_the_ticked_pictures_words_reach_the_planner(self):
        _board, picks = _trend_board(self.task, status="CONFIRMED", confirmed_used=[0])
        seen = {}

        class _CD:
            def __init__(self, *a, **kw):
                self.uploaded_reference_context = None
                self.candidate_reference_context = None
                self.web_reference_context = None

            def run_structured(self, *a, **kw):
                seen["web"] = self.web_reference_context
                raise _Stop()

        class _Stop(Exception):
            pass

        with patch("apps.pipeline.agents.aria.CreativeDirectorAgent", _CD), \
                patch("apps.pipeline.services.concept_references.build_candidates", return_value=[]):
            ARIAAgent(self.task.id)._run_direction_planning()
        self.assertIn("<<trends>>", seen["web"])
        self.assertIn("the take of picture 1", seen["web"])
        self.assertNotIn("the take of picture 2", seen["web"])             # unticked before the press
        self.assertNotIn("ACME", seen["web"])
        self.assertNotIn("dribbble.com", seen["web"])

    def test_the_prompt_writer_gives_the_trend_words_their_own_heading(self):
        from apps.pipeline.agents.prompt_engineer import PromptEngineerAgent
        sent = {}

        def claude(system, message, **kw):
            sent["message"] = message
            return MagicMock(content=[MagicMock(type="text", text='{"prompts": []}')])
        agent = PromptEngineerAgent([{"name": "Rose"}], None)
        agent.trend_context = "CURRENT TRENDS ... <<trends>>\n- Trend picture 1 (found on Dribbble): quiet\n<<end trends>>"
        with patch("apps.pipeline.agents.prompt_engineer.call_claude", claude):
            agent.run()
        self.assertIn("## Current trends found on the web (words only)", sent["message"])
        self.assertNotIn("Owner-uploaded references", sent["message"])     # never under his uploads' heading


@override_settings(ANTHROPIC_API_KEY="test-key", OPENAI_API_KEY="test-key", TREND_REVIEW_WINDOW_S=120)
class TrendBoardEndpointTests(TestCase):
    """§BH71 PART 2 — the design page's trend board: what the status tells the page, the one-click untick, the press
    that makes the directions now, and the thumbnails served from quarantine on the site's own origin."""

    def setUp(self):
        import tempfile
        from datetime import timedelta

        from django.contrib.auth.models import Group
        from django.utils import timezone

        from apps.pipeline.permissions import ROLE_REVIEWER
        self.user = User.objects.create_user("tb", "tb@t.com", "pw")
        self.user.groups.add(Group.objects.get_or_create(name=ROLE_REVIEWER)[0])
        self.client.force_login(self.user)
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(brand=self.brand, task_text="a pressed powder compact",
                                              status="awaiting_trend_review", created_by=self.user)
        self.board, self.picks = _trend_board(self.task, deadline=timezone.now() + timedelta(seconds=100))
        self.quarantine = tempfile.mkdtemp(prefix="trendq_")
        self.addCleanup(__import__("shutil").rmtree, self.quarantine, True)
        thumb = __import__("pathlib").Path(self.quarantine) / "7" / "trend_01_thumb.png"
        thumb.parent.mkdir(parents=True)
        from PIL import Image
        Image.new("RGB", (40, 30), (200, 150, 160)).save(thumb)
        self.picks[0].thumb_path, self.picks[0].thumb_width, self.picks[0].thumb_height = str(thumb), 40, 30
        self.picks[0].save()

    def test_the_status_tells_the_page_the_board_numbered_ticked_and_its_cost(self):
        with override_settings(WEB_QUARANTINE_ROOT=self.quarantine):
            data = self.client.get("/api/tasks/%d/status/" % self.task.id).json()
        board = data["trend_board"]
        self.assertEqual(board["status"], "READY")
        self.assertTrue(0 < board["seconds_left"] <= 100)
        self.assertEqual([p["number"] for p in board["pictures"]], [1, 2])
        self.assertTrue(all(p["used"] and p["feeds"] for p in board["pictures"]))
        self.assertEqual(board["pictures"][0]["thumb_url"], "/api/tasks/%d/trends/%d/thumbnail/" % (
            self.task.id, self.picks[0].pk))
        self.assertNotIn(self.quarantine, str(board))                       # the quarantine path is never shown
        self.assertIn("the take of picture 1", board["pictures"][0]["words"])
        self.assertEqual(board["links"][0]["platform"], "Pinterest")
        self.assertEqual(board["ticked"], 2)
        self.assertEqual(board["cost"]["total_usd"], "0")

    def test_one_click_unticks_a_picture_until_the_press_and_the_press_moves_the_design_on(self):
        from apps.pipeline.services import trend_board
        url = "/api/tasks/%d/trends/%d/" % (self.task.id, self.picks[1].pk)
        self.assertEqual(self.client.post(url, {"used": "no"}, content_type="application/json").status_code, 400)
        answer = self.client.post(url, {"used": False}, content_type="application/json")
        self.assertEqual(answer.json(), {"pick": self.picks[1].pk, "used": False})
        link = self.board.picks.get(kind="link")
        refused = self.client.post("/api/tasks/%d/trends/%d/" % (self.task.id, link.pk), {"used": True},
                                   content_type="application/json")
        self.assertEqual(refused.status_code, 409)
        self.assertIn("link card", refused.json()["words"])
        with patch("apps.pipeline.tasks.run_aria_pipeline.delay") as run, \
                self.captureOnCommitCallbacks(execute=True):
            pressed = self.client.post("/api/tasks/%d/trends/continue/" % self.task.id)
        self.assertEqual(pressed.json(), {"queued": True})
        run.assert_called_once_with(self.task.id)
        self.board.refresh_from_db()
        self.assertEqual(self.board.confirmed_how, trend_board.BY_HIS_CLICK)
        self.assertEqual(self.board.used_at_confirm, [self.picks[0].pk])
        self.assertEqual(self.board.confirmed_by, self.user)
        again = self.client.post("/api/tasks/%d/trends/continue/" % self.task.id)
        self.assertEqual(again.status_code, 409)                           # one press wins
        late = self.client.post(url, {"used": True}, content_type="application/json")
        self.assertEqual(late.status_code, 409)                            # the directions are being made
        self.assertIn("changes nothing", late.json()["words"])

    def test_a_thumbnail_is_served_from_quarantine_on_our_origin_and_nothing_outside_it(self):
        url = "/api/tasks/%d/trends/%d/thumbnail/" % (self.task.id, self.picks[0].pk)
        with override_settings(WEB_QUARANTINE_ROOT=self.quarantine):
            served = self.client.get(url)
            self.assertEqual((served.status_code, served["Content-Type"]), (200, "image/png"))
            self.assertEqual(self.client.get("/api/tasks/%d/trends/%d/thumbnail/" % (
                self.task.id, self.picks[1].pk)).status_code, 404)             # no thumbnail
            self.picks[0].thumb_path = "/etc/hosts"
            self.picks[0].save()
            self.assertEqual(self.client.get(url).status_code, 404)           # outside the quarantine: never
        self.client.logout()
        self.assertIn(self.client.get(url).status_code, (401, 403))

    def test_the_design_page_has_the_board_before_the_directions(self):
        html = self.client.get("/dashboard/designs/%d/" % self.task.id).content.decode()
        self.assertIn('id="trend-state"', html)
        self.assertLess(html.index('id="trend-state"'), html.index('id="direction-state"'))
        self.assertIn("js/trends.js", html)

    def test_no_trend_picture_ever_reaches_the_image_model_or_the_design(self):
        """ "The pictures themselves are never placed": a board's pictures stay in quarantine — never a reference the
        drawing or the image model is handed, whatever is ticked."""
        from apps.pipeline.services import reference_manifest as rm
        from apps.pipeline.services import trend_board
        from apps.pipeline.services.visual_reference_resolver import resolve_visual_references
        trend_board.confirm(self.task, trend_board.BY_HIS_CLICK, self.user)
        bundle = resolve_visual_references(self.task)
        self.assertFalse([p for p in bundle.upload_paths if self.quarantine in str(p) or "trend" in str(p)])
        manifest = rm.build_task_reference_manifest(self.task)
        self.assertEqual(manifest["reference_count"], 0)                   # a trend picture is never a reference
        self.assertEqual(rm.raster_attachment_descriptors(manifest), [])


@override_settings(WEB_INSPIRATION_IN_GENERATION=True)
class TheCapStopsTheWebWireTests(TestCase):
    """§BH71 PART 2: a search is a ledger row now, so the design's spend cap can stop the web inspiration wire — and
    the design with it, as every paid call stops it. The wire's catch-all said "web inspiration unavailable" and the
    design went on to its next paid call."""

    def setUp(self):
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        product = Product.objects.create(brand=brand, product_id="BBR-CO-778", name="Capped", category="CO",
                                         year=2026, product_type="compact")
        self.task = DesignTask.objects.create(brand=brand, product=product, task_text="a compact", status="running")

    @override_settings(ANTHROPIC_API_KEY="test-key", OPENAI_API_KEY="test-key")
    def test_the_designs_cap_reached_by_a_search_stops_the_design(self):
        # [§BH71 PART 2: the search is the trend board's now, made in the trend step before the directions — the
        # wire this test first read was retired with its session]
        from apps.pipeline.services import web_research_tavily as tv
        from apps.pipeline.services import round_designer as rd
        from apps.pipeline.services.cost_ledger import BudgetExceededError
        with patch.object(rd.TavilySearchConnector, "search",
                          side_effect=BudgetExceededError("task budget exceeded: $5.01 spent, cap is $5.00")), \
                patch("apps.pipeline.services.concept_references.build_candidates", return_value=[]), \
                patch("apps.pipeline.agents.aria.CreativeDirectorAgent") as planner:
            ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "failed")
        self.assertIn("task budget exceeded", self.task.error_message)
        planner.return_value.run_structured.assert_not_called()


@override_settings(WEB_INSPIRATION_IN_GENERATION=False)
class HouseLibraryReachesThePlannerTests(TestCase):

    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="BBR-CO-777", name="Test Palette",
            category="CO", year=2026, product_type="palette")
        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product,
            task_text="a rose palette", status="running")

    def _plan_and_capture(self, candidates):
        """Run ARIA's direction planning far enough to see what the CD was given."""
        seen = {}

        class _CD:
            def __init__(self, *a, **kw):
                self.uploaded_reference_context = None
                self.candidate_reference_context = None
                self.web_reference_context = None

            def run_structured(self, *a, **kw):
                seen["candidate"] = self.candidate_reference_context
                raise _Stop()

        class _Stop(Exception):
            pass

        kw = ({"side_effect": candidates} if isinstance(candidates, Exception)
              else {"return_value": candidates})
        with patch("apps.pipeline.agents.aria.CreativeDirectorAgent", _CD), \
                patch("apps.pipeline.services.concept_references.build_candidates",
                      **kw) as bc:
            agent = ARIAAgent(self.task.id)
            try:
                agent._run_direction_planning()
            except _Stop:
                pass
            except Exception:
                pass
        return seen, bc

    def test_the_candidates_reach_the_creative_director(self):
        """The claim the commit made. Not "the call did not raise" — that was true while it failed."""
        c = SimpleNamespace(title="A pressed rose compact", source_type="HISTORICAL_DESIGN_REFERENCE",
                            description="warm cream lid, gold rule", relevance_reason="category match")
        seen, bc = self._plan_and_capture([c])
        self.assertTrue(bc.called, "the run must ASK the library, not wait for a person to open a page")
        self.assertIsNotNone(seen.get("candidate"),
                             "the library answered and the planner was told nothing")
        # [his test findings on design 121, 2026-10-07, item 4: "Earlier designs may inform style only, never names."]
        # the entry's style reaches the planner, named by its kind; its file's title no longer
        self.assertIn("a past BBROSE design — warm cream lid, gold rule", seen["candidate"])
        self.assertNotIn("A pressed rose compact", seen["candidate"])
        self.assertIn("THE HOUSE LIBRARY HOLDS THESE", seen["candidate"])

    def test_it_is_called_with_the_resolved_profile_and_not_an_attribute_that_does_not_exist(self):
        """THE DEFECT, pinned by name. `self.product_profile` is not an attribute of ARIAAgent; reaching for
        it raised AttributeError on every run, and the handler reported the LIBRARY as unavailable."""
        self.assertFalse(hasattr(ARIAAgent, "product_profile"),
                         "if this ever becomes a real attribute, read this test before using it")
        _, bc = self._plan_and_capture([])
        self.assertTrue(bc.called)
        self.assertIn("profile", bc.call_args.kwargs)

    def test_nothing_is_approved_by_the_machine(self):
        """concept_references: "user selects 2-4 in the UI — never automatic"; "machine code never sets
        APPROVED". The run reads the library; approval stays a person's act."""
        from apps.pipeline.models import ConceptReference
        c = SimpleNamespace(title="t", source_type="MATERIAL_LIBRARY_ITEM",
                            description="d", relevance_reason="r")
        self._plan_and_capture([c])
        self.assertEqual(
            ConceptReference.objects.filter(
                task=self.task,
                permission_status=ConceptReference.PERMISSION_APPROVED).count(), 0)

    def test_a_library_that_really_fails_names_the_reason_instead_of_blaming_the_library(self):
        """The handler used to assert "house library unavailable" for any exception at all, including a
        programming error in the line above it. It names the type now, which is the thing that would have
        made this defect visible in the first line of task 85's log."""
        self._plan_and_capture(RuntimeError("index offline"))
        actions = [L.action for L in AgentLog.objects.filter(task=self.task)]
        hit = [a for a in actions if "house library not consulted" in a]
        self.assertTrue(hit, "the run must say the library was not consulted: %s" % actions)
        self.assertIn("RuntimeError", hit[0])
        self.assertNotIn("unavailable", hit[0])


# --- [his final goal, 2026-10-05, B4: "NO PROMPT STEP. Three directions planned privately and validated. Three truly
# different concepts drawn straight away. Each picture shows a name and one sentence; the details folded. He picks a
# picture."] -------------------------------------------------------------------------------------------------------

B4_PROMPTS = [{"direction_id": did, "direction_name": "named by the model", "full_prompt": "a carton for %s" % did,
               "aspect_ratio": "9:21", "notes": ""} for did in ("d3", "d1", "d2")]


@override_settings(ANTHROPIC_API_KEY="test-key", OPENAI_API_KEY="test-key",
                   BRAND_LOGO_PATH="/nonexistent/bh57/no-logo.png")
class NoPromptStepTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("tb4", "t@t.com", "password")
        self.brand = Brand.objects.create(name="BBROSE", master_brief="brief")
        self.product = Product.objects.create(
            brand=self.brand, product_id="P-4", name="Dew Serum", category="SK", year=2026)
        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="Serum carton concept", status="queued",
            created_by=self.user)
        self.statuses = []

        from django.db.models.signals import post_save

        def trace(sender, instance, **kw):
            if instance.pk == self.task.pk:
                self.statuses.append(instance.status)
        post_save.connect(trace, sender=DesignTask, weak=False, dispatch_uid="b4-trace")
        self.addCleanup(post_save.disconnect, sender=DesignTask, dispatch_uid="b4-trace")

    def _run(self, pe_payload=None):
        with patch("apps.pipeline.agents.creative_director.call_claude",
                   return_value=_claude(valid_document())) as mock_cd, \
                patch("apps.pipeline.agents.prompt_engineer.call_claude",
                      return_value=_claude(pe_payload or {"prompts": B4_PROMPTS})) as mock_pe, \
                patch("apps.pipeline.agents.qa_reviewer.call_claude",
                      return_value=_claude(critique(9))), \
                patch("apps.pipeline.agents.image_producer.openai.images.generate",
                      return_value=_openai_image()) as mock_gen, \
                patch("apps.pipeline.agents.image_producer.requests.get",
                      return_value=MagicMock(status_code=200, content=b"png")):
            ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()
        return mock_cd, mock_pe, mock_gen

    def test_b4_a_new_design_goes_from_its_plan_straight_to_one_picture_for_each_direction(self):
        """Three directions planned and validated, then one picture for each — bound to it by id, in the plan's order,
        named as the plan names it — and the design waits at Gate 1 for his pick; no direction is asked of him."""
        _cd, mock_pe, mock_gen = self._run()
        self.assertEqual(self.task.status, "awaiting_gate_1", self.task.error_message)
        self.assertNotIn("awaiting_direction_selection", self.statuses)
        self.assertEqual(mock_pe.call_count, 1)                        # one prompt call, as before
        system, content = mock_pe.call_args.args[0], mock_pe.call_args.args[1]
        self.assertIn("Build one dieline-aware image generation prompt per direction.", content)
        self.assertNotIn("VARIATIONS WITHIN", system)
        for name in ("Porcelain Verse", "Botanical Meridian", "Still Water Relief"):
            self.assertIn(name, content)
        images = list(GeneratedImage.objects.filter(task=self.task).order_by("pk"))
        self.assertEqual([i.direction_id for i in images], ["d1", "d2", "d3"])
        self.assertEqual([i.direction_name for i in images],
                         ["Porcelain Verse", "Botanical Meridian", "Still Water Relief"])
        self.assertEqual(mock_gen.call_count, 3)
        self.assertEqual(CreativeBrief.objects.get(task=self.task).selected_direction_id, "")

    def test_goal_1010_item1_prompts_not_one_for_each_direction_are_bound_in_order_with_a_note(self):
        """[Re-pinned by his goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 1: "NO planner check ever stops a design (not only "not distinct"): on failure it retries once with the reason; if it still fails, it shows me the three directions with a plain note, and I choose."] Three prompts that all name
        the first direction, twice: asked once more with why, then bound to the three directions in their order and
        drawn, the page saying so in words; nothing stops."""
        from apps.dashboard.words import alike_words
        twice = [dict(p, direction_id="d1") for p in B4_PROMPTS]
        _cd, mock_pe, mock_gen = self._run({"prompts": twice})
        self.assertEqual(mock_pe.call_count, 2)                         # [B4c] asked once more, with why
        self.assertEqual(self.task.status, "awaiting_gate_1", self.task.error_message)
        self.assertEqual([i.direction_id for i in GeneratedImage.objects.filter(task=self.task).order_by("pk")],
                         ["d1", "d2", "d3"])
        self.assertEqual(mock_gen.call_count, 3)
        self.assertEqual(alike_words(self.task), [
            "Shown anyway: the instructions for the three concept pictures failed their checks twice — the three "
            "concepts were not each matched to their direction, so they are matched in order; made once more with "
            "that reason, they still did. You choose."])

    def test_b4_each_picture_shows_its_directions_name_and_one_sentence(self):
        from apps.pipeline.serializers import GeneratedImageSerializer
        self._run()
        rows = GeneratedImageSerializer(GeneratedImage.objects.filter(task=self.task).order_by("pk"), many=True).data
        brief = CreativeBrief.objects.get(task=self.task)
        for row, direction in zip(rows, brief.directions):
            self.assertEqual(row["direction_name"], direction["name"])
            sentence = row["direction_sentence"]
            self.assertTrue(sentence and sentence[-1] in ".!?" and sentence in " ".join(
                direction["concept_statement"].split()), sentence)
            self.assertLessEqual(sentence.count(". "), 0)              # one sentence

    def test_b4c_prompts_that_name_their_directions_but_not_their_ids_are_bound_by_name(self):
        """[His final goal, 2026-10-05, B4c] A live model may name each direction and leave its id out: each prompt is
        bound by its direction's exact name (the plan's names are distinct), and the log says so; one prompt call."""
        named = [{"direction_name": n, "full_prompt": "a carton for " + n, "aspect_ratio": "9:21", "notes": ""}
                 for n in ("still water relief", "Porcelain Verse", "Botanical  Meridian")]
        _cd, mock_pe, _gen = self._run({"prompts": named})
        self.assertEqual(self.task.status, "awaiting_gate_1", self.task.error_message)
        self.assertEqual(mock_pe.call_count, 1)
        images = list(GeneratedImage.objects.filter(task=self.task).order_by("pk"))
        self.assertEqual([i.direction_id for i in images], ["d1", "d2", "d3"])
        self.assertTrue(AgentLog.objects.filter(task=self.task, action__contains="bound by its direction's name").exists())

    def test_b4c_prompts_not_bound_are_asked_for_once_more_with_why(self):
        """Not one for each direction by id or name: the step is asked once more, with why, before anything stops."""
        unbound = [dict(p, direction_id="d1", direction_name="?") for p in B4_PROMPTS]
        with patch("apps.pipeline.agents.creative_director.call_claude", return_value=_claude(valid_document())), \
                patch("apps.pipeline.agents.prompt_engineer.call_claude",
                      side_effect=[_claude({"prompts": unbound}), _claude({"prompts": B4_PROMPTS})]) as mock_pe, \
                patch("apps.pipeline.agents.qa_reviewer.call_claude",
                      return_value=_claude(critique(9))), \
                patch("apps.pipeline.agents.image_producer.openai.images.generate", return_value=_openai_image()), \
                patch("apps.pipeline.agents.image_producer.requests.get",
                      return_value=MagicMock(status_code=200, content=b"png")):
            ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "awaiting_gate_1", self.task.error_message)
        self.assertEqual(mock_pe.call_count, 2)
        self.assertIn("Your previous answer was refused", mock_pe.call_args_list[1].args[1])
        self.assertEqual([i.direction_id for i in GeneratedImage.objects.filter(task=self.task).order_by("pk")],
                         ["d1", "d2", "d3"])

    @patch("apps.pipeline.tasks.resume_aria_gate1.delay")
    def test_b4_the_picture_he_picks_names_the_direction_the_design_goes_on_in(self, _resume):
        self._run()
        picked = GeneratedImage.objects.get(task=self.task, direction_id="d2")
        self.client.force_login(self.user)
        r = self.client.post("/api/tasks/%d/gate1_approve/" % self.task.pk, {"image_id": picked.pk},
                             content_type="application/json")
        self.assertIn(r.status_code, (200, 202), r.content[:400])
        brief = CreativeBrief.objects.get(task=self.task)
        self.assertEqual(brief.selected_direction_id, "d2")
        self.assertIsNotNone(brief.direction_selected_at)

    def test_b4_asking_for_changes_draws_the_three_directions_again_with_his_notes(self):
        self._run()
        first = set(GeneratedImage.objects.filter(task=self.task).values_list("id", flat=True))
        self.task.status, self.task.gate_1_notes = "queued", "push warmth"
        self.task.save()
        mock_cd, mock_pe, _gen = self._run()
        self.assertEqual(self.task.status, "awaiting_gate_1")
        self.assertEqual(mock_cd.call_count, 0)                        # never re-planned
        mock_pe.assert_not_called()
        self.assertEqual(_gen.call_count, 3)
        self.assertTrue(all("push warmth" in c.kwargs["prompt"] for c in _gen.call_args_list))
        fresh = GeneratedImage.objects.filter(task=self.task, superseded=False).order_by("pk")
        self.assertEqual([i.direction_id for i in fresh], ["d1", "d2", "d3"])
        self.assertTrue(all(GeneratedImage.objects.get(pk=i).superseded for i in first))

    def test_b4_a_container_asks_its_contract_for_one_variation_for_each_direction(self):
        """The container's structured contract, given the three directions: one call, one variation for each in slot
        order, each echoing its direction's id — a variation bound to the wrong direction is refused by name."""
        from apps.pipeline.services import container_gate1 as cg1
        from apps.pipeline.services.gate1_prompts import (PROMPTS_NOT_BOUND_TO_DIRECTIONS,
                                                          build_regeneration_prompts)
        directions = valid_document()["directions"]
        sent = []

        def answer(order):
            def call(system, message):
                sent.append(message)
                variations = []
                for n, did in enumerate(order):
                    v = {f: "%s %d" % (f, n) for f in cg1.CONTAINER_DIVERSITY_FIELDS}
                    v.update(variation_id=("A_ROSE_VEIL", "B_PETAL_LINE", "C_DEW_FIELD")[n], title="t%d" % n,
                             prompt=("a tall serum bottle for direction %s, a soft rose body, cream type, a gold cap, "
                                     "soft studio light on a plain warm ground. " % did) * 3,
                             native_reconstruction_plan="live type", reference_ids=[], direction_id=did)
                    variations.append(v)
                return json.dumps({"schema_version": cg1.CONTAINER_GATE1_SCHEMA, "approved_reference_ids": [],
                                   "influence_plan_hash": "", "variations": variations}), "stub"
            return call

        kw = dict(direction={}, directions=directions, product_block="a serum bottle", influence_plan={}, plan_hash="",
                  reference_ids=[], variation_identities=(), richness_directives=cg1.CONTAINER_DIRECTIONS_DIRECTIVES,
                  system=cg1.CONTAINER_SYSTEM, schema_version=cg1.CONTAINER_GATE1_SCHEMA,
                  required_fields=cg1.CONTAINER_REQUIRED_FIELDS_NO_REFS,
                  diversity_fields=cg1.CONTAINER_DIVERSITY_FIELDS, min_pairwise=cg1.CONTAINER_MIN_PAIRWISE_DIFFERENCES,
                  identity_slots=cg1.CONTAINER_VARIATION_SLOTS, max_attempts=1)
        ok = build_regeneration_prompts(call_model=answer(["d1", "d2", "d3"]), **kw)
        self.assertTrue(ok.ok, ok.codes)
        self.assertEqual([(p["direction_id"], p["direction_name"]) for p in ok.prompts],
                         [(d["direction_id"], d["name"]) for d in directions])
        self.assertIn("ONE variation for each", sent[0])
        self.assertIn("Draw the three planned directions", sent[0])
        bad = build_regeneration_prompts(call_model=answer(["d2", "d1", "d3"]), **kw)
        # [re-pinned by his goal of 2026-10-10, item 1: "NO planner check ever stops a design"] refused by
        # name, then drawn bound by its slots, the refusal its note
        self.assertTrue(bad.ok)
        self.assertTrue(any(c.startswith(PROMPTS_NOT_BOUND_TO_DIRECTIONS) for c in bad.alike), bad.alike)
        self.assertEqual([p["direction_id"] for p in bad.prompts], ["d1", "d2", "d3"])


# ---- [his test findings on design 121, 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md), item 1: "The ID binding from your last
# ---- round (B4c) clashes with the older naming rule. Make them agree, so a design can never stop here again."]

def _container_step(answers, **kw):
    """The container's concept step as the container calls it (targets/container, three directions, no references),
    answered by ``answers`` in turn — the live model's own words, recorded on 121."""
    from apps.pipeline.services import container_gate1 as cg1
    from apps.pipeline.services.gate1_prompts import build_regeneration_prompts
    queue, asked = list(answers), []

    def call(system, text):
        asked.append(text)
        return queue.pop(0), "anthropic:recorded"
    directions = [{"direction_id": "d%d" % n, "name": name} for n, name in
                  ((1, "Rebel Bloom"), (2, "Retro Rebel Type"), (3, "Petal Scatter Field"))]
    result = build_regeneration_prompts(
        direction={}, directions=directions, product_block="a squeeze tube of hand cream", influence_plan={},
        plan_hash="", reference_ids=[], variation_identities=(),
        richness_directives=cg1.CONTAINER_DIRECTIONS_DIRECTIVES, call_model=call, system=cg1.CONTAINER_SYSTEM,
        schema_version=cg1.CONTAINER_GATE1_SCHEMA, required_fields=cg1.CONTAINER_REQUIRED_FIELDS_NO_REFS,
        diversity_fields=cg1.CONTAINER_DIVERSITY_FIELDS, min_pairwise=cg1.CONTAINER_MIN_PAIRWISE_DIFFERENCES,
        schema_code=cg1.CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED,
        empty_code=cg1.CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED,
        not_distinct_code=cg1.CONTAINER_GATE1_VARIATIONS_NOT_DISTINCT,
        identity_code=cg1.CONTAINER_VARIATION_IDENTITY_MISSING, operation="container_gate1_variations",
        identity_slots=cg1.CONTAINER_VARIATION_SLOTS, **kw)
    return result, asked


def test_his_test_findings_121_the_live_models_two_answers_each_pass_in_one_call():
    """Each of the live model's two answers recorded on 121 — the first named by its slots with no direction ids, the
    second with the ids folded into its names — stands on its own now: one call, the three variations named by their
    slots and bound to their directions in order."""
    from apps.pipeline.tests.fixtures_agentlog2420 import RAW_RESPONSES
    for raw in RAW_RESPONSES:
        result, asked = _container_step([raw])
        assert result.ok and result.attempts == 1 and len(asked) == 1, result.codes
        assert [p["variation_id"] for p in result.prompts] == ["A_REBEL_BLOOM", "B_TYPE_IN_BLOOM", "C_PETAL_VEIL"]
        assert [p["direction_id"] for p in result.prompts] == ["d1", "d2", "d3"]


def test_his_test_findings_121_without_the_agreement_the_same_answers_stop_as_121_stopped():
    """THE CONTROL: the two rules read apart, as at 09f5f41, and the same two recorded answers — the first refused by
    the direction binding, the second by the slot rule: 121's own refusal, reproduced. [Re-pinned by his goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 1: "NO planner check ever stops a design (not only "not distinct"): on failure it retries once with the reason; if it still fails, it shows me the three directions with a plain note, and I choose."]
    It no longer stops: the second answer is drawn bound by its slots, the refusal its note."""
    from apps.pipeline.tests.fixtures_agentlog2420 import RAW_RESPONSES
    with patch("apps.pipeline.services.gate1_prompts.agree_ids", lambda *a, **k: []):
        result, asked = _container_step(list(RAW_RESPONSES))
    assert result.ok and len(asked) == 2 and result.alike_attempts == (1, 2)
    assert any(c.startswith("CONTAINER_VARIATION_IDENTITY_MISSING") for c in result.alike), result.alike
    assert [p["direction_id"] for p in result.prompts] == ["d1", "d2", "d3"]
    assert "never inside its variation_id" in asked[1]           # the repair said where the id belongs


def test_his_test_findings_121_an_id_for_another_direction_is_still_refused_with_why():
    """The agreement reads a slot's OWN direction id out of a name; a variation that names ANOTHER direction is left
    for the binding to refuse — said, with where the id belongs."""
    from apps.pipeline.services.gate1_prompts import agree_ids, direction_binding_codes
    directions = [{"direction_id": "d%d" % n} for n in (1, 2, 3)]
    payload = {"variations": [{"variation_id": "A_d2_REBEL_BLOOM"}, {"variation_id": "B-type in bloom"},
                              {"variation_id": "C_", "title": "Petal Veil", "direction_id": "d1"}]}
    said = agree_ids(payload, identity_slots=("A", "B", "C"), directions=directions)
    assert [v["variation_id"] for v in payload["variations"]] == ["A_d2_REBEL_BLOOM", "B_TYPE_IN_BLOOM", "C_PETAL_VEIL"]
    assert "B-type in bloom read as B_TYPE_IN_BLOOM" in said and "C_ read as C_PETAL_VEIL" in said
    codes = direction_binding_codes(payload, directions)
    assert codes and "never inside its variation_id" in codes[0]


# ---- [his test findings on design 121, 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md), item 3: "Errors are shown to me in words,
# ---- never engine codes (this one was raw codes again)."]

#: an engine code as the record writes one — what he is never shown
_ENGINE_CODE = r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b"

#: 121's own recorded reason, as its record holds it
_REASON_121 = ("Gate-1 variation contract not satisfied after the bounded repair (CONTAINER_VARIATION_IDENTITY_MISSING: "
               "variations[0].variation_id 'A_d1_REBEL_BLOOM' must be A_<NAME> — the slot letter, then the variation's "
               "own concept name in capitals and underscores; CONTAINER_VARIATION_IDENTITY_MISSING: variations[1]."
               "variation_id 'B_d2_TYPE_IN_BLOOM' must be B_<NAME>) — zero images were generated")


class StopReasonInWordsTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="B121", master_brief="x")
        self.task = DesignTask.objects.create(brand=brand, task_text="a tube", status="failed",
                                              design_target="product_container")

    def test_121s_own_reason_is_said_in_words(self):
        from apps.dashboard.words import stop_words
        self.task.error_message = _REASON_121
        words = stop_words(self.task)
        self.assertNotRegex(words, _ENGINE_CODE)
        self.assertIn("instructions for the three concept pictures failed their own checks twice", words)
        self.assertIn("the three concepts were not each named for their direction", words)

    def test_a_reason_with_no_words_written_for_it_names_the_step_it_stopped_on_never_its_codes(self):
        from apps.dashboard.words import stop_words
        from apps.pipeline.models import AgentLog
        AgentLog.objects.create(task=self.task, agent_name="ARIA", level="info",
                                action="ARIA: three design directions planned and validated — drawing one picture for each")
        self.task.error_message = "SOMETHING_NEW_FAILED: a check written after this test, {'detail': None}"
        words = stop_words(self.task)
        self.assertNotRegex(words, _ENGINE_CODE)
        self.assertIn("It stopped while drawing one concept picture for each direction", words)
        self.task.error_message = "The picture service is busy; try again in a minute"       # words already: kept
        self.assertEqual(stop_words(self.task), "The picture service is busy; try again in a minute")

    def test_the_status_and_the_feed_say_it_in_words(self):
        from apps.pipeline.feed_words import said
        from apps.pipeline.models import AgentLog
        user = User.objects.create_superuser("w121", password="x")
        self.client.force_login(user)
        DesignTask.objects.filter(pk=self.task.pk).update(error_message=_REASON_121)
        AgentLog.objects.create(task=self.task, agent_name="ARIA", level="error",
                                action="ARIA: pipeline failed — " + _REASON_121)
        body = self.client.get("/api/tasks/%d/status/" % self.task.pk).json()
        self.assertIn("concept pictures", body["stop_words"])
        self.assertNotRegex(body["stop_words"], _ENGINE_CODE)
        self.assertNotRegex(said("ARIA: pipeline failed — " + _REASON_121), _ENGINE_CODE)
        self.assertEqual(said("Gate-1 variation contract result — refused"),
                         "the prompts failed their checks — no concept picture drawn")


# ---- [his test findings on design 121, 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md), item 4: "A new design never takes names,
# ---- words or ideas from another design's brief. Earlier designs may inform style only, never names."]

#: the house library's own words for three past designs, as 121's planner read them
_LIBRARY_121 = (
    "A BBROSE 'Juicy Lips' lip oil retail display box dieline (239×162×55mm) featuring a whimsical kawaii cartoon "
    "mascot character with big eyes, playful bubble lettering",
    "A soft blush pink and white sunscreen packaging dieline (FS5817) for BBROSE SPF 90 Protector Solar, featuring a "
    "central sun illustration with radiating rays, gold foil typography",
    "BBRose Solid Blush (BL2050) retail display stand dieline featuring a stylized fashion-illustration woman in "
    "sunglasses on a cream-and-beige corrugated tray")


class EarlierDesignsInformStyleOnlyTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.other = Product.objects.create(
            brand=self.brand, product_id="BBR-CO-881", name="Velvet Dusk Lip Oil", category="CO", year=2026,
            product_type="lip oil", finish_notes="glossy lacquer, a gold foil rule",
            notes="Story: dusk to dawn, a rose that opens in the dark")
        self.task = DesignTask.objects.create(brand=self.brand, task_text="a rose lip oil in a slim vial with gold",
                                              status="running")

    def test_the_library_lends_its_style_never_its_names_or_codes(self):
        from apps.pipeline.agents.aria import candidate_reference_context
        from apps.pipeline.services.other_designs import style_only
        said = [style_only(text) for text in _LIBRARY_121]
        for name in ("Juicy Lips", "SPF 90 Protector Solar", "Solid Blush", "FS5817", "BL2050"):
            self.assertFalse(any(name in s for s in said), (name, said))
        self.assertIn("whimsical kawaii cartoon mascot character with big eyes", said[0])
        self.assertIn("central sun illustration with radiating rays, gold foil typography", said[1])
        lines = candidate_reference_context([SimpleNamespace(
            title="YB-BB-202509-1239_LP5922_", source_type="HISTORICAL_DESIGN_REFERENCE", description=_LIBRARY_121[0],
            relevance_reason="shared design vocabulary character/cream")])
        self.assertIn("- a past BBROSE design — ", lines)
        self.assertNotIn("YB-BB-202509-1239", lines)
        self.assertNotIn("Juicy Lips", lines)

    def test_a_similar_product_lends_its_kind_and_finish_never_its_name_or_story(self):
        from apps.pipeline.services.brand_context import find_similar_products
        from apps.pipeline.services.other_designs import names_of_other_designs, similar_style
        found = similar_style(find_similar_products(self.brand.pk, None, self.task.task_text),
                              names_of_other_designs(self.task))
        self.assertEqual(found, [{"category": "CO", "product_type": "lip oil",
                                  "finish_notes": "glossy lacquer, a gold foil rule"}])

    def test_the_planner_is_told_the_rule_and_handed_no_other_designs_name(self):
        from apps.pipeline.agents import creative_director as cdm

        class _Stop(Exception):
            pass
        seen = {}

        def capture(**kw):
            seen.update(kw)
            raise _Stop()
        agent = cdm.CreativeDirectorAgent(self.task, self.brand.pk)
        with patch.object(cdm, "generate_design_directions", capture), \
                patch("apps.pipeline.services.reference_index.select_reference_records", return_value=[]), \
                patch("apps.pipeline.services.brand_context.get_design_references", return_value=[]):
            with self.assertRaises(_Stop):
                agent.run_structured()
        told = "\n".join(seen["reference_summaries"])
        self.assertIn("Never take a name, a line of copy, a story, an idea or a main motif from them", told)
        self.assertIn("glossy lacquer, a gold foil rule", told)
        for word in ("Velvet Dusk", "BBR-CO-881", "dusk to dawn"):
            self.assertNotIn(word, told)

    def test_a_past_designs_anatomy_keeps_its_shape_and_its_style_never_its_copy(self):
        """The anatomy reached 121's planner with each past design's copy in it ("'Lip Oil' set in large mixed-weight
        script ... with 'Subtle Gloss' as a smaller subtitle"): its words are cleaned where they stand — its keys, its
        layout and its type kept, its quoted copy out — and the reference is named by its kind."""
        import json as _json
        from apps.pipeline.services.reference_index import anatomy_digest
        ref = SimpleNamespace(name="YB-1025_LP5870___", product_type="lip oil", anatomy={"layout": {
            "title_treatment": "'Lip Oil' set in large mixed-weight script lettering, with 'Subtle Gloss' as a smaller "
                               "subtitle beneath in italic script", "logo_position": "upper third, centered"},
            "motifs": [{"placement": "corner clusters"}]})
        digest = anatomy_digest([ref])
        self.assertTrue(digest.startswith("reference 1 (lip oil): "), digest)
        blob = _json.loads(digest.split(": ", 1)[1])
        self.assertEqual(sorted(blob), ["layout", "motifs"])
        self.assertIn("set in large mixed-weight script lettering", blob["layout"]["title_treatment"])
        self.assertEqual(blob["motifs"], [{"placement": "corner clusters"}])
        for word in ("Lip Oil", "Subtle Gloss", "YB-1025"):
            self.assertNotIn(word, digest)


class HisTestBlocker122BackdropTests(TestCase):
    """[His test blocker on design 122, 2026-10-07, item 3] "A one-colour brief (all pink) must still produce readable
    pictures: the product's colour comes from my brief, the BACKGROUND is chosen to contrast with it." Every concept
    prompt is told the backdrop in words, and the concept's palette is read off the product, never its backdrop."""

    @staticmethod
    def _picture(tmp, ground, product, border=None):
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (400, 600), ground)
        draw = ImageDraw.Draw(img)
        draw.rectangle((130, 90, 270, 520), fill=product)
        draw.rectangle((160, 250, 240, 300), fill=(213, 91, 100))
        if border:
            for x in range(0, 400, 8):
                draw.rectangle((x, 0, x + 3, 600), fill=border)
            draw.rectangle((40, 40, 360, 560), fill=ground)
            draw.rectangle((130, 90, 270, 520), fill=product)
        path = f"{tmp}/picture.png"
        img.save(path)
        return path

    def test_every_concept_prompt_is_told_a_backdrop_that_contrasts_with_the_product(self):
        from apps.pipeline.services import container_gate1 as cg1
        text = " ".join(cg1.CONTAINER_SYSTEM.split())
        self.assertIn("THE PICTURE IS READ, NOT ONLY SEEN.", text)
        self.assertIn("a light product (pastel, pink, cream or white) on a deep charcoal-grey backdrop", text)
        self.assertIn("Never a backdrop in the product's own colour family", text)
        self.assertIn("Write the backdrop into every prompt in those words.", text)

    def test_a_pink_tube_on_charcoal_is_read_by_its_pink_never_its_backdrop(self):
        import tempfile
        from apps.pipeline.services.image_checks import palette_distance
        brand = ["#F0CED2", "#D55B64"]
        with tempfile.TemporaryDirectory() as tmp:
            on_charcoal = palette_distance(self._picture(tmp, (47, 45, 44), (240, 206, 210)), brand)
        self.assertTrue(on_charcoal["backdrop_left_out"])
        self.assertTrue(on_charcoal["on_brand"], on_charcoal)
        self.assertGreater(on_charcoal["coverage"], 0.9)
        self.assertTrue(on_charcoal["note"].endswith(" — its plain backdrop left out"), on_charcoal["note"])

    def test_a_border_that_is_not_plain_leaves_the_palette_as_it_was(self):
        import tempfile
        from apps.pipeline.services.image_checks import palette_distance
        with tempfile.TemporaryDirectory() as tmp:
            striped = palette_distance(self._picture(tmp, (47, 45, 44), (240, 206, 210), border=(250, 250, 250)),
                                       ["#F0CED2", "#D55B64"])
        self.assertFalse(striped["backdrop_left_out"])
        self.assertFalse(striped["on_brand"], striped)

    def test_a_picture_that_is_nearly_all_backdrop_keeps_its_whole_palette(self):
        import tempfile
        from PIL import Image, ImageDraw
        from apps.pipeline.services.image_checks import palette_distance
        with tempfile.TemporaryDirectory() as tmp:
            img = Image.new("RGB", (400, 600), (47, 45, 44))
            ImageDraw.Draw(img).rectangle((190, 280, 210, 320), fill=(240, 206, 210))
            img.save(f"{tmp}/speck.png")
            speck = palette_distance(f"{tmp}/speck.png", ["#F0CED2"])
        self.assertFalse(speck["backdrop_left_out"])
        self.assertFalse(speck["on_brand"], speck)
