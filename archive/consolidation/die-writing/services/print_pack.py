"""Day 13 §3 — the print pack for Day 14 ($0): one folder a print shop can take as it is.

[The owner, the Day 13 prompt §3 as typed (CURRENT_DECISIONS.md "## Day 13"): "every piece's PDF at 100 % with crop
marks and a 50 mm bar, its paper, count and sheet (A4 or A3, A3 tiled with overlap marks where larger)".]

A piece is a manifest row: its items (a source file and a page, placed whole or by a clip), each item's trim read from
the file's own TrimBox or from the record (never guessed), its bleed per side (the clip less the trim), its paper, its
count and its fold lines. Every item is placed at exactly 1 : 1 — ``show_pdf_page`` into a rectangle of the clip's own
millimetres, never fitted — on the smallest sheet that holds it with its marks (A4 before A3; portrait or landscape,
never turned). A piece larger than A3 is tiled over A3 landscape on ``counter_tray_header_sheets.tile_grid``'s grid
with that exporter's window, overlap bands and circled crosses, so the display's die and its artwork fall on the SAME
tiles. Every page carries crop marks at each trim's corners (``lid_master.crop_marks``), a 50 mm bar
(``counter_tray_header_sheets._bar``'s look: five 10 mm segments, black and white, outlined) and its words outside the
trim. A page that is itself a whole A3 sheet (the board, the plan and elevation) is copied at 1 : 1 and carries its bar
in a patch of its own ground found by looking; it has no trim to mark and says so.

What a page holds is then read back from the written file (``placements``, ``bar_length``, ``crop_marks_found``,
``overlap_marks_found``): each placed form's matrix and box, the bar's length from its drawn segments, the marks'
segments. The record's numbers are the file's.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import fitz
import numpy as np

from apps.pipeline.services import lid_master as lm

PT_PER_MM = lm.PT_PER_MM
MM_PER_PT = 1.0 / PT_PER_MM
REPO = lm.REPO
AUDIT = REPO / 'docs' / 'audit'
OUT = AUDIT / 'day-13' / 'print-pack'
SCHEMA = 'day13_print_pack/1'

#: the sheets, smallest first; within a size, portrait before landscape (the paper is never turned under the piece)
SHEETS = (('A4', 'portrait', 210.0, 297.0), ('A4', 'landscape', 297.0, 210.0),
          ('A3', 'portrait', 297.0, 420.0), ('A3', 'landscape', 420.0, 297.0))
EDGE_MM = 6.0                      # nothing drawn nearer the paper's edge (an office printer's band is 4-5 mm)
CROP_GAP_MM = lm.CROP_MARK_GAP_MM  # lid_master's rule: 5 mm marks, 3 mm off the trim
CROP_LEN_MM = lm.CROP_MARK_MM
REACH_MM = CROP_GAP_MM + CROP_LEN_MM + 1.0     # an item's cell: its trim plus the marks' reach on each side
FOOT_MM = 17.0                     # the words and the bar, under the items
FOLD_MARK_MM = 4.0                 # palette_box's fold mark: dashed, 4 mm, from 1 mm past the bleed
FOLD_MARK_OFF_MM = 1.0
BAR_MM = 50.0
BAR_SEGMENTS = 5
BAR_HEIGHT_MM = 3.0
BAR_TOLERANCE_MM = 0.1
CAPTION_PT = 6.0
LINE_MM = 3.0
FACE = REPO / 'bbrose_design_os' / 'static' / 'fonts' / 'brand2026' / 'Montserrat' / 'Montserrat-Regular.ttf'
FACE_NAME = 'packface'
PRINT_WORDS = 'print at 100 %, no fit: the bar measures 50 mm'
#: the tiles' marks, as counter_tray_header_sheets.write_tiles_pdf draws them
TILE_CROP_GAP_MM = 2.0
TILE_CROP_LEN_MM = 6.0
TILE_REG_RADIUS_MM = 3.0
TILE_REG_ARM_MM = 4.5
TILE_GREY = (0x88 / 255.0, 0x88 / 255.0, 0x88 / 255.0)
TILE_BAR_X_MM = 210.0              # the bar at the window's left + 210 mm, its foot 12.5 mm over the paper's foot
TILE_BAR_FOOT_MM = 12.5
#: a patch of a page's own ground: every pixel within this of the page's commonest colour, read at this scale
GROUND_TOLERANCE = 8
GROUND_PX_PER_MM = 4.0
GROUND_CLEAR_MM = 2.0
#: the finish masks print black on white: no pixel's channels further apart than this (grey edges are not colour)
MASK_CHROMA_MAX = 2
#: the owner's paper weights, his three classes as typed (⟪PROVISIONAL⟫); every other piece says it is not in his list
PAPER = {
    'card': {'words': '300 gsm card', 'class': 'cartons and labels', 'owners': True},
    'wrap': {'words': '250 gsm', 'class': 'wraps', 'owners': True},
    'flute': {'words': 'E-flute', 'class': 'the display', 'owners': True},
}
PROVISIONAL = '⟪PROVISIONAL⟫'


def _pt(value_mm):
    return value_mm * PT_PER_MM


def _mm(value_pt):
    return value_pt * MM_PER_PT


def _rect_mm(rect):
    return [round(_mm(rect.x0), 4), round(_mm(rect.y0), 4), round(_mm(rect.x1), 4), round(_mm(rect.y1), 4)]


def _r(box_mm):
    return fitz.Rect(_pt(box_mm[0]), _pt(box_mm[1]), _pt(box_mm[2]), _pt(box_mm[3]))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def page_words(text):
    """The words a page sets, in the embedded face (Montserrat Regular holds Ẓ, ā, ×, → and ℮); the record's
    double angle brackets are spelled out, since the face has none."""
    return text.replace(PROVISIONAL, 'PROVISIONAL')


def face_chars():
    """Every character the embedded face can set (its cmap)."""
    from fontTools.ttLib import TTFont
    return set(TTFont(str(FACE), lazy=True).getBestCmap())


# --- sources: opened once, read for their trim -------------------------------------------------------------------------


class Sources:
    """Every source opened once for the build: one output file grafts a source page once however many times it is
    placed (the display's 80 MB artwork once for its twelve tiles, never twelve times)."""

    def __init__(self):
        self.docs = {}

    def open(self, path):
        key = str(path)
        if key not in self.docs:
            self.docs[key] = fitz.open(key)
        return self.docs[key]

    def close(self):
        for doc in self.docs.values():
            doc.close()
        self.docs = {}


def opens(path):
    """A file is there to be used when it exists and reads: a PDF (or .ai) with at least one page, a JSON that parses."""
    path = Path(path)
    if not path.is_file():
        return False
    if path.suffix == '.json':
        try:
            json.loads(path.read_text(encoding='utf-8'))
        except ValueError:
            return False
        return True
    try:
        with fitz.open(str(path)) as doc:
            return doc.page_count > 0
    except (RuntimeError, ValueError):          # PyMuPDF's FileDataError is a RuntimeError
        return False


def trim_of(doc, pno):
    """A page's size and trim (mm, the page's own top-left origin): its TrimBox when the file carries one, else the
    page itself; and which. A turned page or one whose box does not start at its origin is refused (1 : 1 would lie)."""
    page = doc[pno]
    if page.rotation != 0:
        raise ValueError('page %d is turned %d°: placed at 1 : 1 its millimetres would not be the file\'s' % (pno, page.rotation))
    media = page.mediabox
    if abs(media.x0) > 1e-6 or abs(media.y0) > 1e-6:
        raise ValueError('page %d\'s MediaBox starts at %s, not its origin' % (pno, media.tl))
    if doc.xref_get_key(page.xref, 'TrimBox')[0] == 'null':
        return _rect_mm(page.rect), _rect_mm(page.rect), 'the page itself (the file carries no TrimBox)'
    return _rect_mm(page.rect), _rect_mm(page.trimbox), 'the file\'s TrimBox'


def crease_lines(doc, pno):
    """The page's axis-aligned crease lines (mm): every straight segment of its 'crease' layer, one per position along
    each axis (a fold drawn in pieces is one fold line)."""
    lines = {}
    for d in doc[pno].get_drawings():
        if d['layer'] != 'crease':
            continue
        for it in d['items']:
            if it[0] != 'l':
                continue
            a, b = it[1], it[2]
            if abs(a.x - b.x) < 0.01:
                key = ('v', round(_mm(a.x), 2))
            elif abs(a.y - b.y) < 0.01:
                key = ('h', round(_mm(a.y), 2))
            else:
                continue
            lines[key] = True
    out = []
    for axis, at in sorted(lines):
        if axis == 'v':
            out.append([at, 0.0, at, 1.0])
        else:
            out.append([0.0, at, 1.0, at])
    return out


def item(sources, src, pno, label, clip_mm=None, trim_mm=None, overlays=(), folds_mm=(), trim_from=None):
    """One thing placed on a sheet: ``src`` page ``pno`` whole (or ``clip_mm`` of it), its trim from the file's
    TrimBox (or ``trim_mm`` with ``trim_from`` naming the record it came from), its bleed per side (the clip less the
    trim), the pages laid over it at the same rectangle (a label's die), and its fold lines (axis-aligned, mm)."""
    doc = sources.open(src)
    page_mm, file_trim, how = trim_of(doc, pno)
    clip = list(page_mm) if clip_mm is None else [float(v) for v in clip_mm]
    trim = file_trim if trim_mm is None else [float(v) for v in trim_mm]
    if trim_mm is not None:
        how = trim_from
    bleed = {'left': round(trim[0] - clip[0], 4), 'top': round(trim[1] - clip[1], 4),
             'right': round(clip[2] - trim[2], 4), 'bottom': round(clip[3] - trim[3], 4)}
    if min(bleed.values()) < -1e-6:
        raise ValueError('%s: the trim %s runs outside the placed area %s' % (label, trim, clip))
    for o_src, o_pno in overlays:
        o_page, _, _ = trim_of(sources.open(o_src), o_pno)
        if o_page != page_mm:
            raise ValueError('%s: the overlay page %s is not the size of the page it lies on %s' % (label, o_page, page_mm))
    return {'src': Path(src), 'page': pno, 'label': label, 'page_mm': page_mm, 'clip_mm': clip, 'trim_mm': trim,
            'trim_from': how, 'bleed_mm': bleed, 'overlays': [(Path(s), p) for s, p in overlays],
            'folds_mm': [list(f) for f in folds_mm]}


# --- layout: the smallest sheet, shelf-packed --------------------------------------------------------------------------


def _cell(it):
    tx0, ty0, tx1, ty1 = it['trim_mm']
    return tx1 - tx0 + 2 * REACH_MM, ty1 - ty0 + 2 * REACH_MM


def shelf(items, sheet):
    """``items`` in rows on ``sheet`` (left to right, a new row when the next does not fit), as many pages as they need,
    each page's block centred across and in the room above the foot; each placed item's trim REACH_MM inside its cell.
    None when an item's cell does not fit the sheet. Returns pages: lists of (item, x, y), (x, y) the clip's top-left
    corner (mm)."""
    _, _, w, h = sheet
    room_w, room_h = w - 2 * EDGE_MM, h - EDGE_MM - FOOT_MM - EDGE_MM
    if any(_cell(it)[0] > room_w + 1e-9 or _cell(it)[1] > room_h + 1e-9 for it in items):
        return None
    pages, rows, row, row_w, row_h, used_h = [], [], [], 0.0, 0.0, 0.0
    for it in items:
        cw, ch = _cell(it)
        if row and (row_w + cw > room_w + 1e-9 or used_h + max(row_h, ch) > room_h + 1e-9):
            rows.append(row)
            used_h += row_h
            row, row_w, row_h = [], 0.0, 0.0
        if not row and used_h + ch > room_h + 1e-9:
            pages.append(rows)
            rows, used_h = [], 0.0
        row.append(it)
        row_w += cw
        row_h = max(row_h, ch)
    rows.append(row)
    pages.append(rows)
    placed = []
    for page_rows in pages:
        block_w = max(sum(_cell(i)[0] for i in r) for r in page_rows)
        x_left = (w - block_w) / 2.0
        block_h = sum(max(_cell(i)[1] for i in r) for r in page_rows)
        out, y = [], EDGE_MM + (room_h - block_h) / 2.0
        for r in page_rows:
            x = x_left
            for it in r:
                tx0, ty0 = it['trim_mm'][0], it['trim_mm'][1]
                cx0, cy0 = it['clip_mm'][0], it['clip_mm'][1]
                out.append((it, x + REACH_MM - (tx0 - cx0), y + REACH_MM - (ty0 - cy0)))
                x += _cell(it)[0]
            y += max(_cell(i)[1] for i in r)
        placed.append(out)
    return placed


def layout(items):
    """The smallest sheet that holds the largest item with its marks — A4 before A3; of a size, the way round that
    needs the fewer pages, portrait on a tie — and the items packed on it. None when no A3 holds it (it is tiled)."""
    for size in ('A4', 'A3'):
        best = None
        for sheet in SHEETS:
            if sheet[0] != size:
                continue
            pages = shelf(items, sheet)
            if pages is not None and (best is None or len(pages) < len(best[1])):
                best = (sheet, pages)
        if best is not None:
            return best
    return None


# --- what a page draws ------------------------------------------------------------------------------------------------


def place(page, sources, it, x_mm, y_mm):
    """``it`` at 1 : 1, its clip's top-left corner at (x, y): the rectangle is the clip's own size, so the form's matrix
    is a translation. Its overlays at the same rectangle. Returns the rectangle (mm)."""
    cx0, cy0, cx1, cy1 = it['clip_mm']
    rect_mm = [x_mm, y_mm, x_mm + cx1 - cx0, y_mm + cy1 - cy0]
    page.show_pdf_page(_r(rect_mm), sources.open(it['src']), it['page'], clip=_r(it['clip_mm']))
    for o_src, o_pno in it['overlays']:
        page.show_pdf_page(_r(rect_mm), sources.open(o_src), o_pno, clip=_r(it['clip_mm']))
    return rect_mm


def on_page(it, x_mm, y_mm, box_mm):
    """A box in the item's source millimetres, where it lands on the page when the clip's corner is at (x, y)."""
    dx, dy = x_mm - it['clip_mm'][0], y_mm - it['clip_mm'][1]
    return [round(box_mm[0] + dx, 4), round(box_mm[1] + dy, 4), round(box_mm[2] + dx, 4), round(box_mm[3] + dy, 4)]


def fold_marks(page, trim_page_mm, folds_page_mm, bleed_mm):
    """palette_box's fold marks: at both ends of every fold line, outside the trim and its bleed (from 1 mm past the
    bleed, 4 mm long, dashed, black) — never across the printed face. Returns the marks drawn (mm segments)."""
    x0, y0, x1, y1 = trim_page_mm
    drawn = []
    for fx0, fy0, fx1, fy1 in folds_page_mm:
        if abs(fx0 - fx1) < 1e-6:
            for edge, s, b in ((y0, -1, bleed_mm['top']), (y1, 1, bleed_mm['bottom'])):
                a = edge + s * (b + FOLD_MARK_OFF_MM)
                drawn.append([fx0, a, fx0, a + s * FOLD_MARK_MM])
        else:
            for edge, s, b in ((x0, -1, bleed_mm['left']), (x1, 1, bleed_mm['right'])):
                a = edge + s * (b + FOLD_MARK_OFF_MM)
                drawn.append([a, fy0, a + s * FOLD_MARK_MM, fy0])
    for seg in drawn:
        page.draw_line(fitz.Point(_pt(seg[0]), _pt(seg[1])), fitz.Point(_pt(seg[2]), _pt(seg[3])), color=(0, 0, 0),
                       width=0.25, dashes='[1 1] 0')
    return [[round(v, 4) for v in seg] for seg in drawn]


def draw_bar(page, x_mm, y_mm):
    """The 50 mm bar in counter_tray_header_sheets._bar's look: five 10 mm segments 3 mm tall, black and white in turn,
    each outlined at 0.5 pt, and "50 mm" 3 mm past its end. (x, y) is its top-left corner; returns its rect (mm)."""
    seg = BAR_MM / BAR_SEGMENTS
    for i in range(BAR_SEGMENTS):
        fill = (0, 0, 0) if i % 2 == 0 else (1, 1, 1)
        page.draw_rect(_r([x_mm + i * seg, y_mm, x_mm + (i + 1) * seg, y_mm + BAR_HEIGHT_MM]), color=(0, 0, 0),
                       fill=fill, width=0.5)
    words(page, '50 mm', x_mm + BAR_MM + 3.0, y_mm + BAR_HEIGHT_MM - 0.6)
    return [round(x_mm, 4), round(y_mm, 4), round(x_mm + BAR_MM, 4), round(y_mm + BAR_HEIGHT_MM, 4)]


def words(page, text, x_mm, baseline_mm):
    """One line of the page's small type, in the embedded face, black."""
    page.insert_font(fontname=FACE_NAME, fontfile=str(FACE))
    page.insert_text(fitz.Point(_pt(x_mm), _pt(baseline_mm)), page_words(text), fontname=FACE_NAME,
                     fontsize=CAPTION_PT, color=(0, 0, 0))


def text_width_mm(text):
    return _mm(fitz.Font(fontfile=str(FACE)).text_length(page_words(text), fontsize=CAPTION_PT))


def fit_lines(lines, width_mm):
    """The caption's lines, each split at its ' · ' where it would run wider than ``width_mm``."""
    out = []
    for line in lines:
        parts = line.split(' · ')
        cur = parts[0]
        for p in parts[1:]:
            if text_width_mm(cur + ' · ' + p) > width_mm:
                out.append(cur)
                cur = p
            else:
                cur = cur + ' · ' + p
        out.append(cur)
    widest = max(text_width_mm(x) for x in out)
    if widest > width_mm + 1e-6:
        raise ValueError('a caption line is %.1f mm, wider than its %.1f mm: %r' % (widest, width_mm, out))
    return out


def caption_lines(piece, sheet_words, copies):
    paper = piece['paper']
    lines = [piece['title'],
             'paper: %s %s · count %d (%s) · %s' % (paper['words'], PROVISIONAL, piece['count'], piece['count_source'],
                                                   sheet_words),
             PRINT_WORDS]
    if copies > 1:
        lines[2] = PRINT_WORDS + ' · %d copies on this sheet' % copies
    return lines


def foot(page, sheet_w_mm, sheet_h_mm, lines):
    """The words and the bar under the items: the caption's lines, then the bar, inside the foot band."""
    x = EDGE_MM + 2.0
    fitted = fit_lines(lines, sheet_w_mm - 2 * x)
    bar_y = sheet_h_mm - EDGE_MM - BAR_HEIGHT_MM - 1.0
    base = bar_y - 1.5 - LINE_MM * (len(fitted) - 1)
    if base - 2.2 < sheet_h_mm - EDGE_MM - FOOT_MM - 1e-6:
        raise ValueError('the caption (%d lines) does not fit the foot' % len(fitted))
    for i, line in enumerate(fitted):
        words(page, line, x, base + i * LINE_MM)
    return draw_bar(page, x, bar_y), fitted


# --- reading a written page back ---------------------------------------------------------------------------------------


def placements(doc, pno):
    """Every form the page itself draws (its top-level XObjects): its matrix and box as the file writes them, so its
    scale and its size on the page in mm. A form placed at 1 : 1 has the matrix [1 0 0 1 e f]."""
    out = []
    for xref, name, invoker, _ in doc[pno].get_xobjects():
        if invoker != 0 or doc.xref_get_key(xref, 'Subtype')[1] != '/Form':
            continue
        box = [float(v) for v in doc.xref_get_key(xref, 'BBox')[1].strip('[]').split()]
        key = doc.xref_get_key(xref, 'Matrix')
        mat = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        if key[0] != 'null':
            mat = [float(v) for v in key[1].strip('[]').split()]
        out.append({'form': name, 'matrix': mat, 'scale': [mat[0], mat[3]], 'shear': [mat[1], mat[2]],
                    'size_mm': [round(_mm((box[2] - box[0]) * mat[0]), 4), round(_mm((box[3] - box[1]) * mat[3]), 4)],
                    'box_mm': [round(_mm(v), 4) for v in box]})
    return out


def at_100(placed):
    """Every placed form a pure translation at scale 1 (to 1e-6)."""
    return bool(placed) and all(abs(p['scale'][0] - 1.0) < 1e-6 and abs(p['scale'][1] - 1.0) < 1e-6
                                and abs(p['shear'][0]) < 1e-9 and abs(p['shear'][1]) < 1e-9 for p in placed)


def bar_length(page, rect_mm):
    """The bar read from the page's drawings: the rectangle paths 3 mm tall inside its rect (0.5 mm about it), their
    extent along the bar — the paths' geometry, not their stroked box. None when it is not five segments."""
    box = _r([rect_mm[0] - 0.5, rect_mm[1] - 0.5, rect_mm[2] + 0.5, rect_mm[3] + 0.5])
    segs = [it[1] for d in page.get_drawings() for it in d['items']
            if it[0] == 're' and box.contains(it[1]) and abs(_mm(it[1].height) - BAR_HEIGHT_MM) < 0.05]
    if len(segs) != BAR_SEGMENTS:
        return {'segments': len(segs), 'length_mm': None}
    return {'segments': len(segs), 'length_mm': round(_mm(max(s.x1 for s in segs) - min(s.x0 for s in segs)), 4)}


def _segments(page):
    return [(it[1], it[2]) for d in page.get_drawings() for it in d['items'] if it[0] == 'l']


def _has(segs, a_mm, b_mm, tol_mm):
    a, b = fitz.Point(_pt(a_mm[0]), _pt(a_mm[1])), fitz.Point(_pt(b_mm[0]), _pt(b_mm[1]))
    tol = _pt(tol_mm)
    return any((abs(p.x - a.x) < tol and abs(p.y - a.y) < tol and abs(q.x - b.x) < tol and abs(q.y - b.y) < tol)
               or (abs(p.x - b.x) < tol and abs(p.y - b.y) < tol and abs(q.x - a.x) < tol and abs(q.y - a.y) < tol)
               for p, q in segs)


def crop_marks_expected(trim_mm, gap, length):
    """The eight mark segments of a trim's corners: from ``gap`` to ``gap + length`` off the trim, along each edge."""
    x0, y0, x1, y1 = trim_mm
    out = []
    for x, y, sx, sy in ((x0, y0, -1, -1), (x1, y0, 1, -1), (x0, y1, -1, 1), (x1, y1, 1, 1)):
        out.append(([x + sx * gap, y], [x + sx * (gap + length), y]))
        out.append(([x, y + sy * gap], [x, y + sy * (gap + length)]))
    return out


def crop_marks_found(page, trim_mm, gap, length):
    """How many of the trim's eight corner-mark segments the page's drawings hold (to 0.05 mm)."""
    segs = _segments(page)
    return sum(1 for a, b in crop_marks_expected(trim_mm, gap, length) if _has(segs, a, b, 0.05))


def overlap_marks_found(page, marks):
    """A tile's overlap marks found in its drawings: each dashed band line (to 0.05 mm) and each circled cross (a
    circle of the registration radius about its centre, to 0.1 mm)."""
    segs = _segments(page)
    lines = sum(1 for a, b in marks['band_lines_mm'] if _has(segs, a, b, 0.05))
    rings = []
    for d in page.get_drawings():
        r = d['rect']
        if abs(_mm(r.width) - 2 * TILE_REG_RADIUS_MM) < 0.1 and abs(_mm(r.height) - 2 * TILE_REG_RADIUS_MM) < 0.1 \
                and any(it[0] == 'c' for it in d['items']):
            rings.append((_mm((r.x0 + r.x1) / 2), _mm((r.y0 + r.y1) / 2)))
    crosses = sum(1 for cx, cy in marks['registration_mm']
                  if any(abs(cx - rx) < 0.1 and abs(cy - ry) < 0.1 for rx, ry in rings))
    return {'band_lines': lines, 'band_lines_of': len(marks['band_lines_mm']), 'registration': crosses,
            'registration_of': len(marks['registration_mm'])}


def chroma_max(doc, pno, dpi):
    """The page rendered: the largest spread between any pixel's channels (0 is neutral: black, white, grey)."""
    pix = doc[pno].get_pixmap(dpi=dpi, alpha=False)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n).astype(np.int16)
    return int((a.max(axis=2) - a.min(axis=2)).max())


