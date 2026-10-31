"""DIP-0B5 runner: human-review manifest, consolidated report, DIP-0C/1 recs.

Consolidation only — no retrieval, embeddings, recipe generation or pipeline
integration. Recomputes B1–B4 per page (self-contained) and joins the findings
into a unit-centred manifest plus the milestone documents.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

import fitz

from tools.dip0 import integrity as I
from tools.dip0.report import json_default

from . import config as C
from . import manifest as M
from . import reports_b5 as RB
from .artwork import describe_unit, logo_placement_candidate
from .boxes import build_boxes
from .cluster import area as _area
from .cluster import build_grid, cluster_rects, containment
from .color import build_spot_ramp, is_near_black, summarise_palette
from .contentstream import analyse_page
from .dieline import (
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

ALGORITHM_VERSION = "b5-0.1.0"
OUT_MANIFEST = C.OUTPUT_ROOT / "manifest"


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


def _colour_classes(art_palette: dict, members, technical) -> dict:
    """Two granularities, kept distinct:

    * palette-level classes (over the unit's dominant + supporting colours) —
      these reconcile with B4's accepted 125 matched / 20 ambiguous / 316
      unattributed.
    * path-level flagged near-black — the true ambiguity scale (B4: ~24k),
      which the small palette view would otherwise hide (decision 4).
    """
    named = ambiguous = unattributed = 0
    fams: Counter = Counter()
    for c in art_palette["dominant"] + art_palette["supporting"]:
        sm = c.get("spot_match") or {}
        if sm.get("matched"):
            named += 1
        elif sm.get("ambiguous"):
            ambiguous += 1
        elif sm.get("reason") and "paper" not in sm.get("reason", ""):
            unattributed += 1
        if is_near_black([v / 255 for v in c["srgb_255"]]):
            fams["near_black"] += 1

    # path-level flagged near-black artwork (kept in artwork, flagged ambiguous)
    flagged_black = 0
    for p in members:
        if p["path_index"] in technical:
            continue
        rgb = p.get("fill") or p.get("stroke")
        if rgb and is_near_black(rgb) and p["type"] in ("f", "fs"):
            flagged_black += 1
    return {
        "named_ink_matched": named,
        "named_ink_ambiguous": ambiguous,
        "unattributed": unattributed,
        "flagged_black_paths": flagged_black,
        "ambiguous_colours": ambiguous,
        "ambiguous_paths": flagged_black,
        "dominant_ambiguous_families": [k for k, _ in fams.most_common(3)],
    }


def enriched_units(doc, page, page_index: int, rel: str, budget: Budget) -> list[dict]:
    stem = Path(rel).stem
    raw = doc.xref_object(page.xref, compressed=False)
    surface = tuple(build_boxes(page, raw)["design_surface_pt"])
    surface_area = max(_area(surface), 1e-6)

    seg = segment_page(doc, page, page_index, rel, budget)
    seg_status = seg["segmentation"]["status"]
    candidates = seg["candidates"]
    workspace = seg["workspace_candidates"]

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
    technical = {i: c for i, c in lines["per_path"].items()
                 if c != "STRUCTURAL_UNRESOLVED"}
    dl_bbox = dl.get("bbox_pt")

    scan = scan_xrefs(doc, budget)
    seps = build_separation_table(doc, budget, scan["raw_separations"], scan["devicen"])
    spots = build_spot_ramp(seps)
    paths = _paths(page, DEFAULT_THRESHOLDS, surface_area)
    for i, p in enumerate(paths):
        p["path_index"] = i
    rasters = _rasters(page)

    order = sorted(range(len(candidates)),
                   key=lambda i: _area(tuple(candidates[i]["bbox_pt"])))
    members: dict[str, list] = {u["unit_id"]: [] for u in candidates}
    for p in paths:
        r = p["rect"]
        cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        for i in order:
            b = candidates[i]["bbox_pt"]
            if b[0] <= cx <= b[2] and b[1] <= cy <= b[3]:
                members[candidates[i]["unit_id"]].append(p)
                break

    grid = build_grid(surface, budget.limits.max_render_px,
                      budget.limits.max_mask_pixels)
    out = []
    for u in candidates + workspace:
        uid = u["unit_id"]
        off = u.get("off_canvas", False)
        mem = members.get(uid, [])
        u_rasters = [r for r in rasters
                     if u["bbox_pt"][0] <= (r["rect"][0] + r["rect"][2]) / 2 <= u["bbox_pt"][2]
                     and u["bbox_pt"][1] <= (r["rect"][1] + r["rect"][3]) / 2 <= u["bbox_pt"][3]]
        art = [{"rgb": p.get("fill") or p.get("stroke"), "area": p["area"]}
               for p in mem
               if (p.get("fill") or p.get("stroke"))
               and p["path_index"] not in technical]

        glyphs = [m for m in mem if m.get("glyph")]
        regions = []
        if glyphs:
            groups = cluster_rects([g["rect"] for g in glyphs],
                                   DEFAULT_THRESHOLDS.content_gap_pt, grid)
            regions = [[glyphs[i] for i in g] for g in groups if len(g) >= 2]

        art_summary = summarise_palette(art)
        # match spots on the ~6 summarised palette colours only (cheap, and the
        # methodology B4's accepted 125/20/316 figures were computed under)
        from .color import match_spot
        for c in art_summary["dominant"] + art_summary["supporting"]:
            c["spot_match"] = match_spot([v / 255 for v in c["srgb_255"]], spots)
        colour = _colour_classes(art_summary, mem, technical)
        colour["raster_colours"] = len(u_rasters)

        unit = {
            "file": rel, "page": page_index, "unit_id": uid,
            "candidate_type": u["candidate_type"]["value"],
            "bbox_pt": u["bbox_pt"],
            "palette": {"artwork": art_summary,
                        "technical_excluded": sum(1 for p in mem
                                                  if p["path_index"] in technical),
                        "unresolved_or_ambiguous": colour["ambiguous_paths"]},
            "descriptors": describe_unit(page, u, mem, u_rasters),
            "logo_placement_candidate": logo_placement_candidate(u, mem, u_rasters),
            "typography": analyse_unit(u, mem, regions),
            "_colour": colour,
            "_candidate_confidence": u["candidate_type"]["confidence"],
            "_segmentation_status": seg_status,
            "_dieline_outcome": dl["outcome"],
            "_dieline_score": dl["evidence"]["score"],
            "_dieline_overlaps": bool(dl_bbox and containment(u["bbox_pt"], dl_bbox) > 0.3
                                     and dl["qualifies"]),
            "_off_canvas": off,
            "_proposed_for_inclusion": False,
            "_alternate_version": bool(u.get("repeat_evidence")),
            "_vector_count": len(mem),
            "_raster_count": len(u_rasters),
            "_preview_crop": u.get("preview_crop"),
            "_provenance": {"b5_version": ALGORITHM_VERSION,
                            "dieline_config": dl.get("config_fingerprint"),
                            "path_association": cs["path_association"]},
        }
        unit["_typo_band"] = M.typography_density_band(unit)
        unit["_deco_band"] = M.decoration_density_band(unit)
        out.append(unit)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dip0b5")
    ap.add_argument("--milestone", action="store_true")
    args = ap.parse_args(argv)

    t0 = time.time()
    C.ensure_output_dirs()
    C.assert_output_safe(OUT_MANIFEST)
    OUT_MANIFEST.mkdir(parents=True, exist_ok=True)
    out_check = I.no_output_under_source()
    if not out_check["ok"]:
        print("FATAL: output root is inside the read-only source root")
        return 2

    print(f"source : {C.SOURCE_ROOT}\noutput : {C.OUTPUT_ROOT}")
    print("[1/4] snapshotting source tree …")
    before = I.snapshot()

    pilot = C.load_pilot()
    print(f"[2/4] consolidating {len(pilot)} files …")
    units = []
    for e in pilot:
        rel = e["relative_path"]
        doc = fitz.open(C.physical_path(rel, C.REPO_ROOT))
        try:
            for i in range(doc.page_count):
                units.extend(enriched_units(doc, doc[i], i, rel, Budget(C.DEFAULT_LIMITS)))
        finally:
            doc.close()
        print(f"      {Path(rel).name[:30]:32} cumulative units={len(units)}")

    all_rows = []
    for u in units:
        row = M.build_row(u)
        row["_typo_band"] = u["_typo_band"]
        row["_deco_band"] = u["_deco_band"]
        all_rows.append(row)
    # Primary DesignUnitCandidates are the authoritative 173; off-canvas
    # workspace candidates are reviewable but kept in a separate section so the
    # manifest row count reconciles to the accepted primary-unit count.
    rows = [r for r in all_rows if r["primary_or_off_canvas"] == "primary"]
    off_canvas_rows = [r for r in all_rows if r["primary_or_off_canvas"] == "off_canvas"]
    batches = M.build_batches(rows)
    manifest_fp = M.fingerprint(rows)

    print("[3/4] writing manifest + reports …")
    manifest = {"manifest_version": M.MANIFEST_VERSION,
                "algorithm_version": ALGORITHM_VERSION,
                "fingerprint": manifest_fp,
                "unit_count": len(rows), "rows": rows,
                "off_canvas_candidate_count": len(off_canvas_rows),
                "off_canvas_candidates": off_canvas_rows,
                "batches": batches}
    _write_json(OUT_MANIFEST / "review_manifest.json", manifest)
    _write_csv(OUT_MANIFEST / "review_manifest.csv", rows)

    recon = _reconcile(rows, batches, units, off_canvas_rows)
    _write_json(C.OUT_REPORTS / "b5_reconciliation.json", recon)

    docs = RB.generate_all(rows, batches, recon, units)

    print("[4/4] verifying integrity …")
    after = I.compare(before, I.snapshot())
    ok = after["unchanged"] and out_check["ok"]

    if args.milestone:
        RB.write_milestone(docs, rows, batches, recon)
        # a compact sampled manifest is small enough to commit
        _write_json(C.DOCS_ROOT / "review_manifest_sample.json",
                    {"manifest_version": M.MANIFEST_VERSION,
                     "fingerprint": manifest_fp, "unit_count": len(rows),
                     "sample": rows[:8],
                     "batches": batches})
        print(f"      milestone docs → {C.DOCS_ROOT}")

    _print_summary(recon, after, out_check, time.time() - t0)
    return 0 if ok else 1


def _write_csv(path: Path, rows: list[dict]) -> None:
    C.assert_output_safe(path)
    cols = ["file", "page", "unit_id", "candidate_type", "candidate_confidence",
            "segmentation_status", "primary_or_off_canvas", "vector_count",
            "raster_count", "likely_dieline_outcome", "dieline_score",
            "dominant_artwork_colours", "named_ink_matched", "unattributed",
            "flagged_near_black_artwork", "technical_excluded",
            "typography_candidates", "decoration_density_paths_per_cm2",
            "whitespace_ratio", "symmetry_score",
            "include_recommendation", "review_priority", "review_priority_reasons",
            "reviewer", "product_category", "sku_product_code", "approval_status",
            "include_in_historical_memory", "disposition", "notes"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({
                "file": r["file"], "page": r["page"], "unit_id": r["unit_id"],
                "candidate_type": r["candidate_type"],
                "candidate_confidence": r["candidate_confidence"],
                "segmentation_status": r["segmentation_status"],
                "primary_or_off_canvas": r["primary_or_off_canvas"],
                "vector_count": r["vector_count"], "raster_count": r["raster_count"],
                "likely_dieline_outcome": r["likely_dieline_outcome"],
                "dieline_score": r["dieline_score"],
                "dominant_artwork_colours": ";".join(
                    str(c) for c in r["dominant_artwork_colours"]),
                "named_ink_matched": r["colour_classes"]["named_ink_matched"],
                "unattributed": r["colour_classes"]["present_but_unattributed"],
                "flagged_near_black_artwork": r["flagged_near_black_artwork"],
                "technical_excluded": r["colour_classes"]["technical_colour"],
                "typography_candidates": r["text_like_geometry_summary"]["candidate_count"],
                "decoration_density_paths_per_cm2": r["decoration_density_paths_per_cm2"],
                "whitespace_ratio": r["whitespace_ratio"],
                "symmetry_score": r["symmetry_score"],
                "include_recommendation": r["include_in_historical_memory_recommendation"],
                "review_priority": r["review_priority"],
                "review_priority_reasons": ";".join(r["review_priority_reasons"]),
                "reviewer": "", "product_category": "", "sku_product_code": "",
                "approval_status": "", "include_in_historical_memory": "",
                "disposition": "", "notes": "",
            })


def _reconcile(rows, batches, units, off_canvas_rows) -> dict:
    prio = Counter(r["review_priority"] for r in rows)
    rec = Counter(r["include_in_historical_memory_recommendation"] for r in rows)
    types = Counter(r["candidate_type"] for r in rows)
    flagged_black = sum(r["flagged_near_black_artwork"] for r in rows)
    named = sum(r["colour_classes"]["named_ink_matched"] for r in rows)
    amb = sum(r["colour_classes"]["named_ink_ambiguous"] for r in rows)
    unattr = sum(r["colour_classes"]["present_but_unattributed"] for r in rows)
    return {
        "units": len(rows),
        "off_canvas_candidates": len(off_canvas_rows),
        "b2_primary_candidate_count": len(rows),
        "review_priority_totals": {p: prio.get(p, 0) for p in M.PRIORITIES},
        "recommendation_totals": {r: rec.get(r, 0) for r in M.RECOMMENDATIONS},
        "unit_types": dict(types.most_common()),
        "batch_group_totals": batches["total_groups"],
        "named_ink_matched": named,
        "named_ink_ambiguous": amb,
        "present_but_unattributed": unattr,
        "flagged_near_black_artwork_total": flagged_black,
        "human_review_workload": {
            "HIGH": prio.get("HIGH", 0), "MEDIUM": prio.get("MEDIUM", 0),
            "batchable_groups": batches["total_groups"]},
        "manifest_fingerprint": M.fingerprint(rows),
        "scale_estimate": RB.scale_estimate(rows, units),
    }


def _print_summary(recon, after, out_check, elapsed):
    print()
    print(f"units                    : {recon['units']}")
    print(f"review priority          : {recon['review_priority_totals']}")
    print(f"recommendation           : {recon['recommendation_totals']}")
    print(f"batch groups             : {recon['batch_group_totals']}")
    print(f"named-ink matched        : {recon['named_ink_matched']}")
    print(f"unattributed             : {recon['present_but_unattributed']}")
    print(f"flagged near-black art    : {recon['flagged_near_black_artwork_total']}")
    print(f"source tree unchanged    : {after['unchanged']}")
    print(f"no output under source   : {out_check['ok']}")
    print(f"elapsed {elapsed:.1f}s")


if __name__ == "__main__":
    sys.exit(main())
