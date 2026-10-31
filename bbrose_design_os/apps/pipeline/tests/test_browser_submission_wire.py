"""Wire tests for direct submission integration (B4b-2A-3).

poll.js now appends Product Container references straight from the canonical
inventory via DesignOSReferenceUI.appendToFormData — no bridge global, no
native-FileList reading, no second payload builder. Every property here is
proven on the wire or in live browser state: requests are intercepted and
their multipart bodies parsed, forged input state is shown not to leak, and
the failure paths are exercised with aborted, 4xx and 5xx responses.

The pending-request tests use a deliberately stalled route: the handler
stashes the route without fulfilling it, the test asserts what the submitting
lock forbids while the request is genuinely in flight, and only then fulfils.
"""
from __future__ import annotations

import re

import pytest
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    HAVE_PLAYWRIGHT = True
except ImportError:              # pragma: no cover
    HAVE_PLAYWRIGHT = False

from apps.pipeline.models import ApiCallRecord, DesignTask, TaskReference

from .test_browser_staged_reference_ui import RefUiHarness, _file

_OK = '{"task_id": 4242, "status": "queued"}'
#: §BH69(2): what the read door answers for one picture — answered here, so no test reads (or spends) for real
_READ = ('{"sha256": "ab", "words": "Layout: a quiet centred mark.", "taken": {"layout": "a centred mark on a wide '
         'quiet field", "mood": "calm", "finish": "soft-touch matte", "type_style": "thin serif capitals", '
         '"colour_words": "blush with warm gold", "take": "quiet space around one gold line"}, '
         '"seen_not_taken": ["LUMIERE PARIS"], "cost_usd": "0.012", "read_before": false}')