def ground_patch(doc, pno, w_mm, h_mm):
    """A w × h mm patch of the page that holds nothing but its ground — every pixel within GROUND_TOLERANCE of the
    page's commonest colour, GROUND_CLEAR_MM clear about it, EDGE_MM in from the paper — read at GROUND_PX_PER_MM: the
    lowest such patch, then the leftmost; its top-left corner (mm), or None when the page has none."""
    page = doc[pno]
    k = GROUND_PX_PER_MM
    pix = page.get_pixmap(matrix=fitz.Matrix(k * MM_PER_PT, k * MM_PER_PT), alpha=False)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n).astype(np.int16)
    flat = a.reshape(-1, pix.n)
    colours, counts = np.unique(flat, axis=0, return_counts=True)
    ground = colours[int(np.argmax(counts))]
    ink = (np.abs(a - ground).max(axis=2) > GROUND_TOLERANCE).astype(np.int64)
    integral = np.zeros((ink.shape[0] + 1, ink.shape[1] + 1), np.int64)
    integral[1:, 1:] = ink.cumsum(0).cumsum(1)
    c = int(math.ceil(GROUND_CLEAR_MM * k))
    pw, ph = int(math.ceil(w_mm * k)) + 2 * c, int(math.ceil(h_mm * k)) + 2 * c
    e = int(math.ceil(EDGE_MM * k)) - c
    best = None
    for y in range(ink.shape[0] - e - ph, e - 1, -1):
        sums = integral[y + ph, pw:] - integral[y, pw:] - integral[y + ph, :-pw] + integral[y, :-pw]
        free = np.nonzero(sums[e:ink.shape[1] - e - pw + 1] == 0)[0]
        if free.size:
            best = ((int(free[0]) + e + c) / k, (y + c) / k)
            break
    if best is None:
        return None
    return {'at_mm': [round(best[0], 3), round(best[1], 3)], 'ground_rgb': [int(v) for v in ground]}


