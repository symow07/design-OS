"""DIP-0B2 — clustering, candidates, workspace, review JSON, determinism."""
from __future__ import annotations

import json

import fitz
import numpy as np
import pytest

from tools.dip0 import integrity as I
from tools.dip0b import config as C
from tools.dip0b.cluster import (
    build_grid,
    clip_rect,
    cluster_rects,
    containment,
    iou,
    label_components,
)
from tools.dip0b.limits import Budget, Limits
from tools.dip0b.regions import (
    CANDIDATE_TYPES,
    DEFAULT_THRESHOLDS,
    SEGMENTATION_STATUS,
    SegThresholds,
    detect_tables,
    segment_page,
)
from tools.dip0b.review import (
    OPERATIONS,
    ReviewError,
    apply_operation,
    build_review,
    validate_review,
)
from tools.dip0b.tests.conftest import pilot_path


def _seg(path, page=0, th=DEFAULT_THRESHOLDS, limits=None):
    doc = fitz.open(path)
    try:
        return segment_page(doc, doc[page], page, str(path), Budget(limits or Limits()), th)
    finally:
        doc.close()


# --------------------------------------------------------------------------
class TestConnectedComponents:
    def test_two_disjoint_blobs(self):
        m = np.zeros((10, 20), dtype=bool)
        m[2:5, 2:5] = True
        m[6:9, 14:18] = True
        lab, n = label_components(m)
        assert n == 2
        assert lab[3, 3] != lab[7, 15]

    def test_l_shape_is_one_component(self):
        m = np.zeros((10, 10), dtype=bool)
        m[1:8, 1:3] = True
        m[6:8, 1:9] = True
        _, n = label_components(m)
        assert n == 1

    def test_empty_mask(self):
        _, n = label_components(np.zeros((5, 5), dtype=bool))
        assert n == 0

    def test_labels_are_deterministic(self):
        m = np.zeros((8, 8), dtype=bool)
        m[1:3, 1:3] = True
        m[5:7, 5:7] = True
        a, _ = label_components(m.copy())
        b, _ = label_components(m.copy())
        assert (a == b).all()


class TestClusterRects:
    def test_gap_merges_and_separates(self):
        grid = build_grid((0, 0, 100, 100), 200, 100_000)
        rects = [(0, 0, 10, 10), (12, 0, 22, 10), (80, 80, 90, 90)]
        groups = cluster_rects(rects, gap_pt=6.0, grid=grid)
        assert len(groups) == 2
        assert sorted(len(g) for g in groups) == [1, 2]

    def test_zero_gap_keeps_touching_rects_together(self):
        grid = build_grid((0, 0, 100, 100), 200, 100_000)
        groups = cluster_rects([(0, 0, 10, 10), (10, 0, 20, 10)], 1.0, grid)
        assert len(groups) == 1

    def test_degenerate_hairline_still_clusters(self):
        """A zero-height rule is real geometry and must paint at least a pixel."""
        grid = build_grid((0, 0, 100, 100), 200, 100_000)
        groups = cluster_rects([(10, 50, 60, 50)], 2.0, grid)
        assert groups == [[0]]

    def test_deterministic(self):
        grid = build_grid((0, 0, 200, 200), 400, 200_000)
        rects = [(i * 7 % 150, i * 11 % 150, i * 7 % 150 + 5, i * 11 % 150 + 5)
                 for i in range(60)]
        assert cluster_rects(rects, 4.0, grid) == cluster_rects(rects, 4.0, grid)


class TestGeometryHelpers:
    def test_clip_rect_allows_degenerate_intersection(self):
        # regression: 95 in-ArtBox hairlines were pushed off-canvas
        assert clip_rect((10, 50, 60, 50), (0, 0, 100, 100)) == (10, 50, 60, 50)
        assert clip_rect((10, 10, 10, 90), (0, 0, 100, 100)) == (10, 10, 10, 90)

    def test_clip_rect_none_only_when_disjoint(self):
        assert clip_rect((200, 200, 210, 210), (0, 0, 100, 100)) is None
        assert clip_rect((-5, -5, 5, 5), (0, 0, 100, 100)) == (0, 0, 5, 5)

    def test_iou_and_containment(self):
        assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
        assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
        assert containment((2, 2, 4, 4), (0, 0, 10, 10)) == 1.0
        assert containment((0, 0, 10, 10), (2, 2, 4, 4)) == pytest.approx(0.04)


