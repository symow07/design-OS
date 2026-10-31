"""D-D14-4: private publication files, database pins and the real /files door.

No publisher, renderer, provider or live records: only small local PDF bytes and
minimal test database rows. Controls mutate bytes, local pins and current output.
"""
import hashlib
import json
from pathlib import Path

import pytest

from apps.core import pinned_media
from apps.pipeline.services import master_tasks as mt


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _blank_pdf():
    """A valid one-page PDF built as bytes, without rendering anything."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Resources << >> >>"]
    data = b"%PDF-1.4\n"
    offsets = []
    for number, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 4\n0000000000 65535 f \n"
    data += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets)
    return data + b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"


@pytest.fixture
def publication(db, settings, tmp_path, client, django_user_model, monkeypatch):
    from apps.core.models import Brand
    from apps.pipeline.models import DesignTask, GeneratedImage, PackagingOutput

    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.HISTORY_TIER_RECORD = str(tmp_path / "no-tiers.jsonl")
    monkeypatch.setattr("apps.pipeline.autopilot.watch", lambda task: None)
    user = django_user_model.objects.create_user(username="day14-files")
    client.force_login(user)
    brand = Brand.objects.create(name="Day14 private file-door test")
    slug = "day14-private-master"
    task = DesignTask.objects.create(brand=brand, task_text="Private publication fixture", status="queued",
                                     options={mt.KEY_OPTION: slug})
    image = GeneratedImage.objects.create(task=task, direction_name="fixture", prompt_used="No call")
    relative = f"{mt.MEDIA_FOLDER}/{slug}/body/body-wrap.pdf"
    data = _blank_pdf()
    target = Path(settings.MEDIA_ROOT) / relative
    target.parent.mkdir(parents=True)
    target.write_bytes(data)
    record = {"schema": mt.RECORD_SCHEMA, "slug": slug, "files": {relative: {"sha256": _sha(data)}}}
    output = PackagingOutput.objects.create(task=task, approved_image=image, spec_sheet={mt.SPEC_KEY: record})
    local = Path(settings.MEDIA_ROOT) / mt.MEDIA_FOLDER / slug / mt.RECORD_NAME
    local.write_text(json.dumps(record))
    return {"target": target, "data": data, "url": "/files/" + relative, "relative": relative,
            "local": local, "record": record, "task": task, "output": output, "image": image,
            "media": Path(settings.MEDIA_ROOT)}


def _body(response):
    # Django's test client wraps this iterator to close the response with its
    # test-transaction protections. A second manual close emits request_finished
    # again and can close the private PostgreSQL transaction before the next GET.
    return b"".join(response.streaming_content)


def test_pinned_pdf_matching_then_one_byte_tamper_then_restore(publication, client, caplog):
    p = publication
    response = client.get(p["url"])
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert _body(response) == p["data"]
    p["target"].write_bytes(p["data"][:-1] + b"X")
    with caplog.at_level("WARNING", logger=pinned_media.__name__):
        response = client.get(p["url"])
    assert response.status_code == 409
    assert b"SHA256 mismatch" in response.content
    assert any(r.name == pinned_media.__name__ and "PINNED_DOWNLOAD_REFUSED" in r.message
               and p["relative"] in r.message for r in caplog.records)
    p["target"].write_bytes(p["data"])
    response = client.get(p["url"])
    assert response.status_code == 200
    assert _body(response) == p["data"]


def test_changing_local_publication_pin_does_not_authorize_tampered_bytes(publication, client):
    p = publication
    changed = p["data"] + b"tampered"
    p["target"].write_bytes(changed)
    p["record"]["files"][p["relative"]]["sha256"] = _sha(changed)
    p["local"].write_text(json.dumps(p["record"]))
    assert client.get(p["url"]).status_code == 409
    p["output"].refresh_from_db()
    assert p["output"].spec_sheet[mt.SPEC_KEY]["files"][p["relative"]]["sha256"] == _sha(p["data"])


def test_served_bytes_are_the_verified_snapshot_and_stream_closes(publication, client, monkeypatch):
    p = publication
    # Exercise disk-spill as well as the interval between checking and streaming.
    monkeypatch.setattr(pinned_media, "SPOOL_MEMORY_BYTES", 16)
    opened = []
    make = pinned_media.SpooledTemporaryFile

    def remember(*args, **kwargs):
        stream = make(*args, **kwargs)
        opened.append(stream)
        return stream

    monkeypatch.setattr(pinned_media, "SpooledTemporaryFile", remember)
    response = client.get(p["url"])
    assert response.status_code == 200
    p["target"].write_bytes(b"changed after verification")
    assert _body(response) == p["data"]
    assert len(opened) == 1 and opened[0].closed


def test_refused_snapshot_is_closed(publication, client, monkeypatch):
    p = publication
    p["target"].write_bytes(p["data"] + b"changed")
    opened = []
    make = pinned_media.SpooledTemporaryFile

    def remember(*args, **kwargs):
        stream = make(*args, **kwargs)
        opened.append(stream)
        return stream

    monkeypatch.setattr(pinned_media, "SpooledTemporaryFile", remember)
    assert client.get(p["url"]).status_code == 409
    assert len(opened) == 1 and opened[0].closed


def test_only_current_output_pin_authorizes_bytes(publication, client):
    from apps.pipeline.models import PackagingOutput
    p = publication
    changed = p["data"] + b"\n% current revision\n"
    record = {"schema": mt.RECORD_SCHEMA, "slug": p["record"]["slug"],
              "files": {p["relative"]: {"sha256": _sha(changed)}}}
    PackagingOutput.objects.create(task=p["task"], approved_image=p["image"], spec_sheet={mt.SPEC_KEY: record})
    assert client.get(p["url"]).status_code == 409
    p["target"].write_bytes(changed)
    response = client.get(p["url"])
    assert response.status_code == 200
    assert _body(response) == changed


@pytest.mark.parametrize("fault", ["missing_task", "missing_output", "missing_pin", "bad_pin"])
def test_published_namespace_without_current_authority_refuses(publication, client, fault):
    p = publication
    if fault == "missing_task":
        p["task"].delete()
    elif fault == "missing_output":
        p["output"].delete()
    else:
        record = p["output"].spec_sheet[mt.SPEC_KEY]
        record["files"] = {} if fault == "missing_pin" else {p["relative"]: {"sha256": "not-a-hash"}}
        p["output"].save(update_fields=["spec_sheet"])
    assert client.get(p["url"]).status_code == 409


def test_generic_media_stays_available(publication, client):
    p = publication
    for relative in ("generated/ordinary.pdf", f"{mt.MEDIA_FOLDER}/unpublished-test/ordinary.pdf"):
        path = p["media"] / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(p["data"])
        response = client.get("/files/" + relative)
        assert response.status_code == 200
        assert _body(response) == p["data"]


def test_symlink_cannot_reclassify_a_pinned_file_as_generic(publication, client):
    p = publication
    generic = p["media"] / "generated/changed.pdf"
    generic.parent.mkdir(parents=True)
    generic.write_bytes(p["data"] + b"changed")
    p["target"].unlink()
    p["target"].symlink_to(generic)
    assert client.get(p["url"]).status_code == 409


def test_existing_auth_and_path_restrictions_still_precede_pin_check(publication, client):
    p = publication
    client.logout()
    assert client.get(p["url"]).status_code == 302
    from django.contrib.auth import get_user_model
    client.force_login(get_user_model().objects.get(username="day14-files"))
    outside = p["media"].parent / "outside.pdf"
    outside.write_bytes(p["data"])
    assert client.get("/files/..%2Foutside.pdf").status_code == 404
    for relative, status in (("references/ref.pdf", 403), ("dielines/hybrid/staging/file.pdf", 404)):
        path = p["media"] / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(p["data"])
        assert client.get("/files/" + relative).status_code == status