# --- the pieces' writers ------------------------------------------------------------------------------------------------


def write_flat(piece, sources, path):
    """A piece's items × its count on the smallest sheet that holds them: each placed at 1 : 1, crop marks at every trim,
    fold marks, the caption and the bar in the foot. Returns the pages' records (as drawn; read back by ``read_back``)."""
    items = [it for it in piece['items'] for _ in range(piece['count'])]
    sheet, pages = layout(items)
    size, way, w, h = sheet
    doc = fitz.open()
    records = []
    for placed in pages:
        page = doc.new_page(width=_pt(w), height=_pt(h))
        drawn = []
        for it, x, y in placed:
            if max(it['bleed_mm'].values()) > CROP_GAP_MM + 1e-6:
                raise ValueError('%s: a bleed of %s mm would run under its crop marks' % (it['label'], it['bleed_mm']))
            rect = place(page, sources, it, x, y)
            trim = on_page(it, x, y, it['trim_mm'])
            lm.crop_marks(page, trim)
            folds = [on_page(it, x, y, [f[0], f[1], f[2], f[3]]) for f in it['folds_mm']]
            folds = [[f[0], trim[1], f[2], trim[3]] if abs(f[0] - f[2]) < 1e-6 else [trim[0], f[1], trim[2], f[3]]
                     for f in folds]
            marks = fold_marks(page, trim, folds, it['bleed_mm'])
            drawn.append({'item': it['label'], 'at_mm': [round(x, 4), round(y, 4)], 'rect_mm': [round(v, 4) for v in rect],
                          'trim_mm': trim, 'fold_marks_mm': marks})
        copies = len(placed)
        bar, lines = foot(page, w, h, caption_lines(piece, '%s %s' % (size, way), copies))
        records.append({'sheet': size, 'way': way, 'sheet_mm': [w, h], 'items': drawn, 'bar_rect_mm': bar,
                        'caption': lines,
                        'crop_marks': {'gap_mm': CROP_GAP_MM, 'length_mm': CROP_LEN_MM,
                                       'trims_mm': [d['trim_mm'] for d in drawn]}})
    save(doc, path)
    return records


