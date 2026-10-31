"""The signed decision-event chain: append service + verifier (DIP-1A-4).

`append_decision(...)` is the ONE way a `DecisionEvent` is written. It serialises on the
singleton chain head (`select_for_update`), validates the chain is currently consistent,
resolves idempotency, allocates the next sequence, generates the signed timestamp once,
signs the canonical 12-field envelope with the active HMAC key, inserts the event, and
re-signs the advanced head — all in one transaction. If anything fails, nothing is written
and the head does not move.

**What this proves and does not prove.** The HMAC proves an event/head was produced by an
instance holding the signing key; it is tamper *evidence*, not personal non-repudiation
(1A-1). Signing the head's terminal sequence/hash/count makes truncation detectable. It
does **not** defeat a full rollback: restoring both an older database and its older, validly
signed head yields an internally consistent past that no in-database check can distinguish —
closing that needs an external anchor (documented, not solved here).
"""
from __future__ import annotations

import dataclasses
import uuid

from django.db import transaction
from django.utils import timezone

from . import authz_policy as authz
from . import bootstrap_registry
from .authorization import authorize_actor
from .models import (
    _CHAIN_WRITE_TOKEN,
    DECISION_EVENT_SCHEMA,
    SIGNATURE_ALGORITHM,
    DecisionChainHead,
    DecisionEvent,
)
from .security import canonical, key_epochs, signing

CHAIN_ID = "global"                       # the one protected-decision chain
SUPPORTED_SCHEMAS = frozenset({DECISION_EVENT_SCHEMA})
SUBJECT_ID_MAX = 200
SUBJECT_TYPE_MAX = 64
# Payload keys that would shadow the signed envelope or smuggle unsigned meaning.
FORBIDDEN_PAYLOAD_KEYS = frozenset(canonical.SIGNED_FIELDS_V2) | {
    "content_hash", "hmac_signature", "supersedes_event_id"}


class ChainError(RuntimeError):
    """The chain is inconsistent, or the append is invalid. FAIL CLOSED."""


class ChainInconsistent(ChainError):
    """The EXISTING chain failed validation — refuse to append on top of it."""


class IdempotencyConflict(ChainError):
    """Same event_id, different content — a real conflict, not a safe retry."""


class AuthorizationDenied(ChainError):
    """The actor is not authorized to perform this action at append time. FAIL CLOSED."""


class SupersessionError(ChainError):
    """The supersession reference is invalid (missing/forward/incompatible subject)."""


# =================================================================================
# Validation of the CURRENT chain (before appending)
# =================================================================================
def _supersedes_event_id(ev: DecisionEvent) -> str | None:
    """The stable event_id of the superseded event (from the FK), or None. Rebuilt from
    the DATABASE relation so that repointing the FK changes the recomputed content hash
    and is therefore detected."""
    if ev.supersedes_event_id is None:
        return None
    return DecisionEvent.objects.values_list("event_id", flat=True).get(
        pk=ev.supersedes_event_id)


def _rebuild_event_doc(ev: DecisionEvent) -> dict:
    """The canonical signed envelope for a persisted event — recomputed, never stored.

    Dispatches on the event's schema version: real events are v2.0 (supersedes_event_id
    and signature_algorithm are SIGNED); v1.0 is recomputed only for legacy/golden
    fixtures, where those fields do not exist.
    """
    if ev.schema_version == canonical.SCHEMA_VERSION_V2:
        return canonical.signed_payload_v2(
            event_id=ev.event_id, sequence_number=ev.sequence_number,
            actor_id=ev.actor_id, role_used=ev.role_used, action=ev.action,
            subject_type=ev.subject_type, subject_id=ev.subject_id, payload=ev.payload,
            previous_event_hash=ev.previous_event_hash,
            supersedes_event_id=_supersedes_event_id(ev), created_at=ev.created_at,
            signing_key_id=ev.signing_key_id,
            signature_algorithm=ev.signature_algorithm,
            schema_version=ev.schema_version)
    return canonical.signed_payload(
        event_id=ev.event_id, sequence_number=ev.sequence_number, actor_id=ev.actor_id,
        role_used=ev.role_used, action=ev.action, subject_type=ev.subject_type,
        subject_id=ev.subject_id, payload=ev.payload,
        previous_event_hash=ev.previous_event_hash, created_at=ev.created_at,
        signing_key_id=ev.signing_key_id, schema_version=ev.schema_version)


def _head_doc(head: DecisionChainHead) -> dict:
    return canonical.signed_head_payload(
        chain_id=head.chain_id,
        terminal_sequence_number=head.terminal_sequence_number,
        terminal_event_hash=head.terminal_event_hash,
        event_count=head.event_count, signing_key_id=head.signing_key_id,
        schema_version=head.schema_version)


