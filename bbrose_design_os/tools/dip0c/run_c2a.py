"""DIP-0C2a runner — capability-aware segmentation over the frozen C2 pilot.

Read-only. Segments every pilot file into AssetCandidates, writes per-candidate
JSON to git-ignored var/, and emits a reconciliation report plus a lightweight
collection-sheet review manifest (validated JSON, not a UI). Materials integrity
is snapshotted before/after; the run exits non-zero on any change or if output
resolves inside the source tree, or if an invariant is violated (a machine
APPROVED_REUSABLE, or any retrieval/automatic-use flag flipped true).

    python -m tools.dip0c.run_c2a
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

from tools.dip0.integrity import compare, snapshot
from tools.dip0.report import json_default

from . import classify_override as co
from . import config as C
from . import segment


def _inventory_map() -> dict:
    path = (C.REPO_ROOT / "var" / "design_intelligence" / "audits" / "dip0"
            / "inventory" / "inventory.jsonl")
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["relative_path"]] = r
                if r.get("original_source_path"):            # Day 6 migration: the pilot names the original spelling
                    out.setdefault(r["original_source_path"], r)
    return out


def _kind(ext: str) -> str:
    if ext in (".ai", ".pdf"):
        return "pdf_backed"
    if ext == ".svg":
        return "svg"
    if ext == ".eps":
        return "eps"
    return "raster"


def _override_for(rel: str, ext: str, inv_rec: dict) -> dict | None:
    """Reuse C1's classification override for PDFs/EPS (never rewrites DIP-0A)."""
    fn = Path(rel).name
    orig = inv_rec.get("category", {}).get("value", "UNKNOWN") if inv_rec else "UNKNOWN"
    third = co.third_party_brand(fn)
    if ext == ".pdf":
        return co.classify_pdf(fn, page_count=1, first_page_text="",
                               original_category=orig, third_party=third)
    if ext == ".eps":
        return co.classify_pdf(fn, page_count=1, first_page_text="",
                               original_category=orig, third_party=third)
    ov = co.override_record(orig, None, "no reclassification indicated", [], 0.0)
    return ov


def segment_entry(entry: dict, inv: dict) -> dict:
    rel = entry["relative_path"]
    ext = (entry.get("format") or Path(rel).suffix).lower()
    inv_rec = inv.get(rel, {})
    source = {"relative_path": rel, "sha256": inv_rec.get("sha256"),
              "format": ext, "kind": _kind(ext)}
    override = _override_for(rel, ext, inv_rec)
    res = segment.segment_file(source, inv_rec, override=override)
    res["entry"] = {"c2_test_role": entry.get("c2_test_role"),
                    "expected_segmentation_capability":
                        entry.get("expected_segmentation_capability"),
                    "expected_family_relationship":
                        entry.get("expected_family_relationship")}
    return res


CONFIDENT_MEMBER_STATUS = (C.SEG_STATUS_SEGMENTED, C.SEG_STATUS_AUTO_CONFIDENT)


def _confident_members(r: dict) -> list[dict]:
    """Candidates that are CONFIDENT multi-asset members of one source surface —
    excludes low-confidence/manual raster fragments and per-artboard singles."""
    return [c for c in r["candidates"]
            if (c.get("collection") or {}).get("is_member")
            and c["segmentation"]["status"] in CONFIDENT_MEMBER_STATUS]


