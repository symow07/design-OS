"""PALT-M4C — design-intent schema, authority law and contract mapping."""
from django.test import SimpleTestCase

from apps.pipeline.services import palette_design_intent as di
from apps.pipeline.services import palette_intent_mapping as im
from apps.pipeline.services.palt_p1 import build_palt_p1


def _field(name, value, level, state=di.PENDING, geom=True, conf=0.9,
           method="IMAGE_COUNTED"):
    return dict(name=name, value=value, source_reference="concept#1",
                source_region="interior", confidence=conf,
                extraction_method=method, confirmation_state=state,
                constraint_level=level, geometry_relevance=geom,
                material_relevance=False, artwork_relevance=False)


def _intent(**over):
    i = di.PaletteDesignIntent(concept_reference="concept#1")
    i.add(**_field("pan_count", 9, di.HARD))
    i.add(**_field("margins", "generous margins", di.SOFT, conf=0.6,
                   method="IMAGE_MEASURED"))
    for k, v in over.items():
        i.add(**v)
    return i


class SchemaTests(SimpleTestCase):
    def test_all_six_field_groups_are_declared(self):
        self.assertEqual(set(di.FIELD_GROUPS), {
            "outer_form", "internal_layout", "mechanical", "material",
            "artwork", "style"})
        self.assertEqual(len(di.OUTER_FORM_FIELDS), 13)
        self.assertEqual(len(di.INTERNAL_LAYOUT_FIELDS), 13)
        self.assertEqual(len(di.MECHANICAL_FIELDS), 10)
        self.assertEqual(len(di.MATERIAL_FIELDS), 11)
        self.assertEqual(len(di.ARTWORK_FIELDS), 11)
        self.assertEqual(len(di.STYLE_FIELDS), 12)

    def test_every_field_carries_the_required_metadata(self):
        f = di.IntentField(**_field("pan_count", 9, di.HARD))
        for attr in ("value", "source_reference", "source_region",
                     "confidence", "extraction_method",
                     "confirmation_state", "constraint_level",
                     "geometry_relevance", "material_relevance",
                     "artwork_relevance"):
            self.assertTrue(hasattr(f, attr), attr)

    def test_unknown_field_rejected(self):
        with self.assertRaises(di.DesignIntentError):
            di.IntentField(**_field("not_a_field", 1, di.HARD))

    def test_unknown_constraint_level_rejected(self):
        with self.assertRaises(di.DesignIntentError):
            di.IntentField(**_field("pan_count", 9, "MADE_UP"))

    def test_confidence_bounds_enforced(self):
        with self.assertRaises(di.DesignIntentError):
            di.IntentField(**_field("pan_count", 9, di.HARD, conf=1.4))

    def test_three_constraint_levels(self):
        self.assertEqual(di.CONSTRAINT_LEVELS,
                         (di.HARD, di.SOFT, di.DECORATIVE))

    def test_concept_is_reference_authority_only(self):
        i = _intent()
        self.assertEqual(i.to_dict()["authority"], "DESIGN_INTENT_REFERENCE")
        for banned in ("MANUFACTURING_DRAWING", "CAD_AUTHORITY",
                       "SUPPLIER_AUTHORITY", "TOLERANCE_AUTHORITY",
                       "HIDDEN_GEOMETRY_AUTHORITY"):
            self.assertIn(banned, i.to_dict()["not_authority"])


class ConfirmationTests(SimpleTestCase):
    def test_unconfirmed_intent_is_a_draft_and_not_authority(self):
        i = _intent()
        self.assertEqual(i.state, di.DRAFT)
        self.assertFalse(i.confirmed)
        for f in i.fields:
            self.assertFalse(f.is_design_authority)

    def test_confirmed_fields_become_authority(self):
        i = di.PaletteDesignIntent(concept_reference="c")
        i.add(**_field("pan_count", 9, di.HARD, state=di.CONFIRMED))
        self.assertTrue(i.confirmed)
        self.assertEqual(i.state, di.CONFIRMED)

    def test_provisional_variant_never_claims_approval(self):
        v = di.provisional_variant(_intent())
        self.assertEqual(v["label"], "PROVISIONAL_INTENT_VARIANT")
        self.assertFalse(v["owner_approved"])
        self.assertEqual(v["manufacturing_authority"], "NOT_ESTABLISHED")
        self.assertTrue(v["pending_owner_confirmation"])

    def test_removed_fields_drop_out(self):
        i = _intent()
        i.add(**_field("rows", 3, di.HARD, state=di.REMOVED))
        self.assertIsNone(i.get("rows"))

    def test_identity_is_deterministic_and_content_sensitive(self):
        a, b = _intent(), _intent()
        self.assertEqual(a.identity(), b.identity())
        c = _intent()
        c.add(**_field("columns", 3, di.HARD))
        self.assertNotEqual(c.identity(), a.identity())


