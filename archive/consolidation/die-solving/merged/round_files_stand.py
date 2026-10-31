"""Picked-layout adapter for the single-product counter-tray engine.

Only measurements, count and source-panel proportions enter geometry. Artwork
and words are placed later; a photograph never supplies a cut or fold path.
The brief's rows × columns build the holder; the picture's own count is kept
beside it and any difference is listed (owner, 2026-10-27; D-D6-2). With no
picture (``inspection`` None: the die comes first, owner 2026-10-28) the die is
solved from the brief and the product records alone, before any design exists.
"""
from pathlib import Path
import math
from statistics import median

from apps.dielines.geometry import counter_display as production
from apps.dielines.geometry import counter_tray_header as engine

from .round_flow import write_json


def _number(value, label, default=None):
    if value is None:
        if default is None:
            raise ValueError(label + ' is needed to build the product holder')
        value = default
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(label + ' must be a finite positive measurement')
    return float(value)


def stand_layout(brief, inspection):
    """The grid the holder is built for, the grid the picture shows, and their difference."""
    seen = (inspection or {}).get('stand', {})
    observed = {key: seen.get(key) for key in ('rows', 'columns', 'count')}
    stand = brief.get('stand') or {}
    layout = stand.get('layout') or {}
    count, rows, columns = stand.get('count'), layout.get('rows'), layout.get('columns')
    whole = lambda value: isinstance(value, int) and not isinstance(value, bool) and value > 0
    if whole(count) and whole(rows) and not whole(columns) and count % rows == 0:
        columns = count // rows
    if whole(count) and whole(columns) and not whole(rows) and count % columns == 0:
        rows = count // columns
    if whole(rows) and whole(columns) and whole(count) and rows * columns == count <= 100:
        built, source = {'rows': rows, 'columns': columns, 'count': count}, 'brief'
        note = (None if built == observed else
                f"The picture shows {observed['count']} products ({observed['rows']} rows × {observed['columns']} across); "
                f"the stand is built for the brief’s {count} ({rows} rows × {columns} across).")
    elif inspection is None:
        raise ValueError('The die comes first: the brief must give rows × columns that make its count')
    else:
        built, source = dict(observed), 'picture'
        note = 'The brief gives no rows × columns that make its count, so the stand is built for the picture’s grid.'
    return dict(built, source=source, observed=observed, differs=built != observed, note=note)


def _panel_ratio(inspection, name):
    panel = (inspection or {}).get('panels', {}).get(name, {})
    box = panel.get('crop_px')
    if box is None:
        return None
    if (not isinstance(box, (list, tuple)) or len(box) != 4 or
            any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in box)):
        raise ValueError('The ' + name + ' source crop must be a pixel rectangle')
    left, top, right, bottom = box
    if left < 0 or top < 0 or right <= left or bottom <= top:
        raise ValueError('The ' + name + ' source crop has no positive area')
    image_size = inspection.get('image_size_px')
    if image_size and (right > image_size[0] or bottom > image_size[1]):
        raise ValueError('The ' + name + ' source crop is outside the picked picture')
    return (bottom - top) / (right - left)


