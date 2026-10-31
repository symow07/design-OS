"""DIP-1A-1 — canonical serialization, hashing, HMAC key registry, system check."""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
from decimal import Decimal

import pytest
from django.conf import settings
from django.core.checks import Error, Warning
from django.test import override_settings

from apps.accounts.security import canonical as CA
from apps.accounts.security import signing as SG
from apps.accounts.security.checks import (
    SIGNING_MISCONFIGURED,
    SIGNING_MISCONFIGURED_DEV,
    check_decision_event_signing,
)

KEY_A = "a" * 40          # >= 32 bytes
KEY_B = "b" * 40
REGISTRY = json.dumps({"k1": KEY_A, "k2": KEY_B})

AT = dt.datetime(2026, 7, 14, 12, 0, 0, tzinfo=dt.timezone.utc)


@pytest.fixture(autouse=True)
def _reset_registry():
    SG.reset_registry()
    yield
    SG.reset_registry()


def _payload(**kw):
    base = dict(
        event_id="evt-0001", sequence_number=1, actor_id=7,
        role_used="LEGAL_REVIEWER", action="confirm_ownership",
        subject_type="FontFace", subject_id="face-abc",
        payload={"note": "ok"}, previous_event_hash=None,
        created_at=AT, signing_key_id="k1",
    )
    base.update(kw)
    return CA.signed_payload(**base)


# === the signed-field contract ===============================================
def test_the_signed_fields_are_declared_and_exact():
    assert CA.SIGNED_FIELDS == (
        "schema_version", "event_id", "sequence_number", "actor_id", "role_used",
        "action", "subject_type", "subject_id", "payload", "previous_event_hash",
        "created_at", "signing_key_id")
    doc = _payload()
    assert set(doc) == set(CA.SIGNED_FIELDS)


def test_database_generated_fields_are_excluded_from_the_signature():
    for f in ("id", "content_hash", "hmac_signature", "created_at_db", "updated_at"):
        assert f in CA.EXCLUDED_FIELDS
        assert f not in CA.SIGNED_FIELDS


def test_the_signed_document_is_exactly_the_declared_fields():
    doc = _payload()
    assert set(doc) == set(CA.SIGNED_FIELDS)


def test_a_non_object_payload_is_refused():
    with pytest.raises(CA.CanonicalizationError, match="must be an object"):
        CA.canonical_bytes(["not", "an", "object"])


# === determinism =============================================================
def test_key_order_never_changes_the_bytes():
    a = CA.canonical_bytes({"b": 1, "a": 2, "c": {"z": 1, "y": 2}})
    b = CA.canonical_bytes({"c": {"y": 2, "z": 1}, "a": 2, "b": 1})
    assert a == b
    assert a == b'{"a":2,"b":1,"c":{"y":2,"z":1}}'


def test_there_is_no_incidental_whitespace():
    assert CA.canonical_bytes({"a": 1, "b": [1, 2]}) == b'{"a":1,"b":[1,2]}'


def test_list_order_is_preserved_because_it_is_semantic():
    """A list of attesters is not the same decision in a different order."""
    a = CA.canonical_bytes({"x": ["alice", "bob"]})
    b = CA.canonical_bytes({"x": ["bob", "alice"]})
    assert a != b


def test_utf8_is_emitted_not_escaped():
    assert CA.canonical_bytes({"n": "Rosé"}) == '{"n":"Rosé"}'.encode("utf-8")


# === the refusals ============================================================
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nan_and_infinity_are_refused(bad):
    with pytest.raises(CA.CanonicalizationError):
        CA.canonical_bytes({"x": bad})


def test_a_naive_datetime_is_refused():
    with pytest.raises(CA.CanonicalizationError, match="names no instant"):
        CA.canonical_bytes({"t": dt.datetime(2026, 7, 14, 12, 0, 0)})


def test_a_datetime_is_normalised_to_utc():
    tz = dt.timezone(dt.timedelta(hours=2))
    local = dt.datetime(2026, 7, 14, 14, 0, 0, tzinfo=tz)
    assert CA.canonical_bytes({"t": local}) == CA.canonical_bytes({"t": AT})


def test_a_decimal_is_a_string_not_a_float():
    """Decimal -> float would lose precision and change the bytes."""
    assert CA.canonical_bytes({"d": Decimal("1.10")}) == b'{"d":"1.10"}'
    assert CA.canonical_bytes({"d": Decimal("1.10")}) != \
        CA.canonical_bytes({"d": Decimal("1.1")})


