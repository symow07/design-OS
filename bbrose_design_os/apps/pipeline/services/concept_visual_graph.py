"""Deterministic visual decomposition of the selected Gate-1 render
(2A-6E-CORR-8 §3) — selected_concept_visual_graph/1.0.

Bounded, local, provider-free pixel analysis of the approved concept image:
estimates the front-panel region, the blush product-name block, the logo
zone, the rose-gold constellation's bounding region / centroid / density
grid, color-area proportions and whitespace distribution. The output is a
set of STRUCTURAL RELATIONSHIPS the geometry gate compares against emitted
vector geometry — pixel similarity is never a production criterion.

Honesty: an embossed ivory-on-ivory element (the POWDER line of image 89)
is not reliably separable by deterministic color analysis; such elements are
recorded as NOT_DETECTABLE_DETERMINISTICALLY and their relationships come
from the variation's structured record instead.
"""
from __future__ import annotations

VISUAL_GRAPH_SCHEMA = "selected_concept_visual_graph/1.0"


def _load_rgb(path, max_side=900):
    from PIL import Image
    import numpy as np
    with Image.open(path) as im:
        im = im.convert("RGB")
        scale = max(im.size) / max_side
        if scale > 1:
            im = im.resize((int(im.width / scale), int(im.height / scale)))
        return np.asarray(im).astype("float32") / 255.0


def _bbox_of_mask(mask):
    import numpy as np
    ys, xs = np.nonzero(mask)
    if len(xs) < 20:
        return None
    return (int(xs.min()), int(ys.min()),
            int(xs.max() - xs.min()), int(ys.max() - ys.min()))


