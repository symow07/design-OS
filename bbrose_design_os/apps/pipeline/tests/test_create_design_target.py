"""Task creation accepts a Design Target (Phase B4a, 2026-07-08).

The creation endpoint gains one field. Omitted/blank → packaging (existing
clients unchanged); an active target is accepted; unknown or not-yet-active
targets are rejected rather than silently mis-created.

[§BH55 Phase 2, 2026-09-19: the artwork targets' own tests live here too — the
declared file that owns the design targets' creation.]
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings

from apps.core.models import Brand, Product
from apps.pipeline.models import CreativeBrief, DesignTask, GeneratedImage, PackagingOutput
from apps.pipeline.permissions import ROLE_DESIGNER
from apps.pipeline.targets import DesignTarget, get_target, ui
from apps.pipeline.targets.artwork import RECORD_KEY, MarketingMaterialTarget


class CreateDesignTargetTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        group, _ = Group.objects.get_or_create(name=ROLE_DESIGNER)
        self.user = User.objects.create_user("d", "d@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)

    def _create(self, **body):
        with patch("apps.core.health.worker_available", return_value=True), \
             patch("apps.pipeline.services.cost_ledger.daily_budget_exceeded",
                   return_value=False), \
             patch("apps.pipeline.tasks.run_aria_pipeline.delay"):
            return self.client.post("/api/tasks/create/",
                                    {"design_target": "packaging", "task_text": "make a design", **body})

    def test_empty_target_requires_an_explicit_choice(self):
        resp = self._create(design_target="")
        assert resp.status_code == 400
        assert not DesignTask.objects.exists()

    def test_bh70_every_cards_bottom_line_says_one_plain_thing(self):
        """§BH70(4), his words: "The bottom line of every card says one plain thing I can understand, the same wording for
        the same meaning. No engine status." And §BH70(1): "The card copy says 'any cosmetic product'." Two meanings,
        two lines; no card promises a finish its design cannot reach today — item 1 of the list he was sent: every
        container waiting at its review is refused there — and each container card says why, in the same words."""
        import re
        lines = {c["value"]: c["status"] for c in ui.TARGET_CARDS}
        # [§BH71 (0a) and (0b), the owner's goal of 2026-09-28, MEASURED after both on Gate 2's own reader: a clean
        # container waits on the owner's acceptance alone and is approved with it — it read CANNOT_FINISH_YET]
        assert set(lines.values()) == {ui.FINISHED_AT_REVIEW, ui.FINISHED_WHEN_ACCEPTED, "Graphics only", "Graphics only — construction pending"}, lines
        for status in lines.values():
            assert not re.search(r"[A-Z]{2,}|_", status) and "." not in status, status     # no code, one line
        for key in ("product_container", "complete_product", "palette"):
            card = ui.card_for(key)
            # [re-pinned: his last goal before the pitch, 2026-10-16, Step 1 (5): "card descriptions in one plain line
            # each, no jargon"] the warning line is said beside Approve, never on the card
            assert card["status"] == ui.FINISHED_WHEN_ACCEPTED and ui.CONTAINER_FINISH not in card["description"], card
        for key in ("product_container", "complete_product"):
            assert "any cosmetic product" in ui.card_for(key)["description"].lower()
            assert "bottle, jar or tube" not in ui.card_for(key)["description"]
        # [the owner's answer of 2026-09-27: the maker's printing specification is a production note, so it is no
        # longer why a container waits — the unbuilt checks are; the gift set's carton closes on the corrected flap]
        assert "printing specification" not in ui.CONTAINER_FINISH_WAITS
        assert "concept" in ui.CONTAINER_FINISH_WAITS and "copy fits" in ui.CONTAINER_FINISH_WAITS
        # [§BH71 (0a): what the container cards say now, in his words — "a warning beside Approve, never a block"]
        assert "not measured yet" in ui.CONTAINER_FINISH and "beside Approve" in ui.CONTAINER_FINISH
        assert "never a block" in ui.CONTAINER_FINISH
        gift = ui.card_for("gift_set")
        assert gift["status"] == ui.FINISHED_AT_REVIEW and "test-fits" in gift["description"]
        assert "not drawn here" not in gift["description"]

    def test_bh70_the_container_cards_are_drawn_with_no_bottle_with_a_neck(self):
        """§BH70(1), item 19 of the list the owner was sent: the Product Container and Complete Product cards were drawn
        with a bottle with a neck. Read off the New design page as it is served: each card's picture, and that
        picture's drawing in the page's own sprite."""
        import re
        html = self.client.get("/dashboard/new/classic/").content.decode()
        for value in ("product_container", "complete_product"):
            chip = html.split(f'data-target="{value}"')[1].split("</button>")[0]
            sym = re.search(r'<use href="#([\w-]+)"', chip).group(1)
            drawing = re.search(r'<symbol id="%s"[^>]*>(.*?)</symbol>' % sym, html, re.S).group(1)
            assert "M10 3h4v3.5l1.5 2" not in drawing and "M6 4h3v3l1 1.5V20H5V8.5l1-1.5z" not in drawing, (value, sym)

    def test_product_container_is_accepted(self):
        resp = self._create(design_target=DesignTarget.PRODUCT_CONTAINER.value)
        assert resp.status_code == 201
        task = DesignTask.objects.get(id=resp.json()["task_id"])
        assert task.design_target == DesignTarget.PRODUCT_CONTAINER.value

    def test_marketing_material_is_accepted_and_its_card_active(self):
        # §BH55 Phase 2: registered — the create door's own test is `get_target(x).name == x` — its card active
        target = DesignTarget.MARKETING_MATERIAL.value
        assert get_target(target).name == target
        card = ui.card_for(target)
        assert card["active"] is True and card["status"] == ui.FINISHED_AT_REVIEW   # §BH55 Phase 3: it read "Active"
        resp = self._create(design_target=target)
        assert resp.status_code == 201
        assert DesignTask.objects.get(id=resp.json()["task_id"]).design_target == target

    def test_social_media_is_accepted_and_its_card_active(self):
        # §BH55 Phase 2: registered, and its card active
        target = DesignTarget.SOCIAL_MEDIA.value
        assert get_target(target).name == target
        card = ui.card_for(target)
        assert card["active"] is True and card["status"] == ui.FINISHED_AT_REVIEW   # §BH55 Phase 3: it read "Active"
        resp = self._create(design_target=target)
        assert resp.status_code == 201

    def test_exhibition_booth_is_accepted_and_its_card_active(self):
        # §BH55 Phase 2: registered, and its card active
        target = DesignTarget.EXHIBITION_BOOTH.value
        assert get_target(target).name == target
        card = ui.card_for(target)
        assert card["active"] is True and card["status"].startswith("Graphics only")   # §BH55 Phase 3: it read "Active"
        resp = self._create(design_target=target)
        assert resp.status_code == 201

    def test_display_stand_is_accepted_and_its_card_active(self):
        # §BH55 Phase 2: registered, and its card active
        target = DesignTarget.DISPLAY_STAND.value
        assert get_target(target).name == target
        card = ui.card_for(target)
        # §BH55 Phase 3: it read "Active"; held at Gate 2 until a sample of its tray is tested, and the card said so —
        # [§BH70(3): "A physical sample is never required to finish a design … Remove that condition from Display
        # Stand." A clean stand is approved at its review (test_the_display_is_composed_… below: 200), and the card says
        # so, in the words every target finished at its review uses]
        assert card["active"] is True and card["status"].startswith("Graphics only")
        resp = self._create(design_target=target)
        assert resp.status_code == 201

    def test_gift_set_is_accepted_and_its_card_active(self):
        # §BH55 Phase 2: registered, and its card active — the last one
        target = DesignTarget.GIFT_SET.value
        assert get_target(target).name == target
        card = ui.card_for(target)
        # §BH55 Phase 3: it read "Active"; held at Gate 2 by its die's own domain, and the card says so
        # [the owner's answer of 2026-09-27: "Yes, switch the Gift Set carton to the corrected flap." Its carton closes
        # since — every set up to a dozen (test_bh70_answer_2_…) — and it is finished when a reviewer approves it]
        assert card["active"] is True and card["status"] == ui.FINISHED_AT_REVIEW
        resp = self._create(design_target=target)
        assert resp.status_code == 201

    def test_bh70_a_palette_is_started_as_its_case_its_concept_first(self):
        """[§BH70(2), his words: "Palette must be startable from New design. If it needs its case, lid, hinge and clasp
        read from a concept, the system makes that concept as its first step. It does not refuse me at the door." This
        test read `test_palette_is_refused_before_any_spend_and_named_with_what_it_needs`: a 400, TARGET_NEEDS.]
        A palette starts — a Product Container design whose shape step proposes the Compact / Palette form, dispatched
        to make its concept first — and its card can be chosen and says how it is finished."""
        from unittest.mock import patch as _patch

        from apps.pipeline.targets import container as C
        card = ui.card_for(DesignTarget.PALETTE.value)
        assert card["active"] is True and not card.get("needs")
        assert card["status"] == ui.card_for(DesignTarget.PRODUCT_CONTAINER.value)["status"]   # a container's line
        with _patch("apps.core.health.worker_available", return_value=True), \
                _patch("apps.pipeline.services.cost_ledger.daily_budget_exceeded", return_value=False), \
                _patch("apps.pipeline.tasks.run_aria_pipeline.delay") as dispatched, \
                self.captureOnCommitCallbacks(execute=True):           # a single design is dispatched on commit
            resp = self.client.post("/api/tasks/create/", {"task_text": "a four-pan eyeshadow palette",
                                                           "design_target": DesignTarget.PALETTE.value})
        assert resp.status_code == 201, resp.content
        task = DesignTask.objects.get(id=resp.json()["task_id"])
        assert task.design_target == DesignTarget.PRODUCT_CONTAINER.value
        assert ui.parse_container_hints(task.task_text)["container_type"] == "compact"
        assert C._infer_profile(task).archetype == "compact"          # the shape step proposes the palette's case
        dispatched.assert_called_once_with(task.id)                   # its first step: the concept
        assert get_target(DesignTarget.PALETTE.value).name == DesignTarget.PALETTE.value   # still registered

    def test_bh70_answer_4_a_bare_gloss_is_asked_before_anything_is_created(self):
        """The owner's answer of 2026-09-27 to the §BH70 report's fourth question: "Neither: when a brief says
        "gloss" without saying which, ask me: wand vial or squeeze tube." The two targets that design the product
        itself ask at the door — nothing created, nothing dispatched — and his choice, on the brief, starts the design
        in that form. A brief that says which, a finish's gloss and a carton are not asked."""
        from apps.pipeline.models import DesignProject
        from apps.pipeline.targets import container as C
        for target in (DesignTarget.PRODUCT_CONTAINER.value, DesignTarget.COMPLETE_PRODUCT.value):
            resp = self._create(task_text="a honey lip gloss inspired by blueberries", design_target=target)
            assert resp.status_code == 409, resp.content
            asked = resp.json()
            assert asked["error"] == C.GLOSS_QUESTION and asked["question"] == "Wand vial or squeeze tube?"
            assert [c["key"] for c in asked["choices"]] == ["wand vial", "squeeze tube"]
        rose = Product.objects.create(brand=self.brand, product_id="CO-410", name="Rosé Nectar Lip Gloss",
                                      category="CO", year=2026, product_type="lip gloss")
        resp = self._create(task_text="a warm rose design", product_id=rose.id, brand_id=self.brand.id,
                            design_target=DesignTarget.PRODUCT_CONTAINER.value)
        assert resp.status_code == 409 and resp.json()["error"] == C.GLOSS_QUESTION     # its record says gloss
        assert DesignTask.objects.count() == 0 and DesignProject.objects.count() == 0
        for choice, form in (("wand vial", "mascara"), ("squeeze tube", "tube")):
            resp = self._create(task_text="a honey lip gloss inspired by blueberries\n\n[Container type: %s]" % choice,
                                design_target=DesignTarget.PRODUCT_CONTAINER.value)
            assert resp.status_code == 201, resp.content
            assert C._infer_profile(DesignTask.objects.get(id=resp.json()["task_id"])).archetype == form
        for text in ("a lip gloss with a doe-foot wand", "a 15 ml lip gloss tube",
                     "a serum bottle with a high-gloss finish"):
            assert self._create(task_text=text,
                                design_target=DesignTarget.PRODUCT_CONTAINER.value).status_code == 201, text
        assert self._create(task_text="a honey lip gloss carton",
                            design_target=DesignTarget.PACKAGING.value).status_code == 201

    def test_his_goal_of_2026_10_06_item_1_his_container_type_always_wins_and_two_forms_are_asked(self):
        """His goal of 2026-10-06, item 1: "Rule, for every design: the Container type I choose ALWAYS wins. Then my
        brief's own words. Never a guess from picture readings or word order." Design 120's own brief: its Container type
        field said jar, its words "squeeze tube" — his choice is what it is made in, and the door asks first (the
        executor's extension, his to veto), his choice standing first; a brief naming two forms in two places with none
        chosen is asked, never decided by the fixed order; nothing is created until he answers."""
        from apps.dashboard.board import title_of
        from apps.pipeline.models import DesignProject
        from apps.pipeline.services.trend_board import subject_of
        from apps.pipeline.targets import container as C
        brief = ("Rose Rebel Hand Cream (test)\n\nType: hand cream in a squeeze tube with a flip-top cap, plus its tall\n"
                 "carton (straight tuck end).\n\n[Container type: %s; Product category: hand cream; Capacity: 60 ml; "
                 "Closure: flip-top cap]")
        for target in (DesignTarget.PRODUCT_CONTAINER.value, DesignTarget.COMPLETE_PRODUCT.value):
            resp = self._create(task_text=brief % "jar", design_target=target)
            assert resp.status_code == 409, resp.content
            asked = resp.json()
            assert asked["error"] == C.FORM_DIFFERS and asked["question"] == "Jar or Tube?", asked
            assert [(c["key"], c.get("keeps", False)) for c in asked["choices"]] == [("jar", True), ("tube", False)]
        assert DesignTask.objects.count() == 0 and DesignProject.objects.count() == 0
        # he keeps his choice: it is what the design is made in, everywhere it is read
        resp = self._create(task_text=brief % "jar", design_target=DesignTarget.PRODUCT_CONTAINER.value,
                            form_confirmed="true")
        assert resp.status_code == 201, resp.content
        task = DesignTask.objects.get(id=resp.json()["task_id"])
        assert (C.form_of_task(task), C._infer_profile(task).archetype) == ("jar", "jar")
        # [re-pinned by his goal of 2026-10-10, item 4] searched in the product's own words and its form's
        assert title_of(task).endswith("— jar") and subject_of(task) == "hand cream jar"
        # …or his brief's form, as the page sends it: his Container type
        resp = self._create(task_text=brief % "tube", design_target=DesignTarget.PRODUCT_CONTAINER.value)
        assert resp.status_code == 201, resp.content
        task = DesignTask.objects.get(id=resp.json()["task_id"])
        assert (C.form_of_task(task), C._infer_profile(task).archetype) == ("tube", "tube")
        assert title_of(task).endswith("— tube") and "jar" not in subject_of(task)
        assert C.form_said(task) == "ARIA: the product's form — Tube, your Container type (“tube”)"
        # a choice wins over a form word the fixed order lists before it, in another clause of the brief
        text = "A tube for Rosa. It replaces the pot it was sold in before.\n\n[Container type: tube]"
        assert C.form_choice(text)["form"] == "tube" and C.form_question(text) is None
        # two forms in two clauses, none chosen: asked — by every target a form is read for — never chosen between
        for target in (DesignTarget.PRODUCT_CONTAINER.value, DesignTarget.COMPLETE_PRODUCT.value,
                       DesignTarget.PACKAGING.value):
            resp = self._create(task_text="A tube for Rosa. It replaces the pot it was sold in before.",
                                design_target=target)
            assert resp.status_code == 409 and resp.json()["error"] == C.FORM_QUESTION, resp.content
            assert [c["key"] for c in resp.json()["choices"]] == ["tube", "jar"]
        # one clause names one product: its particular word — never asked
        for text, form in (("a tube of volumising mascara", "mascara"), ("a solid perfume in a slide tin", "tin"),
                           ("a deodorant stick", "oval_stick"), ("a dry shampoo spray", "aerosol")):
            assert C.form_choice(text)["form"] == form and C.form_question(text) is None, text
        # "Other" names no form the system draws: nothing is guessed from the brief beside it
        assert C.form_choice("a squeeze tube\n\n[Container type: other]")["form"] is None

    def test_unknown_target_rejected(self):
        resp = self._create(design_target="teapot")
        assert resp.status_code == 400

    def test_not_yet_active_target_rejected(self):
        # a valid enum value with no registered strategy is refused — [§BH55 Phase 2, 2026-09-19: every target is
        # registered now, gift set last, so one is taken out of the registry for this test; the door's own rule is
        # what is tested, and it has not moved]
        from apps.pipeline import targets as registry
        saved = registry._REGISTRY.pop(DesignTarget.GIFT_SET.value)
        try:
            resp = self._create(design_target=DesignTarget.GIFT_SET.value)
        finally:
            registry._REGISTRY[DesignTarget.GIFT_SET.value] = saved
        assert resp.status_code == 400
        assert "not active" in resp.json()["error"]


