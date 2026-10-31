"""DIP-0B3 runner: `python -m tools.dip0b.run_b3 [--milestone] [--no-images]`.

Page-level structural analysis first; B2 candidates are attachment targets.
Read-only over the 14 HISTORICAL_DESIGN pilot files.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

from tools.dip0 import integrity as I
from tools.dip0.provenance import human_block
from tools.dip0.report import json_default

from . import config as C
from .associate import associate_all
from .boxes import build_boxes
from .cluster import clip_rect
from .contentstream import analyse_page
from .dieline import (
    ALGORITHM_VERSION,
    B4_HANDOFF_NOTES,
    BORDERLINE,
    DEFAULT_DIELINE_CONFIG,
    LIKELY_DIELINE,
    OFF_CANVAS_TECHNICAL,
    OUTCOMES,
    REJECTED,
    build_dieline_candidate,
    classify_lines,
)
from .limits import Budget
from .regions import segment_page
from .structure import build_graph, extract_segments

OUT_STRUCTURE = C.OUTPUT_ROOT / "structure"
OUT_TECH_OVERLAYS = C.OUTPUT_ROOT / "technical_overlays"
OUT_TECH_REVIEW = C.OUTPUT_ROOT / "dieline_review"

DIELINE = (200, 40, 40)
BORDERLINE_COLOR = (230, 150, 20)
PANEL = (40, 120, 200)
MARK = (230, 140, 20)


def _write_json(path: Path, obj) -> Path:
    C.assert_output_safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False,
                               default=json_default), encoding="utf-8")
    return path


def _load_candidates(rel: str, page: int, doc, budget) -> list[dict]:
    """B2 units if present, else recompute (B3 must work standalone)."""
    p = C.OUT_UNITS / f"{Path(rel).stem}-p{page}.units.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))["candidates"]
    return segment_page(doc, doc[page], page, rel, budget)["candidates"]


def _marks_by_path(graph: dict) -> dict[int, str]:
    m = {}
    for key, cls in (("registration_mark_candidates", "REGISTRATION_MARK_CANDIDATE"),
                     ("crop_mark_candidates", "CROP_MARK_CANDIDATE"),
                     ("dimension_mark_candidates", "DIMENSION_MARK_CANDIDATE")):
        for r in graph[key]:
            m[r["path_index"]] = cls
    return m


def _workspace_technical(drawings, surface, page, stem) -> list[dict]:
    """Off-canvas structural geometry: spare dielines, registration, crop marks.

    Excluded from Historical Design Memory by default; human confirmation required.
    """
    off = [d for d in drawings if clip_rect(tuple(fitz.Rect(d["rect"])), surface) is None]
    if not off:
        return []
    segs = extract_segments(off)
    if not segs:
        return []
    g = build_graph(off, surface)
    xs = [c for s in segs for c in (s.x0, s.x1)]
    ys = [c for s in segs for c in (s.y0, s.y1)]
    return [{
        "candidate_id": f"{stem}-p{page}-oct00",
        "type": OFF_CANVAS_TECHNICAL,
        "bbox_pt": [round(min(xs), 2), round(min(ys), 2),
                    round(max(xs), 2), round(max(ys), 2)],
        "structural_paths": g["structural_paths"],
        "segments": g["segments"],
        "closed_panels": g["panel_count"],
        "dashed_segments": g["dashed_segments"],
        "registration_mark_candidates": len(g["registration_mark_candidates"]),
        "crop_mark_candidates": len(g["crop_mark_candidates"]),
        "dimension_mark_candidates": len(g["dimension_mark_candidates"]),
        "include_in_historical_memory": None,     # never auto-included
        "human_confirmed": human_block(),
        "policy": ("off-canvas technical material is excluded from Historical "
                   "Design Memory by default and requires human confirmation"),
    }]


def _overlay(doc, page, page_index, rel, graph, dl, budget) -> dict | None:
    OUT_TECH_OVERLAYS.mkdir(parents=True, exist_ok=True)
    C.assert_output_safe(OUT_TECH_OVERLAYS)
    surface = tuple(build_boxes(page, doc.xref_object(page.xref, compressed=False))
                    ["design_surface_pt"])
    clip = fitz.Rect(*surface) & page.rect
    if clip.is_empty:
        return None
    z = budget.render_zoom(clip.width, clip.height)
    pix = page.get_pixmap(matrix=fitz.Matrix(z, z), clip=clip, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    d = ImageDraw.Draw(img)

    def box(rect, color, label, w=2):
        x0 = (rect[0] - clip.x0) * z
        y0 = (rect[1] - clip.y0) * z
        x1 = (rect[2] - clip.x0) * z
        y1 = (rect[3] - clip.y0) * z
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        d.rectangle([x0, y0, x1, y1], outline=color, width=w)
        if label:
            ty1 = y0 if y0 - 14 >= 0 else min(y1, y0 + 14)
            d.rectangle([x0, ty1 - 14, x0 + 7 * len(label) + 6, ty1], fill=color)
            d.text((x0 + 3, ty1 - 13), label, fill=(255, 255, 255))

    for i, p in enumerate(graph["panels"][:120]):
        box(p["bbox_pt"], PANEL, f"p{i}" if i < 30 else "", w=1)
    for key, tag in (("registration_mark_candidates", "reg"),
                     ("crop_mark_candidates", "crop"),
                     ("dimension_mark_candidates", "dim")):
        for m in graph[key][:40]:
            box(m["bbox_pt"], MARK, tag, w=2)
    if dl and dl.get("bbox_pt") and dl["outcome"] != "REJECTED_NO_DIELINE_EVIDENCE":
        colour = DIELINE if dl["qualifies"] else BORDERLINE_COLOR
        box(dl["bbox_pt"], colour, dl["outcome"], w=4)

    p = OUT_TECH_OVERLAYS / f"{Path(rel).stem}-p{page_index}.technical.png"
    C.assert_output_safe(p)
    img.save(p)
    return {"path": C.relpath(p), "bytes": p.stat().st_size}


def _review(rel, page, dl, graph, lines, assoc, workspace) -> dict:
    return {
        "review_version": "b3-review-1",
        "file": rel, "page": page,
        "reviewer": None, "reviewed_at": None,
        "machine": {
            "outcome": dl["outcome"],
            "likely_dieline": dl["qualifies"],
            "score": (dl["evidence"]["score"] if dl else 0.0),
            "confidence": (dl["evidence"]["confidence"] if dl else 0.0),
            "config_fingerprint": (dl["evidence"]["config_fingerprint"] if dl else None),
            "qualifying_route": (dl["evidence"].get("qualifying_route") if dl else None),
            "positive_evidence": (dl["evidence"]["positive_evidence"] if dl else []),
            "contradictory_evidence": (dl["evidence"]["contradictory_evidence"] if dl else []),
            "missing_evidence": (dl["evidence"]["missing_evidence"] if dl else []),
            "supporting_evidence_only": (dl["evidence"]["supporting_evidence_only"] if dl else []),
            "line_class_counts": lines["counts"],
            "associated_candidates": [a["unit_id"] for a in
                                      assoc["dieline_region_candidates"]],
            "spans_multiple_candidates": assoc["dieline_spans_multiple_candidates"],
        },
        "human": {
            "confirmed_outcome": None,       # LIKELY / BORDERLINE / REJECTED
            "is_dieline": None,
            "confirmed_line_classes": None,
            "registration_marks_confirmed": None,
            "include_workspace_technical": None,
            "disposition": "pending",
            "correction_reason": None,
            "notes": "",
        },
        "workspace_technical": workspace,
        "policy": ("machine fields are immutable; every result is a candidate "
                   "until human-confirmed; no geometry is exported in a "
                   "production-reusable format"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dip0b3")
    ap.add_argument("--milestone", action="store_true")
    ap.add_argument("--no-images", action="store_true")
    args = ap.parse_args(argv)

    t0 = time.time()
    C.ensure_output_dirs()
    for d in (OUT_STRUCTURE, OUT_TECH_OVERLAYS, OUT_TECH_REVIEW):
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
    print(f"[2/4] analysing structure on {len(pilot)} files …")
    records: list[dict] = []
    for e in pilot:
        rel = e["relative_path"]
        stem = Path(rel).stem
        doc = fitz.open(C.physical_path(rel, C.REPO_ROOT))
        try:
            for i in range(doc.page_count):
                b = Budget(C.DEFAULT_LIMITS)
                page = doc[i]
                dr = [x for x in page.get_drawings(extended=True)
                      if x["type"] in ("f", "s", "fs")]
                surface = tuple(build_boxes(
                    page, doc.xref_object(page.xref, compressed=False))
                    ["design_surface_pt"])

                graph = build_graph(dr, surface)
                cs = analyse_page(doc, page, len(dr))
                dl = build_dieline_candidate(graph, surface, cs, stem, i)

                shared_paths = {p for e2 in graph["shared_edges"]
                                for p in (e2["path_a"], e2["path_b"])}
                # Conservative: only a LIKELY page yields cut/fold/crease classes.
                # A BORDERLINE page keeps its strokes STRUCTURAL_UNRESOLVED.
                lines = classify_lines(
                    graph, _marks_by_path(graph),
                    dl["outcome"] == LIKELY_DIELINE,
                    graph.get("outer_path_index"), shared_paths)

                cands = _load_candidates(rel, i, doc, b)
                assoc = associate_all(dl if dl["qualifies"] else None,
                                      graph, cands)
                workspace = _workspace_technical(dr, surface, i, stem)
                overlay = (None if args.no_images
                           else _overlay(doc, page, i, rel, graph, dl, b))

                graph_out = {k: v for k, v in graph.items() if k != "_paths"}
                rec = {
                    "file": rel, "page": i,
                    "artbox_pt": [round(v, 2) for v in surface],
                    "algorithm_version": ALGORITHM_VERSION,
                    "structural_graph": graph_out,
                    "content_stream": {k: v for k, v in cs.items()
                                       if k != "path_index_map"},
                    "likely_dieline": dl,
                    "line_classes": lines["counts"],
                    "line_class_note": lines["note"],
                    "associations": assoc,
                    "workspace_technical": workspace,
                    "overlay": overlay,
                    "limits": b.to_dict(),
                }
                records.append(rec)
                _write_json(OUT_STRUCTURE / f"{stem}-p{i}.structure.json", rec)
                _write_json(OUT_TECH_REVIEW / f"{stem}-p{i}.dieline_review.json",
                            _review(rel, i, dl, graph, lines, assoc, workspace))

                q = {LIKELY_DIELINE: "LIKELY    ", BORDERLINE: "BORDERLINE",
                     REJECTED: "rejected  "}[dl["outcome"]]
                print(f"      {Path(rel).name[:30]:32} p{i} {q} "
                      f"panels={graph['panel_count']:3} ortho={graph['orthogonal_panel_count']:3} "
                      f"edges={graph['shared_edge_count']:3} dashed={graph['dashed_segments']:3} "
                      f"/All_ops={cs['registration_painting_ops']:4} "
                      f"assoc={assoc['dieline_candidate_count']:2}"
                      f"{' SPAN' if assoc['dieline_spans_multiple_candidates'] else ''}")
        finally:
            doc.close()

    print("[3/4] reconciling …")
    lines_total: Counter = Counter()
    outcomes: Counter = Counter()
    for r in records:
        lines_total.update(r["line_classes"])
        outcomes[r["likely_dieline"]["outcome"]] += 1

    spanning = [r for r in records
                if r["associations"]["dieline_spans_multiple_candidates"]]
    all_files = {Path(r["file"]).name for r in records
                 if r["content_stream"]["registration_ink_used_on_page"]}
    direct = {Path(r["file"]).name for r in records
              if r["content_stream"]["path_association"] == "DIRECT"}
    ws = [w for r in records for w in r["workspace_technical"]]

    def rows(outcome):
        return [{"file": Path(r["file"]).name, "page": r["page"],
                 "score": r["likely_dieline"]["evidence"]["score"],
                 "confidence": r["likely_dieline"]["evidence"]["confidence"],
                 "route": r["likely_dieline"]["evidence"]["qualifying_route"],
                 "contradictory": r["likely_dieline"]["evidence"]["contradictory_evidence"][:2],
                 "missing": r["likely_dieline"]["evidence"]["missing_evidence"][:2]}
                for r in records if r["likely_dieline"]["outcome"] == outcome]

    recon = {
        "files": len({r["file"] for r in records}),
        "pages": len(records),
        "outcome_totals": {o: outcomes.get(o, 0) for o in OUTCOMES},
        "config_fingerprint": DEFAULT_DIELINE_CONFIG.fingerprint(),
        "config": DEFAULT_DIELINE_CONFIG.__dict__ if hasattr(
            DEFAULT_DIELINE_CONFIG, "__dict__") else {},
        "likely_dieline_pages": rows(LIKELY_DIELINE),
        "borderline_pages": rows(BORDERLINE),
        "rejected_pages": rows(REJECTED),
        "line_class_totals": dict(lines_total),
        "files_with_registration_ink": sorted(all_files),
        "files_with_direct_path_association": sorted(direct),
        "path_association_status": ("DIRECT where proven; UNAVAILABLE otherwise — "
                                    "no thin stroke inherits /All certainty"),
        "dielines_spanning_multiple_candidates": len(spanning),
        "workspace_technical_candidates": len(ws),
        "workspace_auto_included": sum(
            1 for w in ws if w["include_in_historical_memory"] is not None),
        "b4_handoff_notes": B4_HANDOFF_NOTES,
    }
    _write_json(C.OUT_REPORTS / "b3_reconciliation.json", recon)

    print("[4/4] verifying integrity …")
    after = I.compare(before, I.snapshot())
    ok = after["unchanged"] and out_check["ok"]

    if args.milestone:
        C.DOCS_ROOT.mkdir(parents=True, exist_ok=True)
        _write_json(C.DOCS_ROOT / "b3_summary.json", recon)
        print(f"      milestone docs → {C.DOCS_ROOT}")

    print()
    print(f"files/pages                    : {recon['files']}/{recon['pages']}")
    for o in OUTCOMES:
        print(f"  {o:32} {recon['outcome_totals'][o]}")
    print(f"config fingerprint             : {recon['config_fingerprint']}")
    print(f"line classes                   : {recon['line_class_totals']}")
    print(f"files with registration ink    : {len(recon['files_with_registration_ink'])}")
    print(f"files w/ DIRECT path assoc     : {len(recon['files_with_direct_path_association'])}")
    print(f"dielines spanning >1 candidate : {recon['dielines_spanning_multiple_candidates']}")
    print(f"workspace technical candidates : {recon['workspace_technical_candidates']} "
          f"(auto-included: {recon['workspace_auto_included']})")
    print(f"dimension marks                : {B4_HANDOFF_NOTES['dimension_marks']}")
    print(f"source tree unchanged          : {after['unchanged']}")
    print(f"no output under source         : {out_check['ok']}")
    print(f"elapsed {time.time() - t0:.1f}s")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
