"""Source-measured second repair: complete metal, edge texture and physical proofs.

No provider, worker, native application or live-round entry point is called here.
Every output belongs to the caller's new revision directory.
"""
from copy import deepcopy
import hashlib
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import binary_fill_holes, distance_transform_edt
from shapely.geometry import LineString, box as geometry_box
from shapely.ops import unary_union

from . import round_files_art as art


def source_metal(rgb, seed, protected, *, distinguish_material=False):
    """The inspection locates a motif; connected source pixels define its ends."""
    if distinguish_material:
        return _source_metal_by_material(rgb, seed, protected)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    core = ((hsv[..., 0] >= 10) & (hsv[..., 0] <= 40) &
            (hsv[..., 1] >= 30) & (hsv[..., 2] >= 155) &
            (rgb[..., 1] >= .73*rgb[..., 0]) & ~protected)
    radius = max(1., float(np.percentile(distance_transform_edt(core)[core], 75))) if core.any() else 1.
    near = distance_transform_edt(~core) <= 2*radius
    pale = ((hsv[..., 1] < 65) & (hsv[..., 2] >= 190) &
            (rgb[..., 0] >= rgb[..., 2]+1.) & (rgb[..., 1] >= rgb[..., 2]+1.))
    candidate = (core | (near & pale)) & ~protected
    number, labels, stats, _ = cv2.connectedComponentsWithStats(candidate.astype(np.uint8), 8)
    selected = np.zeros(candidate.shape, dtype=bool)
    components = []
    for label in range(1, number):
        pixels = labels == label
        intersects = bool(np.any(pixels & seed))
        area = int(stats[label, cv2.CC_STAT_AREA])
        keep = intersects and area >= max(8, int(radius*radius*2))
        if keep:
            selected |= pixels
        components.append({'source_pixels': area, 'intersects_inspection': intersects, 'selected': keep})
    return selected, {'method': 'Connected observed gold and pale metal highlights; inspection boxes seed components and never crop their ends.',
        'highlight_neighbourhood_source_px': 2*radius, 'components': components,
        'source_core_pixels': int(core.sum()), 'selected_source_pixels': int(selected.sum()),
        'outside_seed_pixels': int((selected & ~seed).sum())}


def _mask_evidence(mask):
    """Lossless row runs keep rejected source pixels reviewable without a fit."""
    runs = []
    for y, row in enumerate(mask):
        edges = np.flatnonzero(np.diff(np.pad(row.astype(np.int8), 1)))
        runs.extend([y, int(start), int(end)] for start, end in zip(edges[::2], edges[1::2]))
    return {'size_px': [mask.shape[1], mask.shape[0]], 'pixels': int(mask.sum()),
            'sha256_bool_bytes': hashlib.sha256(mask.tobytes()).hexdigest(),
            'row_runs_y_x0_x1_exclusive': runs}


