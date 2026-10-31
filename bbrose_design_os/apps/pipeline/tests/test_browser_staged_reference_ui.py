"""Real-browser tests for the reference DOM/card renderer (B4b-2A-2).

These drive the REAL dashboard — the server-rendered fieldset, both staged
modules and the untouched poll.js together in headless Chromium. The critical
test intercepts the actual create request and reads the multipart body, so
"submission still carries the staged files" is proven against the wire format
rather than against any of the code that builds it.

Since 2A-3, poll.js submits Product Container tasks straight through
DesignOSReferenceUI.appendToFormData — the canonical inventory is the only
payload source, native inputs are picker controls whose value is cleared on
staging, and no browser file-transfer capability is involved anywhere.
"""
from __future__ import annotations

from importlib import import_module

import pytest
from django.conf import settings
from django.contrib.auth.models import Group, User
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase

try:
    from playwright.sync_api import sync_playwright
    HAVE_PLAYWRIGHT = True
except ImportError:              # pragma: no cover
    HAVE_PLAYWRIGHT = False

from apps.core.models import Brand
from apps.pipeline.models import ApiCallRecord, DesignTask, TaskReference
from apps.pipeline.permissions import ROLE_DESIGNER
from apps.pipeline.targets import ui as target_ui

_URL_RECORDER = """
window.__url = {created: 0, revoked: 0};
var _c = URL.createObjectURL.bind(URL), _r = URL.revokeObjectURL.bind(URL);
URL.createObjectURL = function (o) { window.__url.created++; return _c(o); };
URL.revokeObjectURL = function (u) { window.__url.revoked++; return _r(u); };
"""

PNG = {"name": "a.png", "mimeType": "image/png", "buffer": b"\x89PNG\r\n\x1a\n" + b"\x00" * 24}

#: a started design opens on its own page (static/js/poll.js); the start form's tests stand in for the create door, so
#: the page is told the design it would open instead of leaving for a design that does not exist
_HOLD_STILL = "window.BBROSE_OPEN_DESIGN = function (id) { window.__opened = id; };"


def _file(name, mime="image/png", size=24):
    return {"name": name, "mimeType": mime, "buffer": b"\x00" * size}


