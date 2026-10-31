"""Per-surface fidelity instrument for the D1 stand surfaces (owner Day 6, §2.2) and
its negative control (§2.2: "the Day 4 flat surfaces must fail this instrument against D1").

The instrument measures the EMITTED files, never the JSON plan: artwork.pdf opened with
PyMuPDF (live glyph origins from get_texttrace, vector fills from get_drawings, rasters
rendered from the PDF at 300 PPI; artwork.png is checked against that render).
design-graph.json is read only to name the planned line each live glyph belongs to; the
Day 4 flats have no graph, so there the measured element centres name the lines, and
every record says which assignment it used.

Measured faces (header.front, riser.3.front, lip.front) are judged against the D1
measurement. Composed faces (riser.2.front, riser.1.front, side.left, side.right) carry no
measured element: they are recorded as "composed, not measured", receive no placement or
colour pass claim, and are checked only for grammar (no added copy, no raster, the device
present where the strip crosses), for the shared field, and for continuity across the
front seams. Honest FAIL beats convenient PASS; no threshold below may be loosened.
"""
from pathlib import Path
import datetime, json, math, re
import cv2, fitz, numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from . import fidelity_assets as fa
from .matte_colour import lab, de

MM = 72 / 25.4

# Owner §2.2, verbatim: "placement ≤ 1.0 mm / 3 %, colour ΔE2000 ≤ 4 (ink) / ≤ 6 (field),
# gesture centreline within 1.0 mm of the measured path at stand scale". Never loosened.
PLACEMENT_OFFSET_MM = 1.0        # centre offset per axis and baseline offset
PLACEMENT_SIZE_PERCENT = 3.0     # size per axis
INK_DELTA_E = 4.0                # type, logo, rule
FIELD_DELTA_E = 6.0              # field samples, field continuity across a seam
GESTURE_CENTRELINE_MM = 1.0      # cream centreline against the measured path
SEAM_MM = 1.0                    # device continuity across a seam, the same bar as the centreline
THRESHOLDS = {
    'placement_offset_mm': PLACEMENT_OFFSET_MM, 'placement_size_percent': PLACEMENT_SIZE_PERCENT,
    'ink_delta_e_2000': INK_DELTA_E, 'field_delta_e_2000': FIELD_DELTA_E,
    'gesture_centreline_mm': GESTURE_CENTRELINE_MM, 'seam_device_mm': SEAM_MM,
    'wording': 'owner Day 6 §2.2: placement ≤ 1.0 mm / 3 %, colour ΔE2000 ≤ 4 (ink) / ≤ 6 (field), '
               'gesture centreline within 1.0 mm of the measured path at stand scale'}

RENDER_PPI = 300                 # field colour, PNG comparison, device mask
INK_BOX_PPI = 600                # live-text ink boxes: render minus text-stripped render
INK_COLOUR_PPI = 1200            # pale-class median inside a measured box; thin strokes need interior pixels
FIELD_WINDOW_PX = 11             # the measurement's own sampling window
PALE_FLOOR = (200, 160, 110)     # pale ink class: R>200 and G>160 and B>110
CHANGED_LEVELS = 4               # a pixel is text ink when removing the text moves any channel by more than this
FILL_TOLERANCE = 1.5             # /255 per channel when a vector fill is matched to a recorded colour
EXCLUSION_MM = 1.5               # margin around device, copy and marks when field pixels are collected
LOCUS_STEP_MM = 5.0              # sampling grid on a composed face
LOCUS_NEIGHBOURS = 16
CREAM_SRGB = (245.0, 219.0, 183.0)   # measurement 'shared_device_colours'
SHADOW_SRGB = (130.0, 70.0, 17.0)
COMPOSED = 'composed, not measured'
# Top to base, the order the measurement lists the front faces and the device crosses them.
FRONT_STRIP = ['header.front', 'riser.3.front', 'riser.2.front', 'lip.front', 'riser.1.front']
RISER3_SHADOW_ROW_PX = 1160      # addendum: "Original y1160 retained as photographed shadow diagnostics"

DAY6 = fa.ROOT / 'docs/audit/day-6'
SURFACES = DAY6 / 'stand/surfaces'
MEASUREMENT = DAY6 / 'concept-D1-measurement.json'
ADDENDUM = DAY6 / 'concept-D1-measurement-addendum.json'
DAY4 = fa.ROOT / 'docs/audit/day-4/stand-family/surfaces'
REVIEW_STATE = 'designer_review'


# ----------------------------------------------------------------------------- helpers
def plain(value):
    """JSON-safe copy: numpy scalars and arrays become Python values."""
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def write(path, data):
    path = Path(path)
    if path.exists():
        raise FileExistsError(f'{path} exists; evidence under docs/audit is immutable, add a new file instead')
    path.write_text(json.dumps(plain(data), ensure_ascii=False, indent=2) + '\n')


def source(path):
    resolved = Path(path).resolve()
    inside = resolved.is_relative_to(fa.ROOT)
    return {'path': str(resolved.relative_to(fa.ROOT)) if inside else str(resolved),
            'path_is_repo_relative': inside, 'sha256': fa.sha(resolved)}


def delta_e(a, b):
    return float(de(lab(np.asarray(a, float)), lab(np.asarray(b, float))))


def face_mm(face, xy_px):
    """Source pixel to face millimetre through the face's own source box (the lip transform
    of the addendum is this same formula with the lip's box)."""
    box = face['source_box_px']
    width, height = face['size_mm']
    return [(xy_px[0] - box[0]) * width / (box[2] - box[0]), (xy_px[1] - box[1]) * height / (box[3] - box[1])]


def render(page, ppi, clip=None):
    pix = page.get_pixmap(dpi=ppi, clip=clip, alpha=False, colorspace=fitz.csRGB)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3].copy()


