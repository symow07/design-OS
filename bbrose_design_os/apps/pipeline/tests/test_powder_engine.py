"""M6 §3 — the powder contract: identities separated, validation
fail-closed, every rule with a negative."""
from django.test import SimpleTestCase

from apps.pipeline.services import palette_powder_engine as PE
from apps.pipeline.services import palette_powder_protocol as PP


def _shade(name="prov_test", rgb=(0.5, 0.4, 0.3)):
    return PE.PowderShade(name, rgb, PE.PROVISIONAL_VISUALIZATION_SHADE)


class SpecValidationTests(SimpleTestCase):
    def test_every_family_constructs_with_defaults(self):
        for i, family in enumerate(PE.FAMILIES):
            spec = PE.PowderMaterialSpec(family, _shade(), seed=i)
            self.assertEqual(spec.family, family)
            self.assertTrue(spec.material_identity())

    def test_unknown_family_refused(self):
        with self.assertRaises(PE.PowderSpecError):
            PE.PowderMaterialSpec("VELVET", _shade(), seed=1)

    def test_foreign_structural_block_refused(self):
        """A GLITTER particle census on a MATTE spec is a category
        error, not a default to be ignored."""
        with self.assertRaises(PE.PowderSpecError) as ctx:
            PE.PowderMaterialSpec(
                PP.POWDER_MATTE, _shade(), seed=1,
                overrides={"particles": {"coverage": 0.5}})
        self.assertIn("structural block", str(ctx.exception))

    def test_unknown_nested_parameter_refused(self):
        with self.assertRaises(PE.PowderSpecError):
            PE.PowderMaterialSpec(
                PP.SHIMMER, _shade(), seed=1,
                overrides={"flakes": {"glitteriness": 1.0}})

    def test_cream_refuses_granular_microtexture(self):
        with self.assertRaises(PE.PowderSpecError):
            PE.PowderMaterialSpec(
                PP.CREAM, _shade(), seed=1,
                overrides={"microtexture": {"strength": 0.3}})

    def test_marbling_ratio_must_sum_to_one(self):
        with self.assertRaises(PE.PowderSpecError):
            PE.PowderMaterialSpec(
                PP.MARBLED, _shade(), seed=1,
                overrides={"marbling": {"mixing_ratio": [0.9, 0.5]}})

    def test_pantone_shade_name_refused(self):
        with self.assertRaises(PE.PowderSpecError):
            PE.PowderShade("PANTONE 621 C proxy", (0.5, 0.5, 0.5),
                           PE.PROVISIONAL_VISUALIZATION_SHADE)

    def test_unknown_colour_authority_refused(self):
        # argument changed from "OWNER_CONFIRMED" only because
        # OWNER_CHOSEN_DESIGN_INTENT was admitted; the string below is
        # genuinely not admitted and the guard is unweakened. A tier
        # STRONGER than the one admitted must still be refused, which is
        # the case this now covers.
        with self.assertRaises(PE.PowderSpecError):
            PE.PowderShade("x", (0.5, 0.5, 0.5), "OWNER_MEASURED_LAB")


