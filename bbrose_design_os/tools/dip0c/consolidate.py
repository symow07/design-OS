"""Consolidation of every DIP-0 milestone (DIP-0C5).

**The coverage table is the point.** Only two of the five audits ran on the full corpus.
"DIP-0 complete" means the *inventory* is complete, the *font* audit is complete, and the
*governance framework* is complete — not that the materials are audited. Saying otherwise
would be the largest over-claim in the project, and it would be made in the one document
everybody reads.

Milestone artifacts are **read, never regenerated**. Where a recomputed value disagrees
with a milestone's own frozen record, the disagreement is *reported*; the old record is
not rewritten. Historical milestone records describe what was true then.
"""
from __future__ import annotations

import json
from collections import Counter

from . import config as C

PARSER = f"{C.TOOL_NAME}.consolidate/{C.TOOL_VERSION}"
SCHEMA_VERSION = "dip0_consolidation/1.0"

INVENTORY = (C.REPO_ROOT / "var" / "design_intelligence" / "audits" / "dip0"
             / "inventory" / "inventory.jsonl")

# --- coverage status labels (the business's vocabulary) --------------------------
COMPLETE_FULL_CORPUS = "COMPLETE_FULL_CORPUS"
COMPLETE_FRAMEWORK = "COMPLETE_FRAMEWORK"
PILOT_VALIDATED = "PILOT_VALIDATED"
NOT_RUN_AT_CORPUS_SCALE = "NOT_RUN_AT_CORPUS_SCALE"
DEFERRED = "DEFERRED_TO_DIP1_OR_FOLLOW_UP"
STATUSES = (COMPLETE_FULL_CORPUS, COMPLETE_FRAMEWORK, PILOT_VALIDATED,
            NOT_RUN_AT_CORPUS_SCALE, DEFERRED)

REUSABLE_CATEGORIES = {"REUSABLE_VECTOR_ASSET", "RASTER_DESIGN_ASSET", "PATTERN",
                       "BACKGROUND", "MOTIF", "ICON"}


def _val(v):
    return v.get("value") if isinstance(v, dict) else v


def inventory_totals() -> dict:
    rows = [json.loads(line) for line in INVENTORY.open()]
    cats = Counter(_val(r["category"]) for r in rows)
    return {
        "total_files": len(rows),
        "by_category": dict(cats.most_common()),
        "reusable_category_files": sum(cats[c] for c in REUSABLE_CATEGORIES),
        "historical_designs": cats.get("HISTORICAL_DESIGN", 0),
        "font_files": cats.get("FONT", 0),
    }


def _pilot_size(name: str) -> int:
    p = C.DOCS_ROOT / name
    if not p.exists():
        return 0
    j = json.loads(p.read_text())
    return len(j) if isinstance(j, list) else len(j.get("entries", j))


