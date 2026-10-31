"""Defects found by the Phase 2A-6A controlled local activation smoke test.

Each test pins a failure that the automated suite did NOT catch and only a
live run exposed.
"""
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.core.models import Brand
from apps.dielines.models import DielineJob
from apps.pipeline.models import (
    DesignTask,
    GeneratedImage,
    PackagingOutput,
)
from apps.pipeline.permissions import ROLE_REVIEWER

SKYNTE = "skynte_foundation_tuck_carton"


def _reviewer(name):
    u = User.objects.create_user(name, f"{name}@t.com", "pw")
    g, _ = Group.objects.get_or_create(name=ROLE_REVIEWER)
    u.groups.add(g)
    return u


class DimensionGateForwardsStructuralFieldsTests(TestCase):
    """DEFECT A — the dimension gate built a fixed six-key dict, so an
    explicitly chosen template and the customer's supplied inner/outer
    dimension sets never reached ARIA. Selection could not see a user choice
    and reconciliation silently fell back to model-derived values.

    [The clean-up of 2026-10-04, his Q1 "remove the dormant packaging flow":
    the gate still forwards them, and nothing past it selects or reconciles a
    structure any more — the forwarding is kept for his word.]"""

    def setUp(self):
        self.reviewer = _reviewer("rev-defect-a")
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
        self.client.force_login(self.reviewer)

    def _post(self, extra):
        body = {"dimensions": {
            "width_mm": 42.0, "depth_mm": 32.0, "height_mm": 140.0,
            "bleed_mm": 3.0, "safe_margin_mm": 4.0, "glue_tab_mm": 10.0,
            "board_thickness_mm": 0.30, "thickness_compensation": True,
            **extra}}
        return self.client.post(
            f"/api/tasks/{self.task.id}/confirm_dimensions/",
            data=json.dumps(body), content_type="application/json")

    @patch("apps.pipeline.tasks.resume_aria_dimensions.delay")
    def test_template_and_dimension_sets_reach_aria(self, mock_delay):
        res = self._post({"template": SKYNTE,
                          "inner_mm": [41.4, 31.4, 138.9],
                          "outer_mm": [42.4, 32.4, 140.9]})
        self.assertEqual(res.status_code, 200)
        confirmed = mock_delay.call_args[0][2]
        self.assertEqual(confirmed["template"], SKYNTE)
        self.assertEqual(confirmed["inner_mm"], [41.4, 31.4, 138.9])
        self.assertEqual(confirmed["outer_mm"], [42.4, 32.4, 140.9])

    @patch("apps.pipeline.tasks.resume_aria_dimensions.delay")
    def test_generic_acceptance_is_forwarded(self, mock_delay):
        self._post({"generic_accepted": True})
        self.assertTrue(mock_delay.call_args[0][2]["generic_accepted"])

    @patch("apps.pipeline.tasks.resume_aria_dimensions.delay")
    def test_absent_structural_fields_stay_absent(self, mock_delay):
        self._post({})
        confirmed = mock_delay.call_args[0][2]
        for key in ("template", "inner_mm", "outer_mm", "generic_accepted"):
            self.assertNotIn(key, confirmed)

    def test_malformed_dimension_set_is_rejected(self):
        res = self._post({"inner_mm": [41.4, 31.4]})      # only two values
        self.assertEqual(res.status_code, 400)

    def test_dimensions_are_validated_against_the_chosen_template(self):
        """A per-template structural rule must be applied to the template the
        user actually picked, not always to generic STE."""
        res = self._post({"template": SKYNTE, "height_mm": 20.0})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "Invalid dimensions")


class VerifiedPrintDataIsNeverDestroyedTests(TestCase):
    """DEFECT B — regeneration rebuilt panel_info from Product/Brand defaults
    and overwrote the stored record. For a task with no Product row that
    silently destroyed confirmed regulatory copy.

    [The clean-up of 2026-10-04, his Q1 "remove the dormant packaging flow":
    the three tests that re-ran the structure step's artwork left with it,
    with the confirmed structure they were set up on; the integrity contract
    stays pinned.]"""

    VERIFIED = {
        "product_name": "Skynte Foundation",
        "description": "A lightweight liquid foundation.",
        "ingredients": "AQUA, GLYCERIN, TITANIUM DIOXIDE",
        "how_to_use": "Shake well before use.",
        "warnings": "For external use only.",
        "net_weight": "30 ml / 1.0 fl. oz.",
        "item_no": "SKYNTE-FND-01",
        "barcode_ean": "5061030633823",
        "regulatory_text": "MADE IN CHINA BY SUPPLIER: YIWU YIBIN.",
    }

    def test_guard_stops_a_run_that_would_lose_fields(self):
        """If anything upstream drops a verified field, the integrity check
        halts the run with a precise code instead of writing the loss.

        Asserted against the comparison contract directly — patching ARIA's
        internals to simulate the loss leaked a mock into later tests.
        """
        from apps.pipeline.services import print_data_snapshot as snap
        before = snap.snapshot_from_panel_info(1, dict(self.VERIFIED))
        lossy = {k: v for k, v in self.VERIFIED.items()
                 if k not in ("ingredients", "warnings")}
        after = snap.snapshot_from_panel_info(1, lossy)
        comparison = snap.compare_snapshots(before, after)
        self.assertFalse(comparison.passed)
        self.assertIn(snap.VERIFIED_PRINT_DATA_WOULD_BE_LOST,
                      comparison.codes())
        self.assertIn(snap.PRINT_DATA_FIELD_DROPPED, comparison.codes())
        self.assertEqual(sorted(comparison.changed_fields),
                         ["ingredients", "warnings"])
