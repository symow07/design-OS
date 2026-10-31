"""Day 9 §4 — the recipes: what ``rich_concept.build`` needs for each idea that goes on, read from its spec
(``docs/audit/day-9/directions/<idea>.json``) and its chosen sketch's open choices. A recipe names the idea's ornament
generator and its parameters, the plate's path, guide and prompt, the name's face and lettering operations, the
Arabic, the small lines, the logo and the foils. Every value is the spec's or the sketch's choice, or a decision written
beside it; nothing is defaulted.

The logo is printed in ink on every lid, never in foil: the approved master's tapered strokes close under the foil's
0.2 mm gap at every size up to 38 mm (measured, Day 9), and a gold-coloured ink would be painted gold (D-D9-4).
"""
from __future__ import annotations

import numpy as np

from apps.pipeline.services import rich_concept as rc

W, H = rc.W, rc.H
LID_ROWS, LID_COLS = rc.LID_PX[1], rc.LID_PX[0]
INK_HEX = {'gold_foil': '#C9A55C', 'rose_gold_foil': '#C99A84'}
FOIL_PLATES = {'gold_foil': 'FOIL_GOLD', 'rose_gold_foil': 'FOIL_ROSE_GOLD'}
SUPPORT_STEM = 'Jost[wght]@400'
SUPPORT_CAP_MM = 3.0
SUPPORT_TRACKING_EM = 0.14
ARABIC_STEM = 'ElMessiriPF-Bold'
PICTURE_ONLY = ('Paint only the picture described: no letter, word, number, logo, gold, foil, metal, line pattern, frame '
                'or object; keep exactly the layout\'s light, shadow and colour fields; front-on, flat, edge to edge.')


def _px(x_mm, y_mm):
    return x_mm * rc.PX_PER_MM, y_mm * rc.PX_PER_MM


def _fill_polygons(arr, polys, rgb):
    from PIL import Image, ImageDraw
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    for p in polys:
        if len(p) >= 3:
            draw.polygon([_px(x, y) for x, y in p], fill=rgb)
    return np.asarray(img).copy()


def _rgb(hex_value):
    h = hex_value.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _gradient(start_hex, end_hex, *, angle_from):
    """A flat guide that runs from ``start_hex`` at the top left to ``end_hex`` at the bottom right (or left to right)."""
    ys, xs = np.mgrid[0:LID_ROWS, 0:LID_COLS]
    if angle_from == 'top_left':
        t = (xs / (LID_COLS - 1) * W + ys / (LID_ROWS - 1) * H) / (W + H)
    elif angle_from == 'left':
        t = xs / (LID_COLS - 1)
    else:
        raise ValueError('a gradient runs from the top left or from the left, not %r' % angle_from)
    a, b = np.array(_rgb(start_hex), float), np.array(_rgb(end_hex), float)
    return (a[None, None, :] * (1 - t[..., None]) + b[None, None, :] * t[..., None]).round().astype(np.uint8)


def _flat(hex_value):
    arr = np.zeros((LID_ROWS, LID_COLS, 3), np.uint8)
    arr[:] = _rgb(hex_value)
    return arr


def _support(colours, aligns):
    return {'stem': SUPPORT_STEM, 'cap_mm': SUPPORT_CAP_MM, 'tracking_em': SUPPORT_TRACKING_EM, 'align': aligns, 'colour': colours}


def _base(idea, *, ornament, params, ground_hex, plate_path, guide, prompt, name, arabic, support, logo_ink):
    return {'idea': idea, 'ornament': ornament, 'ornament_params': params, 'ground_hex': ground_hex, 'plate_path': plate_path,
            'guide': guide, 'plate_prompt': prompt, 'name': name, 'arabic': arabic, 'support': support,
            'logo': {'zone': 'logo', 'ink': 'ink:' + logo_ink}, 'ink_hex': INK_HEX, 'foil_plates': FOIL_PLATES}


