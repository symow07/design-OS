"""Automated dieline measurement from factory .ai files (2026-07-07, WS1).

The engine's geometry constants were hand-measured from ONE reference file
(DECISION-016) and several remain provisional. This module automates the
MEASUREMENT_NEEDED.md protocol against the whole production library:

    manage.py measure_dielines ../design_models --out report.json

Two layers, deliberately separated:

  extract_vector_drawing(path)   — the only PyMuPDF-dependent function;
                                   imports fitz lazily (dev dependency).
  classify_linework / infer_ste_measurements / aggregate
                                 — pure functions over simple dataclasses,
                                   unit-testable without fitz.

Probing the real library showed the factory files carry NO dash patterns —
creases are solid strokes in their own color — so classification is
geometry-first: the color group whose strokes span the largest area is the
dieline; long axis-aligned lines strictly inside its bounds are creases,
everything else in the group is cut.

Nothing here changes the engine. The report is reviewed by a human;
constants move only in the deliberate Phase-B step (snapshot regen +
DECISION entry).
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

_PT_TO_MM = 25.4 / 72.0

# --- data model -------------------------------------------------------------

Point = tuple[float, float]


@dataclass
class Stroke:
    color: tuple | None                 # rounded RGB 0-1, or None
    dashed: bool
    width: float                        # pt
    lines: list[tuple[Point, Point]] = field(default_factory=list)
    cubics: list[tuple[Point, Point, Point, Point]] = field(default_factory=list)


@dataclass
class RawDrawing:
    strokes: list[Stroke] = field(default_factory=list)


@dataclass
class Linework:
    cut_lines: list[tuple[Point, Point]] = field(default_factory=list)
    cut_cubics: list[tuple[Point, Point, Point, Point]] = field(default_factory=list)
    crease_lines: list[tuple[Point, Point]] = field(default_factory=list)
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)   # x0,y0,x1,y1 (mm)


# --- extraction (fitz-dependent) ---------------------------------------------

def extract_vector_drawing(path: str) -> RawDrawing | None:
    """Stroked vector paths of page 1, in mm. None when unreadable."""
    try:
        import fitz
    except ImportError as exc:                       # pragma: no cover
        raise RuntimeError(
            "PyMuPDF is required for dieline measurement: "
            "pip install -r requirements-dev.txt"
        ) from exc
    try:
        doc = fitz.open(path)
        page = doc[0]
        drawings = page.get_drawings()
    except Exception:  # noqa: BLE001 — unreadable/non-PDF file
        return None

    raw = RawDrawing()
    for d in drawings:
        color = d.get("color")
        if color is None:
            continue                                  # fill-only artwork
        stroke = Stroke(
            color=tuple(round(c, 2) for c in color),
            dashed=bool(d.get("dashes") and d["dashes"] not in ("[] 0", "")),
            width=float(d.get("width") or 0.0),
        )
        for item in d.get("items") or []:
            kind = item[0]
            if kind == "l":
                p0, p1 = item[1], item[2]
                stroke.lines.append((
                    (p0.x * _PT_TO_MM, p0.y * _PT_TO_MM),
                    (p1.x * _PT_TO_MM, p1.y * _PT_TO_MM),
                ))
            elif kind == "c":
                pts = [(q.x * _PT_TO_MM, q.y * _PT_TO_MM) for q in item[1:5]]
                stroke.cubics.append(tuple(pts))
            elif kind == "re":
                r = item[1]
                cs = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
                cs = [(x * _PT_TO_MM, y * _PT_TO_MM) for x, y in cs]
                for a, b in zip(cs, cs[1:] + cs[:1]):
                    stroke.lines.append((a, b))
        if stroke.lines or stroke.cubics:
            raw.strokes.append(stroke)
    return raw


# --- pure analysis ------------------------------------------------------------

def census_strokes(raw: RawDrawing) -> dict:
    """Color/dash histogram — run with --census to learn a library's
    conventions before trusting classification."""
    colors = Counter(str(s.color) for s in raw.strokes)
    dashed = sum(1 for s in raw.strokes if s.dashed)
    return {
        "strokes": len(raw.strokes),
        "dashed_strokes": dashed,
        "colors": dict(colors.most_common(8)),
    }


def _stroke_points(s: Stroke):
    for a, b in s.lines:
        yield a
        yield b
    for c in s.cubics:
        yield from c


def _bbox(points) -> tuple[float, float, float, float] | None:
    pts = list(points)
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _axis_fraction(lines) -> float:
    if not lines:
        return 0.0
    ax = sum(1 for a, b in lines
             if abs(a[0] - b[0]) < 0.35 or abs(a[1] - b[1]) < 0.35)
    return ax / len(lines)


def classify_linework(raw: RawDrawing) -> Linework | None:
    """Find the dieline inside a factory file's stroke soup.

    Factory convention (verified on the real library): CUT and CREASE are
    two separate solid-color groups — near-black cut outline + red crease
    lines — living in the same region, with artwork strokes all around.
    So: score every ordered pair of color groups where the crease box sits
    inside the cut box and the crease lines are axis-aligned. Falls back to
    the single-group split (dashed = crease, else long interior axis lines)
    for files drawn our own way.
    """
    if not raw or not raw.strokes:
        return None

    by_color: dict = {}
    for s in raw.strokes:
        by_color.setdefault(s.color, []).append(s)

    cands = []
    for color, strokes in by_color.items():
        bb = _bbox(p for s in strokes for p in _stroke_points(s))
        if bb is None or (bb[2] - bb[0]) < 30 or (bb[3] - bb[1]) < 30:
            continue
        lines = [ln for s in strokes for ln in s.lines]
        cubics = [c for s in strokes for c in s.cubics]
        if len(lines) < 4:
            continue
        cands.append({"color": color, "bbox": bb, "lines": lines,
                      "cubics": cubics,
                      "dashed": any(s.dashed for s in strokes)})

    def contains(outer, inner, tol=3.0):
        return (outer[0] - tol <= inner[0] and outer[1] - tol <= inner[1]
                and outer[2] + tol >= inner[2] and outer[3] + tol >= inner[3])

    # --- two-color pairing (the factory convention) --------------------------
    best = None
    best_score = 0.0
    for cut_g in cands:
        for crease_g in cands:
            if crease_g is cut_g:
                continue
            if not contains(cut_g["bbox"], crease_g["bbox"]):
                continue
            axis = _axis_fraction(crease_g["lines"])
            if axis < 0.7:
                continue
            # the crease region must fill most of the cut region (folds span
            # the flat) — rejects small annotation boxes inside artwork
            cw = cut_g["bbox"][2] - cut_g["bbox"][0]
            iw = crease_g["bbox"][2] - crease_g["bbox"][0]
            if iw < 0.4 * cw:
                continue
            score = axis * (len(crease_g["lines"]) + 0.5 * len(cut_g["lines"]))
            if score > best_score:
                best_score = score
                best = (cut_g, crease_g)
    if best:
        cut_g, crease_g = best
        return Linework(
            cut_lines=list(cut_g["lines"]),
            cut_cubics=list(cut_g["cubics"]),
            crease_lines=[ln for ln in crease_g["lines"]
                          if abs(ln[0][0] - ln[1][0]) < 0.35
                          or abs(ln[0][1] - ln[1][1]) < 0.35],
            bbox=cut_g["bbox"],
        )

    # --- single-group fallback (our own files / dashed creases) --------------
    if not cands:
        return None
    group = max(cands, key=lambda g: (g["bbox"][2] - g["bbox"][0])
                * (g["bbox"][3] - g["bbox"][1]))
    x0, y0, x1, y1 = group["bbox"]
    w, h = x1 - x0, y1 - y0
    lw = Linework(bbox=group["bbox"], cut_cubics=list(group["cubics"]))
    eps = 0.35
    strokes = by_color[group["color"]]
    dashed_present = any(s.dashed for s in strokes)
    for s in strokes:
        for a, b in s.lines:
            if dashed_present:
                (lw.crease_lines if s.dashed else lw.cut_lines).append((a, b))
                continue
            vert = abs(a[0] - b[0]) < eps
            horz = abs(a[1] - b[1]) < eps
            length = math.dist(a, b)
            interior = (
                (vert and x0 + eps < a[0] < x1 - eps and length > 0.30 * h)
                or (horz and y0 + eps < a[1] < y1 - eps and length > 0.30 * w)
            )
            (lw.crease_lines if interior else lw.cut_lines).append((a, b))
    if not lw.crease_lines or not lw.cut_lines:
        return None
    return lw


def _cluster(values: list[float], tol: float = 0.8) -> list[float]:
    """Merge near-equal 1D values, sorted."""
    out: list[list[float]] = []
    for v in sorted(values):
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(c) / len(c) for c in out]


def _fold_positions(lines, axis: int, span: float) -> list[float]:
    """Fold coordinates along ``axis`` (0=x verticals, 1=y horizontals).

    Factory files often draw one fold as SEVERAL short segments, so single-
    segment length filters miss them: cluster by position first, then keep
    clusters whose SUMMED length clears the bar."""
    segs = []
    for a, b in lines:
        if abs(a[axis] - b[axis]) < 0.35:
            segs.append((a[axis], math.dist(a, b)))
    if not segs:
        return []
    positions = _cluster([p for p, _ in segs])
    folds = []
    for pos in positions:
        total = sum(length for p, length in segs if abs(p - pos) <= 0.9)
        if total >= max(18.0, 0.20 * span):
            folds.append(pos)
    return folds


def infer_ste_measurements(lw: Linework) -> dict:
    """Recover STE carton ratios from classified linework.

    Returns {"measurements": {...}, "confidence": 0-1, "skip_reason": str}.
    Every field is best-effort; missing pieces stay None and lower the
    confidence rather than failing the file.
    """
    x0, y0, x1, y1 = lw.bbox
    W_total, H_total = x1 - x0, y1 - y0
    result: dict = {"measurements": {}, "confidence": 0.0, "skip_reason": ""}
    m = result["measurements"]

    # fold positions (summed per position — factory folds come in segments)
    vxs = _fold_positions(lw.crease_lines, axis=0, span=H_total)
    hys = _fold_positions(lw.crease_lines, axis=1, span=W_total)
    if len(vxs) < 3:
        result["skip_reason"] = f"only {len(vxs)} vertical fold(s) — not a carton flat"
        return result
    if len(hys) < 2:
        result["skip_reason"] = f"only {len(hys)} horizontal fold(s) — no body band"
        return result

    body_top, body_bottom = min(hys), max(hys)
    edges = [x0] + vxs + [x1]
    widths = [b - a for a, b in zip(edges, edges[1:]) if b - a > 1.5]
    if len(widths) < 4:
        result["skip_reason"] = f"{len(widths)} panels — expected 4-5 for STE"
        return result

    # identify W (the two most-equal large panels) and D (two small equal)
    ordered = sorted(widths, reverse=True)
    W_pair = ordered[:2]
    D_candidates = [w for w in ordered[2:] if w > 3.0]
    if abs(W_pair[0] - W_pair[1]) > 0.08 * W_pair[0] or not D_candidates:
        result["skip_reason"] = "panel widths don't match the STE W/D pattern"
        return result
    W = sum(W_pair) / 2.0
    D_pair = D_candidates[:2]
    D = sum(D_pair) / len(D_pair)
    glue = min(widths)
    m["W_mm"] = round(W, 2)
    m["D_mm"] = round(D, 2)
    m["glue_tab_mm"] = round(glue, 2)
    m["body_height_mm"] = round(body_bottom - body_top, 2)

    # tuck flap: cut geometry above the body over one W-panel column
    # (the taller of the two above-body cut regions is the tuck)
    def region_height(cx_lo, cx_hi):
        # strict interior: flap side lines sit exactly ON the fold x — an
        # inclusive bound would count the tuck's sides into the dust columns
        lo, hi = cx_lo + 0.3, cx_hi - 0.3
        ys = [p[1] for a, b in lw.cut_lines for p in (a, b)
              if lo < p[0] < hi and p[1] < body_top - 0.2]
        ys += [p[1] for c in lw.cut_cubics for p in c
               if lo < p[0] < hi and p[1] < body_top - 0.2]
        return (body_top - min(ys)) if ys else 0.0

    col_edges = list(zip(edges, edges[1:]))
    tuck_col = None
    tuck_h = 0.0
    for lo, hi in col_edges:
        if abs((hi - lo) - W) > 0.08 * W:
            continue
        h = region_height(lo, hi)
        if h > tuck_h:
            tuck_h, tuck_col = h, (lo, hi)
    if tuck_col and tuck_h > 2.0:
        m["tuck_total_over_W"] = round(tuck_h / W, 4)
        # tip width → inset: horizontal cut lines near the flap tip
        tip_y = body_top - tuck_h
        tips = [(a, b) for a, b in lw.cut_lines
                if abs(a[1] - b[1]) < 0.35
                and abs(a[1] - tip_y) < 0.15 * tuck_h
                and tuck_col[0] - 1 <= min(a[0], b[0])
                and max(a[0], b[0]) <= tuck_col[1] + 1]
        if tips:
            tip_w = max(abs(a[0] - b[0]) for a, b in tips)
            m["tuck_inset_over_W"] = round(((W - tip_w) / 2.0) / W, 4)
        # shoulder curve: cubic segments in the tuck region
        shoulder = [c for c in lw.cut_cubics
                    if all(tuck_col[0] - 1 <= p[0] <= tuck_col[1] + 1
                           and p[1] <= body_top + 0.5 for p in c)]
        if shoulder:
            heights = [abs(c[0][1] - c[3][1]) for c in shoulder]
            curve_h = max(heights)
            if curve_h > 0.3:
                m["tuck_curve_over_W"] = round(curve_h / W, 4)
                c = shoulder[heights.index(curve_h)]
                dy = abs(c[3][1] - c[0][1])
                dx = abs(c[3][0] - c[0][0])
                if dy > 0.3:
                    m["shoulder_k_v"] = round(abs(c[1][1] - c[0][1]) / dy, 4)
                if dx > 0.3:
                    m["shoulder_k_h"] = round(abs(c[2][0] - c[3][0]) / dx, 4)

    # dust flaps: above-body cut height over a D-panel column
    dust_hs = []
    for lo, hi in col_edges:
        if abs((hi - lo) - D) > max(0.12 * D, 1.0):
            continue
        h = region_height(lo, hi)
        if h > 1.0:
            dust_hs.append(h)
    if dust_hs:
        m["dust_over_D"] = round(max(dust_hs) / D, 4)

    found = sum(1 for v in m.values() if v is not None)
    result["confidence"] = round(min(1.0, found / 8.0), 2)
    return result


# --- per-file + aggregate ------------------------------------------------------

def measure_file(path: str) -> dict:
    """One file → report dict. Never raises."""
    import os
    report = {"file": os.path.basename(path), "ok": False,
              "skip_reason": "", "measurements": {}, "confidence": 0.0}
    try:
        raw = extract_vector_drawing(path)
        if raw is None or not raw.strokes:
            report["skip_reason"] = "no stroked vector paths (raster or artwork-only)"
            return report
        lw = classify_linework(raw)
        if lw is None:
            report["skip_reason"] = "no dieline linework found (cut+crease)"
            return report
        inferred = infer_ste_measurements(lw)
        report.update(inferred)
        report["ok"] = bool(inferred["measurements"]) and not inferred["skip_reason"]
    except RuntimeError:
        raise                                        # missing PyMuPDF — surface it
    except Exception as exc:  # noqa: BLE001 — per-file, keep the batch going
        report["skip_reason"] = f"error: {exc}"
    return report


_RATIO_KEYS = ("tuck_total_over_W", "tuck_inset_over_W", "tuck_curve_over_W",
               "dust_over_D", "shoulder_k_v", "shoulder_k_h")

_ENGINE_CURRENT = {
    "tuck_total_over_W": 1.227,
    "tuck_inset_over_W": 0.227,
    "tuck_curve_over_W": 0.218,
    "dust_over_D": 0.631,
    "shoulder_k_v": 0.5523,
    "shoulder_k_h": 0.5523,
}


def aggregate(reports: list[dict]) -> dict:
    """Medians + spread per ratio across the measured files."""
    import statistics

    usable = [r for r in reports if r.get("ok")]
    summary: dict = {
        "files_total": len(reports),
        "files_measured": len(usable),
        "coverage": round(len(usable) / len(reports), 2) if reports else 0.0,
        "ratios": {},
    }
    for key in _RATIO_KEYS:
        values = [r["measurements"][key] for r in usable
                  if r["measurements"].get(key) is not None]
        if not values:
            continue
        med = statistics.median(values)
        mad = statistics.median([abs(v - med) for v in values])
        summary["ratios"][key] = {
            "n": len(values),
            "median": round(med, 4),
            "mad": round(mad, 4),
            "engine_current": _ENGINE_CURRENT.get(key),
            # Adoption gate: a factory convention shows up as a TIGHT cluster.
            # Scattered values mean the measured flats aren't the same
            # template family — do not move engine constants from them.
            "consistent": bool(
                len(values) >= 5 and (mad <= 0.02 or mad <= 0.08 * abs(med))
            ),
        }
    return summary
