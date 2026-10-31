"""DIP-0B3 — structural graph, registration precision, dieline evidence model."""
from __future__ import annotations

import fitz

from tools.dip0 import integrity as I
from tools.dip0b import config as C
from tools.dip0b.associate import associate, associate_all
from tools.dip0b.boxes import build_boxes
from tools.dip0b.contentstream import analyse_page
from tools.dip0b.dieline import (
    BORDERLINE,
    LIKELY_DIELINE,
    LINE_CLASSES,
    OUTCOMES,
    REJECTED,
    DielineConfig,
    build_dieline_candidate,
    classify_lines,
    evaluate_dieline,
)
from tools.dip0b.limits import Budget, Limits
from tools.dip0b.regions import segment_page
from tools.dip0b.structure import (
    Segment,
    build_graph,
    extract_segments,
    is_closed,
    shared_edges,
)
from tools.dip0b.tests.conftest import pilot_path


def _page(path, n=0):
    doc = fitz.open(path)
    page = doc[n]
    dr = [x for x in page.get_drawings(extended=True) if x["type"] in ("f", "s", "fs")]
    surface = tuple(build_boxes(page, doc.xref_object(page.xref, compressed=False))
                    ["design_surface_pt"])
    return doc, page, dr, surface


def _analyse(path, n=0):
    doc, page, dr, surface = _page(path, n)
    try:
        g = build_graph(dr, surface)
        cs = analyse_page(doc, page, len(dr))
        dl = build_dieline_candidate(g, surface, cs, "t", n)
        return g, cs, dl, surface
    finally:
        doc.close()


# --------------------------------------------------------------------------
# synthetic geometry


def _carton(tmp_path, dashed_folds=True, glue_flap=True):
    """A cut perimeter with two interior fold lines and a glue flap."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=400)
    # outer cut contour (closed rect)
    page.draw_rect(fitz.Rect(50, 50, 550, 350), color=(0, 0, 0), width=0.5)
    # two panels sharing edges with the contour
    page.draw_rect(fitz.Rect(50, 50, 216, 350), color=(0, 0, 0), width=0.5)
    page.draw_rect(fitz.Rect(216, 50, 383, 350), color=(0, 0, 0), width=0.5)
    page.draw_rect(fitz.Rect(383, 50, 550, 350), color=(0, 0, 0), width=0.5)
    if dashed_folds:
        for x in (216, 383):
            page.draw_line(fitz.Point(x, 50), fitz.Point(x, 350),
                           color=(0, 0, 0), width=0.5, dashes="[3 3] 0")
    if glue_flap:
        # small angled panel hanging off one edge
        page.draw_polyline([fitz.Point(550, 120), fitz.Point(585, 140),
                            fitz.Point(585, 260), fitz.Point(550, 280),
                            fitz.Point(550, 120)], color=(0, 0, 0), width=0.5)
    p = tmp_path / "carton.pdf"
    doc.save(p)
    doc.close()
    return p


def _decorative_border(tmp_path):
    """A single thin ornamental frame: no panels meet, nothing is a dieline."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=400)
    page.draw_rect(fitz.Rect(40, 40, 560, 360), color=(0.6, 0.2, 0.2), width=0.5)
    for i in range(30):                       # ornamental curls, non-orthogonal
        page.draw_bezier(fitz.Point(60 + i * 16, 60), fitz.Point(66 + i * 16, 40),
                         fitz.Point(74 + i * 16, 80), fitz.Point(80 + i * 16, 60),
                         color=(0.6, 0.2, 0.2), width=0.4)
    p = tmp_path / "border.pdf"
    doc.save(p)
    doc.close()
    return p


