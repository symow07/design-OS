"""DIP-0C3b2 runner — schemas, templates, TEST_ONLY examples, ledger validation.

**The real ledger starts EMPTY.** No ownership is confirmed, no licence is approved,
nothing is granted. Fabricating a real approval would be worse than having none, so
the synthetic records live in a separate `examples_TEST_ONLY/` tree, every one of
them flagged `TEST_ONLY: true`, and the read model never loads them.

    python -m tools.dip0c.run_c3b2
"""
from __future__ import annotations

import json
import sys
import time

from tools.dip0.integrity import compare, snapshot
from tools.dip0.report import json_default

from . import authz, config as C, ledger as L, ledger_store as LS
from . import rights_model as RM

PARSER = f"{C.TOOL_NAME}.run_c3b2/{C.TOOL_VERSION}"

EXAMPLES_DIR = L.LEDGER_ROOT / "examples_TEST_ONLY"
TEMPLATES_DIR = L.LEDGER_ROOT / "templates"
SCHEMAS_DIR = L.LEDGER_ROOT / "schemas"

PILOT = ["logo.pdf", "LOGO6.ai", "BBROSE.pdf", "BBROSE-1.pdf",
         "ATC LOGO.ai", "JOJIA LOGO.ai"]

T = "2026-07-11T09:00:00+00:00"


def _mark(rec: dict) -> dict:
    rec = dict(rec)
    rec["TEST_ONLY"] = True
    rec["WARNING"] = ("SYNTHETIC EXAMPLE. This is NOT a real decision and confers "
                      "NOTHING. It exists to exercise the schema and the "
                      "validator.")
    return rec