def window_median(image, x_mm, y_mm, ppi):
    """Median sRGB of the FIELD_WINDOW_PX square centred on a face position; the window is
    clipped to the image and the rows/columns actually used are returned."""
    scale = ppi / 25.4
    column, row = int(round(x_mm * scale)), int(round(y_mm * scale))
    half = FIELD_WINDOW_PX // 2
    r0, r1 = max(0, row - half), min(image.shape[0], row + half + 1)
    c0, c1 = max(0, column - half), min(image.shape[1], column + half + 1)
    if r1 <= r0 or c1 <= c0:
        raise ValueError(f'sample ({x_mm:.2f}, {y_mm:.2f}) mm lies outside the rendered face')
    patch = image[r0:r1, c0:c1].reshape(-1, 3)
    return np.median(patch, axis=0), (r0, r1, c0, c1)


def pale_median(image):
    mask = (image[:, :, 0] > PALE_FLOOR[0]) & (image[:, :, 1] > PALE_FLOOR[1]) & (image[:, :, 2] > PALE_FLOOR[2])
    if not mask.any():
        return None, 0
    return np.median(image[mask], axis=0), int(mask.sum())


def fill_matches(fill, srgb, tolerance):
    if fill is None or len(fill) != 3:
        return False
    return all(abs(f * 255 - s) <= tolerance for f, s in zip(fill, srgb))


# ----------------------------------------------------------------------------- live text
def live_glyphs(page):
    """Visible live glyphs (fill text, opaque) with origin and font box in face mm (y down)."""
    glyphs = []
    for span in page.get_texttrace():
        if span['type'] != 0 or span['opacity'] < .99:
            continue
        for char in span['chars']:
            glyphs.append({'text': chr(char[0]), 'font': re.sub(r'^[A-Z]{6}\+', '', span['font']),
                           'origin_mm': [char[2][0] / MM, char[2][1] / MM],
                           'box_mm': [v / MM for v in char[3]]})
    return glyphs


def without_text(doc):
    """The same page with every live glyph removed and images and vector art kept."""
    bare = fitz.open(stream=doc.tobytes(), filetype='pdf')
    page = bare[0]
    page.add_redact_annot(page.rect, fill=False, cross_out=False)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                          text=fitz.PDF_REDACT_TEXT_REMOVE)
    if page.get_texttrace():
        raise ValueError('text removal left live glyphs; the ink difference would be incomplete')
    return bare


def ink_components(doc, ppi):
    """Connected components of the pixels that change when the live text is removed."""
    full = render(doc[0], ppi).astype(int)
    stripped = render(without_text(doc)[0], ppi).astype(int)
    if full.shape != stripped.shape:
        raise ValueError('text-stripped render differs in size from the full render')
    changed = np.max(np.abs(full - stripped), axis=2) > CHANGED_LEVELS
    count, _, stats, centroids = cv2.connectedComponentsWithStats(changed.astype(np.uint8), connectivity=8)
    scale = 25.4 / ppi
    rows = []
    for i in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[i])
        rows.append({'bbox_mm': [x * scale, y * scale, (x + w) * scale, (y + h) * scale],
                     'centroid_mm': [(float(centroids[i][0]) + .5) * scale, (float(centroids[i][1]) + .5) * scale],
                     'area_px': area})
    return rows, int(changed.sum())


def plan_anchors(graph):
    height = graph['height_mm']
    return [{'id': line['id'], 'origins_mm': [[run['x_mm'], height - run['baseline_z_mm']] for run in line['runs']]}
            for line in graph['lines']]


def measured_anchors(face):
    return [{'id': e['id'], 'origins_mm': [[(e['bbox_mm'][0] + e['bbox_mm'][2]) / 2, (e['bbox_mm'][1] + e['bbox_mm'][3]) / 2]]}
            for e in face['elements'] if e['copy']]


def assign(glyphs, components, anchors):
    """Each glyph goes to the nearest planned origin; each ink component to the glyph whose
    font box contains its centroid (nearest origin when several do)."""
    for glyph in glyphs:
        best = None
        for anchor in anchors:
            for ox, oy in anchor['origins_mm']:
                d = math.hypot(glyph['origin_mm'][0] - ox, glyph['origin_mm'][1] - oy)
                if best is None or d < best[0]:
                    best = (d, anchor['id'])
        glyph['line'] = None if best is None else best[1]
        glyph['anchor_distance_mm'] = None if best is None else best[0]
    for component in components:
        cx, cy = component['centroid_mm']
        inside = [g for g in glyphs if g['box_mm'][0] <= cx <= g['box_mm'][2] and g['box_mm'][1] <= cy <= g['box_mm'][3]]
        if not inside:
            component['line'] = None
            continue
        nearest = min(inside, key=lambda g: math.hypot(cx - g['origin_mm'][0], cy - g['origin_mm'][1]))
        component['line'] = nearest['line']


def copy_placement(element, glyphs, components):
    mine = [c for c in components if c['line'] == element['id']]
    chars = [g for g in glyphs if g['line'] == element['id']]
    x0, y0, x1, y1 = element['bbox_mm']
    row = {'id': element['id'], 'copy': element['copy'], 'kind': 'live text ink',
           'measured_bbox_mm': element['bbox_mm'], 'measured_baseline_y_mm': element['baseline_y_mm'],
           'glyphs': ''.join(g['text'] for g in chars), 'glyph_count': len(chars), 'ink_components': len(mine)}
    if not mine:
        row.update(present=False, passed=False, reason='no live-text ink was assigned to this planned line')
        return row
    a = min(c['bbox_mm'][0] for c in mine)
    b = min(c['bbox_mm'][1] for c in mine)
    c_ = max(c['bbox_mm'][2] for c in mine)
    d = max(c['bbox_mm'][3] for c in mine)
    dx = (a + c_) / 2 - (x0 + x1) / 2
    dy = (b + d) / 2 - (y0 + y1) / 2
    width_percent = 100 * ((c_ - a) / (x1 - x0) - 1)
    height_percent = 100 * ((d - b) / (y1 - y0) - 1)
    baseline = float(np.median([g['origin_mm'][1] for g in chars]))
    baseline_dy = None if element['baseline_y_mm'] is None else baseline - element['baseline_y_mm']
    offsets = [abs(dx), abs(dy)] + ([] if baseline_dy is None else [abs(baseline_dy)])
    row.update(present=True, emitted_bbox_mm=[a, b, c_, d], centre_dx_mm=dx, centre_dy_mm=dy,
               width_percent=width_percent, height_percent=height_percent,
               emitted_baseline_y_mm=baseline, baseline_dy_mm=baseline_dy,
               worst_offset_mm=max(offsets), worst_size_percent=max(abs(width_percent), abs(height_percent)),
               passed=max(offsets) <= PLACEMENT_OFFSET_MM
               and max(abs(width_percent), abs(height_percent)) <= PLACEMENT_SIZE_PERCENT)
    return row


