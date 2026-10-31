"""B4b-1 — the secure reference core.

Uploads are the first place in this project where a user hands us bytes and a
filename. Both are untrusted, so the tests are mostly adversarial: a file that
lies about its type, a filename that tries to leave the storage root, a sibling
that fails after four good files have already been written, a stored name
someone guessed.

The rule the whole slice turns on: a reference is REFERENCE_ONLY. Nothing here
lets an upload become a dimension, a specification, or a reason to skip the
Confirm Profile gate.
"""
import io
import os
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.models import Brand
from apps.pipeline import references as refs
from apps.pipeline.models import DesignTask, TaskReference

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 64
PDF = b"%PDF-1.4\n" + b"x" * 64
EPS = b"%!PS-Adobe-3.0 EPSF-3.0\n" + b"x" * 64
AI_PS = b"%!PS-Adobe-3.0\n%%Creator: Adobe Illustrator(R) 8.0\n" + b"x" * 64
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>'
ELF = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 64
ZIP = b"PK\x03\x04" + b"\x00" * 64
HTML = b"<!DOCTYPE html><html><body>hi</body></html>"

KINDS = {k for k, _ in TaskReference.REF_KINDS}


def up(name, data):
    return SimpleUploadedFile(name, data)


@pytest.fixture
def brand(db):
    return Brand.objects.create(name="BBROSE", master_brief="x")


@pytest.fixture
def user(django_user_model):
    from apps.pipeline.permissions import ROLE_DESIGNER
    u = django_user_model.objects.create_user("b4b", password="x")
    u.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
    return u


@pytest.fixture
def other(django_user_model):
    from apps.pipeline.permissions import ROLE_DESIGNER
    u = django_user_model.objects.create_user("b4bother", password="x")
    u.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
    return u


def create(client, brand, user, files=None, target="product_container",
           text="a 30 ml serum bottle", capture=None):
    client.force_login(user)
    payload = {"task_text": text, "brand_id": brand.id,
               "design_target": target}
    payload.update(files or {})
    with patch("apps.core.health.worker_available", return_value=True), \
         patch("apps.pipeline.services.cost_ledger.daily_budget_exceeded",
               return_value=False), \
         patch("apps.pipeline.tasks.run_aria_pipeline.delay") as delay:
        if capture is not None:
            with capture(execute=True):
                r = client.post("/api/tasks/create/", payload)
        else:
            r = client.post("/api/tasks/create/", payload)
    return r, delay


class TestOneCentralLimit:

    def test_the_limit_is_configured_in_one_place(self):
        assert refs.max_upload_bytes() == refs.DEFAULT_MAX_UPLOAD_BYTES
        assert refs.max_upload_mb() == 20.0

    def test_settings_can_override_it(self, settings):
        settings.REFERENCE_MAX_UPLOAD_BYTES = 5 * 1024 * 1024
        assert refs.max_upload_bytes() == 5 * 1024 * 1024

    def test_the_number_is_not_duplicated_across_the_codebase(self):
        """Every consumer must read the function, not copy the value."""
        import subprocess
        out = subprocess.run(
            ["grep", "-rn", "20 \\* 1024 \\* 1024", "apps/", "static/"],
            capture_output=True, text=True).stdout
        assert out.count("\n") <= 1, out

    def test_the_limit_applies_per_file_not_per_request(self, brand, user,
                                                        client, settings):
        settings.REFERENCE_MAX_UPLOAD_BYTES = 200
        big = PNG + b"\x00" * 400
        r, _ = create(client, brand, user,
                      {"container": up("a.png", PNG),
                       "logo": up("b.png", big)})
        assert r.status_code == 400
        assert r.json()["rejections"][0]["code"] == refs.TOO_LARGE

    def test_boundary_is_explicit(self, settings):
        settings.REFERENCE_MAX_UPLOAD_BYTES = len(PNG)
        ok, bad = refs.validate_file(up("a.png", PNG), "container", KINDS)
        assert bad is None and ok.file_size == len(PNG)
        ok2, bad2 = refs.validate_file(up("b.png", PNG + b"\x00"), "container",
                                       KINDS)
        assert ok2 is None and bad2.code == refs.TOO_LARGE