def _registration_pdf(tmp_path):
    """A page whose content stream provably aligns: two painting ops, both /All."""
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.draw_rect(fitz.Rect(10, 10, 20, 20))          # ensure a contents stream
    cs = doc.get_new_xref()
    doc.update_object(cs, "[/Separation/All /DeviceCMYK "
                          "<</C0[0 0 0 0]/C1[1 1 1 1]/Domain[0 1]"
                          "/FunctionType 2/N 1/Range[0 1 0 1 0 1 0 1]>>]")
    res = doc.xref_get_key(page.xref, "Resources")
    rx = int(res[1].split()[0]) if res[0] == "xref" else page.xref
    prefix = "" if res[0] == "xref" else "Resources/"
    doc.xref_set_key(rx, f"{prefix}ColorSpace", "<<>>")
    doc.xref_set_key(rx, f"{prefix}ColorSpace/CS0", f"{cs} 0 R")
    stream = (b"/CS0 cs 1 scn 20 20 40 40 re f\n"
              b"/CS0 CS 1 SCN 0.5 w 100 100 m 150 150 l S\n")
    doc.update_stream(page.get_contents()[0], stream)
    p = tmp_path / "reg.pdf"
    doc.save(p)
    doc.close()
    return p


# --------------------------------------------------------------------------
class TestStructuralGraph:
    def test_geometric_closure_not_the_closePath_flag(self, tmp_path):
        doc, page, dr, _ = _page(_carton(tmp_path))
        try:
            segs = extract_segments(dr)
            assert segs
            # MuPDF sets closePath=False on these; closure must be geometric
            rects = [d for d in dr if any(i[0] == "re" for i in d.get("items", []))]
            assert rects and is_closed(rects[0], extract_segments([rects[0]]))
        finally:
            doc.close()

    def test_carton_yields_panels_and_shared_edges(self, tmp_path):
        g, _, _, _ = _analyse(_carton(tmp_path))
        assert g["panel_count"] >= 4
        assert g["orthogonal_panel_count"] >= 4
        assert g["shared_edge_count"] >= 2, "adjacent panels must share edges"

    def test_shared_edge_needs_collinear_overlap(self):
        a = Segment(0, 0, 100, 0, 1, False, False, 0.5)
        b = Segment(20, 0, 80, 0, 2, False, False, 0.5)      # collinear, overlaps
        c = Segment(20, 50, 80, 50, 3, False, False, 0.5)    # parallel, far away
        panels = [{"path_index": 1, "panel_index": 0},
                  {"path_index": 2, "panel_index": 1},
                  {"path_index": 3, "panel_index": 2}]
        e = shared_edges([a, b, c], panels)
        pairs = {(x["path_a"], x["path_b"]) for x in e}
        assert (1, 2) in pairs
        assert (1, 3) not in pairs and (2, 3) not in pairs

    def test_dashed_folds_are_detected(self, tmp_path):
        g, _, _, _ = _analyse(_carton(tmp_path, dashed_folds=True))
        assert g["dashed_segments"] >= 2

    def test_glue_flap_topology(self, tmp_path):
        g, _, _, _ = _analyse(_carton(tmp_path, glue_flap=True))
        # a flap attaches on exactly one edge and has an angled side
        assert isinstance(g["glue_flap_candidates"], list)

    def test_decorative_closed_shapes_are_not_orthogonal_panels(self, tmp_path):
        doc = fitz.open()
        page = doc.new_page(width=600, height=400)
        for i in range(20):                    # circles: closed, non-orthogonal
            page.draw_circle(fitz.Point(60 + i * 25, 200), 20,
                             color=(0, 0, 0), width=0.5)
        p = tmp_path / "bubbles.pdf"
        doc.save(p)
        doc.close()
        g, _, _, _ = _analyse(p)
        assert g["panel_count"] >= 1
        assert g["orthogonal_panel_count"] < g["panel_count"]

    def test_graph_is_deterministic(self, tmp_path):
        p = _carton(tmp_path)
        a, _, _, _ = _analyse(p)
        b, _, _, _ = _analyse(p)
        assert a["panel_count"] == b["panel_count"]
        assert a["shared_edge_count"] == b["shared_edge_count"]
        assert [x["bbox_pt"] for x in a["panels"]] == [x["bbox_pt"] for x in b["panels"]]


