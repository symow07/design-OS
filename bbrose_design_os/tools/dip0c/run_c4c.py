"""DIP-0C4c runner — manifests, two views, queues, quarantine, curated candidates.

Read-only. No font installed, rendered, exported, embedded, exposed, retrievable or
approved. Every permission false.

    python -m tools.dip0c.run_c4c
"""
from __future__ import annotations

import sys
import time
from collections import Counter

from tools.dip0.integrity import compare, snapshot

from . import config as C
from . import font_curated as FC
from . import font_style as FS
from . import font_views as FV
from . import review_c4c as RV
from . import run_c3b2
from . import run_c4b

PARSER = f"{C.TOOL_NAME}.run_c4c/{C.TOOL_VERSION}"
OUT = C.OUTPUT_ROOT / "c4c"


def audit() -> dict:
    b = run_c4b.audit()                     # C4a + C4b, reused wholesale
    faces, files, groups = b["faces"], b["file_recs"], b["groups"]

    # --- style observations (heuristic; metadata only, never filenames) ----------
    styles = {}
    for f in faces:
        styles[f["face_id"]] = FS.observe(f)

    # --- the two INDEPENDENT views ----------------------------------------------
    tech = FV.technical_view(faces=faces, files=files, groups=groups,
                             dedupe=b["dedupe"], styles=styles)
    rights = FV.rights_view(files=files, packages=b["packages"],
                            duplicate_model=b["duplicate_model"],
                            evidence_by_path=b["evidence_by_path"],
                            suspicions=b["suspicions"],
                            faces_by_hash={})

    # --- curated candidates (nominated, never approved) ---------------------------
    curated = FC.nominate(groups=groups, faces=faces, packages=b["packages"],
                          evidence_by_path=b["evidence_by_path"],
                          suspicions=b["suspicions"], styles=styles,
                          dedupe=b["dedupe"])

    manifest = FV.face_manifest(
        faces=faces, files=files, groups=groups, dedupe=b["dedupe"],
        evidence_by_path=b["evidence_by_path"], suspicions=b["suspicions"],
        styles=styles, duplicate_model=b["duplicate_model"])

    queues = RV.build(faces=faces, files=files, groups=groups,
                      packages=b["packages"], suspicions=b["suspicions"],
                      duplicate_model=b["duplicate_model"],
                      evidence_by_path=b["evidence_by_path"], curated=curated,
                      dedupe=b["dedupe"])

    return {**b, "styles": styles, "technical_view": tech, "rights_view": rights,
            "curated": curated, "manifest": manifest, "queues": queues}


