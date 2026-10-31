"""DIP-0B1 — coordinates, separations, guards, native-AI boundary, integrity."""
from __future__ import annotations

import fitz
import pytest

from tools.dip0 import integrity as I
from tools.dip0b import config as C
from tools.dip0b import report as R
from tools.dip0b.boxes import (
    build_boxes,
    classify_off_canvas,
    parse_raw_boxes,
    pdf_box_to_ydown,
    pt_to_mm,
)
from tools.dip0b.config import PilotScopeError, verify_pilot_path
from tools.dip0b.inspect import (
    inspect_ai_private,
    inspect_file,
    inspect_page,
    scan_xrefs,
)
from tools.dip0b.limits import Budget, Limits
from tools.dip0b.separation import (
    build_separation_table,
    cmyk_to_srgb,
    lab_to_srgb,
    unescape_pdf_name,
)
from tools.dip0b.tests.conftest import pilot_path


# --------------------------------------------------------------------------
class TestPilotScopeGuard:
    def test_accepts_historical_ai(self):
        verify_pilot_path("materials/historical AI production designs/LP-2018.ai")

    def test_refuses_stock_vector_or_logo(self):
        for bad in ("materials/DOWNLOADE 2026/floral/rose.eps",
                    "materials/DOWNLOADE 2026/office/LOGO6.ai",
                    "materials/Fonts/3333/Arial.ttf",
                    "materials/historical AI production designs/nested/x.ai"):
            with pytest.raises(PilotScopeError):
                verify_pilot_path(bad)

    def test_refuses_non_ai_in_historical_branch(self):
        with pytest.raises(PilotScopeError):
            verify_pilot_path("materials/historical AI production designs/note.txt")

    def test_inspect_file_enforces_the_guard(self):
        with pytest.raises(PilotScopeError):
            inspect_file("materials/DOWNLOADE 2026/office/LOGO6.ai")


# --------------------------------------------------------------------------
class TestCoordinates:
    def test_pt_mm_conversion(self):
        assert round(pt_to_mm(72.0), 6) == 25.4
        assert round(pt_to_mm(0.0), 6) == 0.0

    def test_y_flip_bottom_left_to_top_left(self):
        # page height 300; PDF box [20,30,380,260] (y-up) → y-down [20,40,380,270]
        assert pdf_box_to_ydown([20, 30, 380, 260], 300) == [20.0, 40.0, 380.0, 270.0]

    def test_y_flip_round_trips_through_its_inverse(self):
        h = 300.0
        box_yup = [10, 20, 100, 200]                       # llx, lly, urx, ury
        x0, y0, x1, y1 = pdf_box_to_ydown(box_yup, h)      # y-down
        # inverse: lly = h - y1, ury = h - y0
        assert [x0, h - y1, x1, h - y0] == [10.0, 20.0, 100.0, 200.0]

    def test_y_flip_preserves_height(self):
        x0, y0, x1, y1 = pdf_box_to_ydown([10, 20, 100, 200], 300.0)
        assert round(y1 - y0, 6) == 180.0 and round(x1 - x0, 6) == 90.0

    def test_parse_raw_boxes(self):
        raw = "<</Type/Page/ArtBox[1 2 3 4]/MediaBox[0 0 10 20]>>"
        b = parse_raw_boxes(raw)
        assert b["ArtBox"] == [1.0, 2.0, 3.0, 4.0]
        assert b["MediaBox"] == [0.0, 0.0, 10.0, 20.0]
        assert b["TrimBox"] is None

    def test_artbox_is_the_design_surface(self, simple_pdf):
        doc = fitz.open(simple_pdf)
        page = doc[0]
        b = build_boxes(page, doc.xref_object(page.xref, compressed=False))
        assert b["design_surface"] == "artbox"
        assert b["artbox"]["pt"] == [20.0, 40.0, 380.0, 270.0]   # y-down
        assert b["artbox"]["width_mm"] == round(pt_to_mm(360), 2)
        assert b["mediabox"] and b["trimbox"] and b["bleedbox"]
        doc.close()

    def test_page_rect_used_when_no_artbox(self, empty_pdf):
        doc = fitz.open(empty_pdf)
        page = doc[0]
        b = build_boxes(page, doc.xref_object(page.xref, compressed=False))
        assert b["design_surface"] == "page_rect"
        doc.close()