# --------------------------------------------------------------------------
class TestTableDetection:
    def _paths(self, rects, fill=(1, 1, 1)):
        from tools.dip0b.cluster import area as _a
        return [{"rect": r, "area": _a(r), "type": "fs", "fill": fill,
                 "background": False, "structural": False, "glyph": False,
                 "width": 0.5, "stroke": (0, 0, 0), "dashed": False, "seqno": i}
                for i, r in enumerate(rects)]

    def test_finds_a_real_lattice(self):
        rects = [(c * 60, r * 30, c * 60 + 50, r * 30 + 25)
                 for r in range(4) for c in range(3)]      # 4 rows x 3 cols
        grids = detect_tables(self._paths(rects), DEFAULT_THRESHOLDS)
        assert len(grids) == 1
        assert len(grids[0]["idxs"]) == 12
        assert grids[0]["rows"] == 4 and grids[0]["cols"] == 3

    def test_rejects_scattered_equal_rects(self):
        """FL-3098: 4,913 scattered artwork rects were once called a 17x41 grid."""
        rng = np.random.RandomState(0)
        rects = []
        for _ in range(300):
            x, y = rng.randint(0, 4000), rng.randint(0, 2000)
            rects.append((x, y, x + 50, y + 25))
        assert detect_tables(self._paths(rects), DEFAULT_THRESHOLDS) == []

    def test_rejects_too_many_cells(self):
        rects = [(c * 60, r * 30, c * 60 + 50, r * 30 + 25)
                 for r in range(30) for c in range(30)]     # 900 > table_max_cells
        assert detect_tables(self._paths(rects), DEFAULT_THRESHOLDS) == []

    def test_rejects_overlapping_cells(self):
        rects = [(c * 5, r * 5, c * 5 + 50, r * 5 + 25)     # heavy overlap
                 for r in range(4) for c in range(3)]
        assert detect_tables(self._paths(rects), DEFAULT_THRESHOLDS) == []

    def test_rejects_many_fill_colours(self):
        rects = [(c * 60, r * 30, c * 60 + 50, r * 30 + 25)
                 for r in range(4) for c in range(3)]
        paths = self._paths(rects)
        for i, p in enumerate(paths):
            p["fill"] = (i / 12.0, 0, 0)
        assert detect_tables(paths, DEFAULT_THRESHOLDS) == []


# --------------------------------------------------------------------------
class TestSegmentationSynthetic:
    def test_empty_page(self, empty_pdf):
        seg = _seg(empty_pdf)
        assert seg["segmentation"]["candidate_count"] == 0
        assert seg["segmentation"]["status"] == "MANUAL_REQUIRED" or \
            seg["segmentation"]["status"] in SEGMENTATION_STATUS
        assert seg["page_geometry"]["unassigned_paths"] == 0

    def test_full_bleed_single_candidate_is_manual_required(self, tmp_path):
        doc = fitz.open()
        page = doc.new_page(width=400, height=300)
        for i in range(12):                     # one tight blob = one candidate
            page.draw_rect(fitz.Rect(50 + i * 5, 50, 55 + i * 5, 250),
                           color=None, fill=(0.2, 0.3, 0.4))
        p = tmp_path / "fullbleed.pdf"
        doc.save(p)
        doc.close()
        seg = _seg(p)
        assert seg["segmentation"]["candidate_count"] == 1
        assert "full_bleed_single_candidate" in seg["segmentation"]["failure_indicators"]
        assert seg["segmentation"]["status"] == "MANUAL_REQUIRED"

    def test_never_forces_a_full_bleed_page_apart(self, tmp_path):
        doc = fitz.open()
        page = doc.new_page(width=300, height=300)
        page.draw_rect(fitz.Rect(10, 10, 290, 290), color=None, fill=(0.9, 0.1, 0.1))
        p = tmp_path / "bleed.pdf"
        doc.save(p)
        doc.close()
        seg = _seg(p)
        assert seg["segmentation"]["candidate_count"] <= 1
        assert "never forced apart" in seg["segmentation"]["note"] or \
            "never forced apart" in seg["segmentation"]["note"].replace("is ", "")

    def test_raster_becomes_a_product_photo_candidate(self, tmp_path):
        doc = fitz.open()
        page = doc.new_page(width=400, height=300)
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 30))
        pix.set_rect(pix.irect, (200, 40, 60))
        page.insert_image(fitz.Rect(20, 20, 120, 95), pixmap=pix)
        p = tmp_path / "img.pdf"
        doc.save(p)
        doc.close()
        seg = _seg(p)
        types = [c["candidate_type"]["value"] for c in seg["candidates"]]
        assert "PRODUCT_PHOTO" in types
        photo = next(c for c in seg["candidates"]
                     if c["candidate_type"]["value"] == "PRODUCT_PHOTO")
        assert photo["raster_count"] == 1
        assert photo["bbox_pt"][0] == pytest.approx(20, abs=1)

    def test_dense_page_completes_and_loses_nothing(self, dense_pdf):
        seg = _seg(dense_pdf)
        g = seg["page_geometry"]
        assert g["paths_total"] == 300
        assert g["unassigned_paths"] + sum(c["path_count"] for c in seg["candidates"]) \
            + g["background_paths_suppressed"] + g["fully_off_canvas_paths"] >= 300


