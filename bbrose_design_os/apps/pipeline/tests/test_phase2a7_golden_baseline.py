"""Phase 2A-7 golden regression baseline (ACCEPTED 2026-07-22, a76f660).

Task #50's accepted reconstruction is the frozen fixture for the
selected-concept fidelity contract. These assertions pin the ACCEPTED
numbers — a change here is a change to a human-accepted baseline and must
never happen silently: update only with an explicit new acceptance.

Accepted: GeneratedImage #89 / C_POWDER_CONSTELLATION on
straight_tuck_end_carton/1.1 at 90 × 25 × 92 mm, BarlowCondensed-Bold
(concept reconstruction only; FONT_LICENSE_EVIDENCE_REQUIRED_FOR_PRODUCTION
remains a Gate-2 blocker).
"""
from __future__ import annotations

import hashlib

from django.test import TestCase

from apps.ire.compose_vector_art import VectorArtStyle, compose_vector_art_graph
from apps.ire.concept_fidelity import (
    validate_concept_fidelity,
    validate_concept_geometry,
)
from apps.ire.geometry_report import measure_front_geometry

from .test_selected_concept_fidelity import SELECTED_VARIATION, _spec

from apps.ire.materials_paths import resolve_material_file as _physical_material
# Day 6 library migration: the accepted face keeps its recorded identity; the bytes are located through the manifest.
BARLOW_PATH = str(_physical_material("/Users/symow/Desktop/bbrose-systemOS/materials/Fonts/3333/BarlowCondensed-Bold.ttf"))
#: The accepted font file — a silent swap of the face is a baseline change.
BARLOW_SHA256 = ("79483069c602019259fd2215af033c60fb5c90f3071097839180337dc"
                 "306223b")
GOLDEN_SEED = 50


class Phase2A7GoldenBaselineTests(TestCase):
    """The accepted reconstruction, recomposed deterministically."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from apps.dielines.geometry.engine import calculate_dieline
        from apps.dielines.validators.schema import DielineInputJSON
        cls.spec = {**_spec(),
                    "confirmed_font": {"name": "BarlowCondensed-Bold",
                                       "path": BARLOW_PATH}}
        params = DielineInputJSON(
            template="straight_tuck_end_carton", unit="mm",
            dimensions={"width_mm": 90.0, "depth_mm": 25.0,
                        "height_mm": 92.0},
            print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
            construction={"glue_tab_mm": 12.0, "board_thickness_mm": 0.35,
                          "thickness_compensation": True},
            metadata={"product_name": "Baked Powder",
                      "product_type": "face powder"})
        coords = calculate_dieline(params)
        cls.doc = compose_vector_art_graph(
            coords, style=VectorArtStyle.for_variation(SELECTED_VARIATION,
                                                       seed=GOLDEN_SEED),
            product_name="Baked Powder", subtitle="face powder",
            concept_spec=cls.spec)
        front = {p.name: p for p in coords.panels}["front"]
        min_x, min_y, _, _ = coords.bleed_polygon.bounds
        cls.bounds = (front.x - (min_x - 10), front.y - (min_y - 10),
                      front.width, front.height)
        cls.geometry = measure_front_geometry(cls.doc, cls.bounds)

    def test_accepted_font_file_is_unchanged(self):
        digest = hashlib.sha256(open(BARLOW_PATH, "rb").read()).hexdigest()
        assert digest == BARLOW_SHA256

    def test_zero_fidelity_codes(self):
        assert validate_concept_geometry(self.doc, self.spec,
                                         self.bounds) == []
        assert validate_concept_fidelity(self.doc, self.spec) == []

    def test_accepted_typography_dominance(self):
        group = self.geometry["product_name_group"]
        assert abs(group["w"] - 0.46) < 0.02
        assert abs(group["h"] - 0.46) < 0.02
        assert self.geometry["metric_font"] == "BarlowCondensed-Bold"

    def test_accepted_logo_frame_zone(self):
        frame = self.geometry["logo_frame_group"]
        assert frame["x"] <= 0.10 and frame["y"] <= 0.10
        assert abs(frame["w"] - 0.38) < 0.03

    def test_accepted_motif_density_and_centroid(self):
        constellation = self.geometry["constellation"]
        assert constellation["front_count"] == 117
        assert abs(constellation["coverage_fraction"] - 0.166) < 0.02
        centroid = constellation["centroid"]
        assert abs(centroid["x"] - 0.69) < 0.03
        assert abs(centroid["y"] - 0.70) < 0.03
        assert constellation["quadrant_share"]["lower_right"] >= 0.7

    def test_accepted_panel_continuation(self):
        constellation = self.geometry["constellation"]
        assert constellation["side_continuation_count"] == 14
        assert constellation["other_surface_counts"] == {"side_left": 4}

    def test_zero_decorative_rasters_and_live_text(self):
        inventory = self.doc.metadata["inventory"]
        assert inventory["decorative_raster_count"] == 0
        assert inventory["outlined_text_count"] == 0
        assert inventory["live_text_count"] == 4

    def test_emitted_pdf_agrees_with_measurement(self):
        """Browser/PDF geometry agreement: the emitted spans match the
        measured widths to within a millimeter."""
        import shutil
        import tempfile
        from pathlib import Path
        import fitz
        from apps.ire.emitters.pdf_ai import emit_pdf_ai
        out = Path(tempfile.mkdtemp()) / "golden.ai"
        self.addCleanup(shutil.rmtree, out.parent, True)
        emit_pdf_ai(self.doc, str(out))
        with fitz.open(str(out)) as pdf:
            page = pdf[0]
            fonts = {f[3] for f in page.get_fonts()}
            assert any("BarlowCondensed-Bold" in f for f in fonts)
            spans = {}
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span["text"].strip()
                        if text in ("BAKED", "POWDER"):
                            x0, _, x1, _ = span["bbox"]
                            spans[text] = (x1 - x0) * 25.4 / 72
        fw = self.bounds[2]
        measured = self.geometry["name_lines"]
        assert abs(spans["BAKED"]
                   - measured["product-name-line-1"]["w"] * fw) < 1.0
        assert abs(spans["POWDER"]
                   - measured["product-name-line-2"]["w"] * fw) < 1.0
