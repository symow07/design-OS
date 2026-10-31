"""DIP-0C3d runner — palette decisions, authority domains, queues, reports.

SYNTHETIC. The real ledger stays empty: no real palette is approved, no real brand
asset is activated. The real `Pantone_3519C.ase` is audited (read-only) and lands in a
review queue — which is exactly where it should be, and no further.

    python -m tools.dip0c.run_c3d
"""
from __future__ import annotations

import sys
import time

from tools.dip0.integrity import compare, snapshot

from . import ase
from . import authz
from . import canonical_master as CM
from . import canonical_read as CR
from . import canonical_scope as S
from . import color_compare as CC
from . import config as C
from . import ledger as L
from . import ledger_store as LS
from . import palette_approval as PA
from . import permissions as P
from . import review_c3 as RV
from . import rights_model as RM
from . import run_c3b2
from . import run_c3c
from . import taxonomy as TX

PARSER = f"{C.TOOL_NAME}.run_c3d/{C.TOOL_VERSION}"
EXAMPLES = L.LEDGER_ROOT / "examples_TEST_ONLY"

T = "2026-07-14T09:00:00+00:00"
T2 = "2026-07-14T12:00:00+00:00"
NOW = "2026-07-14T13:00:00+00:00"
EXPIRY = "2026-10-01T00:00:00+00:00"
AFTER_EXPIRY = "2026-10-02T00:00:00+00:00"
COLOR_ID, LEGAL_ID = "TEST_ONLY_brand_admin", "TEST_ONLY_legal"


def _p_atts(color=COLOR_ID, legal=LEGAL_ID):
    return [PA.attestation(PA.ATT_COLOR, actor_id=color,
                           actor_role=authz.BRAND_ADMIN, attested_at=T),
            PA.attestation(PA.ATT_RIGHTS, actor_id=legal,
                           actor_role=authz.LEGAL_REVIEWER, attested_at=T)]


def _p_checklist(color=COLOR_ID, legal=LEGAL_ID):
    cl = PA.blank_checklist()
    for k in cl:
        by = color if k in PA.COLOR_ITEMS else legal
        cl[k] = {"result": True, "confirmed_by": by, "confirmed_at": T,
                 "notes": "TEST_ONLY"}
    return cl


def _m_atts():
    return [CM.attestation(CM.ATT_TECHNICAL, actor_id=COLOR_ID,
                           actor_role=authz.BRAND_ADMIN, attested_at=T),
            CM.attestation(CM.ATT_LEGAL, actor_id=LEGAL_ID,
                           actor_role=authz.LEGAL_REVIEWER, attested_at=T)]


def _m_checklist():
    cl = CM.blank_checklist()
    for k in cl:
        by = COLOR_ID if k in CM.TECHNICAL_ITEMS else LEGAL_ID
        cl[k] = {"result": True, "confirmed_by": by, "confirmed_at": T,
                 "notes": "TEST_ONLY"}
    return cl


def _audit_summary(a: dict) -> dict:
    """The C3c technical audit, condensed for the approval block."""
    p = a["palette"]["palette"]
    return {
        "parse_status": p["parse_status"], "capability": p["capability"],
        "layout": p["layouts_seen"], "fallback_used": p["fallback_used"],
        "parser_warnings": p["parser_warnings"],
        "color_models": p["color_models"], "color_types": p["color_types"],
        "third_party_naming": a["naming"]["detected_naming_systems"],
        "contains_spot_identity": a["naming"]["contains_spot_identity"],
        "swatch_names": a["naming"]["swatch_names"],
    }


