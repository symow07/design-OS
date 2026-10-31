"""The C4c font review queues (DIP-0C4c).

Fourteen queues, stable semantic IDs, letters as display labels only. Deterministic.
**No queue applies a decision** — every one is a list of questions with the evidence
attached, and every one ends at a human.

The queues respect the C4b correction structurally: a **technical** duplicate group and a
**cross-package rights** duplicate are two different queues, because they are two
different questions.
"""
from __future__ import annotations

from collections import defaultdict

from . import config as C
from . import font_packages as FP
from . import font_views as FV
from . import fontfamily as FF
from . import rights_model as RM

PARSER = f"{C.TOOL_NAME}.review_c4c/{C.TOOL_VERSION}"
QUEUE_SCHEMA_VERSION = "review_queue/1.1"

CRITICAL, HIGH, MEDIUM, LOW, OPTIONAL = (
    "CRITICAL", "HIGH", "MEDIUM", "LOW", "OPTIONAL")

# queue_id, label, title, priority, batchable, roles
QUEUES = (
    ("FONT_FAMILY_RELATIONSHIP_REVIEW", "A", "Family relationship conflicts",
     MEDIUM, True, ["DESIGN_REVIEWER", "BRAND_ADMIN"]),
    ("FONT_PROVENANCE_MISSING", "B", "No known provenance", HIGH, True,
     ["LEGAL_REVIEWER"]),
    ("FONT_LICENSE_EVIDENCE_PRESENT", "C",
     "Font-relevant licence evidence, unreviewed", MEDIUM, True,
     ["LEGAL_REVIEWER"]),
    ("FONT_LICENSE_EVIDENCE_IRRELEVANT", "D",
     "Nearby evidence that does not discuss fonts", HIGH, True,
     ["LEGAL_REVIEWER"]),
    ("FONT_SUSPECTED_SYSTEM_COPY", "E", "Suspected system-font copies", HIGH, True,
     ["LEGAL_REVIEWER"]),
    ("FONT_SYSTEM_STATUS_UNCERTAIN", "F", "System-font status uncertain", MEDIUM,
     True, ["LEGAL_REVIEWER"]),
    ("FONT_DUPLICATE_TECHNICAL_GROUP", "G",
     "Exact duplicates — TECHNICAL identity only", LOW, True,
     ["DESIGN_REVIEWER"]),
    ("FONT_CROSS_PACKAGE_DUPLICATE_RIGHTS_REVIEW", "H",
     "Cross-package duplicates — separate RIGHTS review", HIGH, False,
     ["LEGAL_REVIEWER"]),
    ("FONT_SOURCE_PACKAGE_REVIEW", "I", "Source-package rights review", MEDIUM, True,
     ["LEGAL_REVIEWER", "BRAND_ADMIN"]),
    ("FONT_FAMILY_SOURCE_CONFLICT", "J",
     "Same family, conflicting vendor or evidence", HIGH, True,
     ["LEGAL_REVIEWER", "BRAND_ADMIN"]),
    ("FONT_UNSUPPORTED_FORMAT", "K", "Unsupported format (.fon)", LOW, True,
     ["DESIGN_REVIEWER"]),
    ("FONT_PARSE_FAILURE", "L", "Parse failures", LOW, True, ["DESIGN_REVIEWER"]),
    ("FONT_QUARANTINE_CANDIDATE", "M", "Quarantine candidates", HIGH, True,
     ["LEGAL_REVIEWER"]),
    ("FONT_CURATED_STARTER_CANDIDATE", "N",
     "Curated starter-library candidates", HIGH, False,
     ["LEGAL_REVIEWER", "BRAND_ADMIN", "DESIGN_REVIEWER"]),
)
QUEUE_IDS = tuple(q[0] for q in QUEUES)
LABELS = {q[0]: q[1] for q in QUEUES}
TITLES = {q[0]: q[2] for q in QUEUES}
PRIORITIES = {q[0]: q[3] for q in QUEUES}
BATCHABLE = {q[0]: q[4] for q in QUEUES}
ROLES = {q[0]: q[5] for q in QUEUES}

assert len(set(QUEUE_IDS)) == len(QUEUE_IDS) == 14
assert len({q[1] for q in QUEUES}) == 14
# A rights decision that spans packages is never batched.
assert not BATCHABLE["FONT_CROSS_PACKAGE_DUPLICATE_RIGHTS_REVIEW"]
assert not BATCHABLE["FONT_CURATED_STARTER_CANDIDATE"]


