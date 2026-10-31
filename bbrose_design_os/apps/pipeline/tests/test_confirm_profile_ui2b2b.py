"""Confirm Profile UI-2B-2B — retry eligibility, exactly-once retry, recovery.

Retry is REUSE: the persisted confirmed profile and its single GateDecision
drive every re-dispatch; the server's eligibility block is authoritative;
compare-and-set state (task-status CAS, spec failure-marker CAS) makes each
accepted retry dispatch exactly once; previous failure evidence survives in
container_retry_history and the AgentLog; and nothing here ever touches a
provider synchronously.
"""
import json
from unittest.mock import patch

from apps.pipeline.models import AgentLog, GateDecision, PackagingOutput
from apps.pipeline.services import container_contract as cc

from .test_confirm_profile_ui2b1 import _DELAY, _StatusFixture


def _reconstructed(task, fresh):
    """§BH54(d): give a completed fixture a reconstruction and its saved readiness codes — every declared section
    (fresh), or saved before the brand_strings section was declared (stale, 2026-08-21)."""
    from apps.ire import container_production_readiness as cpr
    out = task.packaging_outputs.first()
    spec = out.spec_sheet
    spec["container_reconstruction"] = {"status": "RECONSTRUCTED", "blockers": []}
    spec["container_production_readiness_codes"] = {
        name: [] for name in cpr._SECTIONS if fresh or name != "brand_strings"}
    out.spec_sheet = spec
    out.save(update_fields=["spec_sheet"])
    return out


class RetryEligibilityTests(_StatusFixture):

    def _retry(self, task):
        r = self.client.get(f"/api/tasks/{task.id}/status/")
        rs = r.json()["container_reconstruction_status"]
        return (rs or {}).get("retry")

    def test_active_and_clean_states_are_not_retryable(self):
        for state in ("queued", "running"):
            block = self._retry(self._task(state))
            assert block["eligible"] is False, state
            assert block["active_attempt"] is True, state
        done = self._retry(self._task("completed"))
        assert done["eligible"] is False and done["active_attempt"] is False

    def test_a_stale_result_awaiting_gate_2_may_be_re_derived_and_a_fresh_or_accepted_one_may_not(self):
        """§BH54(d): "a STALE spec is re-derived before it can be accepted and the re-derivation decides." The
        re-derivation is a reconstruction of the SAME confirmed profile, offered for a finished result that awaits
        Gate 2 and whose saved verdict predates today's checks — never for a fresh one, never for an accepted one."""
        from apps.pipeline.models import DesignTask
        stale = self._task("completed")
        _reconstructed(stale, fresh=False)
        block = self._retry(stale)
        assert block["eligible"] is True and block["reason_code"] == "STALE_SPEC_REDERIVATION"
        assert block["checks_predate"] == ["2026-08-21"] and block["active_attempt"] is False
        fresh = self._task("completed")
        _reconstructed(fresh, fresh=True)
        assert self._retry(fresh)["eligible"] is False
        accepted = self._task("completed")
        _reconstructed(accepted, fresh=False)
        DesignTask.objects.filter(pk=accepted.pk).update(status="gate_2_approved")
        accepted.refresh_from_db()
        assert self._retry(accepted)["eligible"] is False

    def test_failure_classes_are_distinguished(self):
        dispatch = self._retry(self._task("dispatch_failed"))
        assert dispatch["eligible"] is True
        assert dispatch["reason_code"] == "RECONSTRUCTION_DISPATCH_FAILED"
        worker = self._retry(self._task("failed"))
        assert worker["eligible"] is True
        assert worker["reason_code"] == "RECONSTRUCTION_WORKER_FAILED"
        for block in (dispatch, worker):
            assert block["requires_owner_confirmation"] is True
            assert block["existing_gate_decision_id"]
            assert block["confirmed_profile_hash"]
            assert block["action"] == "RESUME_EXISTING_CONFIRMED_PROFILE"

    def test_inconsistent_completion_is_retryable(self):
        block = self._retry(self._task("inconsistent_no_ai"))
        assert block["eligible"] is True
        assert block["reason_code"] == \
            "RETRYABLE_RECONSTRUCTION_INCONSISTENCY"

    def test_tampered_artifact_requires_technical_intervention(self):
        task = self._task("completed")
        out = task.packaging_outputs.first()
        out.design_preview_ai.name = "../../.env"
        out.save(update_fields=["design_preview_ai"])
        block = self._retry(task)
        assert block["eligible"] is False
        assert block["reason_code"] == "RECONSTRUCTION_ARTIFACT_INVALID"
        assert block["recovery"] == "TECHNICAL_INTERVENTION_REQUIRED"

    def test_unexplainable_state_requires_technical_intervention(self):
        block = self._retry(self._task("inconsistent_no_resume"))
        assert block["eligible"] is False
        assert block["recovery"] == "TECHNICAL_INTERVENTION_REQUIRED"

    def test_other_targets_and_unconfirmed_have_no_retry_contract(self):
        for state, target in (("queued", "packaging"),
                              ("queued", "complete_product"),
                              ("unconfirmed", "product_container")):
            task = self._task(state, target=target,
                              confirmed=(state != "unconfirmed"))
            r = self.client.get(f"/api/tasks/{task.id}/status/")
            assert r.json()["container_reconstruction_status"] is None

    @patch("openai.images")
    @patch("apps.pipeline.services.claude_service.call_claude")
    @patch(_DELAY)
    def test_eligibility_is_read_only(self, delay, claude, images):
        task = self._task("failed")
        spec_before = task.packaging_outputs.first().spec_sheet
        for _ in range(3):
            assert self._retry(task)["eligible"] is True
        task.refresh_from_db()
        assert task.status == "awaiting_container_profile"
        assert task.packaging_outputs.first().spec_sheet == spec_before
        delay.assert_not_called()
        claude.assert_not_called()
        images.edit.assert_not_called()


