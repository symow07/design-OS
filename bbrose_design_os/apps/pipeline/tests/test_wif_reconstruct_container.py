"""WI-F (§X3) — DIRECT tests for ``reconstruct_container``.

``apps.pipeline.targets.container.reconstruct_container`` is a 546-line
producer that writes thirty records onto ``PackagingOutput.spec_sheet`` and
feeds every downstream container axis. Until this module it had **no direct
test**. The consequence is on the record: a WI-C mutation dropped the
print-method capability table, the 5.0 pt fallback was taken on every run,
the typography axis stayed green and all 6,649 tests passed.

Two things about that hole are worth stating precisely, because the loose
version of each is wrong.

**It was not unreached — it was unasserted.** ``test_container_target.py``
does drive this function, through ``aria.resume_after_container_profile``.
What no test did was look at the records whose *provenance* the mutation
changed. (``test_container_text_floor.TestTheTableActuallyReachesTheProducer``
says in its docstring that "NOTHING exercises ``reconstruct_container``".
That is not accurate, and it is recorded for the owner rather than edited
here — §X3(c) rules new findings RECORDED, NOT FIXED.)

**On the default container the defect is invisible in the number.** The
proposed front zone's technique is ``screen_printing`` → ``SCREEN_PRINT``,
whose capability-table minimum is 5.0 pt — the *same* number as
``container_text_floor.FALLBACK_FLOOR_PT``. A test asserting the floor's
VALUE would have passed the mutation exactly as the suite did. §W2(b)
anticipated this ("the source is carried on every single run rather than
summarised"), so these tests assert the SOURCE, and use a second container
whose method carries a different number to pin the value as well.

Every test here calls ``reconstruct_container`` directly. The caller wraps it
in ``try/except`` and turns a refusal into ``generation_error``; going through
the caller would test the swallow, not the contract.

MUTATION EVIDENCE (§X3(b)). Three forms of the defect were run against this
module, each restored by copy and verified sha256-identical:

* **M1** — ``_METHOD_DEFAULTS = {}`` in ``container_production_method``.
  Caught here (5 tests) and also by the existing ``test_container_text_floor``
  unit tests (16), which build their methods records from that same table.
* **M2** — ``methods_record = {}`` at the call site. Caught here (9 tests);
  the existing source-string guard did NOT see it, because the literal
  ``measure_typography_metrics(doc, methods_record)`` it greps for is intact.
* **M3** — ``minimum_text_size_pt`` popped from each built method, so the
  table reaches the producer carrying no floor. **Caught ONLY here (8 tests).
  All 161 tests in ``test_container_text_floor``, ``test_container_typography
  _metrics``, ``test_container_target``, ``test_vqr2a_visual_quality_gate``
  and ``test_vqr1_m3_integration`` stayed green.** M3 is the defect class
  §X3 describes, and before this module nothing in the repository saw it.

The sharpest single catch is
``test_the_floor_adjudicates_and_does_not_merely_record``: with a 12.0 pt
floor on the front zone and 8.0 pt type emitted, the honest record says
``below_size_floor: True``. Under M3 the 5.0 pt fallback applies, 8.0 clears
it, and the axis reports ``False`` — a PASS on a container that is below its
floor. That is what "kept the axis green" means in practice.
"""
from __future__ import annotations

import pytest
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from apps.core.models import Brand, Product
from apps.ire import container_text_floor as ctf
from apps.pipeline.agents.aria import ARIAAgent
from apps.pipeline.models import (
    DesignTask,
    Gate1RegenerationJob,
    GeneratedImage,
)
from apps.pipeline.services import container_contract as cc
from apps.pipeline.services.container_visual_graph import (
    SelectedVariationIdentityError,
)
from apps.pipeline.targets import DesignTarget
from apps.pipeline.targets.container import (
    ProductContainerTarget,
    reconstruct_container,
)

fitz = pytest.importorskip("fitz")

_PNG = __import__("base64").b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4"
    "z8Dwn4EBAAT/Af9jZv5kAAAAAElFTkSuQmCC")

#: the confirmed profile a reviewer submits at the container gate
CONFIRMED = {"archetype": "bottle", "variant": "cylindrical",
             "height_mm": 110, "width_mm": 40}

#: Exactly the records ``reconstruct_container`` is responsible for adding to
#: a spec sheet that ``begin_output`` has already seeded. Asserted as a SET
#: rather than spot-checked: a producer that silently stops emitting one of
#: these re-UNMEASURES an axis downstream, which is the failure mode this
#: whole module exists for. Adding a record is meant to fail this test too —
#: a new contract on the spec sheet should be a deliberate edit here.
#:
#: §AV3 adds ``container_brand_strings/1.0``, and this test going red is the
#: mechanism working rather than an obstacle to it: the record is a NEW contract
#: on the spec sheet, so it gets a deliberate edit here, which is exactly what
#: the paragraph above asks for. It is written on EVERY reconstruction,
#: including the clean case where it holds an empty code list — a section that
#: appears only when it has something to say has a silence indistinguishable
#: from its absence, and telling those two apart is what §AV1 spent this
#: tranche repairing one level up in the readiness reader.
PERSISTED_RECORDS = frozenset({
    "colors",
    # [his goal of 2026-10-13, (6): "SEE THE DESIGN ON THE PAGE"] where each drawing stands on the drawing's own pages,
    # for his page's viewer — written on every reconstruction
    "drawing_views/1.0",
    # §BH65(b)2: which record each colour came from — the owner's "say which record each colour should come
    # from", written on EVERY reconstruction so the answer is on the record of every run, not only in a report
    "container_colour_sources/1.0",
    "container_brand_strings/1.0",
    # §BH65(c): the ONE contract's record of the run — each term the selected concept used, whether the run's
    # document drew it, a named code for each it did not. Report only; written on EVERY reconstruction
    "container_composer_vocabulary_realization/1.0",
    "container_composition_metrics/1.0",
    # §BH65(c)2: the finishes — what the concept's sentence asked, where each landed or why it could not, and the
    # plates the emitter wrote (one page each, after the artwork); NOT_EMITTED when the artefact is withheld
    "container_finish_plates/1.0",
    "container_design_graph/1.1",
    # §BH67(c)5: the face the concept named for its product name, read against the granted set, and the face that
    # printed it — written on every container-composer reconstruction, a style-only concept included
    "container_concept_typeface/1.0",
    # [his test finding on design 122's drawing, 2026-10-08, B: "check each drawn colour against the concept by
    # eye-level difference (ΔE)"] each colour drawn against the concept's — written on every container reconstruction
    "container_colour_check/1.0",
    "container_design_graph/2.0",
    "container_fidelity_report",
    "container_font_authority/1.0",
    # §BH32(f): the per-run, per-face usage counter reconciled against the
    # emitted artefact — written on EVERY reconstruction, ARTEFACT_WITHHELD
    # when the brand-string gate withholds the .ai (the same silence rule)
    "container_font_usage/1.0",
    # §BH70(1), item 5 of the list the owner was sent: the front copy measured across on the generic path too — THIS
    # run's record, persisted as the dropper path persists its own
    "container_front_copy_fit/1.1",
    "container_front_back_relationship/1.0",
    "container_logo_metrics/1.0",
    "container_motif_fidelity_report",
    "container_motif_spec/1.0",
    "container_native_output_manifest",
    # [§BH71 PART 1, the owner's goal of 2026-09-28: "the design says when the fallback was used" — which drew the
    # outline, and why, written on EVERY reconstruction: a bottle's template, by name]
    "container_outline_source/1.0",
    # §BH50(f)(2): placeholder copy is its own blocker — one record per piece
    # of copy nobody has written, written on EVERY reconstruction, including
    # the generic path, where it says no back copy was composed (the same
    # silence rule as the two channels above)
    "container_placeholder_copy/1.0",
    # §BH67 HARD STOP: every colour the container composer PRINTS, with the record it came from — written on EVERY
    # reconstruction (NOT_READ on the dropper, whose palette §BH50(f)(9) kept), so its silence is never its absence
    "container_printed_colours/1.0",
    "container_production_combined_hash",
    "container_production_method/1.0",
    "container_production_method_validation",
    "container_production_metrics/1.0",
    "container_production_readiness_codes",
    "container_production_separations/1.0",
    "container_projection_report",
    "container_quantitative_fidelity/1.0",
    "container_reconstruction",
    "container_reference_similarity",
    "container_selected_concept_visual_graph/1.0",
    "container_selected_variation/1.0",
    "container_typography_fidelity_report",
    "container_typography_metrics/1.0",
    "container_wrap_alignment",
    "container_wrap_geometry/1.0",
    "container_zone_containment_report",
    "material_influence_realization/1.0",
    "material_influence_realization/1.1",
    # [his final goal, 2026-10-05, C6: "EVERY ELEMENT IS ITS OWN PIECE"] the native, layered .ai — built in Illustrator,
    # or why not (here: NATIVE_AI_BUILD off under tests) — written wherever the sheet is drawn
    "native_ai/1.0",
    # [his final goal, 2026-10-05, C7: "THE SYSTEM CHECKS ITS OWN WORK"] what the sheet's own check fixed and shows —
    # written on every reconstruction (a withheld sheet says no drawn file was read)
    "self_check/1.0",
    # [his final goal, 2026-10-05, C5c] the profile he confirmed, kept so his choice of a stopped back's offers can
    # make the container again
    "container_confirmed_profile",
    # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL ... Every back label carries the
    # full set"] a brief with no back copy ("a serum") gets the full set: its pieces written for its type and kept (never
    # paid twice), the back translated, the form the written pieces are set in measured on its back, the back panel's
    # fit, and each written piece shown beside Approve — written wherever the back is drawn
    "label_copy_written/1.0",
    "container_translations/1.0",
    "container_label_form/1.0",
    "container_back_panel/1.0",
    "checks_shown/1.0",
})


class ReconstructContainerCase(TestCase):
    """Shared fixture: a Gate-1-approved container task at its profile gate."""

    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-410", name="Rose Nectar Serum",
            category="CO", year=2026, product_type="serum")
        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="a serum",
            status="gate_1_approved",
            design_target=DesignTarget.PRODUCT_CONTAINER.value)

    def _image(self, prompt="p", *, motif=None, vid="v_x"):
        img = GeneratedImage.objects.create(
            task=self.task, direction_name="D", prompt_used=prompt,
            variation_number=1,
            reference_provenance={"variation_identity": vid} if motif else {})
        img.image_file.save("c.png", ContentFile(_PNG), save=True)
        if motif is not None:
            Gate1RegenerationJob.objects.create(
                task=self.task, direction_id="d1",
                status=Gate1RegenerationJob.STATUS_COMPLETED,
                prompts_payload={"variations": [{
                    "variation_id": vid, "title": "V", "prompt": prompt,
                    "motif_signature": motif, "logo_zone": "upper left",
                    "product_name_zone": "centered",
                    "decorative_coverage_pct": 18}]})
        return img

    def _at_the_profile_gate(self, image=None):
        """(aria, output) with the 2B-1 profile + zone records seeded exactly
        as production seeds them — no hand-built spec sheet."""
        aria = ARIAAgent(self.task.id)
        ProductContainerTarget().begin_output(aria, image or self._image())
        return aria, self.task.packaging_outputs.first()

    def _repoint_front_zone(self, out, **overrides):
        """Rewrite the confirmed front zone, re-deriving its hash so the
        fixture stays a well-formed zone record rather than an edited dict."""
        spec = out.spec_sheet
        record = spec["container_decoration_zones/1.0"]
        for i, zone in enumerate(record["zones"]):
            if zone["zone_id"] == "z_front":
                zone.update(overrides)
                zone["zone_hash"] = cc.zone_hash(zone)
                record["zones"][i] = zone
        out.spec_sheet = spec
        out.save()

    def _reconstructed(self, out=None, aria=None):
        aria, out = (aria, out) if out is not None else self._at_the_profile_gate()
        reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        return out.spec_sheet


