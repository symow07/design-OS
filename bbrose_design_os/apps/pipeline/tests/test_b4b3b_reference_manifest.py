"""B4b-3B — pipeline reference manifest, resolver and front-half integration.

The manifest is deterministic metadata with opaque locators; the resolver is
the single controlled door to reference bytes; the front half (Creative
Director, Prompt Engineer, Image Producer) consumes categories and
REFERENCE-ONLY semantics without ever seeing a path, a URL or a byte. Missing
owner-supplied content is never silently dropped — it refuses the spend with
a stable code before any provider call.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.core.models import Brand
from apps.pipeline.models import AgentLog, DesignTask, TaskReference
from apps.pipeline.review_board import build_review_board
from apps.pipeline.services import reference_manifest as rm

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4\n" + b"x" * 64
EPS = b"%!PS-Adobe-3.0 EPSF-3.0\n" + b"x" * 64


@pytest.fixture
def brand(db):
    return Brand.objects.create(name="BBROSE", master_brief="x")


@pytest.fixture
def owner(django_user_model):
    from apps.pipeline.permissions import ROLE_DESIGNER
    u = django_user_model.objects.create_user("b4b3b", password="x")
    u.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
    return u


def make_task(brand, target="product_container", **kw):
    return DesignTask.objects.create(
        brand=brand, task_text="a serum bottle", design_target=target, **kw)


def add_ref(task, kind, filename, data=PNG, media_type="image/png",
            ordering=0):
    ref = TaskReference(task=task, kind=kind, original_filename=filename,
                       media_type=media_type, file_size=len(data),
                       ordering=ordering)
    ref.image.save(filename, ContentFile(data), save=True)
    return ref


def mixed_task(brand):
    """container png, logo png, label pdf, inspiration webp, color jpeg."""
    task = make_task(brand)
    add_ref(task, "color", "chips.jpg", b"\xff\xd8\xff" + b"\x00" * 64,
            "image/jpeg", 4)
    add_ref(task, "container", "bottle.png", PNG, "image/png", 0)
    add_ref(task, "label", "sheet.pdf", PDF, "application/pdf", 2)
    add_ref(task, "logo", "mark.png", PNG, "image/png", 1)
    add_ref(task, "inspiration", "mood.webp",
            b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 64, "image/webp", 3)
    return task


# ===========================================================================
# §22 — manifest
# ===========================================================================


class TestManifest:

    def test_schema_is_versioned(self, brand):
        m = rm.build_task_reference_manifest(make_task(brand))
        assert m["schema"] == "design_os.task_reference_manifest/1.0"

    def test_empty_task_produces_a_valid_empty_manifest(self, brand):
        m = rm.build_task_reference_manifest(make_task(brand))
        assert m["reference_count"] == 0
        assert m["entries"] == []
        assert m["counts_by_category"] == {
            "container": 0, "logo": 0, "label": 0, "inspiration": 0,
            "color": 0}
        assert m["design_target"] == "product_container"

    def test_five_categories_in_fixed_order(self, brand):
        m = rm.build_task_reference_manifest(mixed_task(brand))
        assert [e["category"] for e in m["entries"]] == [
            "container", "logo", "label", "inspiration", "color"]
        assert m["reference_count"] == 5
        assert m["counts_by_category"] == {
            "container": 1, "logo": 1, "label": 1, "inspiration": 1,
            "color": 1}

    def test_item_ordering_matches_the_review_board(self, brand):
        task = make_task(brand)
        add_ref(task, "container", "z.png", ordering=1)
        add_ref(task, "container", "a.png", ordering=2)
        add_ref(task, "logo", "m.png", ordering=0)
        m = rm.build_task_reference_manifest(task)
        board = build_review_board(task)
        assert [e["reference_id"] for e in m["entries"]] == \
            [r.id for r in board.references]

    def test_color_key_and_colour_label(self, brand):
        task = make_task(brand)
        add_ref(task, "color", "chips.png")
        (e,) = rm.build_task_reference_manifest(task)["entries"]
        assert e["category"] == "color"
        assert e["category_label"] == "Colour Reference"

    def test_duplicate_filenames_stay_independent(self, brand):
        task = make_task(brand)
        r1 = add_ref(task, "container", "logo.png", ordering=0)
        r2 = add_ref(task, "container", "logo.png", ordering=1)
        entries = rm.build_task_reference_manifest(task)["entries"]
        assert [e["reference_id"] for e in entries] == [r1.id, r2.id]
        assert [e["original_filename"] for e in entries] == \
            ["logo.png", "logo.png"]

    def test_entry_metadata_is_the_persisted_row(self, brand):
        task = make_task(brand)
        ref = add_ref(task, "container", "bottle.png")
        (e,) = rm.build_task_reference_manifest(task)["entries"]
        assert e["original_filename"] == "bottle.png"
        assert e["media_type"] == "image/png"
        assert e["file_size"] == len(PNG)
        assert e["source"] == "USER_UPLOAD"
        assert e["status"] == "REFERENCE_ONLY"
        assert e["uploaded_at"] == ref.created_at.isoformat()
        assert e["preview_kind"] == "raster"
        assert e["availability"] == "AVAILABLE"

    def test_locator_is_opaque(self, brand):
        task = make_task(brand)
        ref = add_ref(task, "container", "bottle.png")
        (e,) = rm.build_task_reference_manifest(task)["entries"]
        assert e["content_locator"] == {
            "kind": "task_reference", "task_id": task.id,
            "reference_id": ref.id}

    def test_manifest_carries_no_path_url_or_bytes(self, brand):
        dump = json.dumps(rm.build_task_reference_manifest(mixed_task(brand)))
        for banned in ("/media/", "task_refs/", "http://", "https://",
                       "/Users/", "/var/", "base64", "MEDIA_URL"):
            assert banned not in dump

    def test_usage_semantics_and_forbidden_inferences(self, brand):
        m = rm.build_task_reference_manifest(mixed_task(brand))
        by_cat = {e["category"]: e for e in m["entries"]}
        assert "dimension_inference" in \
            by_cat["container"]["usage_policy"]["forbidden"]
        assert "image_trace" in by_cat["logo"]["usage_policy"]["forbidden"]
        assert "print_zone_confirmation" in \
            by_cat["label"]["usage_policy"]["forbidden"]
        assert "competitor_identity_copy" in \
            by_cat["inspiration"]["usage_policy"]["forbidden"]
        assert "pantone_inference" in \
            by_cat["color"]["usage_policy"]["forbidden"]
        for e in m["entries"]:
            assert "production_authority" in \
                e["usage_policy"]["forbidden"]
            assert "visual_guidance" in e["usage_policy"]["allowed"]
            assert e["usage_policy"]["guidance"]

    def test_build_performs_no_file_read(self, brand):
        task = mixed_task(brand)
        from django.core.files.storage import FileSystemStorage

        def boom(*a, **k):
            raise AssertionError("manifest build opened a file")
        with patch.object(FileSystemStorage, "open", boom), \
             patch("builtins.open", side_effect=AssertionError(
                 "manifest build opened a file")):
            m = rm.build_task_reference_manifest(task)
        assert m["reference_count"] == 5

    def test_missing_stored_content_is_represented_safely(self, brand):
        task = make_task(brand)
        ref = add_ref(task, "container", "bottle.png")
        ref.image.storage.delete(ref.image.name)
        (e,) = rm.build_task_reference_manifest(task)["entries"]
        assert e["availability"] == "MISSING"
        assert e["attachment_eligibility"] == "ELIGIBLE_RASTER"

    def test_documents_are_metadata_only(self, brand):
        task = make_task(brand)
        add_ref(task, "label", "sheet.pdf", PDF, "application/pdf", 0)
        add_ref(task, "label", "cut.eps", EPS, "application/postscript", 1)
        add_ref(task, "logo", "mark.ai", EPS,
                "application/vnd.adobe.illustrator", 2)
        entries = rm.build_task_reference_manifest(task)["entries"]
        assert all(e["attachment_eligibility"] ==
                   "METADATA_ONLY_FOR_CURRENT_IMAGE_STAGE" for e in entries)
        assert all(e["preview_kind"] == "document" for e in entries)

    def test_query_count_is_flat(self, brand):
        one = make_task(brand)
        add_ref(one, "container", "a.png")
        many = mixed_task(brand)
        add_ref(many, "container", "extra1.png", ordering=10)
        add_ref(many, "container", "extra2.png", ordering=11)
        with CaptureQueriesContext(connection) as q1:
            rm.build_task_reference_manifest(one)
        with CaptureQueriesContext(connection) as q7:
            rm.build_task_reference_manifest(many)
        assert len(q7) == len(q1)

    def test_repeated_builds_are_equal(self, brand):
        task = mixed_task(brand)
        assert rm.build_task_reference_manifest(task) == \
            rm.build_task_reference_manifest(task)


# ===========================================================================
# §23 — resolver
# ===========================================================================


class TestResolver:

    def test_valid_resolution_returns_controlled_content(self, brand):
        task = make_task(brand)
        ref = add_ref(task, "container", "bottle.png")
        c = rm.resolve_task_reference_content(task_id=task.id,
                                              reference_id=ref.id)
        assert c.reference_id == ref.id and c.task_id == task.id
        assert c.category == "container"
        assert c.filename == "bottle.png"
        assert c.media_type == "image/png"
        assert c.file_size == len(PNG)
        assert c.stream.read() == PNG
        assert c.stream.name == "bottle.png"     # safe name, not a path
        assert not hasattr(c, "path")
        assert not any("url" in f.lower() for f in vars(c))

    def test_task_reference_mismatch_is_rejected(self, brand):
        t1, t2 = make_task(brand), make_task(brand)
        ref = add_ref(t1, "container", "bottle.png")
        with pytest.raises(rm.ReferenceResolutionError) as e:
            rm.resolve_task_reference_content(task_id=t2.id,
                                              reference_id=ref.id)
        assert e.value.code == rm.REFERENCE_CONTENT_UNAVAILABLE

    def test_missing_reference_and_missing_task_are_rejected(self, brand):
        task = make_task(brand)
        with pytest.raises(rm.ReferenceResolutionError):
            rm.resolve_task_reference_content(task_id=task.id,
                                              reference_id=999999)
        with pytest.raises(rm.ReferenceResolutionError):
            rm.resolve_task_reference_content(task_id=999999,
                                              reference_id=1)

    def test_missing_stored_content_is_rejected(self, brand):
        task = make_task(brand)
        ref = add_ref(task, "container", "bottle.png")
        ref.image.storage.delete(ref.image.name)
        with pytest.raises(rm.ReferenceResolutionError) as e:
            rm.resolve_task_reference_content(task_id=task.id,
                                              reference_id=ref.id)
        assert e.value.code == rm.REFERENCE_CONTENT_UNAVAILABLE
        assert "task_refs" not in str(e.value)
        assert "/" not in str(e.value).replace("/", "", 0) or \
            "media" not in str(e.value)

    def test_tampered_traversal_path_is_rejected(self, brand, settings,
                                                 tmp_path):
        outside = tmp_path / "outside.png"
        outside.write_bytes(PNG)
        task = make_task(brand)
        ref = add_ref(task, "container", "bottle.png")
        TaskReference.objects.filter(pk=ref.pk).update(
            image="task_refs/../../" + outside.name)
        with pytest.raises(rm.ReferenceResolutionError):
            rm.resolve_task_reference_content(task_id=task.id,
                                              reference_id=ref.id)

    def test_unsupported_stored_media_type_is_rejected(self, brand):
        task = make_task(brand)
        ref = add_ref(task, "container", "page.html", b"<html>",
                      "text/html")
        with pytest.raises(rm.ReferenceResolutionError):
            rm.resolve_task_reference_content(task_id=task.id,
                                              reference_id=ref.id)

    def test_non_reference_only_status_is_rejected(self, brand):
        task = make_task(brand)
        ref = add_ref(task, "container", "bottle.png")
        TaskReference.objects.filter(pk=ref.pk).update(status="SOMETHING")
        with pytest.raises(rm.ReferenceResolutionError):
            rm.resolve_task_reference_content(task_id=task.id,
                                              reference_id=ref.id)

    def test_oversized_recorded_metadata_is_rejected(self, brand, settings):
        settings.REFERENCE_MAX_UPLOAD_BYTES = 16
        task = make_task(brand)
        ref = add_ref(task, "container", "bottle.png")   # 72 bytes > 16
        with pytest.raises(rm.ReferenceResolutionError):
            rm.resolve_task_reference_content(task_id=task.id,
                                              reference_id=ref.id)

    def test_size_mismatch_is_rejected(self, brand):
        task = make_task(brand)
        ref = add_ref(task, "container", "bottle.png")
        TaskReference.objects.filter(pk=ref.pk).update(
            file_size=len(PNG) - 3)
        with pytest.raises(rm.ReferenceResolutionError):
            rm.resolve_task_reference_content(task_id=task.id,
                                              reference_id=ref.id)

    def test_only_the_requested_file_is_opened(self, brand):
        task = make_task(brand)
        ref = add_ref(task, "container", "bottle.png", ordering=0)
        add_ref(task, "logo", "mark.png", ordering=1)
        opened = []
        real_open = open

        def counting_open(path, *a, **k):
            opened.append(str(path))
            return real_open(path, *a, **k)
        with patch("builtins.open", counting_open):
            rm.resolve_task_reference_content(task_id=task.id,
                                              reference_id=ref.id)
        file_opens = [p for p in opened if "task_refs" in p]
        assert len(file_opens) == 1

    def test_no_provider_call_during_resolution(self, brand):
        task = make_task(brand)
        ref = add_ref(task, "container", "bottle.png")
        with patch("openai.images") as images, \
             patch("apps.pipeline.services.claude_service.call_claude") as cc:
            rm.resolve_task_reference_content(task_id=task.id,
                                              reference_id=ref.id)
        images.edit.assert_not_called()
        images.generate.assert_not_called()
        cc.assert_not_called()


# ===========================================================================
# §24 — pipeline context
# ===========================================================================


def _stub_target():
    target = MagicMock()
    target.concept_prompt_profile.return_value = ""
    target.concept_structure_id.return_value = None
    target.gate1_variation_plan.return_value = None
    return target


class TestPipelineContext:

    def _aria(self, task):
        from apps.pipeline.agents.aria import ARIAAgent
        return ARIAAgent(task.id)

    def test_queue_payload_is_the_task_id_alone(self, brand, owner):
        from django.test import Client
        c = Client()
        c.force_login(owner)
        with patch("apps.core.health.worker_available", return_value=True), \
             patch("apps.pipeline.services.cost_ledger.daily_budget_exceeded",
                   return_value=False), \
             patch("apps.pipeline.tasks.run_aria_pipeline.delay") as delay:
            from django.test.utils import CaptureQueriesContext as _C  # noqa
            with patch("django.db.transaction.on_commit",
                       side_effect=lambda f: f()):
                r = c.post("/api/tasks/create/", {
                    "task_text": "a serum bottle", "brand_id": brand.id,
                    "design_target": "product_container",
                    "container": ContentFile(PNG, name="a.png")})
        assert r.status_code == 201
        (args, kwargs) = delay.call_args
        assert args == (r.json()["task_id"],) and not kwargs

    def test_creative_director_receives_category_distinctions(self, brand):
        task = mixed_task(brand)
        aria = self._aria(task)
        captured = {}

        class StubCD:
            def __init__(self, *a, **k):
                captured["instance"] = self

            def run_structured(self):
                captured["context"] = self.uploaded_reference_context
                return MagicMock(ok=False, codes=["STOP_FOR_TEST"])

            def _brief(self):
                return "brief"
        with patch("apps.pipeline.agents.aria.CreativeDirectorAgent", StubCD), \
             patch.object(type(aria), "_product_profile",
                          return_value={}), \
             patch.object(type(aria), "_target",
                          return_value=_stub_target()):
            aria._run_direction_planning()
        ctx = captured["context"]
        for label in ("Container Reference", "Brand Logo",
                      "Existing Label or Artwork", "Visual Inspiration",
                      "Colour Reference"):
            assert label in ctx
        assert "REFERENCE ONLY" in ctx
        assert "never infer dimensions" in ctx
        # §12: no storage paths, URLs or bytes in the reasoning text
        for banned in ("/media/", "task_refs/", "http", "base64"):
            assert banned not in ctx
        # §17: the manifest was audit-logged with the run
        log = AgentLog.objects.filter(
            task=task, action__contains="reference manifest built").first()
        assert log is not None
        assert log.payload["schema"] == rm.MANIFEST_SCHEMA
        assert log.payload["reference_count"] == 5

    def test_prompt_engineer_generic_path_receives_context(self, brand):
        task = mixed_task(brand)
        aria = self._aria(task)
        captured = {}

        class StubPE:
            def __init__(self, *a, **k):
                pass

            def run(self):
                captured["context"] = self.uploaded_reference_context
                return []          # 0 prompts → clean fail, no image stage
        with patch("apps.pipeline.agents.aria.PromptEngineerAgent", StubPE), \
             patch.object(type(aria), "_product_profile",
                          return_value={}), \
             patch.object(type(aria), "_target",
                          return_value=_stub_target()):
            aria._render_variations(
                {"name": "Rose", "direction_id": "A"})
        ctx = captured["context"]
        assert "Container Reference" in ctx and "Colour Reference" in ctx
        assert "REFERENCE ONLY" in ctx
        # §13: technical terms appear ONLY inside the prohibition sentence —
        # never as affirmative claims
        assert "never infer dimensions" in ctx
        assert "supplier compatibility" in ctx.split("never infer", 1)[1]
        low = ctx.lower()
        for affirmative in ("production-ready", "confirmed material",
                            "approved production specification."):
            # the only allowed appearance is inside the negation
            assert affirmative not in low.split("never", 1)[0]

    def test_pe_prompt_text_carries_the_block(self, brand):
        from apps.pipeline.agents.prompt_engineer import PromptEngineerAgent
        task = mixed_task(brand)
        pe = PromptEngineerAgent([{"name": "Rose"}], None,
                                 variation_mode=True)
        pe.uploaded_reference_context = rm.prompt_engineer_reference_context(
            rm.build_task_reference_manifest(task))
        captured = {}

        def fake_call(system, message, **kw):
            captured["message"] = message
            return object()          # opaque; extract_json is stubbed below
        with patch("apps.pipeline.agents.prompt_engineer.call_claude",
                   fake_call), \
             patch("apps.pipeline.agents.prompt_engineer.extract_json",
                   return_value={"prompts": []}):
            pe.run()
        assert "Owner-uploaded references (REFERENCE ONLY)" in \
            captured["message"]
        assert "bottle.png" in captured["message"]

    def test_container_structured_prompt_context_via_product_block(
            self, brand):
        task = mixed_task(brand)
        aria = self._aria(task)
        from apps.pipeline.targets import get_target
        target = get_target("product_container")
        captured = {}

        def fake_build(**kwargs):
            captured.update(kwargs)
            return MagicMock(ok=False, prompts=[], codes=("STOP",),
                             attempts=0, raw_responses=(), payload=None,
                             provider_model="")
        with patch("apps.pipeline.services.gate1_prompts."
                   "build_regeneration_prompts", fake_build), \
             patch.object(type(aria), "_product_profile", return_value={}):
            target.gate1_variation_plan(aria, {"name": "Rose",
                                               "direction_id": "A"})
        block = captured["product_block"]
        assert "OWNER-UPLOADED REFERENCES (REFERENCE ONLY)" in block
        assert "Container Reference" in block and "bottle.png" in block

    def test_empty_references_leave_contexts_none(self, brand):
        task = make_task(brand)
        aria = self._aria(task)
        manifest = aria._reference_manifest()
        assert manifest["reference_count"] == 0
        assert rm.creative_director_reference_context(manifest) is None
        assert rm.prompt_engineer_reference_context(manifest) is None

    def test_packaging_gets_no_reference_context_or_attachments(self, brand):
        from apps.pipeline.services.visual_reference_resolver import (
            resolve_visual_references)
        task = make_task(brand, target="packaging")
        # even with rows planted directly, the ARIA manifest stays empty for
        # non-container targets (§19)
        add_ref(task, "container", "planted.png")
        aria = self._aria(task)
        assert aria._reference_manifest() == {}
        assert rm.prompt_engineer_reference_context({}) is None
        clean = make_task(brand, target="packaging")
        bundle = resolve_visual_references(clean)
        assert bundle.upload_paths == [] and not bundle.logo_is_uploaded
        assert bundle.upload_content_errors == []

    def test_eligible_rasters_become_ordered_attachments(self, brand):
        from apps.pipeline.services.visual_reference_resolver import (
            resolve_visual_references)
        task = mixed_task(brand)
        bundle = resolve_visual_references(task)
        # logo led out separately; grounding keeps manifest (category) order;
        # the PDF is metadata-only and never appears
        assert bundle.logo_is_uploaded is True
        names = [p.rsplit("/", 1)[-1] for p in bundle.upload_paths]
        assert len(names) == 3
        assert names[0].startswith("bottle")
        assert names[1].startswith("mood")
        assert names[2].startswith("chips")
        assert not any(n.endswith(".pdf") for n in names)
        assert bundle.upload_content_errors == []

    def test_documents_are_never_converted(self, brand):
        m = rm.build_task_reference_manifest(mixed_task(brand))
        atts = rm.raster_attachment_descriptors(m)
        assert all(a.media_type in ("image/png", "image/jpeg", "image/webp")
                   for a in atts)
        assert len(atts) == 4          # 5 refs, 1 pdf excluded

    def test_duplicate_reference_ids_attach_once(self, brand):
        task = make_task(brand)
        ref = add_ref(task, "container", "bottle.png")
        m = rm.build_task_reference_manifest(task)
        m["entries"].append(dict(m["entries"][0]))     # simulated duplicate
        atts = rm.raster_attachment_descriptors(m)
        assert [a.reference_id for a in atts] == [ref.id]

    def test_missing_eligible_content_stops_before_provider_dispatch(
            self, brand):
        from apps.pipeline.agents.image_producer import ImageProducerAgent
        from apps.pipeline.services.visual_reference_resolver import (
            resolve_visual_references)
        task = mixed_task(brand)
        gone = task.references.get(kind="inspiration")
        gone.image.storage.delete(gone.image.name)
        bundle = resolve_visual_references(task)
        assert bundle.upload_content_errors and \
            bundle.upload_content_errors[0]["code"] == \
            rm.REFERENCE_CONTENT_UNAVAILABLE
        assert bundle.upload_content_errors[0]["original_filename"] == \
            "mood.webp"
        ip = ImageProducerAgent(task, [{"full_prompt": "x"}], bundle=bundle)
        with patch("apps.pipeline.agents.image_producer.openai") as fake:
            images = ip.run()
        assert images == []
        fake.images.edit.assert_not_called()
        fake.images.generate.assert_not_called()
        # the refusal is recorded with the stable code (§16/§18)
        assert AgentLog.objects.filter(
            task=task,
            action__contains=rm.REFERENCE_CONTENT_UNAVAILABLE).exists() or \
            AgentLog.objects.filter(
                task=task, action__contains="pre-spend").exists()

    def test_no_provider_call_in_manifest_only_flows(self, brand):
        task = mixed_task(brand)
        with patch("openai.images") as images, \
             patch("apps.pipeline.services.claude_service.call_claude") as cc:
            rm.build_task_reference_manifest(task)
            rm.creative_director_reference_context(
                rm.build_task_reference_manifest(task))
            build_review_board(task)
        images.edit.assert_not_called()
        images.generate.assert_not_called()
        cc.assert_not_called()


# ===========================================================================
# §25 — Review Board consistency
# ===========================================================================


class TestReviewBoardConsistency:

    def test_board_and_manifest_agree(self, brand):
        task = mixed_task(brand)
        add_ref(task, "container", "logo.png", ordering=9)   # duplicate name
        board = build_review_board(task).references
        entries = rm.build_task_reference_manifest(task)["entries"]
        assert len(board) == len(entries) == 6
        assert [b.id for b in board] == \
            [e["reference_id"] for e in entries]
        assert [b.category for b in board] == \
            [e["category"] for e in entries]
        assert [b.filename for b in board] == \
            [e["original_filename"] for e in entries]
        assert [b.media_type for b in board] == \
            [e["media_type"] for e in entries]
        assert [b.file_size for b in board] == \
            [e["file_size"] for e in entries]
        assert all(e["source"] == "USER_UPLOAD" for e in entries)
        assert all(b.source == "User upload" for b in board)
        assert all(e["status"] == "REFERENCE_ONLY" for e in entries)
        assert all(b.status == "REFERENCE_ONLY" for b in board)


# ===========================================================================
# §BH69(2) — THE OWNER'S INSPIRATION PICTURE: its WORDS reach the planner and the prompts; its bytes reach no provider
# ===========================================================================

READING = {"layout": "a centred mark on a wide quiet field", "mood": "calm and luxurious",
           "finish": "soft-touch matte with a thin gold foil line", "type_style": "thin high-contrast serif capitals",
           "colour_words": "blush with warm gold", "take": "quiet space around one gold line",
           "seen_not_taken": ["LUMIERE PARIS", "the LP monogram"],
           # a reading stored by the first build still carries the colour codes it measured — never passed on
           "colours": [{"hex": "#F2D4D7", "share": 0.6}]}


def _read_picture(task, filename="pin.png", data=PNG):
    """A stored inspiration picture with its reading — as a read on the start page leaves them."""
    import hashlib

    from apps.pipeline.models import InspirationReading
    digest = hashlib.sha256(data).hexdigest()
    ref = add_ref(task, "inspiration_picture", filename, data)
    TaskReference.objects.filter(pk=ref.pk).update(sha256=digest)
    InspirationReading.objects.get_or_create(sha256=digest, defaults={"reading": dict(READING)})
    return ref


def _confirmed_trend_board(task):
    """§BH71 PART 2: a trend board confirmed with one picture ticked and one unticked, each read into words."""
    from apps.pipeline.models import InspirationReading, TrendBoard, TrendPick
    board = TrendBoard.objects.create(task=task, status=TrendBoard.CONFIRMED, subject="cosmetic serum packaging",
                                      confirmed_how="his click")
    picks = []
    for n in (1, 2):
        sha = ("%x" % (task.id * 16 + n)).rjust(64, "0")
        InspirationReading.objects.create(sha256=sha, reading={
            "layout": "", "mood": "", "finish": "", "type_style": "", "colour_words": "",
            "take": "trend take number %d" % n, "seen_not_taken": ["ACME"]})
        picks.append(TrendPick.objects.create(board=board, number=n, kind=TrendPick.PICTURE, platform="dribbble",
                                              page_url="https://dribbble.com/shots/%d" % n, title="ACME %d" % n,
                                              image_url="https://cdn.dribbble.com/%d.png" % n, sha256=sha,
                                              used=n == 1))
    board.used_at_confirm = [picks[0].pk]
    board.save()
    return board


class TestTrendWordsReachEveryPrompt:
    """§BH71 PART 2: "They feed the directions in words, like my uploaded pictures." The trend board's ticked pictures,
    as words, reach every place his own pictures' words reach — the variation prompts and the container's contract as
    well as the planner — and nothing else of them does."""

    def _aria(self, task):
        from apps.pipeline.agents.aria import ARIAAgent
        return ARIAAgent(task.id)

    def test_the_variation_prompt_writer_is_given_the_ticked_pictures_words(self, brand):
        task = make_task(brand)
        _confirmed_trend_board(task)
        aria = self._aria(task)
        captured = {}

        class StubPE:
            def __init__(self, *a, **k):
                pass

            def run(self):
                captured["trends"] = self.trend_context
                return []          # 0 prompts → clean fail, no image stage
        with patch("apps.pipeline.agents.aria.PromptEngineerAgent", StubPE), \
             patch.object(type(aria), "_product_profile", return_value={}), \
             patch.object(type(aria), "_target", return_value=_stub_target()):
            aria._render_variations({"name": "Rose", "direction_id": "A"})
        assert "<<trends>>" in captured["trends"] and "trend take number 1" in captured["trends"]
        assert "trend take number 2" not in captured["trends"]           # unticked
        for never in ("ACME", "http"):
            assert never not in captured["trends"]

    def test_the_containers_product_block_carries_the_trend_words_after_his_uploads(self, brand):
        task = mixed_task(brand)
        _confirmed_trend_board(task)
        aria = self._aria(task)
        from apps.pipeline.targets import get_target
        target = get_target("product_container")
        captured = {}

        def fake_build(**kwargs):
            captured.update(kwargs)
            return MagicMock(ok=False, prompts=[], codes=("STOP",), attempts=0, raw_responses=(), payload=None,
                             provider_model="")
        with patch("apps.pipeline.services.gate1_prompts.build_regeneration_prompts", fake_build), \
             patch.object(type(aria), "_product_profile", return_value={}):
            target.gate1_variation_plan(aria, {"name": "Rose", "direction_id": "A"})
        block = captured["product_block"]
        assert "CURRENT TRENDS, FOUND ON THE WEB" in block and "trend take number 1" in block
        assert block.index("OWNER-UPLOADED REFERENCES") < block.index("CURRENT TRENDS")
        assert "trend take number 2" not in block and "ACME" not in block



class TestInspirationPictureIsWordsOnly:

    def _aria(self, task):
        from apps.pipeline.agents.aria import ARIAAgent
        return ARIAAgent(task.id)

    def test_it_is_never_an_attachment_whatever_its_type_or_the_design(self, brand):
        from apps.pipeline.services.visual_reference_resolver import resolve_visual_references
        for target in ("product_container", "packaging"):
            task = make_task(brand, target=target)
            _read_picture(task)
            manifest = rm.build_task_reference_manifest(task)
            [entry] = [e for e in manifest["entries"] if e["category"] == "inspiration_picture"]
            assert entry["attachment_eligibility"] == rm.METADATA_ONLY, target
            assert rm.raster_attachment_descriptors(manifest) == [], target
            assert resolve_visual_references(task).upload_paths == [], target

    def test_its_words_reach_the_planner_and_the_prompts_and_nothing_else_of_it(self, brand):
        import base64
        import re
        for target in ("product_container", "packaging"):
            task = make_task(brand, target=target)
            _read_picture(task, filename="secret-screenshot-name.png")
            manifest = self._aria(task)._reference_manifest()
            for ctx in (rm.creative_director_reference_context(manifest),
                        rm.prompt_engineer_reference_context(manifest)):
                assert "quiet space around one gold line" in ctx, target            # what was taken, in words
                assert "<<inspiration>>" in ctx and "<<end inspiration>>" in ctx    # quoted as data
                for never in ("LUMIERE PARIS", "LP monogram", "secret-screenshot-name",   # seen, never taken; its
                              "task_refs/", "/media/", base64.b64encode(PNG).decode()[:24]):  # name, place, bytes
                    assert never not in ctx, (target, never)
                assert not re.search(r"#[0-9A-Fa-f]{6}\b", ctx), target                  # colours in words, never codes

    def test_the_planner_is_given_the_words_before_a_direction_is_written(self, brand):
        task = make_task(brand, target="packaging")
        _read_picture(task)
        aria = self._aria(task)
        captured = {}

        class StubCD:
            def __init__(self, *a, **k):
                pass

            def run_structured(self):
                captured["context"] = self.uploaded_reference_context
                return MagicMock(ok=False, codes=["STOP_FOR_TEST"])

            def _brief(self):
                return "brief"
        with patch("apps.pipeline.agents.aria.CreativeDirectorAgent", StubCD), \
             patch.object(type(aria), "_product_profile", return_value={}), \
             patch.object(type(aria), "_target", return_value=_stub_target()):
            aria._run_direction_planning()
        assert "thin high-contrast serif capitals" in captured["context"]
        assert "LUMIERE PARIS" not in captured["context"]

    def test_a_picture_not_read_on_the_start_page_is_read_against_the_design_before_it_plans(self, brand):
        from apps.pipeline.models import ApiCallRecord
        from apps.pipeline.services import inspiration
        task = make_task(brand, target="packaging")
        png = _png_bytes()
        ref = add_ref(task, "inspiration_picture", "late.png", png)
        TaskReference.objects.filter(pk=ref.pk).update(sha256=inspiration.sha256_of(png))
        reply = MagicMock(content=[MagicMock(type="text", text=json.dumps(
            {k: v for k, v in READING.items() if k != "colours"}))], usage=MagicMock(input_tokens=1200, output_tokens=300))
        with patch("apps.pipeline.services.claude_service._get_client") as client, \
                patch("apps.pipeline.services.cost_ledger.daily_budget_exceeded", return_value=False), \
                self.settings_key():
            client.return_value.messages.create.return_value = reply
            rows = inspiration.readings_for(task, read_missing=True)
        assert rows[0]["reading"]["take"] == "quiet space around one gold line"
        call = ApiCallRecord.objects.get(operation="inspiration_read")
        assert call.task_id == task.pk and call.cost_usd > 0                  # on the ledger, against the design
        sent = client.return_value.messages.create.call_args.kwargs
        assert sent["messages"][0]["content"][0]["type"] == "image"             # the one call the picture reaches

    @staticmethod
    def settings_key():
        from django.test import override_settings
        return override_settings(ANTHROPIC_API_KEY="k")


def _png_bytes(size=(40, 30), colour=(242, 212, 215)):
    import io

    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", size, colour).save(out, format="PNG")
    return out.getvalue()
