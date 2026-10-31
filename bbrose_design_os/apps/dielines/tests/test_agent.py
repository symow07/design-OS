"""Offline tests for the deterministic dieline core (no DB, no API keys).

These exercise the geometry engine and the three exporters that the dielines
app owns — SVG, the new CMYK production PDF, and the schema guards. The
DielineAgent's orchestration (run/generate against the DB) is covered in
apps.pipeline.tests.test_full_pipeline.

Everything here is pure-function: build a DielineInputJSON, run the engine,
export. The exporters take an explicit absolute ``output_dir`` (Milestone
10.1 — no CWD dependence), so each test passes its own temp directory.
"""
from __future__ import annotations

import os
import shutil
import tempfile

from django.test import SimpleTestCase

from apps.dielines.exporters.counter_display_files import write_carton_pdf
from apps.dielines.exporters.counter_display_files import write_carton_svg
from apps.dielines.exporters.svg_validator import validate_svg
from apps.dielines.geometry.engine import calculate_straight_tuck_end
from apps.dielines.validators.schema import DielineInputJSON


def _params(width=35.0, depth=30.0, height=100.0, glue=10.0, bleed=3.0, safe=4.0):
    return DielineInputJSON(
        template="straight_tuck_end_carton",
        unit="mm",
        dimensions={"width_mm": width, "depth_mm": depth, "height_mm": height},
        print_settings={"bleed_mm": bleed, "safe_margin_mm": safe},
        construction={"glue_tab_mm": glue},
        metadata={"product_name": "Test Carton", "product_type": "carton", "notes": ""},
    )


class _InTempDir(SimpleTestCase):
    """Base: give each test a throwaway export dir (passed as output_dir)."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="dieline_test_")

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)


class GeometryEngineTest(_InTempDir):
    def test_engine_produces_valid_coordinates(self):
        coords = calculate_straight_tuck_end(_params())
        # flat width = G + 2W + 2D ; flat height = 2*tuck + H
        self.assertAlmostEqual(coords.flat_width_mm, 10 + 2 * 35 + 2 * 30, places=2)
        self.assertGreater(coords.flat_height_mm, 100)  # body + two tuck flaps
        self.assertEqual(len(coords.panels), 5)
        # bleed strictly contains cut strictly contains safe (validate() asserts this)
        self.assertGreater(coords.bleed_polygon.area, coords.cut_polygon.area)
        self.assertGreater(coords.cut_polygon.area, coords.safe_polygon.area)

    def test_engine_rejects_unprintable_dimensions(self):
        # height must exceed width and depth; 50 < width 35? no — use height<depth
        with self.assertRaises(Exception):
            calculate_straight_tuck_end(_params(width=35, depth=30, height=29))


class SvgExporterTest(_InTempDir):
    def test_svg_validates_clean(self):
        coords = calculate_straight_tuck_end(_params())
        svg = write_carton_svg(coords, "job-svg", output_dir=self._tmp)
        self.assertIn("<svg", svg)
        errors = validate_svg(svg, coords)
        self.assertEqual(errors, [], f"SVG validation errors: {errors}")
        self.assertTrue(os.path.exists(os.path.join(self._tmp, "job-svg.svg")))


class ProductionPdfTest(_InTempDir):
    def test_production_pdf_is_written_and_valid(self):
        coords = calculate_straight_tuck_end(_params())
        rel = write_carton_pdf(
            coords, "job-pdf",
            product_name="Test Carton", product_type="carton",
            bleed_mm=3.0, safe_margin_mm=4.0, glue_tab_mm=10.0,
            board_thickness_mm=0.35,
            output_dir=self._tmp,
        )
        self.assertEqual(rel, os.path.join(self._tmp, "job-pdf_production.pdf"))
        self.assertTrue(os.path.exists(rel))
        with open(rel, "rb") as fh:
            data = fh.read()
        self.assertTrue(data.startswith(b"%PDF"), "not a PDF file")
        self.assertIn(b"%%EOF", data)
        self.assertGreater(len(data), 1500)

    def test_production_pdf_declares_die_separations(self):
        """The cut + crease rules must ride on named spot separations so a
        die-cut house finds them on their own plates."""
        coords = calculate_straight_tuck_end(_params())
        rel = write_carton_pdf(coords, "job-sep", output_dir=self._tmp)
        with open(rel, "rb") as fh:
            data = fh.read()
        # reportlab writes Separation colorant names as plaintext PDF names.
        self.assertIn(b"CutContour", data)
        self.assertIn(b"Crease", data)

    def test_production_pdf_handles_large_and_small_cartons(self):
        for w, d, h in [(12, 12, 60), (50, 40, 180)]:
            coords = calculate_straight_tuck_end(_params(width=w, depth=d, height=h))
            rel = write_carton_pdf(coords, f"job-{w}-{d}-{h}", output_dir=self._tmp)
            self.assertTrue(os.path.exists(rel))