@override_settings(OPENAI_API_KEY="")
class TheReconstructionContractTests(ReconstructContainerCase):
    """What one direct call is responsible for producing."""

    def test_it_returns_none_and_persists_the_output_itself(self):
        aria, out = self._at_the_profile_gate()
        assert reconstruct_container(aria, out, CONFIRMED) is None
        # read back from the DB, not from the in-memory object: the function
        # owns the save, and a caller that forgot to save must not pass.
        out.refresh_from_db()
        assert out.spec_sheet["container_reconstruction"]["status"] == \
            "RECONSTRUCTED"

    def test_it_persists_exactly_the_records_it_is_responsible_for(self):
        aria, out = self._at_the_profile_gate()
        before = set(out.spec_sheet)
        reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        assert set(out.spec_sheet) - before == PERSISTED_RECORDS

    def test_bh71_a_bottle_says_its_template_drew_and_why(self):
        """§BH71 PART 1: \"the design says when the fallback was used\" — on every form, not only where a trace ran:
        a screw-cap bottle, whose outline no trace reaches yet, is drawn by its template, and its record says so by
        name and in words."""
        from apps.pipeline.services import concept_outline as co
        from apps.pipeline.targets.container import OUTLINE_SOURCE_KEY
        aria, out = self._at_the_profile_gate()
        reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        source = out.spec_sheet[OUTLINE_SOURCE_KEY]
        # [§BH71 PART 1, the elevation half: a form drawn in elevation is traced now — this fixture's picture is one
        # pixel, too small to read, so the template draws and says why]
        assert (source["source"], source["reason"]) == (co.TEMPLATE_FALLBACK, co.TRACE_IMAGE_UNREADABLE), source
        assert co.words(source) == "the bottle template, cylindrical — the fallback: the concept picture could not be read"

    def test_bh71_a_standing_bottle_concept_is_drawn_from_its_trace(self):
        """§BH71 PART 1, the elevation half: a bottle whose approved concept stands in its picture is drawn from the
        outline read about its own axis — the record says so, with the size it is drawn to beside the one its
        picture's proportion gives, and the board says it in words."""
        from apps.pipeline.services import concept_outline as co
        from apps.pipeline.targets.container import OUTLINE_SOURCE_KEY
        from apps.pipeline.tests.test_vqr2b_concept_analysis import _bottle_png
        image = self._image()
        image.image_file.save("standing.png", ContentFile(_bottle_png()), save=True)
        aria, out = self._at_the_profile_gate(image)
        reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        source = out.spec_sheet[OUTLINE_SOURCE_KEY]
        assert (source["source"], source["kind"]) == (co.TRACED_FROM_CONCEPT, co.PROFILE), source
        assert source["drawn_mm"] == [40, 110] and abs(source["picture_height_mm"] - 144.0) < 8.0, source
        rows = {r["label"]: r["value"] for r in ProductContainerTarget().review_sections(self.task)}
        assert rows["Drawn outline"].startswith("traced from the concept — its outline read about its own axis")


    def test_it_republishes_the_confirmed_profile_it_was_given(self):
        aria, out = self._at_the_profile_gate()
        spec = self._reconstructed(out, aria)
        profile = spec["container_profile"]
        assert profile["archetype"] == "bottle"
        assert profile["variant"] == "cylindrical"
        assert profile["height_mm"] == 110 and profile["width_mm"] == 40

    def test_it_emits_an_editable_ai_and_a_png_preview_named_for_the_task(self):
        aria, out = self._at_the_profile_gate()
        reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        assert out.design_preview_ai and out.design_preview
        assert f"container_task_{self.task.id}" in out.design_preview_ai.name
        assert f"container_task_{self.task.id}" in out.design_preview.name
        page = fitz.open(out.design_preview_ai.path)[0]
        # native, not a raster label: the product name is LIVE text and the
        # structure is drawn geometry
        assert "Rose Nectar" in page.get_text()
        assert len(page.get_drawings()) > 3

    def test_the_native_output_manifest_names_the_files_that_were_written(self):
        spec = self._reconstructed()
        views = spec["container_native_output_manifest"]["views"]
        assert views["concept_sheet_ai"] == f"container_task_{self.task.id}.ai"
        assert views["preview_png"] == f"container_task_{self.task.id}.png"

    def test_the_manifest_names_every_record_on_the_sheet_and_not_a_subset(self):
        """The defect `/1.1` exists to close, stated as the property it broke.

        `/1.0` carried a hand-written `reports` list of seven names. It was
        read by eye off the eight consecutive report assignments at
        ``targets/container/__init__.py`` 1406-1414 and it named six of them,
        so it was wrong about a line inside the block it was copied from as
        well as about everything outside it. Asserted here as a SET IDENTITY
        against the sheet rather than as a pinned list of names: a pinned list
        is a third copy of the same set and would drift the same way. The one
        subtracted key is this record itself, which cannot name itself and on
        a resumed run would otherwise appear only because a previous run left
        it behind.
        """
        spec = self._reconstructed()
        man = spec["container_native_output_manifest"]
        assert man["schema_version"] == "container_native_output_manifest/1.1"
        assert "reports" not in man
        assert man["records_on_sheet"] == sorted(
            set(spec) - {"container_native_output_manifest",
                         "container_reconstruction"})

    def test_the_two_records_the_old_hand_written_list_skipped_are_named(self):
        """A regression pin on the specific misses, kept separate on purpose.

        The test above would pass on a manifest that named nothing if the
        sheet held nothing, and it moves whenever the sheet moves. These two
        names are the measured historical defect and they do not move:
        ``container_design_graph/2.0`` was assigned one line ABOVE the first
        name the old list carried, and ``container_typography_fidelity_report``
        was assigned BETWEEN two names it did carry.
        """
        man = self._reconstructed()["container_native_output_manifest"]
        assert "container_design_graph/2.0" in man["records_on_sheet"]
        assert "container_typography_fidelity_report" in man["records_on_sheet"]

    def test_the_extent_of_the_manifest_is_stated_rather_than_left_to_infer(self):
        """§AY0(d): the absence carries its search extent.

        ``container_reconstruction`` is assigned six lines BELOW the manifest,
        so it can never appear in it. Without the extent field a reader has to
        choose between "not produced" and "produced after the count", and
        those are different facts.
        """
        spec = self._reconstructed()
        man = spec["container_native_output_manifest"]
        assert "container_reconstruction" in spec
        assert "container_reconstruction" not in man["records_on_sheet"]
        assert "container_reconstruction" in man["records_on_sheet_extent"]

    def test_a_stale_generation_error_from_an_earlier_refusal_is_cleared(self):
        aria, out = self._at_the_profile_gate()
        spec = out.spec_sheet
        spec["generation_error"] = "CONTAINER_NATIVE_RECONSTRUCTION_FAILED: x"
        out.spec_sheet = spec
        out.save()
        assert "generation_error" not in self._reconstructed(out, aria)

    def test_the_design_graph_is_the_two_point_zero_superset_under_both_keys(self):
        spec = self._reconstructed()
        assert spec["container_design_graph/2.0"] == \
            spec["container_design_graph/1.1"]
        assert spec["container_design_graph/1.1"]["mode"] == "native"
        # 2B-2: the raster label is gone; decoration is native geometry
        assert spec["container_design_graph/1.1"]["decorative_raster_count"] == 0


@override_settings(OPENAI_API_KEY="")
class TheCapabilityTableGovernsTheTypographyFloorTests(ReconstructContainerCase):
    """§W2 — THE ACCEPTANCE CRITERION FOR THIS WORK ITEM.

    ``build_production_methods`` is called here and its result handed to
    ``measure_typography_metrics``. If the capability table stops reaching the
    producer — by any route: the argument dropped, the table emptied, the
    method's minimum going None — §W2(b) makes every run take the 5.0 pt
    fallback and SAY SO in ``floor_source``. These tests read that word.
    """

    def _skip_the_code_place(self, out):
        """[§BH71 (0b): the proposal offers every form a code place, OPTIONAL at the shape step. These tests prove the
        size floor DECIDES on the front and back a person prints; the code place's depicted runs leave BOTTOM unmeasured
        (test_bh71_a_confirmed_code_place_leaves_its_depiction_unmeasured), so here it is skipped, as a person may.]"""
        spec = out.spec_sheet
        record = spec["container_decoration_zones/1.0"]
        record["zones"] = [z for z in record["zones"] if z["zone_type"] != "BOTTOM_CODE_ZONE"]
        out.spec_sheet = spec
        out.save()

    def _floor_runs(self, out=None, aria=None):
        if out is None:
            aria, out = self._at_the_profile_gate()
        self._skip_the_code_place(out)
        spec = self._reconstructed(out, aria)
        record = spec["container_typography_metrics/1.0"]
        assert record["size_floor_runs"], "no container-view run was measured"
        return spec, record

    def test_no_run_takes_the_fallback_when_the_zone_records_a_method(self):
        _, record = self._floor_runs()
        assert record["size_floor_is_a_fallback"] is False
        assert [r for r in record["size_floor_runs"]
                if r["floor_source"] == ctf.SOURCE_FALLBACK] == []

    def test_every_run_names_the_capability_table_as_its_source(self):
        _, record = self._floor_runs()
        # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] this brief ("a serum") now prints the full set on its back:
        # the back's label runs stand on the label's own floor (his correction of 2026-10-07: 3 pt), every other run
        # on the capability table, as before
        label = [r for r in record["size_floor_runs"] if r["node_name"].startswith("back-panel-")]
        assert label and all(r["floor_source"] == ctf.SOURCE_FINE for r in label), label
        for run in record["size_floor_runs"]:
            if run in label:
                continue
            assert run["floor_source"] == ctf.SOURCE_TABLE, run
            assert run["method_types"], run

    def test_the_default_container_hides_the_defect_in_the_number(self):
        """The trap, asserted rather than described.

        SCREEN_PRINT's table minimum and the fallback are BOTH 5.0 pt, so on
        the container the pipeline actually proposes, a test on the floor's
        value cannot tell a governed run from an ungoverned one. This test
        exists to fail loudly if that coincidence ever stops holding, so the
        provenance assertions above are never mistaken for value coverage.
        """
        _, record = self._floor_runs()
        run = record["size_floor_runs"][0]
        assert run["method_types"] == ["SCREEN_PRINT"]
        assert run["floor_pt"] == ctf.FALLBACK_FLOOR_PT == 5.0
        assert run["floor_source"] == ctf.SOURCE_TABLE

    def test_a_method_with_its_own_minimum_carries_that_number_through(self):
        """The value assertion the default container cannot make: hot stamping
        cannot hold 5 pt type, and its 6.0 pt table minimum must be what the
        emitted record measures against."""
        aria, out = self._at_the_profile_gate()
        self._repoint_front_zone(out, permitted_techniques=["hot_stamping"])
        _, record = self._floor_runs(out, aria)
        run = record["size_floor_runs"][0]
        assert run["method_types"] == ["HOT_STAMP"]
        assert run["floor_pt"] == 6.0 != ctf.FALLBACK_FLOOR_PT
        assert run["floor_source"] == ctf.SOURCE_TABLE
        assert record["size_floor_is_a_fallback"] is False

    def test_the_floor_map_is_keyed_by_the_surfaces_the_confirmed_zones_name(self):
        spec, record = self._floor_runs()
        surfaces = {z["parent_surface"] for z in
                    spec["container_decoration_zones/1.0"]["zones"]}
        assert set(record["size_floor_by_surface"]) == surfaces
        assert surfaces == {"BODY_FRONT", "BODY_BACK"}
        for resolved in record["size_floor_by_surface"].values():
            assert resolved["ambiguous"] is False
            assert resolved["floor_pt"] is not None

    def test_the_two_records_agree_because_one_fed_the_other(self):
        """The typography floor is not an independent second opinion — it is
        the method record's own number. Asserted as an identity so the pair
        cannot drift apart silently."""
        spec, record = self._floor_runs()
        methods = {m["method_id"]: m for m in
                   spec["container_production_method/1.0"]["methods"]}
        # an empty map would make every comparison below vacuously true, which
        # is exactly the shape the dropped table produces
        assert methods and record["size_floor_by_surface"]
        for surface, resolved in record["size_floor_by_surface"].items():
            assert resolved["methods"]
            for entry in resolved["methods"]:
                method = methods[entry["method_id"]]
                assert entry["floor_pt"] == method["minimum_text_size_pt"]
                assert method["target_surfaces"] == [surface]

    def test_the_floor_adjudicates_and_does_not_merely_record(self):
        """A floor above the emitted type must produce a finding. Without
        this, a producer could carry the right provenance on a number nothing
        ever compares against.

        ONE RUN -> THREE AT §BB7(c), AND THE OWNER PREDICTED TWO. He authorised
        this update in advance — *"Failure 4's `== [12.0]` -> `[12.0, 12.0]`:
        once ruling 1 lands, updating it is honest"* — and the measurement
        came back THREE. His figure is not wrong about anything he ruled; it
        counted TIERS, and this record counts RUNS. §BD(b), his own second
        ruling, is what makes those different numbers: the name wraps at this
        geometry, so the product-name TIER emits TWO runs. Reported to him
        rather than quietly substituted, and it is the same error class as
        `2d8e4e5`'s "three nodes gained" — a correct count of the wrong input.

        WHAT IS ASSERTED WAS STRENGTHENED RATHER THAN JUST WIDENED, because
        `[12.0] -> [12.0, 12.0, 12.0]` on its own is a weaker test wearing a
        longer literal: three copies of the floor say nothing about WHICH runs
        fell below it, and would stay green if the descriptor vanished and some
        other run took its place. The node names and sizes are pinned instead,
        so this now fails if the front stops carrying a wrapped name, if the
        descriptor stops being emitted, or if §BD(a)'s ruled 5.0 pt drifts.
        MEASURED, not predicted: `product-name-hero-0` and `-1` at 9.0 pt and
        `front-descriptor` at 5.0 pt."""
        aria, out = self._at_the_profile_gate()
        self._repoint_front_zone(out, min_text_size_pt=12.0)
        _, record = self._floor_runs(out, aria)
        assert record["below_size_floor"] is True
        below = record["runs_below_size_floor"]
        assert [r["node_name"] for r in below] == [
            "product-name-hero-0", "product-name-hero-1", "front-descriptor"]
        assert [r["size_pt"] for r in below] == [9.0, 9.0, 5.0]
        assert [r["floor_pt"] for r in below] == [12.0, 12.0, 12.0]
        assert all(r["size_pt"] < r["floor_pt"] for r in below)

    def test_bh71_a_confirmed_code_place_leaves_its_depiction_unmeasured(self):
        """§BH71 (0b), measured: the proposed code place drawn, its panel's two depicted runs leave BOTTOM's size floor
        NOT MEASURED (§BH50(f)(1)) — the typography record says so by name, and under (0a) it is a warning beside
        Approve, never a block: the axis reads UNMEASURED, never PASS and never FAIL."""
        from apps.pipeline.services.visual_quality_gate import _typography_axis
        aria, out = self._at_the_profile_gate()
        zones = out.spec_sheet["container_decoration_zones/1.0"]["zones"]
        assert "BOTTOM_CODE_ZONE" in {z["zone_type"] for z in zones}
        spec = self._reconstructed(out, aria)
        record = spec["container_typography_metrics/1.0"]
        # [His review of 127, 130, 131 and 132, 2026-10-15, C (8): "No empty grey blocks in the files"] a code place no
        # brief names is no longer depicted — its panel held only "BATCH —" — so nothing on BOTTOM is left unmeasured;
        # the axis reads what the drawing holds, never a warning about a placeholder no longer drawn
        assert record["unmeasured"] == []
        axis = _typography_axis(spec, spec.get("container_design_graph/1.1") or {})
        assert axis["state"] == "PASS"

    def test_the_typography_axis_comes_back_decidable(self):
        """VQR-4: the gate demands all four fields be present; any one going
        absent returns the axis to UNMEASURED, which blocks."""
        _, record = self._floor_runs()
        assert record["unmeasured"] == []
        for field in ("materially_overlapping", "below_size_floor"):
            assert field in record, field
        # §BH50(f)(2): placeholder copy is its own blocker, not a typography field
        assert "placeholder_text_present" not in record
        assert record["size_floor_status"] == "OWNER_CALIBRATED"