class TestOffCanvas:
    def test_detects_and_bounds_but_never_discards(self):
        surface = [20.0, 40.0, 380.0, 270.0]
        rects = [fitz.Rect(50, 60, 100, 100),      # inside
                 fitz.Rect(0, 0, 12, 12),           # fully outside
                 fitz.Rect(10, 50, 60, 90)]         # straddles the edge
        oc = classify_off_canvas(rects, surface)
        assert oc["fully_outside"] == 1
        assert oc["partially_outside"] == 1
        assert oc["total_off_canvas"] == 2
        assert oc["union_bounds_pt"] is not None
        assert "not discarded" in oc["policy"]

    def test_no_off_canvas_when_all_inside(self):
        oc = classify_off_canvas([fitz.Rect(30, 50, 100, 100)], [20, 40, 380, 270])
        assert oc["total_off_canvas"] == 0 and oc["union_bounds_pt"] is None


# --------------------------------------------------------------------------
class TestSeparation:
    def test_pdf_name_unescaping(self):
        assert unescape_pdf_name("PANTONE#20621#20C") == "PANTONE 621 C"
        assert unescape_pdf_name("All") == "All"
        assert unescape_pdf_name("PANTONE#20Yellow#200131#20C") == "PANTONE Yellow 0131 C"

    def test_lab_to_srgb_anchors(self):
        assert lab_to_srgb(100, 0, 0) == (255, 255, 255)
        assert lab_to_srgb(0, 0, 0) == (0, 0, 0)

    def test_lab_to_srgb_is_deterministic(self):
        assert lab_to_srgb(87.8431, -7, 2) == lab_to_srgb(87.8431, -7, 2)

    def test_lab_midgrey_is_neutral(self):
        r, g, b = lab_to_srgb(50, 0, 0)
        assert abs(r - g) <= 1 and abs(g - b) <= 1 and 110 < r < 130

    def test_cmyk_registration_is_black(self):
        assert cmyk_to_srgb(1, 1, 1, 1) == (0, 0, 0)
        assert cmyk_to_srgb(0, 0, 0, 0) == (255, 255, 255)

    def test_table_from_synthetic_separations(self, tmp_path):
        doc = fitz.open()
        doc.new_page()
        # a Lab-alternate PANTONE and the /All registration ink
        lab = doc.get_new_xref()
        doc.update_object(lab, "[/Lab <</WhitePoint[0.9642 1 0.8249]/Range[-128 127 -128 127]>>]")
        cmyk = doc.get_new_xref()
        doc.update_object(cmyk, "/DeviceCMYK")
        s1 = doc.get_new_xref()
        doc.update_object(s1, f"[/Separation/PANTONE#20621#20C {lab} 0 R "
                              "<</C0[100 0 0]/C1[87.8431 -7 2]/Domain[0 1]"
                              "/FunctionType 2/N 1>>]")
        s2 = doc.get_new_xref()
        doc.update_object(s2, f"[/Separation/All {cmyk} 0 R "
                              "<</C0[0 0 0 0]/C1[1 1 1 1]/Domain[0 1]"
                              "/FunctionType 2/N 1>>]")
        p = tmp_path / "sep.pdf"
        doc.save(p)
        doc.close()

        d = fitz.open(p)
        b = Budget(Limits())
        scan = scan_xrefs(d, b)
        t = build_separation_table(d, b, scan["raw_separations"], scan["devicen"])
        d.close()

        assert t["count"] == 2
        assert t["has_registration"] is True
        assert t["spot_names"] == ["PANTONE 621 C"]
        spot = t["separations"]["PANTONE 621 C"]
        assert spot["alternate_space"] == "lab"
        assert spot["is_registration"] is False
        assert spot["role"] == "spot_ink"
        assert spot["tier"] == "DIRECT"
        assert spot["srgb_full_strength"] == list(lab_to_srgb(87.8431, -7, 2))
        reg = t["separations"]["All"]
        assert reg["is_registration"] is True and reg["role"] == "registration"
        assert reg["alternate_space"] == "cmyk"