def observed_row_placement(inspection, product_height, front_height, header_height):
    """Derive seats from full front bottles, cap-top differences and the base edge.

    These are provisional orthographic reconstruction measurements. A partially
    visible rear cap supplies its top only, never an invented full bottle box.
    """
    result = {'applied': False, 'provisional': True, 'method':
              'Front bottle height sets vertical scale; paired cap tops set row rises; base top sets front seat'}
    if inspection is None:
        return dict(result, reason='The die comes first: no picture, so the engine\'s own row rises')
    layout = inspection['stand']
    rows, columns = layout['rows'], layout['columns']
    bottles = layout.get('bottles')
    if not isinstance(bottles, list) or len(bottles) != rows * columns:
        return dict(result, reason='A located bottle observation is needed for every row and column')
    boxes = {}
    for bottle in bottles:
        if not isinstance(bottle, dict):
            return dict(result, reason='Every bottle observation must identify its grid cell and pixel rectangle')
        row, column, box = (bottle.get(key) for key in ('row', 'column', 'box_px'))
        if (isinstance(row, bool) or isinstance(column, bool) or not isinstance(row, int)
                or not isinstance(column, int) or not 0 <= row < rows or not 0 <= column < columns
                or (row, column) in boxes or not isinstance(box, (list, tuple)) or len(box) != 4
                or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in box)
                or box[0] < 0 or box[1] < 0 or box[2] <= box[0] or box[3] <= box[1]):
            return dict(result, reason='Bottle observations must cover unique grid cells with positive pixel rectangles')
        if inspection.get('image_size_px') and (box[2] > inspection['image_size_px'][0] or box[3] > inspection['image_size_px'][1]):
            return dict(result, reason='A bottle observation lies outside the picked picture')
        boxes[row, column] = list(box)
    base = inspection.get('panels', {}).get('stand_base', {}).get('crop_px')
    header = inspection.get('panels', {}).get('stand_header', {}).get('crop_px')
    if not base or not header:
        return dict(result, reason='Both the base top and header bottom must be located in the picture')
    front = [boxes[0, column] for column in range(columns)]
    if any(box[3] > base[1] for box in front):
        return dict(result, reason='The front bottle bottoms are occluded by the base; their full height is unresolved')
    scale = [product_height / (box[3] - box[1]) for box in front]
    gaps = [(base[1] - box[3]) * value for box, value in zip(front, scale)]
    front_seat = front_height + median(gaps)
    row_records = []
    for row in range(rows):
        rises = [(front[column][1] - boxes[row, column][1]) * scale[column] for column in range(columns)]
        if min(rises) < 0 < max(rises):
            return dict(result, reason='Cap-top observations disagree on whether this row is above or below the front row')
        rise = median(rises)
        row_records.append({'row': row, 'rise_mm': rise, 'seat_z_mm': front_seat + rise,
                            'column_rises_mm': rises, 'source_boxes_px': [boxes[row, column] for column in range(columns)]})
    header_gaps = [(box[1] - header[3]) * value for box, value in zip(front, scale)]
    measured_height = front_seat + product_height + header_height + median(header_gaps)
    return dict(result, applied=True, rows=row_records,
                row_seat_z_mm=[row['seat_z_mm'] for row in row_records],
                front_clearance_above_base_mm=median(gaps), column_mm_per_pixel=scale,
                header_gap_above_front_caps_mm=median(header_gaps), measured_height_mm=measured_height,
                source_base_crop_px=list(base), source_header_crop_px=list(header),
                limitation='Pixel heights preserve the observed front elevation; physical measurements and a folded sample remain required')


