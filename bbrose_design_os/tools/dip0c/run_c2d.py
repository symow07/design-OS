"""DIP-0C2d runner — batchable human-review manifest, queues, reconciliation.

Read-only. Re-runs C2a→C2c in-process, then organises the result for a human:
distinct group types (a collection group is NOT a duplicate family), an
UNKNOWN_RELATIONSHIP review queue grouped by shared reason, EPS marked
VISUAL_COMPARISON_UNAVAILABLE (never "unrelated"), and nine batchable queues with
priorities and reasons.

Nothing is decided. Every human field is blank, machine inference is immutable,
and no batch decision is applied automatically.

    python -m tools.dip0c.run_c2d
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict

from tools.dip0.integrity import compare, snapshot
from tools.dip0.report import json_default

from . import canonical, config as C, families, review_c2d as RV
from . import run_c2a, run_c2c

PARSER = f"{C.TOOL_NAME}.run_c2d/{C.TOOL_VERSION}"


def _queue(qid, items, reason, action, priority, *, batchable) -> dict:
    return {
        "queue": qid,
        "items": len(items),
        "shared_review_reason": reason,
        "recommended_reviewer_action": action,
        "priority": priority,
        "affected": items,
        "one_decision_may_apply_to_group": batchable,
        "batch_decision_applied": False,   # NEVER applied automatically
    }


def build_queues(rows, groups, noms, cand_edges, comps, cands, blocking) -> list:
    by_id = {c["candidate_id"]: c for c in cands}
    qs = []

    exact = [g for g in groups if g["group_type"] == C.GROUP_EXACT_DUPLICATE]
    qs.append(_queue(
        C.QUEUE_EXACT_DUPLICATES, [g["group_id"] for g in exact],
        "byte-identical FILES exist in more than one location",
        "Choose which copy is canonical. Originals are never deleted by the "
        "system; nothing is consolidated automatically.",
        C.PRIORITY_HIGH, batchable=True))

    coll = [g for g in groups if g["group_type"] == C.GROUP_COLLECTION]
    qs.append(_queue(
        C.QUEUE_COLLECTION_GROUPS, [g["group_id"] for g in coll],
        "candidates segmented from ONE source surface",
        "Review the sheet together, then confirm/split/merge/relabel/exclude each "
        "candidate. NOTE: these are independent assets reviewed together — they "
        "are NOT duplicates and NOT substitutes for one another.",
        C.PRIORITY_MEDIUM, batchable=False))

    xf = [g for g in groups if g["group_type"] == C.GROUP_CROSS_FORMAT]
    qs.append(_queue(
        C.QUEUE_CROSS_FORMAT, [g["group_id"] for g in xf],
        "one artwork carried in several FORMATS",
        "Confirm the source relationship. Each member keeps its OWN technical "
        "readiness, capabilities and rights — no member inherits another's.",
        C.PRIORITY_HIGH, batchable=False))

    # D — UNKNOWN, grouped BY SHARED REASON so nobody inspects N edges one by one
    unknown = [e for e in cand_edges
               if e["primary"] == C.CAND_UNKNOWN_RELATIONSHIP]
    by_reason = defaultdict(list)
    for e in unknown:
        a, b = by_id.get(e["a"]), by_id.get(e["b"])
        if not (a and b):
            continue
        r = RV.unknown_reason(e, a, b)
        e["_unknown_reason"] = r
        by_reason[r].append({"a": e["a"], "b": e["b"],
                             "confidence": e["confidence"]})
    for reason, items in sorted(by_reason.items()):
        qs.append(_queue(
            f"{C.QUEUE_UNKNOWN}/{reason}", items,
            f"UNKNOWN_RELATIONSHIP — {reason}. A comparison WAS generated; the "
            "available evidence was insufficient. This is a review queue, NOT "
            "positive family evidence.",
            RV.UNKNOWN_REASON_ACTION[reason],
            C.PRIORITY_MEDIUM, batchable=True))

    qs.append(_queue(
        C.QUEUE_CANONICAL, [n["nominated_candidate_id"] for n in noms
                            if n.get("nominated_candidate_id")],
        "a technical CANONICAL_CANDIDATE was nominated",
        "Select (or reject) the canonical asset. The machine only nominates; "
        "rights evidence contributed ZERO to the nomination score.",
        C.PRIORITY_HIGH, batchable=False))

    eps = [r["machine"]["candidate_id"] for r in rows
           if r["machine"]["dhash"] is None]
    qs.append(_queue(
        C.QUEUE_EPS_UNAVAILABLE, eps,
        f"{C.VISUAL_COMPARISON_UNAVAILABLE}: no perceptual hash could be computed",
        "Do NOT read these as visually unrelated — the comparison could not be "
        "made. Source/package relationships still apply. Visual judgement waits "
        "for Ghostscript.",
        C.PRIORITY_MEDIUM, batchable=True))

    low = [r["machine"]["candidate_id"] for r in rows
           if (r["machine"]["information_score"] or {}).get("weak_evidence")]
    qs.append(_queue(
        C.QUEUE_LOW_INFORMATION, low,
        "the image carries too little visual information for a hash to be trusted",
        "Judge by eye, or exclude from the reusable library.",
        C.PRIORITY_MEDIUM, batchable=True))

    qs.append(_queue(
        C.QUEUE_WEAK_BRIDGES,
        [{"a": w["a"], "b": w["b"], "confidence": w["confidence"]}
         for w in comps["weak_bridges"]],
        "a low-confidence edge was the SOLE connector between two halves of a "
        "component; the component was split there",
        "Confirm whether the two halves are really one family, or correctly split.",
        C.PRIORITY_HIGH, batchable=False))

    blocked = [r["machine"]["candidate_id"] for r in rows
               if r["machine"]["technical_readiness"] in (
                   C.READY_TECHNICALLY_READY,
                   C.READY_TECHNICALLY_USABLE_WITH_CAVEATS)]
    qs.append(_queue(
        C.QUEUE_RIGHTS_BLOCKED, blocked,
        "technically strong, but ownership is unconfirmed and licence unverified",
        "Confirm ownership/licence. Until then the asset is UNUSABLE regardless of "
        "how technically clean it is.",
        C.PRIORITY_HIGH, batchable=False))
    return qs


def reconcile(rows, groups, queues, cand_edges, src_edges, noms, comps, blocking,
              c2c, integrity, runtime_s, out_bytes) -> dict:
    gtypes = Counter(g["group_type"] for g in groups)
    prio = Counter(r["machine"]["review_priority"] for r in rows)
    unknown_reasons = Counter(e.get("_unknown_reason") for e in cand_edges
                              if e["primary"] == C.CAND_UNKNOWN_RELATIONSHIP)
    eps_rows = [r for r in rows if r["machine"]["dhash"] is None]

    # invariants
    human_dirty = [r["machine"]["candidate_id"] for r in rows
                   if any(v not in (None, "") for v in r["human"].values())]
    auto_batch = [q["queue"] for q in queues if q["batch_decision_applied"]]
    canonical_selected = [n for n in noms if n.get("human_selected_canonical")]
    rights_moved = [r["machine"]["candidate_id"] for r in rows
                    if r["machine"]["retrieval_eligibility"]
                    or r["machine"]["automatic_use_eligibility"]
                    or any(r["machine"]["rights_status"][k] for k in
                           ("commercial_use", "modification", "embedding",
                            "redistribution"))]
    # a COLLECTION_GROUP must never be typed as a duplicate/visual family
    mislabelled = [g["group_id"] for g in groups
                   if g["group_type"] == C.GROUP_COLLECTION
                   and "DUPLICATE" in g["group_id"].upper()]
    eps_unrelated = [r["machine"]["candidate_id"] for r in eps_rows
                     if not any(C.VISUAL_COMPARISON_UNAVAILABLE in x
                                for x in r["machine"]["capability_limitations"])]
    # UNKNOWN must never appear as a visual family
    unknown_as_family = [g["group_id"] for g in groups
                         if g["group_type"] == C.GROUP_VISUAL_FAMILY
                         and not any(
                             h["relationship"] in (C.CAND_EXACT_VISUAL_DUPLICATE,
                                                   C.CAND_LIKELY_NEAR_DUPLICATE)
                             for e in cand_edges
                             if e["a"] in g["members"] and e["b"] in g["members"]
                             for h in e["hypotheses"])]

    workload = {
        "manifest_rows": len(rows),
        "high": prio.get(C.PRIORITY_HIGH, 0),
        "medium": prio.get(C.PRIORITY_MEDIUM, 0),
        "low": prio.get(C.PRIORITY_LOW, 0),
        "optional": prio.get(C.PRIORITY_OPTIONAL, 0),
        "batchable_queues": sum(1 for q in queues
                                if q["one_decision_may_apply_to_group"]),
        "estimated_decisions_if_batched": sum(
            1 if q["one_decision_may_apply_to_group"] else q["items"]
            for q in queues),
        "estimated_decisions_if_one_by_one": sum(q["items"] for q in queues),
    }

    return {
        "slice": "DIP-0C2d",
        "c2c_commit": "f845582c199481a5ade414fffe46315edfd334a1",
        "manifest_rows": len(rows),
        "groups_by_type": dict(gtypes),
        "exact_duplicate_groups": gtypes.get(C.GROUP_EXACT_DUPLICATE, 0),
        "collection_groups": gtypes.get(C.GROUP_COLLECTION, 0),
        "source_package_families": gtypes.get(C.GROUP_SOURCE_PACKAGE, 0),
        "cross_format_source_families": gtypes.get(C.GROUP_CROSS_FORMAT, 0),
        "visual_families": gtypes.get(C.GROUP_VISUAL_FAMILY, 0),
        "unknown_relationship_totals": {
            "edges": sum(unknown_reasons.values()),
            "by_reason": dict(unknown_reasons),
        },
        "eps_visual_comparison_unavailable": len(eps_rows),
        "canonical_candidate_reviews": len(noms),
        "weak_bridges": len(comps["weak_bridges"]),
        "priority_totals": dict(prio),
        "estimated_human_review_workload": workload,
        "queues": [{k: q[k] for k in ("queue", "items", "priority",
                                      "one_decision_may_apply_to_group")}
                   for q in queues],
        "blocking_coverage_limitation": {
            "max_bucket_members": blocking["max_bucket_members"],
            "skipped_bucket_count": blocking["skipped_bucket_count"],
            "skipped_buckets": blocking["skipped_buckets"],
            "coverage_note": blocking["coverage_note"],
            "reason_for_the_limit": (
                "an unbounded bucket explodes into O(n^2) pairs; the limit keeps "
                "candidate generation tractable without returning to naive "
                "all-pairs comparison"),
        },
        # totals must reconcile with C2c
        "reconciles_with_c2c": {
            "candidates": c2c["candidates"] == len(rows),
            "c2c_candidates": c2c["candidates"],
            "c2d_manifest_rows": len(rows),
            "exact_duplicate_edges": c2c["source_exact_duplicate_edges"],
            "c2c_components": c2c["family_components"],
            "c2d_candidate_groups": (gtypes.get(C.GROUP_COLLECTION, 0)
                                     + gtypes.get(C.GROUP_VISUAL_FAMILY, 0)),
        },
        "invariants": {
            "all_human_fields_blank": not human_dirty,
            "no_batch_decision_applied": not auto_batch,
            "no_automatic_canonical_selection": not canonical_selected,
            "no_rights_or_permissions_propagated": not rights_moved,
            "collection_groups_not_labelled_duplicate_families": not mislabelled,
            "eps_marked_unavailable_not_unrelated": not eps_unrelated,
            "unknown_never_becomes_a_visual_family": not unknown_as_family,
            "components_match_c2c": (gtypes.get(C.GROUP_COLLECTION, 0)
                                     + gtypes.get(C.GROUP_VISUAL_FAMILY, 0)
                                     == c2c["family_components"]),
        },
        "integrity": integrity,
        "runtime_seconds": round(runtime_s, 2),
        "output_bytes": out_bytes,
    }


def _no_output_under_source() -> dict:
    src, out = C.SOURCE_ROOT.resolve(), C.OUTPUT_ROOT.resolve()
    inside = out == src or src in out.parents
    return {"output_root": str(out), "source_root": str(src), "ok": not inside}


def main(argv=None) -> int:
    t0 = time.monotonic()
    C.ensure_output_dirs()
    for d in (C.OUT_C2C, C.OUT_C2D):
        C.assert_output_safe(d)
        d.mkdir(parents=True, exist_ok=True)
    pilot = C.load_c2_pilot()
    inv = run_c2a._inventory_map()

    before = snapshot()
    sources, cands = run_c2c.collect(pilot, inv)
    src_edges = families.source_edges(sources)
    cand_edges, blocking = run_c2c.build_candidate_edges(cands)
    comps = families.build_components([c["candidate_id"] for c in cands],
                                      cand_edges)
    by_id = {c["candidate_id"]: c for c in cands}
    noms = [canonical.nominate(comp, by_id) for comp in comps["components"]]

    groups = RV.build_groups(sources, cands, src_edges, cand_edges,
                             comps["components"])
    rows = RV.build_rows(cands, cand_edges, groups, noms, blocking)
    queues = build_queues(rows, groups, noms, cand_edges, comps, cands, blocking)
    # priorities are recomputed once the UNKNOWN reasons are attached by the queues
    rows = RV.build_rows(cands, cand_edges, groups, noms, blocking)
    after = snapshot()

    c2c = json.loads((C.OUT_REPORTS / "c2c_reconciliation.json")
                     .read_text(encoding="utf-8"))
    integrity = {"materials": compare(before, after),
                 "no_output_under_source": _no_output_under_source()}
    recon = reconcile(rows, groups, queues, cand_edges, src_edges, noms, comps,
                      blocking, c2c, integrity, time.monotonic() - t0, 0)

    out_bytes = 0
    for name, obj in (("review_manifest.json", rows),
                      ("review_queues.json", queues),
                      ("groups.json", groups)):
        p = C.OUT_C2D / name
        C.assert_output_safe(p)
        payload = json.dumps(obj, default=json_default, ensure_ascii=False,
                             indent=2)
        p.write_text(payload, encoding="utf-8")
        out_bytes += len(payload.encode("utf-8"))
    recon["output_bytes"] = out_bytes

    p = C.OUT_REPORTS / "c2d_reconciliation.json"
    C.assert_output_safe(p)
    p.write_text(json.dumps(recon, default=json_default, ensure_ascii=False,
                            indent=2), encoding="utf-8")

    ok = (integrity["materials"]["unchanged"]
          and integrity["no_output_under_source"]["ok"]
          and all(recon["invariants"].values()))
    _print(recon)
    if not ok:
        print("\nFAILED: integrity or invariant violation", file=sys.stderr)
        return 1
    return 0


def _print(r: dict) -> None:
    print(f"DIP-0C2d — {r['manifest_rows']} manifest rows")
    print(f"  groups:     {r['groups_by_type']}")
    print(f"  UNKNOWN:    {r['unknown_relationship_totals']['edges']} edges "
          f"by reason {r['unknown_relationship_totals']['by_reason']}")
    print(f"  eps unavail:{r['eps_visual_comparison_unavailable']}")
    print(f"  canonical:  {r['canonical_candidate_reviews']}")
    print(f"  priorities: {r['priority_totals']}")
    w = r["estimated_human_review_workload"]
    print(f"  workload:   {w['estimated_decisions_if_batched']} batched vs "
          f"{w['estimated_decisions_if_one_by_one']} one-by-one")
    print(f"  blocking:   skipped={r['blocking_coverage_limitation']['skipped_bucket_count']} "
          f"({r['blocking_coverage_limitation']['coverage_note'][:48]}…)")
    print(f"  reconciles: {r['reconciles_with_c2c']}")
    print(f"  invariants: {r['invariants']}")
    print(f"  integrity:  materials_unchanged="
          f"{r['integrity']['materials']['unchanged']}")
    print(f"  runtime:    {r['runtime_seconds']}s, output {r['output_bytes']} bytes")


if __name__ == "__main__":
    raise SystemExit(main())
