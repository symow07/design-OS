"""B4b-3A — Review Board reference presentation, server side.

The Review Board presents persisted references from STORED metadata through
the authorized endpoint, and nothing else: no raw FileField URL, no
MEDIA_URL, no filesystem path, no file bytes read while building the page,
no re-detection of anything the upload pipeline already decided. Ordering is
deterministic (fixed category order, then persisted ordering) and is proven
against filenames chosen to sort differently alphabetically.
"""
import pytest
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.core.models import Brand
from apps.pipeline.models import DesignTask, TaskReference
from apps.pipeline.review_board import build_review_board

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4\n" + b"x" * 64
EPS = b"%!PS-Adobe-3.0 EPSF-3.0\n" + b"x" * 64
AI_PS = b"%!PS-Adobe-3.0\n%%Creator: Adobe Illustrator(R) 8.0\n" + b"x" * 64


@pytest.fixture
def brand(db):
    return Brand.objects.create(name="BBROSE", master_brief="x")


@pytest.fixture
def owner(django_user_model):
    from apps.pipeline.permissions import ROLE_DESIGNER
    u = django_user_model.objects.create_user("b4b3a", password="x")
    u.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
    return u


def make_task(brand, owner=None, target="product_container"):
    return DesignTask.objects.create(
        brand=brand, task_text="a serum bottle", design_target=target,
        created_by=owner)


def add_ref(task, kind, filename, data=PNG, media_type="image/png",
            ordering=0):
    ref = TaskReference(task=task, kind=kind, original_filename=filename,
                       media_type=media_type, file_size=len(data),
                       ordering=ordering)
    ref.image.save(filename, ContentFile(data), save=True)
    return ref


class TestGroupingAndOrdering:

    def test_categories_group_in_fixed_order_never_alphabetical(self, brand):
        task = make_task(brand)
        # created in scrambled category order, with filenames whose
        # alphabetical order disagrees with everything else
        add_ref(task, "color", "aaa.png", ordering=4)
        add_ref(task, "container", "zzz.png", ordering=0)
        add_ref(task, "inspiration", "bbb.png", ordering=3)
        add_ref(task, "logo", "yyy.png", ordering=1)
        add_ref(task, "label", "ccc.png", ordering=2)
        board = build_review_board(task)
        assert [r.category for r in board.references] == [
            "container", "logo", "label", "inspiration", "color"]
        assert [r.filename for r in board.references] == [
            "zzz.png", "yyy.png", "ccc.png", "bbb.png", "aaa.png"]

    def test_within_category_persisted_ordering_wins(self, brand):
        task = make_task(brand)
        add_ref(task, "container", "z-second.png", ordering=1)
        add_ref(task, "container", "a-third.png", ordering=2)
        add_ref(task, "container", "m-first.png", ordering=0)
        board = build_review_board(task)
        assert [r.filename for r in board.references] == [
            "m-first.png", "z-second.png", "a-third.png"]

    def test_stored_key_color_displays_as_colour_reference(self, brand):
        task = make_task(brand)
        add_ref(task, "color", "chips.png")
        (item,) = build_review_board(task).references
        assert item.category == "color"          # persisted key untouched
        assert item.category_label == "Colour Reference"
        assert "Colour" in item.name

    def test_category_notes_are_non_authoritative(self, brand):
        task = make_task(brand)
        for kind in ("container", "logo", "label", "inspiration", "color"):
            add_ref(task, kind, f"{kind}.png")
        for item in build_review_board(task).references:
            assert item.category_note
            low = item.category_note.lower()
            for banned in ("confirmed", "approved", "dimension",
                           "production", "manufactur", "verified",
                           "supplier"):
                assert banned not in low

    def test_duplicate_filenames_both_present(self, brand):
        task = make_task(brand)
        add_ref(task, "container", "logo.png", ordering=0)
        add_ref(task, "container", "logo.png", ordering=1)
        refs = build_review_board(task).references
        assert [r.filename for r in refs] == ["logo.png", "logo.png"]
        assert refs[0].id != refs[1].id


