"""Lettering the picture invents is an ornament zone, never copy.

The reader traces the zone's centre line in the picture; the build removes the
pictured pseudo-script along it and sets the brief's own COPY there as live
type, one word at a time along the same path. Nothing is transcribed from the
picture: the words are the brand and the brief's Arabic COPY fields.
"""
import math
import re

import cv2
import numpy as np

ARABIC = re.compile(r'[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufefc]')
BAND_COVER = 1.2      # removal reaches past the letters' anti-aliased edge
INK_SHARE = .78       # the tallest letter fills this share of the band
WORD_GAP_EM = .35
FIELD_GAP_EM = 1.2
MAX_FIELD_GAP_EM = 6.
MIN_SIZE_PT = 5.


def face_for(copy):
    return 'arabic' if ARABIC.search(copy) else 'latin'


def ornament_copy(brief, fields):
    """The zone's words in reading order: the brand, then every Arabic COPY field."""
    items = [('brand', brief['copy']['brand'])]
    items += [(key, value) for key, value in fields.items()
              if value and (key == 'product_arabic' or key.startswith('arabic_shade_'))]
    return [{'field': key, 'copy': value, 'face': face_for(value)} for key, value in items if value and value.strip()]


def zone_mask(size, zone, crop):
    """Crop-local pixels of the pictured lettering band."""
    mask = np.zeros((size[1], size[0]), np.uint8)
    points = np.array([[x - crop[0], y - crop[1]] for x, y in zone['path_px']], np.int32)
    cv2.polylines(mask, [points], False, 255, thickness=max(1, math.ceil(zone['height_px'] * BAND_COVER)),
                  lineType=cv2.LINE_8)
    return mask > 0


def zone_record(zone, crop, copy):
    w, h = crop[2] - crop[0], crop[3] - crop[1]
    return {'path_norm': [[(x - crop[0]) / w, (y - crop[1]) / h] for x, y in zone['path_px']],
            'height_norm': zone['height_px'] / h, 'color': zone['color'], 'copy': copy,
            'source_path_px': zone['path_px'], 'source_height_px': zone['height_px']}


def _walk(points):
    lengths = [0.]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.hypot(x1 - x0, y1 - y0))
    def at(distance):
        distance = min(max(distance, 0.), lengths[-1])
        for index in range(1, len(points)):
            if distance <= lengths[index] or index == len(points) - 1:
                span = lengths[index] - lengths[index - 1] or 1.
                t = (distance - lengths[index - 1]) / span
                (x0, y0), (x1, y1) = points[index - 1], points[index]
                return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
    return lengths[-1], at


def layout_runs(panel_id, index, zone, target, *, foil=False):
    """Words along the zone's path, in visual order, each turned to the path under it.

    The path runs the way the letters advance. A band with Arabic reads right to
    left, so its first field sits at the path's end. Fields that cannot fit at
    5 pt are left out from the end of the reading order and listed.
    """
    from .round_balm_master import glyph_metrics
    from .round_files_export import PT
    x0, y0, x1, y1 = target
    path = [(x0 + nx * (x1 - x0), y0 + ny * (y1 - y0)) for nx, ny in zone['path_norm']]
    length_mm, at = _walk(path)
    height_mm = zone['height_norm'] * (y1 - y0)
    items = list(zone['copy'])
    rtl = any(item['face'] == 'arabic' for item in items)
    left_out = []
    while items:
        groups = []
        for item in (reversed(items) if rtl else items):
            words = item['copy'].split()
            words = list(reversed(words)) if item['face'] == 'arabic' else words
            groups.append([(item, word, glyph_metrics(word, item['face'])) for word in words])
        flat = [entry for group in groups for entry in group]
        top = max(metric['box_em'][3] for _, _, metric in flat)
        bottom = min(metric['box_em'][1] for _, _, metric in flat)
        advance_em = sum(metric['advance_em'] for _, _, metric in flat)
        gaps_em = WORD_GAP_EM * (len(flat) - len(groups)) + FIELD_GAP_EM * (len(groups) - 1)
        size = min(height_mm * PT * INK_SHARE / max(top - bottom, .1), length_mm * PT / (advance_em + gaps_em))
        if size >= MIN_SIZE_PT:
            break
        left_out.append(items.pop()['field'])
    if not items:
        return [], {'size_pt': None, 'left_out': left_out, 'reason': 'The band is too short for its COPY at 5 pt.'}
    spare = length_mm * PT - size * (advance_em + gaps_em)
    field_gap = FIELD_GAP_EM * size
    if len(groups) > 1:
        field_gap += min(spare / (len(groups) - 1), (MAX_FIELD_GAP_EM - FIELD_GAP_EM) * size)
    used = size * advance_em + WORD_GAP_EM * size * (len(flat) - len(groups)) + field_gap * (len(groups) - 1)
    cursor = (length_mm * PT - used) / 2
    runs = []
    for group_index, group in enumerate(groups):
        if group_index:
            cursor += field_gap
        for word_index, (item, word, metric) in enumerate(group):
            if word_index:
                cursor += WORD_GAP_EM * size
            advance = metric['advance_em'] * size
            middle = (cursor + advance / 2) / PT
            ax, ay = at(middle - advance / 2 / PT)
            bx, by = at(middle + advance / 2 / PT)
            cx, cy = at(middle)
            runs.append({'name': f"{panel_id}:ornament{index}:{item['field']}:{len(runs)}", 'copy': word,
                         'face': item['face'], 'center_mm': [cx, cy],
                         'angle_deg': math.degrees(math.atan2(-(by - ay), bx - ax)),
                         'center_em_y': (top + bottom) / 2, 'size_pt': size, 'align': 'center',
                         'color': zone['color'], 'foil': foil, 'copy_field': item['field'], 'ornament': True})
            cursor += advance
    return runs, {'size_pt': size, 'left_out': left_out, 'words': len(runs), 'path_mm': length_mm}
