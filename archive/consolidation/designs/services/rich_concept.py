"""Day 9 §4 — a rich build of one palette lid (D-D9-2 … D-D9-6): an idea's spec, its chosen sketch and an idea-specific
RECIPE turned into the truthful lid and every file the pick page reads (``day9_pick.BUILD_FILES``).

The image model illustrates; our engine sets the type, engraves and makes the foil (D-D9-2):
- the PICTURE is a raster plate holding only the picture (D-D9-4): path 'a' cleans the chosen sketch's own picture of
  everything the engine redraws (``rich_plate.clean_large`` for the large or detailed areas, ``clean_small`` for the
  rest); path 'b' lays the picture's flat guide out by engine and lets the model paint only the free areas
  (``rich_plate.paint_free_areas``). Either way ``rich_plate.prove_rich_plate`` runs over the whole plate;
- the ORNAMENT is the recipe's generator's vectors (marks in gold or rose-gold foil, printed ink, or blind relief) and
  its relief regions (emboss plates);
- the NAME is a logotype from a licensed face's outlines (``apps.ire.lettering.logotype``); the ARABIC is set in the
  display face made emitter-capable today (El Messiri PF Bold) or drawn by the ornament (B-1's hero); the small lines
  are live text in the support face; the LOGO is the approved master;
- the flat lid (truthful.png, 1536 × 970, what prints: a blind relief is not drawn on it) and its FINISH PROOF
  (``finish_proof.prove_build``: the proof, coverage, foil limits and line density read from the finish plates).

``build`` resumes: a paid step already made (the plate's edit, the designer's eye) is read back, never bought twice.
The production binders (``make_edit_fn``, ``make_eye_fn``) go through the image guard and the ledger; tests inject
fakes. Nothing is ever written under ``docs/audit/day-8``.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from django.conf import settings

from apps.pipeline.services import truthful_concept as tc

DAY9 = tc.REPO / 'docs' / 'audit' / 'day-9'
DAY8 = tc.REPO / 'docs' / 'audit' / 'day-8'
SPECS = DAY9 / 'directions'
SKETCHES = DAY9 / 'sketches'
CONCEPTS = DAY9 / 'concepts'
SCHEMA = 'day9_build/1'
W, H = tc.W, tc.H
LID_PX = tc.LID_PX
FRAME_PX = tc.FRAME_PX
PX_PER_MM = tc.PX_PER_MM
BUILD_PREFIX = 'day9/builds/'
EYE_PREFIX = 'day9/designer-eye/'
PLATE_QUALITY = 'high'
CROP_DPI = 600                       # day9_pick.CROP_DPI: the 1 : 1 crops are read at this resolution
CROP_PAD_MM = 2.0
FOOTPRINT_GROW_MM = 1.0
INPAINT_RADIUS_PX = 6
NO_TRACKING_EM = 0.0
OCR_PAD_MM = 1.0
OCR_PSMS = (7, 13, 6)                # one line, a raw line (reads a tracked line the first splits), a block
FOIL_GAP_MM = 0.2                    # D-D9-3: the foil's narrowest gap; a logotype in foil is trapped to it
SEAM_EDGE_MM = 1.0
ARABIC_FLATTEN_MM = 0.005
SIGN = '℮'                           # the estimated sign: the emitter draws it as a vector, never as text
NAME_CAP_MIN_MM = 7.0
SIGN_MIN_MM = 3.0
TYPE_MIN_PT = 5.0
ALIF_SHARE_MIN = 0.9
SMALL_TYPE_CONTRAST_MIN = 4.5
LARGE_TYPE_CONTRAST_MIN = 3.0
LARGE_TYPE_CAP_MM = 4.2              # WCAG's large text, 18 pt, as a cap height
RECIPE_KEYS = ('idea', 'ornament', 'ornament_params', 'plate_path', 'plate_prompt', 'guide', 'name', 'arabic', 'support',
               'logo', 'ink_hex', 'foil_plates')
INK_ROLES = ('gold_foil', 'rose_gold_foil')
EYE_SCHEMA = {'type': 'object', 'additionalProperties': False,
              'properties': {'kept': {'type': 'string'}, 'lost': {'type': 'string'}, 'gained': {'type': 'string'},
                             'top_three_fixes': {'type': 'array', 'items': {'type': 'string'}},
                             'reads_as_the_sketch': {'type': 'boolean'}},
              'required': ['kept', 'lost', 'gained', 'top_three_fixes', 'reads_as_the_sketch']}


class RecipeRefused(ValueError):
    """A recipe that does not say everything a build needs (no defaults are invented for it)."""


class LineDoesNotFit(ValueError):
    """A copy line wider or taller than its zone: refused, never shrunk in silence."""


def spec(idea: str) -> dict:
    return json.loads((SPECS / f'{idea}.json').read_text())


def sketch_record(sketch_id: str) -> dict:
    return json.loads((SKETCHES / sketch_id / 'result.json').read_text())


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _attribute(obj, name):
    """``obj.name``, or None when the object has none (a response the spend reservation never marked)."""
    return getattr(obj, name) if hasattr(obj, name) else None


def find_mark(lid_png, lay: dict, out_dir) -> dict:
    """Our mark matched on a lid picture by normalised cross-correlation over scales 0.6–1.4 (Day 8's find_mark, on this
    build's own logo render): its box in mm and score; None and 'not_measured' when no scale can be tried."""
    import cv2
    import numpy as np
    from apps.ire import brand_mark
    from apps.ire.graph import Document, Group, Rect, SolidFill
    recipe = lay['recipe']
    tmp = Path(out_dir) / 'mark-template.png'
    master = brand_mark.approved_master()['master']
    x0, y0, x1, y1 = lay['logo']
    node = brand_mark.mark_node('BBROSE mark', master, x0, y0, x1 - x0, y1 - y0)
    node.recolor = _hex(_ink_hex(recipe['logo']['ink'], recipe))
    doc = Document(page_w=W, page_h=H, title='mark template', root=Group(name='root', role='artwork', children=[
        Group(name='GROUND', role='background', children=[Rect(name='ground', x=0, y=0, w=W, h=H, fill=SolidFill(color=_hex(recipe['ground_hex'])))]),
        Group(name='LOGO', role='logo', children=[node])]))
    tc.render(doc, tmp, frame=False)
    px = lambda v: int(round(v * PX_PER_MM))
    template = tc._gray(tmp)[px(y0):px(y1), px(x0):px(x1)]
    image = tc._gray(lid_png)
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
        return {'box_mm': None, 'score': None, 'not_measured': 'no scale could be tried (too large at %d, flat at %d)' % (too_large, flat)}
    score, (x, y), (h, w) = best
    return {'box_mm': [x / PX_PER_MM, y / PX_PER_MM, (x + w) / PX_PER_MM, (y + h) / PX_PER_MM], 'score': round(score, 3)}


def _hex(value):
    from apps.ire.graph import Color
    return Color.from_hex(value)


def _zone_mm(z) -> tuple:
    return (z[0] * W, z[1] * H, z[2] * W, z[3] * H)


def check_recipe(recipe: dict) -> dict:
    if not isinstance(recipe, dict) or 'idea' not in recipe:
        raise RecipeRefused('a recipe is a dict that names its idea')
    missing = [k for k in RECIPE_KEYS if k not in recipe]
    if missing:
        raise RecipeRefused('the recipe for %s does not say %s' % (recipe['idea'], ', '.join(missing)))
    if recipe['plate_path'] not in ('a', 'b'):
        raise RecipeRefused('plate path %r is neither a nor b' % recipe['plate_path'])
    if recipe['plate_path'] == 'b' and recipe['guide'] is None:
        raise RecipeRefused('plate path b needs the picture\'s flat guide (recipe["guide"])')
    if recipe['plate_path'] == 'a' and not ('clean_large' in recipe and 'clean_small' in recipe):
        raise RecipeRefused('plate path a needs what to clean: recipe["clean_large"] and recipe["clean_small"]')
    return recipe


# --- the type ----------------------------------------------------------------------------------------------------------

def _x_for(zone, width_mm, align) -> float:
    x0, _y0, x1, _y1 = _zone_mm(zone)
    if align == 'left':
        return x0
    if align == 'right':
        return x1 - width_mm
    if align == 'centre':
        return (x0 + x1 - width_mm) / 2
    raise RecipeRefused('alignment %r is not left, right or centre' % align)


def _fits(key, zone, width_mm, height_mm):
    x0, y0, x1, y1 = _zone_mm(zone)
    if width_mm > x1 - x0 + 1e-6 or height_mm > y1 - y0 + 1e-6:
        raise LineDoesNotFit('%s needs %.1f × %.1f mm; its zone is %.1f × %.1f mm' % (key, width_mm, height_mm, x1 - x0, y1 - y0))


def _contours_of(segments) -> list:
    """The Design Graph's path segments as lettering's contours: [('L', p0, p1) | ('C', p0, c1, c2, p3)], each closed."""
    contours, cur, start, prev = [], None, None, None
    for seg in segments:
        kind = type(seg).__name__
        if kind == 'MoveTo':
            if cur:
                contours.append(cur)
            cur, start = [], (seg.x, seg.y)
            prev = start
        elif kind == 'LineTo':
            cur.append(('L', prev, (seg.x, seg.y)))
            prev = (seg.x, seg.y)
        elif kind == 'CubicTo':
            cur.append(('C', prev, (seg.x1, seg.y1), (seg.x2, seg.y2), (seg.x, seg.y)))
            prev = (seg.x, seg.y)
        elif kind == 'ClosePath':
            if prev != start:
                cur.append(('L', prev, start))
            prev = start
        else:
            raise ValueError('a logotype segment %s is not MoveTo, LineTo, CubicTo or ClosePath' % kind)
    if cur:
        contours.append(cur)
    return contours


def foil_trapped(group, *, gap_mm: float):
    """A foil logotype trapped for the press: every gap narrower than ``gap_mm`` (an acute notch in a serif, the meeting
    of two strokes) closed in the foil artwork itself — a morphological closing of the letters' area by half the gap —
    as the foil would close it on press; nothing else moves (the letters' outsides grow back to where they were).
    Returns (group, record): the group with its one compound path redrawn from the closed area, and the area added."""
    from apps.ire import lettering
    path = group.children[0]
    geom = lettering.region(_contours_of(path.segments))
    half = gap_mm / 2.0
    closed = geom.buffer(half, join_style=2, mitre_limit=2.0).buffer(-half, join_style=2, mitre_limit=2.0).union(geom)
    rings = lettering.ring_contours(closed)
    new_path = path.model_copy(update={'segments': lettering.graph_segments(rings)})
    trapped = group.model_copy(update={'children': [new_path] + list(group.children[1:])})
    from shapely import get_parts
    pieces = [len(get_parts(g)) for g in (geom, closed)]
    return trapped, {'trap': 'closing by %.3f mm' % half, 'area_added_mm2': round(closed.area - geom.area, 4), 'pieces': pieces}


def trap_survival(rec: dict, trap: dict) -> dict:
    """The logotype's record read after the foil trap: an operation whose white the trap closes — a cut's line, a
    stroke's clearance from the letters it does not join, under FOIL_GAP_MM (``foil_gap_ok`` False) — is in the print
    file no longer: recorded applied False with why. Returns the record (a copy) and the trap with what it closed."""
    import copy
    rec, trap = copy.deepcopy(rec), dict(trap)
    closed = []
    for op in rec['ops']:
        measured = op['measured'] if 'measured' in op else {}
        if op['applied'] and 'foil_gap_ok' in measured and measured['foil_gap_ok'] is False:
            white = measured['line_mm'] if 'line_mm' in measured else measured['clear_of_others_mm']
            op['applied'] = False
            op['why'] = 'closed by the foil trap: its white is %.3f mm, under the %.1f mm foil gap' % (white, FOIL_GAP_MM)
            closed.append('%s at %s (%.3f mm)' % (op['op'] if op['op'] != 'join' else op['kind'], op['glyph'] if 'glyph' in op else op['pair'], white))
    trap['closed'] = closed
    return rec, trap


def name_lines(sp: dict, recipe: dict) -> list:
    """The name as one or two logotype lines, each measured first (at the origin) and then placed in the name zone."""
    from apps.ire import lettering
    n = recipe['name']
    zone = sp['zones'][n['zone']]
    words = n['lines']
    finishes = _finishes(n['ink'], recipe, ('foil',) if n['ink'] in INK_ROLES else ())
    colour = _ink_hex(n['ink'], recipe)
    measured = []
    for text in words:
        _group, rec = lettering.logotype(text, n['face'], n['ops'][text], cap_mm=n['cap_mm'], x_mm=0.0, top_mm=0.0,
                                         colour=colour, finishes=finishes, upper=n['upper'])
        measured.append(rec)
    lead = n['cap_mm'] * n['leading']
    widths = [r['width_mm'] for r in measured]
    height = n['cap_mm'] + lead * (len(words) - 1) + n['descent_mm']
    _fits('name', zone, max(widths), height)
    x0, y0, x1, y1 = _zone_mm(zone)
    top = y0 + ((y1 - y0) - height) / 2
    out = []
    for k, text in enumerate(words):
        x = _x_for(zone, widths[k], n['align'])
        group, rec = lettering.logotype(text, n['face'], n['ops'][text], cap_mm=n['cap_mm'], x_mm=x, top_mm=top + lead * k,
                                        colour=colour, finishes=finishes, upper=n['upper'])
        trap = None
        if n['ink'] in INK_ROLES:
            group, trap = foil_trapped(group, gap_mm=FOIL_GAP_MM)
            rec, trap = trap_survival(rec, trap)
        out.append({'text': text, 'group': group, 'record': rec, 'box': tuple(rec['box_mm']), 'foil_trap': trap})
    return out


def text_line(key: str, text: str, sp: dict, *, stem_text: str, size_kind: str, size_mm: float, tracking_em: float,
              upper: bool, align: str, colour: str) -> dict:
    """One live line (support or Arabic) typeset with the real face and placed in its zone (top of the zone)."""
    zone = sp['zones'][key]
    if size_kind == 'alif':
        line = tc.typeset(text, stem_text, alif_mm=size_mm)
    else:
        line = tc.typeset(text, stem_text, cap_mm=size_mm, tracking_em=tracking_em, upper=upper)
    _fits(key, zone, line['width_mm'], line['above_mm'] + line['below_mm'])
    x0, y0, x1, _y1 = _zone_mm(zone)
    anchor = {'left': x0, 'right': x1, 'centre': (x0 + x1) / 2}[align]
    if align == 'centre':
        placed = tc.place(line, x=anchor - line['width_mm'] / 2, top=y0, align='left')
    else:
        placed = tc.place(line, x=anchor, top=y0, align=align)
    return dict(placed, key=key, colour=colour)


def arabic_outlined(sp: dict, a: dict) -> dict:
    """The Arabic descriptor drawn from the display face's own outlines (shaped by HarfBuzz, El Messiri PF Bold), its
    lines stacked in reading order in its zone, each line's isolated-alif height ``alif_mm``: the letters as one foil
    area trapped to the foil's gap, a keyline round them in ink (``keyline_mm`` outside, drawn under the foil so the
    foil overlaps it), their emboss inset ``emboss_inset_mm``; the words read back from the glyphs' own names."""
    from fontTools.ttLib import TTFont
    from shapely import affinity
    from shapely.ops import unary_union
    from apps.pipeline.services import orn_b1
    face = orn_b1.face()
    font = TTFont(face['path'])
    glyph_set = font.getGlyphSet()
    k = a['alif_mm'] / orn_b1.alif_units(glyph_set)
    zone = sp['zones'][a['zone']]
    x0, y0, x1, y1 = _zone_mm(zone)
    shapes, words = [], []
    for i, text in enumerate(a['lines']):
        glyphs = orn_b1.set_word(face['path'], glyph_set, text, tol_units=ARABIC_FLATTEN_MM / k)
        line = affinity.scale(unary_union([g['geom'] for g in glyphs]), xfact=k, yfact=-k, origin=(0, 0))
        lx0, _ly0, lx1, _ly1 = line.bounds
        dx = {'right': x1 - lx1, 'left': x0 - lx0, 'centre': (x0 + x1 - lx0 - lx1) / 2}[a['align']]
        shapes.append(affinity.translate(line, dx, y0 + a['alif_mm'] + i * a['alif_mm'] * a['leading']))
        words.append(glyphs)
    letters = unary_union(shapes)
    half = FOIL_GAP_MM / 2.0
    foil = letters.buffer(half, join_style=2, mitre_limit=2.0).buffer(-half, join_style=2, mitre_limit=2.0).union(letters)
    keyline = letters.buffer(a['keyline_mm'], join_style=1)
    relief = letters.buffer(-a['emboss_inset_mm'])
    bx0, by0, bx1, by1 = keyline.bounds
    _fits('descriptor_ar', zone, bx1 - bx0, by1 - by0)
    return {'foil': _rings_of(foil), 'keyline': _rings_of(keyline), 'relief': _rings_of(relief), 'box': (bx0, by0, bx1, by1),
            'reextracted': orn_b1.reextract(words), 'face': {k2: face[k2] for k2 in ('path', 'sha256', 'postscript', 'licence')}}


def _rings_of(geom) -> list:
    """A shapely area as closed point rings (outsides and holes alike: drawn nonzero by the emitter)."""
    from shapely.geometry.polygon import orient
    rings = []
    polys = list(geom.geoms) if hasattr(geom, 'geoms') else [geom]
    for poly in polys:
        if poly.is_empty:
            continue
        poly = orient(poly, sign=1.0)
        rings.append([tuple(c) for c in poly.exterior.coords])
        rings += [[tuple(c) for c in hole.coords] for hole in poly.interiors]
    return rings


def layout(sp: dict, recipe: dict, choices: dict) -> dict:
    """Every copy line placed with the real face, the ornament generated, the logo boxed; refuses a line that does not
    fit, and a line that falls on the ornament's footprint."""
    from shapely.geometry import box
    from shapely.ops import unary_union
    from apps.ire import arabic_display
    check_recipe(recipe)
    if recipe['arabic']['stem'] == arabic_display.CHOSEN['stem']:
        # the derived face lives in var/ (git-ignored): made here where it is absent — the same bytes — so a line
        # naming it is never refused and silently drawn in the chain's next face
        arabic_display.ensure_chosen()
    if 'zones' in recipe:                    # a build zone the recipe measured and names (said in its record), beside the spec's
        sp = dict(sp, zones=dict(sp['zones'], **recipe['zones']))
    orn = recipe['ornament'](**recipe['ornament_params'])
    lines = {}
    s = recipe['support']
    for key, text in (('descriptor_en', sp['copy']['descriptor_en']), ('shades', sp['copy']['shades']), ('net', sp['copy']['net'])):
        lines[key] = text_line(key, text, sp, stem_text=s['stem'], size_kind='cap', size_mm=s['cap_mm'],
                               tracking_em={'descriptor_en': s['tracking_em'], 'shades': NO_TRACKING_EM, 'net': NO_TRACKING_EM}[key],
                               upper=key == 'descriptor_en', align=s['align'][key], colour=s['colour'][key])
    a = recipe['arabic']
    outlined = arabic_outlined(sp, a) if a['outlined'] else None
    if not a['in_ornament'] and not a['outlined']:
        lines['descriptor_ar'] = text_line('descriptor_ar', sp['copy']['descriptor_ar'], sp, stem_text=a['stem'], size_kind='alif',
                                           size_mm=a['alif_mm'], tracking_em=0.0, upper=False, align=a['align'],
                                           colour=_ink_hex(a['ink'], recipe))
    name = name_lines(sp, recipe)
    logo = tc._logo_box(sp['zones'][recipe['logo']['zone']])
    footprint = unary_union(region_polygons(orn['regions']['footprint'])) if orn['regions']['footprint'] else None
    clashes = []
    boxes = {k: v['box'] for k, v in lines.items()}
    boxes.update({'name%d' % k: n['box'] for k, n in enumerate(name)})
    boxes['logo'] = logo
    if outlined is not None:
        boxes['descriptor_ar'] = outlined['box']
    # a name the ornament cuts through itself (recipe name 'draw' False, C-1) lies inside the ornament by design
    clear_of_ornament = [k for k in boxes if recipe['name']['draw'] or not k.startswith('name')]
    if footprint is not None:
        for k in clear_of_ornament:
            if footprint.intersects(box(*boxes[k])):
                clashes.append(k)
    if clashes:
        raise LineDoesNotFit('these lines fall on the ornament: %s' % ', '.join(clashes))
    return {'idea': sp['id'], 'spec': sp, 'choices': choices, 'ornament': orn, 'lines': lines, 'name': name, 'logo': logo,
            'boxes': boxes, 'recipe': recipe, 'arabic_outlined': outlined}


# --- the document ------------------------------------------------------------------------------------------------------

def _ink_hex(role: str, recipe: dict) -> str:
    if role.startswith('ink:'):
        return role[4:]
    if role == 'blind':
        raise RecipeRefused('a blind mark has no ink colour')
    return recipe['ink_hex'][role]


def _finishes(role: str, recipe: dict, names) -> list:
    from apps.ire.graph import Finish
    out = []
    for n in names:
        if n == 'foil':
            if role not in INK_ROLES:
                raise RecipeRefused('a foil finish on %r: only %s are foils' % (role, ', '.join(INK_ROLES)))
            out.append(Finish(kind='foil', plate=recipe['foil_plates'][role], appearance=_hex(recipe['ink_hex'][role])))
        elif n in ('emboss', 'deboss'):
            out.append(Finish(kind=n, plate=n.upper()))
        else:
            raise RecipeRefused('finish %r is not foil, emboss or deboss' % n)
    return out


def _segments(points, closed):
    return tc._path(points, closed)


def _compound(rings) -> list:
    segs = []
    for r in rings:
        segs += tc._path(r, True)
    return segs


def document(lay: dict, *, plate_png=None, guide_only=False):
    """The lid as an engine Document: the plate (or, for the guide, nothing but the picture's flat layout), the ornament,
    the logo, the name and the live lines; every emboss or deboss on a carrier in register (FINISH CARRIERS, opacity 0),
    so page 1 prints only the inks and the foils. ``guide_only``: the engine's own elements drawn over a plain ground,
    never sent to the model (a picture of our structure is what the plate proof compares against)."""
    from apps.ire import brand_mark
    from apps.ire.graph import Document, Group, Image, Path as VPath, Rect, SolidFill, Stroke, TextRun
    recipe = lay['recipe']
    children, carriers = [], []
    if plate_png is not None:
        children.append(Group(name='PLATE', role='background', children=[Image(name='plate', src=str(plate_png), x=0, y=0, w=W, h=H)]))
    else:
        children.append(Group(name='GROUND', role='background',
                              children=[Rect(name='ground', x=0, y=0, w=W, h=H, fill=SolidFill(color=_hex(recipe['ground_hex'])))]))
    nodes = []
    for i, m in enumerate(lay['ornament']['marks']):
        segs = _segments(m['points'], m['closed'] or bool(m['fill']))
        visible = m['ink'] != 'blind'
        relief = [f for f in m['finishes'] if f in ('emboss', 'deboss')]
        if visible:
            colour = _ink_hex(m['ink'], recipe)
            foil = [f for f in m['finishes'] if f == 'foil']
            paint = dict(fill=SolidFill(color=_hex(colour))) if (m['fill'] or not m['width']) else dict(stroke=Stroke(color=_hex(colour), width_mm=m['width']))
            nodes.append(VPath(name=f'ornament-{i}', segments=segs, finishes=_finishes(m['ink'], recipe, foil), **paint))
        if relief:
            paint = dict(fill=SolidFill(color=_hex(recipe['ground_hex']))) if (m['fill'] or not m['width']) else dict(stroke=Stroke(color=_hex(recipe['ground_hex']), width_mm=m['width']))
            carriers.append(VPath(name=f'ornament-{i}-{relief[0]}', segments=segs, finishes=_finishes('gold_foil', recipe, relief), **paint))
    for k, poly in enumerate(region_polygons(lay['ornament']['regions']['relief'])):
        for j, part in enumerate(list(poly.geoms) if hasattr(poly, 'geoms') else [poly]):
            carriers.append(VPath(name=f'relief-{k}-{j}', segments=_compound(_poly_rings(part)), fill=SolidFill(color=_hex(recipe['ground_hex'])),
                                  fill_rule='evenodd', finishes=_finishes('gold_foil', recipe, ('emboss',))))
    children.append(Group(name='ORNAMENT', role='decoration', children=nodes))
    if not guide_only:
        master = brand_mark.approved_master()['master']
        x0, y0, x1, y1 = lay['logo']
        node = brand_mark.mark_node('BBROSE mark', master, x0, y0, x1 - x0, y1 - y0)
        lg = recipe['logo']
        node.recolor = _hex(_ink_hex(lg['ink'], recipe))
        if lg['ink'] in INK_ROLES:
            node.finishes = _finishes(lg['ink'], recipe, ('foil',))
        children.append(Group(name='LOGO', role='logo', children=[node]))
        if recipe['name']['draw']:
            children.append(Group(name='NAME', role='typography', children=[n['group'] for n in lay['name']]))
        if recipe['name']['draw'] and recipe['name']['emboss']:
            for k, n in enumerate(lay['name']):
                for j, p in enumerate(n['group'].children):
                    carriers.append(p.model_copy(update={'name': f'name-{k}-{j}-emboss', 'finishes': _finishes('gold_foil', recipe, ('emboss',))}))
        if lay['arabic_outlined'] is not None:
            ao, ar = lay['arabic_outlined'], recipe['arabic']
            nodes_ar = [VPath(name='arabic-keyline', segments=_compound(ao['keyline']), fill=SolidFill(color=_hex(ar['keyline_hex'])), fill_rule='nonzero'),
                        VPath(name='arabic', segments=_compound(ao['foil']), fill=SolidFill(color=_hex(_ink_hex(ar['ink'], recipe))), fill_rule='nonzero',
                              finishes=_finishes(ar['ink'], recipe, ('foil',)) if ar['ink'] in INK_ROLES else [])]
            children.append(Group(name='ARABIC', role='typography', children=nodes_ar))
            if ar['emboss'] and ao['relief']:
                carriers.append(VPath(name='arabic-emboss', segments=_compound(ao['relief']), fill=SolidFill(color=_hex(recipe['ground_hex'])),
                                      fill_rule='nonzero', finishes=_finishes('gold_foil', recipe, ('emboss',))))
        runs = []
        for key, ln in lay['lines'].items():
            role = recipe['arabic']['ink'] if key == 'descriptor_ar' else None
            spacing = {'tracking_em': ln['tracking_em']} if ln['tracking_em'] > 0 else {}
            run = TextRun(name=key, text=ln['text'], x=ln['x'], y=ln['baseline'], font=ln['font'], size_pt=ln['size_pt'],
                          color=_hex(ln['colour']), align=ln['align'], text_case='upper' if ln['upper'] else None,
                          finishes=_finishes(role, recipe, ('foil',)) if role in INK_ROLES else [], **spacing)
            runs.append(run)
            if key == 'descriptor_ar' and recipe['arabic']['emboss']:
                carriers.append(run.model_copy(update={'name': 'descriptor_ar-emboss', 'finishes': _finishes('gold_foil', recipe, ('emboss',))}))
        children.append(Group(name='TYPE', role='typography', children=runs))
    if carriers:
        children.append(Group(name='FINISH CARRIERS', role='effects', opacity=0.0, children=carriers))
    return Document(page_w=W, page_h=H, title='Enchanted Rose lid %s' % lay['idea'], metadata={'typography_surface': 'apps/pipeline/services/rich_concept.py::build'},
                    root=Group(name='root', role='artwork', children=children))


def emit(doc, folder: Path) -> dict:
    """truthful.ai (the engine's layered .ai: page 1 the artwork, then one page per finish plate), truthful.pdf (the
    same bytes), truthful.png (page 1 at the lid's working scale, unframed) and truthful.svg (page 1)."""
    import fitz
    from apps.ire.container_finishes import SCHEMA as PLATES_SCHEMA
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    folder.mkdir(parents=True, exist_ok=True)
    ai = folder / 'truthful.ai'
    usage = {}
    emit_pdf_ai(doc, str(ai), usage_out=usage)
    shutil.copyfile(ai, folder / 'truthful.pdf')
    png = tc.render(doc, folder / 'truthful.png', frame=False)
    pdf = fitz.open(str(ai))
    try:
        (folder / 'truthful.svg').write_text(pdf[0].get_svg_image(text_as_path=True))
        pages = pdf.page_count
    finally:
        pdf.close()
    # the plates the emitter drew (its own record), so the finish proof's reading of the file can be held to them
    drawn = [{'plate': r['plate'], 'kind': r['kind'], 'page': r['page']} for r in usage[PLATES_SCHEMA]['plates']]
    return {'ai': str(ai), 'ai_sha256': _sha(ai), 'png': png['path'], 'png_sha256': png['sha256'], 'pages': pages,
            'finish_plates': drawn}


# --- the plate ---------------------------------------------------------------------------------------------------------

def region_polygons(items) -> list:
    """A generator's region as shapely polygons: each item a ring of points (a hole-free piece) or a dict
    {'exterior': ring, 'holes': [ring, ...]} (a piece with its holes) — both forms the Day 9 generators return."""
    from shapely.geometry import Polygon
    out = []
    for item in items:
        if isinstance(item, dict):
            poly = Polygon(item['exterior'], item['holes'])
        else:
            poly = Polygon(item) if len(item) >= 3 else None
        if poly is not None and not poly.is_empty:
            out.append(poly if poly.is_valid else poly.buffer(0))
    return out


def _poly_rings(poly) -> list:
    return [list(poly.exterior.coords)] + [list(h.coords) for h in poly.interiors]


def _raster(polys, *, grow_mm) -> 'object':
    import numpy as np
    from PIL import Image as PILImage, ImageDraw
    canvas = PILImage.new('L', LID_PX, 0)
    draw = ImageDraw.Draw(canvas)
    for poly in region_polygons(polys):
        for part in (list(poly.geoms) if hasattr(poly, 'geoms') else [poly]):
            draw.polygon([(x * PX_PER_MM, y * PX_PER_MM) for x, y in part.exterior.coords], fill=255)
            for hole in part.interiors:
                draw.polygon([(x * PX_PER_MM, y * PX_PER_MM) for x, y in hole.coords], fill=0)
    mask = np.asarray(canvas) > 0
    if grow_mm > 0:
        import cv2
        r = max(1, int(round(grow_mm * PX_PER_MM)))
        mask = cv2.dilate(mask.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))) > 0
    return mask


