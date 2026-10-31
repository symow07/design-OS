"""Design-on-dieline preview exporter (P4 fix, 2026-07-04).

Composites the Gate-1-approved concept artwork onto the dieline so a reviewer
sees (and can download) the finished design in context, not a bare die.
Two deliverables per job:

  {job_id}_design_preview.svg — browser preview at Gate 2 / Completed.
    Artwork embedded base64, contained (never cropped) in the front and back
    panels; panels/flaps carry the artwork-edge tint; lines drawn on top.
  {job_id}_design_preview.ai — the same composition drawn directly with
    reportlab (PDF-compatible .ai). Drawn natively rather than via the
    svglib SVG round-trip because svglib's data-URI image support is
    unreliable with megabyte-scale base64 payloads.

PREVIEW-GRADE by design: the artwork is a raster concept render (RGB), not
vector print artwork. Both files carry a visible caption saying so. The
factory deliverable remains the CMYK production PDF; the artwork handoff
note on the spec sheet explains the split.
"""
from __future__ import annotations

import base64
import os

_CAPTION = (
    "DESIGN PREVIEW (concept artwork composited on dieline) — "
    "preview-grade RGB; produce final print artwork in vector per the "
    "spec-sheet handoff note"
)

# Panels that receive the artwork (the two display faces). Sides, flaps and
# the glue tab get a neutral tint so the flat still reads as a carton.
_ARTWORK_PANELS = ("front", "back")
_TINT = "#EFE9E4"
_PAGE_MARGIN_MM = 10.0


def _mime_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(
        ext.lstrip("."), "image/png"
    )


# Sticker rendering lives in info_panel.py (2026-07-07) — shared by this
# module and the production-PDF underlay. These aliases keep the historical
# call sites and test patch targets working.
from apps.dielines.exporters.info_panel import (  # noqa: E402
    draw_info_panel as _draw_info_panel_impl,
    has_info_content as _has_info_content,
    svg_info_panel as _svg_info_panel,
)


def _draw_info_panel(c, p, X, Y, info, f_reg, f_bold, mm):
    _draw_info_panel_impl(c, p, X, Y, info, f_reg, f_bold, mm)


def _draw_cut_fold_lines(c, cut_path, fold_lines, X, Y):
    """Cut (blue) + fold (red dashed) line work, with a solid white HALO
    drawn underneath both (2026-07-07). Full-surface artwork (2026-07-07)
    put a busy floral/pattern motif under every flap where there used to be
    a flat tint — a bare 0.3-0.8pt colored line disappears against it. The
    halo guarantees the fold indicators stay readable over any artwork."""
    c.setStrokeColorRGB(1, 1, 1)
    c.setLineWidth(1.6)
    c.drawPath(cut_path, fill=0, stroke=1)
    for x1, y1, x2, y2 in fold_lines:
        c.line(X(x1), Y(y1), X(x2), Y(y2))

    c.setStrokeColorRGB(0, 0, 1)
    c.setLineWidth(0.8)
    c.drawPath(cut_path, fill=0, stroke=1)

    c.setStrokeColorRGB(1, 0, 0)
    c.setLineWidth(0.5)
    c.setDash(3, 2)
    for x1, y1, x2, y2 in fold_lines:
        c.line(X(x1), Y(y1), X(x2), Y(y2))
    c.setDash()