def drawn_placement(element, drawings, margin_mm):
    """Logo and rule: union of the vector fills in the element's colour inside or near its box."""
    x0, y0, x1, y1 = element['bbox_mm']
    rects = []
    for drawing in drawings:
        if not fill_matches(drawing['fill'], element['colour_srgb'], FILL_TOLERANCE):
            continue
        r = [v / MM for v in drawing['rect']]
        if r[2] < x0 - margin_mm or r[0] > x1 + margin_mm or r[3] < y0 - margin_mm or r[1] > y1 + margin_mm:
            continue
        rects.append(r)
    row = {'id': element['id'], 'copy': None, 'kind': 'vector fill', 'measured_bbox_mm': element['bbox_mm'],
           'measured_baseline_y_mm': None, 'fills_found': len(rects), 'search_margin_mm': margin_mm}
    if not rects:
        row.update(present=False, passed=False,
                   reason=f'no vector fill within {FILL_TOLERANCE}/255 of the measured colour inside or near the measured box')
        return row
    a, b = min(r[0] for r in rects), min(r[1] for r in rects)
    c_, d = max(r[2] for r in rects), max(r[3] for r in rects)
    dx = (a + c_) / 2 - (x0 + x1) / 2
    dy = (b + d) / 2 - (y0 + y1) / 2
    width_percent = 100 * ((c_ - a) / (x1 - x0) - 1)
    height_percent = 100 * ((d - b) / (y1 - y0) - 1)
    row.update(present=True, emitted_bbox_mm=[a, b, c_, d], centre_dx_mm=dx, centre_dy_mm=dy,
               width_percent=width_percent, height_percent=height_percent, baseline_dy_mm=None,
               worst_offset_mm=max(abs(dx), abs(dy)), worst_size_percent=max(abs(width_percent), abs(height_percent)),
               passed=max(abs(dx), abs(dy)) <= PLACEMENT_OFFSET_MM
               and max(abs(width_percent), abs(height_percent)) <= PLACEMENT_SIZE_PERCENT)
    return row


def ink_colour(page, element):
    x0, y0, x1, y1 = element['bbox_mm']
    clip = fitz.Rect(x0 * MM, y0 * MM, x1 * MM, y1 * MM)
    judged, judged_count = pale_median(render(page, INK_COLOUR_PPI, clip))
    coarse, coarse_count = pale_median(render(page, RENDER_PPI, clip))
    row = {'id': element['id'], 'measured_srgb': element['colour_srgb'], 'measured_bbox_mm': element['bbox_mm'],
           'pale_class': 'R>200 and G>160 and B>110', 'judged_ppi': INK_COLOUR_PPI,
           'pale_pixels_at_judged_ppi': judged_count, 'pale_pixels_at_300ppi': coarse_count,
           'median_srgb_at_300ppi': None if coarse is None else coarse.tolist(),
           'delta_e_at_300ppi': None if coarse is None else delta_e(coarse, element['colour_srgb']),
           'tolerance': INK_DELTA_E}
    if judged is None:
        row.update(emitted_srgb=None, delta_e_2000=None, passed=False,
                   reason='no pale-class ink inside the measured box')
        return row
    value = delta_e(judged, element['colour_srgb'])
    row.update(emitted_srgb=judged.tolist(), delta_e_2000=value, passed=value <= INK_DELTA_E)
    return row


# ----------------------------------------------------------------------------- vector device
def flattened_loops(drawing):
    """Closed loops in face mm from a get_drawings() path; curves are flattened."""
    loops, current, previous = [], [], None

    def start(point):
        nonlocal current
        if current:
            loops.append(current)
        current = [[point.x / MM, point.y / MM]]

    for item in drawing['items']:
        kind = item[0]
        if kind == 'l':
            p, q = item[1], item[2]
            if previous is None or (p.x, p.y) != (previous.x, previous.y):
                start(p)
            current.append([q.x / MM, q.y / MM])
            previous = q
        elif kind == 'c':
            p, c1, c2, q = item[1], item[2], item[3], item[4]
            if previous is None or (p.x, p.y) != (previous.x, previous.y):
                start(p)
            for t in np.linspace(0, 1, 9)[1:]:
                x = (1 - t) ** 3 * p.x + 3 * (1 - t) ** 2 * t * c1.x + 3 * (1 - t) * t ** 2 * c2.x + t ** 3 * q.x
                y = (1 - t) ** 3 * p.y + 3 * (1 - t) ** 2 * t * c1.y + 3 * (1 - t) * t ** 2 * c2.y + t ** 3 * q.y
                current.append([x / MM, y / MM])
            previous = q
        elif kind == 're':
            r = item[1]
            start(fitz.Point(r.x0, r.y0))
            current += [[r.x1 / MM, r.y0 / MM], [r.x1 / MM, r.y1 / MM], [r.x0 / MM, r.y1 / MM], [r.x0 / MM, r.y0 / MM]]
            previous = None
        elif kind == 'qu':
            q = item[1]
            start(q.ul)
            current += [[q.ur.x / MM, q.ur.y / MM], [q.lr.x / MM, q.lr.y / MM], [q.ll.x / MM, q.ll.y / MM], [q.ul.x / MM, q.ul.y / MM]]
            previous = None
        else:
            raise ValueError(f'unknown drawing item {kind!r}')
    if current:
        loops.append(current)
    return loops