# --------------------------------------------------------------------------
class TestRegistrationPrecision:
    def test_direct_path_association_when_alignment_is_proven(self, tmp_path):
        doc, page, dr, _ = _page(_registration_pdf(tmp_path))
        try:
            cs = analyse_page(doc, page, len(dr))
        finally:
            doc.close()
        assert cs["alignment_proven"] is True
        assert cs["path_association"] == "DIRECT"
        assert cs["tier_path_level"] == C.TIER_DIRECT
        assert cs["registration_painting_ops"] == 2
        assert cs["registration_ink_used_on_page"] is True
        assert cs["path_index_map"] is not None
        assert cs["path_index_map"][0]["fill_separation"] == "All"
        assert cs["path_index_map"][1]["stroke_separation"] == "All"

    def test_no_registration_ink_reports_cleanly(self, tmp_path):
        doc, page, dr, _ = _page(_carton(tmp_path))
        try:
            cs = analyse_page(doc, page, len(dr))
        finally:
            doc.close()
        assert cs["registration_painting_ops"] == 0
        assert cs["registration_ink_used_on_page"] is False

    def test_all_present_never_assigns_arbitrary_strokes(self, pilot_entries):
        """`/Separation /All` exists in LP-2018 and is used by 245 painting ops,
        yet no thin stroke may inherit registration certainty from that fact."""
        e = next(x for x in pilot_entries if "LP-2018" in x["relative_path"])
        g, cs, _, _ = _analyse(pilot_path(e))
        assert cs["registration_ink_used_on_page"] is True
        assert cs["registration_painting_ops"] > 0
        assert cs["path_association"] == "UNAVAILABLE"     # measured on the pilot
        assert cs["tier_path_level"] == C.TIER_HEURISTIC
        # geometry, not colour, produced the marks — and far fewer than all strokes
        assert len(g["registration_mark_candidates"]) < g["structural_paths"]

    def test_policy_is_recorded(self, tmp_path):
        doc, page, dr, _ = _page(_carton(tmp_path))
        try:
            cs = analyse_page(doc, page, len(dr))
        finally:
            doc.close()
        assert "never proves" in cs["policy"]
        assert cs["tier_document_level"] == C.TIER_DIRECT


# --------------------------------------------------------------------------
class TestDielineEvidence:
    def test_synthetic_carton_qualifies(self, tmp_path):
        g, cs, dl, surface = _analyse(_carton(tmp_path))
        assert dl["qualifies"] is True
        ev = dl["evidence"]
        assert ev["positive_evidence"]
        assert ev["qualifying_route"] in ("contour_and_panels", "panel_topology")
        assert dl["type"]["value"] == LIKELY_DIELINE
        assert dl["outcome"] == LIKELY_DIELINE
        assert dl["type"]["tier"] == C.TIER_HEURISTIC
        assert dl["human_confirmed_is_dieline"] is None

    def test_decorative_border_is_not_a_dieline(self, tmp_path):
        """A big closed frame scores on 'contour' evidence, but panel topology is
        what qualifies a dieline — and an ornamental border has none. It must be
        REJECTED outright, never parked in the human-review band."""
        g, cs, dl, surface = _analyse(_decorative_border(tmp_path))
        assert dl["qualifies"] is False
        assert dl["outcome"] == REJECTED
        assert dl["evidence"]["has_meaningful_structural_evidence"] is False
        ev = dl["evidence"]
        assert ev["qualifying_route"] is None
        assert ev["missing_evidence"], "a rejection must say what was missing"
        assert any("orthogonal closed panels" in m for m in ev["missing_evidence"])
        assert g["shared_edge_count"] == 0

    def test_evidence_model_records_all_four_channels(self, tmp_path):
        g, cs, _, surface = _analyse(_carton(tmp_path))
        ev = evaluate_dieline(g, surface, cs, "carton.pdf")
        for k in ("positive_evidence", "contradictory_evidence",
                  "missing_evidence", "supporting_evidence_only"):
            assert k in ev

    def test_filename_hint_is_supporting_only(self, tmp_path):
        g, cs, _, surface = _analyse(_decorative_border(tmp_path))
        ev = evaluate_dieline(g, surface, cs, "ES3083吸塑 展盒刀线.ai")
        assert ev["supporting_evidence_only"], "the 刀线 hint must be recorded"
        assert ev["qualifies"] is False, "a filename can never qualify a dieline"

    def test_no_export_of_reusable_geometry(self, tmp_path):
        _, _, dl, _ = _analyse(_carton(tmp_path))
        assert "no SVG, DXF or AI export" in dl["export_policy"]
        assert "panel_polygons" not in dl        # measurements only