@override_settings(OPENAI_API_KEY="")
class FailClosedAtTheReconstructionGateTests(ReconstructContainerCase):
    """A blocked reconstruction keeps its evidence — and, [his goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO
    check ever stops a design"], goes on: each check it did not pass said beside Approve in its words."""

    def _unrebuildable(self):
        img = self._image(prompt="ROSE NECTAR bottle, iridescent prism facets",
                          motif="iridescent prism facets", vid="v_ip")
        return self._at_the_profile_gate(img)

    def test_goal_1013_never_stops_an_unrebuildable_motif_goes_on_said_in_its_words(self):
        """It raised CONTAINER_NATIVE_RECONSTRUCTION_FAILED and the design went back to its shape step. It goes on: the
        check it did not pass kept, in its words, with what he can do, for Approve."""
        aria, out = self._unrebuildable()
        reconstruct_container(aria, out, CONFIRMED)                  # never raised
        out.refresh_from_db()
        # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] the back's written pieces are shown beside Approve too,
        # each "not confirmed — please check"; the motif's check is the one other row
        rows = [r for r in out.spec_sheet["checks_shown/1.0"] if r["code"] != "LABEL_COPY_NOT_CONFIRMED"]
        assert [r["code"] for r in rows] == ["VECTOR_RECONSTRUCTION_REVIEW_REQUIRED"]
        assert rows[0]["what"].startswith("the concept's motif cannot be drawn as clean lines yet") and rows[0]["options"]
        assert "_" not in rows[0]["what"]

    def test_the_reports_are_persisted_with_the_check_it_went_past(self):
        """The report that explains it is kept, so the reviewer sees WHY at the gate."""
        aria, out = self._unrebuildable()
        reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        spec = out.spec_sheet
        assert spec["container_reconstruction"] == {
            "status": "BLOCKED",
            "blockers": ["VECTOR_RECONSTRUCTION_REVIEW_REQUIRED"]}
        assert spec["container_motif_spec/1.0"]["reconstruction_capability"] \
            == "REVIEW_REQUIRED"
        # the measurements taken before the refusal survive it
        assert PERSISTED_RECORDS <= set(spec)
        # and the artwork that was refused is still on the output to look at
        assert out.design_preview_ai

    def test_the_refusal_does_not_leave_a_generation_error_of_its_own(self):
        """``generation_error`` belongs to the CALLER's except-block. If
        ``reconstruct_container`` wrote one too, a caller-cleared error would
        reappear from the spec and the two would disagree."""
        aria, out = self._unrebuildable()
        reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        assert "generation_error" not in out.spec_sheet


@override_settings(OPENAI_API_KEY="")
class TheSelectedVariationIsNeverSubstitutedTests(ReconstructContainerCase):
    """2B-2 slice 1: an unverifiable approved image stops the run. It must
    never quietly reconstruct the direction or the first concept instead."""

    def test_an_unverifiable_identity_raises_rather_than_falling_back(self):
        aria, out = self._at_the_profile_gate(self._image(prompt=""))
        with pytest.raises(SelectedVariationIdentityError) as excinfo:
            reconstruct_container(aria, out, CONFIRMED)
        assert "SELECTED_CONTAINER_VARIATION_IDENTITY_REQUIRED" in \
            str(excinfo.value)

    def test_nothing_is_written_when_the_identity_cannot_be_verified(self):
        aria, out = self._at_the_profile_gate(self._image(prompt=""))
        before = set(out.spec_sheet)
        with pytest.raises(SelectedVariationIdentityError):
            reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        assert set(out.spec_sheet) == before
        assert not out.design_preview_ai


@override_settings(OPENAI_API_KEY="")
class ProductionReadinessIsNotAReconstructionBlockerTests(
        ReconstructContainerCase):
    """2B-3A/B/C: readiness codes are a Gate-2 concern. A container whose
    production authority is UNVERIFIED — which is every container in this
    phase, by construction — still reconstructs and is still reviewable."""

    def test_readiness_codes_are_recorded_under_every_channel(self):
        """§AV3 adds ``brand_strings``, written on every reconstruction whether
        or not it has anything to say.

        AND THE EDIT SURFACED AN ASYMMETRY WORTH RECORDING RATHER THAN
        SILENTLY MATCHING. Eight of these nine channels are written
        unconditionally; ``content`` is not — it appears only when
        ``container_back_content_codes`` is non-empty, which is why it is
        absent from this set on a clean run. So the absence of ``content``
        here means either "the back copy is verified" or "the content check
        did not run", and nothing downstream can tell those apart. That is the
        §AV1 disease one level down, in the very category §AV1 was about.

        NOT REPAIRED HERE, and deliberately. Making ``content`` unconditional
        changes what a clean spec looks like for a check this tranche did not
        build and has not measured, and §AU8(f)'s discipline cuts both ways:
        one does not quietly adjust a neighbouring instrument while standing
        next to it. Reported as a finding; it belongs in its own ruling.

        §BH50(f)(2), 2026-09-16: that ruling came. ``content`` is written
        UNCONDITIONALLY from the placeholder record on every path, so the
        tenth channel is PRESENT and EMPTY on a clean run — the asymmetry
        this docstring reported is closed, and asserted below.
        """
        spec = self._reconstructed()
        assert set(spec["container_production_readiness_codes"]) == {
            "back_copy", "brand_strings", "colour_sources", "colour_usage", "content", "font", "front_copy",
            "material", "material_attribution", "production_method", "production_metrics",
            "quantitative_fidelity", "separations", "wrap_alignment"}
        assert spec["container_production_readiness_codes"]["content"] == []
        # §BH67's hard stop, "a finish or colour applied that nothing specified": the fourteenth channel, written on
        # every run, and its record says it READ the artefact, so an empty channel is never "the check did not run"
        # (the §AV1 disease). This fixture's brand holds no colour system and its concept names no type colour, so the
        # name prints in the composer's stand-in and the channel says so BY NAME — at acceptance; the reconstruction
        # stands (RECONSTRUCTED, no blocker — the test below)
        assert spec["container_printed_colours/1.0"]["state"] == "READ"
        assert spec["container_printed_colours/1.0"]["printed"]
        assert spec["container_production_readiness_codes"]["colour_sources"] == [
            "CONTAINER_COLOUR_UNSOURCED:#5A2C3A:product-name-hero-0"]
        # and EVERY section a real reconstruction writes is one the Gate-2 reader declares — 2645345 wrote
        # colour_sources undeclared, and every run read UNDECLARED_READINESS_SECTION: colour_sources until it was
        from apps.ire import container_production_readiness as cpr
        assert set(spec["container_production_readiness_codes"]) <= set(cpr._SECTIONS)
        refusal = cpr.gate2_refusal(spec)
        assert not any(str(c).startswith(cpr.UNDECLARED_READINESS_SECTION) for c in refusal["failures"])
        assert "CONTAINER_COLOUR_UNSOURCED:#5A2C3A:product-name-hero-0" in refusal["failures"]
        # §BH50(f)(7): the twelfth channel — the colour counter against every
        # place the artefact applies colour — PRESENT and EMPTY on a clean run,
        # its record RECONCILED with agree True; never absent and never None
        assert spec["container_production_readiness_codes"]["colour_usage"] == []
        _colour = spec["container_font_usage/1.0"]["colour_usage/1.0"]["reconciliation"]
        assert _colour["status"] == "RECONCILED" and _colour["agree"] is True
        # §BH50(f)(3): the eleventh channel, present on the generic path too — UNMEASURED there until §BH70(1), item 5
        # of the list the owner was sent: its front copy is measured ACROSS now against the confirmed zone's safe area,
        # this run's record persisted, and its height is UNMEASURED with its reason, so the channel still blocks
        from apps.pipeline.targets.container import GENERIC_FRONT_HEIGHT_UNMEASURED
        fit = spec["container_front_copy_fit/1.1"]
        assert fit["name_runs"] and all("width_mm" in r for r in fit["name_runs"]), fit["name_runs"]
        assert spec["container_production_readiness_codes"]["front_copy"] == fit["codes"]
        assert fit["codes"][-1] == ("CONTAINER_FRONT_COPY_FIT_UNMEASURED: vertical (%s)"
                                    % GENERIC_FRONT_HEIGHT_UNMEASURED["ruled"])
        # §BH54(b) (q): the thirteenth channel — the back copy's fit — present on the generic path too, and
        # UNMEASURED there: compose_container draws no true-scale back panel, so nothing measures its back copy
        # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] since every back carries the
        # full set, this brief's back is drawn at print size and measured: it stands, so the channel is present and empty
        assert spec["container_back_panel/1.0"]["fits"] is True
        assert spec["container_production_readiness_codes"]["back_copy"] == []
        assert spec["container_placeholder_copy/1.0"][
            "back_copy_composed_on_this_path"] is True                # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] composed, with the full set
        # the §AV3 channel is PRESENT and EMPTY on a clean run — the two facts
        # that a conditional write cannot express, asserted separately
        assert spec["container_production_readiness_codes"]["brand_strings"] == []
        assert spec["container_brand_strings/1.0"]["clean"] is True

    def test_an_unverified_technique_is_reported_and_does_not_block(self):
        spec = self._reconstructed()
        codes = spec["container_production_readiness_codes"]
        assert "CONTAINER_TECHNIQUE_UNVERIFIED" in codes["production_method"]
        # §BH26(a): the owner grant clears the font channel on the default
        # path, so the readiness/blocker separation is carried by the
        # technique code above — an empty font channel is the grant
        # measured, not a lost code.
        assert codes["font"] == []
        assert spec["container_production_method/1.0"][
            "all_manufacturer_verified"] is False
        assert spec["container_reconstruction"] == {
            "status": "RECONSTRUCTED", "blockers": []}

    def test_a_text_size_failure_is_readiness_and_not_a_blocker(self):
        """The same finding that makes ``below_size_floor`` True above is a
        production-readiness code here — it is advisory, and it must not
        become a reconstruction blocker by accident."""
        aria, out = self._at_the_profile_gate()
        self._repoint_front_zone(out, min_text_size_pt=12.0)
        spec = self._reconstructed(out, aria)
        assert "CONTAINER_MINIMUM_TEXT_SIZE_FAILED" in \
            spec["container_production_readiness_codes"]["production_method"]
        assert spec["container_reconstruction"]["blockers"] == []


