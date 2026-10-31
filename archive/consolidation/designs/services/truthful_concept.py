"""Day 8 §5 — the lid as our engine lays it out (D-D8-4, D-D8-11): what the sketches are given and what the truthful
build prints. The logo is the approved vector master, every word is live type in the spec's own face, and every
geometric device is ``lid_devices``' vectors, all in exact places on the 190 × 120 lid (millimetres, y down).

- ``options(d)``: the six sketches of a direction, a fraction of the 2 × 2 × 2 grid its spec's open choices name
  (never at random): each axis's levels appear three and three times on the first two axes.
- ``layout(d, option, anchors=None)``: the type set at the spec's measured sizes (cap height by the face's own OS/2
  capitals, the Arabic by its alif's ink), placed at the spec's zones — or at a sketch's measured anchors (Stage 2) —
  stacked so no line meets another, and the device drawn out of the type's boxes.
- ``document(lay, ...)``: the engine's Document (ground or plate, device, mark, type; finishes on their plates).
- ``render(doc, out)``: the engine's .ai rasterised at 4 × and brought down by Lanczos to the image model's scale —
  1536 px across the 190 mm (≈ 8.08 px/mm), the lid the middle 970 rows of a 1536 × 1024 frame (27 px bands).
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from functools import lru_cache
from pathlib import Path

from django.conf import settings

from apps.pipeline.services import lid_devices as dev

ROOT = Path(settings.BASE_DIR)
REPO = ROOT.parent
DAY8 = REPO / 'docs' / 'audit' / 'day-8'
SURFACE = 'apps/pipeline/services/truthful_concept.py::build_lid'
W, H = dev.LID_W, dev.LID_H
FRAME_PX = (1536, 1024)
LID_PX = (1536, 970)
BAND_PX = (FRAME_PX[1] - LID_PX[1]) // 2
PX_PER_MM = LID_PX[0] / W
SUPERSAMPLE = 4
MM_PER_PT = 25.4 / 72.0
#: the brief's copy, verbatim (brief 124; D-D8 intro) — every build is checked against it, word for word
COPY = {'name': 'Enchanted Rose', 'descriptor_en': 'Eyeshadow Palette', 'descriptor_ar': 'باليت ظلال العيون',
        'shades': '18 shades', 'net': '27 g ℮ 0.95 oz'}
#: the six of a 2 × 2 × 2 grid (level index per axis): a half fraction plus two, each of the first two axes 3 + 3
PATTERN = ((0, 0, 0), (0, 1, 1), (1, 0, 1), (1, 1, 0), (0, 0, 1), (1, 1, 1))
#: B's "ring field" choice in centres (lid fractions): the spec's pair, and the same pair moved off the corner
RING_CENTRES = {'centres off the right edge': ((1.18, 0.382), (1.236, 0.618)),
                'centres off the bottom-right corner': ((1.13, 1.17), (1.186, 1.406))}
GAP_MM = {'stack': 4.0, 'pair': 3.0}


def spec(direction: str) -> dict:
    return json.loads((DAY8 / 'directions' / f'{direction}.json').read_text())


def options(direction: str) -> list:
    """The direction's six sketch options along its spec's open choices, in ``PATTERN`` order."""
    axes = spec(direction)['open_choices']
    out = []
    for n, levels in enumerate(PATTERN, 1):
        choice = {a['axis']: a['values'][k] for a, k in zip(axes, levels)}
        out.append({'id': f'{direction}{n}', 'direction': direction, 'choices': choice, 'levels': list(levels)})
    return out


# --- type ---------------------------------------------------------------------------------------------------------

def face_of(stem_text: str) -> tuple:
    """'Montserrat[wght]@500' → ('Montserrat[wght]', 500.0); a static face by its own weight word."""
    if '@' in stem_text:
        stem, weight = stem_text.split('@', 1)
        return stem, float(weight)
    return stem_text, 700.0 if 'bold' in stem_text.lower() else 400.0


@lru_cache(maxsize=32)
def resolved(stem: str, weight: float) -> dict:
    from apps.ire import font_roles
    r = font_roles.resolve_line_face(stem, weight)
    if r.get('refused'):
        raise ValueError('the face %s at %s does not verify: %s' % (stem, weight, r.get('tried')))
    return r


def _is_arabic(text):
    return any('؀' <= ch <= 'ۿ' or 'ﭐ' <= ch <= '﻿' for ch in text)


def typeset(text: str, stem_text: str, *, cap_mm=None, alif_mm=None, tracking_em=0.0, upper=False) -> dict:
    """One line in its face at its measured size: the em size that puts the face's own capitals (OS/2) at ``cap_mm``,
    or its alif's ink at ``alif_mm``; the drawn width (outlines, tracking, a 3 mm ℮'s room) and the ink above and
    below the baseline, all in millimetres."""
    from apps.dielines.exporters.text_intl import shape_ar
    from apps.ire.text_metrics import cap_height_em_measured, drawn_width_mm, ink_extent_em
    stem, weight = face_of(stem_text)
    r = resolved(stem, weight)
    cap_em = cap_height_em_measured(r['path'])
    if alif_mm is not None:
        alif_em = ink_extent_em('ا', r['path'])[0]
        size = alif_mm / alif_em
    else:
        size = cap_mm / cap_em
    shown = text.upper() if upper else text
    measured = shape_ar(shown, keep_harakat=True) if _is_arabic(shown) else shown
    width = drawn_width_mm(measured, size, r['label'])
    if width is None:
        raise ValueError('%r does not measure in %s' % (text, stem))
    if tracking_em and '℮' not in measured:
        width += tracking_em * size * (len(measured) - 1)
    ext = ink_extent_em(measured.replace('℮', ''), r['path']) or (cap_em, 0.0)
    # a line carrying the ℮ mirrors what the emitter draws: the sign 3 mm tall (estimated_sign) and no tracking (pdf_ai
    # applies char_space only to a run without the sign) — stated as statements, not as a fallback value (§8)
    sign_line = '℮' in measured
    above = ext[0] * size
    line_tracking = tracking_em
    if sign_line:
        above = max(above, 3.0)
        line_tracking = 0.0
    return {'text': text, 'shown': shown, 'stem': stem, 'weight': weight, 'font': r['role'], 'label': r['label'],
            'path': r['path'], 'size_mm': size, 'size_pt': size / MM_PER_PT, 'cap_mm': (cap_em or 0) * size,
            'alif_mm': alif_mm, 'width_mm': width, 'above_mm': above, 'below_mm': max(0.0, -ext[1] * size),
            'tracking_em': line_tracking, 'upper': upper, 'arabic': _is_arabic(text)}


def place(line: dict, *, x: float, top: float, align='left') -> dict:
    """``line`` with its cap (or alif) top at ``top``: its baseline, anchor and ink box."""
    base = top + line['above_mm']
    x0 = x if align == 'left' else x - line['width_mm']
    return dict(line, x=x, baseline=base, align=align,
                box=(x0, base - line['above_mm'], x0 + line['width_mm'], base + line['below_mm']))


# --- layout -------------------------------------------------------------------------------------------------------

def _hex(h):
    from apps.ire.graph import Color
    return Color.from_hex(h)


def _shade(hex_value, by):
    """``hex_value`` darkened toward black by ``by`` (0–1): a blind line shown flat, tone on tone."""
    h = hex_value.lstrip('#')
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    return '#%02X%02X%02X' % tuple(round(c * (1 - by)) for c in rgb)


def _logo_box(zone_frac):
    from apps.ire import brand_mark
    master = brand_mark.approved_master()['master']
    x0, y0, x1, _y1 = dev.zone_mm(zone_frac)
    w = x1 - x0
    return (x0, y0, x1, y0 + w * master.aspect)


def layout(direction: str, option: dict, anchors: dict | None = None, overrides: dict | None = None) -> dict:
    """The lid for one option: lines placed, the mark's box, the device drawn clear of them, the colours by role and
    every measured fact the checks read. ``anchors`` (Stage 2): {'name' | 'descriptor_en' | 'descriptor_ar' | 'info' |
    'logo': (x, top)} in mm, read from the chosen sketch, replacing the spec's zone corners."""
    s = spec(direction)
    t, z, colours = s['type'], s['layout']['zones'], s['colours']
    ch = option['choices']
    anchors = anchors or {}
    over = overrides or {}                     # Stage 3's engine repairs ($0): type, colour, layout, device parameters
    notes = []

    def at(key, default):
        return anchors.get(key, default)

    support_stem = over.get('support_stem', t['support']['stem'])
    support = dict(stem_text=support_stem, cap_mm=t['support']['cap_mm'], tracking_em=t['support']['tracking_em'],
                   upper=t['support']['case'] == 'upper')
    en = typeset(COPY['descriptor_en'], **support)
    ar = typeset(COPY['descriptor_ar'], over.get('arabic_stem', t['arabic']['stem']), alif_mm=float(over.get('arabic_alif', t['arabic']['alif_mm'])))
    shades = typeset(COPY['shades'], support_stem, cap_mm=t['info_cap_mm'])
    net = typeset(COPY['net'], support_stem, cap_mm=t['info_cap_mm'])
    upper_name = t['display']['case'] == 'upper'
    name_lines = [COPY['name']]
    if direction == 'A':
        cap = float(ch['type scale'])
    elif direction == 'B':
        cap = 14.0 if ch['type scale'].startswith('one line') else 18.0
        if ch['type scale'].startswith('two lines'):
            name_lines = COPY['name'].split(' ')
    else:
        cap = float(ch['type scale'])
        name_lines = COPY['name'].split(' ')          # C's name zone holds the name on two lines (85 mm wide)
    cap = float(over.get('name_cap', cap))
    if over.get('name_lines') == 2 and len(name_lines) == 1:
        name_lines = COPY['name'].split(' ')
    names = [typeset(n, t['display']['stem'], cap_mm=cap, tracking_em=t['display']['tracking_em'], upper=upper_name)
             for n in name_lines]
    advance = names[0]['size_mm'] * (1.05 if direction == 'B' else 1.35 if direction == 'C' else 1.1)
    nx, ny = at('name', (z['name'][0] * W, z['name'][1] * H))
    ny = float(over.get('name_top', ny))
    placed_names = [place(n, x=nx, top=ny + i * advance) for i, n in enumerate(names)]
    name_bottom = max(n['box'][3] for n in placed_names)
    lines = {'name': placed_names}
    logo_zone = z['logo']
    logo = _logo_box(logo_zone)
    if over.get('logo_scale'):
        k = float(over['logo_scale'])
        logo = (logo[0], logo[1], logo[0] + (logo[2] - logo[0]) * k, logo[1] + (logo[3] - logo[1]) * k)
    if 'logo' in anchors:
        lx, ly = anchors['logo']
        logo = (lx, ly, lx + (logo[2] - logo[0]), ly + (logo[3] - logo[1]))
    rule = None
    if direction == 'A':
        ex, ey = at('descriptor_en', (z['descriptor_en'][0] * W, z['descriptor_en'][1] * H))
        ey = max(ey, name_bottom + GAP_MM['stack'])
        lines['descriptor_en'] = place(en, x=ex, top=ey)
        ax = at('descriptor_ar', (z['descriptor_ar'][2] * W, 0))[0]
        ar_top = lines['descriptor_en']['baseline'] - ar['above_mm']          # baselines aligned across the band
        lines['descriptor_ar'] = place(ar, x=ax, top=ar_top, align='right')
        ix = at('info', (z['info'][2] * W, 0))[0]
        info_base = logo[3]                                                   # the info's baseline on the mark's foot
        lines['net'] = place(net, x=ix, top=info_base - net['above_mm'], align='right')
        lines['shades'] = place(shades, x=lines['net']['box'][0] - 5.0, top=info_base - shades['above_mm'], align='right')
    else:
        col_x = at('descriptor_en', (z['descriptor_en'][0] * W, 0))[0]
        if direction == 'C':
            rule_top = max(z['rule'][1] * H, name_bottom + 6.0)
            rule = (z['rule'][0] * W, rule_top, z['rule'][2] * W, rule_top + 0.3)
            prev = rule[3]
        else:
            prev = name_bottom
        ey = max(at('descriptor_en', (0, z['descriptor_en'][1] * H))[1], prev + GAP_MM['stack'] + (2.0 if direction == 'B' else 0))
        lines['descriptor_en'] = place(en, x=col_x, top=ey)
        ay = max(at('descriptor_ar', (0, z['descriptor_ar'][1] * H))[1], lines['descriptor_en']['box'][3] + GAP_MM['pair'])
        lines['descriptor_ar'] = place(ar, x=col_x, top=ay)
        iy = max(at('info', (0, z['info'][1] * H))[1], lines['descriptor_ar']['box'][3] + GAP_MM['stack'])
        lines['shades'] = place(shades, x=col_x, top=iy)
        lines['net'] = place(net, x=lines['shades']['box'][2] + 5.0, top=iy + shades['above_mm'] - net['above_mm'])
    boxes = {'logo': logo}
    for key, value in lines.items():
        for i, ln in enumerate(value if isinstance(value, list) else [value]):
            boxes[key if not isinstance(value, list) else f'{key}.{i}'] = ln['box']
    if rule:
        boxes['rule'] = rule
    # the device, drawn clear of every box
    if direction == 'A':
        keep = [dev.grown(boxes[k], 2.0) for k in ('logo', 'shades', 'net')]
        whole = ch['device scale'].startswith('the whole lid')
        band = None
        zone = tuple(z['device'])
        if whole:
            top_boxes = [b for k, b in boxes.items() if k.startswith(('name', 'descriptor'))]
            band = (min(b[1] for b in top_boxes) - 3.0, max(b[3] for b in top_boxes) + 3.0)
            zone = (0.0, 0.0, 1.0, 1.0)
        device = dev.gravure(**{**dict(zone=zone, clear_band=band, lens=tuple(ch['lens position']), keepouts=keep), **over.get('device', {})})
    elif direction == 'B':
        keep = [dev.grown(b, float(over.get('ring_clearance', 2.0))) for b in boxes.values()]
        printed = 'secondary' if ch['colour weighting'] == 'rose-led' else 'accent'
        device = dev.interference(**{**dict(centres=RING_CENTRES[ch['ring field']], keepouts=keep, inks=(printed, 'blind')), **over.get('device', {})})
    else:
        keep = [dev.grown(b, 3.0) for b in boxes.values()]
        device = dev.astrolabe(**{**dict(centre=tuple(ch['instrument centre']), diameter=float(ch['instrument scale']), keepouts=keep), **over.get('device', {})})
    ink = {'dominant': colours['dominant']['hex'], 'secondary': colours['secondary']['hex'],
           'accent': colours['accent']['hex'], 'type': colours['type']['hex']}
    ink.update(over.get('ink', {}))
    ink['blind'] = over.get('ink', {}).get('blind', _shade(ink['dominant'], 0.22))
    small = ink['accent'] if direction == 'B' else ink['type']
    roles = {'name': ink['type'], 'descriptor_en': small, 'descriptor_ar': small, 'shades': small, 'net': small,
             'logo': {'A': ink['accent'], 'B': ink['accent'], 'C': ink['secondary']}[direction],
             'rule': ink['secondary']}
    roles.update(over.get('roles', {}))
    for key, b in boxes.items():
        if b[0] < 0 or b[1] < 0 or b[2] > W or b[3] > H:
            notes.append('%s runs off the lid (%.1f, %.1f, %.1f, %.1f mm)' % (key, *b))
    return {'direction': direction, 'option': option, 'lines': lines, 'logo': logo, 'rule': rule, 'boxes': boxes,
            'device': device, 'ink': ink, 'roles': roles, 'notes': notes, 'overrides': over}


