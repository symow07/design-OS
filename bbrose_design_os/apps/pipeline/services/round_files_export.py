"""Millimetre-based, six-layer execution files with live type and spot foil.

PDF compatibility and an actual Illustrator save/reopen are reported separately.
The worker uses native=True; isolated PDF fixtures must explicitly opt out.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
import unicodedata
import xml.etree.ElementTree as ET

import arabic_reshaper
from bidi.algorithm import get_display
import fitz
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
import numpy as np
from PIL import Image

from .round_flow import write_json

PT = 72 / 25.4
# the file's law (the owner, 2026-10-30, part 1B), bottom to top: one flat GROUND, the MOTIFS (a sub-layer per panel, each
# motif its own named object), the finishes, the WORDS (the approved logo and live type), the DIE, locked and non-printing,
# with its sub-layers. Nothing else is ever a layer of a print file (print_check; law_check).
LAYERS = ('GROUND', 'MOTIFS', 'RELIEF', 'FOIL', 'WORDS', 'DIE')
PRINT_LAYERS = LAYERS[:5]
DIE_SUBLAYERS = {'cut': 'CUT', 'fold': 'CREASE', 'perf': 'PERF', 'half_cut': 'HALF-CUT', 'glue': 'GLUE', 'safe': 'SAFE', 'bleed': 'BLEED'}
#: a raster covering more of a panel than this is a painted scene, not a motif: the die and its art are one picture again
MOTIF_MAX_SHARE = 0.6
REPO = Path(__file__).resolve().parents[4]
LOGO = REPO / 'bbrose_design_os/docs/brand/mark/bbrose-logo.svg'
LOGO_SHA256 = 'ccf120cef3e8317dc0a3dce36673709a104e9456a4eeb15b36722103d65b19ed'


# --- the pinned faces' metrics and the PDF's layers (from round_balm_master, the consolidation of 2026-10-28) ---

FONT_PATHS = {
    'latin': REPO / 'materials/fonts/dm-sans/fonts_dm-sans_dmsans-regular_1adb096acaa3d14f.ttf',
    'arabic': REPO / 'materials/fonts/almarai/fonts_almarai_almarai-regular_94cc03a8a668a865.ttf',
}


def rgb(hexcolor):
    return tuple(int(hexcolor.lstrip('#')[i:i+2], 16)/255 for i in (0,2,4)) if isinstance(hexcolor,str) else hexcolor


def shaped(copy, face):
    if face != 'arabic': return copy
    cmap = TTFont(FONT_PATHS[face]).getBestCmap()
    s = get_display(arabic_reshaper.reshape(copy))
    # Some fonts encode the isolated glyph at the basic Unicode scalar only.
    # This canonical equivalent is used ONLY for absent presentation forms.
    return ''.join(c if ord(c) in cmap else unicodedata.normalize('NFKC', c) for c in s)


def glyph_metrics(copy, face='latin'):
    font = TTFont(FONT_PATHS[face]); gs=font.getGlyphSet(); cmap=font.getBestCmap(); u=font['head'].unitsPerEm
    boxes=[]; advance=0; missing=[]
    for c in shaped(copy,face):
        name=cmap.get(ord(c))
        if name is None: missing.append(c); continue
        pen=BoundsPen(gs); gs[name].draw(pen)
        if pen.bounds:
            x0,y0,x1,y1=pen.bounds; boxes.append((advance+x0,y0,advance+x1,y1))
        advance += font['hmtx'][name][0]
    box=(min(x[0] for x in boxes), min(x[1] for x in boxes), max(x[2] for x in boxes), max(x[3] for x in boxes)) if boxes else (0,0,0,0)
    return {'box_em':[x/u for x in box], 'advance_em':advance/u,'missing':missing}


def set_layers(doc,names):
    # New document for each reading: hidden locks are retained in the file, not
    # removed to falsify editable Illustrator layers.
    ids=doc.get_ocgs();doc.set_layer(-1,on=[k for k,v in ids.items() if v['name'] in names],off=[k for k,v in ids.items() if v['name'] not in names])


def raster(doc, dpi=300,clip=None):
    # set_layer changes the PDF configuration, while MuPDF can retain its
    # previous viewer state. A fresh in-memory parse applies that configuration
    # without unlocking layers or changing any bytes of the saved artwork.
    if doc.get_ocgs():
        intended=set(doc.get_layer().get('on',[]))
        names={v['name'] for k,v in doc.get_ocgs().items() if k in intended}
        shown={r['text'] for r in doc.layer_ui_configs() if r['on']}
        if names!=shown:
            with fitz.open(stream=doc.tobytes(),filetype='pdf') as fresh:
                pix=fresh[0].get_pixmap(dpi=dpi,alpha=False,clip=clip)
                return np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,pix.n)[...,:3].copy()
    pix=doc[0].get_pixmap(dpi=dpi,alpha=False,clip=clip)
    return np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,pix.n)[...,:3].copy()


FONT_PINS = {'latin': '1adb096acaa3d14f5ed678e99b808b0c8800f62cb342fa5c276298ad8030b458',
             'arabic': '94cc03a8a668a8657735a39947fc4ab26a45f60dfde20e892f5d4bae968563c0'}
FONT_NAMES = {'latin': 'DMSans-Regular', 'arabic': 'Almarai-Regular'}
FOIL_NAME = 'Gold_Foil'
FOIL_CMYK = (.12, .28, .78, .10)
# Illustrator serializes fractional point sizes with small floating-point drift.
# Compare measured differences, never decimal rounding bins (which have edges).
NATIVE_TEXT_SIZE_TOLERANCE_PT = .0001


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _cmyk(color):
    values = tuple(rgb(color))
    if len(values) == 4:
        return values
    if len(values) != 3 or any(not 0 <= value <= 1 for value in values):
        raise ValueError('A process colour must be RGB or CMYK components between zero and one')
    source = fitz.Pixmap(fitz.csRGB, 1, 1, bytes(round(value * 255) for value in values), False)
    converted = fitz.Pixmap(fitz.csCMYK, source)
    return tuple(value / 255 for value in converted.samples)


#: the GRANTED font census (Day 6) and the exclusion list (D-D7-1) the writer checks its pinned faces against (moved
#: here from apps.ire.font_pool, 2026-10-29: the writer reads exactly these two records)
FONT_CENSUS = REPO / 'docs/audit/day-6/library/fonts-granted.json'
FONTS_EXCLUDED = REPO / 'docs/audit/day-7/library/fonts-excluded.json'


def granted_faces():
    """The GRANTED census's faces by their file's SHA-256."""
    out = {}
    for face in json.loads(FONT_CENSUS.read_text(encoding='utf-8'))['faces']:
        if face['source_sha256']:
            out.setdefault(face['source_sha256'], []).append(face)
    return out


def font_records():
    """Validate the actual font bytes against the GRANTED census: each pinned face's file by its hash, in the GRANTED
    pool, not on the exclusion list, and — checked since 2026-10-29 — named in the census by the PostScript name the
    live type sets in Illustrator, at weight 400."""
    granted = granted_faces()
    excluded = {row['sha256'] for row in json.loads(FONTS_EXCLUDED.read_text(encoding='utf-8'))['files']}
    result = {}
    for face, path in FONT_PATHS.items():
        digest = sha(path)
        if digest != FONT_PINS[face] or digest not in granted or digest in excluded:
            raise ValueError('The execution font is not its pinned GRANTED face: ' + face)
        named = [row for row in granted[digest] if row['names']['postscript_name'] == FONT_NAMES[face]
                 and row['weight_class'] == 400 and row['pool'] == 'GRANTED']
        if not named:
            raise ValueError('The census does not name the pinned %s face %s at weight 400.' % (face, FONT_NAMES[face]))
        result[face] = {'path': str(path), 'sha256': digest, 'postscript_name': FONT_NAMES[face],
                        'pool': 'GRANTED', 'licence_evidence': named[0]['pool_basis']['evidence']}
    return result


def _numbers(value, count, label, *, positive=False):
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise ValueError(label + ' has the wrong dimensions')
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
           or (positive and x <= 0) for x in value):
        raise ValueError(label + ' must contain finite millimetre measurements')
    return list(map(float, value))


def _box(value):
    box = _numbers(value, 4, 'box_mm')
    if box[2] <= box[0] or box[3] <= box[1]:
        raise ValueError('A placement box must have positive width and height')
    return box


def _rotation(value):
    if value not in (0, 90, 180, 270):
        raise ValueError('Only quarter-turn rotations are supported')
    return value


def _plain_line(copy):
    return isinstance(copy, str) and bool(copy.strip()) and '\n' not in copy and '\r' not in copy


def _check_script(copy, face):
    if face not in FONT_PATHS:
        raise ValueError('Use the pinned Latin or Arabic face')
    letters = [unicodedata.name(char, '') for char in copy if unicodedata.category(char).startswith('L')]
    if face == 'arabic' and any('LATIN' in name for name in letters):
        raise ValueError('Latin words cannot be set in the Arabic face; split the type run')
    if face == 'latin' and any('ARABIC' in name for name in letters):
        raise ValueError('Arabic words must use the Arabic engine and face; split the type run')


def _vector_svg(path):
    raw = Path(path).read_bytes()
    root = ET.fromstring(raw)
    allowed = {'svg', 'g', 'path', 'rect', 'line', 'polyline', 'polygon', 'circle', 'ellipse',
               'defs', 'clipPath', 'title', 'desc', 'metadata'}
    for node in root.iter():
        if node.tag.rsplit('}', 1)[-1] not in allowed:
            raise ValueError('Foil and logo SVGs may contain vector geometry only')
        if any(key.rsplit('}', 1)[-1] in ('href', 'src') for key in node.attrib):
            raise ValueError('An execution SVG cannot reference external assets')
    return raw


def _fitted_svg_strokes(raw, box, rotation):
    """Read the opt-in fitted network in physical mm, before any import."""
    root = ET.fromstring(raw)
    viewport = [float(value) for value in root.attrib['viewBox'].split()]
    if (len(viewport) != 4 or not all(math.isfinite(value) for value in viewport) or
            viewport[:2] != [0., 0.] or min(viewport[2:]) <= 0 or rotation != 0):
        raise ValueError('Fitted strokes require an unrotated physical-mm SVG viewBox')
    for key, expected in (('width', viewport[2]), ('height', viewport[3])):
        value = root.attrib[key]
        if not value.endswith('mm') or not math.isclose(float(value[:-2]), expected, abs_tol=1e-7):
            raise ValueError('Fitted stroke viewport units must be physical millimetres')
    if (abs(box[2]-box[0]-viewport[2]) > 1e-7 or abs(box[3]-box[1]-viewport[3]) > 1e-7 or
            'transform' in root.attrib):
        raise ValueError('Fitted stroke placement must preserve physical size without scaling')
    strokes = []
    for path in root:
        match = re.fullmatch(r'M\s*([\d.eE+-]+)[,\s]+([\d.eE+-]+)\s*L\s*([\d.eE+-]+)[,\s]+([\d.eE+-]+)\s*', path.attrib.get('d', ''))
        width = float(path.attrib['stroke-width'])
        if (path.tag.rsplit('}', 1)[-1] != 'path' or match is None or
                path.attrib['fill'] != 'none' or 'transform' in path.attrib or 'style' in path.attrib or
                path.attrib['stroke-linecap'] != 'round' or path.attrib['stroke-linejoin'] != 'round' or
                not math.isfinite(width) or width <= 0):
            raise ValueError('Each fitted motif path must be a finite-width, untransformed straight round stroke')
        coordinates = list(map(float, match.groups()))
        if not all(math.isfinite(value) for value in coordinates) or coordinates[:2] == coordinates[2:]:
            raise ValueError('Fitted stroke endpoints must be finite and distinct')
        strokes.append({'points_mm': [[coordinates[index]+box[0], coordinates[index+1]+box[1]]
                                      for index in (0, 2)], 'width_mm': width})
    if not strokes:
        raise ValueError('A fitted stroke network cannot be empty')
    return strokes


def measure_turned_type(item):
    """One word centred on a point and turned to any angle, counter-clockwise as seen.

    Ornament bands set their words along a path this way; the ink box is the
    axis-aligned box of the turned glyph outlines.
    """
    copy, face = item['copy'], item.get('face', 'latin')
    if not _plain_line(copy):
        raise ValueError('Each live type run must be a nonempty single line')
    _check_script(copy, face)
    centre = _numbers(item['center_mm'], 2, 'center_mm')
    size, angle = item.get('size_pt', 5), item.get('angle_deg', 0)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (size, angle)) or size <= 0:
        raise ValueError('Turned live type needs a positive point size and a finite angle')
    metric = glyph_metrics(copy, face)
    if metric['missing']:
        raise ValueError('The pinned face lacks copy glyphs: ' + repr(metric['missing']))
    b, advance = metric['box_em'], metric['advance_em'] * size
    middle = item.get('center_em_y', (b[3] + b[1]) / 2)
    cos, sin = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    # Local glyph frame: x along the advance, y down the page; turned counter-clockwise as seen.
    turn = lambda u, v: (u * cos + v * sin, -u * sin + v * cos)
    ox, oy = turn(-advance / 2, middle * size)
    origin = (centre[0] * PT + ox, centre[1] * PT + oy)
    corners = [turn(u, v) for u in (b[0] * size, b[2] * size) for v in (-b[3] * size, -b[1] * size)]
    corners = [(origin[0] + u, origin[1] + v) for u, v in corners]
    ink = [min(p[0] for p in corners) / PT, min(p[1] for p in corners) / PT,
           max(p[0] for p in corners) / PT, max(p[1] for p in corners) / PT]
    return {'copy': copy, 'face': face, 'box_mm': ink, 'size_pt': size, 'align': 'center', 'rotation': 0,
            'angle_deg': angle, 'center_mm': centre, 'display': shaped(copy, face), 'metric': metric,
            'position_pt': origin, 'ink_box_mm': ink, 'advance_pt': advance, 'overflow': False}


def measure_type(item):
    """Measure the actual pinned glyph outlines at the supplied placement."""
    if 'center_mm' in item:
        return measure_turned_type(item)
    copy, face = item['copy'], item.get('face', 'latin')
    if not _plain_line(copy):
        raise ValueError('Each live type run must be a nonempty single line')
    _check_script(copy, face)
    box = _box(item['box_mm'])
    size = item.get('size_pt', 5)
    if isinstance(size, bool) or not isinstance(size, (int, float)) or not math.isfinite(size) or size <= 0:
        raise ValueError('Live type needs a positive point size')
    align = item.get('align', 'center')
    if align not in ('left', 'center', 'right'):
        raise ValueError('Invalid live-type alignment')
    rotation = _rotation(item.get('rotation', 0))
    metric = glyph_metrics(copy, face)
    if metric['missing']:
        raise ValueError('The pinned face lacks copy glyphs: ' + repr(metric['missing']))
    w, h = (box[2] - box[0]) * PT, (box[3] - box[1]) * PT
    if rotation in (90, 270):
        w, h = h, w
    b, advance = metric['box_em'], metric['advance_em'] * size
    x = (w - advance) / 2 if align == 'center' else w - advance if align == 'right' else 0
    baseline = (h - (b[3] - b[1]) * size) / 2 + b[3] * size

    def transform(x, y):
        if rotation == 90:
            return box[0] * PT + y, box[3] * PT - x
        if rotation == 180:
            return box[2] * PT - x, box[3] * PT - y
        if rotation == 270:
            return box[2] * PT - y, box[1] * PT + x
        return box[0] * PT + x, box[1] * PT + y

    corners = [transform(xx, yy) for xx in (x + b[0] * size, x + b[2] * size)
               for yy in (baseline - b[3] * size, baseline - b[1] * size)]
    ink = [min(p[0] for p in corners) / PT, min(p[1] for p in corners) / PT,
           max(p[0] for p in corners) / PT, max(p[1] for p in corners) / PT]
    overflow = (advance > w + .01 or (b[3] - b[1]) * size > h + .01 or
                ink[0] < box[0] - .01 / PT or ink[1] < box[1] - .01 / PT or
                ink[2] > box[2] + .01 / PT or ink[3] > box[3] + .01 / PT)
    return {'copy': copy, 'face': face, 'box_mm': box, 'size_pt': size, 'align': align,
            'rotation': rotation, 'display': shaped(copy, face), 'metric': metric,
            'position_pt': transform(x, baseline), 'ink_box_mm': ink,
            'advance_pt': advance, 'overflow': overflow}


def fit_type_envelope(item, *, safe_box_mm, occupied_boxes_mm):
    """Expand a centered layout envelope without moving or resizing its type.

    The caller supplies physical safety and other text/mark boxes, excluding the
    current run. This is an explicit mechanical repair, never automatic fitting
    inside export_object. Original source geometry remains in the returned record.
    """
    if 'center_mm' in item:
        raise ValueError('An ornament word keeps its own path; envelope repair does not apply')
    original = measure_type(item)
    if original['size_pt'] < 5:
        raise ValueError('Envelope repair cannot authorize type under 5 pt')
    if original['align'] != 'center':
        raise ValueError('Envelope repair requires a fixed centered source placement')
    box, ink = original['box_mm'], original['ink_box_mm']
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    half_width = max(cx - box[0], cx - ink[0], ink[2] - cx)
    half_height = max(cy - box[1], cy - ink[1], ink[3] - cy)
    half_advance = original['advance_pt'] / PT / 2
    if original['rotation'] in (90, 270):
        half_height = max(half_height, half_advance)
    else:
        half_width = max(half_width, half_advance)
    expanded = [cx - half_width, cy - half_height, cx + half_width, cy + half_height]
    safe = _box(safe_box_mm)
    if any(expanded[index] < safe[index] - 1e-8 for index in (0, 1)) or any(
            expanded[index] > safe[index] + 1e-8 for index in (2, 3)):
        raise ValueError('Measured type envelope cannot fit the physical safe area without moving or shrinking type')
    for other in occupied_boxes_mm:
        other = _box(other)
        if min(expanded[2], other[2]) - max(expanded[0], other[0]) > 1e-8 and min(
                expanded[3], other[3]) - max(expanded[1], other[1]) > 1e-8:
            raise ValueError('Measured type envelope overlaps another source text or mark placement')
    result = dict(item, box_mm=expanded)
    measured = measure_type(result)
    if measured['overflow'] or any(abs(a - b) > 1e-8 for a, b in zip(
            original['position_pt'], measured['position_pt'])):
        raise ValueError('Envelope repair did not preserve the original type baseline and origin')
    source_box = _box(item['source_box_mm']) if 'source_box_mm' in item else list(box)
    result['source_box_mm'] = source_box
    result['type_fit'] = {'method': 'Measured envelope expansion; fixed source center, baseline, font and size',
        'source_box_mm': source_box, 'input_layout_box_mm': list(box),
        'layout_box_mm': expanded, 'ink_box_mm': measured['ink_box_mm'],
        'center_mm': [cx, cy], 'baseline_origin_pt': list(measured['position_pt']),
        'size_pt': measured['size_pt'], 'source_overflow': original['overflow'], 'overflow': False,
        'expansion_mm': [box[0] - expanded[0], box[1] - expanded[1], expanded[2] - box[2], expanded[3] - box[3]],
        'physical_safe_box_mm': safe, 'source_position_preserved': True}
    return result


class Surface:
    def __init__(self, size_mm, title, trim_box_mm=None, *, die_visible=False):
        self.size_mm = _numbers(size_mm, 2, 'size_mm', positive=True)
        self.die_visible = die_visible
        self.doc = fitz.open()
        self.ocg = {name: self.doc.add_ocg(name, on=name in PRINT_LAYERS or (name == 'DIE' and die_visible)) for name in LAYERS}
        for name, xref in self.ocg.items():
            state = 'ON' if name in PRINT_LAYERS else 'OFF'
            self.doc.xref_set_key(xref, 'Usage', f'<</Print <</PrintState /{state}>> /Export <</ExportState /{state}>>>>')
        self.doc.xref_set_key(self.doc.pdf_catalog(), 'OCProperties/D/Locked',
            '[' + f'{self.ocg["DIE"]} 0 R' + ']')
        self.page = self.doc.new_page(width=self.size_mm[0] * PT, height=self.size_mm[1] * PT)
        trim = fitz.Rect(*[x * PT for x in _box(trim_box_mm)]) if trim_box_mm else self.page.rect
        if trim.x0 < -.001 or trim.y0 < -.001 or trim.x1 > self.page.rect.x1 + .001 or trim.y1 > self.page.rect.y1 + .001:
            raise ValueError('The trim box must fit inside the physical page')
        self.page.set_trimbox(trim & self.page.rect)
        self.page.set_bleedbox(self.page.rect)
        self.fonts = font_records()
        for face, path in FONT_PATHS.items():
            self.page.insert_font(fontname=face, fontfile=str(path))
        self.title, self.rows, self.elements = title, [], []
        function = self.doc.get_new_xref()
        self.doc.update_object(function, '<</FunctionType 2 /Domain [0 1] /C0 [0 0 0 0] /C1 [' +
                               ' '.join(map(str, FOIL_CMYK)) + '] /N 1>>')
        self.spot = self.doc.get_new_xref()
        self.doc.update_object(self.spot, f'[/Separation /{FOIL_NAME} /DeviceCMYK {function} 0 R]')
        self._spot_resource(self.page.xref)

    def _spot_resource(self, owner):
        kind, value = self.doc.xref_get_key(owner, 'Resources')
        if kind == 'xref':
            resources = int(value.split()[0])
            kind, value = self.doc.xref_get_key(resources, 'ColorSpace')
            if kind == 'xref':
                self.doc.xref_set_key(int(value.split()[0]), FOIL_NAME, f'{self.spot} 0 R')
            else:
                self.doc.xref_set_key(resources, 'ColorSpace/' + FOIL_NAME, f'{self.spot} 0 R')
        else:
            self.doc.xref_set_key(owner, 'Resources/ColorSpace/' + FOIL_NAME, f'{self.spot} 0 R')

    def _spot_stream(self, xref):
        stream = self.doc.xref_stream(xref)
        if stream is None:
            return
        number = rb'[-+]?(?:\d*\.\d+|\d+\.?\d*)'
        pattern = rb'(?<!\S)(?:' + number + rb'\s+){1,4}(?:rg|RG|g|G|k|K)(?!\S)'
        def replace(match):
            stroke = match.group(0).split()[-1] in (b'RG', b'G', b'K')
            return ('/' + FOIL_NAME + (' CS 1 SCN' if stroke else ' cs 1 scn')).encode()
        self.doc.update_stream(xref, re.sub(pattern, replace, stream))

    def _process_stream(self, xref):
        stream = self.doc.xref_stream(xref)
        number = rb'[-+]?(?:\d*\.\d+|\d+\.?\d*)'
        pattern = rb'(?<!\S)((?:' + number + rb'\s+){1,4})(rg|RG|g|G|k|K)(?!\S)'
        def replace(match):
            values = [float(value) for value in match.group(1).split()]
            if len(values) == 1:
                values = values * 3
            converted = _cmyk(values)
            operator = 'K' if match.group(2) in (b'RG', b'G', b'K') else 'k'
            return (' '.join(f'{value:.8f}' for value in converted) + ' ' + operator).encode()
        self.doc.update_stream(xref, re.sub(pattern, replace, stream))

    def artwork(self, item):
        path, box = Path(item['path']).resolve(), _box(item['box_mm'])
        layer = 'MOTIFS'                    # a raster is a picture motif, unless the spec names its layer
        if 'layer' in item:
            layer = item['layer']
        with Image.open(path) as source:
            source.load()
            dimensions = list(source.size)
            alpha_min, alpha_max = source.convert('RGBA').getextrema()[3]
            has_visible_pixels = alpha_max > 0
        # An intentionally empty ink plate must remain clear. Illustrator drops
        # fully transparent image objects on import; do not invent a raster to
        # keep a meaningless object count. Its exact source remains in the record.
        if has_visible_pixels:
            raster = fitz.Pixmap(str(path))
            # Conversion changes the colour representation, never the geometry.
            # Pixmap insertion uses lossless PDF image streams plus a separate
            # grayscale alpha mask; no JPEG re-encoding is introduced.
            if raster.alpha and alpha_min == 255:
                raster = fitz.Pixmap(raster, 0)
            if raster.colorspace.n != 4:
                raster = fitz.Pixmap(fitz.csCMYK, raster)
            self.page.insert_image(fitz.Rect(*[v * PT for v in box]), pixmap=raster, keep_proportion=False,
                                   rotate=_rotation(item.get('rotation', 0)), oc=self.ocg[layer])
        self.elements.append({'name': item.get('name', path.stem), 'layer': layer, 'kind': 'raster',
            'box_mm': box, 'source': str(path), 'sha256': sha(path), 'source_px': dimensions,
            'has_visible_pixels': has_visible_pixels,
            'print_colour_space': 'DeviceCMYK', 'media_conversion': 'MuPDF RGB-to-CMYK; lossless image storage; separate alpha mask',
            'effective_ppi': [dimensions[0] * 25.4 / (box[2] - box[0]), dimensions[1] * 25.4 / (box[3] - box[1])]})

    def vector_svg(self, item, *, logo=False):
        path = LOGO if logo else Path(item['path']).resolve()
        if logo and ('path' in item and Path(item['path']).resolve() != LOGO.resolve() or sha(LOGO) != LOGO_SHA256):
            raise ValueError('Only the pinned approved vector logo may be placed')
        raw = _vector_svg(path)
        box = _box(item['box_mm'])
        rotation = _rotation(item.get('rotation', 0))
        fitted = item.get('fitted_strokes', False)
        if not isinstance(fitted, bool) or (fitted and logo):
            raise ValueError('Fitted strokes are an explicit foil-network option, never a logo conversion')
        expected_strokes = _fitted_svg_strokes(raw, box, rotation) if fitted else None
        layer, foil = ('WORDS', bool(item.get('foil', False))) if logo else ('FOIL', True)
        first_xref = self.doc.xref_length()
        with fitz.open(stream=raw, filetype='svg') as vector:
            with fitz.open(stream=vector.convert_to_pdf(), filetype='pdf') as source:
                self.page.show_pdf_page(fitz.Rect(*[v * PT for v in box]), source, 0,
                    keep_proportion=logo, rotate=rotation, oc=self.ocg[layer])
        for xref in range(first_xref, self.doc.xref_length()):
            if self.doc.xref_get_key(xref, 'Subtype')[1] == '/Form':
                if foil:
                    self._spot_resource(xref)
                    self._spot_stream(xref)
                else:
                    self._process_stream(xref)
        self.elements.append({'name': item.get('name', 'approved logo' if logo else path.stem),
            'layer': layer, 'kind': 'vector', 'box_mm': box, 'rotation': rotation,
            'source': str(path), 'sha256': sha(path), 'foil': foil,
            'approved_master': logo})
        if expected_strokes is not None:
            self.elements[-1]['fitted_strokes'] = expected_strokes

    def vector_piece(self, item, *, layer='MOTIFS'):
        """One named vector object: its paths ({'d': [['M', x, y], ['L', x, y], ['C', x1, y1, x2, y2, x, y], ['Z']], 'fill':
        hex or None, 'stroke': hex or None, 'stroke_mm': width}, mm on the page), as clean curves."""
        xs, ys, closed_fills = [], [], True
        shape = self.page.new_shape()
        for path in item['paths']:
            at, start = None, None
            for op in path['d']:
                if op[0] == 'M':
                    at = start = fitz.Point(op[1] * PT, op[2] * PT)
                    xs.append(op[1]), ys.append(op[2])
                elif op[0] == 'L':
                    to = fitz.Point(op[1] * PT, op[2] * PT)
                    shape.draw_line(at, to)
                    at = to
                    xs.append(op[1]), ys.append(op[2])
                elif op[0] == 'C':
                    p = [fitz.Point(op[i] * PT, op[i + 1] * PT) for i in (1, 3, 5)]
                    shape.draw_bezier(at, p[0], p[1], p[2])
                    at = p[2]
                    xs.extend((op[1], op[3], op[5])), ys.extend((op[2], op[4], op[6]))
                elif op[0] == 'Z' and at != start:
                    shape.draw_line(at, start)
                    at = start
            closed = path['d'][-1][0] == 'Z'
            fill = path.get('fill')
            closed_fills = closed_fills and (closed or not fill)
            stroke = path.get('stroke')
            shape.finish(color=_cmyk(rgb(stroke)) if stroke else None, fill=_cmyk(rgb(fill)) if fill else None,
                         width=path.get('stroke_mm', 0) * PT if stroke else 0, closePath=closed, lineCap=1, lineJoin=1,
                         oc=self.ocg[layer])
        shape.commit()
        if layer == 'FOIL':
            self._spot_stream(self.page.get_contents()[-1])
        self.elements.append({'name': item['name'], 'layer': layer, 'kind': 'vector', 'object': True, 'paths': len(item['paths']),
                              'box_mm': [min(xs), min(ys), max(xs), max(ys)], 'closed_fills': closed_fills, 'foil': layer == 'FOIL',
                              'panel': item.get('panel')})

    def path(self, item, *, layer='FOIL', color=(0, 0, 0)):
        # one ring (points_mm) or several (rings_mm: an outline and its holes, filled even-odd)
        rings = [[_numbers(point, 2, 'points_mm') for point in ring] for ring in (item['rings_mm'] if 'rings_mm' in item
                                                                                  else [item['points_mm']])]
        points = [point for ring in rings for point in ring]
        if any(len(ring) < 2 for ring in rings):
            raise ValueError('A vector path needs at least two points')
        closed = bool(item.get('closed', False))
        fill = bool(item.get('fill', closed and layer == 'FOIL'))
        width_mm = item.get('stroke_mm', 0 if fill else .15)
        if isinstance(width_mm, bool) or not isinstance(width_mm, (int, float)) or not math.isfinite(width_mm) or width_mm < 0:
            raise ValueError('Vector stroke width must be nonnegative millimetres')
        shape = self.page.new_shape()
        for ring in rings:
            shape.draw_polyline([fitz.Point(x * PT, y * PT) for x, y in ring + ([ring[0]] if len(rings) > 1 and closed else [])])
        color = _cmyk(color)
        shape.finish(color=color if width_mm else None, fill=color if fill else None,
            width=width_mm * PT, closePath=closed, even_odd=True, oc=self.ocg[layer])
        shape.commit()
        if layer == 'FOIL':
            self._spot_stream(self.page.get_contents()[-1])
        xs, ys = zip(*points)
        self.elements.append({'name': item.get('name', layer), 'layer': layer, 'kind': 'vector',
            'box_mm': [min(xs), min(ys), max(xs), max(ys)], 'points_mm': points,
            'closed': closed, 'fill': fill, 'stroke_mm': width_mm, 'foil': layer == 'FOIL'})
        if layer == 'DIE' and self.die_visible:
            self.elements[-1]['visible_on_open'] = True

    def text(self, item):
        measured = measure_type(item)
        copy, face, box, size, align, rotation, display = (measured[key] for key in (
            'copy', 'face', 'box_mm', 'size_pt', 'align', 'rotation', 'display'))
        color = item.get('color', '#202020')
        if 'center_mm' in measured:
            origin = fitz.Point(*measured['position_pt'])
            self.page.insert_text(origin, display, fontname=face, fontsize=size, color=_cmyk(color),
                                  morph=(origin, fitz.Matrix(measured['angle_deg'])), oc=self.ocg['WORDS'])
        else:
            self.page.insert_text(measured['position_pt'], display, fontname=face, fontsize=size, color=_cmyk(color),
                                  rotate=rotation, oc=self.ocg['WORDS'])
        content = self.page.get_contents()[-1]
        if item.get('foil'):
            self._spot_stream(content)
        actual = ('FEFF' + copy.encode('utf-16-be').hex()).upper().encode()
        self.doc.update_stream(content, b'/Span <</ActualText <' + actual + b'>>> BDC\n' +
                               self.doc.xref_stream(content) + b'\nEMC\n')
        ink = measured['ink_box_mm']
        row = {'name': item.get('name', copy), 'copy': copy, 'display': display, 'face': face,
               'font_sha256': FONT_PINS[face], 'font_postscript_name': FONT_NAMES[face], 'size_pt': size,
               'box_mm': box, 'ink_box_mm': ink, 'rotation': rotation, 'align': align, 'color': color,
               'foil': bool(item.get('foil')), 'at_least_5pt': size >= 5,
               'overflow': measured['overflow'],
               'missing_glyphs': measured['metric']['missing'], 'shaping': 'house Arabic joining and bidi' if face == 'arabic' else 'Latin Unicode'}
        if 'center_mm' in measured:
            row.update(center_mm=measured['center_mm'], angle_deg=measured['angle_deg'], ornament=bool(item.get('ornament')))
        if 'source_box_mm' in item:
            row['source_box_mm'] = _box(item['source_box_mm'])
        if 'type_fit' in item:
            row['type_fit'] = item['type_fit']
        self.rows.append(row)
        self.elements.append({'name': row['name'], 'layer': 'WORDS', 'kind': 'live_type',
                              'box_mm': ink, 'copy': copy, 'foil': row['foil']})

    def save(self, path):
        self.doc.set_metadata({'title': self.title, 'creator': 'Product execution files',
                              'subject': 'Live type; approved vector logo; Gold_Foil spot; engine die.'})
        self.doc.save(path, garbage=3, deflate=True)
        self.doc.close()


def _text_colour_spaces(path):
    """Audit text paint state in page/Form streams, not RGB display traces.

    This small content lexer skips PDF strings/comments and follows named colour
    spaces and Form resources. It never parses font or compressed image bytes.
    """
    evidence = []
    token_re = re.compile(rb'/[^\x00\s<>\[\]()/%]+|[-+]?(?:\d*\.\d+|\d+\.?\d*)|[A-Za-z][A-Za-z0-9*]*|[\x27\x22]')
    def tokens(stream):
        cleaned, index = bytearray(), 0
        while index < len(stream):
            byte = stream[index]
            if byte == 40:  # balanced PDF literal string, with escaped parentheses
                depth, index = 1, index + 1
                while index < len(stream) and depth:
                    if stream[index] == 92:
                        index += 2
                        continue
                    if stream[index] == 40:
                        depth += 1
                    elif stream[index] == 41:
                        depth -= 1
                    index += 1
                cleaned.extend(b' ')
            elif byte == 60 and stream[index:index + 2] != b'<<':
                end = stream.find(b'>', index + 1)
                index = len(stream) if end < 0 else end + 1
                cleaned.extend(b' ')
            elif byte == 37:
                end = stream.find(b'\n', index + 1)
                index = len(stream) if end < 0 else end + 1
                cleaned.extend(b' ')
            else:
                cleaned.append(byte)
                index += 1
        return token_re.findall(bytes(cleaned))
    with fitz.open(path) as doc:
        def resources(owner, inherited=None):
            kind, value = doc.xref_get_key(owner, 'Resources')
            if kind == 'xref':
                return int(value.split()[0]), ''
            return (owner, 'Resources/') if kind == 'dict' else inherited
        def resource(resources, key):
            if resources is None:
                return 'null', 'null'
            return doc.xref_get_key(resources[0], resources[1] + key)
        def space_name(name, current_resources):
            if name in ('DeviceCMYK', 'DeviceRGB', 'DeviceGray'):
                return name
            kind, value = resource(current_resources, 'ColorSpace/' + name)
            if kind == 'xref':
                value = doc.xref_object(int(value.split()[0]))
            def classify(value, depth=0):
                if depth > 8:
                    return 'unknown:' + name
                if value.strip() in ('/DeviceCMYK', '/DeviceRGB', '/DeviceGray'):
                    return value.strip()[1:]
                spot = re.match(r'\[\s*/(?:Separation\s+/[^\s\[\]<>]+|DeviceN\s+\[[^\]]*\])\s+', value)
                if spot:
                    alternate = value[spot.end():]
                    ref = re.match(r'(\d+)\s+0\s+R\b', alternate)
                    if ref:
                        alternate = doc.xref_object(int(ref.group(1)))
                    else:
                        direct = re.match(r'/Device(?:CMYK|RGB|Gray)\b', alternate)
                        if direct:
                            alternate = direct.group(0)
                    result = classify(alternate, depth + 1)
                    return 'spot-CMYK' if result in ('DeviceCMYK', 'ICCBased-CMYK') else 'spot-non-CMYK'
                profile = re.match(r'\[\s*/ICCBased\s+(\d+)\s+0\s+R', value)
                if profile:
                    components = doc.xref_get_key(int(profile.group(1)), 'N')[1]
                    return 'ICCBased-' + ('CMYK' if components == '4' else 'non-CMYK')
                return 'unknown:' + name
            return classify(value)
        def inspect(stream, current_resources, inherited='DeviceGray', depth=0):
            if depth > 30:
                raise ValueError('Excessive PDF form nesting')
            space, stack, operands = inherited, [], []
            for token in tokens(stream):
                if token.startswith(b'/') or re.fullmatch(rb'[-+]?(?:\d*\.\d+|\d+\.?\d*)', token):
                    operands.append(token)
                    continue
                if token == b'q':
                    stack.append(space)
                elif token == b'Q' and stack:
                    space = stack.pop()
                elif token in (b'rg', b'g', b'k'):
                    space = {b'rg': 'DeviceRGB', b'g': 'DeviceGray', b'k': 'DeviceCMYK'}[token]
                elif token == b'cs' and operands:
                    space = space_name(operands[-1].decode().lstrip('/'), current_resources)
                elif token in (b'Tj', b'TJ', b"'", b'"'):
                    evidence.append({'operator': token.decode(), 'colour_space': space})
                elif token == b'Do' and operands:
                    kind, value = resource(current_resources, 'XObject/' + operands[-1].decode().lstrip('/'))
                    if kind == 'xref':
                        xref = int(value.split()[0])
                        if doc.xref_get_key(xref, 'Subtype')[1] == '/Form':
                            inspect(doc.xref_stream(xref), resources(xref, current_resources), space, depth + 1)
                operands = []
        for page in doc:
            inspect(b'\n'.join(doc.xref_stream(xref) for xref in page.get_contents()), resources(page.xref))
    return evidence


def _geometry_segments(points, closed=False):
    values = [list(point) for point in points]
    if closed and values and values[0] != values[-1]:
        values.append(values[0])
    return [(a, b) for a, b in zip(values, values[1:]) if a != b]


def _die_geometry_check(elements, actual, tolerance_mm=.005):
    """Match every real cut/fold path, including each square opening, one to one."""
    expected = [item for item in elements if item['layer'] == 'DIE']
    unused = list(range(len(actual)))
    missing = []
    def near(a, b):
        return all(abs(x - y) <= tolerance_mm for x, y in zip(a, b))
    for index, item in enumerate(expected):
        segments = _geometry_segments(item['points_mm'], item['closed'])
        match = None
        for candidate in unused:
            other = list(actual[candidate]['segments'])
            if len(other) != len(segments) or not actual[candidate]['stroked']:
                continue
            for a, b in segments:
                found = next((j for j, (c, d) in enumerate(other)
                              if (near(a, c) and near(b, d)) or (near(a, d) and near(b, c))), None)
                if found is None:
                    break
                other.pop(found)
            else:
                match = candidate
                break
        if match is None:
            missing.append(index)
        else:
            unused.remove(match)
    return {'expected_paths': len(expected), 'actual_paths': len(actual), 'missing_indices': missing,
            'unmatched_actual_indices': unused, 'tolerance_mm': tolerance_mm,
            'holds': not missing and not unused}


def _fitted_stroke_check(elements, actual, *, native):
    """Match each declared straight stroke once; other foil stays outside this opt-in."""
    expected = [stroke for item in elements for stroke in item.get('fitted_strokes', [])]
    coordinate_tolerance, width_tolerance = .005, .0001 if native else .002
    unused = list(range(len(actual)))
    missing, matches = [], []

    def points_valid(points):
        return (isinstance(points, list) and len(points) == 2 and all(
            isinstance(point, list) and len(point) == 2 and all(
                isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)
                for value in point) for point in points))

    def near(left, right):
        return all(abs(a-b) <= coordinate_tolerance for p, q in zip(left, right) for a, b in zip(p, q))

    for index, stroke in enumerate(expected):
        found = None
        for candidate in unused:
            row = actual[candidate]
            points, width = row['points_mm'], row['width_mm']
            if (not points_valid(points) or not isinstance(width, (float, int)) or isinstance(width, bool) or
                    not math.isfinite(width) or width <= 0 or abs(width-stroke['width_mm']) > width_tolerance or
                    not row['stroked'] or row['filled'] or row['closed'] or not row['round_caps_joins']):
                continue
            if native and (not row['editable'] or row['typename'] != 'PathItem' or
                    not points_valid(row['left_mm']) or not points_valid(row['right_mm']) or
                    not near(points, row['left_mm']) or not near(points, row['right_mm'])):
                continue
            if near(points, stroke['points_mm']) or near(points[::-1], stroke['points_mm']):
                found = candidate
                break
        if found is None:
            missing.append(index)
        else:
            unused.remove(found)
            matches.append({'expected_index': index, 'actual_index': found,
                            'expected_width_mm': stroke['width_mm'], 'actual_width_mm': actual[found]['width_mm']})
    return {'expected_strokes': len(expected), 'candidate_strokes': len(actual), 'matched_strokes': matches,
            'missing_indices': missing, 'coordinate_tolerance_mm': coordinate_tolerance,
            'width_tolerance_mm': width_tolerance, 'holds': not missing,
            'scope': 'Only explicitly fitted networks; other foil paths, logos and live type are not reclassified.'}


def _pdf_fitted_strokes(path):
    with fitz.open(path) as doc:
        if not doc.get_ocgs():
            return []
        set_layers(doc, {'FOIL'})
        with fitz.open(stream=doc.tobytes(), filetype='pdf') as fresh:
            result = []
            for row in fresh[0].get_drawings():
                if row['type'] not in ('s', 'fs') or len(row['items']) != 1 or row['items'][0][0] != 'l':
                    continue
                points = [[point.x / PT, point.y / PT] for point in row['items'][0][1:]]
                result.append({'points_mm': points, 'width_mm': row['width'] / PT,
                    'stroked': row['type'] in ('s', 'fs'), 'filled': row['fill'] is not None,
                    'closed': row['closePath'], 'round_caps_joins': row['lineCap'] == (1, 1, 1) and row['lineJoin'] == 1})
            return result


def _pdf_die_geometry(path):
    with fitz.open(path) as doc:
        if not doc.get_ocgs():
            return []
        set_layers(doc, {'DIE'})
        with fitz.open(stream=doc.tobytes(), filetype='pdf') as fresh:
            result = []
            for drawing in fresh[0].get_drawings():
                segments = []
                for item in drawing['items']:
                    if item[0] == 'l':
                        segments.append(([v / PT for v in item[1]], [v / PT for v in item[2]]))
                    elif item[0] == 're':
                        r = item[1]
                        segments.extend(_geometry_segments([[p.x / PT, p.y / PT] for p in (r.tl, r.tr, r.br, r.bl)], True))
                    elif item[0] == 'qu':
                        q = item[1]
                        segments.extend(_geometry_segments([[p.x / PT, p.y / PT] for p in (q.ul, q.ur, q.lr, q.ll)], True))
                if drawing['closePath'] and segments and segments[-1][1] != segments[0][0]:
                    segments.append((segments[-1][1], segments[0][0]))
                result.append({'segments': segments, 'stroked': drawing['type'] in ('s', 'fs')})
            return result


def _raster_colour_spaces(doc):
    """Read the actual color basis, including Illustrator's indexed CMYK palettes."""
    result = []
    for image in doc[0].get_image_info(xrefs=True):
        components, name = image['colorspace'], image['cs-name']
        if image['xref']:
            pixmap = fitz.Pixmap(doc, image['xref'])
            if pixmap.colorspace is not None:
                components, name = pixmap.colorspace.n, pixmap.colorspace.name
        result.append({'components': components, 'name': image['cs-name'],
                       'encoded_components': image['colorspace'], 'base_name': name})
    return result


