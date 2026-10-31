"""DIP-0A runner: `python -m tools.dip0.run [--no-cache] [--full-hash-verify]`.

Pipeline: snapshot → walk+hash → detect → archives → fonts → classify →
duplicates → pilot → reconcile → verify integrity → write outputs.

`materials/` is never written to. The pre/post snapshot proves it.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import archives as A
from . import classify as CL
from . import config as C
from . import fonts as F
from . import integrity as I
from . import report as R
from .detect import detect
from .pilot import build_pilot
from .walk import HashCache, group_duplicates, walk_corpus

# Estimates from the pre-audit, carried so divergence is reported, not hidden.
PRE_AUDIT_EXPECTED = {
    "indexed_files": 7586,
    "excluded_junk": 109,
    "duplicates.groups": 1017,
    "duplicates.redundant_copies": 1046,
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dip0")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--full-hash-verify", action="store_true",
                    help="re-hash every file after the run (slow, exhaustive)")
    ap.add_argument("--sample", type=int, default=50)
    ap.add_argument("--milestone", action="store_true",
                    help="also refresh the committed docs/design_intelligence/dip0a "
                         "milestone record (summary + pilot manifest only)")
    args = ap.parse_args(argv)

    t0 = time.time()
    C.ensure_output_dirs()
    for i, r in enumerate(C.corpus_roots()):
        print(f"source{'' if i == 0 else f' {i + 1}'} : {r}"
              f"{'' if r.exists() else '   (ABSENT — contributes no rows)'}")
    print(f"output : {C.OUTPUT_ROOT}")

    out_check = I.no_output_under_source()
    if not out_check["ok"]:
        print("FATAL: output root is inside the read-only source root")
        return 2

    print("[1/8] snapshotting source tree …")
    before = I.snapshot()
    # §BH30(h)(2): every regen states aloud what the ruled exclusion list keeps
    # OUT of the governed corpus — each entry as typed, with its on-disk size.
    excluded = C.excluded_entries_on_disk()
    print(f"      excluded by ruling (§BH30(h)(2)): {len(excluded)} entries")
    for e in excluded:
        print(f"        - {e['entry']}  [{e['kind']}] files={e['files']} bytes={e['bytes']:,}")
    C.OUT_REPORTS.mkdir(parents=True, exist_ok=True)
    (C.OUT_REPORTS / "excluded_by_ruling.json").write_text(
        json.dumps({"ruling": "§BH30(h)(2)", "entries": excluded}, indent=2))

    print("[2/8] walking + hashing …")
    cache = None if args.no_cache else HashCache(C.OUT_TEMP / "hash_cache.json")
    res = walk_corpus(cache=cache)
    if cache:
        cache.save()
        print(f"      hash cache: {cache.hits} hits, {cache.misses} computed")
    print(f"      {len(res.files)} files, {len(res.junk)} junk, "
          f"{len(res.symlinks)} symlinks, {len(res.errors)} errors")

    print("[3/8] detecting signatures/MIME …")
    for r in res.files:
        detect(r)

    print("[4/8] inspecting archives (manifest only) …")
    arch = A.build_archive_report(res.files)
    print(f"      {arch['archive_count']} archives, "
          f"{arch['total_expanded_bytes'] / 1e9:.1f} GB expanded")

    print("[5/8] inspecting fonts (inventory level) …")
    fnt = F.build_font_report(res.files)
    print(f"      {fnt['font_file_count']} fonts, "
          f"{fnt['quarantined_count']} quarantined")

    print("[6/8] classifying + licence evidence …")
    CL.annotate(res.files)

    print("[7/8] duplicates + pilot …")
    dupes = group_duplicates(res.files)
    for r in res.files:
        r["duplicate_group"] = dupes["index"].get(r["relative_path"])
    pilot = build_pilot(res.files)
    print(f"      {dupes['group_count']} dup groups, "
          f"{dupes['redundant_bytes'] / 1e9:.2f} GB redundant; "
          f"pilot requirements met: {pilot['all_requirements_met']}")

    print("[8/8] verifying integrity + writing outputs …")
    after = I.compare(before, I.snapshot())
    hashes = I.verify_hashes(res.files,
                             sample=None if args.full_hash_verify else args.sample)
    recon = R.reconcile(res.files, res, dupes, arch, fnt, before, after,
                        hashes, out_check)
    div = R.compare_to_pre_audit(recon, PRE_AUDIT_EXPECTED)
    paths = R.write_all(res.files, res, dupes, arch, fnt, pilot, recon, div)

    if args.milestone:
        d = R.write_milestone_docs(recon, pilot, Path(paths["summary_md"]))
        print(f"      milestone docs → {d['docs_dir']}")

    unknown = recon["counts_by_category"].get("UNKNOWN", 0)
    ok = (after["unchanged"] and hashes["stable"] and out_check["ok"])
    print()
    print(f"UNKNOWN records       : {unknown}")
    print(f"source tree unchanged : {after['unchanged']}")
    print(f"hashes stable ({hashes['mode']}) : {hashes['stable']}")
    print(f"no output under source: {out_check['ok']}")
    if not after["unchanged"]:
        print(f"  added={after['added'][:5]} removed={after['removed'][:5]} "
              f"modified={after['modified'][:5]}")
    print(f"\nwrote {paths['summary_md']}")
    print(f"elapsed {time.time() - t0:.1f}s")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
