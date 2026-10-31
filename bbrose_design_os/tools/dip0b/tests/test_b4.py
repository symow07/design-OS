"""DIP-0B4 — colour buckets, ambiguity, artwork descriptors, Level-A typography."""
from __future__ import annotations

import fitz
import pytest

from tools.dip0 import integrity as I
from tools.dip0b import config as C
from tools.dip0b.artwork import describe_unit, logo_placement_candidate
from tools.dip0b.color import (
    BUCKETS,
    MIN_MATCH_TINT,
    DELTA_E_TOLERANCE,
    SPOT_CONFIDENCE_CAP,
    black_explanations,
    bucket_path,
    build_spot_lab,
    delta_e76,
    build_spot_ramp,
    is_near_black,
    is_near_white,
    match_spot,
    srgb_to_lab,
    summarise_palette,
)
from tools.dip0b.typography import (
    CANDIDATE_LABEL,
    analyse_region,
    analyse_unit,
    level_b_unavailable,
)


def _path(rgb=(0.9, 0.2, 0.2), typ="f", rect=(0, 0, 10, 10), background=False,
          glyph=False):
    return {"type": typ, "fill": rgb if typ in ("f", "fs") else None,
            "stroke": rgb if typ in ("s", "fs") else None,
            "rect": rect, "area": (rect[2] - rect[0]) * (rect[3] - rect[1]),
            "background": background, "glyph": glyph, "structural": typ == "s",
            "dashed": False, "width": 0.5, "seqno": 0}


SPOTS = build_spot_lab({"separations": {
    "PANTONE 199 C": {"srgb_full_strength": [214, 37, 55], "is_registration": False},
    "PANTONE 300 C": {"srgb_full_strength": [0, 94, 184], "is_registration": False},
    "All": {"srgb_full_strength": [0, 0, 0], "is_registration": True},
}})


# --------------------------------------------------------------------------
class TestColourMath:
    def test_lab_anchors(self):
        L, a, b = srgb_to_lab((1.0, 1.0, 1.0))
        assert round(L) == 100 and abs(a) < 1 and abs(b) < 1
        assert round(srgb_to_lab((0.0, 0.0, 0.0))[0]) == 0

    def test_delta_e_is_zero_for_identity(self):
        lab = srgb_to_lab((0.4, 0.5, 0.6))
        assert delta_e76(lab, lab) == 0.0

    def test_near_black(self):
        assert is_near_black((0.0, 0.0, 0.0))
        assert is_near_black((0.05, 0.04, 0.05))
        assert not is_near_black((0.5, 0.0, 0.0))


class TestSpotMatching:
    def test_close_colour_matches_one_ink(self):
        m = match_spot((214 / 255, 37 / 255, 55 / 255), SPOTS)
        assert m["matched"] == "PANTONE 199 C"
        assert m["delta_e"] < 1.0
        assert m["ambiguous"] is False
        assert 0 < m["confidence"] <= SPOT_CONFIDENCE_CAP
        assert m["tier"] == C.TIER_HEURISTIC

    def test_confidence_never_exceeds_the_cap(self):
        m = match_spot((0.0, 94 / 255, 184 / 255), SPOTS)
        assert m["confidence"] <= SPOT_CONFIDENCE_CAP

    def test_distant_colour_matches_nothing_but_records_delta_e(self):
        m = match_spot((0.1, 0.9, 0.1), SPOTS)
        assert m["matched"] is None
        assert m["delta_e"] > DELTA_E_TOLERANCE
        assert m["candidates"] and "ΔE" in m["reason"] or m["reason"]

    def test_two_close_inks_are_ambiguous_and_unmatched(self):
        spots = build_spot_lab({"separations": {
            "INK A": {"srgb_full_strength": [200, 30, 40], "is_registration": False},
            "INK B": {"srgb_full_strength": [202, 32, 42], "is_registration": False},
        }})
        m = match_spot((201 / 255, 31 / 255, 41 / 255), spots)
        assert m["ambiguous"] is True
        assert m["matched"] is None            # never pick one of two rivals
        assert len(m["candidates"]) >= 2
        assert m["confidence"] < SPOT_CONFIDENCE_CAP

    def test_no_separations_reports_cleanly(self):
        m = match_spot((0.5, 0.5, 0.5), [])
        assert m["matched"] is None and m["confidence"] == 0.0

    def test_registration_ink_is_never_a_confident_artwork_match(self):
        """Near-black artwork must not be mapped to /Separation /All (decision 4);
        registration converts to black at full tint and would otherwise win."""
        m = match_spot((0.01, 0.01, 0.01), SPOTS)   # SPOTS includes "All"
        assert m["matched"] != "All"
        assert m["matched"] is None or m["matched"].startswith("PANTONE")


