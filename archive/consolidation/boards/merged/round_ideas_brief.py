"""The frozen picture boundary, independent of any product's dieline or panels."""
from copy import deepcopy
import math
import re

SCHEMA = 'product_stand_picture/1'
CONTRACT = 'one_full_size_product_and_stand_picture/1'
DESIGNER_FLOW = 'designer/1'


def is_ideas_brief(brief):
    return isinstance(brief, dict) and brief.get('schema') == SCHEMA


def is_designer_brief(brief):
    """The mood-board flow keeps the frozen picture brief; only its marker differs."""
    return is_ideas_brief(brief) and brief.get('flow') == DESIGNER_FLOW


def _text(value, label, *, required=False):
    if not isinstance(value, str):
        raise ValueError(label + ' must be text')
    value = value.strip()
    if required and not value:
        raise ValueError(label + ' is required')
    if len(value) > 3000:
        raise ValueError(label + ' is too long')
    return value


def _measurements(value, keys):
    if not isinstance(value, dict):
        raise ValueError('Measurements must be named values')
    result = {}
    for key in keys:
        number = value.get(key)
        if number is None or number == '':
            continue  # Unknown measurements are intentionally non-blocking.
        if isinstance(number, bool):
            raise ValueError('A measurement must be a positive number')
        try:
            number = float(number)
        except (TypeError, ValueError):
            raise ValueError('A measurement must be a positive number') from None
        if not math.isfinite(number) or number <= 0:
            raise ValueError('A measurement must be a positive number')
        result[key] = number
    return result


def _lines(value, label):
    if not isinstance(value, list) or len(value) > 30:
        raise ValueError(label + ' must be a list of up to thirty lines')
    return [_text(line, label, required=True) for line in value]


def normalize_ideas_brief(value):
    """Whitelist print copy; geometry and creative directions cannot become copy."""
    if not is_ideas_brief(value):
        raise ValueError('Unknown ideas brief format')
    stand = value.get('stand', {})
    copy = value.get('copy', {})
    if not isinstance(stand, dict) or not isinstance(copy, dict):
        raise ValueError('Product copy and stand must be named fields')
    count = stand.get('count', 12)
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 100:
        raise ValueError('Stand capacity must be between one and one hundred products')
    shades = value.get('shades', [])
    if not isinstance(shades, list) or len(shades) > 20:
        raise ValueError('Use up to twenty shades')
    normalized_shades = []
    for shade in shades:
        if not isinstance(shade, dict) or not re.fullmatch(r'#[0-9a-fA-F]{6}', str(shade.get('hex', ''))):
            raise ValueError('Each shade needs a six-digit colour')
        normalized_shades.append({'name': _text(shade.get('name', ''), 'Shade name', required=True),
                                  'hex': shade['hex'].upper()})
        # Emitted only when present, so older briefs normalize byte-identically.
        arabic = _text(shade.get('name_arabic', ''), 'Arabic shade name')
        if arabic:
            if re.search(r'[A-Za-z]', arabic) or not re.search(r'[\u0600-\u06ff]', arabic) or '\n' in arabic:
                raise ValueError('An Arabic shade name must be one line of Arabic letters')
            normalized_shades[-1]['name_arabic'] = ' '.join(arabic.split())
    if len({shade['name'] for shade in normalized_shades}) != len(normalized_shades):
        raise ValueError('Shade names must be distinct')
    dimensions = _measurements(value.get('dimensions_mm', {}), ('width', 'depth', 'height', 'cap_height', 'diameter'))
    stand_dimensions = _measurements(stand.get('dimensions_mm', {}), ('width', 'depth', 'height', 'board_thickness'))
    layout = stand.get('layout', {})
    if not isinstance(layout, dict):
        raise ValueError('Stand layout must use named fields')
    normalized_layout = {}
    for key in ('columns', 'rows'):
        number = layout.get(key)
        if number is None or number == '':
            continue
        if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= 100:
            raise ValueError('Stand rows and columns must be positive whole numbers')
        normalized_layout[key] = number
    result = {'schema': SCHEMA, 'contract': CONTRACT,
              'name': _text(value.get('name', ''), 'Round name', required=True),
              'product_type': _text(value.get('product_type', ''), 'Product kind', required=True),
              'shape': _text(value.get('shape', ''), 'Product shape'),
              'material': _text(value.get('material', ''), 'Product material'),
              'dimensions_mm': dimensions,
              'measurements_provisional': value.get('measurements_provisional', True) is not False,
              'stand': {'count': count, 'dimensions_mm': stand_dimensions,
                        'material': _text(stand.get('material', ''), 'Stand material'),
                        'layout': normalized_layout, 'provisional': stand.get('provisional', True) is not False},
              'copy': {'brand': _text(copy.get('brand', ''), 'Brand copy'),
                       'product': _text(copy.get('product', ''), 'Product copy')},
              'shades': normalized_shades,
              'truths': _lines(value.get('truths', []), 'Product facts'),
              'banned': _lines(value.get('banned', []), 'Banned motifs'),
              'audience': _text(value.get('audience', ''), 'Audience'),
              'bar': _text(value.get('bar', ''), 'Creative direction')}
    if 'flow' in value:
        # Emitted only when present, so earlier rounds' briefs normalize unchanged.
        if value['flow'] != DESIGNER_FLOW:
            raise ValueError('Unknown ideas flow')
        result['flow'] = DESIGNER_FLOW
    return result


def printed_copy(brief):
    """Only these fields can supply lettering, regardless of submitted role flags."""
    value = normalize_ideas_brief(brief)
    result = {'brand': value['copy']['brand'], 'product': value['copy']['product']}
    result['shade_names'] = [shade['name'] for shade in value['shades']]
    return result


def gloss_brief():
    return normalize_ideas_brief(deepcopy({
        'schema': SCHEMA, 'name': 'Lip gloss — product and counter stand',
        'product_type': 'Lip gloss', 'shape': 'Square bottle with a square cap and doe-foot wand',
        'material': 'Clear acrylic body; gold square cap',
        'dimensions_mm': {'width': 15, 'depth': 15, 'height': 100, 'cap_height': 30},
        'measurements_provisional': True,
        'stand': {'count': 12, 'dimensions_mm': {'width': 110, 'depth': 85, 'height': 160, 'board_thickness': 1.5},
                  'material': 'Rigid paperboard', 'layout': {'columns': 4, 'rows': 3}, 'provisional': True},
        'copy': {'brand': 'BBROSE', 'product': 'Lip Gloss / ملمع شفاه'},
        'shades': [{'name': 'Rose Glass', 'hex': '#C9707A'}, {'name': 'Fig Nectar', 'hex': '#8E4A5C'},
                   {'name': 'Ember Glow', 'hex': '#C2553A'}],
        'truths': ['The liquid is visible through the clear acrylic body in the shade’s colour.',
                   'The gold square cap stays gold; its marks may be engraving or foil.',
                   'A doe-foot wand belongs to this product.'],
        'banned': ['literal lips', 'kisses', 'drips', 'splashes'],
        'audience': 'Beauty customers at a retail counter',
        'bar': 'One memorable idea connects the product decoration and the loaded stand header.'}))
