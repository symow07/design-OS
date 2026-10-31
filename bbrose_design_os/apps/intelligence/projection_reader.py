"""Read-only access to the atomically published human-assertion projection."""
from __future__ import annotations

import dataclasses

from apps.accounts import authz_policy as authz
from apps.accounts.decision_chain import verify_chain
from apps.accounts.models import DecisionChainHead, DecisionEvent

from .models import (
    HumanAssertionProjection, IntelligenceProjectionGeneration,
    ProjectionPublicationState,
)
from .projection import (
    EVIDENCE_DOMAIN, PROJECTOR_IDENTIFIER, PROJECTOR_VERSION,
    PROJECTION_SCHEMA_VERSION, SUPPORTED_ACTIONS,
)


@dataclasses.dataclass(frozen=True)
class PublishedAssertionResult:
    state: str
    reason: str
    generation_id: str | None
    chain_head_hash: str
    terminal_sequence: int
    published_at: object | None
    current_by_domain: dict
    evidence_assessment: dict | None
    history: tuple[dict, ...]
    warning_codes: tuple[str, ...]


def _history_for(item):
    events = list(DecisionEvent.objects.filter(
        subject_type="CorpusItem", subject_id=str(item.pk),
        action__in=SUPPORTED_ACTIONS,
    ).order_by("sequence_number"))
    superseded_pks = {
        event.supersedes_event_id for event in events
        if event.supersedes_event_id is not None
    }
    history = []
    for event in events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        if event.action in {
                authz.RECORD_INTELLIGENCE_CLASSIFICATION,
                authz.CORRECT_INTELLIGENCE_CLASSIFICATION}:
            domain = payload.get("classification_domain", "")
            label = payload.get("asserted_label", "")
        elif event.action in {
                authz.RECORD_HUMAN_SEMANTIC_METADATA,
                authz.CORRECT_HUMAN_SEMANTIC_METADATA}:
            # DIP-1C-5B: a descriptor bundle has no single label; the history line names the
            # domain and leaves the label empty rather than borrowing an evidence assessment.
            domain = payload.get("assertion_domain", "")
            label = ""
        else:
            domain = EVIDENCE_DOMAIN
            label = payload.get("assessment", "")
        history.append({
            "event_id": event.event_id,
            "sequence_number": event.sequence_number,
            "action": event.action,
            "domain": domain,
            "label": label,
            "role_used": event.role_used,
            "created_at": event.created_at,
            "effective": False,
            "superseded": event.pk in superseded_pks,
        })
    return history


def _result(state, reason, history, *, state_row=None, warnings=()):
    return PublishedAssertionResult(
        state=state, reason=reason,
        generation_id=(str(state_row.current_generation_id) if state_row else None),
        chain_head_hash=(state_row.published_chain_head_hash if state_row else ""),
        terminal_sequence=(state_row.published_terminal_sequence if state_row else 0),
        published_at=(state_row.published_at if state_row else None),
        current_by_domain={}, evidence_assessment=None,
        history=tuple(history), warning_codes=tuple(sorted(set(warnings))),
    )


def _publication_pointer_valid(publication):
    generation = publication.current_generation
    return (
        generation.status == IntelligenceProjectionGeneration.Status.PUBLISHED
        and generation.projector_identifier == PROJECTOR_IDENTIFIER
        and generation.projector_version == PROJECTOR_VERSION
        and generation.projection_schema_version == PROJECTION_SCHEMA_VERSION
        and publication.projector_identifier == generation.projector_identifier
        and publication.projector_version == generation.projector_version
        and publication.projection_schema_version == generation.projection_schema_version
        and publication.published_chain_head_hash == generation.source_chain_head_hash
        and publication.published_terminal_sequence == generation.source_terminal_sequence
    )


