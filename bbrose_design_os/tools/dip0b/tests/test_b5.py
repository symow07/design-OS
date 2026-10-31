"""DIP-0B5 — manifest, batching, priority, recommendations, reports."""
from __future__ import annotations

import copy
import json

import pytest

from tools.dip0b import manifest as M
from tools.dip0b import reports_b5 as RB


def _unit(uid="f-p0-u00", ctype="SURFACE_ARTWORK", *, dominant=True,
          off_canvas=False, seg="AUTO_CONFIDENT", dieline="LIKELY_DIELINE_STRUCTURE",
          named=0, ambiguous=0, unattributed=0, flagged_black=0,
          dom_ambiguous=False, typo=0, overlaps=False):
    dom = [{"srgb_255": [200, 50, 50], "coverage": 0.6,
            "spot_match": {"ambiguous": dom_ambiguous}}] if dominant else []
    return {
        "file": "materials/historical AI production designs/F.ai", "page": 0,
        "unit_id": uid, "candidate_type": ctype, "bbox_pt": [0, 0, 100, 100],
        "palette": {"artwork": {"dominant": dom, "supporting": [],
                                "distinct_colours": 1 if dominant else 0},
                    "technical_excluded": 0, "unresolved_or_ambiguous": 0},
        "descriptors": {"hierarchy_zones": {"top": 0.3, "middle": 0.4, "bottom": 0.3},
                        "decoration_density_paths_per_cm2": 12.0,
                        "whitespace_ratio": 0.5, "symmetry_score_vertical_axis": 0.7,
                        "image_vector_balance": {"raster_area_fraction": 0.0,
                                                 "vector_paths": 10, "rasters": 0}},
        "typography": {"candidate_count": typo, "all_typography_outlined": True,
                       "text_like_geometry_candidates": [
                           {"alignment": "left"} for _ in range(min(typo, 3))]},
        "_colour": {"named_ink_matched": named, "named_ink_ambiguous": ambiguous,
                    "unattributed": unattributed, "flagged_black_paths": flagged_black,
                    "ambiguous_colours": ambiguous, "ambiguous_paths": flagged_black,
                    "dominant_ambiguous_families": [], "raster_colours": 0},
        "_candidate_confidence": 0.4, "_segmentation_status": seg,
        "_dieline_outcome": dieline, "_dieline_score": 0.5,
        "_dieline_overlaps": overlaps, "_off_canvas": off_canvas,
        "_proposed_for_inclusion": False, "_alternate_version": False,
        "_vector_count": 10, "_raster_count": 0, "_preview_crop": None,
        "_provenance": {"b5_version": "b5-0.1.0"},
        "_typo_band": "none", "_deco_band": "medium",
    }


# --------------------------------------------------------------------------
class TestRowSchema:
    def test_human_block_is_blank(self):
        row = M.build_row(_unit())
        for k in M.HUMAN_FIELDS:
            v = row["human"][k]
            assert v in (None, [], "")

    def test_machine_fields_present(self):
        row = M.build_row(_unit())
        for k in ("candidate_type", "segmentation_status", "dominant_artwork_colours",
                  "colour_classes", "colour_ambiguity", "review_priority",
                  "include_in_historical_memory_recommendation", "provenance"):
            assert k in row

    def test_review_never_overwrites_machine_inference(self):
        row = M.build_row(_unit())
        before = copy.deepcopy({k: row[k] for k in row if k != "human"})
        # simulate a reviewer populating the human block
        row["human"]["reviewer"] = "designer"
        row["human"]["include_in_historical_memory"] = True
        row["human"]["disposition"] = "accepted"
        after = {k: row[k] for k in row if k != "human"}
        assert after == before


class TestColourClasses:
    def test_six_states_kept_distinct(self):
        row = M.build_row(_unit(named=2, ambiguous=1, unattributed=3))
        c = row["colour_classes"]
        assert c["named_ink_matched"] == 2
        assert c["named_ink_ambiguous"] == 1
        assert c["present_but_unattributed"] == 3      # NOT a failed match
        assert set(c) == {"named_ink_matched", "named_ink_ambiguous",
                          "present_but_unattributed", "technical_colour",
                          "raster_only_colour", "unresolved_or_ambiguous"}

    def test_unattributed_is_not_a_failed_spot_match(self):
        row = M.build_row(_unit(unattributed=5, named=0))
        # unattributed colours are valid colour info, reported separately
        assert row["colour_classes"]["present_but_unattributed"] == 5
        assert row["colour_classes"]["named_ink_matched"] == 0

    def test_ambiguity_aggregated_at_unit_level(self):
        row = M.build_row(_unit(flagged_black=1200, dom_ambiguous=True))
        amb = row["colour_ambiguity"]
        assert amb["near_black_ambiguity_count"] == 1200
        assert amb["ambiguity_affects_dominant_palette"] is True
        assert amb["human_review_required"] is True
        # never a list of 1200 path records
        assert isinstance(amb["near_black_ambiguity_count"], int)