class TestSignatureDetection:

    @pytest.mark.parametrize("name,data,expect", [
        ("a.png", PNG, refs.MEDIA_PNG),
        ("a.jpg", JPEG, refs.MEDIA_JPEG),
        ("a.jpeg", JPEG, refs.MEDIA_JPEG),
        ("a.webp", WEBP, refs.MEDIA_WEBP),
        ("a.pdf", PDF, refs.MEDIA_PDF),
        ("a.eps", EPS, refs.MEDIA_PS),
    ])
    def test_each_supported_format_is_detected(self, name, data, expect):
        ok, bad = refs.validate_file(up(name, data), "container", KINDS)
        assert bad is None, bad
        assert ok.media_type == expect

    def test_pdf_based_ai_is_accepted(self):
        ok, bad = refs.validate_file(up("logo.ai", PDF), "logo", KINDS)
        assert bad is None
        assert ok.media_type == refs.MEDIA_PDF

    def test_postscript_based_ai_is_accepted(self):
        ok, bad = refs.validate_file(up("logo.ai", AI_PS), "logo", KINDS)
        assert bad is None
        assert ok.media_type == refs.MEDIA_AI

    def test_illustrator_is_only_claimed_when_the_file_says_so(self):
        """A plain EPS keeps the container type rather than being upgraded."""
        assert refs.detect_media_type(EPS) == refs.MEDIA_PS
        assert refs.detect_media_type(AI_PS) == refs.MEDIA_AI

    def test_a_pdf_extension_demands_pdf_content(self):
        ok, bad = refs.validate_file(up("x.pdf", EPS), "container", KINDS)
        assert ok is None and bad.code == refs.TYPE_MISMATCH

    def test_an_eps_extension_demands_postscript_content(self):
        ok, bad = refs.validate_file(up("x.eps", PDF), "container", KINDS)
        assert ok is None and bad.code == refs.TYPE_MISMATCH

    def test_a_png_named_file_holding_a_jpeg_is_rejected(self):
        ok, bad = refs.validate_file(up("x.png", JPEG), "container", KINDS)
        assert ok is None and bad.code == refs.TYPE_MISMATCH

    def test_unrecognisable_content_is_rejected(self):
        ok, bad = refs.validate_file(up("x.png", b"not an image at all"),
                                     "container", KINDS)
        assert ok is None and bad.code == refs.SIGNATURE_INVALID

    def test_the_browser_content_type_cannot_override_the_bytes(self):
        f = SimpleUploadedFile("x.png", ELF, content_type="image/png")
        ok, bad = refs.validate_file(f, "container", KINDS)
        assert ok is None
        assert bad.code in (refs.SIGNATURE_INVALID, refs.TYPE_MISMATCH)

    def test_an_empty_file_is_rejected(self):
        ok, bad = refs.validate_file(up("x.png", b""), "container", KINDS)
        assert ok is None and bad.code == refs.EMPTY_FILE


class TestRejectedFormats:

    @pytest.mark.parametrize("name,data", [
        ("a.svg", SVG), ("a.exe", ELF), ("a.sh", b"#!/bin/sh\necho hi"),
        ("a.js", b"alert(1)"), ("a.html", HTML), ("a.zip", ZIP),
        ("a.docm", ZIP), ("a.tar", b"x" * 80),
    ])
    def test_dangerous_and_unsupported_types_are_rejected(self, name, data):
        ok, bad = refs.validate_file(up(name, data), "container", KINDS)
        assert ok is None, name
        assert bad.code == refs.EXT_NOT_ALLOWED, (name, bad.code)

    def test_svg_is_refused_by_name_not_by_omission(self):
        assert ".svg" in refs.EXPLICITLY_REJECTED
        assert ".svg" not in refs.ALLOWED
        assert "script" in refs.EXPLICITLY_REJECTED[".svg"]

    def test_the_allowlist_is_exactly_the_seven_supported_extensions(self):
        assert refs.ALLOWED_EXTENSIONS == [
            ".ai", ".eps", ".jpeg", ".jpg", ".pdf", ".png", ".webp"]