# --- §BH55 PHASE 2 (2026-09-19): THE ARTWORK TARGETS — the SDK, and Marketing Material, its first target. OWNER STANDING
# ORDER §BH55 (1dabb79), PHASE 2: "EVERY REMAINING TARGET … No target reads COMING SOON when this phase ends." A target
# ships when a person can create it, the concept is told what to depict, and after Gate 1 a design is composed around the
# approved concept, every run of type and the logo MEASURED, and the design waits at its gate — held there by any
# measured code, never passed on an unmeasured one. Here, in the declared file that owns the design targets' creation
# (a new test file would rebind the suite manifest's pin — §BH26(i)'s cascade).

MM = DesignTarget.MARKETING_MATERIAL.value


def _key_visual(root, name="kv.png", size=(1024, 1536)):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", size, (232, 214, 208))
    ImageDraw.Draw(im).rectangle([size[0] // 3, size[1] // 4, 2 * size[0] // 3, 3 * size[1] // 4], fill=(120, 60, 72))
    path = Path(root) / "generated" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)
    return f"generated/{name}"


def _logo(root):
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (1439, 300), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle([40, 60, 1400, 240], fill=(0, 0, 0, 255))
    path = Path(root) / "brand" / "logo.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)
    return str(path)


class ArtworkDeclarationTests(TestCase):
    """§BH55 Phase 2 — an artwork target is DECLARED: what its concept depicts, and the pieces its brief chooses."""

    def test_the_concept_is_told_what_to_depict(self):
        directive = MarketingMaterialTarget().concept_prompt_profile(None)
        assert "MARKETING MATERIAL" in directive and "ONE KEY VISUAL" in directive
        assert "Do NOT render any words" in directive and "carton" in directive
        assert MarketingMaterialTarget().concept_structure_id(None) is None

    def test_the_brief_chooses_the_pieces(self):
        from types import SimpleNamespace
        t = MarketingMaterialTarget()

        def keys(text):
            return [f.key for f in t.formats_for(SimpleNamespace(task_text=text))]
        assert keys("a poster for the launch") == ["a4_poster"]
        assert keys("a flyer and a poster") == ["a5_leaflet_front", "a5_leaflet_back", "a4_poster"]
        assert keys("postcards for the counter") == ["a6_postcard"]
        assert keys("launch collateral") == ["a5_leaflet_front", "a5_leaflet_back", "a4_poster"]   # the kit


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class TheDesignIsComposedMeasuredAndHeldAtItsGate(TestCase):
    """One composition, every assertion read from what it wrote."""

    @classmethod
    def setUpTestData(cls):
        cls.brand = Brand.objects.create(name="BBROSE", master_brief="x")

    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="artwork_")
        self.addCleanup(shutil.rmtree, self.media, True)
        self.logo = _logo(self.media)
        self.product = Product.objects.create(
            brand=self.brand, product_id="SK-900", name="Rose Damascena Night Repair Oil", category="SK", year=2026,
            product_type="serum", net_weight="30 ml",
            description="Precious repair oil that works overnight — deeply nourishing, restoring suppleness and glow "
                        "by morning. For all skin types.",
            how_to_use="Warm 3-4 drops between palms and press into clean skin every evening.")
        self.task = DesignTask.objects.create(brand=self.brand, product=self.product, design_target=MM,
                                              task_text="launch collateral for the night oil", status="running")
        with override_settings(MEDIA_ROOT=self.media):
            self.image = GeneratedImage.objects.create(task=self.task, direction_name="D", prompt_used="p",
                                                       variation_number=1, image_file=_key_visual(self.media))

    def _compose(self):
        from apps.pipeline.agents.aria import ARIAAgent
        with override_settings(MEDIA_ROOT=self.media, BRAND_LOGO_PATH=self.logo):
            MarketingMaterialTarget().begin_output(ARIAAgent(self.task.id), self.image)
        self.task.refresh_from_db()
        return self.task.packaging_outputs.get()

    def test_every_piece_is_composed_measured_and_waits_at_the_design_gate(self):
        import fitz
        out = self._compose()
        assert self.task.status == "awaiting_gate_2"
        spec = out.spec_sheet
        rec = spec[RECORD_KEY]
        assert spec["backend"] == "artwork" and spec["design_target"] == MM
        assert [r["key"] for r in rec["formats"]] == ["a5_leaflet_front", "a5_leaflet_back", "a4_poster"]
        assert rec["codes"] == [], rec["codes"]
        assert rec["copy"]["headline"] == "Rose Damascena Night Repair Oil"
        assert rec["copy"]["headline_source"] == "the product record"
        assert rec["print_readiness"]["state"] == "NOT_ESTABLISHED"
        # the picture the design's gate shows, at the resolution pdf_to_png declares (not the 72 dpi sips renders at)
        assert rec["preview"]["dpi"] == 150 and rec["preview"]["px"][0] > 1500, rec["preview"]
        for r in rec["formats"]:
            assert r["runs"] and all(x["state"] == "HELD" for x in r["runs"]), r["key"]
            assert all(x["width_mm"] <= x["box_width_mm"] for x in r["runs"])
            assert r["vertical"]["state"] == "HELD"
            assert r["ground"]["hex"] == "#F6EDEB"                  # §BB1's ruled ground, by lookup
            assert r["logo"]["state"] == "PLACED" and r["logo"]["placed_mm"][0] >= 12.0      # §AU3 print minimum
            assert r["logo"]["clear_space_mm"] > 0
            # the picture's pixels per inch as placed, recomputed here from the record's own two numbers
            kv = r["key_visual"]
            assert kv["state"] == "PLACED" and kv["source_px"] == [1024, 1536]
            assert abs(kv["effective_ppi"] - 1024 / (kv["placed_mm"][0] / 25.4)) < 0.1
        back = rec["formats"][1]
        assert any(x["name"].startswith("a5_leaflet_back-copy-") for x in back["runs"])   # the product's own words
        # one print file: a page per format, each at its true size with its bleed (points → mm)
        with override_settings(MEDIA_ROOT=self.media):
            with fitz.open(out.production_pdf.path) as pdf:
                sizes = [(round(p.rect.width * 25.4 / 72, 1), round(p.rect.height * 25.4 / 72, 1)) for p in pdf]
                fonts = {f[3] for p in pdf for f in p.get_fonts()}
            assert out.design_preview and os.path.exists(out.design_preview.path)
            assert out.design_preview_ai and os.path.exists(out.design_preview_ai.path)
        assert sizes == [(154.0, 216.0), (154.0, 216.0), (216.0, 303.0)]
        assert any("Montserrat" in f for f in fonts) and any("Poppins" in f for f in fonts), fonts   # the theme drew it

    def test_a_clean_design_is_approved_at_gate_2_and_one_with_a_check_open_is_approved_with_it_kept(self):
        """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a design"] a measured code no
        longer refuses Gate 2: the design is approved with it kept on its record, in words."""
        from apps.pipeline.permissions import ROLE_REVIEWER
        out = self._compose()
        reviewer = User.objects.create_user("rv", password="x")
        reviewer.groups.add(Group.objects.get_or_create(name=ROLE_REVIEWER)[0])
        self.client.force_login(reviewer)
        held = PackagingOutput.objects.create(task=self.task, approved_image=self.image,
                                              spec_sheet={"backend": "artwork",
                                                          RECORD_KEY: {"codes": ["ARTWORK_COPY_EXCEEDS_BOX"]}})
        r = self.client.post(f"/api/tasks/{self.task.id}/gate2_approve/", {"packaging_output_id": held.id},
                             content_type="application/json")
        assert r.status_code == 200, r.content
        held.refresh_from_db()
        assert held.spec_sheet["kept_with_approval"] == [{"code": "ARTWORK_COPY_EXCEEDS_BOX",
                                                          "words": "a piece's copy runs past its box"}]
        DesignTask.objects.filter(pk=self.task.pk).update(status="awaiting_gate_2")
        PackagingOutput.objects.filter(task_id=self.task.pk).update(is_final_approved=False)
        r = self.client.post(f"/api/tasks/{self.task.id}/gate2_approve/", {"packaging_output_id": out.id},
                             content_type="application/json")
        assert r.status_code == 200, r.content
        out.refresh_from_db()
        assert out.spec_sheet["kept_with_approval"] == []

    def test_a_rejected_design_goes_back_to_gate_1_and_is_composed_again_in_place(self):
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.permissions import ROLE_REVIEWER
        first = self._compose()
        first_preview = first.design_preview.name
        reviewer = User.objects.create_user("rv2", password="x")
        reviewer.groups.add(Group.objects.get_or_create(name=ROLE_REVIEWER)[0])
        self.client.force_login(reviewer)
        r = self.client.post(f"/api/tasks/{self.task.id}/gate2_reject/", {"notes": "a warmer picture"},
                             content_type="application/json")
        assert r.status_code == 200, r.content
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_gate_1"               # there is no dimension gate for artwork
        assert not GeneratedImage.objects.filter(task=self.task, is_approved=True).exists()
        with override_settings(MEDIA_ROOT=self.media):
            second = GeneratedImage.objects.create(task=self.task, direction_name="D", prompt_used="p",
                                                   variation_number=2,
                                                   image_file=_key_visual(self.media, "kv2.png", (1536, 1024)))
        with override_settings(MEDIA_ROOT=self.media, BRAND_LOGO_PATH=self.logo):
            MarketingMaterialTarget().begin_output(ARIAAgent(self.task.id), second)
        outs = list(self.task.packaging_outputs.all())
        assert len(outs) == 1 and outs[0].id == first.id and outs[0].approved_image_id == second.id
        hist = outs[0].spec_sheet["history"]
        assert hist[0]["generated_image_id"] == self.image.id
        assert hist[0]["gate_2_revision_note"] == "a warmer picture"
        assert hist[0]["preview"] == first_preview and hist[0]["preview_sha256"]
        assert outs[0].design_preview.name != first_preview

    def test_no_product_record_and_a_name_that_is_only_the_brief_line_hold_the_design(self):
        task = DesignTask.objects.create(brand=self.brand, design_target=MM, status="running",
                                         task_text="a poster for our new night oil")
        CreativeBrief.objects.create(task=task, directions=[], design_intent={
            "brief": {"product_name": "a poster for our new night oil"}})
        copy = MarketingMaterialTarget().copy_for(task)
        assert copy.headline_source == "the direction plan (no product record)"
        assert copy.codes == ["ARTWORK_HEADLINE_IS_THE_BRIEF_LINE"]

    def test_his_answers_122_a_piece_prints_his_briefs_size_before_the_records(self):
        """His answers after the fixes for design 122 (2026-10-08, transcribed at fc88e8d), (2): "the drawing must always
        print my brief's size (60 ml), never the picture's text." A piece's subline carries his brief's size, in his
        words, before the product record's net weight; with no record, his size alone."""
        from apps.core.models import Product
        product = Product.objects.create(brand=self.brand, product_id="SK-122", name="Rose Blossom", category="SK",
                                         year=2026, net_weight="100 ml e 3.38 fl. oz.")
        task = DesignTask.objects.create(brand=self.brand, product=product, design_target=MM, status="running",
                                         task_text="A poster for Rose Blossom.\n\nSize: 60 ml ℮ / 2 fl oz.\n")
        copy = MarketingMaterialTarget().copy_for(task)
        assert copy.subline.endswith(" · 60 ml ℮ / 2 fl oz") and "100 ml" not in copy.subline, copy.subline
        task.task_text = "A poster for Rose Blossom.\n"
        assert MarketingMaterialTarget().copy_for(task).subline.endswith(" · 100 ml e 3.38 fl. oz.")
        task.product, task.task_text = None, "a poster for our hand cream\n\nSize: 60 ml ℮ / 2 fl oz.\n"
        CreativeBrief.objects.create(task=task, directions=[], design_intent={"brief": {"product_name": "Rose Blossom"}})
        assert MarketingMaterialTarget().copy_for(task).subline == "60 ml ℮ / 2 fl oz"


