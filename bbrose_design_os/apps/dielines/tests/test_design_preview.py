"""Design-on-dieline preview exporters (P4 fix, 2026-07-04)."""
from __future__ import annotations

import base64
import io
import os

import pytest

from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.validators.schema import DielineInputJSON

# 1x1 rose-pink PNG.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4"
    "z8Dwn4EBAAT/Af9jZv5kAAAAAElFTkSuQmCC"
)


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


def _inflated_pdf_streams(path):
    import base64 as b64
    import re
    import zlib

    raw = open(path, "rb").read()
    inflated = b""
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.DOTALL):
        chunk = m.group(1).strip()
        try:
            inflated += zlib.decompress(b64.a85decode(chunk, adobe=True))
        except (ValueError, zlib.error):
            continue
    return raw, inflated


def test_export_service_builds_the_editable_ai_from_the_design_graph(coords, tmp_path, settings, db):
    """[The clean-up of 2026-10-04 (E2), approved by the owner: the service's pixel-faithful mode and the switch that
    chose between the two are removed — the Design Graph's editable .ai is the one it builds.]"""
    settings.MEDIA_ROOT = str(tmp_path)
    from apps.dielines.models import DielineJob
    from apps.dielines.services.export_service import generate_exports
    job = DielineJob.objects.create(
        template_type="straight_tuck_end_carton", scenario="A", input_json={},
    )
    params = DielineInputJSON(
        template="straight_tuck_end_carton", unit="mm",
        dimensions={"width_mm": 28, "depth_mm": 28, "height_mm": 120},
        print_settings={}, construction={},
        metadata={"product_name": "Hydra Serum", "product_type": "30 ml"},
    )
    result = generate_exports(job, params)
    ai = result["design_preview_ai_path"]
    assert ai and os.path.exists(ai)
    # components mode is now graph-emitted (apps.ire): native editable objects
    # — live text + vector drawings, no baked "DESIGN COMPONENTS" raster caption.
    fitz = pytest.importorskip("fitz")
    page = fitz.open(ai)[0]
    assert len(page.get_drawings()) > 0
    # [§BH55 Phase 2, 2026-09-19: the name is set as type at 9.0 pt and MEASURED inside its 28 mm front, 20 mm inside
    # the safe margin — it sets in two lines now, each live text, so the name is read across them]
    assert "Hydra Serum" in " ".join(page.get_text().split())          # live product-name text


def test_export_service_composes_a_carton_given_no_picture(coords, tmp_path, settings, db):
    settings.MEDIA_ROOT = str(tmp_path)
    from apps.dielines.models import DielineJob
    from apps.dielines.services.export_service import generate_exports
    job = DielineJob.objects.create(
        template_type="straight_tuck_end_carton", scenario="A", input_json={},
    )
    params = DielineInputJSON(
        template="straight_tuck_end_carton", unit="mm",
        dimensions={"width_mm": 28, "depth_mm": 28, "height_mm": 120},
        print_settings={}, construction={},
        metadata={"product_name": "T", "product_type": "t"},
    )
    # [the owner's finding on design 119, 2026-10-03: "Every panel is vector"] given no picture the carton is still
    # composed, as editable objects with no picture — it read "previews are None". [The clean-up of 2026-10-04 (E2):
    # a picture can no longer be passed at all; the half of this test that passed one left with the parameter.]
    result = generate_exports(job, params)
    # The editable .ai is always produced; the PNG preview is best-effort
    # (needs sips/pdftoppm). No user-facing SVG key exists anymore.
    assert result["design_preview_ai_path"] and os.path.exists(result["design_preview_ai_path"])
    assert "design_preview_svg" not in result
    assert "design_preview_png_path" in result
    fitz = pytest.importorskip("fitz")
    assert len(fitz.open(result["design_preview_ai_path"])[0].get_images()) <= 1    # at most the house mark's own


def test_his_finding_on_119_a_carton_drawn_from_its_map_is_composed_with_no_picture(coords, tmp_path, settings, db):
    """The owner's finding on design 119 (2026-10-03, transcribed at 32898c7): "KILL THE RASTER PATH ... Every panel is
    vector, drawn from the concept's map". A carton whose front is drawn from its concept's map, given no artwork and no
    motif, is still composed as editable objects on its map's ground; its production PDF carries no picture under its
    plates; the design file no picture but the house mark's own, if the mark is drawn from its raster. [The clean-up of
    2026-10-04 (E2): the switch that could ask the service for the pixel-faithful file is removed.]"""
    settings.MEDIA_ROOT = str(tmp_path)
    fitz = pytest.importorskip("fitz")
    from apps.dielines.models import DielineJob
    from apps.dielines.services.export_service import generate_exports
    job = DielineJob.objects.create(template_type="straight_tuck_end_carton", scenario="A", input_json={})
    params = DielineInputJSON(
        template="straight_tuck_end_carton", unit="mm",
        dimensions={"width_mm": 22, "depth_mm": 22, "height_mm": 105},
        print_settings={}, construction={},
        metadata={"product_name": "Rose Glaze Lip Gloss", "product_type": "carton"},
    )
    square = [[[[0.2, 0.2], [0.4, 0.2, 0.6, 0.2, 0.8, 0.2], [0.8, 0.4, 0.8, 0.6, 0.8, 0.8],
                [0.6, 0.8, 0.4, 0.8, 0.2, 0.8], [0.2, 0.6, 0.2, 0.4, 0.2, 0.2]]]]
    front = {"shapes": {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "x"},
                        "shapes": [{"part": "berry silhouette", "ink": "#56111B", "box": [0.2, 0.2, 0.8, 0.8],
                                    "cubics": square}]},
             "edge_part": None, "ground": "#F1D2C0"}
    result = generate_exports(job, params, artwork_tint="#F1D2C0", map_front=front)
    ai = result["design_preview_ai_path"]
    assert ai and os.path.exists(ai)
    _, inflated = _inflated_pdf_streams(ai)
    assert b"DESIGN PREVIEW" not in inflated                       # never the pixel-faithful file
    assert len(fitz.open(ai)[0].get_images()) <= 1                 # at most the house mark's own raster
    assert fitz.open(result["production_pdf_path"])[0].get_images() == []
