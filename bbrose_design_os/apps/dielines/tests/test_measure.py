"""Dieline measurement tool (WS1, 2026-07-07).

The inference layer is anchored against the engine itself: a RawDrawing
built from calculate_dieline() coordinates must give back the very
constants the engine used (1.227 / 0.227 / 0.218 / 0.631, shoulder k) —
if it can't recover known geometry, it can't be trusted on factory files.
"""
from __future__ import annotations

import pytest

from apps.dielines.analysis.measure import (
    RawDrawing,
    Stroke,
    aggregate,
    census_strokes,
    classify_linework,
    infer_ste_measurements,
    measure_file,
)
from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.geometry.primitives import CubicSeg
from apps.dielines.validators.schema import DielineInputJSON


def _engine_drawing(width=40, depth=20, height=110) -> RawDrawing:
    """A synthetic factory file built from the engine's own output."""
    coords = calculate_dieline(DielineInputJSON(
        template="straight_tuck_end_carton", unit="mm",
        dimensions={"width_mm": width, "depth_mm": depth, "height_mm": height},
        print_settings={}, construction={},
        metadata={"product_name": "T", "product_type": "t"},
    ))
    cut = Stroke(color=(0.9, 0.0, 0.07), dashed=False, width=0.5)
    ext = list(coords.cut_polygon.exterior.coords)
    for a, b in zip(ext, ext[1:]):
        cut.lines.append((a, b))
    for prims in coords.component_paths.values():
        for seg in prims:
            if isinstance(seg, CubicSeg):
                cut.cubics.append((seg.p0, seg.c1, seg.c2, seg.p1))
    crease = Stroke(color=(0.9, 0.0, 0.07), dashed=True, width=0.4)
    for x1, y1, x2, y2 in coords.fold_lines:
        crease.lines.append(((x1, y1), (x2, y2)))
    return RawDrawing(strokes=[cut, crease])


class TestInferenceAnchor:
    """Recover the engine's own constants from its own geometry."""

    def test_recovers_engine_constants(self):
        lw = classify_linework(_engine_drawing())
        assert lw is not None
        result = infer_ste_measurements(lw)
        m = result["measurements"]
        assert not result["skip_reason"]
        assert m["W_mm"] == pytest.approx(40, abs=0.5)
        assert m["D_mm"] == pytest.approx(20, abs=0.8)
        assert m["glue_tab_mm"] == pytest.approx(10, abs=0.5)
        assert m["tuck_total_over_W"] == pytest.approx(1.227, abs=0.02)
        assert m["tuck_inset_over_W"] == pytest.approx(0.227, abs=0.02)
        assert m["dust_over_D"] == pytest.approx(0.631, abs=0.02)
        assert m["tuck_curve_over_W"] == pytest.approx(0.218, abs=0.02)
        assert m["shoulder_k_v"] == pytest.approx(0.5523, abs=0.05)
        assert result["confidence"] >= 0.8

    def test_solid_color_classification_without_dashes(self):
        """Factory files carry no dash patterns — long interior axis-aligned
        lines must classify as creases by geometry alone."""
        raw = _engine_drawing()
        for s in raw.strokes:
            s.dashed = False
        lw = classify_linework(raw)
        assert lw is not None
        result = infer_ste_measurements(lw)
        assert result["measurements"].get("tuck_total_over_W") == pytest.approx(
            1.227, abs=0.02)


class TestRobustness:
    def test_empty_drawing_returns_none(self):
        assert classify_linework(RawDrawing()) is None

    def test_artwork_only_strokes_skip(self):
        tiny = Stroke(color=(0, 0, 0), dashed=False, width=0.3,
                      lines=[((0, 0), (5, 5)), ((5, 5), (8, 2))])
        assert classify_linework(RawDrawing(strokes=[tiny])) is None

    def test_non_carton_flat_reports_reason(self):
        box = Stroke(color=(0, 0, 1), dashed=False, width=0.5)
        pts = [(0, 0), (100, 0), (100, 60), (0, 60), (0, 0)]
        for a, b in zip(pts, pts[1:]):
            box.lines.append((a, b))
        cross = Stroke(color=(0, 0, 1), dashed=True, width=0.4,
                       lines=[((50, 0), (50, 60))])
        lw = classify_linework(RawDrawing(strokes=[box, cross]))
        assert lw is not None
        result = infer_ste_measurements(lw)
        assert result["skip_reason"]                  # not enough folds

    def test_census_shape(self):
        c = census_strokes(_engine_drawing())
        assert c["strokes"] == 2 and c["dashed_strokes"] == 1

    def test_aggregate_medians(self):
        reports = [
            {"ok": True, "measurements": {"tuck_total_over_W": 1.22}},
            {"ok": True, "measurements": {"tuck_total_over_W": 1.24}},
            {"ok": False, "measurements": {}},
        ]
        s = aggregate(reports)
        assert s["files_measured"] == 2
        assert s["ratios"]["tuck_total_over_W"]["median"] == pytest.approx(1.23)
        assert s["ratios"]["tuck_total_over_W"]["engine_current"] == 1.227


class TestFitzSmoke:
    def test_extracts_from_generated_pdf(self, tmp_path):
        pytest.importorskip("fitz")
        from reportlab.lib.units import mm as MM
        from reportlab.pdfgen import canvas as rl_canvas

        from apps.dielines.analysis.measure import extract_vector_drawing

        p = tmp_path / "probe.pdf"
        c = rl_canvas.Canvas(str(p), pagesize=(100 * MM, 100 * MM))
        c.setStrokeColorRGB(0, 0, 1)
        c.rect(10 * MM, 10 * MM, 80 * MM, 60 * MM, stroke=1, fill=0)
        c.setStrokeColorRGB(1, 0, 0)
        c.setDash(3, 2)
        c.line(30 * MM, 10 * MM, 30 * MM, 70 * MM)
        c.showPage()
        c.save()

        raw = extract_vector_drawing(str(p))
        assert raw is not None and len(raw.strokes) >= 2
        colors = {s.color for s in raw.strokes}
        assert (0.0, 0.0, 1.0) in colors
        assert any(s.dashed for s in raw.strokes)
        # a stroked mm-space line should measure ~60mm
        red = next(s for s in raw.strokes if s.color == (1.0, 0.0, 0.0))
        (a, b) = red.lines[0]
        assert abs(abs(a[1] - b[1]) - 60) < 1.0

    def test_measure_file_never_raises_on_junk(self, tmp_path):
        pytest.importorskip("fitz")
        junk = tmp_path / "junk.ai"
        junk.write_bytes(b"not a pdf at all")
        report = measure_file(str(junk))
        assert report["ok"] is False and report["skip_reason"]
