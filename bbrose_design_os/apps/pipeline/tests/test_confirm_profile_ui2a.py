"""Confirm Profile UI-2A — confirmation security, idempotency, transaction.

The browser's readiness gating is a courtesy; these tests hold the SERVER to
§9/§10/§12: strict validation of every provided value (the pre-UI-2A
sanitizer silently swallowed junk), a refusal for any post-confirmation
profile change, one GateDecision per accepted profile inside one atomic
block, and worker dispatch strictly after that block — with a queue failure
preserving the accepted gate.
"""
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.core.models import Brand, Product
from apps.pipeline.models import (DesignTask, GateDecision, GeneratedImage,
                                  PackagingOutput)
from apps.pipeline.permissions import ROLE_REVIEWER
from apps.pipeline.services import container_contract as cc
from apps.pipeline.targets.base import DesignTarget

_PROMPT = "p"
_DELAY = "apps.pipeline.tasks.resume_aria_container_profile.delay"


class _ConfirmFixture(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-UI2A", name="Rosé Nectar",
            category="CO", year=2026, product_type="lip gloss",
            width_mm=35, depth_mm=25, height_mm=95)
        group, _ = Group.objects.get_or_create(name=ROLE_REVIEWER)
        self.user = User.objects.create_user("r2a", "r@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)
        self.task = self._make_task()

    def _make_task(self, target=DesignTarget.PRODUCT_CONTAINER.value,
                   status="awaiting_container_profile"):
        task = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="gloss",
            status=status, design_target=target)
        img = GeneratedImage.objects.create(
            task=task, direction_name="D", prompt_used=_PROMPT,
            variation_number=3)
        PackagingOutput.objects.create(
            task=task, approved_image=img,
            spec_sheet={"backend": "container",
                        "container_profile": {"archetype": "bottle"}})
        return task

    def _payload(self, **overrides):
        profile = {"archetype": "bottle", "variant": "slim",
                   "height_mm": 95, "width_mm": 35, "depth_mm": 25,
                   "cap_style": "screw"}
        profile.update(overrides)
        rec = cc.merge_product_record_dims(
            cc.build_inferred_profile("bottle", "slim"), self.product)
        zones = cc.propose_zones(rec)
        for z in zones:
            z["user_confirmation_state"] = cc.ZONE_USER_CONFIRMED
        return {"profile": profile, "zones": zones}

    def _post(self, task=None, body=None):
        task = task or self.task
        return self.client.post(
            f"/api/tasks/{task.id}/confirm_container_profile/",
            body if body is not None else self._payload(),
            content_type="application/json")

    def _assert_nothing_created(self, task=None, delay=None):
        task = task or self.task
        task.refresh_from_db()
        assert task.status == "awaiting_container_profile"
        assert GateDecision.objects.filter(task=task).count() == 0
        if delay is not None:
            delay.assert_not_called()