def _validate_current_chain(head: DecisionChainHead) -> None:
    """Fail closed unless the chain is internally consistent right now.

    Only the TERMINAL event and the head are checked here (the append path); a full walk
    is `verify_chain`. That is enough to guarantee the new link attaches to a sound tip:
    a broken interior would already have been caught when it was the tip.
    """
    count = DecisionEvent.objects.count()

    if head.is_genesis:
        # genesis must be pristine: no events may exist under a seq-0/count-0 head
        if count != 0:
            raise ChainInconsistent(
                f"genesis head but {count} event(s) exist — chain is corrupt.")
        return

    # non-genesis: the head must be signed and agree with the table
    if head.event_count != count:
        raise ChainInconsistent(
            f"head event_count={head.event_count} but {count} rows exist.")
    if not head.head_signature:
        raise ChainInconsistent("non-empty chain has an unsigned head.")

    terminal = DecisionEvent.objects.order_by("-sequence_number").first()
    if terminal is None:
        raise ChainInconsistent("head claims events but none exist.")
    if terminal.sequence_number != head.terminal_sequence_number:
        raise ChainInconsistent(
            f"head terminal seq {head.terminal_sequence_number} != "
            f"actual {terminal.sequence_number}.")
    if terminal.content_hash != head.terminal_event_hash:
        raise ChainInconsistent("head terminal hash != terminal event content hash.")
    # recompute the terminal event's content hash and HMAC — a mutated tip fails here. An
    # unknown/absent signing key raises SigningConfigurationError from the registry; we
    # re-raise it as ChainInconsistent so the whole append path fails closed with ONE
    # exception type ("unknown signing key blocks append"), rather than leaking a config
    # error out of append_decision.
    doc = _rebuild_event_doc(terminal)
    if canonical.content_hash(doc) != terminal.content_hash:
        raise ChainInconsistent("terminal event content hash does not verify.")
    try:
        # KEY EPOCH RESET: a terminal/head signed under a FORMALLY DECLARED
        # lost epoch is UNVERIFIABLE, not forged — its content hash and head
        # reconciliation (checked above) still guard structure. Refusing to
        # append here would freeze the chain forever and make the mandated
        # reaffirmation decisions impossible; the append itself re-signs the
        # head under the ACTIVE epoch. An UNDECLARED unknown key still fails
        # closed below.
        if not key_epochs.is_lost_key_id(terminal.signing_key_id):
            if not signing.verify(doc, terminal.hmac_signature,
                                  terminal.signing_key_id):
                raise ChainInconsistent("terminal event HMAC does not verify.")
        # the head signature itself must verify (with the key the head names)
        if not key_epochs.is_lost_key_id(head.signing_key_id):
            if not signing.verify(_head_doc(head), head.head_signature,
                                  head.signing_key_id):
                raise ChainInconsistent("head signature does not verify.")
    except signing.SigningConfigurationError as e:
        raise ChainInconsistent(f"chain references an unusable signing key: {e}") from None


# =================================================================================
# Append
# =================================================================================
def _validate_event_inputs(*, action, subject_type, subject_id, payload, supersedes):
    if action not in authz.ACTIONS:
        raise ChainError(f"unknown action {action!r}")
    if len(subject_type) > SUBJECT_TYPE_MAX or len(subject_id) > SUBJECT_ID_MAX:
        raise ChainError("subject identifiers exceed bounds")
    if not isinstance(payload, dict):
        raise ChainError("payload must be a JSON object")
    forbidden = FORBIDDEN_PAYLOAD_KEYS & set(payload)
    if forbidden:
        raise ChainError(f"payload may not contain reserved keys: {sorted(forbidden)}")
    try:
        canonical.canonical_bytes(payload)          # must be canonical-serialisable
    except canonical.CanonicalizationError as e:
        raise ChainError(f"payload is not canonically serialisable: {e}") from None


def _supersession_action_compatible(new_action, prior_action):
    if new_action == prior_action:
        return True
    # DIP-1B-3 corrections are a separately authorized action, but remain in the same
    # bounded classification decision domain. DIP-1C-5B human semantic metadata is a second
    # such family. No other cross-action pair is compatible.
    families = (
        (authz.CORRECT_INTELLIGENCE_CLASSIFICATION, {
            authz.RECORD_INTELLIGENCE_CLASSIFICATION,
            authz.CORRECT_INTELLIGENCE_CLASSIFICATION,
        }),
        (authz.CORRECT_HUMAN_SEMANTIC_METADATA, {
            authz.RECORD_HUMAN_SEMANTIC_METADATA,
            authz.CORRECT_HUMAN_SEMANTIC_METADATA,
        }),
    )
    return any(new_action == correction and prior_action in priors
               for correction, priors in families)


