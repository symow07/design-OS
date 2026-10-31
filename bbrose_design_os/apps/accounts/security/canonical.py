"""Canonical serialization for signed decision events (DIP-1A-1).

**One serializer. Everything signs what this produces, and nothing signs anything
else.**

The rule that makes tamper evidence meaningful is boring and absolute: the bytes that
were signed must be reproducible, byte-for-byte, years later, by code that has been
refactored in between. If the serializer can drift, the signature proves nothing — a
verifier would simply be told "this doesn't match" for every historical event, and the
chain would be worthless exactly when it mattered.

So:

* **`str(dict)` and unspecified `json.dumps` are never signed.** Python's dict repr is a
  representation, not a format; its ordering, spacing and escaping are implementation
  details that have changed before and may change again.
* **Unsupported types raise.** They are never coerced silently — a `Decimal` quietly
  becoming a float would change the bytes and break every signature that followed.
* **NaN and Infinity are refused.** They are not valid JSON, they do not round-trip, and
  `NaN != NaN` makes verification non-deterministic by definition.
* **Datetimes are normalised to UTC ISO-8601 with an explicit offset.** A naive datetime
  is refused: it is an instant nobody can identify.
* **Mutable database-generated fields are excluded** (see `SIGNED_FIELDS`). A numeric
  primary key is assigned by the database *after* signing; signing it would be signing a
  value we do not yet have.

Golden vectors in the tests pin the exact bytes, content hashes and HMACs of known
payloads. If a future refactor changes what this function emits, those tests fail — which
is the entire point. **A serializer that can be changed without noticing is a serializer
that can silently reinterpret history.**
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import uuid
from decimal import Decimal

SCHEMA_VERSION = "decision_event/1.0"
SCHEMA_VERSION_V2 = "decision_event/2.0"
ENCODING = "utf-8"
SEPARATORS = (",", ":")          # fixed: no incidental whitespace in the signed bytes

# --- what is signed, and what is not --------------------------------------------
# Declared explicitly, asserted by test. What we sign must be STATED, never implied.
# v1.0 is FROZEN (golden vectors depend on it byte-for-byte) — never edit this tuple.
SIGNED_FIELDS = (
    "schema_version",
    "event_id",
    "sequence_number",
    "actor_id",
    "role_used",
    "action",
    "subject_type",
    "subject_id",
    "payload",
    "previous_event_hash",
    "created_at",
    "signing_key_id",
)

# v2.0 (DIP-1A-5 pre-correction): supersession and the algorithm are now SIGNED, so a
# tampered supersedes reference or a downgraded algorithm changes the content hash and is
# detected. Order is fixed; the canonical serializer sorts keys, so ORDER here is only
# documentation — the *set* is what the signature covers.
SIGNED_FIELDS_V2 = (
    "schema_version",
    "event_id",
    "sequence_number",
    "actor_id",
    "role_used",
    "action",
    "subject_type",
    "subject_id",
    "payload",
    "previous_event_hash",
    "supersedes_event_id",
    "created_at",
    "signing_key_id",
    "signature_algorithm",
)

# Excluded, and why. Every one of these is either assigned by the database after the
# signature is computed, or is itself derived from the signature.
EXCLUDED_FIELDS = {
    "id": "database-generated primary key — not known at signing time",
    "content_hash": "derived FROM the signed bytes; signing it would be circular",
    "hmac_signature": "derived from the signed bytes",
    "created_at_db": "auto_now_add would REPLACE the signed timestamp — the append "
                     "service generates created_at once and stores it unchanged",
    "updated_at": "mutable by definition; a signed event is never updated",
}


class CanonicalizationError(TypeError):
    """The value cannot be canonically serialized. It is never coerced silently."""


def _canonical(value):
    """Convert to a JSON-safe structure. Deterministic, or it raises."""
    if value is None or isinstance(value, (str, bool)):
        return value

    if isinstance(value, int):
        # bool is a subclass of int and was handled above
        return value

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise CanonicalizationError(
                f"{value!r} cannot be signed: NaN and Infinity are not valid JSON, do "
                "not round-trip, and (for NaN) are not even equal to themselves — "
                "verification could never be deterministic.")
        return value

    if isinstance(value, Decimal):
        if not value.is_finite():
            raise CanonicalizationError(
                f"{value!r} cannot be signed: a non-finite Decimal has no canonical "
                "form.")
        # A STRING, deliberately. Decimal -> float would lose precision and change the
        # bytes; Decimal("1.10") and Decimal("1.1") are different values and must
        # produce different signatures.
        return format(value, "f")

    if isinstance(value, dt.datetime):
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise CanonicalizationError(
                "a naive datetime cannot be signed: it names no instant. Supply a "
                "timezone-aware datetime; it will be normalised to UTC.")
        return value.astimezone(dt.timezone.utc).isoformat()

    if isinstance(value, dt.date):
        return value.isoformat()

    if isinstance(value, uuid.UUID):
        return str(value)

    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise CanonicalizationError(
                    f"object keys must be strings; got {type(k).__name__}. A non-string "
                    "key has no deterministic ordering.")
            out[k] = _canonical(v)
        return out

    if isinstance(value, (list, tuple)):
        # ORDER IS PRESERVED. A list's order is semantic — a list of attesters is not
        # the same decision in a different order, and sorting it would erase that.
        return [_canonical(v) for v in value]

    raise CanonicalizationError(
        f"{type(value).__name__} is not canonically serializable. It is NOT coerced "
        "silently: an unsupported type that quietly became a string would change the "
        "signed bytes and break every signature computed after it. Convert it "
        "explicitly at the call site.")


def canonical_bytes(payload: dict) -> bytes:
    """THE bytes that get hashed and signed. Deterministic, or it raises."""
    if not isinstance(payload, dict):
        raise CanonicalizationError("the signed payload must be an object")
    return json.dumps(
        _canonical(payload),
        ensure_ascii=False,        # UTF-8, not \\uXXXX escapes
        allow_nan=False,           # belt and braces: NaN/Inf already raised above
        sort_keys=True,            # object key order is never incidental
        separators=SEPARATORS,     # no whitespace drift
    ).encode(ENCODING)


def signed_payload(*, event_id: str, sequence_number: int, actor_id: int,
                   role_used: str, action: str, subject_type: str, subject_id: str,
                   payload: dict, previous_event_hash: str | None,
                   created_at: dt.datetime, signing_key_id: str,
                   schema_version: str = SCHEMA_VERSION) -> dict:
    """Build the exact structure that will be signed — only `SIGNED_FIELDS`.

    `created_at` is generated ONCE by the append service and stored unchanged. It is
    never an `auto_now_add` value: the database would assign that *after* signing, and
    the signed timestamp would then differ from the persisted one — a chain that fails
    verification on every row, for a reason nobody could find.
    """
    doc = {
        "schema_version": schema_version,
        "event_id": event_id,
        "sequence_number": sequence_number,
        "actor_id": actor_id,
        "role_used": role_used,
        "action": action,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "payload": payload,
        "previous_event_hash": previous_event_hash,
        "created_at": created_at,
        "signing_key_id": signing_key_id,
    }
    missing = [f for f in SIGNED_FIELDS if f not in doc]
    extra = [k for k in doc if k not in SIGNED_FIELDS]
    if missing or extra:
        raise CanonicalizationError(
            f"the signed document must be exactly SIGNED_FIELDS "
            f"(missing={missing}, extra={extra})")
    return doc


def signed_payload_v2(*, event_id: str, sequence_number: int, actor_id: int,
                      role_used: str, action: str, subject_type: str, subject_id: str,
                      payload: dict, previous_event_hash: str | None,
                      supersedes_event_id: str | None, created_at: dt.datetime,
                      signing_key_id: str, signature_algorithm: str,
                      schema_version: str = SCHEMA_VERSION_V2) -> dict:
    """The v2.0 signed envelope: v1 plus SIGNED `supersedes_event_id` and
    `signature_algorithm`. `supersedes_event_id` is the referenced event's stable
    `event_id` (never a database pk), or None for a normal event."""
    doc = {
        "schema_version": schema_version,
        "event_id": event_id,
        "sequence_number": sequence_number,
        "actor_id": actor_id,
        "role_used": role_used,
        "action": action,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "payload": payload,
        "previous_event_hash": previous_event_hash,
        "supersedes_event_id": supersedes_event_id,
        "created_at": created_at,
        "signing_key_id": signing_key_id,
        "signature_algorithm": signature_algorithm,
    }
    missing = [f for f in SIGNED_FIELDS_V2 if f not in doc]
    extra = [k for k in doc if k not in SIGNED_FIELDS_V2]
    if missing or extra:
        raise CanonicalizationError(
            f"the signed document must be exactly SIGNED_FIELDS_V2 "
            f"(missing={missing}, extra={extra})")
    return doc


def content_hash(payload: dict) -> str:
    """SHA-256 over the canonical bytes."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


