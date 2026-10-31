"""Full-surface artwork on every panel and flap (2026-07-07), as the raster preview exporters (design_preview.py)
draw it. [The clean-up of 2026-10-04 (E2), approved by the owner: the production PDF's artwork underlay and the
composer's motif are removed, and with them cover_box and their tests.]"""
from __future__ import annotations

import pytest

from apps.dielines.exporters.artwork_layers import (
    artwork_targets,
    target_bounds,
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