def _validate_supersession(supersedes, *, sequence, action, subject_type, subject_id):
    """A supersession must reference a persisted, PRECEDING event about the SAME subject
    AND a compatible action in the SAME decision domain — a correction supersedes the
    same *kind* of decision, not an unrelated one. DIP-1B-3 classification record/correction
    is the only bounded cross-action family. Forward, cross-subject and unrelated-action
    references are refused (defence in depth — the signed supersedes_event_id also makes
    tampering hash-detectable)."""
    if supersedes is None:
        return
    if supersedes.pk is None:
        raise SupersessionError("supersedes must reference a persisted event")
    if not DecisionEvent.objects.filter(pk=supersedes.pk).exists():
        raise SupersessionError("superseded event does not exist")
    if supersedes.sequence_number >= sequence:
        raise SupersessionError("supersedes must reference a PRECEDING event (no forward "
                                "or self references)")
    if (supersedes.subject_type, supersedes.subject_id) != (subject_type, subject_id):
        raise SupersessionError("supersedes must reference an event about the SAME "
                                "subject")
    if not _supersession_action_compatible(action, supersedes.action):
        raise SupersessionError(
            "supersedes must reference a compatible action in the SAME decision domain")


def _caller_identity(user, action, subject_type, subject_id, payload) -> tuple:
    """The idempotency identity: the CALLER's intent. Deliberately excludes role_used,
    which is DERIVED — a retry after a policy change must still be recognised as the same
    decision, and the original event stands."""
    return (user.pk, action, subject_type, subject_id, payload)


@transaction.atomic
def append_decision(*, user, action: str, payload: dict, subject=None,
                    event_id: str = None, supersedes: DecisionEvent = None
                    ) -> DecisionEvent:
    """Append one signed decision. **The caller does not choose `role_used`.**

    The service authorizes the actor itself (canonical 1A-3 service, at the append
    timestamp), derives `role_used` deterministically from policy, and writes that derived
    role into the SIGNED payload. The caller supplies only intent: authenticated actor,
    canonical action, subject, payload, optional idempotency id, optional supersession.

    Serialises on the chain head; fully transactional. Returns the created event, or — for
    an idempotent retry (same event_id, same caller intent) — the existing one. Fails
    closed: `AuthorizationDenied` if the actor may not act now, `ChainInconsistent` if the
    existing chain is unsound, `IdempotencyConflict` on same-id/different-intent,
    `SupersessionError` on a bad supersession reference.
    """
    subject_type, subject_id = ("", "")
    if subject is not None:
        subject_type, subject_id = (str(subject[0] or ""), str(subject[1] or ""))

    # 1-2) lock the singleton head. Fail closed if missing — NEVER create-on-append.
    try:
        head = DecisionChainHead.objects.select_for_update().get(pk=1)
    except DecisionChainHead.DoesNotExist:
        raise ChainInconsistent(
            "no chain head — genesis was not seeded; refusing to create one on append."
        ) from None

    # 3-4) validate the existing chain
    _validate_current_chain(head)

    # 5) resolve the event id (documented policy: server-generated uuid4 hex if absent)
    event_id = event_id or uuid.uuid4().hex

    # 6) idempotency on event_id, comparing CALLER INTENT (sequence/timestamp/role are not
    # available/derived yet). A matching retry returns the existing event WITHOUT
    # re-authorizing — it was authorized when first written.
    existing = DecisionEvent.objects.filter(event_id=event_id).first()
    if existing is not None:
        incoming = _caller_identity(user, action, subject_type, subject_id, payload)
        stored = (existing.actor_id, existing.action, existing.subject_type,
                  existing.subject_id, existing.payload)
        if stored == incoming:
            return existing                       # safe idempotent retry
        raise IdempotencyConflict(
            f"event_id {event_id!r} already exists with different content.")

    _validate_event_inputs(action=action, subject_type=subject_type,
                           subject_id=subject_id, payload=payload, supersedes=supersedes)

    # 7-8) one UTC timestamp, used for the authorization decision AND the signed field.
    now = timezone.now()
    subject_pair = (subject_type, subject_id) if (subject_type or subject_id) else None
    result = authorize_actor(user, action, subject=subject_pair, at=now)
    if not result.allowed:
        raise AuthorizationDenied(
            f"actor {user.pk} may not {action!r} at append time: {result.reason_code}")
    # role_used is DERIVED from policy — the caller never supplied it.
    role_used = result.role_used

    # 9) allocate sequence + previous-hash from the LOCKED head; validate supersession
    sequence = head.terminal_sequence_number + 1
    previous_hash = head.terminal_event_hash          # None at genesis -> event 1 null
    _validate_supersession(supersedes, sequence=sequence, action=action,
                           subject_type=subject_type, subject_id=subject_id)
    supersedes_event_id = supersedes.event_id if supersedes is not None else None

    return _sign_and_insert(
        head=head, sequence=sequence, previous_hash=previous_hash, event_id=event_id,
        user=user, role_used=role_used, action=action, subject_type=subject_type,
        subject_id=subject_id, payload=payload, supersedes=supersedes,
        supersedes_event_id=supersedes_event_id, now=now)