class ARunThatDoesNotFitIsNamed(TestCase):

    def test_a_name_too_long_for_its_floor_is_over_and_coded_never_shrunk_below_it(self):
        from apps.ire import compose_artwork as ca
        fmt = MarketingMaterialTarget.formats[0]
        long_name = " ".join(["Extraordinary"] * 18)
        with tempfile.TemporaryDirectory() as media:
            doc, row = ca.artwork_document(fmt, ca.ArtworkCopy(headline=long_name), key_visual=None,
                                           logo=_logo(media))
        heads = [r for r in row["runs"] if "-headline-" in r["name"]]
        assert heads and min(r["size_pt"] for r in heads) >= round(min(fmt.width_mm, fmt.height_mm)
                                                                   * ca.HEADLINE_MIN_PT_PER_MM, 2)
        assert any(r["state"] == "EXCEEDS_BOX" for r in heads)
        assert ca.EXCEEDS_BOX in row["codes"] and ca.KEY_VISUAL_MISSING in row["codes"]
        assert doc.metadata["typography_surface"] == ca.SURFACE_FORMAT      # the theme's surface, not an exempt one


class W9TheCopyBoxGrowsToFit(TestCase):
    """[His answer of 2026-10-05, W9: "let the copy box grow to fit; no hold for under 2 mm".] The square post's copy box
    was 0.17 mm short of a two-word name and its category line, and held the design at Gate 2."""

    def _post(self, headline, subline):
        from PIL import Image

        from apps.ire import compose_artwork as ca
        from apps.pipeline.targets.artwork import SocialMediaTarget
        fmt = next(f for f in SocialMediaTarget.formats if f.key == "post_square")
        with tempfile.TemporaryDirectory() as media:
            kv = os.path.join(media, "kv.png")
            Image.new("RGB", (1024, 1024), (139, 58, 82)).save(kv)
            _doc, row = ca.artwork_document(fmt, ca.ArtworkCopy(headline=headline, subline=subline), key_visual=kv,
                                            logo=_logo(media))
        return ca, row

    #: a headline that needs three lines at its floor on the square post: over its box by 3.352 mm as laid
    LONG = " ".join(["Velvet"] * 6)

    def test_w9_a_box_short_of_its_words_grows_into_the_picture_and_holds_them(self):
        ca, row = self._post(self.LONG, "Face serum")
        grown = row["type_box_grown"]
        assert round(grown["by_mm"], 3) == 3.352 and row["vertical"]["state"] == "HELD", (grown, row["vertical"])
        assert ca.EXCEEDS_BOX not in row["codes"], row["codes"]
        laid = row["trim_mm"][1] * ca.KEY_VISUAL_SHARE + row["bleed_mm"]
        assert row["key_visual"]["region_mm"][3] == round(laid - grown["by_mm"], 3)      # the picture gave up its foot
        assert row["key_visual"]["region_mm"][3] >= ca.TYPE_BOX_PICTURE_KEEPS * laid     # and kept at least half

    def test_w9_an_overrun_under_2_mm_is_measured_never_a_hold(self):
        ca = __import__("apps.ire.compose_artwork", fromlist=["x"])
        assert ca.COPY_OVERRUN_TOLERANCE_MM == 2.0
        with patch.object(ca, "TYPE_BOX_PICTURE_KEEPS", 1.0):                    # the box may not grow at all
            _ca, held = self._post(self.LONG, "Face serum")
            assert (held["vertical"]["state"], held["vertical"]["over_mm"]) == ("EXCEEDS_BOX", 3.352)
            assert ca.EXCEEDS_BOX in held["codes"]                                # over by 2 mm or more: named, a hold
            with patch.object(ca, "COPY_OVERRUN_TOLERANCE_MM", 4.0):              # the same overrun, under the bar
                _ca, kept = self._post(self.LONG, "Face serum")
        assert kept["vertical"]["state"] == "OVER_UNDER_TOLERANCE" and ca.EXCEEDS_BOX not in kept["codes"], kept


