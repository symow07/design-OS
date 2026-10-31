"""Local activation smoke tests (Phase 2A-6A §5–§7).

A bounded diagnostic job — never a real external design task, never a
reusable production asset. No Creative Director, no DIP search, no Prompt
Engineer, no image generation, no external provider call.

[The clean-up of 2026-10-04, his Q1 "remove the dormant packaging flow": the
structural + vector run that drove the structure-confirmation flow left with
it. What stays is the STE 1.1 and reverse-tuck geometry, measured on the
engine alone.]
"""
from __future__ import annotations

from django.test import TestCase

from apps.dielines import registry
from apps.dielines.exporters.structural_comparison import geometry_integrity
from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.validators.schema import DielineInputJSON

STE = "straight_tuck_end_carton"
RTE = "reverse_tuck_end_carton"


class StraightTuck11SmokeTests(TestCase):
    """§5 — STE 1.1's die, measured on the engine alone: no cut/fold conflict and valid boundaries. [The clean-up of
    2026-10-04: the bounded structural + vector smoke run that also lived here drove the structure-confirmation flow
    and left with it; this check never touched that flow.]"""

    DIMS = {"width_mm": 42.0, "depth_mm": 32.0, "height_mm": 140.0,
            "bleed_mm": 3.0, "safe_margin_mm": 4.0, "glue_tab_mm": 10.0,
            "board_thickness_mm": 0.30, "thickness_compensation": True,
            "template": STE, "template_version": "1.1"}

    def test_zero_cut_fold_conflict_and_valid_boundaries(self):
        coords = calculate_dieline(DielineInputJSON(
            template=STE, unit="mm", template_version="1.1",
            dimensions={k: self.DIMS[k] for k in
                        ("width_mm", "depth_mm", "height_mm")},
            print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
            construction={"glue_tab_mm": 10.0, "board_thickness_mm": 0.30,
                          "thickness_compensation": True},
            metadata={"product_name": "d", "product_type": "d"}))
        integrity = geometry_integrity(coords)
        self.assertFalse(integrity["cut_fold_conflict"])
        self.assertFalse(integrity["self_intersecting"])
        self.assertFalse(integrity["open_contour"])
        # hinges survive, slits stay cut
        self.assertGreaterEqual(len(coords.fold_lines), 10)
        self.assertEqual(len(coords.stadium_cutouts), 2)
        self.assertTrue(coords.bleed_polygon.area > coords.cut_polygon.area
                        > coords.safe_polygon.area)


class ReverseTuckRegressionTests(TestCase):
    """§6 — automated reverse-tuck validation. No external provider call."""

    def _coords(self, version="1.1"):
        return calculate_dieline(DielineInputJSON(
            template=RTE, unit="mm", template_version=version,
            dimensions={"width_mm": 42.0, "depth_mm": 32.0,
                        "height_mm": 140.0},
            print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
            construction={"glue_tab_mm": 10.0, "board_thickness_mm": 0.30,
                          "thickness_compensation": True},
            metadata={"product_name": "d", "product_type": "d"}))

    def test_opposing_tuck_orientation(self):
        rte = self._coords().derived
        ste = calculate_dieline(DielineInputJSON(
            template=STE, unit="mm", template_version="1.1",
            dimensions={"width_mm": 42.0, "depth_mm": 32.0,
                        "height_mm": 140.0},
            print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
            construction={"glue_tab_mm": 10.0, "board_thickness_mm": 0.30,
                          "thickness_compensation": True},
            metadata={"product_name": "d", "product_type": "d"})).derived
        self.assertEqual(rte["top_tuck_panel"], "front")
        self.assertEqual(rte["bottom_tuck_panel"], "back")
        self.assertNotEqual(rte["top_tuck_panel"], ste["top_tuck_panel"])

    def test_panel_roles_match_the_registry(self):
        coords = self._coords()
        self.assertEqual([p.name for p in coords.panels],
                         registry.resolve(RTE, "1.1").panel_order())

    def test_zero_cut_fold_conflict(self):
        integrity = geometry_integrity(self._coords())
        self.assertFalse(integrity["cut_fold_conflict"])
        self.assertEqual(integrity["cut_fold_conflict_segments"], [])

    def test_no_mirrored_slit_error(self):
        coords = self._coords()
        self.assertEqual([s[0] for s in coords.stadium_cutouts],
                         ["top-front-slit", "bottom-back-slit"])
        # each slit sits inside its own tuck column
        d = coords.derived
        top = next(s for s in coords.stadium_cutouts if s[0].startswith("top"))
        self.assertGreater(top[1], d["x3"])
        self.assertLess(top[1], d["x4"])

    def test_production_ready_registry_state(self):
        defn = registry.resolve(RTE, "1.1")
        self.assertTrue(defn.production_ready)
        self.assertEqual(defn.structure_status, registry.STRUCTURE_MEASURED)
        self.assertIn(defn.key, {d.key for d in registry.production_templates()})

    def test_no_generic_1_0_fallback(self):
        """An unpinned caller must get 1.1, never the defective 1.0."""
        self.assertEqual(registry.current_version(RTE), "1.1")
        unpinned = calculate_dieline(DielineInputJSON(
            template=RTE, unit="mm",
            dimensions={"width_mm": 42.0, "depth_mm": 32.0,
                        "height_mm": 140.0},
            print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
            construction={"glue_tab_mm": 10.0, "board_thickness_mm": 0.30,
                          "thickness_compensation": True},
            metadata={"product_name": "d", "product_type": "d"}))
        self.assertEqual(unpinned.fold_lines, self._coords().fold_lines)
