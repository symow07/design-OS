"""Slice 4 — output writers + reconciliation. Never writes under materials/."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from . import config as C


def json_default(o):
    """Last-resort coercion so one malformed file cannot abort the whole run.

    Malformed fonts yield raw bytes where a string is specified; `fonts._safe_str`
    handles the known cases. Anything else still raises, so genuinely unexpected
    types surface rather than being silently swallowed.
    """
    if isinstance(o, bytes):
        return o.decode("latin-1", "replace")
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def _write_json(path: Path, obj) -> None:
    C.assert_output_safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False,
                               default=json_default))


def write_inventory(records: list[dict]) -> tuple[Path, Path]:
    jsonl = C.OUT_INVENTORY / "inventory.jsonl"
    C.assert_output_safe(jsonl)
    jsonl.parent.mkdir(parents=True, exist_ok=True)
    with open(jsonl, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, default=json_default) + "\n")

    csv_path = C.OUT_INVENTORY / "inventory.csv"
    C.assert_output_safe(csv_path)
    cols = ["relative_path", "filename", "extension", "mime", "signature",
            "size_bytes", "sha256", "mtime_iso", "category", "category_confidence",
            "category_source", "ownership_status", "license_status",
            "parser_status", "parser", "duplicate_group", "review_required",
            "review_reasons", "warnings"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in records:
            w.writerow({
                "relative_path": r["relative_path"], "filename": r["filename"],
                "extension": r["extension"],
                "mime": r.get("mime_detected", {}).get("value"),
                "signature": r.get("signature_kind", {}).get("value"),
                "size_bytes": r["size_bytes"], "sha256": r["sha256"],
                "mtime_iso": r["mtime_iso"],
                "category": r["category"]["value"],
                "category_confidence": r["category"]["confidence"],
                "category_source": r["category"]["source"],
                "ownership_status": r["ownership_status"]["value"],
                "license_status": r["license_status"]["value"],
                "parser_status": r["parser_support"]["status"],
                "parser": r["parser_support"]["parser"],
                "duplicate_group": r.get("duplicate_group") or "",
                "review_required": r["review_required"],
                "review_reasons": ";".join(r["review_reasons"]),
                "warnings": ";".join(r["warnings"]),
            })
    return jsonl, csv_path


def write_out_of_scope_review(records: list[dict]) -> Path:
    """Lightweight human-review sheet for the deliberately excluded files.

    Nothing here is deleted, moved or modified — the sheet exists so a person
    can confirm or overturn each exclusion before DIP-0B.
    """
    p = C.OUT_REPORTS / "out_of_scope_review.csv"
    C.assert_output_safe(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = [r for r in records if r["category"]["value"] == "OUT_OF_SCOPE"]
    rows.sort(key=lambda r: r["relative_path"])
    cols = ["relative_path", "filename", "detected_type", "size_bytes",
            "exclusion_rule", "evidence", "confidence",
            "recommended_disposition", "human_confirmed_disposition"]
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            cat = r["category"]
            # High-confidence, format-driven exclusions are safe to keep out;
            # rule-inferred ones (unrelated mockups) want a human eye.
            disposition = ("exclude_permanently" if cat["confidence"] >= 0.8
                           else "human_confirm_exclusion")
            w.writerow({
                "relative_path": r["relative_path"],
                "filename": r["filename"],
                "detected_type": (r.get("mime_detected", {}).get("value")
                                  or r["extension"]),
                "size_bytes": r["size_bytes"],
                "exclusion_rule": cat["source"],
                "evidence": " | ".join(cat["evidence"]),
                "confidence": cat["confidence"],
                "recommended_disposition": disposition,
                "human_confirmed_disposition": "",   # never machine-written
            })
    return p


def reconcile(records, walk_res, dupes, archives, fonts, integrity_before,
              integrity_after, hash_check, output_check) -> dict:
    by_ext = Counter(r["extension"] or "(no ext)" for r in records)
    by_cat = Counter(r["category"]["value"] for r in records)
    by_parser = Counter(r["parser_support"]["status"] for r in records)
    by_branch = Counter(r["relative_path"].split("/")[1] for r in records
                        if "/" in r["relative_path"])
    total_bytes = sum(r["size_bytes"] for r in records)

    return {
        "indexed_files": len(records),
        "excluded_junk": len(walk_res.junk),
        "junk_by_name": dict(Counter(j["filename"] for j in walk_res.junk)),
        "symlinks_recorded": len(walk_res.symlinks),
        "symlinks_escaping_root": sum(1 for s in walk_res.symlinks
                                      if s["escapes_source_root"]),
        "skipped_dirs": len(walk_res.skipped_dirs),
        "directories_walked": walk_res.dir_count,
        "walk_errors": walk_res.errors,
        "total_bytes": total_bytes,
        "counts_by_extension": dict(by_ext.most_common()),
        "counts_by_category": dict(by_cat.most_common()),
        "counts_by_parser_support": dict(by_parser.most_common()),
        "counts_by_branch": dict(by_branch.most_common()),
        "duplicates": {
            "groups": dupes["group_count"],
            "redundant_copies": dupes["redundant_copies"],
            "redundant_bytes": dupes["redundant_bytes"],
        },
        "archives": {
            "count": archives["archive_count"],
            "total_archive_bytes": archives["total_archive_bytes"],
            "total_expanded_bytes": archives["total_expanded_bytes"],
            "encrypted": len(archives["encrypted"]),
            "corrupt": len(archives["corrupt"]),
            "suspicious": len(archives["suspicious"]),
        },
        "fonts": {
            "files": fonts["font_file_count"], "parsed": fonts["parsed"],
            "parse_failed": fonts["parse_failed"],
            "quarantined": fonts["quarantined_count"],
            "distinct_families": fonts["distinct_families"],
        },
        "review_required": sum(1 for r in records if r["review_required"]),
        "integrity": {
            "source_tree": integrity_after,
            "hash_stability": hash_check,
            "output_outside_source": output_check,
            "files_before": integrity_before["file_count_before"]
            if "file_count_before" in integrity_before else len(integrity_before),
        },
    }


def compare_to_pre_audit(recon: dict, expected: dict) -> dict:
    """Report divergence from the pre-audit estimates instead of hiding it."""
    diffs = {}
    for k, exp in expected.items():
        actual = recon
        for part in k.split("."):
            actual = actual.get(part, {}) if isinstance(actual, dict) else None
        if isinstance(actual, dict):
            actual = None
        if actual != exp:
            diffs[k] = {"pre_audit_estimate": exp, "actual": actual,
                        "delta": (actual - exp) if isinstance(actual, (int, float))
                        and isinstance(exp, (int, float)) else None}
    return {"matches": not diffs, "differences": diffs}


def write_summary_md(recon, pilot, archives, fonts, dupes, divergence) -> Path:
    p = C.OUT_REPORTS / "summary.md"
    C.assert_output_safe(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    gb = lambda b: f"{b / 1e9:.2f} GB"                                  # noqa: E731

    lines = [
        "# DIP-0A — `materials/` master inventory",
        "",
        f"- Indexed files: **{recon['indexed_files']}**",
        f"- Excluded junk (counted, not deleted): **{recon['excluded_junk']}**",
        f"- Total indexed bytes: **{gb(recon['total_bytes'])}**",
        f"- Duplicate groups: **{recon['duplicates']['groups']}** "
        f"({recon['duplicates']['redundant_copies']} redundant copies, "
        f"{gb(recon['duplicates']['redundant_bytes'])} redundant)",
        f"- Files flagged for human review: **{recon['review_required']}**",
        f"- Symlinks recorded (never followed): {recon['symlinks_recorded']}",
        "",
        "`materials/` was treated as read-only. Nothing was renamed, moved, "
        "converted, deduplicated or deleted. No generated output was written "
        "beneath the source root.",
        "",
        "## Categories",
        "",
        "| Category | Files |", "|---|---|",
    ]
    for k, v in recon["counts_by_category"].items():
        lines.append(f"| {k} | {v} |")

    lines += ["", "## Parser support", "", "| Status | Files |", "|---|---|"]
    for k, v in recon["counts_by_parser_support"].items():
        lines.append(f"| {k} | {v} |")

    lines += ["", "## Extensions", "", "| Ext | Files |", "|---|---|"]
    for k, v in recon["counts_by_extension"].items():
        lines.append(f"| `{k}` | {v} |")

    lines += [
        "", "## Archives (manifest-only, never extracted)", "",
        f"- Archives: {recon['archives']['count']} "
        f"({gb(recon['archives']['total_archive_bytes'])} on disk, "
        f"~{gb(recon['archives']['total_expanded_bytes'])} expanded)",
        f"- Encrypted: {recon['archives']['encrypted']} · "
        f"Corrupt: {recon['archives']['corrupt']} · "
        f"Suspicious: {recon['archives']['suspicious']}",
        f"- Exact duplicate archives: {len(archives['exact_duplicate_archives'])} groups",
        f"- Probable duplicates by content manifest: "
        f"{len(archives['probable_duplicate_archives_by_manifest'])} groups",
        "",
        "## Font quarantine", "",
        f"- Font files: {recon['fonts']['files']} "
        f"(parsed {recon['fonts']['parsed']}, failed {recon['fonts']['parse_failed']})",
        f"- Quarantined under `{fonts['quarantine_branch']}`: "
        f"**{recon['fonts']['quarantined']}**",
        f"- {fonts['policy']}",
        "",
        "## Pilot manifest", "",
        f"- All mandated requirements met: **{pilot['all_requirements_met']}**",
    ]
    for k, v in pilot["requirements_met"].items():
        lines.append(f"  - {'✅' if v else '❌'} {k}")
    lines += ["", "## Divergence from pre-audit estimates", ""]
    if divergence["matches"]:
        lines.append("No divergence.")
    else:
        for k, d in divergence["differences"].items():
            lines.append(f"- `{k}`: estimate {d['pre_audit_estimate']} → "
                         f"actual {d['actual']}")

    lines += [
        "", "## Source-of-truth counts (supersede all earlier estimates)", "",
        f"- Indexed files: {recon['indexed_files']}",
        f"- Historical production designs: "
        f"{recon['counts_by_category'].get('HISTORICAL_DESIGN', 0)}",
        f"- Total `.ai` files: {recon['counts_by_extension'].get('.ai', 0)}",
        f"- Exact-duplicate groups: {recon['duplicates']['groups']}",
        f"- Redundant storage: {gb(recon['duplicates']['redundant_bytes'])}",
        f"- Font files: {recon['fonts']['files']} "
        f"(quarantined: {recon['fonts']['quarantined']})",
        f"- ZIP archives: {recon['archives']['count']}",
        f"- Excluded junk files: {recon['excluded_junk']}",
        "",
        "## Correction to the pre-audit estimates", "",
        "The pre-audit reported **~18 GB of ZIP archives**. That figure was "
        "wrong. A *directory* is literally named `25.10.15.zip`, so "
        "`find -name \"*.zip\"` matched the directory and `du` recursed into it, "
        "double-counting the two 3.57 GB archives stored inside. The correct "
        f"total, confirmed by `stat` and by this audit, is "
        f"**{gb(recon['archives']['total_archive_bytes'])}**. The derived "
        "pre-audit claim of an \"effective library of ~10 GB\" was wrong for the "
        "same reason; the non-archive material is ~18.2 GB.",
        "",
        "## Taxonomy (user-approved 2026-07-10)", "",
        "- `ARCHIVE` — transport/storage container. Inventoried, hashed, manifest-"
        "inspected; excluded from retrieval and generation; never auto-extracted. "
        "Its existence is not proof that its contents are licensed or approved.",
        "- `LICENSE_EVIDENCE` — supporting evidence linked to nearby assets/fonts. "
        "Never a reusable design asset; never auto-changes licence status.",
        "- `SUPPORTING_METADATA` (subtype `FONT_METADATA`) — provenance / font-"
        "management sidecars. Traceable, never in design retrieval.",
        "- `COLOR_PALETTE` — colour systems (`.ase` etc). Retrieval blocked until "
        "the DIP-0C/DIP-1 palette ingestion contract; auto-use blocked until "
        "parsed and human-approved.",
        "- `OUT_OF_SCOPE` — understood and deliberately excluded. Distinct from "
        "`UNKNOWN`, which is reserved for genuinely unidentified files.",
        "",
        "## Integrity", "",
        f"- Source tree unchanged: **{recon['integrity']['source_tree']['unchanged']}**",
        f"- Hash stability: {recon['integrity']['hash_stability']['mode']} → "
        f"stable={recon['integrity']['hash_stability']['stable']}",
        f"- Output outside source root: "
        f"{recon['integrity']['output_outside_source']['ok']}",
    ]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def write_all(records, walk_res, dupes, archives, fonts, pilot, recon,
              divergence) -> dict:
    jsonl, csvp = write_inventory(records)
    _write_json(C.OUT_REPORTS / "duplicates.json", dupes)
    _write_json(C.OUT_REPORTS / "archives.json", archives)
    _write_json(C.OUT_REPORTS / "fonts.json", fonts)
    _write_json(C.OUT_REPORTS / "reconciliation.json", recon)
    _write_json(C.OUT_REPORTS / "divergence.json", divergence)
    _write_json(C.OUT_MANIFESTS / "pilot_manifest.json", pilot)
    _write_json(C.OUT_INVENTORY / "symlinks.json", walk_res.symlinks)
    _write_json(C.OUT_INVENTORY / "excluded_junk.json", walk_res.junk)
    oos = write_out_of_scope_review(records)
    md = write_summary_md(recon, pilot, archives, fonts, dupes, divergence)
    return {"inventory_jsonl": str(jsonl), "inventory_csv": str(csvp),
            "summary_md": str(md), "out_of_scope_review": str(oos)}


def write_milestone_docs(recon, pilot, summary_md: Path) -> dict:
    """Commit-able milestone record: the summary + the pilot manifest only.

    The 7,586-row inventory, previews, caches and large duplicate reports stay
    under the ignored `var/` tree — regenerable from `materials/` at any time.
    """
    docs = C.REPO_ROOT / "docs" / "design_intelligence" / "dip0a"
    C.assert_output_safe(docs)
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "summary.md").write_text(summary_md.read_text(encoding="utf-8"),
                                     encoding="utf-8")
    (docs / "pilot_manifest.json").write_text(
        json.dumps(pilot, indent=1, ensure_ascii=False, default=json_default),
        encoding="utf-8")
    return {"docs_dir": str(docs)}
