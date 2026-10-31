"""Extract print media from one pinned picture without generating another picture.

Every coordinate comes from the recorded inspection. Source pixels outside the
listed removal and header-extension masks remain exact in the 2x baseline.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re

import cv2
import fitz
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt

from . import lid_master as metrics
from .round_files_ornament import ARABIC, face_for, ornament_copy, zone_mask, zone_record

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


def _region_mask(size, boxes, crop):
    result = np.zeros((size[1], size[0]), dtype=bool)
    for box in boxes:
        x0, y0, x1, y1 = _local_box(box, crop)
        result[y0:y1, x0:x1] = True
    return result


def silhouette(size, points, crop):
    mask = Image.new('L', size, 0)
    ImageDraw.Draw(mask).polygon([(x-crop[0], y-crop[1]) for x, y in points], fill=255)
    return np.asarray(mask) > 0


def gold_mask(rgb):
    """Colour selection only; no new line is fitted or moved."""
    hsv = cv2.cvtColor(rgb.astype('uint8'), cv2.COLOR_RGB2HSV)
    return ((hsv[..., 0] >= 12) & (hsv[..., 0] <= 39) &
            (hsv[..., 1] >= 35) & (hsv[..., 2] >= 75))


def letter_mask(rgb, plan, crop):
    """Remove every pixel in tight lettering boxes, including shadows and highlights."""
    result = np.zeros(rgb.shape[:2], dtype=bool)
    for row in plan.get('text', []) + plan.get('marks', []):
        region = _region_mask((rgb.shape[1], rgb.shape[0]), [row['box_px']], crop)
        # Gold engraving can have light faces, dark shadows and antialiased edges.
        # A colour threshold cannot prove those source glyph pixels are all gone.
        result |= region
    for zone in plan.get('ornament_lettering', []):
        result |= zone_mask((rgb.shape[1], rgb.shape[0]), zone, crop)
    return result


def text_rows(info, crop, literal):
    """Live COPY rows of one panel; the face follows the words' script."""
    return [dict(field=row['field'], copy=literal[row['field']], box_norm=_normal_box(row['box_px'], crop),
                 color=row['color'], rotation=row.get('rotation', 0), face=face_for(literal[row['field']]))
            for row in info.get('text', [])]


def ornament_rows(info, crop, brief):
    copy = ornament_copy(brief, copy_fields(brief))
    return [zone_record(zone, crop, copy) for zone in info.get('ornament_lettering', [])]


def nearest_source_copy(rgb, mask):
    """Copy the nearest untouched pixel into each authorized removal pixel."""
    if not mask.any():
        return rgb.copy()
    if mask.all():
        raise ValueError('A removal mask cannot consume the whole source panel')
    indices = distance_transform_edt(mask, return_distances=False, return_indices=True)
    result = rgb.copy()
    result[mask] = rgb[indices[0][mask], indices[1][mask]]
    return result


def nearest_clean_source_copy(rgb, allowed, donors):
    """Fill only an allowed mask, copying actual clean source pixels in 2D."""
    if allowed.shape != rgb.shape[:2] or donors.shape != allowed.shape:
        raise ValueError('Source-copy masks must match the source pixels')
    if not allowed.any():
        return rgb.copy()
    if not donors.any():
        raise ValueError('No unchanged clean source pixels remain for extraction')
    if np.any(allowed & donors):
        raise ValueError('A replacement pixel cannot also be a clean source donor')
    indices = distance_transform_edt(~donors, return_distances=False, return_indices=True)
    result = rgb.copy()
    result[allowed] = rgb[indices[0][allowed], indices[1][allowed]]
    return result


