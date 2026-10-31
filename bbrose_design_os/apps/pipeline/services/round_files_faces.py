"""The faces of a design, each placed with its live type and the approved logo from the brief's COPY and Accepted or
Redrawn by the owner (owner, 2026-10-28: the owner is the gate; round_files_gate).

The stand is designed flat (owner, 2026-10-28: "die first, then the design on it"): the dieline engine draws the flat
die first (counter_display_files.flat_template), one painting fills its printed faces and their bleed, and the die is
applied again to what comes back. Each stand face is that painting's printed face, cut straight from it at the die's
transform and turned upright; a Redraw repaints that one face on the same template. The bottle and the cap are each
drawn front-on as one edit on their own flat face template, guided by the picked picture's view of them, with no
lettering.

Its own turn (each face as it folds; from zilal_tray). Reused: round_files_export (the writer: live type, the
approved logo, the die locked) and product_drawing (the drawings)."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, box as shp_box

from . import round_flow as flow
from .round_calls import sha

SHEETS = {'landscape': (1536, 1024), 'portrait': (1024, 1536)}
MARGIN_PX = 48
STAND_BLEED_MM, STAND_SAFE_MM = 3.0, 3.0          # counter_tray_header: each printed panel inset 3 mm, bleed 3 mm
PRODUCT_SAFE_MM = 0.5                             # the bottle and cap print to their edges; their guide 0.5 mm in
EDIT_HOLD_USD = 0.35                              # one high edit: about $0.18–0.21 on round 3's own journal
NOTE_MAX = 160                                    # the owner's one-line Redraw note, in characters

#: the faces of a design. Every printed face of the stand's die is one (``die``: its part and face; it lands on the die
#: turned ``quarters`` clockwise from upright as it folds — the die drawn from the print side, seen from below, x as
#: the shopper sees it); the header is the back panel's own board doubled over, its folded leaf the shopper's "header
#: front". ``panel``: the picked picture's reading panel that places a face's words (None: a face with no words).
FACES = {
    'header': {'label': 'Stand header (front leaf)', 'panel': 'stand_header', 'die': ('tray', 'header front'),
               'quarters': 0},
    'header_back': {'label': 'Stand header (back leaf)', 'panel': None, 'die': ('tray', 'header back'), 'quarters': 2},
    'front': {'label': 'Stand front strip', 'panel': 'stand_base', 'die': ('tray', 'front panel'), 'quarters': 0},
    'side': {'label': 'Stand right side wall', 'panel': None, 'die': ('tray', 'right side'), 'quarters': 1},
    'left': {'label': 'Stand left side wall', 'panel': None, 'die': ('tray', 'left side'), 'quarters': 3},
    'back': {'label': 'Stand back wall', 'panel': None, 'die': ('tray', 'back panel'), 'quarters': 2},
    'bottle': {'label': 'Bottle front', 'panel': 'body_front', 'object': 'bottle-front'},
    'cap': {'label': 'Cap front', 'panel': 'cap_front', 'object': 'cap'},
}
K = 300 / 25.4                                    # px per mm at 300 PPI: the composer's raster of the stand
REMAP_COLUMNS = 1024        # OpenCV's remap takes maps under 32,767 a side: points are read in rows of this many


def read_between(field, points):
    """``field`` read bilinearly at each (x, y) point, between pixels; any number of points (round 4's 300 PPI faces
    sample more edge points than one remap column holds)."""
    xy = np.asarray(points, np.float32).reshape(-1, 2)
    n = len(xy)
    if not n:
        return np.zeros(0, np.float32)
    xy = np.vstack([xy, np.zeros(((-n) % REMAP_COLUMNS, 2), np.float32)]).reshape(-1, REMAP_COLUMNS, 2)
    return cv2.remap(np.asarray(field, np.float32), xy[..., 0], xy[..., 1], cv2.INTER_LINEAR).ravel()[:n]


def turn(img, quarters):
    """A picture turned ``quarters`` clockwise: a face as it folds onto the sheet (the reverse turn: upright)."""
    return np.ascontiguousarray(np.rot90(img, -quarters))


def face_mm_size(poly, quarters):
    """A face's upright size (w × h mm) from its polygon on the sheet, where it lies turned ``quarters``."""
    x0, y0, x1, y1 = poly.bounds
    w, h = x1 - x0, y1 - y0
    return (w, h) if quarters % 2 == 0 else (h, w)


def upright_polygon(poly, quarters, w, h):
    """A face's polygon in its upright frame (origin the picture's top-left, the bleed included): the sheet turned back
    by ``quarters`` counter-clockwise."""
    x0, y0, x1, y1 = poly.bounds
    W, H = w + 2 * STAND_BLEED_MM, h + 2 * STAND_BLEED_MM
    pts = []
    for X, Y in poly.exterior.coords:
        x, y = X - (x0 - STAND_BLEED_MM), Y - (y0 - STAND_BLEED_MM)
        for i in range(quarters % 4):
            # the inverse of the sheet's turn: a clockwise turn of a frame (fw × fh) maps (x, y) → (fh − y, x)
            x, y = y, (H if (quarters - 1 - i) % 2 == 0 else W) - x
        pts.append((x, y))
    return Polygon(pts)


def stand_face(key):
    return 'die' in FACES[key]


# --- the faces' geometry ----------------------------------------------------------------------------------------------

def die_of(geometry):
    from apps.dielines.geometry import counter_display
    return counter_display.build_die(geometry['record'])


def die_face(die, part_face):
    """A face by its die part and name; a slot-in header's leaves are the same faces on their own part."""
    for part in sorted(die.parts, key=lambda p: p.name != part_face[0]):
        for name, poly, _printed in part.faces:
            if name == part_face[1]:
                return part, poly
    raise ValueError('The die has no face called ' + part_face[1])


def face_geometry(key, brief, die):
    """A face's upright frame: its trim (w × h mm), its bleed and safe inset, and its outline in the frame (the bleed
    included, origin at the frame's top-left)."""
    spec = FACES[key]
    if stand_face(key):
        _part, poly = die_face(die, spec['die'])
        w, h = face_mm_size(poly, spec['quarters'])
        outline = upright_polygon(poly, spec['quarters'], w, h)
        return {'w_mm': w, 'h_mm': h, 'bleed_mm': STAND_BLEED_MM, 'safe_mm': STAND_SAFE_MM, 'outline': outline}
    dims = brief['dimensions_mm']
    w, cap = float(dims['width']), float(dims['cap_height'])
    h = cap if key == 'cap' else float(dims['height']) - cap
    return {'w_mm': w, 'h_mm': h, 'bleed_mm': 0.0, 'safe_mm': PRODUCT_SAFE_MM, 'outline': shp_box(0, 0, w, h)}


def trim_box(face):
    b = face['bleed_mm']
    return [b, b, b + face['w_mm'], b + face['h_mm']]


def placed(norm, target):
    x0, y0, x1, y1 = target
    return [x0 + norm[0] * (x1 - x0), y0 + norm[1] * (y1 - y0), x0 + norm[2] * (x1 - x0), y0 + norm[3] * (y1 - y0)]


def marks(key, inspection, brief, face, drawn=None):
    """The face's live words and logos in its upright frame (mm). The header's are placed from its drawn face
    (the dial type below: each shade label on its own colour band, the brand upright and ملمع شفاه on the navy ring); the
    front strip's logo and its one line "Lip Gloss / ملمع شفاه" are centred across the face at the reading's heights;
    the bottle's come from the reading's boxes. The words are the brief's COPY; the picture supplies only where."""
    from .round_files_export import glyph_metrics
    from .round_files_export import PT
    spec = FACES[key]
    out = {'type': [], 'logos': [], 'zones': []}
    if inspection.get('flat_pick'):
        return flat_marks(key, brief, face, drawn)  # a flat pick shows no words: the brief's, placed (2026-10-30)
    if spec['panel'] is None:
        return out
    info = inspection['panels'][spec['panel']]
    crop = info['crop_px']
    target = trim_box(face)
    fields = copy_fields(brief)
    foil = not stand_face(key)
    if key == 'bottle' and not ARABIC_TYPE:
        # English only (the owner, 2026-10-29): fewer lines with more space — the brand, the product and the shade's
        # name; the box the picture gave its Arabic line carries the shade's name, a gap opened between the two words
        info = dict(info, text=bottle_rows(info.get('text', []), fields))
    rows = text_rows(info, crop, fields)
    if key == 'header':
        if drawn is not None:
            colour = next((row['color'] for row in rows), '#E8C98A')
            ring = next((zone['color'] for zone in info.get('ornament_lettering', [])), colour)
            out['type'], out['placement'] = header_type(drawn['face'], drawn['template']['px_per_mm'], face, brief,
                                                             fields, label_colour=colour, ring_colour=ring)
        return out
    centre_x = (target[0] + target[2]) / 2
    if key == 'front':
        # the logo over its line as one block, the picture's proportions kept, brought inside the safe area and
        # centred in it (the photograph sets the line below the strip's 3 mm safe line)
        line = [row for row in rows if row['field'] in ('product_latin', 'product_arabic')]
        logos = [placed(_normal_box(row['box_px'], crop), target) for row in info.get('marks', [])]
        boxes = [placed(row['box_norm'], target) for row in line]
        parts = boxes + logos
        if parts:
            top, bottom = min(b[1] for b in parts), max(b[3] for b in parts)
            safe_top, safe_bottom = target[1] + face['safe_mm'], target[3] - face['safe_mm']
            scale = min(1.0, (safe_bottom - safe_top) / max(bottom - top, 1e-6))
            shift = (safe_top + safe_bottom) / 2 - (top + bottom) / 2 * scale
            fit = lambda y: y * scale + shift
            if boxes:
                y0, y1 = fit(min(b[1] for b in boxes)), fit(max(b[3] for b in boxes))
                out['type'] = product_line(fields, centre_x, (y0 + y1) / 2, y1 - y0, target[2] - target[0],
                                           colour=line[0]['color'], foil=foil, name='front',
                                           safe=(safe_top, safe_bottom))
            for box in logos:
                half = (box[2] - box[0]) * scale / 2
                out['logos'].append({'box_mm': [centre_x - half, fit(box[1]), centre_x + half, fit(box[3])],
                                     'rotation': 0, 'foil': True})
        return out
    for row in rows:
        box = placed(row['box_norm'], target)
        metric = glyph_metrics(row['copy'], row['face'])
        width, height = (box[2] - box[0]) * PT, (box[3] - box[1]) * PT
        if row['rotation'] in (90, 270):
            width, height = height, width
        ink = metric['box_em'][3] - metric['box_em'][1]
        size = max(5., min(height / max(ink, .1), width / max(metric['advance_em'], .1)))
        out['type'].append({'name': key + ':' + row['field'], 'copy': row['copy'], 'face': row['face'], 'box_mm': box,
                            'size_pt': size, 'align': 'center', 'rotation': row['rotation'], 'color': row['color'],
                            'foil': foil, 'copy_field': row['field']})
    for row in info.get('marks', []):
        out['logos'].append({'box_mm': placed(_normal_box(row['box_px'], crop), target),
                             'rotation': row.get('rotation', 0), 'foil': True})
    out['zones'] = ornament_rows(info, crop, brief)
    return out


#: A flat pick's words (the owner, 2026-10-30: "Place the words first"): a flat design shows none, so the brief's own
#: copy is placed — the logo over "Lip Gloss" in the header's plain label band and centred across the front strip,
#: "Lip Gloss" in the right wall's empty frame ("it's where the lettering goes"), and on the bottle the logo, the
#: product and the shade's name along its length; the header's back leaf, the left wall, the back and the cap none.
FLAT_WORDS = {'header': 'band', 'front': 'centre', 'side': 'frame', 'bottle': 'upright'}
PLAIN_STD = 12.0                                  # a label area: its 15 px neighbourhoods vary under this in grey
PLAIN_MIN_MM = 3.0                                # … and it is at least this tall and wide
BAND_LINE_MM = 12.0                               # a band under this tall takes the logo alone
WINDOW_MIN_MM = (5.0, 30.0)                       # a bottle's clear window holds its words when at least this big


def plain_area_mm(drawn):
    """The largest plain rectangle of a drawn face (its label band or empty frame), in its upright frame's mm."""
    with Image.open(drawn['face']) as image:
        grey = np.asarray(image.convert('L')).astype(np.float32)
    return plain_box(grey, printed_region(drawn['template']), drawn['template']['px_per_mm'])


def plain_box(grey, printed, k):
    """The largest plain rectangle of a picture (lightness, 2-D) inside its printed pixels, in mm at ``k`` px/mm, or None."""
    from scipy import ndimage
    mean = ndimage.uniform_filter(grey, 15)
    std = np.sqrt(np.maximum(ndimage.uniform_filter(grey * grey, 15) - mean * mean, 0))
    plain = std < PLAIN_STD
    if printed.shape == plain.shape:                             # inside the face's printed shape only
        plain &= ndimage.binary_erosion(printed, iterations=8)
    plain = ndimage.binary_opening(ndimage.binary_closing(plain, iterations=4), iterations=4)   # past the felt's grain
    small = plain[::4, ::4]
    x0, y0, x1, y1 = (4 * int(v) for v in _largest_rectangle(small))
    box = [x0 / k, y0 / k, x1 / k, y1 / k]
    if box[2] - box[0] < PLAIN_MIN_MM or box[3] - box[1] < PLAIN_MIN_MM:
        return None
    return box


def _flat_row(key, field, copy, box, rotation, foil):
    """One live line in a box (mm), its size the largest the box holds, as the reading's rows are set."""
    from .round_files_export import glyph_metrics
    from .round_files_export import PT
    face_name = face_for(copy)
    metric = glyph_metrics(copy, face_name)
    width, height = (box[2] - box[0]) * PT, (box[3] - box[1]) * PT
    if rotation in (90, 270):
        width, height = height, width
    ink = metric['box_em'][3] - metric['box_em'][1]
    size = max(MIN_SIZE_PT, min(height / max(ink, .1), width / max(metric['advance_em'], .1)))
    return {'name': key + ':' + field, 'copy': copy, 'face': face_name, 'box_mm': box, 'size_pt': size,
            'align': 'center', 'rotation': rotation, 'color': GOLD_HEX, 'foil': foil, 'copy_field': field}


def flat_marks(key, brief, face, drawn):
    """A flat pick's words and logo on one face (FLAT_WORDS), in its upright frame (mm)."""
    out = {'type': [], 'logos': [], 'zones': []}
    if drawn is not None and drawn.get('source') == 'plan':       # the one placement record's own words, in their zones
        words = json.loads(Path(drawn['plan']).read_text())['words']
        return dict(out, type=words['type'], logos=words['logos'], placement={'flat_words': FLAT_WORDS.get(key), 'zones': words['zones']})
    how = FLAT_WORDS.get(key)
    if how is None:
        return out
    fields = copy_fields(brief)
    foil = not stand_face(key)
    t = trim_box(face)
    if how in ('band', 'frame'):
        area = None
        if drawn is not None:
            area = plain_area_mm(drawn)
        if area is None:
            out['placement'] = {'flat_words': how, 'area_mm': None, 'why': 'no plain area to set the words in'}
            return out
        x0, y0, x1, y1 = (max(area[0], t[0]), max(area[1], t[1]), min(area[2], t[2]), min(area[3], t[3]))
        w, h, cx = x1 - x0, y1 - y0, (x0 + x1) / 2
        if how == 'band' and h < BAND_LINE_MM:
            # a thin band (round 4's header: 3.9 mm inside the trim) takes the logo alone, at three quarters of it
            out['logos'].append({'box_mm': [cx - 0.25 * w, y0 + 0.125 * h, cx + 0.25 * w, y0 + 0.875 * h],
                                 'rotation': 0, 'foil': True})
        elif how == 'band':
            out['logos'].append({'box_mm': [cx - 0.3 * w, y0 + 0.12 * h, cx + 0.3 * w, y0 + 0.52 * h],
                                 'rotation': 0, 'foil': True})
            out['type'] = product_line(fields, cx, y0 + 0.74 * h, 0.22 * h, w, colour=GOLD_HEX, foil=foil, name=key,
                                       safe=(y0, y1))
        else:
            out['type'] = product_line(fields, cx, (y0 + y1) / 2, 0.36 * h, 0.8 * w, colour=GOLD_HEX, foil=foil,
                                       name=key, safe=(y0, y1))
        out['placement'] = {'flat_words': how, 'area_mm': [round(v, 2) for v in (x0, y0, x1, y1)]}
        return out
    w, h, cx = t[2] - t[0], t[3] - t[1], (t[0] + t[2]) / 2
    if how == 'centre':
        safe_top, safe_bottom = t[1] + face['safe_mm'], t[3] - face['safe_mm']
        sh = safe_bottom - safe_top
        out['logos'].append({'box_mm': [cx - 0.16 * w, safe_top + 0.05 * sh, cx + 0.16 * w, safe_top + 0.5 * sh],
                             'rotation': 0, 'foil': True})
        out['type'] = product_line(fields, cx, safe_top + 0.75 * sh, 0.3 * sh, w, colour=GOLD_HEX, foil=foil,
                                   name=key, safe=(safe_top, safe_bottom))
        out['placement'] = {'flat_words': how}
        return out
    # the bottle: inside its clear window (its plain area) where it has one, else its whole front, along its length
    # reading bottom to top — the logo, the product, the shade's name (round 4: set over the woven border, its shade
    # name ran off the foot)
    x0, y0, x1, y1 = t
    window = None
    if drawn is not None:
        window = plain_area_mm(drawn)
    if window is not None and window[2] - window[0] >= WINDOW_MIN_MM[0] and window[3] - window[1] >= WINDOW_MIN_MM[1]:
        x0, y0, x1, y1 = window[0] + 1, window[1] + 1, window[2] - 1, window[3] - 1
    w, h, cx = x1 - x0, y1 - y0, (x0 + x1) / 2
    band = lambda a, b: [cx - 0.35 * w, y0 + a * h, cx + 0.35 * w, y0 + b * h]
    out['logos'].append({'box_mm': band(0.04, 0.40), 'rotation': 90, 'foil': True})
    out['type'] = [_flat_row(key, 'product_latin', fields['product_latin'], band(0.47, 0.70), 90, foil)]
    if 'shade_0' in fields:
        out['type'].append(_flat_row(key, 'shade_0', fields['shade_0'], band(0.76, 0.94), 90, foil))
    out['placement'] = {'flat_words': how, 'area_mm': [round(v, 2) for v in (x0, y0, x1, y1)]}
    return out


LINE_WIDTH_SHARE = 0.6                            # the line takes at most 60 % of the face's width


def product_line(fields, centre_x, centre_y, height_mm, width_mm, *, colour, foil, name, safe=None):
    """The brief's product COPY as one line, the Latin, the slash and the Arabic (as "Lip Gloss / ملمع شفاه"), set on a
    shared baseline and centred at (centre_x, centre_y): three runs, each centred on its own point, one word space of
    the Latin face apart, as the line is typed; every glyph inside ``safe`` (its top and bottom, mm) when given."""
    from .round_files_export import glyph_metrics
    from .round_files_export import PT
    parts = [(fields['product_latin'], 'latin', 'product_latin')]
    if fields.get('product_arabic'):                  # Arabic only where it is set (ARABIC_TYPE; English only since 2026-10-29)
        parts += [('/', 'latin', 'product'), (fields['product_arabic'], 'arabic', 'product_arabic')]
    parts = [part for part in parts if part[0]]
    metrics = [glyph_metrics(copy, face) for copy, face, _ in parts]
    latin = metrics[0]
    ink = latin['box_em'][3] - latin['box_em'][1]
    advances = [m['advance_em'] for m in metrics]
    space = glyph_metrics(' ', 'latin')['advance_em']
    span_em = sum(advances) + space * (len(parts) - 1)
    size_mm = min(height_mm / max(ink, .1), width_mm * LINE_WIDTH_SHARE / span_em)
    middle = (latin['box_em'][3] + latin['box_em'][1]) / 2
    if safe is not None:
        top, bottom = max(m['box_em'][3] for m in metrics), min(m['box_em'][1] for m in metrics)
        size_mm = min(size_mm, (centre_y - safe[0]) / max(top - middle, .01), (safe[1] - centre_y) / max(middle - bottom, .01))
    x = centre_x - span_em * size_mm / 2
    rows = []
    for (copy, face, field), advance in zip(parts, advances):
        rows.append({'name': name + ':' + field, 'copy': copy, 'face': face,
                     'center_mm': [x + advance * size_mm / 2, centre_y], 'angle_deg': 0.0, 'center_em_y': middle,
                     'size_pt': max(5., size_mm * PT), 'color': colour, 'foil': foil, 'copy_field': field})
        x += (advance + space) * size_mm
    return rows


# --- the template ------------------------------------------------------------------------------------------------------

def _rings(geom):
    return [list(g.exterior.coords) for g in (geom.geoms if hasattr(geom, 'geoms') else [geom]) if not g.is_empty]


def template(key, face, folder):
    """The sheet a product face is drawn on: white, the face's outline (its bleed included) TRANSPARENT at its true
    proportion — nothing else on it: no guide is ever drawn into the art (the guides live on the files' locked guides
    layer). The same picture is the mask. Returns its record: the frame's pixel box and px/mm."""
    folder.mkdir(parents=True, exist_ok=True)
    W, H = face['w_mm'] + 2 * face['bleed_mm'], face['h_mm'] + 2 * face['bleed_mm']
    orientation = 'landscape' if W >= H else 'portrait'
    SW, SH = SHEETS[orientation]
    k = min((SW - 2 * MARGIN_PX) / W, (SH - 2 * MARGIN_PX) / H)
    fw, fh = int(round(W * k)), int(round(H * k))
    fx, fy = (SW - fw) // 2, (SH - fh) // 2
    img = Image.new('RGBA', (SW, SH), (255, 255, 255, 255))
    hole = Image.new('L', (SW, SH), 0)
    printed = face['outline'].buffer(face['bleed_mm'], join_style=2) if face['bleed_mm'] else face['outline']
    for ring in _rings(printed):
        ImageDraw.Draw(hole).polygon([(fx + x * k, fy + y * k) for x, y in ring], fill=255)
    img.paste((0, 0, 0, 0), mask=hole)
    img.save(folder / 'template.png')
    return {'size': '%dx%d' % (SW, SH), 'frame_px': [fx, fy, fx + fw, fy + fh], 'px_per_mm': round(k, 6),
            'frame_mm': [W, H], 'template': str(folder / 'template.png'),
            'template_sha256': sha(folder / 'template.png'), 'rectangle': abs(printed.area - printed.envelope.area) < 1e-6}


def reference(key, inspection, source, folder):
    """The picked picture's view of a product face: its reading panel's crop."""
    crop = inspection['panels'][FACES[key]['panel']]['crop_px']
    with Image.open(source) as image:
        view = image.convert('RGB').crop(crop)
    longest = max(view.size)
    if longest < 1024:
        scale = 1024 / longest
        view = view.resize((round(view.width * scale), round(view.height * scale)), Image.LANCZOS)
    path = folder / 'reference.png'
    view.save(path)
    return {'path': str(path), 'sha256': sha(path), 'crop_px': crop}


#: the owner's ruling of 2026-10-29: designs are English only — Arabic is set on no face, label, carton or stand (the
#: company adds it if it wants it). The Arabic shaping code stays where it is, switched off: True sets it again.
ARABIC_TYPE = False
#: the type rules a face's preview was placed under: a preview from before is placed again ($0, round_files_gate.retype)
TYPE_REVISION = 'english-only+whole-painting+flat-words-2/2026-10-30'   # a flat pick's words; the bottle's in its window
NO_ARABIC = ' No Arabic lettering anywhere.'

NO_WORDS = ('No letters, numbers or words anywhere — leave the label areas as plain ground of their band colour; keep '
            'the gold tick scale, numerals as plain tick marks, rims and pointer. Every word on this face is set '
            'afterwards from the brief\'s COPY as live type.' + NO_ARABIC)
#: the owner's note, said last (round 4, 2026-10-30: "the band pattern across the whole strip, not plain green" came back
#: plain twice, the no-words line's "leave the label areas as plain ground" being the last word)
NOTE_LAST = ('The owner\'s note on this face comes before every line above, the plain label areas included: "%s".')
WHAT = {
    'bottle': 'This is the front of the bottle\'s body below the cap: the clear acrylic body with the gloss seen through it '
              'in its shade, drawn flat and front-on, with the printed decoration only where the picture shows it.',
    'cap': 'This is the front face of the gold square cap: the gold metal with its engraved gold line art (the dial, its '
           'needle, its tick marks and the star), drawn flat and front-on as one clean engraving.',
}


# A finding about the live type (its words, logo, spacing or place) is the type setter's to fix, never the drawing's:
# quoted to the image model, it is drawn as lettering (round 3's front strip, 2026-10-28).
TYPE_FINDING = re.compile(r'\b(live|type|typeset|letter(s|ing)?|words?|logo|brand|bbrose|slash|font|kerning|spacing|'
                          r'copy|labels?|text)\b|[\u0600-\u06FF]', re.IGNORECASE)


HARD_RULES = ('THE OWNER\'S HARD RULES. They come before image 2, the style and every other line here: wherever image '
              '2, the board or the design shows or names what they forbid, paint what they ask in its place.')
UPRIGHT_WORDS = ('Every figure, animal, flower and fruit on this face stands upright: the top of image 1\'s sheet is the '
                 'top of this face on the folded stand. Where image 2 shows one sideways or upside down, turn it upright.')


def hard_rules(banned, lines=(), notes=(), names=(), truths=()):
    """The owner's hard rules for one drawing (the owner, 2026-10-29, round 4: "My pick reason and my redraw notes
    must reach every face drawing as hard rules"): the round's banned motifs, the owner's lines on the round (the
    board choice, the pick) and the face's own notes, each quoted; a line naming another brand is never sent, and the
    brief's own words (``names``: the brand, the product, the shades) are never quoted, so no lettering is asked for."""
    from . import round_calls as image_guard
    rows = []
    if banned:
        rows.append('- Never draw these motifs, in any form or size: %s. Where image 2 shows one, draw in its place one '
                    'the owner\'s words name instead, else one of the design\'s other motifs.' % ', '.join(banned))
    # the brief's product truths ("The gold square cap stays gold") outrank image 2's ground too (round 4's cap)
    for label, items in (('The product\'s truth', truths), ('The owner\'s words', lines),
                         ('The owner\'s note on this face', notes)):
        for line in items:
            if not isinstance(line, str):
                continue
            line = ' '.join(line.split())
            for name in names:
                if name:
                    line = re.sub(re.escape(name), 'the named one', line, flags=re.I)
            if line and not image_guard.competitor_in(line):
                rows.append('- %s: "%s"' % (label, line))
    if not rows:
        return ''
    return '\n'.join([HARD_RULES] + rows)


def owner_note(note):
    """The owner's one-line Redraw note as it may reach the image model: trimmed to one line of NOTE_MAX characters;
    a note about the words (set afterwards as live type) is kept on the face's record but never drawn."""
    from . import round_calls as image_guard
    text = ' '.join(str(note or '').split())[:NOTE_MAX]
    if not text:
        return '', None
    if image_guard.competitor_in(text):
        return text, 'it names another brand, so it was not sent to the drawing'
    if TYPE_FINDING.search(text):
        return text, 'it is about the words, which are set as live type, so it was not sent to the drawing'
    return text, None


def prompt(key, face, *, note='', previous=False, rules=''):
    words = ['Image 1 is the sheet to draw on: a white ground with one TRANSPARENT shape, the only place to draw. It '
             'is the true flat shape of this face (%.1f × %.1f mm with its bleed). Fill it EXACTLY, edge to edge, with '
             'flat print artwork seen front-on: no perspective, no 3D, no shadow, no physical thickness, no product, no '
             'hands, no mockup, no guide lines, no labels. Keep the white around it white; do not move, resize, tilt or '
             'round it.' % (face['w_mm'] + 2 * face['bleed_mm'], face['h_mm'] + 2 * face['bleed_mm']),
             'Image 2 is the picked picture\'s view of this face, the design to follow: the same ground, colours, '
             'materials, motifs, gold line art and layout, drawn flat and front-on. ' +
             WHAT[key].format(bleed=face['bleed_mm'], trim_h=face['h_mm'])]
    if rules:
        words.append(rules)
    if previous:
        words.append('Image 3 is your previous drawing of this face. The owner asks: "%s". Draw the face again with '
                     'that change, keeping what was right.' % note)
    elif note:
        words.append('The owner asks: "%s".' % note)
    words.append(NO_WORDS)
    return '\n\n'.join(words)


# --- one face drawn ---------------------------------------------------------------------------------------------------

def cut_face(raw_path, record, folder):
    """A product face cut from its edit at the template's frame, as drawn: nothing is erased after drawing (owner,
    2026-10-28)."""
    x0, y0, x1, y1 = record['frame_px']
    with Image.open(raw_path) as image:
        image.convert('RGB').crop((x0, y0, x1, y1)).save(folder / 'face.png')
    path = folder / 'face.png'
    return {'frame_px': record['frame_px'], 'face': str(path), 'face_sha256': sha(path),
            'rule': 'cut at the template\'s frame; nothing erased'}


def draw_face(ctx, key, n, face, inspection, *, note='', previous=None, rules=''):
    """Drawing ``n`` of a product face: one paid edit in its own durable folder (faces/<key>/drawings/<n>), cut as drawn —
    nothing is erased after drawing. Restartable: the call's saved reply is never bought twice. ``note``: the owner's
    Redraw note (owner_note); ``previous``: the drawing it answers, given as image 3."""
    folder = drawing_folder(ctx.root, key, n)
    record_path = folder / 'record.json'
    if record_path.exists():
        prior = json.loads(record_path.read_text())
        if sha(prior['face']) != prior['face_sha256']:
            raise ValueError('A drawn face changed after it was cut: ' + key)
        return prior
    sheet = template(key, face, folder)
    ref = reference(key, inspection, ctx.root / 'source.png', folder)
    sent, withheld = owner_note(note)
    words = prompt(key, face, note='' if withheld else sent, previous=bool(previous) and bool(sent) and not withheld,
                   rules=rules)
    references = [ref['path']] + ([previous] if previous and sent and not withheld else [])
    call = ctx.face_edit('face/%s/%d' % (key, n), words, folder / 'call', template=sheet['template'],
                         references=references, size=sheet['size'])
    drawn = cut_face(folder / 'call' / 'raw.png', sheet, folder)
    record = dict(drawn, key=key, n=n, label=FACES[key]['label'], template=sheet, reference=ref, prompt=words,
                  note=sent, note_withheld=withheld, previous=previous, cost_usd=call.get('cost_usd'),
                  reservation_id=call['reservation_id'])
    flow.write_json(record_path, record)
    return record


def drawing_folder(root, key, n):
    return Path(root) / 'faces' / key / 'drawings' / str(n)


# --- the bottle's and the cap's flat nets (die-first for the products, the owner's goal of 2026-10-29) ----------------
# A square product's printed sides laid out flat, as the stand's die is: the bottle's four body sides in a strip, front
# first; the cap's four sides with its top above the front. Built as a counter_display Part so the die writer's flat
# frame, template, masks and die application work on it unchanged; painted with one edit; its faces cut from it.

NET_SIDES = (('front', 'w'), ('right side', 'd'), ('back', 'w'), ('left side', 'd'))


def product_net(key, brief):
    """The product's net (counter_display Die, one part named ``key``), mm, the front's top-left at the origin."""
    from shapely.geometry import LineString
    from apps.dielines.geometry import counter_display as cd
    dims = brief['dimensions_mm']
    w, d, cap = float(dims['width']), float(dims['depth']), float(dims['cap_height'])
    # each product's sides: the cap's below its top (laid above the front), the bottle's body below the cap
    h, top = {'cap': (cap, d), 'bottle': (float(dims['height']) - cap, 0.0)}[key]
    faces_, creases, x = [], [], 0.0
    for name, along in NET_SIDES:
        span = w if along == 'w' else d
        faces_.append((name, shp_box(x, top, x + span, top + h), True))
        if x > 0:
            creases.append(('%s fold' % name, LineString([(x, top), (x, top + h)])))
        x += span
    if key == 'cap':
        faces_.append(('top', shp_box(0, 0, w, d), True))
        creases.append(('top fold', LineString([(0, d), (w, d)])))
    part = cd.Part(key, {'bottle': 'Bottle body net', 'cap': 'Cap net'}[key], faces_, creases)
    return cd.Die([part], x + 2 * STAND_BLEED_MM, top + h + 2 * STAND_BLEED_MM, [], (0.0, 0.0, 0.0),
                  '%s net' % key)


def net_face_box(die, key, name='front'):
    part = next(p for p in die.parts if p.name == key)
    return next(poly for face, poly, _printed in part.faces if face == name).bounds


def net_setup(key, brief, folder):
    """The net's template (counter_display_files.flat_template on the product's part), written once into the drawing's
    own folder (the face edit's template.png); a changed net never reuses it."""
    from apps.dielines.exporters import counter_display_files as cdf
    folder = Path(folder)
    die = product_net(key, brief)
    spec = {'key': key, 'dimensions_mm': {k: brief['dimensions_mm'][k] for k in ('width', 'depth', 'height', 'cap_height')}}
    path = folder / 'net.json'
    if path.exists():
        saved = json.loads(path.read_text())
        if saved['net_digest'] != _digest(spec) or sha(folder / 'template.png') != saved['template_sha256']:
            raise ValueError('The net template no longer matches the product\'s dimensions.')
        return die, saved
    frame = cdf.flat_frame(die, part=key)
    record = cdf.flat_template(die, frame, folder, up={name: 0 for name, _a in NET_SIDES} | {'top': 0})
    record.update(net_digest=_digest(spec), template_sha256=sha(folder / 'template.png'), net=spec)
    flow.write_json(path, record)
    return die, record