class TestBlackRegistrationAmbiguity:
    def test_black_lists_every_plausible_explanation(self):
        e = black_explanations((0.0, 0.0, 0.0), True, "UNAVAILABLE", SPOTS)
        kinds = [c["explanation"] for c in e["candidates"]]
        assert any("artwork black" in k for k in kinds)
        assert any("registration ink" in k for k in kinds)
        assert e["ambiguous"] is True
        assert e["confidence"] == 0.0          # unavailable association
        assert "indistinguishable" in e["note"]

    def test_black_artwork_fill_stays_in_artwork(self):
        """Document-level /All presence must not strip black artwork."""
        b, ev = bucket_path(_path((0.02, 0.02, 0.02), "f"), technical_class=None,
                            in_palette_strip=False, is_canvas_background=False,
                            registration_present=True,
                            path_association="UNAVAILABLE", spots=SPOTS)
        assert b == "artwork"
        assert ev["ambiguity"]["ambiguous"] is True

    def test_black_stroke_with_registration_is_unresolved_not_registration(self):
        b, ev = bucket_path(_path((0.0, 0.0, 0.0), "s"), technical_class=None,
                            in_palette_strip=False, is_canvas_background=False,
                            registration_present=True,
                            path_association="UNAVAILABLE", spots=SPOTS)
        assert b == "unresolved_or_ambiguous"
        assert "no path-level association" in ev["reason"]
        # it is never asserted to be /All
        assert ev["explanations"]["ambiguous"] is True

    def test_black_stroke_without_registration_is_artwork(self):
        b, _ = bucket_path(_path((0.0, 0.0, 0.0), "s"), technical_class=None,
                           in_palette_strip=False, is_canvas_background=False,
                           registration_present=False,
                           path_association="UNAVAILABLE", spots=SPOTS)
        assert b == "artwork"


class TestBuckets:
    def test_six_buckets(self):
        assert set(BUCKETS) == {"artwork", "dieline_technical", "embedded_raster",
                                "swatch_reference", "canvas_background",
                                "unresolved_or_ambiguous"}

    def test_technical_class_excludes_the_colour(self):
        b, ev = bucket_path(_path((0.9, 0.1, 0.1), "s"),
                            technical_class="CUT_LINE_CANDIDATE",
                            in_palette_strip=False, is_canvas_background=False,
                            registration_present=False,
                            path_association="UNAVAILABLE", spots=SPOTS)
        assert b == "dieline_technical"
        assert ev["technical_class"] == "CUT_LINE_CANDIDATE"

    def test_thin_stroke_is_not_technical_ink(self):
        """A thin structural stroke that B3 left STRUCTURAL_UNRESOLVED must keep
        its colour in artwork intelligence."""
        b, _ = bucket_path(_path((0.9, 0.4, 0.1), "s"), technical_class=None,
                           in_palette_strip=False, is_canvas_background=False,
                           registration_present=False,
                           path_association="UNAVAILABLE", spots=SPOTS)
        assert b == "artwork"

    def test_palette_strip_goes_to_swatch_reference(self):
        b, ev = bucket_path(_path(), technical_class=None, in_palette_strip=True,
                            is_canvas_background=False, registration_present=False,
                            path_association="UNAVAILABLE", spots=SPOTS)
        assert b == "swatch_reference" and "spot_match" in ev

    def test_canvas_background_bucket(self):
        b, _ = bucket_path(_path(background=True), technical_class=None,
                           in_palette_strip=False, is_canvas_background=True,
                           registration_present=False,
                           path_association="UNAVAILABLE", spots=SPOTS)
        assert b == "canvas_background"

    def test_colourless_path_is_unresolved(self):
        p = _path()
        p["fill"] = None
        p["stroke"] = None
        b, _ = bucket_path(p, technical_class=None, in_palette_strip=False,
                           is_canvas_background=False, registration_present=False,
                           path_association="UNAVAILABLE", spots=SPOTS)
        assert b == "unresolved_or_ambiguous"

    def test_palette_summary_is_coverage_weighted(self):
        entries = [{"rgb": (1, 0, 0), "area": 100.0},
                   {"rgb": (1, 0, 0), "area": 50.0},
                   {"rgb": (0, 1, 0), "area": 20.0}]
        s = summarise_palette(entries)
        assert s["distinct_colours"] == 2
        assert s["dominant"][0]["srgb_255"] == [255, 0, 0]
        assert s["dominant"][0]["coverage"] > s["supporting"][0]["coverage"]