# --- the engine's document ------------------------------------------------------------------------------------------

FOIL_PLATES = {'A': {'accent': 'FOIL_ROSE_GOLD'}, 'B': {}, 'C': {'secondary': 'FOIL_GOLD', 'accent': 'FOIL_ROSE_GOLD'}}


def _finishes(direction, ink_role, names, hex_value):
    from apps.ire.graph import Finish
    out = []
    for n in names:
        if n == 'foil':
            out.append(Finish(kind='foil', plate=FOIL_PLATES[direction].get(ink_role, 'FOIL'), appearance=_hex(hex_value)))
        elif n in ('deboss', 'emboss'):
            out.append(Finish(kind=n, plate=n.upper()))
    return out


def _path(points, closed):
    from apps.ire.graph import ClosePath, LineTo, MoveTo
    segs = [MoveTo(x=points[0][0], y=points[0][1])] + [LineTo(x=x, y=y) for x, y in points[1:]]
    return segs + ([ClosePath()] if closed else [])


CLEAR = ('deboss', 'emboss')


def document(lay: dict, *, parts=('ground', 'device', 'logo', 'type'), plate: str | None = None, view=True,
             only: str | None = None, keep_mark=None, rule=True):
    """The lid as an engine Document. ``parts`` picks the layers; ``plate`` puts a raster under everything instead of
    the flat ground; ``only`` keeps one line key or 'logo'.

    Inks and foils draw on page 1 flat (a foil in its metal). A CLEAR finish (deboss, emboss) is carried by a copy of
    its element's geometry in the zero-opacity layer FINISH CARRIERS, so the emitter writes its plate in register and
    page 1 keeps the ink's own colour — the emitter's lit-outline depiction of a relief, drawn over 0.18 mm lines,
    greys the whole field (measured on the first render, Day 8). A BLIND mark has no ink: ``view=True`` (the flat
    preview the jury reads, finishes as flat zones) shows it tone on tone; ``view=False`` (what prints, and what the
    image model is shown) leaves it out — it lives on its plate."""
    from apps.ire import brand_mark
    from apps.ire.graph import Document, Group, Image, Path as VPath, Rect, SolidFill, Stroke, TextRun
    d, ink, roles = lay['direction'], lay['ink'], lay['roles']
    children, carriers = [], []
    if 'ground' in parts:
        if plate:
            children.append(Group(name='PLATE', role='background', children=[Image(name='plate', src=str(plate), x=0, y=0, w=W, h=H)]))
        else:
            children.append(Group(name='GROUND', role='background', children=[Rect(name='ground', x=0, y=0, w=W, h=H, fill=SolidFill(color=_hex(ink['dominant'])))]))
    if 'device' in parts and only is None:
        nodes = []
        for i, m in enumerate(lay['device']['marks']):
            if keep_mark is not None and not keep_mark(m):
                continue
            colour = ink[m['ink']]
            foil = [f for f in m['finishes'] if f == 'foil']
            clear = [f for f in m['finishes'] if f in CLEAR]
            segs = _path(m['points'], m['closed'] or bool(m['fill']))
            paint = dict(fill=SolidFill(color=_hex(colour))) if m['fill'] else dict(stroke=Stroke(color=_hex(colour), width_mm=m['width']))
            if m['ink'] != 'blind' or view:
                nodes.append(VPath(name=f'device-{i}', segments=segs, finishes=_finishes(d, m['ink'], foil, colour), **paint))
            if clear:
                carriers.append(VPath(name=f'device-{i}-{clear[0]}', segments=segs, finishes=_finishes(d, m['ink'], clear, colour), **paint))
        if lay.get('rule') and rule:
            x0, y0, x1, y1 = lay['rule']
            nodes.append(VPath(name='rule', segments=_path([(x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2)], False),
                               stroke=Stroke(color=_hex(roles['rule']), width_mm=y1 - y0),
                               finishes=_finishes(d, 'secondary', ('foil',), roles['rule'])))
        children.append(Group(name='DEVICE', role='decoration', children=nodes))
    if 'logo' in parts and only in (None, 'logo'):
        master = brand_mark.approved_master()['master']
        x0, y0, x1, y1 = lay['logo']
        node = brand_mark.mark_node('BBROSE mark', master, x0, y0, x1 - x0, y1 - y0)
        node.recolor = _hex(roles['logo'])
        if d in ('A', 'C') and not lay.get('overrides', {}).get('logo_ink'):
            node.finishes = _finishes(d, 'accent' if d == 'A' else 'secondary', ('foil',), roles['logo'])
        children.append(Group(name='LOGO', role='logo', children=[node]))
    if 'type' in parts:
        runs = []
        for key, value in lay['lines'].items():
            if only not in (None, key):
                continue
            for i, ln in enumerate(value if isinstance(value, list) else [value]):
                run = TextRun(name=f'{key}-{i}' if isinstance(value, list) else key, text=ln['text'], x=ln['x'],
                              y=ln['baseline'], font=ln['font'], size_pt=ln['size_pt'], color=_hex(roles[key]),
                              align=ln['align'], tracking_em=ln['tracking_em'] or None,
                              text_case='upper' if ln['upper'] else None)
                runs.append(run)
                if d == 'B' and key == 'name':      # the name raised in register with its ink (blind emboss)
                    carriers.append(run.model_copy(update={'name': run.name + '-emboss',
                                                           'finishes': _finishes(d, 'type', ('emboss',), roles[key])}))
        children.append(Group(name='TYPE', role='typography', children=runs))
    if carriers:
        children.append(Group(name='FINISH CARRIERS', role='effects', opacity=0.0, children=carriers))
    return Document(page_w=W, page_h=H, title=f'Enchanted Rose lid {lay["option"]["id"]}',
                    metadata={'typography_surface': SURFACE}, root=Group(name='root', role='artwork', children=children))