#: what the model drew on a path-a sketch that the engine redraws, measured on the sketch (mm: x0, y0, x1, y1)
SKETCH_DRAWN = {
    'B-1.3': [(143.0, 0.0, 188.5, 11.5),       # its BBROSE logo
              (159.0, 16.5, 184.0, 27.5),      # باليت
              (65.0, 21.5, 172.5, 71.0),       # ظلال, hatched in painted gold
              (54.0, 71.5, 79.0, 82.0),        # العيون
              (9.0, 85.5, 98.0, 108.5),        # Enchanted Rose and EYESHADOW PALETTE
              (112.0, 112.0, 138.0, 119.5),    # 18 SHADES
              (148.0, 111.5, 185.0, 119.5)],   # 27 g ℮ 0.95 oz
}


def _box(b, *, grow_mm):
    x0, y0, x1, y1 = b
    x0, y0, x1, y1 = max(0.0, x0 - grow_mm), max(0.0, y0 - grow_mm), min(W, x1 + grow_mm), min(H, y1 + grow_mm)
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# --- B-1 Ẓilāl ---------------------------------------------------------------------------------------------------------

def recipe_b1(choices: dict, sketch_id: str) -> dict:
    from apps.pipeline.services import orn_b1
    sp = rc.spec('B-1')
    z = sp['zones']['arabic_hero']
    alif = {'ظلال at alif 26 mm': 26.0, 'ظلال at alif 22 mm with more marbling around it': 22.0}[choices['hero scale']]
    hatch = {'hatched at 45°': 45.0, 'hatched level': 0.0}[choices['hatch']]
    small_alif = 8.0
    # the generator's own build values (orn_b1.BUILD_PARAMS: its hatch is validated at 0.30 mm lines on a 0.62 mm pitch,
    # 16.1 lines/cm in the stems; a finer pitch does not draw an open hatch), the zone from the spec, the choices' values
    params = dict(orn_b1.BUILD_PARAMS, zone_mm=(z[0] * W, z[1] * H, z[2] * W, z[3] * H), alif_mm=alif, small_alif_mm=small_alif,
                  hatch_angle_deg=hatch)
    warm = '#F3EEF2'

    def clean_large(lay):
        """What the model drew on the chosen sketch that the engine redraws — its logo, its lettering and its small lines —
        as boxes measured on the sketch itself (mm), each grown 2 mm here (clean_large grows its edit mask 2 mm more)."""
        return [_box(b, grow_mm=2.0) for b in SKETCH_DRAWN[sketch_id]]

    def clean_small(lay):
        return []

    name = {'face': 'CormorantGaramond-Italic[wght]@600', 'cap_mm': 9.0, 'lines': ['Enchanted Rose'],
            'ops': {'Enchanted Rose': [{'op': 'join', 'kind': 'bridge', 'after': 't', 'height_em': 0.36}]},
            'ink': 'rose_gold_foil', 'emboss': True, 'zone': 'name', 'align': 'left', 'upper': False, 'leading': 1.2,
            'descent_mm': 2.0, 'draw': True}
    arabic = {'in_ornament': True, 'outlined': False, 'stem': ARABIC_STEM, 'alif_mm': small_alif, 'ink': 'rose_gold_foil', 'zone': 'arabic_hero',
              'align': 'right', 'emboss': True}
    def ornament(**p):
        res = orn_b1.zilal(**p)
        res['measures']['lines_per_cm_by_construction'] = {
            'lines_per_cm': round(10.0 / p['hatch_pitch_mm'], 2),
            'where': 'the hatch inside the hero letters (%.2f mm lines on a %.2f mm pitch; stems about 3.5 mm wide)' % (p['hatch_line_mm'], p['hatch_pitch_mm'])}
        return res

    r = _base('B-1', ornament=ornament, params=params, ground_hex='#22205A', plate_path='a', guide=None,
              prompt=('Repaint these areas as more of the same Turkish stone (battal) marbling floated on deep indigo that '
                      'surrounds them: irregular stones of rose, lilac and teal drifting apart with wide deep-indigo veins, '
                      'matching the edges exactly; where the lettering will sit (the upper right and the lower left) keep calm, '
                      'open deep indigo with few or no stones. ' + PICTURE_ONLY),
              name=name, arabic=arabic,
              support=_support({'descriptor_en': warm, 'shades': warm, 'net': warm}, {'descriptor_en': 'left', 'shades': 'left', 'net': 'right'}),
              logo_ink=warm)
    r['clean_large'], r['clean_small'] = clean_large, clean_small
    return r


