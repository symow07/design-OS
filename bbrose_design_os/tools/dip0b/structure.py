"""Page-wide structural graph (DIP-0B3).

Built from page geometry alone, **independent of B2 candidate boundaries**. A
likely dieline may span several candidates, coexist with surface artwork, cross
candidate borders, or live on a page whose content segmentation collapsed — so
this runs first and candidates become attachment targets afterwards.

Nothing here exports reusable production geometry. Panel polygons are recorded as
analytical measurements (vertex counts, areas, adjacency), never as an importable
path set.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import fitz

from .cluster import area as _area

# --- tolerances -------------------------------------------------------------
POINT_TOL = 0.75          # pt: two endpoints are the same point
COLLINEAR_TOL = 0.75      # pt: perpendicular distance for a shared edge
ANGLE_TOL_DEG = 2.0       # orthogonality / parallelism
MIN_SEGMENT_PT = 1.5      # ignore sub-hairline fragments
MIN_PANEL_AREA_PT2 = 400.0
MIN_EDGE_OVERLAP_PT = 4.0

STRUCTURAL_MAX_WIDTH_PT = 1.2


@dataclass(frozen=True)
class Segment:
    x0: float
    y0: float
    x1: float
    y1: float
    path_index: int
    dashed: bool
    curved: bool
    width: float

    @property
    def length(self) -> float:
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    @property
    def angle_deg(self) -> float:
        a = math.degrees(math.atan2(self.y1 - self.y0, self.x1 - self.x0)) % 180.0
        return a

    @property
    def is_axis_aligned(self) -> bool:
        a = self.angle_deg
        return min(a, abs(90.0 - a), abs(180.0 - a)) <= ANGLE_TOL_DEG

    def as_dict(self) -> dict:
        return {"p0": [round(self.x0, 2), round(self.y0, 2)],
                "p1": [round(self.x1, 2), round(self.y1, 2)],
                "length_pt": round(self.length, 2),
                "angle_deg": round(self.angle_deg, 1),
                "axis_aligned": self.is_axis_aligned,
                "dashed": self.dashed, "curved": self.curved,
                "path_index": self.path_index}


def _pt(p) -> tuple[float, float]:
    return (float(p.x), float(p.y))


def structural_paths(drawings) -> list[tuple[int, dict]]:
    """Thin, no-fill strokes — the structural layer. Index is into `drawings`."""
    out = []
    for i, d in enumerate(drawings):
        if d["type"] != "s" or d.get("fill") is not None:
            continue
        w = d.get("width") or 0.0
        if not (0 < w <= STRUCTURAL_MAX_WIDTH_PT):
            continue
        out.append((i, d))
    return out


def extract_segments(drawings) -> list[Segment]:
    """Line segments of the structural layer. Curves contribute their chord and
    are flagged — a rounded corner is still an edge, but it is not a fold."""
    segs: list[Segment] = []
    for i, d in structural_paths(drawings):
        dashed = bool(d.get("dashes") and d["dashes"] not in ("[] 0", "[]0"))
        w = d.get("width") or 0.0
        for it in d.get("items", []):
            kind = it[0]
            if kind == "l":
                a, b = _pt(it[1]), _pt(it[2])
                segs.append(Segment(a[0], a[1], b[0], b[1], i, dashed, False, w))
            elif kind == "c":
                a, b = _pt(it[1]), _pt(it[4])
                segs.append(Segment(a[0], a[1], b[0], b[1], i, dashed, True, w))
            elif kind == "re":
                r = fitz.Rect(it[1])
                pts = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
                for j in range(4):
                    a, b = pts[j], pts[(j + 1) % 4]
                    segs.append(Segment(a[0], a[1], b[0], b[1], i, dashed, False, w))
            elif kind == "qu":
                q = it[1]
                pts = [_pt(q.ul), _pt(q.ur), _pt(q.lr), _pt(q.ll)]
                for j in range(4):
                    a, b = pts[j], pts[(j + 1) % 4]
                    segs.append(Segment(a[0], a[1], b[0], b[1], i, dashed, False, w))
    return [s for s in segs if s.length >= MIN_SEGMENT_PT]


# --- closed panels ----------------------------------------------------------

def is_closed(d, segs: list[Segment]) -> bool:
    """Geometric closure. MuPDF reports `closePath=False` on every structural
    path in the pilot, so the flag alone finds nothing: ES3083 has 166 structural
    strokes, 0 with the flag, 9 closed by coincident endpoints.
    """
    if any(it[0] in ("re", "qu") for it in d.get("items", [])):
        return True
    if d.get("closePath"):
        return True
    if not segs:
        return False
    first, last = segs[0], segs[-1]
    return (math.hypot(first.x0 - last.x1, first.y0 - last.y1) <= POINT_TOL)


def closed_panels(drawings) -> list[dict]:
    """Closed structural paths large enough to be a carton panel.

    Recorded as measurements: bbox, area, vertex count, orthogonal fraction.
    The vertex list is deliberately NOT emitted as a reusable path.
    """
    panels = []
    for i, d in structural_paths(drawings):
        r = fitz.Rect(d["rect"])
        if r.is_empty or _area(tuple(r)) < MIN_PANEL_AREA_PT2:
            continue
        segs = [s for s in extract_segments([d])]
        if not segs or not is_closed(d, segs):
            continue
        ortho = sum(1 for s in segs if s.is_axis_aligned) / len(segs)
        panels.append({
            "panel_index": len(panels),
            "path_index": i,
            "bbox_pt": [round(v, 2) for v in r],
            "area_pt2": round(_area(tuple(r)), 2),
            "vertex_count": len(segs),
            "orthogonal_fraction": round(ortho, 3),
            "dashed": bool(d.get("dashes") and d["dashes"] not in ("[] 0", "[]0")),
            "curved_edges": sum(1 for s in segs if s.curved),
            "width_pt": round(d.get("width") or 0.0, 2),
        })
    return panels


# --- shared edges -----------------------------------------------------------

def _projection_overlap(a: Segment, b: Segment) -> float:
    """Overlap length of b projected onto a's direction, if collinear."""
    dx, dy = a.x1 - a.x0, a.y1 - a.y0
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return 0.0
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    for px, py in ((b.x0, b.y0), (b.x1, b.y1)):
        if abs((px - a.x0) * nx + (py - a.y0) * ny) > COLLINEAR_TOL:
            return 0.0
    t0 = (b.x0 - a.x0) * ux + (b.y0 - a.y0) * uy
    t1 = (b.x1 - a.x0) * ux + (b.y1 - a.y0) * uy
    lo, hi = sorted((t0, t1))
    return max(0.0, min(hi, L) - max(lo, 0.0))


