"""The two independent review views, and the manifests (DIP-0C4c).

**A decision in one view never implies a decision in the other.** They answer different
questions and they are kept apart on purpose:

* **Technical-family view** — *which faces belong together, and are they healthy?*
* **Provenance-rights view** — *where did each copy come from, and what paperwork exists?*

Confirming a family is one typeface says nothing about whether BBROSE may use it.
Confirming a licence covers a package says nothing about whether two faces are the same
family. The C4b correction is the reason this is structural rather than a note: exact
bytes prove technical identity and prove **nothing** about rights.

**Machine inference is immutable.** Every manifest row carries a `machine` block and a
separate, entirely blank `human` block. A human correction is recorded *beside* the
inference, never over it — the same discipline as every slice since DIP-0B.
"""
from __future__ import annotations


from . import config as C
from . import font_packages as FP
from . import fontfamily as FF
from . import rights_model as RM

PARSER = f"{C.TOOL_NAME}.font_views/{C.TOOL_VERSION}"
SCHEMA_VERSION = "font_view/1.0"

VIEW_TECHNICAL = "TECHNICAL_FAMILY"
VIEW_RIGHTS = "PROVENANCE_RIGHTS"
VIEWS = (VIEW_TECHNICAL, VIEW_RIGHTS)


def human_block() -> dict:
    """Every human field, blank. A machine may never fill one of these."""
    return {
        "reviewer": None,
        "reviewed_at": None,
        "family_confirmation": None,
        "source_package_confirmation": None,
        "provenance_confirmation": None,
        "license_decision": None,
        "ownership_decision": None,
        "quarantine_decision": None,
        "approved_scripts": [],
        "approved_usage": [],
        "style_tags_confirmation": None,
        "notes": None,
        "correction_reason": None,
    }


def permissions() -> dict:
    return {flag: False for flag in RM.PERMISSION_FLAGS}


# --- priorities ------------------------------------------------------------------
CRITICAL, HIGH, MEDIUM, LOW, OPTIONAL = (
    "CRITICAL", "HIGH", "MEDIUM", "LOW", "OPTIONAL")


def prioritise(*, healthy: bool, has_font_evidence: bool, suspected: bool,
               cross_package_dup: bool, family_conflict: bool,
               unsupported: bool, curated_candidate: bool) -> tuple[str, list[str]]:
    """A priority, and the reasons for it. Never a bare number."""
    reasons: list[str] = []
    if unsupported:
        reasons.append("the format cannot be parsed at all; it is already disabled")
        return LOW, reasons

    if suspected:
        reasons.append("suspected system-font copy — name-table evidence of an OS or "
                       "major foundry")
    if healthy and not has_font_evidence:
        reasons.append("technically healthy, but NO font-relevant licence evidence — "
                       "possession is not permission")
    if cross_package_dup:
        reasons.append("an exact duplicate arrives from a different package: identical "
                       "bytes, potentially different rights")
    if family_conflict:
        reasons.append("the family name matched but the corroborating evidence did not")
    if curated_candidate and not has_font_evidence:
        reasons.append("a curated-starter candidate whose rights are unresolved")

    if suspected or (healthy and not has_font_evidence) or cross_package_dup \
            or (curated_candidate and not has_font_evidence):
        return HIGH, reasons
    if has_font_evidence or family_conflict:
        if has_font_evidence:
            reasons.append("an organised package with font-relevant evidence — "
                           "UNREVIEWED")
        return MEDIUM, reasons
    reasons.append("no outstanding rights or technical question")
    return OPTIONAL, reasons


