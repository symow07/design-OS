"""Confirm Profile UI-2B-2A — reconstruction result presentation (browser).

A cleanly completed container task shows its frozen confirmed profile plus
the Reconstruction Result beside the existing Gate-2 approval UI: the PNG
genuinely loads through the authorized role-addressed endpoint (naturalWidth
proven), the .AI is a download-only SOURCE OF TRUTH card that never enters
an <img>, missing artifacts degrade honestly (PREVIEW_UNAVAILABLE / no
fabricated result), refreshes and task switches stay read-only and
stale-safe, and no raw storage URL appears anywhere.
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

from apps.core.models import Brand, Product
from apps.pipeline.models import (AgentLog, DesignTask, GateDecision,
                                  GeneratedImage, PackagingOutput)
from apps.pipeline.services import container_contract as cc

from .test_browser_profile_editor import PNG, _ProfileEditorFixtures
from .test_browser_recon_status import _DELAY, _DONE, _START

MOBILE = {"width": 390, "height": 844}
AI_BYTES = b"%PDF-1.4\n" + b"x" * 600


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class ReconResultBrowserTests(_ProfileEditorFixtures,
                              DrainedStaticLiveServerTestCase):

    def _completed_task(self, png=True, ai=True, ai_name=None):
        product = Product.objects.create(
            brand=Brand.objects.first(),
            product_id=f"CO-C{next(self._PRODUCT_SEQ)}", name="Rosé",
            category="CO", year=2026, width_mm=35, depth_mm=25, height_mm=95)
        task = DesignTask.objects.create(
            brand=Brand.objects.first(), product=product,
            task_text="a completed serum bottle", status="awaiting_gate_2",
            design_target="product_container", created_by=self.user)
        img = GeneratedImage(task=task, direction_name="Rose")
        img.image_file.save("concept.png", ContentFile(PNG), save=True)
        record = cc.merge_product_record_dims(
            cc.build_inferred_profile("bottle", "slim"), product)
        out = PackagingOutput.objects.create(
            task=task, approved_image=img,
            spec_sheet={"backend": "container", cc.PROFILE_SCHEMA: record,
                        "container_profile": {"archetype": "bottle"},
                        "container_fidelity_report": {"state": "recorded"},
                        "container_confirmation": {
                            "combined_hash": "c0ffee" * 8,
                            "confirmed_by": "uib4b",
                            "confirmed_at": "2026-08-01T00:00:00+00:00",
                            "authority": "HUMAN_CONFIRMED_CONCEPT_ONLY"},
                        "container_resume": {
                            "celery_task_id": "celery-1",
                            "requested_at": "2026-08-01T00:00:01+00:00",
                            "requested_by": "uib4b",
                            "kind": "INITIAL_CONFIRMATION"}})
        if ai:
            out.design_preview_ai.save(ai_name or f"container_task_{task.id}.ai",
                                       ContentFile(AI_BYTES), save=True)
        if png:
            out.design_preview.save(f"container_task_{task.id}.png",
                                    ContentFile(PNG), save=True)
        GateDecision.objects.create(task=task, gate="container_profile",
                                    decision="approve", decided_by=self.user)
        AgentLog.objects.create(task=task, agent_name="ARIA", action=_START)
        AgentLog.objects.create(task=task, agent_name="ARIA", action=_DONE)
        return task

    def _result_page(self, task, viewport=None):
        # [the owner's answer to the UI directions of 2026-09-25: the result is drawn on the design's own page — no queue
        # drawer to close; the listeners are attached before the page opens its design]
        self.confirm_posts = []
        self.status_requests = []

        def listen(page):
            page.on("request", lambda r: self.confirm_posts.append(r.url)
                    if "confirm_container_profile" in r.url else None)
            page.on("request", lambda r: self.status_requests.append(r.url)
                    if "/status/" in r.url else None)
        return self._design_page(task, viewport=viewport, before=listen)

    # -- presentation ---------------------------------------------------------

    def test_the_review_says_its_record_in_words_and_keeps_its_codes_folded(self):
        # [the owner's goal of 2026-09-25, (d): "Plain words everywhere. No engine codes on screen." — read through what
        # the page SHOWS (innerText skips a closed fold); every code is still on the page, folded under its record]
        import hashlib
        import re
        from datetime import datetime, timezone as tz

        from django.test import override_settings

        from apps.dashboard.models import DesignAcceptance
        task = self._completed_task()
        out = task.packaging_outputs.first()
        sha = hashlib.sha256(PNG).hexdigest()
        DesignAcceptance.objects.create(
            task=task, output=out, decision="REJECTED", decided_by=self.user,
            decided_at=datetime(2026, 9, 25, 15, 47, tzinfo=tz.utc), preview_sha256=sha,
            preview_name=out.design_preview.name)
        with override_settings(OWNER_ACCOUNT=self.user.get_username()):
            page = self._result_page(task)
            page.wait_for_selector(".recon-result", state="attached")
            page.wait_for_selector(".gate2-records", state="attached")
            shown = " ".join((page.inner_text("#profile-view") + " "
                              + page.inner_text("#gate2-state")).split())
            kept = " ".join((page.text_content("#profile-view") + " "
                             + page.text_content("#gate2-state")).split())
        # the confirmed form by the editor's names, and only the proportions a bottle has
        assert "Form Bottle" in shown and "Archetype" not in shown
        # [his goal of 2026-10-13, (5): "Merge "Accept this design" and "Approve" into one "Approve""] what Approve
        # records said in one quiet line beside it; his decisions folded, each in words — the picture's sha256 kept
        assert "Approving records your account, the time and the drawing's own fingerprint" in shown
        assert "Your decisions on this design (1)" in shown
        assert "the picture is still exactly the one decided on" in kept and "Changes asked for" in kept
        assert sha not in shown and sha in kept
        # no machine time, no media type, no validation state on screen — all of them kept
        assert not re.search(r"\d{4}-\d\d-\d\dT\d\d:\d\d", shown), shown
        assert "application/" not in shown and "validation " not in shown
        assert "validation " in kept
        assert not re.search(r"\b[A-Z]{3,}_[A-Z_]{3,}\b", shown), re.findall(r"\b[A-Z]{3,}_[A-Z_]{3,}\b", shown)

    def test_finding1_the_header_and_the_badge_say_one_spent_number_as_the_ledger_grows(self):
        # his test day finding 1 (2026-09-29, design 116): the header said "$0.01 spent" — written once, when the page
        # opened — while the badge, written on every refresh, said "$0.64". One number, the true one: the ledger's sum
        from decimal import Decimal

        from apps.pipeline.models import ApiCallRecord
        task = self._completed_task()
        ApiCallRecord.objects.create(task=task, provider="anthropic", model="m", operation="inspiration_read",
                                     cost_usd=Decimal("0.009012"))
        page = self._result_page(task)
        page.wait_for_selector(".recon-result", state="attached")
        assert page.inner_text("#task-spent") == "$0.01 spent"
        ApiCallRecord.objects.create(task=task, provider="anthropic", model="m", operation="creative_directions",
                                     cost_usd=Decimal("0.630061"))
        page.evaluate(f"loadTask({task.id})")
        page.wait_for_function("document.getElementById('task-spent').textContent === '$0.64 spent'")
        assert "$0.64" in page.inner_text("#task-status-badge")

    def test_completed_renders_profile_result_and_gate2_together(self):
        task = self._completed_task()
        page = self._result_page(task)
        page.wait_for_selector(".recon-result", state="attached")
        body = " ".join(page.text_content("#profile-view").split())
        # [B1, the clean-up of 2026-10-04] the badge says who confirmed it — here the viewer, uib4b, did
        assert "Confirmed by you — for the design, not for manufacture" in body
        assert "The drawing's files" in body
        # [§BH71 (0a), the owner's goal of 2026-09-28: "Unmeasured checks … show as a warning beside Approve, never
        # a block." This fixture has no measurable quality evidence: it read "For looking only", "Not yet passed
        # its quality check" and "it is not artwork you have approved" — a failed reconstruction for inspection
        # only; nothing measured failed, so its file is the design and Approve is drawn, the checks not measured
        # yet said beside it (test_browser_vqr2a_quality)]
        assert "For looking only" not in body and "Not yet passed its quality check" not in body
        assert "The editable file" in body
        assert "A picture of it" in body
        assert "container_task_" in body and ".ai" in body
        assert "it is not artwork you have approved" not in body
        # §15 continuity: the existing Gate-2 approval UI still shows
        assert page.eval_on_selector(
            "#gate2-state", "el => getComputedStyle(el).display") != "none"
        assert page.text_content("#recon-status").strip() == "Drawn"  # [the owner's goal of 2026-09-25, (d): the same claim, in the plain words the page now says]

    def test_png_loads_through_the_authorized_endpoint(self):
        task = self._completed_task()
        page = self._result_page(task)
        img = page.wait_for_selector(".recon-preview-img")
        src = img.get_attribute("src")
        assert f"/api/tasks/{task.id}/reconstruction-artifact/png/" in src
        assert "/media/" not in src and "/files/" not in src
        page.wait_for_function(
            "document.querySelector('.recon-preview-img').naturalWidth > 0")
        assert page.eval_on_selector(
            ".recon-preview-img",
            "i => getComputedStyle(i).objectFit") == "contain"
        assert img.get_attribute("alt") == \
            "The drawn design, as a picture"

    def test_ai_is_download_only_never_an_img(self):
        task = self._completed_task()
        page = self._result_page(task)
        page.wait_for_selector(".recon-ai-card", state="attached")
        assert page.eval_on_selector(
            ".recon-ai-card", "el => el.querySelectorAll('img').length") == 0
        href = page.eval_on_selector(
            '.recon-ai-card a[aria-label^="Download AI source"]',
            "a => a.getAttribute('href')")
        assert href == (f"/api/tasks/{task.id}/reconstruction-artifact/ai/"
                        "?download=1")
        html = page.eval_on_selector("#profile-view", "el => el.innerHTML")
        assert "/media/" not in html and "/files/" not in html

    def test_refresh_restores_result_without_posts_or_dispatch(self):
        task = self._completed_task()
        with patch(_DELAY) as delay:
            page = self._result_page(task)
            page.wait_for_selector(".recon-result", state="attached")
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector("#panel-center", state="attached")  # [the owner's answer to the UI directions of 2026-09-25: the reload lands on the design's own page, C's design page, which opens the design itself]
            page.wait_for_selector(".recon-result", state="attached")
            delay.assert_not_called()
        assert self.confirm_posts == []
        assert GateDecision.objects.filter(task=task).count() == 1

    def test_switching_tasks_never_paints_a_stale_result(self):
        completed = self._completed_task()
        editor_task = self._gate_task()
        page = self._result_page(completed)
        page.wait_for_selector(".recon-result", state="attached")
        # [2026-09-25: opening another design from a design's page opens that design's own page — its step is never
        # drawn under the first design's header]
        with page.expect_response(lambda r: f"/api/tasks/{editor_task.id}/status/" in r.url):
            page.evaluate(f"loadTask({editor_task.id})")
        assert page.url.endswith(f"/dashboard/designs/{editor_task.id}/")
        assert page.evaluate("window.OPEN_TASK_ID") == editor_task.id   # the page itself is the other design's
        page.wait_for_selector("#archetype-cards .archetype-card",
                               state="attached")
        assert page.eval_on_selector_all(
            ".recon-result", "els => els.length") == 0

    # -- degraded artifacts ----------------------------------------------------

    def test_missing_png_shows_preview_unavailable_ai_intact(self):
        task = self._completed_task(png=False)
        page = self._result_page(task)
        page.wait_for_selector(".recon-result", state="attached")
        panel = page.text_content(".recon-png-card")
        assert "No picture was saved" in panel  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]
        assert "still good" in panel  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]
        assert page.eval_on_selector_all(
            ".recon-preview-img", "els => els.length") == 0
        # [§BH71 (0a): the AI card intact — it read "For looking only"; a fixture that measures nothing is not]
        assert "The editable file" in page.text_content(".recon-ai-card")

    def test_deleted_png_storage_degrades_server_side(self):
        # a missing storage object is caught by the CONTRACT's availability
        # stat: the card renders the static PREVIEW_UNAVAILABLE branch and
        # no <img> is emitted at all
        task = self._completed_task()
        out = task.packaging_outputs.first()
        out.design_preview.storage.delete(out.design_preview.name)
        page = self._result_page(task)
        page.wait_for_selector(".recon-result", state="attached")
        assert page.eval_on_selector_all(
            ".recon-preview-img", "els => els.length") == 0
        assert "No picture was saved" in \
            page.text_content(".recon-png-card")  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]
        assert "The editable file" in page.text_content(".recon-ai-card")      # [§BH71 (0a): it read "For looking only"]

    def test_midflight_png_failure_falls_back_client_side(self):
        # storage intact, but the preview fetch fails in the browser — the
        # inline onerror swaps in the honest fallback without touching the
        # valid AI card or persisted state. The failure is induced by
        # repointing the live img at a 404 target (route interception of
        # this panel's own img load proved unreliable in this Playwright
        # build, while the same handler fires fine on a request error).
        task = self._completed_task()
        page = self._result_page(task)
        page.wait_for_selector(".recon-preview-img", state="attached")
        page.wait_for_function(
            "document.querySelector('.recon-preview-img').complete")
        page.eval_on_selector(
            ".recon-preview-img",
            f"i => {{ i.src = '/api/tasks/{task.id}"
            f"/reconstruction-artifact/missing-role/'; }}")
        page.wait_for_selector(".recon-preview-fallback:not([hidden])",
                               timeout=5000)
        assert "could not be loaded" in \
            page.text_content(".recon-preview-fallback")  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]
        assert page.eval_on_selector(
            ".recon-preview-img", "i => i.hidden") is True
        assert "The editable file" in page.text_content(".recon-ai-card")      # [§BH71 (0a): it read "For looking only"]
        task.refresh_from_db()
        assert task.status == "awaiting_gate_2"

    def test_missing_ai_shows_inconsistency_not_a_result(self):
        task = self._completed_task(ai=False)
        page = self._result_page(task)
        page.wait_for_selector("#recon-status", state="attached")
        assert page.eval_on_selector_all(
            ".recon-result", "els => els.length") == 0
        assert "RECONSTRUCTION_STATUS_INCONSISTENT" in \
            page.text_content(".recon-status-panel")

    # -- read-only, no polling, providers ---------------------------------------

    def test_completed_task_does_not_poll(self):
        task = self._completed_task()
        page = self._result_page(task)
        page.wait_for_selector(".recon-result", state="attached")
        page.wait_for_timeout(1500)
        assert len(self.status_requests) == 1

    @patch("openai.images")
    @patch("apps.pipeline.services.claude_service.call_claude")
    def test_viewing_calls_no_provider(self, claude, images):
        task = self._completed_task()
        page = self._result_page(task)
        page.wait_for_selector(".recon-result", state="attached")
        page.wait_for_function(
            "document.querySelector('.recon-preview-img').naturalWidth > 0")
        claude.assert_not_called()
        images.edit.assert_not_called()
        images.generate.assert_not_called()

    # -- accessibility + responsive ---------------------------------------------

    def test_actions_are_keyboard_reachable_with_specific_names(self):
        task = self._completed_task()
        page = self._result_page(task)
        page.wait_for_selector(".recon-result", state="attached")
        labels = page.eval_on_selector_all(
            ".recon-artifact-actions a",
            "els => els.map(a => a.getAttribute('aria-label'))")
        assert any(lab.startswith("Download AI source") for lab in labels)
        assert any(lab.startswith("Open PNG preview") for lab in labels)
        page.focus('.recon-ai-card a[aria-label^="Download AI source"]')
        assert page.evaluate(
            "document.activeElement.getAttribute('aria-label')"
        ).startswith("Download AI source")

    def test_mobile_390_contains_everything(self):
        long_name = ("container_task_extremely_long_artifact_name_"
                     + "x" * 60 + ".ai")
        task = self._completed_task(ai_name=long_name)
        page = self._result_page(task, viewport=MOBILE)
        page.wait_for_selector(".recon-result", state="attached")
        assert page.evaluate(
            "document.documentElement.scrollWidth <= "
            "document.documentElement.clientWidth") is True
        assert page.evaluate("""
          (() => {
            const card = document.querySelector('.recon-ai-card')
                                 .getBoundingClientRect();
            const name = document.querySelector('.recon-artifact-name')
                                 .getBoundingClientRect();
            return name.right <= card.right + 1 && name.left >= card.left - 1;
          })()
        """) is True


# ====================================================================================================================
# — kept in this declared suite (a new test file is a manifest commit of its own: the gate-axis arc's lesson).
# [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), B. SIMPLE, CALM INTERFACE (for every page and type):
# 
# (3) "Resume this design / Not moving?" appears ONLY when the design has truly stopped (no progress for well past its
#     usual time, or a failure). Never while it's working, waiting for me, or done.
# (4) No browser pop-ups anywhere ("127.0.0.1 says…"). Any confirmation happens inside the page, in plain words, in the
#     house style.
# (5) ONE clear primary button per step. Merge "Accept this design" and "Approve" into one "Approve"; one "Download" (the
#     layered .ai, with other formats in a small menu); never two buttons that mean the same thing. Secondary actions are
#     small and quiet; technical details fold away.
# (6) SEE THE DESIGN ON THE PAGE: show each drawing (outside, inside, lid, tray, back label, plates) large, with
#     click-to-enlarge, zoom and pan, so I never need to open the file to see it."]
# 
# Each read through the page as he uses it — its own scripts, its own server — and the server's own answers.
# ====================================================================================================================
import os  # noqa: E402 — the calm page's tests, appended to this declared suite
import re
import tempfile
from datetime import timedelta

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone

from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    HAVE_PLAYWRIGHT = True
except ImportError:              # pragma: no cover
    HAVE_PLAYWRIGHT = False

from apps.core.models import Brand
from apps.pipeline.models import AgentLog, DesignTask

from .test_browser_profile_editor import _ProfileEditorFixtures


def _drawing_pdf() -> bytes:
    """A two-page drawing, as the composer draws one: a rose panel and a band on its first page, its inside on the
    second."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, Rect, SolidFill
    doc = Document(page_w=120.0, page_h=80.0, root=Group(name="Artwork", role="artwork", children=[
        Rect(name="panel-front", x=10.0, y=10.0, w=60.0, h=50.0, fill=SolidFill(color=Color.from_hex("#E8B4C0"))),
        Rect(name="band", x=10.0, y=50.0, w=60.0, h=10.0, fill=SolidFill(color=Color.from_hex("#8C3B5A")))]))
    with tempfile.TemporaryDirectory() as tmp:
        path = emit_pdf_ai(doc, tmp + "/d.ai")
        import fitz
        with fitz.open(path) as pdf:
            pdf.new_page(width=pdf[0].rect.width, height=pdf[0].rect.height)
            return pdf.tobytes()


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class CalmPageBrowserTests(_ProfileEditorFixtures, DrainedStaticLiveServerTestCase):

    def _at_gate2(self, drawing=False):
        from .test_browser_recon_result import ReconResultBrowserTests
        task = ReconResultBrowserTests._completed_task(self)
        if drawing:
            out = task.packaging_outputs.first()
            out.design_preview_ai.save("container_task_%d.ai" % task.id, ContentFile(_drawing_pdf()), save=False)
            out.spec_sheet = dict(out.spec_sheet, **{"drawing_views/1.0": {"schema": "drawing_views/1.0", "sections": [
                {"key": "panel-front", "words": "The front", "page": 1, "box_mm": [10.0, 10.0, 70.0, 60.0]}]}})
            out.save()
        return task

    def _gate2_page(self, task):
        page = self._design_page(task)
        page.wait_for_selector("#gate2-state .gate2-actions", state="attached")
        return page

    # -- (4) no browser pop-up ---------------------------------------------------------------------------------------

    def test_goal_1013_popups_every_question_is_asked_in_the_page_never_by_the_browser(self):
        """Approve asks in the page's own dialog, in words, with its own two answers — "Not now" closes it and nothing
        is sent; the browser's own dialog is never raised."""
        task = self._at_gate2()
        page = self._gate2_page(task)
        posted = []
        page.on("request", lambda r: posted.append(r.url) if r.method == "POST" else None)
        page.click("#gate2-state .gate2-actions button.primary")
        page.wait_for_selector("#ask-dialog[open]")
        assert page.text_content("#ask-words").startswith("Approve this design?")
        assert page.text_content("#ask-yes") == "Approve" and page.text_content("#ask-no") == "Not now"
        page.click("#ask-no")
        page.wait_for_selector("#ask-dialog", state="hidden")
        page.wait_for_timeout(300)
        assert posted == [] and self.dialogs == []
        # a refusal said in the page too: the page's own words, one Close, nothing thrown
        # (its promise is kept when it is closed: started here, never awaited)
        page.evaluate("() => { sayInPage('The request for changes was not sent — try again.'); }")
        page.wait_for_selector("#ask-dialog[open]")
        assert page.is_hidden("#ask-no") and page.text_content("#ask-yes") == "Close"
        page.keyboard.press("Escape")
        page.wait_for_selector("#ask-dialog", state="hidden")
        assert self.dialogs == []

    # -- (5) one primary button a step -------------------------------------------------------------------------------

    def test_goal_1013_one_button_gate2_has_one_primary_approve_and_one_quiet_download(self):
        """At the design's gate: ONE primary — Approve; "Accept this design" is gone into it; one Download, quiet beside
        it, its other formats in a small menu; what Approve records said in one quiet line."""
        task = self._at_gate2()
        page = self._gate2_page(task)
        # the whole page as he sees it — its top bar and its panels too — holds one primary: the step's Approve
        primaries = page.eval_on_selector_all(".btn.primary, .btn-approve, .btn-download-primary",
                                              "els => els.filter(e => e.offsetParent !== null)"
                                              ".map(e => e.textContent.trim())")
        assert primaries == ["Approve"], primaries
        body = page.text_content("#gate2-state")
        assert "Accept this design" not in body and "Reject this design" not in body
        downloads = page.eval_on_selector_all("#gate2-state .download-main", "els => els.map(e => e.className)")
        assert len(downloads) == 1 and "quiet" in downloads[0], downloads
        assert page.eval_on_selector_all("#gate2-state .gate2-actions button",
                                         "bs => bs.map(b => b.textContent.trim())") == ["Approve", "Ask for changes"]

    def test_goal_1013_one_button_the_finished_design_has_one_download_and_its_menu(self):
        """Finished: one primary — Download, the first file there is — and every other format in its small menu."""
        task = self._at_gate2()
        out = task.packaging_outputs.first()
        out.production_pdf.save("p.pdf", ContentFile(b"%PDF-1.4\n" + b"x" * 300), save=True)
        DesignTask.objects.filter(pk=task.pk).update(status="completed")
        page = self._design_page(task)
        page.wait_for_selector("#complete-state .download-one", state="attached")
        primaries = page.eval_on_selector_all("#complete-state .btn.primary", "els => els.map(e => e.textContent.trim())")
        assert primaries == ["Download"], primaries
        menu = page.eval_on_selector_all("#complete-state .download-more li a", "as => as.map(a => a.textContent.trim())")
        assert "The production PDF (CMYK)" in menu and "The specification (PDF)" in menu, menu
        assert page.eval_on_selector("#complete-state .download-more", "d => d.open") is False   # folded away

    # -- (6) the drawings on the page ----------------------------------------------------------------------------------

    def test_goal_1013_viewer_each_drawing_large_with_enlarge_zoom_and_pan(self):
        """The drawing large on the page, made from the drawing itself; each page and named part beside it; a click
        enlarges it over the page — + zooms, a drag pans, Escape closes it — never a new tab, never the file."""
        task = self._at_gate2(drawing=True)
        page = self._gate2_page(task)
        page.wait_for_selector("#drawings .drawing-big", state="visible")
        page.wait_for_function("() => { const i = document.querySelector('#drawings .drawing-big');"
                               " return i && i.complete && i.naturalWidth > 1000; }")
        thumbs = page.eval_on_selector_all("#drawings .drawing-thumb", "ts => ts.map(t => t.textContent.trim())")
        assert "The outside" in thumbs[0] or "The design" in thumbs[0], thumbs
        assert any("The front" in t for t in thumbs) and any("Page 2" in t or "The inside" in t for t in thumbs), thumbs
        pages_before = len(page.context.pages)
        page.click("#drawings .drawing-big")
        page.wait_for_selector("#viewer-dialog[open]")
        page.click("#viewer-dialog button[aria-label='Zoom in']")
        scale = page.eval_on_selector("#viewer-dialog .viewer-img", "i => i.style.transform")
        assert re.search(r"scale\(1\.5\)", scale), scale
        stage = page.locator("#viewer-dialog .viewer-stage").bounding_box()
        page.mouse.move(stage["x"] + stage["width"] / 2, stage["y"] + stage["height"] / 2)
        page.mouse.down()
        page.mouse.move(stage["x"] + stage["width"] / 2 + 80, stage["y"] + stage["height"] / 2 + 40, steps=5)
        page.mouse.up()
        moved = page.eval_on_selector("#viewer-dialog .viewer-img", "i => i.style.transform")
        assert re.search(r"translate\((?!0px, 0px)", moved), moved
        page.keyboard.press("Escape")
        page.wait_for_selector("#viewer-dialog", state="hidden")
        assert len(page.context.pages) == pages_before and self.dialogs == []

    # -- (3) resume only when stopped ----------------------------------------------------------------------------------

    def test_goal_1013_resume_shown_only_when_the_design_has_truly_stopped(self):
        """Working with its step just begun: no "Not moving?"; the same design quiet far past its step's time: offered;
        waiting for him at its gate: never."""
        task = self._at_gate2()
        DesignTask.objects.filter(pk=task.pk).update(status="gate_1_approved")
        AgentLog.objects.create(task=task, agent_name="ARIA", action="ARIA: Gate 1 approved — image 1")
        page = self._design_page(task)
        page.wait_for_selector("#feed-state, #state-note", state="attached")
        page.wait_for_timeout(800)
        assert page.locator("#resume-note").count() == 0
        AgentLog.objects.filter(task=task).update(timestamp=timezone.now() - timedelta(hours=3))
        page.evaluate("loadTask(%d)" % task.pk)
        page.wait_for_selector("#resume-note", timeout=15000)
        assert "Not moving?" in page.text_content("#resume-note")
        DesignTask.objects.filter(pk=task.pk).update(status="awaiting_gate_2")
        page.evaluate("loadTask(%d)" % task.pk)
        page.wait_for_selector("#gate2-state .gate2-actions", state="attached")
        page.wait_for_timeout(500)
        assert page.locator("#resume-note").count() == 0
        assert self.dialogs == []


