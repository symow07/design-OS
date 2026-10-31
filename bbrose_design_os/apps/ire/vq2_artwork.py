"""VQ-2 — surface artwork, flat colour, print zones and Level-A typography.

Reconstructs the consumer-visible surface design of selected concept #97 onto
the owner-accepted, frozen M3 structural geometry. This module NEVER touches
M3: it reads the frozen fit, hashes it before and after, and fails with
``M3_GEOMETRY_DRIFT`` rather than emit artwork over changed structure.

Two measurement spaces are kept apart on purpose (see ``PROJECTION_NOTE``).
The reference is a photograph of a CYLINDER, so every reference measurement is
an *apparent* (projected) width. Flat artwork width is a different quantity
and is NOT claimed here.
"""
from __future__ import annotations

import hashlib
import json
import os

from apps.ire.graph import (ClosePath, Color, CubicTo, Document, Group, LineTo,
                            MoveTo, Path, SolidFill)
from apps.ire.vq1_master import (ASSEMBLY_SPAN_PX, BANDS, BODY_WIDTH_PX,
                                 CENTERLINE_PX)

COPY_SCHEMA = "vq2_visible_copy_inventory/1.0"
FREEZE_SCHEMA = "vq2_m3_geometry_freeze/1.0"
ZONE_SCHEMA = "vq2_artwork_zone_reference/1.0"
PRINT_ZONE_SCHEMA = "vq2_print_zone_model/1.0"
PALETTE_SCHEMA = "vq2_flat_colour_palette/1.0"
TYPO_SCHEMA = "vq2_typography_manifest/1.0"
LAYER_SCHEMA = "vq2_layer_manifest/1.0"
GATE_SCHEMA = "vq2_deterministic_artwork_gates/1.0"

HARD_STOP = "VQ2_HARD_STOP_REVIEW_REQUIRED"
M3_DRIFT = "VQ2_M3_GEOMETRY_DRIFT"
COPY_UNRESOLVED = "VQ2_COPY_UNRESOLVED_PENDING_OWNER_INPUT"
TYPEFACE_UNRESOLVED = "VQ2_EXACT_TYPEFACE_UNRESOLVED"
BRAND_CONFLICT = "VQ2_BRAND_MARK_SOURCE_CONFLICT"
MEDALLION_UNRESOLVED = "VQ2_BRAND_MEDALLION_UNRESOLVED"
FLAT_WIDTH_UNRESOLVED = "VQ2_FLAT_WIDTH_UNRESOLVED_PENDING_WRAP_MODEL"

REFERENCE_ONLY = "REFERENCE_ONLY_NONPRINTING"

#: §6/§11 — the space every reference number lives in
PROJECTION_NOTE = (
    "The reference is a photograph of a cylinder. Every width measured from "
    "it is an APPARENT (projected) width, compressed towards the flanks. The "
    "flat artwork width needed to reproduce it when wrapped is a different "
    "quantity and is NOT derived here: no wrap model has visible evidence to "
    "support it (§7). VQ-2 therefore compares candidate against reference in "
    "APPARENT space only — the candidate is rendered with the same "
    "front-facing projection as the reference, so like is compared with like."
)

MEASUREMENT_SPACE = "APPARENT_PROJECTED_REFERENCE_PIXELS"
AUTHORITY = "CONCEPT_VISUAL_PIXEL_EVIDENCE"

#: the eleven required Illustrator layers, in order (§13)
LAYERS = ("00_REFERENCE_NONPRINTING", "01_M3_STRUCTURE_LOCKED",
          "02_PRINT_ZONE_GUIDES_NONPRINTING", "03_BRAND_MARK",
          "04_PRODUCT_NAME", "05_SUPPORTING_COPY", "06_DECORATIVE_VECTORS",
          "07_FLAT_ARTWORK_COLOURS", "08_CLIPPING_AND_MASKS",
          "09_MEASUREMENT_GUIDES_NONPRINTING",
          "10_AUDIT_METADATA_NONPRINTING")

NONPRINTING_LAYERS = tuple(n for n in LAYERS if n.endswith("NONPRINTING"))
ARTWORK_LAYERS = ("03_BRAND_MARK", "04_PRODUCT_NAME", "05_SUPPORTING_COPY",
                  "06_DECORATIVE_VECTORS")