def _sign_and_insert(*, head, sequence, previous_hash, event_id, user, role_used, action,
                     subject_type, subject_id, payload, supersedes, supersedes_event_id,
                     now):
    """Steps 10-15: sign the v2 envelope, insert through the capability token, advance and
    re-sign the head. Shared verbatim by the ordinary append and the bootstrap ceremony so
    both produce byte-identical envelope structure — the ceremony gets NO alternate crypto,
    only an alternate authorization story that its payload states openly.

    The caller has already locked the head and decided that this event may exist.
    """
    registry = signing.get_registry()
    active_kid = registry.active_key_id
    doc = canonical.signed_payload_v2(
        event_id=event_id, sequence_number=sequence, actor_id=user.pk,
        role_used=role_used, action=action, subject_type=subject_type,
        subject_id=subject_id, payload=payload, previous_event_hash=previous_hash,
        supersedes_event_id=supersedes_event_id, created_at=now,
        signing_key_id=active_kid, signature_algorithm=SIGNATURE_ALGORITHM,
        schema_version=DECISION_EVENT_SCHEMA)
    content_hash = canonical.content_hash(doc)
    hmac_signature, kid = registry.sign(doc)

    event = DecisionEvent(
        sequence_number=sequence, event_id=event_id,
        schema_version=DECISION_EVENT_SCHEMA, actor=user, role_used=role_used,
        action=action, subject_type=subject_type, subject_id=subject_id, payload=payload,
        previous_event_hash=previous_hash, content_hash=content_hash,
        hmac_signature=hmac_signature, signing_key_id=kid,
        signature_algorithm=SIGNATURE_ALGORITHM, supersedes_event=supersedes,
        created_at=now)
    event.save(_chain_write_token=_CHAIN_WRITE_TOKEN, force_insert=True)

    head_doc = canonical.signed_head_payload(
        chain_id=head.chain_id, terminal_sequence_number=sequence,
        terminal_event_hash=content_hash, event_count=head.event_count + 1,
        signing_key_id=active_kid)
    head_sig, head_kid = registry.sign(head_doc)
    head.terminal_sequence_number = sequence
    head.terminal_event_hash = content_hash
    head.event_count = head.event_count + 1
    head.signing_key_id = head_kid
    head.head_signature = head_sig
    head.schema_version = canonical.HEAD_SCHEMA_VERSION
    head.save(_chain_write_token=_CHAIN_WRITE_TOKEN)
    return event


# The capability for the ONE non-role-authorized append. Held privately here; the ceremony
# service imports it. Identity check, never equality — unforgeable from request data.
_BOOTSTRAP_APPEND_TOKEN = object()


def append_bootstrap_initial_reviewer_event(*, capability, user, payload, head, now):
    """Append THE single-operator bootstrap event. Not a general escape hatch.

    This function cannot produce any other event: the action, `role_used` sentinel and
    payload schema are hard-coded, so there is no "skip authorization" switch for a caller
    to reuse or widen. It deliberately does not call `authorize_actor` — at genesis the
    operator holds no role, and inventing one is the falsification this whole correction
    exists to avoid.

    The caller (`bootstrap_ceremony`) owns the locks, the preconditions, the password
    challenge and the environment classification; this owns only the envelope.
    """
    if capability is not _BOOTSTRAP_APPEND_TOKEN:
        raise ChainError("bootstrap append requires the private ceremony capability")
    if not isinstance(payload, dict):
        raise ChainError("payload must be a JSON object")
    if set(payload) != bootstrap_registry.CEREMONY_PAYLOAD_FIELDS:
        raise ChainError("bootstrap payload fields are not exact")
    if payload.get("bootstrap_schema") != bootstrap_registry.BOOTSTRAP_CEREMONY_SCHEMA:
        raise ChainError("unsupported bootstrap ceremony schema")
    if "authz_snapshot" in payload:                 # unreachable above; stated anyway
        raise ChainError("a bootstrap event may not carry an authorization snapshot")
    forbidden = FORBIDDEN_PAYLOAD_KEYS & set(payload)
    if forbidden:
        raise ChainError(f"payload may not contain reserved keys: {sorted(forbidden)}")
    _validate_current_chain(head)
    if head.event_count != 0 or head.terminal_sequence_number != 0:
        raise ChainError("the bootstrap ceremony may only append at genesis")

    return _sign_and_insert(
        head=head, sequence=1, previous_hash=head.terminal_event_hash,
        event_id=uuid.uuid4().hex, user=user,
        role_used=bootstrap_registry.BOOTSTRAP_OPERATOR,
        action=bootstrap_registry.BOOTSTRAP_INITIAL_REVIEWER_ROLE,
        subject_type="User", subject_id=str(user.pk), payload=payload,
        supersedes=None, supersedes_event_id=None, now=now)


