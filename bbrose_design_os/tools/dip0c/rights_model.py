"""Rights model — four separate layers and one central invariant (DIP-0C3b1).

This slice defines a MODEL, not an audit. Its correctness lives in the state
machine and the guards.

FOUR LAYERS, NEVER COLLAPSED. They live in four blocks whose key sets are
**disjoint**, so no layer can silently write into another:

    1. business_assertion  — "what the business BELIEVES"      (a human says it)
    2. machine_inference   — "what the evidence SUGGESTS"       (machine, uncertain)
    3. human_confirmation  — "what a reviewer DECIDED"          (HUMAN ONLY)
    4. permissions         — "what the system MAY DO"           (HUMAN ONLY, per flag)

A user asserting *"this is our logo"* records layer 1 and **nothing else**. It does
not confirm ownership, approve a licence, approve a master, or grant a single
permission. `LOGO6.ai` is why that separation is structural rather than a matter of
care: the business may sincerely believe it owns that logo, and the file's own live
text reads "global logistics services".

THE CORE INVARIANT:

    *** Machine code may only ever REDUCE certainty or permission. ***

It may quarantine, dispute, expire, revoke, reduce confidence, demand review. It may
never confirm, approve, grant, restore or activate. One rule, enforced centrally by
`machine_transition()` and `machine_permission_update()` — not re-implemented ad hoc
at each call site.
"""
from __future__ import annotations

from tools.dip0.provenance import now_iso

from . import config as C

PARSER = f"{C.TOOL_NAME}.rights_model/{C.TOOL_VERSION}"
MODEL_VERSION = "rights/1.0"

ACTOR_MACHINE = "machine"
ACTOR_HUMAN = "human"

AXIS_OWNERSHIP = "ownership"
AXIS_LICENSE = "license"


class MachineMayNotIncrease(RuntimeError):
    """Raised when machine code tries to INCREASE certainty or permission."""


class IllegalTransition(RuntimeError):
    """Raised on a state transition that is not in the transition matrix."""


# --- certainty ranks: what "reduce" precisely MEANS --------------------------
# A machine transition may only move to a rank <= the current rank. This is what
# makes "may reduce, never increase" a checkable property rather than a slogan.
OWNERSHIP_RANK = {
    C.OWN_QUARANTINED: 0,
    C.OWN_DISPUTED: 0,
    C.OWN_UNKNOWN: 1,
    C.OWN_BBROSE_UNCONFIRMED: 2,
    C.OWN_THIRD_PARTY_UNCONFIRMED: 2,
    C.OWN_BUSINESS_ASSERTED_BBROSE: 2,     # a belief is not more certain than a guess
    C.OWN_BBROSE_CONFIRMED: 3,
    C.OWN_THIRD_PARTY_CONFIRMED: 3,
    C.OWN_LICENSED_LIMITED: 3,
    C.OWN_JOINT_OR_CONTRACTED: 3,
}
LICENSE_RANK = {
    C.LIC_QUARANTINED: 0,
    C.LIC_EXPIRED_OR_REVIEW: 0,
    C.LIC_NO_EVIDENCE: 1,
    C.LIC_UNVERIFIED: 1,
    C.LIC_COMMERCIAL_UNKNOWN: 1,
    C.LIC_INTERNAL_ONLY: 2,
    C.LIC_ATTRIBUTION_REQUIRED: 2,
    C.LIC_MODIFICATION_RESTRICTED: 2,
    C.LIC_EMBEDDING_RESTRICTED: 2,
    C.LIC_REDISTRIBUTION_RESTRICTED: 2,
    C.LIC_APPROVED: 3,
}
RANK = {AXIS_OWNERSHIP: OWNERSHIP_RANK, AXIS_LICENSE: LICENSE_RANK}
STATES = {AXIS_OWNERSHIP: C.OWNERSHIP_STATES, AXIS_LICENSE: C.LICENSE_STATES}
MACHINE_ALLOWED = {AXIS_OWNERSHIP: C.MACHINE_ALLOWED_OWNERSHIP,
                   AXIS_LICENSE: C.MACHINE_ALLOWED_LICENSE}