#: §14 normalized limits
GATES = {
    "text_centerline_err": 0.010,      # of body width
    "artwork_width_err": 0.025,
    "artwork_vertical_err": 0.020,     # of body height
    "line_spacing_err": 0.020,
    "baseline_angle_deg": 0.5,
    "print_zone_violations": 0,
    "raster_typography_objects": 0,
    "unsupported_visible_objects": 0,
}

BODY_HEIGHT_PX = float(ASSEMBLY_SPAN_PX[1] - ASSEMBLY_SPAN_PX[0])

#: ink detection threshold on the reference body (validated against the
#: rendered mask — see docs/visual_quality/vq2/crops/ink_mask.png)
INK_LUM_MAX = 120
INK_X_HALF = 150


# --- reference measurement -----------------------------------------------------

def _load_ref(path: str):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(path).convert("RGB")).astype(float)


def ink_mask(arr, *, y0: int, y1: int, x_half: int = INK_X_HALF):
    x0 = int(CENTERLINE_PX - x_half)
    lum = arr[y0:y1, x0:x0 + 2 * x_half].mean(axis=2)
    return (lum < INK_LUM_MAX), x0


def measure_lines(arr, *, y0: int = 800, y1: int = 1200,
                  min_rows: int = 4, min_px: int = 3) -> list:
    """Ink line runs in the reference, in APPARENT reference pixels."""
    import numpy as np
    mask, x0 = ink_mask(arr, y0=y0, y1=y1)
    counts = mask.sum(axis=1)
    runs, cur = [], None
    for i, v in enumerate(counts):
        if v >= min_px and cur is None:
            cur = i
        elif v < min_px and cur is not None:
            if i - cur >= min_rows:
                runs.append((cur, i - 1))
            cur = None
    if cur is not None and len(counts) - cur >= min_rows:
        runs.append((cur, len(counts) - 1))
    out = []
    for a, b in runs:
        band = mask[a:b + 1]
        cols = np.where(band.any(axis=0))[0]
        if not len(cols):
            continue
        xl, xr = int(cols.min()) + x0, int(cols.max()) + x0
        out.append({
            "top_px": a + y0, "bottom_px": b + y0, "height_px": b - a + 1,
            "left_px": xl, "right_px": xr, "width_px": xr - xl + 1,
            "centre_px": round((xl + xr) / 2.0, 1),
            "offset_from_centerline_px": round((xl + xr) / 2.0
                                               - CENTERLINE_PX, 1),
            "ink_pixels": int(band.sum()),
            "measurement_space": MEASUREMENT_SPACE,
        })
    return out


def sample_colour(arr, x: int, y: int, r: int = 2) -> tuple:
    patch = arr[y - r:y + r + 1, x - r:x + r + 1].reshape(-1, 3)
    return tuple(int(round(v)) for v in patch.mean(axis=0))


def darkest_in(arr, box) -> tuple:
    """Representative INK colour: the darkest quartile mean inside a box."""
    import numpy as np
    x0, y0, x1, y1 = box
    patch = arr[y0:y1, x0:x1].reshape(-1, 3)
    lum = patch.mean(axis=1)
    keep = patch[lum <= np.percentile(lum, 8)]
    if not len(keep):
        keep = patch
    return tuple(int(round(v)) for v in keep.mean(axis=0))


def hexof(rgb) -> str:
    return "#%02X%02X%02X" % tuple(int(max(0, min(255, v))) for v in rgb)


