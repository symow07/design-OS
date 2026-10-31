"""Retry safety after a distinctness failure (Phase 2A-6C §6).

A failed direction-planning run drops its partial brief (fail-closed), so a
retry re-plans from scratch: one clean set of exactly three directions,
paused at awaiting_direction_selection, with no Prompt Engineer or image
call and no duplicate direction records.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.core.models import Brand, Product
from apps.pipeline.agents.aria import ARIAAgent
from apps.pipeline.models import CreativeBrief, DesignTask, GeneratedImage

from .direction_fixtures import valid_document
from .test_phase2a4 import _drawing_recorded


def _claude(payload):
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)
    response = MagicMock()
    response.content = [block]
    return response


@override_settings(ANTHROPIC_API_KEY="test-key", OPENAI_API_KEY="test-key")
class RetryAfterDistinctnessFailureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("t2a6c", "t@t.com", "pw")
        self.brand = Brand.objects.create(name="BBROSE", master_brief="brief")
        self.product = Product.objects.create(
            brand=self.brand, product_id="P-BP", name="Baked Powder",
            category="CO", year=2026)
        # A task that already failed direction planning: fail-closed, so NO
        # brief exists (task #49's real post-failure state).
        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product,
            task_text="Baked Powder carton concept", status="failed",
            error_message="Direction planning failed validation: "
                          "TYPOGRAPHY_NOT_DISTINCT",
            created_by=self.user)

    @patch("apps.pipeline.agents.image_producer.openai.images.generate")
    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    @patch("apps.pipeline.agents.creative_director.call_claude")
    def test_retry_replans_one_clean_set_and_pauses(
            self, mock_cd, mock_pe, mock_img):
        mock_cd.return_value = _claude(valid_document())
        # retry of a failed task == a fresh pipeline run
        # [his final goal, 2026-10-05, B4, re-pinned: "NO PROMPT STEP"] the clean plan goes straight to its drawing
        drawn = []
        with patch.object(ARIAAgent, "_render_each_direction", _drawing_recorded(drawn)):
            ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()

        self.assertEqual(drawn, [None])
        self.assertEqual(self.task.status, "awaiting_gate_1")
        briefs = CreativeBrief.objects.filter(task=self.task)
        self.assertEqual(briefs.count(), 1)                 # no duplicate brief
        self.assertEqual(len(briefs.first().directions), 3)  # exactly three
        self.assertFalse(briefs.first().selected_direction_id)
        mock_pe.assert_not_called()                          # no Prompt Engineer
        mock_img.assert_not_called()                         # no image generation
        self.assertEqual(GeneratedImage.objects.filter(task=self.task).count(), 0)

    @patch("apps.pipeline.agents.image_producer.openai.images.generate")
    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    @patch("apps.pipeline.agents.creative_director.call_claude")
    def test_second_retry_does_not_accumulate_direction_sets(
            self, mock_cd, mock_pe, mock_img):
        mock_cd.return_value = _claude(valid_document())
        # [his final goal, B4, re-pinned] a second run draws the same plan again; it never adds a set
        drawn = []
        with patch.object(ARIAAgent, "_render_each_direction", _drawing_recorded(drawn)):
            ARIAAgent(self.task.id).run()
            ARIAAgent(self.task.id).run()
        self.assertEqual(
            CreativeBrief.objects.filter(task=self.task).count(), 1)
        self.task.refresh_from_db()
        self.assertEqual((drawn, self.task.status), ([None, None], "awaiting_gate_1"))
        mock_img.assert_not_called()
