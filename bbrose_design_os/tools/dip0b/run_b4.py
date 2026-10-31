"""DIP-0B4 runner: per-unit colour, artwork descriptors and Level-A typography.

Uses DIP-0B3 findings as *exclusion and context* evidence while preserving
uncertainty: a colour leaves the artwork palette only when B3 classified that
specific path as a technical line — never because the stroke is thin.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import fitz

from tools.dip0 import integrity as I
from tools.dip0.provenance import human_block
from tools.dip0.report import json_default

from . import config as C
from .artwork import describe_unit, logo_placement_candidate
from .boxes import build_boxes
from .cluster import area as _area
from .cluster import build_grid, cluster_rects
from .color import BUCKETS, bucket_path, build_spot_ramp, summarise_palette
from .contentstream import analyse_page
from .dieline import (
    B4_HANDOFF_NOTES,
    DEFAULT_DIELINE_CONFIG,
    LIKELY_DIELINE,
    build_dieline_candidate,
    classify_lines,
)
from .inspect import scan_xrefs
from .limits import Budget
from .regions import DEFAULT_THRESHOLDS, _paths, _rasters, segment_page
from .separation import build_separation_table
from .structure import build_graph
from .typography import analyse_unit

ALGORITHM_VERSION = "b4-0.1.0"
OUT_UNITS_B4 = C.OUTPUT_ROOT / "unit_analysis"
OUT_REVIEW_B4 = C.OUTPUT_ROOT / "unit_review"

BACKGROUND_COVERAGE = 0.6      # a fill covering this much of the surface is ground


def _write_json(path: Path, obj) -> Path:
    C.assert_output_safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False,
                               default=json_default), encoding="utf-8")
    return path


def _marks_by_path(graph):
    m = {}
    for key, cls in (("registration_mark_candidates", "REGISTRATION_MARK_CANDIDATE"),
                     ("crop_mark_candidates", "CROP_MARK_CANDIDATE"),
                     ("dimension_mark_candidates", "DIMENSION_MARK_CANDIDATE")):
        for r in graph[key]:
            m[r["path_index"]] = cls
    return m


def _members_by_unit(paths, units):
    """Assign each path to the smallest unit whose bbox contains its centre."""
    order = sorted(range(len(units)), key=lambda i: _area(tuple(units[i]["bbox_pt"])))
    out: dict[str, list] = {u["unit_id"]: [] for u in units}
    for p in paths:
        r = p["rect"]
        cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        for i in order:
            b = units[i]["bbox_pt"]
            if b[0] <= cx <= b[2] and b[1] <= cy <= b[3]:
                out[units[i]["unit_id"]].append(p)
                break
    return out


def analyse_page_units(doc, page, page_index: int, rel: str, budget: Budget) -> dict:
    stem = Path(rel).stem
    raw = doc.xref_object(page.xref, compressed=False)
    boxes = build_boxes(page, raw)
    surface = tuple(boxes["design_surface_pt"])
    surface_area = max(_area(surface), 1e-6)

    seg = segment_page(doc, page, page_index, rel, budget)
    units = seg["candidates"]

    drawings = [x for x in page.get_drawings(extended=True)
                if x["type"] in ("f", "s", "fs")]
    graph = build_graph(drawings, surface)
    cs = analyse_page(doc, page, len(drawings))
    dl = build_dieline_candidate(graph, surface, cs, stem, page_index,
                                 DEFAULT_DIELINE_CONFIG)
    shared = {p for e in graph["shared_edges"] for p in (e["path_a"], e["path_b"])}
    lines = classify_lines(graph, _marks_by_path(graph),
                           dl["outcome"] == LIKELY_DIELINE,
                           graph.get("outer_path_index"), shared)
    # Only *technical* classes exclude a colour. STRUCTURAL_UNRESOLVED does not:
    # a thin stroke is not technical ink.
    technical = {i: c for i, c in lines["per_path"].items()
                 if c != "STRUCTURAL_UNRESOLVED"}

    scan = scan_xrefs(doc, budget)
    seps = build_separation_table(doc, budget, scan["raw_separations"], scan["devicen"])
    spots = build_spot_ramp(seps)
    reg_present = cs["registration_ink_used_on_page"]

    paths = _paths(page, DEFAULT_THRESHOLDS, surface_area)
    for i, p in enumerate(paths):
        p["path_index"] = i
    rasters = _rasters(page)

    palette_units = {u["unit_id"] for u in units
                     if u["candidate_type"]["value"] == "COLOR_PALETTE_STRIP"}
    members = _members_by_unit(paths, units)

    buckets: dict[str, list] = {b: [] for b in BUCKETS}
    ambiguous = 0
    for u in units:
        for p in members[u["unit_id"]]:
            rgb = p.get("fill") or p.get("stroke")
            if rgb is None:
                continue
            is_bg = (p["background"]
                     and _area(p["rect"]) >= BACKGROUND_COVERAGE * surface_area)
            b, ev = bucket_path(
                p, technical_class=technical.get(p["path_index"]),
                in_palette_strip=u["unit_id"] in palette_units,
                is_canvas_background=is_bg,
                registration_present=reg_present,
                path_association=cs["path_association"], spots=spots)
            entry = {"rgb": rgb, "area": p["area"], "unit_id": u["unit_id"],
                     "path_index": p["path_index"], "bucket": b, **ev}
            if ev.get("ambiguity") or (ev.get("spot_match") or {}).get("ambiguous"):
                ambiguous += 1
            buckets[b].append(entry)

    # rasters live in their own bucket, never mixed with vector brand colour
    for r in rasters:
        buckets["embedded_raster"].append(
            {"rgb": None, "area": _area(r["rect"]), "unit_id": None,
             "width_px": r["width_px"], "height_px": r["height_px"],
             "colorspace": r["colorspace"],
             "reason": "embedded image; raster colour is not vector brand colour"})

    # --- per-unit records ---------------------------------------------------
    unit_records = []
    grid = build_grid(surface, budget.limits.max_render_px,
                      budget.limits.max_mask_pixels)
    for u in units:
        mem = members[u["unit_id"]]
        art = [e for e in buckets["artwork"] if e["unit_id"] == u["unit_id"]]
        tech = [e for e in buckets["dieline_technical"] if e["unit_id"] == u["unit_id"]]
        unresolved = [e for e in buckets["unresolved_or_ambiguous"]
                      if e["unit_id"] == u["unit_id"]]
        u_rasters = [r for r in rasters
                     if u["bbox_pt"][0] <= (r["rect"][0] + r["rect"][2]) / 2 <= u["bbox_pt"][2]
                     and u["bbox_pt"][1] <= (r["rect"][1] + r["rect"][3]) / 2 <= u["bbox_pt"][3]]

        glyphs = [m for m in mem if m.get("glyph")]
        regions = []
        if glyphs:
            groups = cluster_rects([g["rect"] for g in glyphs],
                                   DEFAULT_THRESHOLDS.content_gap_pt, grid)
            regions = [[glyphs[i] for i in g] for g in groups if len(g) >= 2]

        unit_records.append({
            "unit_id": u["unit_id"],
            "candidate_type": u["candidate_type"]["value"],
            "bbox_pt": u["bbox_pt"],
            "palette": {
                "artwork": summarise_palette(art),
                "technical_excluded": len(tech),
                "unresolved_or_ambiguous": len(unresolved),
            },
            "descriptors": describe_unit(page, u, mem, u_rasters),
            "logo_placement_candidate": logo_placement_candidate(u, mem, u_rasters),
            "typography": analyse_unit(u, mem, regions),
            "human_confirmed": human_block(),
        })

    return {
        "file": rel, "page": page_index,
        "algorithm_version": ALGORITHM_VERSION,
        "artbox_pt": [round(v, 2) for v in surface],
        "dieline_outcome": dl["outcome"],
        "registration_ink_present": reg_present,
        "path_association": cs["path_association"],
        "separation_inks": seps["names"],
        "bucket_totals": {b: len(v) for b, v in buckets.items()},
        "bucket_area_pt2": {b: round(sum(e["area"] for e in v), 2)
                            for b, v in buckets.items()},
        "ambiguous_colour_entries": ambiguous,
        "technical_paths_excluded": len(technical),
        "structural_unresolved_not_excluded": sum(
            1 for c in lines["per_path"].values() if c == "STRUCTURAL_UNRESOLVED"),
        "units": unit_records,
        "b4_handoff_notes": B4_HANDOFF_NOTES,
        "limits": budget.to_dict(),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dip0b4")
    ap.add_argument("--milestone", action="store_true")
    args = ap.parse_args(argv)

    t0 = time.time()
    C.ensure_output_dirs()
    for d in (OUT_UNITS_B4, OUT_REVIEW_B4):
        C.assert_output_safe(d)
        d.mkdir(parents=True, exist_ok=True)

    out_check = I.no_output_under_source()
    if not out_check["ok"]:
        print("FATAL: output root is inside the read-only source root")
        return 2

    print(f"source : {C.SOURCE_ROOT}\noutput : {C.OUTPUT_ROOT}")
    print(f"algorithm: {ALGORITHM_VERSION}")
    print("[1/4] snapshotting source tree …")
    before = I.snapshot()

    pilot = C.load_pilot()
    print(f"[2/4] analysing units on {len(pilot)} files …")
    records = []
    for e in pilot:
        rel = e["relative_path"]
        doc = fitz.open(C.physical_path(rel, C.REPO_ROOT))
        try:
            for i in range(doc.page_count):
                b = Budget(C.DEFAULT_LIMITS)
                rec = analyse_page_units(doc, doc[i], i, rel, b)
                records.append(rec)
                _write_json(OUT_UNITS_B4 / f"{Path(rel).stem}-p{i}.units_b4.json", rec)
                bt = rec["bucket_totals"]
                print(f"      {Path(rel).name[:30]:32} p{i} units={len(rec['units']):3} "
                      f"art={bt['artwork']:5} tech={bt['dieline_technical']:3} "
                      f"unres={bt['unresolved_or_ambiguous']:4} "
                      f"swatch={bt['swatch_reference']:3} bg={bt['canvas_background']:2} "
                      f"amb={rec['ambiguous_colour_entries']:5}")
        finally:
            doc.close()

    print("[3/4] reconciling …")
    bt: Counter = Counter()
    ba: Counter = Counter()
    types: Counter = Counter()
    typ_candidates = 0
    review_units = []
    for r in records:
        for k, v in r["bucket_totals"].items():
            bt[k] += v
        for k, v in r["bucket_area_pt2"].items():
            ba[k] += v
        for u in r["units"]:
            types[u["candidate_type"]] += 1
            typ_candidates += u["typography"]["candidate_count"]
            if (u["palette"]["unresolved_or_ambiguous"]
                    or u["palette"]["artwork"]["distinct_colours"] == 0):
                review_units.append(u["unit_id"])

    recon = {
        "files": len({r["file"] for r in records}),
        "pages": len(records),
        "units": sum(len(r["units"]) for r in records),
        "bucket_totals": dict(bt),
        "bucket_area_pt2": {k: round(v, 2) for k, v in ba.items()},
        "ambiguous_colour_entries": sum(r["ambiguous_colour_entries"] for r in records),
        "technical_paths_excluded": sum(r["technical_paths_excluded"] for r in records),
        "structural_unresolved_not_excluded": sum(
            r["structural_unresolved_not_excluded"] for r in records),
        "unit_types": dict(types.most_common()),
        "typography_candidates": typ_candidates,
        "units_requiring_review": len(review_units),
        "pages_with_registration_ink": sum(1 for r in records
                                           if r["registration_ink_present"]),
        "path_association_status": records[0]["path_association"] if records else None,
        "dieline_outcomes": dict(Counter(r["dieline_outcome"] for r in records)),
        "level_b": "unavailable — no OCR, no font-family inference",
        "b4_handoff_notes": B4_HANDOFF_NOTES,
    }
    _write_json(C.OUT_REPORTS / "b4_reconciliation.json", recon)

    print("[4/4] verifying integrity …")
    after = I.compare(before, I.snapshot())
    ok = after["unchanged"] and out_check["ok"]
    if args.milestone:
        C.DOCS_ROOT.mkdir(parents=True, exist_ok=True)
        _write_json(C.DOCS_ROOT / "b4_summary.json", recon)
        print(f"      milestone docs → {C.DOCS_ROOT}")

    print()
    print(f"files/pages/units          : {recon['files']}/{recon['pages']}/{recon['units']}")
    print(f"bucket totals (paths)      : {recon['bucket_totals']}")
    print(f"ambiguous colour entries   : {recon['ambiguous_colour_entries']}")
    print(f"technical paths excluded   : {recon['technical_paths_excluded']}")
    print(f"structural-unresolved kept : {recon['structural_unresolved_not_excluded']}")
    print(f"typography candidates      : {recon['typography_candidates']}")
    print(f"units requiring review     : {recon['units_requiring_review']}")
    print(f"dieline outcomes           : {recon['dieline_outcomes']}")
    print(f"source tree unchanged      : {after['unchanged']}")
    print(f"no output under source     : {out_check['ok']}")
    print(f"elapsed {time.time() - t0:.1f}s")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
