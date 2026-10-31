"""PALT-M4C M4C-3 / §8 — the bridge driven by the RECOVERED real design.

ES3083 is a genuine BBROSE 'Outer Glow' eyeshadow palette production sheet
recovered from ConceptReference 6, which was filed under the packaging
target where the palette engine could never see it.
"""
from django.test import SimpleTestCase

from apps.pipeline.services import palette_design_intent as di
from apps.pipeline.services import palette_intent_mapping as im
from apps.pipeline.services.palette_es3083_intent import (
    CONCEPT_REFERENCE, build_es3083_intent)

DEFAULTS = {
    "layout.pan_count": 9, "layout.rows": 3, "layout.columns": 3,
    "pan.shape": "CIRCLE", "layout.outer_margin_mm": 5.0,
    "layout.inter_pan_gap_mm": 4.0, "case.corner_radius_mm": 6.0,
    "mirror.present": True, "case.outer_height_mm": 15.0,
    "material.primary": "ABS_NEUTRAL", "material.powder_finish":
    "UNSPECIFIED", "artwork.logo_zone": "NONE", "artwork.type_zones": [],
    "case.opening_direction": "UPWARD", "hinge.edge": "TOP_EDGE",
}


class ES3083IntentTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.intent = build_es3083_intent()

    def test_it_is_drafted_from_the_recovered_asset(self):
        self.assertIn("ES3083", CONCEPT_REFERENCE)
        self.assertIn("ConceptReference:6", self.intent.concept_reference)

    def test_nothing_is_owner_confirmed(self):
        self.assertEqual(self.intent.state, di.DRAFT)
        self.assertFalse(self.intent.confirmed)
        self.assertEqual(len(self.intent.pending()),
                         len(self.intent.fields))

    def test_the_intent_validates(self):
        self.assertTrue(di.validate(self.intent)["valid"])

    def test_the_headline_contradiction_is_captured(self):
        """PALT-P1 assumed circular pans; the real palette is rectangular."""
        self.assertEqual(self.intent.get("pan_shapes").value, "RECTANGULAR")
        self.assertEqual(self.intent.get("pan_shapes").constraint_level,
                         di.HARD)

    def test_pantone_colours_are_the_strongest_fact(self):
        f = self.intent.get("colour_zones")
        self.assertEqual(f.constraint_level, di.HARD)
        self.assertGreaterEqual(f.confidence, 0.9)
        self.assertIn("PANTONE 621 C", f.value)

    def test_uncertain_pan_count_is_soft_not_hard(self):
        """Read from a small render, so it must not be a hard rule."""
        self.assertEqual(self.intent.get("pan_count").constraint_level,
                         di.SOFT)
        self.assertLess(self.intent.get("pan_count").confidence, 0.7)

    def test_ornament_is_decorative_and_not_geometry(self):
        for name in ("ornament", "pattern"):
            f = self.intent.get(name)
            self.assertEqual(f.constraint_level, di.DECORATIVE)
            self.assertFalse(f.geometry_relevance)

    def test_presentation_layers_are_explicitly_ignored(self):
        d = self.intent.decomposition["layers"]
        for layer in ("SHADOWS", "REFLECTIONS", "LIGHTING", "BACKGROUND"):
            self.assertIn("ignored", d[layer])

    def test_no_millimetre_dimension_is_invented(self):
        self.assertTrue(any("millimetres" in r or "mm" in r
                            for r in self.intent.unresolved_regions))


class TwoVariantProofTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.intent = build_es3083_intent()
        cls.mapping = im.map_intent(cls.intent, DEFAULTS)

    def _driven(self):
        return {k: self.mapping["resolved"][k]["value"] for k in DEFAULTS}

    def test_the_two_variants_are_not_identical(self):
        """§8: identical variants classify the bridge as FAIL."""
        self.assertNotEqual(DEFAULTS, self._driven())

    def test_the_pan_shape_actually_changed(self):
        self.assertEqual(DEFAULTS["pan.shape"], "CIRCLE")
        self.assertEqual(self._driven()["pan.shape"], "RECTANGULAR")

    def test_several_fields_changed(self):
        driven = self._driven()
        changed = [k for k in DEFAULTS
                   if repr(DEFAULTS[k]) != repr(driven[k])]
        self.assertGreaterEqual(len(changed), 5, changed)

    def test_artwork_zones_came_from_the_concept(self):
        driven = self._driven()
        self.assertEqual(DEFAULTS["artwork.type_zones"], [])
        self.assertIn("EYE SHADOW", driven["artwork.type_zones"])

    def test_a_soft_pan_count_does_not_override_a_hard_only_rule(self):
        """A low-confidence render reading must not silently set the pan
        count; §J logs a conflict instead."""
        row = self.mapping["resolved"]["layout.pan_count"]
        self.assertEqual(row["origin"], im.FROM_DEFAULT)
        self.assertTrue(self.mapping["conflicts"])

    def test_every_changed_value_carries_its_source(self):
        for key, row in self.mapping["resolved"].items():
            if row["origin"] != im.FROM_DEFAULT:
                self.assertTrue(row["source_field"], key)
                self.assertIn("ES3083", row["source_reference"])

    def test_defaults_remain_labelled(self):
        for row in self.mapping["resolved"].values():
            if row["origin"] == im.FROM_DEFAULT:
                self.assertIn("no concept field", row["mapping_rule"])

    def test_nothing_claims_owner_approval(self):
        self.assertFalse(self.mapping["owner_approved"])
        self.assertEqual(self.mapping["manufacturing_authority"],
                         "NOT_ESTABLISHED")