def extend_header_edges(rgb, inside):
    """Square a silhouette using its own nearest vertical edge, without rescaling."""
    if not inside.any():
        raise ValueError('The header silhouette is empty')
    result = rgb.copy()
    valid_columns = np.flatnonzero(inside.any(axis=0))
    for x in range(rgb.shape[1]):
        source_x = x if inside[:, x].any() else int(valid_columns[np.argmin(abs(valid_columns-x))])
        valid_y = np.flatnonzero(inside[:, source_x])
        for y in np.flatnonzero(~inside[:, x]):
            source_y = int(valid_y[np.argmin(abs(valid_y-y))])
            result[y, x] = rgb[source_y, source_x]
    return result


def fidelity(source, doubled):
    compare = cv2.resize(doubled, (source.shape[1], source.shape[0]), interpolation=cv2.INTER_AREA)
    delta = metrics.delta_e00(metrics.srgb_to_lab(source), metrics.srgb_to_lab(compare))
    if min(source.shape[:2]) > 12:
        similarity = metrics.ssim(metrics.luma(source), metrics.luma(compare))
    else:
        similarity = None
    return {'de00_mean': float(delta.mean()), 'de00_max': float(delta.max()), 'ssim': similarity,
            'method': 'Exact cv2 2x Lanczos4 baseline brought back to source sampling with area averaging.',
            'scope': 'Before declared extraction and header edge extension; measurements are reports, not the eye.'}


def trace_lineart(mask, path):
    """Closed contours preserve the inspected gold footprint and its holes."""
    height, width = mask.shape
    contours_norm, commands = [], []
    # Trace pixel edges at 4x nearest sampling; at most 1/4 source-pixel quantization.
    large = np.repeat(np.repeat(mask.astype('uint8'), 4, axis=0), 4, axis=1)
    contours, hierarchy = cv2.findContours(large, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    for index, contour in enumerate(contours):
        simplified = cv2.approxPolyDP(contour, 1.0, True)  # <=0.25 original pixel
        if len(simplified) < 3:
            simplified = contour
        points = simplified[:, 0, :].astype(float)/4
        if len(points) < 3:
            continue
        parent = hierarchy[0][index][3]; depth = 0
        while parent >= 0:
            depth += 1; parent = hierarchy[0][parent][3]
        commands.append('M'+' L'.join(f'{x:.4f},{y:.4f}' for x, y in points)+' Z')
        contours_norm.append({'points': [[float(x/width), float(y/height)] for x, y in points], 'hole': bool(depth % 2)})
    value = ('<svg xmlns="http://www.w3.org/2000/svg" width="'+str(width)+'" height="'+str(height)+
             '" viewBox="0 0 '+str(width)+' '+str(height)+'"><path fill="#D5AF59" fill-rule="evenodd" d="'+
             ' '.join(commands)+'"/></svg>')
    Path(path).write_text(value)
    return contours_norm


def trace_measurement(path, mask):
    """Read the saved vector back at source scale, without trusting its point list."""
    with fitz.open(stream=Path(path).read_bytes(), filetype='svg') as svg:
        with fitz.open(stream=svg.convert_to_pdf(), filetype='pdf') as doc:
            pix = doc[0].get_pixmap(alpha=True)
            rendered = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 4)[..., 3] > 127
    if rendered.shape != mask.shape:
        raise ValueError('Vector trace changed its source coordinate space')
    union = mask | rendered
    boundary = lambda value: value & ~(cv2.erode(value.astype('uint8'), np.ones((3, 3), np.uint8)) > 0)
    source_edge, vector_edge = boundary(mask), boundary(rendered)
    distances = []
    if source_edge.any() and vector_edge.any():
        distances.extend(distance_transform_edt(~source_edge)[vector_edge])
        distances.extend(distance_transform_edt(~vector_edge)[source_edge])
    return {'iou': float((mask & rendered).sum()/union.sum()) if union.any() else 1.,
            'maximum_boundary_distance_source_px': float(max(distances)) if distances else None,
            'source_ink_pixels': int(mask.sum()), 'saved_vector_ink_pixels': int(rendered.sum()),
            'simplification_tolerance_source_px': .25,
            'method': 'Saved SVG rendered and compared with extracted gold pixels at original sampling.'}


