"""DIP-0C3b3 runner — canonical workflow, permission grants, expiry.

Everything here is SYNTHETIC. The real ledger stays empty: no real asset receives a
canonical approval or a permission grant, because fabricating one would look like a
decision a human actually made.

    python -m tools.dip0c.run_c3b3
"""
from __future__ import annotations

import sys
import time

from tools.dip0.integrity import compare, snapshot

from . import authz, canonical_master as CM, config as C, ledger as L
from . import ledger_store as LS, permissions as P
from . import rights_model as RM
from . import run_c3b2

PARSER = f"{C.TOOL_NAME}.run_c3b3/{C.TOOL_VERSION}"

EXAMPLES = L.LEDGER_ROOT / "examples_TEST_ONLY"
T0 = "2026-07-11T09:00:00+00:00"
T_GRANT = "2026-07-12T09:00:00+00:00"
EXPIRY = "2026-10-01T00:00:00+00:00"
BEFORE_EXPIRY = "2026-09-30T00:00:00+00:00"
AFTER_EXPIRY = "2026-10-02T00:00:00+00:00"


def _ev(asset, accepted=True):
    e = L.evidence(asset, evidence_type="CONTRACT", title="design contract",
                   submitted_by="TEST_ONLY_owner", actor_role=authz.BUSINESS_OWNER,
                   submitted_at=T0, confidence=0.9)
    if accepted:
        e["review_status"] = L.EV_ACCEPTED
        e["reviewed_by"] = "TEST_ONLY_legal"
        e["reviewed_at"] = T0
        e["content_hash"] = L.content_hash(e)
    return e


TECH_ID = "TEST_ONLY_brand_admin"
LEGAL_ID = "TEST_ONLY_legal"


def _full_checklist(tech_id=TECH_ID, legal_id=LEGAL_ID):
    """Every item answered — the technical half by the technical attester, the legal
    half by the legal one. Each attester answers only what they are competent for."""
    cl = CM.blank_checklist()
    for k in cl:
        by = tech_id if k in CM.TECHNICAL_ITEMS else legal_id
        cl[k] = {"result": True, "confirmed_by": by, "confirmed_at": T0,
                 "notes": "TEST_ONLY"}
    return cl


def _attestations(tech_id=TECH_ID, tech_role=authz.BRAND_ADMIN,
                  legal_id=LEGAL_ID, legal_role=authz.LEGAL_REVIEWER):
    return [
        CM.attestation(CM.ATT_TECHNICAL, actor_id=tech_id, actor_role=tech_role,
                       attested_at=T0, notes="TEST_ONLY"),
        CM.attestation(CM.ATT_LEGAL, actor_id=legal_id, actor_role=legal_role,
                       attested_at=T0, notes="TEST_ONLY"),
    ]


