"""PRODUCT_CONTAINER target activation (Phase B3b, 2026-07-08).

Exercises the backend container journey with no live API: begin_output opens
the confirm-profile gate; the confirm endpoint validates + transitions +
reconstructs; reconstruction produces an editable native-vector .ai (colours
sampled from the approved concept, label skipped without a key); the Review
Board shows container-specific specs. Packaging is untouched.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings

from apps.core.models import Brand, Product
from apps.pipeline.agents.aria import ARIAAgent
from apps.pipeline.models import (
    DesignTask,
    Gate1RegenerationJob,
    GeneratedImage,
    PackagingOutput,
)
from apps.pipeline.permissions import ROLE_REVIEWER
from apps.pipeline.targets import DesignTarget, get_target
from apps.pipeline.targets.container import ProductContainerTarget

fitz = pytest.importorskip("fitz")

_PNG = __import__("base64").b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4"
    "z8Dwn4EBAAT/Af9jZv5kAAAAAElFTkSuQmCC")


class ContainerTargetRegistryTests(TestCase):
    def test_registered_and_prompt_directive(self):
        t = get_target(DesignTarget.PRODUCT_CONTAINER.value)
        assert isinstance(t, ProductContainerTarget)
        assert "PRODUCT CONTAINER" in t.concept_prompt_profile(None)
        assert t.concept_structure_id(None) is None


class ConceptDirectiveNamesTheFormTests(TestCase):
    """§BH70(1), item 4 of the list the owner was sent: every container concept was made with "a bottle, jar or tube ...
    label, cap, body colours ... standing upright" — a palette asked for a label and a cap and to stand upright."""

    def test_bh70_the_concept_directive_names_the_products_own_form(self):
        from types import SimpleNamespace

        t = ProductContainerTarget()

        def directive(text, recorded=None):
            class _Outputs:
                def order_by(self, *_a):
                    return self

                def first(self):
                    return SimpleNamespace(spec_sheet={"container_profile/1.0": {"archetype": recorded}}) \
                        if recorded else None
            return t.concept_prompt_profile(SimpleNamespace(task=SimpleNamespace(
                product=None, task_text=text, packaging_outputs=_Outputs())))
        lipstick = directive("a matte lipstick in a gold case")
        assert "a lipstick" in lipstick and "standing upright" in lipstick
        palette = directive("a four pan baked palette")
        assert "a compact or palette" in palette and "seen from above" in palette and "upright" not in palette
        assert "a pencil" in directive("a waterproof eyeliner pencil")
        assert "a bottle" in directive("a 30 ml serum bottle")
        anyone = directive("a lovely thing in a nice colour")
        assert "the product's own form" in anyone
        assert "a compact or palette" in directive("a 30 ml serum bottle", recorded="compact")   # the record governs
        for text in (lipstick, palette, anyone):
            assert "bottle, jar or tube" not in text and "PRODUCT CONTAINER" in text


class TheConceptIsPicturedToBeTracedTests(TestCase):
    """His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): "build the map path to run on its own
    for every new design, for a wand vial and a carton". The map cuts one product from a plain ground; the gloss vials
    on record (a pink vial leaning on a pink wall over its reflection) could not be cut."""

    def test_his_go_every_container_concept_is_pictured_so_its_map_can_read_it(self):
        from apps.pipeline.targets.container import MAP_GROUND, MAP_PLAN_POSE, MAP_STANDING_POSE, concept_directive
        vial = concept_directive("mascara", "a honey lip gloss\n\n[Container type: wand vial]")
        assert MAP_STANDING_POSE in vial and MAP_GROUND in vial and "not leaning" in vial and "plain seamless" in vial
        compact = concept_directive("compact", "a pressed powder")
        assert MAP_PLAN_POSE in compact and MAP_GROUND in compact and "upright" not in compact
        assert MAP_GROUND in concept_directive(None, "a lovely thing")
        assert "a lip gloss in a wand vial." in vial                       # the product still named for what it is


class GlossInItsVesselTests(TestCase):
    """The owner's answer of 2026-09-27 to the §BH70 report's fourth question: "Neither: when a brief says "gloss"
    without saying which, ask me: wand vial or squeeze tube." His gloss drawn in the mascara's vial is told for what
    it is — the concept prompt said "a mascara" — and so is a liquid eyeliner the vial holds; a mascara is a
    mascara, and a finish's gloss is not a product."""

    def test_bh70_answer_4_a_gloss_in_the_wand_vial_is_named_for_what_it_is(self):
        from apps.pipeline.targets.container import concept_directive, gloss_question, product_in_form
        gloss = concept_directive("mascara", "a honey lip gloss\n\n[Container type: wand vial]")
        assert "a lip gloss in a wand vial" in gloss and "mascara" not in gloss.lower()
        assert "a liquid eyeliner in a wand vial" in concept_directive("mascara", "a liquid eyeliner")
        assert "a mascara." in concept_directive("mascara", "a lengthening mascara")
        assert "a lip gloss in a squeeze tube" in concept_directive("tube", "a lip gloss [Container type: squeeze tube]")
        assert "a tube." in concept_directive("tube", "a hand cream tube")
        assert product_in_form("mascara", "a mascara with a high-gloss cap") == "mascara"
        assert product_in_form("bottle", "a lip gloss bottle") is None
        # the door's question: a finish's gloss, or a gloss whose form is said, asks nothing
        assert gloss_question("a honey lip gloss")["choices"] == [
            {"key": "wand vial", "label": "Wand vial"}, {"key": "squeeze tube", "label": "Squeeze tube"}]
        for said in ("a serum bottle with a high-gloss finish", "selective gloss details on the carton",
                     "a lip gloss with a doe-foot wand", "a lip gloss palette", "a gloss pot"):
            assert gloss_question(said) is None, said

    def test_bh70_answer_4_the_board_calls_a_gloss_vial_a_wand_vial(self):
        from types import SimpleNamespace

        from apps.dashboard.board import what_words
        spec = {"container_profile/1.0": {"archetype": "mascara", "fields": {"cap_type": {"value": "wand"}}}}

        def task(text):
            return SimpleNamespace(design_target="product_container", task_text=text, product=None)
        assert what_words(task("a honey lip gloss\n\n[Container type: wand vial]"), spec) == "wand vial"
        assert what_words(task("a lengthening mascara"), spec) == "mascara"


class TheBoardSaysTheFormsOwnWordsTests(TestCase):
    """§BH70(1), item 21 of the list the owner was sent: the review board said "Cap: clasp" and "Cap colour" of a
    compact. It names the closure in its form's own label and the colour for the part it paints."""

    def test_bh70_a_compacts_closure_and_lid_colour_in_its_own_words(self):
        spec = {"container_profile": {"archetype": "compact", "variant": "rounded_rect", "cap_style": "clasp",
                                      "height_mm": 95, "width_mm": 110},
                "colors": {"body": "#EAD7D2", "cap": "#C9A24B"}}
        rows = {r["label"]: r["value"] for r in ProductContainerTarget()._spec_rows(None, spec)}
        assert (rows["Closure"], rows["Lid colour"]) == ("Clasp", "#C9A24B"), rows
        assert "Cap" not in rows and "Cap colour" not in rows
        spec["container_profile"].update(archetype="bottle", variant="slim", cap_style="screw")
        rows = {r["label"]: r["value"] for r in ProductContainerTarget()._spec_rows(None, spec)}
        assert (rows["Closure"], rows["Cap colour"]) == ("Screw Cap", "#C9A24B"), rows