def _parallel(a: Segment, b: Segment) -> bool:
    d = abs(a.angle_deg - b.angle_deg)
    return min(d, 180.0 - d) <= ANGLE_TOL_DEG


def shared_edges(segments: list[Segment], panels: list[dict]) -> list[dict]:
    """Collinear, overlapping STRAIGHT segments from *different* structural paths.

    A shared edge is the topological signal that two panels meet — the thing a
    decorative border never has. Callers must exclude curve chords: they are
    collinear by accident, not by structure.
    """
    by_path: dict[int, list[Segment]] = {}
    for s in segments:
        by_path.setdefault(s.path_index, []).append(s)

    panel_of = {p["path_index"]: p["panel_index"] for p in panels}
    out = []
    paths = sorted(by_path)
    for ai in range(len(paths)):
        for bi in range(ai + 1, len(paths)):
            pa, pb = paths[ai], paths[bi]
            best = None
            for sa in by_path[pa]:
                for sb in by_path[pb]:
                    if not _parallel(sa, sb):
                        continue
                    ov = _projection_overlap(sa, sb)
                    if ov >= MIN_EDGE_OVERLAP_PT and (best is None or ov > best[0]):
                        best = (ov, sa, sb)
            if best:
                ov, sa, sb = best
                out.append({
                    "path_a": pa, "path_b": pb,
                    "panel_a": panel_of.get(pa), "panel_b": panel_of.get(pb),
                    "overlap_pt": round(ov, 2),
                    "axis_aligned": sa.is_axis_aligned and sb.is_axis_aligned,
                    "either_dashed": sa.dashed or sb.dashed,
                    "edge_p0": [round(sa.x0, 2), round(sa.y0, 2)],
                    "edge_p1": [round(sa.x1, 2), round(sa.y1, 2)],
                })
    return out


