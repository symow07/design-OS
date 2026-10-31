"""VQ-1-CORR-2 — reference-faithful structural fixture."""
from __future__ import annotations

import json
import os

from django.conf import settings

from apps.ire import vq1_render as r
from apps.ire.vq1_backbone import bulb_width_samples


class TestCorr2:
    def test_projection_contract_and_dims(self):
        # CORR-3 tightened the ONE shared contract to near-orthographic
        assert r.PROJECTION["ellipse_depth_ratio"] == 0.055
        assert r.PROJECTION["centerline"] == "shared"
        d = r.CORR2_DIMS
        assert d["shoulder_style"] == "SOFT_ROUNDED_SERUM_SHOULDER"
        # §7 perceived collar/body 0.58–0.64; sleeve reads tall not saucer
        ratio = d["collar_diameter"] / d["body_diameter"]
        assert 0.58 <= round(ratio, 3) <= 0.64
        assert d["collar_height"] / d["collar_diameter"] >= 0.5
        # §8 shallow top ellipse (depth ≤ 0.10 of collar width)
        assert r.PROJECTION["ellipse_depth_ratio"] <= 0.10
        # §10/§11 bulb: narrow base, inserted, narrower than collar
        assert d["bulb_base_ratio"] <= 0.5
        assert d["bulb_insertion"] > 0
        assert d["bulb_width"] < d["collar_diameter"]

    def test_bulb_profile_is_tapered_pipette_11_samples(self):
        s = bulb_width_samples({**r.CORR2_DIMS, "bulb_dome_start": 0.18,
                                "bulb_upper_narrowing": 0.42}, n=11)
        assert len(s) == 11
        w = [x["width_frac"] for x in s]
        assert w[0] <= 0.5                       # narrow base
        assert max(w) >= 0.97                    # real maximum
        assert w.index(max(w)) <= 5              # max in lower-middle
        assert w[-1] < 0.35                      # rounded dome closes
        assert w[-3] < w[5]                      # upper half narrows

    def test_bottle_draws_with_soft_shoulder_and_no_pedestal(self):
        g = r.draw_bottle(r.CORR2_DIMS, 0, 0, 1.0)
        names = {getattr(n, "name", "") for n in g.children}
        assert {"BODY", "COLLAR_SLEEVE", "COLLAR_TOP_RIM", "NECK_GLASS",
                "BULB"} <= names
        # no pedestal band object; base is part of the BODY path
        assert not any("PEDESTAL" in n or "FOOTER" in n for n in names)
        sil = r.draw_bottle(r.CORR2_DIMS, 0, 0, 1.0, silhouette_only=True)
        assert [getattr(n, "name", "") for n in sil.children] == \
            ["SILHOUETTE"]

    def test_rejected_fixture_and_review_state_preserved(self):
        base = os.path.join(settings.BASE_DIR, "docs", "visual_quality",
                            "vq1")
        g = json.load(open(os.path.join(
            base, "vq1_cylindrical_backbone_graph.json")))
        assert g["backbone_hash"].startswith("19f9b98d0bc46a0d")
        review = json.load(open(os.path.join(
            base, "vq1_human_structural_review.json")))
        assert review["state"] == "REVISION_REQUIRED"
        # rejection #1's codes now live in history[0] after rejection #2
        all_codes = review["codes"] + [c for h in review.get("history", [])
                                       for c in h["codes"]]
        assert "VQ_COLLAR_SAUCER_SHAPE" in all_codes


class TestCorr3:
    def test_reference_targets_and_shared_silhouette(self):
        d = r.CORR3_DIMS
        cb = d["collar_diameter"] / d["body_diameter"]
        assert 0.50 <= round(cb, 3) <= 0.56          # §7 reference target
        hw = d["collar_height"] / d["collar_diameter"]
        assert 0.75 <= round(hw, 3) <= 0.90
        # §9 bulb vs collar: base 30–36%, max 52–60%
        base_c = d["bulb_width"] * d["bulb_base_ratio"] / d["collar_diameter"]
        assert 0.30 <= round(base_c, 3) <= 0.36
        assert 0.52 <= round(d["bulb_width"] / d["collar_diameter"], 3) <= 0.60
        assert d["bulb_insertion"] > 0
        # §13 near-orthographic camera
        assert r.PROJECTION["ellipse_depth_ratio"] <= 0.06
        # §4 one canonical profile: silhouette view and rendered body use
        # the SAME path construction (same function, same dims)
        sil = r.draw_bottle(d, 0, 0, 1.0, silhouette_only=True)
        full = r.draw_bottle(d, 0, 0, 1.0)
        sil_path = [n for n in sil.children if n.name == "SILHOUETTE"][0]
        body_path = [n for n in full.children if n.name == "BODY"][0]
        assert [type(s).__name__ for s in sil_path.segments] == \
            [type(s).__name__ for s in body_path.segments]
        assert all(getattr(a, "x", None) == getattr(b, "x", None)
                   and getattr(a, "y", None) == getattr(b, "y", None)
                   for a, b in zip(sil_path.segments, body_path.segments))
        # §12 no pedestal ellipse object
        assert not any("BASE_ELLIPSE" in str(getattr(n, "name", ""))
                       for n in full.children)
        # §14 closure mass subordinate
        closure = (d["collar_diameter"] * d["collar_height"]
                   + d["bulb_width"] * d["bulb_height"])
        assert closure / (d["body_diameter"] * d["body_height"]) < 0.25

    def test_bulb_15_samples_reference_progression(self):
        s = bulb_width_samples({**r.CORR3_DIMS, "bulb_dome_start": 0.22,
                                "bulb_upper_narrowing": 0.5,
                                "bulb_dome_continuous": True}, n=15)
        assert len(s) == 15
        w = [x["width_frac"] for x in s]
        assert w[0] <= 0.62                    # narrow base vs max
        assert w.index(max(w)) <= 7            # max in lower-middle
        assert w[10] < w[6]                    # upper half narrows
        assert w[-1] < 0.30                    # narrow dome, no tombstone

    def test_both_rejections_preserved(self):
        base = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
        review = json.load(open(os.path.join(
            base, "vq1", "vq1_human_structural_review.json")))
        assert review["state"] == "REVISION_REQUIRED"
        assert "VQ1_HUMAN_STRUCTURAL_REJECTION_STILL_ACTIVE" in \
            review["codes"]
        assert review["history"][0]["codes"]            # rejection #1 kept
        contour = json.load(open(os.path.join(
            base, "vq1_corr2", "vq1_reference_structural_contour.json")))
        assert contour["authority"].startswith("CONCEPT_ONLY")
