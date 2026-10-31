"""PALT-M4C §2/§3 — Palette as a first-class design target.

The §D audit's root cause was that ``palette`` was not a DesignTarget at
all, so no palette task, TaskReference or ConceptReference could exist and
no design could ever reach the palette engine. These tests pin the target
into existence and pin the properties the owner required: dedicated (not
an alias for Product Container), selectable, and fail-closed rather than
pretending to produce a deliverable it cannot yet produce.
"""
import pytest
from django.test import SimpleTestCase

from apps.pipeline.models import DesignTask, TaskReference
from apps.pipeline.targets import DesignTarget, get_target, ui
from apps.pipeline.targets.palette import (
    PALETTE_REFERENCE_KINDS, SELECTED_CONCEPT_ROLE, PaletteTarget)


class PaletteTargetExistsTests(SimpleTestCase):
    def test_palette_is_a_design_target(self):
        self.assertEqual(DesignTarget.PALETTE.value, "palette")
        self.assertIn("palette", DesignTarget.values)

    def test_the_model_field_accepts_palette(self):
        choices = [c[0] for c in
                   DesignTask._meta.get_field("design_target").choices]
        self.assertIn("palette", choices)

    def test_a_palette_strategy_is_registered(self):
        self.assertIsInstance(get_target("palette"), PaletteTarget)
        self.assertEqual(get_target("palette").name, "palette")

    def test_palette_is_not_an_alias_for_product_container(self):
        pal = get_target("palette")
        con = get_target("product_container")
        self.assertNotEqual(type(pal), type(con))
        self.assertNotEqual(pal.concept_prompt_profile(None),
                            con.concept_prompt_profile(None))

    def test_the_concept_profile_describes_a_palette(self):
        text = get_target("palette").concept_prompt_profile(None).lower()
        self.assertIn("palette", text)
        self.assertIn("pans", text)
        # and explicitly excludes the other targets' objects
        self.assertIn("not a bottle", text)

    def test_palette_has_no_carton_structure(self):
        self.assertIsNone(get_target("palette").concept_structure_id(None))

    def test_output_entry_fails_closed_rather_than_faking_a_deliverable(self):
        with self.assertRaises(NotImplementedError) as ctx:
            get_target("palette").begin_output(None, None)
        self.assertIn("PALETTE_OUTPUT_PIPELINE_NOT_YET_CONNECTED",
                      str(ctx.exception))

    def test_review_sections_declare_authority(self):
        rows = {r["label"]: r["value"]
                for r in get_target("palette").review_sections(None)}
        self.assertEqual(rows["Manufacturing authority"], "NOT_ESTABLISHED")
        self.assertEqual(rows["Selected concept role"],
                         SELECTED_CONCEPT_ROLE)
        self.assertIn("dedicated", rows["Design target"].lower())


class PaletteSelectorTests(SimpleTestCase):
    def test_palette_has_a_selector_card(self):
        # §BH55 Phase 2: it read Active and failed after its paid concepts — its card NAMED what it needs — [§BH70(2):
        # "Palette must be startable from New design … It does not refuse me at the door." It can be chosen, and starts
        # as its case — a Product Container of the Compact / Palette form, its concept made first — its bottom line a
        # container's]
        card = next(c for c in ui.TARGET_CARDS if c["value"] == "palette")
        self.assertEqual(card["name"], "Palette")
        self.assertTrue(card["active"])
        self.assertEqual(card["status"], ui.card_for("product_container")["status"])
        self.assertIn("its concept is made first", card["description"])

    def test_bh70_palette_is_selectable(self):
        """[§BH70(2): this test read `test_palette_is_not_selectable_until_it_can_be_designed` (§BH55 Phase 2: was
        selectable) — it starts as its case now, so it can be chosen.]"""
        self.assertTrue(ui.is_selectable("palette"))

    def test_every_target_still_has_exactly_one_card(self):
        values = [c["value"] for c in ui.TARGET_CARDS]
        self.assertEqual(len(values), len(set(values)))
        self.assertEqual(set(values), set(DesignTarget.values))

    def test_the_active_targets_are_exactly_these(self):   # §BH55: renamed as Phase 2 ships
        # §BH55 PHASE 1 (2026-09-19): Complete Product ships — three became four
        # §BH55 PHASE 2 (2026-09-19): Marketing Material ships — four became five; Social Media — six;
        # Exhibition Booth — seven; Display Stand — eight; Gift Set — nine; Palette named with its needs — eight
        # §BH70(2) (2026-09-27): Palette starts, as its case — nine
        active = [c["name"] for c in ui.TARGET_CARDS if c["active"]]
        self.assertEqual(active, ["Product", "Display", "Carton", "Palette", "Complete Product", "Gift Set",
                                  "Marketing Material", "Booth graphics", "Social Media"])


class PaletteReferenceKindTests(SimpleTestCase):
    def test_palette_reference_kinds_are_declared(self):
        names = [k for k, _ in PALETTE_REFERENCE_KINDS]
        for expected in ("palette_concept", "palette_product", "outer_case",
                         "pan_layout", "hinge", "clasp", "mirror",
                         "powder_finish", "artwork", "logo", "typography",
                         "color", "material", "inspiration"):
            self.assertIn(expected, names, expected)

    def test_the_model_accepts_the_palette_kinds(self):
        model_kinds = {k for k, _ in TaskReference.REF_KINDS}
        for k, _ in PALETTE_REFERENCE_KINDS:
            self.assertIn(k, model_kinds, k)

    def test_a_palette_concept_is_not_a_container_photo(self):
        model_kinds = {k for k, _ in TaskReference.REF_KINDS}
        self.assertIn("palette_concept", model_kinds)
        self.assertIn("container", model_kinds)
        self.assertNotEqual("palette_concept", "container")

    def test_references_stay_reference_only(self):
        statuses = {s for s, _ in TaskReference.STATUS_CHOICES}
        self.assertEqual(statuses, {"REFERENCE_ONLY"})


@pytest.mark.django_db
class TestAPaletteTaskCanExist:
    def test_a_palette_task_can_be_created(self, django_user_model):
        from apps.core.models import Brand
        brand = Brand.objects.create(name="BBROSE-palette-test")
        task = DesignTask.objects.create(
            brand=brand, task_text="nine-pan eyeshadow palette",
            design_target="palette")
        assert task.pk is not None
        assert task.design_target == "palette"
        assert DesignTask.objects.filter(design_target="palette").exists()

    def test_a_palette_task_can_carry_a_palette_concept_reference(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.core.models import Brand
        brand = Brand.objects.create(name="BBROSE-palette-ref")
        task = DesignTask.objects.create(
            brand=brand, task_text="palette", design_target="palette")
        ref = TaskReference.objects.create(
            task=task, kind="palette_concept",
            image=SimpleUploadedFile("c.png", b"\x89PNG\r\n\x1a\n"),
            original_filename="c.png")
        assert ref.kind == "palette_concept"
        assert ref.status == "REFERENCE_ONLY"
        assert task.references.count() == 1
