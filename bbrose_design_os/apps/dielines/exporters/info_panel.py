"""Back-face regulatory STICKER (2026-07-07) — drawn by the Design Graph's sticker bridge
(apps/ire/emitters/pdf_ai.py), and by design_preview.py's raster .ai, which only its tests still call.

Mirrors the factory back panels (EP2508): a rounded sticker frame carrying
the label copy in THREE languages (English, Spanish, Arabic — translations
arrive pre-computed in ``info["translations"]``), a bottom band with the
NET WT / ITEM / BATCH box, vector EAN-13 barcode and QR code, and the
supplier block.

Arabic lines are shaped + bidi'd via text_intl (wrap on logical text, bidi
per line) and drawn right-aligned. Missing translations, shaping libs or the
Arabic font degrade the sticker to fewer languages — never a crash.

The 3x text volume is handled by ``_fit_sticker_blocks``: font size steps
down from ``_SIZE_MAX`` to ``_SIZE_MIN``; if it still overflows, block text
is truncated in priority order (description, then how_to_use, then the
ingredients tail) equally across languages. WARNINGS are never truncated.
"""
from __future__ import annotations

from apps.dielines.exporters.text_intl import has_ar_support, shape_ar, wrap_ar

# Fields that make the back face render as the sticker at all.
INFO_CONTENT_KEYS = (
    "description", "ingredients", "how_to_use", "warnings",
    "barcode_ean", "qr_url", "regulatory_text",
)

_FIELDS = ("description", "ingredients", "how_to_use", "warnings")

_EN_LABELS = {"description": "", "ingredients": "INGREDIENTS:",
              "how_to_use": "HOW TO USE:", "warnings": "WARNINGS:"}
_ES_LABELS = {"description": "DESCRIPCIÓN:", "ingredients": "INGREDIENTES:",
              "how_to_use": "MODO DE USO:", "warnings": "ADVERTENCIAS:"}
_AR_LABELS = {"description": "الوصف:", "ingredients": "المكونات:",
              "how_to_use": "طريقة الاستعمال:", "warnings": "تحذيرات:"}

_INK = (0.25, 0.15, 0.12)
# CMYK equivalents (DIP-2A-5-DIE-4): the sticker paints with CMYK operators
# so the design .ai / production PDF carry no RGB ink (Gate-2 requirement).
# Same visual values as the RGB pair above.
from reportlab.lib.colors import CMYKColor as _CMYK  # noqa: E402

_INK_C = _CMYK(0.0, 0.40, 0.52, 0.75)
_PAPER_C = _CMYK(0.0, 0.012, 0.023, 0.012)
_BLACK_C = _CMYK(0.0, 0.0, 0.0, 1.0)
_SIZE_MAX = 4.4
_SIZE_MIN = 2.2
_TRUNC_ORDER = ("description", "how_to_use", "ingredients")   # never warnings


def _resolve_arabic_font_for_label():
    """The Arabic face the sticker draws with, or None where shaping or the face is missing."""
    from apps.dielines.exporters.counter_display_files import _resolve_arabic_font
    f_ar = _resolve_arabic_font()
    if not has_ar_support(f_ar):
        return None
    return f_ar


def has_info_content(info: dict | None) -> bool:
    info = info or {}
    return any(info.get(k) for k in INFO_CONTENT_KEYS)


def build_sticker_blocks(info: dict) -> list[dict]:
    """[{field, lang, label, text}] in draw order (EN -> ES -> AR per field)."""
    translations = info.get("translations") or {}
    es = translations.get("es") or {}
    ar = translations.get("ar") or {}
    blocks = []
    for field in _FIELDS:
        en_text = (info.get(field) or "").strip()
        if not en_text:
            continue
        blocks.append({"field": field, "lang": "en",
                       "label": _EN_LABELS[field], "text": en_text})
        if (es.get(field) or "").strip():
            blocks.append({"field": field, "lang": "es",
                           "label": _ES_LABELS[field], "text": es[field].strip()})
        # No Arabic INGREDIENTS block — the factory reference (EP2508) lists
        # INCI once in Latin only; repeating it in the Arabic block wastes
        # space and INCI names are international nomenclature anyway.
        if field != "ingredients" and (ar.get(field) or "").strip():
            blocks.append({"field": field, "lang": "ar",
                           "label": _AR_LABELS[field], "text": ar[field].strip()})
    if (info.get("regulatory_text") or "").strip():
        blocks.append({"field": "regulatory_text", "lang": "en",
                       "label": "", "text": info["regulatory_text"].strip()})
    return blocks