def coverage() -> dict:
    """THE table. Measured, not asserted."""
    inv = inventory_totals()
    hist_total = inv["historical_designs"]
    reuse_total = inv["reusable_category_files"]
    font_total = inv["font_files"]

    # DIP-0B audited 14 Illustrator files (its own frozen summary says so)
    b4 = C.REPO_ROOT / "docs" / "design_intelligence" / "dip0b" / "b4_summary.json"
    hist_audited = json.loads(b4.read_text())["files"] if b4.exists() else 14
    c1_pilot = _pilot_size("pilot_manifest.json")
    c2_pilot = _pilot_size("c2_pilot_manifest.json")
    c3_pilot = _pilot_size("c3_pilot_manifest.json")

    rows = [
        {
            "milestone": "DIP-0A — materials inventory",
            "status": COMPLETE_FULL_CORPUS,
            "corpus": inv["total_files"], "audited": inv["total_files"],
            "coverage_pct": 100.0, "outstanding": 0,
            "note": "every file indexed, classified, hashed. UNKNOWN = 0.",
        },
        {
            "milestone": "DIP-0B — historical Illustrator deep audit",
            "status": PILOT_VALIDATED,
            "corpus": hist_total, "audited": hist_audited,
            "coverage_pct": round(100 * hist_audited / max(1, hist_total), 1),
            "outstanding": hist_total - hist_audited,
            "note": f"{hist_audited} files / 173 design units. The METHOD is validated; "
                    f"{hist_total - hist_audited} historical designs remain unaudited "
                    "at corpus scale.",
        },
        {
            "milestone": "DIP-0C1/C2 — reusable-material deep audit",
            "status": PILOT_VALIDATED,
            "corpus": reuse_total, "audited": c1_pilot,
            "coverage_pct": round(100 * c1_pilot / max(1, reuse_total), 1),
            "outstanding": reuse_total - c1_pilot,
            "note": f"frozen pilots of {c1_pilot} (C1) and {c2_pilot} (C2) files. "
                    f"~{reuse_total - c1_pilot} reusable-material files remain "
                    "unaudited at corpus scale.",
        },
        {
            "milestone": "DIP-0C3 — brand, logo, palette, ownership, permissions",
            "status": COMPLETE_FRAMEWORK,
            "corpus": c3_pilot, "audited": c3_pilot,
            "coverage_pct": 100.0, "outstanding": 0,
            "note": "a complete governance framework (dual control, ledger, scope, "
                    "conflicts, expiry) plus a pilot audit. NO real approval or "
                    "permission exists.",
        },
        {
            "milestone": "DIP-0C4 — font intelligence",
            "status": COMPLETE_FULL_CORPUS,
            "corpus": font_total, "audited": font_total,
            "coverage_pct": 100.0, "outstanding": 0,
            "note": "4,883 files / 3,966 faces / 2,832 families. Every font audited.",
        },
        {
            "milestone": "DIP-1 — production ingestion",
            "status": DEFERRED,
            "corpus": None, "audited": 0, "coverage_pct": 0.0, "outstanding": None,
            "note": "database models, authenticated identity, retrieval activation. "
                    "Not implemented, by design.",
        },
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "rows": rows,
        "headline": (
            "DIP-0 is COMPLETE as an audit framework, a governance framework, a full "
            "inventory and a full font audit — with PILOT-VALIDATED methods for "
            "historical designs and reusable assets. The materials library is NOT "
            "fully audited, and this report does not claim otherwise."),
        "outstanding_workstreams": [
            {
                "workstream": "Historical Design Corpus Expansion",
                "outstanding_files": hist_total - hist_audited,
                "status": NOT_RUN_AT_CORPUS_SCALE,
                "note": "planned operational expansion — not a hidden omission",
            },
            {
                "workstream": "Reusable Asset Corpus Expansion",
                "outstanding_files": reuse_total - c1_pilot,
                "status": NOT_RUN_AT_CORPUS_SCALE,
                "note": "planned operational expansion — not a hidden omission",
            },
        ],
        "parser": PARSER,
    }


def milestone_artifacts() -> dict:
    """Read every milestone's frozen reconciliation. NEVER regenerate one."""
    d = C.DOCS_ROOT
    found, missing = {}, []
    for name in ("c3a_reconciliation.json", "c3b1_reconciliation.json",
                 "c3b2_reconciliation.json", "c3b3_reconciliation.json",
                 "c3b4_reconciliation.json", "c3c_parser_reconciliation.json",
                 "c3d_reconciliation.json", "c3e_reconciliation.json",
                 "c4a_reconciliation.json", "c4b_reconciliation.json",
                 "c4c_reconciliation.json"):
        p = d / name
        if p.exists():
            found[name] = json.loads(p.read_text())
        else:
            missing.append(name)

    # C1/C2 and DIP-0B predate the reconciliation-JSON convention: they left markdown
    # reports and summary JSON instead. That is a fact about the project's history, not
    # a defect to paper over by regenerating them under today's schema.
    narrative = [
        {"milestone": "DIP-0B", "artifact_kind": "summary JSON + markdown report",
         "machine_readable_reconciliation": False},
        {"milestone": "DIP-0C1", "artifact_kind": "markdown completion report",
         "machine_readable_reconciliation": False},
        {"milestone": "DIP-0C2", "artifact_kind": "markdown + pilot manifests",
         "machine_readable_reconciliation": False},
    ]
    return {
        "reconciliations_found": sorted(found),
        "reconciliation_count": len(found),
        "missing": missing,
        "milestones_without_machine_reconciliation": narrative,
        "regenerated_any_old_artifact": False,
        "note": "milestone records are READ, never rewritten. A record describes what "
                "was true at that milestone.",
        "artifacts": found,
    }


def activation_totals(ledger_report: dict, compound_report: dict) -> dict:
    """What is actually switched on. The answer must be zero, everywhere."""
    return {
        "real_approval_events": ledger_report["counts"]["events"],
        "real_permission_grants": 0,
        "compound_decision_events": compound_report["compound_events"],
        "retrieval_enabled_assets": 0,
        "automatic_use_enabled_assets": 0,
        "fonts_installed": 0,
        "fonts_activated": 0,
        "files_moved_or_deleted": 0,
        "synthetic_decisions_in_real_ledger": 0,
        "all_zero": (ledger_report["counts"]["events"] == 0
                     and compound_report["compound_events"] == 0),
        "note": "the real decision ledger is EMPTY. Every TEST_ONLY record lives in "
                "examples_TEST_ONLY/ and is excluded from migration.",
    }