class TestFlaggedBlackVisibility:
    def test_flagged_black_shown_on_the_row(self):
        row = M.build_row(_unit(flagged_black=800))
        assert row["flagged_near_black_artwork"] == 800

    def test_flagged_black_not_hidden_by_small_unresolved_bucket(self):
        row = M.build_row(_unit(flagged_black=800))
        assert row["colour_classes"]["unresolved_or_ambiguous"] < row["flagged_near_black_artwork"]


class TestReviewPriority:
    def test_manual_required_is_high(self):
        _, reasons = M.review_priority(_unit(seg="MANUAL_REQUIRED"))
        assert any("MANUAL_REQUIRED" in r for r in reasons)
        assert M.review_priority(_unit(seg="MANUAL_REQUIRED"))[0] == "HIGH"

    def test_borderline_dieline_is_high(self):
        assert M.review_priority(
            _unit(dieline="BORDERLINE_REVIEW_REQUIRED"))[0] == "HIGH"

    def test_ambiguous_dominant_is_high(self):
        assert M.review_priority(_unit(dom_ambiguous=True, flagged_black=1))[0] == "HIGH"

    def test_no_dominant_artwork_colour_is_high(self):
        assert M.review_priority(_unit(dominant=False))[0] == "HIGH"

    def test_unnamed_process_colour_is_medium(self):
        p = M.review_priority(_unit(unattributed=4))
        assert p[0] == "MEDIUM"

    def test_exclusion_candidate_is_optional(self):
        assert M.review_priority(_unit(ctype="SPEC_TABLE"))[0] == "OPTIONAL"

    def test_high_confidence_unit_is_low(self):
        assert M.review_priority(_unit())[0] == "LOW"

    def test_every_priority_has_reasons(self):
        for u in (_unit(), _unit(seg="MANUAL_REQUIRED"), _unit(unattributed=4),
                  _unit(ctype="SPEC_TABLE")):
            _, reasons = M.review_priority(u)
            assert reasons


class TestRecommendation:
    def test_surface_artwork_recommends_include(self):
        assert M.include_recommendation(_unit())[0] == "RECOMMEND_INCLUDE"

    def test_spec_table_recommends_exclude(self):
        assert M.include_recommendation(_unit(ctype="SPEC_TABLE"))[0] == "RECOMMEND_EXCLUDE"

    def test_barcode_legal_dieline_notes_all_exclude(self):
        for t in ("BARCODE", "LEGAL_TEXT", "DIELINE_CANDIDATE", "TECHNICAL_NOTES"):
            assert M.include_recommendation(_unit(ctype=t))[0] == "RECOMMEND_EXCLUDE"

    def test_mixed_region_defaults_to_review(self):
        assert M.include_recommendation(
            _unit(ctype="SURFACE_ARTWORK", overlaps=True))[0] == "REVIEW_REQUIRED"

    def test_artwork_without_dominant_colour_is_review(self):
        assert M.include_recommendation(_unit(dominant=False))[0] == "REVIEW_REQUIRED"

    def test_recommendation_is_never_human_confirmation(self):
        row = M.build_row(_unit())
        assert row["include_in_historical_memory_recommendation"] in M.RECOMMENDATIONS
        # the human field for the actual decision is separate and blank
        assert row["human"]["include_in_historical_memory"] is None


class TestBatching:
    def _rows(self):
        units = [_unit(f"f-p0-u{i:02d}", "SPEC_TABLE", seg="MANUAL_REQUIRED")
                 for i in range(3)]
        units += [_unit(f"f-p0-v{i:02d}", "SURFACE_ARTWORK", dominant=False)
                  for i in range(2)]
        rows = []
        for u in units:
            row = M.build_row(u)
            row["_typo_band"] = u["_typo_band"]
            row["_deco_band"] = u["_deco_band"]
            rows.append(row)
        return rows

    def test_batches_group_by_shared_reason(self):
        b = M.build_batches(self._rows())
        assert b["total_groups"] >= 1
        assert all(g["units"] >= 1 for g in b["groups"])
        assert any(g["dimension"] == "candidate_type" for g in b["groups"])

    def test_batch_is_review_convenience_only(self):
        b = M.build_batches(self._rows())
        assert "never applied automatically" in b["note"]
        assert all("recommended_batch_action" in g for g in b["groups"])

    def test_batching_is_deterministic(self):
        a = M.build_batches(self._rows())
        b = M.build_batches(self._rows())
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


class TestScaleEstimate:
    def test_extrapolates_and_labels_estimates(self):
        rows = [M.build_row(_unit(f"f-p0-u{i}")) for i in range(10)]
        units = [_unit(f"f-p0-u{i}") for i in range(10)]
        for u in units:
            u["file"] = "materials/historical AI production designs/F.ai"
        est = RB.scale_estimate(rows, units)
        assert est["all_files"] == 91
        assert est["these_are_estimates"] is True
        assert est["estimated_units"] > len(rows)
        assert len(est["sample_bias"]) >= 3
        assert any("non-random" in s or "over-represented" in s
                   for s in est["sample_bias"])