@override_settings(OPENAI_API_KEY="")
class ConfirmedFontsReachTheProductionGateTests(ReconstructContainerCase):
    """P2-b — ``confirmed_fonts`` reaches ``build_font_authority`` from the one
    production call site (``targets/container/__init__.py`` :1217).

    Until this class that call was ``build_font_authority(doc)`` with no seam,
    so three of the five §2 gate codes were unreachable on the production path
    no matter what any owner confirmed. ``CONTAINER_FONT_LICENSE_REVIEW_
    REQUIRED`` was the sharpest case: it was asserted by NO test in the
    repository — not even negatively, unlike ``CONTAINER_FONT_MISSING`` and
    ``CONTAINER_FONT_IDENTITY_MISMATCH`` — and no caller could produce it.

    The confirmation below deliberately OMITS ``verification``, which is what a
    licence-pending confirmation actually looks like: the owner has named a
    face and its file and has NOT asserted a production right.
    ``_face_record`` defaults that to ``LICENCE_REVIEW_REQUIRED``, which is the
    honest state — and the one the gate had no way to reach.

    The font file is a TEMPORARY file, not a resolved system face. That is
    deliberate, and the reason CHANGED under it while the choice stayed right.

    This paragraph used to say that ``_regular_face()`` resolves to
    ``("NotoSans", None)`` in this tree — the file does not exist — so a fixture
    leaning on it would take the same silent ``return`` that
    ``test_confirmed_production_face_can_verify`` took at its line 84, and would
    assert nothing while reporting green. Both halves stopped being true at the
    §BH12(c)(1) naming fix. ``_regular_face()`` had been deriving the path from
    reportlab's REGISTRATION LABEL (``NotoSans``) as though it were a filename
    stem, and the regular face's file is ``NotoSans-Regular.ttf``; it now asks
    reportlab for the file it actually registered. That test's silent ``return``
    no longer fires and its body asserts for the first time.

    The tmp file is KEPT because the original reason survives its own premise:
    ``extract_identity`` sets ``file_present`` from ``os.path.exists`` alone and
    degrades its fontTools parse in a ``try/except``, so any real file exercises
    the confirmed path hermetically and on every platform — including one where
    the repo fonts are absent and the resolver falls to DejaVu or to Helvetica,
    which is a built-in with no file at all.
    """

    def _tmp_font(self) -> str:
        import os
        import tempfile
        fh = tempfile.NamedTemporaryFile(suffix=".ttf", delete=False)
        fh.write(b"\x00\x01\x00\x00 present-file-not-a-parseable-font")
        fh.close()
        self.addCleanup(os.unlink, fh.name)
        return fh.name

    def test_a_licence_pending_confirmation_reaches_the_readiness_record(self):
        aria, out = self._at_the_profile_gate()
        # `licence_id: "PENDING-OWNER-REVIEW"` was here and the §BH12(b) guard
        # refuses it: a claim in a licence field with no `licence_evidence`.
        # The guard refuses on the field's SHAPE, without reading the value —
        # code that could tell a placeholder from "OFL-1.1" would be reading
        # licences, which §BH12(a) reserves to the owner. Every assertion below
        # survives the deletion, because what makes this confirmation
        # licence-PENDING is the OMITTED `verification`, exactly as the class
        # docstring already says, and never this string.
        conf = {"name": "Owner Confirmed Face", "path": self._tmp_font()}
        reconstruct_container(aria, out, CONFIRMED,
                              confirmed_fonts={"regular": conf, "bold": conf})
        out.refresh_from_db()
        spec = out.spec_sheet
        codes = spec["container_production_readiness_codes"]["font"]
        # the code that no test in the repository could previously produce
        assert "CONTAINER_FONT_LICENSE_REVIEW_REQUIRED" in codes
        # and the confirmation genuinely displaced the placeholder, rather
        # than riding alongside it — which the two assertions after the source
        # are what actually measure, and they are unchanged
        # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] the faces it confirmed —
        # regular and bold; the back now printed with the full set sets its copy in the theme's own heading and body
        faces = [f for f in spec["container_font_authority/1.0"]["faces"] if f["role"] in ("regular", "bold")]
        assert faces
        # INVERTED per §BH16(a), the second of the two live assertions that
        # pinned the old default. This confirmation carries no `provenance` key,
        # and silence may no longer read as a human claim. It still DISPLACES the
        # placeholder; it just no longer says who chose it.
        assert all(f["source"] == "UNDECLARED" for f in faces)
        assert all(f["source"] != "USER_CONFIRMED" for f in faces)
        assert all(not f["is_fallback"] for f in faces)
        assert "CONTAINER_FONT_FALLBACK_DETECTED" not in codes
        assert "CONTAINER_FONT_CONFIRMATION_REQUIRED" not in codes

    def test_the_owner_grant_moves_the_default_production_result(self):
        """INVERTED at §BH26(a) — was
        ``test_the_seam_does_not_move_the_default_production_result``.

        That test's docstring premise — "An owner record that does not exist
        must read as UNKNOWN" — was overtaken the moment the §BH26 grant
        landed as repo data: the owner record now EXISTS
        (``apps/ire/container_font_owner_grant.py``, transcribed at §BH26 in
        OWNER_BLOCKER_CLEARANCE.md), and the default production result
        carries it. The SEAM is still inert when nothing is confirmed —
        ``confirmed_fonts`` is still omitted here and the machine-derived
        column beneath the grant is unchanged; what moves the record is the
        owner-grant CHANNEL at the call site, which is not the seam. Both
        faces resolve to the two sha256-named files, so the font gate clears
        entirely for this document — measured, not forced."""
        aria, out = self._at_the_profile_gate()
        reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        codes = out.spec_sheet["container_production_readiness_codes"]["font"]
        assert codes == []
        faces = out.spec_sheet["container_font_authority/1.0"]["faces"]
        assert faces and all(f["verification"] == "VERIFIED_FOR_PRODUCTION"
                             for f in faces)
        assert all(f["source"] == "USER_CONFIRMED" for f in faces)
        assert all(f["approved_by"] == "BBrose" for f in faces)
        assert all(f["is_fallback"] is False for f in faces)

    # ---- §BH26(b): the join producer goes live at the call site. The evidence
    # is a FIXTURE (the real artifact is untracked, git-ignored and absent in a
    # clean clone), keyed by the grant's own two sha256s — the files both roles
    # resolve to here — so these tests measure the WIRING, not the corpus.

    def _evidence_fixture(self, rows):
        import json
        import os
        import tempfile
        fh = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
        json.dump(rows, fh)
        fh.close()
        self.addCleanup(os.unlink, fh.name)
        return fh.name

    #: §BH48(a): the faces the emitter USES on the lifted surface — the theme's Poppins pair, by
    #: the catalogue's own sha256 (the §BH26 Noto pair is the Latin chains' last fallback now)
    def _joined_rows_for_both_faces(self):
        from apps.ire import font_roles as FR
        cat = FR.catalogue()
        return [{"machine": {"file_sha256": cat[stem]["sha256"], "postscript_name": "",
                             "face_id": f"fixture-face-{i}"}}
                for i, stem in enumerate(("Poppins-Light", "Poppins-Regular"))]

    def test_the_live_join_feeds_the_seam_beneath_the_grant(self):
        """§BH26(b): with no caller-supplied mapping the seam receives the
        join's yield for the faces the emitter uses — measured AT THE SEAM by
        spying on ``build_font_authority``'s argument — while the record the
        owner sees is unchanged, because the grant sits on top of it."""
        from pathlib import Path
        from unittest import mock
        from apps.ire import container_font_authority as cfa
        from apps.ire import container_font_evidence_join as cfj
        ev = self._evidence_fixture(self._joined_rows_for_both_faces())
        seen = {}
        real = cfa.build_font_authority

        def spy(doc, *, confirmed_fonts=None):
            seen["confirmed_fonts"] = confirmed_fonts
            return real(doc, confirmed_fonts=confirmed_fonts)

        aria, out = self._at_the_profile_gate()
        with mock.patch.object(cfj, "DEFAULT_EVIDENCE_PATH", Path(ev)), \
                mock.patch.object(cfa, "build_font_authority", spy):
            reconstruct_container(aria, out, CONFIRMED)
        conf = seen["confirmed_fonts"]
        # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] and the body the back's full set is set in
        assert set(conf) == {"regular", "bold", "body"}
        for c in conf.values():
            assert c["provenance"] == "MACHINE_DERIVED"
            assert c["verification"] == "LICENCE_REVIEW_REQUIRED"
            assert c["evidence_face_id"].startswith("fixture-face-")
        out.refresh_from_db()
        faces = out.spec_sheet["container_font_authority/1.0"]["faces"]
        assert faces and all(f["verification"] == "VERIFIED_FOR_PRODUCTION"
                             for f in faces)
        assert all(f["source"] == "USER_CONFIRMED" for f in faces)
        assert out.spec_sheet["container_production_readiness_codes"]["font"] \
            == []

    def test_beneath_a_void_grant_the_theme_faces_are_refused_and_the_record_says_so(self):
        """§BH48(a) re-pin of §BH26(b)'s proof. It pinned the live record to the join's
        MACHINE_DERIVED column beneath a void grant — true while the Noto pair drew on this
        surface without verifying. The surface is lifted: the theme's faces draw only when
        their record verifies (§BH32(e)), so a void grant REFUSES them — every candidate of the
        display and body chains tried and LICENCE_REVIEW_REQUIRED, the record's rows the
        placeholder column, and the gate asking for a confirmation. The join column no longer
        stands beneath a theme face; where the pair still draws (an untagged document) the
        companion below keeps §BH26(b)'s claim measured."""
        from pathlib import Path
        from unittest import mock
        from apps.ire import container_font_evidence_join as cfj
        from apps.ire import container_font_owner_grant as cfg
        ev = self._evidence_fixture(self._joined_rows_for_both_faces())
        aria, out = self._at_the_profile_gate()
        with mock.patch.object(cfj, "DEFAULT_EVIDENCE_PATH", Path(ev)), \
                mock.patch.object(cfg, "_measured_evidence_sha256",
                                  lambda grant: "0" * 64):
            reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        spec = out.spec_sheet
        faces = spec["container_font_authority/1.0"]["faces"]
        # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] the back now printed with the full set adds the
        # theme's heading and body, set in the same refused chains
        assert [f["role"] for f in faces] == ["bold", "heading", "regular", "body"]
        assert all(f["source"] == "PLACEHOLDER_FALLBACK" for f in faces)
        assert all(f["verification"] == "UNVERIFIED" for f in faces)
        assert all(f["is_fallback"] is True and f["file_identity"] == "" and f["sha256"] == "" for f in faces)
        codes = spec["container_production_readiness_codes"]["font"]
        assert "CONTAINER_FONT_CONFIRMATION_REQUIRED" in codes
        assert "CONTAINER_FONT_FALLBACK_DETECTED" in codes
        assert "CONTAINER_FONT_LICENSE_REVIEW_REQUIRED" not in codes
        refused = spec["container_font_usage/1.0"]["refused"]["roles"]
        # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] and the heading the back's
        # full set is headed in, refused as they are
        assert set(refused) == {"display", "body", "heading"}
        assert refused["heading"]["code"] == "FONT_ROLE_UNRESOLVED_NO_VERIFIED_FACE"
        for role, chain in (("display", ["Poppins-Light", "Poppins-Regular", "NotoSans-Bold"]),
                            ("body", ["Poppins-Regular", "NotoSans-Regular"])):
            assert refused[role]["code"] == "FONT_ROLE_UNRESOLVED_NO_VERIFIED_FACE"
            assert [t["stem"] for t in refused[role]["tried"]] == chain
            assert all(t["verification"] == "LICENCE_REVIEW_REQUIRED" for t in refused[role]["tried"])

    def test_beneath_a_void_grant_the_join_column_shows_through_where_the_pair_draws(self):
        """§BH48(a): the companion — §BH26(b)'s claim, kept where it is still true. An
        UNTAGGED document resolves as at 41604ac (the Noto pair, drawn without verifying);
        joined against evidence naming the pair, beneath a void §BH26 grant, the record's
        rows are the join's MACHINE_DERIVED column, capped at LICENCE_REVIEW_REQUIRED."""
        from pathlib import Path
        from unittest import mock
        from apps.ire import container_font_authority as cfa
        from apps.ire import container_font_evidence_join as cfj
        from apps.ire import container_font_owner_grant as cfg
        from apps.ire.font_roles import SURFACE_KEY
        from apps.pipeline.tests.test_container_font_authority import _doc
        doc = _doc()
        doc.metadata = {k: v for k, v in (doc.metadata or {}).items() if k != SURFACE_KEY}
        rows = [{"machine": {"file_sha256": sha, "postscript_name": "", "face_id": f"fixture-face-{i}"}}
                for i, sha in enumerate(cfg.OWNER_GRANT_BH26["face_sha256s"])]
        ev = self._evidence_fixture(rows)
        with mock.patch.object(cfj, "DEFAULT_EVIDENCE_PATH", Path(ev)):
            joined = cfj.join_document_fonts(doc)["confirmed_fonts"]
        assert set(joined) == {"regular", "bold"}
        bad = dict(cfg.OWNER_GRANT_BH26, licence_evidence_sha256="0" * 64)
        auth = cfg.apply_owner_grant(cfa.build_font_authority(doc, confirmed_fonts=joined), grant=bad)
        faces = auth["faces"]
        assert faces and all(f["source"] == "MACHINE_DERIVED" for f in faces)
        assert all(f["verification"] == "LICENCE_REVIEW_REQUIRED" for f in faces)
        assert all(f["is_fallback"] is True and f["licence_id"] == "" for f in faces)
        codes = cfa.font_confirmation_gate(auth)
        assert "CONTAINER_FONT_LICENSE_REVIEW_REQUIRED" in codes
        assert "CONTAINER_FONT_CONFIRMATION_REQUIRED" not in codes

    def test_absent_evidence_leaves_the_default_column_beneath_the_grant(self):
        """The control for the test above: with NO evidence (a clean clone) and
        the same void grant, the seam yields nothing and the DEFAULT column is
        what shows through — the placeholder, not a machine claim."""
        from pathlib import Path
        from unittest import mock
        from apps.ire import container_font_evidence_join as cfj
        from apps.ire import container_font_owner_grant as cfg
        aria, out = self._at_the_profile_gate()
        with mock.patch.object(cfj, "DEFAULT_EVIDENCE_PATH",
                               Path("/nonexistent/face_manifest.json")), \
                mock.patch.object(cfg, "_measured_evidence_sha256",
                                  lambda grant: "0" * 64):
            reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        faces = out.spec_sheet["container_font_authority/1.0"]["faces"]
        assert faces and all(f["source"] == "PLACEHOLDER_FALLBACK" for f in faces)
        assert all(f["is_fallback"] is True for f in faces)