def adjacency_components(panels: list[dict], edges: list[dict]) -> list[list[int]]:
    """Connected components of the panel-adjacency graph (union-find)."""
    idx = {p["panel_index"]: p["panel_index"] for p in panels}
    if not idx:
        return []
    parent = {k: k for k in idx}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e in edges:
        a, b = e["panel_a"], e["panel_b"]
        if a is None or b is None or a not in parent or b not in parent:
            continue
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    groups: dict[int, list[int]] = {}
    for k in parent:
        groups.setdefault(find(k), []).append(k)
    return [sorted(v) for _, v in sorted(groups.items())]


# --- technical marks --------------------------------------------------------

def glue_flap_candidates(panels: list[dict], edges: list[dict]) -> list[int]:
    """Small panels attached on exactly one edge with non-orthogonal sides.

    Topology, not appearance: a flap hangs off the carton by a single crease.
    """
    degree: dict[int, int] = {}
    for e in edges:
        for k in ("panel_a", "panel_b"):
            if e[k] is not None:
                degree[e[k]] = degree.get(e[k], 0) + 1
    if not panels:
        return []
    median_area = sorted(p["area_pt2"] for p in panels)[len(panels) // 2]
    out = []
    for p in panels:
        if degree.get(p["panel_index"], 0) != 1:
            continue
        if p["area_pt2"] > 0.6 * median_area:
            continue
        if p["orthogonal_fraction"] >= 0.95:      # a flap has an angled side
            continue
        out.append(p["panel_index"])
    return out


def mark_candidates(segments: list[Segment], surface: tuple, drawings) -> dict:
    """Registration / crop / dimension geometry, by shape and position only.

    Colour is NOT used here: `/Separation /All` proves registration ink exists in
    the document, never that a given stroke is a registration mark.
    """
    sx0, sy0, sx1, sy1 = surface
    w, h = sx1 - sx0, sy1 - sy0
    margin = 0.06 * min(w, h)

    def near_edge(x, y) -> bool:
        return (x < sx0 + margin or x > sx1 - margin
                or y < sy0 + margin or y > sy1 - margin)

    by_path: dict[int, list[Segment]] = {}
    for s in segments:
        by_path.setdefault(s.path_index, []).append(s)

    registration, crop, dimension = [], [], []
    for pi, segs in sorted(by_path.items()):
        xs = [c for s in segs for c in (s.x0, s.x1)]
        ys = [c for s in segs for c in (s.y0, s.y1)]
        bx0, by0, bx1, by1 = min(xs), min(ys), max(xs), max(ys)
        bw, bh = bx1 - bx0, by1 - by0
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        n = len(segs)

        # crop mark: 1-2 short orthogonal ticks near a corner/edge
        if n <= 2 and max(bw, bh) <= 40 and all(s.is_axis_aligned for s in segs) \
                and near_edge(cx, cy):
            crop.append({"path_index": pi, "bbox_pt": [round(bx0, 2), round(by0, 2),
                                                       round(bx1, 2), round(by1, 2)],
                         "segments": n})
            continue
        # registration mark: small, roughly square, several segments, near an edge
        if (3 <= n <= 12 and max(bw, bh) <= 30
                and abs(bw - bh) <= 0.35 * max(bw, bh, 1e-6) and near_edge(cx, cy)):
            registration.append({"path_index": pi,
                                 "bbox_pt": [round(bx0, 2), round(by0, 2),
                                             round(bx1, 2), round(by1, 2)],
                                 "segments": n})
            continue
        # dimension mark: a long thin axis-aligned run with short end ticks
        if n >= 3 and max(bw, bh) > 60 and min(bw, bh) <= 12 \
                and all(s.is_axis_aligned for s in segs):
            dimension.append({"path_index": pi,
                              "bbox_pt": [round(bx0, 2), round(by0, 2),
                                          round(bx1, 2), round(by1, 2)],
                              "segments": n})

    return {"registration_mark_candidates": registration,
            "crop_mark_candidates": crop,
            "dimension_mark_candidates": dimension,
            "note": ("shape and position only; registration ink presence is a "
                     "document-level fact and never assigns a mark here")}


MAX_REPEAT_PAIRS = 60


def repeated_panels(panels: list[dict], surface: tuple,
                    tol: float = 0.02) -> tuple[list[dict], int]:
    """Panels of equal dimensions, and mirrored pairs about the surface centre."""
    cx = (surface[0] + surface[2]) / 2
    out = []
    for i in range(len(panels)):
        a = panels[i]
        aw = a["bbox_pt"][2] - a["bbox_pt"][0]
        ah = a["bbox_pt"][3] - a["bbox_pt"][1]
        for j in range(i + 1, len(panels)):
            b = panels[j]
            bw = b["bbox_pt"][2] - b["bbox_pt"][0]
            bh = b["bbox_pt"][3] - b["bbox_pt"][1]
            if (abs(aw - bw) > tol * max(aw, 1) or abs(ah - bh) > tol * max(ah, 1)):
                continue
            am = (a["bbox_pt"][0] + a["bbox_pt"][2]) / 2
            bm = (b["bbox_pt"][0] + b["bbox_pt"][2]) / 2
            mirrored = abs((cx - am) + (cx - bm)) < 0.02 * max(aw, 1)
            out.append({"panel_a": a["panel_index"], "panel_b": b["panel_index"],
                        "size_pt": [round(aw, 2), round(ah, 2)],
                        "kind": "mirrored_pair" if mirrored else "repeated_geometry"})
    total = len(out)
    out.sort(key=lambda r: (r["kind"] != "mirrored_pair", -r["size_pt"][0]))
    return out[:MAX_REPEAT_PAIRS], total


def interior_lines(segments: list[Segment], outer: dict | None) -> dict:
    """Structural segments *inside* the outer cut contour.

    A production dieline is rarely a set of closed polygons. It is normally ONE
    closed cut contour with open fold/crease lines subdividing it — so panel
    topology has to be read from lines that terminate on the contour, not from
    polygon adjacency alone.
    """
    if outer is None:
        return {"segments_inside_outer_bbox": 0, "dashed_inside_outer_bbox": 0,
                "segments_touching_outer_bbox_edge": 0, "outer_path_index": None}

    x0, y0, x1, y1 = outer["bbox_pt"]
    tol = 4 * POINT_TOL

    def inside(px, py) -> bool:
        return x0 - tol <= px <= x1 + tol and y0 - tol <= py <= y1 + tol

    def on_boundary(px, py) -> bool:
        return (abs(px - x0) <= tol or abs(px - x1) <= tol
                or abs(py - y0) <= tol or abs(py - y1) <= tol)

    # Position relative to the outer contour's BBOX. This is a rectangular
    # approximation of a non-rectangular contour, so it is reported as a
    # measurement and deliberately does NOT drive the dieline threshold.
    inside_seg, dashed_inside, touching = 0, 0, 0
    for s in segments:
        mx, my = (s.x0 + s.x1) / 2, (s.y0 + s.y1) / 2
        if not inside(mx, my):
            continue
        inside_seg += 1
        if s.dashed:
            dashed_inside += 1
        if on_boundary(s.x0, s.y0) or on_boundary(s.x1, s.y1):
            touching += 1

    return {
        "segments_inside_outer_bbox": inside_seg,
        "dashed_inside_outer_bbox": dashed_inside,
        "segments_touching_outer_bbox_edge": touching,
        "outer_path_index": outer["path_index"],
        "interior_classification_note": (
            "positions are measured against the outer contour's bounding box, a "
            "rectangular approximation; these counts are evidence, not thresholds"),
    }


STRUCTURAL_COMPONENT_GAP_PT = 12.0


def structural_components(drawings, surface: tuple) -> list[dict]:
    """Connected components of the structural layer, by proximity.

    The dieline REGION must be anchored here, not on the largest closed polygon:
    a production carton outline is drawn as many open cut/fold paths and is never
    geometrically closed, so `outer_contour` on ES3083 is its blank spec table,
    not its carton.
    """
    from .cluster import build_grid, cluster_rects, union_bbox

    paths = structural_paths(drawings)
    if not paths:
        return []
    rects = [tuple(fitz.Rect(d["rect"])) for _, d in paths]
    grid = build_grid(surface, 2000, 4_000_000)
    groups = cluster_rects(rects, STRUCTURAL_COMPONENT_GAP_PT, grid)
    out = []
    for g in groups:
        bb = union_bbox(rects, g)
        out.append({"paths": len(g),
                    "path_indices": sorted(paths[i][0] for i in g),
                    "bbox_pt": [round(v, 2) for v in bb],
                    "area_pt2": round(_area(bb), 2)})
    out.sort(key=lambda c: (-c["paths"], c["bbox_pt"]))
    return out


def build_graph(drawings, surface: tuple) -> dict:
    """The page-level structural graph. No candidate boundaries are consulted."""
    segs = extract_segments(drawings)
    panels = closed_panels(drawings)
    # A shared panel edge is a STRAIGHT edge. Curve chords are collinear by
    # accident (an ornamental curl row put 29 fake "shared edges" on a page with
    # no panels at all), so they never establish adjacency.
    edges = shared_edges([s for s in segs if not s.curved], panels)
    comps = adjacency_components(panels, edges)
    flaps = glue_flap_candidates(panels, edges)
    marks = mark_candidates(segs, surface, drawings)
    repeats, repeats_total = repeated_panels(panels, surface)

    ortho = (sum(1 for s in segs if s.is_axis_aligned) / len(segs)) if segs else 0.0
    dashed = [s for s in segs if s.dashed]
    outer = max(panels, key=lambda p: p["area_pt2"], default=None)
    inner = interior_lines(segs, outer)
    comps = structural_components(drawings, surface)
    main = comps[0] if comps else None

    path_meta = [{"path_index": i,
                  "dashed": bool(d.get("dashes") and d["dashes"] not in ("[] 0", "[]0")),
                  "width_pt": round(d.get("width") or 0.0, 2)}
                 for i, d in structural_paths(drawings)]

    return {
        "_paths": path_meta,
        "structural_paths": len({s.path_index for s in segs}),
        "segments": len(segs),
        "segments_axis_aligned_fraction": round(ortho, 3),
        "dashed_segments": len(dashed),
        "structural_components": comps[:20],
        "structural_component_count": len(comps),
        "main_structural_component": main,
        "outer_contour": ({"panel_index": outer["panel_index"],
                           "bbox_pt": outer["bbox_pt"],
                           "area_pt2": outer["area_pt2"],
                           "orthogonal_fraction": outer["orthogonal_fraction"]}
                          if outer else None),
        **inner,
        "panels": panels,
        "panel_count": len(panels),
        # A decorative bubble is a closed structural stroke too: HL5503 has 115
        # "panels" that are circles. Carton panels are substantially orthogonal.
        "orthogonal_panel_count": sum(1 for p in panels
                                      if p["orthogonal_fraction"] >= 0.5),
        "shared_edges": edges,
        "shared_edge_count": len(edges),
        "adjacency_components": comps,
        "largest_component_panels": max((len(c) for c in comps), default=0),
        "glue_flap_candidates": flaps,
        "repeated_panels": repeats,
        "repeated_panel_pairs_total": repeats_total,
        "mirrored_panel_pairs": sum(1 for r in repeats if r["kind"] == "mirrored_pair"),
        **marks,
        "geometry_policy": ("analytical measurements only; no path set is exported "
                            "in SVG, DXF, AI or any production-reusable format"),
    }
