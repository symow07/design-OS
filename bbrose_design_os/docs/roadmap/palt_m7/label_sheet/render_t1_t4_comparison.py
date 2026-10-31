"""A1 = RENDER BOTH — regenerate the parametric label sheet in T1 AND T4
and build the side-by-side comparison page the owner picks from.

Reuses render_label_sheet.py wholesale (same substrate, same fit rule,
same SET_FACE) — this script adds no geometry and no treatment; it calls
the existing parametric functions for exactly the two treatments the
owner asked to see, adds the T4 PDF that did not exist yet, and lays the
two sheets side by side at equal scale.

Owner decisions honoured (owner_blocker_clearance_ingestion.json):
  A1 RENDER_BOTH — the pick is the OWNER's next answer, not this run's.
  A2 surface MATCH_THE_VENDOR_SAMPLE; allocation 24/12 CONFIRMED.
  C1 ACCEPT_SET_FACE (Crimson Text Regular).
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_label_sheet as R  # noqa: E402  (chdirs to bbrose_design_os)

SET_FACE = os.path.join(R.REPO, R.T["SET_FACE"]["file"])
FAMILY = R.T["SET_FACE"]["family"]
PAIR = ["T1_centred_black", "T4_left_black"]


def comparison_page(pngs, out, tile_w_px=2000):
    tiles = []
    for p in pngs:
        img = Image.open(p)
        h = round(img.height * tile_w_px / img.width)
        tiles.append(img.resize((tile_w_px, h), Image.LANCZOS))
    gap, head, cap, foot = 60, 150, 90, 130
    th = max(t.height for t in tiles)
    page_w = 2 * tile_w_px + 3 * gap
    page_h = head + th + cap + foot + 2 * gap
    page = Image.new("RGB", (page_w, page_h), (244, 244, 242))
    d = ImageDraw.Draw(page)
    fh = ImageFont.truetype(SET_FACE, 64)
    fc = ImageFont.truetype(SET_FACE, 46)
    ff = ImageFont.truetype(SET_FACE, 34)
    title = "ES3083 SHADE-LABEL SHEET — T1 (CENTRED) vs T4 (RANGED-LEFT)"
    d.text((page_w / 2 - fh.getlength(title) / 2, 45), title, font=fh,
           fill=(20, 22, 20))
    caps = ["T1 — centred, black, no keyline",
            "T4 — ranged-left, black, no keyline (alignment is the ONLY difference)"]
    for i, (t, c) in enumerate(zip(tiles, caps)):
        x = gap + i * (tile_w_px + gap)
        y = head + gap
        page.paste(t, (x, y))
        d.rectangle([x, y, x + t.width, y + t.height],
                    outline=(180, 180, 180), width=2)
        d.text((x + t.width / 2 - fc.getlength(c) / 2, y + th + 20), c,
               font=fc, fill=(20, 22, 20))
    foot_lines = [
        "Equal scale, sheet 263.00 x 190.00 mm, 24 labels 77.00 x 16.00 mm — all values from the geometry substrate  ·  "
        "Face: %s Regular (SET_FACE, OFL)" % FAMILY,
        "A1 = RENDER BOTH: the pick between T1 and T4 is the owner's next answer  ·  "
        "A2: labels apply per the vendor sample; 24 labels / 12 shades CONFIRMED  ·  "
        "ground shown is the WHITE-STOCK ASSUMPTION (stock undetermined)",
    ]
    fy = page_h - foot - 10
    for fl in foot_lines:
        w = ff.getlength(fl)
        assert w < page_w * 0.97, "footer overflows"
        d.text((page_w / 2 - w / 2, fy), fl, font=ff, fill=(90, 90, 90))
        fy += 52
    page.save(out, dpi=(200, 200))


if __name__ == "__main__":
    pngs = []
    for tr in PAIR:
        png = f"{HERE}/es3083_label_sheet_{tr}.png"
        sz = R.render_png(SET_FACE, 600, tr, png)
        R.write_svg(SET_FACE, FAMILY, tr, f"{HERE}/es3083_label_sheet_{tr}.svg")
        R.write_pdf(SET_FACE, tr, f"{HERE}/es3083_label_sheet_{tr}.pdf")
        pngs.append(png)
        print(f"{tr}: PNG+SVG+PDF regenerated, solved {sz}px @600dpi "
              f"({round(sz * 72 / 600, 2)}pt)")
    comparison_page(pngs, f"{HERE}/es3083_label_sheet_T1_vs_T4_comparison.png")
    print("comparison page written")
