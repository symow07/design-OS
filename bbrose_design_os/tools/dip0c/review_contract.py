"""The unified review contract (DIP-0C5).

**A review item is `(review_domain, canonical_subject_id)`. Queue membership never
creates one.**

C4c already caught the failure this prevents: summing fourteen queues gave 6,921
"decisions" for 4,883 files, because one face sits in four queues at once. Queue
membership is a **many-to-many relationship**, and a decision attaches to the **item**,
never to the membership. Remove a membership and the item — and its decision history —
survives.

The same subject in two genuinely different domains is **two** review items, and that is
deliberate: `FONT_FACE:face-abc` asks *"is this typographically what we think it is?"* and
`PROVENANCE_RIGHTS_GROUP:sha+package` asks *"do we know where this copy came from?"*.
Collapsing them would let a technical confirmation imply a rights one.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict

from . import config as C
from . import dispositions as D
from . import review_domains as RD
from . import rights_model as RM

PARSER = f"{C.TOOL_NAME}.review_contract/{C.TOOL_VERSION}"
SCHEMA_VERSION = "review_item/1.0"


def review_item_id(domain: str, subject_id: str,
                   schema_version: str = SCHEMA_VERSION) -> str:
    """Stable identity from (domain, subject, schema version). Deterministic."""
    RD.spec(domain)                                # unknown domain -> raise
    if not subject_id:
        raise ValueError("a review item must name its subject")
    key = f"{domain}|{subject_id}|{schema_version}"
    return "ri-" + hashlib.sha256(key.encode()).hexdigest()[:20]


def human_block() -> dict:
    """Every human field, blank. A machine may never fill one."""
    return {
        "human_decision": None,
        "reviewer": None,
        "reviewed_at": None,
        "review_expiry": None,
        "notes": None,
        "correction_reason": None,
    }


def review_item(*, domain: str, subject_id: str, source_refs: list,
                machine_summary: dict, priority: str, reasons: list,
                evidence_refs: list = None, restrictions: list = None,
                recommended_action: str = None,
                config_version: str = None) -> dict:
    """The shared ENVELOPE. Domain-specific payloads are REFERENCED, never merged in."""
    s = RD.spec(domain)
    return {
        "schema_version": SCHEMA_VERSION,
        "review_item_id": review_item_id(domain, subject_id),
        "review_domain": domain,
        "canonical_subject_id": subject_id,
        "source_references": sorted(source_refs or []),
        "machine_summary": machine_summary,
        # a RECOMMENDATION. The guard raises if a human decision is smuggled in here.
        "recommended_action": D.machine_disposition(recommended_action),
        "review_priority": priority,
        "review_reasons": list(reasons or []),
        "required_reviewer_roles": list(s["required_roles"]),
        "evidence_references": sorted(evidence_refs or []),
        "current_restrictions": list(restrictions or []),
        "batch_review_allowed": s["batch_review_allowed"],
        "dual_control_required": s["dual_control_required"],
        "expiry_applies": s["expiry_applies"],
        "eventual_permissions": list(s["eventual_permissions"]),
        "permissions": {flag: False for flag in RM.PERMISSION_FLAGS},
        "human": human_block(),
        "decision_history": [],          # append-only; a correction ADDS an event
        "configuration_version": config_version,
        "machine_inference_immutable": True,
        "parser": PARSER,
    }


def queue_membership(*, review_item_id_: str, queue_id: str, reason: str,
                     priority: str, blocking: bool, required_role: str,
                     batchable: bool, provenance: str) -> dict:
    """A MEMBERSHIP, not an item. Removing it must not remove the item."""
    return {
        "schema_version": "queue_membership/1.0",
        "review_item_id": review_item_id_,
        "queue_id": queue_id,
        "reason": reason,
        "priority": priority,
        "blocking": blocking,
        "required_role": required_role,
        "batchable": batchable,
        "provenance": provenance,
        "creates_review_item": False,      # it NEVER does
        "carries_decision": False,         # decisions attach to the ITEM
    }


def append_decision(item: dict, *, decision: str, reviewer: str, at: str,
                    reason: str = None, corrects: str = None) -> dict:
    """A human decision, APPENDED. A correction adds a new event against the same
    review-item identity; it never edits or erases the previous one."""
    d = D.human_decision(decision)          # a machine recommendation raises here
    event = {
        "decision": d,
        "reviewer": reviewer,
        "reviewed_at": at,
        "reason": reason,
        "corrects_decision": corrects,
        "grants_permission": D.decision_grants_permission(d),   # always False
    }
    item["decision_history"] = list(item["decision_history"]) + [event]
    item["human"] = {**item["human"], "human_decision": d, "reviewer": reviewer,
                     "reviewed_at": at, "correction_reason": reason if corrects
                     else item["human"]["correction_reason"]}
    return item


def index(items: list, memberships: list) -> dict:
    """The global review index. Counts items ONCE, however many queues they sit in."""
    by_id = {}
    for it in items:
        by_id.setdefault(it["review_item_id"], it)        # same (domain,subject) -> one

    mem_by_item = defaultdict(list)
    for m in memberships:
        mem_by_item[m["review_item_id"]].append(m["queue_id"])

    unique = list(by_id.values())
    multi = [i for i in unique if len(set(mem_by_item.get(i["review_item_id"], []))) > 1]
    blocking = [i for i in unique
                if any(m["blocking"] for m in memberships
                       if m["review_item_id"] == i["review_item_id"])]
    high = [i for i in unique if i["review_priority"] in ("CRITICAL", "HIGH")]
    dual = [i for i in unique if i["dual_control_required"]]
    need_ev = [i for i in unique if not i["evidence_references"]]

    per_domain = defaultdict(int)
    for i in unique:
        per_domain[i["review_domain"]] += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "unique_review_items": len(unique),
        "total_queue_memberships": len(memberships),
        "items_in_multiple_queues": len(multi),
        "unique_blocking_items": len(blocking),
        "unique_high_priority_items": len(high),
        "items_requiring_dual_control": len(dual),
        "items_requiring_evidence_before_review": len(need_ev),
        "batch_groups": len({(i["review_domain"], i["batch_review_allowed"])
                             for i in unique if i["batch_review_allowed"]}),
        "estimated_human_decisions": len(unique),
        "by_domain": dict(sorted(per_domain.items())),
        "queue_memberships_are_not_decisions": (
            "ESTIMATED DECISIONS = UNIQUE REVIEW ITEMS, never the sum of queue "
            "memberships. One font face can sit in four queues; it is still ONE "
            "decision in its domain. C4c's fourteen queues summed to 6,921 'decisions' "
            "for 4,883 files — a number that flattered nobody and misled everybody."),
        "parser": PARSER,
    }