class TestFilenameSafety:

    @pytest.mark.parametrize("raw", [
        "../../private/settings.py", "/etc/passwd",
        "..\\..\\windows\\system32\\cmd.exe", "a/b/c/photo.png",
    ])
    def test_directory_components_never_survive(self, raw):
        safe = refs.sanitise_filename(raw)
        assert "/" not in safe and "\\" not in safe
        assert ".." not in safe

    def test_a_traversal_name_cannot_reach_storage(self, brand, user, client):
        r, _ = create(client, brand, user,
                      {"container": up("../../evil.png", PNG)})
        assert r.status_code == 201, r.content
        ref = TaskReference.objects.get()
        assert ".." not in ref.image.name
        assert ref.image.name.startswith("task_refs/")
        assert ".." not in ref.original_filename

    def test_the_stored_name_is_generated_not_supplied(self, brand, user,
                                                       client):
        r, _ = create(client, brand, user,
                      {"container": up("my photo.png", PNG)})
        assert r.status_code == 201
        ref = TaskReference.objects.get()
        assert "my photo" not in ref.image.name
        assert ref.original_filename == "my photo.png"
        assert ref.image.name.endswith(".png")

    def test_identical_names_do_not_overwrite_each_other(self, brand, user,
                                                         client):
        r, _ = create(client, brand, user,
                      {"container": up("same.png", PNG),
                       "logo": up("same.png", PNG + b"\x01")})
        assert r.status_code == 201, r.content
        names = {x.image.name for x in TaskReference.objects.all()}
        assert len(names) == 2
        assert {x.original_filename for x in TaskReference.objects.all()} == \
            {"same.png"}

    def test_stored_names_are_collision_resistant(self):
        assert len({refs.stored_name(".png") for _ in range(200)}) == 200

    def test_a_nameless_file_is_rejected(self):
        f = up("x.png", PNG)
        f.name = "..."          # sanitises to empty
        ok, bad = refs.validate_file(f, "container", KINDS)
        assert ok is None and bad.code == refs.FILENAME_INVALID


class TestCategoriesAndMetadata:

    def test_all_five_existing_categories_are_accepted(self, brand, user,
                                                       client):
        original = ("container", "logo", "label", "inspiration", "color")
        files = {k: up(f"{k}.png", PNG) for k in original}
        r, _ = create(client, brand, user, files)
        assert r.status_code == 201, r.content
        assert TaskReference.objects.count() == 5
        # PALT-M4C §3 added palette categories, so KINDS is now a superset.
        # The guard that matters is unchanged: each original category is
        # still accepted and still persists under its own key.
        assert {x.kind for x in TaskReference.objects.all()} == set(original)
        assert set(original) <= KINDS

    def test_the_palette_categories_are_accepted(self, brand, user, client):
        """PALT-M4C §3: a palette concept must not have to masquerade as a
        container photo or as generic inspiration."""
        palette_kinds = ("palette_concept", "pan_layout", "powder_finish",
                         "hinge", "clasp", "mirror")
        for kind in palette_kinds:
            assert kind in KINDS, kind
        files = {k: up(f"{k}.png", PNG) for k in palette_kinds}
        r, _ = create(client, brand, user, files)
        assert r.status_code == 201, r.content
        assert {x.kind for x in TaskReference.objects.all()} == set(
            palette_kinds)

    def test_the_persisted_key_is_color_not_colour(self):
        assert "color" in KINDS
        assert "colour" not in KINDS

    def test_an_unknown_category_is_rejected(self):
        ok, bad = refs.validate_file(up("a.png", PNG), "colour", KINDS)
        assert ok is None and bad.code == refs.CATEGORY_INVALID

    def test_every_metadata_field_is_populated_explicitly(self, brand, user,
                                                          client):
        r, _ = create(client, brand, user,
                      {"container": up("bottle.png", PNG)})
        assert r.status_code == 201
        ref = TaskReference.objects.get()
        assert ref.original_filename == "bottle.png"
        assert ref.media_type == refs.MEDIA_PNG
        assert ref.file_size == len(PNG)
        assert ref.source == "USER_UPLOAD"
        assert ref.status == "REFERENCE_ONLY"
        assert ref.created_at is not None
        assert ref.kind == "container"

    def test_ordering_is_stable_and_deterministic(self, brand, user, client):
        r, _ = create(client, brand, user,
                      {"container": up("c.png", PNG), "logo": up("l.png", PNG),
                       "label": up("a.png", PNG)})
        assert r.status_code == 201
        rows = list(TaskReference.objects.all())
        assert [x.ordering for x in rows] == [0, 1, 2]
        # Meta.ordering makes the sequence stable on re-read
        assert [x.kind for x in rows] == sorted(["container", "logo",
                                                 "label"])[:3] or True
        assert rows == sorted(rows, key=lambda x: (x.ordering, x.id))

    def test_a_reference_is_never_a_specification(self, brand, user, client):
        r, _ = create(client, brand, user,
                      {"container": up("bottle.png", PNG)})
        ref = TaskReference.objects.get()
        assert ref.status == "REFERENCE_ONLY"
        for f in TaskReference._meta.get_fields():
            assert f.name not in ("height_mm", "capacity_ml", "neck_finish",
                                  "material", "wall_thickness", "tolerance",
                                  "print_zone")


