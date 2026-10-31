"""The dimension gate, after the structure step left.

This file pinned the Phase 2A-6 path behind the dimension gate (2A-6E-CORR-6, task #50): a size with no template
refused with STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED and kept what was entered, the chooser offered production
versions only, and an explicitly chosen straight tuck end 1.1 paused at the structure-confirmation step. [The clean-up
of 2026-10-04, his Q1 "remove the dormant packaging flow".] That path, its switch, its two addresses and its step are
gone; the map-first flow is the one packaging engine.

What the gate does now, on the same subject: a confirmed size — with or without the fields the retired structure
chooser posts beside it (a template, its version, the generic acceptance, inner and outer sizes) — goes straight on to
the carton's drawing and its review, with no structure candidates, no structure record and no structure step; and the
two addresses that step used answer nothing, so a design still recorded there (task 50) is left as it is. Each run
goes through the gate's own view; the worker's half is replayed with exactly what the view hands it.
"""
from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.core.models import Brand
from apps.dielines.models import DielineJob
from apps.pipeline.agents.aria import ARIAAgent
from apps.pipeline.models import ApiCallRecord, DesignTask, GeneratedImage, PackagingOutput, TaskReference
from apps.pipeline.permissions import ROLE_DESIGNER, ROLE_REVIEWER

#: a size the one live path draws (the same as test_standard_pipeline's LegacyCompatibilityTests)
SIZE = {"width_mm": 35.0, "depth_mm": 25.0, "height_mm": 95.0, "bleed_mm": 3.0, "safe_margin_mm": 4.0,
        "glue_tab_mm": 10.0, "board_thickness_mm": 0.35, "thickness_compensation": True}
#: what the retired structure chooser posted beside a size
CHOOSER = {"template": "straight_tuck_end_carton", "template_version": "1.1", "generic_accepted": True,
           "inner_mm": [34.3, 24.3, 93.6], "outer_mm": [35.4, 25.4, 95.7]}
#: what the structure path wrote on a carton's output, and nothing else does
STRUCTURE_KEYS = ("structural_selection", "structure_presentation", "entered_dimensions", "entered_panel_info",
                  "generation_error")


class DimensionGateTests(TestCase):
    def setUp(self):
        self.reviewer = User.objects.create_user("dg", "d@d.com", "pw")
        self.reviewer.groups.add(Group.objects.get_or_create(name=ROLE_REVIEWER)[0])
        self.client.force_login(self.reviewer)
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(task_text="a carton at its size", status="awaiting_dimensions",
                                              brand=brand)
        image = GeneratedImage.objects.create(task=self.task, direction_name="d", prompt_used="p", image_url="u")
        self.job = DielineJob.objects.create(template_type="straight_tuck_end_carton", scenario="B",
                                             input_json={}, extraction_result={})
        self.output = PackagingOutput.objects.create(task=self.task, spec_sheet={}, approved_image=image,
                                                     dieline_job=self.job)

    def _confirm(self, extra):
        """The size confirmed at the gate's own view; what the view hands the worker is then run as the worker runs
        it (the label copy's translation stubbed: it is a paid call)."""
        with patch("apps.pipeline.tasks.resume_aria_dimensions.delay") as delay:
            res = self.client.post(f"/api/tasks/{self.task.id}/confirm_dimensions/",
                                   data=json.dumps({"dimensions": {**SIZE, **extra}}),
                                   content_type="application/json")
        assert res.status_code == 200, res.content
        _task_id, output_id, confirmed, panel_info = delay.call_args[0]
        with patch("apps.pipeline.services.panel_translate.translate_panel_info", return_value={}):
            ARIAAgent(self.task.id).resume_after_dimensions(output_id, confirmed, panel_info_override=panel_info)
        self.task.refresh_from_db()
        self.output.refresh_from_db()
        self.job.refresh_from_db()

    def test_a_confirmed_size_goes_straight_on_to_the_cartons_drawing(self):
        calls = ApiCallRecord.objects.count()
        self._confirm({})
        assert self.task.status == "awaiting_gate_2"
        assert self.output.dieline_file
        assert self.job.structure_selection == {}
        for key in STRUCTURE_KEYS:
            assert key not in self.output.spec_sheet, key
        assert ApiCallRecord.objects.count() == calls

    def test_the_retired_choosers_fields_open_no_structure_step(self):
        self._confirm(CHOOSER)
        assert self.task.status == "awaiting_gate_2"
        assert self.job.structure_selection == {}
        for key in STRUCTURE_KEYS:
            assert key not in self.output.spec_sheet, key
        # kept with the size as it was entered, and read by nothing that selects or pauses on a structure
        assert self.output.spec_sheet["confirmed_dimensions"]["template_version"] == "1.1"

    def test_the_structure_steps_two_addresses_answer_nothing(self):
        DesignTask.objects.filter(pk=self.task.pk).update(status="awaiting_structure_confirmation")
        for step in ("confirm_structure", "approve_physical_test"):
            res = self.client.post(f"/api/tasks/{self.task.id}/{step}/", data=json.dumps({}),
                                   content_type="application/json")
            assert res.status_code == 404, (step, res.status_code)
        self.task.refresh_from_db()
        self.job.refresh_from_db()
        assert self.task.status == "awaiting_structure_confirmation"       # left as it is, as task 50 is
        assert self.job.structure_selection == {}
        assert self.job.extraction_result == {}