class IdentitySeparationTests(SimpleTestCase):
    def test_material_only_change_keeps_geometry_identity(self):
        a = PE.PowderMaterialSpec(PP.POWDER_MATTE, _shade(), seed=1)
        b = PE.PowderMaterialSpec(
            PP.POWDER_MATTE, _shade("prov_other", (0.2, 0.3, 0.4)),
            seed=2)
        self.assertNotEqual(a.material_identity(), b.material_identity())
        self.assertEqual(a.geometry_state_identity(),
                         b.geometry_state_identity())

    def test_baked_dome_moves_geometry_identity_only_for_baked(self):
        matte = PE.PowderMaterialSpec(PP.POWDER_MATTE, _shade(), seed=1)
        baked = PE.PowderMaterialSpec(PP.BAKED, _shade(), seed=1)
        self.assertNotEqual(matte.geometry_state_identity(),
                            baked.geometry_state_identity())
        # the baked crown is the dome height — one number, not two
        self.assertEqual(baked.params["crown_height_mm"],
                         baked.params["dome"]["crown_height_mm"])

    def test_evidence_identity_is_the_pair(self):
        spec = PE.PowderMaterialSpec(PP.SHIMMER, _shade(), seed=3)
        e1 = PE.powder_evidence_identity("mesh_aaaa", spec)
        e2 = PE.powder_evidence_identity("mesh_bbbb", spec)
        self.assertNotEqual(e1, e2)
        self.assertNotEqual(e1, spec.material_identity())

    def test_seed_changes_material_identity(self):
        a = PE.PowderMaterialSpec(PP.GLITTER, _shade(), seed=1)
        b = PE.PowderMaterialSpec(PP.GLITTER, _shade(), seed=2)
        self.assertNotEqual(a.material_identity(), b.material_identity())

    def test_identities_are_deterministic(self):
        a = PE.PowderMaterialSpec(PP.MARBLED, _shade(), seed=7)
        b = PE.PowderMaterialSpec(PP.MARBLED, _shade(), seed=7)
        self.assertEqual(a.material_identity(), b.material_identity())
        self.assertEqual(a.to_dict(), b.to_dict())


class GlitterRigPlacementTests(SimpleTestCase):
    """§1 — the mirror source is computed from the rig contract, and a
    drift in either the camera or the override math must fail here."""

    def test_the_mirror_direction_is_recomputed_from_the_rig(self):
        import math
        from apps.pipeline.services import palette_powder_rigs as PR
        from apps.pipeline.services import (
            palette_characterization_rig as CR)
        cam = CR.RIG["camera"]
        over = PR.mirror_source_overrides()["specular_source"]
        self.assertEqual(over["elevation"], cam["elevation"])
        self.assertEqual(over["azimuth"],
                         (cam["azimuth"] + 180.0) % 360.0)
        # apparatus verbatim from the proven compact source
        src = CR.RIG["specular_source"]
        self.assertEqual(over["size"], src["size"])
        self.assertEqual(over["distance"], src["distance"])
        self.assertEqual(over["energy"], src["energy"])
        # the placement record's reflection vector really is the mirror
        rec = PR.placement_record()
        cam_vec = rec["camera_vector_surface_to_camera"]
        refl = rec["reflection_vector"]
        self.assertAlmostEqual(refl[2], cam_vec[2])
        self.assertAlmostEqual(refl[0], -cam_vec[0])
        self.assertAlmostEqual(refl[1], -cam_vec[1])
        self.assertAlmostEqual(
            math.hypot(*refl), 1.0, places=6)
        self.assertTrue(rec["sanity"]["reflection_z_positive"])
        self.assertEqual(rec["sanity"]["azimuth_delta_deg"], 180.0)

    def test_the_census_law_is_pinned(self):
        from apps.pipeline.services import palette_powder_rigs as PR
        self.assertEqual(PR.EVENT_LUMINANCE_FACTOR, 1.8)
        self.assertEqual(PR.EVENT_MIN_AREA_PX, 4)
        self.assertEqual(PR.EVENT_MAX_AREA_PX, 2000)
        self.assertEqual(PR.GLITTER_MIN_EVENTS, 25)
        self.assertEqual(PR.CONTROL_MAX_EVENTS, 5)