def build_pilot() -> dict:
    r: dict = {"refused": [], "events": []}

    # --- 1. logo.pdf: NOMINATED only. No canonical approval is recorded. --------
    r["logo_pdf"] = {
        "machine_state": CM.machine_canonical(C.BRAND_MASTER_CANDIDATE),
        "canonical_approved": False,
        "note": "machine NOMINATION only. No human approved it, so it is not the "
                "canonical master and it has no permissions.",
    }

    # --- 2. LOGO6.ai: contradiction present -> canonical approval REFUSED -------
    contradiction = L.contradiction_block(
        present=True,
        refs=["C3a: the artwork's live text reads 'global logistics services'"],
        acknowledged=False)
    ok, problems = CM.check_canonical_approval(
        "LOGO6.ai", requested_state=C.CANONICAL_BRAND_MASTER,
        actor_role=authz.BRAND_ADMIN, actor_id="TEST_ONLY_brand_admin",
        checklist=_full_checklist(), ownership_state=C.OWN_BBROSE_CONFIRMED,
        evidence_records=[_ev("LOGO6.ai")], reason="the business says it is ours",
        contradiction=contradiction, attestations=_attestations(),
        requested_scope=CM.scope("BBROSE"))
    r["logo6"] = {"canonical_approval_allowed": ok, "problems": problems}

    # ... and it IS allowed once the contradiction is acknowledged with a reason
    ack = L.contradiction_block(
        present=True, refs=["live text reads 'global logistics services'"],
        acknowledged=True,
        reason="TEST_ONLY: the mark was acquired from the prior owner; deed "
               "attached")
    ok2, _ = CM.check_canonical_approval(
        "LOGO6.ai", requested_state=C.CANONICAL_BRAND_MASTER,
        actor_role=authz.BRAND_ADMIN, actor_id="TEST_ONLY_brand_admin",
        checklist=_full_checklist(), ownership_state=C.OWN_BBROSE_CONFIRMED,
        evidence_records=[_ev("LOGO6.ai")], reason="acquired mark",
        contradiction=ack, attestations=_attestations(),
        requested_scope=CM.scope("BBROSE"))
    r["logo6"]["allowed_once_contradiction_acknowledged"] = ok2
    r["logo6"]["note"] = ("still NO real approval is recorded — this only shows "
                          "the gate opening when a human takes responsibility")

    # --- 2b. DUAL CONTROL: one BRAND_ADMIN cannot do this alone ------------------
    solo = "TEST_ONLY_solo_attempt.ai"
    dual: dict = {}
    # (a) one BRAND_ADMIN answers everything and attests both halves
    solo_cl = _full_checklist(tech_id=TECH_ID, legal_id=TECH_ID)
    okA, probA = CM.check_canonical_approval(
        solo, requested_state=C.CANONICAL_BRAND_MASTER,
        actor_role=authz.BRAND_ADMIN, actor_id=TECH_ID, checklist=solo_cl,
        ownership_state=C.OWN_BBROSE_CONFIRMED, evidence_records=[_ev(solo)],
        reason="I can do this myself",
        attestations=_attestations(tech_id=TECH_ID, legal_id=TECH_ID,
                                   legal_role=authz.LEGAL_REVIEWER),
        requested_scope=CM.scope("BBROSE"))
    dual["one_brand_admin_alone"] = {"allowed": okA, "problems": probA}

    # (b) technical attestation only
    okB, probB = CM.check_canonical_approval(
        solo, requested_state=C.CANONICAL_BRAND_MASTER,
        actor_role=authz.BRAND_ADMIN, actor_id=TECH_ID,
        checklist=_full_checklist(), ownership_state=C.OWN_BBROSE_CONFIRMED,
        evidence_records=[_ev(solo)], reason="the design is right",
        attestations=[_attestations()[0]], requested_scope=CM.scope("BBROSE"))
    dual["technical_only"] = {"allowed": okB, "problems": probB}

    # (c) legal attestation only
    okC, probC = CM.check_canonical_approval(
        solo, requested_state=C.CANONICAL_BRAND_MASTER,
        actor_role=authz.BRAND_ADMIN, actor_id=TECH_ID,
        checklist=_full_checklist(), ownership_state=C.OWN_BBROSE_CONFIRMED,
        evidence_records=[_ev(solo)], reason="the rights are clear",
        attestations=[_attestations()[1]], requested_scope=CM.scope("BBROSE"))
    dual["legal_only"] = {"allowed": okC, "problems": probC}

    # (d) two DISTINCT authorised actors -> satisfied
    okD, probD = CM.check_canonical_approval(
        solo, requested_state=C.CANONICAL_BRAND_MASTER,
        actor_role=authz.BRAND_ADMIN, actor_id=TECH_ID,
        checklist=_full_checklist(), ownership_state=C.OWN_BBROSE_CONFIRMED,
        evidence_records=[_ev(solo)], reason="two people signed for their half",
        attestations=_attestations(), requested_scope=CM.scope("BBROSE"))
    dual["two_distinct_actors"] = {"allowed": okD, "problems": probD}
    dual["note"] = ("separation is by ACTOR IDENTITY, not role. One person holding "
                    "both roles is still one person — and one person is exactly "
                    "what dual control exists to prevent.")
    r["dual_control"] = dual

    # --- 3. an INCOMPLETE checklist blocks approval ------------------------------
    partial = _full_checklist()
    partial["official_proportions_confirmed"]["result"] = None      # unanswered
    ok3, problems3 = CM.check_canonical_approval(
        "logo.pdf", requested_state=C.CANONICAL_BRAND_MASTER,
        actor_role=authz.BRAND_ADMIN, actor_id="TEST_ONLY_brand_admin",
        checklist=partial, ownership_state=C.OWN_BBROSE_CONFIRMED,
        evidence_records=[_ev("logo.pdf")], reason="looks right",
        attestations=_attestations(), requested_scope=CM.scope("BBROSE"))
    r["incomplete_checklist"] = {"allowed": ok3, "problems": problems3}

    # --- 4. SYNTHETIC BBROSE master: the full lifecycle --------------------------
    asset = "TEST_ONLY_synthetic_bbrose_master.ai"
    ev = _ev(asset)
    own_ref = "evt-TEST_ONLY-ownership"
    lic_ref = "evt-TEST_ONLY-license"

    ok4, problems4 = CM.check_canonical_approval(
        asset, requested_state=C.CANONICAL_BRAND_MASTER,
        actor_role=authz.BRAND_ADMIN, actor_id="TEST_ONLY_brand_admin",
        checklist=_full_checklist(), ownership_state=C.OWN_BBROSE_CONFIRMED,
        evidence_records=[ev], reason="passes the full checklist",
        attestations=_attestations(),
        requested_scope=CM.scope("BBROSE", markets=["EU"]))
    canon_evt = L.event(
        asset, event_type=L.CANONICAL_MASTER_APPROVED,
        actor_id="TEST_ONLY_brand_admin", actor_role=authz.BRAND_ADMIN,
        occurred_at=T0, decision_reason="passes the full checklist",
        evidence_refs=[ev["evidence_id"]],
        canonical=L.canonical_block(
            C.CANONICAL_BRAND_MASTER,
            scope=CM.scope("BBROSE", markets=["EU"]),
            checklist=_full_checklist(), attestations=_attestations(),
            version_or_date="v1 / 2026-07-11"))

    # CANONICAL != USABLE. Every permission is still false.
    eff_after_canonical = P.effective_permissions(asset, [canon_evt], now=T0)
    r["canonical_grants_nothing"] = {
        "canonical_approved": ok4,
        "problems": problems4,
        "all_permissions_false": all(
            not v["value"] for v in eff_after_canonical["permissions"].values()),
    }

    # ONE explicit permission grant — named, validated, with an expiry
    gok, gproblems = P.check_grant(
        "retrieval_allowed", actor_role=authz.LEGAL_REVIEWER,
        actor_id="TEST_ONLY_legal", ownership_state=C.OWN_BBROSE_CONFIRMED,
        license_state=C.LIC_APPROVED, evidence_records=[ev],
        reason="internal retrieval for design work", purpose="internal_design",
        ownership_decision_ref=own_ref, license_decision_ref=lic_ref)
    grant_evt = L.event(
        asset, event_type=L.PERMISSION_GRANTED, actor_id="TEST_ONLY_legal",
        actor_role=authz.LEGAL_REVIEWER, occurred_at=T_GRANT,
        decision_reason="internal retrieval for design work",
        evidence_refs=[ev["evidence_id"]], review_expiry=EXPIRY,
        permission=L.permission_block(
            "retrieval_allowed", previous_value=False, requested_value=True,
            purpose="internal_design", approved_brands=["BBROSE"],
            approved_markets=["EU"], validity_start=T_GRANT, review_expiry=EXPIRY,
            ownership_decision_ref=own_ref, license_decision_ref=lic_ref))

    events = [canon_evt, grant_evt]
    before = P.effective_permissions(asset, events, now=BEFORE_EXPIRY,
                                     brand="BBROSE", market="EU")
    after = P.effective_permissions(asset, events, now=AFTER_EXPIRY,
                                    brand="BBROSE", market="EU")
    out_of_scope = P.effective_permissions(asset, events, now=BEFORE_EXPIRY,
                                           brand="BBROSE", market="US")

    r["synthetic_master_lifecycle"] = {
        "grant_allowed": gok, "grant_problems": gproblems,
        "before_expiry": {
            "retrieval": before["permissions"]["retrieval_allowed"]["value"],
            "status": before["permissions"]["retrieval_allowed"]["status"]},
        "after_expiry": {
            "retrieval": after["permissions"]["retrieval_allowed"]["value"],
            "status": after["permissions"]["retrieval_allowed"]["status"]},
        "out_of_scope_market_US": {
            "retrieval": out_of_scope["permissions"]["retrieval_allowed"]["value"],
            "status": out_of_scope["permissions"]["retrieval_allowed"]["status"]},
        "expired_detected": P.detect_expired(asset, events, now=AFTER_EXPIRY),
        "note": "the grant event is UNTOUCHED by expiry. Only the EVALUATION "
                "changes, and it fails closed the moment the date passes — it "
                "does not wait for an audit event.",
    }
    r["events"] = [canon_evt, grant_evt]

    # --- 5. JOJIA LOGO.ai: third-party CONFIRMED, and STILL nothing is permitted --
    # The point is subtle and worth stating plainly: retrieval's prerequisites DO
    # admit THIRD_PARTY_CONFIRMED. Knowing whose logo it is settles a QUESTION; it
    # does not hand out a PERMISSION. Absent an explicit grant, every flag is false.
    jojia = "JOJIA LOGO.ai"
    jojia_eff = P.effective_permissions(jojia, [], now=T_GRANT, brand="BBROSE")
    # ...and it may not be canonical for BBROSE at all — it is not BBROSE's mark
    jok, jproblems = CM.check_canonical_approval(
        jojia, requested_state=C.CANONICAL_BRAND_MASTER,
        actor_role=authz.BRAND_ADMIN, actor_id="TEST_ONLY_brand_admin",
        checklist=_full_checklist(), ownership_state=C.OWN_THIRD_PARTY_CONFIRMED,
        evidence_records=[_ev(jojia)],
        reason="TEST_ONLY: it sits in our folders",
        attestations=_attestations(), requested_scope=CM.scope("BBROSE"))
    r["jojia_third_party"] = {
        "ownership_state": C.OWN_THIRD_PARTY_CONFIRMED,
        "retrieval_admits_third_party": C.OWN_THIRD_PARTY_CONFIRMED
            in P.PREREQUISITES["retrieval_allowed"]["requires_ownership"],
        "all_permissions_false": all(
            not v["value"] for v in jojia_eff["permissions"].values()),
        "canonical_for_bbrose_allowed": jok,
        "problems": jproblems,
        "note": "confirming WHOSE it is grants NOTHING. Third-party ownership is a "
                "settled question, not a permission — and a third party's mark can "
                "never be BBROSE's canonical master.",
    }

    # --- 6. CONFLICT: a second canonical for the same scope ----------------------
    existing = [{"asset": asset, "scope": CM.scope("BBROSE", markets=["EU"])}]
    conflict = CM.detect_conflict(CM.scope("BBROSE", markets=["EU"]), existing)
    ok5, problems5 = CM.check_canonical_approval(
        "TEST_ONLY_second_master.ai", requested_state=C.CANONICAL_BRAND_MASTER,
        actor_role=authz.BRAND_ADMIN, actor_id="TEST_ONLY_brand_admin",
        checklist=_full_checklist(), ownership_state=C.OWN_BBROSE_CONFIRMED,
        evidence_records=[_ev("TEST_ONLY_second_master.ai")],
        reason="we like this one better",
        attestations=_attestations(), existing_canonicals=existing,
        requested_scope=CM.scope("BBROSE", markets=["EU"]))
    r["conflict"] = {"machine_flag": conflict["state"],
                     "second_canonical_allowed": ok5, "problems": problems5,
                     "permitted_resolutions": conflict["permitted_resolutions"]}

    # --- 6. refusals ------------------------------------------------------------
    for role, action, label in (
            (authz.SYSTEM_ADMIN, authz.APPROVE_CANONICAL_MASTER,
             "SYSTEM_ADMIN selects the canonical master"),
            (authz.SYSTEM_ADMIN, authz.GRANT_PERMISSION,
             "SYSTEM_ADMIN grants a permission"),
            (authz.BRAND_ADMIN, authz.GRANT_LEGAL_PERMISSION,
             "BRAND_ADMIN grants redistribution")):
        try:
            authz.authorize(role, action, actor_id=f"TEST_ONLY_{role}")
        except authz.NotAuthorized as err:
            r["refused"].append({"attempt": label, "reason": str(err)})

    # the LEDGER itself refuses to record a single-actor canonical approval
    try:
        L.event(solo, event_type=L.CANONICAL_MASTER_APPROVED, actor_id=TECH_ID,
                actor_role=authz.BRAND_ADMIN, occurred_at=T0,
                decision_reason="solo", canonical=L.canonical_block(
                    C.CANONICAL_BRAND_MASTER, scope=CM.scope("BBROSE"),
                    checklist=solo_cl,
                    attestations=_attestations(tech_id=TECH_ID, legal_id=TECH_ID)))
    except L.LedgerError as err:
        r["refused"].append({
            "attempt": "LEDGER records a canonical approval attested by ONE person",
            "reason": str(err)})

    try:
        CM.machine_canonical(C.CANONICAL_BRAND_MASTER)
    except C.HumanOnlyStateViolation as err:
        r["refused"].append({"attempt": "machine declares CANONICAL_BRAND_MASTER",
                             "reason": str(err)})
    try:
        P.machine_may_revoke_only(False, True)
    except RM.MachineMayNotIncrease as err:
        r["refused"].append({"attempt": "machine turns a permission false->true",
                             "reason": str(err)})
    return r


