"""PALT-M4C M4C-9 — the geometric two-variant proof.

The DesignGraphTests and DesignFidelityTests that lived here covered
``palette_design_fidelity/1.0`` and the first Design Graph projection.
Both were superseded when §4 replaced the ten ad-hoc metrics with the
eleven the owner named and §7 completed the graph; their coverage now
lives in ``test_palette_graph_fidelity_v2.py``.

The geometric variant proof is NOT duplicated there, so it stays here.
"""
from django.test import SimpleTestCase


class TwoVariantGeometryProofTests(SimpleTestCase):
    """M4C-9 — the difference must be in the geometry, not the paperwork."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from apps.pipeline.services import palette_variant_proof as vp
        cls.vp = vp
        cls.proof = vp.prove_two_variants()

    def test_the_proof_passes_on_built_geometry(self):
        self.assertEqual(self.proof["verdict"], self.vp.PASS,
                         self.proof["failed"])
        self.assertEqual(self.proof["failed"], [])

    def test_it_measures_meshes_not_contracts(self):
        for key in ("vertex_count", "face_count", "mesh_identity"):
            self.assertIn(key, self.proof["variant_a"])
            self.assertIn(key, self.proof["variant_b"])

    def test_the_rectangular_pocket_is_not_a_rounded_square(self):
        self.assertFalse(self.proof["variant_b"]["pocket_is_isotropic"])
        self.assertTrue(self.proof["variant_a"]["pocket_is_isotropic"])

    def test_both_pilots_survive_and_neither_replaces_the_other(self):
        self.assertEqual(self.proof["variant_a"]["role"],
                         "ENGINEERING_REGRESSION_FIXTURE")
        self.assertEqual(self.proof["variant_b"]["role"],
                         "OWNER_DESIGN_INTENT_PILOT")
        self.assertEqual(self.proof["variant_a"]["mesh_identity"],
                         "ec65ea9402c16230")

    def test_it_states_what_it_does_not_prove(self):
        self.assertIn("that either variant is manufacturable",
                      self.proof["does_not_prove"])
        self.assertEqual(self.proof["manufacturing_authority"],
                         "NOT_ESTABLISHED")