# --------------------------------------------------------------------------
class TestLineClassification:
    def _classify(self, path, has_region=True):
        g, cs, dl, _ = _analyse(path)
        shared = {p for e in g["shared_edges"] for p in (e["path_a"], e["path_b"])}
        marks = {}
        for key, cls in (("registration_mark_candidates", "REGISTRATION_MARK_CANDIDATE"),
                         ("crop_mark_candidates", "CROP_MARK_CANDIDATE"),
                         ("dimension_mark_candidates", "DIMENSION_MARK_CANDIDATE")):
            for m in g[key]:
                marks[m["path_index"]] = cls
        return classify_lines(g, marks, bool(dl and dl.get("qualifies")),
                              g.get("outer_path_index"), shared)

    def test_all_classes_are_known(self, tmp_path):
        c = self._classify(_carton(tmp_path))
        assert set(c["counts"]) == set(LINE_CLASSES)

    def test_carton_yields_cut_and_fold_candidates(self, tmp_path):
        c = self._classify(_carton(tmp_path))["counts"]
        assert c["CUT_LINE_CANDIDATE"] >= 1
        assert c["FOLD_LINE_CANDIDATE"] >= 1

    def test_without_topology_nothing_becomes_cut_or_fold(self, tmp_path):
        c = self._classify(_decorative_border(tmp_path))["counts"]
        assert c["CUT_LINE_CANDIDATE"] == 0
        assert c["FOLD_LINE_CANDIDATE"] == 0
        assert c["CREASE_LINE_CANDIDATE"] == 0
        assert c["STRUCTURAL_UNRESOLVED"] >= 1

    def test_classification_is_heuristic(self, tmp_path):
        c = self._classify(_carton(tmp_path))
        assert "heuristic" in c["note"]


# --------------------------------------------------------------------------
class TestAssociation:
    def test_many_to_many(self):
        cands = [{"unit_id": "u0", "bbox_pt": [0, 0, 50, 50],
                  "candidate_type": {"value": "SURFACE_ARTWORK"}},
                 {"unit_id": "u1", "bbox_pt": [40, 0, 100, 50],
                  "candidate_type": {"value": "SPEC_TABLE"}},
                 {"unit_id": "u2", "bbox_pt": [200, 200, 250, 250],
                  "candidate_type": {"value": "UNKNOWN"}}]
        hits = associate((10, 10, 90, 40), cands)
        assert {h["unit_id"] for h in hits} == {"u0", "u1"}     # spans two
        assert associate((300, 300, 310, 310), cands) == []     # attaches to zero

    def test_dieline_spanning_flag(self, tmp_path):
        g, cs, dl, _ = _analyse(_carton(tmp_path))
        cands = [{"unit_id": "a", "bbox_pt": [40, 40, 300, 360],
                  "candidate_type": {"value": "SURFACE_ARTWORK"}},
                 {"unit_id": "b", "bbox_pt": [300, 40, 560, 360],
                  "candidate_type": {"value": "SURFACE_ARTWORK"}}]
        a = associate_all(dl, g, cands)
        assert a["dieline_candidate_count"] == 2
        assert a["dieline_spans_multiple_candidates"] is True

    def test_findings_may_attach_to_zero_candidates(self, tmp_path):
        g, cs, dl, _ = _analyse(_carton(tmp_path))
        a = associate_all(dl, g, [])
        assert a["dieline_candidate_count"] == 0
        assert a["panels_attached_to_zero_candidates"] == len(g["panels"])

    def test_works_when_segmentation_is_low_confidence(self, pilot_entries):
        """The page graph is authoritative: YB-BB is MANUAL_REQUIRED in B2 and
        B3 must still analyse it."""
        e = next(x for x in pilot_entries if "YB-BB" in x["relative_path"])
        g, cs, dl, _ = _analyse(pilot_path(e))
        assert g["structural_paths"] > 0
        assert dl["qualifies"] is False