#: a product net drawn in its stand's design (round 4, 2026-10-29: both caps came back on the header's green ground,
#: told to take "its ground, colours" from image 2): the design's motif goes onto the product's own material
STYLE_ONLY_WORDS = {
    'cap': ('Image 2 is the header of the counter stand as the owner\'s picked flat design paints it. Carry its motif and '
            'line art onto the cap as engraving or foil on the cap\'s own gold metal: the cap\'s ground is gold on every '
            'side and on its top, never image 2\'s ground colour, so the product and its stand are one family. '),
    'bottle': ('Image 2 is the header of the counter stand as the owner\'s picked flat design paints it. Carry its motif, '
               'colours and finish onto the bottle as print on its clear acrylic body: where nothing is printed the body '
               'is clear, the gloss seen through it in its shade, never image 2\'s ground colour, so the product and '
               'its stand are one family. Print only the motifs and the gold line art, with no ground colour or solid '
               'fill behind them anywhere, the label areas included: the clear body and the gloss show between every '
               'motif, and nothing is opaque. '),
}


def net_prompt(key, setup, *, note='', previous=False, style_only=False, rules=''):
    W, H = setup['frame']['canvas_px']
    rows = ['- %s: x %d–%d, y %d–%d px' % ((face['name'].upper(),) + tuple(int(round(v)) for v in
                                         (face['box_px'][0], face['box_px'][2], face['box_px'][1], face['box_px'][3])))
            for face in setup['faces'] if face['printed']]
    thing = {'bottle': 'the square lip gloss bottle\'s body below its cap', 'cap': 'the square gold cap'}[key]
    words = ['Image 1 is a flat net, drawn by our engine at its true shape on a %d × %d sheet: the printed sides of %s, '
             'laid out flat — %s. Its TRANSPARENT areas are those sides and their 3 mm bleed: paint flat print artwork '
             'into them, edge to edge and on into the bleed. Everything else stays exactly as it is: the white paper, '
             'every line and the names in the margin. The sides (pixels; x from the left, y from the top; each one '
             'upright):' % (W, H, thing, 'four sides in a strip, front first, then right side, back, left side'
                            if key == 'bottle' else 'its four sides in a strip, front first, and its top above the front'),
             '\n'.join(rows),
             (STYLE_ONLY_WORDS[key] if style_only else
              'Image 2 is the picked picture\'s view of the front: paint the FRONT as it shows it, flat and front-on. ') +
             WHAT[key] + ' The other sides continue its ground, material and finish around the product as the picture '
             'implies, and meet the front across each fold: no perspective, no 3D, no shadow, no product drawn, no '
             'mockup, no guide lines.']
    if rules:
        words.append(rules)
    if previous:
        words.append('Image 3 is your previous painting of this net. The owner asks: "%s". Paint it again with that '
                     'change, keeping what was right.' % note)
    elif note:
        words.append('The owner asks: "%s".' % note)
    words.append(NO_WORDS)
    if note:
        words.append(NOTE_LAST % note)
    return '\n\n'.join(words)


def settle_net(raw_path, die, setup, folder, key):
    """A painted net: its die applied again (nothing erased inside it), the flat net and each side cut at its own
    outline (the front is the face the files use)."""
    from apps.dielines.exporters import counter_display_files as cdf
    folder = Path(folder)
    frame = setup['frame']
    masks = cdf.flat_masks(die, frame)
    with Image.open(folder / 'template.png') as image:
        sheet = np.asarray(image.convert('RGBA'))
    with Image.open(raw_path) as image:
        raw = np.asarray(image.convert('RGB'))
    flat, art = cdf.apply_die(raw, sheet, masks['paint'])
    proof = cdf.die_proof(raw, sheet, flat, masks['paint'], masks['owner'], masks['names'])
    Image.fromarray(flat, 'RGB').save(folder / 'net.png')
    Image.fromarray(art, 'RGBA').save(folder / 'net-art.png')
    sides = {}
    for name, _along in NET_SIDES + (('top', 'w'),) if key == 'cap' else NET_SIDES:
        x0, y0, x1, y1 = net_face_box(die, key, name)
        (u0, v0), (u1, v1) = cdf.flat_px(frame, x0, y0), cdf.flat_px(frame, x1, y1)
        box = tuple(int(round(v)) for v in (u0, v0, u1, v1))
        path = folder / ('face.png' if name == 'front' else 'side-%s.png' % name.replace(' ', '-'))
        Image.fromarray(flat[box[1]:box[3], box[0]:box[2]]).save(path)
        sides[name] = {'path': str(path), 'sha256': sha(path), 'box_px': list(box)}
    return {'flat': str(folder / 'net.png'), 'flat_sha256': sha(folder / 'net.png'),
            'art': str(folder / 'net-art.png'), 'art_sha256': sha(folder / 'net-art.png'),
            'sheet': str(folder / 'sheet.png'), 'sides': sides, 'proof': proof, 'size_mm': [die.sheet_w, die.sheet_h]}


def draw_net(ctx, key, n, inspection, *, note='', previous=None, rules='', quality='high'):
    """Drawing ``n`` of a product face, die-first: its net's template painted with one paid edit (image 1 the template,
    image 2 the picked picture's view of the face, image 3 the previous painting for a Redraw with a note), the net's
    die applied again, the front cut at its own outline (the face the files use) and the other sides kept for the wrap
    view. Restartable: the call's saved reply is never bought twice."""
    folder = drawing_folder(ctx.root, key, n)
    record_path = folder / 'record.json'
    if record_path.exists():
        prior = json.loads(record_path.read_text())
        if sha(prior['face']) != prior['face_sha256']:
            raise ValueError('A drawn face changed after it was cut: ' + key)
        return prior
    folder.mkdir(parents=True, exist_ok=True)
    die, setup = net_setup(key, ctx.brief, folder)
    ref = reference(key, inspection, ctx.root / 'source.png', folder)
    sent, withheld = owner_note(note)
    redraw = bool(previous) and bool(sent) and not withheld
    words = net_prompt(key, setup, note='' if withheld else sent, previous=redraw,
                       style_only=bool(inspection['panels'][FACES[key]['panel']].get('style_only')), rules=rules)
    call = ctx.face_edit('face/%s/%d' % (key, n), words, folder / 'call', template=folder / 'template.png',
                         references=[ref['path']] + ([previous] if redraw else []), size=setup['frame']['size'],
                         quality=quality)
    frame = setup['frame']
    net = settle_net(folder / 'call' / 'raw.png', die, setup, folder, key)
    sides = net['sides']
    front = sides['front']
    w, h = (lambda b: (b[2] - b[0], b[3] - b[1]))(net_face_box(die, key))
    record = {'frame_px': front['box_px'], 'face': front['path'], 'face_sha256': front['sha256'],
              'rule': 'the net\'s die applied again to its painting; the front cut at its own outline; nothing erased',
              'key': key, 'n': n, 'label': FACES[key]['label'], 'source': 'net',
              'template': {'size': frame['size'], 'frame_mm': [w, h], 'px_per_mm': frame['px_per_mm'],
                           'frame_px': front['box_px'], 'template': str(folder / 'template.png'),
                           'template_sha256': setup['template_sha256'], 'net': True},
              'native_ppi': frame['dpi_at_1to1'],
              'net': net,
              'reference': ref, 'prompt': words, 'note': sent, 'note_withheld': withheld, 'previous': previous,
              'cost_usd': call.get('cost_usd'), 'reservation_id': call['reservation_id']}
    flow.write_json(record_path, record)
    return record


# --- the stand designed flat (owner, 2026-10-28): the die first, the design painted on it -----------------------------

UP_WORDS = {0: 'its top is toward the top of the sheet', 1: 'its top is toward the right of the sheet',
            2: 'its top is toward the bottom of the sheet', 3: 'its top is toward the left of the sheet'}
FLAT_NO_WORDS = ('No letters, numbers or words anywhere in the artwork: every word is set afterwards from the brief\'s '
                 'COPY as live type and the logo is placed by our engine; leave plain ground where words will stand.'
                 + NO_ARABIC)


def flat_up():
    """Each printed face of the die and the quarters it is turned clockwise onto the die from upright."""
    return {FACES[key]['die'][1]: FACES[key]['quarters'] for key in FACES if stand_face(key)}


def flat_root(root):
    return Path(root) / 'flat'


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def flat_setup(geometry, folder):
    """The engine's flat die, drawn before any painting, at $0: its transform, the painting's template and the owner's
    template sheet (counter_display_files.flat_template). Written once; a changed die never reuses it."""
    from apps.dielines.exporters import counter_display_files as cdf
    folder = Path(folder)
    path, die_digest = folder / 'template.json', _digest(geometry['record'])
    if path.exists():
        saved = json.loads(path.read_text())
        if saved['die_digest'] != die_digest or sha(folder / 'template.png') != saved['template_sha256']:
            raise ValueError('The flat template no longer matches the stand\'s die.')
        return saved
    die = die_of(geometry)
    record = cdf.flat_template(die, cdf.flat_frame(die), folder, up=flat_up())
    record.update(die_digest=die_digest, template_sha256=sha(folder / 'template.png'),
                  sheet_sha256=sha(folder / 'sheet.png'))
    flow.write_json(path, record)
    return record


def flat_prompt(setup, *, style, keep='', panel=None, note=''):
    """The words of one painting of the flat die, or (``panel``) of one printed face on it with the rest kept."""
    W, H = setup['frame']['canvas_px']
    rows = []
    for face in setup['faces']:
        if face['printed']:
            x0, y0, x1, y1 = (int(round(v)) for v in face['box_px'])
            rows.append('- %s%s: x %d–%d, y %d–%d px; %s.' % (
                face['name'].upper(), ' (the shopper sees it)' if face['shopper'] else '', x0, x1, y0, y1,
                UP_WORDS[setup['up'][face['name']] % 4]))
    if panel is None:
        first = ('Image 1 is a flat die: the cutting pattern of a folding cardboard counter stand, drawn by our engine '
                 'at its true shape on a %d × %d sheet. Its TRANSPARENT areas are the printed faces and their 3 mm '
                 'bleed: paint flat print artwork into them, edge to edge and on into the bleed. Everything else stays '
                 'exactly as it is: the white paper, the grey parts (inside faces, glue flaps and tabs, never printed), '
                 'every line and the names in the margin. The printed faces (pixels; x from the left, y from the top):'
                 % (W, H))
    else:
        first = ('Image 1 is our flat die with its artwork painted. Its one TRANSPARENT area is the %s and its bleed: '
                 'paint that face again, flat, edge to edge and into the bleed, so that it meets the art around it '
                 'across every fold. Leave every other pixel exactly as it is. The printed faces (pixels; x from the '
                 'left, y from the top):' % panel.upper())
    words = [first, '\n'.join(rows),
             'Turn each face\'s artwork to its own fold before you paint it: every figure, animal, flower and fruit '
             'stands upright on its own face as the list above says, so that it stands upright on the folded stand. '
             'On a face whose top is toward the bottom of the sheet, paint them upside down on this sheet; on a face '
             'whose top is toward the left or the right of the sheet, paint them turned a quarter that way. Never '
             'paint every face upright on the sheet.',
             'How it folds: the walls rise from the grey floor, and the header front folds over the top of the header '
             'back to face the shopper. Art that meets across a fold continues across it: the walls meet at the '
             'stand\'s four corners, and the back panel runs straight on into the header back.',
             'Image 2 is the style reference: %s Paint in its colours, materials, finishes, motif and texture. This is '
             'the flat print sheet itself: no product, no stand drawn in perspective, no 3D, no shadow, no mockup, no '
             'guide lines.' % style]
    if keep:
        words.append(keep)
    if note:
        words.append('The owner asks: "%s".' % note)
    words.append(FLAT_NO_WORDS)
    return '\n\n'.join(words)


def seam_colour(flat, die, frame):
    """ΔE00 across every fold where printed art meets printed art (counter_display_files.fold_pairs):
    the 3 × 3 px mean either side of each sample. Reported, never a block."""
    from apps.dielines.exporters import counter_display_files as cdf
    h, w = flat.shape[:2]
    padded = np.pad(flat.astype(np.float64), ((1, 1), (1, 1), (0, 0)), mode='edge')
    mean = sum(padded[dy:dy + h, dx:dx + w] for dy in range(3) for dx in range(3)) / 9
    rows = []
    for seam in cdf.fold_pairs(die, frame):
        a = np.array([mean[y, x] for (x, y), _other in seam['pairs']])
        b = np.array([mean[y, x] for _one, (x, y) in seam['pairs']])
        d = delta_e00(srgb_to_lab(a), srgb_to_lab(b))
        rows.append({'seam': seam['seam'], 'kind': seam['kind'], 'samples': int(d.size),
                     'delta_e00_mean': round(float(d.mean()), 2), 'delta_e00_p90': round(float(np.percentile(d, 90)), 2),
                     'delta_e00_max': round(float(d.max()), 2)})
    return {'schema': 'flat_fold_continuity/1', 'metric': 'CIEDE2000 (delta_e00), 3 × 3 px means 1 mm '
            'either side', 'seams': rows, 'rule': 'reported, never a block'}


def settle_flat(raw_path, root, folder, geometry, *, base=None, panel=None):
    """The die applied again to a painting (counter_display_files.apply_die): inside the printed faces and their bleed
    the painting stands — for a Redraw (``panel``) only inside that face's own part of them, the ``base`` painting's
    pixels elsewhere — and every other pixel is the template's. Writes art.png (the printed faces alone: the stand's
    one raster), flat.png, view.png (the engine's cut and crease drawn over), proof.json (the die-match proof and the
    1:1 PDF read back) and continuity.json (ΔE00 across every fold); returns the painting's record."""
    from apps.dielines.exporters import counter_display_files as cdf
    root, folder = Path(root), Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    frame = json.loads((root / 'template.json').read_text())['frame']
    die = die_of(geometry)
    masks = cdf.flat_masks(die, frame)
    with Image.open(root / 'template.png') as image:
        template = np.asarray(image.convert('RGBA'))
    with Image.open(raw_path) as image:
        raw = np.asarray(image.convert('RGB'))
    if panel is None:
        region, given, painted = masks['paint'], template, raw
    else:
        region = masks['owner'] == masks['names'].index(panel) + 1
        with Image.open(base['flat']) as image:
            before = np.asarray(image.convert('RGB'))
        given = np.dstack([np.where(region[..., None], 255, before), np.where(region, 0, 255)]).astype(np.uint8)
        painted = np.where(region[..., None], raw, before).astype(np.uint8)
    flat, art = cdf.apply_die(painted, template, masks['paint'])
    proof = cdf.die_proof(raw, given, flat, region, masks['owner'], masks['names'])
    Image.fromarray(flat, 'RGB').save(folder / 'flat.png')
    Image.fromarray(art, 'RGBA').save(folder / 'art.png')
    cdf.die_view(flat, die, frame).save(folder / 'view.png')
    box = cdf.flat_box_mm(frame)
    cdf.write_pdf(die, geometry['record'], folder / 'die-flat.pdf', {'path': folder / 'art.png', 'box_mm': box})
    proof.update(pdf=cdf.pdf_readback(folder / 'die-flat.pdf', die, geometry['record'], box), panel=panel,
                 dpi_at_1to1=frame['dpi_at_1to1'],
                 by_construction='every pixel off the printed faces and their bleed is the template\'s own; the cut '
                                 'and crease on view.png are the engine\'s polygons through the one transform')
    continuity = seam_colour(flat, die, frame)
    flow.write_json(folder / 'proof.json', proof)
    flow.write_json(folder / 'continuity.json', continuity)
    out = {'panel': panel, 'base': base['n'] if base else None, 'proof': proof, 'continuity': continuity}
    for name in ('flat', 'art', 'view'):
        out[name], out[name + '_sha256'] = str(folder / (name + '.png')), sha(folder / (name + '.png'))
    return out


def _checked(record_path, *keys):
    record = json.loads(Path(record_path).read_text())
    for key in keys:
        if sha(record[key]) != record[key + '_sha256']:
            raise ValueError('A flat painting or face changed after it was made: ' + str(record_path))
    return record


def current_painting(root):
    """The painting the stand faces are cut from now: the whole die's, or a Redraw's that repainted one face."""
    pointer = flat_root(root) / 'current.json'
    if not pointer.exists():
        return None
    return _checked(Path(root) / json.loads(pointer.read_text())['record'], 'flat', 'art')


def _set_current(root, record_path):
    flow.write_json(flat_root(root) / 'current.json',
                    {'record': str(Path(record_path).resolve().relative_to(Path(root).resolve()))})


def paint_flat(ctx, n, geometry, style):
    """Painting ``n`` of the whole flat die: one paid edit (image 1 the template and its mask, image 2 the style
    reference), the die applied again to it. Restartable: a saved reply is never bought twice."""
    folder = flat_root(ctx.root) / 'paintings' / str(n)
    record_path = folder / 'record.json'
    if not record_path.exists():
        setup = flat_setup(geometry, flat_root(ctx.root))
        words = flat_prompt(setup, style=style['words'], keep=style.get('keep', ''))
        call = ctx.face_edit('flat/stand/%d' % n, words, folder / 'call', template=flat_root(ctx.root) / 'template.png',
                             references=[style['path']], size=setup['frame']['size'])
        record = settle_flat(folder / 'call' / 'raw.png', flat_root(ctx.root), folder, geometry)
        record.update(n=n, prompt=words, style=style, cost_usd=call.get('cost_usd'), reservation_id=call['reservation_id'])
        flow.write_json(record_path, record)
    _set_current(ctx.root, record_path)
    return _checked(record_path, 'flat', 'art')


def painted_face(painting, key, geometry):
    """A stand face's upright picture (its bleed included) cut from a flat painting at the die's transform and turned
    upright (turn, the composer's own turn undone), its frame (w × h mm, the bleed included) and its
    pixel box on the painting."""
    from apps.dielines.exporters import counter_display_files as cdf
    die = die_of(geometry)
    frame = cdf.flat_frame(die)
    _part, poly = die_face(die, FACES[key]['die'])
    b, (x0, y0, x1, y1) = STAND_BLEED_MM, poly.bounds
    (u0, v0), (u1, v1) = cdf.flat_px(frame, x0 - b, y0 - b), cdf.flat_px(frame, x1 + b, y1 + b)
    box = [int(round(u0)), int(round(v0)), int(round(u1)), int(round(v1))]
    with Image.open(painting['flat']) as image:
        crop = np.asarray(image.convert('RGB'))[box[1]:box[3], box[0]:box[2]]
    w, h = face_mm_size(poly, FACES[key]['quarters'])
    return turn(crop, (4 - FACES[key]['quarters']) % 4), [w + 2 * b, h + 2 * b], box


def painted_plain(painting, key, geometry):
    """Whether a stand face is plain in the picked flat painting itself — one ground, nothing drawn on it (the owner's
    ruling of 2026-10-29: a face whose art is only the board is never painted): its printed shape (the die's polygon,
    STAND_BLEED_MM inside the trim, where a neighbour's art can cross a fold) with at most PLAIN['share'] of its pixels
    further than PLAIN['delta_e'] from their median, as plain_check measures a drawing. $0."""
    from PIL import ImageDraw
    from apps.dielines.exporters import counter_display_files as cdf
    die = die_of(geometry)
    frame = cdf.flat_frame(die)
    _part, poly = die_face(die, FACES[key]['die'])
    inner = poly.buffer(-STAND_BLEED_MM)
    b, (x0, y0, x1, y1) = STAND_BLEED_MM, poly.bounds
    (u0, v0), (u1, v1) = cdf.flat_px(frame, x0 - b, y0 - b), cdf.flat_px(frame, x1 + b, y1 + b)
    box = [int(round(min(u0, u1))), int(round(min(v0, v1))), int(round(max(u0, u1))), int(round(max(v0, v1)))]
    with Image.open(painting['flat']) as image:
        rgb = np.asarray(image.convert('RGB'))[box[1]:box[3], box[0]:box[2]]
    mask = Image.new('L', (rgb.shape[1], rgb.shape[0]), 0)
    parts = [] if inner.is_empty else [inner] if inner.geom_type == 'Polygon' else list(inner.geoms)
    for part in parts:
        ImageDraw.Draw(mask).polygon([tuple(np.subtract(cdf.flat_px(frame, x, y), box[:2])) for x, y in part.exterior.coords],
                                     fill=255)
    keep = np.asarray(mask) > 0
    if keep.sum() < 50:
        return {'schema': 'painted_plain/1', 'share_over': None, 'threshold': dict(PLAIN), 'plain': False,
                'why': 'too small on the painting to read'}
    lab = srgb_to_lab(rgb[keep].astype(np.float64))
    median = np.broadcast_to(np.median(lab, axis=0), lab.shape)
    share = float((delta_e00(lab, median) > PLAIN['delta_e']).mean())
    return {'schema': 'painted_plain/1', 'share_over': round(share, 4), 'threshold': dict(PLAIN),
            'plain': share <= PLAIN['share']}


def flat_face(root, key, n, painting, geometry, **extra):
    """Drawing ``n`` of a stand face, taken straight from a flat painting (painted_face). Nothing is redrawn or
    re-fitted."""
    folder = drawing_folder(root, key, n)
    record_path = folder / 'record.json'
    if record_path.exists():
        return _checked(record_path, 'face')
    folder.mkdir(parents=True, exist_ok=True)
    upright, frame_mm, box = painted_face(painting, key, geometry)
    Image.fromarray(upright).save(folder / 'face.png')
    record = dict(extra, key=key, n=n, label=FACES[key]['label'], face=str(folder / 'face.png'),
                  face_sha256=sha(folder / 'face.png'), source='flat', painting=painting['flat'],
                  painting_sha256=painting['flat_sha256'], painting_art=painting['art'],
                  painting_art_sha256=painting['art_sha256'], painting_n=painting['n'], box_px=box,
                  template={'frame_mm': frame_mm, 'px_per_mm': upright.shape[1] / frame_mm[0]},
                  rule='cut straight from the flat painting at the die\'s transform, turned upright; nothing redrawn')
    flow.write_json(record_path, record)
    return record


def repaint_face(ctx, key, n, base, geometry, style, *, note=''):
    """A Redraw of a stand face: one paid edit on the same template — image 1 the current flat art with only this face
    and its bleed transparent, image 2 the style reference — settled as a new painting of the whole die (every other
    face's pixels kept byte for byte), and the face cut from it."""
    from apps.dielines.exporters import counter_display_files as cdf
    folder = drawing_folder(ctx.root, key, n)
    if (folder / 'record.json').exists():
        return _checked(folder / 'record.json', 'face')
    folder.mkdir(parents=True, exist_ok=True)
    setup = flat_setup(geometry, flat_root(ctx.root))
    name = FACES[key]['die'][1]
    sent, withheld = owner_note(note)
    painting_record = folder / 'painting' / 'record.json'
    if not painting_record.exists():
        masks = cdf.flat_masks(die_of(geometry), setup['frame'])
        region = masks['owner'] == masks['names'].index(name) + 1
        with Image.open(base['flat']) as image:
            before = np.asarray(image.convert('RGB'))
        given = np.dstack([np.where(region[..., None], 255, before), np.where(region, 0, 255)]).astype(np.uint8)
        Image.fromarray(given, 'RGBA').save(folder / 'template.png')
        words = flat_prompt(setup, style=style['words'], keep=style.get('keep', ''), panel=name,
                            note='' if withheld else sent)
        call = ctx.face_edit('face/%s/%d' % (key, n), words, folder / 'call', template=folder / 'template.png',
                             references=[style['path']], size=setup['frame']['size'])
        painting = settle_flat(folder / 'call' / 'raw.png', flat_root(ctx.root), folder / 'painting', geometry,
                               base=base, panel=name)
        painting.update(n='%s/%d' % (key, n), prompt=words, style=style, cost_usd=call.get('cost_usd'),
                        reservation_id=call['reservation_id'])
        flow.write_json(painting_record, painting)
    _set_current(ctx.root, painting_record)
    painting = _checked(painting_record, 'flat', 'art')
    return flat_face(ctx.root, key, n, painting, geometry, note=sent, note_withheld=withheld,
                     cost_usd=painting.get('cost_usd'), reservation_id=painting.get('reservation_id'))


# --- each stand face drawn again at 300 PPI on its own outline (the owner's goal of 2026-10-29) ------------------------
# The whole-die painting is the idea (one edit of the die: about 2.35 px/mm, 60 dpi at 1:1 on round 3); each printed face
# is then drawn at full resolution on its own outline, following its crop of that painting, and checked against it.

PANEL_MARGIN_PX = 32
PANEL_MIN_PX, PANEL_MAX_PX = 655_360, 2560 * 1440   # gpt-image-2: at least 0.65 MP; above 2560 × 1440 experimental
CANVAS_PX = 1536 * 1024                             # the two fixed canvases the edit hold was measured on
AGAINST_BAR = {'median': 10.0, 'p90': 20.0}         # ΔE00 of a 16 × 16 grid's mean colours against the painting's crop
#: a stand face's crop of the settled painting is followed only where the painting kept that face (the owner's goal of
#: 2026-10-29: round 3's first real painting stretched the die, registration IoU 0.53, the side walls 0.26 and 0.31
#: covered): its die-match coverage at least this, and at most this share of its printed pixels (bleed included) left
#: in the template's own unpainted colours (near-neutral and light: the template's white and light grey)
RELIABLE_CROP = {'coverage': 0.9, 'unpainted_share': 0.5}
#: a face the owner's policy names plain: at most this share of its printed pixels further than this CIEDE2000 from
#: the face's own median colour (round 3's back wall: an invented gold gauge and gold edges on plain board)
PLAIN = {'delta_e': 15.0, 'share': 0.02}


# Each face's set-aside, measured on round 4's own ledger (the owner, 2026-10-29: "Each face's set-aside should be its
# measured cost, not a flat $0.35"): gpt-image-2's output per megapixel of canvas at each quality, the most measured
# (high: the back panel's 8,411 tokens at 1.85 MP; medium: a design's 1,551 at 1.57 MP), each input picture's tokens
# per megapixel (2,960 for a 1.85 MP sheet and its reference; 3,072 for two 1.57 MP pictures), the stream's two
# partial pictures, the words, and a 15 % margin. Every round-4 call settled under it (the ledger, 2026-10-29).
OUTPUT_TOKENS_PER_MP = {'high': 4553, 'medium': 986}
INPUT_TOKENS_PER_MP = 1000
PARTIAL_TOKENS = 200
HOLD_MARGIN = 1.15
#: the owner: "Draw faces at medium quality where the eye can't see the difference. Keep the header and the bottle at
#: high." — the shopper's face of the stand and the product stay high; the walls, the back, the header's back leaf,
#: the front strip and the cap are drawn at medium, on a round made under these rules (FACE_RULES on its record)
HIGH_FACES = ('header', 'bottle')
FACE_RULES = 'measured-holds+medium-faces/2026-10-29'


def face_quality(record, key):
    """The quality a face is drawn at: medium for a round made under FACE_RULES, except the header and the bottle."""
    ruled = isinstance(record.artifacts, dict) and record.artifacts.get('face_rules') == FACE_RULES
    if ruled and key not in HIGH_FACES:
        return 'medium'
    return 'high'


def edit_cost(size, quality='high', inputs=(), words=''):
    """What one face edit costs on the measured rates: its canvas's output at its quality, its input pictures
    (``inputs``: their [w, h]) and its words."""
    from django.conf import settings
    tariff = settings.OPENAI_IMAGE_PRICES['gpt-image-2']
    w, h = (int(v) for v in str(size).split('x'))
    output = OUTPUT_TOKENS_PER_MP[quality] * w * h / 1e6 + PARTIAL_TOKENS
    pictures = sum(INPUT_TOKENS_PER_MP * iw * ih / 1e6 for iw, ih in inputs)
    return (output * tariff['image_output'] + pictures * tariff['image_input'] +
            len(words) / 3 * tariff['text_input']) / 1e6


def edit_hold(size, quality='high', inputs=None, words=None):
    """The hold one face edit reserves: its measured cost with the margin. Before its pictures and words are known,
    three pictures of its canvas's size (its sheet, its reference, a previous drawing) and 4,000 characters."""
    w, h = (int(v) for v in str(size).split('x'))
    if inputs is None:
        inputs = [(w, h)] * 3
    if words is None:
        words = 'x' * 4000
    return round(HOLD_MARGIN * edit_cost(size, quality, inputs, words), 4)


def _up16(value):
    return int(math.ceil(value / 16.0) * 16)


def panel_canvas(W, H):
    """The canvas a W × H mm frame (its bleed included) is drawn on at 300 PPI or more: both sides multiples of 16, the
    aspect within 1:3–3:1 (white added), within gpt-image-2's pixel range. Returns (px/mm, (cw, ch), (fw, fh))."""
    k = K
    for _ in range(60):
        fw, fh = int(math.ceil(W * k)), int(math.ceil(H * k))
        cw, ch = fw + 2 * PANEL_MARGIN_PX, fh + 2 * PANEL_MARGIN_PX
        cw, ch = max(cw, int(math.ceil(ch / 3))), max(ch, int(math.ceil(cw / 3)))
        cw, ch = _up16(cw), _up16(ch)
        if cw * ch >= PANEL_MIN_PX:
            break
        k *= 1.05
    if cw * ch > PANEL_MAX_PX:
        raise ValueError('A %.1f × %.1f mm face does not fit one 300 PPI edit (%d × %d px).' % (W, H, cw, ch))
    return k, (cw, ch), (fw, fh)


def panel_canvas_size(key, brief, geometry):
    """The canvas a stand face's panel drawing will use (panel_canvas), before its sheet is drawn: for the hold."""
    face = face_geometry(key, brief, die_of(geometry))
    _k, (cw, ch), _frame = panel_canvas(face['w_mm'] + 2 * face['bleed_mm'], face['h_mm'] + 2 * face['bleed_mm'])
    return '%dx%d' % (cw, ch)


def board_fits(key, brief, geometry, source):
    """Whether a board drawing (``source``, a panel record) is fine enough to tile this face at its panel resolution:
    board_face never upscales, so a face drawn at more pixels per mm than its source is drawn paid instead."""
    face = face_geometry(key, brief, die_of(geometry))
    k, _size, _frame = panel_canvas(face['w_mm'] + 2 * face['bleed_mm'], face['h_mm'] + 2 * face['bleed_mm'])
    return k <= source['template']['px_per_mm'] * (1 + 1e-6)


def is_panel_size(size):
    """A canvas panel_canvas can make: multiples of 16, aspect 1:3–3:1, inside gpt-image-2's pixel range."""
    try:
        w, h = (int(v) for v in str(size).split('x'))
    except ValueError:
        return False
    return w % 16 == 0 and h % 16 == 0 and 1 / 3 <= w / h <= 3 and PANEL_MIN_PX <= w * h <= PANEL_MAX_PX


def panel_sheet(key, face, folder):
    """The sheet a stand face is drawn on at 300 PPI: white, the face's outline (its bleed included) TRANSPARENT at its
    true size, nothing else on it (the same picture is the mask). Returns its record, as template()'s."""
    folder.mkdir(parents=True, exist_ok=True)
    W, H = face['w_mm'] + 2 * face['bleed_mm'], face['h_mm'] + 2 * face['bleed_mm']
    k, (SW, SH), (fw, fh) = panel_canvas(W, H)
    fx, fy = (SW - fw) // 2, (SH - fh) // 2
    img = Image.new('RGBA', (SW, SH), (255, 255, 255, 255))
    hole = Image.new('L', (SW, SH), 0)
    printed = face['outline'].buffer(face['bleed_mm'], join_style=2) if face['bleed_mm'] else face['outline']
    for ring in _rings(printed):
        ImageDraw.Draw(hole).polygon([(fx + x * k, fy + y * k) for x, y in ring], fill=255)
    img.paste((0, 0, 0, 0), mask=hole)
    img.save(folder / 'template.png')
    return {'size': '%dx%d' % (SW, SH), 'frame_px': [fx, fy, fx + fw, fy + fh], 'px_per_mm': round(k, 6),
            'frame_mm': [W, H], 'template': str(folder / 'template.png'), 'native_ppi': round(k * 25.4, 1),
            'template_sha256': sha(folder / 'template.png'), 'rectangle': abs(printed.area - printed.envelope.area) < 1e-6,
            'hold_usd': edit_hold('%dx%d' % (SW, SH))}


#: the check's revision: a drawing checked under an older one is measured again ($0, round_files_gate.system_repairs)
CHECK_REVISION = 'printed-pixels/2026-10-29'
#: a grid cell is compared only where at least this share of it is measured (printed, and not the picture's lettering)
CELL_SHARE = 0.5
#: the drawings upright on their own outline: a panel (one paid edit), a plain board face ($0) or a face cut from a wrap
UPRIGHT_SOURCES = ('panel', 'board', 'wrap', 'plan')


def _region(mask, size):
    """A boolean mask brought to ``size`` (w, h) by nearest pixels."""
    return np.asarray(Image.fromarray(np.asarray(mask, np.uint8) * 255).resize(size, Image.NEAREST)) > 0


def printed_region(template):
    """A face's printed pixels on its frame: its sheet's transparent shape (its outline with its bleed), cut at the
    frame — never the protected white around it."""
    x0, y0, x1, y1 = template['frame_px']
    with Image.open(template['template']) as image:
        return np.asarray(image.convert('RGBA'))[y0:y1, x0:x1, 3] == 0


def lettering_region(inspection, panel, size):
    """The picked picture's lettering on its view of a face — the reading's text and mark boxes (and any ornament
    lettering boxes) on that panel — at ``size`` (w, h: the frame's pixels); None when the reading boxes none."""
    if not panel or panel not in inspection['panels'] or 'crop_px' not in inspection['panels'][panel]:
        return None
    info = inspection['panels'][panel]
    boxes = [row['box_px'] for name in ('text', 'marks', 'ornament_lettering') if name in info
             for row in info[name] if isinstance(row, dict) and 'box_px' in row]
    if not boxes:
        return None
    cx0, cy0, cx1, cy1 = info['crop_px']
    w, h = size
    out = np.zeros((h, w), bool)
    for x0, y0, x1, y1 in boxes:
        u0, u1 = int(np.floor((x0 - cx0) * w / (cx1 - cx0))), int(np.ceil((x1 - cx0) * w / (cx1 - cx0)))
        v0, v1 = int(np.floor((y0 - cy0) * h / (cy1 - cy0))), int(np.ceil((y1 - cy0) * h / (cy1 - cy0)))
        out[max(v0, 0):min(v1, h), max(u0, 0):min(u1, w)] = True
    return out