def type_mask(lay: dict, *, grow_mm: float):
    boxes = [b for b in lay['boxes'].values()]
    return _raster([[(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])] for b in boxes], grow_mm=grow_mm)


def make_plate(lay: dict, sketch_id: str, folder: Path, *, edit_fn, ocr, mark_matcher) -> dict:
    """The plate by the recipe's path, then its proof over the whole plate. Resumes from plate.json."""
    import numpy as np
    from PIL import Image as PILImage
    from apps.pipeline.services import rich_plate
    done = folder / 'plate.json'
    if done.exists():
        return json.loads(done.read_text())
    recipe = lay['recipe']
    sketch_lid = SKETCHES / sketch_id / 'lid.png'
    sketch_frame = SKETCHES / sketch_id / 'sketch.png'
    work = folder / 'plate'
    work.mkdir(parents=True, exist_ok=True)
    structure_png = work / 'structure.png'
    tc.render(document(lay, guide_only=True), structure_png, frame=False)
    with PILImage.open(structure_png) as im:
        structure_rgb = np.asarray(im.convert('RGB'))
    structure_mask = _raster(lay['ornament']['regions']['footprint'], grow_mm=0.0)
    if recipe['plate_path'] == 'b':
        guide = recipe['guide'](lay)
        free = _raster(lay['ornament']['regions']['paint'], grow_mm=0.0) & ~type_mask(lay, grow_mm=FOOTPRINT_GROW_MM)
        style_ref = sketch_frame
        if 'style_ref' in recipe and recipe['style_ref'] == 'guide':
            style_ref = work / 'guide-frame.png'
            framed = np.zeros((FRAME_PX[1], FRAME_PX[0], 3), np.uint8)
            framed[:] = guide[0, 0]
            framed[tc.BAND_PX:tc.BAND_PX + LID_PX[1]] = guide
            PILImage.fromarray(framed).save(style_ref)
        painted, rec = rich_plate.paint_free_areas(guide, free, edit_fn=edit_fn, prompt=recipe['plate_prompt'],
                                                   style_ref=str(style_ref), out_dir=str(work))
        rec['style_ref'] = str(style_ref)
        import cv2
        under = rich_plate.seam_ready(~free)
        bgr = cv2.cvtColor(painted, cv2.COLOR_RGB2BGR)
        filled = cv2.inpaint(bgr, under.astype(np.uint8) * 255, INPAINT_RADIUS_PX, cv2.INPAINT_TELEA)
        plate = cv2.cvtColor(filled, cv2.COLOR_BGR2RGB)
        rec['under_the_engine'] = 'the free areas painted by the model; under our vectors (the rest) filled from them by OpenCV inpainting ($0), so the plate is one picture'
        removed, pasted = [under], [under]
        before = None
    else:
        # a repair may start from the build's own cleaned plate (recipe 'plate_source') instead of the sketch's picture
        source = Path(recipe['plate_source']) if 'plate_source' in recipe else sketch_lid
        with PILImage.open(source) as im:
            plate = np.asarray(im.convert('RGB').resize(LID_PX, PILImage.LANCZOS))
        before = plate.copy()
        large = rich_plate.seam_ready(_raster(recipe['clean_large'](lay), grow_mm=0.0))
        style = Path(recipe['plate_style_ref']) if 'plate_style_ref' in recipe else sketch_frame
        plate, rec = rich_plate.clean_large(plate, large, edit_fn=edit_fn, prompt=recipe['plate_prompt'],
                                            style_ref=str(style), out_dir=str(work))
        rec['source'], rec['style_ref'] = str(source), str(style)
        removed, pasted = [large], [rec['region_mask']]
        for k, poly in enumerate(recipe['clean_small'](lay)):
            small = _raster([poly], grow_mm=0.0)
            plate, small_rec = rich_plate.clean_small(plate, small, avoid_mask=large)
            removed.append(small)
            pasted.append(small_rec['region_mask'])
    plate_png = folder / 'plate.png'
    PILImage.fromarray(plate).save(plate_png)
    proof = rich_plate.prove_rich_plate(plate, removed_masks=removed, pasted_regions=pasted, structure_rgb=structure_rgb,
                                        structure_mask=structure_mask, px_per_mm=PX_PER_MM, ocr=ocr, mark_matcher=mark_matcher,
                                        before_rgb=before)
    kept = []
    for k, region in enumerate(pasted):
        PILImage.fromarray(region.astype(np.uint8) * 255).save(work / ('pasted-%d.png' % k))
        kept.append({'file': str(work / ('pasted-%d.png' % k)), 'sha256': rich_plate._mask_sha256(region)})
    record = {'path': recipe['plate_path'], 'plate': str(plate_png), 'plate_sha256': _sha(plate_png), 'sketch': sketch_id,
              'record': rich_plate.jsonable(rec), 'proof': rich_plate.jsonable(proof), 'pasted': kept}
    done.write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str) + '\n')
    return record