# --------------------------------------------------------------------------
class TestGuards:
    def test_budget_starts_clean(self):
        b = Budget(Limits())
        assert b.truncated is False and b.data_loss is False
        assert b.aggregates_complete is True and b.confidence_penalty() == 1.0

    def test_bounded_sample_does_not_reduce_confidence(self):
        """A bounded sample leaves aggregate statistics complete."""
        b = Budget(Limits())
        kept = b.sample(range(100), 10, "max_paths_detailed", "detailed_paths")
        assert len(kept) == 10
        assert b.truncated is True          # a limit WAS reached (recorded)
        assert b.data_loss is False         # ...but nothing was lost
        assert b.aggregates_complete is True
        assert b.confidence_penalty() == 1.0
        assert b.skipped["detailed_paths"] == 90
        assert "max_paths_detailed=10" in b.sampling_limits

    def test_sample_is_a_noop_under_the_limit(self):
        b = Budget(Limits())
        assert b.sample(range(5), 10, "x", "y") == list(range(5))
        assert b.truncated is False

    def test_data_loss_reduces_confidence(self):
        b = Budget(Limits(max_xref_scan=50))
        b.xref_scan_range(1000)
        assert b.data_loss is True and b.aggregates_complete is False
        assert b.confidence_penalty() < 1.0
        assert b.skipped["xref_objects"] == 950

    def test_xref_skip_counted_once_per_budget(self):
        """One logical sweep must not be counted three times (86,951 objects
        were once reported as 200,853 skipped)."""
        b = Budget(Limits(max_xref_scan=50))
        for _ in range(3):
            b.xref_scan_range(1000)
        assert b.skipped["xref_objects"] == 950
        assert b.data_loss_limits == ["max_xref_scan=50"]

    def test_render_zoom_never_upscales_and_caps_long_edge(self):
        assert Budget(Limits(max_render_px=100)).render_zoom(50, 20) == 1.0
        z = Budget(Limits(max_render_px=100)).render_zoom(1000, 500)
        assert 1000 * z <= 100 + 1e-6

    def test_preview_clamp_is_sampling_not_data_loss(self):
        b = Budget(Limits(max_render_px=100))
        b.render_zoom(1000, 500)
        assert b.truncated is True and b.data_loss is False
        assert b.confidence_penalty() == 1.0

    def test_mask_pixel_cap_shrinks_zoom(self):
        b = Budget(Limits(max_render_px=10_000, max_mask_pixels=10_000))
        z = b.render_zoom(1000, 1000)
        assert (1000 * z) * (1000 * z) <= 10_000 + 1

    def test_page_timeout_is_data_loss(self):
        b = Budget(Limits(max_page_seconds=-1.0))
        assert b.out_of_time() is True
        assert b.data_loss is True and b.confidence_penalty() < 1.0

    def test_confidence_penalty_floors_at_0_4(self):
        b = Budget(Limits())
        for i in range(20):
            b.hit(f"limit_{i}", i)          # default kind is data_loss
        assert b.confidence_penalty() == 0.4

    def test_guard_never_silently_omits(self, dense_pdf):
        doc = fitz.open(dense_pdf)
        b = Budget(Limits(max_paths_detailed=10))
        rec = inspect_page(doc, doc[0], 0, b)
        doc.close()
        assert rec["paths"]["total"] == 300          # aggregate keeps everything
        assert len(rec["paths"]["sample"]) == 10     # sample is bounded
        assert b.skipped["detailed_paths"] == 290
        assert b.aggregates_complete is True


# --------------------------------------------------------------------------
class TestNativeIllustratorBoundary:
    def test_absent_when_no_private_data(self, simple_pdf):
        doc = fitz.open(simple_pdf)
        ai = inspect_ai_private(scan_xrefs(doc, Budget(Limits())))
        doc.close()
        assert ai["present"] is False and ai["parsed"] is False
        assert ai["unavailable_capabilities"] == []

    def test_detected_but_never_parsed(self, tmp_path):
        doc = fitz.open()
        doc.new_page()
        x = doc.get_new_xref()
        doc.update_object(x, "<</AIMetaData 2 0 R/AIPrivateData1 3 0 R/Length 4096>>")
        p = tmp_path / "ai.pdf"
        doc.save(p)
        doc.close()

        d = fitz.open(p)
        ai = inspect_ai_private(scan_xrefs(d, Budget(Limits())))
        d.close()

        assert ai["present"] is True
        assert ai["container_objects"] >= 1
        assert ai["approx_declared_bytes"] >= 4096
        assert ai["parsed"] is False              # the boundary is not crossed
        caps = {c["capability"] for c in ai["unavailable_capabilities"]}
        assert "original_layer_names_and_nesting" in caps
        assert "live_text_objects_and_fonts" in caps
        for c in ai["unavailable_capabilities"]:
            assert c["tier"] == C.TIER_REQUIRES_ILLUSTRATOR
            assert c["value"] is None             # nothing inferred from the payload
            assert c["confidence"] == 0.0


