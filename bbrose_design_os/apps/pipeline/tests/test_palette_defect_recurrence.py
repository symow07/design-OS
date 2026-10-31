"""PALT-M4C §3 — locks against the three defects that have recurred.

Each of these has already appeared more than once in this programme, in a
new module each time. They are pinned here as named regressions so a
fourth recurrence fails a test rather than reaching an owner review.
"""
import math

from django.test import SimpleTestCase

from apps.pipeline.services import palette_es3083_owner_confirmation as OC
from apps.pipeline.services import palette_profile_offset as PO
from apps.pipeline.services import palette_rect_pan as rect_pan
from apps.pipeline.services import palette_rect_tray_geometry as rt


class RadialOffsetRecurrenceTests(SimpleTestCase):
    """DEFECT 1 — offsetting in radius instead of along the normal.

    Appeared in the round pocket (A3R), the cup wall (A3F) and the
    rectangular pan (M4C §8). It delivers w*cos(obliquity) wherever the
    surface normal is not radial, so corners come out thin.
    """

    def test_the_rectangular_pan_wall_is_exactly_its_nominal_thickness(self):
        loop = rect_pan.rounded_rect_loop(24.0, 18.0, 2.0)
        for inset in (0.10, 0.25, 0.60):
            off = rect_pan._offset_loop(loop, inset)
            d = [math.hypot(a[0] - b[0], a[1] - b[1])
                 for a, b in zip(loop, off)]
            with self.subTest(inset=inset):
                self.assertAlmostEqual(min(d), inset, places=9)
                self.assertAlmostEqual(max(d), inset, places=9)

    def test_the_rectangular_pocket_wall_is_exactly_its_offset(self):
        c = rt.RECT_TRAY_DEFAULTS
        pr = c["pocket_sharp_wall_corner_radius_at_deck_mm"]
        rim = rt.rect_pocket_loop(0.0, 0.0,
                                  c["pocket_sharp_wall_width_at_deck_mm"],
                                  c["pocket_sharp_wall_height_at_deck_mm"],
                                  pr, rt.POCKET_SEGMENTS)
        for inward in (0.05, 0.30, 0.75):
            off = rt.offset_pocket_loop(rim, inward, corner_radius=pr)
            d = [math.hypot(a[0] - b[0], a[1] - b[1])
                 for a, b in zip(rim, off)]
            with self.subTest(inward=inward):
                self.assertAlmostEqual(min(d), inward, places=9)
                self.assertAlmostEqual(max(d), inward, places=9)

    def test_a_scaled_loop_would_have_failed_this_test(self):
        """Proves the assertion above can actually catch the defect: the
        WRONG construction is exercised here and must be rejected."""
        loop = rect_pan.rounded_rect_loop(24.0, 18.0, 2.0)
        inset = 0.25
        # the defect: move every point toward the rectangle CENTRE
        scaled = []
        for x, y, _, _ in loop:
            r = math.hypot(x, y) or 1.0
            scaled.append((x - x / r * inset, y - y / r * inset))
        d = [math.hypot(a[0] - b[0], a[1] - b[1])
             for a, b in zip(loop, scaled)]
        # centre-radial motion is uniform in magnitude but lands on the
        # WRONG curve; the corner clearance is what collapses
        hw, hd, r0 = 24.0 / 2 - 2.0, 18.0 / 2 - 2.0, 2.0
        corner_err = max(
            abs(math.hypot(abs(x) - hw, abs(y) - hd) - (r0 - inset))
            for (x, y), (ox, oy, _, _) in zip(scaled, loop)
            if abs(ox) > hw + 1e-9 and abs(oy) > hd + 1e-9)
        self.assertGreater(corner_err, 1e-3,
                           "the centre-radial construction must NOT land on "
                           "the true offset curve, or this guard is vacuous")
        self.assertAlmostEqual(min(d), inset, places=9)

    def test_the_meridional_kernel_still_fails_closed_on_a_cusp(self):
        """A concave arc offset past its own curvature radius has no valid
        offset curve. Clamping it silently is how the wall collapsed."""
        with self.assertRaises(PO.ProfileOffsetError) as ctx:
            PO.offset_primitive({"kind": PO.ARC, "centre": (10.0, 2.0),
                                 "radius": 0.40, "start_deg": 180.0,
                                 "end_deg": 270.0,
                                 "material_toward_centre": True}, 0.90)
        self.assertIn(PO.OFFSET_SINGULARITY, str(ctx.exception))

    def test_a_convex_arc_offsets_to_a_larger_radius(self):
        out = PO.offset_primitive({"kind": PO.ARC, "centre": (10.0, 2.0),
                                   "radius": 0.40, "start_deg": 0.0,
                                   "end_deg": 90.0,
                                   "material_toward_centre": False}, 0.25)
        self.assertAlmostEqual(out["radius"], 0.65, places=9)