def render(doc, out_png, *, frame=True, ground_hex=None) -> dict:
    """The document through the engine (.ai) and rasterised at 4 ×, brought down by Lanczos to 1536 × 970; in the
    1536 × 1024 frame (27 px bands in the ground's colour) when ``frame``."""
    from PIL import Image as PILImage
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.rasterize import pdf_to_png
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    dpi = round(LID_PX[0] * SUPERSAMPLE / (W / 25.4))
    with tempfile.TemporaryDirectory() as tmp:
        ai = Path(tmp) / 'lid.ai'
        emit_pdf_ai(doc, str(ai))
        big = Path(tmp) / 'big.png'
        if not pdf_to_png(ai, big, dpi=dpi):
            raise RuntimeError('the engine render failed at %s dpi' % dpi)
        with PILImage.open(big) as im:
            lid = im.convert('RGB').resize(LID_PX, PILImage.LANCZOS)
    if frame:
        canvas = PILImage.new('RGB', FRAME_PX, ground_hex or '#FFFFFF')
        canvas.paste(lid, (0, BAND_PX))
        canvas.save(out_png)
    else:
        lid.save(out_png)
    return {'path': str(out_png), 'sha256': hashlib.sha256(out_png.read_bytes()).hexdigest(), 'dpi_supersampled': dpi}


def crop_to(png_path, box_mm, out_png, pad_mm=3.0, framed=True):
    """A lid render cropped to ``box_mm`` (+ padding), at the lid's own scale."""
    from PIL import Image as PILImage
    x0, y0, x1, y1 = box_mm
    off = BAND_PX if framed else 0
    px = lambda v: int(round(v * PX_PER_MM))
    with PILImage.open(png_path) as im:
        cut = im.crop((max(0, px(x0 - pad_mm)), max(0, px(y0 - pad_mm) + off),
                       min(im.width, px(x1 + pad_mm)), min(im.height, px(y1 + pad_mm) + off)))
        cut.save(out_png)
    return {'path': str(out_png), 'sha256': hashlib.sha256(Path(out_png).read_bytes()).hexdigest(), 'size': list(cut.size)}


# =====================================================================================================================
# Stage 2 — the truthful build: the sketch read, our layout placed, the picture painted around it, the plate cleaned
# under our elements and proven to carry no model-drawn copy of them
# =====================================================================================================================

CONCEPTS = DAY8 / 'concepts'
BUILD_PREFIX = 'day8/builds/'
BUILD_CAP_USD = 4.5               # the money plan's $10 for Stages 2–3: ≤ 18 high-quality edits here, the jury $5.5
PLATE_QUALITY = 'high'            # the printed plate is always high quality (15 Oct)
#: the media map's picture layer, in the specs' own words; B has none (flat spot colour, D-D8-4)
PLATE_GROUND = {'A': 'deep plum lacquer (%s) with a fine velvet grain', 'C': 'warm ivory cotton-rag board (%s) with a soft felt texture'}
GROW_MM = 1.0
MARGIN_MM = 5.0
ANCHOR_TOLERANCE_MM = 25.0


def _px(v):
    return int(round(v * PX_PER_MM))