def against_painting(face_path, crop, *, printed=None, leave_out=None, lettering='not applicable'):
    """A drawn face against its reference (its crop of the whole-die painting, or what it was drawn from): the face
    brought down to the reference's pixels, a 16 × 16 grid of mean colours over the face's PRINTED pixels only (its
    outline with its bleed: ``printed``, never the protected white around it), less ``leave_out`` (the picked
    picture's lettering, which the face leaves to live type); a cell less than CELL_SHARE measured is left out;
    CIEDE2000 cell by cell. Over the bar it is flagged for the owner, never passed or redrawn."""
    crop = np.asarray(crop)[..., :3].astype(np.float64)
    h, w = crop.shape[:2]
    with Image.open(face_path) as image:
        drawn = np.asarray(image.convert('RGB').resize((w, h), Image.LANCZOS)).astype(np.float64)
    keep = np.ones((h, w), bool)
    if printed is not None:
        keep &= _region(printed, (w, h))
    if leave_out is not None:
        keep &= ~_region(leave_out, (w, h))
    a, b = [], []
    for r in np.array_split(np.arange(h), 16):
        for c in np.array_split(np.arange(w), 16):
            if not len(r) or not len(c):
                continue
            cell = keep[r[0]:r[-1] + 1, c[0]:c[-1] + 1]
            if cell.mean() < CELL_SHARE:
                continue
            a.append(drawn[r[0]:r[-1] + 1, c[0]:c[-1] + 1][cell].mean(axis=0))
            b.append(crop[r[0]:r[-1] + 1, c[0]:c[-1] + 1][cell].mean(axis=0))
    if not a:
        raise ValueError('No part of the face is left to compare with its reference.')
    d = delta_e00(srgb_to_lab(np.array(a)), srgb_to_lab(np.array(b))).ravel()
    median, p90 = float(np.median(d)), float(np.percentile(d, 90))
    return {'schema': 'panel_against_painting/2', 'grid': [16, 16], 'cells': int(d.size), 'median': round(median, 2),
            'p90': round(p90, 2), 'max': round(float(d.max()), 2), 'bar': dict(AGAINST_BAR),
            'flagged': median > AGAINST_BAR['median'] or p90 > AGAINST_BAR['p90'],
            'measured_on': 'the face\'s printed pixels' if printed is not None else 'the whole frame',
            'lettering': lettering, 'revision': CHECK_REVISION,
            'rule': 'over the bar the face is flagged for the owner; it is never silently passed or redrawn'}


def reference_check(record, inspection):
    """A drawing's check against the reference it was given, measured on its printed pixels; where that reference is
    the picked picture's view, the reading's lettering boxes on the panel are left out (said either way)."""
    with Image.open(record['reference']['path']) as image:
        reference = np.asarray(image.convert('RGB'))
    leave_out, lettering = None, 'not applicable'
    if record['reference'].get('source') == 'picked picture':
        h, w = reference.shape[:2]
        leave_out = lettering_region(inspection, FACES[record['key']]['panel'], (w, h))
        lettering = ('the picture\'s lettering left out (the reading\'s boxes)' if leave_out is not None else
                     'the comparison includes the picture\'s lettering: the reading boxes none on this panel')
    return against_painting(record['face'], reference, printed=printed_region(record['template']),
                            leave_out=leave_out, lettering=lettering)


def _largest_rectangle(mask):
    """The largest axis-aligned rectangle of True in ``mask``: (x0, y0, x1, y1)."""
    h, w = mask.shape
    heights, best = np.zeros(w, int), (0, 0, 0, 0, 0)
    for y in range(h):
        heights = np.where(mask[y], heights + 1, 0)
        stack = []
        for x, height in enumerate(np.append(heights, 0)):      # a zero bar at the end empties the stack
            start = x
            while stack and stack[-1][1] >= height:
                start, top = stack.pop()
                if top * (x - start) > best[0]:
                    best = (top * (x - start), start, y - top + 1, x, y + 1)
            stack.append((start, height))
    return best[1:]


def board_face(ctx, key, n, source, geometry, *, why):
    """Drawing ``n`` of a face the owner's policy calls plain, at $0 (the owner's goal of 2026-10-29): when its own
    drawings stay not plain after their one system redraw, the stand's plainest passing plain drawing (``source``, a
    record) gives the board — the largest rectangle of its printed pixels, its 3 mm bleed inset, at its own pixels —
    mirror-tiled over this face's frame at 300 PPI: never upscaled. Checked like any drawing; recorded as made."""
    folder = drawing_folder(ctx.root, key, n)
    record_path = folder / 'record.json'
    if record_path.exists():
        return _checked(record_path, 'face')
    face = face_geometry(key, ctx.brief, die_of(geometry))
    sheet = panel_sheet(key, face, folder)
    scale = sheet['px_per_mm'] / source['template']['px_per_mm']
    if scale > 1 + 1e-6:
        raise ValueError('The board\'s drawing is at a lower resolution than this face: it is never upscaled.')
    inset = int(math.ceil(STAND_BLEED_MM * source['template']['px_per_mm']))
    small = printed_region(source['template'])[::4, ::4]
    x0, y0, x1, y1 = (4 * int(v) for v in _largest_rectangle(small))
    x0, y0, x1, y1 = x0 + inset, y0 + inset, x1 - inset, y1 - inset
    if x1 - x0 < 32 or y1 - y0 < 32:
        raise ValueError('The board\'s drawing has too little plain board to tile.')
    with Image.open(source['face']) as image:
        block = image.convert('RGB').crop((x0, y0, x1, y1))
    if scale < 1 - 1e-6:
        block = block.resize((max(1, round(block.width * scale)), max(1, round(block.height * scale))), Image.LANCZOS)
    fx0, fy0, fx1, fy1 = sheet['frame_px']
    fw, fh = fx1 - fx0, fy1 - fy0
    pixels = np.asarray(block)
    tiled = np.pad(pixels, ((0, max(0, fh - pixels.shape[0])), (0, max(0, fw - pixels.shape[1])), (0, 0)),
                   mode='symmetric')[:fh, :fw]
    printed = printed_region(sheet)
    Image.fromarray(np.where(printed[..., None], tiled, 255).astype(np.uint8), 'RGB').save(folder / 'face.png')
    Image.fromarray(np.ascontiguousarray(tiled), 'RGB').save(folder / 'reference.png')
    record = {'frame_px': sheet['frame_px'], 'face': str(folder / 'face.png'), 'face_sha256': sha(folder / 'face.png'),
              'key': key, 'n': n, 'label': FACES[key]['label'], 'source': 'board', 'template': sheet,
              'reference': {'path': str(folder / 'reference.png'), 'sha256': sha(folder / 'reference.png'),
                            'source': 'board', 'detail': 'the board of %s drawing %d, tiled' % (source['key'], source['n'])},
              'reference_source': 'board', 'plain': True, 'native_ppi': sheet['native_ppi'], 'cost_usd': 0.0,
              'board_face': {'from': '%s/%d' % (source['key'], source['n']), 'from_face_sha256': source['face_sha256'],
                             'block_px': [x0, y0, x1, y1], 'scale': round(scale, 6), 'why': why,
                             'rule': 'its board mirror-tiled at its own pixels (never upscaled); $0'},
              'rule': 'a plain face made at $0 from the stand\'s plainest passing plain drawing; checked like any drawing'}
    record['plain_check'] = plain_check(folder / 'face.png', sheet)
    record['against_painting'] = against_painting(folder / 'face.png', tiled, printed=printed)
    flow.write_json(record_path, record)
    return record


def unpainted(rgb):
    """The template's own unpainted colours: near-neutral (the channels within 12 of each other) and light (their mean
    at least 170): its white and its light grey."""
    rgb = np.asarray(rgb).astype(np.int16)
    return (rgb.max(axis=-1) - rgb.min(axis=-1) <= 12) & (rgb.mean(axis=-1) >= 170)


def crop_reliability(painting, key, geometry):
    """Whether a stand face's crop of the settled painting may be what its panel follows and is checked against: the
    face's die-match coverage (the painting's own proof) and the share of the face's printed pixels, its bleed
    included, that the painting left in the template's unpainted colours."""
    from apps.dielines.exporters import counter_display_files as cdf
    if 'proof' not in painting:
        raise ValueError('The flat painting has no die-match proof, so no face can be cut or drawn from it.')
    die = die_of(geometry)
    name = FACES[key]['die'][1]
    masks = cdf.flat_masks(die, cdf.flat_frame(die))
    region = masks['owner'] == masks['names'].index(name) + 1
    with Image.open(painting['flat']) as image:
        flat = np.asarray(image.convert('RGB'))
    share = float(unpainted(flat[region]).mean())
    coverage = float(painting['proof']['coverage'][name])
    return {'schema': 'painting_crop_reliability/1', 'face': name, 'coverage': round(coverage, 4),
            'unpainted_share': round(share, 4), 'thresholds': dict(RELIABLE_CROP),
            'registration_iou': painting['proof']['registration']['iou_at_best'],
            'reliable': coverage >= RELIABLE_CROP['coverage'] and share <= RELIABLE_CROP['unpainted_share']}


def plain_check(face_path, template):
    """A face the owner's policy names plain: the share of its printed pixels (its sheet's transparent shape, cut at
    the frame) further than PLAIN['delta_e'] from the face's own median colour; plain at most PLAIN['share']."""
    with Image.open(face_path) as image:
        face = image.convert('RGB')
    x0, y0, x1, y1 = template['frame_px']
    with Image.open(template['template']) as image:
        hole = np.asarray(image.convert('RGBA'))[y0:y1, x0:x1, 3] == 0
    scale = min(1.0, 400 / max(face.size))
    size = (max(1, round(face.width * scale)), max(1, round(face.height * scale)))
    rgb = np.asarray(face.resize(size, Image.LANCZOS)).astype(np.float64)
    mask = np.asarray(Image.fromarray(hole.astype(np.uint8) * 255).resize(size, Image.NEAREST)) > 0
    lab = srgb_to_lab(rgb[mask])
    median = np.broadcast_to(np.median(lab, axis=0), lab.shape)
    share = float((delta_e00(lab, median) > PLAIN['delta_e']).mean())
    return {'schema': 'panel_plain_check/1', 'share_over': round(share, 4), 'threshold': dict(PLAIN),
            'plain': share <= PLAIN['share']}


#: what image 2 of a panel is, by its source (panel_reference)
REFERENCE_WORDS = {
    'painting': ('Image 2 is this same face as our painting of the whole flat die shows it, at a low resolution: the '
                 'design to follow EXACTLY — the same layout, the same colours, the same motifs, each in its own place '
                 'and at its own size. Draw it again at full print resolution: sharper lines, finer texture and finish, '
                 'nothing added, nothing moved, nothing left out.'),
    'picked picture': ('Image 2 is the owner\'s picked picture\'s own view of this face: a photograph of the stand, '
                       'seen at an angle and at a low resolution. It is the design to follow — its ground, colours, '
                       'motifs and their places — drawn flat, front-on and upright, filling the shape, at full print '
                       'resolution.'),
    'board swatch': ('Image 2 is a swatch of this stand\'s own board, as drawn on another of its faces. Paint this face '
                     'PLAIN in that same board, edge to edge: the same colour, texture and finish, and nothing else — '
                     'no motif, no band, no gauge, no dial, no border, no frame, no edge line.'),
}
REFERENCE_WORDS['pattern'] = (
    'Image 2 is the stand\'s back panel as already drawn, at this wall\'s scale and cut to its width: the side walls '
    'share its pattern. Continue its bands LEVEL across this wall when the stand is folded — the same bands in the same '
    'order, at the same heights above the floor, running across the wall from the corner it shares with the back panel, '
    'never up and down — and fill this wall\'s whole shape with them, edge to edge.')
#: the walls that share the back panel's pattern (the owner, 2026-10-29: "both side walls (bands level when folded,
#: not sideways)"); a wall drawn after the back follows the back's drawing
WALL_PATTERN = {'side': 'back', 'left': 'back'}


def pattern_reference(pattern, key, size, px_per_mm):
    """A wall's reference from the back panel's drawing (``pattern``, its record): at the wall's own scale, its floor
    edge level with the wall's, cut to the wall's width from the corner the two share and mirrored there, so that the
    back's bands run straight on into the wall's."""
    with Image.open(pattern['face']) as image:
        art = image.convert('RGB')
    scale = px_per_mm / pattern['template']['px_per_mm']
    if abs(scale - 1) > 1e-6:
        art = art.resize((max(1, round(art.width * scale)), max(1, round(art.height * scale))), Image.LANCZOS)
    pixels = np.asarray(art)
    W, H = size
    pixels = np.pad(pixels, ((max(0, H - pixels.shape[0]), 0), (0, max(0, W - pixels.shape[1])), (0, 0)),
                    mode='symmetric')
    pixels = pixels[pixels.shape[0] - H:]                                  # the floor edges level
    # the right wall meets the back's left edge, the left wall its right edge (seen from outside, folded)
    window = pixels[:, pixels.shape[1] - W:]
    if key == 'side':
        window = pixels[:, :W]
    return Image.fromarray(np.ascontiguousarray(window[:, ::-1]))


PLAIN_WORDS = ('This face is plain board in the owner\'s design: no motif, no band, no gauge, no dial, no border, no '
               'frame, no edge line.')


def panel_reference(ctx, key, painting, geometry, size, folder, *, plain=False, swatch=None, pattern=None,
                    px_per_mm=None):
    """Image 2 of a stand face's panel and what it is (the owner's goal of 2026-10-29): the face's crop of the settled
    painting where the painting kept that face (crop_reliability); else the picked picture's own view of the face
    where the reading has one; else, for a face the owner calls plain, a swatch of the stand's board (the best plain
    face drawn so far, or the painting's ground colour). With none of them the face is refused in words: an
    unreliable crop is never what a panel follows. Writes folder/reference.png at the frame's size."""
    reliability = crop_reliability(painting, key, geometry)
    panel = FACES[key]['panel']
    inspection = json.loads((ctx.root / 'inspection.json').read_text())
    if pattern is not None:
        source, detail = 'pattern', 'the back panel\'s drawing %d, cut to this wall' % pattern['n']
        picture = pattern_reference(pattern, key, size, px_per_mm)
    elif reliability['reliable']:
        source, detail = 'painting', 'its crop of the whole-die painting'
        picture = Image.fromarray(np.ascontiguousarray(painted_face(painting, key, geometry)[0]))
    elif panel and panel in inspection['panels'] and 'crop_px' in inspection['panels'][panel]:
        source, detail = 'picked picture', 'the reading\'s %s crop of the picked picture' % panel
        with Image.open(ctx.root / 'source.png') as image:
            picture = image.convert('RGB').crop(tuple(inspection['panels'][panel]['crop_px']))
    elif plain and swatch:
        source, detail = 'board swatch', 'the stand\'s best plain face drawn so far (%s)' % Path(swatch).parent.parent.parent.name
        with Image.open(swatch) as image:
            picture = image.convert('RGB')
    elif plain:
        source, detail = 'board swatch', 'the painting\'s own ground colour'
        with Image.open(painting['flat']) as image:
            flat = np.asarray(image.convert('RGB'))
        from apps.dielines.exporters import counter_display_files as cdf
        die = die_of(geometry)
        painted = cdf.flat_masks(die, cdf.flat_frame(die))['paint'] & ~unpainted(flat)
        picture = Image.new('RGB', (64, 64), tuple(int(v) for v in np.median(flat[painted], axis=0)))
    else:
        raise ValueError('The %s\'s crop of the painting is not reliable (coverage %.2f, %.0f%% left unpainted) and '
                         'there is no other view of it to draw from: press Redraw with a note, or paint the die again.'
                         % (FACES[key]['label'].lower(), reliability['coverage'], 100 * reliability['unpainted_share']))
    picture.resize(size, Image.LANCZOS).save(folder / 'reference.png')
    return {'source': source, 'detail': detail, 'reliability': reliability, 'path': str(folder / 'reference.png'),
            'sha256': sha(folder / 'reference.png')}


def panel_prompt(key, face, *, note='', previous=False, source='painting', plain=False, keep='', rules=''):
    W, H = face['w_mm'] + 2 * face['bleed_mm'], face['h_mm'] + 2 * face['bleed_mm']
    words = ['Image 1 is the sheet to draw on: a white ground with one TRANSPARENT shape, the only place to draw. It is '
             'the true flat shape of one printed face of a folding cardboard counter stand, the %s (%.1f × %.1f mm with '
             'its 3 mm bleed). Fill it EXACTLY, edge to edge and into the bleed, with flat print artwork seen front-on: '
             'no perspective, no 3D, no shadow, no product, no mockup, no guide lines. Keep the white around it white.'
             % (FACES[key]['label'].lower(), W, H),
             REFIT_WORDS if source == 'previous drawing' else REFERENCE_WORDS[source]]
    if plain and source != 'board swatch':
        words.append(PLAIN_WORDS)
    if rules:
        words.append(rules)
    words.append(UPRIGHT_WORDS)
    if keep:
        words.append('The owner\'s words for the whole stand (where they say image 2 they meant his picked picture): '
                     '"%s"' % keep)
    if previous:
        words.append('Image 3 is your previous drawing of this face. The owner asks: "%s". Draw the face again with '
                     'that change, keeping what was right.' % note)
    elif note:
        words.append('The owner asks: "%s".' % note)
    words.append(NO_WORDS)
    if note:
        words.append(NOTE_LAST % note)
    return '\n\n'.join(words)


REFIT_WORDS = ('Image 2 is this same face as it was drawn for its earlier outline, before the die was cut to the owner\'s '
               'picked picture: the design to keep — the same colours, motifs, bands, rims and ornaments in the same '
               'order. The face\'s outline has changed to the TRANSPARENT shape of image 1: redraw the same design so it '
               'fills that whole shape exactly, edge to edge, its outermost ring and rim following the cut edge, with no '
               'empty ground above it or beside it.')


def refit_reference(previous_face, size, folder):
    """A face's previous drawing as the reference of its redraw on a changed outline: brought to the new frame."""
    with Image.open(previous_face) as image:
        image.convert('RGB').resize(size, Image.LANCZOS).save(folder / 'reference.png')
    return {'path': str(folder / 'reference.png'), 'sha256': sha(folder / 'reference.png'), 'source': 'previous drawing',
            'detail': 'its drawing for the earlier outline', 'reliability': {'reliable': True, 'coverage': 1.0,
                                                                              'unpainted_share': 0.0}}


def panel_face(ctx, key, n, painting, geometry, *, note='', previous=None, plain=False, swatch=None, keep='',
               system_redraw=None, refit=None, rules='', pattern=None, quality='high'):
    """Drawing ``n`` of a stand face at 300 PPI on its own outline: one paid edit (image 1 its panel sheet, image 2 the
    whole-die painting's crop of this face, image 3 the previous drawing for a Redraw with the owner's note), cut at the
    frame as drawn (nothing erased) and checked against the painting's crop (against_painting). Restartable: the call's
    saved reply is never bought twice."""
    folder = drawing_folder(ctx.root, key, n)
    record_path = folder / 'record.json'
    if record_path.exists():
        return _checked(record_path, 'face')
    face = face_geometry(key, ctx.brief, die_of(geometry))
    sheet = panel_sheet(key, face, folder)
    x0, y0, x1, y1 = sheet['frame_px']
    if refit is not None:
        # the outline changed under an earlier drawing (the shape check, 2026-10-29): that drawing is the design,
        # refitted to the new outline; the painting was made on the old die and is not read
        upright, frame_mm, box = None, None, None
        given = refit_reference(refit, (x1 - x0, y1 - y0), folder)
    else:
        upright, frame_mm, box = painted_face(painting, key, geometry)
        given = panel_reference(ctx, key, painting, geometry, (x1 - x0, y1 - y0), folder, plain=plain, swatch=swatch,
                                pattern=pattern, px_per_mm=sheet['px_per_mm'])
    sent, withheld = owner_note(note)
    redraw = bool(previous) and bool(sent) and not withheld
    words = panel_prompt(key, face, note='' if withheld else sent, previous=redraw, source=given['source'], plain=plain,
                         keep=keep, rules=rules)
    call = ctx.face_edit('face/%s/%d' % (key, n), words, folder / 'call', template=sheet['template'],
                         references=[folder / 'reference.png'] + ([previous] if redraw else []), size=sheet['size'],
                         quality=quality)
    drawn = cut_face(folder / 'call' / 'raw.png', sheet, folder)
    record = dict(drawn, key=key, n=n, label=FACES[key]['label'], source='panel', template=sheet,
                  reference={'path': given['path'], 'sha256': given['sha256'], 'source': given['source'],
                             'detail': given['detail'], 'painting_box_px': box,
                             'painting_px_per_mm': round(upright.shape[1] / frame_mm[0], 4) if upright is not None else None},
                  reference_source=given['source'], reliability=given['reliability'], plain=plain,
                  plain_check=plain_check(folder / 'face.png', sheet) if plain else None,
                  system_redraw=system_redraw,
                  painting=painting['flat'], painting_sha256=painting['flat_sha256'], painting_n=painting['n'],
                  native_ppi=sheet['native_ppi'],
                  prompt=words, note=sent, note_withheld=withheld, previous=previous, cost_usd=call.get('cost_usd'),
                  reservation_id=call['reservation_id'],
                  rule='drawn at 300 PPI on its own outline from its reference (reference_source), checked against that '
                       'same reference on its printed pixels; cut at the frame as drawn')
    record['against_painting'] = reference_check(record, json.loads((ctx.root / 'inspection.json').read_text()))
    flow.write_json(record_path, record)
    return record


def trim_view(upright, frame_mm):
    """A stand face's upright picture at its trim (the bleed cut off), for the drawings."""
    b, image = STAND_BLEED_MM, Image.fromarray(upright)
    k = image.width / frame_mm[0]
    return image.crop((round(b * k), round(b * k), image.width - round(b * k), image.height - round(b * k)))


# --- composed on the die, and written ---------------------------------------------------------------------------------

def _to_sheet(poly, quarters, w, h, bleed):
    """The mark turn: the upright frame (origin its top-left, the bleed included) onto the sheet."""
    x0, y0, _x1, _y1 = poly.bounds
    W, H = w + 2 * bleed, h + 2 * bleed

    def to_sheet(x, y):
        for i in range(quarters % 4):
            x, y = (H if i % 2 == 0 else W) - y, x
        return x0 - bleed + x, y0 - bleed + y
    return to_sheet


def _box_to_sheet(box, to_sheet):
    a, b = to_sheet(box[0], box[1]), to_sheet(box[2], box[3])
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]


def upright_marks(key, face, inspection, brief, drawn):
    """A face's live words, logos and ornament band in its upright frame (mm; the bleed included, origin top-left):
    the one placement both the owner's preview and the written files use."""
    guides = marks(key, inspection, brief, face, drawn)
    out = {'type': list(guides['type']), 'logos': list(guides['logos']), 'ornament': [],
           'placement': guides.get('placement')}
    for index, zone in enumerate(guides['zones']):
        runs, record = layout_runs(key, index, zone, trim_box(face), **({} if stand_face(key) else {'foil': True}))
        out['type'].extend(runs)
        out['ornament'].append(dict(record, face=key, zone=index))
    return out


def upright_face(key, brief, die):
    """The frame marks() and the preview use: a stand face as the composer sees it (no outline, its 3 mm safe line),
    a product face as drawn."""
    face = face_geometry(key, brief, die)
    return dict(face, outline=None, safe_mm=STAND_SAFE_MM) if stand_face(key) else face


def face_spec(key, drawn, inspection, brief, die, identifier):
    """One face alone, written as the files will write it (its drawing, live type and logo in the upright frame), for
    the owner's preview and the eye; its trim is the cut."""
    face = upright_face(key, brief, die)
    b = face['bleed_mm']
    W, H = face['w_mm'] + 2 * b, face['h_mm'] + 2 * b
    placed_marks = upright_marks(key, face, inspection, brief, drawn)
    trim = trim_box(face)
    if drawn.get('source') == 'plan':
        return plan_spec(key, json.loads(Path(drawn['plan']).read_text()), identifier=identifier), trim
    return {'id': identifier, 'title': FACES[key]['label'] + ' · preview', 'size_mm': [W, H],
            'artwork': [{'name': key + ' painting', 'path': drawn['face'], 'box_mm': [0, 0, W, H]}], 'foil_svg': [],
            'type_runs': placed_marks['type'], 'logos': placed_marks['logos'],
            'die': {'cut': [{'points_mm': [[trim[0], trim[1]], [trim[2], trim[1]], [trim[2], trim[3]],
                                           [trim[0], trim[3]]], 'closed': True}]}, 'guides': []}, trim


def printed_rings(die):
    """The rings (mm on the die's sheet) of the printed faces and their bleed: nothing that prints lies outside them."""
    from apps.dielines.geometry import counter_display as cd
    piece = cd.piece_of(die)
    rings = [[[round(x, 3), round(y, 3)] for x, y in ring] for ring in _rings(cd.bleed_area(piece))]
    for _name, polygon in ground_only(die):
        rings += [[[round(x, 3), round(y, 3)] for x, y in ring] for ring in _rings(polygon)]
    return rings


def inside_board(die, ground_hex, default):
    """What the shopper sees behind the products: a template's rolled inner wall carries the design's flat ground on its print side; a die
    with no such wall shows the board's unprinted side."""
    if ground_hex and getattr(die, 'ground_faces', None):
        return tuple(int(ground_hex[i:i + 2], 16) for i in (1, 3, 5))
    return default


def ground_only(die):
    """A template's visible board that carries only the design's flat ground: its rims, its inner walls, its stair's treads and
    risers, whose print side faces the shopper. (name, polygon) each, the polygon grown 1 mm so the colour reaches its folds."""
    wanted = getattr(die, 'ground_faces', None) or []
    out = []
    for part in die.parts:
        for name, polygon, _printed in part.faces:
            if (part.name, name) in wanted:
                out.append(('%s / %s' % (part.name, name), polygon.buffer(1.0, join_style=2)))
    return out


def stand_frame(painted):
    """The composer's frame of the die: the painting's frame (counter_display_files.flat_frame) at 300 PPI."""
    x0, y0, x1, y1 = painted['frame_mm']
    W, H = int(math.ceil((x1 - x0) * K)) + 2, int(math.ceil((y1 - y0) * K)) + 2
    return dict(painted, size='%dx%d' % (W, H), canvas_px=[W, H], px_per_mm=K, offset_px=[1.0, 1.0],
                dpi_at_1to1=round(K * 25.4, 1))


def stand_raster(drawn, die):
    """The stand's one flat raster on the die at 300 PPI: each printed face's pixels from its drawing or the painting it
    was cut from, on its own pixels (a Redraw repaints only its own face; the faces never pass through a turn and back).
    Returns (the RGBA raster, its frame, its masks, each face's own PPI)."""
    from apps.dielines.exporters import counter_display_files as cdf
    painted = cdf.flat_frame(die)
    frame = stand_frame(painted)
    masks = cdf.flat_masks(die, frame)
    keys = [key for key in FACES if stand_face(key)]
    if sorted(masks['names']) != sorted(FACES[key]['die'][1] for key in keys):
        raise ValueError('Every printed face of the die must be a face of the design.')
    if any(key not in drawn or ('painting_art' not in drawn[key] and drawn[key].get('source') not in UPRIGHT_SOURCES)
           for key in keys):
        raise ValueError('The stand is made from its flat design; every stand face must be cut from it or drawn on it.')
    full = np.zeros(masks['owner'].shape + (4,), np.uint8)            # the painting, whole on its printed faces
    b = STAND_BLEED_MM
    native = {}
    for key in keys:
        part_face, quarters = FACES[key]['die'], FACES[key]['quarters']
        _part, poly = die_face(die, part_face)
        x0, y0, x1, y1 = poly.bounds
        (u0, v0), (u1, v1) = cdf.flat_px(frame, x0 - b, y0 - b), cdf.flat_px(frame, x1 + b, y1 + b)
        box = [int(round(u0)), int(round(v0)), int(round(u1)), int(round(v1))]
        if drawn[key].get('source') in UPRIGHT_SOURCES:
            # drawn upright at 300 PPI on its own outline: turned onto the die by whole quarter turns, scaled once
            if sha(drawn[key]['face']) != drawn[key]['face_sha256']:
                raise ValueError('A drawn face changed after it was cut: ' + key)
            with Image.open(drawn[key]['face']) as image:
                upright = np.asarray(image.convert('RGB'))
            art = Image.fromarray(turn(upright, quarters)).resize((box[2] - box[0], box[3] - box[1]), Image.LANCZOS)
            native[key] = {'source': drawn[key]['source'], 'ppi': drawn[key]['native_ppi']}
        else:
            # cut from the whole-die painting: its pixels, brought up to the composer's scale (their own PPI recorded)
            if sha(drawn[key]['painting_art']) != drawn[key]['painting_art_sha256']:
                raise ValueError('A flat painting changed after its face was cut: ' + key)
            (p0, q0), (p1, q1) = cdf.flat_px(painted, x0 - b, y0 - b), cdf.flat_px(painted, x1 + b, y1 + b)
            with Image.open(drawn[key]['painting_art']) as image:
                art = image.convert('RGBA').crop(tuple(int(round(v)) for v in (p0, q0, p1, q1))).resize((box[2] - box[0], box[3] - box[1]),
                                                                          Image.LANCZOS).convert('RGB')
            native[key] = {'source': 'painting', 'ppi': painted['dpi_at_1to1']}
        layer = np.zeros_like(full)
        rows, cols = max(0, min(box[3], layer.shape[0]) - box[1]), max(0, min(box[2], layer.shape[1]) - box[0])
        layer[box[1]:box[3], box[0]:box[2], :3] = np.asarray(art)[:rows, :cols]
        layer[..., 3] = 255
        mine = masks['owner'] == masks['names'].index(part_face[1]) + 1
        full[mine] = layer[mine]
    return full, frame, masks, native


def compose_stand(drawn, inspection, brief, geometry, folder):
    """The stand's one flat raster (stand_raster) written at 1:1, with each face's words, logos and ornament band turned
    onto the sheet with it. Returns the writer's spec and each face's frame."""
    die = die_of(geometry)
    folder.mkdir(parents=True, exist_ok=True)
    spec = {'id': 'stand', 'title': 'Counter stand · provisional measurements', 'size_mm': geometry['sheet_mm'],
            'artwork': [], 'foil_svg': [], 'type_runs': [], 'logos': [], 'die': geometry['die'],
            'guides': geometry['guides']['safe'] + geometry['guides']['bleed']}
    full, frame, _masks, native = stand_raster(drawn, die)
    keys = [key for key in FACES if stand_face(key)]
    b = STAND_BLEED_MM
    ys, xs = np.nonzero(full[..., 3])
    u0, v0, u1, v1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    k, (ox, oy), (fx, fy) = frame['px_per_mm'], frame['offset_px'], frame['frame_mm'][:2]
    box_mm = [fx + (u0 - ox) / k, fy + (v0 - oy) / k, fx + (u1 - ox) / k, fy + (v1 - oy) / k]
    path = folder / 'stand--flat.png'
    Image.fromarray(full[v0:v1, u0:u1], 'RGBA').save(path, dpi=(frame['dpi_at_1to1'],) * 2)
    if all(drawn[key].get('source') == 'plan' for key in keys):
        pieces = stand_pieces(drawn, geometry)
        spec.update(law=True, ground=pieces['ground'], motifs=pieces['motifs'], finishes=pieces['finishes'], panels=pieces['panels'],
                    guides=[], die=dict(geometry['die'], safe=geometry['guides']['safe'], bleed=geometry['guides']['bleed'],
                                        glue=geometry['layers_geometry'].get('glue', [])), own_ground=None)
    else:
        spec['artwork'].append({'name': 'stand-flat', 'path': str(path), 'ppi': frame['dpi_at_1to1'], 'box_mm': box_mm})
    spec['printed_mm'] = printed_rings(die)             # the print check's bound: the printed faces and their bleed
    placements, ornaments = {}, []
    for key in keys:
        part_face, quarters = FACES[key]['die'], FACES[key]['quarters']
        _part, poly = die_face(die, part_face)
        w, h = face_mm_size(poly, quarters)
        face = {'w_mm': w, 'h_mm': h, 'bleed_mm': b}
        x0, y0, x1, y1 = poly.bounds
        placements[' / '.join(part_face)] = {'face': key, 'turn_quarters_cw': quarters,
                                             'frame_mm': [x0 - b, y0 - b, x1 + b, y1 + b],
                                             'size_mm': [round(w, 3), round(h, 3)],
                                             'painting': drawn[key].get('painting_n'),
                                             'native_ppi': native[key]['ppi'], 'source': native[key]['source'],
                                             'composed_ppi': frame['dpi_at_1to1']}
        to_sheet = _to_sheet(poly, quarters, w, h, b)
        upright = dict(face, outline=None, safe_mm=STAND_SAFE_MM)
        guides = upright_marks(key, upright, inspection, brief, drawn[key])
        if guides.get('placement'):
            placements[' / '.join(part_face)]['type_placement'] = guides['placement']
        for row in guides['type']:
            if 'center_mm' in row:
                cx, cy = to_sheet(*row['center_mm'])
                spec['type_runs'].append(dict(row, center_mm=[cx, cy], angle_deg=row['angle_deg'] - 90 * quarters))
                continue
            spec['type_runs'].append(dict(row, box_mm=_box_to_sheet(row['box_mm'], to_sheet),
                                          rotation=(row['rotation'] - 90 * quarters) % 360))
        for row in guides['logos']:
            spec['logos'].append(dict(row, box_mm=_box_to_sheet(row['box_mm'], to_sheet),
                                      rotation=(row['rotation'] - 90 * quarters) % 360))
        ornaments.extend(guides['ornament'])
    if ornaments:
        spec['ornament'] = ornaments
    return spec, placements


CLEAR_DE = (10.0, 20.0)                  # no ink within ΔE00 10 of the painted ground or window, all ink past 20