def export_design_preview_svg(
    coords, job_id: str, output_dir: str, artwork_path: str,
    tint: str = _TINT, panel_info: dict | None = None,
    motif_path: str | None = None,
) -> str:
    """Write ``{job_id}_design_preview.svg``; returns the SVG string.

    With ``motif_path`` (2026-07-07) the text-free motif covers EVERY panel
    and flap (defined once in <defs>, one clipped <use> per surface); the
    front keeps the full artwork and the back becomes the info sticker.
    Without it, the legacy front+back layout applies.
    """
    with open(artwork_path, "rb") as fh:
        b64 = base64.standard_b64encode(fh.read()).decode("ascii")
    href = f"data:{_mime_for(artwork_path)};base64,{b64}"

    min_x, min_y, max_x, max_y = coords.bleed_polygon.bounds
    vx = min_x - _PAGE_MARGIN_MM
    vy = min_y - _PAGE_MARGIN_MM
    vw = (max_x - min_x) + 2 * _PAGE_MARGIN_MM
    vh = (max_y - min_y) + 2 * _PAGE_MARGIN_MM + 8.0  # room for the caption

    parts: list[str] = []
    parts.append(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{vw:.2f}mm" height="{vh:.2f}mm" '
        f'viewBox="{vx:.2f} {vy:.2f} {vw:.2f} {vh:.2f}">'
    )
    parts.append(f'<rect x="{vx:.2f}" y="{vy:.2f}" width="{vw:.2f}" '
                 f'height="{vh:.2f}" fill="#FFFFFF"/>')

    # Carton silhouette tint (flaps, sides, glue tab) under everything.
    cut_pts = " ".join(f"{x:.2f},{y:.2f}"
                       for x, y in coords.cut_polygon.exterior.coords)
    parts.append(f'<polygon points="{cut_pts}" fill="{tint}"/>')

    # Info panel (2026-07-06): when regulatory data exists, the back face
    # shows it right here on screen — the preview mirrors the deliverable.
    info = panel_info or {}
    has_info = _has_info_content(info)

    if motif_path:
        # Full-surface artwork (2026-07-07): the motif is defined ONCE in
        # defs and instanced per surface — a base64 copy per flap would make
        # a multi-megabyte preview.
        from apps.dielines.exporters.artwork_layers import (
            artwork_targets, svg_clip_defs, target_bounds,
        )
        from PIL import Image

        with open(motif_path, "rb") as fh:
            m64 = base64.standard_b64encode(fh.read()).decode("ascii")
        with Image.open(motif_path) as im:
            miw, mih = im.size

        targets = artwork_targets(coords, has_info)
        parts.append("<defs>")
        parts.append(
            f'<image id="motif-img" width="{miw}" height="{mih}" '
            f'xlink:href="data:{_mime_for(motif_path)};base64,{m64}"/>'
        )
        parts.append(svg_clip_defs(coords, targets))
        parts.append("</defs>")

        info_p = None
        for i, t in enumerate(targets):
            if t.kind == "sticker":
                info_p = t.panel
                continue
            bounds = target_bounds(coords, t)
            if bounds is None:
                continue
            bx, by, bw, bh = bounds
            if t.kind == "full":
                parts.append(
                    f'<image x="{bx:.2f}" y="{by:.2f}" width="{bw:.2f}" '
                    f'height="{bh:.2f}" preserveAspectRatio="xMidYMid meet" '
                    f'clip-path="url(#clip-t{i})" xlink:href="{href}"/>'
                )
                continue
            # motif: cover-crop via a uniform scale inside the clip group
            scale = max(bw / miw, bh / mih)
            ox = bx - (miw * scale - bw) / 2.0
            oy = by - (mih * scale - bh) / 2.0
            parts.append(
                f'<g clip-path="url(#clip-t{i})">'
                f'<use href="#motif-img" xlink:href="#motif-img" '
                f'transform="translate({ox:.2f} {oy:.2f}) '
                f'scale({scale:.5f})"/></g>'
            )
        if info_p is not None:
            parts.append(_svg_info_panel(info_p, info))
    else:
        display = [p for p in coords.panels if p.name in _ARTWORK_PANELS]
        info_p = next((p for p in display if p.name == "back"), None) if has_info else None
        art_panels = [p for p in display if p is not info_p]

        # Artwork contained in each art panel via its own clipPath.
        parts.append("<defs>")
        for p in art_panels:
            parts.append(
                f'<clipPath id="clip-{p.name}"><rect x="{p.x:.2f}" '
                f'y="{p.y:.2f}" width="{p.width:.2f}" '
                f'height="{p.height:.2f}"/></clipPath>'
            )
        parts.append("</defs>")
        for p in art_panels:
            parts.append(
                f'<image x="{p.x:.2f}" y="{p.y:.2f}" width="{p.width:.2f}" '
                f'height="{p.height:.2f}" preserveAspectRatio="xMidYMid meet" '
                f'clip-path="url(#clip-{p.name})" xlink:href="{href}"/>'
            )
        if info_p is not None:
            parts.append(_svg_info_panel(info_p, info))

    # Line work on top so it still reads as a dieline. A white halo underneath
    # (2026-07-07) keeps the fold indicators readable over full-surface
    # artwork — a bare 0.3-0.4mm colored line disappears against a busy
    # floral/pattern motif on the flaps.
    parts.append(
        f'<polygon points="{cut_pts}" fill="none" stroke="#FFFFFF" '
        f'stroke-width="1.6" stroke-linejoin="round"/>'
    )
    for x1, y1, x2, y2 in coords.fold_lines:
        parts.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="#FFFFFF" stroke-width="1.6"/>'
        )
    parts.append(
        f'<polygon points="{cut_pts}" fill="none" stroke="#EC008C" '
        f'stroke-width="0.4"/>'
    )
    for x1, y1, x2, y2 in coords.fold_lines:
        parts.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="#00AEEF" stroke-width="0.3" stroke-dasharray="3 2" '
            f'opacity="0.8"/>'
        )

    parts.append(
        f'<text x="{vx + 2:.2f}" y="{vy + vh - 2.5:.2f}" '
        f'font-family="Helvetica,Arial,sans-serif" font-size="3" '
        f'fill="#8B3A52">{_CAPTION}</text>'
    )
    parts.append("</svg>")
    svg_string = "".join(parts)

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{job_id}_design_preview.svg")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(svg_string)
    return svg_string


