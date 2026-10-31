"""PALT-M4B-A — deterministic recessed-tray kernel tests.

Every check the owner listed for the tray, asserted on the real mesh
rather than on the builder's own report. Fail-closed behaviour is proven
with negatives, and the "no Blender Boolean dependency" requirement is
proven structurally — the kernel must import and build with ``bpy``
absent from the module graph entirely.
"""
import copy
import math
import sys

import numpy as np
from django.test import SimpleTestCase

from apps.pipeline.services import palette_moulded_validators as mv
from apps.pipeline.services import palt_m4b_a as A
from apps.pipeline.services.palette_recessed_tray_geometry import (
    TOPOLOGY, RecessedTrayError, build_recessed_palette_tray)

SPEC = dict(A._values(A.TRAY))


def _tray(**over):
    spec = dict(SPEC)
    spec.update(over)
    return build_recessed_palette_tray(spec)


def _half_edges(faces):
    return np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]],
                           faces[:, [2, 0]]])


class RecessedTrayKernelTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tray = _tray()
        cls.v = cls.tray["vertices"]
        cls.f = cls.tray["faces"]

    # --- determinism ----------------------------------------------------
    def test_deterministic_tray_identity(self):
        again = _tray()
        self.assertEqual(self.tray["mesh_identity"], again["mesh_identity"])
        np.testing.assert_array_equal(self.v, again["vertices"])
        np.testing.assert_array_equal(self.f, again["faces"])

    def test_deterministic_topology_counts(self):
        s = TOPOLOGY["cell_edge_samples"]
        n = TOPOLOGY["pocket_segments"]
        k = TOPOLOGY["fillet_arc_samples"]
        self.assertEqual(n, 4 * s)
        self.assertEqual(TOPOLOGY["outer_loop_samples"],
                         4 * TOPOLOGY["cells_x"] * s)
        # 9 pockets x (2K+2 rings + centre) + deck lattice + outer loops
        rings = 2 * k + 2
        self.assertEqual(len(self.tray["pocket_profile_rings"]), rings)
        self.assertEqual(len(self.f), 15360)
        self.assertEqual(len(self.v), 7682)

    def test_topology_constant_change_alters_identity(self):
        """A pure-metadata topology key still participates in the hash."""
        original = TOPOLOGY["draft_strategy"]
        try:
            TOPOLOGY["draft_strategy"] = "SOMETHING_ELSE"
            changed = _tray()
        finally:
            TOPOLOGY["draft_strategy"] = original
        self.assertNotEqual(self.tray["mesh_identity"],
                            changed["mesh_identity"])
        self.assertEqual(_tray()["mesh_identity"],
                         self.tray["mesh_identity"])

    def test_consistent_topology_change_alters_identity_and_counts(self):
        """A real lattice change: S, N and the outer loop move together."""
        keep = {k: TOPOLOGY[k] for k in
                ("cell_edge_samples", "pocket_segments",
                 "outer_loop_samples")}
        try:
            TOPOLOGY["cell_edge_samples"] = 8
            TOPOLOGY["pocket_segments"] = 32
            TOPOLOGY["outer_loop_samples"] = 96
            coarse = _tray()
        finally:
            TOPOLOGY.update(keep)
        self.assertNotEqual(coarse["mesh_identity"],
                            self.tray["mesh_identity"])
        self.assertLess(len(coarse["faces"]), len(self.f))
        self.assertEqual(_tray()["mesh_identity"],
                         self.tray["mesh_identity"])

    # --- structure ------------------------------------------------------
    def test_exactly_nine_pockets(self):
        self.assertEqual(len(self.tray["pockets"]), 9)
        centres = {(p["centre_mm"][0], p["centre_mm"][1])
                   for p in self.tray["pockets"]}
        pitch = SPEC["pitch_mm"]
        self.assertEqual(centres,
                         {(round((c - 1) * pitch, 6), round((r - 1) * pitch,
                                                            6))
                          for r in range(3) for c in range(3)})

    def test_continuous_deck(self):
        """One deck elevation, and it is the highest surface in the tray."""
        deck = self.tray["elevations_mm"]["deck"]
        self.assertAlmostEqual(float(self.v[:, 2].max()), deck, places=9)
        on_deck = np.isclose(self.v[:, 2], deck)
        # the deck ring is a single connected surface, so its vertices
        # outnumber any single pocket's ring
        self.assertGreater(int(on_deck.sum()),
                           TOPOLOGY["pocket_segments"] * 9)

    def test_shared_cell_boundary_vertices(self):
        """Adjacent cells reuse indices — the reuse counter is non-zero and
        no two vertices share a position."""
        self.assertGreater(self.tray["shared_vertex_reuse_count"], 0)
        _, counts = np.unique(np.round(self.v, 6), axis=0,
                              return_counts=True)
        self.assertEqual(int((counts > 1).sum()), 0)

    def test_no_cracks_between_cells(self):
        """A crack shows up as a boundary edge; there are none."""
        he = _half_edges(self.f)
        _, counts = np.unique(np.sort(he, axis=1), axis=0,
                              return_counts=True)
        self.assertEqual(int((counts == 1).sum()), 0)
        self.assertEqual(int((counts != 2).sum()), 0)

    def test_no_t_junctions(self):
        self.assertEqual(mv.find_t_junctions(self.v, self.f), [])

    def test_manifold_and_watertight(self):
        rep = mv.validate_mesh("tray", self.tray)
        d = rep["diagnostics"]
        self.assertEqual(d["boundary_edges"], 0)
        self.assertEqual(d["non_manifold_edges"], 0)
        self.assertEqual(d["euler_characteristic"], 2)
        self.assertEqual(d["connected_components"], 1)
        self.assertEqual(d["self_intersecting_pairs"], 0)
        self.assertEqual(d["zero_area_faces"], 0)
        self.assertEqual(d["duplicate_faces"], 0)
        self.assertEqual(d["duplicate_vertices"], 0)
        self.assertTrue(rep["valid"], rep["findings"])

    def test_outward_normals(self):
        """Consistent winding, plus the three flat surfaces face the way
        they physically must."""
        he = _half_edges(self.f)
        directed = set(map(tuple, he))
        self.assertFalse([(a, b) for a, b in map(tuple, he)
                          if (b, a) not in directed])
        a = self.v[self.f[:, 0]]
        cr = np.cross(self.v[self.f[:, 1]] - a, self.v[self.f[:, 2]] - a)
        n = cr / np.linalg.norm(cr, axis=1)[:, None]
        cz = self.v[self.f].mean(axis=1)[:, 2]
        deck = np.isclose(cz, self.tray["elevations_mm"]["deck"])
        under = np.isclose(cz, self.tray["elevations_mm"]["underside"])
        floor = np.isclose(cz, self.tray["elevations_mm"]["pocket_floor"])
        self.assertTrue((n[deck][:, 2] > 0.99).all())
        self.assertTrue((n[under][:, 2] < -0.99).all())
        self.assertTrue((n[floor][:, 2] > 0.99).all())

    def test_positive_volume(self):
        a = self.v[self.f[:, 0]]
        cr = np.cross(self.v[self.f[:, 1]] - a, self.v[self.f[:, 2]] - a)
        vol = float(np.einsum("ij,ij->i", a, cr).sum() / 6.0)
        self.assertGreater(vol, 0.0)
        # cross-check against the analytic solid minus nine frusta
        w, d = SPEC["tray_width_mm"], SPEC["tray_depth_mm"]
        h = SPEC["deck_z_mm"] - SPEC["underside_z_mm"]
        p = self.tray["pockets"][0]
        r0, r1 = p["opening_radius_mm"], p["floor_radius_mm"]
        frustum = (math.pi * p["depth_mm"] / 3.0) * (r0 * r0 + r0 * r1
                                                     + r1 * r1)
        self.assertAlmostEqual(vol, w * d * h - 9 * frustum, delta=900.0)

    # --- contract -------------------------------------------------------
    def test_correct_tray_and_pocket_draft(self):
        rings = self.tray["pocket_profile_rings"]
        k = TOPOLOGY["fillet_arc_samples"]
        (r_top, z_top), (r_bot, z_bot) = rings[k], rings[k + 1]
        measured = math.degrees(math.atan2(r_top - r_bot, z_top - z_bot))
        self.assertAlmostEqual(measured, SPEC["pocket_draft_deg"], places=6)
        # the tray wall inset must match its own draft over the full height
        h = SPEC["deck_z_mm"] - SPEC["underside_z_mm"]
        self.assertAlmostEqual(
            self.tray["draft"]["tray_underside_inset_mm"],
            h * math.tan(math.radians(SPEC["tray_draft_deg"])), places=6)
        self.assertEqual(self.tray["draft"]["release_direction"], "UPWARD")

    def test_correct_pocket_floor_elevation(self):
        floor = self.tray["elevations_mm"]["pocket_floor"]
        self.assertAlmostEqual(floor, 2.50, places=9)
        on_floor = np.isclose(self.v[:, 2], floor)
        self.assertEqual(int(on_floor.sum()),
                         9 * (TOPOLOGY["pocket_segments"] + 1))
        self.assertAlmostEqual(float(self.v[:, 2].min()),
                               SPEC["underside_z_mm"], places=9)

    def test_no_underside_breakthrough(self):
        self.assertAlmostEqual(self.tray["pocket_floor_thickness_mm"], 1.0,
                               places=9)
        self.assertGreater(self.tray["pocket_floor_thickness_mm"], 0.0)
        rep = mv.validate_recessed_tray(self.tray, A.contract())
        self.assertNotIn(mv.POCKET_BREAKTHROUGH,
                         [f["code"] for f in rep["findings"]])

    def test_weld_free_construction(self):
        self.assertEqual(self.tray["weld_count"], 0)
        self.assertIsNone(self.tray["topology"]["weld_tolerance"])

    # --- pan relationships ----------------------------------------------
    def test_correct_pan_seating_and_exact_recess(self):
        rep = mv.validate_pan_seating(self.tray, A.contract())
        m = rep["measured"]
        self.assertAlmostEqual(m["pan_recess_mm"], 1.00, places=9)
        self.assertAlmostEqual(m["adhesive_gap_mm"], 0.15, places=9)
        codes = [f["code"] for f in rep["findings"]]
        self.assertNotIn(mv.PAN_FLOATS, codes)
        self.assertNotIn(mv.PAN_RECESS_MISMATCH, codes)

    def test_pan_pocket_interference_is_reported_not_repaired(self):
        """The contract triple (26.6 pocket / 0.6 floor fillet / sharp-
        cornered 26.0 pan) genuinely interferes. The validator must SAY so
        with a number, and must not adjust anything to hide it."""
        rep = mv.validate_pan_seating(self.tray, A.contract())
        codes = [f["code"] for f in rep["findings"]]
        self.assertIn(mv.PAN_POCKET_INTERSECTION, codes)
        self.assertLess(rep["measured"]["min_radial_clearance_mm"], 0.0)
        # the tightest point is the pan BASE, not the rim
        self.assertLess(rep["measured"]["clearance_at_pan_base_mm"],
                        rep["measured"]["clearance_at_pan_top_mm"])
        # nothing was mutated to make it pass
        self.assertEqual(_tray()["mesh_identity"],
                         self.tray["mesh_identity"])
        self.assertEqual(A._values(A.TRAY)["pocket_sharp_wall_theoretical_diameter_at_deck_mm"], 26.6)

    def test_solved_envelope_is_published(self):
        declared = A.declared_findings(self.tray)
        env = [f for f in declared
               if f["code"] == mv.PAN_POCKET_INTERSECTION]
        self.assertEqual(len(env), 1)
        self.assertLess(env[0]["max_floor_fillet_mm"],
                        SPEC["floor_fillet_mm"])
        self.assertGreater(env[0]["min_pocket_diameter_mm"],
                           SPEC["pocket_sharp_wall_theoretical_diameter_at_deck_mm"])

    def test_pan_clears_when_the_solved_fillet_is_used(self):
        """Proves the solved envelope is real — used only as a check, never
        written back into the contract."""
        declared = A.declared_findings(self.tray)
        env = next(f for f in declared
                   if f["code"] == mv.PAN_POCKET_INTERSECTION)
        relaxed = _tray(floor_fillet_mm=env["max_floor_fillet_mm"])
        rep = mv.validate_pan_seating(relaxed, A.contract())
        self.assertGreaterEqual(
            rep["measured"]["min_radial_clearance_mm"], -1e-6)
        self.assertEqual(A._values(A.TRAY)["floor_fillet_mm"], 0.6)

    # --- fail closed ----------------------------------------------------
    def test_missing_spec_key_fails_closed(self):
        for key in SPEC:
            spec = dict(SPEC)
            spec.pop(key)
            with self.assertRaises(RecessedTrayError):
                build_recessed_palette_tray(spec)

    def test_invalid_input_fails_closed(self):
        cases = {
            "elevation order": dict(pocket_floor_z_mm=9.0),
            "floor below underside": dict(underside_z_mm=3.0),
            "draft collapses floor": dict(pocket_draft_deg=80.0),
            "fillets overlap": dict(rim_fillet_mm=3.0, floor_fillet_mm=3.0),
            "field wider than tray": dict(pitch_mm=60.0),
            "pocket wider than pitch": dict(pocket_sharp_wall_theoretical_diameter_at_deck_mm=40.0),
            "tray draft collapses wall": dict(tray_draft_deg=80.0),
        }
        for label, over in cases.items():
            with self.subTest(label):
                with self.assertRaises(RecessedTrayError):
                    _tray(**over)

    def test_no_dimension_is_silently_repaired(self):
        """The builder never mutates the caller's spec."""
        spec = dict(SPEC)
        snapshot = copy.deepcopy(spec)
        build_recessed_palette_tray(spec)
        self.assertEqual(spec, snapshot)

    # --- authority ------------------------------------------------------
    def test_no_blender_boolean_dependency(self):
        """The kernel and section engine must build with no Blender in the
        module graph, and must declare themselves Boolean-free."""
        import apps.pipeline.services.palette_mesh_section as sec_mod
        import apps.pipeline.services.palette_recessed_tray_geometry as mod
        self.assertNotIn("bpy", sys.modules)
        for m in (mod, sec_mod):
            src = open(m.__file__).read()
            # the modules NAME the banned mechanism in their docstrings on
            # purpose; what must be absent is any call into it
            code = "\n".join(ln for ln in src.splitlines()
                             if not ln.lstrip().startswith("#"))
            for banned in ("import bpy", "bpy.", "modifiers.new",
                           "modifier_apply", "solver ="):
                self.assertNotIn(banned, code)
        self.assertTrue(self.tray["boolean_free"])
        self.assertEqual(self.tray["authority"],
                         "DETERMINISTIC_PYTHON_MESH_CONSTRUCTION")
        self.assertEqual(self.tray["blender_role"],
                         "VISUALIZATION_AND_RENDERING_ONLY")

    def test_render_script_refuses_boolean_config(self):
        path = ("apps/pipeline/services/blender_scripts/"
                "m4b_a_tray_views.py")
        src = open(path).read()
        self.assertIn('if cfg.get("csg")', src)
        self.assertNotIn("modifiers.new", src)

    def test_contract_holds_the_owner_stated_values(self):
        c = A.contract()
        self.assertEqual(c["tray_spec"]["pocket_sharp_wall_theoretical_diameter_at_deck_mm"], 26.6)
        self.assertEqual(c["tray_spec"]["deck_z_mm"], 7.15)
        self.assertEqual(c["tray_spec"]["pocket_floor_z_mm"], 2.50)
        self.assertEqual(c["pan"]["pan_seating_z_mm"], 2.65)
        self.assertEqual(c["pan"]["pan_top_z_mm"], 6.15)
        self.assertEqual(c["pan"]["pan_recess_mm"], 1.00)
        self.assertEqual(c["tray_spec"]["tray_draft_deg"], 1.5)
        self.assertEqual(c["tray_spec"]["pocket_draft_deg"], 2.0)
        self.assertEqual(c["authority"]["PALT_M5"], "BLOCKED")
        self.assertEqual(c["authority"]["PALT_P1_OWNER_APPROVAL"],
                         "REJECTED_PENDING_M4B")
        for key in ("pocket_sharp_wall_theoretical_diameter_at_deck_mm", "deck_z_mm"):
            self.assertEqual(c["provenance"][key]["authority"],
                             "OWNER_STATED_M4B_A_PRESERVED_VALUE")

    def test_pocket_diameter_divergence_is_declared(self):
        """26.6 is used; PAN_SYSTEM's 26.8 is untouched and the divergence
        is reported rather than reconciled."""
        from apps.pipeline.services.palette_moulded_geometry import PAN_SYSTEM
        self.assertEqual(PAN_SYSTEM["pocket_diameter_mm"], 26.8)
        codes = [f["code"] for f in A.declared_findings(self.tray)]
        self.assertIn(mv.CONTRACT_VALUE_DIVERGENCE, codes)
