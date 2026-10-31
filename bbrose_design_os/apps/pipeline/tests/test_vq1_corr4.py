"""VQ-1-CORR-4 §14 — human-calibrated contour, mirrored canonical paths,
emitted/canonical identity, and preservation of every prior rejection."""
import json
import os

import pytest
from django.conf import settings

from apps.ire import vq1_corr4 as m
from apps.ire.graph import ClosePath, CubicTo, LineTo

D = m.CORR4_DIMS
DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
CORR4 = os.path.join(DOCS, "vq1_corr4")


def _pts(segs):
    return [(s.x, s.y) for s in segs if not isinstance(s, ClosePath)]


class TestCalibratedContour:
    def test_human_calibrated_anchors_exist(self):
        anchors = m.calibrated_anchors()
        names = {a["name"] for a in anchors}
        for required in ("body_wall_top", "body_wall_bottom",
                         "lower_body_curve", "shoulder_start",
                         "shoulder_apex", "neck_bounds", "collar_top",
                         "collar_bottom", "bulb_apex", "bulb_max_width",
                         "base_integration", "shared_centerline"):
            assert required in names
        for a in anchors:
            assert a["status"].startswith("MANUALLY_CALIBRATED")
            assert a["authority"] == "CONCEPT_ONLY_NOT_PRODUCTION"
            assert a["tolerance_norm"] > 0
            assert a["source_image"].startswith("GeneratedImage#97")
            assert a["human_confirmed"] is False
            assert 0.0 <= a["y_norm"] <= 1.0

    def test_committed_contour_record(self):
        rec = json.load(open(os.path.join(
            CORR4, "vq1_human_calibrated_reference_contour.json")))
        assert rec["record_type"] == \
            "vq1_human_calibrated_reference_contour/1.0"
        assert rec["authority"] == "CONCEPT_ONLY_NOT_PRODUCTION"
        assert rec["human_review"] == "PENDING"
        assert "confidence 0.6" in rec["supersedes"]
        assert len(rec["anchors"]) >= 12


class TestCanonicalMirroring:
    def test_body_right_side_is_a_mathematical_mirror(self):
        g = m.canonical_geometry(D, 0, 0, 1.0)
        cx = D["body_diameter"] / 2
        pts = _pts(g["BODY"])
        half = (len(pts) + 1) // 2
        left, right = pts[:half], pts[half - 1:][::-1]
        assert len(left) >= 4
        for lp, rp in zip(left, right):
            assert lp[0] <= cx + 1e-9
            assert abs((cx - lp[0]) - (rp[0] - cx)) < 1e-9
            assert abs(lp[1] - rp[1]) < 1e-9

    def test_bulb_right_side_is_an_exact_mirror(self):
        assert "VQ_BULB_LEFT_RIGHT_ASYMMETRY" not in m.bulb_findings(D)
        g = m.canonical_geometry(D, 0, 0, 1.0)
        cx = D["body_diameter"] / 2
        pts = _pts(g["BULB"])
        half = (len(pts) + 1) // 2
        for lp, rp in zip(pts[:half], pts[half - 1:][::-1]):
            assert abs((cx - lp[0]) - (rp[0] - cx)) < 1e-12
            assert abs(lp[1] - rp[1]) < 1e-12

    def test_mirror_helper_reflects_control_points_in_order(self):
        src = [m.MoveTo(x=0.0, y=0.0),
               CubicTo(x1=1.0, y1=2.0, x2=3.0, y2=4.0, x=5.0, y=6.0)]
        out = m.mirrored_return(src, 10.0)
        assert len(out) == 1
        assert (out[0].x1, out[0].y1) == (17.0, 4.0)     # x2 becomes x1
        assert (out[0].x2, out[0].y2) == (19.0, 2.0)
        assert (out[0].x, out[0].y) == (20.0, 0.0)       # back to start


class TestBodyAndShoulder:
    def test_body_walls_are_parallel(self):
        g = m.canonical_geometry(D, 0, 0, 1.0)
        cx = D["body_diameter"] / 2
        walls = [s for s in g["BODY"] if isinstance(s, LineTo)]
        lx = [s.x for s in walls if s.x < cx]
        rx = [s.x for s in walls if s.x > cx]
        assert lx and rx
        assert max(lx) - min(lx) < 1e-9        # no taper on the left
        assert max(rx) - min(rx) < 1e-9        # nor the right
        assert abs((max(rx) - min(lx)) - D["body_diameter"]) < 1e-9

    def test_shoulder_has_no_straight_diagonal_facet(self):
        g = m.canonical_geometry(D, 0, 0, 1.0)
        shoulder = g["BODY"][1]
        assert isinstance(shoulder, CubicTo)
        curv = m.shoulder_curvature_samples(D, 21)
        k = [c["curvature"] for c in curv]
        assert min(k) > 0.001                  # always curving, never flat
        flat = run = 0
        for v in k:
            run = run + 1 if v < 0.005 else 0
            flat = max(flat, run)
        assert flat == 0

    def test_shoulder_tangents_are_continuous(self):
        g = m.canonical_geometry(D, 0, 0, 1.0)
        p0, sh = g["BODY"][0], g["BODY"][1]
        assert abs(sh.y1 - p0.y) < 1e-9        # horizontal at the neck
        assert abs(sh.x2 - sh.x) < 1e-9        # vertical at wall entry
        wall = g["BODY"][2]
        assert abs(wall.x - sh.x) < 1e-9       # C1 into the parallel wall
        k = [c["curvature"] for c in m.shoulder_curvature_samples(D, 21)]
        assert max(abs(a - b) for a, b in zip(k, k[1:])) < max(k) * 0.6


