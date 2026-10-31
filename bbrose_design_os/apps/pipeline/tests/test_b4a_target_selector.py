"""B4a — design target selector and creation form.

The backend already accepted ``design_target``; what was missing was a way for
a user to choose one honestly. The chips were hardcoded in the template and had
drifted from the target list: two of the targets were absent entirely and three
carried abbreviated labels. So the selector is now data, and these tests read
that data and the rendered page and require them to agree.

The other half is what creation must NOT do: no dimensions demanded, no hint
promoted to a specification, no task created before submit, and no regression
in Packaging.
"""
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from apps.core.models import Brand
from apps.pipeline.models import DesignTask
from apps.pipeline.targets import ui
from apps.pipeline.targets.base import DesignTarget

# §BH55 PHASE 1 (2026-09-19): Complete Product ships — four active, five coming soon until Phase 2
# §BH55 PHASE 2 (2026-09-19): Marketing Material ships — five active, four coming soon
# §BH55 PHASE 2 (2026-09-19): Social Media ships — six active, three coming soon
# §BH55 PHASE 2 (2026-09-19): Exhibition Booth ships — seven active, two coming soon
# §BH55 PHASE 2 (2026-09-19): Display Stand ships — eight active, one coming soon
# §BH55 PHASE 2 (2026-09-19): Gift Set ships — nine active, none coming soon
# §BH55 PHASE 2 (2026-09-19): Palette is NAMED with what it needs — eight active; the one not active is not "coming
# soon" either: its card says what it needs
# §BH70(2) (2026-09-27): Palette starts — "Palette must be startable from New design … It does not refuse me at the
# door." — as a Product Container of the Compact / Palette form: nine active, none waiting
ACTIVE = ["Product", "Display", "Carton", "Palette", "Complete Product", "Gift Set",
          "Marketing Material", "Booth graphics", "Social Media"]
COMING = []


@pytest.fixture
def brand(db):
    return Brand.objects.create(name="BBROSE")


@pytest.fixture
def user(django_user_model):
    from apps.pipeline.permissions import ROLE_DESIGNER
    u = django_user_model.objects.create_user("b4a", password="x",
                                              is_staff=True)
    group, _ = Group.objects.get_or_create(name=ROLE_DESIGNER)
    u.groups.add(group)
    return u


@pytest.fixture
def page(client, user, brand):
    client.force_login(user)
    return client.get(reverse("dashboard:new_classic")).content.decode()


class TestTheNineTargetsAreAllPresent:

    def test_every_design_target_has_a_card(self):
        assert {c["value"] for c in ui.TARGET_CARDS} == set(
            DesignTarget.values)
        assert len(ui.TARGET_CARDS) == 9

    def test_the_active_and_the_coming_soon_cards_are_exactly_these(self):   # §BH55: renamed as Phase 2 ships
        assert [c["name"] for c in ui.TARGET_CARDS if c["active"]] == ACTIVE
        assert [c["name"] for c in ui.TARGET_CARDS
                if not c["active"]] == COMING

    def test_every_card_carries_name_description_status_and_icon(self):
        for c in ui.TARGET_CARDS:
            assert c["name"] and c["description"] and c["status"] and c["icon"]
            assert c["description"].endswith("."), c["name"]

    def test_the_two_required_descriptions_are_exact(self):
        # [§BH70(1), his words: "The card copy says 'any cosmetic product'." It was the B4a brief's "Design the physical
        # bottle, jar or tube before packaging."]
        # [re-pinned: his last goal before the pitch, 2026-10-16, Step 1 (5): "card descriptions in one plain line each, no jargon"]
        assert ui.card_for("product_container")["description"].startswith(
            "Any cosmetic product itself — a lipstick, compact, palette, mascara, pencil, tube, jar or bottle")
        assert ui.card_for("packaging")["description"] == "The box or carton around a product."

    def test_full_names_not_abbreviations(self):
        """The template used to say Display, Marketing and Social."""
        names = [c["name"] for c in ui.TARGET_CARDS]
        for full in ("Display", "Marketing Material", "Social Media",
                     "Booth graphics"):
            assert full in names, full