# --------------------------------------------------------------------------
class TestRealPilotRegressions:
    def test_es3083_has_a_page_level_likely_dieline(self, pilot_entries):
        e = next(x for x in pilot_entries if "ES3083" in x["relative_path"])
        g, cs, dl, _ = _analyse(pilot_path(e))
        assert dl["qualifies"] is True
        assert g["orthogonal_panel_count"] >= 3
        assert dl["evidence"]["contour_area_fraction"] > 0.05

    def test_yb_bb_stays_below_the_dieline_threshold(self, pilot_entries):
        e = next(x for x in pilot_entries if "YB-BB" in x["relative_path"])
        _, _, dl, _ = _analyse(pilot_path(e))
        assert dl["qualifies"] is False
        assert dl["evidence"]["missing_evidence"]

    def test_second_artboard_without_structure_is_rejected(self, pilot_entries):
        e = next(x for x in pilot_entries if "YB-1035" in x["relative_path"])
        g, _, dl, _ = _analyse(pilot_path(e), n=1)
        assert g["structural_paths"] == 0
        assert dl["qualifies"] is False

    def test_dieline_spans_multiple_b2_candidates_on_a_real_file(self, pilot_entries):
        e = next(x for x in pilot_entries if "ES3083" in x["relative_path"])
        doc = fitz.open(pilot_path(e))
        try:
            dr = [x for x in doc[0].get_drawings(extended=True)
                  if x["type"] in ("f", "s", "fs")]
            surface = tuple(build_boxes(
                doc[0], doc.xref_object(doc[0].xref, compressed=False))
                ["design_surface_pt"])
            g = build_graph(dr, surface)
            cs = analyse_page(doc, doc[0], len(dr))
            dl = build_dieline_candidate(g, surface, cs, "ES3083", 0)
            cands = segment_page(doc, doc[0], 0, e["relative_path"],
                                 Budget(Limits()))["candidates"]
        finally:
            doc.close()
        a = associate_all(dl, g, cands)
        assert a["dieline_candidate_count"] >= 1
        assert a["dieline_spans_multiple_candidates"] is True

    def test_no_off_canvas_structural_geometry_in_the_pilot(self, pilot_entries):
        """Measured: the 29,589 off-canvas paths are fills, not thin strokes —
        no registration or crop marks live outside the ArtBox."""
        from tools.dip0b.cluster import clip_rect
        from tools.dip0b.structure import structural_paths
        total = 0
        for e in pilot_entries:
            doc = fitz.open(pilot_path(e))
            try:
                for i in range(doc.page_count):
                    dr = [x for x in doc[i].get_drawings(extended=True)
                          if x["type"] in ("f", "s", "fs")]
                    surface = tuple(build_boxes(
                        doc[i], doc.xref_object(doc[i].xref, compressed=False))
                        ["design_surface_pt"])
                    off = [x for x in dr
                           if clip_rect(tuple(fitz.Rect(x["rect"])), surface) is None]
                    total += len(structural_paths(off))
            finally:
                doc.close()
        assert total == 0

    def test_reading_the_pilot_never_modifies_it(self, pilot_entries):
        e = pilot_entries[0]
        before = I.snapshot(pilot_path(e).parent)
        _analyse(pilot_path(e))
        assert I.compare(before, I.snapshot(pilot_path(e).parent))["unchanged"]