class TestNeckCollarBulb:
    def test_neck_is_a_visible_cylinder(self):
        assert D["visible_neck"] > 0
        assert D["neck_diameter"] < D["collar_diameter"]
        g = m.canonical_geometry(D, 0, 0, 1.0)
        cx = D["body_diameter"] / 2
        xs = [p[0] for p in _pts(g["NECK"])]
        assert abs(min(xs) - (cx - D["neck_diameter"] / 2)) < 1e-9
        # straight parallel sides + curved rims = a cylinder, not a block
        assert any(isinstance(s, LineTo) for s in g["NECK"])
        assert any(isinstance(s, CubicTo) for s in g["NECK"])

    def test_collar_is_not_a_rectangular_block(self):
        g = m.canonical_geometry(D, 0, 0, 1.0)
        assert not any(isinstance(s, LineTo) for s in g["COLLAR"])
        assert all(isinstance(s, (m.MoveTo, CubicTo, ClosePath))
                   for s in g["COLLAR"])
        cx = D["body_diameter"] / 2
        # the side surface bows outward — a block would not
        side = g["COLLAR"][2]
        assert (cx - side.x1) > D["collar_diameter"] / 2
        r = m.perceived_structural_report(D)
        assert r["checks"]["collar_cylindrical_readability"]
        assert r["checks"]["collar_visual_mass_subordinate"]

    def test_bulb_profile_shape(self):
        s = m.bulb_samples(D, 21)
        assert len(s) == 21
        w = [x["width_frac"] for x in s]
        peak = w.index(max(w))
        assert 0.15 <= peak / 20 <= 0.45           # max in the lower-middle
        assert w[0] < 0.80                         # narrow insertion base
        assert all(b >= a - 1e-9 for a, b in zip(w[:peak], w[1:peak + 1]))
        upper = w[peak:]
        assert all(b < a for a, b in zip(upper, upper[1:]))   # no plateau
        assert w[-1] == 0.0                        # closes at the apex
        assert w[-2] < 0.45                        # narrow rounded dome
        assert m.bulb_findings(D) == []

    def test_bulb_base_enters_the_collar(self):
        lay = m.layout(D)
        assert D["bulb_insertion"] > 0
        g = m.canonical_geometry(D, 0, 0, 1.0)
        bulb_base_y = max(p[1] for p in _pts(g["BULB"]))
        assert bulb_base_y > lay["y_collar_top"]   # base is below the rim
        assert bulb_base_y < lay["y_collar_bot"]   # but inside the collar
        assert D["bulb_base_width"] < D["collar_diameter"] - 2


class TestBaseIntegration:
    def test_base_lives_inside_the_single_body_silhouette(self):
        g = m.canonical_geometry(D, 0, 0, 1.0)
        lay = m.layout(D)
        assert set(g) >= {"BODY", "COLLAR", "NECK", "BULB"}
        assert "BASE" not in g and "BASE_ELLIPSE" not in g
        ys = [p[1] for p in _pts(g["BODY"])]
        assert abs(max(ys) - lay["y_bottom"]) < 1e-9
        cx = D["body_diameter"] / 2
        bottom = [p for p in _pts(g["BODY"])
                  if abs(p[1] - lay["y_bottom"]) < 1e-9]
        assert any(abs(p[0] - cx) < 1e-9 for p in bottom)


class TestEmittedPathIdentity:
    def test_emitted_paths_equal_canonical_paths(self, tmp_path):
        from apps.ire.emitters.pdf_ai import emit_pdf_ai
        from apps.ire.graph import Document, Group
        ox, oy, s = 30.0, 20.0, 1.6
        doc = Document(page_w=140, page_h=200, title="corr4-identity",
                       root=Group(name="Artwork", role="artwork", children=[
                           m.draw_fixture(D, ox, oy, s),
                           m.draw_fixture(D, ox, oy, s, prefix="sil-",
                                          silhouette_only=True)]))
        out = str(tmp_path / "identity.pdf")
        emit_pdf_ai(doc, out)
        geom = m.canonical_geometry(D, ox, oy, s)
        assert m.verify_emitted_contours(out, geom) == []

    def test_divergent_geometry_is_detected(self, tmp_path):
        from apps.ire.emitters.pdf_ai import emit_pdf_ai
        from apps.ire.graph import Document, Group
        ox, oy, s = 30.0, 20.0, 1.6
        doc = Document(page_w=140, page_h=200, title="corr4-divergent",
                       root=Group(name="Artwork", role="artwork",
                                  children=[m.draw_fixture(D, ox, oy, s)]))
        out = str(tmp_path / "divergent.pdf")
        emit_pdf_ai(doc, out)
        wrong = m.canonical_geometry({**D, "collar_diameter": 26.0},
                                     ox, oy, s)
        found = m.verify_emitted_contours(out, wrong)
        assert any(f.startswith("VQ_CANONICAL_PROFILE_NOT_USED_BY_RENDER")
                   for f in found)

    def test_silhouette_and_render_share_the_canonical_segments(self):
        full = m.draw_fixture(D, 5, 7, 1.3)
        sil = m.draw_fixture(D, 5, 7, 1.3, prefix="s-",
                             silhouette_only=True)
        by_name = {n.name.replace("s-", ""): n for n in sil.children}
        for node in full.children:
            key = node.name
            if key in by_name:
                assert _pts(node.segments) == _pts(by_name[key].segments)