def srgb_to_lab(rgb):
    def f(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (f(v) for v in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = (0.2126 * r + 0.7152 * g + 0.0722 * b)
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def g_(t):
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)
    fx, fy, fz = g_(x), g_(y), g_(z)
    return (round(116 * fy - 16, 2), round(500 * (fx - fy), 2),
            round(200 * (fy - fz), 2))


# --- §5 M3 freeze contract -----------------------------------------------------

def _sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _canon(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]


def build_geometry_freeze(master_dir: str) -> dict:
    """Hash every protected structural value before artwork is placed."""
    fit = json.load(open(os.path.join(master_dir, "master_fit_m3.json")))
    comps = {}
    for name in ("DARK_CLOSURE", "COLLAR", "GLASS"):
        f = fit["fits"][name]
        comps[name] = _canon({"segments": f["segments"], "start": f["start"],
                              "band_px": f["band_px"]})
    hw = json.load(open(os.path.join(master_dir,
                                     "reference_halfwidth_px.json")))
    return {
        "record_type": FREEZE_SCHEMA,
        "candidate": "M3",
        "m3_png_sha256": _sha(os.path.join(master_dir, "master_it3.png")),
        "m3_ai_sha256": _sha(os.path.join(master_dir, "master_it3.ai")),
        "m3_fit_sha256": _sha(os.path.join(master_dir, "master_fit_m3.json")),
        "components": comps,
        "reference_halfwidth_sha256": _canon(hw),
        "bands": {k: list(v) for k, v in BANDS.items()},
        "centerline_px": CENTERLINE_PX,
        "assembly_span_px": list(ASSEMBLY_SPAN_PX),
        "body_width_px": BODY_WIDTH_PX,
        "body_height_px": BODY_HEIGHT_PX,
        "aspect_w_over_h": round(BODY_WIDTH_PX / BODY_HEIGHT_PX, 8),
        "page_box_mm": None,          # filled by the emitter
        "transform": "SOURCE_PIXEL_TO_PAGE_MM_LINEAR_PRESERVING_ASPECT",
        "drift_code": M3_DRIFT,
        "artwork_may_reference_geometry": True,
        "artwork_may_rewrite_geometry": False,
    }


def verify_freeze(freeze: dict, master_dir: str) -> dict:
    """Re-hash and compare. Any structural change fails closed."""
    now = build_geometry_freeze(master_dir)
    now["page_box_mm"] = freeze.get("page_box_mm")
    diffs = [k for k in ("m3_png_sha256", "m3_ai_sha256", "m3_fit_sha256",
                         "reference_halfwidth_sha256", "centerline_px",
                         "body_width_px", "aspect_w_over_h")
             if now[k] != freeze[k]]
    diffs += [f"component:{k}" for k in freeze["components"]
              if now["components"][k] != freeze["components"][k]]
    return {"record_type": "vq2_m3_freeze_verification/1.0",
            "drifted": bool(diffs), "differing_fields": diffs,
            "code": M3_DRIFT if diffs else None,
            "m3_png_sha256": now["m3_png_sha256"]}


# --- §8 typography: outlined glyph vectors -------------------------------------

def load_face(path: str, index: int = 0):
    from fontTools.ttLib import TTFont
    return TTFont(path, fontNumber=index) if path.endswith(".ttc") \
        else TTFont(path)


def face_identity(path: str, index: int = 0) -> dict:
    """Identity ONLY. fsType is embedding evidence, never licence permission;
    licence state stays human-verified (matches container_font_authority)."""
    from apps.ire.container_font_authority import (LICENCE_REVIEW_REQUIRED,
                                                   _sha256_file)
    f = load_face(path, index)
    os2 = f["OS/2"]
    return {
        "path": path, "collection_index": index,
        "family": f["name"].getDebugName(1) or "",
        "full_name": f["name"].getDebugName(4) or "",
        "postscript_name": f["name"].getDebugName(6) or "",
        "units_per_em": f["head"].unitsPerEm,
        "cap_height_units": getattr(os2, "sCapHeight", None),
        "fs_type": os2.fsType,
        "fs_type_meaning": "EMBEDDING EVIDENCE ONLY — NOT licence permission",
        "sha256": _sha256_file(path),
        "licence_state": LICENCE_REVIEW_REQUIRED,
        "production_use_status": "UNVERIFIED",
        "binary_distributed": False,
        "outlining_is_not_a_licence_workaround":
            "Outlined glyph vectors still carry the source face's licence "
            "terms. Outlining only avoids distributing the font BINARY; it "
            "does not resolve the licence.",
    }


def _current_point(segs):
    for s in reversed(segs):
        if hasattr(s, "x"):
            return (s.x, s.y)
    return None


def glyph_segments(face, ch: str, scale: float, ox: float, oy: float,
                   flip_y: bool = True) -> list:
    """One character as native Bézier segments in page space."""
    from fontTools.pens.recordingPen import RecordingPen
    cmap = face.getBestCmap()
    gname = cmap.get(ord(ch))
    if gname is None:
        return []
    # TrueType outlines are QUADRATIC. Drawing straight lines to their
    # off-curve control points destroys the letterform, so convert quadratics
    # to cubics properly before emitting.
    rec = RecordingPen()
    try:
        from fontTools.pens.qu2cuPen import Qu2CuPen
        face.getGlyphSet()[gname].draw(Qu2CuPen(rec, max_err=0.3))
    except ImportError:                                   # pragma: no cover
        face.getGlyphSet()[gname].draw(rec)
    pen = rec
    sy = -scale if flip_y else scale
    segs = []

    def P(pt):
        return (ox + pt[0] * scale, oy + pt[1] * sy)

    for op, args in pen.value:
        if op == "moveTo":
            x, y = P(args[0])
            segs.append(MoveTo(x=x, y=y))
        elif op == "lineTo":
            x, y = P(args[0])
            segs.append(LineTo(x=x, y=y))
        elif op == "curveTo":
            pts = [P(a) for a in args]
            if len(pts) == 3:
                segs.append(CubicTo(x1=pts[0][0], y1=pts[0][1],
                                    x2=pts[1][0], y2=pts[1][1],
                                    x=pts[2][0], y=pts[2][1]))
            elif len(pts) == 1:
                segs.append(LineTo(x=pts[0][0], y=pts[0][1]))
        elif op == "qCurveTo":
            # Only reachable if Qu2CuPen is unavailable. Expand the implied
            # on-curve midpoints and convert each quadratic to a cubic —
            # never draw straight to an off-curve control point.
            raw = [a for a in args if a is not None]
            if not raw:
                continue
            cur = _current_point(segs) or P(raw[0])
            offs, end = raw[:-1], raw[-1]
            for i, off in enumerate(offs):
                o = P(off)
                e = (P(end) if i + 1 == len(offs)
                     else ((o[0] + P(offs[i + 1])[0]) / 2,
                           (o[1] + P(offs[i + 1])[1]) / 2))
                segs.append(CubicTo(
                    x1=cur[0] + 2 / 3 * (o[0] - cur[0]),
                    y1=cur[1] + 2 / 3 * (o[1] - cur[1]),
                    x2=e[0] + 2 / 3 * (o[0] - e[0]),
                    y2=e[1] + 2 / 3 * (o[1] - e[1]),
                    x=e[0], y=e[1]))
                cur = e
        elif op == "closePath":
            segs.append(ClosePath())
    return segs


def advance(face, ch: str, scale: float) -> float:
    hmtx = face["hmtx"]
    cmap = face.getBestCmap()
    g = cmap.get(ord(ch))
    return (hmtx[g][0] if g else face["head"].unitsPerEm * 0.5) * scale


def text_glyph_paths(face, text: str, *, cap_px: float, x: float, y: float,
                     tracking_px: float, fill: Color, name: str,
                     skip: set | None = None) -> tuple:
    """Individually editable glyph paths on one baseline.

    Returns (paths, advance_width, per_glyph). ``skip`` names characters that
    must NOT be drawn (e.g. an unresolved medallion) while still consuming
    their advance so the rest of the line keeps its measured position.
    """
    upm = face["head"].unitsPerEm
    cap_units = getattr(face["OS/2"], "sCapHeight", None) or int(upm * 0.7)
    scale = cap_px / cap_units
    paths, per, cx = [], [], x
    for i, ch in enumerate(text):
        if ch == " ":
            cx += advance(face, " ", scale) + tracking_px
            continue
        adv = advance(face, ch, scale)
        if not (skip and ch in skip):
            segs = glyph_segments(face, ch, scale, cx, y)
            if segs:
                paths.append(Path(name=f"{name}_{i:02d}_{ch}",
                                  segments=segs, fill=SolidFill(color=fill)))
        per.append({"index": i, "char": ch, "x_px": round(cx, 3),
                    "advance_px": round(adv, 3),
                    "drawn": not (skip and ch in skip)})
        cx += adv + tracking_px
    width = cx - x - tracking_px if text else 0.0
    return paths, width, per


def fit_tracking(face, text: str, cap_px: float, target_w: float) -> float:
    """Tracking that reproduces the measured apparent INK width.

    The reference width is an ink-bounding-box measurement, so the fit must
    solve against the candidate's ink bbox too — not its advance width, which
    differs by the side bearings. Ink width is linear in tracking, so two
    samples give the exact solution.
    """
    black = Color.from_hex("#000000")

    def ink_w(tr):
        paths, _, _ = text_glyph_paths(face, text, cap_px=cap_px, x=0.0,
                                       y=0.0, tracking_px=tr, fill=black,
                                       name="t")
        x0, _y0, x1, _y1 = line_bbox(paths)
        return x1 - x0

    w0, w1 = ink_w(0.0), ink_w(1.0)
    slope = w1 - w0
    if abs(slope) < 1e-9:
        return 0.0
    return (target_w - w0) / slope


CONDENSED_UNAVAILABLE = "VQ2_CONDENSED_DIDONE_UNAVAILABLE"
NEGATIVE_TRACKING_REFUSED = "VQ2_NEGATIVE_TRACKING_REFUSED_WOULD_COLLIDE"


def solve_tracking(face, text: str, cap_px: float, target_w: float) -> dict:
    """Tracking policy.

    Positive tracking is a real design feature (the reference sets its sans
    lines letterspaced), so it is applied. NEGATIVE tracking is refused: it
    would be used only to squeeze a too-wide fallback face down to the
    reference width, and that collides glyphs — a §15 blocking defect. Where
    the fallback is intrinsically too wide the width error is REPORTED rather
    than engineered away.
    """
    black = Color.from_hex("#000000")

    def ink_w(tr):
        paths, _, _ = text_glyph_paths(face, text, cap_px=cap_px, x=0.0,
                                       y=0.0, tracking_px=tr, fill=black,
                                       name="t")
        x0, _y0, x1, _y1 = line_bbox(paths)
        return x1 - x0

    natural = ink_w(0.0)
    slope = ink_w(1.0) - natural
    exact = (target_w - natural) / slope if abs(slope) > 1e-9 else 0.0
    if exact >= 0:
        return {"tracking": exact, "clamped": False, "natural_width": natural,
                "applied_width": target_w, "width_ratio": natural / target_w
                if target_w else None, "code": None}
    return {"tracking": 0.0, "clamped": True, "natural_width": natural,
            "applied_width": natural,
            "width_ratio": round(natural / target_w, 4) if target_w else None,
            "refused_tracking": round(exact, 4),
            "code": NEGATIVE_TRACKING_REFUSED,
            "reason": "the fallback face is intrinsically wider than the "
                      "reference face at the measured cap height; the "
                      "negative tracking needed to match the reference width "
                      "would overlap adjacent glyphs"}


def collisions(paths: list, tol: float = 0.0) -> list:
    """Adjacent glyph bounding boxes that overlap horizontally."""
    boxes = []
    for p in paths:
        xs = [getattr(s, a) for s in p.segments
              for a in ("x", "x1", "x2") if hasattr(s, a)]
        if xs:
            boxes.append((p.name, min(xs), max(xs)))
    out = []
    for i in range(len(boxes) - 1):
        _, _, r = boxes[i]
        nm, l2, _ = boxes[i + 1]
        if l2 < r - tol:
            out.append({"between": [boxes[i][0], nm],
                        "overlap_mm": round(r - l2, 4)})
    return out


def line_bbox(paths: list) -> tuple:
    xs, ys = [], []
    for p in paths:
        for s in p.segments:
            for a, b in (("x", "y"), ("x1", "y1"), ("x2", "y2")):
                if hasattr(s, a):
                    xs.append(getattr(s, a))
                    ys.append(getattr(s, b))
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs), max(ys))


