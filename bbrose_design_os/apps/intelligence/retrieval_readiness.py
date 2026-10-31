"""Retrieval readiness — DIP-1B-6 (`retrieval_readiness/1.0`).

The single place that answers "what may this item actually be used for?" — by **asking the
existing authority, never by re-deriving it**. Every allow/deny below comes from
`evaluate_operational_permission`, the canonical fail-closed permission boundary, which
already verifies the projection, its source DecisionEvent, the event signature, the whole
chain, and the projection's chain-head checkpoint.

Three things this module keeps strictly apart, because collapsing them is how a review tool
quietly becomes a production pipeline:

* **candidate_review_visible** — an authenticated reviewer may look at this item for
  internal review. This is corpus membership plus resolved identity; it is deliberately
  **not** the VISIBLE_IN_REVIEWER_SEARCH permission. (Zero permission projections exist:
  deriving reviewer visibility from a permission would make the corpus unsearchable, and
  would conflate "a human may examine this" with "a machine may use this".)
* **retrieval_allowed** — a currently valid RETRIEVAL permission exists.
* **automatic_use_allowed** — an independently valid AUTOMATIC_USE permission exists.

Being visible for review implies nothing about the other two. Nothing here writes.
"""
from __future__ import annotations

import dataclasses

from django.utils import timezone

from apps.accounts.models import DecisionChainHead

from .evidence_integrity import EvidenceIntegrityResolver
from .governance_reader import read_published_governance
from .models import (
    CorpusItem, DesignAssetProfile, OperationalPermissionProjection as Projection,
)
from .permissions import evaluate_operational_permission

READINESS_SCHEMA = "retrieval_readiness/1.0"

# identity blockers — an item we cannot canonically resolve is withheld, never guessed
IDENTITY_NOT_ACTIVE = "SUBJECT_NOT_ACTIVE"
IDENTITY_NO_STABLE_KEY = "NO_STABLE_EXTERNAL_KEY"
IDENTITY_TEST_ONLY = "TEST_ONLY_RECORD"


@dataclasses.dataclass(frozen=True)
class RetrievalReadiness:
    schema_version: str
    corpus_item_id: str
    # the three separate questions — never one answer
    candidate_review_visible: bool
    retrieval_allowed: bool
    automatic_use_allowed: bool
    export_allowed: bool
    production_allowed: bool
    permission_states: dict
    permission_reason_codes: dict
    projection_ids: dict
    source_decision_event_ids: dict
    projected_chain_head_hash: str | None
    current_chain_head_hash: str | None
    stale_projection: bool
    expired_projection: bool
    identity_blockers: tuple[str, ...]
    evidence_integrity_blockers: tuple[str, ...]
    governance_state: str
    evaluated_at: object

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def _current_chain_head() -> str | None:
    head = DecisionChainHead.objects.filter(pk=1).first()
    return (head.terminal_event_hash or None) if head else None


def _identity_blockers(item) -> tuple[str, ...]:
    """Canonical identity must be resolvable before an item is even reviewable."""
    blockers = []
    if item.lifecycle_state != CorpusItem.Lifecycle.ACTIVE:
        blockers.append(IDENTITY_NOT_ACTIVE)
    if not (item.external_key or "").strip():
        blockers.append(IDENTITY_NO_STABLE_KEY)
    if DesignAssetProfile.objects.filter(corpus_item=item, is_test_only=True).exists():
        blockers.append(IDENTITY_TEST_ONLY)
    return tuple(blockers)


def evaluate_retrieval_readiness(corpus_item, at=None) -> RetrievalReadiness:
    """Structured, read-only readiness for one corpus item. Writes nothing, grants nothing.

    Permission authority is NOT duplicated here: each answer is whatever
    `evaluate_operational_permission` returned.
    """
    at = at or timezone.now()
    item = corpus_item
    results = {
        permission_type: evaluate_operational_permission(item, permission_type, at=at)
        for permission_type in Projection.Permission.values
    }

    projections = {
        p.permission_type: p for p in Projection.objects.filter(corpus_item=item)
    } if getattr(item, "pk", None) else {}
    current_head = _current_chain_head()
    # Stale is reported as its own fact. The permission gate folds a stale checkpoint into
    # UNVERIFIED_PROJECTION_CHECKPOINT (correctly — it denies either way); we read the
    # checkpoint separately so the reason is legible, without becoming a second authority.
    projected_heads = {
        p.projected_chain_head_hash for p in projections.values()
        if p.projected_chain_head_hash
    }
    stale = bool(projected_heads) and any(
        h != current_head for h in projected_heads)
    expired = any(
        p.expires_at is not None and at >= p.expires_at for p in projections.values())

    integrity = EvidenceIntegrityResolver().evaluate(item)
    integrity_blockers = (
        tuple(integrity.reason_codes)
        if integrity.blocks_evidence_dependent_claims else ())
    identity_blockers = _identity_blockers(item)
    governance = read_published_governance(item)

    def allowed(permission_type):
        return results[permission_type].allowed

    return RetrievalReadiness(
        schema_version=READINESS_SCHEMA,
        corpus_item_id=str(item.pk),
        # reviewer visibility is corpus membership + resolvable identity, gated by the
        # caller's reviewer authorization — NOT a permission, and never implying one
        candidate_review_visible=not identity_blockers,
        retrieval_allowed=allowed(Projection.Permission.RETRIEVAL),
        automatic_use_allowed=allowed(Projection.Permission.AUTOMATIC_USE),
        export_allowed=allowed(Projection.Permission.EXPORT),
        production_allowed=allowed(Projection.Permission.PRODUCTION),
        permission_states={k: r.effective_state for k, r in sorted(results.items())},
        permission_reason_codes={k: r.reason_code for k, r in sorted(results.items())},
        projection_ids={k: r.projection_id for k, r in sorted(results.items())},
        source_decision_event_ids={
            k: (str(p.source_decision_event_id)
                if p.source_decision_event_id else None)
            for k, p in sorted(projections.items())},
        projected_chain_head_hash=sorted(projected_heads)[0] if projected_heads else None,
        current_chain_head_hash=current_head,
        stale_projection=stale,
        expired_projection=expired,
        identity_blockers=identity_blockers,
        evidence_integrity_blockers=integrity_blockers,
        governance_state=governance.state,
        evaluated_at=at,
    )
