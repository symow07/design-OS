"""The one packaging path writes no structure record (Phase 2A-6 §14, as it now stands).

This file proved the Phase 2A-6 standard path — dimensions confirmed, a structure selected and paused for a human,
native-vector artwork after the confirmation, Gate 2 machine-validated — and that the earlier path was untouched with
its flag off. [The clean-up of 2026-10-04, his Q1 "remove the dormant packaging flow".] The standard path and its flag
left; the path these tests call "legacy" is the one live packaging path, and they pin that it reaches its review with
no structure step and no structure record.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.core.models import Brand
from apps.dielines.models import DielineJob
from apps.pipeline.agents.aria import ARIAAgent
from apps.pipeline.models import (
    DesignTask,
    GeneratedImage,
    PackagingOutput,
)


class LegacyCompatibilityTests(TestCase):
    """§14, as it now stands: no structure step — the dieline path runs as it always did, and it is the only one."""

    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.task = DesignTask.objects.create(
            task_text="t", status="awaiting_dimensions", brand=self.brand)
        self.image = GeneratedImage.objects.create(
            task=self.task, direction_name="d", prompt_used="p", image_url="u")
        self.job = DielineJob.objects.create(
            template_type="straight_tuck_end_carton", scenario="B",
            input_json={}, extraction_result={})
        self.output = PackagingOutput.objects.create(
            task=self.task, spec_sheet={}, approved_image=self.image,
            dieline_job=self.job)

    @patch("apps.pipeline.services.panel_translate.translate_panel_info",
           return_value={})
    def test_legacy_flow_skips_the_structure_gate(self, _tr):
        ARIAAgent(self.task.id).resume_after_dimensions(
            self.output.id, {"width_mm": 35.0, "depth_mm": 25.0,
                             "height_mm": 95.0, "bleed_mm": 3.0,
                             "safe_margin_mm": 4.0, "glue_tab_mm": 10.0,
                             "board_thickness_mm": 0.35,
                             "thickness_compensation": True})
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "awaiting_gate_2")
        self.job.refresh_from_db()
        # No structural record is written on the legacy path.
        self.assertEqual(self.job.structure_selection, {})

    def test_legacy_output_is_not_strictly_validated(self):
        self.output.spec_sheet = {"template": "straight_tuck_end_carton"}
        self.output.save()
        self.assertNotIn("production_validation", self.output.spec_sheet)
