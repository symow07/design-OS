"""DIP-0C3b3 — canonical-master workflow, permission grants, scopes, expiry."""
from __future__ import annotations

import pytest

from tools.dip0c import authz
from tools.dip0c import canonical_master as CM
from tools.dip0c import config as C
from tools.dip0c import ledger as L
from tools.dip0c import permissions as P
from tools.dip0c import rights_model as RM
from tools.dip0c import run_c3b3

T0 = "2026-07-11T09:00:00+00:00"
EXPIRY = "2026-10-01T00:00:00+00:00"
BEFORE = "2026-09-30T00:00:00+00:00"
AFTER = "2026-10-02T00:00:00+00:00"
ASSET = "TEST_ONLY_asset.ai"


# --- helpers -----------------------------------------------------------------
def _ev(asset=ASSET, status=L.EV_ACCEPTED, reviewer="TEST_ONLY_legal"):
    e = L.evidence(asset, evidence_type="CONTRACT", title="t",
                   submitted_by="TEST_ONLY_owner", actor_role=authz.BUSINESS_OWNER,
                   submitted_at=T0)
    e["review_status"] = status
    e["reviewed_by"] = reviewer
    return e


TECH = "alice_brand_admin"
LEGAL = "bob_legal"


def _checklist(tech_id=TECH, legal_id=LEGAL, **overrides):
    cl = CM.blank_checklist()
    for k in cl:
        by = tech_id if k in CM.TECHNICAL_ITEMS else legal_id
        cl[k] = {"result": True, "confirmed_by": by, "confirmed_at": T0, "notes": ""}
    for k, v in overrides.items():
        cl[k]["result"] = v
    return cl


def _atts(tech_id=TECH, tech_role=authz.BRAND_ADMIN,
          legal_id=LEGAL, legal_role=authz.LEGAL_REVIEWER):
    return [
        CM.attestation(CM.ATT_TECHNICAL, actor_id=tech_id, actor_role=tech_role,
                       attested_at=T0),
        CM.attestation(CM.ATT_LEGAL, actor_id=legal_id, actor_role=legal_role,
                       attested_at=T0),
    ]


def _approve(asset=ASSET, **kw):
    kw.setdefault("requested_state", C.CANONICAL_BRAND_MASTER)
    kw.setdefault("actor_role", authz.BRAND_ADMIN)
    kw.setdefault("actor_id", TECH)
    kw.setdefault("checklist", _checklist())
    kw.setdefault("attestations", _atts())
    kw.setdefault("ownership_state", C.OWN_BBROSE_CONFIRMED)
    kw.setdefault("evidence_records", [_ev(asset)])
    kw.setdefault("reason", "test")
    kw.setdefault("requested_scope", CM.scope("BBROSE"))
    return CM.check_canonical_approval(asset, **kw)


def _grant(flag="retrieval_allowed", *, expiry=EXPIRY, brands=("BBROSE",),
           markets=(), products=(), start=T0, occurred_at=T0, asset=ASSET):
    return L.event(
        asset, event_type=L.PERMISSION_GRANTED, actor_id="TEST_ONLY_legal",
        actor_role=authz.LEGAL_REVIEWER, occurred_at=occurred_at,
        decision_reason="test grant", evidence_refs=["ev-1"], review_expiry=expiry,
        permission=L.permission_block(
            flag, previous_value=False, requested_value=True, purpose="p",
            approved_brands=list(brands), approved_markets=list(markets),
            approved_products=list(products), validity_start=start,
            review_expiry=expiry, ownership_decision_ref="evt-own",
            license_decision_ref="evt-lic"))


# === 1-4. canonical states are human-only ====================================
@pytest.mark.parametrize("state", C.HUMAN_ONLY_CANONICAL)
def test_machine_may_not_emit_any_human_canonical_state(state):
    with pytest.raises(C.HumanOnlyStateViolation):
        CM.machine_canonical(state)


def test_machine_may_emit_only_the_four_nomination_states():
    for s in C.MACHINE_ALLOWED_CANONICAL:
        assert CM.machine_canonical(s) == s
    assert C.CANONICAL_BRAND_MASTER not in C.MACHINE_ALLOWED_CANONICAL


def test_nomination_is_not_approval():
    """BRAND_MASTER_CANDIDATE grants nothing and is not the canonical master."""
    nominated = CM.machine_canonical(C.BRAND_MASTER_CANDIDATE)
    assert nominated != C.CANONICAL_BRAND_MASTER
    eff = P.effective_permissions(ASSET, [], now=T0)
    assert not any(r["value"] for r in eff["permissions"].values())


