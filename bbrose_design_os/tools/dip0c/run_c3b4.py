"""DIP-0C3b4 runner — conflicts, atomic resolution, queues, reports.

SYNTHETIC. The real ledger stays empty. Every scenario runs on TEST_ONLY assets and
in-memory events; the compound writer is exercised against a scratch directory, never
against the committed decision ledger.

    python -m tools.dip0c.run_c3b4
"""
from __future__ import annotations

import sys
import time

from tools.dip0.integrity import compare, snapshot

from . import authz
from . import canonical_master as CM
from . import canonical_read as CR
from . import canonical_scope as S
from . import compound as CP
from . import config as C
from . import conflict_resolution as RES
from . import ledger as L
from . import ledger_store as LS
from . import review_c3b4 as RV
from . import run_c3b2
from . import taxonomy as TX

PARSER = f"{C.TOOL_NAME}.run_c3b4/{C.TOOL_VERSION}"
EXAMPLES = L.LEDGER_ROOT / "examples_TEST_ONLY"

T = "2026-07-14T09:00:00+00:00"
T2 = "2026-07-14T12:00:00+00:00"
NOW = "2026-07-14T13:00:00+00:00"
TECH, LEGAL = "TEST_ONLY_brand_admin", "TEST_ONLY_legal"


def _atts(tech=TECH, legal=LEGAL):
    return [CM.attestation(CM.ATT_TECHNICAL, actor_id=tech,
                           actor_role=authz.BRAND_ADMIN, attested_at=T),
            CM.attestation(CM.ATT_LEGAL, actor_id=legal,
                           actor_role=authz.LEGAL_REVIEWER, attested_at=T)]


def _cl(tech=TECH, legal=LEGAL):
    cl = CM.blank_checklist()
    for k in cl:
        by = tech if k in CM.TECHNICAL_ITEMS else legal
        cl[k] = {"result": True, "confirmed_by": by, "confirmed_at": T,
                 "notes": "TEST_ONLY"}
    return cl


def _activate(asset, scope, at=T):
    return L.event(asset, event_type=L.CANONICAL_MASTER_APPROVED, actor_id=TECH,
                   actor_role=authz.BRAND_ADMIN, occurred_at=at,
                   decision_reason="TEST_ONLY activation",
                   canonical=L.canonical_block(
                       C.CANONICAL_BRAND_MASTER, scope=scope, checklist=_cl(),
                       attestations=_atts(), version_or_date=at))


