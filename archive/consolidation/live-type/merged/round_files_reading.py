"""Read the picked picture item by item: COPY fields, the reading's repairs and checks, and seat loading.

Moved unchanged from round_files_art when its picture extraction was retired
(docs/rounds/reuse-plan.md). The reading names fields; it never supplies printable characters.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re

from .round_files_ornament import ARABIC, face_for, ornament_copy, zone_record

PANEL_IDS = ('body_front', 'cap_front', 'stand_header', 'stand_base')
PANEL_LABELS = {'body_front': 'Bottle front', 'cap_front': 'Cap front',
                'stand_header': 'Stand header', 'stand_base': 'Stand base'}
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')
READS = {0: 'upright', 90: 'reads bottom to top', 180: 'upside down', 270: 'reads top to bottom'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def copy_fields(brief):
    """Inspection names a field; it never supplies printable characters."""
    value = brief['copy']['product']
    parts = [part.strip() for part in value.split('/')]
    result = {'product_latin': ' / '.join(part for part in parts if not ARABIC.search(part)),
              'product_arabic': ' / '.join(part for part in parts if ARABIC.search(part))}
    result.update({'shade_' + str(index): shade['name'] for index, shade in enumerate(brief.get('shades', []))})
    # Never a shade_ prefix: seat loading and proof variants key on it.
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
    from .round_files_stand import stand_layout
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
            for row in info.get('text', [])]


def ornament_rows(info, crop, brief):
    copy = ornament_copy(brief, copy_fields(brief))
    return [zone_record(zone, crop, copy) for zone in info.get('ornament_lettering', [])]