class TheRecordCarriesTheArabicRowsDistinctTests(ReconstructContainerCase):
    """§BH33(4): the reconstruct contract pins the record's Arabic shape —
    arabic-display / arabic-heading / arabic-body as distinct rows, never a
    collapsed ``arabic`` row. The live container composition is EXEMPT
    (§BH32(h)(1)) and records exactly as at 41604ac; here the composer's
    document is re-tagged non-exempt, the way a surface adopts the theme, so
    the persisted record shows the ruled shape on the real reconstruct path."""

    _VOCABULARY = {"bold", "display", "heading", "regular", "body", "caption",
                   "script-accent", "arabic-display", "arabic-heading", "arabic-body"}

    def test_a_reconstructed_arabic_named_product_persists_the_distinct_rows(self):
        from unittest import mock

        import apps.ire.compose_container as CC
        from apps.ire.font_roles import NON_EXEMPT_EXERCISE, SURFACE_KEY
        real = CC.compose_container_graph

        def adopted(*a, **k):
            doc = real(*a, **k)
            doc.metadata = dict(doc.metadata, **{SURFACE_KEY: NON_EXEMPT_EXERCISE})
            return doc

        aria, out = self._at_the_profile_gate()
        spec = out.spec_sheet
        spec["product_name"] = "رحيق الورد"
        out.spec_sheet = spec
        out.save()
        with mock.patch.object(CC, "compose_container_graph", adopted):
            reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        faces = out.spec_sheet["container_font_authority/1.0"]["faces"]
        roles = [f["role"] for f in faces]
        assert "arabic-display" in roles and "arabic" not in roles
        assert set(roles) <= self._VOCABULARY
        for f in faces:
            if f["role"].startswith("arabic-"):
                assert f["postscript_name"] == "NotoNaskhArabic-Regular"
                assert f["verification"] == "VERIFIED_FOR_PRODUCTION"
        # the usage counter on the same artefact reconciles: Naskh drew the Arabic name
        usage = out.spec_sheet["container_font_usage/1.0"]
        assert usage["reconciliation"]["agree"] is True
        assert "NotoNaskhArabic-Regular" in usage["reconciliation"]["embedded"]

    def test_the_live_composition_records_the_theme_roles(self):
        """§BH48(a) re-pin: this proof pinned the live composition to 41604ac's collapsed
        `arabic` row; the surface is lifted, so the production record carries the layer's
        role for the Arabic name — arabic-display — beside the theme's Latin roles."""
        aria, out = self._at_the_profile_gate()
        spec = out.spec_sheet
        spec["product_name"] = "رحيق الورد"
        out.spec_sheet = spec
        out.save()
        reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        roles = [f["role"] for f in out.spec_sheet["container_font_authority/1.0"]["faces"]]
        # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] the back's heading and body beside them, the back
        # now printed with the full set
        assert roles == ["bold", "heading", "regular", "body", "arabic-display"]


@override_settings(OPENAI_API_KEY="")
class TheDisplayWordmarkReachesTheFaceTests(ReconstructContainerCase):
    """§BH67(b)2 through the production path: "THE DISPLAY WORDMARK IS LOST … Find where it drops." A face form whose
    concept sets its display name as the record's own leading phrase prints that phrase on the lid — the record's
    words, never a name it does not hold — and the spec says where each attribute of the wordmark went: the text, the
    face, the size."""

    def setUp(self):
        super().setUp()
        self.product.name, self.product.name_ar = "Focus Pressed Powder", "فوكس بودرة مضغوطة"
        self.product.product_type = "pressed powder compact"
        self.product.save(update_fields=["name", "name_ar", "product_type"])
        self.task.task_text = "a pressed powder compact"
        self.task.save(update_fields=["task_text"])

    def test_the_lid_prints_the_concepts_display_name_in_the_records_words_and_says_where_it_drops(self):
        from apps.ire import display_name as DN
        from apps.pipeline.models import Gate1RegenerationJob
        image = self._image(prompt="p", motif="five rounded petals in a ring inside an oval window", vid="A_FOCUS")
        job = Gate1RegenerationJob.objects.get(task=self.task)
        payload = job.prompts_payload
        payload["variations"][0]["typography_signature"] = (
            "High-contrast old-style Latin serif ('Focus') over matching Naskh ('فوكس'), set above the window")
        job.prompts_payload = payload
        job.save(update_fields=["prompts_payload"])
        from unittest import mock
        aria, out = self._at_the_profile_gate(image)
        # §BH67(d)1 reads a face form's concept through a provider; none is called here — the read FAILS by name
        with mock.patch("apps.pipeline.services.claude_service.call_claude",
                        side_effect=RuntimeError("no provider in this test")):
            reconstruct_container(aria, out, {"archetype": "compact", "variant": "rounded_rect", "height_mm": 95,
                                              "width_mm": 110})
        out.refresh_from_db()
        assert out.spec_sheet["container_concept_layout/1.0"]["state"] == "FAILED"     # reported, never silent
        record = out.spec_sheet[DN.SCHEMA]
        assert (record["name"]["source"], record["name"]["text"]) == (DN.DISPLAY, "Focus")
        assert (record["name_ar"]["source"], record["name_ar"]["text"]) == (DN.DISPLAY, "فوكس")
        assert [o["text"] for o in record["off_the_face"]] == ["Pressed Powder", "بودرة مضغوطة"]
        drops = {d["attribute"]: d for d in record["drops"]}
        # §BH68(b): the size is the scale's step the lid holds for the concept's layout, no longer the tier's
        assert (drops["text"]["state"], drops["face"]["state"], drops["size"]["state"]) == (
            "CONCEPT", "ROLE_LAYER", "SCALE_STEP")
        assert drops["face"]["drawn"] and isinstance(drops["size"]["drawn"], float)
        # the drawn file itself, run by run: the lid's name is the display name as live text, and the whole record
        # name no longer prints there (the sheet's own title, an annotation above the drawing, keeps it in capitals)
        runs = [s["text"].strip() for b in fitz.open(out.design_preview_ai.path)[0].get_text("dict")["blocks"]
                for line in b.get("lines", []) for s in line.get("spans", []) if s["text"].strip()]
        assert "Focus" in runs and "Focus Pressed Powder" not in runs

    def test_bh70_the_lids_front_copy_is_measured_across_and_what_is_not_says_why(self):
        """§BH70(1), item 5 of the list the owner was sent: a compact's front copy carried one code, "no fit instrument
        on this path". Its lid is laid into the zone the person confirmed, at true size, so its name is measured across
        against that zone's safe area; its Arabic line, which no instrument reads, and the height of the block are each
        named UNMEASURED with its reason — the channel still blocks acceptance and never reads as passed."""
        from unittest import mock

        from apps.pipeline.targets.container import GENERIC_FRONT_HEIGHT_UNMEASURED
        image = self._image(prompt="p", motif="five rounded petals in a ring inside an oval window", vid="A_FOCUS")
        aria, out = self._at_the_profile_gate(image)
        with mock.patch("apps.pipeline.services.claude_service.call_claude",
                        side_effect=RuntimeError("no provider in this test")):
            reconstruct_container(aria, out, {"archetype": "compact", "variant": "rounded_rect", "height_mm": 95,
                                              "width_mm": 110})
        out.refresh_from_db()
        fit = out.spec_sheet["container_front_copy_fit/1.1"]
        assert " ".join(r["text"] for r in fit["name_runs"]) == "Focus Pressed Powder"     # every line of the name
        assert all(r["state"] == "HELD" and r["width_mm"] < r["safe_area_mm"] for r in fit["name_runs"]), fit["name_runs"]
        codes = out.spec_sheet["container_production_readiness_codes"]["front_copy"]
        assert codes == fit["codes"]
        assert "CONTAINER_FRONT_COPY_FIT_UNMEASURED: vertical (%s)" % GENERIC_FRONT_HEIGHT_UNMEASURED["face"] in codes
        assert [r["name"] for r in fit["not_read"]] == ["product-name-ar"], fit["not_read"]
        assert "CONTAINER_FRONT_COPY_FIT_UNMEASURED: product-name-ar (no instrument reads this line on this path)" in codes


@override_settings(OPENAI_API_KEY="")
class EveryPrintedColourHasARecordTests(ReconstructContainerCase):
    """§BH67 HARD STOP, OWNER RULED 2026-09-24: "a finish or colour applied that nothing specified". Every colour the
    container composer prints comes from a record — the concept's words, a measurement of its image, or the brand
    swatch whose usage the brand wrote for the job — and one no record names is a NAMED ACCEPTANCE blocker, never
    silence. Measured on task 91's lid: the name printed in #5A2C3A, a constant no record names."""

    def _house_palette(self):
        from apps.core.models import STATUS_CANONICAL, ColorSystem
        ColorSystem.objects.create(brand=self.brand, name="Blush Core", system_id="CS-001", status=STATUS_CANONICAL,
                                   palette=[{"role": "Primary", "name": "Blush", "hex": "#F2C4CE",
                                             "usage": "Main surfaces, hero cartons"},
                                            {"role": "Accent", "name": "Deep Rose", "hex": "#8B3A52",
                                             "usage": "Typography, fine detail lines"}])

    def test_the_brands_typography_swatch_sources_the_type_and_the_record_is_clean(self):
        self._house_palette()
        spec = self._reconstructed()
        record = spec["container_printed_colours/1.0"]
        assert spec["container_colour_sources/1.0"]["colors"]["ink"] == "#8B3A52"
        assert "Typography" in spec["container_colour_sources/1.0"]["sources"]["ink"]
        assert "#8B3A52" in record["printed"] and record["codes"] == []
        assert spec["container_production_readiness_codes"]["colour_sources"] == []

    def test_a_type_no_record_names_blocks_acceptance_by_name_and_the_evidence_stands(self):
        spec = self._reconstructed()          # this brand keeps no colour record and the concept names no colour
        codes = spec["container_production_readiness_codes"]["colour_sources"]
        assert any(c.startswith("CONTAINER_COLOUR_UNSOURCED:#5A2C3A:") for c in codes), codes
        assert spec["container_printed_colours/1.0"]["codes"] == codes
        assert spec["container_reconstruction"]["status"] == "RECONSTRUCTED"     # for the reviewer to see


class TheFaceIsReadFromItsConceptTests(ReconstructContainerCase):
    """§BH67(d)1 through the production path: a FACE form's approved concept is read as structure by the vision step
    — once, its cost on the task's ledger, its record on the spec — and a re-confirmed profile reads the record, never
    the model again. No provider is called: the vision answer is stood in for at the one call the service makes."""

    def setUp(self):
        super().setUp()
        self.product.product_type = "pressed powder compact"
        self.product.save(update_fields=["product_type"])
        self.task.task_text = "a pressed powder compact"
        self.task.save(update_fields=["task_text"])

    def test_the_approved_concept_is_read_once_and_recorded_on_the_spec(self):
        import json
        from types import SimpleNamespace
        from unittest import mock
        from apps.pipeline.services import concept_layout as L
        answer = {"surface": "LID_TOP", "surface_box": [0.1, 0.2, 0.9, 0.8], "surface_shape": "round",
                  "elements": [{"kind": "name", "box": [0.3, 0.2, 0.7, 0.3], "align": "centre", "seen_text": "Rose",
                                "confidence": 0.9}], "unread": [], "notes": ""}
        response = SimpleNamespace(usage=SimpleNamespace(input_tokens=2000, output_tokens=500),
                                   content=[SimpleNamespace(type="text", text=json.dumps(answer))])
        compact = {"archetype": "compact", "variant": "rounded_rect", "height_mm": 95, "width_mm": 110}
        aria, out = self._at_the_profile_gate()
        with mock.patch("apps.pipeline.services.claude_service.call_claude", return_value=response) as call:
            reconstruct_container(aria, out, compact)
            out.refresh_from_db()
            record = out.spec_sheet[L.SPEC_KEY]
            assert record["state"] == L.READ and record["surface"] == "LID_TOP"
            assert [e["kind"] for e in record["elements"]] == ["name"]
            assert record["image"]["sha256"] and record["cost"]["calls"] == 1
            assert call.call_count == 1 and call.call_args.kwargs["operation"] == L.OPERATION
            # a re-confirmed profile reads the record, not the model
            reconstruct_container(aria, out, compact)
            assert call.call_count == 1

    def test_bh67d2_the_face_is_drawn_from_the_read_and_measured_against_it(self):
        """§BH67(d)2 and (e) through the production path: with the concept read, the face is drawn from the read — the
        follow record on the face says which elements followed and every move by name — and the layout measure is
        written beside it, a number per element, the drawn file against the concept."""
        import json
        from types import SimpleNamespace
        from unittest import mock
        from apps.pipeline.services import concept_layout as L
        answer = {"surface": "LID_TOP", "surface_box": [0.1, 0.2, 0.9, 0.8], "surface_shape": "round",
                  "elements": [{"kind": "mark", "box": [0.35, 0.06, 0.65, 0.14], "align": "centre"},
                               {"kind": "name", "box": [0.3, 0.2, 0.7, 0.3], "align": "centre",
                                "seen_text": "Rose"},
                               {"kind": "window", "box": [0.3, 0.4, 0.7, 0.85], "align": "centre", "shape": "oval"},
                               {"kind": "motif", "box": [0.35, 0.45, 0.65, 0.8], "align": "centre"}],
                  "unread": [], "notes": ""}
        response = SimpleNamespace(usage=SimpleNamespace(input_tokens=2000, output_tokens=500),
                                   content=[SimpleNamespace(type="text", text=json.dumps(answer))])
        compact = {"archetype": "compact", "variant": "rounded_rect", "height_mm": 95, "width_mm": 110}
        aria, out = self._at_the_profile_gate(self._image(
            prompt="p", motif="seven slender teardrop petals in a fan inside an oval window"))
        with mock.patch("apps.pipeline.services.claude_service.call_claude", return_value=response):
            reconstruct_container(aria, out, compact)
        out.refresh_from_db()
        spec = out.spec_sheet
        assert spec[L.SPEC_KEY]["state"] == L.READ
        measure = spec[L.MEASURE_SCHEMA]
        rows = {r["element"]: r for r in measure["rows"]}
        assert rows["name"]["state"] == "MEASURED" and isinstance(rows["name"]["distance"], float)
        assert rows["window"]["state"] == "MEASURED"
        assert rows["motif"]["state"] == "MEASURED"          # its own drawn leaves, inside its window
        assert measure["governed_by"] == "§BH67(e)" and measure["surface_mm"]


