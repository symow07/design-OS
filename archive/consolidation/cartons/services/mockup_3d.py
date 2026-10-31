"""Preview-grade folded-carton mockup (DIP-2A-5-DIE-5).

Renders an isometric "erected carton" PNG from the flat design preview:
the front panel, right side panel and the top face (the tuck flap's
fold-over band) are cropped out of the rasterized design .ai and
perspective-mapped onto the three visible faces of a box, with simple
per-face shading. Deterministic and offline — a communication aid for the
Gate-2 reviewer, NOT a manufacturing deliverable (the dieline + production
PDF remain the factory truth).

Best-effort by contract: returns None when PIL/numpy or the preview PNG
are unavailable.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_PAGE_MARGIN_MM = 10.0
_ISO_RX = (0.866, 0.5)      # screen direction of the width axis (front)
_ISO_DX = (0.866, -0.5)     # screen direction of the depth axis (side)


def export_folded_mockup(
    coords, design_png_path: str, out_path: str,
    page_margin_mm: float = _PAGE_MARGIN_MM, px_per_mm: float = 8.0,
) -> str | None:
    """Write an isometric folded mockup PNG; returns the path or None."""
    try:
        import numpy as np
        from PIL import Image, ImageEnhance
    except ImportError:
        logger.warning("3D mockup skipped: PIL/numpy unavailable")
        return None
    if not os.path.exists(design_png_path):
        return None

    try:
        flat = Image.open(design_png_path).convert("RGB")
    except OSError:
        return None

    # --- flat-page geometry (same contract as the composers) ---------------
    min_x, min_y, max_x, _max_y = coords.bleed_polygon.bounds
    vx = min_x - page_margin_mm
    vy = min_y - page_margin_mm
    page_w_mm = (max_x - min_x) + 2 * page_margin_mm
    s_png = flat.width / page_w_mm                # PNG px per mm

    def crop(x_mm, y_mm, w_mm, h_mm):
        left = int((x_mm - vx) * s_png)
        top = int((y_mm - vy) * s_png)
        return flat.crop((
            max(left, 0), max(top, 0),
            min(left + int(w_mm * s_png), flat.width),
            min(top + int(h_mm * s_png), flat.height),
        ))

    panels = {p.name: p for p in coords.panels}
    front = panels.get("front")
    side = panels.get("side_right") or panels.get("side_left")
    if front is None or side is None:
        return None
    d = coords.derived
    W_mm, D_mm = front.width, side.width
    H_mm = front.height

    front_img = crop(front.x, front.y, front.width, front.height)
    side_img = crop(side.x, side.y, side.width, side.height)
    # Top face: the tuck flap's fold-over band (its lower D mm), which is the
    # face a customer sees on the closed carton. Falls back to a tint strip.
    top_panel = panels.get(str(d.get("top_tuck_panel", "back")))
    y1 = float(d.get("y1", front.y))
    if top_panel is not None:
        top_img = crop(top_panel.x, max(y1 - D_mm, 0.0), top_panel.width, D_mm)
    else:
        top_img = front_img.crop((0, 0, front_img.width,
                                  max(1, int(D_mm * s_png))))

    # Per-face shading for depth.
    side_img = ImageEnhance.Brightness(side_img).enhance(0.88)
    top_img = ImageEnhance.Brightness(top_img).enhance(1.06)

    # --- isometric assembly --------------------------------------------------
    s = px_per_mm
    rx = (_ISO_RX[0] * s, _ISO_RX[1] * s)
    dx = (_ISO_DX[0] * s, _ISO_DX[1] * s)
    pad = 30.0
    ox = pad
    oy = pad + H_mm * s + W_mm * rx[1] + pad   # base-front-left corner

    def pt(w_units, d_units, h_units):
        return (ox + rx[0] * w_units + dx[0] * d_units,
                oy + rx[1] * w_units + dx[1] * d_units - s * h_units)

    canvas_w = int(ox + rx[0] * W_mm + dx[0] * D_mm + pad)
    canvas_h = int(oy + rx[1] * W_mm + pad)
    out = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    def perspective_coeffs(dest_quad, src_quad):
        """Coefficients for PIL PERSPECTIVE, which maps OUTPUT -> INPUT:
        solve T(dest) = src for the 8 homography parameters."""
        matrix = []
        for (dx_, dy_), (sx_, sy_) in zip(dest_quad, src_quad):
            matrix.append([dx_, dy_, 1, 0, 0, 0, -sx_ * dx_, -sx_ * dy_])
            matrix.append([0, 0, 0, dx_, dy_, 1, -sy_ * dx_, -sy_ * dy_])
        A = np.array(matrix, dtype=np.float64)
        B = np.array([c for p in src_quad for c in p], dtype=np.float64)
        return np.linalg.solve(A, B).tolist()

    def paste_face(img, dest_quad):
        src = [(0, 0), (img.width, 0), (img.width, img.height), (0, img.height)]
        coeffs = perspective_coeffs(dest_quad, src)
        warped = img.convert("RGBA").transform(
            (canvas_w, canvas_h), Image.PERSPECTIVE, coeffs,
            resample=Image.BICUBIC)
        # Mask: only inside the destination quad.
        from PIL import ImageDraw
        mask = Image.new("L", (canvas_w, canvas_h), 0)
        ImageDraw.Draw(mask).polygon(dest_quad, fill=255)
        out.paste(warped, (0, 0), mask)

    # top face first (behind edges), then side, then front
    paste_face(top_img, [pt(0, D_mm, H_mm), pt(W_mm, D_mm, H_mm),
                         pt(W_mm, 0, H_mm), pt(0, 0, H_mm)])
    paste_face(side_img, [pt(W_mm, 0, H_mm), pt(W_mm, D_mm, H_mm),
                          pt(W_mm, D_mm, 0), pt(W_mm, 0, 0)])
    paste_face(front_img, [pt(0, 0, H_mm), pt(W_mm, 0, H_mm),
                           pt(W_mm, 0, 0), pt(0, 0, 0)])

    background = Image.new("RGB", out.size, (246, 243, 239))
    background.paste(out, (0, 0), out)
    background.save(out_path)
    return out_path


__all__ = ["export_folded_mockup"]
