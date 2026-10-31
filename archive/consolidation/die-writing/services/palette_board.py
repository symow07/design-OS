"""Day 10 §5 — the presentation board: one A3 sheet of the Enchanted Rose palette for the owner's boss (Day 15).

The pick and the lid master side by side at one scale, the finish proof, the open tray and the inside of the lid, the back
sticker, the box flat on its die and its front; a caption line per item — what it is, its finishes, its size — with no
scores and no engine words.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from apps.pipeline.services import lid_master as lm

DAY10 = lm.REPO / 'docs' / 'audit' / 'day-10'
OUT = DAY10 / 'board'
SHEET_MM = (420.0, 297.0)
MARGIN_MM = 12.0
GAP_MM = 9.0
CELL_MM = (124.0, 76.0)
CAPTION_PT = 7.5
TITLE_PT = 14.0
SUB_PT = 8.0
BOARD_DPI = 220
GROUND = (0.985, 0.976, 0.968)
INK = (0.13, 0.16, 0.22)
TITLE = 'Enchanted Rose — eyeshadow palette, 18 shades'
SUBTITLE = 'BBROSE · the lid, its finishes, the open palette, the back sticker and the box'


def box_front(box_pdf, out_png):
    """The box's front panel from the box's artwork without its die (engine/box-art-only.pdf) at 300 PPI (die x
    148.35–270.8, y 22.9–215.8 mm; the page's origin 3 mm inside its bleed), turned upright (a quarter clockwise, as the
    box is read lying flat)."""
    import fitz
    with fitz.open(str(box_pdf)) as doc:
        clip = fitz.Rect(lm.pt(148.35 + 3.0), lm.pt(22.9 + 3.0), lm.pt(270.8 + 3.0), lm.pt(215.8 + 3.0))
        pix = doc[0].get_pixmap(dpi=300, clip=clip, alpha=False)
        img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    img.rotate(-90, expand=True).save(out_png)
    return out_png


def sources_of(sources):
    """Where each piece is read from: Day 10's folders by default; [Day 11] ``sources`` (piece → folder) names others
    for the pieces it gives — 'lid', 'tray', 'inside-lid', 'sticker', 'box'."""
    out = {name: DAY10 / name for name in ('lid', 'tray', 'inside-lid', 'sticker', 'box')}
    if sources is not None:
        out.update({k: Path(v) for k, v in sources.items()})
    return out


def detail(out_png, sources=None):
    """The name at full size: the word Rose (the traced letters' own bounds, 2 mm round them) from the 300 PPI flat, placed
    1 : 1 on the sheet."""
    pick = lm.load_pick(lm.PICK)
    rings, _, _ = lm.trace_name(pick, lm.NAME_BOX)
    letters = sorted(lm.parts(lm.rings_area(rings, 24)), key=lambda g: g.bounds[0])
    rose = letters[9:]
    x0 = min(g.bounds[0] for g in rose) - 2.0
    y0 = min(g.bounds[1] for g in rose) - 2.0
    x1 = max(g.bounds[2] for g in rose) + 2.0
    y1 = max(g.bounds[3] for g in rose) + 2.0
    img = Image.open(sources_of(sources)['lid'] / 'lid-master-flat.png').convert('RGB')
    k = 300.0 / lm.MM_PER_INCH
    img.crop((int(x0 * k), int(y0 * k), int(x1 * k), int(y1 * k))).save(out_png)
    return out_png


def items(work, sources=None):
    """The nine cells, in reading order: (picture, caption)."""
    src = sources_of(sources)
    front = box_front(src['box'] / 'engine' / 'box-art-only.pdf', work / 'box-front.png')
    zoom = detail(work / 'lid-detail.png', sources)
    return [
        (lm.PICK, 'The chosen design — the lid as drawn, 190 × 120 mm'),
        (src['lid'] / 'lid-master-flat.png', 'The lid as it prints — 190 × 120 mm, gold foil on the name and the BBROSE letters'),
        (src['lid'] / 'finish-proof.png', 'The lid\'s finish — the gold foil seen as metal under light'),
        (src['tray'] / 'tray-proof.png', 'The open palette — 18 square pans in 3 rows of 6, each shade named, 190 × 120 mm'),
        (src['inside-lid'] / 'inside-lid-flat.png', 'Inside the lid — soft lilac light across plaster, printed, 184 × 114 mm'),
        (src['sticker'] / 'sticker-flat.png', 'The back sticker — English, Spanish and Arabic, 182 × 112 mm'),
        (src['box'] / 'box-flat.png', 'The box, flat — a reverse tuck-end carton, 122 × 14 × 192 mm'),
        (front, 'The box front — the lid\'s design, gold foil on the name and the BBROSE letters'),
        (zoom, 'The name at full size — gold foil lettering over the painted gold'),
    ]


def build(out_dir, *, sources=None):
    """palette-board.pdf (A3 landscape, the pictures resampled to 220 PPI at their placed size, the captions live in
    DM Sans) and palette-board.png (the sheet at 150 PPI). The pieces are Day 10's unless ``sources`` [Day 11] names
    other folders (``sources_of``)."""
    import fitz
    out = Path(out_dir)
    work = out / 'engine'
    work.mkdir(parents=True, exist_ok=True)
    regular = lm.line_face('descriptor_en')
    pdf = fitz.open()
    page = pdf.new_page(width=lm.pt(SHEET_MM[0]), height=lm.pt(SHEET_MM[1]))
    page.draw_rect(page.rect, color=None, fill=GROUND, width=0)
    page.insert_font(fontname='support', fontfile=regular['path'])
    page.insert_text((lm.pt(MARGIN_MM), lm.pt(MARGIN_MM + 5)), TITLE, fontname='support', fontsize=TITLE_PT, color=INK)
    page.insert_text((lm.pt(MARGIN_MM), lm.pt(MARGIN_MM + 11)), SUBTITLE, fontname='support', fontsize=SUB_PT, color=INK)
    top = MARGIN_MM + 18.0
    placed = []
    for i, (src, caption) in enumerate(items(work, sources)):
        r, c = divmod(i, 3)
        cx = MARGIN_MM + c * (CELL_MM[0] + GAP_MM)
        cy = top + r * (CELL_MM[1] + GAP_MM + 4.0)
        img = Image.open(src).convert('RGB')
        w, h = img.size
        scale = min(CELL_MM[0] / w, CELL_MM[1] / h)
        pw, ph = w * scale, h * scale
        if Path(src).name == 'lid-detail.png':
            pw, ph = w / (300.0 / lm.MM_PER_INCH), h / (300.0 / lm.MM_PER_INCH)    # 1 : 1
        px = BOARD_DPI / lm.MM_PER_INCH
        small = img.resize((max(int(pw * px), 1), max(int(ph * px), 1)), Image.LANCZOS)
        tmp = work / ('cell-%d.png' % i)
        small.save(tmp)
        x0 = cx + (CELL_MM[0] - pw) / 2
        y0 = cy + (CELL_MM[1] - ph) / 2
        page.insert_image(fitz.Rect(lm.pt(x0), lm.pt(y0), lm.pt(x0 + pw), lm.pt(y0 + ph)), filename=str(tmp))
        page.insert_text((lm.pt(cx), lm.pt(cy + CELL_MM[1] + 4.5)), caption, fontname='support', fontsize=CAPTION_PT,
                         color=INK)
        placed.append({'cell': i + 1, 'picture': lm.rel(src), 'caption': caption,
                       'placed_mm': [round(v, 2) for v in (x0, y0, x0 + pw, y0 + ph)]})
    pdf.set_metadata({'title': TITLE, 'creator': 'apps/pipeline/services/palette_board.py::build'})
    lm.tag_srgb(pdf)
    pdf.save(str(out / 'palette-board.pdf'), garbage=3, deflate=True)
    pdf.close()
    lm.render_png(out / 'palette-board.pdf', 0, 150.0, out / 'palette-board.png')
    widths = [placed[k]['placed_mm'][2] - placed[k]['placed_mm'][0] for k in (0, 1)]
    record = {'schema': 'day10_board/1', 'sheet_mm': list(SHEET_MM), 'cells': placed,
              'pick_and_master_widths_mm': [round(v, 2) for v in widths],
              'one_scale': bool(abs(widths[0] - widths[1]) <= 0.1)}
    lm.write_json(out / 'board.json', record)
    return record