def build_examples() -> dict:
    """Synthetic records that exercise every rule — none of them is a real
    approval."""
    out = {"assertions": [], "evidence": [], "events": [],
           "refused": []}

    # 1. The business asserts LOGO6.ai is theirs. It is a BELIEF, and grants nothing.
    a = L.assertion(
        "LOGO6.ai", asserted_state=C.OWN_BUSINESS_ASSERTED_BBROSE,
        asserted_by="TEST_ONLY_business_owner", actor_role=authz.BUSINESS_OWNER,
        asserted_at=T, notes="the business believes this is the BBROSE logo")
    out["assertions"].append(_mark(a))

    # 2. Evidence is SUBMITTED — and submission is not acceptance.
    e_sub = L.evidence(
        "LOGO6.ai", evidence_type="BUSINESS_OWNER_DECLARATION",
        title="verbal declaration of ownership",
        submitted_by="TEST_ONLY_business_owner", actor_role=authz.BUSINESS_OWNER,
        submitted_at=T, description="the owner states the logo is BBROSE's",
        confidence=0.3, ownership_relevance="CLAIMED_BBROSE")
    out["evidence"].append(_mark(e_sub))

    # 3. A DESIGN_REVIEWER may review evidence — but may NOT confirm ownership.
    try:
        authz.authorize(authz.DESIGN_REVIEWER, authz.CONFIRM_OWNERSHIP,
                        actor_id="TEST_ONLY_designer")
    except authz.NotAuthorized as err:
        out["refused"].append({
            "attempt": "DESIGN_REVIEWER confirms ownership",
            "refused_because": "NotAuthorized", "reason": str(err)})

    # 4. A SYSTEM_ADMIN may revoke — but may NOT approve a licence.
    try:
        authz.authorize(authz.SYSTEM_ADMIN, authz.APPROVE_LICENSE,
                        actor_id="TEST_ONLY_admin")
    except authz.NotAuthorized as err:
        out["refused"].append({
            "attempt": "SYSTEM_ADMIN approves a licence",
            "refused_because": "NotAuthorized",
            "reason": str(err)})

    # 5. THE LOGO6.ai CASE. A LEGAL_REVIEWER tries to confirm BBROSE ownership on
    #    the strength of the assertion alone. It must FAIL: an assertion is a
    #    belief, the evidence is unreviewed, and a contradiction is unacknowledged.
    contradiction = L.contradiction_block(
        present=True,
        refs=["C3a: live text of LOGO6.ai reads 'global logistics services'"],
        acknowledged=False)
    ok, problems = L.check_confirmation(
        "LOGO6.ai", requested_state=C.OWN_BBROSE_CONFIRMED,
        actor_role=authz.LEGAL_REVIEWER, actor_id="TEST_ONLY_legal",
        current_state=C.OWN_UNKNOWN, axis=RM.AXIS_OWNERSHIP,
        evidence_records=[e_sub], reason="the business says so",
        contradiction=contradiction)
    out["logo6_confirmation_attempt"] = {
        "allowed": ok,
        "problems": problems,
        "note": "the business believes it owns LOGO6.ai; the artwork's own live "
                "text reads 'global logistics services'. Confirmation is REFUSED.",
    }

    # 6. A clean, well-formed decision on a DIFFERENT asset, to prove the happy path
    #    exists — third-party status for JOJIA, which C3a read from its live text.
    e_ok = L.evidence(
        "JOJIA LOGO.ai", evidence_type="SOURCE_FILE",
        title="live text of the artwork reads 'Jojiia'",
        submitted_by="TEST_ONLY_designer", actor_role=authz.DESIGN_REVIEWER,
        submitted_at=T, description="DIP-0C3a extracted the wordmark directly",
        confidence=0.85, ownership_relevance="THIRD_PARTY")
    e_ok["review_status"] = L.EV_ACCEPTED
    e_ok["reviewed_by"] = "TEST_ONLY_legal"
    e_ok["reviewed_at"] = T
    e_ok["content_hash"] = L.content_hash(e_ok)
    out["evidence"].append(_mark(e_ok))

    ok2, problems2 = L.check_confirmation(
        "JOJIA LOGO.ai", requested_state=C.OWN_THIRD_PARTY_CONFIRMED,
        actor_role=authz.LEGAL_REVIEWER, actor_id="TEST_ONLY_legal",
        current_state=C.OWN_THIRD_PARTY_UNCONFIRMED, axis=RM.AXIS_OWNERSHIP,
        evidence_records=[e_ok],
        reason="the wordmark reads 'Jojiia'; this is not BBROSE artwork")
    out["jojia_confirmation_attempt"] = {"allowed": ok2, "problems": problems2}
    if ok2:
        evt = L.event(
            "JOJIA LOGO.ai", event_type=L.THIRD_PARTY_CONFIRMED,
            actor_id="TEST_ONLY_legal", actor_role=authz.LEGAL_REVIEWER,
            occurred_at=T, previous_state=C.OWN_THIRD_PARTY_UNCONFIRMED,
            requested_state=C.OWN_THIRD_PARTY_CONFIRMED,
            decision_reason="the wordmark reads 'Jojiia'; not BBROSE artwork",
            evidence_refs=[e_ok["evidence_id"]])
        out["events"].append(_mark(evt))
    return out


def blank_templates() -> dict:
    return {
        "event.template.json": {
            "schema_version": L.SCHEMA_VERSION,
            "event_id": "<generated>", "event_type": f"<one of {list(L.EVENT_TYPES)}>",
            "asset": "<relative path or asset id>",
            "actor_id": "<who>", "actor_role": f"<one of {list(authz.ROLES)}>",
            "occurred_at": "<ISO-8601>", "recorded_at": "<generated>",
            "previous_state": None, "requested_state": None,
            "decision_reason": "<REQUIRED for a decision>",
            "evidence_refs": [], "assertion_refs": [],
            "supersedes_event_id": None, "review_expiry": None,
            "repository_commit": None,
            "contradiction": L.contradiction_block(),
            "notes": "", "content_hash": "<generated>",
        },
        "evidence.template.json": {
            "schema_version": L.SCHEMA_VERSION,
            "evidence_id": "<generated>",
            "evidence_type": f"<one of {list(L.EVIDENCE_TYPES)}>",
            "asset": "<relative path>", "title": "", "description": "",
            "submitted_by": "", "actor_role": "", "submitted_at": "<ISO-8601>",
            "reference": "<path or URI — sensitive files by REFERENCE, never "
                         "committed>",
            "file_hash": None, "validity_start": None, "validity_end": None,
            "confidence": 0.0, "reviewed_by": None, "reviewed_at": None,
            "review_status": L.EV_SUBMITTED, "review_notes": None,
            "ownership_relevance": "UNKNOWN", "license_relevance": "UNKNOWN",
            "restrictions_observed": [], "supersedes_evidence_id": None,
            "content_hash": "<generated>",
        },
        "assertion.template.json": {
            "schema_version": L.SCHEMA_VERSION,
            "assertion_id": "<generated>", "asset": "<relative path>",
            "asserted_state": C.OWN_BUSINESS_ASSERTED_BBROSE,
            "asserted_by": "", "actor_role": authz.BUSINESS_OWNER,
            "asserted_at": "<ISO-8601>", "assertion_notes": "",
            "supporting_refs": [], "withdrawn_by": None, "withdrawn_at": None,
            "withdrawal_reason": None, "supersedes_assertion_id": None,
            "is_confirmation": False, "grants_permissions": False,
            "content_hash": "<generated>",
        },
    }


