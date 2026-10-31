"""DIP-0C3b2 tests — evidence, assertions, authorisation, the append-only ledger.

The ledger's value is entirely in what it REFUSES, so the refusals are the tests:
an assertion cannot confirm; unreviewed or rejected evidence cannot support a
confirmation; an unauthorised actor cannot decide even with perfect evidence;
records cannot be edited or deleted; and rank never silently authorises a
transition the explicit matrix does not list.
"""
from __future__ import annotations

import json

import pytest

from tools.dip0c import authz, config as C, ledger as L, ledger_store as LS
from tools.dip0c import rights_model as RM
from tools.dip0c import run_c3b2

T = "2026-07-11T09:00:00+00:00"


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    """Point the ledger at a temp tree so tests never touch the real one."""
    root = tmp_path / "decisions"
    monkeypatch.setattr(L, "LEDGER_ROOT", root)
    monkeypatch.setattr(L, "EVENTS_DIR", root / "events")
    monkeypatch.setattr(L, "EVIDENCE_DIR", root / "evidence")
    monkeypatch.setattr(L, "ASSERTIONS_DIR", root / "assertions")
    monkeypatch.setattr(L, "INDEX_PATH", root / "index.json")
    monkeypatch.setattr(LS, "KINDS", {
        "events": (root / "events", "event_id"),
        "evidence": (root / "evidence", "evidence_id"),
        "assertions": (root / "assertions", "assertion_id"),
    })
    monkeypatch.setattr(C, "assert_output_safe", lambda p: p)
    LS.ensure_dirs()
    return root


def _evidence(asset="LOGO6.ai", accepted=False, rejected=False):
    e = L.evidence(asset, evidence_type="CONTRACT", title="design contract",
                   submitted_by="owner", actor_role=authz.BUSINESS_OWNER,
                   submitted_at=T, confidence=0.8)
    if accepted:
        e["review_status"] = L.EV_ACCEPTED
        e["reviewed_by"] = "legal"
        e["reviewed_at"] = T
    if rejected:
        e["review_status"] = L.EV_REJECTED
        e["reviewed_by"] = "legal"
        e["reviewed_at"] = T
    e["content_hash"] = L.content_hash(e)
    return e


def _confirm(evidence_records, role=authz.LEGAL_REVIEWER, reason="contract on file",
             contradiction=None, state=C.OWN_BBROSE_CONFIRMED,
             current=C.OWN_UNKNOWN):
    return L.check_confirmation(
        "LOGO6.ai", requested_state=state, actor_role=role, actor_id="a",
        current_state=current, axis=RM.AXIS_OWNERSHIP,
        evidence_records=evidence_records, reason=reason,
        contradiction=contradiction)


# --- 1-3. what cannot support a confirmation --------------------------------
def test_business_assertion_alone_cannot_confirm_ownership():
    ok, problems = _confirm([])
    assert ok is False
    assert any("BELIEF" in p for p in problems)


def test_unreviewed_evidence_cannot_support_confirmation():
    ok, problems = _confirm([_evidence()])          # SUBMITTED, not reviewed
    assert ok is False
    assert any("REVIEWED_ACCEPTED" in p for p in problems)


def test_rejected_evidence_cannot_support_confirmation():
    ok, problems = _confirm([_evidence(rejected=True)])
    assert ok is False
    assert any("REVIEWED_ACCEPTED" in p for p in problems)


# --- 4-5. authorisation ------------------------------------------------------
def test_accepted_evidence_plus_unauthorized_actor_still_fails():
    """A DESIGN_REVIEWER with perfect evidence still may not decide ownership."""
    ok, problems = _confirm([_evidence(accepted=True)],
                            role=authz.DESIGN_REVIEWER)
    assert ok is False
    assert any("unauthorized" in p for p in problems)


def test_system_admin_may_revoke_but_may_not_approve_a_license():
    assert authz.may(authz.SYSTEM_ADMIN, authz.REVOKE_DECISION) is True
    assert authz.may(authz.SYSTEM_ADMIN, authz.APPROVE_LICENSE) is False
    with pytest.raises(authz.NotAuthorized):
        authz.authorize(authz.SYSTEM_ADMIN, authz.APPROVE_LICENSE)


