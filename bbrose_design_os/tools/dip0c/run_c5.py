"""DIP-0C5 runner — consolidation, review contract, gates, DIP-1 blueprint.

Read-only. Nothing activated, approved, installed, migrated or granted.

    python -m tools.dip0c.run_c5
"""
from __future__ import annotations

import sys
import time

from tools.dip0.integrity import compare, snapshot

from . import compound as CP
from . import config as C
from . import consolidate as CON
from . import dispositions as D
from . import gates as G
from . import ledger_store as LS
from . import review_contract as RC
from . import review_domains as RD
from . import run_c3b2
from . import run_c4c

PARSER = f"{C.TOOL_NAME}.run_c5/{C.TOOL_VERSION}"
OUT = C.OUTPUT_ROOT / "c5"


def build_review_index() -> dict:
    """Real review items from the C4 audit + the C3 pilot findings, with UNIQUE
    (domain, subject) identity and queue membership as a separate relation."""
    c4 = run_c4c.audit()
    items: list[dict] = []
    memberships: list[dict] = []

    def add(domain, subject, *, summary, priority, reasons, rec=None,
            evidence=None, restrictions=None, queues=()):
        it = RC.review_item(
            domain=domain, subject_id=subject, source_refs=summary.get("_src", []),
            machine_summary={k: v for k, v in summary.items() if k != "_src"},
            priority=priority, reasons=reasons, recommended_action=rec,
            evidence_refs=evidence, restrictions=restrictions,
            config_version="dip0c5/1.0")
        items.append(it)
        s = RD.spec(domain)
        for qid, reason, blocking in queues:
            memberships.append(RC.queue_membership(
                review_item_id_=it["review_item_id"], queue_id=qid, reason=reason,
                priority=priority, blocking=blocking,
                required_role=s["required_roles"][0],
                batchable=s["batch_review_allowed"], provenance="DIP-0C4c"))
        return it

    # --- FONT_FACE (technical) --------------------------------------------------
    for row in c4["manifest"]:
        m = row["machine"]
        qs = [("FONT_FAMILY_RELATIONSHIP_REVIEW", "family evidence conflicts", False)] \
            if m["review_priority"] == "MEDIUM" else []
        if m["system_font_suspicion"] == "SUSPECTED_SYSTEM_FONT_COPY":
            qs.append(("FONT_SUSPECTED_SYSTEM_COPY", "name-table foundry evidence",
                       True))
        if not m["license_evidence_mentioning_fonts"]:
            qs.append(("FONT_MISSING_LICENSE_EVIDENCE", "no font-relevant evidence",
                       True))
        add(RD.FONT_FACE, m["face_id"],
            summary={"_src": [m["source_path"]], "family": m["technical_family"],
                     "vendor": m["vendor"], "health": m["technical_health"],
                     "dominant_script": m["dominant_script"]},
            priority=m["review_priority"], reasons=m["review_reasons"],
            rec=(D.QUARANTINE_CANDIDATE if m["quarantine_recommendation"]
                 else D.REQUIRES_HUMAN),
            evidence=m["license_evidence_mentioning_fonts"], queues=qs)

    # --- PROVENANCE_RIGHTS_GROUP (rights) — a DIFFERENT decision -----------------
    for d in c4["duplicate_model"]:
        for sg in d["provenance_rights_subgroups"]:
            subject = f"{d['sha256'][:16]}::{sg['source_package']}"
            add(RD.PROVENANCE_RIGHTS_GROUP, subject,
                summary={"_src": sg["paths"], "sha256": d["sha256"],
                         "provenance_kind": sg["provenance_kind"],
                         "files": sg["file_count"]},
                priority="HIGH" if not d["rights_batchable"] else "MEDIUM",
                reasons=[d["rights_batch_reason"]],
                rec=(D.PROVENANCE_MISSING
                     if sg["provenance_kind"] == "UNVERIFIED_DUMP"
                     else D.RIGHTS_REVIEW_REQUIRED),
                evidence=sg["license_evidence_mentioning_fonts"],
                queues=[("FONT_CROSS_PACKAGE_DUPLICATE_RIGHTS_REVIEW",
                         "identical bytes, different provenance",
                         not d["rights_batchable"])])

    # --- FONT_SOURCE_PACKAGE ------------------------------------------------------
    for p in c4["packages"]:
        add(RD.FONT_SOURCE_PACKAGE, p["package_key"],
            summary={"_src": p["package_roots"], "kind": p["package_kind"],
                     "files": p["file_count"], "faces": p["face_count"]},
            priority="MEDIUM" if p["has_license_evidence"] else "HIGH",
            reasons=[p["note"]],
            rec=(D.RIGHTS_REVIEW_REQUIRED if p["has_license_evidence"]
                 else D.PROVENANCE_MISSING),
            evidence=p["license_evidence_files"],
            restrictions=p["restrictions_detected"],
            queues=[("FONT_SOURCE_PACKAGE_REVIEW", "a credible rights unit", False)])

    # --- FONT_FAMILY --------------------------------------------------------------
    for g in c4["groups"]:
        if g["state"] == "FAMILY_GROUPED":
            continue                                    # nothing to ask
        add(RD.FONT_FAMILY, g["group_id"],
            summary={"_src": g["source_packages"], "family": g["family_key"],
                     "faces": g["face_count"], "vendors": g["vendors"]},
            priority="MEDIUM", reasons=g["conflicting_evidence"],
            rec=D.REQUIRES_HUMAN,
            queues=[("FONT_FAMILY_RELATIONSHIP_REVIEW",
                     "name matched, evidence did not", False)])

    # --- QUARANTINE_BATCH ----------------------------------------------------------
    prop = c4["system_font_proposal"]
    add(RD.QUARANTINE_BATCH, "materials/Fonts[+3333]",
        summary={"_src": ["materials/Fonts", "materials/Fonts/3333"],
                 "files": prop["total_files"], "faces": prop["total_faces"],
                 "suspected_faces": prop["suspected_faces"],
                 "is_applied": prop["is_applied"]},
        priority="HIGH", reasons=[prop["false_positive_risk"]],
        rec=D.QUARANTINE_CANDIDATE,
        queues=[("FONT_QUARANTINE_CANDIDATE", "proposed, not applied", True)])

    # --- COLOR_PALETTE (C3c) --------------------------------------------------------
    add(RD.COLOR_PALETTE, "Pantone_3519C.ase",
        summary={"_src": ["materials/DOWNLOADE 2026/…/Pantone_3519C.ase"],
                 "parse_status": "PARTIAL_PARSE", "swatches": 1, "model": "RGB",
                 "color_type": "GLOBAL", "third_party_naming": ["PANTONE"]},
        priority="HIGH",
        reasons=["PARTIAL_PARSE via a non-standard fallback",
                 "PANTONE naming is third-party and unacknowledged",
                 "ownership unknown, licence unverified"],
        rec=D.RIGHTS_REVIEW_REQUIRED,
        queues=[("PALETTE_APPROVAL_DUAL_CONTROL", "needs two attestations", True)])

    # --- CANONICAL_MASTER_CANDIDATE (C3a) -------------------------------------------
    for asset, reason in (
            ("logo.pdf", "nominated BRAND_MASTER_CANDIDATE — a nomination confers "
                         "nothing"),
            ("LOGO6.ai", "live text reads 'global logistics services' — an "
                         "unacknowledged contradiction blocks approval")):
        add(RD.CANONICAL_MASTER_CANDIDATE, asset,
            summary={"_src": [asset], "state": "CANDIDATE"},
            priority="HIGH", reasons=[reason], rec=D.REQUIRES_HUMAN,
            queues=[("CANONICAL_MASTER_NOMINATION", "awaiting dual control", True)])

    return {"items": items, "memberships": memberships,
            "index": RC.index(items, memberships), "c4": c4}