class SecurityTests(_ConfirmFixture):

    def test_unauthenticated_is_rejected(self):
        from django.test import Client
        r = Client().post(
            f"/api/tasks/{self.task.id}/confirm_container_profile/",
            self._payload(), content_type="application/json")
        assert r.status_code in (401, 403)
        self._assert_nothing_created()

    def test_non_reviewer_is_rejected_without_task_leak(self):
        outsider = User.objects.create_user("nobody2a", password="pw")
        from django.test import Client
        c = Client()
        c.force_login(outsider)
        r = c.post(f"/api/tasks/{self.task.id}/confirm_container_profile/",
                   self._payload(), content_type="application/json")
        assert r.status_code == 403
        body = r.content.decode()
        assert "gloss" not in body and "Rosé" not in body
        self._assert_nothing_created()

    @patch(_DELAY)
    def test_packaging_and_complete_product_are_rejected(self, delay):
        for target in ("packaging", "complete_product"):
            task = self._make_task(target=target)
            r = self._post(task=task)
            assert r.status_code == 409, target
            assert r.json()["error"] == "PROFILE_CONFIRMATION_NOT_APPLICABLE"
            task.refresh_from_db()
            assert task.status == "awaiting_container_profile"
            assert GateDecision.objects.filter(task=task).count() == 0
        delay.assert_not_called()

    @patch(_DELAY)
    def test_wrong_task_state_is_rejected(self, delay):
        task = self._make_task(status="awaiting_gate_1")
        r = self._post(task=task)
        assert r.status_code == 409
        task.refresh_from_db()
        assert task.status == "awaiting_gate_1"
        # not even a rejected-proposal write may land on the spec
        spec = task.packaging_outputs.first().spec_sheet
        assert cc.PROFILE_SCHEMA not in spec
        delay.assert_not_called()

    def test_malformed_profile_is_rejected(self):
        r = self._post(body={"profile": "not-an-object"})
        assert r.status_code == 400
        self._assert_nothing_created()

    def test_unsupported_and_other_archetypes_are_rejected(self):
        for archetype in ("teapot", "other"):
            r = self._post(body={"profile": {"archetype": archetype}})
            assert r.status_code == 400, archetype
            assert "archetype must be one of" in r.json()["error"]
        self._assert_nothing_created()

    @patch(_DELAY)
    def test_incompatible_variant_and_closure_are_rejected(self, delay):
        cases = [{"variant": "nonsense"},          # unknown variant
                 {"cap_style": "spout"},           # unknown closure
                 {"archetype": "jar", "variant": "tapered"},
                 {"archetype": "tube", "variant": "standard",
                  "cap_style": "lid"}]
        for overrides in cases:
            r = self._post(body=self._payload(**overrides))
            assert r.status_code == 400, overrides
            assert r.json()["error"] == "PROFILE_VALIDATION_FAILED", overrides
        self._assert_nothing_created(delay=delay)

    @patch(_DELAY)
    def test_non_finite_and_non_numeric_values_are_rejected(self, delay):
        # raw JSON NaN/Infinity never even reach the validator — the parser
        # refuses the body (still a 400 that creates nothing)
        for bad in (float("nan"), float("inf"), float("-inf")):
            r = self._post(body=self._payload(height_mm=bad))
            assert r.status_code == 400, bad
        # string/typed forms DO reach the validator and get the stable code
        # ("Infinity" and "NaN" parse as floats — isfinite refuses them)
        for bad in ("abc", "NaN", "Infinity", "-Infinity", [], True):
            r = self._post(body=self._payload(height_mm=bad))
            assert r.status_code == 400, bad
            assert r.json()["error"] == "PROFILE_VALIDATION_FAILED", bad
        self._assert_nothing_created(delay=delay)

    @patch(_DELAY)
    def test_out_of_range_values_are_rejected(self, delay):
        for overrides in ({"height_mm": 10}, {"height_mm": 999},
                          {"width_mm": 5}, {"width_mm": 500},
                          {"neck_ratio": 0.05}, {"neck_ratio": 0.9},
                          {"depth_mm": 2}):
            r = self._post(body=self._payload(**overrides))
            assert r.status_code == 400, overrides
        self._assert_nothing_created(delay=delay)

    @patch(_DELAY)
    def test_a_name_wider_than_its_front_is_stopped_in_words(self, delay):
        """§BH70(1) and his §BD(b), "A clipped brand name never ships": a 7 mm pencil named "Rose Glow" cannot carry
        its name across its front at the size a name prints, so the shape step refuses it — its reason in words, never
        an engine code — before a single record byte is written or anything is drawn."""
        import re
        out = self.task.packaging_outputs.first()
        out.spec_sheet = dict(out.spec_sheet, product_name="Rose Glow")
        out.save(update_fields=["spec_sheet"])
        record = cc.merge_user_profile(cc.build_inferred_profile("pencil", "sharpened"), {
            "archetype": "pencil", "variant": "sharpened", "cap_type": "cap",
            "body_height_mm": 150, "body_width_mm": 7, "body_depth_mm": 7})
        zones = cc.propose_zones(record)
        for z in zones:
            z["user_confirmation_state"] = cc.ZONE_USER_CONFIRMED
        r = self._post(body={"profile": {"archetype": "pencil", "variant": "sharpened", "cap_style": "cap",
                                         "height_mm": 150, "width_mm": 7, "depth_mm": 7}, "zones": zones})
        assert r.status_code == 400, r.content
        data = r.json()
        assert data["error"] == "CONTAINER_NAME_WIDER_THAN_ITS_FRONT"
        assert "Rose Glow" in data["reason"] and "cut off" in data["reason"]
        assert not re.search(r"\b[A-Z]{3,}_[A-Z_]{2,}\b", data["reason"]), data["reason"]
        self._assert_nothing_created(delay=delay)

    def test_unknown_task_is_a_plain_404(self):
        r = self.client.post(
            "/api/tasks/999999/confirm_container_profile/",
            self._payload(), content_type="application/json")
        assert r.status_code == 404

    @patch("apps.pipeline.services.claude_service.call_claude")
    @patch(_DELAY)
    def test_failed_validation_touches_nothing(self, delay, claude):
        r = self._post(body=self._payload(height_mm=float("inf")))
        assert r.status_code == 400
        self._assert_nothing_created(delay=delay)
        claude.assert_not_called()