def append_bootstrap_closure_event(*, capability, user, payload, head, now):
    """Append THE closure of a lost-epoch bootstrap grant. Not a general
    revocation instrument.

    Preconditions this function itself enforces (the ceremony service owns
    locks and database writes):

    * the private capability token — unforgeable from request data;
    * the exact closure payload schema (no snapshot, no reserved keys);
    * the referenced legacy predecessor exists, IS the bootstrap grant
      ceremony event, and its signing key id is FORMALLY DECLARED lost
      (`key_epochs`) — so this path cannot revoke anything whose signature
      is still verifiable (those go through role policy), and cannot run
      twice (one closure per grant, checked here and by the verifier);
    * de-escalation only: the payload can name no role but the revoked one.
    """
    if capability is not _BOOTSTRAP_APPEND_TOKEN:
        raise ChainError("bootstrap append requires the private ceremony capability")
    if not isinstance(payload, dict):
        raise ChainError("payload must be a JSON object")
    if set(payload) != bootstrap_registry.CLOSURE_PAYLOAD_FIELDS:
        raise ChainError("closure payload fields are not exact")
    if payload.get("bootstrap_schema") != bootstrap_registry.CLOSURE_CEREMONY_SCHEMA:
        raise ChainError("unsupported closure ceremony schema")
    if payload.get("human_decision") != bootstrap_registry.CLOSURE_HUMAN_DECISION:
        raise ChainError("a closure may only express NO_LONGER_REQUIRED")
    forbidden = FORBIDDEN_PAYLOAD_KEYS & set(payload)
    if forbidden:
        raise ChainError(f"payload may not contain reserved keys: {sorted(forbidden)}")
    predecessor = DecisionEvent.objects.filter(
        event_id=payload.get("legacy_predecessor_event_id")).first()
    if predecessor is None or predecessor.action != \
            bootstrap_registry.BOOTSTRAP_INITIAL_REVIEWER_ROLE:
        raise ChainError("closure must reference the bootstrap grant ceremony event")
    if not key_epochs.is_lost_key_id(predecessor.signing_key_id):
        raise ChainError(
            "closure is reserved for grants signed under a DECLARED lost key "
            "epoch — a verifiable grant is revoked through role policy")
    if DecisionEvent.objects.filter(
            action=bootstrap_registry.BOOTSTRAP_REVIEWER_ROLE_CLOSURE).exists():
        raise ChainError("a closure ceremony event already exists")
    _validate_current_chain(head)

    return _sign_and_insert(
        head=head, sequence=head.terminal_sequence_number + 1,
        previous_hash=head.terminal_event_hash,
        event_id=uuid.uuid4().hex, user=user,
        role_used=bootstrap_registry.BOOTSTRAP_OPERATOR,
        action=bootstrap_registry.BOOTSTRAP_REVIEWER_ROLE_CLOSURE,
        subject_type="User", subject_id=str(user.pk), payload=payload,
        supersedes=None, supersedes_event_id=None, now=now)