# --- measured checks ----------------------------------------------------------------------------------------------------

def _median_under(png, box_mm) -> str:
    import numpy as np
    from PIL import Image as PILImage
    with PILImage.open(png) as im:
        arr = np.asarray(im.convert('RGB'))
    x0, y0, x1, y1 = [int(round(v * PX_PER_MM)) for v in box_mm]
    cut = arr[max(0, y0):max(y0 + 1, y1), max(0, x0):max(x0 + 1, x1)].reshape(-1, 3)
    med = np.median(cut, axis=0)
    return '#%02X%02X%02X' % tuple(int(v) for v in med)


def _words(text: str) -> list:
    import re
    return re.findall(r'[a-z0-9.]+', text.replace(SIGN, ' ').lower())


def _ocr_or_none(cs, path, psm):
    """The line's words, or None when the reader failed (said by the caller as a line not read, never as an empty read)."""
    try:
        return cs.ocr_words(path, lang='eng', psm=psm)
    except cs.OCRFailed:
        return None


def _line_reads(want: list, read: str) -> bool:
    """Every wanted word read (exactly, inside a longer token, or one letter off), or the wanted words' letters and digits
    run together found in the read's own (a reader that joins '27 g' or reads the drawn ℮ as a sign)."""
    import re
    got = _words(read)
    if all(any(w == g or (len(w) > 3 and w in g) or (len(w) >= 5 and _one_off(w, g)) for g in got) for w in want):
        return True
    joined, seen = re.sub(r'[^a-z0-9.]', '', ''.join(want)), re.sub(r'[^a-z0-9.]', '', read.lower())
    if joined in seen:
        return True
    return any(_one_off(joined, seen[i:i + len(joined)]) for i in range(0, len(seen) - len(joined) + 1))