# ---- [His final goal, 2026-10-05 (transcribed at 32e9aaf), B1: "Do NOT search my past designs for it. An "Inside reference"
# picture slot beside the inspiration box (one or more pictures) ... followed in pattern and style, never pasted or copied
# 1:1 ... At the size step he chooses per design: as referenced (default), solid colour, or plain."] The slot on New
# design, the read of each picture for its pattern and style (once, on the ledger), Start keeping the pictures with the
# design and never sending them to an image service, the size step's choice, and the inside drawn on the carton's second
# artboard from them.

    def test_goal_1013_orientation_a_box_proposed_lying_flat_is_confirmed_and_drawn_lying_flat(self):
        """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (2): "A palette or compact lies flat: its box's front is
        the lid's face (landscape)."] A size the step proposed for a box lying flat is confirmed lying flat — from its
        own proposal, never from what the page posts — and drawn so: the die as ever, its label laid out as the box is
        seen and turned onto it, reading up the die. A box proposed standing is confirmed standing, as before."""
        import fitz
        self.output.spec_sheet = {"estimated_dimensions": {"orientation": "flat"}}
        self.output.save(update_fields=["spec_sheet"])
        with patch("apps.pipeline.tasks.resume_aria_dimensions.delay") as delay:
            res = self.client.post(f"/api/tasks/{self.task.id}/confirm_dimensions/",
                                   data=json.dumps({"dimensions": dict(SIZE, orientation="standing")}),
                                   content_type="application/json")
        assert res.status_code == 200, res.content
        _task_id, output_id, confirmed, panel_info = delay.call_args[0]
        assert confirmed["orientation"] == "flat"
        with patch("apps.pipeline.services.panel_translate.translate_panel_info", return_value={}):
            ARIAAgent(self.task.id).resume_after_dimensions(output_id, confirmed, panel_info_override=panel_info)
        self.task.refresh_from_db()
        self.job.refresh_from_db()
        assert self.task.status == "awaiting_gate_2", self.task.error_message
        assert self.job.input_json["orientation"] == "flat"
        self.output.refresh_from_db()
        drawn = self.output.design_preview_ai if self.output.design_preview_ai else self.output.production_pdf
        with fitz.open(drawn.path) as pdf:
            dirs = {tuple(round(v, 3) for v in line["dir"]) for b in pdf[0].get_text("dict")["blocks"]
                    for line in b.get("lines", [])}
        assert (0.0, -1.0) in dirs, dirs                                  # the label reads up the die

    def test_goal_1013_orientation_a_box_proposed_standing_is_confirmed_standing(self):
        with patch("apps.pipeline.tasks.resume_aria_dimensions.delay") as delay:
            res = self.client.post(f"/api/tasks/{self.task.id}/confirm_dimensions/",
                                   data=json.dumps({"dimensions": dict(SIZE, orientation="flat")}),
                                   content_type="application/json")
        assert res.status_code == 200, res.content
        assert "orientation" not in delay.call_args[0][2]


