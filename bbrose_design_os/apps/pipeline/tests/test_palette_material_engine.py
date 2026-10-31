"""M5 §11/§12 — the generalized material and colour engine."""
from django.test import SimpleTestCase

from apps.pipeline.services import palette_es3083_owner_confirmation as OC
from apps.pipeline.services import palette_identity as PI
from apps.pipeline.services import palette_material_engine as ME
from apps.pipeline.services import palette_moulded_rect as MR


def _p1b():
    comps, dims = MR.build_rect_components(OC.confirmed_intent())
    return comps, dims


class MaterialContractTests(SimpleTestCase):
    def test_every_material_the_directive_names_exists(self):
        for m in ("ABS", "PP", "ACRYLIC", "METAL",
                  "PAPERBOARD_COMPOSITE"):
            self.assertIn(m, ME.MATERIALS)
            self.assertIn(m, ME.MATERIAL_BASE)

    def test_every_finish_the_directive_names_exists(self):
        for f in ("MATTE", "SATIN", "GLOSSY", "METALLIC", "TRANSPARENT",
                  "TRANSLUCENT"):
            self.assertIn(f, ME.FINISHES)
            self.assertIn(f, ME.FINISH_MODIFIER)

    def test_finishes_differ_by_more_than_roughness(self):
        """One shader with a roughness dial would collapse these."""
        axes = ("roughness", "transmission", "sheen", "clearcoat",
                "metallic_scale")
        seen = set()
        for finish in ME.FINISHES:
            m = ME.FINISH_MODIFIER[finish]
            seen.add(tuple(m.get(a, 0.0) for a in axes))
        self.assertEqual(len(seen), len(ME.FINISHES))
        rough_only = {ME.FINISH_MODIFIER[f]["roughness"]
                      for f in ME.FINISHES}
        self.assertLess(len(rough_only), len(ME.FINISHES) + 1)

    def test_transmission_separates_the_transparent_family(self):
        for f in ("TRANSPARENT", "TRANSLUCENT"):
            self.assertGreater(ME.FINISH_MODIFIER[f]["transmission"], 0.0)
        for f in ("MATTE", "SATIN", "GLOSSY", "METALLIC"):
            self.assertEqual(ME.FINISH_MODIFIER[f]["transmission"], 0.0)

    def test_an_impossible_combination_is_refused(self):
        for material, finish in ((ME.METAL, ME.TRANSPARENT),
                                 (ME.METAL, ME.TRANSLUCENT),
                                 (ME.PAPERBOARD_COMPOSITE,
                                  ME.TRANSPARENT)):
            with self.subTest(material=material, finish=finish):
                with self.assertRaises(ME.MaterialError):
                    ME.MaterialAssignment("*", material, finish,
                                          ME.Colour(rgb=(0.5, 0.5, 0.5)))

    def test_an_unknown_material_or_finish_is_refused(self):
        with self.assertRaises(ME.MaterialError):
            ME.MaterialAssignment("*", "UNOBTANIUM", ME.MATTE,
                                  ME.Colour(rgb=(0.5, 0.5, 0.5)))
        with self.assertRaises(ME.MaterialError):
            ME.MaterialAssignment("*", ME.ABS, "SPARKLY",
                                  ME.Colour(rgb=(0.5, 0.5, 0.5)))

    def test_an_unmatched_component_is_refused_not_guessed(self):
        c = ME.MaterialContract("partial", [
            ME.MaterialAssignment("lid_", ME.ABS, ME.MATTE,
                                  ME.Colour(rgb=(0.5, 0.5, 0.5)))])
        with self.assertRaises(ME.MaterialError) as ctx:
            c.for_component("base_outer_shell")
        self.assertIn("will not guess", str(ctx.exception))

    def test_a_specific_pattern_overrides_a_general_one(self):
        c = ME.MaterialContract("layered", [
            ME.MaterialAssignment("*", ME.ABS, ME.MATTE,
                                  ME.Colour(rgb=(0.1, 0.1, 0.1))),
            ME.MaterialAssignment("lid_", ME.METAL, ME.METALLIC,
                                  ME.Colour(rgb=(0.8, 0.7, 0.5)))])
        self.assertEqual(c.for_component("lid_outer_shell").material,
                         ME.METAL)
        self.assertEqual(c.for_component("base_outer_shell").material,
                         ME.ABS)


class SymbolicColourTests(SimpleTestCase):
    def test_a_pantone_token_carries_no_value(self):
        c = ME.pantone(ME.PANTONE_621C)
        self.assertEqual(c.kind, ME.SYMBOLIC)
        self.assertIsNone(c.rgb)
        self.assertIn("licensed", c.why_unresolved)

    def test_a_resolved_colour_carries_one(self):
        c = ME.Colour(rgb=(0.3, 0.6, 0.5))
        self.assertEqual(c.kind, ME.RESOLVED)
        self.assertEqual(c.rgb, (0.3, 0.6, 0.5))

    def test_a_colour_needs_a_value_or_a_name(self):
        with self.assertRaises(ME.MaterialError):
            ME.Colour()

    def test_an_out_of_range_value_is_refused(self):
        with self.assertRaises(ME.MaterialError):
            ME.Colour(rgb=(1.4, 0.0, 0.0))

    def test_no_variant_fabricates_a_pantone_value(self):
        for contract in ME.variant_contracts().values():
            for a in contract.assignments:
                if a.colour.name.startswith("PANTONE"):
                    with self.subTest(name=a.colour.name):
                        self.assertIsNone(a.colour.rgb)
                        self.assertEqual(a.colour.kind, ME.SYMBOLIC)