def _one_off(a: str, b: str) -> bool:
    """Whether ``a`` and ``b`` differ by one letter swapped (same length) — an OCR slip, never a copy change."""
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1


def read_lines(lay: dict, png, *, px_per_mm: float) -> dict:
    """Each Latin copy line read by OCR on its own crop of page 1 rendered at CROP_DPI (its box + OCR_PAD_MM, one text
    line): what it read, and whether every word of the line is in it (a word of five letters or more may differ by one
    letter — the reader's own slip, e.g. T read as I)."""
    import tempfile
    from PIL import Image as PILImage, ImageOps
    from apps.pipeline.services import concept_sketches as cs
    copy = lay['spec']['copy']
    boxes = {'descriptor_en': lay['lines']['descriptor_en']['box'], 'shades': lay['lines']['shades']['box'], 'net': lay['lines']['net']['box']}
    for k, n in enumerate(lay['name']):
        boxes['name%d' % k] = n['box']
    out = {}
    with PILImage.open(png) as im:
        lid = im.convert('L')
        for key, b in boxes.items():
            x0, y0, x1, y1 = [v * px_per_mm for v in (b[0] - OCR_PAD_MM, b[1] - OCR_PAD_MM, b[2] + OCR_PAD_MM, b[3] + OCR_PAD_MM)]
            cut = lid.crop((int(max(0, x0)), int(max(0, y0)), int(min(lid.width, x1)), int(min(lid.height, y1))))
            variants = [cut, ImageOps.invert(cut)]          # as printed, and inverted (light type on a dark ground)
            reads = []
            with tempfile.TemporaryDirectory() as tmp:
                for v, variant in enumerate(variants):
                    path = Path(tmp) / ('line-%d.png' % v)
                    variant.save(path)
                    reads += [(psm, _ocr_or_none(cs, path, psm)) for psm in OCR_PSMS]
            want = _words(lay['name'][int(key[4:])]['text']) if key.startswith('name') else _words(copy[key])
            tried = [(psm, ' '.join(t for t, _c, _b in words)) for psm, words in reads if words is not None]
            if not tried:
                out[key] = {'read': None, 'reads': False, 'failed': 'OCR failed on this line'}
                continue
            good = [(psm, read) for psm, read in tried if _line_reads(want, read)]
            psm, read = good[0] if good else tried[0]
            out[key] = {'read': read, 'psm': psm, 'reads': bool(good)}
    return out