HUMAN_ONLY = {AXIS_OWNERSHIP: C.HUMAN_ONLY_OWNERSHIP,
              AXIS_LICENSE: C.HUMAN_ONLY_LICENSE}


# --- THE EXPLICIT TRANSITION MATRIX — the authoritative policy ---------------
#
# Rank is an ADDITIONAL invariant, never the authorisation mechanism. Uncertain
# states are not a true linear hierarchy: BBROSE_OWNED_UNCONFIRMED and
# THIRD_PARTY_UNCONFIRMED share a rank while being *materially different
# hypotheses*. A transition must therefore appear in this allowlist to be legal —
# nothing becomes legal merely because its rank is equal or lower.
#
# LATERAL transitions (equal rank = a change of hypothesis, not of certainty) are
# listed explicitly and flagged, and must record a reason and the previous state.

MACHINE_TRANSITIONS = {
    AXIS_OWNERSHIP: {
        # retract toward ignorance
        (C.OWN_BBROSE_UNCONFIRMED, C.OWN_UNKNOWN),
        (C.OWN_THIRD_PARTY_UNCONFIRMED, C.OWN_UNKNOWN),
        # raise a conflict
        (C.OWN_UNKNOWN, C.OWN_DISPUTED),
        (C.OWN_BBROSE_UNCONFIRMED, C.OWN_DISPUTED),
        (C.OWN_THIRD_PARTY_UNCONFIRMED, C.OWN_DISPUTED),
        # quarantine
        (C.OWN_UNKNOWN, C.OWN_QUARANTINED),
        (C.OWN_BBROSE_UNCONFIRMED, C.OWN_QUARANTINED),
        (C.OWN_THIRD_PARTY_UNCONFIRMED, C.OWN_QUARANTINED),
        (C.OWN_DISPUTED, C.OWN_QUARANTINED),
        # LATERAL (equal rank, different hypothesis) — explicitly permitted
        (C.OWN_BBROSE_UNCONFIRMED, C.OWN_THIRD_PARTY_UNCONFIRMED),
        (C.OWN_THIRD_PARTY_UNCONFIRMED, C.OWN_BBROSE_UNCONFIRMED),
        (C.OWN_QUARANTINED, C.OWN_DISPUTED),
        # machine may REVOKE a human confirmation down to review (never restore it)
        (C.OWN_BBROSE_CONFIRMED, C.OWN_QUARANTINED),
        (C.OWN_THIRD_PARTY_CONFIRMED, C.OWN_QUARANTINED),
        (C.OWN_LICENSED_LIMITED, C.OWN_QUARANTINED),
        (C.OWN_JOINT_OR_CONTRACTED, C.OWN_QUARANTINED),
        (C.OWN_BBROSE_CONFIRMED, C.OWN_DISPUTED),
        (C.OWN_THIRD_PARTY_CONFIRMED, C.OWN_DISPUTED),
    },
    AXIS_LICENSE: {
        # LATERAL among the unverified family — explicitly permitted
        (C.LIC_UNVERIFIED, C.LIC_NO_EVIDENCE),
        (C.LIC_NO_EVIDENCE, C.LIC_UNVERIFIED),
        (C.LIC_UNVERIFIED, C.LIC_COMMERCIAL_UNKNOWN),
        (C.LIC_COMMERCIAL_UNKNOWN, C.LIC_UNVERIFIED),
        (C.LIC_NO_EVIDENCE, C.LIC_COMMERCIAL_UNKNOWN),
        (C.LIC_COMMERCIAL_UNKNOWN, C.LIC_NO_EVIDENCE),
        # expire / quarantine from any machine state
        (C.LIC_UNVERIFIED, C.LIC_EXPIRED_OR_REVIEW),
        (C.LIC_NO_EVIDENCE, C.LIC_EXPIRED_OR_REVIEW),
        (C.LIC_COMMERCIAL_UNKNOWN, C.LIC_EXPIRED_OR_REVIEW),
        (C.LIC_UNVERIFIED, C.LIC_QUARANTINED),
        (C.LIC_NO_EVIDENCE, C.LIC_QUARANTINED),
        (C.LIC_COMMERCIAL_UNKNOWN, C.LIC_QUARANTINED),
        (C.LIC_EXPIRED_OR_REVIEW, C.LIC_QUARANTINED),
        (C.LIC_QUARANTINED, C.LIC_EXPIRED_OR_REVIEW),
        # machine may EXPIRE / revoke a human approval (never restore it)
        (C.LIC_APPROVED, C.LIC_EXPIRED_OR_REVIEW),
        (C.LIC_INTERNAL_ONLY, C.LIC_EXPIRED_OR_REVIEW),
        (C.LIC_ATTRIBUTION_REQUIRED, C.LIC_EXPIRED_OR_REVIEW),
        (C.LIC_MODIFICATION_RESTRICTED, C.LIC_EXPIRED_OR_REVIEW),
        (C.LIC_EMBEDDING_RESTRICTED, C.LIC_EXPIRED_OR_REVIEW),
        (C.LIC_REDISTRIBUTION_RESTRICTED, C.LIC_EXPIRED_OR_REVIEW),
        (C.LIC_APPROVED, C.LIC_QUARANTINED),
    },
}