class ProvisionalShadeSetTests(SimpleTestCase):
    def test_twelve_rows_cover_the_required_families(self):
        rows = PE.es3083_provisional_shade_set()
        self.assertEqual(len(rows), 12)
        self.assertEqual([r["pan"] for r in rows], list(range(1, 13)))
        families = {r["spec"].family for r in rows}
        for required in (PP.POWDER_MATTE, PP.POWDER_SATIN, PP.SHIMMER,
                         PP.POWDER_METALLIC, PP.GLITTER, PP.BAKED,
                         PP.MARBLED):
            self.assertIn(required, families)

    def test_every_shade_is_provisional_never_owner_colour(self):
        for row in PE.es3083_provisional_shade_set():
            d = row["spec"].shade.to_dict()
            self.assertEqual(d["authority"],
                             PE.PROVISIONAL_VISUALIZATION_SHADE)
            self.assertEqual(d["owner_colour_authority"],
                             PE.NOT_OWNER_COLOUR_AUTHORITY)

    def test_light_medium_dark_are_all_present(self):
        rows = PE.es3083_provisional_shade_set()
        lum = [sum(r["spec"].shade.rgb) / 3.0 for r in rows]
        self.assertGreater(max(lum), 0.75)
        self.assertLess(min(lum), 0.25)

    def test_fb3093_spec_is_pressed_powder(self):
        spec = PE.fb3093_pressed_spec()
        self.assertEqual(spec.family, PP.PRESSED_POWDER)
        self.assertIn("press", spec.params)


class OwnerShadeSetTests(SimpleTestCase):
    """The owner's settled twelve for ES3083, decided 2026-08-13.

    These are CHOSEN colours, not measured ones. Every test below
    guards that distinction rather than the colours themselves.
    """

    def test_twelve_rows_pans_one_to_twelve_no_gaps(self):
        rows = PE.es3083_owner_shade_set()
        self.assertEqual(len(rows), 12)
        self.assertEqual([r["pan"] for r in rows], list(range(1, 13)))

    def test_every_shade_is_owner_chosen_and_never_measured(self):
        for row in PE.es3083_owner_shade_set():
            d = row["spec"].shade.to_dict()
            with self.subTest(pan=row["pan"]):
                self.assertEqual(d["authority"],
                                 PE.OWNER_CHOSEN_DESIGN_INTENT)
                self.assertEqual(d["owner_colour_authority"],
                                 PE.OWNER_DESIGN_INTENT_NOT_MEASURED)

    def test_every_rgb_round_trips_to_its_recorded_hex(self):
        """The hex is the authority; the triple is derived from it."""
        for meta, row in zip(PE.ES3083_OWNER_SHADES,
                             PE.es3083_owner_shade_set()):
            rgb = row["spec"].shade.rgb
            h = meta["hex"].lstrip("#")
            for i, chan in enumerate((0, 2, 4)):
                with self.subTest(pan=meta["pan"], channel=i):
                    self.assertAlmostEqual(
                        rgb[i], int(h[chan:chan + 2], 16) / 255,
                        delta=1 / 255)

    def test_no_shade_name_carries_a_pantone_token(self):
        """The construction guard covers the class; this covers the
        data, because a Pantone name here would read as a fabricated
        conversion of a colour nobody specified."""
        for row in PE.es3083_owner_shade_set():
            with self.subTest(pan=row["pan"]):
                self.assertNotIn("PANTONE",
                                 row["spec"].shade.name.upper())

    def test_every_family_named_is_a_real_powder_family(self):
        for row in PE.es3083_owner_shade_set():
            with self.subTest(pan=row["pan"]):
                self.assertIn(row["spec"].family, PP.POWDER_FAMILIES)

    def test_the_two_load_bearing_finish_notes_travel_with_the_shade(self):
        """Moss Garden's marbling and Midnight Bloom's family choice are
        decisions a renderer must see. A note left in a comment is a
        note the renderer never reads."""
        notes = {m["pan"]: m.get("finish_note", "")
                 for m in PE.ES3083_OWNER_SHADES}
        self.assertIn("NOT bright gold veining", notes[11])
        self.assertIn("POWDER_METALLIC", notes[12])

    def test_the_seed_is_the_pan_number(self):
        for row in PE.es3083_owner_shade_set():
            with self.subTest(pan=row["pan"]):
                self.assertEqual(row["spec"].seed, row["pan"])

    def test_srgb_to_linear_is_the_declared_transfer(self):
        """Named, not a hunch: IEC 61966-2-1. Anchors and the knee are
        checked so a silently swapped gamma cannot pass."""
        self.assertEqual(PE.SRGB_TRANSFER_FUNCTION,
                         "IEC_61966_2_1_sRGB_EOTF")
        self.assertAlmostEqual(PE.srgb_to_linear(0.0), 0.0, places=9)
        self.assertAlmostEqual(PE.srgb_to_linear(1.0), 1.0, places=9)
        self.assertAlmostEqual(PE.srgb_to_linear(0.04045),
                               0.04045 / 12.92, places=9)
        # the mid-tone that makes the difference visible
        self.assertAlmostEqual(PE.srgb_to_linear(0.5), 0.2140, places=4)

    def test_a_linear_value_is_never_stored_as_the_shade(self):
        """Step 4(b): the sRGB hex stays the authority and the linear
        form is derived. If the shade ever held the linear triple this
        assertion is what says so."""
        for meta, row in zip(PE.ES3083_OWNER_SHADES,
                             PE.es3083_owner_shade_set()):
            with self.subTest(pan=meta["pan"]):
                self.assertEqual(row["spec"].shade.rgb,
                                 PE.hex_to_srgb_triple(meta["hex"]))


