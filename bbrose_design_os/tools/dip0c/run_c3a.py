"""DIP-0C3a runner — brand/logo technical + relationship audit.

Read-only. Audits the frozen 21-file C3 pilot for TECHNIQUE and RELATIONSHIPS only.
It infers **no** ownership, licence, canonical status or permission: those are C3b/
C3d, and `BBROSE_OWNED_CONFIRMED`, `LICENSE_APPROVED` and `CANONICAL_BRAND_MASTER`
are human-only and unreachable from machine code (guarded in `config`).

    python -m tools.dip0c.run_c3a
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter

from tools.dip0.integrity import compare, snapshot
from tools.dip0.report import json_default

from . import brand, brand_rel, config as C

PARSER = f"{C.TOOL_NAME}.run_c3a/{C.TOOL_VERSION}"

HUMAN_ONLY = (C.OWN_BBROSE_CONFIRMED, C.LIC_APPROVED, C.CANONICAL_BRAND_MASTER,
              C.POSTURE_APPROVED_REUSABLE)


def reconcile(records, edges, integrity, runtime_s, out_bytes) -> dict:
    overrides = [r for r in records if r.get("classification_override")]
    nominations = [r for r in records
                   if r.get("brand_master_candidate") == C.BRAND_MASTER_CANDIDATE]
    third_party = [r for r in records
                   if (r.get("detected_third_party_brand") or {}).get("value")]
    direct = [r for r in records
              if r.get("brand_name", {}).get("tier") == C.TIER_DIRECT
              and r["brand_name"]["value"]]
    outlined = [r for r in records
                if (r.get("outlined_wordmark_likelihood") or {}).get("value")]
    isolated = [r for r in records
                if (r.get("isolated_logo_likelihood") or {}).get("value")]
    compositions = [r for r in records
                    if (r.get("raster_heavy_composition") or {}).get("value")]

    blob = json.dumps({"r": records, "e": edges}, default=json_default)
    leaks = [s for s in HUMAN_ONLY if s in blob]
    perms_on = [r["filename"] for r in records
                if any(v is True for k, v in r["permissions"].items())]
    # a composition or a third-party mark must NEVER be nominated
    bad_nom = [r["filename"] for r in nominations
               if (r.get("raster_heavy_composition") or {}).get("value")
               or (r.get("detected_third_party_brand") or {}).get("value")]
    # DIP-0A must not have been rewritten
    dip0a_kept = all(o["classification_override"]["inventory_category_original"]
                     == "BRAND_MASTER" for o in overrides)
    human_dirty = [r["filename"] for r in records
                   if any(v not in (None, "") for v in r["human"].values())]

    rel_types = Counter(h["relationship"] for e in edges for h in e["hypotheses"])

    return {
        "slice": "DIP-0C3a",
        "c2_milestone_commit": "c3756222b1771e6ea5b7a5c92c90267a6e6f8675",
        "pilot_files": len(records),
        "pilot_by_role": dict(Counter(r["c3_test_role"] for r in records)),
        "pilot_by_format": dict(Counter(r["format"] for r in records)),
        "classification_overrides": [
            {"file": r["filename"],
             "original": r["classification_override"]["inventory_category_original"],
             "override": r["classification_override"]["audit_category_override"],
             "reuse_posture": r["classification_override"]["reuse_posture"],
             "confidence": r["classification_override"]["override_confidence"],
             "cannot_be_canonical_master":
                 r["classification_override"]["cannot_be_canonical_master"],
             "evidence": r["classification_override"]["override_evidence"]}
            for r in overrides],
        "brand_names_from_live_text": [
            {"file": r["filename"], "brand_name": r["brand_name"]["value"],
             "tier": r["brand_name"]["tier"]} for r in direct],
        "outlined_wordmarks_requiring_human": [
            r["filename"] for r in outlined],
        "isolated_logo_candidates": [r["filename"] for r in isolated],
        "raster_heavy_design_compositions": [r["filename"] for r in compositions],
        "third_party_candidates": [
            {"file": r["filename"],
             "brand": r["detected_third_party_brand"]["value"],
             "tier": r["detected_third_party_brand"]["tier"],
             "in_bbrose_office_folder":
                 r["name_and_folder_evidence"]["folder_is_bbrose_office"]}
            for r in third_party],
        "brand_master_candidate_nominations": [r["filename"] for r in nominations],
        "relationship_edges": len(edges),
        "relationship_hypotheses": dict(rel_types),
        "queue_i_files": sum(1 for r in records
                             if r["queue_i_membership"]["in_queue_i"]),
        "machine_guards": {
            "human_only_states_absent_from_output": not leaks,
            "leaked_states": leaks,
            "all_permissions_false": not perms_on,
            "no_composition_or_third_party_nominated": not bad_nom,
            "dip0a_classification_preserved": dip0a_kept,
            "human_fields_blank": not human_dirty,
            "ownership_not_assessed_in_c3a": all(
                r["ownership"]["status"] == "NOT_ASSESSED_IN_C3A"
                for r in records),
            "license_not_assessed_in_c3a": all(
                r["license"]["status"] == "NOT_ASSESSED_IN_C3A"
                for r in records),
        },
        "integrity": integrity,
        "runtime_seconds": round(runtime_s, 2),
        "output_bytes": out_bytes,
    }


def _no_output_under_source() -> dict:
    src, out = C.SOURCE_ROOT.resolve(), C.C3A_OUTPUT_ROOT.resolve()
    inside = out == src or src in out.parents
    return {"output_root": str(out), "source_root": str(src), "ok": not inside}


def main(argv=None) -> int:
    t0 = time.monotonic()
    C.ensure_output_dirs()
    C.assert_output_safe(C.OUT_C3A)
    C.assert_output_safe(C.OUT_C3A_REPORTS)
    C.OUT_C3A.mkdir(parents=True, exist_ok=True)
    C.OUT_C3A_REPORTS.mkdir(parents=True, exist_ok=True)
    pilot = brand.load_pilot()

    before = snapshot()
    records = [brand.audit(e) for e in pilot]
    edges = brand_rel.build(records)
    after = snapshot()

    out_bytes = 0
    for name, obj in (("brand_candidates.json", records),
                      ("brand_relationships.json", edges)):
        p = C.OUT_C3A / name
        C.assert_output_safe(p)
        payload = json.dumps(obj, default=json_default, ensure_ascii=False,
                             indent=2)
        p.write_text(payload, encoding="utf-8")
        out_bytes += len(payload.encode("utf-8"))

    integrity = {"materials": compare(before, after),
                 "no_output_under_source": _no_output_under_source()}
    recon = reconcile(records, edges, integrity, time.monotonic() - t0, out_bytes)
    p = C.OUT_C3A_REPORTS / "c3a_reconciliation.json"
    C.assert_output_safe(p)
    p.write_text(json.dumps(recon, default=json_default, ensure_ascii=False,
                            indent=2), encoding="utf-8")

    ok = (integrity["materials"]["unchanged"]
          and integrity["no_output_under_source"]["ok"]
          and all(recon["machine_guards"][k] for k in recon["machine_guards"]
                  if isinstance(recon["machine_guards"][k], bool)))
    _print(recon)
    if not ok:
        print("\nFAILED: integrity or machine-guard violation", file=sys.stderr)
        return 1
    return 0


def _print(r: dict) -> None:
    print(f"DIP-0C3a — {r['pilot_files']} pilot files "
          f"({r['queue_i_files']} from Queue I)")
    print(f"  overrides:  {[(o['file'], o['override']) for o in r['classification_overrides']]}")
    print(f"  brand names (live text): "
          f"{[(b['file'], b['brand_name']) for b in r['brand_names_from_live_text']]}")
    print(f"  outlined -> human: {r['outlined_wordmarks_requiring_human']}")
    print(f"  isolated logos:    {r['isolated_logo_candidates']}")
    print(f"  compositions:      {r['raster_heavy_design_compositions']}")
    print(f"  third-party:       "
          f"{[(t['file'], t['brand']) for t in r['third_party_candidates']]}")
    print(f"  nominations:       {r['brand_master_candidate_nominations']}")
    print(f"  relationships:     {r['relationship_edges']} edges "
          f"{r['relationship_hypotheses']}")
    print(f"  guards:     {r['machine_guards']}")
    print(f"  integrity:  materials_unchanged="
          f"{r['integrity']['materials']['unchanged']}")
    print(f"  runtime:    {r['runtime_seconds']}s, output {r['output_bytes']} bytes")


if __name__ == "__main__":
    raise SystemExit(main())