class TestStraddleAndWorkspace:
    def _pdf(self, tmp_path):
        doc = fitz.open()
        page = doc.new_page(width=400, height=300)
        doc.xref_set_key(page.xref, "ArtBox", "[100 100 300 200]")   # y-up
        # y-down artbox == (100, 100, 300, 200)
        for i in range(4):                                    # inside
            page.draw_rect(fitz.Rect(120 + i * 12, 120, 128 + i * 12, 140),
                           color=None, fill=(0, 0, 0))
        page.draw_rect(fitz.Rect(90, 130, 115, 150), color=None, fill=(1, 0, 0))   # straddles
        for i in range(4):                                    # fully off-canvas
            page.draw_rect(fitz.Rect(10 + i * 12, 250, 18 + i * 12, 270),
                           color=None, fill=(0, 0, 1))
        p = tmp_path / "straddle.pdf"
        doc.save(p)
        doc.close()
        return p

    def test_artbox_is_the_primary_surface(self, tmp_path):
        seg = _seg(self._pdf(tmp_path))
        assert seg["surface"] == "artbox"
        assert seg["artbox_pt"] == [100.0, 100.0, 300.0, 200.0]

    def test_straddler_uses_clipped_geometry_but_keeps_full_bbox(self, tmp_path):
        seg = _seg(self._pdf(tmp_path))
        assert seg["page_geometry"]["straddling_paths"] == 1
        # its clipped part joined a primary candidate; it is NOT in the workspace
        assert seg["page_geometry"]["fully_off_canvas_paths"] == 4

    def test_off_canvas_becomes_workspace_candidates(self, tmp_path):
        seg = _seg(self._pdf(tmp_path))
        ws = seg["workspace_candidates"]
        assert ws, "fully off-canvas geometry must cluster into workspace candidates"
        assert all(c["off_canvas"] is True for c in ws)
        assert all(c["unit_id"].split("-")[-1].startswith("w") for c in ws)

    def test_workspace_never_auto_included_in_memory(self, tmp_path):
        seg = _seg(self._pdf(tmp_path))
        for c in seg["workspace_candidates"]:
            assert c["include_in_historical_memory"] is None
            assert c["human_confirmed_type"] is None

    def test_no_object_is_duplicated_across_candidate_counts(self, tmp_path):
        seg = _seg(self._pdf(tmp_path))
        primary = sum(c["path_count"] for c in seg["candidates"])
        ws = sum(c["path_count"] for c in seg["workspace_candidates"])
        g = seg["page_geometry"]
        assert primary + g["unassigned_paths"] <= g["clustering_input_paths"]
        assert ws <= g["fully_off_canvas_paths"]


class TestProvenanceAndDeterminism:
    def test_candidate_ids_are_deterministic(self, tmp_path):
        p = TestStraddleAndWorkspace()._pdf(tmp_path)
        a, b = _seg(p), _seg(p)
        assert [c["unit_id"] for c in a["candidates"]] == \
               [c["unit_id"] for c in b["candidates"]]
        assert [c["bbox_pt"] for c in a["candidates"]] == \
               [c["bbox_pt"] for c in b["candidates"]]
        assert [c["candidate_type"]["value"] for c in a["candidates"]] == \
               [c["candidate_type"]["value"] for c in b["candidates"]]

    def test_provenance_records_algorithm_and_thresholds(self, tmp_path):
        seg = _seg(TestStraddleAndWorkspace()._pdf(tmp_path))
        pr = seg["provenance"]
        assert pr["algorithm_version"]
        assert pr["thresholds_fingerprint"]
        assert pr["thresholds"]["block_gap_frac"] == DEFAULT_THRESHOLDS.block_gap_frac

    def test_threshold_change_changes_the_fingerprint(self):
        a = DEFAULT_THRESHOLDS.fingerprint()
        b = SegThresholds(content_gap_pt=99.0).fingerprint()
        assert a != b

    def test_every_type_is_in_the_taxonomy(self, tmp_path):
        seg = _seg(TestStraddleAndWorkspace()._pdf(tmp_path))
        for c in seg["candidates"] + seg["workspace_candidates"]:
            assert c["candidate_type"]["value"] in CANDIDATE_TYPES
            assert c["candidate_type"]["tier"] == C.TIER_HEURISTIC
            assert c["human_confirmed_type"] is None       # machine never confirms