class ProvisionalFixtureUnchangedTests(SimpleTestCase):
    """The guard against the fixture being quietly repurposed as the
    product. It has a different job and it is why GLITTER stays
    exercised."""

    def test_still_twelve_rows_all_provisional_never_owner_colour(self):
        rows = PE.es3083_provisional_shade_set()
        self.assertEqual(len(rows), 12)
        self.assertEqual([r["pan"] for r in rows], list(range(1, 13)))
        for row in rows:
            d = row["spec"].shade.to_dict()
            with self.subTest(pan=row["pan"]):
                self.assertEqual(d["authority"],
                                 PE.PROVISIONAL_VISUALIZATION_SHADE)
                self.assertEqual(d["owner_colour_authority"],
                                 PE.NOT_OWNER_COLOUR_AUTHORITY)

    def test_the_fixture_still_exercises_glitter(self):
        families = {r["spec"].family
                    for r in PE.es3083_provisional_shade_set()}
        self.assertIn(PP.GLITTER, families)

    def test_the_two_sets_are_disjoint_in_name_and_authority(self):
        prov = {r["spec"].shade.name
                for r in PE.es3083_provisional_shade_set()}
        owner = {r["spec"].shade.name
                 for r in PE.es3083_owner_shade_set()}
        self.assertEqual(prov & owner, set())
        # the prov_ prefix belongs to the fixture and would misstate the
        # authority of the owner's shades
        self.assertTrue(all(n.startswith("prov_") for n in prov))
        self.assertFalse(any(n.startswith("prov_") for n in owner))


