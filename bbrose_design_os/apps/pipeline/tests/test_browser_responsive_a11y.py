"""Responsive and accessibility validation for the B4b-2 workflow (§11/§16).

Geometry over vibes: these tests measure real boxes in a real 390 px
viewport — page overflow, card containment, control reachability, dialog
fit — and assert the accessibility contract (labels, live regions, textual
state markers) that the visual states rely on. Screenshots are evidence;
these assertions are the gate.
"""
from __future__ import annotations

import pytest
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    HAVE_PLAYWRIGHT = True
except ImportError:              # pragma: no cover
    HAVE_PLAYWRIGHT = False

from .test_browser_staged_reference_ui import RefUiHarness, _file

_OK = '{"task_id": 4242, "status": "queued"}'
MOBILE = {"width": 390, "height": 844}

LONG_NAME = ("an-extremely-long-reference-filename-that-keeps-going-"
             "and-going-for-the-hit-test_final_v2_APPROVED_copy.png")


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class ResponsiveA11yBrowserTests(RefUiHarness, DrainedStaticLiveServerTestCase):

    def _mobile(self):
        return self._page(viewport=MOBILE)

    # -- mobile geometry (§11) ------------------------------------------------

    def test_no_horizontal_overflow_at_390(self):
        page = self._mobile()
        page.set_input_files("#ref-input-container",
                             files=[_file(LONG_NAME), _file("b.pdf",
                                                            "application/pdf")])
        assert page.evaluate(
            "document.documentElement.scrollWidth <= "
            "document.documentElement.clientWidth") is True

    def test_categories_stack_in_one_column_at_390(self):
        page = self._mobile()
        xs = page.eval_on_selector_all(
            ".ref-category",
            "els => els.map(e => Math.round(e.getBoundingClientRect().left))")
        assert len(set(xs)) == 1   # all five share one left edge

    def test_cards_stay_inside_their_container(self):
        page = self._mobile()
        page.set_input_files("#ref-input-container",
                             files=[_file(LONG_NAME), _file("b.png")])
        assert page.evaluate("""
          (() => {
            const grid = document.getElementById('reference-categories-grid')
                                 .getBoundingClientRect();
            return Array.from(document.querySelectorAll('.ref-card'))
              .every(c => {
                const r = c.getBoundingClientRect();
                return r.left >= grid.left - 1 && r.right <= grid.right + 1;
              });
          })()
        """) is True

    def test_long_filenames_do_not_cover_the_remove_button(self):
        # the 2A-2 defect class: overflowing inline text hit-testing above
        # the button. A REAL mouse click must reach the control.
        page = self._mobile()
        page.set_input_files("#ref-input-container", files=[_file(LONG_NAME)])
        page.click(".ref-card .ref-card-remove")
        assert page.evaluate("DesignOSReferenceUI.count()") == 0

    def test_cards_are_scannable_in_the_narrow_desktop_panel(self):
        # the grid must answer to its CONTAINER: in the ~250px queue panel a
        # second column crushed filenames to one ellipsised letter (found in
        # screenshot inspection) — a card's name needs real width to scan
        page = self._page()
        page.set_input_files("#ref-input-container", files=[_file(LONG_NAME)])
        assert page.eval_on_selector(
            ".ref-card .ref-card-name",
            "el => el.getBoundingClientRect().width") >= 80

    def test_raster_previews_keep_aspect_ratio(self):
        page = self._mobile()
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        # a fixed thumb box may crop or letterbox, never distort
        assert page.eval_on_selector(
            ".ref-card img",
            "i => getComputedStyle(i).objectFit") == "contain"

    def test_error_rows_fit_without_clipping_at_390(self):
        page = self._mobile()
        page.set_input_files(
            "#ref-input-container",
            files=[_file(LONG_NAME.replace(".png", ".txt"), "text/plain")])
        assert page.eval_on_selector_all(
            "#ref-errors .ref-error-row", "els => els.length") == 1
        assert page.evaluate("""
          (() => {
            const row = document.querySelector('#ref-errors .ref-error-row')
                                .getBoundingClientRect();
            return row.right <= document.documentElement.clientWidth &&
                   row.left >= 0;
          })()
        """) is True

    def test_held_notice_wraps_within_the_viewport(self):
        page = self._mobile()
        page.set_input_files("#ref-input-container",
                             files=[_file("a.png"), _file("b.png")])
        page.click('.target-chip[data-target="packaging"]')
        assert page.evaluate("""
          (() => {
            const n = document.getElementById('ref-held-notice')
                              .getBoundingClientRect();
            return n.right <= document.documentElement.clientWidth &&
                   n.width > 0;
          })()
        """) is True

    def test_dialog_fits_inside_the_mobile_viewport(self):
        page = self._mobile()
        page.route("**/api/tasks/create/", lambda r: r.fulfill(
            status=201, content_type="application/json", body=_OK))
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        page.click('.target-chip[data-target="packaging"]')
        page.fill("#task-input", "a folding carton")
        page.click("#btn-submit")
        page.wait_for_selector("#omission-dialog[open]")
        box = page.eval_on_selector(
            "#omission-dialog", """d => {
              const r = d.getBoundingClientRect();
              return {l: r.left, r: r.right, t: r.top, b: r.bottom};
            }""")
        assert box["l"] >= 0 and box["t"] >= 0
        assert box["r"] <= MOBILE["width"]
        assert box["b"] <= MOBILE["height"]

    def test_dialog_actions_reachable_by_keyboard_on_mobile(self):
        page = self._mobile()
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        page.click('.target-chip[data-target="packaging"]')
        page.fill("#task-input", "a folding carton")
        page.click("#btn-submit")
        page.wait_for_selector("#omission-dialog[open]")
        seen = set()
        for _ in range(4):
            seen.add(page.evaluate("document.activeElement.id"))
            page.keyboard.press("Tab")
        assert {"omission-cancel", "omission-return",
                "omission-submit"} <= seen
        page.keyboard.press("Escape")

    def test_focus_outline_is_visible_on_mobile_remove_control(self):
        page = self._mobile()
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        page.focus(".ref-card .ref-card-remove")
        # :focus-visible outline is keyboard-only; force-check the declared
        # rule instead of a heuristic screenshot diff
        assert page.evaluate("""
          (() => {
            const el = document.querySelector('.ref-card .ref-card-remove');
            for (const sheet of document.styleSheets) {
              let rules; try { rules = sheet.cssRules; } catch (e) { continue; }
              for (const r of rules) {
                if (r.selectorText &&
                    r.selectorText.includes('.ref-card-remove:focus-visible') &&
                    r.style.outline) return true;
              }
            }
            return false;
          })()
        """) is True

    # -- accessibility contract (§16) -----------------------------------------

    def test_held_notice_is_a_labelled_live_region(self):
        page = self._page()
        assert page.eval_on_selector(
            "#ref-held-notice", "el => el.getAttribute('role')") == "status"

    def test_state_markers_are_textual_not_color_only(self):
        page = self._page()
        # drag-active: the drop text changes, not just the border colour
        page.evaluate("""
          (() => {
            const zone = document.querySelector(
              '.ref-zone[data-kind="container"]');
            const dt = new DataTransfer();
            zone.dispatchEvent(new DragEvent('dragover',
              {bubbles: true, cancelable: true, dataTransfer: dt}));
          })()
        """)
        assert "Release to add files" in page.text_content(
            '.ref-zone[data-kind="container"] .ref-zone-drop')
        # NOT ADDED badge and REJECTED prefix are words, asserted elsewhere;
        # REFERENCE ONLY badge is rendered per card
        page.set_input_files("#ref-input-logo", files=[_file("a.png")])
        assert "REFERENCE ONLY" in page.text_content(".ref-card")

    def test_remove_controls_keep_explicit_labels(self):
        page = self._page()
        page.set_input_files("#ref-input-logo", files=[_file("mark.png")])
        label = page.eval_on_selector(
            ".ref-card .ref-card-remove",
            "b => b.getAttribute('aria-label')")
        assert "mark.png" in label
        assert "Brand Logo" in label

    def test_b4b2b_error_focus_still_works_at_390(self):
        page = self._mobile()
        page.set_input_files("#ref-input-container",
                             files=[_file("bad.txt", "text/plain")])
        assert page.evaluate(
            "document.activeElement.classList.contains('ref-error-row')") \
            is True

    def test_aria_live_region_still_announces(self):
        page = self._page()
        assert page.eval_on_selector(
            "#ref-live", "el => el.getAttribute('aria-live')") == "polite"
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        assert "Added 1 file" in page.text_content("#ref-live")