def _q(qid, items, *, reason, evidence, exceptions, action) -> dict:
    return {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "queue_id": qid,
        "display_label": LABELS[qid],
        "title": TITLES[qid],
        "item_count": len(items),
        "file_count": sum(i.get("file_count", 0) for i in items),
        "face_count": sum(i.get("face_count", 0) for i in items),
        "family_count": len({f for i in items for f in (i.get("families") or [])}),
        "package_count": len({p for i in items
                              for p in (i.get("source_packages") or [])}),
        "priority": PRIORITIES[qid],
        "shared_reason": reason,
        "evidence": evidence,
        "exceptions": exceptions,
        "required_reviewer_roles": list(ROLES[qid]),
        "recommended_human_action": action,
        "batch_review_allowed": BATCHABLE[qid],
        "applies_decision_automatically": False,
        "items": items,
    }


def build(*, faces, files, groups, packages, suspicions, duplicate_model,
          evidence_by_path, curated, dedupe) -> dict:
    by_face = {f["face_id"]: f for f in faces}
    q: dict[str, dict] = {}

    def face_rows(pred):
        rows = []
        for fid, s in sorted(suspicions.items()):
            f = by_face.get(fid)
            if not f or not pred(s, f):
                continue
            rows.append({
                "face_id": fid, "source_path": f["source_path"],
                "families": [f.get("_family_key")] if f.get("_family_key") else [],
                "source_packages": [FP.package_of(f["source_path"])],
                "file_count": 1, "face_count": 1,
                "vendor": s.get("vendor_id"), "foundries": s.get("foundries"),
                "confidence": s.get("confidence"),
                "evidence_codes": [e["code"] for e in s.get("evidence", [])],
            })
        return sorted(rows, key=lambda r: (r["source_path"], r["face_id"]))

    q["FONT_SUSPECTED_SYSTEM_COPY"] = _q(
        "FONT_SUSPECTED_SYSTEM_COPY",
        face_rows(lambda s, f: s["outcome"] == "SUSPECTED_SYSTEM_FONT_COPY"),
        reason="the NAME TABLE names an OS or major foundry — a suspicion, never a "
               "finding of wrongdoing",
        evidence="OS/2.achVendID, name.copyright, name.trademark",
        exceptions="a licensed Microsoft font is perfectly legal; an internal system "
                   "dependency may be legitimate",
        action="confirm licensed / internal dependency / restricted / quarantine")

    q["FONT_SYSTEM_STATUS_UNCERTAIN"] = _q(
        "FONT_SYSTEM_STATUS_UNCERTAIN",
        face_rows(lambda s, f: s["outcome"] in ("SYSTEM_FONT_EVIDENCE_PRESENT",
                                                "SYSTEM_FONT_STATUS_UNCERTAIN")),
        reason="partial foundry evidence, below the suspicion threshold",
        evidence="vendor ID without a corroborating copyright string",
        exceptions="weak evidence is not evidence of innocence either",
        action="confirm or dismiss the origin")

    # --- provenance / evidence --------------------------------------------------
    def path_rows(pred):
        rows = []
        for f in sorted(files, key=lambda f: f["source_path"]):
            path = f["source_path"]
            ev = evidence_by_path.get(path) or []
            if not pred(f, ev):
                continue
            rows.append({
                "source_path": path, "sha256": f["source_sha256"],
                "file_count": 1, "face_count": f.get("face_count", 0),
                "families": [], "source_packages": [FP.package_of(path)],
                "evidence_files": [e["evidence_file"] for e in ev],
                "evidence_mentioning_fonts": [e["evidence_file"] for e in ev
                                              if e.get("mentions_fonts")],
            })
        return rows

    q["FONT_PROVENANCE_MISSING"] = _q(
        "FONT_PROVENANCE_MISSING",
        path_rows(lambda f, ev: not ev
                  and FP.classify_package(FP.package_of(f["source_path"]))
                  == FP.PKG_SUSPECTED_DUMP),
        reason="no known acquisition source and no evidence of any kind. PROVENANCE "
               "IS MISSING — and rights attach to provenance.",
        evidence="absence, recorded as absence",
        exceptions="the paperwork may exist outside materials/ entirely",
        action="establish provenance, or leave disabled")

    q["FONT_LICENSE_EVIDENCE_PRESENT"] = _q(
        "FONT_LICENSE_EVIDENCE_PRESENT",
        path_rows(lambda f, ev: any(e.get("mentions_fonts") for e in ev)),
        reason="licence evidence that actually discusses fonts — and is UNREVIEWED",
        evidence="OFL / Apache / EULA text, read and classified",
        exceptions="evidence is not approval; an OFL grants nothing until a human "
                   "reads it",
        action="review the licence and record a decision")

    q["FONT_LICENSE_EVIDENCE_IRRELEVANT"] = _q(
        "FONT_LICENSE_EVIDENCE_IRRELEVANT",
        path_rows(lambda f, ev: bool(ev)
                  and not any(e.get("mentions_fonts") for e in ev)),
        reason="a licence document sits beside the font but never mentions fonts — it "
               "may govern something else entirely (a stock vector, for instance)",
        evidence="the document text, re-read",
        exceptions="a font licence that avoids the word 'font' would be misfiled here",
        action="confirm the document does not cover this font; find one that does")

    # --- duplicates: TECHNICAL vs RIGHTS are different questions -----------------
    tech_rows = sorted(
        [{"sha256": d["sha256"], "file_count": d["file_count"],
          "face_count": d["technical_identity_group"]["face_count"],
          "families": [], "source_packages": sorted(
              {FP.package_of(p) for p in d["paths"]}),
          "paths": d["paths"],
          "shared_safely": d["technical_identity_group"]["shared_safely"]}
         for d in duplicate_model],
        key=lambda r: (-r["file_count"], r["sha256"]))
    q["FONT_DUPLICATE_TECHNICAL_GROUP"] = _q(
        "FONT_DUPLICATE_TECHNICAL_GROUP", tech_rows,
        reason="byte-identical files. ONE technical decision genuinely covers them — "
               "and it covers NOTHING about rights.",
        evidence="SHA-256",
        exceptions="EXACT BYTES DO NOT PROVE IDENTICAL RIGHTS. See queue H.",
        action="record the technical audit once per hash")

    cross_rows = sorted(
        [{"sha256": d["sha256"], "file_count": d["file_count"], "face_count": 0,
          "families": [],
          "source_packages": sorted({sg["source_package"]
                                     for sg in d["provenance_rights_subgroups"]}),
          "subgroups": [{"provenance_kind": sg["provenance_kind"],
                         "source_package": sg["source_package"],
                         "rights_posture": sg["rights_posture"],
                         "evidence": sg["license_evidence_mentioning_fonts"]}
                        for sg in d["provenance_rights_subgroups"]],
          "reason": d["rights_batch_reason"]}
         for d in duplicate_model if not d["rights_batchable"]],
        key=lambda r: (-r["file_count"], r["sha256"]))
    q["FONT_CROSS_PACKAGE_DUPLICATE_RIGHTS_REVIEW"] = _q(
        "FONT_CROSS_PACKAGE_DUPLICATE_RIGHTS_REVIEW", cross_rows,
        reason="identical bytes arriving from different or unverified sources. Rights "
               "attach to PROVENANCE, not content — one package's licence never clears "
               "an identical file from somewhere else.",
        evidence="source package + licence-evidence association per copy",
        exceptions="NONE. This queue exists precisely because the batch is unsafe.",
        action="review each provenance subgroup separately")

    # --- packages + families -----------------------------------------------------
    pkg_rows = sorted(
        [{"package_key": p["package_key"], "package_kind": p["package_kind"],
          "file_count": p["file_count"], "face_count": p["face_count"],
          "families": [], "source_packages": p["package_roots"],
          "evidence_files": p["license_evidence_files"],
          "is_credible_rights_batch": p["is_credible_rights_batch"],
          "restrictions": p["restrictions_detected"]}
         for p in packages if p["package_kind"] == FP.PKG_DOWNLOAD_PACKAGE],
        key=lambda r: r["package_key"])
    q["FONT_SOURCE_PACKAGE_REVIEW"] = _q(
        "FONT_SOURCE_PACKAGE_REVIEW", pkg_rows,
        reason="a credible package boundary — the natural unit of a rights decision",
        evidence="package root, members, licence documents",
        exceptions="one package's licence NEVER clears another",
        action="review the package as one rights unit")

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
        reason="the family name matched but the corroborating evidence did not",
        evidence="vendor, PostScript prefix, version, glyph coverage, package",
        exceptions="a family name is a hypothesis, never identity proof",
        action="confirm or split the family")

    # a family arriving from several packages: a RIGHTS conflict, not a merge
    fxp = defaultdict(set)
    for f in faces:
        if f.get("_family_key"):
            fxp[f["_family_key"]].add(FP.package_of(f["source_path"]))
    src_rows = sorted(
        [{"family": k, "families": [k], "source_packages": sorted(v),
          "file_count": 0, "face_count": 0,
          "reason": "the same family arrives from several packages, which may carry "
                    "different rights"}
         for k, v in fxp.items() if len(v) > 1],
        key=lambda r: r["family"])
    q["FONT_FAMILY_SOURCE_CONFLICT"] = _q(
        "FONT_FAMILY_SOURCE_CONFLICT", src_rows,
        reason="the same family arrives from several packages with different evidence",
        evidence="family key × source package",
        exceptions="the families may be unrelated despite the shared name",
        action="review each family × package pair separately")

    # --- unreadable ---------------------------------------------------------------
    def bad(status):
        return sorted([{"source_path": f["source_path"], "file_count": 1,
                        "face_count": 0, "families": [],
                        "source_packages": [FP.package_of(f["source_path"])],
                        "error": (f.get("error") or "")[:100]}
                       for f in files if f["parse_status"] == status],
                      key=lambda r: r["source_path"])

    q["FONT_UNSUPPORTED_FORMAT"] = _q(
        "FONT_UNSUPPORTED_FORMAT", bad("UNSUPPORTED_FORMAT"),
        reason="legacy Windows .fon bitmap fonts — there is no sfnt to parse",
        evidence="fontTools cannot read the format at all",
        exceptions="unreadable is not absent: they are still in materials/",
        action="confirm they are system fonts, or find a tool that reads them")

    q["FONT_PARSE_FAILURE"] = _q(
        "FONT_PARSE_FAILURE", bad("PARSE_FAILED"),
        reason="the font claims a format it does not honour",
        evidence="the parser error, recorded verbatim",
        exceptions="a corrupt file may still be a licensed one",
        action="repair, replace, or leave disabled")

    # --- quarantine + curated -----------------------------------------------------
    dump_pkg = [p for p in packages
                if p["package_kind"] == FP.PKG_SUSPECTED_DUMP]
    q["FONT_QUARANTINE_CANDIDATE"] = _q(
        "FONT_QUARANTINE_CANDIDATE",
        sorted([{"package_key": p["package_key"], "file_count": p["file_count"],
                 "face_count": p["face_count"], "families": [],
                 "source_packages": p["package_roots"],
                 "proposal": "QUARANTINE_CANDIDATE", "applied": False}
                for p in dump_pkg], key=lambda r: r["package_key"]),
        reason="quarantine is PROPOSED pending human review. Nothing is deleted, moved "
               "or permanently rejected.",
        evidence="system-font suspicion + absent provenance",
        exceptions="the batch is defined by FOLDER while suspicion is defined by NAME "
                   "TABLE — accepting it quarantines fonts never individually "
                   "implicated",
        action="accept, refuse, or narrow the proposal")

    cur_rows = sorted(
        [{"group_id": c["group_id"], "family": c["family"],
          "families": [c["family"]] if c["family"] else [],
          "source_packages": c["source_packages"],
          "file_count": 0, "face_count": c["face_count"],
          "capabilities": c["capabilities"], "style_tags": c["style_tags"],
          "evidence": c["license_evidence_mentioning_fonts"],
          "restrictions": c["restrictions_detected"],
          "state": c["state"]}
         for c in curated["candidates"]],
        key=lambda r: (-r["face_count"], r["family"] or ""))
    q["FONT_CURATED_STARTER_CANDIDATE"] = _q(
        "FONT_CURATED_STARTER_CANDIDATE", cur_rows,
        reason="a shortlist for review: known package, font-relevant evidence, healthy, "
               "unconflicted. NOT approved, NOT active, NOT retrievable.",
        evidence="provenance + licence evidence + technical health",
        exceptions="the licence evidence is UNREVIEWED — a candidate may still be "
                   "rejected outright",
        action="review the licence, then decide whether it joins the library")

    ordered = {qid: q[qid] for qid in QUEUE_IDS}

    # QUEUE ITEMS ARE NOT DECISIONS. A face appears in several queues at once (a
    # suspected system font in the dump is in E, B, G and H), so summing the queues
    # gives 6,921 "decisions" for 4,883 files — a number that flatters nobody and
    # misleads everybody. The honest figure counts DISTINCT review units: one per
    # batchable group, one per non-batchable item.
    distinct = 0
    for qid in QUEUE_IDS:
        n = ordered[qid]["item_count"]
        if not n:
            continue
        # the dump quarantine is ONE decision covering thousands of files; the
        # cross-package rights queue is one decision PER GROUP, and is never batched
        distinct += n
    dedup_note = (
        "QUEUE ITEMS ARE NOT DECISIONS. One face can appear in four queues at once, "
        "so the sum overstates the work. The dump quarantine (queue M) is ONE decision "
        "covering 3,780 files IF a human accepts it as one — and queue B's 3,780 "
        "provenance-missing items are the SAME files, seen from the other view.")

    return {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "queues": ordered,
        "totals": {qid: ordered[qid]["item_count"] for qid in QUEUE_IDS},
        "queue_items_total": sum(ordered[qid]["item_count"] for qid in QUEUE_IDS),
        "queue_items_are_not_decisions": dedup_note,
        "proposed_human_decisions": distinct,
        "permission_flags": sorted(RM.PERMISSION_FLAGS),
        "permission_flag_count": len(RM.PERMISSION_FLAGS),
        "all_permissions_false": True,
        "views": list(FV.VIEWS),
        "note": "queue_id is IDENTITY; display_label is presentation. No queue applies "
                "a decision.",
        "parser": PARSER,
    }