# --- B-2 Damascene -----------------------------------------------------------------------------------------------------

def recipe_b2(choices: dict, sketch_id: str) -> dict:
    from apps.pipeline.services import orn_b2
    sp = rc.spec('B-2')
    band = sp['band']
    glaze = {'rose, lilac and teal in turn along the channels': 'turns', 'rose in the gold strap, teal in the rose-gold strap': 'by_strap'}[choices['glaze']]
    # the chosen sketch asked for a 54 mm medallion; at 54 mm the name would come within 2 mm of it, so the build keeps the
    # spec's 46 mm (every text zone at least 6 mm clear, measured)
    params = {'p0_mm': (band['p0'][0] * W, band['p0'][1] * H), 'p1_mm': (band['p1'][0] * W, band['p1'][1] * H),
              'band_mm': band['width_mm'], 'medallion_centre_mm': (0.5 * W, 0.5 * H), 'medallion_mm': band['medallion_mm'],
              'folds': 10, 'wire_mm': 0.20, 'channel_mm': 1.0, 'edge_wire_mm': 0.3, 'glaze': glaze, 'finial': orn_b2.FINIALS[0]}
    warm = '#EDE6EC'
    name = {'face': 'Gloock-Regular', 'cap_mm': 8.0, 'lines': ['Enchanted Rose'],
            'ops': {'Enchanted Rose': [{'op': 'join', 'kind': 'overlap', 'after': 'R', 'overlap_em': 0.04},
                                       {'op': 'cut_in', 'at': 'R', 'shape': 'knockout', 'by': 'o', 'gap_em': 0.018}]},
            'ink': 'rose_gold_foil', 'emboss': True, 'zone': 'name', 'align': 'left', 'upper': False, 'leading': 1.2,
            'descent_mm': 0.6, 'draw': True}
    arabic = {'in_ornament': False, 'outlined': False, 'stem': ARABIC_STEM, 'alif_mm': 6.6, 'ink': 'gold_foil', 'zone': 'descriptor_ar', 'align': 'left', 'emboss': False}

    def ornament(**p):
        # the glaze in enamel depth, not pastel (the first build read as candy ribbon): the same three families, deeper
        res = orn_b2.damascene(**p)
        for m in res['marks']:
            for key in ('ink', 'fill'):
                if m[key] in B2_DEEP_GLAZE:
                    m[key] = B2_DEEP_GLAZE[m[key]]
        return res

    r = _base('B-2', ornament=ornament, params=params, ground_hex='#0B0A0E', plate_path='b',
                 guide=lambda lay: _flat('#0B0A0E'),
                 prompt=('Deep black lacquer covering the whole lid, the warm translucency of many coats: even, quiet depth, a '
                         'faint warm undertone, no highlight, no sheen, no streak, no reflection. ' + PICTURE_ONLY),
                 name=name, arabic=arabic,
                 support=_support({'descriptor_en': warm, 'shades': warm, 'net': warm}, {'descriptor_en': 'left', 'shades': 'left', 'net': 'right'}),
                 logo_ink=warm)
    # the lacquer is a plain material: the sketch, a braid drawn by the image model, is not shown to it again (the first
    # plate copied the sketch's braids and a painted gold band into the free areas)
    r['style_ref'] = 'guide'
    return r


