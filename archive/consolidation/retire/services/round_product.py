"""Serializable product briefs for the app's whole-object rounds.

Presets supply editable intake values. The sheet consumes the submitted panel
list; it never infers a product's geometry from a name or an old design.
"""
from copy import deepcopy
import math
import re

from . import stick_carton

HEX = re.compile(r'^#[0-9a-fA-F]{6}$')
PANEL_ID = re.compile(r'^[a-z][a-z0-9_]{0,47}$')
CARTON_FACES = ('back', 'side_left', 'front', 'side_right', 'top_end', 'bottom_end')
LIP_GLOSS_OBJECT_PANELS = ('body_front', 'body_back', 'body_left', 'body_right', 'cap_front', 'cap_top')
BANNED = ['rose flowers', 'petals', 'gardens', 'arches', 'glow frames', 'lips',
          'cherries', 'botanical line-art wallpaper', 'the August twelve-rosette',
          'engine-turned cartouche', 'strapwork moire', 'kisses', 'drips', 'honey',
          'bees', 'liquid splash', 'gloss drip motif']
AUDIENCE = 'Women 18–30 in Amman, Beirut, Damascus, Ramallah and Tunis; Arabic equal or leading.'
BAR = ('$1B prestige house; crafted artwork, restrained branding, never one colour family '
       'everywhere, never looks easy to make; each element in its true medium.')
PROMPT_CONTRACT = 'typed_copy_faces/1'
DEFAULT_COPY_ROLES = {key: 'COPY' for key in
                      ('brand', 'product', 'net', 'back_en', 'back_es', 'back_ar', 'batch', 'required')}
DEFAULT_COPY_ROLES.update({key: 'INSTRUCTION' for key in ('collection', 'leaflet', 'ean', 'inci')})


def content_fields(brief):
    """Canonical leaf paths; control metadata is never product content."""
    result = {}
    def visit(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, path + '.' + key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, path + '.' + str(index))
        else:
            result[path] = value
    for key, value in brief.items():
        if key not in ('schema', 'prompt_contract', 'content_roles'):
            visit(value, key)
    return result


def typed_content(brief):
    """Absence is the pinned legacy contract; never upgrade an existing round."""
    if 'prompt_contract' not in brief:
        return False
    if brief['prompt_contract'] != PROMPT_CONTRACT:
        raise ValueError('Unknown round prompt contract')
    return True


def classify_intake(raw, copy_roles):
    """Explicit new-intake operation, not a normalization or resume default."""
    brief = normalize_brief(raw)
    if set(copy_roles) != set(brief['copy']):
        raise ValueError('Every copy/intention field needs its explicit treatment')
    fields = content_fields(brief)
    roles = dict.fromkeys(fields, 'INSTRUCTION')
    for key, role in copy_roles.items():
        roles['copy.' + key] = role
    for index in range(len(brief['shades'])):
        roles[f'shades.{index}.name'] = 'COPY'
    brief.update(prompt_contract=PROMPT_CONTRACT, content_roles=roles)
    return normalize_brief(brief)


def printed_copy(brief):
    """Literal lettering for the first-shade object; other shade variants stay separate."""
    fields = content_fields(brief)
    return {path: fields[path] for path, role in brief['content_roles'].items() if role == 'COPY' and fields[path].strip()
            and (not path.startswith('shades.') or path == 'shades.0.name')}


