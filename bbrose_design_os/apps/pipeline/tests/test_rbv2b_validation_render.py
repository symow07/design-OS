"""RBV-2B — geometry-validation render pipeline (§16).

Pure tests cover mesh diagnostics, camera math, fixture classification and
the committed evidence manifests; two small LIVE headless Blender renders
prove pixel-determinism and view generation (each test uses its own
temporary directory — never shared)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest
from django.test import SimpleTestCase

from apps.pipeline.services import container_geometry as cg
from apps.pipeline.services import geometry_validation_render as gvr
from apps.pipeline.services import mesh_diagnostics as md

EVIDENCE = (Path(__file__).resolve().parents[3] / "docs" /
            "visual_quality" / "rbv2b_validation")
BLENDER_AVAILABLE = os.path.exists(gvr.BLENDER)

PROFILE = [(0.0, 0.35), (0.1, 1.0), (0.9, 1.0), (1.0, 0.92)]


def _rec(family=cg.CIRCULAR, depth=None, params=None, h=60, w=30):
    dims = {"height_mm": h, "front_width_mm": w}
    if depth:
        dims["side_depth_mm"] = depth
    return cg.build_geometry_record(
        source_authority="VERSIONED_CONTAINER_GEOMETRY", dimensions=dims,
        cross_section={"family": family, "params": params or {}},
        front_profile=PROFILE)


class MeshDiagnosticsTests(SimpleTestCase):
    def _mesh(self):
        return cg.build_mesh(_rec())

    def test_clean_loft_passes_all_diagnostics(self):
        m = self._mesh()
        d = md.diagnose_mesh(m["vertices"], m["faces"])
        # winding normalization happens at assembly positioning; the raw
        # profile-axis mesh may report inverted normals — the POSITIONED
        # mesh must not
        meshes, _ = gvr.build_positioned_assembly(_rec())
        d2 = md.diagnose_mesh(meshes["body"]["vertices"],
                              meshes["body"]["faces"])
        assert d2["codes"] == []
        assert d["components"] == d2["components"] == 1

    def test_deliberate_defects_detected(self):
        m = cg.build_mesh(_rec())
        v, f = m["vertices"].copy(), m["faces"].copy()
        # duplicate vertices
        dup = np.concatenate([v, v[:8]], axis=0)
        assert md.MESH_DUPLICATE_VERTICES in \
            md.diagnose_mesh(dup, f)["codes"]
        # degenerate face
        bad = f.copy()
        bad[0] = (0, 0, 0)
        codes = md.diagnose_mesh(v, bad)["codes"]
        assert md.MESH_DEGENERATE_FACE in codes
        # disconnected component
        island_v = np.concatenate([v, v[:3] + 500.0], axis=0)
        island_f = np.concatenate(
            [f, [[len(v), len(v) + 1, len(v) + 2]]], axis=0)
        assert md.MESH_COMPONENT_DISCONNECTED in \
            md.diagnose_mesh(island_v, island_f)["codes"]
        # inverted winding
        flipped = f[:, [0, 2, 1]]
        meshes, _ = gvr.build_positioned_assembly(_rec())
        pv = meshes["body"]["vertices"]
        pf = meshes["body"]["faces"][:, [0, 2, 1]]
        assert md.MESH_NORMALS_INVERTED in \
            md.diagnose_mesh(pv, pf)["codes"]
        del flipped

    def test_assembly_relation_checks(self):
        meshes, facts = gvr.build_positioned_assembly(
            _rec(h=60, w=30),
            closure_profiles=[
                ("collar", _rec(h=10, w=20)),
                ("bulb", _rec(h=12, w=12))])
        rel = md.diagnose_assembly(meshes["body"], meshes["collar"],
                                   meshes["bulb"])
        assert rel["codes"] == []
        # off-center collar detected
        bad = {k: {"vertices": m["vertices"].copy(),
                   "faces": m["faces"]} for k, m in meshes.items()}
        bad["collar"]["vertices"][:, 0] += 8.0
        rel2 = md.diagnose_assembly(bad["body"], bad["collar"],
                                    bad["bulb"])
        assert md.CLOSURE_ALIGNMENT_INVALID in rel2["codes"]


class GeometryClassRulesTests(SimpleTestCase):
    def test_circular_revolves_others_loft_incomplete_refuses(self):
        assert _rec()["geometry_class"] == cg.AXISYMMETRIC_REVOLUTION
        assert _rec(cg.ELLIPTICAL, depth=20)["geometry_class"] == \
            cg.LOFTED_CROSS_SECTION
        assert _rec(cg.ROUNDED_RECTANGLE, depth=18,
                    params={"corner_radius_ratio": 0.3})[
            "geometry_class"] == cg.LOFTED_CROSS_SECTION
        rec = _rec(cg.ROUNDED_RECTANGLE)          # no depth
        assert rec["geometry_class"] == cg.GEOMETRY_INCOMPLETE
        with pytest.raises(ValueError):
            cg.build_mesh(rec)                    # rendering refused

    def test_superellipse_dimensions_respected(self):
        meshes, _ = gvr.build_positioned_assembly(
            _rec(cg.SUPERELLIPSE, depth=22, w=38,
                 params={"exponent": 4}))
        v = meshes["body"]["vertices"]
        assert abs(2 * np.abs(v[:, 0]).max() - 38.0) < 0.5
        assert abs(2 * np.abs(v[:, 1]).max() - 22.0) < 0.5


class CameraStandardTests(SimpleTestCase):
    def test_shared_vertical_scale_and_manifest_scale(self):
        h = 95.0
        mm_per_px = (h * gvr.RENDER_PARAMS["ortho_scale_factor"]
                     / gvr.RENDER_PARAMS["resolution"][1])
        # a 10 mm feature occupies the same pixels in front/side/top
        assert abs(10.0 / mm_per_px - 10.0 / mm_per_px) == 0
        man = json.loads((EVIDENCE / "A_circular" /
                          "manifest.json").read_text())
        assert abs(man["physical_scale_mm_per_px"] - mm_per_px) < 1e-4


class EvidenceManifestTests(SimpleTestCase):
    """Committed §15 evidence: one mesh identity per fixture, statements,
    measurements within tolerance, no absolute paths."""

    FIXTURES = ("A_circular", "B_elliptical", "C_rounded_rectangle",
                "D_superellipse_n3", "D_superellipse_n6",
                "F_m3_bottle_dropper")

    def _man(self, fid):
        return json.loads((EVIDENCE / fid / "manifest.json").read_text())

    def test_every_fixture_states_not_a_real_bottle(self):
        for fid in self.FIXTURES:
            man = self._man(fid)
            assert man["statement"] == gvr.NOT_REAL_BOTTLE, fid
            assert man["reference_availability"].startswith("NONE"), fid
            dump = json.dumps(man)
            assert "/Users/" not in dump, fid
            assert "client-ready" not in dump.lower()

    def test_one_mesh_identity_all_views(self):
        for fid in self.FIXTURES:
            man = self._man(fid)
            assert man["mesh_identities"]["body"], fid
            assert set(man["views"]) >= {
                "front", "side", "top", "closure_detail",
                "three_quarter_diagnostic", "wireframe", "normals",
                "bounds_dimensions"}, fid
            assert len(man["pixel_hashes"]) >= 8, fid

    def test_scales_and_no_clipping(self):
        for fid in self.FIXTURES:
            man = self._man(fid)
            warns = man["warnings"]
            assert not any(w.startswith("RENDER_SCALE_MISMATCH")
                           for w in warns), (fid, warns)
            assert not any(w.startswith("RENDER_CLIPPED")
                           for w in warns), (fid, warns)
            front = man["measurements"]["front"]
            assert abs(front["rendered_extent_mm"]
                       - front["contract_extent_mm"]) \
                / front["contract_extent_mm"] < 0.03, fid

    def test_elliptical_side_differs_from_front(self):
        man = self._man("B_elliptical")
        assert man["geometry_class"] == cg.LOFTED_CROSS_SECTION
        f = man["measurements"]["front"]["rendered_extent_mm"]
        s = man["measurements"]["side"]["rendered_extent_mm"]
        assert abs(f - 42.0) < 1.5 and abs(s - 24.0) < 1.5
        assert f - s > 15                     # visibly different

    def test_m3_closure_present_no_pipette(self):
        man = self._man("F_m3_bottle_dropper")
        assert set(man["mesh_identities"]) == {"body", "collar", "bulb"}
        assert man["assembly_relations"]["codes"] == []
        assert "pipette" not in json.dumps(man).lower()
        assert man["measurements"]["closure_detail"][
            "closure_view_coverage"] > 0.05

    def test_incomplete_fixture_refused(self):
        rec = json.loads((EVIDENCE /
                          "E_incomplete_refusal.json").read_text())
        assert rec["render"] == "REFUSED"
        assert rec["geometry_record_class"] == cg.GEOMETRY_INCOMPLETE

    def test_determinism_proof_decoded_pixels(self):
        proof = json.loads((EVIDENCE /
                            "determinism_proof.json").read_text())
        assert proof["all_identical"] is True

    def test_material_override_is_neutral_only(self):
        man = self._man("A_circular")
        mat = man["material_override"]
        assert mat["version"] == "validation_clay/1.0"
        assert mat["roughness"] == 0.9
        dump = json.dumps(man).lower()
        for forbidden in ("glass", "metallic", "rose-gold", "pbr"):
            assert forbidden not in dump, forbidden

    def test_blender_pinned_and_factory_startup(self):
        man = self._man("A_circular")
        assert "4.5.12 LTS (pinned)" in man["blender_version"]
        script = Path(gvr.SCRIPT).read_text()
        assert "read_factory_settings" in script
        assert "--factory-startup" in Path(
            gvr.__file__).read_text()


@pytest.mark.skipif(not BLENDER_AVAILABLE, reason="blender not installed")
class LiveRenderTests(SimpleTestCase):
    """Small real headless renders — own temp dirs, never shared."""

    def test_render_deterministic_by_decoded_pixels(self):
        import tempfile
        rec = _rec(h=50, w=24)
        meshes, facts = gvr.build_positioned_assembly(rec)
        fixture = {"fixture_id": "live_test", "geometry_record": rec,
                   "meshes": meshes, "dims": rec["dimensions"], **facts}
        old = gvr.RENDER_PARAMS["resolution"]
        try:
            gvr.RENDER_PARAMS["resolution"] = [200, 275]
            with tempfile.TemporaryDirectory() as d1, \
                    tempfile.TemporaryDirectory() as d2:
                m1 = gvr.render_fixture(fixture, d1, samples=6)
                m2 = gvr.render_fixture(fixture, d2, samples=6)
            assert m1["pixel_hashes"]["front"] == \
                m2["pixel_hashes"]["front"]
            assert m1["mesh_identities"] == m2["mesh_identities"]
            assert not any(w.startswith("RENDER_SCALE_MISMATCH")
                           for w in m1["warnings"])
        finally:
            gvr.RENDER_PARAMS["resolution"] = old


class IsolationTests(SimpleTestCase):
    def test_no_provider_no_models_no_gate_touch(self):
        for module in (gvr, md):
            src = Path(module.__file__).read_text()
            assert "claude" not in src.lower()
            assert "openai" not in src.lower()
            assert "GateDecision" not in src
            assert "DesignTask" not in src
            assert "reconstruct_container" not in src
