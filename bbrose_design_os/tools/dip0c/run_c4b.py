"""DIP-0C4b runner — system-font suspicion, packages, licence evidence, queues.

Read-only. No font is installed, rendered, copied, embedded, exported or made
retrievable. No file is moved or deleted. Every permission is false.

    python -m tools.dip0c.run_c4b
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict

from tools.dip0.integrity import compare, snapshot

from . import config as C
from . import font_packages as FP
from . import font_provenance as FPV
from . import font_rights as FR
from . import fontfamily as FF
from . import review_c4 as RV
from . import run_c3b2
from . import run_c4a

PARSER = f"{C.TOOL_NAME}.run_c4b/{C.TOOL_VERSION}"
OUT = C.OUTPUT_ROOT / "c4b"
C4A = C.OUTPUT_ROOT / "c4a"


def _val(v):
    return v.get("value") if isinstance(v, dict) else v


def load_c4a() -> dict:
    """The C4a audit. Re-run C4a first if it is not on disk."""
    need = [C4A / "faces.json", C4A / "files.json", C4A / "groups.json"]
    if not all(p.exists() for p in need):
        print("C4a output missing — running it first...")
        if run_c4a.main() != 0:
            raise SystemExit("C4a failed")
    return {
        "faces": json.loads((C4A / "faces.json").read_text()),
        "files": json.loads((C4A / "files.json").read_text()),
        "groups": json.loads((C4A / "groups.json").read_text()),
    }


def load_inventory_evidence() -> dict:
    """The licence-evidence associations DIP-0A already found, per font path."""
    out: dict[str, list] = {}
    with run_c4a.INVENTORY.open() as fh:
        for line in fh:
            r = json.loads(line)
            if _val(r.get("category")) != "FONT":
                continue
            ev = r.get("license_evidence") or []
            if isinstance(ev, dict):
                ev = ev.get("value") or []
            out[_val(r["relative_path"])] = ev
    return out


def audit() -> dict:
    c4a = load_c4a()
    files = run_c4a.load_fonts()
    dd = FF.dedupe(files)
    faces = c4a["faces"]
    file_recs = c4a["files"]

    # C4a stored the family key on each face; restore it (json round-trip keeps it)
    for f in faces:
        f.setdefault("_family_key", None)

    # --- 1. licence evidence, RE-READ ------------------------------------------
    raw_ev = load_inventory_evidence()
    evidence_by_path: dict[str, list] = {}
    for f in files:
        rows = raw_ev.get(f["relative_path"]) or []
        if rows:
            evidence_by_path[f["relative_path"]] = FP.associate(f, rows)

    # --- 2. system-font suspicion, from the NAME TABLE --------------------------
    faces_by_hash: dict[str, list] = defaultdict(list)
    for fr in file_recs:
        for fc in fr["faces"]:
            faces_by_hash[fr["source_sha256"]].append(fc)

    # a hash is "suspect" if any of its faces names an OS foundry
    suspect_hashes = set()
    prelim = {}
    for fc in faces:
        s = FPV.assess(fc)
        prelim[fc["face_id"]] = s
        if s["outcome"] in (FPV.SUSPECTED_SYSTEM_FONT_COPY,
                            FPV.SYSTEM_FONT_EVIDENCE_PRESENT):
            suspect_hashes.add(fc["source_sha256"])

    suspicions = {}
    for fc in faces:
        in_dump = FP.classify_package(
            FP.package_of(fc["source_path"])) == FP.PKG_SUSPECTED_DUMP
        dup_of_suspect = (fc["source_sha256"] in suspect_hashes
                          and prelim[fc["face_id"]]["outcome"]
                          == FPV.NO_SYSTEM_FONT_EVIDENCE)
        suspicions[fc["face_id"]] = FPV.assess(
            fc, in_dump_folder=in_dump, duplicate_of_suspect=dup_of_suspect)

    # --- 3. packages ------------------------------------------------------------
    packages = FP.build_packages(files, faces_by_hash, evidence_by_path)
    overlap = FP.dump_overlap(files)

    # --- 4. rights recommendation per batch -------------------------------------
    files_by_pkg: dict[str, list] = defaultdict(list)
    for fr in file_recs:
        pkg = FP.package_of(fr["source_path"])
        key = ("materials/Fonts[+3333]"
               if FP.classify_package(pkg) == FP.PKG_SUSPECTED_DUMP else pkg)
        files_by_pkg[key].append(fr)

    batches = []
    for p in packages:
        pf = files_by_pkg.get(p["package_key"], [])
        pfaces = [fc for fr in pf for fc in fr["faces"]]
        batches.append(FR.assess_batch(
            batch_id=p["package_key"], kind=p["package_kind"],
            faces=pfaces, files=pf, package=p, suspicions=suspicions))

    # --- 5. EXACT BYTES DO NOT PROVE IDENTICAL RIGHTS ---------------------------
    dup_model = FR.duplicate_review_model(dd, evidence_by_path, faces_by_hash)

    unparseable = [fr for fr in file_recs
                   if fr["parse_status"] in ("UNSUPPORTED_FORMAT", "PARSE_FAILED")]
    dump_files = [f for f in files
                  if FP.classify_package(FP.package_of(f["relative_path"]))
                  == FP.PKG_SUSPECTED_DUMP]
    dump_faces = [fc for fc in faces
                  if FP.classify_package(FP.package_of(fc["source_path"]))
                  == FP.PKG_SUSPECTED_DUMP]
    proposal = FR.system_font_batch_proposal(
        files=dump_files, faces=dump_faces, suspicions=suspicions,
        overlap=overlap, unparseable=unparseable)

    ev_font_count = sum(1 for rows in evidence_by_path.values()
                        if any(e["mentions_fonts"] for e in rows))
    curated = FR.curated_library_recommendation(
        packages=packages, evidence_fonts=ev_font_count, faces=faces)

    leverage = FR.batch_leverage(files=files, faces=faces, groups=c4a["groups"],
                                 packages=packages, suspicions=suspicions,
                                 dedupe=dd, duplicate_model=dup_model)
    queues = RV.build(faces=faces, files=file_recs, groups=c4a["groups"],
                      packages=packages, suspicions=suspicions, batches=batches,
                      dedupe=dd)

    return {"files": files, "file_recs": file_recs, "faces": faces,
            "groups": c4a["groups"], "dedupe": dd,
            "evidence_by_path": evidence_by_path, "suspicions": suspicions,
            "packages": packages, "overlap": overlap, "batches": batches,
            "leverage": leverage, "queues": queues,
            "duplicate_model": dup_model, "system_font_proposal": proposal,
            "curated_recommendation": curated}


def main(argv=None) -> int:
    t0 = time.monotonic()
    before = snapshot()
    a = audit()

    sus = Counter(s["outcome"] for s in a["suspicions"].values())
    foundries = Counter(f for s in a["suspicions"].values() for f in s["foundries"])
    ev_types = Counter(e["license_type"]
                       for rows in a["evidence_by_path"].values() for e in rows)
    pkg_kinds = Counter(p["package_kind"] for p in a["packages"])
    postures = Counter(b["reuse_posture"] for b in a["batches"])

    suspected_faces = [fid for fid, s in a["suspicions"].items()
                       if s["outcome"] == FPV.SUSPECTED_SYSTEM_FONT_COPY]
    suspect_hashes = {f["source_sha256"] for f in a["faces"]
                      if f["face_id"] in set(suspected_faces)}
    suspect_families = {f.get("_family_key") for f in a["faces"]
                        if f["face_id"] in set(suspected_faces) and f.get("_family_key")}

    fonts_with_ev = len(a["evidence_by_path"])
    ev_mentioning_fonts = sum(
        1 for rows in a["evidence_by_path"].values()
        if any(e["mentions_fonts"] for e in rows))

    C.assert_output_safe(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    out_bytes = run_c3b2._write(OUT / "suspicions.json", a["suspicions"])
    out_bytes += run_c3b2._write(OUT / "duplicate_review_model.json",
                                 a["duplicate_model"])
    out_bytes += run_c3b2._write(OUT / "packages.json", a["packages"])
    out_bytes += run_c3b2._write(OUT / "queues.json", a["queues"])

    light_queues = {
        "schema_version": a["queues"]["schema_version"],
        "permission_flags": a["queues"]["permission_flags"],
        "permission_flag_count": a["queues"]["permission_flag_count"],
        "all_permissions_false": True,
        "queues": [{k: v for k, v in q.items() if k != "items"}
                   for q in a["queues"]["queues"].values()],
    }
    out_bytes += run_c3b2._write(C.MILESTONE_OUTPUT_ROOT / "c4b_review_queue_summary.json",
                                 light_queues)
    out_bytes += run_c3b2._write(
        C.MILESTONE_OUTPUT_ROOT / "c4b_license_evidence_report.json",
        {"evidence_types": dict(ev_types.most_common()),
         "fonts_with_evidence": fonts_with_ev,
         "fonts_with_evidence_mentioning_fonts": ev_mentioning_fonts,
         "packages": [{k: v for k, v in p.items()
                       if k not in ("license_evidence",)}
                      for p in a["packages"] if p["has_license_evidence"]]})

    after = snapshot()
    recon = {
        "slice": "DIP-0C4b",
        "c4a_commit": "2447a72",
        "system_font_suspicion": {
            "outcomes": dict(sus),
            "suspected_faces": len(suspected_faces),
            "suspected_files": len(suspect_hashes),
            "suspected_families": len(suspect_families),
            "foundries": dict(foundries.most_common()),
            "filename_used": False,
            "confidence_cap": FPV.CONFIDENCE_CAP,
        },
        "source_packages": {
            "total": len(a["packages"]),
            "kinds": dict(pkg_kinds),
            "with_license_evidence": sum(1 for p in a["packages"]
                                         if p["has_license_evidence"]),
        },
        "duplicated_dump": a["overlap"],
        "license_evidence": {
            "fonts_with_evidence": fonts_with_ev,
            "fonts_whose_evidence_mentions_fonts": ev_mentioning_fonts,
            "fonts_without_evidence": len(a["files"]) - fonts_with_ev,
            "evidence_types": dict(ev_types.most_common()),
        },
        "quarantine": {
            "batch_postures": dict(postures),
            "quarantine_candidate_batches": postures.get("QUARANTINE_CANDIDATE", 0),
            "files_moved_or_deleted": 0,
            "machine_may_delete_or_reject": False,
        },
        "duplicate_rights_model": {
            "rule": "EXACT BYTES DO NOT PROVE IDENTICAL RIGHTS. Exact duplicates are "
                    "safe as ONE TECHNICAL IDENTITY decision; rights remain "
                    "PROVENANCE-AWARE.",
            "duplicate_groups": len(a["duplicate_model"]),
            "rights_batchable_groups": sum(1 for d in a["duplicate_model"]
                                           if d["rights_batchable"]),
            "groups_needing_separate_rights_review": sum(
                1 for d in a["duplicate_model"] if not d["rights_batchable"]),
            "total_rights_subgroups": sum(d["rights_subgroup_count"]
                                          for d in a["duplicate_model"]),
        },
        "system_font_batch_proposal": a["system_font_proposal"],
        "curated_library_recommendation": a["curated_recommendation"],
        "fail_closed_policy": FR.FAIL_CLOSED_POLICY,
        "no_suspicion_is_not_safety": FR.NO_SUSPICION_IS_NOT_SAFETY,
        "batch_leverage": a["leverage"],
        "queues": [{k: v for k, v in q.items() if k != "items"}
                   for q in a["queues"]["queues"].values()],
        "queue_totals": a["queues"]["totals"],
        "safety": {
            "permission_flags": len(a["queues"]["permission_flags"]),
            "all_permissions_false": True,
            "fonts_installed": 0, "fonts_rendered": 0, "fonts_exposed": 0,
            "approval_states_emitted": 0,
        },
        "integrity": {"materials": compare(before, after)},
        "runtime_seconds": round(time.monotonic() - t0, 2),
        "output_bytes": out_bytes,
    }
    run_c3b2._write(C.MILESTONE_OUTPUT_ROOT / "c4b_reconciliation.json", recon)
    _print(recon, a)

    ok = (recon["integrity"]["materials"]["unchanged"]
          and recon["quarantine"]["files_moved_or_deleted"] == 0
          and a["system_font_proposal"]["is_applied"] is False
          and all(not any(b["permissions"].values()) for b in a["batches"])
          and all(not any(sg["permissions"].values())
                  for d in a["duplicate_model"]
                  for sg in d["provenance_rights_subgroups"]))
    if not ok:
        print("\nFAILED: a C4b invariant broke", file=sys.stderr)
        return 1
    return 0


def _print(r: dict, a: dict) -> None:
    s, lv = r["system_font_suspicion"], r["batch_leverage"]
    print("DIP-0C4b — system-font suspicion, packages, licence evidence")
    print(f"  suspicion (from the NAME TABLE, filename_used={s['filename_used']}):")
    for k, v in s["outcomes"].items():
        print(f"     {v:5d}  {k}")
    print(f"     suspected: {s['suspected_faces']} faces / {s['suspected_files']} "
          f"files / {s['suspected_families']} families")
    print(f"     foundries: {dict(list(s['foundries'].items())[:6])}")
    print(f"  packages:  {r['source_packages']['total']} "
          f"({r['source_packages']['kinds']}), "
          f"{r['source_packages']['with_license_evidence']} with evidence")
    d = r["duplicated_dump"]
    print(f"  dump:      Fonts/3333={d['fonts_3333_unique_hashes']} vs "
          f"Fonts={d['fonts_unique_hashes']} | shared={d['shared_hashes']} "
          f"({d['overlap_pct_of_fonts']}%) -> {d['conclusion']}")
    e = r["license_evidence"]
    print(f"  evidence:  {e['fonts_with_evidence']} fonts have some; only "
          f"{e['fonts_whose_evidence_mentions_fonts']} have evidence that MENTIONS "
          f"FONTS")
    print(f"             {e['fonts_without_evidence']} fonts have NONE")
    print(f"             types: {dict(list(e['evidence_types'].items())[:6])}")
    print(f"  quarantine: {r['quarantine']['quarantine_candidate_batches']} candidate "
          f"batches | files moved/deleted: "
          f"{r['quarantine']['files_moved_or_deleted']}")
    dm = r["duplicate_rights_model"]
    print("  EXACT BYTES != IDENTICAL RIGHTS:")
    print(f"     {dm['duplicate_groups']} duplicate groups -> "
          f"{dm['total_rights_subgroups']} provenance-rights subgroups")
    print(f"     rights-batchable: {dm['rights_batchable_groups']} | "
          f"need separate rights review: "
          f"{dm['groups_needing_separate_rights_review']}")
    print("  batch leverage:")
    print(f"     raw: {lv['raw_files']} files / {lv['faces']} faces / "
          f"{lv['family_groups']} families / {lv['source_packages']} packages")
    for x in lv["levers"]:
        safe = "SAFE as one decision" if x["safe_as_one_decision"] else "NOT safe alone"
        n = x.get("removes_files") or x.get("removes_faces") or x.get("batches") or \
            x.get("families_split_across_packages")
        print(f"     {x['lever']:42s} {str(n):>6s}  [{safe}]")
    print("  queues:")
    for q in r["queues"]:
        print(f"     {q['display_label']}  {q['queue_id']:32s} "
              f"{q['item_count']:5d} items  {q['file_count']:5d} files  "
              f"{q['priority']}")
    print(f"  safety:    all_permissions_false="
          f"{r['safety']['all_permissions_false']} | installed=0 | rendered=0")
    print(f"  integrity: materials_unchanged="
          f"{r['integrity']['materials']['unchanged']}")
    print(f"  runtime:   {r['runtime_seconds']}s")


if __name__ == "__main__":
    raise SystemExit(main())