#: B-2's glaze, deepened to enamel tones (the generator's pastel channels read as candy ribbon on the first build)
B2_DEEP_GLAZE = {'ink:#E3A9B4': 'ink:#A8516C', 'ink:#9B7BC0': 'ink:#6A4C99', 'ink:#5FB3AE': 'ink:#2C7C77'}


# --- A-2 Golden Hour ---------------------------------------------------------------------------------------------------



def recipe_a2(choices: dict, sketch_id: str) -> dict:
    from apps.pipeline.services import orn_a2
    sp = rc.spec('A-2')
    bars = {'five narrow bars': 5, 'four broader bars': 4}[choices['bars']]
    whole = choices['oval'].startswith('120')
    oval = (120.0, 70.0) if whole else (146.0, 84.0)
    # the centres measured so the oval keeps 6 mm from every type zone (the generator's own rule), as low and as far
    # right as that allows: the whole oval at (0.30, 0.26), the larger one cropped by the top and left edges at (0.26, 0.19)
    centre = (0.30 * W, 0.26 * H) if whole else (48.0, 24.0)
    lit_hex, wall_hex = {'rose plaster lit warm': ('#F2D2B8', '#C99A92'), 'lilac plaster lit rose': ('#E9C3B8', '#8F7FA6')}[choices['wall']]
    deep_hex = '#2B3A55'
    type_zones = {k: tuple(v) for k, v in sp['zones'].items() if isinstance(v, list)}
    # the bar rhythm fixed and reused on every product (J1's idea-check lift): the generator's own 3-1-3 core — two broad
    # bars parted by a slit on the O's diameter (orn_a2.RHYTHM_FIVE / RHYTHM_FOUR) — and its tested build values
    params = {'oval_centre_mm': centre, 'oval_mm': oval, 'turn_deg': -20.0, 'bars': bars,
              'rhythm': orn_a2.RHYTHM_FIVE if bars == 5 else orn_a2.RHYTHM_FOUR, 'gap_ratio': 1.0,
              'line_mm': 0.12, 'pitch_mm': 0.40, 'fade_mm': 1.6, 'emboss': True, 'type_zones': type_zones}

    def guide(lay):
        base = _gradient(wall_hex, deep_hex, angle_from='top_left')
        return _fill_polygons(base, lay['ornament']['regions']['lit'], _rgb(lit_hex))

    warm = '#F6EEEA'
    name = {'face': 'InstrumentSerif-Italic', 'cap_mm': 11.0, 'lines': ['Enchanted Rose'], 'ops': {'Enchanted Rose': []},
            'ink': 'gold_foil', 'emboss': True, 'zone': 'name', 'align': 'left', 'upper': False, 'leading': 1.2, 'descent_mm': 2.5, 'draw': True}
    arabic = {'in_ornament': False, 'outlined': False, 'stem': ARABIC_STEM, 'alif_mm': 3.0, 'ink': 'ink:' + warm, 'zone': 'descriptor_ar', 'align': 'right', 'emboss': False}
    return _base('A-2', ornament=orn_a2.golden_hour, params=params, ground_hex=deep_hex, plate_path='b', guide=guide,
                 prompt=('A wall of hand-trowelled lime plaster at the golden hour, painted, front-on: keep exactly the layout\'s '
                         'light — warm light only inside the bright slanted bars, their edges soft, the plaster\'s fine trowel '
                         'texture showing through the light — and its shadow: cool %s plaster outside the bars, deepening '
                         'smoothly to a deep teal-ink shadow at the lower right. Matte, quiet, no glow ring, no halo. ' % ('rose' if lit_hex == '#F2D2B8' else 'lilac')) + PICTURE_ONLY,
                 name=name, arabic=arabic,
                 support=_support({'descriptor_en': warm, 'shades': warm, 'net': warm}, {'descriptor_en': 'left', 'shades': 'left', 'net': 'right'}),
                 logo_ink=warm)


