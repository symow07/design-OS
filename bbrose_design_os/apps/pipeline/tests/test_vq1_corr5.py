"""VQ-1-CORR-5 §14 — closure-first subfixtures, the assembly gate, and
preservation of every prior rejected fixture."""
import json
import os

import pytest
from django.conf import settings

from apps.ire import vq1_corr5 as m
from apps.ire.graph import ClosePath, CubicTo, LineTo

D = m.CORR5_DIMS
DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
CORR5 = os.path.join(DOCS, "vq1_corr5")


def _pts(segs):
    return [(s.x, s.y) for s in segs if not isinstance(s, ClosePath)]


class TestReferenceCalibrationV11:
    def test_landmarks_cover_every_required_structure(self):
        names = {a["name"] for a in m.calibrated_landmarks()}
        for required in ("body_wall_top", "body_wall_bottom",
                         "shoulder_start", "shoulder_apex", "neck_visible",
                         "collar_top", "collar_bottom",
                         "bulb_insertion_stem", "bulb_lower_width",
                         "bulb_maximum_width", "bulb_upper_taper",
                         "bulb_dome_upper", "bulb_top", "base_curve",
                         "base_bottom", "shared_centerline"):
            assert required in names

    def test_every_landmark_is_read_from_a_large_crop(self):
        for a in m.calibrated_landmarks():
            assert a["status"] == "MANUALLY_CALIBRATED_ON_LARGE_GRIDDED_CROP"
            assert a["authority"] == "CONCEPT_ONLY_NOT_PRODUCTION"
            assert a["human_confirmed"] is False
            assert a["crop"] in set(m.REF_CROPS) | {"all"}
        # left/right are exact reflections about the shared centerline
        for a in m.calibrated_landmarks():
            if "left_px" in a:
                assert abs((m.REF_CENTERLINE_PX - a["left_px"])
                           - (a["right_px"] - m.REF_CENTERLINE_PX)) < 1e-9

    def test_committed_contour_v1_1_supersedes_the_invalid_v1_0(self):
        rec = json.load(open(os.path.join(
            CORR5, "vq1_human_calibrated_reference_contour_v1_1.json")))
        assert rec["record_type"] == \
            "vq1_human_calibrated_reference_contour/1.1"
        assert "1.0" in rec["supersedes"] and "INVALID" in rec["supersedes"]
        assert rec["human_review"] == "PENDING"
        assert set(rec["crops"]) == {"closure", "shoulder_neck",
                                     "body_base"}
        for crop in rec["crops"]:
            assert os.path.exists(os.path.join(CORR5, f"ref97_{crop}.png"))