def read_back_ai(path, rows=(), elements=()):
    """Reopen actual PDF operators, font streams, spots and locked layer states."""
    with fitz.open(path) as doc:
        page = doc[0]
        ocgs = doc.get_ocgs()
        locked = doc.xref_get_key(doc.pdf_catalog(), 'OCProperties/D/Locked')[1]
        layers = []
        for xref, layer in ocgs.items():
            usage = doc.xref_get_key(xref, 'Usage')[1]
            if re.fullmatch(r'\d+ 0 R', usage):
                usage = doc.xref_object(int(usage.split()[0]))
            layers.append({'name': layer['name'], 'locked': bool(re.search(r'\b' + str(xref) + r' 0 R\b', locked)),
                           'printable': '/PrintState/ON' in usage.replace(' ', ''),
                           'visible': xref in doc.get_layer().get('on', [])})
        fonts = []
        for resource in page.get_fonts(full=True):
            name, extension, kind, data = doc.extract_font(resource[0])
            fonts.append({'name': name, 'embedded_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest() if data else None})
        streams = b'\n'.join(doc.xref_stream(xref) or b'' for xref in range(1, doc.xref_length()) if doc.xref_is_stream(xref))
        objects = '\n'.join(doc.xref_object(xref) for xref in range(1, doc.xref_length()))
        text = page.get_text('text')
        actual = [bytes.fromhex(value.decode()).decode('utf-16-be').lstrip('\ufeff')
                  for value in re.findall(rb'/ActualText\s*<([0-9A-Fa-f]+)>', streams)]
        traces = page.get_texttrace()
        images = page.get_image_info()
        raster_colours = _raster_colour_spaces(doc)
        size_mm = [page.rect.width / PT, page.rect.height / PT]
        trim_mm = [v / PT for v in page.trimbox]
        vector_paths = len(page.get_drawings())
    normalize = lambda value: ' '.join(unicodedata.normalize('NFKC', value).split())
    normalized = normalize(text)
    glyph_text = normalize(' '.join(''.join(chr(char[0]) for char in span['chars'] if char[0] >= 0) for span in traces))
    copies = [{'copy': row['copy'], 'present':
               (row['copy'] in actual or normalize(row['copy']) in normalized or normalize(row['display']) in normalized
                or normalize(row['copy'])[::-1] in normalized) and
               (normalize(row['display']) in glyph_text or normalize(row['copy']) in glyph_text)} for row in rows]
    text_colours = _text_colour_spaces(path)
    allowed_fonts = {re.sub(r'[^a-z0-9]', '', name.lower()) for name in FONT_NAMES.values()}
    foil_expected = any(item.get('foil') for item in elements)
    spot_present = bool(re.search(r'/Separation\s*/' + FOIL_NAME + r'\b', objects))
    spot_operators = len(re.findall(rb'/(?:Gold_Foil|CS\d+)\s+[cC][sS]\s+1(?:\.0*)?\s+[sS][cC][nN]', streams))
    die_geometry = _die_geometry_check(elements, _pdf_die_geometry(path))
    fitted_strokes = _fitted_stroke_check(elements,
        _pdf_fitted_strokes(path) if any(item.get('fitted_strokes') for item in elements) else [], native=False)
    checks = {
        'exact_layers': len(layers) == len(LAYERS) and {row['name'] for row in layers} == set(LAYERS),
        'die_guides_locked_nonprinting': all(row['locked'] and not row['printable'] for row in layers if row['name'] == 'DIE'),
        'art_layers_printing': all(row['printable'] for row in layers if row['name'] in PRINT_LAYERS),
        'fonts_embedded': bool(fonts) and all(row['embedded_bytes'] > 0 for row in fonts) if rows else True,
        'granted_font_names': all(re.sub(r'[^a-z0-9]', '', row['name'].split('+')[-1].lower()) in allowed_fonts for row in fonts),
        'live_text': sum(len(span['chars']) for span in traces) > 0 if rows else True,
        'all_expected_copy': all(row['present'] for row in copies),
        'gold_foil_spot': spot_present and spot_operators > 0 if foil_expected else True,
        'artwork_present': bool(images) if any(item['kind'] == 'raster' and item.get('has_visible_pixels', True) for item in elements) else True,
        # die and guide paths sit on hidden layers and are proven by die_geometry_complete; a printing vector is
        # a logo or foil path
        'geometry_vector': vector_paths > 0 if any(item['kind'] == 'vector' and item['layer'] != 'DIE'
                                                   for item in elements) else True,
        'die_geometry_complete': die_geometry['holds'] if elements else True,
        'fitted_strokes_preserved': fitted_strokes['holds'],
        'requested_die_visible': all(row['visible'] for row in layers if row['name'] == 'DIE')
            if any(item.get('visible_on_open') for item in elements) else True,
        'raster_colour_cmyk': all(image['components'] == 4 for image in raster_colours),
        'live_type_colour_cmyk_or_spot': all(row['colour_space'] in ('DeviceCMYK', 'ICCBased-CMYK', 'spot-CMYK') for row in text_colours),
    }
    return {'schema': 'round_files_pdf_readback/1', 'file_sha256': sha(path), 'size_mm': size_mm,
            'trim_box_mm': trim_mm, 'layers': layers, 'fonts': fonts, 'copies': copies,
            'actual_text': actual, 'extracted_text': text, 'live_glyphs': sum(len(span['chars']) for span in traces),
            'raster_count': len(images), 'vector_path_count': vector_paths,
            'die_geometry': die_geometry,
            'fitted_strokes': fitted_strokes,
            'raster_colour_spaces': raster_colours,
            'live_type_colour_spaces': text_colours,
            'spot_name': FOIL_NAME if spot_present else None, 'spot_operator_count': spot_operators,
            'checks': checks, 'pdf_compatible_holds': all(checks.values()),
            'native_illustrator_validated': False}


def _geometry_items(value):
    for item in value:
        yield item if isinstance(item, dict) else {'points_mm': item}


def render_flat(path, output, *, dpi=300, clip_mm=None):
    """Transparent printable ink only: physical liquid and gold stay outside it."""
    with fitz.open(path) as doc:
        set_layers(doc, PRINT_LAYERS)
        # Reparse to apply the changed optional-content viewer state reliably.
        with fitz.open(stream=doc.tobytes(), filetype='pdf') as fresh:
            clip = fitz.Rect(*[value * PT for value in clip_mm]) if clip_mm else None
            pixmap = fresh[0].get_pixmap(dpi=dpi, alpha=True, clip=clip)
            pixmap.save(output)


#: the page is read at this resolution for what prints; ink further than PRINT_CHECK_MM past the bound is outside (a
#: raster's own edge reads up to 0.19 mm past it at 300 dpi; read coarser, MuPDF smears it to 1 mm and fails a clean file)
PRINT_CHECK_DPI = 300
PRINT_CHECK_MM = 0.3


def print_check(path, printed_mm=None):
    """The written print file read back (the owner, 2026-10-30): its only layers are LAYERS, every vector on one of them;
    and nothing that prints lies outside ``printed_mm`` (the rings, mm on the page, of the die's printed faces
    plus their bleed; None: the page itself, a product face whose trim is its page). Returns the record, its ``faults``
    in words."""
    from PIL import ImageDraw
    from scipy import ndimage
    faults = []
    with fitz.open(path) as doc:
        names = {layer['name'] for layer in doc.get_ocgs().values()}
        extra = sorted(names - set(LAYERS))
        if extra:
            faults.append('it has layers a print file never has: ' + ', '.join(extra))
        over = [d for d in doc[0].get_drawings() if d.get('layer') not in set(LAYERS)]
        if over:
            faults.append('%d vector piece(s) sit on no named layer' % len(over))
        set_layers(doc, [name for name in names if name != 'DIE'])
        with fitz.open(stream=doc.tobytes(), filetype='pdf') as fresh:
            pixmap = fresh[0].get_pixmap(dpi=PRINT_CHECK_DPI, alpha=True)
            size_mm = [fresh[0].rect.width / PT, fresh[0].rect.height / PT]
    ink = np.frombuffer(pixmap.samples, np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)[..., 3] > 0
    outside = 0
    if printed_mm is not None:
        k = pixmap.width / size_mm[0]
        region = Image.new('L', (pixmap.width, pixmap.height), 0)
        for ring in printed_mm:
            ImageDraw.Draw(region).polygon([(x * k, y * k) for x, y in ring], fill=255)
        allowed = ndimage.binary_dilation(np.asarray(region) > 0, iterations=max(1, round(PRINT_CHECK_MM * k)))
        outside = int((ink & ~allowed).sum())
        if outside:
            faults.append('%.1f mm² prints outside the die\'s printed faces and their bleed' % (outside / k / k))
    return {'schema': 'print_check/1', 'layers': sorted(names), 'unlayered_vectors': len(over),
            'outside_mm2': round(outside / (pixmap.width / size_mm[0]) ** 2, 2), 'dpi': PRINT_CHECK_DPI,
            'faults': faults, 'holds': not faults}


_NATIVE_JS = r'''(function(){var D=__DATA__,doc=null,src=null,old=app.userInteractionLevel,report={};
function q(s){return '"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/[\x00-\x1f]/g,function(c){return '\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4);})+'"';}
function json(v){if(v===null||v===undefined)return 'null';if(typeof v==='string')return q(v);if(typeof v==='number'||typeof v==='boolean')return String(v);var a=[],k;if(v instanceof Array){for(k=0;k<v.length;k++)a.push(json(v[k]));return '['+a.join(',')+']';}for(k in v)if(v.hasOwnProperty(k))a.push(q(k)+':'+json(v[k]));return '{'+a.join(',')+'}';}
function top(item){var L=item.layer;while(L.parent&&L.parent.typename==='Layer')L=L.parent;return L;}
function walk(L,path,r){var here=path?path+'/'+L.name:L.name,kids=[];for(var i=0;i<L.layers.length;i++)kids.push(L.layers[i].name);var row={path:here,sublayers:kids,items:0};r.tree.push(row);var n=L.pageItems.length;for(var i=0;i<n;i++){var it=L.pageItems[i];if(it.parent!==L&&it.parent.typename!=='Layer')continue;if(it.layer.name!==L.name)continue;row.items++;var b=it.geometricBounds;r.objects.push({name:it.name,type:it.typename,layer:here,bounds_mm:[b[0]/(72/25.4),(D.size[1]-b[1])/(72/25.4),b[2]/(72/25.4),(D.size[1]-b[3])/(72/25.4)]});}for(var i=0;i<L.layers.length;i++)walk(L.layers[i],here,r);}
function census(d){var r={layers:[],tree:[],objects:[],frames:[],spots:[],diePaths:[],foilStrokes:[],rasters:d.rasterItems.length,nonNativeItems:d.nonNativeItems.length,placed:d.placedItems.length,version:app.version,foilPaths:0,foilText:0};
for(var i=0;i<d.layers.length;i++){var L=d.layers[i];r.layers.push({name:L.name,locked:L.locked,visible:L.visible,printable:L.printable});walk(L,'',r);}
for(var i=0;i<d.textFrames.length;i++){var t=d.textFrames[i],cs=[];for(var j=0;j<t.contents.length;j++){var c=t.contents.charAt(j);if(/\s/.test(c)){cs.push({text:c,font:null,size:null});continue;}var a=t.characters[j].characterAttributes;cs.push({text:c,font:a.textFont.name,size:a.size});if(a.fillColor.typename==='SpotColor'&&a.fillColor.spot.name===D.foilName)r.foilText++;}r.frames.push({text:t.contents,layer:top(t).name,kind:String(t.kind),characters:cs});}
for(var i=0;i<d.spots.length;i++)r.spots.push(d.spots[i].name);
for(var i=0;i<d.pathItems.length;i++){var p=d.pathItems[i];if((p.filled&&p.fillColor.typename==='SpotColor'&&p.fillColor.spot.name===D.foilName)||(p.stroked&&p.strokeColor.typename==='SpotColor'&&p.strokeColor.spot.name===D.foilName))r.foilPaths++;if(top(p).name==='DIE'&&!p.clipping){var pts=[];for(var j=0;j<p.pathPoints.length;j++){var a=p.pathPoints[j].anchor;pts.push([a[0]/(72/25.4),(D.size[1]-a[1])/(72/25.4)]);}r.diePaths.push({points_mm:pts,closed:p.closed,stroked:p.stroked&&!p.hidden});}if(top(p).name==='FOIL'&&!p.clipping&&p.stroked){var pts=[],left=[],right=[];for(var j=0;j<p.pathPoints.length;j++){var point=p.pathPoints[j],a=point.anchor,l=point.leftDirection,b=point.rightDirection;pts.push([a[0]/(72/25.4),(D.size[1]-a[1])/(72/25.4)]);left.push([l[0]/(72/25.4),(D.size[1]-l[1])/(72/25.4)]);right.push([b[0]/(72/25.4),(D.size[1]-b[1])/(72/25.4)]);}r.foilStrokes.push({points_mm:pts,left_mm:left,right_mm:right,width_mm:p.strokeWidth/(72/25.4),closed:p.closed,filled:p.filled,stroked:p.stroked&&!p.hidden,editable:p.editable,typename:p.typename,cap:String(p.strokeCap),join:String(p.strokeJoin)});}}
return r;}
function inFoilBox(item){var b=item.geometricBounds,cx=(b[0]+b[2])/2/(72/25.4),cy=(D.size[1]-(b[1]+b[3])/2)/(72/25.4);for(var z=0;z<D.foilBoxes.length;z++){var f=D.foilBoxes[z],a=f.box_mm;if(f.layer===top(item).name&&cx>=a[0]-.01&&cx<=a[2]+.01&&cy>=a[1]-.01&&cy<=a[3]+.01)return true;}return false;}
try{app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;
if(D.mode==='build'){doc=app.documents.add(DocumentColorSpace.CMYK,D.size[0],D.size[1]);doc.artboards[0].artboardRect=[0,D.size[1],D.size[0],0];
var tops={};for(var i=0;i<D.layers.length;i++){var L=i===0?doc.layers[0]:doc.layers.add();L.name=D.layers[i];tops[D.layers[i]]=L;}
for(var i=0;i<D.dieLayers.length;i++){var S=tops.DIE.layers.add();S.name=D.dieLayers[i];}
for(var k=0;k<D.objects.length;k++){var o=D.objects[k],T=tops[o.layer],S=T;report.at='object '+k+' '+o.name+': layer';if(o.sub){S=null;for(var i=0;i<T.layers.length;i++)if(T.layers[i].name===o.sub)S=T.layers[i];if(!S){S=T.layers.add();S.name=o.sub;}}report.at='object '+k+' '+o.name+': open';src=app.open(new File(o.source));var items=[];for(var j=0;j<src.pageItems.length;j++){var it=src.pageItems[j];if(it.parent.typename==='Layer')items.push(it);}report.at='object '+k+' '+o.name+': copy '+items.length;var copies=[],many=o.group&&items.length>1;for(var j=items.length-1;j>=0;j--){var b=items[j].geometricBounds,cp=items[j].duplicate(S,ElementPlacement.PLACEATBEGINNING),cb=cp.geometricBounds;cp.translate(b[0]-cb[0],b[1]-cb[1]);copies.push(cp);if(!many&&o.group)cp.name=o.name;}src.close(SaveOptions.DONOTSAVECHANGES);src=null;doc.activate();if(many){var g=S.groupItems.add();g.name=o.name;for(var j=0;j<copies.length;j++)copies[j].move(g,ElementPlacement.PLACEATEND);}}report.at='';
var gold;try{gold=doc.spots.getByName(D.foilName);}catch(e){gold=doc.spots.add();gold.name=D.foilName;}gold.colorType=ColorModel.SPOT;var alt=new CMYKColor();alt.cyan=D.foilCMYK[0]*100;alt.magenta=D.foilCMYK[1]*100;alt.yellow=D.foilCMYK[2]*100;alt.black=D.foilCMYK[3]*100;gold.color=alt;var ink=new SpotColor();ink.spot=gold;ink.tint=100;
for(var i=0;i<doc.pathItems.length;i++){var p=doc.pathItems[i];if(top(p).name==='FOIL'||inFoilBox(p)){if(p.filled)p.fillColor=ink;if(p.stroked)p.strokeColor=ink;}}
for(var i=0;i<doc.textFrames.length;i++){var t=doc.textFrames[i];if(inFoilBox(t))t.textRange.characterAttributes.fillColor=ink;}
for(var i=0;i<doc.layers.length;i++){var L=doc.layers[i],printing=L.name!=='DIE';L.visible=printing||(L.name==='DIE'&&D.dieVisible);L.printable=printing;L.locked=!printing;}
app.redraw();var options=new IllustratorSaveOptions();options.pdfCompatible=true;options.embedICCProfile=true;options.embedLinkedFiles=true;options.fontSubsetThreshold=0;doc.saveAs(new File(D.path),options);report=census(doc);report.saved=true;
}else{doc=app.open(new File(D.path));app.redraw();report=census(doc);report.reopened=true;}
}catch(e){report.error=String(e)+' at line '+e.line;report.saved=false;report.reopened=false;}finally{if(src)src.close(SaveOptions.DONOTSAVECHANGES);if(doc)doc.close(SaveOptions.DONOTSAVECHANGES);app.userInteractionLevel=old;}
var file=new File(D.census);file.encoding='UTF-8';file.open('w');file.write(json(report));file.close();return json({saved:report.saved,reopened:report.reopened,error:report.error});})();'''


def _native_checks(report, raster_count, rows, elements):
    layers, frames = report.get('layers', []), report.get('frames', [])
    foil = any(item.get('foil') for item in elements)
    die_geometry = _die_geometry_check(elements, [
        {'segments': _geometry_segments(item['points_mm'], item['closed']), 'stroked': item['stroked']}
        for item in report.get('diePaths', [])])
    report['die_geometry'] = die_geometry
    fitted_strokes = _fitted_stroke_check(elements, [dict(row,
        round_caps_joins=row['cap'] == 'StrokeCap.ROUNDENDCAP' and row['join'] == 'StrokeJoin.ROUNDENDJOIN')
        for row in report.get('foilStrokes', [])], native=True)
    report['fitted_strokes'] = fitted_strokes
    return {
        'exact_layers': len(layers) == len(LAYERS) and {layer['name'] for layer in layers} == set(LAYERS),
        'die_guides_locked_nonprinting': all(layer['locked'] and not layer['printable'] for layer in layers if layer['name'] == 'DIE'),
        'art_layers_printing': all(layer['printable'] for layer in layers if layer['name'] in PRINT_LAYERS),
        'die_geometry_complete': die_geometry['holds'],
        'fitted_strokes_preserved': fitted_strokes['holds'],
        'requested_die_visible': all(layer['visible'] for layer in layers if layer['name'] == 'DIE')
            if any(item.get('visible_on_open') for item in elements) else True,
        'all_live_text_on_type': bool(frames) and all(frame['layer'] == 'WORDS' for frame in frames) if rows else not frames,
        'granted_character_fonts': all(char['font'] in FONT_NAMES.values() for frame in frames
                                       for char in frame['characters'] if not char['text'].isspace()),
        'raster_preserved_and_embedded': report.get('pdf_raster_count', report.get('rasters')) == raster_count and report.get('placed') == 0,
        'foil_spot_used': FOIL_NAME in report.get('spots', []) and report.get('foilPaths', 0) + report.get('foilText', 0) > 0 if foil else True,
    }


def _frame_signature(report):
    return [(frame['text'], frame['layer'], tuple((char['text'], char['font'], char['size'])
        for char in frame['characters'])) for frame in report.get('frames', [])]


def _compare_native_frames(saved, reopened):
    """Exact text/font/layer identity, bounded size drift, one-to-one frames.

    Frame enumeration can change on reopen. Duplicate frame identities require
    matching rather than greedy selection: two near-sized frames can share one
    candidate while only one can use the other candidate.
    """
    left, right = _frame_signature(saved), _frame_signature(reopened)

    def size_delta(a, b):
        if a[:2] != b[:2] or len(a[2]) != len(b[2]):
            return None
        largest = 0.
        for ca, cb in zip(a[2], b[2]):
            if ca[:2] != cb[:2]:
                return None
            va, vb = ca[2], cb[2]
            if va is None and vb is None and ca[0].isspace():
                continue
            if any(isinstance(value, bool) or not isinstance(value, (int, float))
                   or not math.isfinite(value) or value <= 0 for value in (va, vb)):
                return None
            delta = abs(va - vb)
            if delta > NATIVE_TEXT_SIZE_TOLERANCE_PT:
                return None
            largest = max(largest, delta)
        return largest

    candidates = []
    for a in left:
        row = {}
        for index, b in enumerate(right):
            delta = size_delta(a, b)
            if delta is not None:
                row[index] = delta
        candidates.append(row)
    matches = {}

    def assign(index, visited):
        for target in candidates[index]:
            if target in visited:
                continue
            visited.add(target)
            if target not in matches or assign(matches[target], visited):
                matches[target] = index
                return True
        return False

    holds = len(left) == len(right) and all(assign(index, set()) for index in range(len(left)))
    pairs = [{'saved_frame_index': source, 'reopened_frame_index': target,
              'max_size_delta_pt': candidates[source][target]} for target, source in sorted(matches.items())]
    return {'matches': holds, 'size_tolerance_pt': NATIVE_TEXT_SIZE_TOLERANCE_PT,
            'saved_frame_count': len(left), 'reopened_frame_count': len(right),
            'max_size_delta_pt': max([0.] + [pair['max_size_delta_pt'] for pair in pairs]) if holds else None,
            'matched_frames': pairs}


#: Illustrator's save and reopen, timed by the file's size (round 4, 2026-10-30: its 24.7 MB stand took 317 s to save,
#: past the fixed 180 s, and Make my files stopped; 12.8 s a megabyte measured, 30 allowed, inside the worker's 1,800 s)
NATIVE_SECONDS_PER_OBJECT = 3
NATIVE_SECONDS_PER_MB = 30
NATIVE_TIMEOUT_S = (180, 1200)


def native_timeout(path, objects=0):
    """The seconds Illustrator is given to save or reopen a file: by its size, and by the objects it imports one by one (a 3 MB
    stand of 150 objects took 175 s, past the size's 180 s on a busy machine)."""
    low, high = NATIVE_TIMEOUT_S
    by_size = math.ceil(NATIVE_SECONDS_PER_MB * Path(path).stat().st_size / 1e6)
    return int(min(high, max(low, by_size, NATIVE_SECONDS_PER_OBJECT * objects)))


def reopen_once_more(run):
    """The reopen only reads the file: Illustrator's passing 'MRAP' (a fresh application's font index still settling, the
    same bytes reopen on the next try: round 4's bottle, 2026-10-30) is asked once more, never taken for a bad file."""
    result = run()
    return run() if 'MRAP' in str(result.get('error')) or 'MRAP' in str(result.get('reason')) else result


def native_roundtrip(path, rows, elements, ops=None, size_mm=None):
    """Actual Illustrator save, followed by an independent open of final bytes."""
    from apps.ire.handoff.illustrator_exec import run_jsx
    path = Path(path).resolve()
    check_path = path.with_suffix('.native.json')
    with fitz.open(path) as doc:
        size = [doc[0].rect.width, doc[0].rect.height]
        trim = list(doc[0].trimbox)
        before = raster(doc, 150)
        raster_count = len(doc[0].get_image_info())
    Image.fromarray(before).save(path.with_suffix('.before-native.png'), dpi=(150, 150))
    input_sha = sha(path)
    report = {'schema': 'round_files_native/1', 'input_sha256': input_sha, 'requested': True}
    with tempfile.TemporaryDirectory(prefix='round-files-native-') as directory:
        directory = Path(directory)
        objects = []
        for index, op in enumerate(ops or []):
            # each object its own one-page file: Illustrator keeps it apart, named, on its own (sub-)layer
            piece = Surface(size_mm, 'piece')
            try:
                draw_op(piece, op)
                piece.page.clean_contents() if False else None
                source = directory / ('%04d.pdf' % index)
                set_layers(piece.doc, {op['layer']})
                for xref in piece.doc.get_ocgs():
                    piece.doc.xref_set_key(xref, 'Usage', '<</View <</ViewState /ON>> /Print <</PrintState /ON>>>>')
                piece.doc.xref_set_key(piece.doc.pdf_catalog(), 'OCProperties/D/Locked', '[]')
                piece.doc.save(source, garbage=3, deflate=True)
            finally:
                if not piece.doc.is_closed:
                    piece.doc.close()
            objects.append({'source': str(source), 'layer': op['layer'], 'sub': op.get('sub'), 'name': op['name'],
                            'group': op.get('group', True)})
        candidate = directory / 'native.ai'
        data = {'mode': 'build', 'size': size, 'layers': list(LAYERS), 'dieLayers': list(reversed(list(DIE_SUBLAYERS.values()))), 'objects': objects,
                'path': str(candidate), 'census': str(directory / 'saved.json'),
                'foilName': FOIL_NAME, 'foilCMYK': FOIL_CMYK,
                'dieVisible': any(item.get('visible_on_open') for item in elements),
                'foilBoxes': [element for element in elements if element.get('foil')]}
        script = directory / 'save.jsx'
        script.write_text(_NATIVE_JS.replace('__DATA__', json.dumps(data, ensure_ascii=False)))
        report['save_execution'] = run_jsx(str(script), timeout_s=native_timeout(path, len(objects)))
        saved_path = directory / 'saved.json'
        saved = json.loads(saved_path.read_text()) if saved_path.exists() else {}
        report['saved_census'] = saved
        saved_ok = bool(saved.get('saved') and candidate.exists())
        if saved_ok:
            with fitz.open(candidate) as doc:
                after = raster(doc, 150)
                saved['pdf_raster_count'] = len(doc[0].get_image_info())
                saved['pdf_raster_colour_spaces'] = [image['components'] for image in _raster_colour_spaces(doc)]
            Image.fromarray(after).save(path.with_suffix('.native-candidate.png'), dpi=(150, 150))
            path.with_suffix('.native-candidate.ai').write_bytes(candidate.read_bytes())
        checks = _native_checks(saved, raster_count, rows, elements)
        checks['saved'] = saved_ok
        checks['raster_colour_cmyk'] = all(components == 4 for components in saved.get('pdf_raster_colour_spaces', []))
        if saved_ok:
            checks['same_dimensions'] = before.shape == after.shape
            error = float(np.abs(before.astype(float) - after.astype(float)).mean()) if checks['same_dimensions'] else None
            report['render_mean_absolute_error_150ppi'] = error
            checks['appearance_preserved'] = error is not None and error < 3
        report['checks'] = checks
        if not all(checks.values()):
            report['holds'] = False
            write_json(check_path, report)
            raise ValueError('Illustrator save census failed: ' + repr(checks))
        path.write_bytes(candidate.read_bytes())
        # Mirror actual native locks into PDF OCG metadata; native editing data
        # stays untouched. Reopen happens after this final compatibility patch.
        with fitz.open(path) as doc:
            ocgs = doc.get_ocgs()
            if data['dieVisible']:
                # Illustrator preserves native visibility but writes nonprinting
                # layers OFF in its PDF view. Keep this requested die visible in
                # both views while retaining the independent print exclusion.
                set_layers(doc, {*PRINT_LAYERS, 'DIE'})
            locked = [xref for xref, row in ocgs.items() if row['name'] == 'DIE']
            doc.xref_set_key(doc.pdf_catalog(), 'OCProperties/D/Locked',
                '[' + ' '.join(f'{xref} 0 R' for xref in locked) + ']')
            for xref in ocgs:
                state = 'OFF' if xref in locked else 'ON'
                doc.xref_set_key(xref, 'Usage', f'<</Print <</PrintState /{state}>>>>')
            doc[0].set_trimbox(fitz.Rect(trim) & doc[0].rect)
            doc[0].set_bleedbox(doc[0].rect)
            doc.saveIncr()
        data.update(mode='reopen', path=str(path), census=str(directory / 'reopened.json'))
        script = directory / 'reopen.jsx'
        script.write_text(_NATIVE_JS.replace('__DATA__', json.dumps(data, ensure_ascii=False)))
        report['reopen_execution'] = reopen_once_more(lambda: run_jsx(str(script), timeout_s=native_timeout(path)))
        reopened_path = directory / 'reopened.json'
        reopened = json.loads(reopened_path.read_text()) if reopened_path.exists() else {}
        with fitz.open(path) as doc:
            reopened['pdf_raster_count'] = len(doc[0].get_image_info())
            reopened['pdf_raster_colour_spaces'] = [image['components'] for image in _raster_colour_spaces(doc)]
        report['reopened_census'] = reopened
        reopened_checks = _native_checks(reopened, raster_count, rows, elements)
        report['text_comparison'] = _compare_native_frames(saved, reopened)
        reopened_checks.update(reopened=bool(reopened.get('reopened')),
                              raster_colour_cmyk=all(components == 4 for components in reopened['pdf_raster_colour_spaces']),
                              same_live_text_and_fonts=report['text_comparison']['matches'])
        report['reopen_checks'] = reopened_checks
        report['final_sha256'] = sha(path)
        report['holds'] = all(checks.values()) and all(reopened_checks.values())
        write_json(check_path, report)
        if not report['holds']:
            raise ValueError('Illustrator final-file reopen failed: ' + repr(reopened_checks))
    return report


def law_check(spec, elements, census=None):
    """The file's law (the owner, 2026-10-30, §1), on what was written and, when given, on what Illustrator holds: the die never
    merges with art; every motif its own named object on its panel's sub-layer; one flat colour for the ground. Returns the
    record, its ``faults`` in words."""
    faults = []
    grounds = {item['hex'].upper() for item in spec.get('ground', [])}
    if len(grounds) > 1:
        faults.append('the ground is not one flat colour: ' + ', '.join(sorted(grounds)))
    if not grounds and not spec.get('own_ground'):
        faults.append('it has no ground, and no reason for none')
    if spec.get('artwork'):
        faults.append('a painting fused with the die: %d raster(s) outside the motif library' % len(spec['artwork']))
    names = [item['name'] for item in spec.get('motifs', [])]
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        faults.append('motifs share a name, so are not their own objects: ' + ', '.join(repeated[:5]))
    for item in spec.get('motifs', []):
        if item['kind'] != 'picture':
            continue
        x0, y0, x1, y1 = item['box_mm']
        area = (spec.get('panels') or {}).get(item['panel'])
        if area and (x1 - x0) * (y1 - y0) > MOTIF_MAX_SHARE * area:
            faults.append('%s is not a motif: a picture over %d %% of its panel' % (item['name'], 100 * MOTIF_MAX_SHARE))
    if any(element['layer'] == 'DIE' and element.get('kind') != 'vector' for element in elements):
        faults.append('the die has art on it')
    held = None
    if census and census.get('tree'):
        die_row = next((row for row in census['tree'] if row['path'] == 'DIE'), None)
        missing_subs = [name for name in DIE_SUBLAYERS.values() if die_row is None or name not in die_row['sublayers']]
        if missing_subs:
            faults.append('the die lacks its sub-layer(s): ' + ', '.join(missing_subs))
    if census:
        held = {row['name']: row for row in census.get('objects', [])}
        missing = [name for name in names if name not in held]
        if missing:
            faults.append('%d motif(s) are not their own objects in Illustrator: %s' % (len(missing), ', '.join(missing[:5])))
        moved = [item['name'] for item in spec.get('motifs', []) if item['name'] in held and held[item['name']]['layer'] != 'MOTIFS/' + item['panel']]
        if moved:
            faults.append('%d motif(s) off their panel\'s sub-layer: %s' % (len(moved), ', '.join(moved[:5])))
        art_on_die = [row['name'] or row['type'] for row in census.get('objects', [])
                      if row['layer'].startswith('DIE') and row['type'] not in ('PathItem', 'GroupItem', 'CompoundPathItem')]
        if art_on_die:
            faults.append('the die merged with art in Illustrator: ' + ', '.join(art_on_die[:5]))
    return {'schema': 'law_check/1', 'ground': sorted(grounds), 'motif_objects': len(names),
            'illustrator_objects': len(held) if held is not None else None, 'faults': faults, 'holds': not faults}


_PROOF_JS = r'''(function(){var D=__DATA__,doc=null,out={steps:[]},old=app.userInteractionLevel;
function q(s){return '"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/[\x00-\x1f]/g,' ')+'"';}
function json(v){if(v===null||v===undefined)return 'null';if(typeof v==='string')return q(v);if(typeof v==='number'||typeof v==='boolean')return String(v);var a=[],k;if(v instanceof Array){for(k=0;k<v.length;k++)a.push(json(v[k]));return '['+a.join(',')+']';}for(k in v)if(v.hasOwnProperty(k))a.push(q(k)+':'+json(v[k]));return '{'+a.join(',')+'}';}
function shot(name){var o=new ExportOptionsPNG24();o.artBoardClipping=true;o.horizontalScale=D.scale;o.verticalScale=D.scale;o.transparency=false;var f=new File(D.folder+'/'+name+'.png');doc.exportFile(f,ExportType.PNG24,o);out.steps.push(name);}
function count(L,path,rows){var here=path?path+'/'+L.name:L.name,n=0;for(var i=0;i<L.pageItems.length;i++){if(L.pageItems[i].layer.name===L.name)n++;}rows.push({layer:here,objects:n,locked:L.locked,visible:L.visible});for(var i=0;i<L.layers.length;i++)count(L.layers[i],here,rows);}
function find(name){for(var i=0;i<doc.pageItems.length;i++){if(doc.pageItems[i].name===name)return doc.pageItems[i];}return null;}
try{app.userInteractionLevel=UserInteractionLevel.DONTDISPLAYALERTS;doc=app.open(new File(D.path));doc.artboards.setActiveArtboardIndex(0);
var rows=[];for(var i=0;i<doc.layers.length;i++)count(doc.layers[i],'',rows);out.layers=rows;out.textFrames=doc.textFrames.length;out.rasters=doc.rasterItems.length;
shot('1-as-saved');
out.moved=[];for(var i=0;i<D.move.length;i++){var it=find(D.move[i]);if(it){var b=it.geometricBounds;it.translate(D.by,-D.by);var a=it.geometricBounds;out.moved.push({name:D.move[i],from:[b[0],b[1]],to:[a[0],a[1]]});}else{out.moved.push({name:D.move[i],missing:true});}}
shot('2-three-motifs-moved');
var G=doc.layers.getByName('GROUND');G.visible=false;shot('3-ground-hidden');G.visible=true;
var E=doc.layers.getByName('DIE');out.die_locked_as_saved=E.locked;E.locked=false;E.visible=true;out.die_unlocked=!E.locked;shot('4-die-unlocked-shown');E.locked=true;out.die_locked_again=E.locked;
out.done=true;}catch(e){out.error=String(e)+' at line '+e.line;}finally{if(doc)doc.close(SaveOptions.DONOTSAVECHANGES);app.userInteractionLevel=old;}
var f=new File(D.folder+'/proof.json');f.encoding='UTF-8';f.open('w');f.write(json(out));f.close();return 'done';})();'''


def illustrator_proof(ai_path, folder, motifs, *, scale=60.0, by_mm=12.0):
    """The owner's proof (§6), by script on a copy: Illustrator opens the file, lists every layer and object, moves three motifs,
    hides the ground, unlocks the die, and saves a picture of each state. It closes the copy unsaved and never quits Illustrator.
    Returns the record."""
    from apps.ire.handoff.illustrator_exec import run_jsx
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    copy_path = folder / ('copy-' + Path(ai_path).name)
    copy_path.write_bytes(Path(ai_path).read_bytes())
    data = {'path': str(copy_path), 'folder': str(folder), 'move': list(motifs)[:3], 'by': by_mm * PT, 'scale': scale}
    script = folder / 'proof.jsx'
    script.write_text(_PROOF_JS.replace('__DATA__', json.dumps(data, ensure_ascii=False)))
    run = run_jsx(str(script), timeout_s=native_timeout(copy_path))
    made = json.loads((folder / 'proof.json').read_text()) if (folder / 'proof.json').exists() else {'error': str(run)}
    copy_path.unlink(missing_ok=True)
    made.update(schema='illustrator_proof/1', source_sha256=sha(ai_path), run=run)
    write_json(folder / 'proof.json', made)
    return made


def spec_ops(spec):
    """A spec's objects in the order they are drawn, bottom to top: each one thing Illustrator keeps apart and names."""
    ops = []
    for item in spec.get('ground', []):
        ops.append({'kind': 'path', 'item': dict(item, closed=True, fill=True, stroke_mm=0), 'layer': 'GROUND',
                    'name': item['name'], 'color': rgb(item['hex'])})
    for item in spec.get('artwork', []):
        ops.append({'kind': 'raster', 'item': item, 'layer': item.get('layer', 'MOTIFS'), 'sub': item.get('panel'),
                    'name': item.get('name', 'artwork')})
    for item in spec.get('motifs', []):
        kind = 'raster' if item['kind'] == 'picture' else 'vector'
        ops.append({'kind': kind, 'item': item, 'layer': 'MOTIFS', 'sub': item['panel'], 'name': item['name']})
    for item in spec.get('foil_paths', []):
        ops.append({'kind': 'path', 'item': item, 'layer': 'FOIL', 'name': item.get('name', 'foil')})
    for item in spec.get('relief_paths', []):
        ops.append({'kind': 'path', 'item': item, 'layer': 'RELIEF', 'name': item.get('name', 'relief')})
    for item in spec.get('finishes', []):
        ops.append({'kind': 'vector', 'item': item, 'layer': 'FOIL' if item['finish'] == 'foil' else 'RELIEF',
                    'name': item['name']})
    for item in spec.get('foil_svg', []):
        ops.append({'kind': 'svg', 'item': item, 'layer': 'FOIL', 'name': item.get('name', 'foil')})
    for item in spec.get('type_runs', []):
        ops.append({'kind': 'text', 'item': item, 'layer': 'WORDS', 'name': item.get('name', 'words'), 'group': False})
    for item in spec.get('logos', []):
        ops.append({'kind': 'logo', 'item': item, 'layer': 'WORDS', 'name': item.get('name', 'logo (approved vector)')})
    die = spec.get('die', {})
    for kind, color in (('cut', (1, 0, .5)), ('fold', (0, .6, 1)), ('perf', (.9, .4, 0)), ('half_cut', (.55, .2, .7)), ('glue', (.9, .6, 0)),
                        ('safe', (0, .7, .8)), ('bleed', (0, .7, .8))):
        for item in _geometry_items(die.get(kind, [])):
            ops.append({'kind': 'path', 'item': dict(item, name=item.get('name', kind), fill=False), 'layer': 'DIE',
                        'sub': DIE_SUBLAYERS[kind], 'name': item.get('name', kind), 'color': color, 'group': False})
    for item in _geometry_items(spec.get('guides', [])):
        ops.append({'kind': 'path', 'item': dict(item, fill=False), 'layer': 'DIE', 'sub': 'SAFE', 'name': 'guide',
                    'color': (0, .7, .8), 'group': False})
    return ops


def draw_op(surface, op):
    item, kind = op['item'], op['kind']
    if kind == 'raster':
        surface.artwork(dict(item, layer=op['layer']))
    elif kind == 'vector':
        surface.vector_piece(item, layer=op['layer'])
    elif kind == 'path':
        surface.path(item, layer=op['layer'], **({'color': op['color']} if 'color' in op else {}))
    elif kind == 'svg':
        surface.vector_svg(item)
    elif kind == 'text':
        surface.text(item)
    elif kind == 'logo':
        surface.vector_svg(item, logo=True)
    else:
        raise ValueError('An object is a raster, a vector, a path, a line of type or the logo.')


def export_object(spec, output_dir, *, native=True):
    """Write one object. All boxes are x0,y0,x1,y1 mm, origin at top left.

    Artwork is raster; foil_paths/foil_svg and engine cut/fold geometry are
    vector. Type and logo placements accept rotation=0/90/180/270 and foil=True.
    """
    identifier = spec['id']
    if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', identifier):
        raise ValueError('An export object needs a safe identifier')
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    surface = Surface(spec['size_mm'], spec.get('title', identifier), spec.get('trim_box_mm'),
                      die_visible=spec.get('die_visible', False))
    try:
        # a fitted piece traced off a painting is never written; the file's objects are built, in the law's order
        if spec.get('face_layers'):
            raise ValueError('A fitted vector piece is never laid over the painting: it prints whole.')
        ops = spec_ops(spec)
        for op in ops:
            draw_op(surface, op)
        path = output_dir / (identifier + '.ai')
        surface.save(path)
    finally:
        if not surface.doc.is_closed:
            surface.doc.close()
    checked = print_check(path, spec.get('printed_mm'))
    if spec.get('law'):
        law = law_check(spec, surface.elements)
        checked.update(law=law, holds=checked['holds'] and law['holds'], faults=checked['faults'] + law['faults'])
    write_json(output_dir / (identifier + '.print-check.json'), checked)
    if not checked['holds']:
        raise ValueError('The print file fails its check: ' + '; '.join(checked['faults']))
    initial = read_back_ai(path, surface.rows, surface.elements)
    if not initial['pdf_compatible_holds']:
        write_json(output_dir / (identifier + '.readback.json'), initial)
        raise ValueError('Execution PDF readback failed: ' + repr(initial['checks']))
    native_report = native_roundtrip(path, surface.rows, surface.elements, ops, surface.size_mm) if native else {
        'requested': False, 'holds': False, 'reason': 'Explicit PDF-only fixture; no Illustrator claim.'}
    readback = read_back_ai(path, surface.rows, surface.elements)
    readback['native_illustrator_validated'] = bool(native_report.get('holds') and native_report.get('final_sha256') == sha(path))
    if native and not (readback['pdf_compatible_holds'] and readback['native_illustrator_validated']):
        raise ValueError('The native Illustrator execution file did not pass save and reopen checks')
    if native:                  # Illustrator's own file is the print file: it is read back the same way
        checked = print_check(path, spec.get('printed_mm'))
        if spec.get('law'):
            law = law_check(spec, surface.elements, native_report.get('saved_census'))
            checked.update(law=law, holds=checked['holds'] and law['holds'], faults=checked['faults'] + law['faults'])
        write_json(output_dir / (identifier + '.print-check.json'), checked)
        if not checked['holds']:
            raise ValueError('The print file fails its check after Illustrator: ' + '; '.join(checked['faults']))
    flat = output_dir / (identifier + '.png')
    render_flat(path, flat, dpi=300)
    pdf = output_dir / (identifier + '.pdf')
    pdf.write_bytes(path.read_bytes())
    record = {'schema': 'round_files_object/1', 'id': identifier, 'ai': str(path), 'pdf': str(pdf), 'png': str(flat),
              'size_mm': surface.size_mm, 'layers': list(LAYERS), 'sha256': sha(path),
              'type': surface.rows, 'elements': surface.elements, 'fonts': surface.fonts,
              'readback': readback, 'native': native_report}
    write_json(output_dir / (identifier + '.readback.json'), readback)
    write_json(output_dir / (identifier + '.export.json'), record)
    return record