def clear_painting(drawn):
    """A clear body's painting as it prints (ruled 2026-10-30: "their ground stays unprinted"; "a window left open"): the
    image model paints a clear body in colours, so the file leaves them out: its ground (ground_of) and its window (the
    shape around its largest plain area) carry no ink and only its woven art prints. Written beside the face; returns its
    path."""
    from scipy import ndimage
    path = Path(drawn['face']).with_name('clear.png')
    with Image.open(drawn['face']) as image:
        rgb = np.asarray(image.convert('RGB'))
    lab = srgb_to_lab(rgb.astype(np.float64))
    flat = lab.reshape(-1, 3)
    window = np.zeros(rgb.shape[:2], bool)
    box = plain_area_mm(drawn)
    if box is not None:
        # the window is one shape, its colour joined to its plain area; a fruit of the same colour elsewhere is art
        k = drawn['template']['px_per_mm']
        x0, y0, x1, y1 = (int(round(value * k)) for value in box)
        colour = np.median(lab[y0:y1, x0:x1].reshape(-1, 3), axis=0)
        near = delta_e00(flat, np.broadcast_to(colour, flat.shape)).reshape(rgb.shape[:2]) < CLEAR_DE[1]
        labels, _count = ndimage.label(near)
        window = labels == labels[(y0 + y1) // 2, (x0 + x1) // 2]
    if (~window).mean() < 0.01:
        return drawn['face']                            # one plain colour, nothing to tell apart: it prints as painted
    ground = ground_of(rgb, ~window)[0]
    away = delta_e00(flat, np.broadcast_to(ground, flat.shape)).reshape(rgb.shape[:2])
    alpha = np.clip((away - CLEAR_DE[0]) / (CLEAR_DE[1] - CLEAR_DE[0]), 0, 1)
    alpha[window] = 0
    if not alpha.any():
        return drawn['face']
    Image.fromarray(np.dstack([rgb, np.round(alpha * 255).astype(np.uint8)]), 'RGBA').save(path)
    return str(path)


def product_spec(key, drawn, inspection, brief, die):
    face = face_geometry(key, brief, die)
    w, h = face['w_mm'], face['h_mm']
    guides = upright_marks(key, face, inspection, brief, drawn[key])
    title = {'bottle': 'Bottle front · provisional measurements', 'cap': 'Cap front · gold engraving'}[key]
    if drawn[key].get('source') == 'plan':
        return dict(plan_spec(key, json.loads(Path(drawn[key]['plan']).read_text())), title=title, trim_box_mm=None)
    painting = clear_painting(drawn[key]) if key == 'bottle' and drawn[key].get('source') == 'net' else drawn[key]['face']
    spec = {'id': FACES[key]['object'], 'title': title, 'size_mm': [w, h],
            'artwork': [{'name': key + ' painting', 'path': painting, 'box_mm': [0, 0, w, h]}], 'foil_svg': [],
            'type_runs': guides['type'], 'logos': guides['logos'],
            'die': {'cut': [{'points_mm': [[0, 0], [w, 0], [w, h], [0, h]], 'closed': True}]},
            'guides': [{'points_mm': [[.5, .5], [w - .5, .5], [w - .5, h - .5], [.5, h - .5]], 'closed': True}]}
    if guides['ornament']:
        spec['ornament'] = guides['ornament']
    return spec


def net_sides(drawn):
    """Each product face painted on its net: its right side, back and left side as painted, for the wrap view."""
    return {key: [drawn[key]['net']['sides'][name]['path'] for name in ('right side', 'back', 'left side')]
            for key in ('bottle', 'cap') if key in drawn and drawn[key].get('source') == 'net'}


def specs(drawn, inspection, brief, geometry, folder):
    die = die_of(geometry)
    stand, placements = compose_stand(drawn, inspection, brief, geometry, folder / 'on-die')
    return [product_spec('bottle', drawn, inspection, brief, die), product_spec('cap', drawn, inspection, brief, die),
            stand], placements


def face_views(objects, placements, folder, *, liquid=None):
    """What the eye judges: each face rendered from its written file — the print layers only (artwork, live type, the
    logo), the stand's faces cut to their trim on the sheet and turned back upright — on white."""
    from .round_files_export import render_flat
    folder.mkdir(parents=True, exist_ok=True)
    by_id = {item['id']: item for item in objects}
    views = {}
    for key in FACES:
        path = folder / (key + '.png')
        if stand_face(key):
            where = placements[' / '.join(FACES[key]['die'])]
            raw = folder / (key + '.on-die.png')
            b = STAND_BLEED_MM
            x0, y0, x1, y1 = where['frame_mm']
            render_flat(by_id["stand"]["ai"], raw, dpi=200, clip_mm=[x0 + b + .35, y0 + b + .35, x1 - b - .35, y1 - b - .35])
            with Image.open(raw) as image:
                rgba = np.asarray(image.convert('RGBA'))
            rgba = turn(rgba, (4 - where['turn_quarters_cw']) % 4)
        else:
            with Image.open(by_id[FACES[key]['object']]['png']) as image:
                rgba = np.asarray(image.convert('RGBA'))
        alpha = rgba[..., 3:4].astype(np.float64) / 255
        behind = np.array([int(liquid[i:i + 2], 16) for i in (1, 3, 5)], np.float64) if liquid and key in CLEAR_FACES else 255.0
        flat = rgba[..., :3] * alpha + behind * (1 - alpha)
        Image.fromarray(np.round(flat).astype(np.uint8)).save(path)
        views[key] = str(path)
    return views


# --- the built drawing ------------------------------------------------------------------------------------------------

def _wrap(face_path, side_mm, height_mm, folder, name, sides=None):
    """A square product's wrap for product_drawing: the front as written (its live type and logo on), its other three
    faces flat in the front's own median colour (unprinted: the reading shows no decoration there) — or, for a face
    painted on its net (``sides``: the right side, back and left side as painted), its own sides."""
    with Image.open(face_path) as image:
        front = np.asarray(image.convert('RGB'))
    k = front.shape[1] / side_mm
    if sides:
        rest = []
        for path in sides:
            with Image.open(path) as image:
                rest.append(np.asarray(image.convert('RGB').resize((front.shape[1], front.shape[0]), Image.LANCZOS)))
    else:
        plain = np.broadcast_to(np.median(front.reshape(-1, 3), axis=0).astype(np.uint8), front.shape)
        rest = [plain, plain, plain]
    wrap = np.concatenate([front] + rest, axis=1)
    path = folder / ('%s-wrap.png' % name)
    Image.fromarray(np.ascontiguousarray(wrap)).save(path)
    return (name, path, (4 * side_mm, height_mm), 0.0, height_mm), k


def drawing(views, brief, geometry, loading, folder, sides=None, ground_hex=None):
    """The built drawing on product_drawing: the bottle's front and three-quarter views (its square section), and the
    loaded stand's front elevation from the die's seats — the header and front strip as written, a product_drawing
    front view of the closed bottle at every seat, back rows first. ``views``: each face as written (face_views)."""
    from . import product_drawing as pd
    folder.mkdir(parents=True, exist_ok=True)
    dims = brief['dimensions_mm']
    side, cap = float(dims['width']), float(dims['cap_height'])
    body = float(dims['height']) - cap
    sides = sides or {}
    bands = [_wrap(views['bottle'], side, body, folder, 'body', sides.get('bottle'))[0],
             _wrap(views['cap'], side, cap, folder, 'cap', sides.get('cap'))[0]]
    with Image.open(views['cap']) as image:
        top = '#%02X%02X%02X' % tuple(int(v) for v in np.median(np.asarray(image.convert('RGB')).reshape(-1, 3), axis=0))
    bottle_png = folder / 'bottle-drawing.png'
    bottle = pd.draw('Lip gloss bottle', bands, side, side / 2, 0.0, top, bottle_png, section='square')
    textures = []
    for _name, path, wrap_mm, bleed, height in bands:
        tex, k = pd.band_texture(path, wrap_mm, bleed)
        textures.append((tex, k, height))
    closed = pd.outline(pd.square_view(textures, side, 0.0, 0.0, tuple(int(top[i:i + 2], 16) for i in (1, 3, 5))))
    s = pd.PX_PER_MM
    elevation = geometry['front_elevation']
    W, H = elevation['width_mm'], elevation['height_mm']
    sheet = Image.new('RGB', (int(math.ceil(W * s)) + 2, int(math.ceil(H * s)) + 2), inside_board(die_of(geometry), ground_hex, (236, 236, 236)))

    def paste_face(key, box):
        with Image.open(views[key]) as image:
            trim = image.convert('RGB')
        size = (max(1, int(round((box[2] - box[0]) * s))), max(1, int(round((box[3] - box[1]) * s))))
        sheet.paste(trim.resize(size, Image.LANCZOS), (int(round(box[0] * s)), int(round(box[1] * s))))

    paste_face('header', elevation['header_box_mm'])
    rows = sorted({slot['row'] for slot in elevation['product_slots']}, reverse=True)
    bottle_img = Image.fromarray(closed, 'RGBA')
    for row in rows:
        for slot in (sl for sl in elevation['product_slots'] if sl['row'] == row):
            x0, _y0, x1, y1 = slot['box_mm']
            size = (max(1, int(round((x1 - x0) * s))), max(1, int(round(bottle_img.height * (x1 - x0) * s / bottle_img.width))))
            scaled = bottle_img.resize(size, Image.LANCZOS)
            sheet.paste(scaled, (int(round(x0 * s)), int(round(y1 * s)) - size[1]), scaled)
    paste_face('front', elevation['base_box_mm'])
    ImageDraw.Draw(sheet).rectangle([0, 0, sheet.width - 1, sheet.height - 1], outline=pd.EDGE_INK)
    stand_png = folder / 'stand-elevation.png'
    sheet.save(stand_png)
    with Image.open(bottle_png) as left:
        left = left.convert('RGB')
        height = max(left.height, sheet.height)
        both = Image.new('RGB', (left.width + 40 + sheet.width, height), pd.SHEET)
        both.paste(left, (0, height - left.height))
        both.paste(sheet, (left.width + 40, height - sheet.height))
    path = folder.parent / 'product-drawing.png'
    both.save(path)
    return {'schema': 'round_files_drawing/2', 'engine': 'product_drawing (D-D12-1.4), square section',
            'label': pd.LABEL, 'bottle': bottle, 'stand_elevation': {
                'file': str(stand_png), 'sha256': sha(stand_png), 'px_per_mm': s,
                'method': 'the header and front strip as drawn; a product_drawing front view of the closed bottle at '
                          'every seat of the die, back rows first; the back wall\'s inside is unprinted board'},
            'shade_loading': loading, 'file': str(path), 'sha256': sha(path)}


def folded_drawing(views, geometry, folder, ground_hex=None):
    """The stand folded and empty, drawn by our own code from its flat faces (product_drawing's sheet, ink and label:
    a drawing, not a render), at one scale: the front (the header's front leaf, the unprinted inside of the back wall,
    the front strip), the right side (its trapezoid as it stands) and the back (the back panel, the header's back leaf
    above it). ``views``: each stand face upright at its trim."""
    from . import product_drawing as pd
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    s = pd.PX_PER_MM / 2
    elevation = geometry['front_elevation']
    W, H = elevation['width_mm'], elevation['height_mm']
    inside = inside_board(die_of(geometry), ground_hex, (222, 214, 200))   # the board's unprinted side, or a rolled wall's ground

    def picture(key, box, sheet):
        with Image.open(views[key]) as image:
            face = image.convert('RGB')
        size = (max(1, int(round((box[2] - box[0]) * s))), max(1, int(round((box[3] - box[1]) * s))))
        sheet.paste(face.resize(size, Image.LANCZOS), (int(round(box[0] * s)), int(round(box[1] * s))))

    front = Image.new('RGB', (int(math.ceil(W * s)), int(math.ceil(H * s))), inside)
    picture('header', elevation['header_box_mm'], front)
    picture('front', elevation['base_box_mm'], front)
    die = die_of(geometry)
    _part, poly = die_face(die, FACES['side']['die'])
    w, h = face_mm_size(poly, FACES['side']['quarters'])
    outline = upright_polygon(poly, FACES['side']['quarters'], w, h)
    side = Image.new('RGB', (int(math.ceil(w * s)), int(math.ceil(h * s))), pd.SHEET)
    with Image.open(views['side']) as image:
        wall = image.convert('RGB').resize(side.size, Image.LANCZOS)
    mask = Image.new('L', side.size, 0)
    ImageDraw.Draw(mask).polygon([((x - STAND_BLEED_MM) * s, (y - STAND_BLEED_MM) * s)
                                  for x, y in outline.exterior.coords], fill=255)
    side.paste(wall, (0, 0), mask)
    backs = []
    for key in ('header_back', 'back'):
        _part, poly = die_face(die, FACES[key]['die'])
        backs.append((key, face_mm_size(poly, FACES[key]['quarters'])))
    back = Image.new('RGB', (int(math.ceil(max(w for _k, (w, _h) in backs) * s)),
                             int(math.ceil(sum(h for _k, (_w, h) in backs) * s))), pd.SHEET)
    top = 0.0
    for key, (bw, bh) in backs:
        picture(key, [0, top, bw, top + bh], back)
        top += bh
    views_out = []
    for name, image in (('front', front), ('right side', side), ('back', back)):
        ImageDraw.Draw(image).rectangle([0, 0, image.width - 1, image.height - 1], outline=pd.EDGE_INK)
        views_out.append((name, image))
    gap, caption = 40, 28
    height = max(image.height for _n, image in views_out) + caption + 24
    sheet = Image.new('RGB', (sum(image.width for _n, image in views_out) + gap * (len(views_out) + 1), height + 30),
                      pd.SHEET)
    draw = ImageDraw.Draw(sheet)
    x = gap
    for name, image in views_out:
        sheet.paste(image, (x, 30 + height - caption - image.height))
        draw.text((x, 30 + height - caption + 6), name, fill=pd.EDGE_INK)
        x += image.width + gap
    draw.text((gap, 8), 'The stand folded, empty: ' + pd.LABEL, fill=pd.EDGE_INK)
    path = folder / 'stand-folded.png'
    sheet.save(path)
    return {'schema': 'flat_folded_drawing/1', 'engine': 'our own code from the flat faces (product_drawing\'s '
            'sheet and label)', 'label': pd.LABEL, 'views': ['front', 'right side', 'back'], 'px_per_mm': s,
            'file': str(path), 'sha256': sha(path)}


# --- the eye ----------------------------------------------------------------------------------------------------------

ALLOWED = ('Allowed differences: the face is drawn flat and front-on (no perspective, no 3D, no physical trim or rim); '
           'the header is a full rectangle with square corners; the dial\'s numerals are drawn as plain tick marks '
           '(owner); every word is live type in the house faces from the brief\'s COPY, in English only (owner, '
           '2026-10-29: no Arabic on any face) and the logo the approved vector; each shade label stands centred on its '
           'own colour band, and the picture\'s invented lettering is replaced by the brand, upright, on the navy ring; '
           'the bottle front carries the brand, the product and the shade\'s name; '
           'measurements are provisional; the stand holds the brief\'s %s.')


def advice_prompt(key, facts, stand_count):
    return ('You are the designer\'s eye, advising the owner, who accepts or redraws each face. Image 1 is the picked '
            'picture, the design intent. Image 2 is its view of this face: %s. Image 3 is the face as built for print, '
            'flat, with its live type and logo. Does the built face read as the picture\'s face: the same idea, ground, '
            'colours, motifs, gold line art, layout and words? Look for raster or invented lettering, doubled or '
            'garbled words, smears, stretched, cropped or patched areas, missing line art, wrong colours, wrong words, '
            'and anything the picture does not show. %s'
            '\nFACE FACTS: %s'
            '\nReturn JSON only: {"verdict":"pass" or "needs_attention","findings":["plain observed finding"]}.'
            % (FACES[key]['label'], ALLOWED % stand_count, json.dumps(facts, ensure_ascii=False)))


def validate_look(payload):
    if not isinstance(payload, dict) or payload.get('verdict') not in ('pass', 'needs_attention'):
        raise ValueError('The designer must return a complete verdict.')
    findings = payload.get('findings')
    if not isinstance(findings, list) or any(not isinstance(row, str) or not row.strip() for row in findings):
        raise ValueError('The designer must list the observed findings.')
    if payload['verdict'] == 'needs_attention' and not findings:
        raise ValueError('The designer must explain a request for attention.')
    return {'verdict': payload['verdict'], 'findings': findings}


def face_facts(key, spec_rows):
    return {'face': FACES[key]['label'], 'live_words': [row['copy'] for row in spec_rows],
            'die': ' / '.join(FACES[key]['die']) if stand_face(key) else FACES[key]['object']}


# --- ornament lettering: COPY set live along a band (from round_files_ornament, 2026-10-28) ---------------------------
# Lettering the picture invents is an ornament zone, never copy.
#
# The reader traces the zone's centre line in the picture; the build removes the
# pictured pseudo-script along it and sets the brief's own COPY there as live
# type, one word at a time along the same path. Nothing is transcribed from the
# picture: the words are the brand and the brief's Arabic COPY fields.

ARABIC = re.compile(r'[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufefc]')
BAND_COVER = 1.2      # removal reaches past the letters' anti-aliased edge
INK_SHARE = .78       # the tallest letter fills this share of the band
WORD_GAP_EM = .35
FIELD_GAP_EM = 1.2
MAX_FIELD_GAP_EM = 6.
MIN_SIZE_PT = 5.


def face_for(copy):
    return 'arabic' if ARABIC.search(copy) else 'latin'


def ornament_copy(brief, fields):
    """The zone's words in reading order: the brand, then every Arabic COPY field."""
    items = [('brand', brief['copy']['brand'])]
    items += [(key, value) for key, value in fields.items()
              if value and (key == 'product_arabic' or key.startswith('arabic_shade_'))]
    return [{'field': key, 'copy': value, 'face': face_for(value)} for key, value in items if value and value.strip()]


def zone_record(zone, crop, copy):
    w, h = crop[2] - crop[0], crop[3] - crop[1]
    return {'path_norm': [[(x - crop[0]) / w, (y - crop[1]) / h] for x, y in zone['path_px']],
            'height_norm': zone['height_px'] / h, 'color': zone['color'], 'copy': copy,
            'source_path_px': zone['path_px'], 'source_height_px': zone['height_px']}


def _walk(points):
    lengths = [0.]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.hypot(x1 - x0, y1 - y0))
    def at(distance):
        distance = min(max(distance, 0.), lengths[-1])
        for index in range(1, len(points)):
            if distance <= lengths[index] or index == len(points) - 1:
                span = lengths[index] - lengths[index - 1] or 1.
                t = (distance - lengths[index - 1]) / span
                (x0, y0), (x1, y1) = points[index - 1], points[index]
                return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
    return lengths[-1], at


def layout_runs(panel_id, index, zone, target, *, foil=False):
    """Words along the zone's path, in visual order, each turned to the path under it.

    The path runs the way the letters advance. A band with Arabic reads right to
    left, so its first field sits at the path's end. Fields that cannot fit at
    5 pt are left out from the end of the reading order and listed.
    """
    from .round_files_export import glyph_metrics
    from .round_files_export import PT
    x0, y0, x1, y1 = target
    path = [(x0 + nx * (x1 - x0), y0 + ny * (y1 - y0)) for nx, ny in zone['path_norm']]
    length_mm, at = _walk(path)
    height_mm = zone['height_norm'] * (y1 - y0)
    items = list(zone['copy'])
    rtl = any(item['face'] == 'arabic' for item in items)
    left_out = []
    while items:
        groups = []
        for item in (reversed(items) if rtl else items):
            words = item['copy'].split()
            words = list(reversed(words)) if item['face'] == 'arabic' else words
            groups.append([(item, word, glyph_metrics(word, item['face'])) for word in words])
        flat = [entry for group in groups for entry in group]
        top = max(metric['box_em'][3] for _, _, metric in flat)
        bottom = min(metric['box_em'][1] for _, _, metric in flat)
        advance_em = sum(metric['advance_em'] for _, _, metric in flat)
        gaps_em = WORD_GAP_EM * (len(flat) - len(groups)) + FIELD_GAP_EM * (len(groups) - 1)
        size = min(height_mm * PT * INK_SHARE / max(top - bottom, .1), length_mm * PT / (advance_em + gaps_em))
        if size >= MIN_SIZE_PT:
            break
        left_out.append(items.pop()['field'])
    if not items:
        return [], {'size_pt': None, 'left_out': left_out, 'reason': 'The band is too short for its COPY at 5 pt.'}
    spare = length_mm * PT - size * (advance_em + gaps_em)
    field_gap = FIELD_GAP_EM * size
    if len(groups) > 1:
        field_gap += min(spare / (len(groups) - 1), (MAX_FIELD_GAP_EM - FIELD_GAP_EM) * size)
    used = size * advance_em + WORD_GAP_EM * size * (len(flat) - len(groups)) + field_gap * (len(groups) - 1)
    cursor = (length_mm * PT - used) / 2
    runs = []
    for group_index, group in enumerate(groups):
        if group_index:
            cursor += field_gap
        for word_index, (item, word, metric) in enumerate(group):
            if word_index:
                cursor += WORD_GAP_EM * size
            advance = metric['advance_em'] * size
            middle = (cursor + advance / 2) / PT
            ax, ay = at(middle - advance / 2 / PT)
            bx, by = at(middle + advance / 2 / PT)
            cx, cy = at(middle)
            runs.append({'name': f"{panel_id}:ornament{index}:{item['field']}:{len(runs)}", 'copy': word,
                         'face': item['face'], 'center_mm': [cx, cy],
                         'angle_deg': math.degrees(math.atan2(-(by - ay), bx - ax)),
                         'center_em_y': (top + bottom) / 2, 'size_pt': size, 'align': 'center',
                         'color': zone['color'], 'foil': foil, 'copy_field': item['field'], 'ornament': True})
            cursor += advance
    return runs, {'size_pt': size, 'left_out': left_out, 'words': len(runs), 'path_mm': length_mm}


# --- the picked picture's reading: panels, COPY fields, rows (from round_files_reading, 2026-10-28) -------------------
# Read the picked picture item by item: COPY fields, the reading's repairs and checks, and seat loading.
#
# Moved unchanged from round_files_art when its picture extraction was retired
# (docs/rounds/reuse-plan.md). The reading names fields; it never supplies printable characters.

PANEL_IDS = ('body_front', 'cap_front', 'stand_header', 'stand_base')
PANEL_LABELS = {'body_front': 'Bottle front', 'cap_front': 'Cap front',
                'stand_header': 'Stand header', 'stand_base': 'Stand base'}
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')
READS = {0: 'upright', 90: 'reads bottom to top', 180: 'upside down', 270: 'reads top to bottom'}


#: the space opened between the bottle's two words in one column, as a share of the column's length (English only)
BOTTLE_GAP = 0.06


def bottle_rows(rows, fields):
    """The bottle front's reading rows for English only: the Arabic line's box takes the shade's name (the first
    shade's; the files set it per product), and the two boxes sharing the column draw apart by BOTTLE_GAP of its
    length so the product and the shade's name stand clear of each other."""
    out = [dict(row, field='shade_0') if row['field'] == 'product_arabic' and 'shade_0' in fields else dict(row)
           for row in rows]
    pair = [row for row in out if row['field'] in ('product_latin', 'shade_0')]
    if len(pair) == 2 and 'rotation' in pair[0] and pair[0]['rotation'] in (90, 270):
        a, b = sorted(pair, key=lambda row: row['box_px'][1])
        length = max(a['box_px'][3], b['box_px'][3]) - min(a['box_px'][1], b['box_px'][1])
        half = BOTTLE_GAP * length / 2
        middle = (a['box_px'][3] + b['box_px'][1]) / 2
        a['box_px'] = [a['box_px'][0], a['box_px'][1], a['box_px'][2], min(a['box_px'][3], middle - half)]
        b['box_px'] = [b['box_px'][0], max(b['box_px'][1], middle + half), b['box_px'][2], b['box_px'][3]]
    return out


def copy_fields(brief):
    """Inspection names a field; it never supplies printable characters."""
    value = brief['copy']['product']
    parts = [part.strip() for part in value.split('/')]
    result = {'product_latin': ' / '.join(part for part in parts if not ARABIC.search(part))}
    if ARABIC_TYPE:
        result['product_arabic'] = ' / '.join(part for part in parts if ARABIC.search(part))
    result.update({'shade_' + str(index): shade['name'] for index, shade in enumerate(brief.get('shades', []))})
    # Never a shade_ prefix: seat loading and proof variants key on it.
    if ARABIC_TYPE:
        result.update({'arabic_shade_' + str(index): shade['name_arabic']
                       for index, shade in enumerate(brief.get('shades', [])) if shade.get('name_arabic')})
    return result


def _box(value, bounds):
    if (not isinstance(value, list) or len(value) != 4 or
            any(isinstance(v, bool) or not isinstance(v, int) for v in value)):
        raise ValueError('Inspection boxes must be integer source pixels')
    if not (bounds[0] <= value[0] < value[2] <= bounds[2] and bounds[1] <= value[1] < value[3] <= bounds[3]):
        raise ValueError('Inspection box is outside its source panel')
    return value


def _number(value):
    if isinstance(value, str):
        try:
            value = float(value.strip().removesuffix('deg').rstrip('°'))
        except ValueError:
            return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return value


def _colour(value):
    """'#RRGGBB' from hex (3, 6 or 8 digits, '#' optional), rgb()/rgba() or an [r, g, b] list; None otherwise."""
    if isinstance(value, str):
        text = value.strip()
        match = re.fullmatch(r'#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})', text)
        if match:
            digits = match.group(1)
            return '#' + (''.join(c * 2 for c in digits) if len(digits) == 3 else digits[:6]).upper()
        match = re.fullmatch(r'rgba?\(([^)]*)\)', text, re.I)
        if not match:
            return None
        parts = [part for part in re.split(r'[\s,/]+', match.group(1).strip()) if part]
        if len(parts) not in (3, 4):
            return None
        channels = [None if _number(part.rstrip('%')) is None else
                    _number(part.rstrip('%')) * (2.55 if part.endswith('%') else 1) for part in parts[:3]]
    elif isinstance(value, (list, tuple)) and len(value) in (3, 4):
        channels = [_number(part) for part in value[:3]]
    else:
        return None
    if any(channel is None or not 0 <= channel <= 255 for channel in channels):
        return None
    return '#' + ''.join(f'{round(channel):02X}' for channel in channels)


def _turn(value):
    """Degrees counter-clockwise as seen: 90 reads bottom to top, 270 top to bottom.

    A negative angle is the screen's clockwise convention, so -90 also reads
    bottom to top. Returns the nearest quarter turn and the exact angle.
    """
    angle = _number(0 if value is None else value)
    if angle is None:
        return None, None
    seen = (-angle if angle < 0 else angle) % 360
    quarter = round(seen / 90) * 90 % 360
    off = abs((seen - quarter + 180) % 360 - 180)
    return quarter, seen if off > 3 else quarter


def _clip(value, bounds):
    """An integer box clipped to bounds, or None when nothing of it is left."""
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    numbers = [_number(v) for v in value]
    if any(number is None for number in numbers):
        return None
    (left, right), (top, bottom) = sorted(numbers[0::2]), sorted(numbers[1::2])
    box = [max(bounds[0], math.floor(left)), max(bounds[1], math.floor(top)),
           min(bounds[2], math.ceil(right)), min(bounds[3], math.ceil(bottom))]
    return box if box[0] < box[2] and box[1] < box[3] else None


def _placed_row(row, crop):
    """Box, colour and turn of one text or logo row: (row, notes) or (None, reason)."""
    box = _clip(row.get('box_px'), crop)
    if box is None:
        return None, 'its box is missing or lies outside its panel'
    colour = _colour(row.get('color'))
    if colour is None:
        return None, f"its colour {row.get('color')!r} is not a colour"
    rotation, angle = _turn(row.get('rotation'))
    if rotation is None:
        return None, f"its rotation {row.get('rotation')!r} is not an angle"
    notes = []
    if box != row.get('box_px'):
        notes.append('box clipped to its panel')
    if colour != row.get('color'):
        notes.append(f"colour {row.get('color')!r} read as {colour}")
    clean = {'box_px': box, 'color': colour, 'rotation': rotation}
    if angle != rotation:
        clean['angle_deg'] = round(angle, 1)
        notes.append(f'set level in its box; the picture turns it {angle:.0f}°')
    elif rotation != row.get('rotation', 0):
        notes.append(f"rotation {row.get('rotation')!r} read as {rotation} ({READS[rotation]})")
    arc = row.get('arc') or row.get('curved') or row.get('path_px')
    if arc:
        clean['arc'] = arc if isinstance(arc, dict) else True
        notes.append('set straight in its bounding box; the picture curves it')
    return clean, notes


