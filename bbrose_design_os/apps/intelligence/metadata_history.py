"""Effective human-semantic-metadata resolution from verified signed history —
DIP-1C-5C-CORR-3.

The correction form used to be gated on the *projected* current bundle. When the projection
was stale, `current_by_domain` was empty, the template fell back to the record form, and a
reviewer could not correct a signed event they knew to be wrong — precisely when they most
needed to. Worse, submitting that fallback form would have appended a second independent
record event and produced two active bundles.

The signed DecisionEvent chain, not the read projection, is the authority on whether a prior
metadata event exists. This module answers that question directly.

It is **read-only** and it decides nothing by convenience: not by primary key, not by
`created_at`, not by highest sequence number. It applies the *signed* supersession
relationships and refuses to guess — ambiguity resolves to `REVIEW_REQUIRED`, never to a
best-effort pick.
"""
from __future__ import annotations

import dataclasses

from apps.accounts.decision_chain import verify_chain, verify_event
from apps.accounts.security import key_epochs
from apps.accounts.models import DecisionEvent

from apps.accounts import authz_policy as authz

from .human_semantic_metadata import (
    METADATA_ASSERTION_DOMAIN, METADATA_SCHEMA, RESOLUTION_SCHEMA,
)
from .projection import METADATA_ACTIONS
from .review_services import SUBJECT_TYPE

# --- states -----------------------------------------------------------------------
EFFECTIVE = "EFFECTIVE"
NONE = "NONE"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
INVALID = "INVALID"

CORRECTION_ACTION_REQUIRED = "EXISTING_METADATA_EVENT_REQUIRES_CORRECTION"


@dataclasses.dataclass(frozen=True)
class EffectiveAssertion:
    state: str
    reason: str
    event: object = None
    history: tuple = ()
    superseded_event_ids: tuple = ()
    #: every currently active (unsuperseded, unresolved) metadata event, in sequence order.
    #: A conflict resolution must name exactly this set, so it is reported rather than
    #: recomputed by the caller.
    active_events: tuple = ()

    @property
    def active_event_ids(self) -> tuple:
        return tuple(event.event_id for event in self.active_events)

    @property
    def has_effective(self) -> bool:
        return self.state == EFFECTIVE and self.event is not None


def _metadata_events(item):
    """Signed metadata events for THIS canonical item only.

    Filtered on the event's own signed subject, so an event about another item cannot
    influence this item's history even if a payload claimed otherwise.
    """
    actions = set(METADATA_ACTIONS) | {authz.RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT}
    events = list(DecisionEvent.objects.select_related("actor").filter(
        subject_type=SUBJECT_TYPE, subject_id=str(item.pk),
        action__in=actions).order_by("sequence_number"))
    kept = []
    for event in events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        if payload.get("corpus_item_id") != str(item.pk):
            continue                      # payload must agree with the signed subject
        if event.action == authz.RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT:
            if payload.get("resolution_schema") != RESOLUTION_SCHEMA:
                continue
            if payload.get("metadata_domain") != METADATA_ASSERTION_DOMAIN:
                continue
            if payload.get("metadata_schema") != METADATA_SCHEMA:
                continue
        else:
            if payload.get("assertion_schema") != METADATA_SCHEMA:
                continue                  # unsupported schema is not reinterpreted
            if payload.get("assertion_domain") != METADATA_ASSERTION_DOMAIN:
                continue
        kept.append(event)
    return kept