def line_system(direction: str, mark: dict) -> bool:
    """A mark of a dense engine line system laid OVER the plate and never shown to the image model: A's field (its
    0.6 mm pitch grown by 1 mm is the whole field — inpainted, it would smear the plate) and C's instrument. A's hero
    line (a filled shape) is shown. Recorded under SKIPPED OR SIMPLIFIED: the owner's step 2 leaves out only the blind."""
    return (direction == 'A' and not mark['fill']) or direction == 'C'


def _gray(png):
    import cv2
    return cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)


def find_mark(lid_png, lay, out_dir) -> dict:
    """Our mark matched on a lid picture (normalised cross-correlation over scales 0.6–1.4): its box in mm and score.
    Where no scale can be tried (the template as large as the picture, or flat in grey: a mark printed in its
    ground's own grey) nothing is matched: the box and the score are None, and 'not_measured' says why."""
    import cv2
    import numpy as np
    tmp = Path(out_dir) / 'mark-template.png'
    render(document(lay, parts=('ground', 'logo'), only='logo'), tmp, frame=False)
    x0, y0, x1, y1 = lay['logo']
    template = _gray(tmp)[_px(y0):_px(y1), _px(x0):_px(x1)]
    image = _gray(lid_png)
    # Day 8 residual (find_mark): the best match starts as None, never as a score of -1.0. A mark matched at no scale
    # read -1.0 at a box at the origin: the plate proof took it for "our mark is not on the plate" and held with
    # nothing measured (a logo printed in the ground's own colour is flat in grey at every scale), and designer_eye
    # reported the sketch's mark at (0.0, 0.0). The scales skipped are counted, so the reason is said.
    best, too_large, flat = None, 0, 0
    for scale in np.linspace(0.6, 1.4, 17):
        t = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if t.shape[0] >= image.shape[0] or t.shape[1] >= image.shape[1]:
            too_large += 1
            continue
        if t.std() < 1:
            flat += 1
            continue
        _lo, hi, _lp, loc = cv2.minMaxLoc(cv2.matchTemplate(image, t, cv2.TM_CCOEFF_NORMED))
        if best is None or hi > best[0]:
            best = (float(hi), loc, t.shape)
    if best is None:
        return {'box_mm': None, 'score': None,
                'not_measured': 'no scale could be tried: of the 17 from 0.6 to 1.4, the template is as large as the '
                                'picture at %d and flat in grey at %d, a grey std under 1 (a mark that does not stand '
                                'off its ground in grey)' % (too_large, flat)}
    score, (x, y), (h, w) = best
    return {'box_mm': [x / PX_PER_MM, y / PX_PER_MM, (x + w) / PX_PER_MM, (y + h) / PX_PER_MM], 'score': round(score, 3)}


def read_sketch(direction: str, option: dict, lid_png, out_dir) -> dict:
    """The chosen sketch's measured positions (mm on the lid; the crop is 1536 × 970 at ≈ 8.08 px/mm): OCR boxes for
    the name, the descriptor and the info line; the mark by image matching. An anchor stands only where it reads, keeps
    the lid's margins and lies within 25 mm of the spec's own place; otherwise the spec's zone stands, and it is said."""
    from apps.pipeline.services.concept_sketches import _near, ocr_words
    spec_lay = layout(direction, option)
    # the gate review of Day 8: a failed OCR read raises OCRFailed here, so the build stops before any plate is paid
    # for, and no anchor reads "not read on the sketch" for a read that never happened
    words = ocr_words(lid_png)

    def box_of(targets):
        hits = [b for t, c, b in words if c > 20 and any(_near(t, w) or (len(w) > 3 and w.lower() in t.lower()) for w in targets)]
        if not hits:
            return None
        return [min(b[0] for b in hits) / PX_PER_MM, min(b[1] for b in hits) / PX_PER_MM,
                max(b[2] for b in hits) / PX_PER_MM, max(b[3] for b in hits) / PX_PER_MM]

    measured = {'name': box_of(('Enchanted', 'Rose')), 'descriptor_en': box_of(('EYESHADOW', 'PALETTE')),
                'info': box_of(('18', 'shades', '0.95', 'oz', '27'))}
    measured['logo'] = find_mark(lid_png, spec_lay, out_dir)
    anchors, notes = {}, []
    sb = spec_lay['boxes']
    want = {'name': (sb['name.0'][0], sb['name.0'][1]), 'descriptor_en': (sb['descriptor_en'][0], sb['descriptor_en'][1]),
            'info': (sb['net'][2], sb['net'][1]) if direction == 'A' else (sb['shades'][0], sb['shades'][1]),
            'logo': (spec_lay['logo'][0], spec_lay['logo'][1])}
    for key, target in want.items():
        got = measured[key]
        if key == 'logo':
            if got['score'] is None:
                # Day 8 residual (read_sketch): our mark matched at no scale has no score (find_mark says why). It is
                # treated as a low score is, explicitly: no anchor, the spec's place stands, and the note says it was
                # not measured, never "not read" (a None score compared with 0.45 would raise)
                notes.append('logo: not measured on the sketch — %s — the spec\'s place stands' % got['not_measured'])
                continue
            got = got['box_mm'] if got['score'] >= 0.45 else None
        if got is None:
            notes.append('%s: not read on the sketch — the spec\'s place stands' % key)
            continue
        point = (got[2], got[1]) if (key == 'info' and direction == 'A') else (got[0], got[1])
        inside = MARGIN_MM <= point[0] <= W - MARGIN_MM and MARGIN_MM <= point[1] <= H - MARGIN_MM
        near = abs(point[0] - target[0]) <= ANCHOR_TOLERANCE_MM and abs(point[1] - target[1]) <= ANCHOR_TOLERANCE_MM
        if inside and near:
            anchors[key] = point
        else:
            notes.append('%s: read at (%.1f, %.1f) mm, %s — the spec\'s place stands' % (
                key, point[0], point[1], 'outside the margins' if not inside else 'over 25 mm from the spec\'s place'))
    return {'measured': measured, 'anchors': anchors, 'notes': notes, 'ocr_words': [t for t, c, _b in words if c >= 50]}


def _render_elements(lay, out_png, *, keep_mark=None, rule=True, parts=('device', 'logo', 'type')):
    """Our inked elements alone (no blind) on the flat ground, unframed — for footprints and the plate's input."""
    return render(document(lay, parts=('ground',) + tuple(parts), view=False, keep_mark=keep_mark, rule=rule), out_png, frame=False)


def footprint(lay, out_dir, *, keep_mark=None, rule=True, grow_mm=GROW_MM, parts=('device', 'logo', 'type')):
    """Where our inked elements print (their pixels against the flat ground), grown by ``grow_mm``: a 970 × 1536 mask."""
    import cv2
    import numpy as np
    out_dir = Path(out_dir)
    ground = render(document(lay, parts=('ground',)), out_dir / '_ground.png', frame=False)['path']
    shown = _render_elements(lay, out_dir / '_elements.png', keep_mark=keep_mark, rule=rule, parts=parts)['path']
    diff = np.abs(cv2.imread(shown).astype(int) - cv2.imread(ground).astype(int)).max(axis=2) > 10
    r = max(1, _px(grow_mm))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    return cv2.dilate(diff.astype(np.uint8), kernel) > 0


def plate_prompt(direction: str, lay: dict) -> str:
    ground = PLATE_GROUND[direction] % lay['ink']['dominant']
    laid = {'A': 'the engraved field of fine teal lines', 'C': 'the gold-foil instrument'}[direction]
    shown = {'A': 'its words, its mark and its rose-gold hero line', 'C': 'its words, its mark and its gold rule'}[direction]
    return '\n\n'.join([
        'FORMAT. The flat print artwork of the closed lid of an eyeshadow palette, 190 × 120 mm, front-on and edge to '
        'edge; the lid is the middle 1536 × 970 of the 1536 × 1024 frame, the 27 px bands continue the ground.',
        'IMAGE 1 is the lid laid out by our engine: %s are final and stay exactly where and as they are; the mask '
        'marks them. IMAGE 2 is the chosen sketch — the reference for the ground\'s colour, light and texture only.' % shown,
        'PAINT ONLY THE PICTURE LAYER: the lid\'s ground, %s — even, matte and flat, lit evenly from the front, '
        'continuous from edge to edge and under where the elements sit.' % ground,
        'DO NOT draw any line, wave, ring, engraving, instrument, compass, star, ornament, pattern, word, letter, number, '
        'symbol or logo anywhere — our engine lays %s over the ground afterwards. No glow, halo, gradient band, '
        'vignette, shadow, reflection, light rays, sparkle, frame, perspective or mockup.' % laid])