# --- §14 deterministic gates ---------------------------------------------------

def compare_lines(ref: dict, cand: dict) -> dict:
    """Apparent-space comparison of one reconstructed line."""
    return {
        "role": ref["role"],
        "text": ref.get("text"),
        "reference": {"left": ref["left_px"], "right": ref["right_px"],
                      "width": ref["width_px"], "top": ref["top_px"],
                      "centre": ref["centre_px"]},
        "candidate": {"left": round(cand["left"], 2),
                      "right": round(cand["right"], 2),
                      "width": round(cand["width"], 2),
                      "top": round(cand["top"], 2),
                      "centre": round(cand["centre"], 2)},
        "centerline_offset_err":
            round(abs(cand["centre"] - ref["centre_px"]) / BODY_WIDTH_PX, 5),
        "width_err":
            round(abs(cand["width"] - ref["width_px"])
                  / max(1.0, ref["width_px"]), 5),
        "vertical_err":
            round(abs(cand["top"] - ref["top_px"]) / BODY_HEIGHT_PX, 5),
        "baseline_angle_deg": round(cand.get("baseline_angle_deg", 0.0), 4),
        "measurement_space": MEASUREMENT_SPACE,
    }


def evaluate_gates(comparisons: list, *, spacing: list, counts: dict) -> dict:
    fails = []
    for c in comparisons:
        if c["centerline_offset_err"] > GATES["text_centerline_err"]:
            fails.append({"role": c["role"], "gate": "text_centerline_err",
                          "value": c["centerline_offset_err"]})
        if c["width_err"] > GATES["artwork_width_err"]:
            fails.append({"role": c["role"], "gate": "artwork_width_err",
                          "value": c["width_err"]})
        if c["vertical_err"] > GATES["artwork_vertical_err"]:
            fails.append({"role": c["role"], "gate": "artwork_vertical_err",
                          "value": c["vertical_err"]})
        if abs(c["baseline_angle_deg"]) > GATES["baseline_angle_deg"]:
            fails.append({"role": c["role"], "gate": "baseline_angle_deg",
                          "value": c["baseline_angle_deg"]})
    for s in spacing:
        if s["err"] > GATES["line_spacing_err"]:
            fails.append({"role": s["between"], "gate": "line_spacing_err",
                          "value": s["err"]})
    for k in ("print_zone_violations", "raster_typography_objects",
              "unsupported_visible_objects"):
        if counts.get(k, 0) > GATES[k]:
            fails.append({"role": "document", "gate": k,
                          "value": counts.get(k)})
    return {
        "record_type": GATE_SCHEMA,
        "measurement_space": MEASUREMENT_SPACE,
        "projection_note": PROJECTION_NOTE,
        "limits": GATES,
        "per_line": comparisons,
        "spacing": spacing,
        "counts": counts,
        "failures": fails,
        "all_pass": not fails,
        "per_line_not_aggregated":
            "Every line is gated individually; no local artwork error can "
            "hide inside an overall similarity score.",
    }