def schemas() -> dict:
    return {
        "schema_version": L.SCHEMA_VERSION,
        "event_types": list(L.EVENT_TYPES),
        "decision_events": list(L.DECISION_EVENTS),
        "corrective_events": list(L.CORRECTIVE_EVENTS),
        "event_requires_action": dict(L.EVENT_ACTION),
        "evidence_types": list(L.EVIDENCE_TYPES),
        "evidence_statuses": list(L.EVIDENCE_STATUSES),
        "hash_excluded_fields": list(L.HASH_EXCLUDED),
        "authorization_policy": authz.policy_document(),
        "rules": [
            "the immutable record FILES are the source of truth; index.json is "
            "generated and is a deletion tripwire, never authoritative",
            "a record is never edited or deleted; a correction is a NEW "
            "superseding event",
            "evidence status NEVER automatically changes ownership or licence",
            "a business assertion is a BELIEF: it confirms nothing and grants "
            "nothing",
            "git authorship is provenance, not authorisation",
            "sensitive evidence is referenced by path/hash, never committed",
        ],
    }


def _write(path, obj):
    C.assert_output_safe(path)
    C.assert_not_frozen_milestone(path)          # fail closed on a frozen-tree write
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2,
                               default=json_default), encoding="utf-8")
    return len(json.dumps(obj, default=json_default).encode("utf-8"))