def build_review_manifest(results: list[dict]) -> dict:
    """Validated collection review JSON (not a UI). Every multi-candidate source
    is offered for split/merge/relabel/exclude, but tagged by confidence so a
    low-confidence raster (e.g. a fluid background split into regions) is NEVER
    presented as a confirmed sticker sheet — the reviewer sees the caveat."""
    confident, needs_confirmation = [], []
    for r in results:
        members = [c for c in r["candidates"]
                   if (c.get("collection") or {}).get("is_member")]
        if len(members) <= 1:
            continue
        row = {
            "parent_source": members[0]["source_file"]["relative_path"],
            "candidate_count": len(members),
            "candidate_ids": [c["candidate_id"] for c in members],
            "segmentation_statuses": sorted({c["segmentation"]["status"]
                                             for c in members}),
            "manual_actions_allowed": ["split", "merge", "relabel", "exclude"],
            "human_decision": None,   # blank — filled by a reviewer
        }
        if all(c["segmentation"]["status"] in CONFIDENT_MEMBER_STATUS
               for c in members):
            confident.append(row)
        else:
            row["caveat"] = ("low-confidence: regions may be parts of one "
                             "composition, not distinct assets — human must "
                             "confirm before treating as a collection")
            needs_confirmation.append(row)
    return {"slice": "DIP-0C2a",
            "confident_collection_splits": confident,
            "low_confidence_multi_region": needs_confirmation,
            "note": "validated review JSON; no machine reuse/ownership decision"}


def reconcile(results, integrity, runtime_s, out_bytes) -> dict:
    all_c = [c for r in results for c in r["candidates"]]
    by_status = Counter(c["segmentation"]["status"] for c in all_c)
    by_method = Counter(c["segmentation"]["method"] for c in all_c)
    file_status = Counter(r["file_status"] for r in results)
    per_source = {r["candidates"][0]["source_file"]["relative_path"]
                  if r["candidates"] else r["entry"]["c2_test_role"]:
                  len(r["candidates"]) for r in results}
    multi = {rel: n for rel, n in per_source.items() if n > 1}
    singles = {rel: n for rel, n in per_source.items() if n == 1}
    # a genuine collection sheet = CONFIDENT multi-asset split on one surface
    confident_sheets = {}
    multi_artboard = {}
    for r in results:
        if not r["candidates"]:
            continue
        rel = r["candidates"][0]["source_file"]["relative_path"]
        members = _confident_members(r)
        if len(members) > 1:
            confident_sheets[rel] = len(members)
        # multiple per-artboard NATURAL candidates (not one-surface split)
        elif len(r["candidates"]) > 1 and all(
                c["segmentation"]["method"] == C.SEG_METHOD_VECTOR_WHOLE_NATURAL
                for c in r["candidates"]):
            multi_artboard[rel] = len(r["candidates"])
    expected_vs_actual = _expected_vs_actual(results)

    blob = json.dumps(all_c, default=json_default)
    approved_leak = C.POSTURE_APPROVED_REUSABLE in blob
    retrieval_on = [c["candidate_id"] for c in all_c
                    if c["D_retrieval_eligibility"] or c["E_automatic_use_eligibility"]
                    or c["production_use"]]
    # Candidate IDs are unique WITHIN a source file. Identical bytes+config across
    # different files (the exact-dup fixture) legitimately share an id — that is
    # determinism, not a collision, and a signal C2c will use.
    per_file_dupe = []
    for r in results:
        ids_in_file = [c["candidate_id"] for c in r["candidates"]]
        if len(ids_in_file) != len(set(ids_in_file)):
            per_file_dupe.append(r["candidates"][0]["source_file"]["relative_path"]
                                 if r["candidates"] else "?")
    rights_granted = [c["candidate_id"] for c in all_c
                      if c["B_rights_readiness"]["commercial_use"]
                      or c["B_rights_readiness"]["modification"]
                      or c["B_rights_readiness"]["embedding"]
                      or c["B_rights_readiness"]["redistribution"]]
    # EPS candidates must carry NO geometry/editability keys
    geom_keys = {"editability", "editability_score", "path_count", "path_cleanliness",
                 "anchor_count", "clip_structure", "vector_raster_balance",
                 "recolorability"}
    eps_geom_leak = [c["candidate_id"] for c in all_c
                     if c["source_file"]["format"] == ".eps"
                     and (geom_keys & set(c) or geom_keys & set(c.get(
                         "segmentation_detail", {})))]
    human_dirty = [c["candidate_id"] for c in all_c
                   if any(c["human"][k] for k in ("category", "reviewed_by",
                                                  "reviewed_at"))]

    return {
        "slice": "DIP-0C2a",
        "pilot_files": len(results),
        "total_candidates": len(all_c),
        "candidates_by_segmentation_status": dict(by_status),
        "candidates_by_method": dict(by_method),
        "file_level_status": dict(file_status),
        "files_with_multiple_candidates": {Path(k).name: v
                                           for k, v in multi.items()},
        "confident_collection_splits": {Path(k).name: v
                                        for k, v in confident_sheets.items()},
        "multi_artboard_files": {Path(k).name: v
                                 for k, v in multi_artboard.items()},
        "single_candidate_files": len(singles),
        "expected_vs_actual": expected_vs_actual,
        "eps_preview_derived": by_status.get(C.SEG_STATUS_PREVIEW_DERIVED, 0),
        "eps_unavailable": sum(1 for c in all_c
                               if c["source_file"]["format"] == ".eps"
                               and c["segmentation"]["status"]
                               == C.SEG_STATUS_UNAVAILABLE),
        "raster_low_confidence": by_status.get(C.SEG_STATUS_AUTO_LOW_CONF, 0),
        "raster_manual_review": by_status.get(C.SEG_STATUS_MANUAL, 0),
        "invariants": {
            "no_approved_reusable": not approved_leak,
            "retrieval_and_auto_use_all_false": not retrieval_on,
            "no_rights_granted": not rights_granted,
            "eps_no_geometry_claims": not eps_geom_leak,
            "human_blocks_blank": not human_dirty,
            "candidate_ids_unique_per_file": not per_file_dupe,
        },
        "determinism_note": "identical source bytes + config yield identical "
                            "candidate ids across files (exact-dup signal), by "
                            "design; uniqueness is enforced within each file",
        "integrity": integrity,
        "runtime_seconds": round(runtime_s, 2),
        "output_bytes": out_bytes,
    }