class DecompositionTests(SimpleTestCase):
    def test_presentation_layers_are_not_product_geometry(self):
        got = di.decompose({k: {} for k in di.DECOMPOSITION_LAYERS})
        for layer in ("SHADOWS", "REFLECTIONS", "LIGHTING", "BACKGROUND",
                      "PRESENTATION_EFFECTS"):
            self.assertIn(layer, got["non_product_layers"])
        self.assertIn("shadows are not moulded geometry",
                      got["interpretation_rules"])

    def test_unknown_layer_rejected(self):
        with self.assertRaises(di.DesignIntentError):
            di.decompose({"NOT_A_LAYER": {}})


class ValidationTests(SimpleTestCase):
    def test_decorative_may_not_drive_geometry(self):
        i = di.PaletteDesignIntent(concept_reference="c")
        i.add(**_field("luxury", "gold", di.DECORATIVE, geom=True,
                       method="IMAGE_INFERRED"))
        got = di.validate(i)
        self.assertFalse(got["valid"])
        self.assertEqual(got["findings"][0]["code"],
                         "DECORATIVE_DRIVING_GEOMETRY")

    def test_hard_constraint_needs_confidence(self):
        i = di.PaletteDesignIntent(concept_reference="c")
        i.add(**_field("pan_count", 9, di.HARD, conf=0.2))
        self.assertIn("HARD_CONSTRAINT_LOW_CONFIDENCE",
                      [f["code"] for f in di.validate(i)["findings"]])

    def test_clean_intent_validates(self):
        self.assertTrue(di.validate(_intent())["valid"])


class MappingTests(SimpleTestCase):
    DEFAULTS = {"layout.pan_count": 9, "layout.outer_margin_mm": 5.0,
                "layout.inter_pan_gap_mm": 4.0,
                "case.corner_radius_mm": 6.0}

    def test_hard_constraint_maps_exactly(self):
        m = im.map_intent(_intent(), self.DEFAULTS)
        row = m["resolved"]["layout.pan_count"]
        self.assertEqual(row["value"], 9)
        self.assertEqual(row["origin"], im.FROM_INTENT)
        self.assertIn("EXACT", row["scaling_rule"])

    def test_soft_constraint_scales_and_is_not_a_rigid_rule(self):
        m = im.map_intent(_intent(), self.DEFAULTS)
        row = m["resolved"]["layout.outer_margin_mm"]
        self.assertEqual(row["value"], 6.25)
        self.assertIn("SOFT_SCALE[generous]", row["scaling_rule"])

    def test_unspecified_features_keep_a_labelled_default(self):
        m = im.map_intent(_intent(), self.DEFAULTS)
        row = m["resolved"]["case.corner_radius_mm"]
        self.assertEqual(row["origin"], im.FROM_DEFAULT)
        self.assertIn("no concept field", row["mapping_rule"])

    def test_every_resolved_value_carries_provenance(self):
        m = im.map_intent(_intent(), self.DEFAULTS)
        for row in m["resolved"].values():
            for key in ("origin", "mapping_rule", "authority",
                        "confirmation_state", "confidence"):
                self.assertIn(key, row)

    def test_unconfirmed_intent_never_reports_approved(self):
        m = im.map_intent(_intent(), self.DEFAULTS)
        self.assertFalse(m["owner_approved"])
        self.assertEqual(m["manufacturing_authority"], "NOT_ESTABLISHED")

    def test_mapping_is_deterministic(self):
        a = im.map_intent(_intent(), self.DEFAULTS)
        b = im.map_intent(_intent(), self.DEFAULTS)
        self.assertEqual(a["mapping_identity"], b["mapping_identity"])

    def test_misclassified_field_becomes_a_conflict_not_a_silent_drop(self):
        i = di.PaletteDesignIntent(concept_reference="c")
        i.add(**_field("pan_count", 9, di.SOFT))   # must be HARD
        m = im.map_intent(i, self.DEFAULTS)
        self.assertEqual(m["resolved"]["layout.pan_count"]["origin"],
                         im.FROM_DEFAULT)
        self.assertTrue(m["conflicts"])

    def test_engineering_conflict_is_reported_not_clamped(self):
        m = im.map_intent(_intent(), self.DEFAULTS)
        got = im.check_engineering(m, feasibility={
            "layout.outer_margin_mm": {"min": 3.0, "max": 6.0,
                                       "why": "mechanism zone"}})
        self.assertGreaterEqual(got["conflict_count"], 1)
        self.assertIn("never silently", got["resolution_policy"])
        # the value is NOT modified
        self.assertEqual(m["resolved"]["layout.outer_margin_mm"]["value"],
                         6.25)


class ContractChannelTests(SimpleTestCase):
    """§D's loss point: build_palt_p1 had no design channel at all."""

    def test_contract_accepts_design_intent(self):
        spec = build_palt_p1(design_intent=_intent())
        self.assertIsNotNone(spec)

    def test_intent_changes_the_resolved_contract(self):
        a = build_palt_p1()
        b = build_palt_p1(design_intent=_intent())
        self.assertEqual(a.layout.module_width.mm, b.layout.module_width.mm)
        self.assertIsNotNone(b.case)

    def test_absent_intent_is_byte_identical_behaviour(self):
        """Every existing caller and prior identity must be preserved."""
        a = build_palt_p1()
        self.assertEqual(a.layout.module_width.mm, 26.6)
        self.assertEqual(len(a.layout.pans), 9)