def build_pilot() -> dict:
    r: dict = {"refused": []}
    real = run_c3c.audit()                       # the REAL file, read-only
    audit = _audit_summary(real)
    r["real_ase_audit"] = audit

    sc = S.scope("BBROSE", markets=["EU"], media=["DIGITAL"])
    ev = run_c3b2  # noqa: F841  (kept for symmetry with earlier runners)

    def _evidence(asset):
        e = L.evidence(asset, evidence_type="CONTRACT", title="t",
                       submitted_by=LEGAL_ID, actor_role=authz.LEGAL_REVIEWER,
                       submitted_at=T)
        e["review_status"] = L.EV_ACCEPTED
        e["reviewed_by"] = LEGAL_ID
        return e

    # --- 1. THE REAL FILE: audited, queued, and approved by NOBODY --------------
    ok_real, problems_real = PA.check_approval(
        "Pantone_3519C.ase", requested_state=PA.APPROVED_BRAND_PALETTE,
        actor_role=authz.BRAND_ADMIN, actor_id=COLOR_ID,
        checklist=_p_checklist(), attestations=_p_atts(), parser_audit=audit,
        ownership_state=C.OWN_UNKNOWN, license_state=C.LIC_UNVERIFIED,
        evidence_records=[], reason="it looks like our colour",
        requested_scope=sc)
    r["real_ase_approval"] = {
        "allowed": ok_real, "problems": problems_real,
        "note": "the REAL file is refused on every axis that matters: ownership "
                "unknown, licence unverified, no evidence, PANTONE naming "
                "unacknowledged, the parser fallback unacknowledged, and no swatch "
                "provenance declared. It stays in a queue. NO approval is recorded.",
    }

    # --- 2. a SYNTHETIC palette that DOES pass, under dual control --------------
    syn = "TEST_ONLY_bbrose_palette.ase"
    syn_audit = {**audit, "parse_status": ase.TECHNICALLY_PARSED,
                 "fallback_used": False, "layout": [ase.LAYOUT_STANDARD],
                 "parser_warnings": [], "third_party_naming": [],
                 "swatch_names": ["BBROSE Plum"]}
    ok_syn, problems_syn = PA.check_approval(
        syn, requested_state=PA.APPROVED_BRAND_PALETTE,
        actor_role=authz.BRAND_ADMIN, actor_id=COLOR_ID,
        checklist=_p_checklist(), attestations=_p_atts(), parser_audit=syn_audit,
        ownership_state=C.OWN_BBROSE_CONFIRMED, license_state=C.LIC_APPROVED,
        evidence_records=[_evidence(syn)], reason="TEST_ONLY: our palette",
        value_provenance={"BBROSE Plum": PA.RAW_SOURCE}, requested_scope=sc)
    pal_evt = L.event(
        syn, event_type=L.BRAND_PALETTE_APPROVED, actor_id=COLOR_ID,
        actor_role=authz.BRAND_ADMIN, occurred_at=T,
        decision_reason="TEST_ONLY: our palette",
        evidence_refs=[_evidence(syn)["evidence_id"]],
        canonical=PA.canonical_block(
            PA.APPROVED_BRAND_PALETTE, scope=sc, checklist=_p_checklist(),
            attestations=_p_atts(), parser_audit=syn_audit,
            value_provenance={"BBROSE Plum": PA.RAW_SOURCE}, version_or_date=T))

    eff = P.effective_permissions(syn, [pal_evt], now=NOW)
    r["approval_grants_nothing"] = {
        "approved": ok_syn, "problems": problems_syn,
        "all_permissions_false": not any(x["value"] for x in
                                         eff["permissions"].values()),
        "permission_flags_checked": len(P.FLAGS),
        "note": "APPROVED as the BBROSE brand palette — and every permission is "
                "still false. Approving the colours is not permitting their use.",
    }

    # --- 3. AUTHORITY DOMAINS: a master and a palette do not fight --------------
    master = L.event(
        "TEST_ONLY_logo.ai", event_type=L.CANONICAL_MASTER_APPROVED,
        actor_id=COLOR_ID, actor_role=authz.BRAND_ADMIN, occurred_at=T,
        decision_reason="TEST_ONLY",
        canonical=L.canonical_block(
            C.CANONICAL_BRAND_MASTER, scope=sc, checklist=_m_checklist(),
            attestations=_m_atts(),
            authority_domain=L.DOMAIN_BRAND_MASTER))
    pal2 = L.event(
        "TEST_ONLY_other_palette.ase", event_type=L.BRAND_PALETTE_APPROVED,
        actor_id=COLOR_ID, actor_role=authz.BRAND_ADMIN, occurred_at=T2,
        decision_reason="TEST_ONLY",
        canonical=PA.canonical_block(
            PA.APPROVED_BRAND_PALETTE, scope=sc, checklist=_p_checklist(),
            attestations=_p_atts(), parser_audit=syn_audit,
            value_provenance={"BBROSE Plum": PA.RAW_SOURCE}))
    r["authority_domains"] = {
        "master_plus_palette_same_scope_conflicts":
            len(CR.conflicts([master, pal_evt])),
        "two_palettes_same_scope_conflicts":
            len(CR.conflicts([master, pal_evt, pal2])),
        "conflict_domain": (CR.conflicts([master, pal_evt, pal2])[0]["authority_domain"]
                            if CR.conflicts([master, pal_evt, pal2]) else None),
        "master_still_usable":
            CR.canonical_for([master, pal_evt, pal2], sc,
                             L.DOMAIN_BRAND_MASTER)["asset"],
        "palette_blocked":
            CR.canonical_for([master, pal_evt, pal2], sc,
                             L.DOMAIN_BRAND_PALETTE)["state"],
        "note": "a logo master and a brand palette answer DIFFERENT questions. They "
                "may both be authoritative for one scope without contradicting each "
                "other. Two palettes for one scope DO conflict.",
    }

    # --- 4. MEDIA scope gates permissions --------------------------------------
    grant = L.event(
        syn, event_type=L.PERMISSION_GRANTED, actor_id=LEGAL_ID,
        actor_role=authz.LEGAL_REVIEWER, occurred_at=T2,
        decision_reason="TEST_ONLY: digital retrieval", review_expiry=EXPIRY,
        permission=L.permission_block(
            "retrieval_allowed", previous_value=False, requested_value=True,
            purpose="internal_design", approved_brands=["BBROSE"],
            approved_media=["DIGITAL"], validity_start=T2, review_expiry=EXPIRY,
            ownership_decision_ref="evt-TEST", license_decision_ref="evt-TEST"))
    events = [pal_evt, grant]
    r["media_scope"] = {
        m: P.effective_permissions(syn, events, now=NOW, brand="BBROSE",
                                   media=m)["permissions"]["retrieval_allowed"]["value"]
        for m in ("DIGITAL", "SCREEN", "PACKAGING_PRINT", "PRINT", "WEB")
    }
    r["media_scope"]["note"] = (
        "approved for DIGITAL. SCREEN is inside DIGITAL, so it is covered. "
        "PACKAGING_PRINT is not — PRINT and DIGITAL are declared disjoint and "
        "PACKAGING_PRINT inherits that. WEB is UNKNOWN, and unknown FAILS CLOSED.")

    # --- 5. expiry still fails closed ------------------------------------------
    r["expiry"] = {
        "before": P.effective_permissions(syn, events, now=NOW, brand="BBROSE",
                                          media="DIGITAL")["permissions"][
                                              "retrieval_allowed"]["value"],
        "after": P.effective_permissions(syn, events, now=AFTER_EXPIRY,
                                         brand="BBROSE", media="DIGITAL")[
                                             "permissions"]["retrieval_allowed"],
    }

    # --- 6. the parser limitation SURVIVES approval -----------------------------
    approved_real = PA.approval_block(
        audit, value_provenance={"Pantone 3519 C": PA.DERIVED_PREVIEW},
        parser_limitation_ack={"parser_limitation_acknowledged": True,
                               "reason": "TEST_ONLY: accepted with eyes open"},
        third_party_ack={"acknowledged": True, "reason": "TEST_ONLY"})
    r["parser_limitation_survives"] = {
        "parse_status": approved_real["parse_status"],
        "layout": approved_real["layout"],
        "fallback_used": approved_real["fallback_used"],
        "parser_warnings": approved_real["parser_warnings"],
        "contains_spot_identity": approved_real["contains_spot_identity"],
        "value_provenance": approved_real["value_provenance"],
        "grants_permissions": approved_real["grants_permissions"],
        "note": "even a hypothetical approval cannot rewrite the audit. PARTIAL_PARSE "
                "stays PARTIAL_PARSE; a derived preview stays derived.",
    }

    # --- 7. the colour-comparison gate -----------------------------------------
    cmyk = {"raw": {"model": "CMYK", "channels": [0.1, 0.2, 0.3, 0.4],
                    "authoritative": True},
            "normalized": {"conversion_method": "NAIVE_CMYK_TO_SRGB_NO_ICC"}}
    rgb = real["palette"]["swatches"][0]
    gates = []
    for label, fn in (
            ("naive CMYK preview grounds a ΔE", lambda: CC.refuse_naive_preview(cmyk)),
            ("cross-model RGB vs CMYK", lambda: CC.compare(rgb, cmyk)),
            ("CMYK without an ICC profile", lambda: CC.compare(cmyk, cmyk))):
        try:
            fn()
            gates.append({"attempt": label, "refused": False})
        except CC.ComparisonRefused as e:
            gates.append({"attempt": label, "refused": True, "reason": str(e)[:90]})
    r["color_comparison_gate"] = {
        "refusals": gates,
        "rgb_to_rgb_allowed": CC.can_compare(rgb, rgb)["comparable"],
        "name_is_not_an_id": CC.name_is_not_an_identifier("Pantone 3519 C")["status"],
        "historical_link": CC.historical_link("Pantone_3519C.ase"),
    }

    # --- 8. refusals ------------------------------------------------------------
    errs = (authz.NotAuthorized, L.LedgerError, C.HumanOnlyStateViolation,
            RM.MachineMayNotIncrease)
    for label, fn in (
            ("SYSTEM_ADMIN approves a brand palette",
             lambda: authz.authorize(authz.SYSTEM_ADMIN, authz.APPROVE_BRAND_PALETTE,
                                     actor_id="sa")),
            ("SYSTEM_ADMIN attests palette rights",
             lambda: authz.authorize(authz.SYSTEM_ADMIN, authz.ATTEST_PALETTE_RIGHTS,
                                     actor_id="sa")),
            ("BRAND_ADMIN attests palette RIGHTS (legal only)",
             lambda: authz.authorize(authz.BRAND_ADMIN, authz.ATTEST_PALETTE_RIGHTS,
                                     actor_id="ba")),
            ("machine declares APPROVED_BRAND_PALETTE",
             lambda: PA.machine_palette_authority(PA.APPROVED_BRAND_PALETTE)),
            ("a palette approval attested by ONE person",
             lambda: L.event(
                 syn, event_type=L.BRAND_PALETTE_APPROVED, actor_id=COLOR_ID,
                 actor_role=authz.BRAND_ADMIN, occurred_at=T, decision_reason="solo",
                 canonical=PA.canonical_block(
                     PA.APPROVED_BRAND_PALETTE, scope=sc,
                     checklist=_p_checklist(COLOR_ID, COLOR_ID),
                     attestations=_p_atts(COLOR_ID, COLOR_ID),
                     parser_audit=syn_audit, value_provenance={})))):
        try:
            fn()
            r["refused"].append({"attempt": label, "reason": "NOT REFUSED — BUG"})
        except errs as e:
            r["refused"].append({"attempt": label,
                                 "reason": str(e).splitlines()[0][:90]})

    # --- 9. dual-control refusals ------------------------------------------------
    solo_ok, solo_problems = PA.check_approval(
        syn, requested_state=PA.APPROVED_BRAND_PALETTE,
        actor_role=authz.BRAND_ADMIN, actor_id=COLOR_ID,
        checklist=_p_checklist(COLOR_ID, COLOR_ID),
        attestations=_p_atts(COLOR_ID, COLOR_ID), parser_audit=syn_audit,
        ownership_state=C.OWN_BBROSE_CONFIRMED, license_state=C.LIC_APPROVED,
        evidence_records=[_evidence(syn)], reason="alone",
        value_provenance={"BBROSE Plum": PA.RAW_SOURCE}, requested_scope=sc)
    r["dual_control"] = {
        "one_person_both_halves_allowed": solo_ok,
        "problems": solo_problems,
    }

    # --- 10. queues ---------------------------------------------------------------
    findings = {
        "palettes_unassociated": [{"asset": "Pantone_3519C.ase",
                                   "reason": "brand association REQUIRES_HUMAN"}],
        "palettes_rights_unresolved": [{"asset": "Pantone_3519C.ase",
                                        "reason": "PANTONE naming; ownership unknown"}],
        "palettes_awaiting_approval": [{"asset": "Pantone_3519C.ase",
                                        "reason": "needs two attestations"}],
        "possible_masters": [{"asset": "logo.pdf"}],
        "third_party_logos": [{"asset": "JOJIA LOGO.ai"}],
        "contradictions": [{"asset": "LOGO6.ai",
                            "reason": "live text reads 'global logistics services'"}],
        "canonical_nominations": [{"asset": "logo.pdf"}],
        "outlined_wordmarks": [{"asset": "BBROSE.pdf"}],
    }
    q1 = RV.build([master, pal_evt, pal2, grant], now=NOW, brand_findings=findings)
    q2 = RV.build([grant, pal2, pal_evt, master], now=NOW, brand_findings=findings)
    r["queues"] = {
        "totals": q1["totals"], "total_items": q1["total_items"],
        "critical": q1["critical"],
        "never_batch_approved": q1["never_batch_approved"],
        "deterministic": q1 == q2,
        "permission_flags_derived": q1["permission_flag_count"],
    }
    r["queue_detail"] = q1
    r["events"] = [master, pal_evt, pal2, grant]
    return r