def build_pilot() -> dict:
    r: dict = {"refused": []}
    sc = lambda **k: S.scope("BBROSE", **k)                          # noqa: E731

    eu = _activate("TEST_ONLY_master_eu.ai", sc(markets=["EU"]))
    us = _activate("TEST_ONLY_master_us.ai", sc(markets=["US"]))
    fr = _activate("TEST_ONLY_master_fr.ai", sc(markets=["FR"]), at=T2)
    atl = _activate("TEST_ONLY_master_atlantis.ai", sc(markets=["ATLANTIS"]), at=T2)

    # --- 1. disjoint scopes coexist. Two masters is not automatically a bug. ----
    r["disjoint"] = {"assets": ["EU", "US"],
                     "conflicts": len(CR.conflicts([eu, us])),
                     "note": "FR vs DE, EU vs US: the taxonomy PROVES they cannot "
                             "collide, so both masters stay active."}

    # --- 2. EU vs FR: a PROVEN overlap -> CANONICAL_CONFLICT --------------------
    conf = CR.conflicts([eu, us, fr])
    r["proven_conflict"] = {
        "count": len(conf), "assets": conf[0]["assets"],
        "relation": conf[0]["relation"], "proven": conf[0]["proven"],
        "reason": conf[0]["reason"],
    }

    # --- 3. the conflict is SCOPE-LOCAL ----------------------------------------
    q_us = CR.canonical_for([eu, us, fr], sc(markets=["US"]))
    q_fr = CR.canonical_for([eu, us, fr], sc(markets=["FR"]))
    r["scope_local"] = {
        "us_still_usable": q_us["usable"], "us_master": q_us["asset"],
        "fr_blocked": q_fr["state"],
        "note": "a fight over France does not invalidate the master approved for "
                "the United States. Being maximally destructive is not being safe.",
    }

    # --- 4. an UNKNOWN token fails closed --------------------------------------
    unk = CR.conflicts([eu, atl])
    r["uncertain"] = {
        "count": len(unk),
        "relation": unk[0]["relation"] if unk else None,
        "proven": unk[0]["proven"] if unk else None,
        "note": "ATLANTIS is not in the taxonomy. 'We cannot tell' is not 'they do "
                "not collide', so it is treated as a conflict and queued for review.",
    }

    # --- 5. ATOMIC supersession -------------------------------------------------
    _, sup = RES.resolve(
        RES.SUPERSEDE_INCUMBENT, incumbent_event_id=eu["event_id"],
        existing_events=[eu, us], actor_id=TECH, actor_role=authz.BRAND_ADMIN,
        occurred_at=T2, reason="TEST_ONLY: a new EU master supersedes the old",
        new_asset="TEST_ONLY_master_eu_v2.ai", new_scope=sc(markets=["EU"]),
        attestations=_atts(), checklist=_cl(), dry_run=True)
    post = [eu, us] + sup["constituents"]
    r["supersession"] = {
        "compound_event_id": sup["compound_event_id"],
        "constituents": [e["event_type"] for e in sup["constituents"]],
        "post_state": sorted((m["asset"], m["lifecycle"]) for m in CR.masters(post)),
        "post_conflicts": len(CR.conflicts(post)),
        "chain": CR._chains(CR.masters(post)),
        "canonical_for_eu": CR.canonical_for(post, sc(markets=["EU"]))["asset"],
        "note": "the incumbent's retirement and the successor's activation live in "
                "ONE file. There is no instant at which two masters hold the EU.",
    }

    # --- 6. narrowing reduces; widening is a new approval -----------------------
    _, nar = RES.resolve(
        RES.NARROW_INCUMBENT_SCOPE, incumbent_event_id=eu["event_id"],
        existing_events=[eu], actor_id=TECH, actor_role=authz.BRAND_ADMIN,
        occurred_at=T2, reason="TEST_ONLY: EU is too broad; France only",
        narrowed_scope=sc(markets=["FR"]), dry_run=True)
    r["narrowing"] = {
        "before": eu["canonical"]["scope"]["markets"]["tokens"],
        "after": CR.masters([eu] + nar["constituents"])[0]["scope"]["markets"]["tokens"],
        "event": nar["constituents"][0]["event_type"],
    }

    # --- 7. every illegal resolution, refused; NOTHING written ------------------
    errs = (CP.CompoundError, RES.ResolutionError, L.LedgerError,
            authz.NotAuthorized, C.HumanOnlyStateViolation)
    attempts = [
        ("supersede with no legal attestation", lambda: RES.resolve(
            RES.SUPERSEDE_INCUMBENT, incumbent_event_id=eu["event_id"],
            existing_events=[eu], actor_id=TECH, actor_role=authz.BRAND_ADMIN,
            occurred_at=T2, reason="r", new_asset="x.ai",
            new_scope=sc(markets=["EU"]), attestations=[_atts()[0]],
            checklist=_cl())),
        ("supersede where one person attests both halves", lambda: RES.resolve(
            RES.SUPERSEDE_INCUMBENT, incumbent_event_id=eu["event_id"],
            existing_events=[eu], actor_id=TECH, actor_role=authz.BRAND_ADMIN,
            occurred_at=T2, reason="r", new_asset="x.ai",
            new_scope=sc(markets=["EU"]), attestations=_atts(TECH, TECH),
            checklist=_cl())),
        ("widening disguised as a narrowing", lambda: RES.resolve(
            RES.NARROW_INCUMBENT_SCOPE, incumbent_event_id=eu["event_id"],
            existing_events=[eu], actor_id=TECH, actor_role=authz.BRAND_ADMIN,
            occurred_at=T2, reason="r", narrowed_scope=sc(markets=["EU", "US"]))),
        ("SYSTEM_ADMIN supersedes a master", lambda: RES.resolve(
            RES.SUPERSEDE_INCUMBENT, incumbent_event_id=eu["event_id"],
            existing_events=[eu], actor_id="sa", actor_role=authz.SYSTEM_ADMIN,
            occurred_at=T2, reason="r", new_asset="x.ai",
            new_scope=sc(markets=["EU"]), attestations=_atts(), checklist=_cl())),
        ("a variant reclassified INTO the canonical master", lambda: RES.resolve(
            RES.RECLASSIFY_AS_VARIANT, incumbent_event_id=eu["event_id"],
            existing_events=[eu], actor_id=TECH, actor_role=authz.BRAND_ADMIN,
            occurred_at=T2, reason="r", variant_state=C.CANONICAL_BRAND_MASTER)),
        ("a resolution with no reason", lambda: RES.resolve(
            RES.DEPRECATE_INCUMBENT, incumbent_event_id=eu["event_id"],
            existing_events=[eu], actor_id=TECH, actor_role=authz.BRAND_ADMIN,
            occurred_at=T2, reason="   ")),
        ("a machine resolving a conflict", RES.machine_may_not_resolve),
    ]
    before_files = len(CP.load_all())
    for label, fn in attempts:
        try:
            fn()
            r["refused"].append({"attempt": label, "reason": "NOT REFUSED — BUG"})
        except errs as e:
            line = [x for x in str(e).splitlines() if x.strip()][-1].strip()
            r["refused"].append({"attempt": label, "reason": line})
    r["nothing_written_on_failure"] = len(CP.load_all()) == before_files

    # --- 8. queues --------------------------------------------------------------
    events = [eu, us, fr, atl]
    q1 = RV.build(events, now=NOW,
                  nominations=[{"asset": "logo.pdf",
                                "state": C.BRAND_MASTER_CANDIDATE}],
                  third_party=[{"asset": "JOJIA LOGO.ai",
                                "reason": "third-party mark in BBROSE folders"}],
                  contradictions=[{"asset": "LOGO6.ai",
                                   "reason": "live text reads 'global logistics "
                                             "services'"}])
    q2 = RV.build(events, now=NOW,
                  nominations=[{"asset": "logo.pdf",
                                "state": C.BRAND_MASTER_CANDIDATE}],
                  third_party=[{"asset": "JOJIA LOGO.ai",
                                "reason": "third-party mark in BBROSE folders"}],
                  contradictions=[{"asset": "LOGO6.ai",
                                   "reason": "live text reads 'global logistics "
                                             "services'"}])
    r["queues"] = {
        "totals": q1["totals"], "total_items": q1["total_items"],
        "critical": q1["critical"],
        "never_batch_approved": q1["never_batch_approved"],
        "deterministic": q1 == q2,
    }
    r["queue_detail"] = q1

    # --- 9. no permission is activated by any of this ---------------------------
    proj = CR.project(post, now=NOW)
    r["no_permission_granted"] = all(
        not p["value"]
        for eff in proj["effective_permissions"].values()
        for p in eff["permissions"].values())
    r["projection"] = {
        "active": [m["asset"] for m in proj["active"]],
        "superseded": [m["asset"] for m in proj["superseded"]],
        "deprecated": [m["asset"] for m in proj["deprecated"]],
        "quarantined": [m["asset"] for m in proj["quarantined"]],
        "conflict_free": proj["conflict_free"],
    }
    return r


