"""VQ-1-MASTER-CLOSE-1 §17/§18 — forensic and human-review packages.

Both packages are assembled from records that already exist on disk. Nothing
here measures, scores or renders the candidate; it only presents evidence,
including the negative evidence (§18: "do not hide negative evidence").
"""
from __future__ import annotations

import json
import os

REVIEW_SCHEMA = "vq1_master_structural_review/1.0"
FORENSIC_SCHEMA = "vq1_junction_forensics/1.0"


def _styles():
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    return {
        "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=17,
                             spaceAfter=10, textColor=colors.HexColor("#1d1b1e")),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12,
                             spaceBefore=12, spaceAfter=5,
                             textColor=colors.HexColor("#2A2426")),
        "p": ParagraphStyle("p", fontName="Helvetica", fontSize=9.2,
                            leading=12.6, spaceAfter=4),
        "mono": ParagraphStyle("mono", fontName="Courier", fontSize=7.8,
                               leading=9.6, spaceAfter=3),
        "warn": ParagraphStyle("warn", fontName="Helvetica-Bold", fontSize=9.6,
                               leading=12.8, spaceAfter=5,
                               textColor=colors.HexColor("#9c1f1f")),
    }


def _img(path, max_w, max_h=340):
    from reportlab.platypus import Image as RLImage
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        w, h = im.size
    k = min(max_w / w, max_h / h)
    return RLImage(path, width=w * k, height=h * k)


def _esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def build_pdf(out_pdf: str, title: str, sections: list) -> dict:
    """``sections`` = list of (heading, [blocks]) where a block is
    ("p"|"mono"|"warn", text) or ("img", path)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer,
                                    PageBreak)
    st = _styles()
    doc = SimpleDocTemplate(out_pdf, pagesize=A4,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm,
                            title=title)
    avail = A4[0] - 32 * mm
    flow = [Paragraph(_esc(title), st["h1"])]
    for i, (heading, blocks) in enumerate(sections, start=1):
        flow.append(Paragraph(f"{i}. {_esc(heading)}", st["h2"]))
        for kind, payload in blocks:
            if kind == "img":
                if os.path.exists(payload):
                    flow.append(_img(payload, avail))
                    flow.append(Spacer(1, 5))
                else:
                    flow.append(Paragraph(
                        f"[missing evidence file: {_esc(payload)}]",
                        st["warn"]))
            elif kind == "pagebreak":
                flow.append(PageBreak())
            else:
                for line in str(payload).split("\n"):
                    flow.append(Paragraph(_esc(line) or "&nbsp;", st[kind]))
    doc.build(flow)
    return {"path": out_pdf, "sections": len(sections),
            "size_bytes": os.path.getsize(out_pdf)}


def build_summary_png(out_png: str, title: str, lines: list,
                      images: list | None = None, width: int = 1500) -> dict:
    """A single flat PNG companion so the package is reviewable without a
    PDF viewer. Text only plus optional thumbnails; never a candidate edit."""
    from PIL import Image, ImageDraw
    from apps.ire.vq1_close1 import BG, LABEL, _font
    thumbs = []
    for p in (images or []):
        if os.path.exists(p):
            im = Image.open(p).convert("RGB")
            k = min(460 / im.width, 400 / im.height)
            thumbs.append(im.resize((max(1, int(im.width * k)),
                                     max(1, int(im.height * k)))))
    per_row = max(1, (width - 40) // 480
                  ) if thumbs else 1
    rows = (len(thumbs) + per_row - 1) // per_row if thumbs else 0
    th = max((t.height for t in thumbs), default=0)
    h = 70 + len(lines) * 19 + rows * (th + 16) + 40
    img = Image.new("RGB", (width, h), BG)
    d = ImageDraw.Draw(img)
    d.text((22, 20), title, fill=LABEL, font=_font(23))
    y = 60
    for ln in lines:
        d.text((22, y), ln, fill=LABEL, font=_font(14))
        y += 19
    y += 14
    for i, t in enumerate(thumbs):
        cx = 22 + (i % per_row) * 480
        cy = y + (i // per_row) * (th + 16)
        img.paste(t, (cx, cy))
    img.save(out_png)
    return {"path": out_png, "size": list(img.size)}


def write_json(out_json: str, payload: dict) -> dict:
    with open(out_json, "w") as fh:
        json.dump(payload, fh, indent=1)
    return {"path": out_json, "size_bytes": os.path.getsize(out_json)}