class TestTheSelectorRenders:

    def test_all_nine_appear_on_the_page(self, page):
        for name in ACTIVE + COMING:
            assert name in page, name

    def test_disabled_targets_are_rendered_disabled(self, page):
        import re
        for c in ui.TARGET_CARDS:
            m = re.search(
                r'data-target="%s"(.*?)</button>' % c["value"], page,
                re.S)
            assert m, c["value"]
            chunk = m.group(1)
            if c["active"]:
                assert "disabled" not in chunk, c["name"]
            else:
                assert "disabled" in chunk, c["name"]
                assert 'aria-disabled="true"' in chunk, c["name"]

    def test_descriptions_and_statuses_are_visible_not_just_tooltips(self,
                                                                    page):
        # [re-pinned: Step 1 (5), "card descriptions in one plain line each"] how a card's design is finished is said
        # in its title, never a second line under the description
        assert "chip-desc" in page and "chip-status" not in page
        # [§BH70(1): the description says "the maker's printing specification", and the page escapes its apostrophe]
        from django.utils.html import escape
        assert escape(ui.card_for("product_container")["description"]) in page
        # §BH55 Phase 2: no card reads "Coming soon" now — every card's OWN status is what must be visible
        for c in ui.TARGET_CARDS:
            assert c["status"] in page, c["name"]

    def test_a_target_that_needs_something_is_named_not_greyed(self, page):
        # §BH55 Phase 2: "named with what it needs, not left grey" — the card's class says so, and the sheet reads
        # it at full contrast
        import pathlib
        import re
        for c in ui.TARGET_CARDS:
            if c.get("needs"):
                assert re.search(r'class="target-chip[^"]* needs[^"]*"[^>]*data-target="%s"' % c["value"], page), c["name"]
                assert c["description"] in page and c["status"] in page
        css = (pathlib.Path(__file__).resolve().parents[3] / "static/css/bbrose.css").read_text()
        assert "#target-selector .target-chip.needs[disabled] { opacity: 1;" in css

    def test_no_target_is_selected_by_default(self, page):
        # [re-pinned: his last goal before the pitch, 2026-10-16, Step 1 (5): "New design: nothing pre-selected"] it
        # read test_exactly_one_target_is_selected_by_default — Start asks for one (poll.js submitTask)
        assert page.count('aria-checked="true"') == 0
        assert page.count('aria-checked="false"') == len(ui.TARGET_CARDS)
        assert "kcard active" not in page

    def test_it_says_nothing_is_preselected(self, page):
        assert "Nothing is selected" in page
        assert "Nothing is selected" in ui.SELECTOR_EXPLANATION

    def test_it_is_a_keyboard_accessible_radiogroup(self, page):
        assert 'role="radiogroup"' in page
        assert page.count('role="radio"') == 9
        # §BH55 Phase 3: the group is named by the question the start page asks on screen, not a hidden label
        assert 'aria-labelledby="start-what"' in page
        assert 'id="start-what">What are you designing?</h2>' in page

    def test_brief_is_marked_required_and_project_name_optional(self, page):
        # §BH55 Phase 3: the start page asks in a designer's words — "Brief" is "Describe it", "Project name" is
        # "Name this project"; both still say which is required and which optional
        assert "Describe it <span>required</span>" in page
        assert "Name this project <span>optional</span>" in page


