"""HAYAT D1/A: deterministic preservation only; never redraw the fragment painting.

The immutable 2× Lanczos plates and their round-trip fidelity precede cleaning.
Local mask cleaning has explicit area masks, retains the picked pink ink pixels,
and does not reconstruct anything concealed by the fork's pasted rectangles.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
from . import lid_master as lid

REPO = Path(__file__).resolve().parents[4]
SOURCE = REPO / 'docs/rounds/r1-balm/developments/D1/A'
OUT = REPO / 'docs/rounds/r1-balm/master'
PANELS = ('body', 'cap', 'label', 'back', 'side_left', 'front', 'side_right', 'top_end', 'bottom_end')
SOURCE_PINS = {'body.png': 'd1cf1ebf9f3a15ed297337ee289e2aef647ce44999cb8bb781d05ff343ae7716', 'cap.png': '303d76a1a955a5332569aa643b53df5c3583663d650323bb8065edbcb1048b6c', 'label.png': '0980fb2ba18955cf9fe1227ec88884849b011cc83b7cbd4c6609a64d4208201c', 'back.png': '6a01928e6dd8911db382c32e3ea762fe5c779a1a63b12b9c659e05bfb0186eba', 'side_left.png': 'a9ff03c29e62b4163ba97bdaa09277525552b022fca37ebfd4dfd854493d0e2e', 'front.png': 'd2a5c0914babcfa3d83ac900e6d39fc1f363393a08ce39d49e59f6d1825cbd0e', 'side_right.png': '81128c2d84eaf5900c9d2887ce6be3baec95daded9cc38738a3295c2dc0b3b53', 'top_end.png': '58c2a90e89f6baeb76b6d225087e91d4007b5c86b8f8d6f5ddf88b73d17a3971', 'bottom_end.png': '994889ee86bfecf568bc544e1de57363ff735daa37e51e34bfacae0b35e4d46c', 'crop.json': 'e77f208deeaac777d49adb37c77141ebfdb4b445aa02846501cb5d43af56e633', 'picture.png': 'a88576f2e1d94681b203e154acc32f16353dabf36da7fe76d4032bde9800c382', 'drawing.png': '7a26c1a8954c277361045061ffcf9d3e1467c53879fe4624fa2724e3a6369e23'}

# Hand-inspected fork boundaries, in source pixels; no new shape is drawn in them.
PATCHES = {
    'cap': [(52, 19, 241, 104)],
    'body': [(16, 54, 58, 118), (196, 55, 274, 109)],
    'side_left': [(25, 109, 48, 190)],
    'side_right': [(58, 92, 86, 183)],
}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def save(path, array):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.asarray(array, dtype=np.uint8)).save(path)


def paint_mask(rgb):
    """Warm painted ink; used only to protect existing strokes from ground cleaning."""
    a = rgb.astype(float)
    warm = (a[..., 0] > 105) & (a[..., 0] - a[..., 1] > 25) & (a[..., 0] - a[..., 2] > 20)
    core = warm & (a[..., 0] > 135)
    fringe = cv2.dilate(core.astype('uint8'), np.ones((3, 3), np.uint8)) > 0
    return core | (warm & fringe)


def construction_mask(name, src):
    """Only known neutral construction dashes/rules; painted strokes remain protected."""
    h, w = src.shape[:2]
    yy, xx = np.indices((h, w))
    if name == 'label':
        return np.zeros((h, w), bool)
    if name == 'body':
        xs, ys = [0, 274, w - 1, 101, 192], [0, 4.5, 197.5, h - 1]
        dash = ((abs(yy - 15) <= 1.5) | (abs(yy - 189) <= 1.5)) & (xx >= 100) & (xx <= 193)
    elif name == 'cap':
        xs, ys = [0, 274.5, w - 1, 101, 192], [0, 4.5, 149, h - 1]
        dash = ((abs(yy - 14.5) <= 1.5) | (abs(yy - 140.5) <= 1.5)) & (xx >= 100) & (xx <= 193)
    else:
        xs, ys = [0, w - 1, 15, 82 if name.endswith('_end') else 85], [0, h - 1]
        dash = ((abs(yy - 14) <= 1.5) | (abs(yy - (84 if name.endswith('_end') else h - 15)) <= 1.5)) & (xx >= 14) & (xx <= w - 13)
    band = dash.copy()
    for x in xs:
        band |= abs(xx - x) <= 1.5
    for y in ys:
        band |= abs(yy - y) <= 1.5
    a = src.astype(float)
    neutral = (a.max(2) - a.min(2) < 40) & (a.min(2) > 45)
    mask = band & neutral
    mask = cv2.dilate(mask.astype('uint8'), np.ones((3, 3), np.uint8)) > 0
    return mask & ~paint_mask(src)


def clean_panel(name, src, plate):
    guides = construction_mask(name, src)
    gm = cv2.resize(guides.astype('uint8'), (plate.shape[1], plate.shape[0]), interpolation=cv2.INTER_NEAREST)
    gm = cv2.dilate(gm, np.ones((3, 3), np.uint8))
    # Isolate construction neutral ink: do not touch adjacent intentional pink paint.
    protected = paint_mask(plate)
    gm[protected] = 0
    clean = cv2.inpaint(plate, gm * 255, 7, cv2.INPAINT_NS)
    patch_mask = np.zeros(plate.shape[:2], bool)
    boxes = []
    for box in PATCHES.get(name, []):
        x0, y0, x1, y1 = [v * 2 for v in box]
        rect = np.zeros(plate.shape[:2], bool)
        rect[y0:y1, x0:x1] = True
        # Fit the local ground from the rectangle's immediate neighbours, excluding
        # paint. Preserve the patch's existing fine grain; no concealed stroke guessed.
        valid = ~(rect | protected | gm.astype(bool))
        # Normalized Gaussian extension of this surface's surrounding ground.
        # This bends to the real neighbours along every edge; a hard replacement
        # rectangle is never introduced. Large sigma reaches across the cap patch.
        sigma = max(12, min(x1 - x0, y1 - y0) / 2)
        weight = gaussian_filter(valid.astype(float), sigma)
        ground = np.stack([gaussian_filter(clean[..., c].astype(float) * valid, sigma) /
                           np.maximum(weight, 1e-8) for c in range(3)], -1)
        low = np.stack([gaussian_filter(clean[..., c].astype(float), 4) for c in range(3)], -1)
        grain = np.clip(clean.astype(float) - low, -12, 12)
        edge_distance = cv2.distanceTransform(rect.astype('uint8'), cv2.DIST_L2, 3)
        grain *= np.minimum(edge_distance / 5, 1)[..., None]
        replacement = np.clip(ground + grain, 0, 255)
        allowed = rect & ~protected
        # One-pixel ink fringe protection leaves every coloured fragment in place.
        protected_dilated = cv2.dilate(protected.astype('uint8'), np.ones((3, 3), np.uint8)) > 0
        allowed &= ~protected_dilated
        guide = np.where(protected_dilated[..., None], clean, replacement)
        solved = lid.poisson_fill(clean.astype(float), guide.astype(float), allowed)
        clean[allowed] = np.clip(solved[allowed], 0, 255).astype('uint8')
        patch_mask |= allowed
        boxes.append({'source_box_px': list(box), 'changed_area_px': int(allowed.sum()),
                      'method': 'normalized local ground extension plus the rectangle’s own high-frequency grain; Poisson boundary blend; existing warm ink protected'})
    changed = np.any(clean != plate, 2)
    if np.any(changed & protected):
        raise AssertionError(f'{name}: protected fragment ink altered')
    return clean, changed, gm.astype(bool), patch_mask, boxes


def verify_sources():
    for name, expected in SOURCE_PINS.items():
        if lid.sha256(SOURCE / name) != expected:
            raise ValueError(f'pinned D1/A source mismatch: {name}')


def build_plates(out=OUT):
    verify_sources()
    crop = json.loads((SOURCE / 'crop.json').read_text())['panels']
    fidelity = {'schema': 'round_balm_fidelity/1', 'design': 'D1/A — HAYAT', 'upscale': 'exactly 2× cv2.INTER_LANCZOS4, unmodified pinned pixels', 'panels': {}}
    cleaning = {'schema': 'round_balm_cleaning/1', 'design': 'D1/A — HAYAT', 'panels': {}, 'retained_findings': [
        'Repeated/interrupted strokes and all fragments are the design: retained, never traced or reconstructed.',
        'Fork rectangles conceal some earlier stroke continuity; cleaning restores only ground, never guesses concealed strokes.',
        'side_left also contains a fork rectangle; treated under the explicit any-mask-edge allowance.',
        'Small provisional raster copy is left for the separately recorded live-type conversion.',
        'Some straight clipped painted endings still reveal the fork boundary; their discontinuity is retained rather than inventing connecting strokes.']}
    for name in PANELS:
        src = np.array(Image.open(SOURCE / f'{name}.png').convert('RGB'))
        plate = lid.upscale(src)
        save(out / 'plates' / f'{name}.png', plate)
        physical = crop[name]['mm']
        source_ppi = [src.shape[1] / physical[0] * 25.4, src.shape[0] / physical[1] * 25.4]
        nominal_ppi = [x * 2 for x in source_ppi]
        report = lid.prove_upscale(src, plate, {})
        report.update({'source': str((SOURCE / f'{name}.png').relative_to(REPO)), 'source_sha256': lid.sha256(SOURCE / f'{name}.png'),
                       'plate': f'plates/{name}.png', 'plate_sha256': lid.sha256(out / 'plates' / f'{name}.png'),
                       'source_px': [src.shape[1], src.shape[0]], 'plate_px': [plate.shape[1], plate.shape[0]],
                       'source_extent_mm': physical, 'trim_mm': [58.5, 40] if name == 'body' else [58.5, 30] if name == 'cap' else physical,
                       'source_ppi_xy': source_ppi, 'resampled_ppi_xy': nominal_ppi,
                       'effective_ppi_at_trim': min(source_ppi), 'nominal_ppi_at_trim': min(nominal_ppi),
                       'effective_ppi_method': 'source-sampling upper bound: interpolation adds no independent detail; wrap source extent includes its two 1 mm bleed bands',
                       'ppi_300_met': min(source_ppi) >= 300,
                       'sharpness': {'source_hf_energy_above_quarter_nyquist': lid.spectrum_share_above(lid.luma(src), .25),
                                     'plate_hf_energy_above_source_nyquist': lid.spectrum_share_above(lid.luma(plate), .25),
                                     'method': 'lid_master.spectrum_share_above: DC removed, Hann-windowed Fourier luma energy; frequencies in cycles per current pixel'}})
        fidelity['panels'][name] = report
        clean, changed, guides, patches, boxes = clean_panel(name, src, plate)
        for suffix, array in [('before', plate), ('after', clean), ('mask', changed * 255), ('guide-mask', guides * 255), ('patch-mask', patches * 255), ('protected-ink', paint_mask(plate) * 255)]:
            save(out / 'cleaning' / f'{name}-{suffix}.png', array)
        cleaning['panels'][name] = {'before': f'cleaning/{name}-before.png', 'after': f'cleaning/{name}-after.png',
                                   'mask': f'cleaning/{name}-mask.png', 'source_sha256': report['source_sha256'],
                                   'cleaned_sha256': lid.sha256(out / 'cleaning' / f'{name}-after.png'),
                                   'changed_pixels': int(changed.sum()), 'total_pixels': int(changed.size),
                                   'cleaned_area_share': float(changed.mean()), 'boxes': boxes,
                                   'construction_pixels': int(guides.sum()), 'protected_ink_changed_pixels': 0,
                                   'unmasked_pixels_byte_identical': bool(np.array_equal(clean[~changed], plate[~changed]))}
    fidelity['all_fidelity_thresholds_pass'] = all(all(p['holds'].values()) for p in fidelity['panels'].values())
    fidelity['all_panels_300_ppi'] = all(p['ppi_300_met'] for p in fidelity['panels'].values())
    fidelity['status'] = 'Reports, not gates; low source resolution remains honestly listed under D-D10-2.1.'
    write_json(out / 'fidelity.json', fidelity)
    write_json(out / 'cleaning.json', cleaning)
    return fidelity, cleaning



def build_trace(out=OUT):
    """Only the cap's whole word: source alpha → 8× Potrace, independent 16× proof.

    Letter components are selected on the original sketch, never on the output
    vector. The visibly separate numeral-shaped component is explicitly removed.
    All other panels' word fragments remain raster.
    """
    verify_sources()
    src = np.array(Image.open(SOURCE / 'cap.png').convert('RGB'))
    a = src.astype(float)
    alpha = np.clip((a[..., 0] - 95.) / 80., 0, 1)
    alpha *= (a[..., 0] - a[..., 1] > 35)
    # Component sampling is independent of the vector. Four observed letter groups:
    # upper pair of dots, ta marbuta loop, joined ha/ya/alif, lower pair of dots.
    roi = np.zeros(alpha.shape, bool)
    roi[20:101, 53:240] = True
    core = (alpha >= .5) & roi
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(core.astype('uint8'), 8)
    seeds = [(66, 31), (67, 52), (110, 45), (157, 89)]
    selected = []
    for x, y in seeds:
        component = int(labels[y, x])
        if component == 0:
            # The point lies within the component's bbox but may be in a counter.
            candidates = [i for i, (xx, yy, ww, hh, area) in enumerate(stats) if i and xx <= x < xx + ww and yy <= y < yy + hh]
            if len(candidates) != 1:
                raise AssertionError(f'cap letter seed {x,y} does not uniquely identify a sketch component')
            component = candidates[0]
        selected.append(component)
    selected_mask = np.isin(labels, selected)
    region = cv2.dilate(selected_mask.astype('uint8'), np.ones((3, 3), np.uint8)) > 0
    selected_alpha = alpha * region * roi
    # Separate numeral 1 observed at x122..145, y33..61, including its short base.
    one_ids = [i for i, (x, y, w, h, area) in enumerate(stats) if i and 120 <= x <= 125 and 30 <= y <= 36 and area > 40]
    if len(one_ids) != 1:
        raise AssertionError('spurious 1 no longer matches the pinned source component')
    one = labels == one_ids[0]
    selected_alpha[cv2.dilate(one.astype('uint8'), np.ones((3, 3), np.uint8)) > 0] = 0
    h, w = alpha.shape
    trace_bitmap = cv2.resize(selected_alpha.astype('float32'), (w * 8, h * 8), interpolation=cv2.INTER_CUBIC) >= .5
    rings = lid.map_rings(lid.potrace_rings(trace_bitmap), lambda p: p / 8)
    geom = lid.rings_area(rings, 32)
    # This reference is recomputed from original sketch alpha at 16×; it is not
    # the traced bitmap nor a rasterized SVG self-comparison.
    ref = cv2.resize(selected_alpha.astype('float32'), (w * 16, h * 16), interpolation=cv2.INTER_CUBIC) >= .5
    fill = lid.raster_fill(geom, ref.shape, (0, 0), 16)
    iou = float((ref & fill).sum() / (ref | fill).sum())
    paths = []
    for ring in rings:
        paths.append('M ' + ' '.join(f'{v:.5f}' for v in ring[0][1]))
        for seg in ring:
            paths.append(seg[0] + ' ' + ' '.join(f'{v:.5f}' for point in seg[2:] for v in point))
        paths.append('Z')
    colour = np.median(src[selected_mask], axis=0).round().astype(int)
    hexcolour = '#' + ''.join(f'{x:02x}' for x in colour)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="58.5mm" height="32mm" viewBox="0 0 {w} {h}">\n'
           '<title>HAYAT — حياة — cap sketch trace; spurious numeral 1 removed</title>\n'
           f'<path id="hayat-logotype" fill="{hexcolour}" fill-rule="evenodd" d="' + ' '.join(paths) + '"/>\n</svg>\n')
    (out / 'logotype').mkdir(parents=True, exist_ok=True)
    (out / 'logotype/hayat.svg').write_text(svg)
    # Read the actual saved SVG through an independent renderer as a second proof.
    import fitz
    with fitz.open(stream=(out / 'logotype/hayat.svg').read_bytes(), filetype='svg') as doc:
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(w * 16 / page.rect.width, h * 16 / page.rect.height), alpha=True)
        actual = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[..., -1] >= 128
    actual_iou = float((actual & ref).sum() / (actual | ref).sum())
    save(out / 'logotype/actual-svg-silhouette.png', actual * 255)
    save(out / 'logotype/sketch-silhouette.png', ref * 255)
    save(out / 'logotype/vector-silhouette.png', fill * 255)
    save(out / 'logotype/sketch-alpha.png', selected_alpha * 255)
    # A small proof shows source pixels and independently rendered vector on the
    # same cleaned ground. The word's outer fragments are not included in the SVG.
    base = np.array(Image.open(out / 'cleaning/cap-after.png').convert('RGB'))
    one_up = cv2.resize(one.astype('uint8'), (w * 2, h * 2), interpolation=cv2.INTER_NEAREST)
    one_up = cv2.dilate(one_up, np.ones((7, 7), np.uint8))
    # Confine numeral clearing away from the intentional joined word below it.
    trace_protect = cv2.resize(selected_mask.astype('uint8'), (w * 2, h * 2), interpolation=cv2.INTER_NEAREST)
    one_up[cv2.dilate(trace_protect, np.ones((3, 3), np.uint8)) > 0] = 0
    without_one = cv2.inpaint(base, one_up * 255, 5, cv2.INPAINT_NS)
    save(out / 'logotype/cap-without-spurious-one.png', without_one)
    save(out / 'logotype/spurious-one-before.png', base[54:130, 234:300])
    save(out / 'logotype/spurious-one-after.png', without_one[54:130, 234:300])
    save(out / 'logotype/spurious-one-mask.png', one_up * 255)
    save(out / 'logotype/vector-preview.png', np.where(cv2.resize(fill.astype('uint8'), (w * 2, h * 2), interpolation=cv2.INTER_AREA)[..., None] > 0, colour, without_one))
    # Distances are computed independently against original-alpha contour pixels.
    from scipy.spatial import cKDTree
    ref_contours, _ = cv2.findContours(ref.astype('uint8'), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    vector_contours, _ = cv2.findContours(fill.astype('uint8'), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    ref_pts = np.concatenate([c[:, 0] for c in ref_contours]) / 16
    vec_pts = np.concatenate([c[:, 0] for c in vector_contours]) / 16
    factor = 58.5 / w
    d1 = cKDTree(ref_pts).query(vec_pts)[0] * factor
    d2 = cKDTree(vec_pts).query(ref_pts)[0] * factor
    result = {'schema': 'round_balm_trace/1', 'source': str((SOURCE / 'cap.png').relative_to(REPO)),
              'source_sha256': lid.sha256(SOURCE / 'cap.png'), 'vector': 'logotype/hayat.svg',
              'vector_sha256': lid.sha256(out / 'logotype/hayat.svg'), 'source_viewbox_px': [0, 0, w, h],
              'source_extent_mm': [58.5, 32], 'trim': {'y_mm': [1, 31], 'mm': [58.5, 30]},
              'word': 'حياة', 'fill': hexcolour, 'trace_method': 'lid_master.potrace_rings at 8× cubic alpha, alphamax=1, opttolerance=.2, turdsize=20',
              'reference_method': 'original pinned sketch soft red-channel alpha, sampled independently at 16×; four source components selected by observed letter seeds, before any vector exists',
              'source_component_seeds_px': seeds, 'source_components': [stats[i].tolist() for i in selected],
              'reference_exclusions': ['the separate numeral-shaped 1 component', 'larger exterior painted fragments', 'unconnected background brush specks; retained raster'],
              'removed': [{'item': 'spurious numeral-shaped 1 inside cap word', 'source_component_box_xywh_px': stats[one_ids[0]][:4].tolist(),
                           'source_core_pixels': int(one.sum()), 'cleaned_pixels_2x': int(one_up.sum()), 'cleaned_share_of_cap': float(one_up.mean()),
                           'before': 'logotype/spurious-one-before.png', 'after': 'logotype/spurious-one-after.png', 'mask': 'logotype/spurious-one-mask.png'}],
              'iou': iou, 'actual_svg_iou': actual_iou, 'actual_svg_proof_method': 'MuPDF reads saved SVG; 16× alpha threshold128 vs independently sampled original sketch reference', 'trace_to_sketch_max_mm': float(d1.max()), 'sketch_to_trace_max_mm': float(d2.max()),
              'holds': {'iou_0_95': iou >= .95, 'saved_svg_iou_0_95': actual_iou >= .95, 'overlay_within_0_3_mm': bool(max(d1.max(), d2.max()) <= .3)},
              'only_cap_word_traced': True, 'all_other_fragments_raster': True, 'no_font_substitution': True,
              'raster_underlay': 'logotype/cap-without-spurious-one.png',
              'raster_underlay_sha256': lid.sha256(out / 'logotype/cap-without-spurious-one.png'),
              'outside_numeral_mask_byte_identical': bool(np.array_equal(without_one[one_up == 0], base[one_up == 0]))}
    write_json(out / 'trace.json', result)
    if min(iou, actual_iou) < .95:
        raise AssertionError(f'cap logotype IoU {iou:.6f} below .95')
    return result


def build_emboss_proposal(out=OUT):
    """A separate, unapplied rolling-tool-clearance proof of the cap word only."""
    from PIL import ImageDraw, ImageFont
    from scipy.ndimage import distance_transform_edt
    ref = np.array(Image.open(out / 'logotype/actual-svg-silhouette.png')) > 127
    h, w = ref.shape
    mm_x, mm_y = 58.5 / w, 32. / h
    required = .3
    rx, ry = int(np.ceil(required / 2 / mm_x)), int(np.ceil(required / 2 / mm_y))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rx + 1, 2 * ry + 1))
    # Erosion finds only tool centres whose complete >=0.3 mm footprint fits.
    # Dilation reconstructs the union of these footprint placements. Thin tips
    # and isolated slivers excluded by this measured clearance remain ink.
    centers = cv2.erode(ref.astype('uint8'), kernel) > 0
    distance = distance_transform_edt(ref, sampling=(mm_y, mm_x))
    minimum_center_clearance = float(2 * distance[centers].min())
    # Reject lattice corner exceptions whose Euclidean clearance misses the bar.
    centers &= distance >= required / 2
    retained = cv2.dilate(centers.astype('uint8'), kernel) > 0
    retained &= ref
    excluded = ref & ~retained
    min_diameter = min(2 * rx * mm_x, 2 * ry * mm_y)
    measured_center_diameter = float(2 * distance[centers].min())
    if min(min_diameter, measured_center_diameter) < required:
        raise AssertionError('proposal tool clearance below 0.3 mm')
    folder = out / 'proposals'
    save(folder / 'cap-emboss-mask.png', retained * 255)
    save(folder / 'cap-emboss-excluded.png', excluded * 255)
    save(folder / 'cap-emboss-centres.png', centers * 255)
    # Proof page, never a layer or instruction in any production master.
    sheet = Image.new('RGB', (1500, 950), '#f7f5ef')
    draw = ImageDraw.Draw(sheet)
    font = lambda size: ImageFont.load_default(size=size)
    draw.rectangle((0, 0, 1500, 106), fill='#8f2031')
    draw.text((45, 26), 'BLIND EMBOSS / PROPOSAL ONLY / NOT APPLIED', font=font(39), fill='white')
    draw.text((45, 130), 'Cap word only. Rosewater master remains process colour, with no finish.', font=font(27), fill='#222222')
    # Isolate the logotype bounds; no brush fragments or other panel art enters.
    yy, xx = np.nonzero(ref)
    box = (int(xx.min()) - 24, int(yy.min()) - 24, int(xx.max()) + 25, int(yy.max()) + 25)
    crop = np.s_[box[1]:box[3], box[0]:box[2]]
    masks = [('Proposed relief footprint', retained), ('Fine edges stay in process ink', excluded)]
    for column, (title, mask) in enumerate(masks):
        x = 45 + column * 745
        draw.text((x, 205), title, font=font(26), fill='#222222')
        canvas = np.full((*ref[crop].shape, 3), 250, dtype='uint8')
        canvas[ref[crop]] = (220, 214, 206)
        canvas[mask[crop]] = (35, 35, 35) if column == 0 else (177, 52, 68)
        tile = Image.fromarray(canvas)
        tile.thumbnail((690, 390), Image.Resampling.LANCZOS)
        sheet.paste(tile, (x, 280))
    draw.line((45, 705, 1455, 705), fill='#b9b3a8', width=2)
    lines = [f'Measured rolling-tool diameter: {min_diameter:.4f} mm (required: at least 0.3000 mm).',
             f'Every retained pixel is covered by a permitted tool footprint; minimum centre clearance: {measured_center_diameter:.4f} mm.',
             f'Excluded fine area: {100 * excluded.sum() / ref.sum():.2f}% of the traced word; those edges remain process ink.',
             'This is a geometric relief proposal. No emboss, foil or varnish is applied to any .ai master.']
    for j, line in enumerate(lines):
        draw.text((45, 740 + j * 43), line, font=font(23), fill='#222222')
    save(folder / 'cap-emboss-proof.png', np.array(sheet))
    report = {'schema': 'hayat_emboss_proposal/1', 'status': 'FLAGGED PROPOSAL — NOT APPLIED',
              'applied_to_master': False, 'master_finish': 'process colour only', 'surface': 'cap word only',
              'source_vector': 'logotype/hayat.svg', 'source_vector_sha256': lid.sha256(out / 'logotype/hayat.svg'),
              'source_raster': 'logotype/actual-svg-silhouette.png', 'source_raster_sha256': lid.sha256(out / 'logotype/actual-svg-silhouette.png'),
              'proof': 'proposals/cap-emboss-proof.png', 'mask': 'proposals/cap-emboss-mask.png',
              'excluded_mask': 'proposals/cap-emboss-excluded.png', 'centre_mask': 'proposals/cap-emboss-centres.png',
              'required_min_feature_mm': required, 'minimum_feature_mm': min_diameter,
              'minimum_measured_centre_clearance_diameter_mm': measured_center_diameter,
              'measurement': 'independent anisotropic Euclidean distance transform from actual SVG silhouette; erode by ellipse, reject centres below 0.15 mm clearance, then reconstruct union of full tool footprints',
              'metric_scope': 'minimum rolling-tool footprint, not a promise about an unmade physical emboss die; all thin source tips outside the footprint remain ink',
              'kernel_radius_px_xy': [rx, ry], 'pixel_mm_xy': [mm_x, mm_y],
              'source_pixels': int(ref.sum()), 'retained_pixels': int(retained.sum()),
              'excluded_pixels': int(excluded.sum()), 'excluded_share_of_word': float(excluded.sum() / ref.sum()),
              'relief_outside_word_pixels': int((retained & ~ref).sum()),
              'minimum_feature_pass': bool(min(min_diameter, measured_center_diameter) >= required),
              'no_master_file_modified': True, 'finish_instructions_in_master': []}
    write_json(folder / 'cap-emboss-proof.json', report)
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, default=OUT)
    p.add_argument('--stage', choices=('plates', 'trace', 'proposal', 'all'), default='plates')
    args = p.parse_args()
    if args.stage in ('plates', 'all'):
        build_plates(args.out)
    if args.stage in ('trace', 'all'):
        build_trace(args.out)
    if args.stage in ('proposal', 'all'):
        build_emboss_proposal(args.out)


if __name__ == '__main__':
    main()