def polygon_edges(loops):
    segments = []
    for loop in loops:
        points = np.asarray(loop, float)
        if len(points) < 2:
            continue
        if not np.allclose(points[0], points[-1]):
            points = np.vstack([points, points[:1]])
        segments.append(np.hstack([points[:-1], points[1:]]))
    return np.vstack(segments) if segments else np.zeros((0, 4))


def merge_intervals(pairs):
    merged = []
    for a, b in sorted((min(p), max(p)) for p in pairs):
        if merged and a <= merged[-1][1] + 1e-9:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [[a, b] for a, b in merged if b - a > 1e-6]


def sections(edges, y, even_odd):
    """Inside intervals of a filled polygon set along the horizontal line at face y (mm)."""
    if len(edges) == 0:
        return []
    x0, y0, x1, y1 = edges.T
    lo, hi = np.minimum(y0, y1), np.maximum(y0, y1)
    hit = (y0 != y1) & (lo <= y) & (y < hi)
    if not hit.any():
        return []
    xs = x0[hit] + (y - y0[hit]) * (x1[hit] - x0[hit]) / (y1[hit] - y0[hit])
    direction = np.where(y1[hit] > y0[hit], 1, -1)
    order = np.argsort(xs)
    xs, direction = xs[order], direction[order]
    if even_odd:
        pairs = [[xs[i], xs[i + 1]] for i in range(0, len(xs) - 1, 2)]
    else:
        winding = np.cumsum(direction)
        pairs = [[xs[i], xs[i + 1]] for i in range(len(xs) - 1) if winding[i] != 0]
    return merge_intervals(pairs)


def device_polygons(drawings, srgb):
    return [(polygon_edges(flattened_loops(d)), bool(d['even_odd'])) for d in drawings
            if fill_matches(d['fill'], srgb, FILL_TOLERANCE)]


def role_sections(polygons, y):
    return merge_intervals([pair for edges, even_odd in polygons for pair in sections(edges, y, even_odd)])


def device_mask(polygons, shape, ppi):
    scale = 25.4 / ppi
    mask = np.zeros(shape[:2], bool)
    if not polygons:
        return mask
    for row in range(shape[0]):
        for a, b in role_sections(polygons, (row + .5) * scale):
            c0, c1 = max(0, int(math.floor(a / scale))), min(shape[1], int(math.ceil(b / scale)))
            if c1 > c0:
                mask[row, c0:c1] = True
    return mask


DEVICE_SCAN_STEP_MM = 1.0        # horizontals tested when asking whether the device crosses a face at all


def device_present(polygons, height_mm):
    return any(role_sections(polygons, y) for y in np.arange(DEVICE_SCAN_STEP_MM / 2, height_mm, DEVICE_SCAN_STEP_MM))


def gesture_check(cream, points_mm):
    rows = []
    for x, y in points_mm:
        segments = role_sections(cream, y)
        if not segments:
            rows.append({'measured_xy_mm': [x, y], 'segments_mm': [], 'passed': False,
                         'reason': 'no cream device fill on this horizontal'})
            continue
        containing = [s for s in segments if s[0] <= x <= s[1]]
        chosen = containing[0] if containing else min(segments, key=lambda s: min(abs(s[0] - x), abs(s[1] - x)))
        midpoint = (chosen[0] + chosen[1]) / 2
        # Diagnostic only: the midpoint of the whole cream extent on this horizontal (parallel
        # hairline included) shows whether a miss comes from the band or from the pose's centring.
        extent_midpoint = (segments[0][0] + segments[-1][1]) / 2
        rows.append({'measured_xy_mm': [x, y], 'segments_mm': segments, 'chosen_segment_mm': chosen,
                     'contains_measured_x': bool(containing), 'midpoint_x_mm': midpoint, 'dx_mm': midpoint - x,
                     'section_width_mm': chosen[1] - chosen[0],
                     'extent_mm': [segments[0][0], segments[-1][1]], 'extent_midpoint_x_mm': extent_midpoint,
                     'extent_dx_mm_diagnostic': extent_midpoint - x,
                     'passed': abs(midpoint - x) <= GESTURE_CENTRELINE_MM})
    offsets = [abs(r['dx_mm']) for r in rows if 'dx_mm' in r]
    extents = [abs(r['extent_dx_mm_diagnostic']) for r in rows if 'dx_mm' in r]
    return {'rows': rows, 'points': len(rows), 'missing': sum(1 for r in rows if 'dx_mm' not in r),
            'max_abs_dx_mm': max(offsets) if offsets else None, 'threshold_mm': GESTURE_CENTRELINE_MM,
            'max_abs_extent_dx_mm_diagnostic': max(extents) if extents else None,
            'judged_on': 'midpoint of the cream section containing or nearest the measured x; '
                         'the full-extent midpoint is a diagnostic, not a pass',
            'cream_fill_srgb': list(CREAM_SRGB), 'cream_drawings': len(cream),
            'passed': bool(rows) and all(r['passed'] for r in rows)}


# ----------------------------------------------------------------------------- field
def field_rows(image, face, samples, mask):
    rows = []
    for sample in samples:
        x, y = face_mm(face, sample['xy_px'])
        value, (r0, r1, c0, c1) = window_median(image, x, y, RENDER_PPI)
        rows.append({'source_xy_px': sample['xy_px'], 'face_xy_mm': [x, y], 'measured_srgb': sample['srgb'],
                     'emitted_srgb': value.tolist(), 'delta_e_2000': delta_e(value, sample['srgb']),
                     'window_px': [int(c1 - c0), int(r1 - r0)], 'on_device': bool(mask[r0:r1, c0:c1].any())})
    return rows


