"""Full-surface artwork on every panel and flap (2026-07-07), as the raster preview exporters (design_preview.py)
draw it. [The clean-up of 2026-10-04 (E2), approved by the owner: the production PDF's artwork underlay and the
composer's motif are removed, and with them cover_box and their tests.]"""
from __future__ import annotations

import pytest

from apps.dielines.exporters.artwork_layers import (
    artwork_targets,
    target_bounds,
)
from apps.dielines.exporters.design_preview import (
    export_design_components_ai,
    export_design_preview_ai,
    export_design_preview_svg,
)
from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.tests.test_design_preview import _PNG, _inflated_pdf_streams
from apps.dielines.validators.schema import DielineInputJSON

_INFO = {"description": "A palette.", "barcode_ean": "5061030633823"}


@pytest.fixture
def coords():
    return calculate_dieline(DielineInputJSON(
        template="straight_tuck_end_carton", unit="mm",
        dimensions={"width_mm": 28, "depth_mm": 28, "height_mm": 120},
        print_settings={}, construction={},
        metadata={"product_name": "T", "product_type": "t"},
    ))


@pytest.fixture
def artwork(tmp_path):
    p = tmp_path / "art.png"
    p.write_bytes(_PNG)
    return str(p)


@pytest.fixture
def motif(tmp_path):
    p = tmp_path / "motif.png"
    p.write_bytes(_PNG)
    return str(p)


class TestTargets:
    def test_every_surface_is_covered(self, coords):
        targets = artwork_targets(coords, panel_info_present=True)
        kinds = {t.kind for t in targets}
        assert kinds == {"full", "motif", "sticker"}
        # 5 body panels + 6 flaps (2 tucks + 4 dusts)
        assert len(targets) == 11
        assert sum(1 for t in targets if t.comp_id) == 6
        assert all(target_bounds(coords, t) for t in targets)

    def test_back_gets_motif_without_info(self, coords):
        targets = artwork_targets(coords, panel_info_present=False)
        back = next(t for t in targets if t.panel is not None
                    and t.panel.name == "back")
        assert back.kind == "motif"


class TestSvgFullSurface:
    def test_motif_defined_once_and_used_per_surface(self, coords, artwork,
                                                     motif, tmp_path):
        svg = export_design_preview_svg(
            coords, "fs1", str(tmp_path), artwork,
            panel_info=_INFO, motif_path=motif)
        assert svg.count('id="motif-img"') == 1        # single base64 payload
        # 9 motif surfaces: side_left, side_right, glue_tab + 6 flaps
        # (front carries the full artwork; back is the sticker)
        assert svg.count("<use ") == 9
        assert svg.count("<clipPath ") >= 10
        assert 'clip-path="url(#clip-t' in svg

    def test_legacy_layout_untouched_without_motif(self, coords, artwork, tmp_path):
        svg = export_design_preview_svg(coords, "fs2", str(tmp_path), artwork)
        assert svg.count("<image ") == 2               # front + back, as before
        assert "<use " not in svg


class TestAiFullSurface:
    def test_faithful_ai_draws_artwork_and_motif(self, coords, artwork,
                                                 motif, tmp_path):
        path = export_design_preview_ai(
            coords, "fs3", str(tmp_path), artwork,
            panel_info=_INFO, motif_path=motif)
        raw, _ = _inflated_pdf_streams(path)
        # two distinct image XObjects embedded (artwork + motif)
        assert raw.count(b"/Subtype /Image") >= 2

    def test_components_ai_covers_flaps(self, coords, motif, tmp_path):
        path = export_design_components_ai(
            coords, "fs4", str(tmp_path), motif, panel_info=_INFO)
        _, inflated = _inflated_pdf_streams(path)
        # a curveTo-clipped tuck flap shows up as 'c' path ops before 'W n'
        assert b" c\n" in inflated or b" c " in inflated
