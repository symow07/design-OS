"""Real-browser tests for Review Board reference presentation (B4b-3A).

Persisted references rendered in the live dashboard: grouped semantic
headings in fixed category order, raster previews served ONLY through the
authorized per-task endpoint (asserted by watching what the browser actually
loads), honest neutral cards for PDF/AI/EPS, the exact empty state, hostile
filenames neutralized, and 390px geometry. The reference section must stay
strictly separate from generated concepts and free of dieline language.
"""
from __future__ import annotations

import json
import os

import pytest
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase
from django.core.files.base import ContentFile
from django.test import override_settings

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    HAVE_PLAYWRIGHT = True
except ImportError:              # pragma: no cover
    HAVE_PLAYWRIGHT = False

from apps.core.models import Brand
from apps.pipeline.models import DesignTask, TaskReference

from .test_browser_staged_reference_ui import RefUiHarness, _file

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
       b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf"
       b"\xc0\xf0\x1f\x00\x05\x05\x02\x00_\xc8\xf1\xd2\x00\x00\x00\x00IEND"
       b"\xaeB`\x82")
PDF = b"%PDF-1.4\n" + b"x" * 64
EPS = b"%!PS-Adobe-3.0 EPSF-3.0\n" + b"x" * 64
MOBILE = {"width": 390, "height": 844}


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class ReviewBoardReferenceBrowserTests(RefUiHarness,
                                       DrainedStaticLiveServerTestCase):

    def _task(self, target="product_container"):
        return DesignTask.objects.create(
            brand=Brand.objects.first(), task_text="a serum bottle",
            design_target=target, status="completed",
            created_by=self.user)

    def _ref(self, task, kind, filename, data=PNG, media_type="image/png",
             ordering=0):
        ref = TaskReference(task=task, kind=kind,
                            original_filename=filename,
                            media_type=media_type, file_size=len(data),
                            ordering=ordering)
        ref.image.save(filename, ContentFile(data), save=True)
        return ref

    def _open_board(self, page, task, viewport=None):
        # [the owner's answer to the UI directions of 2026-09-25: the board is drawn on the design's own page, which
        # opens the design itself — the references fold is opened here as a person would]
        page.wait_for_selector("#review-board .rb-references",
                               state="attached")
        page.eval_on_selector(".rb-references", "d => { d.open = true; }")

    def _board_page(self, task, viewport=None):
        page = self._design_page(task, viewport=viewport)
        self._open_board(page, task)
        return page

    # -- grouping and cards ---------------------------------------------------

    def test_groups_render_in_fixed_order_with_owner_labels(self):
        task = self._task()
        for i, kind in enumerate(
                ("color", "inspiration", "label", "logo", "container")):
            self._ref(task, kind, f"{kind}-file.png", ordering=i)
        page = self._board_page(task)
        heads = page.eval_on_selector_all(
            ".rb-ref-group-title", "els => els.map(e => e.textContent)")
        assert heads == ["Container Reference", "Brand Logo",
                         "Existing Label or Artwork", "Visual Inspiration",
                         "Colour Reference"]
        # §4 guidance renders per group, non-authoritative
        notes = page.eval_on_selector_all(
            ".rb-ref-group-note", "els => els.map(e => e.textContent)")
        assert len(notes) == 5
        assert "Physical form and proportion guidance only." in notes[0]

    def test_raster_previews_load_through_the_authorized_endpoint(self):
        task = self._task()
        ref = self._ref(task, "container", "amber.png")
        page = self._board_page(task)
        img = page.wait_for_selector(".rb-ref-card img.rb-ref-thumb")
        src = img.get_attribute("src")
        assert f"/api/tasks/{task.id}/references/{ref.id}/" in src
        assert "/media/" not in src
        assert img.get_attribute("alt") == "amber.png"
        # the preview genuinely loads for the owner in the browser
        page.wait_for_function(
            "document.querySelector('.rb-ref-thumb').naturalWidth > 0")
        assert page.eval_on_selector(
            ".rb-ref-thumb", "i => getComputedStyle(i).objectFit") == \
            "contain"

    def test_documents_get_neutral_cards_never_img(self):
        task = self._task()
        self._ref(task, "label", "sheet.pdf", PDF, "application/pdf", 0)
        self._ref(task, "label", "mark.eps", EPS, "application/postscript", 1)
        self._ref(task, "label", "art.ai", EPS,
                  "application/vnd.adobe.illustrator", 2)
        page = self._board_page(task)
        cards = page.eval_on_selector_all(
            ".rb-ref-card", """els => els.map(e => ({
              imgs: e.querySelectorAll('img').length,
              tile: (e.querySelector('.rb-ref-doc') || {}).textContent,
              note: (e.querySelector('.rb-ref-doc-note') || {}).textContent,
            }))""")
        assert [c["imgs"] for c in cards] == [0, 0, 0]
        assert [c["tile"] for c in cards] == ["PDF", "EPS", "AI"]
        assert all("no visual preview" in c["note"] for c in cards)

    def test_card_metadata_badge_and_actions(self):
        task = self._task()
        self._ref(task, "container", "amber.png")
        page = self._board_page(task)
        card = page.text_content(".rb-ref-card")
        assert "amber.png" in card
        assert "image/png" in card
        assert " B" in card                       # human-readable size
        assert "User upload" in card
        assert "REFERENCE ONLY" in card           # stored status, as words
        # semantic time element with the upload date
        assert page.eval_on_selector(
            ".rb-ref-card time", "t => t.getAttribute('datetime')") != ""
        # actions carry the filename in their accessible names
        open_label = page.eval_on_selector(
            '.rb-ref-actions a[aria-label^="Open"]',
            "a => a.getAttribute('aria-label')")
        dl = page.eval_on_selector(
            '.rb-ref-actions a[aria-label^="Download"]',
            "a => ({label: a.getAttribute('aria-label'), href: a.href})")
        assert open_label == "Open amber.png"
        assert dl["label"] == "Download amber.png"
        assert dl["href"].endswith("?download=1")

    def test_duplicate_filenames_both_display(self):
        task = self._task()
        self._ref(task, "container", "logo.png", ordering=0)
        self._ref(task, "container", "logo.png", ordering=1)
        page = self._board_page(task)
        names = page.eval_on_selector_all(
            ".rb-ref-name", "els => els.map(e => e.textContent)")
        assert names == ["logo.png", "logo.png"]

    # -- empty state and target separation ------------------------------------

    def test_container_empty_state_is_exact_and_bare(self):
        task = self._task()
        page = self._board_page(task)
        assert page.text_content(".rb-ref-empty") == \
            "No references were supplied for this task."
        assert page.eval_on_selector_all(
            ".rb-ref-group, .rb-ref-card", "els => els.length") == 0
        body = page.text_content(".rb-references")
        assert "dieline" not in body.lower()
        assert "Drop files" not in body     # review surface, not an uploader

    def test_packaging_without_references_renders_no_section(self):
        task = self._task(target="packaging")
        page = self._design_page(task)  # [2026-09-25: the design's own page]
        page.wait_for_selector("#review-board .rb-project", state="attached")
        assert page.eval_on_selector_all(
            ".rb-references", "els => els.length") == 0

    def test_references_stay_separate_from_concepts(self):
        from apps.pipeline.models import GeneratedImage
        task = self._task()
        self._ref(task, "container", "uploaded-ref.png")
        img = GeneratedImage(task=task, direction_name="Rose Gold")
        img.image_file.save("generated-concept.png", ContentFile(PNG),
                            save=True)
        page = self._board_page(task)
        refs_text = page.text_content(".rb-references")
        assert "uploaded-ref.png" in refs_text
        assert "generated-concept" not in refs_text
        assert page.eval_on_selector_all(
            ".rb-ref-card", "els => els.length") == 1

    def test_no_dieline_or_confirmed_profile_language(self):
        task = self._task()
        self._ref(task, "container", "amber.png")
        page = self._board_page(task)
        body = page.text_content(".rb-references").lower()
        for banned in ("dieline", "print zone", "confirmed profile",
                       "approved dimensions", "production artwork"):
            assert banned not in body

    # -- template safety ------------------------------------------------------

    def test_hostile_filenames_are_neutralized(self):
        task = self._task()
        self._ref(task, "container",
                  '<img src=x onerror="window.__xss=1">.png', ordering=0)
        self._ref(task, "container", 'quote"&\'name.png', ordering=1)
        page = self._board_page(task)
        names = page.eval_on_selector_all(
            ".rb-ref-name", "els => els.map(e => e.textContent)")
        assert names[0] == '<img src=x onerror="window.__xss=1">.png'
        assert names[1] == 'quote"&\'name.png'
        assert page.evaluate("window.__xss") is None
        # the markup became text, not an element
        assert page.eval_on_selector_all(
            '.rb-ref-name img, img[src="x"]', "els => els.length") == 0

    def test_long_unicode_filename_stays_inside_its_card(self):
        long_name = "参照-ファイル-" + "ロングネーム" * 8 + "-🌹.png"
        task = self._task()
        self._ref(task, "container", long_name)
        page = self._board_page(task)
        assert page.evaluate("""
          (() => {
            const card = document.querySelector('.rb-ref-card')
                                 .getBoundingClientRect();
            const name = document.querySelector('.rb-ref-name')
                                 .getBoundingClientRect();
            return name.right <= card.right + 1 &&
                   name.left >= card.left - 1;
          })()
        """) is True

    # -- responsive -----------------------------------------------------------

    def test_mobile_390_no_overflow_and_actions_reachable(self):
        task = self._task()
        self._ref(task, "container", "amber.png", ordering=0)
        self._ref(task, "label", "sheet.pdf", PDF, "application/pdf", 1)
        page = self._design_page(task, viewport=MOBILE)  # [2026-09-25: the design's own page, its library closed]
        page.wait_for_selector("#review-board .rb-references",
                               state="attached")
        page.eval_on_selector(".rb-references", "d => { d.open = true; }")
        assert page.evaluate(
            "document.documentElement.scrollWidth <= "
            "document.documentElement.clientWidth") is True
        page.eval_on_selector(
            '.rb-ref-actions a[aria-label^="Open"]',
            "a => a.scrollIntoView()")
        box = page.eval_on_selector(
            '.rb-ref-actions a[aria-label^="Open"]', """a => {
              const r = a.getBoundingClientRect();
              return {w: r.width, h: r.height, right: r.right};
            }""")
        assert box["w"] > 0 and box["h"] > 0
        assert box["right"] <= MOBILE["width"]


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class DesignAddressBrowserTests(RefUiHarness, DrainedStaticLiveServerTestCase):
    """§BH55 Phase 3 — a design has its own address in the live dashboard: opening one moves the browser's address to
    /dashboard/designs/<id>/, the back button returns to the design before it and then to the home, which opens no
    one's design; an address typed or bookmarked opens its design."""

    def _task(self, text, status="completed"):
        return DesignTask.objects.create(brand=Brand.objects.first(), task_text=text, design_target="packaging",
                                         status=status, created_by=self.user)

    def _titled(self, page, start):
        page.wait_for_function(f"document.getElementById('task-title').textContent.startsWith({start!r})")

    def test_the_home_opens_no_ones_design(self):
        self._task("a waiting carton", status="awaiting_gate_1")
        page = self._page()
        page.wait_for_timeout(600)
        assert page.text_content("h1.start-title") == "Start a new design"  # [the owner's answer to the UI directions of 2026-09-25: C's start page replaced the old single page]
        assert page.evaluate("location.pathname") == "/dashboard/new/classic/"
        assert page.evaluate("window.OPEN_TASK_ID") is None

    def test_opening_a_design_moves_the_address_and_back_returns(self):
        # [the owner's answer to the UI directions of 2026-09-25: a design is opened from the board, each card a link to
        # the design's own page; back returns to the board] [the owner's goal of 2026-10-29: the board's cards are the
        # chain's rounds, each opening the round's own page]
        from uuid import uuid4

        from apps.pipeline.models import Round
        from apps.pipeline.services import round_designer
        first, second = (Round.objects.create(
            slug=f"walk-{n}-{uuid4().hex[:8]}", request_key=str(uuid4()), created_by=self.user, budget_usd=10,
            state="awaiting_board_pick", current_step="board_pick",
            product_brief=dict(round_designer.gloss_brief(), flow=round_designer.DESIGNER_FLOW, name=name))
            for n, name in ((1, "The first gloss"), (2, "The second gloss")))
        page = self._page()
        page.goto(self.live_server_url + "/dashboard/", wait_until="domcontentloaded")
        for record, name in ((first, "The first gloss"), (second, "The second gloss")):
            page.click(f'a.nm[href="/dashboard/rounds/{record.pk}/"]')
            page.wait_for_function(f"location.pathname === '/dashboard/rounds/{record.pk}/'")
            page.wait_for_selector(f"h1:text-is({name!r})")
            page.go_back()
            page.wait_for_function("location.pathname === '/dashboard/'")
        assert page.is_visible("h1:text-is('Board')")

    def test_the_one_bar_fits_a_laptops_width(self):
        # [the owner's answer to the UI directions of 2026-09-25: at 1280 px the three counts and the account menu ran
        # 83 px past the edge — the old page's own sheet had hidden it; the bar wraps now, and the counts are never hidden]
        # [the checklist of 2026-09-26: the bell joined the bar — measured at the widths where the bar wraps, 1400 and 1180]
        for width in (1440, 1401, 1400, 1366, 1301, 1280, 1181, 1180, 1024):
            ctx = self._context(viewport={"width": width, "height": 800})
            page = ctx.new_page()
            page.goto(self.live_server_url + "/dashboard/new/classic/", wait_until="domcontentloaded")
            assert page.evaluate("document.documentElement.scrollWidth <= "
                                 "document.documentElement.clientWidth") is True, width
            assert page.is_visible("#shell-pills"), width
            assert page.evaluate("document.querySelector('.me').getBoundingClientRect().right <= innerWidth + 1"), width

    def test_the_board_fits_a_phones_width(self):
        # [the owner's answer to the UI directions of 2026-09-25: the home is the board — at a phone's width the three
        # counts wrap and a long product name never pushes the filter past the edge] [the owner's goal of 2026-10-29: the
        # board's cards are the chain's rounds — a long-named round, its product kind in the filter]
        from uuid import uuid4

        from apps.pipeline.models import Round
        from apps.pipeline.services import round_designer
        Round.objects.create(slug=f"long-{uuid4().hex[:8]}", request_key=str(uuid4()), created_by=self.user,
                             budget_usd=10, state="awaiting_board_pick", current_step="board_pick",
                             product_brief=dict(round_designer.gloss_brief(), flow=round_designer.DESIGNER_FLOW,
                                                name="Rose Damascena Night Repair Gloss with a Name Longer Than a Phone",
                                                product_type="Lip gloss with a product kind longer than a phone"))
        ctx = self._context(viewport={"width": 390, "height": 844})
        page = ctx.new_page()
        page.goto(self.live_server_url + "/dashboard/", wait_until="domcontentloaded")
        assert page.is_visible("#board-product")
        assert page.evaluate("document.documentElement.scrollWidth <= "
                             "document.documentElement.clientWidth") is True

    def test_a_start_from_a_finished_container_shows_its_container_fields(self):
        # [2026-09-25: the page opens on a finished design's own target WITH its fields — the old page compared the chosen
        # card with its script's own first value, so a container start opened with the container fields hidden]
        from apps.pipeline.models import GeneratedImage, PackagingOutput
        task = DesignTask.objects.create(brand=Brand.objects.first(), task_text="A serum bottle", status="completed",
                                         design_target="product_container", created_by=self.user)
        concept = GeneratedImage.objects.create(task=task, direction_name="Nocturne", prompt_used="p")
        out = PackagingOutput.objects.create(task=task, approved_image=concept, spec_sheet={}, is_final_approved=True)
        page = self._page()
        page.goto(self.live_server_url + f"/dashboard/new/classic/?from={out.pk}", wait_until="domcontentloaded")
        page.wait_for_selector("#start-from")
        assert page.get_attribute('.target-chip[data-target="product_container"]', "aria-checked") == "true"
        assert page.is_visible("#container-inputs") and page.is_visible("#reference-section")

    def test_the_front_door_is_on_screen_at_a_phones_width(self):
        # §BH55 Phase 3 p3-front: the start page is the home's center, on screen without opening any drawer
        page = self._page(viewport={"width": 390, "height": 844})
        assert page.is_visible("#start-design")
        assert page.is_visible("#task-input") and page.is_visible("#btn-submit")
        assert page.text_content("#btn-submit") == "Start the design"

    def test_start_a_design_from_a_design_returns_to_the_front_door(self):
        # §BH55 Phase 3 p3-front; [2026-09-25: from a design's own page, "New design" in the one top bar]
        task = self._task("a finished carton")
        page = self._design_page(task)
        self._titled(page, "a finished")
        assert not page.is_visible("#start-design")
        page.click(".bar a.new-btn")
        page.wait_for_function("location.pathname === '/dashboard/new/'")
        page.wait_for_selector("#round-intake", state="visible")  # [the designer flow of 2026-10-27: New design]

    def test_the_step_line_says_where_a_design_stands(self):
        # §BH55 Phase 3 p3-steps: the steps done ticked, the one waiting on the designer named "your turn"
        task = self._task("a carton waiting for its concept", status="awaiting_gate_1")
        page = self._page()
        page.goto(self.live_server_url + f"/dashboard/designs/{task.id}/", wait_until="domcontentloaded")
        page.wait_for_selector("#step-line .step-now")
        steps = page.eval_on_selector_all("#step-line .step", "els => els.map(e => [e.className, e.textContent])")
        assert [t for _, t in steps] == ["Brief", "Direction", "Concept — your turn", "Size", "Design", "Approved"]
        assert [c.split("step-")[-1] for c, _ in steps] == ["done", "done", "now", "next", "next", "next"]

    def test_a_printed_piece_has_no_size_step_and_a_finished_design_is_all_done(self):
        # §BH55 Phase 3 p3-steps
        poster = DesignTask.objects.create(brand=Brand.objects.first(), task_text="a poster",
                                           design_target="marketing_material", status="completed", created_by=self.user)
        page = self._page()
        page.goto(self.live_server_url + f"/dashboard/designs/{poster.id}/", wait_until="domcontentloaded")
        page.wait_for_selector("#step-line .step")
        steps = page.eval_on_selector_all("#step-line .step", "els => els.map(e => e.className)")
        assert len(steps) == 5 and all(c.endswith("step-done") for c in steps)

    def test_an_unchecked_concept_says_so_and_the_redraws_left_are_the_servers(self):
        # §BH55 Phase 3 p3-steps: a check that never ran read "QA ?/10 ✗ Failed"; the page counted two redraws
        from apps.pipeline.models import GeneratedImage
        task = self._task("a carton at its concepts", status="awaiting_gate_1")
        GeneratedImage.objects.create(task=task, direction_name="Nocturne", prompt_used="p", variation_number=1)
        page = self._page()
        page.goto(self.live_server_url + f"/dashboard/designs/{task.id}/", wait_until="domcontentloaded")
        page.wait_for_selector("#image-gallery .concept-diagnostics > summary")
        assert page.locator("#image-gallery > .image-card").count() == 0
        page.click("#image-gallery .concept-diagnostics > summary")
        card = " ".join(page.text_content("#image-gallery .concept-diagnostics .image-card").split())
        assert "Quality not checked" in card and "Failed" not in card
        assert "Review pending — approval unavailable" in card
        assert "Use this concept" not in card
        assert page.locator("#image-gallery .btn-approve").count() == 0
        allowance = page.evaluate("url => fetch(url).then(r => r.json())", f"/api/tasks/{task.pk}/status/")["repair_allowance"]
        redraw = page.locator('#gate1-actions button[onclick^="rerunImages"]')
        assert " ".join(redraw.inner_text().split()) == f"Draw these concepts again ({allowance['remaining']} left)"
        assert redraw.is_enabled() == allowance["can_revise"]

    def test_the_library_opens_a_finished_design_and_starts_a_new_one_from_it(self):
        # §BH55 Phase 3 p3-library: a finished design's way back to itself, and a new design started from it, filled in
        # [the owner's goal of 2026-10-29: the Library's finished designs are the rounds whose files are made — a card
        # opens the round's faces and files; the old approved output keeps its own page, unlisted]
        from uuid import uuid4

        from apps.pipeline.models import GeneratedImage, PackagingOutput, Round, RoundMaster
        from apps.pipeline.services import round_designer, round_files_gate
        made = Round.objects.create(
            slug=f"made-{uuid4().hex[:8]}", request_key=str(uuid4()), created_by=self.user, budget_usd=10,
            state="complete", current_step="pick",
            product_brief=dict(round_designer.gloss_brief(), flow=round_designer.DESIGNER_FLOW, name="Night gloss"))
        RoundMaster.objects.create(round=made, state="complete", current_step="files", budget_usd=10,
                                   steps={name: {"state": "complete"} for name in round_files_gate.V1_STEPS},
                                   inputs={"schema": round_files_gate.FILES_SCHEMA, "picture_sha256": "0" * 64},
                                   publication={"download": "files.zip", "report": "README.md",
                                                "files": {"files.zip": "0" * 64}})
        task = self._task("A carton for the night oil")
        concept = GeneratedImage.objects.create(task=task, direction_name="Nocturne", prompt_used="p")
        PackagingOutput.objects.create(task=task, approved_image=concept, spec_sheet={}, is_final_approved=True)
        page = self._page()
        page.goto(self.live_server_url + "/dashboard/library/", wait_until="domcontentloaded")
        assert page.locator(".card.fin").count() == 1                 # the made round, never the old output
        page.click(".card.fin a.frame")                     # [the owner's answer to the UI directions of 2026-09-25: the Library is C's — one page, finished designs part of it]: a finished design's own page
        page.wait_for_function(f"location.pathname === '/dashboard/rounds/{made.pk}/built-files/'")
        output = PackagingOutput.objects.get(task=task)
        page.goto(self.live_server_url + f"/dashboard/library/finished/{output.pk}/", wait_until="domcontentloaded")
        page.click("text=Open the design")                  # the old output's own page, by its address
        page.wait_for_function(f"location.pathname === '/dashboard/designs/{task.id}/'")
        self._titled(page, "A carton for the night oil")
        page.goto(self.live_server_url + f"/dashboard/library/finished/{output.pk}/", wait_until="domcontentloaded")
        page.wait_for_selector("text=Open the design")
        # [the designer flow of 2026-10-27] the start from a finished design is a classic path: unlinked, kept in the code
        assert page.locator("text=Start a new design from this one").count() == 0
        page.goto(self.live_server_url + f"/dashboard/new/classic/?from={output.pk}", wait_until="domcontentloaded")
        page.wait_for_selector("#start-from")
        assert page.input_value("#task-input") == "A carton for the night oil"
        assert page.get_attribute('.target-chip[data-target="packaging"]', "aria-checked") == "true"

    def test_the_library_is_one_click_from_your_designs(self):
        # §BH55 Phase 3 p3-brand: what designs are made from, reached from the dashboard's own header
        # [2026-09-25: from the board, "Library" in the one top bar]
        page = self._page()
        page.goto(self.live_server_url + "/dashboard/", wait_until="domcontentloaded")
        page.click(".bar nav a:text-is('Library')")
        page.wait_for_selector("h1:has-text('Library')")      # [the owner's answer to the UI directions of 2026-09-25: the Library is C's — one page, finished designs part of it]
        assert page.is_visible("#colours") and page.is_visible("#faces") and page.is_visible("#mark")

    def test_a_typed_address_opens_its_design(self):
        task = self._task("a bookmarked carton")
        page = self._page()
        page.goto(self.live_server_url + f"/dashboard/designs/{task.id}/", wait_until="domcontentloaded")
        self._titled(page, "a bookmarked")
        # [the owner's answer to the UI directions of 2026-09-25: C's design page names the design in its own header —
        # the list that stood beside it is the board now]
        assert "a bookmarked carton" in page.text_content("h1.d-title")