# --- the technical-family view ---------------------------------------------------
def technical_view(*, faces: list, files: list, groups: list, dedupe: dict,
                   styles: dict) -> dict:
    """Which faces belong together, and are they healthy? NOTHING about rights."""
    by_face = {f["face_id"]: f for f in faces}
    fam_of: dict[str, str] = {}
    for g in groups:
        for fid in g["faces"]:
            fam_of[fid] = g["group_id"]

    rows = []
    for g in sorted(groups, key=lambda g: (g["family_key"] or "~", g["group_id"])):
        rows.append({
            "group_id": g["group_id"],
            "family_key": g["family_key"],
            "key_source": g["key_source"],
            "state": g["state"],
            "face_count": g["face_count"],
            "file_count": g["file_count"],
            "display_names": g["display_names"],
            "vendors": g["vendors"],
            "weight_classes": g["weight_classes"],
            "width_classes": g["width_classes"],
            "is_variable": g["is_variable"],
            "variable_axes": g["variable_axes"],
            "scripts": g["scripts"],
            "dominant_scripts": g["dominant_scripts"],
            "duplicate_hashes": g["duplicate_hashes"],
            "supporting_evidence": g["supporting_evidence"],
            "conflicting_evidence": g["conflicting_evidence"],
            "style_tags": sorted({t for fid in g["faces"]
                                  for t in (styles.get(fid, {}).get("tag_names") or [])}),
            "health": ("HEALTHY" if all(by_face[fid]["parse_status"] == "PARSED"
                                        for fid in g["faces"] if fid in by_face)
                       else "REVIEW_REQUIRED"),
            "human": human_block(),
        })

    unsupported = [f for f in files
                   if f["parse_status"] in ("UNSUPPORTED_FORMAT", "PARSE_FAILED")]
    return {
        "view": VIEW_TECHNICAL,
        "question": "which faces belong together, and are they technically healthy?",
        "answers_nothing_about": "ownership, licence, permission, or quarantine",
        "family_groups": rows,
        "family_group_count": len(rows),
        "face_count": len(faces),
        "file_count": len(files),
        "technical_duplicate_groups": dedupe["duplicate_group_count"],
        "unsupported_files": len(unsupported),
        "note": "TECHNICAL ONLY. A decision here implies NOTHING in the rights view.",
        "parser": PARSER,
    }


# --- the provenance-rights view --------------------------------------------------
def rights_view(*, files: list, packages: list, duplicate_model: list,
                evidence_by_path: dict, suspicions: dict,
                faces_by_hash: dict) -> dict:
    """Where did each copy come from, and what paperwork exists? NOTHING about
    typography."""
    subgroups = []
    for d in duplicate_model:
        for sg in d["provenance_rights_subgroups"]:
            subgroups.append({
                "sha256": d["sha256"],
                "provenance_kind": sg["provenance_kind"],
                "source_package": sg["source_package"],
                "paths": sg["paths"],
                "file_count": sg["file_count"],
                "license_evidence_mentioning_fonts":
                    sg["license_evidence_mentioning_fonts"],
                "rights_posture": sg["rights_posture"],
                "permissions": sg["permissions"],
                "rights_batchable_with_siblings": d["rights_batchable"],
                "human": human_block(),
            })

    pkg_rows = []
    for p in sorted(packages, key=lambda p: p["package_key"]):
        pkg_rows.append({
            "package_key": p["package_key"],
            "package_kind": p["package_kind"],
            "package_roots": p["package_roots"],
            "file_count": p["file_count"],
            "face_count": p["face_count"],
            "is_credible_rights_batch": p["is_credible_rights_batch"],
            "license_evidence_files": p["license_evidence_files"],
            "evidence_mentioning_fonts": sorted(
                {e["evidence_file"] for e in (p["license_evidence"] or [])
                 if e.get("mentions_fonts")}),
            "restrictions_detected": p["restrictions_detected"],
            "evidence_warnings": p["evidence_warnings"],
            "permissions": permissions(),
            "human": human_block(),
        })

    with_ev = sum(1 for rows in evidence_by_path.values()
                  if any(e["mentions_fonts"] for e in rows))
    return {
        "view": VIEW_RIGHTS,
        "question": "where did each copy come from, and what paperwork exists?",
        "answers_nothing_about": "typographic family, weight, script, or health",
        "source_packages": pkg_rows,
        "provenance_rights_subgroups": subgroups,
        "subgroup_count": len(subgroups),
        "files_with_font_relevant_evidence": with_ev,
        "files_without_evidence": len(files) - len(evidence_by_path),
        "rights_batchable_duplicate_groups": sum(1 for d in duplicate_model
                                                 if d["rights_batchable"]),
        "all_permissions_false": True,
        "note": "RIGHTS ONLY. A decision here implies NOTHING in the technical view. "
                "One package's licence never clears an identical file from another.",
        "parser": PARSER,
    }


