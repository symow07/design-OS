"""Operational preflight for the first real human metadata pilot — DIP-1C-5C.

Answers "can a real reviewer record real metadata today, and what is missing?" **without
changing anything**. It configures no signing key, provisions no reviewer, grants no role,
claims no candidate and appends no event. Every field is a read.

It reports the *presence and shape* of the signing configuration, never a key value: whether
keys are configured, how many, the active key id, and whether the active id resolves — enough
to act on, and nothing that could leak a secret into a log, a report or a commit.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts import authz_policy as authz
from apps.accounts.decision_chain import verify_chain
from apps.accounts.models import (
    DecisionChainHead, DecisionEvent, ReviewerProfile, ReviewerRoleAssignment,
)
from apps.accounts.security import signing

from .evidence_integrity import EvidenceIntegrityResolver
from .models import (
    CorpusItem, EvidenceReference, GovernanceDecisionProjection,
    HumanAssertionProjection, OperationalPermissionProjection,
)
from .semantic_metadata_pilot import build_pilot_document, pilot_hash
from .semantic_metadata_scope import scope_hash

PREFLIGHT_SCHEMA = "dip1c_semantic_metadata_preflight/1.0"
METADATA_ROLES = (authz.BUSINESS_OWNER, authz.BRAND_ADMIN, authz.DESIGN_REVIEWER)


def _signing_status():
    """Shape only. No key material is read, returned, logged or hashed."""
    raw = getattr(settings, "DECISION_EVENT_HMAC_KEYS", None)
    active = getattr(settings, "DECISION_EVENT_ACTIVE_KEY_ID", None)
    configured = raw not in (None, "", {})
    status = {
        "keys_configured": bool(configured),
        "active_key_id_configured": bool(active),
        "key_count": len(raw) if isinstance(raw, dict) else (1 if configured else 0),
        "registry_resolves": False,
        "error_code": "",
    }
    if not configured:
        status["error_code"] = "DECISION_EVENT_HMAC_KEYS_NOT_CONFIGURED"
        return status
    try:
        signing.get_registry()
        status["registry_resolves"] = True
    except signing.SigningConfigurationError as exc:
        # the message names the configuration problem, never a value
        status["error_code"] = type(exc).__name__
    return status


def _reviewer_status():
    User = get_user_model()
    now = timezone.now()
    active_users = User.objects.filter(is_active=True)
    profiles = ReviewerProfile.objects.select_related("user")
    grants = ReviewerRoleAssignment.objects.select_related("user").filter(
        revoked_at__isnull=True, expires_at__gt=now)
    enabled_ids = {p.user_id for p in profiles if p.reviewer_enabled}
    eligible = []
    for grant in grants:
        if grant.role not in METADATA_ROLES:
            continue
        if grant.user_id not in enabled_ids or not grant.user.is_active:
            continue
        eligible.append({
            "username": grant.user.get_username(),
            "role": grant.role,
            "expires_at": grant.expires_at.isoformat(),
        })
    return {
        "active_user_count": active_users.count(),
        "usernames": sorted(user.get_username() for user in active_users),
        "reviewer_profile_count": profiles.count(),
        "reviewer_enabled_count": len(enabled_ids),
        "active_role_assignment_count": grants.count(),
        "active_roles": sorted({grant.role for grant in grants}),
        "metadata_eligible_reviewers": sorted(
            eligible, key=lambda row: (row["role"], row["username"])),
        "metadata_eligible_count": len(eligible),
    }


def _chain_status():
    head = DecisionChainHead.objects.filter(pk=1).first()
    result = verify_chain()
    return {
        "event_count": DecisionEvent.objects.count(),
        "head_present": head is not None,
        "terminal_sequence": head.terminal_sequence_number if head else 0,
        "terminal_event_hash": (head.terminal_event_hash or "") if head else "",
        "verified": bool(result.ok),
        "verification_detail": getattr(result, "reason", "") or "",
    }


def _item_readiness(document):
    resolver = EvidenceIntegrityResolver()
    ids = [entry["corpus_item_id"] for entry in document["entries"]]
    items = {str(item.pk): item for item in CorpusItem.objects.filter(pk__in=ids)}
    counts = {}
    for item_id in EvidenceReference.objects.filter(
            corpus_item_id__in=ids, is_test_only=False).values_list(
            "corpus_item_id", flat=True):
        counts[str(item_id)] = counts.get(str(item_id), 0) + 1
    rows = []
    for entry in document["entries"]:
        item = items.get(entry["corpus_item_id"])
        integrity = resolver.evaluate(item) if item is not None else None
        evidence_count = counts.get(entry["corpus_item_id"], 0)
        blocked = bool(integrity and integrity.blocks_evidence_dependent_claims)
        rows.append({
            "corpus_item_id": entry["corpus_item_id"],
            "external_key": entry["external_key"],
            "segment": entry["segment"],
            "review_candidate_id": entry["review_candidate_id"],
            "non_test_evidence_count": evidence_count,
            "evidence_integrity_status": (
                integrity.status if integrity else "ITEM_MISSING"),
            "blocks_evidence_dependent_claims": blocked,
            "ready_for_descriptive_review": bool(
                item is not None and evidence_count > 0 and not blocked),
        })
    return rows


def build_preflight():
    """The whole read-only picture. Writes nothing; returns no secret."""
    document = build_pilot_document()
    readiness = _item_readiness(document)
    return {
        "preflight_schema": PREFLIGHT_SCHEMA,
        "pilot_schema": document["schema_version"],
        "pilot_hash": pilot_hash(document),
        "review_scope_hash": scope_hash(),
        "pilot_segment_counts": document["segment_counts"],
        "pilot_total": document["actual_total"],
        "signing": _signing_status(),
        "reviewers": _reviewer_status(),
        "chain": _chain_status(),
        "items": readiness,
        "items_ready": sum(1 for row in readiness
                           if row["ready_for_descriptive_review"]),
        "authority_counts": {
            "decision_events": DecisionEvent.objects.count(),
            "human_assertion_projections": HumanAssertionProjection.objects.count(),
            "governance_decision_projections":
                GovernanceDecisionProjection.objects.count(),
            "operational_permission_projections":
                OperationalPermissionProjection.objects.count(),
        },
        "blocking_conditions": _blocking(readiness),
    }


def _blocking(readiness):
    blocking = []
    status = _signing_status()
    if not status["registry_resolves"]:
        blocking.append("NO_USABLE_DECISION_EVENT_SIGNING_KEY")
    if _reviewer_status()["metadata_eligible_count"] == 0:
        blocking.append("NO_REVIEWER_AUTHORIZED_FOR_SEMANTIC_METADATA")
    if not _chain_status()["verified"]:
        blocking.append("DECISION_CHAIN_NOT_VERIFIED")
    unready = [row["external_key"] for row in readiness
               if not row["ready_for_descriptive_review"]]
    if unready:
        blocking.append(f"ITEMS_NOT_READY_FOR_DESCRIPTIVE_REVIEW:{len(unready)}")
    return blocking