def _zone(zone, crop):
    """One ornament lettering zone: its centre line, letter height and colour."""
    if not isinstance(zone, dict):
        return None, 'it is not a zone'
    path = zone.get('path_px')
    if path is None and _clip(zone.get('box_px'), crop) is not None:
        box = _clip(zone.get('box_px'), crop)
        path, zone = [[box[0], (box[1] + box[3]) // 2], [box[2], (box[1] + box[3]) // 2]], dict(zone, height_px=box[3] - box[1])
    points = []
    for point in path if isinstance(path, list) else []:
        if not isinstance(point, (list, tuple)) or len(point) != 2 or any(_number(v) is None for v in point):
            return None, 'its path has a point that is not a pixel'
        points.append([min(max(round(_number(point[0])), crop[0]), crop[2]),
                       min(max(round(_number(point[1])), crop[1]), crop[3])])
    if len(points) < 2 or sum(math.dist(a, b) for a, b in zip(points, points[1:])) < 1:
        return None, 'it has no path inside its panel'
    height = _number(zone.get('height_px'))
    if height is None or height < 1:
        return None, 'it has no letter height'
    colour = _colour(zone.get('color'))
    if colour is None:
        return None, f"its colour {zone.get('color')!r} is not a colour"
    return {'path_px': points, 'height_px': math.ceil(height), 'color': colour}, None


def normalise_reading(payload, image_size, brief):
    """Repair the reading item by item; drop what cannot be repaired and list it.

    One bad text, logo, box or ornament zone never stops the read. A missing
    panel, crop or silhouette is structural and still stops it.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get('panels'), dict):
        raise ValueError('The reading must name its panels')
    reading, findings = deepcopy(payload), []
    allowed = copy_fields(brief)

    def finding(key, item, action, why):
        findings.append({'panel': key, 'label': PANEL_LABELS[key], 'item': item, 'action': action, 'why': why})

    for key in PANEL_IDS:
        panel = reading['panels'].get(key)
        crop = _clip(panel.get('crop_px'), [0, 0, *image_size]) if isinstance(panel, dict) else None
        if crop is None:
            continue
        if crop != panel['crop_px']:
            finding(key, 'crop', 'normalised', 'crop clipped to the picture')
            panel['crop_px'] = crop
        polygon = panel.get('print_polygon_px')
        if isinstance(polygon, list) and all(isinstance(p, (list, tuple)) and len(p) == 2 and
                                             all(_number(v) is not None for v in p) for p in polygon):
            clipped = [[min(max(round(_number(x)), crop[0]), crop[2]), min(max(round(_number(y)), crop[1]), crop[3])]
                       for x, y in polygon]
            if clipped != polygon:
                finding(key, 'print silhouette', 'normalised', 'points clipped to its crop')
                panel['print_polygon_px'] = clipped
        rows = []
        for row in panel.get('text') or []:
            field = row.get('field') if isinstance(row, dict) else None
            item = f'text “{field}”' if isinstance(field, str) else 'a text item'
            if not isinstance(field, str) or not allowed.get(field):
                finding(key, item, 'dropped', 'it names no supplied COPY field')
                continue
            clean, notes = _placed_row(row, crop)
            if clean is None:
                finding(key, item, 'dropped', notes)
                continue
            rows.append(dict(clean, field=field))
            for note in notes:
                finding(key, item, 'normalised', note)
        panel['text'] = rows
        marks = []
        for row in panel.get('marks') or []:
            if not isinstance(row, dict) or row.get('kind', 'logo') != 'logo':
                finding(key, 'a mark', 'dropped', 'only the approved brand logo may replace a mark')
                continue
            clean, notes = _placed_row(row, crop)
            if clean is None:
                finding(key, 'logo', 'dropped', notes)
                continue
            clean.pop('arc', None)
            marks.append(dict(clean, kind='logo'))
            for note in notes:
                finding(key, 'logo', 'normalised', note)
        panel['marks'] = marks
        for name, label in (('lineart_boxes_px', 'line-art box'), ('colour_print_boxes_px', 'colour box')):
            boxes = []
            for box in panel.get(name) or []:
                clipped = _clip(box, crop)
                if clipped is None:
                    finding(key, label, 'dropped', 'it lies outside its panel')
                    continue
                if clipped != box:
                    finding(key, label, 'normalised', 'clipped to its panel')
                boxes.append(clipped)
            panel[name] = boxes
        zones = []
        for zone in panel.get('ornament_lettering') or []:
            clean, why = _zone(zone, crop)
            if clean is None:
                finding(key, 'ornament lettering', 'dropped', why + '; the pictured lettering stays as it is')
                continue
            zones.append(clean)
            finding(key, 'ornament lettering', 'replaced',
                    'invented lettering removed and set with the brand and Arabic COPY along its path')
        panel['ornament_lettering'] = zones
    reading['reading_findings'] = findings
    return reading


def shade_loading(inspection, brief):
    """Bind observed shades to exact zero-based seats; unknown means unknown."""
    stand = inspection['stand']
    rows, columns, count = (stand[key] for key in ('rows', 'columns', 'count'))
    if (any(isinstance(value, bool) or not isinstance(value, int) or value < 1
            for value in (rows, columns, count)) or rows * columns != count or count > 100):
        raise ValueError('The inspected shade loading needs consistent rows, columns and count')
    allowed = {key for key in copy_fields(brief) if key.startswith('shade_')}
    bottles = stand['bottles']
    if not isinstance(bottles, list) or len(bottles) != count:
        raise ValueError('Every inspected stand seat needs a bottle and an explicit shade field or null')
    slots, seen = [], set()
    for bottle in bottles:
        row, column = bottle['row'], bottle['column']
        if (isinstance(row, bool) or isinstance(column, bool) or not isinstance(row, int)
                or not isinstance(column, int) or not 0 <= row < rows or not 0 <= column < columns
                or (row, column) in seen):
            raise ValueError('Inspected shade seats must be distinct zero-based row and column positions')
        _box(bottle['box_px'], [0, 0, *inspection['image_size_px']])
        field = bottle['shade_field']
        if field is not None and (not isinstance(field, str) or field not in allowed):
            raise ValueError('An observed shade must name a supplied shade COPY field or be null')
        seen.add((row, column))
        slots.append({'row': row, 'column': column, 'shade_field': field})
    hero_fields = {row['field'] for row in inspection['panels']['body_front'].get('text', [])
                   if row['field'].startswith('shade_')}
    if len(hero_fields) > 1 or not hero_fields <= allowed:
        raise ValueError('The hero bottle must not carry conflicting or unknown shade COPY fields')
    hero = next(iter(hero_fields)) if hero_fields else None
    from apps.dielines.geometry.counter_display import stand_layout
    layout = stand_layout(brief, inspection)
    result = {'hero_shade_field': hero, 'slots': slots,
              'coordinate_system': 'Inspection rows and columns are zero-based, front to back and left to right.'}
    if layout['differs']:
        seen = {(row['row'], row['column']): row['shade_field'] for row in slots}
        result.update(observed_slots=slots, layout=layout,
                      slots=[{'row': row, 'column': column, 'shade_field': seen.get((row, column))}
                             for row in range(layout['rows']) for column in range(layout['columns'])],
                      seat_rule='A built seat keeps the shade the picture shows at the same row and column; '
                                'a seat the picture does not show stays unresolved.')
    result['unresolved_count'] = sum(row['shade_field'] is None for row in result['slots'])
    return result


def validate_inspection(inspection, image_size, brief):
    if inspection.get('image_size_px') != list(image_size):
        raise ValueError('Inspection dimensions differ from the picked picture')
    if set(inspection.get('panels', {})) != set(PANEL_IDS):
        raise ValueError('Inspection must identify the product front, cap, stand header and base')
    allowed = copy_fields(brief)
    for key, panel in inspection['panels'].items():
        crop = _box(panel['crop_px'], [0, 0, *image_size])
        polygon = panel.get('print_polygon_px')
        if (not isinstance(polygon, list) or len(polygon) < 3 or len(polygon) > 256 or
                any(not isinstance(p, list) or len(p) != 2 or
                    any(isinstance(v, bool) or not isinstance(v, int) for v in p) or
                    not crop[0] <= p[0] <= crop[2] or not crop[1] <= p[1] <= crop[3] for p in polygon)):
            raise ValueError('Each inspected panel needs its source print silhouette')
        for row in panel.get('text', []):
            if row.get('field') not in allowed or not allowed[row['field']]:
                raise ValueError('Printed text must name a nonempty supplied COPY field')
            _box(row['box_px'], crop)
            if row.get('rotation', 0) not in (0, 90, 180, 270) or not HEX.fullmatch(row.get('color', '')):
                raise ValueError('Invalid inspected text placement or colour')
            if 'angle_deg' in row and _number(row['angle_deg']) is None:
                raise ValueError('An inspected text angle note must be a number')
        for row in panel.get('marks', []):
            if row.get('kind', 'logo') != 'logo':
                raise ValueError('Only the approved brand logo may replace an inspected mark')
            _box(row['box_px'], crop)
            if row.get('rotation', 0) not in (0, 90, 180, 270) or not HEX.fullmatch(row.get('color', '')):
                raise ValueError('Invalid inspected logo placement or colour')
        for zone in panel.get('ornament_lettering', []):
            path = zone.get('path_px')
            if (not isinstance(path, list) or len(path) < 2 or
                    any(not isinstance(p, list) or len(p) != 2 or any(isinstance(v, bool) or not isinstance(v, int) for v in p)
                        or not crop[0] <= p[0] <= crop[2] or not crop[1] <= p[1] <= crop[3] for p in path)
                    or isinstance(zone.get('height_px'), bool) or not isinstance(zone.get('height_px'), int)
                    or zone['height_px'] < 1 or not HEX.fullmatch(zone.get('color', ''))):
                raise ValueError('Invalid inspected ornament lettering zone')
        for box in panel.get('lineart_boxes_px', []):
            _box(box, crop)
        for box in panel.get('colour_print_boxes_px', []):
            _box(box, crop)
        if key == 'cap_front' and panel.get('colour_print_boxes_px'):
            raise ValueError('The physical gold cap cannot carry painted colour regions')
    shade_loading(inspection, brief)
    return deepcopy(inspection)


def _local_box(box, crop):
    return [box[0]-crop[0], box[1]-crop[1], box[2]-crop[0], box[3]-crop[1]]


def _normal_box(box, crop):
    w, h = crop[2]-crop[0], crop[3]-crop[1]
    local = _local_box(box, crop)
    return [local[0]/w, local[1]/h, local[2]/w, local[3]/h]


def text_rows(info, crop, literal):
    """Live COPY rows of one panel; the face follows the words' script."""
    return [dict(field=row['field'], copy=literal[row['field']], box_norm=_normal_box(row['box_px'], crop),
                 color=row['color'], rotation=row.get('rotation', 0), face=face_for(literal[row['field']]))
            for row in info.get('text', []) if row['field'] in literal]      # a field not set (Arabic) has no row


def ornament_rows(info, crop, brief):
    copy = ornament_copy(brief, copy_fields(brief))
    return [zone_record(zone, crop, copy) for zone in info.get('ornament_lettering', [])]


# --- dial type: the header's labels and ring words (from round_files_dial, 2026-10-28) --------------------------------
# Live type placed from a drawn dial's own geometry (owner, 2026-10-28): each shade label centred on its own colour
# band (found by the shade's colour in the drawn face, never from the photograph's boxes), and the brand and "ملمع شفاه"
# along the free navy ring only, never over a band, the brand upright. Nothing is erased; the face is read, not changed.
#
# Coordinates are the face picture's pixels (its bleed included); the caller divides by the template's px/mm.

NAVY_HEX = '#1B2B4B'                              # a seed only: the drawn navy is read as the face's own dark ground
GOLD_HEX = '#D5AF59'
BAND_DE = 22.0                                    # a pixel belongs to a shade's band within ΔE00 22 of its seed …
BAND_OPEN_PX = 5                                  # … the band's thin gold rules and ticks opened away
BAND_PIECE_SHARE = 0.15                           # … every piece of it at least 15 % of its largest kept
LABEL_SHARE = 0.62                                # a label block stands in 62 % of its band's thickness …
LABEL_WIDTH_SHARE = 0.82                          # … and 82 % of the free width it is centred in
LINE_GAP_EM = 0.28                                # the Latin name over the Arabic, 0.28 em apart
RING_NAVY, RING_GOLD = 0.85, 0.03                 # a free ring: ≥ 85 % navy and ≤ 3 % gold at its radius
RING_MIN_MM = 2.5                                 # … at least 2.5 mm wide
RING_LETTER_SHARE = 0.62                          # the ring's letters fill 62 % of its width
OUTSIDE_GAP_MM, OUTSIDE_WIDTH_MM = 0.8, 6.0       # with no plain ring drawn: 0.8 mm outside the rim, 6 mm wide
RIM_GOLD, RIM_REACH_PX = 0.08, 8                # the ring is inside the gold rim: ≥ 8 % gold within 8 px beyond it
MIN_PT = 5.0


def _lab_of_hex(hex_):
    rgb = np.array([[[int(hex_.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]]], np.uint8)
    return srgb_to_lab(rgb)[0, 0]


def gold_of(lab):
    """The drawn gold: bright and yellow (b* over 22, L* over 50, a* under 25), grown 1 px so a thin anti-aliased
    tick or rule is seen."""
    gold = (lab[..., 2] > 22) & (lab[..., 0] > 50) & (lab[..., 1] < 25)
    return cv2.dilate(gold.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0


def navy_of(lab):
    """The face's own navy: within ΔE00 15 of the median of its dark bluish pixels."""
    dark = (lab[..., 0] < 32) & (lab[..., 2] < -4)
    seed = np.median(lab[dark], axis=0) if dark.sum() > 100 else _lab_of_hex(NAVY_HEX)
    return delta_e00(lab, np.broadcast_to(seed, lab.shape)) < 15


def band_masks(rgb, shades, seed=7):
    """Each shade's band in the drawn face: the face's own colours clustered (k-means on the coloured pixels, neither
    navy nor gold), each cluster matched to the shade whose brief colour it is nearest (the matching with the least
    total ΔE00), opened, its sizeable pieces. A drawn colour is matched, never assumed to be the brief's hex."""
    from itertools import permutations
    lab = srgb_to_lab(rgb)
    gold, navy = gold_of(lab), navy_of(lab)
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    coloured = ~gold & ~navy & (chroma > 12)
    points = lab[coloured].astype(np.float32)
    out = {field: np.zeros(rgb.shape[:2], bool) for field, _hex in shades}
    if len(points) < 100 * len(shades):
        return out, {'clusters': 0}
    rng = np.random.default_rng(seed)
    sample = points[rng.choice(len(points), min(len(points), 30000), replace=False)]
    cv2.setRNGSeed(seed)
    _c, _labels, centres = cv2.kmeans(sample, len(shades), None,
                                      (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.2), 5, cv2.KMEANS_PP_CENTERS)
    targets = [_lab_of_hex(hex_) for _field, hex_ in shades]
    cost = np.array([[float(delta_e00(centre[None, None, :], target[None, None, :])[0, 0]) for target in targets]
                     for centre in centres])
    match = min(permutations(range(len(shades))), key=lambda order: sum(cost[i, j] for i, j in enumerate(order)))
    distances = np.stack([delta_e00(lab, np.broadcast_to(centre, lab.shape)) for centre in centres])
    nearest = distances.argmin(axis=0)
    record = {'clusters': len(centres)}
    for cluster, shade in enumerate(match):
        field = shades[shade][0]
        mask = (coloured & (nearest == cluster) & (distances[cluster] < BAND_DE)).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((BAND_OPEN_PX,) * 2, np.uint8))
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        if n > 1:
            # the needle may cut a band in two: every piece of at least 15 % of its largest is the band
            areas = stats[1:, cv2.CC_STAT_AREA]
            keep = 1 + np.flatnonzero(areas >= BAND_PIECE_SHARE * areas.max())
            out[field] = np.isin(labels, keep)
        record[field] = {'drawn_lab': [round(float(v), 1) for v in centres[cluster]],
                         'delta_e00_to_brief': round(cost[cluster, shade], 1)}
    return out, record


def _circle(p):
    (x1, y1), (x2, y2), (x3, y3) = p
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-9:
        return None
    ux = ((x1 * x1 + y1 * y1) * (y2 - y3) + (x2 * x2 + y2 * y2) * (y3 - y1) + (x3 * x3 + y3 * y3) * (y1 - y2)) / d
    uy = ((x1 * x1 + y1 * y1) * (x3 - x2) + (x2 * x2 + y2 * y2) * (x1 - x3) + (x3 * x3 + y3 * y3) * (x2 - x1)) / d
    return ux, uy


def dial_centre(masks, seed=7):
    """The dial's centre: the bands' arcs are concentric, so a circle fitted (RANSAC, then least squares on its
    inliers) to their edges — a band's straight edges where the face cuts it are outliers."""
    points = []
    for mask in masks.values():
        if mask.any():
            contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            points += [c.reshape(-1, 2) for c in contours]
    pts = np.concatenate(points).astype(float)
    h, w = masks[next(iter(masks))].shape
    inside = (pts[:, 0] > 2) & (pts[:, 0] < w - 3) & (pts[:, 1] > 2) & (pts[:, 1] < h - 3)
    pts = pts[inside]
    rng = np.random.default_rng(seed)
    best, best_n = None, 0
    for _ in range(400):
        centre = _circle(pts[rng.choice(len(pts), 3, replace=False)])
        if centre is None:
            continue
        r = np.hypot(pts[:, 0] - centre[0], pts[:, 1] - centre[1])
        # one arc's inliers: the radius at which the most points agree
        hist, edges = np.histogram(r, bins=np.arange(0, r.max() + 3, 2.0))
        n = int(hist.max())
        if n > best_n:
            best, best_n = centre, n
    r = np.hypot(pts[:, 0] - best[0], pts[:, 1] - best[1])
    hist, edges = np.histogram(r, bins=np.arange(0, r.max() + 3, 2.0))
    radius = edges[int(hist.argmax())] + 1.0
    arc = pts[np.abs(r - radius) < 3.0]
    a = np.column_stack([2 * arc[:, 0], 2 * arc[:, 1], np.ones(len(arc))])
    b = arc[:, 0] ** 2 + arc[:, 1] ** 2
    cx, cy, _c = np.linalg.lstsq(a, b, rcond=None)[0]
    return float(cx), float(cy)


def _metric(copy, face):
    from .round_files_export import glyph_metrics
    return glyph_metrics(copy, face)


def label_windows(mask, block_h):
    """The widest horizontal window in which a block ``block_h`` px tall stands wholly inside the band: (width, y, x0,
    x1), or None."""
    h, w = mask.shape
    if block_h < 2 or block_h >= h:
        return None
    cs = np.vstack([np.zeros((1, w), np.int32), np.cumsum(mask.astype(np.int32), axis=0)])
    ok = (cs[block_h:] - cs[:-block_h]) == block_h
    best = None
    for y in range(ok.shape[0]):
        row = np.concatenate([[0], ok[y].astype(np.int8), [0]])
        edges = np.flatnonzero(np.diff(row))
        if not len(edges):
            continue
        starts, ends = edges[0::2], edges[1::2]
        i = int(np.argmax(ends - starts))
        if best is None or ends[i] - starts[i] > best[0]:
            best = (int(ends[i] - starts[i]), y, int(starts[i]), int(ends[i]))
    return best


def shade_labels(rgb, k, brief, fields, *, colour, safe_px):
    """Each shade's Latin name over its Arabic name, centred on its own band where the band runs widest and level."""
    from .round_files_export import PT
    shades = [('shade_%d' % i, shade['hex']) for i, shade in enumerate(brief['shades'])]
    masks, matched = band_masks(rgb, shades)
    x0s, y0s, x1s, y1s = safe_px
    rows, record, blocks = [], {}, []
    for i, shade in enumerate(brief['shades']):
        field = 'shade_%d' % i
        mask = masks[field].copy()
        mask[:, :x0s] = mask[:, x1s:] = False
        mask[:y0s] = mask[y1s:] = False
        if mask.sum() < 50:
            record[field] = {'placed': False, 'why': 'its band was not found in the drawn face'}
            continue
        thickness = 2 * float(cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5).max())
        lines = [(fields[field], 'latin')]
        if fields.get('arabic_' + field):
            lines.append((fields['arabic_' + field], 'arabic'))
        metrics = [_metric(copy, face) for copy, face in lines]
        ink = [m['box_em'][3] - m['box_em'][1] for m in metrics]
        block_em = sum(ink) + LINE_GAP_EM * (len(lines) - 1)
        block_h = int(thickness * LABEL_SHARE)
        window = label_windows(mask, block_h)
        if window is None:
            record[field] = {'placed': False, 'why': 'its band has no room for a label'}
            continue
        width, y, xa, xb = window
        size_px = min(block_h / block_em, width * LABEL_WIDTH_SHARE / max(m['advance_em'] for m in metrics))
        blocks.append((field, lines, metrics, ink, block_em, (xa + xb) / 2.0, y + block_h / 2.0, size_px))
        record[field] = {'placed': True, 'band_px': int(masks[field].sum()), 'thickness_px': round(thickness, 1),
                         'centre_px': [round((xa + xb) / 2.0, 1), round(y + block_h / 2, 1)]}
    # the labels are one set: every one at the size the tightest band allows
    size_px = min((block[-1] for block in blocks), default=0.0)
    for field, lines, metrics, ink, block_em, cx, cy, _own in blocks:
        top = cy - block_em * size_px / 2
        for (copy, face), metric, height in zip(lines, metrics, ink):
            rows.append({'name': 'header:' + ('arabic_' if face == 'arabic' else '') + field, 'copy': copy,
                         'face': face, 'center_mm': [cx / k, (top + height * size_px / 2) / k], 'angle_deg': 0.0,
                         'size_pt': max(MIN_PT, size_px / k * PT), 'color': colour, 'foil': False,
                         'copy_field': ('arabic_' if face == 'arabic' else '') + field})
            top += (height + LINE_GAP_EM) * size_px
        record[field]['size_pt'] = round(size_px / k * PT, 2)
    record['matched'] = matched
    return rows, masks, record


def free_ring(rgb, masks, shades, centre, safe_px):
    """The free navy runs outside the outermost band: the radii at which the face is ≥ 85 % navy and ≤ 3 % gold
    (clear of the tick scale), each with how much gold bounds it outward (the rim). Returns (candidates, the outermost
    band's radius), in px."""
    lab = srgb_to_lab(rgb)
    gold_px, navy_px = gold_of(lab), navy_of(lab)
    h, w = gold_px.shape
    cx, cy = centre
    outer = max(float(np.percentile(np.hypot(*(np.argwhere(m)[:, ::-1] - (cx, cy)).T), 99)) for m in masks.values() if m.any())
    thetas = np.radians(np.arange(0, 360, 0.5))
    radii = np.arange(int(outer) + 2, int(math.hypot(w, h)) + 2)
    X = cx + radii[:, None] * np.cos(thetas)[None, :]
    Y = cy - radii[:, None] * np.sin(thetas)[None, :]
    x0s, y0s, x1s, y1s = safe_px
    valid = (X >= x0s) & (X < x1s) & (Y >= y0s) & (Y < y1s)
    xi, yi = np.clip(np.round(X).astype(int), 0, w - 1), np.clip(np.round(Y).astype(int), 0, h - 1)
    count = valid.sum(axis=1)
    navy = (navy_px[yi, xi] & valid).sum(axis=1) / np.maximum(count, 1)
    gold = (gold_px[yi, xi] & valid).sum(axis=1) / np.maximum(count, 1)
    free = (navy >= RING_NAVY) & (gold <= RING_GOLD) & (count >= 20)
    runs, start = [], None
    for i, flag in enumerate(np.append(free, False)):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            runs.append((start, i - 1))
            start = None
    candidates = []
    for a, b in runs:
        r_in, r_out = float(radii[a]), float(radii[b])
        rim = gold[b + 1:b + 1 + RIM_REACH_PX].max() if b + 1 < len(gold) else 0.0
        candidates.append({'r_in': r_in, 'r_out': r_out, 'width_px': r_out - r_in, 'rim_gold': round(float(rim), 3)})
    return candidates, outer


def ring_type(rgb, k, brief, fields, masks, *, colour, safe_px):
    """The brand upright where the free ring runs most nearly level, then "ملمع شفاه" along the rest of the ring
    (layout_runs), both on the navy ring only."""
    from .round_files_export import PT
    shades = [('shade_%d' % i, shade['hex']) for i, shade in enumerate(brief['shades'])]
    centre = dial_centre(masks)
    candidates, outer = free_ring(rgb, masks, shades, centre, safe_px)
    ringed = [c for c in candidates if c['width_px'] >= RING_MIN_MM * k and c['rim_gold'] >= RIM_GOLD]
    record = {'centre_px': [round(centre[0], 1), round(centre[1], 1)], 'outer_band_px': round(outer, 1),
              'candidates': candidates}
    if ringed:
        ring = dict(max(ringed, key=lambda c: c['r_out']), kind='the free navy ring inside the rim')
    else:
        # no plain ring inside the rim was drawn: the navy just outside it, never a band (recorded for the eye)
        wide = [c for c in candidates if c['width_px'] >= RING_MIN_MM * k]
        if not wide:
            record.update(placed=False, why='no free navy ring at least %.1f mm wide was found in the drawn face'
                                            % RING_MIN_MM)
            return [], record
        first = min(wide, key=lambda c: c['r_in'])
        r_in = first['r_in'] + OUTSIDE_GAP_MM * k
        ring = {'r_in': r_in, 'r_out': min(first['r_out'], r_in + OUTSIDE_WIDTH_MM * k), 'rim_gold': first['rim_gold'],
                'kind': 'the navy just outside the gold rim (the drawn face has no plain ring inside it)'}
        ring['width_px'] = ring['r_out'] - ring['r_in']
    record['ring_kind'] = ring['kind']
    r_mid = (ring['r_in'] + ring['r_out']) / 2
    letters = ring['width_px'] * RING_LETTER_SHARE
    cx, cy = centre
    x0s, y0s, x1s, y1s = safe_px
    inside = [t for t in np.arange(180.0, -180.0, -0.25)
              if all(x0s <= cx + r * math.cos(math.radians(t)) < x1s and y0s <= cy - r * math.sin(math.radians(t)) < y1s
                     for r in (ring['r_in'], ring['r_out']))]
    if len(inside) < 8:
        record.update(placed=False, why='the free ring does not lie inside the safe area')
        return [], record
    # the longest run of consecutive angles inside, from the top of the arc down (the path's direction)
    spans, run = [], [inside[0]]
    for t in inside[1:]:
        if abs(run[-1] - t - 0.25) < 1e-6:
            run.append(t)
        else:
            spans.append(run)
            run = [t]
    spans.append(run)
    span = max(spans, key=len)
    brand = brief['copy']['brand']
    metric = _metric(brand, 'latin')
    ink = metric['box_em'][3] - metric['box_em'][1]
    # the brand upright where the ring is most nearly level (its tangent closest to horizontal): its corners on the ring
    level = min(span, key=lambda t: abs(abs(t) - 90))
    size_px = letters / ink
    rows = []
    for _ in range(40):
        advance = metric['advance_em'] * size_px
        corners_ok, at = False, None
        for t in sorted(span, key=lambda t: abs(t - level)):
            px, py = cx + r_mid * math.cos(math.radians(t)), cy - r_mid * math.sin(math.radians(t))
            box = [px + metric['box_em'][0] * size_px - advance / 2, py - ink * size_px / 2,
                   px + metric['box_em'][2] * size_px - advance / 2, py + ink * size_px / 2]
            corners = [(box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])]
            if all(ring['r_in'] <= math.hypot(x - cx, y - cy) <= ring['r_out'] and x0s <= x < x1s and y0s <= y < y1s
                   for x, y in corners):
                corners_ok, at = True, (t, px, py, advance)
                break
        if corners_ok or size_px / k * PT <= MIN_PT:
            break
        size_px *= 0.92
    if at is None:
        record.update(placed=False, why='the brand cannot stand upright on the ring at 5 pt or more')
        return [], record
    t_brand, px, py, advance = at
    rows.append({'name': 'header:ring:brand', 'copy': brand, 'face': 'latin', 'center_mm': [px / k, py / k],
                 'angle_deg': 0.0, 'size_pt': size_px / k * PT, 'color': colour, 'foil': False, 'copy_field': 'brand',
                 'ornament': True})
    # "ملمع شفاه" along the ring straight after the brand, on the longer side of it, at the brand's size
    brand_pt = size_px / k * PT
    half = math.degrees((advance / 2 + letters * 0.6) / r_mid)
    before = [t for t in span if t > t_brand + half]
    after = [t for t in span if t < t_brand - half]
    rest = max((before, after), key=len)
    record.update(placed=True, ring_px=[ring['r_in'], ring['r_out']], brand_angle_on_ring=round(t_brand, 2),
                  brand_size_pt=round(brand_pt, 2))
    phrase = fields.get('product_arabic')
    if not phrase:
        record['product_arabic'] = 'English only (the owner, 2026-10-29): no Arabic on the ring'
        return rows, record
    if len(rest) < 8:
        record['product_arabic'] = 'no room on the ring past the brand'
        return rows, record
    words = [_metric(word, 'arabic') for word in phrase.split()]
    top = max(m['box_em'][3] for m in words)
    bottom = min(m['box_em'][1] for m in words)
    length_px = (sum(m['advance_em'] for m in words) + WORD_GAP_EM * (len(words) - 1)) * size_px * 1.02
    sweep = math.degrees(length_px / r_mid)
    ordered = sorted(rest, reverse=rest is after)               # from the brand outward along the ring
    taken = [t for t in ordered if abs(t - ordered[0]) <= sweep]
    if abs(taken[-1] - taken[0]) < sweep * 0.98:
        record['product_arabic'] = 'no room on the ring past the brand at the brand\'s size'
        return rows, record
    h, w = rgb.shape[:2]
    path = [((cx + r_mid * math.cos(math.radians(t))) / w, (cy - r_mid * math.sin(math.radians(t))) / h)
            for t in sorted(taken, reverse=True)]
    height_px = size_px * (top - bottom) / INK_SHARE
    zone = {'path_norm': path, 'height_norm': height_px / h, 'color': colour,
            'copy': [{'field': 'product_arabic', 'copy': phrase, 'face': 'arabic'}]}
    runs, laid = layout_runs('header', 0, zone, [0.0, 0.0, w / k, h / k])
    rows.extend(dict(run, name='header:ring:' + run['name'].split(':', 2)[2]) for run in runs)
    record['product_arabic'] = laid
    return rows, record


def header_type(face_png, k, face, brief, fields, *, label_colour, ring_colour):
    """The header's live type from its drawn face: the shade labels on their bands, the brand and ملمع شفاه on the
    navy ring. Returns (rows in the upright frame's mm, record)."""
    from PIL import Image
    with Image.open(face_png) as image:
        rgb = np.asarray(image.convert('RGB'))
    b, s = face['bleed_mm'], face['safe_mm']
    safe_px = [int(math.ceil((b + s) * k)), int(math.ceil((b + s) * k)),
               int((b + face['w_mm'] - s) * k), int((b + face['h_mm'] - s) * k)]
    labels, masks, label_record = shade_labels(rgb, k, brief, fields, colour=label_colour, safe_px=safe_px)
    ring, ring_record = ring_type(rgb, k, brief, fields, masks, colour=ring_colour, safe_px=safe_px)
    return labels + ring, {'labels': label_record, 'ring': ring_record, 'px_per_mm': k,
                           'rule': 'placed from the drawn face: each label on its own colour band, the brand upright '
                                   'and ملمع شفاه on the free navy ring'}


# --- colour: CIELAB and CIEDE2000 (from lid_master, the consolidation of 2026-10-28) -----------------------------------

def srgb_to_lab(rgb):
    """sRGB (0–255, …×3) → CIE L*a*b* (D65)."""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    t = (lin @ m.T) / np.array([0.95047, 1.0, 1.08883])
    d = 6.0 / 29.0
    f = np.where(t > d ** 3, np.cbrt(t), t / (3 * d * d) + 4.0 / 29.0)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def delta_e00(lab1, lab2):
    """CIEDE2000 (Sharma, Wu and Dalal 2005), elementwise."""
    l1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    l2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]
    cb = (np.hypot(a1, b1) + np.hypot(a2, b2)) / 2
    g = 0.5 * (1 - np.sqrt(cb ** 7 / (cb ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dhp = h2p - h1p
    dhp = np.where(dhp > 180, dhp - 360, dhp)
    dhp = np.where(dhp < -180, dhp + 360, dhp)
    dhp = np.where(c1p * c2p == 0, 0, dhp)
    dlp, dcp = l2 - l1, c2p - c1p
    dhp_big = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(dhp) / 2)
    lbp, cbp = (l1 + l2) / 2, (c1p + c2p) / 2
    hsum = h1p + h2p
    hbp = np.where(np.abs(h1p - h2p) > 180, (hsum + 360) / 2, hsum / 2)
    hbp = np.where(hbp >= 360, hbp - 360, hbp)
    hbp = np.where(c1p * c2p == 0, hsum, hbp)
    t = (1 - 0.17 * np.cos(np.radians(hbp - 30)) + 0.24 * np.cos(np.radians(2 * hbp))
         + 0.32 * np.cos(np.radians(3 * hbp + 6)) - 0.20 * np.cos(np.radians(4 * hbp - 63)))
    rc = 2 * np.sqrt(cbp ** 7 / (cbp ** 7 + 25.0 ** 7))
    sl = 1 + (0.015 * (lbp - 50) ** 2) / np.sqrt(20 + (lbp - 50) ** 2)
    sc = 1 + 0.045 * cbp
    sh = 1 + 0.015 * cbp * t
    rt = -np.sin(np.radians(2 * 30 * np.exp(-(((hbp - 275) / 25) ** 2)))) * rc
    return np.sqrt((dlp / sl) ** 2 + (dcp / sc) ** 2 + (dhp_big / sh) ** 2 + rt * (dcp / sc) * (dhp_big / sh))


# --- one ground, the panels linked across their folds (the owner, 2026-10-30: every round, every die) -------------------
# The painting is the artwork, so what holds it together is painted, never laid over it. Panels that meet at a fold are
# painted as one continuous wrap: their layout unrolled (wrap_layout), one edit on it (paint_wrap), each face cut from it.
# Every panel's ground and every fold are then measured on the raster that prints (print_rules). Each measure takes its
# panels and its folds as data, so a stand and a carton are the same check.

GROUND_DE = 4.0                 # a panel's ground within this of the design's (ΔE00, the owner's bar)
FOLD_DE = 3.0                   # the colour across a fold (ΔE00, the owner's bar), read on its ground: on dense art a
                                # fold through one picture measures median 3.3 pixel to pixel, for a thread is not a colour
FOLD_BAND_MM = 0.5              # a band meets itself across a fold within this (the owner's bar)
FOLD_STEP_MM = 0.25             # samples along a fold
FOLD_TOUCH_MM = 0.1             # the strip either side of a fold starts here: the pixels that touch it
FOLD_DEPTH_MM = 8.0             # and ends here: a band runs through it, a thread does not
FOLD_STRIP = 40                 # points read across a strip at each sample
FOLD_BAND_L = 20.0              # a band: a row this much lighter than what is around it (gold rules measured 27–43 L,
                                # the motifs along a fold under 14 on round 4)
FOLD_NO_BAND_MM = 99.0          # what a band with nothing to meet on the other side counts as
FOLD_BAND_MET = 0.25            # the other side meets a band where it rises at least this share of the band's own height
#: a surface whose ground is its own material, never the design's (2026-10-30: "No green" on the cap's own gold; the
#: bottle's clear body stays unprinted, as ruled)
OWN_GROUND = {'bottle': 'its clear body stays unprinted', 'cap': 'its own gold'}


def _hex_lab(value):
    return srgb_to_lab(np.array([[int(value[i:i + 2], 16) for i in (1, 3, 5)]], np.float64))[0]


def _lab_hex(lab):
    rgb = cv2.cvtColor(np.float32(np.reshape(lab, (1, 1, 3))), cv2.COLOR_LAB2RGB)[0, 0]
    return '#%02X%02X%02X' % tuple(int(round(float(np.clip(v, 0, 1)) * 255)) for v in rgb)


def ground_of(rgb, mask):
    """A panel's ground on its printed pixels: its largest colour (k-means in Lab, colours within ΔE00 6 one colour).
    Returns (Lab, share of the panel)."""
    lab = srgb_to_lab(np.asarray(rgb)[mask].astype(np.float64))
    sample = lab[np.random.default_rng(0).choice(len(lab), min(len(lab), 60000), replace=False)].astype(np.float32)
    cv2.setRNGSeed(0)
    clusters = min(6, max(1, len(np.unique(sample.round(), axis=0))))
    _c, labels, centres = cv2.kmeans(sample, clusters, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, .2),
                                     3, cv2.KMEANS_PP_CENTERS)
    labels, parent = labels.ravel(), list(range(clusters))

    def find(i):
        while parent[i] != i:
            i = parent[i]
        return i
    for i in range(clusters):
        for j in range(i + 1, clusters):
            if delta_e00(centres[i:i + 1].astype(np.float64), centres[j:j + 1].astype(np.float64))[0] < 6:
                parent[find(j)] = find(i)
    merged = np.array([find(i) for i in range(clusters)])[labels]
    largest = int(np.argmax(np.bincount(merged, minlength=clusters)))
    return sample[merged == largest].mean(axis=0).astype(np.float64), float((merged == largest).mean())


def ground_check(panels, ground_hex, *, own=()):
    """Each panel's ground against the design's. ``panels``: {name: (rgb, printed mask)}; ``own``: the panels whose
    ground is their own material, reported and never held to it. Returns the record: its rows, its ``off`` names."""
    target, rows = _hex_lab(ground_hex), {}
    for name, (rgb, mask) in panels.items():
        if name in own:
            rows[name] = {'own_ground': True, 'holds': True}
            continue
        lab, share = ground_of(rgb, mask)
        de = float(delta_e00(lab[None], target[None])[0])
        rows[name] = {'ground_hex': _lab_hex(lab), 'share': round(share, 3), 'delta_e00': round(de, 2), 'holds': de <= GROUND_DE}
    off = [name for name, row in rows.items() if not row['holds']]
    return {'schema': 'ground_check/1', 'ground_hex': ground_hex, 'bar_delta_e00': GROUND_DE, 'panels': rows, 'off': off,
            'holds': not off}


def fold_samples(die, frame):
    """Where to read each fold on a raster at ``frame``, from the die's own pairs (counter_display_files.fold_pairs): a
    point either side of it at each end of its strip."""
    from apps.dielines.exporters import counter_display_files as cdf
    far = {seam['seam']: seam['pairs'] for seam in cdf.fold_pairs(die, frame, depth_mm=FOLD_DEPTH_MM, step_mm=FOLD_STEP_MM)}
    return {seam['seam']: {'kind': seam['kind'], 'near': seam['pairs'], 'far': far[seam['seam']]}
            for seam in cdf.fold_pairs(die, frame, depth_mm=FOLD_TOUCH_MM, step_mm=FOLD_STEP_MM) if seam['seam'] in far}


def _fold_strip(pixels, seam, side):
    """One side of a fold read off a raster: samples × FOLD_STRIP × 3."""
    n = min(len(seam['near']), len(seam['far']))
    near, far = (np.array([pair[side] for pair in seam[end][:n]], np.float64) for end in ('near', 'far'))
    t = np.linspace(0, 1, FOLD_STRIP)[None, :, None]
    points = np.round(near[:, None, :] * (1 - t) + far[:, None, :] * t).astype(int)
    return pixels[points[..., 1], points[..., 0]]


def _band_rows(light):
    """The bands along one side of a fold (lightness per sample): (each band's middle in samples, the rows' rise)."""
    from scipy.ndimage import median_filter
    rise = light - median_filter(light, size=int(14 / FOLD_STEP_MM) | 1, mode='nearest')
    if rise.max() < FOLD_BAND_L:
        return [], rise
    rows = np.nonzero(rise > max(FOLD_BAND_L, 0.5 * rise.max()))[0]
    return [int(group.mean()) for group in np.split(rows, np.nonzero(np.diff(rows) > 1 / FOLD_STEP_MM)[0] + 1)], rise


def _band_offset(a, b):
    """How far apart two sides' bands meet across a fold, in mm: every band of either side looked for on the other. A band
    the other side has nowhere (a wall's art stopping at the crease) counts as FOLD_NO_BAND_MM. Returns (offset, bands)."""
    rows_a, rise_a = _band_rows(a)
    rows_b, rise_b = _band_rows(b)
    within, worst = int(FOLD_BAND_MM / FOLD_STEP_MM), 0.0
    for rows, rise, others, other_rise in ((rows_a, rise_a, rows_b, rise_b), (rows_b, rise_b, rows_a, rise_a)):
        for row in rows:
            low, high = max(0, row - within), row + within + 1
            if other_rise[low:high].max() >= FOLD_BAND_MET * rise[row]:
                continue
            nearest = min((abs(row - other) for other in others), default=None)
            worst = max(worst, FOLD_NO_BAND_MM if nearest is None else nearest * FOLD_STEP_MM)
    return worst, len(rows_a) + len(rows_b)


def fold_check(rgb, samples, *, crossing=('folded corner',)):
    """Every fold on a raster: the colour across it (the two sides' grounds, ground_of, on the strip either side, the bar
    FOLD_DE; pixel to pixel beside it, as a note) and, where the art's bands cross it (``crossing``, the seam kinds or
    names), how far apart they meet (FOLD_BAND_MM). A fold the bands run along has its colour only. Returns the record:
    its rows and the folds that fail."""
    from scipy.ndimage import gaussian_filter1d
    pixels = np.asarray(rgb)[..., :3]
    rows, off = [], []
    for name, seam in samples.items():
        a, b = _fold_strip(pixels, seam, 0), _fold_strip(pixels, seam, 1)
        everywhere = np.ones(a.shape[:2], bool)
        ground_a, ground_b = ground_of(a, everywhere)[0], ground_of(b, everywhere)[0]
        sigma = 3 / FOLD_STEP_MM
        touching = delta_e00(srgb_to_lab(gaussian_filter1d(a[:, 0].astype(np.float64), sigma, axis=0, mode='nearest')),
                             srgb_to_lab(gaussian_filter1d(b[:, 0].astype(np.float64), sigma, axis=0, mode='nearest')))
        row = {'fold': name, 'kind': seam['kind'], 'length_mm': round(len(a) * FOLD_STEP_MM, 1),
               'colour_de00': round(float(delta_e00(ground_a[None], ground_b[None])[0]), 2),
               'touching_de00': round(float(touching.mean()), 2), 'bands': 'along', 'band_offset_mm': None}
        holds = row['colour_de00'] <= FOLD_DE
        if seam['kind'] in crossing or name in crossing:
            light = [srgb_to_lab(side.reshape(-1, 3).astype(np.float64))[:, 0].reshape(side.shape[:2]).mean(axis=1)
                     for side in (a, b)]
            offset, bands = _band_offset(*light)
            row.update(bands='cross', band_offset_mm=round(offset, 2), band_rows=bands)
            if offset > FOLD_BAND_MM:
                holds = False
        row['holds'] = holds
        rows.append(row)
        if not holds:
            off.append(name)
    return {'schema': 'fold_check/1', 'bars': {'colour_de00': FOLD_DE, 'band_offset_mm': FOLD_BAND_MM}, 'folds': rows,
            'off': off, 'holds': not off}


def design_ground(record):
    """The design's ground, one rule for every round: the picked board's palette colour whose role names the ground, as
    {'hex', 'name'}; else None, and the page says it was not measured (a round from before the boards)."""
    path = flow.round_root(record) / 'board-pick.json'
    if path.exists():
        for colour in json.loads(path.read_text()).get('board', {}).get('palette', []):
            if 'ground' in str(colour.get('role', '')).lower():
                return {'hex': colour['hex'], 'name': colour.get('name', '')}
    return None


def print_rules(drawn, geometry, ground_hex):
    """The owner's two painted rules, on the stand's raster as it prints ($0): every panel's ground, every fold. Returns
    the record; ground is None when the design names none."""
    from apps.dielines.exporters import counter_display_files as cdf
    die = die_of(geometry)
    full, frame, masks, _native = stand_raster(drawn, die)
    rgb = full[..., :3]
    panels = {}
    for key in (key for key in FACES if stand_face(key)):
        panels[key] = (rgb, masks['owner'] == masks['names'].index(FACES[key]['die'][1]) + 1)
    return {'schema': 'print_rules/1', 'ground': ground_check(panels, ground_hex) if ground_hex else None,
            'folds': fold_check(rgb, fold_samples(die, frame)),
            'measured_on': 'the stand\'s raster as it prints, %.0f ppi' % frame['dpi_at_1to1']}


# --- the wrap ---------------------------------------------------------------------------------------------------------

_EDGE = {'top': 0, 'right': 1, 'bottom': 2, 'left': 3}
#: the stand's outside, unrolled from the back panel: right wall, back, left wall, front strip; the header back rises from
#: the back; the header front folds over its top. The front strip's far end folds to the right wall's short end: that is
#: the wrap's one closing fold, the one a strip cannot join by construction (checked like every other).
STAND_WRAP = (('back', 'left', 'side', 'right'), ('back', 'right', 'left', 'left'), ('left', 'right', 'front', 'left'),
              ('back', 'top', 'header_back', 'bottom'), ('header_back', 'top', 'header', 'top'))
WRAP_MARGIN_PX = 16
WRAP_MAX_EDGE, WRAP_MAX_PX = 3840, 8_294_400        # gpt-image-2's limits; above PANEL_MAX_PX its results may vary
WRAP_CONTEXT_MM = 15.0                              # a repainted panel sees this much of the art it joins


def wrap_layout(panels, joins, *, bleed=STAND_BLEED_MM):
    """Panels joined edge to edge in one plane. ``panels``: {name: {'w', 'h', 'outline'}} (mm, upright, origin the
    panel's top-left, no bleed); ``joins``: (placed panel, its edge, next panel, its edge): an edge along the art's up
    joins with the two feet level, across it centred. Returns {'panels': {name: place}, 'bleed'}; a place's ``q`` is the
    quarters it lies turned clockwise, ``x, y, W, H`` its box and ``poly`` its outline in the plane."""
    from shapely.affinity import translate
    first = joins[0][0]

    def placed(name, x, y, q):
        panel = panels[name]
        w, h = panel['w'], panel['h']
        W, H = (w, h) if q % 2 == 0 else (h, w)
        coords = [_wrap_point(u, v, w, h, q) for u, v in panel['outline'].exterior.coords]
        return {'x': x, 'y': y, 'q': q, 'W': W, 'H': H, 'w': w, 'h': h, 'poly': translate(Polygon(coords), x, y)}
    out = {first: placed(first, 0.0, 0.0, 0)}
    for a, edge_a, b, edge_b in joins:
        at = out[a]
        facing = (_EDGE[edge_a] + at['q']) % 4
        q = ((facing + 2) % 4 - _EDGE[edge_b]) % 4
        W, H = (panels[b]['w'], panels[b]['h']) if q % 2 == 0 else (panels[b]['h'], panels[b]['w'])
        if facing == 1:
            x, y = at['x'] + at['W'], at['y'] + at['H'] - H
        elif facing == 3:
            x, y = at['x'] - W, at['y'] + at['H'] - H
        elif facing == 0:
            x, y = at['x'] + (at['W'] - W) / 2, at['y'] - H
        else:
            x, y = at['x'] + (at['W'] - W) / 2, at['y'] + at['H']
        out[b] = placed(b, x, y, q)
    return {'panels': out, 'bleed': bleed}


def _wrap_point(u, v, w, h, q):
    """A point of a panel's upright frame, in its box turned ``q`` quarters clockwise."""
    return [(u, v), (h - v, u), (w - u, h - v), (v, w - u)][q % 4]


def stand_panels(geometry):
    """The stand's printed faces as wrap_layout's panels."""
    from shapely.affinity import translate
    die, out = die_of(geometry), {}
    for key in FACES:
        if stand_face(key):
            _part, poly = die_face(die, FACES[key]['die'])
            w, h = face_mm_size(poly, FACES[key]['quarters'])
            out[key] = {'w': w, 'h': h, 'outline': translate(upright_polygon(poly, FACES[key]['quarters'], w, h),
                                                             -STAND_BLEED_MM, -STAND_BLEED_MM)}
    return out


def wrap_canvas(layout, open_, *, context_mm=0.0):
    """The canvas one edit paints ``open_`` on: their box with their bleed and ``context_mm`` of what they join, at 300
    PPI where it fits, else as large as the model's limits allow (one panel keeps within what it draws reliably, a wrap
    may use all of its range). Returns {'box_mm', 'px_per_mm', 'size', 'canvas_px', 'offset_px', 'native_ppi'}."""
    places = [layout['panels'][name] for name in open_]
    pad = layout['bleed'] + context_mm
    x0, y0 = min(p['x'] for p in places) - pad, min(p['y'] for p in places) - pad
    x1, y1 = max(p['x'] + p['W'] for p in places) + pad, max(p['y'] + p['H'] for p in places) + pad
    W, H, limit = x1 - x0, y1 - y0, (PANEL_MAX_PX if len(open_) == 1 else WRAP_MAX_PX)
    room = WRAP_MAX_EDGE - 2 * WRAP_MARGIN_PX
    k = min(K, room / W, room / H)
    for _ in range(80):
        cw, ch = _up16(math.ceil(W * k) + 2 * WRAP_MARGIN_PX), _up16(math.ceil(H * k) + 2 * WRAP_MARGIN_PX)
        cw, ch = _up16(max(cw, math.ceil(ch / 3))), _up16(max(ch, math.ceil(cw / 3)))
        if cw * ch <= limit and max(cw, ch) <= WRAP_MAX_EDGE:
            break
        k *= 0.99
    else:
        raise ValueError('A %.1f × %.1f mm wrap does not fit one edit.' % (W, H))
    return {'box_mm': [x0, y0, x1, y1], 'px_per_mm': round(k, 6), 'size': '%dx%d' % (cw, ch), 'canvas_px': [cw, ch],
            'offset_px': [(cw - W * k) / 2, (ch - H * k) / 2], 'native_ppi': round(k * 25.4, 1)}


def is_wrap_size(size):
    """A canvas wrap_canvas can make: multiples of 16, aspect 1:3–3:1, inside gpt-image-2's whole range."""
    try:
        w, h = (int(v) for v in str(size).split('x'))
    except ValueError:
        return False
    return (w % 16 == 0 and h % 16 == 0 and 1 / 3 <= w / h <= 3 and max(w, h) <= WRAP_MAX_EDGE and
            PANEL_MIN_PX <= w * h <= WRAP_MAX_PX)


def _wrap_px(canvas, x, y):
    k, (ox, oy), (x0, y0) = canvas['px_per_mm'], canvas['offset_px'], canvas['box_mm'][:2]
    return ox + (x - x0) * k, oy + (y - y0) * k


def wrap_masks(layout, canvas):
    """Per canvas pixel: ``paint`` — inside a panel or its bleed; ``owner`` — the panel it belongs to (1-based, in
    ``names``' order; a bleed pixel goes to the nearest panel), 0 elsewhere. As counter_display_files.flat_masks on a
    die."""
    from scipy import ndimage
    from shapely.ops import unary_union
    W, H = canvas['canvas_px']
    names = list(layout['panels'])
    paint, owner = Image.new('L', (W, H), 0), Image.new('L', (W, H), 0)
    around = unary_union([p['poly'].buffer(layout['bleed'], join_style=2) for p in layout['panels'].values()])
    for ring in _rings(around):
        ImageDraw.Draw(paint).polygon([_wrap_px(canvas, x, y) for x, y in ring], fill=255)
    for index, name in enumerate(names, 1):
        ImageDraw.Draw(owner).polygon([_wrap_px(canvas, x, y) for x, y in layout['panels'][name]['poly'].exterior.coords],
                                      fill=index)
    paint, owner = np.asarray(paint) > 0, np.asarray(owner)
    _d, (iy, ix) = ndimage.distance_transform_edt(owner == 0, return_indices=True)
    return {'paint': paint, 'owner': np.where(paint, np.where(owner > 0, owner, owner[iy, ix]), 0).astype(np.uint8),
            'names': names}


def _frame_box(layout, canvas, name):
    """A panel's frame (its bleed included) on the canvas, in whole pixels."""
    place, b = layout['panels'][name], layout['bleed']
    (u0, v0), (u1, v1) = _wrap_px(canvas, place['x'] - b, place['y'] - b), _wrap_px(canvas, place['x'] + place['W'] + b,
                                                                                    place['y'] + place['H'] + b)
    return [int(round(u0)), int(round(v0)), int(round(u1)), int(round(v1))]


def wrap_picture(layout, canvas, pictures, *, only=None):
    """The panels' upright pictures (``pictures``: {name: path}, each its frame with its bleed) laid on the canvas, each
    on its own pixels; white elsewhere. Returns the RGB canvas."""
    masks = wrap_masks(layout, canvas)
    W, H = canvas['canvas_px']
    out = np.full((H, W, 3), 255, np.uint8)
    for index, name in enumerate(masks['names'], 1):
        if name not in pictures or (only is not None and name not in only):
            continue
        x0, y0, x1, y1 = _frame_box(layout, canvas, name)
        sx0, sy0, sx1, sy1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
        if sx1 <= sx0 or sy1 <= sy0:
            continue                                                    # off this canvas
        with Image.open(pictures[name]) as image:
            art = np.asarray(Image.fromarray(turn(np.asarray(image.convert('RGB')), layout['panels'][name]['q']))
                             .resize((x1 - x0, y1 - y0), Image.LANCZOS))
        mine = masks['owner'] == index
        layer = np.full((H, W, 3), 255, np.uint8)
        layer[sy0:sy1, sx0:sx1] = art[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0]
        out[mine] = layer[mine]
    return out


def ground_tone(rgb, mask, ground_hex, *, reach=12.0):
    """A painting's ground brought to the design's in the picture's own pixels ($0): the difference between its largest
    colour and the ground, added to its pixels by how near they are to that colour, so that its threads and fruit stay as
    painted. One tone for the whole painting, so no fold gains a step. A ground further than ``reach`` off is not a tone
    but a wrong colour: left as it is, for the check and its one repaint. Returns (pixels, record)."""
    measured, _share = ground_of(rgb, mask)
    target = _hex_lab(ground_hex)
    de = float(delta_e00(measured[None], target[None])[0])
    record = {'ground_before': _lab_hex(measured), 'ground_hex': ground_hex, 'delta_e00_before': round(de, 2)}
    if de > reach or de <= GROUND_DE / 4:
        return rgb, dict(record, toned=False)
    lab = cv2.cvtColor(np.float32(np.asarray(rgb) / 255), cv2.COLOR_RGB2LAB)
    cv_measured = cv2.cvtColor(np.float32(np.reshape(_lab_rgb(measured), (1, 1, 3))), cv2.COLOR_RGB2LAB)[0, 0]
    cv_target = cv2.cvtColor(np.float32(np.reshape(_lab_rgb(target), (1, 1, 3))), cv2.COLOR_RGB2LAB)[0, 0]
    near = np.exp(-(np.linalg.norm(lab - cv_measured, axis=2) / 14.0) ** 2)[..., None] * mask[..., None]
    toned = cv2.cvtColor(np.float32(lab + near * (cv_target - cv_measured)), cv2.COLOR_LAB2RGB)
    return np.round(np.clip(toned, 0, 1) * 255).astype(np.uint8), dict(record, toned=True)


def _lab_rgb(lab):
    """A Lab colour as sRGB, 0–1: through OpenCV's Lab, the same D65 white as srgb_to_lab within a rounding."""
    return cv2.cvtColor(np.float32(np.reshape(lab, (1, 1, 3))), cv2.COLOR_LAB2RGB)[0, 0]


WRAP_NAMES = {'side': 'RIGHT WALL', 'back': 'BACK PANEL', 'left': 'LEFT WALL', 'front': 'FRONT STRIP',
              'header_back': 'HEADER BACK', 'header': 'HEADER FRONT'}
WRAP_WHOLE = ('One continuous painting. The panels are joined edge to edge here as they fold around the stand, so this is '
              'one piece of cloth, not separate panels. Every horizontal band runs dead level and unbroken across the '
              'whole width, straight over every crease, at the same height above the bottom edge on every panel. Vines, '
              'stems and small flowers cross the creases and carry straight on. Large motifs (a fruit, an animal, a '
              'medallion, a frame) stand whole inside one panel, never on a crease and never cut by a panel\'s top edge.')
WRAP_CLOSING = ('The two far ends of this strip fold together on the stand: at the short left end and the far right end let '
                'only the ground and the bands reach the edge, at the same heights at both ends, no motif cut there.')
WRAP_JOIN = ('The opaque art around the transparent shape is already painted and stays. Continue it: every band, vine and '
             'colour that reaches the transparent shape carries straight on across the crease, at the same height, on the '
             'same ground.')


def _view_box(box, canvas, view):
    """A pixel box of the canvas, on the canvas as it is sent (turned ``view`` quarters clockwise)."""
    W, H = canvas['canvas_px']
    corners = [[(x, y), (H - y, x), (W - x, H - y), (y, W - x)][view % 4] for x, y in ((box[0], box[1]), (box[2], box[3]))]
    return [min(c[0] for c in corners), min(c[1] for c in corners), max(c[0] for c in corners), max(c[1] for c in corners)]


def wrap_prompt(layout, canvas, open_, *, ground_hex=None, ground_name='', keep='', rules='', note='', view=0, plain=None):
    rows, frames = [], []
    for name in open_:
        x0, y0, x1, y1 = _view_box(_frame_box(layout, canvas, name), canvas, view)
        rows.append('- %s: x %d–%d, y %d–%d px.' % (WRAP_NAMES.get(name, name.upper()), x0, x1, y0, y1))
    for name, box in (plain or {}).items():
        place, b = layout['panels'][name], layout['bleed']
        a = _wrap_point(box[0] - b, box[1] - b, place['w'], place['h'], place['q'])
        c = _wrap_point(box[2] - b, box[3] - b, place['w'], place['h'], place['q'])
        x0, y0, x1, y1 = (int(round(v)) for v in _view_box(_wrap_px(canvas, place['x'] + a[0], place['y'] + a[1]) +
                                                           _wrap_px(canvas, place['x'] + c[0], place['y'] + c[1]), canvas, view))
        frames.append('- %s: x %d–%d, y %d–%d px.' % (WRAP_NAMES.get(name, name.upper()), min(x0, x1), max(x0, x1),
                                                      min(y0, y1), max(y0, y1)))
    whole = len(open_) > 1
    words = ['Image 1 is the sheet: white, with TRANSPARENT shape%s, the only place to paint: the outside of a folding '
             'cardboard counter stand%s. Fill %s exactly, edge to edge and into the bleed, with flat print artwork seen '
             'front-on: no perspective, no 3D, no shadow, no product, no mockup, no guide lines. Keep the white white.%s'
             % ('s' if whole else '', ', unrolled flat' if whole else '', 'them' if whole else 'it',
                '' if not rows else ' The panels (pixels, x from the left, y from the top):\n' + '\n'.join(rows)),
             'Image 2 shows this art as it stands now, panel by panel, placed on the same sheet. Keep its drawing: its '
             'colours, its motifs, its woven richness, its band patterns and the order of its rows. Where its bands and '
             'its panels do not meet, repaint so that they do.']
    words.append(WRAP_WHOLE + ' ' + WRAP_CLOSING if whole else WRAP_JOIN)
    if ground_hex:
        words.append('The ground is one flat colour on every panel, %s%s: the same colour everywhere, never darker on one '
                     'panel, never cream.' % (ground_hex, ' (%s)' % ground_name if ground_name else ''))
    if frames:
        words.append('These areas stay empty, plain ground with no motif, each inside a thin frame or band: that is where '
                     'the words go. Paint nothing else in them:\n' + '\n'.join(frames))
    if rules:
        words.append(rules)
    words.append(UPRIGHT_WORDS.replace('on this face', 'here'))
    if keep:
        words.append('The owner\'s words for the whole stand (where they say image 2 they meant his picked picture): "%s"'
                     % keep)
    words.append(FLAT_NO_WORDS)
    if note:
        words.append(NOTE_LAST % note)
    return '\n\n'.join(words)


def is_word_place(box, panel):
    """Whether a plain area is a place for words, not a face that is plain all over."""
    return box is not None and (box[2] - box[0]) * (box[3] - box[1]) < 0.5 * panel['w'] * panel['h']


def lost_word_place(record, panel):
    """The plain area its words need (FLAT_WORDS 'band' or 'frame') that a face cut from a wrap had and has lost: the box
    (its upright frame, mm), or None when it has one or never had one."""
    if FLAT_WORDS.get(record['key']) not in ('band', 'frame') or plain_area_mm(record) is not None:
        return None
    had = plain_area_mm(dict(record, face=record['reference']['path']))
    return had if is_word_place(had, panel) else None


RESTORE_MARGIN_MM, RESTORE_FEATHER_MM = 2.0, 0.5


def restore_word_place(root, key, n, record, box, panel):
    """Drawing ``n`` of a face cut from a wrap, with the plain area its words stand in put back at $0 (record: the face that
    lost it; box: where its reference has it, its upright frame in mm): that area and its frame, from the reference, feathered
    into the wrap's own pixels. Every band and fold of the wrap stands as painted; a repaint of the face would not keep them
    (round 4's right wall, repainted alone, moved two of its three bands 6–13 mm off the back's)."""
    folder = drawing_folder(root, key, n)
    record_path = folder / 'record.json'
    if record_path.exists():
        return _checked(record_path, 'face')
    folder.mkdir(parents=True, exist_ok=True)
    k = record['template']['px_per_mm']
    with Image.open(record['face']) as image:
        rgb = np.asarray(image.convert('RGB')).astype(np.float32)
    with Image.open(record['reference']['path']) as image:
        given = np.asarray(image.convert('RGB').resize((rgb.shape[1], rgb.shape[0]), Image.LANCZOS)).astype(np.float32)
    x0, y0, x1, y1 = (v * k for v in (box[0] - RESTORE_MARGIN_MM, box[1] - RESTORE_MARGIN_MM, box[2] + RESTORE_MARGIN_MM,
                                      box[3] + RESTORE_MARGIN_MM))
    mask = np.zeros(rgb.shape[:2], np.float32)
    mask[max(0, int(y0)):int(y1), max(0, int(x0)):int(x1)] = 1
    mask = cv2.GaussianBlur(mask, (0, 0), RESTORE_FEATHER_MM * k)[..., None]
    out = np.round(rgb * (1 - mask) + given * mask).astype(np.uint8)
    Image.fromarray(out).save(folder / 'face.png')
    for name in ('template.png', 'reference.png'):
        (folder / name).write_bytes((Path(record['face']).parent / name).read_bytes())
    made = dict(record, n=n, face=str(folder / 'face.png'), face_sha256=sha(folder / 'face.png'), cost_usd=0.0,
                template=dict(record['template'], template=str(folder / 'template.png')),
                reference=dict(record['reference'], path=str(folder / 'reference.png')),
                restored={'box_mm': [round(v, 2) for v in box], 'of': record['n'], 'from': 'its reference'},
                rule='the wrap\'s own pixels, the plain area its words stand in put back at $0')
    flow.write_json(record_path, made)
    return made


def wrap_folder(root, key, n):
    return flat_root(root) / 'wraps' / ('%s-%d' % (key, n))


def paint_wrap(ctx, key, n, layout, open_, pictures, *, ground_hex=None, ground_name='', keep='', rules='', note='',
               quality='medium', context=None, plain=None):
    """One paid edit of ``open_``, joined as one picture (``key`` 'stand', or the one face being repainted): image 1 their
    transparent shape, with the art they join opaque around them; image 2 their art as it stands. A single panel lying
    turned is sent upright, and what it joins turned with it. Its reply is settled: nothing is kept outside the
    transparent shape; the ground toned ($0, ground_tone); each open face cut upright with its bleed. The plain areas the
    words stand in are named (``plain``: {face: box in its upright frame, mm}; by default those image 2 shows). Restartable:
    a saved reply is never bought twice. Returns the record."""
    folder = wrap_folder(ctx.root, key, n)
    record_path = folder / 'record.json'
    if record_path.exists():
        return _checked_wrap(record_path)
    folder.mkdir(parents=True, exist_ok=True)
    canvas = wrap_canvas(layout, open_, context_mm=WRAP_CONTEXT_MM if len(open_) == 1 else 0.0)
    masks = wrap_masks(layout, canvas)
    indices = [masks['names'].index(name) + 1 for name in open_]
    hole = np.isin(masks['owner'], indices)
    # a panel's bleed runs over any neighbour that is not on this canvas as art: it is painted, never left white
    around = Image.new('L', tuple(canvas['canvas_px']), 0)
    for name in open_:
        ImageDraw.Draw(around).polygon([_wrap_px(canvas, x, y) for x, y in _rings(
            layout['panels'][name]['poly'].buffer(layout['bleed'], join_style=2))[0]], fill=255)
    given = np.zeros_like(hole) if context is None else masks['paint'] & ~hole & np.isin(
        masks['owner'], [masks['names'].index(name) + 1 for name in context])
    hole = hole | ((np.asarray(around) > 0) & ~given)
    art = wrap_picture(layout, canvas, context or {}) if context else None
    painted = np.full(hole.shape + (3,), 255, np.uint8)
    if art is not None:
        painted[given] = art[given]
    view = (4 - layout['panels'][open_[0]]['q']) % 4 if len(open_) == 1 else 0     # a turned panel is sent upright
    sheet = np.dstack([painted, np.where(hole, 0, 255).astype(np.uint8)])
    Image.fromarray(turn(sheet, view), 'RGBA').save(folder / 'template.png')
    reference = wrap_picture(layout, canvas, pictures)
    if ground_hex:
        for index in indices:                       # each panel's art to the one ground, so image 2 already shows it
            mine = (masks['owner'] == index) & (reference.min(axis=2) < 235)
            if mine.any():
                reference, _tone = ground_tone(reference, mine, ground_hex)
    Image.fromarray(turn(reference, view)).save(folder / 'reference.png')
    if plain is None:
        plain = {}
        for name in open_:
            x0, y0, x1, y1 = _frame_box(layout, canvas, name)
            up = turn(reference[y0:y1, x0:x1], (4 - layout['panels'][name]['q']) % 4)
            found = plain_box(np.asarray(Image.fromarray(up).convert('L')).astype(np.float32), up.min(axis=2) < 235,
                              canvas['px_per_mm'])
            if FLAT_WORDS.get(name) in ('band', 'frame') and is_word_place(found, layout['panels'][name]):
                plain[name] = found
    words = wrap_prompt(layout, canvas, open_, ground_hex=ground_hex, ground_name=ground_name, keep=keep, rules=rules,
                        note=note, view=view, plain=plain)
    w, h = turn(sheet, view).shape[1::-1]
    call = ctx.face_edit('wrap/%s/%d' % (key, n), words, folder / 'call', template=folder / 'template.png',
                         references=[folder / 'reference.png'], size='%dx%d' % (w, h), quality=quality)
    with Image.open(folder / 'call' / 'raw.png') as image:
        raw = turn(np.asarray(image.convert('RGB')), (4 - view) % 4)
    settled, tone = (ground_tone(raw, hole, ground_hex) if ground_hex else (raw, {'toned': False}))
    canvas_art = np.full(hole.shape + (3,), 255, np.uint8)
    canvas_art[hole] = settled[hole]
    if art is not None:
        canvas_art[given] = art[given]
    Image.fromarray(canvas_art).save(folder / 'wrap.png')
    out = {}
    for name in open_:
        place, b = layout['panels'][name], layout['bleed']
        x0, y0, x1, y1 = _frame_box(layout, canvas, name)
        upright = turn(canvas_art[y0:y1, x0:x1], (4 - place['q']) % 4)
        reference_face = turn(reference[y0:y1, x0:x1], (4 - place['q']) % 4)
        Image.fromarray(upright).save(folder / (name + '.png'))
        Image.fromarray(reference_face).save(folder / (name + '.reference.png'))
        out[name] = {'face': str(folder / (name + '.png')), 'face_sha256': sha(folder / (name + '.png')),
                     'reference': str(folder / (name + '.reference.png')),
                     'reference_sha256': sha(folder / (name + '.reference.png')),
                     'frame_mm': [place['w'] + 2 * b, place['h'] + 2 * b]}
    record = {'schema': 'stand_wrap/1', 'key': key, 'n': n, 'open': list(open_), 'canvas': canvas, 'faces': out,
              'wrap': str(folder / 'wrap.png'), 'wrap_sha256': sha(folder / 'wrap.png'), 'tone': tone, 'prompt': words,
              'cost_usd': call.get('cost_usd'), 'reservation_id': call['reservation_id'], 'quality': quality,
              'rule': 'one edit on the panels joined as they fold; each face cut from it; the ground in its own pixels'}
    flow.write_json(record_path, record)
    return record


def _checked_wrap(record_path):
    record = json.loads(Path(record_path).read_text())
    if sha(record['wrap']) != record['wrap_sha256']:
        raise ValueError('A wrap changed after it was painted: ' + str(record_path))
    return record


def current_wrap(root, attempt):
    """The stand's wrap of a claim's attempt, or None while it is not painted."""
    path = wrap_folder(root, 'stand', attempt) / 'record.json'
    return _checked_wrap(path) if path.exists() else None


def wrap_face(root, key, n, wrap, outline):
    """Drawing ``n`` of a stand face, cut from a wrap: nothing is drawn again ($0). ``outline``: its printed shape,
    upright, no bleed."""
    folder = drawing_folder(root, key, n)
    record_path = folder / 'record.json'
    if record_path.exists():
        return _checked(record_path, 'face')
    folder.mkdir(parents=True, exist_ok=True)
    cut = wrap['faces'][key]
    with Image.open(cut['face']) as image:
        rgb = image.convert('RGB')
    rgb.save(folder / 'face.png')
    k = rgb.width / cut['frame_mm'][0]
    hole = Image.new('L', rgb.size, 0)
    for ring in _rings(outline.buffer(STAND_BLEED_MM, join_style=2)):
        ImageDraw.Draw(hole).polygon([((x + STAND_BLEED_MM) * k, (y + STAND_BLEED_MM) * k) for x, y in ring], fill=255)
    sheet = Image.new('RGBA', rgb.size, (255, 255, 255, 255))
    sheet.paste((0, 0, 0, 0), mask=hole)
    sheet.save(folder / 'template.png')
    Image.open(cut['reference']).convert('RGB').save(folder / 'reference.png')
    template = {'size': '%dx%d' % rgb.size, 'frame_px': [0, 0, rgb.width, rgb.height], 'px_per_mm': round(k, 6),
                'frame_mm': cut['frame_mm'], 'template': str(folder / 'template.png'), 'native_ppi': round(k * 25.4, 1),
                'template_sha256': sha(folder / 'template.png')}
    record = {'key': key, 'n': n, 'label': FACES[key]['label'], 'source': 'wrap', 'face': str(folder / 'face.png'),
              'face_sha256': sha(folder / 'face.png'), 'template': template, 'native_ppi': template['native_ppi'],
              'reference': {'path': str(folder / 'reference.png'), 'sha256': sha(folder / 'reference.png'),
                            'source': 'wrap', 'detail': 'this face as it stood before the wrap'},
              'wrap': {'key': wrap['key'], 'n': wrap['n'], 'sha256': wrap['wrap_sha256']}, 'cost_usd': None,
              'rule': 'cut from the wrap along the die; nothing drawn again'}
    flow.write_json(record_path, record)
    return record


# --- the folded stand, from the front three-quarter (the owner, 2026-10-30: "so I can judge it as one object") ----------

def _project(point, eye, target, focal, centre):
    forward = np.subtract(target, eye) / np.linalg.norm(np.subtract(target, eye))
    right = np.cross(forward, (0, 0, 1.0))
    right = right / np.linalg.norm(right)
    up = np.cross(right, forward)
    rel = np.subtract(point, eye)
    depth = rel @ forward
    return centre[0] + focal * (rel @ right) / depth, centre[1] - focal * (rel @ up) / depth


def three_quarter_drawing(views, geometry, folder, ground_hex=None):
    """The stand folded and empty, with its panels together: from the front three-quarter (the shopper's view: the
    header, the front strip and the right wall) and from behind (the back panel, the header back and a wall, where the
    wrap's bands turn the corners). Our own drawing from the flat faces, in perspective: not a render. ``views``: each
    stand face upright at its trim. Returns the record."""
    from . import product_drawing as pd
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    die = die_of(geometry)
    size = {}
    for key in FACES:
        if stand_face(key):
            _part, poly = die_face(die, FACES[key]['die'])
            size[key] = face_mm_size(poly, FACES[key]['quarters'])
    W, D = size['back'][0], size['side'][0]
    wall, base = size['back'][1], size['front'][1]
    top = wall + size['header_back'][1]
    # each face's corners in space: its picture's top-left, top-right, bottom-right, bottom-left
    planes = {
        'front': [(0, 0, base), (W, 0, base), (W, 0, 0), (0, 0, 0)],
        'side': [(W, 0, wall), (W, D, wall), (W, D, 0), (W, 0, 0)],
        'left': [(0, D, wall), (0, 0, wall), (0, 0, 0), (0, D, 0)],
        'back': [(W, D, wall), (0, D, wall), (0, D, 0), (W, D, 0)],
        'header_back': [(W, D, top), (0, D, top), (0, D, wall), (W, D, wall)],
        'header': [(0, D - .5, top), (W, D - .5, top), (W, D - .5, top - size['header'][1]), (0, D - .5, top - size['header'][1])],
    }
    shades = {'back': inside_board(die, ground_hex, (226, 218, 204)), 'header_back': (226, 218, 204), 'left': (205, 197, 183), 'floor': (186, 178, 165), 'side': (205, 197, 183),
              'front': inside_board(die, ground_hex, (205, 197, 183))}
    scenes = (('front three-quarter', (W + 170, -270, top + 45), ('back', 'header_back', 'left', 'floor', 'header', 'front', 'side')),
              ('from behind', (W + 190, D + 270, top + 60), ('front', 'left', 'floor', 'side', 'back', 'header_back')))
    pictures = []
    for name, eye, order in scenes:
        S = 1100
        target, canvas = (W / 2, D / 2, top * .47), np.full((S, S, 3), np.array(pd.SHEET, np.uint8), np.uint8)
        # the whole stand in the frame, whatever its height: the scale and the centre from its own corners
        seen = np.array([_project(p, eye, target, 1.0, (0.0, 0.0)) for name_ in order if name_ != 'floor' for p in planes[name_]])
        low, high = seen.min(axis=0), seen.max(axis=0)
        focal = (S - 80) / float(max(high - low))
        centre = (S / 2 - focal * (low[0] + high[0]) / 2, S / 2 - focal * (low[1] + high[1]) / 2)
        for part in order:
            if part == 'floor':
                corners = [_project(p, eye, target, focal, centre) for p in ((0, 0, 0), (W, 0, 0), (W, D, 0), (0, D, 0))]
                cv2.fillPoly(canvas, [np.int32(np.round(corners))], shades['floor'])
                continue
            corners = [_project(p, eye, target, focal, centre) for p in planes[part]]
            facing = (corners[1][0] - corners[0][0]) * (corners[3][1] - corners[0][1]) - \
                     (corners[1][1] - corners[0][1]) * (corners[3][0] - corners[0][0])
            with Image.open(views[part]) as image:
                art = np.asarray(image.convert('RGB'))
            h, w = art.shape[:2]
            _part, poly = die_face(die, FACES[part]['die'])
            fw, fh = size[part]
            mask = Image.new('L', (w, h), 0)
            ImageDraw.Draw(mask).polygon([((x - STAND_BLEED_MM) * w / fw, (y - STAND_BLEED_MM) * h / fh) for x, y in
                                          upright_polygon(poly, FACES[part]['quarters'], fw, fh).exterior.coords], fill=255)
            if facing <= 0:             # we see its inside: the unprinted board
                art = np.full_like(art, shades[part])
            matrix = cv2.getPerspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]), np.float32(corners))
            warped = cv2.warpPerspective(art, matrix, (S, S), flags=cv2.INTER_AREA)
            held = cv2.warpPerspective(np.asarray(mask), matrix, (S, S), flags=cv2.INTER_LINEAR)[..., None] / 255.0
            canvas = np.round(canvas * (1 - held) + warped * held).astype(np.uint8)
        pictures.append((name, Image.fromarray(canvas)))
    sheet = Image.new('RGB', (2 * 1100 + 60, 1100 + 60), pd.SHEET)
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 8), 'The stand folded, empty, its panels together: ' + pd.LABEL, fill=pd.EDGE_INK)
    for index, (name, picture) in enumerate(pictures):
        sheet.paste(picture, (20 + index * 1120, 30))
        draw.text((20 + index * 1120, 1135), name, fill=pd.EDGE_INK)
    path = folder / 'stand-three-quarter.png'
    sheet.save(path)
    return {'schema': 'stand_three_quarter/1', 'views': [name for name, _picture in pictures], 'file': str(path),
            'sha256': sha(path)}