class TestOutputSafety:
    def test_output_root_outside_source(self):
        assert I.no_output_under_source()["ok"] is True

    def test_structure_never_emits_a_reusable_path_set(self, tmp_path):
        g, _, _, _ = _analyse(_carton(tmp_path))
        assert "analytical measurements only" in g["geometry_policy"]
        for p in g["panels"]:
            assert "vertices" not in p and "points" not in p


class TestRegionAnchor:
    """The dieline region is the largest connected STRUCTURAL COMPONENT.

    Anchoring it on the largest closed polygon drew ES3083's dieline box around
    its blank spec table: a production carton outline is drawn as many open
    cut/fold paths and is never a single closed path.
    """

    def test_es3083_region_is_the_carton_not_the_spec_table(self, pilot_entries):
        e = next(x for x in pilot_entries if "ES3083" in x["relative_path"])
        g, cs, dl, _ = _analyse(pilot_path(e))
        assert dl["qualifies"] is True
        assert dl["region_anchor"] == "main_structural_component"
        x0, y0, x1, y1 = dl["bbox_pt"]
        # the spec table sits on the left (x < 800); the carton on the right
        assert x0 > 900, "region must not be anchored on the left-hand spec table"
        assert dl["bbox_pt"] != g["outer_contour"]["bbox_pt"]
        assert dl["structural_paths_in_region"] > 100

    def test_main_component_holds_most_structural_paths(self, tmp_path):
        g, _, _, _ = _analyse(_carton(tmp_path))
        m = g["main_structural_component"]
        assert m and m["paths"] >= 3
        assert g["structural_component_count"] >= 1

    def test_region_falls_back_to_contour_without_components(self, tmp_path):
        doc = fitz.open()
        doc.new_page(width=200, height=200)
        p = tmp_path / "empty.pdf"
        doc.save(p)
        doc.close()
        g, cs, dl, _ = _analyse(p)
        assert g["main_structural_component"] is None
        assert dl["qualifies"] is False