class TestContainerFieldsAreHintsOnly:

    def test_the_hint_fields_render(self, page):
        for f in ui.CONTAINER_HINT_FIELDS:
            assert f'id="{f["id"]}"' in page, f["id"]
            assert f["label"] in page, f["label"]

    def test_all_four_hints_are_optional(self):
        for f in ui.CONTAINER_HINT_FIELDS:
            assert "optional" in f["hint"], f["id"]

    def test_no_technical_dimension_is_demanded(self, page):
        assert "required" not in page.split('id="container-inputs"')[1][:1200]
        for f in ui.CONTAINER_HINT_FIELDS:
            assert f["id"] != "container-height"
            assert f["id"] != "container-diameter"

    def test_the_profile_gate_is_named_as_authoritative(self, page):
        assert ui.PROFILE_GATE_NOTE in page
        assert "starting hints, not specifications" in ui.PROFILE_GATE_NOTE
        assert "Confirm Profile" in ui.PROFILE_GATE_NOTE

    def test_the_container_panel_is_hidden_until_selected(self, page):
        assert 'id="container-inputs" hidden' in page  # [the owner's answer to the UI directions of 2026-09-25: C's start page replaced the old single page]

    def test_bh70_the_form_hint_offers_every_form(self):
        """§BH70(1), item 15: the form hint offered Bottle, Jar, Tube and Other — no palette, lipstick or pencil. It
        offers every form the one declaration names, and its examples are no longer only a serum's."""
        from apps.pipeline.targets.container import archetypes as A
        fields = {f["id"]: f for f in ui.CONTAINER_HINT_FIELDS}
        assert [k for k, _ in fields["container-archetype"]["options"]] == ["", *A.ARCHETYPES, "other"]
        assert "clasp" in fields["container-closure"]["hint"] and " g" in fields["container-capacity"]["hint"]

    def test_bh70_the_hints_are_offered_to_every_design_that_starts_from_a_shape(self, page):
        """§BH70(1), item 15: a Complete Product's first stage is a product container, and it showed no hints — they
        sat inside the Product Container's own panel. They have their own block, for both targets the page names."""
        assert ui.HINT_TARGETS == ("product_container", "complete_product")
        assert 'id="product-hints" data-targets="product_container complete_product" hidden' in page


class TestOnlyActiveTargetsCanBeCreated:

    def _create(self, client, brand, user, target, text="a 30 ml serum"):
        client.force_login(user)
        with patch("apps.core.health.worker_available", return_value=True), \
             patch("apps.pipeline.services.cost_ledger."
                   "daily_budget_exceeded", return_value=False), \
             patch("apps.pipeline.tasks.run_aria_pipeline.delay"):
            return client.post("/api/tasks/create/",
                               {"task_text": text, "brand_id": brand.id,
                                "design_target": target})

    def test_product_container_creates_with_that_target(self, client, brand,
                                                        user):
        r = self._create(client, brand, user, "product_container")
        assert r.status_code == 201, r.content
        t = DesignTask.objects.get(id=r.json()["task_id"])
        assert t.design_target == DesignTarget.PRODUCT_CONTAINER.value

    def test_packaging_creates_with_that_target(self, client, brand, user):
        r = self._create(client, brand, user, "packaging")
        assert r.status_code == 201, r.content
        t = DesignTask.objects.get(id=r.json()["task_id"])
        assert t.design_target == DesignTarget.PACKAGING.value

    def test_an_unknown_target_is_rejected(self, client, brand, user):
        r = self._create(client, brand, user, "teleportation")
        assert r.status_code == 400

    def test_a_disabled_target_is_not_selectable_in_the_form(self):
        for c in ui.TARGET_CARDS:
            assert ui.is_selectable(c["value"]) is c["active"], c["name"]
        # §BH55 Phase 2: marketing_material, social_media, exhibition_booth, display_stand and gift_set ship — no
        # target is left unselectable by name; the loop above holds every card to its own flag

    def test_a_missing_brief_creates_nothing(self, client, brand, user):
        before = DesignTask.objects.count()
        r = self._create(client, brand, user, "product_container", text="")
        assert r.status_code >= 400
        assert DesignTask.objects.count() == before

    def test_rendering_the_form_creates_no_task(self, client, user, brand):
        """No task may exist until the user submits."""
        client.force_login(user)
        before = DesignTask.objects.count()
        client.get(reverse("dashboard:new_classic"))
        assert DesignTask.objects.count() == before