def tile_grid_for(sheet_w_mm, sheet_h_mm):
    """counter_tray_header_sheets.tile_grid on a sheet of these millimetres (the die's own grid)."""
    from apps.dielines.exporters import counter_tray_header_sheets as X
    return X.tile_grid(SimpleNamespace(sheet_w=sheet_w_mm, sheet_h=sheet_h_mm), X.A3_LONG_MM, X.A3_SHORT_MM)


def tile_marks(page, tg, r, col):
    """write_tiles_pdf's marks, drawn in PyMuPDF's top-down millimetres: the window's dashed overlap-band lines, crop
    corners 2-8 mm off its corners, a circled cross centred in each shared band. Returns what was drawn."""
    from apps.dielines.exporters import counter_tray_header_sheets as X
    m, ww, wh, ov = tg['margin'], tg['win_w'], tg['win_h'], X.OVERLAP_MM
    band = []
    if col > 0:
        band.append(([m + ov, m], [m + ov, m + wh]))
    if col < tg['cols'] - 1:
        band.append(([m + ww - ov, m], [m + ww - ov, m + wh]))
    if r > 0:
        band.append(([m, m + ov], [m + ww, m + ov]))
    if r < tg['rows'] - 1:
        band.append(([m, m + wh - ov], [m + ww, m + wh - ov]))
    dash = '[%g %g] 0' % (_pt(1.0), _pt(1.0))
    for a, b in band:
        page.draw_line(fitz.Point(_pt(a[0]), _pt(a[1])), fitz.Point(_pt(b[0]), _pt(b[1])), color=TILE_GREY,
                       width=0.3, dashes=dash)
    window = [m, m, m + ww, m + wh]
    for a, b in crop_marks_expected(window, TILE_CROP_GAP_MM, TILE_CROP_LEN_MM):
        page.draw_line(fitz.Point(_pt(a[0]), _pt(a[1])), fitz.Point(_pt(b[0]), _pt(b[1])), color=(0, 0, 0), width=0.3)
    reg = []
    if col > 0:
        reg.append([m + ov / 2, m + wh / 2])
    if col < tg['cols'] - 1:
        reg.append([m + ww - ov / 2, m + wh / 2])
    if r > 0:
        reg.append([m + ww / 2, m + ov / 2])
    if r < tg['rows'] - 1:
        reg.append([m + ww / 2, m + wh - ov / 2])
    for cx, cy in reg:
        page.draw_circle(fitz.Point(_pt(cx), _pt(cy)), _pt(TILE_REG_RADIUS_MM), color=(0, 0, 0), width=0.3)
        page.draw_line(fitz.Point(_pt(cx - TILE_REG_ARM_MM), _pt(cy)), fitz.Point(_pt(cx + TILE_REG_ARM_MM), _pt(cy)),
                       color=(0, 0, 0), width=0.3)
        page.draw_line(fitz.Point(_pt(cx), _pt(cy - TILE_REG_ARM_MM)), fitz.Point(_pt(cx), _pt(cy + TILE_REG_ARM_MM)),
                       color=(0, 0, 0), width=0.3)
    return {'window_mm': window, 'band_lines_mm': [[list(a), list(b)] for a, b in band],
            'registration_mm': [[round(v, 4) for v in c] for c in reg]}


