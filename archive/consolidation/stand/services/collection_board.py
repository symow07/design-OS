"""Day 12 §5 (D-D12-4) — the collection board, page 1: one A3 sheet of the Ẓilāl collection for the owner's boss (Day 15).

The palette's six surfaces, the lipstick's product drawing, wraps, label and carton front, the balm's product drawing,
wraps and label (its carton front where it is built, else "carton — Day 13"), the display's flat artwork and its plan
and elevation; one caption line per item — what it is, its size, its finish — with no scores and no engine words
(``ENGINE_WORDS`` refused before anything is drawn). Day 10's board (palette_board.py) is the pattern.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import product_drawing as pdw
from apps.pipeline.services import stick_carton as sc
from apps.pipeline.services import zilal_balm as zb
from apps.pipeline.services import zilal_lipstick as zl

DAY11 = lm.REPO / 'docs' / 'audit' / 'day-11'
DAY12 = lm.REPO / 'docs' / 'audit' / 'day-12'
DAY13 = lm.REPO / 'docs' / 'audit' / 'day-13'
OUT = DAY12 / 'board'
SHEET_MM = (420.0, 297.0)
MARGIN_MM = 12.0
COLUMNS = 6
COL_GAP_MM = 6.0
HEAD_MM = 22.0                     # the title and the subtitle
ROW_HEAD_MM = 5.0                  # a row's heading above its cells
CAPTION_MM = 5.0                   # the caption's line under its cell
ROW_GAP_MM = 4.0
ROW_SHARE = (0.22, 0.39, 0.39)     # each row's share of the cells' height: the palette's wide pieces need least
CAPTION_PT = 6.5
ROW_PT = 8.0
TITLE_PT = 15.0
SUB_PT = 8.0
BOARD_DPI = 220
PNG_DPI = 150.0
GROUND = (0.985, 0.976, 0.968)
INK = (0.13, 0.16, 0.22)
SOFT = (0.55, 0.57, 0.62)
DOT_BELOW_EM = 0.20                # Ẓ is Z with a dot below (the face has neither the letter nor the combining dot)
DOT_R_EM = 0.075
TITLE = 'Ẓilāl — the Enchanted Rose collection'
SUBTITLE = 'BBROSE · the eyeshadow palette, the lipstick, the lip balm and the counter display that holds them'
ABSENT = 'carton — Day 13'
# a caption names what the piece is, its size and its finish: never how it was made or judged
ENGINE_WORDS = ('engine', 'master', 'gate', 'score', 'jury', 'j1', 'eye', 'trace', 'plate', 'sketch', 'pick', 'round',
                'ppi', 'iou', 'δe', 'de00', 'd-d', 'prompt', 'model', 'pass', 'fail', 'repair', 'proof')


def mm(a, b):
    return '%g × %g mm' % (a, b)


def carton_front(fold_check_json, out_png):
    """A carton's front panel from its artwork without the die (engine/carton-engine.ai, page 1: the page's origin
    the die's less its bleed), at 300 PPI, standing as the carton stands."""
    import fitz
    rec = json.loads(Path(fold_check_json).read_text(encoding='utf-8'))
    x0, y0, x1, y1 = rec['faces']['front']['box_mm']
    b = rec['die']['bleed_mm']
    with fitz.open(str(Path(fold_check_json).parent / 'engine' / 'carton-engine.ai')) as doc:
        pix = doc[0].get_pixmap(dpi=300, clip=fitz.Rect(lm.pt(x0 + b), lm.pt(y0 + b), lm.pt(x1 + b), lm.pt(y1 + b)),
                                alpha=False)
        Image.frombytes('RGB', (pix.width, pix.height), pix.samples).save(out_png)
    return out_png