# --- the chain head is signed too (DIP-1A-4 will use this) ------------------------
HEAD_SCHEMA_VERSION = "decision_chain_head/1.0"
HEAD_SIGNED_FIELDS = (
    "schema_version",
    "chain_id",
    "terminal_sequence_number",
    "terminal_event_hash",
    "event_count",
    "signing_key_id",
)


def signed_head_payload(*, chain_id: str, terminal_sequence_number: int,
                        terminal_event_hash: str | None, event_count: int,
                        signing_key_id: str,
                        schema_version: str = HEAD_SCHEMA_VERSION) -> dict:
    """Sign the HEAD state, not just the events.

    Signing events alone leaves a gap: an attacker who deletes the last N rows leaves a
    chain that is internally consistent — every remaining link verifies. Signing the
    head's terminal sequence, terminal hash and event count makes that truncation
    detectable, because the head then disagrees with the table.

    It does NOT defeat a full rollback: an attacker who restores both the table and an
    older, genuinely-signed head from a backup produces a state that is internally
    consistent and indistinguishable from the past. Detecting that needs an external
    anchor (a transparency log, an external timestamp, write-once storage) and is
    documented as a known limitation rather than papered over.
    """
    doc = {
        "schema_version": schema_version,
        "chain_id": chain_id,
        "terminal_sequence_number": terminal_sequence_number,
        "terminal_event_hash": terminal_event_hash,
        "event_count": event_count,
        "signing_key_id": signing_key_id,
    }
    if set(doc) != set(HEAD_SIGNED_FIELDS):
        raise CanonicalizationError("the signed head must be exactly HEAD_SIGNED_FIELDS")
    return doc