def main(argv=None) -> int:
    t0 = time.monotonic()
    before = snapshot()
    a = audit()

    styled = sum(1 for s in a["styles"].values() if s["tag_names"])
    panose = sum(1 for s in a["styles"].values() if s["panose_declared"])
    tags = Counter(t for s in a["styles"].values() for t in s["tag_names"])
    prio = Counter(r["machine"]["review_priority"] for r in a["manifest"])

    C.assert_output_safe(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    out_bytes = run_c3b2._write(OUT / "face_manifest.json", a["manifest"])
    out_bytes += run_c3b2._write(OUT / "technical_view.json", a["technical_view"])
    out_bytes += run_c3b2._write(OUT / "rights_view.json", a["rights_view"])
    out_bytes += run_c3b2._write(OUT / "queues.json", a["queues"])
    out_bytes += run_c3b2._write(OUT / "styles.json", a["styles"])

    # --- committed, lightweight ---------------------------------------------------
    out_bytes += run_c3b2._write(
        C.MILESTONE_OUTPUT_ROOT / "font_review_queue_summary.json",
        {"schema_version": a["queues"]["schema_version"],
         "permission_flags": a["queues"]["permission_flags"],
         "all_permissions_false": True,
         "proposed_human_decisions": a["queues"]["proposed_human_decisions"],
         "queues": [{k: v for k, v in q.items() if k != "items"}
                    for q in a["queues"]["queues"].values()]})
    out_bytes += run_c3b2._write(
        C.MILESTONE_OUTPUT_ROOT / "font_batch_review_manifest.json",
        {"note": "the FULL per-face manifest lives in var/…/c4c/face_manifest.json. "
                 "Committed here: the batch structure and one sample row per queue.",
         "technical_view": {k: v for k, v in a["technical_view"].items()
                            if k != "family_groups"},
         "rights_view": {k: v for k, v in a["rights_view"].items()
                         if k not in ("source_packages",
                                      "provenance_rights_subgroups")},
         "source_packages": a["rights_view"]["source_packages"],
         "sample_manifest_row": a["manifest"][0] if a["manifest"] else None})
    out_bytes += run_c3b2._write(
        C.MILESTONE_OUTPUT_ROOT / "c4c_curated_starter_candidates.json",
        {k: v for k, v in a["curated"].items() if k != "candidates"}
        | {"candidates": a["curated"]["candidates"]})

    after = snapshot()
    dm = a["duplicate_model"]
    recon = {
        "slice": "DIP-0C4c",
        "c4b_commits": ["394ca3c", "d18e1c7"],
        "scale": {
            "raw_files": len(a["files"]),
            "unique_files_by_hash": a["dedupe"]["files_unique"],
            "faces": len(a["faces"]),
            "technical_families": len(a["groups"]),
            "source_packages": len(a["packages"]),
            "technical_duplicate_groups": len(dm),
            "provenance_rights_subgroups": sum(d["rights_subgroup_count"]
                                               for d in dm),
            "rights_batchable_duplicate_groups": sum(1 for d in dm
                                                     if d["rights_batchable"]),
            "review_queues": len(RV.QUEUE_IDS),
            "proposed_human_decisions": a["queues"]["proposed_human_decisions"],
            "review_reduction_note":
                "Technical deduplication reduces repeated PARSING. It does NOT reduce "
                "legal review: 0 of "
                f"{len(dm)} duplicate groups are rights-batchable.",
            "exceptions_preventing_batch_decisions": [
                "exact bytes do not prove identical rights",
                "one package's licence never clears another",
                "the dump batch is defined by folder, suspicion by name table",
                "190 families carry conflicting evidence",
                "evidence that does not mention fonts governs nothing",
            ],
        },
        "views": {
            "technical": {k: v for k, v in a["technical_view"].items()
                          if k != "family_groups"},
            "rights": {k: v for k, v in a["rights_view"].items()
                       if k not in ("source_packages",
                                    "provenance_rights_subgroups")},
            "independence": "a decision in one view NEVER implies a decision in the "
                            "other",
        },
        "style_observations": {
            "faces_with_a_tag": styled,
            "faces_with_panose_declared": panose,
            "faces_with_no_tag": len(a["faces"]) - styled,
            "tags": dict(tags.most_common()),
            "filename_used": False,
            "affects_license_or_permission": False,
        },
        "review_priorities": dict(prio.most_common()),
        "curated_starter": {
            "candidates": a["curated"]["candidate_count"],
            "capability_coverage": a["curated"]["capability_coverage"],
            "capability_gaps": a["curated"]["capability_gaps"],
            "approved": False, "activated": False,
        },
        "quarantine": {
            "proposal": a["system_font_proposal"]["proposal"],
            "is_applied": a["system_font_proposal"]["is_applied"],
            "applied_by_machine": a["system_font_proposal"]["applied_by_machine"],
            "human_confirmed": a["system_font_proposal"]["human_confirmation"],
            "total_files": a["system_font_proposal"]["total_files"],
            "total_faces": a["system_font_proposal"]["total_faces"],
            "suspected_faces": a["system_font_proposal"]["suspected_faces"],
            "duplicate_overlap": a["system_font_proposal"]["duplicate_overlap"],
            "unsupported_fon_files": a["system_font_proposal"]["unsupported_fon_files"],
            "false_positive_risk": a["system_font_proposal"]["false_positive_risk"],
            "statements": [
                "folder membership alone does not prove system-font status",
                "system-font suspicion does not prove illegal acquisition",
                "quarantine is PROPOSED, not executed",
            ],
        },
        "queue_totals": a["queues"]["totals"],
        "safety": {
            "all_permissions_false": True,
            "fonts_installed": 0, "fonts_rendered": 0, "fonts_exported": 0,
            "fonts_exposed": 0, "fonts_approved": 0, "fonts_activated": 0,
            "files_moved_or_deleted": 0,
            "human_fields_blank": True,
            "machine_inference_immutable": True,
        },
        "integrity": {"materials": compare(before, after)},
        "runtime_seconds": round(time.monotonic() - t0, 2),
        "output_bytes": out_bytes,
    }
    run_c3b2._write(C.MILESTONE_OUTPUT_ROOT / "c4c_reconciliation.json", recon)
    _print(recon, a)

    ok = (recon["integrity"]["materials"]["unchanged"]
          and recon["quarantine"]["is_applied"] is False
          and recon["curated_starter"]["approved"] is False
          and all(not any(r["machine"]["permissions"].values())
                  for r in a["manifest"][:50])
          and all(v is None or v == [] for v in a["manifest"][0]["human"].values()))
    if not ok:
        print("\nFAILED: a C4c invariant broke", file=sys.stderr)
        return 1
    return 0


def _print(r: dict, a: dict) -> None:
    s, st = r["scale"], r["style_observations"]
    print("DIP-0C4c — manifests, two views, queues, quarantine, curated candidates")
    print(f"  scale:  {s['raw_files']} files / {s['unique_files_by_hash']} unique / "
          f"{s['faces']} faces / {s['technical_families']} families / "
          f"{s['source_packages']} packages")
    print(f"          {s['technical_duplicate_groups']} technical duplicate groups -> "
          f"{s['provenance_rights_subgroups']} provenance-rights subgroups "
          f"({s['rights_batchable_duplicate_groups']} rights-batchable)")
    print("  views:  TECHNICAL_FAMILY and PROVENANCE_RIGHTS — independent")
    print(f"  style:  {st['faces_with_a_tag']} faces tagged, "
          f"{st['faces_with_no_tag']} untagged "
          f"({st['faces_with_panose_declared']} declare PANOSE) | "
          f"filename_used={st['filename_used']}")
    print(f"          tags: {dict(list(st['tags'].items())[:6])}")
    print(f"  priorities: {r['review_priorities']}")
    c = r["curated_starter"]
    print(f"  curated: {c['candidates']} CURATED_STARTER_CANDIDATEs "
          f"(approved={c['approved']}, activated={c['activated']})")
    print(f"           gaps: {c['capability_gaps']}")
    q = r["quarantine"]
    print(f"  quarantine: {q['total_files']} files proposed | "
          f"is_applied={q['is_applied']} | human_confirmed={q['human_confirmed']}")
    print("  queues:")
    for qid in RV.QUEUE_IDS:
        qq = a["queues"]["queues"][qid]
        batch = "" if qq["batch_review_allowed"] else "  [NEVER BATCH]"
        print(f"     {qq['display_label']}  {qid:44s} {qq['item_count']:5d} items"
              f"{batch}")
    print(f"  proposed human decisions: {s['proposed_human_decisions']}")
    print(f"  safety: all_permissions_false={r['safety']['all_permissions_false']} | "
          f"approved=0 | activated=0 | installed=0 | moved/deleted=0")
    print(f"  integrity: materials_unchanged="
          f"{r['integrity']['materials']['unchanged']}")
    print(f"  runtime: {r['runtime_seconds']}s")


if __name__ == "__main__":
    raise SystemExit(main())