def carton_holds(fold_check_json):
    """A carton the board shows: built, and holding its own checks — the fold check passed, everything inside its safe
    areas, nothing across a crease. One that does not (the balm's: its copy runs over its creases) is "carton — Day 13".
    [Day 13, §1.3] A record that counts its crossings (``zero_crossings``) holds by the owner's words — "the fold check
    must report zero crossings ... any overflow listed": its fold check passed and no box across a crease or on another
    face; a line still over at the 5 pt floor inside its own panel's margin is listed in its fit report, not hidden."""
    path = Path(fold_check_json)
    if not path.exists():
        return False
    rec = json.loads(path.read_text(encoding='utf-8'))
    if 'zero_crossings' in rec:
        z = rec['zero_crossings']
        return bool(z['fold_check_passed'] and z['crossings'] == 0 and z['nothing_across_a_crease']
                    and z['no_box_on_another_face'])
    return bool(rec['fold_check']['passed'] and rec['all_inside_safe'] and rec['nothing_across_a_crease'])


REBUILT = ('display/die/die.json', 'display/die/plan-elevation.png', 'display/tray/display-flat.png',
           'lipstick/carton/carton-fold-check.json', 'balm/carton/carton-fold-check.json')   # [Day 13] what §1 rebuilt


def rebuilt(rel, day12=DAY12, day13=None):
    """[Day 13] A file a Day 13 repair rebuilt (``rel`` under the day's folder): Day 13's when ``day13`` is given and
    holds it, else Day 12's — so the board and the family sheet lay what prints now, and Day 12's build stays Day 12's."""
    if day13 is not None and (Path(day13) / rel).exists():
        return Path(day13) / rel
    return Path(day12) / rel


def label_round(folder, record_name, out_png):
    """A round label as it is cut: its flat (the die's circle and its bleed, at the PPI the file carries) with the
    bleed outside the circle laid in the board's ground."""
    import numpy as np
    d_mm = json.loads((Path(folder) / record_name).read_text(encoding='utf-8'))['label']['diameter_mm']
    img = Image.open(Path(folder) / 'label-flat.png')
    k = img.info['dpi'][0] / lm.MM_PER_INCH
    rgb = np.asarray(img.convert('RGB')).copy()
    h, w = rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    outside = np.hypot(xx + 0.5 - w / 2, yy + 0.5 - h / 2) > d_mm / 2 * k
    rgb[outside] = [int(round(v * 255)) for v in GROUND]
    Image.fromarray(rgb).save(out_png)
    return out_png