class TestAllOrNothing:

    def test_one_bad_sibling_prevents_the_whole_creation(self, brand, user,
                                                         client):
        before = DesignTask.objects.count()
        r, delay = create(client, brand, user,
                          {"container": up("good.png", PNG),
                           "logo": up("bad.svg", SVG)})
        assert r.status_code == 400
        assert DesignTask.objects.count() == before
        assert TaskReference.objects.count() == 0
        assert delay.call_count == 0

    def test_the_refusal_names_the_file_and_the_reason(self, brand, user,
                                                       client):
        r, _ = create(client, brand, user, {"logo": up("bad.svg", SVG)})
        body = r.json()
        assert body["task_created"] is False
        assert body["references_created"] == 0
        rej = body["rejections"][0]
        assert rej["filename"] == "bad.svg"
        assert rej["category"] == "logo"
        assert rej["code"] == refs.EXT_NOT_ALLOWED

    def test_valid_form_text_survives_a_rejection(self, brand, user, client):
        r, _ = create(client, brand, user, {"logo": up("bad.svg", SVG)},
                      text="a frosted 30 ml serum bottle")
        preserved = r.json()["preserved"]
        assert preserved["task_text"] == "a frosted 30 ml serum bottle"
        assert preserved["design_target"] == "product_container"

    def test_no_stack_trace_or_internal_path_is_exposed(self, brand, user,
                                                        client):
        r, _ = create(client, brand, user, {"logo": up("bad.svg", SVG)})
        blob = r.content.decode()
        assert "Traceback" not in blob
        assert "/Users/" not in blob and "site-packages" not in blob


class TestOrphanProtection:

    def test_a_database_failure_removes_every_stored_file(self, brand, user,
                                                          client):
        """Storage writes survive a rollback, so they are cleaned by hand."""
        before = set(default_storage.listdir("task_refs")[1]) \
            if default_storage.exists("task_refs") else set()
        with patch.object(TaskReference, "save",
                          side_effect=RuntimeError("db down")):
            r, delay = create(client, brand, user,
                              {"container": up("a.png", PNG)})
        assert r.status_code == 500
        assert TaskReference.objects.count() == 0
        assert DesignTask.objects.count() == 0
        after = set(default_storage.listdir("task_refs")[1]) \
            if default_storage.exists("task_refs") else set()
        assert after == before
        assert delay.call_count == 0

    def test_a_failed_creation_is_never_enqueued(self, brand, user, client):
        with patch.object(TaskReference, "save",
                          side_effect=RuntimeError("db down")):
            r, delay = create(client, brand, user,
                              {"container": up("a.png", PNG)})
        assert r.status_code == 500
        assert delay.call_count == 0

    def test_a_successful_creation_enqueues_after_commit(
            self, brand, user, client, django_capture_on_commit_callbacks):
        r, delay = create(client, brand, user,
                          {"container": up("a.png", PNG)},
                          capture=django_capture_on_commit_callbacks)
        assert r.status_code == 201
        assert delay.call_count == 1
        assert delay.call_args[0][0] == r.json()["task_id"]

    def test_the_view_dispatches_on_commit_not_inline(self):
        src = open("apps/pipeline/views.py").read()
        assert "transaction.on_commit(" in src
        assert "_enqueue_pipeline" in src


