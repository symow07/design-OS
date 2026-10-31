"""Attempt-two print media: selected detail pixels and fitted straight strokes.

No contour tracing, raster repainting, provider calls or physical cap pictures.
"""
from copy import deepcopy
import math
from pathlib import Path
import shutil

import cv2
import fitz
import numpy as np
from PIL import Image

from . import round_files_art as art
from . import round_files_line_fit as line_fit
from .round_files_refinement_v2 import source_metal


def _scaled(mask, size):
    return cv2.resize(mask.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST) > 0


def _selected(key, original, baseline, details, source_sha, crop):
    if key not in ('body_front', 'stand_header'):
        return baseline.copy(), None
    record = details['panels'][key]
    identity = record['identity']
    if (identity['source_sha256'] != source_sha or identity['crop_px'] != crop or
            record['panel'] != key or art.sha(record['selected_path']) != record['selected_sha256']):
        raise ValueError('Selected detail pixels do not match their pinned source panel')
    with Image.open(record['selected_path']) as image:
        selected = np.asarray(image.convert('RGB'))
    if record['accepted']:
        if (record['selected'] != 'candidate.png' or not all(math.isfinite(record[field]) for field in ('de00_mean', 'ssim')) or record['de00_mean'] > 1.5 or
                record['ssim'] < .97):
            raise ValueError('An accepted detail must satisfy both preservation measurements')
    elif record['selected'] != 'upscale.png' or not np.array_equal(selected, baseline):
        raise ValueError('Rejected detail must retain the exact two-times Lanczos baseline')
    return selected, deepcopy(record)


def _stroke_mask(path, size):
    with fitz.open(stream=Path(path).read_bytes(), filetype='svg') as svg:
        pdf = svg.convert_to_pdf()
    with fitz.open(stream=pdf, filetype='pdf') as doc:
        page = doc[0]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(size[0]*4/page.rect.width, size[1]*4/page.rect.height), alpha=True)
        rgba = np.frombuffer(pixmap.samples, np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)
        alpha = cv2.resize(rgba[..., -1], size, interpolation=cv2.INTER_AREA)
    return alpha > 0


def _copy_and_extend(selected, words, strokes, inside, header):
    removal = (words | strokes) & inside
    donors = inside & ~removal
    clean = art.nearest_clean_source_copy(selected, removal, donors)
    extension = np.zeros(inside.shape, bool)
    if header:
        extension = ~inside
        # Extend after extraction, using only original clean own-pane pixels.
        # Nearest 2D edge donors cannot copy removed gold or source lettering.
        clean = art.nearest_clean_source_copy(clean, extension, donors)
    return clean, removal, extension


