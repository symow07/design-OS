"""Confirm Profile UI-2B-1 — polling controller and status panel (browser).

EventSource is disabled per test so the deterministic interval controller is
the transport under test: settle-then-schedule, one request in flight,
generation-token stale protection, terminal stop, bounded refresh retries,
and a status panel that never rebuilds for identical snapshots. The server's
POLL_AFTER_MS and the client's POLL_MIN_MS floor are shrunk per test so real
cadences stay observable without slow tests.
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase
from django.core.files.base import ContentFile

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    HAVE_PLAYWRIGHT = True
except ImportError:              # pragma: no cover
    HAVE_PLAYWRIGHT = False

from apps.core.models import Brand, Product
from apps.pipeline.models import (AgentLog, DesignTask, GateDecision,
                                  GeneratedImage, PackagingOutput)
from apps.pipeline.services import container_contract as cc
from apps.pipeline.services import reconstruction_status as rst

from .test_browser_profile_editor import PNG, _ProfileEditorFixtures

_START = "ARIA: container profile confirmed — reconstructing container .ai"
_DONE = "ARIA: reached Gate 2 — awaiting container approval"
_DELAY = "apps.pipeline.tasks.resume_aria_container_profile.delay"


class _ReconFixtures(_ProfileEditorFixtures):
    """Recon-task + status-page fixtures shared with the UI-2B-2B retry
    suite; no tests of its own."""

    def setUp(self):
        super().setUp()
        # fast, observable cadence: server suggests 400ms, client floor 200ms
        self._poll_patch = patch.object(rst, "POLL_AFTER_MS", 400)
        self._poll_patch.start()
        self.addCleanup(self._poll_patch.stop)

    # -- fixtures -------------------------------------------------------------

    def _recon_task(self, state="queued", target="product_container"):
        status = {"queued": "generating_dieline",
                  "running": "generating_dieline",
                  "dispatch_failed": "generating_dieline",
                  "failed": "awaiting_container_profile"}[state] \
            if target == "product_container" else "completed"
        product = Product.objects.create(
            brand=Brand.objects.first(),
            product_id=f"CO-R{next(self._PRODUCT_SEQ)}", name="Rosé",
            category="CO", year=2026, width_mm=35, depth_mm=25, height_mm=95)
        task = DesignTask.objects.create(
            brand=Brand.objects.first(), product=product,
            task_text="a serum bottle recon", status=status,
            design_target=target, created_by=self.user)
        img = GeneratedImage(task=task, direction_name="Rose")
        img.image_file.save("concept.png", ContentFile(PNG), save=True)
        record = cc.merge_product_record_dims(
            cc.build_inferred_profile("bottle", "slim"), product)
        spec = {"backend": "container", cc.PROFILE_SCHEMA: record,
                "container_profile": {"archetype": "bottle"},
                "container_confirmation": {
                    "combined_hash": "c0ffee" * 8, "confirmed_by": "uib4b",
                    "confirmed_at": "2026-08-01T00:00:00+00:00",
                    "authority": "HUMAN_CONFIRMED_CONCEPT_ONLY"},
                "container_resume": {
                    "celery_task_id": "celery-1",
                    "requested_at": "2026-08-01T00:00:01+00:00",
                    "requested_by": "uib4b", "kind": "INITIAL_CONFIRMATION"}}
        if state == "dispatch_failed":
            spec["generation_error"] = "RECONSTRUCTION_DISPATCH_FAILED"
        if state == "failed":
            spec["generation_error"] = \
                "backbone exploded at /Users/private/x.py"
        PackagingOutput.objects.create(task=task, approved_image=img,
                                       spec_sheet=spec)
        GateDecision.objects.create(task=task, gate="container_profile",
                                    decision="approve",
                                    decided_by=self.user)
        if state == "running":
            AgentLog.objects.create(task=task, agent_name="ARIA",
                                    action=_START)
        return task

    def _status_page(self, task):
        """Editor-free page tracking every /status/ request, with SSE off so
        the interval controller is the transport under test."""
        # [the owner's answer to the UI directions of 2026-09-25: the design's own page opens its design as it loads —
        # the listeners, the SSE switch and the short floor are all set BEFORE it opens]
        self.status_requests = []
        self.confirm_posts = []

        def listen(page):
            page.on("request", lambda r: self.status_requests.append(time.time())
                    if "/status/" in r.url else None)
            page.on("request", lambda r: self.confirm_posts.append(r.url)
                    if "confirm_container_profile" in r.url else None)
        return self._design_page(task, before=listen,
                                 extra_init="window.EventSource = undefined; window.POLL_MIN_MS = 200;")


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class ReconStatusBrowserTests(_ReconFixtures, DrainedStaticLiveServerTestCase):

    # -- rendering ------------------------------------------------------------

    def test_queued_renders_frozen_profile_and_honest_status(self):
        page = self._status_page(self._recon_task("queued"))
        page.wait_for_selector("#recon-status", state="attached")
        panel = " ".join(page.text_content(".recon-status-panel").split())
        assert "Waiting to be drawn" in panel
        assert "dispatched (INITIAL_CONFIRMATION)" in panel
        assert "has not finished yet" in panel
        assert "The editable file: not ready yet" in panel
        assert "its picture: not ready yet" in panel
        assert "%" not in panel                       # no fabricated numbers
        assert page.eval_on_selector_all(
            ".recon-progress", "els => els.length") == 1
        assert page.eval_on_selector(
            "#recon-status", "el => el.getAttribute('role')") == "status"
        # frozen profile stays; the editable editor never returns
        body = page.text_content("#profile-view")
        # [B1, the clean-up of 2026-10-04] the badge says who confirmed it — here the viewer, uib4b, did
        assert "Confirmed by you — for the design, not for manufacture" in body
        assert page.eval_on_selector_all(
            "#archetype-cards", "els => els.length") == 0

    def test_running_state_shows_no_fabricated_phase(self):
        page = self._status_page(self._recon_task("running"))
        page.wait_for_selector("#recon-status", state="attached")
        panel = " ".join(page.text_content(".recon-status-panel").split())
        assert "Being drawn" in panel
        assert "phase" not in panel.lower()           # none persisted → none shown
        assert "%" not in panel
        assert "started" in panel                     # real persisted evidence

    def test_worker_failure_renders_code_and_stops(self):
        task = self._recon_task("failed")
        page = self._status_page(task)
        page.wait_for_selector("#recon-status", state="attached")
        panel = page.text_content(".recon-status-panel")
        assert "The drawing did not finish" in panel
        assert "RECONSTRUCTION_FAILED" in panel
        assert "[path removed]" in panel
        assert "/Users/" not in panel
        # UI-2B-2B: recovery goes through the reviewed retry dialog — the
        # eligibility-gated opener replaces the old direct Resume button
        assert page.eval_on_selector_all(
            "#open-retry-dialog", "els => els.length") == 1
        # awaiting_container_profile is not a working status: no polling loop
        page.wait_for_timeout(1500)
        assert len(self.status_requests) == 1

    def test_his_122_the_stop_is_said_in_plain_words_in_view_its_codes_kept_in_the_fold(self):
        """[His test blocker on design 122 at reconstruction, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md), item 3: "The stop
        reason must be shown in plain words on the page, never only codes in a fold."] 122's own stop, as its record
        wrote it: each reason in words, in view; the codes only in the folded record."""
        task = self._recon_task("failed")
        out = task.packaging_outputs.first()
        out.spec_sheet = dict(out.spec_sheet, generation_error=(
            "CONTAINER_NATIVE_RECONSTRUCTION_FAILED: CONTAINER_PRODUCT_NAME_TOO_SMALL; "
            "CONTAINER_FRONT_BACK_RELATIONSHIP_FAILED"))
        out.save()
        page = self._status_page(task)
        page.wait_for_selector(".stop-reasons li", state="visible")
        reasons = [" ".join(t.split()) for t in page.locator(".stop-reasons li").all_text_contents()]
        assert reasons == [
            "The product name was not drawn on the front as the name, or it was drawn smaller than the print floor "
            "allows.",
            "The front does not carry the hero — neither the product name nor the concept's motif — or the back "
            "carries the hero motif."], reasons
        assert page.locator(".stop-reasons-head").is_visible()
        assert "_" not in " ".join(reasons)
        folded = page.locator(".recon-error details.tech")
        assert not folded.evaluate("d => d.open") and "CONTAINER_PRODUCT_NAME_TOO_SMALL" in folded.text_content()

    # -- polling behavior -----------------------------------------------------

    def test_terminal_snapshot_never_starts_polling(self):
        # dispatch_failed sits in a WORKING task status, but the initial
        # snapshot is already terminal — loadTask's terminal guard means the
        # loop never even starts: one request total, zero wasted ticks
        page = self._status_page(self._recon_task("dispatch_failed"))
        page.wait_for_selector("#recon-status", state="attached")
        page.wait_for_timeout(2000)
        assert len(self.status_requests) == 1
        panel = page.text_content(".recon-status-panel")
        assert "RECONSTRUCTION_DISPATCH_FAILED" in panel

    def test_queued_task_keeps_polling_on_cadence_single_flight(self):
        task = self._recon_task("queued")
        page = self._status_page(task)
        page.wait_for_selector("#recon-status", state="attached")
        page.wait_for_timeout(2200)
        count = len(self.status_requests)
        assert count >= 3                             # cadence is alive
        # settle-then-schedule: consecutive request STARTS are separated by
        # at least the clamped interval — overlapping requests would violate
        gaps = [b - a for a, b in zip(self.status_requests,
                                      self.status_requests[1:])]
        assert all(g >= 0.18 for g in gaps), gaps

    def test_unconfirmed_editor_and_packaging_do_not_poll(self):
        page = self._status_page(self._gate_task())   # unconfirmed editor
        page.wait_for_selector("#archetype-cards .archetype-card",
                               state="attached")
        page.wait_for_timeout(1500)
        assert len(self.status_requests) == 1
        pkg = DesignTask.objects.create(
            brand=Brand.objects.first(), task_text="a carton",
            design_target="packaging", status="completed",
            created_by=self.user)
        # [2026-09-25: opening another design from a design's page opens that design's own page]
        with page.expect_response(lambda r: f"/api/tasks/{pkg.id}/status/" in r.url):
            page.evaluate(f"loadTask({pkg.id})")
        assert page.url.endswith(f"/dashboard/designs/{pkg.id}/")
        assert page.evaluate("window.OPEN_TASK_ID") == pkg.id     # the page itself is the other design's — its header too
        page.wait_for_selector("#review-board .rb-project", state="attached")
        before = len(self.status_requests)
        page.wait_for_timeout(1500)
        assert len(self.status_requests) == before    # no packaging polling

    def test_switching_tasks_makes_stale_responses_inert(self):
        # [the owner's answer to the UI directions of 2026-09-25: switching designs opens the other design's own page,
        # so a late response of the first can never paint it — the same claim, now held by the page itself]
        a = self._recon_task("queued")
        b = self._recon_task("failed")
        page = self._status_page(a)
        page.wait_for_selector("#recon-status", state="attached")
        # slow down ONLY task A's status responses so one is in flight when
        # the owner switches to task B
        page.route(f"**/api/tasks/{a.id}/status/**", lambda r: (
            time.sleep(1.2), r.continue_()))
        page.wait_for_timeout(300)                    # A's next request in flight
        with page.expect_response(lambda r: f"/api/tasks/{b.id}/status/" in r.url):
            page.evaluate(f"loadTask({b.id})")
        assert page.evaluate("window.OPEN_TASK_ID") == b.id
        page.wait_for_selector("#recon-status", state="attached")
        page.wait_for_timeout(1800)                   # A's response lands late
        # B's failed panel is showing; A's queued snapshot never painted it
        panel = page.text_content(".recon-status-panel")
        assert "The drawing did not finish" in panel
        assert "Waiting to be drawn" not in panel
        assert page.text_content("#task-title").startswith(
            "a serum bottle recon")

    def test_reopening_the_same_task_runs_one_loop(self):
        task = self._recon_task("queued")
        page = self._status_page(task)
        page.wait_for_selector("#recon-status", state="attached")
        page.evaluate(f"loadTask({task.id})")         # reopen, same task
        page.wait_for_timeout(1500)
        gaps = [b - a for a, b in zip(self.status_requests,
                                      self.status_requests[1:])]
        # a doubled loop would produce near-zero gaps between ticks
        assert all(g >= 0.15 for g in gaps[2:]), gaps

    def test_refresh_failure_notes_not_reconstruction_failure(self):
        task = self._recon_task("queued")
        page = self._status_page(task)
        page.wait_for_selector("#recon-status", state="attached")
        # after the first good snapshot, every status request dies
        page.route("**/status/**", lambda r: r.abort())
        page.wait_for_selector("#recon-refresh-note:not([hidden])",
                               timeout=5000)
        note = page.text_content("#recon-refresh-note")
        assert "could not be refreshed" in note
        assert "confirmed profile remains recorded" in note
        assert "STATUS_REFRESH_FAILED" in note
        # the lifecycle label still says QUEUED — polling failure is never
        # reported as reconstruction failure
        assert "Waiting to be drawn" in \
            page.text_content("#recon-status")
        # bounded retry: the controller gives up after the limit
        before = len(self.status_requests)
        page.wait_for_timeout(2500)
        retries = len(self.status_requests) - before
        assert retries <= 4                            # limit 3 (+ timing slack)

    def test_identical_snapshots_do_not_rebuild_the_panel(self):
        task = self._recon_task("queued")
        page = self._status_page(task)
        page.wait_for_selector("#recon-status", state="attached")
        page.eval_on_selector("#recon-status", "el => { el._marked = 42; }")
        page.wait_for_timeout(1500)                                # several poll cycles
        assert len(self.status_requests) >= 3
        assert page.eval_on_selector(
            "#recon-status", "el => el._marked") == 42

    def test_refresh_restores_confirmed_state_from_server(self):
        task = self._recon_task("queued")
        page = self._status_page(task)
        page.wait_for_selector("#recon-status", state="attached")
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("#panel-center", state="attached")  # [the owner's answer to the UI directions of 2026-09-25: the reload lands on the design's own page, C's design page, which opens the design itself]
        page.wait_for_selector("#recon-status", state="attached")
        assert page.eval_on_selector_all(
            "#archetype-cards", "els => els.length") == 0
        assert "Waiting to be drawn" in \
            page.text_content("#recon-status")

    def test_polling_confirms_nothing_and_calls_nothing(self):
        task = self._recon_task("queued")
        decisions_before = GateDecision.objects.count()
        with patch(_DELAY) as delay, \
             patch("apps.pipeline.services.claude_service.call_claude") as cl, \
             patch("openai.images") as images:
            page = self._status_page(task)
            page.wait_for_selector("#recon-status", state="attached")
            page.wait_for_timeout(1600)
            delay.assert_not_called()
            cl.assert_not_called()
            images.edit.assert_not_called()
            images.generate.assert_not_called()
        assert self.confirm_posts == []
        assert GateDecision.objects.count() == decisions_before
        task.refresh_from_db()
        assert task.status == "generating_dieline"
