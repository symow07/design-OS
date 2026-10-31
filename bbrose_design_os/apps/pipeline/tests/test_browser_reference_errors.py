"""Real-browser tests for reference validation and error presentation (B4b-2B).

Two validation layers, one authority. The browser refuses only what it can
know without reading bytes — category, emptiness, extension, size from the
server-rendered configuration — and refused files never become entries, cards
or object URLs. Everything else is the server's verdict, delivered per file as
category + request-local file_index (never filename, which duplicates make
ambiguous) and worn by the STAGED card: the file stays present, previewed and
removable, because telling the owner to reselect a file that is still staged
would be a lie about state.

Every failure path used to be an alert(); these tests hold the replacement to
account — dialogs are recorded by the harness and asserted EMPTY throughout
the reference flows.
"""
from __future__ import annotations

import json

import pytest
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase
from django.test import override_settings

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    HAVE_PLAYWRIGHT = True
except ImportError:              # pragma: no cover
    HAVE_PLAYWRIGHT = False

from apps.pipeline.models import ApiCallRecord, DesignTask, TaskReference

from .test_browser_staged_reference_ui import RefUiHarness, _file

_OK = '{"task_id": 4242, "status": "queued"}'


def _rejection_body(rejections, message="No task was created. Fix the files "
                    "below and submit again."):
    return json.dumps({
        "error": "REFERENCE_VALIDATION_FAILED",
        "message": message,
        "rejections": rejections,
        "accepted_count": 0,
        "task_created": False,
        "references_created": 0,
        "preserved": {},
    })


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class ReferenceErrorBrowserTests(RefUiHarness, DrainedStaticLiveServerTestCase):

    # -- helpers -------------------------------------------------------------

    def _route(self, page, status=201, body=_OK, abort=False):
        seen = {"count": 0}

        def handle(route):
            seen["count"] += 1
            if abort:
                route.abort()
            else:
                route.fulfill(status=status,
                              content_type="application/json", body=body)

        page.route("**/api/tasks/create/", handle)
        page.route("**/api/tasks/4242/**", lambda r: r.fulfill(
            status=200, content_type="application/json", body="{}"))
        return seen

    def _submit(self, page, brief="a rose serum bottle"):
        page.fill("#task-input", brief)
        page.click("#btn-submit")
        page.wait_for_function(
            "document.getElementById('btn-submit').disabled === false")

    def _rows(self, page):
        return page.eval_on_selector_all(
            "#ref-errors .ref-error-row", "els => els.map(e => e.textContent)")

    def _marked(self, page):
        """Filenames of cards carrying a server verdict, in DOM order."""
        return page.eval_on_selector_all(
            ".ref-card.server-error .ref-card-name",
            "els => els.map(e => e.textContent)")

    # -- preliminary browser validation (§4/§5) ------------------------------

    def test_an_empty_file_is_refused_before_staging(self):
        page = self._page()
        page.set_input_files("#ref-input-container",
                             files=[_file("hollow.png", size=0)])
        assert page.evaluate("DesignOSReferenceUI.count()") == 0
        assert self._cards(page) == []
        # no entry means no object URL was ever created for it
        assert page.evaluate("window.__url.created") == 0
        rows = self._rows(page)
        assert len(rows) == 1
        assert "NOT ADDED" in rows[0]
        assert "hollow.png" in rows[0]
        assert "Container" in rows[0]
        assert "empty" in rows[0]

    def test_a_disallowed_extension_is_refused_with_the_allowed_list(self):
        page = self._page()
        page.set_input_files("#ref-input-logo",
                             files=[_file("notes.txt", "text/plain")])
        assert page.evaluate("DesignOSReferenceUI.count()") == 0
        rows = self._rows(page)
        assert "not supported" in rows[0]
        # the fix is named: the allowlist, from the rendered config
        for ext in ("PNG", "JPG", "PDF", "AI"):
            assert ext in rows[0]

    @override_settings(REFERENCE_MAX_UPLOAD_BYTES=200)
    def test_an_oversized_file_is_refused_using_the_rendered_limit(self):
        # the limit reaches the browser via #reference-config, not a copied
        # constant — overriding the setting must change what the CLIENT does
        page = self._page()
        assert page.eval_on_selector(
            "#reference-config",
            "el => el.dataset.maxBytes") == "200"
        page.set_input_files("#ref-input-container",
                             files=[_file("big.png", size=300)])
        assert page.evaluate("DesignOSReferenceUI.count()") == 0
        rows = self._rows(page)
        assert "per-file limit" in rows[0]
        assert "not added" in rows[0]

    def test_valid_siblings_still_stage_when_one_is_refused(self):
        page = self._page()
        page.set_input_files("#ref-input-container",
                             files=[_file("bad.txt", "text/plain"),
                                    _file("good.png")])
        # partition, not all-or-nothing: staging is local and reversible —
        # the server applies its own all-or-nothing rule at submission
        assert page.evaluate("DesignOSReferenceUI.count()") == 1
        assert len(self._cards(page, "container")) == 1
        rows = self._rows(page)
        assert len(rows) == 1 and "bad.txt" in rows[0]
        live = page.text_content("#ref-live")
        assert "Added 1 file" in live
        assert "1 file was not added" in live

    def test_the_browser_reads_no_signatures(self):
        # a .png whose bytes are nothing like PNG stages anyway — content
        # verdicts belong to the server, and the section says so
        page = self._page()
        page.set_input_files("#ref-input-container", files=[{
            "name": "liar.png", "mimeType": "image/png",
            "buffer": b"PK\x03\x04" + b"\x00" * 24}])
        assert page.evaluate("DesignOSReferenceUI.count()") == 1
        assert self._rows(page) == []
        section = " ".join(page.text_content("#reference-section").split())
        assert "final validation happens at submission" in section

    def test_a_client_refusal_is_dismissable(self):
        page = self._page()
        page.set_input_files("#ref-input-container",
                             files=[_file("bad.txt", "text/plain")])
        assert len(self._rows(page)) == 1
        page.click("#ref-errors .ref-error-dismiss")
        assert self._rows(page) == []

    def test_focus_moves_to_the_first_error_row(self):
        page = self._page()
        page.set_input_files("#ref-input-container",
                             files=[_file("bad.txt", "text/plain")])
        assert page.evaluate(
            "document.activeElement.classList.contains('ref-error-row')") \
            is True

    # -- server verdicts on staged cards (§7–§10) ----------------------------

    def test_a_server_rejection_marks_the_correct_card(self):
        page = self._page()
        self._route(page, status=400, body=_rejection_body([
            {"code": "REFERENCE_EXTENSION_TYPE_MISMATCH",
             "message": "raw server words",
             "filename": "b.png", "category": "container", "file_index": 1},
        ]))
        page.set_input_files("#ref-input-container",
                             files=[_file("a.png"), _file("b.png")])
        self._submit(page)
        assert self._marked(page) == ["b.png"]
        card_err = page.text_content(".ref-card.server-error .ref-card-error")
        assert card_err.startswith("REJECTED — ")
        # the owner sees OUR wording for a known code, not the raw payload
        assert "does not match the detected file content" in card_err
        assert "raw server words" not in card_err
        summary = page.text_content("#ref-errors .ref-error-summary")
        assert "No task was created" in summary
        assert "still staged in your browser" in summary

    def test_duplicate_filenames_mark_only_the_rejected_position(self):
        # two files, SAME name, same category — only index 0 is rejected.
        # Correlation by filename would mark both or the wrong one.
        page = self._page()
        self._route(page, status=400, body=_rejection_body([
            {"code": "REFERENCE_SIGNATURE_INVALID", "message": "x",
             "filename": "logo.png", "category": "container",
             "file_index": 0},
        ]))
        page.set_input_files("#ref-input-container",
                             files=[_file("logo.png"), _file("logo.png")])
        self._submit(page)
        states = page.eval_on_selector_all(
            ".ref-card", "els => els.map(e => e.classList.contains("
                         "'server-error'))")
        assert states == [True, False]

    def test_an_unknown_code_falls_back_to_the_server_message(self):
        page = self._page()
        self._route(page, status=400, body=_rejection_body([
            {"code": "REFERENCE_SOMETHING_NEW",
             "message": "a message only the server knows",
             "filename": "a.png", "category": "container", "file_index": 0},
        ]))
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        self._submit(page)
        assert "a message only the server knows" in \
            page.text_content(".ref-card-error")

    def test_rejected_files_stay_staged_previewed_and_removable(self):
        page = self._page()
        self._route(page, status=400, body=_rejection_body([
            {"code": "REFERENCE_SIGNATURE_INVALID", "message": "x",
             "filename": "a.png", "category": "container", "file_index": 0},
        ]))
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        self._submit(page)
        # still staged: entry, card, preview URL all intact
        assert page.evaluate("DesignOSReferenceUI.count()") == 1
        assert page.evaluate("window.__url.revoked") == 0
        assert page.eval_on_selector(".ref-card img.ref-card-thumb",
                                     "el => el.src.startsWith('blob:')")
        # and the advertised fix works: remove clears the verdict with it
        page.click(".ref-card.server-error .ref-card-remove")
        assert page.evaluate("DesignOSReferenceUI.count()") == 0
        assert self._marked(page) == []
        assert page.eval_on_selector_all(
            "#ref-errors .ref-error-summary", "els => els.length") == 0

    def test_task_text_survives_the_rejection(self):
        page = self._page()
        self._route(page, status=400, body=_rejection_body([
            {"code": "REFERENCE_FILE_EMPTY", "message": "x",
             "filename": "a.png", "category": "container", "file_index": 0},
        ]))
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        self._submit(page, brief="a very particular 30 ml serum bottle")
        assert page.input_value("#task-input") == \
            "a very particular 30 ml serum bottle"

    def test_an_unmatched_rejection_falls_back_to_an_error_row(self):
        # a rejection naming a position that is not in the inventory must
        # never crash and never mark an innocent card
        page = self._page()
        self._route(page, status=400, body=_rejection_body([
            {"code": "REFERENCE_SIGNATURE_INVALID", "message": "x",
             "filename": "ghost.png", "category": "logo", "file_index": 5},
        ]))
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        self._submit(page)
        assert self._marked(page) == []
        rows = self._rows(page)
        assert len(rows) == 1 and "ghost.png" in rows[0]

    def test_focus_lands_on_the_first_rejected_cards_remove(self):
        page = self._page()
        self._route(page, status=400, body=_rejection_body([
            {"code": "REFERENCE_SIGNATURE_INVALID", "message": "x",
             "filename": "a.png", "category": "container", "file_index": 0},
        ]))
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        self._submit(page)
        # focus is deferred one tick past the submit-lock release (a disabled
        # remove button cannot take focus), so wait for it rather than peek
        page.wait_for_function("""
          document.activeElement.classList.contains('ref-card-remove') &&
          document.activeElement.closest('.ref-card')
            .classList.contains('server-error')
        """)

    def test_the_rejection_is_announced_and_never_a_dialog(self):
        page = self._page()
        self._route(page, status=400, body=_rejection_body([
            {"code": "REFERENCE_SIGNATURE_INVALID", "message": "x",
             "filename": "a.png", "category": "container", "file_index": 0},
        ]))
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        self._submit(page)
        assert self.dialogs == []
        live = page.text_content("#ref-live")
        assert "The task was not created" in live
        assert "still staged" in live

    def test_resubmission_clears_stale_errors(self):
        page = self._page()
        seen = self._route(page, status=400, body=_rejection_body([
            {"code": "REFERENCE_SIGNATURE_INVALID", "message": "x",
             "filename": "bad.png", "category": "container",
             "file_index": 1},
        ]))
        page.set_input_files("#ref-input-container",
                             files=[_file("good.png"), _file("bad.png")])
        self._submit(page)
        assert self._marked(page) == ["bad.png"]
        # owner removes the rejected file and tries again — this time it works
        page.click(".ref-card.server-error .ref-card-remove")
        page.unroute("**/api/tasks/create/")
        self._route(page)
        self._submit(page)
        assert seen["count"] == 1  # first route saw exactly the first attempt
        assert page.eval_on_selector_all(
            "#ref-errors .ref-error-row", "els => els.length") == 0
        assert self._marked(page) == []
        assert page.evaluate("DesignOSReferenceUI.count()") == 0

    # -- general failures stay general (§12) ---------------------------------

    def test_network_failure_shows_a_general_error_not_per_file_marks(self):
        page = self._page()
        self._route(page, abort=True)
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        self._submit(page)
        assert self.dialogs == []
        general = page.text_content("#ref-errors .ref-error-general")
        assert "nothing was confirmed" in general
        assert "untouched" in general
        # no file was blamed for a transport problem
        assert self._marked(page) == []
        assert page.evaluate("DesignOSReferenceUI.count()") == 1

    def test_a_non_reference_server_error_is_general_on_container(self):
        page = self._page()
        self._route(page, status=500, body='{"error": "WORKER_UNAVAILABLE"}')
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        self._submit(page)
        assert self.dialogs == []
        general = page.text_content("#ref-errors .ref-error-general")
        assert "could not be created" in general
        assert "WORKER_UNAVAILABLE" in general
        assert self._marked(page) == []
        assert page.evaluate("DesignOSReferenceUI.count()") == 1

    def test_packaging_failures_are_said_in_the_page_never_a_browser_alert(self):
        # [his goal of 2026-10-13, (4): "No browser pop-ups anywhere ("127.0.0.1 says…"). Any confirmation happens
        # inside the page, in plain words, in the house style."] Packaging's failure is said in the page's own dialog
        page = self._page()
        self._route(page, status=500, body='{"error": "boom"}')
        page.click('.target-chip[data-target="packaging"]')
        self._submit(page)
        page.wait_for_selector("#ask-dialog[open]", timeout=10000)
        assert "boom" in page.text_content("#ask-words")
        assert self.dialogs == []
        assert page.eval_on_selector_all(
            "#ref-errors .ref-error-row", "els => els.length") == 0

    # -- nothing real happened -----------------------------------------------

    def test_error_flows_touch_no_server_state(self):
        assert DesignTask.objects.count() == 0
        assert TaskReference.objects.count() == 0
        assert ApiCallRecord.objects.count() == 0