def paint_plate(direction: str, lay: dict, sketch_frame_png, out_dir, *, client=None, attempt='plate') -> dict:
    """ONE high-quality gpt-image-2 edit of our layout — the picture painted around our elements, the chosen sketch the
    style reference, a mask guiding it — then the model's pixels kept only outside our elements' footprints (grown
    1 mm), the footprints filled by OpenCV inpainting ($0). Resumes: a plate already paid for is read back."""
    import cv2
    import numpy as np
    from PIL import Image as PILImage
    from apps.pipeline.services import image_guard
    from apps.pipeline.services.spend_reservation import paid_operation
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    done = out_dir / f'{attempt}.json'
    if done.exists():
        return json.loads(done.read_text())
    keep = (lambda m: not line_system(direction, m))
    layout_png = render(document(lay, view=False, keep_mark=keep), out_dir / f'{attempt}-input.png', ground_hex=lay['ink']['dominant'])['path']
    fp = footprint(lay, out_dir, keep_mark=keep)
    alpha = np.zeros((FRAME_PX[1], FRAME_PX[0]), np.uint8)
    alpha[BAND_PX:BAND_PX + LID_PX[1], :] = np.where(fp, 255, 0)
    mask = np.dstack([np.zeros_like(alpha)] * 3 + [alpha])
    mask_png = out_dir / f'{attempt}-mask.png'
    PILImage.fromarray(mask, 'RGBA').save(mask_png)
    text = plate_prompt(direction, lay)
    items = [{'role': 'the lid laid out by our engine (inked elements; the line system and the blind left out)', 'path': layout_png},
             {'role': 'the chosen sketch, the style reference', 'path': str(sketch_frame_png)},
             {'role': 'the mask (our elements\' footprints, grown 1 mm)', 'path': str(mask_png)}]
    operation = BUILD_PREFIX + '%s/%s' % (out_dir.name, attempt)

    def invoke(checked):
        if client is None:
            from openai import OpenAI
            api = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0, timeout=400)
        else:
            api = client
        from contextlib import ExitStack
        import shutil
        with ExitStack() as stack:
            images = [stack.enter_context(open(i['path'], 'rb')) for i in checked[:2]]
            mask_file = stack.enter_context(open(checked[2]['path'], 'rb'))
            response = paid_operation(api.images.edit, provider='openai', operation=operation, reservation_prefix=BUILD_PREFIX,
                                      reservation_cap=BUILD_CAP_USD, model=settings.IMAGE_MODEL, image=images, mask=mask_file,
                                      prompt=text, n=1, size='%dx%d' % FRAME_PX, quality=PLATE_QUALITY)
        saved = getattr(response, '_rescue_paid_images', [])
        if len(saved) != 1:
            raise RuntimeError('the paid response is kept, but exactly one picture was not recovered')
        shutil.copyfile(saved[0], out_dir / f'{attempt}-picture-frame.png')
        return {'reservation_id': getattr(response, '_rescue_reservation_id', None),
                'usage': response.model_dump(mode='json').get('usage')}

    result = image_guard.guarded_call(invoke, operation=operation, inputs=items, prompt=text, quality=PLATE_QUALITY,
                                      size='%dx%d' % FRAME_PX)
    with PILImage.open(out_dir / f'{attempt}-picture-frame.png') as im:
        frame = im.convert('RGB')
        if frame.size != FRAME_PX:
            frame = frame.resize(FRAME_PX, PILImage.LANCZOS)
        picture = frame.crop((0, BAND_PX, FRAME_PX[0], BAND_PX + LID_PX[1]))
    picture.save(out_dir / f'{attempt}-picture.png')
    bgr = cv2.cvtColor(np.asarray(picture), cv2.COLOR_RGB2BGR)
    clean = cv2.inpaint(bgr, fp.astype(np.uint8) * 255, 6, cv2.INPAINT_TELEA)
    cv2.imwrite(str(out_dir / f'{attempt}.png'), clean)
    record = dict(result, plate=str(out_dir / f'{attempt}.png'), picture=str(out_dir / f'{attempt}-picture.png'),
                  input=layout_png, mask=str(mask_png), prompt=text, inpainted_fraction=round(float(fp.mean()), 4))
    done.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
    return record


# --- the plate's proof: no model-drawn copy of the logo, a word or the device, anywhere on it ------------------------

def _line_energy(gray, region):
    """Band-pass energy (periods of 3–14 px: the devices' line pitches at ≈ 8 px/mm) inside ``region`` (bool); None
    for an empty region, where nothing is measured."""
    import cv2
    import numpy as np
    # the gate review of Day 8 (_line_energy): an empty region read 0.0, "no lines", and an empty device footprint
    # passed the plate proof on it; the caller now names what it could not measure
    if not region.any():
        return None
    g = gray.astype(np.float32)
    band = cv2.GaussianBlur(g, (0, 0), 1.0) - cv2.GaussianBlur(g, (0, 0), 4.0)
    return float(np.sqrt(np.mean(band[region] ** 2)))


def _ocr(png, lang, psm):
    """``ocr_words`` as (words, None), or (None, why) when tesseract failed: the plate proof records the failure and
    does not hold (the gate review of Day 8: a failed read came back as no words, and the proof passed on it)."""
    from apps.pipeline.services.concept_sketches import OCRFailed, ocr_words
    try:
        return ocr_words(png, lang=lang, psm=psm), None
    except OCRFailed as failed:
        # Day 8 residual (_ocr): the failure is told by the words being None, never by the message; an OCRFailed
        # without a message still names the read that failed
        why = str(failed)
        if not why:
            why = 'tesseract (%s, psm %s) raised OCRFailed without a message' % (lang, psm)
        return None, why