def prepare_attempt_art(source_path, inspection, brief, outdir, details, geometry, *, expected_sha256, width_mode='fixed'):
    if width_mode not in ('fixed', 'pictured'):
        raise ValueError('Foil widths must use the fixed instruction or the owner-authorized picture measurement.')
    source_path, out = Path(source_path), Path(outdir)
    if art.sha(source_path) != expected_sha256:
        raise ValueError('Picked picture changed before attempt-two extraction')
    with Image.open(source_path) as picture:
        picture = picture.convert('RGB')
    plan = art.validate_inspection(inspection, picture.size, brief)
    literal = art.copy_fields(brief)
    product = brief['dimensions_mm']
    body_size = [float(product['width']), float(product['height'])-float(product['cap_height'])]
    body_crop = plan['panels']['body_front']['crop_px']
    body_mm_per_original_px = body_size[0]/(body_crop[2]-body_crop[0])
    sizes = {'body_front': body_size, 'cap_front': [body_size[0], float(product['cap_height'])],
             'stand_header': geometry['surfaces']['stand_header']['size_mm'],
             'stand_base': geometry['surfaces']['stand_base']['size_mm']}
    descriptor = {'schema': 'round_files_art/1', 'attempt_schema': 'straight_detail_art/1',
        'source': str(source_path.resolve()), 'source_sha256': expected_sha256,
        'source_size_px': list(picture.size), 'panels': {}, 'foil_width_mode': width_mode,
        'drawing_material_strategy': 'Source-free engine materials only. Print body is clear except declared ink; cap has no source raster. No physical_source from a previous attempt is inherited.'}
    out.mkdir(parents=True, exist_ok=True)
    art.write(out/'inspection.json', plan)
    for key in art.PANEL_IDS:
        info = plan['panels'][key]; crop = info['crop_px']; folder = out/key
        folder.mkdir(parents=True, exist_ok=True)
        original = np.asarray(picture.crop(crop))
        baseline = cv2.resize(original, None, fx=2, fy=2, interpolation=cv2.INTER_LANCZOS4)
        selected, detail_record = _selected(key, original, baseline, details, expected_sha256, crop)
        # Retain the exact inputs before classification or geometry can stop.
        Image.fromarray(original).save(folder/'crop.png')
        Image.fromarray(baseline).save(folder/'upscale.png')
        if detail_record is not None:
            shutil.copyfile(detail_record['selected_path'], folder/'selected.png')
        else:
            Image.fromarray(selected).save(folder/'selected.png')
        original_size = (original.shape[1], original.shape[0]); size = (selected.shape[1], selected.shape[0])
        original_inside = art.silhouette(original_size, info['print_polygon_px'], crop)
        original_words = art.letter_mask(original, info, crop)
        original_seed = art._region_mask(original_size, info.get('lineart_boxes_px', []), crop)
        inside = _scaled(original_inside, size)
        words = _scaled(original_words, size)
        seed = _scaled(original_seed, size)
        colour = _scaled(art._region_mask(original_size, info.get('colour_print_boxes_px', []), crop), size) & inside
        strokes = np.zeros(inside.shape, bool)
        lines = np.zeros(inside.shape, bool)
        fit_record = None; svg = None; segmentation = None
        if key != 'cap_front' and seed.any():
            # The full source segmentation remains the measurement denominator.
            # Neither line fitting nor its footprint can select easier pixels.
            original_lines, original_segmentation = source_metal(
                original, original_seed, original_words | ~original_inside,
                distinguish_material=width_mode == 'pictured')
            if not original_lines.any():
                raise ValueError('The original picked crop has no supported gold motif pixels: '+key)
            Image.fromarray(original_lines.astype(np.uint8)*255).save(folder/'original-foil-source-mask.png')
            art.write(folder/'original-source-classification.json', original_segmentation)
            if detail_record is None or not detail_record['accepted']:
                # Lanczos ringing is not new motif evidence. A fallback has no
                # new source detail: carry the entire original mask unchanged.
                lines = _scaled(original_lines, size)
                segmentation = {'method': 'Nearest-neighbour transport of the full original mask; no colour reclassification of the upscale.',
                                'original': original_segmentation}
            else:
                lines, segmentation = source_metal(selected, seed, words | ~inside,
                    distinguish_material=width_mode == 'pictured')
            if not lines.any():
                raise ValueError('Inspected motif regions contain no supported gold line pixels: '+key)
            Image.fromarray(lines.astype(np.uint8)*255).save(folder/'foil-source-mask.png')
            art.write(folder/'selected-source-classification.json', segmentation)
            width = .3
            if width_mode == 'fixed' and key.startswith('stand_'):
                width *= (float(sizes[key][0])/original_size[0])/body_mm_per_original_px
            svg = folder/'lineart.svg'
            fit_inputs = folder/'fit-inputs.json'
            art.write(fit_inputs, {'schema':'panel_fit_inputs/1', 'panel':key,
                'source_picture_sha256':expected_sha256, 'source_crop_px':crop,
                'original_size_px':list(original_size), 'selected_size_px':list(size),
                'size_mm':list(sizes[key]), 'width_mode':width_mode,
                'fixed_width_mm':width if width_mode == 'fixed' else None,
                'minimum_pixel_coverage':.9,
                'original_motif_pixels':int(original_lines.sum()), 'selected_motif_pixels':int(lines.sum()),
                'detail_selection':detail_record,
                'files':{name:art.sha(folder/name) for name in (
                    'crop.png','upscale.png','selected.png','original-foil-source-mask.png',
                    'foil-source-mask.png','original-source-classification.json','selected-source-classification.json')}})
            try:
                fit_record = line_fit.fit_line_network(selected, lines, sizes[key], svg, width,
                    **({'width_mode': 'pictured', 'width_reference_mask': original_lines} if width_mode == 'pictured' else {}))
            except Exception as exc:
                diagnostic = getattr(exc, 'diagnostic', None)
                if diagnostic is None:
                    diagnostic = {'schema':'panel_geometry_error/1'}
                if isinstance(diagnostic, dict):
                    exc.diagnostic = dict(diagnostic, panel=key,
                        fit_inputs_path=str(fit_inputs.resolve()), fit_inputs_sha256=art.sha(fit_inputs))
                raise
            for segment in fit_record['segments']:
                segment['endpoints_original_source_px'] = [
                    [crop[0]+(point[0]+.5)*original_size[0]/size[0]-.5,
                     crop[1]+(point[1]+.5)*original_size[1]/size[1]-.5]
                    for point in segment['endpoints_source_px']]
            fit_record['width_reference_original_crop_px'] = list(original_size)
            original_measurement = line_fit.measure_line_network(svg, original_lines, sizes[key], width,
                **({'width_mode': 'pictured'} if width_mode == 'pictured' else {}))
            original_measurement['source_segmentation'] = original_segmentation
            original_measurement['source_picture_sha256'] = expected_sha256
            original_measurement['source_crop_px'] = crop
            original_measurement['mask_sha256'] = art.sha(folder/'original-foil-source-mask.png')
            fit_record['original_picture_measurement'] = original_measurement
            art.write(folder/'line-fit.json', fit_record)
            if not fit_record['passed'] or fit_record['coverage'] < .9 or not fit_record['all_segments_supported']:
                raise ValueError('Fitted motif coverage/support failed before bundle: '+key)
            if (not original_measurement['passed'] or original_measurement['coverage'] < .9 or
                    not original_measurement['all_segments_supported']):
                raise ValueError('Fitted motif differs from original picked lines before bundle: '+key)
            strokes = _stroke_mask(svg, size) & ~words
        clean, removal, extension = _copy_and_extend(selected, words, strokes, inside, key == 'stand_header')
        alpha = np.zeros(inside.shape, np.uint8)
        if key.startswith('stand_'):
            alpha[:] = 255
        elif key == 'body_front':
            alpha[colour] = 255
        rgba = np.dstack((clean, alpha)); rgba[alpha == 0] = 0
        for name, array in [('artwork', rgba),
                            ('text-removal-mask', words.astype(np.uint8)*255),
                            ('fitted-stroke-removal-mask', strokes.astype(np.uint8)*255),
                            ('removal-mask', removal.astype(np.uint8)*255),
                            ('header-extension-mask', extension.astype(np.uint8)*255)]:
            Image.fromarray(array).save(folder/(name+'.png'))
        text = art.text_rows(info, crop, literal)
        marks = []
        for row in info.get('marks', []):
            box = art._normal_box(row['box_px'], crop)
            if key == 'cap_front':
                width, height = box[2]-box[0], box[3]-box[1]
                box = [(1-width)/2, (1-height)/2, (1+width)/2, (1+height)/2]
            marks.append(dict(kind='logo', box_norm=box, color=row['color'], rotation=row.get('rotation', 0), foil=True))
        measured = art.fidelity(original, baseline)
        if detail_record is not None:
            measured = {'de00_mean': detail_record['de00_mean'], 'ssim': detail_record['ssim'],
                        'accepted': detail_record['accepted'], 'selected': detail_record['selected'],
                        'method': detail_record['method']}
        outside_exact = np.array_equal(clean[~(removal | extension)], selected[~(removal | extension)])
        record = {'id': key, 'crop': str((folder/'crop.png').resolve()), 'upscale': str((folder/'upscale.png').resolve()),
            'raster': str((folder/'artwork.png').resolve()), 'lineart_svg': None, 'lineart_sha256': None,
            'contours_norm': [], 'text': text, 'marks': marks, 'source_crop_px': crop,
            'ornament': art.ornament_rows(info, crop, brief),
            'source_size_px': list(original_size), 'size_px': list(size), 'size_mm': sizes[key], 'fidelity': measured,
            'source_crop_sha256': art.sha(folder/'crop.png'), 'raster_sha256': art.sha(folder/'artwork.png'),
            'selected_path': str((folder/'selected.png').resolve()), 'selected_sha256': art.sha(folder/'selected.png'),
            'detail': detail_record, 'lineart_measurement': fit_record, 'source_segmentation': segmentation,
            'substrate': 'Stand source picture' if key.startswith('stand_') else 'Clear body or unpainted physical cap; only declared ink and separate vector/live elements print.',
            'preservation': {'outside_allowed_masks_exact': bool(outside_exact),
                'gold_removal_rule': 'Only the actual fitted-stroke footprint; source copy/logo rectangles are separately declared.',
                'source_pixel_copy_only': True, 'lineart_source_pixels': int(lines.sum()),
                'removal_pixels': int(removal.sum()), 'extension_pixels': int(extension.sum()),
                'declared_colour_print_boxes_px': info.get('colour_print_boxes_px', []),
                'substrate_excluded_from_print': key in ('body_front', 'cap_front'),
                'cap_source_pixels_used': False, 'approved_logo_only': True,
                'allowed': ['Live COPY and approved logo replacement', 'Straight fitted gold strokes at recorded physical width',
                            'Clear body and unpainted cap', 'Header corners extended from its own unchanged clean edge pixels']}}
        if svg is not None:
            record['lineart_svg'] = str(svg.resolve()); record['lineart_sha256'] = art.sha(svg)
        art.write(folder/'record.json', record)
        descriptor['panels'][key] = record
    if art.sha(source_path) != expected_sha256:
        raise ValueError('Picked picture changed during attempt-two extraction')
    descriptor['source_unchanged'] = True
    art.write(out/'art.json', descriptor)
    return descriptor