# --------------------------------------------------------------------------
class TestReviewJson:
    def _review(self, tmp_path):
        return build_review(_seg(TestStraddleAndWorkspace()._pdf(tmp_path)))

    def test_supports_every_mandated_operation(self):
        for op in ("accept", "relabel", "split_by_bbox", "merge", "exclude",
                   "identify_primary_artwork", "identify_dieline",
                   "include_workspace", "exclude_workspace", "mark_manual", "note"):
            assert op in OPERATIONS

    def test_human_fields_start_empty(self, tmp_path):
        r = self._review(tmp_path)
        for c in r["candidates"] + r["workspace_candidates"]:
            h = c["human"]
            assert h["confirmed_type"] is None and h["disposition"] == "pending"
            assert h["is_primary_artwork"] is None and h["is_dieline"] is None
        assert r["reviewer"] is None and r["reviewed_at"] is None
        assert validate_review(r) == []

    def test_machine_inference_preserved_after_relabel(self, tmp_path):
        r = self._review(tmp_path)
        uid = r["candidates"][0]["unit_id"]
        before = json.dumps(r["candidates"][0]["machine"], sort_keys=True)
        r2 = apply_operation(r, {"op": "relabel", "unit_id": uid,
                                 "candidate_type": "MOCKUP",
                                 "reason": "reviewer knows better"}, "designer")
        c = next(c for c in r2["candidates"] if c["unit_id"] == uid)
        assert json.dumps(c["machine"], sort_keys=True) == before   # untouched
        assert c["human"]["confirmed_type"] == "MOCKUP"
        assert c["human"]["disposition"] == "relabelled"
        assert c["human"]["correction_reason"] == "reviewer knows better"

    def test_relabel_rejects_unknown_type(self, tmp_path):
        r = self._review(tmp_path)
        with pytest.raises(ReviewError):
            apply_operation(r, {"op": "relabel", "unit_id": r["candidates"][0]["unit_id"],
                                "candidate_type": "NOT_A_TYPE"}, "d")

    def test_split_records_children_without_touching_machine_bbox(self, tmp_path):
        r = self._review(tmp_path)
        uid = r["candidates"][0]["unit_id"]
        mbox = r["candidates"][0]["machine"]["bbox_pt"]
        r2 = apply_operation(r, {"op": "split_by_bbox", "unit_id": uid,
                                 "bboxes": [[0, 0, 10, 10], [10, 10, 20, 20]]}, "d")
        c = next(c for c in r2["candidates"] if c["unit_id"] == uid)
        assert c["machine"]["bbox_pt"] == mbox
        assert len(c["human"]["split_into"]) == 2
        assert c["human"]["disposition"] == "split"

    def test_split_rejects_degenerate_bbox(self, tmp_path):
        r = self._review(tmp_path)
        with pytest.raises(ReviewError):
            apply_operation(r, {"op": "split_by_bbox",
                                "unit_id": r["candidates"][0]["unit_id"],
                                "bboxes": [[0, 0, 0, 10], [1, 1, 2, 2]]}, "d")

    def test_merge_requires_two_and_same_surface(self, tmp_path):
        r = self._review(tmp_path)
        with pytest.raises(ReviewError):
            apply_operation(r, {"op": "merge", "unit_ids": [r["candidates"][0]["unit_id"]]}, "d")
        if r["workspace_candidates"]:
            with pytest.raises(ReviewError):
                apply_operation(r, {"op": "merge",
                                    "unit_ids": [r["candidates"][0]["unit_id"],
                                                 r["workspace_candidates"][0]["unit_id"]]}, "d")

    def test_include_workspace_only_applies_to_off_canvas(self, tmp_path):
        r = self._review(tmp_path)
        ws = r["workspace_candidates"][0]["unit_id"]
        r2 = apply_operation(r, {"op": "include_workspace", "unit_id": ws}, "d")
        c = next(c for c in r2["workspace_candidates"] if c["unit_id"] == ws)
        assert c["human"]["include_in_historical_memory"] is True
        with pytest.raises(ReviewError):
            apply_operation(r, {"op": "include_workspace",
                                "unit_id": r["candidates"][0]["unit_id"]}, "d")

    def test_identify_primary_artwork_and_dieline(self, tmp_path):
        r = self._review(tmp_path)
        uid = r["candidates"][0]["unit_id"]
        r = apply_operation(r, {"op": "identify_primary_artwork", "unit_id": uid}, "d")
        r = apply_operation(r, {"op": "identify_dieline", "unit_id": uid}, "d")
        c = next(c for c in r["candidates"] if c["unit_id"] == uid)
        assert c["human"]["is_primary_artwork"] is True
        assert c["human"]["is_dieline"] is True

    def test_mark_manual_sets_resolved_status(self, tmp_path):
        r = self._review(tmp_path)
        r2 = apply_operation(r, {"op": "mark_manual", "resolved": True}, "d")
        assert r2["segmentation"]["human_status"] == "MANUAL_RESOLVED"
        assert r2["segmentation"]["machine_status"] in SEGMENTATION_STATUS

    def test_operations_are_audited_with_reviewer_and_timestamp(self, tmp_path):
        r = self._review(tmp_path)
        r2 = apply_operation(r, {"op": "accept", "unit_id": r["candidates"][0]["unit_id"]},
                             "alice")
        op = r2["review_operations"][-1]
        assert op["op"] == "accept" and op["reviewer"] == "alice"
        assert op["at"].endswith("+00:00") and op["review_version"]
        assert r2["reviewer"] == "alice"

    def test_unknown_operation_and_unit_are_rejected(self, tmp_path):
        r = self._review(tmp_path)
        with pytest.raises(ReviewError):
            apply_operation(r, {"op": "delete_everything"}, "d")
        with pytest.raises(ReviewError):
            apply_operation(r, {"op": "accept", "unit_id": "nope"}, "d")

    def test_invalid_op_leaves_document_unmodified(self, tmp_path):
        r = self._review(tmp_path)
        before = json.dumps(r, sort_keys=True)
        with pytest.raises(ReviewError):
            apply_operation(r, {"op": "accept", "unit_id": "nope"}, "d")
        assert json.dumps(r, sort_keys=True) == before