class IdempotencyAndTransactionTests(_ConfirmFixture):

    @patch(_DELAY)
    def test_one_request_one_gate_one_transition_one_dispatch(self, delay):
        delay.return_value.id = "celery-1"
        r = self._post()
        assert r.status_code == 200, r.json()
        body = r.json()
        assert body["ok"] is True and body["task_id"] == self.task.id
        assert body["authority"] == "HUMAN_CONFIRMED_CONCEPT_ONLY"
        decisions = GateDecision.objects.filter(task=self.task,
                                                gate="container_profile")
        assert decisions.count() == 1
        assert body["gate_decision_id"] == decisions.first().id
        # §11: the decision references the schema, hashes and authority
        notes = decisions.first().notes
        assert cc.PROFILE_SCHEMA in notes
        assert "HUMAN_CONFIRMED_CONCEPT_ONLY" in notes
        self.task.refresh_from_db()
        assert self.task.status == "generating_dieline"
        assert delay.call_count == 1
        (args, _) = delay.call_args
        assert args[0] == self.task.id            # stable IDs, no file bytes
        out = self.task.packaging_outputs.first()
        assert out.spec_sheet["container_confirmation"]["authority"] == \
            "HUMAN_CONFIRMED_CONCEPT_ONLY"

    @patch(_DELAY)
    def test_identical_replay_creates_and_dispatches_nothing_new(self, delay):
        delay.return_value.id = "celery-1"
        assert self._post().status_code == 200
        r = self._post()                          # byte-identical replay
        assert r.status_code == 200
        assert r.json()["replayed"] is True
        assert GateDecision.objects.filter(
            task=self.task, gate="container_profile").count() == 1
        assert delay.call_count == 1              # nothing enqueued again

    @patch(_DELAY)
    def test_changed_replay_is_refused(self, delay):
        delay.return_value.id = "celery-1"
        assert self._post().status_code == 200
        r = self._post(body=self._payload(height_mm=150))
        assert r.status_code == 409
        assert r.json()["error"] == "PROFILE_ALREADY_CONFIRMED"
        assert "height_mm" in " ".join(r.json()["detail"])
        assert GateDecision.objects.filter(task=self.task).count() == 1
        assert delay.call_count == 1
        # the confirmed record is untouched
        out = self.task.packaging_outputs.first()
        rec = out.spec_sheet[cc.PROFILE_SCHEMA]
        assert float(rec["fields"]["body_height_mm"]["value"]) == 95.0

    @patch(_DELAY)
    def test_empty_resume_body_still_resumes(self, delay):
        delay.return_value.id = "celery-1"
        assert self._post().status_code == 200
        self.task.refresh_from_db()
        # a failed reconstruction returns the task to the gate state with
        # the error recorded in the spec — that is what resume recovers from
        DesignTask.objects.filter(pk=self.task.pk).update(
            status="awaiting_container_profile")
        out = self.task.packaging_outputs.first()
        spec = out.spec_sheet
        spec["generation_error"] = "boom"
        out.spec_sheet = spec
        out.save(update_fields=["spec_sheet"])
        r = self._post(body={"profile": {}})
        assert r.status_code == 200
        # UI-2B-2B refinement: recovering a WORKER FAILURE is a retry, not a
        # replay — the response says so and names the reason
        assert r.json()["replayed"] is False
        assert r.json()["retry_reason"] == "RECONSTRUCTION_WORKER_FAILED"
        assert delay.call_count == 2              # legitimate re-dispatch
        assert GateDecision.objects.filter(task=self.task).count() == 1

    @patch(_DELAY)
    def test_database_failure_rolls_back_everything(self, delay):
        with patch("apps.pipeline.views._record_decision",
                   side_effect=RuntimeError("db down")):
            try:
                self._post()
            except RuntimeError:
                pass
        # §12: no partial gate — profile persistence rolled back WITH the
        # failed decision, no transition survived, nothing was dispatched
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_container_profile"
        assert GateDecision.objects.filter(task=self.task).count() == 0
        spec = self.task.packaging_outputs.first().spec_sheet
        assert "container_confirmation" not in spec
        delay.assert_not_called()

    @patch(_DELAY)
    def test_queue_failure_preserves_the_accepted_gate(self, delay):
        delay.side_effect = RuntimeError("broker down")
        r = self._post()
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["reconstruction"] == "DISPATCH_FAILED"
        assert GateDecision.objects.filter(task=self.task).count() == 1
        self.task.refresh_from_db()
        assert self.task.status == "generating_dieline"
        spec = self.task.packaging_outputs.first().spec_sheet
        assert spec["container_confirmation"]["combined_hash"]
        assert spec["generation_error"] == "RECONSTRUCTION_DISPATCH_FAILED"

    @patch(_DELAY)
    def test_retry_after_queue_failure_duplicates_no_gate(self, delay):
        delay.side_effect = RuntimeError("broker down")
        assert self._post().status_code == 200
        delay.side_effect = None
        delay.return_value.id = "celery-2"
        r = self._post()                          # retry, identical payload
        assert r.status_code == 200
        assert GateDecision.objects.filter(task=self.task).count() == 1

    @patch("openai.images")
    @patch("apps.pipeline.services.claude_service.call_claude")
    @patch(_DELAY)
    def test_no_synchronous_provider_call(self, delay, claude, images):
        delay.return_value.id = "celery-1"
        assert self._post().status_code == 200
        claude.assert_not_called()
        images.edit.assert_not_called()
        images.generate.assert_not_called()