def append_temporary_web_reviewer_grant_event(*, capability, user, payload,
                                              head, now):
    """Append ONE owner-authorized temporary WEB_REFERENCE_REVIEWER grant.

    Bounded by construction: the only role it can name is
    WEB_REFERENCE_REVIEWER (which authorizes no decision-chain action), the
    grant window may not exceed the registry maximum, and it exists only in
    the post-reaffirmation world — the closure event it references must
    exist. It can never widen into a general role-granting instrument.
    """
    if capability is not _BOOTSTRAP_APPEND_TOKEN:
        raise ChainError("bootstrap append requires the private ceremony capability")
    if not isinstance(payload, dict):
        raise ChainError("payload must be a JSON object")
    if set(payload) != bootstrap_registry.TEMP_GRANT_PAYLOAD_FIELDS:
        raise ChainError("temporary-grant payload fields are not exact")
    if payload.get("bootstrap_schema") != bootstrap_registry.TEMP_GRANT_SCHEMA:
        raise ChainError("unsupported temporary-grant ceremony schema")
    if payload.get("granted_role") not in \
            bootstrap_registry.TEMP_GRANT_ALLOWED_ROLES:
        raise ChainError("this ceremony may grant ONLY WEB_REFERENCE_REVIEWER")
    forbidden = FORBIDDEN_PAYLOAD_KEYS & set(payload)
    if forbidden:
        raise ChainError(f"payload may not contain reserved keys: {sorted(forbidden)}")
    from django.utils.dateparse import parse_datetime
    granted = parse_datetime(payload.get("granted_at") or "")
    expires = parse_datetime(payload.get("expires_at") or "")
    if granted is None or expires is None or expires <= granted:
        raise ChainError("grant window timestamps are invalid")
    if (expires - granted).days > bootstrap_registry.TEMP_GRANT_MAX_DAYS or \
            ((expires - granted).days == bootstrap_registry.TEMP_GRANT_MAX_DAYS
             and (expires - granted).seconds > 0):
        raise ChainError(
            f"grant exceeds {bootstrap_registry.TEMP_GRANT_MAX_DAYS} days")
    closure = DecisionEvent.objects.filter(
        event_id=payload.get("reaffirmation_closure_event_id")).first()
    if closure is None or closure.action != \
            bootstrap_registry.BOOTSTRAP_REVIEWER_ROLE_CLOSURE:
        raise ChainError(
            "temporary grant must reference the reaffirmation closure event")
    _validate_current_chain(head)

    return _sign_and_insert(
        head=head, sequence=head.terminal_sequence_number + 1,
        previous_hash=head.terminal_event_hash,
        event_id=uuid.uuid4().hex, user=user,
        role_used=bootstrap_registry.BOOTSTRAP_OPERATOR,
        action=bootstrap_registry.TEMPORARY_WEB_REVIEWER_GRANT,
        subject_type="User", subject_id=str(user.pk), payload=payload,
        supersedes=None, supersedes_event_id=None, now=now)


def append_pipeline_concept_selection_event(*, capability, user, payload,
                                            head, now):
    """Append ONE owner-authorized pipeline concept-selection RECORD
    (2C-2D-CORR-2 §3).

    Bounded by construction: the event grants nothing — the action is not in
    ``authz.ACTIONS`` so no role ever authorizes it, its payload signs an
    explicit non-authorization list, and the required statements pin it as a
    record of an EXISTING human decision (the GateDecision), never a new
    one. Idempotent per subject: a second call for the same task with the
    same decision identity returns the existing event; a different identity
    for the same task fails closed.
    """
    if capability is not _BOOTSTRAP_APPEND_TOKEN:
        raise ChainError("bootstrap append requires the private ceremony capability")
    if not isinstance(payload, dict):
        raise ChainError("payload must be a JSON object")
    if set(payload) != bootstrap_registry.CONCEPT_SELECT_PAYLOAD_FIELDS:
        raise ChainError("concept-selection payload fields are not exact")
    if payload.get("bootstrap_schema") != \
            bootstrap_registry.CONCEPT_SELECT_SCHEMA:
        raise ChainError("unsupported concept-selection ceremony schema")
    if payload.get("decision_code") != \
            bootstrap_registry.CONCEPT_SELECT_DECISION_CODE:
        raise ChainError("decision code must be SELECT_CONTAINER_CONCEPT")
    if tuple(payload.get("statements") or ()) != \
            bootstrap_registry.CONCEPT_SELECT_REQUIRED_STATEMENTS:
        raise ChainError("required statements are not exact")
    if tuple(payload.get("non_authorizations") or ()) != \
            bootstrap_registry.CONCEPT_SELECT_NON_AUTHORIZATIONS:
        raise ChainError("non-authorization list is not exact")
    forbidden = FORBIDDEN_PAYLOAD_KEYS & set(payload)
    if forbidden:
        raise ChainError(f"payload may not contain reserved keys: {sorted(forbidden)}")
    if payload.get("actor_user_id") != user.pk:
        raise ChainError("payload actor does not match the signing user")

    task_id = str(payload.get("task_id") or "")
    identity_keys = ("selected_image_id", "gate_decision_id",
                     "metadata_decision_record_hash", "visual_contract_hash")
    existing = DecisionEvent.objects.filter(
        action=bootstrap_registry.PIPELINE_CONTAINER_CONCEPT_SELECT,
        subject_type="DesignTask", subject_id=task_id,
        superseded_by__isnull=True).first()
    if existing is not None:
        stored = existing.payload or {}
        if all(stored.get(k) == payload.get(k) for k in identity_keys):
            return existing               # idempotent re-run, no duplicate
        raise ChainError(
            "a concept-selection event already exists for this task with a "
            "DIFFERENT decision identity — refusing to append a conflicting "
            "record")
    _validate_current_chain(head)

    return _sign_and_insert(
        head=head, sequence=head.terminal_sequence_number + 1,
        previous_hash=head.terminal_event_hash,
        event_id=uuid.uuid4().hex, user=user,
        role_used=bootstrap_registry.BOOTSTRAP_OPERATOR,
        action=bootstrap_registry.PIPELINE_CONTAINER_CONCEPT_SELECT,
        subject_type="DesignTask", subject_id=task_id, payload=payload,
        supersedes=None, supersedes_event_id=None, now=now)


