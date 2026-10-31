"""Generalized production validator + editability report (Phase 2A-6 §11–12).

Every failure family gets a distinct, structured code; missing evidence
fails closed; readiness becomes true only when every check passes.
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest
from django.test import override_settings

from apps.dielines.analysis.reconciliation import reconcile_dimensions
from apps.dielines.exporters.structural_comparison import build_checklist
from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.validators.production import (
    CATEGORY_ARTWORK,
    CATEGORY_CONTENT,
    CATEGORY_OUTPUT,
    CATEGORY_STRUCTURAL,
    evaluate_production,
)
from apps.dielines.validators.schema import DielineInputJSON
from apps.pipeline.services.print_data import build_print_record

TEMPLATE = "skynte_foundation_tuck_carton"
INNER, OUTER = (41.4, 31.4, 138.9), (42.4, 32.4, 140.9)
GOOD_PRINT = {
    "brand_display_name": "BBROSE", "product_name": "Skynte Foundation",
    "product_type": "Fundación facial",
    "ingredients": "AQUA, GLYCERIN, TITANIUM DIOXIDE",
    "how_to_use": "Shake well and blend outward.",
    "warnings": "For external use only.",
    "net_weight": "30 ml", "manufacturer": "YIWU YIBIN TRADING COMPANY",
    "country_of_origin": "Made in China",
}


def _coords(t=0.30):
    return calculate_dieline(DielineInputJSON(
        template=TEMPLATE, unit="mm",
        dimensions={"width_mm": 42.0, "depth_mm": 32.0, "height_mm": 140.0},
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction={"glue_tab_mm": 10.0, "board_thickness_mm": t,
                      "thickness_compensation": True},
        metadata={"product_name": "Skynte Foundation", "product_type": "f"},
    ))


def _checklist(coords=None):
    coords = coords or _coords()
    return build_checklist(coords, reconcile_dimensions(coords, INNER, OUTER))


def _inventory(**over):
    inv = {"artwork_mode": "NATIVE_VECTOR_RECONSTRUCTION",
           "node_counts": {"sticker_bridge": 1},
           "decorative_raster_count": 0, "panel_sized_raster_count": 0,
           "raster_count": 1, "raster_area_mm2": 132.0,
           "raster_area_fraction": 0.004, "decorative_vector_count": 63,
           "min_text_size_pt": 6.0, "vector_object_count": 85,
           "live_text_count": 2, "outlined_text_count": 0,
           "gradient_count": 1, "clip_mask_count": 7,
           "swatches": {f"S{i}": {} for i in range(6)},
           "layer_groups": [{"name": "Background", "role": "background"}],
           "rasters": [{"name": "logo", "decorative": False,
                        "panel_sized": False, "logo_lockup": True,
                        "flag": "BRAND_LOGO_RASTER_FALLBACK"}],
           "panel_roles": []}
    inv.update(over)
    return {"artwork_mode": "vector", "inventory": inv}


def _job_dir(media_root, job_id, checklist=None, inventory=None):
    d = os.path.join(media_root, "dielines", job_id)
    os.makedirs(d, exist_ok=True)
    if checklist is not None:
        json.dump(checklist, open(
            os.path.join(d, f"{job_id}_structural_checklist.json"), "w"))
    if inventory is not None:
        json.dump(inventory, open(
            os.path.join(d, f"{job_id}_artwork_inventory.json"), "w"))


def _filefield(path):
    if not path:
        return SimpleNamespace(name="")
    return SimpleNamespace(name=os.path.basename(path), path=path)


def _confirmed_record(coords=None):
    from apps.dielines import registry
    params = {"width_mm": 42.0, "depth_mm": 32.0, "height_mm": 140.0}
    return {"template_id": TEMPLATE, "template_version": "1.0",
            "parameters": params, "confirmed_at": "2026-07-20T10:00:00Z",
            "confirmed_by": "reviewer",
            "geometry_hash": registry.geometry_hash(TEMPLATE, "1.0", params)}


def _output(tmp_path, media_root, *, checklist, inventory, spec=None,
            ai_path=None, pdf_path="auto", structure=None):
    job_id = "prod-validator-job"
    _job_dir(media_root, job_id, checklist, inventory)
    if pdf_path == "auto":
        pdf_path = str(tmp_path / "prod.pdf")
        _real_production_pdf(pdf_path)
    return SimpleNamespace(
        spec_sheet=spec if spec is not None else {
            "template": TEMPLATE, "required_template": TEMPLATE,
            "panel_order": [p.name for p in _coords().panels],
        },
        dieline_job=SimpleNamespace(
            id=job_id,
            structure_selection=(structure if structure is not None
                                 else _confirmed_record())),
        design_preview_ai=_filefield(ai_path),
        production_pdf=_filefield(pdf_path),
    )


def _real_production_pdf(path):
    """A genuine CMYK production PDF with the spot plates."""
    from apps.dielines.exporters.counter_display_files import write_carton_pdf
    out = write_carton_pdf(
        _coords(), "spot", product_name="P", product_type="t",
        bleed_mm=3.0, safe_margin_mm=4.0, glue_tab_mm=10.0,
        board_thickness_mm=0.30, output_dir=os.path.dirname(path))
    os.replace(out, path)
    return path


def _vector_ai(tmp_path):
    from apps.ire.compose_vector_art import (
        VectorArtStyle,
        compose_vector_art_graph,
    )
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    doc = compose_vector_art_graph(
        _coords(), style=VectorArtStyle(), product_name="Skynte Foundation",
        subtitle="Fundación facial", panel_info={"net_weight": "30 ml"})
    return emit_pdf_ai(doc, str(tmp_path / "design.ai"))


@pytest.fixture()
def media_root(tmp_path):
    root = tmp_path / "media"
    root.mkdir()
    with override_settings(MEDIA_ROOT=str(root)):
        yield str(root)


def _evaluate(out, **kw):
    kw.setdefault("expected_template", TEMPLATE)
    kw.setdefault("print_record",
                  build_print_record(GOOD_PRINT, verified_keys=GOOD_PRINT.keys()))
    return evaluate_production(out, **kw)


class TestFailClosed:
    def test_missing_evidence_fails_in_every_family(self, tmp_path, media_root):
        out = _output(tmp_path, media_root, checklist=None, inventory=None,
                      pdf_path=None, structure={})
        codes = _evaluate(out).codes()
        assert "STRUCTURE_CHECKLIST_MISSING" in codes
        assert "ARTWORK_INVENTORY_MISSING" in codes
        assert "PRODUCTION_PDF_MISSING" in codes
        assert "STRUCTURE_NOT_CONFIRMED" in codes


class TestStructuralFamily:
    def test_unconfirmed_structure_blocks(self, tmp_path, media_root):
        rec = _confirmed_record()
        rec["confirmed_at"] = ""
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory(), structure=rec)
        assert "STRUCTURE_NOT_CONFIRMED" in _evaluate(out).codes()

    def test_die_changed_after_confirmation_blocks(self, tmp_path, media_root):
        rec = _confirmed_record()
        rec["parameters"]["height_mm"] = 150.0      # hash no longer matches
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory(), structure=rec)
        assert "STRUCTURE_NOT_CONFIRMED" in _evaluate(out).codes()

    def test_panel_sequence_mismatch(self, tmp_path, media_root):
        spec = {"template": TEMPLATE, "required_template": TEMPLATE,
                "panel_order": ["glue_tab", "front", "side_left", "back",
                                "side_right"]}      # the STE order
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory(), spec=spec)
        assert "PANEL_SEQUENCE_MISMATCH" in _evaluate(out).codes()

    def test_template_mismatch(self, tmp_path, media_root):
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory())
        codes = _evaluate(out, expected_template="reverse_tuck_end_carton").codes()
        assert "TEMPLATE_MISMATCH" in codes

    def test_unreconciled_dimensions(self, tmp_path, media_root):
        cl = _checklist()
        cl["reconciliation"]["discrepancies"] = ["inner width off by 3 mm"]
        out = _output(tmp_path, media_root, checklist=cl, inventory=_inventory())
        assert "DIMENSIONS_UNRECONCILED" in _evaluate(out).codes()

    def test_collision_bleed_and_slit_codes_are_distinct(self, tmp_path,
                                                         media_root):
        cl = _checklist()
        cl["reconciliation"]["collision_checks"] = [
            {"name": "dust_flap_opposing_clearance", "ok": False, "detail": "x"},
            {"name": "bleed_contour_complete", "ok": False, "detail": "y"},
            {"name": "slit_web", "ok": False, "detail": "z"},
        ]
        out = _output(tmp_path, media_root, checklist=cl, inventory=_inventory())
        codes = _evaluate(out).codes()
        assert {"CLOSURE_COLLISION", "INCOMPLETE_BLEED",
                "INVALID_SLIT_OR_NOTCH"} <= codes

    def test_open_contour_and_cut_fold_conflict(self, tmp_path, media_root):
        cl = _checklist()
        cl["geometry_integrity"] = {"self_intersecting": True,
                                    "open_contour": True,
                                    "cut_fold_conflict": True}
        out = _output(tmp_path, media_root, checklist=cl, inventory=_inventory())
        codes = _evaluate(out).codes()
        assert "OPEN_OR_SELF_INTERSECTING_CONTOUR" in codes
        assert "CUT_FOLD_CONFLICT" in codes

    def test_missing_closure_geometry(self, tmp_path, media_root):
        cl = _checklist()
        cl["required_features"][0]["present"] = False
        out = _output(tmp_path, media_root, checklist=cl, inventory=_inventory())
        assert "MISSING_CLOSURE_GEOMETRY" in _evaluate(out).codes()


class TestArtworkFamily:
    def test_panel_sized_raster(self, tmp_path, media_root):
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory(panel_sized_raster_count=2))
        assert "PANEL_SIZED_RASTER" in _evaluate(out).codes()

    def test_printable_concept_render(self, tmp_path, media_root):
        inv = _inventory(decorative_raster_count=1)
        inv["inventory"]["rasters"] = [
            {"name": "motif-front", "decorative": True, "panel_sized": False}]
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=inv)
        assert "PRINTABLE_CONCEPT_RENDER" in _evaluate(out).codes()

    def test_flattened_panel_graphics(self, tmp_path, media_root):
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory(raster_area_fraction=0.45))
        assert "FLATTENED_PANEL_GRAPHICS" in _evaluate(out).codes()

    def test_insufficient_editable_vector_coverage(self, tmp_path, media_root):
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory(decorative_vector_count=3))
        assert "INSUFFICIENT_EDITABLE_VECTOR_COVERAGE" in _evaluate(out).codes()

    def test_duplicated_panel_texture(self, tmp_path, media_root):
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory(
                          duplicate_panel_groups=["side_left==side_right"]))
        assert "DUPLICATED_PANEL_TEXTURE" in _evaluate(out).codes()

    def test_reference_only_image_printable(self, tmp_path, media_root):
        inv = _inventory()
        inv["inventory"]["rasters"] = [
            {"name": "concept", "decorative": False, "panel_sized": False,
             "reference_only": True}]
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=inv)
        assert "REFERENCE_ONLY_IMAGE_PRINTABLE" in _evaluate(out).codes()


class TestContentFamily:
    def test_placeholder_inci_blocks(self, tmp_path, media_root):
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory())
        record = build_print_record(
            {**GOOD_PRINT, "ingredients": "To be confirmed"},
            verified_keys=GOOD_PRINT.keys())
        codes = _evaluate(out, print_record=record).codes()
        assert "PLACEHOLDER_PRINT_CONTENT" in codes

    def test_forbidden_panel_text(self, tmp_path, media_root):
        pytest.importorskip("fitz")
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory(), ai_path=_vector_ai(tmp_path))
        codes = _evaluate(
            out, forbidden_panel_texts=("Skynte Foundation",)).codes()
        assert "FORBIDDEN_PANEL_TEXT" in codes

    def test_text_below_minimum(self, tmp_path, media_root):
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory(min_text_size_pt=2.0))
        assert "TEXT_BELOW_MINIMUM_SIZE" in _evaluate(out).codes()


class TestColorOutputFamily:
    def test_rgb_production_artwork(self, tmp_path, media_root):
        pytest.importorskip("fitz")
        from reportlab.lib.colors import CMYKColor
        from reportlab.pdfgen import canvas
        rgb = str(tmp_path / "rgb.ai")
        c = canvas.Canvas(rgb)
        c.setFillColorRGB(1.0, 0.2, 0.2)
        c.rect(10, 10, 80, 80, fill=1)
        c.setFillColor(CMYKColor(0, 0, 0, 1))
        c.save()
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory(), ai_path=rgb)
        assert "RGB_PRODUCTION_ARTWORK" in _evaluate(out).codes()

    def test_missing_spot_definitions(self, tmp_path, media_root):
        from reportlab.pdfgen import canvas
        plain = str(tmp_path / "plain.pdf")
        c = canvas.Canvas(plain)
        c.rect(10, 10, 80, 80)
        c.save()
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory(), pdf_path=plain)
        assert "INVALID_SPOT_DEFINITION" in _evaluate(out).codes()

    def test_real_production_pdf_has_spot_plates(self, tmp_path, media_root):
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory())
        assert "INVALID_SPOT_DEFINITION" not in _evaluate(out).codes()

    def test_output_intent_gap_is_reported_not_hidden(self, tmp_path,
                                                      media_root):
        """The reportlab pipeline cannot attach an ICC OutputIntent — the
        validator states it as a real, coded failure rather than a warning."""
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory())
        assert "MISSING_OUTPUT_INTENT" in _evaluate(out).codes()


class TestEditabilityReport:
    def test_report_carries_every_required_metric(self, tmp_path, media_root):
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory())
        ed = _evaluate(out).editability
        for key in ("vector_object_count", "raster_object_count",
                    "raster_area_mm2", "decorative_vector_coverage",
                    "live_text_count", "outlined_text_count",
                    "clipping_masks", "gradients", "swatches", "spot_colors",
                    "technical_layers", "printing_layers",
                    "reference_only_layers", "editable_elements",
                    "fixed_elements"):
            assert key in ed, f"missing editability metric {key}"
        assert ed["editable_elements"] > ed["fixed_elements"]

    def test_failures_are_categorized(self, tmp_path, media_root):
        out = _output(tmp_path, media_root, checklist=None, inventory=None,
                      pdf_path=None, structure={})
        cats = _evaluate(out).by_category()
        assert CATEGORY_STRUCTURAL in cats
        assert CATEGORY_ARTWORK in cats
        assert CATEGORY_OUTPUT in cats
        assert all(f["code"] != "PRODUCTION_NOT_READY"
                   for fs in cats.values() for f in fs)

    def test_no_override_parameter_exists(self):
        import inspect
        sig = inspect.signature(evaluate_production)
        assert not any("override" in p or "force" in p or "skip" in p
                       for p in sig.parameters)


class TestOutputIntentAttachment:
    """§9: the intent is closable, its profile identity is recorded, and an
    unsuitable profile is refused rather than embedded."""

    _SYSTEM_CMYK = "/System/Library/ColorSync/Profiles/Generic CMYK Profile.icc"
    _SYSTEM_RGB = "/System/Library/ColorSync/Profiles/sRGB Profile.icc"

    def _pdf(self, tmp_path):
        return _real_production_pdf(str(tmp_path / "oi.pdf"))

    @staticmethod
    def _mock_cmyk_profile(path, *, space=b"CMYK", cls=b"prtr", desc=b"Mock Press"):
        """A minimal but STRUCTURALLY VALID ICC profile."""
        import struct
        tag_data = b"desc" + b"\x00" * 4 + struct.pack(">I", len(desc) + 1) \
            + desc + b"\x00"
        header = bytearray(128)
        header[8:10] = b"\x02\x20"                    # version 2.2
        header[12:16] = cls
        header[16:20] = space
        header[36:40] = b"acsp"
        table = struct.pack(">I", 1) + struct.pack(
            ">4sII", b"desc", 128 + 4 + 12, len(tag_data))
        blob = bytes(header) + table + tag_data
        blob = struct.pack(">I", len(blob)) + blob[4:]
        open(path, "wb").write(blob)
        return str(path)

    def test_unconfigured_reports_identity_not_a_guess(self, tmp_path):
        from apps.dielines.exporters.output_intent import (
            attach_output_intent,
            describe_profile,
        )
        pdf = self._pdf(tmp_path)
        before = os.path.getsize(pdf)
        attached, identity = attach_output_intent(pdf)
        assert attached is False
        assert identity.validation_result == "NOT_CONFIGURED"
        assert identity.configured is False
        assert "never guessed" in identity.detail
        assert os.path.getsize(pdf) == before
        assert describe_profile().valid is False

    def test_missing_profile_file_is_reported(self, tmp_path):
        from apps.dielines.exporters.output_intent import describe_profile
        with override_settings(
                PRODUCTION_ICC_PROFILE_PATH=str(tmp_path / "nope.icc")):
            identity = describe_profile()
        assert identity.validation_result == "FILE_NOT_FOUND"
        assert identity.valid is False

    def test_malformed_profile_is_refused(self, tmp_path):
        from apps.dielines.exporters.output_intent import describe_profile
        bad = tmp_path / "bad.icc"
        bad.write_bytes(b"not an icc profile at all" * 8)
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=str(bad)):
            identity = describe_profile()
        assert identity.validation_result == "MALFORMED"
        assert identity.valid is False
        assert identity.sha256                      # identity still recorded

    def test_rgb_profile_is_refused(self, tmp_path):
        from apps.dielines.exporters.output_intent import describe_profile
        rgb = self._mock_cmyk_profile(tmp_path / "rgb.icc", space=b"RGB ",
                                      cls=b"mntr", desc=b"Mock Monitor")
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=rgb):
            identity = describe_profile()
        assert identity.validation_result == "NOT_CMYK"
        assert identity.colour_space == "RGB"
        assert identity.valid is False

    def test_non_output_class_profile_is_refused(self, tmp_path):
        from apps.dielines.exporters.output_intent import describe_profile
        path = self._mock_cmyk_profile(tmp_path / "cmyk_mntr.icc", cls=b"mntr")
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=path):
            identity = describe_profile()
        assert identity.validation_result == "NOT_AN_OUTPUT_PROFILE"
        assert identity.valid is False

    def test_valid_mocked_cmyk_profile_passes_identity_validation(self, tmp_path):
        from apps.dielines.exporters.output_intent import describe_profile
        path = self._mock_cmyk_profile(tmp_path / "press.icc")
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=path,
                               PRODUCTION_OUTPUT_CONDITION="FOGRA51"):
            identity = describe_profile()
        assert identity.valid is True
        assert identity.validation_result == "VALID_CMYK_OUTPUT_PROFILE"
        assert identity.colour_space == "CMYK" and identity.components == 4
        assert identity.device_class == "output (printer)"
        assert identity.description == "Mock Press"
        assert identity.profile_version == "2.2"
        assert len(identity.sha256) == 64
        assert identity.output_condition == "FOGRA51"

    def test_mocked_profile_attaches_and_satisfies_the_validator(
            self, tmp_path, media_root):
        pytest.importorskip("fitz")
        path = self._mock_cmyk_profile(tmp_path / "press.icc")
        pdf = str(tmp_path / "withicc.pdf")
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=path,
                               PRODUCTION_OUTPUT_CONDITION="FOGRA51"):
            _real_production_pdf(pdf)
            out = _output(tmp_path, media_root, checklist=_checklist(),
                          inventory=_inventory(), pdf_path=pdf)
            report = _evaluate(out)
        assert "MISSING_OUTPUT_INTENT" not in report.codes()
        assert "INVALID_OUTPUT_INTENT_PROFILE" not in report.codes()
        assert report.output_intent["valid"] is True
        assert report.output_intent["sha256"]

    def test_missing_icc_blocks_gate_2_and_marks_preview_only(
            self, tmp_path, media_root):
        pytest.importorskip("fitz")
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory())
        report = _evaluate(out)
        assert "MISSING_OUTPUT_INTENT" in report.codes()
        failure = next(f for f in report.failures
                       if f["code"] == "MISSING_OUTPUT_INTENT")
        assert "PREVIEW_ONLY_NO_OUTPUT_INTENT" in failure["detail"]
        assert failure["icc_validation"] == "NOT_CONFIGURED"
        assert report.output_intent["configured"] is False

    def test_identity_is_published_in_the_report(self, tmp_path, media_root):
        out = _output(tmp_path, media_root, checklist=_checklist(),
                      inventory=_inventory())
        payload = _evaluate(out).to_dict()["output_intent"]
        for key in ("configured", "path", "sha256", "description",
                    "colour_space", "device_class", "profile_version",
                    "valid", "validation_result"):
            assert key in payload, f"missing ICC identity field {key}"

    @pytest.mark.skipif(not os.path.exists(_SYSTEM_CMYK),
                        reason="no system CMYK ICC profile available")
    def test_real_system_cmyk_profile_validates(self):
        from apps.dielines.exporters.output_intent import describe_profile
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=self._SYSTEM_CMYK):
            identity = describe_profile()
        assert identity.valid is True
        assert identity.colour_space == "CMYK"

    @pytest.mark.skipif(not os.path.exists(_SYSTEM_RGB),
                        reason="no system RGB ICC profile available")
    def test_real_system_rgb_profile_is_refused(self):
        from apps.dielines.exporters.output_intent import describe_profile
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=self._SYSTEM_RGB):
            identity = describe_profile()
        assert identity.valid is False
        assert identity.validation_result == "NOT_CMYK"