# --------------------------------------------------------------------------
class TestRealPilotRegressions:
    def test_es3083_finds_the_blank_spec_table_and_photo(self, pilot_entries):
        e = next(x for x in pilot_entries if "ES3083" in x["relative_path"])
        seg = _seg(pilot_path(e))
        types = [c["candidate_type"]["value"] for c in seg["candidates"]]
        assert "SPEC_TABLE" in types
        assert "PRODUCT_PHOTO" in types
        assert types.count("LEGAL_TEXT") >= 1
        table = next(c for c in seg["candidates"]
                     if c["candidate_type"]["value"] == "SPEC_TABLE")
        assert table["table_cells"] == 24                 # measured: 8 rows x 3 cols
        assert table["raster_count"] == 0
        assert seg["segmentation"]["status"] == "AUTO_CONFIDENT"

    def test_es3083_has_no_off_canvas_geometry(self, pilot_entries):
        """Regression: 95 in-ArtBox hairlines were once classed off-canvas."""
        e = next(x for x in pilot_entries if "ES3083" in x["relative_path"])
        seg = _seg(pilot_path(e))
        assert seg["page_geometry"]["fully_off_canvas_paths"] == 0
        assert seg["workspace_candidates"] == []

    def test_yb_bb_full_bleed_is_manual_required(self, pilot_entries):
        e = next(x for x in pilot_entries if "YB-BB" in x["relative_path"])
        seg = _seg(pilot_path(e))
        s = seg["segmentation"]
        assert s["status"] == "MANUAL_REQUIRED"
        assert "content_cluster_collapse" in s["failure_indicators"]
        assert s["largest_candidate_path_share"] > 0.9

    def test_cjk_filename_segments(self, pilot_entries):
        e = next(x for x in pilot_entries if "HL5503" in x["relative_path"])
        seg = _seg(pilot_path(e))
        assert "高光液" in seg["file"]
        assert seg["segmentation"]["candidate_count"] > 0

    def test_second_artboard_is_segmented_separately(self, pilot_entries):
        e = next(x for x in pilot_entries if "YB-1035" in x["relative_path"])
        p0 = _seg(pilot_path(e), page=0)
        p1 = _seg(pilot_path(e), page=1)
        assert p0["artbox_pt"] != p1["artbox_pt"]
        assert all(c["page"] == 0 for c in p0["candidates"])
        assert all(c["page"] == 1 for c in p1["candidates"])
        assert p1["segmentation"]["status"] == "MANUAL_REQUIRED"

    def test_no_barcode_false_positive_on_outlined_type(self, pilot_entries):
        """5,102 outlined glyph stems once scored as a barcode."""
        for name in ("ES3083", "YB-BB"):
            e = next(x for x in pilot_entries if name in x["relative_path"])
            seg = _seg(pilot_path(e))
            for c in seg["candidates"]:
                if c["candidate_type"]["value"] == "BARCODE":
                    assert c["barcode_bars"] <= DEFAULT_THRESHOLDS.barcode_max_bars

    def test_reading_the_pilot_never_modifies_it(self, pilot_entries):
        e = pilot_entries[0]
        before = I.snapshot(pilot_path(e).parent)
        _seg(pilot_path(e))
        assert I.compare(before, I.snapshot(pilot_path(e).parent))["unchanged"]