class TransferDirectionTests(SimpleTestCase):
    """The direction of the colour-space error, PROVEN not asserted.

    A committed record (6341794) said these shades render "materially
    darker than chosen". That was INVERTED. srgb_to_linear is strictly
    BELOW the identity on (0, 1), so an sRGB value handed to a
    scene-linear socket is an albedo that is too HIGH, and the surface
    can only ever arrive LIGHTER and less saturated. These tests exist
    so the claim cannot be inverted again by prose.
    """

    def test_srgb_to_linear_is_strictly_below_identity_on_the_open_range(self):
        """Densely sampled: 20001 points across (0, 1)."""
        n = 20001
        for i in range(1, n):
            x = i / n
            with self.subTest(x=x):
                self.assertLess(PE.srgb_to_linear(x), x)

    def test_the_endpoints_are_fixed_points_not_violations(self):
        """0 and 1 are EQUAL, not less — which is why the claim is
        stated on the OPEN interval and the test above starts at 1/n."""
        self.assertEqual(PE.srgb_to_linear(0.0), 0.0)
        self.assertEqual(PE.srgb_to_linear(1.0), 1.0)
        self.assertEqual(PE.linear_to_srgb(0.0), 0.0)
        self.assertAlmostEqual(PE.linear_to_srgb(1.0), 1.0, places=12)

    def test_the_two_segments_meet_at_the_knee(self):
        """0.04045 encoded / 0.0031308 linear. A discontinuity here
        would make every claim below piecewise-false."""
        self.assertAlmostEqual(PE.srgb_to_linear(0.04045),
                               0.04045 / 12.92, places=15)
        self.assertAlmostEqual(PE.linear_to_srgb(0.0031308),
                               0.0031308 * 12.92, places=15)

    def test_the_oetf_is_strictly_above_identity_so_arrival_is_lighter(self):
        n = 20001
        for i in range(1, n):
            L = i / n
            with self.subTest(L=L):
                self.assertGreater(PE.linear_to_srgb(L), L)

    def test_the_two_transfers_round_trip(self):
        for i in range(1, 1000):
            x = i / 1000
            with self.subTest(x=x):
                self.assertAlmostEqual(
                    PE.linear_to_srgb(PE.srgb_to_linear(x)), x, places=12)

    def test_the_deep_end_is_hurt_far_more_than_the_light_end(self):
        """The finding is NOT a uniform shift. The error grows as the
        shade deepens, which is what compresses the palette's own depth
        run rather than merely brightening it."""
        light = PE.linear_to_srgb(0.9490) - 0.9490      # Petal Veil R
        deep = PE.linear_to_srgb(0.1804) - 0.1804       # Midnight Bloom G
        self.assertLess(light, 0.03)
        self.assertGreater(deep, 0.25)
        self.assertGreater(deep, light * 8)

    def test_the_depth_run_compresses(self):
        """Damascena -> Blush Hour -> Old Rose -> Thorn. The run's
        intended range shrinks on arrival; the structure degrades."""
        def mean_of(hx):
            return sum(PE.hex_to_srgb_triple(hx)) / 3.0

        def arrival_mean(hx):
            return sum(PE.linear_to_srgb(c)
                       for c in PE.hex_to_srgb_triple(hx)) / 3.0

        run = ("#D9A2A6", "#C57E82", "#8D5459", "#5D3A42")
        intended = mean_of(run[0]) - mean_of(run[-1])
        arrives = arrival_mean(run[0]) - arrival_mean(run[-1])
        self.assertLess(arrives, intended)
        # the run retains under three quarters of its intended spread
        self.assertLess(arrives / intended, 0.75)


#: The twelve provisional material identities as they stood BEFORE the
#: colour-space act of 2026-08-13, captured from the tree before a line
#: of it was edited. Recommendation (e)'s entire justification was that
#: none of these would move; this is what holds it to that.
PRE_COLOUR_SPACE_PROVISIONAL_IDENTITIES = {
    1: "7d93f904338efca3", 2: "8d32fbfdde26714b", 3: "bc9846891902d645",
    4: "6b2042ca34efdd89", 5: "3f5bd6dd57a92d7c", 6: "b49f4307fcfbad51",
    7: "b054b5654b0c4e32", 8: "17887c348292e96d", 9: "359ae17268b138d8",
    10: "a116f893b11f4ea1", 11: "b91793eb79c8b4a0", 12: "5608df660530657e",
}
PRE_COLOUR_SPACE_OWNER_IDENTITIES = {
    1: "cf453f50d0cf8821", 2: "0bb669c8bc29fa54", 3: "5c1958b87e36401a",
    4: "0fbabda62796e634", 5: "cdef405be5f3a688", 6: "40e337533247a857",
    7: "dbe60ac195e7104c", 8: "59aee44c3d5a1fdd", 9: "9a93235d6b010351",
    10: "64d020884b8502a7", 11: "f16682b607e0fae4", 12: "4dfb3281c2aee351",
}