def judged(rows):
    for row in rows:
        row['passed'] = row['delta_e_2000'] <= FIELD_DELTA_E
    return rows


def field_pixels(context):
    """Field-class pixels of a measured face: the 300-PPI render outside the device, the live
    glyph boxes and the drawn marks, each widened by EXCLUSION_MM."""
    image = context['render']
    scale = RENDER_PPI / 25.4
    mask = context['device_mask'].copy()
    for glyph in context['glyphs']:
        x0, y0, x1, y1 = glyph['box_mm']
        mask[max(0, int(y0 * scale)):int(y1 * scale) + 1, max(0, int(x0 * scale)):int(x1 * scale) + 1] = True
    for drawing in context['drawings']:
        if drawing['fill'] is None or fill_matches(drawing['fill'], CREAM_SRGB, FILL_TOLERANCE) \
                or fill_matches(drawing['fill'], SHADOW_SRGB, FILL_TOLERANCE):
            continue
        r = drawing['rect']
        if r.width * r.height >= context['page'].rect.width * context['page'].rect.height * .5:
            continue  # a page-sized fill is the field itself, not a mark
        mask[max(0, int(r.y0 / MM * scale)):int(r.y1 / MM * scale) + 1, max(0, int(r.x0 / MM * scale)):int(r.x1 / MM * scale) + 1] = True
    kernel = np.ones((int(EXCLUSION_MM * scale) * 2 + 1,) * 2, np.uint8)
    mask = cv2.dilate(mask.astype(np.uint8), kernel).astype(bool)
    return image[~mask][::7]


def build_locus(contexts):
    pixels = np.vstack([field_pixels(c) for c in contexts])
    colours = np.unique((pixels >> 2) << 2, axis=0).astype(float)
    return {'tree': cKDTree(lab(colours)), 'lab': lab(colours), 'colours': colours,
            'faces': [c['surface_id'] for c in contexts], 'pixels': int(len(pixels)), 'distinct_colours': int(len(colours))}


def shared_field_check(context, locus):
    image = context['render']
    scale = RENDER_PPI / 25.4
    kernel = np.ones((int(EXCLUSION_MM * scale) * 2 + 1,) * 2, np.uint8)
    excluded = cv2.dilate(context['device_mask'].astype(np.uint8), kernel).astype(bool)
    width, height = context['page_mm']
    rows = []
    for y in np.arange(LOCUS_STEP_MM / 2, height, LOCUS_STEP_MM):
        for x in np.arange(LOCUS_STEP_MM / 2, width, LOCUS_STEP_MM):
            column, row = int(round(x * scale)), int(round(y * scale))
            if excluded[min(row, excluded.shape[0] - 1), min(column, excluded.shape[1] - 1)]:
                continue
            value, _ = window_median(image, x, y, RENDER_PPI)
            value_lab = lab(value)
            _, index = locus['tree'].query(value_lab, k=min(LOCUS_NEIGHBOURS, len(locus['lab'])))
            nearest = float(np.min(de(np.repeat(value_lab[None, :], len(np.atleast_1d(index)), 0), locus['lab'][np.atleast_1d(index)])))
            rows.append({'face_xy_mm': [float(x), float(y)], 'emitted_srgb': value.tolist(), 'min_delta_e_2000': nearest})
    values = [r['min_delta_e_2000'] for r in rows]
    return {'basis': 'every sampled field colour must lie within the field tolerance of a colour the shared field '
                     'realises on the measured faces of the same family (their emitted renders outside device, copy and marks)',
            'locus_faces': locus['faces'], 'locus_distinct_colours': locus['distinct_colours'], 'step_mm': LOCUS_STEP_MM,
            'samples': len(rows), 'failing': sum(1 for v in values if v > FIELD_DELTA_E),
            'max_delta_e_2000': max(values) if values else None, 'median_delta_e_2000': float(np.median(values)) if values else None,
            'tolerance': FIELD_DELTA_E, 'rows': rows, 'passed': bool(rows) and all(v <= FIELD_DELTA_E for v in values)}


# ----------------------------------------------------------------------------- one surface
def surface_context(pdf_path, surface_id):
    doc = fitz.open(pdf_path)
    if len(doc) != 1:
        raise ValueError(f'{pdf_path} has {len(doc)} pages; a surface master is one page')
    page = doc[0]
    drawings = page.get_drawings()
    cream = device_polygons(drawings, CREAM_SRGB)
    shadow = device_polygons(drawings, SHADOW_SRGB)
    image = render(page, RENDER_PPI)
    return {'surface_id': surface_id, 'pdf': Path(pdf_path), 'doc': doc, 'page': page,
            'page_mm': [page.rect.width / MM, page.rect.height / MM], 'render': image, 'glyphs': live_glyphs(page),
            'drawings': drawings, 'cream': cream, 'shadow': shadow,
            'device_mask': device_mask(cream + shadow, image.shape, RENDER_PPI),
            'raster_images': len(page.get_images(full=True))}