def test_canonical_event_without_a_canonical_block_is_refused():
    with pytest.raises(L.LedgerError):
        L.event(ASSET, event_type=L.CANONICAL_MASTER_APPROVED,
                actor_id="a", actor_role=authz.BRAND_ADMIN, occurred_at=T0,
                decision_reason="r")


# === 5-8. the checklist ======================================================
def test_blank_checklist_is_unanswered_not_passing():
    cl = CM.blank_checklist()
    assert all(v["result"] is None for v in cl.values())
    ok, problems = _approve(checklist=cl)
    assert not ok
    assert any("UNANSWERED" in p for p in problems)


def test_a_single_unanswered_item_blocks_approval():
    cl = _checklist()
    cl["official_proportions_confirmed"]["result"] = None
    ok, problems = _approve(checklist=cl)
    assert not ok
    assert any("official_proportions_confirmed" in p for p in problems)


def test_a_failed_item_blocks_approval():
    ok, problems = _approve(checklist=_checklist(editable_vector_confirmed=False))
    assert not ok
    assert any("failed" in p for p in problems)


def test_no_role_can_both_declare_a_file_authoritative_and_let_it_out():
    """APPROVE_CANONICAL_MASTER and GRANT_LEGAL_PERMISSION are disjoint. Deciding a
    file IS the brand and deciding the world may have it are never one person's call.
    """
    approvers = set(authz.POLICY[authz.APPROVE_CANONICAL_MASTER])
    releasers = set(authz.POLICY[authz.GRANT_LEGAL_PERMISSION])
    assert approvers and releasers
    assert not (approvers & releasers)


def test_every_checklist_item_belongs_to_exactly_one_attestation():
    assert set(CM.TECHNICAL_ITEMS) | set(CM.LEGAL_ITEMS) == set(CM.CHECKLIST)
    assert not (set(CM.TECHNICAL_ITEMS) & set(CM.LEGAL_ITEMS))
    assert len(CM.CHECKLIST_ATTESTATION) == len(CM.CHECKLIST)


def test_neither_attestation_role_can_answer_the_other_half():
    """The split is what makes dual control real: a DESIGN_REVIEWER is not permitted
    to attest rights, and a LEGAL_REVIEWER is not permitted to attest geometry."""
    assert not authz.may(authz.DESIGN_REVIEWER, authz.ATTEST_CANONICAL_LEGAL)
    assert not authz.may(authz.LEGAL_REVIEWER, authz.ATTEST_CANONICAL_TECHNICAL)
    assert authz.may(authz.LEGAL_REVIEWER, authz.ATTEST_CANONICAL_LEGAL)
    assert authz.may(authz.DESIGN_REVIEWER, authz.ATTEST_CANONICAL_TECHNICAL)
    assert authz.may(authz.BRAND_ADMIN, authz.ATTEST_CANONICAL_TECHNICAL)


# === DUAL CONTROL ============================================================
def test_one_brand_admin_alone_cannot_approve_a_canonical_master():
    solo = _checklist(tech_id=TECH, legal_id=TECH)
    ok, problems = _approve(
        checklist=solo,
        attestations=_atts(tech_id=TECH, legal_id=TECH,
                           legal_role=authz.LEGAL_REVIEWER))
    assert not ok
    assert any("DUAL CONTROL" in p and "BOTH halves" in p for p in problems)


def test_technical_attestation_without_legal_is_blocked():
    ok, problems = _approve(attestations=[_atts()[0]])
    assert not ok
    assert any("RIGHTS_AND_OWNERSHIP attestation is missing" in p
               for p in problems)


def test_legal_attestation_without_technical_is_blocked():
    ok, problems = _approve(attestations=[_atts()[1]])
    assert not ok
    assert any("TECHNICAL_AND_BRAND attestation is missing" in p for p in problems)


def test_no_attestations_at_all_is_blocked():
    ok, problems = _approve(attestations=[])
    assert not ok
    assert sum("attestation is missing" in p for p in problems) == 2


def test_one_person_holding_both_roles_still_cannot_satisfy_both_halves():
    """Separation is by ACTOR IDENTITY, not by role. Two hats, one person, no."""
    both = _checklist(tech_id="carol", legal_id="carol")
    ok, problems = _approve(
        actor_id="carol", checklist=both,
        attestations=_atts(tech_id="carol", tech_role=authz.BRAND_ADMIN,
                           legal_id="carol", legal_role=authz.LEGAL_REVIEWER))
    assert not ok
    assert any("two DIFFERENT people" in p for p in problems)