def plate_before(lay: dict, sketch_id: str):
    """Path a's plate before any paste — the picture ``make_plate`` cleaned (the recipe's 'plate_source', else the
    sketch's lid), at the lid's grid; None on path b, whose paste (the inpainting under our vectors) has no picture
    before it to read a seam against."""
    import numpy as np
    from PIL import Image as PILImage
    recipe = lay['recipe']
    if recipe['plate_path'] == 'b':
        return None
    source = Path(recipe['plate_source']) if 'plate_source' in recipe else SKETCHES / sketch_id / 'lid.png'
    with PILImage.open(source) as im:
        return np.asarray(im.convert('RGB').resize(LID_PX, PILImage.LANCZOS))


def pasted_regions(lay: dict, plate: dict) -> list:
    """The plate's pasted regions: the masks ``make_plate`` keeps beside the plate, or — for a plate made before it kept
    them — rebuilt from the layout exactly as ``make_plate`` built them and proven against the plate record's own
    digest. A region that cannot be rebuilt to its recorded digest is refused, never guessed."""
    import numpy as np
    from PIL import Image as PILImage
    from apps.pipeline.services import rich_plate
    if 'pasted' in plate:
        out = []
        for row in plate['pasted']:
            with PILImage.open(row['file']) as im:
                region = np.asarray(im.convert('L')) > 127
            if rich_plate._mask_sha256(region) != row['sha256']:
                raise RecipeRefused('the pasted region %s is not the one the plate record names' % row['file'])
            out.append(region)
        return out
    recipe = lay['recipe']
    if plate['path'] == 'b':
        free = _raster(lay['ornament']['regions']['paint'], grow_mm=0.0) & ~type_mask(lay, grow_mm=FOOTPRINT_GROW_MM)
        if rich_plate._mask_sha256(free) != plate['record']['free']['sha256']:
            # a build whose vectors were redrawn on the plate it already had: the free areas are the ones the model was
            # sent, read from that call's own mask (alpha 0 = editable, on the lid's rows of the frame)
            with PILImage.open(Path(plate['plate']).parent / 'plate' / 'free-areas-mask.png') as im:
                alpha = np.asarray(im.convert('RGBA'))[..., 3]
            free = alpha[rich_plate.BAND_PX:rich_plate.BAND_PX + LID_PX[1]] == 0
            if rich_plate._mask_sha256(free) != plate['record']['free']['sha256']:
                raise RecipeRefused('neither the layout nor the mask the model was sent gives the free areas the plate record names')
        return [rich_plate.seam_ready(~free)]
    large = rich_plate.seam_ready(_raster(recipe['clean_large'](lay), grow_mm=0.0))
    if rich_plate._mask_sha256(large) != plate['record']['region']['sha256']:
        whole = np.ones((LID_PX[1], LID_PX[0]), bool)
        if rich_plate._mask_sha256(whole) != plate['record']['region']['sha256']:
            raise RecipeRefused('the cleaned region rebuilt from the layout is not the one the plate record names')
        large = whole        # the record's region is the whole plate (B-1.3-r1: its recipe's region lost its hole)
    if recipe['clean_small'](lay):
        raise RecipeRefused('the small cleaned regions of a plate made before their masks were kept cannot be rebuilt')
    return [large]