def inspect_surface(folder, face, *, addendum, pdf_name='artwork.pdf', png_name='artwork.png',
                    graph_name='design-graph.json', bindings=None, locus=None, context=None):
    """Measure one emitted surface against one measured face. Returns the record; nothing is written."""
    folder = Path(folder)
    surface_id = face['surface_id']
    measured = face['status'] != COMPOSED
    if context is None:
        context = surface_context(folder / pdf_name, surface_id)
    page, image = context['page'], context['render']
    width, height = face['size_mm']
    result = {'schema': 'day6_surface_fidelity/1', 'surface_id': surface_id, 'status': face['status'],
              'measured': measured, 'review_state': REVIEW_STATE, 'thresholds': THRESHOLDS,
              'sources': {'artwork_pdf': source(context['pdf'])},
              'page_mm': context['page_mm'],
              'page_size_matches_geometry': abs(context['page_mm'][0] - width) <= .05 and abs(context['page_mm'][1] - height) <= .05,
              'live_text_chars': len(context['glyphs']), 'raster_images': context['raster_images'],
              'drawings': len(context['drawings']), 'cream_drawings': len(context['cream']), 'shadow_drawings': len(context['shadow'])}
    if bindings is not None:
        recorded = [s for s in bindings['surfaces'] if s['surface_id'] == surface_id]
        result['bindings_pdf_sha256_matches'] = bool(recorded) and recorded[0]['pdf_sha256'] == result['sources']['artwork_pdf']['sha256']
    # The shipped PNG against a fresh 300-PPI render of the PDF.
    if png_name is not None:
        png_path = folder / png_name
        shipped = np.asarray(Image.open(png_path).convert('RGB'))
        result['sources']['artwork_png'] = source(png_path)
        result['png'] = {'size_px': [int(shipped.shape[1]), int(shipped.shape[0])], 'fresh_render_px': [int(image.shape[1]), int(image.shape[0])],
                         'expected_px_at_300ppi': [width / 25.4 * RENDER_PPI, height / 25.4 * RENDER_PPI],
                         'size_matches_300ppi_render': shipped.shape == image.shape,
                         'pixels_match_fresh_render': shipped.shape == image.shape and bool(np.array_equal(shipped, image))}
    # Grammar: §2.2 fields are parametric and the device is vector (no raster); composed faces add no copy;
    # the device crosses every front face.
    copy_expected = measured and any(e['copy'] for e in face['elements']) if 'elements' in face else False
    present = device_present(context['cream'], context['page_mm'][1])
    grammar = {'no_raster': context['raster_images'] == 0,
               'copy_matches_measurement': (len(context['glyphs']) > 0) == copy_expected,
               'copy_expected': copy_expected, 'device_present': present,
               'device_required': surface_id in FRONT_STRIP}
    grammar['passed'] = grammar['no_raster'] and grammar['copy_matches_measurement'] and (present or not grammar['device_required'])
    result['grammar'] = grammar
    categories = {'grammar': grammar['passed']}
    if measured:
        elements = face['elements'] if 'elements' in face else []
        copy_elements = [e for e in elements if e['copy']]
        if copy_elements:
            graph_path = None if graph_name is None else folder / graph_name
            if graph_path is not None:
                graph = json.loads(graph_path.read_text())
                result['sources']['design_graph'] = source(graph_path)
                anchors, assignment = plan_anchors(graph), 'design-graph run origins (nearest origin per glyph)'
            else:
                anchors, assignment = measured_anchors(face), 'measured element centres (no design graph shipped)'
            components, changed = ink_components(context['doc'], INK_BOX_PPI)
            glyphs = [dict(g) for g in context['glyphs']]
            assign(glyphs, components, anchors)
            rows = [copy_placement(e, glyphs, components) for e in copy_elements]
            rows += [drawn_placement(e, context['drawings'], 2.0) for e in elements if not e['copy']]
            distances = [g['anchor_distance_mm'] for g in glyphs if g['anchor_distance_mm'] is not None]
            result['placement'] = {'rows': rows, 'line_assignment': assignment, 'ink_box_ppi': INK_BOX_PPI,
                                   'text_ink_pixels': changed, 'ink_components': len(components),
                                   'unassigned_components': sum(1 for c in components if c['line'] is None),
                                   'max_glyph_to_anchor_mm': max(distances) if distances else None,
                                   'worst_offset_mm': max([r['worst_offset_mm'] for r in rows if r['present']], default=None),
                                   'worst_size_percent': max([r['worst_size_percent'] for r in rows if r['present']], default=None),
                                   'passed': all(r['passed'] for r in rows)}
            ink = [ink_colour(page, e) for e in elements]
            values = [r['delta_e_2000'] for r in ink if r['delta_e_2000'] is not None]
            result['ink_colour'] = {'rows': ink, 'max_delta_e_2000': max(values) if values else None,
                                    'missing': sum(1 for r in ink if r['delta_e_2000'] is None), 'passed': all(r['passed'] for r in ink)}
            categories['placement'] = result['placement']['passed']
            categories['ink_colour'] = result['ink_colour']['passed']
        if face['field_samples']:
            samples = face['field_samples']
            field = {'tolerance': FIELD_DELTA_E, 'window_px': FIELD_WINDOW_PX, 'render_ppi': RENDER_PPI}
            if surface_id == 'riser.3.front':
                if addendum is None or 'y1160' not in addendum['riser3_deep_shadow_samples_status']:
                    raise ValueError('riser.3 shadow row must be named by the addendum before its samples are split')
                lit = [s for s in samples if s['xy_px'][1] != RISER3_SHADOW_ROW_PX]
                shadow = [s for s in samples if s['xy_px'][1] == RISER3_SHADOW_ROW_PX]
                field['rows'] = judged(field_rows(image, face, lit, context['device_mask']))
                field['diagnostics'] = {
                    'basis': 'reported, not judged: photographed shadow (y1160) and held-out samples per the addendum',
                    'shadow_rows': field_rows(image, face, shadow, context['device_mask']),
                    'held_out_rows': field_rows(image, face, addendum['riser3_held_out'], context['device_mask'])}
            else:
                field['rows'] = judged(field_rows(image, face, samples, context['device_mask']))
            values = [r['delta_e_2000'] for r in field['rows']]
            field.update(total=len(values), failing=sum(1 for v in values if v > FIELD_DELTA_E),
                         max_delta_e_2000=max(values) if values else None, passed=bool(values) and all(v <= FIELD_DELTA_E for v in values))
            result['field'] = field
            categories['field'] = field['passed']
        points = None
        if 'gesture_centreline_mm' in face:
            points, basis = face['gesture_centreline_mm'], 'gesture_centreline_mm of the measured face'
        elif 'gesture_centreline_px' in face:
            points, basis = [face_mm(face, p) for p in face['gesture_centreline_px']], \
                'gesture_centreline_px through the face transform (addendum lip_transform formula)'
        if points is not None:
            gesture = gesture_check(context['cream'], points)
            gesture['basis'] = basis
            result['gesture'] = gesture
            categories['gesture'] = gesture['passed']
        measured_categories = [categories[k] for k in ('placement', 'ink_colour', 'field', 'gesture') if k in categories]
        result['measured_fidelity_passed'] = bool(measured_categories) and all(measured_categories)
        result['claim'] = 'measured against the D1 measurement; categories judged: ' + ', '.join(
            k for k in ('placement', 'ink_colour', 'field', 'gesture') if k in categories)
    else:
        if locus is None:
            raise ValueError('a composed face needs the shared-field locus of its family')
        result['shared_field_locus'] = shared_field_check(context, locus)
        categories['shared_field_locus'] = result['shared_field_locus']['passed']
        result['measured_fidelity_passed'] = None
        result['claim'] = COMPOSED + ': no placement or colour pass claim; grammar, shared field and seam continuity only'
    result['categories'] = categories
    result['sources']['measurement'] = source(MEASUREMENT)
    result['sources']['addendum'] = source(ADDENDUM)
    return result