class TestReports:
    def _recon(self):
        rows = [M.build_row(_unit(f"f-p0-u{i}", named=1)) for i in range(5)]
        units = [_unit(f"f-p0-u{i}") for i in range(5)]
        batches = M.build_batches(rows)
        return {
            "units": 173, "review_priority_totals": {"HIGH": 68, "MEDIUM": 91,
                                                     "LOW": 3, "OPTIONAL": 11},
            "recommendation_totals": {"RECOMMEND_INCLUDE": 50, "RECOMMEND_EXCLUDE": 84,
                                      "REVIEW_REQUIRED": 39},
            "unit_types": {"SURFACE_ARTWORK": 53}, "batch_group_totals": 15,
            "named_ink_matched": 127, "named_ink_ambiguous": 20,
            "present_but_unattributed": 308, "flagged_near_black_artwork_total": 23587,
            "scale_estimate": RB.scale_estimate(rows, units),
        }, rows, batches, units

    def test_audit_report_answers_all_questions(self):
        recon, rows, batches, units = self._recon()
        docs = RB.generate_all(rows, batches, recon, units)
        rpt = docs["historical_design_audit_report.md"]
        for i in range(1, 15):
            assert f"### {i}." in rpt, f"missing acceptance question {i}"

    def test_report_states_reference_memory_not_templates(self):
        recon, rows, batches, units = self._recon()
        rpt = RB.generate_all(rows, batches, recon, units)["historical_design_audit_report.md"]
        assert "reference memory, not templates" in rpt
        assert "No OCR was used" in rpt
        assert "No font-family claims were made" in rpt
        assert "No path-level registration association was falsely inferred" in rpt

    def test_all_seven_docs_generated(self):
        recon, rows, batches, units = self._recon()
        docs = RB.generate_all(rows, batches, recon, units)
        assert set(docs) == {"historical_design_audit_report.md",
                             "native_illustrator_requirements.md",
                             "recommendations_dip0c_dip1.md", "capability_matrix.md",
                             "known_limitations.md", "summary.md", "decisions.md"}

    def test_native_report_does_not_parse_private_data(self):
        recon, rows, batches, units = self._recon()
        n = RB.generate_all(rows, batches, recon, units)["native_illustrator_requirements.md"]
        assert "never parsed" in n and "/AIPrivateData" in n

    def test_dip1_recs_propose_all_required_entities(self):
        recon, rows, batches, units = self._recon()
        r = RB.generate_all(rows, batches, recon, units)["recommendations_dip0c_dip1.md"]
        for e in ("HistoricalDesign", "HistoricalDesignPage", "DesignUnit",
                  "TechnicalAudit", "PaletteObservation", "TypographyObservation",
                  "DielineObservation", "ReviewDecision", "ProvenanceRecord",
                  "SourceFile"):
            assert e in r
        assert "ownership" in r.lower()

    def test_reports_are_reproducible(self):
        recon, rows, batches, units = self._recon()
        a = RB.generate_all(rows, batches, recon, units)
        b = RB.generate_all(rows, batches, recon, units)
        assert a == b


class TestRealManifest:
    def test_row_count_equals_primary_unit_count(self):
        p = _find("manifest/review_manifest.json")
        if not p:
            pytest.skip("run `python -m tools.dip0b.run_b5` first")
        m = json.loads(p.read_text())
        assert m["unit_count"] == len(m["rows"])
        # 173 primary DesignUnitCandidates (the accepted authoritative count)
        assert m["unit_count"] == 173
        assert all(r["primary_or_off_canvas"] == "primary" for r in m["rows"])

    def test_off_canvas_kept_separate(self):
        p = _find("manifest/review_manifest.json")
        if not p:
            pytest.skip("run b5 first")
        m = json.loads(p.read_text())
        assert m["off_canvas_candidate_count"] == len(m["off_canvas_candidates"])
        assert all(r["primary_or_off_canvas"] == "off_canvas"
                   for r in m["off_canvas_candidates"])

    def test_every_manifest_row_has_blank_human_block(self):
        p = _find("manifest/review_manifest.json")
        if not p:
            pytest.skip("run b5 first")
        m = json.loads(p.read_text())
        for r in m["rows"]:
            assert r["human"]["reviewer"] is None
            assert r["human"]["include_in_historical_memory"] is None
            assert r["human"]["disposition"] is None

    def test_no_unit_is_reusable_by_default(self):
        p = _find("manifest/review_manifest.json")
        if not p:
            pytest.skip("run b5 first")
        m = json.loads(p.read_text())
        for r in m["rows"]:
            # a recommendation is not a decision; the decision stays blank
            assert r["human"]["include_in_historical_memory"] is None


def _find(rel):
    from tools.dip0b import config as C
    p = C.OUTPUT_ROOT / rel
    return p if p.exists() else None


class TestSourceIntegrity:
    def test_output_root_outside_source(self):
        from tools.dip0 import integrity as I
        assert I.no_output_under_source()["ok"] is True