# --- the artwork made of separate pieces (the owner, 2026-10-30, part 1B: every round, every product, every die) --------
# A face is a placement record: one flat ground, its motifs each its own object, its words in their quiet zones. The same
# record drives the preview, the print file and the drawings. Motifs are made on their own: a vector the engine draws, or
# a picture the image model paints alone on a plain ground, cut out here, never from a painted scene and never traced.
# Back from the archive (the consolidation of 2026-10-28 dropped them from the chain): truthful_concept's contrast and
# measured "no text over the device", lid_devices' keep-out region and intrusions, orn_a2's press limits, flat_motif's key.

PIECE_MARGIN_MM = 1.2           # a motif keeps this far from a cut line
ROW_MIN_MM = 16.0               # a register's least height
BLOOM_SHARE = 0.8               # a bloom's share of the pitch: the rest is its sprigs and small flowers
SPRIG_MAX_MM = 11.0             # a sprig's height: a taller column takes two, one over the other
BLOOM_MIN_MM = 8.0              # under this a picture motif is only specks: its place goes to sprigs
SPRIG_PITCH_MM = 3.8
BAND_MM = 2.8                   # a band's height
BAND_PITCH_MM = 5.6             # a band's repeat before it is fitted to whole units between its ends
BLOOM_PITCH_MM = 25.0           # the blooms' pitch where the design's own cannot be measured
QUIET_CONTRAST = 4.5            # words against what is under them (truthful_concept.fix_contrast's small-type bar)
FOIL_LINE_MIN_MM, FOIL_GAP_MIN_MM, RELIEF_MIN_MM = 0.1, 0.2, 0.3      # the press's limits (D-D9-3; orn_a2)
PICTURE_MIN_PPI = 300.0
LOGO_ASPECT = 1379.315316 / 287.712086                                # the approved mark's own viewBox
#: the sheet the picture motifs are painted on: one call, cut apart here. A large cell for the hero, four cells by three
#: for the registers; opaque ground between them, so each motif stands alone by construction
SHEET_SIZE = (1536, 1024)
SHEET_HERO = (24, 256, 536, 768)
SHEET_GRID = (560, 24, 1512, 1000, 4, 3)
#: where the words of each face stand: the engine's own zones, reserved before any motif is placed
WORD_FACES = dict(FLAT_WORDS)
#: every picture motif a face may use; a figure (the hero) only where the design names it (its header: "with no doe" behind)
HERO_FACES = ('header',)
CLEAR_FACES = ('bottle',)
OWN_GOLD_FACES = ('cap',)
#: which edges of a stand face are folds or the same board: bands and vines run flush to these, and stop short of the rest
STAND_FLUSH = {'side': ('left', 'right'), 'back': ('left', 'right'), 'left': ('left', 'right'), 'front': ('left', 'right'),
               'header_back': (), 'header': ()}


