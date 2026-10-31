"""DIP-0C3e runner — domain-aware conflict resolution + C3 closure reconciliation.

SYNTHETIC. Every resolution below runs on TEST_ONLY assets, in memory or against a
scratch directory. The real ledger stays empty.

    python -m tools.dip0c.run_c3e
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
from . import palette_approval as PA
from . import permissions as P
from . import run_c3b2

PARSER = f"{C.TOOL_NAME}.run_c3e/{C.TOOL_VERSION}"
EXAMPLES = L.LEDGER_ROOT / "examples_TEST_ONLY"

T = "2026-07-14T09:00:00+00:00"
T2 = "2026-07-14T12:00:00+00:00"
NOW = "2026-07-14T13:00:00+00:00"
COLOR, LEGAL = "TEST_ONLY_brand_admin", "TEST_ONLY_legal"

AUDIT = {"parse_status": "PARTIAL_PARSE", "fallback_used": True,
         "layout": ["NON_STANDARD_NAME_ENCODING"],
         "parser_warnings": ["NAME_LENGTH_FIELD_ABSENT"],
         "third_party_naming": ["PANTONE"], "swatch_names": ["Plum"],
         "color_models": ["RGB"], "color_types": ["GLOBAL"],
         "contains_spot_identity": False}
ACK_P = {"parser_limitation_acknowledged": True, "reason": "TEST_ONLY: eyes open"}
ACK_N = {"acknowledged": True, "reason": "TEST_ONLY: reviewed"}


def _p_atts(c=COLOR, lg=LEGAL):
    return [PA.attestation(PA.ATT_COLOR, actor_id=c, actor_role=authz.BRAND_ADMIN,
                           attested_at=T),
            PA.attestation(PA.ATT_RIGHTS, actor_id=lg,
                           actor_role=authz.LEGAL_REVIEWER, attested_at=T)]


def _p_cl(c=COLOR, lg=LEGAL):
    cl = PA.blank_checklist()
    for k in cl:
        cl[k] = {"result": True, "confirmed_by": (c if k in PA.COLOR_ITEMS else lg),
                 "confirmed_at": T, "notes": "TEST_ONLY"}
    return cl


def _palette(asset, scope, at=T):
    return L.event(asset, event_type=L.BRAND_PALETTE_APPROVED, actor_id=COLOR,
                   actor_role=authz.BRAND_ADMIN, occurred_at=at,
                   decision_reason="TEST_ONLY",
                   canonical=PA.canonical_block(
                       PA.APPROVED_BRAND_PALETTE, scope=scope, checklist=_p_cl(),
                       attestations=_p_atts(), parser_audit=AUDIT,
                       value_provenance={"Plum": PA.DERIVED_PREVIEW},
                       parser_limitation_ack=ACK_P, third_party_ack=ACK_N))


def _master(asset, scope, at=T):
    cl = CM.blank_checklist()
    for k in cl:
        cl[k] = {"result": True,
                 "confirmed_by": (COLOR if k in CM.TECHNICAL_ITEMS else LEGAL),
                 "confirmed_at": T, "notes": "TEST_ONLY"}
    atts = [CM.attestation(CM.ATT_TECHNICAL, actor_id=COLOR,
                           actor_role=authz.BRAND_ADMIN, attested_at=T),
            CM.attestation(CM.ATT_LEGAL, actor_id=LEGAL,
                           actor_role=authz.LEGAL_REVIEWER, attested_at=T)]
    return L.event(asset, event_type=L.CANONICAL_MASTER_APPROVED, actor_id=COLOR,
                   actor_role=authz.BRAND_ADMIN, occurred_at=at,
                   decision_reason="TEST_ONLY",
                   canonical=L.canonical_block(
                       C.CANONICAL_BRAND_MASTER, scope=scope, checklist=cl,
                       attestations=atts,
                       authority_domain=L.DOMAIN_BRAND_MASTER))


def build_pilot() -> dict:
    r: dict = {"refused": []}
    sc = S.scope("BBROSE", markets=["EU"], media=["DIGITAL"])
    m = _master("TEST_ONLY_logo.ai", sc)
    a = _palette("TEST_ONLY_palette_a.ase", sc)
    b = _palette("TEST_ONLY_palette_b.ase", sc, at=T2)

    # --- 1. two overlapping palettes fail closed --------------------------------
    conf = CR.conflicts([m, a, b])
    q = CR.canonical_for([m, a, b], sc, L.DOMAIN_BRAND_PALETTE)
    r["conflict"] = {
        "count": len(conf),
        "domain": conf[0]["authority_domain"] if conf else None,
        "neither_available": q["usable"] is False,
        "master_unaffected": CR.canonical_for([m, a, b], sc,
                                              L.DOMAIN_BRAND_MASTER)["usable"],
    }

    # --- 2. DEPRECATE resolves it, atomically -----------------------------------
    _, dep = RES.resolve(RES.DEPRECATE_INCUMBENT, incumbent_event_id=a["event_id"],
                         existing_events=[m, a, b], actor_id=COLOR,
                         actor_role=authz.BRAND_ADMIN, occurred_at=T2,
                         reason="TEST_ONLY: palette_a retired", dry_run=True)
    post = [m, a, b] + dep["constituents"]
    carried = dep["constituents"][0]["canonical"]["palette"]
    r["deprecate"] = {
        "domain": dep["authority_domain"],
        "events": [e["event_type"] for e in dep["constituents"]],
        "post_conflicts": len(CR.conflicts(post)),
        "post_state": sorted((x["asset"], x["lifecycle"]) for x in CR.masters(post)),
        "palette_now_active": CR.canonical_for(post, sc,
                                               L.DOMAIN_BRAND_PALETTE)["asset"],
        "master_still_active": CR.canonical_for(post, sc,
                                                L.DOMAIN_BRAND_MASTER)["asset"],
        "audit_carried_verbatim": {
            "parse_status": carried["parse_status"],
            "parser_warnings": carried["parser_warnings"],
            "value_provenance": carried["value_provenance"],
            "third_party_acknowledged":
                carried["third_party_naming_acknowledged"]["acknowledged"],
            "grants_permissions": carried["grants_permissions"],
        },
    }

    # --- 3. SUPERSEDE, with dual control ----------------------------------------
    _, sup = RES.resolve(
        RES.SUPERSEDE_INCUMBENT, incumbent_event_id=a["event_id"],
        existing_events=[m, a], actor_id=COLOR, actor_role=authz.BRAND_ADMIN,
        occurred_at=T2, reason="TEST_ONLY: v2", new_asset="TEST_ONLY_palette_c.ase",
        new_scope=sc, attestations=_p_atts(), checklist=_p_cl(), palette_audit=AUDIT,
        value_provenance={"Plum": PA.RAW_SOURCE}, parser_limitation_ack=ACK_P,
        third_party_ack=ACK_N, dry_run=True)
    post2 = [m, a] + sup["constituents"]
    eff = P.effective_permissions("TEST_ONLY_palette_c.ase", post2, now=NOW)
    r["supersede"] = {
        "events": [e["event_type"] for e in sup["constituents"]],
        "no_master_events": not any("CANONICAL_MASTER" in e["event_type"]
                                    for e in sup["constituents"]),
        "post_conflicts": len(CR.conflicts(post2)),
        "post_state": sorted((x["asset"], x["lifecycle"])
                             for x in CR.masters(post2)),
        "chain": CR._chains(CR.masters(post2)),
        "replacement_keeps_partial_parse":
            sup["constituents"][1]["canonical"]["palette"]["parse_status"],
        "grants_no_permission": not any(x["value"]
                                        for x in eff["permissions"].values()),
    }

    # --- 4. refusals — nothing written ------------------------------------------
    errs = (RES.ResolutionError, CP.CompoundError, L.LedgerError,
            C.HumanOnlyStateViolation)
    base = dict(incumbent_event_id=a["event_id"], existing_events=[a],
                actor_id=COLOR, actor_role=authz.BRAND_ADMIN, occurred_at=T2,
                reason="r", new_asset="x.ase", new_scope=sc,
                attestations=_p_atts(), checklist=_p_cl(), palette_audit=AUDIT,
                value_provenance={"Plum": PA.RAW_SOURCE},
                parser_limitation_ack=ACK_P, third_party_ack=ACK_N)
    before_files = len(CP.load_all())
    for label, over in (
            ("supersede with no legal attestation",
             {"attestations": [_p_atts()[0]]}),
            ("one actor attests both halves",
             {"attestations": _p_atts(COLOR, COLOR)}),
            ("a replacement with no technical audit", {"palette_audit": None}),
            ("a replacement with undeclared value provenance",
             {"value_provenance": {}}),
            ("SYSTEM_ADMIN resolves a palette conflict",
             {"actor_id": "sa", "actor_role": authz.SYSTEM_ADMIN}),
            ("a resolution that would leave an overlap",
             {"existing_events": [a, b]})):
        try:
            RES.resolve(RES.SUPERSEDE_INCUMBENT, **{**base, **over})
            r["refused"].append({"attempt": label, "reason": "NOT REFUSED — BUG"})
        except errs as e:
            line = [x for x in str(e).splitlines() if x.strip()][-1].strip()
            r["refused"].append({"attempt": label, "reason": line[:100]})
    try:
        RES.resolve(RES.NARROW_INCUMBENT_SCOPE, incumbent_event_id=a["event_id"],
                    existing_events=[a], actor_id=COLOR,
                    actor_role=authz.BRAND_ADMIN, occurred_at=T2, reason="r",
                    narrowed_scope=S.scope("BBROSE", markets=["EU", "US"]))
    except errs as e:
        r["refused"].append({"attempt": "palette widening disguised as narrowing",
                             "reason": str(e).splitlines()[-1].strip()[:100]})
    try:
        RES.machine_may_not_resolve()
    except C.HumanOnlyStateViolation as e:
        r["refused"].append({"attempt": "a machine resolves a palette conflict",
                             "reason": str(e)[:100]})
    r["nothing_written_on_failure"] = len(CP.load_all()) == before_files

    # --- 5. narrowing reduces only ----------------------------------------------
    _, nar = RES.resolve(RES.NARROW_INCUMBENT_SCOPE,
                         incumbent_event_id=a["event_id"], existing_events=[a],
                         actor_id=COLOR, actor_role=authz.BRAND_ADMIN,
                         occurred_at=T2, reason="TEST_ONLY: France only",
                         narrowed_scope=S.scope("BBROSE", markets=["FR"],
                                                media=["DIGITAL"]),
                         dry_run=True)
    nm = CR.masters([a] + nar["constituents"])[0]
    r["narrowing"] = {
        "event": nar["constituents"][0]["event_type"],
        "domain": nar["constituents"][0]["canonical"]["authority_domain"],
        "before": ["EU"], "after": nm["scope"]["markets"]["tokens"],
    }
    return r


def main(argv=None) -> int:
    t0 = time.monotonic()
    LS.ensure_dirs()
    before = snapshot()
    p = build_pilot()

    out_bytes = run_c3b2._write(EXAMPLES / "c3e_pilot.json", run_c3b2._mark(p))
    report = LS.validate()
    cp_report = CP.validate_committed()
    after = snapshot()

    recon = {
        "slice": "DIP-0C3e",
        "c3d_commit": "1960128",
        "authority_domains": list(L.AUTHORITY_DOMAINS),
        "resolution_actions": list(RES.ACTIONS),
        "domain_event_mapping": {
            d: {k: v for k, v in spec.items() if k.endswith("_event")}
            for d, spec in RES.DOMAIN_SPEC.items()},
        "pilot": {
            "two_palettes_fail_closed": p["conflict"]["count"] == 1,
            "conflict_domain_is_palette":
                p["conflict"]["domain"] == L.DOMAIN_BRAND_PALETTE,
            "neither_palette_available": p["conflict"]["neither_available"],
            "master_unaffected_by_palette_conflict":
                p["conflict"]["master_unaffected"],
            "deprecate_resolves": p["deprecate"]["post_conflicts"] == 0,
            "supersede_resolves": p["supersede"]["post_conflicts"] == 0,
            "no_master_events_from_palette_resolution":
                p["supersede"]["no_master_events"],
            "parser_limitation_survives":
                p["deprecate"]["audit_carried_verbatim"]["parse_status"]
                == "PARTIAL_PARSE",
            "third_party_ack_survives":
                p["deprecate"]["audit_carried_verbatim"]["third_party_acknowledged"],
            "resolution_grants_no_permission":
                p["supersede"]["grants_no_permission"],
            "narrowing_reduces_only": p["narrowing"]["after"] == ["FR"],
            "nothing_written_on_failure": p["nothing_written_on_failure"],
        },
        "refused_attempts": p["refused"],
        "real_ledger": {"events": report["counts"]["events"],
                        "compound_events": cp_report["compound_events"],
                        "note": "EMPTY. No real conflict was resolved."},
        "ledger_valid": report["valid"],
        "compound_valid": cp_report["valid"],
        "integrity": {"materials": compare(before, after)},
        "runtime_seconds": round(time.monotonic() - t0, 2),
        "output_bytes": out_bytes,
    }
    run_c3b2._write(C.MILESTONE_OUTPUT_ROOT / "c3e_reconciliation.json", recon)
    _print(recon, p)

    ok = (report["valid"] and cp_report["valid"]
          and recon["integrity"]["materials"]["unchanged"]
          and recon["real_ledger"]["events"] == 0
          and recon["real_ledger"]["compound_events"] == 0
          and all(v is True for v in recon["pilot"].values())
          and not any(a["reason"].startswith("NOT REFUSED") for a in p["refused"]))
    if not ok:
        print("\nFAILED: a C3e invariant broke", file=sys.stderr)
        return 1
    return 0


def _print(r: dict, p: dict) -> None:
    print("DIP-0C3e — domain-aware conflict resolution")
    print(f"  domains:  {r['authority_domains']}")
    for d, ev in r["domain_event_mapping"].items():
        print(f"    {d}: {ev['deprecate_event']} / {ev['replace_event']} / "
              f"{ev['variant_event']}")
    print("  pilot:")
    for k, v in r["pilot"].items():
        print(f"    {k:42s} {v}")
    print(f"  deprecate -> {p['deprecate']['post_state']}")
    print(f"  supersede -> {p['supersede']['post_state']}")
    print(f"  refused:  {len(r['refused_attempts'])}")
    for a in r["refused_attempts"]:
        print(f"     - {a['attempt']}")
    print(f"  real ledger: {r['real_ledger']['events']} events, "
          f"{r['real_ledger']['compound_events']} compound (EMPTY)")
    print(f"  integrity: materials_unchanged="
          f"{r['integrity']['materials']['unchanged']}")
    print(f"  runtime:  {r['runtime_seconds']}s")


if __name__ == "__main__":
    raise SystemExit(main())
