"""Many-to-many association of structural findings to B2 candidates (DIP-0B3).

The page-level structural graph is authoritative. B2 candidates are *attachment
targets*, never prerequisites: a likely dieline may span several candidates,
coexist with surface artwork, cross candidate boundaries, or sit on a page whose
content segmentation collapsed. A finding may therefore attach to zero, one or
many candidates — and a candidate may carry many findings.
"""
from __future__ import annotations

from .cluster import containment, iou

MIN_OVERLAP = 0.05          # a finding must genuinely sit inside a candidate


def _intersects(a, b) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def associate(finding_bbox, candidates: list[dict]) -> list[dict]:
    """Candidates a finding overlaps, with the overlap measured both ways."""
    out = []
    for c in candidates:
        cb = c["bbox_pt"]
        if not _intersects(finding_bbox, cb):
            continue
        inside = containment(finding_bbox, cb)
        covers = containment(cb, finding_bbox)
        if max(inside, covers) < MIN_OVERLAP:
            continue
        out.append({
            "unit_id": c["unit_id"],
            "candidate_type": c["candidate_type"]["value"],
            "finding_inside_candidate": round(inside, 3),
            "candidate_inside_finding": round(covers, 3),
            "iou": round(iou(finding_bbox, cb), 3),
        })
    return sorted(out, key=lambda r: (-r["iou"], r["unit_id"]))


def associate_all(dieline: dict | None, graph: dict,
                  candidates: list[dict]) -> dict:
    """Attach the dieline region, panels and technical marks to candidates."""
    region_assoc = associate(dieline["bbox_pt"], candidates) if (
        dieline and dieline.get("qualifies")) else []

    panel_assoc = []
    for p in graph["panels"]:
        hits = associate(p["bbox_pt"], candidates)
        panel_assoc.append({"panel_index": p["panel_index"],
                            "candidates": [h["unit_id"] for h in hits]})

    mark_assoc = {}
    for key in ("registration_mark_candidates", "crop_mark_candidates",
                "dimension_mark_candidates"):
        rows = []
        for m in graph[key]:
            hits = associate(m["bbox_pt"], candidates)
            rows.append({"path_index": m["path_index"],
                         "candidates": [h["unit_id"] for h in hits]})
        mark_assoc[key] = rows

    spanning = len(region_assoc) > 1
    return {
        "dieline_region_candidates": region_assoc,
        "dieline_spans_multiple_candidates": spanning,
        "dieline_candidate_count": len(region_assoc),
        "panel_associations": panel_assoc,
        "panels_attached_to_zero_candidates": sum(
            1 for p in panel_assoc if not p["candidates"]),
        "mark_associations": mark_assoc,
        "policy": ("the page-level structural graph is authoritative; candidates "
                   "are attachment targets, and a finding may attach to zero, one "
                   "or many of them"),
    }