def main(argv=None) -> int:
    t0 = time.monotonic()
    LS.ensure_dirs()
    before = snapshot()
    p = build_pilot()

    out_bytes = run_c3b2._write(
        EXAMPLES / "c3d_pilot.json",
        run_c3b2._mark({k: v for k, v in p.items()
                        if k not in ("queue_detail", "events")}))
    out_bytes += run_c3b2._write(C.MILESTONE_OUTPUT_ROOT / "c3d_review_queue_summary.json",
                                 p["queue_detail"])
    report = LS.validate()
    after = snapshot()

    tax = TX.load()
    recon = {
        "slice": "DIP-0C3d",
        "c3c_commit": "c34d4a1",
        "taxonomy": {
            "schema_version": tax["schema_version"],
            "taxonomy_version": tax["taxonomy_version"],
            "axes": list(TX.AXES),
            "media_tokens": sorted(tax["axes"]["media"]["tokens"]),
            "media_closed_world": tax["axes"]["media"]["closed_world"],
            "media_mutually_exclusive_roots":
                tax["axes"]["media"]["mutually_exclusive_roots"],
            "media_relations": {
                f"{a} vs {b}": TX.relate_tokens("media", a, b)[0]
                for a, b in (("ALL", "PRINT"), ("PRINT", "PACKAGING_PRINT"),
                             ("DIGITAL", "SCREEN"), ("PRINT", "DIGITAL"),
                             ("DIGITAL", "PACKAGING_PRINT"), ("SCREEN", "WEB"),
                             ("WEB", "SOCIAL_MEDIA"))},
        },
        "authority_domains": list(L.AUTHORITY_DOMAINS),
        "palette_event_types": list(L.PALETTE_EVENTS),
        "dual_control_events": list(L.DUAL_CONTROL_EVENTS),
        "permission_flags": sorted(RM.PERMISSION_FLAGS),
        "permission_flag_count": len(RM.PERMISSION_FLAGS),
        "queues": [{"queue_id": q, "display_label": RV.LABELS[q],
                    "title": RV.TITLES[q], "priority": RV.PRIORITIES[q],
                    "batch_review_allowed": RV.BATCHABLE[q],
                    "count": p["queues"]["totals"][q]}
                   for q in RV.QUEUE_IDS],
        "real_ase": {
            "audit": p["real_ase_audit"],
            "approval_allowed": p["real_ase_approval"]["allowed"],
            "problems": p["real_ase_approval"]["problems"],
        },
        "pilot": {
            "real_ase_refused": p["real_ase_approval"]["allowed"] is False,
            "synthetic_palette_approved": p["approval_grants_nothing"]["approved"],
            "approval_grants_no_permission":
                p["approval_grants_nothing"]["all_permissions_false"],
            "master_and_palette_do_not_conflict":
                p["authority_domains"]["master_plus_palette_same_scope_conflicts"] == 0,
            "two_palettes_conflict":
                p["authority_domains"]["two_palettes_same_scope_conflicts"] == 1,
            "media_digital_covers_screen": p["media_scope"]["SCREEN"] is True,
            "media_digital_denies_packaging_print":
                p["media_scope"]["PACKAGING_PRINT"] is False,
            "media_unknown_fails_closed": p["media_scope"]["WEB"] is False,
            "expiry_fails_closed": p["expiry"]["after"]["value"] is False,
            "parser_limitation_survives_approval":
                p["parser_limitation_survives"]["parse_status"] == ase.PARTIAL_PARSE,
            "dual_control_refuses_one_person":
                p["dual_control"]["one_person_both_halves_allowed"] is False,
            "naive_cmyk_refused":
                all(g["refused"] for g in p["color_comparison_gate"]["refusals"]),
            "historical_link_absent":
                p["color_comparison_gate"]["historical_link"][
                    "linked_to_historical_design_memory"] is False,
            "queues_deterministic": p["queues"]["deterministic"],
        },
        "refused_attempts": p["refused"],
        "real_ledger": {"events": report["counts"]["events"],
                        "compound_events": report["counts"]["compound_events"],
                        "note": "EMPTY. No real palette approval, no real activation."},
        "ledger_valid": report["valid"],
        "integrity": {"materials": compare(before, after)},
        "runtime_seconds": round(time.monotonic() - t0, 2),
        "output_bytes": out_bytes,
    }
    run_c3b2._write(C.MILESTONE_OUTPUT_ROOT / "c3d_reconciliation.json", recon)
    _print(recon, p)

    ok = (report["valid"]
          and recon["integrity"]["materials"]["unchanged"]
          and recon["real_ledger"]["events"] == 0
          and all(v is True for v in recon["pilot"].values() if isinstance(v, bool))
          and not any(a["reason"].startswith("NOT REFUSED")
                      for a in p["refused"]))
    if not ok:
        print("\nFAILED: a C3d invariant broke", file=sys.stderr)
        return 1
    return 0