def _rows_digest():
    """sha256 of every model's rows in primary-key order, the sessions table apart — what "nothing written" is measured
    against."""
    import hashlib
    import json

    from django.apps import apps as _apps
    from django.db import DatabaseError, transaction
    digest = {}
    for model in _apps.get_models():
        if model._meta.label == "sessions.Session":
            continue
        try:
            with transaction.atomic():
                rows = list(model.objects.order_by("pk").values())
        except DatabaseError:
            continue
        digest[model._meta.label] = hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()
    return digest


class FaceFormCase(ReconstructContainerCase):
    """Task 110 in a test database: a compact whose product record carries its size (110 x 95 x 18 mm, as task 110's
    does, so begin_output proposes the whole lid as its zone) and its Arabic name, whose selected variation carries task
    110's own concept words (a hairline rule in Rose Gold foil, a rim ring, a radial motif —
    `apps/ire/tests/test_au3_divider_gates.py` `_T110_CONCEPT`), reconstructed once on the governed path with the vision
    read stood in for by task 110's own reading (`_T110_VISION`), so that reading is cached on the sheet exactly as
    production caches it. It is confirmed with the record's own profile, as the retry door hands it on
    (`exploration_render.confirmed_profile`). No provider is called."""

    #: the concept picture's side in pixels — large enough that its reading's boxes survive the service's 0.1 px grid
    CONCEPT_PX = 1000

    def setUp(self):
        super().setUp()
        self.product.name, self.product.name_ar = "Focus Pressed Powder", "فوكس بودرة مضغوطة"
        self.product.product_type = "pressed powder compact"
        self.product.width_mm, self.product.height_mm, self.product.depth_mm = 110, 95, 18
        self.product.save(update_fields=["name", "name_ar", "product_type", "width_mm", "height_mm", "depth_mm"])
        self.task.task_text = "a pressed powder compact"
        self.task.save(update_fields=["task_text"])

    @classmethod
    def _concept_png(cls) -> bytes:
        from io import BytesIO

        from PIL import Image
        buf = BytesIO()
        Image.new("RGB", (cls.CONCEPT_PX, cls.CONCEPT_PX), (250, 243, 236)).save(buf, format="PNG")
        return buf.getvalue()

    @staticmethod
    def _read_answer():
        """The vision step's answer — task 110's own reading, its fractions of the lid put back into pixels of the
        fixture's concept — stood in for at the one call the service makes."""
        import json
        from types import SimpleNamespace

        from apps.ire.tests.test_au3_divider_gates import _T110_VISION
        x0, y0, side = 100.0, 100.0, 800.0

        def px(box):
            return [round(x0 + box[0] * side, 1), round(y0 + box[1] * side, 1),
                    round(x0 + box[2] * side, 1), round(y0 + box[3] * side, 1)]
        answer = {"surface": "LID_TOP", "surface_box": [x0, y0, x0 + side, y0 + side], "surface_shape": "round",
                  "elements": [dict(e, box=px(e["box"])) for e in _T110_VISION["elements"]],
                  "unread": [], "notes": ""}
        return SimpleNamespace(usage=SimpleNamespace(input_tokens=2000, output_tokens=500),
                               content=[SimpleNamespace(type="text", text=json.dumps(answer))])

    def _face(self, *, read=True):
        from unittest import mock

        from apps.ire.tests.test_au3_divider_gates import _T110_CONCEPT
        image = self._image(prompt="p", motif=_T110_CONCEPT["motif_signature"], vid="A_RADIANT_AXIS")
        image.image_file.save("concept.png", ContentFile(self._concept_png()), save=True)
        job = Gate1RegenerationJob.objects.get(task=self.task)
        payload = job.prompts_payload
        payload["variations"][0].update({k: v for k, v in _T110_CONCEPT.items() if k.endswith("_signature")})
        job.prompts_payload = payload
        job.save(update_fields=["prompts_payload"])
        aria, out = self._at_the_profile_gate(image)
        from apps.dashboard.exploration_render import confirmed_profile
        self.confirmed = confirmed_profile(out.spec_sheet)
        if read:
            with mock.patch("apps.pipeline.services.claude_service.call_claude", return_value=self._read_answer()):
                reconstruct_container(aria, out, self.confirmed)
            out.refresh_from_db()
        return aria, out


@override_settings(OPENAI_API_KEY="")
class TheLidIsTracedFromItsConceptTests(FaceFormCase):
    """§BH71 PART 1, the owner's goal of 2026-09-28: \"Take the drawn outline and proportions from the chosen concept
    picture itself (read and traced to a clean vector). Templates are only a fallback, and the design says when the
    fallback was used.\" Task 110's fixture, its concept a round lid seen tilted: the shape step is proposed the
    traced lid, and confirmed so it is drawn as the clean circle the picture shows, the drawing saying so."""

    @classmethod
    def _concept_png(cls) -> bytes:
        from apps.pipeline.tests.test_vqr2b_concept_analysis import _lid_png
        return _lid_png((380, 330), 20.0, size=(cls.CONCEPT_PX, cls.CONCEPT_PX))

    def test_the_shape_step_is_proposed_the_traced_lid(self):
        from apps.pipeline.services import concept_outline as co
        image = self._image(prompt="p")
        image.image_file.save("concept.png", ContentFile(self._concept_png()), save=True)
        _aria, out = self._at_the_profile_gate(image)
        record = out.spec_sheet[cc.PROFILE_SCHEMA]
        assert record["variant"] == "round" and record["fields"]["variant"]["source"] == cc.SRC_INFERRED
        assert record["fields"]["body_height_mm"]["value"] == record["fields"]["body_width_mm"]["value"] == 110.0
        trace = out.spec_sheet[co.SCHEMA]
        assert trace["state"] == co.TRACED_FROM_CONCEPT and trace["kind"] == co.ROUND
        # the product record's 95 mm is replaced in the PROPOSAL only, and said by value and source
        assert trace["proposal"]["replaced"] == {"body_height_mm": {"was": 95.0, "source": cc.SRC_PRODUCT_RECORD}}

    def test_the_confirmed_round_lid_is_drawn_from_its_trace_and_the_drawing_says_so(self):
        from apps.pipeline.services import concept_outline as co
        from apps.pipeline.targets.container import OUTLINE_SOURCE_KEY
        _aria, out = self._face()
        assert self.confirmed["variant"] == "round" and self.confirmed["height_mm"] == self.confirmed["width_mm"]
        source = out.spec_sheet[OUTLINE_SOURCE_KEY]
        assert source["source"] == co.TRACED_FROM_CONCEPT and source["kind"] == co.ROUND, source
        rows = {r["label"]: r["value"] for r in ProductContainerTarget().review_sections(self.task)}
        assert rows["Drawn outline"].startswith("traced from the concept — a round lid"), rows.get("Drawn outline")
        # the concept's ring runs round the lid as the concept draws it — on the lid's own round outline, no substitute
        from apps.dashboard.exploration_render import _reading_on_record
        from apps.pipeline.targets.container import draw_face_form, face_form_inputs
        doc, _finish = draw_face_form(face_form_inputs(self.task, out, self.confirmed, read_layout=_reading_on_record))
        ring = doc.metadata["concept_front"]["face"]["ring_shape"]
        assert (ring["drawn_shape"], ring["state"]) == ("round", "THE_LID_OUTLINE"), ring
        # [§BH71 PART 1: and the face is cut to the lid's circle, never to the square its zone is — nothing it lays out
        # leaves the circle less its safe margin, and the containment report reads it]
        cut = [n.clip for n, _ in doc.walk() if getattr(n, "type", "") == "group"
               and n.name in ("FRONT_CONCEPT", "FRONT_DIRECT_PRINT")]
        assert cut and all([type(s).__name__ for s in clip].count("CubicTo") == 4 for clip in cut), cut
        assert doc.metadata["concept_front"]["face"]["round_lid"]["outside"] == []
        assert out.spec_sheet["container_zone_containment_report"]["contained"] is True

    def test_his_answer_a_part_inside_the_margin_as_pictured_is_drawn_and_noted_beside_approve(self):
        """His answer on the print area's safe margin (2026-10-01, transcribed at f23b9e8): "The picture (Recommended)".
        Where the zone check finds a part inside the margin where the concept picture prints it, the design is drawn —
        the note never refuses it — and the note is kept with the containment report and read by the verdict as a
        production note beside Approve, never among what blocks."""
        from unittest import mock

        from apps.ire.container_production_readiness import build_readiness
        from apps.pipeline.services import container_projection as cp
        real = cp.validate_zone_containment
        note = "%s: band sits inside the 3.0mm safe margin of zone z_front, where the concept picture prints it" % (
            cp.ZONE_SAFE_MARGIN_AS_PICTURED)
        with mock.patch.object(cp, "validate_zone_containment", lambda *a, **k: real(*a, **k) + [note]):
            _aria, out = self._face()
        spec = out.spec_sheet
        assert spec["container_reconstruction"] == {"status": "RECONSTRUCTED", "blockers": []}, (
            spec["container_reconstruction"])
        report = spec["container_zone_containment_report"]
        assert report["contained"] is True and report["production_notes"] == [note], report
        verdict = build_readiness(spec)
        assert note in verdict["production_notes"] and note not in verdict["blocking_codes"]
        assert spec["container_production_readiness_codes"]["production_metrics"][-1] == note


@override_settings(OPENAI_API_KEY="")
class TheLearnedOvalLidIsDrawnTests(FaceFormCase):
    """§BH71 PART 3, the owner's goal of 2026-09-28: "When a concept shows a shape the system doesn't know, it says so
    and offers to learn it." Task 110's fixture, its brief "an oval pressed powder compact" and its concept an oval lid
    seen square-on: the shape step says the oval and proposes no shape; learned, the design is proposed the learned
    oval, confirmed, and drawn from its trace — its outline the ellipse, its face cut to it and nothing laid out leaving
    it, the drawing saying which drew."""

    def setUp(self):
        super().setUp()
        self.task.task_text = "an oval pressed powder compact"
        self.task.save(update_fields=["task_text"])

    @classmethod
    def _concept_png(cls) -> bytes:
        from apps.pipeline.tests.test_vqr2b_concept_analysis import _lid_png
        return _lid_png((380, 260), 0.0, size=(cls.CONCEPT_PX, cls.CONCEPT_PX))

    def test_the_oval_is_said_learned_and_drawn_from_its_trace(self):
        from unittest import mock

        from django.contrib.auth.models import User

        from apps.dashboard.exploration_render import _reading_on_record, confirmed_profile
        from apps.ire.tests.test_au3_divider_gates import _T110_CONCEPT
        from apps.pipeline.services import concept_outline as co
        from apps.pipeline.services import learned_shapes as ls
        from apps.pipeline.targets.container import OUTLINE_SOURCE_KEY, draw_face_form, face_form_inputs
        image = self._image(prompt="p", motif=_T110_CONCEPT["motif_signature"], vid="A_RADIANT_AXIS")
        image.image_file.save("concept.png", ContentFile(self._concept_png()), save=True)
        job = Gate1RegenerationJob.objects.get(task=self.task)
        payload = job.prompts_payload
        payload["variations"][0].update({k: v for k, v in _T110_CONCEPT.items() if k.endswith("_signature")})
        job.prompts_payload = payload
        job.save(update_fields=["prompts_payload"])
        aria, out = self._at_the_profile_gate(image)
        record, trace = out.spec_sheet[cc.PROFILE_SCHEMA], out.spec_sheet[co.SCHEMA]
        assert record["variant"] == "" and record["unknown_shape"]["source"] == ls.FROM_THE_CONCEPT, record
        assert (trace["kind"], trace["named_by"]) == (co.OVAL, "the brief's words"), trace
        row, created = ls.learn(self.task, User.objects.create_user("owner"))
        assert created and row.kind == "oval"
        out.refresh_from_db()
        confirmed = confirmed_profile(out.spec_sheet)
        assert confirmed["variant"] == "learned_oval" and confirmed["height_mm"] < confirmed["width_mm"], confirmed
        with mock.patch("apps.pipeline.services.claude_service.call_claude", return_value=self._read_answer()):
            reconstruct_container(aria, out, confirmed)
        out.refresh_from_db()
        source = out.spec_sheet[OUTLINE_SOURCE_KEY]
        assert source["source"] == co.TRACED_FROM_CONCEPT and source["kind"] == co.OVAL, source
        doc, _finish = draw_face_form(face_form_inputs(self.task, out, confirmed, read_layout=_reading_on_record))
        cut = [n.clip for n, _ in doc.walk() if getattr(n, "type", "") == "group"
               and n.name in ("FRONT_CONCEPT", "FRONT_DIRECT_PRINT")]
        assert cut and all([type(s).__name__ for s in clip].count("CubicTo") == 4 for clip in cut), cut
        assert doc.metadata["concept_front"]["face"]["oval_lid"]["outside"] == []
        assert out.spec_sheet["container_zone_containment_report"]["contained"] is True