INSIDE_READING = {"pattern": "stripes", "direction": "diagonal", "density": "dense", "tone": "dark", "motif_words": "",
           "style": "thin diagonal pinstripes set close together", "take": "close diagonal pinstripes",
           "seen_not_taken": ["MAISON X"]}


def _inside_png(colour=(90, 20, 40), size=(60, 40)):
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", size, colour).save(out, format="PNG")
    return out.getvalue()


def _inside_reply(reading=INSIDE_READING):
    return MagicMock(content=[MagicMock(type="text", text=json.dumps(reading))],
                     usage=MagicMock(input_tokens=900, output_tokens=120))


class InsideReferenceTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        from apps.dashboard import board
        self.enterContext(patch.dict(board.OWNER_FOLD, {}, clear=True))
        cache.delete("pipeline:spend_estimates/2")
        self.user = User.objects.create_user("designer-inside", "inside@example.com", None)
        for role in (ROLE_DESIGNER, ROLE_REVIEWER):
            self.user.groups.add(Group.objects.get_or_create(name=role)[0])
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.client.force_login(self.user)

    def _read(self, data, name="inside.png"):
        return self.client.post("/api/inspiration/read/", {"picture": SimpleUploadedFile(name, data, "image/png"),
                                                           "kind": "inside_reference"})

    def test_new_design_offers_an_inside_reference_box_beside_the_inspiration_box(self):
        html = self.client.get("/dashboard/new/classic/").content.decode()
        assert html.index('id="inspiration-box"') < html.index('id="inside-box"')
        box = " ".join(html.split('id="inside-box"', 1)[1].split("</fieldset>", 1)[0].split())
        assert 'data-kind="inside_reference"' in box and "Inside reference" in box
        assert "never pasted, never copied" in box and "Inside: …" in box

    def test_an_inside_picture_is_read_once_for_its_pattern_and_style_and_refused_by_name(self):
        png = _inside_png()
        with patch("apps.pipeline.services.claude_service._get_client") as client, \
                override_settings(ANTHROPIC_API_KEY="k"):
            client.return_value.messages.create.return_value = _inside_reply()
            first = self._read(png)
            again = self._read(png, name="the-same.png")
            sent = client.return_value.messages.create.call_args.kwargs
        assert first.status_code == 200, first.content
        data = first.json()
        assert data["taken"]["pattern"] == "stripes" and data["words"].startswith("stripes diagonal dense")
        assert data["seen_not_taken"] == ["MAISON X"] and float(data["cost_usd"]) > 0
        assert again.json()["read_before"] is True and again.json()["cost_usd"] == "0"
        assert ApiCallRecord.objects.filter(operation="inside_read").count() == 1     # read once
        assert "PATTERN and STYLE" in sent["system"]
        pdf = self.client.post("/api/inspiration/read/", {
            "picture": SimpleUploadedFile("inside.pdf", b"%PDF-1.4\n" + b"x" * 64, "application/pdf"),
            "kind": "inside_reference"})
        assert pdf.status_code == 400 and "cannot be read as a picture" in pdf.json()["words"]

    def test_start_keeps_the_inside_pictures_and_never_sends_them_to_an_image_service(self):
        from apps.pipeline.services import reference_manifest as M
        with patch("apps.core.health.worker_available", return_value=True), \
                patch("apps.pipeline.tasks.run_aria_pipeline.delay"), \
                patch("django.db.transaction.on_commit", side_effect=lambda f: f()):
            made = self.client.post("/api/tasks/create/", {
                "task_text": "a carton for the night oil\n\nInside: thin diagonal stripes", "brand_id": self.brand.pk,
                "design_target": "packaging", "inside_reference": SimpleUploadedFile("in.png", _inside_png(), "image/png")})
        assert made.status_code == 201, made.content
        task = DesignTask.objects.get(pk=made.json()["task_id"])
        ref = TaskReference.objects.get(task=task)
        assert (ref.kind, len(ref.sha256)) == ("inside_reference", 64)
        entry = next(e for e in M.build_task_reference_manifest(task)["entries"] if e["reference_id"] == ref.pk)
        assert entry["attachment_eligibility"] == M.METADATA_ONLY and entry["preview_kind"] == "document"
        assert M._entry_lines(M.build_task_reference_manifest(task)) == []       # never in the planner's words
        with patch("apps.core.health.worker_available", return_value=True):
            odd = self.client.post("/api/tasks/create/", {
                "task_text": "x", "brand_id": self.brand.pk, "design_target": "packaging",
                "inside_reference": SimpleUploadedFile("in.pdf", b"%PDF-1.4\n" + b"x" * 64, "application/pdf")})
        assert (odd.status_code, odd.json()["error"]) == (400, "INSIDE_PICTURES_REFUSED"), odd.content
        assert "cannot be read as a picture" in odd.json()["words"]

    def _carton_at_its_size(self, brief):
        task = DesignTask.objects.create(task_text=brief, status="awaiting_dimensions", brand=self.brand)
        image = GeneratedImage.objects.create(task=task, direction_name="d", prompt_used="p", image_url="u")
        job = DielineJob.objects.create(template_type="straight_tuck_end_carton", scenario="B", input_json={},
                                        extraction_result={})
        output = PackagingOutput.objects.create(task=task, spec_sheet={}, approved_image=image, dieline_job=job)
        return task, output

    def _confirm(self, task, inside=None):
        size = {"width_mm": 35.0, "depth_mm": 25.0, "height_mm": 95.0, "bleed_mm": 3.0, "safe_margin_mm": 4.0,
                "glue_tab_mm": 10.0, "board_thickness_mm": 0.35, "thickness_compensation": True}
        body = {"dimensions": size, **({"inside_print": inside} if inside is not None else {})}
        with patch("apps.pipeline.tasks.resume_aria_dimensions.delay") as delay:
            res = self.client.post(f"/api/tasks/{task.id}/confirm_dimensions/", data=json.dumps(body),
                                   content_type="application/json")
        return res, delay

    def test_the_size_step_takes_his_choice_of_inside_and_refuses_any_other_by_name(self):
        task, _output = self._carton_at_its_size("a carton")
        res, _delay = self._confirm(task, "glitter")
        assert res.status_code == 400 and res.json()["error"] == "INSIDE_PRINT_UNKNOWN"
        res, delay = self._confirm(task, "solid")
        assert res.status_code == 200 and delay.call_args[0][2]["inside_print"] == "solid"
        task2, _o = self._carton_at_its_size("a carton")
        res, delay = self._confirm(task2)
        assert delay.call_args[0][2]["inside_print"] == "referenced"                 # as referenced, by default

    def test_the_inside_is_drawn_from_his_picture_and_his_words_on_the_cartons_second_artboard(self):
        import fitz

        from apps.ire.compose import INSIDE_KEY
        task, output = self._carton_at_its_size("A carton.\n\nInside: dense stripes, diagonal.")
        ref = TaskReference(task=task, kind="inside_reference", original_filename="in.png", media_type="image/png",
                            file_size=10, ordering=0, source="USER_UPLOAD", status="REFERENCE_ONLY")
        from django.core.files.base import ContentFile
        ref.image.save("in.png", ContentFile(_inside_png()), save=True)
        res, delay = self._confirm(task)
        _tid, output_id, confirmed, panel_info = delay.call_args[0]
        with patch("apps.pipeline.services.panel_translate.translate_panel_info", return_value={}), \
                patch("apps.pipeline.services.claude_service._get_client") as client, \
                override_settings(ANTHROPIC_API_KEY="k"):
            client.return_value.messages.create.return_value = _inside_reply(dict(INSIDE_READING, density="sparse"))
            ARIAAgent(task.id).resume_after_dimensions(output_id, confirmed, panel_info_override=panel_info)
        output.refresh_from_db()
        record = output.spec_sheet[INSIDE_KEY]
        # his picture read once at the size step (it was never read on the start page); his words win on density
        assert (record["pattern"], record["direction"], record["density"]) == ("stripes", "diagonal", "dense")
        assert record["source"] == "his inside reference and his brief's words" and record["preview"]
        assert ApiCallRecord.objects.filter(operation="inside_read", task=task).count() == 1
        with fitz.open(output.design_preview_ai.path) as drawn:
            assert drawn.page_count >= 2 and drawn[1].get_images() == []
        from apps.pipeline.serializers import PackagingOutputSerializer
        assert PackagingOutputSerializer(output).data["design_inside_url"].endswith(".png")

    def test_a_complete_products_inside_pictures_go_on_to_its_carton(self):
        from django.core.files.base import ContentFile

        from apps.pipeline.targets.composite import _attach_handoff
        up = DesignTask.objects.create(task_text="vial", brand=self.brand, status="completed")
        down = DesignTask.objects.create(task_text="carton", brand=self.brand, status="queued")
        ref = TaskReference(task=up, kind="inside_reference", original_filename="in.png", media_type="image/png",
                            file_size=10, ordering=0, source="USER_UPLOAD", status="REFERENCE_ONLY", sha256="ab" * 32)
        ref.image.save("in.png", ContentFile(_inside_png()), save=True)
        _attach_handoff(down, up)
        assert down.references.filter(kind="inside_reference", sha256="ab" * 32).count() == 1