def _human_transitions(axis: str) -> set:
    """A human may move anywhere in the vocabulary EXCEPT setting a business
    ASSERTION as a confirmed state — a belief is recorded in its own layer."""
    out = set()
    for frm in STATES[axis]:
        for to in STATES[axis]:
            if frm == to or to == C.OWN_BUSINESS_ASSERTED_BBROSE:
                continue
            out.add((frm, to))
    return out


HUMAN_TRANSITIONS = {axis: _human_transitions(axis)
                     for axis in (AXIS_OWNERSHIP, AXIS_LICENSE)}
TRANSITIONS = {ACTOR_MACHINE: MACHINE_TRANSITIONS,
               ACTOR_HUMAN: HUMAN_TRANSITIONS}


def is_lateral(axis: str, frm: str, to: str) -> bool:
    """Equal rank = a change of HYPOTHESIS, not of certainty. Must be explicit,
    and must record a reason and the previous state."""
    return RANK[axis][frm] == RANK[axis][to]


# --- the record: four blocks with DISJOINT keys ------------------------------
def business_assertion(state=None, *, asserted_by=None, asserted_at=None,
                       notes="", source=None) -> dict:
    """Layer 1. What the business BELIEVES. It grants nothing, confirms nothing,
    and — crucially — it SURVIVES contradicting evidence. It may only be withdrawn
    by a human, and even then the withdrawal is recorded rather than erased."""
    return {
        "asserted_state": state,                 # e.g. BUSINESS_ASSERTED_BBROSE
        "asserted_by": asserted_by,
        "asserted_at": asserted_at,
        "assertion_notes": notes,
        "assertion_source": source,
        "withdrawn_at": None,
        "withdrawal_reason": None,
        "is_confirmation": False,
        "grants_permissions": False,
        "note": "a business assertion is a BELIEF. It is not evidence, not a "
                "confirmation, and it grants nothing.",
    }


def machine_inference(axis: str, state: str, *, evidence=None,
                      confidence=0.0) -> dict:
    """Layer 2. What the evidence SUGGESTS. Always an uncertain state."""
    guard = (C.machine_ownership if axis == AXIS_OWNERSHIP else C.machine_license)
    return {
        "machine_state": guard(state),
        "machine_evidence": list(evidence or []),
        "machine_confidence": round(float(confidence), 3),
        "previous_state": None,
        "transition_history": [],
        "machine_inferred_at": now_iso(),
        "parser": PARSER,
    }


def human_confirmation() -> dict:
    """Layer 3. What a reviewer DECIDED. Machine code never writes these keys."""
    return {
        "confirmed_state": None,
        "confirmed_by": None,
        "confirmed_at": None,
        "confirmation_reason": None,
        "confirmation_evidence_refs": [],
    }