def test_an_unsupported_type_raises_and_is_never_coerced():
    class Weird:
        def __str__(self):
            return "weird"

    with pytest.raises(CA.CanonicalizationError, match="NOT coerced"):
        CA.canonical_bytes({"x": Weird()})


def test_a_non_string_key_is_refused():
    with pytest.raises(CA.CanonicalizationError, match="must be strings"):
        CA.canonical_bytes({1: "a"})


def test_str_of_a_dict_is_never_what_gets_signed():
    doc = {"b": 1, "a": 2}
    assert CA.canonical_bytes(doc) != str(doc).encode()


# === golden vectors — the bytes are PINNED ===================================
# If a refactor changes what the serializer emits, these fail. That is the point:
# a serializer that can change without anyone noticing can silently reinterpret
# every historical event, and the chain would be worthless exactly when it mattered.
GOLDEN_BYTES = (
    b'{"action":"confirm_ownership","actor_id":7,"created_at":"2026-07-14T12:00:00+00:00"'
    b',"event_id":"evt-0001","payload":{"note":"ok"},"previous_event_hash":null,'
    b'"role_used":"LEGAL_REVIEWER","schema_version":"decision_event/1.0",'
    b'"sequence_number":1,"signing_key_id":"k1","subject_id":"face-abc",'
    b'"subject_type":"FontFace"}'
)
GOLDEN_HASH = hashlib.sha256(GOLDEN_BYTES).hexdigest()
GOLDEN_HMAC = hmac.new(KEY_A.encode(), GOLDEN_BYTES, hashlib.sha256).hexdigest()


def test_golden_vector_bytes():
    assert CA.canonical_bytes(_payload()) == GOLDEN_BYTES


def test_golden_vector_content_hash():
    assert CA.content_hash(_payload()) == GOLDEN_HASH
    assert len(GOLDEN_HASH) == 64


@override_settings(DECISION_EVENT_HMAC_KEYS=REGISTRY,
                   DECISION_EVENT_ACTIVE_KEY_ID="k1")
def test_golden_vector_hmac():
    sig, kid = SG.sign(_payload())
    assert kid == "k1"
    assert sig == GOLDEN_HMAC
    assert SG.verify(_payload(), sig, "k1") is True


# === v2 golden vector — the REAL production envelope, also PINNED =================
# Every real DecisionEvent is decision_event/2.0. Without a byte-pinned vector, a v2
# serializer drift would go unnoticed (sign and verify move together and stay
# self-consistent) while every previously-signed v2 event silently failed. Same
# discipline as v1; supersedes_event_id and signature_algorithm are now inside the bytes.
def _payload_v2(**kw):
    base = dict(
        event_id="evt-0002", sequence_number=2, actor_id=7,
        role_used="LEGAL_REVIEWER", action="confirm_ownership",
        subject_type="FontFace", subject_id="face-abc",
        payload={"note": "ok"}, previous_event_hash="00ff",
        supersedes_event_id="evt-0001", created_at=AT, signing_key_id="k1",
        signature_algorithm="HMAC-SHA-256",
    )
    base.update(kw)
    return CA.signed_payload_v2(**base)


GOLDEN_BYTES_V2 = (
    b'{"action":"confirm_ownership","actor_id":7,"created_at":"2026-07-14T12:00:00+00:00"'
    b',"event_id":"evt-0002","payload":{"note":"ok"},"previous_event_hash":"00ff",'
    b'"role_used":"LEGAL_REVIEWER","schema_version":"decision_event/2.0",'
    b'"sequence_number":2,"signature_algorithm":"HMAC-SHA-256","signing_key_id":"k1",'
    b'"subject_id":"face-abc","subject_type":"FontFace","supersedes_event_id":"evt-0001"}'
)
GOLDEN_HASH_V2 = hashlib.sha256(GOLDEN_BYTES_V2).hexdigest()
GOLDEN_HMAC_V2 = hmac.new(KEY_A.encode(), GOLDEN_BYTES_V2, hashlib.sha256).hexdigest()


def test_golden_vector_v2_bytes():
    assert CA.canonical_bytes(_payload_v2()) == GOLDEN_BYTES_V2


def test_golden_vector_v2_content_hash():
    assert CA.content_hash(_payload_v2()) == GOLDEN_HASH_V2