# --------------------------------------------------------------------------
class TestPageRecord:
    def test_text_like_geometry_is_never_called_text(self, simple_pdf):
        doc = fitz.open(simple_pdf)
        rec = inspect_page(doc, doc[0], 0, Budget(Limits()))
        doc.close()
        t = rec["text_like_geometry"]
        assert t["candidate_label"] == "TEXT_LIKE_GEOMETRY_CANDIDATE"
        assert t["glyph_scale_fill_ratio"]["tier"] == C.TIER_HEURISTIC
        assert any("icons/ornaments" in e for e in t["glyph_scale_fill_ratio"]["evidence"])
        assert "text_regions" not in rec

    def test_structural_strokes_are_evidence_not_a_dieline_claim(self, simple_pdf):
        doc = fitz.open(simple_pdf)
        rec = inspect_page(doc, doc[0], 0, Budget(Limits()))
        doc.close()
        s = rec["structural_strokes"]
        assert s["thin_nofill_stroke_count"] >= 1
        assert "not a dieline claim" in s["evidence_for"]

    def test_live_text_recorded_as_direct(self, simple_pdf):
        doc = fitz.open(simple_pdf)
        rec = inspect_page(doc, doc[0], 0, Budget(Limits()))
        doc.close()
        assert rec["live_text"]["span_count"]["tier"] == C.TIER_DIRECT
        assert rec["live_text"]["all_typography_outlined"]["value"] is True

    def test_empty_page_does_not_crash(self, empty_pdf):
        doc = fitz.open(empty_pdf)
        rec = inspect_page(doc, doc[0], 0, Budget(Limits()))
        doc.close()
        assert rec["paths"]["total"] == 0
        assert rec["text_like_geometry"]["glyph_scale_fill_ratio"]["value"] == 0.0

    def test_off_canvas_reported_on_page(self, simple_pdf):
        doc = fitz.open(simple_pdf)
        rec = inspect_page(doc, doc[0], 0, Budget(Limits()))
        doc.close()
        assert rec["off_canvas"]["total_off_canvas"] >= 1

    def test_multipage_iterates_every_page(self, multipage_pdf):
        doc = fitz.open(multipage_pdf)
        recs = [inspect_page(doc, doc[i], i, Budget(Limits()))
                for i in range(doc.page_count)]
        doc.close()
        assert len(recs) == 2
        assert recs[1]["boxes"]["page_rect"]["width_pt"] > recs[0]["boxes"]["page_rect"]["width_pt"]


# --------------------------------------------------------------------------
class TestRequiresHuman:
    def test_level_b_fields_are_null_with_status(self, pilot_entries):
        rec = inspect_file(pilot_entries[0]["relative_path"],
                           Limits(max_xref_scan=2000, max_paths_detailed=20))
        rh = rec["requires_human"]
        assert rh["exact_wording"]["value"] is None
        assert "requires OCR" in rh["exact_wording"]["status"]
        assert rh["language"]["value"] is None
        assert rh["font_family"]["value"] is None
        assert rh["font_family"]["tier"] == C.TIER_REQUIRES_ILLUSTRATOR
        assert "never inferred from visual resemblance" in \
            " ".join(rh["font_family"]["evidence"])
        assert rh["type_style"]["status"] == "uncertain"
        for k in rh:
            assert rh[k]["confidence"] == 0.0


