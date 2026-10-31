"""Design Target router/strategy seam (Phase A, 2026-07-08).

Pins the invisible-refactor contract: PACKAGING is the default, the registry
resolves it, unknown/blank falls back to it, and ARIA routes the two branch
points (concept structure + post-Gate-1 output) through the strategy rather
than hardcoding packaging.
"""
from __future__ import annotations
from apps.pipeline.tests.quality_fixtures import critique, reviewed

from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.core.models import Brand
from apps.pipeline.models import DesignTask
from apps.pipeline.targets import DesignTarget, get_target, register
from apps.pipeline.targets.base import TargetStrategy
from apps.pipeline.targets.packaging import PackagingTarget


class RegistryTests(TestCase):
    def test_packaging_is_registered_and_default(self):
        assert isinstance(get_target(DesignTarget.PACKAGING.value), PackagingTarget)

    def test_unknown_or_blank_falls_back_to_packaging(self):
        assert isinstance(get_target(None), PackagingTarget)
        assert isinstance(get_target(""), PackagingTarget)
        assert isinstance(get_target("does_not_exist_yet"), PackagingTarget)

    def test_new_target_registers_without_touching_the_pipeline(self):
        class _Fake(TargetStrategy):
            name = "fake_target"

            def begin_output(self, aria, image):
                return "did-fake"
        register(_Fake())
        assert get_target("fake_target").begin_output(None, None) == "did-fake"


class DefaultFieldTests(TestCase):
    def test_new_task_defaults_to_packaging(self):
        brand = Brand.objects.create(name="B", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="a box")
        assert task.design_target == DesignTarget.PACKAGING.value


class AriaRoutingTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")

    def _task(self, status, target=DesignTarget.PACKAGING.value):
        return DesignTask.objects.create(
            brand=self.brand, task_text="a box", status=status,
            design_target=target)

    def test_resume_after_gate_1_dispatches_through_the_strategy(self):
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.models import GeneratedImage

        task = self._task("gate_1_approved")
        img = GeneratedImage.objects.create(
            task=task, direction_name="d", prompt_used="p", variation_number=1)
        reviewed(img)
        agent = ARIAAgent(task.id)

        strat = MagicMock()
        with patch.object(ARIAAgent, "_target", return_value=strat):
            agent.resume_after_gate_1(img.id)
        # ARIA delegates the back half to the target, not a hardcoded branch
        strat.begin_output.assert_called_once()
        assert strat.begin_output.call_args.args[1].id == img.id

    def test_packaging_begin_output_runs_the_dieline_estimate(self):
        from apps.pipeline.agents.aria import ARIAAgent

        task = self._task("gate_1_approved")
        agent = ARIAAgent(task.id)
        image = MagicMock()
        with patch.object(ARIAAgent, "_run_dieline_estimate") as est:
            PackagingTarget().begin_output(agent, image)
        est.assert_called_once_with(image)


class TheCartonsMapIsReadAtItsGateOneTests(TestCase):
    """His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): "build the map path to run on its own
    for every new design, for a wand vial and a carton"."""

    def test_his_go_a_cartons_concept_is_read_for_its_map_once_after_its_gate_one(self):
        """The carton's concept is pictured to be traced — its front square to the camera on a plain ground — and once
        its Gate 1 makes the carton's output, its approved picture's design map is read once, on the design's own
        ledger, and kept on that output; nothing is read where the read is switched off, as under every test."""
        import hashlib

        from django.conf import settings
        from django.core.files.base import ContentFile
        from django.test import override_settings

        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.models import GeneratedImage, PackagingOutput
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.packaging import CARTON_MAP_DIRECTIVE
        assert "FRONT panel square to the camera" in CARTON_MAP_DIRECTIVE and "plain seamless ground" in CARTON_MAP_DIRECTIVE
        brand = Brand.objects.create(name="B", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="a tall slim lip gloss carton", status="gate_1_approved",
                                         design_target=DesignTarget.PACKAGING.value)
        img = GeneratedImage.objects.create(task=task, direction_name="D", prompt_used="p", variation_number=1)
        png = b"\x89PNG\r\n\x1a\n" + b"carton" * 20
        img.image_file.save("carton.png", ContentFile(png), save=True)
        # [the owner's finding on design 119, 2026-10-03 (transcribed at 32898c7)] a carton is read by its front panel
        read = {"schema_version": dm.SCHEMA, "state": dm.MAP_READ, "source_sha256": hashlib.sha256(png).hexdigest(),
                "read": dm.CARTON_READ, "parts_prompt_version": dm.CARTON_PARTS_PROMPT_VERSION,
                "model": settings.CLAUDE_MODEL_HEAVY, "face_box_px": [0, 0, 10, 10],
                "parts": [{"kind": "field", "name": "cream", "box": [0, 0, 1, 1], "colour": "#FAF0E2"}],
                "problems": [], "cost": {"usd": "0.116400", "calls": 1}}
        aria = ARIAAgent(task.id)

        def estimate(_image):                     # the dieline estimate's own output, as `_run_dieline_estimate` makes
            PackagingOutput.objects.create(task=task, approved_image=img, spec_sheet={"backend": "dieline"})
        target = PackagingTarget()
        # [the owner's finding on design 119, 2026-10-03: "NO SILENT FALLBACK"] read and checked before the estimate:
        # here every part it names (its ground) is drawn
        traced = {"schema_version": dm.SHAPES_SCHEMA, "state": dm.SHAPES_TRACED, "problems": [],
                  "params": dict(dm.SHAPE_PARAMS)}
        with patch.object(aria, "_run_dieline_estimate", side_effect=estimate), \
                patch.object(dm, "read_carton_parts", return_value=read) as paid, \
                patch.object(dm, "trace_shapes", return_value=traced), \
                patch.object(dm, "read_parts") as standing:
            target.begin_output(aria, img)
            assert not paid.called and dm.SCHEMA not in task.packaging_outputs.order_by("-pk").first().spec_sheet
            with override_settings(DESIGN_MAP_READ=True, ANTHROPIC_API_KEY="k"):
                target.begin_output(aria, img)
                assert paid.call_count == 1 and paid.call_args.args[1] == png and not standing.called
                assert task.packaging_outputs.order_by("-pk").first().spec_sheet[dm.SCHEMA] == read
                target.begin_output(aria, img)            # the same picture again: its read is kept, nothing paid
            assert paid.call_count == 1 and task.packaging_outputs.order_by("-pk").first().spec_sheet[dm.SCHEMA] == read


class TheCartonsCopyIsHisBriefsTests(TestCase):
    """His go of 2026-10-02 and his answer 3 the same day (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): the map
    path for a carton, and "My brief's back copy counts as my copy for acceptance"."""

    def test_his_finding_on_119_the_back_and_sides_come_from_his_brief_never_another_products_supplier(self):
        """The owner's finding on design 119 (2026-10-03, transcribed at 32898c7): "The back panel fills from my brief,
        and never carries another product's supplier text." 119's brief labels its back "Carton back:" and its side
        "Carton side:"; its back took none of them and printed the brand's supplier block ("MADE IN CHINA BY SUPPLIER:
        YIWU …") where his brief says "Made in UAE". His "Carton back:" is read as his "Back copy:" is; his side's
        phrases are read for both sides; the brand's supplier block is printed only for a product its record
        describes, and never where his brief gives the back's own lines."""
        from apps.core.models import Product
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.services.panel_info import build_panel_info
        supplier = "MADE IN CHINA BY SUPPLIER: YIWU YIBIN TRADING COMPANY, GENERAL PARTNERSHIP."
        brand = Brand.objects.create(name="B", master_brief="x", regulatory_text=supplier)
        brief = ("Rose Glaze Lip Gloss (test)\n\nCarton side: \"LIP GLOSS · ملمّع الشفاه\", 8 ml ℮ / 0.27 fl oz.\n"
                 "Carton back: How to use: apply to lips alone or over lipstick. /\nIngredients: Polybutene, "
                 "Hydrogenated Polyisobutene,\nSilica Dimethyl Silylate, Parfum. / Batch code place. /\nMade in UAE.\n")
        back = dm.brief_back_copy(brief)
        his = {s["heading"]: s["text"] for s in back["sections"]}
        assert his["How to use"] == "apply to lips alone or over lipstick."
        assert his["Ingredients"].startswith("Polybutene") and his["Ingredients"].endswith("Parfum.")
        assert his[""] == "Made in UAE." and back["batch_code_place"] == "Batch code place."
        assert dm.brief_side_copy(brief) == ["LIP GLOSS · ملمّع الشفاه", "8 ml ℮ / 0.27 fl oz"]
        task = DesignTask.objects.create(brand=brand, task_text=brief, status="awaiting_dimensions",
                                         design_target=DesignTarget.PACKAGING.value)
        info = build_panel_info(task)
        assert info["how_to_use"] == his["How to use"] and info["ingredients"] == his["Ingredients"]
        assert info["regulatory_text"] == "Made in UAE." and "YIWU" not in str(info)
        task.task_text = "Rose Glaze Lip Gloss (test)\n"
        task.save()
        assert build_panel_info(task)["regulatory_text"] == ""                  # no record: no one's supplier block
        task.product = Product.objects.create(brand=brand, product_id="CO-411", name="Rose Glaze", category="CO",
                                              year=2026, product_type="lip gloss")
        task.save()
        assert build_panel_info(task)["regulatory_text"] == supplier            # the record's own product: the brand's
        # a set's carton is a carton: the same back from his brief, the set's own words after it
        task.task_text = brief + "\na set of three\n"
        task.product = None
        task.design_target = DesignTarget.GIFT_SET.value
        task.save()
        info = build_panel_info(task)
        assert info["regulatory_text"] == "Made in UAE." and info["how_to_use"] == his["How to use"]
        assert info["item_no"] == "" and info["barcode_ean"] == ""

    def test_his_answers_122_the_labels_size_is_his_briefs_before_the_records(self):
        """His answers after the fixes for design 122 (2026-10-08, transcribed at fc88e8d), (2): "the drawing must always
        print my brief's size". A carton's label (NET WT) prints his brief's size, in his words, before the product
        record's; the record's where his brief gives none; a set's the set's count times his."""
        from apps.core.models import Product
        from apps.pipeline.services.panel_info import build_panel_info
        brand = Brand.objects.create(name="B", master_brief="x")
        product = Product.objects.create(brand=brand, product_id="SK-122", name="Rose Blossom", category="SK", year=2026,
                                         product_type="hand cream", net_weight="100 ml e 3.38 fl. oz.")
        task = DesignTask.objects.create(brand=brand, product=product, status="awaiting_dimensions",
                                         design_target=DesignTarget.PACKAGING.value,
                                         task_text='Rose Blossom\n\nFront copy: BBROSE logo, "Rose Blossom", 60 ml ℮ 2 fl oz.\n')
        assert build_panel_info(task)["net_weight"] == "60 ml ℮ 2 fl oz"
        task.task_text = "Rose Blossom\n"
        task.save()
        assert build_panel_info(task)["net_weight"] == "100 ml e 3.38 fl. oz."
        task.task_text = "Rose Blossom, a set of three.\n\nSize: 30 ml ℮ / 1 fl oz.\n"
        task.design_target = DesignTarget.GIFT_SET.value
        task.save()
        assert build_panel_info(task)["net_weight"] == "3 × 30 ml ℮ / 1 fl oz"

    def test_his_go_a_cartons_name_and_back_copy_come_from_his_brief_where_no_record_gives_them(self):
        """A Complete Product's carton has no product record: its panel copy takes the product's name as a container's
        front takes it (the brief's own first line here, never sixty characters of it) and each piece his brief's back
        copy gives under a heading that names it, with the piece no heading names after the brand's regulatory line; a
        record's own words, where it gives them, still win, and a person still edits every field at the dimension gate."""
        from apps.core.models import Product
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.services.panel_info import build_panel_info
        brand = Brand.objects.create(name="B", master_brief="x", regulatory_text="BBROSE FZ-LLC, Dubai")
        brief = ("Rosé Nectar Lip Gloss\n\nBack copy: How to use: Glide over the lips. / Ingredients: Polybutene, "
                 "Rosa Damascena Oil. / Batch code place / Made in UAE\n")
        task = DesignTask.objects.create(brand=brand, task_text=brief, status="awaiting_dimensions",
                                         design_target=DesignTarget.PACKAGING.value)
        info = build_panel_info(task)
        his = {s["heading"]: s["text"] for s in dm.brief_back_copy(brief)["sections"]}
        assert info["product_name"] == "Rosé Nectar Lip Gloss"
        assert info["how_to_use"] == his["How to use"] and info["ingredients"] == his["Ingredients"]
        # [the owner's finding on design 119, 2026-10-03: the back "never carries another product's supplier text"] his
        # brief's own line, never after the brand's supplier block
        assert info["regulatory_text"] == his[""]
        assert info["warnings"] == "" and info["description"] == ""
        product = Product.objects.create(brand=brand, product_id="CO-410", name="Rose Nectar", category="CO",
                                         year=2026, product_type="lip gloss", how_to_use="Apply to clean lips.")
        task.product = product
        task.save()
        info = build_panel_info(task)
        assert info["product_name"] == "Rose Nectar" and info["how_to_use"] == "Apply to clean lips."
        assert info["ingredients"] == his["Ingredients"]


class HisFindingOn119NoSilentFallbackTests(TestCase):
    """The owner's finding on design 119 (2026-10-03, OWNER_BLOCKER_CLEARANCE.md, transcribed at 32898c7): "NO SILENT
    FALLBACK. If the map can't read the concept, STOP and tell me why, with options. Never hand me a different design."
    """

    def setUp(self):
        from django.core.files.base import ContentFile

        from apps.pipeline.models import GeneratedImage
        self.png = b"\x89PNG\r\n\x1a\n" + b"carton119" * 20
        brand = Brand.objects.create(name="B", master_brief="x")
        self.task = DesignTask.objects.create(brand=brand, task_text="Rose Glaze Lip Gloss\n\na tall slim carton",
                                              status="gate_1_approved", design_target=DesignTarget.PACKAGING.value)
        self.img = GeneratedImage.objects.create(task=self.task, direction_name="Bold Silhouette", prompt_used="p",
                                                 variation_number=1, is_approved=True)
        self.img.image_file.save("carton.png", ContentFile(self.png), save=True)

    def _record(self, parts):
        import hashlib

        from django.conf import settings

        from apps.pipeline.services import concept_design_map as dm
        return {"schema_version": dm.SCHEMA, "state": dm.MAP_READ, "read": dm.CARTON_READ,
                "source_sha256": hashlib.sha256(self.png).hexdigest(), "face_box_px": [0, 0, 10, 10],
                "parts_prompt_version": dm.CARTON_PARTS_PROMPT_VERSION, "model": settings.CLAUDE_MODEL_HEAVY,
                "parts": parts, "problems": [], "cost": {"usd": "0.091440", "calls": 1}}

    def test_his_finding_on_119_a_concept_the_map_cannot_read_stops_at_gate_one_and_a_part_it_cannot_draw_goes_on(self):
        """A carton concept whose map names no front panel stops before its paid dimension estimate: back at Gate 1, the
        concept no longer the chosen one, the reason and his three options kept on it and said in the log; the read kept
        on the picture, so choosing it again pays nothing; and the Gate 1 page's own record says so. A part the drawing
        would not draw (a framed panel — no tracer draws one yet) goes on, said ([his goal of 2026-10-13, (1)]). A concept whose every part
        is drawn goes on, its map and its shapes kept on the carton's output. A missing key is a stop too — never a
        different design — and not the picture's fault."""
        from django.test import override_settings

        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.models import PackagingOutput
        from apps.pipeline.serializers import DesignTaskSerializer
        from apps.pipeline.services import concept_design_map as dm
        aria = ARIAAgent(self.task.id)
        unread = dict(self._record([]), state=dm.MAP_UNREAD, reason=dm.CARTON_NO_FACE,
                      detail="the read named no front panel inside the picture")
        estimate = patch.object(aria, "_run_dieline_estimate")
        with override_settings(DESIGN_MAP_READ=True, ANTHROPIC_API_KEY="k"), estimate as est, \
                patch.object(dm, "read_carton_parts", return_value=unread) as paid:
            PackagingTarget().begin_output(aria, self.img)
            assert not est.called and not PackagingOutput.objects.filter(task=self.task).exists()
        self.task.refresh_from_db()
        self.img.refresh_from_db()
        stop = self.img.reference_provenance[dm.MAP_STOP_KEY]
        assert self.task.status == "awaiting_gate_1" and self.img.is_approved is False
        assert stop["concept"] is True and "no front panel" in stop["why"] and stop["options"] == list(dm.STOP_OPTIONS)
        assert self.img.reference_provenance[dm.SCHEMA] == unread                  # kept on the picture
        page = DesignTaskSerializer(self.task).data["gate_1_map_stop"]
        assert page["image_id"] == self.img.pk and page["direction_name"] == "Bold Silhouette" and page["why"]
        assert self.task.logs.filter(action__contains=dm.MAP_STOP).exists()
        # a part the drawing would not draw: named, and the picture's read not paid again
        window = self._record([{"kind": "field", "name": "cream panel", "box": [0, 0, 1, 1], "colour": "#F1D2C0"},
                               {"kind": "window", "name": "arched cartouche", "box": [0.2, 0.2, 0.8, 0.5],
                                "colour": "#56111B"}])
        traced = {"schema_version": dm.SHAPES_SCHEMA, "state": dm.SHAPES_TRACED, "problems": [],
                  "params": dict(dm.SHAPE_PARAMS)}
        self.task.status = "gate_1_approved"
        self.task.save()
        with override_settings(DESIGN_MAP_READ=True, ANTHROPIC_API_KEY="k"), estimate as est, \
                patch.object(dm, "read_carton_parts", return_value=window) as paid, \
                patch.object(dm, "trace_shapes", return_value=traced):
            PackagingTarget().begin_output(aria, self.img)
            # [his goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a design"] a part the
            # drawing would not draw: the design goes on — its estimate made, the part said beside Approve where it is
            # drawn (``front_checked``) — never stopped back at Gate 1; the picture's read not paid again
            assert paid.call_count == 1 and est.called
            self.img.refresh_from_db()
            assert dm.MAP_STOP_KEY not in (self.img.reference_provenance or {})
            assert self.task.logs.filter(action__contains="would not be drawn as the picture prints them — the "
                                                           "design goes on").exists()
        # every part drawn: the carton goes on, its map and shapes kept on its output, the stop no longer standing
        drawn = self._record([{"kind": "field", "name": "cream panel", "box": [0, 0, 1, 1], "colour": "#F1D2C0"},
                              {"kind": "shape", "name": "berry silhouette", "box": [0.1, 0.1, 0.9, 0.9],
                               "colour": "#56111B"}])
        shapes = dict(traced, shapes=[{"part": "berry silhouette", "ink": "#56111B", "box": [0.1, 0.1, 0.9, 0.9],
                                       "cubics": []}])

        def made(_image):
            PackagingOutput.objects.create(task=self.task, approved_image=self.img, spec_sheet={"backend": "dieline"})
        self.img.reference_provenance = {dm.MAP_STOP_KEY: stop}                  # stopped before, read no more
        self.img.save()
        self.task.status = "gate_1_approved"
        self.task.save()
        with override_settings(DESIGN_MAP_READ=True, ANTHROPIC_API_KEY="k"), \
                patch.object(aria, "_run_dieline_estimate", side_effect=made) as est, \
                patch.object(dm, "read_carton_parts", return_value=drawn), patch.object(dm, "trace_shapes",
                                                                                     return_value=shapes):
            PackagingTarget().begin_output(aria, self.img)
            assert est.call_count == 1
        spec = self.task.packaging_outputs.order_by("-pk").first().spec_sheet
        assert spec[dm.SCHEMA] == drawn and spec[dm.SHAPES_SCHEMA] == __import__("json").loads(
            __import__("json").dumps(shapes))                                    # as the record keeps it
        self.img.refresh_from_db()
        assert dm.MAP_STOP_KEY not in self.img.reference_provenance
        # no key: a stop too, never a different design — and not the picture's
        from django.core.files.base import ContentFile

        from apps.pipeline.models import GeneratedImage
        other = GeneratedImage.objects.create(task=self.task, direction_name="Liquid Swirl", prompt_used="p",
                                              variation_number=2, is_approved=True)
        other.image_file.save("swirl.png", ContentFile(self.png + b"swirl"), save=True)
        self.task.status = "gate_1_approved"
        self.task.save()
        with override_settings(DESIGN_MAP_READ=True, ANTHROPIC_API_KEY=""), estimate as est:
            PackagingTarget().begin_output(aria, other)
            assert not est.called
        other.refresh_from_db()
        stop = other.reference_provenance[dm.MAP_STOP_KEY]
        assert stop["concept"] is False and "no model key is set" in stop["why"] and other.is_approved is False


class HisFindingOn119NoPictureOnACartonTests(TestCase):
    """The owner's finding on design 119 (2026-10-03, OWNER_BLOCKER_CLEARANCE.md, transcribed at 32898c7): "KILL THE
    RASTER PATH. The flat-artwork and "background pattern" image edits ... must never place AI pixels on a carton."."""

    def test_his_finding_on_119_no_image_edit_reaches_a_carton_and_a_front_its_map_cannot_draw_stops(self):
        """Confirming a carton's dimensions makes no image edit and places no picture: the carton is composed with no
        artwork and no motif, its ground the map's. Where its front cannot be drawn from its concept's map the design
        goes back to Gate 1 with why — before the die is drawn or anything is spent — never drawn some other way."""
        from django.core.files.base import ContentFile
        from django.test import override_settings

        from apps.dielines.models import DielineJob
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.agents.dieline_agent import DielineAgent
        from apps.pipeline.models import GeneratedImage, PackagingOutput
        from apps.pipeline.services import concept_design_map as dm
        brand = Brand.objects.create(name="B", master_brief="x")
        dims = {"width_mm": 22.0, "depth_mm": 22.0, "height_mm": 110.0, "bleed_mm": 3.0, "safe_margin_mm": 4.0,
                "glue_tab_mm": 10.0}
        seen = {}

        def generate(_self, *_a, **kw):
            seen.update(kw)
            raise RuntimeError("stopped here: what the carton is composed with is what this test reads")
        task = DesignTask.objects.create(brand=brand, design_target=DesignTarget.PACKAGING.value,
                                         task_text="Rose Glaze Lip Gloss", status="awaiting_dimensions")
        image = GeneratedImage.objects.create(task=task, direction_name="Bold Silhouette", prompt_used="p",
                                              variation_number=1, is_approved=True)
        image.image_file.save("c.png", ContentFile(b"\x89PNG\r\n\x1a\n" + b"119" * 30), save=True)
        job = DielineJob.objects.create(template_type="straight_tuck_end_carton", scenario="A", input_json={})
        out = PackagingOutput.objects.create(task=task, approved_image=image, dieline_job=job, spec_sheet={})
        front = {"shapes": {"state": "TRACED"}, "edge_part": None, "ground": "#F1D2C0"}
        with patch.object(DielineAgent, "generate", generate), \
                patch("apps.pipeline.services.panel_translate.translate_panel_info", return_value={}), \
                patch.object(PackagingTarget, "carton_map_front", return_value=front):
            ARIAAgent(task.id).resume_after_dimensions(out.id, dims)
        # [the clean-up of 2026-10-04 (E1-E2), approved by the owner: the image edit is removed, and with it the
        # picture and the motif the carton was called with as None] the carton is called with no picture at all
        assert "artwork_path" not in seen and "motif_path" not in seen and seen["map_front"] == front
        assert seen["artwork_tint"] == "#F1D2C0"
        task.status = "awaiting_dimensions"
        task.save()
        seen.clear()
        with override_settings(DESIGN_MAP_READ=True), patch.object(DielineAgent, "generate", generate), \
                patch("apps.pipeline.services.panel_translate.translate_panel_info") as words, \
                patch.object(PackagingTarget, "carton_map_front", return_value=None):
            ARIAAgent(task.id).resume_after_dimensions(out.id, dims)
            assert not words.called and seen == {}
        task.refresh_from_db()
        image.refresh_from_db()
        assert task.status == "awaiting_gate_1" and image.is_approved is False
        assert "could not be drawn from its design map" in image.reference_provenance[dm.MAP_STOP_KEY]["why"]