def prove_plate(direction: str, lay: dict, plate_png, out_dir) -> dict:
    """Over the WHOLE plate: OCR (English, and Arabic) finds none of the brief's words or the house name; our mark is
    not matched anywhere; and over the device's place the plate carries no line system — its band-pass line energy is
    no higher than the plate's own elsewhere, and its line pattern does not correlate with our device's. What could
    not be measured (an OCR read that failed, an empty region, our mark matched at no scale, a pattern correlation
    that is not a number) is named under 'not_measured', its value None, and the proof does not hold. Line energy over
    the device and essentially none elsewhere is measured, not missing: 'line_system_detected', with the energy over
    the device ('device_line_energy'); its ratio is unbounded (None), and the proof does not hold."""
    import cv2
    import numpy as np
    from apps.pipeline.services.concept_sketches import COPY_WORDS, _near
    out_dir = Path(out_dir)
    sparse, sparse_failed = _ocr(plate_png, 'eng', 11)
    block, block_failed = _ocr(plate_png, 'eng', 6)
    arabic, arabic_failed = _ocr(plate_png, 'ara', 11)
    # Day 8 residual (the OCR failure): a failed read is told by its words being None, never by its message's
    # truthiness — an OCRFailed with an empty message was dropped here, its copy stayed None, and the proof held on it
    not_measured = ['the OCR failed, so the plate\'s copy is not read: %s' % why
                    for words, why in ((sparse, sparse_failed), (block, block_failed), (arabic, arabic_failed)) if words is None]
    latin, ar = None, None
    if sparse is not None and block is not None:
        latin = [t for t, c, _b in sparse + block if c >= 40 and len(t) >= 2 and any(_near(t, w) for w in COPY_WORDS + ('BBROSE',))]
    if arabic is not None:
        arabic_words = COPY['descriptor_ar'].split()
        ar = [t for t, c, _b in arabic if c >= 40 and any(_near(t, w) for w in arabic_words)]
    mark = find_mark(plate_png, lay, out_dir)
    if mark['score'] is None:
        # Day 8 residual (the mark): matched at no scale, our mark was not looked for — its score is None, never -1.0
        # read as "not on the plate"
        not_measured.append('our mark could not be looked for on the plate — %s' % mark['not_measured'])
    gray = _gray(plate_png)
    dev_px = footprint(lay, out_dir, keep_mark=lambda m: True, rule=False, grow_mm=2.0, parts=('device',))
    rest = ~footprint(lay, out_dir, keep_mark=lambda m: True, grow_mm=6.0)
    inside, outside = _line_energy(gray, dev_px), _line_energy(gray, rest)
    lines_only = footprint(lay, out_dir, keep_mark=lambda m: True, rule=False, grow_mm=0.0, parts=('device',)).astype(np.float32)
    g = gray.astype(np.float32)
    band = cv2.GaussianBlur(g, (0, 0), 1.0) - cv2.GaussianBlur(g, (0, 0), 4.0)
    sel = dev_px
    # The gate review of Day 8 (prove_plate|ifexp): every case of the line-energy ratio and of the pattern's
    # correlation is said here. An empty region is no measurement: its value is None, the reason is named, and the
    # proof does not hold (an empty device footprint read as a ratio of 0.0 and a correlation of 0.0, and passed).
    ratio, ncc, detected_energy = None, None, None
    if inside is None:
        not_measured.append('the device footprint is empty: no line energy or line pattern is measured over it')
    if outside is None:
        not_measured.append('no plate is left clear of our elements to compare the device\'s line energy with')
    if inside is not None and outside is not None:
        if outside > 1e-6:
            ratio = inside / outside
        elif inside < 1e-6:
            # a flat plate everywhere: both energies measured and essentially zero, so the device's place carries no
            # line system, as nowhere else does: the ratio is recorded as 0.0 and this part of the proof holds
            ratio = 0.0
        else:
            # line energy over the device and none elsewhere: no ratio to state (it was recorded as 99.0), and the
            # proof does not hold
            # Day 8 residual (the unbounded case): both energies were measured, so this is a MEASURED detection of a
            # line system, never a missing measurement — recorded as line_system_detected with the energy over the
            # device, outside not_measured (it was filed there); the ratio stays None and the proof does not hold
            detected_energy = inside
    if inside is not None:
        if band[sel].std() <= 1e-6:
            # the plate is flat under the device: no line pattern there to correlate, a measured 0.0, and it holds
            ncc = 0.0
        elif lines_only[sel].std() > 1e-6:
            # Day 8 residual (the correlation guard): the guard above reads band, but |band| is what is correlated —
            # an even |band| over the device (band alternating +c and -c) made np.corrcoef NaN, and NaN was stored.
            # The correlation is taken only where |band| varies, and one that is still not a finite number is None
            # and named, never stored
            pattern = np.abs(band[sel])
            if pattern.std() <= 1e-6:
                not_measured.append('the plate\'s line energy is even in strength over the device (|band| does not vary '
                                    'there): the line pattern\'s correlation is undefined, so it is not measured')
            else:
                correlation = float(np.corrcoef(pattern, lines_only[sel])[0, 1])
                if np.isfinite(correlation):
                    ncc = correlation
                else:
                    not_measured.append('the line pattern\'s correlation over the device came out %r: it is not measured' % correlation)
        else:
            not_measured.append('our device\'s lines fill their whole footprint: the line pattern\'s correlation is not measured')
    # Day 8 residual (holds): every value is read explicitly, so one that is None (a read that failed, a mark matched
    # at no scale, an unbounded ratio, a correlation not measured) never reads as a pass — `not latin` read a failed
    # OCR's None as "no copy found", and the unbounded ratio's None no longer rests on not_measured to stop the chain
    holds = (not not_measured and latin == [] and ar == [] and mark['score'] is not None and mark['score'] < 0.45
             and ratio is not None and ratio <= 1.6 and ncc is not None and ncc <= 0.2)
    proof = {'latin_copy_found': latin, 'arabic_copy_found': ar, 'mark_best_score': mark['score'],
             'device_line_energy_ratio': None if ratio is None else round(ratio, 3),
             'device_pattern_ncc': None if ncc is None else round(ncc, 3),
             'thresholds': {'mark_score': 0.45, 'line_energy_ratio': 1.6, 'pattern_ncc': 0.2}, 'holds': holds}
    if detected_energy is not None:
        proof['line_system_detected'] = True
        proof['device_line_energy'] = round(detected_energy, 3)
    if not_measured:
        proof['not_measured'] = not_measured
    return proof


def banding_proxy(png) -> dict:
    """A proxy for a banded gradient or a hard-band glow: the largest step between neighbouring pixels of the plate
    softened by a 4 px blur (a smooth ground steps by a level or two; a hard band by many), and the share of the
    plate where such steps line up."""
    import cv2
    import numpy as np
    g = cv2.GaussianBlur(_gray(png).astype(np.float32), (0, 0), 4.0)
    steps = np.maximum(np.abs(np.diff(g, axis=0))[:, :-1], np.abs(np.diff(g, axis=1))[:-1, :])
    p999 = float(np.percentile(steps, 99.9))
    return {'p99_9_step': round(p999, 2), 'share_over_3': round(float((steps > 3).mean()), 5), 'holds': p999 <= 3.0}


# --- the measured checks, met by construction (§3a; D-D8-6) ---------------------------------------------------------