def prepare_art(picture_path, inspection, brief, output_dir, expected_sha256=None, *, repair_masks=None):
    source_path, out = Path(picture_path), Path(output_dir)
    before = sha(source_path)
    if expected_sha256 is not None and before != expected_sha256:
        raise ValueError('Picked picture changed before extraction')
    with Image.open(source_path) as image:
        picture = image.convert('RGB')
    plan = validate_inspection(inspection, picture.size, brief)
    out.mkdir(parents=True, exist_ok=True)
    literal = copy_fields(brief)
    descriptor = {'schema': 'round_files_art/1', 'source': str(source_path.resolve()),
                  'source_sha256': before, 'source_size_px': list(picture.size), 'panels': {}}
    write(out/'inspection.json', plan)
    for key in PANEL_IDS:
        info = plan['panels'][key]; crop = info['crop_px']; folder = out/key
        folder.mkdir(parents=True, exist_ok=True)
        original = np.asarray(picture.crop(crop))
        doubled = cv2.resize(original, None, fx=2, fy=2, interpolation=cv2.INTER_LANCZOS4)
        Image.fromarray(original).save(folder/'crop.png')
        Image.fromarray(doubled).save(folder/'upscale.png')
        size = (original.shape[1], original.shape[0])
        inside = silhouette(size, info['print_polygon_px'], crop)
        words = letter_mask(original, info, crop)
        if repair_masks is not None:
            boxes = repair_masks[key]['removal_boxes_px']
            for box in boxes:
                _box(box, crop)
            words |= _region_mask(size, boxes, crop)
        word_boxes = words.copy()
        line_regions = _region_mask(size, info.get('lineart_boxes_px', []), crop)
        lines = gold_mask(original) & line_regions & inside & ~word_boxes
        # Masks include the original raster's anti-aliased edge; vectors trace the gold core.
        line_removal = (cv2.dilate(lines.astype('uint8'), np.ones((3, 3), np.uint8)) > 0) & line_regions & inside & ~word_boxes
        removal = (words | line_removal) & inside
        removal2 = np.repeat(np.repeat(removal, 2, axis=0), 2, axis=1)
        inside2 = np.repeat(np.repeat(inside, 2, axis=0), 2, axis=1)
        working = doubled.copy()
        extension = np.zeros(inside2.shape, dtype=bool)
        if key == 'stand_header' and repair_masks is None:
            working = extend_header_edges(working, inside2)
            extension = ~inside2
        colour_region = _region_mask(size, info.get('colour_print_boxes_px', []), crop) & inside
        colour_region2 = np.repeat(np.repeat(colour_region, 2, axis=0), 2, axis=1)
        if key.startswith('stand_'):
            if repair_masks is not None:
                extension = ~inside2 if key == 'stand_header' else extension
                clean = nearest_clean_source_copy(doubled, removal2 | extension,
                                                 inside2 & ~removal2)
            else:
                clean = nearest_source_copy(working, removal2)
            rgba = np.dstack((clean, np.full(clean.shape[:2], 255, dtype='uint8')))
            outside_same = np.array_equal(clean[~(removal2 | extension)], doubled[~(removal2 | extension)])
            substrate = 'Printed stand picture; retained source pixels outside declared extraction and extension.'
        else:
            clean = nearest_source_copy(doubled, removal2) if key == 'body_front' and colour_region.any() else doubled
            rgba = np.dstack((clean, (colour_region2*255).astype('uint8')))
            rgba[~colour_region2] = 0
            outside_same = np.array_equal(clean[colour_region2 & ~removal2], doubled[colour_region2 & ~removal2])
            substrate = ('Only inspected printed-colour zones remain; the clear body and liquid are not ink.'
                         if key == 'body_front' else 'Physical gold cap is not painted ink.')
        Image.fromarray(rgba).save(folder/'artwork.png')
        for name, mask in [('text-removal-mask', words), ('foil-source-mask', lines), ('removal-mask', removal), ('print-silhouette', inside)]:
            Image.fromarray(mask.astype('uint8')*255).save(folder/(name+'.png'))
        Image.fromarray(extension.astype('uint8')*255).save(folder/'header-extension-mask.png')
        svg = folder/'lineart.svg'
        contours = trace_lineart(lines, svg) if lines.any() else []
        text = text_rows(info, crop, literal)
        marks = [dict(kind='logo', box_norm=_normal_box(row['box_px'], crop), color=row['color'],
                      rotation=row.get('rotation', 0), foil=True) for row in info.get('marks', [])]
        record = {'id': key, 'crop': str((folder/'crop.png').resolve()), 'upscale': str((folder/'upscale.png').resolve()),
                  'raster': str((folder/'artwork.png').resolve()), 'lineart_svg': str(svg.resolve()) if contours else None,
                  'contours_norm': contours, 'text': text, 'marks': marks, 'source_crop_px': crop,
                  'ornament': ornament_rows(info, crop, brief),
                  'source_size_px': list(size), 'size_px': [size[0]*2, size[1]*2],
                  'fidelity': fidelity(original, doubled), 'substrate': substrate,
                  'source_crop_sha256': sha(folder/'crop.png'), 'raster_sha256': sha(folder/'artwork.png'),
                  'lineart_sha256': sha(svg) if contours else None,
                  'lineart_measurement': trace_measurement(svg, lines) if contours else None,
                  'preservation': {'outside_allowed_masks_exact': bool(outside_same),
                      'removal_pixels_2x': int(removal2.sum()), 'extension_pixels_2x': int(extension.sum()),
                      'lineart_source_pixels': int(lines.sum()), 'source_pixel_copy_only': True,
                      'declared_colour_print_boxes_px': info.get('colour_print_boxes_px', []),
                      'colour_print_pixels_2x': int(colour_region2.sum()),
                      'allowed': ['Replace inspected lettering with supplied live COPY', 'Replace inspected brand with approved vector',
                                  'Extract inspected gold leading as positional vector contours']+
                                 (['Square header by copying its own silhouette edge; no interior stretching'] if key=='stand_header' else [])+
                                 (['Replace invented ornament lettering with the brand and Arabic COPY along its own path']
                                  if info.get('ornament_lettering') else []),
                      'substrate_excluded_from_print': key in ('body_front', 'cap_front')}}
        if repair_masks is not None:
            record['preservation']['repair_extraction'] = deepcopy(repair_masks[key])
            record['preservation']['source_copy_method'] = 'Nearest unchanged clean source pixel in two dimensions; extraction pixels cannot be donors.'
        write(folder/'record.json', record)
        descriptor['panels'][key] = record
    if sha(source_path) != before:
        raise ValueError('Picked picture changed during extraction')
    descriptor['source_unchanged'] = True
    write(out/'art.json', descriptor)
    return descriptor