# --- manifests -------------------------------------------------------------------
def face_manifest(*, faces: list, files: list, groups: list, dedupe: dict,
                  evidence_by_path: dict, suspicions: dict, styles: dict,
                  duplicate_model: list) -> list[dict]:
    """One row per FACE. Machine fields populated; human fields blank."""
    fam_of, fam_state = {}, {}
    for g in groups:
        for fid in g["faces"]:
            fam_of[fid] = g["group_id"]
            fam_state[fid] = g["state"]

    sub_of: dict[str, dict] = {}
    for d in duplicate_model:
        for sg in d["provenance_rights_subgroups"]:
            for p in sg["paths"]:
                sub_of[p] = sg

    by_file = {f["source_path"]: f for f in files}
    rows = []
    for f in sorted(faces, key=lambda f: (f["source_path"], f["face_id"])):
        path = f["source_path"]
        ev = evidence_by_path.get(path) or []
        font_ev = [e for e in ev if e.get("mentions_fonts")]
        sus = suspicions.get(f["face_id"], {})
        st = styles.get(f["face_id"], {})
        sg = sub_of.get(path)
        fr = by_file.get(path, {})
        healthy = f.get("parse_status") == "PARSED"
        suspected = sus.get("outcome") == "SUSPECTED_SYSTEM_FONT_COPY"
        cross = bool(sg and not sg.get("rights_batchable_with_siblings", True)) \
            if sg else False
        conflict = fam_state.get(f["face_id"]) == \
            FF.FAMILY_RELATIONSHIP_REVIEW_REQUIRED
        prio, reasons = prioritise(
            healthy=healthy, has_font_evidence=bool(font_ev), suspected=suspected,
            cross_package_dup=cross, family_conflict=conflict,
            unsupported=not healthy, curated_candidate=False)

        n = f.get("names") or {}
        rows.append({
            "schema_version": "font_face_manifest/1.0",
            "machine": {
                "source_path": path,
                "file_sha256": f["source_sha256"],
                "face_id": f["face_id"],
                "collection_index": f["collection_index"],
                "preferred_family": n.get("family_typographic"),
                "fallback_family": n.get("family_legacy"),
                "subfamily": n.get("subfamily_typographic")
                             or n.get("subfamily_legacy"),
                "postscript_name": n.get("postscript_name"),
                "vendor": f.get("vendor_id"),
                "version": f.get("version"),
                "weight_class": f.get("weight_class"),
                "width_class": f.get("width_class"),
                "italic": f.get("italic"),
                "is_variable": f.get("is_variable"),
                "variable_axes": [a["tag"] for a in f.get("variable_axes") or []],
                "scripts": f.get("scripts"),
                "script_coverage": f.get("script_coverage"),
                "dominant_script": f.get("dominant_script"),
                "glyph_count": f.get("glyph_count"),
                "file_format": f.get("extension"),
                "technical_health": ("HEALTHY" if healthy
                                     else fr.get("parse_status", "UNKNOWN")),
                "fstype": f.get("fstype"),
                "duplicate_group": (f["source_sha256"]
                                    if len(dedupe["by_hash"].get(
                                        f["source_sha256"], [])) > 1 else None),
                "technical_family": fam_of.get(f["face_id"]),
                "source_package": FP.package_of(path),
                "provenance_rights_subgroup": (
                    f"{sg['source_package']}::{sg['provenance_kind']}" if sg else None),
                "license_evidence": [e["evidence_file"] for e in ev],
                "license_evidence_mentioning_fonts":
                    [e["evidence_file"] for e in font_ev],
                "system_font_suspicion": sus.get("outcome"),
                "suspicion_confidence": sus.get("confidence"),
                "style_tags": st.get("tag_names", []),
                "quarantine_recommendation": (
                    "QUARANTINE_CANDIDATE" if suspected or not font_ev else None),
                "review_priority": prio,
                "review_reasons": reasons,
                "permissions": permissions(),
                "taxonomy_version": None,
                "parser": PARSER,
            },
            "human": human_block(),
            "machine_inference_immutable": True,
        })
    return rows
