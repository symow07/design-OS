"""One worker-owned mechanical refinement, using only the pinned source pixels.

These functions do not call a model, run the worker, or decide whether a repair
is permitted. The job owns that limit and stores this output in a new revision.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from . import round_files_art as art


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def _expand(box, crop, padding):
    return [max(crop[0], box[0]-padding), max(crop[1], box[1]-padding),
            min(crop[2], box[2]+padding), min(crop[3], box[3]+padding)]


def _removal_boxes(panel):
    """Expand extraction alone; live type/logo placement remains exactly fixed."""
    crop = panel['crop_px']
    rows = panel.get('text', []) + panel.get('marks', [])
    records = []
    for row in rows:
        box = row['box_px']
        padding = min(6, max(2, round(min(box[2]-box[0], box[3]-box[1])*.18)))
        records.append({'source_box_px': list(box), 'box_px': _expand(box, crop, padding),
                        'padding_source_px': padding, 'reason': 'Remove source glyph antialiasing, highlight and shadow.'})
    text = panel.get('text', [])
    for left in text:
        for right in text:
            # A narrow separator between two same-baseline product COPY fields
            # belongs to that source lettering. Shade labels are never bridged.
            if {left['field'], right['field']} != {'product_latin', 'product_arabic'}:
                continue
            a, b = left['box_px'], right['box_px']
            gap = b[0]-a[2]
            overlap = min(a[3], b[3])-max(a[1], b[1])
            small_height, large_height = min(a[3]-a[1], b[3]-b[1]), max(a[3]-a[1], b[3]-b[1])
            if 0 < gap <= .75*large_height and overlap >= .7*small_height:
                bridge = [a[2], min(a[1], b[1]), b[0], max(a[3], b[3])]
                records.append({'source_box_px': bridge, 'box_px': _expand(bridge, crop, 3),
                                'padding_source_px': 3, 'reason': 'Remove the narrow original product-copy separator; no new copy is introduced.'})
    return {'removal_boxes_px': [row['box_px'] for row in records], 'regions': records,
            'live_placements_unchanged': True, 'maximum_padding_source_px': 6}


def _observed_colour(rgb, box, cap_fraction):
    """Sample a central visible liquid area, avoiding caps and bottom labels."""
    x0, y0, x1, y1 = box
    w, h = x1-x0, y1-y0
    left, right = x0+round(w*.25), x0+round(w*.75)
    top = y0+round(h*(cap_fraction+.15*(1-cap_fraction)))
    bottom = y0+round(h*(cap_fraction+.65*(1-cap_fraction)))
    sample = rgb[top:bottom, left:right]
    if sample.size == 0:
        return None
    hsv = cv2.cvtColor(sample, cv2.COLOR_RGB2HSV)
    valid = (hsv[..., 1] >= 25) & (hsv[..., 2] >= 40) & ~art.gold_mask(sample)
    if valid.sum() < max(12, .15*valid.size):
        return None
    lab = art.metrics.srgb_to_lab(sample)[valid]
    return {'lab': np.median(lab, axis=0).tolist(), 'sample_box_px': [left, top, right, bottom],
            'accepted_source_pixels': int(valid.sum())}


def _resolve_visible_shades(rgb, inspection, brief):
    bottles = inspection['stand']['bottles']
    product = brief['dimensions_mm']
    cap_fraction = float(product['cap_height'])/float(product['height'])
    known = [row for row in bottles if row['shade_field'] is not None]
    aspects = [(row['box_px'][3]-row['box_px'][1])/(row['box_px'][2]-row['box_px'][0]) for row in known]
    expected_aspect = float(np.median(aspects)) if aspects else float(product['height'])/float(product['width'])
    prototypes, measurements = {}, []
    for row in known:
        box = row['box_px']
        if (box[3]-box[1])/(box[2]-box[0]) < .75*expected_aspect:
            continue
        measured = _observed_colour(rgb, box, cap_fraction)
        if measured is not None:
            prototypes.setdefault(row['shade_field'], []).append(measured['lab'])
    prototypes = {field: np.median(np.asarray(values), axis=0) for field, values in prototypes.items()}
    for row in bottles:
        if row['shade_field'] is not None:
            continue
        record = {'row': row['row'], 'column': row['column'], 'source_box_px': list(row['box_px']),
                  'before': None, 'after': None}
        box = row['box_px']
        if (box[3]-box[1])/(box[2]-box[0]) < .75*expected_aspect:
            record['reason'] = 'Only a partial bottle is visible; hidden liquid is not assigned a shade.'
            measurements.append(record)
            continue
        measured = _observed_colour(rgb, box, cap_fraction)
        if measured is None or not prototypes:
            record['reason'] = 'No sufficiently supported visible liquid/source reference colour.'
            measurements.append(record)
            continue
        distances = sorted((float(art.metrics.delta_e00(np.asarray(measured['lab']), lab)), field)
                           for field, lab in prototypes.items())
        best, field = distances[0]
        margin = distances[1][0]-best if len(distances)>1 else None
        record.update(measured)
        record['reference_delta_e00'] = {key: value for value, key in distances}
        record['runner_up_margin_delta_e00'] = margin
        # With a single source reference, only an almost exact match is evidence.
        accepted = best <= (8. if margin is not None else 2.) and (margin is None or margin >= 3.)
        if accepted:
            row['shade_field'] = field
            record['after'] = field
            record['reason'] = 'Visible liquid matches an inspected source bottle of this supplied shade.'
        else:
            record['reason'] = 'Visible source colour is ambiguous; shade remains unresolved.'
        measurements.append(record)
    return {'method': 'Central visible liquid compared in CIEDE2000 with known-shade bottles in the same source picture.',
            'minimum_visible_aspect_ratio': .75*expected_aspect,
            'maximum_delta_e00': 8., 'minimum_runner_up_margin_delta_e00': 3.,
            'single_reference_maximum_delta_e00': 2.,
            'source_reference_lab': {key: value.tolist() for key, value in prototypes.items()},
            'decisions': measurements}


def _largest_run(mask):
    positions = np.flatnonzero(mask)
    if not len(positions):
        return None
    runs = np.split(positions, np.where(np.diff(positions)>1)[0]+1)
    chosen = max(runs, key=len)
    return int(chosen[0]), int(chosen[-1]+1)


def _measure_material(rgb, inspection, brief):
    panel = inspection['panels']['body_front']
    crop = panel['crop_px']; x0, y0, x1, y1 = crop
    source = rgb[y0:y1, x0:x1]
    field = art.shade_loading(inspection, brief)['hero_shade_field']
    base = {'source_crop_px': list(crop), 'hero_shade_field': field,
            'method': 'Largest contiguous source liquid region matching the known hero hue; walls/base remain original source pixels.',
            'scope': 'Drawing-only physical material; never included in a print master.'}
    if field is None:
        return dict(base, status='unresolved', reason='The hero source has no inspected shade COPY field.')
    value = brief['shades'][int(field.split('_')[1])]['hex']
    reference = np.asarray([[[int(value[i:i+2], 16) for i in (1, 3, 5)]]], dtype=np.uint8)
    reference_hsv = cv2.cvtColor(reference, cv2.COLOR_RGB2HSV)[0, 0]
    hsv = cv2.cvtColor(source, cv2.COLOR_RGB2HSV)
    hue_distance = np.abs(hsv[..., 0].astype(float)-float(reference_hsv[0]))
    hue_distance = np.minimum(hue_distance, 180-hue_distance)
    material = ((hue_distance <= 18) & (hsv[..., 1] >= max(25, float(reference_hsv[1])*.22)) &
                (hsv[..., 2] >= 35) & ~art.gold_mask(source))
    material &= art.silhouette((x1-x0, y1-y0), panel['print_polygon_px'], crop)
    material &= ~art._region_mask((x1-x0, y1-y0), panel.get('colour_print_boxes_px', []), crop)
    occupancy = material.sum(axis=0)
    horizontal = _largest_run(occupancy >= max((y1-y0)*.25, float(occupancy.max())*.5))
    if horizontal is None or horizontal[1]-horizontal[0] < .2*(x1-x0):
        return dict(base, status='unresolved', reason='The source does not separate liquid from walls reliably.')
    left, right = horizontal
    row_count = material[:, left:right].sum(axis=1)
    vertical = _largest_run(row_count >= max((right-left)*.25, float(row_count.max())*.4))
    if vertical is None or vertical[1]-vertical[0] < .4*(y1-y0):
        return dict(base, status='unresolved', reason='The source does not support a continuous liquid height.')
    top, bottom = vertical
    return dict(base, status='measured', liquid_box_source_px=[x0+left, y0+top, x0+right, y0+bottom],
                liquid_box_norm=[left/(x1-x0), top/(y1-y0), right/(x1-x0), bottom/(y1-y0)],
                acrylic_margin_source_px={'left': left, 'top': top, 'right': x1-x0-right, 'base': y1-y0-bottom},
                liquid_source_pixels=int(material[top:bottom, left:right].sum()))


def refine_inspection(source_path, inspection, brief, *, original_sha256):
    """Return a new inspection and evidence; never mutate its input or source."""
    source_path = Path(source_path)
    if art.sha(source_path) != original_sha256:
        raise ValueError('Picked picture changed before the mechanical refinement')
    with Image.open(source_path) as image:
        source = np.asarray(image.convert('RGB'))
    refined = art.validate_inspection(inspection, (source.shape[1], source.shape[0]), brief)
    source_inspection_sha = _digest(inspection)
    shade_record = _resolve_visible_shades(source, refined, brief)
    panels, trace_records = {}, {}
    for key in art.PANEL_IDS:
        panel = refined['panels'][key]
        panels[key] = _removal_boxes(panel)
        original_boxes = deepcopy(panel.get('lineart_boxes_px', []))
        expanded = [_expand(box, panel['crop_px'], 4) for box in original_boxes]
        x0, y0, x1, y1 = panel['crop_px']; pixels = source[y0:y1, x0:x1]
        size = (x1-x0, y1-y0)
        inside = art.silhouette(size, panel['print_polygon_px'], panel['crop_px'])
        protected = art._region_mask(size, panels[key]['removal_boxes_px'], panel['crop_px'])
        previous = art._region_mask(size, original_boxes, panel['crop_px'])
        enlarged = art._region_mask(size, expanded, panel['crop_px'])
        actual = art.gold_mask(pixels) & inside & ~protected
        trace_records[key] = {'before_boxes_px': original_boxes, 'after_boxes_px': expanded,
                             'maximum_halo_source_px': 4, 'new_observed_gold_pixels': int((actual & enlarged & ~previous).sum()),
                             'method': 'Bounded localisation halo; only existing source gold is traced and its source coordinates stay fixed.'}
        panel['lineart_boxes_px'] = expanded
    refined['drawing_material'] = _measure_material(source, refined, brief)
    refined['art_repair'] = {'schema': 'round_files_art_refinement/1', 'source_sha256': original_sha256,
                             'original_inspection_sha256': source_inspection_sha, 'panels': panels}
    record = {'schema': 'round_files_art_refinement_record/1', 'source_sha256': original_sha256,
              'original_inspection_sha256': source_inspection_sha, 'refined_inspection_sha256': _digest(refined),
              'shade_resolution': shade_record, 'extraction_masks': panels, 'lineart_localisation': trace_records,
              'drawing_material': deepcopy(refined['drawing_material']), 'source_unchanged': art.sha(source_path)==original_sha256,
              'policy': 'One deterministic worker repair; original picture and original inspection are retained; hidden shades are never inferred.'}
    if not record['source_unchanged']:
        raise ValueError('Picked picture changed during the mechanical refinement')
    return {'inspection': refined, 'record': record}


def prepare_repaired_art(source_path, refined_inspection, brief, outdir, *, expected_sha256):
    """Build a new art revision and attach drawing-only acrylic material paths."""
    repair = refined_inspection['art_repair']
    if repair['source_sha256'] != expected_sha256:
        raise ValueError('Refinement belongs to another picked picture')
    out = Path(outdir)
    descriptor = art.prepare_art(source_path, refined_inspection, brief, out,
                                 expected_sha256, repair_masks=repair['panels'])
    material = refined_inspection['drawing_material']
    if material['status'] == 'measured':
        panel = descriptor['panels']['body_front']
        original = np.asarray(Image.open(panel['crop']).convert('RGB'))
        x0, y0, x1, y1 = refined_inspection['panels']['body_front']['crop_px']
        a, b, c, d = material['liquid_box_source_px']
        wall = np.ones(original.shape[:2], dtype=bool)
        wall[b-y0:d-y0, a-x0:c-x0] = False
        removal = np.asarray(Image.open(out/'body_front'/'removal-mask.png'))>0
        # Original printed gold/copy does not become a second raster print layer
        # in the material proof. Donors remain on the original acrylic walls.
        clean = art.nearest_clean_source_copy(original, wall & removal, wall & ~removal)
        rgba = np.dstack((clean, (wall*255).astype(np.uint8)))
        rgba[~wall] = 0
        target = out/'body_front'/'acrylic-walls-drawing-only.png'
        Image.fromarray(rgba).save(target)
        material['wall_raster'] = str(target.resolve())
        material['wall_raster_sha256'] = art.sha(target)
        material['wall_source_pixels'] = int((wall & ~removal).sum())
        material['wall_extraction_pixels'] = int((wall & removal).sum())
        material['outside_extraction_exact'] = bool(np.array_equal(clean[wall & ~removal], original[wall & ~removal]))
    descriptor['drawing_material'] = deepcopy(material)
    descriptor['repair'] = deepcopy(repair)
    descriptor['prepared_inspection_sha256'] = _digest(refined_inspection)
    art.write(out/'inspection.json', refined_inspection)
    art.write(out/'art.json', descriptor)
    if art.sha(source_path) != expected_sha256:
        raise ValueError('Picked picture changed during repaired art preparation')
    return descriptor


def refine_inspection_v2(source_path, inspection, brief, *, original_sha256):
    """Second authorized repair, retaining original source/absolute COPY boxes."""
    from . import round_files_refinement_v2 as v2
    result = refine_inspection(source_path, inspection, brief, original_sha256=original_sha256)
    refined = result['inspection']
    with Image.open(source_path) as image:
        source = np.asarray(image.convert('RGB'))
    # Region boxes are seeds in v2, never masks that truncate observed strokes.
    for key in art.PANEL_IDS:
        refined['panels'][key]['lineart_boxes_px'] = deepcopy(inspection['panels'][key].get('lineart_boxes_px', []))
    header = v2.refine_header(source, refined)
    refined['refinement_v2'] = {'schema': 'round_files_source_refinement/2',
        'source_sha256': original_sha256, 'header_source_region': header,
        'lineart': 'Connected observed metal highlights and core; skeleton positions and measured widths, no rectangle clipping or arbitrary halo.',
        'physical_material': 'Full original cap/body material minus extracted source lettering and foil; no flat liquid repaint.',
        'projection': 'True front elevation retains source-measured rear rise; broad perspective side-wall wedges are represented by actual board edges and a separate engine side elevation.'}
    result['record']['second_refinement'] = deepcopy(refined['refinement_v2'])
    result['record']['lineart_localisation'] = {'method': 'Inspection boxes are connected-component seeds; previous bounded halo is not used.'}
    result['record']['refined_inspection_sha256'] = _digest(refined)
    if art.sha(source_path) != original_sha256:
        raise ValueError('Picked picture changed during the second refinement')
    return result


def prepare_repaired_art_v2(source_path, refined_inspection, brief, outdir, *, expected_sha256):
    from . import round_files_refinement_v2 as v2
    return v2.prepare(source_path, refined_inspection, brief, outdir,
                      expected_sha256=expected_sha256, base_prepare=prepare_repaired_art)