# ----------------------------------------------------------------------------- seams
def seam_check(upper, lower):
    """Continuity across a front seam: cream and shadow sections at the shared edge must agree
    within SEAM_MM, the field rows 0.5 mm either side within the field tolerance."""
    height = upper['page_mm'][1]
    device = {}
    for role in ('cream', 'shadow'):
        above = role_sections(upper[role], height - 1e-6)
        below = role_sections(lower[role], 1e-6)
        matches, worst = [], None
        for a in above:
            if not below:
                break
            b = min(below, key=lambda s: abs((s[0] + s[1]) / 2 - (a[0] + a[1]) / 2))
            delta = max(abs(a[0] - b[0]), abs(a[1] - b[1]))
            worst = delta if worst is None else max(worst, delta)
            matches.append({'upper_mm': a, 'lower_mm': b, 'max_delta_mm': delta})
        required = role == 'cream'
        if not above and not below:
            passed = not required
            note = 'absent on both faces at this seam' + (' (cream is required: the device crosses every front face)' if required else '')
        elif len(above) != len(below):
            passed, note = False, f'{len(above)} section(s) above, {len(below)} below'
        else:
            passed, note = worst <= SEAM_MM, 'matched by nearest midpoint'
        device[role] = {'upper_sections_mm': above, 'lower_sections_mm': below, 'matches': matches,
                        'max_delta_mm': worst, 'required': required, 'note': note, 'passed': passed}
    occupied = [s for role in ('cream', 'shadow') for s in device[role]['upper_sections_mm'] + device[role]['lower_sections_mm']]
    rows = []
    for x in np.arange(9.0, upper['page_mm'][0], 18.0):
        if any(s[0] - 1 <= x <= s[1] + 1 for s in occupied):
            continue
        a, _ = window_median(upper['render'], x, height - .5, RENDER_PPI)
        b, _ = window_median(lower['render'], x, .5, RENDER_PPI)
        rows.append({'x_mm': float(x), 'upper_srgb': a.tolist(), 'lower_srgb': b.tolist(), 'delta_e_2000': delta_e(a, b)})
    values = [r['delta_e_2000'] for r in rows]
    field = {'rows': rows, 'max_delta_e_2000': max(values) if values else None, 'tolerance': FIELD_DELTA_E,
             'passed': bool(values) and all(v <= FIELD_DELTA_E for v in values)}
    return {'seam': f"{upper['surface_id']}|{lower['surface_id']}", 'edge_mm': height,
            'sources': {'upper_pdf': source(upper['pdf']), 'lower_pdf': source(lower['pdf'])},
            'device': device, 'field': field, 'threshold_device_mm': SEAM_MM,
            'passed': device['cream']['passed'] and device['shadow']['passed'] and field['passed']}


def continuity_by_surface(seams):
    """Each front face owns every seam it takes part in; sides have none."""
    owned = {}
    for seam in seams:
        for surface_id in seam['seam'].split('|'):
            owned.setdefault(surface_id, []).append(seam)
    return owned


# ----------------------------------------------------------------------------- families
def family(folder, faces, *, addendum, names, bindings):
    """Inspect every face of one emitted family and its front seams. names(surface_id) gives
    (pdf_name, png_name, graph_name) inside folder(surface_id)."""
    contexts, results = {}, {}
    for face in faces:
        pdf_name, _, _ = names(face['surface_id'])
        contexts[face['surface_id']] = surface_context(Path(folder(face['surface_id'])) / pdf_name, face['surface_id'])
    measured_faces = [f for f in faces if f['status'] != COMPOSED]
    locus = build_locus([contexts[f['surface_id']] for f in measured_faces])
    for face in faces:
        pdf_name, png_name, graph_name = names(face['surface_id'])
        results[face['surface_id']] = inspect_surface(folder(face['surface_id']), face, addendum=addendum, pdf_name=pdf_name,
                                                      png_name=png_name, graph_name=graph_name, bindings=bindings,
                                                      locus=locus, context=contexts[face['surface_id']])
    strip = [s for s in FRONT_STRIP if s in contexts]
    seams = [seam_check(contexts[a], contexts[b]) for a, b in zip(strip, strip[1:])]
    for surface_id, owned in continuity_by_surface(seams).items():
        results[surface_id]['seams'] = owned
        results[surface_id]['categories']['continuity'] = all(s['passed'] for s in owned)
    for result in results.values():
        result['all_categories_passed'] = all(v for v in result['categories'].values())
    return results, seams, {'faces': locus['faces'], 'pixels': locus['pixels'], 'distinct_colours': locus['distinct_colours']}


