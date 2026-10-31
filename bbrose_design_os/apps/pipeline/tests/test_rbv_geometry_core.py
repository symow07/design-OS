"""RBV-2A mesh core + RBV-1 reference intake — the owner's critical
geometry amendment as executable law: no silent revolve, no fabricated
depth, deterministic meshes, exact missing-evidence reporting."""
import json
import os
from pathlib import Path

import numpy as np
from django.test import SimpleTestCase

from apps.pipeline.services import container_geometry as cg
from apps.pipeline.services import reference_pack as rp

PROFILE = [(0.0, 0.62), (0.1, 0.75), (0.2, 1.0), (0.9, 1.0), (1.0, 0.95)]


def _record(family=cg.CIRCULAR, depth=None, params=None):
    dims = {"height_mm": 95, "front_width_mm": 35}
    if depth:
        dims["side_depth_mm"] = depth
    return cg.build_geometry_record(
        source_authority="VERSIONED_CONTAINER_GEOMETRY",
        dimensions=dims,
        cross_section={"family": family, "params": params or {}},
        front_profile=PROFILE)


class MeshCoreTests(SimpleTestCase):
    def test_only_circular_may_revolve(self):
        assert _record(cg.CIRCULAR)["geometry_class"] == \
            cg.AXISYMMETRIC_REVOLUTION
        for family in (cg.ELLIPTICAL, cg.SUPERELLIPSE,
                       cg.ROUNDED_RECTANGLE, cg.RECTANGULAR):
            rec = _record(family, depth=22,
                          params={"exponent": 4,
                                  "corner_radius_ratio": 0.3})
            assert rec["geometry_class"] == cg.LOFTED_CROSS_SECTION, family

    def test_missing_depth_never_fabricated(self):
        rec = _record(cg.ROUNDED_RECTANGLE)          # no side_depth_mm
        assert rec["geometry_class"] == cg.GEOMETRY_INCOMPLETE
        assert rec["body_mesh_identity"] is None
        assert any("refusing to fabricate" in f for f in rec["findings"])

    def test_conflicting_depth_on_circular_is_an_evidence_conflict(self):
        rec = _record(cg.CIRCULAR, depth=20)
        assert rec["geometry_class"] == cg.GEOMETRY_INCOMPLETE
        assert any("not silently revolved" in f for f in rec["findings"])

    def test_custom_family_requires_outline_evidence(self):
        rec = _record(cg.CUSTOM, depth=22)
        assert rec["geometry_class"] == cg.GEOMETRY_INCOMPLETE

    def test_mesh_deterministic_and_dimensioned(self):
        rec = _record(cg.CIRCULAR)
        m1 = cg.build_mesh(rec)
        m2 = cg.build_mesh(rec)
        assert m1["mesh_identity"] == m2["mesh_identity"]
        v = m1["vertices"]
        assert abs(v[:, 2].max() - 95.0) < 1e-9          # height honored
        assert abs(2 * np.abs(v[:, 0]).max() - 35.0) < 0.5
        # circular: depth equals width
        assert abs(np.abs(v[:, 1]).max() - np.abs(v[:, 0]).max()) < 1e-6

    def test_loft_respects_independent_depth(self):
        rec = _record(cg.SUPERELLIPSE, depth=22, params={"exponent": 4})
        v = cg.build_mesh(rec)["vertices"]
        assert abs(2 * np.abs(v[:, 1]).max() - 22.0) < 0.5
        assert abs(2 * np.abs(v[:, 0]).max() - 35.0) < 0.5

    def test_authorities_recorded_and_material_free(self):
        rec = _record(cg.CIRCULAR)
        assert rec["authorities"]["RENDER_SCENE_AUTHORITY"] == \
            "NONE_VISUALIZATION_ONLY"
        assert rec["authorities"]["AI_GENERATED_CONCEPT_AUTHORITY"] == \
            "DESIGN_INTENT_REFERENCE_ONLY"
        assert "material" not in json.dumps(rec).lower()


class ReferencePackTests(SimpleTestCase):
    def test_empty_pilot_lists_all_18_required_items(self):
        state = rp.pilot_intake_state()
        assert state["status"] == rp.INCOMPLETE
        assert len(state["missing_evidence"]) == len(rp.PACK_ITEMS) == 18

    def test_partial_pack_reports_exact_missing_and_uncertainty(self):
        manifest = {
            "overall_height_mm": {"value": 95},
            "body_width_mm": {"value": 35},
            "provenance": {"text": "owner shelf sample"},
        }
        state = rp.validate_reference_pack(manifest)
        assert state["status"] == rp.INCOMPLETE
        assert "cad_or_technical_drawing" in state["missing_evidence"]
        assert "front_photo" in state["missing_evidence"]
        assert "overall_height_mm" not in state["missing_evidence"]

    def test_photo_declarations_recorded_never_assumed(self):
        from PIL import Image
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png",
                                         delete=False) as fh:
            Image.new("RGB", (64, 64), "#FFFFFF").save(fh.name)
            self.addCleanup(os.remove, fh.name)   # the test removes what it made (the clean-up of 2026-10-04)
            manifest = {"front_photo": {
                "path": fh.name,
                "declarations": {"neutral_background": True}}}
            state = rp.validate_reference_pack(manifest)
        item = state["items"]["front_photo"]
        assert item["capture_declarations"]["neutral_background"] is True
        assert item["capture_declarations"]["no_beauty_filter"] is False
        assert any(u.get("item") == "front_photo"
                   for u in state["uncertainty"])

    def test_blender_runtime_record_pins_version(self):
        rec = json.loads((Path(__file__).resolve().parents[3] / "docs" /
                          "visual_quality" / "rbv" /
                          "blender_runtime.json").read_text())
        assert "4.5.12 LTS" in rec["version"]
        assert rec["installer_sha256"].startswith("f4afdca92c56")
        assert "NO auto-upgrade" in rec["installation_method"]
        assert "pixel-identical" in \
            rec["deterministic_configuration"]["verified"]
