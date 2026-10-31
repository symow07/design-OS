"""M4C-9 §8 — the drawn half of the variant proof.

The measured-difference and produced-evidence tests that lived here
covered the §8 contract: nine differences, eight producible views and two
blocked on the unbuilt lid. M4B-B built the lid, so all ten views exist,
the lid/base relationship joined the measured set and the compared views
share one frame across both families.

That coverage now lives in ``test_m4b_b_evidence.py``. What remains here
is the part §9 did not replace: the drawn comparisons, which are produced
from geometry rather than rendered.
"""
import os
from pathlib import Path

from django.test import SimpleTestCase

from apps.pipeline.services import palette_variant_visual_proof as VP

REPO = Path(__file__).resolve().parents[3]
EVIDENCE = str(REPO / "docs" / "roadmap" / "palt_m4b_b" / "bridge")


class DrawnComparisonTests(SimpleTestCase):
    """The four views drawn from geometry, not rendered."""

    DRAWN = ("silhouette_comparison", "layout_graph_comparison",
             "artwork_zone_comparison", "colour_zone_diagram")

    def test_the_drawn_views_are_not_sourced_from_a_render(self):
        for key in self.DRAWN:
            self.assertNotIn(key, VP.FROM_REVIEW)

    def test_the_rendered_views_are_sourced_from_the_review_set(self):
        rendered = [k for k, _m, how in VP.REQUIRED_VIEWS if how == "PAIR"]
        self.assertEqual(len(rendered), 6)
        for key in rendered:
            self.assertIn(key, VP.FROM_REVIEW)

    def test_no_view_is_blocked_any_more(self):
        """Both families have a lid, so nothing is deferred."""
        self.assertEqual(
            [k for k, _m, how in VP.REQUIRED_VIEWS if how == VP.BLOCKED],
            [])

    def test_all_ten_required_views_are_declared(self):
        self.assertEqual(len(VP.REQUIRED_VIEWS), 10)
        self.assertEqual(len({v[0] for v in VP.REQUIRED_VIEWS}), 10)

    def test_the_produced_set_is_complete(self):
        self.assertTrue(os.path.isdir(EVIDENCE), EVIDENCE)
        for key, _means, _how in VP.REQUIRED_VIEWS:
            with self.subTest(view=key):
                self.assertTrue(
                    os.path.exists(os.path.join(EVIDENCE, f"{key}.png")),
                    f"{key}.png is missing from the bridge set")

    def test_eleven_differences_are_required(self):
        self.assertEqual(len(VP.REQUIRED_DIFFERENCES), 11)
        self.assertIn("lid / base relationship", VP.REQUIRED_DIFFERENCES)