def published_projection_statuses(items):
    """Resolve list-page statuses with one chain verification and bounded row query."""
    item_ids = [item.pk for item in items]
    if not item_ids:
        return {}
    chain = verify_chain()
    if not chain.ok:
        return {item_id: "INVALID" for item_id in item_ids}
    publication = ProjectionPublicationState.objects.select_related(
        "current_generation").filter(pk=1).first()
    if publication is None:
        return {item_id: "NOT_BUILT" for item_id in item_ids}
    if not _publication_pointer_valid(publication):
        return {item_id: "INVALID" for item_id in item_ids}
    head = DecisionChainHead.objects.get(pk=1)
    if (publication.published_chain_head_hash != (head.terminal_event_hash or "")
            or publication.published_terminal_sequence
            != head.terminal_sequence_number):
        return {item_id: "STALE" for item_id in item_ids}
    statuses = {item_id: "CURRENT" for item_id in item_ids}
    rows = HumanAssertionProjection.objects.filter(
        projection_generation=publication.current_generation,
        corpus_item_id__in=item_ids,
        effective_state__in=(
            HumanAssertionProjection.EffectiveState.REVIEW_REQUIRED,
            HumanAssertionProjection.EffectiveState.INVALID,
        ),
    ).values_list("corpus_item_id", "effective_state")
    for item_id, effective_state in rows:
        if effective_state == HumanAssertionProjection.EffectiveState.INVALID:
            statuses[item_id] = "INVALID"
        elif statuses[item_id] != "INVALID":
            statuses[item_id] = "REVIEW_REQUIRED"
    return statuses


def read_published_assertions(item):
    """Return current projection state only when chain and pointer are fully valid.

    This function is deliberately write-free. Directly created rows have no authority:
    only rows reached through the verified publication singleton can be returned current.
    """
    history = _history_for(item)
    chain = verify_chain()
    if not chain.ok:
        return _result("INVALID", "DECISION_CHAIN_INVALID", history)

    publication = ProjectionPublicationState.objects.select_related(
        "current_generation").filter(pk=1).first()
    if publication is None:
        return _result("NOT_BUILT", "NO_PUBLISHED_GENERATION", history)
    generation = publication.current_generation
    if not _publication_pointer_valid(publication):
        return _result(
            "INVALID", "PUBLICATION_POINTER_INVALID", history,
            state_row=publication)

    head = DecisionChainHead.objects.get(pk=1)
    current_hash = head.terminal_event_hash or ""
    if (publication.published_chain_head_hash != current_hash
            or publication.published_terminal_sequence
            != head.terminal_sequence_number):
        return _result(
            "STALE", "CHAIN_ADVANCED_SINCE_PUBLICATION", history,
            state_row=publication)

    rows = list(HumanAssertionProjection.objects.select_related(
        "source_decision_event").filter(
            projection_generation=generation, corpus_item=item,
        ).order_by("assertion_domain"))
    warnings = sorted({code for row in rows for code in row.warning_codes})
    if any(row.effective_state == HumanAssertionProjection.EffectiveState.INVALID
           for row in rows):
        return _result(
            "INVALID", "PROJECTED_ASSERTION_INVALID", history,
            state_row=publication, warnings=warnings)
    if any(row.effective_state == HumanAssertionProjection.EffectiveState.REVIEW_REQUIRED
           for row in rows):
        return _result(
            "REVIEW_REQUIRED", "ACTIVE_ASSERTION_CONFLICT", history,
            state_row=publication, warnings=warnings)

    current_by_domain = {}
    evidence_assessment = None
    effective_event_ids = set()
    for row in rows:
        event = row.source_decision_event
        projected = {
            "domain": row.assertion_domain,
            "state": row.effective_state,
            "label": row.asserted_label,
            "normalized_value": row.normalized_value,
            "explanation": row.explanation_summary,
            "event_id": event.event_id if event else "",
            "sequence_number": row.source_sequence_number,
            "policy_id": row.source_policy_id,
            "policy_version": row.source_policy_version,
            "reviewer_id": row.source_reviewer_id,
            "role_used": row.source_role,
            "effective_from": row.effective_from,
            "warning_codes": tuple(row.warning_codes),
        }
        if event:
            effective_event_ids.add(event.event_id)
        if row.assertion_domain == EVIDENCE_DOMAIN:
            evidence_assessment = projected
        else:
            current_by_domain[row.assertion_domain] = projected
    for event in history:
        event["effective"] = event["event_id"] in effective_event_ids

    return PublishedAssertionResult(
        state="CURRENT", reason="PUBLISHED_CHAIN_CHECKPOINT_MATCHES",
        generation_id=str(generation.pk),
        chain_head_hash=publication.published_chain_head_hash,
        terminal_sequence=publication.published_terminal_sequence,
        published_at=publication.published_at,
        current_by_domain=current_by_domain,
        evidence_assessment=evidence_assessment,
        history=tuple(history), warning_codes=tuple(warnings),
    )