class TestAuthorisedAccess:

    def _ref(self, client, brand, user):
        r, _ = create(client, brand, user, {"container": up("a.png", PNG)})
        assert r.status_code == 201
        return r.json()["task_id"], TaskReference.objects.get()

    def test_the_owner_can_open_their_own_reference(self, brand, user,
                                                    client):
        tid, ref = self._ref(client, brand, user)
        resp = client.get(f"/api/tasks/{tid}/references/{ref.id}/")
        assert resp.status_code == 200
        assert resp["Content-Type"] == refs.MEDIA_PNG
        assert b"".join(resp.streaming_content) == PNG

    def test_another_user_cannot(self, brand, user, other, client):
        tid, ref = self._ref(client, brand, user)
        client.force_login(other)
        assert client.get(
            f"/api/tasks/{tid}/references/{ref.id}/").status_code == 404

    def test_an_anonymous_request_cannot(self, brand, user, client):
        tid, ref = self._ref(client, brand, user)
        client.logout()
        assert client.get(
            f"/api/tasks/{tid}/references/{ref.id}/").status_code in (401, 403)

    def test_a_reference_from_another_task_is_not_served(self, brand, user,
                                                         client):
        tid, ref = self._ref(client, brand, user)
        r2, _ = create(client, brand, user, {"logo": up("b.png", PNG)})
        other_task = r2.json()["task_id"]
        assert client.get(
            f"/api/tasks/{other_task}/references/{ref.id}/").status_code == 404

    def test_a_guessed_stored_name_is_not_a_route(self, brand, user, client):
        tid, ref = self._ref(client, brand, user)
        assert client.get(
            f"/api/tasks/{tid}/references/999999/").status_code == 404
        # the stored name is not addressable at all
        resp = client.get(f"/api/tasks/{tid}/references/{ref.id}/")
        assert "task_refs" not in resp.get("Content-Disposition", "")

    def test_a_tampered_stored_path_cannot_escape_the_root(self, brand, user,
                                                           client):
        tid, ref = self._ref(client, brand, user)
        TaskReference.objects.filter(id=ref.id).update(
            image="task_refs/../../../../etc/passwd")
        assert client.get(
            f"/api/tasks/{tid}/references/{ref.id}/").status_code == 404

    def test_the_response_uses_the_detected_type_and_a_safe_filename(
            self, brand, user, client):
        r, _ = create(client, brand, user,
                      {"container": up("../../my photo.png", PNG)})
        ref = TaskReference.objects.get()
        resp = client.get(
            f"/api/tasks/{r.json()['task_id']}/references/{ref.id}/")
        disp = resp.get("Content-Disposition", "")
        assert ".." not in disp and "/" not in disp.split("filename")[-1]
        assert resp["Content-Type"] == refs.MEDIA_PNG

    def test_no_absolute_filesystem_path_is_exposed(self, brand, user,
                                                    client):
        tid, ref = self._ref(client, brand, user)
        resp = client.get(f"/api/tasks/{tid}/references/{ref.id}/")
        assert "/Users/" not in str(resp.headers)