def _source_metal_by_material(rgb, seed, protected):
    """Separate yellow metal from warm substrate reflections before line fitting.

    Hue 18 in OpenCV's half-degree units is a yellow-biased colour: the
    green-minus-blue channel difference exceeds red-minus-green. Warm pink
    acrylic reflections can meet the legacy hue-10 threshold, even while
    physically connected to the motif. They cannot become metal merely by
    that connection. Pale yellow is allowed when it still has measurable
    chroma; neutral white alone is insufficient evidence of gold.
    """
    legacy_selected, legacy_record = source_metal(rgb, seed, protected)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    yellow_hue = (hsv[..., 0] >= 18) & (hsv[..., 0] <= 40)
    reliable = yellow_hue & (((hsv[..., 1] >= 30) & (hsv[..., 2] >= 155)) |
                             ((hsv[..., 1] >= 12) & (hsv[..., 2] >= 230))) & ~protected
    if not reliable.any():
        raise ValueError('No reliable yellow metal core in the source; material segmentation needs review')
    # A separate gold object must not widen this motif's shadow allowance.
    # Assign each source pixel to its nearest reliable core component, then
    # use only that component's measured thickness for its local support.
    core_count, core_labels, core_stats, _ = cv2.connectedComponentsWithStats(reliable.astype(np.uint8), 8)
    core_depth = distance_transform_edt(reliable)
    neighbourhoods = np.zeros(core_count, dtype=float)
    core_components = []
    for label in range(1, core_count):
        pixels = core_labels == label
        radius = float(np.percentile(core_depth[pixels], 75))
        neighbourhoods[label] = max(1., 2*radius)
        core_components.append({'label': label, 'source_pixels': int(pixels.sum()),
            'box_px': [int(core_stats[label, cv2.CC_STAT_LEFT]), int(core_stats[label, cv2.CC_STAT_TOP]),
                       int(core_stats[label, cv2.CC_STAT_LEFT]+core_stats[label, cv2.CC_STAT_WIDTH]),
                       int(core_stats[label, cv2.CC_STAT_TOP]+core_stats[label, cv2.CC_STAT_HEIGHT])],
            'radius_source_px': radius, 'highlight_neighbourhood_source_px': float(neighbourhoods[label])})
    distance, nearest = distance_transform_edt(~reliable, return_indices=True)
    nearest_labels = core_labels[nearest[0], nearest[1]]
    local_support = distance <= neighbourhoods[nearest_labels]
    warm_shadow = ((hsv[..., 0] >= 10) & (hsv[..., 0] <= 40) &
                   (hsv[..., 1] >= 30) & (hsv[..., 2] >= 155) &
                   (rgb[..., 1] >= .73*rgb[..., 0]))
    pale_highlight = ((hsv[..., 1] < 65) & (hsv[..., 2] >= 190) &
                      (rgb[..., 0] >= rgb[..., 2]+1.) & (rgb[..., 1] >= rgb[..., 2]+1.))
    candidate = (reliable | warm_shadow | pale_highlight) & local_support & ~protected
    number, labels, stats, _ = cv2.connectedComponentsWithStats(candidate.astype(np.uint8), 8)
    selected = np.zeros(candidate.shape, dtype=bool)
    components = []
    for label in range(1, number):
        pixels = labels == label
        intersects = bool(np.any(pixels & seed))
        has_core = bool(np.any(pixels & reliable))
        keep = intersects and has_core
        if keep:
            selected |= pixels
        components.append({'source_pixels': int(stats[label, cv2.CC_STAT_AREA]),
            'box_px': [int(stats[label, cv2.CC_STAT_LEFT]), int(stats[label, cv2.CC_STAT_TOP]),
                       int(stats[label, cv2.CC_STAT_LEFT]+stats[label, cv2.CC_STAT_WIDTH]),
                       int(stats[label, cv2.CC_STAT_TOP]+stats[label, cv2.CC_STAT_HEIGHT])],
            'intersects_inspection': intersects, 'contains_reliable_core': has_core, 'selected': keep})
    if not selected.any():
        raise ValueError('No inspected motif has reliable yellow metal support; material segmentation needs review')
    rejected = legacy_selected & ~selected
    return selected, {'method': 'Source-only yellow-metal evidence with bounded local shadow/highlight support; warm connected substrate reflections do not propagate the motif. No fitted lines or coverage feedback.',
        'schema': 'source_material_metal/1',
        'colour_rule': {'hue_half_degrees': [18, 40], 'ordinary_min_saturation': 30,
                        'ordinary_min_value': 155, 'pale_min_saturation': 12, 'pale_min_value': 230},
        'support_method': 'Each pixel uses only the thickness of its nearest connected reliable-core component; unrelated metal cannot enlarge another component\'s support.',
        'core_components': core_components,
        'components': components, 'source_core_pixels': int(reliable.sum()),
        'selected_source_pixels': int(selected.sum()), 'outside_seed_pixels': int((selected & ~seed).sum()),
        'legacy_source_segmentation': legacy_record,
        'legacy_candidate_mask': _mask_evidence(legacy_selected),
        'rejected_legacy_mask': _mask_evidence(rejected),
        'added_source_pale_mask': _mask_evidence(selected & ~legacy_selected),
        'reliable_core_mask': _mask_evidence(reliable),
        'rejection_reason': 'The source pixel lacks local, independently coloured yellow-metal support; a connected warm reflection alone is insufficient.'}