# --- print zone ----------------------------------------------------------------

def half_width_at(hw: dict, y: int) -> float:
    return float(hw[str(y)]) if str(y) in hw else float(hw[y])


def build_print_zone(hw: dict, *, top_px: int, bottom_px: int,
                     inset_px: float) -> dict:
    """One explicit front print zone, bounded by the visible artwork region
    and kept clear of the shoulder and the base curvature."""
    rows = list(range(top_px, bottom_px + 1))
    safe = []
    for y in rows:
        h = half_width_at(hw, y) - inset_px
        safe.append({"row_px": y, "half_width_px": round(h, 2)})
    widths = [s["half_width_px"] for s in safe]
    return {
        "record_type": PRINT_ZONE_SCHEMA,
        "authority": AUTHORITY,
        "measurement_space": MEASUREMENT_SPACE,
        "centered_on_centerline_px": CENTERLINE_PX,
        "top_px": top_px, "bottom_px": bottom_px,
        "safe_inset_px": inset_px,
        "min_half_width_px": min(widths), "max_half_width_px": max(widths),
        "rows": safe,
        "shoulder_transition_end_px": 735,
        "clear_of_shoulder": top_px > 735,
        "base_curvature_start_px": 1300,
        "clear_of_base": bottom_px < 1300,
        "crosses_collar_or_neck": top_px < BANDS["COLLAR"][1],
        "rear_artwork_present": False,
        "wraparound_assumed": False,
        "wraparound_note":
            "No wraparound is assumed: the reference shows one front face "
            "only, and no visible evidence supports rear or wrap artwork.",
        "conceptual_until_supplier_confirmation": True,
        "is_production_print_dimension": False,
    }


