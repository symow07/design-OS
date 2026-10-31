"""Font review queues (DIP-0C4b).

Same discipline as C3: **`queue_id` is identity; the letter is a display label.** Code,
tests and future database rows key on the ID. Determinism is a tested property.

**No queue applies a decision.** A queue is a list of questions with the evidence
attached, and every one of them ends at a human.
"""
from __future__ import annotations

from collections import defaultdict

from . import config as C
from . import font_packages as FP
from . import font_provenance as FPV
from . import fontfamily as FF
from . import rights_model as RM

PARSER = f"{C.TOOL_NAME}.review_c4/{C.TOOL_VERSION}"
QUEUE_SCHEMA_VERSION = "review_queue/1.0"

CRITICAL, HIGH, MEDIUM, LOW = "CRITICAL", "HIGH", "MEDIUM", "LOW"

# queue_id, display_label, title, priority, batchable
QUEUES = (
    ("FONT_SUSPECTED_SYSTEM_COPY", "A", "Suspected system-font copies", HIGH, True),
    ("FONT_SYSTEM_STATUS_UNCERTAIN", "B", "System-font status uncertain", MEDIUM,
     True),
    ("FONT_MISSING_LICENSE_EVIDENCE", "C",
     "Technically healthy, no licence evidence", HIGH, True),
    ("FONT_LICENSE_EVIDENCE_PRESENT", "D",
     "Licence evidence present, unreviewed", MEDIUM, True),
    ("FONT_SOURCE_PACKAGE_REVIEW", "E", "Source-package rights review", MEDIUM, True),
    ("FONT_FAMILY_RELATIONSHIP_REVIEW", "F", "Family relationship conflicts", MEDIUM,
     True),
    ("FONT_UNPARSEABLE", "G", "Unparseable or unsupported fonts", LOW, True),
    ("FONT_QUARANTINE_CANDIDATE", "H", "Quarantine candidates", HIGH, True),
    ("FONT_DUPLICATE_BATCH", "I", "Exact-duplicate batches", LOW, True),
    ("FONT_RIGHTS_CONFLICT", "J",
     "Conflicting rights evidence across packages", HIGH, True),
)
QUEUE_IDS = tuple(q[0] for q in QUEUES)
LABELS = {q[0]: q[1] for q in QUEUES}
TITLES = {q[0]: q[2] for q in QUEUES}
PRIORITIES = {q[0]: q[3] for q in QUEUES}
BATCHABLE = {q[0]: q[4] for q in QUEUES}

assert len(set(QUEUE_IDS)) == len(QUEUE_IDS), "duplicate queue_id"
assert len({q[1] for q in QUEUES}) == len(QUEUES), "duplicate display_label"

ROLES = {
    "FONT_SUSPECTED_SYSTEM_COPY": ["LEGAL_REVIEWER"],
    "FONT_SYSTEM_STATUS_UNCERTAIN": ["LEGAL_REVIEWER"],
    "FONT_MISSING_LICENSE_EVIDENCE": ["LEGAL_REVIEWER"],
    "FONT_LICENSE_EVIDENCE_PRESENT": ["LEGAL_REVIEWER"],
    "FONT_SOURCE_PACKAGE_REVIEW": ["LEGAL_REVIEWER", "BRAND_ADMIN"],
    "FONT_FAMILY_RELATIONSHIP_REVIEW": ["DESIGN_REVIEWER", "BRAND_ADMIN"],
    "FONT_UNPARSEABLE": ["DESIGN_REVIEWER"],
    "FONT_QUARANTINE_CANDIDATE": ["LEGAL_REVIEWER"],
    "FONT_DUPLICATE_BATCH": ["DESIGN_REVIEWER"],
    "FONT_RIGHTS_CONFLICT": ["LEGAL_REVIEWER"],
}


def _q(qid, items, *, reason, action, evidence, exceptions, priority=None) -> dict:
    files = sum(i.get("file_count", 0) for i in items)
    faces = sum(i.get("face_count", 0) for i in items)
    fams = sorted({f for i in items for f in (i.get("families") or [])})
    pkgs = sorted({p for i in items for p in (i.get("source_packages") or [])})
    return {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "queue_id": qid,
        "display_label": LABELS[qid],
        "title": TITLES[qid],
        "item_count": len(items),
        "file_count": files,
        "face_count": faces,
        "family_count": len(fams),
        "source_packages": pkgs,
        "priority": priority or PRIORITIES[qid],
        "shared_reason": reason,
        "evidence": evidence,
        "exceptions": exceptions,
        "required_reviewer_roles": list(ROLES[qid]),
        "recommended_human_action": action,
        "batch_review_allowed": BATCHABLE[qid],
        "applies_decision_automatically": False,
        "items": items,
    }