def export_design_components_ai(
    coords, job_id: str, output_dir: str, motif_path: str,
    tint: str = _TINT, logo_path: str | None = None,
    product_name: str = "", subtitle: str = "", panel_info: dict | None = None,
    segments: list | None = None,
) -> str:
    """Write ``{job_id}_design_preview.ai`` as SEPARATE EDITABLE COMPONENTS
    (2026-07-06) instead of one flattened raster:

      1. vector silhouette + per-panel background fills (recolorable paths)
      2. the text-free motif artwork per display panel (one image object —
         the only raster component)
      3. the official logo as its own object (upper band of each face)
      4. product name + subtitle as REAL TEXT objects in an embedded font
         (retypeable in Illustrator)
      5. cut/fold line work

    Illustrator shows each drawing op as an individually selectable object,
    so a designer can retype the name, move the logo, or swap the motif
    without touching anything else.
    """
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas

    from apps.dielines.exporters.production_pdf import _resolve_fonts

    f_reg, f_bold = _resolve_fonts()

    min_x, min_y, max_x, max_y = coords.bleed_polygon.bounds
    vx = min_x - _PAGE_MARGIN_MM
    vy = min_y - _PAGE_MARGIN_MM
    vw = (max_x - min_x) + 2 * _PAGE_MARGIN_MM
    vh = (max_y - min_y) + 2 * _PAGE_MARGIN_MM + 8.0

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{job_id}_design_preview.ai")
    c = rl_canvas.Canvas(out_path, pagesize=(vw * mm, vh * mm))
    c.setTitle(f"{job_id} design components")

    def X(x):
        return (x - vx) * mm

    def Y(y):
        return (vh - (y - vy)) * mm

    tr = int(tint[1:3], 16) / 255.0
    tg = int(tint[3:5], 16) / 255.0
    tb = int(tint[5:7], 16) / 255.0

    # --- component 1: vector silhouette + per-panel background fills --------
    c.setFillColorRGB(tr, tg, tb)
    sil = c.beginPath()
    ext = list(coords.cut_polygon.exterior.coords)
    sil.moveTo(X(ext[0][0]), Y(ext[0][1]))
    for x, y in ext[1:]:
        sil.lineTo(X(x), Y(y))
    sil.close()
    c.drawPath(sil, fill=1, stroke=0)
    display = [p for p in coords.panels if p.name in _ARTWORK_PANELS]
    # Info panel (2026-07-06): when regulatory data exists, the BACK face
    # carries it (description / ingredients / barcode / QR) and only the
    # front face gets the motif + logo + name — like real production files.
    info = panel_info or {}
    has_info = _has_info_content(info)
    info_panel = next((p for p in display if p.name == "back"), None) if has_info else None
    art_panels = [p for p in display if p is not info_panel]
    for p in display:
        c.rect(X(p.x), Y(p.y + p.height), p.width * mm, p.height * mm,
               fill=1, stroke=0)
    if info_panel is not None:
        # near-white ground for legibility of small regulatory type
        c.setFillColorRGB(0.985, 0.973, 0.960)
        c.rect(X(info_panel.x), Y(info_panel.y + info_panel.height),
               info_panel.width * mm, info_panel.height * mm, fill=1, stroke=0)

    # --- component 2: text-free motif per display panel ----------------------
    # Cover-crop (2026-07-06): the background variant carries no text, so
    # filling the panel edge-to-edge is safe — contain left the design as a
    # letterboxed band inside a dark field.
    img = ImageReader(motif_path)
    iw, ih = img.getSize()
    # Per-element cut (2026-07-07): with ``segments`` each motif element is
    # drawn as its OWN image object (soft-alpha RGBA crop of the approved
    # artwork) at its original position — every flower individually
    # selectable/movable in Illustrator. Without segments: single raster.
    seg_readers = ([(ImageReader(s.image), s) for s in segments]
                   if segments else [])
    for p in art_panels:
        c.saveState()
        clip = c.beginPath()
        clip.rect(X(p.x), Y(p.y + p.height), p.width * mm, p.height * mm)
        c.clipPath(clip, stroke=0, fill=0)
        scale = max((p.width * mm) / iw, (p.height * mm) / ih)
        dw, dh = iw * scale, ih * scale
        ox = X(p.x) - (dw - p.width * mm) / 2.0
        oy = Y(p.y + p.height) - (dh - p.height * mm) / 2.0
        if seg_readers:
            for reader, s in seg_readers:
                sx = ox + s.x * scale
                sy = oy + dh - (s.y + s.h) * scale   # image y-down → PDF y-up
                c.drawImage(reader, sx, sy,
                            width=s.w * scale, height=s.h * scale,
                            preserveAspectRatio=False, mask="auto")
        else:
            c.drawImage(img, ox, oy, width=dw, height=dh,
                        preserveAspectRatio=False, mask="auto")
        c.restoreState()

    # Full-surface coverage (2026-07-07): sides, glue tab and every flap get
    # the motif too, clipped to their real outlines — one object per surface.
    from apps.dielines.exporters.artwork_layers import (
        artwork_targets, rl_clip_component, target_bounds,
    )
    for t in artwork_targets(coords, has_info):
        if t.kind != "motif":
            continue
        if t.panel is not None and t.panel.name in _ARTWORK_PANELS:
            continue                      # body faces handled above
        bounds = target_bounds(coords, t)
        if bounds is None:
            continue
        bx, by, bw, bh = bounds
        c.saveState()
        if t.panel is not None:
            clip = c.beginPath()
            clip.rect(X(bx), Y(by + bh), bw * mm, bh * mm)
            c.clipPath(clip, stroke=0, fill=0)
        elif not rl_clip_component(c, coords, t.comp_id, X, Y):
            c.restoreState()
            continue
        scale = max((bw * mm) / iw, (bh * mm) / ih)
        dw, dh = iw * scale, ih * scale
        ox = X(bx) - (dw - bw * mm) / 2.0
        oy = Y(by + bh) - (dh - bh * mm) / 2.0
        c.drawImage(img, ox, oy, width=dw, height=dh,
                    preserveAspectRatio=False, mask="auto")
        c.restoreState()

    # --- component 3: official logo, its own object per face ----------------
    if logo_path and os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        lw, lh = logo.getSize()
        for p in art_panels:
            span = p.width * mm * 0.62               # 62% of panel width
            h = span * lh / lw
            lx = X(p.x) + (p.width * mm - span) / 2.0
            ly = Y(p.y) - p.height * mm * 0.16 - h   # upper band
            c.drawImage(logo, lx, ly, width=span, height=h,
                        preserveAspectRatio=True, mask="auto")

    # --- component 4: REAL text objects (editable in Illustrator) -----------
    # Ink chosen by tint luminance so the type stays readable on dark designs.
    _lum = 0.299 * tr + 0.587 * tg + 0.114 * tb
    if _lum < 0.5:
        c.setFillColorRGB(0.97, 0.94, 0.90)          # warm white on dark
    else:
        c.setFillColorRGB(0.35, 0.16, 0.22)          # deep rose ink on light
    for p in art_panels:
        cx = X(p.x) + (p.width * mm) / 2.0
        if product_name:
            c.setFont(f_bold, max(8.0, p.width * mm * 0.075))
            c.drawCentredString(cx, Y(p.y + p.height) + p.height * mm * 0.22,
                                product_name[:40])
        if subtitle:
            c.setFont(f_reg, max(5.5, p.width * mm * 0.045))
            c.drawCentredString(cx, Y(p.y + p.height) + p.height * mm * 0.16,
                                subtitle[:60])

    # --- component 4b: regulatory info panel on the back face ---------------
    if info_panel is not None:
        _draw_info_panel(c, info_panel, X, Y, info, f_reg, f_bold, mm)

    # --- component 5: cut + fold line work -----------------------------------
    _draw_cut_fold_lines(c, sil, coords.fold_lines, X, Y)

    c.setFillColorRGB(0.545, 0.227, 0.322)
    c.setFont(f_reg, 7)
    c.drawString(X(vx) + 6, 8,
                 "DESIGN COMPONENTS — editable objects: background fills, "
                 "motif image, logo, live text, dieline. Motif is raster "
                 "(preview-grade); rebuild in vector for print.")

    c.showPage()
    c.save()
    return out_path