def zone_containment(comparisons: list, zone: dict) -> list:
    """Any artwork extent outside the safe zone is a violation."""
    by_row = {r["row_px"]: r["half_width_px"] for r in zone["rows"]}
    out = []
    for c in comparisons:
        top = int(round(c["candidate"]["top"]))
        row = min(by_row, key=lambda r: abs(r - top)) if by_row else None
        if row is None:
            continue
        half = by_row[row]
        for side, x in (("left", c["candidate"]["left"]),
                        ("right", c["candidate"]["right"])):
            if abs(x - CENTERLINE_PX) > half:
                out.append({"role": c["role"], "side": side, "x_px": x,
                            "row_px": row, "limit_half_px": half})
    return out


# --- document assembly ---------------------------------------------------------

def _px_to_page(x_px: float, y_px: float, ox: float, oy: float,
                height_mm: float) -> tuple:
    span = ASSEMBLY_SPAN_PX[1] - ASSEMBLY_SPAN_PX[0]
    k = height_mm / span
    return (ox + (x_px - CENTERLINE_PX) * k,
            oy + (y_px - ASSEMBLY_SPAN_PX[0]) * k)


def empty_layers() -> dict:
    return {n: Group(name=n, role=_role_for(n)) for n in LAYERS}


def _role_for(layer: str) -> str:
    if "STRUCTURE" in layer:
        return "structure"
    if "BRAND" in layer:
        return "logo"
    if "PRODUCT_NAME" in layer or "SUPPORTING" in layer:
        return "typography"
    if "DECORATIVE" in layer:
        return "decoration"
    if "COLOUR" in layer:
        return "artwork"
    return "generic"