class CalmPageServerTests(TestCase):
    """The server's own halves of (3) and (6)."""

    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")

    def _task(self, status, log_age=None):
        task = DesignTask.objects.create(brand=self.brand, task_text="a design", status=status)
        if log_age is not None:
            row = AgentLog.objects.create(task=task, agent_name="ARIA", action="ARIA: working")
            AgentLog.objects.filter(pk=row.pk).update(timestamp=timezone.now() - log_age)
        return task

    def test_goal_1013_resume_stalled_is_said_for_every_state_true_only_when_stopped(self):
        """``step_times.stalled`` for every state: never while it waits for him, is finished or failed; a working design
        only once its log has been quiet well past its step's time."""
        from apps.pipeline.step_times import STALLED_UNMEASURED_SECONDS, stalled
        for status in ("awaiting_trend_review", "awaiting_gate_1", "awaiting_dimensions", "awaiting_container_profile",
                       "awaiting_gate_2", "completed", "failed", "running"):
            assert stalled(self._task(status, log_age=timedelta(days=2))) is False, status
        assert stalled(self._task("gate_1_approved", log_age=timedelta(seconds=5))) is False
        # a step measured at a second or two is still never "stopped" within STALLED_LEAST_SECONDS of its last line
        from apps.pipeline.step_times import STALLED_LEAST_SECONDS
        from unittest import mock
        with mock.patch("apps.pipeline.step_times.typical", return_value={"plan": (1.0, 3)}):
            assert stalled(self._task("gate_1_approved", log_age=timedelta(seconds=30))) is False
            assert stalled(self._task("gate_1_approved",
                                      log_age=timedelta(seconds=STALLED_LEAST_SECONDS + 5))) is True
        assert stalled(self._task("generating_dieline",
                                  log_age=timedelta(seconds=3 * STALLED_UNMEASURED_SECONDS))) is True

    def test_goal_1013_resume_the_status_says_stalled_for_every_state(self):
        """The page is told, for every state, whether the design has stopped — never left to guess from a missing
        answer (it offered Resume whenever it was not told "false")."""
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_superuser("calm", "c@example.invalid", "x")
        self.client.force_login(user)
        for status in ("awaiting_gate_1", "awaiting_gate_2", "completed"):
            body = self.client.get("/api/tasks/%d/status/" % self._task(status).pk).json()
            assert body["stalled"] is False, (status, body.get("stalled"))

    def test_goal_1013_viewer_views_for_every_page_and_named_part_and_never_a_fault(self):
        """The drawing's views: each page in words and each named part of its first, rendered from the drawing at the
        size asked, kept once made; a drawing whose bytes do not open shows no views — never a fault."""
        from django.contrib.auth import get_user_model
        from django.test import override_settings

        from apps.pipeline.drawing_views import picture, views_for
        from apps.pipeline.models import GeneratedImage, PackagingOutput
        media = tempfile.mkdtemp(prefix="calm_")
        with override_settings(MEDIA_ROOT=media):
            task = self._task("awaiting_gate_2")
            image = GeneratedImage.objects.create(task=task, direction_name="d", prompt_used="p", variation_number=1)
            out = PackagingOutput.objects.create(task=task, approved_image=image, spec_sheet={"drawing_views/1.0": {"sections": [
                {"key": "panel-front", "words": "The front", "page": 1, "box_mm": [10.0, 10.0, 70.0, 60.0]}]}})
            out.design_preview_ai.save("d.ai", ContentFile(_drawing_pdf()), save=True)
            views = views_for(task)
            assert [v["words"] for v in views] == ["The outside", "The front", "Page 2"], views
            path = picture(task, 1, 600, [10.0, 10.0, 70.0, 60.0])
            from PIL import Image
            with Image.open(path) as im:
                assert im.size[0] == 600 and abs(im.size[1] - 500) <= 2       # the part's own 60 x 50 mm
            assert picture(task, 1, 600, [10.0, 10.0, 70.0, 60.0]) == path          # kept once made
            assert picture(task, 3, 600) is None
            out.design_preview_ai.save("bad.ai", ContentFile(b"%PDF-1.4\n" + b"x" * 600), save=True)
            assert views_for(task) == [] and picture(task, 1, 600) is None
            user = get_user_model().objects.create_superuser("calm2", "c2@example.invalid", "x")
            self.client.force_login(user)
            r = self.client.get("/api/tasks/%d/drawing/" % task.pk)
            assert r.status_code == 200 and r.json() == {"views": []}
            assert self.client.get("/api/tasks/%d/drawing/1.png?w=600" % task.pk).status_code == 404

    def test_goal_1013_viewer_views_are_made_with_the_drawing_and_the_page_only_reads_them(self):
        """Made with the drawing (``drawing_views.prepare``, in the pipeline's thread): its views listed on its record
        with its fingerprint, each picture beside the page and the large one kept — then the page's own requests never
        open the drawing (PyMuPDF reads one drawing at a time in a process; the site answers on several threads)."""
        from unittest import mock

        from django.contrib.auth import get_user_model
        from django.test import override_settings

        from apps.pipeline import drawing_views as DV
        from apps.pipeline.models import GeneratedImage, PackagingOutput
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="calm_")):
            task = self._task("awaiting_gate_2")
            image = GeneratedImage.objects.create(task=task, direction_name="d", prompt_used="p", variation_number=1)
            out = PackagingOutput.objects.create(task=task, approved_image=image, spec_sheet={})
            out.design_preview_ai.save("d.ai", ContentFile(_drawing_pdf()), save=True)
            DV.prepare(task, out)
            out.refresh_from_db()
            record = out.spec_sheet["drawing_views/1.0"]
            assert [v["words"] for v in record["views"]] == ["The outside", "Page 2"] and record["drawing"]
            user = get_user_model().objects.create_superuser("calm3", "c3@example.invalid", "x")
            self.client.force_login(user)
            with mock.patch("fitz.open", side_effect=AssertionError("the page opened the drawing")):
                views = self.client.get("/api/tasks/%d/drawing/" % task.pk).json()["views"]
                assert [v["words"] for v in views] == ["The outside", "Page 2"]
                for v in views:
                    for size in ("thumb", "url"):
                        assert self.client.get(v[size]).status_code == 200, v[size]

    def test_goal_1013_viewer_each_named_part_is_kept_where_it_is_drawn_turned_with_its_group(self):
        """Each named part measured where it is drawn — a turned group's turned (a box lying flat)."""
        from apps.ire.graph import Color, Document, Group, Rect, SolidFill, quarter_turn
        from apps.ire.views_of import views
        front = Rect(name="panel-front", x=10.0, y=10.0, w=40.0, h=20.0, fill=SolidFill(color=Color.from_hex("#E8B4C0")))
        doc = Document(page_w=100, page_h=100, root=Group(name="Artwork", children=[
            Group(name="turned", turn=quarter_turn(40.0, 20.0, 10.0, 10.0), children=[front])]))
        assert views(doc)["sections"] == [{"key": "panel-front", "words": "The front", "page": 1,
                                           "box_mm": [10.0, 10.0, 30.0, 50.0]}]

    def test_source_guard_goal_1013_popups_no_script_calls_the_browsers_own_dialogs(self):
        """SOURCE-STRING GUARD (§Y2): asserts the absence of a literal — a call of the browser's own alert, confirm or
        prompt — in every script and template the site serves, and asserts nothing about behaviour; the behaviour is
        held by the browser tests above (no dialog raised, every question in the page)."""
        call = re.compile(r"(^|[^\w.])(window\.)?(alert|confirm|prompt)\(")
        found = []
        for root in (os.path.join(settings.BASE_DIR, "static", "js"), os.path.join(settings.BASE_DIR, "templates")):
            for here, _dirs, files in os.walk(root):
                for name in files:
                    if name.endswith((".js", ".html")):
                        with open(os.path.join(here, name), encoding="utf-8") as fh:
                            for n, line in enumerate(fh, 1):
                                code = line.split("//")[0]
                                if call.search(code):
                                    found.append("%s:%d" % (os.path.relpath(os.path.join(here, name), settings.BASE_DIR), n))
        assert found == [], found