def build(*, faces, files, groups, packages, suspicions, batches,
          dedupe) -> dict:
    """Every font queue. Deterministic: stable sort keys, never set/dict order."""
    by_face = {f["face_id"]: f for f in faces}

    def _face_items(pred, extra=None):
        rows = []
        for fid, s in sorted(suspicions.items()):
            if not pred(s):
                continue
            f = by_face.get(fid)
            if not f:
                continue
            rows.append({
                "face_id": fid,
                "source_path": f["source_path"],
                "family": f.get("_family_key"),
                "families": [f.get("_family_key")] if f.get("_family_key") else [],
                "source_packages": [FP.package_of(f["source_path"])],
                "file_count": 1, "face_count": 1,
                "vendor_id": s["vendor_id"],
                "foundries": s["foundries"],
                "confidence": s["confidence"],
                "evidence": [e["code"] for e in s["evidence"]],
                **(extra or {}),
            })
        return sorted(rows, key=lambda r: (r["source_path"], r["face_id"]))

    q: dict[str, dict] = {}

    q["FONT_SUSPECTED_SYSTEM_COPY"] = _q(
        "FONT_SUSPECTED_SYSTEM_COPY",
        _face_items(lambda s: s["outcome"] == FPV.SUSPECTED_SYSTEM_FONT_COPY),
        reason="the name table names an OS or major foundry. A SUSPICION, not a "
               "finding of wrongdoing — the font may be licensed, or an internal "
               "system dependency.",
        evidence="OS/2.achVendID, name.copyright, name.trademark — never the filename",
        exceptions="a licensed Microsoft font is perfectly legal; each foundry may "
                   "warrant its own decision",
        action="confirm licensed / internal dependency / third-party restricted / "
               "quarantine permanently")

    q["FONT_SYSTEM_STATUS_UNCERTAIN"] = _q(
        "FONT_SYSTEM_STATUS_UNCERTAIN",
        _face_items(lambda s: s["outcome"] in (FPV.SYSTEM_FONT_EVIDENCE_PRESENT,
                                               FPV.SYSTEM_FONT_STATUS_UNCERTAIN)),
        reason="some name-table evidence of a major foundry, below the suspicion "
               "threshold",
        evidence="partial name-table signals",
        exceptions="weak evidence is not evidence of innocence either",
        action="confirm or dismiss the origin")

    # --- batches (package / dump) ------------------------------------------------
    def _batch_rows(pred):
        rows = []
        for b in sorted(batches, key=lambda b: b["batch_id"]):
            if not pred(b):
                continue
            pkg = next((p for p in packages
                        if p["package_key"] == b["batch_id"]), None)
            rows.append({
                "batch_id": b["batch_id"],
                "batch_kind": b["batch_kind"],
                "file_count": b["file_count"],
                "face_count": b["face_count"],
                "families": (pkg or {}).get("families", []),
                "source_packages": (pkg or {}).get("package_roots", []),
                "reuse_posture": b["reuse_posture"],
                "reasons": b["reasons"],
                "license_evidence_files": b["license_evidence_files"],
                "restrictions_detected": b["restrictions_detected"],
                "evidence_warnings": b["evidence_warnings"],
                "suspected_system_faces": b["suspected_system_faces"],
            })
        return rows

    q["FONT_QUARANTINE_CANDIDATE"] = _q(
        "FONT_QUARANTINE_CANDIDATE",
        _batch_rows(lambda b: b["reuse_posture"] == "QUARANTINE_CANDIDATE"),
        reason="quarantine RECOMMENDED pending human review. Nothing is deleted, "
               "moved, or permanently rejected.",
        evidence="system-font suspicion and/or absent licence evidence",
        exceptions="a human may confirm PROPERLY_LICENSED or "
                   "INTERNAL_SYSTEM_DEPENDENCY and release it",
        action="choose one of the five permitted human outcomes")

    q["FONT_MISSING_LICENSE_EVIDENCE"] = _q(
        "FONT_MISSING_LICENSE_EVIDENCE",
        _batch_rows(lambda b: not b["license_evidence_files"] and b["face_count"]),
        reason="technically healthy fonts with NO licence evidence of any kind. "
               "Possession is not permission.",
        evidence="absence of evidence — recorded as absence, not as permission",
        exceptions="evidence may exist outside materials/ and simply not be here",
        action="obtain licence evidence, or quarantine")

    q["FONT_LICENSE_EVIDENCE_PRESENT"] = _q(
        "FONT_LICENSE_EVIDENCE_PRESENT",
        _batch_rows(lambda b: bool(b["license_evidence_mentioning_fonts"])),
        reason="licence evidence that actually mentions fonts is associated — and is "
               "UNREVIEWED. Evidence is not approval.",
        evidence="OFL / Apache / EULA text, read and classified",
        exceptions="an OFL grants nothing until a human reads it and decides",
        action="review the licence and record a decision")

    q["FONT_SOURCE_PACKAGE_REVIEW"] = _q(
        "FONT_SOURCE_PACKAGE_REVIEW",
        _batch_rows(lambda b: b["batch_kind"] == FP.PKG_DOWNLOAD_PACKAGE),
        reason="a credible package boundary — the natural unit of a rights decision",
        evidence="package root, members, licence documents",
        exceptions="one package's licence NEVER clears another",
        action="review the package as one rights unit")

    # --- families ---------------------------------------------------------------
    fam_rows = sorted(
        [{"group_id": g["group_id"], "family": g["family_key"],
          "families": [g["family_key"]] if g["family_key"] else [],
          "source_packages": g["source_packages"],
          "file_count": g["file_count"], "face_count": g["face_count"],
          "state": g["state"], "vendors": g["vendors"],
          "conflicting_evidence": g["conflicting_evidence"]}
         for g in groups
         if g["state"] == FF.FAMILY_RELATIONSHIP_REVIEW_REQUIRED],
        key=lambda r: (r["family"] or "", r["group_id"]))
    q["FONT_FAMILY_RELATIONSHIP_REVIEW"] = _q(
        "FONT_FAMILY_RELATIONSHIP_REVIEW", fam_rows,
        reason="a family name matched but the corroborating evidence did not",
        evidence="vendor, PostScript prefix, version, glyph coverage, package",
        exceptions="a family name is a hypothesis, never identity proof",
        action="confirm or split the family")

    # a family appearing in more than one package is a RIGHTS conflict, not a merge
    fxp: dict[str, set] = defaultdict(set)
    for f in faces:
        if f.get("_family_key"):
            fxp[f["_family_key"]].add(FP.package_of(f["source_path"]))
    conflict_rows = sorted(
        [{"family": k, "families": [k], "source_packages": sorted(v),
          "file_count": 0, "face_count": 0,
          "reason": "the same family arrives from more than one package — the "
                    "packages may carry DIFFERENT rights, and one never clears "
                    "the other"}
         for k, v in fxp.items() if len(v) > 1],
        key=lambda r: r["family"])
    q["FONT_RIGHTS_CONFLICT"] = _q(
        "FONT_RIGHTS_CONFLICT", conflict_rows,
        reason="the same family arrives from several packages with different "
               "evidence. Licence approval NEVER propagates across packages because "
               "two family names match.",
        evidence="family key × source package",
        exceptions="the families may be unrelated despite the shared name",
        action="review each family × package pair separately")

    # --- unparseable + duplicates ------------------------------------------------
    unp = sorted([{"source_path": f["source_path"], "file_count": 1, "face_count": 0,
                   "families": [], "source_packages": [FP.package_of(f["source_path"])],
                   "parse_status": f["parse_status"], "error": (f.get("error") or "")[:90]}
                  for f in files
                  if f["parse_status"] in ("UNSUPPORTED_FORMAT", "PARSE_FAILED")],
                 key=lambda r: r["source_path"])
    q["FONT_UNPARSEABLE"] = _q(
        "FONT_UNPARSEABLE", unp,
        reason="fontTools cannot read these at all — 32 legacy .fon bitmap fonts",
        evidence="no sfnt to parse",
        exceptions="unreadable is not the same as absent: they are still in materials/",
        action="confirm they are system fonts, or find a tool that reads them")

    dup_rows = sorted(
        [{"sha256": h, "file_count": len(v), "face_count": 0, "families": [],
          "source_packages": sorted({FP.package_of(m["relative_path"]) for m in v}),
          "paths": [m["relative_path"] for m in v]}
         for h, v in dedupe["duplicate_groups"].items()],
        key=lambda r: (-r["file_count"], r["sha256"]))
    q["FONT_DUPLICATE_BATCH"] = _q(
        "FONT_DUPLICATE_BATCH", dup_rows,
        reason="byte-identical files. Identical bytes carry identical rights, so one "
               "decision genuinely covers the group.",
        evidence="SHA-256",
        exceptions="none — this is the ONLY lever that is safe as a single decision",
        action="decide once per hash")

    ordered = {qid: q[qid] for qid in QUEUE_IDS}
    return {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "queues": ordered,
        "totals": {qid: ordered[qid]["item_count"] for qid in QUEUE_IDS},
        "permission_flags": sorted(RM.PERMISSION_FLAGS),
        "permission_flag_count": len(RM.PERMISSION_FLAGS),
        "all_permissions_false": True,
        "note": "queue_id is IDENTITY; display_label is presentation. No queue applies "
                "a decision.",
        "parser": PARSER,
    }