def _print(r: dict, p: dict) -> None:
    t, pil = r["taxonomy"], r["pilot"]
    print("DIP-0C3d — palette decisions, authority domains, C3 queues")
    print(f"  taxonomy:   v{t['taxonomy_version']} — axes {t['axes']}")
    print(f"  media:      {t['media_tokens']}")
    for k, v in t["media_relations"].items():
        print(f"     {k:32s} -> {v}")
    print(f"  domains:    {r['authority_domains']}")
    print(f"  palette events: {len(r['palette_event_types'])} | "
          f"permission flags: {r['permission_flag_count']} (derived, not hardcoded)")
    print(f"  real ledger: {r['real_ledger']['events']} events (EMPTY)")
    print("  pilot:")
    for k, v in pil.items():
        print(f"    {k:38s} {v}")
    print(f"  refused:    {len(r['refused_attempts'])}")
    for a in r["refused_attempts"]:
        print(f"     - {a['attempt']}")
    print("  queues:")
    for q in r["queues"]:
        batch = "" if q["batch_review_allowed"] else "  [NEVER BATCH]"
        print(f"     {q['display_label']}  {q['queue_id']:38s} "
              f"{q['count']:3d}  {q['priority']}{batch}")
    print(f"  integrity:  materials_unchanged="
          f"{r['integrity']['materials']['unchanged']}")
    print(f"  runtime:    {r['runtime_seconds']}s")


if __name__ == "__main__":
    raise SystemExit(main())