def test_observer_may_do_nothing():
    for action in authz.ACTIONS:
        assert authz.may(authz.OBSERVER, action) is False


def test_authorized_actor_plus_accepted_evidence_may_confirm():
    ok, problems = _confirm([_evidence(accepted=True)])
    assert ok is True, problems


# --- 6. contradiction acknowledgement (the LOGO6.ai case) -------------------
def test_unacknowledged_contradiction_blocks_confirmation():
    c = L.contradiction_block(
        present=True, refs=["live text reads 'global logistics services'"],
        acknowledged=False)
    ok, problems = _confirm([_evidence(accepted=True)], contradiction=c)
    assert ok is False
    assert any("has NOT been acknowledged" in p for p in problems)


def test_acknowledged_contradiction_requires_a_reason():
    c = L.contradiction_block(present=True, refs=["x"], acknowledged=True,
                              reason="")
    ok, problems = _confirm([_evidence(accepted=True)], contradiction=c)
    assert ok is False
    assert any("requires a reason" in p for p in problems)


def test_a_reviewer_may_confirm_despite_a_contradiction_if_they_say_so():
    c = L.contradiction_block(
        present=True, refs=["live text reads 'global logistics services'"],
        acknowledged=True,
        reason="the wordmark was licensed from a prior owner; contract attached")
    ok, problems = _confirm([_evidence(accepted=True)], contradiction=c)
    assert ok is True, problems


# --- 7. the explicit matrix stays authoritative ------------------------------
def test_certainty_rank_does_not_silently_authorize_a_lateral_transition():
    """A REDUCING, machine-emittable transition that is not in the matrix is still
    refused. Rank may only reject; it never authorises."""
    assert RM.RANK[RM.AXIS_LICENSE][C.LIC_QUARANTINED] < \
        RM.RANK[RM.AXIS_LICENSE][C.LIC_INTERNAL_ONLY]
    assert (C.LIC_INTERNAL_ONLY, C.LIC_QUARANTINED) not in \
        RM.MACHINE_TRANSITIONS[RM.AXIS_LICENSE]
    with pytest.raises(RM.IllegalTransition):
        RM.validate_transition(RM.AXIS_LICENSE, C.LIC_INTERNAL_ONLY,
                               C.LIC_QUARANTINED, RM.ACTOR_MACHINE)


def test_illegal_transition_blocks_confirmation():
    ok, problems = _confirm([_evidence(accepted=True)],
                            state=C.OWN_BBROSE_CONFIRMED,
                            current="NOT_A_STATE")
    assert ok is False
    assert any("illegal transition" in p for p in problems)


# --- 8-12. append-only enforcement -------------------------------------------
def test_an_existing_record_cannot_be_modified(ledger):
    e = _evidence()
    LS.append("evidence", e)
    tampered = dict(e, title="a different title")
    with pytest.raises(L.LedgerError):
        LS.append("evidence", tampered)         # same id, different content


def test_editing_a_file_on_disk_is_detected(ledger):
    e = _evidence()
    path = LS.append("evidence", e)
    LS.write_index()
    # somebody edits the file behind the tool's back
    raw = json.loads(path.read_text())
    raw["title"] = "SILENTLY CHANGED"
    path.write_text(json.dumps(raw, indent=2))
    report = LS.validate()
    assert report["valid"] is False
    assert report["findings"]["hash_mismatches"]
    assert e["evidence_id"] in report["findings"]["modified_records"]


def test_deleting_a_file_is_detected(ledger):
    e = _evidence()
    path = LS.append("evidence", e)
    LS.write_index()          # the index remembers it existed
    path.unlink()             # ... and then it vanishes
    report = LS.validate()
    assert report["valid"] is False
    assert any(d["id"] == e["evidence_id"]
               for d in report["findings"]["deleted_records"])