def test_two_distinct_authorized_actors_satisfy_the_separation_requirement():
    ok, problems = _approve()
    assert ok, problems


def test_the_legal_attestation_must_come_from_someone_other_than_the_activator():
    """The activator may have given the technical attestation; never the legal one."""
    cl = _checklist(tech_id=TECH, legal_id="dave")
    ok, problems = _approve(
        actor_id="dave", actor_role=authz.BRAND_ADMIN, checklist=cl,
        attestations=_atts(tech_id=TECH, legal_id="dave"))
    assert not ok
    assert any("activating actor" in p for p in problems)


def test_the_legal_attestation_is_legal_reviewers_alone():
    cl = _checklist(tech_id=TECH, legal_id="eve")
    ok, problems = _approve(
        checklist=cl,
        attestations=_atts(tech_id=TECH, legal_id="eve",
                           legal_role=authz.BRAND_ADMIN))
    assert not ok
    assert any("RIGHTS_AND_OWNERSHIP" in p and "may NOT" in p for p in problems)


def test_an_attester_may_only_cover_what_they_personally_confirmed():
    """Signing for items someone else ticked is not an attestation."""
    forged = _checklist(tech_id="someone_else", legal_id=LEGAL)
    ok, problems = _approve(checklist=forged, attestations=_atts())
    assert not ok
    assert any("personally confirmed" in p for p in problems)


def test_final_activation_still_requires_brand_admin():
    assert authz.POLICY[authz.APPROVE_CANONICAL_MASTER] == (authz.BRAND_ADMIN,)
    for role in (authz.DESIGN_REVIEWER, authz.LEGAL_REVIEWER, authz.BUSINESS_OWNER,
                 authz.SYSTEM_ADMIN, authz.OBSERVER):
        with pytest.raises(authz.NotAuthorized):
            authz.authorize(role, authz.APPROVE_CANONICAL_MASTER, actor_id="x")


def test_the_ledger_refuses_to_record_a_single_actor_canonical_approval():
    """Belt and braces: the guard is at the point of RECORDING too, so no code path
    can write the event by skipping check_canonical_approval()."""
    with pytest.raises(L.LedgerError, match="DIFFERENT people"):
        L.event(ASSET, event_type=L.CANONICAL_MASTER_APPROVED, actor_id=TECH,
                actor_role=authz.BRAND_ADMIN, occurred_at=T0,
                decision_reason="solo",
                canonical=L.canonical_block(
                    C.CANONICAL_BRAND_MASTER, scope=CM.scope("BBROSE"),
                    checklist=_checklist(tech_id=TECH, legal_id=TECH),
                    attestations=_atts(tech_id=TECH, legal_id=TECH)))


def test_the_ledger_refuses_a_canonical_approval_with_no_attestations():
    with pytest.raises(L.LedgerError, match="DUAL CONTROL"):
        L.event(ASSET, event_type=L.CANONICAL_MASTER_APPROVED, actor_id=TECH,
                actor_role=authz.BRAND_ADMIN, occurred_at=T0, decision_reason="r",
                canonical=L.canonical_block(
                    C.CANONICAL_BRAND_MASTER, scope=CM.scope("BBROSE"),
                    checklist=_checklist()))


def test_replacing_a_canonical_master_is_also_under_dual_control():
    assert L.CANONICAL_MASTER_REPLACED in L.DUAL_CONTROL_EVENTS
    with pytest.raises(L.LedgerError, match="DUAL CONTROL"):
        L.event(ASSET, event_type=L.CANONICAL_MASTER_REPLACED, actor_id=TECH,
                actor_role=authz.BRAND_ADMIN, occurred_at=T0, decision_reason="r",
                supersedes_event_id="evt-old",
                canonical=L.canonical_block(
                    C.CANONICAL_BRAND_MASTER, scope=CM.scope("BBROSE"),
                    checklist=_checklist()))


def test_dual_control_does_not_apply_to_variants_or_nomination():
    """It guards BECOMING the canonical master — nothing else."""
    assert L.VARIANT_CLASSIFIED not in L.DUAL_CONTROL_EVENTS
    assert L.CANONICAL_MASTER_DEPRECATED not in L.DUAL_CONTROL_EVENTS
    assert L.ASSET_QUARANTINED not in L.DUAL_CONTROL_EVENTS
    # a variant needs no attestations at all
    ok, problems = _approve(requested_state=C.MONOCHROME_VARIANT,
                            actor_role=authz.DESIGN_REVIEWER, actor_id="dr",
                            attestations=[])
    assert ok, problems