# frozen manifest expectation -> the file_status values that satisfy it
_EXPECTED_TO_STATUS = {
    "VECTOR_GEOMETRY_MULTI": {C.SEG_STATUS_SEGMENTED},
    "WHOLE_FILE_SINGLE_ASSET": {C.SEG_STATUS_WHOLE_FILE},
    "VECTOR_GEOMETRY": {C.SEG_STATUS_SEGMENTED, C.SEG_STATUS_WHOLE_FILE},
    "RASTER_REGION_AUTO_CONFIDENT": {C.SEG_STATUS_AUTO_CONFIDENT},
    "RASTER_REGION_MULTI": {C.SEG_STATUS_AUTO_CONFIDENT, C.SEG_STATUS_AUTO_LOW_CONF},
    "RASTER_REGION_LOW_CONFIDENCE": {C.SEG_STATUS_AUTO_LOW_CONF, C.SEG_STATUS_MANUAL},
    "RASTER_REGION": {C.SEG_STATUS_AUTO_CONFIDENT, C.SEG_STATUS_AUTO_LOW_CONF,
                      C.SEG_STATUS_MANUAL},
    "UNAVAILABLE_PREVIEW_NOT_DECODABLE": {C.SEG_STATUS_UNAVAILABLE},
    "UNAVAILABLE": {C.SEG_STATUS_UNAVAILABLE},
}


def _expected_vs_actual(results: list[dict]) -> dict:
    """The payoff of freezing expectations: compare each entry's frozen
    expected_segmentation_capability against the actual file_status."""
    rows, mismatches = [], []
    for r in results:
        exp = r["entry"].get("expected_segmentation_capability")
        actual = r["file_status"]
        ok = actual in _EXPECTED_TO_STATUS.get(exp, set())
        row = {"role": r["entry"].get("c2_test_role"), "expected": exp,
               "actual_file_status": actual,
               "candidate_count": len(r["candidates"]), "match": ok}
        rows.append(row)
        if not ok:
            mismatches.append(row)
    return {"all_match": not mismatches, "mismatches": mismatches, "rows": rows}