def resolve_effective_assertion_from_verified_history(item) -> EffectiveAssertion:
    """The one effective metadata event for `item`, or an honest refusal.

    Chain verification comes first: on an invalid chain nothing here is trustworthy, so no
    mutation may be offered from it.
    """
    chain = verify_chain()
    if not chain.ok:
        return EffectiveAssertion(INVALID, "DECISION_CHAIN_INVALID")

    events = _metadata_events(item)
    if not events:
        return EffectiveAssertion(NONE, "NO_METADATA_EVENT")

    by_pk = {event.pk: event for event in events}
    by_event_id = {event.event_id: event for event in events}
    superseded = set()
    legacy_pks = set()
    for event in events:
        ok, problems = verify_event(event)
        if not ok:
            if problems and all(key_epochs.is_legacy_problem(p)
                                for p in problems):
                # KEY EPOCH RESET: signed under a formally lost key — the
                # assertion carries no authority of its own. Judgement is
                # deferred: a verified epoch-2 replacement that supersedes it
                # clears it; a legacy event nothing supersedes suspends the
                # item until a human reaffirms (checked after the loop).
                legacy_pks.add(event.pk)
                continue
            return EffectiveAssertion(INVALID, "EVENT_SIGNATURE_INVALID")
        if event.action == authz.RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT:
            problem = _apply_resolution(event, by_event_id, superseded)
            if problem:
                return EffectiveAssertion(REVIEW_REQUIRED, problem)
            continue
        target = event.supersedes_event_id
        if target is None:
            continue
        prior = by_pk.get(target)
        if prior is None:
            # supersedes something outside this item's metadata history
            return EffectiveAssertion(REVIEW_REQUIRED, "CROSS_ITEM_OR_UNKNOWN_SUPERSESSION")
        if prior.sequence_number >= event.sequence_number:
            return EffectiveAssertion(REVIEW_REQUIRED, "FORWARD_SUPERSESSION_REFERENCE")
        if target in superseded:
            # two corrections superseding the same event: the history is a fork
            return EffectiveAssertion(REVIEW_REQUIRED, "CONFLICTING_SUPERSESSION")
        superseded.add(target)

    if legacy_pks - superseded:
        # at least one lost-epoch assertion has no verified replacement —
        # suspended, reviewable, never silently trusted or called tampered
        return EffectiveAssertion(
            REVIEW_REQUIRED,
            key_epochs.CORPUS_AUTHORIZATION_REAFFIRMATION_REQUIRED)
    active = [event for event in events if event.pk not in superseded]
    history = tuple(events)
    superseded_ids = tuple(
        event.event_id for event in events if event.pk in superseded)
    if len(active) > 1:
        return EffectiveAssertion(
            REVIEW_REQUIRED, "MULTIPLE_ACTIVE_METADATA_EVENTS",
            history=history, superseded_event_ids=superseded_ids,
            active_events=tuple(active))
    if not active:
        return EffectiveAssertion(
            REVIEW_REQUIRED, "NO_ACTIVE_METADATA_EVENT",
            history=history, superseded_event_ids=superseded_ids)
    return EffectiveAssertion(
        EFFECTIVE, "RESOLVED_FROM_VERIFIED_EVENT_HISTORY", event=active[0],
        history=history, superseded_event_ids=superseded_ids,
        active_events=tuple(active))


def _apply_resolution(event, by_event_id, superseded) -> str:
    """Invalidate every event a resolution names. Only this action/schema may invalidate a
    SET; ordinary events keep single-parent supersession.

    Returns a problem code, or "" when the resolution is well formed.
    """
    payload = event.payload if isinstance(event.payload, dict) else {}
    resolved = payload.get("resolved_event_ids")
    if not isinstance(resolved, list) or not resolved:
        return "RESOLUTION_NAMES_NO_EVENTS"
    if len(set(resolved)) != len(resolved):
        return "RESOLUTION_NAMES_DUPLICATE_EVENTS"
    for event_id in resolved:
        target = by_event_id.get(event_id)
        if target is None:
            return "RESOLUTION_NAMES_UNKNOWN_OR_CROSS_ITEM_EVENT"
        if target.sequence_number >= event.sequence_number:
            return "RESOLUTION_FORWARD_REFERENCE"
        if target.pk in superseded:
            return "RESOLUTION_TARGET_ALREADY_RESOLVED"
        if target.pk == event.pk:
            return "RESOLUTION_CYCLE"
        superseded.add(target.pk)
    return ""