@override_settings(OPENAI_API_KEY="")
class TheLidDrawsTheRecordsShadeTests(FaceFormCase):
    """His answer of 2026-09-29 to the §BH71 report, (4): "the lid drawing draws the shade name my brief asks for".
    Task 110's fixture with the record's one shade, "Natural" and its Arabic: the lid draws them side by side where
    the concept sets its own shade line (task 110's reading: "02 BEIGE | PRESSED POWDER", read descriptor, at its
    foot), the words the record's and never the picture's, measured as front copy and kept inside the lid; a record
    with no shade draws none."""

    def _drawn(self):
        from apps.dashboard.exploration_render import _reading_on_record
        from apps.pipeline.targets.container import draw_face_form, face_form_inputs
        _aria, out = self._face()
        doc, _finish = draw_face_form(face_form_inputs(self.task, out, self.confirmed, read_layout=_reading_on_record))
        return out, doc, {n.name: n for n, _ in doc.walk() if getattr(n, "type", "") == "text"}

    def test_the_records_shade_is_drawn_where_the_concepts_line_is_and_never_its_words(self):
        from apps.core.models import AR_UNCONFIRMED
        self.product.shade_names = [{"en": "Natural", "ar": "طبيعي", "ar_source": AR_UNCONFIRMED}]
        self.product.save(update_fields=["shade_names"])
        out, doc, runs = self._drawn()
        assert (runs["product-shade"].text, runs["product-shade-ar"].text) == ("Natural", "طبيعي"), sorted(runs)
        assert not any("BEIGE" in (r.text or "") for r in runs.values()), sorted(runs)    # the concept's "02 BEIGE"
        face = doc.metadata["concept_front"]["face"]
        shade = face["shade"]
        assert shade["place"] == "the concept's own shade line" and shade["ar_unconfirmed"] is True, shade
        assert "shade" in {f["element"] for f in face["concept_layout"]["followed"]}, face["concept_layout"]
        zx, zy, zw, zh = face["concept_layout"]["surface_mm"]
        name_ar_y = runs["product-name-ar"].y
        assert name_ar_y < runs["product-shade"].y and (runs["product-shade"].y - zy) / zh > 0.8, (name_ar_y, zy, zh)
        assert "product-shade" in face["drawn"]
        fit = out.spec_sheet["container_front_copy_fit/1.1"]
        assert "product-shade" in {r["name"] for r in fit["runs"]}, fit["runs"]        # measured as front copy
        assert out.spec_sheet["container_zone_containment_report"]["contained"] is True

    def test_its_arabic_written_by_the_executor_is_marked_beside_approve_and_a_confirmed_one_is_not(self):
        """The production run writes the mark off the lid it drew: an Arabic the record marks the executor's is
        CONTAINER_SHADE_ARABIC_UNCONFIRMED in the content section — a warning beside Approve — and a row with no such
        mark writes nothing."""
        from apps.core.models import AR_UNCONFIRMED
        from apps.pipeline.targets.container import SHADE_ARABIC_UNCONFIRMED
        self.product.shade_names = [{"en": "Natural", "ar": "طبيعي", "ar_source": AR_UNCONFIRMED}]
        self.product.save(update_fields=["shade_names"])
        _aria, out = self._face()
        content = out.spec_sheet["container_production_readiness_codes"]["content"]
        assert [c for c in content if c.startswith(SHADE_ARABIC_UNCONFIRMED)], content

    def test_a_shade_whose_arabic_is_not_marked_writes_no_mark(self):
        from apps.pipeline.targets.container import SHADE_ARABIC_UNCONFIRMED
        self.product.shade_names = [{"en": "Natural", "ar": "طبيعي"}]
        self.product.save(update_fields=["shade_names"])
        _aria, out = self._face()
        content = out.spec_sheet["container_production_readiness_codes"]["content"]
        assert not [c for c in content if c.startswith(SHADE_ARABIC_UNCONFIRMED)], content

    def test_a_record_with_no_shade_draws_none(self):
        _out, doc, runs = self._drawn()
        assert not {"product-shade", "product-shade-ar"} & set(runs), sorted(runs)
        assert "shade" not in doc.metadata["concept_front"]["face"]


def _never_dispatched(*_args):
    raise AssertionError("a refused re-confirmation dispatched the worker's job")


@override_settings(OPENAI_API_KEY="")
class AWaitingDesignsShapeIsConfirmedAgainTests(FaceFormCase):
    """His answer of 2026-09-29 to the §BH71 report, (3): "Yes, redraw 91 and 89 on their records". The confirm endpoint
    keeps a confirmation immutable, so task 110's fixture — confirmed through it as its record's rounded rectangle and
    drawn, waiting at its review — has its shape confirmed again as the round lid its concept shows: the confirmation it
    had kept whole in its history, the new one said as the executor's on his word and never his, its zones the round
    lid's own proposal, its gate decision with no user, and the design drawn again by the worker's own job; anything
    else is refused by name, with nothing written."""

    WORD = "his answer of 2026-09-29 to the §BH71 report, (3)"

    def _at_its_review(self):
        from unittest import mock

        from django.contrib.auth.models import Group, User
        from django.test import Client

        from apps.dashboard.exploration_render import confirmed_profile
        from apps.ire.tests.test_au3_divider_gates import _T110_CONCEPT
        from apps.pipeline.permissions import ROLE_REVIEWER
        image = self._image(prompt="p", motif=_T110_CONCEPT["motif_signature"], vid="A_RADIANT_AXIS")
        image.image_file.save("concept.png", ContentFile(self._concept_png()), save=True)
        job = Gate1RegenerationJob.objects.get(task=self.task)
        payload = job.prompts_payload
        payload["variations"][0].update({k: v for k, v in _T110_CONCEPT.items() if k.endswith("_signature")})
        job.prompts_payload = payload
        job.save(update_fields=["prompts_payload"])
        _aria, out = self._at_the_profile_gate(image)
        reviewer = User.objects.create_superuser("reviewer", password="x")
        Group.objects.get_or_create(name=ROLE_REVIEWER)[0].user_set.add(reviewer)
        client = Client(HTTP_HOST="127.0.0.1")
        client.force_login(reviewer)
        profile = dict(confirmed_profile(out.spec_sheet), variant="rounded_rect")
        zones = [dict(z, user_confirmation_state=cc.ZONE_USER_CONFIRMED)
                 for z in out.spec_sheet[cc.ZONES_SCHEMA]["zones"]]
        with mock.patch("apps.pipeline.services.claude_service.call_claude", return_value=self._read_answer()), \
                self.captureOnCommitCallbacks(execute=True):
            answer = client.post(f"/api/tasks/{self.task.id}/confirm_container_profile/",
                                 {"profile": profile, "zones": zones}, content_type="application/json")
        assert answer.status_code == 200, answer.content
        self.task.refresh_from_db()
        out.refresh_from_db()
        assert self.task.status == "awaiting_gate_2", self.task.status
        return out

    def test_its_shape_is_confirmed_again_the_old_confirmation_kept_and_it_is_drawn_again(self):
        from apps.pipeline.models import GateDecision
        from apps.pipeline.services import shape_reconfirmation as sr
        out = self._at_its_review()
        before = dict(out.spec_sheet["container_confirmation"])
        was = out.spec_sheet[cc.PROFILE_SCHEMA]["variant"]
        done = sr.reconfirm(self.task, variant="round", by="the executor", on_word_of=self.WORD)
        self.task.refresh_from_db()
        out.refresh_from_db()
        spec = out.spec_sheet
        (kept,) = spec[sr.HISTORY_KEY]
        assert (kept["confirmation"], kept["profile"]["variant"], kept["on_word_of"]) == (before, was, self.WORD)
        record = spec[cc.PROFILE_SCHEMA]
        assert (record["variant"], record["confirmed_by"]) == ("round", "the executor"), record
        fields = record["fields"]
        assert fields["body_height_mm"]["value"] == fields["body_width_mm"]["value"] == 110, fields
        confirmation = spec["container_confirmation"]
        assert (confirmation["confirmed_by"], confirmation["on_word_of"], confirmation["replaces"]) == (
            "the executor", self.WORD, before["combined_hash"]), confirmation
        assert spec[cc.ZONES_SCHEMA]["profile_hash"] == record["profile_hash"]
        decision = GateDecision.objects.get(id=done["gate_decision_id"])
        assert decision.decided_by is None and self.WORD in decision.notes and "the executor" in decision.notes
        assert self.task.status == "awaiting_gate_2", self.task.status               # drawn again, waiting again
        assert spec["container_resume"]["kind"] == "RECONFIRMATION"
        assert spec["container_reconstruction"]["status"] == "RECONSTRUCTED"
        assert spec["container_zone_containment_report"]["contained"] is True

    def test_a_record_confirmed_before_the_forms_lost_their_neck_is_confirmed_again_its_neck_left_out(self):
        """Measured on 89, the first design this path met: a compact confirmed before §BH70(1), item 17, still carries a
        bottle's neck ratio (0.42), and the editor's rules refuse to fill a neck on a compact — so the check reads only
        the fields the form has, the new record says which it lacks, and the old value stays on it, unread."""
        from types import SimpleNamespace

        from apps.pipeline.services import shape_reconfirmation as sr
        out = self._at_its_review()
        spec = dict(out.spec_sheet)
        record = dict(spec[cc.PROFILE_SCHEMA])
        record["fields"] = dict(record["fields"], neck_ratio=cc._field(0.42, source=cc.SRC_USER_VISUAL,
                                                                       verification=cc.VERIFIED))
        spec[cc.PROFILE_SCHEMA] = record
        out.spec_sheet = spec
        out.save(update_fields=["spec_sheet"])
        done = sr.reconfirm(self.task, variant="round", by="the executor", on_word_of=self.WORD,
                            dispatch=lambda *_a: SimpleNamespace(id="stood-in"))
        out.refresh_from_db()
        record = out.spec_sheet[cc.PROFILE_SCHEMA]
        assert done["variant"] == "round" and record["variant"] == "round", done
        assert "neck_ratio" in record["not_applying"] and record["fields"]["neck_ratio"]["value"] == 0.42, record

    def test_his_yes_a_design_at_its_review_is_reopened_at_its_shape_step_for_him_to_confirm_again(self):
        """His yes of 2026-09-30 (transcribed at 5d23649): 117's print area re-proposed from his concept, and he confirms
        it again himself at the shape step. A design waiting at its review is reopened: its confirmation kept whole in
        its history, lifted; its profile left unconfirmed as the step's start; its print areas proposed, none confirmed;
        the design back at its shape step. A design he has accepted, or one no longer at its review, is refused by name
        with nothing written."""
        import copy

        from apps.dashboard.owner_channel import preview_sha256
        from apps.ire.container_production_readiness import ACCEPTANCE_KEY
        from apps.pipeline.services import shape_reconfirmation as sr
        out = self._at_its_review()
        before = dict(out.spec_sheet["container_confirmation"])
        kept = copy.deepcopy(out.spec_sheet)
        spec = dict(out.spec_sheet)
        spec[ACCEPTANCE_KEY] = {"state": "ACCEPTED", "decided_by": "owner", "preview_sha256": preview_sha256(out)[0]}
        out.spec_sheet = spec
        out.save(update_fields=["spec_sheet"])
        with self.assertRaises(sr.Refused) as raised:
            sr.reopen(self.task, by="the executor", on_word_of=self.WORD)
        assert raised.exception.code == sr.AFTER_HIS_ACCEPTANCE
        out.spec_sheet = kept
        out.save(update_fields=["spec_sheet"])
        done = sr.reopen(self.task, by="the executor", on_word_of=self.WORD)
        self.task.refresh_from_db()
        out.refresh_from_db()
        spec = out.spec_sheet
        assert self.task.status == "awaiting_container_profile" and "container_confirmation" not in spec
        (was,) = spec[sr.HISTORY_KEY]
        assert (was["confirmation"], was["on_word_of"], was["reopened"]) == (before, self.WORD, True)
        assert spec[cc.PROFILE_SCHEMA]["confirmation_state"] == "UNCONFIRMED" and done["replaces"] == \
            before["combined_hash"]
        assert spec[cc.ZONES_SCHEMA]["confirmation_state"] == "PROPOSED"
        assert not any(z.get("user_confirmation_state") == cc.ZONE_USER_CONFIRMED for z in spec[cc.ZONES_SCHEMA]["zones"])
        with self.assertRaises(sr.Refused) as raised:
            sr.reopen(self.task, by="the executor", on_word_of=self.WORD)
        assert raised.exception.code == sr.NOT_AT_REVIEW
        # and the shape step's own confirm door takes his confirmation as a first — his, by his name — and draws it
        from unittest import mock

        from django.contrib.auth.models import User
        from django.test import Client

        from apps.dashboard.exploration_render import confirmed_profile
        client = Client(HTTP_HOST="127.0.0.1")
        client.force_login(User.objects.get(username="reviewer"))
        zones = [dict(z, user_confirmation_state=cc.ZONE_USER_CONFIRMED) for z in spec[cc.ZONES_SCHEMA]["zones"]]
        with mock.patch("apps.pipeline.services.claude_service.call_claude", return_value=self._read_answer()), \
                self.captureOnCommitCallbacks(execute=True):
            answer = client.post(f"/api/tasks/{self.task.id}/confirm_container_profile/",
                                 {"profile": confirmed_profile(spec), "zones": zones}, content_type="application/json")
        assert answer.status_code == 200, answer.content
        self.task.refresh_from_db()
        out.refresh_from_db()
        assert self.task.status == "awaiting_gate_2", self.task.status
        assert out.spec_sheet["container_confirmation"]["confirmed_by"] == "reviewer"
        assert len(out.spec_sheet[sr.HISTORY_KEY]) == 1 and "container_reopened" in out.spec_sheet

    def test_anything_else_is_refused_by_name_and_nothing_is_written(self):
        import copy

        from apps.dashboard.owner_channel import preview_sha256
        from apps.ire.container_production_readiness import ACCEPTANCE_KEY
        from apps.pipeline.services import shape_reconfirmation as sr
        out = self._at_its_review()
        was = out.spec_sheet[cc.PROFILE_SCHEMA]["variant"]
        kept = copy.deepcopy(out.spec_sheet)

        def refused(code, variant):
            with self.assertRaises(sr.Refused) as raised:
                sr.reconfirm(self.task, variant=variant, by="the executor", on_word_of=self.WORD,
                             dispatch=_never_dispatched)
            assert raised.exception.code == code, raised.exception
            out.refresh_from_db()
        refused(sr.UNCHANGED, was)
        refused(sr.VARIANT_NOT_DRAWN, "hexagon")
        assert out.spec_sheet == kept
        spec = dict(out.spec_sheet)
        spec[ACCEPTANCE_KEY] = {"state": "ACCEPTED", "decided_by": "owner", "preview_sha256": preview_sha256(out)[0]}
        out.spec_sheet = spec
        out.save(update_fields=["spec_sheet"])
        refused(sr.AFTER_HIS_ACCEPTANCE, "round")                  # his acceptance settles its shape
        self.task.status = "awaiting_container_profile"
        self.task.save(update_fields=["status"])
        refused(sr.NOT_AT_REVIEW, "round")
        assert sr.HISTORY_KEY not in out.spec_sheet


