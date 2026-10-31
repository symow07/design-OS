"""DIP-0B1 runner: `python -m tools.dip0b.run [--milestone] [--limit-*]`.

Read-only over the 14 approved HISTORICAL_DESIGN pilot files. `materials/` is
never written to; a pre/post snapshot proves it and the process exits non-zero
if anything changed.
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace
from pathlib import Path

import fitz

from tools.dip0 import integrity as I

from . import config as C
from . import report as R
from .inspect import inspect_file
from .limits import Budget
from .preview import render_page


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dip0b")
    ap.add_argument("--milestone", action="store_true",
                    help="refresh the committed docs/design_intelligence/dip0b record")
    ap.add_argument("--no-previews", action="store_true")
    ap.add_argument("--max-xref-scan", type=int)
    ap.add_argument("--max-paths-detailed", type=int)
    ap.add_argument("--max-render-px", type=int)
    ap.add_argument("--max-page-seconds", type=float)
    args = ap.parse_args(argv)

    limits = C.DEFAULT_LIMITS
    for field in ("max_xref_scan", "max_paths_detailed", "max_render_px",
                  "max_page_seconds"):
        v = getattr(args, field)
        if v is not None:
            limits = replace(limits, **{field: v})

    t0 = time.time()
    C.ensure_output_dirs()
    out_check = I.no_output_under_source()
    if not out_check["ok"]:
        print("FATAL: output root is inside the read-only source root")
        return 2

    print(f"source : {C.SOURCE_ROOT}")
    print(f"output : {C.OUTPUT_ROOT}")
    print(f"limits : {limits.to_dict()}")

    print("[1/5] snapshotting source tree …")
    before = I.snapshot()

    print("[2/5] loading pilot (HISTORICAL_DESIGN only) …")
    pilot = C.load_pilot()
    print(f"      {len(pilot)} files")

    print("[3/5] technical inspection …")
    records = []
    for e in pilot:
        rel = e["relative_path"]
        rec = inspect_file(rel, limits)
        records.append(rec)
        R.write_technical(rec)
        trunc = " DATA_LOSS" if rec["limits"]["data_loss"] else ""
        print(f"      {Path(rel).name}: {len(rec['pages'])}p "
              f"paths={sum(p['paths']['total'] for p in rec['pages'])} "
              f"spots={len(rec['separations']['spot_names'])}"
              f"{'+reg' if rec['separations']['has_registration'] else ''}{trunc}")

    previews: dict = {}
    if not args.no_previews:
        print("[4/5] previews (clipped to design surface) …")
        for e in pilot:
            rel = e["relative_path"]
            doc = fitz.open(C.physical_path(rel, C.REPO_ROOT))
            try:
                b = Budget(limits)
                previews[rel] = [render_page(doc, doc[i], i, rel, b)
                                 for i in range(doc.page_count)]
            finally:
                doc.close()
        total_px = sum(p["bytes"] for v in previews.values() for p in v)
        print(f"      {sum(len(v) for v in previews.values())} PNGs, "
              f"{total_px / 1e6:.1f} MB")
    else:
        print("[4/5] previews skipped")

    print("[5/5] reconciling + verifying integrity …")
    recon = R.reconcile(records)
    after = I.compare(before, I.snapshot())
    integ = {"source_unchanged": after["unchanged"],
             "output_outside_source": out_check["ok"], "detail": after}
    paths = R.write_reports(records, recon, previews, integ)
    if args.milestone:
        d = R.write_milestone_docs(recon, Path(paths["summary_md"]))
        print(f"      milestone docs → {d['docs_dir']}")

    ok = after["unchanged"] and out_check["ok"]
    print()
    print(f"files/pages           : {recon['files']}/{recon['pages']}")
    print(f"live text spans       : {recon['live_text_spans_total']} "
          f"(all typography outlined: {recon['all_typography_outlined']})")
    print(f"distinct spot inks    : {recon['separations']['distinct_spot_inks']}")
    print(f"files w/ registration : {recon['separations']['registration_count']}")
    print(f"AI private parsed     : {recon['ai_private_parsed']}")
    print(f"data loss (guards)    : {recon['files_with_data_loss'] or 'none'}")
    print(f"bounded sampling      : {len(recon['files_with_bounded_sampling'])}/{recon['files']} "
          f"(aggregates complete: {recon['aggregates_complete_for_all_files']})")
    print(f"source tree unchanged : {after['unchanged']}")
    print(f"no output under source: {out_check['ok']}")
    if not after["unchanged"]:
        print(f"  added={after['added'][:3]} removed={after['removed'][:3]} "
              f"modified={after['modified'][:3]}")
    print(f"\nwrote {paths['summary_md']}")
    print(f"elapsed {time.time() - t0:.1f}s")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