def main(argv=None) -> int:
    t0 = time.monotonic()
    before = snapshot()

    cov = CON.coverage()
    arts = CON.milestone_artifacts()
    inv = CON.inventory_totals()
    rv = build_review_index()
    idx = rv["index"]

    led = LS.validate()
    cpr = CP.validate_committed()
    act = CON.activation_totals(led, cpr)

    C.assert_output_safe(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    out_bytes = run_c3b2._write(OUT / "review_items.json", rv["items"])
    out_bytes += run_c3b2._write(OUT / "queue_memberships.json", rv["memberships"])

    after = snapshot()
    recon = {
        "slice": "DIP-0C5",
        "c4c_commit": "7beb5e5",
        "coverage": cov,
        "inventory": inv,
        "milestone_artifacts": {k: v for k, v in arts.items() if k != "artifacts"},
        "review_index": idx,
        "review_domains": {
            d: {"dual_control_required": s["dual_control_required"],
                "batch_review_allowed": s["batch_review_allowed"],
                "expiry_applies": s["expiry_applies"],
                "allowed_human_actions": list(s["allowed_human_actions"])}
            for d, s in RD.SPEC.items()},
        "dispositions": {
            "machine_recommendations": list(D.MACHINE_RECOMMENDATIONS),
            "human_decisions": list(D.HUMAN_DECISIONS),
            "vocabularies_disjoint": not (set(D.MACHINE_RECOMMENDATIONS)
                                          & set(D.HUMAN_DECISIONS)),
            "any_decision_grants_permission": False,
        },
        "gates": {
            "retrieval_default": False,
            "automatic_use_default": False,
            "collapsed": G.gates_are_independent()["collapsed"],
            "font_permissions_separate": G.font_permissions_are_separate()["separate"],
            "historical_memory_posture": G.REFERENCE_MEMORY_ONLY,
            "historical_memory_excluded": list(G.MEMORY_EXCLUDED),
        },
        "activation": act,
        "integrity": {"materials": compare(before, after)},
        "runtime_seconds": round(time.monotonic() - t0, 2),
        "output_bytes": out_bytes,
    }
    run_c3b2._write(C.MILESTONE_OUTPUT_ROOT / "dip0c5_reconciliation.json", recon)
    _print(recon)

    ok = (recon["integrity"]["materials"]["unchanged"]
          and act["all_zero"]
          and recon["dispositions"]["vocabularies_disjoint"]
          and idx["estimated_human_decisions"] == idx["unique_review_items"]
          and idx["estimated_human_decisions"] < idx["total_queue_memberships"] * 10
          and not arts["regenerated_any_old_artifact"])
    if not ok:
        print("\nFAILED: a C5 invariant broke", file=sys.stderr)
        return 1
    return 0


def _print(r: dict) -> None:
    print("DIP-0C5 — consolidation, review contract, gates, DIP-1 blueprint\n")
    print("  COVERAGE — what was ACTUALLY audited:")
    for row in r["coverage"]["rows"]:
        aud = f"{row['audited']}/{row['corpus']}" if row["corpus"] else "—"
        print(f"     {row['status']:28s} {aud:>12s}  "
              f"{row['coverage_pct']:5.1f}%  {row['milestone']}")
    print("\n  OUTSTANDING (planned expansion, not hidden omissions):")
    for w in r["coverage"]["outstanding_workstreams"]:
        print(f"     {w['outstanding_files']:5d} files — {w['workstream']}")
    i = r["review_index"]
    print("\n  REVIEW INDEX (identity = domain + subject):")
    print(f"     unique review items:            {i['unique_review_items']:6d}")
    print(f"     total queue memberships:        {i['total_queue_memberships']:6d}")
    print(f"     items in multiple queues:       {i['items_in_multiple_queues']:6d}")
    print(f"     unique blocking items:          {i['unique_blocking_items']:6d}")
    print(f"     unique HIGH-priority items:     {i['unique_high_priority_items']:6d}")
    print(f"     items requiring dual control:   {i['items_requiring_dual_control']:6d}")
    print(f"     items needing evidence first:   "
          f"{i['items_requiring_evidence_before_review']:6d}")
    print(f"     ESTIMATED HUMAN DECISIONS:      {i['estimated_human_decisions']:6d}"
          "   <- unique items, NOT queue memberships")
    print(f"     by domain: {i['by_domain']}")
    a = r["activation"]
    print("\n  ACTIVATION — everything must be zero:")
    for k in ("real_approval_events", "real_permission_grants",
              "retrieval_enabled_assets", "automatic_use_enabled_assets",
              "fonts_installed", "files_moved_or_deleted"):
        print(f"     {k:34s} {a[k]}")
    print(f"     all_zero: {a['all_zero']}")
    print(f"\n  vocabularies disjoint: "
          f"{r['dispositions']['vocabularies_disjoint']} | "
          f"old artifacts regenerated: "
          f"{r['milestone_artifacts']['regenerated_any_old_artifact']}")
    print(f"  integrity: materials_unchanged="
          f"{r['integrity']['materials']['unchanged']}")
    print(f"  runtime: {r['runtime_seconds']}s")


if __name__ == "__main__":
    raise SystemExit(main())