def test_dual_control_still_grants_no_operational_permission():
    """Two people signing does not switch anything on."""
    canon = L.event(
        ASSET, event_type=L.CANONICAL_MASTER_APPROVED, actor_id=TECH,
        actor_role=authz.BRAND_ADMIN, occurred_at=T0, decision_reason="r",
        canonical=L.canonical_block(C.CANONICAL_BRAND_MASTER,
                                    scope=CM.scope("BBROSE"),
                                    checklist=_checklist(),
                                    attestations=_atts()))
    eff = P.effective_permissions(ASSET, [canon], now=T0)
    assert all(r["value"] is False for r in eff["permissions"].values())


# === 9-11. approval prerequisites ============================================
def test_unconfirmed_ownership_blocks_canonical_approval():
    ok, problems = _approve(ownership_state=C.OWN_UNKNOWN)
    assert not ok
    assert any("ownership" in p for p in problems)


def test_unreviewed_evidence_blocks_canonical_approval():
    ok, problems = _approve(evidence_records=[_ev(status=L.EV_SUBMITTED,
                                                  reviewer=None)])
    assert not ok
    assert any("REVIEWED_ACCEPTED" in p for p in problems)


def test_unacknowledged_contradiction_blocks_canonical_approval():
    c = L.contradiction_block(present=True, refs=["logo text says another company"],
                              acknowledged=False)
    ok, problems = _approve(contradiction=c)
    assert not ok
    assert any("contradiction" in p for p in problems)


# === 12-13. conflicts ========================================================
def test_a_second_canonical_for_the_same_scope_is_refused_not_substituted():
    existing = [{"asset": "first.ai", "scope": CM.scope("BBROSE")}]
    ok, problems = _approve("second.ai", existing_canonicals=existing,
                            evidence_records=[_ev("second.ai")])
    assert not ok
    assert any("CANONICAL CONFLICT" in p for p in problems)
    assert any("NOT silently replaced" in p for p in problems)


def test_empty_scope_list_means_all_and_therefore_collides():
    """The dangerous case a naive set-intersection would miss. (C3b4 replaced the
    boolean overlap with the quad-state `collides`; the property is unchanged.)"""
    everything = CM.scope("BBROSE", markets=[])
    just_eu = CM.scope("BBROSE", markets=["EU"])
    assert CM.collides(everything, just_eu)
    flag = CM.detect_conflict(just_eu, [{"asset": "x", "scope": everything}])
    assert flag["state"] == C.POSSIBLE_CONFLICT
    assert flag["resolution_is_human_only"]


# === 14-16. authorisation ====================================================
def test_system_admin_may_never_select_a_canonical_master_or_grant():
    for action in (authz.APPROVE_CANONICAL_MASTER, authz.GRANT_PERMISSION,
                   authz.GRANT_LEGAL_PERMISSION, authz.CONFIRM_OWNERSHIP):
        with pytest.raises(authz.NotAuthorized):
            authz.authorize(authz.SYSTEM_ADMIN, action, actor_id="sa")
    # ...but it may still REDUCE
    authz.authorize(authz.SYSTEM_ADMIN, authz.QUARANTINE_ASSET, actor_id="sa")
    authz.authorize(authz.SYSTEM_ADMIN, authz.REVOKE_PERMISSION, actor_id="sa")


def test_only_legal_may_grant_a_permission_that_exposes_the_asset_outside():
    for flag in authz.LEGAL_PERMISSIONS:
        assert authz.permission_action(flag) == authz.GRANT_LEGAL_PERMISSION
        ok, problems = P.check_grant(
            flag, actor_role=authz.BRAND_ADMIN, actor_id=TECH,
            ownership_state=C.OWN_BBROSE_CONFIRMED, license_state=C.LIC_APPROVED,
            evidence_records=[_ev()], reason="r", purpose="p",
            ownership_decision_ref="evt-own", license_decision_ref="evt-lic")
        assert not ok
        assert any("unauthorized" in p for p in problems)


def test_observer_may_do_nothing():
    for action in authz.ACTIONS:
        assert not authz.may(authz.OBSERVER, action)


