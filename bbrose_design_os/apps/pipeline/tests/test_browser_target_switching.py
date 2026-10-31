"""Real-browser tests for target-switch state preservation (B4b-2C §2/§3/§8).

Switching the design target is a VIEW change, never a state change. The
canonical staged-reference inventory (entries, client ids, insertion order,
object URLs, server verdicts, preliminary error rows) must ride out any
number of Product Container → Packaging → Product Container round trips
untouched, and while Packaging is selected a held-reference notice — counted
from the controller alone — speaks for the hidden files.

Nothing here reconstructs state from filenames, DOM cards, native inputs or
web storage; the assertions check exactly that by comparing controller
snapshots and URL-recorder counters across switches.
"""
from __future__ import annotations

import pytest
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    HAVE_PLAYWRIGHT = True
except ImportError:              # pragma: no cover
    HAVE_PLAYWRIGHT = False

from .test_browser_reference_errors import _rejection_body
from .test_browser_staged_reference_ui import RefUiHarness, _file

_OK = '{"task_id": 4242, "status": "queued"}'


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class TargetSwitchBrowserTests(RefUiHarness, DrainedStaticLiveServerTestCase):

    # -- helpers -------------------------------------------------------------

    def _switch(self, page, target):
        page.click(f'.target-chip[data-target="{target}"]')

    def _notice(self, page):
        el = page.query_selector("#ref-held-notice")
        return None if el.get_attribute("hidden") is not None \
            else el.text_content()

    def _ids(self, page):
        return page.evaluate(
            "DesignOSReferenceUI.list().map(e => e.id)")

    def _count_requests(self, page):
        seen = {"count": 0}
        page.route("**/api/tasks/create/",
                   lambda r: (seen.__setitem__("count", seen["count"] + 1),
                              r.fulfill(status=201,
                                        content_type="application/json",
                                        body=_OK)))
        return seen

    # -- §BH70(1), item 15: the product hints for a Complete Product -------------

    def test_bh70_a_complete_product_shows_the_product_hints_and_starts_with_them(self):
        """§BH70(1), item 15: the hints sat inside the Product Container's panel, so a Complete Product — whose first
        stage is a product container — showed none and sent none. Chosen, it shows them (its references stay the
        Product Container's), and Start sends them in the brief its container stage reads."""
        import json
        page = self._page()
        page.route("**/api/tasks/create/", lambda r: r.fulfill(status=201, content_type="application/json", body=_OK))
        self._switch(page, "complete_product")
        assert page.is_visible("#product-hints")
        assert not page.is_visible("#reference-section")
        page.select_option("#container-archetype", "lipstick")
        page.fill("#container-closure", "magnetic cap")
        page.fill("#task-input", "a rose lipstick in a gold case")
        with page.expect_request("**/api/tasks/create/") as sent:
            page.click("#btn-submit")
        body = json.loads(sent.value.post_data)
        assert body["design_target"] == "complete_product"
        assert "[Container type: lipstick; Closure: magnetic cap]" in body["task_text"], body["task_text"]

    def test_his_122_new_design_sends_the_optional_sku_he_types(self):
        """[His answers after 122 was redrawn, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md), (1): "Add an optional SKU field on
        New design"] — sent with Start when he types one, for every kind of design; nothing sent when he leaves it empty."""
        import json
        page = self._page()
        page.route("**/api/tasks/create/", lambda r: r.fulfill(status=201, content_type="application/json", body=_OK))
        assert page.is_visible("#sku-input") and "optional" in page.inner_text('label[for="sku-input"]')
        for target, sku in (("complete_product", "BBR-HC-122"), ("packaging", "")):
            self._switch(page, target)
            page.fill("#sku-input", sku)
            page.fill("#task-input", "a rose hand cream")
            with page.expect_request("**/api/tasks/create/") as sent:
                page.click("#btn-submit")
            body = json.loads(sent.value.post_data)
            assert body.get("sku") == (sku or None), body
            page.goto(page.url)
            page.wait_for_selector("#btn-submit")

    def test_his_goal_of_2026_10_06_item_1_a_container_type_his_brief_does_not_name_is_asked_on_the_page(self):
        """His goal of 2026-10-06, item 1, design 120 at the page: Jar chosen, "squeeze tube" written. The server's own
        question (``form_question`` answers each request here) is asked in the page's dialog; "Tube — your brief's
        words" sets the Container type list itself and starts as a tube; "Jar — your Container type" keeps his choice
        and says so once (form_confirmed). Nothing starts before he answers."""
        import json
        import re

        from apps.pipeline.targets.container import form_question
        sent = []

        def answer(route):
            body = json.loads(route.request.post_data)
            sent.append(body)
            asked = form_question(body["task_text"], confirmed=bool(body.get("form_confirmed")))
            route.fulfill(status=409 if asked else 201, content_type="application/json",
                          body=json.dumps(asked) if asked else _OK)
        brief = "Rose Rebel Hand Cream (test)\n\nType: hand cream in a squeeze tube with a flip-top cap."
        for pick, expect in (("Tube — your brief's words", ("tube", None)),
                             ("Jar — your Container type", ("jar", True))):
            sent.clear()
            page = self._page()
            page.evaluate("window.BBROSE_OPEN_DESIGN = function () {}")
            page.route("**/api/tasks/create/", answer)
            self._switch(page, "complete_product")
            page.select_option("#container-archetype", "jar")
            page.fill("#task-input", brief)
            page.click("#btn-submit")
            page.wait_for_selector("#gloss-dialog[open]")
            assert page.text_content("#gloss-title") == "Jar or Tube?"
            assert len(sent) == 1
            page.click('#gloss-choices button:has-text("%s")' % pick)
            page.wait_for_function("() => !document.querySelector('#gloss-dialog').open")
            page.wait_for_timeout(300)
            assert len(sent) == 2, sent
            started = sent[-1]
            assert re.search(r"\[Container type: %s[;\]]" % expect[0], started["task_text"]), started["task_text"]
            assert started.get("form_confirmed") is expect[1], started
            page.context.close()

    # -- inventory survives the round trip -----------------------------------

    def test_staged_files_survive_switching_to_packaging(self):
        page = self._page()
        page.set_input_files("#ref-input-container",
                             files=[_file("a.png"), _file("b.pdf",
                                                          "application/pdf")])
        self._switch(page, "packaging")
        assert page.evaluate("DesignOSReferenceUI.count()") == 2

    def test_switching_hides_the_references_editor(self):
        page = self._page()
        assert page.is_visible("#reference-section")
        self._switch(page, "packaging")
        assert not page.is_visible("#reference-section")
        assert not page.is_visible("#container-inputs")

    def test_switching_back_restores_cards_ids_order_and_urls(self):
        page = self._page()
        page.set_input_files("#ref-input-container",
                             files=[_file("first.png"), _file("second.png")])
        page.set_input_files("#ref-input-logo", files=[_file("mark.png")])
        ids = self._ids(page)
        created = page.evaluate("window.__url.created")
        srcs = page.eval_on_selector_all(
            ".ref-card img", "els => els.map(e => e.src)")
        self._switch(page, "packaging")
        self._switch(page, "product_container")
        # same entries, same client ids, same order — nothing restaged
        assert self._ids(page) == ids
        assert page.eval_on_selector_all(
            ".ref-card", "els => els.map(e => e.dataset.refId)") == ids
        # same object URLs: none revoked, none newly created
        assert page.evaluate("window.__url.created") == created
        assert page.evaluate("window.__url.revoked") == 0
        assert page.eval_on_selector_all(
            ".ref-card img", "els => els.map(e => e.src)") == srcs
        assert page.is_visible("#reference-section")

    def test_server_error_states_survive_the_round_trip(self):
        page = self._page()
        page.route("**/api/tasks/create/", lambda r: r.fulfill(
            status=400, content_type="application/json",
            body=_rejection_body([
                {"code": "REFERENCE_SIGNATURE_INVALID", "message": "x",
                 "filename": "bad.png", "category": "container",
                 "file_index": 1}])))
        page.set_input_files("#ref-input-container",
                             files=[_file("good.png"), _file("bad.png")])
        page.fill("#task-input", "a serum bottle")
        page.click("#btn-submit")
        page.wait_for_function(
            "document.getElementById('btn-submit').disabled === false")
        marked = page.eval_on_selector_all(
            ".ref-card", "els => els.map(e => e.classList.contains("
                         "'server-error'))")
        assert marked == [False, True]
        self._switch(page, "packaging")
        self._switch(page, "product_container")
        assert page.eval_on_selector_all(
            ".ref-card", "els => els.map(e => e.classList.contains("
                         "'server-error'))") == [False, True]
        # the error summary is preserved, not duplicated
        assert page.eval_on_selector_all(
            "#ref-errors .ref-error-summary", "els => els.length") == 1

    def test_preliminary_error_rows_are_preserved_not_duplicated(self):
        page = self._page()
        page.set_input_files("#ref-input-container",
                             files=[_file("bad.txt", "text/plain"),
                                    _file("good.png")])
        assert page.eval_on_selector_all(
            "#ref-errors .ref-error-row", "els => els.length") == 1
        self._switch(page, "packaging")
        self._switch(page, "product_container")
        assert page.eval_on_selector_all(
            "#ref-errors .ref-error-row", "els => els.length") == 1

    def test_switching_dispatches_no_request(self):
        page = self._page()
        seen = self._count_requests(page)
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        for _ in range(3):
            self._switch(page, "packaging")
            self._switch(page, "product_container")
        assert seen["count"] == 0

    # -- held-reference notice (§3) ------------------------------------------

    def test_notice_hidden_on_container_and_at_zero(self):
        page = self._page()
        # on Product Container: never shown, staged or not
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        assert self._notice(page) is None
        # on Packaging with zero staged: not shown
        page.evaluate("DesignOSReferenceUI.controller.clear("
                      "{confirmedSuccess: true})")
        self._switch(page, "packaging")
        assert self._notice(page) is None

    def test_notice_shows_exact_count_and_plurals(self):
        page = self._page()
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        self._switch(page, "packaging")
        text = self._notice(page)
        assert "1 Product Container reference file is being held." in text
        assert "will not be attached to this Packaging task" in text
        self._switch(page, "product_container")
        page.set_input_files("#ref-input-logo",
                             files=[_file("b.png"), _file("c.png")])
        self._switch(page, "packaging")
        assert "3 Product Container reference files are being held." in \
            self._notice(page)

    def test_preliminary_rejections_never_inflate_the_count(self):
        page = self._page()
        page.set_input_files("#ref-input-container",
                             files=[_file("good.png"),
                                    _file("bad.txt", "text/plain"),
                                    _file("empty.png", size=0)])
        self._switch(page, "packaging")
        assert "1 Product Container reference file is being held." in \
            self._notice(page)

    def test_notice_updates_immediately_and_disappears_at_zero(self):
        page = self._page()
        page.set_input_files("#ref-input-container",
                             files=[_file("a.png"), _file("b.png")])
        self._switch(page, "packaging")
        assert "2 Product Container reference files" in self._notice(page)
        # count changes while Packaging is selected must reflect immediately
        page.evaluate("""
          (() => {
            const id = DesignOSReferenceUI.list()[0].id;
            DesignOSReferenceUI.controller.remove(id);
          })()
        """)
        assert "1 Product Container reference file is" in self._notice(page)
        page.evaluate("""
          (() => {
            const id = DesignOSReferenceUI.list()[0].id;
            DesignOSReferenceUI.controller.remove(id);
          })()
        """)
        assert self._notice(page) is None

    def test_notice_mentions_correction_only_with_server_errors(self):
        page = self._page()
        page.route("**/api/tasks/create/", lambda r: r.fulfill(
            status=400, content_type="application/json",
            body=_rejection_body([
                {"code": "REFERENCE_SIGNATURE_INVALID", "message": "x",
                 "filename": "a.png", "category": "container",
                 "file_index": 0}])))
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        self._switch(page, "packaging")
        assert "need correction" not in self._notice(page)
        self._switch(page, "product_container")
        page.fill("#task-input", "a serum bottle")
        page.click("#btn-submit")
        page.wait_for_function(
            "document.getElementById('btn-submit').disabled === false")
        self._switch(page, "packaging")
        assert "need correction" in self._notice(page)

    def test_notice_return_action_restores_the_editor_and_focus(self):
        page = self._page()
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        self._switch(page, "packaging")
        page.click("#ref-held-notice .ref-held-return")
        assert page.is_visible("#reference-section")
        assert self._notice(page) is None
        assert page.evaluate(
            "document.activeElement.classList.contains('ref-card-remove')") \
            is True

    # -- shared fields and hints (§9) ------------------------------------------

    def test_shared_fields_survive_switching(self):
        from apps.core.models import Brand, Product
        brand = Brand.objects.first()
        from apps.core.models import PRODUCT_CATEGORIES
        Product.objects.create(brand=brand, product_id="BBR-T-001",
                               name="Switch Test",
                               category=PRODUCT_CATEGORIES[0][0], year=2026)
        page = self._page()
        page.fill("#project-name", "Rose Nectar Launch")
        page.fill("#task-input", "a 30 ml serum bottle")
        # §BH55 Phase 3 p3-products: the menu says each product's size — this one has none on record
        page.select_option("#product-select", label="BBR-T-001 — Switch Test · no size on record")
        chosen = page.input_value("#product-select")
        self._switch(page, "packaging")
        self._switch(page, "product_container")
        assert page.input_value("#project-name") == "Rose Nectar Launch"
        assert page.input_value("#task-input") == "a 30 ml serum bottle"
        assert page.input_value("#product-select") == chosen

    def test_container_hints_survive_while_hidden(self):
        page = self._page()
        page.fill("#container-capacity", "30 ml")
        page.fill("#container-closure", "gold dropper")
        self._switch(page, "packaging")
        # hidden, not cleared
        assert not page.is_visible("#container-capacity")
        assert page.input_value("#container-capacity") == "30 ml"
        self._switch(page, "product_container")
        assert page.input_value("#container-capacity") == "30 ml"
        assert page.input_value("#container-closure") == "gold dropper"

    def test_values_typed_on_packaging_survive_switching(self):
        page = self._page()
        self._switch(page, "packaging")
        page.fill("#project-name", "Carton Refresh")
        page.fill("#task-input", "a folding carton for the serum")
        self._switch(page, "product_container")
        self._switch(page, "packaging")
        assert page.input_value("#project-name") == "Carton Refresh"
        assert page.input_value("#task-input") == \
            "a folding carton for the serum"