def rows(work, day11=DAY11, day12=DAY12, day13=None):
    """The board's rows, each (heading, [(picture or None, caption)]): the palette, the lipstick, the balm; the display
    the last column of the second and third rows (``DISPLAY_AT``). [Day 13] ``day13``: the files its repairs rebuilt
    (``rebuilt``) — the cartons, the display's flat and its die."""
    lip, balm = day12 / 'lipstick', day12 / 'balm'
    lid_w, lid_h = lm.LID_MM
    box = json.loads((day12 / 'zilal' / 'box' / 'box.json').read_text(encoding='utf-8'))['die']['dimensions_mm']
    lip_in, balm_in = sc.PRODUCTS['lipstick']['inside_mm'], sc.PRODUCTS['lip_balm']['inside_mm']
    die = json.loads(rebuilt('display/die/die.json', day12, day13).read_text(encoding='utf-8'))
    op = die['owner_provisional']
    foot = (op['footprint_width_mm']['value'], op['footprint_depth_mm']['value'])
    head = (op['header_width_mm']['value'], op['header_height_mm']['value'])
    counts = (op['balm_count']['value'], op['lipstick_count']['value'], op['palettes_in_slot']['value'])
    palette = [
        (day12 / 'zilal' / 'lid' / 'lid-master-flat.png', 'The lid — %s, rose-gold foil and emboss' % mm(lid_w, lid_h)),
        (day11 / 'zilal' / 'sides' / 'alternative-mirror' / 'sides-unfolded-print.png',
         'The four sides, unfolded — the lid\'s pattern continued'),
        (day11 / 'zilal' / 'inside-lid' / 'master' / 'inside-lid-flat.png', 'Inside the lid — printed, 184 × 114 mm'),
        (day11 / 'zilal' / 'tray' / 'master' / 'tray-proof.png', 'The open palette — 18 pans in three rows of six'),
        (day11 / 'zilal' / 'sticker' / 'sticker-flat.png', 'The base sticker — English, Spanish, Arabic'),
        (day12 / 'zilal' / 'box' / 'box-flat.png', 'The box, flat — reverse tuck end, %g × %g × %g mm' % (
            box['width_mm'], box['depth_mm'], box['height_mm'])),
    ]
    lip_carton = rebuilt('lipstick/carton/carton-fold-check.json', day12, day13)
    lipstick = [
        (lip / 'closed' / 'lipstick-drawing.png', 'The lipstick, 80 × Ø 20 mm — %s' % pdw.LABEL),
        (lip / 'closed' / 'body-flat.png', 'The body wrap — %s, rose-gold foil' % mm(*zl.WRAP_MM)),
        (lip / 'closed' / 'cap-flat.png', 'The cap wrap — %s' % mm(*zl.WRAP_MM)),
        (label_round(lip / 'closed', 'lipstick.json', work / 'lipstick-label.png'),
         'The base label — Ø 18 mm, the shade Wild Rose'),
        ((carton_front(lip_carton, work / 'lipstick-carton-front.png') if carton_holds(lip_carton) else None),
         ('The lipstick\'s carton front — %g × %g × %g mm' % lip_in) if carton_holds(lip_carton)
         else 'The lipstick\'s %s' % ABSENT),
    ]
    balm_carton = rebuilt('balm/carton/carton-fold-check.json', day12, day13)
    balm_row = [
        (balm / 'master' / 'balm-drawing.png', 'The lip balm, 70 × Ø 18 mm — %s' % pdw.LABEL),
        (balm / 'master' / 'body-flat.png', 'The body wrap — %s, rose-gold foil' % mm(*zb.WRAPS_MM['body'])),
        (balm / 'master' / 'cap-flat.png', 'The cap wrap — %s' % mm(*zb.WRAPS_MM['cap'])),
        (label_round(balm / 'master', 'balm.json', work / 'balm-label.png'), 'The base label — Ø 16 mm, the tint Rosewater'),
        ((carton_front(balm_carton, work / 'balm-carton-front.png') if carton_holds(balm_carton) else None),
         ('The lip balm\'s carton front — %g × %g × %g mm' % balm_in) if carton_holds(balm_carton)
         else 'The lip balm\'s %s' % ABSENT),
    ]
    display = [
        (rebuilt('display/tray/display-flat.png', day12, day13), 'The display, flat on its die — the header in rose gold'),
        (rebuilt('display/die/plan-elevation.png', day12, day13), 'Plan and elevation — %g × %g, header %s' % (
            foot + (mm(*head),))),
    ]
    return [('The eyeshadow palette — 18 shades, %s closed' % mm(lid_w, lid_h), palette, None),
            ('The lipstick — Wild Rose', lipstick + [display[0]],
             'The counter display — %d balms, %d lipsticks, %d palettes' % counts),
            ('The lip balm — Rosewater', balm_row + [display[1]], None)]


DISPLAY_COLUMN = 5                 # the display's two cells: the last column of the second and third rows


def refused_words(caption):
    """The engine words a caption carries (whole words, any case)."""
    import re
    words = set(re.findall(r"[\w\-δ]+", caption.lower()))
    return [w for w in ENGINE_WORDS if w in words]


def title_with_dot(page, x_pt, y_pt, text, size, fontname, font, colour):
    """``text`` set at (x, y) with each Ẓ as Z and a dot below it, centred under the Z's advance."""
    import fitz
    parts = text.split('Ẓ')
    x = x_pt
    for i, part in enumerate(parts):
        if i:
            w = font.text_length('Z', fontsize=size)
            page.insert_text((x, y_pt), 'Z', fontname=fontname, fontsize=size, color=colour)
            page.draw_circle(fitz.Point(x + w / 2, y_pt + DOT_BELOW_EM * size), DOT_R_EM * size, color=None,
                             fill=colour, width=0)
            x += w
        if part:
            page.insert_text((x, y_pt), part, fontname=fontname, fontsize=size, color=colour)
            x += font.text_length(part, fontsize=size)
    return x