def permissions() -> dict:
    """Layer 4. What the system MAY DO. Every flag independent, every one denied.

    NOTHING here is derived from ownership or licence. A fully-owned,
    fully-confirmed asset still has every permission false until a human grants
    each one individually.
    """
    return {
        "retrieval_allowed": False,
        "automatic_use_allowed": False,
        "production_use_allowed": False,
        "modification_allowed": False,
        "embedding_allowed": False,
        "redistribution_allowed": False,
        "public_export_allowed": False,
        "approved_for_bbrose": False,
        "approved_for_other_brands": False,
        "approved_products": [],
        "approved_markets": [],
        "attribution_required": None,
        "review_expiry": None,
    }


PERMISSION_FLAGS = tuple(k for k, v in permissions().items() if v is False)
PERMISSION_LISTS = ("approved_products", "approved_markets")


def rights_record(rel_path: str) -> dict:
    """The four layers side by side. Their key sets are DISJOINT by construction."""
    return {
        "relative_path": rel_path,
        "model_version": MODEL_VERSION,
        "business_assertion": business_assertion(),
        "machine_inference": {
            AXIS_OWNERSHIP: machine_inference(AXIS_OWNERSHIP, C.OWN_UNKNOWN),
            AXIS_LICENSE: machine_inference(AXIS_LICENSE, C.LIC_UNVERIFIED),
        },
        "human_confirmation": {
            AXIS_OWNERSHIP: human_confirmation(),
            AXIS_LICENSE: human_confirmation(),
        },
        "permissions": permissions(),
        "canonical_brand_master": None,     # human-only; nominated elsewhere
    }


def effective_state(record: dict, axis: str) -> str:
    """A human confirmation, if one exists; otherwise the machine's guess.
    A business ASSERTION never becomes the effective state — belief is not fact."""
    conf = record["human_confirmation"][axis]["confirmed_state"]
    return conf or record["machine_inference"][axis]["machine_state"]


# --- the transition matrix ---------------------------------------------------
def legal_transitions(axis: str, actor: str) -> list[tuple[str, str]]:
    """Every legal (from, to) pair for an actor on an axis."""
    out = []
    for frm in STATES[axis]:
        for to in STATES[axis]:
            if frm == to:
                continue
            try:
                validate_transition(axis, frm, to, actor)
            except (IllegalTransition, MachineMayNotIncrease,
                    C.HumanOnlyStateViolation):
                continue
            out.append((frm, to))
    return out


def validate_transition(axis: str, frm: str, to: str, actor: str) -> str:
    """The ONE place a transition is judged.

    Authorisation order — and the order matters:

    1. **The explicit transition matrix is authoritative.** A transition is legal
       only if it is in the allowlist. Nothing becomes legal merely because its
       rank is equal or lower: `BBROSE_OWNED_UNCONFIRMED` and
       `THIRD_PARTY_UNCONFIRMED` share a rank while being materially different
       hypotheses, so a lateral move must be listed on purpose.
    2. **Human-only states** are refused to machine actors.
    3. **Rank is an ADDITIONAL invariant** that can only ever *reject* — it never
       authorises anything.
    """
    if axis not in STATES:
        raise IllegalTransition(f"unknown axis: {axis!r}")
    if frm not in STATES[axis] or to not in STATES[axis]:
        raise IllegalTransition(f"unknown {axis} state in {frm!r} -> {to!r}")
    if actor not in TRANSITIONS:
        raise IllegalTransition(f"unknown actor: {actor!r}")

    # (2) human-only states are refused to machines FIRST, so the error says why
    if actor == ACTOR_MACHINE:
        if to in HUMAN_ONLY[axis]:
            raise C.HumanOnlyStateViolation(
                f"{to!r} is HUMAN-ONLY; machine code may never confirm or approve")
        if to == C.OWN_BUSINESS_ASSERTED_BBROSE:
            raise C.HumanOnlyStateViolation(
                "a machine cannot invent a business assertion")

    # (1) THE AUTHORITATIVE CHECK: is it in the explicit allowlist?
    if (frm, to) not in TRANSITIONS[actor][axis]:
        raise IllegalTransition(
            f"{frm!r} -> {to!r} is NOT in the explicit {actor} transition matrix "
            f"for {axis}. The matrix is the authoritative policy; a transition is "
            "never legal merely because its certainty rank is equal or lower.")

    # (3) the ADDITIONAL invariant — it may only reject, never authorise
    if actor == ACTOR_MACHINE and RANK[axis][to] > RANK[axis][frm]:
        raise MachineMayNotIncrease(
            f"machine may NOT increase certainty on {axis}: {frm!r} (rank "
            f"{RANK[axis][frm]}) -> {to!r} (rank {RANK[axis][to]}). Machine code "
            "may only ever reduce.")
    return to


