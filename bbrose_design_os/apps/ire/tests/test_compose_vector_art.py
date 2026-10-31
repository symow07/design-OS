"""Native-vector artwork composer (DIP-2A-5-DIE-3).

The Gate-2 correction contract these tests pin:
  * the decorative field is PURE vector — zero decorative rasters, zero
    panel-sized rasters; the sole permitted Image is the official logo
    lockup (small, role="logo")
  * grounds are editable gradients, linework is Bézier paths, typography is
    live text; every style color carries a CMYK override
  * the back panel stays quiet (no pour linework behind the legal sticker)
  * composition is deterministic (same style/seed → same graph)
  * the emitted .ai embeds no raster XObject except the logo
"""
from __future__ import annotations

import pytest

from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.validators.schema import DielineInputJSON
from apps.ire.compose_vector_art import (
    VectorArtStyle,
    compose_vector_art_graph,
    document_inventory,
)
from apps.ire.emitters.pdf_ai import emit_pdf_ai
from apps.ire.graph import GradientFill, Group, Image, Path, TextRun

_INFO = {"net_weight": "30 ml", "warnings": "For external use only.",
         "how_to_use": "Shake well."}


def _coords():
    return calculate_dieline(DielineInputJSON(
        template="skynte_foundation_tuck_carton", unit="mm",
        dimensions={"width_mm": 42.0, "depth_mm": 32.0, "height_mm": 140.0},
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction={"glue_tab_mm": 10.0, "board_thickness_mm": 0.30,
                      "thickness_compensation": True},
        metadata={"product_name": "Skynte Foundation",
                  "product_type": "foundation"},
    ))


def _doc(logo_path=None):
    return compose_vector_art_graph(
        _coords(), style=VectorArtStyle(),
        logo_path=logo_path, product_name="Skynte Foundation",
        subtitle="Silk Veil Fluid Foundation", panel_info=_INFO)


class TestVectorPurity:
    def test_zero_decorative_and_panel_sized_rasters(self):
        inv = _doc().metadata["inventory"]
        assert inv["decorative_raster_count"] == 0
        assert inv["panel_sized_raster_count"] == 0
        assert inv["raster_count"] == 0          # no logo file supplied

    def test_logo_is_the_only_raster_when_present(self, tmp_path):
        from PIL import Image as PILImage
        logo = tmp_path / "logo.png"
        PILImage.new("RGBA", (400, 120), (90, 40, 60, 255)).save(logo)
        doc = _doc(logo_path=str(logo))
        inv = doc.metadata["inventory"]
        assert inv["raster_count"] == 1
        r = inv["rasters"][0]
        assert r["logo_lockup"] is True
        assert r["decorative"] is False and r["panel_sized"] is False

    def test_ground_is_an_editable_gradient(self):
        doc = _doc()
        grounds = doc.find_role("background")[0]
        gradient_paths = [n for n in grounds.children
                          if isinstance(n, Path)
                          and isinstance(n.fill, GradientFill)]
        assert gradient_paths, "ground must be a gradient-filled path"

    def test_decoration_is_bezier_paths(self):
        doc = _doc()

        def walk(g):
            for child in g.children:
                yield child
                if isinstance(child, Group):
                    yield from walk(child)

        deco = [g for g in doc.find_role("decoration") if isinstance(g, Group)]
        paths = [n for g in deco for n in walk(g) if isinstance(n, Path)]
        assert len(paths) > 50
        assert all(n.fill or n.stroke for n in paths)

    def test_all_style_colors_carry_cmyk(self):
        swatches = VectorArtStyle().parameters.swatches
        for sw in swatches.all():
            assert sw.color().cmyk is not None, f"{sw.name} has no CMYK"


class TestLayoutContract:
    def test_back_panel_quiet_no_pour_group(self):
        doc = _doc()
        deco_names = {g.name for g in doc.find_role("decoration")
                      if isinstance(g, Group)}
        lang = VectorArtStyle().language
        assert f"{lang}-back" not in deco_names, "back panel must stay quiet"
        assert f"{lang}-front" in deco_names

    def test_typography_is_live_text_front_only(self):
        doc = _doc()
        texts = [n for n, _ in doc.walk() if isinstance(n, TextRun)]
        assert {t.name for t in texts} == {"product-name", "subtitle"}
        assert all(t.size_pt >= 5.0 for t in texts)

    def test_sticker_bridge_on_back(self):
        doc = _doc()
        info = doc.find_role("info")[0]
        assert info.children and info.children[0].type == "sticker_bridge"

    def test_structure_layer_present(self):
        doc = _doc()
        assert doc.find_role("structure")[0].children

    def test_deterministic(self):
        a = _doc().model_dump_json()
        b = _doc().model_dump_json()
        assert a == b