class TestThreeOutcomes:
    """A binary verdict forces a confident answer the evidence cannot support.
    HL5503 (13 orthogonal panels, 77 `/All` ops, score 0.50) is the calibration
    example: it neither qualifies nor cleanly rejects."""

    def test_outcomes_are_the_three_approved_values(self):
        assert OUTCOMES == ("LIKELY_DIELINE_STRUCTURE",
                            "BORDERLINE_REVIEW_REQUIRED",
                            "REJECTED_NO_DIELINE_EVIDENCE")

    def test_hl5503_is_borderline(self, pilot_entries):
        e = next(x for x in pilot_entries if "HL5503" in x["relative_path"])
        g, cs, dl, _ = _analyse(pilot_path(e))
        assert dl["outcome"] == BORDERLINE
        ev = dl["evidence"]
        assert 0.45 <= ev["score"] < 0.60
        assert ev["has_meaningful_structural_evidence"] is True
        assert g["orthogonal_panel_count"] >= 3
        assert cs["registration_painting_ops"] > 0

    def test_es3083_remains_likely(self, pilot_entries):
        e = next(x for x in pilot_entries if "ES3083" in x["relative_path"])
        _, _, dl, _ = _analyse(pilot_path(e))
        assert dl["outcome"] == LIKELY_DIELINE

    def test_yb_bb_remains_rejected(self, pilot_entries):
        e = next(x for x in pilot_entries if "YB-BB" in x["relative_path"])
        _, _, dl, _ = _analyse(pilot_path(e))
        assert dl["outcome"] == REJECTED

    def test_every_page_keeps_full_evidence_and_provenance(self, pilot_entries):
        for name in ("ES3083", "HL5503", "YB-BB"):
            e = next(x for x in pilot_entries if name in x["relative_path"])
            _, _, dl, _ = _analyse(pilot_path(e))
            ev = dl["evidence"]
            for k in ("score", "confidence", "positive_evidence",
                      "contradictory_evidence", "missing_evidence",
                      "supporting_evidence_only", "config_fingerprint",
                      "human_confirmed_outcome"):
                assert k in ev, f"{name} missing {k}"
            assert ev["human_confirmed_outcome"] is None
            assert dl["human_confirmed_outcome"] is None

    def test_rejected_pages_still_carry_a_record(self, pilot_entries):
        e = next(x for x in pilot_entries if "YB-BB" in x["relative_path"])
        _, _, dl, _ = _analyse(pilot_path(e))
        assert dl["region_id"]
        assert dl["evidence"]["missing_evidence"]
        assert dl["config_fingerprint"]

    def test_band_is_configuration_driven(self):
        a = DielineConfig().fingerprint()
        b = DielineConfig(borderline_min_score=0.10).fingerprint()
        assert a != b

    def test_widening_the_band_moves_a_rejection_to_borderline(self, pilot_entries):
        """The band is config-driven, not tuned around one file."""
        e = next(x for x in pilot_entries if "EP416" in x["relative_path"])
        doc, page, dr, surface = _page(pilot_path(e))
        try:
            g = build_graph(dr, surface)
            cs = analyse_page(doc, page, len(dr))
        finally:
            doc.close()
        tight = build_dieline_candidate(g, surface, cs, "EP416", 0)
        wide = build_dieline_candidate(g, surface, cs, "EP416", 0,
                                       DielineConfig(borderline_min_score=0.25))
        assert tight["outcome"] == REJECTED
        assert wide["outcome"] == BORDERLINE
        assert tight["config_fingerprint"] != wide["config_fingerprint"]

    def test_borderline_page_keeps_lines_unresolved(self, pilot_entries):
        """Conservative: only a LIKELY page yields cut/fold/crease classes."""
        e = next(x for x in pilot_entries if "HL5503" in x["relative_path"])
        g, cs, dl, _ = _analyse(pilot_path(e))
        shared = {p for x in g["shared_edges"] for p in (x["path_a"], x["path_b"])}
        lines = classify_lines(g, {}, dl["outcome"] == LIKELY_DIELINE,
                               g.get("outer_path_index"), shared)
        assert lines["counts"]["CUT_LINE_CANDIDATE"] == 0
        assert lines["counts"]["FOLD_LINE_CANDIDATE"] == 0
        assert lines["counts"]["STRUCTURAL_UNRESOLVED"] > 0


class TestB4Handoff:
    def test_dimension_finding_is_worded_precisely(self):
        from tools.dip0b.dieline import B4_HANDOFF_NOTES as N
        assert N["dimension_marks"] == (
            "no geometric dimension-mark candidates detected under the current rule")
        assert "contain no dimensions" not in N["dimension_marks"]
        assert len(N["dimension_mark_spot_check_pages"]) >= 4
        assert N["dimension_mark_open_questions"]

    def test_structural_is_not_technical_is_recorded(self):
        from tools.dip0b.dieline import B4_HANDOFF_NOTES as N
        t = N["structural_is_not_technical"]
        assert "is NOT technical ink" in t
        assert "merely because its path is thin" in t

    def test_registration_black_ambiguity_is_recorded(self):
        from tools.dip0b.dieline import B4_HANDOFF_NOTES as N
        t = N["registration_black_ambiguity"]
        assert "unresolved_or_ambiguous" in t
        assert "never be mapped" in t