def test_broken_supersedes_reference_is_detected(ledger):
    evt = L.event("x.ai", event_type=L.OWNERSHIP_REVOKED, actor_id="legal",
                  actor_role=authz.LEGAL_REVIEWER, occurred_at=T,
                  decision_reason="revoked", supersedes_event_id="evt-DOES-NOT-EXIST")
    LS.append("events", evt)
    report = LS.validate()
    assert report["valid"] is False
    assert report["findings"]["broken_supersedes"]


def test_missing_evidence_reference_is_detected(ledger):
    evt = L.event("x.ai", event_type=L.OWNERSHIP_CONFIRMED, actor_id="legal",
                  actor_role=authz.LEGAL_REVIEWER, occurred_at=T,
                  previous_state=C.OWN_UNKNOWN,
                  requested_state=C.OWN_BBROSE_CONFIRMED,
                  decision_reason="ok", evidence_refs=["evd-NOPE"])
    LS.append("events", evt)
    report = LS.validate()
    assert report["valid"] is False
    assert report["findings"]["missing_evidence_refs"]


def test_content_hashes_are_verified(ledger):
    e = _evidence()
    assert L.content_hash(e) == e["content_hash"]
    # the hash excludes the volatile fields, so it is stable across re-recording
    e2 = dict(e, recorded_at="2099-01-01T00:00:00+00:00")
    assert L.content_hash(e2) == e["content_hash"]


def test_corrections_append_rather_than_overwrite(ledger):
    ok_ev = _evidence(accepted=True)
    LS.append("evidence", ok_ev)
    first = L.event("x.ai", event_type=L.OWNERSHIP_CONFIRMED, actor_id="legal",
                    actor_role=authz.LEGAL_REVIEWER, occurred_at=T,
                    previous_state=C.OWN_UNKNOWN,
                    requested_state=C.OWN_BBROSE_CONFIRMED,
                    decision_reason="contract", evidence_refs=[ok_ev["evidence_id"]])
    LS.append("events", first)
    # a correction: a NEW event that supersedes the first. The first still exists.
    correction = L.event("x.ai", event_type=L.OWNERSHIP_REVOKED, actor_id="legal",
                         actor_role=authz.LEGAL_REVIEWER,
                         occurred_at="2026-08-01T00:00:00+00:00",
                         decision_reason="the contract was for a different mark",
                         supersedes_event_id=first["event_id"])
    LS.append("events", correction)
    events = LS.load("events")
    assert len(events) == 2                       # history is COMPLETE
    assert first["event_id"] in {e["event_id"] for e in events}
    assert LS.validate()["valid"] is True


def test_a_corrective_event_must_reference_what_it_supersedes():
    with pytest.raises(L.LedgerError):
        L.event("x.ai", event_type=L.OWNERSHIP_REVOKED, actor_id="legal",
                actor_role=authz.LEGAL_REVIEWER, occurred_at=T,
                decision_reason="revoked")        # no supersedes_event_id


# --- 13-14. machine/human separation + permissions ---------------------------
def test_a_ledger_event_never_mutates_machine_inference(ledger):
    machine = RM.rights_record("x.ai")
    before = json.dumps(machine["machine_inference"], sort_keys=True)
    ok_ev = _evidence("x.ai", accepted=True)
    LS.append("evidence", ok_ev)
    LS.append("events", L.event(
        "x.ai", event_type=L.OWNERSHIP_CONFIRMED, actor_id="legal",
        actor_role=authz.LEGAL_REVIEWER, occurred_at=T,
        previous_state=C.OWN_UNKNOWN, requested_state=C.OWN_BBROSE_CONFIRMED,
        decision_reason="contract", evidence_refs=[ok_ev["evidence_id"]]))
    rm = LS.read_model("x.ai", machine)
    # the read model reflects the decision ...
    assert rm["effective_ownership"] == C.OWN_BBROSE_CONFIRMED
    # ... and the machine inference is untouched
    assert json.dumps(machine["machine_inference"], sort_keys=True) == before