class TestEmittedFile:
    def test_ai_has_no_raster_xobjects_without_logo(self, tmp_path):
        fitz = pytest.importorskip("fitz")
        doc = _doc()
        out = str(tmp_path / "vector.ai")
        emit_pdf_ai(doc, out)
        with fitz.open(out) as pdf:
            images = pdf[0].get_images(full=True)
            text = pdf[0].get_text()
        assert images == []
        assert "Skynte Foundation" in text      # live, extractable text

    def test_inventory_matches_walk(self):
        doc = _doc()
        inv = document_inventory(doc, _coords())
        # Panel-role emphasis (§8) deliberately thins the non-front surfaces,
        # so the count is lower than the flat-density DIE-3 composition while
        # still being a genuinely reconstructed field.
        assert inv["vector_object_count"] > 50
        assert inv["decorative_vector_count"] > 40
        assert inv["live_text_count"] == 2
        assert inv["min_text_size_pt"] >= 5.0
        assert inv["artwork_mode"] == "NATIVE_VECTOR_RECONSTRUCTION"


class TestTheMarkFromItsApprovedVectorMaster:
    """THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
    switch the mark to it so gold foil can print." Handed an approved vector master — a SYNTHETIC fixture here
    (apps/ire/tests/brand_mark_fixtures.py) — the dieline's lockup is no raster: it is drawn from the master, carries
    the master's flag in its name where the raster carries BRAND_LOGO_RASTER_FALLBACK, and is handed off as one path."""

    def _marked(self):
        from apps.ire import brand_mark as B
        from apps.ire.tests import brand_mark_fixtures as FX
        master = B.read_master(FX.POTRACE_STYLE)
        doc = compose_vector_art_graph(
            _coords(), style=VectorArtStyle(), logo_path=None, product_name="Skynte Foundation",
            subtitle="Silk Veil Fluid Foundation", panel_info=_INFO, logo_master=master)
        return doc, master

    def test_the_lockup_is_drawn_from_the_master_and_no_raster_is_placed(self, tmp_path):
        from apps.ire import brand_mark as B
        from apps.ire.compose_vector_art import BRAND_LOGO_RASTER_FALLBACK
        doc, master = self._marked()
        logos = [n for n, _ in doc.walk() if (n.name or "").startswith("logo-front")]
        assert [(n.type, n.name) for n in logos] == [("asset_ref", "logo-front-" + B.VECTOR_MASTER_FLAG)]
        assert BRAND_LOGO_RASTER_FALLBACK not in logos[0].name
        assert abs(logos[0].h / logos[0].w - master.aspect) < 1e-12
        inv = doc.metadata["inventory"]
        assert inv["raster_count"] == 0 and inv["decorative_raster_count"] == 0
        out = emit_pdf_ai(doc, str(tmp_path / "vart.ai"))
        import fitz
        with fitz.open(out) as pdf:
            assert pdf[0].get_images() == []

    def test_the_handoff_carries_the_mark_as_one_path_and_its_census_holds(self):
        from apps.ire.handoff.graph_schema import serialize_handoff_graph
        from apps.ire.handoff.package import HANDOFF_OBJECT_COUNT_MISMATCH, validate_handoff
        doc, master = self._marked()
        g = serialize_handoff_graph(doc, task_id=1)
        brand = [o for o in g["objects"] if o["layer"] == "06_BRAND"]
        assert [(o["type"], o.get("fill_rule")) for o in brand] == [("path", "nonzero")]
        assert sum(1 for s in brand[0]["segments"] if s[0] == "M") == master.census["subpaths"]
        assert not [c for c in validate_handoff(doc, g) if c.startswith(HANDOFF_OBJECT_COUNT_MISMATCH)]