def lip_gloss_brief():
    panels = [{'id': 'body_' + face, 'label': 'Body ' + face, 'width_mm': 15,
               'height_mm': 70, 'surface': 'clear_acrylic',
               'decoration': 'Screen print, hot foil or clear label; declare any deliberate opaque zone.'}
              for face in ('front', 'back', 'left', 'right')]
    panels += [{'id': 'cap_front', 'label': 'Cap front', 'width_mm': 15, 'height_mm': 30,
                'surface': 'gold_metal', 'decoration': 'Engraving, hot foil or deboss only; never painted.'},
               {'id': 'cap_top', 'label': 'Cap top', 'width_mm': 15, 'height_mm': 15,
                'surface': 'gold_metal', 'decoration': 'Engraving, hot foil or deboss only; never painted.'}]
    panels += [{'id': key, 'label': 'Carton ' + key.replace('_', ' '),
                'surface': 'carton', 'engine_face': key} for key in CARTON_FACES]
    return {'schema': 'round_product/1', 'name': 'Lip gloss', 'product_type': 'lip_gloss',
            'shape': 'lip_gloss_wand', 'provisional': True,
            'dimensions_mm': {'width': 15, 'depth': 15, 'height': 100,
                              'body_height': 70, 'cap_height': 30, 'wall': 2.5},
            'material': 'Square thick-walled clear acrylic bottle, doe-foot wand, square gold metal cap.',
            'carton': {'inside_mm': [16, 16, 102]}, 'panels': panels,
            'shades': [{'name': 'Rose Glass', 'hex': '#C9707A'},
                       {'name': 'Fig Nectar', 'hex': '#8E4A5C'},
                       {'name': 'Ember Glow', 'hex': '#C2553A'}],
            'copy': {'brand': 'BBROSE', 'collection': 'An original collection name',
                     'product': 'Lip Gloss / ملمع شفاه', 'net': '5 ml ℮ 0.17 fl oz',
                     'back_en': 'Lip Gloss. See leaflet.',
                     'back_es': 'Brillo de labios. Ver prospecto.',
                     'back_ar': 'ملمع شفاه. انظر النشرة',
                     'inci': 'INCI: owner to supply', 'batch': 'Batch / Lote / التشغيلة',
                     'ean': 'Empty ladder-wise truncated EAN-13 frame; no bars or digits.',
                     'leaflet': 'Full EN / ES / AR drafts and warnings on the Round 1C leaflet mechanism; day two.'},
            'truths': ['shine', 'liquid colour visible through every clear face', 'doe-foot',
                       'gold cap', 'wand leaving the bottle', 'mirror', 'pocket'],
            'banned': list(BANNED), 'audience': AUDIENCE, 'bar': BAR}


