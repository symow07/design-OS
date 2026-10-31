"""Phase 2C-1 — Complete Product activation, preflight + composite readiness.

Golden fixtures A–E (§16) + the §7 human-acceptance advancement gate + the §5
handoff record + §12 preflight. No provider calls anywhere."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from apps.core.models import Brand, Product
from apps.pipeline.models import (
    DesignTask,
    GateDecision,
    GeneratedImage,
    PackagingOutput,
    TaskReference,
)
from apps.pipeline.targets import composite as cx

_JS = (Path(__file__).resolve().parents[3] / "static" / "js"
       / "poll.js").read_text()
_TPL_DIR = Path(__file__).resolve().parents[3] / "templates" / "dashboard"
# [the owner's answer to the UI directions of 2026-09-25: C's start page replaced the old single page and its parts]
_TPL = (Path(__file__).resolve().parents[3] / "templates" / "dashboard"
        / "new.html").read_text()


class _Mixin(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-1", name="P", category="CO",
            year=2026, product_type="lip gloss",
            width_mm=35, depth_mm=25, height_mm=95)
        self.user = User.objects.create_superuser("u", "u@t.com", "pw")
        self.project, self.container = cx.create_composite_project(
            brand=self.brand, product=self.product, brief="complete set",
            created_by=self.user, target="complete_product")

    def _accept_container(self, human="accepted"):
        """Drive the container stage to completed with a given human state."""
        img = GeneratedImage.objects.create(
            task=self.container, direction_name="D", prompt_used="p",
            variation_number=1)
        spec = {"backend": "container",
                "container_profile/1.0": {"profile_hash": "ph",
                                          "archetype": "bottle",
                                          "fields": {}},
                "container_decoration_zones/1.0": {"zones": [],
                                                   "zone_set_hash": "zh"},
                "container_selected_variation/1.0": {"variation_id": "C_X"},
                "container_reconstruction": {"status": "RECONSTRUCTED",
                                             "blockers": []}}
        if human == "accepted":
            spec["container_human_visual_acceptance"] = {
                "state": "ACCEPTED", "decided_by": "u",
                "decided_at": "2026-07-24T00:00:00Z"}
        elif human == "rejected":
            spec["container_2b3v_final_status/1.0"] = {
                "gate2_human_acceptance": "REJECTED", "blocking_codes": []}
        PackagingOutput.objects.create(
            task=self.container, approved_image=img, spec_sheet=spec)
        self.container.status = "completed"
        self.container.save(update_fields=["status"])


# --- §2/§13 UI ----------------------------------------------------------------

class UiActivationTests(TestCase):
    def test_the_chip_is_present_and_honestly_labelled(self):
        """B4a scoped the selector to the two single-stage targets, so this
        chip is now shown as coming soon. That is a SELECTOR decision: the
        composite pipeline below is untouched and still registered, and the
        note says so rather than letting the label imply it was removed.

        [§BH55 PHASE 1, 2026-09-19 — "The target ships". The chip is ACTIVE now; the paragraph above is what
        stood. The five targets after it stay gated until Phase 2 builds them.]"""
        from apps.pipeline.targets import get_target, ui
        # B4a made the selector data-driven, so the chip is no longer a literal
        # in the template — it is rendered from TARGET_CARDS.
        # [§BH55 Phase 3, 2026-09-19: the chips moved with the composer to the home's center, _start_design.html]
        # [2026-09-25: C's start page, templates/dashboard/new.html]
        assert 'data-target="{{ c.value }}"' in (_TPL_DIR / "new.html").read_text()
        card = ui.card_for("complete_product")
        assert card is not None
        assert card["active"] is True
        # §BH55 Phase 3: it read "Active", then "Finished when the owner accepts its bottle" — [§BH70(4) and §BH70(1)
        # item 1: its container stage cannot be finished yet, so it never reaches its packaging, and the card says so]
        # [§BH71 (0a) and (0b), the owner's goal of 2026-09-28, MEASURED after both on Gate 2's own reader: a clean
        # container waits on the owner's acceptance alone and is approved with it — it read CANNOT_FINISH_YET]
        # [re-pinned: his last goal before the pitch, 2026-10-16, Step 1 (5): "card descriptions in one plain line
        # each, no jargon"] the warning line is said beside Approve, never on the card
        assert card["status"] == ui.FINISHED_WHEN_ACCEPTED and ui.CONTAINER_FINISH not in card["description"]
        assert get_target("complete_product") is not None
        assert "implemented" in ui.COMPLETE_PRODUCT_NOTE
        # every unfinished target stays gated — [§BH55 Phase 2, 2026-09-19: and is NAMED with what it needs, never
        # "Coming soon": "A target that cannot be built is named with what it needs, not left grey."]
        for c in ui.TARGET_CARDS:
            if not c["active"]:
                assert c["status"].startswith("Needs"), c["name"]

    def test_workflow_preview_steps(self):
        for step in ("Design the product container", "Approve the container",
                     "Design coordinated packaging",
                     "Review the complete product set"):
            assert step in _JS


# --- §3 creation contract -------------------------------------------------------

class CreationContractTests(_Mixin):
    def test_creates_project_and_container_only(self):
        assert self.container.design_target == "product_container"
        assert self.container.stage == "container"
        assert DesignTask.objects.filter(project=self.project).count() == 1
        assert not DesignTask.objects.filter(project=self.project,
                                             stage="packaging").exists()


# --- §7 human acceptance gate + fixture B ---------------------------------------

class HumanAcceptanceTests(_Mixin):
    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_fixture_b_rejected_container_never_spawns_packaging(self, _d):
        self._accept_container(human="rejected")
        cx.advance_project(self.project)
        self.project.refresh_from_db()
        assert not DesignTask.objects.filter(project=self.project,
                                             stage="packaging").exists()
        hold = (self.project.metadata or {}).get("hold") or {}
        assert hold.get("code") == \
            cx.COMPOSITE_STAGE_HUMAN_ACCEPTANCE_REQUIRED
        assert cx.project_state(self.project) == "CONTAINER_REJECTED"
        # the rejection stays; project reviewable, not destroyed
        assert self.project.status == "container"

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_completed_but_unreviewed_stage_holds(self, _d):
        self._accept_container(human="none")
        cx.advance_project(self.project)
        assert not DesignTask.objects.filter(project=self.project,
                                             stage="packaging").exists()

    def test_task51_shaped_rejection_is_never_accepted(self):
        self._accept_container(human="rejected")
        acceptance = cx.stage_human_acceptance(self.container)
        assert "REJECTED" in acceptance["state"]


# --- fixture A: approved container advances once (idempotent §9) ---------------

class AdvanceTests(_Mixin):
    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_fixture_a_accepted_container_spawns_packaging_once(self, _d):
        self._accept_container(human="accepted")
        cx.advance_project(self.project)
        cx.advance_project(self.project)            # repeated call
        packs = DesignTask.objects.filter(project=self.project,
                                          stage="packaging")
        assert packs.count() == 1                    # no duplicates
        self.project.refresh_from_db()
        handoffs = (self.project.metadata or {}).get("handoffs") or {}
        assert "packaging" in handoffs               # §5 record, exactly one
        h = handoffs["packaging"]
        assert h["schema_version"] == "complete_product_stage_handoff/1.0"
        assert h["handoff_hash"]
        assert h["source_task_id"] == self.container.id
        assert h["human_visual_acceptance_state"] == "ACCEPTED"
        # §6: no prompts/credentials/hidden reasoning in the record
        blob = str(h)
        assert "prompt" not in blob and "API_KEY" not in blob
        # TaskReferences attached once
        pack = packs.first()
        assert TaskReference.objects.filter(task=pack).count() <= 3

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_fixture_c_packaging_rejected(self, _d):
        self._accept_container(human="accepted")
        cx.advance_project(self.project)
        pack = DesignTask.objects.get(project=self.project, stage="packaging")
        pack.status = "completed"
        pack.save(update_fields=["status"])
        GateDecision.objects.create(task=pack, gate="gate_2",
                                    decision="reject", decided_by=self.user)
        assert cx.project_state(self.project) == "PACKAGING_REJECTED"
        # container stays approved; project not design-complete
        assert cx.stage_human_acceptance(self.container)["state"] == "ACCEPTED"

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_fixture_d_design_complete_production_blocked(self, _d):
        self._accept_container(human="accepted")
        out = self.container.packaging_outputs.first()
        spec = out.spec_sheet
        spec["container_production_readiness/1.0"] = {
            "ready": False, "blocking_codes": ["MISSING_OUTPUT_INTENT"]}
        out.spec_sheet = spec
        out.save(update_fields=["spec_sheet"])
        cx.advance_project(self.project)
        pack = DesignTask.objects.get(project=self.project, stage="packaging")
        pack.status = "completed"
        pack.save(update_fields=["status"])
        GateDecision.objects.create(task=pack, gate="gate_2",
                                    decision="approve", decided_by=self.user)
        assert cx.project_state(self.project) == \
            "DESIGN_COMPLETE_PRODUCTION_BLOCKED"

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_a_production_note_leaves_the_design_complete_and_production_waiting(self, _d):
        """The owner's answer of 2026-09-27: the design is finished when he approves it; the maker's printing
        specification is production's. A container approved with notes standing leaves the project design-complete,
        production waiting — never PRODUCTION_READY while a note stands — and the stage carries its notes."""
        self._accept_container(human="accepted")
        out = self.container.packaging_outputs.first()
        spec = out.spec_sheet
        spec["container_production_readiness/1.0"] = {
            "ready": True, "blocking_codes": [], "production_notes": ["CONTAINER_TECHNIQUE_UNVERIFIED"]}
        out.spec_sheet = spec
        out.save(update_fields=["spec_sheet"])
        cx.advance_project(self.project)
        pack = DesignTask.objects.get(project=self.project, stage="packaging")
        pack.status = "completed"
        pack.save(update_fields=["status"])
        GateDecision.objects.create(task=pack, gate="gate_2",
                                    decision="approve", decided_by=self.user)
        assert cx.project_state(self.project) == "DESIGN_COMPLETE_PRODUCTION_BLOCKED"

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_fixture_e_production_ready_synthetic(self, _d):
        self._accept_container(human="accepted")
        cx.advance_project(self.project)
        pack = DesignTask.objects.get(project=self.project, stage="packaging")
        pack.status = "completed"
        pack.save(update_fields=["status"])
        GateDecision.objects.create(task=pack, gate="gate_2",
                                    decision="approve", decided_by=self.user)
        assert cx.project_state(self.project) == "PRODUCTION_READY"
        summary = cx.build_project_summary(self.project)
        assert summary["production_ready"] is True
        assert summary["project_state"] == "PRODUCTION_READY"
        assert summary["next_required_action"].startswith("none")


# --- §12 preflight ---------------------------------------------------------------

class PreflightTests(TestCase):
    def test_preflight_reports_checks_without_provider_calls(self):
        with patch("apps.pipeline.services.claude_service.call_claude") as pe, \
                patch("apps.pipeline.agents.image_producer.openai.images"
                      ".edit") as ie:
            report = cx.complete_product_preflight()
        pe.assert_not_called()
        ie.assert_not_called()
        assert report["schema_version"] == "complete_product_preflight/1.1"
        assert set(report["checks"]) >= {
            "product_container_target", "packaging_target",
            "migrations_applied", "revision_match", "provider_configuration",
            "handoff_path", "human_acceptance_enforcement",
            "gate2_enforcement", "task_reference_linking", "review_board"}
        assert report["result"] in ("READY_FOR_LIVE_PILOT", "BLOCKED")
        if report["result"] == "BLOCKED":
            assert all(b.startswith("COMPOSITE_DEPENDENCY_NOT_READY")
                       for b in report["blockers"])

    def test_every_check_states_a_reason_and_every_blocker_carries_it(self):
        """The /1.1 defect, stated as the property /1.0 broke.

        /1.0 named the failing check and stopped there, so the 409 body and
        the persisted creation contract said `migrations_applied` whether the
        database was behind or unreachable. Asserted as a TOTAL relation
        between `checks` and `check_detail` rather than against a pinned list
        of names: a pinned list is a second copy of the key set and drifts the
        moment a check is added (§AR2).
        """
        report = cx.complete_product_preflight()
        assert set(report["check_detail"]) == set(report["checks"])
        assert all(str(v).strip() for v in report["check_detail"].values())

        # The test database is migrated and the eager worker matches, so the
        # preflight is READY here and the loop below would be VACUOUS on the
        # real record — it passed against a mutant that dropped the reason
        # from every blocker. Forcing one blocked check is what gives the
        # assertion something to be true of (§AA).
        with patch("apps.core.health.migration_state",
                   return_value="unapplied: 1 (dielines.0008_example)"):
            report = cx.complete_product_preflight()
        assert report["result"] == "BLOCKED"
        assert report["blockers"]
        for blocker in report["blockers"]:
            name = blocker.split(": ", 1)[1].split(" — ")[0]
            assert report["checks"][name] is False
            assert report["check_detail"][name] in blocker

    def test_an_unreadable_database_does_not_look_like_a_behind_one(self):
        """The two states that /1.0 collapsed. Their remedies are opposite."""
        with patch("apps.core.health.migration_state",
                   return_value="unknown: connection refused"):
            unreadable = cx.complete_product_preflight()
        with patch("apps.core.health.migration_state",
                   return_value="unapplied: 1 (pipeline.0026_example)"):
            behind = cx.complete_product_preflight()
        assert unreadable["checks"]["migrations_applied"] is False
        assert behind["checks"]["migrations_applied"] is False
        u = [b for b in unreadable["blockers"] if "migrations_applied" in b]
        b = [x for x in behind["blockers"] if "migrations_applied" in x]
        assert u and b and u != b
        assert "connection refused" in u[0]
        assert "pipeline.0026_example" in b[0]


class HisBlocker123ContinuationTests(_Mixin):
    """[His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (1): "In a
    Complete Product, the carton CONTINUES the approved container: same mood, motif, colours, type and logo treatment
    as 122's approved tube (red line-art roses, oval window, blush pink). Its three options differ only by layout and
    composition on the carton (e.g. full all-over pattern / oval window front / pattern band + clean panels), never by
    mood or personality. The distinctness checks for mood, colour and motif don't apply to it."]"""

    def _approved_container(self):
        from apps.pipeline.models import CreativeBrief
        self._accept_container(human="accepted")
        CreativeBrief.objects.create(task=self.container, selected_direction_id="d3", directions=[
            {"direction_id": "d1", "name": "Not Chosen", "emotional_tone": "bold and loud"},
            {"direction_id": "d3", "name": "Rose Field Engraved", "concept_statement": "An all-over engraved field.",
             "emotional_tone": "Abundant, garden-immersive and tactile.", "graphic_elements": "red line-art roses",
             "color_system": "pale soft pink ground, red line art", "typography": "a geometric rounded sans",
             "material_finish_direction": "rose-gold foil on the BBROSE lockup"}])
        out = self.container.packaging_outputs.first()
        spec = dict(out.spec_sheet)
        spec["container_colour_check/1.0"] = {"roles": {
            "body": {"drawn": "#FAE8E5", "concept": "#F7E9E4"}, "line art": {"drawn": "#AF2B2F", "concept": "#AD252C"}}}
        spec["container_font_usage/1.0"] = {"faces": [{"postscript": "Poppins-Light", "roles": ["display"]},
                                                      {"postscript": "Montserrat-Bold", "roles": ["heading"]}]}
        out.spec_sheet = spec
        out.save(update_fields=["spec_sheet"])

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_the_carton_is_handed_the_approved_containers_own_look(self, _d):
        """Its chosen direction's words, the colours its drawing prints as measured, the faces its drawing sets — what
        was approved, never the plan's guess at a face; the container itself, and a design of its own, handed none."""
        self._approved_container()
        cx.advance_project(self.project)
        pack = DesignTask.objects.get(project=self.project, stage="packaging")
        self.assertEqual(cx.continued_container(pack), self.container)
        words = cx.continuation_words(pack)
        self.assertTrue(words.startswith('This design is the carton of a Complete Product. Its container is approved — '
                                         '"Rose Field Engraved", and the carton CONTINUES it.'), words)
        for said in ("- Its mood: Abundant, garden-immersive and tactile.", "- Its motif: red line-art roses",
                     "- Its finish and logo treatment: rose-gold foil on the BBROSE lockup",
                     "- The colours its drawing prints, as measured on it: body #FAE8E5; line art #AF2B2F",
                     "- Its type, as its drawing sets it: Poppins-Light (display); Montserrat-Bold (heading)"):
            self.assertIn(said, words)
        self.assertNotIn("bold and loud", words)
        self.assertNotIn("geometric rounded sans", words)          # the faces drawn, not the plan's words for them
        self.assertEqual(cx.continuation_words(self.container), "")
        own = DesignTask.objects.create(brand=self.brand, task_text="a carton", design_target="packaging",
                                        created_by=self.user)
        self.assertEqual(cx.continuation_words(own), "")

    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    def test_the_concept_prompts_keep_its_look(self, mock_pe):
        """The prompt writer, told the container it continues, writes three layouts of one look — its one clause
        switched — and every other design's prompt is as it was."""
        from apps.pipeline.agents import prompt_engineer as pe
        mock_pe.return_value = "{\"prompts\": []}"
        agent = pe.PromptEngineerAgent([{"direction_id": "d1", "name": "Band"}], None)
        agent.continuation = "This design is the carton of a Complete Product."
        with patch.object(pe, "extract_json", return_value={"prompts": []}):
            agent.run()
            system, message = mock_pe.call_args[0][:2]
            self.assertEqual(system, pe.PROMPT_ENGINEER_CONTINUATION_SYSTEM)
            self.assertIn("three LAYOUTS of one approved look", system)
            self.assertNotIn("three DIFFERENT designs", system)
            self.assertIn("## This design continues its approved container — keep its look\nThis design is the carton",
                          message)
            agent.continuation = None
            agent.run()
            system, message = mock_pe.call_args[0][:2]
            self.assertEqual(system, pe.PROMPT_ENGINEER_SYSTEM)
            self.assertNotIn("continues its approved container", message)
