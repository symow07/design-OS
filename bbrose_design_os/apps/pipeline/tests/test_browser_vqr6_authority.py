"""VQR-6 — single artifact and status authority (browser).

Real-dashboard proof of the owner's §8 status-consistency defect fix: a
tampered/unavailable record (task-56 shape) presents ONE coherent blocked
state — no "Download Design .ai (editable)", no handoff generation, no
enabled Gate-2 approval; a clean completion (task-53 shape) keeps every
authorized action; an optional-PNG gap (task-55 shape) keeps the valid AI
authority; DOM manipulation cannot bypass server readiness; Packaging Gate-2
behavior does not regress.
"""
from __future__ import annotations

import json

import pytest
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase
from django.core.files.base import ContentFile

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    HAVE_PLAYWRIGHT = True
except ImportError:              # pragma: no cover
    HAVE_PLAYWRIGHT = False

from apps.core.models import Brand, Product
from apps.pipeline.models import (DesignTask, GateDecision, GeneratedImage,
                                  PackagingOutput)

from .test_browser_profile_editor import PNG, _ProfileEditorFixtures

AI_BYTES = b"%PDF-1.4\n" + b"x" * 600
AI_LINK_TEXT = "The design .ai, one layer"   # [his goal of 2026-10-13, (5)] one Download, the file it takes said beside it
HANDOFF_BTN = "Prepare the Illustrator package"   # §BH55 Phase 3: was "Generate native Illustrator handoff package"


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class Vqr6AuthorityBrowserTests(_ProfileEditorFixtures,
                                DrainedStaticLiveServerTestCase):

    def _completed_task(self, **kw):
        # reuse the UI-2B-2A completed-container factory; imported inside the
        # method so pytest does not re-collect that module's tests here
        from .test_browser_recon_result import ReconResultBrowserTests
        return ReconResultBrowserTests._completed_task(self, **kw)

    def _tampered_task(self):
        """Task-56 shape: FieldFile truthy, storage object unresolvable."""
        task = self._completed_task()
        out = task.packaging_outputs.first()
        out.design_preview_ai.name = "../../tampered-demo-record"
        out.save(update_fields=["design_preview_ai"])
        return task

    def _gate2_page(self, task):
        page = self._design_page(task)  # [2026-09-25: the review is drawn on the design's own page]
        page.wait_for_selector("#gate2-state h3, #gate2-state h4, "
                               "#gate2-state .gate2-blocked",
                               state="attached")
        return page

    def _gate2_text(self, page):
        return " ".join(page.text_content("#gate2-state").split())

    def test_his_122_at_gate_2_he_gives_the_sku_any_time_and_a_product_records_stands(self):
        """[His answers after 122 was redrawn, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md), (1): "Add an optional SKU field
        ... at Gate 2 so I can fill it in any time."] A design with no product record shows an SKU field beside Approve;
        saved, it is said and kept; a design whose product record carries one shows that one."""
        task = self._completed_task()
        page = self._gate2_page(task)
        page.wait_for_selector(".sku-line", state="attached")
        assert "from the product record" in self._gate2_text(page)
        task.product = None
        task.save(update_fields=["product"])
        page = self._gate2_page(task)
        page.wait_for_selector("#design-sku", state="visible")
        page.fill("#design-sku", "BBR-HC-122")
        page.click("#save-sku")
        page.wait_for_function("document.getElementById('sku-msg') && "
                               "document.getElementById('sku-msg').textContent.includes('Saved')")
        assert page.input_value("#design-sku") == "BBR-HC-122"
        task.refresh_from_db()
        assert task.sku == "BBR-HC-122"

    # -- task-56 shape: one coherent blocked state ---------------------------

    def test_tampered_record_shows_one_coherent_blocked_state(self):
        task = self._tampered_task()
        page = self._gate2_page(task)
        page.wait_for_selector(".gate2-blocked", state="attached")
        body = self._gate2_text(page)
        # no AI download claim anywhere on the Gate-2 surface
        assert AI_LINK_TEXT not in body
        # no handoff generation action
        assert HANDOFF_BTN not in body
        # [re-pinned: his last goal before the pitch, 2026-10-16, Step 1 (8): "Remove the leftover "Illustrator
        # package" box/button; Download is the one way to get files."] it read: assert "Illustrator package cannot be
        # made" in body
        assert "Illustrator package" not in body
        # no enabled Gate-2 approval control
        assert page.eval_on_selector(
            "#gate2-state",
            "el => [...el.querySelectorAll('button')]"
            ".filter(b => b.textContent.trim() === 'Approve').length"   # [his goal of 2026-10-13, (5)] one Approve
        ) == 0
        assert "Ask for changes" not in body                 # §BH55 Phase 3: was "Request Revision"
        # the blocked panel states the single authority decision
        # §BH55 Phase 3: the heading in a designer's words, its code kept beside it
        # [the owner's goal of 2026-09-25, (d): the heading in plain words, its code beside it under the record]
        assert "This design cannot be approved yet" in body and "GATE_2_NOT_READY" in body
        # "No engine codes on screen" (the goal, (d)): the code is kept, folded under "What the record says" —
        # what the page SHOWS (innerText skips a closed fold) carries the words and not the code
        shown = " ".join(page.inner_text("#gate2-state").split())
        assert "This design cannot be approved yet" in shown and "What the record says" in shown
        assert "GATE_2_NOT_READY" not in shown
        assert "someone who knows the code must look" in body
        assert "Its editable file is not there" in body
        assert page.eval_on_selector(
            ".gate2-blocked", "el => el.getAttribute('role')") == "alert"
        # and the status panel above agrees (no contradictory wording)
        profile = " ".join(page.text_content("#profile-view").split())
        assert "TECHNICAL_INTERVENTION_REQUIRED" in profile
        assert "TECHNICAL_INTERVENTION_REQUIRED" not in " ".join(page.inner_text("#profile-view").split())
        assert "The editable file: not ready yet" in profile
        assert AI_LINK_TEXT not in profile

    def test_tampered_record_leaks_no_raw_storage_url(self):
        # Gate-1 concept images legitimately use the authenticated /files/
        # route; the RECONSTRUCTION artifacts must not — no .ai link, no
        # dielines path, no trace of the tampered record name.
        task = self._tampered_task()
        page = self._gate2_page(task)
        page.wait_for_selector(".gate2-blocked", state="attached")
        html = page.evaluate(
            "document.getElementById('profile-view').innerHTML + "
            "document.getElementById('gate2-state').innerHTML")
        assert "tampered-demo-record" not in html
        assert "/files/dielines" not in html
        assert page.evaluate(
            "[...document.getElementById('profile-view').querySelectorAll('a'),"
            " ...document.getElementById('gate2-state').querySelectorAll('a')]"
            ".filter(a => (a.getAttribute('href') || '')"
            ".includes('.ai')).length") == 0

    # -- task-53 shape: completion keeps authorized INSPECTION artifacts ----
    # (VQR-2A: approval and handoff are quality-blocked; the authorized
    # artifact links themselves must survive for technical inspection)

    def test_clean_completion_keeps_authorized_artifact_access(self):
        # [§BH71 (0a), the owner's goal of 2026-09-28: a completion that measures nothing is a warning beside
        # Approve now; the quality-FAILED completion this test is about is the task-53 shape, its A4 artboard
        # measured — imported inside the method so pytest does not re-collect that module's tests here]
        from .test_browser_vqr2a_quality import Vqr2aQualityBrowserTests
        task = Vqr2aQualityBrowserTests._task53_shape(self)
        page = self._gate2_page(task)
        body = self._gate2_text(page)
        href = page.eval_on_selector(
            "#gate2-state .download-main",
            "a => a.getAttribute('href')")
        assert href == (f"/api/tasks/{task.id}/reconstruction-artifact/ai/"
                        "?download=1")
        hero = page.eval_on_selector(
            "#gate2-state img.dieline-img", "i => i.getAttribute('src')")
        assert hero == f"/api/tasks/{task.id}/reconstruction-artifact/png/"
        # [his goal of 2026-10-13, (1): "NO check ever stops a design ... the problem is shown beside Approve in plain
        # words"] a quality-failed result is approvable: Approve stands, what it did not pass said beside it; the
        # printer's package still waits on the quality check
        assert "It has not passed its quality check — what it did not pass is said beside Approve" in body
        assert "Checks it has not passed" in body
        assert HANDOFF_BTN not in body
        assert page.eval_on_selector(
            "#gate2-state",
            "el => [...el.querySelectorAll('button')]"
            ".filter(b => b.textContent.trim() === 'Approve').length"   # [his goal of 2026-10-13, (5)] one Approve
        ) == 1
        assert "Its quality check:" in body
        # artifact download block carries authorized endpoints only
        downloads = page.eval_on_selector(
            "#gate2-state .download-one", "el => el.innerHTML")
        assert "/files/" not in downloads and "/media/" not in downloads

    # -- task-55 shape: optional PNG missing, AI inspection retained ---------

    def test_missing_optional_png_keeps_valid_ai_action(self):
        task = self._completed_task(png=False)
        page = self._gate2_page(task)
        body = self._gate2_text(page)
        assert AI_LINK_TEXT in body
        assert page.eval_on_selector(
            "#gate2-state",
            "el => el.querySelectorAll('img.dieline-img').length") == 0
        # [§BH71 (0a), the owner's goal of 2026-09-28: it read "blocked by visual quality — never by the optional
        # PNG loss", with no Approve: this fixture measures nothing, so neither blocks it — Approve is drawn, the
        # checks not measured yet said beside it]
        assert "Its quality check:" not in body
        assert "Not measured yet (" in body
        assert page.eval_on_selector(
            "#gate2-state",
            "el => [...el.querySelectorAll('button')]"
            ".filter(b => b.textContent.trim() === 'Approve').length"   # [his goal of 2026-10-13, (5)] one Approve
        ) == 1

    # -- DOM manipulation cannot bypass the server ---------------------------

    def test_dom_bypass_post_is_refused_by_the_server(self):
        task = self._tampered_task()
        out = task.packaging_outputs.first()
        page = self._gate2_page(task)
        page.wait_for_selector(".gate2-blocked", state="attached")
        decisions = GateDecision.objects.count()
        verdict = page.evaluate(
            """async ([taskId, outId]) => {
                 const res = await fetch(`/api/tasks/${taskId}/gate2_approve/`, {
                   method: 'POST',
                   headers: {'Content-Type': 'application/json',
                             'X-CSRFToken': (document.cookie.match(
                               /csrftoken=([^;]+)/) || [])[1] || ''},
                   body: JSON.stringify({packaging_output_id: outId})});
                 return {status: res.status, body: await res.json()};
               }""", [task.id, out.id])
        assert verdict["status"] == 409
        assert verdict["body"]["error"] == "GATE_2_NOT_READY"
        assert GateDecision.objects.count() == decisions
        task.refresh_from_db()
        assert task.status == "awaiting_gate_2"

    # -- §9: Packaging Gate-2 does not regress -------------------------------

    def _packaging_task(self):
        product = Product.objects.create(
            brand=Brand.objects.first(), product_id="PK-V6", name="Carton",
            category="PK", year=2026, width_mm=90, depth_mm=32, height_mm=92)
        task = DesignTask.objects.create(
            brand=Brand.objects.first(), product=product,
            task_text="a packaging carton", status="awaiting_gate_2",
            design_target="packaging", created_by=self.user)
        img = GeneratedImage(task=task, direction_name="Rose")
        img.image_file.save("concept.png", ContentFile(PNG), save=True)
        out = PackagingOutput.objects.create(
            task=task, approved_image=img, spec_sheet={"backend": "vector"})
        out.design_preview_ai.save("pkg.ai", ContentFile(AI_BYTES),
                                   save=True)
        out.design_preview.save("pkg.png", ContentFile(PNG), save=True)
        return task

    def test_packaging_gate2_unchanged(self):
        task = self._packaging_task()
        out = task.packaging_outputs.first()
        page = self._gate2_page(task)
        body = self._gate2_text(page)
        assert "Gate 2 is not ready" not in body
        assert AI_LINK_TEXT in body
        # packaging keeps its raw FileField URL — VQR-6 scoped to container
        href = page.eval_on_selector(
            "#gate2-state .download-main",
            "a => a.getAttribute('href')")
        assert href == out.design_preview_ai.url
        assert page.eval_on_selector(
            "#gate2-state",
            "el => [...el.querySelectorAll('button')]"
            ".filter(b => b.textContent.trim() === 'Approve').length"   # [his goal of 2026-10-13, (5)] one Approve
        ) == 1
        payload = json.loads(page.evaluate(
            f"fetch('/api/tasks/{task.id}/status/')"
            ".then(r => r.text())"))
        readiness = payload.get("container_gate2_readiness", "MISSING")
        assert readiness is None