def main(argv=None) -> int:
    t0 = time.monotonic()
    LS.ensure_dirs()
    before = snapshot()
    p = build_pilot()

    # synthetic records go to examples_TEST_ONLY/ — NEVER the real ledger
    out_bytes = 0
    for evt in p["events"]:
        rec = run_c3b2._mark(evt)
        out_bytes += run_c3b2._write(
            EXAMPLES / "events" / f"{rec['event_id']}.json", rec)
    out_bytes += run_c3b2._write(EXAMPLES / "c3b3_pilot.json",
                                 run_c3b2._mark({k: v for k, v in p.items()
                                                 if k != "events"}))
    report = LS.validate()
    LS.write_index()
    after = snapshot()

    lc = p["synthetic_master_lifecycle"]
    recon = {
        "slice": "DIP-0C3b3",
        "c3b2_commit": "bcac12fbf4ee2d35eca4215a72c9b15d5e90bd1e",
        "canonical_states": {
            "human_only": list(C.HUMAN_ONLY_CANONICAL),
            "machine_allowed": list(C.MACHINE_ALLOWED_CANONICAL)},
        "canonical_checklist_items": list(CM.CHECKLIST),
        "dual_control": {
            "applies_to": list(L.DUAL_CONTROL_EVENTS),
            "technical_attestation": {
                "items": list(CM.TECHNICAL_ITEMS),
                "roles": list(authz.POLICY[authz.ATTEST_CANONICAL_TECHNICAL])},
            "legal_attestation": {
                "items": list(CM.LEGAL_ITEMS),
                "roles": list(authz.POLICY[authz.ATTEST_CANONICAL_LEGAL])},
            "final_activation_roles":
                list(authz.POLICY[authz.APPROVE_CANONICAL_MASTER]),
            "rule": "technical_reviewer_id != legal_reviewer_id — separation is by "
                    "ACTOR IDENTITY, not by role",
        },
        "permission_flags": list(P.FLAGS),
        "permission_prerequisites": {
            f: {"requires_ownership": list(v["requires_ownership"]),
                "requires_license": list(v["requires_license"] or []),
                "legal_only": v["legal_only"]}
            for f, v in P.PREREQUISITES.items()},
        "authorization_policy": {a: list(rs) for a, rs in authz.POLICY.items()},
        "system_admin_forbidden": list(authz.SYSTEM_ADMIN_FORBIDDEN),
        "ledger_event_types": len(L.EVENT_TYPES),
        "real_ledger": {"events": report["counts"]["events"],
                        "note": "EMPTY. No real canonical approval, no real "
                                "permission grant."},
        "ledger_valid": report["valid"],
        "pilot": {
            "logo_pdf_nominated_not_approved":
                p["logo_pdf"]["canonical_approved"] is False,
            "logo6_canonical_refused":
                p["logo6"]["canonical_approval_allowed"] is False,
            "logo6_allowed_once_acknowledged":
                p["logo6"]["allowed_once_contradiction_acknowledged"],
            "incomplete_checklist_blocks":
                p["incomplete_checklist"]["allowed"] is False,
            "canonical_grants_no_permission":
                p["canonical_grants_nothing"]["all_permissions_false"],
            "dual_control": {
                "one_brand_admin_alone_refused":
                    p["dual_control"]["one_brand_admin_alone"]["allowed"] is False,
                "technical_only_refused":
                    p["dual_control"]["technical_only"]["allowed"] is False,
                "legal_only_refused":
                    p["dual_control"]["legal_only"]["allowed"] is False,
                "two_distinct_actors_allowed":
                    p["dual_control"]["two_distinct_actors"]["allowed"],
            },
            "third_party_confirmed_grants_no_permission":
                p["jojia_third_party"]["all_permissions_false"],
            "third_party_not_canonical_for_bbrose":
                p["jojia_third_party"]["canonical_for_bbrose_allowed"] is False,
            "grant_allowed": lc["grant_allowed"],
            "retrieval_before_expiry": lc["before_expiry"],
            "retrieval_after_expiry": lc["after_expiry"],
            "out_of_scope_denied": lc["out_of_scope_market_US"],
            "second_canonical_refused":
                p["conflict"]["second_canonical_allowed"] is False,
            "conflict_flag": p["conflict"]["machine_flag"],
        },
        "refused_attempts": p["refused"],
        "integrity": {"materials": compare(before, after)},
        "runtime_seconds": round(time.monotonic() - t0, 2),
        "output_bytes": out_bytes,
    }
    run_c3b2._write(C.MILESTONE_OUTPUT_ROOT / "c3b3_reconciliation.json", recon)

    ok = (report["valid"]
          and recon["integrity"]["materials"]["unchanged"]
          and recon["real_ledger"]["events"] == 0
          and recon["pilot"]["logo6_canonical_refused"]
          and recon["pilot"]["incomplete_checklist_blocks"]
          and recon["pilot"]["canonical_grants_no_permission"]
          and all(v for k, v in recon["pilot"]["dual_control"].items())
          and recon["pilot"]["third_party_confirmed_grants_no_permission"]
          and recon["pilot"]["third_party_not_canonical_for_bbrose"]
          and recon["pilot"]["second_canonical_refused"]
          and recon["pilot"]["retrieval_after_expiry"]["retrieval"] is False)
    _print(recon)
    if not ok:
        print("\nFAILED: a C3b3 invariant broke", file=sys.stderr)
        return 1
    return 0


