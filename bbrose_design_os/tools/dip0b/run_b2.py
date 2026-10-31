"""DIP-0B2 runner: `python -m tools.dip0b.run_b2 [--milestone] [--no-images]`.

Read-only over the 14 approved HISTORICAL_DESIGN pilot files. Produces
DesignUnitCandidates, numbered overlays, candidate crops and an editable
human-review JSON per page.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

import fitz

from tools.dip0 import integrity as I
from tools.dip0.report import json_default

from . import config as C
from .limits import Budget
from .overlay import render_crops, render_overlays
from .regions import DEFAULT_THRESHOLDS, segment_page
from .review import build_review, write_review


def _write_json(path: Path, obj) -> Path:
    C.assert_output_safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False,
                               default=json_default), encoding="utf-8")
    return path


def reconcile(segs: list[dict]) -> dict:
    types: Counter = Counter()
    ws_types: Counter = Counter()
    status: Counter = Counter()
    per_page = []
    manual_files = set()

    for s in segs:
        for c in s["candidates"]:
            types[c["candidate_type"]["value"]] += 1
        for c in s["workspace_candidates"]:
            ws_types[c["candidate_type"]["value"]] += 1
        status[s["segmentation"]["status"]] += 1
        if s["segmentation"]["status"] == "MANUAL_REQUIRED":
            manual_files.add(Path(s["file"]).name)
        per_page.append({
            "file": Path(s["file"]).name, "page": s["page"],
            "candidates": len(s["candidates"]),
            "workspace": len(s["workspace_candidates"]),
            "status": s["segmentation"]["status"],
            "failures": s["segmentation"]["failure_indicators"],
            "largest_coverage": s["segmentation"]["largest_candidate_coverage"],
        })

    return {
        "files": len({s["file"] for s in segs}),
        "pages": len(segs),
        "candidates_total": sum(len(s["candidates"]) for s in segs),
        "workspace_candidates_total": sum(len(s["workspace_candidates"]) for s in segs),
        "candidates_by_type": dict(types.most_common()),
        "workspace_candidates_by_type": dict(ws_types.most_common()),
        "segmentation_status_totals": dict(status.most_common()),
        "files_manual_required": sorted(manual_files),
        "per_page": per_page,
        "straddling_paths_total": sum(s["page_geometry"]["straddling_paths"] for s in segs),
        "off_canvas_paths_total": sum(s["page_geometry"]["fully_off_canvas_paths"]
                                      for s in segs),
        "background_paths_suppressed_total": sum(
            s["page_geometry"]["background_paths_suppressed"] for s in segs),
        "policy": ("candidates are machine-inferred until human-confirmed; a "
                   "full-bleed design may legitimately be one candidate; "
                   "off-canvas workspace candidates are never auto-included in "
                   "Historical Design Memory"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dip0b2")
    ap.add_argument("--milestone", action="store_true")
    ap.add_argument("--no-images", action="store_true",
                    help="skip overlays and crops")
    ap.add_argument("--max-crops-per-page", type=int)
    ap.add_argument("--max-render-px", type=int)
    args = ap.parse_args(argv)

    limits = C.DEFAULT_LIMITS
    for f in ("max_crops_per_page", "max_render_px"):
        v = getattr(args, f)
        if v is not None:
            limits = replace(limits, **{f: v})

    t0 = time.time()
    C.ensure_output_dirs()
    out_check = I.no_output_under_source()
    if not out_check["ok"]:
        print("FATAL: output root is inside the read-only source root")
        return 2

    print(f"source : {C.SOURCE_ROOT}")
    print(f"output : {C.OUTPUT_ROOT}")
    print(f"thresholds: {DEFAULT_THRESHOLDS.fingerprint()}")

    print("[1/4] snapshotting source tree …")
    before = I.snapshot()

    pilot = C.load_pilot()
    print(f"[2/4] segmenting {len(pilot)} pilot files …")
    segs: list[dict] = []
    for e in pilot:
        rel = e["relative_path"]
        doc = fitz.open(C.physical_path(rel, C.REPO_ROOT))
        try:
            for i in range(doc.page_count):
                b = Budget(limits)
                seg = segment_page(doc, doc[i], i, rel, b)
                if not args.no_images:
                    seg["overlays"] = render_overlays(doc, doc[i], i, rel, seg, b)
                    seg["crops"] = render_crops(doc, doc[i], i, rel, seg, b)
                segs.append(seg)
                _write_json(C.OUT_UNITS / f"{Path(rel).stem}-p{i}.units.json", seg)
                write_review(build_review(seg))
                st = seg["segmentation"]
                print(f"      {Path(rel).name[:32]:34} p{i} "
                      f"units={len(seg['candidates']):3} "
                      f"ws={len(seg['workspace_candidates']):2} "
                      f"{st['status']:20} {','.join(st['failure_indicators']) or '-'}")
        finally:
            doc.close()

    print("[3/4] reconciling …")
    recon = reconcile(segs)
    _write_json(C.OUT_REPORTS / "b2_reconciliation.json", recon)

    print("[4/4] verifying integrity …")
    after = I.compare(before, I.snapshot())
    ok = after["unchanged"] and out_check["ok"]

    if args.milestone:
        docs = C.DOCS_ROOT
        C.assert_output_safe(docs)
        docs.mkdir(parents=True, exist_ok=True)
        light = {k: v for k, v in recon.items() if k != "per_page"}
        light["per_page"] = recon["per_page"]     # small: 15 rows
        _write_json(docs / "b2_summary.json", light)
        print(f"      milestone docs → {docs}")

    print()
    print(f"files/pages              : {recon['files']}/{recon['pages']}")
    print(f"candidates               : {recon['candidates_total']}")
    print(f"workspace candidates     : {recon['workspace_candidates_total']}")
    print(f"by type                  : {recon['candidates_by_type']}")
    print(f"status                   : {recon['segmentation_status_totals']}")
    print(f"MANUAL_REQUIRED files    : {recon['files_manual_required'] or 'none'}")
    print(f"source tree unchanged    : {after['unchanged']}")
    print(f"no output under source   : {out_check['ok']}")
    print(f"elapsed {time.time() - t0:.1f}s")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