#: engine words a designer does not use — counted in what a screen SHOWS (innerText: hidden text is excluded)
WALK_ENGINE_WORDS = [r"\bgate ?[12]\b", r"\bpipeline\b", r"\baria\b", r"\breconstruction\b", r"\bschema\b",
                     r"\bhash\b", r"\bscenario [ab]\b", r"\bauthority\b", r"\best \d+%", r"\bdb\b",
                     r"\bfrontend build\b", r"\btask #\d+", r"\bdieline job\b", r"\bgraph\b", r"\bhandoff\b",
                     r"\bprovenance\b", r"\bfidelity\b", r"\bpayload\b", r"\bjson\b", r"\bapi\b", r"\bsha(?:256)?\b",
                     r"\binspection only\b", r"\bcandidate\b", r"\btier\b", r"\b[A-Z]{3,}_[A-Z_]{3,}\b"]
#: the engine words the walk saw when it was pinned (§BH55 Phase 3, p3-walk) — a ratchet: fewer is always allowed
#: [10 at p3-walk (670d703): the reference panel's seven, "gate 1" once, "reconstruction" twice; p3-words says them in
#: words, and the walk's plan now carries two references, one withheld, so the direction step's are read too]
WALK_ENGINE_WORDS_PINNED = 0


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class StrangersWalkBrowserTests(RefUiHarness, DrainedStaticLiveServerTestCase):
    """§BH55 Phase 3 — THE STRANGER'S WALK, the phase's own instrument, pinned: "Judge it by a person who has never seen it
    finding their way to a finished design without being told how." A new designer-and-reviewer account walks from the
    front door to a finished carton — choosing what to design, describing it, choosing its product, starting it,
    choosing a direction and a concept, confirming the size, approving the design, taking its files — and then finds it
    again (by the one search box since the owner's goal of 2026-10-29, the Library's finished designs being the chain's
    rounds), each step taken by a control's VISIBLE words in the pane a stranger acts in. The
    two paid steps are stood in for (the planner's directions: the tests' own valid plan; the three renders: a picture
    drawn here); everything else runs the real code; connections off this machine are refused; media is a temporary
    folder. It fails on a STOP — a step that cannot be taken by its words — and on more engine words seen than when it
    was pinned. [The same walk, run on six real designs of the development database as its history, is the scratch
    instrument the phase's report measures with; this one builds its own rows.]"""

    BRIEF = "A retail carton for our Rose Damascena Night Repair Oil, soft blush and cream, quietly luxurious"
    PRODUCT = "Rose Damascena Night Repair Oil"

    def setUp(self):
        import tempfile

        from django.contrib.auth.models import Group
        from PIL import Image

        from apps.core.models import Product
        from apps.pipeline.permissions import ROLE_REVIEWER
        super().setUp()
        self.user.groups.add(Group.objects.get_or_create(name=ROLE_REVIEWER)[0])
        Product.objects.create(brand=Brand.objects.first(), product_id="BBR-WALK-1", name=self.PRODUCT,
                               category="SK", year=2026, width_mm=40, depth_mm=40, height_mm=110,
                               product_type="carton", net_weight="30 ml")
        self._media = tempfile.TemporaryDirectory()
        media = self._media.name
        for rel, colour in (("generated/walk_concept.png", (236, 214, 208)), ("brand/logo.png", (80, 37, 37))):
            path = os.path.join(media, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            Image.new("RGB", (480, 640) if "concept" in rel else (240, 80), colour).save(path)
        self.steps, self.stops = [], []

    def tearDown(self):
        super().tearDown()
        self._media.cleanup()

    # -- the stand-ins for the two paid steps, and the real stages run in place ---------------------------------------
    @staticmethod
    def _stand_in(task_id):
        """The two paid steps, stood in for: the planner runs its own code with its model call answering the tests'
        own valid plan (it persists the plan and pauses for a direction, as it does); then the three renders are a
        picture drawn here. [His final goal, 2026-10-05, B4, re-pinned: "NO PROMPT STEP ... Three truly different
        concepts drawn straight away."] the plan no longer pauses: its drawing — one picture for each direction, bound
        by its id — is stood in, in the same call."""
        import json
        from unittest import mock

        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.models import CreativeBrief, DesignTask, GeneratedImage
        from .direction_fixtures import valid_document
        from .quality_fixtures import reviewed
        task = DesignTask.objects.get(pk=task_id)
        brief = CreativeBrief.objects.filter(task=task).first()
        if brief is None:                                    # the planner's directions
            block = mock.MagicMock()
            document = valid_document()                      # its first direction draws on two items, one withheld
            document["directions"][0]["dip_references"] = [
                {"corpus_item_id": "walk-archive-1", "label": "DESCRIPTIVE_REFERENCE_ONLY", "source": "HUMAN_VERIFIED",
                 "note": "a rose carton from the house's archive"},
                {"corpus_item_id": "walk-archive-2", "label": "DESCRIPTIVE_REFERENCE_ONLY", "source": "MACHINE_DERIVED",
                 "blocked": True}]
            block.type, block.text = "text", json.dumps(document)
            answer = mock.MagicMock()
            answer.content = [block]

            def drawn(agent, feedback=None):
                for i, d in enumerate(CreativeBrief.objects.get(task=agent.task).directions):
                    reviewed(GeneratedImage.objects.create(task=agent.task, direction_name=d["name"],
                                                  direction_id=d["direction_id"], variation_number=i + 1,
                                                  prompt_used="(a stand-in for the paid render)",
                                                  image_file="generated/walk_concept.png"))
                DesignTask.objects.filter(pk=agent.task.pk).update(status="awaiting_gate_1")
            with mock.patch("apps.pipeline.agents.creative_director.call_claude", return_value=answer), \
                    mock.patch.object(ARIAAgent, "_render_each_direction", drawn):
                ARIAAgent(task_id).run()
            return
        for i in range(3):                                   # the three renders
            reviewed(GeneratedImage.objects.create(task=task, direction_name=(brief.directions or [{}])[0].get("name", "concept"),
                                          prompt_used="(a stand-in for the paid render)", variation_number=i + 1,
                                          image_file="generated/walk_concept.png"))
        DesignTask.objects.filter(pk=task.pk).update(status="awaiting_gate_1")

    @staticmethod
    def _real(stage):
        from unittest import mock

        def run(*a):
            from apps.pipeline.agents.aria import ARIAAgent
            agent = ARIAAgent(a[0])
            if stage == "gate1":
                agent.resume_after_gate_1(a[1])
            elif stage == "dimensions":
                agent.resume_after_dimensions(a[1], a[2], panel_info_override=(a[3] if len(a) > 3 else None))
            else:
                agent.resume_after_gate_2(a[1])
            return mock.Mock(id="in-place")
        return run

    @staticmethod
    def _fence():
        import socket
        from unittest import mock
        real = socket.socket.connect

        def connect(sock, address):
            host = address[0] if isinstance(address, tuple) else str(address)
            if host not in ("127.0.0.1", "localhost", "::1") and not str(host).startswith("/"):
                raise RuntimeError(f"the walk spends nothing and reaches nothing off this machine ({host})")
            return real(sock, address)
        return mock.patch.object(socket.socket, "connect", connect)

    # -- the stranger's senses ------------------------------------------------------------------------------------------
    def _see(self, page, name):
        import re
        page.wait_for_timeout(500)
        text = page.evaluate("() => document.body.innerText")
        words = sorted({m.group(0).lower() for rx in WALK_ENGINE_WORDS for m in re.finditer(rx, text, re.I)})
        self.steps.append((name, page.evaluate("() => location.pathname"), words))

    def _click_words(self, page, words, scope="#panel-center"):
        """Click the one VISIBLE control whose name reads ``words``; anything else is a STOP, named."""
        import re
        rx = re.compile(words, re.I)
        found = [el for role in ("button", "radio", "link")
                 for loc in [page.locator(scope).get_by_role(role, name=rx)]
                 for el in (loc.nth(i) for i in range(loc.count())) if el.is_visible()]
        labels = sorted({(e.inner_text() or "").strip().split("\n")[0] for e in found})
        if len(labels) != 1:
            self.stops.append(f"{words!r}: {labels or 'no visible control reads it'}")
            return False
        found[0].click()
        return True

    def test_a_stranger_reaches_a_finished_design_and_finds_it_again(self):
        from unittest import mock
        own = override_settings(MEDIA_ROOT=self._media.name, OPENAI_API_KEY="fenced-walk", ANTHROPIC_API_KEY="fenced-walk",
                                BRAND_LOGO_PATH=os.path.join(self._media.name, "brand", "logo.png"))
        patches = [self._fence(),
                   mock.patch("apps.core.health.worker_available", lambda: True),
                   mock.patch("apps.pipeline.tasks.run_aria_pipeline.delay", self._stand_in),
                   mock.patch("apps.pipeline.tasks.resume_aria_gate1.delay", self._real("gate1")),
                   mock.patch("apps.pipeline.tasks.resume_aria_dimensions.delay", self._real("dimensions")),
                   mock.patch("apps.pipeline.tasks.resume_aria_gate2.delay", self._real("gate2"))]
        own.enable()
        for p in patches:
            p.start()
        try:
            page = self._context().new_page()                # a person answers OK to what the page asks
            # [his goal of 2026-10-13, (4)] the page asks in its own dialog — a browser pop-up is recorded, never wanted
            page.on("dialog", lambda d: (self.dialogs.append(d.message), d.accept()))
            page.goto(self.live_server_url + "/dashboard/", wait_until="domcontentloaded")
            # [the owner's answer to the UI directions of 2026-09-25: the home is the board — a stranger finds "New
            # design" in the one top bar, one click, and the start form opens]
            self._see(page, "the board")
            if self._click_words(page, r"^new design$", scope=".bar"):
                page.wait_for_url("**/dashboard/new/")
            # [the designer flow of 2026-10-27: New design is the mood-board intake; this walk's carton path is the
            # classic start, kept in the code at its own address]
            page.wait_for_selector("#round-intake", state="visible")
            page.goto(self.live_server_url + "/dashboard/new/classic/", wait_until="domcontentloaded")
            self._see(page, "the front door")
            self._click_words(page, r"^Carton\b", scope="#start-design")      # [2026-09-25: C's start page]
            page.fill("#task-input", self.BRIEF)
            page.select_option("#product-select", value=page.locator(
                "#product-select option", has_text=self.PRODUCT).first.get_attribute("value"))
            self._see(page, "the brief written")
            # [2026-09-25: a started design opens on its own page — the stranger follows it there]
            if self._click_words(page, r"start (a |the )?design", scope="#start-design"):
                page.wait_for_url("**/dashboard/designs/*/", timeout=15000)
            page.wait_for_timeout(2500)
            self._see(page, "started")
            # [his final goal, 2026-10-05, B4, re-pinned: "NO PROMPT STEP"] no direction is asked of him: the start
            # leads to the three pictures, and the first choice is a concept
            for step, words, wait in (("a concept chosen", r"use this concept", 3000),
                                      ("the size confirmed", r"make the design|confirm (the )?size", 4000),
                                      ("the design approved", r"^approve$", 4000)):
                self._click_words(page, words)
                if page.locator("#ask-dialog[open]").count():           # he answers yes to what the page asks
                    page.click("#ask-yes")
                page.wait_for_timeout(wait)
                self._see(page, step)
            files = page.locator("#complete-state a[href*='/files/'], #complete-state a[download]").count()
            if not files:
                self.stops.append("the finished design shows no file to take away")
            if not page.evaluate("() => location.pathname").startswith("/dashboard/designs/"):
                self.stops.append("the design has no address of its own")
            # [2026-09-25: the Library in the one top bar, then its Finished designs — two clicks from any page]
            # [the owner's goal of 2026-10-29: the Library's finished designs are the chain's rounds whose files are
            # made; this classic design is found again by the one search box in the top bar, which still reaches the
            # old designs, and opens at its own address]
            address = page.evaluate("() => location.pathname")
            page.fill("#shell-find", self.PRODUCT)
            page.press("#shell-find", "Enter")
            page.wait_for_url("**/dashboard/find/**")
            found = page.locator(f'a.frow[href="{address}"]')
            if not found.count():
                self.stops.append("the finished design is not found again")
            else:
                found.first.click()
                page.wait_for_function(f"location.pathname === {address!r}")
                try:                                              # its files arrive with the page's own script
                    page.wait_for_selector("#complete-state a[href*='/files/'], #complete-state a[download]",
                                           state="attached", timeout=10000)
                except Exception:  # noqa: BLE001 — no file to take away is a stop, said
                    self.stops.append("the finished design, found again, shows no file to take away")
            self._see(page, "found again")
        finally:
            for p in reversed(patches):
                p.stop()
            own.disable()
        seen = sum(len(words) for _, _, words in self.steps)
        assert self.stops == [], self.stops
        assert self.dialogs == [], self.dialogs          # [his goal of 2026-10-13, (4)] no browser pop-up on the way
        assert seen <= WALK_ENGINE_WORDS_PINNED, [(name, words) for name, _, words in self.steps if words]


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class DesignPageAdjustBrowserTests(RefUiHarness, DrainedStaticLiveServerTestCase):
    """His pick (2026-09-25): "pick an element and try colours and faces from a library that stays open". On a lid's face
    a colour in the library is tried on the element picked in Adjust and a face on the name, and the try answers in place,
    beside the design. The design loop is stood in — its offer (in its own shape) and its answer at the network — so what
    is proved is the page: what it sends, and what it says back."""

    def _lid_page(self, answers):
        from unittest import mock

        from apps.core.models import ColorSystem
        from apps.core.tests import _LID_OFFER
        from apps.dashboard import exploration_render, explorations
        brand = Brand.objects.first()
        ColorSystem.objects.create(brand=brand, name="Blush Core", system_id="CS-001", status="canonical",
                                   palette=[{"name": "Deep Rose", "role": "Accent", "hex": "#8B3A52"},
                                            {"name": "Rose Gold", "role": "Metallic", "hex": "Metallic 10122 C"}],
                                   image_generation_context="blush")
        task = DesignTask.objects.create(brand=brand, task_text="a pressed powder lid", design_target="packaging",
                                         status="awaiting_gate_2", created_by=self.user)
        for p in (mock.patch.object(exploration_render, "explorable", return_value={"form": True}),
                  mock.patch.object(exploration_render, "knob_offer", return_value=_LID_OFFER),
                  mock.patch.object(explorations, "owner_refusal", return_value="")):
            p.start()
            self.addCleanup(p.stop)
        self.posts = []

        def answer(route):
            self.posts.append({"body": route.request.post_data_buffer or b"",
                               "accept": route.request.headers.get("accept", "")})
            status, body = answers.pop(0)
            route.fulfill(status=status, content_type="application/json", body=json.dumps(body))
        page = self._design_page(task, library=True, before=lambda pg: pg.route("**/explore/", answer))
        page.wait_for_selector("#adjust-form")
        return page

    def test_a_colour_in_the_library_is_tried_on_the_picked_element_and_answers_in_place(self):
        tried = {"study": "t1-loop-x", "picture": "p1", "url": "data:image/png;base64,iVBORw0KGgo=",
                 "what_changed": ["the lid's ground in Deep Rose #8B3A52 (Blush Core, Accent) — it stood in Warm Cream "
                                  "#FAF3EC (Blush Core, Ground)"], "codes": []}
        page = self._lid_page([(200, tried)])
        assert page.inner_text("#library-panel [data-picked]") == "the lid's ground"      # the first, until picked
        page.click('#library-panel [data-colour="#8B3A52"]')
        page.wait_for_selector("#adjust-result figure")
        assert len(self.posts) == 1 and "application/json" in self.posts[0]["accept"]
        body = self.posts[0]["body"]
        assert b'name="colour_ground"\r\n\r\n#8B3A52' in body                          # the picked element, that colour
        assert "the lid's ground in Deep Rose" in page.inner_text("#adjust-result")
        assert page.inner_text("#adjust-tries [data-tries]") == "1" and page.is_visible("#adjust-tries")
        assert "/dashboard/designs/" in page.url                                       # it stayed on the design's page

    def test_a_refusal_is_said_in_words_and_a_face_is_tried_on_the_name(self):
        why = ("EXPLORATION_COLOUR_OUTSIDE_THE_BRAND_PALETTE: REFUSED — #123456 is not a colour of the brand's palette "
               "(Blush Core, Nude Warm)")
        refused = {"refused": "EXPLORATION_COLOUR_OUTSIDE_THE_BRAND_PALETTE", "why": why}
        tried = {"study": "t1-loop-x", "picture": "p2", "url": "data:image/png;base64,iVBORw0KGgo=",
                 "what_changed": ["the name set in Amatic SC Bold — it stood in Poppins Light"], "codes": []}
        page = self._lid_page([(409, refused), (200, tried)])
        page.click("#adjust-form button[type=submit]")
        page.wait_for_selector("#adjust-result.refused")
        shown = page.inner_text("#adjust-result")
        assert "It was not drawn." in shown and "#123456 is not a colour of the brand" in shown
        assert "EXPLORATION_" not in shown                                        # the code is kept, folded
        assert "EXPLORATION_COLOUR_OUTSIDE_THE_BRAND_PALETTE" in page.text_content("#adjust-result")
        page.click("#tab-faces")
        page.click('#library-panel [data-face="AmaticSC-Bold"]')
        page.wait_for_selector("#adjust-result:not(.refused) figure")
        assert b'name="face_name"\r\n\r\nAmaticSC-Bold' in self.posts[1]["body"]
        assert "the name set in Amatic SC Bold" in page.inner_text("#adjust-result")

    def test_an_inspiration_picture_added_on_the_adjust_panel_is_read_and_kept_and_a_try_never_carries_it(self):
        """§BH69(2): "An upload box on New design (and on a design's Adjust panel)". The box sits outside the Adjust
        form: a picture dropped there is read against the design and kept with it (the design's own door, stood in
        here), and what was taken shows in place; a try posted after it carries no picture — the design loop stays
        free and never reads one (§BH51(a))."""
        tried = {"study": "t1-loop-x", "picture": "p1", "url": "data:image/png;base64,iVBORw0KGgo=",
                 "what_changed": [], "codes": []}
        page = self._lid_page([(200, tried)])
        kept = {"sha256": "ab", "words": "Layout: a quiet centred mark.", "seen_not_taken": ["LUMIERE PARIS"],
                "taken": {"layout": "a centred mark on a wide quiet field", "mood": "calm", "finish": "soft-touch matte",
                          "type_style": "thin serif capitals", "colour_words": "blush with warm gold",
                          "take": "quiet space around one gold line"},
                "cost_usd": "0.008", "read_before": False, "reference_id": 7, "url": "/api/tasks/1/references/7/",
                "left": 5, "over_cap": ""}
        doors = []

        def door(route):
            doors.append(route.request.url)
            route.fulfill(status=200, content_type="application/json", body=json.dumps(kept))
        page.route("**/inspiration/", door)
        said = " ".join(page.text_content("#inspiration-box").split())
        assert "Reading is reserved within the rescue budget when you add a picture" in said
        assert "a try above stays free and never uses it" in said
        page.set_input_files("#inspiration-input", files=[_file("pin.png")])
        page.wait_for_selector("#inspiration-list .inspire-item.read")
        item = page.text_content("#inspiration-list .inspire-item")
        assert "What the design takes: quiet space around one gold line" in item
        assert "Read for $0.008 · kept with this design" in item
        assert "Seen, and never copied: LUMIERE PARIS" in item
        assert "thin serif capitals" in item
        assert "Colours" in item and "blush with warm gold" in item
        assert page.query_selector("#inspiration-list .inspire-remove") is None      # kept: there is nothing to remove
        assert len(doors) == 1 and "/api/tasks/" in doors[0] and doors[0].endswith("/inspiration/")
        page.click("#adjust-form button[type=submit]")
        page.wait_for_selector("#adjust-result figure")
        assert b"filename=" not in self.posts[0]["body"]                              # a try carries no picture