def main(argv=None) -> int:
    t0 = time.monotonic()
    LS.ensure_dirs()
    before = snapshot()

    out_bytes = 0
    out_bytes += _write(SCHEMAS_DIR / "ledger_schemas.json", schemas())
    for name, tpl in blank_templates().items():
        out_bytes += _write(TEMPLATES_DIR / name, tpl)

    ex = build_examples()
    for kind in ("assertions", "evidence", "events"):
        for rec in ex[kind]:
            idkey = {"assertions": "assertion_id", "evidence": "evidence_id",
                     "events": "event_id"}[kind]
            out_bytes += _write(EXAMPLES_DIR / kind / f"{rec[idkey]}.json", rec)
    out_bytes += _write(EXAMPLES_DIR / "refused_attempts.json", ex["refused"])

    # the REAL ledger stays empty — validate it and generate its index
    report = LS.validate()
    LS.write_index()
    after = snapshot()

    integrity = {"materials": compare(before, after),
                 "no_output_under_source": {
                     "ok": C.SOURCE_ROOT.resolve() not in
                     C.DOCS_ROOT.resolve().parents}}

    recon = {
        "slice": "DIP-0C3b2",
        "c3b1_commit": "4e67309e5ded48a7720985a32e7a87434c24d17c",
        "schema_version": L.SCHEMA_VERSION,
        "pilot": PILOT,
        # repo-relative when writing under the repo (the committed regeneration); a temp
        # output root (ordinary tests) is recorded absolute rather than crashing
        "ledger_root": (str(L.LEDGER_ROOT.relative_to(C.REPO_ROOT))
                        if C.REPO_ROOT in L.LEDGER_ROOT.parents
                        else str(L.LEDGER_ROOT)),
        "real_ledger": {
            "events": report["counts"]["events"],
            "evidence": report["counts"]["evidence"],
            "assertions": report["counts"]["assertions"],
            "note": "EMPTY BY DESIGN. No ownership is confirmed, no licence is "
                    "approved, nothing is granted. Fabricating a real approval "
                    "would be worse than having none.",
        },
        "ledger_valid": report["valid"],
        "validator_findings": {k: len(v) for k, v in report["findings"].items()},
        "event_types": len(L.EVENT_TYPES),
        "evidence_types": len(L.EVIDENCE_TYPES),
        "evidence_statuses": list(L.EVIDENCE_STATUSES),
        "roles": list(authz.ROLES),
        "actions": list(authz.ACTIONS),
        "authorization_policy": {a: list(r) for a, r in authz.POLICY.items()},
        "transition_matrix_is_authoritative": True,
        "machine_legal_transitions": {
            axis: len(RM.MACHINE_TRANSITIONS[axis])
            for axis in RM.MACHINE_TRANSITIONS},
        "examples_TEST_ONLY": {
            "assertions": len(ex["assertions"]),
            "evidence": len(ex["evidence"]),
            "events": len(ex["events"]),
            "refused_attempts": len(ex["refused"]),
            "logo6_confirmation_refused":
                ex["logo6_confirmation_attempt"]["allowed"] is False,
            "logo6_problems": ex["logo6_confirmation_attempt"]["problems"],
            "jojia_confirmation_allowed":
                ex["jojia_confirmation_attempt"]["allowed"],
        },
        "permissions_still_all_false": all(
            RM.permissions()[f] is False for f in RM.PERMISSION_FLAGS),
        "integrity": integrity,
        "runtime_seconds": round(time.monotonic() - t0, 2),
        "output_bytes": out_bytes,
    }
    _write(C.MILESTONE_OUTPUT_ROOT / "c3b2_reconciliation.json", recon)

    ok = (report["valid"] and integrity["materials"]["unchanged"]
          and recon["permissions_still_all_false"]
          and recon["examples_TEST_ONLY"]["logo6_confirmation_refused"])
    _print(recon)
    if not ok:
        print("\nFAILED: ledger invalid or an invariant broke", file=sys.stderr)
        return 1
    return 0


def _print(r: dict) -> None:
    print(f"DIP-0C3b2 — decision ledger {r['schema_version']}")
    print(f"  real ledger: events={r['real_ledger']['events']} "
          f"evidence={r['real_ledger']['evidence']} "
          f"assertions={r['real_ledger']['assertions']} (EMPTY BY DESIGN)")
    bad = {k: v for k, v in r["validator_findings"].items() if v}
    print(f"  valid:      {r['ledger_valid']} — {bad or 'no findings'}")
    print(f"  events:     {r['event_types']} types | evidence: "
          f"{r['evidence_types']} types, {len(r['evidence_statuses'])} statuses")
    print(f"  roles:      {r['roles']}")
    print(f"  machine transitions (explicit matrix): "
          f"{r['machine_legal_transitions']}")
    ex = r["examples_TEST_ONLY"]
    print(f"  TEST_ONLY:  {ex['assertions']} assertions, {ex['evidence']} evidence, "
          f"{ex['events']} events, {ex['refused_attempts']} refused attempts")
    print(f"  LOGO6.ai confirmation REFUSED: {ex['logo6_confirmation_refused']}")
    for p in ex["logo6_problems"]:
        print(f"     - {p[:96]}")
    print(f"  JOJIA third-party confirmation allowed: "
          f"{ex['jojia_confirmation_allowed']}")
    print(f"  permissions all false: {r['permissions_still_all_false']}")
    print(f"  integrity:  materials_unchanged="
          f"{r['integrity']['materials']['unchanged']}")
    print(f"  runtime:    {r['runtime_seconds']}s")


if __name__ == "__main__":
    raise SystemExit(main())
