"""Confirm Profile UI-2B-2B — retry dialog and recovery (browser).

The retry control renders only from server eligibility; the reviewed dialog
is the single door to the resume POST (reuse statements, failure code, gate
decision identity, focus discipline); an accepted retry dispatches once,
renders QUEUED and resumes polling; recovery completes into the result +
Gate-2 continuity; and every non-eligible state — refresh failure, optional
PNG absence, clean completion, technical intervention — exposes no retry.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase
from django.core.files.base import ContentFile

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    HAVE_PLAYWRIGHT = True
except ImportError:              # pragma: no cover
    HAVE_PLAYWRIGHT = False

from apps.pipeline.models import AgentLog, GateDecision

from .test_browser_profile_editor import PNG
from .test_browser_recon_status import _DELAY, _DONE, _ReconFixtures

AI_BYTES = b"%PDF-1.4\n" + b"x" * 600


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class RetryRecoveryBrowserTests(_ReconFixtures, DrainedStaticLiveServerTestCase):

    def _failed_page(self, task=None):
        task = task or self._recon_task("failed")
        page = self._status_page(task)
        page.wait_for_selector("#open-retry-dialog", state="attached")
        return task, page

    def _open_dialog(self, page):
        page.click("#open-retry-dialog")
        page.wait_for_selector("#retry-dialog[open]")

    # -- eligibility-gated control ---------------------------------------------

    def test_dialog_states_reuse_and_no_new_gate(self):
        task, page = self._failed_page()
        self._open_dialog(page)
        assert self.confirm_posts == []           # opening sends nothing
        text = " ".join(page.text_content("#retry-dialog").split())
        assert "The shape you confirmed will not change" in text
        assert "no new decision is recorded" in text
        assert "is used as it stands" in text
        assert "What the failed attempt left stays in its history" in text
        assert "The design is drawn again from the same shape" in text
        assert "does not create any manufacturing authority" in text
        assert "RECONSTRUCTION_FAILED" in text
        decision = GateDecision.objects.filter(task=task).first()
        assert f"#{decision.id}" in text
        assert page.evaluate("document.activeElement.id") == "rtd-cancel"

    def test_cancel_review_escape_send_nothing_and_trap_focus(self):
        task, page = self._failed_page()
        self._open_dialog(page)
        for _ in range(4):
            page.keyboard.press("Tab")
            assert page.evaluate(
                "document.activeElement.closest('#retry-dialog') !== null")
        page.click("#rtd-cancel")
        assert page.eval_on_selector("#retry-dialog", "d => d.open") is False
        assert page.evaluate("document.activeElement.id") == \
            "open-retry-dialog"
        self._open_dialog(page)
        page.click("#rtd-review")
        assert page.evaluate(
            "document.activeElement.classList.contains("
            "'confirmed-profile-summary')") is True
        self._open_dialog(page)
        page.keyboard.press("Escape")
        assert page.eval_on_selector("#retry-dialog", "d => d.open") is False
        assert self.confirm_posts == []
        assert GateDecision.objects.filter(task=task).count() == 1

    def test_no_retry_for_refresh_failure_png_absence_or_clean_result(self):
        # 1. clean completed (with artifacts) → no retry control
        completed = self._recon_task("queued")
        out = completed.packaging_outputs.first()
        out.design_preview_ai.save("t.ai", ContentFile(AI_BYTES), save=True)
        out.design_preview.save("t.png", ContentFile(PNG), save=True)
        type(completed).objects.filter(pk=completed.pk).update(
            status="awaiting_gate_2")
        AgentLog.objects.create(task=completed, agent_name="ARIA",
                                action=_DONE)
        page = self._status_page(completed)
        page.wait_for_selector(".recon-result", state="attached")
        assert page.eval_on_selector_all(
            "#open-retry-dialog", "els => els.length") == 0
        page.close()
        # 2. optional PNG absent → still completed, still no retry
        out.design_preview.delete(save=True)
        page = self._status_page(completed)
        page.wait_for_selector(".recon-result", state="attached")
        assert "No picture was saved" in page.text_content(".recon-png-card")  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]
        assert page.eval_on_selector_all(
            "#open-retry-dialog", "els => els.length") == 0
        # AI download still offered
        assert page.eval_on_selector_all(
            '.recon-ai-card a[aria-label^="Download AI source"]',
            "els => els.length") == 1
        page.close()
        # 3. status-refresh failure on an ACTIVE task → note, never a retry
        active = self._recon_task("queued")
        page = self._status_page(active)
        page.wait_for_selector("#recon-status", state="attached")
        page.route("**/status/**", lambda r: r.abort())
        page.wait_for_selector("#recon-refresh-note:not([hidden])",
                               timeout=5000)
        assert page.eval_on_selector_all(
            "#open-retry-dialog", "els => els.length") == 0
        assert "STATUS_REFRESH_FAILED" in \
            page.text_content("#recon-refresh-note")

    def test_technical_intervention_has_no_retry_button(self):
        task = self._recon_task("queued")
        out = task.packaging_outputs.first()
        out.design_preview_ai.name = "../../.env"
        out.save(update_fields=["design_preview_ai"])
        type(task).objects.filter(pk=task.pk).update(status="awaiting_gate_2")
        page = self._status_page(task)
        page.wait_for_selector("#recon-status", state="attached")
        panel = page.text_content(".recon-status-panel")
        assert "TECHNICAL_INTERVENTION_REQUIRED" in panel
        assert "RECONSTRUCTION_ARTIFACT_INVALID" in panel
        assert page.eval_on_selector_all(
            "#open-retry-dialog", "els => els.length") == 0
        assert "/Users/" not in panel and "/media/" not in panel

    # -- dispatch ---------------------------------------------------------------

    def test_retry_dispatches_once_renders_queued_and_resumes_polling(self):
        task, page = self._failed_page()
        with patch(_DELAY) as delay, \
             patch("apps.pipeline.services.claude_service.call_claude") as cl, \
             patch("openai.images") as images:
            delay.return_value.id = "celery-live"
            self._open_dialog(page)
            page.evaluate("""
              (() => {
                const b = document.getElementById('rtd-retry');
                b.click(); b.click();
              })()
            """)
            page.wait_for_selector("#recon-status", state="attached")
            page.wait_for_function(
                "document.getElementById('recon-status')"
                ".textContent.includes('Waiting to be drawn')")
            assert delay.call_count == 1          # double click, one dispatch
            cl.assert_not_called()
            images.edit.assert_not_called()
            # polling resumed exactly once: /status/ requests keep arriving
            before = len(self.status_requests)
            page.wait_for_timeout(1200)
            assert len(self.status_requests) > before
        assert len(self.confirm_posts) == 1       # exactly one POST
        assert GateDecision.objects.filter(task=task).count() == 1
        task.refresh_from_db()
        assert task.status == "generating_dieline"
        # the confirmed values remain on screen, unchanged
        body = page.text_content("#profile-view")
        assert "95 mm" in body and "35 mm" in body

    def test_retry_request_failure_preserves_the_failed_state(self):
        task, page = self._failed_page()
        page.route("**/confirm_container_profile/", lambda r: r.fulfill(
            status=500, content_type="application/json",
            body='{"error": "SERVER_ERROR"}'))
        self._open_dialog(page)
        page.click("#rtd-retry")
        page.wait_for_function(
            "document.getElementById('profile-msg').textContent.length > 3")
        assert "The drawing did not finish" in \
            page.text_content(".recon-status-panel")
        task.refresh_from_db()
        assert task.status == "awaiting_container_profile"

    def test_network_loss_reconciles_through_status(self):
        task, page = self._failed_page()
        page.route("**/confirm_container_profile/", lambda r: r.abort())
        self._open_dialog(page)
        page.click("#rtd-retry")
        page.wait_for_function(
            "document.getElementById('profile-msg').textContent"
            ".includes('you can retry again')")
        # nothing was dispatched; the state is unchanged and still eligible
        task.refresh_from_db()
        assert task.status == "awaiting_container_profile"
        assert GateDecision.objects.filter(task=task).count() == 1

    def test_recovery_completes_into_result_and_gate2(self):
        task, page = self._failed_page()
        with patch(_DELAY) as delay:
            delay.return_value.id = "celery-live"
            self._open_dialog(page)
            page.click("#rtd-retry")
            page.wait_for_function(
                "document.getElementById('recon-status')"
                ".textContent.includes('Waiting to be drawn')")
        # simulate the worker finishing (persisted success + artifacts)
        out = task.packaging_outputs.first()
        out.design_preview_ai.save(f"container_task_{task.id}.ai",
                                   ContentFile(AI_BYTES), save=True)
        out.design_preview.save(f"container_task_{task.id}.png",
                                ContentFile(PNG), save=True)
        type(task).objects.filter(pk=task.pk).update(status="awaiting_gate_2")
        AgentLog.objects.create(task=task, agent_name="ARIA", action=_DONE)
        # the next poll renders the recovered completion
        page.wait_for_selector(".recon-result", state="attached")
        body = " ".join(page.text_content("#profile-view").split())
        assert page.text_content("#recon-status").strip() == "Drawn"  # [the owner's goal of 2026-09-25, (d): the same claim, in the plain words the page now says]
        # VQR-2A: the recovered completion has no measurable quality
        # evidence, so the AI presents as inspection-only
        # [§BH71 (0a), the owner's goal of 2026-09-28: evidence not measured is a warning beside Approve, never a
        # block — it read "For looking only"; the recovered file is the design]
        assert "For looking only" not in body and "The editable file" in body
        # Gate-2 continuity: the gate surface renders beside the result
        # (as the visual-quality blocked panel), no retry button
        assert page.eval_on_selector(
            "#gate2-state", "el => getComputedStyle(el).display") != "none"
        assert page.eval_on_selector_all(
            "#open-retry-dialog", "els => els.length") == 0
        assert GateDecision.objects.filter(
            task=task, gate="container_profile").count() == 1
        # refresh restores the recovered result with zero POSTs
        posts_before = len(self.confirm_posts)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("#panel-center", state="attached")  # [the owner's answer to the UI directions of 2026-09-25: the reload lands on the design's own page, C's design page, which opens the design itself]
        page.wait_for_selector(".recon-result", state="attached")
        assert len(self.confirm_posts) == posts_before
        html = page.eval_on_selector("#profile-view", "el => el.innerHTML")
        assert "/media/" not in html and "/files/" not in html