class SocialMediaShips(TestCase):
    """§BH55 Phase 2 — Social Media on the artwork SDK: a square and a portrait post, a story and a link image, each a
    PNG at its exact pixel size — the file the channel takes — and a story's type kept clear of the platform's chrome."""

    @classmethod
    def setUpTestData(cls):
        cls.brand = Brand.objects.create(name="BBROSE", master_brief="x")

    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="social_")
        self.addCleanup(shutil.rmtree, self.media, True)
        self.logo = _logo(self.media)
        product = Product.objects.create(brand=self.brand, product_id="SK-901", name="Rose Damascena Night Repair Oil",
                                         category="SK", year=2026, product_type="serum", net_weight="30 ml")
        self.task = DesignTask.objects.create(brand=self.brand, product=product, status="running",
                                              design_target=DesignTarget.SOCIAL_MEDIA.value,
                                              task_text="a launch across our channels")
        with override_settings(MEDIA_ROOT=self.media):
            self.image = GeneratedImage.objects.create(task=self.task, direction_name="D", prompt_used="p",
                                                       variation_number=1, image_file=_key_visual(self.media))

    def test_each_piece_is_a_png_at_its_exact_size_and_a_story_keeps_its_type_off_the_chrome(self):
        from django.core.files.storage import default_storage
        from PIL import Image

        from apps.ire import compose_artwork as ca
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.targets.artwork import SocialMediaTarget
        with override_settings(MEDIA_ROOT=self.media, BRAND_LOGO_PATH=self.logo):
            SocialMediaTarget().begin_output(ARIAAgent(self.task.id), self.image)
            self.task.refresh_from_db()
            rec = self.task.packaging_outputs.get().spec_sheet[RECORD_KEY]
            sizes = {}
            for r in rec["formats"]:                       # measured back from the files the channels take
                with Image.open(default_storage.path(r["png"]["name"])) as im:
                    sizes[r["key"]] = im.size
        assert self.task.status == "awaiting_gate_2" and rec["codes"] == [], rec["codes"]
        assert sizes == {"post_square": (1080, 1080), "post_portrait": (1080, 1350), "story": (1080, 1920),
                         "link_landscape": (1200, 628)}
        assert all(r["png"]["exact"] and r["png"]["url"].startswith("/files/") for r in rec["formats"])
        story = next(r for r in rec["formats"] if r["key"] == "story")
        box_foot_px = (story["type_box_mm"][1] + story["type_box_mm"][3]) / ca.MM_PER_PX
        assert box_foot_px <= 1920 - SocialMediaTarget.STORY_CHROME_PX + 1e-6       # clear of the reply bar
        for r in rec["formats"]:
            assert all(x["state"] == "HELD" for x in r["runs"]), r["key"]
            assert r["logo"]["placed_mm"][0] / ca.MM_PER_PX >= 60.0                 # §AU3's minimum on screen
        link = next(r for r in rec["formats"] if r["key"] == "link_landscape")
        assert link["key_visual"]["region_mm"][2] < link["trim_mm"][0]              # the picture left, the type right

    def test_the_brief_chooses_the_channels(self):
        from types import SimpleNamespace

        from apps.pipeline.targets.artwork import SocialMediaTarget
        t = SocialMediaTarget()

        def keys(text):
            return [f.key for f in t.formats_for(SimpleNamespace(task_text=text))]
        assert keys("an instagram launch") == ["post_square", "post_portrait", "story"]
        assert keys("stories only") == ["story"]
        assert keys("a linkedin post") == ["link_landscape"]
        assert keys("launch week") == ["post_square", "post_portrait", "story", "link_landscape"]
        directive = t.concept_prompt_profile(None)
        assert "SOCIAL MEDIA" in directive and "Do NOT render any words" in directive


