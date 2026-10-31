"""VQR-2A — fail-closed visual quality gate (browser).

Real-dashboard proof of §9/§11: a task-53-shaped completion (A4 artboard,
placeholder front artwork) renders ONE coherent Visual Quality Gate panel —
overall FAIL, every required axis visible including UNMEASURED ones, no
approval language anywhere on the screen, artifacts retained as
inspection-only — and the server refuses direct approval with the
authoritative quality reason. Packaging keeps its vocabulary-free Gate 2.
"""
from __future__ import annotations

import pytest
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    HAVE_PLAYWRIGHT = True
except ImportError:              # pragma: no cover
    HAVE_PLAYWRIGHT = False

from django.core.files.base import ContentFile

from apps.pipeline.models import GateDecision

from .test_browser_profile_editor import _ProfileEditorFixtures
from .test_vqr2a_visual_quality_gate import AI_A4, PROFILE, TASK53_GRAPH


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class Vqr2aQualityBrowserTests(_ProfileEditorFixtures,
                               DrainedStaticLiveServerTestCase):

    def _task53_shape(self, *, png=True):
        from .test_browser_recon_result import ReconResultBrowserTests
        task = ReconResultBrowserTests._completed_task(self, png=png)
        out = task.packaging_outputs.first()
        out.design_preview_ai.delete(save=True)
        out.design_preview_ai.save(f"container_task_{task.id}.ai",
                                   ContentFile(AI_A4), save=True)
        spec = dict(out.spec_sheet)
        spec["container_design_graph/1.1"] = TASK53_GRAPH
        spec["container_profile"] = PROFILE
        out.spec_sheet = spec
        out.save(update_fields=["spec_sheet"])
        return task

    def _gate2_page(self, task):
        page = self._design_page(task)  # [2026-09-25: the review is drawn on the design's own page]
        page.wait_for_selector("#gate2-state .vq-gate-panel, "
                               "#gate2-state .gate2-blocked, "
                               "#gate2-state .gate2-actions",
                               state="attached")
        return page

    def test_vq_panel_shows_every_axis_and_approve_stands_beside_it(self):
        task = self._task53_shape()
        page = self._gate2_page(task)
        page.wait_for_selector(".vq-gate-panel", state="attached")
        body = " ".join(page.text_content("#gate2-state").split())
        assert "Its quality check:" in body
        assert "BLOCKED_VISUAL_QUALITY" in body
        # [his goal of 2026-10-13, (1): "NO check ever stops a design ... the problem is shown beside Approve in plain
        # words"] it read "It cannot be approved ... until each check that fails is put right"
        assert "Each check that fails is said beside Approve, and approving keeps it with your approval" in body
        # [re-pinned: his last goal before the pitch, 2026-10-16, Step 1 (8): "Remove the leftover "Illustrator
        # package" box/button"] it read: assert "the printer's package is made once each is put right" in body
        assert "printer's package" not in body and "Illustrator package" not in body
        # every required axis visible — UNMEASURED never hidden (§9)
        for label in ("The editable file is there and whole", "The artboard fits the product",
                      "The outline matches the concept", "The closure matches the concept",
                      "The front artwork is drawn, not a stand-in",
                      "The mark is not cut off, stretched or too small",
                      "No text is cut off, overlapping or too small",
                      "Everything is on the artboard, with no text over text"):  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]
            assert label in body, label
        assert page.eval_on_selector_all(
            ".vq-axis", "els => els.length") == 8
        assert page.eval_on_selector_all(
            ".vq-unmeasured", "els => els.length") == 5
        # [§BH71 (0a): it read "This check is needed and was not measured, so the design cannot move on." — an
        # unmeasured check is a warning beside Approve, shown here while a measured one fails]
        assert "Not measured yet — a warning beside Approve." in body
        # measured failures carry their codes and safe values
        assert "VQ_ARTBOARD_NOT_PRODUCT_DERIVED" in body
        assert "VQ_FRONT_ARTWORK_UNRESOLVED_PLACEHOLDER" in body
        assert "matched_page_standard: A4" in body
        # [his goal of 2026-10-13, (1) and (5)] one Approve and Ask for changes stand beside what it did not pass, said
        # in words; the printer's package still waits on the quality check
        assert page.eval_on_selector_all("#gate2-state .gate2-actions button",
                                         "bs => bs.map(b => b.textContent.trim())") == ["Approve", "Ask for changes"]
        assert "Checks it has not passed" in body
        assert "Prepare the Illustrator package" not in body
        assert page.eval_on_selector(
            ".vq-gate-panel", "el => el.getAttribute('role')") == "alert"

    def test_artifacts_retained_as_inspection_only(self):
        task = self._task53_shape()
        page = self._gate2_page(task)
        body = " ".join(page.text_content("#gate2-state").split())
        # [his goal of 2026-10-13, (1)] approvable now: never "for looking only" beside Approve
        assert "It has not passed its quality check — what it did not pass is said beside Approve" in body
        assert ("This is the drawing's editable file. It has not passed its quality check; approving it keeps what it "
                "did not pass with your approval.") in " ".join(body.split())
        href = page.eval_on_selector(
            "#gate2-state .download-main",
            "a => a.getAttribute('href')")
        assert href == (f"/api/tasks/{task.id}/reconstruction-artifact/ai/"
                        "?download=1")
        # the result panel's AI card agrees (one coherent state, §9)
        profile = " ".join(page.text_content("#profile-view").split())
        assert "Not passed its quality check" in profile and "for looking only" not in profile.lower()
        assert "approving it keeps what it did not pass with your approval" in profile
        assert "The .ai file is the design itself" not in profile  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]

    def test_unmeasured_checks_are_said_beside_approve_never_a_block(self):
        """§BH71 (0a), the owner's goal of 2026-09-28: "My approval overrides §BH50(f)(5). Unmeasured checks (fidelity
        to the concept, copy fit) show as a warning beside Approve, never a block." A completion that measures
        nothing is approvable: Approve is drawn, each check not measured yet said in words beside it — its code one
        click under — its count in the question Approve asks, and nothing on the page says "for looking only"."""
        from .test_browser_recon_result import ReconResultBrowserTests
        task = ReconResultBrowserTests._completed_task(self)
        page = self._gate2_page(task)
        page.wait_for_selector("#gate2-state .gate2-warnings", state="attached")
        body = " ".join(page.text_content("#gate2-state").split())
        shown = page.eval_on_selector_all(".gate2-warnings > ul > li", "els => els.map(e => e.textContent)")
        assert f"Not measured yet ({len(shown)})" in body and len(shown) == 7
        assert "whether the outline matches the concept — not measured yet" in shown
        assert all(s.endswith("— not measured yet") and "VQ_" not in s for s in shown)
        assert "VQ_SILHOUETTE_COMPARISON_UNAVAILABLE" in page.text_content(".gate2-warnings details")
        assert "for looking only" not in body.lower() and "Its quality check:" not in body
        approve = page.eval_on_selector_all(
            "#gate2-state .gate2-actions button", "els => els.filter(b => b.textContent.trim() === 'Approve')"
            ".map(b => b.getAttribute('onclick'))")
        # [his goal of 2026-10-13, (1)] each count in its own place: not measured, not confirmed, not passed
        assert approve == [f"approveGate2({task.id}, {task.packaging_outputs.first().id}, 7, 0, 1)"]
        # the one check it has not passed said in words, the fact it found missing said as missing
        assert "The printed information is incomplete — the product's name is not given." in body
        # the warnings sit before Approve, in the same panel
        assert page.evaluate("(() => { const w = document.querySelector('.gate2-warnings'),"
                             " a = document.querySelector('.gate2-actions');"
                             " return !!(w && a && (w.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING)); })()")

    def test_bh71_the_shades_unconfirmed_arabic_is_said_apart_beside_approve(self):
        """His answer of 2026-09-29 to the §BH71 report, (4): the record's shade drawn with an Arabic the executor wrote
        is said beside Approve as words not confirmed yet — under its own heading, apart from the checks not measured
        yet — and Approve's question counts it apart; nothing refuses."""
        from .test_browser_recon_result import ReconResultBrowserTests
        task = ReconResultBrowserTests._completed_task(self)
        from .test_2b3d_readiness import _CLEAN_SECTIONS, _spec
        out = task.packaging_outputs.first()
        code = ("CONTAINER_SHADE_ARABIC_UNCONFIRMED: the shade's Arabic 'طبيعي' was written by the executor and nobody "
                "has confirmed it — Product.shade_names")
        # the design's readiness as a reconstruction writes it, clean but for the shade's mark: the page reads Gate 2's
        # own record, as it does for a drawn container
        out.spec_sheet = {**out.spec_sheet, **_spec(codes={**_CLEAN_SECTIONS, "content": [code]})}
        out.save(update_fields=["spec_sheet"])
        page = self._gate2_page(task)
        page.wait_for_selector("#gate2-state .gate2-warnings", state="attached")
        body = " ".join(page.text_content("#gate2-state").split())
        assert "Not confirmed yet (1)" in body, body[:600]
        assert "the shade name's Arabic, written by the executor — not confirmed yet" in body
        unmeasured = page.eval_on_selector_all(".gate2-warnings > ul > li", "els => els.map(e => e.textContent)")
        unmeasured = [w for w in unmeasured if w.endswith("— not measured yet")]
        assert f"Not measured yet ({len(unmeasured)})" in body and unmeasured, body[:600]   # said apart, as before
        approve = page.eval_on_selector_all(
            "#gate2-state .gate2-actions button", "els => els.filter(b => b.textContent.trim() === 'Approve')"
            ".map(b => b.getAttribute('onclick'))")
        assert approve == [f"approveGate2({task.id}, {out.id}, {len(unmeasured)}, 1, 0)"], approve

    def test_png_loss_is_not_the_blocker(self):
        task = self._task53_shape(png=False)
        page = self._gate2_page(task)
        page.wait_for_selector(".vq-gate-panel", state="attached")
        body = " ".join(page.text_content("#gate2-state").split())
        assert "Its quality check:" in body
        assert "Download" in body and "The design .ai, one layer" in body      # [his goal of 2026-10-13, (5)]

    def test_dom_bypass_is_never_refused_for_quality_and_the_handoff_still_waits_on_it(self):
        # [his goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a design"] a measured quality
        # failure is kept beside Approve, never what refuses it — this design's approval waits on his own acceptance
        # alone; the printer's package still waits on the quality check
        task = self._task53_shape()
        out = task.packaging_outputs.first()
        page = self._gate2_page(task)
        page.wait_for_selector(".vq-gate-panel", state="attached")
        decisions = GateDecision.objects.count()
        verdict = page.evaluate(
            """async ([taskId, outId]) => {
                 const csrf = (document.cookie.match(
                     /csrftoken=([^;]+)/) || [])[1] || '';
                 const approve = await fetch(
                   `/api/tasks/${taskId}/gate2_approve/`, {
                     method: 'POST',
                     headers: {'Content-Type': 'application/json',
                               'X-CSRFToken': csrf},
                     body: JSON.stringify({packaging_output_id: outId})});
                 const handoff = await fetch(
                   `/api/tasks/${taskId}/generate_handoff/`, {
                     method: 'POST',
                     headers: {'Content-Type': 'application/json',
                               'X-CSRFToken': csrf},
                     body: JSON.stringify({})});
                 return {a: {status: approve.status,
                             body: await approve.json()},
                         h: {status: handoff.status,
                             body: await handoff.json()}};
               }""", [task.id, out.id])
        from apps.pipeline.gate2_problems import REFUSING
        assert verdict["a"]["status"] == 409
        assert verdict["a"]["body"]["error"] != "GATE_2_NOT_READY"
        assert {str(c).split(":")[0] for c in verdict["a"]["body"]["failures"]} <= set(REFUSING), verdict["a"]
        assert verdict["h"]["status"] == 409
        assert verdict["h"]["body"]["reason_code"] == \
            "VISUAL_QUALITY_GATE_FAILED"
        assert GateDecision.objects.count() == decisions
        task.refresh_from_db()
        assert task.status == "awaiting_gate_2"
        out.refresh_from_db()
        assert "handoff" not in out.spec_sheet

    def test_packaging_gate2_keeps_no_container_quality_vocabulary(self):
        from .test_browser_vqr6_authority import Vqr6AuthorityBrowserTests
        task = Vqr6AuthorityBrowserTests._packaging_task(self)
        page = self._gate2_page(task)
        body = " ".join(page.text_content("#gate2-state").split())
        assert "Visual Quality Gate" not in body
        assert "For looking only" not in body
        assert page.eval_on_selector(
            "#gate2-state",
            "el => [...el.querySelectorAll('button')]"
            ".filter(b => b.textContent.trim() === 'Approve').length"   # [his goal of 2026-10-13, (5)] one Approve
        ) == 1
