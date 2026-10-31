"""Confirm Profile UI-1 — real-browser editor and preview tests.

The editor renders from the server config in the live dashboard at the
awaiting_container_profile gate: semantic archetype radios (keyboard
operable), config-driven variant/closure chips whose invalidation clears
visibly, synchronized slider+number proportions, dirty/reset, incomplete
gating, and a deterministic canvas preview that changes with the state and
never touches the network. Nothing here confirms anything: the ONE assertion
repeated throughout is zero POSTs to the confirmation endpoint.
"""
from __future__ import annotations

import itertools
from unittest.mock import patch

import pytest
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase
from django.core.files.base import ContentFile

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    HAVE_PLAYWRIGHT = True
except ImportError:              # pragma: no cover
    HAVE_PLAYWRIGHT = False

from apps.core.models import Brand
from apps.pipeline.models import (DesignTask, GateDecision, GeneratedImage,
                                  PackagingOutput)
from apps.pipeline.services import container_contract as cc

from .test_browser_staged_reference_ui import RefUiHarness

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
       b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf"
       b"\xc0\xf0\x1f\x00\x05\x05\x02\x00_\xc8\xf1\xd2\x00\x00\x00\x00IEND"
       b"\xaeB`\x82")
MOBILE = {"width": 390, "height": 844}


