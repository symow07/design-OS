"""Phase 2B-3V resume-correction — confirmation must resume the workflow.

Task #51's combined confirmation persisted and the worker consumed the resume,
but reconstruction failed closed with SELECTED_CONTAINER_VARIATION_IDENTITY_
REQUIRED: the identity chain only searched the REGENERATION flow's payloads
("Gate-1 prompts: generation result" / Gate1RegenerationJob) and missed the
INITIAL structured contract render's log ("Gate-1 variation contract result").
The stale UI then re-rendered an active confirmation form over a CONFIRMED
contract. These tests pin the correction. No provider call anywhere."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.core.models import Brand, Product
from apps.pipeline.models import (
    AgentLog,
    DesignTask,
    GateDecision,
    GeneratedImage,
    PackagingOutput,
)
from apps.pipeline.services import container_contract as cc
from apps.pipeline.targets.base import DesignTarget

ROLE_REVIEWER = "Reviewer"

_JS = (Path(__file__).resolve().parents[3] / "static" / "js"
       / "confirm_profile.js").read_text()

_PROMPT = ("a slim rigid wand-applicator lip-gloss bottle with a native-vector "
           "dewdrop constellation design built from live typography and closed "
           "Bézier droplet paths with radial gradient fills and selective "
           "spot-UV masks, photographed as a luxury concept packshot with "
           "shallow depth of field and warm studio light from the upper right "
           "side of frame") * 2


def _payload(identity="C_DEWDROP_CONSTELLATION"):
    base = {
        "title": "Dewdrop Constellation",
        "prompt": _PROMPT,
        "typography_signature": "flush-left editorial stack",
        "composition_signature": "asymmetric diagonal",
        "motif_signature": "dewdrop constellation, 22-30 droplets",
        "cap_body_signature": "matte cap vs glassy body",
        "decoration_zone_signature": "edge-led constellation",
        "color_field_signature": "peach-rose transparent glass",
        "finish_signature": "selective spot-UV on largest drops",
        "native_reconstruction_plan": "live type + Bézier droplets + gradients",
        "reference_ids": [1],
    }
    variations = []
    for vid in ("A_PETAL_WINDOW", "B_LIQUID_VEIL", "C_DEWDROP_CONSTELLATION"):
        v = dict(base)
        v["variation_id"] = vid
        v["prompt"] = _PROMPT if vid == identity else _PROMPT + f" {vid}"
        variations.append(v)
    return {"schema_version": "container_gate1_variations/1.0",
            "approved_reference_ids": [1], "influence_plan_hash": "ph",
            "variations": variations}


class PayloadFinderTests(TestCase):
    """The identity chain recognizes the initial contract render's log."""

    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.task = DesignTask.objects.create(
            brand=self.brand, task_text="gloss", status="awaiting_gate_1",
            design_target=DesignTarget.PRODUCT_CONTAINER.value)
        self.img = GeneratedImage.objects.create(
            task=self.task, direction_name="D", prompt_used=_PROMPT,
            variation_number=3,
            reference_provenance={"variation_identity":
                                  "C_DEWDROP_CONSTELLATION"})

    def test_contract_render_log_payload_is_found_and_verified(self):
        AgentLog.objects.create(
            task=self.task, agent_name="PromptEngineer",
            action="Gate-1 variation contract result",
            payload={"ok": True,
                     "raw_responses": [json.dumps(_payload())]})
        from apps.pipeline.services.selected_concept import (
            load_selected_variation)
        v = load_selected_variation(self.task, self.img)
        assert v is not None and v["verified"] is True
        assert v["variation_id"] == "C_DEWDROP_CONSTELLATION"

    def test_without_any_payload_it_fails_closed(self):
        from apps.pipeline.services.selected_concept import (
            load_selected_variation)
        v = load_selected_variation(self.task, self.img)
        assert v["verified"] is False           # never silently legacy

    def test_his_test_findings_121_a_concept_whose_ids_were_read_by_their_slots_is_found_again(self):
        """[His test findings on design 121, 2026-10-07, item 1] the live model's second answer on 121, as the log keeps
        it ("A_d1_REBEL_BLOOM"), and the concept drawn and approved as the step read it ("A_REBEL_BLOOM"): found and
        verified — read apart, a design outside a project stopped after Gate 1, its approved concept not found."""
        from apps.pipeline.services.claude_service import loads_tolerant
        from apps.pipeline.services.selected_concept import load_selected_variation
        from apps.pipeline.tests.fixtures_agentlog2420 import RAW_RESPONSES
        first = loads_tolerant(RAW_RESPONSES[1])["variations"][0]
        assert first["variation_id"] == "A_d1_REBEL_BLOOM"
        img = GeneratedImage.objects.create(
            task=self.task, direction_name="Rebel Bloom", prompt_used=first["prompt"], variation_number=1,
            reference_provenance={"variation_identity": "A_REBEL_BLOOM"})
        AgentLog.objects.create(task=self.task, agent_name="PromptEngineer", action="Gate-1 variation contract result",
                                payload={"ok": True, "raw_responses": [RAW_RESPONSES[1]]})
        v = load_selected_variation(self.task, img)
        assert v["verified"] is True and v["variation_id"] == "A_REBEL_BLOOM", v


class IdempotentConfirmTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-410", name="Rosé Nectar",
            category="CO", year=2026, product_type="lip gloss",
            width_mm=35, depth_mm=25, height_mm=95)
        group, _ = Group.objects.get_or_create(name=ROLE_REVIEWER)
        self.user = User.objects.create_user("r", "r@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)
        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="gloss",
            status="awaiting_container_profile",
            design_target=DesignTarget.PRODUCT_CONTAINER.value)
        img = GeneratedImage.objects.create(
            task=self.task, direction_name="D", prompt_used=_PROMPT,
            variation_number=3)
        self.out = PackagingOutput.objects.create(
            task=self.task, approved_image=img,
            spec_sheet={"backend": "container",
                        "container_profile": {"archetype": "bottle"}})

    def _confirm(self):
        rec = cc.merge_product_record_dims(
            cc.build_inferred_profile("bottle", "slim"), self.product)
        zones = cc.propose_zones(rec)
        for z in zones:
            z["user_confirmation_state"] = cc.ZONE_USER_CONFIRMED
        return self.client.post(
            f"/api/tasks/{self.task.id}/confirm_container_profile/",
            {"profile": {"archetype": "bottle", "variant": "slim",
                         "height_mm": 95, "width_mm": 35, "depth_mm": 25,
                         "cap_style": "screw"},
             "zones": zones}, content_type="application/json")

    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_first_confirmation_records_once_and_returns_resume_identity(
            self, mock_delay):
        mock_delay.return_value.id = "celery-abc"
        resp = self._confirm()
        assert resp.status_code == 200, resp.json()
        body = resp.json()
        assert body["resume"]["celery_task_id"] == "celery-abc"
        assert body["resume"]["kind"] == "INITIAL_CONFIRMATION"
        assert mock_delay.call_count == 1
        assert GateDecision.objects.filter(
            task=self.task, gate="container_profile").count() == 1
        self.out.refresh_from_db()
        assert self.out.spec_sheet["container_resume"]["celery_task_id"] == \
            "celery-abc"

    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_repeat_post_after_failure_resumes_without_duplicating(
            self, mock_delay):
        mock_delay.return_value.id = "celery-1"
        assert self._confirm().status_code == 200
        self.out.refresh_from_db()
        spec = self.out.spec_sheet
        h_profile = spec[cc.PROFILE_SCHEMA]["profile_hash"]
        h_zones = spec[cc.ZONES_SCHEMA]["zone_set_hash"]
        combined = spec["container_confirmation"]["combined_hash"]
        # reconstruction failed closed → parked back at the gate with a code
        self.task.refresh_from_db()
        self.task.status = "awaiting_container_profile"
        self.task.save(update_fields=["status"])
        spec["generation_error"] = "SOME_CODE"
        self.out.spec_sheet = spec
        self.out.save(update_fields=["spec_sheet"])

        mock_delay.return_value.id = "celery-2"
        resp = self._confirm()                      # repeated POST
        assert resp.status_code == 200, resp.json()
        body = resp.json()
        assert body["resume"]["kind"] == \
            "IDEMPOTENT_RESUME_FROM_PERSISTED_CONFIRMATION"
        assert mock_delay.call_count == 2           # exactly one more resume
        # no duplicated confirmation history, hashes unchanged
        assert GateDecision.objects.filter(
            task=self.task, gate="container_profile").count() == 1
        self.out.refresh_from_db()
        spec = self.out.spec_sheet
        assert spec[cc.PROFILE_SCHEMA]["profile_hash"] == h_profile
        assert spec[cc.ZONES_SCHEMA]["zone_set_hash"] == h_zones
        assert spec["container_confirmation"]["combined_hash"] == combined
        assert "generation_error" not in spec       # cleared for the new run
        self.task.refresh_from_db()
        assert self.task.status == "generating_dieline"

    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_repeat_post_while_running_does_not_enqueue_again(self, mock_delay):
        mock_delay.return_value.id = "celery-1"
        assert self._confirm().status_code == 200   # → generating_dieline
        resp = self._confirm()                      # still running
        assert resp.status_code == 200
        assert "already running" in resp.json()["message"].lower()
        assert mock_delay.call_count == 1           # no duplicate job

    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_no_provider_call_during_confirm_or_resume(self, mock_delay):
        mock_delay.return_value.id = "celery-1"
        with patch("apps.pipeline.services.claude_service.call_claude") as pe, \
                patch("apps.pipeline.agents.image_producer.openai.images.edit") as ie, \
                patch("apps.pipeline.agents.image_producer.openai.images.generate") as ig:
            self._confirm()
            self._confirm()
        pe.assert_not_called()
        ie.assert_not_called()
        ig.assert_not_called()


class ConfirmedUiTests(TestCase):
    def test_confirmed_state_replaces_the_form(self):
        assert "_renderConfirmedState" in _JS
        assert "Its shape, sizes and print areas — confirmed" in _JS    # [plain words, 2026-09-25 (d)]
        # the confirmed branch renders BEFORE the form builds
        confirmed_branch = _JS.split("_renderConfirmedState(data, spec);")[0]
        assert "container_confirmation" in confirmed_branch

    def test_failed_state_shows_code_and_resume_action(self):
        # [the owner's goal of 2026-09-25, (d): the words shown, the code kept — folded under the record, escaped]
        assert "The drawing did not finish." in _JS
        assert "<code>${escapeHtml(err)}</code>" in _JS
        assert "generation_error" in _JS
        assert "submitContainerResume" in _JS

    def test_running_and_complete_states_render(self):
        assert "Being drawn…" in _JS
        assert "Drawn — waiting for your review." in _JS                 # [plain words, 2026-09-25 (d)]
