"""D-R1C-1: provisional accordion leaflet derived from a stick carton's inside.

This engine owns dimensions and fold geometry, not artwork or typesetting.
Native printed ink boxes are checked against its panel safe rectangles.
The folded width/height fit is geometric; stock caliper and assembly remain
provisional until a physical sample exists.
"""
from __future__ import annotations

import math
from numbers import Real

PANEL_ORDER = ('en1', 'en2', 'es1', 'es2', 'ar2', 'ar1')
VERSION = '0.1'


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(name + ' must be a finite number.')
    return float(value)


def layout(inside_mm=(20.0, 20.0, 73.0), *, clearance_mm=2.0, safe_mm=1.5):
    """Six equal panels, two per language; Arabic reads from the right."""
    if len(inside_mm) != 3:
        raise ValueError('Carton inside dimensions must be width, depth, height.')
    width, depth, height = [_number(value, 'Inside dimension') for value in inside_mm]
    clearance = _number(clearance_mm, 'Clearance')
    safe = _number(safe_mm, 'Safe inset')
    if min(width, depth, height, clearance, safe) <= 0:
        raise ValueError('Dimensions, clearance and safe inset must be positive.')
    panel_w, panel_h = width - clearance, height - clearance
    if min(panel_w, panel_h) <= 2 * safe:
        raise ValueError('The folded panel must retain a positive safe area.')
    sheet_w = len(PANEL_ORDER) * panel_w
    panels = []
    for index, name in enumerate(PANEL_ORDER):
        left, right = index * panel_w, (index + 1) * panel_w
        panels.append({'id': name, 'language': name[:2], 'rect_mm': [left, 0.0, right, panel_h],
                       'safe_mm': [left + safe, safe, right - safe, panel_h - safe]})
    cuts = [{'kind': 'cut', 'points_mm': points} for points in (
        [[0.0, 0.0], [sheet_w, 0.0]], [[sheet_w, 0.0], [sheet_w, panel_h]],
        [[sheet_w, panel_h], [0.0, panel_h]], [[0.0, panel_h], [0.0, 0.0]])]
    folds = [{'kind': 'fold', 'fold': 'valley' if index % 2 else 'mountain',
              'points_mm': [[index * panel_w, 0.0], [index * panel_w, panel_h]]}
             for index in range(1, len(PANEL_ORDER))]
    return {'schema': 'balm_leaflet_geometry/1', 'engine': 'balm_leaflet', 'version': VERSION,
            'provisional': True, 'inside_mm': [width, depth, height],
            'sheet_mm': [sheet_w, panel_h], 'folded_mm': [panel_w, panel_h],
            'clearance_mm': clearance, 'safe_inset_mm': safe, 'panel_count': len(panels),
            'printing': 'one side', 'fold_scheme': 'six-panel accordion; five alternating folds',
            'panel_order_left_to_right': list(PANEL_ORDER),
            'reading_order': {'en': ['en1', 'en2'], 'es': ['es1', 'es2'], 'ar': ['ar1', 'ar2']},
            'panels': panels, 'cuts': cuts, 'folds': folds,
            'planar_fit': panel_w < width and panel_h < height,
            'physical_status': 'PROVISIONAL: stock caliper, folded thickness and assembly need a physical sample.'}


def check_printed_lines(geometry, rows, *, tolerance_mm=0.001):
    """Measure every actual printed line, never an estimated preview row.

    Each row must contain name, panel and box_mm=[left, top, right, bottom]
    in sheet coordinates. Copy retention is a separate native-file check.
    """
    tolerance = _number(tolerance_mm, 'Tolerance')
    if not 0 <= tolerance <= 0.001:
        raise ValueError('Printed-line tolerance must be between zero and 0.001 mm.')
    panels = {panel['id']: panel for panel in geometry['panels']}
    lines = list(rows)
    if not lines:
        raise ValueError('At least one actual printed line is required.')
    checked, outside, crossings = [], [], []
    for row in lines:
        if not isinstance(row['name'], str) or not row['name']:
            raise ValueError('Each printed line requires a nonempty name.')
        if row['panel'] not in panels:
            raise ValueError('Printed line names an unknown leaflet panel.')
        if len(row['box_mm']) != 4:
            raise ValueError('Printed ink box must have four coordinates.')
        left, top, right, bottom = [_number(value, 'Ink coordinate') for value in row['box_mm']]
        if left >= right or top >= bottom:
            raise ValueError('Printed ink box must have positive width and height.')
        safe = panels[row['panel']]['safe_mm']
        inside = (left >= safe[0] - tolerance and top >= safe[1] - tolerance
                  and right <= safe[2] + tolerance and bottom <= safe[3] + tolerance)
        crossed = [index + 1 for index, fold in enumerate(geometry['folds'])
                   if left < fold['points_mm'][0][0] < right
                   and top < fold['points_mm'][1][1] and bottom > fold['points_mm'][0][1]]
        measured = {'name': row['name'], 'panel': row['panel'], 'box_mm': [left, top, right, bottom],
                    'safe_mm': safe, 'inside_safe': inside, 'crossed_folds': crossed}
        checked.append(measured)
        if not inside:
            outside.append(measured)
        if crossed:
            crossings.append(measured)
    return {'schema': 'balm_leaflet_printed_lines/1', 'method': 'Actual native/PDF printed ink boxes in sheet millimetres.',
            'tolerance_mm': tolerance, 'printed_lines': checked, 'measured_line_count': len(checked),
            'outside_safe_area': outside, 'all_inside_safe': not outside,
            'crossed_lines': crossings, 'crossings': sum(len(row['crossed_folds']) for row in crossings),
            'nothing_across_a_crease': not crossings,
            'holds': not outside and not crossings and geometry['planar_fit'],
            'copy_retention_checked_here': False}