def build(out_dir=OUT, *, day11=DAY11, day12=DAY12, day13=None):
    """collection-board.pdf (A3 landscape; the pictures resampled to 220 PPI at their placed size, the captions live in
    DM Sans) and collection-board.png (the sheet at 150 PPI); board.json beside them: every cell's picture (its
    sha256), caption and placed box, the absent pieces, and the checks (one line each, no engine word, the drawings
    labelled). Refuses before drawing a caption that carries an engine word or does not fit its cell's width."""
    import fitz
    out = Path(out_dir)
    work = out / 'engine'
    work.mkdir(parents=True, exist_ok=True)
    face = lm.line_face('descriptor_en')
    font = fitz.Font(fontfile=face['path'])
    cell_w = (SHEET_MM[0] - 2 * MARGIN_MM - (COLUMNS - 1) * COL_GAP_MM) / COLUMNS
    cells_h = SHEET_MM[1] - 2 * MARGIN_MM - HEAD_MM - 2 * ROW_GAP_MM - 3 * (ROW_HEAD_MM + CAPTION_MM)
    cell_hs = [cells_h * share for share in ROW_SHARE]
    if day13 is None:                           # [Day 13] Day 12's call kept as it was when no Day 13 folder is given
        board = rows(work, day11, day12)
    else:
        board = rows(work, day11, day12, day13)
    problems = []
    for _, cells, side_heading in board:
        for caption in [c for _, c in cells] + ([side_heading] if side_heading is not None else []):
            if refused_words(caption):
                problems.append('%r carries %s' % (caption, refused_words(caption)))
            if font.text_length(caption, fontsize=CAPTION_PT) > lm.pt(cell_w):
                problems.append('%r is wider than its cell (%.1f mm)' % (caption, cell_w))
    if problems:
        raise ValueError('the board\'s captions: ' + '; '.join(problems))

    pdf = fitz.open()
    page = pdf.new_page(width=lm.pt(SHEET_MM[0]), height=lm.pt(SHEET_MM[1]))
    page.draw_rect(page.rect, color=None, fill=GROUND, width=0)
    page.insert_font(fontname='support', fontfile=face['path'])
    title_with_dot(page, lm.pt(MARGIN_MM), lm.pt(MARGIN_MM + 6), TITLE, TITLE_PT, 'support', font, INK)
    page.insert_text((lm.pt(MARGIN_MM), lm.pt(MARGIN_MM + 13)), SUBTITLE, fontname='support', fontsize=SUB_PT,
                     color=INK)
    placed, absent = [], []
    px = BOARD_DPI / lm.MM_PER_INCH
    for r, (heading, cells, side_heading) in enumerate(board):
        top = MARGIN_MM + HEAD_MM + sum(cell_hs[:r]) + r * (ROW_HEAD_MM + CAPTION_MM + ROW_GAP_MM)
        cell_h = cell_hs[r]
        page.insert_text((lm.pt(MARGIN_MM), lm.pt(top + 3.5)), heading, fontname='support', fontsize=ROW_PT, color=INK)
        if side_heading is not None:
            dx = MARGIN_MM + DISPLAY_COLUMN * (cell_w + COL_GAP_MM)
            page.insert_text((lm.pt(dx), lm.pt(top + 3.5)), side_heading, fontname='support', fontsize=CAPTION_PT,
                             color=INK)
        for c, (src, caption) in enumerate(cells):
            cx = MARGIN_MM + c * (cell_w + COL_GAP_MM)
            cy = top + ROW_HEAD_MM
            if src is None:
                page.draw_rect(fitz.Rect(lm.pt(cx), lm.pt(cy), lm.pt(cx + cell_w), lm.pt(cy + cell_h)), color=SOFT,
                               width=0.4, dashes='[2 2] 0')
                absent.append(caption)
                box = None
            else:
                img = Image.open(src).convert('RGB')
                w, h = img.size
                scale = min(cell_w / w, cell_h / h)
                pw, ph = w * scale, h * scale
                small = img.resize((max(int(pw * px), 1), max(int(ph * px), 1)), Image.LANCZOS)
                tmp = work / ('cell-%d-%d.png' % (r, c))
                small.save(tmp)
                x0, y0 = cx + (cell_w - pw) / 2, cy + (cell_h - ph) / 2
                page.insert_image(fitz.Rect(lm.pt(x0), lm.pt(y0), lm.pt(x0 + pw), lm.pt(y0 + ph)), filename=str(tmp))
                box = [round(v, 2) for v in (x0, y0, x0 + pw, y0 + ph)]
            page.insert_text((lm.pt(cx), lm.pt(cy + cell_h + 3.6)), caption, fontname='support', fontsize=CAPTION_PT,
                             color=INK)
            placed.append({'row': r + 1, 'column': c + 1, 'picture': None if src is None else lm.rel(src),
                           'sha256': None if src is None else lm.sha256(src), 'caption': caption, 'placed_mm': box})
    second = second_page(pdf, golden_hour(day11), face, font, work)
    pdf.set_metadata({'title': TITLE, 'creator': 'apps/pipeline/services/collection_board.py::build'})
    lm.tag_srgb(pdf)
    pdf.save(str(out / 'collection-board.pdf'), garbage=3, deflate=True)
    pdf.close()
    lm.render_png(out / 'collection-board.pdf', 0, PNG_DPI, out / 'collection-board.png')
    lm.render_png(out / 'collection-board.pdf', 1, PNG_DPI, out / 'collection-board-2.png')
    captions = [p['caption'] for p in placed + second]
    record = {'schema': 'day12_board/1', 'rule': 'D-D12-4, page 1', 'sheet_mm': list(SHEET_MM),
              'cell_mm': {'width': round(cell_w, 2), 'heights': [round(v, 2) for v in cell_hs]}, 'cells': placed, 'absent': absent,
              'checks': {'captions_one_line_inside_their_cells': True,
                         'no_engine_word': not any(refused_words(c) for c in captions),
                         'drawings_labelled': all(pdw.LABEL in p['caption'] for p in placed
                                                  if p['picture'] and p['picture'].endswith('-drawing.png'))},
              'page_2': {'rule': 'D-D12-4, page 2: Golden Hour as test one', 'cells': second},
              'files': {'pdf': lm.rel(out / 'collection-board.pdf'), 'png': lm.rel(out / 'collection-board.png'),
                        'png_page_2': lm.rel(out / 'collection-board-2.png')}}
    if day13 is not None:
        record['rebuilt_on_day13'] = sorted(lm.rel(rebuilt(r, day12, day13)) for r in REBUILT
                                            if rebuilt(r, day12, day13).parent.is_relative_to(Path(day13)))
    lm.write_json(out / 'board.json', record)
    return record