def summary_row(result):
    def verdict(key):
        if key not in result['categories']:
            return 'n/a'
        return 'PASS' if result['categories'][key] else 'FAIL'
    row = {'surface_id': result['surface_id'], 'status': result['status'], 'measured': result['measured'],
           'placement': verdict('placement'),
           'placement_worst_offset_mm': result['placement']['worst_offset_mm'] if 'placement' in result else None,
           'placement_worst_size_percent': result['placement']['worst_size_percent'] if 'placement' in result else None,
           'placement_missing': sum(1 for r in result['placement']['rows'] if not r['present']) if 'placement' in result else None,
           'ink_colour': verdict('ink_colour'),
           'ink_delta_e_max': result['ink_colour']['max_delta_e_2000'] if 'ink_colour' in result else None,
           'field': verdict('field'),
           'field_delta_e_max': result['field']['max_delta_e_2000'] if 'field' in result else None,
           'field_failing': result['field']['failing'] if 'field' in result else None,
           'field_total': result['field']['total'] if 'field' in result else None,
           'gesture': verdict('gesture'),
           'gesture_max_mm': result['gesture']['max_abs_dx_mm'] if 'gesture' in result else None,
           'gesture_missing': result['gesture']['missing'] if 'gesture' in result else None,
           'grammar': verdict('grammar'), 'shared_field_locus': verdict('shared_field_locus'), 'continuity': verdict('continuity'),
           'measured_fidelity_passed': result['measured_fidelity_passed'],
           'all_categories_passed': result['all_categories_passed'], 'review_state': REVIEW_STATE}
    return row


def run(destination=SURFACES):
    """Measure the seven emitted D1 surfaces; write <id>/fidelity-check.json and fidelity-summary.json."""
    destination = Path(destination)
    measurement = json.loads(MEASUREMENT.read_text())
    addendum = json.loads(ADDENDUM.read_text())
    bindings = json.loads((destination / 'surface-bindings.json').read_text())
    faces = measurement['faces']
    targets = [destination / f['surface_id'] / 'fidelity-check.json' for f in faces] + [destination / 'fidelity-summary.json']
    for target in targets:
        if target.exists():
            raise FileExistsError(f'{target} exists; existing Day 6 evidence is immutable')
    results, seams, locus = family(lambda s: destination / s, faces, addendum=addendum,
                                   names=lambda s: ('artwork.pdf', 'artwork.png', 'design-graph.json'), bindings=bindings)
    for face in faces:
        write(destination / face['surface_id'] / 'fidelity-check.json', results[face['surface_id']])
    rows = [summary_row(results[f['surface_id']]) for f in faces]
    summary = {'schema': 'day6_surface_fidelity_summary/1', 'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'instrument': source(Path(__file__)), 'thresholds': THRESHOLDS,
               'sources': {'measurement': source(MEASUREMENT), 'addendum': source(ADDENDUM),
                           'surface_bindings': source(destination / 'surface-bindings.json'),
                           'surfaces': {s: {k: v for k, v in results[s]['sources'].items() if k.startswith('artwork') or k == 'design_graph'} for s in results}},
               'rows': rows, 'seams': seams, 'shared_field_locus': locus,
               'measured_faces_passed': all(r['measured_fidelity_passed'] for r in rows if r['measured']),
               'family_all_categories_passed': all(r['all_categories_passed'] for r in rows),
               'review_state': REVIEW_STATE,
               'reading': 'measured faces carry pass/fail per owner §2.2 category; composed faces are "composed, not measured" '
                          'and carry grammar, shared-field and seam continuity only; FAILs are reported, never rescued'}
    write(destination / 'fidelity-summary.json', summary)
    return summary


def negative_control(destination=SURFACES, day4=DAY4):
    """The same instrument on the Day 4 flat surfaces against the same D1 measurement. Every Day 4
    surface must fail at least one category and header.front must fail placement or colour."""
    destination, day4 = Path(destination), Path(day4)
    target = destination / 'negative-control-day4.json'
    if target.exists():
        raise FileExistsError(f'{target} exists; existing Day 6 evidence is immutable')
    measurement = json.loads(MEASUREMENT.read_text())
    addendum = json.loads(ADDENDUM.read_text())
    faces = measurement['faces']
    results, seams, locus = family(lambda s: day4, faces, addendum=addendum,
                                   names=lambda s: (f'{s}.pdf', f'{s}.png', None), bindings=None)
    rows = []
    for face in faces:
        result = results[face['surface_id']]
        failing = [k for k, v in result['categories'].items() if not v]
        row = summary_row(result)
        row['failing_categories'] = failing
        rows.append(row)
        if not failing:
            raise ValueError(f"instrument broken: Day 4 {face['surface_id']} passed every category against D1")
    header = results['header.front']
    header_fails = not header['categories']['placement'] or not header['categories']['ink_colour']
    if not header_fails:
        raise ValueError('instrument broken: Day 4 header.front failed neither placement nor colour against D1')
    report = {'schema': 'day6_surface_fidelity_negative_control/1', 'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'instrument': source(Path(__file__)), 'thresholds': THRESHOLDS,
              'control': 'Day 4 flat surfaces (docs/audit/day-4/stand-family/surfaces) measured against the D1 measurement',
              'sources': {'measurement': source(MEASUREMENT), 'addendum': source(ADDENDUM),
                          'day4_surface_bindings': source(day4 / 'surface-bindings.json'),
                          'surfaces': {s: {k: v for k, v in results[s]['sources'].items() if k.startswith('artwork')} for s in results}},
              'rows': rows, 'seams': seams, 'shared_field_locus': locus, 'surfaces': results,
              'every_surface_fails': True, 'header_fails_placement_or_colour': header_fails, 'instrument_distinguishes': True}
    write(target, report)
    return report