def skeleton(mask):
    """Zhang–Suen thinning, retaining the observed connected centre lines."""
    work = np.pad(mask.astype(np.uint8), 1)
    while True:
        changed = 0
        for phase in (0, 1):
            p = [work[:-2, 1:-1], work[:-2, 2:], work[1:-1, 2:], work[2:, 2:],
                 work[2:, 1:-1], work[2:, :-2], work[1:-1, :-2], work[:-2, :-2]]
            neighbours = sum(p)
            transitions = sum((p[i] == 0) & (p[(i+1) % 8] == 1) for i in range(8))
            condition = ((p[0]*p[2]*p[4] == 0) & (p[2]*p[4]*p[6] == 0) if phase == 0 else
                         (p[0]*p[2]*p[6] == 0) & (p[0]*p[4]*p[6] == 0))
            remove = ((work[1:-1, 1:-1] == 1) & (neighbours >= 2) & (neighbours <= 6) &
                      (transitions == 1) & condition)
            changed += int(remove.sum())
            work[1:-1, 1:-1][remove] = 0
        if not changed:
            return work[1:-1, 1:-1].astype(bool)


def trace_strokes(mask, path):
    centre = skeleton(mask)
    pixels = {tuple(point) for point in np.argwhere(centre)}
    adjacent = {p: sorted(q for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                          if (dy or dx) and (q := (p[0]+dy, p[1]+dx)) in pixels) for p in pixels}
    visited, paths = set(), []
    starts = sorted(pixels, key=lambda p: (len(adjacent[p]) == 2, p))
    widths = distance_transform_edt(mask)*2
    for start in starts:
        for next_pixel in adjacent[start]:
            edge = frozenset((start, next_pixel))
            if edge in visited:
                continue
            visited.add(edge); chain = [start, next_pixel]
            while len(adjacent[chain[-1]]) == 2:
                candidates = [p for p in adjacent[chain[-1]] if p != chain[-2]]
                following = candidates[0]
                edge = frozenset((chain[-1], following))
                if edge in visited:
                    break
                visited.add(edge); chain.append(following)
            length = sum(math.dist(a, b) for a, b in zip(chain, chain[1:]))
            if length < 2:
                continue
            points = np.asarray([[x+.5, y+.5] for y, x in chain], dtype=np.float32)
            simple = cv2.approxPolyDP(points.reshape(-1, 1, 2), .35, False)[:, 0]
            width = float(np.median([widths[y, x] for y, x in chain]))
            paths.append({'points_source_px': simple.tolist(), 'width_source_px': width,
                          'observed_centreline_length_source_px': length})
    h, w = mask.shape
    polygons = []
    for row in paths:
        polygons.append(LineString(row['points_source_px']).buffer(row['width_source_px']/2, resolution=16,
                                                                  cap_style=1, join_style=1))
    ink = unary_union(polygons).intersection(geometry_box(0, 0, w, h))
    parts = list(ink.geoms) if ink.geom_type == 'MultiPolygon' else [ink]
    commands = []
    for polygon in parts:
        if polygon.is_empty:
            continue
        for ring in [polygon.exterior, *polygon.interiors]:
            commands.append('M'+' L'.join(f'{x:.4f},{y:.4f}' for x, y in ring.coords)+' Z')
    Path(path).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><path fill="#D5AF59" fill-rule="evenodd" d="'+ ' '.join(commands)+'"/></svg>')
    return {'method': 'Observed connected skeleton, simplified within 0.35 source px; round strokes use measured source-metal width.',
            'paths': paths, 'native_geometry': 'Round source strokes expanded to closed filled contours before any anisotropic placement.',
            'skeleton_source_pixels': int(centre.sum()), 'saved_vector': art.trace_measurement(path, mask)}