def _lum(rgb):
    def ch(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(rgb1, rgb2) -> float:
    a, b = sorted((_lum(rgb1), _lum(rgb2)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def _rgb(hex_value):
    h = hex_value.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _all_lines(lay):
    for key, value in lay['lines'].items():
        for i, ln in enumerate(value if isinstance(value, list) else [value]):
            yield (key if not isinstance(value, list) else f'{key}.{i}'), key, ln


def ground_under(lay, box, plate_png=None):
    """The ground a line stands on: the median of the plate's pixels under its box (the plate is clean there), or the
    flat ground."""
    if not plate_png:
        return _rgb(lay['ink']['dominant'])
    import numpy as np
    from PIL import Image as PILImage
    with PILImage.open(plate_png) as im:
        arr = np.asarray(im.convert('RGB'))
    x0, y0, x1, y1 = (_px(v) for v in box)
    patch = arr[max(0, y0):max(y0 + 1, y1), max(0, x0):max(x0 + 1, x1)].reshape(-1, 3)
    return tuple(int(v) for v in np.median(patch, axis=0))


def fix_contrast(lay, plate_png=None) -> list:
    """10-07: a line that fails its contrast gets a colour from the spec's own roles, automatically — the first role
    that passes, in the order type, accent, secondary. Returns what changed."""
    changed = []
    for label, key, ln in _all_lines(lay):
        ground = ground_under(lay, ln['box'], plate_png)
        need = 4.5 if (ln['alif_mm'] or ln['cap_mm']) < 4.0 else 3.0
        if contrast(_rgb(lay['roles'][key]), ground) >= need:
            continue
        for role in ('type', 'accent', 'secondary'):
            if contrast(_rgb(lay['ink'][role]), ground) >= need:
                changed.append('%s: %s → %s (%s), contrast %.2f' % (key, lay['roles'][key], lay['ink'][role], role,
                                                                   contrast(_rgb(lay['ink'][role]), ground)))
                lay['roles'][key] = lay['ink'][role]
                break
    return changed


def measured_checks(lay, plate_png=None, truthful_png=None) -> dict:
    """Every measured check of §3a on the build, each with its number; issues apart from failures."""
    import itertools
    rows, issues = [], []
    lines = list(_all_lines(lay))
    for label, key, ln in lines:
        ground = ground_under(lay, ln['box'], plate_png)
        height = ln['alif_mm'] or ln['cap_mm']
        need = 4.5 if height < 4.0 else 3.0
        c = contrast(_rgb(lay['roles'][key]), ground)
        rows.append({'check': 'contrast', 'line': label, 'value': round(c, 2), 'need': need, 'holds': c >= need})
    name_cap = min(ln['cap_mm'] for _l, k, ln in lines if k == 'name')
    rows.append({'check': 'name cap height ≥ 7 mm', 'value': round(name_cap, 2), 'holds': name_cap >= 7.0})
    info = [ln for _l, k, ln in lines if k == 'net'][0]
    sign = 0.72 * info['size_mm']
    rows.append({'check': '℮ ≥ 3 mm (drawn where the line\'s capitals reach 3 mm)', 'value': round(sign, 2), 'holds': sign >= 3.0})
    smallest = min(ln['size_pt'] for _l, _k, ln in lines)
    rows.append({'check': 'no printed line under 5.0 pt', 'value': round(smallest, 2), 'holds': smallest >= 5.0})
    en = [ln for _l, k, ln in lines if k == 'descriptor_en'][0]
    ar = [ln for _l, k, ln in lines if k == 'descriptor_ar'][0]
    ratio = ar['alif_mm'] / en['cap_mm']
    rows.append({'check': 'Arabic alif ≥ 90 % of its Latin pair\'s capitals', 'value': round(ratio, 3), 'holds': ratio >= 0.9})
    step = abs(ar['weight'] - en['weight'])
    rows.append({'check': 'Arabic stroke within one weight step', 'value': '%d vs %d' % (ar['weight'], en['weight']), 'holds': step <= 100})
    names = ' '.join(ln['text'] for _l, k, ln in lines if k == 'name')
    copy_ok = (names == COPY['name'] and en['text'] == COPY['descriptor_en'] and ar['text'] == COPY['descriptor_ar']
               and [ln['text'] for _l, k, ln in lines if k == 'shades'] == [COPY['shades']] and info['text'] == COPY['net'])
    rows.append({'check': 'copy identical to the brief', 'value': copy_ok, 'holds': copy_ok})
    prop = abs((W / H) - (LID_PX[0] / LID_PX[1])) / (W / H)
    rows.append({'check': 'panel proportion exact (190 × 120)', 'value': '%.4f %%' % (prop * 100), 'holds': prop < 0.001})
    boxes = {label: ln['box'] for label, _k, ln in lines}
    boxes['logo'] = lay['logo']
    crossings = dev.intrusions(lay['device'], list(boxes.values()))
    overlaps = [(a, b) for (a, ba), (b, bb) in itertools.combinations(boxes.items(), 2)
                if min(ba[2], bb[2]) - max(ba[0], bb[0]) > 0.2 and min(ba[3], bb[3]) - max(ba[1], bb[1]) > 0.2]
    rows.append({'check': 'no text over the device or another line', 'value': {'device_marks_in_text': len(crossings),
                 'overlapping_lines': overlaps}, 'holds': not crossings and not overlaps})
    if plate_png:
        band = banding_proxy(plate_png)
        rows.append({'check': 'no banded gradient or hard-band glow (proxy)', 'value': band, 'holds': band['holds']})
    if truthful_png:
        import numpy as np
        from PIL import Image as PILImage
        with PILImage.open(truthful_png) as im:
            hsv = np.asarray(im.convert('RGB').resize((384, 243)).convert('HSV')).reshape(-1, 3)
        coloured = hsv[hsv[:, 1] > 40]
        if len(coloured):
            hist = np.bincount((coloured[:, 0].astype(int) * 12) // 256, minlength=12)
            top = max(hist[i] + hist[(i + 1) % 12] for i in range(12)) / len(hsv)
            if top >= 0.85:
                issues.append('one hue family covers %.0f %% of the lid' % (top * 100))
    families = {ln['stem'].split('[')[0].split('-')[0] for _l, k, ln in lines if not ln['arabic']}
    if len(families) > 2:
        issues.append('more than two Latin families: %s' % sorted(families))
    return {'checks': rows, 'all_hold': all(r['holds'] for r in rows), 'issues': issues,
            'cannot_meet': ['%s: %s' % (r['check'] + (' — ' + r['line'] if 'line' in r else ''), r['value']) for r in rows if not r['holds']]}


# --- the files a build writes -----------------------------------------------------------------------------------------

def _d(points, closed):
    return 'M ' + ' L '.join('%.3f %.3f' % p for p in points) + (' Z' if closed else '')


def write_svg(lay, plate_png, out_svg) -> str:
    """A layered SVG (millimetres): PLATE or GROUND · DEVICE (BLIND shown flat in its own layer) · LOGO · TYPE · the
    finish plates as hidden layers. Type stays live text in its face."""
    from xml.sax.saxutils import escape, quoteattr
    from apps.ire import brand_mark
    ink, roles = lay['ink'], lay['roles']
    out = ['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="%gmm" height="%gmm" viewBox="0 0 %g %g">' % (W, H, W, H)]
    if plate_png:
        out.append('<g id="PLATE"><image xlink:href=%s x="0" y="0" width="%g" height="%g" preserveAspectRatio="none"/></g>' % (quoteattr(Path(plate_png).name), W, H))
    else:
        out.append('<g id="GROUND"><rect x="0" y="0" width="%g" height="%g" fill="%s"/></g>' % (W, H, ink['dominant']))
    inked, blind, plates = [], [], {}
    for m in lay['device']['marks']:
        colour = ink[m['ink']]
        el = ('<path d="%s" fill="%s"/>' % (_d(m['points'], True), colour)) if m['fill'] else \
             ('<path d="%s" fill="none" stroke="%s" stroke-width="%g"/>' % (_d(m['points'], m['closed']), colour, m['width']))
        (blind if m['ink'] == 'blind' else inked).append(el)
        for f in m['finishes']:
            name = FOIL_PLATES[lay['direction']].get(m['ink'], 'FOIL') if f == 'foil' else f.upper()
            plates.setdefault(name, []).append(el.replace(colour, '#000000'))
    if lay.get('rule'):
        x0, y0, x1, y1 = lay['rule']
        el = '<path d="M %.3f %.3f L %.3f %.3f" stroke="%s" stroke-width="%g"/>' % (x0, (y0 + y1) / 2, x1, (y0 + y1) / 2, roles['rule'], y1 - y0)
        inked.append(el)
        plates.setdefault('FOIL_GOLD', []).append(el.replace(roles['rule'], '#000000'))
    out.append('<g id="DEVICE">%s</g>' % ''.join(inked))
    if blind:
        out.append('<g id="BLIND-shown-flat-tone-on-tone">%s</g>' % ''.join(blind))
    master = brand_mark.approved_master()['master']
    x0, y0, x1, y1 = lay['logo']
    d = []
    for sg in brand_mark.placed_segments(master, x0, y0, x1 - x0, y1 - y0):
        d.append({'M': 'M %.3f %.3f' % (getattr(sg, 'x', 0), getattr(sg, 'y', 0)), 'L': 'L %.3f %.3f' % (getattr(sg, 'x', 0), getattr(sg, 'y', 0)),
                  'C': 'C %.3f %.3f %.3f %.3f %.3f %.3f' % (getattr(sg, 'x1', 0), getattr(sg, 'y1', 0), getattr(sg, 'x2', 0), getattr(sg, 'y2', 0), getattr(sg, 'x', 0), getattr(sg, 'y', 0)),
                  'Z': 'Z'}[sg.op])
    logo = '<path d="%s" fill="%s" fill-rule="nonzero"/>' % (' '.join(d), roles['logo'])
    out.append('<g id="LOGO">%s</g>' % logo)
    if lay['direction'] in ('A', 'C') and not lay.get('overrides', {}).get('logo_ink'):
        plates.setdefault(FOIL_PLATES[lay['direction']]['accent' if lay['direction'] == 'A' else 'secondary'], []).append(logo.replace(roles['logo'], '#000000'))
    texts = []
    for label, key, ln in _all_lines(lay):
        family = ln['label']
        anchor = 'end' if (ln['align'] == 'right' or ln['arabic']) else 'start'
        x = ln['box'][2] if anchor == 'end' else ln['x']
        texts.append('<text x="%.3f" y="%.3f" font-family=%s font-size="%.3f" fill="%s"%s text-anchor="%s">%s</text>' % (
            x, ln['baseline'], quoteattr(family), ln['size_mm'], roles[key],
            (' letter-spacing="%.3f"' % (ln['tracking_em'] * ln['size_mm'])) if ln['tracking_em'] else '', anchor, escape(ln['shown'])))
    out.append('<g id="TYPE">%s</g>' % ''.join(texts))
    for name, els in plates.items():
        out.append('<g id="FINISH-PLATE-%s" style="display:none">%s</g>' % (name, ''.join(els)))
    out.append('</svg>')
    Path(out_svg).write_text('\n'.join(out))
    return str(out_svg)


def finish_sheet(ai_path, out_png) -> dict:
    """The flat finish sheet: each finish plate of the .ai (pages 2…) drawn in its own colour over the lid's outline,
    labelled — the foil and deboss masks at a glance."""
    import fitz
    import numpy as np
    from PIL import Image as PILImage, ImageDraw, ImageFont
    colours = {'FOIL_GOLD': (203, 168, 125), 'FOIL_ROSE_GOLD': (201, 154, 132), 'DEBOSS': (70, 70, 80), 'EMBOSS': (60, 110, 170)}
    pdf = fitz.open(str(ai_path))
    sheet = np.full((LID_PX[1] + 60, LID_PX[0], 3), 246, np.uint8)
    legend = []
    zoom = LID_PX[0] / pdf[0].rect.width
    for i in range(1, pdf.page_count):
        page = pdf[i]
        label = page.get_text().strip().splitlines()[-1] if page.get_text().strip() else 'PLATE %d' % i
        name = label.replace('FINISH PLATE ', '').split(' - ')[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
        on = arr[:LID_PX[1], :LID_PX[0]].mean(axis=2) < 128
        on[:int(9 * PX_PER_MM), :int(110 * PX_PER_MM)] = False          # the plate's own label, not the mask
        sheet[60:60 + on.shape[0], :on.shape[1]][on] = colours.get(name, (120, 120, 120))
        legend.append((name, colours.get(name, (120, 120, 120)), int(on.sum())))
    im = PILImage.fromarray(sheet)
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 60, LID_PX[0] - 1, 60 + LID_PX[1] - 1), outline=(0, 0, 0))
    font = ImageFont.truetype(str(Path(settings.BASE_DIR) / 'static' / 'fonts' / 'NotoSans-Bold.ttf'), 22)
    x = 10
    for name, colour, n in legend:
        draw.rectangle((x, 18, x + 28, 42), fill=colour)
        draw.text((x + 36, 16), name, fill=(0, 0, 0), font=font)
        x += 60 + int(draw.textlength(name, font=font))
    im.save(out_png)
    return {'path': str(out_png), 'plates': [{'plate': n, 'pixels': c} for n, _col, c in legend]}


def media_map(lay, plate_rec, ai_record) -> dict:
    s = spec(lay['direction'])
    els = [{'element': 'ground', 'medium': 'raster plate painted by the image model, cleaned under our elements' if plate_rec else 'flat spot colour',
            'colour': lay['ink']['dominant'], **({'file': Path(plate_rec['plate']).name, 'ppi_at_190mm': round(LID_PX[0] / (W / 25.4))} if plate_rec else {})}]
    by_ink = {}
    for m in lay['device']['marks']:
        by_ink.setdefault((m['ink'], tuple(m['finishes']), bool(m['fill'])), 0)
        by_ink[(m['ink'], tuple(m['finishes']), bool(m['fill']))] += 1
    for (role, fins, filled), n in by_ink.items():
        els.append({'element': 'device (%s, %d %s)' % (lay['device']['kind'], n, 'shapes' if filled else 'lines'), 'medium': 'vector',
                    'ink': 'none — blind' if role == 'blind' else lay['ink'][role], 'finishes': list(fins)})
    if lay.get('rule'):
        els.append({'element': 'rule', 'medium': 'vector', 'ink': lay['roles']['rule'], 'finishes': ['foil']})
    els.append({'element': 'logo', 'medium': 'the approved vector master', 'ink': lay['roles']['logo'],
                'finishes': ['foil'] if lay['direction'] in ('A', 'C') and not lay.get('overrides', {}).get('logo_ink') else []})
    for label, key, ln in _all_lines(lay):
        els.append({'element': label, 'medium': 'live type', 'text': ln['text'], 'face': ln['label'], 'size_pt': round(ln['size_pt'], 2),
                    'cap_or_alif_mm': round(ln['alif_mm'] or ln['cap_mm'], 2), 'ink': lay['roles'][key],
                    'finishes': ['emboss'] if (lay['direction'] == 'B' and key == 'name') else []})
    return {'schema': 'day8_media_map/1.0', 'direction': lay['direction'], 'option': lay['option'], 'spec_media_map': s['media_map'],
            'elements': els, 'finish_plates': ai_record}


def designer_eye(read, lay) -> list:
    """Where the build differs from the sketch it came from (a report, not a gate)."""
    out = list(read['notes'])
    m = read['measured']
    pairs = {'name': lay['boxes'].get('name.0'), 'descriptor_en': lay['boxes']['descriptor_en'], 'logo': lay['logo']}
    for key, built in pairs.items():
        got = m[key]['box_mm'] if key == 'logo' else m[key]
        if got is None or built is None:
            continue
        out.append('%s: sketch at (%.1f, %.1f) mm, %.1f mm tall; build at (%.1f, %.1f) mm, %.1f mm tall' % (
            key, got[0], got[1], got[3] - got[1], built[0], built[1], built[3] - built[1]))
    return out


def build(direction: str, option: dict, sketch_id: str, *, concept_id=None, paint=True, overrides=None, plate_from=None,
          client=None) -> dict:
    """One truthful build from its chosen sketch: read → layout (our vectors at the sketch's places, the spec's sizes)
    → the picture painted around them and cleaned (A, C; B has no plate) → proof → checks (contrast fixed by role) →
    truthful.png, .ai (+ .pdf), layered .svg, media-map.json, finish sheet, checks.json, designer-eye.json."""
    import shutil
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.pipeline.services.concept_sketches import SKETCHES
    out = CONCEPTS / (concept_id or sketch_id)
    out.mkdir(parents=True, exist_ok=True)
    sk = SKETCHES / sketch_id
    read = read_sketch(direction, option, sk / 'lid.png', out)
    lay = layout(direction, option, anchors=read['anchors'], overrides=overrides)
    plate_rec, proof = None, None
    if direction in PLATE_GROUND and paint:
        plate_rec = plate_from or paint_plate(direction, lay, sk / 'sketch.png', out, client=client)
        proof = prove_plate(direction, lay, plate_rec['plate'], out)
    plate = plate_rec['plate'] if plate_rec else None
    changed = fix_contrast(lay, plate)
    truthful = render(document(lay, plate=plate), out / 'truthful.png', frame=False)
    usage = {}
    emit_pdf_ai(document(lay, plate=plate, view=False), str(out / 'truthful.ai'), usage_out=usage)
    shutil.copyfile(out / 'truthful.ai', out / 'truthful.pdf')
    if plate and Path(plate).resolve() != (out / 'plate.png').resolve():
        shutil.copyfile(plate, out / 'plate.png')
    write_svg(lay, out / 'plate.png' if plate else None, out / 'truthful.svg')
    sheet = finish_sheet(out / 'truthful.ai', out / 'finish-sheet.png')
    checks = measured_checks(lay, plate, out / 'truthful.png')
    checks['contrast_fixed_by_role'] = changed
    if proof is not None:
        checks['plate_proof'] = proof
        if not proof['holds']:
            # the gate review of Day 8: the plate proof is one of the build's checks. all_hold (and so build.json's
            # checks_hold) was computed before the proof was added, and a failing proof reached only cannot_meet
            checks['all_hold'] = False
            checks['cannot_meet'].append('the plate proof: %s' % json.dumps({k: proof[k] for k in proof if k != 'thresholds'}))
    (out / 'checks.json').write_text(json.dumps(checks, ensure_ascii=False, indent=1) + '\n')
    (out / 'media-map.json').write_text(json.dumps(media_map(lay, plate_rec, sheet['plates']), ensure_ascii=False, indent=1) + '\n')
    eye = designer_eye(read, lay)
    (out / 'designer-eye.json').write_text(json.dumps({'sketch': sketch_id, 'differences': eye, 'read': {
        k: v for k, v in read.items() if k != 'ocr_words'}}, ensure_ascii=False, indent=1, default=str) + '\n')
    record = {'concept': out.name, 'direction': direction, 'option': option, 'sketch': sketch_id, 'truthful': truthful,
              'plate': plate_rec, 'checks_hold': checks['all_hold'], 'cannot_meet': checks['cannot_meet'],
              'issues': checks['issues'], 'overrides': overrides or {}, 'device': {k: v for k, v in lay['device'].items() if k != 'marks'},
              'notes': lay['notes']}
    (out / 'build.json').write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str) + '\n')
    return record