class TestPerceivedValidationAndPreservation:
    def test_best_automated_state_is_pending_human_review(self):
        r = m.perceived_structural_report(D)
        assert r["verdict"] == "PASSES_STRUCTURAL_FORM_PENDING_HUMAN_REVIEW"
        assert r["findings"] == []
        for name in ("body_wall_parallelism", "shoulder_curvature_continuity",
                     "neck_visibility", "collar_cylindrical_readability",
                     "collar_visual_mass_subordinate", "bulb_symmetry",
                     "bulb_taper", "bulb_dome", "bulb_insertion",
                     "base_integration", "closure_coherence",
                     "visual_center_of_mass_in_body",
                     "canonical_render_identity"):
            assert r["checks"][name] is True
        assert "human rejection is always authoritative" in r["human_note"]

    def test_emitted_findings_block_the_pass(self):
        r = m.perceived_structural_report(
            D, emitted_findings=["VQ_CANONICAL_PROFILE_NOT_USED_BY_RENDER"])
        assert r["verdict"] == "STRUCTURAL_FORM_FAILED"
        assert r["checks"]["canonical_render_identity"] is False

    def test_human_rejection_remains_active_and_history_preserved(self):
        rec = json.load(open(os.path.join(
            DOCS, "vq1", "vq1_human_structural_review.json")))
        assert rec["state"] == "REVISION_REQUIRED"
        assert "VQ1_HUMAN_STRUCTURAL_REJECTION_STILL_ACTIVE" in rec["codes"]
        # every rejection ever recorded stays on file; later ones push the
        # earlier record into history rather than replacing it
        assert len(rec["history"]) >= 2
        every = rec["codes"] + [c for h in rec["history"] for c in h["codes"]]
        assert "VQ_COLLAR_SAUCER_SHAPE" in every             # rejection #1
        assert "VQ_PREVIEW_SILHOUETTE_DIVERGENCE" in every   # rejection #2
        assert "VQ_REFERENCE_CONTOUR_NOT_CONTROLLING_OUTPUT" in every

    def test_prior_fixtures_are_preserved(self):
        from apps.ire.vq1_backbone import build_backbone
        assert build_backbone()["backbone_hash"].startswith(
            "19f9b98d0bc46a0d")
        for p in ("vq1/vq1_cylindrical_backbone_review.png",
                  "vq1_corr2/vq1_corr2_review.png",
                  "vq1_corr3/vq1_corr3_review.png",
                  "vq1_corr4/vq1_corr4_review.png",
                  "vq1_corr4/vq1_corr4_assembly.png",
                  "vq1_corr4/vq1_corr4_fixture.json"):
            assert os.path.exists(os.path.join(DOCS, p)), p

    def test_committed_fixture_record_is_reproducible(self):
        rec = json.load(open(os.path.join(CORR4, "vq1_corr4_fixture.json")))
        assert rec["record_type"] == "vq1_corr4_structural_fixture/1.0"
        assert rec["dims_mm"] == D
        assert rec["human_review"] == "PENDING"
        assert rec["emitted_contour_verification"]["filled_render"] == \
            "EQUAL_TO_CANONICAL"
        assert rec["perceived_structural_report"]["verdict"] == \
            "PASSES_STRUCTURAL_FORM_PENDING_HUMAN_REVIEW"
        assert len(rec["bulb_samples_21"]) == 21
        g = m.canonical_geometry(D, 0, 0, 1.0)
        for name, h in rec["canonical_path_hashes"].items():
            assert len(g[name]) > 3 and len(h) == 16

    @pytest.mark.django_db
    def test_live_pilot_records_untouched(self):
        from apps.pipeline.models import DesignProject, DesignTask
        assert DesignTask.objects.filter(
            id=52, status="container_stage_visually_rejected").exists() or \
            not DesignTask.objects.filter(id=52).exists()
        assert DesignProject.objects.filter(
            id=7, status="container_rejected").exists() or \
            not DesignProject.objects.filter(id=7).exists()

    def test_no_provider_call_paths_in_corr4(self):
        src = open(m.__file__).read()
        for banned in ("openai", "requests.post", "urllib.request",
                       "httpx", "anthropic", "run_aria_pipeline"):
            assert banned not in src.lower()