class TestBulbSubfixtureA:
    def test_insertion_stem_exists_and_is_narrow(self):
        r = m.bulb_subfixture(D)
        assert r["checks"]["insertion_stem_exists"]
        assert r["checks"]["stem_width_10_15pc_of_body"]
        assert 0.10 <= r["stem_width_frac_of_body"] <= 0.15
        assert r["checks"]["stem_substantially_narrower"]
        assert D["bulb_stem_width"] < D["bulb_max_width"] * 0.60
        assert r["insertion_mm"] > 0

    def test_maximum_width_and_upper_middle(self):
        r = m.bulb_subfixture(D)
        assert 0.25 <= r["max_width_frac_of_body"] <= 0.32
        assert r["checks"]["maximum_in_lower_middle"]
        assert r["checks"]["upper_middle_clearly_slimmer"]
        w = [s["half_width_mm"] for s in r["samples_31"]]
        upper_third = max(w[20:])
        assert upper_third <= 0.80 * max(w)

    def test_crown_is_continuously_curved_not_polygonal(self):
        r = m.bulb_subfixture(D)
        assert r["checks"]["crown_continuously_curved"]
        assert r["checks"]["dome_closes_to_zero"]
        assert r["checks"]["dome_narrow_not_tombstone"]
        dome = [s["half_width_mm"] for s in r["samples_31"]
                if s["t"] >= D["bulb_dome_start"]]
        d1 = [a - b for a, b in zip(dome, dome[1:])]
        # a polygon would step by a constant amount; a curve accelerates
        assert max(abs(a - b) for a, b in zip(d1, d1[1:])) > 1e-4

    def test_no_flat_base_segment(self):
        r = m.bulb_subfixture(D)
        assert r["checks"]["no_flat_base_segment"]
        w = [s["half_width_mm"] for s in r["samples_31"]]
        assert w[0] < w[1]

    def test_at_least_31_samples_and_exact_mirroring(self):
        assert len(m.bulb_samples(D, 31)) == 31
        g = m.canonical_geometry(D, 0, 0, 1.0, ["bulb"])
        cx = D["body_diameter"] / 2
        pts = _pts(g["BULB"])
        half = (len(pts) + 1) // 2
        for lp, rp in zip(pts[:half], pts[half - 1:][::-1]):
            assert abs((cx - lp[0]) - (rp[0] - cx)) < 1e-12
            assert abs(lp[1] - rp[1]) < 1e-12

    def test_a_paddle_profile_is_rejected(self):
        bad = {**D, "bulb_stem_width": D["bulb_max_width"] * 0.95,
               "bulb_max_at": 0.9}
        r = m.bulb_subfixture(bad)
        assert r["status"] == "SUBFIXTURE_FAILED"
        assert r["findings"]

    def test_a_tombstone_dome_is_rejected(self):
        bad = {**D, "bulb_dome_width": 0.95, "bulb_dome_start": 0.97}
        r = m.bulb_subfixture(bad)
        assert "VQ_BULB_TOMBSTONE_DOME" in r["findings"]
        assert r["status"] == "SUBFIXTURE_FAILED"


class TestCollarNeckSubfixtureB:
    def test_collar_ratios_match_the_recalibrated_targets(self):
        r = m.collar_neck_subfixture(D)
        assert 0.45 <= r["collar_body_ratio"] <= 0.55
        assert 0.65 <= r["sleeve_height_width_ratio"] <= 0.85
        assert r["checks"]["collar_45_55pc_of_body"]
        assert r["checks"]["sleeve_height_65_85pc_of_width"]

    def test_collar_is_not_a_block_or_jar_lid(self):
        r = m.collar_neck_subfixture(D)
        assert r["checks"]["no_straight_sleeve_sidewall"]
        assert r["checks"]["sidewall_is_bowed"]
        assert r["checks"]["not_jar_lid"]
        assert r["checks"]["minimal_top_face"]
        g = m.canonical_geometry(D, 0, 0, 1.0, ["collar"])
        assert not any(isinstance(s, LineTo) for s in g["COLLAR"])

    def test_top_opening_is_concealed_by_the_stem(self):
        r = m.collar_neck_subfixture(D)
        assert r["checks"]["top_opening_concealed_by_stem"]

    def test_neck_is_cylindrical_and_overlapped_by_the_collar(self):
        r = m.collar_neck_subfixture(D)
        assert r["checks"]["neck_is_cylindrical"]
        assert r["checks"]["collar_physically_overlaps_neck"]
        assert r["checks"]["neck_mostly_hidden_in_collar"]
        assert r["checks"]["small_visible_glass_transition"]
        assert r["neck_hidden_fraction"] >= 0.60
        assert r["neck_overlap_mm"] > 0
        g = m.canonical_geometry(D, 0, 0, 1.0, ["neck"])
        assert any(isinstance(s, CubicTo) for s in g["NECK"])
        assert any(isinstance(s, LineTo) for s in g["NECK"])

    def test_a_swollen_block_collar_is_rejected(self):
        bad = {**D, "collar_diameter": 24.0, "collar_height": 4.0}
        r = m.collar_neck_subfixture(bad)
        assert r["status"] == "SUBFIXTURE_FAILED"
        assert "VQ_COLLAR_GENERIC_BLOCK_FALLBACK" in r["findings"]