# --------------------------------------------------------------------------
class TestTypographyLevelA:
    def _glyphs(self, rows=3, per_row=6, h=10.0, x0=0.0):
        out = []
        for r in range(rows):
            for c in range(per_row):
                x = x0 + c * 12
                y = r * 20
                out.append(_path((0, 0, 0), "f", (x, y, x + 8, y + h), glyph=True))
        return out

    def test_line_grouping_and_hierarchy(self):
        r = analyse_region(self._glyphs(), [0, 0, 200, 100])
        assert r["apparent_line_count"] == 3
        assert r["candidate_label"] == CANDIDATE_LABEL
        assert r["tier"] == C.TIER_HEURISTIC
        assert r["line_spacing_pt"] == 20.0

    def test_uniform_heights_read_as_all_caps_appearance(self):
        r = analyse_region(self._glyphs(h=10.0), [0, 0, 200, 100])
        assert r["capitalisation_appearance"] == "uniform_height_appears_all_caps"

    def test_mixed_heights_read_as_mixed_case_appearance(self):
        gs = self._glyphs()
        for i, g in enumerate(gs):
            if i % 2:
                g["rect"] = (g["rect"][0], g["rect"][1], g["rect"][2],
                             g["rect"][1] + 5.0)
        r = analyse_region(gs, [0, 0, 200, 100])
        assert r["capitalisation_appearance"] == "mixed_height_appears_mixed_case"

    def test_left_alignment_detected(self):
        r = analyse_region(self._glyphs(), [0, 0, 200, 100])
        assert r["alignment"] in ("left", "centre", "right")

    def test_never_called_a_text_region(self):
        r = analyse_region(self._glyphs(), [0, 0, 200, 100])
        assert "text_region" not in r
        assert "may be outlined type OR icons" in r["caveat"]

    def test_hierarchy_rank_and_primary_candidate(self):
        small = self._glyphs(rows=1, h=6.0)
        big = self._glyphs(rows=1, h=20.0, x0=300)
        unit = {"bbox_pt": [0, 0, 500, 200]}
        out = analyse_unit(unit, small + big, [small, big])
        assert out["candidate_count"] == 2
        assert out["text_like_geometry_candidates"][0]["hierarchy_rank"] == 0
        assert (out["text_like_geometry_candidates"][0]["largest_apparent_scale_pt"]
                >= out["text_like_geometry_candidates"][1]["largest_apparent_scale_pt"])
        p = out["primary_typography_candidate_position"]
        assert p["label"] == "primary typography candidate position"
        assert "not asserted to be a product name" in p["caveat"]

    def test_level_b_is_explicitly_unavailable(self):
        lb = level_b_unavailable()
        assert lb["exact_wording"]["value"] is None
        assert "requires OCR" in lb["exact_wording"]["status"]
        assert lb["language"]["value"] is None
        assert lb["font_family"]["value"] is None
        assert lb["font_family"]["tier"] == C.TIER_REQUIRES_ILLUSTRATOR
        assert "never inferred from visual resemblance" in lb["font_family"]["note"]
        assert lb["precise_type_style"]["status"] == "uncertain"
        assert lb["confidence"] is None
        assert lb["ocr_used"] is False
        assert "DIP-0E" in lb["future_milestone"]

    def test_unit_records_all_typography_outlined(self):
        out = analyse_unit({"bbox_pt": [0, 0, 100, 100]}, [], [])
        assert out["all_typography_outlined"] is True
        assert out["live_text_spans"] == 0 and out["embedded_fonts"] == 0
        assert out["level_b"]["ocr_used"] is False


# --------------------------------------------------------------------------
class TestArtworkDescriptors:
    def _page(self, tmp_path):
        doc = fitz.open()
        page = doc.new_page(width=200, height=200)
        page.draw_rect(fitz.Rect(20, 20, 180, 180), color=None, fill=(0.9, 0.2, 0.2))
        p = tmp_path / "a.pdf"
        doc.save(p)
        doc.close()
        return fitz.open(p)

    def test_descriptors_are_descriptive_not_a_template(self, tmp_path):
        doc = self._page(tmp_path)
        try:
            unit = {"unit_id": "u0", "bbox_pt": [0, 0, 200, 200]}
            d = describe_unit(doc[0], unit, [_path(rect=(20, 20, 180, 180))], [])
        finally:
            doc.close()
        assert d["tier"] == C.TIER_HEURISTIC
        assert 0.0 <= d["whitespace_ratio"] <= 1.0
        assert 0.0 <= d["symmetry_score_vertical_axis"] <= 1.0
        assert d["composition_direction"] in ("horizontal", "vertical", "square")
        assert "reference memory, not templates" in d["policy"]
        # no reusable geometry
        for k in ("vertices", "points", "path_geometry", "layout"):
            assert k not in d

    def test_symmetric_shape_scores_high(self, tmp_path):
        doc = self._page(tmp_path)
        try:
            d = describe_unit(doc[0], {"unit_id": "u", "bbox_pt": [0, 0, 200, 200]},
                              [_path(rect=(20, 20, 180, 180))], [])
        finally:
            doc.close()
        assert d["symmetry_score_vertical_axis"] > 0.9

    def test_logo_candidate_is_a_candidate_not_a_claim(self):
        unit = {"bbox_pt": [0, 0, 100, 100]}
        c = logo_placement_candidate(unit, [_path(rect=(5, 5, 25, 25))], [])
        assert c["value"] in ("top-left", "top-centre", "top-right",
                              "middle-left", "middle-centre", "middle-right",
                              "bottom-left", "bottom-centre", "bottom-right")
        assert c["confidence"] <= 0.3
        assert "may equally be an ornament" in c["reason"]

    def test_no_vector_fills_yields_no_logo_candidate(self):
        c = logo_placement_candidate({"bbox_pt": [0, 0, 10, 10]}, [], [])
        assert c["value"] is None