class ColourSpaceMappingTests(SimpleTestCase):
    """Recommendation (e): the space rides on the authority, which is
    already digested, so no identity moves."""

    def test_the_mapping_is_total_over_the_admitted_authorities(self):
        self.assertEqual(set(PE.COLOUR_SPACE_BY_AUTHORITY),
                         set(PE.SHADE_AUTHORITIES))
        for space in PE.COLOUR_SPACE_BY_AUTHORITY.values():
            self.assertIn(space, PE.TRANSFORM_TO_SCENE_LINEAR)

    def test_an_unmapped_authority_raises_rather_than_defaulting(self):
        """The same discipline as OWNER_COLOUR_AUTHORITY_BY_AUTHORITY: an
        authority admitted without a space decided must stop, not fall
        through to whichever branch looks safe."""
        # hex-derived, not a raw triple: an owner-authority shade built
        # from raw numbers IS the class 23 hole, and a test that models
        # it teaches the pattern it is meant to fence
        shade = PE.PowderShade("Petal Veil",
                               PE.hex_to_srgb_triple("#F2E3D8"),
                               PE.OWNER_CHOSEN_DESIGN_INTENT)
        spec = PE.PowderMaterialSpec(PP.POWDER_MATTE, shade, seed=1)
        original = dict(PE.COLOUR_SPACE_BY_AUTHORITY)
        try:
            del PE.COLOUR_SPACE_BY_AUTHORITY[PE.OWNER_CHOSEN_DESIGN_INTENT]
            with self.assertRaises(KeyError):
                spec.realize()
        finally:
            PE.COLOUR_SPACE_BY_AUTHORITY.clear()
            PE.COLOUR_SPACE_BY_AUTHORITY.update(original)

    def test_the_undeclared_space_asserts_nothing_about_the_triples(self):
        """It records that nobody said, not that they are scene-linear."""
        self.assertEqual(
            PE.COLOUR_SPACE_BY_AUTHORITY[PE.PROVISIONAL_VISUALIZATION_SHADE],
            PE.AUTHORED_COLOUR_SPACE_UNDECLARED)
        self.assertFalse(PE.TRANSFORM_TO_SCENE_LINEAR[
            PE.AUTHORED_COLOUR_SPACE_UNDECLARED])

    def test_the_module_mapping_equals_the_bound_record(self):
        """Step 2 — the mapping is an input to a value a rendered frame
        depends on, so it may not drift silently. Editing the module
        fails here; editing the record moves the manifest digest and the
        gate refuses."""
        import json
        import pathlib
        repo = pathlib.Path(PE.__file__).resolve().parents[3]
        rec = json.loads((repo / "docs/roadmap/palt_m6"
                          / "shade_colour_space_binding.json").read_text())
        self.assertEqual(rec["COLOUR_SPACE_BY_AUTHORITY"],
                         dict(PE.COLOUR_SPACE_BY_AUTHORITY))
        self.assertEqual(rec["TRANSFORM_TO_SCENE_LINEAR"],
                         dict(PE.TRANSFORM_TO_SCENE_LINEAR))
        self.assertEqual(rec["SHADE_AUTHORITIES"],
                         list(PE.SHADE_AUTHORITIES))
        self.assertEqual(rec["transfer_function"],
                         PE.SRGB_TRANSFER_FUNCTION)