# ---- page 2 (D-D12-4, cuttable): Golden Hour as test one — the palette as first closed (Day 11, D-D11-5)
GOLDEN_TITLE = 'Golden Hour — test one'
GOLDEN_SUB = 'BBROSE · the Enchanted Rose palette as first closed: the lid, the inside, the open palette, the sticker and the box'
GOLDEN_COLUMNS = 3
GOLDEN_GAP_MM = 9.0


def golden_hour(day11=DAY11):
    """Golden Hour's five pieces as its page shows them (docs/audit/day-11/pages/golden-hour.json), each (picture,
    caption); the box's size read from its fold check."""
    gh = day11 / 'golden-hour'
    box = json.loads((gh / 'box' / 'box-fold-check.json').read_text(encoding='utf-8'))['die']['dimensions_mm']
    lid_w, lid_h = lm.LID_MM
    return [(gh / 'lid' / 'lid-master-flat.png', 'The lid — %s, gold foil on the name, the bars embossed' % mm(lid_w, lid_h)),
            (day11.parent / 'day-10' / 'inside-lid' / 'inside-lid-flat.png', 'Inside the lid — printed, 184 × 114 mm'),
            (gh / 'tray' / 'tray-proof.png', 'The open palette — 18 pans in three rows of six'),
            (gh / 'sticker' / 'sticker-flat.png', 'The base sticker — English, Spanish, Arabic'),
            (gh / 'box' / 'box-flat.png', 'The box, flat — reverse tuck end, %g × %g × %g mm' % (
                box['width_mm'], box['depth_mm'], box['height_mm']))]