class DatumConfusionRecurrenceTests(SimpleTestCase):
    """DEFECT 2 — a value measured at one datum used as a dimension
    defined at another. Appeared in M4B-A (26.6 layout module fed in as a
    fit dimension) and again in the rectangular tray."""

    def test_a_bare_pocket_dimension_is_refused(self):
        for key in ("pocket_width_mm", "pocket_height_mm",
                    "pocket_corner_radius_mm", "pocket_diameter_mm"):
            with self.subTest(key=key):
                with self.assertRaises(rt.RectTrayError) as ctx:
                    rt.build_rect_recessed_tray({key: 24.8})
                self.assertIn("does not name a datum", str(ctx.exception))

    def test_the_functional_envelope_names_its_datum(self):
        self.assertEqual(rect_pan.pocket_envelope()["datum"],
                         "FUNCTIONAL_CLEARANCE_AT_SEATING_DATUM")

    def test_the_two_datums_are_numerically_different(self):
        """If they were equal the conversion would be untested by
        construction and the guard would prove nothing."""
        sol = rt.POCKET_DATUM_SOLUTION
        env = rect_pan.pocket_envelope()
        self.assertGreater(
            abs(sol["pocket_sharp_wall_width_at_deck_mm"]
                - env["functional_width_at_seating_datum_mm"]), 1e-3)

    def test_feeding_the_functional_value_in_as_deck_input_tightens_fit(self):
        """The defect, exercised: build a tray from the functional numbers
        as if they were deck-plane input and show the fit gets tighter."""
        env = rect_pan.pocket_envelope()
        wrong = rt.build_rect_recessed_tray({
            "pocket_sharp_wall_width_at_deck_mm":
                env["functional_width_at_seating_datum_mm"],
            "pocket_sharp_wall_height_at_deck_mm":
                env["functional_height_at_seating_datum_mm"],
            "pocket_sharp_wall_corner_radius_at_deck_mm":
                env["functional_corner_radius_at_seating_datum_mm"]})
        z = rt.POCKET_DATUM_SOLUTION["seating_datum_z_mm"]
        c = rect_pan.contract_values()
        got = rt.functional_section(wrong, z)
        clearance = (got["width_mm"] - c["pan_width_mm"]) / 2
        self.assertLess(clearance, c["pocket_tolerance_mm"] - 1e-4,
                        "feeding the seating-datum value in as deck input "
                        "must measurably tighten the fit, or the datum "
                        "conversion is not doing anything")

    def test_the_correct_construction_delivers_the_contract_clearance(self):
        tray = rt.build_rect_recessed_tray()
        z = rt.POCKET_DATUM_SOLUTION["seating_datum_z_mm"]
        c = rect_pan.contract_values()
        sec = rt.functional_section(tray, z)
        self.assertAlmostEqual((sec["width_mm"] - c["pan_width_mm"]) / 2,
                               c["pocket_tolerance_mm"], places=6)