def printed_seams(lay: dict, plate: dict, sketch_id: str, flat_png) -> dict:
    """The plate's seams as they PRINT: each pasted region's arcs read only where the flat build shows the plate (a
    pixel the print covers — the flat more than ΔE00 SEAM_DELTA_E_MAX from the plate there — is not read), and on path
    a judged on their rise over the picture before the paste (``rich_plate.seam_delta_e``). An arc whose printing bands
    hold too little is 'covered': its seam does not print."""
    import numpy as np
    from PIL import Image as PILImage
    from apps.pipeline.services import rich_plate
    with PILImage.open(plate['plate']) as im:
        plate_rgb = np.asarray(im.convert('RGB'))
    with PILImage.open(flat_png) as im:
        flat_rgb = np.asarray(im.convert('RGB'))
    if flat_rgb.shape != plate_rgb.shape:
        raise RecipeRefused('the flat build is %s, the plate %s: the seams cannot be read where they print'
                            % (flat_rgb.shape[:2], plate_rgb.shape[:2]))
    bound = rich_plate.SEAM_DELTA_E_MAX
    cover = rich_plate.ciede2000(rich_plate.srgb_to_lab(flat_rgb), rich_plate.srgb_to_lab(plate_rgb)) > bound
    before = plate_before(lay, sketch_id)
    rows = []
    for k, region in enumerate(pasted_regions(lay, plate)):
        if region.all():
            rows.append({'index': k, 'not_measured': 'the region covers the whole plate: it has no seam to read'})
            continue
        rows.append(dict(rich_plate.seam_delta_e(plate_rgb, region, px_per_mm=PX_PER_MM, before_rgb=before, cover=cover), index=k))
    return {'regions': rows, 'cover': 'the flat more than ΔE00 %s from the plate' % bound, 'cover_share': round(float(cover.mean()), 4)}


def plate_findings(plate: dict, recipe: dict, printed: dict) -> tuple:
    """The plate proof read into issues and cannot-meets. Every part that does not hold is an issue, but the seams are
    judged as they PRINT (``printed_seams``): an arc judged at or over the bound is an issue, except an arc within
    SEAM_EDGE_MM of the lid's edge (under the board's wrap), a cannot-meet said with where; a seam that could not be
    read where it prints is an issue. The plate-only seam reading stays in the plate record."""
    from apps.pipeline.services import rich_plate
    proof = plate['proof']
    issues, cannot = [], []
    for part in ('words', 'mark', 'structure', 'residue'):
        res = proof[part]
        if res['holds']:
            continue
        if part == 'structure' and 'structure_in_plate' in recipe:
            cannot.append('plate structure (shifted NCC %s): %s' % (res['shifted_best_ncc'], recipe['structure_in_plate']))
            continue
        issues.append('plate proof: %s does not hold (%s)' % (part, json.dumps({k: v for k, v in res.items() if k not in ('regions', 'reads')}, default=str)[:300]))
    for part in proof['not_measured']:
        if not part.startswith('seams'):
            issues.append('plate proof not measured: %s' % part)
    for row in printed['regions']:
        if 'not_measured' in row:
            issues.append('plate seam of region %d not read where it prints: %s' % (row['index'], row['not_measured']))
            continue
        if row['unmeasured']:
            issues.append('plate seam of region %d: %d of its %d arcs could not be read where they print'
                          % (row['index'], row['unmeasured'], row['arcs']))
        edge = [a for a in row['over'] if min(a['at_mm'][0], a['at_mm'][1], W - a['at_mm'][0], H - a['at_mm'][1]) <= SEAM_EDGE_MM]
        inland = [a for a in row['over'] if a not in edge]
        said = 'its rise over the picture before the paste' if row['over'] and 'rise' in row['over'][0] else 'the colour across it'
        value = 'rise' if said.startswith('its rise') else 'delta_e'
        if inland:
            issues.append('plate seam prints: %d arc(s) of region %d over ΔE00 %s on %s — the worst %s at %s mm'
                          % (len(inland), row['index'], rich_plate.SEAM_DELTA_E_MAX, said, inland[0][value], inland[0]['at_mm']))
        if edge:
            cannot.append("plate seam on the lid's edge, under the board's wrap: %d arc(s) of region %d over ΔE00 %s on %s"
                          " — the worst %s at %s mm" % (len(edge), row['index'], rich_plate.SEAM_DELTA_E_MAX, said,
                                                        edge[0][value], edge[0]['at_mm']))
    return issues, cannot


