"""HAYAT's bounded paid operations and immutable picked source, without network."""
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from datetime import datetime, timedelta

import numpy as np
from PIL import Image
import pytest

from apps.pipeline.services import round_balm_review as review


@pytest.mark.parametrize("operation", ["image", "jury", "seed", "eye-r2", "reading-K3"])
def test_unauthorized_operation_refused_before_input_read_or_reservation(operation, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Unauthorized operation reached an input or spend boundary")
    monkeypatch.setattr(review.calls, "image_block", forbidden)
    monkeypatch.setattr(review.spend, "reserve", forbidden)
    with pytest.raises(ValueError, match="Only the eye and two blind readings"):
        review.paid_text(operation, "irrelevant", [("bad", Path("missing-image.png"))], ceiling=3)


def test_paid_request_reserves_first_and_never_sends_source_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "OUT", tmp_path)
    events = []
    source = Path("/private/picked-D1-A-HAYAT-master.png")
    monkeypatch.setattr(review.calls, "image_block", lambda path: (
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AA=="}},
        {"path": str(path), "sha256": "0" * 64, "px": [10, 10]}))
    monkeypatch.setattr(review.spend, "reserve", lambda *args, **kwargs: events.append(("reserve", args, kwargs)) or "private-id")
    monkeypatch.setattr(review.spend, "rejected_status", lambda exc: None)
    class StopBeforeNetwork(Exception):
        pass
    def capture(**kwargs):
        events.append(("request", kwargs))
        raise StopBeforeNetwork()
    client = SimpleNamespace(messages=SimpleNamespace(create=capture))
    with pytest.raises(StopBeforeNetwork):
        review.paid_text("reading-K1", "Describe the packaging idea in ten words.",
                         [("K1: nine panels of one lip balm object.", source)], ceiling=.06,
                         max_tokens=600, client=client)
    assert [event[0] for event in events] == ["reserve", "request"]
    reservation = events[0][2]
    assert reservation["budget_prefix"] == "r1-balm-b/" and reservation["prefix_cap"] == 3
    assert reservation["count_cap"] == 1
    actual_request = json.dumps(events[1][1])
    assert str(source) not in actual_request
    assert "HAYAT" not in actual_request and "D1" not in actual_request
    assert "sha256" not in actual_request
    request_file = tmp_path / "calls/reading-K1.request.json"
    assert request_file.exists()
    assert json.loads((tmp_path / "calls/reading-K1.json").read_text())["status"] == "provider_error"
    # A retained attempted request prevents a second reserve/payment.
    with pytest.raises(ValueError, match="reconciliation"):
        review.paid_text("reading-K1", "Describe the packaging idea in ten words.",
                         [("K1: nine panels of one lip balm object.", source)], ceiling=.06,
                         max_tokens=600, client=client)
    assert len(events) == 2


@pytest.mark.parametrize('reply_budget', [4000, 8001])
def test_close_completion_rejects_invalid_reply_budget_before_inputs(reply_budget, monkeypatch):
    monkeypatch.setattr(review, 'completion_inputs', lambda: pytest.fail('Invalid budget read inputs'))
    with pytest.raises(ValueError, match='Completion reply budget'):
        review.complete_eye(max_tokens=reply_budget)


def test_close_completion_reserves_its_own_one_dollar_scope_once(tmp_path, monkeypatch):
    monkeypatch.setattr(review, 'OUT', tmp_path)
    monkeypatch.setattr(review, 'completion_inputs', lambda: ('Complete the authorized review.', []))
    events = []
    monkeypatch.setattr(review.spend, 'reserve',
                        lambda *args, **kwargs: events.append(('reserve', args, kwargs)) or 'close-id')
    monkeypatch.setattr(review.spend, 'rejected_status', lambda exc: None)
    class StopBeforeNetwork(Exception):
        pass
    def capture(**kwargs):
        events.append(('request', kwargs))
        raise StopBeforeNetwork()
    client = SimpleNamespace(messages=SimpleNamespace(create=capture))
    with pytest.raises(StopBeforeNetwork):
        review.complete_eye(client=client)
    assert [event[0] for event in events] == ['reserve', 'request']
    assert events[0][1][1] == 'r1-balm-c/eye-r2'
    assert events[0][2]['budget_prefix'] == 'r1-balm-c/'
    assert events[0][2]['prefix_cap'] == 1
    assert events[0][2]['count_cap'] == 1
    assert events[1][1]['max_tokens'] == 6400
    request = json.loads((tmp_path / 'calls/eye-r2.request.json').read_text())
    assert request['reserved_usd'] <= request['ceiling_usd'] == .20
    with pytest.raises(ValueError, match='reconciliation'):
        review.complete_eye(client=client)
    assert len(events) == 2
    assert not (tmp_path / 'eye-r2.json').exists()