class RefUiHarness:
    """Shared live-dashboard harness: authenticated context, URL recorders,
    auto-dismissed (and recorded) dialogs, staging helpers. Used by the 2A-2
    UI tests here and the 2A-3 submission wire tests."""

    @classmethod
    def setUpClass(cls):
        import os
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._pw.stop()
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user("uib4b", "u@t.com", "pw",
                                             is_staff=True)
        self.user.groups.add(
            Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
        Brand.objects.create(name="BBROSE", master_brief="x")
        self._ctxs = []
        self.dialogs = []
        # his fold names designs by their number in HIS database (apps/dashboard/board.py HIS_FOLD); a test database
        # numbers its own designs as it makes them, so a longer run folded a test's designs off the board — emptied here,
        # as the counting tests empty it (the live server runs in this process)
        from unittest.mock import patch

        from apps.dashboard import board
        fold = patch.dict(board.OWNER_FOLD, {}, clear=True)
        fold.start()
        self.addCleanup(fold.stop)

    def tearDown(self):
        for ctx in self._ctxs:
            ctx.close()

    # -- harness -------------------------------------------------------------

    def _context(self, extra_init=None, viewport=None):
        engine = import_module(settings.SESSION_ENGINE)
        store = engine.SessionStore()
        store["_auth_user_id"] = str(self.user.pk)
        store["_auth_user_backend"] = \
            "django.contrib.auth.backends.ModelBackend"
        store["_auth_user_hash"] = self.user.get_session_auth_hash()
        store.save()
        ctx = self._browser.new_context(viewport=viewport) if viewport \
            else self._browser.new_context()
        host = self.live_server_url.split("//")[1].split(":")[0]
        # a csrftoken cookie lets real in-browser POSTs pass Django's
        # double-submit check (getCsrf() reads this cookie into X-CSRFToken)
        from django.middleware.csrf import _get_new_csrf_string
        # Django 4.1+ keeps the raw secret in the cookie; the header may
        # legally carry the same secret (unmasked tokens are accepted)
        ctx.add_cookies([{"name": "sessionid", "value": store.session_key,
                          "domain": host, "path": "/"},
                         {"name": "csrftoken",
                          "value": _get_new_csrf_string(),
                          "domain": host, "path": "/"}])
        self._ctxs.append(ctx)
        return ctx

    def _page(self, extra_init=None, viewport=None):
        ctx = self._context(viewport=viewport)
        page = ctx.new_page()
        page.add_init_script(_URL_RECORDER)
        page.add_init_script(_HOLD_STILL)
        if extra_init:
            page.add_init_script(extra_init)
        page.on("dialog",
                lambda d: (self.dialogs.append(d.message), d.dismiss()))
        page.goto(self.live_server_url + "/dashboard/new/classic/",  # [the owner's answer to the UI directions of 2026-09-25: the home is the board; the start form is at New design]
                  wait_until="domcontentloaded")
        page.wait_for_selector("#reference-section", state="attached")
        # at mobile widths the queue panel is a drawer behind #mobile-toggle — [§BH55 Phase 3, 2026-09-19: the
        # composer moved to the home's center, so it is on screen at every width and no drawer is opened for it]
        # reveal the Product Container panel (poll.js toggles it on click)
        page.click('.target-chip[data-target="product_container"]')
        return page

    def _design_page(self, task, viewport=None, before=None, extra_init=None, library=False):
        """A design's own page — C's design page (the owner's answer to the UI directions of 2026-09-25), where every
        step is drawn by the same scripts into the same containers the old single page held. The page opens its
        design itself: what a test must see of that first load (its request listeners) is attached in `before`,
        BEFORE the address is opened, and the test waits on the design's first status response instead of loading
        it a second time. The library beside the step is set here — closed unless a test asks for it — never left
        to what an earlier page stored in this browser."""
        ctx = self._context(viewport=viewport)
        page = ctx.new_page()
        page.add_init_script(_URL_RECORDER)
        page.add_init_script("try { localStorage.setItem('bbrose.library.open', '%s'); } catch (e) {}"
                             % ("1" if library else "0"))
        if extra_init:
            page.add_init_script(extra_init)
        page.on("dialog",
                lambda d: (self.dialogs.append(d.message), d.dismiss()))
        if before:
            before(page)
        with page.expect_response(lambda r: f"/api/tasks/{task.pk}/status/" in r.url):
            page.goto(f"{self.live_server_url}/dashboard/designs/{task.pk}/",
                      wait_until="domcontentloaded")
        return page

    def _drop(self, page, kind, files):
        return page.evaluate("""
          (args) => {
            const zone = document.querySelector(
              `.ref-zone[data-kind="${args.kind}"]`);
            const dt = new DataTransfer();
            for (const f of args.files) {
              dt.items.add(new File([new Uint8Array(f.size || 3)], f.name,
                                    {type: f.type || ''}));
            }
            const over = new DragEvent('dragover',
              {bubbles: true, cancelable: true, dataTransfer: dt});
            zone.dispatchEvent(over);
            const drop = new DragEvent('drop',
              {bubbles: true, cancelable: true, dataTransfer: dt});
            zone.dispatchEvent(drop);
            return {overPrevented: over.defaultPrevented,
                    dropPrevented: drop.defaultPrevented};
          }
        """, {"kind": kind, "files": files})

    def _cards(self, page, kind=None):
        sel = (f'.ref-cards[data-kind="{kind}"] .ref-card' if kind
               else ".ref-card")
        return page.eval_on_selector_all(
            sel, "els => els.map(e => e.dataset.refId)")


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class StagedReferenceUiBrowserTests(RefUiHarness, DrainedStaticLiveServerTestCase):

    # -- structure from server configuration ---------------------------------

    def test_section_renders_from_server_configuration(self):
        page = self._page()
        kinds = page.eval_on_selector_all(
            ".ref-category", "els => els.map(e => e.dataset.kind)")
        # [§BH69(2), the owner's goal of 2026-09-26: the "inspiration" zone sent the picture itself to the picture
        # service; the inspiration box outside the container's inputs takes its place, for every kind of design]
        assert kinds == ["container", "logo", "label", "color"]
        body = page.text_content("#reference-section")
        for cat in target_ui.START_REFERENCE_CATEGORIES:
            assert cat["label"] in body, cat["key"]
            assert cat["description"] in body, cat["key"]
        assert "REFERENCE ONLY" in body
        assert "do not confirm dimensions" in body
        assert "20.0 MB" in body
        # every input: multiple, an accept list, and an associated label
        assert page.eval_on_selector_all(
            "input.ref-input",
            """els => els.every(i => i.multiple
                 && i.accept.includes('.png')
                 && document.querySelector(`label[for="${i.id}"]`) !== null)
            """) is True
        assert page.eval_on_selector(
            "#reference-section", "el => el.tagName") == "FIELDSET"
        assert page.eval_on_selector(
            "#reference-section legend", "el => !!el") is True

    def test_the_complete_products_card_names_its_stages_and_no_card_fails(self):
        # [the checklist of 2026-09-26: the card's hint read COMPOSITE_STAGES, which only a design's page loaded — on
        # the start page every card's click threw before the hint was drawn, so the Complete Product's stages never showed]
        page = self._page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.click('.target-chip[data-target="complete_product"]')
        hint = page.locator("#composite-hint")
        assert hint.is_visible()
        assert "Made in stages" in hint.inner_text()
        assert "Design coordinated packaging" in hint.inner_text()
        page.click('.target-chip[data-target="packaging"]')
        assert hint.is_hidden()
        assert errors == []

    def test_integration_handle_is_exposed_for_2a3(self):
        page = self._page()
        assert page.evaluate("""
          ['list', 'count', 'appendToFormData', 'setSubmitting',
           'clearAfterSuccess'].every(
             k => typeof window.DesignOSReferenceUI[k] === 'function')
        """) is True
        assert page.evaluate(
            "typeof DesignOSReferenceUI.controller.addFiles") == "function"

    # -- picker staging ------------------------------------------------------

    def test_picker_selection_stages_and_renders_cards(self):
        page = self._page()
        page.set_input_files("#ref-input-container", files=[_file("one.png")])
        assert len(self._cards(page, "container")) == 1
        text = page.text_content('.ref-cards[data-kind="container"]')
        assert "one.png" in text and "Container Reference" in text
        assert "image/png" in text and "REFERENCE ONLY" in text
        # repeated selection ADDS, and the same filename can be staged again
        page.set_input_files("#ref-input-container",
                             files=[_file("two.png"), _file("one.png")])
        assert len(self._cards(page, "container")) == 3
        assert page.evaluate("DesignOSReferenceUI.count()") == 3

    # -- drag and drop -------------------------------------------------------

    def test_drop_stages_into_the_zone_category(self):
        page = self._page()
        out = self._drop(page, "logo", [_file("mark.png"),
                                        _file("mark2.jpg", "image/jpeg")])
        assert out == {"overPrevented": True, "dropPrevented": True}
        assert len(self._cards(page, "logo")) == 2
        names = page.evaluate(
            "DesignOSReferenceUI.list().map(e => [e.category, e.name])")
        assert names == [["logo", "mark.png"], ["logo", "mark2.jpg"]]

    def test_drag_active_state_in_text_and_class(self):
        page = self._page()
        state = page.evaluate("""
          (() => {
            const zone = document.querySelector('.ref-zone[data-kind="label"]');
            const txt = () => zone.querySelector('.ref-zone-drop').textContent;
            const dt = new DataTransfer();
            zone.dispatchEvent(new DragEvent('dragenter',
              {bubbles: true, cancelable: true, dataTransfer: dt}));
            const during = [zone.classList.contains('drag-active'), txt()];
            zone.dispatchEvent(new DragEvent('dragleave', {bubbles: true}));
            const after = [zone.classList.contains('drag-active'), txt()];
            return {during, after};
          })()
        """)
        assert state["during"] == [True, "Release to add files"]
        assert state["after"] == [False, "Drop files here or browse"]

    # -- previews ------------------------------------------------------------

    def test_rasters_get_previews_documents_get_neutral_cards(self):
        page = self._page()
        page.set_input_files(                                    # [§BH69(2): the label zone, the inspiration
            "#ref-input-label",                                   # zone no longer drawn]
            files=[_file("p.png"), _file("j.jpg", "image/jpeg"),
                   _file("w.webp", "image/webp"),
                   _file("d.pdf", "application/pdf"),
                   _file("v.ai", ""), _file("e.eps", "")])
        imgs = page.eval_on_selector_all(
            ".ref-card img", "els => els.map(e => [e.alt, e.src])")
        assert [a for a, _ in imgs] == ["p.png", "j.jpg", "w.webp"]
        assert all(src.startswith("blob:") for _, src in imgs)
        docs = page.eval_on_selector_all(
            ".ref-card-doc", "els => els.map(e => e.textContent)")
        assert docs == ["PDF", "AI", "EPS"]
        # document cards never contain an img
        assert page.eval_on_selector_all(
            ".ref-card", """els => els.filter(c =>
              c.querySelector('.ref-card-doc') && c.querySelector('img')
            ).length""") == 0
        # the UI created no object URLs beyond the controller's three
        assert page.evaluate("window.__url.created") == 3

    # -- removal -------------------------------------------------------------

    def test_remove_deletes_one_and_revokes_its_url(self):
        page = self._page()
        page.set_input_files("#ref-input-container",
                             files=[_file("same.png"), _file("same.png")])
        assert len(self._cards(page, "container")) == 2
        label = page.eval_on_selector(
            ".ref-card-remove", "el => el.getAttribute('aria-label')")
        assert "same.png" in label and "Container Reference" in label
        page.click('.ref-cards[data-kind="container"] '
                   '.ref-card:first-child .ref-card-remove')
        assert len(self._cards(page, "container")) == 1
        assert page.evaluate("DesignOSReferenceUI.count()") == 1
        assert "Removed same.png" in page.text_content("#ref-live")
        # the picker is not state: it was cleared at staging time and removal
        # does not touch it — the inventory is the only record
        assert page.evaluate(
            "document.getElementById('ref-input-container').files.length") == 0
        assert page.evaluate("window.__url.revoked") == 1

    # -- native mirror and REF_FILES bridge ----------------------------------

    def test_native_inputs_are_pickers_not_state(self):
        """2A-3: inputs are cleared the moment a selection is staged. The
        canonical inventory is the only record of what will be submitted."""
        page = self._page()
        page.set_input_files("#ref-input-container", files=[_file("c.png")])
        self._drop(page, "color", [_file("chips.pdf", "application/pdf")])
        empties = page.evaluate("""
          Array.from(document.querySelectorAll('input.ref-input'))
               .map(i => i.files.length)
        """)
        # [his final goal, 2026-10-05, B1 and B3] the inside and sticker reference boxes beside the inspiration box
        assert empties == [0, 0, 0, 0, 0, 0, 0]
        assert page.evaluate(
            "DesignOSReferenceUI.list().map(e => [e.category, e.name])") == [
            ["container", "c.png"], ["color", "chips.pdf"]]

    def test_the_temporary_bridge_global_is_gone(self):
        """2A-3 removed the accessor bridge: the page carries no such global,
        no property descriptor, nothing to drift."""
        page = self._page()
        page.set_input_files("#ref-input-container", files=[_file("c.png")])
        assert page.evaluate("""
          ({typeofGlobal: typeof window.REF_FILES,
            descriptor: Object.getOwnPropertyDescriptor(
              window, 'REF_FILES') === undefined})
        """) == {"typeofGlobal": "undefined", "descriptor": True}

    # -- the wire: Product Container submission ------------------------------

    def test_product_container_submission_carries_staged_files(self):
        page = self._page()
        captured = {}

        def handle(route):
            req = route.request
            captured["content_type"] = req.headers.get("content-type", "")
            captured["body"] = req.post_data_buffer
            route.fulfill(status=201, content_type="application/json",
                          body='{"task_id": 4242, "status": "queued"}')

        page.route("**/api/tasks/create/", handle)
        page.route("**/api/tasks/4242/**", lambda r: r.fulfill(
            status=200, content_type="application/json", body="{}"))

        page.fill("#task-input", "a rose serum bottle")
        page.set_input_files("#ref-input-container",
                             files=[_file("shape.png")])
        page.set_input_files("#ref-input-color",
                             files=[_file("chips.pdf", "application/pdf")])
        page.click("#btn-submit")
        page.wait_for_function(
            "DesignOSReferenceUI && DesignOSReferenceUI.count() === 0")

        assert captured["content_type"].startswith("multipart/form-data")
        body = captured["body"]
        assert b'name="container"; filename="shape.png"' in body
        assert b'name="color"; filename="chips.pdf"' in body
        assert b'name="colour"' not in body
        assert b'name="design_target"\r\n\r\nproduct_container' in body
        # confirmed success cleared the inventory, the cards and the URLs
        assert self._cards(page) == []
        assert page.evaluate("window.__url.revoked") == \
            page.evaluate("window.__url.created")

    # -- Packaging isolation -------------------------------------------------

    def test_packaging_submission_stays_json_and_fileless(self):
        page = self._page()
        page.set_input_files("#ref-input-container",
                             files=[_file("held.png")])
        captured = {}

        def handle(route):
            req = route.request
            captured["content_type"] = req.headers.get("content-type", "")
            captured["body"] = req.post_data
            route.fulfill(status=201, content_type="application/json",
                          body='{"task_id": 4243, "status": "queued"}')

        page.route("**/api/tasks/create/", handle)
        page.route("**/api/tasks/4243/**", lambda r: r.fulfill(
            status=200, content_type="application/json", body="{}"))

        page.click('.target-chip[data-target="packaging"]')
        page.fill("#task-input", "a folding carton")
        page.click("#btn-submit")
        # B4b-2C: a held Product Container file makes Packaging ask first —
        # the JSON dispatch happens through the explicit omission confirm
        page.click("#omission-submit")
        page.wait_for_timeout(300)          # request is captured synchronously

        assert captured["content_type"].startswith("application/json")
        assert '"design_target": "packaging"' in captured["body"] or \
            '"design_target":"packaging"' in captured["body"]
        assert "filename=" not in captured["body"]
        assert "held.png" not in captured["body"]

    # -- accessibility, overflow, and nothing-server-side --------------------

    def test_aria_live_announces_additions(self):
        page = self._page()
        live = page.eval_on_selector(
            "#ref-live", "el => el.getAttribute('aria-live')")
        assert live == "polite"
        page.set_input_files("#ref-input-logo", files=[_file("m.png")])
        assert page.text_content("#ref-live") == \
            "Added 1 file to Brand Logo."
        page.set_input_files("#ref-input-logo",
                             files=[_file("n.png"), _file("o.png")])
        assert page.text_content("#ref-live") == \
            "Added 2 files to Brand Logo."

    def test_long_filenames_do_not_overflow_the_page(self):
        page = self._page()
        long = ("extremely-long-reference-filename-with-many-many-words-"
                "describing-a-frosted-rose-serum-bottle-photograph.png")
        page.set_input_files("#ref-input-container", files=[_file(long)])
        assert page.eval_on_selector(
            ".ref-card-name", "el => el.title") == long
        assert page.eval_on_selector(
            ".ref-card-name",
            "el => getComputedStyle(el).textOverflow") == "ellipsis"
        assert page.evaluate(
            "document.documentElement.scrollWidth"
            " <= document.documentElement.clientWidth + 1") is True

    def test_staging_alone_touches_nothing_server_side(self):
        page = self._page()
        creates = []
        page.route("**/api/tasks/create/",
                   lambda r: (creates.append(1), r.abort()))
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        self._drop(page, "label", [_file("b.pdf", "application/pdf")])      # [§BH69(2): the label zone]
        page.wait_for_timeout(200)
        assert creates == []
        assert DesignTask.objects.count() == 0
        assert TaskReference.objects.count() == 0
        assert ApiCallRecord.objects.count() == 0

    # -- browser capability independence -------------------------------------

    def test_staging_works_without_datatransfer(self):
        """2A-3 made the file-transfer capability irrelevant: nothing assigns
        input.files any more, so a browser without DataTransfer stages,
        renders and keeps the submit button live."""
        page = self._page(extra_init="window.DataTransfer = undefined;")
        page.set_input_files("#ref-input-container", files=[_file("a.png")])
        assert page.evaluate("DesignOSReferenceUI.count()") == 1
        assert len(self._cards(page, "container")) == 1
        assert page.eval_on_selector(
            "#btn-submit", "el => el.disabled") is False
        assert "Added 1 file" in page.text_content("#ref-live")

    # -- inventory/DOM consistency -------------------------------------------

    def test_cards_and_inventory_carry_identical_ids(self):
        page = self._page()
        page.set_input_files("#ref-input-container",
                             files=[_file("a.png"), _file("b.pdf",
                                                          "application/pdf")])
        self._drop(page, "color", [_file("c.jpg", "image/jpeg")])
        dom_ids = self._cards(page)
        inv_ids = page.evaluate(
            "DesignOSReferenceUI.list().map(e => e.id)")
        assert sorted(dom_ids) == sorted(inv_ids)
        assert len(dom_ids) == 3
        assert page.evaluate("DesignOSReferenceUI.count()") == 3

    def test_a_cartons_structure_chooser_says_each_version_in_words_in_the_one_look(self):
        """[the owner's goal of 2026-09-25, (c) and (d): the chooser at a carton's size step named each version by its
        template's id and was drawn in the old dark page's inline borders; it says each in words, in the one look, and
        every input it posts is as it was]"""
        import re

        from apps.core.models import Brand
        from apps.dielines import registry
        from apps.pipeline.models import DesignTask, GeneratedImage, PackagingOutput
        brand = Brand.objects.create(name="B-struct", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="a carton at its size", status="awaiting_dimensions",
                                         design_target="packaging")
        image = GeneratedImage.objects.create(task=task, direction_name="d", prompt_used="p", variation_number=1,
                                              is_approved=True)
        PackagingOutput.objects.create(task=task, approved_image=image, spec_sheet={
            "structural_selection": {"candidates": registry.new_selection_templates()}})
        page = self._design_page(task)
        page.wait_for_selector('.struct-chooser', timeout=15000)
        shown = page.inner_text('.struct-chooser')
        assert "choose a version" in shown and "Recommended — corrected" in shown, shown
        assert not re.search(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b|\b[a-z]+(?:_[a-z0-9]+)+\b", shown), shown
        assert page.eval_on_selector_all('.struct-chooser [style]', 'els => els.length') == 0
        assert page.eval_on_selector_all('input[name="struct-template"][data-template-id]', 'els => els.length') >= 1

    def test_bh70_a_projects_carton_step_names_the_product_and_a_compact_on_its_edge(self):
        """§BH70(1), items 8 and 20 of the list the owner was sent: the carton step said a project's carton sizes came
        from "the bottle designed for it in this project", for any product; and a compact's carton — stood on its
        edge so the tuck-end carton holds it — was not said to stand so. Both are said now, in words."""
        from apps.core.models import Brand
        from apps.pipeline.models import DesignTask, GeneratedImage, PackagingOutput
        brand = Brand.objects.create(name="B-edge", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="a palette's carton", status="awaiting_dimensions",
                                         design_target="packaging")
        image = GeneratedImage.objects.create(task=task, direction_name="d", prompt_used="p", variation_number=1,
                                              is_approved=True)

        def field(v):
            return {"value": v, "confidence": 0.85, "source": "container on its edge", "blocked": False}
        PackagingOutput.objects.create(task=task, approved_image=image, spec_sheet={
            "backend": "dieline", "template": "straight_tuck_end_carton", "scenario": "A",
            "estimated_dimensions": {"width_mm": field(102.0), "depth_mm": field(25.0), "height_mm": field(123.69)}})
        page = self._design_page(task)
        page.wait_for_selector('#dimensions-view .dim-row', timeout=15000)
        shown = page.inner_text('#dimensions-view')
        assert "the product designed for it in this project, standing on its edge" in shown, shown
        assert "from the product, on its edge" in shown and "bottle" not in shown.lower(), shown

    def test_his_122_a_cartons_stopped_drawing_is_said_in_words_at_its_size_step(self):
        """[His test blocker on design 122 at reconstruction, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md), item 3: "The stop
        reason must be shown in plain words on the page, never only codes in a fold."] for every design: a carton whose
        last drawing stopped says why at its size step, in words and in view, its codes only in the folded record."""
        from apps.core.models import Brand
        from apps.pipeline.models import DesignTask, GeneratedImage, PackagingOutput
        brand = Brand.objects.create(name="B-stop", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="a carton that stopped", status="awaiting_dimensions",
                                         design_target="packaging")
        image = GeneratedImage.objects.create(task=task, direction_name="d", prompt_used="p", variation_number=1,
                                              is_approved=True)
        PackagingOutput.objects.create(task=task, approved_image=image, spec_sheet={
            "backend": "dieline", "template": "straight_tuck_end_carton", "scenario": "A",
            "generation_error": "RECONSTRUCTION_DISPATCH_FAILED"})
        page = self._design_page(task)
        page.wait_for_selector('#dimensions-view .stop-reasons li', state="visible", timeout=15000)
        assert page.inner_text('#dimensions-view .stop-reasons') == (
            "The drawing could not be sent to be drawn, so nothing was drawn — draw it again.")
        assert "RECONSTRUCTION_DISPATCH_FAILED" not in page.inner_text('#dimensions-view')     # only in the fold


# ---------------------------------------------------------------------------
# §BH41(3) — THE DRAINED LIVE SERVER, proved without a browser: a server whose
# handler is still running when the client has gone is waited for, not raced;
# a handler that outlives the timeout fails by name. No playwright needed, so
# this class carries no skipif and runs in every environment the gate runs in.
# ---------------------------------------------------------------------------

import http.client as _http_client
import threading as _threading
import time as _time
import unittest as _unittest

from apps.pipeline.tests.browser_live_server import (DrainableWSGIServer,
                                                     LiveServerNotDrained)


class _SlowApp:
    """A WSGI app whose handler sleeps ``delay`` seconds before answering — a view mid-query."""

    def __init__(self, delay):
        self.delay = delay
        self.started = _threading.Event()

    def __call__(self, environ, start_response):
        self.started.set()
        _time.sleep(self.delay)
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"done"]


def _serve(app):
    from django.core.servers.basehttp import WSGIRequestHandler
    httpd = DrainableWSGIServer(("127.0.0.1", 0), WSGIRequestHandler, allow_reuse_address=False)
    httpd.set_app(app)
    t = _threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, t


def _fire(port):
    """Open a request and abandon it — the client side ends, the server thread keeps going."""
    c = _http_client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.putrequest("GET", "/")
    c.endheaders()
    return c


class DrainedLiveServerTests(_unittest.TestCase):

    def test_wait_idle_returns_only_after_the_in_flight_handler_finishes(self):
        app = _SlowApp(0.6)
        httpd, t = _serve(app)
        try:
            c = _fire(httpd.server_address[1])
            self.assertTrue(app.started.wait(2.0), "the handler never started")
            c.close()                                    # the client is gone; the handler is not
            self.assertEqual(httpd.inflight, 1)
            waited = httpd.wait_idle(5.0)
            self.assertEqual(httpd.inflight, 0)
            self.assertGreaterEqual(waited, 0.3, "wait_idle returned before the handler finished")
        finally:
            httpd.shutdown(); httpd.server_close()

    def test_wait_idle_fails_fast_by_name_when_a_handler_outlives_the_timeout(self):
        app = _SlowApp(3.0)
        httpd, t = _serve(app)
        try:
            c = _fire(httpd.server_address[1])
            self.assertTrue(app.started.wait(2.0))
            c.close()
            t0 = _time.monotonic()
            with self.assertRaises(LiveServerNotDrained) as cm:
                httpd.wait_idle(0.5)
            self.assertLess(_time.monotonic() - t0, 2.0, "the named failure was not fast")
            self.assertIn("LIVE_SERVER_NOT_DRAINED", str(cm.exception))
        finally:
            httpd.shutdown(); httpd.server_close()

    def test_an_abandoned_stream_is_tolerated_once_it_is_old(self):
        """A streaming response whose client has gone cannot be ended from the server side (measured: the
        first write after the close still succeeds, a shutdown raises ENOTCONN) and, like the task page's
        event stream between its pings, may write nothing for many seconds — so it is tolerated once older
        than stream_seconds, while a YOUNG request whose client has gone still blocks the drain."""
        class _SilentStream:
            def __call__(self, environ, start_response):
                start_response("200 OK", [("Content-Type", "text/event-stream")])
                def gen():
                    yield b": connected\n\n"
                    _time.sleep(4.0)              # four seconds inside the generator, nothing written
                    yield b"event: ping\ndata: 1\n\n"
                return gen()
        httpd, t = _serve(_SilentStream())
        httpd.stream_seconds = 1.0
        try:
            c = _fire(httpd.server_address[1])
            _time.sleep(0.3)
            self.assertEqual(httpd.inflight, 1)
            c.close()                                    # the client is gone; the stream sleeps on
            _time.sleep(0.2)
            self.assertEqual(len(httpd.blocking_requests()), 1, "a young request blocks even when its client has gone")
            t0 = _time.monotonic()
            waited = httpd.wait_idle(5.0)
            self.assertLess(_time.monotonic() - t0, 2.0, "the old abandoned stream was not tolerated")
            self.assertEqual(httpd.inflight, 1, "the stream is still in flight — tolerated, not ended")
            self.assertEqual(httpd.blocking_requests(), [])
        finally:
            httpd.shutdown(); httpd.server_close()

    def test_an_idle_server_drains_at_once(self):
        httpd, t = _serve(_SlowApp(0.0))
        try:
            self.assertEqual(httpd.inflight, 0)
            # an idle server drains in one quiet window (settle_seconds), not a full timeout
            self.assertLess(httpd.wait_idle(1.0), httpd.settle_seconds + 0.1)
        finally:
            httpd.shutdown(); httpd.server_close()