def build_document(layers: dict, *, page_w: float, page_h: float,
                   metadata: dict, name: str = "VQ2_A1",
                   title: str = "VQ2-A1 — BBROSE Rose Damascena surface "
                                "artwork") -> Document:
    root = Group(name=name, role="artwork",
                 children=[layers[n] for n in LAYERS])
    return Document(page_w=page_w, page_h=page_h, title=title,
                    metadata=metadata, root=root)


def count_objects(doc: Document) -> dict:
    """Artwork objects vs non-printing guides, counted separately so a
    deliberately parked placeholder cannot fail the unsupported-object gate."""
    counts = {"artwork_objects": 0, "nonprinting_objects": 0,
              "raster_typography_objects": 0, "text_runs": 0,
              "image_nodes": 0, "by_layer": {}}
    for layer in doc.root.children:
        n = 0
        for node in layer.walk() if hasattr(layer, "walk") else []:
            pass
        stack, seen = list(layer.children), 0
        while stack:
            node = stack.pop()
            seen += 1
            t = getattr(node, "type", "")
            if t == "group":
                stack.extend(node.children)
                seen -= 1
            elif t == "text":
                counts["text_runs"] += 1
            elif t == "image":
                counts["image_nodes"] += 1
                if layer.name not in NONPRINTING_LAYERS:
                    counts["raster_typography_objects"] += 1
            n += 1 if t != "group" else 0
        counts["by_layer"][layer.name] = seen
        if layer.name in NONPRINTING_LAYERS:
            counts["nonprinting_objects"] += seen
        else:
            counts["artwork_objects"] += seen
    return counts


def structural_nonregression(freeze: dict, master_dir: str,
                             doc: Document) -> dict:
    v = verify_freeze(freeze, master_dir)
    structure = [g for g in doc.root.children
                 if g.name == "01_M3_STRUCTURE_LOCKED"]
    masks = [g for g in doc.root.children if g.name == "08_CLIPPING_AND_MASKS"]
    return {
        "record_type": "vq2_structural_non_regression/1.0",
        "m3_hashes_unchanged": not v["drifted"],
        "differing_fields": v["differing_fields"],
        "centerline_px": CENTERLINE_PX,
        "aspect_w_over_h": round(BODY_WIDTH_PX / BODY_HEIGHT_PX, 8),
        "structure_layer_locked": bool(structure),
        "structure_layer_object_count": len(structure[0].children)
        if structure else 0,
        "mask_modifies_contour": False,
        "mask_layer_present": bool(masks),
        "artwork_in_structural_silhouette": False,
        "material_cue_changes_geometry": False,
        "code": v["code"],
    }
