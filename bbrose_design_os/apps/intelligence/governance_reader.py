"""Write-free access to the atomically published governance projection."""
from __future__ import annotations

import dataclasses

from apps.accounts.decision_chain import verify_chain
from apps.accounts.models import DecisionChainHead

from .governance import governance_event_history
from .governance_projection import (
    PROJECTOR_IDENTIFIER,
    PROJECTOR_VERSION,
    PROJECTION_SCHEMA_VERSION,
)
from .models import (
    GovernanceDecisionProjection,
    GovernanceProjectionGeneration,
    GovernanceProjectionPublicationState,
)


@dataclasses.dataclass(frozen=True)
class PublishedGovernanceResult:
    state: str
    reason: str
    generation_id: str | None
    chain_head_hash: str
    terminal_sequence: int
    published_at: object | None
    projections: tuple[dict, ...]
    attestations: tuple
    final_decisions: tuple
    revocations: tuple
    warning_codes: tuple[str, ...]


def _publication_pointer_valid(publication):
    generation = publication.current_generation
    return (
        generation.status == GovernanceProjectionGeneration.Status.PUBLISHED
        and generation.projector_identifier == PROJECTOR_IDENTIFIER
        and generation.projector_version == PROJECTOR_VERSION
        and generation.projection_schema_version == PROJECTION_SCHEMA_VERSION
        and publication.projector_identifier == generation.projector_identifier
        and publication.projector_version == generation.projector_version
        and publication.projection_schema_version == generation.projection_schema_version
        and publication.published_chain_head_hash == generation.source_chain_head_hash
        and publication.published_terminal_sequence == generation.source_terminal_sequence
    )


def _result(state, reason, history, *, publication=None, rows=(), warnings=()):
    return PublishedGovernanceResult(
        state=state, reason=reason,
        generation_id=(str(publication.current_generation_id)
                       if publication else None),
        chain_head_hash=(publication.published_chain_head_hash if publication else ""),
        terminal_sequence=(publication.published_terminal_sequence
                           if publication else 0),
        published_at=(publication.published_at if publication else None),
        projections=tuple(rows), attestations=history["attestations"],
        final_decisions=history["finals"], revocations=history["revocations"],
        warning_codes=tuple(sorted(set(warnings))),
    )


def read_published_governance(item):
    """Return governance only through a verified, current publication pointer."""
    history = governance_event_history(item)
    chain = verify_chain()
    if not chain.ok:
        return _result("INVALID", "DECISION_CHAIN_INVALID", history)
    publication = GovernanceProjectionPublicationState.objects.select_related(
        "current_generation").filter(pk=1).first()
    if publication is None:
        return _result("NOT_BUILT", "NO_PUBLISHED_GOVERNANCE_GENERATION", history)
    if not _publication_pointer_valid(publication):
        return _result(
            "INVALID", "GOVERNANCE_PUBLICATION_POINTER_INVALID", history,
            publication=publication)
    head = DecisionChainHead.objects.get(pk=1)
    if (publication.published_chain_head_hash != (head.terminal_event_hash or "")
            or publication.published_terminal_sequence
            != head.terminal_sequence_number):
        return _result(
            "STALE", "CHAIN_ADVANCED_SINCE_GOVERNANCE_PUBLICATION", history,
            publication=publication)
    model_rows = list(GovernanceDecisionProjection.objects.select_related(
        "source_final_decision_event").filter(
            projection_generation=publication.current_generation,
            selected_corpus_item=item,
        ).order_by("governance_type", "governance_scope_hash",
                   "source_sequence_number"))
    rows = tuple({
        "governance_type": row.governance_type,
        "normalized_scope": row.normalized_scope,
        "governance_scope_hash": row.governance_scope_hash,
        "effective_state": row.effective_state,
        "event_id": row.source_final_decision_event.event_id,
        "sequence_number": row.source_sequence_number,
        "attestation_event_ids": tuple(row.attestation_event_ids),
        "policy_id": row.source_policy_id,
        "policy_version": row.source_policy_version,
        "effective_from": row.effective_from,
        "revoked_at": row.revoked_at,
        "warning_codes": tuple(row.warning_codes),
        "metadata": row.projection_metadata,
    } for row in model_rows)
    warnings = tuple(code for row in model_rows for code in row.warning_codes)
    states = {row.effective_state for row in model_rows}
    if GovernanceDecisionProjection.EffectiveState.INVALID in states:
        state, reason = "INVALID", "PROJECTED_GOVERNANCE_INVALID"
    elif GovernanceDecisionProjection.EffectiveState.EVIDENCE_INTEGRITY_BLOCKED in states:
        state, reason = (
            "EVIDENCE_INTEGRITY_BLOCKED", "PROJECTED_EVIDENCE_INTEGRITY_BLOCKED")
    elif GovernanceDecisionProjection.EffectiveState.REVIEW_REQUIRED in states:
        state, reason = "REVIEW_REQUIRED", "PROJECTED_GOVERNANCE_REVIEW_REQUIRED"
    else:
        state, reason = "CURRENT", "PUBLISHED_CHAIN_CHECKPOINT_MATCHES"
    return _result(
        state, reason, history, publication=publication, rows=rows, warnings=warnings)


__all__ = ["PublishedGovernanceResult", "read_published_governance"]