class TestSharedFieldsSurviveTargetSwitching:
    """Switching targets is a display change in the client. These assert the
    contract the JS implements."""

    @pytest.fixture(scope="class")
    def js(self):
        import os
        from django.conf import settings
        return open(os.path.join(settings.BASE_DIR, "static", "js",
                                 "poll.js")).read()

    def test_switching_only_toggles_target_specific_fields(self, js):
        """Clearing the brief AFTER a successful submit is correct; clearing
        it on a target switch would not be. Scope to the switch handler."""
        block = js[js.index("function initTargetSelector"):]
        block = block[:block.index("\n}")]
        assert "container-inputs" in block
        for shared in ("task-input').value = ''", "project-name').value = ''",
                       "product-select').value = ''"):
            assert shared not in block, shared

    def test_the_selected_state_is_mirrored_to_assistive_tech(self, js):
        assert "setAttribute('aria-checked', 'true')" in js
        assert "setAttribute('aria-checked', 'false')" in js

    def test_disabled_chips_get_no_click_handler(self, js):
        assert ".target-chip:not([disabled])" in js

    def test_the_project_name_is_carried_not_discarded(self, js):
        assert "projectName" in js
        assert "projectName ? `${projectName}" in js

    def test_every_container_hint_is_carried(self, js):
        for f in ui.CONTAINER_HINT_FIELDS:
            assert f["id"] in js, f["id"]

    def test_the_brief_is_required_client_side_too(self, js):
        assert "if (!text) return;   // brief is required" in js


class TestNoRegressionAndNoOverreach:

    def test_the_pipeline_still_registers_both_active_targets(self):
        from apps.pipeline.targets import get_target
        assert get_target("packaging").name == "packaging"
        assert get_target("product_container").name == "product_container"

    def test_complete_product_capability_was_not_removed(self):
        """It is disabled in the SELECTOR only. Saying otherwise would
        misdescribe a working pipeline as broken."""
        from apps.pipeline.targets import get_target
        assert get_target("complete_product") is not None
        assert "implemented" in ui.COMPLETE_PRODUCT_NOTE
        assert "not because the capability was removed" in \
            ui.COMPLETE_PRODUCT_NOTE

    def test_missing_target_is_refused(self, client, brand, user):
        """A caller must explicitly choose the output it wants."""
        client.force_login(user)
        with patch("apps.core.health.worker_available", return_value=True), \
             patch("apps.pipeline.services.cost_ledger."
                   "daily_budget_exceeded", return_value=False), \
             patch("apps.pipeline.tasks.run_aria_pipeline.delay"):
            r = client.post("/api/tasks/create/",
                            {"task_text": "a carton", "brand_id": brand.id})
        assert r.status_code == 400, r.content
        assert not DesignTask.objects.exists()

    def test_the_form_default_is_a_target_its_designer_can_finish(self):
        # §BH55 Phase 3: it read `test_the_form_default_is_product_container` — the one target a stranger can never
        # finish (a bottle's last approval is the owner's); Packaging leads now, as the create door's own default does
        assert ui.DEFAULT_TARGET == ""

    def test_each_card_says_how_its_design_is_finished(self):
        # §BH55 Phase 3: every card read "Active" — the four a stranger can finish were not told from the four that
        # wait on the owner or cannot be approved yet (measured: the Phase 2 dry runs, Gate 2's own refusals)
        by_status = {c["value"]: c["status"] for c in ui.TARGET_CARDS}
        assert "Active" not in by_status.values()
        # [§BH70(3), his words: "A physical sample is never required to finish a design … Remove that condition from
        # Display Stand." The display stand is finished at its review since — a clean one is approved at Gate 2, 200
        # (test_create_design_target) — and only the gift set still cannot be approved yet]
        # [the owner's answer of 2026-09-27: the gift set's carton closes on the corrected flap, and its card joins the
        # five finished at review]
        assert {v for v, s in by_status.items() if s == ui.FINISHED_AT_REVIEW} == {
            "packaging", "marketing_material", "social_media", "gift_set"}
        # [§BH70(4) with §BH70(1) item 1: no container can be finished today — every one waiting at its review is
        # refused there — so its card says so, the same wording for the same meaning]
        # [§BH71 (0a) and (0b), the owner's goal of 2026-09-28, MEASURED after both on Gate 2's own reader: a clean
        # container waits on the owner's acceptance alone and is approved with it — it read CANNOT_FINISH_YET]
        assert by_status["product_container"] == by_status["palette"] == by_status["complete_product"] == \
            ui.FINISHED_WHEN_ACCEPTED

    def test_there_is_one_target_field_not_two(self):
        names = [f.name for f in DesignTask._meta.get_fields()
                 if "target" in f.name]
        assert names == ["design_target"]

    def test_no_provider_or_image_call_when_rendering_the_form(
            self, client, user, brand, monkeypatch):
        import apps.pipeline.services.claude_service as cs
        called = []
        for attr in dir(cs):
            if attr.startswith("call") or attr.startswith("generate"):
                monkeypatch.setattr(cs, attr,
                                    lambda *a, **k: called.append(attr),
                                    raising=False)
        client.force_login(user)
        assert client.get(reverse("dashboard:new_classic")).status_code == 200
        assert called == []