def write_tiles(piece, sources, path):
    """The piece's one item at 1 : 1 over A3 landscape tiles on the die's grid: each tile a window of it (the window
    clipped to the sheet), its marks, its row / column and words, and the 50 mm bar where write_tiles_pdf puts it."""
    from apps.dielines.exporters import counter_tray_header_sheets as X
    it = piece['items'][0]
    sx0, sy0, sx1, sy1 = it['clip_mm']
    tg = tile_grid_for(piece['grid_mm'][0], piece['grid_mm'][1])
    w, h = X.A3_LONG_MM, X.A3_SHORT_MM
    m, ww, wh = tg['margin'], tg['win_w'], tg['win_h']
    doc = fitz.open()
    records = []
    for r in range(tg['rows']):
        for col in range(tg['cols']):
            wx, wy = col * tg['step_w'], r * tg['step_h']
            page = doc.new_page(width=_pt(w), height=_pt(h))
            clip = [max(sx0, sx0 + wx), max(sy0, sy0 + wy), min(sx1, sx0 + wx + ww), min(sy1, sy0 + wy + wh)]
            if clip[2] - clip[0] > 1e-6 and clip[3] - clip[1] > 1e-6:
                rect = [m + clip[0] - (sx0 + wx), m + clip[1] - (sy0 + wy), m + clip[2] - (sx0 + wx),
                        m + clip[3] - (sy0 + wy)]
                page.show_pdf_page(_r(rect), sources.open(it['src']), it['page'], clip=_r(clip))
            marks = tile_marks(page, tg, r, col)
            lines = [
                '%s - tile row %d / col %d of %d x %d - print at 100 %%, no fit (A3 landscape)'
                % (piece['title'], r + 1, col + 1, tg['rows'], tg['cols']),
                'x %.0f..%.0f, y %.0f..%.0f mm of the %.0f x %.0f mm sheet; overlap %g mm with each neighbour: lay the '
                'circled crosses on each other' % (wx, wx + ww, wy, wy + wh, sx1 - sx0, sy1 - sy0, X.OVERLAP_MM),
                'paper: %s %s · count %d (%s)' % (piece['paper']['words'], PROVISIONAL, piece['count'],
                                                   piece['count_source'])]
            fitted = fit_lines(lines, TILE_BAR_X_MM - 4.0)
            base = h - 19.0
            for i, line in enumerate(fitted):
                words(page, line, m, base + i * LINE_MM)
            bar = draw_bar(page, m + TILE_BAR_X_MM, h - TILE_BAR_FOOT_MM - BAR_HEIGHT_MM)
            records.append({'sheet': 'A3', 'way': 'landscape', 'sheet_mm': [w, h], 'tile': [r + 1, col + 1],
                            'source_window_mm': [round(v, 4) for v in clip], 'marks': marks, 'bar_rect_mm': bar,
                            'caption': fitted,
                            'crop_marks': {'gap_mm': TILE_CROP_GAP_MM, 'length_mm': TILE_CROP_LEN_MM,
                                           'trims_mm': [marks['window_mm']]}})
    save(doc, path)
    return records, tg


def write_copy(piece, sources, path):
    """Pages that are each a whole sheet already (the board, the plan and elevation): copied at 1 : 1 onto a page of
    their own size, the bar and its words set in a patch of the page's own ground found by looking. No crop marks:
    the trim is the sheet's edge."""
    doc = fitz.open()
    records = []
    for it in piece['items']:
        src = sources.open(it['src'])
        w, h = it['page_mm'][2], it['page_mm'][3]
        sheet = [s for s in SHEETS if abs(s[2] - w) < 0.5 and abs(s[3] - h) < 0.5]
        if not sheet:
            raise ValueError('%s: a %.1f x %.1f mm page is not an A4 or A3 sheet' % (it['label'], w, h))
        page = doc.new_page(width=_pt(w), height=_pt(h))
        place(page, sources, it, 0.0, 0.0)
        said = PRINT_WORDS if piece['bar_words'] is None else piece['bar_words']
        line = '%s · %s · paper: %s %s · count %d' % (said, it['label'], piece['paper']['words'], PROVISIONAL,
                                                      piece['count'])
        lead_w = BAR_MM + 3.0 + text_width_mm('50 mm') + 3.0
        # one line beside the bar first (it fits a board's foot margin); else the bar over two lines
        lines = [line]
        spot = ground_patch(src, it['page'], lead_w + text_width_mm(line), BAR_HEIGHT_MM + 0.5)
        if spot is None:
            lines = fit_lines([piece['title'] + ' · ' + it['label'],
                               'paper: %s %s · count %d · %s' % (piece['paper']['words'], PROVISIONAL, piece['count'],
                                                                 said)], 170.0)
            spot = ground_patch(src, it['page'], max(lead_w, max(text_width_mm(x) for x in lines)),
                                BAR_HEIGHT_MM + 1.5 + LINE_MM * len(lines))
        if spot is None:
            raise ValueError('%s: no patch of its own ground holds the bar and its words' % it['label'])
        x, y = spot['at_mm']
        bar = draw_bar(page, x, y)
        if len(lines) == 1:
            words(page, line, x + lead_w, y + BAR_HEIGHT_MM - 0.6)
        else:
            for i, text in enumerate(lines):
                words(page, text, x, y + BAR_HEIGHT_MM + 1.5 + 2.2 + i * LINE_MM)
        records.append({'sheet': sheet[0][0], 'way': sheet[0][1], 'sheet_mm': [w, h],
                        'items': [{'item': it['label'], 'at_mm': [0.0, 0.0], 'rect_mm': list(it['page_mm']),
                                   'trim_mm': list(it['page_mm']), 'fold_marks_mm': []}],
                        'bar_rect_mm': bar, 'caption': lines, 'ground_patch': spot, 'crop_marks': None,
                        'crop_marks_why': 'the page is a whole %s sheet (%.0f x %.0f mm): its trim is the sheet\'s edge, '
                                          'with no room outside it for marks; printed at 100 %%, the bar set in a patch of '
                                          'its own ground' % (sheet[0][0], w, h)})
    save(doc, path)
    return records


def save(doc, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path), garbage=3, deflate=True)
    doc.close()


def read_back(path, pages):
    """The written file read back, page by page: its forms (scale, size), its bar's length, its crop marks and a tile's
    overlap marks — beside what each page says it drew."""
    out = []
    with fitz.open(str(path)) as doc:
        if doc.page_count != len(pages):
            raise ValueError('%s has %d pages, the build drew %d' % (path, doc.page_count, len(pages)))
        for pno, rec in enumerate(pages):
            page = doc[pno]
            placed = placements(doc, pno)
            read = {'page': pno + 1, 'forms': placed, 'at_100': at_100(placed),
                    'bar': bar_length(page, rec['bar_rect_mm']),
                    'sheet_mm_read': [round(_mm(page.rect.width), 3), round(_mm(page.rect.height), 3)]}
            if rec['crop_marks'] is not None:
                cm = rec['crop_marks']
                read['crop_marks_found'] = sum(crop_marks_found(page, t, cm['gap_mm'], cm['length_mm'])
                                               for t in cm['trims_mm'])
                read['crop_marks_of'] = 8 * len(cm['trims_mm'])
            if 'marks' in rec:
                read['overlap_marks'] = overlap_marks_found(page, rec['marks'])
            out.append(dict(rec, read=read))
    return out


# --- the manifest ---------------------------------------------------------------------------------------------------------


def choose(day13, day12, names):
    """The Day 13 folder when it holds every named file and each reads; Day 12's otherwise. A Day 13 folder that
    exists but is short is said loudly (``warning``), never a silent fallback; one that does not exist yet is said
    plainly (the §1 repair has not written it)."""
    d13, d12 = AUDIT / day13, AUDIT / day12
    found = {n: opens(d13 / n) for n in names}
    if all(found.values()):
        return d13, {'day': 13, 'folder': lm.rel(d13), 'expected_day13': day13, 'found': found, 'warning': None}
    if d13.is_dir():
        warning = ('THE DAY 13 FOLDER %s EXISTS BUT DOES NOT HOLD %s: Day 12\'s files are used'
                   % (day13, ', '.join(n for n, ok in found.items() if not ok)))
    else:
        warning = None
    missing = [n for n in names if not opens(d12 / n)]
    if missing:
        raise FileNotFoundError('neither %s nor %s holds %s' % (day13, day12, missing))
    return d12, {'day': 12, 'folder': lm.rel(d12), 'expected_day13': day13, 'found': found, 'warning': warning,
                 'day13_folder_exists': d13.is_dir()}


def _paper(kind, reading=None):
    """The paper: one of the owner's three classes (his ⟪PROVISIONAL⟫ weights as typed) — ``reading`` says so, or
    gives the builder's reading where he did not name the piece outright — or, for a piece outside his three
    classes, the words for its paper with ``reading`` saying what it is for and that it is not in his list."""
    if kind in PAPER:
        p = dict(PAPER[kind])
        p['reading'] = 'the owner\'s class: %s' % p['class'] if reading is None else reading
        return p
    return {'words': kind, 'class': None, 'owners': False,
            'reading': 'not in the owner\'s list (his: cartons and labels, wraps, the display): %s' % reading}


