"""DIP-0C4a runner — per-face font audit, TTC handling, family grouping, duplicates.

Read-only. No font is installed, rendered, embedded, exported, exposed or made
retrievable. Nothing here grants anything.

    python -m tools.dip0c.run_c4a
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter

from tools.dip0.integrity import compare, snapshot

from . import config as C
from . import fontfamily as FF
from . import fontinfo as FI
from . import run_c3b2

PARSER = f"{C.TOOL_NAME}.run_c4a/{C.TOOL_VERSION}"
OUT = C.OUTPUT_ROOT / "c4a"
INVENTORY = (C.REPO_ROOT / "var" / "design_intelligence" / "audits" / "dip0"
             / "inventory" / "inventory.jsonl")


def _val(v):
    return v.get("value") if isinstance(v, dict) else v


def load_fonts() -> list[dict]:
    """Every FONT row from the committed DIP-0A inventory."""
    out = []
    with INVENTORY.open() as fh:
        for line in fh:
            r = json.loads(line)
            if _val(r.get("category")) != "FONT":
                continue
            out.append({
                "relative_path": _val(r["relative_path"]),
                "filename": _val(r["filename"]),
                "extension": _val(r["extension"]),
                "sha256": r["sha256"],
                "size_bytes": r["size_bytes"],
            })
    return sorted(out, key=lambda r: r["relative_path"])


def audit(files: list[dict]) -> dict:
    # 1. DEDUP FIRST. Parse the unique set once; attach the result to every member.
    dd = FF.dedupe(files)

    faces: list[dict] = []
    file_records: list[dict] = []
    unsupported: list[dict] = []
    failed: list[dict] = []

    for h in dd["unique_hashes"]:
        rep = dd["by_hash"][h][0]                  # one representative per hash
        rec = FI.audit_file(C.SOURCE_ROOT.parent / rep["relative_path"], sha256=h)
        rec["duplicate_paths"] = [m["relative_path"] for m in dd["by_hash"][h]]
        rec["duplicate_count"] = len(dd["by_hash"][h])
        file_records.append(rec)
        if rec["parse_status"] == FI.UNSUPPORTED_FORMAT:
            unsupported.append(rec)
        elif rec["parse_status"] == FI.PARSE_FAILED:
            failed.append(rec)
        faces.extend(rec["faces"])

    groups = FF.build_groups(faces, by_hash=dd["by_hash"])
    return {"dedupe": dd, "files": file_records, "faces": faces, "groups": groups,
            "unsupported": unsupported, "failed": failed}


def summarise(files: list[dict], a: dict) -> dict:
    faces, groups, dd = a["faces"], a["groups"], a["dedupe"]
    collections_ = [f for f in a["files"] if f["is_collection"]]
    multi = [f for f in collections_ if f["face_count"] > 1]

    by_state = Counter(g["state"] for g in groups)
    scripts = Counter(s for f in faces for s in f["scripts"])
    dominant = Counter(f["dominant_script"] for f in faces if f["dominant_script"])
    exts = Counter(_val(f["extension"]) for f in files)
    variable = [f for f in faces if f["is_variable"]]
    key_src = Counter(g["key_source"] for g in groups)
    fstype = Counter(fl for f in faces for fl in f["fstype"]["flags"])

    # how badly would name ID 1 have fragmented things? (D2, measured)
    id16_keys = {FF.normalize(f["names"].get("family_typographic"))
                 for f in faces if f["names"].get("family_typographic")}
    id1_keys = {FF.normalize(f["names"].get("family_legacy"))
                for f in faces if f["names"].get("family_legacy")}

    return {
        "files_total": len(files),
        "files_unique_by_hash": dd["files_unique"],
        "duplicate_groups": dd["duplicate_group_count"],
        "files_in_duplicate_groups": dd["files_in_duplicate_groups"],
        "faces_total": len(faces),
        "collection_files": len(collections_),
        "collection_faces": sum(f["face_count"] for f in collections_),
        "collections_with_multiple_faces": len(multi),
        "unsupported_files": len(a["unsupported"]),
        "failed_files": len(a["failed"]),
        "extensions": dict(exts.most_common()),
        "family_groups": len(groups),
        "family_group_states": dict(by_state),
        "family_key_source": dict(key_src),
        "id16_distinct_keys": len(id16_keys),
        "id1_distinct_keys": len(id1_keys),
        "variable_faces": len(variable),
        "variable_axes": sorted({ax["tag"] for f in variable
                                 for ax in f["variable_axes"]}),
        "scripts": dict(scripts.most_common()),
        "dominant_scripts": dict(dominant.most_common()),
        "fstype_flags": dict(fstype.most_common()),
        "largest_groups": [
            {"family": g["family_key"], "faces": g["face_count"],
             "vendors": g["vendors"], "state": g["state"]}
            for g in sorted(groups, key=lambda g: -g["face_count"])[:8]],
    }


def main(argv=None) -> int:
    t0 = time.monotonic()
    before = snapshot()

    files = load_fonts()
    if not files:
        print("no FONT rows in the DIP-0A inventory", file=sys.stderr)
        return 1
    print(f"auditing {len(files)} font files "
          f"({len({f['sha256'] for f in files})} unique by hash)...")

    a = audit(files)
    s = summarise(files, a)

    C.assert_output_safe(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    out_bytes = run_c3b2._write(OUT / "faces.json", a["faces"])
    out_bytes += run_c3b2._write(OUT / "files.json", a["files"])
    out_bytes += run_c3b2._write(OUT / "groups.json", a["groups"])

    # Lightweight, committed. The full 2,832-group list is 3.7 MB and belongs in var/;
    # what a human needs in git is the summary plus the groups that actually need a
    # decision — the ones the machine could NOT resolve.
    needs_review = [g for g in a["groups"]
                    if g["state"] != FF.FAMILY_GROUPED]
    biggest = sorted([g for g in a["groups"] if g["state"] == FF.FAMILY_GROUPED],
                     key=lambda g: -g["face_count"])[:40]

    def _slim(g):
        return {k: v for k, v in g.items()
                if k not in ("faces", "incompatible_faces", "note", "parser",
                             "schema_version")}

    light = {
        "slice": "DIP-0C4a",
        "summary": s,
        "note": "the FULL group list lives in var/design_intelligence/audits/dip0c/"
                "c4a/groups.json (3.7 MB, git-ignored). Committed here: every group "
                "that needs a human decision, plus the largest clean families.",
        "groups_needing_review": [_slim(g) for g in needs_review],
        "largest_clean_families": [_slim(g) for g in biggest],
    }
    out_bytes += run_c3b2._write(C.MILESTONE_OUTPUT_ROOT / "c4a_family_summary.json", light)

    after = snapshot()
    recon = {
        "slice": "DIP-0C4a",
        "c3e_commit": "a56109b",
        "summary": s,
        "corpus_shape": {
            "note": "the corpus is TWO populations, and folder is not a batch key",
            "packages": _packages(files),
        },
        "safety": {
            "fonts_installed": 0,
            "fonts_rendered": 0,
            "fonts_embedded_or_exported": 0,
            "permissions_granted": 0,
            "all_permissions_false": True,
            "note": "C4a AUDITS. It approves nothing, installs nothing, renders "
                    "nothing, and grants nothing. fsType is technical metadata, not "
                    "a licence.",
        },
        "integrity": {"materials": compare(before, after)},
        "runtime_seconds": round(time.monotonic() - t0, 2),
        "output_bytes": out_bytes,
    }
    run_c3b2._write(C.MILESTONE_OUTPUT_ROOT / "c4a_reconciliation.json", recon)
    _print(recon)

    ok = (recon["integrity"]["materials"]["unchanged"]
          and s["faces_total"] > s["files_unique_by_hash"] - 1
          and s["unsupported_files"] > 0)          # the .fon files must be surfaced
    if not ok:
        print("\nFAILED: a C4a invariant broke", file=sys.stderr)
        return 1
    return 0


def _packages(files: list[dict]) -> list[dict]:
    c = Counter(str(C.Path(f["relative_path"]).parent) for f in files)
    return [{"package": k, "files": v} for k, v in c.most_common(8)]


def _print(r: dict) -> None:
    s = r["summary"]
    print("\nDIP-0C4a — font technical audit, families, duplicates")
    print(f"  files:    {s['files_total']}  ->  {s['files_unique_by_hash']} unique "
          f"by hash  ({s['duplicate_groups']} duplicate groups covering "
          f"{s['files_in_duplicate_groups']} files)")
    print(f"  FACES:    {s['faces_total']}   <- a file is NOT a font")
    print(f"            {s['collection_files']} .ttc/.otc files -> "
          f"{s['collection_faces']} faces "
          f"({s['collections_with_multiple_faces']} carry more than one)")
    print(f"  unparsed: {s['unsupported_files']} UNSUPPORTED_FORMAT (.fon), "
          f"{s['failed_files']} PARSE_FAILED — all surfaced, none dropped")
    print(f"  families: {s['family_groups']} review groups")
    for k, v in s["family_group_states"].items():
        print(f"              {v:5d}  {k}")
    print(f"  D2 key:   ID16 -> {s['id16_distinct_keys']} distinct families | "
          f"ID1 -> {s['id1_distinct_keys']} "
          f"(ID1 would fragment by "
          f"{s['id1_distinct_keys'] - s['id16_distinct_keys']:+d})")
    print(f"  scripts:  {dict(list(s['dominant_scripts'].items())[:6])}")
    print(f"  variable: {s['variable_faces']} faces, axes {s['variable_axes']}")
    print(f"  fsType:   {s['fstype_flags']}  (metadata, NOT permission)")
    print("  largest groups:")
    for g in s["largest_groups"][:5]:
        print(f"     {g['faces']:4d}  {str(g['family'])[:34]:34s} "
              f"{g['vendors']}  {g['state']}")
    print(f"  integrity: materials_unchanged="
          f"{r['integrity']['materials']['unchanged']}")
    print(f"  runtime:   {r['runtime_seconds']}s | output {r['output_bytes']} bytes")


if __name__ == "__main__":
    raise SystemExit(main())