class TestStoredMetadataOnly:

    def test_card_metadata_comes_from_the_row(self, brand):
        task = make_task(brand)
        ref = add_ref(task, "container", "amber.png")
        (item,) = build_review_board(task).references
        assert item.filename == "amber.png"
        assert item.media_type == "image/png"
        assert item.file_size == len(PNG)
        assert item.file_size_display.endswith(" B")
        assert item.uploaded_at == ref.created_at.isoformat()
        assert item.source == "User upload"
        assert item.status == "REFERENCE_ONLY"
        assert item.label == "Reference Only"

    def test_raster_uses_the_authorized_endpoint(self, brand):
        task = make_task(brand)
        ref = add_ref(task, "container", "amber.png")
        (item,) = build_review_board(task).references
        expected = f"/api/tasks/{task.id}/references/{ref.id}/"
        assert item.previewable is True
        assert item.image_url == expected
        assert item.open_url == expected
        assert item.download_url == expected + "?download=1"

    def test_documents_get_doc_type_and_no_image_url(self, brand):
        task = make_task(brand)
        add_ref(task, "label", "sheet.pdf", PDF, "application/pdf",
                ordering=0)
        add_ref(task, "label", "cut.eps", EPS, "application/postscript",
                ordering=1)
        add_ref(task, "label", "art-ps.ai", AI_PS,
                "application/vnd.adobe.illustrator", ordering=2)
        add_ref(task, "label", "art-pdf.ai", PDF, "application/pdf",
                ordering=3)
        refs = build_review_board(task).references
        assert [r.doc_type for r in refs] == ["PDF", "EPS", "AI", "AI"]
        assert all(r.previewable is False for r in refs)
        assert all(r.image_url is None for r in refs)
        # documents still get authorized open/download
        assert all("/api/tasks/" in r.open_url for r in refs)

    def test_no_raw_storage_url_or_path_in_the_payload(self, brand):
        task = make_task(brand)
        add_ref(task, "container", "amber.png")
        add_ref(task, "label", "sheet.pdf", PDF, "application/pdf")
        dump = build_review_board(task).model_dump_json()
        assert "/media/" not in dump
        assert "task_refs/" not in dump
        assert "/Users/" not in dump and "/var/" not in dump

    def test_no_file_bytes_are_read_while_building(self, brand):
        # delete the stored file: if the builder touched bytes (or even the
        # storage path), this would explode — it must not
        task = make_task(brand)
        ref = add_ref(task, "container", "amber.png")
        ref.image.storage.delete(ref.image.name)
        (item,) = build_review_board(task).references
        assert item.filename == "amber.png"

    def test_references_expected_flag_by_target(self, brand):
        assert build_review_board(
            make_task(brand)).references_expected is True
        assert build_review_board(
            make_task(brand, target="packaging")).references_expected is False
        assert build_review_board(make_task(
            brand, target="complete_product")).references_expected is False

    def test_empty_reference_list_is_empty_not_placeholder(self, brand):
        board = build_review_board(make_task(brand))
        assert board.references == []


class TestQueryBoundary:

    def test_reference_count_does_not_grow_queries(self, brand):
        one = make_task(brand)
        add_ref(one, "container", "a.png")
        many = make_task(brand)
        for i, kind in enumerate(
                ("container", "logo", "label", "inspiration", "color")):
            add_ref(many, kind, f"{kind}-{i}.png", ordering=i)
            add_ref(many, kind, f"{kind}-dup-{i}.png", ordering=i + 10)
        with CaptureQueriesContext(connection) as q1:
            build_review_board(one)
        with CaptureQueriesContext(connection) as q10:
            build_review_board(many)
        assert len(q10) == len(q1)   # 10 references, same query count as 1


class TestAuthorizedDownloadMode:

    def _client_for(self, user):
        from django.test import Client
        c = Client()
        c.force_login(user)
        return c

    def test_download_param_switches_disposition_only(self, brand, owner):
        task = make_task(brand, owner)
        ref = add_ref(task, "container", "amber.png")
        c = self._client_for(owner)
        base = f"/api/tasks/{task.id}/references/{ref.id}/"
        inline = c.get(base)
        assert inline.status_code == 200
        assert "attachment" not in inline.get("Content-Disposition", "")
        att = c.get(base + "?download=1")
        assert att.status_code == 200
        assert "attachment" in att["Content-Disposition"]
        assert "amber.png" in att["Content-Disposition"]
        # same file either way — the parameter selects nothing
        assert b"".join(att.streaming_content) == \
            b"".join(c.get(base).streaming_content)

    def test_download_mode_is_still_authorized(self, brand, owner,
                                               django_user_model):
        from apps.pipeline.permissions import ROLE_DESIGNER
        task = make_task(brand, owner)
        ref = add_ref(task, "container", "amber.png")
        stranger = django_user_model.objects.create_user("b4b3astr",
                                                         password="x")
        stranger.groups.add(
            Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
        c = self._client_for(stranger)
        r = c.get(f"/api/tasks/{task.id}/references/{ref.id}/?download=1")
        assert r.status_code == 404   # standard non-leaking response