def checks(lay: dict, plate_png, emitted: dict, proof_record: dict, *, page_png, plate: dict) -> dict:
    """Day 8's measured checks re-done for Day 9 on the files, and D-D9-3 read from the finish plates."""
    from shapely.geometry import box
    from apps.pipeline.services import concept_sketches as cs
    from apps.ire import lettering
    sp, recipe = lay['spec'], lay['recipe']
    printed = printed_seams(lay, plate, plate['sketch'], emitted['png'])
    issues, cannot = plate_findings(plate, lay['recipe'], printed)
    contrast = []
    rows = [(key, ln['box'], ln['colour'], ln['arabic'] or ln['cap_mm'] >= LARGE_TYPE_CAP_MM) for key, ln in lay['lines'].items()]
    rows += [('name%d' % k, n['box'], _ink_hex(recipe['name']['ink'], recipe), True) for k, n in enumerate(lay['name'])]
    if lay['arabic_outlined'] is not None:
        rows.append(('descriptor_ar (its keyline)', lay['arabic_outlined']['box'], recipe['arabic']['keyline_hex'], True))
    for key, box_mm, colour, large in rows:
        under = _median_under(plate_png, box_mm)
        ratio = tc.contrast(tc._rgb(colour), tc._rgb(under))
        floor = LARGE_TYPE_CONTRAST_MIN if large else SMALL_TYPE_CONTRAST_MIN
        contrast.append({'line': key, 'ink': colour, 'under': under, 'ratio': round(ratio, 2), 'floor': floor, 'holds': ratio >= floor})
        if ratio < floor:
            issues.append('%s reads %.2f:1 on what is under it (floor %.1f:1)' % (key, ratio, floor))
    for k, n in enumerate(lay['name']):
        trap = n['foil_trap']
        if trap is not None and (trap['closed'] or trap['pieces'][1] < trap['pieces'][0]):
            said = list(trap['closed'])
            if not said:
                said.append('letters that no operation joins fuse')
            issues.append('the foil trap closes the name\'s lettering (line %d): %s; its %d separate shapes become %d'
                          % (k, '; '.join(said), trap['pieces'][0], trap['pieces'][1]))
    name_cap = min(n['record']['cap_mm_measured'] for n in lay['name'])
    sizes = {'name_cap_mm': round(name_cap, 2), 'name_cap_holds': name_cap >= NAME_CAP_MIN_MM - 1e-6,
             'smallest_pt': round(min(ln['size_pt'] for ln in lay['lines'].values()), 2)}
    sizes['smallest_holds'] = sizes['smallest_pt'] >= TYPE_MIN_PT
    sizes['sign_mm'] = round(lay['lines']['net']['above_mm'], 2)
    sizes['sign_holds'] = sizes['sign_mm'] >= SIGN_MIN_MM - 1e-6
    en_cap = lay['lines']['descriptor_en']['cap_mm']
    if 'descriptor_ar' in lay['lines']:
        alif = lay['lines']['descriptor_ar']['alif_mm']
    else:
        alif = recipe['arabic']['alif_mm']
    sizes['alif_share'] = round(alif / en_cap, 3)
    sizes['alif_holds'] = sizes['alif_share'] >= ALIF_SHARE_MIN
    for k in ('name_cap_holds', 'smallest_holds', 'sign_holds', 'alif_holds'):
        if not sizes[k]:
            issues.append('size check fails: %s (%s)' % (k, json.dumps({kk: v for kk, v in sizes.items() if not kk.endswith('holds')})))
    overlaps = []
    keys = list(lay['boxes'])
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if box(*lay['boxes'][a]).intersects(box(*lay['boxes'][b])):
                overlaps.append([a, b])
    if overlaps:
        issues.append('lines overlap: %s' % overlaps)
    ocr = read_lines(lay, page_png, px_per_mm=CROP_DPI / 25.4)
    unread = [k for k, v in ocr.items() if not v['reads']]
    if unread:
        issues.append('OCR on the flat build does not read, line by line: %s' % ', '.join('%s (%r)' % (k, ocr[k]['read']) for k in unread))
    extracted = lettering.extracted_text(emitted['ai'], 0)
    flat = ' '.join(extracted.replace(SIGN, ' ').split()).lower()
    copy = sp['copy']
    in_file = {k: ' '.join(copy[k].replace(SIGN, ' ').split()).lower() in flat for k in ('name', 'descriptor_en', 'shades', 'net')}
    if not recipe['name']['draw'] and not in_file['name']:
        cannot.append('the name is cut through the ornament as openings (no live text and no logotype group carries it); '
                      'it is read by OCR on the flat build instead')
        in_file.pop('name')
    if not all(in_file.values()):
        issues.append('the file\'s own text lacks: %s' % ', '.join(k for k, ok in in_file.items() if not ok))
    finish = proof_record['coverage']
    limits = proof_record['foil_limits']
    read = [[r['plate'], r['kind']] for r in finish['plates']]
    drawn = [[r['plate'], r['kind']] for r in emitted['finish_plates']]
    if read != drawn:
        issues.append('the finish plates read from the file (%s) are not the ones the emitter drew (%s)' % (read, drawn))
    if proof_record['skipped_pages']:
        issues.append('the finish proof skipped page(s) of the file: %s' % proof_record['skipped_pages'])
    densities = [row['max_lines_per_cm'] for row in proof_record['line_density'] if row['kind'].lower() == 'foil' and 'max_lines_per_cm' in row]
    lines_cm = max(densities) if densities else None
    d93 = {'foil_metallic_pct': finish['foil_and_metallic_pct'], 'relief_pct': finish['relief_pct'], 'meets_area_floor': finish['meets_d9_3'],
           'lines_per_cm_densest': lines_cm, 'meets_lines_floor': lines_cm is not None and lines_cm >= 12.0, 'foil_limits_hold': limits['holds']}
    if d93['meets_area_floor'] is None:
        issues.append('D-D9-3 area floor not measured: %s' % finish['said'])
    elif not d93['meets_area_floor']:
        if lay['spec']['layers']['finish']['note'].startswith('an argued exception'):
            cannot.append('D-D9-3 area floor not met by design — the spec argues the exception: %s' % lay['spec']['layers']['finish']['note'])
        else:
            issues.append('D-D9-3: foil %.1f %% and relief %.1f %% meet neither floor' % (d93['foil_metallic_pct'], d93['relief_pct']))
    built = lay['ornament']['measures']['lines_per_cm_by_construction'] if 'lines_per_cm_by_construction' in lay['ornament']['measures'] else None
    d93['lines_per_cm_by_construction'] = built
    if not d93['meets_lines_floor']:
        if built is not None and built['lines_per_cm'] >= 12.0:
            cannot.append('D-D9-3 line density: the shared reader (a 10 mm window) reads %s lines/cm; the ornament is %s lines/cm '
                          'by construction where densest (%s) — narrower than the window, so the window dilutes it'
                          % (lines_cm, built['lines_per_cm'], built['where']))
        else:
            issues.append('D-D9-3: the densest foil ornament reads %s lines/cm (floor 12)' % lines_cm)
    if d93['foil_limits_hold'] is not True:
        issues.append('foil limits: %s' % limits['said'])
    if not recipe['arabic']['in_ornament'] and not recipe['arabic']['outlined']:
        import fitz
        pdf = fitz.open(emitted['ai'])
        try:
            embedded = sorted({f[3].split('+')[-1] for f in pdf[0].get_fonts(full=True)})
        finally:
            pdf.close()
        if recipe['arabic']['stem'] not in embedded:
            issues.append('the Arabic is not drawn in %s: page 1 embeds %s' % (recipe['arabic']['stem'], embedded))
    if lay['arabic_outlined'] is not None and lay['arabic_outlined']['reextracted'] != sp['copy']['descriptor_ar']:
        issues.append('the drawn Arabic reads back as %r, not %r' % (lay['arabic_outlined']['reextracted'], sp['copy']['descriptor_ar']))
    arabic_read = lay['arabic_outlined']['reextracted'] if lay['arabic_outlined'] is not None else None
    return {'contrast': contrast, 'sizes': sizes, 'overlaps': overlaps, 'ocr': ocr, 'extracted_copy': in_file, 'd9_3': d93, 'arabic_read_back': arabic_read,
            'plate_seams_as_printed': printed,
            'page_mm': [W, H], 'issues': issues, 'cannot_meet': cannot, 'checks_hold': not issues}


def media_map(lay: dict, plate: dict) -> dict:
    recipe = lay['recipe']
    from collections import Counter
    by_ink = dict(Counter(m['ink'] for m in lay['ornament']['marks']))
    return {'plate': {'medium': 'raster picture (the image model\'s, path %s), cleaned and proven' % plate['path'], 'file': plate['plate'], 'sha256': plate['plate_sha256']},
            'ornament': {'medium': 'vector by our engine', 'marks_by_ink': by_ink, 'relief_regions': len(lay['ornament']['regions']['relief']),
                         'kind': lay['ornament']['kind']},
            'name': {'medium': 'vector logotype from a licensed face\'s outlines (apps.ire.lettering)', 'ink': recipe['name']['ink'], 'emboss': recipe['name']['emboss']},
            'arabic': {'medium': 'drawn by the ornament from the display face\'s outlines' if recipe['arabic']['in_ornament'] else 'live text in the display face (ElMessiriPF-Bold)', 'ink': recipe['arabic']['ink']},
            'support': {'medium': 'live text in %s' % recipe['support']['stem']},
            'logo': {'medium': 'the approved master, vector', 'ink': recipe['logo']['ink']},
            'metallic_ink': 'none (PANTONE 9244 C is a pastel in the house files)'}


def crops(lay: dict, emitted: dict, folder: Path) -> dict:
    """The name and the Arabic at 1 : 1 — page 1 rendered at CROP_DPI and cut to each line's box (+ CROP_PAD_MM)."""
    from PIL import Image as PILImage
    from apps.ire.rasterize import pdf_to_png
    big = folder / 'plate' / 'page1-600dpi.png'
    big.parent.mkdir(parents=True, exist_ok=True)
    if not pdf_to_png(Path(emitted['ai']), big, dpi=CROP_DPI):
        raise RuntimeError('page 1 did not render at %s dpi' % CROP_DPI)
    k = CROP_DPI / 25.4
    out = {}
    names = [n['box'] for n in lay['name']]
    name_box = (min(b[0] for b in names), min(b[1] for b in names), max(b[2] for b in names), max(b[3] for b in names))
    if lay['arabic_outlined'] is not None:
        arabic_box = lay['arabic_outlined']['box']
    elif 'descriptor_ar' in lay['lines']:
        arabic_box = lay['lines']['descriptor_ar']['box']
    else:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        arabic_box = unary_union(region_polygons(lay['ornament']['regions']['footprint'])).bounds
    with PILImage.open(big) as im:
        for key, b, fname in (('name', name_box, 'name-1to1.png'), ('arabic', arabic_box, 'arabic-1to1.png')):
            cut = im.crop((int((b[0] - CROP_PAD_MM) * k), int((b[1] - CROP_PAD_MM) * k), int((b[2] + CROP_PAD_MM) * k), int((b[3] + CROP_PAD_MM) * k)))
            cut.save(folder / fname)
            out[key] = {'file': str(folder / fname), 'box_mm': [round(v, 2) for v in b], 'dpi': CROP_DPI}
    return out


# --- the paid binders ---------------------------------------------------------------------------------------------------