def second_page(pdf, cells, face, font, work):
    """Page 2 on the open document: the five pieces in a 3 + 2 grid, a caption line each (refused as page 1's are)."""
    import fitz
    cell_w = (SHEET_MM[0] - 2 * MARGIN_MM - (GOLDEN_COLUMNS - 1) * GOLDEN_GAP_MM) / GOLDEN_COLUMNS
    cell_h = (SHEET_MM[1] - 2 * MARGIN_MM - HEAD_MM - 2 * CAPTION_MM - GOLDEN_GAP_MM) / 2
    problems = ['%r carries %s' % (c, refused_words(c)) for _, c in cells if refused_words(c)]
    problems += ['%r is wider than its cell' % c for _, c in cells if font.text_length(c, fontsize=CAPTION_PT) > lm.pt(cell_w)]
    if problems:
        raise ValueError('the board\'s second page: ' + '; '.join(problems))
    page = pdf.new_page(width=lm.pt(SHEET_MM[0]), height=lm.pt(SHEET_MM[1]))
    page.draw_rect(page.rect, color=None, fill=GROUND, width=0)
    page.insert_font(fontname='support', fontfile=face['path'])
    page.insert_text((lm.pt(MARGIN_MM), lm.pt(MARGIN_MM + 6)), GOLDEN_TITLE, fontname='support', fontsize=TITLE_PT, color=INK)
    page.insert_text((lm.pt(MARGIN_MM), lm.pt(MARGIN_MM + 13)), GOLDEN_SUB, fontname='support', fontsize=SUB_PT, color=INK)
    placed = []
    for i, (src, caption) in enumerate(cells):
        r, c = divmod(i, GOLDEN_COLUMNS)
        cx = MARGIN_MM + c * (cell_w + GOLDEN_GAP_MM)
        cy = MARGIN_MM + HEAD_MM + r * (cell_h + CAPTION_MM + GOLDEN_GAP_MM)
        with Image.open(src) as img:
            w, h = img.size
        s = min(cell_w / w, cell_h / h)
        box = place(page, src, cx + (cell_w - w * s) / 2, cy + (cell_h - h * s) / 2, w * s, h * s, work,
                    'golden-%d.png' % i)
        page.insert_text((lm.pt(cx), lm.pt(cy + cell_h + 3.6)), caption, fontname='support', fontsize=CAPTION_PT, color=INK)
        placed.append({'row': r + 1, 'column': c + 1, 'picture': lm.rel(src), 'sha256': lm.sha256(src), 'caption': caption,
                       'placed_mm': box})
    return placed


# ---- the family sheet (D-D12-2): the display's flat artwork on its die, its plan and elevation, and the three products'
# fronts at one scale (the palette's lid as it faces the shopper; each stick's front view from its product drawing)
FAMILY = DAY12 / 'display' / 'family'
FAMILY_TITLE = 'Ẓilāl — the family counter display'
FAMILY_SUB = 'BBROSE · the display flat on its die, its plan and elevation, and the three products it holds at one scale'
FRONTS_SCALE = 1 / 1.5             # the three fronts at 1 : 1.5
FRONTS_GAP_MM = 12.0
FRONT_TOLERANCE_MM = 0.3           # a front cropped from its drawing measures its record's size within this
SCALE_BAR_MM = 50.0


def stick_front(drawing_png, drawing_json, height_mm, out_png):
    """A stick's front view cropped from its product drawing (D-D12-1.4: drawn at ``product_drawing.PX_PER_MM``, the
    front view first, its left edge at the sheet's margin): the first run of drawn rows in the front view's columns.
    Returns (out_png, size_mm); refuses a crop whose size is not the record's (Ø, height) within the tolerance."""
    import numpy as np
    rec = json.loads(Path(drawing_json).read_text(encoding='utf-8'))
    k = rec['px_per_mm']
    rgb = np.asarray(Image.open(drawing_png).convert('RGB'))
    m = int(pdw.MARGIN_MM * k)
    band = rgb[:, max(m - 4, 0):m + int(np.ceil(rec['case_d_mm'] * k)) + 4]
    drawn = (band != np.array(pdw.SHEET, np.uint8)).any(axis=2)
    rows_ = np.nonzero(drawn.any(axis=1))[0]
    top = rows_[0]
    gaps = np.nonzero(np.diff(rows_) > 1)[0]
    bottom = rows_[gaps[0]] if len(gaps) else rows_[-1]
    cols = np.nonzero(drawn[top:bottom + 1].any(axis=0))[0]
    x0 = max(m - 4, 0) + cols[0]
    crop = rgb[top:bottom + 1, x0:x0 + len(cols)]
    size = (crop.shape[1] / k, crop.shape[0] / k)
    if abs(size[0] - rec['case_d_mm']) > FRONT_TOLERANCE_MM or abs(size[1] - height_mm) > FRONT_TOLERANCE_MM:
        raise ValueError('%s: the front crop measures %.2f × %.2f mm, not Ø %g × %g' % (
            drawing_png, size[0], size[1], rec['case_d_mm'], height_mm))
    Image.fromarray(crop).save(out_png)
    return out_png, size


