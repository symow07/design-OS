"""Gate-2 production readiness validator (DIP-2A-5-DIE-4).

Each contract failure code is exercised against a stub PackagingOutput:
the validator must fail closed (missing artifacts are failures, not
passes) and pass only a fully corrected deliverable set.
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest
from django.test import override_settings

from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.validators.production_readiness import (
    evaluate_production_readiness,
)
from apps.dielines.validators.schema import DielineInputJSON

GOOD_INFO = {
    "net_weight": "30 ml / 1.0 fl. oz.",
    "warnings": "For external use only. Keep out of reach of children.",
    "how_to_use": "Shake well before use. Apply a small amount.",
}


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


def _filefield(path: str | None):
    if path is None:
        return SimpleNamespace(name="")
    return SimpleNamespace(name=os.path.basename(path), path=path)


def _write_job_artifacts(media_root, job_id, *, checklist=None, inventory=None):
    d = os.path.join(media_root, "dielines", job_id)
    os.makedirs(d, exist_ok=True)
    if checklist is not None:
        with open(os.path.join(d, f"{job_id}_structural_checklist.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(checklist, fh)
    if inventory is not None:
        with open(os.path.join(d, f"{job_id}_artwork_inventory.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(inventory, fh)
    return d


def _good_checklist():
    from apps.dielines.analysis.reconciliation import reconcile_dimensions
    from apps.dielines.exporters.structural_comparison import build_checklist
    coords = _coords()
    rec = reconcile_dimensions(coords, (41.4, 31.4, 138.9), (42.4, 32.4, 140.9))
    return build_checklist(coords, rec)


def _good_inventory():
    return {"artwork_mode": "vector", "inventory": {
        "decorative_raster_count": 0, "panel_sized_raster_count": 0,
        "raster_count": 1, "min_text_size_pt": 6.0,
        "vector_object_count": 150, "live_text_count": 2}}


def _vector_ai(tmp_path):
    from apps.ire.compose_vector_art import compose_vector_art_graph
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    doc = compose_vector_art_graph(
        _coords(), product_name="Skynte Foundation",
        subtitle="Silk Veil", panel_info=GOOD_INFO)
    return emit_pdf_ai(doc, str(tmp_path / "design.ai"))


def _output(tmp_path, media_root, *, checklist, inventory, spec=None,
            ai_path=None, pdf_path=None):
    job_id = "test-job-readiness"
    _write_job_artifacts(media_root, job_id, checklist=checklist,
                         inventory=inventory)
    if pdf_path is None:
        pdf_path = str(tmp_path / "prod.pdf")
        open(pdf_path, "wb").write(b"%PDF-1.4\n%%EOF\n")
    return SimpleNamespace(
        spec_sheet=spec if spec is not None else {
            "template": "skynte_foundation_tuck_carton",
            "required_template": "skynte_foundation_tuck_carton",
            "panel_info": dict(GOOD_INFO),
        },
        dieline_job=SimpleNamespace(id=job_id),
        design_preview_ai=_filefield(ai_path),
        production_pdf=_filefield(pdf_path),
    )


@pytest.fixture()
def media_root(tmp_path):
    root = tmp_path / "media"
    root.mkdir()
    with override_settings(MEDIA_ROOT=str(root)):
        yield str(root)


class TestPassing:
    def test_fully_corrected_output_is_ready(self, tmp_path, media_root):
        out = _output(tmp_path, media_root, checklist=_good_checklist(),
                      inventory=_good_inventory(),
                      ai_path=_vector_ai(tmp_path))
        report = evaluate_production_readiness(
            out, expected_template="skynte_foundation_tuck_carton",
            forbidden_panel_texts=("Design a luxury foundation carton",))
        assert report.failures == []
        assert report.ready is True


class TestFailClosed:
    def test_missing_checklist_and_inventory_fail(self, tmp_path, media_root):
        out = _output(tmp_path, media_root, checklist=None, inventory=None)
        codes = {f["code"] for f in evaluate_production_readiness(out).failures}
        assert {"STRUCTURE_CHECKLIST_MISSING",
                "ARTWORK_INVENTORY_MISSING"} <= codes

    def test_template_mismatch(self, tmp_path, media_root):
        out = _output(tmp_path, media_root, checklist=_good_checklist(),
                      inventory=_good_inventory())
        report = evaluate_production_readiness(
            out, expected_template="some_other_template")
        assert any(f["code"] == "TEMPLATE_MISMATCH" for f in report.failures)

    def test_raster_decorative_background(self, tmp_path, media_root):
        inv = _good_inventory()
        inv["inventory"]["decorative_raster_count"] = 3
        inv["inventory"]["panel_sized_raster_count"] = 2
        out = _output(tmp_path, media_root, checklist=_good_checklist(),
                      inventory=inv)
        codes = {f["code"] for f in evaluate_production_readiness(out).failures}
        assert "RASTER_DECORATIVE_BACKGROUND" in codes

    def test_unreconciled_dimensions(self, tmp_path, media_root):
        cl = _good_checklist()
        cl["reconciliation"]["discrepancies"] = ["inner width off by 3 mm"]
        out = _output(tmp_path, media_root, checklist=cl,
                      inventory=_good_inventory())
        codes = {f["code"] for f in evaluate_production_readiness(out).failures}
        assert "DIMENSIONS_UNRECONCILED" in codes

    def test_closure_collision_and_bleed(self, tmp_path, media_root):
        cl = _good_checklist()
        cl["reconciliation"]["collision_checks"] = [
            {"name": "dust_flap_opposing_clearance", "ok": False,
             "detail": "flaps overlap"},
            {"name": "bleed_contour_complete", "ok": False,
             "detail": "bleed open"},
        ]
        out = _output(tmp_path, media_root, checklist=cl,
                      inventory=_good_inventory())
        codes = {f["code"] for f in evaluate_production_readiness(out).failures}
        assert {"CLOSURE_COLLISION", "INCOMPLETE_BLEED"} <= codes

    def test_missing_closure_details(self, tmp_path, media_root):
        cl = _good_checklist()
        cl["required_features"][0]["present"] = False
        out = _output(tmp_path, media_root, checklist=cl,
                      inventory=_good_inventory())
        codes = {f["code"] for f in evaluate_production_readiness(out).failures}
        assert "MISSING_CLOSURE_DETAILS" in codes

    def test_placeholder_regulatory_info(self, tmp_path, media_root):
        spec = {"template": "skynte_foundation_tuck_carton",
                "panel_info": {"net_weight": "TBD", "warnings": "",
                               "how_to_use": "[add usage here]"}}
        out = _output(tmp_path, media_root, checklist=_good_checklist(),
                      inventory=_good_inventory(), spec=spec)
        report = evaluate_production_readiness(out)
        codes = [f["code"] for f in report.failures]
        assert codes.count("PLACEHOLDER_REGULATORY_INFO") == 3

    def test_placeholder_in_optional_field(self, tmp_path, media_root):
        spec = {"template": "skynte_foundation_tuck_carton",
                "panel_info": {**GOOD_INFO,
                               "ingredients": "INGREDIENTS: To be confirmed "
                                              "according to the approved "
                                              "product formulation."}}
        out = _output(tmp_path, media_root, checklist=_good_checklist(),
                      inventory=_good_inventory(), spec=spec)
        codes = [f["code"] for f in evaluate_production_readiness(out).failures]
        assert codes.count("PLACEHOLDER_REGULATORY_INFO") == 1

    def test_truncated_title_fragment_on_panel_caught(self, tmp_path,
                                                      media_root):
        pytest.importorskip("fitz")
        # A panel printing the first 60 chars of the brief title must fail
        # even though the full forbidden string never appears verbatim.
        from reportlab.pdfgen import canvas
        from reportlab.lib.colors import CMYKColor
        ai = str(tmp_path / "frag.ai")
        c = canvas.Canvas(ai)
        c.setFillColor(CMYKColor(0, 0, 0, 1))
        c.drawString(30, 500,
                     "Create a new coordinated outer packaging design for BBROSE S")
        c.save()
        out = _output(tmp_path, media_root, checklist=_good_checklist(),
                      inventory=_good_inventory(), ai_path=ai)
        report = evaluate_production_readiness(
            out, forbidden_panel_texts=(
                "Create a new coordinated outer packaging design for BBROSE "
                "Skynte Foundation.",))
        codes = {f["code"] for f in report.failures}
        assert "FORBIDDEN_PANEL_TEXT" in codes

    def test_text_below_minimum(self, tmp_path, media_root):
        inv = _good_inventory()
        inv["inventory"]["min_text_size_pt"] = 3.0
        out = _output(tmp_path, media_root, checklist=_good_checklist(),
                      inventory=inv)
        codes = {f["code"] for f in evaluate_production_readiness(out).failures}
        assert "TEXT_BELOW_MINIMUM_SIZE" in codes

    def test_forbidden_panel_text(self, tmp_path, media_root):
        pytest.importorskip("fitz")
        out = _output(tmp_path, media_root, checklist=_good_checklist(),
                      inventory=_good_inventory(),
                      ai_path=_vector_ai(tmp_path))
        report = evaluate_production_readiness(
            out, forbidden_panel_texts=("Skynte Foundation",))
        codes = {f["code"] for f in report.failures}
        assert "FORBIDDEN_PANEL_TEXT" in codes

    def test_rgb_artwork_detected(self, tmp_path, media_root):
        pytest.importorskip("fitz")
        # An RGB-painted PDF (reportlab default RGB fill).
        from reportlab.pdfgen import canvas
        rgb_pdf = str(tmp_path / "rgb.ai")
        c = canvas.Canvas(rgb_pdf)
        c.setFillColorRGB(1.0, 0.2, 0.2)
        c.rect(10, 10, 100, 100, fill=1)
        c.save()
        out = _output(tmp_path, media_root, checklist=_good_checklist(),
                      inventory=_good_inventory(), ai_path=rgb_pdf)
        codes = {f["code"] for f in evaluate_production_readiness(out).failures}
        assert "RGB_ARTWORK" in codes

    def test_missing_production_pdf(self, tmp_path, media_root):
        out = _output(tmp_path, media_root, checklist=_good_checklist(),
                      inventory=_good_inventory())
        out.production_pdf = _filefield(None)
        codes = {f["code"] for f in evaluate_production_readiness(out).failures}
        assert "PRODUCTION_PDF_MISSING" in codes