class HisFindingOn119TheSecondCheckTests(TestCase):
    """The owner's finding on design 119 (2026-10-03, OWNER_BLOCKER_CLEARANCE.md, transcribed at 32898c7): "NO SILENT
    FALLBACK ... Never hand me a different design." — checked again where the design is drawn."""

    def setUp(self):
        import hashlib

        from django.conf import settings
        from django.core.files.base import ContentFile

        from apps.dielines.models import DielineJob
        from apps.pipeline.models import GeneratedImage, PackagingOutput
        from apps.pipeline.services import concept_design_map as dm
        self.png = b"\x89PNG\r\n\x1a\n" + b"second" * 30
        brand = Brand.objects.create(name="B", master_brief="x")
        self.task = DesignTask.objects.create(brand=brand, task_text="Rose Glaze Lip Gloss", status="awaiting_dimensions",
                                              design_target=DesignTarget.PACKAGING.value)
        self.img = GeneratedImage.objects.create(task=self.task, direction_name="Bold Silhouette", prompt_used="p",
                                                 variation_number=1, is_approved=True)
        self.img.image_file.save("c.png", ContentFile(self.png), save=True)
        sha = hashlib.sha256(self.png).hexdigest()
        self.read = {"schema_version": dm.SCHEMA, "state": dm.MAP_READ, "read": dm.CARTON_READ, "source_sha256": sha,
                     "face_box_px": [0, 0, 10, 10], "parts_prompt_version": dm.CARTON_PARTS_PROMPT_VERSION,
                     "model": settings.CLAUDE_MODEL_HEAVY, "problems": [], "cost": {"usd": "0.091440", "calls": 1},
                     "parts": [{"kind": "field", "name": "cream panel", "box": [0, 0, 1, 1], "colour": "#F1D2C0"},
                               {"kind": "shape", "name": "berry silhouette", "box": [0.1, 0.1, 0.9, 0.9],
                                "colour": "#56111B"},
                               {"kind": "type", "name": "the name", "box": [0.2, 0.3, 0.8, 0.9], "colour": "#F2B6AF",
                                "seen_text": "RoseGlaze"}]}
        # as the record keeps them: its numbers come back from the database as lists, never tuples
        self.shapes = __import__("json").loads(__import__("json").dumps(
            {"schema_version": dm.SHAPES_SCHEMA, "state": dm.SHAPES_TRACED, "source_sha256": sha, "problems": [],
             "params": dict(dm.SHAPE_PARAMS), "shapes": [{"part": "berry silhouette", "ink": "#56111B",
                                                          "box": [0.1, 0.1, 0.9, 0.9], "cubics": []}]}))
        job = DielineJob.objects.create(template_type="straight_tuck_end_carton", scenario="A", input_json={})
        self.out = PackagingOutput.objects.create(task=self.task, approved_image=self.img, dieline_job=job,
                                                  spec_sheet={dm.SCHEMA: self.read, dm.SHAPES_SCHEMA: self.shapes})

    def test_his_finding_on_119_a_front_its_map_would_not_draw_whole_goes_on_said_where_it_is_drawn(self):
        """A carton whose map on record would leave a part undrawn — read before the first check, or traced under other
        numbers — [his goal of 2026-10-13, (1): "NO check ever stops a design"] goes on when its dimensions are
        confirmed, that part named beside Approve with what he can do; it went back to Gate 1 until then. The shapes on
        record are read, never traced again for a tuple come back as a list. A container's shape step with no map of its
        picture at all still stops — nothing of the concept can be drawn — a face form's too."""
        from django.test import override_settings

        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.agents.dieline_agent import DielineAgent
        from apps.pipeline.models import GeneratedImage, PackagingOutput
        from apps.pipeline.services import concept_design_map as dm
        dims = {"width_mm": 22.0, "depth_mm": 22.0, "height_mm": 105.0, "bleed_mm": 3.0, "safe_margin_mm": 4.0,
                "glue_tab_mm": 10.0}
        with override_settings(DESIGN_MAP_READ=True), patch.object(dm, "trace_shapes") as traced, \
                patch.object(DielineAgent, "generate") as gen, \
                patch("apps.pipeline.services.panel_translate.translate_panel_info") as words:
            ARIAAgent(self.task.id).resume_after_dimensions(self.out.id, dims)
            assert not traced.called and gen.called
        self.task.refresh_from_db()
        self.img.refresh_from_db()
        self.out.refresh_from_db()
        assert dm.MAP_STOP_KEY not in (self.img.reference_provenance or {}) and self.img.is_approved is not False
        rows = self.out.spec_sheet["checks_shown/1.0"]
        # [his goal of 2026-10-13, (1)] and the layout picture this test does not stand in for, not made — said beside
        # Approve with why, never only in the log
        from apps.pipeline.targets.carton_layout import LAYOUT_NOT_MADE
        assert [(r["code"], r["what"]) for r in rows] == [
            (dm.MAP_STOP, "the type 'the name' is not drawn as the concept prints it — not traced"),
            (LAYOUT_NOT_MADE, "the carton's layout picture was not made, so its back, sides and flaps continue its "
                              "front — the picture service could not make it just now")], rows
        assert rows[0]["options"] == list(dm.STOP_OPTIONS)
        # a container's shape step, with no map of its picture: stopped — [his test blocker on design 124, 2026-10-11,
        # (2) and (4)] a face form's too, never drawn from its own reading
        for form in ("compact", "tube"):
            task = DesignTask.objects.create(brand=self.task.brand, task_text="a lip gloss",
                                             status="awaiting_container_profile",
                                             design_target=DesignTarget.PRODUCT_CONTAINER.value)
            img = GeneratedImage.objects.create(task=task, direction_name="D", prompt_used="p", variation_number=1,
                                                is_approved=True)
            out = PackagingOutput.objects.create(task=task, approved_image=img, spec_sheet={"backend": "container"})
            with override_settings(DESIGN_MAP_READ=True), \
                    patch("apps.pipeline.targets.container.reconstruct_container") as drawn:
                ARIAAgent(task.id).resume_after_container_profile(out.id, {"archetype": form})
            assert drawn.call_count == 0, form
            task.refresh_from_db()
            assert task.status == "awaiting_gate_1", form


class TheIllustratorPackageIsTheCartonsOwnDrawingTests(TestCase):
    """E5b — the owner's Q2, approved with the clean-up list (transcribed at b5892f9): "rebuild 'Prepare the Illustrator
    package' on the map-front drawing", so a carton has one engine. The package drew the carton a second time, from the
    direction's style and with no map front (``native_handoff.py``, ``compose_vector_art_graph``); it is composed now by
    the composer the carton's own design file is, from the same map front on its record — and a carton whose front no map
    draws is refused by name, nothing composed, nothing written."""

    def setUp(self):
        import hashlib
        import json

        from django.core.files.base import ContentFile

        from apps.dielines.models import DielineJob
        from apps.pipeline.models import GeneratedImage, PackagingOutput
        from apps.pipeline.services import concept_design_map as dm
        png = b"\x89PNG\r\n\x1a\n" + b"package" * 30
        brand = Brand.objects.create(name="B", master_brief="x")
        self.task = DesignTask.objects.create(brand=brand, task_text="Rose Glaze Lip Gloss", status="awaiting_dimensions",
                                              design_target=DesignTarget.PACKAGING.value)
        image = GeneratedImage.objects.create(task=self.task, direction_name="Bold Silhouette", prompt_used="p",
                                              variation_number=1, is_approved=True)
        image.image_file.save("c.png", ContentFile(png), save=True)
        sha = hashlib.sha256(png).hexdigest()
        read = {"schema_version": dm.SCHEMA, "state": dm.MAP_READ, "read": dm.CARTON_READ, "source_sha256": sha,
                "face_box_px": [0, 0, 10, 10], "parts_prompt_version": dm.CARTON_PARTS_PROMPT_VERSION, "model": "m",
                "problems": [], "cost": {"usd": "0.091440", "calls": 1},
                "parts": [{"kind": "field", "name": "cream panel", "box": [0, 0, 1, 1], "colour": "#F1D2C0"},
                          {"kind": "shape", "name": "berry silhouette", "box": [0.2, 0.3, 0.8, 0.8],
                           "colour": "#56111B"}]}
        square = [[[[0.2, 0.2], [0.4, 0.2, 0.6, 0.2, 0.8, 0.2], [0.8, 0.4, 0.8, 0.6, 0.8, 0.8],
                    [0.6, 0.8, 0.4, 0.8, 0.2, 0.8], [0.2, 0.6, 0.2, 0.4, 0.2, 0.2]]]]
        # as the record keeps them (lists, never tuples): a hot-pink band and a gold rule the picture runs edge to edge —
        # continued round the carton — and a berry silhouette within the front
        shapes = json.loads(json.dumps({
            "schema_version": dm.SHAPES_SCHEMA, "state": dm.SHAPES_TRACED, "source_sha256": sha, "problems": [],
            "params": dict(dm.SHAPE_PARAMS),
            "bands": [{"part": "hot pink band", "fill": "#E82878", "edge_ink": None, "edge_width": 0.0, "edge": [],
                       "outline": [[0.0, 0.0], [1.0, 0.0], [1.0, 0.2], [0.0, 0.2]], "drips": 0,
                       "edges": {"left": [0.0, 0.2], "right": [0.0, 0.2]}, "bleed_reach": 0.0}],
            "rules": [{"part": "gold rule", "box": [0.0, 0.2, 1.0, 0.208], "ink": "#D0A85C", "edges": ["left", "right"],
                       "drawn_box": [0.0, 0.2, 1.0, 0.208]}],
            "shapes": [{"part": "berry silhouette", "ink": "#56111B", "box": [0.2, 0.3, 0.8, 0.8], "cubics": square}]}))
        self.job = DielineJob.objects.create(template_type="straight_tuck_end_carton", scenario="A", input_json={})
        self.out = PackagingOutput.objects.create(task=self.task, approved_image=image, dieline_job=self.job,
                                                  spec_sheet={dm.SCHEMA: read, dm.SHAPES_SCHEMA: shapes})

    def test_e5b_the_package_is_the_cartons_own_drawing_its_front_from_the_same_map(self):
        """The carton made at its size step on the real path, then its package: one composer, twice — the package's
        front is the carton's front (one digest), set as the carton's record measured it, and every part the front and
        its continuation round the carton draw is in the package's design graph, on its own panel; the direction's style
        is never reached."""
        import contextlib
        import json
        import os

        from django.conf import settings

        from apps.dielines.services import export_service
        from apps.ire import compose
        from apps.ire.compose import CARTON_MAP_FRONT, FRONT_TYPE_KEY
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.models import PackagingOutput
        from apps.pipeline.services import native_handoff as nh
        composed = []
        real = compose.compose_components_graph

        def composing(*args, **kwargs):
            composed.append(real(*args, **kwargs))
            return composed[-1]
        dims = {"width_mm": 22.0, "depth_mm": 22.0, "height_mm": 105.0, "bleed_mm": 3.0, "safe_margin_mm": 4.0,
                "glue_tab_mm": 10.0}
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(compose, "compose_components_graph", composing))
            if hasattr(export_service, "compose_components_graph"):         # where the export imports it by name
                stack.enter_context(patch.object(export_service, "compose_components_graph", composing))
            stack.enter_context(patch("apps.pipeline.services.panel_translate.translate_panel_info", return_value={}))
            stack.enter_context(patch("apps.ire.compose_vector_art.compose_vector_art_graph",
                                      side_effect=AssertionError("the direction's style drew the carton")))
            ARIAAgent(self.task.id).resume_after_dimensions(self.out.id, dims)
            self.task.refresh_from_db()
            assert self.task.status == "awaiting_gate_2", (self.task.status, self.task.error_message)
            handoff = nh.generate_native_handoff(PackagingOutput.objects.get(pk=self.out.pk), None)
        # the carton's own design file, then its package — [his test findings on design 123, (4)] and between them only
        # the same front, drawn to measure its copy where it is drawn (``settle_front_copy``)
        assert len(composed) >= 2, composed
        carton, package = composed[0], composed[-1]
        assert {nh.front_digest(d) for d in composed} == {nh.front_digest(carton)}
        assert nh.front_digest(carton) is not None
        assert handoff["front_digest"] == nh.front_digest(carton) == nh.front_digest(package)
        assert handoff["drawn_from"] == CARTON_MAP_FRONT
        spec = PackagingOutput.objects.get(pk=self.out.pk).spec_sheet
        assert json.loads(json.dumps(package.metadata[FRONT_TYPE_KEY])) == spec[FRONT_TYPE_KEY]
        assert not [c for c in handoff["validation_codes"] if c.startswith(nh.HANDOFF_FRONT_NOT_THE_CARTONS)]

        def drawn(group):
            out = set()
            for child in group.children:
                out |= drawn(child) if child.type == "group" else {child.name}
            return out
        parts = set()
        for top in carton.root.children:
            if top.name in ("Map front", "Continued round the carton"):
                parts |= drawn(top)
        assert {"band-map-0", "rule-map-0", "shape-map-0", "continued-band-0-side_left"} <= parts, sorted(parts)
        with open(os.path.join(settings.MEDIA_ROOT, handoff["files"]["graph"]), encoding="utf-8") as fh:
            graph = json.load(fh)
        panels = {o["name"]: o["panel"] for o in graph["objects"]}
        assert parts <= set(panels), sorted(parts - set(panels))           # none dropped from the package
        assert not [o["name"] for o in graph["objects"] if o["type"] == "group"]
        assert {panels[p] for p in ("band-map-0", "rule-map-0", "shape-map-0")} == {"FRONT"}
        # [his final goal, 2026-10-05, B2: "The glue area marked"] the glue tab is glued: nothing continues onto it
        assert panels["continued-band-0-side_left"] == "SIDE_LEFT" and "continued-rule-0-glue_tab" not in panels

    def test_e5b_a_carton_whose_front_no_map_draws_is_refused_by_name_and_nothing_is_written(self):
        """No map of its picture on its record: the package is refused by name — before anything is composed, the writer
        never reached, nothing recorded — and the button's request is answered 409 with that name, which the page says
        in words; never the direction's style in its place."""
        from django.contrib.auth.models import Group, User

        from apps.dielines.validators.schema import DielineInputJSON
        from apps.ire import compose
        from apps.pipeline.models import PackagingOutput
        from apps.pipeline.permissions import ROLE_REVIEWER
        from apps.pipeline.services import native_handoff as nh
        params = DielineInputJSON(template="straight_tuck_end_carton", unit="mm",
                                  dimensions={"width_mm": 22, "depth_mm": 22, "height_mm": 105},
                                  print_settings={}, construction={},
                                  metadata={"product_name": "Rose Glaze Lip Gloss", "product_type": "carton"})
        self.job.input_json = params.model_dump()
        self.job.save(update_fields=["input_json"])
        self.out.spec_sheet = {"panel_info": {}}                           # no map of its picture on record
        self.out.save(update_fields=["spec_sheet"])
        reviewer = User.objects.create_user("reviewer-e5b", password="x")
        reviewer.groups.add(Group.objects.get_or_create(name=ROLE_REVIEWER)[0])
        self.client.force_login(reviewer)
        with patch("apps.ire.handoff.package.build_handoff_package", side_effect=AssertionError("written")) as writer, \
                patch.object(compose, "compose_components_graph", side_effect=AssertionError("composed")), \
                patch("apps.ire.compose_vector_art.compose_vector_art_graph",
                      side_effect=AssertionError("the direction's style drew the carton")):
            with self.assertRaises(nh.HandoffError) as refused:
                nh.generate_native_handoff(PackagingOutput.objects.get(pk=self.out.pk), None)
            answer = self.client.post(f"/api/tasks/{self.task.id}/generate_handoff/", {},
                                      content_type="application/json")
            assert not writer.called
        assert refused.exception.code == nh.HANDOFF_NO_MAP_FRONT
        assert "not drawn from its concept's map" in str(refused.exception)
        assert answer.status_code == 409 and answer.json()["code"] == nh.HANDOFF_NO_MAP_FRONT, answer.content
        assert answer.json()["error"] == nh.NO_MAP_FRONT_WORDS
        assert "handoff" not in PackagingOutput.objects.get(pk=self.out.pk).spec_sheet



class HisReviewPointThreeCartonGroundTests(TestCase):
    """[His review of 119, 2026-10-05, point 3: "One ground all round the carton, taken from the concept's own
    colour".] The carton's map front takes its ground from the concept's field with the photograph's light taken out,
    and says so."""

    def test_the_cartons_ground_is_the_concepts_own_colour(self):
        import cv2
        import numpy as np
        from types import SimpleNamespace
        from unittest.mock import patch

        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.packaging import PackagingTarget
        im = np.zeros((200, 200, 3), np.uint8)
        im[:] = (242, 212, 193)
        im[:20, :20] = (254, 247, 223)
        picture = cv2.imencode(".png", np.ascontiguousarray(im[..., ::-1]))[1].tobytes()
        spec = {dm.SCHEMA: {"parts": [{"name": "cream panel", "kind": "field", "colour": "#F2D4C1"}]}}
        output = SimpleNamespace(spec_sheet=spec, approved_image=None, save=lambda **kw: None)
        task = SimpleNamespace(product=None, task_text="Rose Glaze Lip Gloss", pk=None, id=None)
        with patch("apps.pipeline.targets.container._concept_bytes", return_value=picture), \
                patch("apps.pipeline.targets.container._map_front", return_value={"shapes": {"types": []}}), \
                patch("apps.pipeline.targets.container.product_name_for", return_value=("Rose Glaze", "x")):
            front = PackagingTarget().carton_map_front(task, output)
        assert front["ground"] == "#F2D7CE", front
        assert front["ground_light"]["photographed"] == "#F2D4C1" and "von Kries" in front["ground_light"]["method"]


class HisSecondBlocker123CartonFlatTests(TestCase):
    """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (4): "a
    standalone carton gets the same flat redraw before tracing".] A carton's own line art — every part of a carton
    standing alone, each small part a continuing carton gives none of its container's art — is drawn from its flat
    redraw kept on the concept, never from the strokes traced from its photo; the container's art where it is given."""

    def _front(self, art):
        from types import SimpleNamespace
        from unittest.mock import patch

        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.packaging import PackagingTarget
        field = {"part": "rose field", "ink": "#E3A9A7",
                 "strokes": [{"points": [[0.1, 0.1], [0.9, 0.7]], "closed": False}]}
        scallops = {"part": "scallops", "ink": "#E3A9A7",
                    "strokes": [{"points": [[0.0, 0.95], [1.0, 0.95]], "closed": False}]}
        spec = {dm.SCHEMA: {"parts": [{"name": "rose field", "kind": "motif", "box": [0.0, 0.0, 1.0, 0.8]},
                                      {"name": "scallops", "kind": "motif", "box": [0.0, 0.9, 1.0, 1.0]}]}}
        image = SimpleNamespace(pk=1)
        output = SimpleNamespace(spec_sheet=spec, approved_image=image, save=lambda **kw: None)
        task = SimpleNamespace(product=None, task_text="Rose Blossom Hand Cream", pk=None, id=None)

        def flat(front, spec_, image_, face_mm=None):      # [his goal of 2026-10-13, (2)] keyed by its face
            assert image_ is image
            return {"shapes": {"lines": [dict(line, flat={"state": "TRACED"}) for line in front["shapes"]["lines"]]}}
        with patch("apps.pipeline.targets.container._concept_bytes", return_value=b"png"), \
                patch("apps.pipeline.targets.container._map_front",
                      return_value={"shapes": {"types": [], "lines": [field, scallops]}}), \
                patch("apps.pipeline.targets.container.product_name_for", return_value=("Rose Blossom", "x")), \
                patch("apps.pipeline.targets.composite.continued_line_art", return_value=art), \
                patch("apps.pipeline.targets.container._with_flat_motifs", side_effect=flat) as flats:
            front = PackagingTarget().carton_map_front(task, output)
            plain = PackagingTarget().carton_front(task, spec, b"png", [])          # no concept: the check's own
        return {line["part"]: line for line in front["shapes"]["lines"]}, plain, flats

    def test_a_carton_standing_alone_draws_every_motif_from_its_flat_redraw(self):
        lines, plain, flats = self._front(None)
        assert all(line["flat"]["state"] == "TRACED" and "continued" not in line for line in lines.values()), lines
        assert flats.call_count == 1
        assert all("flat" not in line for line in plain["shapes"]["lines"])          # traced, measured only

    def test_a_continuing_carton_takes_its_containers_art_and_redraws_its_small_motifs_flat(self):
        art = {"part": "red hairline rose field", "outlines": {"svg": "<svg/>", "frame": [0, 0, 1, 1]},
               "box": [0.1, 0.05, 0.9, 0.95], "product_mm": [35.0, 120.0], "ink": "#AF2B2F", "ink_share": 0.16,
               "source_task_id": 122}
        lines, _plain, _flats = self._front(art)
        assert "continued" in lines["rose field"] and "flat" not in lines["rose field"]
        assert lines["scallops"]["flat"]["state"] == "TRACED" and "continued" not in lines["scallops"]


