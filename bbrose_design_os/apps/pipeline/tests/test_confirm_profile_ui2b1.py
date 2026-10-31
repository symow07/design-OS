"""Confirm Profile UI-2B-1 — reconstruction status contract (server).

The snapshot is DERIVED and read-only: it normalizes the records the
lifecycle already persists (task status, container_resume, generation_error,
ARIA AgentLog milestones, artifact fields) into four coarse states, refuses
to fabricate phases or percentages, scrubs path-like tokens from stored
failure text, and building or requesting it mutates nothing and dispatches
nothing.
"""
import json
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.files.base import ContentFile
from django.test import TestCase

from apps.core.models import Brand, Product
from apps.pipeline.models import (AgentLog, DesignTask, GateDecision,
                                  GeneratedImage, PackagingOutput)
from apps.pipeline.permissions import ROLE_REVIEWER
from apps.pipeline.services import container_contract as cc
from apps.pipeline.services.reconstruction_status import (
    build_container_reconstruction_status)

_DELAY = "apps.pipeline.tasks.resume_aria_container_profile.delay"
_START = "ARIA: container profile confirmed — reconstructing container .ai"
_DONE = "ARIA: reached Gate 2 — awaiting container approval"


class _StatusFixture(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-2B1", name="Rosé", category="CO",
            year=2026, width_mm=35, depth_mm=25, height_mm=95)
        group, _ = Group.objects.get_or_create(name=ROLE_REVIEWER)
        self.user = User.objects.create_user("r2b1", "r@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)

    def _task(self, state="queued", target="product_container",
              confirmed=True):
        status = {"queued": "generating_dieline",
                  "running": "generating_dieline",
                  "dispatch_failed": "generating_dieline",
                  "failed": "awaiting_container_profile",
                  "completed": "awaiting_gate_2",
                  "inconsistent_no_resume": "generating_dieline",
                  "inconsistent_no_ai": "awaiting_gate_2",
                  "unconfirmed": "awaiting_container_profile"}[state]
        task = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="gloss",
            status=status, design_target=target)
        img = GeneratedImage.objects.create(
            task=task, direction_name="D", prompt_used="p",
            variation_number=3)
        record = cc.merge_product_record_dims(
            cc.build_inferred_profile("bottle", "slim"), self.product)
        spec = {"backend": "container", cc.PROFILE_SCHEMA: record,
                "container_profile": {"archetype": "bottle"}}
        if confirmed and state != "unconfirmed":
            spec["container_confirmation"] = {
                "combined_hash": "c0ffee" * 8, "confirmed_by": "r2b1",
                "confirmed_at": "2026-08-01T00:00:00+00:00",
                "authority": "HUMAN_CONFIRMED_CONCEPT_ONLY"}
            if state != "inconsistent_no_resume":
                spec["container_resume"] = {
                    "celery_task_id": "celery-1",
                    "requested_at": "2026-08-01T00:00:01+00:00",
                    "requested_by": "r2b1", "kind": "INITIAL_CONFIRMATION"}
        if state == "dispatch_failed":
            spec["generation_error"] = "RECONSTRUCTION_DISPATCH_FAILED"
        if state == "failed":
            spec["generation_error"] = (
                "backbone build exploded at "
                "/Users/symow/Desktop/private/file.py line 12")
        out = PackagingOutput.objects.create(task=task, approved_image=img,
                                             spec_sheet=spec)
        if confirmed and state != "unconfirmed":
            GateDecision.objects.create(task=task, gate="container_profile",
                                        decision="approve",
                                        decided_by=self.user)
        if state in ("running", "completed"):
            AgentLog.objects.create(task=task, agent_name="ARIA",
                                    action=_START)
        if state == "completed":
            out.design_preview_ai.save("sheet.ai", ContentFile(b"%!PS x"),
                                       save=True)
            out.design_preview.save("sheet.png", ContentFile(b"\x89PNG x"),
                                    save=True)
            AgentLog.objects.create(task=task, agent_name="ARIA",
                                    action=_DONE)
        return task

    def _payload(self, task):
        r = self.client.get(f"/api/tasks/{task.id}/status/")
        assert r.status_code == 200
        return r.json()["container_reconstruction_status"]