class TheFrontPrintsTheProductsNameTests(TestCase):
    """His test day finding 3 (2026-09-30, design 117): with no product record the front printed the brief's first
    sixty characters — "Coconut Rose Body Lotion (test)\\r\\n\\r\\nProduct: BBROSE Coconut R" — as a three-line hero. The
    name is the product record's, else the brief's product name as the planner read it (the house's name dropped, the
    mark carrying it), else the brief's first line; a name written from the old cut is read again when it is drawn."""

    def setUp(self):
        from apps.core.models import Brand
        self.brand = Brand.objects.create(name="BBROSE")
        self.text = ("Coconut Rose Body Lotion (test)\r\n\r\nProduct: BBROSE Coconut Rose Body Lotion (imaginary "
                     "test product).")
        self.task = DesignTask.objects.create(brand=self.brand, task_text=self.text,
                                              design_target="product_container")

    def _brief(self, product_name):
        from apps.pipeline.models import CreativeBrief
        CreativeBrief.objects.create(task=self.task, directions=[], design_intent={
            "brief": {"brand": "BBROSE", "product_name": product_name}})

    def test_finding3_the_name_is_the_products_never_the_briefs_first_sixty_characters(self):
        from types import SimpleNamespace

        from apps.pipeline.targets.container import product_name_for
        assert product_name_for(self.task, None) == ("Coconut Rose Body Lotion (test)", "the brief's first line")
        self._brief("BBROSE Coconut Rose Body Lotion")
        name, source = product_name_for(self.task, None)
        assert name == "Coconut Rose Body Lotion" and "without the house's own name" in source
        assert product_name_for(self.task, SimpleNamespace(name="Focus Pressed Powder"))[0] == "Focus Pressed Powder"

    def test_finding3_a_name_the_old_cut_wrote_is_read_again_and_one_the_owner_set_is_kept(self):
        from apps.pipeline.targets.container import drawing_name
        self._brief("BBROSE Coconut Rose Body Lotion")
        assert drawing_name(self.task, {"product_name": self.text[:60]})[0] == "Coconut Rose Body Lotion"
        assert drawing_name(self.task, {"product_name": "Coconut Rose"}) == ("Coconut Rose", None)


class TheTubesFrontCopyIsLaidInTheZoneHeConfirmedTests(TestCase):
    """His test day finding 3 (2026-09-30, design 117): a tube's front copy was laid into its drawing's own label box
    and not the 35 x 99 mm front he confirmed. A tube's label is its confirmed front zone when that zone lies on the
    drawn body clear of its closure, held inside the body where the body is narrower — said on the record — else the
    drawing's own, the reason said; every other form's record is dropped, never left from a previous run."""

    def _spec(self, x, y, w, h, surface="BODY_FRONT"):
        return {"container_decoration_zones/1.0": {"zones": [
            {"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": surface,
             "x": x, "y": y, "width": w, "height": h}]}}

    def test_finding3_a_tubes_label_is_the_front_he_confirmed_held_on_its_body(self):
        from apps.pipeline.targets.container import (FRONT_LABEL_CONFIRMED, FRONT_LABEL_SCHEMA,
                                                     _outline_span, _profile_with_front_zone)
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        tube = ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0, width_mm=50.0)
        records = []
        placed = _profile_with_front_zone(tube, self._spec(7.5, 40.5, 35.0, 99.0), records)   # 117's, as confirmed
        (_op, key, record), = records
        assert key == FRONT_LABEL_SCHEMA and record["source"] == FRONT_LABEL_CONFIRMED, record
        lx, ly, lw, lh = placed.label_zone
        assert (ly, lh) == (40.5, 99.0) and 7.5 <= lx and lx + lw <= 42.5                    # his front's own place
        left, right = _outline_span(build_backbone(tube).silhouette, ly, ly + lh)
        assert left <= lx + 1e-9 and lx + lw <= right + 1e-9                                  # on the drawn body
        assert lw < 35.0 and "narrower than the zone" in record["narrowed"]                    # the tube narrows up
        records = []
        kept = _profile_with_front_zone(tube, self._spec(7.5, 2.0, 35.0, 99.0), records)    # on its cap: refused
        assert kept.label_zone is None and "clear of its closure" in records[0][2]["reason"]
        bottle = ContainerProfile(archetype="bottle", variant="cylindrical", cap_style="screw", height_mm=110.0,
                                  width_mm=40.0)
        records = []
        assert _profile_with_front_zone(bottle, self._spec(7.5, 30.0, 25.0, 50.0), records).label_zone is None
        assert records == [("drop", FRONT_LABEL_SCHEMA, None)]                               # never a stale record

    def test_his_122_a_front_confirmed_from_the_crimped_end_is_his_on_a_traced_tube(self):
        """[His answers after 122 was redrawn, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md), (2): "Fix the front-copy fit
        check so it measures against MY confirmed print area, not the drawing's own."] 122 at his 120 x 35 mm, drawn with
        the outline traced from its concept, which closes to a point at the crimped end: his front, confirmed from that
        end (54.9 x 99.9 mm at 0, 0, its safe margin 3 mm), is the label — the body measured across its safe band, never
        its very edge — where it was refused and the drawing's own label taken."""
        import json
        import os

        from apps.pipeline.targets.container import FRONT_LABEL_CONFIRMED, _profile_with_front_zone
        from apps.pipeline.targets.container.silhouettes import ContainerProfile
        here = os.path.join(os.path.dirname(__file__), "fixtures_122", "outline_149.json")
        tube = ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=120.0, width_mm=35.0,
                                outline=json.load(open(here)))
        spec = self._spec(0.0, 0.0, 54.9, 99.9)
        spec["container_decoration_zones/1.0"]["zones"][0]["safe_margin_mm"] = 3.0
        records = []
        placed = _profile_with_front_zone(tube, spec, records)
        assert records[0][2]["source"] == FRONT_LABEL_CONFIRMED, records
        assert placed.label_zone[1] == 0.0 and placed.label_zone[3] == 99.9
        # [His review of 127, 130, 131 and 132, 2026-10-15, C (3)] the traced crimp no longer closes to a point at its very
        # edge (its last row, the mask's own, was drawn as a V): drawn flat as a tube's crimp is, with its corners
        # rounded (``silhouettes.END_ROUND``), his front holds there too — narrowed inside the body as across its band
        edge = dict(spec["container_decoration_zones/1.0"]["zones"][0], safe_margin_mm=0.0)
        records = []
        _profile_with_front_zone(tube, {"container_decoration_zones/1.0": {"zones": [edge]}}, records)
        assert records[0][2]["source"] == FRONT_LABEL_CONFIRMED, records


class ContainerFlowTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-410", name="Rose Nectar Lip Gloss",
            category="CO", year=2026, product_type="lip gloss")
        # [the owner's answer of 2026-09-27: a brief that says "gloss" without saying which is asked at the door, "wand
        # vial or squeeze tube?", and his answer rides the brief — so a gloss task that exists carries it. It read "a lip
        # gloss", a bare gloss the tube's words used to claim]
        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="a lip gloss\n\n[Container type: squeeze tube]",
            status="gate_1_approved",
            design_target=DesignTarget.PRODUCT_CONTAINER.value)
        self.img = GeneratedImage.objects.create(
            task=self.task, direction_name="D", prompt_used="p", variation_number=1)
        self.img.image_file.save("c.png", __import__("django.core.files.base",
                                 fromlist=["ContentFile"]).ContentFile(_PNG), save=True)

    def test_begin_output_opens_the_confirm_profile_gate(self):
        ProductContainerTarget().begin_output(ARIAAgent(self.task.id), self.img)
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_container_profile"
        out = self.task.packaging_outputs.first()
        assert out and out.spec_sheet["backend"] == "container"
        # lip gloss, his answer on the brief "squeeze tube" → tube archetype inferred
        assert out.spec_sheet["container_profile"]["archetype"] == "tube"
        assert out.dieline_job_id is None      # no dieline for a container
        # 2B-1: begin_output additionally seeds the versioned records, every
        # field INFERRED/UNKNOWN and zones PROPOSED — the legacy key is intact
        spec = out.spec_sheet
        prof = spec["container_profile/1.0"]
        assert prof["schema_version"] == "container_profile/1.0"
        assert prof["confirmation_state"] == "UNCONFIRMED"
        assert not [f for f in prof["fields"].values()
                    if f["verification"] == "VERIFIED"]        # §8 photo-safety
        zrec = spec["container_decoration_zones/1.0"]
        assert zrec["confirmation_state"] == "PROPOSED"
        assert all(z["user_confirmation_state"] == "PROPOSED"
                   for z in zrec["zones"])

    def test_review_sections_include_contract_rows(self):
        ProductContainerTarget().begin_output(ARIAAgent(self.task.id), self.img)
        rows = ProductContainerTarget().review_sections(self.task)
        labels = {r["label"] for r in rows}
        assert "Container contract" in labels
        assert "Profile state" in labels
        assert "Decoration zones" in labels
        assert any(r["label"] == "Profile hash" and r["value"] for r in rows)

    @override_settings(OPENAI_API_KEY="")      # no key → no LABEL raster extracted
    def test_reconstruct_produces_editable_native_vector_ai(self):
        aria = ARIAAgent(self.task.id)
        ProductContainerTarget().begin_output(aria, self.img)
        out = self.task.packaging_outputs.first()
        aria.resume_after_container_profile(
            out.id, {"archetype": "bottle", "variant": "cylindrical",
                     "height_mm": 110, "width_mm": 40})
        self.task.refresh_from_db()
        out.refresh_from_db()
        assert self.task.status == "awaiting_gate_2"
        assert out.design_preview_ai            # editable .ai stored
        page = fitz.open(out.design_preview_ai.path)[0]
        # container STRUCTURE is native vector: live text + drawings
        # VQR-1: at true product scale the long name wraps to stay above
        # the 8pt legibility floor — every word survives as live text
        _text = page.get_text()
        assert "Rose Nectar" in _text and "Lip Gloss" in _text
        assert "REFERENCE — not final artwork" in page.get_text()   # ref labelled
        assert len(page.get_drawings()) > 3                  # silhouette + swatches
        # 2B-2 native: the raster label is gone — the only rasters are the
        # reference photo + the controlled logo fallback (never decoration)
        assert len(page.get_images()) <= 2
        assert out.spec_sheet["colors"]["body"].startswith("#")
        # container_design_graph/1.1 census: native mode, ZERO decorative rasters
        cdg = out.spec_sheet["container_design_graph/1.1"]
        assert cdg["mode"] == "native"
        assert cdg["decorative_raster_count"] == 0
        assert cdg["primitives"]["live_text"] >= 1
        assert cdg["zones_consumed"]                         # zones were consumed
        # 2B-2 slice 3: emitted placements are contained + zones are projected
        assert out.spec_sheet["container_zone_containment_report"]["contained"]
        proj = out.spec_sheet["container_projection_report"]
        assert proj["review_required"] is False
        assert proj["zones"] and all("method" in z for z in proj["zones"])
        # 2B-2 slice 4: Review Board surfaces the native reconstruction (§15)
        labels = {r["label"] for r in ProductContainerTarget().review_sections(self.task)}
        assert "Selected variation" in labels
        assert "Native reconstruction" in labels
        assert "Concept fidelity" in labels
        assert "Zone containment" in labels
        # 2B-2 slice 1: reconstruction persists the verified selected-variation
        # identity + the deterministic selected-concept visual graph
        ident = out.spec_sheet["container_selected_variation/1.0"]
        assert ident["verified"] is True and ident["approved_prompt_hash"]
        vg = out.spec_sheet["container_selected_concept_visual_graph/1.0"]
        assert vg["schema_version"] == "container_selected_concept_visual_graph/1.0"
        assert vg["visual_graph_hash"]

    def _regenerated(self, motif_signature, vid="v_x"):
        prompt = f"ROSE NECTAR bottle, {motif_signature}"
        img = GeneratedImage.objects.create(
            task=self.task, direction_name="D", prompt_used=prompt,
            variation_number=1, reference_provenance={"variation_identity": vid})
        img.image_file.save("c.png", __import__(
            "django.core.files.base", fromlist=["ContentFile"]).ContentFile(_PNG),
            save=True)
        Gate1RegenerationJob.objects.create(
            task=self.task, direction_id="d1",
            status=Gate1RegenerationJob.STATUS_COMPLETED,
            prompts_payload={"variations": [{
                "variation_id": vid, "title": "V", "prompt": prompt,
                "motif_signature": motif_signature,
                "logo_zone": "upper left", "product_name_zone": "centered",
                "decorative_coverage_pct": 18}]})
        return img

    @override_settings(OPENAI_API_KEY="")
    def test_supported_motif_reconstructs_natively(self):
        """A SUPPORTED motif whose front is now WIRED parks at the profile gate.

        WHY THIS TEST ASSERTS A RED-SHAPED STATE (§BB5(c) + §BE(a)).

        2B-2A wrote this test when the front carried no ruled hierarchy: the
        powder-constellation motif reconstructed natively, motif fidelity
        measured PASS, and the task reached Gate 2.  Wiring the ruled front
        hierarchy into the container composer changed the emitted graph: the
        front's own geometry now occupies the motif surface, the emitted motif
        nodes no longer carry the requested family's geometry, and the
        motif-family checker fires CONTAINER_MOTIF_FAMILY_MISMATCH.  The
        pipeline does exactly what it is built to do — it fails closed and
        parks the task at ``awaiting_container_profile`` for a human.

        §BB5(c) ruled that this FAIL "stands as a recorded known-red", with the
        closing line that an executor finding it red and "fixing" it has
        defeated the instrument rather than the defect.  §BE(a) invoked that
        clause's own yield provision and said what the sentence reaches: the
        PIPELINE BEHAVIOUR stands (the mismatch fires, the task parks) and the
        RECORD asserts that behaviour verbatim.  So the assertions below are
        not a lowered bar and not a silenced checker — they are the checker
        PINNED.  Nothing here weakens the mismatch: if the family check ever
        stops firing, or fires with a different code set, or the task ever
        stops parking, this test goes RED.  That is the instrument.

        The method name is deliberately NOT changed.  This failure is known by
        this name across OWNER_BLOCKER_CLEARANCE.md and OWNER_REVIEW_QUEUE.md;
        renaming it would break the audit trail that earned the ruling.  The
        docstring, not the name, carries the truth.

        Restoring native motif reconstruction on a wired front is real work,
        not a test edit — it is an open engine item, not a defect in the
        instrument that reports it.

        §BH65(c)3 (2026-09-23) DID THAT WORK, AND THIS PIN MOVES WITH IT — THE
        INSTRUMENT DOES NOT. The owner ruled §BH65: "the composer discarded
        them ... the ten days go to closing it". The composer now draws the
        concept's motif on the wired front where §AU1 (C8, OWNER RULED, LIVE)
        lets decoration print — "the decoration element sits above or behind"
        — and on this fixture's bottle the confirmed front zone has room ABOVE
        the mark's 1.0x cap-height clear space, so a powder-constellation FIELD
        prints there. The emitted motif nodes now carry the requested family's
        geometry, so the family check reads MEASURED_PASS on its own terms:
        not one line of `validate_motif_fidelity` changed, its expectation
        table included. The task no longer parks; it reaches Gate 2. The
        pipeline behaviour this test pinned was the checker firing on a front
        that discarded the motif — that front is gone from this fixture, and
        the assertions below pin what replaced it, verbatim. The known-red is
        reported to the owner as a reading of new content, never as a bar
        moved. Where §AU1 leaves no room (task 89's compact: 7.703 mm above
        its mark), the motif is still not placed on the front, and the record
        says so.
        """
        img = self._regenerated("scattered powder constellation motif", "v_pc")
        aria = ARIAAgent(self.task.id)
        ProductContainerTarget().begin_output(aria, img)
        out = self.task.packaging_outputs.first()
        aria.resume_after_container_profile(
            out.id, {"archetype": "bottle", "height_mm": 110, "width_mm": 40})
        self.task.refresh_from_db()
        out.refresh_from_db()
        # §BH65(c)3: the task no longer parks — the wired front now carries the
        # requested family's geometry above the mark, where §AU1 lets it print
        assert self.task.status == "awaiting_gate_2"
        assert out.spec_sheet["container_motif_spec/1.0"]["rendered_via"] == \
            "powder_constellation"
        # THE PIN, MOVED WITH THE ENGINE AND NOT WITH THE INSTRUMENT: the family
        # check passes on its own terms, no failure code is written anywhere,
        # and the parking decision is gone from both downstream surfaces
        mf = out.spec_sheet["container_motif_fidelity_report"]
        assert mf["failures"] == []
        assert mf["axes"]["motif_family"]["state"] == "MEASURED_PASS"
        assert out.spec_sheet["container_reconstruction"] == {
            "status": "RECONSTRUCTED", "blockers": []}
        assert "generation_error" not in out.spec_sheet
        # and the contract's record says where the motif printed, and why there
        front = out.spec_sheet["container_composer_vocabulary_realization/1.0"]["front"]
        assert front["layout"] == "field" and front["drawn"] == ["motif-field"]
        assert front["placed"] == "above the mark's clear space"
        # §10 native-output manifest + §14 Review Board surfacing
        man = out.spec_sheet["container_native_output_manifest"]
        assert man["legacy_raster_preserved"] is True
        assert "BODY_FRONT" in man["surfaces_with_artwork"]
        labels = {r["label"] for r in ProductContainerTarget().review_sections(self.task)}
        assert "Motif reconstruction" in labels
        assert "Motif fidelity" in labels
        assert "Surfaces with artwork" in labels
        # 2B-3A, amended at §BH26(a): font authority is recorded, and the
        # owner grant now confers VERIFIED_FOR_PRODUCTION on the two
        # sha256-named faces at the production call site, so the
        # confirmation-required code is GONE from the readiness record. The
        # readiness/blocker separation this block always proved still holds,
        # from the other side: reconstruction IS blocked above, the blocker
        # list is exactly the two motif codes, and no font code — present or
        # absent — is among them.
        fa = out.spec_sheet["container_font_authority/1.0"]
        assert fa["faces"] and all(
            f["verification"] == "VERIFIED_FOR_PRODUCTION"
            for f in fa["faces"])                       # §BH26(a) owner grant
        codes = out.spec_sheet["container_production_readiness_codes"]["font"]
        assert codes == []
        assert "CONTAINER_FONT_CONFIRMATION_REQUIRED" not in \
            out.spec_sheet["container_reconstruction"]["blockers"]
        # 2B-3A §5: material realization — this task has no approved references
        # → NOT_APPLICABLE, nothing blocks
        mr = out.spec_sheet["material_influence_realization/1.0"]
        assert mr["state"] == "NO_APPROVED_REFERENCES" and mr["codes"] == []
        # 2B-3B: production methods derived from zones, authority UNVERIFIED by
        # construction; the gate code is a readiness code, not a blocker
        pmr = out.spec_sheet["container_production_method/1.0"]
        assert pmr["methods"] and pmr["all_manufacturer_verified"] is False
        pmcodes = out.spec_sheet["container_production_readiness_codes"]["production_method"]
        assert "CONTAINER_TECHNIQUE_UNVERIFIED" in pmcodes
        assert "CONTAINER_TECHNIQUE_UNVERIFIED" not in \
            out.spec_sheet["container_reconstruction"]["blockers"]
        # 2B-3B commit 2: separations manifest — PROCESS_ARTWORK visible, ink
        # separations present, white underbase REVIEW (transparency unknown)
        sepr = out.spec_sheet["container_production_separations/1.0"]
        names = {s["name"] for s in sepr["separations"]}
        assert "PROCESS_ARTWORK" in names and "SCREEN_INK_1" in names
        assert sepr["white_underbase"]["state"] == "REVIEW_REQUIRED"
        assert out.spec_sheet["container_production_combined_hash"]
        # 2B-3C: quantitative fidelity present; this task's visual graph has no
        # reliable targets for most axes → UNMEASURED, nothing new blocks
        qfr = out.spec_sheet["container_quantitative_fidelity/1.0"]
        assert qfr["counts"]["UNMEASURED"] >= 10
        assert "CONTAINER_MOTIF_COVERAGE_FAILED" not in \
            out.spec_sheet["container_reconstruction"]["blockers"]
        # 2B-3C §7-§10: true wrap production geometry + aligned emission
        wgr = out.spec_sheet["container_wrap_geometry/1.0"]
        assert wgr["wraps"] and all(w["projection_hash"] for w in wgr["wraps"])
        # §BH50(f)(6): a bottle has no wrapped surface, so the seam check
        # places itself off it — NOT_APPLICABLE with its reason, never a pass
        # over nothing. This line asserted `aligned is True` until then: the
        # statement the ruling removes.
        wa = out.spec_sheet["container_wrap_alignment"]
        assert wa["aligned"] is None
        assert wa["seam_check"]["state"] == "NOT_APPLICABLE"
        assert "BODY_FRONT" in wa["seam_check"]["reason"]
        assert "BODY_BACK" in wa["seam_check"]["reason"]
        assert not {"CONTAINER_WRAP_SEAM_CONFLICT",
                    "CONTAINER_TEXT_CROSSES_SEAM"} & set(wa["codes"])
        # 2B-3C §11-§14: coverage/registration/complete colour count present;
        # registration reviews (manufacturer capability unverified)
        pmet = out.spec_sheet["container_production_metrics/1.0"]
        assert pmet["color_count"]["per_method"]
        assert pmet["registration"]["state"] in ("REVIEW_REQUIRED", "NO_INTERACTION")
        # 2B-3C §16: per-reference attribution — no approved refs on this task
        assert out.spec_sheet["material_influence_realization/1.1"]["state"] == \
            "NO_APPROVED_REFERENCES"

    @override_settings(OPENAI_API_KEY="")
    def test_the_usage_record_is_persisted_and_reconciles_on_the_live_path(self):
        """§BH32(f): the container target persists container_font_usage/1.0
        beside the authority record; on the live path the faces that drew are
        exactly the faces the emitted .ai embeds, and no usage code joins the
        font readiness."""
        img = self._regenerated("scattered powder constellation motif", "v_pc")
        aria = ARIAAgent(self.task.id)
        ProductContainerTarget().begin_output(aria, img)
        out = self.task.packaging_outputs.first()
        aria.resume_after_container_profile(
            out.id, {"archetype": "bottle", "height_mm": 110, "width_mm": 40})
        out.refresh_from_db()
        usage = out.spec_sheet["container_font_usage/1.0"]
        assert usage["schema_version"] == "container_font_usage/1.0"
        assert usage["faces"] and all(f["runs"] >= 1 for f in usage["faces"])
        recon = usage["reconciliation"]
        assert recon["status"] == "RECONCILED" and recon["agree"] is True
        assert recon["codes"] == [] and recon["missing_from_artefact"] == [] \
            and recon["unaccounted_in_artefact"] == []
        fa = out.spec_sheet["container_font_authority/1.0"]
        recorded = {f["postscript_name"] for f in fa["faces"]}
        assert {f["postscript"] for f in usage["faces"]} <= recorded | set(recon["embedded"])
        assert out.spec_sheet["container_production_readiness_codes"]["font"] == []

    def test_unsupported_motif_goes_on_to_gate_2_said_beside_approve(self):
        # a motif that cannot be responsibly rebuilt from the supported primitives is never drawn as a raster; [his goal
        # of 2026-10-13, (1): "NO check ever stops a design"] the design goes on to Gate 2, the check it did not pass said
        # beside Approve in its words — it went back to its shape step until then; the report + identity/profile/zones
        # are kept as before.
        img = self._regenerated("iridescent prism facets", "v_ip")
        aria = ARIAAgent(self.task.id)
        ProductContainerTarget().begin_output(aria, img)
        out = self.task.packaging_outputs.first()
        aria.resume_after_container_profile(
            out.id, {"archetype": "bottle", "height_mm": 110, "width_mm": 40})
        self.task.refresh_from_db()
        out.refresh_from_db()
        assert self.task.status == "awaiting_gate_2"
        assert "generation_error" not in out.spec_sheet
        said = out.spec_sheet["self_check/1.0"]["said"]
        assert any(s.startswith("Look at: the concept's motif cannot be drawn as clean lines yet") for s in said), said
        ms = out.spec_sheet["container_motif_spec/1.0"]
        assert ms["reconstruction_capability"] == "REVIEW_REQUIRED"
        assert out.spec_sheet["container_selected_variation/1.0"]["verified"]
        assert out.spec_sheet["container_profile/1.0"]
        assert out.spec_sheet["container_decoration_zones/1.0"]

    def test_review_sections_are_container_specific(self):
        aria = ARIAAgent(self.task.id)
        ProductContainerTarget().begin_output(aria, self.img)
        rows = ProductContainerTarget().review_sections(self.task)
        labels = {r["label"] for r in rows}
        assert "Container" in labels and "Product" in labels
        assert not any(r["label"] == "Template" for r in rows)   # not packaging


    def test_his_go_the_concepts_design_map_is_read_on_its_own_once_per_picture(self):
        """His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): "build the map path to run on its own
        for every new design". When a container design reaches its shape step its approved concept's design map is read
        — one read, on the design's own ledger — kept on the record, and the shape step's first proposal of the front's
        print area is the map's; the same picture approved again is not read again; and nothing is read where the read is
        switched off (as under every test). [His test blocker on design 124, 2026-10-11, (2) and (4)] a face form's is
        read from its lid stood square, never skipped — where no lid can be cut from its picture, UNREAD by name, nothing
        paid."""
        import hashlib

        from django.conf import settings

        from apps.pipeline.services import concept_design_map as dm
        sha = hashlib.sha256(_PNG).hexdigest()
        read = {"schema_version": dm.SCHEMA, "state": dm.MAP_READ, "source_sha256": sha,
                "parts_prompt_version": dm.PARTS_PROMPT_VERSION, "model": settings.CLAUDE_MODEL_HEAVY,
                "parts": [{"kind": "type", "name": "the name", "box": [0.1, 0.5, 0.9, 0.7], "colour": "#9D5045",
                           "seen_text": "LIP GLOSS"}],
                "problems": [], "cost": {"usd": "0.116400", "calls": 1}}
        # [the owner's finding on design 119, 2026-10-03: "NO SILENT FALLBACK"] a map is drawn from only where its every
        # part traces: here, the one line, traced
        traced = {"schema_version": dm.SHAPES_SCHEMA, "state": dm.SHAPES_TRACED, "source_sha256": sha, "problems": [],
                  "params": dict(dm.SHAPE_PARAMS), "types": [{"part": "the name", "seen": "LIP GLOSS", "ink": "#9D5045",
                                                              "box": [0.1, 0.5, 0.9, 0.7]}]}
        aria = ARIAAgent(self.task.id)
        with patch.object(dm, "read_parts", return_value=read) as paid, \
                patch.object(dm, "trace_shapes", return_value=traced):
            ProductContainerTarget().begin_output(aria, self.img)          # switched off, as under every test
            assert not paid.called
            assert dm.SCHEMA not in self.task.packaging_outputs.order_by("-pk").first().spec_sheet
            with override_settings(DESIGN_MAP_READ=True, ANTHROPIC_API_KEY="k"):
                ProductContainerTarget().begin_output(aria, self.img)
                assert paid.call_count == 1 and paid.call_args.args[0].pk == self.task.pk
                assert paid.call_args.args[1] == _PNG
                spec = self.task.packaging_outputs.order_by("-pk").first().spec_sheet
                assert spec[dm.SCHEMA] == read
                front = next(z for z in spec["container_decoration_zones/1.0"]["zones"]
                             if z["zone_type"] == "FRONT_PRINT_ZONE")
                assert front["proposed_from"] == "the concept picture's map: the parts it prints", front
                ProductContainerTarget().begin_output(aria, self.img)      # the same picture: kept, not read again
                assert paid.call_count == 1
                assert self.task.packaging_outputs.order_by("-pk").first().spec_sheet[dm.SCHEMA] == read
        from apps.pipeline.targets.container import _read_design_map
        with override_settings(DESIGN_MAP_READ=True, ANTHROPIC_API_KEY="k"), patch.object(dm, "read_parts") as paid, \
                patch.object(dm, "read_lid_parts") as lid_paid:
            got = _read_design_map(aria, "compact", self.img)
            assert got == {"state": dm.MAP_UNREAD, "detail": "its lid could not be traced in the concept picture"}
            assert not paid.called and not lid_paid.called

    def test_his_go_a_vials_name_is_not_stopped_where_its_map_sets_it(self):
        """His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): the map path for a wand vial. At the
        ruled name size "Strawberry" is wider than a 16 mm vial's front and the shape step stopped it; where the design's
        front is set from its concept's map — a map READ of its approved picture naming a type line — the name is set
        where and as large as the picture sets it, and the stop does not apply; without such a map it stops as before."""
        import hashlib

        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.container import map_sets_the_name, name_fits_front
        from apps.pipeline.targets.container.silhouettes import ContainerProfile
        vial = ContainerProfile(archetype="mascara", variant="square", cap_style="wand", height_mm=80.0, width_mm=16.0)
        stop = name_fits_front(vial, "Strawberry Kiss")
        assert stop and stop["word"] == "Strawberry" and stop["word_mm"] > stop["front_mm"]
        assert name_fits_front(vial, "Strawberry Kiss", map_sets_name=True) is None
        output = PackagingOutput.objects.create(task=self.task, approved_image=self.img, spec_sheet={})
        read = {"state": dm.MAP_READ, "source_sha256": hashlib.sha256(_PNG).hexdigest(),
                "parts": [{"kind": "type", "name": "the name", "box": [0.1, 0.5, 0.9, 0.6]}]}
        assert map_sets_the_name({dm.SCHEMA: read}, output)
        assert not map_sets_the_name({dm.SCHEMA: dict(read, parts=[{"kind": "band", "box": [0, 0, 1, 1]}])}, output)
        assert not map_sets_the_name({dm.SCHEMA: dict(read, source_sha256="ab" * 32)}, output)
        assert not map_sets_the_name({}, output)

    def test_his_word_the_brief_is_read_in_its_own_product_words_never_its_copy(self):
        """His word after the fix for design 118 (2026-10-03, OWNER_BLOCKER_CLEARANCE.md): "the trend search uses the
        brief's own product words (lip gloss, wand vial), for every design". 118's brief says its product is a lip gloss
        in a slim wand vial; its carton's back copy says to apply it "alone or over lipstick" — and that copy made the
        product a lipstick: the trend search looked for lipstick cartons and the shape step would have proposed a
        lipstick. Read in its own product words, never its copy: the form is the wand vial, the trend search's words are
        the brief's own, and the shape step proposes a wand vial."""
        from apps.pipeline.services import trend_board
        from apps.pipeline.targets.container import _infer_profile, forms_named_in, form_of_task, product_words
        brief = ("BBROSE Rose Glaze Lip Gloss\n\nProduct: BBROSE Rose Glaze Lip Gloss (imaginary test product).\n"
                 "Type: lip gloss in a slim wand vial with a doe-foot applicator, plus its\n"
                 "tall slim carton (straight tuck end).\n\nColours: deep berry, hot pink, pale pink, cream.\n\n"
                 "Vial copy: BBROSE logo, \"Rose Glaze\", 8 ml.\nKeep the vial's words horizontal.\n"
                 "Carton front: BBROSE logo, \"Rose Glaze\", the hero graphic.\n"
                 "Carton back: How to use: apply to lips alone or over lipstick. /\n"
                 "Ingredients: Polybutene, Parfum. / Batch code place. /\nMade in UAE.")
        # what its copy made of it: the copy's "lipstick" beside the product's own wand vial — read whole, the first of
        # the fixed order (lipstick) won; [his goal of 2026-10-06, item 1] two forms in two clauses are never chosen
        # between, and the copy is not read at all (below)
        assert forms_named_in(brief) == ["mascara", "lipstick"]
        words = product_words(brief)
        assert "over lipstick" not in words and "Polybutene" not in words and "hero graphic" not in words
        assert "lip gloss in a slim wand vial" in words and "Colours: deep berry" in words
        task = DesignTask.objects.create(brand=self.brand, task_text=brief, status="queued", design_target="packaging")
        assert form_of_task(task) == "mascara"
        # [re-pinned by his goal of 2026-10-10, item 4: "Search with the product's own words ... not generic
        # "packaging""] its carton searched as the product's box; the product as itself
        assert trend_board.subject_of(task) == "lip gloss wand vial box"
        task.design_target = "product_container"
        assert trend_board.subject_of(task) == "lip gloss wand vial"
        assert _infer_profile(task).archetype == "mascara"