def _part_names(body: bytes):
    """(field, filename) pairs for every file part, in wire order."""
    return re.findall(
        rb'name="([a-z_]+)"; filename="([^"]+)"', body)


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class SubmissionWireTests(RefUiHarness, DrainedStaticLiveServerTestCase):

    # -- helpers -------------------------------------------------------------

    def _capture(self, page, status=201, body=_OK, abort=False):
        captured = {"count": 0}

        def handle(route):
            captured["count"] += 1
            captured["content_type"] = \
                route.request.headers.get("content-type", "")
            captured["body"] = route.request.post_data_buffer
            if abort:
                route.abort()
            else:
                route.fulfill(status=status,
                              content_type="application/json", body=body)

        page.route("**/api/tasks/create/", handle)
        page.route("**/api/tasks/4242/**", lambda r: r.fulfill(
            status=200, content_type="application/json", body="{}"))
        return captured

    def _submit(self, page, brief="a rose serum bottle"):
        page.fill("#task-input", brief)
        page.click("#btn-submit")
        page.wait_for_function(
            "document.getElementById('btn-submit').disabled === false")

    # -- the payload ---------------------------------------------------------

    def test_zero_references_is_a_valid_multipart_request(self):
        page = self._page()
        cap = self._capture(page)
        self._submit(page)
        assert cap["count"] == 1
        assert cap["content_type"].startswith("multipart/form-data")
        assert _part_names(cap["body"]) == []
        assert b'name="design_target"\r\n\r\nproduct_container' in cap["body"]

    def test_all_five_categories_arrive_once_each_in_order(self):
        # Rescue Day 1: the fifth picture is staged without a paid read, then sent after the other four.
        page = self._page()
        cap = self._capture(page)
        reads = []
        page.route("**/api/inspiration/read/", lambda r: (reads.append(r.request.url), r.abort()))
        for kind in ("container", "logo", "label", "color"):
            page.set_input_files(f"#ref-input-{kind}",
                                 files=[_file(f"{kind}-ref.png")])
        page.set_input_files("#inspiration-input", files=[_file("inspiration-ref.png")])
        page.wait_for_selector("#inspiration-list .inspire-item")
        assert "Added — read after Start" in page.text_content("#inspiration-list")
        assert page.locator("#inspiration-list .reading, #inspiration-list .read").count() == 0
        self._submit(page)
        assert reads == []
        assert _part_names(cap["body"]) == [
            (b"container", b"container-ref.png"),
            (b"logo", b"logo-ref.png"),
            (b"label", b"label-ref.png"),
            (b"color", b"color-ref.png"),
            (b"inspiration_picture", b"inspiration-ref.png"),
        ]
        assert b'name="colour"' not in cap["body"]

    def test_duplicates_and_same_file_twice_arrive_as_distinct_parts(self):
        page = self._page()
        cap = self._capture(page)
        page.set_input_files("#ref-input-container",
                             files=[_file("same.png"), _file("same.png")])
        # the SAME File object staged twice, through the controller
        page.evaluate("""
          (() => {
            const f = new File([new Uint8Array(4)], 'twin.png',
                               {type: 'image/png'});
            DesignOSReferenceUI.controller.addFiles('logo', [f]);
            DesignOSReferenceUI.controller.addFiles('logo', [f]);
          })()
        """)
        self._submit(page)
        assert _part_names(cap["body"]) == [
            (b"container", b"same.png"), (b"container", b"same.png"),
            (b"logo", b"twin.png"), (b"logo", b"twin.png"),
        ]

    def test_removed_files_do_not_arrive(self):
        page = self._page()
        cap = self._capture(page)
        page.set_input_files("#ref-input-container",
                             files=[_file("keep.png"), _file("drop.png")])
        page.evaluate("""
          (() => {
            const doomed = DesignOSReferenceUI.list()
              .find(e => e.name === 'drop.png');
            DesignOSReferenceUI.controller.remove(doomed.id);
          })()
        """)
        self._submit(page)
        assert _part_names(cap["body"]) == [(b"container", b"keep.png")]

    def test_forged_native_input_state_cannot_reach_the_payload(self):
        """Native inputs are pickers, not state: files planted in them without
        staging never arrive, and cannot duplicate what was staged."""
        page = self._page()
        cap = self._capture(page)
        page.set_input_files("#ref-input-container", files=[_file("real.png")])
        page.evaluate("""
          (() => {
            const dt = new DataTransfer();
            dt.items.add(new File([new Uint8Array(3)], 'planted.png',
                                  {type: 'image/png'}));
            dt.items.add(new File([new Uint8Array(3)], 'real.png',
                                  {type: 'image/png'}));
            // programmatic assignment fires no change event — nothing stages
            document.getElementById('ref-input-logo').files = dt.files;
            document.getElementById('ref-input-container').files = dt.files;
          })()
        """)
        self._submit(page)
        assert _part_names(cap["body"]) == [(b"container", b"real.png")]

    def test_submission_works_with_datatransfer_removed(self):
        """2A-3 needs no browser file-transfer capability anywhere."""
        page = self._page(extra_init="window.DataTransfer = undefined;")
        cap = self._capture(page)
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        self._submit(page)
        assert _part_names(cap["body"]) == [(b"container", b"a.png")]
        assert page.evaluate("DesignOSReferenceUI.count()") == 0  # cleaned up

    # -- append is target-scoped ---------------------------------------------

    def test_append_is_called_for_container_and_not_for_packaging(self):
        page = self._page()
        cap = self._capture(page)
        page.evaluate("""
          (() => {
            const orig = DesignOSReferenceUI.appendToFormData;
            window.__appendCalls = 0;
            DesignOSReferenceUI.appendToFormData = function (fd) {
              window.__appendCalls++; return orig(fd);
            };
          })()
        """)
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        self._submit(page)
        assert page.evaluate("window.__appendCalls") == 1
        # now Packaging, with a file still staged afterwards? inventory was
        # cleared by success — stage another to prove it is HELD, not sent.
        # B4b-2C: submitting Packaging with held files opens the omission
        # dialog first; the dispatch happens only through explicit confirm.
        page.set_input_files("#ref-input-container", files=[_file("b.png")])
        page.click('.target-chip[data-target="packaging"]')
        self._submit(page, brief="a folding carton")
        assert cap["count"] == 1                 # intercepted, not sent yet
        page.click("#omission-submit")
        page.wait_for_function(
            "document.getElementById('btn-submit').disabled === false")
        assert cap["count"] == 2
        assert cap["content_type"].startswith("application/json")
        assert b"filename=" not in cap["body"]
        assert b"b.png" not in cap["body"]
        assert page.evaluate("window.__appendCalls") == 1   # unchanged
        # §6: confirmed Packaging success after omission approval clears the
        # held inventory — the owner agreed those references would not be used
        assert page.evaluate("DesignOSReferenceUI.count()") == 0

    # -- submission lifecycle ------------------------------------------------

    def test_double_click_produces_one_request(self):
        page = self._page()
        cap = self._capture(page)
        page.fill("#task-input", "a serum bottle")
        page.evaluate("""
          (() => {
            const b = document.getElementById('btn-submit');
            b.click(); b.click();
          })()
        """)
        page.wait_for_function(
            "document.getElementById('btn-submit').disabled === false")
        assert cap["count"] == 1

    def test_in_flight_request_blocks_staging_and_removal(self):
        page = self._page()
        stalled = {}

        def handle(route):
            stalled["route"] = route          # deliberately not fulfilled yet

        page.route("**/api/tasks/create/", handle)
        page.route("**/api/tasks/4242/**", lambda r: r.fulfill(
            status=200, content_type="application/json", body="{}"))
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        page.fill("#task-input", "a serum bottle")
        page.click("#btn-submit")
        page.wait_for_function("() => window.DesignOSReferenceUI"
                               ".controller.isSubmitting()")
        locked = page.evaluate("""
          (() => {
            const id = DesignOSReferenceUI.list()[0].id;
            return {
              add: DesignOSReferenceUI.controller
                     .addFiles('logo', []).error || 'SUBMITTING',
              remove: DesignOSReferenceUI.controller.remove(id).error,
              inputDisabled: document.getElementById('ref-input-logo').disabled,
              removeDisabled: document.querySelector('.ref-card-remove')
                                 .disabled,
              cardsVisible: document.querySelectorAll('.ref-card').length,
            };
          })()
        """)
        assert locked == {"add": "SUBMITTING", "remove": "SUBMITTING",
                          "inputDisabled": True, "removeDisabled": True,
                          "cardsVisible": 1}
        stalled["route"].fulfill(status=201,
                                 content_type="application/json", body=_OK)
        page.wait_for_function(
            "document.getElementById('btn-submit').disabled === false")
        assert page.evaluate("DesignOSReferenceUI.count()") == 0

    @pytest.mark.filterwarnings("ignore")
    def test_failed_requests_retain_everything(self):
        for mode in ({"abort": True}, {"status": 400,
                                       "body": '{"error": "bad"}'},
                     {"status": 500, "body": '{"error": "boom"}'}):
            page = self._page()
            cap = self._capture(page, **mode)
            page.set_input_files("#ref-input-container",
                                 files=[_file("kept.png")])
            created = page.evaluate("window.__url.created")
            self._submit(page)
            assert cap["count"] == 1
            # inventory, cards and object URLs all survive the failure
            assert page.evaluate("DesignOSReferenceUI.count()") == 1
            assert page.eval_on_selector_all(
                ".ref-card", "els => els.length") == 1
            assert page.evaluate("window.__url.revoked") == 0
            assert page.evaluate("window.__url.created") == created
            # and interaction is restored
            assert page.evaluate("""
              DesignOSReferenceUI.controller
                .addFiles('logo', []).ok
            """) is True
            page.close()

    def test_a_started_design_opens_on_its_own_page(self):
        # [the owner's answer to the UI directions of 2026-09-25: the start page holds no design — a started one opens
        # on its own page, told here through the one seam the harness holds still]
        page = self._page()
        self._capture(page)
        self._submit(page)
        assert page.evaluate("window.__opened") == 4242
        assert page.evaluate("location.pathname") == "/dashboard/new/classic/"

    def test_success_clears_inventory_cards_urls_and_pickers(self):
        page = self._page()
        self._capture(page)
        page.set_input_files("#ref-input-container",
                             files=[_file("a.png"),
                                    _file("d.pdf", "application/pdf")])
        self._submit(page)
        assert page.evaluate("DesignOSReferenceUI.count()") == 0
        assert page.eval_on_selector_all(".ref-card",
                                         "els => els.length") == 0
        assert page.evaluate(
            "window.__url.revoked === window.__url.created") is True
        assert page.evaluate("""
          Array.from(document.querySelectorAll('input.ref-input'))
               .every(i => i.value === '' && i.files.length === 0)
        """) is True

    # -- pre-dispatch failure safety -----------------------------------------

    def test_missing_handle_prevents_dispatch(self):
        page = self._page()
        cap = self._capture(page)
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        page.evaluate("delete window.DesignOSReferenceUI")
        page.fill("#task-input", "a serum bottle")
        page.click("#btn-submit")
        page.wait_for_function(
            "document.getElementById('btn-submit').disabled === false")
        assert cap["count"] == 0
        # B4b-2B: structured error row, not a dialog (REFERENCE_UI_UNAVAILABLE)
        assert self.dialogs == []
        row = page.text_content("#ref-errors .ref-error-row")
        assert "did not initialise" in row and "Nothing was sent" in row
        assert page.text_content("#ref-live") != ""

    def test_append_exception_prevents_dispatch_and_retains_files(self):
        page = self._page()
        cap = self._capture(page)
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        # NB: if an evaluated expression YIELDS a function, Playwright calls
        # it — wrap the assignment so nothing is returned
        page.evaluate("""
          (() => {
            DesignOSReferenceUI.appendToFormData =
              function () { throw new Error('boom'); };
          })()
        """)
        page.fill("#task-input", "a serum bottle")
        page.click("#btn-submit")
        page.wait_for_function(
            "document.getElementById('btn-submit').disabled === false")
        assert cap["count"] == 0
        # B4b-2B: structured general error, not a dialog
        assert self.dialogs == []
        row = page.text_content("#ref-errors .ref-error-general")
        assert "could not be attached" in row
        assert "still staged" in row
        assert page.evaluate("DesignOSReferenceUI.count()") == 1
        # no stack trace or internal detail leaked into the rendered error
        assert "boom" not in page.text_content("#ref-errors")

    # -- nothing real happened -----------------------------------------------

    def test_wire_tests_touch_no_server_state(self):
        assert DesignTask.objects.count() == 0
        assert TaskReference.objects.count() == 0
        assert ApiCallRecord.objects.count() == 0


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class InspirationBoxWireTests(RefUiHarness, DrainedStaticLiveServerTestCase):
    """Rescue Day 1: stage locally; retain uploads until Start succeeds, with no pre-Start paid read."""

    def _capture(self, page):
        captured = {"count": 0}

        def handle(route):
            captured["count"] += 1
            captured["body"] = route.request.post_data_buffer
            captured["content_type"] = route.request.headers.get("content-type", "")
            route.fulfill(status=201, content_type="application/json", body=_OK)
        page.route("**/api/tasks/create/", handle)
        page.route("**/api/tasks/4242/**", lambda r: r.fulfill(status=200, content_type="application/json", body="{}"))
        return captured

    def test_a_carton_stages_an_inspiration_picture_locally_and_carries_it_with_start(self):
        page = self._page()
        cap = self._capture(page)
        reads = []
        page.route("**/api/inspiration/read/", lambda r: (reads.append(r.request.url), r.abort()))
        page.click('.target-chip[data-target="packaging"]')
        page.set_input_files("#inspiration-input", files=[_file("pin.png")])
        page.wait_for_selector("#inspiration-list .inspire-item")
        item = page.text_content("#inspiration-list .inspire-item")
        assert "pin.png" in item and "Added — read after Start" in item
        assert page.locator("#inspiration-list .inspire-read, #inspiration-list .inspire-cost").count() == 0
        assert reads == []
        page.fill("#task-input", "a carton for the night oil")
        page.click("#btn-submit")
        page.wait_for_function("window.__opened === 4242")
        assert cap["count"] == 1 and cap["content_type"].startswith("multipart/form-data")
        assert _part_names(cap["body"]) == [(b"inspiration_picture", b"pin.png")]
        assert b'name="design_target"\r\n\r\npackaging' in cap["body"]
        assert reads == []

    def test_start_retains_staged_picture_until_submission_succeeds_without_a_read(self):
        page = self._page()
        held, reads = [], []
        page.route("**/api/tasks/create/", lambda r: held.append(r))
        page.route("**/api/tasks/4242/**", lambda r: r.fulfill(
            status=200, content_type="application/json", body="{}"))
        page.route("**/api/inspiration/read/", lambda r: (reads.append(r.request.url), r.abort()))
        page.click('.target-chip[data-target="packaging"]')
        page.set_input_files("#inspiration-input", files=[_file("pin.png")])
        page.wait_for_selector("#inspiration-list .inspire-item")
        assert held == [] and reads == []
        page.fill("#task-input", "a carton for the night oil")
        with page.expect_request("**/api/tasks/create/"):
            page.click("#btn-submit")
        page.wait_for_timeout(100)
        assert len(held) == 1 and reads == []
        assert page.locator("#btn-submit").is_disabled()
        assert page.locator("#inspiration-list .inspire-item").count() == 1
        assert _part_names(held[0].request.post_data_buffer) == [(b"inspiration_picture", b"pin.png")]
        held[0].fulfill(status=201, content_type="application/json", body=_OK)
        page.wait_for_function("window.__opened === 4242")
        assert page.locator("#inspiration-list .inspire-item").count() == 0
        assert page.evaluate("DesignOSInspiration.count()") == 0
        assert reads == []