class ExactlyOnceRetryTests(_StatusFixture):

    def _resume(self, task):
        return self.client.post(
            f"/api/tasks/{task.id}/confirm_container_profile/",
            {"profile": {}}, content_type="application/json")

    @patch(_DELAY)
    def test_worker_failure_retry_reuses_everything_once(self, delay):
        delay.return_value.id = "celery-r1"
        task = self._task("failed")
        profile_before = json.dumps(
            task.packaging_outputs.first().spec_sheet[cc.PROFILE_SCHEMA],
            sort_keys=True)
        r = self._resume(task)
        assert r.status_code == 200, r.json()
        body = r.json()
        assert body["retry_reason"] == "RECONSTRUCTION_WORKER_FAILED"
        assert body["replayed"] is False
        # exactly one gate decision, byte-identical confirmed profile
        assert GateDecision.objects.filter(
            task=task, gate="container_profile").count() == 1
        out = task.packaging_outputs.first()
        assert json.dumps(out.spec_sheet[cc.PROFILE_SCHEMA],
                          sort_keys=True) == profile_before
        # one dispatch with stable IDs only
        assert delay.call_count == 1
        args = delay.call_args[0]
        assert args[0] == task.id and args[1] == out.id
        assert all(isinstance(v, (int, float, str))
                   for v in args[2].values())
        task.refresh_from_db()
        assert task.status == "generating_dieline"
        # audit: history entry + attributed AgentLog row; evidence retained
        history = out.spec_sheet["container_retry_history"]
        assert len(history) == 1
        assert "backbone build exploded" in history[0]["previous_failure"]
        assert history[0]["by"] == "r2b1"
        log = AgentLog.objects.filter(
            task=task, action__contains="owner retry dispatched").first()
        assert log is not None and log.actor_id == self.user.id

    @patch(_DELAY)
    def test_double_and_replayed_requests_dispatch_once(self, delay):
        delay.return_value.id = "celery-r1"
        task = self._task("failed")
        assert self._resume(task).status_code == 200
        second = self._resume(task)
        assert second.status_code == 200
        assert second.json()["replayed"] is True
        assert delay.call_count == 1
        assert GateDecision.objects.filter(task=task).count() == 1

    @patch(_DELAY)
    def test_retry_while_running_is_a_replay_not_a_dispatch(self, delay):
        task = self._task("running")
        r = self._resume(task)
        assert r.status_code == 200
        assert r.json()["replayed"] is True
        delay.assert_not_called()

    @patch(_DELAY)
    def test_retry_after_clean_completion_is_refused(self, delay):
        task = self._task("completed")
        r = self._resume(task)
        assert r.status_code == 409
        assert r.json()["error"] == "RETRY_NOT_ELIGIBLE"
        delay.assert_not_called()
        task.refresh_from_db()
        assert task.status == "awaiting_gate_2"

    @patch(_DELAY)
    def test_a_stale_re_derivation_transitions_and_dispatches_once(self, delay):
        """§BH54(d): the door accepts the re-derivation of a stale, not-yet-accepted result — the existing confirmed
        profile and its one gate decision reused, the lineage kept — and a fresh clean completion stays refused."""
        delay.return_value.id = "celery-r54"
        task = self._task("completed")
        _reconstructed(task, fresh=False)
        r = self._resume(task)
        assert r.status_code == 200, r.json()
        assert r.json()["retry_reason"] == "STALE_SPEC_REDERIVATION"
        task.refresh_from_db()
        assert task.status == "generating_dieline"
        assert delay.call_count == 1
        history = task.packaging_outputs.first().spec_sheet["container_retry_history"]
        assert history[0]["previous_failure"] == "STALE_SPEC_REDERIVATION"
        assert GateDecision.objects.filter(task=task).count() == 1
        again = self._resume(task)                                # already running: a replay, never a second dispatch
        assert again.status_code == 200 and again.json()["replayed"] is True
        assert delay.call_count == 1
        fresh = self._task("completed")
        _reconstructed(fresh, fresh=True)
        refused = self._resume(fresh)
        assert refused.status_code == 409 and refused.json()["error"] == "RETRY_NOT_ELIGIBLE"

    @patch(_DELAY)
    def test_dispatch_failure_recovery_redispatches_once(self, delay):
        delay.return_value.id = "celery-r2"
        task = self._task("dispatch_failed")
        r = self._resume(task)
        assert r.status_code == 200, r.json()
        assert r.json()["retry_reason"] == "RECONSTRUCTION_DISPATCH_FAILED"
        assert delay.call_count == 1
        out = task.packaging_outputs.first()
        assert "generation_error" not in out.spec_sheet
        assert out.spec_sheet["container_retry_history"][0][
            "previous_failure"] == "RECONSTRUCTION_DISPATCH_FAILED"
        # a second request finds the marker cleared → replay, no dispatch
        again = self._resume(task)
        assert again.json()["replayed"] is True
        assert delay.call_count == 1

    @patch(_DELAY)
    def test_inconsistent_completion_retry_transitions_and_dispatches(
            self, delay):
        delay.return_value.id = "celery-r3"
        task = self._task("inconsistent_no_ai")
        r = self._resume(task)
        assert r.status_code == 200, r.json()
        assert r.json()["retry_reason"] == \
            "RETRYABLE_RECONSTRUCTION_INCONSISTENCY"
        task.refresh_from_db()
        assert task.status == "generating_dieline"
        assert delay.call_count == 1
        history = task.packaging_outputs.first().spec_sheet[
            "container_retry_history"]
        assert history[0]["previous_failure"] == "INCONSISTENT_COMPLETION"
        assert GateDecision.objects.filter(task=task).count() == 1

    @patch(_DELAY)
    def test_tampered_artifact_retry_is_refused(self, delay):
        task = self._task("completed")
        out = task.packaging_outputs.first()
        out.design_preview_ai.name = "../../.env"
        out.save(update_fields=["design_preview_ai"])
        r = self._resume(task)
        assert r.status_code == 409
        assert r.json()["error"] == "RETRY_NOT_ELIGIBLE"
        assert "TECHNICAL_INTERVENTION_REQUIRED" in r.json()["detail"]
        delay.assert_not_called()

    @patch(_DELAY)
    def test_queue_failure_on_retry_stays_recoverable(self, delay):
        task = self._task("failed")
        delay.side_effect = RuntimeError("broker down")
        r = self._resume(task)
        assert r.status_code == 502
        assert r.json()["error"] == "RECONSTRUCTION_DISPATCH_FAILED"
        out = task.packaging_outputs.first()
        assert out.spec_sheet["generation_error"] == \
            "RECONSTRUCTION_DISPATCH_FAILED"
        assert len(out.spec_sheet["container_retry_history"]) == 1
        assert GateDecision.objects.filter(task=task).count() == 1
        # the queue recovers; the owner retries once more — still one gate
        delay.side_effect = None
        delay.return_value.id = "celery-r4"
        r2 = self._resume(task)
        assert r2.status_code == 200
        assert delay.call_count == 2
        assert GateDecision.objects.filter(task=task).count() == 1
        history = task.packaging_outputs.first().spec_sheet[
            "container_retry_history"]
        assert len(history) == 2                 # both attempts preserved

    @patch(_DELAY)
    def test_database_failure_dispatches_nothing(self, delay):
        task = self._task("failed")
        with patch.object(PackagingOutput, "save",
                          side_effect=RuntimeError("db down")):
            try:
                self._resume(task)
            except RuntimeError:
                pass
        delay.assert_not_called()

    @patch("openai.images")
    @patch("apps.pipeline.services.claude_service.call_claude")
    @patch(_DELAY)
    def test_retry_calls_no_provider_synchronously(self, delay, claude,
                                                   images):
        delay.return_value.id = "celery-r5"
        task = self._task("failed")
        assert self._resume(task).status_code == 200
        claude.assert_not_called()
        images.edit.assert_not_called()
        images.generate.assert_not_called()

    @patch(_DELAY)
    def test_gate2_records_untouched_by_retry(self, delay):
        delay.return_value.id = "celery-r6"
        task = self._task("failed")
        GateDecision.objects.create(task=task, gate="gate_1",
                                    decision="approve",
                                    decided_by=self.user)
        before = list(GateDecision.objects.filter(task=task)
                      .values_list("id", "gate", "decision"))
        assert self._resume(task).status_code == 200
        after = list(GateDecision.objects.filter(task=task)
                     .values_list("id", "gate", "decision"))
        assert after == before