class GeneralizationProofTests(SimpleTestCase):
    """§12 — one colour would prove a hard-coded look, not an engine."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comps, _dims = _p1b()
        cls.geometry_identity = PI.mesh_geometry_identity(
            cls.comps["lid_outer_shell"])
        cls.proof = ME.prove_generalization(cls.geometry_identity,
                                            list(cls.comps))

    def test_all_six_required_variants_exist(self):
        names = {v["variant"] for v in self.proof["variants"]}
        self.assertEqual(names, {
            "NEUTRAL_ABS_MATTE", "DARK_GLOSSY_ABS", "LIGHT_SATIN_ABS",
            "METALLIC_ACCENT", "ES3083_SYMBOLIC_ZONES",
            "OWNER_SUBSTITUTED_COLOUR"})

    def test_the_mesh_identity_is_the_same_for_every_variant(self):
        self.assertEqual(self.proof["distinct_mesh_identities"], 1)
        self.assertFalse(self.proof["geometry_rebuilt"])

    def test_each_variant_has_its_own_material_identity(self):
        self.assertEqual(self.proof["distinct_material_identities"],
                         self.proof["variant_count"])

    def test_each_variant_has_its_own_evidence_identity(self):
        self.assertEqual(self.proof["distinct_evidence_identities"],
                         self.proof["variant_count"])

    def test_the_proof_passes(self):
        self.assertEqual(self.proof["verdict"], "PASS")
        self.assertFalse(self.proof["pantone_rgb_fabricated"])

    def test_the_es3083_variant_is_symbolic_only(self):
        row = next(v for v in self.proof["variants"]
                   if v["variant"] == "ES3083_SYMBOLIC_ZONES")
        self.assertEqual(sorted(row["symbolic_colour_references"]),
                         ["PANTONE 621 C", "PANTONE 627 C"])

    def test_every_component_resolves_under_every_variant(self):
        for row in self.proof["variants"]:
            with self.subTest(variant=row["variant"]):
                self.assertEqual(row["resolved_component_count"],
                                 len(self.comps))

    def test_identical_contracts_share_an_identity(self):
        """The negative control: if identity ignored the assignments,
        every variant would collide and the proof would be vacuous."""
        a = ME.variant_contracts()["DARK_GLOSSY_ABS"]
        b = ME.variant_contracts()["DARK_GLOSSY_ABS"]
        self.assertEqual(a.identity(), b.identity())
        c = ME.variant_contracts()["LIGHT_SATIN_ABS"]
        self.assertNotEqual(a.identity(), c.identity())

    def test_changing_only_colour_moves_only_the_material_identity(self):
        base = ME.MaterialContract("x", [
            ME.MaterialAssignment("*", ME.ABS, ME.MATTE,
                                  ME.Colour(rgb=(0.5, 0.5, 0.5)))])
        recoloured = ME.MaterialContract("x", [
            ME.MaterialAssignment("*", ME.ABS, ME.MATTE,
                                  ME.Colour(rgb=(0.1, 0.2, 0.3)))])
        self.assertNotEqual(base.identity(), recoloured.identity())
        self.assertNotEqual(
            ME.evidence_identity(self.geometry_identity, base),
            ME.evidence_identity(self.geometry_identity, recoloured))
        # and the geometry is untouched by either
        again, _ = _p1b()
        self.assertEqual(
            PI.mesh_geometry_identity(again["lid_outer_shell"]),
            self.geometry_identity)

    def test_it_claims_no_manufacturing_authority(self):
        self.assertFalse(self.proof["owner_approved"])
        self.assertEqual(self.proof["manufacturing_authority"],
                         "NOT_ESTABLISHED")
        self.assertIn("that any of these materials is manufacturable",
                      self.proof["does_not_prove"])


class ContractRecordTests(SimpleTestCase):
    def test_the_record_says_it_cannot_change_geometry(self):
        c = ME.variant_contracts()["NEUTRAL_ABS_MATTE"]
        d = c.to_dict(["lid_outer_shell", "metal_pan_1", "powder_1"])
        self.assertFalse(d["changes_geometry"])
        self.assertEqual(len(d["resolved_components"]), 3)

    def test_metallic_finish_raises_the_metallic_response(self):
        a = ME.MaterialAssignment("*", ME.ABS, ME.METALLIC,
                                  ME.Colour(rgb=(0.5, 0.5, 0.5)))
        b = ME.MaterialAssignment("*", ME.ABS, ME.MATTE,
                                  ME.Colour(rgb=(0.5, 0.5, 0.5)))
        self.assertGreater(a.resolved()["metallic"],
                           b.resolved()["metallic"])