def observed_panes(rgb, seed, forbidden):
    """Learn pane colours from this source, excluding observed metal and copy."""
    lab = art.metrics.srgb_to_lab(rgb)
    pool = seed & ~forbidden & ~art.gold_mask(rgb)
    if not pool.any():
        raise ValueError('No non-metal source pixels support a printed-pane colour measurement')
    samples = lab[pool]
    bins, inverse, counts = np.unique(np.floor(samples/12).astype(int), axis=0, return_inverse=True, return_counts=True)
    order = np.argsort(counts)[::-1]
    prototypes = []
    for index in order[:5]:
        if counts[index] < .025*len(samples):
            continue
        prototypes.append(np.median(samples[inverse == index], axis=0))
    if not prototypes:
        raise ValueError('Observed pane colours do not form a stable source cluster')
    distance = np.minimum.reduce([np.linalg.norm(lab-prototype, axis=2) for prototype in prototypes])
    return distance <= 18., {'source_pane_lab': [row.tolist() for row in prototypes],
                             'maximum_source_colour_distance_lab': 18., 'source_sample_pixels': int(pool.sum())}


def refine_header(rgb, inspection):
    panel = inspection['panels']['stand_header']; old = deepcopy(panel)
    x0, y0, x1, y1 = panel['crop_px']
    search = rgb[:y1, x0:x1]
    seed = np.zeros(search.shape[:2], bool)
    seed[y0:y1] = art.silhouette((x1-x0, y1-y0), panel['print_polygon_px'], panel['crop_px'])
    words = np.zeros(search.shape[:2], bool)
    words[y0:y1] = art.letter_mask(search[y0:y1], panel, panel['crop_px'])
    try:
        pane, colour_record = observed_panes(search, seed, words)
    except ValueError as exc:
        return {'status': 'unresolved', 'reason': str(exc), 'old_crop_px': old['crop_px']}
    core = art.gold_mask(search)
    radius = max(1, round(float(np.percentile(distance_transform_edt(core)[core], 75)))) if core.any() else 1
    joined = cv2.morphologyEx(pane.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((4*radius+1, 4*radius+1), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(joined, 8)
    candidates = [(int(((labels == i) & seed).sum()), i) for i in range(1, count)]
    if not candidates or max(candidates)[0] < .35*int(seed.sum()):
        return {'status': 'unresolved', 'reason': 'No observed printed-pane component supports a larger source header.', 'old_crop_px': old['crop_px']}
    label = max(candidates)[1]
    mask = binary_fill_holes(labels == label)
    ys, xs = np.where(mask)
    new_top = int(ys.min())
    if new_top > y0:
        new_top = y0
    mask = mask[new_top:y1]
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour = max(contours, key=cv2.contourArea)
    points = cv2.approxPolyDP(contour, .75, True)[:, 0]
    if len(points) > 256:
        return {'status': 'unresolved', 'reason': 'Observed pane boundary is too ambiguous to express as a stable source silhouette.', 'old_crop_px': old['crop_px']}
    panel['crop_px'] = [x0, new_top, x1, y1]
    panel['print_polygon_px'] = [[int(x)+x0, int(y)+new_top] for x, y in points]
    return {'status': 'measured', 'old_crop_px': old['crop_px'], 'new_crop_px': list(panel['crop_px']),
            'old_polygon_px': old['print_polygon_px'], 'new_polygon_px': deepcopy(panel['print_polygon_px']),
            'added_source_rows': y0-new_top, 'absolute_type_and_logo_boxes_unchanged': panel.get('text', []) == old.get('text', []) and panel.get('marks', []) == old.get('marks', []),
            'source_colour_measurement': colour_record,
            'method': 'Connected observed pane pixels above the original seed, bounded by existing header width and bottle baseline; yellow physical trim is not a pane donor.'}


def reflected_edge_source(rgb, inside, forbidden, metal=None):
    """Outside-only reflected source coordinates; no constant edge extrusion."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    pane, colour_record = observed_panes(rgb, inside, forbidden)
    measured_panes = inside & pane & ~forbidden
    if not measured_panes.any():
        raise ValueError('No observed pane colour remains for header edge extension')
    light_floor = float(np.percentile(hsv[..., 2][measured_panes], 20))
    pane &= hsv[..., 2] >= light_floor
    observed = pane if metal is None else pane | metal
    donor = inside & observed & ~forbidden
    if not donor.any():
        raise ValueError('No clean observed pane pixels support square header extension')
    boundary = distance_transform_edt(~inside, return_distances=False, return_indices=True)
    yy, xx = np.indices(inside.shape)
    sy, sx = 2*boundary[0]-yy, 2*boundary[1]-xx
    # A reflected point beyond the crop reflects again, never clamps a long
    # outside strip onto one pixel column or samples beyond the picked source.
    def reflect(values, length):
        if length == 1:
            return np.zeros(values.shape, dtype=int)
        value = np.mod(values, 2*(length-1))
        return np.where(value < length, value, 2*(length-1)-value)
    sy, sx = reflect(sy, rgb.shape[0]), reflect(sx, rgb.shape[1])
    clean_index = distance_transform_edt(~donor, return_distances=False, return_indices=True)
    sy, sx = clean_index[0, sy, sx], clean_index[1, sy, sx]
    out = rgb.copy(); out[~inside] = rgb[sy[~inside], sx[~inside]]
    return out, {'source_y': sy, 'source_x': sx, 'donors': donor,
                 'record': {'method': 'Reflect actual interior source coordinates across the observed edge; exclude lettering, gold rim and dark trim shadows from pane donors.',
                            'outside_only': True, 'donor_source_pixels': int(donor.sum()),
                            'observed_pane_value_floor': light_floor,
                            'source_colour_measurement': colour_record,
                            'unique_extension_donor_pixels': int(len(set(zip(sy[~inside].tolist(), sx[~inside].tolist())))),
                            'inside_pixels_unchanged': bool(np.array_equal(out[inside], rgb[inside]))}}


def physical_clean(rgb, words, metal):
    # Source shading and glass reflections survive unchanged outside extraction.
    radius = max(1, round(float(np.percentile(distance_transform_edt(metal)[metal], 75)))) if metal.any() else 1
    removal = words | (cv2.dilate(metal.astype(np.uint8), np.ones((2*radius+1, 2*radius+1), np.uint8)) > 0)
    return art.nearest_source_copy(rgb, removal), removal


def material_record(image, removal, path, source_box):
    Image.fromarray(image).save(path)
    mask = Path(path).with_name(Path(path).stem+'-extraction-mask.png')
    Image.fromarray(removal.astype(np.uint8)*255).save(mask)
    return {'path': str(Path(path).resolve()), 'sha256': art.sha(path), 'source_box_px': list(source_box),
            'extraction_mask': str(mask.resolve()), 'extraction_mask_sha256': art.sha(mask),
            'extraction_pixels': int(removal.sum()), 'method': 'Original physical source pixels minus separately extracted lettering/foil; no colour fill or recolouring.',
            'scope': 'Drawing-only physical material, never a downloadable print master.'}


def _mapped_words(panel, size):
    crop = panel['crop_px']; result = np.zeros((size[1], size[0]), bool)
    for row in panel.get('text', []) + panel.get('marks', []):
        box = art._normal_box(row['box_px'], crop)
        a, b, c, d = [round(value*size[index % 2]) for index, value in enumerate(box)]
        result[max(0, b-2):min(size[1], d+2), max(0, a-2):min(size[0], c+2)] = True
    return result


def _observed_word_spans(body):
    """Central pixels seed copy rows; full source glyphs define their extent."""
    gold = art.gold_mask(body)
    h, w = gold.shape
    central = gold[:, w//5:max(w//5+1, 4*w//5)]
    rows = np.flatnonzero((central.sum(axis=1) >= max(2, .03*w)) & (np.arange(h) >= .62*h))
    mask = np.zeros((h, w), bool)
    boxes = []
    if not len(rows):
        return mask, boxes
    number, labels, stats, _ = cv2.connectedComponentsWithStats(gold.astype(np.uint8), 8)
    for group in np.split(rows, np.where(np.diff(rows) > 3)[0]+1):
        top, bottom = int(group[0]), int(group[-1]+1)
        glyphs = np.zeros((h, w), bool)
        for label in range(1, number):
            x, y, width, height, _ = stats[label]
            # A continuous physical side rim is not a copy component. Detached
            # letters beyond the central seed remain eligible at the same rows.
            if (0 < x and x+width < w and y >= .62*h and
                    y < bottom and y+height > top and height <= max(4, 2*(bottom-top))):
                glyphs |= labels == label
        yy, xx = np.where(glyphs)
        if not len(xx):
            continue
        box = [max(0, int(xx.min())-2), max(0, int(yy.min())-2),
               min(w, int(xx.max())+3), min(h, int(yy.max())+3)]
        a, b, c, d = box
        mask[b:d, a:c] = True
        boxes.append(box)
    return mask, boxes


def physical_materials(source, inspection, brief, out, panels):
    folder = Path(out)/'physical-materials'; folder.mkdir(parents=True, exist_ok=True)
    material = {'schema': 'source_physical_material/2', 'body_sources': {}, 'cap_source': None,
                'scope': 'Original source physical material in mechanical drawing only; unknown hidden liquid remains absent.'}
    for key, target in [('body_front', 'hero_body'), ('cap_front', 'cap_source')]:
        info = inspection['panels'][key]; a, b, c, d = info['crop_px']; rgb = source[b:d, a:c]
        words = art._region_mask((c-a, d-b), inspection['art_repair']['panels'][key]['removal_boxes_px'], info['crop_px'])
        metal = panels[key]['metal'] if key == 'body_front' else np.zeros(words.shape, bool)
        clean, removal = physical_clean(rgb, words, metal)
        record = material_record(clean, removal, folder/(target+'.png'), info['crop_px'])
        record['outside_extraction_exact'] = bool(np.array_equal(clean[~removal], rgb[~removal]))
        material[target] = record
    hero = art.shade_loading(inspection, brief)['hero_shade_field']
    if hero is not None:
        material['body_sources'][hero] = material['hero_body']
    missing = []
    for field in sorted({row['shade_field'] for row in inspection['stand']['bottles'] if row['shade_field'] is not None}):
        if field in material['body_sources']:
            continue
        candidates = [row for row in inspection['stand']['bottles'] if row['shade_field'] == field]
        bottle = max(candidates, key=lambda row: row['box_px'][3]-row['box_px'][1])
        a, b, c, d = bottle['box_px']; rgb = source[b:d, a:c]
        density = art.gold_mask(rgb[:, max(1, (c-a)//5):max(2, 4*(c-a)//5)]).mean(axis=1)
        cap_rows = np.flatnonzero(density >= .65)
        cap_rows = cap_rows[cap_rows < .65*(d-b)]
        if not len(cap_rows) or cap_rows[-1] < .1*(d-b):
            missing.append({'shade_field': field, 'reason': 'No observed cap/body material boundary supports a source material crop.'})
            continue
        top = int(cap_rows[-1]+1); body = rgb[top:]
        words = _mapped_words(inspection['panels']['body_front'], (c-a, d-b-top))
        observed_words, word_boxes = _observed_word_spans(body)
        words |= observed_words
        h, w = words.shape
        seed = np.zeros((h, w), bool); seed[:round(.62*h), w//8:7*w//8] = True
        metal, _ = source_metal(body, seed, words)
        clean, removal = physical_clean(body, words, metal)
        record = material_record(clean, removal, folder/(field+'.png'), [a, b+top, c, d])
        record.update(observed_row=bottle['row'], observed_column=bottle['column'], cap_body_boundary_source_y=b+top,
                      source_word_removal={'method': 'Central columns seed copy rows; full-width source glyph components set padded removal boxes, excluding continuous side rims.',
                          'boxes_source_px': [[a+x0, b+top+y0, a+x1, b+top+y1] for x0, y0, x1, y1 in word_boxes]},
                      outside_extraction_exact=bool(np.array_equal(clean[~removal], body[~removal])))
        material['body_sources'][field] = record
    material['unresolved_materials'] = missing
    return material


def enclosure_samples(source, inspection):
    bottles = [row for row in inspection['stand']['bottles'] if row['row'] == 0]
    rows = []
    for left, right in zip(sorted(bottles, key=lambda row: row['column']), sorted(bottles, key=lambda row: row['column'])[1:]):
        x0, x1 = left['box_px'][2], right['box_px'][0]
        y0 = max(left['box_px'][1], right['box_px'][1]); y1 = min(left['box_px'][3], right['box_px'][3])
        if x1 > x0 and y1 > y0:
            rows.append([x0, y0, x1, y1])
    candidates = []
    for box in rows:
        a, b, c, d = box; rgb = source[b:d, a:c]; mask = art.gold_mask(rgb)
        yy, xx = np.where(mask)
        candidates.extend((int(x+a), int(y+b), source[y+b, x+a].tolist()) for y, x in zip(yy, xx))
    if not candidates:
        return {'status': 'unresolved', 'reason': 'No visible source tray gaps support a material finish.', 'sample_boxes_px': rows}
    colours = np.asarray([row[2] for row in candidates], dtype=float)
    median = np.median(colours, axis=0)
    index = int(np.argmin(np.sum((colours-median)**2, axis=1)))
    x, y, rgb = candidates[index]
    light = int(np.argmax(np.mean(colours, axis=1)))
    lx, ly, lrgb = candidates[light]
    return {'status': 'observed', 'sample_boxes_px': rows,
        'interior': {'rgb': rgb, 'source_pixel_px': [x, y]}, 'edge': {'rgb': lrgb, 'source_pixel_px': [lx, ly]},
        'method': 'Actual gold material pixels visible between inspected front-row bottles: median-nearest interior and observed light edge; drawing only.',
        'assembly_finish': {'provisional': True, 'source_class': 'SOURCE_PICTURE_OBSERVATION',
            'interior': 'Coloured stock or applied material finish matched to the observed warm tray interior.',
            'supports': 'The same proposed source-matched stock finish applies to exposed engine seat and collar faces; no printed motif is added.',
            'edge': 'Gold material finish on the actual tray edges.',
            'printed_surfaces': 'Header and base only; these material swatches add no ink to print masters.',
            'physical_sample_required': True, 'supplier_stock_measured': False}}


def prepare(source_path, inspection, brief, outdir, *, expected_sha256, base_prepare):
    result = base_prepare(source_path, inspection, brief, outdir, expected_sha256=expected_sha256)
    with Image.open(source_path) as image:
        source = np.asarray(image.convert('RGB'))
    panels = {}
    for key in art.PANEL_IDS:
        info = inspection['panels'][key]; crop = info['crop_px']; a, b, c, d = crop
        rgb = source[b:d, a:c]; size = (c-a, d-b); folder = Path(outdir)/key
        inside = art.silhouette(size, info['print_polygon_px'], crop)
        words = art._region_mask(size, inspection['art_repair']['panels'][key]['removal_boxes_px'], crop)
        seed = art._region_mask(size, info.get('lineart_boxes_px', []), crop)
        metal, segmentation = source_metal(rgb, seed, words | ~inside)
        if key == 'cap_front':
            metal[:] = False
        clean, removal = physical_clean(rgb, words, metal)
        # Header donor colour explicitly excludes dark brown/yellow physical
        # trim. Its entire actual top pane is now present in the refined crop.
        extension_record = None
        if key == 'stand_header':
            _extended, mapping = reflected_edge_source(rgb, inside, words, metal)
            sy, sx = mapping['source_y'], mapping['source_x']
            continued_metal = metal[sy, sx] & ~inside
            pane, _pane_measurement = observed_panes(rgb, inside, words)
            pane_donors = inside & pane & ~words & ~metal
            pane_donors &= rgb.max(axis=2) >= mapping['record']['observed_pane_value_floor']
            if not pane_donors.any():
                raise ValueError('No original clean pane donors support reflected raster extraction')
            pane_index = distance_transform_edt(~pane_donors, return_distances=False, return_indices=True)
            py, px = pane_index[0, sy, sx], pane_index[1, sy, sx]
            clean[~inside] = rgb[py[~inside], px[~inside]]
            metal |= continued_metal
            extension_record = mapping['record']
            extension_record['continued_observed_metal_pixels'] = int(continued_metal.sum())
            extension_record['raster_donor_rule'] = 'Original measured pane pixels only, separate from reflected foil coordinates; no extracted replacement pixel can become a donor.'
            np.savez_compressed(folder/'extension-source-coordinates.npz', source_x=mapping['source_x'],
                                source_y=mapping['source_y'], donor_mask=mapping['donors'],
                                raster_source_x=px, raster_source_y=py, raster_donor_mask=pane_donors)
            extension_record['coordinate_record'] = str((folder/'extension-source-coordinates.npz').resolve())
            extension_record['coordinate_record_sha256'] = art.sha(folder/'extension-source-coordinates.npz')
        baseline = np.asarray(Image.open(result['panels'][key]['upscale']))
        mask2 = np.repeat(np.repeat(removal & inside, 2, 0), 2, 1)
        extension2 = np.repeat(np.repeat(~inside if key == 'stand_header' else np.zeros(inside.shape, bool), 2, 0), 2, 1)
        output = baseline.copy()
        copied = np.repeat(np.repeat(clean, 2, 0), 2, 1)
        output[mask2 | extension2] = copied[mask2 | extension2]
        if key.startswith('stand_'):
            rgba = np.dstack((output, np.full(output.shape[:2], 255, np.uint8)))
        else:
            alpha = art._region_mask(size, info.get('colour_print_boxes_px', []), crop) & inside
            alpha2 = np.repeat(np.repeat(alpha, 2, 0), 2, 1)
            rgba = np.dstack((output, (alpha2*255).astype(np.uint8))); rgba[~alpha2] = 0
        Image.fromarray(rgba).save(folder/'artwork.png')
        Image.fromarray(metal.astype(np.uint8)*255).save(folder/'foil-source-mask.png')
        Image.fromarray((removal & inside).astype(np.uint8)*255).save(folder/'removal-mask.png')
        Image.fromarray(extension2.astype(np.uint8)*255).save(folder/'header-extension-mask.png')
        svg = folder/'lineart.svg'
        trace = trace_strokes(metal, svg) if metal.any() else None
        row = result['panels'][key]
        row.update(raster_sha256=art.sha(folder/'artwork.png'), lineart_svg=str(svg.resolve()) if trace else None,
                   lineart_sha256=art.sha(svg) if trace else None, lineart_measurement=trace, contours_norm=[],
                   source_segmentation=segmentation)
        row['preservation'].update(outside_allowed_masks_exact=bool(np.array_equal(output[~(mask2 | extension2)], baseline[~(mask2 | extension2)])),
            removal_pixels_2x=int(mask2.sum()), extension_pixels_2x=int(extension2.sum()), source_pixel_copy_only=True,
            extension=extension_record, lineart_source_pixels=int(metal.sum()),
            source_copy_method='Recorded extraction and reflected original source pixels; no repaint or image generation.')
        art.write(folder/'record.json', row)
        panels[key] = {'metal': metal, 'removal': removal}
    material = physical_materials(source, inspection, brief, outdir, panels)
    material['enclosure'] = enclosure_samples(source, inspection)
    inspection['drawing_material']['physical_source'] = material
    result['drawing_material'] = deepcopy(inspection['drawing_material'])
    result['refinement_v2'] = deepcopy(inspection['refinement_v2'])
    from .round_files_repair_art import _digest
    result['prepared_inspection_sha256'] = _digest(inspection)
    if art.sha(source_path) != expected_sha256:
        raise ValueError('Picked picture changed during source-material refinement')
    art.write(Path(outdir)/'inspection.json', inspection)
    art.write(Path(outdir)/'art.json', result)
    return result
