"""DIP-0B2 — region clustering and `DesignUnitCandidate` generation.

Layered, deterministic segmentation:

  1. structural-stroke skeleton (thin, no-fill strokes)
  2. background-suppressed content clustering (page-spanning fills removed)
  3. raster candidates
  4. repeat / mirror evidence
  5. merge + containment resolution

The ArtBox is the primary design surface. Geometry fully outside it is clustered
**separately** as `workspace_candidates` — a first-class design-workspace concept,
never auto-included in Historical Design Memory. A straddling object contributes
its *clipped* portion to primary clustering, keeps its original bbox, and is
never duplicated into another candidate's counts.

A file may legitimately yield ONE full-bleed candidate with low confidence and
`MANUAL_REQUIRED`. That is reported honestly, never forced apart.

Every candidate type is machine-inferred until human-confirmed.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz

from tools.dip0.provenance import Inferred, human_block

from . import config as C
from .boxes import build_boxes, pt_to_mm
from .cluster import (
    area,
    build_grid,
    clip_rect,
    cluster_rects,
    containment,
    iou,
    union_bbox,
)
from .limits import Budget

ALGORITHM_VERSION = "b2-0.1.0"
PARSER = f"{C.TOOL_NAME}.regions/{ALGORITHM_VERSION}"

# User-approved candidate taxonomy (2026-07-10). SPEC_TABLE added and
# COLOR_PALETTE_STRIP confirmed after the ES3083 preview showed both.
#
# `DIELINE_CANDIDATE`, never `DIELINE`: B2 only detects a region CONTAINING
# structural signals. Whether that geometry actually forms a dieline is a
# page-level question for DIP-0B3, and a human confirms it either way.
CANDIDATE_TYPES = (
    "DIELINE_CANDIDATE",
    "SURFACE_ARTWORK",
    "PRODUCT_PHOTO",
    "MOCKUP",
    "SPEC_TABLE",
    "TECHNICAL_NOTES",
    "COLOR_PALETTE_STRIP",
    "ALTERNATE_VERSION",
    "LEGAL_TEXT",
    "BARCODE",
    "REFERENCE_MATERIAL",
    "UNKNOWN",
)

SEGMENTATION_STATUS = (
    "AUTO_CONFIDENT", "AUTO_LOW_CONFIDENCE", "MANUAL_REQUIRED", "MANUAL_RESOLVED",
)


@dataclass(frozen=True)
class SegThresholds:
    structural_max_width_pt: float = 1.2
    structural_gap_pt: float = 6.0
    content_gap_pt: float = 10.0        # level 1: glyphs/strokes -> words/marks
    # Level 2 agglomerates level-1 clusters into blocks. A fixed gap cannot
    # serve both a 400 pt synthetic page and a 2,846 pt production sheet, so the
    # block gap scales with the shorter edge of the design surface. Measured:
    # 1.5 % gives ES3083 nine blocks (its preview shows ~8 units) and is stable
    # up to 2.5 %; YB-BB stays a single full-bleed block at every value.
    block_gap_frac: float = 0.015
    workspace_gap_pt: float = 12.0
    background_area_frac: float = 0.02      # of the design surface
    glyph_min_area_pt2: float = 1.0
    glyph_max_area_pt2: float = 900.0
    min_structural_strokes: int = 3
    min_cluster_paths: int = 3
    min_cluster_area_pt2: float = 100.0
    mirror_size_tol: float = 0.02           # 2 % (twin panels differ ~1.2 %)
    full_bleed_coverage: float = 0.90
    content_collapse_frac: float = 0.80
    max_unassigned_frac: float = 0.05
    thin_line_pt: float = 2.0
    grid_min_rows: int = 3
    grid_min_cols: int = 2
    barcode_min_bars: int = 20
    barcode_max_bars: int = 200          # a real barcode has tens of bars
    barcode_min_frac: float = 0.5        # bars must dominate their cluster
    palette_min_chips: int = 2
    palette_size_tol: float = 0.05
    palette_min_chip_coverage: float = 0.15
    palette_max_paths: int = 60
    table_max_cells: int = 200           # a spec table has tens of cells
    table_min_fill: float = 0.4          # cells must tile their own bbox
    table_max_fill: float = 1.15         # ...without overlapping

    def fingerprint(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


DEFAULT_THRESHOLDS = SegThresholds()


def _inf(value, source, evidence, confidence, tier=C.TIER_HEURISTIC) -> dict:
    d = Inferred(value=value, source=source, evidence=list(evidence),
                 confidence=round(confidence, 3), parser=PARSER).to_dict()
    d["tier"] = tier
    return d


# --------------------------------------------------------------------------
# path extraction


def _paths(page, th: SegThresholds, surface_area: float) -> list[dict]:
    out = []
    for d in page.get_drawings(extended=True):
        if d["type"] not in ("f", "s", "fs"):
            continue
        r = fitz.Rect(d["rect"])
        if r.is_infinite:
            continue
        rect = (round(r.x0, 3), round(r.y0, 3), round(r.x1, 3), round(r.y1, 3))
        a = area(rect)
        w = d.get("width") or 0.0
        structural = (d["type"] == "s" and d.get("fill") is None
                      and 0 < w <= th.structural_max_width_pt)
        out.append({
            "rect": rect, "area": a, "type": d["type"], "width": w,
            "fill": tuple(round(c, 3) for c in d["fill"]) if d.get("fill") else None,
            "stroke": tuple(round(c, 3) for c in d["color"]) if d.get("color") else None,
            "dashed": bool(d.get("dashes") and d["dashes"] not in ("[] 0", "[]0")),
            "structural": structural,
            "glyph": (d["type"] == "f"
                      and th.glyph_min_area_pt2 < a < th.glyph_max_area_pt2),
            "background": a >= th.background_area_frac * surface_area,
            "seqno": d.get("seqno"),
        })
    return out


def _rasters(page) -> list[dict]:
    out = []
    for im in page.get_images(full=True):
        try:
            bb = page.get_image_bbox(im)
        except Exception:  # noqa: BLE001
            continue
        r = (round(bb.x0, 3), round(bb.y0, 3), round(bb.x1, 3), round(bb.y1, 3))
        if area(r) <= 0:
            continue
        out.append({"rect": r, "width_px": im[2], "height_px": im[3],
                    "colorspace": im[5], "xref": im[0]})
    return out


# --------------------------------------------------------------------------
# classification


def _grid_signals(members, th: SegThresholds) -> tuple[int, int]:
    """Counts of thin horizontal and vertical rules (SPEC_TABLE / BARCODE)."""
    h = v = 0
    for m in members:
        x0, y0, x1, y1 = m["rect"]
        w, ht = x1 - x0, y1 - y0
        if ht <= th.thin_line_pt and w > 4 * max(ht, 0.5):
            h += 1
        elif w <= th.thin_line_pt and ht > 4 * max(w, 0.5):
            v += 1
    return h, v


def _palette_signal(members, th: SegThresholds) -> tuple[int, float]:
    """Equal-sized solid fill chips, aligned, with distinct colours.

    Returns (chip_count, chip_area_fraction_of_their_own_bbox). Requiring the
    chips to dominate their cluster stops a swatch strip that merely sits beside
    a render from re-labelling the whole render.
    """
    chips = [m for m in members
             if m["type"] == "f" and m["fill"] and m["area"] > th.glyph_max_area_pt2]
    if len(chips) < th.palette_min_chips:
        return 0, 0.0
    best: list = []
    for i, a in enumerate(chips):
        aw, ah = a["rect"][2] - a["rect"][0], a["rect"][3] - a["rect"][1]
        group = [a]
        for b in chips[i + 1:]:
            bw, bh = b["rect"][2] - b["rect"][0], b["rect"][3] - b["rect"][1]
            if (abs(aw - bw) <= th.palette_size_tol * max(aw, 1)
                    and abs(ah - bh) <= th.palette_size_tol * max(ah, 1)
                    and b["fill"] != a["fill"]
                    and (abs(a["rect"][1] - b["rect"][1]) < ah
                         or abs(a["rect"][0] - b["rect"][0]) < aw)):
                group.append(b)
        if len(group) > len(best):
            best = group
    if len(best) < th.palette_min_chips:
        return 0, 0.0
    bb = union_bbox([c["rect"] for c in best], range(len(best)))
    frac = sum(c["area"] for c in best) / max(area(bb), 1e-6)
    return len(best), round(frac, 4)


def _barcode_signal(members, th: SegThresholds) -> int:
    """Narrow vertical bars sharing ONE baseline and ONE height.

    Outlined typography defeats a naive version of this: the stems of `l`, `i`
    and `1` are narrow tall fills, and 5,102 of them once scored as a barcode.
    Bars must therefore share a baseline *and* a height, be bounded in number,
    and dominate their cluster.
    """
    bars = [m for m in members if m["type"] == "f" and m["fill"]
            and (m["rect"][2] - m["rect"][0]) <= th.thin_line_pt
            and (m["rect"][3] - m["rect"][1]) > 4 * th.thin_line_pt]
    if not (th.barcode_min_bars <= len(bars) <= th.barcode_max_bars):
        return 0
    if len(bars) < th.barcode_min_frac * max(len(members), 1):
        return 0
    tops = {round(b["rect"][1], 0) for b in bars}
    bots = {round(b["rect"][3], 0) for b in bars}
    if len(tops) > 3 or len(bots) > 3:      # must share a baseline and a height
        return 0
    return len(bars)


def _table_signal(members, th: SegThresholds) -> tuple[int, int, int]:
    """Largest genuine lattice among `members`, via the same strict test used by
    the pre-pass. A looser variant once reported 4,913 scattered artwork rects as
    a 17x41 grid on FL-3098."""
    grids = detect_tables(members, th)
    if not grids:
        return 0, 0, 0
    g = max(grids, key=lambda x: len(x["idxs"]))
    return len(g["idxs"]), g["rows"], g["cols"]


def classify_candidate(stats: dict, th: SegThresholds, *, workspace: bool,
                       penalty: float = 1.0) -> dict:
    """Provisional type + evidence. Confidence is deliberately capped: nothing
    here is a claim, and every candidate awaits human confirmation."""
    n = stats["path_count"]
    ev: list[str] = []
    bbox_area = max(stats["bbox_area_pt2"], 1e-6)

    raster_cov = stats["raster_area_pt2"] / bbox_area
    if stats["raster_count"] and raster_cov > 0.6:
        ev = [f"raster covers {raster_cov:.0%} of the candidate",
              f"{stats['raster_count']} embedded image(s)"]
        return _inf("PRODUCT_PHOTO", "raster_dominance", ev, 0.55 * penalty)

    if (stats["table_cells"] >= th.grid_min_rows * th.grid_min_cols
            and stats["raster_count"] == 0
            and stats["glyph_count"] <= 0.1 * max(n, 1)
            and stats["distinct_fill_colors"] <= 2):
        ev = [f"{stats['table_cells']} equal-sized cells in "
              f"{stats['table_rows']} rows x {stats['table_cols']} columns",
              f"{stats['glyph_count']} glyph-scale fills (cells are empty)",
              f"{stats['distinct_fill_colors']} distinct fill colour(s)"]
        return _inf("SPEC_TABLE", "ruled_grid", ev, 0.5 * penalty)

    if stats["barcode_bars"]:
        ev = [f"{stats['barcode_bars']} narrow vertical bars sharing one "
              "baseline and one height"]
        return _inf("BARCODE", "bar_pattern", ev, 0.5 * penalty)

    if (stats["palette_chips"] >= th.palette_min_chips
            and stats["palette_chip_coverage"] >= th.palette_min_chip_coverage
            and n <= th.palette_max_paths):
        ev = [f"{stats['palette_chips']} equal-sized solid chips, aligned, "
              "distinct fills",
              f"chips cover {stats['palette_chip_coverage']:.0%} of their own bbox"]
        return _inf("COLOR_PALETTE_STRIP", "chip_row", ev, 0.5 * penalty)

    if (stats["structural_count"] >= th.min_structural_strokes
            and stats["fill_coverage"] < 0.15
            and stats["structural_count"] >= 0.3 * max(n, 1)):
        ev = [f"{stats['structural_count']} thin no-fill strokes",
              f"{stats['dashed_count']} dashed",
              "structural evidence only — dieline confirmation is DIP-0B3"]
        return _inf("DIELINE_CANDIDATE", "structural_dominance", ev, 0.4 * penalty)

    glyph_frac = stats["glyph_count"] / max(n, 1)
    if glyph_frac > 0.8 and stats["raster_count"] == 0:
        w = stats["bbox_pt"][2] - stats["bbox_pt"][0]
        h = stats["bbox_pt"][3] - stats["bbox_pt"][1]
        elongated = w > 3 * h or h > 3 * w
        ev = [f"{glyph_frac:.0%} glyph-scale fills",
              "TEXT_LIKE_GEOMETRY_CANDIDATE — may be type OR icons/ornaments/"
              "motifs/decorative linework"]
        if elongated and n > 200:
            return _inf("LEGAL_TEXT", "dense_glyph_block", ev, 0.35 * penalty)
        return _inf("TECHNICAL_NOTES", "glyph_cluster", ev, 0.3 * penalty)

    if workspace:
        return _inf("REFERENCE_MATERIAL", "off_canvas_default",
                    ["fully outside the ArtBox; reviewer decides its role"],
                    0.3 * penalty)

    if n >= th.min_cluster_paths and (stats["fill_count"] or stats["raster_count"]):
        ev = [f"{n} paths, {stats['fill_count']} fills, "
              f"{stats['raster_count']} rasters",
              f"fill coverage {stats['fill_coverage']:.0%}"]
        return _inf("SURFACE_ARTWORK", "mixed_content", ev, 0.4 * penalty)

    return _inf("UNKNOWN", "no_rule_matched", [f"{n} paths"], 0.0)


# --------------------------------------------------------------------------
# candidate assembly


def _stats(members, rasters, bbox) -> dict:
    fill_area = sum(m["area"] for m in members if m["type"] in ("f", "fs"))
    bbox_area = max(area(bbox), 1e-6)
    fills = [m for m in members if m["fill"]]
    return {
        "bbox_pt": [round(v, 2) for v in bbox],
        "bbox_mm": [round(pt_to_mm(v), 2) for v in bbox],
        "bbox_area_pt2": round(bbox_area, 2),
        "path_count": len(members),
        "structural_count": sum(1 for m in members if m["structural"]),
        "glyph_count": sum(1 for m in members if m["glyph"]),
        "fill_count": sum(1 for m in members if m["type"] in ("f", "fs")),
        "stroke_count": sum(1 for m in members if m["type"] in ("s", "fs")),
        "dashed_count": sum(1 for m in members if m["dashed"]),
        "raster_count": len(rasters),
        "raster_area_pt2": round(sum(area(r["rect"]) for r in rasters), 2),
        "fill_coverage": round(min(1.0, fill_area / bbox_area), 4),
        "distinct_fill_colors": len({m["fill"] for m in fills}),
    }


def _attach_signals(st: dict, members, th: SegThresholds) -> None:
    """Type-discriminating signals, computed once per candidate."""
    h, v = _grid_signals(members, th)
    # The palette test is O(chips^2) and the rule requires a small cluster
    # anyway; on a 67k-path artwork page it would compare millions of pairs.
    if len(members) <= th.palette_max_paths:
        chips, chip_cov = _palette_signal(members, th)
    else:
        chips, chip_cov = 0, 0.0
    cells, rows, cols = _table_signal(members, th)
    st["grid_h_runs"], st["grid_v_runs"] = h, v
    st["palette_chips"] = chips
    st["palette_chip_coverage"] = chip_cov
    st["table_cells"], st["table_rows"], st["table_cols"] = cells, rows, cols
    st["barcode_bars"] = _barcode_signal(members, th)


def _lattice_positions(vals: list[float], tol: float) -> int:
    """Count distinct lattice positions, merging values within `tol`."""
    if not vals:
        return 0
    xs = sorted(vals)
    n, last = 1, xs[0]
    for v in xs[1:]:
        if v - last > tol:
            n += 1
            last = v
    return n


def detect_tables(paths, th: SegThresholds) -> list[dict]:
    """Find ruled grids of equal-sized cells BEFORE proximity agglomeration.

    A blank spec table sits flush against neighbouring artwork (ES3083's grid
    overlaps the artwork block in y), so no proximity gap can separate them.
    Structure can — but only if the test demands a genuine lattice. A loose
    version matched 1,304 scattered artwork rects on YB-BB and, by lifting them
    out, destroyed that page's correct full-bleed verdict. So the cells must:

      * be equal-sized, larger than a glyph, and not page-background
      * number between `grid_min_rows * grid_min_cols` and `table_max_cells`
      * sit on a lattice: rows x cols must account for the cell count (±20 %)
      * tile their own bbox without overlapping (fill factor in [0.4, 1.15])
      * share at most two fill colours
    """
    buckets: dict[tuple[int, int], list[int]] = {}
    for i, m in enumerate(paths):
        if m["area"] <= th.glyph_max_area_pt2 or m["background"]:
            continue
        w = round((m["rect"][2] - m["rect"][0]) / 4) * 4
        h = round((m["rect"][3] - m["rect"][1]) / 4) * 4
        if w <= 0 or h <= 0:
            continue
        buckets.setdefault((w, h), []).append(i)

    out: list[dict] = []
    for (w, h), idxs in sorted(buckets.items()):
        n = len(idxs)
        if not (th.grid_min_rows * th.grid_min_cols <= n <= th.table_max_cells):
            continue
        rows = _lattice_positions([paths[i]["rect"][1] for i in idxs], h / 2.0)
        cols = _lattice_positions([paths[i]["rect"][0] for i in idxs], w / 2.0)
        if rows < th.grid_min_rows or cols < th.grid_min_cols:
            continue
        if abs(rows * cols - n) > 0.2 * n:          # must be a full lattice
            continue
        bb = union_bbox([paths[i]["rect"] for i in idxs], range(n))
        fill_factor = sum(paths[i]["area"] for i in idxs) / max(area(bb), 1e-6)
        if not (th.table_min_fill <= fill_factor <= th.table_max_fill):
            continue                                 # scattered or overlapping
        if len({paths[i]["fill"] for i in idxs}) > 2:
            continue
        out.append({"idxs": sorted(idxs), "rows": rows, "cols": cols})
    return out


def _mirror_evidence(cands, surface, th: SegThresholds) -> None:
    """Repeated / mirrored geometry — measured in the pilot (ES3083 has two
    identical 346x627 pt panels at mirrored x)."""
    cx = (surface[0] + surface[2]) / 2.0
    for i, a in enumerate(cands):
        aw = a["bbox_pt"][2] - a["bbox_pt"][0]
        ah = a["bbox_pt"][3] - a["bbox_pt"][1]
        for b in cands[i + 1:]:
            bw = b["bbox_pt"][2] - b["bbox_pt"][0]
            bh = b["bbox_pt"][3] - b["bbox_pt"][1]
            if (abs(aw - bw) > th.mirror_size_tol * max(aw, 1)
                    or abs(ah - bh) > th.mirror_size_tol * max(ah, 1)):
                continue
            a_mid = (a["bbox_pt"][0] + a["bbox_pt"][2]) / 2
            b_mid = (b["bbox_pt"][0] + b["bbox_pt"][2]) / 2
            mirrored = abs((cx - a_mid) + (cx - b_mid)) < 0.02 * max(aw, 1)
            same_row = abs(a["bbox_pt"][1] - b["bbox_pt"][1]) < 0.05 * max(ah, 1)
            kind = ("front_back_pair" if mirrored and same_row
                    else "repeated_geometry")
            for x, y in ((a, b), (b, a)):
                x.setdefault("repeat_evidence", []).append(
                    {"kind": kind, "twin_unit_id": y["unit_id"],
                     "size_pt": [round(aw, 2), round(ah, 2)]})


def _sort_key(bbox, count):
    return (round(bbox[1], 2), round(bbox[0], 2), -count)


# --------------------------------------------------------------------------


def segment_page(doc, page, page_index: int, rel_path: str, budget: Budget,
                 th: SegThresholds = DEFAULT_THRESHOLDS) -> dict:
    raw_page = doc.xref_object(page.xref, compressed=False)
    boxes = build_boxes(page, raw_page)
    surface = tuple(boxes["design_surface_pt"])
    surface_area = max(area(surface), 1e-6)

    paths = _paths(page, th, surface_area)
    rasters = _rasters(page)

    # --- ArtBox / workspace partition (safeguard 4 + B2 decision 2) --------
    primary_paths, workspace_paths = [], []
    straddlers = 0
    for p in paths:
        clipped = clip_rect(p["rect"], surface)
        if clipped is None:
            p["straddles_artbox"] = False
            workspace_paths.append(p)
            continue
        full_a = max(p["area"], 1e-9)
        inside = area(clipped) / full_a
        p["straddles_artbox"] = inside < 0.999
        p["inside_coverage"] = round(min(1.0, inside), 4)
        p["original_rect"] = p["rect"]         # never discarded
        p["clip_rect"] = clipped               # used for primary clustering
        if p["straddles_artbox"]:
            straddlers += 1
        primary_paths.append(p)

    primary_rasters, workspace_rasters = [], []
    for r in rasters:
        c = clip_rect(r["rect"], surface)
        (primary_rasters if c else workspace_rasters).append(r)

    background = [p for p in primary_paths if p["background"]]
    structural = [p for p in primary_paths if p["structural"]]
    # Clustering input is EVERY non-background primary path — structural strokes
    # included. Excluding them once dropped ES3083's blank spec-table cells from
    # the model entirely (they clustered below `min_structural_strokes` and then
    # belonged to no candidate). `unassigned_paths` below proves nothing is lost.
    content = [p for p in primary_paths if not p["background"]]

    grid = build_grid(surface, budget.limits.max_render_px,
                      budget.limits.max_mask_pixels)

    # Structure-aware pre-pass: lift ruled grids out before proximity merging.
    table_groups = detect_tables(content, th)
    table_idx = {i for g in table_groups for i in g["idxs"]}
    table_paths = [[content[i] for i in g["idxs"]] for g in table_groups]
    content = [p for i, p in enumerate(content) if i not in table_idx]

    # Structural skeleton: evidence for B3 and a candidate source for panels
    # that carry no artwork of their own.
    struct_groups = cluster_rects([p["clip_rect"] for p in structural],
                                  th.structural_gap_pt, grid) if structural else []

    # Level 1: tight proximity -> words / marks. NOT size-filtered: a lone
    # spec-table cell is a legitimate 1-path level-1 cluster and must survive
    # to be agglomerated at level 2. Filtering happens on blocks.
    level1 = cluster_rects([p["clip_rect"] for p in content],
                           th.content_gap_pt, grid) if content else []
    # Level 2: agglomerate level-1 bboxes into blocks, gap scaled to the surface.
    block_gap = max(th.content_gap_pt,
                    th.block_gap_frac * min(surface[2] - surface[0],
                                            surface[3] - surface[1]))
    level1_boxes = [union_bbox([content[i]["clip_rect"] for i in g], range(len(g)))
                    for g in level1]
    content_groups = []
    if level1_boxes:
        for blk in cluster_rects(level1_boxes, block_gap, grid):
            merged_idx: list[int] = []
            for j in blk:
                merged_idx.extend(level1[j])
            content_groups.append(sorted(merged_idx))

    raw: list[dict] = []
    for g in struct_groups:
        if len(g) < th.min_structural_strokes:
            continue
        bb = union_bbox([structural[i]["clip_rect"] for i in g], range(len(g)))
        raw.append({"layer": "structural", "bbox": bb,
                    "members": [structural[i] for i in g]})
    for g in content_groups:
        if len(g) < th.min_cluster_paths:
            continue
        bb = union_bbox([content[i]["clip_rect"] for i in g], range(len(g)))
        if area(bb) < th.min_cluster_area_pt2:
            continue
        raw.append({"layer": "content", "bbox": bb,
                    "members": [content[i] for i in g]})
    for members in table_paths:
        bb = union_bbox([m["clip_rect"] for m in members], range(len(members)))
        raw.append({"layer": "table", "bbox": bb, "members": members,
                    "protected": True})
    for r in primary_rasters:
        raw.append({"layer": "raster", "bbox": r["rect"], "members": [], "raster": r})

    # merge highly-overlapping candidates across layers
    merged: list[dict] = []
    for cand in sorted(raw, key=lambda c: -area(c["bbox"])):
        hit = None
        for m in merged:
            if m.get("protected") or cand.get("protected"):
                continue                    # a detected grid is never merged away
            if iou(cand["bbox"], m["bbox"]) > 0.8:
                hit = m
                break
        if hit:
            hit["bbox"] = union_bbox([hit["bbox"], cand["bbox"]], [0, 1])
            hit["members"].extend(cand["members"])
            hit["layer"] = f"{hit['layer']}+{cand['layer']}"
            if "raster" in cand:
                hit.setdefault("rasters", []).append(cand["raster"])
        else:
            m = dict(cand)
            if "raster" in m:
                m["rasters"] = [m.pop("raster")]
            merged.append(m)

    # assign every primary path to exactly ONE candidate: the smallest whose
    # bbox contains its centre (most specific). No object is double-counted.
    for m in merged:
        if m.get("protected"):
            m["_table_members"] = list(m["members"])
        m["members"] = []
        m.setdefault("rasters", [])
    for m in merged:
        if m.get("protected"):
            m["members"] = list(m.get("_table_members", m["members"]))

    order = sorted(range(len(merged)), key=lambda i: area(merged[i]["bbox"]))
    unassigned = 0
    unassigned_rects = []
    for p in content:                      # already includes structural paths
        r = p["clip_rect"]
        cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        for i in order:
            b = merged[i]["bbox"]
            if b[0] <= cx <= b[2] and b[1] <= cy <= b[3]:
                merged[i]["members"].append(p)
                break
        else:
            unassigned += 1                # counted, never silently dropped
            unassigned_rects.append(p["clip_rect"])
    for r in primary_rasters:
        rr = r["rect"]
        cx, cy = (rr[0] + rr[2]) / 2, (rr[1] + rr[3]) / 2
        for i in order:
            b = merged[i]["bbox"]
            if b[0] <= cx <= b[2] and b[1] <= cy <= b[3]:
                if r not in merged[i]["rasters"]:
                    merged[i]["rasters"].append(r)
                break

    merged = [m for m in merged if m["members"] or m["rasters"]]
    merged.sort(key=lambda m: _sort_key(m["bbox"], len(m["members"])))

    stem = Path(rel_path).stem
    penalty = budget.confidence_penalty()
    candidates = []
    for i, m in enumerate(merged):
        st = _stats(m["members"], m["rasters"], m["bbox"])
        _attach_signals(st, m["members"], th)
        cand = {
            "unit_id": f"{stem}-p{page_index}-u{i:02d}",
            "file": rel_path, "page": page_index,
            "artbox_pt": [round(v, 2) for v in surface],
            "surface": "artbox" if boxes["design_surface"] == "artbox" else "page_rect",
            "layer": m["layer"],
            "off_canvas": False,
            "straddling_members": sum(1 for p in m["members"]
                                      if p.get("straddles_artbox")),
            **st,
            "candidate_type": classify_candidate(st, th, workspace=False,
                                                 penalty=penalty),
            "human_confirmed_type": None,
            "include_in_historical_memory": None,
            "human_confirmed": human_block(),
        }
        candidates.append(cand)

    _mirror_evidence(candidates, surface, th)
    for c in candidates:
        if c.get("repeat_evidence"):
            c["candidate_type"]["evidence"].append(
                f"repeat/mirror: {c['repeat_evidence'][0]['kind']}")

    # containment links (nesting preserved, not merged away)
    for a in candidates:
        for b in candidates:
            if a is b:
                continue
            if containment(a["bbox_pt"], b["bbox_pt"]) >= 0.95:
                a["contained_by"] = b["unit_id"]
                b.setdefault("contains", []).append(a["unit_id"])

    # --- workspace (fully off-canvas) -------------------------------------
    workspace_candidates = []
    if workspace_paths or workspace_rasters:
        wrects = [p["rect"] for p in workspace_paths]
        wbb = union_bbox(wrects + [r["rect"] for r in workspace_rasters],
                         range(len(wrects) + len(workspace_rasters))) \
            if (wrects or workspace_rasters) else surface
        wgrid = build_grid(wbb, budget.limits.max_render_px,
                           budget.limits.max_mask_pixels)
        wgroups = cluster_rects(wrects, th.workspace_gap_pt, wgrid) if wrects else []
        for i, g in enumerate(wgroups):
            if len(g) < th.min_cluster_paths:
                continue
            bb = union_bbox([workspace_paths[j]["rect"] for j in g], range(len(g)))
            members = [workspace_paths[j] for j in g]
            rs = [r for r in workspace_rasters
                  if containment(r["rect"], bb) > 0.5]
            st = _stats(members, rs, bb)
            _attach_signals(st, members, th)
            workspace_candidates.append({
                "unit_id": f"{stem}-p{page_index}-w{i:02d}",
                "file": rel_path, "page": page_index,
                "artbox_pt": [round(v, 2) for v in surface],
                "off_canvas": True,
                **st,
                "candidate_type": classify_candidate(st, th, workspace=True,
                                                     penalty=penalty),
                "human_confirmed_type": None,
                # never auto-included in Historical Design Memory
                "include_in_historical_memory": None,
                "human_confirmed": human_block(),
            })
        workspace_candidates.sort(key=lambda c: _sort_key(c["bbox_pt"],
                                                          c["path_count"]))
        for i, c in enumerate(workspace_candidates):
            c["unit_id"] = f"{stem}-p{page_index}-w{i:02d}"

    # --- status ------------------------------------------------------------
    # Segmentation status describes SEGMENTATION quality. It must not be gated on
    # candidate *type* confidence (types are capped low by design), or no page
    # could ever be AUTO_CONFIDENT. Type confidence is reported separately.
    largest_cov = (max((area(c["bbox_pt"]) for c in candidates), default=0.0)
                   / surface_area)
    top_paths = max((c["path_count"] for c in candidates), default=0)
    clustering_input = len(content) + len(table_idx)
    collapse = top_paths > th.content_collapse_frac * max(clustering_input, 1)
    unassigned_frac = unassigned / max(clustering_input, 1)

    failures = []
    if not struct_groups:
        failures.append("no_structural_skeleton")
    if len(candidates) == 1:
        failures.append("full_bleed_single_candidate")
    elif largest_cov >= th.full_bleed_coverage:
        failures.append("dominant_candidate")
    if collapse:
        failures.append("content_cluster_collapse")
    if unassigned_frac > th.max_unassigned_frac:
        failures.append("unassigned_paths")
    if budget.sampling_limits:
        failures.append("clip_group_detail_capped")

    mean_conf = (sum(c["candidate_type"]["confidence"] for c in candidates)
                 / len(candidates)) if candidates else 0.0
    if ("full_bleed_single_candidate" in failures
            or "content_cluster_collapse" in failures):
        status = "MANUAL_REQUIRED"
    elif ("no_structural_skeleton" in failures
          or "dominant_candidate" in failures
          or "unassigned_paths" in failures
          or len(candidates) < 2):
        status = "AUTO_LOW_CONFIDENCE"
    else:
        status = "AUTO_CONFIDENT"

    return {
        "file": rel_path,
        "page": page_index,
        "artbox_pt": [round(v, 2) for v in surface],
        "artbox_mm": [round(pt_to_mm(v), 2) for v in surface],
        "surface": boxes["design_surface"],
        "segmentation": {
            "status": status,
            "failure_indicators": failures,
            "candidate_count": len(candidates),
            "workspace_candidate_count": len(workspace_candidates),
            "mean_type_confidence": round(mean_conf, 3),
            "largest_candidate_coverage": round(largest_cov, 4),
            "largest_candidate_path_share": round(top_paths / max(clustering_input, 1), 4),
            "unassigned_fraction": round(unassigned_frac, 4),
            "methods": ["structural_stroke_clustering",
                        "background_suppressed_content_clustering_level1",
                        "block_agglomeration_level2",
                        "raster_candidates", "repeat_mirror_detection",
                        "merge_and_containment"],
            "effective_block_gap_pt": round(block_gap, 2),
            "note": ("a full-bleed design may legitimately yield ONE candidate; "
                     "it is never forced apart"),
        },
        "page_geometry": {
            "paths_total": len(paths),
            "background_paths_suppressed": len(background),
            "structural_paths": len(structural),
            "structural_clusters": len(struct_groups),
            "clustering_input_paths": len(content),
            "unassigned_paths": unassigned,
            "unassigned_union_bbox_pt": ([round(v, 2) for v in
                                          union_bbox(unassigned_rects,
                                                     range(len(unassigned_rects)))]
                                         if unassigned_rects else None),
            "protected_table_grids": len(table_groups),
            "content_clusters_level1": len(level1),
            "content_blocks_level2": len(content_groups),
            "straddling_paths": straddlers,
            "fully_off_canvas_paths": len(workspace_paths),
            "rasters_primary": len(primary_rasters),
            "rasters_off_canvas": len(workspace_rasters),
        },
        "provenance": {
            "algorithm_version": ALGORITHM_VERSION,
            "parser": PARSER,
            "thresholds": asdict(th),
            "thresholds_fingerprint": th.fingerprint(),
            "grid": {"zoom": round(grid.zoom, 6),
                     "width_px": grid.width, "height_px": grid.height},
            "note": ("candidate ids are deterministic for identical source bytes, "
                     "parser version and thresholds; a threshold change is "
                     "explainable via thresholds_fingerprint"),
        },
        "candidates": candidates,
        "workspace_candidates": workspace_candidates,
        "limits": budget.to_dict(),
    }