# =================================================================================
# Read-only verification (never repairs)
# =================================================================================
@dataclasses.dataclass(frozen=True)
class VerificationResult:
    ok: bool
    event_count: int
    problems: tuple[str, ...]
    #: classified lost-key-epoch notices (key_epochs.LEGACY_STATE). Reported,
    #: auditable, NON-fatal at chain level — but the affected events remain
    #: fail-closed individually (verify_event refuses them). Without this
    #: separation one lost key would brick the whole chain forever and no
    #: reaffirmed decision could restore authority.
    legacy_notices: tuple[str, ...] = ()


def verify_chain() -> VerificationResult:
    """Walk the whole chain read-only and report every problem. Never writes or repairs."""
    problems: list[str] = []
    legacy: list[str] = []
    try:
        head = DecisionChainHead.objects.get(pk=1)
    except DecisionChainHead.DoesNotExist:
        return VerificationResult(False, 0, ("no chain head exists",))

    events = list(DecisionEvent.objects.order_by("sequence_number"))
    count = len(events)

    if count == 0:
        if not head.is_genesis:
            problems.append("no events but head is not a valid genesis state")
        return VerificationResult(not problems, 0, tuple(problems))

    # head/table agreement
    if head.event_count != count:
        problems.append(f"head event_count {head.event_count} != {count} rows")
    if head.is_genesis:
        problems.append("events exist but head is still genesis")

    by_pk = {ev.pk: ev for ev in events}
    prev_hash = None
    expected_seq = 1
    for ev in events:
        if ev.sequence_number != expected_seq:
            problems.append(
                f"sequence gap/disorder at {ev.sequence_number} (expected {expected_seq})")
        if ev.previous_event_hash != prev_hash:
            problems.append(f"seq {ev.sequence_number}: previous_event_hash linkage broken")
        # signature algorithm is now SIGNED (v2); reject anything but the pinned one
        if ev.signature_algorithm != SIGNATURE_ALGORITHM:
            problems.append(f"seq {ev.sequence_number}: invalid signature algorithm "
                            f"{ev.signature_algorithm!r}")
        doc = _rebuild_event_doc(ev)
        if canonical.content_hash(doc) != ev.content_hash:
            problems.append(f"seq {ev.sequence_number}: content hash does not verify")
        if key_epochs.is_lost_key_id(ev.signing_key_id):
            # formally declared lost epoch: authenticity is UNVERIFIABLE, not
            # tampered — content-hash/linkage checks above still hard-fail
            legacy.append(f"seq {ev.sequence_number}: " + key_epochs
                          .legacy_problem(ev.signing_key_id))
        else:
            try:
                if not signing.verify(doc, ev.hmac_signature,
                                      ev.signing_key_id):
                    problems.append(
                        f"seq {ev.sequence_number}: HMAC does not verify")
            except signing.SigningConfigurationError as e:
                problems.append(f"seq {ev.sequence_number}: key problem — {e}")
        if ev.actor_id is None:
            problems.append(f"seq {ev.sequence_number}: actor missing")
        problems += [f"seq {ev.sequence_number}: {p}"
                     for p in _role_and_action_problems(ev)]
        # supersession (v2, SIGNED): the reference must exist, PRECEDE this event, and be
        # about the SAME subject. A repointed FK also changes the recomputed content hash
        # above, so this is defence in depth with specific diagnostics.
        if ev.supersedes_event_id is not None:
            ref = by_pk.get(ev.supersedes_event_id)
            if ref is None:
                problems.append(
                    f"seq {ev.sequence_number}: supersedes a missing event")
            elif ref.pk == ev.pk:
                problems.append(f"seq {ev.sequence_number}: event supersedes itself")
            else:
                if ref.sequence_number >= ev.sequence_number:
                    problems.append(
                        f"seq {ev.sequence_number}: forward supersession reference")
                if (ref.subject_type, ref.subject_id) != (ev.subject_type, ev.subject_id):
                    problems.append(
                        f"seq {ev.sequence_number}: supersedes an incompatible subject")
                if not _supersession_action_compatible(ev.action, ref.action):
                    problems.append(
                        f"seq {ev.sequence_number}: supersedes an incompatible action")
        prev_hash = ev.content_hash
        expected_seq += 1

    terminal = events[-1]
    if head.terminal_sequence_number != terminal.sequence_number:
        problems.append("head terminal sequence != last event")
    if head.terminal_event_hash != terminal.content_hash:
        problems.append("head terminal hash != last event content hash")
    if key_epochs.is_lost_key_id(head.signing_key_id):
        # the head re-signs itself under the ACTIVE key at the next append;
        # until then its unsigned terminal-hash/sequence reconciliation above
        # still holds and the signature is a classified legacy notice
        legacy.append("head: " + key_epochs.legacy_problem(
            head.signing_key_id, what="chain head"))
    else:
        try:
            if not signing.verify(_head_doc(head), head.head_signature,
                                  head.signing_key_id):
                problems.append("head signature does not verify")
        except signing.SigningConfigurationError as e:
            problems.append(f"head key problem — {e}")

    return VerificationResult(not problems, count, tuple(problems),
                              tuple(legacy))