def main(argv=None) -> int:
    t0 = time.monotonic()
    LS.ensure_dirs()
    before = snapshot()
    p = build_pilot()

    out_bytes = run_c3b2._write(EXAMPLES / "c3b4_pilot.json",
                                run_c3b2._mark({k: v for k, v in p.items()
                                                if k != "queue_detail"}))
    out_bytes += run_c3b2._write(C.MILESTONE_OUTPUT_ROOT / "c3b4_review_queue_summary.json",
                                 p["queue_detail"])
    ledger_report = LS.validate()
    compound_report = CP.validate_committed()
    after = snapshot()

    tax = TX.load()
    recon = {
        "slice": "DIP-0C3b4",
        "c3b3_commit": "8685f3f",
        "taxonomy": {
            "schema_version": tax["schema_version"],
            "taxonomy_version": tax["taxonomy_version"],
            "tokens_per_axis": {ax: len(tax["axes"][ax]["tokens"]) for ax in TX.AXES},
            "closed_world": {ax: tax["axes"][ax]["closed_world"] for ax in TX.AXES},
        },
        "scope_relations": list(TX.RELATIONS),
        "resolution_actions": list(RES.ACTIONS),
        "lifecycle_states": list(CR.LIFECYCLE),
        "pilot": {
            "disjoint_masters_coexist": p["disjoint"]["conflicts"] == 0,
            "proven_conflict_detected": p["proven_conflict"]["count"] == 1,
            "conflict_is_scope_local": p["scope_local"]["us_still_usable"],
            "unknown_token_fails_closed": (p["uncertain"]["count"] == 1
                                           and not p["uncertain"]["proven"]),
            "supersession_atomic": p["supersession"]["post_conflicts"] == 0,
            "supersession_post_state": p["supersession"]["post_state"],
            "narrowing_reduces": p["narrowing"]["after"] == ["FR"],
            "nothing_written_on_failure": p["nothing_written_on_failure"],
            "no_permission_granted": p["no_permission_granted"],
            "queues_deterministic": p["queues"]["deterministic"],
            "queue_totals": p["queues"]["totals"],
        },
        "refused_attempts": p["refused"],
        "real_ledger": {"events": ledger_report["counts"]["events"],
                        "compound_events": compound_report["compound_events"],
                        "note": "EMPTY. No real conflict was resolved."},
        "ledger_valid": ledger_report["valid"],
        "compound_valid": compound_report["valid"],
        "integrity": {"materials": compare(before, after)},
        "runtime_seconds": round(time.monotonic() - t0, 2),
        "output_bytes": out_bytes,
    }
    run_c3b2._write(C.MILESTONE_OUTPUT_ROOT / "c3b4_reconciliation.json", recon)
    _print(recon, p)

    pil = recon["pilot"]
    ok = (ledger_report["valid"] and compound_report["valid"]
          and recon["integrity"]["materials"]["unchanged"]
          and recon["real_ledger"]["events"] == 0
          and recon["real_ledger"]["compound_events"] == 0
          and all(v is True for k, v in pil.items()
                  if isinstance(v, bool))
          and not any(a["reason"].startswith("NOT REFUSED")
                      for a in p["refused"]))
    if not ok:
        print("\nFAILED: a C3b4 invariant broke", file=sys.stderr)
        return 1
    return 0