class TestShoulderBodySubfixtureC:
    def test_shoulder_rise_is_shallow_and_reference_calibrated(self):
        r = m.shoulder_body_subfixture(D)
        assert r["checks"]["shoulder_rise_shallow"]
        assert r["checks"]["shoulder_rise_matches_reference"]
        assert abs(r["shoulder_rise_mm"]
                   - r["reference_shoulder_rise_mm"]) <= 0.6
        assert r["shoulder_rise_frac_of_body_width"] <= 0.18

    def test_shoulder_is_not_a_dome(self):
        r = m.shoulder_body_subfixture(D)
        assert r["checks"]["not_a_dome"]
        assert r["checks"]["shoulder_is_uppermost_portion_only"]
        assert r["checks"]["no_straight_facet"]
        assert r["checks"]["horizontal_tangent_at_neck"]
        assert r["checks"]["vertical_tangent_at_wall"]

    def test_an_oversized_dome_shoulder_is_rejected(self):
        bad = {**D, "shoulder_rise": 14.0}
        r = m.shoulder_body_subfixture(bad)
        assert r["status"] == "SUBFIXTURE_FAILED"
        assert "VQ_SHOULDER_DOME_OVERSIZED" in r["findings"]

    def test_body_walls_are_parallel_with_an_integrated_base(self):
        r = m.shoulder_body_subfixture(D)
        assert r["checks"]["walls_parallel"] and r["checks"]["no_taper"]
        assert r["checks"]["base_integrated_no_pedestal"]
        assert r["checks"]["base_curve_shallow"]
        g = m.canonical_geometry(D, 0, 0, 1.0)
        assert "BASE" not in g
        cx = D["body_diameter"] / 2
        lx = [s.x for s in g["BODY"] if isinstance(s, LineTo) and s.x < cx]
        assert lx and (max(lx) - min(lx)) < 1e-9


class TestAssemblyGate:
    def test_gate_releases_only_when_all_subfixtures_pass(self):
        g = m.assembly_gate(D)
        assert g["complete_assembly_released"] is True
        assert g["status"] == "PASSES_STRUCTURAL_FORM_PENDING_HUMAN_REVIEW"
        assert all(v.startswith("PASSES")
                   for v in g["subfixtures"].values())
        assert g["canonical_render_identity"] == "EQUAL"

    def test_a_failed_subfixture_blocks_the_complete_assembly(self):
        bad = {**D, "shoulder_rise": 14.0}
        g = m.assembly_gate(bad)
        assert g["complete_assembly_released"] is False
        assert g["status"] == "COMPLETE_ASSEMBLY_BLOCKED"
        assert g["subfixtures"]["C_shoulder_body"] == "SUBFIXTURE_FAILED"

    def test_render_divergence_blocks_the_complete_assembly(self):
        g = m.assembly_gate(
            D, emitted_findings=["VQ_CANONICAL_PROFILE_NOT_USED_BY_RENDER"])
        assert g["complete_assembly_released"] is False
        assert "VQ_CANONICAL_PROFILE_NOT_USED_BY_RENDER" in g["findings"]

    def test_gate_never_auto_accepts(self):
        g = m.assembly_gate(D)
        assert "never overrides a human visual rejection" in g["human_note"]
        assert "ACCEPTED" not in g["status"]


class TestEmittedContourIdentity:
    def test_emitted_paths_equal_canonical_paths(self, tmp_path):
        from apps.ire.emitters.pdf_ai import emit_pdf_ai
        from apps.ire.graph import Document, Group
        ox, oy, s = 25.0, 15.0, 2.0
        doc = Document(page_w=120, page_h=210, title="corr5-identity",
                       root=Group(name="Artwork", role="artwork", children=[
                           m.draw(D, ox, oy, s),
                           m.draw(D, ox, oy, s, prefix="sil-",
                                  outline_only=True)]))
        out = str(tmp_path / "identity.pdf")
        emit_pdf_ai(doc, out)
        assert m.verify_emitted_contours(
            out, m.canonical_geometry(D, ox, oy, s)) == []

    def test_divergent_geometry_is_detected(self, tmp_path):
        from apps.ire.emitters.pdf_ai import emit_pdf_ai
        from apps.ire.graph import Document, Group
        ox, oy, s = 25.0, 15.0, 2.0
        doc = Document(page_w=120, page_h=210, title="corr5-divergent",
                       root=Group(name="Artwork", role="artwork",
                                  children=[m.draw(D, ox, oy, s)]))
        out = str(tmp_path / "divergent.pdf")
        emit_pdf_ai(doc, out)
        wrong = m.canonical_geometry({**D, "collar_diameter": 26.0},
                                     ox, oy, s)
        assert any(f.startswith("VQ_CANONICAL_PROFILE_NOT_USED_BY_RENDER")
                   for f in m.verify_emitted_contours(out, wrong))

    def test_outline_and_render_share_the_canonical_segments(self):
        full = m.draw(D, 4, 6, 1.4)
        out = m.draw(D, 4, 6, 1.4, prefix="s-", outline_only=True)
        by_name = {n.name.replace("s-", ""): n for n in out.children}
        for node in full.children:
            if node.name in by_name:
                assert _pts(node.segments) == \
                    _pts(by_name[node.name].segments)