# --- C-1 Signed Baguette ------------------------------------------------------------------------------------------------

def recipe_c1(choices: dict, sketch_id: str) -> dict:
    from apps.pipeline.services import orn_c1
    sp = rc.spec('C-1')
    z = sp['zones']['baguette']
    centre = ((z[0] + z[2]) / 2 * W, (z[1] + z[3]) / 2 * H)
    if choices['ends'] != 'three facets coming to a point':
        raise rc.RecipeRefused('C-1 builds the pointed baguette only: %r' % choices['ends'])
    end = {'count': 3, 'tip_deg': 120.0, 'apex_deg': 60.0}
    # J1's ranking: "reduce the bar to 0.75 of the width" — 142.5 mm, its height 30 mm
    cut = orn_c1.name_cutouts(text='ENCHANTED ROSE', face='Marcellus-Regular', cap_mm=7.5, centre_mm=centre)
    params = {'centre_mm': centre, 'length_mm': 0.75 * W, 'height_mm': 30.0, 'end_facets': end, 'line_mm': 0.12, 'pitch_mm': 0.40,
              'rim_mm': 0.3, 'cutouts_mm': cut['rings'], 'emboss': True}
    start_hex, mid_hex = {'rose to amethyst': ('#8C5A7E', '#4A3A72'), 'rose to deep teal': ('#8C5A7E', '#1F4E54')}[choices['shagreen']]

    def guide(lay):
        # J1's ranking: "add teal to C-1" — the far lower-right corner turns to deep teal
        base = _gradient(start_hex, mid_hex, angle_from='top_left')
        teal = _gradient('#4A3A72', '#1F4E54', angle_from='top_left')
        ys, xs = np.mgrid[0:LID_ROWS, 0:LID_COLS]
        t = np.clip(((xs / (LID_COLS - 1) + ys / (LID_ROWS - 1)) / 2 - 0.62) / 0.38, 0, 1)[..., None]
        return (base * (1 - t) + teal * t).round().astype(np.uint8)

    warm = '#F3ECEF'
    name = {'face': 'Marcellus-Regular', 'cap_mm': 7.5, 'lines': ['Enchanted Rose'], 'ops': {'Enchanted Rose': []},
            'ink': 'gold_foil', 'emboss': False, 'zone': 'name', 'align': 'centre', 'upper': True, 'leading': 1.2, 'descent_mm': 0.0, 'draw': False}
    arabic = {'in_ornament': False, 'outlined': False, 'stem': ARABIC_STEM, 'alif_mm': 3.0, 'ink': 'ink:' + warm, 'zone': 'descriptor_ar', 'align': 'right', 'emboss': False}
    return _base('C-1', ornament=orn_c1.baguette, params=params, ground_hex='#4A3A72', plate_path='b', guide=guide,
                 prompt=('Shagreen (galuchat) covering the whole lid, painted front-on: the fine pebbled grain of polished ray '
                         'skin, each tiny pearl of the grain catching a little light, its colour exactly the layout\'s — glowing '
                         'rose at the upper left, deep amethyst across the middle, a deep teal in the far lower-right corner. '
                         'Rich, tactile, even. ') + PICTURE_ONLY,
                 name=name, arabic=arabic,
                 support=_support({'descriptor_en': warm, 'shades': warm, 'net': warm}, {'descriptor_en': 'left', 'shades': 'left', 'net': 'right'}),
                 logo_ink=warm)


# --- C-2 Taʿshīq --------------------------------------------------------------------------------------------------------