# --------------------------------------------------------------------------
class TestRealPilotRegressions:
    """Pinned to values measured during the DIP-0B probe. READ-ONLY."""

    def test_zero_live_text_across_the_entire_pilot(self, pilot_entries):
        total_spans = total_fonts = 0
        for e in pilot_entries:
            doc = fitz.open(pilot_path(e))
            for i in range(doc.page_count):
                td = doc[i].get_text("dict")
                total_spans += sum(len(line["spans"]) for b in td["blocks"]
                                   if b["type"] == 0 for line in b["lines"])
                total_fonts += len(doc.get_page_fonts(i))
            doc.close()
        assert total_spans == 0 and total_fonts == 0

    def test_yb1035_has_two_artboards_second_larger(self, pilot_entries):
        e = next(x for x in pilot_entries if "YB-1035" in x["relative_path"])
        doc = fitz.open(pilot_path(e))
        assert doc.page_count == 2
        assert doc[1].rect.get_area() > doc[0].rect.get_area()
        doc.close()

    def test_cjk_filename_inspects_and_reports_spots(self, pilot_entries):
        e = next(x for x in pilot_entries if "ES3083" in x["relative_path"])
        rec = inspect_file(e["relative_path"], Limits(max_paths_detailed=20))
        assert "吸塑" in rec["filename"]
        assert rec["separations"]["spot_names"] == ["PANTONE 621 C", "PANTONE 627 C"]
        assert rec["document"]["encrypted"] is False

    def test_registration_detected_where_present(self, pilot_entries):
        e = next(x for x in pilot_entries if "LP-2018" in x["relative_path"])
        rec = inspect_file(e["relative_path"], Limits(max_paths_detailed=5))
        assert rec["separations"]["has_registration"] is True
        assert rec["separations"]["separations"]["All"]["role"] == "registration"

    def test_ai_private_present_but_unparsed_on_a_real_file(self, pilot_entries):
        rec = inspect_file(pilot_entries[0]["relative_path"],
                           Limits(max_paths_detailed=5))
        ai = rec["ai_private_data"]
        assert ai["present"] is True and ai["parsed"] is False
        assert ai["container_objects"] >= 1

    def test_reading_the_pilot_never_modifies_it(self, pilot_entries):
        import os
        e = pilot_entries[0]
        p = pilot_path(e)
        before = os.stat(p)
        inspect_file(e["relative_path"], Limits(max_paths_detailed=5))
        after = os.stat(p)
        assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)


# --------------------------------------------------------------------------
class TestOutputSafety:
    def test_refuses_to_write_into_materials(self):
        with pytest.raises(RuntimeError):
            R._write_json(C.SOURCE_ROOT / "evil.json", {"x": 1})

    def test_output_root_is_outside_source(self):
        assert I.no_output_under_source()["ok"] is True

    def test_capability_matrix_declares_the_boundary(self):
        m = R.CAPABILITY_MATRIX
        assert "original_layer_names_and_nesting" in m[C.TIER_REQUIRES_ILLUSTRATOR]
        assert any("never inferred" in s or "unavailable" in s
                   for s in m[C.TIER_REQUIRES_HUMAN])
        assert any("TEXT_LIKE_GEOMETRY_CANDIDATE" in s for s in m[C.TIER_HEURISTIC])


class TestXrefSweepCompleteness:
    """`xref_object()` itself materializes objects from compressed object
    streams, inflating `xref_length` on later reads (19,548 -> 86,951). The
    declared table at open is the authoritative size; sweeping it is complete."""

    def test_declared_xref_length_covers_the_whole_pilot(self, pilot_entries):
        import fitz as _f
        from tools.dip0b.config import DEFAULT_LIMITS
        biggest = 0
        for e in pilot_entries:
            d = _f.open(pilot_path(e))
            biggest = max(biggest, d.xref_length())
            d.close()
        assert biggest <= DEFAULT_LIMITS.max_xref_scan, (
            f"pilot needs a larger max_xref_scan: {biggest}")

    def test_no_pilot_file_suffers_data_loss(self, pilot_entries):
        rec = inspect_file(
            next(x["relative_path"] for x in pilot_entries if "YB-1025" in x["relative_path"]),
            Limits(max_paths_detailed=5))
        assert rec["limits"]["data_loss"] is False
        assert rec["limits"]["aggregates_complete"] is True
        # the densest file still yields every separation and xobject
        assert rec["separations"]["count"] == 8
        assert rec["xobjects"]["transparency_groups"] == 9630

    def test_single_sweep_feeds_every_consumer(self, pilot_entries):
        """Separations, xobjects and the AI-private census come from ONE sweep."""
        import fitz as _f
        e = pilot_entries[0]
        d = _f.open(pilot_path(e))
        b = Budget(Limits())
        scan = scan_xrefs(d, b)
        d.close()
        assert set(scan) == {"raw_separations", "devicen", "xobjects", "ai"}
        assert b.skipped.get("xref_objects") is None    # nothing skipped, counted once