def manifest(sources):
    """Every piece of the pack, in print order — Ẓilāl, the lipstick, the balm, the display, the board, and Golden
    Hour's test one last and in its own folder (the cut order cuts it first). Where a §1 repair rebuilds a Day 12 piece
    the Day 13 folder is taken when it holds the file, Day 12's otherwise, and the choice recorded."""
    z11, z12 = AUDIT / 'day-11' / 'zilal', AUDIT / 'day-12' / 'zilal'
    choices = {}
    sides_record = json.loads((z11 / 'sides' / 'sides-of-record.json').read_text(encoding='utf-8'))
    sides_page = REPO / sides_record['page']
    lid = z12 / 'lid' / 'lid-master.pdf'
    _, lid_trim, _ = trim_of(sources.open(lid), 0)
    side_page_mm, _, _ = trim_of(sources.open(sides_page), 0)
    band_x = (side_page_mm[2] - (lid_trim[2] - lid_trim[0])) / 2.0
    band_y = (side_page_mm[3] - (lid_trim[3] - lid_trim[1])) / 2.0
    wrap_folds = [[band_x, 0.0, band_x, 1.0], [side_page_mm[2] - band_x, 0.0, side_page_mm[2] - band_x, 1.0],
                  [0.0, band_y, 1.0, band_y], [0.0, side_page_mm[3] - band_y, 1.0, side_page_mm[3] - band_y]]

    lip = AUDIT / 'day-12' / 'lipstick' / 'closed'
    balm = AUDIT / 'day-12' / 'balm' / 'master'
    lip_carton, choices['lipstick carton'] = choose('day-13/lipstick/carton', 'day-12/lipstick/carton',
                                                    ['carton-artwork.pdf', 'carton-fold-check.json',
                                                     'carton-fit-report.json'])
    balm_carton, choices['balm carton'] = choose('day-13/balm/carton', 'day-12/balm/carton',
                                                 ['carton-artwork.pdf', 'carton-fold-check.json',
                                                  'carton-fit-report.json'])
    die_dir, choices['display die'] = choose('day-13/display/die', 'day-12/display/die',
                                             ['die-1to1.pdf', 'die.json', 'plan-elevation.pdf', 'die-A3-100pct.pdf'])
    art_dir, choices['display artwork'] = choose('day-13/display/tray', 'day-12/display/tray',
                                                 ['display-artwork.pdf', 'tray.json'])
    board_dir, choices['board'] = choose('day-13/board', 'day-12/board', ['collection-board.pdf', 'board.json'])
    die = json.loads((die_dir / 'die.json').read_text(encoding='utf-8'))
    counts = die['owner_provisional']
    n_lip, n_balm = int(counts['lipstick_count']['value']), int(counts['balm_count']['value'])
    sheet_w, sheet_h = float(die['die']['sheet_mm'][0]), float(die['die']['sheet_mm'][1])
    board_mm = die['owner_provisional']['board_mm']['value']
    die_rel = lm.rel(die_dir / 'die.json')
    count_lip = 'die.json lipstick_count, %s' % PROVISIONAL
    count_balm = 'die.json balm_count, %s' % PROVISIONAL
    one = 'one piece'

    def flat(key, group, title, items, paper, counted=None, notes=()):
        n, said = (1, one) if counted is None else counted
        return {'key': key, 'group': group, 'title': title, 'kind': 'flat', 'items': items, 'paper': paper,
                'count': n, 'count_source': said, 'notes': list(notes)}

    def creases(path, pno):
        return crease_lines(sources.open(path), pno)

    pieces = [
        flat('zilal-lid-and-sides', 'zilal', 'Ẓilāl — the lid and its four sides, one wrap sheet (fold at the lid\'s edges)',
             [item(sources, sides_page, 0, 'the lid and the sides of record, unfolded', folds_mm=wrap_folds)],
             _paper('wrap'), notes=[
                 'the sides of record are %s (sides-of-record.json), not day-11/zilal/sides/sides-unfolded.pdf (the '
                 'masked edit that failed its continuity and the eye)' % sides_record['page'],
                 'fold lines at the lid\'s four edges: %.1f mm in from each side (the page %.0f x %.0f less the lid\'s '
                 'trim %.0f x %.0f from lid-master.pdf\'s TrimBox, halved); the four %.0f x %.0f corners are cut away'
                 % (band_x, side_page_mm[2], side_page_mm[3], lid_trim[2] - lid_trim[0], lid_trim[3] - lid_trim[1],
                    band_x, band_y)]),
        flat('zilal-inside-lid', 'zilal', 'Ẓilāl — inside the lid',
             [item(sources, z11 / 'inside-lid' / 'master' / 'inside-lid.pdf', 0, 'inside the lid')],
             _paper('wrap', 'the builder\'s reading: a wrap, it lines the lid\'s inside')),
        flat('zilal-tray-print', 'zilal', 'Ẓilāl — the tray insert, print layer',
             [item(sources, z11 / 'tray' / 'master' / 'tray-artwork.pdf', 0, 'the tray insert, printed')],
             _paper('card', 'the builder\'s reading: card, the insert is cut with its 18 wells')),
        flat('zilal-tray-cut', 'zilal', 'Ẓilāl — the tray insert, cut page (outline and 18 wells)',
             [item(sources, z11 / 'tray' / 'master' / 'tray-artwork.pdf', 1, 'the tray insert, cut lines')],
             _paper('80 gsm plain paper', 'the cutting template laid over the printed insert')),
        flat('zilal-sticker', 'zilal', 'Ẓilāl — the base sticker',
             [item(sources, z11 / 'sticker' / 'sticker.pdf', 0, 'the base sticker')],
             _paper('card', 'the builder\'s reading: a label')),
        flat('zilal-box', 'zilal', 'Ẓilāl — the box flat (reverse tuck end)',
             [item(sources, z12 / 'box' / 'box-artwork.pdf', 0, 'the box flat, print with its die',
                   folds_mm=creases(z12 / 'box' / 'box-artwork.pdf', 0))],
             _paper('card')),
        flat('zilal-lid-foil-mask', 'zilal', 'Ẓilāl — the lid\'s rose-gold foil, mask (black prints foil)',
             [item(sources, z12 / 'lid' / 'engine' / 'layer-foil.ai', 0, 'the lid\'s foil layer')],
             _paper('80 gsm plain paper', 'the stamp-maker\'s original, or a hand-applied foil test'),
             notes=['the lid\'s trim (190 x 120 mm): register it on the wrap sheet\'s lid between the fold lines']),
        flat('zilal-lid-relief-mask', 'zilal', 'Ẓilāl — the lid\'s emboss, mask (black is raised)',
             [item(sources, z12 / 'lid' / 'engine' / 'layer-relief.ai', 0, 'the lid\'s relief layer')],
             _paper('80 gsm plain paper', 'the stamp-maker\'s original')),
        flat('zilal-box-foil-mask', 'zilal', 'Ẓilāl — the box\'s rose-gold foil, mask (black prints foil)',
             [item(sources, z12 / 'box' / 'box-artwork.pdf', 1, 'the box\'s foil page')],
             _paper('80 gsm plain paper', 'the stamp-maker\'s original, or a hand-applied foil test')),
        flat('zilal-box-relief-mask', 'zilal', 'Ẓilāl — the box\'s emboss, mask (black is raised)',
             [item(sources, z12 / 'box' / 'box-artwork.pdf', 2, 'the box\'s relief page')],
             _paper('80 gsm plain paper', 'the stamp-maker\'s original')),

        flat('lipstick-body-wrap', 'lipstick', 'The lipstick — body wrap (wraps a Ø 20 tube)',
             [item(sources, lip / 'body-wrap.pdf', 0, 'the body wrap')], _paper('wrap'), (n_lip, count_lip)),
        flat('lipstick-cap-wrap', 'lipstick', 'The lipstick — cap wrap (wraps a Ø 20 tube)',
             [item(sources, lip / 'cap-wrap.pdf', 0, 'the cap wrap')], _paper('wrap'), (n_lip, count_lip)),
        flat('lipstick-label', 'lipstick', 'The lipstick — bottom label Ø 18, with its die',
             [item(sources, lip / 'label.pdf', 0, 'the bottom label', overlays=[(lip / 'label.pdf', 1)])],
             _paper('card'), (n_lip, count_lip)),
        flat('lipstick-carton', 'lipstick', 'The lipstick — the carton flat (straight tuck end)',
             [item(sources, lip_carton / 'carton-artwork.pdf', 0, 'the carton flat, print with its die',
                   folds_mm=creases(lip_carton / 'carton-artwork.pdf', 0))],
             _paper('card')),

        flat('balm-body-wrap', 'balm', 'The lip balm — body wrap (wraps a Ø 18 tube)',
             [item(sources, balm / 'body-wrap.pdf', 0, 'the body wrap')], _paper('wrap'), (n_balm, count_balm)),
        flat('balm-cap-wrap', 'balm', 'The lip balm — cap wrap (wraps a Ø 18 tube)',
             [item(sources, balm / 'cap-wrap.pdf', 0, 'the cap wrap')], _paper('wrap'), (n_balm, count_balm)),
        flat('balm-label', 'balm', 'The lip balm — bottom label Ø 16, with its die',
             [item(sources, balm / 'label.pdf', 0, 'the bottom label', overlays=[(balm / 'label.pdf', 1)])],
             _paper('card'), (n_balm, count_balm)),
        flat('balm-carton', 'balm', 'The lip balm — the carton flat (straight tuck end)',
             [item(sources, balm_carton / 'carton-artwork.pdf', 0, 'the carton flat, print with its die',
                   folds_mm=creases(balm_carton / 'carton-artwork.pdf', 0))],
             _paper('card')),
    ]

    from apps.dielines.exporters import counter_tray_header_sheets as X
    die_page = die_dir / 'die-1to1.pdf'
    art_page = art_dir / 'display-artwork.pdf'
    flute = dict(_paper('flute'), words='E-flute %g mm' % board_mm,
                 reading='the owner\'s class: the display (the board %g mm: %s owner_provisional.board_mm)'
                 % (board_mm, die_rel))
    whole = [0.0, 0.0, sheet_w, sheet_h]
    pieces.append({'key': 'display-die-tiles', 'group': 'display', 'kind': 'tiles',
                   'title': 'The counter display — the die at 100 %',
                   'items': [item(sources, die_page, 0, 'the die (cut, crease, words)', clip_mm=whole, trim_mm=whole,
                                  trim_from='%s die.sheet_mm' % die_rel)],
                   'grid_mm': [sheet_w, sheet_h], 'paper': flute, 'count': 1, 'count_source': 'one set of tiles',
                   'notes': ['the die is the cutting guide: lay the tiles on the board, crosses on crosses']})
    pieces.append({'key': 'display-artwork-tiles', 'group': 'display', 'kind': 'tiles',
                   'title': 'The counter display — the artwork at 100 %',
                   'items': [item(sources, art_page, 0, 'the artwork (print, cut, crease)', clip_mm=whole,
                                  trim_mm=whole, trim_from='%s die.sheet_mm (the artwork is drawn on the die\'s sheet)'
                                  % die_rel)],
                   'grid_mm': [sheet_w, sheet_h], 'paper': flute, 'count': 1, 'count_source': 'one set of tiles',
                   'notes': ['the same grid as the die\'s tiles: tile row r / col c of the artwork is tile r / c of '
                             'the die']})
    parts = {p['part']: p for p in die['die']['parts']}
    part_items = []
    for name in ('slot insert', 'front platform', 'back platform'):
        b = parts[name]['bbox_mm']
        clip = [b[0] - X.BLEED_MM, b[1] - X.BLEED_MM, b[2] + X.BLEED_MM, b[3] + X.BLEED_MM]
        part_items.append(item(sources, art_page, 0, 'the %s' % name, clip_mm=clip, trim_mm=b,
                               trim_from='%s die.parts["%s"].bbox_mm, bleed counter_tray_header.DIE_BLEED_MM'
                               % (die_rel, name)))
    pieces.append(flat('display-parts', 'display', 'The counter display — the slot insert and the two platforms',
                       part_items, flute, notes=['the same parts are on the die\'s tiles; here each whole on one '
                                                 'sheet, cut at its outline, creased at its cyan lines']))
    pieces.append({'key': 'display-plan-elevation', 'group': 'display', 'kind': 'copy',
                   'title': 'The counter display — plan, front elevation, side section (a drawing at 1 : 2)',
                   'items': [item(sources, die_dir / 'plan-elevation.pdf', 0, 'the plan and elevation')],
                   'paper': _paper('80 gsm plain paper', 'a drawing'), 'count': 1, 'count_source': one,
                   'bar_words': 'this bar is 50 mm on paper, the print\'s check, not the drawing\'s 1 : 2 scale',
                   'notes': ['the drawing is at 1 : 2: its own scale bar is 25 mm on paper for 50 mm of the display; '
                             'the 50 mm bar the pack adds is the paper\'s calibration, not the drawing\'s scale']})
    board = board_dir / 'collection-board.pdf'
    board_paper = _paper('the lead\'s choice', 'a presentation sheet')

    def board_page(key, group, pno, label, notes):
        return {'key': key, 'group': group, 'kind': 'copy', 'title': 'The collection board', 'paper': board_paper,
                'items': [item(sources, board, pno, label)], 'count': 1, 'count_source': one, 'notes': notes,
                'bar_words': None}

    pieces.append(board_page('collection-board-page-1', 'board', 0, 'page 1, Ẓilāl',
                             ['page 2 (Golden Hour, test one) is in golden-hour/, cut with Golden Hour\'s pages']))

    g11 = AUDIT / 'day-11' / 'golden-hour'
    pieces += [
        flat('golden-hour-lid', 'golden-hour', 'Golden Hour (test one) — the lid',
             [item(sources, g11 / 'lid' / 'lid-master.pdf', 0, 'the lid')],
             _paper('wrap', 'the builder\'s reading: a wrap, the lid print mounted on its board')),
        flat('golden-hour-tray-print', 'golden-hour', 'Golden Hour (test one) — the tray insert, print layer',
             [item(sources, g11 / 'tray' / 'tray-artwork.pdf', 0, 'the tray insert, printed')],
             _paper('card', 'the builder\'s reading: card, the insert is cut with its wells')),
        flat('golden-hour-tray-cut', 'golden-hour', 'Golden Hour (test one) — the tray insert, cut page',
             [item(sources, g11 / 'tray' / 'tray-artwork.pdf', 1, 'the tray insert, cut lines')],
             _paper('80 gsm plain paper', 'the cutting template laid over the printed insert')),
        flat('golden-hour-sticker', 'golden-hour', 'Golden Hour (test one) — the base sticker',
             [item(sources, g11 / 'sticker' / 'sticker.pdf', 0, 'the base sticker')],
             _paper('card', 'the builder\'s reading: a label')),
        flat('golden-hour-box', 'golden-hour', 'Golden Hour (test one) — the box flat (reverse tuck end)',
             [item(sources, g11 / 'box' / 'box-artwork.pdf', 0, 'the box flat, print with its die',
                   folds_mm=creases(g11 / 'box' / 'box-artwork.pdf', 0))],
             _paper('card')),
        board_page('collection-board-page-2', 'golden-hour', 1, 'page 2, Golden Hour (test one)',
                   ['the board\'s page 2: kept with Golden Hour\'s pages so the cut order can cut them together']),
    ]
    facts = {'sides_record': lm.rel(z11 / 'sides' / 'sides-of-record.json'), 'sides_page': sides_record['page'],
             'lid_trim_mm': lid_trim, 'wrap_band_mm': [band_x, band_y], 'die_sheet_mm': [sheet_w, sheet_h],
             'die_json': die_rel, 'die_json_sha256': sha256(die_dir / 'die.json'),
             'artwork_tray_json_die_sha256': json.loads((art_dir / 'tray.json').read_text(encoding='utf-8'))['die_json_sha256'],
             'artwork_page_mm': trim_of(sources.open(art_page), 0)[0],
             'die_builders_tiles': lm.rel(die_dir / 'die-A3-100pct.pdf'),
             'die_builders_tile_pages': sources.open(die_dir / 'die-A3-100pct.pdf').page_count,
             'counts': {'lipstick_count': n_lip, 'balm_count': n_balm,
                        'palettes_in_slot': int(counts['palettes_in_slot']['value'])}}
    return pieces, choices, facts