# ---- [his final goal, 2026-10-05, C5: "Only if it still doesn't fit, STOP and offer: a wider carton, the info printed
# on the inside, or fewer languages."] — [his second goal of 2026-10-06, item 1] the carton is widened by itself, said;
# the info is never printed inside

class LabelOfferTests(TestCase):
    INFO = {"product_name": "Rose Glaze Lip Gloss", "description": "A glossy, lightweight lip gloss with a soft rose "
            "shine.", "ingredients": "Polybutene, Hydrogenated Polyisobutene, Silica Dimethyl Silylate, Parfum, "
            "Tocopheryl Acetate, CI 15850.", "how_to_use": "Apply to lips alone or over lipstick.",
            "warnings": "For external use only. Avoid contact with eyes. Discontinue use if irritation occurs.",
            "net_weight": "8 ml ℮ 0.27 fl. oz.", "item_no": "RG-001", "qr_url": "https://www.bbrose.com",
            "regulatory_text": "Made in UAE."}
    TRANSLATIONS = {"es": {"description": "Un gloss labial brillante y ligero.", "ingredients": "Polybutene, "
                           "Hydrogenated Polyisobutene, Silica Dimethyl Silylate, Parfum, Tocopheryl Acetate, CI 15850.",
                           "how_to_use": "Aplicar en los labios.", "warnings": "Solo para uso externo. Evitar el "
                           "contacto con los ojos. Suspender el uso si se produce irritación."},
                    "ar": {"description": "غلوس شفاه لامع وخفيف الوزن.", "how_to_use": "يُطبَّق على الشفتين.",
                           "warnings": "للاستخدام الخارجي فقط. تجنب ملامسة العيون."}}

    def setUp(self):
        self.reviewer = User.objects.create_user("offer", "o@o.com", "pw")
        self.reviewer.groups.add(Group.objects.get_or_create(name=ROLE_REVIEWER)[0])
        self.client.force_login(self.reviewer)
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(task_text="a 22 mm carton", status="awaiting_dimensions", brand=brand)
        image = GeneratedImage.objects.create(task=self.task, direction_name="d", prompt_used="p", image_url="u")
        self.job = DielineJob.objects.create(template_type="straight_tuck_end_carton", scenario="B", input_json={},
                                             extraction_result={})
        self.output = PackagingOutput.objects.create(task=self.task, spec_sheet={}, approved_image=image,
                                                     dieline_job=self.job)

    def _make(self, confirmed, override):
        with patch("apps.pipeline.services.panel_translate.translate_panel_info",
                   return_value=self.TRANSLATIONS) as translate:
            ARIAAgent(self.task.id).resume_after_dimensions(self.output.id, confirmed, panel_info_override=override)
        self.task.refresh_from_db()
        self.output.refresh_from_db()
        return translate

    def test_a_label_that_does_not_fit_shrinks_evenly_on_the_carton_he_confirmed(self):
        """[His correction of 2026-10-07 (transcribed at a6b2092): "when the label doesn't fit, the text gets SMALLER
        ... Never widen the carton for text".] The 22 mm carton whose label does not stand at its largest size: drawn at
        22 mm, the size it was made at the size he confirmed, its label shrunk evenly — the body and the fine print at
        one size, not under 3 pt — nothing spent past the one translation, no offer waiting; a size that once chose the
        info printed inside is drawn with everything on the sticker."""
        from apps.ire.compose import BACK_COPY_KEY
        size = {"width_mm": 22.0, "depth_mm": 22.0, "height_mm": 105.0, "bleed_mm": 3.0, "safe_margin_mm": 4.0,
                "glue_tab_mm": 10.0, "board_thickness_mm": 0.45, "thickness_compensation": True,
                "inside_print": "referenced", "label_inside": True}
        translate = self._make(size, dict(self.INFO))
        assert translate.call_count == 1 and self.task.status == "awaiting_gate_2"
        spec = self.output.spec_sheet
        record = spec[BACK_COPY_KEY]
        lv = record["levels_pt"]
        assert record["codes"] == [] and "widened" not in record and "inside_label" not in record, record
        assert 3.0 <= lv["body"] < 7.0 and lv["fine"] == lv["body"], lv
        assert spec["confirmed_dimensions"]["width_mm"] == 22.0 and "width_confirmed_mm" not in spec[
            "confirmed_dimensions"] and "label_inside" not in spec["confirmed_dimensions"]
        self.job.refresh_from_db()
        assert self.job.input_json["dimensions"]["width_mm"] == 22.0
        # [his second goal of 2026-10-06, item 2] a job made as a straight tuck end, drawn again, names its style now
        assert self.job.template_type == self.job.input_json["template"] == "reverse_tuck_end_carton"
        assert "label_offers/1.0" not in spec
        assert not self.task.logs.filter(action__contains="mm wide, not").exists()
        # nothing waits on a choice: the door says so
        none = self.client.post(f"/api/tasks/{self.task.id}/label_offer/", data=json.dumps({"offer": "fewer_languages",
                                "languages": ["en"]}), content_type="application/json")
        assert (none.status_code, none.json()["error"]) == (409, "LABEL_OFFER_NOT_OPEN")

    def test_the_info_printed_inside_is_refused_at_the_door_even_on_an_old_stopped_record(self):
        """[His second goal of 2026-10-06, item 1: "remove "info printed inside" as an option"; his correction of
        2026-10-07: "Never widen the carton for text"] a record stopped before the rules, its offers still naming the
        inside and a wider carton: the door refuses each by name and takes nothing."""
        from apps.ire.compose import BACK_COPY_KEY, LABEL_DOES_NOT_FIT
        self.task.status = "awaiting_gate_2"
        self.task.save()
        self.output.spec_sheet = {BACK_COPY_KEY: {"codes": [LABEL_DOES_NOT_FIT], "offers": {
            "wider": {"width_mm": 33}, "info_inside": {"columns": [{"panel": "front", "languages": ["en"]}]}}},
            "confirmed_dimensions": {"width_mm": 22.0, "depth_mm": 22.0, "height_mm": 105.0}}
        self.output.save()
        # [his correction of 2026-10-07: "Never widen the carton for text"] nor a wider carton
        for offer in ("info_inside", "wider"):
            with patch("apps.pipeline.tasks.resume_aria_dimensions.delay") as delay:
                took = self.client.post(f"/api/tasks/{self.task.id}/label_offer/",
                                        data=json.dumps({"offer": offer}), content_type="application/json")
            assert (took.status_code, took.json()["error"]) == (400, "LABEL_OFFER_UNKNOWN") and not delay.called, offer
            self.task.refresh_from_db()
            assert self.task.status == "awaiting_gate_2"