@override_settings(DECISION_EVENT_HMAC_KEYS=REGISTRY,
                   DECISION_EVENT_ACTIVE_KEY_ID="k1")
def test_golden_vector_v2_hmac():
    sig, kid = SG.sign(_payload_v2())
    assert kid == "k1" and sig == GOLDEN_HMAC_V2


def test_v2_null_supersedes_is_the_common_path():
    # the normal (non-superseding) event carries supersedes_event_id: null
    doc = _payload_v2(supersedes_event_id=None)
    assert b'"supersedes_event_id":null' in CA.canonical_bytes(doc)


# === the key registry ========================================================
@override_settings(DECISION_EVENT_HMAC_KEYS=REGISTRY,
                   DECISION_EVENT_ACTIVE_KEY_ID="k1")
def test_only_the_active_key_signs():
    r = SG.get_registry(refresh=True)
    assert r.active_key_id == "k1"
    assert r.key_ids == ("k1", "k2")
    _, kid = r.sign(_payload())
    assert kid == "k1"                       # never k2, whatever else is registered


@override_settings(DECISION_EVENT_HMAC_KEYS=REGISTRY,
                   DECISION_EVENT_ACTIVE_KEY_ID="k2")
def test_a_rotated_key_still_verifies_old_events():
    """Rotation must not invalidate history."""
    r = SG.get_registry(refresh=True)
    assert r.active_key_id == "k2"
    # an event signed long ago under k1 still verifies...
    assert r.verify(_payload(), GOLDEN_HMAC, "k1") is True
    # ...while new events are signed with k2
    sig, kid = r.sign(_payload())
    assert kid == "k2"
    assert sig != GOLDEN_HMAC


@override_settings(DECISION_EVENT_HMAC_KEYS=REGISTRY,
                   DECISION_EVENT_ACTIVE_KEY_ID="k1")
def test_an_unknown_key_id_fails_closed():
    with pytest.raises(SG.UnknownSigningKey, match="FAIL CLOSED"):
        SG.verify(_payload(), GOLDEN_HMAC, "k99")


@override_settings(DECISION_EVENT_HMAC_KEYS=REGISTRY,
                   DECISION_EVENT_ACTIVE_KEY_ID="k1")
def test_a_tampered_payload_does_not_verify():
    tampered = _payload(payload={"note": "definitely fine"})
    assert SG.verify(tampered, GOLDEN_HMAC, "k1") is False


@override_settings(DECISION_EVENT_HMAC_KEYS=REGISTRY,
                   DECISION_EVENT_ACTIVE_KEY_ID="k1")
def test_an_empty_or_wrong_signature_does_not_verify():
    assert SG.verify(_payload(), "", "k1") is False
    assert SG.verify(_payload(), "0" * 64, "k1") is False


# === invalid configuration fails closed ======================================
@override_settings(DECISION_EVENT_HMAC_KEYS="", DECISION_EVENT_ACTIVE_KEY_ID="")
def test_missing_configuration_means_no_event_can_be_signed():
    ok, detail = SG.signing_available()
    assert ok is False
    assert "not configured" in detail
    with pytest.raises(SG.SigningConfigurationError):
        SG.sign(_payload())


@override_settings(DECISION_EVENT_HMAC_KEYS=json.dumps({"k1": KEY_A}),
                   DECISION_EVENT_ACTIVE_KEY_ID="missing")
def test_an_active_key_without_material_fails_closed():
    ok, detail = SG.signing_available()
    assert ok is False
    assert "FAIL CLOSED" in detail


@override_settings(DECISION_EVENT_HMAC_KEYS='{"k1":"' + KEY_A + '","k1":"' + KEY_B + '"}',
                   DECISION_EVENT_ACTIVE_KEY_ID="k1")
def test_a_duplicate_key_id_fails_startup_validation():
    ok, detail = SG.signing_available()
    assert ok is False
    assert "duplicate signing key id" in detail


@override_settings(DECISION_EVENT_HMAC_KEYS=json.dumps({"k1": "short"}),
                   DECISION_EVENT_ACTIVE_KEY_ID="k1")
def test_a_short_key_is_refused():
    ok, detail = SG.signing_available()
    assert ok is False
    assert "decoration" in detail


@override_settings(DECISION_EVENT_HMAC_KEYS="not json",
                   DECISION_EVENT_ACTIVE_KEY_ID="k1")