def fit_box(size, box_w, box_h):
    s = min(box_w / size[0], box_h / size[1])
    return size[0] * s, size[1] * s


def place(page, src, x0, y0, w_mm, h_mm, work, name):
    """``src`` resampled to the board's PPI at its placed size and drawn at (x0, y0) mm."""
    import fitz
    px = BOARD_DPI / lm.MM_PER_INCH
    img = Image.open(src).convert('RGB')
    tmp = work / name
    img.resize((max(int(w_mm * px), 1), max(int(h_mm * px), 1)), Image.LANCZOS).save(tmp)
    page.insert_image(fitz.Rect(lm.pt(x0), lm.pt(y0), lm.pt(x0 + w_mm), lm.pt(y0 + h_mm)), filename=str(tmp))
    return [round(v, 2) for v in (x0, y0, x0 + w_mm, y0 + h_mm)]


def family_sheet(out_dir=FAMILY, *, day12=DAY12, day13=None):
    """family-sheet.pdf (A3 landscape) and family-sheet.png (150 PPI); family.json beside them: each piece's picture
    (sha256), placed box and the scale it is shown at; the three fronts' sizes measured against their records."""
    import fitz
    out = Path(out_dir)
    work = out / 'engine'
    work.mkdir(parents=True, exist_ok=True)
    face = lm.line_face('descriptor_en')
    font = fitz.Font(fontfile=face['path'])
    flat = rebuilt('display/tray/display-flat.png', day12, day13)       # [Day 13] the rebuilt flat and die, when given
    plan = rebuilt('display/die/plan-elevation.png', day12, day13)
    die = json.loads(rebuilt('display/die/die.json', day12, day13).read_text(encoding='utf-8'))
    lip_front, lip_mm = stick_front(day12 / 'lipstick' / 'closed' / 'lipstick-drawing.png',
                                    day12 / 'lipstick' / 'closed' / 'lipstick-drawing.json', 80.0,
                                    work / 'lipstick-front.png')
    balm_front, balm_mm = stick_front(day12 / 'balm' / 'master' / 'balm-drawing.png',
                                      day12 / 'balm' / 'master' / 'balm-drawing.json', 70.0, work / 'balm-front.png')
    fronts = [(day12 / 'zilal' / 'lid' / 'lid-master-flat.png', tuple(lm.LID_MM), 'the palette %s' % mm(*lm.LID_MM)),
              (lip_front, lip_mm, 'the lipstick 80 × Ø 20 mm'), (balm_front, balm_mm, 'the lip balm 70 × Ø 18 mm')]
    pdf = fitz.open()
    page = pdf.new_page(width=lm.pt(SHEET_MM[0]), height=lm.pt(SHEET_MM[1]))
    page.draw_rect(page.rect, color=None, fill=GROUND, width=0)
    page.insert_font(fontname='support', fontfile=face['path'])
    title_with_dot(page, lm.pt(MARGIN_MM), lm.pt(MARGIN_MM + 6), FAMILY_TITLE, TITLE_PT, 'support', font, INK)
    page.insert_text((lm.pt(MARGIN_MM), lm.pt(MARGIN_MM + 13)), FAMILY_SUB, fontname='support', fontsize=SUB_PT,
                     color=INK)

    def caption(x, y, words):
        page.insert_text((lm.pt(x), lm.pt(y)), words, fontname='support', fontsize=CAPTION_PT, color=INK)

    top = MARGIN_MM + HEAD_MM
    left_w = 200.0
    flat_mm = die['die']['sheet_mm']
    img = Image.open(flat)
    k_flat = img.info['dpi'][0] / lm.MM_PER_INCH
    flat_size = (img.width / k_flat, img.height / k_flat)
    fw, fh = fit_box(flat_size, left_w, SHEET_MM[1] - MARGIN_MM - top - CAPTION_MM)
    record = {'schema': 'day12_family/1', 'rule': 'D-D12-2, the family sheet', 'pieces': []}
    box = place(page, flat, MARGIN_MM, top, fw, fh, work, 'flat.png')
    words = 'The display, flat on its die — %g × %g mm sheet, shown at 1 : %.1f' % (
        flat_mm[0], flat_mm[1], flat_size[0] / fw)
    caption(MARGIN_MM, top + fh + 3.6, words)
    record['pieces'].append({'piece': 'flat artwork on the die', 'picture': lm.rel(flat), 'sha256': lm.sha256(flat),
                             'placed_mm': box, 'caption': words, 'sheet_mm': [round(v, 1) for v in flat_size],
                             'die_record_sheet_mm': flat_mm})
    rx = MARGIN_MM + left_w + 10.0
    rw = SHEET_MM[0] - MARGIN_MM - rx
    img = Image.open(plan)
    k_plan = img.info['dpi'][0] / lm.MM_PER_INCH
    plan_size = (img.width / k_plan, img.height / k_plan)
    pw, ph = fit_box(plan_size, rw, 118.0)
    box = place(page, plan, rx, top, pw, ph, work, 'plan.png')
    words = 'Plan, front elevation and side section — drawn at 1 : 2, shown at 1 : %.1f' % (2 * plan_size[0] / pw)
    caption(rx, top + ph + 3.6, words)
    record['pieces'].append({'piece': 'plan and elevation', 'picture': lm.rel(plan), 'sha256': lm.sha256(plan),
                             'placed_mm': box, 'caption': words})
    base = SHEET_MM[1] - MARGIN_MM - CAPTION_MM - 8.0       # the three stand on one line
    x = rx
    shown = []
    for src, size, name in fronts:
        w, h = size[0] * FRONTS_SCALE, size[1] * FRONTS_SCALE
        box = place(page, src, x, base - h, w, h, work, 'front-%s.png' % len(shown))
        shown.append({'piece': name, 'picture': lm.rel(src), 'sha256': lm.sha256(src), 'size_mm': [round(v, 2) for v in size],
                      'placed_mm': box})
        x += w + FRONTS_GAP_MM
    page.draw_line(fitz.Point(lm.pt(rx), lm.pt(base + 3)), fitz.Point(lm.pt(rx + SCALE_BAR_MM * FRONTS_SCALE),
                   lm.pt(base + 3)), color=INK, width=0.6)
    caption(rx + SCALE_BAR_MM * FRONTS_SCALE + 2, base + 4, '%g mm' % SCALE_BAR_MM)
    words = 'The three at one scale, 1 : %g — %s' % (1 / FRONTS_SCALE, ', '.join(n for _, _, n in fronts))
    caption(rx, base + 3.0 + CAPTION_MM + 1.5, words)
    record['fronts'] = {'scale': '1 : %g' % (1 / FRONTS_SCALE), 'caption': words, 'pieces': shown,
                        'measured_against_the_records_within_mm': FRONT_TOLERANCE_MM}
    if font.text_length(words, fontsize=CAPTION_PT) > lm.pt(rw):
        raise ValueError('the fronts\' caption is wider than its column')
    pdf.set_metadata({'title': FAMILY_TITLE, 'creator': 'apps/pipeline/services/collection_board.py::family_sheet'})
    lm.tag_srgb(pdf)
    pdf.save(str(out / 'family-sheet.pdf'), garbage=3, deflate=True)
    pdf.close()
    lm.render_png(out / 'family-sheet.pdf', 0, PNG_DPI, out / 'family-sheet.png')
    record['files'] = {'pdf': lm.rel(out / 'family-sheet.pdf'), 'png': lm.rel(out / 'family-sheet.png')}
    lm.write_json(out / 'family.json', record)
    return record