def _positive(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(label + ' must be a positive measurement')
    if not math.isfinite(number) or number <= 0 or number > 5000:
        raise ValueError(label + ' must be between 0 and 5000 mm')
    return number


def normalize_brief(raw):
    if not isinstance(raw, dict):
        raise ValueError('Product brief must be an object')
    brief = deepcopy(raw)
    if not isinstance(brief.get('name'), str) or not brief['name'].strip():
        raise ValueError('Product needs a name')
    brief['name'] = brief['name'].strip()
    panels = brief.get('panels')
    if not isinstance(panels, list) or not 1 <= len(panels) <= 32:
        raise ValueError('Product needs an ordered list of 1–32 panels')
    seen = set()
    for panel in panels:
        if not isinstance(panel, dict) or not PANEL_ID.fullmatch(str(panel.get('id', ''))):
            raise ValueError('Each panel needs a safe, lower-case ID')
        if panel['id'] in seen:
            raise ValueError('Panel IDs must be distinct')
        seen.add(panel['id'])
        panel.setdefault('label', panel['id'].replace('_', ' ').title())
        panel.setdefault('surface', 'print')
        panel.setdefault('decoration', '')
        if 'blank_reason' in panel:
            if not isinstance(panel['blank_reason'], str) or not panel['blank_reason'].strip():
                raise ValueError('A declared blank panel needs a nonempty text reason')
            panel['blank_reason'] = panel['blank_reason'].strip()
        if panel.get('engine_face'):
            if panel['engine_face'] not in CARTON_FACES:
                raise ValueError('Unknown carton engine face')
        else:
            for key in ('width_mm', 'height_mm'):
                panel[key] = _positive(panel.get(key), panel['id'] + ' ' + key)
    if brief.get('shape') == 'lip_gloss_wand' and brief.get('sheet_layout') not in ('round1_balm_v1', 'round1_balm_v2'):
        missing = set(LIP_GLOSS_OBJECT_PANELS) - seen
        if missing:
            raise ValueError('The square lip-gloss bottle needs every object face; missing: '+', '.join(sorted(missing)))
    engines = [p['engine_face'] for p in panels if p.get('engine_face')]
    if engines:
        if len(engines) != 6 or set(engines) != set(CARTON_FACES):
            raise ValueError('A carton must include its six engine faces exactly once')
        dims = brief.get('carton', {}).get('inside_mm')
        if not isinstance(dims, (list, tuple)) or len(dims) != 3:
            raise ValueError('Carton needs three internal dimensions')
        brief['carton']['inside_mm'] = [_positive(v, 'Carton dimension') for v in dims]
    shades = brief.get('shades')
    if not isinstance(shades, list) or not shades:
        raise ValueError('Supply shade names and liquid hex colours')
    for shade in shades:
        if not isinstance(shade, dict) or not str(shade.get('name', '')).strip() or not HEX.fullmatch(str(shade.get('hex', ''))):
            raise ValueError('Each shade needs a name and #RRGGBB colour')
        shade['hex'] = shade['hex'].upper()
    if not isinstance(brief.get('copy'), dict) or not brief['copy']:
        raise ValueError('Supply the product copy')
    if any(not isinstance(v, str) for v in brief['copy'].values()):
        raise ValueError('Copy fields must be text')
    if not isinstance(brief.get('banned'), list) or any(not isinstance(v, str) for v in brief['banned']):
        raise ValueError('Banned motifs must be a list of text')
    brief.setdefault('truths', [])
    brief.setdefault('audience', AUDIENCE)
    brief.setdefault('bar', BAR)
    brief.setdefault('dimensions_mm', {})
    if any(panel['surface'] == 'clear_acrylic' for panel in panels):
        dimensions = brief['dimensions_mm']
        if not isinstance(dimensions, dict):
            raise ValueError('Clear acrylic panels need wall measurements')
        wall = _positive(dimensions.get('wall'), 'Clear acrylic wall')
        if any(panel['surface'] == 'clear_acrylic' and not panel.get('engine_face') and
               2*wall >= min(panel['width_mm'], panel['height_mm']) for panel in panels):
            raise ValueError('Clear acrylic walls must leave an inner liquid face')
        dimensions['wall'] = wall
    brief.setdefault('provisional', True)
    brief['schema'] = 'round_product/1'
    if typed_content(brief):
        fields = content_fields(brief)
        roles = brief.get('content_roles')
        if not isinstance(roles, dict) or set(roles) != set(fields):
            raise ValueError('Every intake field needs exactly one COPY or INSTRUCTION role')
        if any(role not in ('COPY', 'INSTRUCTION') for role in roles.values()):
            raise ValueError('Content roles must be COPY or INSTRUCTION')
        if any(roles[path] == 'COPY' and not isinstance(value, str) for path, value in fields.items()):
            raise ValueError('Only text can be printed verbatim as COPY')
    return brief


def repair_missing_body_right(raw):
    """Explicit queued repair of the known intake omission; never an intake default.

    The submitted left wall owns the mirrored right-wall dimensions and material.
    The worker must archive the original brief before persisting this replacement.
    """
    brief = deepcopy(raw)
    if brief.get('shape') != 'lip_gloss_wand':
        return normalize_brief(brief)
    ids = {panel['id'] for panel in brief['panels']}
    missing = set(LIP_GLOSS_OBJECT_PANELS) - ids
    if missing == {'body_right'}:
        left = next(index for index, panel in enumerate(brief['panels']) if panel['id'] == 'body_left')
        right = deepcopy(brief['panels'][left])
        right.update(id='body_right', label='Body right')
        # An intentional blank declaration belongs to the named face only.
        right.pop('blank_reason', None)
        brief['panels'].insert(left+1, right)
    return normalize_brief(brief)


def engine_panels(brief):
    """Resolve only carton dimensions through the existing dieline engine."""
    panels = deepcopy(brief['panels'])
    if not any(p.get('engine_face') for p in panels):
        return panels, None
    coords, fold = stick_carton.die({'name': brief['name'], 'inside_mm': brief['carton']['inside_mm']})
    faces = stick_carton.faces(coords)
    for panel in panels:
        if panel.get('engine_face'):
            face = faces[panel['engine_face']]
            x0, y0, x1, y1 = face['box']
            panel.update(width_mm=x1-x0, height_mm=y1-y0, engine=face)
    return panels, coords


def legacy_balm_brief(version=1):
    """Compatibility fixture: geometry contract only, no old artwork or seed."""
    from .round_balm_sheet import PANEL_IDS
    brief = lip_gloss_brief()
    if version not in (1, 2):
        raise ValueError('Known legacy sheet versions are 1 and 2')
    sizes = [(58.5, 42), (58.5, 32), (16 if version == 1 else 18,)*2,
             (20.45, 74.35), (20.45, 73.45), (20.45, 73.45), (20.45, 73.45),
             (20, 20.45), (20, 20.45)]
    brief.update(name='Lip balm', sheet_layout='round1_balm_v'+str(version),
                 panels=[{'id': key, 'width_mm': size[0], 'height_mm': size[1],
                          'shape': 'circle' if key == 'label' else 'rectangle'}
                         for key, size in zip(PANEL_IDS, sizes)])
    return brief