def test_close_completion_does_not_publish_an_invalid_final_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr(review, 'OUT', tmp_path)
    monkeypatch.setattr(review, 'completion_inputs', lambda: ('Review.', []))
    monkeypatch.setattr(review, '_paid_text', lambda *args, **kwargs: {
        'status': 'complete', 'payload': {'verdict': 'pass'}})
    with pytest.raises(ValueError, match='final verdict schema'):
        review.complete_eye()
    assert not (tmp_path / 'eye-r2.json').exists()


def test_completion_preserves_allowed_list_and_refuses_changed_archived_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(review, 'OUT', tmp_path)
    differences = '{"allowed": ["unchanged painted fragments"]}\n'
    (tmp_path / 'allowed-differences.json').write_text(differences)
    panel = tmp_path / 'back.png'
    for path in (panel, tmp_path / 'drawing.png', tmp_path / 'leaflet-flat.png'):
        path.write_bytes(path.name.encode())
    monkeypatch.setattr(review, 'comparisons', lambda: [('Back source and master.', panel)])
    prompt, images = review.completion_inputs()
    assert differences in prompt and 'D-R1C-1/2' in prompt
    assert len(images) == 3
    retained = tmp_path / 'eye-inputs/r2/back.png'
    assert retained.read_bytes() == b'back.png'
    panel.write_bytes(b'changed after archiving')
    with pytest.raises(ValueError, match='cannot be replaced'):
        review.completion_inputs()
    assert retained.read_bytes() == b'back.png'
    assert (tmp_path / 'allowed-differences.json').read_text() == differences


def test_two_blind_inputs_have_same_question_no_source_or_prior_reading(tmp_path, monkeypatch):
    output = tmp_path / "output"
    output.mkdir()
    monkeypatch.setattr(review, "REPO", tmp_path)
    monkeypatch.setattr(review, "OUT", output)
    labels = {}
    for label, source in (("K1", "master-secret.png"), ("K2", "sketch-secret.png")):
        path = tmp_path / source
        path.write_bytes(label.encode())
        labels[label] = {"path": source, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (output / "reading-map.json").write_text(json.dumps({"labels": labels}))
    captured = []
    def paid(operation, prompt, images, **kwargs):
        captured.append({"operation": operation, "prompt": prompt, "images": images, **kwargs})
        return {"payload": {"idea_in_ten_words": "One two three four five six seven eight nine ten"}}
    monkeypatch.setattr(review, "paid_text", paid)
    result = review.readings()
    assert [row["operation"] for row in captured] == ["reading-K1", "reading-K2"]
    assert captured[0]["prompt"] == captured[1]["prompt"]
    for row in captured:
        visible = row["prompt"] + " " + " ".join(caption for caption, path in row["images"])
        assert len(row["images"]) == 1 and row["ceiling"] == .06
        assert all(word not in visible.lower() for word in ("master", "sketch", "hayat", "d1/a", "one two three"))
    assert all(row["exactly_ten"] for row in result["labels"].values())
    assert result["gates_nothing"] is True


def test_blind_map_pin_mismatch_refused_before_call(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "REPO", tmp_path)
    monkeypatch.setattr(review, "OUT", tmp_path)
    (tmp_path / "input.png").write_bytes(b"changed")
    (tmp_path / "reading-map.json").write_text(json.dumps({"labels": {
        "K1": {"path": "input.png", "sha256": "0" * 64}}}))
    monkeypatch.setattr(review, "paid_text", lambda *args, **kwargs: pytest.fail("Changed blind input reached payment"))
    with pytest.raises(ValueError, match="Blind input changed"):
        review.readings()


@pytest.fixture
def audit_scope(tmp_path, monkeypatch, settings):
    entry = json.loads((review.OUT / "entry.json").read_text())
    anchor = datetime.fromisoformat(subprocess.check_output(
        ["git", "show", "-s", "--format=%cI", entry["entry_commit"]], cwd=review.REPO, text=True).strip())
    monkeypatch.setattr(review, "OUT", tmp_path)
    (tmp_path / "entry.json").write_text(json.dumps(entry))
    settings.RESCUE_SPEND_ROOT = tmp_path / "private-reservations"

    def add(identifier, stamp, *, provider="openai", operation="outside-prefix/image/probe", model="gpt-image-2"):
        with review.spend._connect() as ledger:
            ledger.execute("INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (identifier, stamp.date().isoformat(), provider, operation, model, None,
                            100, 0, "rejected_unbilled", None, None, "private-fixture",
                            stamp.isoformat(), stamp.isoformat()))
    return anchor, add