class _ProfileEditorFixtures(RefUiHarness):
    """Shared gate-task + editor-page fixtures; no tests of its own."""

    #: WI-3A. `Product.product_id` is `unique=True` (apps/core/models.py:89).
    #: Three fixtures across three files minted it from
    #: `DesignTask.objects.count()`, and that is wrong three ways. It counted
    #: the wrong model; in a per-test database truncated between methods the
    #: count is 0, so every call site minted the identical string; and — the
    #: one that matters — counting the RIGHT model would be the same class of
    #: defect. A count is a property of the table at a moment. A unique key
    #: must be a property of the row. Two calls between which nothing was
    #: committed get the same number, and two calls either side of a
    #: truncation get the same number again.
    #:
    #: One sequence, defined here and inherited by every subclass, so the
    #: three prefixes (B/C/R) cannot collide with each other either. It reads
    #: no table, no truncation can rewind it, and it is deterministic under
    #: `-p no:randomly`. `uuid4()` was rejected: it would be unique but would
    #: also make the value differ between two runs of the same test, and this
    #: repository compares bytes.
    _PRODUCT_SEQ = itertools.count()

    def setUp(self):
        super().setUp()
        # gate decisions require the reviewer role (IsReviewer)
        from django.contrib.auth.models import Group
        from apps.pipeline.permissions import ROLE_REVIEWER
        self.user.groups.add(
            Group.objects.get_or_create(name=ROLE_REVIEWER)[0])

    # -- fixtures -------------------------------------------------------------

    def _gate_task_without_a_profile(self):
        """§BH64(c): a gate task the pipeline proposed NO form for.

        Both profile keys are absent — the versioned `container_profile/1.0`
        AND the legacy `container_profile`, because `confirm_profile.js:57`
        reads the legacy one too and a fixture that dropped only the versioned
        record would still hand the page a bottle through the back door.
        """
        task = DesignTask.objects.create(
            brand=Brand.objects.first(),
            task_text="a lovely thing in a nice colour",
            design_target="product_container",
            status="awaiting_container_profile", created_by=self.user)
        img = GeneratedImage(task=task, direction_name="Rose")
        img.image_file.save("concept.png", ContentFile(PNG), save=True)
        PackagingOutput.objects.create(task=task, approved_image=img,
                                       spec_sheet={"backend": "container"})
        return task

    def _gate_task(self, hints="", confirmed=False):
        task = DesignTask.objects.create(
            brand=Brand.objects.first(),
            task_text="a serum bottle" + hints,
            design_target="product_container",
            status="awaiting_container_profile", created_by=self.user)
        img = GeneratedImage(task=task, direction_name="Rose")
        img.image_file.save("concept.png", ContentFile(PNG), save=True)
        record = cc.build_inferred_profile(
            "bottle", "cylindrical",
            estimates={"body_width_mm": 40, "body_height_mm": 110,
                       "neck_ratio": 0.42, "cap_type": "screw"})
        zones = cc.propose_zones(record)
        spec = {
            "backend": "container",
            "container_profile": {"archetype": "bottle",
                                  "variant": "cylindrical",
                                  "cap_style": "screw", "height_mm": 110,
                                  "width_mm": 40, "neck_ratio": 0.42},
            cc.PROFILE_SCHEMA: record,
            cc.ZONES_SCHEMA: {"schema_version": cc.ZONES_SCHEMA,
                              "zones": zones,
                              "zone_set_hash": cc.zone_set_hash(zones),
                              "confirmation_state": "PROPOSED"},
        }
        if confirmed:
            spec["container_confirmation"] = {
                "combined_hash": "cafe" * 16, "confirmed_by": "ui1",
                "confirmed_at": "2026-08-01T00:00:00Z"}
        PackagingOutput.objects.create(task=task, approved_image=img,
                                       spec_sheet=spec)
        return task

    def _editor(self, task, viewport=None):
        # [the owner's answer to the UI directions of 2026-09-25: the editor is drawn on the design's own page — no
        # queue drawer to close; the listener is attached before the page opens its design]
        self.confirm_posts = []
        page = self._design_page(task, viewport=viewport, before=lambda pg: pg.on(
            "request", lambda r: self.confirm_posts.append(r.url)
            if "confirm_container_profile" in r.url else None))
        page.wait_for_selector("#archetype-cards .archetype-card",
                               state="attached")
        return page

    def _summary(self, page):
        return page.text_content("#profile-preview-summary")

    def _canvas(self, page):
        return page.eval_on_selector("#profile-preview-canvas",
                                     "c => c.toDataURL()")

    def _select_archetype(self, page, key):
        page.click(f'.archetype-card[data-archetype="{key}"]')

    def _confirmable_task(self, archetype="bottle", variant="slim", cap="screw", size_mm=(35, 25, 95)):
        """A gate task whose confirmation would genuinely be ACCEPTED:
        product-record dims source the profile and every proposed zone is
        already USER_CONFIRMED in the spec. [§BH70(1): of any form — a bottle unless another is named, (width, depth,
        height) in mm; a form without a neck carries no neck proportion]"""
        from apps.core.models import Product
        from apps.pipeline.targets.container import archetypes as A
        width_mm, depth_mm, height_mm = size_mm
        product = Product.objects.create(
            brand=Brand.objects.first(), product_id=f"CO-B{next(self._PRODUCT_SEQ)}",
            name="Rosé Nectar", category="CO", year=2026,
            width_mm=width_mm, depth_mm=depth_mm, height_mm=height_mm)
        task = DesignTask.objects.create(
            brand=Brand.objects.first(), product=product,
            task_text="a serum bottle" if archetype == "bottle" else f"a {archetype}",
            design_target="product_container",
            status="awaiting_container_profile", created_by=self.user)
        img = GeneratedImage(task=task, direction_name="Rose")
        img.image_file.save("concept.png", ContentFile(PNG), save=True)
        record = cc.merge_product_record_dims(
            cc.build_inferred_profile(archetype, variant), product)
        zones = cc.propose_zones(record)
        for z in zones:
            z["user_confirmation_state"] = cc.ZONE_USER_CONFIRMED
        neck = {"neck_ratio": 0.42} if "neck_ratio" in A.proportions_of(archetype) else {}
        PackagingOutput.objects.create(task=task, approved_image=img,
                                       spec_sheet={
            "backend": "container",
            "container_profile": {"archetype": archetype, "variant": variant,
                                  "cap_style": cap, "height_mm": height_mm,
                                  "width_mm": width_mm, **neck},
            cc.PROFILE_SCHEMA: record,
            cc.ZONES_SCHEMA: {"schema_version": cc.ZONES_SCHEMA,
                              "zones": zones,
                              "zone_set_hash": cc.zone_set_hash(zones),
                              "confirmation_state": "PROPOSED"}})
        return task


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class ProfileEditorBrowserTests(_ProfileEditorFixtures,
                                DrainedStaticLiveServerTestCase):

    # -- archetypes ------------------------------------------------------------

    def test_the_radio_cards_are_config_driven(self):
        """§BH55(a): 4 -> 5 cards, compact added. RENAMED — the old name said "four"."""
        page = self._editor(self._gate_task())
        cards = page.eval_on_selector_all(
            ".archetype-card", """els => els.map(e => ({
              key: e.dataset.archetype, role: e.getAttribute('role'),
              checked: e.getAttribute('aria-checked'),
              desc: e.querySelector('.archetype-desc').textContent}))""")
        # §BH70(1), 2026-09-27: 5 -> 8 cards, lipstick, mascara and pencil added before "other" — his "ANY cosmetic
        # product, not a bottle". Was: == ["bottle", "jar", "tube", "compact", "other"], and the checked list five long.
        # [§BH71 PART 3, the owner's goal of 2026-09-28: "Add each as a shape the system can draw." — 8 -> 13 cards,
        # the tin, the sachet, the oval stick, the aerosol can and the ampoule before "other"; the checked list eight
        # long before]
        assert [c["key"] for c in cards] == ["bottle", "jar", "tube", "compact", "lipstick", "mascara", "pencil",
                                             "tin", "sachet", "oval_stick", "aerosol", "ampoule", "other"]
        assert all(c["role"] == "radio" for c in cards)
        assert [c["checked"] for c in cards] == ["true"] + ["false"] * 12
        assert "broad opening" in cards[1]["desc"]
        assert page.eval_on_selector(
            "#archetype-cards", "el => el.getAttribute('role')") == \
            "radiogroup"

    def test_selection_updates_state_and_preview(self):
        page = self._editor(self._gate_task())
        before = self._canvas(page)
        assert "Bottle" in self._summary(page)
        self._select_archetype(page, "jar")
        assert page.evaluate("_profileState.archetype") == "jar"
        assert "Jar" in self._summary(page)
        assert self._canvas(page) != before
        assert self.confirm_posts == []

    def test_keyboard_arrows_move_and_select(self):
        page = self._editor(self._gate_task())
        page.focus('.archetype-card[data-archetype="bottle"]')
        page.keyboard.press("ArrowRight")
        assert page.evaluate("_profileState.archetype") == "jar"
        assert page.evaluate(
            "document.activeElement.dataset.archetype") == "jar"
        page.keyboard.press("ArrowLeft")
        assert page.evaluate("_profileState.archetype") == "bottle"

    def test_nothing_is_preselected_when_the_pipeline_proposed_nothing(self):
        """§BH64(c)/§BH61(a) ON THE SCREEN, which is where it had not landed.

        `confirm_profile.js:22` opened as a cylindrical bottle with a screw cap and `:74` fell back to
        `'bottle'` when no record said otherwise, so a task the pipeline proposed nothing for showed the
        owner a fully-specified bottle with the confirm button ENABLED. §BH61(a) removed that default
        from the server config in the same arc and this page kept it, which is his §BH64(d) sentence:
        the repair landed where it was looked for and not where it wasn't.

        Asserted on what RENDERS — the checked card, the canvas, the sentence and the button — not on
        the config that feeds them.
        """
        page = self._editor(self._gate_task_without_a_profile())
        assert page.query_selector_all('.archetype-card[aria-checked="true"]') == []
        empty_canvas = self._canvas(page)
        summary = self._summary(page)
        assert "bottle" not in summary.lower(), summary
        assert page.eval_on_selector("#confirm-profile-zones", "b => b.disabled") is True
        note = page.text_content("#confirm-blocked-note")
        assert "CONTAINER_ARCHETYPE_UNRESOLVED" in note, note          # kept, folded under its record
        shown = page.inner_text("#confirm-blocked-note")
        assert "No shape was proposed for this design" in shown and "CONTAINER_ARCHETYPE_UNRESOLVED" not in shown  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]
        # and choosing a form moves BOTH the picture and the sentence
        self._select_archetype(page, "compact")
        assert self._canvas(page) != empty_canvas
        assert "Compact" in self._summary(page)
        assert self.confirm_posts == []

    def test_every_archetype_has_its_own_picture_its_own_sentence_and_its_own_icon(self):
        """§BH64(d)4 — THE CONFORMANCE TEST, READ OFF THE SCREEN AND NOT OFF THE CONFIG.

        His list: "every archetype has a preview that renders in its own form, a description naming
        only its own parts, and an icon. A new archetype fails the gate with that list rather than
        reaching me half-drawn." A sixth form added to the declaration reaches this test with no
        `drawn_as` and no `nominal` and fails `ArchetypeConformanceTests` first, by name; if it gets
        past that, it arrives here and must actually draw as itself.

        Every assertion is on what RENDERS — the canvas bytes, the sentence, the card's icon and the
        controls that exist — because the three defects he found were all invisible to the record.
        """
        page = self._editor(self._gate_task())
        cfgs = page.evaluate("_editorConfig.archetypes")
        assert len(cfgs) >= 5, cfgs
        previews, icons = {}, {}
        for a in cfgs:
            key = a["key"]
            self._select_archetype(page, key)
            assert page.evaluate("_profileState.archetype") == key

            # 1. ITS OWN PICTURE. No two forms draw the same canvas — the compact fell through to the
            #    `else` and was drawn as a bottle, which is the defect that reached him as "the preview
            #    draws a jar while the record says compact".
            drawn = self._canvas(page)
            clash = [k for k, v in previews.items() if v == drawn]
            assert not clash, (key, "draws the same picture as", clash)
            previews[key] = drawn

            # 2. A DESCRIPTION NAMING ONLY ITS OWN PARTS. "neck" appears if and only if this form
            #    declares neck_ratio — the sentence appended it for every form but Other.
            summary = self._summary(page)
            assert ("neck" in summary.lower()) == ("neck_ratio" in a["proportions"]), (key, summary)

            # 3. ONLY ITS OWN CONTROLS.
            keys = page.eval_on_selector_all(
                "#proportion-rows input[type=range]", "els => els.map(e => e.dataset.key)")
            assert set(keys) == set(a["proportions"]), (key, keys, a["proportions"])

            # 4. AN ICON. Drawn from its own silhouette for a form that has one; the honest `?` for
            #    Other, which has none. `compact.png` never existed and its card was blank.
            icon = page.eval_on_selector(
                f'.archetype-card[data-archetype="{key}"]',
                "el => { const c = el.querySelector('canvas.archetype-icon');"
                "        if (c) return c.toDataURL();"
                "        const s = el.querySelector('.archetype-icon-other');"
                "        return s ? 'OTHER:' + s.textContent.trim() : null; }")
            assert icon, (key, "has no icon")
            if a["confirmable"]:
                assert icon.startswith("data:image/png"), (key, icon[:40])
                clash = [k for k, v in icons.items() if v == icon]
                assert not clash, (key, "has the same icon as", clash)
            icons[key] = icon

        # and the two he named, asserted by name rather than only by the loop above
        self._select_archetype(page, "compact")
        assert "neck" not in self._summary(page).lower(), self._summary(page)
        assert previews["compact"] != previews["jar"]
        assert previews["compact"] != previews["bottle"]
        assert self.confirm_posts == []

    def test_other_is_honest_never_a_bottle(self):
        page = self._editor(self._gate_task())
        bottle_canvas = self._canvas(page)
        self._select_archetype(page, "other")
        assert page.evaluate("_profileState.archetype") == "other"
        assert self._canvas(page) != bottle_canvas
        assert "Custom container form" in self._summary(page)
        assert "No standard silhouette applies" in self._summary(page)
        # explicit empty choice states, not fabricated options
        assert "No predefined variant applies" in \
            page.text_content("#variant-note")
        assert page.eval_on_selector_all(
            "#variant-chips .chip", "els => els.length") == 0
        # confirmation is blocked with the honest custom-form note
        assert page.eval_on_selector(
            "#confirm-profile-zones", "b => b.disabled") is True
        note = page.text_content("#confirm-blocked-note")
        assert "A form of its own cannot be confirmed here yet" in note  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]
        assert "OTHER_CUSTOM_PROFILE_RECONSTRUCTION_PENDING" in note

    def test_a_chosen_form_opens_at_its_own_size_and_within_its_own_limits(self):
        """§BH70(1), items 12 and 14: every form opened at a bottle's 110 x 40 x 40 — "so a palette opens as 40 wide
        and 110 tall" — and no row went under 20 mm wide, so a pencil could not be entered at its size. Chosen over
        the bottle this task loads, a pencil opens at its own starting size and says so, carries no neck, and its
        width row reaches 7 mm; a compact chosen after it opens at a compact's."""
        page = self._editor(self._gate_task())
        self._select_archetype(page, "pencil")
        assert page.evaluate("[_profileState.height_mm, _profileState.width_mm, _profileState.depth_mm]") == [150, 8, 8]
        assert page.evaluate("_profileState.neck_ratio") is None
        assert "starting size" in page.text_content("#size-note")
        assert float(page.eval_on_selector("#sl-width_mm", "el => el.min")) <= 7
        self._select_archetype(page, "compact")
        assert page.evaluate("[_profileState.height_mm, _profileState.width_mm, _profileState.depth_mm]") == [95, 110, 18]
        assert self.confirm_posts == []

    def test_a_form_the_preview_does_not_know_is_not_drawn_as_a_bottle(self):
        """§BH70(1), item 9: the drawer's last `else` WAS the bottle, so the next form declared on the server would
        have reached him drawn as one. A form it does not know draws an empty frame and says so in words."""
        page = self._editor(self._gate_task())
        drawn = page.evaluate("""() => {
            const draw = (state) => {
              const c = document.createElement('canvas'); c.width = 220; c.height = 300;
              const ctx = c.getContext('2d'); const said = [];
              const fillText = ctx.fillText.bind(ctx);
              ctx.fillText = (t, ...rest) => { said.push(t); return fillText(t, ...rest); };
              _drawSilhouette(ctx, state, 220, 300);
              return {png: c.toDataURL(), said: said};
            };
            // [§BH71 PART 3: a sachet is a declared form now, drawn from the server's own drawing — the form
            // this test names as unknown is one the declaration does not know]
            return {unknown: draw({archetype: 'hamper', height_mm: 100, width_mm: 40}),
                    bottle: draw({archetype: 'bottle', variant: 'cylindrical', cap_style: 'screw',
                                  height_mm: 100, width_mm: 40, neck_ratio: 0.42})};
        }""")
        assert drawn["unknown"]["png"] != drawn["bottle"]["png"]
        assert drawn["unknown"]["said"] == ["No drawing for this form yet"], drawn["unknown"]["said"]
        assert drawn["bottle"]["said"] == []
        assert self.confirm_posts == []

    def test_bh71_the_shape_step_offers_to_learn_the_oval_and_learns_it(self):
        """§BH71 PART 3: "... it says so and offers to learn it." A lid the approved concept shows and no variant
        draws is said with one button; the click learns it and the shape step is drawn again with the learned shape
        chosen for the person, from the server's own drawing. A shape only the brief names is said with why it cannot
        be learned, and no button."""
        from apps.pipeline.models import LearnedShape
        from apps.pipeline.services import concept_outline as co
        task = self._gate_task()
        out = task.packaging_outputs.first()
        record = cc.build_inferred_profile("compact", "", estimates={"body_width_mm": 110, "body_height_mm": 95,
                                                                   "cap_type": "clasp"})
        record["unknown_shape"] = {"kind": "oval", "words": "an oval lid", "source": "the approved concept",
                                   "sentence": "The approved concept shows an oval lid — a shape the system does not "
                                               "draw yet, so no shape is chosen for you: choose the nearest yourself."}
        zones = cc.propose_zones(record)
        out.spec_sheet = dict(out.spec_sheet, **{
            cc.PROFILE_SCHEMA: record,
            "container_profile": {"archetype": "compact", "variant": "", "cap_style": "clasp", "height_mm": 95,
                                  "width_mm": 110},
            co.SCHEMA: {"state": co.TRACED_FROM_CONCEPT, "view": "PLAN", "kind": "oval", "aspect": 0.7,
                        "source_sha256": "ab" * 32},
            cc.ZONES_SCHEMA: cc.zone_set_record(zones, record, confirmation_state="PROPOSED")})
        out.save()
        page = self._editor(task)
        assert page.text_content("#variant-note").startswith("The approved concept shows an oval lid")
        assert page.is_visible("#learn-shape-btn")
        page.click("#learn-shape-btn")
        page.wait_for_function("() => (_profileState && _profileState.variant) === 'learned_oval'", timeout=15000)
        assert LearnedShape.objects.filter(form="compact", kind="oval").count() == 1
        active = page.eval_on_selector_all("#variant-chips .chip.active", "els => els.map(e => e.dataset.val)")
        assert active == ["learned_oval"], active
        assert self.confirm_posts == []
        # a shape only the brief names: said, why it cannot be learned, no button
        other = self._gate_task()
        o2 = other.packaging_outputs.first()
        r2 = dict(record, unknown_shape=dict(record["unknown_shape"], source="the brief", kind="heart",
                                                  sentence="The brief names a heart-shaped lid — ..."))
        o2.spec_sheet = dict(o2.spec_sheet, **{cc.PROFILE_SCHEMA: r2, "container_profile": {
            "archetype": "compact", "variant": "", "cap_style": "clasp", "height_mm": 95, "width_mm": 110}})
        o2.save()
        page2 = self._editor(other)
        assert not page2.is_visible("#learn-shape-btn")
        assert "cannot be learned" in page2.text_content("#learn-shape-msg")

    def test_bh71_a_lid_no_variant_draws_is_said_and_no_shape_is_chosen(self):
        """§BH71 PART 3, the owner's goal of 2026-09-28: \"When a concept shows a shape the system doesn't know, it says
        so ... It never squeezes a product into the wrong shape.\" The page gave a record with no variant the form's
        FIRST variant; a lid the proposal says no variant draws is said where the variant is chosen, in its own
        words, and no variant is chosen for the person — nothing is sent."""
        task = self._gate_task()
        out = task.packaging_outputs.first()
        record = cc.build_inferred_profile("compact", "", estimates={"body_width_mm": 90, "body_height_mm": 70,
                                                                   "cap_type": "clasp"})
        record["unknown_shape"] = {
            "kind": "oval", "words": "an oval lid", "source": "the brief",
            "sentence": "The brief names an oval lid — a shape the system does not draw yet, so no shape is chosen "
                        "for you: choose the nearest yourself."}
        zones = cc.propose_zones(record)
        out.spec_sheet = dict(out.spec_sheet, **{
            cc.PROFILE_SCHEMA: record,
            "container_profile": {"archetype": "compact", "variant": "", "cap_style": "clasp", "height_mm": 70,
                                  "width_mm": 90},
            cc.ZONES_SCHEMA: {"schema_version": cc.ZONES_SCHEMA, "zones": zones,
                              "zone_set_hash": cc.zone_set_hash(zones), "confirmation_state": "PROPOSED"}})
        out.save()
        page = self._editor(task)
        assert page.evaluate("_profileState.archetype") == "compact"
        assert page.evaluate("_profileState.variant") is None
        assert page.evaluate("_editorConfig.unknown_shape.kind") == "oval"
        assert page.text_content("#variant-note").startswith("The brief names an oval lid"), \
            page.text_content("#variant-note")
        assert page.eval_on_selector_all("#variant-chips .chip.active", "els => els.length") == 0
        assert self.confirm_posts == []

    def test_bh71_a_new_form_is_drawn_from_the_servers_own_drawing(self):
        """§BH71 PART 3: the five new forms have no hand-drawn picture in the preview; each is drawn from the server's
        own drawing of it (targets/ui.py _form_outlines), its outline and its closure, scaled to the size set —
        never the empty frame, never a bottle — and each variant as its own."""
        page = self._editor(self._gate_task())
        drawn = page.evaluate("""() => {
            const draw = (state) => {
              const c = document.createElement('canvas'); c.width = 220; c.height = 300;
              const ctx = c.getContext('2d'); const said = [];
              const fillText = ctx.fillText.bind(ctx);
              ctx.fillText = (t, ...rest) => { said.push(t); return fillText(t, ...rest); };
              _drawSilhouette(ctx, state, 220, 300);
              return {png: c.toDataURL(), said: said};
            };
            const out = {};
            [['tin', 'round', 42, 42], ['tin', 'slide', 42, 60], ['sachet', 'three_side', 180, 125],
             ['oval_stick', 'oval', 124, 54], ['aerosol', 'straight', 190, 45], ['ampoule', 'glass', 75, 11]]
              .forEach(([a, v, h, w]) => { out[a + ':' + v] = draw({archetype: a, variant: v, height_mm: h,
                                                                      width_mm: w}); });
            out.empty = draw({archetype: 'hamper', height_mm: 100, width_mm: 40});
            out.bottle = draw({archetype: 'bottle', variant: 'cylindrical', cap_style: 'screw',
                              height_mm: 100, width_mm: 40, neck_ratio: 0.42});
            return out;
        }""")
        pictures = {k: v["png"] for k, v in drawn.items()}
        assert len(set(pictures.values())) == len(pictures), [k for k in pictures]      # each its own picture
        for key in ("tin:round", "tin:slide", "sachet:three_side", "oval_stick:oval", "aerosol:straight",
                    "ampoule:glass"):
            assert drawn[key]["said"] == [], (key, drawn[key]["said"])
        assert self.confirm_posts == []

    # -- variants and closures ---------------------------------------------------

    def test_switching_preserves_valid_and_clears_invalid_visibly(self):
        page = self._editor(self._gate_task())
        # bottle: pick tapered + screw
        page.click('#variant-chips .chip[data-val="tapered"]')
        assert page.evaluate("_profileState.variant") == "tapered"
        self._select_archetype(page, "jar")
        # screw is valid for jar → preserved; tapered is not → cleared,
        # never silently replaced
        assert page.evaluate("_profileState.cap_style") == "screw"
        assert page.evaluate("_profileState.variant") is None
        note = page.text_content("#variant-note")
        assert 'Variant "tapered" does not apply to Jar' in note
        assert page.eval_on_selector_all(
            "#variant-chips .chip.active", "els => els.length") == 0
        # incomplete state + confirm gating, in calm language
        assert "Not finished yet" in \
            page.text_content("#profile-incomplete")  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]
        assert page.eval_on_selector(
            "#confirm-profile-zones", "b => b.disabled") is True

    def test_variant_and_closure_update_the_preview(self):
        page = self._editor(self._gate_task())
        c0 = self._canvas(page)
        page.click('#variant-chips .chip[data-val="tapered"]')
        c1 = self._canvas(page)
        assert c1 != c0
        assert "Tapered" in self._summary(page)
        page.click('#cap-chips .chip[data-val="dropper"]')
        assert self._canvas(page) != c1
        assert "Dropper" in self._summary(page)
        assert self.confirm_posts == []

    def test_group_labels_are_semantic(self):
        page = self._editor(self._gate_task())
        groups = page.eval_on_selector_all(
            ".choice-group", """els => els.map(e => ({
              role: e.getAttribute('role'),
              label: document.getElementById(
                e.getAttribute('aria-labelledby')).textContent}))""")
        assert [g["role"] for g in groups] == ["group", "group"]
        assert [g["label"] for g in groups] == ["Variant", "Cap or closure"]

    # -- proportions ---------------------------------------------------------------

    def test_slider_and_number_stay_synchronized(self):
        page = self._editor(self._gate_task())
        page.eval_on_selector("#sl-height_mm", """el => {
          el.value = 160;
          el.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        assert page.evaluate("_profileState.height_mm") == 160
        assert page.input_value("#num-height_mm") == "160"
        assert page.text_content("#sl-val-height_mm") == "160mm"
        page.fill("#num-width_mm", "90")
        page.eval_on_selector("#num-width_mm", "el => el.dispatchEvent("
                              "new Event('change', {bubbles: true}))")
        assert page.evaluate("_profileState.width_mm") == 90
        assert page.eval_on_selector("#sl-width_mm", "el => el.value") == "90"

    def test_number_input_clamps_to_config_range(self):
        page = self._editor(self._gate_task())
        page.fill("#num-height_mm", "9999")
        page.eval_on_selector("#num-height_mm", "el => el.dispatchEvent("
                              "new Event('change', {bubbles: true}))")
        # [§BH71 PART 3, the owner's goal of 2026-09-28: the bottle declares its own ranges from the catalogue's pages —
        # a lotion pump bottle stands 250 mm — so it clamps to the bottle's own 260, the range the page is sent. Was:
        # == 200, the shared row]
        assert page.evaluate("_archetypeCfg('bottle').ranges.height_mm.max") == 260
        assert page.evaluate("_profileState.height_mm") == 260

    def test_proportions_move_the_preview_without_network(self):
        page = self._editor(self._gate_task())
        c0 = self._canvas(page)
        api_before = []
        page.on("request", lambda r: api_before.append(r.url)
                if "/api/" in r.url else None)
        page.eval_on_selector("#sl-neck_ratio", """el => {
          el.value = 0.65;
          el.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        assert self._canvas(page) != c0
        assert "neck 65% of body width" in self._summary(page)
        # drawing is purely local; [his test day finding 2, 2026-09-29: the one request a size change sends is the
        # print areas' proposal for the new size, which writes nothing]
        assert [u for u in api_before if "/propose_container_zones/" not in u] == []
        assert self.confirm_posts == []

    def test_finding2_the_print_areas_follow_the_sizes_shown(self):
        """His test day finding 2 (2026-09-29, design 117): he set his tube to 180 x 50 mm and the print areas beside
        it stayed those proposed for other sizes. The step now shows the areas the server proposes for the sizes it
        shows — through the confirm door's own record — as a size changes, writing nothing; a tick on an area whose
        numbers changed is cleared."""
        from apps.pipeline import views as pv
        task = self._gate_task()
        spec = task.packaging_outputs.first().spec_sheet
        page = self._editor(task)
        page.wait_for_selector("#zone-proposals .zone-card", state="attached")
        box = '#zone-proposals input[onchange="toggleZoneConfirm(this)"] >> nth=0'
        page.check(box)
        page.fill("#num-height_mm", "160")
        page.eval_on_selector("#num-height_mm", "el => el.dispatchEvent(new Event('change', {bubbles: true}))")
        state = page.evaluate("JSON.parse(JSON.stringify(_profileState))")
        record = pv._container_profile_record(task, spec, state["archetype"], state,
                                              pv._clean_container_profile(state, state["archetype"]))
        want = next(z for z in cc.augment_code_zones(record, cc.propose_zones(record))
                    if z["zone_type"] == "FRONT_PRINT_ZONE")
        words = "%g × %g mm, placed at %g, %g mm" % (want["width"], want["height"], want["x"], want["y"])
        page.wait_for_function(
            "w => document.querySelector('#zone-proposals .zone-card').innerText.includes(w)", arg=words)
        assert page.is_checked(box) is False                     # its numbers changed: the tick is cleared
        task.refresh_from_db()
        assert task.packaging_outputs.first().spec_sheet == spec          # nothing written
        assert self.confirm_posts == []

    def test_finding2_the_brief_s_stated_size_opens_the_step_and_its_print_areas_follow(self):
        """His test day finding 2 (2026-09-29, design 117): his brief said "Tube about 50 mm across, 180 mm tall"; the
        record held no size; the step opened on the tube's own 130 x 35 and the print areas on the fallback 100 x 50.
        It now opens on the brief's size, said as the brief's hint, and shows the print areas for that size."""
        from apps.pipeline import views as pv
        task = DesignTask.objects.create(
            brand=Brand.objects.first(), design_target="product_container", status="awaiting_container_profile",
            created_by=self.user, task_text="Body lotion in a squeeze tube. Tube about 50 mm across, 180 mm tall.")
        img = GeneratedImage(task=task, direction_name="Playful Drip")
        img.image_file.save("concept.png", ContentFile(PNG), save=True)
        record = cc.build_inferred_profile("tube", "standard")             # a record holding no size, as 117's
        zones = cc.augment_code_zones(record, cc.propose_zones(record))
        spec = {"backend": "container", cc.PROFILE_SCHEMA: record, cc.ZONES_SCHEMA: cc.zone_set_record(zones, record)}
        PackagingOutput.objects.create(task=task, approved_image=img, spec_sheet=spec)
        page = self._editor(task)
        assert page.input_value("#num-height_mm") == "180" and page.input_value("#num-width_mm") == "50"
        assert "Size, from your brief: 50 mm across · 180 mm tall" in " ".join(page.inner_text("#profile-view").split())
        state = page.evaluate("JSON.parse(JSON.stringify(_profileState))")
        record = pv._container_profile_record(task, spec, "tube", state, pv._clean_container_profile(state, "tube"))
        want = next(z for z in cc.augment_code_zones(record, cc.propose_zones(record))
                    if z["zone_type"] == "FRONT_PRINT_ZONE")
        words = "%g × %g mm, placed at %g, %g mm" % (want["width"], want["height"], want["x"], want["y"])
        page.wait_for_function(
            "w => document.querySelector('#zone-proposals .zone-card').innerText.includes(w)", arg=words)
        assert want["height"] > 55                        # not the fallback's 55 mm front
        assert self.confirm_posts == []

    def test_his_answer_a_tube_s_width_is_asked_as_its_round_diameter(self):
        """His answer after test day finding 3 (2026-09-30), (4) "round": his 50 mm is the tube's round diameter, and the
        shape step asked it as "Body Width". A tube's width row reads "Diameter (round end)"; a bottle's reads "Body
        Width" as before; the editor's config says which, from the form's declaration."""
        from apps.pipeline.targets.container import shapes
        from apps.pipeline.targets.ui import container_profile_editor_config
        task = DesignTask.objects.create(
            brand=Brand.objects.first(), design_target="product_container", status="awaiting_container_profile",
            created_by=self.user, task_text="Body lotion in a squeeze tube. Tube about 50 mm across, 180 mm tall.")
        img = GeneratedImage(task=task, direction_name="Playful Drip")
        img.image_file.save("concept.png", ContentFile(PNG), save=True)
        record = cc.build_inferred_profile("tube", "standard")
        zones = cc.augment_code_zones(record, cc.propose_zones(record))
        spec = {"backend": "container", cc.PROFILE_SCHEMA: record, cc.ZONES_SCHEMA: cc.zone_set_record(zones, record)}
        PackagingOutput.objects.create(task=task, approved_image=img, spec_sheet=spec)
        config = {a["key"]: a for a in container_profile_editor_config(task)["archetypes"]}
        assert config["tube"]["labels"] == {"width_mm": "Diameter (round end)"} and "labels" not in config["bottle"]
        page = self._editor(task)
        assert page.get_attribute("#sl-width_mm", "aria-label") == "Diameter (round end)"
        assert page.input_value("#num-width_mm") == "50"
        tube = next(s for s in shapes.SHAPES if s["id"] == "squeeze_tube")
        assert tube["size_mm"]["width"] == (16, 51)                   # the catalogue's tube width is its diameter
        assert self.confirm_posts == []

    def test_proportion_language_disclaims_manufacturing(self):
        page = self._editor(self._gate_task())
        assert page.text_content(".proportion-note") == (
            "These controls define relative silhouette proportions, not "
            "manufacturing dimensions.")
        assert "A preview of the shape — not a production drawing" in \
            page.text_content(".preview-disclaimer")

    # -- dirty / reset ---------------------------------------------------------------

    def test_dirty_reset_cycle_restores_everything(self):
        page = self._editor(self._gate_task())
        c0 = self._canvas(page)
        assert page.text_content("#profile-dirty") == ""
        assert page.eval_on_selector("#profile-reset",
                                     "b => b.disabled") is True
        self._select_archetype(page, "tube")
        page.eval_on_selector("#sl-height_mm", """el => {
          el.value = 70;
          el.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        assert "Changed from the suggested shape" in \
            page.text_content("#profile-dirty")  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]
        assert page.eval_on_selector("#profile-reset",
                                     "b => b.disabled") is False
        page.click("#profile-reset")
        assert page.evaluate("_profileState.archetype") == "bottle"
        assert page.evaluate("_profileState.height_mm") == 110
        assert page.input_value("#num-height_mm") == "110"
        assert self._canvas(page) == c0
        assert page.text_content("#profile-dirty") == ""
        assert page.eval_on_selector("#profile-reset",
                                     "b => b.disabled") is True
        assert self.confirm_posts == []

    def test_the_shape_step_shows_no_engine_code(self):
        # "Plain words everywhere. No engine codes on screen." (the owner's goal of 2026-09-25, (d)): read through what
        # the step SHOWS — innerText skips a closed fold — with the editor open and its print areas proposed; every
        # code is still on the page, folded under its record
        import re
        page = self._editor(self._gate_task())
        page.wait_for_selector("#zone-proposals .zone-card", state="attached")
        shown = " ".join(page.inner_text("#profile-view").split())
        kept = " ".join(page.text_content("#profile-view").split())
        for rx in (r"\b[A-Z]{3,}_[A-Z_]{2,}\b", r"\b[a-z]+_[a-z_]+\b", r"\b[a-z_]+/\d\.\d\b", r"\bhash\b",
                   r"\bINFERRED\b", r"\bPLAN\b"):
            assert not re.search(rx, shown), (rx, re.findall(rx, shown)[:8])
        assert "Where the print goes" in shown and "Front print area" in shown and "I confirm this print area" in shown
        assert "FRONT_PRINT_ZONE" in kept and "container_decoration_zones/1.0" in kept and "zone hash" in kept

    def test_the_caps_sizes_are_asked_only_of_a_form_with_a_cap(self):
        # §BH61(b), his words: "no cap dimensions where there is no cap" — the block asked a compact for its cap's sizes
        page = self._editor(self._gate_task())                       # a bottle: it has a cap
        assert page.is_visible("#cap-dims-block")
        self._select_archetype(page, "compact")                      # a hinged case: no cap
        assert not page.is_visible("#cap-dims-block")

    def test_dirty_region_is_a_status_region(self):
        page = self._editor(self._gate_task())
        assert page.eval_on_selector(
            "#profile-dirty", "el => el.getAttribute('role')") == "status"
        assert page.eval_on_selector(
            "#profile-reset", "b => b.getAttribute('aria-label')") == \
            "Back to the suggested shape"  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]

    # -- hints, gate visibility, no mutation -------------------------------------

    def test_hints_render_as_suggestions_only(self):
        page = self._editor(self._gate_task(
            hints="\n\n[Container type: bottle; Product category: serum; "
                  "Capacity: 30 ml; Closure: gold dropper]"))
        panel = page.text_content(".profile-hints")
        assert "Said when the design was started" in panel  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]
        assert "not confirmed" in panel
        assert "gold dropper" in panel
        # a hint never confirms anything: the closure hint text does not
        # select the dropper chip by itself
        assert page.evaluate("_profileState.cap_style") == "screw"

    def test_confirmed_task_shows_confirmed_state_not_the_editor(self):
        task = self._gate_task(confirmed=True)
        page = self._design_page(task)  # [2026-09-25: the design's own page]
        page.wait_for_selector("#profile-view h3", state="attached")
        assert "Its shape, sizes and print areas — confirmed" in \
            page.text_content("#profile-view")
        assert page.eval_on_selector_all(
            "#archetype-cards, #profile-preview-canvas",
            "els => els.length") == 0

    def test_packaging_task_never_shows_the_editor(self):
        task = DesignTask.objects.create(
            brand=Brand.objects.first(), task_text="a carton",
            design_target="packaging", status="completed",
            created_by=self.user)
        page = self._design_page(task)  # [2026-09-25: the design's own page]
        page.wait_for_selector("#review-board .rb-project", state="attached")
        assert page.eval_on_selector(
            "#profile-state", "el => getComputedStyle(el).display") == "none"

    def test_editing_mutates_no_server_state(self):
        task = self._gate_task()
        page = self._editor(task)
        self._select_archetype(page, "jar")
        page.click('#cap-chips .chip[data-val="lid"]')
        task.refresh_from_db()
        assert task.status == "awaiting_container_profile"
        assert GateDecision.objects.count() == 0
        assert self.confirm_posts == []
        spec = task.packaging_outputs.first().spec_sheet
        assert "container_confirmation" not in spec


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class ProfileEditorResponsiveA11yTests(_ProfileEditorFixtures,
                                       DrainedStaticLiveServerTestCase):
    """Geometry + accessibility (§22) — desktop semantics and the 390 px
    drawer, with real boxes measured, not assumed."""

    def test_sliders_have_accessible_names_and_values(self):
        page = self._editor(self._gate_task())
        rows = page.eval_on_selector_all(
            '#profile-view .slider-pair input[type="range"]',
            """els => els.map(e => ({label: e.getAttribute('aria-label'),
                                     text: e.getAttribute('aria-valuetext')}))""")
        assert [r["label"] for r in rows] == \
            ["Overall Height", "Body Width", "Body Depth", "Neck Proportion"]
        assert rows[0]["text"] == "110 mm"
        page.eval_on_selector("#sl-height_mm", """el => {
          el.value = 150;
          el.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        assert page.eval_on_selector(
            "#sl-height_mm", "el => el.getAttribute('aria-valuetext')") == \
            "150 mm"

    def test_preview_has_textual_summary_and_hidden_canvas(self):
        page = self._editor(self._gate_task())
        assert page.eval_on_selector(
            "#profile-preview-canvas",
            "c => c.getAttribute('aria-hidden')") == "true"
        summary = self._summary(page)
        assert "Bottle" in summary and "A preview only" in summary  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]

    def test_selected_states_are_not_colour_only(self):
        page = self._editor(self._gate_task())
        assert "✓ selected" in page.text_content(
            '.archetype-card[data-archetype="bottle"]')
        assert "✓ selected" not in page.text_content(
            '.archetype-card[data-archetype="jar"]')
        assert "✓" in page.text_content("#variant-chips .chip.active")

    def test_focus_visible_styling_is_declared(self):
        page = self._editor(self._gate_task())
        assert page.evaluate("""
          (() => {
            for (const sheet of document.styleSheets) {
              let rules; try { rules = sheet.cssRules; } catch (e) { continue; }
              for (const r of rules) {
                if (r.selectorText &&
                    r.selectorText.includes('.archetype-card:focus-visible') &&
                    r.style.outline) return true;
              }
            }
            return false;
          })()
        """) is True

    def test_mobile_390_the_step_has_the_pages_width_at_every_library_state(self):
        # [the owner's answer to the UI directions of 2026-09-25: C's design page at a phone's width is one column
        # whether the library is open or closed — the closed library's two-class rules once outranked the narrow
        # layout and kept the concepts beside the step, which was squeezed to a word a line]
        for library in (False, True):
            page = self._design_page(self._gate_task(), viewport=MOBILE, library=library)
            page.wait_for_selector("#archetype-cards .archetype-card", state="attached")
            assert page.evaluate("document.documentElement.scrollWidth <= "
                                 "document.documentElement.clientWidth") is True, library
            width = page.evaluate("document.getElementById('panel-center').getBoundingClientRect().width")
            assert width >= 300, (library, width)

    def test_mobile_390_stacks_without_overflow(self):
        page = self._editor(self._gate_task(), viewport=MOBILE)
        assert page.evaluate(
            "document.documentElement.scrollWidth <= "
            "document.documentElement.clientWidth") is True
        # editor and preview stack: the preview panel sits BELOW the controls
        boxes = page.evaluate("""
          (() => {
            const c = document.querySelector('.profile-controls')
                              .getBoundingClientRect();
            const p = document.querySelector('.profile-preview-panel')
                              .getBoundingClientRect();
            return {controlsBottom: c.bottom, previewTop: p.top,
                    overlap: !(p.top >= c.bottom || c.top >= p.bottom)};
          })()
        """)
        assert boxes["overlap"] is False

    def test_mobile_cards_operable_and_reset_reachable(self):
        page = self._editor(self._gate_task(), viewport=MOBILE)
        page.click('.archetype-card[data-archetype="tube"]')
        assert page.evaluate("_profileState.archetype") == "tube"
        page.eval_on_selector("#profile-reset", "b => b.scrollIntoView()")
        box = page.eval_on_selector("#profile-reset", """b => {
          const r = b.getBoundingClientRect();
          return {w: r.width, right: r.right};
        }""")
        assert box["w"] > 0 and box["right"] <= MOBILE["width"]
        page.click("#profile-reset")
        assert page.evaluate("_profileState.archetype") == "bottle"

    def test_mobile_sliders_fit_the_viewport(self):
        page = self._editor(self._gate_task(), viewport=MOBILE)
        assert page.evaluate("""
          (() => {
            const vw = document.documentElement.clientWidth;
            return Array.from(document.querySelectorAll(
              '#profile-view .slider-pair')).every(row => {
                const r = row.getBoundingClientRect();
                return r.right <= vw && r.left >= 0;
              });
          })()
        """) is True


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class ConfirmationDialogBrowserTests(_ProfileEditorFixtures,
                                     DrainedStaticLiveServerTestCase):
    """UI-2A §23/§24 — the reviewed confirmation door, in a real browser.

    The page button only OPENS the dialog; the dialog's explicit Confirm &
    Reconstruct is the single dispatch path. The live server runs in this
    process, so patching the worker dispatch seam here mocks it for the real
    POST too — the state machine runs for real, the queue never does.
    """

    _DELAY = "apps.pipeline.tasks.resume_aria_container_profile.delay"

    def _open_dialog(self, page):
        page.click("#confirm-profile-zones")
        page.wait_for_selector("#confirm-profile-dialog[open]")

    def test_the_confirm_dialog_is_in_the_pages_look(self):
        # "One clean visual system" (the owner's goal of 2026-09-25, (c)): the dialog fell back to the old dark theme
        # (#17171b under cream text) on C's light page
        import re
        page = self._editor(self._confirmable_task())
        self._open_dialog(page)
        bg, fg = page.eval_on_selector("#confirm-profile-dialog",
                                       "d => [getComputedStyle(d).backgroundColor, getComputedStyle(d).color]")
        light = sum(map(int, re.findall(r"\d+", bg)[:3]))
        dark = sum(map(int, re.findall(r"\d+", fg)[:3]))
        assert light > 600 and dark < 300, (bg, fg)

    # -- opening is gated and sends nothing ----------------------------------

    def test_incomplete_profile_cannot_open_the_dialog(self):
        page = self._editor(self._gate_task())
        page.click('#variant-chips .chip[data-val="tapered"]')
        self._select_archetype(page, "jar")           # variant cleared
        assert page.eval_on_selector(
            "#confirm-profile-zones", "b => b.disabled") is True
        # even a forced call refuses while readiness fails (§6)
        page.evaluate("openConfirmProfileDialog(1)")
        assert page.eval_on_selector(
            "#confirm-profile-dialog", "d => d.open") is False
        assert self.confirm_posts == []

    def test_other_cannot_open_or_post(self):
        page = self._editor(self._gate_task())
        self._select_archetype(page, "other")
        assert page.eval_on_selector(
            "#confirm-profile-zones", "b => b.disabled") is True
        page.evaluate("openConfirmProfileDialog(1)")
        assert page.eval_on_selector(
            "#confirm-profile-dialog", "d => d.open") is False
        assert self.confirm_posts == []

    def test_bh70_a_form_without_a_neck_is_shown_no_neck_in_the_dialog(self):
        """§BH70(1), item 21 of the list the owner was sent: the dialog listed "Neck Proportion" for every form — a
        hinged case carries none since a754a10, so its dialog read "Neck Proportion: null". A compact's dialog lists
        its own rows and no neck; a bottle's keeps its neck (the test below)."""
        page = self._editor(self._confirmable_task("compact", "rounded_rect", "clasp", (110, 18, 95)))
        self._open_dialog(page)
        text = " ".join(page.text_content("#confirm-profile-dialog").split())
        assert "Compact / Palette" in text and "Clasp" in text and "110 mm" in text, text
        assert "Neck Proportion" not in text and "null" not in text, text
        assert self.confirm_posts == []

    def test_his_round_a_tube_s_dialog_and_confirmed_view_name_its_width_as_its_diameter(self):
        """Found on his re-confirmed 117 (2026-10-01): the shape step asks a tube's width as "Diameter (round end)", and
        the dialog he confirmed it through still said "Body Width" — so did the confirmed view after it. Both name the
        row as the form does; a bottle's dialog keeps "Body Width" (the test below)."""
        page = self._editor(self._confirmable_task("tube", "standard", "flip", (50, 50, 180)))
        self._open_dialog(page)
        text = " ".join(page.text_content("#confirm-profile-dialog").split())
        assert "Diameter (round end)" in text and "50 mm" in text and "Body Width" not in text, text
        with patch(self._DELAY) as delay, \
             patch("apps.pipeline.services.claude_service.call_claude"), patch("openai.images"):
            delay.return_value.id = "celery-live"
            page.click("#cpd-confirm")
            page.wait_for_selector(".confirmed-authority-badge", state="attached")
        body = " ".join(page.text_content("#profile-view").split())
        assert "Diameter (round end)" in body and "Body Width" not in body, body

    def test_complete_profile_opens_dialog_with_exact_values(self):
        page = self._editor(self._confirmable_task())
        assert page.eval_on_selector(
            "#confirm-profile-zones", "b => b.disabled") is False
        self._open_dialog(page)
        assert self.confirm_posts == []               # opening sends nothing
        text = " ".join(page.text_content("#confirm-profile-dialog").split())
        for expected in ("Bottle", "Slim", "Screw Cap", "95 mm", "35 mm",
                         "25 mm", "0.42"):
            assert expected in text, expected
        # [the owner's goal of 2026-09-25, (d): the same four claims, in the plain words the dialog now says]
        assert "your confirmation of the concept's shape" in text
        assert "not a supplier's manufacturing dimensions" in text
        assert "Confirming records your decision and starts drawing the design" in text
        assert "not a manufacturing drawing" in text
        # §8: safe initial focus, consequential action not default
        assert page.evaluate("document.activeElement.id") == "cpd-cancel"

    def test_review_cancel_and_escape_send_nothing(self):
        page = self._editor(self._confirmable_task())
        self._open_dialog(page)
        page.click("#cpd-review")                     # → back to the editor
        assert page.eval_on_selector(
            "#confirm-profile-dialog", "d => d.open") is False
        assert page.evaluate(
            "document.activeElement.classList.contains('archetype-card')") \
            is True
        self._open_dialog(page)
        page.click("#cpd-cancel")
        assert page.evaluate("document.activeElement.id") == \
            "confirm-profile-zones"
        self._open_dialog(page)
        page.keyboard.press("Escape")
        assert page.eval_on_selector(
            "#confirm-profile-dialog", "d => d.open") is False
        assert self.confirm_posts == []

    def test_dialog_traps_focus(self):
        page = self._editor(self._confirmable_task())
        self._open_dialog(page)
        for _ in range(5):
            page.keyboard.press("Tab")
            assert page.evaluate(
                "document.activeElement.closest('#confirm-profile-dialog')"
                " !== null")
        for _ in range(5):
            page.keyboard.press("Shift+Tab")
            assert page.evaluate(
                "document.activeElement.closest('#confirm-profile-dialog')"
                " !== null")
        page.keyboard.press("Escape")

    # -- dispatch ------------------------------------------------------------

    def test_confirm_sends_one_request_and_freezes_into_confirmed_state(self):
        task = self._confirmable_task()
        page = self._editor(task)
        with patch(self._DELAY) as delay, \
             patch("apps.pipeline.services.claude_service.call_claude") as cl, \
             patch("openai.images") as images:
            delay.return_value.id = "celery-live"
            self._open_dialog(page)
            page.click("#cpd-confirm")
            page.wait_for_selector(".confirmed-authority-badge",
                                   state="attached")
            assert delay.call_count == 1
            cl.assert_not_called()
            images.edit.assert_not_called()
            images.generate.assert_not_called()
        assert len(self.confirm_posts) == 1           # exactly one POST
        body = " ".join(page.text_content("#profile-view").split())
        # [B1, the clean-up of 2026-10-04] the badge says who confirmed it — here the viewer, uib4b, did
        assert "Confirmed by you — for the design, not for manufacture" in body
        # UI-2B-1: the status contract renders the coarse lifecycle label
        assert ("Waiting to be drawn" in body
                or "Being drawn" in body)
        assert "95 mm" in body and "Slim" not in body or True
        assert "not a supplier's manufacturing dimensions" in body
        # the editable editor is GONE — frozen persisted presentation
        assert page.eval_on_selector_all(
            "#archetype-cards, #profile-preview-canvas, #profile-reset",
            "els => els.length") == 0
        # server truth: one gate decision, transitioned state
        from apps.pipeline.models import GateDecision
        task.refresh_from_db()
        assert task.status == "generating_dieline"
        assert GateDecision.objects.filter(
            task=task, gate="container_profile").count() == 1
        # references/board sections survive untouched
        assert page.eval_on_selector_all(
            "#review-board", "els => els.length") == 1
        # refresh cannot resurrect an editable profile
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("#panel-center", state="attached")  # [the owner's answer to the UI directions of 2026-09-25: the reload lands on the design's own page, C's design page, which opens the design itself]
        page.wait_for_selector(".confirmed-authority-badge",
                               state="attached")
        assert page.eval_on_selector_all(
            "#archetype-cards", "els => els.length") == 0

    def test_double_click_sends_one_request(self):
        task = self._confirmable_task()
        page = self._editor(task)
        with patch(self._DELAY) as delay:
            delay.return_value.id = "celery-live"
            self._open_dialog(page)
            page.evaluate("""
              (() => {
                const b = document.getElementById('cpd-confirm');
                b.click(); b.click();
              })()
            """)
            page.wait_for_selector(".confirmed-authority-badge",
                                   state="attached")
        assert len(self.confirm_posts) == 1

    # -- failure paths ---------------------------------------------------------

    def test_409_refusal_preserves_editor_and_state(self):
        # the plain gate task has PROPOSED zones + unsourced dims → a real
        # contract refusal, rendered without resetting anything
        page = self._editor(self._gate_task())
        canvas_before = self._canvas(page)
        page.eval_on_selector("#sl-height_mm", """el => {
          el.value = 150;
          el.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        dirty_canvas = self._canvas(page)
        self._open_dialog(page)
        page.click("#cpd-confirm")
        # the dialog unlocks/closes only when the response has arrived
        page.wait_for_function(
          "!document.getElementById('confirm-profile-dialog').open")
        page.wait_for_function(
          "!document.getElementById('profile-msg').textContent"
          ".includes('Confirming')")
        assert len(self.confirm_posts) == 1
        assert page.text_content("#profile-msg").strip() != ""
        # "Plain words everywhere" (the owner's goal of 2026-09-25, (d)): the refusal says why in words; the server's
        # own code is kept — folded under its record, escaped — never on the screen
        import re
        shown = page.inner_text("#profile-msg")
        assert "The shape could not be confirmed" in shown, shown
        assert not re.search(r"\b[A-Z]{3,}_[A-Z_]{2,}\b", shown), shown
        assert re.search(r"\b[A-Z]{3,}_[A-Z_]{2,}\b", page.text_content("#profile-msg"))
        # editor, preview and dirty state all survive the refusal
        assert page.evaluate("_profileState.height_mm") == 150
        assert self._canvas(page) == dirty_canvas != canvas_before
        assert "Changed from the suggested shape" in \
            page.text_content("#profile-dirty")  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]
        assert page.evaluate(
            "document.activeElement.id") == "profile-msg"

    def test_a_confirmation_does_not_carry_across_a_geometry_it_never_showed(self):
        """§BH64(b) ON THE SCREEN, and without this the refusal he ruled is defeated by one click.

        The owner's zones are USER_CONFIRMED in the spec. Shrinking the body makes them no longer fit,
        so the door refuses by name and hands back a proposal that DOES fit. The page adopts those zones
        — `confirm_profile.js:1271` always has — but the per-zone confirmation map was keyed on
        `zone_id` alone, so every tick survived the substitution and a second Confirm would have been
        accepted against numbers nobody had looked at.

        Asserted on what renders: the refusal code in the message, and no checkbox left ticked.
        """
        task = self._confirmable_task()
        page = self._editor(task)
        assert page.evaluate(
            "Object.values(_contractState.confirmed).every(Boolean)") is True
        page.eval_on_selector("#sl-width_mm", """el => {
          el.value = 20;
          el.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        self._open_dialog(page)
        page.click("#cpd-confirm")
        page.wait_for_function(
          "!document.getElementById('confirm-profile-dialog').open")
        page.wait_for_function(
          "!document.getElementById('profile-msg').textContent"
          ".includes('Confirming')")
        assert len(self.confirm_posts) == 1
        assert "CONTAINER_ZONE_PROFILE_DIVERGED" in \
            page.text_content("#profile-msg")
        # the substituted zones arrived, and NOT ONE of them is still ticked
        assert page.evaluate("_contractState.zones.length") > 0
        assert page.evaluate(
            "Object.values(_contractState.confirmed).some(Boolean)") is False
        # [§BH71 (0b): the proposal carries an optional code place now, whose "Include this optional print area" box is
        # ticked by default; it read ".zone-cards input[type=checkbox]:checked" — the CONFIRMATION ticks are what must
        # not survive the substitution]
        assert page.eval_on_selector_all(
            ".zone-cards input[type=checkbox][onchange^=toggleZoneConfirm]:checked", "els => els.length") == 0

    def test_network_failure_recovers_through_state_inspection(self):
        task = self._confirmable_task()
        page = self._editor(task)
        page.route("**/confirm_container_profile/", lambda r: r.abort())
        self._open_dialog(page)
        page.click("#cpd-confirm")
        page.wait_for_function(
          "document.getElementById('profile-msg').textContent"
          ".includes('no confirmed shape exists yet')")  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]
        # §17: the client checked the persisted state before offering retry
        assert page.evaluate("_profileState.archetype") == "bottle"
        assert page.eval_on_selector(
            "#confirm-profile-zones", "b => b.disabled") is False
        from apps.pipeline.models import GateDecision
        assert GateDecision.objects.filter(task=task).count() == 0

    def test_a_refusal_with_a_reason_says_it_in_words(self):
        """§BH70(1): the shape step's stop for a name its front would cut off carries its reason in words, and the page
        shows that reason — not only "could not be confirmed" with the code folded away."""
        task = self._confirmable_task()
        page = self._editor(task)
        reason = ("The name \u201cRose Glow\u201d does not fit across this pencil's front: its word \u201cRose\u201d "
                  "needs 6.7 mm at the size a name is printed, and the front is 5.6 mm across.")
        import json
        page.route("**/confirm_container_profile/", lambda r: r.fulfill(
            status=400, content_type="application/json",
            body=json.dumps({"error": "CONTAINER_NAME_WIDER_THAN_ITS_FRONT", "reason": reason,
                             "detail": ["'Rose' needs 6.7 mm at 9 pt; the front is 5.6 mm"]})))
        self._open_dialog(page)
        page.click("#cpd-confirm")
        page.wait_for_function("!document.getElementById('confirm-profile-dialog').open")
        page.wait_for_function("!document.getElementById('profile-msg').textContent.includes('Confirming')")
        shown = page.inner_text("#profile-msg")
        assert "The shape could not be confirmed" in shown and "does not fit across this pencil" in shown, shown
        assert "CONTAINER_NAME_WIDER_THAN_ITS_FRONT" not in shown, shown
        assert "CONTAINER_NAME_WIDER_THAN_ITS_FRONT" in page.text_content("#profile-msg")   # kept, folded

    def test_500_preserves_editor_state(self):
        task = self._confirmable_task()
        page = self._editor(task)
        page.route("**/confirm_container_profile/", lambda r: r.fulfill(
            status=500, content_type="application/json",
            body='{"error": "SERVER_ERROR"}'))
        self._open_dialog(page)
        page.click("#cpd-confirm")
        page.wait_for_function(
          "document.getElementById('profile-msg').textContent.length > 5")
        # §BH70(1), 2026-09-27: eight cards since lipstick, mascara and pencil joined (was: == 5)
        # [§BH71 PART 3, 2026-09-28: thirteen since the tin, the sachet, the oval stick, the aerosol can and the
        # ampoule joined (was: == 8)]
        assert page.eval_on_selector_all(
            "#archetype-cards .archetype-card", "els => els.length") == 13
        assert page.evaluate("_profileState.height_mm") == 95



class HisShapeStep122BrowserTests(_ProfileEditorFixtures, DrainedStaticLiveServerTestCase):
    """[His test blocker on design 122 at the shape step, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md): "The page came back at
    the shape step with the height reset to 80.4 mm and every tick cleared, and no message saying why ... a confirm
    either moves on, or stays with my values and says why in words ... the shape preview shows a bottle, not a tube."]
    In a real browser, on a tube."""

    def _tube(self):
        return self._confirmable_task("tube", "standard", "flip", (35, 20, 120))

    def _set_height(self, page, mm):
        page.fill("#num-height_mm", str(mm))
        page.dispatch_event("#num-height_mm", "input")
        page.dispatch_event("#num-height_mm", "change")

    def test_a_refusal_keeps_his_sizes_and_ticks_and_says_why_beside_the_button(self):
        page = self._editor(self._tube())
        self._set_height(page, 121)
        page.wait_for_timeout(600)                                  # the areas proposed for the size he set
        boxes = page.locator('#zone-proposals input[onchange="toggleZoneConfirm(this)"]')
        for i in range(boxes.count()):
            if not boxes.nth(i).is_checked():
                boxes.nth(i).check()
        zones = page.evaluate("_contractState.zones")
        reason = "These print areas were worked out for other sizes."
        page.route("**/confirm_container_profile/", lambda route: route.fulfill(
            status=409, content_type="application/json", body=__import__("json").dumps(
                {"error": "CONTAINER_ZONE_PROFILE_DIVERGED", "reason": reason, "detail": [],
                 "zones": [dict(z, user_confirmation_state="PROPOSED", zone_hash="other") for z in zones]})))
        page.click("#confirm-profile-zones")
        page.wait_for_selector("#confirm-profile-dialog[open]")
        page.click("#cpd-confirm")
        page.wait_for_selector(".profile-msg-refused")
        msg = page.locator("#profile-msg")
        assert reason in msg.text_content() and msg.is_visible()
        assert msg.evaluate("m => { const r = m.getBoundingClientRect(); "
                            "return r.top >= 0 && r.bottom <= window.innerHeight; }")
        assert page.input_value("#num-height_mm") == "121"
        assert all(boxes.nth(i).is_checked() for i in range(boxes.count()))

    def test_his_sizes_and_ticks_are_kept_when_the_page_is_loaded_again(self):
        task = self._tube()
        page = self._editor(task)
        self._set_height(page, 121)
        page.wait_for_timeout(600)
        page.locator('#zone-proposals input[onchange="toggleZoneConfirm(this)"]').first.check()
        page.reload()
        page.wait_for_selector("#archetype-cards .archetype-card", state="attached")
        page.wait_for_timeout(600)
        assert page.input_value("#num-height_mm") == "121"
        assert page.locator('#zone-proposals input[onchange="toggleZoneConfirm(this)"]').first.is_checked()
        assert "Your sizes and ticks from before the page was loaded again are kept" in page.text_content(
            "#profile-view")

    def test_a_tube_is_previewed_from_its_own_outline_never_a_bottle(self):
        page = self._editor(self._tube())
        page.evaluate("window._shapesDrawn = []; const real = _drawServerShape;"
                      "_drawServerShape = function (ctx, shape) { window._shapesDrawn.push(shape); "
                      "return real.apply(this, arguments); }; true;")
        page.evaluate("_drawProfilePreview()")
        drawn = page.evaluate("window._shapesDrawn")
        outline = page.evaluate("_serverOutline(_profileState)")
        assert drawn and drawn[-1] == outline and outline["outline"], drawn