class TestReferenceConfigReachesTheBrowser:
    """B4b-2 §8 prerequisite: the limit and the allowlist are rendered from the
    secure core, so JavaScript never carries its own copy of either."""

    def test_the_config_comes_from_the_secure_core(self):
        from apps.pipeline import references as refs
        cfg = ui.reference_config()
        assert cfg["max_file_bytes"] == refs.max_upload_bytes()
        assert cfg["allowed_extensions"] == refs.ALLOWED_EXTENSIONS

    def test_it_is_rendered_into_the_page(self, page):
        from apps.pipeline import references as refs
        assert 'id="reference-config"' in page
        assert f'data-max-bytes="{refs.max_upload_bytes()}"' in page
        for ext in refs.ALLOWED_EXTENSIONS:
            assert ext in page, ext

    def test_the_limit_is_not_duplicated_in_javascript(self):
        import subprocess
        out = subprocess.run(["grep", "-rn", "20971520", "static/"],
                             capture_output=True, text=True).stdout
        assert out == "", out
        out2 = subprocess.run(["grep", "-rn", "20 \\* 1024", "static/"],
                              capture_output=True, text=True).stdout
        assert out2 == "", out2

    def test_all_five_categories_carry_a_label_and_a_description(self):
        assert [c["key"] for c in ui.REFERENCE_CATEGORIES] == [
            "container", "logo", "label", "inspiration", "color"]
        for c in ui.REFERENCE_CATEGORIES:
            assert c["label"] and c["description"].endswith(".")

    def test_the_persisted_key_stays_color_while_the_label_says_colour(self):
        colour = [c for c in ui.REFERENCE_CATEGORIES if c["key"] == "color"][0]
        assert colour["label"] == "Colour Reference"
        assert "colour" not in [c["key"] for c in ui.REFERENCE_CATEGORIES]

    def test_the_reference_only_notice_is_shown(self, page):
        assert "REFERENCE ONLY" in page
        assert "do not confirm dimensions" in page

    def test_previewable_excludes_the_document_formats(self):
        cfg = ui.reference_config()
        assert cfg["previewable_extensions"] == [".png", ".jpg", ".jpeg",
                                                 ".webp"]
        for doc in (".pdf", ".ai", ".eps"):
            assert doc not in cfg["previewable_extensions"], doc

    def test_the_authorized_url_template_is_the_only_file_route(self):
        cfg = ui.reference_config()
        assert cfg["authorized_file_url_template"] == \
            "/api/tasks/{task_id}/references/{reference_id}/"

    def test_no_raw_media_url_is_used_for_references(self):
        import subprocess
        out = subprocess.run(
            ["grep", "-rn", "reference.image.url", "templates/", "static/"],
            capture_output=True, text=True).stdout
        assert out == "", out
