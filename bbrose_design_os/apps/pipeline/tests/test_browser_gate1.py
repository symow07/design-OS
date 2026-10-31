"""Real-browser tests for Gate-1 regeneration (2A-6E-CORR-4 §9).

The essential workflow must work with JavaScript COMPLETELY DISABLED: the
regeneration control is a plain anchor to a server-rendered confirmation
page, the confirmation is a standard HTML POST, and the dry-run result is
server-rendered. These tests run headless Chromium twice — once with
JavaScript off (the authoritative path) and once with it on (the optional
enhancement must not interfere). No provider is ever called
(GATE1_REGENERATION_MODE stays dry_run) and no job is created.
"""
from __future__ import annotations

import atexit
import shutil
import tempfile
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase
from django.test import override_settings

try:
    from playwright.sync_api import sync_playwright
    HAVE_PLAYWRIGHT = True
except ImportError:              # pragma: no cover
    HAVE_PLAYWRIGHT = False

from apps.core.models import Brand
from apps.pipeline.models import (
    ApiCallRecord,
    ConceptInfluencePlan,
    ConceptReference,
    CreativeBrief,
    DesignTask,
    Gate1RegenerationJob,
    GeneratedImage,
)
from apps.pipeline.services.concept_references import (
    build_influence_plan,
    plan_hash,
)