def recipe_c2(choices: dict, sketch_id: str) -> dict:
    from apps.pipeline.services import orn_c2
    sp = rc.spec('C-2')
    z = sp['zones']['seam']
    tails = {'five broad tails': 5, 'six tails, a little finer': 6}[choices['seam']]
    left_hex = {'deep lilac and pearl': '#4A3A72', 'rose-wine and pearl': '#6E2840'}[choices['pages']]
    pearl = '#EEE6E4'
    params = {'seam_x0_mm': z[0] * W, 'seam_x1_mm': z[2] * W, 'tails': tails, 'slope': 7.0, 'line_mm': 0.12, 'pitch_mm': 0.40,
              'outline_mm': 0.4, 'inset_mm': 0.3, 'emboss': True}

    def guide(lay):
        base = _flat(left_hex)
        return _fill_polygons(base, lay['ornament']['regions']['right_page'], _rgb(pearl))

    warm, ink = '#F4EEF0', '#2E2547'
    two = choices['name'] == 'on two lines as a title page'
    lines = ['Enchanted', 'Rose'] if two else ['Enchanted Rose']
    ops = {'Enchanted': [], 'Rose': [{'op': 'swash', 'at': 'R', 'terminal': 'bottom_right', 'c1_em': [0.2, -0.06], 'c2_em': [1.0, -0.22], 'to_em': [2.2, -0.1]}],
           'Enchanted Rose': []}
    name = {'face': 'LibreBaskerville[wght]@400', 'cap_mm': 9.0, 'lines': lines, 'ops': ops, 'ink': 'gold_foil', 'emboss': True,
            'zone': 'name', 'align': 'left', 'upper': False, 'leading': 1.25, 'descent_mm': 2.5, 'draw': True}
    # the Arabic drawn as the chosen sketch drew it — large, on two lines, the name's equal on its own page — from the face's
    # own outlines, so the spec's deep-lilac keyline can hold it on the pearl (rose-gold foil alone reads 2.0:1 there)
    arabic = {'in_ornament': False, 'outlined': True, 'lines': ['باليت', 'ظلال العيون'], 'stem': ARABIC_STEM, 'alif_mm': 7.5,
              'leading': 1.55, 'ink': 'rose_gold_foil', 'keyline_hex': ink, 'keyline_mm': 0.4, 'emboss_inset_mm': 0.3,
              'zone': 'descriptor_ar_two_lines', 'align': 'right', 'emboss': True}
    r = _base('C-2', ornament=orn_c2.tashiq, params=params, ground_hex=left_hex, plate_path='b', guide=guide,
                 prompt=('Two lacquer panels, painted front-on, exactly where the layout puts them: on the left a deep %s lacquer, '
                         'on the right a pearl-white lacquer with a faint, fine lacquer grain; each with the depth of many coats, '
                         'even, no highlight or streak. ' % ('rose-wine' if left_hex == '#6E2840' else 'lilac')) + PICTURE_ONLY,
                 name=name, arabic=arabic,
                 support=_support({'descriptor_en': warm, 'shades': warm, 'net': ink}, {'descriptor_en': 'left', 'shades': 'left', 'net': 'left'}),
                 logo_ink=warm)
    r['zones'] = {'descriptor_ar_two_lines': [0.61, 0.30, 0.95, 0.60]}     # the pearl page's upper half: two lines at alif 7.5 mm
    r['structure_in_plate'] = ('the two lacquer pages meet along the dovetail line by design — the boundary is our engine\'s own '
                               'geometry (the generator\'s left and right pages), laid as the guide\'s two colours, never drawn by '
                               'the model; it repeats with the tails, so the plate correlates with the seam at a tail\'s shift')
    return r


RECIPES = {'A-2': recipe_a2, 'B-1': recipe_b1, 'B-2': recipe_b2, 'C-1': recipe_c1, 'C-2': recipe_c2}


def recipe(idea: str, choices: dict, sketch_id: str) -> dict:
    if idea not in RECIPES:
        raise rc.RecipeRefused('no recipe yet for %s' % idea)
    return RECIPES[idea](choices, sketch_id)


# --- the one repair a build may have (D-D9-8), from its jurors' findings --------------------------------------------------

