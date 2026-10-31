"""M4B-B §2-§7 — the PALT-P1B moulded assembly for ES3083."""
import math

import numpy as np
from django.test import SimpleTestCase

from apps.pipeline.services import palette_es3083_owner_confirmation as OC
from apps.pipeline.services import palette_moulded_geometry as MG
from apps.pipeline.services import palette_moulded_rect as MR
from apps.pipeline.services import palette_moulded_validators as mv
from apps.pipeline.services import palette_rect_pan as RP


def _build():
    return MR.build_rect_components(OC.confirmed_intent())


class ComponentIntegrityTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comps, cls.dims = _build()

    def test_every_component_is_manifold_and_watertight(self):
        for name, comp in sorted(self.comps.items()):
            d = mv.validate_mesh(name, comp,
                                 check_self_intersection=False)["diagnostics"]
            with self.subTest(component=name):
                self.assertEqual(d["boundary_edges"], 0)
                self.assertEqual(d["non_manifold_edges"], 0)
                self.assertEqual(d["inconsistent_half_edges"], 0)
                self.assertEqual(d["euler_characteristic"], 2)

    def test_nothing_here_is_a_boolean_cutter(self):
        """P1A recesses with Blender Booleans. Tray geometry authority is
        deterministic Python, so P1B has no cutters at all."""
        man = MR.rect_manifest(self.comps, self.dims)
        self.assertTrue(man["boolean_free"])
        self.assertEqual(man["cutters"], [])
        self.assertEqual(man["geometry_authority"],
                         "DETERMINISTIC_PYTHON_MESH_CONSTRUCTION")
        for name in self.comps:
            self.assertNotIn("cutter", name)

    def test_it_is_deterministic(self):
        again, _ = _build()
        self.assertEqual(MR.rect_manifest(again, self.dims)
                         ["aggregate_identity"],
                         MR.rect_manifest(self.comps, self.dims)
                         ["aggregate_identity"])


class LidSystemTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comps, cls.dims = _build()

    def test_the_lid_is_a_hollow_shell_not_a_floating_plate(self):
        """A slab would enclose its full bounding volume; a real shell
        encloses far less because the cavity is genuine geometry."""
        v = self.comps["lid_outer_shell"]["vertices"]
        f = self.comps["lid_outer_shell"]["faces"]
        a = v[f[:, 0]]
        vol = abs(float(np.einsum("ij,ij->i", a,
                                  np.cross(v[f[:, 1]] - a,
                                           v[f[:, 2]] - a)).sum() / 6.0))
        span = v.max(axis=0) - v.min(axis=0)
        box = float(span[0] * span[1] * span[2])
        self.assertLess(vol / box, 0.55,
                        "the lid encloses too much of its bounding box to "
                        "be a hollow moulding")
        self.assertGreater(span[2], 3.0, "the lid has real height")

    def test_the_lid_cavity_opens_downward_onto_the_base(self):
        """A lid built opening upward is a shallow tray. It passes every
        manifold check and is obviously wrong the moment it is rendered,
        so the geometry has to say which way it faces."""
        v = self.comps["lid_outer_shell"]["vertices"]
        lo, hi = v[:, 2].min(), v[:, 2].max()
        band = 0.35
        bottom = v[np.abs(v[:, 2] - (lo + 0.2)) < band]
        top = v[np.abs(v[:, 2] - (hi - 0.2)) < band]
        self.assertGreater(
            len(bottom), len(top),
            "the open rim carries two rings and the closed roof one, so "
            "the bottom must hold more vertices than the top")

    def test_the_lid_carries_a_structural_rim(self):
        self.assertIn("lid_structural_rim", self.comps)
        rim = self.comps["lid_structural_rim"]["vertices"]
        lid = self.comps["lid_outer_shell"]["vertices"]
        self.assertLess(rim.max(axis=0)[0], lid.max(axis=0)[0])

    def test_the_lid_walls_are_drafted(self):
        """The lid releases upward, so it is widest at the parting line
        below and narrows toward the roof."""
        v = self.comps["lid_outer_shell"]["vertices"]
        lo = v[v[:, 2] < v[:, 2].min() + 0.01]
        hi = v[v[:, 2] > v[:, 2].max() - 0.01]
        self.assertGreater(lo[:, 0].max(), hi[:, 0].max(),
                           "the wall must taper from the parting line "
                           "toward the roof")

    def test_visible_proportions_come_from_the_confirmed_intent(self):
        """§3 — generic defaults may fill hidden construction only."""
        prov = self.dims["provenance"]
        self.assertEqual(prov["case_width_mm"], MR.VISIBLE)
        self.assertEqual(prov["case_depth_mm"], MR.VISIBLE)
        self.assertEqual(prov["pan_shape"], MR.VISIBLE)
        self.assertEqual(prov["wall_thickness"], MR.HIDDEN)
        self.assertEqual(prov["hinge_geometry"], MR.HIDDEN)

    def test_the_case_follows_the_es3083_pan_field(self):
        tray = self.dims["tray"]["spec"]
        self.assertAlmostEqual(
            self.dims["case_width_mm"],
            tray["tray_width_mm"] + 2 * MR.CONSTRUCTION["case_wall_mm"],
            places=6)


class HingeSystemTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comps, cls.dims = _build()

    def test_knuckles_alternate_between_lid_and_base(self):
        names = sorted(n for n in self.comps
                       if n.startswith("hinge_knuckle_"))
        self.assertEqual(len(names), MR.HINGE["knuckle_count"])
        owners = [n.split("_")[2] for n in
                  sorted(names, key=lambda s: int(s.rsplit("_", 1)[1]))]
        for a, b in zip(owners, owners[1:]):
            self.assertNotEqual(a, b, "knuckles must alternate")

    def test_the_barrel_axis_is_the_hinge_axis_not_a_standing_boss(self):
        """A knuckle standing on end reads as a boss, not a hinge."""
        for name in (n for n in self.comps
                     if n.startswith("hinge_knuckle_")):
            v = self.comps[name]["vertices"]
            span = v.max(axis=0) - v.min(axis=0)
            with self.subTest(component=name):
                self.assertGreater(span[0], span[2],
                                   "the barrel must be longer along the "
                                   "hinge axis than it is tall")

    def test_every_knuckle_shares_one_continuous_axis(self):
        axis_y = self.dims["hinge_axis_y_mm"]
        axis_z = self.dims["hinge_axis_z_mm"]
        for name in [n for n in self.comps
                     if n.startswith("hinge_knuckle_")] + ["hinge_pin"]:
            v = self.comps[name]["vertices"]
            with self.subTest(component=name):
                self.assertAlmostEqual((v[:, 1].min() + v[:, 1].max()) / 2,
                                       axis_y, places=6)
                self.assertAlmostEqual((v[:, 2].min() + v[:, 2].max()) / 2,
                                       axis_z, places=6)

    def test_the_pin_runs_through_every_knuckle(self):
        pin = self.comps["hinge_pin"]["vertices"]
        for name in (n for n in self.comps
                     if n.startswith("hinge_knuckle_")):
            v = self.comps[name]["vertices"]
            with self.subTest(component=name):
                self.assertLessEqual(pin[:, 0].min(), v[:, 0].min() + 1e-6)
                self.assertGreaterEqual(pin[:, 0].max(),
                                        v[:, 0].max() - 1e-6)

    def test_the_pin_is_retained_at_both_ends(self):
        pin = self.comps["hinge_pin"]["vertices"]
        for k in (1, 2):
            cap = self.comps[f"hinge_pin_cap_{k}"]["vertices"]
            with self.subTest(cap=k):
                self.assertGreater(
                    (cap[:, 1].max() - cap[:, 1].min()) / 2,
                    (pin[:, 1].max() - pin[:, 1].min()) / 2,
                    "a retention cap must be larger than the pin it holds")

    def test_the_pin_has_running_clearance_inside_the_knuckle(self):
        self.assertGreater(MR.HINGE["barrel_outer_radius_mm"],
                           MR.HINGE["pin_radius_mm"]
                           + MR.HINGE["pin_clearance_mm"])

    def test_the_hinge_roots_are_locally_reinforced(self):
        self.assertIn("hinge_reinforcement", self.comps)


class ArticulationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comps, cls.dims = _build()

    def _lid(self, state, **kw):
        return MR.compose_rect_state(self.comps, self.dims, state,
                                     **kw)["lid_outer_shell"]["vertices"]

    def test_closed_seats_the_lid_on_the_base(self):
        base = self.comps["base_outer_shell"]["vertices"]
        lid = self._lid("CLOSED")
        self.assertGreaterEqual(lid[:, 2].min(), base[:, 2].max() - 1e-6)

    def test_opening_lifts_the_lid_up_and_back_not_down(self):
        """A negative rotation swings the lid down through the base, which
        still renders as a closed palette from most angles."""
        base = self.comps["base_outer_shell"]["vertices"]
        for state in ("OPEN_90", "OPEN_REVIEW_ANGLE"):
            lid = self._lid(state)
            with self.subTest(state=state):
                self.assertGreater(lid[:, 2].max(), base[:, 2].max() + 20.0)
                self.assertGreaterEqual(lid[:, 2].min(), -1e-6)
                self.assertLess(lid[:, 1].max(), 0.0,
                                "an opened lid sits behind the hinge axis")

    def test_a_larger_angle_leans_the_lid_further_back(self):
        self.assertLess(self._lid("OPEN_REVIEW_ANGLE")[:, 1].min(),
                        self._lid("OPEN_90")[:, 1].min())

    def test_the_open_stop_is_enforced(self):
        with self.assertRaises(MR.RectAssemblyError):
            MR.compose_rect_state(self.comps, self.dims,
                                  "OPEN_REVIEW_ANGLE", open_angle_deg=130.0)

    def test_exploded_separates_the_groups(self):
        state = MR.compose_rect_state(self.comps, self.dims, "EXPLODED")
        self.assertGreater(state["lid_outer_shell"]["vertices"][:, 2].min(),
                           state["metal_pan_1"]["vertices"][:, 2].min())

    def test_an_unknown_state_is_refused(self):
        with self.assertRaises(MR.RectAssemblyError):
            MR.compose_rect_state(self.comps, self.dims, "AJAR")


class ClaspSystemTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comps, cls.dims = _build()

    def test_every_named_clasp_feature_exists(self):
        for part in ("clasp_hook", "clasp_hook_lip", "clasp_detent",
                     "clasp_flex_zone", "clasp_finger_notch",
                     "clasp_reinforcement"):
            self.assertIn(part, self.comps)

    def test_the_clasp_is_visible_at_review_resolution(self):
        """No invisible or symbolic clasp."""
        hook = self.comps["clasp_hook"]["vertices"]
        span = hook.max(axis=0) - hook.min(axis=0)
        self.assertGreater(span[0], 10.0)
        self.assertGreater(span[2], 2.0)

    def test_the_hook_and_detent_engage_with_clearance(self):
        self.assertGreater(MR.CLASP["hook_lip_mm"], 0.0)
        self.assertGreater(MR.CLASP["detent_depth_mm"],
                           MR.CLASP["release_clearance_mm"])
        self.assertGreater(MR.CLASP["engagement_depth_mm"], 0.0)

    def test_the_hook_travels_with_the_lid(self):
        self.assertIn("clasp_hook", MR.LID_GROUP)
        self.assertNotIn("clasp_detent", MR.LID_GROUP)
        opened = MR.compose_rect_state(self.comps, self.dims, "OPEN_90")
        self.assertFalse(np.allclose(opened["clasp_hook"]["vertices"],
                                     self.comps["clasp_hook"]["vertices"]))
        self.assertTrue(np.allclose(opened["clasp_detent"]["vertices"],
                                    self.comps["clasp_detent"]["vertices"]))