def _print(r: dict, p: dict) -> None:
    t, pil = r["taxonomy"], r["pilot"]
    print("DIP-0C3b4 — canonical conflicts, atomic resolution, queues")
    print(f"  taxonomy:   v{t['taxonomy_version']} — "
          + ", ".join(f"{ax}={n}" for ax, n in t["tokens_per_axis"].items()))
    print(f"  real ledger: {r['real_ledger']['events']} events, "
          f"{r['real_ledger']['compound_events']} compound (EMPTY)")
    print("  pilot:")
    print(f"    disjoint masters coexist (EU+US):     {pil['disjoint_masters_coexist']}")
    print(f"    proven conflict detected (EU vs FR):  {pil['proven_conflict_detected']}")
    print(f"    conflict is SCOPE-LOCAL (US usable):  {pil['conflict_is_scope_local']}")
    print(f"    unknown token FAILS CLOSED:           {pil['unknown_token_fails_closed']}")
    print(f"    supersession ATOMIC (0 conflicts):    {pil['supersession_atomic']}")
    print(f"      post-state: {pil['supersession_post_state']}")
    print(f"    narrowing reduces only:               {pil['narrowing_reduces']}")
    print(f"    NOTHING written on failure:           {pil['nothing_written_on_failure']}")
    print(f"    no permission granted by resolution:  {pil['no_permission_granted']}")
    print(f"    queues deterministic:                 {pil['queues_deterministic']}")
    print(f"    queue totals: {pil['queue_totals']}")
    print(f"  refused:    {len(r['refused_attempts'])} illegal resolutions")
    for a in r["refused_attempts"]:
        print(f"     - {a['attempt']}")
    print(f"  integrity:  materials_unchanged="
          f"{r['integrity']['materials']['unchanged']}")
    print(f"  runtime:    {r['runtime_seconds']}s")


if __name__ == "__main__":
    raise SystemExit(main())
