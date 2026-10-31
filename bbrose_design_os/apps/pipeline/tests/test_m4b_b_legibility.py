"""M4B-B-EVIDENCE-LEGIBILITY — the render contract and its regressions.

§5 camera/file identity, §6 articulation, §7 lid cavity orientation, and
the legibility bars themselves, each with a control that can fail.
"""
import json
from collections import Counter
from pathlib import Path

import numpy as np
from django.test import SimpleTestCase
from PIL import Image

from apps.pipeline.services import palette_es3083_owner_confirmation as OC
from apps.pipeline.services import palette_m4b_b_evidence as EVB
from apps.pipeline.services import palette_m4b_b_gate as G
from apps.pipeline.services import palette_moulded_geometry as MG
from apps.pipeline.services import palette_moulded_rect as MR
from apps.pipeline.services import palette_render_contract as RC

REPO = Path(__file__).resolve().parents[3]
DOCS = REPO / "docs" / "roadmap" / "palt_m4b_b"


class RenderContractTests(SimpleTestCase):
    def test_the_thresholds_were_predeclared_and_are_unchanged(self):
        self.assertTrue(RC.CONTRACT["thresholds_predeclared"])
        self.assertEqual(RC.MINIMUM_MODAL_BACKGROUND_SUBJECT_COVERAGE, 0.05)
        self.assertEqual(RC.MINIMUM_LUMINANCE_CONTRAST, 40.0)

    def test_the_backdrop_contrasts_with_the_clay(self):
        """The failure was a 0.42 clay on a 0.55 backdrop."""
        clay = sum(RC.CONTRACT["clay_albedo"]) / 3
        backdrop = sum(RC.CONTRACT["backdrop_colour"]) / 3
        self.assertLess(backdrop, clay * 0.5)

    def test_it_stays_technical_not_presentational(self):
        c = RC.CONTRACT
        self.assertEqual(c["purpose"],
                         "TECHNICAL_FORM_LEGIBILITY_NOT_CLIENT_"
                         "PRESENTATION_BEAUTY")
        for banned in ("beauty_colour", "cosmetic_artwork",
                       "material_styling", "dramatic_lighting",
                       "depth_of_field", "edge_enhancement",
                       "silhouette_altering_post"):
            self.assertFalse(c[banned], banned)
        self.assertEqual(c["post_processing"], "NONE")

    def test_it_cannot_change_geometry(self):
        self.assertFalse(RC.record()["changes_geometry"])

    def test_it_is_versioned_and_identified(self):
        self.assertEqual(len(RC.contract_identity()), 16)
        self.assertEqual(RC.contract_identity(), RC.contract_identity())

    def test_every_field_the_directive_names_is_pinned(self):
        c = RC.CONTRACT
        for key in ("clay_albedo", "backdrop_colour", "key_light",
                    "fill_light", "rim_light", "exposure", "camera_mode",
                    "resolution", "view_transform", "seed",
                    "contact_shading", "minimum_luminance_contrast"):
            self.assertIn(key, c)

    def test_the_four_frame_rules_are_declared(self):
        for rule in ("CLOSED_STATE_FRAME", "OPEN_STATE_FRAME",
                     "DETAIL_FRAME", "PAN_LAYOUT_FRAME"):
            self.assertIn(rule, RC.FRAME_RULES)


class LegibilityMeasureTests(SimpleTestCase):
    def _png(self, subject_fraction, subject_lum, bg_lum=14):
        arr = np.full((400, 400, 3), bg_lum, np.uint8)
        n = int(400 * 400 * subject_fraction)
        side = max(1, int(np.sqrt(n)))
        arr[:side, :side] = subject_lum
        import shutil
        import tempfile
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        p = str(Path(folder) / "subject.png")
        Image.fromarray(arr).save(p)
        return p

    def test_it_measures_a_legible_render(self):
        cov, con = G.subject_separation(self._png(0.30, 190))
        self.assertGreater(cov, 0.05)
        self.assertGreater(con, 40)

    def test_a_subject_that_is_too_small_fails(self):
        """The negative control for coverage."""
        cov, _con = G.subject_separation(self._png(0.01, 190))
        self.assertLessEqual(cov,
                             RC.MINIMUM_MODAL_BACKGROUND_SUBJECT_COVERAGE)

    def test_a_subject_that_blends_into_the_backdrop_fails(self):
        """The negative control for contrast — the actual defect."""
        cov, con = G.subject_separation(self._png(0.30, 26))
        self.assertLess(con, RC.MINIMUM_LUMINANCE_CONTRAST)
        self.assertLess(cov, RC.CONTRAST_APPLIES_BELOW_COVERAGE)

    def test_the_backdrop_is_read_from_the_border_not_the_mode(self):
        """A subject filling the frame would otherwise be mistaken for the
        background, reporting a legible close-up as having no contrast."""
        cov, con = G.subject_separation(self._png(0.80, 200))
        self.assertGreater(cov, 0.5)
        self.assertGreater(con, 100)


class ProducedEvidenceIsLegibleTests(SimpleTestCase):
    def test_every_committed_render_clears_both_bars(self):
        recs = json.loads((DOCS / "review_records.json").read_text())
        for rec in recs:
            for key in rec["produced"]:
                if key == "dimension_overlay":
                    continue
                path = Path(rec["out_dir"]) / f"{key}.png"
                cov, con = G.subject_separation(str(path))
                with self.subTest(view=f"{rec['family']}/{key}"):
                    self.assertGreater(
                        cov, RC.MINIMUM_MODAL_BACKGROUND_SUBJECT_COVERAGE)
                    if cov < RC.CONTRAST_APPLIES_BELOW_COVERAGE:
                        self.assertGreaterEqual(
                            con, RC.MINIMUM_LUMINANCE_CONTRAST)