def build_visual_graph(image_path: str, variation: dict | None = None) -> dict:
    import numpy as np

    rgb = _load_rgb(image_path)
    h, w, _ = rgb.shape
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    luminance = 0.299 * r + 0.587 * g + 0.114 * b

    # --- front panel: the largest bright (ivory) region ---------------------
    bright = luminance > 0.72
    col_hits = bright.sum(axis=0) > h * 0.25
    row_hits = bright.sum(axis=1) > w * 0.20
    xs = np.nonzero(col_hits)[0]
    ys = np.nonzero(row_hits)[0]
    if len(xs) < 10 or len(ys) < 10:
        return {"schema_version": VISUAL_GRAPH_SCHEMA,
                "panel_detected": False}
    px0, px1 = int(xs[0]), int(xs[-1])
    py0, py1 = int(ys[0]), int(ys[-1])
    pw, ph = px1 - px0, py1 - py0

    def rel(box):
        if box is None:
            return None
        return {"x": round((box[0] - px0) / pw, 3),
                "y": round((box[1] - py0) / ph, 3),
                "w": round(box[2] / pw, 3), "h": round(box[3] / ph, 3)}

    panel = (slice(py0, py1), slice(px0, px1))
    pr, pg, pb = r[panel], g[panel], b[panel]
    p_lum = luminance[panel]

    # --- blush name block (BAKED): saturated pink, mid-tone -----------------
    pinkness = pr - (pg + pb) / 2.0
    blush_text = (pinkness > 0.10) & (p_lum > 0.45) & (p_lum < 0.85)
    # restrict to the upper 70% (the constellation lives lower-right)
    blush_upper = blush_text.copy()
    blush_upper[int(0.62 * ph):, :] = False
    blush_upper[:, int(0.60 * pw):] = False
    name_box = _bbox_of_mask(blush_upper)
    if name_box:
        name_box = (name_box[0] + px0, name_box[1] + py0,
                    name_box[2], name_box[3])

    # --- rose-gold constellation: pink/tan accents, lower-right biased ------
    accent = (pinkness > 0.045) & (p_lum > 0.5) & (p_lum < 0.92)
    accent[: int(0.35 * ph), :] = False       # exclude logo + name zone
    accent[:, : int(0.30 * pw)] = False
    const_box = _bbox_of_mask(accent)
    density_grid = []
    total_accent = max(1, int(accent.sum()))
    for gy in range(4):
        row = []
        for gx in range(4):
            cell = accent[int(gy * ph / 4):int((gy + 1) * ph / 4),
                          int(gx * pw / 4):int((gx + 1) * pw / 4)]
            row.append(round(float(cell.sum()) / total_accent, 3))
        density_grid.append(row)
    ys_a, xs_a = np.nonzero(accent)
    centroid = ({"x": round(float(xs_a.mean()) / pw, 3),
                 "y": round(float(ys_a.mean()) / ph, 3)}
                if len(xs_a) else None)
    coverage = round(float(accent.sum()) / (pw * ph), 4)
    if const_box:
        const_box = (const_box[0] + px0, const_box[1] + py0,
                     const_box[2], const_box[3])

    # --- logo zone: darker rose marks in the upper-left quarter -------------
    logo_mask = (pinkness > 0.06) & (p_lum < 0.75)
    logo_mask[int(0.30 * ph):, :] = False
    logo_mask[:, int(0.55 * pw):] = False
    logo_box = _bbox_of_mask(logo_mask)
    if logo_box:
        logo_box = (logo_box[0] + px0, logo_box[1] + py0,
                    logo_box[2], logo_box[3])

    # --- whitespace / color proportions per quadrant ------------------------
    quadrants = {}
    for name, (ry, rx) in {
        "upper_left": (slice(0, ph // 2), slice(0, pw // 2)),
        "upper_right": (slice(0, ph // 2), slice(pw // 2, pw)),
        "lower_left": (slice(ph // 2, ph), slice(0, pw // 2)),
        "lower_right": (slice(ph // 2, ph), slice(pw // 2, pw)),
    }.items():
        region_lum = p_lum[ry, rx]
        region_pink = pinkness[ry, rx]
        quadrants[name] = {
            "whitespace": round(float((region_lum > 0.82).mean()), 3),
            "accent": round(float(((region_pink > 0.045)
                                   & (region_lum < 0.92)).mean()), 3),
        }

    dominant_movement = "diagonal-lower-right-to-center"
    if centroid and centroid["x"] < 0.5:
        dominant_movement = "diagonal-lower-left-to-center"

    # Confidence: a warm-lit packshot backdrop is itself bright and warm, so
    # absolute box extraction degrades when the detected panel spans most of
    # the frame. Directional metrics (centroid, density gradient, movement)
    # remain robust; box-level values are flagged and the §4 target
    # relationships stay anchored to the variation's structured record.
    frame_share = (pw * ph) / float(w * h)
    box_confidence = "LOW" if frame_share > 0.85 else "MEDIUM"

    return {
        "schema_version": VISUAL_GRAPH_SCHEMA,
        "panel_detected": True,
        "box_confidence": box_confidence,
        "directional_confidence": "HIGH",
        "front_panel_px": {"x": px0, "y": py0, "w": pw, "h": ph},
        "logo_zone": rel(logo_box),
        "product_name_block": rel(name_box),
        "product_name_block_note": (
            "blush BAKED line only — the embossed ivory POWDER line is "
            "NOT_DETECTABLE_DETERMINISTICALLY; total group extent per the "
            "variation record spans both lines"),
        "constellation": {
            "bounding": rel(const_box),
            "centroid": centroid,
            "coverage_fraction": coverage,
            "density_grid_4x4": density_grid,
        },
        "quadrants": quadrants,
        "dominant_movement": dominant_movement,
        "vertical_copy": {
            "orientation": "vertical", "zone": "right-edge",
            "source": "variation_record"},
        "decorative_coverage_declared_pct":
            (variation or {}).get("decorative_coverage_pct"),
        "panel_continuation_intent": "reduced continuation onto the "
                                     "adjacent side panel",
    }


__all__ = ["build_visual_graph", "VISUAL_GRAPH_SCHEMA"]
