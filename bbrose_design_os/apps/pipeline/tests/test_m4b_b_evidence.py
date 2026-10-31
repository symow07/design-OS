"""M4B-B §9/§10 — neutral review evidence and the ten-view bridge proof."""
import json
from collections import Counter
from pathlib import Path

import numpy as np
from django.test import SimpleTestCase
from PIL import Image

from apps.pipeline.services import palette_design_graph as dg
from apps.pipeline.services import palette_es3083_owner_confirmation as OC
from apps.pipeline.services import palette_m4b_b_evidence as EVB
from apps.pipeline.services import palette_moulded_geometry as MG
from apps.pipeline.services import palette_moulded_rect as MR
from apps.pipeline.services import palette_rect_tray_geometry as rt
from apps.pipeline.services import palette_variant_visual_proof as VP

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "docs" / "roadmap" / "palt_m4b_b"

#: An image is reviewable when its subject occupies at least a twentieth
#: of the frame. Fixed a priori: an elevation of a flat palette is
#: legitimately low-variance, so variance is the wrong measure, and a
#: threshold chosen after looking at the results would prove nothing.
MIN_SUBJECT_FRACTION = 0.05

#: CLOSED by M4B-B-EVIDENCE-LEGIBILITY. The six views that failed the
#: grey-on-grey defect now clear both predeclared bars; the fix was a
#: contrasting backdrop, a stronger rim and per-camera framing, not a
#: softer threshold.


def _subject_fraction(arr):
    """How much of the frame differs from the backdrop.

    The backdrop is read from the border ring, which is backdrop by
    construction in an orthographic technical render.
    """
    lum = arr.astype(int).mean(axis=2).round().astype(int)
    h, w = lum.shape
    band = max(2, int(min(h, w) * 0.05))
    border = np.concatenate([lum[:band].ravel(), lum[-band:].ravel(),
                             lum[:, :band].ravel(), lum[:, -band:].ravel()])
    bg = int(np.bincount(border, minlength=256).argmax())
    return float((np.abs(lum - bg) > 8).mean())


class ViewContractTests(SimpleTestCase):
    def test_no_two_views_in_one_state_share_a_camera(self):
        """The render dict is keyed by camera, so a collision writes one
        file while the record claims both."""
        for state in {v[1] for v in EVB.REVIEW_VIEWS}:
            cams = [v[2] for v in EVB.REVIEW_VIEWS if v[1] == state]
            dupes = [c for c, n in Counter(cams).items() if n > 1]
            with self.subTest(state=state):
                self.assertEqual(dupes, [], f"{state}: {dupes}")

    def test_every_view_name_is_unique(self):
        names = [v[0] for v in EVB.REVIEW_VIEWS]
        self.assertEqual(len(set(names)), len(names))

    def test_the_required_set_covers_the_directive(self):
        for key in ("closed_top", "closed_front", "closed_side",
                    "closed_three_quarter", "open_top", "open_front",
                    "open_side", "open_three_quarter", "pan_layout",
                    "recessed_pocket_detail", "hinge_exterior",
                    "hinge_interior", "hinge_exploded", "clasp_exterior",
                    "clasp_interior", "clasp_exploded", "lid_interior",
                    "mirror_stack_view", "exploded_palette",
                    "hinge_section", "clasp_section",
                    "true_stack_section", "dimension_overlay"):
            self.assertIn(key, EVB.REQUIRED)
        self.assertEqual(len(EVB.REQUIRED), 23)

    def test_the_pan_field_view_removes_the_lid(self):
        """'the pan field alone' means alone — an edge-on lid reads as a
        render artefact."""
        self.assertIn("TRAY_ONLY", EVB.HIDE)
        for prefix in ("lid_", "hinge_", "clasp_"):
            self.assertIn(prefix, EVB.HIDE["TRAY_ONLY"])
        state = next(v[1] for v in EVB.REVIEW_VIEWS
                     if v[0] == "pan_layout")
        self.assertEqual(state, "TRAY_ONLY")


class ProducedReviewTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        path = OUT / "review_records.json"
        cls.records = json.loads(path.read_text()) if path.exists() else []

    def setUp(self):
        if not self.records:
            self.skipTest("review renders not present")

    def test_both_families_were_rendered(self):
        self.assertEqual({r["family"] for r in self.records},
                         {"P1A", "P1B"})

    def test_p1b_skips_only_the_mirror_view_and_says_why(self):
        rec = next(r for r in self.records if r["family"] == "P1B")
        self.assertEqual([s["view"] for s in rec["skipped"]],
                         ["mirror_stack_view"])
        self.assertIn("no mirror", rec["skipped"][0]["why"])

    def test_p1a_renders_the_mirror_view(self):
        rec = next(r for r in self.records if r["family"] == "P1A")
        self.assertIn("mirror_stack_view", rec["produced"])

    def test_every_recorded_file_exists_and_is_not_white_on_white(self):
        for rec in self.records:
            for key in rec["produced"]:
                path = Path(rec["out_dir"]) / f"{key}.png"
                with self.subTest(view=f"{rec['family']}/{key}"):
                    self.assertTrue(path.exists(), str(path))
                    arr = np.asarray(Image.open(path).convert("RGB"))
                    self.assertLess(float(arr.mean()), 245.0,
                                    "white-on-white is not evidence")
                    if key in ("dimension_overlay",):
                        continue          # a line drawing, not a render
                    self.assertGreater(_subject_fraction(arr),
                                       MIN_SUBJECT_FRACTION)

    def test_both_families_used_one_renderer(self):
        renderers = {r["renderer"] for r in self.records}
        self.assertEqual(len(renderers), 1)

    def test_the_compared_views_share_one_frame_across_families(self):
        """Two images at different scales captioned as an identical-camera
        comparison would misstate how much the design changed."""
        frames = [r["shared_frames"] for r in self.records]
        self.assertEqual(frames[0], frames[1])
        self.assertTrue(frames[0])

    def test_only_the_compared_views_share_a_frame(self):
        """Framing an elevation to the open-assembly frame renders it as a
        sliver."""
        self.assertEqual(len(EVB.COMPARED_VIEWS), 6)
        for key in ("closed_front", "closed_side", "open_front",
                    "open_side", "hinge_interior"):
            self.assertNotIn(key, EVB.COMPARED_VIEWS)


class BridgeProofTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.graph = dg.build_palette_design_graph(
            OC.confirmed_intent(), rt.build_rect_recessed_tray())
        _ca, cls.da = MG.build_moulded_components()
        _cb, cls.db = MR.build_rect_components(OC.confirmed_intent())
        cls.a, cls.b = VP._variants()

    def test_the_two_previously_blocked_views_are_no_longer_blocked(self):
        blocked = [k for k, _m, how in VP.REQUIRED_VIEWS
                   if how == VP.BLOCKED]
        self.assertEqual(blocked, [])
        for key in ("closed_top", "closed_three_quarter"):
            self.assertIn(key, VP.FROM_REVIEW)

    def test_all_eleven_differences_are_measured(self):
        diffs = VP.measured_differences(
            self.a, self.b, graph_a=None, graph_b=self.graph,
            assembly_a=self.da, assembly_b=self.db)
        self.assertEqual(len(diffs), len(VP.REQUIRED_DIFFERENCES))
        self.assertEqual({d["difference"] for d in diffs},
                         set(VP.REQUIRED_DIFFERENCES))
        self.assertEqual([d["difference"] for d in diffs
                          if not d["visible"]], [])

    def test_the_lid_base_relationship_is_now_comparable(self):
        diffs = {d["difference"]: d for d in VP.measured_differences(
            self.a, self.b, graph_a=None, graph_b=self.graph,
            assembly_a=self.da, assembly_b=self.db)}
        row = diffs["lid / base relationship"]
        self.assertFalse(row["excluded_from_verdict"])
        self.assertTrue(row["visible"])

    def test_it_is_excluded_when_an_assembly_is_missing(self):
        """Honest: without both lids there is nothing to compare."""
        diffs = {d["difference"]: d for d in VP.measured_differences(
            self.a, self.b, graph_a=None, graph_b=self.graph)}
        self.assertTrue(
            diffs["lid / base relationship"]["excluded_from_verdict"])

    def test_comparing_a_variant_with_itself_finds_nothing(self):
        same = VP.measured_differences(
            self.a, self.a, graph_a=self.graph, graph_b=self.graph,
            assembly_a=self.da, assembly_b=self.da)
        self.assertEqual([d["visible"] for d in same],
                         [False] * len(VP.REQUIRED_DIFFERENCES))

    def test_the_verdict_requires_every_view_to_exist(self):
        # the record is committed, so absence is a failure not a skip
        rec = OUT / "m4c9_visual_variant_proof_full.json"
        self.assertTrue(rec.exists(), str(rec))
        data = json.loads(rec.read_text())
        self.assertTrue(data["all_required_views_exist"])
        self.assertEqual(data["produced_count"], 10)
        self.assertEqual(data["DESIGN_INTENT_BRIDGE"], "PASS")
        self.assertEqual(data["differences_not_visible"], [])
