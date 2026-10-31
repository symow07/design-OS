"""DIP-0C3b1 tests — the rights model.

This slice's correctness IS its guards, so the tests are the specification:
a business assertion grants nothing and confirms nothing; ownership and licence are
independent; ownership confirmation grants no permission; and machine code may only
ever REDUCE certainty or permission — never increase it.
"""
from __future__ import annotations

import copy
import json

import pytest

from tools.dip0c import config as C
from tools.dip0c import rights_model as RM
from tools.dip0c import run_c3b1


# --- 1. a business assertion alone never confirms ownership -----------------
def test_business_assertion_alone_never_confirms_ownership():
    rec = RM.rights_record("LOGO6.ai")
    rec["business_assertion"] = RM.business_assertion(
        C.OWN_BUSINESS_ASSERTED_BBROSE, asserted_by="owner",
        asserted_at="2026-07-11T00:00:00+00:00",
        notes="the business believes this is our logo")
    # the assertion is recorded ...
    assert rec["business_assertion"]["asserted_state"] == \
        C.OWN_BUSINESS_ASSERTED_BBROSE
    # ... and confirms nothing
    assert rec["human_confirmation"]["ownership"]["confirmed_state"] is None
    assert RM.effective_state(rec, RM.AXIS_OWNERSHIP) == C.OWN_UNKNOWN
    ok, why = RM.can_confirm(rec, RM.AXIS_OWNERSHIP, C.OWN_BBROSE_CONFIRMED,
                             reviewed_evidence=[])
    assert ok is False
    assert "BELIEF, not evidence" in why


def test_business_assertion_grants_no_permission():
    rec = RM.rights_record("LOGO6.ai")
    before = copy.deepcopy(rec["permissions"])
    rec["business_assertion"] = RM.business_assertion(
        C.OWN_BUSINESS_ASSERTED_BBROSE, asserted_by="owner")
    assert rec["permissions"] == before
    assert all(rec["permissions"][f] is False for f in RM.PERMISSION_FLAGS)
    assert rec["business_assertion"]["grants_permissions"] is False


def test_confirmation_requires_reviewed_evidence():
    rec = RM.rights_record("logo.pdf")
    unreviewed = [{"type": "contract", "reviewed_by": None}]
    ok, why = RM.can_confirm(rec, RM.AXIS_OWNERSHIP, C.OWN_BBROSE_CONFIRMED,
                             reviewed_evidence=unreviewed)
    assert ok is False and "REVIEWED evidence" in why
    reviewed = [{"type": "contract", "reviewed_by": "legal"}]
    ok, _ = RM.can_confirm(rec, RM.AXIS_OWNERSHIP, C.OWN_BBROSE_CONFIRMED,
                           reviewed_evidence=reviewed)
    assert ok is True


# --- 2. ownership confirmation grants NO permission --------------------------
def test_ownership_confirmation_grants_no_permission():
    """A fully-owned, fully-confirmed asset is still entirely unusable."""
    rec = RM.rights_record("logo.pdf")
    rec["human_confirmation"]["ownership"].update(
        {"confirmed_state": C.OWN_BBROSE_CONFIRMED, "confirmed_by": "owner",
         "confirmed_at": "2026-07-11T00:00:00+00:00",
         "confirmation_reason": "contract on file"})
    assert RM.effective_state(rec, RM.AXIS_OWNERSHIP) == C.OWN_BBROSE_CONFIRMED
    # ... and NOTHING is permitted
    assert all(rec["permissions"][f] is False for f in RM.PERMISSION_FLAGS)
    assert rec["permissions"]["retrieval_allowed"] is False
    assert rec["permissions"]["automatic_use_allowed"] is False
    assert rec["permissions"]["production_use_allowed"] is False


def test_license_approval_grants_no_permission_automatically():
    rec = RM.rights_record("x.ai")
    rec["human_confirmation"]["license"].update(
        {"confirmed_state": C.LIC_APPROVED, "confirmed_by": "legal"})
    assert RM.effective_state(rec, RM.AXIS_LICENSE) == C.LIC_APPROVED
    assert all(rec["permissions"][f] is False for f in RM.PERMISSION_FLAGS)