class ApplicabilityTests(_StatusFixture):

    def test_absent_for_other_targets_and_unconfirmed(self):
        for state, target in (("queued", "packaging"),
                              ("queued", "complete_product"),
                              ("unconfirmed", "product_container")):
            task = self._task(state=state, target=target,
                              confirmed=(state != "unconfirmed"))
            assert self._payload(task) is None, (state, target)

    def test_absent_without_gate_decision(self):
        task = self._task()
        GateDecision.objects.filter(task=task).delete()
        assert self._payload(task) is None

    def test_unauthenticated_and_unauthorized_are_refused(self):
        from django.test import Client
        task = self._task()
        r = Client().get(f"/api/tasks/{task.id}/status/")
        assert r.status_code in (401, 403)
        outsider = User.objects.create_user("nobody2b1", password="pw")
        c = Client()
        c.force_login(outsider)
        r2 = c.get(f"/api/tasks/{task.id}/status/")
        assert r2.status_code == 403
        assert "gloss" not in r2.content.decode()


class NormalizationTests(_StatusFixture):

    def test_queued(self):
        rs = self._payload(self._task("queued"))
        assert rs["schema"] == "container_reconstruction_status/1.0"
        assert rs["lifecycle_state"] == "QUEUED"
        assert rs["dispatch_status"] == "INITIAL_CONFIRMATION"
        assert rs["terminal"] is False
        assert rs["poll_after_ms"] >= 1000
        assert rs["profile_authority"] == "HUMAN_CONFIRMED_CONCEPT_ONLY"
        assert rs["gate_decision_id"]
        assert rs["profile_hash"]
        assert rs["phase"] is None
        assert rs["started_at"] is None and rs["finished_at"] is None
        assert rs["artifacts"] == {"ai": {"available": False},
                                   "png": {"available": False}}

    def test_running_uses_persisted_worker_evidence(self):
        rs = self._payload(self._task("running"))
        assert rs["lifecycle_state"] == "RUNNING"
        assert rs["started_at"]
        assert rs["terminal"] is False
        assert rs["attempt"] == 1
        assert rs["phase"] is None            # no persisted phase records

    def test_completed_requires_the_recorded_ai_output(self):
        rs = self._payload(self._task("completed"))
        assert rs["lifecycle_state"] == "COMPLETED"
        assert rs["terminal"] is True
        assert rs["finished_at"]
        assert rs["artifacts"]["ai"]["available"] is True
        assert rs["artifacts"]["png"]["available"] is True

    def test_a_redraw_is_never_finished_by_the_drawing_before_it(self):
        """Found on his re-confirmed 117 (2026-10-01): the page said "queued 1 Oct, 17:51 · started 1 Oct, 17:51 ·
        finished 30 Sept, 20:04" — its poll landed between the design reaching its review and the drawing's done line,
        and read the drawing before's. A done line older than this drawing's start is not its finish: the design's own
        last change is, until the done line is written; then the done line."""
        import datetime
        task = self._task("completed")
        old_done = AgentLog.objects.filter(task=task, action=_DONE).get()
        AgentLog.objects.filter(pk=old_done.pk).update(
            timestamp=old_done.timestamp - datetime.timedelta(hours=14))
        start = AgentLog.objects.create(task=task, agent_name="ARIA", action=_START)      # the redraw
        task.save()                                       # the redraw reaches the review — its done line not yet written
        rs = self._payload(task)
        assert rs["lifecycle_state"] == "COMPLETED" and rs["finished_at"] >= rs["started_at"], rs
        assert rs["finished_at"] != AgentLog.objects.get(pk=old_done.pk).timestamp.isoformat()
        done = AgentLog.objects.create(task=task, agent_name="ARIA", action=_DONE)
        assert self._payload(task)["finished_at"] == done.timestamp.isoformat() and done.timestamp >= start.timestamp

    def test_success_state_without_output_is_inconsistent(self):
        rs = self._payload(self._task("inconsistent_no_ai"))
        assert rs["lifecycle_state"] == "RECONSTRUCTION_STATUS_INCONSISTENT"
        assert rs["terminal"] is False

    def test_generating_without_resume_record_is_inconsistent(self):
        rs = self._payload(self._task("inconsistent_no_resume"))
        assert rs["lifecycle_state"] == "RECONSTRUCTION_STATUS_INCONSISTENT"

    def test_worker_failure_is_failed_with_scrubbed_message(self):
        rs = self._payload(self._task("failed"))
        assert rs["lifecycle_state"] == "FAILED"
        assert rs["terminal"] is True
        assert rs["error"]["code"] == "RECONSTRUCTION_FAILED"
        assert "[path removed]" in rs["error"]["message"]
        assert "/Users/" not in rs["error"]["message"]

    def test_dispatch_failure_is_represented_honestly(self):
        rs = self._payload(self._task("dispatch_failed"))
        assert rs["lifecycle_state"] == "FAILED"
        assert rs["error"]["code"] == "RECONSTRUCTION_DISPATCH_FAILED"
        assert rs["dispatch_status"] == "DISPATCH_FAILED"
        # the accepted gate survives the dispatch failure
        assert rs["gate_decision_id"]

    def test_his_122_every_stop_the_drawing_can_make_is_said_in_words(self):
        """[His test blocker on design 122 at reconstruction, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md), item 3: "The stop
        reason must be shown in plain words on the page, never only codes in a fold."] A failed drawing's status carries
        each reason in words; every code each of the drawing's own checks can stop it on — the fidelity checks, the motif
        and lettering checks, the shape checks, the print-area checks — has words of its own, never its code and never
        "no words written for it yet"; a code no check has yet is still said in words."""
        import re

        from apps.dashboard.words import drawing_stop_reasons
        from apps.ire import container_concept_fidelity, container_fidelity, container_motif_fidelity
        from apps.pipeline.services import container_projection, flat_motif
        task = self._task("failed")
        out = task.packaging_outputs.first()
        out.spec_sheet = dict(out.spec_sheet, generation_error=(
            "CONTAINER_NATIVE_RECONSTRUCTION_FAILED: CONTAINER_PRODUCT_NAME_TOO_SMALL; "
            "CONTAINER_FRONT_BACK_RELATIONSHIP_FAILED"))
        out.save()
        reasons = self._payload(task)["error"]["reasons"]
        assert reasons == [
            "the product name was not drawn on the front as the name, or it was drawn smaller than the print floor "
            "allows",
            "the front does not carry the hero — neither the product name nor the concept's motif — or the back carries "
            "the hero motif"], reasons
        unwritten = drawing_stop_reasons("CONTAINER_SOMETHING_NEW")
        codes = {v for mod in (container_fidelity, container_motif_fidelity, container_concept_fidelity,
                               container_projection, flat_motif)
                 for k, v in vars(mod).items() if k.isupper() and isinstance(v, str)
                 and re.fullmatch(r"(CONTAINER|SELECTED)_[A-Z_]+", v) and not v.endswith("_UNMEASURED")}
        codes |= {"VECTOR_RECONSTRUCTION_REVIEW_REQUIRED", "RECONSTRUCTION_DISPATCH_FAILED"}
        codes.discard(container_fidelity.NATIVE_RECONSTRUCTION_FAILED)        # the head: that it failed, never why
        assert len(codes) > 40, len(codes)
        for code in sorted(codes):
            said = drawing_stop_reasons("CONTAINER_NATIVE_RECONSTRUCTION_FAILED: %s: its detail" % code)
            assert said and said != unwritten and not re.search(r"[A-Z]{2,}_", " ".join(said)), (code, said)
        assert unwritten and "_" not in unwritten[0]
        assert drawing_stop_reasons("") == []

    def test_payload_carries_no_paths_keys_or_percentages(self):
        for state in ("queued", "running", "completed", "failed",
                      "dispatch_failed"):
            rs = self._payload(self._task(state))
            dump = json.dumps(rs)
            for banned in ("/media/", "task_refs/", "/Users/", "/var/",
                           "Traceback", "MEDIA_URL", "dielines/"):
                assert banned not in dump, (state, banned)
            assert "percent" not in dump and '"progress"' not in dump


class ReadOnlyTests(_StatusFixture):

    @patch("openai.images")
    @patch("apps.pipeline.services.claude_service.call_claude")
    @patch(_DELAY)
    def test_status_requests_mutate_and_dispatch_nothing(self, delay, claude,
                                                         images):
        task = self._task("queued")
        before_decisions = GateDecision.objects.count()
        before_logs = AgentLog.objects.count()
        spec_before = task.packaging_outputs.first().spec_sheet
        for _ in range(3):
            assert self._payload(task)["lifecycle_state"] == "QUEUED"
        task.refresh_from_db()
        assert task.status == "generating_dieline"
        assert GateDecision.objects.count() == before_decisions
        assert AgentLog.objects.count() == before_logs
        assert task.packaging_outputs.first().spec_sheet == spec_before
        delay.assert_not_called()
        claude.assert_not_called()
        images.edit.assert_not_called()
        images.generate.assert_not_called()

    def test_builder_is_pure_for_repeated_calls(self):
        task = self._task("running")
        first = build_container_reconstruction_status(task)
        second = build_container_reconstruction_status(task)
        assert first == second