class TheContainersBackIsTrilingualTests(TestCase):
    """[His final goal, 2026-10-05 (transcribed at 32e9aaf), A: "Go: container back labels are trilingual too (English,
    Spanish, Arabic), translated per design."]"""

    ENGLISH = [{"heading": "How to use", "text": "Smooth over lips."},
               {"heading": "Ingredients", "text": "Aqua, Glycerin."},
               {"heading": "Warnings", "text": "External use only."},
               {"heading": "Batch code place", "text": ""}]
    TRANSLATED = {"es": {"how_to_use": "Aplicar sobre los labios.", "ingredients": "Aqua, Glycerin.",
                         "warnings": "Solo uso externo."},
                  "ar": {"how_to_use": "يُطبَّق على الشفتين.", "warnings": "للاستخدام الخارجي فقط."}}

    def test_the_back_reads_english_then_spanish_then_arabic_and_a_missing_piece_holds_by_name(self):
        from apps.pipeline.targets.container import (CONTAINER_LABEL_NOT_TRILINGUAL, back_english,
                                                     trilingual_sections)
        kept = {"english": back_english(self.ENGLISH), "translations": self.TRANSLATED}
        out, codes = trilingual_sections(self.ENGLISH, kept)
        assert codes == []
        assert [(s["lang"], s["heading"]) for s in out] == [
            ("en", "How to use"), ("en", "Ingredients / INGREDIENTES"), ("en", "Warnings"), ("en", "Batch code place"),
            ("es", "MODO DE USO"), ("es", "ADVERTENCIAS"), ("ar", "طريقة الاستعمال"), ("ar", "تحذيرات")]
        missing = {"english": kept["english"], "translations": {"es": self.TRANSLATED["es"]}}
        _out, codes = trilingual_sections(self.ENGLISH, missing)
        assert codes == ["%s:ar:how_to_use" % CONTAINER_LABEL_NOT_TRILINGUAL, "%s:ar:warnings" % CONTAINER_LABEL_NOT_TRILINGUAL]
        stale = {"english": {"how_to_use": "other words"}, "translations": self.TRANSLATED}
        _out, codes = trilingual_sections(self.ENGLISH, stale)              # translations of other words: none
        assert len(codes) == 5

    def test_the_back_is_translated_once_per_design(self):
        from unittest.mock import patch

        from apps.pipeline.targets.container import CONTAINER_TRANSLATIONS_KEY, translate_back
        spec = {}
        with patch("apps.pipeline.services.panel_translate.translate_panel_info",
                   return_value=self.TRANSLATED) as translate:
            translate_back(None, spec, self.ENGLISH)
            translate_back(None, spec, self.ENGLISH)                            # the same English: kept, not paid again
            assert translate.call_count == 1
            translate_back(None, spec, self.ENGLISH[:1])                        # changed English: translated again
            assert translate.call_count == 2
        assert spec[CONTAINER_TRANSLATIONS_KEY]["english"] == {"how_to_use": "Smooth over lips."}


# --- [His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (1): "NO GUESSED
# PANELS. After I pick a concept, draw ONE more picture of the same design as a flat carton layout (front, both sides,
# back, flaps, same style), ~$0.25, never printed, read into the map like the front. Every panel is drawn from it."] ---

import base64 as _layout_b64  # noqa: E402
import shutil as _layout_shutil  # noqa: E402
import tempfile as _layout_tempfile  # noqa: E402
from unittest import mock as _layout_mock  # noqa: E402

import cv2 as _layout_cv2  # noqa: E402
import numpy as _layout_np  # noqa: E402
from django.core.files.base import ContentFile  # noqa: E402
from django.test import override_settings  # noqa: E402

from apps.pipeline.models import ApiCallRecord, GeneratedImage  # noqa: E402

from apps.pipeline.targets import carton_layout as _CL  # noqa: E402

LAYOUT_DIMS = {"width_mm": 57.0, "depth_mm": 37.0, "height_mm": 123.0}


def _layout_png(img) -> bytes:
    return _layout_cv2.imencode(".png", img)[1].tobytes()


def _layout_sheet(side=0.65, wrong=None):
    """A flat sheet as the picture lays it: four tall panels in a row on white, a thin gap between, a flap above and
    below the front — each panel its own ground, a dark stripe at its foot."""
    img = _layout_np.full((1024, 1536, 3), 255, _layout_np.uint8)
    fw, h, gap, x = 300, 660, 12, 60
    boxes = {}
    for name, share in (("back", 1.0), ("side_left", side), ("front", 1.0), ("side_right", side)):
        w = int(fw * (wrong if name == "side_right" and wrong else share))
        boxes[name] = [x, 180, x + w, 180 + h]
        img[180:180 + h, x:x + w] = (200, 190, 240)
        img[180 + h - 60:180 + h, x:x + w] = (110, 60, 200)
        x += w + gap
    f = boxes["front"]
    boxes["top_flap"] = [f[0], 40, f[2], 168]
    boxes["bottom_flap"] = [f[0], 852, f[2], 980]
    for n in ("top_flap", "bottom_flap"):
        b = boxes[n]
        img[b[1]:b[3], b[0]:b[2]] = (200, 190, 240)
    return img, boxes


def _layout_scale(sheet) -> float:
    """The scale the map reads the sheet at (``concept_outline._read``)."""
    from apps.pipeline.services import concept_outline as co
    return co._read(_layout_png(sheet))[1]


def _layout_answer(boxes, s):
    """The read's answer: each panel's box and its stripe, in the read's own grid — the sheet at the map's scale ``s``,
    twice its size."""
    def up(b):
        return [int(round(v * s)) * 2 for v in b]
    panels = []
    for name, b in boxes.items():
        parts = [{"kind": "field", "name": "pink ground", "box": up(b), "confidence": 0.9}]
        if name in _CL.ROW:
            parts.append({"kind": "band", "name": "berry foot band", "box": up([b[0], b[3] - 60, b[2], b[3]]),
                          "confidence": 0.9})
        panels.append({"panel": name, "box": up(b), "parts": parts})
    import json
    text = json.dumps({"panels": panels, "notes": "a flat sheet"})
    return _layout_mock.MagicMock(content=[_layout_mock.MagicMock(type="text", text=text)],
                          usage=_layout_mock.MagicMock(input_tokens=5000, output_tokens=900))


class LayoutPictureTests(TestCase):
    def setUp(self):
        media = _layout_tempfile.mkdtemp(prefix="layout_")
        self.addCleanup(_layout_shutil.rmtree, media, True)
        self.enterContext(override_settings(MEDIA_ROOT=media, OPENAI_API_KEY="test"))
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(brand=brand, task_text="Rose Blossom Hand Cream",
                                              design_target="packaging", status="generating_dieline")
        self.image = GeneratedImage.objects.create(task=self.task, direction_name="Garden Wrap", prompt_used="p",
                                                   variation_number=1)
        self.image.image_file.save("garden_wrap.png",
                                   ContentFile(_layout_png(_layout_np.full((64, 32, 3), 220, _layout_np.uint8))))
        self.aria = _layout_mock.MagicMock(task=self.task)

    def test_the_picture_is_asked_for_at_his_size_drawn_once_and_kept_never_printed(self):
        said = _CL.layout_prompt(LAYOUT_DIMS)
        assert "each side 65% as wide as the front" in said and "2.2 times as tall" in said
        for noun in ("tube", "bottle", "jar", "box", "carton"):
            assert noun not in said.lower().split(), noun
        sheet, _boxes = _layout_sheet()
        data = _layout_mock.MagicMock(b64_json=_layout_b64.b64encode(_layout_png(sheet)).decode())
        with _layout_mock.patch("openai.images.edit",
                                return_value=_layout_mock.MagicMock(data=[data], _request_id="r")) as edit:
            record = _CL.make_layout(self.aria, self.image, LAYOUT_DIMS)
        assert edit.call_count == 1 and edit.call_args.kwargs["size"] == _CL.LAYOUT_SIZE
        assert edit.call_args.kwargs["prompt"] == said
        self.image.refresh_from_db()
        assert _CL.kept_layout(self.image) == record and _CL.layout_bytes(record) == _layout_png(sheet)
        assert ApiCallRecord.objects.filter(task=self.task, operation="image:carton layout:Garden Wrap").count() == 1
        # another concept picture: the layout is no longer its own
        self.image.image_file.save("other.png", ContentFile(_layout_png(_layout_np.full((64, 32, 3), 90, _layout_np.uint8))))
        assert _CL.kept_layout(self.image) is None

    def test_each_panel_is_read_into_a_map_as_the_front_is_and_checked_against_the_die(self):
        sheet, boxes = _layout_sheet()
        s = _layout_scale(sheet)
        got = _CL.read_layout(self.task, _layout_png(sheet), LAYOUT_DIMS, call=lambda *a, **k: _layout_answer(boxes, s))
        assert set(got["panels"]) == set(_CL.ROW + _CL.FLAPS)
        back = got["panels"]["back"]
        assert back["state"] == "READ" and back["face_box_px"] == [int(round(v * s)) for v in boxes["back"]]
        assert {p["kind"] for p in back["parts"]} == {"field", "band"}
        assert got["checked"] == {name: None for name in ("back", "side_left", "side_right") + _CL.FLAPS}
        assert float(got["cost"]["usd"]) > 0 and got["cost"]["calls"] == 1

    def test_a_panel_the_picture_draws_wrong_continues_the_front_said_why(self):
        sheet, boxes = _layout_sheet(wrong=1.0)                       # its right side drawn as wide as its front
        s = _layout_scale(sheet)
        got = _CL.read_layout(self.task, _layout_png(sheet), LAYOUT_DIMS, call=lambda *a, **k: _layout_answer(boxes, s))
        assert got["checked"]["side_left"] is None
        assert got["checked"]["side_right"].startswith("it stands 1.00 as wide as the front in the picture, the die 0.65")
        broke = _CL.read_layout(self.task, _layout_png(sheet), LAYOUT_DIMS,
                                call=_layout_mock.Mock(side_effect=RuntimeError("socket closed")))
        assert broke["panels"] == {} and "RuntimeError: socket closed" in broke["unread"]

    def _kept_sheet(self, wrong=None):
        """The sheet made and read for the concept, kept on it as ``ensure_layout`` keeps them — its read stood in."""
        sheet, boxes = _layout_sheet(wrong=wrong)
        s = _layout_scale(sheet)
        data = _layout_mock.MagicMock(b64_json=_layout_b64.b64encode(_layout_png(sheet)).decode())
        aria = _layout_mock.MagicMock(task=self.task)
        real = _CL.read_layout
        with _layout_mock.patch("openai.images.edit",
                                return_value=_layout_mock.MagicMock(data=[data], _request_id="r")), \
                _layout_mock.patch.object(_CL, "read_layout", side_effect=lambda task, pic, dims: real(
                    task, pic, dims, call=lambda *a, **k: _layout_answer(boxes, s))):
            read = _CL.ensure_layout(aria, self.image, LAYOUT_DIMS)
        self.image.refresh_from_db()
        return read, aria

    def test_the_picture_and_its_read_are_made_once_and_kept_and_never_a_refusal(self):
        read, aria = self._kept_sheet()
        assert read is not None and _CL.kept_layout_read(self.image) == read
        rows = ApiCallRecord.objects.filter(task=self.task).count()
        with _layout_mock.patch("openai.images.edit", side_effect=AssertionError("paid again")):
            assert _CL.ensure_layout(aria, self.image, LAYOUT_DIMS) == read            # kept: nothing paid
        assert ApiCallRecord.objects.filter(task=self.task).count() == rows
        self.image.image_file.save("another.png",
                                   ContentFile(_layout_png(_layout_np.full((64, 32, 3), 9, _layout_np.uint8))))
        with _layout_mock.patch("openai.images.edit", side_effect=RuntimeError("service down")):
            assert _CL.ensure_layout(aria, self.image, LAYOUT_DIMS) is None             # said, never refused
        assert "could not be made just now" in aria.log.call_args[0][0]

    def test_each_panel_the_read_gives_is_drawn_from_it_the_fronts_band_carried_never_traced_again(self):
        self._kept_sheet(wrong=1.0)                                # its right side drawn as wide as its front
        from apps.pipeline.services import concept_design_map as dm
        front_band = {"part": "berry foot band", "ink": "#C83C6E", "box": [-0.1, 0.9, 1.1, 1.0],
                      "edges": {"left": [0.9, 1.0]}}
        sources = [("Rose Blossom", "the product's name on the record")]
        panels = _CL.panel_fronts(self.task, self.image, sources, front_shapes={"shapes": [front_band]})
        assert panels["back"]["drawn_from"] == _CL.FROM_LAYOUT and panels["back"]["shapes"]["types"] == []
        assert panels["side_left"]["drawn_from"] == _CL.FROM_LAYOUT
        assert panels["side_right"] == {"continues": "it stands 1.00 as wide as the front in the picture, the die 0.65"}
        # the sheet's berry band is the front's own: carried round as the front draws it, never traced again
        assert panels["back"]["bands_from_front"] is True
        assert not [b for b in panels["back"]["shapes"]["bands"] + panels["back"]["shapes"]["shapes"]
                    if b.get("part") == "berry foot band"]
        assert panels["back"]["shapes"]["state"] == dm.SHAPES_TRACED
        assert _CL.panel_fronts(self.task, None, sources) == {}


# ---- [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (3):
# ---- "FULL-COLOUR ILLUSTRATION: a concept's illustrated scene (shaded roses, gradient sky, glowing arch) is redrawn flat
# ---- at high resolution and traced as COLOUR vector ..., keeping its colours, gradients and shapes."]