class ExhibitionBoothShips(TestCase):
    """§BH55 Phase 2 — Exhibition Booth on the artwork SDK: the stand's graphics at their true sizes, a page each in one
    print file; the picture's pixels per inch at three metres MEASURED and recorded, never judged."""

    def test_the_stands_graphics_are_composed_at_their_true_sizes(self):
        import fitz

        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.targets.artwork import ExhibitionBoothTarget
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        media = tempfile.mkdtemp(prefix="booth_")
        self.addCleanup(shutil.rmtree, media, True)
        logo = _logo(media)
        product = Product.objects.create(brand=brand, product_id="SK-902", name="Rose Damascena Night Repair Oil",
                                         category="SK", year=2026, product_type="serum", net_weight="30 ml")
        task = DesignTask.objects.create(brand=brand, product=product, status="running",
                                         design_target=DesignTarget.EXHIBITION_BOOTH.value,
                                         task_text="our stand at the beauty fair")
        with override_settings(MEDIA_ROOT=media, BRAND_LOGO_PATH=logo):
            image = GeneratedImage.objects.create(task=task, direction_name="D", prompt_used="p", variation_number=1,
                                                  image_file=_key_visual(media))
            ExhibitionBoothTarget().begin_output(ARIAAgent(task.id), image)
            task.refresh_from_db()
            out = task.packaging_outputs.get()
            with fitz.open(out.production_pdf.path) as pdf:
                sizes = [(round(p.rect.width * 25.4 / 72), round(p.rect.height * 25.4 / 72)) for p in pdf]
        rec = out.spec_sheet[RECORD_KEY]
        assert task.status == "awaiting_gate_2" and rec["codes"] == [], rec["codes"]
        assert [r["key"] for r in rec["formats"]] == ["back_wall", "counter_front", "rollup_banner"]
        assert sizes == [(3010, 2410), (1010, 910), (860, 2010)]                # true size, a 5 mm bleed each side
        wall = rec["formats"][0]
        assert wall["key_visual"]["region_mm"][2] == 3010.0   # near-square: the picture across the wall, the type below it
        # at three metres a 1024 px picture is a measured number and never a verdict: print readiness is not established
        assert wall["key_visual"]["effective_ppi"] < 20 and rec["print_readiness"]["state"] == "NOT_ESTABLISHED"
        assert all(x["state"] == "HELD" for r in rec["formats"] for x in r["runs"])

    def test_the_brief_chooses_the_pieces_and_the_concept_is_told_what_it_is(self):
        from types import SimpleNamespace

        from apps.pipeline.targets.artwork import ExhibitionBoothTarget
        t = ExhibitionBoothTarget()

        def keys(text):
            return [f.key for f in t.formats_for(SimpleNamespace(task_text=text))]
        assert keys("a roll-up banner for the fair") == ["rollup_banner"]
        assert keys("a corner stand with a counter") == ["counter_front", "side_wall"]
        assert keys("our stand at the fair") == ["back_wall", "counter_front", "rollup_banner"]
        directive = t.concept_prompt_profile(None)
        assert "EXHIBITION BOOTH" in directive and "no booth, stand, hall, floor plan" in directive