class HandCopiedValueRecurrenceTests(SimpleTestCase):
    """DEFECT 3 — a solved value replaced by a hand-copied constant, which
    then silently desynchronises when its source changes."""

    def test_the_tray_pocket_defaults_are_solved_not_typed(self):
        for key in ("pocket_sharp_wall_width_at_deck_mm",
                    "pocket_sharp_wall_height_at_deck_mm",
                    "pocket_sharp_wall_corner_radius_at_deck_mm"):
            self.assertAlmostEqual(rt.RECT_TRAY_DEFAULTS[key],
                                   rt.POCKET_DATUM_SOLUTION[key], places=9)

    def test_the_solution_moves_when_the_pan_contract_moves(self):
        d = rt.RECT_TRAY_DEFAULTS
        base = rt.POCKET_DATUM_SOLUTION["pocket_sharp_wall_width_at_deck_mm"]
        for tol in (0.30, 0.55):
            sol = rt.solve_rect_sharp_wall_for_functional(
                rect_pan.pocket_envelope({"pocket_tolerance_mm": tol}),
                deck_z=d["deck_z_mm"], floor_z=d["pocket_floor_z_mm"],
                draft_deg=d["pocket_draft_deg"],
                rim_fillet=d["rim_fillet_mm"],
                floor_fillet=d["floor_fillet_mm"])
            with self.subTest(tol=tol):
                self.assertNotAlmostEqual(
                    sol["pocket_sharp_wall_width_at_deck_mm"], base,
                    places=4)

    def test_the_tray_envelope_is_derived_from_the_pan_field(self):
        d = rt.RECT_TRAY_DEFAULTS
        margin = rt.POCKET_DATUM_SOLUTION["derived_border_margin_mm"]
        self.assertAlmostEqual(
            d["tray_width_mm"], d["cells_x"] * d["pitch_x_mm"] + 2 * margin,
            places=6)
        self.assertAlmostEqual(
            d["tray_depth_mm"], d["cells_y"] * d["pitch_y_mm"] + 2 * margin,
            places=6)


class OwnerConfirmationScopeTests(SimpleTestCase):
    """§1 — a visible-composition confirmation must not widen."""

    def test_it_refuses_to_be_authority_for_what_it_did_not_confirm(self):
        for claim in ("exact pan dimensions", "wall thickness",
                      "hinge construction", "clasp construction",
                      "manufacturing feasibility", "tolerances",
                      "thermoforming details", "hidden geometry",
                      "exact case dimensions"):
            with self.subTest(claim=claim):
                with self.assertRaises(OC.UnauthorizedInference):
                    OC.check_authority(f"derive {claim} from this")

    def test_it_does_not_block_what_the_owner_did_confirm(self):
        for claim in ("pan shape is RECTANGULAR", "12 pans in a 4 x 3 grid",
                      "PANTONE 621 C is a named colour reference"):
            OC.check_authority(claim)

    def test_the_owner_promoted_the_soft_grid_to_hard(self):
        intent = OC.confirmed_intent()
        for name, value in (("pan_count", 12), ("rows", 3), ("columns", 4)):
            f = intent.get(name)
            with self.subTest(name=name):
                self.assertEqual(f.value, value)
                self.assertEqual(f.constraint_level, "HARD_VISIBLE_CONSTRAINT")
                self.assertTrue(f.is_design_authority)

    def test_pantone_is_not_converted_numerically(self):
        rec = OC.owner_confirmation()
        self.assertEqual(rec["pantone_policy"]["state"],
                         "NAMED_REFERENCE_NOT_NUMERICALLY_CONVERTED")
        self.assertEqual(rec["pantone_policy"]["governs"], "THE_NAMED_TOKEN")

    def test_the_confirmation_grants_no_dimensional_authority(self):
        rec = OC.owner_confirmation()
        self.assertEqual(rec["scope"], "VISIBLE_COMPOSITION_ONLY")
        self.assertEqual(rec["PALT_P1_FINAL_DIMENSIONS"], "NOT_APPROVED")
        self.assertEqual(rec["PALT_P1_MANUFACTURING_AUTHORITY"],
                         "NOT_ESTABLISHED")
        self.assertEqual(rec["PALT_P1_OWNER_APPROVAL"], "NOT_GRANTED")
        self.assertEqual(rec["GATE_2"], "BLOCKED")

    def test_the_draft_is_not_mutated_by_confirmation(self):
        from apps.pipeline.services import palette_es3083_intent as es
        self.assertEqual(es.build_es3083_intent().get("pan_count")
                         .constraint_level, "SOFT_VISUAL_CONSTRAINT")
