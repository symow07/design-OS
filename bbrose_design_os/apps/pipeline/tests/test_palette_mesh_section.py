"""PALT-M4B-A — deterministic mesh-plane section tests.

The centre sections are exactly degenerate by construction: middle-row
pocket centres sit at y=0 and the 64-segment rings start at 45 deg, so
ring vertices land exactly on the plane. These tests pin that the engine
handles the on-plane cases rather than merely surviving them.
"""
import numpy as np
from django.test import SimpleTestCase

from apps.pipeline.services import palette_mesh_section as MS
from apps.pipeline.services import palette_moulded_validators as mv
from apps.pipeline.services import palt_m4b_a as A


def _cube(size=2.0, centre=(0.0, 0.0, 0.0)):
    h = size / 2.0
    cx, cy, cz = centre
    v = np.array([[cx - h, cy - h, cz - h], [cx + h, cy - h, cz - h],
                  [cx + h, cy + h, cz - h], [cx - h, cy + h, cz - h],
                  [cx - h, cy - h, cz + h], [cx + h, cy - h, cz + h],
                  [cx + h, cy + h, cz + h], [cx - h, cy + h, cz + h]],
                 dtype=float)
    f = np.array([[0, 3, 2], [0, 2, 1], [4, 5, 6], [4, 6, 7],
                  [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                  [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]],
                 dtype=np.int64)
    return {"vertices": v, "faces": f}


class SectionEngineTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.assembly = A.build_assembly()
        cls.tray = cls.assembly["tray"]
        cls.section = A.centre_section(cls.assembly)

    # --- basics ---------------------------------------------------------
    def test_cube_section_is_a_square(self):
        sec = MS.section_component("cube", **_cube(), axis="z", at=0.0)
        joined = MS.join_loops(sec)
        self.assertEqual(joined["loop_count"], 1)
        self.assertAlmostEqual(
            abs(joined["loops"][0]["signed_area_mm2"]), 4.0, places=9)

    def test_plane_missing_the_mesh_yields_nothing(self):
        sec = MS.section_component("cube", **_cube(), axis="z", at=9.0)
        self.assertEqual(sec["segments"], {})

    def test_interpolated_crossings_use_edge_keys(self):
        """An off-vertex plane must produce ("E", lo, hi) keys, and both
        triangles sharing an edge must agree bit-for-bit."""
        sec = MS.section_component("cube", **_cube(), axis="z", at=0.37)
        kinds = {k[0] for k in sec["points"]}
        self.assertEqual(kinds, {"E"})
        for key in sec["points"]:
            self.assertLess(key[1], key[2])       # canonical lo < hi
        joined = MS.join_loops(sec)
        self.assertEqual(joined["loop_count"], 1)

    # --- the real centre section ----------------------------------------
    def test_centre_section_closed_loops(self):
        self.assertEqual(self.section["open_loop_count"], 0)
        self.assertEqual(self.section["loop_count"], 7)
        for joined in self.section["components"].values():
            for loop in joined["loops"]:
                self.assertTrue(loop["closed"])
                self.assertGreater(abs(loop["signed_area_mm2"]), 0.0)

    def test_centre_section_hits_exact_on_plane_vertices(self):
        """Proves the degeneracy is real and is handled by vertex keys, not
        dodged by nudging the plane."""
        tray = self.section["components"]["recessed_palette_tray"]
        keys = [k for loop in tray["loops"] for k in loop["keys"]]
        self.assertTrue(all(k[0] == "V" for k in keys))
        self.assertEqual(self.section["at"], 0.0)

    def test_section_exposes_every_required_layer(self):
        layers = A._layers_exposed(self.section, self.tray,
                                   A._values(A.PAN))
        self.assertEqual(sorted(layers), sorted(A.SECTION_LAYERS))
        for name, present in layers.items():
            self.assertTrue(present, f"{name} not exposed")
        rep = mv.validate_section(self.section, layers)
        self.assertTrue(rep["valid"], rep["findings"])
        self.assertEqual(rep["missing_layers"], [])

    def test_section_elevations_match_the_contract(self):
        tray = self.section["components"]["recessed_palette_tray"]
        zs = MS.loop_elevations(tray)
        for z in (7.15, 2.5, 1.5):
            self.assertIn(z, zs)
        self.assertAlmostEqual(max(zs), 7.15, places=6)
        self.assertAlmostEqual(min(zs), 1.5, places=6)

    def test_section_area_matches_the_solid(self):
        """A true section, cross-checked analytically: full slab minus the
        three pocket profiles."""
        tray = self.section["components"]["recessed_palette_tray"]
        area = abs(tray["loops"][0]["signed_area_mm2"])
        w = self.tray["spec"]["tray_width_mm"]
        h = 7.15 - 1.5
        self.assertLess(area, w * h)
        self.assertGreater(area, w * h - 3 * 27.8 * 4.65)

    def test_three_pans_and_three_powders_in_the_middle_row(self):
        names = set(self.section["components"])
        self.assertEqual(
            len([n for n in names if n.startswith("metal_pan_")]), 3)
        self.assertEqual(
            len([n for n in names if n.startswith("powder_")]), 3)

    def test_deterministic_section_identity(self):
        again = A.centre_section(A.build_assembly())
        self.assertEqual(again["section_identity"],
                         self.section["section_identity"])

    def test_section_is_boolean_free(self):
        self.assertTrue(self.section["boolean_free"])
        self.assertEqual(self.section["authority"],
                         "DETERMINISTIC_PYTHON_MESH_PLANE_INTERSECTION")
        self.assertIsNone(self.section["topology"]["join_tolerance"])

    # --- caps -----------------------------------------------------------
    def test_cap_mesh_is_generated_and_covers_the_loop(self):
        tray = self.section["components"]["recessed_palette_tray"]
        loop = tray["loops"][0]
        cap = loop["cap"]
        self.assertEqual(cap["triangle_count"], loop["point_count"] - 2)
        pts = loop["points_2d"]
        total = 0.0
        for a, b, c in cap["triangles"]:
            total += abs(MS.polygon_area([pts[a], pts[b], pts[c]]))
        self.assertAlmostEqual(total, abs(loop["signed_area_mm2"]),
                               places=6)

    # --- fail closed ----------------------------------------------------
    def test_open_surface_fails_closed(self):
        """Remove a face and the section must refuse, not guess."""
        mesh = _cube()
        # drop a face the plane actually crosses, so the loop really opens
        mesh["faces"] = mesh["faces"][1:]
        sec = MS.section_component("open", **mesh, axis="x", at=0.0)
        with self.assertRaises(MS.SectionError) as ctx:
            MS.join_loops(sec)
        self.assertIn("open or ambiguous", str(ctx.exception))

    def test_unknown_axis_fails_closed(self):
        with self.assertRaises(MS.SectionError):
            MS.section_component("cube", **_cube(), axis="w", at=0.0)

    def test_ear_clipping_rejects_a_non_simple_polygon(self):
        with self.assertRaises(MS.SectionError):
            MS._ear_clip(np.array([[0.0, 0.0], [2.0, 2.0], [2.0, 0.0],
                                   [0.0, 2.0]]))

    def test_disjoint_solids_give_separate_loops(self):
        a = _cube(2.0, (-4.0, 0.0, 0.0))
        b = _cube(2.0, (4.0, 0.0, 0.0))
        merged = {"vertices": np.vstack([a["vertices"], b["vertices"]]),
                  "faces": np.vstack([a["faces"],
                                      b["faces"] + len(a["vertices"])])}
        sec = MS.section_component("pair", **merged, axis="z", at=0.0)
        joined = MS.join_loops(sec)
        self.assertEqual(joined["loop_count"], 2)
        self.assertEqual([lp["role"] for lp in joined["loops"]],
                         ["OUTER", "INNER"])