# --- 3. the two axes are independent ----------------------------------------
def test_ownership_and_license_axes_are_independent():
    rec = RM.rights_record("x.ai")
    rec["human_confirmation"]["ownership"]["confirmed_state"] = \
        C.OWN_BBROSE_CONFIRMED
    # confirming ownership did NOT touch the licence axis
    assert rec["human_confirmation"]["license"]["confirmed_state"] is None
    assert RM.effective_state(rec, RM.AXIS_LICENSE) == C.LIC_UNVERIFIED

    rec2 = RM.rights_record("y.ai")
    rec2["human_confirmation"]["license"]["confirmed_state"] = C.LIC_APPROVED
    # approving a licence did NOT prove ownership
    assert rec2["human_confirmation"]["ownership"]["confirmed_state"] is None
    assert RM.effective_state(rec2, RM.AXIS_OWNERSHIP) == C.OWN_UNKNOWN


# --- 4. every permission defaults false --------------------------------------
def test_every_permission_defaults_false_or_empty():
    p = RM.permissions()
    for flag in ("retrieval_allowed", "automatic_use_allowed",
                 "production_use_allowed", "modification_allowed",
                 "embedding_allowed", "redistribution_allowed",
                 "public_export_allowed", "approved_for_bbrose",
                 "approved_for_other_brands"):
        assert p[flag] is False
    assert p["approved_products"] == [] and p["approved_markets"] == []
    assert p["attribution_required"] is None
    assert p["review_expiry"] is None


# --- 5. machine may REDUCE, never INCREASE ----------------------------------
def test_machine_may_reduce_certainty():
    rec = RM.rights_record("x.ai")
    RM.machine_transition(rec, RM.AXIS_OWNERSHIP, C.OWN_DISPUTED,
                          reason="two conflicting sources")
    assert RM.effective_state(rec, RM.AXIS_OWNERSHIP) == C.OWN_DISPUTED
    RM.machine_transition(rec, RM.AXIS_LICENSE, C.LIC_EXPIRED_OR_REVIEW,
                          reason="review date passed")
    assert RM.effective_state(rec, RM.AXIS_LICENSE) == C.LIC_EXPIRED_OR_REVIEW


def test_machine_may_never_increase_certainty():
    rec = RM.rights_record("x.ai")
    RM.machine_transition(rec, RM.AXIS_OWNERSHIP, C.OWN_DISPUTED, reason="conflict")
    # DISPUTED (rank 0) -> BBROSE_OWNED_UNCONFIRMED (rank 2) is an INCREASE. It is
    # rejected TWICE over: it is not in the explicit matrix, AND it raises rank.
    with pytest.raises((RM.IllegalTransition, RM.MachineMayNotIncrease)):
        RM.machine_transition(rec, RM.AXIS_OWNERSHIP, C.OWN_BBROSE_UNCONFIRMED,
                              reason="nice try")


def test_the_explicit_matrix_is_authoritative_not_the_rank():
    """A REDUCING transition that is NOT in the matrix must still be refused.

    LICENSE_INTERNAL_ONLY (rank 2) -> QUARANTINED (rank 0) lowers certainty, and
    QUARANTINED is machine-emittable — so rank alone would wave it through. It is
    not in the allowlist, so it is refused. Rank may only ever REJECT; it never
    authorises.
    """
    assert RM.RANK[RM.AXIS_LICENSE][C.LIC_QUARANTINED] < \
        RM.RANK[RM.AXIS_LICENSE][C.LIC_INTERNAL_ONLY]      # a reduction
    assert C.LIC_QUARANTINED in C.MACHINE_ALLOWED_LICENSE   # and machine-emittable
    assert (C.LIC_INTERNAL_ONLY, C.LIC_QUARANTINED) not in \
        RM.MACHINE_TRANSITIONS[RM.AXIS_LICENSE]             # but NOT in the matrix
    with pytest.raises(RM.IllegalTransition):
        RM.validate_transition(RM.AXIS_LICENSE, C.LIC_INTERNAL_ONLY,
                               C.LIC_QUARANTINED, RM.ACTOR_MACHINE)