def mechanical_drawing(flat_paths, brief, geometry, output_path, *, inspection, body_proofs, px_per_mm=6):
    """Use final trim PNGs and exact engine front-elevation coordinates.

    Rear seats may be occluded in a true front view. Their actual positions and
    depths are retained; this drawing never invents raised seats to show them.
    """
    product = brief['dimensions_mm']
    width, height = float(product['width']), float(product['height'])
    cap = float(product['cap_height']); body = height-cap
    if min(width, height, cap, body, px_per_mm) <= 0:
        raise ValueError('The mechanical drawing needs positive product dimensions')
    elevation = geometry.get('front_elevation')
    if not isinstance(elevation, dict):
        raise ValueError('An engine front elevation is required; drawing cannot invent stand geometry')
    sw, sh = float(elevation['width_mm']), float(elevation['height_mm'])
    slots = elevation['product_slots']
    if len(slots) != geometry['count']:
        raise ValueError('Engine front elevation count differs from its inspected loading')
    header, base_box = elevation['header_box_mm'], elevation['base_box_mm']
    platforms = elevation.get('platform_fronts', [])
    enclosure = elevation.get('enclosure_faces', [])
    if not isinstance(platforms, list):
        raise ValueError('Engine support faces must be an explicit list')
    for face in platforms:
        if face['printed'] is not False or face['material'] != 'unprinted board':
            raise ValueError('Only unprinted engine board may use the neutral drawing material')
        depth = face['depth_mm']
        if isinstance(depth, bool) or not isinstance(depth, (float, int)) or not math.isfinite(depth) or depth < 0:
            raise ValueError('Engine support face depth must be a finite positive coordinate')
    for face in enclosure:
        if not isinstance(face['depth_mm'], (float, int)) or not math.isfinite(face['depth_mm']):
            raise ValueError('Engine enclosure face needs a finite physical depth')
        if any(not (0 <= point[0] <= sw and 0 <= point[1] <= sh) for point in face['polygon_mm']):
            raise ValueError('Engine enclosure polygon is out of bounds')
    for box in [header, base_box]+[row['box_mm'] for row in slots]+[row['box_mm'] for row in platforms+enclosure]:
        if len(box)!=4 or not 0 <= box[0] < box[2] <= sw or not 0 <= box[1] < box[3] <= sh:
            raise ValueError('Engine front elevation contains an out-of-bounds piece')
    margin, gap = 8., 18.
    canvas = Image.new('RGBA', (math.ceil((2*margin+width+gap+sw)*px_per_mm),
                               math.ceil((2*margin+max(height, sh))*px_per_mm)), 'white')
    pieces = {key: Image.open(path).convert('RGBA') for key, path in flat_paths.items()}
    material = inspection.get('drawing_material')
    physical = material.get('physical_source') if material is not None else None
    engine_material = None
    if material is not None and material['status'] == 'engine':
        if physical is not None:
            raise ValueError('Engine material drawing cannot contain physical source-picture crops')
        wall, base_height = material['wall_mm'], material['base_mm']
        if (any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                or value <= 0 for value in (wall, base_height)) or 2 * wall >= width or wall + base_height >= body):
            raise ValueError('Engine acrylic walls and base must leave a positive liquid cavity')
        engine_material = {'wall_mm': wall, 'base_mm': base_height,
            'liquid_box_mm': [wall, wall, width-wall, body-base_height], 'provisional': True,
            'cap_gradient_rgb': [[121, 83, 28], [244, 218, 155], [213, 175, 89], [177, 130, 50]],
            'scope': 'Engine product drawing only; no source material raster and no change to print separations'}
    if physical is not None:
        records = {'physical:cap': physical['cap_source']}
        records.update({'physical:'+key: record for key, record in physical['body_sources'].items()})
        for key, record in records.items():
            if sha(record['path']) != record['sha256']:
                raise ValueError('The original physical source material pixels changed')
            pieces[key] = Image.open(record['path']).convert('RGBA')
    if material is not None and material['status'] == 'measured':
        liquid_box = material['liquid_box_norm']
        if (len(liquid_box) != 4 or not 0 <= liquid_box[0] < liquid_box[2] <= 1
                or not 0 <= liquid_box[1] < liquid_box[3] <= 1):
            raise ValueError('Measured liquid box must remain within the acrylic source crop')
        if sha(material['wall_raster']) != material['wall_raster_sha256']:
            raise ValueError('The measured source acrylic wall pixels changed')
        pieces['acrylic-walls'] = Image.open(material['wall_raster']).convert('RGBA')
    def paste(key, x, y, w, h, ground=None):
        size = (max(1, round(w*px_per_mm)), max(1, round(h*px_per_mm)))
        piece = pieces[key].resize(size, Image.Resampling.LANCZOS)
        physical_key = 'physical:cap' if key == 'cap_front' else 'physical:'+key.removeprefix('body:')
        if engine_material is not None and key == 'cap_front':
            stops = np.asarray(engine_material['cap_gradient_rgb'], dtype=float)
            positions = np.linspace(0, 1, size[0])
            stripe = np.stack([np.interp(positions, [0, .12, .52, 1], stops[:, channel]) for channel in range(3)], axis=1)
            gold = np.tile(stripe.round().astype('uint8')[None, :, :], (size[1], 1, 1))
            base = Image.fromarray(gold).convert('RGBA')
            ImageDraw.Draw(base).rectangle((0, 0, size[0]-1, size[1]-1), outline=(121, 83, 28, 255),
                                           width=max(1, round(.12 * px_per_mm)))
            base.alpha_composite(piece); piece = base
        elif engine_material is not None and key.startswith('body:'):
            base = Image.new('RGBA', size, (210, 220, 227, 36))
            drawing = ImageDraw.Draw(base)
            x0, y0, x1, y1 = [round(value*px_per_mm) for value in engine_material['liquid_box_mm']]
            if ground:
                drawing.rounded_rectangle((x0, y0, x1-1, y1-1), radius=max(1, round(.6*px_per_mm)), fill=ground)
            drawing.rectangle((0, 0, size[0]-1, size[1]-1), outline=(144, 157, 166, 175), width=max(1, round(.1*px_per_mm)))
            for edge in (round(wall*.35*px_per_mm), size[0]-1-round(wall*.35*px_per_mm)):
                drawing.line((edge, 1, edge, size[1]-2), fill=(255, 255, 255, 210), width=max(1, round(.12*px_per_mm)))
            base.alpha_composite(piece); piece = base
        elif physical is not None and physical_key in pieces:
            base = pieces[physical_key].resize(size, Image.Resampling.LANCZOS)
            base.alpha_composite(piece); piece = base
        elif key.startswith('body:') and material is not None:
            base = Image.new('RGBA', size, (0, 0, 0, 0))
            if material['status'] == 'measured':
                if ground:
                    x0, y0, x1, y1 = [round(v*size[index % 2]) for index, v in enumerate(liquid_box)]
                    ImageDraw.Draw(base).rectangle((x0, y0, x1-1, y1-1), fill=ground)
                base.alpha_composite(pieces['acrylic-walls'].resize(size, Image.Resampling.LANCZOS))
            base.alpha_composite(piece)
            piece = base
        elif ground:
            base = Image.new('RGBA', size, ground); base.alpha_composite(piece); piece = base
        canvas.alpha_composite(piece, (round(x*px_per_mm), round(y*px_per_mm)))
    from .round_files_stand import stand_layout
    loading, layout = shade_loading(inspection, brief), stand_layout(brief, inspection)
    shades = {'shade_'+str(index): shade['hex'] for index, shade in enumerate(brief['shades'])}
    assigned = {(row['row'], row['column']): row['shade_field'] for row in loading['slots']}
    if set(assigned) != {(row['row']-1, row['column']-1) for row in slots}:
        raise ValueError('The inspected shade seats differ from the engine loading')
    for field, proof in body_proofs.items():
        pieces['body:'+field] = Image.open(proof['path']).convert('RGBA')
    def bottle(x, y, field):
        key = field if field is not None else 'unresolved'
        colour = shades[field] if field is not None else None
        applied_colour = colour if physical is None and (material is None or material['status'] in ('measured', 'engine')) else None
        paste('cap_front', x, y, width, cap, '#D5AF59')
        paste('body:'+key, x, y+cap, width, body, applied_colour)
        source_material = physical['body_sources'].get(key) if physical is not None else None
        return {'shade_field': field, 'liquid_colour': applied_colour, 'observed_shade_colour': colour, 'proof': body_proofs[key],
                'physical_source_material': source_material,
                'substrate': ('Original observed physical source pixels with separate live print overlay' if source_material is not None else
                              'Observed shade colour' if applied_colour is not None else 'Unresolved material or shade; no liquid colour applied')}
    hero = bottle(margin, margin+max(height,sh)-height, loading['hero_shade_field'])
    sx = margin+width+gap
    paste('stand_header', sx+header[0], margin+header[1], header[2]-header[0], header[3]-header[1])
    placements=[]
    board_colour = '#E4E4E4'
    if physical is not None and physical['enclosure']['status'] == 'observed':
        board_colour = tuple(physical['enclosure']['interior']['rgb'])
    elevation_objects = [('enclosure', face) for face in enclosure] + [('board', face) for face in platforms] + [('bottle', slot) for slot in slots]
    for kind, slot in sorted(elevation_objects, key=lambda entry: entry[1]['depth_mm'], reverse=True):
        x0,y0,x1,y1=slot['box_mm']
        if kind == 'enclosure':
            colour = board_colour
            if physical is not None and physical['enclosure']['status'] == 'observed':
                sample = 'interior' if slot['kind'] == 'back_interior' else 'edge'
                colour = tuple(physical['enclosure'][sample]['rgb'])
            points = [(round((sx+x)*px_per_mm), round((margin+y)*px_per_mm)) for x, y in slot['polygon_mm']]
            ImageDraw.Draw(canvas).polygon(points, fill=colour)
            continue
        if kind == 'board':
            # Unprinted engine structure exists only in this mechanical drawing;
            # it is never painted into any source art or downloadable print plate.
            box = (round((sx+x0)*px_per_mm), round((margin+y0)*px_per_mm),
                   round((sx+x1)*px_per_mm)-1, round((margin+y1)*px_per_mm)-1)
            ImageDraw.Draw(canvas).rectangle(box, fill=board_colour)
            continue
        if abs((x1-x0)-width)>.001 or abs((y1-y0)-height)>.001:
            raise ValueError('Engine seat projection changes the physical product size')
        assignment = bottle(sx+x0, margin+y0, assigned[(slot['row']-1, slot['column']-1)])
        placements.append(dict(slot, **assignment))
    paste('stand_base',sx+base_box[0],margin+base_box[1],base_box[2]-base_box[0],base_box[3]-base_box[1])
    output=Path(output_path);output.parent.mkdir(parents=True,exist_ok=True)
    canvas.convert('RGB').save(output,dpi=(round(px_per_mm*25.4),)*2)
    record={'schema':'round_files_mechanical_drawing/1','label':'Engine product drawing · front elevation',
            'method':'Final trim pieces on exact engine coordinates; physical liquid and gold only in drawing.',
            'count':len(slots),'drawn_product_instances':len(placements),'stand_slots':placements,
            'intake_count':brief['stand']['count'],
            'count_source':('the brief’s rows × columns through the engine' if layout['source'] == 'brief'
                            else 'picked-picture inspection through the engine'),
            'stand_layout': layout,
            'hero': hero, 'shade_loading': loading,
            'drawing_material': material,
            'unprinted_structure': {'faces': platforms, 'drawing_colour': board_colour,
                'method': 'Engine front faces and bottles in descending physical depth; printed tray front is drawn last.',
                'scope': 'Observed provisional stock finish when source material is available, otherwise neutral unprinted board; original proof pixels and print masters remain unchanged.'},
            'enclosure': {'faces': enclosure,
                'material': physical['enclosure'] if physical is not None else None,
                'projection_difference': 'True front elevation shows actual side-wall thickness; perspective sloping side-wall wedges are represented in the separate engine side elevation.'},
            'bottle_master_scope':'Only the picked hero bottle master is supplied; loaded shade variants are drawing proofs, not print masters.',
            'proof_variants':body_proofs,
            'front_elevation':elevation,
            'source_sha256':{key:sha(path) for key,path in flat_paths.items()},'sha256':sha(output),
            'px_per_mm':px_per_mm,'projection':'True front elevation; rear-row occlusion is retained, never raised to expose it.'}
    if engine_material is not None:
        record['engine_material'] = engine_material
    write(output.with_suffix('.json'),record)
    return record