class DisplayStandShips(TestCase):
    """§BH55 Phase 2 — Display Stand: a counter display sized from the product — the arrangement, the tray and its header
    card PROPOSED from the unit's own size and the count the brief names — its header card and tray lip composed around
    the approved concept, and the tray's flat blank drawn beside them, PROVISIONAL. The expected sizes below were
    computed outside this file, by running the fit engine, not by the code under test's own arithmetic."""

    def test_the_fit_engine_chooses_no_empty_places_then_the_nearest_proportion(self):
        from apps.ire import fit_grid
        fit = fit_grid.tray_for(72, fit_grid.Unit(10.0, 10.0, 140.0, "a test eyeliner"))
        a = fit["arrangement"]
        assert (a["columns"], a["rows"], a["empty_places"]) == (12, 6, 0)       # the roadmap's 72-unit eyeliner display
        assert (a["inner_w_mm"], a["inner_d_mm"]) == (146.0, 74.0)
        assert [(b["columns"], b["rows"]) for b in fit["alternatives"]] == [(9, 8), (8, 9), (18, 4)]
        assert fit["tray"] == {"inner_w_mm": 146.0, "inner_d_mm": 74.0, "outer_w_mm": 152.0, "outer_d_mm": 80.0,
                               "lip_h_mm": 42.0, "back_h_mm": 84.0}
        assert fit["header"] == {"w_mm": 152.0, "h_mm": 120.0}                   # the tray's width; the 120 mm floor
        # §BH70(3): the structure stays PROVISIONAL, its drawing keeps the converter's note, and its sample is said — a
        # colleague test-fits it — never a hold
        assert fit["structure_state"].startswith("PROVISIONAL STRUCTURE — PHYSICAL SAMPLE REQUIRED")
        assert (fit["structure_status"], fit["codes"]) == ("PROVISIONAL_STRUCTURE", [])
        assert [i["code"] for i in fit["information"]] == ["PHYSICAL_SAMPLE_VALIDATION_REQUIRED"]

    def test_the_display_is_composed_with_its_structure_and_waits_at_its_gate(self):
        import fitz

        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.targets.artwork import DisplayStandTarget
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        media = tempfile.mkdtemp(prefix="display_")
        self.addCleanup(shutil.rmtree, media, True)
        logo = _logo(media)
        product = Product.objects.create(brand=brand, product_id="CO-903", name="Velvet Kohl Eyeliner", category="CO",
                                         year=2026, product_type="eyeliner", width_mm=10, depth_mm=10, height_mm=140)
        task = DesignTask.objects.create(brand=brand, product=product, status="running",
                                         design_target=DesignTarget.DISPLAY_STAND.value,
                                         task_text="a 72-unit counter display for our eyeliner")
        with override_settings(MEDIA_ROOT=media, BRAND_LOGO_PATH=logo):
            image = GeneratedImage.objects.create(task=task, direction_name="D", prompt_used="p", variation_number=1,
                                                  image_file=_key_visual(media))
            DisplayStandTarget().begin_output(ARIAAgent(task.id), image)
            task.refresh_from_db()
            out = task.packaging_outputs.get()
            with fitz.open(out.production_pdf.path) as pdf:
                sizes = [(round(p.rect.width * 25.4 / 72), round(p.rect.height * 25.4 / 72)) for p in pdf]
        rec = out.spec_sheet[RECORD_KEY]
        # the design waits at its gate — held there, until §BH70(3), by the registry's code for a structure no sample
        # had proven; "a physical sample is never required to finish a design", so it carries no code, and a reviewer
        # approves it: 200, no spend
        assert task.status == "awaiting_gate_2" and rec["codes"] == [], rec["codes"]
        from apps.pipeline.permissions import ROLE_REVIEWER
        reviewer = User.objects.create_user("rv-stand", password="x")
        reviewer.groups.add(Group.objects.get_or_create(name=ROLE_REVIEWER)[0])
        self.client.force_login(reviewer)
        with override_settings(MEDIA_ROOT=media, BRAND_LOGO_PATH=logo):
            r = self.client.post(f"/api/tasks/{task.id}/gate2_approve/", {"packaging_output_id": out.id},
                                 content_type="application/json")
        assert r.status_code == 200, r.content
        assert (rec["fit"]["units"], rec["fit"]["count_source"]) == (72, "the brief's own words")
        assert rec["fit"]["unit"]["source"] == "the product record"
        assert [r["key"] for r in rec["formats"]] == ["header_card", "front_lip"]
        assert sizes[:2] == [(158, 126), (158, 48)]           # the header card 152 × 120 and the lip 152 × 42, 3 mm bleed
        assert len(sizes) == 3                                 # and the structure on a page of its own
        assert all(x["state"] == "HELD" for r in rec["formats"] for x in r["runs"])
        assert rec["formats"][1]["key_visual"]["state"] == "NOT_IN_THIS_LAYOUT"   # the lip carries the name, not the picture

    def test_bh70_a_stand_saved_with_the_sample_code_is_not_held_for_it_at_gate_2(self):
        """§BH70(3), his words: "A physical sample is never required to finish a design … Remove that condition from
        Display Stand." Every stand composed before it carries the sample code on its saved record; Gate 2 reads it as
        information and approves the stand, and a code that is measured on the design still holds it."""
        from apps.pipeline.permissions import ROLE_REVIEWER
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        task = DesignTask.objects.create(brand=brand, status="awaiting_gate_2",
                                         design_target=DesignTarget.DISPLAY_STAND.value,
                                         task_text="a counter display for our eyeliner")
        image = GeneratedImage.objects.create(task=task, direction_name="D", prompt_used="p", variation_number=1)
        reviewer = User.objects.create_user("rv-saved", password="x")
        reviewer.groups.add(Group.objects.get_or_create(name=ROLE_REVIEWER)[0])
        self.client.force_login(reviewer)
        held = PackagingOutput.objects.create(task=task, approved_image=image, spec_sheet={
            "backend": "artwork", RECORD_KEY: {"codes": ["ARTWORK_COPY_EXCEEDS_BOX", "PHYSICAL_SAMPLE_VALIDATION_REQUIRED"]}})
        r = self.client.post(f"/api/tasks/{task.id}/gate2_approve/", {"packaging_output_id": held.id},
                             content_type="application/json")
        # [his goal of 2026-10-13, (1)] approved, the measured code kept with it in words — the sample code never one
        assert r.status_code == 200, r.content
        held.refresh_from_db()
        assert [k["code"] for k in held.spec_sheet["kept_with_approval"]] == ["ARTWORK_COPY_EXCEEDS_BOX"]
        DesignTask.objects.filter(pk=task.pk).update(status="awaiting_gate_2")
        PackagingOutput.objects.filter(task_id=task.pk).update(is_final_approved=False)
        saved = PackagingOutput.objects.create(task=task, approved_image=image, spec_sheet={
            "backend": "artwork", RECORD_KEY: {"codes": ["PHYSICAL_SAMPLE_VALIDATION_REQUIRED"]}})
        r = self.client.post(f"/api/tasks/{task.id}/gate2_approve/", {"packaging_output_id": saved.id},
                             content_type="application/json")
        assert r.status_code == 200, r.content

    def test_bh71_a_piece_whose_copy_could_not_be_measured_is_not_held_for_it_at_gate_2(self):
        """§BH71 (0a), the owner's goal of 2026-09-28: "Unmeasured checks … show as a warning beside Approve, never a
        block." A piece whose copy the instrument could not measure no longer holds its design at Gate 2; a
        measured overrun still does."""
        from apps.pipeline.permissions import ROLE_REVIEWER
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        task = DesignTask.objects.create(brand=brand, status="awaiting_gate_2",
                                         design_target=DesignTarget.DISPLAY_STAND.value,
                                         task_text="a counter display for our eyeliner")
        image = GeneratedImage.objects.create(task=task, direction_name="D", prompt_used="p", variation_number=1)
        reviewer = User.objects.create_user("rv-0a", password="x")
        reviewer.groups.add(Group.objects.get_or_create(name=ROLE_REVIEWER)[0])
        self.client.force_login(reviewer)
        held = PackagingOutput.objects.create(task=task, approved_image=image, spec_sheet={
            "backend": "artwork", RECORD_KEY: {"codes": ["ARTWORK_COPY_UNMEASURED", "ARTWORK_COPY_EXCEEDS_BOX"]}})
        r = self.client.post(f"/api/tasks/{task.id}/gate2_approve/", {"packaging_output_id": held.id},
                             content_type="application/json")
        # [his goal of 2026-10-13, (1)] approved, the measured overrun kept with it in words — never the unmeasured one
        assert r.status_code == 200, r.content
        held.refresh_from_db()
        assert [k["code"] for k in held.spec_sheet["kept_with_approval"]] == ["ARTWORK_COPY_EXCEEDS_BOX"]
        DesignTask.objects.filter(pk=task.pk).update(status="awaiting_gate_2")
        PackagingOutput.objects.filter(task_id=task.pk).update(is_final_approved=False)
        unmeasured = PackagingOutput.objects.create(task=task, approved_image=image, spec_sheet={
            "backend": "artwork", RECORD_KEY: {"codes": ["ARTWORK_COPY_UNMEASURED"]}})
        r = self.client.post(f"/api/tasks/{task.id}/gate2_approve/", {"packaging_output_id": unmeasured.id},
                             content_type="application/json")
        assert r.status_code == 200, r.content

    def test_a_unit_with_no_size_holds_the_design_and_a_count_not_named_is_proposed(self):
        from types import SimpleNamespace

        from apps.pipeline.targets.artwork import DisplayStandTarget
        t = DisplayStandTarget()
        unsized = SimpleNamespace(task_text="a counter display for our new balm", product=None)
        fit = t.fit_for(unsized)
        assert fit["codes"] == ["DISPLAY_STAND_UNIT_UNSIZED"] and "tray" not in fit
        assert [f.key for f in t.formats_for(unsized, fit)] == ["header_card"] and t.extras_for(unsized, fit) == []
        assert fit["units"] == 12 and fit["count_source"].startswith("PROPOSED")
        sized = SimpleNamespace(task_text="a counter display holding 24 of our 30 ml serum bottles", product=None)
        fit = t.fit_for(sized)
        assert (fit["units"], fit["codes"]) == (24, [])                             # §BH70(3): no sample hold
        assert fit["unit"]["source"].startswith("sized from the capacity")
        assert (fit["unit"]["width_mm"], fit["unit"]["height_mm"]) == (33.0, 96.0)   # the container's own proposal
        assert (fit["arrangement"]["columns"], fit["arrangement"]["rows"]) == (6, 4)