def _lum(hex_value):
    """WCAG relative luminance (as truthful_concept.contrast)."""
    out = []
    for i in (1, 3, 5):
        c = int(hex_value[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast_ratio(a, b):
    high, low = sorted((_lum(a), _lum(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def word_colour(grounds, palette):
    """The first of the design's own colours that reads at QUIET_CONTRAST on every ground under the words
    (truthful_concept.fix_contrast); none does, the darker of ink or paper that does."""
    for colour in palette:
        if all(contrast_ratio(colour, ground) >= QUIET_CONTRAST for ground in grounds):
            return colour
    return max(('#101010', '#FFFFFF'), key=lambda ink: min(contrast_ratio(ink, ground) for ground in grounds))


def design_colours(record, fallback_ground='#1F3A33'):
    """The design's colours by what they do: its ground, line colour and foil from the picked board's palette (by the
    words of their roles), the rest as accents."""
    path = flow.round_root(record) / 'board-pick.json'
    palette = json.loads(path.read_text()).get('board', {}).get('palette', []) if path.exists() else []
    def named(*words):
        for colour in palette:
            if any(word in str(colour.get('role', '')).lower() for word in words):
                return colour['hex']
        return None
    ground = named('ground') or fallback_ground
    line = named('thread', 'stem', 'border', 'stitch', 'accent') or '#B88A3E'
    foil = named('metallic', 'foil', 'gold') or '#C4A04C'
    return {'ground': ground, 'line': line, 'foil': foil,
            'words': [colour['hex'] for colour in palette if colour['hex'] not in (ground, line)] or [foil, '#E8DCC2']}


def _mix(a, b, share):
    return '#%02X%02X%02X' % tuple(int(round(int(a[i:i + 2], 16) * (1 - share) + int(b[i:i + 2], 16) * share)) for i in (1, 3, 5))


# a further shade: proposed by rule, picked by the owner ----------------------------------------------------------------------

#: the colours a further shade is proposed from: named by us, each its own hex; a rule picks among them, no model. No name carries a banned motif.
SHADE_TABLE = (('Pomegranate Silk', '#A12C3C'), ('Madder Root', '#A63A3F'), ('Mulberry Velvet', '#7B2D4E'), ('Orchid Thread', '#A8597F'),
               ('Wine Damask', '#6B1F33'), ('Garnet Thread', '#7E1F2F'), ('Coral Silk', '#D9735F'), ('Copper Thread', '#B06A3B'),
               ('Cinnamon Bark', '#8F4E33'), ('Almond Wool', '#C48F78'), ('Apricot Wool', '#DE9A6B'), ('Peony Dusk', '#D4848F'),
               ('Brick Madder', '#9C3B2E'), ('Plum Thread', '#5E2A45'), ('Cherry Lacquer', '#A3242F'), ('Terracotta Clay', '#B5523B'))
SHADE_APART_DE = 10.0           # at least this far (ΔE00) from every shade of the family, so a shopper tells them apart
SHADE_FAMILY_DE = 45.0          # and no further from its nearest than this, so it still belongs
SHADE_EACH_OTHER_DE = 10.0      # the proposals differ from each other, or it is no choice


def _lab_chroma_hue(hex_value):
    _l, a, b = _hex_lab(hex_value)
    return float(math.hypot(a, b)), float(math.degrees(math.atan2(b, a)) % 360)


def shade_candidates(family, ground_hex, *, count=3, table=SHADE_TABLE):
    """A further shade for a family: what stands far enough from each of its shades to be told apart, close enough to belong, at its lightness
    and chroma, and readable on the design's ground. Rule-based and deterministic: ranked by the room it finds (its distance from its nearest
    shade, capped) less how far it strays from the family's lightness, each next proposal apart from those before. Each with its reason in words."""
    labs = {shade['name']: _hex_lab(shade['hex']) for shade in family}
    lights = [lab[0] for lab in labs.values()]
    chromas = [_lab_chroma_hue(shade['hex'])[0] for shade in family]
    names = {shade['hex'].upper() for shade in family}
    rows = []
    for name, hex_value in table:
        if hex_value.upper() in names:
            continue
        lab = _hex_lab(hex_value)
        away = {other: float(delta_e00(np.array(lab), np.array(value))) for other, value in labs.items()}
        nearest = min(away, key=away.get)
        chroma = _lab_chroma_hue(hex_value)[0]
        stray = max(0.0, min(lights) - lab[0], lab[0] - max(lights))
        on_ground = contrast_ratio(hex_value, ground_hex)
        if away[nearest] < SHADE_APART_DE or away[nearest] > SHADE_FAMILY_DE or stray > 12.0 or chroma < .6 * min(chromas) or on_ground < 1.6:
            continue
        rows.append({'name': name, 'hex': hex_value, 'nearest': nearest, 'away_de': round(away[nearest], 1), 'light_off': round(float(stray), 1),
                     'on_ground': round(on_ground, 2), 'score': round(float(min(away[nearest], 25.0) - stray), 2)})
    rows.sort(key=lambda row: (-row['score'], row['name']))
    picked = []
    for row in rows:
        if all(delta_e00(np.array(_hex_lab(row['hex'])), np.array(_hex_lab(other['hex']))) >= SHADE_EACH_OTHER_DE for other in picked):
            picked.append(row)
        if len(picked) == count:
            break
    for row in picked:
        where = 'inside the family\'s lightness' if not row['light_off'] else '%.0f L past the family\'s lightness' % row['light_off']
        row['why'] = 'Told apart from its nearest, %s, at ΔE00 %.0f; %s; %.1f:1 on the ground.' % (row['nearest'], row['away_de'], where, row['on_ground'])
    return picked


def column_shades(shades, columns):
    """One shade per column, left to right, as the brief lists them, repeating if the columns outnumber them."""
    return [dict(shades[index % len(shades)], column=index + 1) for index in range(columns)] if shades else []


# the vector motifs: clean curves in the face's upright frame, never traced ------------------------------------------------

def _rect_path(x0, y0, x1, y1, fill):
    return {'d': [['M', x0, y0], ['L', x1, y0], ['L', x1, y1], ['L', x0, y1], ['Z']], 'fill': fill}


def _circle_d(cx, cy, r):
    k = 0.5522847 * r
    return [['M', cx + r, cy], ['C', cx + r, cy + k, cx + k, cy + r, cx, cy + r], ['C', cx - k, cy + r, cx - r, cy + k, cx - r, cy],
            ['C', cx - r, cy - k, cx - k, cy - r, cx, cy - r], ['C', cx + k, cy - r, cx + r, cy - k, cx + r, cy], ['Z']]


def _leaf_d(x, y, length, width, angle):
    """A leaf from (x, y) along ``angle`` (radians): two curves, closed."""
    c, s = math.cos(angle), math.sin(angle)
    at = lambda u, v: (x + u * c - v * s, y + u * s + v * c)   # noqa: E731
    tip, a, b, d, e = at(length, 0), at(.3 * length, width / 2), at(.75 * length, width / 2), at(.75 * length, -width / 2), at(.3 * length, -width / 2)
    return [['M', x, y], ['C', *a, *b, *tip], ['C', *d, *e, x, y], ['Z']]


def small_flower(cx, cy, r, petal, heart, petals=5):
    """A geometric flower: its petals, leaf-shaped and closed, round its heart."""
    paths = [{'d': _leaf_d(cx, cy, r, r * .62, 2 * math.pi * i / petals - math.pi / 2), 'fill': petal} for i in range(petals)]
    paths.append({'d': _circle_d(cx, cy, r * .24), 'fill': heart})
    return paths


def rosette(cx, cy, r, stroke, width_mm, folds=12):
    """A guilloché rosette: a ring of circles round a centre, and its bounding ring."""
    paths = [{'d': _circle_d(cx + r * .5 * math.cos(2 * math.pi * i / folds), cy + r * .5 * math.sin(2 * math.pi * i / folds), r * .5),
              'stroke': stroke, 'stroke_mm': width_mm} for i in range(folds)]
    paths.append({'d': _circle_d(cx, cy, r), 'stroke': stroke, 'stroke_mm': width_mm})
    return paths


def woven_band(x0, x1, y, height, line, accent):
    """A band between (x0, y) and (x1, y + height): its two rules and a lattice of whole diamonds, fitted so each end is a
    whole unit's edge. Two panels meeting at a fold each draw theirs whole to it: a matched pair from one vector."""
    units = max(1, int(round((x1 - x0) / BAND_PITCH_MM)))
    pitch = (x1 - x0) / units
    rule = 0.28
    paths = [_rect_path(x0, y, x1, y + rule, line), _rect_path(x0, y + height - rule, x1, y + height, line)]
    mid, half = y + height / 2, height / 2 - rule - 0.2
    for i in range(units):
        cx = x0 + (i + .5) * pitch
        w = pitch / 2 - .2
        paths.append({'d': [['M', cx - w, mid], ['L', cx, mid - half], ['L', cx + w, mid], ['L', cx, mid + half], ['Z']],
                      'stroke': accent, 'stroke_mm': 0.22})
        paths.append({'d': _circle_d(cx, mid, 0.34), 'fill': accent})
    return paths


def vine_run(x0, x1, y, amp, stem, leaf):
    """A vine along a row between x0 and x1: whole half-waves, its ends level at ``y`` so a neighbour's run meets it; a leaf
    on each crest."""
    if x1 - x0 < 2.0:
        return []
    halves = max(1, int(round((x1 - x0) / 7.0)))
    step = (x1 - x0) / halves
    d = [['M', x0, y]]
    paths = []
    for i in range(halves):
        a, b, sign = x0 + i * step, x0 + (i + 1) * step, 1 if i % 2 else -1
        d.append(['C', a + step / 3, y + sign * amp * 1.33, b - step / 3, y + sign * amp * 1.33, b, y])
        if step > 2.5:
            paths.append({'d': _leaf_d((a + b) / 2, y + sign * amp, min(step * .55, 3.4), 1.3, sign * math.pi / 2 - .5), 'fill': leaf})
    return [{'d': d, 'stroke': stem, 'stroke_mm': 0.3}] + paths


def sprig(x, y0, y1, stem, leaf, petal, heart, *, sign=1):
    """A sprig rising from (x, y1) to (x, y0): a curved stem, a leaf either side at each node, a small flower at its tip."""
    h = y1 - y0
    wob = min(h * .16, .7)
    d = [['M', x, y1], ['C', x + sign * wob, y1 - h * .33, x - sign * wob, y1 - h * .66, x, y0 + 1.2]]
    paths = [{'d': d, 'stroke': stem, 'stroke_mm': 0.26}]
    nodes = max(1, int((h - 2) / 3.0))
    for i in range(nodes):
        t = (i + .5) / nodes
        cy = y1 - t * (h - 1.2)
        for side in (-1, 1):
            paths.append({'d': _leaf_d(x, cy, 1.5, .8, (0 if side > 0 else math.pi) - side * .75), 'fill': leaf})
    paths += small_flower(x, y0 + 1.1, 1.1, petal, heart)
    return paths


def double_frame(box, stroke, width_mm, gap_mm=0.7):
    x0, y0, x1, y1 = box
    ring = lambda a: [['M', x0 + a, y0 + a], ['L', x1 - a, y0 + a], ['L', x1 - a, y1 - a], ['L', x0 + a, y1 - a], ['Z']]  # noqa: E731
    return [{'d': ring(0), 'stroke': stroke, 'stroke_mm': width_mm}, {'d': ring(gap_mm), 'stroke': stroke, 'stroke_mm': width_mm * .7}]


def _paths_box(paths):
    xs, ys = [], []
    for path in paths:
        pad = path.get('stroke_mm', 0) / 2 if path.get('stroke') else 0
        for op in path['d']:
            coords = op[1:]
            xs.extend(v + s * pad for v in coords[0::2] for s in (-1, 1))
            ys.extend(v + s * pad for v in coords[1::2] for s in (-1, 1))
    return [min(xs), min(ys), max(xs), max(ys)]


# the picture motifs: painted alone, cut out here ---------------------------------------------------------------------------

def motifs_root(root):
    return Path(root) / 'motifs'


def sheet_cells():
    """The sheet's cells: the hero's, then each register's, top to bottom."""
    x0, y0, x1, y1, cols, rows = SHEET_GRID
    gutter = 24
    w, h = (x1 - x0 - gutter * (cols - 1)) / cols, (y1 - y0 - gutter * (rows - 1)) / rows
    cells = [{'id': 'hero', 'register': None, 'box': list(SHEET_HERO)}]
    for r in range(rows):
        for c in range(cols):
            left, top = x0 + c * (w + gutter), y0 + r * (h + gutter)
            cells.append({'id': 'bloom %02d' % (r * cols + c + 1), 'register': r,
                          'box': [int(left), int(top), int(left + w), int(top + h)]})
    return cells


def sheet_template(ground_hex, folder):
    """Image 1: the design's ground, opaque, with each cell transparent."""
    W, H = SHEET_SIZE
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., :3] = [int(ground_hex[i:i + 2], 16) for i in (1, 3, 5)]
    rgba[..., 3] = 255
    for cell in sheet_cells():
        x0, y0, x1, y1 = cell['box']
        rgba[y0:y1, x0:x1, 3] = 0
    Image.fromarray(rgba, 'RGBA').save(Path(folder) / 'template.png')
    return Path(folder) / 'template.png'


def sheet_prompt(*, ground_hex, ground_name, hero_words, composition, rules='', note=''):
    x0, y0, x1, y1 = SHEET_HERO
    words = ['Image 1 is a sheet of plain %s%s with %d TRANSPARENT cells. In each transparent cell paint exactly ONE motif, '
             'alone and whole, centred, its whole outline inside the cell and well clear of the cell\'s edges, on that same '
             'perfectly plain flat %s: no pattern behind it, no texture, no vignette, no frame, no border, no shadow, nothing '
             'else in the cell.' % (ground_name + ' ' if ground_name else '', ground_hex, len(sheet_cells()), ground_hex),
             'The large cell (x %d–%d, y %d–%d px) holds the design\'s hero: %s, seen from the side, on its own, no medallion '
             'and no ground under its feet.' % (x0, x1, y0, y1, hero_words),
             'The %d small cells stand in %d rows. Each row is one of the design\'s registers from the top down, and each cell '
             'in it a different drawing of that register\'s bloom or fruit. The design says: "%s"'
             % (SHEET_GRID[4] * SHEET_GRID[5], SHEET_GRID[5], composition),
             'Image 2 shows the design as it stands: take the woven, embroidered drawing, the thread, the colours and the '
             'richness of its motifs from it, one motif at a time. Never copy its layout, its bands or its background.']
    if rules:
        words.append(rules)
    words.append(FLAT_NO_WORDS)
    if note:
        words.append(NOTE_LAST % note)
    return '\n\n'.join(words)


CUT_DE = (9.0, 17.0)            # no ink within ΔE00 9 of the plain ground, all ink past 17 (flat_motif's key, softened)
CUT_MIN_SHARE = 0.03            # a cell with less of its area inked is empty, and dropped
CUT_EDGE_SHARE = 0.01           # a mask with more of its pixels on the cell's edge ran out of it, and is dropped


def cut_cell(rgb, ground_lab):
    """One cell's motif cut out on the plain ground: an alpha from its distance to the ground, its loose specks dropped, the
    ground unmixed from its soft edge so no ground-coloured fringe rides with it. Returns (RGBA, ink share, edge share)."""
    from scipy import ndimage
    h, w = rgb.shape[:2]
    lab = srgb_to_lab(rgb.astype(np.float64)).reshape(-1, 3)
    away = delta_e00(lab, np.broadcast_to(ground_lab, lab.shape)).reshape(h, w)
    alpha = np.clip((away - CUT_DE[0]) / (CUT_DE[1] - CUT_DE[0]), 0, 1)
    labels, count = ndimage.label(alpha > 0.5)
    if not count:
        return None, 0.0, 0.0
    sizes = ndimage.sum(np.ones_like(labels), labels, range(1, count + 1))
    keep = np.isin(labels, [i + 1 for i, size in enumerate(sizes) if size >= max(40, 0.01 * sizes.max())])
    alpha = alpha * ndimage.binary_dilation(keep, iterations=2)
    edge = np.zeros((h, w), bool)
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
    ink = alpha > 0.5
    ground_rgb = cv2.cvtColor(np.float32(np.reshape(ground_lab, (1, 1, 3))), cv2.COLOR_LAB2RGB)[0, 0] * 255
    a = np.maximum(alpha[..., None], 1e-3)
    unmixed = np.clip((rgb.astype(np.float64) - (1 - a) * ground_rgb) / a, 0, 255)
    return (np.dstack([np.round(unmixed).astype(np.uint8), np.round(alpha * 255).astype(np.uint8)]),
            float(ink.mean()), float((ink & edge).sum() / max(ink.sum(), 1)))


def cut_sheet(raw_path, folder, *, hero_name='hero'):
    """The sheet cut apart: each cell's motif on its own (a PNG with its mask), its size at 300 PPI, its colours and hash;
    a cell that is empty or ran out of its edges dropped and listed. The ground is read from the sheet's own gutters."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    with Image.open(raw_path) as image:
        rgb = np.asarray(image.convert('RGB'))
    gutter = np.ones(rgb.shape[:2], bool)
    for cell in sheet_cells():
        x0, y0, x1, y1 = cell['box']
        gutter[max(0, y0 - 2):y1 + 2, max(0, x0 - 2):x1 + 2] = False
    ground = np.median(srgb_to_lab(rgb[gutter].astype(np.float64)), axis=0)
    kept, dropped = [], []
    for cell in sheet_cells():
        x0, y0, x1, y1 = cell['box']
        cut, share, on_edge = cut_cell(rgb[y0:y1, x0:x1], ground)
        if cut is None or share < CUT_MIN_SHARE:
            dropped.append({'id': cell['id'], 'why': 'its cell is empty'})
            continue
        if on_edge > CUT_EDGE_SHARE:
            dropped.append({'id': cell['id'], 'why': 'it ran out of its cell (%.1f %% of its ink on the edge)' % (100 * on_edge)})
            continue
        ys, xs = np.nonzero(cut[..., 3] > 16)
        crop = cut[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        name = cell['id'].replace(' ', '-') + '.png'
        Image.fromarray(crop, 'RGBA').save(folder / name)
        solid = crop[crop[..., 3] > 200][:, :3]
        kept.append({'id': cell['id'], 'kind': 'picture', 'hero': cell['id'] == 'hero', 'name': hero_name if cell['id'] == 'hero' else cell['id'],
                     'register': cell['register'], 'file': str(folder / name), 'sha256': sha(folder / name), 'px': [crop.shape[1], crop.shape[0]],
                     'max_mm': [round(crop.shape[1] / K, 2), round(crop.shape[0] / K, 2)], 'ink_share': round(share, 3),
                     'colours': ['#%02X%02X%02X' % tuple(int(v) for v in np.median(solid, axis=0))] if len(solid) else [],
                     'mask': 'its alpha'})
    return {'schema': 'motif_library/1', 'ground_lab': [round(float(v), 2) for v in ground], 'pictures': kept, 'dropped': dropped}


# placement by rules ---------------------------------------------------------------------------------------------------------

def _spans(geom, y):
    """Where a horizontal line at ``y`` lies inside ``geom``: [(x0, x1)]."""
    from shapely.geometry import LineString
    x0, _a, x1, _b = geom.bounds
    cut = geom.intersection(LineString([(x0 - 1, y), (x1 + 1, y)]))
    parts = getattr(cut, 'geoms', [cut])
    return sorted((min(p.coords[0][0], p.coords[-1][0]), max(p.coords[0][0], p.coords[-1][0])) for p in parts
                  if p.geom_type == 'LineString' and p.length > 1e-6)


def _vspans(geom, x):
    """Where a vertical line at ``x`` lies inside ``geom``: [(y0, y1)]."""
    from shapely.geometry import LineString
    _a, y0, _b, y1 = geom.bounds
    cut = geom.intersection(LineString([(x, y0 - 1), (x, y1 + 1)]))
    return sorted((min(p.coords[0][1], p.coords[-1][1]), max(p.coords[0][1], p.coords[-1][1])) for p in getattr(cut, 'geoms', [cut])
                  if p.geom_type == 'LineString' and p.length > 1e-6)


def _both(a, b):
    out = []
    for p in a:
        for q in b:
            lo, hi = max(p[0], q[0]), min(p[1], q[1])
            if hi > lo:
                out.append((lo, hi))
    return out


def _word_block(key, brief, face, colours):
    """The words of a face: their rows and logos, and their quiet zones (the logo's height on every side, a line's cap height
    for words), reserved first. Everything else is placed in what is left."""
    from .round_files_export import glyph_metrics
    how = WORD_FACES.get(key)
    out = {'type': [], 'logos': [], 'zones': [], 'keep': [], 'contrast': []}
    if how is None:
        return out
    fields = copy_fields(brief)
    t = trim_box(face)
    w, h, cx = t[2] - t[0], t[3] - t[1], (t[0] + t[2]) / 2
    ground = colours['ground']
    colour = word_colour([ground], [colours['foil']] + colours['words'])
    if how == 'band':                     # the header: the logo alone, on its quiet band at the foot, the hero above it
        logo_h = min(0.11 * h, 6.5)
        logo_w = logo_h * LOGO_ASPECT
        y1 = t[3] - logo_h - 1.0
        box = [cx - logo_w / 2, y1 - logo_h, cx + logo_w / 2, y1]
        out['logos'].append({'box_mm': box, 'rotation': 0, 'foil': True, 'name': key + ' / logo (approved vector)'})
        out['zones'].append({'name': 'logo', 'box': [box[0] - logo_h, box[1] - logo_h, box[2] + logo_h, box[3] + logo_h]})
        out['contrast'].append({'what': 'logo', 'colour': colours['foil'], 'on': ground})
    elif how == 'centre':                 # the front strip: the logo over its line, centred
        logo_h = min(0.22 * h, 5.0)
        logo_w = logo_h * LOGO_ASPECT
        cap = max(0.11 * h, 2.0)
        top = t[1] + (h - logo_h - cap - 1.6) / 2
        box = [cx - logo_w / 2, top, cx + logo_w / 2, top + logo_h]
        out['logos'].append({'box_mm': box, 'rotation': 0, 'foil': True, 'name': key + ' / logo (approved vector)'})
        out['type'] = product_line(fields, cx, top + logo_h + 1.6 + cap / 2, cap, w, colour=colour, foil=False, name=key)
        out['zones'].append({'name': 'logo and line', 'box': [box[0] - logo_h, max(t[1], box[1] - logo_h), box[2] + logo_h,
                                                             min(t[3], top + logo_h + 1.6 + cap + logo_h)]})
        out['contrast'] += [{'what': 'logo', 'colour': colours['foil'], 'on': ground}, {'what': 'line', 'colour': colour, 'on': ground}]
    elif how == 'frame':                  # the right wall: the line, in its own frame, in the wall's middle register
        cap = 2.6
        metric = glyph_metrics(fields['product_latin'], 'latin')
        size = cap / max(metric['box_em'][3] - metric['box_em'][1], .1)
        span = metric['advance_em'] * size
        cx, cy = t[0] + 0.62 * w, t[3] - 0.33 * h
        out['type'] = product_line(fields, cx, cy, cap, w, colour=colour, foil=False, name=key)
        box = [cx - span / 2 - cap, cy - cap / 2 - cap, cx + span / 2 + cap, cy + cap / 2 + cap]
        out['zones'].append({'name': 'line', 'box': box})
        out['frames'] = [box]
        out['contrast'].append({'what': 'line', 'colour': colour, 'on': ground})
    else:                                  # the bottle: along its length, in its open window, over the liquid
        window = [t[0] + .18 * w, t[1] + .2 * h, t[2] - .18 * w, t[3] - .2 * h]
        shades = [shade['hex'] for shade in brief.get('shades', [])][:1] or ['#C9707A']     # the file's own shade
        ink = word_colour(shades, [colours['ground']] + colours['words'])
        x0, y0, x1, y1 = window[0] + .6, window[1] + 1, window[2] - .6, window[3] - 1
        ww, hh, mx = x1 - x0, y1 - y0, (x0 + x1) / 2
        band = lambda a, b: [mx - 0.35 * ww, y0 + a * hh, mx + 0.35 * ww, y0 + b * hh]   # noqa: E731
        out['logos'].append({'box_mm': band(0.04, 0.40), 'rotation': 90, 'foil': False, 'name': key + ' / logo (approved vector)'})
        out['type'] = [dict(_flat_row(key, 'product_latin', fields['product_latin'], band(0.47, 0.70), 90, False), color=ink)]
        if 'shade_0' in fields:
            out['type'].append(dict(_flat_row(key, 'shade_0', fields['shade_0'], band(0.76, 0.94), 90, False), color=ink))
        out['zones'].append({'name': 'window', 'box': window})
        out['window'] = window
        out['contrast'] += [{'what': 'line on ' + shade, 'colour': ink, 'on': shade} for shade in shades]
    return out


def measure_rhythm(painting, geometry, face='back'):
    """The chosen design's rhythm, measured on its picked painting: the heights of its bands above the floor, and the pitch
    of its blooms (the first peak of its own row's self-likeness). Stated on the round; a painting with neither gives the
    plain defaults, said so."""
    out = {'source': 'measured on the picked design', 'face': face}
    try:
        upright, frame_mm, _box = painted_face(painting, face, geometry)
        k = upright.shape[1] / frame_mm[0]
        b = int(round(STAND_BLEED_MM * k))
        art = upright[b:-b, b:-b]
        light = srgb_to_lab(art.astype(np.float64).reshape(-1, 3))[:, 0].reshape(art.shape[:2]).mean(axis=1)
        samples = np.interp(np.arange(0, art.shape[0] / k, FOLD_STEP_MM), np.arange(art.shape[0]) / k, light)
        from scipy.ndimage import median_filter
        rise = samples - median_filter(samples, size=int(14 / FOLD_STEP_MM) | 1, mode='nearest')
        H = art.shape[0] / k
        middle = rise[int(6 / FOLD_STEP_MM):-int(6 / FOLD_STEP_MM)]          # its own edge is not one of its bands
        at = np.nonzero(rise > 0.6 * middle.max())[0]
        at = at[(at > 6 / FOLD_STEP_MM) & (at < rise.size - 6 / FOLD_STEP_MM)]
        groups = np.split(at, np.nonzero(np.diff(at) > 3 / FOLD_STEP_MM)[0] + 1) if at.size else []
        out['bands_mm'] = sorted(round(H - float(group.mean()) * FOLD_STEP_MM, 1) for group in groups)
        grey = art.mean(axis=2)
        grey = grey - grey.mean(axis=1, keepdims=True)
        seen = [np.correlate(row, row, 'full')[row.size - 1:] for row in grey[::max(1, grey.shape[0] // 40)]]
        auto = np.mean([s / max(s[0], 1e-6) for s in seen], axis=0)
        low, high = int(12 * k), min(int(50 * k), auto.size - 1)
        out['pitch_mm'] = round((low + int(np.argmax(auto[low:high]))) / k, 1) if high > low else None
    except Exception as exc:                    # a painting too small or plain to read: the defaults, in words
        out.update(bands_mm=[], pitch_mm=None, why=('%s: %s' % (type(exc).__name__, exc))[:200])
    return out


def stand_registers(face_h, floor_up, front_h, rhythm):
    """The bands' heights above the floor on a face of ``face_h``: from the measured rhythm, its lowest always where the front
    strip ends so one band runs round the whole stand; never closer than a row's room."""
    start = front_h - BAND_MM - 1.2 if front_h <= face_h else None
    measured = sorted(rhythm.get('bands_mm') or [])
    spacing = float(np.median(np.diff(measured))) if len(measured) > 1 else 27.0
    bands = [start] if start is not None else []
    base = (start + BAND_MM) if start is not None else 0.0
    room = face_h - base
    if room > ROW_MIN_MM:                       # the rest evenly, on the design's own spacing, so no row is left too tall
        rows = max(1, int(math.ceil(room / max(spacing, ROW_MIN_MM))))
        while rows > 1 and room / rows < ROW_MIN_MM:
            rows -= 1
        bands += [base + room * i / rows for i in range(1, rows)]
    return sorted(bands)


def _name(key, what):
    return '%s / %s' % (key, what)


def plan_face(key, n, brief, die, geometry, library, rhythm, colours, *, seed=0):
    """One face's placement record, by rules: the words and their quiet zones first, the hero where the design names it, the
    bands level, the blooms on the pitch, the vines and small flowers between, each its own named object in the face's upright
    frame. No motif crosses a fold, a cut line, the bleed edge or a quiet zone. Returns the record."""
    from shapely.geometry import box as bx
    from shapely.ops import unary_union
    face = face_geometry(key, brief, die)
    b = face['bleed_mm']
    W, H = face['w_mm'] + 2 * b, face['h_mm'] + 2 * b
    t = trim_box(face)
    outline = face['outline']
    words = _word_block(key, brief, face, colours)
    keep = [bx(*zone['box']) for zone in words['zones']]
    plan = {'schema': 'face_plan/1', 'key': key, 'n': n, 'seed': seed, 'frame_mm': [W, H], 'trim_mm': list(t),
            'colours': colours, 'ground': None, 'own_ground': None, 'motifs': [], 'finishes': [], 'words': words,
            'zones': words['zones'], 'rhythm': rhythm, 'overlaps': []}
    if key in CLEAR_FACES:
        plan['own_ground'] = OWN_GROUND['bottle']
    elif key in OWN_GOLD_FACES:
        plan['own_ground'] = OWN_GROUND['cap']
        plan['ground'] = {'hex': colours['foil']}
    else:
        plan['ground'] = {'hex': colours['ground']}
    line, ground = colours['line'], colours['ground']
    leaf = _mix(line, '#3F5A2A', .55)
    petal = _mix(colours['foil'], '#E8DCC2', .25)
    used = {'vector': 0, 'picture': 0}

    def add_vector(what, paths, kind='vector'):
        if paths:
            plan['motifs'].append({'kind': 'vector', 'panel': key, 'name': _name(key, what), 'paths': paths, 'box_mm': _paths_box(paths),
                                   'generator': kind})
            used['vector'] += 1

    def add_picture(what, piece, box, generator):
        plan['motifs'].append({'kind': 'picture', 'panel': key, 'name': _name(key, what), 'path': piece['file'], 'sha256': piece['sha256'],
                               'box_mm': [round(v, 3) for v in box], 'piece': piece['id'],
                               'ppi': round(min(piece['px'][0] / (box[2] - box[0]), piece['px'][1] / (box[3] - box[1])) * 25.4, 1),
                               'generator': generator})
        used['picture'] += 1

    if key in OWN_GOLD_FACES:                  # its own gold: engraved, relief lines only; a figure would need tracing
        cx, cy, r = (t[0] + t[2]) / 2, (t[1] + t[3]) / 2, min(t[2] - t[0], t[3] - t[1]) / 2 - 1.6
        engrave = _mix(colours['foil'], '#2A1E08', .75)
        plan['finishes'].append({'finish': 'relief', 'of': _name(key, 'rosette'), 'name': _name(key, 'rosette (relief)'),
                                 'paths': rosette(cx, cy, r, engrave, 0.32), 'panel': key})
        plan['finishes'].append({'finish': 'relief', 'of': _name(key, 'border'), 'name': _name(key, 'border (relief)'),
                                 'paths': double_frame([t[0] + .8, t[1] + .8, t[2] - .8, t[3] - .8], engrave, .45, 1.0), 'panel': key})
        return plan
    # a frame for the words that have one
    for i, zone_box in enumerate(words.get('frames', [])):
        x0, y0, x1, y1 = zone_box
        frame = [x0 - .9, y0 - .9, x1 + .9, y1 + .9]
        add_vector('word frame', double_frame(frame, line, .3, .5))
        keep.append(bx(*[frame[0] - 1, frame[1] - 1, frame[2] + 1, frame[3] + 1]))
    pictures = {r: [p for p in library.get('pictures', []) if p.get('register') == r] for r in range(SHEET_GRID[5])}
    hero = next((p for p in library.get('pictures', []) if p.get('hero')), None)
    if key in HERO_FACES and hero is not None:
        free = t[3] - t[1] - (t[3] - words['zones'][0]['box'][1] if words['zones'] else 0)
        side = min(free - 3.0, 0.5 * (t[2] - t[0]))
        cx, cy = (t[0] + t[2]) / 2, t[1] + free / 2 + .5
        frame = [cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2]
        inner = side - 3.0
        scale = min(inner / hero['px'][0], inner / hero['px'][1], 1 / K)
        hw, hh = hero['px'][0] * scale, hero['px'][1] * scale
        add_picture(hero['name'] + ' medallion', hero, [cx - hw / 2, cy - hh / 2, cx + hw / 2, cy + hh / 2], 'hero')
        plan['finishes'].append({'finish': 'foil', 'of': _name(key, hero['name'] + ' medallion'), 'panel': key,
                                 'name': 'foil / ' + _name(key, hero['name'] + ' medallion frame'),
                                 'paths': double_frame(frame, colours['foil'], .3, .6)})
        keep.append(bx(frame[0] - 1.2, frame[1] - 1.2, frame[2] + 1.2, frame[3] + 1.2))
    window = words.get('window')
    if window:
        keep.append(bx(window[0] - .3, window[1] - .3, window[2] + .3, window[3] + .3))
    allowed = outline.difference(unary_union(keep)) if keep else outline
    inner = outline.buffer(-PIECE_MARGIN_MM, join_style=2)
    room = inner.difference(unary_union(keep)) if keep else inner
    # the bands, level: heights from the floor on a wall; flush to a fold, short of a cut
    floor_y, top_y = t[3], t[1]
    face_h = t[3] - t[1]
    flush = STAND_FLUSH.get(key, ())
    if stand_face(key):
        front_h = face_geometry('front', brief, die)['h_mm']
        heights = stand_registers(face_h, 0, front_h, rhythm)
    else:
        heights = []
        if window:                             # the weave round the open window: a band at each of its ends, nothing opaque
            heights = [t[3] - window[3] - BAND_MM - .8, t[3] - window[1] + .8]
    band_rows = []
    for index, height in enumerate(heights, 1):
        y1 = floor_y - height
        y0 = y1 - BAND_MM
        if y0 < top_y + 1:
            continue
        for part, (a, c) in enumerate(_both(_spans(allowed, y0 + .01), _spans(allowed, y1 - .01)), 1):
            a = a if 'left' in flush and abs(a - t[0]) < 1e-6 else max(a + PIECE_MARGIN_MM, t[0])
            c = c if 'right' in flush and abs(c - t[2]) < 1e-6 else min(c - PIECE_MARGIN_MM, t[2])
            if c - a < 6:
                continue
            add_vector('band %d%s' % (index, '' if part == 1 else chr(96 + part)), woven_band(a, c, y0, BAND_MM, line, _mix(line, colours['foil'], .4)), 'woven band')
        band_rows.append((y0, y1))
    # the registers between them, each on the pitch
    edges = sorted({top_y, floor_y} | {v for row in band_rows for v in row})
    rows = [(edges[i], edges[i + 1]) for i in range(len(edges) - 1) if (edges[i], edges[i + 1]) not in band_rows]
    rows = [row for row in rows if row[1] - row[0] > 4]
    pitch = rhythm.get('pitch_mm') or BLOOM_PITCH_MM
    pitch = float(min(max(pitch, 16.0), 30.0))
    if t[2] - t[0] < 40:                       # a product face: its own small rhythm
        pitch = (t[2] - t[0]) * .9
    bloom_no, count = 0, 0
    registers = len([r for r in pictures if pictures[r]])
    for row_index, (y0, y1) in enumerate(sorted(rows, key=lambda row: -row[1])):
        # lowest row is the design's lowest register; the rows of the sheet read from the top down
        register = max(0, registers - 1 - min(row_index, registers - 1)) if registers else None
        pieces = pictures.get(register, []) if register is not None else []
        size = min(y1 - y0 - 2.4, pitch * BLOOM_SHARE)
        # column by column, so a sloping cut or a quiet zone closes only the columns it reaches
        strip = bx(t[0], y0 + .2, t[2], y1 - .2).intersection(room)
        if strip.is_empty:
            continue
        lo, hi = strip.bounds[0], strip.bounds[2]
        if hi - lo < 3:
            continue

        def column(x):
            parts = [part for part in _vspans(strip, x) if part[1] - part[0] >= 3.0]
            return max(parts, key=lambda part: part[1] - part[0], default=None)
        leafy = strip.buffer(-1.7, join_style=2)                # a sprig's leaves reach this far from its stem
        cells = max(1, int(round((hi - lo) / pitch)))
        step = (hi - lo) / cells
        taken = []
        for i in range(cells):
            centre = lo + (i + .5) * step
            at = column(centre)
            piece = pieces[(i + seed + row_index) % len(pieces)] if pieces else None
            if at is None or piece is None:
                continue
            scale = min(min(size, at[1] - at[0] - .6) / piece['px'][0], min(size, at[1] - at[0] - .6) / piece['px'][1], 1 / K)
            pw, ph = piece['px'][0] * scale, piece['px'][1] * scale
            cy = (at[0] + at[1]) / 2
            box = [centre - pw / 2, cy - ph / 2, centre + pw / 2, cy + ph / 2]
            if max(pw, ph) >= BLOOM_MIN_MM and room.contains(bx(*box)):
                bloom_no += 1
                add_picture('bloom %02d' % bloom_no, piece, box, 'bloom')
                taken.append(box)
        # a sprig in every free column between the blooms, its height the room there
        paths, x, tally = [], lo + 1.3, 0
        while x < hi - .6:
            hit = next((box for box in taken if box[0] - 1.2 < x < box[2] + 1.2), None)
            if hit is not None:
                x = hit[2] + 1.9
                if paths:
                    add_vector('sprigs %d.%d' % (row_index + 1, count), paths, 'sprig')
                    paths, count = [], count + 1
                continue
            parts = [part for part in _vspans(leafy, x) if part[1] - part[0] >= 3.0] if not leafy.is_empty else []
            at = max(parts, key=lambda part: part[1] - part[0], default=None)
            if at is not None and at[1] - at[0] >= 4.0:
                tiers = max(1, int(math.ceil((at[1] - at[0] - .4) / SPRIG_MAX_MM)))
                tall = (at[1] - at[0] - .4) / tiers
                for tier in range(tiers):
                    paths += sprig(x, at[0] + .2 + tier * tall, at[0] + .2 + (tier + 1) * tall, line, leaf,
                                   petal if (tally + tier) % 2 else colours['words'][-1], line, sign=1 if (tally + tier) % 2 else -1)
                tally += 1
            x += SPRIG_PITCH_MM
        if paths:
            add_vector('sprigs %d.%d' % (row_index + 1, count), paths, 'sprig')
            count += 1
    # a bottle's sides beside its window: a vine up each, nothing opaque
    if window:
        for side, x in (('left', (t[0] + window[0]) / 2), ('right', (window[2] + t[2]) / 2)):
            d = [['M', x, window[1] + 1]]
            n_w = int((window[3] - window[1] - 2) / 6) or 1
            step = (window[3] - window[1] - 2) / n_w
            for i in range(n_w):
                y = window[1] + 1 + i * step
                sign = 1 if i % 2 else -1
                d.append(['C', x + sign * .7, y + step / 3, x + sign * .7, y + 2 * step / 3, x, y + step])
            add_vector('side vine ' + side, [{'d': d, 'stroke': line, 'stroke_mm': .28}], 'vine')
        rule = .5
        add_vector('window frame', [{'d': [['M', window[0] - rule, window[1] - rule], ['L', window[2] + rule, window[1] - rule],
                                           ['L', window[2] + rule, window[3] + rule], ['L', window[0] - rule, window[3] + rule], ['Z']],
                                     'stroke': line, 'stroke_mm': .25}], 'frame')
    plan['counts'] = used
    return plan


# the checks ---------------------------------------------------------------------------------------------------------------

def press_check(plan):
    """Every piece against the press (the owner's §4): foil lines ≥ 0.1 mm, its gaps ≥ 0.2 mm, relief ≥ 0.3 mm; vectors closed
    where filled and clean; pictures at 300 PPI at their print size. A finish that fails drops to ink, moved to the motifs and
    listed; a picture under the bar fails. Returns the record."""
    from shapely.geometry import LineString
    rows, dropped = [], []
    for item in list(plan['finishes']):
        faults = []
        floor = FOIL_LINE_MIN_MM if item['finish'] == 'foil' else RELIEF_MIN_MM
        lines = []
        for path in item['paths']:
            width = path.get('stroke_mm', 0)
            if path.get('stroke') and width < floor - 1e-9:
                faults.append('a line of %.2f mm (at least %.2f)' % (width, floor))
            points = [tuple(op[-2:]) for op in path['d'] if op[0] != 'Z']
            if path.get('stroke') and len(points) > 1:
                lines.append(LineString(points).buffer(width / 2))
        if item['finish'] == 'foil':
            for i, a in enumerate(lines):
                for other in lines[i + 1:]:
                    gap = a.distance(other)
                    if 0 < gap < FOIL_GAP_MIN_MM - 1e-9:
                        faults.append('a gap of %.2f mm (at least %.2f)' % (gap, FOIL_GAP_MIN_MM))
        rows.append({'piece': item['name'], 'finish': item['finish'], 'holds': not faults, 'faults': faults})
        if faults:
            plan['finishes'].remove(item)
            plan['motifs'].append({'kind': 'vector', 'panel': item.get('panel', plan['key']), 'name': item['name'] + ' (in ink)', 'paths': item['paths'],
                                   'box_mm': _paths_box(item['paths']), 'generator': 'dropped to ink'})
            dropped.append(item['name'])
    for item in plan['motifs']:
        if item['kind'] == 'picture':
            rows.append({'piece': item['name'], 'ppi': item['ppi'], 'holds': item['ppi'] >= PICTURE_MIN_PPI - .5,
                         'faults': [] if item['ppi'] >= PICTURE_MIN_PPI - .5 else ['%.0f PPI at its print size' % item['ppi']]})
            continue
        faults = []
        for path in item['paths']:
            if len(path['d']) < 2:
                faults.append('a stray point')
            if path.get('fill') and path['d'][-1][0] != 'Z':
                faults.append('an open path on a fill')
            seen = [tuple(op[-2:]) for op in path['d'] if op[0] != 'Z']
            if any(p == q for p, q in zip(seen, seen[1:])):
                faults.append('a zero-length segment')
        rows.append({'piece': item['name'], 'holds': not faults, 'faults': faults})
    failed = [row['piece'] for row in rows if not row['holds'] and 'finish' not in row]
    return {'schema': 'press_check/1', 'limits_mm': {'foil_line': FOIL_LINE_MIN_MM, 'foil_gap': FOIL_GAP_MIN_MM, 'relief': RELIEF_MIN_MM},
            'picture_min_ppi': PICTURE_MIN_PPI, 'pieces': len(rows), 'dropped_to_ink': dropped, 'failed': failed, 'holds': not failed,
            'lowest_ppi': min([row['ppi'] for row in rows if 'ppi' in row], default=None),
            'rows': [row for row in rows if not row['holds']]}


def placement_check(plan, outline):
    """The placement's rules on one face's record: no motif crosses its printed shape (so no fold, cut line or bleed edge), none
    enters a quiet zone (lid_devices.intrusions), no two collide unless listed, and the words read at QUIET_CONTRAST."""
    from shapely.geometry import box as bx
    rows, faults = plan['motifs'], []
    shape = outline.buffer(1e-3, join_style=2)
    def boxes(item):
        return [_paths_box([path]) for path in item['paths']] if 'paths' in item else [item['box_mm']]
    for item in rows + plan['finishes']:
        if not all(shape.contains(bx(*box)) for box in boxes(item)):
            faults.append({'rule': 'crosses a fold or cut line', 'piece': item['name']})
    for zone in plan['zones']:
        z = bx(*zone['box'])
        for item in rows + plan['finishes']:
            if any(bx(*box).intersection(z).area > 1e-6 for box in boxes(item)) and not item['name'].endswith(('word frame', 'window frame')):
                faults.append({'rule': 'enters a quiet zone', 'piece': item['name'], 'zone': zone['name']})
    pictures = [item for item in rows if item['kind'] == 'picture']
    for i, a in enumerate(pictures):
        for other in pictures[i + 1:]:
            if bx(*a['box_mm']).intersection(bx(*other['box_mm'])).area > 1e-6:
                faults.append({'rule': 'collides', 'piece': a['name'], 'with': other['name']})
    readings = []
    for row in plan['words'].get('contrast', []):
        ratio = contrast_ratio(row['colour'], row['on'])
        readings.append(dict(row, ratio=round(ratio, 2), holds=ratio >= QUIET_CONTRAST - 1e-6))
        if ratio < QUIET_CONTRAST - 1e-6:
            faults.append({'rule': 'contrast under 4.5:1', 'piece': row['what'], 'ratio': round(ratio, 2)})
    return {'schema': 'placement_check/1', 'motifs': len(rows), 'zones': len(plan['zones']), 'contrast': readings, 'faults': faults,
            'holds': not faults}


def plan_spec(key, plan, die=None, *, identifier=None, words=True):
    """The writer's spec of one face alone, in its upright frame: the one placement record, for the preview and the file."""
    W, H = plan['frame_mm']
    t = plan['trim_mm']
    spec = {'id': identifier or FACES[key].get('object', key), 'title': FACES[key]['label'], 'size_mm': [W, H], 'law': True,
            'own_ground': plan['own_ground'], 'panels': {key: (t[2] - t[0]) * (t[3] - t[1])}, 'foil_svg': [],
            'ground': [{'name': _name(key, 'ground'), 'panel': key, 'hex': plan['ground']['hex'],
                        'rings_mm': plan['ground'].get('rings_mm') or [[[0, 0], [W, 0], [W, H], [0, H]]]}] if plan['ground'] else [],
            'motifs': plan['motifs'], 'finishes': plan['finishes'], 'type_runs': plan['words']['type'] if words else [],
            'logos': plan['words']['logos'] if words else [],
            'die': {'cut': [{'points_mm': [[t[0], t[1]], [t[2], t[1]], [t[2], t[3]], [t[0], t[3]]], 'closed': True}]}, 'guides': []}
    return spec


def _carry_paths(paths, to_sheet):
    out = []
    for path in paths:
        d = []
        for op in path['d']:
            coords = op[1:]
            moved = [v for i in range(0, len(coords), 2) for v in to_sheet(coords[i], coords[i + 1])]
            d.append([op[0]] + moved)
        out.append(dict(path, d=d))
    return out


def stand_pieces(drawn, geometry):
    """The stand's objects on the die's sheet, from each face's placement record: its ground (the panel's shape grown by the
    bleed, inside the die's printed area: one colour, overlapping, so no seam can open at a fold), its motifs and finishes
    turned onto the sheet with the face."""
    from apps.dielines.geometry import counter_display as cd
    die = die_of(geometry)
    piece = cd.piece_of(die)
    area = cd.bleed_area(piece)
    out = {'ground': [], 'motifs': [], 'finishes': [], 'panels': {}}
    b = STAND_BLEED_MM
    for key in (key for key in FACES if stand_face(key)):
        plan = json.loads(Path(drawn[key]['plan']).read_text())
        part_face, quarters = FACES[key]['die'], FACES[key]['quarters']
        _part, poly = die_face(die, part_face)
        w, h = face_mm_size(poly, quarters)
        to_sheet = _to_sheet(poly, quarters, w, h, b)
        grown = poly.buffer(b, join_style=2).intersection(area)
        out['panels'][key] = poly.area
        if plan['ground']:
            out['ground'].append({'name': _name(key, 'ground'), 'panel': key, 'hex': plan['ground']['hex'],
                                  'rings_mm': [[[round(x, 3), round(y, 3)] for x, y in ring] for ring in _rings(grown)]})
        for item in plan['motifs']:
            if item['kind'] == 'picture':
                out['motifs'].append(dict(item, box_mm=_box_to_sheet(item['box_mm'], to_sheet), rotation=(-90 * quarters) % 360))
            else:
                out['motifs'].append(dict(item, paths=_carry_paths(item['paths'], to_sheet)))
        for item in plan['finishes']:
            out['finishes'].append(dict(item, paths=_carry_paths(item['paths'], to_sheet)))
    colour = next((row['hex'] for row in out['ground']), None)
    if colour:
        for name, polygon in ground_only(die):
            out['ground'].append({'name': 'ground / ' + name, 'panel': 'ground', 'hex': colour,
                                  'rings_mm': [[[round(x, 3), round(y, 3)] for x, y in ring] for ring in _rings(polygon)]})
    return out


# the round's motif library: one sheet, cut apart, saved once ------------------------------------------------------------------

def design_words(record):
    """The picked design's own words on its layout, and its hero's name (from the picked board's motif line)."""
    root = flow.round_root(record)
    pick = (record.pick or {}).get('id')
    composition = ''
    for path in sorted(root.glob('designs/g*/designs.json'), reverse=True):
        candidate = json.loads(path.read_text()).get('candidates', {}).get(pick)
        if candidate:
            composition = ' '.join(str(candidate.get(name, '')) for name in ('composition', 'header', 'faces')).strip()
            break
    motif = ''
    if (root / 'board-pick.json').exists():
        motif = json.loads((root / 'board-pick.json').read_text()).get('board', {}).get('motif', '')
    found = re.search(r'\bone ([a-z]+)', motif.lower())
    hero = found.group(1) if found else 'hero'
    return {'composition': composition or motif, 'hero': hero, 'hero_words': 'the design\'s %s' % hero if found else 'the design\'s hero figure'}


def current_library(root):
    pointer = motifs_root(root) / 'current.json'
    return json.loads((motifs_root(root) / json.loads(pointer.read_text())['sheet'] / 'library.json').read_text()) if pointer.exists() else None


def sheet_reference(root, folder, record):
    """Image 2: the design as it stands, small: the latest stand art it has, else the picked picture."""
    wraps = sorted(Path(root).glob('flat/wraps/stand-*/wrap.png'))
    source = wraps[-1] if wraps else Path(root) / 'source.png'
    with Image.open(source) as image:
        art = image.convert('RGB')
    art.thumbnail((1024, 1024), Image.LANCZOS)
    art.save(Path(folder) / 'reference.png')
    return Path(folder) / 'reference.png'


def sheet_cost(*, words=3200):
    """The one motif sheet's cost and hold on the measured rates, its reference at most 1024 px wide (for the estimate)."""
    w, h = SHEET_SIZE
    inputs = [(w, h), (1024, 444)]
    return {'size': '%dx%d' % (w, h), 'pictures': len(sheet_cells()), 'usd': round(edit_cost('%dx%d' % (w, h), 'medium', inputs, 'x' * words), 4),
            'hold_usd': edit_hold('%dx%d' % (w, h), 'medium', inputs, 'x' * words)}


def paint_sheet(ctx, n, *, colours, rules='', note=''):
    """Sheet ``n`` of the round's picture motifs: one medium edit, each motif alone on the plain ground, cut apart here and
    saved once. Restartable: a saved reply is never bought twice. Returns the library."""
    folder = motifs_root(ctx.root) / ('sheet-%d' % n)
    record_path = folder / 'library.json'
    if record_path.exists():
        return json.loads(record_path.read_text())
    folder.mkdir(parents=True, exist_ok=True)
    words_of = design_words(ctx.round)
    sheet_template(colours['ground'], folder)
    reference = sheet_reference(ctx.root, folder, ctx.round)
    found = design_ground(ctx.round)
    words = sheet_prompt(ground_hex=colours['ground'], ground_name=(found or {}).get('name', ''), hero_words=words_of['hero_words'],
                         composition=words_of['composition'], rules=rules, note=note)
    call = ctx.face_edit('motif/sheet/%d' % n, words, folder / 'call', template=folder / 'template.png', references=[reference],
                         size='%dx%d' % SHEET_SIZE, quality='medium')
    library = cut_sheet(folder / 'call' / 'raw.png', folder / 'pieces', hero_name=words_of['hero'])
    library.update(sheet=n, prompt=words, cost_usd=call.get('cost_usd'), reservation_id=call['reservation_id'], ground=colours['ground'],
                   composition=words_of['composition'], reference_sha256=sha(reference), raw_sha256=sha(folder / 'call' / 'raw.png'))
    flow.write_json(record_path, library)
    flow.write_json(motifs_root(ctx.root) / 'current.json', {'sheet': 'sheet-%d' % n})
    return library


def draw_plan(root, key, n, brief, die, geometry, library, rhythm, colours, *, seed=0):
    """Drawing ``n`` of a face: its placement record, its checks, and the art rendered from it ($0: the writer's own render,
    so the views show what prints). Restartable. Returns the record."""
    from .round_files_export import export_object, render_flat
    folder = drawing_folder(root, key, n)
    record_path = folder / 'record.json'
    if record_path.exists():
        return _checked(record_path, 'face')
    folder.mkdir(parents=True, exist_ok=True)
    plan = plan_face(key, n, brief, die, geometry, library, rhythm, colours, seed=seed)
    face = face_geometry(key, brief, die)
    outline = face['outline']
    if plan['ground'] and stand_face(key):
        plan['ground']['rings_mm'] = [[[round(x, 3), round(y, 3)] for x, y in ring] for ring in _rings(outline.buffer(face['bleed_mm'], join_style=2))]
    press = press_check(plan)
    placement = placement_check(plan, outline)
    plan.update(press=press, placement=placement)
    flow.write_json(folder / 'plan.json', plan)
    art = export_object(plan_spec(key, plan, identifier='art-%s-%d' % (key, n), words=False), folder / 'art', native=False)
    render_flat(art['ai'], folder / 'face.png', dpi=300)
    W, H = plan['frame_mm']
    with Image.open(folder / 'face.png') as image:
        size = image.size
    k = size[0] / W
    hole = Image.new('L', size, 0)
    for ring in _rings(outline.buffer(face['bleed_mm'], join_style=2) if face['bleed_mm'] else outline):
        ImageDraw.Draw(hole).polygon([(x * k, y * k) for x, y in ring], fill=255)
    sheet = Image.new('RGBA', size, (255, 255, 255, 255))
    sheet.paste((0, 0, 0, 0), mask=hole)
    sheet.save(folder / 'template.png')
    template = {'size': '%dx%d' % size, 'frame_px': [0, 0, size[0], size[1]], 'px_per_mm': round(k, 6), 'frame_mm': [W, H],
                'template': str(folder / 'template.png'), 'native_ppi': 300.0, 'template_sha256': sha(folder / 'template.png')}
    record = {'key': key, 'n': n, 'label': FACES[key]['label'], 'source': 'plan', 'plan': str(folder / 'plan.json'), 'face': str(folder / 'face.png'),
              'face_sha256': sha(folder / 'face.png'), 'template': template, 'native_ppi': 300.0, 'seed': seed,
              'reference': {'path': str(folder / 'face.png'), 'sha256': sha(folder / 'face.png'), 'source': 'plan', 'detail': 'its art, from its placement record'},
              'counts': plan.get('counts'), 'press': {k_: press[k_] for k_ in ('holds', 'dropped_to_ink', 'failed', 'lowest_ppi', 'pieces')},
              'placement': {'holds': placement['holds'], 'faults': placement['faults'], 'contrast': placement['contrast']},
              'rule': 'placed by the engine, from the round\'s motif library; one record for the preview, the file and the drawings'}
    flow.write_json(record_path, record)
    return record


def on_liquid(path, hex_value, out):
    """A clear face over its liquid's colour (the owner's §5: "clear surfaces show the liquid colour through them, never
    white"), for the drawings: what the printed weave looks like on the filled bottle."""
    with Image.open(path) as image:
        rgba = image.convert('RGBA')
    ground = Image.new('RGBA', rgba.size, tuple(int(hex_value[i:i + 2], 16) for i in (1, 3, 5)) + (255,))
    ground.alpha_composite(rgba)
    ground.convert('RGB').save(out)
    return str(out)


def seam_proof(ai_path, die, folder, *, dpi=288):
    """Every crease of the die at 400 % (72 dpi × 4): a strip either side rendered from the print layers, listing any pixel of
    a printed face left with no ink: a crack. Returns the record, each crease's picture in ``folder``."""
    import fitz
    from .round_files_export import PRINT_LAYERS, PT, set_layers
    from shapely.geometry import box as bx
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    from apps.dielines.geometry import counter_display as cd
    piece = cd.piece_of(die)
    printed = [face for _name, face, is_printed in piece.faces if is_printed]
    rows = []
    with fitz.open(ai_path) as doc:
        set_layers(doc, PRINT_LAYERS)
        with fitz.open(stream=doc.tobytes(), filetype='pdf') as fresh:
            for index, (name, line) in enumerate(piece.creases):
                touching = [face for face in printed if face.distance(line) < 1e-3]
                if not touching:
                    continue
                x0, y0, x1, y1 = line.bounds
                clip = fitz.Rect((x0 - 2) * PT, (y0 - 2) * PT, (x1 + 2) * PT, (y1 + 2) * PT) & fresh[0].rect
                pix = fresh[0].get_pixmap(dpi=dpi, alpha=True, clip=clip)
                ink = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[..., 3]
                k = dpi / 25.4
                left, up = clip.x0 / PT, clip.y0 / PT
                mask = Image.new('L', (pix.width, pix.height), 0)
                for face in touching:
                    for ring in _rings(face.intersection(bx(left, up, clip.x1 / PT, clip.y1 / PT))):
                        ImageDraw.Draw(mask).polygon([((x - left) * k, (y - up) * k) for x, y in ring], fill=255)
                inside = cv2.erode(np.asarray(mask), np.ones((5, 5), np.uint8), borderValue=0) > 0     # its own outer edge antialiases
                gaps = int((inside & (ink < 250)).sum())
                out = folder / ('crease-%02d.png' % index)
                pix.save(out)
                rows.append({'crease': name, 'pixels_checked': int(inside.sum()), 'gap_pixels': gaps, 'picture': str(out), 'holds': gaps == 0})
    return {'schema': 'seam_proof/1', 'zoom_percent': 400, 'creases': rows, 'cracks': sum(row['gap_pixels'] for row in rows),
            'holds': all(row['holds'] for row in rows)}


def library_piece_verdict(path):
    """Whether a house file is one motif or a whole layout, read from the file itself (a caption calls a playing card's back
    an ornament): a fill under nearly the whole page, or several pieces standing apart, is a layout, and is never placed."""
    import fitz
    if not Path(path).exists():
        return 'refused: the file is not on disk'
    if Path(path).suffix.lower() != '.ai':
        return 'not read: an .eps needs Illustrator to open it'
    try:
        with fitz.open(path) as doc:
            page = doc[0]
            area = page.rect.width * page.rect.height
            drawings = page.get_drawings()
            if page.get_images():
                return 'refused: it holds pictures, not only vectors'
            if any(d.get('fill') is not None and (d['rect'] & page.rect).get_area() > 0.6 * area for d in drawings):
                return 'refused: a whole layout on its own ground'
            if len(drawings) > 400:
                return 'refused: a whole layout (%d paths)' % len(drawings)
    except Exception as exc:
        return 'refused: unreadable (%s)' % type(exc).__name__
    return 'one motif by its file; not placed: placing a house vector is not built yet'


def library_supporting(record, *, limit=8):
    """The house library's best supporting motifs for the round (D-D7-1), ranked by caption, tags and colour against its mood
    board: its vector ornaments, patterns and illustrations only, never a piece showing words or a banned motif. Pinned by
    hash. Never the hero. Returns the ranked rows, each with why it was or was not usable."""
    from . import round_designer as designer
    path = flow.REPO / 'docs/audit/day-7/library/materials-index.json'
    rows = json.loads(path.read_text()) if path.exists() else []
    rows = rows.get('items', []) if isinstance(rows, dict) else rows
    root = flow.round_root(record)
    board = json.loads((root / 'board-pick.json').read_text()).get('board', {}) if (root / 'board-pick.json').exists() else {}
    words = {word for word in re.findall(r'[a-z]{4,}', ' '.join(str(board.get(name, '')) for name in ('idea', 'motif', 'type')).lower())}
    banned = {str(word).lower().rstrip('s') for word in designer.round_banned(record, record.product_brief)}
    labs = [_hex_lab(colour['hex']) for colour in board.get('palette', [])]
    out = []
    for row in rows:
        rights = row.get('rights') or {}
        if row.get('kind') not in ('ornament', 'pattern', 'illustration') or str(row.get('extension')) not in ('.ai', '.eps'):
            continue
        if rights.get('excluded') or rights.get('tier') != 'house':
            continue
        text = ' '.join(str(row.get(name) or '') for name in ('tags', 'style', 'subject')).lower()
        hits = sum(1 for word in words if word in text)
        if not hits:
            continue
        colours = [c['lab'] for c in (row.get('colours') or []) if isinstance(c, dict) and c.get('lab')]
        near = min((math.dist(lab, other) for lab in labs for other in colours), default=99.0)
        verdict = 'usable'
        hit = next((word for word in banned if word and word in text), None)
        if hit:
            verdict = 'refused: it shows a banned motif (%s)' % hit
        elif row.get('text_seen'):
            verdict = 'refused: it carries words'
        else:
            verdict = library_piece_verdict(flow.REPO / ((row.get('paths') or [''])[0] if isinstance(row.get('paths'), list) else str(row.get('paths'))))
        out.append({'sha256': row['sha256'], 'name': row.get('name'), 'path': (row.get('paths') or [''])[0] if isinstance(row.get('paths'), list) else str(row.get('paths')),
                    'kind': row['kind'], 'extension': row['extension'], 'score': round(hits + max(0.0, 2 * (1 - near / 12)), 2),
                    'tags': row.get('tags'), 'verdict': verdict})
    out.sort(key=lambda row: -row['score'])
    return out[:limit]