def _no_output_under_source() -> dict:
    src = C.SOURCE_ROOT.resolve()
    out = C.OUTPUT_ROOT.resolve()
    inside = out == src or src in out.parents
    return {"output_root": str(out), "source_root": str(src),
            "output_inside_source": inside, "ok": not inside}


def main(argv=None) -> int:
    t0 = time.monotonic()
    C.ensure_output_dirs()
    pilot = C.load_c2_pilot()
    inv = _inventory_map()

    # Segment each unique source file once; a file serving several manifest roles
    # (e.g. 5955567.ai as jpeg-shell AND cross-format family member) is not
    # segmented twice. Roles are merged so provenance is preserved.
    unique: dict[str, dict] = {}
    for entry in pilot:
        rel = entry["relative_path"]
        if rel in unique:
            unique[rel].setdefault("_extra_roles", []).append(
                entry.get("c2_test_role"))
        else:
            unique[rel] = dict(entry)

    before = snapshot()
    results, out_bytes = [], 0
    for entry in unique.values():
        res = segment_entry(entry, inv)
        if entry.get("_extra_roles"):
            res["entry"]["also_serves_roles"] = entry["_extra_roles"]
        results.append(res)
        safe = entry["relative_path"].replace("/", "__")
        dest = C.OUT_CANDIDATES / f"{safe}.json"
        C.assert_output_safe(dest)
        payload = json.dumps(res, default=json_default, ensure_ascii=False, indent=2)
        dest.write_text(payload, encoding="utf-8")
        out_bytes += len(payload.encode("utf-8"))
    after = snapshot()

    integrity = {"materials": compare(before, after),
                 "no_output_under_source": _no_output_under_source()}
    recon = reconcile(results, integrity, time.monotonic() - t0, out_bytes)
    review = build_review_manifest(results)
    for name, obj in (("c2a_reconciliation.json", recon),
                      ("c2a_collection_review.json", review)):
        p = C.OUT_REPORTS / name
        C.assert_output_safe(p)
        p.write_text(json.dumps(obj, default=json_default, ensure_ascii=False,
                                indent=2), encoding="utf-8")

    inv_ok = all(recon["invariants"].values())
    ok = (integrity["materials"]["unchanged"]
          and integrity["no_output_under_source"]["ok"] and inv_ok
          and recon["expected_vs_actual"]["all_match"])
    _print_summary(recon)
    if not ok:
        print("\nFAILED: integrity or invariant violation", file=sys.stderr)
        return 1
    return 0


def _print_summary(r: dict) -> None:
    print(f"DIP-0C2a segmentation — {r['pilot_files']} files, "
          f"{r['total_candidates']} candidates")
    print(f"  by status:  {r['candidates_by_segmentation_status']}")
    print(f"  by method:  {r['candidates_by_method']}")
    print(f"  multi-cand: {r['files_with_multiple_candidates']}")
    print(f"  collections:{r['confident_collection_splits']}")
    print(f"  artboards:  {r['multi_artboard_files']}")
    print(f"  singles:    {r['single_candidate_files']}")
    print(f"  exp==actual:{r['expected_vs_actual']['all_match']} "
          f"(mismatches: {[m['role'] for m in r['expected_vs_actual']['mismatches']]})")
    print(f"  eps:        preview_derived={r['eps_preview_derived']} "
          f"unavailable={r['eps_unavailable']}")
    print(f"  raster:     low_conf={r['raster_low_confidence']} "
          f"manual={r['raster_manual_review']}")
    print(f"  invariants: {r['invariants']}")
    print(f"  integrity:  materials_unchanged="
          f"{r['integrity']['materials']['unchanged']} "
          f"output_outside_source={r['integrity']['no_output_under_source']['ok']}")
    print(f"  runtime:    {r['runtime_seconds']}s, output {r['output_bytes']} bytes")


if __name__ == "__main__":
    raise SystemExit(main())