def _lid_art_png(w=600, h=400, round_lid=False):
    """A lid's flat redraw as the image model answers it: a sky running lilac at the top to pink below, a teal glow
    rising from the foot, two deep-rose flowers with green leaves — its own ground and colours (BGR)."""
    import cv2
    import numpy as _np
    img = _np.zeros((h, w, 3), _np.float32)
    top, low, glow = _np.float32((201, 170, 190)), _np.float32((190, 180, 234)), _np.float32((196, 202, 160))
    for yy in range(h):
        img[yy] = top + (low - top) * (yy / float(h - 1))
    yy, xx = _np.mgrid[0:h, 0:w]
    reach = _np.clip(1.0 - _np.hypot((xx - w / 2.0) / (w * 0.3), (yy - h) / (h * 0.45)), 0, 1)[..., None]
    img = img * (1 - reach * 0.8) + glow * reach * 0.8
    img = img.clip(0, 255).astype(_np.uint8)
    for cx, cy in ((int(w * 0.2), int(h * 0.62)), (int(w * 0.8), int(h * 0.6))):
        cv2.ellipse(img, (cx - 40, cy + 30), (36, 14), 30, 0, 360, (120, 150, 60), -1)      # a leaf
        cv2.circle(img, (cx, cy), 46, (150, 90, 210), -1)                                  # the rose
        cv2.circle(img, (cx, cy), 20, (110, 50, 160), -1)                                  # its heart
    if round_lid:
        mask = _np.zeros((h, w), _np.uint8)
        cv2.circle(mask, (w // 2, h // 2), min(w, h) // 2, 1, -1)
        img[mask == 0] = (255, 255, 255)
    ok, png = cv2.imencode(".png", img)
    return png.tobytes(), img


def _lab_px(bgr):
    import cv2
    import numpy as _np
    lab = cv2.cvtColor(_np.uint8([[bgr]]), cv2.COLOR_BGR2LAB)[0, 0].astype(float)
    return _np.array([lab[0] * 100 / 255, lab[1] - 128, lab[2] - 128])


def _hex_bgr(hx):
    return (int(hx[5:7], 16), int(hx[3:5], 16), int(hx[1:3], 16))


def test_goal_1011_illustration_traced_in_colour_over_its_own_sky_drawn_as_gradients(tmp_path):
    """The redraw read at $0: its sky a fitted field drawn as bands of left-to-right gradients — lilac above, pink below,
    the teal glow at its foot — every sample within ΔE 3 of the redraw's own; its flowers and leaves traced as filled
    colour regions in their own colours, none of them the sky; drawn as vector (gradients and paths, no raster) and,
    emitted, standing within ΔE 4 of the redraw at every sample; laid on a lid of other proportions FILLING it, its
    fractions the lid's as the map's are (his blocker (3); covering it stood 124's scene 5 % off)."""
    import fitz
    import numpy as _np
    from django.conf import settings as _s

    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Document, Group
    from apps.pipeline.targets.container import lid_art as LA
    png, img = _lid_art_png()
    tr = LA.trace_art(png, False)
    assert tr["state"] == LA.TRACED, tr.get("why")
    assert tr["measured"]["sky_de_p95"] < 4.0 and 0.5 < tr["measured"]["sky_share"] < 0.97, tr["measured"]
    rows = tr["sky"]["rows"]
    h, w = img.shape[:2]
    for fy, fx in ((0.05, 0.1), (0.4, 0.5), (0.95, 0.5), (0.95, 0.05), (0.2, 0.9)):
        drawn = _hex_bgr(rows[int(fy * len(rows))][int(round(fx * (len(rows[0]) - 1)))])
        assert _np.linalg.norm(_lab_px(drawn) - _lab_px(img[int(fy * (h - 1)), int(fx * (w - 1))])) < 3.0, (fy, fx)
    fills = [_lab_px(_hex_bgr(r["fill"])) for r in tr["regions"]]
    for colour in ((150, 90, 210), (110, 50, 160), (120, 150, 60)):             # the rose, its heart, the leaf
        assert min(_np.linalg.norm(f - _lab_px(colour)) for f in fills) < 6.0, colour
    assert _s  # the module reads no settings to trace
    doc = Document(page_w=200.0, page_h=130.0, title="lid",
                   root=Group(name="Artwork", children=[LA.art_group(tr, 5.0, 5.0, 190.0, 120.0)]))
    out = emit_pdf_ai(doc, str(tmp_path / "lid.ai"))
    with fitz.open(out) as pdf:
        page = pdf[0]
        assert page.get_images() == []                                          # vector, never a raster
        pix = page.get_pixmap(dpi=72)
    seen = _np.frombuffer(pix.samples, _np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3][:, :, ::-1]
    x, y, dw, dh, stretch = LA.on_lid(tr, 5.0, 5.0, 190.0, 120.0)
    assert (x, y, dw, dh) == (5.0, 5.0, 190.0, 120.0) and abs(stretch - (190 / 600.0) / (120 / 400.0)) < 1e-4
    for fy, fx in ((0.1, 0.5), (0.62, 0.2), (0.6, 0.8), (0.9, 0.5)):
        px = (x + fx * dw) * 72 / 25.4, (y + fy * dh) * 72 / 25.4
        got = seen[int(px[1]), int(px[0])]
        want = img[int(fy * (h - 1)), int(fx * (w - 1))]
        assert _np.linalg.norm(_lab_px(got) - _lab_px(want)) < 4.0, (fy, fx, got, want)


def test_goal_1011_illustration_a_round_lid_is_traced_inside_its_rim_and_a_redraw_that_will_not_open_is_refused():
    """A round lid's redraw traced inside its rim alone — nothing outside it kept; a redraw that will not open is
    REFUSED by name, never drawn without it."""
    from apps.pipeline.targets.container import lid_art as LA
    png, _img = _lid_art_png(500, 500, round_lid=True)
    tr = LA.trace_art(png, True)
    assert tr["state"] == LA.TRACED and tr["round"]
    assert all(r["fill"] != "#FFFFFF" for r in tr["regions"])
    bad = LA.trace_art(b"not a picture", False)
    assert (bad["state"], bad["code"]) == (LA.REFUSED, LA.ART_NOT_TRACED)


class LidArtTests(TestCase):
    """[His test blocker on design 124, (3)] the lid's flat redraw: made once from the lid stood square, kept on the
    concept, never paid again; a refusal said by name, never a drawing without it."""

    def setUp(self):
        import tempfile
        media = tempfile.mkdtemp(prefix="lidart_")
        self.addCleanup(__import__("shutil").rmtree, media, True)
        self.enterContext(override_settings(MEDIA_ROOT=media, OPENAI_API_KEY="test"))
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(brand=brand, task_text="Enchanted Rose palette",
                                              design_target="product_container", status="gate_1_approved")
        self.image = GeneratedImage.objects.create(task=self.task, direction_name="Arch & Bloom", prompt_used="p",
                                                   variation_number=1)
        png, _img = _lid_art_png()
        self.image.image_file.save("arch.png", ContentFile(png))
        from unittest import mock
        self.aria = mock.MagicMock(task=self.task)
        self.lid = {"shape": "rect", "png": png, "lid_sha256": "a" * 64}

    def test_goal_1011_illustration_the_lid_is_redrawn_once_from_the_lid_stood_square_and_kept(self):
        import base64
        from unittest import mock

        from apps.pipeline.targets.container import lid_art as LA
        art, _img = _lid_art_png()
        data = mock.MagicMock(b64_json=base64.b64encode(art).decode())
        with mock.patch("openai.images.edit", return_value=mock.MagicMock(data=[data], _request_id="r")) as edit:
            rec = LA.ensure_lid_art(self.aria, self.image, self.lid, (190.0, 120.0), "palette's lid")
        assert rec["state"] == LA.REDRAWN and edit.call_count == 1
        said = edit.call_args.kwargs["prompt"]
        assert said.startswith(LA.LID_ART_WORDS) and "no text" in said and "no logo" in said
        assert "wider than it is tall" in said and edit.call_args.kwargs["size"] == "1536x1024"
        assert "keep its layout exactly" in said and rec["prompt_version"] == LA.LID_ART_PROMPT_VERSION
        import cv2
        import numpy as _np
        sent = cv2.imdecode(_np.frombuffer(edit.call_args.kwargs["image"][0][1], _np.uint8), cv2.IMREAD_COLOR)
        assert sent.shape[:2] == (1024, 1536)                  # the lid stood square, sent filling the service's frame
        lid = cv2.resize(cv2.imdecode(_np.frombuffer(self.lid["png"], _np.uint8), cv2.IMREAD_COLOR), (1536, 1024))
        assert _np.abs(sent.astype(int) - lid.astype(int)).mean() < 2.0
        assert ApiCallRecord.objects.filter(task=self.task, operation="image:lid art:Arch & Bloom").count() == 1
        self.image.refresh_from_db()
        assert LA.kept_lid_art(self.image) == rec and LA.lid_art_bytes(rec) == art
        with mock.patch("openai.images.edit", side_effect=AssertionError("paid again")):
            assert LA.ensure_lid_art(self.aria, self.image, self.lid, (190.0, 120.0), "palette's lid") == rec
        self.image.image_file.save("other.png", ContentFile(_lid_art_png(300, 200)[0]))
        assert LA.kept_lid_art(self.image) is None                                     # another concept: not its own

    def test_goal_1011_illustration_a_redraw_the_service_refuses_is_said_never_drawn_without(self):
        from unittest import mock

        from apps.pipeline.targets.container import lid_art as LA
        with mock.patch("openai.images.edit", side_effect=RuntimeError("upstream 500")):
            rec = LA.ensure_lid_art(self.aria, self.image, self.lid, (190.0, 120.0), "palette's lid")
        assert (rec["state"], rec["code"]) == (LA.REFUSED, LA.ART_NOT_MADE) and "upstream 500" in rec["why"]
        assert LA.kept_lid_art(self.image) is None

    def test_pitch_a3_held_lid_art_of_another_proportion_is_refused_and_made_again(self):
        """[His goal after the pitch page, 2026-10-15, A (3): "131 drawn landscape when the concept is portrait"] a flat
        redraw kept for a lid of one proportion is never stretched onto a lid of another: refused, and made again at the
        lid's own — while the same lid keeps it, nothing spent."""
        import base64
        from unittest import mock

        from apps.pipeline.targets.container import lid_art as LA
        art, _img = _lid_art_png()
        data = mock.MagicMock(b64_json=base64.b64encode(art).decode())
        with mock.patch("openai.images.edit", return_value=mock.MagicMock(data=[data], _request_id="r")):
            rec = LA.ensure_lid_art(self.aria, self.image, self.lid, (110.0, 95.0), "palette's lid")
        self.image.refresh_from_db()
        assert LA.kept_lid_art(self.image, (110.0, 95.0)) == rec == LA.kept_lid_art(self.image)
        assert LA.kept_lid_art(self.image, (110.4, 95.0)) == rec                     # within the tolerance: the same lid
        assert LA.kept_lid_art(self.image, (110.0, 123.8)) is None                   # portrait: another lid's art
        with mock.patch("openai.images.edit", return_value=mock.MagicMock(data=[data], _request_id="r")) as edit:
            again = LA.ensure_lid_art(self.aria, self.image, self.lid, (110.0, 123.8), "palette's lid")
        assert edit.call_count == 1 and again["product_mm"] == [110.0, 123.8]



# ---- [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (5): "THE TRAY:
# ---- after I pick a concept, draw one more picture of the open palette in the same style (tray, pans, names), ~$0.25,
# ---- read into the map. Every pan gets a real shade colour and finish (matte / shimmer / glitter), from that picture
# ---- or, if needed, from the shade name and the concept's palette; list them for me to check. No grey pans."]


_TRAY_SHADES = [[(200, 190, 245), (180, 120, 230), (210, 200, 240), (190, 170, 235), (120, 90, 210), (90, 50, 150)],
          [(220, 180, 200), (90, 170, 220), (150, 80, 160), (160, 110, 200), (130, 70, 120), (60, 40, 110)],
          [(140, 110, 150), (170, 120, 170), (60, 90, 70), (80, 50, 80), (100, 80, 160), (70, 30, 90)]]
_TRAY_FINISHES = [["shimmer", "matte", "glitter", "shimmer", "matte", "matte"],
            ["matte", "shimmer", "matte", "glitter", "matte", "matte"],
            ["matte", "matte", "matte", "matte", "shimmer", "glitter"]]


def _tray_png(rows=3, cols=6, missing=None, seed=7):
    rnd = _layout_np.random.default_rng(seed)
    img = _layout_np.zeros((1024, 1536, 3), _layout_np.uint8)
    img[:] = (238, 236, 240)
    _layout_cv2.rectangle(img, (120, 160), (1416, 900), (226, 210, 242), -1)                 # the insert
    side, gap = 150, 50
    x0 = (1536 - (cols * side + (cols - 1) * gap)) // 2
    y0 = 200
    for r in range(rows):
        for c in range(cols):
            if missing == (r, c):
                continue
            x, y = x0 + c * (side + gap), y0 + r * (side + 80)
            colour = _layout_np.array(_TRAY_SHADES[r][c], float)
            pan = _layout_np.zeros((side, side, 3), float)
            pan[:] = colour
            if _TRAY_FINISHES[r][c] == "shimmer":
                yy, xx = _layout_np.mgrid[0:side, 0:side]
                t = _layout_np.clip(1.0 - (xx + yy) / (1.2 * side), 0, 1)[..., None]
                pan = pan + (255 - pan) * 0.5 * t
            if _TRAY_FINISHES[r][c] == "glitter":
                for _ in range(int(0.05 * side * side / 4)):
                    px, py = rnd.integers(2, side - 3, 2)
                    pan[py - 1:py + 2, px - 1:px + 2] = pan[py, px] + (255 - pan[py, px]) * 0.8
            img[y:y + side, x:x + side] = pan.clip(0, 255).astype(_layout_np.uint8)
            _layout_cv2.rectangle(img, (x - 2, y - 2), (x + side + 1, y + side + 1), (150, 140, 160), 2)   # its well's rim
            _layout_cv2.putText(img, "SHADE %d" % (r * cols + c + 1), (x + 10, y + side + 40), _layout_cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (110, 70, 120), 2)
    ok, png = _layout_cv2.imencode(".png", img)
    return png.tobytes()


def _tray_lab(bgr):
    lab = _layout_cv2.cvtColor(_layout_np.uint8([[bgr]]), _layout_cv2.COLOR_BGR2LAB)[0, 0].astype(float)
    return _layout_np.array([lab[0] * 100 / 255, lab[1] - 128, lab[2] - 128])


def test_goal_1011_tray_the_picture_is_read_into_his_grid_each_pan_its_colour_and_finish():
    """The open palette's picture read at $0: its 18 pans found in his 3 rows of 6, each pan's colour its own middle's
    (within ΔE 6 of the shade drawn, a sheen's within ΔE 14) and its finish read from its texture — matte flat, shimmer
    a sheen across it, glitter bright specks — every one right."""
    from apps.pipeline.targets.container import tray_picture as TP
    rec = TP.read_tray_picture(_tray_png(), 3, 6)
    assert rec["state"] == TP.READ and len(rec["pans"]) == 3 and all(len(row) == 6 for row in rec["pans"])
    for r in range(3):
        for c in range(6):
            pan = rec["pans"][r][c]
            assert pan["finish"] == _TRAY_FINISHES[r][c], (r, c, pan)
            got = _tray_lab(tuple(int(pan["hex"][i:i + 2], 16) for i in (5, 3, 1)))
            near = 14.0 if _TRAY_FINISHES[r][c] == "shimmer" else 6.0
            assert _layout_np.linalg.norm(got - _tray_lab(_TRAY_SHADES[r][c])) < near, (r, c, pan["hex"])


def test_goal_1011_tray_a_picture_not_showing_his_grid_is_refused_and_each_pan_says_its_source():
    """A picture with a pan missing is REFUSED by name, never fitted to his grid; then every pan takes its name's finish
    and the concept's palette, each said by its source — never grey; read, each says the tray picture."""
    from apps.pipeline.targets.container import tray_picture as TP
    bad = TP.read_tray_picture(_tray_png(missing=(1, 2)), 3, 6)
    assert (bad["state"], bad["code"]) == (TP.REFUSED, TP.TRAY_NOT_READ) and "18 pans in 3 rows of 6" in bad["why"]
    tray = {"rows": 3, "cols": 6, "shape": "square", "names": [["Petal Frost", "Moonlit Rose", "Fairy Dust", "Rosewater",
            "Wild Rose", "Velvet Bloom"], ["Lilac Mist", "Gilded Petal", "Spellbound", "Enchanted", "Twilight", "Briar"],
            ["Dusk Garden", "Mystic", "Thorn", "Nightshade", "Eternal", "Midnight Bloom"]]}
    palette = ["#F5D0DC", "#A8D8D8", "#C8A8D8"]
    named = TP.pans_for(tray, bad, palette)
    assert all(p["source"] == TP.FROM_NAME and p["hex"] in palette for row in named for p in row)
    assert (named[0][0]["finish"], named[0][2]["finish"], named[1][1]["finish"], named[2][2]["finish"]) == (
        TP.SHIMMER, TP.GLITTER, TP.SHIMMER, TP.MATTE)               # Petal Frost, Fairy Dust, Gilded Petal, Thorn
    read = TP.pans_for(tray, TP.read_tray_picture(_tray_png(), 3, 6), palette)
    assert all(p["source"] == TP.FROM_PICTURE and p["hex"] != "#D8D2CF" for row in read for p in row)
    assert read[2][5]["name"] == "Midnight Bloom" and read[2][5]["finish"] == TP.GLITTER


class TrayPictureTests(TestCase):
    """[His test blocker on design 124, (5)] the open palette's picture: made once from the chosen concept, his grid and
    his shades' names asked for, kept on the concept, never paid again; a refusal said by name."""

    def setUp(self):
        media = _layout_tempfile.mkdtemp(prefix="tray_")
        self.addCleanup(_layout_shutil.rmtree, media, True)
        self.enterContext(override_settings(MEDIA_ROOT=media, OPENAI_API_KEY="test"))
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(brand=brand, task_text="Enchanted Rose palette",
                                              design_target="product_container", status="gate_1_approved")
        self.image = GeneratedImage.objects.create(task=self.task, direction_name="Arch & Bloom", prompt_used="p",
                                                   variation_number=1)
        self.image.image_file.save("arch.png", ContentFile(_layout_png(_layout_np.full((64, 48, 3), 200, _layout_np.uint8))))
        self.aria = _layout_mock.MagicMock(task=self.task)
        self.tray = {"rows": 3, "cols": 6, "shape": "square",
                     "names": [["Petal Frost"] * 6, ["Lilac Mist"] * 6, ["Midnight Bloom"] * 6]}

    def test_goal_1011_tray_the_open_palette_is_drawn_once_his_grid_and_names_asked_for_and_kept(self):
        from apps.pipeline.targets.container import tray_picture as TP
        data = _layout_mock.MagicMock(b64_json=_layout_b64.b64encode(_tray_png()).decode())
        with _layout_mock.patch("openai.images.edit",
                                return_value=_layout_mock.MagicMock(data=[data], _request_id="r")) as edit:
            rec = TP.ensure_tray(self.aria, self.image, self.tray)
        assert rec["state"] == TP.MADE and edit.call_count == 1 and edit.call_args.kwargs["size"] == TP.TRAY_SIZE
        said = edit.call_args.kwargs["prompt"]
        assert said.startswith(TP.TRAY_WORDS) and "18 square pans in 3 rows of 6" in said and "Midnight Bloom" in said
        assert ApiCallRecord.objects.filter(task=self.task, operation="image:open tray:Arch & Bloom").count() == 1
        self.image.refresh_from_db()
        assert TP.kept_tray(self.image) == rec and TP.tray_bytes(rec) == _tray_png()
        with _layout_mock.patch("openai.images.edit", side_effect=AssertionError("paid again")):
            assert TP.ensure_tray(self.aria, self.image, self.tray) == rec
        with _layout_mock.patch("openai.images.edit", side_effect=RuntimeError("upstream 500")):
            self.image.image_file.save("other.png", ContentFile(_layout_png(_layout_np.full((64, 48, 3), 9, _layout_np.uint8))))
            refused = TP.ensure_tray(self.aria, self.image, self.tray)
        assert (refused["state"], refused["code"]) == (TP.REFUSED, TP.TRAY_NOT_MADE) and "upstream 500" in refused["why"]


def test_goal_1011_tray_the_real_picture_each_pan_its_finish_read_from_its_grain_and_its_flakes():
    """[His test blocker on design 124, (5): "Every pan gets a real shade colour and finish (matte / shimmer / glitter),
    from that picture"] 124's own open palette (fixtures_124/tray_153.png, drawn from his chosen "Arch & Bloom") read in
    his 3 rows of 6, each pan's finish as the picture shows it — the executor's reading of the picture, pan by pan: its
    eight flat pans matte; its fine-grained ones shimmer, Wild Rose, Spellbound, Twilight and Nightshade among them (the
    bright-speck count read those four matte); the two flaked with light and colour, Fairy Dust and Eternal, glitter —
    and no two pans one colour (ΔE above 3 between every pair), none the grey the tray was drawn in."""
    import os
    from apps.pipeline.targets.container import tray_picture as TP
    with open(os.path.join(os.path.dirname(__file__), "fixtures_124", "tray_153.png"), "rb") as fh:
        rec = TP.read_tray_picture(fh.read(), 3, 6)
    assert rec["state"] == TP.READ, rec.get("why")
    seen = [[TP.SHIMMER, TP.SHIMMER, TP.GLITTER, TP.MATTE, TP.SHIMMER, TP.MATTE],      # Petal Frost … Velvet Bloom
            [TP.MATTE, TP.SHIMMER, TP.SHIMMER, TP.MATTE, TP.SHIMMER, TP.MATTE],        # Lilac Mist … Briar
            [TP.MATTE, TP.SHIMMER, TP.MATTE, TP.SHIMMER, TP.GLITTER, TP.MATTE]]        # Dusk Garden … Midnight Bloom
    assert [[p["finish"] for p in row] for row in rec["pans"]] == seen, [[p["measures"] for p in row] for row in rec["pans"]]
    hexes = [p["hex"] for row in rec["pans"] for p in row]
    labs = [_tray_lab(tuple(int(h[i:i + 2], 16) for i in (5, 3, 1))) for h in hexes]
    assert min(_layout_np.linalg.norm(a - b) for i, a in enumerate(labs) for b in labs[i + 1:]) > 3.0, hexes
    assert "#D8D2CF" not in hexes


def _registered_pictures():
    """A lid's concept as the map reads it — the drawn sky and roses, its small print on plain ground at its foot — and
    three redraws of it: faithful; a rose grown under the small print; its right rose gone (BGR, PNG bytes)."""
    import cv2
    _png, art = _lid_art_png()
    h, w = art.shape[:2]
    concept = art.copy()
    cv2.putText(concept, "18 SHADES - 27 g", (int(0.3 * w), int(0.965 * h)), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (120, 90, 140), 1, cv2.LINE_AA)
    grown = art.copy()
    cv2.ellipse(grown, (int(0.5 * w), int(0.955 * h)), (60, 16), 0, 0, 360, (150, 90, 210), -1)   # a rose laid low
    gone = art.copy()
    gone[int(0.45 * h):int(0.8 * h), int(0.62 * w):] = art[int(0.45 * h):int(0.8 * h), int(0.62 * w) - 1:int(0.62 * w)]
    enc = lambda im: cv2.imencode(".png", im)[1].tobytes()  # noqa: E731
    return enc(concept), enc(art), enc(grown), enc(gone)


_REGISTER_PARTS = [{"kind": "field", "name": "ground", "box": [0.0, 0.0, 1.0, 1.0]},
                   {"kind": "type", "name": "shade line", "box": [0.28, 0.92, 0.72, 0.99]},
                   {"kind": "illustration", "name": "left rose", "box": [0.05, 0.45, 0.32, 0.8]},
                   {"kind": "illustration", "name": "right rose", "box": [0.65, 0.45, 0.95, 0.8]}]


def test_goal_1011_illustration_the_redraw_is_checked_against_the_lids_map_part_by_part_before_it_is_drawn():
    """[His test blocker on design 124, (2) "self-check" and (4) "stop and tell me which part and why"] the redraw laid
    filling the lid, checked at $0 against the map's parts: faithful, REGISTERED, each box measured; a rose grown under
    the small print the concept keeps on plain ground REFUSED, naming the line of type; a rose the concept draws and the
    redraw leaves out REFUSED, naming the rose — never drawn misplaced."""
    from apps.pipeline.targets.container import lid_art as LA
    concept, art, grown, gone = _registered_pictures()
    ok = LA.registration(art, concept, _REGISTER_PARTS, False)
    assert ok["state"] == LA.REGISTERED and ok["parts"] == [] and set(ok["boxes"]) == {"shade line", "left rose",
                                                                                      "right rose"}
    assert ok["boxes"]["shade line"]["art"] == 0.0 and ok["boxes"]["right rose"]["art"] > 0.15
    bad = LA.registration(grown, concept, _REGISTER_PARTS, False)
    assert (bad["state"], bad["code"]) == (LA.REFUSED, LA.ART_NOT_REGISTERED)
    assert [(p["kind"], p["name"]) for p in bad["parts"]] == [("type", "shade line")]
    assert "grows its illustration under it" in bad["why"] and "shade line" in bad["why"]
    lost = LA.registration(gone, concept, _REGISTER_PARTS, False)
    assert lost["state"] == LA.REFUSED and [p["name"] for p in lost["parts"]] == ["right rose"]
    assert LA.registration(b"", concept, _REGISTER_PARTS, False)["state"] == LA.REFUSED


def test_goal_1011_illustration_124s_first_redraw_is_refused_where_its_roses_grow_under_the_small_print():
    """124's own first redraw (fixtures_124/lid_art_153_first.png, lid-art-1: the lid sent at its own 919 x 725, asked
    at 1536 x 1024) against its concept's lid (concept_153.png, stood square) and its lid's map (lid_map_153.json, the
    read on record): laid filling the lid its arch, its rose clusters and its petals stand where the concept's do, its
    title, subtitle and mark on plain ground — and its roses and leaves grown under the two lines of small print at its
    foot, which the concept prints on plain ground: REFUSED, naming those two lines and no other part; its second redraw
    (lid_art_153.png), sent filling the frame, REGISTERED."""
    import json
    import os

    from apps.pipeline.services import concept_outline as co
    from apps.pipeline.targets.container import lid_art as LA
    here = os.path.join(os.path.dirname(__file__), "fixtures_124")
    with open(os.path.join(here, "concept_153.png"), "rb") as fh:
        lid = co.lid_picture(fh.read())
    with open(os.path.join(here, "lid_art_153_first.png"), "rb") as fh:
        first = fh.read()
    with open(os.path.join(here, "lid_map_153.json"), encoding="utf-8") as fh:
        parts = json.load(fh)["parts"]
    assert lid["state"] == co.LID_STRAIGHTENED
    reg = LA.registration(first, lid["png"], parts, False)
    assert (reg["state"], reg["code"]) == (LA.REFUSED, LA.ART_NOT_REGISTERED)
    assert sorted(p["name"] for p in reg["parts"]) == ["Arabic product line", "shade count and weight"]
    assert reg["boxes"]["Enchanted Rose title"]["art"] < 0.1 and reg["boxes"]["BBROSE logo"]["art"] < 0.1
    for name in ("gold ogee arch with glow", "left rose cluster with buds and leaves",
                 "right rose cluster with buds and leaves", "scattered petals along base"):
        assert abs(reg["boxes"][name]["art"] - reg["boxes"][name]["concept"]) < 0.12, (name, reg["boxes"][name])
    # its second redraw (lid_art_153.png, lid-art-2: the lid sent filling the frame), the one drawn: REGISTERED, the
    # ground under its small print plain
    with open(os.path.join(here, "lid_art_153.png"), "rb") as fh:
        second = LA.registration(fh.read(), lid["png"], parts, False)
    assert second["state"] == LA.REGISTERED and second["parts"] == []
    assert second["boxes"]["shade count and weight"]["art"] < 0.05 and second["boxes"]["Arabic product line"]["art"] < 0.05


# ---- [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2)-(5): ONE
# ---- ENGINE for palettes and compacts; their illustration redrawn flat and traced in colour; NO SILENT FALLBACK; the
# ---- open tray's pans from one more picture, listed for him]

def _closed_palette_png():
    """A closed palette's concept as the image model draws it from above, a little off square on a dark ground: its
    pink lid with a lilac-to-teal sky, a teal arch and two deep-rose flowers (BGR)."""
    import cv2
    import numpy as _np
    w, h = 460, 300
    lid = _np.zeros((h, w, 3), _np.float32)
    for yy in range(h):
        lid[yy] = _np.float32((201, 170, 190)) + (_np.float32((190, 180, 234)) - _np.float32((201, 170, 190))) * yy / h
    lid = lid.astype(_np.uint8)
    cv2.ellipse(lid, (w // 2, h), (w // 4, int(h * 0.7)), 0, 180, 360, (190, 200, 120), 6)
    for cx in (w // 5, 4 * w // 5):
        cv2.circle(lid, (cx, int(h * 0.7)), 30, (150, 90, 210), -1)
    size = (640, 960)
    cx0, cy0 = size[0] // 2, size[1] // 2
    dst = _np.float32([[cx0 - w / 2 + 5, cy0 - h / 2], [cx0 + w / 2 - 3, cy0 - h / 2 + 2], [cx0 + w / 2, cy0 + h / 2],
                       [cx0 - w / 2, cy0 + h / 2 - 2]])
    warp = cv2.getPerspectiveTransform(_np.float32([[0, 0], [w, 0], [w, h], [0, h]]), dst)
    canvas = _np.full((size[1], size[0], 3), 60, _np.uint8)
    inside = cv2.warpPerspective(_np.full((h, w), 255, _np.uint8), warp, size) > 127
    canvas[inside] = cv2.warpPerspective(lid, warp, size, flags=cv2.INTER_CUBIC)[inside]
    ok, png = cv2.imencode(".png", canvas)
    return png.tobytes()


class CompactOneEngineTests(TestCase):
    """[His test blocker on design 124, (2)-(5)] a palette on the one map-first engine: its map read from its lid stood
    square, its illustration counted as drawn by its art, its art made once and kept where the lid is drawn — and every
    refusal a stop at Gate 1, by name, with his options."""

    def setUp(self):
        import tempfile
        media = tempfile.mkdtemp(prefix="compact_")
        self.addCleanup(__import__("shutil").rmtree, media, True)
        self.enterContext(override_settings(MEDIA_ROOT=media, OPENAI_API_KEY="test"))
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(brand=brand, task_text="Enchanted Rose eyeshadow palette, 190 x 120 mm",
                                              design_target="product_container", status="gate_1_approved")
        self.image = GeneratedImage.objects.create(task=self.task, direction_name="Arch & Bloom", prompt_used="p",
                                                   variation_number=1, is_approved=True)
        self.image.image_file.save("arch.png", ContentFile(_closed_palette_png()))
        from unittest import mock
        self.aria = mock.MagicMock(task=self.task)

    def _lid_record(self, lid_png):
        import hashlib

        from django.conf import settings

        from apps.pipeline.services import concept_design_map as dm
        return {"schema_version": dm.SCHEMA, "state": dm.MAP_READ, "read": dm.LID_READ,
                "source_sha256": hashlib.sha256(lid_png).hexdigest(), "face_box_px": [0, 0, 10, 10],
                "parts_prompt_version": dm.LID_PARTS_PROMPT_VERSION, "model": settings.CLAUDE_MODEL_HEAVY,
                "parts": [{"kind": "field", "name": "pink lid ground", "box": [0, 0, 1, 1], "colour": "#EAB6C4"},
                          {"kind": "illustration", "name": "rose arch", "box": [0.1, 0.3, 0.9, 1.0],
                           "colour": "#D25A96"}],
                "problems": [], "cost": {"usd": "0.090000", "calls": 1}}

    def test_goal_1011_one_engine_a_compacts_map_is_read_from_its_lid_stood_square_and_kept(self):
        """A compact's map is read from its lid stood square — never skipped as a face form's was — and kept: chosen
        again, nothing is paid; its illustration is drawn by its art in the one check, every other form's picture as it
        stands."""
        from unittest import mock

        from django.test import override_settings

        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.services import concept_outline as co
        from apps.pipeline.targets import container as C
        lid = co.lid_picture(_closed_palette_png())
        assert C._map_bytes(self.image, "compact") == lid["png"]
        assert C._map_bytes(self.image, "tube") == _closed_palette_png()
        record = self._lid_record(lid["png"])
        with override_settings(DESIGN_MAP_READ=True, ANTHROPIC_API_KEY="k"), \
                mock.patch.object(dm, "read_lid_parts", return_value=record) as paid:
            got = C._read_design_map(self.aria, "compact", self.image)
        assert got == record and paid.call_args[0][1] == lid["png"]
        self.image.reference_provenance = {dm.SCHEMA: record}
        self.image.save()
        with override_settings(DESIGN_MAP_READ=True, ANTHROPIC_API_KEY="k"), \
                mock.patch.object(dm, "read_lid_parts", side_effect=AssertionError("paid again")):
            assert C._read_design_map(self.aria, "compact", self.image) == record
        verdict = C.drawable_verdict(self.task, record, lid["png"])
        assert verdict["shapes"]["illustrations"] == [
            {"part": "rose arch", "drawn_by": "the lid's art, redrawn flat and traced in colour"}]
        assert verdict["shapes"]["state"] == dm.SHAPES_TRACED
        assert not [u for u in verdict["undrawn"] or [] if u["kind"] == "illustration"]

    def test_goal_1011_no_fallback_a_lid_whose_art_cannot_be_made_stops_at_gate_one_with_his_options(self):
        """Where the lid's illustration cannot be redrawn flat, the design stops at Gate 1 — the illustration named, why,
        and his three options — never the lid drawn from its form's own layout instead."""
        from unittest import mock

        from apps.pipeline.models import PackagingOutput
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets import container as C
        from apps.pipeline.services import concept_outline as co
        lid = co.lid_picture(_closed_palette_png())
        out = PackagingOutput.objects.create(task=self.task, approved_image=self.image, spec_sheet={
            dm.SCHEMA: self._lid_record(lid["png"]), "container_profile": {"archetype": "compact"},
            "container_profile/1.0": {"archetype": "compact", "fields": {"body_width_mm": {"value": 190.0},
                                                                         "body_height_mm": {"value": 120.0}}}})
        from apps.pipeline.agents.aria import ARIAAgent
        aria = ARIAAgent(self.task.id)
        with mock.patch("openai.images.edit", side_effect=RuntimeError("upstream 500")):
            assert C.lid_art_or_stop(aria, out, "compact") is None
        self.task.refresh_from_db()
        self.image.refresh_from_db()
        stop = self.image.reference_provenance[dm.MAP_STOP_KEY]
        assert self.task.status == "awaiting_gate_1" and self.image.is_approved is False
        assert stop["why"].startswith("its illustration could not be redrawn flat") and "upstream 500" in stop["why"]
        assert stop["parts"][0]["kind"] == "illustration" and stop["parts"][0]["name"] == "rose arch"
        assert stop["options"] == list(dm.STOP_OPTIONS) and stop["concept"] is False

    def test_goal_1011_no_fallback_a_lid_drawn_from_its_art_is_made_once_and_kept(self):
        """Where it can be made, the lid's art is made once at the size he confirmed and traced in colour; drawn again,
        it is read from the kept redraw — nothing paid, nothing made."""
        import base64
        from unittest import mock

        from apps.pipeline.models import PackagingOutput
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.services import concept_outline as co
        from apps.pipeline.targets import container as C
        from apps.pipeline.targets.container import lid_art as LA
        lid = co.lid_picture(_closed_palette_png())
        out = PackagingOutput.objects.create(task=self.task, approved_image=self.image, spec_sheet={
            dm.SCHEMA: self._lid_record(lid["png"]), "container_profile": {"archetype": "compact"},
            "container_profile/1.0": {"archetype": "compact", "fields": {"body_width_mm": {"value": 190.0},
                                                                         "body_height_mm": {"value": 120.0}}}})
        def faithful(**kw):                    # the image model keeping the lid it was sent, as asked
            data = mock.MagicMock(b64_json=base64.b64encode(kw["image"][0][1]).decode())
            return mock.MagicMock(data=[data], _request_id="r")
        with mock.patch("openai.images.edit", side_effect=faithful) as edit:
            traced = C.lid_art_or_stop(self.aria, out, "compact")
        assert traced["state"] == LA.TRACED and edit.call_args.kwargs["size"] == "1536x1024"
        assert "palette's lid" in edit.call_args.kwargs["prompt"]
        assert traced["registration"]["state"] == LA.REGISTERED and "rose arch" in traced["registration"]["boxes"]
        self.image.refresh_from_db()
        assert LA.kept_lid_art(self.image)["registration"]["state"] == LA.REGISTERED      # kept with its redraw
        self.image.refresh_from_db()
        with mock.patch("openai.images.edit", side_effect=AssertionError("paid again")):
            assert C.kept_lid_art_trace(self.image, "compact")["regions"] == traced["regions"]
        assert C.kept_lid_art_trace(self.image, "tube") is None

    def test_goal_1013_never_stops_a_redraw_not_standing_where_the_concept_does_goes_on_naming_its_parts(self):
        """[His blocker (2) "self-check"; his goal of 2026-10-13, (1): "NO check ever stops a design"] a redraw that grows a
        rose under the small print the concept prints on plain ground is never drawn — and the design goes on: the lid
        drawn without its illustration, the line of type named with why beside Approve, with what he can do."""
        import base64
        from unittest import mock

        import cv2
        import numpy as _np

        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.models import PackagingOutput
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.services import concept_outline as co
        from apps.pipeline.targets import container as C
        lid = co.lid_picture(_closed_palette_png())
        record = self._lid_record(lid["png"])
        record["parts"].append({"kind": "type", "name": "shade line", "box": [0.3, 0.9, 0.7, 0.99], "colour": "#7A5A8C"})
        out = PackagingOutput.objects.create(task=self.task, approved_image=self.image, spec_sheet={
            dm.SCHEMA: record, "container_profile": {"archetype": "compact"},
            "container_profile/1.0": {"archetype": "compact", "fields": {"body_width_mm": {"value": 190.0},
                                                                         "body_height_mm": {"value": 120.0}}}})

        def grown(**kw):                       # the lid redrawn with a rose laid under its small print
            img = cv2.imdecode(_np.frombuffer(kw["image"][0][1], _np.uint8), cv2.IMREAD_COLOR)
            h, w = img.shape[:2]
            cv2.ellipse(img, (w // 2, int(0.945 * h)), (w // 7, h // 20), 0, 0, 360, (150, 90, 210), -1)
            data = mock.MagicMock(b64_json=base64.b64encode(cv2.imencode(".png", img)[1].tobytes()).decode())
            return mock.MagicMock(data=[data], _request_id="r")
        aria = ARIAAgent(self.task.id)
        status = self.task.status
        with mock.patch("openai.images.edit", side_effect=grown):
            # [his review of 127-132, C (4)-(5), and his goal after the pitch page, B (11)] drawn on WITH its art — every
            # element of the concept drawn, never a stop — what its check saw said beside Approve
            drawn = C.lid_art_or_stop(aria, out, "compact")
        assert drawn and drawn["regions"] and drawn["registration"]["state"] == "REFUSED"
        self.task.refresh_from_db()
        self.image.refresh_from_db()
        out.refresh_from_db()
        assert self.task.status == status and dm.MAP_STOP_KEY not in (self.image.reference_provenance or {})
        rows = out.spec_sheet["checks_shown/1.0"]
        assert len(rows) == 1 and rows[0]["what"].startswith(
            "the lid's illustration is drawn as it was redrawn, but its flat redraw does not stand exactly where")
        assert "shade line" in rows[0]["what"] and rows[0]["options"] == list(C.LID_ART_OPTIONS)
        from apps.pipeline.targets.container import lid_art as LA
        assert LA.kept_lid_art(self.image)["registration"]["state"] == LA.REFUSED
        assert C.kept_lid_art_trace(self.image, "compact")["regions"]                    # and so by the loop

    def test_goal_1011_tray_the_kept_tray_picture_gives_every_pan_and_the_review_lists_them(self):
        """The open palette's picture kept on the concept is read into his grid at $0 and every pan carries its colour,
        finish and source; the Review Board lists them, row by row, for him to check."""
        import hashlib

        from django.core.files.base import ContentFile as _CF
        from django.core.files.storage import default_storage

        from apps.pipeline.targets import container as C
        from apps.pipeline.targets.container import tray_picture as TP
        self.task.task_text = ("Enchanted Rose eyeshadow palette, 18 square pans in 3 rows of 6.\nShade names:\n"
                               "Row 1: A1, A2, A3, A4, A5, A6.\nRow 2: B1, B2, B3, B4, B5, B6.\n"
                               "Row 3: C1, C2, C3, C4, C5, C6.\n")
        self.task.save()
        name = default_storage.save("concepts/tray_test.png", _CF(_tray_png()))
        with self.image.image_file.open("rb") as fh:
            concept = fh.read()
        self.image.reference_provenance = {TP.TRAY_KEY: {"state": TP.MADE, "file": name, "prompt_version":
                                                         TP.TRAY_PROMPT_VERSION,
                                                         "concept_sha256": hashlib.sha256(concept).hexdigest()}}
        self.image.save()
        records = []
        plan = C.palette_tray_plan(self.task, "compact", {"body": "#F6DCE6", "cap": "#EAB6C4", "ink": "#6B3A5A",
                                                          "motif": ["#F4B8CF"]}, records, image=self.image)
        assert all(p["source"] == TP.FROM_PICTURE for row in plan["pans"] for p in row)
        assert plan["pans"][0][0]["name"] == "A1" and plan["pans"][2][5]["finish"] == _TRAY_FINISHES[2][5]
        assert any(key == TP.TRAY_READ_KEY for _op, key, _v in records)
        rows = C._tray_rows({C.TRAY_PANS_KEY: plan["pans"]})
        assert [r["label"] for r in rows] == ["Tray, row 1", "Tray, row 2", "Tray, row 3"]
        assert rows[0]["value"].startswith("A1 — #") and "(from the tray picture)" in rows[0]["value"]


class CompactConceptCheckTests(TestCase):
    """[His test blocker on design 124, (2): "ONE ENGINE"] a palette's concepts checked before they are shown, as every
    form's are — each read from its lid stood square; a lid its trace cannot cut from its ground redrawn once on a
    plain backdrop and checked again — they were skipped, their lids drawn from their own reading."""

    def setUp(self):
        import tempfile
        media = tempfile.mkdtemp(prefix="compact_check_")
        self.addCleanup(__import__("shutil").rmtree, media, True)
        self.enterContext(override_settings(MEDIA_ROOT=media, OPENAI_API_KEY="test"))
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(
            brand=brand, design_target="product_container", status="running",
            task_text="Enchanted Rose eyeshadow palette.\n\n[Container type: Compact; Closure: Magnetic lid]")
        self.image = GeneratedImage.objects.create(task=self.task, direction_name="Arch & Bloom", prompt_used="p",
                                                   variation_number=1)
        self.image.image_file.save("arch.png", ContentFile(_closed_palette_png()))
        from unittest import mock
        self.aria = mock.MagicMock(task=self.task)

    def test_goal_1011_one_engine_each_palette_concept_is_read_from_its_lid_before_it_is_shown(self):
        import hashlib
        from unittest import mock

        from django.conf import settings
        from django.test import override_settings

        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.services import concept_outline as co
        from apps.pipeline.targets.container import form_of_task, readable
        assert form_of_task(self.task) == "compact"
        lid = co.lid_picture(_closed_palette_png())
        record = {"schema_version": dm.SCHEMA, "state": dm.MAP_READ, "read": dm.LID_READ,
                  "source_sha256": hashlib.sha256(lid["png"]).hexdigest(), "face_box_px": [0, 0, 10, 10],
                  "parts_prompt_version": dm.LID_PARTS_PROMPT_VERSION, "model": settings.CLAUDE_MODEL_HEAVY,
                  "parts": [{"kind": "field", "name": "pink lid ground", "box": [0, 0, 1, 1], "colour": "#EAB6C4"},
                            {"kind": "illustration", "name": "rose arch", "box": [0.1, 0.3, 0.9, 1.0],
                             "colour": "#D25A96"}],
                  "problems": [], "cost": {"usd": "0.090000", "calls": 1}}
        with override_settings(DESIGN_MAP_READ=True, ANTHROPIC_API_KEY="k"), \
                mock.patch.object(dm, "read_lid_parts", return_value=record) as paid:
            counts = readable.check_concepts(self.aria, [self.image])
        assert counts == {"drawable": 1, "redrawn": 0, "not_drawable": 0, "unchecked": 0}
        assert paid.call_args[0][1] == lid["png"]                                # its lid, stood square
        self.image.refresh_from_db()
        assert self.image.reference_provenance[dm.SCHEMA] == record              # kept: approval pays nothing again



class FlatLayoutPictureTests(TestCase):
    """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (2): "A palette or compact lies flat: its box's front is the
    lid's face (landscape). Use each container's real orientation for every form."] The layout picture of a box lying
    flat asked for as it lies; a picture drawn for the box standing never laid on it; one not made said, with why."""
    setUp = LayoutPictureTests.setUp
    _kept_sheet = LayoutPictureTests._kept_sheet

    def test_goal_1013_orientation_a_box_lying_flat_is_asked_for_as_it_lies(self):
        flat = dict(LAYOUT_DIMS, orientation="flat")
        said = _CL.layout_prompt(flat)
        assert "ONE column of four wide panels" in said and "2.2 times as wide as the front is tall" in said
        assert said != _CL.layout_prompt(LAYOUT_DIMS) and _CL.lies_flat(flat) and not _CL.lies_flat(LAYOUT_DIMS)
        for noun in ("tube", "bottle", "jar", "box", "carton"):
            assert noun not in said.lower().split(), noun

    def test_goal_1013_orientation_a_picture_for_the_box_standing_is_never_laid_on_it_lying_flat(self):
        from apps.pipeline.services import cost_ledger
        read, aria = self._kept_sheet()                                    # drawn and read for the box standing
        flat = dict(LAYOUT_DIMS, orientation="flat")
        assert _CL.kept_layout(self.image, LAYOUT_DIMS) is not None and _CL.kept_layout_read(self.image, LAYOUT_DIMS)
        assert _CL.kept_layout(self.image, flat) is None and _CL.kept_layout_read(self.image, flat) is None
        # [re-pinned by his goal for the pitch, 2026-10-15, B (6): "NEVER DEGRADE TO SAVE MONEY ... Pay for what
        # fidelity needs."] this design's spending held at $0: the layout picture its drawing needs is still asked for
        # — paid for, never left out to save money
        self.task.options = {"spend_held": True}
        self.task.save(update_fields=["options"])
        unmade = []
        with cost_ledger.task_cost_context(self.task), \
                _layout_mock.patch("openai.images.edit", side_effect=AssertionError("paid")) as edit:
            try:
                _CL.ensure_layout(aria, self.image, flat, said=unmade)
            except AssertionError:
                pass
        assert edit.called                                     # asked for, never held at $0
        logged = " ".join(str(c[0][0]) for c in aria.log.call_args_list)
        assert "drawn for the box lying otherwise" in logged and "held at $0" not in logged


class PitchGoalQualityTests(TestCase):
    """[His goal for the pitch, 2026-10-15 (OWNER_BLOCKER_CLEARANCE.md), B: "QUALITY (from my review of the 124–126
    report)"] the designer's eye, fidelity paid for, a motif's own colours, the dropper from its concept, the gilded
    line in its two tones."""

    @staticmethod
    def _png(draw):
        img = _layout_np.full((300, 300, 3), (200, 210, 245), _layout_np.uint8)      # a blush ground (BGR)
        draw(img)
        ok, buf = _layout_cv2.imencode(".png", img)
        return buf.tobytes()

    def test_b7_a_one_ink_hairline_motif_keeps_its_purest_ink_and_an_illustrated_one_its_colours(self):
        from apps.pipeline.services import flat_motif as fm
        hair = self._png(lambda im: [_layout_cv2.line(im, (20, 20 + 12 * k), (280, 40 + 12 * k), (40, 40, 170), 2,
                                                      _layout_cv2.LINE_AA) for k in range(18)])
        one = fm.trace_flat(hair, [0.1, 0.1, 0.9, 0.9], (40, 40))
        self.assertIsNone(one.get("art"))                     # its anti-aliased edge is no second colour
        r, g, b = (int(one["ink"][i:i + 2], 16) for i in (1, 3, 5))
        self.assertGreater(r, 120)
        self.assertLess(g, 90)                                # red, never the pink of its soft edge
        two = self._png(lambda im: (_layout_cv2.circle(im, (100, 150), 70, (40, 160, 40), -1),
                                    _layout_cv2.circle(im, (210, 150), 60, (30, 180, 230), -1)))
        art = fm.trace_flat(two, [0.1, 0.1, 0.9, 0.9], (40, 40))
        self.assertEqual(art["state"], fm.TRACED)
        self.assertTrue(art.get("art") and art["art"]["regions"])
        self.assertGreaterEqual(len(art["colours"]), 2)

    def test_b6_a_call_fidelity_needs_is_never_held_at_zero(self):
        from apps.pipeline.services import cost_ledger as cl
        from types import SimpleNamespace
        task = SimpleNamespace(options={"spend_held": True})
        token = cl._current_task.set(task)
        try:
            with self.assertRaises(cl.BudgetExceededError):
                cl.before_paid_call("a concept picture")
            cl.before_paid_call("a picture", fidelity=True)          # a motif's or a lid's redraw: paid for
            with cl.fidelity_call("designers_eye"):
                cl.before_paid_call("a written answer")
            with cl.fidelity_call("creative_directions"), self.assertRaises(cl.BudgetExceededError):
                cl.before_paid_call("a written answer")
        finally:
            cl._current_task.reset(token)

    def test_b5_the_designers_eye_fixes_a_colour_it_has_a_lever_for_and_says_what_is_left(self):
        import json
        from apps.ire.graph import Color, Document, Group, Path, MoveTo, LineTo, ClosePath, SolidFill
        from apps.pipeline.services import designers_eye as eye
        doc = Document(page_w=50, page_h=50, root=Group(name="root", children=[
            Path(name="rose", segments=[MoveTo(x=0, y=0), LineTo(x=10, y=0), LineTo(x=10, y=10), ClosePath()],
                 fill=SolidFill(color=Color.from_hex("#3A2A2C")))]))
        answers = [{"matches": False, "summary": "the rose is brown",
                    "differences": [{"kind": "colour", "part": "rose", "concept": "gold", "drawing": "brown",
                                     "severity": "major", "fix": {"lever": "recolour", "drawing_hex": "#3B2B2B",
                                                                  "concept_hex": "#D4A437"}},
                                    {"kind": "missing part", "part": "30 ml", "concept": "30 ml", "drawing": "none",
                                     "severity": "blocking", "fix": {"lever": "none"}}]},
                   {"matches": False, "summary": "the volume is missing",
                    "differences": [{"kind": "missing part", "part": "30 ml", "concept": "30 ml", "drawing": "none",
                                     "severity": "blocking", "fix": {"lever": "none"}}]}]
        seen = []

        def call(system, content):
            seen.append(content)
            return json.dumps(answers[(len(seen) - 1) // 2])       # [A (7)] each round looks twice
        record = eye.check(self._png(lambda im: None), lambda: self._png(lambda im: None), doc, call=call)
        self.assertEqual(record["state"], "DIFFERS")                 # PASS only where it matches the concept
        self.assertEqual(doc.root.children[0].fill.color.to_hex().upper(), "#D4A437")
        self.assertEqual(len(record["fixed"]), 1)
        self.assertEqual([d["part"] for d in record["left"]], ["30 ml"])
        self.assertIn("30 ml", eye.shown(record)[0]["what"])
        self.assertEqual(len(seen), 4)                              # looked twice again after its fix, then stopped
        self.assertEqual([c["type"] for c in seen[0]][:4], ["text", "image", "text", "image"])
        self.assertEqual(eye.shown({"state": "PASS"}), [])

    def test_a7_the_eye_checks_five_things_by_name_and_reports_what_two_looks_agree_on(self):
        import json
        from apps.pipeline.services import designers_eye as eye
        for name in ("shape", "font", "metal", "completeness", "contrast"):
            self.assertIn('"%s"' % name, eye.SYSTEM)
        clean = {name: {"same": True, "note": ""} for name in eye.CHECKS}
        sans = dict(clean, font={"same": False, "note": "the name is a serif in the concept, a sans here"})
        said = {"matches": False, "summary": "the type is wrong", "checks": sans, "differences": [
            {"check": "font", "kind": "font", "part": "product name", "concept": "serif", "drawing": "sans",
             "severity": "major", "fix": {"lever": "none"}},
            {"check": "other", "kind": "size or position", "part": "tagline", "concept": "low", "drawing": "high",
             "severity": "minor", "fix": {"lever": "none"}}]}
        passed = {"matches": True, "summary": "fine", "checks": clean, "differences": []}
        # the first two looks disagree on the type: a third breaks the tie, and the difference two saw is reported
        answers = [said, passed, dict(said, differences=said["differences"][:1])]
        seen = []

        def call(system, content):
            seen.append(1)
            return json.dumps(answers[len(seen) - 1])
        record = eye.check(self._png(lambda im: None), lambda: self._png(lambda im: None), None, call=call)
        self.assertEqual(len(seen), 3)
        self.assertEqual(record["state"], "DIFFERS")
        self.assertEqual([d["part"] for d in record["left"]], ["product name"])
        self.assertFalse(record["checks"]["font"]["same"])
        # one look's say-so is never reported: the minor offset two looks never agreed on is dropped
        self.assertEqual(record["minor"], [])
        # a look that says it matches while a check differs is read by its check
        sneaky = dict(passed, checks=dict(clean, metal={"same": False, "note": "the cap is flat tan"}))
        seen.clear()
        answers[:] = [sneaky, sneaky]
        record = eye.check(self._png(lambda im: None), lambda: self._png(lambda im: None), None, call=call)
        self.assertEqual(record["state"], "DIFFERS")
        self.assertIn("flat tan", " ".join(r["what"] for r in eye.shown(record)))
        # PASS only where two looks find all five the same
        seen.clear()
        answers[:] = [passed, passed]
        self.assertEqual(eye.check(self._png(lambda im: None), lambda: self._png(lambda im: None), None,
                                   call=call)["state"], "PASS")

    def test_a1_a_line_read_as_a_style_is_set_in_the_closest_granted_face(self):
        from apps.ire import lettering_faces as lf
        from apps.pipeline.services import concept_design_map as dm
        style = dm.type_style({"style": {"class": "Serif", "serif": "high-contrast", "weight": "bold",
                                         "italic": False, "case": "upper", "spacing": "wide", "width": "sideways"}})
        self.assertEqual(style, {"class": "serif", "serif": "high-contrast", "weight": "bold", "case": "upper",
                                 "spacing": "wide", "italic": False})       # a word outside the read's own is dropped
        for line, stem, weight in (
                ({"style": style}, "PlayfairDisplay[wght]", 700.0),
                ({"style": {"class": "serif", "serif": "old-style", "weight": "light", "italic": True}},
                 "CormorantGaramond-Italic[wght]", 300.0),
                ({"style": {"class": "sans", "width": "condensed", "weight": "medium"}}, "BarlowCondensed-Medium",
                 500.0),
                ({"style": {"class": "condensed", "weight": "bold"}}, "BarlowCondensed-Bold", 700.0),
                ({"style": {"class": "sans", "weight": "light"}}, "Jost[wght]", 300.0),
                ({"style": {"class": "sans", "width": "wide", "weight": "semibold"}}, "Montserrat[wght]", 600.0),
                ({"style": {"class": "serif", "serif": "flared"}}, "Marcellus-Regular", 400.0),
                # [his review of 127, 130, 131 and 132, C (6)] a tall condensed serif
                ({"style": {"class": "serif", "width": "condensed"}}, "InstrumentSerif-Regular", 400.0),
                ({"style": {"class": "condensed", "serif": "high-contrast", "weight": "bold"}}, "Gloock-Regular", 650.0),
                ({"lettering": "sans", "weight": "bold", "style": {"class": "serif"}}, "PlayfairDisplay[wght]", 700.0)):
            face = lf.choose(line)
            self.assertEqual((face["stem"], face["weight"]), (stem, weight), line)
        self.assertEqual(lf.choose({"style": style})["tracking_em"], lf.SPACING_EM["wide"])
        self.assertTrue(lf.choose({"style": style})["upper"])
        self.assertIsNone(lf.choose({"lettering": "display"}))              # matched by its outline first
        self.assertIsNone(lf.choose({"lettering": "arabic", "style": {"class": "sans"}}))
        self.assertIsNone(lf.choose({}))                                    # no reading: the role it had
        self.assertIsNone(lf.choose({"lettering": "serif", "weight": "bold"}))   # read before its style was asked
        self.assertIn("1", dm.EARLIER_READS_HELD[dm.PARTS_PROMPT_VERSION])   # ... and held, never paid for again

    def test_a1_a_name_read_as_a_granted_face_is_live_type_never_the_pictures_traced_letters(self):
        from types import SimpleNamespace
        from apps.ire import compose_container as cc
        traced = [[[0.2, 0.40], [0.8, 0.40], [0.8, 0.48], [0.2, 0.48]]]
        line = {"part": "product name", "words": "Tide Glass", "source": "brief", "ink": "#FFFFFF",
                "box": [0.2, 0.40, 0.8, 0.48], "outlines": traced, "match": 1.0,
                "style": {"class": "sans", "weight": "light", "case": "upper", "spacing": "very wide"}}
        zone = {"x": 0, "y": 0, "width": 40, "height": 100, "zone_id": "front"}
        group, _places, record = cc._map_type_group({"shapes": {"types": [line]}}, zone,
                                                    SimpleNamespace(width_mm=40.0, height_mm=100.0), 1.0, 0, 0,
                                                    name_font="bold", product_name="Tide Glass")
        runs = [k for k in group.children if getattr(k, "type", None) == "text"]
        self.assertTrue(runs and all(r.font.startswith("line-face:Jost") for r in runs))
        self.assertFalse(any(getattr(k, "name", "") == "product-name-traced" for k in group.children))
        self.assertEqual(record["typed"][0]["face"]["family"], "sans")

    def test_c6_a_line_traced_as_a_sliver_of_its_read_is_set_in_the_reads_box(self):
        # [his review of 127, 130, 131 and 132, C (6): "132's name is tiny"] a thin rule in the line's ink above its
        # letters is never the line
        from apps.pipeline.services import concept_design_map as dm
        img = _layout_np.full((400, 400, 3), 235, _layout_np.uint8)
        _layout_cv2.rectangle(img, (60, 150), (340, 152), (115, 62, 34), -1)          # a navy rule, 3 px
        _layout_cv2.putText(img, "CITRUS", (70, 220), _layout_cv2.FONT_HERSHEY_SIMPLEX, 2.4, (190, 160, 150), 6)
        mask = _layout_np.full((400, 400), 255, _layout_np.uint8)
        part = {"name": "title", "kind": "type", "box": [0.15, 0.37, 0.85, 0.57], "colour": "#223E73",
                "seen_text": "CITRUS", "lettering": "serif"}
        line = dm.trace_type(img, mask, (0, 0, 400, 400), part)
        self.assertEqual(line["box"], part["box"])
        self.assertIn("ink_sliver", line)

    def test_c5_a_printed_grain_the_map_reads_is_drawn_as_a_stipple_and_a_smooth_ground_gets_none(self):
        # [his review of 127-132, C (5): "131's sky grain ... Nothing simplified to hand-drawn flat"]
        from apps.ire import grain
        from apps.pipeline.targets.container import lid_art as la
        rng = _layout_np.random.default_rng(3)
        sky = _layout_np.zeros((300, 300, 3), _layout_np.uint8)
        for y in range(300):
            sky[y, :] = (200 - y // 4, 170 - y // 6, 120 + y // 4)
        grainy = _layout_np.clip(sky.astype(int) + rng.normal(0, 6, sky.shape[:2])[..., None], 0, 255).astype(
            _layout_np.uint8)
        png = lambda im: _layout_cv2.imencode(".png", im)[1].tobytes()
        got = grain.measure(png(grainy), [[0, 0, 1, 1]])
        self.assertTrue(got and got["tones"] and got["amplitude"] > grain.GRAIN["min_amplitude"])
        self.assertIsNone(grain.measure(png(sky), [[0, 0, 1, 1]]))          # a smooth sky: no grain added
        self.assertEqual(la.textured_boxes([{"texture": "grain", "box": [0, 0, 1, 0.5]}, {"texture": "none",
                                                                                         "box": [0, 0, 1, 1]}]),
                         [[0, 0, 1, 0.5]])
        trace = {"regions": [], "size_px": [300, 300], "grain": got}
        group = la.art_group(trace, 0, 0, 50, 50, ground=False)
        self.assertTrue(any(g.name == "lid-grain" and g.children for g in group.children))

    def test_c4_a_redraws_own_lettering_is_never_printed_under_the_live_words(self):
        # [his review of 127-132, C (4); the first brand-new brief, 134: its name and "EAU DE PARFUM" printed twice]
        from apps.pipeline.targets.container import lid_art as la
        sq = lambda x0, y0, x1, y1: [[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]]
        trace = {"regions": [{"fill": "#3A2A3A", "rings": sq(0, 0, 1, 1)},                # the ground: kept
                             {"fill": "#C8A050", "rings": sq(0.30, 0.41, 0.36, 0.45)},    # a letter the redraw kept
                             {"fill": "#C8A050", "rings": sq(0.10, 0.52, 0.90, 0.525)}],  # a rule under the name: kept
                 "lines": []}
        out = la.without_words(trace, [[0.2, 0.40, 0.8, 0.46]])
        self.assertEqual([r["fill"] for r in out["regions"] if not r.get("painted_out")], ["#3A2A3A", "#C8A050"])
        self.assertEqual(out["words_left_out"], 1)
        self.assertIs(la.without_words(trace, []), trace)
        # with the line's ink read: lettering in that ink left out from the padded box; a motif of its own colour
        # standing inside the name's box (a compact's flower beside its name) and a traced light line always kept
        trace = {"regions": [{"fill": "#3A2A3A", "rings": sq(0, 0, 1, 1)},
                             {"fill": "#C8A050", "rings": sq(0.30, 0.385, 0.36, 0.45)},   # a letter, its ink
                             {"fill": "#B0405A", "rings": sq(0.62, 0.40, 0.70, 0.46)}],   # a rose in the box: kept
                 "lines": [{"points": [[0.3, 0.42], [0.5, 0.43]]}]}
        out = la.without_words(trace, [[0.2, 0.40, 0.8, 0.46]], ["#C9A24F"])
        self.assertEqual([r["fill"] for r in out["regions"] if not r.get("painted_out")], ["#3A2A3A", "#B0405A"])
        self.assertEqual(out["lines"], trace["lines"])

    def test_b11_a_concept_picture_is_asked_again_when_the_connection_drops(self):
        # [his goal after the pitch page, B (11)] the first Complete Product's carton lost its trend-led concept to one
        # dropped connection
        from unittest import mock

        import httpx
        import openai
        from apps.pipeline.agents import image_producer as ip
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) == 1:
                raise openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/images"))
            return "picture"
        with mock.patch.object(ip.time, "sleep"):
            self.assertEqual(ip._with_retries(flaky, ()), "picture")
        self.assertEqual(len(calls), 2)
        with mock.patch.object(ip.time, "sleep"), self.assertRaises(ValueError):
            ip._with_retries(lambda: (_ for _ in ()).throw(ValueError("a refusal")), ())   # never asked again

    def test_c4_a_name_the_picture_sets_over_two_lines_prints_each_line_once(self):
        # [his review of 127-132, C (4); 136's carton printed "Oat & Honey Comfort" then "Comfort" again]
        from apps.pipeline.services import concept_design_map as dm
        sources = [("Oat & Honey Comfort", "brief"), ("Daily Body Lotion", "brief")]
        got = dm.type_sources([{"part": "a", "seen": "Oat & Honey"}, {"part": "b", "seen": "Comfort"},
                               {"part": "c", "seen": "DAILY BODY LOTION"}], sources)
        self.assertEqual([g["words"] for g in got], ["Oat & Honey", "Comfort", "Daily Body Lotion"])
        self.assertEqual(dm._part_of("Oat & Honey Comfort", dm._words("Oat Comfort")), "Oat & Honey Comfort")

    def test_b11_the_shape_step_proposes_the_sizes_its_record_holds(self):
        # [his goal after the pitch page, B (11); 137's round compact] the editor read its sizes under names the record
        # never uses, so every editor opened at the form's starting size
        from types import SimpleNamespace
        from apps.pipeline.targets.ui import _proposed_profile
        output = SimpleNamespace(spec_sheet={"container_profile/1.0": {
            "archetype": "compact", "fields": {"variant": {"value": "round"}, "body_width_mm": {"value": 80.0},
                                                "body_height_mm": {"value": 80.0}, "body_depth_mm": {"value": 14.0}}}})
        outputs = SimpleNamespace(order_by=lambda *_a: SimpleNamespace(first=lambda: output))
        got = _proposed_profile(SimpleNamespace(packaging_outputs=outputs))["proportions"]
        self.assertEqual((got["width_mm"], got["height_mm"], got["depth_mm"]), (80.0, 80.0, 14.0))

    def test_a6_a_line_inside_an_oval_is_held_inside_it_at_its_own_rows(self):
        from apps.ire import compose_container as cc
        oval = {"box": [0.2, 0.4, 0.8, 0.6], "shape": "ellipse", "centre": [0.5, 0.5], "half": [0.3, 0.1]}
        line = {"box": [0.1, 0.52, 0.9, 0.57]}                  # the picture's line runs past the oval
        left, right = cc._frame_room(line, {"windows": [oval]}, 100.0, 100.0)
        half = 30.0 * (1.0 - (7.0 / 10.0) ** 2) ** 0.5
        self.assertAlmostEqual(right - left, 2 * half * (1 - 2 * cc.MAP_TYPE_FRAME_PAD), places=3)
        self.assertAlmostEqual((left + right) / 2.0, 50.0, places=3)
        self.assertIsNone(cc._frame_room({"box": [0.0, 0.0, 0.1, 0.1]}, {"windows": [oval]}, 100.0, 100.0))
        self.assertGreater(cc._arabic_width_mm("كريم الجسم", 10.0), 0.0)

    def test_b10_a_gilded_line_keeps_its_gold_and_its_bright_core(self):
        from apps.pipeline.services import line_geometry as lg
        groups = lg._inks([{"fill": "#BD7E12", "rings": []}, {"fill": "#F5D998", "rings": []}])
        gold = groups[0]
        self.assertEqual(gold["tones"], ["#BD7E12", "#F5D998"])

    def test_b9_a_flat_face_is_traced_crisp_and_a_graded_one_keeps_its_smooth_ground(self):
        from apps.pipeline.targets.container import face_art as fa
        flat = self._png(lambda im: (_layout_cv2.rectangle(im, (0, 0), (300, 120), (30, 50, 90), -1),
                                     _layout_cv2.circle(im, (150, 200), 40, (60, 200, 240), -1)))
        img = _layout_cv2.imdecode(_layout_np.frombuffer(flat, _layout_np.uint8), _layout_cv2.IMREAD_COLOR)
        self.assertTrue(fa.is_flat(img))
        traced = fa.trace_face(flat)
        self.assertTrue(traced["flat"] and traced["regions"])
        ramp = _layout_np.zeros((300, 300, 3), _layout_np.uint8)
        for y in range(300):
            ramp[y, :] = (150 + y // 3, 120 + y // 4, 200 - y // 3)
        self.assertFalse(fa.is_flat(ramp))                       # a smooth gradient is never cut into bands
        self.assertEqual(fa.face_top({}), 0.0)                   # a face with no closure named prints whole

    def test_b5_the_eye_leaves_the_marks_own_drawing_alone_and_sets_a_line_heavier(self):
        import json
        from apps.ire.graph import Color, Document, Group, TextRun
        from apps.pipeline.services import designers_eye as eye
        doc = Document(page_w=50, page_h=50, root=Group(name="root", children=[
            TextRun(name="map-type-0", text="COCOA FONDANT", x=1, y=10, size_pt=9, color=Color.from_hex("#DFC9AA"))]))
        answer = {"matches": False, "summary": "x", "differences": [
            {"kind": "extra element", "part": "BBROSE wordmark", "concept": "no ®", "drawing": "® added",
             "severity": "major", "fix": {"lever": "none"}},
            {"kind": "font", "part": "COCOA FONDANT name", "concept": "chunky", "drawing": "thin",
             "severity": "major", "fix": {"lever": "weight", "to": "bold"}}]}
        seen = eye.look(self._png(lambda im: None), self._png(lambda im: None), call=lambda s, c: json.dumps(answer))
        self.assertEqual([d["part"] for d in seen["differences"]], ["COCOA FONDANT name"])
        said = eye.recolour(doc, seen["differences"])
        self.assertEqual(doc.root.children[0].font, "heading")
        self.assertTrue(said and "heavier" in said[0])


# ---- [His goal after the pitch page, 2026-10-15, A (2) and A (3): metals drawn as metallic, from the concept's own light;
# ---- shapes and proportions from the concept. Every case a picture no design has drawn.]

_PORTRAIT_LID = {"state": "TRACED_FROM_CONCEPT", "view": "PLAN", "kind": "rounded_rect", "aspect": 0.8884,
                 "quad": {"wide": False, "aspect": 0.8884}}


def test_c3_the_shape_door_hands_on_the_size_its_record_confirms():
    # [his review of 127-132, C (3)] 131 was drawn at its starting 110 x 95 while its record held 123.8
    from types import SimpleNamespace
    from apps.pipeline.views import _concept_sized
    task = SimpleNamespace(task_text="An eyeshadow palette, nine pans.")
    spec = {"container_outline_trace/1.0": _PORTRAIT_LID}
    clean = {"width_mm": 110.0, "height_mm": 95.0, "depth_mm": 18.0}
    assert _concept_sized(task, spec, "compact", clean) == dict(clean, height_mm=123.8)
    assert _concept_sized(task, spec, "compact", dict(clean, height_mm=100.0))["height_mm"] == 100.0


def test_pitch_a3_the_forms_starting_size_gives_way_to_the_concepts_proportion():
    from apps.pipeline.targets.container import concept_proportion_size
    w, h, why = concept_proportion_size("compact", 110.0, 95.0, _PORTRAIT_LID, "An eyeshadow palette, nine pans.")
    assert (w, h) == (110.0, 123.8) and "starting size" in why        # portrait, as its concept is
    assert concept_proportion_size("compact", 110.0, 95.0, _PORTRAIT_LID, "A palette 95 mm tall.")[2] is None
    assert concept_proportion_size("compact", 110.0, 100.0, _PORTRAIT_LID, "")[1:] == (100.0, None)   # a chosen size
    assert concept_proportion_size("compact", 110.0, 95.0, None, "")[1:] == (95.0, None)               # nothing traced
    jar = {"state": "TRACED_FROM_CONCEPT", "view": "ELEVATION", "kind": "profile", "height_to_width": 0.8}
    from apps.pipeline.targets.container import archetypes as declared
    n = declared.nominal_of("jar")
    assert concept_proportion_size("jar", float(n["width_mm"]), float(n["height_mm"]), jar, "")[1] == round(
        float(n["width_mm"]) * 0.8, 1)


def test_pitch_a3_the_shape_steps_record_takes_the_concepts_proportion_over_the_starting_size():
    from apps.pipeline.views import _container_profile_record
    task = MagicMock(product=None, task_text="An eyeshadow palette, nine pans.")
    record = _container_profile_record(task, {"container_outline_trace/1.0": _PORTRAIT_LID}, "compact",
                                       {"variant": "rounded_rect"},
                                       {"width_mm": 110.0, "height_mm": 95.0, "depth_mm": 18.0, "cap_style": "clasp"})
    assert record["fields"]["body_height_mm"]["value"] == 123.8 and record["fields"]["body_width_mm"]["value"] == 110.0


def test_pitch_a3_an_outline_is_stood_closure_up_by_where_its_closure_is():
    from apps.pipeline.targets.container import closure_up
    flipped = {"kind": "profile", "profile": [[0.0, 0.6], [0.5, 1.0], [1.0, 0.9]], "stands_on_closure": True}
    up, why = closure_up(flipped, "top")                              # a jar narrower at its foot, read upside down
    assert up["profile"] == [[0.0, 0.9], [0.5, 1.0], [1.0, 0.6]] and up["stands_on_closure"] is False and why
    assert closure_up(flipped, "foot") == (flipped, None)             # a tube on its cap stays as it was read
    assert closure_up(dict(flipped, stands_on_closure=False), "top")[1] is None


def _closure_picture(cap_columns):
    """A product on a dark ground: a pale body and a closure whose columns carry ``cap_columns`` (BGR) left to right."""
    import cv2
    import numpy as np
    img = np.full((600, 400, 3), 40, np.uint8)
    img[200:560, 100:300] = (222, 214, 190)
    for j, colour in enumerate(cap_columns):
        x0 = 150 + j * 100 // len(cap_columns)
        img[80:200, x0:150 + (j + 1) * 100 // len(cap_columns)] = colour
    return cv2.imencode(".png", img)[1].tobytes()


def _closure_spec(finish, name="cap"):
    return {"container_design_map/1.0": {"product_box_px": [100, 80, 300, 560], "parts": [
        {"kind": "closure", "name": name, "box": [0.25, 0.0, 0.75, 0.25], "finish": finish},
        {"kind": "field", "name": "body", "box": [0.0, 0.25, 1.0, 1.0]}]}}


def test_pitch_a2_a_metal_closures_light_is_measured_where_the_concept_shows_it():
    from apps.pipeline.targets.container import closure_looks_of
    chrome = [(225, 225, 225), (250, 250, 250), (150, 150, 150), (75, 75, 75), (190, 190, 190)]
    colors, sources = {}, {}
    looks = closure_looks_of(_closure_spec("polished chrome"), _closure_picture(chrome), "bottle", colors, sources)
    run = looks["cap"]["lightness"]
    assert looks["cap"]["metal"] == "chrome" and run[0][0] == 0.0 and run[-1][0] == 1.0
    brightest = max(run, key=lambda r: r[1])
    darkest = min(run, key=lambda r: r[1])
    assert 0.2 <= brightest[0] <= 0.4 and 0.6 <= darkest[0] <= 0.8   # its shine and its shade where the photo has them
    assert brightest[1] - darkest[1] > 40 and colors["cap"].startswith("#")
    gold = [(60, 140, 190), (120, 210, 240), (40, 100, 150)]          # BGR: a gold lid, lit across its middle
    gl = closure_looks_of(_closure_spec(None, "lid"), _closure_picture(gold), "jar", {}, {})
    assert gl["cap"]["metal"] == "gold"                               # read as gold by its light alone


def test_pitch_a2_a_pale_matte_cap_shaded_stays_flat():
    from apps.pipeline.targets.container import closure_looks_of
    matte = [(235, 235, 240), (225, 225, 230), (210, 210, 215)]
    assert closure_looks_of(_closure_spec("matte"), _closure_picture(matte), "bottle", {}, {}) is None
    assert closure_looks_of(_closure_spec(None), _closure_picture(matte), "bottle", {}, {}) is None
    assert closure_looks_of(_closure_spec("polished chrome"), _closure_picture(matte), "compact", {}, {}) is None


def test_pitch_a3_a_droppers_bulb_and_collar_are_each_read_on_their_own_part():
    from apps.pipeline.targets.container import OUTLINE_SOURCE_KEY, closure_looks_of
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(_closure_picture([(200, 200, 200)]), np.uint8), cv2.IMREAD_COLOR)
    img[80:140, 150:250] = (60, 60, 160)                              # a red-brown bulb over a pale collar
    pic = cv2.imencode(".png", img)[1].tobytes()
    spec = dict(_closure_spec("rubber bulb, glass collar"), **{OUTLINE_SOURCE_KEY: {"closure_split_in_picture": 0.125}})
    colors = {"cap": "#101010"}
    closure_looks_of(spec, pic, "bottle", colors, {})
    assert colors["bulb"] != colors["cap"] and colors["cap"] != "#101010"
    r, g, b = (int(colors["bulb"][k:k + 2], 16) for k in (1, 3, 5))
    assert r > b + 60                                                 # the bulb's own colour, not the collar's grey


def test_pitch_a3_where_the_closure_is_is_read_from_the_map_never_from_the_narrower_end():
    from apps.pipeline.targets.container import _map_closure_line, closure_at_picture_foot
    lid_up = {"container_design_map/1.0": {"state": "READ", "parts": [{"kind": "closure", "box": [0.1, 0.0, 0.9, 0.2]}]},
              "container_outline_trace/1.0": {"stood_narrow_end_up": True}}     # a jar narrower at its foot
    from apps.pipeline.services import concept_design_map as dm
    lid_up[dm.SCHEMA]["state"] = dm.MAP_READ
    assert closure_at_picture_foot(lid_up) is False and _map_closure_line(lid_up) == 0.2
    on_cap = {dm.SCHEMA: {"state": dm.MAP_READ, "parts": [{"kind": "closure", "box": [0.3, 0.85, 0.7, 1.0]}]}}
    assert closure_at_picture_foot(on_cap) is True and _map_closure_line(on_cap) == 0.15
    assert closure_at_picture_foot({"container_outline_trace/1.0": {"stood_narrow_end_up": True}}) is True


def test_his_review_132_c2_a_broken_motif_is_redrawn_flat_or_left_out_said_never_printed_broken():
    """[His review of 127, 130, 131 and 132, 2026-10-15, C (2): "a motif that can't be traced cleanly ... is redrawn
    flat and traced again; never printed broken."] Each solid motif of the front is measured against its picture
    (``_with_flat_shapes``): a whole one is kept as traced; a broken one is drawn from its flat redraw kept on the
    concept, traced again in its colours and as one ink's outlines; one with no redraw kept is left out and said beside
    Approve (``flat_motif_codes`` — never a stop), and is asked to be redrawn once (``broken_shape_parts``)."""
    from types import SimpleNamespace

    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import flat_motif as fm
    from apps.pipeline.targets.container import _with_flat_shapes, broken_shape_parts, flat_motif_codes
    spec = {dm.SCHEMA: {"parts": [{"name": "flower emblem", "kind": "shape", "box": [0.4, 0.3, 0.6, 0.45]},
                                  {"name": "label", "kind": "field", "box": [0.1, 0.1, 0.9, 0.9]}]}}
    flower = {"part": "flower emblem", "ink": "#C6903C", "box": [0.4, 0.3, 0.6, 0.45], "cubics": []}
    label = {"part": "label", "ink": "#FFFFFF", "box": [0.1, 0.1, 0.9, 0.9], "cubics": []}
    front = {"shapes": {"shapes": [flower, label]}}
    broken = {"ok": False, "measured": True, "agreement": 0.64, "pieces": [11, 10], "why": "it is broken into pieces"}
    whole = dict(broken, ok=True, why="")
    image = SimpleNamespace(pk=1)
    measured = []

    def measure(pic, record, shape):
        measured.append(shape["part"])
        return broken if shape["part"] == "flower emblem" else whole
    with patch.object(fm, "shape_whole", side_effect=measure), patch.object(fm, "kept_flat", return_value=None):
        out = _with_flat_shapes(front, spec, image, b"png", face_mm=(67.0, 83.7))
        assert broken_shape_parts(spec, b"png", front) == ["flower emblem"]
    assert measured[:1] == ["flower emblem"] and "label" not in measured       # a field is no motif
    left, kept = out["shapes"]["shapes"]
    assert left["undrawn"].startswith("it is broken into pieces") and "flat" not in left and kept == label
    code, = flat_motif_codes(out)
    assert code.startswith(fm.SHAPE_BROKEN + ": flower emblem")
    art = {"state": "TRACED", "art": {"regions": []}, "box": [0.4, 0.3, 0.6, 0.45], "ground": "#F6EEE1"}
    mono = {"state": "TRACED", "outlines": {"svg": "<svg/>", "frame": [0, 0, 1, 1]}}
    record = {"part": "flower emblem", "file": "f.png", "product_mm": [67.0, 83.7]}
    with patch.object(fm, "shape_whole", side_effect=measure), patch.object(fm, "kept_flat", return_value=record), \
            patch.object(fm, "flat_bytes", return_value=b"flat"), \
            patch.object(fm, "trace_flat", side_effect=lambda png, box, mm, colour=True: art if colour else mono):
        out = _with_flat_shapes(front, spec, image, b"png", face_mm=(67.0, 83.7))
    redrawn = out["shapes"]["shapes"][0]
    assert redrawn["flat"] is art and redrawn["flat_mono"] is mono and not redrawn.get("undrawn")
    assert "drawn from its flat redraw" in redrawn["redrawn"] and flat_motif_codes(out) == []


# [His review of 127, 130, 131 and 132, 2026-10-15, C (3), D (11); the lead's looks at 128, 134 and 135]

def test_his_review_d11_a_collar_under_its_cap_is_read_on_its_own_part():
    """134's map reads its closure as two parts — a plum cap on a brushed bronze collar. Each is read on its own box, in
    its own words: the collar its own colour and, metal, its own light, printed as the gold is."""
    from apps.pipeline.targets.container import OUTLINE_SOURCE_KEY, closure_looks_of, closure_parts
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(_closure_picture([(70, 50, 60)]), np.uint8), cv2.IMREAD_COLOR)
    for j, colour in enumerate([(70, 140, 190), (140, 215, 245), (40, 90, 140)]):
        img[150:200, 150 + j * 33:150 + (j + 1) * 33] = colour          # a gold collar, lit across its middle
    pic = cv2.imencode(".png", img)[1].tobytes()
    spec = {"container_design_map/1.0": {"product_box_px": [100, 80, 300, 560], "parts": [
        {"kind": "closure", "name": "plum cap", "box": [0.25, 0.0, 0.75, 0.146], "finish": "matte"},
        {"kind": "closure", "name": "bronze collar", "box": [0.25, 0.146, 0.75, 0.25], "finish": "brushed metallic"},
        {"kind": "field", "name": "body", "box": [0.0, 0.25, 1.0, 1.0]}]}, OUTLINE_SOURCE_KEY: {"collar_split": 0.146}}
    assert [p["name"] for p in closure_parts(spec["container_design_map/1.0"])] == ["plum cap", "bronze collar"]
    colors = {}
    looks = closure_looks_of(spec, pic, "bottle", colors, {})
    assert looks["collar"]["metal"] == "gold" and "cap" not in looks   # the matte cap stays flat
    r, g, b = (int(colors["collar"][k:k + 2], 16) for k in (1, 3, 5))
    cr, cg, cb = (int(colors["cap"][k:k + 2], 16) for k in (1, 3, 5))
    assert r > b + 40 and cr < 100                                      # each its own colour
    one = dict(spec["container_design_map/1.0"], parts=spec["container_design_map/1.0"]["parts"][1:])
    assert closure_parts(one) is None


def test_his_review_d11_a_closures_seam_is_read_where_the_concept_shows_it():
    """135's flip-top drawn as a flat yellow block: the line its lid parts from its base along is the concept's own. A
    dark line across the closure is read as its seam, at its place; a plain cap, a cap's one edge, a shine — none."""
    from apps.pipeline.targets.container import closure_seams_of
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(_closure_picture([(40, 190, 245)]), np.uint8), cv2.IMREAD_COLOR)
    plain = cv2.imencode(".png", img)[1].tobytes()
    img[140:143, 150:250] = (15, 120, 200)                             # its seam: a darker line across it
    seamed = cv2.imencode(".png", img)[1].tobytes()
    spec = _closure_spec("gloss", "flip cap")
    seams = closure_seams_of(spec, seamed, "tube")
    assert len(seams) == 1 and abs(seams[0]["at"] - (141.5 - 80) / 480.0) < 0.01, seams
    assert closure_seams_of(spec, plain, "tube") == []
    img[140:143, 150:250] = (120, 240, 255)                            # a shine, lighter than the cap: never a seam
    assert closure_seams_of(spec, cv2.imencode(".png", img)[1].tobytes(), "tube") == []
    assert closure_seams_of(spec, seamed, "compact") == []             # a lid drawn in plan has no closure to read


def test_his_review_d11_gold_line_art_is_inked_in_the_concepts_own_gold():
    """126's rose, "gold line" in its map, drawn in the dark brown its flat redraw drew its lines in. Line art the map
    names gold is inked in the concept photo's own lit gold; line art it names otherwise keeps its ink."""
    from types import SimpleNamespace
    from unittest import mock
    from apps.pipeline import targets
    from apps.pipeline.targets.container import concept_gold_ink
    import cv2
    import numpy as np
    img = np.full((600, 400, 3), 40, np.uint8)
    img[100:560, 100:300] = (170, 180, 230)                            # a pink body
    for y in range(300, 500, 8):
        img[y:y + 3, 120:280] = (90, 170, 215)                         # its fine gold lines (BGR)
    pic = cv2.imencode(".png", img)[1].tobytes()
    spec = {"container_design_map/1.0": {"product_box_px": [100, 100, 300, 560], "parts": [
        {"kind": "motif", "name": "rose", "box": [0.05, 0.4, 0.95, 0.9], "finish": "gold line"},
        {"kind": "motif", "name": "leaf", "box": [0.05, 0.4, 0.95, 0.9], "finish": "matte ink"}]}}
    with mock.patch.object(targets.container, "_concept_bytes", return_value=pic):
        gold = concept_gold_ink(spec, SimpleNamespace(), "rose")
        assert concept_gold_ink(spec, SimpleNamespace(), "leaf") is None
    r, g, b = (int(gold[k:k + 2], 16) for k in (1, 3, 5))
    assert abs(r - 215) < 12 and abs(g - 170) < 12 and abs(b - 90) < 12, gold   # the lines' gold, not the pink


def test_his_review_c3_a_redraws_own_paper_is_never_the_face():
    """127's and 128's redraws drew their face as a card, white paper round its rounded corners and over its top: traced,
    a white gap under the cap and a white fade at the foot. That paper, where the concept shows its backdrop or its own
    colour, is filled from the art beside it; a white the concept itself shows there is kept."""
    from apps.pipeline.targets.container import face_art as fa
    import cv2
    import numpy as np
    art = np.full((300, 200, 3), (60, 200, 240), np.uint8)             # a yellow face …
    art[:12, :] = 255                                                  # … white paper over its top
    for (cy, cx) in ((0, 0), (0, 199), (299, 0), (299, 199)):
        cv2.circle(art, (cx, cy), 30, (255, 255, 255), -1)            # … and round its corners
    face = np.full((300, 200, 3), (40, 40, 40), np.uint8)             # the concept: its dark backdrop there …
    face[40:260, 20:180] = (60, 200, 240)
    enc = lambda im: cv2.imencode(".png", im)[1].tobytes()
    out, rec = fa.without_paper(enc(art), enc(face), (16.0, 0.0))
    got = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)
    assert rec is not None and int(got[3, 100].min()) < 200 and int(got[5, 5].min()) < 200   # no paper left
    assert np.abs(got[150, 100].astype(int) - (60, 200, 240)).max() <= 2                     # the face untouched
    white = np.full((300, 200, 3), 250, np.uint8)                     # the concept shows white there itself
    kept, rec2 = fa.without_paper(enc(art), enc(white), (16.0, 0.0))
    assert rec2 is None and kept == enc(art)


def test_his_review_d11_a_narrow_reflection_is_drawn_as_narrow_as_the_concept_shows_it():
    """128's collar: a dark reflection a tenth of its width, read at nine evenly spaced places, was drawn across a
    quarter of it. The light run keeps every place it turns: the dark band is as narrow drawn as photographed."""
    from apps.pipeline.services import flat_motif as fm
    import cv2
    import numpy as np
    img = np.full((600, 400, 3), 40, np.uint8)
    img[80:200, 150:250] = (230, 230, 230)
    img[80:200, 196:206] = (12, 12, 12)                                # its narrow dark band
    run = fm.light_run(cv2.imencode(".png", img)[1].tobytes(), [0.25, 0.0, 0.75, 0.25], [100, 80, 300, 560])
    at = lambda x: float(np.interp(x, [o for o, _l in run["lightness"]], [light for _o, light in run["lightness"]]))
    assert at(0.51) < 20 and at(0.42) > 75 and at(0.60) > 75, run["lightness"]   # dark only where it is dark


def test_his_review_c3_a_body_is_read_clear_of_the_window_it_holds():
    """[His review of 127, 130, 131 and 132, 2026-10-15, C (3)] 130's body field held its cobalt oval window across its
    whole middle two-fifths, so its matte white body was read navy. A standing product's surface is read clear of every
    surface held inside it; one with nothing inside it is read in its middle as before."""
    import numpy as np
    from apps.pipeline.services import concept_design_map as dm
    labels = np.zeros((100, 100), np.int64)                            # 0: the white body
    labels[30:85, 25:75] = 1                                           # 1: the cobalt oval window over its middle
    body = {"colours": [{"hex": "#F4F1EA", "lab": [95.0, 0.0, 4.0]}, {"hex": "#173371", "lab": [22.0, 10.0, -40.0]}],
            "backdrop_lab": None}
    shade = np.zeros((100, 100), bool)
    field = {"kind": "field", "_px": (5, 10, 95, 95)}
    window = {"kind": "window", "_px": (25, 30, 75, 85)}
    dm._colour_parts([field, window], labels, body, shade)
    assert field["colour"] == "#F4F1EA" and window["colour"] == "#173371", (field, window)
    alone = {"kind": "field", "_px": (25, 30, 75, 85)}
    dm._colour_parts([alone], labels, body, shade)
    assert alone["colour"] == "#173371"


# [his goal after the pitch page, B (9)-(11): the three brand-new briefs, re-run on 9adb649 — the perfume, 138]

def test_b9_a_brief_written_as_a_client_writes_gives_its_quoted_words_and_size():
    """138's brief has no "Front copy:" field: "Name on the front, then "Eau de Parfum" and "50 ml / 1.7 fl oz" small
    underneath." Its quoted phrases are its copy and its size is the one it quotes — never "no size on record"."""
    from apps.pipeline.services import concept_design_map as dm
    brief = ('Hi team, we need the bottle artwork for a new eau de parfum, 50 ml, called "Midnight Fig". Dark and '
             'moody. Name on the front, then "Eau de Parfum" and "50 ml / 1.7 fl oz" small underneath. Brand is BBROSE.')
    assert dm.brief_front_copy(brief) == ["Midnight Fig", "Eau de Parfum", "50 ml / 1.7 fl oz"]
    assert dm.brief_size(brief)[0] == "50 ml / 1.7 fl oz"
    # a field on record still governs: its quotes are its own
    assert dm.brief_front_copy('Front copy: "Rose Blossom", Hand Cream.\nStyle: "soft"') == ["Rose Blossom",
                                                                                          "Hand Cream"]
    assert dm.brief_front_copy('A soft cream, "a %s"' % ("very long sentence about the design " * 3)) == []


def test_b9_a_redraws_lettering_is_left_out_where_its_read_ink_is_muddier_than_its_print():
    """138's flat redraw kept its near-white capitals (#E5DFD4) where the map read their ink #9F9B98, on its deep plum:
    lettering is any region in the line's box on the way from its ground through its ink — or past it — and any patch
    of its ground's own colour there (a letter's counter); a motif of its own colour inside the box stays."""
    from apps.pipeline.targets.container import lid_art as la
    sq = lambda x0, y0, x1, y1: [[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]]
    trace = {"regions": [{"fill": "#2E2027", "rings": sq(0, 0, 1, 1)},                  # the plum ground
                         {"fill": "#E5DFD4", "rings": sq(0.30, 0.63, 0.32, 0.65)},      # a near-white capital
                         {"fill": "#7A6E6E", "rings": sq(0.40, 0.63, 0.42, 0.65)},      # its blended edge
                         {"fill": "#33252C", "rings": sq(0.36, 0.635, 0.37, 0.645)},    # a counter, traced apart
                         {"fill": "#B7823C", "rings": sq(0.60, 0.63, 0.63, 0.65)}]}     # an amber motif: kept
    out = la.without_words(trace, [[0.25, 0.62, 0.75, 0.665]], ["#9F9B98"])
    assert [r["fill"] for r in out["regions"] if not r.get("painted_out")] == ["#2E2027", "#B7823C"] and out["words_left_out"] == 3
    # [his last goal before the pitch, Step 2, 127] each left out in its ground's own colour: no hole, bay or counter shows
    assert {r["fill"] for r in out["regions"] if r.get("painted_out")} == {"#2E2027"}


def test_b9_a_closure_too_near_its_bodys_colour_ends_at_its_map_box():
    """138's matte black cap on its deep plum body: where the cap's colour begins was read 0.7 % down the product, so
    the whole bottle was drawn as body. An edge farther inside the closure than SHAPE_PARAMS["closure_edge_band"] of its
    map box is not its edge: the box's own stands, said; an edge read where the box ends stands as read."""
    import cv2
    import numpy as np
    from apps.pipeline.services import concept_design_map as dm
    img = np.full((400, 200, 3), 250, np.uint8)
    img[40:380, 40:160] = (40, 22, 38)                                  # the deep plum body (BGR)
    img[40:120, 60:140] = (38, 25, 37)                                  # its black cap, as near it as 138's
    img[40:48, 60:140] = (62, 60, 62)                                   # the cap's lit top, the one row run of its own
    png = cv2.imencode(".png", img)[1].tobytes()
    import hashlib
    rec = {"state": dm.MAP_READ, "source_sha256": hashlib.sha256(png).hexdigest(),
           "parts": [{"kind": "closure", "name": "matte black cap", "box": [0.17, 0.0, 0.83, 0.235], "colour": "#252324"},
                     {"kind": "field", "name": "deep plum body", "box": [0.0, 0.235, 1.0, 1.0], "colour": "#26162A"}]}
    mask = np.zeros(img.shape[:2], np.uint8)
    mask[40:380, 40:160] = 255
    with patch.object(dm, "_full_size", return_value=(img, mask, (40, 40, 160, 380))):
        got = dm.closure_edge(png, rec)
    assert got["edge"] == 0.235 and "too far inside the closure" in got["by"], got      # read near the top: refused
    img[40:120, 60:140] = (37, 35, 36)
    img[120:380, 40:160] = (120, 40, 150)                               # a body far from the cap's colour: as read
    rec["parts"][1]["colour"] = "#962878"
    with patch.object(dm, "_full_size", return_value=(img, mask, (40, 40, 160, 380))):
        got = dm.closure_edge(png, rec)
    assert "by" not in got and abs(got["edge"] - 0.235) < 0.02, got


def test_b9_the_eyes_recolour_takes_the_lines_it_names_never_a_back_sentence_sharing_a_word():
    """138: the eye's "upper 'MIDNIGHT FIG' and 'eau de parfum'" recoloured cream every back line holding "eau" or
    "parfum" — cream on the white back. Only a line whose own words are mostly the part's is that line."""
    from apps.ire.graph import Color, Document, Group, TextRun
    from apps.pipeline.services import designers_eye as eye
    runs = [TextRun(name="map-type-0", text="MIDNIGHT FIG", x=1, y=10, size_pt=9, color=Color.from_hex("#4A2A33")),
            TextRun(name="map-type-1", text="eau de parfum", x=1, y=14, size_pt=5, color=Color.from_hex("#4A2A33")),
            TextRun(name="back-panel-0-copy-1", text="An eau de parfum with a warm, sophisticated character",
                    x=1, y=30, size_pt=3, color=Color.from_hex("#9F9B98"))]
    doc = Document(page_w=50, page_h=50, root=Group(name="root", children=runs))
    said = eye.recolour(doc, [{"kind": "illegible type", "part": "upper 'MIDNIGHT FIG' and 'eau de parfum'",
                               "severity": "blocking", "concept": "cream", "drawing": "plum",
                               "fix": {"lever": "recolour", "concept_hex": "#F2E6D4", "drawing_hex": "#4A2A33"}}])
    assert said and [r.color.to_hex() for r in runs] == ["#F2E6D4", "#F2E6D4", "#9F9B98"]


def test_b10_a_face_stood_on_its_cap_is_cut_above_it():
    """[His goal after the pitch page, B (10)] the lotion tube, 139, stands on its cap: its face was cut BELOW the cap
    (``face_top`` read the cap's box as a closure on top, clamped to 0.6) — the cream band and the cap redrawn, its honey
    dipper, oats and drips never drawn. A face runs from below a closure at its top to above one at its foot."""
    from apps.pipeline.targets.container import face_art as fa
    foot_cap = {"container_design_map/1.0": {"parts": [{"kind": "closure", "box": [0.15, 0.7757, 0.92, 1.0154]}]}}
    assert fa.face_top(foot_cap) == 0.0 and fa.face_foot(foot_cap) == 0.7757
    top_cap = {"container_design_map/1.0": {"parts": [{"kind": "closure", "box": [0.18, -0.01, 0.8, 0.2276]}]}}
    assert fa.face_top(top_cap) == 0.2276 and fa.face_foot(top_cap) == 1.0
    assert fa.face_top({}) == 0.0 and fa.face_foot({}) == 1.0


def test_b10_a_lines_ink_read_off_its_letters_is_read_again_and_a_marks_never_its_grounds_gold():
    """[His goal after the pitch page, B (10)] the lotion tube, 139: "Comfort" read #DCB975 (its honey dipper's tan) on
    a sunny yellow where its letters print dark brown, and its red-brown BBROSE drawn yellow — its ground passed the gold
    test. A line's ink is its letters' — the pixels farthest from the ground just outside its box — where the read lies
    far from them; a mark read in another ink than gold is never its ground's gold; a read that is right stands."""
    import cv2
    import numpy as np
    from apps.pipeline.services import concept_design_map as dm
    img = np.full((300, 200, 3), (40, 171, 228), np.uint8)             # the sunny yellow (BGR of #E4AB28)
    cv2.putText(img, "Comfort", (20, 160), cv2.FONT_HERSHEY_DUPLEX, 1.6, (34, 52, 79), 5)   # dark brown letters
    mask = np.full(img.shape[:2], 255, np.uint8)
    pbox = (0, 0, 200, 300)
    part = {"name": "hero line two", "kind": "type", "box": [0.08, 0.40, 0.95, 0.56], "colour": "#DCB975",
            "seen_text": "Comfort", "lettering": "sans"}
    got = dm.trace_type(img, mask, pbox, part)
    from apps.ire.legibility import colour_distance
    assert colour_distance(got["ink"], "#4F3422") < 15, got["ink"]
    right = dict(part, colour="#4F3422")
    assert colour_distance(dm.trace_type(img, mask, pbox, right)["ink"], "#4F3422") < 15
    cv2.putText(img, "BBROSE", (40, 60), cv2.FONT_HERSHEY_DUPLEX, 0.9, (36, 63, 168), 2)    # its red-brown mark
    mark = {"name": "BBROSE wordmark", "kind": "mark", "box": [0.15, 0.12, 0.85, 0.24], "colour": "#A83F24"}
    assert colour_distance(dm.trace_mark(img, mask, pbox, mark)["ink"], "#A83F24") < 20


def test_b10_a_typewriter_slab_line_is_set_in_the_granted_slab():
    """[His goal after the pitch page, B (10)] the lotion tube's "with colloidal oat" and "℮ 200 ml", read a slab serif,
    were set in Libre Baskerville for want of a slab: a slab line is set in Courier Prime, granted for it."""
    from apps.ire import lettering_faces as LF
    slab = {"case": "lower", "class": "serif", "serif": "slab", "width": "normal", "italic": False,
            "weight": "regular", "spacing": "normal"}
    assert LF.choose({"seen": "with colloidal oat", "style": slab})["label"] == "CourierPrime-Regular"
    assert LF.choose({"seen": "OAT", "style": dict(slab, weight="bold")})["label"] == "CourierPrime-Bold"


def test_b11_a_size_inside_a_quoted_phrase_is_the_briefs_size():
    """[His goal after the pitch page, B (11)] the blush's brief quotes "Powder Blush 6 g" for its lid: its line,
    "POWDER BLUSH 6G" in the picture, was never printed — "no size on record". The size a phrase of its copy states
    among its words is the brief's size."""
    from apps.pipeline.services import concept_design_map as dm
    brief = 'A round powder blush compact called "Coral Haze". Shade "Sunlit Coral" and "Powder Blush 6 g" on the lid.'
    assert dm.brief_size(brief)[0] == "6 g"
    assert dm.brief_size('Front copy: "Rose Oil", 30 ml') == ("30 ml", dm.BRIEF_SIZE_FRONT)


def test_b11_a_lids_lettering_on_its_sky_is_left_out_a_little_off_its_box():
    """[His goal after the pitch page, B (11)] the blush's lid: its ground a smooth sky (no traced region holds the
    name's box), its redraw's "CORAL HAZE" a little above the map's box — printed in fragments under the live name. A
    lid's ground is its sky at the box's middle, and a box is padded by a line's height; a pearl of its own colour stays."""
    from apps.pipeline.targets.container import lid_art as la
    sq = lambda x0, y0, x1, y1: [[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]]
    trace = {"sky": {"rows": [["#D9785A"] * 4] * 4},
             "regions": [{"fill": "#F3D9C2", "rings": sq(0.30, 0.49, 0.33, 0.53)},      # a letter, a little high
                         {"fill": "#E9A98C", "rings": sq(0.40, 0.50, 0.42, 0.53)},      # its blended edge
                         {"fill": "#7FB0C8", "rings": sq(0.49, 0.46, 0.51, 0.48)}]}     # a blue pearl: kept
    out = la.without_words(trace, [[0.23, 0.527, 0.77, 0.579]], ["#EDCAAD"])
    assert [r["fill"] for r in out["regions"] if not r.get("painted_out")] == ["#7FB0C8"] and out["words_left_out"] == 2


def test_b10_one_field_redrawn_for_two_parts_is_drawn_once():
    """[His goal after the pitch page, B (10): 140's front "looks doubled ... far denser than the concept's spaced oat
    flakes"] Two all-over parts whose redraws are one field — the same box, the same inks — are drawn once: the later
    is ``drawn_with`` the first, counted drawn, never printed over it; a field in other inks, or a motif standing in one
    place, is its own."""
    from apps.ire.compose import wrapping_pattern
    from apps.pipeline.targets.container import one_field_once

    def field(part, inks, box=(0.02, 0.0, 0.98, 1.0)):
        return {"part": part, "flat": {"state": "TRACED", "box": list(box), "art": {"regions": []}, "colours": inks,
                                       "ink": inks[0]}}
    oats = field("oat grains scattered", ["#FCEAC3", "#DD8301"])
    drops = field("honey droplets", ["#FDF5E0", "#D97400"])
    stripes = field("blue stripes", ["#1A3E7E"])
    lone = field("one bee", ["#FCEAC3", "#DD8301"], box=(0.1, 0.1, 0.3, 0.3))
    got = one_field_once([oats, drops, stripes, lone])
    assert got[0] is oats and got[2] is stripes and got[3] is lone
    assert got[1]["drawn_with"] == "oat grains scattered"
    assert [line["part"] for line in wrapping_pattern({"shapes": {"lines": got}})] == ["oat grains scattered",
                                                                                     "blue stripes"]


def test_b10_a_colour_split_into_shades_is_one_colour_of_the_redraw():
    """[His goal after the pitch page, B (10): the designer's eye on 140, "concept has many orange honey droplets ...
    drawing omits them"] A colour the redraw prints in two near shades, each under ``least_share`` of the ink on its own
    and over it together, is one of the redraw's colours — 140's orange drops, read as two clusters of 4.6% and 4.2%,
    were traced in the field's cream; the field is traced in colour."""
    import cv2
    import numpy as np

    from apps.pipeline.services import flat_motif as fm
    img = np.zeros((600, 400, 3), np.uint8)
    img[:] = (0x13, 0xBA, 0xFA)                                       # the yellow ground (BGR)
    rnd = np.random.default_rng(3)
    for k in range(60):                                               # cream oats, most of the ink
        cx, cy = int(rnd.integers(30, 370)), int(rnd.integers(30, 570))
        cv2.ellipse(img, (cx, cy), (16, 9), float(rnd.integers(0, 180)), 0, 360, (0xC4, 0xEA, 0xFC), -1)
    for k in range(70):                                               # orange drops, in two shades
        cx, cy = int(rnd.integers(20, 380)), int(rnd.integers(20, 580))
        shade = (0x00, 0x74, 0xD9) if k % 2 else (0x02, 0x93, 0xF1)
        cv2.circle(img, (cx, cy), 4, shade, -1)
    ok, png = cv2.imencode(".png", img)
    read = fm.read_flat(png.tobytes(), 40.0, 60.0)
    cv2.setRNGSeed(1)
    inks = fm.ink_colours(read)
    assert len(inks) == 2, inks
    assert fm.delta_e(inks[0], "#FCEAC4") < 12 and min(fm.delta_e(inks[1], hx) for hx in ("#D97400", "#F19302")) < 12


def test_step1_1_the_face_and_lid_arts_colours_are_the_concepts_never_unsourced():
    """[His last goal before the pitch, 2026-10-16, Step 1 (1)] 138's page listed "A fault in the system itself —
    #E5DDE1:face-art-66" a hundred times over: every colour of the face's traced redraw was printed unsourced. The face's
    and the lid's art — their regions, sky, glow and grain — are the concept's own colours, said so."""
    from apps.pipeline.targets.container import map_front_colour_sources
    front = {"shapes": {}, "face_art": {"state": "TRACED", "regions": [{"fill": "#E5DDE1", "rings": []}],
                                         "grain": {"tones": {"#A0908A": [[0.1, 0.2]]}}},
             "lid_art": {"state": "TRACED", "regions": [], "sky": {"rows": [["#D9785A", "#E08A6A"]]}}}
    got = map_front_colour_sources(front)
    assert {"#E5DDE1", "#A0908A", "#D9785A", "#E08A6A"} <= set(got)
    assert "flat redraw" in got["#E5DDE1"] and "grain" in got["#A0908A"]


# [his last goal before the pitch, 2026-10-16, Step 2 — 139, the lotion tube]

def test_s2_139_a_lines_lettering_is_left_out_in_its_traced_ink_as_in_its_read():
    """139's "Comfort" ghosted behind its live line: the map read its ink as the dipper's tan, its letters brown. A box
    may name both inks — the read's and the traced letters' own — and a region in either is the redraw's lettering."""
    from apps.pipeline.targets.container import lid_art as la
    sq = lambda x0, y0, x1, y1: [[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]]
    trace = {"regions": [{"fill": "#F2B32A", "rings": sq(0, 0, 1, 1)},
                         {"fill": "#4B2F1E", "rings": sq(0.30, 0.60, 0.34, 0.68)}]}
    assert la.without_words(trace, [[0.22, 0.59, 0.83, 0.70]], ["#DCB975"])["regions"][-1]["fill"] == "#4B2F1E"
    out = la.without_words(trace, [[0.22, 0.59, 0.83, 0.70]], [["#DCB975", "#4B2F1E"]])
    assert [r["fill"] for r in out["regions"] if not r.get("painted_out")] == ["#F2B32A"]


def test_s2_139_a_line_no_frame_holds_stays_inside_the_products_outline():
    """139's "with colloidal oat" set at its picture's place ran past the drawn tube's edge, the body narrower there
    than its concept's. A line no frame holds is kept inside the product's own outline at its rows."""
    from types import SimpleNamespace
    from apps.ire.compose_container import MAP_TYPE_OUTLINE_PAD_MM, _outline_room
    from apps.ire.graph import ClosePath, LineTo, MoveTo
    # a tapering body: 50 mm wide at its top, 40 mm at its foot
    bb = SimpleNamespace(height_mm=100.0, silhouette=[MoveTo(x=0, y=0), LineTo(x=50, y=0), LineTo(x=45, y=100),
                                                      LineTo(x=5, y=100), ClosePath()])
    left, right = _outline_room(bb, 0.78, 0.82)
    assert abs(right - (50 - 5 * 0.82 - MAP_TYPE_OUTLINE_PAD_MM)) < 0.05 and abs(left - (5 * 0.82 + 1.5)) < 0.05


def test_s2_139_a_band_of_the_caps_colour_on_the_body_is_the_bodys_and_the_cap_begins_below_it():
    """139 stood on its cream flip-cap under a cream band its body prints — one colour, read as one closure, no cap
    drawn. The band across the edge is the body's: the closure, and the face, end at its far side."""
    import numpy as np
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.targets.container import face_art as fa
    lab = lambda hx: np.array([0.0, 0.0, 0.0]) if hx == "#000000" else np.array([80.0, 5.0, 25.0])
    rec = {"parts": [{"kind": "band", "box": [0.13, 0.7604, 0.93, 0.8295], "colour": "#DBC59D"}]}
    cap = {"kind": "closure", "box": [0.15, 0.7757, 0.92, 1.0154], "colour": "#DBC59D"}
    assert dm._band_on_the_body(rec, cap, True, 0.7727, lab) == 0.8295
    assert dm._band_on_the_body(rec, cap, True, 0.90, lab) is None
    spec = {"container_design_map/1.0": {"parts": [cap] + rec["parts"]}}
    assert fa.face_foot(spec) == 0.8295


def test_s2_139_the_grain_is_its_grounds_never_a_dotted_ghost_of_its_words():
    """139's speckled yellow: its grain's dots, each in the photo's colour where it stands, drew its bold brown name
    again in dots, and the dark backdrop beside the tube along its sides. No dot inside a line's box, nor off its
    area's own ground."""
    import cv2
    import numpy as np
    from apps.ire import grain
    rng = np.random.default_rng(5)
    img = np.full((300, 200, 3), (40, 180, 240), np.uint8)
    img = np.clip(img.astype(int) + rng.normal(0, 7, img.shape[:2])[..., None], 0, 255).astype(np.uint8)
    img[120:170, 40:160] = (30, 52, 79)                                  # the bold brown name
    img[:, :10] = (60, 30, 20)                                           # the dark backdrop at its side
    png = cv2.imencode(".png", img)[1].tobytes()
    got = grain.measure(png, [[0, 0, 1, 1]], [[0.2, 0.4, 0.8, 0.566]])
    dots = [d for v in got["tones"].values() for d in v]
    assert dots and not any(0.2 <= x <= 0.8 and 0.4 <= y <= 0.566 for x, y in dots)
    assert not any(x < 0.05 for x, _y in dots)


def test_s2_139_the_holes_a_left_out_letter_leaves_in_its_ground_are_closed():
    """139's ghost name: its yellow ground kept the letters cut out of it as holes, the body's yellow showing through.
    Where a letter is left out, its hole in the ground is closed; a kept motif's hole stays."""
    from apps.pipeline.targets.container import lid_art as la
    sq = lambda x0, y0, x1, y1: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    ground = {"fill": "#F8BA31", "rings": [sq(0, 0, 1, 1), sq(0.30, 0.60, 0.34, 0.68), sq(0.62, 0.30, 0.70, 0.36)]}
    letter = {"fill": "#4B2F1E", "rings": [sq(0.30, 0.60, 0.34, 0.68)]}
    motif = {"fill": "#7FB0C8", "rings": [sq(0.62, 0.30, 0.70, 0.36)]}
    out = la.without_words({"regions": [ground, letter, motif]}, [[0.22, 0.59, 0.83, 0.70]], ["#4B2F1E"])
    assert [r["fill"] for r in out["regions"] if not r.get("painted_out")] == ["#F8BA31", "#7FB0C8"]
    # the letter's hole is filled in the ground's own colour (its letter painted out): nothing of the body shows there
    painted = [r for r in out["regions"] if r.get("painted_out")]
    assert painted and painted[0]["fill"] == "#F8BA31" and painted[0]["rings"] == [sq(0.30, 0.60, 0.34, 0.68)]


def test_s2_140_the_lines_of_one_name_are_set_in_one_face():
    """140's "Oat &", "Honey" and "Comfort", one stacked name in one ink, were set in Barlow Condensed, Oswald and
    Fredoka, each line in its own closest face. Display lines stacked as one block are set in the face of the line its
    letters fit best; a line apart from the block keeps its own."""
    from apps.pipeline.services import concept_design_map as dm
    mk = lambda seen, y0, y1, face, outline: {"seen": seen, "ink": "#98292B", "box": [0.3, y0, 0.7, y1],
                                              "lettering_set": {"state": dm.LETTERING_SET, "face": face,
                                                                "outline": outline}}
    types = [mk("Oat &", 0.30, 0.36, "BarlowCondensed-Regular", 0.42), mk("Honey", 0.37, 0.43, "Oswald[wght]", 0.58),
             mk("Comfort", 0.44, 0.50, "Fredoka[wdth,wght]", 0.24), mk("SALE", 0.80, 0.84, "Jost[wght]", 0.5)]
    asked = []

    def again(img, mask, pbox, line, only=None):
        asked.append((line["seen"], only))
        return {"state": dm.LETTERING_SET, "face": only, "outline": 0.3}
    with patch.object(dm, "set_display", side_effect=again):
        dm._one_face_for_the_name(types, [], None, None, None)
    assert [t["lettering_set"]["face"] for t in types] == ["Oswald[wght]"] * 3 + ["Jost[wght]"]
    assert sorted(asked) == [("Comfort", "Oswald[wght]"), ("Oat &", "Oswald[wght]")]
    assert types[2]["lettering_set"]["was"] == "Fredoka[wdth,wght]"


def test_s2_138_a_closure_its_colour_cannot_end_ends_at_its_outlines_step():
    """[His last goal before the pitch, Step 2] 138's black cap on its plum neck: its colour too near the body's, its
    edge taken at its map box (0.2276), so the cap was drawn down over the neck, narrow and notched. Its outline ends it:
    at the step where the traced width narrows just above the box's edge."""
    from apps.pipeline.targets.container import closure_step
    prof = [(0.0, 0.586), (0.198, 0.586), (0.209, 0.543), (0.22, 0.469), (0.241, 0.469), (0.252, 0.525), (0.357, 1.0)]
    assert closure_step(prof, 0.2276) == (0.209 + 0.22) / 2.0
    assert closure_step([(0.0, 0.5), (0.2276, 0.5), (0.3, 1.0)], 0.2276) == 0.2276      # no step: as it was


def test_s2_138_a_line_read_in_small_letters_prints_in_small_letters():
    """[His last goal before the pitch, Step 2] 138's "eau de parfum", lettered in small letters, printed "Eau de
    Parfum" from his brief: his brief's words, in the case the concept letters them — never the product's name."""
    from types import SimpleNamespace
    from apps.ire import compose_container as cc
    line = {"part": "eau de parfum line", "words": "Eau de Parfum", "source": "brief", "ink": "#C3C1BB",
            "box": [0.34, 0.75, 0.66, 0.77], "style": {"class": "sans", "case": "lower", "italic": True}}
    zone = {"x": 0, "y": 0, "width": 40, "height": 100, "zone_id": "front"}
    group, _p, _r = cc._map_type_group({"shapes": {"types": [line]}}, zone, SimpleNamespace(width_mm=40.0,
                                       height_mm=100.0), 1.0, 0, 0, name_font="bold", product_name="Midnight Fig")
    assert [k.text for k in group.children if getattr(k, "type", None) == "text"] == ["eau de parfum"]


# [his fixes to 142 (Cherry Kiss), 2026-10-17]

def test_142_a_tall_line_is_read_turned_and_set_on_end_in_a_script_whole_inside_its_box():
    """(1) "A vertical script name is set vertically in a matching script face, whole and inside the panel (it came out
    horizontal sans, cut off)." A line its read gives no turn, its box standing 2.5 times taller than wide, is read
    turned, and its trace keeps the turn; set on end as one line in the granted script whose letters run closest to the
    picture's, no longer than its box; the copy fit holds its length against the zone's height."""
    from types import SimpleNamespace
    from apps.ire import compose_container as cc
    from apps.ire.compose_dropper import front_copy_fit
    from apps.ire.graph import Document, Group
    from apps.pipeline.services import concept_design_map as dm
    part = {"kind": "type", "name": "cherry kiss vertical script", "box": [0.6884, 0.4425, 0.9058, 0.8112],
            "seen_text": "cherry kiss"}
    turned = dm._turned_if_tall(part, (0, 0, 200, 1000))
    assert turned["rotation"] == 90 and "taller than wide" in turned["rotation_from"]
    assert "rotation" not in dm._turned_if_tall(part, (0, 0, 1000, 1000))            # wider in its own pixels
    assert "rotation" not in dm._turned_if_tall(dict(part, seen_text="3.5g"), (0, 0, 200, 1000))
    with patch.object(dm, "_trace_type", return_value={"part": part["name"], "set": "set in its box"}):
        assert dm.trace_type(None, None, None, turned)["rotation"] == 90
    line = {"part": part["name"], "words": "cherry kiss", "source": "brief", "ink": "#F9E8C9", "box": part["box"],
            "rotation": 90, "lettering": "script", "style": {"class": "script", "weight": "regular", "italic": True}}
    zone = {"x": 0, "y": 0, "width": 20, "height": 100, "zone_id": "front", "safe_margin_mm": 1.5}
    group, _p, rec = cc._map_type_group({"shapes": {"types": [line]}}, zone, SimpleNamespace(
        width_mm=20.0, height_mm=100.0), 1.0, 0, 0, name_font="bold", product_name="cherry kiss")
    runs = [k for k in group.children if getattr(k, "type", None) == "text"]
    assert [(r.text, r.rotation_deg, r.align) for r in runs] == [("cherry kiss", 90.0, "center")]
    assert rec["typed"][0]["set_on_end"] and rec["typed"][0]["face"]["stem"] == "DancingScript[wght]"
    x0, y0, x1, y1 = rec["boxes"][part["name"]]
    assert 0.6884 - 1e-4 <= x0 and x1 <= 0.9058 + 1e-4 and 0.4425 - 1e-4 <= y0 and y1 <= 0.8112 + 1e-4
    doc = Document(page_w=20.0, page_h=100.0, root=Group(name="root", children=[group]))
    fit = front_copy_fit(doc, zone)
    row = next(r for r in fit["name_runs"] if r["text"] == "cherry kiss")
    assert row.get("axis", "").startswith("along the zone's height") and row["zone_width_mm"] == 100.0


def test_142_the_redraws_own_lettering_is_taken_across_a_turned_line_never_the_art_beside_it():
    """(2) "Graphic illustrations (lips, cherries) are traced whole and clean, never broken outlines". 142's tall name
    box, padded by its own height, took the lips' and cherries' cream outlines for its letters. A turned line is padded
    by a share of its width, and a shape far thicker across than the line is no letter of it; the redraw's swash just
    past the box is still its letter."""
    from apps.pipeline.targets.container import lid_art as la
    sq = lambda x0, y0, x1, y1: [[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]]
    trace = {"size_px": [1024, 1536], "regions": [
        {"fill": "#9F2426", "rings": sq(0, 0, 1, 1)},
        {"fill": "#F9E8C9", "rings": sq(0.10, 0.20, 0.75, 0.45)},             # the lips' outline, across the box
        {"fill": "#F9E8C9", "rings": sq(0.40, 0.50, 0.45, 0.56)},             # a cherry's shine, in the old pad
        {"fill": "#F9E8C9", "rings": sq(0.75, 0.50, 0.80, 0.60)},             # a letter
        {"fill": "#F9E8C9", "rings": sq(0.935, 0.40, 0.975, 0.44)}]}          # its swash, past the box
    out = la.without_words(trace, [[0.6884, 0.137, 0.9058, 0.708]], [["#F9E8C9"]])
    kept = [r["rings"][0][0] for r in out["regions"] if not r.get("painted_out")]
    assert kept == [[0, 0], [0.10, 0.20], [0.40, 0.50]]


def test_142_the_products_own_side_the_redraw_drew_is_printed_in_the_ground():
    """(4) "No stray dark stripes." 142's redraw drew the box's side as a solid dark band down its left edge. A solid
    band joined to the face's side, down its whole height, a shade of its ground, is printed in the ground; a band of
    another colour is the face's own."""
    from apps.pipeline.targets.container import face_art as fa
    sq = lambda x0, y0, x1, y1: [[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]]
    ground = {"fill": "#9F2426", "rings": sq(0, 0, 1, 1)}
    side = {"fill": "#6B181A", "rings": sq(0, 0, 0.1025, 1.0)}
    out = fa.without_side({"regions": [ground, side]})
    assert [r["fill"] for r in out["regions"]] == ["#9F2426", "#9F2426"] and out["side"]["taken"][0]["fill"] == "#6B181A"
    blue = {"fill": "#1B3A8A", "rings": sq(0, 0, 0.1025, 1.0)}
    assert "side" not in fa.without_side({"regions": [ground, blue]})
    short = {"fill": "#6B181A", "rings": sq(0, 0.2, 0.1025, 1.0)}
    assert "side" not in fa.without_side({"regions": [ground, short]})


def test_142_a_cap_its_colour_cannot_end_stands_at_its_map_box_and_keeps_its_gloss():
    """(4) "caps keep the concept's gloss." 142's red cap on its red body: no colour run to end it, its outline read at
    the cap's own shine (0.062) where its map box ends at 0.354 — drawn a thin stripe. Its map box's edge stands where the
    outline's reading lies far from it; and a cap its words call glossy, its light running 25 L* or more, is drawn in it."""
    from apps.pipeline.targets.container import _glossy, closure_by_its_box
    rec = {"parts": [{"kind": "closure", "name": "glossy red cap", "box": [0.0, 0.0, 1.0, 0.354]}]}
    refused = {"refused": "its colour no different from the body's"}
    got = closure_by_its_box(rec, 0.062, refused)
    assert got["edge"] == 0.354 and got["side"] == "top" and "map box's edge" in got["by"]
    assert closure_by_its_box(rec, 0.33, refused) is refused
    assert _glossy({"finish": "high-shine lacquer", "name": "cap"}, {"spread": 34.0})
    assert not _glossy({"finish": "matte", "name": "cap"}, {"spread": 34.0})
    assert not _glossy({"finish": "gloss", "name": "cap"}, {"spread": 12.0})