class RealizeColourSpaceTests(SimpleTestCase):
    def test_owner_shades_realize_transformed_per_channel(self):
        for row in PE.es3083_owner_shade_set():
            r = row["spec"].realize()
            with self.subTest(pan=row["pan"]):
                self.assertTrue(r["colour_transform_applied"])
                self.assertEqual(r["shader_input_colour_space"],
                                 PE.SCENE_LINEAR)
                self.assertEqual(r["authored_colour_space"],
                                 PE.AUTHORED_SRGB)
                for got, stored in zip(r["shader_input_rgb"],
                                       row["spec"].shade.rgb):
                    self.assertAlmostEqual(got, PE.srgb_to_linear(stored),
                                           places=12)

    def test_provisional_shades_realize_UNCHANGED(self):
        """The test that protects the M6 corpus. Every M6 measurement was
        taken through a provisional shade; if any of these moved, every
        frame in the corpus would mean something different."""
        for row in PE.es3083_provisional_shade_set():
            r = row["spec"].realize()
            with self.subTest(pan=row["pan"]):
                self.assertFalse(r["colour_transform_applied"])
                self.assertEqual(r["shader_input_rgb"],
                                 list(row["spec"].shade.rgb))
                self.assertEqual(r["display_rgb"],
                                 list(row["spec"].shade.rgb))
                self.assertEqual(r["shader_input_colour_space"],
                                 PE.AUTHORED_COLOUR_SPACE_UNDECLARED)

    def test_no_material_identity_moved(self):
        """Recommendation (e) rested entirely on this. Pinned against
        values computed BEFORE the edit."""
        for row in PE.es3083_provisional_shade_set():
            with self.subTest(set="provisional", pan=row["pan"]):
                self.assertEqual(
                    row["spec"].material_identity(),
                    PRE_COLOUR_SPACE_PROVISIONAL_IDENTITIES[row["pan"]])
        for row in PE.es3083_owner_shade_set():
            with self.subTest(set="owner", pan=row["pan"]):
                self.assertEqual(
                    row["spec"].material_identity(),
                    PRE_COLOUR_SPACE_OWNER_IDENTITIES[row["pan"]])

    def test_midnight_bloom_reaches_the_shader_correctly(self):
        spec = PE.es3083_owner_shade_set()[11]["spec"]
        self.assertEqual(spec.shade.name, "Midnight Bloom")
        for got, want in zip(spec.realize()["shader_input_rgb"],
                             (0.068480, 0.027323, 0.043745)):
            self.assertAlmostEqual(got, want, places=6)

    def test_display_rgb_is_retained_as_the_frozen_contract_alias(self):
        """powder_materials.py reads spec["display_rgb"] in nine places
        and is the frozen instrument. The key stays; the honest name is
        what new code reads."""
        for row in PE.es3083_owner_shade_set():
            r = row["spec"].realize()
            with self.subTest(pan=row["pan"]):
                self.assertEqual(r["display_rgb"], r["shader_input_rgb"])


class Class23ReachabilityTests(SimpleTestCase):
    def test_the_class_23_hole_is_unreachable_in_this_tree(self):
        """The authority is caller-asserted, so an OWNER_CHOSEN_DESIGN_
        INTENT shade built from raw values would be transferred as if it
        were sRGB. This asserts no such construction exists HERE.

        SEARCH EXTENT: every .py under apps/, tools/, docs/, scripts/,
        config/ and templates/, EXCLUDING test modules, for a shade
        construction whose authority argument is
        OWNER_CHOSEN_DESIGN_INTENT within a four-line window.

        Tests are excluded DELIBERATELY and the exclusion is the point,
        not a convenience: a test may construct the hole, because
        exercising an edge case is what tests are for. Production code
        may not. This assertion first fired on this very file, which was
        building an owner-authority shade from a raw triple — the hole
        itself, modelled in a test. That construction was corrected to a
        hex-derived one rather than excused.

        The guarantee is about this tree, not about the class; class 23
        stays OPEN on the register.
        """
        import pathlib
        import re
        repo = pathlib.Path(PE.__file__).resolve().parents[3]
        pat = re.compile(r"PowderShade\s*\(")
        sites = []
        for root in ("apps", "tools", "docs", "scripts", "config",
                     "templates"):
            for p in (repo / root).rglob("*.py"):
                if "__pycache__" in str(p) or p.name.startswith("test_"):
                    continue
                src = p.read_text(encoding="utf-8", errors="ignore")
                if "OWNER_CHOSEN_DESIGN_INTENT" not in src:
                    continue
                lines = src.splitlines()
                for i, line in enumerate(lines):
                    if not pat.search(line):
                        continue
                    window = "\n".join(lines[i:i + 4])
                    if "OWNER_CHOSEN_DESIGN_INTENT" in window:
                        sites.append((str(p.relative_to(repo)), i + 1))
        self.assertEqual(
            len(sites), 1,
            f"expected exactly one construction site, found {sites}")
        path, _line = sites[0]
        self.assertEqual(
            path, "apps/pipeline/services/palette_powder_engine.py")
        # and that one site derives every triple from the hex
        src = (repo / path).read_text()
        fn = src.split("def es3083_owner_shade_set")[1]
        self.assertIn("hex_to_srgb_triple(row[\"hex\"])", fn)
