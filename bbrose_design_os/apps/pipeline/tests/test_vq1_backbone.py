"""VQ-1 — explicit cylindrical serum-dropper backbone. Deterministic,
provider-free; the golden fixture qualifies and every negative fails with
its stable finding."""
from __future__ import annotations

from apps.ire import vq1_backbone as vq


class TestBackbone:
    def test_qualified_fixture_and_determinism(self):
        a = vq.build_backbone()
        b = vq.build_backbone()
        assert a["backbone_hash"] == b["backbone_hash"]
        assert a["perceived_findings"] == []
        assert a["verdict"] == vq.VERDICT_PENDING       # never auto-approved
        assert a["schema_version"] == "container_form_backbone/1.0"
        assert a["implementation"] == \
            "cylindrical_serum_dropper_backbone/1.0"
        p = a["profile"]
        assert p["closed_symmetric_path"] and p["curve_segments"] >= 4
        assert p["self_intersections"] == 0
        assert p["rounded_rectangle_primitive"] is False
        assert p["top_width_ratio"] <= 0.45              # narrow neck top
        an = a["profile_anchors"]
        for left, right in (("BASE_LEFT", "BASE_RIGHT"),
                            ("WALL_LEFT", "WALL_RIGHT"),
                            ("NECK_LEFT", "NECK_RIGHT")):
            assert an[left][0] == -an[right][0]
        c = a["closure_assembly"]["continuity"]
        assert c["shoulder_to_neck"] and c["neck_to_collar"] \
            and c["bulb_into_collar"]
        assert c["total_height_composition"] == c["components_sum"] == 104.0
        assert set(a["surfaces"]) == set(vq.SURFACES)

    def test_registry_never_falls_back(self):
        assert vq.resolve_backbone(vq.ARCHETYPE)["verdict"] == \
            vq.VERDICT_PENDING
        missing = vq.resolve_backbone("RECTANGULAR_RIGID_BOTTLE")
        assert missing["verdict"] == "NO_EXPLICIT_BACKBONE"
        assert vq.VQ_EXPLICIT_BACKBONE_REQUIRED in missing["findings"]
        assert "VECTOR_RECONSTRUCTION_REVIEW_REQUIRED" in \
            missing["findings"]

    def test_negative_fixtures_emit_expected_findings(self):
        r = vq.build_backbone({"collar_diameter": 28.0})
        assert vq.VQ_COLLAR_RATIO_EXCESSIVE in r["perceived_findings"]
        r = vq.build_backbone({"bulb_base_ratio": 0.95, "bulb_max_at": 0.7})
        assert vq.VQ_BULB_EGG in r["perceived_findings"]
        assert vq.VQ_BULB_BASE_WIDE in r["perceived_findings"]
        r = vq.build_backbone({"bulb_dome_start": 0.02, "bulb_max_at": 0.9,
                               "bulb_upper_narrowing": 0.03})
        assert vq.VQ_BULB_PADDLE in r["perceived_findings"]
        r = vq.build_backbone({"visible_neck": 0.0, "neck_overlap": 0.0})
        assert vq.VQ_NECK_GEOMETRY_MISSING in r["perceived_findings"]
        assert vq.VQ_NECK_COLLAR_DISCONNECTED in r["perceived_findings"]
        r = vq.build_backbone({"neck_overlap": 0.0})
        assert vq.VQ_COLLAR_NECK_CONNECTION in r["perceived_findings"]
        r = vq.build_backbone({"body_height": 40.0, "body_diameter": 33.0,
                               "bulb_height": 40.0, "collar_height": 21.5})
        assert vq.VQ_CYL_READABILITY in r["perceived_findings"]
        r = vq.build_backbone({"shoulder_radius": 0.0})
        assert vq.VQ_NECK_SHOULDER_DISCONTINUITY in r["perceived_findings"]
        r = vq.build_backbone({"collar_height": 18.0, "bulb_height": 30.0,
                               "body_height": 53.5})
        assert vq.VQ_BULB_TOP_HEAVY in r["perceived_findings"]

    def test_bulb_width_samples_shape(self):
        s = vq.bulb_width_samples(vq.DEFAULT_DIMS)
        assert len(s) == 9
        assert s[0]["width_frac"] < 0.7
        assert max(x["width_frac"] for x in s) >= 0.97
        assert s[-1]["width_frac"] < 0.35