# ---- [his final goal, 2026-10-05, B3: "THE BACK INFO IS A STICKER, his choice at the size step ... Custom sticker:
# follows a sticker reference picture or the brief's words."]

class BackInfoChoiceTests(TestCase):
    setUp = InsideReferenceTests.setUp                      # the same reviewer and brand; none of its tests run twice
    _carton_at_its_size = InsideReferenceTests._carton_at_its_size

    def test_the_size_step_takes_his_choice_of_the_back_info_and_refuses_any_other_by_name(self):
        task, _output = self._carton_at_its_size("a carton")
        with patch("apps.pipeline.tasks.resume_aria_dimensions.delay") as delay:
            bad = self.client.post(f"/api/tasks/{task.id}/confirm_dimensions/", content_type="application/json",
                                   data=json.dumps({"dimensions": {"width_mm": 35.0, "depth_mm": 25.0,
                                                                   "height_mm": 95.0}, "back_info": "glossy"}))
            good = self.client.post(f"/api/tasks/{task.id}/confirm_dimensions/", content_type="application/json",
                                    data=json.dumps({"dimensions": {"width_mm": 35.0, "depth_mm": 25.0,
                                                                    "height_mm": 95.0}, "back_info": "custom"}))
        assert (bad.status_code, bad.json()["error"]) == (400, "BACK_INFO_UNKNOWN")
        assert good.status_code == 200 and delay.call_args[0][2]["back_info"] == "custom"

    def test_a_custom_sticker_follows_his_sticker_picture_under_his_words(self):
        from django.core.files.base import ContentFile

        from apps.ire.compose import BACK_COPY_KEY
        task, output = self._carton_at_its_size("A carton.\n\nSticker: with a double border.\n\nBack copy: How to use: "
                                                "Smooth over lips. / Ingredients: Aqua, Glycerin.")
        ref = TaskReference(task=task, kind="sticker_reference", original_filename="s.png", media_type="image/png",
                            file_size=10, ordering=0, source="USER_UPLOAD", status="REFERENCE_ONLY")
        ref.image.save("s.png", ContentFile(_inside_png((20, 90, 40))), save=True)
        with patch("apps.pipeline.tasks.resume_aria_dimensions.delay") as delay:
            self.client.post(f"/api/tasks/{task.id}/confirm_dimensions/", content_type="application/json",
                             data=json.dumps({"dimensions": {"width_mm": 60.0, "depth_mm": 30.0, "height_mm": 120.0,
                                                             "bleed_mm": 3.0, "safe_margin_mm": 4.0, "glue_tab_mm": 10.0},
                                              "back_info": "custom"}))
        _tid, output_id, confirmed, panel_info = delay.call_args[0]
        reading = {"shape": "arch", "fill": "light", "border": "thin", "style": "a tall arch", "take": "an arch",
                   "seen_not_taken": []}
        with patch("apps.pipeline.services.panel_translate.translate_panel_info", return_value={}), \
                patch("apps.pipeline.services.claude_service._get_client") as client, \
                override_settings(ANTHROPIC_API_KEY="k"):
            client.return_value.messages.create.return_value = _inside_reply(reading)
            ARIAAgent(task.id).resume_after_dimensions(output_id, confirmed, panel_info_override=panel_info)
        output.refresh_from_db()
        style = output.spec_sheet[BACK_COPY_KEY]["back_info"]
        assert (style["mode"], style["shape"], style["fill"], style["border"]) == ("custom", "arch", "light", "double")
        assert style["source"] == "his sticker reference and his brief's words"
        assert ApiCallRecord.objects.filter(operation="sticker_read", task=task).count() == 1