def repair_b1(choices: dict, sketch_id: str) -> dict:
    """B-1.3's repair: the marbling repainted as true floated battal (both jurors read it as pebbles or terrazzo) from the
    build's own cleaned plate, the base band cleared to calm indigo under the small copy (J2), the name's t–e bridge
    dropped (J1: a broken ligature), and the lockup lowered so the logo stands twice as far above باليت (J2)."""
    r = recipe_b1(choices, sketch_id)
    r['zones'] = {'arabic_hero': [0.38, 0.16, 0.95, 0.625]}
    z = r['zones']['arabic_hero']
    r['ornament_params'] = dict(r['ornament_params'], zone_mm=(z[0] * W, z[1] * H, z[2] * W, z[3] * H))
    r['name'] = dict(r['name'], ops={'Enchanted Rose': []})
    r['plate_source'] = str(rc.CONCEPTS / sketch_id / 'plate.png')
    r['plate_style_ref'] = str(rc.CONCEPTS / sketch_id / 'plate.png')

    def clean_large(lay):
        """Everything but the lockup's calm field (grown 2 mm): the marbling is painted again, around the lettering."""
        from shapely.geometry import box
        from shapely.ops import unary_union
        calm = unary_union(rc.region_polygons(lay['ornament']['regions']['calm'])).buffer(2.0)
        rest = box(0, 0, W, H).difference(calm)
        # every ring: the calm field is a hole in what is painted again (ring 0 alone would repaint the whole lid)
        return [{'exterior': rings[0], 'holes': rings[1:]}
                for rings in (rc._poly_rings(p) for p in (list(rest.geoms) if hasattr(rest, 'geoms') else [rest]))]

    r['clean_large'] = clean_large
    r['plate_prompt'] = ('Repaint the marbling as true Turkish ebru in the battal (stone) style, floated on deep indigo size: '
                         'soft-edged stones of rose, lilac, violet and teal pressed together and parted by hair-thin, wavering pale '
                         'veins, liquid and painterly, the colours of the stones as they are now — never pebbles, never cracked '
                         'stone, never mosaic or terrazzo. Keep the bottom 18 mm of the lid and the field round the lettering calm, '
                         'open deep indigo with no stones. ' + PICTURE_ONLY)
    return r


def repair_a2(choices: dict, sketch_id: str) -> dict:
    """A-2.3's repair: the light drawn whole on the wall as the O-window's oval (both jurors read the cropped 3-1-3 bars as
    speed stripes, blades or a comb), five even louvre bars, the lit plaster pale warm rose instead of a painted gold glow
    (J2: raster gold beside foil reads as fake gold), the logo larger in deeper shadow (J1, J2), the Arabic a size lighter."""
    from apps.pipeline.services import orn_a2
    r = recipe_a2(dict(choices, oval='120 × 70 mm, whole on the wall'), sketch_id)
    r['ornament_params'] = dict(r['ornament_params'], rhythm=(1.0, 1.0, 1.0, 1.0, 1.0), bars=5)
    lit_hex, wall_hex, deep_hex = '#F0D4C8', '#8F7FA6', '#2B3A55'

    def guide(lay):
        base = _gradient(wall_hex, deep_hex, angle_from='top_left')
        return _fill_polygons(base, lay['ornament']['regions']['lit'], _rgb(lit_hex))

    r['guide'] = guide
    r['zones'] = {'logo': [0.76, 0.06, 0.95, 0.12]}
    r['arabic'] = dict(r['arabic'], alif_mm=2.8)
    r['plate_prompt'] = ('A wall of hand-trowelled lime plaster at dusk, painted, front-on: inside the layout\'s oval, the slanted bars '
                         'are lit by a pale, warm rose light — the plaster itself lit, never gold, never yellow, no glow beyond the bars — '
                         'with soft lilac shadow between them; outside the oval the plaster lies in cool lilac shadow deepening smoothly '
                         'to a deep teal-ink at the lower right. Matte, quiet. ') + PICTURE_ONLY
    return r


REPAIRS = {'B-1': repair_b1, 'A-2': repair_a2}