def solve_stand(brief, inspection, *, include_enclosure=False, rear_visibility=False):
    """Return serializable geometry and reports without generating any artwork."""
    dimensions = brief.get('dimensions_mm', {})
    stand = brief.get('stand', {})
    target = stand.get('dimensions_mm', {})
    layout = stand_layout(brief, inspection)
    rows, columns, count = (layout.get(key) for key in ('rows', 'columns', 'count'))
    if (any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in (rows, columns, count))
            or rows * columns != count or count > 100):
        raise ValueError('The picked picture must declare a count equal to its rows times columns')
    pw = _number(dimensions.get('width', dimensions.get('diameter')), 'Product width')
    pd = _number(dimensions.get('depth'), 'Product depth', pw)
    ph = _number(dimensions.get('height'), 'Product height')
    board = _number(target.get('board_thickness'), 'Board thickness', 1.5)
    clearance = 0.5  # total opening clearance, not 0.5 mm on each side
    opening = max(pw, pd) + clearance
    edge = 3 * board
    fit = max(board, 1.0)
    minimum_width = columns * opening + (columns + 1) * edge + 2 * fit + 2 * board
    minimum_depth = rows * opening + (rows + 1) * edge + 2 * fit + 2 * board
    width = _number(target.get('width'), 'Stand width', minimum_width)
    depth = _number(target.get('depth'), 'Stand depth', minimum_depth)
    adjustments = []
    provisional = stand.get('provisional', True) is not False
    for key, original, needed in (('width', width, minimum_width), ('depth', depth, minimum_depth)):
        if provisional and original < needed:
            adjustments.append({'dimension': key, 'from_mm': original, 'to_mm': needed,
                                'reason': 'Fit the observed count with product clearance and three-board webs'})
    if provisional:
        width, depth = max(width, minimum_width), max(depth, minimum_depth)
    floor_width = width - 2 * board
    header_ratio = _panel_ratio(inspection, 'stand_header')
    base_ratio = _panel_ratio(inspection, 'stand_base')
    header_height = floor_width * header_ratio if header_ratio is not None else ph * 0.6
    front_height = floor_width * base_ratio + board if base_ratio is not None else min(25.0, ph * 0.25)
    height = _number(target.get('height'), 'Stand height', ph + header_height + board)
    placement = observed_row_placement(inspection, ph, front_height, header_height)
    if placement['applied'] and len(placement['row_seat_z_mm']) != rows:
        placement = {'applied': False, 'provisional': True, 'method': placement['method'],
                     'reason': 'The picture’s rows differ from the built rows; seats use the engine’s own rises'}
    if placement['applied']:
        row_support_depth = rows * (opening + 2 * edge) + 2 * fit + 2 * board
        if provisional and depth < row_support_depth:
            adjustments.append({'dimension': 'depth', 'from_mm': depth, 'to_mm': row_support_depth,
                                'reason': 'Retain three-board edge webs around each separate measured row collar'})
            depth = row_support_depth
    if placement['applied'] and provisional and abs(height - placement['measured_height_mm']) > 1e-9:
        adjustments.append({'dimension': 'height', 'from_mm': height, 'to_mm': placement['measured_height_mm'],
                            'reason': 'Preserve the measured cap-top gap below the header after raising the pictured bottle seats'})
        height = placement['measured_height_mm']
    # Keep the constructed back >= front after the engine subtracts board and
    # header thickness. An exact decimal boundary can otherwise round below it.
    minimum_height = math.nextafter(front_height + header_height, math.inf)
    if provisional and height < minimum_height:
        adjustments.append({'dimension': 'height', 'from_mm': height, 'to_mm': minimum_height,
                            'reason': 'Retain the picked panel proportions with a back wall at least as tall as the front'})
        height = minimum_height
    if placement['applied']:
        placement['height_matches_observation'] = abs(height - placement['measured_height_mm']) <= engine.TOL_MM
    profile = 'circle' if dimensions.get('diameter') and not dimensions.get('width') else 'square'
    # counter_tray_header 1.0 (owner, 2026-10-28): the production die, its board preset by the brief's thickness
    record = production.solve(product='bottle', board='e_flute' if abs(board - 1.5) < 1e-6 else 'white_card_0_5'
                              if abs(board - 0.5) < 1e-6 else 'sbs_1_5', product_grid={
        'product_width_mm': pw, 'product_depth_mm': pd, 'product_height_mm': ph,
        'rows': rows, 'columns': columns, 'count': count,
        'width_mm': width, 'depth_mm': depth, 'height_mm': height,
        'header_height_mm': header_height, 'front_height_mm': front_height,
        'hole_shape': profile, 'clearance_mm': clearance, 'top_edge': 'square',
        'row_seat_z_mm': placement['row_seat_z_mm'] if placement['applied'] else None})
    visibility_adjustment = None
    if rear_visibility:
        if not provisional:
            raise ValueError('Rear visibility adjustment needs provisional stand measurements')
        visibility_adjustment = engine.product_tray_raise_rear(record)
        raised = visibility_adjustment.pop('record')
        record = production.resolve_raised(record, raised)
        height = record['inputs']['height_mm']
        if placement['applied']:
            placement['height_matches_observation'] = abs(height - placement['measured_height_mm']) <= engine.TOL_MM
    die = engine.build_die(record)
    fold = engine.fold_check(record, die)
    sight = engine.sightlines(record)
    geometry = production.layer_geometry(die)
    surfaces = {}
    tray = next(part for part in die.parts if part.name == 'tray')
    for key, name in (('stand_header', 'header front'), ('stand_base', 'front panel')):
        polygon = next(face for face_name, face, _printed in tray.faces if face_name == name)
        left, top, right, bottom = polygon.bounds
        surfaces[key] = {'part': 'tray', 'face': name, 'box_mm': list(polygon.bounds),
                         'size_mm': [right - left, bottom - top], 'polygon_mm': [list(point) for point in polygon.exterior.coords],
                         'source_crop_px': (inspection or {}).get('panels', {}).get(key, {}).get('crop_px')}
    elevation = {'width_mm': width, 'height_mm': height,
                 'header_box_mm': [board, 0.0, width - board, header_height],
                 'base_box_mm': [board, height - front_height, width - board, height - board],
                 'platform_fronts': engine.product_tray_platform_fronts(record),
                 'product_slots': [{'index': hole['index'], 'row': hole['row'], 'column': hole['column'],
                     'box_mm': [hole['product_centre_mm'][0] - pw / 2, height - hole['seat_z_mm'] - ph,
                                hole['product_centre_mm'][0] + pw / 2, height - hole['seat_z_mm']],
                     'seat_z_mm': hole['seat_z_mm'],
                     'depth_mm': hole['product_centre_mm'][1]} for hole in record['holes']]}
    result = {'schema': 'round_files_stand/1', 'record': record, 'count': count, 'rows': rows, 'columns': columns,
            'layout': layout,
            'valid': fold['passed'], 'fold_check': fold, 'sightlines': sight,
            'sheet_mm': [die.sheet_w, die.sheet_h], 'surfaces': surfaces,
            'die': {'cut': geometry['cut'] + [
                [[cx + radius * math.cos(2 * math.pi * i / 128), cy + radius * math.sin(2 * math.pi * i / 128)]
                 for i in range(129)] for cx, cy, radius in geometry['holes']], 'fold': geometry['crease']},
            'guides': {'safe': geometry['safe'], 'bleed': geometry['bleed']},
            'layers_geometry': geometry, 'front_elevation': elevation,
            'header_mm': surfaces['stand_header']['size_mm'], 'base_front_mm': surfaces['stand_base']['size_mm'],
            'dimensions_mm': {'width': width, 'depth': depth, 'height': height, 'board_thickness': board},
            'provisional': True, 'dimension_adjustments': adjustments, 'observed_row_placement': placement, 'measurement_sources': {
                'layout': ('the brief’s rows × columns; the picture’s grid is listed beside it' if layout['source'] == 'brief'
                           else 'picked-picture inspection; the brief gives no complete grid'),
                'header_height': 'source crop aspect at the tray width' if header_ratio is not None else 'provisional 60% of product height',
                'front_height': 'source crop aspect at the tray width plus board' if base_ratio is not None else 'provisional quarter product height, at most 25 mm',
                'missing_stand_dimensions': 'minimum holder fit with three-board webs, or product plus header height'}}
    if include_enclosure:
        enclosure = engine.product_tray_enclosure_elevations(record)
        elevation['enclosure_faces'] = enclosure['front_faces']
        elevation['enclosure_projection'] = enclosure['projection_note']
        result['side_elevation'] = enclosure['side_elevation']
        result['enclosure_surfaces'] = []
        for name, polygon, printed in tray.faces:
            if name not in ('back panel', 'left side', 'right side', 'floor'):
                continue
            result['enclosure_surfaces'].append({'part': tray.name, 'face': name,
                'box_mm': list(polygon.bounds), 'polygon_mm': [list(point) for point in polygon.exterior.coords],
                'printed': printed, 'material': None,
                'note': 'Actual engine face; a source-supported material or finish must be assigned separately'})
    if visibility_adjustment is not None:
        result['rear_visibility_adjustment'] = visibility_adjustment
    return result


def build_stand(brief, inspection, outdir, *, include_enclosure=False, rear_visibility=False):
    """Write the engine record and its independent fold and sightline reports."""
    result = solve_stand(brief, inspection, include_enclosure=include_enclosure, rear_visibility=rear_visibility)
    root = Path(outdir)
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / 'stand-geometry.json', result)
    write_json(root / 'stand-die.json', result['record'])
    write_json(root / 'stand-fold-check.json', result['fold_check'])
    write_json(root / 'stand-sightlines.json', result['sightlines'])
    return result