def test_lateral_transitions_must_be_explicit_and_record_reason():
    """Equal rank = a DIFFERENT HYPOTHESIS, not less certainty. It is allowed only
    because it is listed, and it must record its reason and previous state."""
    rec = RM.rights_record("ATC LOGO.ai")
    rec["machine_inference"]["ownership"]["machine_state"] = \
        C.OWN_BBROSE_UNCONFIRMED
    assert RM.is_lateral(RM.AXIS_OWNERSHIP, C.OWN_BBROSE_UNCONFIRMED,
                         C.OWN_THIRD_PARTY_UNCONFIRMED)
    RM.machine_transition(rec, RM.AXIS_OWNERSHIP, C.OWN_THIRD_PARTY_UNCONFIRMED,
                          reason="live text reads 'ATC'")
    blk = rec["machine_inference"]["ownership"]
    assert blk["machine_state"] == C.OWN_THIRD_PARTY_UNCONFIRMED
    assert blk["previous_state"] == C.OWN_BBROSE_UNCONFIRMED   # never lost
    h = blk["transition_history"][-1]
    assert h["lateral"] is True and h["reason"] == "live text reads 'ATC'"


def test_a_transition_without_a_reason_is_refused():
    rec = RM.rights_record("x.ai")
    with pytest.raises(ValueError):
        RM.machine_transition(rec, RM.AXIS_OWNERSHIP, C.OWN_DISPUTED, reason="")


def test_machine_cannot_grant_any_permission():
    perms = RM.permissions()
    for flag in RM.PERMISSION_FLAGS:
        proposed = dict(perms)
        proposed[flag] = True
        with pytest.raises(RM.MachineMayNotIncrease):
            RM.machine_permission_update(perms, proposed)


def test_machine_cannot_widen_an_approved_list():
    current = dict(RM.permissions(), approved_markets=["EU"])
    with pytest.raises(RM.MachineMayNotIncrease):
        RM.machine_permission_update(current,
                                     dict(current, approved_markets=["EU", "US"]))
    # narrowing IS allowed
    assert RM.machine_permission_update(
        current, dict(current, approved_markets=[]))["approved_markets"] == []


def test_machine_cannot_relax_an_attribution_requirement():
    current = dict(RM.permissions(), attribution_required=True)
    with pytest.raises(RM.MachineMayNotIncrease):
        RM.machine_permission_update(current,
                                     dict(current, attribution_required=False))


def test_machine_may_revoke_a_granted_permission():
    rec = RM.rights_record("x.ai")
    rec["permissions"]["retrieval_allowed"] = True        # a human granted it
    RM.machine_revoke(rec, "retrieval_allowed", reason="review expired")
    assert rec["permissions"]["retrieval_allowed"] is False
    assert rec["permissions"]["_machine_revocations"][0]["actor"] == \
        RM.ACTOR_MACHINE


# --- 6. human-only states are unreachable from machine functions -------------
@pytest.mark.parametrize("state", C.HUMAN_ONLY_OWNERSHIP)
def test_machine_cannot_emit_any_human_only_ownership_state(state):
    with pytest.raises(C.HumanOnlyStateViolation):
        C.machine_ownership(state)


@pytest.mark.parametrize("state", C.HUMAN_ONLY_LICENSE)
def test_machine_cannot_emit_any_human_only_license_state(state):
    with pytest.raises(C.HumanOnlyStateViolation):
        C.machine_license(state)


def test_machine_cannot_invent_a_business_assertion():
    with pytest.raises(C.HumanOnlyStateViolation):
        C.machine_ownership(C.OWN_BUSINESS_ASSERTED_BBROSE)


def test_machine_cannot_select_the_canonical_master():
    with pytest.raises(C.HumanOnlyStateViolation):
        C.machine_brand_master(C.CANONICAL_BRAND_MASTER)


# --- 7. illegal transitions are rejected -------------------------------------
@pytest.mark.parametrize("axis,frm,to", [
    (RM.AXIS_OWNERSHIP, C.OWN_UNKNOWN, C.OWN_BBROSE_CONFIRMED),
    (RM.AXIS_OWNERSHIP, C.OWN_BBROSE_UNCONFIRMED, C.OWN_THIRD_PARTY_CONFIRMED),
    (RM.AXIS_LICENSE, C.LIC_UNVERIFIED, C.LIC_APPROVED),
    (RM.AXIS_LICENSE, C.LIC_NO_EVIDENCE, C.LIC_INTERNAL_ONLY),
])
def test_forbidden_machine_transitions_are_rejected(axis, frm, to):
    with pytest.raises(C.HumanOnlyStateViolation):
        RM.validate_transition(axis, frm, to, RM.ACTOR_MACHINE)