# === 17-19. permissions are independent, explicit, never derived =============
def test_canonical_master_does_not_equal_usable():
    """THE tested scenario: approved as canonical, yet every permission is false."""
    canon = L.event(
        ASSET, event_type=L.CANONICAL_MASTER_APPROVED, actor_id=TECH,
        actor_role=authz.BRAND_ADMIN, occurred_at=T0, decision_reason="r",
        canonical=L.canonical_block(C.CANONICAL_BRAND_MASTER,
                                    scope=CM.scope("BBROSE"),
                                    checklist=_checklist(),
                                    attestations=_atts(),
                                    version_or_date="v1"))
    eff = P.effective_permissions(ASSET, [canon], now=T0)
    assert all(r["value"] is False for r in eff["permissions"].values())
    assert all(r["status"] == C.EFF_DENIED_NO_GRANT
               for r in eff["permissions"].values())


def test_a_grant_of_one_permission_grants_only_that_permission():
    """No implicit bundles."""
    eff = P.effective_permissions(ASSET, [_grant("retrieval_allowed")], now=BEFORE,
                                  brand="BBROSE")
    assert eff["permissions"]["retrieval_allowed"]["value"] is True
    for flag in P.FLAGS:
        if flag != "retrieval_allowed":
            assert eff["permissions"][flag]["value"] is False


def test_permission_prerequisites_are_action_specific():
    """Retrieval needs no licence; production use requires an APPROVED one."""
    kw = dict(actor_role=authz.LEGAL_REVIEWER, actor_id="legal",
              ownership_state=C.OWN_BBROSE_CONFIRMED,
              license_state=C.LIC_UNVERIFIED, evidence_records=[_ev()],
              reason="r", purpose="p", ownership_decision_ref="evt-own",
              license_decision_ref="evt-lic")
    ok_retrieval, _ = P.check_grant("retrieval_allowed", **kw)
    ok_production, problems = P.check_grant("production_use_allowed", **kw)
    assert ok_retrieval
    assert not ok_production
    assert any("licence" in p for p in problems)


def test_a_permission_grant_event_must_name_its_flag():
    with pytest.raises(L.LedgerError):
        L.event(ASSET, event_type=L.PERMISSION_GRANTED, actor_id="legal",
                actor_role=authz.LEGAL_REVIEWER, occurred_at=T0,
                decision_reason="r")


# === 20-22. scopes, expiry, revocation =======================================
def test_scope_mismatch_denies_even_a_valid_grant():
    ev = [_grant(markets=["EU"])]
    assert P.effective_permissions(ASSET, ev, now=BEFORE, brand="BBROSE",
                                   market="EU")["permissions"][
                                       "retrieval_allowed"]["value"] is True
    us = P.effective_permissions(ASSET, ev, now=BEFORE, brand="BBROSE",
                                 market="US")["permissions"]["retrieval_allowed"]
    assert us["value"] is False
    assert us["status"] == C.EFF_DENIED_SCOPE


def test_expiry_fails_closed_without_waiting_for_an_audit_event():
    """No PERMISSION_EXPIRED event exists — the evaluation still denies."""
    ev = [_grant()]
    before = P.effective_permissions(ASSET, ev, now=BEFORE, brand="BBROSE")
    after = P.effective_permissions(ASSET, ev, now=AFTER, brand="BBROSE")
    assert before["permissions"]["retrieval_allowed"]["value"] is True
    assert after["permissions"]["retrieval_allowed"]["value"] is False
    assert after["permissions"]["retrieval_allowed"]["status"] \
        == C.EFF_RE_REVIEW_REQUIRED
    assert not any(e["event_type"] == L.PERMISSION_EXPIRED for e in ev)
    assert after["any_expired"]


def test_reading_permission_state_never_writes():
    """detect_expired and effective_permissions are pure."""
    ledger_files = sorted(L.LEDGER_ROOT.rglob("*.json"))
    ev = [_grant()]
    P.effective_permissions(ASSET, ev, now=AFTER)
    expired = P.detect_expired(ASSET, ev, now=AFTER)
    assert expired and expired[0]["flag"] == "retrieval_allowed"
    assert expired[0]["effective_value"] is False
    assert sorted(L.LEDGER_ROOT.rglob("*.json")) == ledger_files


def test_re_review_restores_nothing_by_itself():
    """Only a NEW authorized human grant can make it true again."""
    ev = [_grant()]
    rr = L.event(ASSET, event_type=L.RE_REVIEW_REQUIRED, actor_id="legal",
                 actor_role=authz.LEGAL_REVIEWER, occurred_at=AFTER,
                 decision_reason="expired")
    eff = P.effective_permissions(ASSET, ev + [rr], now=AFTER, brand="BBROSE")
    assert eff["permissions"]["retrieval_allowed"]["value"] is False

    regrant = _grant(expiry="2027-01-01T00:00:00+00:00", start=AFTER,
                     occurred_at=AFTER)
    eff2 = P.effective_permissions(ASSET, ev + [rr, regrant], now=AFTER,
                                   brand="BBROSE")
    assert eff2["permissions"]["retrieval_allowed"]["value"] is True