class PipelineHandoffColourTests(TestCase):
    """§BH55 Phase 4 — the four colour sources, measured beside each other.

    The queue called this "the dead colour dict". It is not dead: it is what the NATIVE HANDOFF draws with, and what
    it replaces — the design's own concept-authority colours — is live. These tests state all four sources exactly
    so none of them drifts unseen, and so the day the owner rules, the change moves a pin rather than nothing.

    No hex is asserted to be RIGHT here. Which colours a dropper's handoff should draw with is his line (§BH52;
    §BH50(d)), and it is entry 12 on the ACCEPTANCE-TIME list. This measures; it does not rule.
    """

    def test_the_handoff_colours_are_the_constant_the_dropper_spec_carries(self):
        from apps.pipeline.targets.container import HANDOFF_COLOURS
        self.assertEqual(HANDOFF_COLOURS,
                         {"body": "#D8BEB8", "cap": "#B76E79", "product": "#C9A6A0"})

    def test_the_body_it_draws_is_the_literal_the_palette_layer_moves(self):
        """The sheet draws the brand swatch; the handoff draws the colour from before the layer touched it."""
        from apps.ire.compose_dropper import MATERIALS, palette_row
        from apps.pipeline.targets.container import HANDOFF_COLOURS
        row = palette_row("BODY_BASE")
        self.assertEqual(row["literal"].upper(), HANDOFF_COLOURS["body"],
                         "the handoff's body is the composer's pre-palette literal")
        self.assertEqual(row["role"], "accent_nude")
        self.assertNotEqual(row["hex"].upper(), HANDOFF_COLOURS["body"].upper(),
                            "§BH50(d) moves BODY_BASE to its brand swatch; if it no longer does, this pin is stale")
        self.assertEqual(MATERIALS["PRODUCT_FILL"][0].upper(), HANDOFF_COLOURS["product"],
                         "the product tint is the same in both")

    def test_the_cap_it_draws_is_drawn_nowhere_else(self):
        from apps.ire.compose_dropper import MATERIALS
        from apps.pipeline.targets.container import HANDOFF_COLOURS
        drawn = {v[0].upper() for v in MATERIALS.values()}
        self.assertNotIn(HANDOFF_COLOURS["cap"].upper(), drawn,
                         "§BH50(d): 'a hard-coded dict whose cap #B76E79 the artefact never draws'")
        self.assertIn("#BC7480", drawn, "the rose-gold base the composer does draw")

    def test_the_composer_falls_back_to_a_fourth_pair_again_drawn_nowhere(self):
        """compose_container_graph called with no colours draws neither the handoff's pair nor the composer's."""
        from apps.ire.compose_container import _DEFAULT_BODY, _DEFAULT_CAP
        from apps.ire.compose_dropper import MATERIALS
        from apps.pipeline.targets.container import (_DEFAULT_BODY_HEX, _DEFAULT_CAP_HEX,
                                                     HANDOFF_COLOURS)
        drawn = {v[0].upper() for v in MATERIALS.values()}
        self.assertEqual((_DEFAULT_BODY.upper(), _DEFAULT_CAP.upper()), ("#EAD7D2", "#C9A24B"))
        self.assertEqual((_DEFAULT_BODY_HEX.upper(), _DEFAULT_CAP_HEX.upper()), ("#EAD7D2", "#C9A24B"),
                         "the target and the composer hold the same fallback pair")
        for h in (_DEFAULT_BODY, _DEFAULT_CAP):
            self.assertNotIn(h.upper(), drawn)
        self.assertNotEqual(_DEFAULT_BODY.upper(), HANDOFF_COLOURS["body"].upper())

    def test_the_sheet_is_not_what_reads_them(self):
        """The dropper sheet takes no colours at all — so the constant exists only for the spec's two readers."""
        import inspect

        from apps.ire.compose_dropper import compose_dropper_sheet
        self.assertNotIn("colors", inspect.signature(compose_dropper_sheet).parameters,
                         "the sheet now takes colours — the constant's note is stale")

    def test_source_guard_the_native_handoff_reads_the_spec_colours(self):
        """SOURCE-STRING GUARD (§Y2(b)) — asserts nothing about behaviour.

        It reads two literals out of `apps/pipeline/services/native_handoff.py` and says only that they are
        present. It cannot tell you the handoff draws anything: what it defends is that the constant's own note,
        which names this reader, does not quietly become false.
        """
        import inspect

        from apps.pipeline.services import native_handoff
        src = inspect.getsource(native_handoff)
        self.assertIn('spec.get("colors")', src,
                      "the native handoff no longer reads spec['colors'] — the constant's note is stale")
        self.assertIn("colors=colors", src,
                      "the native handoff no longer hands them to the composer — the note is stale")

    def test_source_guard_the_rebind_still_discards_a_computed_value(self):
        """SOURCE-STRING GUARD (§Y2(b)) — asserts nothing about behaviour.

        It reads three literals out of `reconstruct_container` and compares two of their positions. It cannot tell
        you a colour is discarded; what it defends is that ACCEPTANCE-TIME entry 12, which says the concept-
        authority colours are computed and then thrown away, cannot quietly stop being true — the day the sampling
        is removed or the rebind moves above it, this fails and the entry is re-read.

        [The owner's answer to the UI directions of 2026-09-25 — his pick, the design page "pick an element and try
        colours and faces from a library that stays open": the colours are derived by `_composer_inputs`, moved out of
        `reconstruct_container` unchanged so the design loop derives a face exactly as production does. The two
        literals are read in the derivation, and the derivation's call in `reconstruct_container` must still come
        before the rebind — the same reading, whole.]
        """
        import inspect

        from apps.pipeline.targets.container import _composer_inputs, reconstruct_container
        derivation = inspect.getsource(_composer_inputs)
        src = inspect.getsource(reconstruct_container)
        self.assertIn("dominant_color_hex(color_src)", derivation,
                      "the body sampled from the approved concept")
        self.assertIn('colors["cap"] = cap_hex', derivation,
                      "the confirmed profile's own recorded cap")
        self.assertLess(src.index("_composer_inputs(aria.task"), src.index("colors = dict(HANDOFF_COLOURS)"),
                        "the rebind must come after what it discards, or this reading is wrong")


class ConfirmContainerEndpointTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        group, _ = Group.objects.get_or_create(name=ROLE_REVIEWER)
        self.user = User.objects.create_user("r", "r@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)
        self.task = DesignTask.objects.create(
            brand=self.brand, task_text="gloss", status="awaiting_container_profile",
            design_target=DesignTarget.PRODUCT_CONTAINER.value)
        img = GeneratedImage.objects.create(
            task=self.task, direction_name="D", prompt_used="p", variation_number=1)
        self.out = PackagingOutput.objects.create(
            task=self.task, approved_image=img,
            spec_sheet={"backend": "container",
                        "container_profile": {"archetype": "bottle"}})

    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_profile_only_refuses_with_proposed_zones(self, mock_delay):
        # 2B-1: a confirmed profile without confirmed zones does NOT transition
        # — it returns the decoration-zone refusal + PROPOSED zones (§10/§12).
        resp = self.client.post(
            f"/api/tasks/{self.task.id}/confirm_container_profile/",
            {"profile": {"archetype": "jar", "height_mm": 60, "width_mm": 70, "depth_mm": 70}},
            content_type="application/json")
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"] == "CONTAINER_DECORATION_ZONE_CONFIRMATION_REQUIRED"
        assert body["zones"], "proposals must be surfaced, never auto-confirmed"
        assert all(z["user_confirmation_state"] == "PROPOSED"
                   for z in body["zones"])
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_container_profile"   # no transition
        mock_delay.assert_not_called()

    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_confirmed_zones_transition_and_enqueue(self, mock_delay):
        # first the refusal surfaces the proposals ...
        r1 = self.client.post(
            f"/api/tasks/{self.task.id}/confirm_container_profile/",
            {"profile": {"archetype": "jar", "height_mm": 60, "width_mm": 70, "depth_mm": 70}},
            content_type="application/json")
        zones = r1.json()["zones"]
        for z in zones:
            z["user_confirmation_state"] = "USER_CONFIRMED"
        # ... then confirming the FULL profile + confirmed zones transitions
        r2 = self.client.post(
            f"/api/tasks/{self.task.id}/confirm_container_profile/",
            {"profile": {"archetype": "jar", "height_mm": 60, "width_mm": 70, "depth_mm": 70},
             "zones": zones}, content_type="application/json")
        assert r2.status_code == 200
        assert r2.json()["combined_hash"]
        self.task.refresh_from_db()
        assert self.task.status == "generating_dieline"     # transient generating
        mock_delay.assert_called_once()
        sent = mock_delay.call_args.args
        assert sent[2]["archetype"] == "jar" and sent[2]["height_mm"] == 60.0
        self.out.refresh_from_db()
        spec = self.out.spec_sheet
        assert spec["container_profile/1.0"]["confirmation_state"] == "CONFIRMED"
        assert spec["container_decoration_zones/1.0"]["confirmation_state"] == "CONFIRMED"
        assert spec["container_confirmation"]["combined_hash"]

    @patch("apps.pipeline.services.claude_service.call_claude")
    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_confirm_makes_no_provider_calls(self, mock_delay, mock_claude):
        # the contract + gate are pure — neither a refusal nor a successful
        # confirmation may reach the provider (reconstruction is enqueued, and
        # its worker is out of scope here / mocked).
        r1 = self.client.post(
            f"/api/tasks/{self.task.id}/confirm_container_profile/",
            {"profile": {"archetype": "jar", "height_mm": 60, "width_mm": 70, "depth_mm": 70}},
            content_type="application/json")
        zones = r1.json()["zones"]
        for z in zones:
            z["user_confirmation_state"] = "USER_CONFIRMED"
        self.client.post(
            f"/api/tasks/{self.task.id}/confirm_container_profile/",
            {"profile": {"archetype": "jar", "height_mm": 60, "width_mm": 70, "depth_mm": 70},
             "zones": zones}, content_type="application/json")
        mock_claude.assert_not_called()

    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_confirmed_but_invalid_zone_marks_review_required(self, mock_delay):
        r1 = self.client.post(
            f"/api/tasks/{self.task.id}/confirm_container_profile/",
            {"profile": {"archetype": "jar", "height_mm": 60, "width_mm": 70, "depth_mm": 70}},
            content_type="application/json")
        zones = r1.json()["zones"]
        for z in zones:
            z["user_confirmation_state"] = "USER_CONFIRMED"
        zones[0]["x"] = 99999                            # shove it out of bounds
        r2 = self.client.post(
            f"/api/tasks/{self.task.id}/confirm_container_profile/",
            {"profile": {"archetype": "jar", "height_mm": 60, "width_mm": 70, "depth_mm": 70},
             "zones": zones}, content_type="application/json")
        assert r2.status_code == 409
        body = r2.json()
        assert body["error"] == "CONTAINER_DECORATION_ZONE_CONFIRMATION_REQUIRED"
        assert any(d.startswith("CONTAINER_ZONE_OUT_OF_BOUNDS")
                   for d in body["detail"])
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_container_profile"   # no transition
        self.out.refresh_from_db()
        # set-level state is honest: confirmed-but-failed reads REVIEW_REQUIRED
        assert (self.out.spec_sheet["container_decoration_zones/1.0"]
                ["confirmation_state"] == "REVIEW_REQUIRED")
        mock_delay.assert_not_called()

    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_bad_archetype_rejected(self, mock_delay):
        resp = self.client.post(
            f"/api/tasks/{self.task.id}/confirm_container_profile/",
            {"profile": {"archetype": "teapot"}}, content_type="application/json")
        assert resp.status_code == 400
        mock_delay.assert_not_called()

    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_malformed_zones_rejected(self, mock_delay):
        # §16 boundary: a junk zones payload is a 400, never a 500
        r1 = self.client.post(
            f"/api/tasks/{self.task.id}/confirm_container_profile/",
            {"profile": {"archetype": "jar", "height_mm": 60, "width_mm": 70, "depth_mm": 70},
             "zones": "not-a-list"}, content_type="application/json")
        assert r1.status_code == 400
        r2 = self.client.post(
            f"/api/tasks/{self.task.id}/confirm_container_profile/",
            {"profile": {"archetype": "jar", "height_mm": 60, "width_mm": 70, "depth_mm": 70},
             "zones": ["oops", 3]}, content_type="application/json")
        assert r2.status_code == 400
        mock_delay.assert_not_called()


class HisAnswers122TheBriefsSizeTests(TestCase):
    """His answers after the fixes for design 122 (2026-10-08, transcribed at fc88e8d), (2): "the drawing must always
    print my brief's size (60 ml), never the picture's text. Confirm that holds for every design." A container's back
    carries his brief's size under "Net content" where his back copy states none; its front's net content is his
    brief's size, else the record's as held, else none."""

    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")

    def _task(self, text, product=None):
        return DesignTask.objects.create(brand=self.brand, product=product, task_text=text,
                                         design_target="product_container", status="awaiting_gate_1")

    def test_the_back_carries_his_size_where_his_back_copy_states_none(self):
        from apps.pipeline.targets.container import NET_CONTENT_HEADING, back_copy
        task = self._task('Rose Blossom\n\nFront copy: "Rose Blossom", 60 ml ℮ 2 fl oz.\n'
                          "Back copy: How to use: massage into clean hands. / Made in UAE.\n")
        sections = back_copy(task)["sections"]
        assert sections[-1] == {"heading": NET_CONTENT_HEADING, "text": "60 ml ℮ 2 fl oz",
                                "source": "his brief's size, in its front copy"}
        task.task_text += "\nBack copy: How to use: massage. / Net content: 60 ml ℮ 2 fl oz. / Made in UAE.\n"
        task.task_text = task.task_text.replace("Back copy: How to use: massage into clean hands. / Made in UAE.\n", "")
        # his back copy states the size itself: his line, never a second one
        assert [s["heading"] for s in back_copy(task)["sections"]].count(NET_CONTENT_HEADING) == 1
        assert back_copy(self._task("Rose Blossom\n\nBack copy: Made in UAE.\n"))["sections"][-1]["heading"] != (
            NET_CONTENT_HEADING)

    def test_the_fronts_net_content_is_his_size_before_the_records(self):
        from apps.pipeline.targets.container import net_content
        product = Product.objects.create(brand=self.brand, product_id="SK-1", name="Rose", category="SK", year=2026,
                                         net_weight="100 ml e 3.38 fl. oz.")
        assert net_content(self._task("Rose\n\nSize: 60 ml ℮ / 2 fl oz.\n", product)) == "60 ml ℮ / 2 fl oz"
        assert net_content(self._task("Rose\n", product)) == "100 ml e 3.38 fl. oz."
        assert net_content(self._task("Rose\n")) is None


@override_settings(ANTHROPIC_API_KEY="")
class HisReviewC7NeverAnEmptyLabelTests(TestCase):
    """[His review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL: 127's and 130's backs print only
    "Net content" ... Every back label carries the full set (description, ingredients, how to use, warnings, made in, net
    content, batch/exp, QR). When the brief gives no back copy, write sensible standard copy for that product type and
    mark it "not confirmed — please check" beside Approve."] Driven on 127's own brief and its back's own size."""

    BRIEF_127 = (' BBROSE Cocoa Fondant Matte Lipstick, 3.5 g bullet. A creamy matte nude-brown. Style: gourmand pop — '
                 'butter yellow and cocoa brown. Front copy: "COCOA FONDANT", "Matte Lipstick", "3.5 g". English and '
                 'Arabic.\n\n[Container type: lipstick]')
    #: 127's back print zone as its record holds it
    ZONES_127 = [{"zone_type": "BACK_PRINT_ZONE", "zone_id": "back", "x": 0.0, "y": 0.0, "width": 20.0,
                  "height": 58.4, "safe_margin_mm": 1.5}]

    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x", website="https://www.bbrose.com")

    def _task(self, text):
        return DesignTask.objects.create(brand=self.brand, task_text=text, design_target="product_container",
                                         status="awaiting_gate_1")

    def test_a_brief_with_no_back_copy_prints_the_full_set_each_written_piece_marked(self):
        from apps.pipeline.services import label_copy as lc
        from apps.pipeline.targets.container import BATCH_HEADING, MADE_IN_HEADING, NET_CONTENT_HEADING, label_back
        back = label_back(self._task(self.BRIEF_127), {})
        heads = [s["heading"] for s in back["sections"]]
        assert heads == ["Description", "How to use", "Ingredients", "Warnings", MADE_IN_HEADING, NET_CONTENT_HEADING,
                         BATCH_HEADING], heads
        by = {s["heading"]: s for s in back["sections"]}
        assert all(by[h]["source"] == lc.WRITTEN_SOURCE for h in ("Description", "How to use", "Ingredients",
                                                                  "Warnings", MADE_IN_HEADING))
        assert "Ricinus Communis" in by["Ingredients"]["text"]          # a lipstick's typical list, never a cream's
        assert by[NET_CONTENT_HEADING]["text"] == "3.5 g" and by[BATCH_HEADING]["text"] == lc.BATCH_EXP
        assert back["qr"] == "https://www.bbrose.com" and back["made_in"] == lc.MADE_IN_PLACEHOLDER
        assert not any("check" in s["text"] for s in back["sections"])  # the words to check are beside Approve only

    def test_his_brief_copy_wins_piece_by_piece(self):
        from apps.pipeline.services import label_copy as lc
        from apps.pipeline.targets.container import MADE_IN_HEADING, label_back
        back = label_back(self._task(self.BRIEF_127 + "\nBack copy: How to use: Glide over the lips. / Ingredients: "
                                                       "Castor Oil, Candelilla Wax. / Made in UAE.\n"), {})
        by = {s["heading"]: s for s in back["sections"]}
        assert by["How to use"]["text"] == "Glide over the lips." and by["How to use"]["source"] != lc.WRITTEN_SOURCE
        assert by["Ingredients"]["text"] == "Castor Oil, Candelilla Wax." and "Ricinus" not in str(back["sections"])
        assert set(back["written"]) == {"description", "warnings"}
        assert MADE_IN_HEADING not in by                                   # his "Made in UAE." stands for it

    def test_the_pieces_are_written_once_by_the_strongest_model_and_never_paid_twice(self):
        import json

        from django.conf import settings

        from apps.pipeline.services import label_copy as lc
        answer = {"description": "A matte cocoa lipstick.", "how_to_use": "Apply to lips.",
                  "ingredients": "Ricinus Communis Seed Oil, Ascorbyl Palmitate.", "warnings": "External use only."}
        from types import SimpleNamespace
        spec, about = {}, "Cocoa Fondant Matte Lipstick"
        reply = SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(answer))])
        with override_settings(ANTHROPIC_API_KEY="k", LABEL_COPY_WRITING=True), patch(
                "apps.pipeline.services.claude_service.call_claude", return_value=reply) as call:
            assert lc.ensure(spec, about, lc.FIELDS) == answer
            assert lc.ensure(spec, about, lc.FIELDS) == answer             # kept with the design: nothing paid
            assert lc.ensure(spec, about, ["warnings"]) == {"warnings": "External use only."}
            assert call.call_count == 1
            assert call.call_args.kwargs["model"] == settings.CLAUDE_MODEL_HEAVY
            assert call.call_args.kwargs["operation"] == lc.OPERATION
        from apps.pipeline.services.cost_ledger import FIDELITY_OPERATIONS
        assert lc.OPERATION in FIDELITY_OPERATIONS                        # a $0 hold never leaves the label empty
        # the call cannot be made: the type's standard copy stands, said on the record
        spec = {}
        with override_settings(ANTHROPIC_API_KEY="k", LABEL_COPY_WRITING=True), patch(
                "apps.pipeline.services.claude_service.call_claude", side_effect=RuntimeError("refused")):
            got = lc.ensure(spec, about, lc.FIELDS)
        assert got == {f: lc.STANDARD["lip"][f] for f in lc.FIELDS} and spec[lc.SCHEMA]["by"] == lc.FROM_STANDARD

    def test_127s_back_stands_with_the_full_set_and_each_written_piece_is_shown_beside_approve(self):
        """The shape step's own step (``ensure_label``) on 127's brief and back zone: the full set trilingual where it
        stands, the written pieces shortened or in English only where it does not — measured, never a stop — and every
        written piece, the placeholder origin and the QR's address listed beside Approve, "not confirmed — please
        check"."""
        from types import SimpleNamespace

        from apps.ire import self_check
        from apps.ire.compose_container import compose_information_panels
        from apps.pipeline.services import label_copy as lc
        from apps.pipeline.targets.container import (LABEL_FORM_KEY, ensure_label, label_back, label_languages,
                                                     trilingual_sections)

        def translate(english, task=None, log=None):
            return {"es": {k: "ES " + v for k, v in english.items()},
                    "ar": {k: "عربي " + v for k, v in english.items() if k != "ingredients"}}
        spec = {}
        aria = SimpleNamespace(task=self._task(self.BRIEF_127), log=lambda *a, **k: None)
        with patch("apps.pipeline.services.panel_translate.translate_panel_info", side_effect=translate) as tr:
            ensure_label(aria, spec, self.ZONES_127, 20.0)
            ensure_label(aria, spec, self.ZONES_127, 20.0)                 # drawn again: nothing translated again
            assert tr.call_count == 1
        chosen = spec[LABEL_FORM_KEY]
        assert chosen["form"] in lc.FORMS and "stands" not in chosen, chosen
        back = label_back(aria.task, spec)
        sections, codes = trilingual_sections(back["sections"], back["kept"], languages=label_languages(spec))
        assert codes == []
        groups, fit = compose_information_panels(sections, self.ZONES_127, 20.0, 0.0, 0.0, heading_role="heading",
                                                 copy_role="body", qr_url=back["qr"] if chosen["qr"] else None)
        assert fit["fits"] is True and not any(str(c).startswith("CONTAINER_BACK_COPY_DOES_NOT_FIT")
                                               for c in fit["codes"]), fit["codes"]
        def names(node):
            yield node.name
            for kid in getattr(node, "children", None) or []:
                yield from names(kid)
        drawn = [n for g in groups for n in names(g)]
        assert ("back-panel-qr" in drawn) is bool(chosen["qr"])
        shown = [r["what"] for r in spec[self_check.CHECKS_SHOWN_KEY] if r["code"] == lc.NOT_CONFIRMED]
        assert len(shown) >= 6 and all(w.endswith(lc.NOT_CONFIRMED_WORDS) for w in shown), shown
        assert any("ingredients" in w for w in shown) and any("made in UAE" in w for w in shown)
        assert any("https://www.bbrose.com" in w for w in shown)

    def test_the_smallest_back_with_the_types_standard_copy_never_stops(self):
        """A 15 × 25 mm back — smaller than any the wiring check draws — given the type's whole standard copy: the
        written pieces shortened, set in English only, and at the last left off one at a time, until the back stands
        — no CONTAINER_BACK_COPY_DOES_NOT_FIT, so no offer and no stop; each piece left off said beside Approve."""
        from types import SimpleNamespace

        from apps.ire import self_check
        from apps.ire.compose_container import compose_information_panels
        from apps.pipeline.services import label_copy as lc
        from apps.pipeline.targets.container import (LABEL_FORM_KEY, ensure_label, label_back, label_languages,
                                                     trilingual_sections)
        zones = [{"zone_type": "BACK_PRINT_ZONE", "zone_id": "back", "x": 0.0, "y": 0.0, "width": 15.0,
                  "height": 25.0, "safe_margin_mm": 1.5}]
        spec = {}
        aria = SimpleNamespace(task=self._task(self.BRIEF_127), log=lambda *a, **k: None)
        ensure_label(aria, spec, zones, 15.0)
        chosen = spec[LABEL_FORM_KEY]
        assert "stands" not in chosen, chosen
        back = label_back(aria.task, spec)
        sections, _codes = trilingual_sections(back["sections"], back["kept"], languages=label_languages(spec))
        _groups, fit = compose_information_panels(sections, zones, 15.0, 0.0, 0.0, heading_role="heading",
                                                  copy_role="body")
        assert fit["fits"] is True and fit["codes"] == [], fit["codes"]
        assert [s["text"] for s in back["sections"] if s["heading"] == "Net content"] == ["3.5 g"]   # his, always
        left = [r["what"] for r in spec[self_check.CHECKS_SHOWN_KEY] if r["what"].startswith("no room on this back")]
        assert len(left) == len(chosen.get("dropped") or []), (left, chosen)