@pytest.mark.parametrize("axis,frm,to", [
    (RM.AXIS_OWNERSHIP, C.OWN_UNKNOWN, C.OWN_DISPUTED),
    (RM.AXIS_OWNERSHIP, C.OWN_BBROSE_UNCONFIRMED, C.OWN_QUARANTINED),
    (RM.AXIS_LICENSE, C.LIC_UNVERIFIED, C.LIC_EXPIRED_OR_REVIEW),
    (RM.AXIS_LICENSE, C.LIC_UNVERIFIED, C.LIC_QUARANTINED),
])
def test_allowed_machine_transitions_are_accepted(axis, frm, to):
    assert RM.validate_transition(axis, frm, to, RM.ACTOR_MACHINE) == to


def test_a_human_may_confirm_but_never_by_asserting():
    # a human may confirm
    assert RM.validate_transition(RM.AXIS_OWNERSHIP, C.OWN_UNKNOWN,
                                  C.OWN_BBROSE_CONFIRMED, RM.ACTOR_HUMAN) == \
        C.OWN_BBROSE_CONFIRMED
    # but nobody may set an ASSERTION as a confirmed state
    with pytest.raises(RM.IllegalTransition):
        RM.validate_transition(RM.AXIS_OWNERSHIP, C.OWN_UNKNOWN,
                               C.OWN_BUSINESS_ASSERTED_BBROSE, RM.ACTOR_HUMAN)


# --- 8. the four layers use SEPARATE keys ------------------------------------
def test_the_four_layers_have_disjoint_keys():
    rec = RM.rights_record("x.ai")
    sets = [set(rec["business_assertion"]),
            set(rec["machine_inference"][RM.AXIS_OWNERSHIP]),
            set(rec["human_confirmation"][RM.AXIS_OWNERSHIP]),
            set(rec["permissions"])]
    for i, a in enumerate(sets):
        for b in sets[i + 1:]:
            assert not (a & b), f"layers share keys: {sorted(a & b)}"


def test_machine_transition_never_touches_confirmation_or_permissions():
    rec = RM.rights_record("x.ai")
    conf_before = copy.deepcopy(rec["human_confirmation"])
    perms_before = copy.deepcopy(rec["permissions"])
    RM.machine_transition(rec, RM.AXIS_OWNERSHIP, C.OWN_QUARANTINED,
                          reason="pending review")
    assert rec["human_confirmation"] == conf_before
    assert rec["permissions"] == perms_before


# --- 9. contradictory evidence does not erase a business assertion -----------
def test_contradictory_evidence_does_not_erase_a_business_assertion():
    """LOGO6.ai: the business says it is theirs; the live text says 'global
    logistics services'. Both must remain visible."""
    rec = RM.rights_record("LOGO6.ai")
    rec["business_assertion"] = RM.business_assertion(
        C.OWN_BUSINESS_ASSERTED_BBROSE, asserted_by="owner",
        notes="this is our logo")
    # the machine finds contradicting evidence and DISPUTES ownership
    RM.machine_transition(
        rec, RM.AXIS_OWNERSHIP, C.OWN_DISPUTED,
        reason="live text reads 'global logistics services'")
    # the dispute is recorded ...
    assert RM.effective_state(rec, RM.AXIS_OWNERSHIP) == C.OWN_DISPUTED
    # ... and the assertion SURVIVES, unerased
    assert rec["business_assertion"]["asserted_state"] == \
        C.OWN_BUSINESS_ASSERTED_BBROSE
    assert rec["business_assertion"]["asserted_by"] == "owner"
    assert rec["business_assertion"]["withdrawn_at"] is None


# --- 10. deterministic serialization -----------------------------------------
def test_model_serializes_deterministically():
    a = RM.rights_record("x.ai")
    b = RM.rights_record("x.ai")
    for rec in (a, b):
        rec["machine_inference"]["ownership"]["machine_inferred_at"] = "FIXED"
        rec["machine_inference"]["license"]["machine_inferred_at"] = "FIXED"
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# --- 11. the validator run ----------------------------------------------------
def test_model_validator_passes():
    assert run_c3b1.main() == 0
    recon = json.loads((C.MILESTONE_OUTPUT_ROOT / "c3b1_reconciliation.json")
                       .read_text(encoding="utf-8"))
    g = recon["machine_guards"]
    assert g["machine_never_increases_certainty"] is True
    assert g["machine_cannot_grant_any_permission"] is True
    assert g["machine_may_revoke"] is True
    assert recon["four_layers"]["layers_are_disjoint"] is True
    assert recon["business_assertion_behaviour"][
        "assertion_alone_cannot_confirm"] is True
    assert recon["integrity"]["materials"]["unchanged"] is True