def verify_event(event: DecisionEvent) -> tuple[bool, tuple[str, ...]]:
    """Single-event verification — the 'verified-event interface' every higher-level
    reader (e.g. dual control) uses instead of trusting a row because it exists. Read-only.

    Checks the SIGNED envelope only: recomputed content hash, HMAC (pinned HMAC-SHA-256 via
    the event's recorded key id), signature algorithm, and a known role/action. It does NOT
    walk linkage (that is `verify_chain`); a caller that needs full-chain assurance runs
    both.
    """
    problems: list[str] = []
    if event.signature_algorithm != SIGNATURE_ALGORITHM:
        problems.append(f"invalid signature algorithm {event.signature_algorithm!r}")
    try:
        doc = _rebuild_event_doc(event)
        if canonical.content_hash(doc) != event.content_hash:
            problems.append("content hash does not verify")
        if key_epochs.is_lost_key_id(event.signing_key_id):
            # fail-closed WITH classification: the event can never authorize
            # anything again, but the refusal names the lost-key incident
            # instead of implying tampering
            problems.append(key_epochs.legacy_problem(event.signing_key_id))
        elif not signing.verify(doc, event.hmac_signature,
                                event.signing_key_id):
            problems.append("HMAC does not verify")
    except signing.SigningConfigurationError as e:
        problems.append(f"key problem — {e}")
    except canonical.CanonicalizationError as e:
        problems.append(f"not canonically serialisable — {e}")
    if event.actor_id is None:
        problems.append("actor missing")
    problems += _role_and_action_problems(event)
    return (not problems, tuple(problems))


def event_integrity_state(event: DecisionEvent) -> str:
    """Single-event integrity projection (read-only):

    * ``VERIFIED`` — envelope recomputes and the HMAC verifies under a live key;
    * ``UNVERIFIABLE_DUE_TO_LOST_KEY_MATERIAL`` — every check that can still
      run passes, but the signing key is formally lost (never called VALID,
      never called TAMPERED, never authorizes);
    * ``INVALID`` — any other failure (incl. tamper evidence on a legacy event).
    """
    ok, problems = verify_event(event)
    if ok:
        return "VERIFIED"
    if all(key_epochs.is_legacy_problem(p) for p in problems):
        return key_epochs.LEGACY_STATE
    return "INVALID"


def _role_and_action_problems(event) -> list[str]:
    """Role/action vocabulary check, shared by whole-chain and single-event verification.

    The bootstrap ceremony action and its `BOOTSTRAP_OPERATOR` sentinel are recognised
    ONLY together: the sentinel on any other action, or the ceremony action with any
    ordinary role, is a problem. Ordinary events are unaffected — they must still name a
    real role and a real policy action, exactly as before.
    """
    is_bootstrap_action = bootstrap_registry.is_bootstrap_action(event.action)
    is_sentinel = event.role_used == bootstrap_registry.BOOTSTRAP_OPERATOR
    if is_bootstrap_action or is_sentinel:
        problems = []
        if not is_bootstrap_action:
            problems.append("BOOTSTRAP_OPERATOR sentinel used on a non-bootstrap action")
        if not is_sentinel:
            problems.append("bootstrap action does not use the BOOTSTRAP_OPERATOR "
                            "sentinel")
        return problems
    problems = []
    if event.role_used not in authz.ROLES:
        problems.append("unknown role_used")
    if event.action not in authz.ACTIONS:
        problems.append("unknown action")
    return problems