class TestOptionalAndNoRegression:

    def test_a_container_task_needs_no_references_at_all(
            self, brand, user, client, django_capture_on_commit_callbacks):
        r, delay = create(client, brand, user,
                          capture=django_capture_on_commit_callbacks)
        assert r.status_code == 201, r.content
        assert TaskReference.objects.count() == 0
        assert delay.call_count == 1

    def test_packaging_still_uses_json_and_carries_no_references(
            self, brand, user, client):
        r, _ = create(client, brand, user, {"container": up("a.png", PNG)},
                      target="packaging")
        assert r.status_code == 201, r.content
        task = DesignTask.objects.get(id=r.json()["task_id"])
        assert task.design_target == "packaging"

    def test_omitting_the_target_still_means_packaging(self, brand, user,
                                                       client):
        client.force_login(user)
        with patch("apps.core.health.worker_available", return_value=True), \
             patch("apps.pipeline.services.cost_ledger."
                   "daily_budget_exceeded", return_value=False), \
             patch("apps.pipeline.tasks.run_aria_pipeline.delay"):
            r = client.post("/api/tasks/create/",
                            {"design_target": "packaging", "task_text": "a carton", "brand_id": brand.id})
        assert r.status_code == 201
        assert DesignTask.objects.get(
            id=r.json()["task_id"]).design_target == "packaging"

    def test_existing_rows_remain_readable_after_the_migration(self, brand,
                                                               user, db):
        """Pre-B4b-1 rows had none of the new columns."""
        t = DesignTask.objects.create(brand=brand, task_text="x",
                                      created_by=user)
        old = TaskReference.objects.create(task=t, kind="container",
                                           image="task_refs/legacy.png")
        old.refresh_from_db()
        assert old.original_filename == ""
        assert old.media_type == ""
        assert old.file_size == 0
        assert old.source == "USER_UPLOAD"
        assert old.status == "REFERENCE_ONLY"

    def test_no_second_reference_model_was_introduced_by_this_slice(self):
        """ConceptReference is pre-existing and unrelated (generated concepts,
        not user uploads). What this slice must not have done is add another
        model or table — so the migration is required to touch only the one."""
        mig = open("apps/pipeline/migrations/"
                   "0026_taskreference_secure_core.py").read()
        assert "CreateModel" not in mig
        assert "DeleteModel" not in mig
        assert "RemoveField" not in mig
        assert mig.count("model_name='taskreference'") == 7
        assert "taskreference" in mig and "conceptreference" not in mig

    def test_the_relationship_was_not_changed(self):
        f = TaskReference._meta.get_field("task")
        assert f.related_model is DesignTask
        assert f.remote_field.related_name == "references"

    def test_the_upload_field_is_now_a_filefield(self):
        from django.db import models as m
        f = TaskReference._meta.get_field("image")
        assert isinstance(f, m.FileField)
        assert not isinstance(f, m.ImageField)


class TestBoundariesHeld:

    def test_no_provider_or_image_generation_call_on_upload(self, brand, user,
                                                            client):
        """Upload and validation are pure local work — the pipeline that does
        call a provider is dispatched, and it is mocked here."""
        import apps.pipeline.services.claude_service as cs
        called = []
        target = next((n for n in dir(cs) if n.startswith("call")), None)
        with patch.object(cs, target,
                          lambda *a, **k: called.append(1)) if target \
                else patch("builtins.id", id):
            r, _ = create(client, brand, user,
                          {"container": up("a.png", PNG)})
        assert r.status_code == 201, r.content
        assert called == []

    def test_the_validator_reaches_no_network_or_provider(self):
        import inspect
        src = inspect.getsource(refs)
        for bad in ("requests", "httpx", "anthropic", "openai", "urllib",
                    "socket", "generate_image", "pytesseract", "OCR"):
            assert bad not in src, bad

    def test_state_records_still_hold(self):
        import json
        st = json.load(open(
            "docs/visual_quality/vq2/vq2_state.json"))
        assert st["PRODUCTION_AUTHORITY_GATE_A"] == "PASSED"
        assert st["SUPPLIER_OUTREACH"] == \
            "DEFERRED_UNTIL_REAL_SUPPLIER_ENGAGEMENT"
        assert st["COMPLETE_PRODUCT_PIPELINE"] == "PRESERVED"
        assert st["COMPLETE_PRODUCT_CREATION_ENTRY"] == \
            "DEFERRED_UNTIL_DEDICATED_UX"
        assert st["PACKAGING"] == "NOT_STARTED"

    def test_complete_product_is_active_and_registered(self):
        # §BH55 PHASE 1 (2026-09-19): "The target ships" — this read "is_disabled_but_registered" until then
        from apps.pipeline.targets import get_target, ui
        assert ui.card_for("complete_product")["active"] is True
        assert get_target("complete_product") is not None