class MirrorStateTests(SimpleTestCase):
    def test_es3083_does_not_establish_a_mirror(self):
        """§6 — do not invent one as a hard design fact."""
        _c, dims = _build()
        self.assertEqual(dims["mirror_state"], MR.UNRESOLVED)

    def test_no_mirror_geometry_is_built_when_unresolved(self):
        comps, _ = _build()
        self.assertNotIn("mirror", comps)
        self.assertNotIn("mirror_adhesive_pad", comps)

    def test_the_full_stack_is_built_when_a_mirror_is_configured(self):
        comps, dims = MR.build_rect_components(OC.confirmed_intent(),
                                               include_mirror=True)
        self.assertEqual(dims["mirror_state"], MR.CONFIRMED)
        for part in ("mirror", "mirror_adhesive_pad",
                     "mirror_retaining_border"):
            self.assertIn(part, comps)
            d = mv.validate_mesh(part, comps[part],
                                 check_self_intersection=False)["diagnostics"]
            self.assertEqual(d["euler_characteristic"], 2)

    def test_the_mirror_sits_inside_its_retaining_border(self):
        comps, _ = MR.build_rect_components(OC.confirmed_intent(),
                                            include_mirror=True)
        m = comps["mirror"]["vertices"]
        b = comps["mirror_retaining_border"]["vertices"]
        self.assertGreater(m.min(axis=0)[0], b.min(axis=0)[0])
        self.assertLess(m.max(axis=0)[0], b.max(axis=0)[0])


class PanSystemTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comps, cls.dims = _build()

    def test_twelve_rectangular_pans_with_powder(self):
        self.assertEqual(sum(1 for n in self.comps
                             if n.startswith("metal_pan_")), 12)
        self.assertEqual(sum(1 for n in self.comps
                             if n.startswith("powder_")), 12)

    def test_the_datum_solver_is_still_in_the_path(self):
        """Never feed a functional seating dimension into a deck-mouth
        field."""
        from apps.pipeline.services import palette_rect_tray_geometry as rt
        for key in ("pocket_width_mm", "pocket_height_mm",
                    "pocket_corner_radius_mm"):
            with self.subTest(key=key):
                with self.assertRaises(rt.RectTrayError):
                    rt.build_rect_recessed_tray({key: 24.8})

    def test_each_pan_sits_in_a_pocket_with_clearance(self):
        c = RP.contract_values()
        for p in self.dims["tray"]["pockets"]:
            self.assertGreater(p["opening_width_mm"], c["pan_width_mm"])
            self.assertGreater(p["opening_height_mm"], c["pan_height_mm"])

    def test_powder_sits_above_the_pan_floor(self):
        pan = self.comps["metal_pan_1"]["vertices"]
        pw = self.comps["powder_1"]["vertices"]
        self.assertGreater(pw[:, 2].min(), pan[:, 2].min())


class P1ANotBrokenTests(SimpleTestCase):
    """The owner's constraint: P1B must not break P1A."""

    def test_the_round_assembly_still_builds_unchanged(self):
        comps, _dims = MG.build_moulded_components()
        self.assertEqual(sum(1 for n in comps
                             if n.startswith("metal_pan_")), 9)

    def test_the_two_families_are_separate_schemas(self):
        self.assertNotEqual(MR.SCHEMA, MG.SCHEMA)
        self.assertEqual(MR.SCHEMA, "palt_p1b_moulded_assembly/1.0")

    def test_p1b_claims_no_dimensional_or_manufacturing_authority(self):
        _c, dims = _build()
        self.assertEqual(dims["PALT_P1_FINAL_DIMENSIONS"], "NOT_APPROVED")
        self.assertEqual(dims["PALT_P1_MANUFACTURING_AUTHORITY"],
                         "NOT_ESTABLISHED")
