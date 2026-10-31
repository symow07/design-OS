"""Real-browser tests for the Packaging omission confirmation (B4b-2C §4–§6).

Submitting a Packaging task while Product Container references are staged
must be an informed decision. The dialog asks once, for that attempt only:
cancel and Escape keep everything and send nothing; Return restores the
References editor without sending; only the explicit confirm dispatches — one
JSON request, no filenames, no bytes, no appendToFormData. Approval is never
stored: every failure (network, 4xx, 5xx, malformed) preserves the held
files and makes the next attempt ask again. Confirmed success is the single
moment held references are cleared, because the owner completed a different
task agreeing they would not be used.
"""
from __future__ import annotations

import pytest
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase

try:
    from playwright.sync_api import TimeoutError as PWTimeoutError
    from playwright.sync_api import sync_playwright  # noqa: F401
    HAVE_PLAYWRIGHT = True
except ImportError:              # pragma: no cover
    HAVE_PLAYWRIGHT = False

from apps.pipeline.models import ApiCallRecord, DesignTask, TaskReference

from .test_browser_staged_reference_ui import RefUiHarness, _file

_OK = '{"task_id": 4242, "status": "queued"}'


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class PackagingOmissionBrowserTests(RefUiHarness, DrainedStaticLiveServerTestCase):

    # -- helpers -------------------------------------------------------------

    def _route(self, page, status=201, body=_OK, abort=False):
        seen = {"count": 0}

        def handle(route):
            seen["count"] += 1
            seen["content_type"] = route.request.headers.get(
                "content-type", "")
            seen["body"] = route.request.post_data or ""
            if abort:
                route.abort()
            else:
                route.fulfill(status=status,
                              content_type="application/json", body=body)

        page.route("**/api/tasks/create/", handle)
        page.route("**/api/tasks/4242/**", lambda r: r.fulfill(
            status=200, content_type="application/json", body="{}"))
        return seen

    def _submit(self, page, brief="a folding carton"):
        page.fill("#task-input", brief)
        page.click("#btn-submit")
        page.wait_for_function(
            "document.getElementById('btn-submit').disabled === false")

    def _stage_and_go_packaging(self, page, names=("held.png",)):
        page.set_input_files("#ref-input-container",
                             files=[_file(n) for n in names])
        page.click('.target-chip[data-target="packaging"]')

    def _dialog_open(self, page):
        return page.eval_on_selector("#omission-dialog", "d => d.open")

    # -- when the dialog appears (§4) ----------------------------------------

    def test_zero_held_files_submits_without_confirmation(self):
        page = self._page()
        seen = self._route(page)
        page.click('.target-chip[data-target="packaging"]')
        self._submit(page)
        assert seen["count"] == 1
        assert self._dialog_open(page) is False

    def test_held_files_do_not_dispatch_immediately(self):
        page = self._page()
        seen = self._route(page)
        self._stage_and_go_packaging(page)
        self._submit(page)
        assert seen["count"] == 0
        assert self._dialog_open(page) is True

    def test_dialog_states_exact_count_and_omission(self):
        page = self._page()
        self._route(page)
        self._stage_and_go_packaging(page, ("a.png", "b.png", "c.png"))
        self._submit(page)
        text = " ".join(page.text_content("#omission-dialog").split())
        assert "3 staged Product Container reference files" in text
        assert "will NOT be attached to this Packaging task" in text
        assert "Packaging submits as JSON" in text
        assert "No reference records will be created" in text

    def test_singular_count_reads_singular(self):
        page = self._page()
        self._route(page)
        self._stage_and_go_packaging(page)
        self._submit(page)
        text = page.text_content("#omission-desc")
        assert "1 staged Product Container reference file will NOT" in text
        assert "It stays held" in text

    def test_correction_note_only_for_server_error_cards(self):
        # computed visibility, not the DOM property — a display rule on the
        # hint class was found (in screenshot inspection) defeating [hidden]
        page = self._page()
        self._route(page)
        self._stage_and_go_packaging(page)
        self._submit(page)
        assert page.is_visible("#omission-correction") is False
        page.close()
        # and WITH a server-rejected card the note must actually show
        from .test_browser_reference_errors import _rejection_body
        page = self._page()
        page.route("**/api/tasks/create/", lambda r: r.fulfill(
            status=400, content_type="application/json",
            body=_rejection_body([
                {"code": "REFERENCE_SIGNATURE_INVALID", "message": "x",
                 "filename": "held.png", "category": "container",
                 "file_index": 0}])))
        page.set_input_files("#ref-input-container", files=[_file("held.png")])
        self._submit(page, brief="a serum bottle")
        page.unroute("**/api/tasks/create/")
        self._route(page)
        page.click('.target-chip[data-target="packaging"]')
        self._submit(page)
        assert page.is_visible("#omission-correction") is True

    def test_container_submit_never_opens_the_dialog(self):
        page = self._page()
        seen = self._route(page)
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        self._submit(page, brief="a serum bottle")
        assert seen["count"] == 1
        assert self._dialog_open(page) is False

    # -- the three actions (§4) ----------------------------------------------

    def test_cancel_sends_nothing_and_stays_on_packaging(self):
        page = self._page()
        seen = self._route(page)
        self._stage_and_go_packaging(page)
        self._submit(page)
        page.click("#omission-cancel")
        assert self._dialog_open(page) is False
        assert seen["count"] == 0
        assert page.eval_on_selector(
            '.target-chip[data-target="packaging"]',
            "c => c.classList.contains('active')") is True
        assert page.evaluate("DesignOSReferenceUI.count()") == 1
        # §10: focus returns to the Packaging submit control
        assert page.evaluate("document.activeElement.id") == "btn-submit"

    def test_return_sends_nothing_and_restores_the_editor(self):
        page = self._page()
        seen = self._route(page)
        self._stage_and_go_packaging(page)
        self._submit(page)
        page.click("#omission-return")
        assert self._dialog_open(page) is False
        assert seen["count"] == 0
        assert page.is_visible("#reference-section")
        assert page.eval_on_selector(
            '.target-chip[data-target="product_container"]',
            "c => c.classList.contains('active')") is True
        # focus lands on the first staged reference's remove control
        assert page.evaluate(
            "document.activeElement.classList.contains('ref-card-remove')") \
            is True

    def test_confirm_sends_exactly_one_json_request_without_files(self):
        page = self._page()
        seen = self._route(page)
        self._stage_and_go_packaging(page)
        page.evaluate("""
          (() => {
            const orig = DesignOSReferenceUI.appendToFormData;
            window.__appendCalls = 0;
            DesignOSReferenceUI.appendToFormData = function (fd) {
              window.__appendCalls++; return orig(fd);
            };
          })()
        """)
        self._submit(page)
        page.click("#omission-submit")
        page.wait_for_function(
            "document.getElementById('btn-submit').disabled === false")
        assert seen["count"] == 1
        assert seen["content_type"].startswith("application/json")
        assert '"design_target": "packaging"' in seen["body"].replace(
            '":"', '": "')
        assert "filename=" not in seen["body"]
        assert "held.png" not in seen["body"]
        assert page.evaluate("window.__appendCalls") == 0

    def test_duplicate_confirm_clicks_produce_one_request(self):
        page = self._page()
        seen = self._route(page)
        self._stage_and_go_packaging(page)
        self._submit(page)
        # two synchronous clicks — the second lands after settle() and must
        # be swallowed by the one-outcome guard
        page.evaluate("""
          (() => {
            const b = document.getElementById('omission-submit');
            b.click(); b.click();
          })()
        """)
        page.wait_for_function(
            "document.getElementById('btn-submit').disabled === false")
        page.wait_for_timeout(200)
        assert seen["count"] == 1

    # -- success lifecycle (§6) ----------------------------------------------

    def test_confirmed_success_clears_held_references(self):
        page = self._page()
        self._route(page)
        self._stage_and_go_packaging(page, ("a.png", "b.png"))
        created = page.evaluate("window.__url.created")
        assert created == 2
        self._submit(page)
        page.click("#omission-submit")
        page.wait_for_function(
            "document.getElementById('btn-submit').disabled === false")
        assert page.evaluate("DesignOSReferenceUI.count()") == 0
        # every raster object URL revoked, notice gone, cards gone
        assert page.evaluate("window.__url.revoked") == created
        assert page.eval_on_selector(
            "#ref-held-notice", "el => el.hidden") is True
        page.click('.target-chip[data-target="product_container"]')
        assert page.eval_on_selector_all(
            ".ref-card", "els => els.length") == 0
        assert page.evaluate("""
          Array.from(document.querySelectorAll('input.ref-input'))
               .every(i => i.value === '' && i.files.length === 0)
        """) is True

    # -- failure lifecycle: nothing clears, approval never persists (§5/§6) ---

    def test_failures_preserve_held_state_and_require_reconfirmation(self):
        for mode in ({"abort": True},
                     {"status": 400, "body": '{"error": "bad"}'},
                     {"status": 500, "body": '{"error": "boom"}'},
                     {"status": 201, "body": "not json at all"}):
            page = self._page()
            self._route(page, **mode)
            self._stage_and_go_packaging(page)
            self._submit(page)
            page.click("#omission-submit")
            page.wait_for_function(
                "document.getElementById('btn-submit').disabled === false")
            # [his goal of 2026-10-13, (4)] a refusal is said in the page's own dialog — he closes it, as he would
            if page.locator("#ask-dialog[open]").count():
                page.click("#ask-yes")
                page.wait_for_selector("#ask-dialog", state="hidden")
            # held state survives the failure untouched
            assert page.evaluate("DesignOSReferenceUI.count()") == 1, mode
            assert page.evaluate("window.__url.revoked") == 0, mode
            assert page.eval_on_selector(
                "#ref-held-notice", "el => el.hidden") is False, mode
            # and the next attempt must ask again — approval did not persist
            page.click("#btn-submit")
            assert self._dialog_open(page) is True, mode
            page.click("#omission-cancel")
            page.close()

    def test_failure_restores_submission_controls(self):
        page = self._page()
        self._route(page, abort=True)
        self._stage_and_go_packaging(page)
        self._submit(page)
        page.click("#omission-submit")
        page.wait_for_function(
            "document.getElementById('btn-submit').disabled === false")
        assert page.text_content("#btn-submit") == "Start the design"   # §BH55 Phase 3: was "→ Start Pipeline"

    # -- accessible modal behavior (§10) ---------------------------------------

    def test_dialog_is_modal_and_labelled(self):
        page = self._page()
        self._route(page)
        self._stage_and_go_packaging(page)
        self._submit(page)
        assert page.eval_on_selector(
            "#omission-dialog",
            "d => d.getAttribute('aria-modal')") == "true"
        assert page.eval_on_selector(
            "#omission-dialog",
            "d => d.getAttribute('aria-labelledby')") == "omission-title"
        assert "Submit Packaging without references?" in \
            page.text_content("#omission-title")

    def test_initial_focus_is_the_safe_action(self):
        page = self._page()
        self._route(page)
        self._stage_and_go_packaging(page)
        self._submit(page)
        assert page.evaluate("document.activeElement.id") == "omission-cancel"

    def test_tab_cycles_inside_the_dialog(self):
        page = self._page()
        self._route(page)
        self._stage_and_go_packaging(page)
        self._submit(page)
        for _ in range(5):
            page.keyboard.press("Tab")
            assert page.evaluate(
                "document.activeElement.closest('#omission-dialog') !== null")
        for _ in range(5):
            page.keyboard.press("Shift+Tab")
            assert page.evaluate(
                "document.activeElement.closest('#omission-dialog') !== null")

    def test_escape_behaves_as_cancel(self):
        page = self._page()
        seen = self._route(page)
        self._stage_and_go_packaging(page)
        self._submit(page)
        page.keyboard.press("Escape")
        assert self._dialog_open(page) is False
        assert seen["count"] == 0
        assert page.evaluate("DesignOSReferenceUI.count()") == 1
        assert page.evaluate("document.activeElement.id") == "btn-submit"

    def test_enter_on_open_activates_only_the_safe_default(self):
        # accidental Enter right after the dialog opens must cancel, not
        # confirm — initial focus sits on Cancel
        page = self._page()
        seen = self._route(page)
        self._stage_and_go_packaging(page)
        self._submit(page)
        page.keyboard.press("Enter")
        assert self._dialog_open(page) is False
        assert seen["count"] == 0
        assert page.evaluate("DesignOSReferenceUI.count()") == 1

    def test_background_controls_are_inert_while_open(self):
        page = self._page()
        seen = self._route(page)
        self._stage_and_go_packaging(page)
        self._submit(page)
        with pytest.raises(PWTimeoutError):
            page.click("#btn-submit", timeout=800)
        assert seen["count"] == 0
        assert self._dialog_open(page) is True

    # -- nothing real happened -----------------------------------------------

    def test_omission_flows_touch_no_server_state(self):
        assert DesignTask.objects.count() == 0
        assert TaskReference.objects.count() == 0
        assert ApiCallRecord.objects.count() == 0