def export_design_preview_ai(
    coords, job_id: str, output_dir: str, artwork_path: str,
    tint: str = _TINT, panel_info: dict | None = None,
    motif_path: str | None = None,
) -> str:
    """Write ``{job_id}_design_preview.ai`` (PDF-compatible); returns path.

    When ``panel_info`` carries content (2026-07-06), the BACK face renders
    the regulatory info panel (live text + vector EAN-13 + QR) and the
    artwork stays on the front — matching the on-screen SVG preview, which
    already worked this way; the faithful .ai had been left behind.

    With ``motif_path`` (2026-07-07) the text-free motif cover-crops onto
    every other panel and flap (clipped to the real outlines, curved tuck
    shoulders included) so the flat reads like a finished production file.
    """
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas

    from apps.dielines.exporters.production_pdf import _resolve_fonts

    min_x, min_y, max_x, max_y = coords.bleed_polygon.bounds
    vx = min_x - _PAGE_MARGIN_MM
    vy = min_y - _PAGE_MARGIN_MM
    vw = (max_x - min_x) + 2 * _PAGE_MARGIN_MM
    vh = (max_y - min_y) + 2 * _PAGE_MARGIN_MM + 8.0

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{job_id}_design_preview.ai")
    c = rl_canvas.Canvas(out_path, pagesize=(vw * mm, vh * mm))
    c.setTitle(f"{job_id} design preview")

    def X(x):  # dieline mm → page points
        return (x - vx) * mm

    def Y(y):  # dieline y grows downward; PDF y grows upward
        return (vh - (y - vy)) * mm

    # Silhouette tint (artwork-derived when the caller provides one).
    tr = int(tint[1:3], 16) / 255.0
    tg = int(tint[3:5], 16) / 255.0
    tb = int(tint[5:7], 16) / 255.0
    c.setFillColorRGB(tr, tg, tb)
    path = c.beginPath()
    ext = list(coords.cut_polygon.exterior.coords)
    path.moveTo(X(ext[0][0]), Y(ext[0][1]))
    for x, y in ext[1:]:
        path.lineTo(X(x), Y(y))
    path.close()
    c.drawPath(path, fill=1, stroke=0)

    # Info panel on the back face when regulatory content exists.
    info = panel_info or {}
    has_info = _has_info_content(info)
    display = [p for p in coords.panels if p.name in _ARTWORK_PANELS]
    info_panel = next((p for p in display if p.name == "back"), None) if has_info else None

    img = ImageReader(artwork_path)
    iw, ih = img.getSize()

    # Full-surface motif (2026-07-07): cover-crop the text-free motif onto
    # every non-front surface, clipped to the real outline (curved tuck
    # shoulders included). Drawn before the front artwork and sticker.
    if motif_path:
        from apps.dielines.exporters.artwork_layers import (
            artwork_targets, rl_clip_component, target_bounds,
        )
        motif = ImageReader(motif_path)
        miw, mih = motif.getSize()
        for t in artwork_targets(coords, has_info):
            if t.kind != "motif":
                continue
            bounds = target_bounds(coords, t)
            if bounds is None:
                continue
            bx, by, bw, bh = bounds
            c.saveState()
            if t.panel is not None:
                clip = c.beginPath()
                clip.rect(X(bx), Y(by + bh), bw * mm, bh * mm)
                c.clipPath(clip, stroke=0, fill=0)
            elif not rl_clip_component(c, coords, t.comp_id, X, Y):
                c.restoreState()
                continue
            scale = max((bw * mm) / miw, (bh * mm) / mih)
            dw, dh = miw * scale, mih * scale
            ox = X(bx) - (dw - bw * mm) / 2.0
            oy = Y(by + bh) - (dh - bh * mm) / 2.0
            c.drawImage(motif, ox, oy, width=dw, height=dh,
                        preserveAspectRatio=False, mask="auto")
            c.restoreState()

    # Approved artwork contained in the display panels (clip + centered
    # draw); with a motif the front alone carries it, like a real box.
    art_panels = [p for p in display if p is not info_panel]
    if motif_path:
        art_panels = [p for p in art_panels if p.name == "front"]
    for p in art_panels:
        c.saveState()
        clip = c.beginPath()
        clip.rect(X(p.x), Y(p.y + p.height), p.width * mm, p.height * mm)
        c.clipPath(clip, stroke=0, fill=0)
        # contain: the full artwork stays visible, centered; the panel's
        # remaining area carries the artwork-edge tint so nothing is cropped
        # (a 2:3 render cover-cropped into a ~1:3 panel chopped the type).
        scale = min((p.width * mm) / iw, (p.height * mm) / ih)
        dw, dh = iw * scale, ih * scale
        ox = X(p.x) - (dw - p.width * mm) / 2.0
        oy = Y(p.y + p.height) - (dh - p.height * mm) / 2.0
        c.drawImage(img, ox, oy, width=dw, height=dh,
                    preserveAspectRatio=False, mask="auto")
        c.restoreState()

    if info_panel is not None:
        f_reg, f_bold = _resolve_fonts()
        c.setFillColorRGB(0.985, 0.973, 0.960)
        c.rect(X(info_panel.x), Y(info_panel.y + info_panel.height),
               info_panel.width * mm, info_panel.height * mm, fill=1, stroke=0)
        _draw_info_panel(c, info_panel, X, Y, info, f_reg, f_bold, mm)

    # Cut outline (blue) + fold lines (red dashed), with a white halo.
    _draw_cut_fold_lines(c, path, coords.fold_lines, X, Y)

    c.setFillColorRGB(0.545, 0.227, 0.322)
    c.setFont("Helvetica", 7)
    c.drawString(X(vx) + 6, 8, _CAPTION)

    c.showPage()
    c.save()
    return out_path