def _print(r: dict) -> None:
    p = r["pilot"]
    print("DIP-0C3b3 — canonical workflow + permissions")
    print(f"  canonical:  {len(r['canonical_states']['human_only'])} human-only, "
          f"{len(r['canonical_states']['machine_allowed'])} machine-allowed")
    print(f"  checklist:  {len(r['canonical_checklist_items'])} items (an "
          f"UNANSWERED item blocks approval)")
    print(f"  permissions:{len(r['permission_flags'])} flags, each with its OWN "
          f"prerequisites")
    print(f"  real ledger: {r['real_ledger']['events']} events (EMPTY)")
    print("  pilot:")
    print(f"    logo.pdf nominated, NOT approved:     {p['logo_pdf_nominated_not_approved']}")
    print(f"    LOGO6.ai canonical REFUSED:           {p['logo6_canonical_refused']}")
    print(f"      ...allowed once acknowledged:       {p['logo6_allowed_once_acknowledged']}")
    print(f"    incomplete checklist blocks:          {p['incomplete_checklist_blocks']}")
    print(f"    CANONICAL GRANTS NO PERMISSION:       {p['canonical_grants_no_permission']}")
    d = p["dual_control"]
    print("    DUAL CONTROL:")
    print(f"      one BRAND_ADMIN alone REFUSED:      {d['one_brand_admin_alone_refused']}")
    print(f"      technical attestation only REFUSED: {d['technical_only_refused']}")
    print(f"      legal attestation only REFUSED:     {d['legal_only_refused']}")
    print(f"      two DISTINCT actors allowed:        {d['two_distinct_actors_allowed']}")
    print("    JOJIA third-party CONFIRMED, still")
    print(f"      no permission:                      {p['third_party_confirmed_grants_no_permission']}")
    print(f"      not canonical for BBROSE:           {p['third_party_not_canonical_for_bbrose']}")
    print(f"    retrieval before expiry:              {p['retrieval_before_expiry']}")
    print(f"    retrieval AFTER expiry (fail closed): {p['retrieval_after_expiry']}")
    print(f"    out-of-scope market denied:           {p['out_of_scope_denied']}")
    print(f"    second canonical REFUSED:             {p['second_canonical_refused']} "
          f"(flag={p['conflict_flag']})")
    print(f"  refused:    {len(r['refused_attempts'])} illegal attempts")
    for a in r["refused_attempts"]:
        print(f"     - {a['attempt']}")
    print(f"  integrity:  materials_unchanged="
          f"{r['integrity']['materials']['unchanged']}")
    print(f"  runtime:    {r['runtime_seconds']}s")


if __name__ == "__main__":
    raise SystemExit(main())