def _block_lines(block, size, max_w, f_reg, f_ar, keep_marks=False):
    """Wrapped lines for one block at the given size (measuring real fonts)."""
    from reportlab.lib.utils import simpleSplit
    body = f"{block['label']} {block['text']}".strip()
    if block["lang"] == "ar":
        return (wrap_ar(body, f_ar, size, max_w, latin_font=f_reg, keep_harakat=keep_marks)
                if f_ar else [])
    return simpleSplit(body, f_reg, size, max_w)


def _layout_height(blocks, size, max_w, f_reg, f_ar) -> float:
    lead = size * 1.22
    total = 0.0
    prev_field = None
    for b in blocks:
        lines = _block_lines(b, size, max_w, f_reg, f_ar)
        if not lines:
            continue
        total += len(lines) * lead
        total += lead * (0.55 if b["field"] != prev_field else 0.18)
        prev_field = b["field"]
    return total


def _fit_sticker_blocks(blocks, avail_h, max_w, f_reg, f_ar,
                        size_max=_SIZE_MAX, size_min=_SIZE_MIN):
    """(font_size, blocks) that fit avail_h; truncates by priority if needed."""
    size = size_max
    while size > size_min:
        if _layout_height(blocks, size, max_w, f_reg, f_ar) <= avail_h:
            return size, blocks
        size = round(size - 0.2, 2)

    # Still overflowing at minimum size: truncate low-priority copy equally
    # across the three languages of the sacrificed field. Warnings survive.
    blocks = [dict(b) for b in blocks]
    for field in _TRUNC_ORDER:
        for _ in range(6):
            if _layout_height(blocks, size_min, max_w, f_reg, f_ar) <= avail_h:
                return size_min, blocks
            cut = False
            for b in blocks:
                if b["field"] == field and len(b["text"]) > 60:
                    b["text"] = b["text"][: int(len(b["text"]) * 0.8)].rstrip() + "…"
                    cut = True
            if not cut:
                break
    return size_min, blocks


def title_ar(info: dict) -> str:
    """[His review of 119, 2026-10-05, point 6: "Back-panel Arabic: where my brief gives the Arabic, use my words
    exactly (with the shadda)."] The Arabic of the title: the product's Arabic name as his brief or the product record
    writes it (``info["product_name_ar"]``), else the translation's — and only words in Arabic letters (119's translation
    returned "Rose Glaze Lip Gloss", English letters the Arabic face cannot draw)."""
    from apps.dielines.exporters.text_intl import _is_arabic_char
    for words in (info.get("product_name_ar"), ((info.get("translations") or {}).get("ar") or {}).get("product_name")):
        words = " ".join(str(words or "").split())
        if words and any(_is_arabic_char(ch) for ch in words):
            return words
    return ""