def machine_transition(record: dict, axis: str, to: str, *, reason: str) -> dict:
    """Apply a machine transition — quarantine, dispute, expire, or an explicitly
    allowed LATERAL change of hypothesis.

    Every transition records its **reason** and its **previous state**; a lateral
    move (equal rank = a different hypothesis, not less certainty) is flagged as
    such, because it is the case most likely to be waved through unexamined.

    Writes ONLY into the machine_inference layer — never human_confirmation, never
    permissions.
    """
    if not reason:
        raise ValueError("a machine transition must record a reason")
    frm = effective_state(record, axis)
    validate_transition(axis, frm, to, ACTOR_MACHINE)
    lateral = is_lateral(axis, frm, to)
    blk = record["machine_inference"][axis]
    blk["machine_state"] = to
    blk["previous_state"] = frm                       # never lost
    blk["machine_evidence"] = list(blk["machine_evidence"]) + [
        f"machine transition {frm!r} -> {to!r}"
        f"{' (LATERAL: a different hypothesis, not less certainty)' if lateral else ''}"
        f": {reason}"]
    blk.setdefault("transition_history", []).append({
        "from": frm, "to": to, "lateral": lateral, "reason": reason,
        "actor": ACTOR_MACHINE, "at": now_iso()})
    blk["machine_inferred_at"] = now_iso()
    return record


def machine_permission_update(current: dict, proposed: dict) -> dict:
    """Machine code may only ever REMOVE permission (revoke, expire).

    A single false -> true anywhere, or a widening of an approved list, is refused.
    """
    for flag in PERMISSION_FLAGS:
        if not current.get(flag) and proposed.get(flag):
            raise MachineMayNotIncrease(
                f"machine may NOT grant {flag!r}: false -> true. Granting a "
                "permission is a human decision.")
    for key in PERMISSION_LISTS:
        if not set(proposed.get(key) or []) <= set(current.get(key) or []):
            raise MachineMayNotIncrease(
                f"machine may NOT widen {key!r}; it may only narrow it")
    if proposed.get("attribution_required") is False and \
            current.get("attribution_required") is True:
        raise MachineMayNotIncrease(
            "machine may NOT drop an attribution requirement — that RELAXES a "
            "restriction")
    return proposed


def machine_revoke(record: dict, flag: str, *, reason: str) -> dict:
    """The one permission change a machine MAY make: true -> false."""
    if flag not in PERMISSION_FLAGS:
        raise ValueError(f"unknown permission flag: {flag!r}")
    record["permissions"][flag] = False
    record["permissions"].setdefault("_machine_revocations", [])
    record["permissions"]["_machine_revocations"].append(
        {"flag": flag, "reason": reason, "at": now_iso(), "actor": ACTOR_MACHINE})
    return record


# --- what a HUMAN confirmation requires --------------------------------------
def can_confirm(record: dict, axis: str, to: str,
                reviewed_evidence: list) -> tuple[bool, str]:
    """A confirmation needs BOTH a human decision AND at least one REVIEWED piece
    of evidence. A business assertion is not evidence and can never, on its own,
    reach a confirmed state."""
    if to not in HUMAN_ONLY[axis]:
        return False, f"{to!r} is not a confirmable state on {axis}"
    reviewed = [e for e in (reviewed_evidence or []) if e.get("reviewed_by")]
    if not reviewed:
        assertion = record["business_assertion"]["asserted_state"]
        why = ("the business assertion is a BELIEF, not evidence"
               if assertion else "no evidence has been submitted")
        return False, (f"confirmation requires at least one REVIEWED evidence "
                       f"item; {why}")
    return True, "a reviewer may confirm: reviewed evidence exists"