class TestPreservationAndProvenance:
    def test_human_rejection_remains_active_with_full_history(self):
        rec = json.load(open(os.path.join(
            DOCS, "vq1", "vq1_human_structural_review.json")))
        assert rec["state"] == "REVISION_REQUIRED"
        assert "VQ1_HUMAN_STRUCTURAL_REJECTION_STILL_ACTIVE" in rec["codes"]
        # each new rejection pushes the previous record into history; every
        # code ever recorded stays retrievable from codes + history
        assert len(rec["history"]) >= 3
        every = rec["codes"] + [c for h in rec["history"] for c in h["codes"]]
        assert "VQ_COLLAR_SAUCER_SHAPE" in every
        assert "VQ_PREVIEW_SILHOUETTE_DIVERGENCE" in every
        assert "VQ_REFERENCE_CONTOUR_NOT_CONTROLLING_OUTPUT" in every
        assert "VQ_HUMAN_CALIBRATED_CONTOUR_INVALID" in every

    def test_all_prior_fixtures_preserved(self):
        from apps.ire.vq1_backbone import build_backbone
        assert build_backbone()["backbone_hash"].startswith(
            "19f9b98d0bc46a0d")
        for p in ("vq1/vq1_cylindrical_backbone_review.png",
                  "vq1_corr2/vq1_corr2_review.png",
                  "vq1_corr3/vq1_corr3_review.png",
                  "vq1_corr4/vq1_corr4_review.png",
                  "vq1_corr4/vq1_corr4_fixture.json",
                  "vq1_corr4/vq1_human_calibrated_reference_contour.json"):
            assert os.path.exists(os.path.join(DOCS, p)), p
        c4 = json.load(open(os.path.join(
            DOCS, "vq1_corr4", "vq1_corr4_fixture.json")))
        assert c4["fixture_hash"].startswith("b67352ca10e8b623")

    def test_review_package_pages_exist(self):
        for n in ("p1_bulb", "p2_collar_neck", "p3_shoulder_body",
                  "p4_assembly", "p5_overlay", "p6_all_fixtures",
                  "p7_deviation"):
            for ext in ("png", "pdf", "ai"):
                assert os.path.exists(
                    os.path.join(CORR5, f"vq1_corr5_{n}.{ext}")), f"{n}.{ext}"

    def test_committed_fixture_record(self):
        rec = json.load(open(os.path.join(CORR5, "vq1_corr5_fixture.json")))
        assert rec["record_type"] == "vq1_corr5_structural_fixture/1.0"
        assert rec["contour"] == m.CONTOUR_VERSION
        assert rec["dims_mm"] == D
        assert rec["human_review"] == "PENDING"
        assert rec["assembly_gate"]["complete_assembly_released"] is True
        assert len(rec["canonical_path_hashes"]) == 4

    def test_no_provider_call_paths(self):
        src = open(m.__file__).read().lower()
        for banned in ("openai", "requests.post", "urllib.request",
                       "httpx", "anthropic", "run_aria_pipeline"):
            assert banned not in src

    @pytest.mark.django_db
    def test_live_pilot_records_untouched(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for tid, status in ((52, "container_stage_visually_rejected"),
                            (51, "awaiting_gate_2")):
            t = DesignTask.objects.filter(id=tid).first()
            assert t is None or t.status == status
        p = DesignProject.objects.filter(id=7).first()
        assert p is None or p.status == "container_rejected"