def draw_info_panel(c, p, X, Y, info, f_reg, f_bold, mm, keep_marks=False, ground=None, layout=None, ink=None):
    """Render the trilingual sticker onto panel ``p`` (reportlab canvas).

    Same call contract as the pre-sticker `_draw_info_panel` so the faithful
    .ai, components .ai and production-PDF underlay share one renderer.
    ``keep_marks``: the document keeps its Arabic marks (his rule of 2026-10-05). ``ground``: the panel's own
    ground the copy stands on — no paper and no frame of the sticker's own (his review of 119, 2026-10-05, point 3).
    ``layout``: [his final goal, 2026-10-05, C5: "THE INFO IS ONE DESIGNED BLOCK"] the carton's plan for its back
    (``apps/ire/compose.py``) — its region on the sticker, the languages it carries, its title and foot, its levels —
    drawn by ``label_layout`` in ``ink``: never under a floor, never cut. Without one, the sticker as before (the paths
    no carton reaches).
    """
    if layout:
        from apps.dielines.exporters import label_layout as _LL
        f_ar = _resolve_arabic_font_for_label()
        fonts = {"regular": f_reg, "bold": f_bold, "arabic": f_ar}
        dx, dy, rw, rh = (float(v) for v in layout["region_mm"])
        plan = _LL.plan_label(info, rw * mm, rh * mm, fonts, panel_w=p.width * mm, tail=layout.get("tail", True),
                              languages=layout.get("languages", _LL.LANGUAGES), title=bool(layout.get("title")),
                              band=bool(layout.get("band")), keep_marks=keep_marks, levels=layout.get("levels"))
        colour = _INK_C
        if ink:
            colour = _LL._cmyk(ink)
        return _LL.draw_plan(c, plan, X(p.x + dx), Y(p.y + dy + rh), info, fonts, colour, paper=ground)
    from apps.dielines.exporters.counter_display_files import _resolve_arabic_font

    info = info or {}
    f_ar = _resolve_arabic_font()
    if not has_ar_support(f_ar):
        f_ar = None

    pw = p.width * mm
    ph = p.height * mm

    # --- sticker frame -------------------------------------------------------
    inset = pw * 0.04
    fx = X(p.x) + inset
    fy = Y(p.y + p.height) + inset
    fw = pw - 2 * inset
    fh = ph - 2 * inset
    radius = min(8.0, pw * 0.05)
    if ground is None:
        c.saveState()
        c.setFillColor(_PAPER_C)
        c.setStrokeColor(_INK_C)
        c.setLineWidth(0.5)
        c.roundRect(fx, fy, fw, fh, radius, fill=1, stroke=1)
        c.restoreState()

    pad = fw * 0.05
    left = fx + pad
    right = fx + fw - pad
    max_w = fw - 2 * pad
    top = fy + fh - pad
    c.setFillColor(_INK_C)

    # --- title line: EN left / AR right on one baseline ----------------------
    y = top - 4.5
    title_en = (info.get("product_name") or "").upper()
    ar_title = title_ar(info)
    tsize = max(4.2, min(6.0, pw * 0.035))
    if title_en:
        c.setFont(f_bold, tsize)
        if ar_title and f_ar:
            c.drawString(left, y, title_en[:42])
            c.setFont(f_ar, tsize)
            c.drawRightString(right, y, shape_ar(ar_title[:42], keep_harakat=keep_marks))
        else:
            c.drawCentredString(fx + fw / 2.0, y, title_en[:48])
        y -= tsize * 1.9

    # --- bottom band reservation ---------------------------------------------
    bar_h = max(14.0, pw * 0.11)
    band_h = bar_h + 12.0
    band_top = fy + pad + band_h

    # --- fitted trilingual body blocks ----------------------------------------
    blocks = build_sticker_blocks(info)
    if not f_ar:
        blocks = [b for b in blocks if b["lang"] != "ar"]
    avail_h = max(0.0, y - band_top)
    size, blocks = _fit_sticker_blocks(blocks, avail_h, max_w, f_reg, f_ar)   # marks weigh nothing in a line's width
    lead = size * 1.22
    prev_field = None
    for b in blocks:
        lines = _block_lines(b, size, max_w, f_reg, f_ar, keep_marks)
        if not lines:
            continue
        y -= lead * (0.55 if b["field"] != prev_field else 0.18)
        prev_field = b["field"]
        if b["lang"] == "ar":
            # Mixed-run drawing: the Arabic face has no Latin glyphs, so
            # runs like 'BBROSE' inside Arabic copy switch to the Latin
            # font. Lines are visual-order after bidi — draw left to right
            # from a right-aligned start.
            from apps.dielines.exporters.text_intl import split_script_runs
            from reportlab.pdfbase.pdfmetrics import stringWidth
            for ln in lines:
                if y < band_top:
                    break
                runs = split_script_runs(ln)
                total = sum(stringWidth(t, f_ar if is_ar else f_reg, size)
                            for is_ar, t in runs)
                x = right - total
                for is_ar, t in runs:
                    c.setFont(f_ar if is_ar else f_reg, size)
                    c.drawString(x, y, t)
                    x += stringWidth(t, f_ar if is_ar else f_reg, size)
                y -= lead
            continue
        label = b["label"]
        # [his goal of 2026-10-10, item 8: "The ℮ prints as a plain "e": it must be the real estimated sign everywhere."] each ℮ drawn as the sign itself
        from apps.ire.estimated_sign import draw_text as _draw_signed
        for i, ln in enumerate(lines):
            if y < band_top:
                break
            if i == 0 and label:
                c.setFont(f_bold, size)
                lw = c.stringWidth(label, f_bold, size)
                c.drawString(left, y, label)
                c.setFont(f_reg, size)
                _draw_signed(c, left + lw + 1.5, y, ln[len(label):].lstrip(), f_reg, size)
            else:
                c.setFont(f_reg, size)
                _draw_signed(c, left, y, ln, f_reg, size)
            y -= lead

    # --- bottom band: meta box + EAN-13 + QR ----------------------------------
    band_y = fy + pad
    msize = max(2.8, size - 0.4)

    # meta box (NET WT / ITEM NO / BATCH) on the left, like the factory files
    meta_rows = [r for r in (
        f"NET WT: {info['net_weight']}" if info.get("net_weight") else "",
        f"ITEM NO: {info['item_no']}" if info.get("item_no") else "",
        "BATCH NO: ________   EXP: ________",
    ) if r]
    box_w = max_w * 0.34
    if meta_rows:
        row_h = msize * 1.5
        box_h = row_h * len(meta_rows) + 3
        c.setLineWidth(0.4)
        c.setStrokeColor(_INK_C)
        c.rect(left, band_y, box_w, box_h, fill=0, stroke=1)
        ty = band_y + box_h - row_h + 1.5
        from apps.ire.estimated_sign import draw_text as _draw_signed
        for row in meta_rows:
            c.setFont(f_bold, msize)
            _draw_signed(c, left + 2, ty, row[:44], f_bold, msize)     # [his goal of 2026-10-10, item …] the sign itself
            ty -= row_h

    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode import createBarcodeDrawing

    ean = "".join(ch for ch in (info.get("barcode_ean") or "") if ch.isdigit())
    if len(ean) in (12, 13):
        try:
            d = createBarcodeDrawing("EAN13", value=ean, barHeight=bar_h,
                                     humanReadable=True,
                                     barFillColor=_BLACK_C,
                                     textColor=_BLACK_C)
            sc = min(1.0, (max_w * 0.36) / d.width)
            c.saveState()
            c.translate(left + box_w + max_w * 0.04, band_y)
            c.scale(sc, sc)
            renderPDF.draw(d, c, 0, 0)
            c.restoreState()
        except Exception:  # noqa: BLE001 — bad digits must not kill the export
            pass
    qr_target = info.get("qr_url")
    if qr_target:
        try:
            from reportlab.graphics.barcode.qr import QrCodeWidget
            from reportlab.graphics.shapes import Drawing

            q = QrCodeWidget(qr_target, barFillColor=_BLACK_C)
            b = q.getBounds()
            side = max(18.0, pw * 0.14)
            dq = Drawing(side, side,
                         transform=[side / (b[2] - b[0]), 0, 0,
                                    side / (b[3] - b[1]), 0, 0])
            dq.add(q)
            renderPDF.draw(dq, c, right - side, band_y)
        except Exception:  # noqa: BLE001
            pass