def make_edit_fn(concept_id: str, *, cap_usd: float, client=None):
    """ONE guarded gpt-image-2 edit at HIGH quality per call: the image (the layout or the plate in the 1536 × 1024
    frame), the chosen sketch as the style reference, the mask (transparent where the model may paint)."""
    import numpy as np
    from contextlib import ExitStack
    from PIL import Image as PILImage
    from apps.pipeline.services import image_guard
    from apps.pipeline.services.spend_reservation import paid_operation

    def edit_fn(image_png, mask_png, prompt, style_ref):
        out = Path(image_png).with_name(Path(image_png).stem + '-edited.png')
        if out.exists():
            with PILImage.open(out) as im:
                return np.asarray(im.convert('RGB'))
        items = [{'role': 'the lid laid out by our engine (the picture to paint or clean)', 'path': str(image_png)},
                 {'role': 'the chosen sketch, the style reference', 'path': str(style_ref)},
                 {'role': 'the mask (transparent where the model paints)', 'path': str(mask_png)}]
        operation = BUILD_PREFIX + '%s/%s' % (concept_id, Path(image_png).stem)

        def invoke(checked):
            api = client
            if api is None:
                from openai import OpenAI
                api = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0, timeout=400)
            with ExitStack() as stack:
                images = [stack.enter_context(open(i['path'], 'rb')) for i in checked[:2]]
                mask_file = stack.enter_context(open(checked[2]['path'], 'rb'))
                response = paid_operation(api.images.edit, provider='openai', operation=operation, reservation_prefix=BUILD_PREFIX,
                                          reservation_cap=cap_usd, model=settings.IMAGE_MODEL, image=images, mask=mask_file,
                                          prompt=prompt, n=1, size='%dx%d' % FRAME_PX, quality=PLATE_QUALITY)
            saved = _attribute(response, '_rescue_paid_images')
            if saved is None or len(saved) != 1:
                raise RuntimeError('the paid response is kept, but exactly one picture was not recovered')
            shutil.copyfile(saved[0], out)
            dumped = response.model_dump(mode='json')
            return {'reservation_id': _attribute(response, '_rescue_reservation_id'), 'usage': dumped['usage'] if 'usage' in dumped else None}

        result = image_guard.guarded_call(invoke, operation=operation, inputs=items, prompt=prompt, quality=PLATE_QUALITY,
                                          size='%dx%d' % FRAME_PX)
        (out.with_suffix('.json')).write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str) + '\n')
        with PILImage.open(out) as im:
            frame = im.convert('RGB')
            if frame.size != FRAME_PX:
                # never resized into register: rich_plate refuses an edit of another size, and so does this
                raise RuntimeError('the image model returned a %dx%d frame, not the %dx%d asked' % (frame.size + FRAME_PX))
            return np.asarray(frame)
    return edit_fn


def make_eye_fn(concept_id: str, *, cap_usd: float, client=None):
    """ONE Claude vision call (effort low): the chosen sketch, the build's finish proof and its flat lid, compared."""
    from apps.pipeline.services import jury
    from apps.pipeline.services.spend_reservation import paid_operation

    def eye_fn(sketch_png, proof_png, truthful_png, spec_text):
        content = [{'type': 'text', 'text': 'DESIGNER\'S EYE (Day 9). Image 1 is the chosen sketch (an idea from an image model). '
                                            'Image 2 is the truthful build\'s FINISH PROOF (its finishes rendered from the plates). '
                                            'Image 3 is the build\'s flat print artwork. Compare the build with the sketch as a senior '
                                            'packaging designer: what it kept, what it lost, what it gained, and the three fixes that '
                                            'would most raise it, in order. Answer in JSON.'}]
        for p in (sketch_png, proof_png, truthful_png):
            content.append(jury._block(jury.resized_png(p, long_edge=jury.SKETCH_EDGE_PX)[0]))
        content.append({'type': 'text', 'text': 'THE SPEC:\n' + spec_text})
        api = client if client is not None else jury._client()
        model = jury.jury_model()
        response = paid_operation(api.messages.create, provider='anthropic', operation=EYE_PREFIX + concept_id, reservation_prefix=EYE_PREFIX,
                                  reservation_cap=cap_usd, model=model, max_tokens=jury.MAX_OUTPUT_TOKENS,
                                  output_config={'effort': 'low', 'format': {'type': 'json_schema', 'schema': EYE_SCHEMA}},
                                  messages=[{'role': 'user', 'content': content}])
        text = ''.join(b.text for b in response.content if b.type == 'text')
        usage = response.model_dump(mode='json')['usage']
        return {'payload': json.loads(text) if response.stop_reason == 'end_turn' else None, 'stop_reason': response.stop_reason,
                'usage': usage, 'cost_usd': jury.cost_usd(model, usage), 'model': model}
    return eye_fn


# --- the build ----------------------------------------------------------------------------------------------------------

def build(concept_id: str, *, idea: str, sketch_id: str, recipe: dict, edit_fn, eye_fn, ocr, mark_matcher, repair_of,
          folder_root=None) -> dict:
    """One truthful build into ``<folder_root or CONCEPTS>/<concept_id>/`` with every file the pick page reads."""
    from apps.pipeline.services import finish_proof
    root = Path(folder_root) if folder_root is not None else CONCEPTS
    folder = root / concept_id
    if folder.resolve().is_relative_to(DAY8.resolve()):
        raise PermissionError('nothing is written under docs/audit/day-8')
    folder.mkdir(parents=True, exist_ok=True)
    sp = spec(idea)
    choices = sketch_record(sketch_id)['option']['choices']
    lay = layout(sp, recipe, choices)
    plate = make_plate(lay, sketch_id, folder, edit_fn=edit_fn, ocr=ocr, mark_matcher=mark_matcher)
    doc = document(lay, plate_png=plate['plate'])
    emitted = emit(doc, folder)
    proof = finish_proof.prove_build(emitted['png'], emitted['ai'], folder / 'proof-record',
                                     foil_drawn=any(r['kind'] == 'foil' for r in emitted['finish_plates']))
    shutil.copyfile(folder / 'proof-record' / 'finish-proof.png', folder / 'finish-proof.png')
    tc.finish_sheet(emitted['ai'], folder / 'finish-sheet.png')
    crop = crops(lay, emitted, folder)
    measured = checks(lay, plate['plate'], emitted, proof, page_png=folder / 'plate' / 'page1-600dpi.png', plate=plate)
    (folder / 'checks.json').write_text(json.dumps(measured, ensure_ascii=False, indent=1, default=str) + '\n')
    (folder / 'media-map.json').write_text(json.dumps(media_map(lay, plate), ensure_ascii=False, indent=1) + '\n')
    eye_path = folder / 'designer-eye.json'
    if not eye_path.exists():
        eye = eye_fn(SKETCHES / sketch_id / 'lid.png', folder / 'finish-proof.png', folder / 'truthful.png', (SPECS / f'{idea}.md').read_text())
        eye_path.write_text(json.dumps(eye, ensure_ascii=False, indent=1, default=str) + '\n')
    n0 = lay['name'][0]['record']
    face = n0['face']
    arabic = {'face': 'El Messiri PF Bold (derived, emitter-capable)', 'stem': recipe['arabic']['stem'],
              'licence': 'SIL Open Font License 1.1 (El Messiri; the derived file carries the licence beside it)'}
    record = {'schema': SCHEMA, 'concept': concept_id, 'idea': idea, 'direction': idea[0], 'idea_name': sp['name'],
              'idea_line': sp['idea'], 'sketch': sketch_id, 'choices': choices, 'plate_path': recipe['plate_path'],
              'lettering': {'face': face['family'], 'stem': face['stem_text'], 'licence': face['licence'],
                            'ops': [n['record']['ops'] for n in lay['name']], 'cap_mm': round(min(n['record']['cap_mm_measured'] for n in lay['name']), 2)},
              'arabic': arabic, 'checks_hold': measured['checks_hold'], 'cannot_meet': measured['cannot_meet'],
              'issues': measured['issues'],
              'finish': {'foil_metallic_pct': measured['d9_3']['foil_metallic_pct'], 'relief_pct': measured['d9_3']['relief_pct'],
                         'lines_per_cm_densest': measured['d9_3']['lines_per_cm_densest'], 'foil_limits_hold': measured['d9_3']['foil_limits_hold']},
              'plate': {'proof_holds': plate['proof']['holds'], 'file': plate['plate']}, 'crops': crop,
              'files': {'ai': emitted['ai_sha256'], 'truthful_png': emitted['png_sha256']}, 'repair_of': repair_of}
    (folder / 'build.json').write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str) + '\n')
    return record