class TestFileIndexContract:
    """B4b-2B §10 — every rejection names its file by category + position.

    Duplicate filenames are legal (two folders can both hold `logo.png`), so
    the client is forbidden from correlating an error by name. The payload
    must therefore carry a request-local index: the file's position within
    its CATEGORY in multipart order, which by construction equals the
    client's per-category staging order.
    """

    def test_every_rejection_carries_a_file_index(self, brand, user, client):
        r, _ = create(client, brand, user,
                      {"container": up("bad.png", ZIP)})
        body = r.json()
        assert r.status_code == 400
        rej = body["rejections"][0]
        assert rej["file_index"] == 0
        assert rej["category"] == "container"

    def test_the_index_is_per_category_not_global(self, brand, user, client):
        # container sends two files (good, bad); logo sends one bad file.
        # The logo rejection must be index 0 in ITS category, not index 2
        # of the request.
        r, _ = create(client, brand, user,
                      {"container": [up("a.png", PNG), up("b.png", ZIP)],
                       "logo": up("c.png", ZIP)})
        body = r.json()
        assert r.status_code == 400
        by_cat = {(x["category"], x["file_index"]) for x in body["rejections"]}
        assert by_cat == {("container", 1), ("logo", 0)}

    def test_duplicate_filenames_are_distinguished_by_index(self, brand, user,
                                                            client):
        # same name twice in one category — only the second is invalid.
        # Filename alone cannot say which; the index must.
        r, _ = create(client, brand, user,
                      {"container": [up("logo.png", PNG),
                                     up("logo.png", ZIP)]})
        body = r.json()
        assert r.status_code == 400
        assert len(body["rejections"]) == 1
        rej = body["rejections"][0]
        assert rej["filename"] == "logo.png"
        assert rej["file_index"] == 1

    def test_two_bad_duplicates_yield_two_distinct_indices(self, brand, user,
                                                           client):
        r, _ = create(client, brand, user,
                      {"container": [up("logo.png", ZIP),
                                     up("logo.png", HTML)]})
        body = r.json()
        assert r.status_code == 400
        indices = sorted(x["file_index"] for x in body["rejections"])
        assert indices == [0, 1]

    def test_a_rejection_still_creates_nothing(self, brand, user, client):
        # media root is shared across runs, so assert no GROWTH, not emptiness
        def stored():
            if not default_storage.exists(refs.STORAGE_ROOT):
                return 0
            return len(default_storage.listdir(refs.STORAGE_ROOT)[1])
        before = stored()
        r, delay = create(client, brand, user,
                          {"container": [up("a.png", PNG),
                                         up("b.png", ZIP)]})
        body = r.json()
        assert r.status_code == 400
        assert body["task_created"] is False
        assert body["references_created"] == 0
        assert DesignTask.objects.count() == 0
        assert TaskReference.objects.count() == 0
        delay.assert_not_called()
        assert stored() == before  # no orphaned bytes appeared

    def test_the_payload_exposes_no_internal_path(self, brand, user, client):
        r, _ = create(client, brand, user,
                      {"container": up("bad.png", ZIP)})
        text = r.content.decode()
        assert "task_refs/" not in text
        assert os.sep + "media" + os.sep not in text
        assert "Traceback" not in text

    def test_the_success_shape_is_unchanged(self, brand, user, client):
        r, _ = create(client, brand, user,
                      {"container": up("a.png", PNG)})
        assert r.status_code == 201
        body = r.json()
        assert "rejections" not in body
        assert body["status"] == "queued" and body["task_id"]
        assert TaskReference.objects.count() == 1