_MEDIA = tempfile.mkdtemp()
atexit.register(shutil.rmtree, _MEDIA, True)


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
@override_settings(MEDIA_ROOT=_MEDIA, GATE1_REGENERATION_MODE="dry_run")
class Gate1BrowserTests(DrainedStaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        import os
        # Playwright's sync API drives an event loop in this thread; Django
        # ORM calls in the test body are still synchronous test code — the
        # standard Playwright+Django arrangement.
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
        self.user = User.objects.create_superuser("bt", "bt@b.com", "pw")
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(
            brand=self.brand, task_text="Baked Powder carton",
            status="awaiting_gate_1", created_by=self.user)
        from apps.pipeline.design_intent import (
            build_design_brief, build_design_intent)
        from .direction_fixtures import valid_document
        raw = valid_document()
        document = build_design_intent(
            brief=build_design_brief({
                "brand": "BBROSE", "product_name": "Baked Powder",
                "product_category": "face powder",
                "design_target": "packaging"}),
            intent=raw["design_intent"], directions=raw["directions"])
        self.brief = CreativeBrief.objects.create(
            task=self.task,
            design_intent={k: v for k, v in document.items()
                           if k != "directions"},
            directions=document["directions"],
            selected_direction_id=document["directions"][0]["direction_id"])
        from apps.pipeline.tests.quality_fixtures import reviewed
        reviewed(GeneratedImage.objects.create(
            task=self.task, direction_name="d", prompt_used="p",
            variation_number=1))
        rows = []
        for index in range(2):
            (Path(_MEDIA) / f"bt{index}.png").write_bytes(b"\x89PNG")
            rows.append(ConceptReference.objects.create(
                task=self.task, source_type="HISTORICAL_DESIGN_REFERENCE",
                library_item_id=f"design_reference:bt{index}",
                title=f"bt{index}", image_root="media",
                image_path=f"bt{index}.png",
                permission_status=ConceptReference.PERMISSION_APPROVED,
                approved_by=self.user))
        self.rows = rows
        plan = build_influence_plan(self.task, rows)
        self.plan = ConceptInfluencePlan.objects.create(
            task=self.task, plan=plan, plan_hash=plan_hash(plan),
            created_by=self.user)
        self.confirm_url = (f"{self.live_server_url}/dashboard/tasks/"
                            f"{self.task.pk}/gate1-regeneration/confirm/")

    def _context(self, java_script_enabled=True):
        from importlib import import_module
        from django.conf import settings
        engine = import_module(settings.SESSION_ENGINE)
        store = engine.SessionStore()
        store['_auth_user_id'] = str(self.user.pk)
        store['_auth_user_backend'] = \
            'django.contrib.auth.backends.ModelBackend'
        store['_auth_user_hash'] = self.user.get_session_auth_hash()
        store.create()
        ctx = self._browser.new_context(
            java_script_enabled=java_script_enabled)
        host = self.live_server_url.split('//')[1].split(':')[0]
        ctx.add_cookies([{'name': 'sessionid', 'value': store.session_key,
                          'domain': host, 'path': '/'}])
        return ctx

    def _assert_nothing_created(self, calls_before):
        assert Gate1RegenerationJob.objects.count() == 0
        assert ApiCallRecord.objects.count() == calls_before
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_gate_1"

    def test_full_dry_run_flow_with_javascript_disabled(self):
        calls_before = ApiCallRecord.objects.count()
        images_before = set(GeneratedImage.objects
                            .values_list("pk", flat=True))
        ctx = self._context(java_script_enabled=False)
        page = ctx.new_page()
        page.goto(self.confirm_url, wait_until='domcontentloaded')
        body = page.text_content('body')
        # [the owner's answer to the UI directions of 2026-09-25: the page is in the one shell and says its heading in
        # words — it read "Regenerate the Gate-1 concept set"]
        assert "Draw the concepts again" in body
        for row in self.rows:
            assert f"#{row.pk} {row.title}" in body
        assert self.plan.plan_hash[:16] in body
        assert "DRY RUN" in body
        assert "Editorial Panel" in body
        # a standard HTML form submit — no JavaScript anywhere
        page.click('button[type="submit"]')
        page.wait_for_load_state('domcontentloaded')
        result = page.text_content('body')
        assert "DRY_RUN_ACCEPTED" in result
        assert "Diagnostic request ID" in result
        assert "no provider was called" in result.lower() \
            or "no provider" in result
        self._assert_nothing_created(calls_before)
        assert set(GeneratedImage.objects.values_list("pk", flat=True)) == \
            images_before
        ctx.close()

    def test_cancel_link_works_without_javascript(self):
        ctx = self._context(java_script_enabled=False)
        page = ctx.new_page()
        page.goto(self.confirm_url, wait_until='domcontentloaded')
        page.click('a:has-text("Cancel")')
        page.wait_for_load_state('domcontentloaded')
        assert "/dashboard/" in page.url
        assert Gate1RegenerationJob.objects.count() == 0
        ctx.close()

    def test_error_page_is_visible_without_javascript(self):
        self.task.status = "completed"
        self.task.save()
        ctx = self._context(java_script_enabled=False)
        page = ctx.new_page()
        page.goto(self.confirm_url, wait_until='domcontentloaded')
        body = page.text_content('body')
        assert "TASK_STATE_REJECTED" in body
        assert "Regeneration refused" in body
        ctx.close()

    def test_dashboard_anchor_reaches_the_confirmation_with_js_enabled(self):
        """The optional JS enhancement must not interfere: the dashboard's
        REVIEW AND REGENERATE control is a plain anchor whose navigation
        lands on the server-rendered confirmation page."""
        calls_before = ApiCallRecord.objects.count()
        ctx = self._context(java_script_enabled=True)
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(f"{self.live_server_url}/dashboard/designs/{self.task.pk}/",
                  wait_until='networkidle')  # [the owner's answer to the UI directions of 2026-09-25: a design's step is drawn on its own page]
        page.wait_for_selector('#mat-ref-regen-link', timeout=15000)
        anchor = page.get_attribute('#mat-ref-regen-link', 'href')
        assert anchor.endswith(
            f"/dashboard/tasks/{self.task.pk}/gate1-regeneration/confirm/")
        # §BH55 Phase 3: the panel said "MATERIAL REFERENCES APPROVED: 2 — REGENERATION READY"; it says it in words
        assert "the concepts can be drawn again with them" in \
            page.text_content('#material-reference-panel')
        page.click('#mat-ref-regen-link')
        page.wait_for_load_state('domcontentloaded')
        assert page.url.endswith("/gate1-regeneration/confirm/")
        assert "Draw the concepts again" in \
            page.text_content('body')  # [2026-09-25: in words — it read "Regenerate the Gate-1 concept set"]
        assert not errors, errors
        self._assert_nothing_created(calls_before)
        ctx.close()

    def test_each_paid_step_says_what_it_costs_before_the_click(self):
        """§BH55 Phase 3 (survey rows 1.15, 6.26, 1.4): the direction step, the concepts step and the size step spend on
        the paid services, and none of them said so — only the redraw did. Each says it now, measured on the ledger's own
        rows, with the picture model and its size named where pictures are drawn."""
        from apps.pipeline.models import ApiCallRecord
        for operation, usd in (("creative_directions", 0.08), ("image_prompts", 0.04), ("qa_vision_review", 0.05),
                               ("dieline_estimation", 0.01)):
            ApiCallRecord.objects.create(task=self.task, provider="anthropic", model="m", operation=operation,
                                         cost_usd=usd)
        ApiCallRecord.objects.create(task=self.task, provider="openai", model="gpt-image", operation="image:d",
                                     image_count=1, cost_usd=0.25)
        from django.core.cache import cache
        cache.delete("pipeline:spend_estimates/2")
        ctx = self._context(java_script_enabled=True)
        page = ctx.new_page()
        page.goto(f"{self.live_server_url}/dashboard/designs/{self.task.pk}/",
                  wait_until='networkidle')                             # the concepts step, as the fixture stands
        page.wait_for_selector('#gate1-actions .spend-note', timeout=15000)
        shown = page.inner_text('#gate1-actions')
        assert "Using a concept spends about $0.01 — the product has no size on record" in shown, shown
        assert "Asking for changes applies your notes to the current concepts" in shown, shown
        DesignTask.objects.filter(pk=self.task.pk).update(status="awaiting_direction_selection")
        page.evaluate(f"loadTask({self.task.pk})")                      # the direction step
        page.wait_for_selector('#direction-view .spend-note', timeout=15000)
        note = page.inner_text('#direction-view .spend-note')
        assert note.startswith("Choosing a direction spends about $0.94"), note
        assert "3 drawings" in note and "measured on past designs" in note, note
        ctx.close()

    def test_bh71_the_trend_pictures_are_shown_ticked_before_the_directions_and_one_click_unticks_one(self):
        """§BH71 PART 2, the owner's goal of 2026-09-28: "Show the found pictures on the design page before directions.
        They are used by default; I can untick any I dislike in one click." In a real browser: the board is drawn in
        its own place above the directions, each picture numbered and ticked, where it was found and its page, its
        thumbnail from the site's own origin; one click posts the untick; the press posts once and moves the design
        on with the ticked pictures only."""
        from datetime import timedelta
        from unittest.mock import patch

        from django.utils import timezone
        from PIL import Image

        from apps.pipeline.models import InspirationReading, TrendBoard, TrendPick
        from apps.pipeline.services import trend_board
        quarantine = Path(tempfile.mkdtemp(prefix="trendq_"))
        self.addCleanup(shutil.rmtree, quarantine, True)
        CreativeBrief.objects.filter(pk=self.brief.pk).delete()             # no direction exists yet
        DesignTask.objects.filter(pk=self.task.pk).update(status="awaiting_trend_review")
        board = TrendBoard.objects.create(
            task=self.task, status=TrendBoard.READY, subject="cosmetic powder compact packaging",
            review_deadline=timezone.now() + timedelta(seconds=120),
            refusals={"pinterest": {"mode": "LINK", "words": trend_board.LINK_WORDS["pinterest"]}})
        picks = []
        for n in (1, 2):
            thumb = quarantine / ("thumb_%d.png" % n)
            Image.new("RGB", (60, 40), (40 * n, 120, 150)).save(thumb)
            sha = ("%d" % n) * 64
            InspirationReading.objects.create(sha256=sha, reading={
                "layout": "layout %d" % n, "mood": "calm", "finish": "", "type_style": "", "colour_words": "",
                "take": "the take of picture %d" % n, "seen_not_taken": []})
            picks.append(TrendPick.objects.create(
                board=board, number=n, kind=TrendPick.PICTURE, platform="dribbble", title="t%d" % n,
                page_url="https://dribbble.com/shots/%d" % n, image_url="https://cdn.dribbble.com/%d.png" % n,
                sha256=sha, thumb_path=str(thumb), thumb_width=60, thumb_height=40, used=True))
        TrendPick.objects.create(board=board, number=3, kind=TrendPick.LINK, platform="pinterest",
                                 page_url="https://www.pinterest.com/pin/1/", title="a powder carton")
        posts = []
        with override_settings(WEB_QUARANTINE_ROOT=str(quarantine)), \
                patch("apps.pipeline.tasks.run_aria_pipeline.delay") as run:
            ctx = self._context(java_script_enabled=True)
            # closed however the test ends: a context left open keeps the live server's connections alive, and its
            # drain (§BH41) then refuses the next test's flush
            self.addCleanup(ctx.close)
            page = ctx.new_page()
            page.on("request", lambda r: posts.append(r.url) if r.method == "POST" else None)
            page.goto(f"{self.live_server_url}/dashboard/designs/{self.task.pk}/", wait_until="domcontentloaded")
            page.wait_for_selector("#trend-view .trend-card", timeout=15000)
            page.wait_for_function("() => [...document.querySelectorAll('#trend-view img')]"
                                   ".every(i => i.complete && i.naturalWidth > 0)", timeout=15000)
            numbers = page.eval_on_selector_all("#trend-view .trend-card", "els => els.map(e => e.dataset.number)")
            assert numbers == ["1", "2"], numbers
            ticks = page.eval_on_selector_all("#trend-view input[data-pick]", "els => els.map(e => e.checked)")
            assert ticks == [True, True], ticks                            # used by default
            sources = page.eval_on_selector_all("#trend-view img", "els => els.map(e => e.getAttribute('src'))")
            assert all(s.startswith("/api/tasks/%d/trends/" % self.task.pk) for s in sources), sources
            shown = page.inner_text("#trend-view")
            assert "Found on Dribbble" in shown and "the take of picture 1" in shown, shown
            # the link card and its reason — [his goal of 2026-10-10, item 3] a link naming the design's own product
            assert "a powder carton" in shown and "robots.txt" in shown, shown
            assert "Make the directions now with 2 pictures" in shown, shown
            assert page.is_hidden("#direction-view .direction-card")         # before the directions
            with page.expect_response(lambda r: "/trends/%d/" % picks[0].pk in r.url):
                page.click("#trend-view input[data-pick='%d']" % picks[0].pk)   # one click
            picks[0].refresh_from_db()
            assert picks[0].used is False
            assert page.inner_text("#trend-continue") == "Make the directions now with 1 picture"
            with page.expect_response(lambda r: r.url.endswith("/trends/continue/")):
                page.click("#trend-continue")
        board.refresh_from_db()
        assert board.status == TrendBoard.CONFIRMED and board.used_at_confirm == [picks[1].pk]
        assert board.confirmed_how == trend_board.BY_HIS_CLICK
        run.assert_called_once_with(self.task.pk)
        assert len([u for u in posts if u.endswith("/trends/continue/")]) == 1

    def test_bh71_a_concept_close_to_a_trend_picture_is_said_beside_it(self):
        """§BH71 PART 2 "never near-copied": the concept's card says it is close to a trend picture its directions
        used, and which — look before you choose it; the concept stays choosable."""
        image = GeneratedImage.objects.get(task=self.task)
        image.reference_provenance = {"trend_near_copy": {
            "method": "the house's 8×8 average hash; 10 bits or fewer of 64 apart is close", "compared_with": 4,
            "compared": True, "close_to": [{"number": 3, "platform": "Dribbble", "bits_apart": 4}]}}
        image.save()
        ctx = self._context(java_script_enabled=True)
        self.addCleanup(ctx.close)                   # closed however it ends: the live server's drain needs it
        page = ctx.new_page()
        page.goto(f"{self.live_server_url}/dashboard/designs/{self.task.pk}/", wait_until="networkidle")
        page.wait_for_selector(".image-card .near-copy", timeout=15000)
        said = page.inner_text(".image-card .near-copy")
        assert said == "Close to trend picture 3 (found on Dribbble, 4 of 64 apart) — look before you choose it.", said
        assert page.is_visible(".image-card .btn-approve")                  # still choosable: nothing removed

    def test_his_blocker_123_three_shown_though_too_alike_carry_the_note_in_words(self):
        """[His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (2): "Every
        "not distinct" check: it never stops a design. On failure it retries once with the reason; if it still fails, it
        shows me the three anyway with a note, and I choose."]
        The note stands beside the concepts, in words — never a code; the concepts stay choosable."""
        from apps.pipeline.direction_signature import SHOWN_ALIKE_KEY
        from apps.pipeline.models import AgentLog
        AgentLog.objects.create(task=self.task, agent_name="ARIA", action="ARIA: structured directions validated",
                                payload={SHOWN_ALIKE_KEY: {"codes": ["EMOTIONAL_TONE_NOT_DISTINCT"],
                                                           "alike_attempts": [1, 2], "attempts": 2}})
        ctx = self._context(java_script_enabled=True)
        self.addCleanup(ctx.close)                   # closed however it ends: the live server's drain needs it
        page = ctx.new_page()
        page.goto(f"{self.live_server_url}/dashboard/designs/{self.task.pk}/", wait_until="networkidle")
        page.wait_for_selector(".alike-note", timeout=15000)
        said = page.inner_text(".alike-note")
        assert said == ("Shown anyway: the three directions came back too alike twice — their mood was too alike; made "
                        "once more with that reason, they did not change. You choose."), said
        assert "NOT_DISTINCT" not in page.inner_text("#gallery-state")
        assert page.is_visible(".image-card .btn-approve")                  # still choosable: nothing removed

    def test_his_second_blocker_123_the_couldnt_be_drawn_note_reaches_the_design_page(self):
        """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (4):
        "the "couldn't be drawn" note reaches the design page."] 123's Garden Wrap, stopped at drawing: the status the
        page polls carries the stop, and the page says it beside the concepts — the concept, why, each part, his
        options — in words."""
        from apps.pipeline.services import concept_design_map as dm
        image = GeneratedImage.objects.get(task=self.task)
        image.direction_name = "Garden Wrap"
        image.reference_provenance = {dm.MAP_STOP_KEY: {
            "at": "2026-10-09T09:14:42+00:00", "concept": True,
            "why": "1 of the parts it prints would not be drawn as the picture prints them",
            "parts": [{"kind": "band", "name": "scalloped pink base band",
                       "why": "its colour runs on 12 pixels past it — not a plain stripe"}],
            "options": ["choose another of the concepts", "draw these concepts again",
                        "ask for changes, in your own words"]}}
        image.save()
        ctx = self._context(java_script_enabled=True)
        self.addCleanup(ctx.close)                   # closed however it ends: the live server's drain needs it
        page = ctx.new_page()
        page.goto(f"{self.live_server_url}/dashboard/designs/{self.task.pk}/", wait_until="networkidle")
        page.wait_for_selector("text=was not drawn", timeout=15000)
        said = page.inner_text("#image-gallery")
        assert '"Garden Wrap" was not drawn: 1 of the parts it prints would not be drawn as the picture prints them.' \
            in said, said
        assert "scalloped pink base band — its colour runs on 12 pixels past it — not a plain stripe" in said, said
        assert "choose another of the concepts" in said and "MAP_STOP" not in said

    def test_his_findings_123_an_impossible_size_is_flagged_as_he_types(self):
        """[His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (6):
        "Flag impossible sizes at the size step (I typed 1123 mm for a 120 mm product; it accepted it)."] At the size
        step, 1123 mm typed for a 120 mm product is flagged in words beside the sizes as he types; 123 mm clears it."""
        from apps.core.models import Product
        from apps.dielines.models import DielineJob
        from apps.pipeline.models import PackagingOutput
        self.task.product = Product.objects.create(brand=self.brand, product_id="HC-120", name="Rose Blossom",
                                                   category="SK", year=2026, product_type="hand cream", width_mm=42,
                                                   depth_mm=27, height_mm=120)
        self.task.status = "awaiting_dimensions"
        self.task.save()
        est = {k: {"value": v, "confidence": 0.9, "source": "db", "blocked": False}
               for k, v in (("width_mm", 42.0), ("depth_mm", 27.0), ("height_mm", 120.0), ("bleed_mm", 3.0),
                            ("safe_margin_mm", 4.0), ("glue_tab_mm", 12.0))}
        PackagingOutput.objects.create(task=self.task, approved_image=GeneratedImage.objects.get(task=self.task),
                                       dieline_job=DielineJob.objects.create(template_type="reverse_tuck_end_carton",
                                                                             scenario="A", input_json={}),
                                       spec_sheet={"estimated_dimensions": dict(est, scenario="A", can_proceed=True),
                                                   "scenario": "A"})
        ctx = self._context(java_script_enabled=True)
        self.addCleanup(ctx.close)                   # closed however it ends: the live server's drain needs it
        page = ctx.new_page()
        page.goto(f"{self.live_server_url}/dashboard/designs/{self.task.pk}/", wait_until="networkidle")
        page.wait_for_selector("#dim-height_mm", timeout=15000)
        page.fill("#dim-height_mm", "1123")
        page.wait_for_selector("#dim-size-flags li", timeout=15000)
        said = page.inner_text("#dim-size-flags")
        assert "1123 mm tall is not a carton this die makes" in said and "the product is 120 mm tall" in said, said
        assert "SIZE_IMPOSSIBLE" not in said
        page.fill("#dim-height_mm", "123")
        page.wait_for_function("() => !document.querySelector('#dim-size-flags li')", timeout=15000)

    def test_a_directions_own_codes_are_said_in_words(self):
        """[the owner's answer to the UI directions of 2026-09-25, (d) "No engine codes on screen": the planner writes
        its vocabulary's names into its prose ("The LOGO_FIRST hierarchy suits…"); the card says them in words, and the
        record keeps what it wrote]"""
        directions = self.brief.directions
        directions[0]["emotional_tone"] = "The LOGO_FIRST hierarchy suits a LINEAR_ENGRAVED pattern, confirmed before Gate 2"
        CreativeBrief.objects.filter(pk=self.brief.pk).update(directions=directions)
        DesignTask.objects.filter(pk=self.task.pk).update(status="awaiting_direction_selection")
        ctx = self._context(java_script_enabled=True)
        page = ctx.new_page()
        page.goto(f"{self.live_server_url}/dashboard/designs/{self.task.pk}/", wait_until='networkidle')
        page.wait_for_selector('#direction-view .direction-card', timeout=15000)
        shown = page.inner_text('#direction-view')
        assert "The logo first hierarchy suits a linear engraved pattern, confirmed before the review" in shown, shown
        assert "LOGO_FIRST" not in shown and "LINEAR_ENGRAVED" not in shown, shown
        assert "LOGO_FIRST" in CreativeBrief.objects.get(pk=self.brief.pk).directions[0]["emotional_tone"]
        ctx.close()

    def test_a_refusal_is_drawn_where_the_person_is_looking(self):
        """§BH55 Phase 3 (survey rows 4.13, 6.14): a refused action reached the person as a browser alert — gone the
        moment it was dismissed, and saying nothing of where it came from. It is drawn in the pane now, and no dialog
        is thrown."""
        ctx = self._context(java_script_enabled=True)
        page = ctx.new_page()
        thrown = []
        page.on("dialog", lambda d: (thrown.append(d.message), d.dismiss()))
        page.goto(f"{self.live_server_url}/dashboard/designs/{self.task.pk}/",
                  wait_until='networkidle')  # [the owner's answer to the UI directions of 2026-09-25: a design's step is drawn on its own page]
        page.wait_for_selector('#gate1-actions', timeout=15000)
        page.evaluate(f"postAction('/api/tasks/{self.task.pk}/gate2_approve/', {{packaging_output_id: 1}})")
        page.wait_for_selector('#refusal-note:not([hidden])', timeout=10000)
        shown = page.inner_text('#refusal-note')
        assert shown.startswith("It was refused."), shown
        assert shown.strip() != "It was refused.", shown         # the server's own words stand beside it
        assert thrown == [], thrown                              # nothing was thrown as a browser dialog
        ctx.close()

    def test_a_state_with_no_panel_says_where_it_stands_and_a_stuck_design_can_be_resumed(self):
        """§BH55 Phase 3 (survey rows 1.18, 6.24, 4.21, 6.22): a state with no panel of its own drew nothing at all —
        the pane was blank and the design looked lost; and a design stopped mid-step had no way on from its own page."""
        ctx = self._context(java_script_enabled=True)
        page = ctx.new_page()
        page.goto(f"{self.live_server_url}/dashboard/designs/{self.task.pk}/",
                  wait_until='networkidle')  # [the owner's answer to the UI directions of 2026-09-25: a design's step is drawn on its own page]
        DesignTask.objects.filter(pk=self.task.pk).update(status="design_intent_confirmed")
        page.evaluate(f"loadTask({self.task.pk})")
        page.wait_for_selector('#state-note:not([hidden])', timeout=15000)
        note = page.inner_text('#state-note')
        assert "Design intent confirmed" in note, note
        assert "Open its history" in note, note
        DesignTask.objects.filter(pk=self.task.pk).update(status="gate_1_approved")
        page.evaluate(f"loadTask({self.task.pk})")
        page.wait_for_selector('#resume-note', timeout=15000)
        resume = page.inner_text('#resume-note')
        assert "Its concept was chosen and the step after it has not finished." in resume, resume
        assert "a paid step" in resume, resume
        assert page.is_visible("#resume-note button"), resume
        ctx.close()

    def test_the_reference_panel_says_each_reference_in_words(self):
        """§BH55 Phase 3: the panel printed each reference as stored — "#12 bt0 · HISTORICAL_DESIGN_REFERENCE · raster ·
        score 0.0", "ownership: OWNERSHIP_UNCONFIRMED · rights: RIGHTS_UNREVIEWED", "permission:
        USER_APPROVED_FOR_CONCEPT_REFERENCE" — with "Frontend build: …" and "Regenerate Gate-1 set". It says each in words
        now; which scripts loaded stays on the panel, as its data-build attribute."""
        import re
        ctx = self._context(java_script_enabled=True)
        page = ctx.new_page()
        page.goto(f"{self.live_server_url}/dashboard/designs/{self.task.pk}/",
                  wait_until='networkidle')  # [the owner's answer to the UI directions of 2026-09-25: a design's step is drawn on its own page]
        page.wait_for_selector('#mat-ref-regen-link', timeout=15000)
        shown = page.inner_text('#material-reference-panel')
        assert not re.search(r"\b[A-Z]{3,}_[A-Z_]{3,}\b|Gate-1|Frontend build|score \d|#\d", shown), shown
        assert shown.count("approved — a reference for this design's concepts only") == 2, shown
        assert "a past BBROSE design" in shown and "whose it is: not confirmed" in shown
        assert "2 references approved — you can draw the concepts again with them." in shown
        assert page.get_attribute('#material-reference-panel', 'data-build').startswith("page ")
        ctx.close()