class TestOutputSafety:
    def test_output_root_outside_source(self):
        assert I.no_output_under_source()["ok"] is True

    def test_review_write_refuses_source_root(self, tmp_path, monkeypatch):
        from tools.dip0b import review as R
        r = build_review(_seg(TestStraddleAndWorkspace()._pdf(tmp_path)))
        with pytest.raises(RuntimeError):
            R.write_review(r, out_dir=C.SOURCE_ROOT)


class TestDielineTerminology:
    """B2 detects regions CONTAINING structural signals. It must never present
    one as a confirmed dieline — that is B3's page-level question, and a human
    confirms it either way."""

    def test_taxonomy_uses_dieline_candidate_not_dieline(self):
        assert "DIELINE_CANDIDATE" in CANDIDATE_TYPES
        assert "DIELINE" not in CANDIDATE_TYPES

    def test_no_candidate_is_ever_typed_plain_dieline(self, pilot_entries):
        for e in pilot_entries:
            seg = _seg(pilot_path(e))
            for c in seg["candidates"] + seg["workspace_candidates"]:
                assert c["candidate_type"]["value"] != "DIELINE"

    def test_structural_dominance_yields_a_candidate_label(self, tmp_path):
        doc = fitz.open()
        # Big page so the panel outlines stay well under the 2 %-of-surface
        # background-suppression threshold.
        page = doc.new_page(width=1000, height=1000)
        for i in range(8):                       # thin no-fill strokes only
            page.draw_rect(fitz.Rect(100 + i * 3, 100 + i * 3,
                                     220 - i * 3, 220 - i * 3),
                           color=(0, 0, 0), width=0.7)
        p = tmp_path / "struct.pdf"
        doc.save(p)
        doc.close()
        seg = _seg(p)
        types = [c["candidate_type"]["value"] for c in seg["candidates"]]
        assert "DIELINE_CANDIDATE" in types
        c = next(c for c in seg["candidates"]
                 if c["candidate_type"]["value"] == "DIELINE_CANDIDATE")
        assert c["candidate_type"]["tier"] == C.TIER_HEURISTIC
        assert c["human_confirmed_type"] is None
        assert any("DIP-0B3" in e for e in c["candidate_type"]["evidence"])

    def test_relabel_accepts_the_new_name_and_rejects_the_old(self, tmp_path):
        r = build_review(_seg(TestStraddleAndWorkspace()._pdf(tmp_path)))
        uid = r["candidates"][0]["unit_id"]
        ok = apply_operation(r, {"op": "relabel", "unit_id": uid,
                                 "candidate_type": "DIELINE_CANDIDATE"}, "d")
        c = next(c for c in ok["candidates"] if c["unit_id"] == uid)
        assert c["human"]["confirmed_type"] == "DIELINE_CANDIDATE"
        with pytest.raises(ReviewError):
            apply_operation(r, {"op": "relabel", "unit_id": uid,
                                "candidate_type": "DIELINE"}, "d")