class ViewIdentityTests(SimpleTestCase):
    """§5 — camera and file identity."""

    def setUp(self):
        self.recs = json.loads((DOCS / "review_records.json").read_text())

    def test_every_entry_carries_the_required_identity_fields(self):
        for rec in self.recs:
            for e in rec["entries"]:
                for field in ("semantic_view_id", "camera_id", "state_id",
                              "output_filename"):
                    self.assertIn(field, e)
            self.assertIn("render_contract_identity", rec)

    def test_no_file_is_claimed_by_two_view_records(self):
        for rec in self.recs:
            names = [e["output_filename"] for e in rec["entries"]]
            dupes = [n for n, c in Counter(names).items() if c > 1]
            self.assertEqual(dupes, [], f"{rec['family']}: {dupes}")

    def test_no_two_semantic_views_resolve_to_one_camera_in_a_state(self):
        for state in {v[1] for v in EVB.REVIEW_VIEWS}:
            cams = [v[2] for v in EVB.REVIEW_VIEWS if v[1] == state]
            self.assertEqual(
                [c for c, n in Counter(cams).items() if n > 1], [])

    def test_the_recorded_state_matches_the_view_definition(self):
        by_view = {v[0]: (v[1], v[2]) for v in EVB.REVIEW_VIEWS}
        for rec in self.recs:
            for e in rec["entries"]:
                if e["semantic_view_id"] == "dimension_overlay":
                    continue
                state, cam = by_view[e["semantic_view_id"]]
                self.assertEqual(e["state_id"], state)
                self.assertEqual(e["camera_id"], cam)


class ArticulationRegressionTests(SimpleTestCase):
    """§6 — measured from transformed geometry, never from the input."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comps, cls.dims = MR.build_rect_components(
            OC.confirmed_intent())

    def _lid(self, state):
        return MR.compose_rect_state(
            self.comps, self.dims, state)["lid_outer_shell"]["vertices"]

    def test_the_lid_centroid_moves_behind_the_hinge_when_open(self):
        axis_y = self.dims["hinge_axis_y_mm"]
        closed = self._lid("CLOSED").mean(axis=0)
        opened = self._lid("OPEN_90").mean(axis=0)
        self.assertGreater(closed[1], axis_y)
        self.assertLess(opened[1], axis_y)

    def test_the_lid_does_not_cross_through_the_base(self):
        base = self.comps["base_outer_shell"]["vertices"]
        for state in ("OPEN_90", "OPEN_REVIEW_ANGLE"):
            lid = self._lid(state)
            with self.subTest(state=state):
                self.assertGreaterEqual(lid[:, 2].min(), -1e-6)
                self.assertGreater(lid[:, 2].max(),
                                   base[:, 2].max() + 20.0)

    def test_the_open_silhouette_differs_materially_from_closed(self):
        closed, opened = self._lid("CLOSED"), self._lid("OPEN_90")
        cs = closed.max(axis=0) - closed.min(axis=0)
        os_ = opened.max(axis=0) - opened.min(axis=0)
        self.assertGreater(abs(os_[2] - cs[2]), 20.0)

    def test_the_angle_is_measured_from_transformed_geometry(self):
        """Not read back from the rotation parameter."""
        import numpy as np
        axis_z = self.dims["hinge_axis_z_mm"]
        axis_y = self.dims["hinge_axis_y_mm"]
        closed = self._lid("CLOSED").mean(axis=0)
        opened = self._lid("OPEN_90").mean(axis=0)
        v0 = np.array([closed[1] - axis_y, closed[2] - axis_z])
        v1 = np.array([opened[1] - axis_y, opened[2] - axis_z])
        cos = float(v0 @ v1 / (np.linalg.norm(v0) * np.linalg.norm(v1)))
        self.assertAlmostEqual(np.degrees(np.arccos(cos)), 90.0, delta=2.0)


class LidCavityOrientationTests(SimpleTestCase):
    """§7 — a lid is not a shallow tray with reversed orientation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comps, cls.dims = MR.build_rect_components(
            OC.confirmed_intent())

    def test_the_cavity_opens_toward_the_palette_interior(self):
        v = self.comps["lid_outer_shell"]["vertices"]
        lo, hi = v[:, 2].min(), v[:, 2].max()
        bottom = v[np.abs(v[:, 2] - (lo + 0.2)) < 0.35]
        top = v[np.abs(v[:, 2] - (hi - 0.2)) < 0.35]
        self.assertGreater(len(bottom), len(top))

    def test_the_lid_sits_above_the_base_when_closed(self):
        lid = self.comps["lid_outer_shell"]["vertices"]
        base = self.comps["base_outer_shell"]["vertices"]
        self.assertGreaterEqual(lid[:, 2].min(), base[:, 2].max() - 1e-6)

    def test_the_cavity_faces_the_tray_when_open(self):
        opened = MR.compose_rect_state(self.comps, self.dims, "OPEN_90")
        lid = opened["lid_outer_shell"]["vertices"]
        tray = self.comps["moulded_tray"]["vertices"]
        self.assertLess(lid[:, 1].max(), tray[:, 1].min())

    def test_p1a_is_unaffected_by_the_p1b_correction(self):
        comps, _ = MG.build_moulded_components()
        self.assertIn("lid_outer_shell", comps)