def svg_info_panel(p, info) -> str:
    """Trilingual sticker for the ON-SCREEN SVG preview. Arabic is emitted as
    raw logical Unicode with direction="rtl" — browsers shape natively, so no
    reshaper pass is needed (or wanted) here."""
    from xml.sax.saxutils import escape

    info = info or {}
    translations = info.get("translations") or {}
    ar = translations.get("ar") or {}

    blocks = build_sticker_blocks(info)
    # crude volume-aware sizing: 3x the copy needs a smaller face
    volume = sum(len(b["text"]) for b in blocks) or 1
    size = max(1.15, min(2.2, (p.width * p.height) / (volume * 22.0)))
    lead = size * 1.28
    inset = p.width * 0.04
    fx, fy = p.x + inset, p.y + inset
    fw, fh = p.width - 2 * inset, p.height - 2 * inset
    pad = fw * 0.05
    left = fx + pad
    right = fx + fw - pad
    max_chars = max(12, int((fw - 2 * pad) / (size * 0.58)))

    parts = [
        f'<rect x="{p.x:.2f}" y="{p.y:.2f}" width="{p.width:.2f}" '
        f'height="{p.height:.2f}" fill="#FBF8F5"/>',
        f'<rect x="{fx:.2f}" y="{fy:.2f}" width="{fw:.2f}" height="{fh:.2f}" '
        f'rx="{min(3.0, fw * 0.05):.2f}" fill="#FCF9F6" stroke="#3F2620" '
        f'stroke-width="0.25"/>',
    ]
    bottom_limit = fy + fh - pad - 13
    y = fy + pad + size * 1.6

    title = (info.get("product_name") or "").upper()
    title_ar = ar.get("product_name", "")
    if title:
        if title_ar:
            parts.append(
                f'<text x="{left:.2f}" y="{y:.2f}" font-family="Helvetica,Arial" '
                f'font-size="{size * 1.25:.2f}" font-weight="bold" '
                f'fill="#3F2620">{escape(title[:40])}</text>'
            )
            parts.append(
                f'<text x="{right:.2f}" y="{y:.2f}" direction="rtl" '
                f'text-anchor="end" font-family="Noto Naskh Arabic,Arial" '
                f'font-size="{size * 1.25:.2f}" font-weight="bold" '
                f'fill="#3F2620">{escape(title_ar[:40])}</text>'
            )
        else:
            parts.append(
                f'<text x="{fx + fw / 2:.2f}" y="{y:.2f}" text-anchor="middle" '
                f'font-family="Helvetica,Arial" font-size="{size * 1.25:.2f}" '
                f'font-weight="bold" fill="#3F2620">{escape(title[:44])}</text>'
            )
        y += lead * 1.7

    def wrap(text):
        words, line, out = text.split(), "", []
        for w in words:
            if len(line) + len(w) + 1 > max_chars:
                out.append(line)
                line = w
            else:
                line = f"{line} {w}".strip()
        if line:
            out.append(line)
        return out

    prev_field = None
    for b in blocks:
        if y > bottom_limit:
            break
        y += lead * (0.4 if b["field"] != prev_field else 0.1)
        prev_field = b["field"]
        body = f"{b['label']} {b['text']}".strip()
        rtl = b["lang"] == "ar"
        for i, ln in enumerate(wrap(body)):
            if y > bottom_limit:
                break
            weight = ' font-weight="bold"' if (i == 0 and b["label"]) else ""
            if rtl:
                parts.append(
                    f'<text x="{right:.2f}" y="{y:.2f}" direction="rtl" '
                    f'text-anchor="end" font-family="Noto Naskh Arabic,Arial" '
                    f'font-size="{size:.2f}" fill="#3F2620"{weight}>'
                    f'{escape(ln)}</text>'
                )
            else:
                parts.append(
                    f'<text x="{left:.2f}" y="{y:.2f}" '
                    f'font-family="Helvetica,Arial" font-size="{size:.2f}" '
                    f'fill="#3F2620"{weight}>{escape(ln)}</text>'
                )
            y += lead

    # machine-readable placeholders along the bottom band (real codes in .ai)
    by = fy + fh - pad - 8
    ean = "".join(ch for ch in (info.get("barcode_ean") or "") if ch.isdigit())
    if ean:
        parts.append(
            f'<rect x="{left:.2f}" y="{by:.2f}" width="{fw * 0.42:.2f}" '
            f'height="8" fill="none" stroke="#3F2620" stroke-width="0.2"/>'
            f'<text x="{left + 1:.2f}" y="{by + 5:.2f}" font-family="Helvetica" '
            f'font-size="{size:.2f}" fill="#3F2620">EAN {escape(ean)}</text>'
        )
    if info.get("qr_url"):
        qx = fx + fw - pad - 8
        parts.append(
            f'<rect x="{qx:.2f}" y="{by:.2f}" width="8" height="8" fill="none" '
            f'stroke="#3F2620" stroke-width="0.2"/>'
            f'<text x="{qx + 4:.2f}" y="{by + 5:.2f}" text-anchor="middle" '
            f'font-family="Helvetica" font-size="{size * 0.9:.2f}" '
            f'fill="#3F2620">QR</text>'
        )
    meta = " · ".join(filter(None, [
        f"NET WT: {info['net_weight']}" if info.get("net_weight") else "",
        f"ITEM NO: {info['item_no']}" if info.get("item_no") else "",
    ]))
    if meta:
        # [his goal of 2026-10-10, item 8: "The ℮ prints as a plain "e": it must be the real estimated sign everywhere."] its ℮ the sign's own shape, a path beside its words
        from apps.ire.estimated_sign import svg_text
        parts.append(svg_text(left, by + 11, meta[:70], size * 0.9,
                              f'font-family="Helvetica" font-size="{size * 0.9:.2f}" font-weight="bold" fill="#3F2620"'))
    return "".join(parts)