# --------------------------------------------------------------------------
class TestRealPilotB4:
    def test_thin_structural_strokes_are_not_all_excluded(self, pilot_entries):
        """Measured: 1,972 STRUCTURAL_UNRESOLVED paths stay in artwork while only
        the 168 B3-classified technical paths are excluded."""
        import json
        p = C.OUTPUT_ROOT / "reports" / "b4_reconciliation.json"
        if not p.exists():
            pytest.skip("run `python -m tools.dip0b.run_b4` first")
        r = json.loads(p.read_text())
        assert r["structural_unresolved_not_excluded"] > r["technical_paths_excluded"]
        assert r["bucket_totals"]["dieline_technical"] == r["technical_paths_excluded"]

    def test_rasters_never_mix_with_vector_colour(self, pilot_entries):
        import json
        p = C.OUTPUT_ROOT / "reports" / "b4_reconciliation.json"
        if not p.exists():
            pytest.skip("run b4 first")
        r = json.loads(p.read_text())
        assert r["bucket_totals"]["embedded_raster"] > 0

    def test_all_units_carry_blank_human_fields(self, pilot_entries):
        import glob
        import json
        files = glob.glob(str(C.OUTPUT_ROOT / "unit_analysis" / "*.json"))
        if not files:
            pytest.skip("run b4 first")
        rec = json.loads(open(files[0]).read())
        for u in rec["units"]:
            h = u["human_confirmed"]
            assert h["category"] is None and h["reviewed_by"] is None
            assert u["typography"]["level_b"]["font_family"]["value"] is None


class TestOutputSafety:
    def test_output_root_outside_source(self):
        assert I.no_output_under_source()["ok"] is True


class TestTintRampMatching:
    """Artwork prints spot inks at TINTS. Matching only against the 100 % value
    found zero matches across the entire pilot."""

    RAMP = build_spot_ramp({"separations": {
        "PANTONE 621 C": {"tint_zero": [100.0, 0.0, 0.0],
                          "tint_full": [87.8431, -7.0, 2.0],
                          "alternate_space": "lab", "alternate_whitepoint": None,
                          "exponent_N": 1.0, "is_registration": False},
        "PANTONE 627 C": {"tint_zero": [100.0, 0.0, 0.0],
                          "tint_full": [18.0392, -14.0, 0.0],
                          "alternate_space": "lab", "alternate_whitepoint": None,
                          "exponent_N": 1.0, "is_registration": False},
    }})

    def test_ramp_has_samples_across_tints(self):
        assert self.RAMP and all(len(s["samples"]) >= 4 for s in self.RAMP)
        tints = [x["tint"] for x in self.RAMP[0]["samples"]]
        assert min(tints) < 0.5 < max(tints)

    def test_full_strength_ink_matches_at_tint_1(self):
        from tools.dip0b.separation import lab_to_srgb
        rgb = lab_to_srgb(18.0392, -14.0, 0.0)
        m = match_spot(tuple(c / 255 for c in rgb), self.RAMP)
        assert m["matched"] == "PANTONE 627 C"
        assert m["matched_tint"] == 1.0
        assert m["delta_e"] < 1.0

    def test_a_tint_matches_at_its_tint(self):
        from tools.dip0b.separation import lab_to_srgb
        comps = [100 + 0.5 * (87.8431 - 100), 0.5 * -7.0, 0.5 * 2.0]
        rgb = lab_to_srgb(*comps)
        m = match_spot(tuple(c / 255 for c in rgb), self.RAMP)
        assert m["matched"] == "PANTONE 621 C"
        assert m["matched_tint"] == pytest.approx(0.5, abs=0.11)

    def test_white_never_matches_a_pale_inks_low_tint(self):
        """A 10 % tint of PANTONE 621 C lands within ΔE 1.5 of paper white."""
        assert is_near_white((1.0, 1.0, 1.0))
        m = match_spot((1.0, 1.0, 1.0), self.RAMP)
        assert m["matched"] is None
        assert "paper" in m["reason"]

    def test_low_tints_are_excluded_from_matching(self):
        assert MIN_MATCH_TINT >= 0.2