class TheBadgeSaysWhoConfirmedItTests(TestCase):
    """B1 — the clean-up of 2026-10-04, the badge's words approved by the owner with the clean-up list (transcribed at
    b5892f9): "Confirmed by a person" was fixed text, whoever confirmed the shape — and design 91 and 89, confirmed again
    by the executor on his word (``shape_reconfirmation.reconfirm``), read as his own confirmation. The badge reads the
    record now: "Confirmed by you", "Confirmed by {name}", "Confirmed again by the executor on your word — not by you"
    (his word quoted), or "Not confirmed by a person"; the status payload carries it, said to the person looking."""

    WORD = "his answer of 2026-09-29 to the §BH71 report, (3)"

    def test_b1_each_confirmation_the_record_can_hold_is_said_as_it_was_made(self):
        from apps.pipeline.services.shape_reconfirmation import confirmation_provenance as said
        again = {"confirmed_by": "the executor", "on_word_of": self.WORD, "replaces": "ab" * 32}
        assert said(again, viewer="owner-b1", viewer_is_owner=True)["words"] == (
            "Confirmed again by the executor on your word — not by you: “%s”" % self.WORD)
        assert said(again, viewer="reviewer-b1", viewer_is_owner=False)["words"] == (
            "Confirmed again by the executor on the owner's word — not by the owner: “%s”" % self.WORD)
        mine = {"confirmed_by": "reviewer-b1", "confirmed_at": "2026-10-04T00:00:00+00:00"}
        assert said(mine, viewer="reviewer-b1", viewer_is_owner=False) == {
            "kind": "the_viewer", "by": "reviewer-b1", "on_word_of": "", "words": "Confirmed by you"}
        assert said(mine, viewer="owner-b1", viewer_is_owner=True)["words"] == "Confirmed by reviewer-b1"
        # a name is carried as the record holds it — the page escapes it, never the record
        assert said({"confirmed_by": "<b>x</b>"}, viewer="v", viewer_is_owner=False)["words"] == "Confirmed by <b>x</b>"
        for nothing in (None, {}, {"confirmed_by": "  "}, {"combined_hash": "c0ffee" * 8}):
            assert said(nothing, viewer="owner-b1", viewer_is_owner=True) == {
                "kind": "nobody", "by": "", "on_word_of": "", "words": "Not confirmed by a person"}, nothing

    def test_b1_the_status_payload_says_it_to_the_person_looking(self):
        from django.contrib.auth.models import Group, User
        from django.test import Client

        from apps.pipeline.models import GateDecision, PackagingOutput
        from apps.pipeline.permissions import ROLE_DESIGNER, ROLE_REVIEWER
        brand = Brand.objects.create(name="B", master_brief="x")
        product = Product.objects.create(brand=brand, product_id="CO-B1", name="Rosé", category="CO", year=2026,
                                         width_mm=35, depth_mm=25, height_mm=95)
        task = DesignTask.objects.create(brand=brand, product=product, task_text="a serum bottle",
                                         status="generating_dieline", design_target=DesignTarget.PRODUCT_CONTAINER.value)
        image = GeneratedImage(task=task, direction_name="Rose")
        image.image_file.save("concept.png", ContentFile(_PNG), save=True)
        record = cc.merge_product_record_dims(cc.build_inferred_profile("bottle", "slim"), product)
        # as the executor's door leaves it (shape_reconfirmation.reconfirm): confirmed again on his word, no user
        GateDecision.objects.create(task=task, gate="container_profile", decision="approve", decided_by=None,
                                    notes="Confirmed again as slim by the executor, on " + self.WORD)
        out = PackagingOutput.objects.create(task=task, approved_image=image, spec_sheet={
            "backend": "container", cc.PROFILE_SCHEMA: record, "container_profile": {"archetype": "bottle"},
            "container_confirmation": {"combined_hash": "c0ffee" * 8, "confirmed_by": "the executor",
                                       "confirmed_at": "2026-09-29T06:00:00+00:00",
                                       "authority": "HUMAN_CONFIRMED_CONCEPT_ONLY", "on_word_of": self.WORD,
                                       "replaces": "ab" * 32},
            "container_resume": {"celery_task_id": "celery-1", "requested_at": "2026-09-29T06:00:01+00:00",
                                 "requested_by": "the executor", "kind": "RECONFIRMATION"}})
        owner = User.objects.create_user("owner-b1", password="x")
        owner.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
        reviewer = User.objects.create_user("reviewer-b1", password="x")
        reviewer.groups.add(Group.objects.get_or_create(name=ROLE_REVIEWER)[0])

        def badge(user):
            client = Client()
            client.force_login(user)
            answer = client.get(f"/api/tasks/{task.id}/status/")
            assert answer.status_code == 200, answer.content
            return answer.json()["container_confirmation_provenance"]["words"]
        with override_settings(OWNER_ACCOUNT="owner-b1"):
            assert badge(owner) == "Confirmed again by the executor on your word — not by you: “%s”" % self.WORD
            assert badge(reviewer).startswith("Confirmed again by the executor on the owner's word — not by the owner")
            spec = dict(out.spec_sheet)
            spec["container_confirmation"] = {"combined_hash": "c0ffee" * 8, "confirmed_by": "reviewer-b1",
                                              "confirmed_at": "2026-10-04T00:00:00+00:00"}
            out.spec_sheet = spec
            out.save(update_fields=["spec_sheet"])
            assert badge(reviewer) == "Confirmed by you"
            assert badge(owner) == "Confirmed by reviewer-b1"
        with override_settings(OWNER_ACCOUNT=""):                  # unset: nobody is the owner, and nobody is "you"
            assert badge(owner) == "Confirmed by reviewer-b1"


@override_settings(OPENAI_API_KEY="")
class TheTemplateFallbackIsSaidTests(FaceFormCase):
    """§BH71 PART 1: \"the design says when the fallback was used\" — task 110's fixture, its concept a flat cream picture
    with no lid in it: the template draws, and the drawing's record and the review board say why, by name."""

    def test_a_concept_with_no_lid_in_it_is_drawn_by_the_template_and_says_so(self):
        from apps.pipeline.services import concept_outline as co
        from apps.pipeline.targets.container import OUTLINE_SOURCE_KEY
        _aria, out = self._face()
        source = out.spec_sheet[OUTLINE_SOURCE_KEY]
        assert (source["source"], source["reason"]) == (co.TEMPLATE_FALLBACK, co.TRACE_NO_RIM), source
        rows = {r["label"]: r["value"] for r in ProductContainerTarget().review_sections(self.task)}
        assert " — the fallback: the picture's edges support no outline of the lid" in rows["Drawn outline"]


@override_settings(OPENAI_API_KEY="")
class TheHandOffIsTheFaceTests(FaceFormCase):
    """§BH70(1), item 6 of the list the owner was sent: the Illustrator hand-off recomposed every form through the ruled
    front — a bottle's front label laid over a compact's lid — while his §BH66(a) (LIVE) gives a face "the concept's own
    arrangement". A face form's hand-off is now derived as production and the design loop derive it, never paying for a
    reading: task 110's compact hands off its own face, and without its reading on the record the hand-off refuses."""

    def _handed_off(self, out):
        from unittest import mock

        from apps.ire.handoff import container_adapter
        from apps.pipeline.services import native_handoff as nh
        seen = {}

        class _Written(Exception):
            pass

        def writer(doc, *_a, **_k):                     # the package writer, stood in for: nothing is written
            seen["doc"] = doc
            raise _Written()
        with mock.patch.object(container_adapter, "build_container_handoff_package", writer), \
                mock.patch("apps.pipeline.services.claude_service.call_claude", side_effect=AssertionError("a provider")):
            try:
                nh.generate_container_native_handoff(out, None)
            except _Written:
                pass
        return seen["doc"]

    def test_bh70_a_compacts_hand_off_is_the_face_production_drew(self):
        _aria, out = self._face()
        doc = self._handed_off(out)
        face = (doc.metadata.get("concept_front") or {}).get("face") or {}     # the ruled front carries no face
        assert "product-name-hero" in face.get("drawn", []), face.keys()

    def test_bh70_without_the_concepts_reading_a_compacts_hand_off_refuses_by_name(self):
        from apps.pipeline.services import concept_layout as L
        from apps.pipeline.services import native_handoff as nh
        _aria, out = self._face()
        spec = dict(out.spec_sheet)
        spec.pop(L.SPEC_KEY, None)
        out.spec_sheet = spec
        with self.assertRaises(nh.HandoffError) as refused:
            self._handed_off(out)
        assert refused.exception.code == nh.HANDOFF_NEEDS_THE_CONCEPTS_READING, refused.exception.code


@override_settings(OPENAI_API_KEY="")
class OneDerivationTwoCallersTests(FaceFormCase):
    """[The owner's goal of 2026-09-25, "THE UI, DESIGNED THIS TIME", rule (d): "The library is usable WHILE designing,
    not a separate trip."] What `reconstruct_container` hands the composer for a FACE form is derived by functions moved
    out of it unchanged (`_composer_inputs`, `_front_plan`, `_finish_inputs`), so the design loop draws a face from
    production's own inputs: `face_form_inputs` hands the composer the very call production makes, and writes nothing.
    A run that fails part-way still leaves on the sheet the records it made before the failure — the caller saves it."""

    def test_the_loop_derives_a_face_as_production_does_hands_the_composer_its_call_and_writes_nothing(self):
        import json
        from unittest import mock

        import apps.ire.compose_container as CC
        from apps.pipeline.services import concept_layout as L
        from apps.pipeline.targets.container import draw_face_form, face_form_inputs
        aria, out = self._face()
        sheet, rows = json.dumps(out.spec_sheet, sort_keys=True, default=str), _rows_digest()
        with mock.patch("apps.pipeline.services.claude_service.call_claude", side_effect=AssertionError("a provider")):
            loop = face_form_inputs(self.task, out, self.confirmed, read_layout=L.cached_or_read)
            doc, finish = draw_face_form(loop)
        assert loop["concept_front"]["face"]["vision_layout"]["cached"] is True       # the reading on the record
        assert "product-name-hero" in doc.metadata["concept_front"]["face"]["drawn"] and finish["applied"]
        assert json.dumps(out.spec_sheet, sort_keys=True, default=str) == sheet       # the instance: untouched
        out.refresh_from_db()
        assert json.dumps(out.spec_sheet, sort_keys=True, default=str) == sheet       # the database: untouched
        assert _rows_digest() == rows                                                 # no row of any model
        seen = {}
        real = CC.compose_container_graph

        def spy(backbone, **kw):
            seen.update(kw)
            return real(backbone, **kw)
        with mock.patch.object(CC, "compose_container_graph", spy), \
                mock.patch("apps.pipeline.services.claude_service.call_claude", side_effect=AssertionError("a provider")):
            reconstruct_container(aria, out, self.confirmed)
        assert seen == loop["compose"]                          # production's own call, keyword for keyword
        out.refresh_from_db()
        for op, key, value in loop["records"]:                 # and the records it made are the ones production wrote
            if op == "drop":
                assert key not in out.spec_sheet, key
            else:
                assert out.spec_sheet[key] == json.loads(json.dumps(value, default=str)), key

    def test_a_run_that_fails_part_way_leaves_the_records_it_made_before_it_failed(self):
        """The caller saves the sheet a failed run leaves (aria's `resume_after_container_profile`), so what a failure
        leaves on it is part of the contract: every record made before the failure, and none after it."""
        from unittest import mock
        aria, out = self._face(read=False)
        before = set(out.spec_sheet)
        with mock.patch("apps.ire.container_motif.build_motif_spec", side_effect=RuntimeError("forced")), \
                mock.patch("apps.pipeline.services.claude_service.call_claude", side_effect=AssertionError("provider")):
            with pytest.raises(RuntimeError):
                reconstruct_container(aria, out, self.confirmed)
        # [§BH71 PART 1: the outline the backbone draws is derived, and its record made, BEFORE the composer's
        # inputs — a record made before the failure, so the sheet a failed run leaves carries it]
        # [his final goal, 2026-10-05, C5c] and the profile he confirmed, kept first, so his choice of a stopped
        # back's offers can make the container again
        assert set(out.spec_sheet) - before == {"container_selected_variation/1.0",
                                                "container_selected_concept_visual_graph/1.0",
                                                "container_colour_sources/1.0",
                                                "container_outline_source/1.0",
                                                "container_confirmed_profile"}
        with mock.patch("apps.pipeline.services.claude_service.call_claude", return_value=self._read_answer()), \
                mock.patch("apps.ire.front_hierarchy.ruled_front_hierarchy", side_effect=RuntimeError("forced")):
            with pytest.raises(RuntimeError):
                reconstruct_container(aria, out, self.confirmed)
        assert {"container_motif_spec/1.0", "container_concept_layout/1.0"} <= set(out.spec_sheet)  # the read kept
        assert "container_reconstruction" not in out.spec_sheet