# --- the build -----------------------------------------------------------------------------------------------------------


def piece_file(out_dir, piece):
    return Path(out_dir) / piece['group'] / ('%s.pdf' % piece['key'])


def build(out_dir=OUT, keep=None):
    """Every piece's PDF into ``out_dir`` (one folder per group, Golden Hour's last), each read back; the record.
    ``keep``: a previous record whose pieces' ``prints_as_it_stands`` (the lead's, D-D13-8) are carried over."""
    sources = Sources()
    kept = {}
    if keep is not None:
        kept = {p['key']: p['prints_as_it_stands'] for p in keep['pieces']}
    pieces, choices, facts = manifest(sources)
    rows = []
    for piece in pieces:
        path = piece_file(out_dir, piece)
        extra = {}
        if piece['kind'] == 'flat':
            drawn = write_flat(piece, sources, path)
        elif piece['kind'] == 'tiles':
            drawn, tg = write_tiles(piece, sources, path)
            extra['grid'] = tg
        else:
            drawn = write_copy(piece, sources, path)
        pages = read_back(path, drawn)
        srcs = []
        for it in piece['items']:
            entry = {'item': it['label'], 'path': lm.rel(it['src']), 'page': it['page'] + 1, 'sha256': sha256(it['src']),
                     'page_mm': it['page_mm'], 'clip_mm': it['clip_mm'], 'trim_mm': it['trim_mm'],
                     'trim_from': it['trim_from'], 'bleed_mm': it['bleed_mm'], 'folds_mm': it['folds_mm'],
                     'overlays': [{'path': lm.rel(s), 'page': p + 1, 'sha256': sha256(s)} for s, p in it['overlays']]}
            srcs.append(entry)
        sheets = {'A4': sum(1 for p in pages if p['sheet'] == 'A4'), 'A3': sum(1 for p in pages if p['sheet'] == 'A3')}
        row = {'key': piece['key'], 'group': piece['group'], 'title': piece['title'], 'kind': piece['kind'],
               'file': lm.rel(path), 'sha256': sha256(path), 'bytes': path.stat().st_size, 'pages': len(pages),
               'sheets': sheets, 'paper': piece['paper'], 'count': piece['count'],
               'count_source': piece['count_source'], 'sources': srcs, 'notes': piece['notes'],
               'prints_as_it_stands': kept[piece['key']] if piece['key'] in kept else None,
               'page_records': pages}
        row.update(extra)
        rows.append(row)
    sources.close()
    return {'schema': SCHEMA, 'pieces': rows, 'choices': choices, 'facts': facts}


