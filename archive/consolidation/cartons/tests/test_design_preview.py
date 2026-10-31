"""Design-on-dieline preview exporters (P4 fix, 2026-07-04)."""
from __future__ import annotations

import base64
import io
import os

import pytest

from apps.dielines.exporters.design_preview import (
    export_design_preview_ai,
    export_design_preview_svg,
)
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


def test_svg_embeds_artwork_clipped_to_display_panels(coords, artwork, tmp_path):
    svg = export_design_preview_svg(coords, "j1", str(tmp_path), artwork)
    assert svg.count("<image ") == 2                      # front + back
    assert 'clip-path="url(#clip-front)"' in svg
    assert 'clip-path="url(#clip-back)"' in svg
    assert "data:image/png;base64," in svg
    assert "DESIGN PREVIEW" in svg                        # caption present
    assert os.path.exists(tmp_path / "j1_design_preview.svg")


def test_ai_is_pdf_compatible_and_nonempty(coords, artwork, tmp_path):
    path = export_design_preview_ai(coords, "j1", str(tmp_path), artwork)
    with open(path, "rb") as fh:
        head = fh.read(5)
    assert head == b"%PDF-"                               # .ai = PDF-compatible
    assert os.path.getsize(path) > 1000


def test_components_ai_has_separate_objects_and_live_text(coords, artwork, tmp_path):
    from apps.dielines.exporters.design_preview import export_design_components_ai
    logo = tmp_path / "logo.png"
    logo.write_bytes(_PNG)
    path = export_design_components_ai(
        coords, "jc", str(tmp_path), artwork,
        logo_path=str(logo), product_name="Hydra Serum", subtitle="30 ml",
    )
    raw, inflated = _inflated_pdf_streams(path)
    assert raw[:5] == b"%PDF-"
    # Separate raster components: motif + logo = at least 2 image XObjects.
    assert raw.count(b"/Subtype /Image") >= 2
    # LIVE text (editable in Illustrator): reportlab writes content streams
    # as ASCII85(Flate(...)) — decode both layers and find the strings. A
    # flattened raster would contain neither.
    assert b"Hydra Serum" in inflated
    assert b"30 ml" in inflated


def test_components_ai_renders_info_panel(coords, artwork, tmp_path):
    """Regulatory back panel (2026-07-06): live text sections + vector
    EAN-13 + QR, replacing the motif on the back face."""
    import base64 as b64
    import re
    import zlib

    from apps.dielines.exporters.design_preview import export_design_components_ai
    path = export_design_components_ai(
        coords, "ji", str(tmp_path), artwork,
        product_name="Hydra Serum",
        panel_info={
            "product_name": "BBROSE Hydra Serum",
            "description": "Deeply hydrating serum.",
            "ingredients": "AQUA, SODIUM HYALURONATE.",
            "how_to_use": "Apply 2-3 drops daily.",
            "warnings": "Avoid contact with eyes.",
            "net_weight": "30 ml",
            "item_no": "HA-1",
            "barcode_ean": "5061030633786",
            "qr_url": "https://www.bbrose.com",
            "regulatory_text": "IMPORTER: BBPUER FOR COMMERCIAL AGENCIES",
        },
    )
    raw = open(path, "rb").read()
    inflated = b""
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.DOTALL):
        try:
            inflated += zlib.decompress(b64.a85decode(m.group(1).strip(), adobe=True))
        except (ValueError, zlib.error):
            continue
    for expected in (b"INGREDIENTS:", b"HOW TO USE:", b"WARNINGS:",
                     b"BBROSE HYDRA SERUM", b"ITEM NO: HA-1", b"IMPORTER"):
        assert expected in inflated, expected
    # EAN-13 human-readable digits are drawn by the vector barcode.
    assert b"061030" in inflated


def test_faithful_ai_renders_info_panel(coords, artwork, tmp_path):
    """2026-07-06 regression: the user filled the dimension-gate info form
    but the faithful .ai (an available export mode; "components" is the
    default since 2026-07-07) ignored panel_info entirely."""
    path = export_design_preview_ai(
        coords, "jf", str(tmp_path), artwork,
        panel_info={
            "product_name": "Silk Veil Lip Gloss",
            "description": "High-shine, non-sticky lip gloss.",
            "ingredients": "POLYBUTENE, OCTYLDODECANOL.",
            "barcode_ean": "506103063381",
            "qr_url": "https://www.bbrose.com",
        },
    )
    _, inflated = _inflated_pdf_streams(path)
    for expected in (b"SILK VEIL LIP GLOSS", b"INGREDIENTS:", b"POLYBUTENE"):
        assert expected in inflated, expected


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