class GiftSetShips(TestCase):
    """§BH55 Phase 2 — Gift Set: the packaging target's own carton and gates, sized to hold the set — the pieces on an
    insert (apps/ire/fit_grid.py::insert_for), in a carton the dimension gate accepts — with no paid guess. The expected
    sizes below were computed by running the fit engine, not by the arithmetic under test."""

    def test_the_carton_is_sized_to_hold_the_set_with_no_paid_guess(self):
        from apps.pipeline.agents import dieline_agent as da
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        product = Product.objects.create(brand=brand, product_id="SK-904", name="Rose Damascena Serum", category="SK",
                                         year=2026, product_type="serum", width_mm=33, depth_mm=33, height_mm=96)
        task = DesignTask.objects.create(brand=brand, product=product, design_target=DesignTarget.GIFT_SET.value,
                                         task_text="a gift set of three serums for the holidays", status="running")
        with patch.object(da.DielineAgent, "_call_claude", side_effect=AssertionError("a paid estimate was asked for")):
            result, job = da.DielineAgent(task).run()
        # three pieces 33 × 33 × 96 mm in one row, 3 mm around each and 8 mm above them: 111 × 39 × 104, which the
        # dimension gate refuses (the cartons it accepts are taller than wide) — so the carton is the least whole
        # millimetre taller it accepts, 112, the insert raising the pieces 8 mm; NOT one piece's own record
        assert (result.width_mm.value, result.depth_mm.value, result.height_mm.value) == (111.0, 39.0, 112.0)
        assert {f.source for f in (result.width_mm, result.depth_mm, result.height_mm)} == {"gift set"}
        assert result.width_mm.confidence == 0.85 and result.can_proceed and (result.scenario, job.scenario) == ("A", "A")
        lone = DesignTask.objects.create(brand=brand, product=product, design_target="packaging", task_text="a carton")
        result2, _job = da.DielineAgent(lone).run()
        assert (result2.width_mm.value, result2.width_mm.source) == (33.0, "db")       # packaging is unchanged

    def test_the_set_is_counted_from_the_brief_and_its_insert_recorded(self):
        from types import SimpleNamespace

        from apps.pipeline.targets.gift_set import gift_set_fit, set_count
        assert set_count(SimpleNamespace(task_text="a set of four minis")) == (4, "the brief's own words")
        assert set_count(SimpleNamespace(task_text="a trio for the holidays"))[0] == 3
        assert set_count(SimpleNamespace(task_text="2 serums in one box"))[0] == 2
        assert set_count(SimpleNamespace(task_text="a holiday gift"))[1].startswith("PROPOSED")
        fit = gift_set_fit(SimpleNamespace(task_text="a set of 3 of our 30 ml serums", product=None))
        assert fit["carton_inner"] == {"w_mm": 111.0, "d_mm": 39.0, "h_mm": 112.0}   # the piece from its capacity: 33 × 96
        assert [c[0] for c in fit["insert"]["cutouts_mm"]] == [3.0, 39.0, 75.0] and fit["insert"]["raised_mm"] == 8.0
        assert (fit["arrangement"]["columns"], fit["arrangement"]["rows"]) == (3, 1)
        assert gift_set_fit(SimpleNamespace(task_text="a holiday gift", product=None)) is None   # nothing to size from
        directive = get_target(DesignTarget.GIFT_SET.value).concept_prompt_profile(None)
        assert "GIFT SET" in directive and "ONE carton" in directive

    def test_the_carton_is_one_the_dimension_gate_accepts_and_what_it_beat_is_recorded(self):
        from apps.ire.fit_grid import SET_CARTON_REFUSED, Unit, insert_for
        from apps.pipeline.targets.gift_set import gate_refusal
        piece = Unit(33.0, 33.0, 96.0, "a 30 ml piece")
        # the gate's own words for the row as it stands; it accepts the carton 8 mm taller
        assert "must be greater than width_mm (111.0)" in gate_refusal(111.0, 39.0, 104.0)
        assert gate_refusal(111.0, 39.0, 112.0) == ""
        trio = insert_for(3, piece, gate_refusal)
        assert trio["insert_raised_mm"] == 8.0
        # beaten: a square with one place empty, the larger carton; refused: one piece across, in the gate's own words
        assert [(a["columns"], a["rows"], a["empty_places"], a["carton_h_mm"]) for a in trio["alternatives"]] == [
            (2, 2, 1, 104.0)]
        assert [(a["columns"], a["rows"]) for a in trio["refused"]] == [(1, 3)]
        assert "more than 2.5x width_mm" in trio["refused"][0]["refusal"]
        # four stand as a square, not as a row of four made 44 mm taller
        four = insert_for(4, piece, gate_refusal)
        assert (four["arrangement"]["columns"], four["arrangement"]["rows"], four["insert_raised_mm"]) == (2, 2, 0.0)
        assert (four["alternatives"][0]["columns"], four["alternatives"][0]["raised_mm"]) == (4, 44.0)
        # every set up to a dozen is a carton the gate accepts
        for n in range(1, 13):
            c = insert_for(n, piece, gate_refusal)["carton_inner"]
            assert gate_refusal(c["w_mm"], c["d_mm"], c["h_mm"]) == "", n
        # a set no carton holds is REFUSED, every arrangement in the gate's own words
        big = insert_for(24, Unit(100.0, 100.0, 200.0, "a large piece"), gate_refusal)
        assert big["code"] == SET_CARTON_REFUSED and big["carton_inner"] is None
        assert big["refused"] and all(a["refusal"] for a in big["refused"])

    def test_a_carton_record_is_not_a_piece_and_a_refused_set_is_left_for_a_person(self):
        from apps.pipeline.agents import dieline_agent as da
        from apps.pipeline.targets.gift_set import set_piece
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        boxed = Product.objects.create(brand=brand, product_id="SK-905", name="Night Oil", category="SK", year=2026,
                                       product_type="carton", width_mm=40, depth_mm=40, height_mm=110,
                                       net_weight="30 ml e 1 fl. oz.")
        task = DesignTask.objects.create(brand=brand, product=boxed, design_target=DesignTarget.GIFT_SET.value,
                                         task_text="a gift set of three night oils", status="running")
        piece = set_piece(task)                               # the set replaces the carton: the piece, not 40 × 110
        assert (piece.width_mm, piece.height_mm) == (33.0, 96.0) and "carton" in piece.source
        big = Product.objects.create(brand=brand, product_id="SK-906", name="Body Wash", category="SK", year=2026,
                                     product_type="bottle", width_mm=100, depth_mm=100, height_mm=200)
        many = DesignTask.objects.create(brand=brand, product=big, design_target=DesignTarget.GIFT_SET.value,
                                         task_text="a set of 24 bottles", status="running")
        with patch.object(da.DielineAgent, "_call_claude", side_effect=AssertionError("a paid estimate was asked for")):
            result, _job = da.DielineAgent(many).run()
        # the gate refuses every arrangement: nothing is proposed and nothing guessed — the carton is for a person
        assert result.can_proceed is False
        assert all(f.blocked and f.value is None for f in (result.width_mm, result.depth_mm, result.height_mm))

    def test_the_set_speaks_for_itself_on_the_carton(self):
        from apps.pipeline.services.panel_info import build_panel_info
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        product = Product.objects.create(brand=brand, product_id="SK-907", name="Night Oil", category="SK", year=2026,
                                         product_type="carton", width_mm=40, depth_mm=40, height_mm=110,
                                         net_weight="30 ml", item_no="RD-0001-6", barcode_ean="5061030633793")
        gift = DesignTask.objects.create(brand=brand, product=product, design_target=DesignTarget.GIFT_SET.value,
                                         task_text="a set of three night oils")
        info = build_panel_info(gift)                   # the set's content; one piece's number and barcode not printed
        assert (info["net_weight"], info["item_no"], info["barcode_ean"]) == ("3 × 30 ml", "", "")
        lone = DesignTask.objects.create(brand=brand, product=product, design_target="packaging", task_text="a carton")
        info2 = build_panel_info(lone)                  # every other target: the record's own words, unchanged
        assert (info2["net_weight"], info2["item_no"], info2["barcode_ean"]) == ("30 ml", "RD-0001-6", "5061030633793")
        assert get_target(DesignTarget.GIFT_SET.value).design_metadata(gift, {"product_type": "carton"}) == {
            "product_type": "Gift set of 3"}
        assert get_target("packaging").design_metadata(lone, {"product_type": "carton"}) == {"product_type": "carton"}

    def test_bh70_answer_2_the_sets_carton_is_drawn_on_the_corrected_flap_and_its_die_accepted(self):
        """The owner's answer of 2026-09-27 to the §BH70 report's second question: "Yes, switch the Gift Set carton
        to the corrected flap." The set's carton is drawn at the straight tuck end's corrected closure, 1.2 — its top
        flap cut from the carton's depth — and the die check reads the version drawn: the pilot's row of three, held
        at 1.1 (a 97.2 mm lip against H/2 = 56 mm), is accepted. A packaging carton is drawn as before.
        [His final goal, 2026-10-05, B2, re-pinned: "A PRINT-READY DIELINE ... It must go to a printer without being
        edited."] every carton is drawn at 1.3 — 1.2's corrected flap, its tuck folds creased between their lock slits,
        a thumb notch — and its die read over 1.2's published domain; the structure chooser's recommendation stays 1.2.
        [His second goal of 2026-10-06, item 2, re-pinned: "TOP-TIER DIELINES"] every carton is drawn at 1.4 now — the
        reverse tuck end to the trade's written rules — and its die is folded and checked (fold_check): the pilot's
        row of three folds, and so does every set up to a dozen; 1.1's and 1.2's domain record stays as it was."""
        from apps.dielines import registry
        from apps.dielines.models import DielineJob
        from apps.pipeline.agents.dieline_agent import DielineAgent
        from apps.pipeline.targets.gift_set import die_qualification
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        task = DesignTask.objects.create(brand=brand, design_target=DesignTarget.GIFT_SET.value,
                                         task_text="a set of three", status="awaiting_gate_2")
        gift = get_target(DesignTarget.GIFT_SET.value)
        assert gift.carton_template_version(task) == "1.4" == registry.print_ready_version("reverse_tuck_end_carton")
        assert registry.recommended_corrected_version("straight_tuck_end_carton") == "1.2"
        assert registry.QUALIFIED_AS["1.3"] == "1.2"
        assert get_target("packaging").carton_template_version(task) == "1.4"
        job = DielineJob.objects.create(template_type="reverse_tuck_end_carton", scenario="A", input_json={})
        gen = DielineAgent(task).generate(job, {"width_mm": 111.0, "depth_mm": 39.0, "height_mm": 112.0},
                                          {"product_name": "Rose", "product_type": "Gift set of 3"},
                                          template_version=gift.carton_template_version(task))
        job.refresh_from_db()
        assert job.input_json["template"] == "reverse_tuck_end_carton" and job.input_json["template_version"] == "1.4"
        assert gen["fold_check"]["passed"], gen["fold_check"]["failed"]
        image = GeneratedImage.objects.create(task=task, direction_name="d1", prompt_used="p", variation_number=1,
                                              image_file="concepts/gift.png")
        out = PackagingOutput.objects.create(task=task, approved_image=image, dieline_job=job,
                                             spec_sheet={"fold_check/1.0": gen["fold_check"]})
        assert die_qualification(out) is None                  # 1.4 is read by the fold check, not 1.2's domain
        assert gift.gate2_hold(task, out) is None
        # every set up to a dozen of the pilot's piece closes at 1.2 — at 1.1 the check held the sets of 2, 3, 5 and 6
        from apps.dielines.qualification.domain import evaluate_domain
        from apps.dielines.qualification.runner import adapter_for
        from apps.ire.fit_grid import Unit, insert_for
        from apps.pipeline.targets.gift_set import NOT_APPLIED, gate_refusal

        def held(version):
            adapter = adapter_for("straight_tuck_end_carton" + ("@" + version if version != "1.1" else ""))
            applied = tuple(c for c in adapter.domain_constraints if c.name not in NOT_APPLIED)
            sets = []
            for n in range(1, 13):
                c = insert_for(n, Unit(33.0, 33.0, 96.0, "a 30 ml piece"), gate_refusal)["carton_inner"]
                user = {"width_mm": c["w_mm"], "depth_mm": c["d_mm"], "height_mm": c["h_mm"], "board_thickness_mm": 0.35,
                        "glue_tab_mm": 10.0, "bleed_mm": 3.0, "safe_margin_mm": 4.0}
                if evaluate_domain(user, applied):
                    sets.append(n)
            return sets
        assert held("1.1") == [2, 3, 5, 6] and held("1.2") == []
        from apps.dielines.geometry.engine import calculate_dieline
        from apps.dielines.geometry.fold_check import check
        from apps.dielines.validators.schema import DielineInputJSON
        for n in range(1, 13):                                 # and every one folds at 1.4
            c = insert_for(n, Unit(33.0, 33.0, 96.0, "a 30 ml piece"), gate_refusal)["carton_inner"]
            params = DielineInputJSON(template="reverse_tuck_end_carton", template_version="1.4", unit="mm",
                                      dimensions={"width_mm": c["w_mm"], "depth_mm": c["d_mm"], "height_mm": c["h_mm"]},
                                      print_settings={}, construction={"board_thickness_mm": 0.35, "glue_tab_mm": 12.0},
                                      metadata={"product_name": "Rose", "product_type": "Gift set"})
            assert check(calculate_dieline(params))["passed"], n

    def test_bh70_answer_2_aria_asks_the_target_which_version_to_draw(self):
        """The carton step draws the version the design's target names — a gift set's 1.2 — where it drew the
        current one for every carton. [His final goal, 2026-10-05, B2, re-pinned] both now name the print-ready 1.3."""
        from apps.dielines.models import DielineJob
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.agents.dieline_agent import DielineAgent
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        seen = {}

        def record(_self, *_a, **kw):
            seen[_self.task.design_target] = kw.get("template_version")
            raise RuntimeError("stopped here: the version asked for is what this test reads")
        dims = {"width_mm": 111.0, "depth_mm": 39.0, "height_mm": 112.0, "bleed_mm": 3.0, "safe_margin_mm": 4.0,
                "glue_tab_mm": 10.0}
        for target in (DesignTarget.GIFT_SET.value, DesignTarget.PACKAGING.value):
            task = DesignTask.objects.create(brand=brand, design_target=target, task_text="a set of three",
                                             status="awaiting_dimensions")
            image = GeneratedImage.objects.create(task=task, direction_name="d1", prompt_used="p",
                                                  variation_number=1, image_file="")
            job = DielineJob.objects.create(template_type="straight_tuck_end_carton", scenario="A", input_json={})
            out = PackagingOutput.objects.create(task=task, approved_image=image, dieline_job=job, spec_sheet={})
            with patch.object(DielineAgent, "generate", record), \
                    patch("apps.pipeline.services.panel_translate.translate_panel_info", return_value={}):
                ARIAAgent(task.id).resume_after_dimensions(out.id, dims)
        assert seen == {DesignTarget.GIFT_SET.value: "1.4", DesignTarget.PACKAGING.value: "1.4"}

    def test_a_die_outside_its_own_domain_is_held_at_gate_2_with_what_it_needs(self):
        from apps.dielines.models import DielineJob
        from apps.dielines.validators.schema import DielineInputJSON
        from apps.pipeline.permissions import ROLE_REVIEWER
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        task = DesignTask.objects.create(brand=brand, design_target=DesignTarget.GIFT_SET.value,
                                         task_text="a set of three", status="awaiting_gate_2")
        image = GeneratedImage.objects.create(task=task, direction_name="d1", prompt_used="p", variation_number=1,
                                              image_file="concepts/gift.png")

        # [a die as this deployment drew a set's carton until the owner's answer of 2026-09-27 — the straight tuck end at
        # its current version, 1.1; a set's carton is drawn at 1.2 since, and a die saved at 1.1 is read and held so]
        def drawn(w, d, h):          # a die as this deployment draws it: the straight tuck end, at its current version
            params = DielineInputJSON(template="straight_tuck_end_carton", unit="mm",
                                      dimensions={"width_mm": w, "depth_mm": d, "height_mm": h}, print_settings={},
                                      construction={}, metadata={"product_name": "x", "product_type": "carton"})
            job = DielineJob.objects.create(template_type="straight_tuck_end_carton", scenario="A",
                                            input_json=params.model_dump())
            return PackagingOutput.objects.create(task=task, approved_image=image, dieline_job=job, spec_sheet={})
        row = drawn(111.0, 39.0, 112.0)                  # three 30 ml pieces in a row
        reviewer = User.objects.create_user("rv-gift", password="x")
        reviewer.groups.add(Group.objects.get_or_create(name=ROLE_REVIEWER)[0])
        self.client.force_login(reviewer)
        r = self.client.post(f"/api/tasks/{task.id}/gate2_approve/", {"packaging_output_id": row.id},
                             content_type="application/json")
        # [his goal of 2026-10-13, (1): "NO check ever stops a design"] approved, the die outside its domain kept with
        # the approval in words — what it breaks and what would make it
        assert r.status_code == 200, r.content
        row.refresh_from_db()
        kept = row.spec_sheet["kept_with_approval"]
        assert [k["code"] for k in kept] == ["DIMENSION_COMBINATION_UNSUPPORTED"]
        assert kept[0]["words"].startswith("the carton's sizes are not a combination its die can make — lip = ")
        assert "the corrected closure" in kept[0]["words"] and "TUCK_LIP_VS_HEIGHT" not in kept[0]["words"]
        task.refresh_from_db()
        assert task.status in ("gate_2_approved", "completed")
        DesignTask.objects.filter(pk=task.pk).update(status="awaiting_gate_2")
        PackagingOutput.objects.filter(task_id=task.pk).update(is_final_approved=False)
        # the dust-pair clearance is not applied: a square of four with one place empty keeps its tuck, and is not held
        assert get_target(DesignTarget.GIFT_SET.value).gate2_hold(task, drawn(75.0, 75.0, 104.0)) is None
        assert get_target("packaging").gate2_hold(task, row) is None           # every other target: no hold