@pytest.mark.django_db
def test_audit_catches_out_of_prefix_image_attempts_in_both_ledgers(audit_scope):
    from apps.pipeline.models import ApiCallRecord
    start, add = audit_scope
    stamp = start + timedelta(minutes=1)
    add("private-rejected-image", stamp)
    row = ApiCallRecord.objects.create(provider="openai", model="gpt-image-2",
                                       operation="unrelated-generation", image_count=1)
    ApiCallRecord.objects.filter(pk=row.pk).update(created_at=stamp)
    before = ApiCallRecord.objects.values().get(pk=row.pk)
    result = review.audit(as_of=start + timedelta(hours=1))
    assert result["image_calls"] == 0  # The round prefix alone misses both attempts.
    session = result["call_audit"]["session"]
    assert session["reservation_journal"]["image_attempts"] == 1
    assert session["application_api_ledger"]["image_attempts"] == 1
    assert session["zero_image_attempts_in_both_ledgers"] is False
    assert session["only_eye_and_readings_in_both_ledgers"] is False
    assert ApiCallRecord.objects.values().get(pk=row.pk) == before
    with review.spend._connect() as ledger:
        assert ledger.execute("SELECT state FROM calls WHERE id=?", ("private-rejected-image",)).fetchone()[0] == "rejected_unbilled"


@pytest.mark.django_db
def test_audit_distinguishes_earlier_same_day_images_from_current_master_session(audit_scope):
    start, add = audit_scope
    add("earlier-image", start - timedelta(minutes=1))
    add("authorized-eye", start + timedelta(minutes=1), provider="anthropic",
        operation=review.PREFIX + "eye-r0", model="claude-opus-5-5")
    result = review.audit(as_of=start + timedelta(hours=1))["call_audit"]
    assert result["session"]["zero_image_attempts_in_both_ledgers"] is True
    assert result["session"]["only_eye_and_readings_in_both_ledgers"] is True
    assert result["calendar_day"]["reservation_journal"]["image_attempts"] == 1
    assert result["calendar_day"]["zero_image_attempts_in_both_ledgers"] is False
    assert result["session_lower_bound"]["conservative"] is True
    assert result["session"]["from_inclusive"] == start.isoformat()


def test_entire_picked_source_directory_is_byte_equal_to_entry_commit():
    source = "docs/rounds/r1-balm/developments/D1/A"
    entry = json.loads((review.OUT / "entry.json").read_text())
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", entry["entry_commit"], "--", source],
                                    cwd=review.REPO, text=True).splitlines()
    assert len(paths) >= 20
    for name in paths:
        original = subprocess.check_output(["git", "show", entry["entry_commit"] + ":" + name], cwd=review.REPO)
        assert (review.REPO / name).read_bytes() == original, name
    actual = {path.relative_to(review.REPO).as_posix() for path in (review.REPO / source).iterdir() if path.is_file()}
    assert actual == set(paths), "No source files added, removed, or replaced"


def test_cleaning_report_matches_actual_changed_pixels_and_protected_fragment_snapshot():
    report = json.loads((review.OUT / "cleaning.json").read_text())
    fidelity = json.loads((review.OUT / "fidelity.json").read_text())
    assert set(report["panels"]) == set(review.PANELS) == set(fidelity["panels"])
    for name in review.PANELS:
        row = report["panels"][name]
        before = np.array(Image.open(review.OUT / row["before"]).convert("RGB"))
        after = np.array(Image.open(review.OUT / row["after"]).convert("RGB"))
        mask = np.array(Image.open(review.OUT / row["mask"]).convert("L")) > 0
        protected = np.array(Image.open(review.OUT / "cleaning" / f"{name}-protected-ink.png").convert("L")) > 0
        changed = np.any(before != after, axis=2)
        assert np.array_equal(mask, changed), name
        assert row["changed_pixels"] == int(changed.sum())
        assert row["cleaned_area_share"] == pytest.approx(float(changed.mean()))
        assert not np.any(changed & protected), name
        assert hashlib.sha256((review.OUT / row["after"]).read_bytes()).hexdigest() == row["cleaned_sha256"]
        source = review.REPO / fidelity["panels"][name]["source"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row["source_sha256"]