def test_machine_may_only_revoke_never_grant():
    assert P.machine_may_revoke_only(True, False) is False
    with pytest.raises(RM.MachineMayNotIncrease):
        P.machine_may_revoke_only(False, True)


def test_quarantine_denies_everything_regardless_of_grants():
    q = L.event(ASSET, event_type=L.ASSET_QUARANTINED, actor_id="sa",
                actor_role=authz.SYSTEM_ADMIN, occurred_at=BEFORE,
                decision_reason="disputed ownership")
    eff = P.effective_permissions(ASSET, [_grant(), q], now=BEFORE, brand="BBROSE")
    assert eff["quarantined"]
    assert eff["permissions"]["retrieval_allowed"]["value"] is False
    assert eff["permissions"]["retrieval_allowed"]["status"] \
        == C.EFF_DENIED_QUARANTINED


def test_revocation_denies_the_grant_it_supersedes():
    g = _grant()
    rev = L.event(ASSET, event_type=L.PERMISSION_REVOKED, actor_id="legal",
                  actor_role=authz.LEGAL_REVIEWER, occurred_at=BEFORE,
                  decision_reason="contract ended",
                  supersedes_event_id=g["event_id"],
                  permission=L.permission_block(
                      "retrieval_allowed", previous_value=True,
                      requested_value=False, purpose="p"))
    eff = P.effective_permissions(ASSET, [g, rev], now=BEFORE, brand="BBROSE")
    assert eff["permissions"]["retrieval_allowed"]["value"] is False
    assert eff["permissions"]["retrieval_allowed"]["status"] == C.EFF_DENIED_REVOKED


def test_attribution_requirement_persists_into_the_effective_model():
    g = _grant()
    g["permission"]["attribution_required"] = True
    eff = P.effective_permissions(ASSET, [g], now=BEFORE, brand="BBROSE")
    assert eff["attribution_required"] is True


def test_confirming_third_party_ownership_grants_nothing():
    """Retrieval's prerequisites DO admit THIRD_PARTY_CONFIRMED — so this is the
    trap. Settling WHOSE a logo is answers a question; it hands out no permission.
    """
    assert C.OWN_THIRD_PARTY_CONFIRMED in \
        P.PREREQUISITES["retrieval_allowed"]["requires_ownership"]
    eff = P.effective_permissions("JOJIA LOGO.ai", [], now=T0, brand="BBROSE")
    assert all(r["value"] is False for r in eff["permissions"].values())


def test_a_third_party_mark_can_never_be_bbroses_canonical_master():
    ok, problems = _approve("JOJIA LOGO.ai",
                            ownership_state=C.OWN_THIRD_PARTY_CONFIRMED,
                            evidence_records=[_ev("JOJIA LOGO.ai")],
                            requested_scope=CM.scope("BBROSE"))
    assert not ok
    assert any("ownership" in p for p in problems)


# === the pilot ===============================================================
def test_pilot_records_no_real_canonical_approval_or_permission_grant():
    p = run_c3b3.build_pilot()
    assert p["logo_pdf"]["canonical_approved"] is False
    assert p["logo6"]["canonical_approval_allowed"] is False
    assert p["incomplete_checklist"]["allowed"] is False
    assert p["canonical_grants_nothing"]["all_permissions_false"]
    assert p["jojia_third_party"]["all_permissions_false"]
    assert p["jojia_third_party"]["canonical_for_bbrose_allowed"] is False
    assert p["conflict"]["second_canonical_allowed"] is False
    lc = p["synthetic_master_lifecycle"]
    assert lc["before_expiry"]["retrieval"] is True
    assert lc["after_expiry"]["retrieval"] is False
    assert lc["after_expiry"]["status"] == C.EFF_RE_REVIEW_REQUIRED
    # every synthetic asset is clearly marked
    for e in p["events"]:
        assert "TEST_ONLY" in e["asset"] or "TEST_ONLY" in e["actor_id"]


def test_the_real_ledger_stays_empty():
    from tools.dip0c import ledger_store as LS
    report = LS.validate()
    assert report["counts"]["events"] == 0
    assert report["valid"]