# --- PRINT-LIST.md ---------------------------------------------------------------------------------------------------------

GROUPS = (('zilal', 'Ẓilāl — the palette'), ('lipstick', 'The lipstick'), ('balm', 'The lip balm'),
          ('display', 'The counter display'), ('board', 'The collection board'),
          ('golden-hour', 'Golden Hour (test one) — cut first if anything is cut'))
ASSEMBLY = 'cut → crease → fold → glue; wrap the sticks on Ø 20 and Ø 18 tubes or dowels; mount the lid on 2 mm board ' \
           'at 190 × 120; stand the display and load it'


def sheet_totals(rows):
    """The sheets to print, A4 and A3 apart: every page of every file once (the copies are on the pages)."""
    return {'A4': sum(r['sheets']['A4'] for r in rows), 'A3': sum(r['sheets']['A3'] for r in rows)}


def print_list(record):
    """PRINT-LIST.md from the record: every file, its sheet, its paper (⟪PROVISIONAL⟫), its count, the D-D13-8 field
    the lead fills, the sheets counted A4 and A3 apart, and the order of assembly in the owner's words."""
    rows = record['pieces']
    gh = [r for r in rows if r['group'] == 'golden-hour']
    rest = [r for r in rows if r['group'] != 'golden-hour']
    t_all, t_rest, t_gh = sheet_totals(rows), sheet_totals(rest), sheet_totals(gh)
    by_paper = {}
    for r in rows:
        k = r['paper']['words']
        by_paper[k] = [by_paper[k][0] + r['sheets']['A4'], by_paper[k][1] + r['sheets']['A3']] if k in by_paper \
            else [r['sheets']['A4'], r['sheets']['A3']]
    out = ['# Print list — Day 14',
           '',
           'Every file in this folder, the sheet it prints on, its paper, how many, and the order of assembly. Print '
           'every page **at 100 %%, no fit** (no "fit to page", no scaling): the 50 mm bar on each page must measure '
           '50 mm with a ruler before anything is cut. Paper weights are %s — the owner\'s: 300 gsm card for cartons '
           'and labels, 250 gsm for wraps, E-flute for the display; a piece outside those three says so.' % PROVISIONAL,
           '',
           'Written by `docs/audit/rescue_runtime/day13/print_pack_run.py` from `print-pack.json` (every source\'s '
           'path and sha256, every page read back from its file: each placed form at scale 1, the bar\'s length, the '
           'crop marks). The column "as it stands" is D-D13-8\'s: what fails its look prints as it stands — the lead '
           'fills it in `print-pack.json` (`prints_as_it_stands`); a re-run keeps what is filled.',
           '',
           '## Sheets',
           '',
           '| | A4 | A3 |', '|---|---|---|',
           '| the whole pack | %d | %d |' % (t_all['A4'], t_all['A3']),
           '| without Golden Hour | %d | %d |' % (t_rest['A4'], t_rest['A3']),
           '| Golden Hour (test one) alone | %d | %d |' % (t_gh['A4'], t_gh['A3']),
           '',
           'By paper (sheets, A4 / A3): ' + '; '.join('%s %d / %d' % (k, v[0], v[1]) for k, v in by_paper.items()) + '.',
           '']
    for group, heading in GROUPS:
        mine = [r for r in rows if r['group'] == group]
        if not mine:
            continue
        out += ['## ' + heading, '',
                '| File | Sheet | Pages | Paper %s | Count | Made from | As it stands (D-D13-8) |' % PROVISIONAL,
                '|---|---|---|---|---|---|---|']
        for r in mine:
            ways = sorted({'%s %s' % (p['sheet'], p['way']) for p in r['page_records']})
            paper = '%s — %s' % (r['paper']['words'], r['paper']['reading'])
            made = '; '.join('`%s` p%d' % (s['path'], s['page']) for s in r['sources'][:1])
            if len(r['sources']) > 1:
                made += ' (+%d more)' % (len(r['sources']) - 1)
            stands = '— (the lead fills)' if r['prints_as_it_stands'] is None else str(r['prints_as_it_stands'])
            out.append('| `%s` | %s | %d | %s | %d (%s) | %s | %s |' % (
                r['file'].split('print-pack/')[-1], ', '.join(ways), r['pages'], paper, r['count'], r['count_source'],
                made, stands))
        notes = [n for r in mine for n in r['notes']]
        if notes:
            out += [''] + ['- ' + n for n in notes]
        out.append('')
    choices = record['choices']
    out += ['## Which day\'s file each repaired piece was made from', '',
            '| Piece | Day | Folder | Note |', '|---|---|---|---|']
    for name, c in choices.items():
        out.append('| %s | %d | `%s` | %s |' % (name, c['day'], c['folder'], c['warning'] if c['warning'] else
                                               ('Day 13 not written yet: Day 12 used' if c['day'] == 12 else '')))
    out += ['', '## The order of assembly', '',
            'The owner\'s order, as typed: "%s".' % ASSEMBLY, '',
            '1. **Cut → crease → fold → glue.** Cut every piece at its trim (the crop marks; a carton or box at its '
            'magenta die line, the tray inserts at their cut page\'s lines), crease at the cyan lines and the dashed '
            'fold marks, fold, glue. The lid and sides wrap: cut its four corner squares away, fold at the dashed '
            'marks (the lid\'s four edges).',
            '2. **Wrap the sticks on Ø 20 and Ø 18 tubes or dowels.** The lipstick\'s body and cap wraps on Ø 20, the '
            'lip balm\'s on Ø 18; each bottom label at its die circle, on the stick\'s foot.',
            '3. **Mount the lid on 2 mm board at 190 × 120.** The lid face of the wrap sheet (between its fold marks) '
            'on the board, the sides folded down; the inside lid inside it; the foil and emboss masks register on the '
            'lid\'s trim (their crop marks are the lid\'s corners).',
            '4. **Stand the display and load it.** The die tiles and artwork tiles laid crosses on crosses on the '
            'E-flute, cut and creased as one sheet; the slot insert and platforms from their own sheets; stood as the '
            'plan and elevation draws it; loaded with the palettes in the slot (%d), the lipsticks (%d) and the lip '
            'balms (%d).' % (record['facts']['counts']['palettes_in_slot'], record['facts']['counts']['lipstick_count'],
                             record['facts']['counts']['balm_count']),
            '']
    return '\n'.join(out)