def test_malformed_registry_json_fails_closed():
    ok, _ = SG.signing_available()
    assert ok is False


def test_the_signing_key_is_never_the_django_secret_key():
    """The real property is BEHAVIOURAL: signing.py must never READ settings.SECRET_KEY.
    Reusing it would mean anything able to forge a session could also forge a decision
    event — and the two must fail independently."""
    import ast
    from pathlib import Path

    src = (Path(settings.BASE_DIR) / "apps" / "accounts" / "security"
           / "signing.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "SECRET_KEY":
            raise AssertionError("signing.py reads settings.SECRET_KEY")
    # ...and it DOES read the dedicated key
    assert "DECISION_EVENT_HMAC_KEYS" in src
    assert settings.SECRET_KEY  # exists, and is used for sessions — not for this


# === the system check ========================================================
@override_settings(DEBUG=False, DECISION_EVENT_HMAC_KEYS="",
                   DECISION_EVENT_ACTIVE_KEY_ID="")
def test_the_system_check_is_an_error_in_production():
    errs = check_decision_event_signing(None)
    assert len(errs) == 1
    assert isinstance(errs[0], Error)
    assert errs[0].id == SIGNING_MISCONFIGURED


@override_settings(DEBUG=True, DECISION_EVENT_HMAC_KEYS="",
                   DECISION_EVENT_ACTIVE_KEY_ID="")
def test_the_system_check_is_a_warning_in_development():
    errs = check_decision_event_signing(None)
    assert len(errs) == 1
    assert isinstance(errs[0], Warning)
    assert errs[0].id == SIGNING_MISCONFIGURED_DEV      # W001, not E001


@override_settings(DEBUG=False, DECISION_EVENT_HMAC_KEYS=REGISTRY,
                   DECISION_EVENT_ACTIVE_KEY_ID="k1")
def test_a_valid_configuration_passes_the_system_check():
    assert check_decision_event_signing(None) == []


# === the head signature (used by 1A-4) =======================================
def test_the_chain_head_is_signable():
    head = CA.signed_head_payload(
        chain_id="global", terminal_sequence_number=42,
        terminal_event_hash="ab" * 32, event_count=42, signing_key_id="k1")
    assert set(head) == set(CA.HEAD_SIGNED_FIELDS)
    assert CA.content_hash(head)


def test_the_head_records_the_event_count_so_truncation_is_detectable():
    """Signing events alone leaves a gap: delete the last N rows and every remaining
    link still verifies. The head's count and terminal hash close it."""
    assert "event_count" in CA.HEAD_SIGNED_FIELDS
    assert "terminal_sequence_number" in CA.HEAD_SIGNED_FIELDS
    assert "terminal_event_hash" in CA.HEAD_SIGNED_FIELDS


# === scope boundary, updated by 1A-2 ========================================
# In 1A-1 this asserted `models.py` was EMPTY and NO migration existed — correct
# then, because 1A-1 was pure functions (canonical serialization, signing, checks)
# and deliberately added no persistence. 1A-2 legitimately changes that reality:
# it introduces ReviewerProfile / ReviewerRoleAssignment by COMPOSITION and their
# single 0001_initial migration. The assertions are therefore inverted here on
# purpose (not deleted-to-green) — the point they defended (1A-1 shipped no models)
# is now history; the point that still holds is that the User model was NOT swapped.
def test_1a2_added_models_by_composition_without_swapping_user():
    from pathlib import Path

    acc = Path(settings.BASE_DIR) / "apps" / "accounts"
    assert (acc / "models.py").read_text().strip() != "", \
        "1A-2 adds ReviewerProfile / ReviewerRoleAssignment"
    migrations = sorted(p.name for p in (acc / "migrations").glob("*.py")
                        if p.name != "__init__.py")
    # 1A-2 introduced 0001_initial; 1A-3 added 0002_authorizationaudit. Both are the
    # accounts app's own migrations — the point that still holds is that identity was
    # added by composition, with no AUTH_USER_MODEL swap (asserted below).
    assert "0001_initial.py" in migrations, migrations


def test_the_user_model_was_not_swapped():
    # Composition, never a custom AUTH_USER_MODEL. request.user.pk stays the
    # authoritative actor id; reviewer meaning is attached, never substituted.
    assert settings.AUTH_USER_MODEL == "auth.User"