def test_permissions_remain_false_even_after_a_confirmation(ledger):
    machine = RM.rights_record("x.ai")
    ok_ev = _evidence("x.ai", accepted=True)
    LS.append("evidence", ok_ev)
    LS.append("events", L.event(
        "x.ai", event_type=L.OWNERSHIP_CONFIRMED, actor_id="legal",
        actor_role=authz.LEGAL_REVIEWER, occurred_at=T,
        previous_state=C.OWN_UNKNOWN, requested_state=C.OWN_BBROSE_CONFIRMED,
        decision_reason="contract", evidence_refs=[ok_ev["evidence_id"]]))
    rm = LS.read_model("x.ai", machine)
    assert rm["effective_ownership"] == C.OWN_BBROSE_CONFIRMED
    assert all(rm["permissions"][f] is False for f in RM.PERMISSION_FLAGS)


# --- 15. an assertion survives a withdrawal and a contradiction --------------
def test_withdrawal_does_not_delete_an_assertion(ledger):
    a = L.assertion("LOGO6.ai", asserted_state=C.OWN_BUSINESS_ASSERTED_BBROSE,
                    asserted_by="owner", actor_role=authz.BUSINESS_OWNER,
                    asserted_at=T, notes="this is our logo")
    LS.append("assertions", a)
    withdrawn = L.assertion(
        "LOGO6.ai", asserted_state=C.OWN_BUSINESS_ASSERTED_BBROSE,
        asserted_by="owner", actor_role=authz.BUSINESS_OWNER,
        asserted_at="2026-08-01T00:00:00+00:00",
        notes="superseding: we no longer believe this",
        supersedes_assertion_id=a["assertion_id"])
    LS.append("assertions", withdrawn)
    stored = LS.load("assertions")
    assert len(stored) == 2                        # the original SURVIVES
    assert a["assertion_id"] in {x["assertion_id"] for x in stored}


# --- 16-17. no canonical-master action, no DB, no UI -------------------------
def test_canonical_master_arrived_in_c3b3_and_stays_human_only():
    """C3b2 asserted the canonical workflow did not exist yet. C3b3 built it, so
    this scope guard graduates into the invariant it was protecting: the actions and
    events now exist, and every DECIDING state remains unreachable from machine code.
    """
    from tools.dip0c import config as CFG
    assert any("canonical" in a.lower() for a in authz.ACTIONS)
    assert any("CANONICAL" in e for e in L.EVENT_TYPES)
    for state in CFG.HUMAN_ONLY_CANONICAL:
        with pytest.raises(CFG.HumanOnlyStateViolation):
            CFG.machine_brand_master(state)


def test_no_database_or_ui_module_is_introduced():
    import pathlib
    d = pathlib.Path("tools/dip0c")
    names = {p.name for p in d.glob("*.py")}
    assert "models.py" not in names and "views.py" not in names
    assert not any("migrations" in str(p) for p in d.rglob("*"))


# --- 18-19. determinism + integrity -------------------------------------------
def test_index_generation_is_deterministic(ledger):
    LS.append("evidence", _evidence())
    a = LS.build_index()
    b = LS.build_index()
    a.pop("generated_at"), b.pop("generated_at")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_index_is_not_the_source_of_truth(ledger):
    LS.append("evidence", _evidence())
    idx = LS.build_index()
    assert "source of truth" in idx["note"]
    assert "GENERATED" in idx["note"]


def test_full_run_and_source_integrity():
    assert run_c3b2.main() == 0
    # read the reconciliation the runner just wrote to the injectable output root (a temp
    # dir under test) — never the frozen committed copy
    recon = json.loads((C.MILESTONE_OUTPUT_ROOT / "c3b2_reconciliation.json")
                       .read_text(encoding="utf-8"))
    assert recon["ledger_valid"] is True
    assert recon["integrity"]["materials"]["unchanged"] is True
    assert recon["permissions_still_all_false"] is True
    # THE REAL LEDGER IS EMPTY — no real approval was fabricated
    assert recon["real_ledger"]["events"] == 0
    assert recon["real_ledger"]["assertions"] == 0
    assert recon["examples_TEST_ONLY"]["logo6_confirmation_refused"] is True
