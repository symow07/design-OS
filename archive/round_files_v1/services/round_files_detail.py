"""Restartable preservation detail passes; the supplied context owns every paid call."""
from io import BytesIO
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from . import lid_master as metrics
from .round_calls import sha
from .round_flow import write_json


CANVASES = {'body_front': (1024, 1536), 'stand_header': (1536, 1024)}
THRESHOLDS = {'de00_mean_max': 1.5, 'ssim_min': .97}
PROMPT = ('Preservation detail pass of this single supplied flat panel crop, at the full supplied resolution. '
          'Remake fine detail only inside the transparent mask. Preserve EXACT composition, colours, textures, '
          'line positions, existing words, proportions and material. Do not redesign, add elements, invent copy, '
          'change lighting, create a scene or mockup, or alter the protected canvas. The crop is the design.')


def _read(path):
    return json.loads(Path(path).read_text())


def _unchanged(path, digest):
    if not Path(path).is_file() or sha(path) != digest:
        raise ValueError('A recorded detail-pass artifact changed: ' + str(path))


def _pins(folder, pins):
    for name, digest in pins.items():
        path = (folder/name).resolve()
        if not path.is_relative_to(folder.resolve()):
            raise ValueError('A detail-pass pin leaves its own panel folder')
        _unchanged(path, digest)


def _save_image(path, image):
    output = BytesIO(); image.save(output, format='PNG'); data = output.getvalue()
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('A partial detail-pass image changed: ' + str(path))
    else:
        path.write_bytes(data)


def compare_crop(reference, candidate):
    """Independent original-resolution CIEDE2000 and Gaussian-window luma SSIM."""
    original = np.asarray(reference.convert('RGB'))
    if min(reference.size) < 13:
        raise ValueError('A detail crop is too small for the existing 11-pixel SSIM window')
    compared = np.asarray(candidate.convert('RGB').resize(reference.size, Image.Resampling.LANCZOS))
    mean = float(metrics.delta_e00(metrics.srgb_to_lab(original), metrics.srgb_to_lab(compared)).mean())
    similarity = float(metrics.ssim(metrics.luma(original), metrics.luma(compared)))
    if not all(math.isfinite(value) for value in (mean, similarity)):
        raise ValueError('Detail-pass comparison must return finite measurements')
    return {'de00_mean': mean, 'ssim': similarity,
        'accepted': mean <= THRESHOLDS['de00_mean_max'] and similarity >= THRESHOLDS['ssim_min'],
        'thresholds': dict(THRESHOLDS), 'reference_px': list(reference.size),
        'candidate_px': list(candidate.size),
        'method': 'Candidate RGB downsampled with Pillow Lanczos to the original crop; CIEDE2000 mean and Gaussian-window luma SSIM before any type/material changes.'}


def _prepare(folder, panel_id, source_path, crop_px, expected_source_sha256):
    source_path = Path(source_path).resolve()
    _unchanged(source_path, expected_source_sha256)
    if panel_id not in CANVASES:
        raise ValueError('Only the bottle front and stand header have an authorized detail pass')
    if (not isinstance(crop_px, (list, tuple)) or len(crop_px) != 4 or
            any(isinstance(x, bool) or not isinstance(x, int) for x in crop_px)):
        raise ValueError('Detail crop coordinates must be four source-pixel integers')
    with Image.open(source_path) as image:
        x0, y0, x1, y1 = crop_px
        if not 0 <= x0 < x1 <= image.width or not 0 <= y0 < y1 <= image.height:
            raise ValueError('Detail crop must remain inside its own picked source')
        source_size = list(image.size)
        crop = image.convert('RGB').crop(crop_px)
    if min(crop.size) < 13:
        raise ValueError('A detail crop is too small for the existing 11-pixel SSIM window')
    dimensions = CANVASES[panel_id]
    scale = min((dimensions[0]-32)/crop.width, (dimensions[1]-32)/crop.height)
    size = (max(1, round(crop.width*scale)), max(1, round(crop.height*scale)))
    x, y = (dimensions[0]-size[0])//2, (dimensions[1]-size[1])//2
    box = [x, y, x+size[0], y+size[1]]
    identity = {'schema': 'round_files_detail_inputs/1', 'panel': panel_id,
        'source': str(source_path), 'source_sha256': expected_source_sha256, 'source_size_px': source_size,
        'crop_px': list(crop_px), 'crop_size_px': list(crop.size), 'model': 'gpt-image-2', 'quality': 'high',
        'canvas_size_px': list(dimensions), 'full_canvas_box_px': box, 'prompt': PROMPT,
        'mask_rule': 'Transparent only inside this own crop; opaque 16-pixel-or-larger canvas surround.',
        'fallback': 'Exact 2x cv2.INTER_LANCZOS4 crop', 'thresholds': dict(THRESHOLDS)}
    prepared = folder/'prepared.json'
    if prepared.exists():
        prior = _read(prepared)
        if prior['identity'] != identity:
            raise ValueError('A detail pass cannot change its source, crop, prompt or comparison contract')
        _pins(folder, prior['pins'])
        return identity
    folder.mkdir(parents=True, exist_ok=True)
    full = Image.new('RGB', dimensions, 'white')
    full.paste(crop.resize(size, Image.Resampling.LANCZOS), (x, y))
    mask = Image.new('RGBA', dimensions, (255, 255, 255, 255))
    mask.paste((255, 255, 255, 0), box)
    baseline = Image.fromarray(cv2.resize(np.asarray(crop), None, fx=2, fy=2, interpolation=cv2.INTER_LANCZOS4))
    for name, image in [('crop.png', crop), ('upscale.png', baseline), ('input.png', full), ('mask.png', mask)]:
        _save_image(folder/name, image)
    _unchanged(source_path, expected_source_sha256)
    write_json(prepared, {'identity': identity, 'pins': {name: sha(folder/name) for name in
        ('crop.png', 'upscale.png', 'input.png', 'mask.png')}})
    return identity


def detail_panel(ctx, panel_id, source_path, crop_px, outdir, *, expected_source_sha256):
    """One own-crop edit via ctx.image_call; rejected detail keeps exact 2x pixels.

    ctx.image_call accepts operation, prompt, folder, target, mask and size. Its
    durable records are image-call.json/.request.json/.response.json and raw.png.
    The context owns whitelisting, reservation, provider validation, settlement,
    journal recovery and the one-new-call-per-delivery yield.
    """
    folder = (Path(outdir)/panel_id).resolve()
    if not folder.is_relative_to(Path(ctx.root).resolve()):
        raise ValueError('Detail records must belong to their supplied worker context')
    identity = _prepare(folder, panel_id, source_path, crop_px, expected_source_sha256)
    checkpoint = folder/'detail.json'
    if checkpoint.exists():
        prior = _read(checkpoint)
        if prior['identity'] != identity:
            raise ValueError('A completed detail decision cannot change its input identity')
        _pins(folder, prior['pins'])
        comparison = _read(folder/'comparison.json')
        selected = 'candidate.png' if comparison['accepted'] else 'upscale.png'
        if (any(prior.get(key) != value for key, value in comparison.items()) or prior['selected'] != selected or
                prior['selected_path'] != str(folder/selected) or prior['selected_sha256'] != sha(folder/selected)):
            raise ValueError('A completed detail decision differs from its retained comparison')
        return prior
    size = 'x'.join(map(str, identity['canvas_size_px']))
    paid = ctx.image_call('detail/'+panel_id, PROMPT, folder/'call', target=folder/'input.png', mask=folder/'mask.png', size=size)
    required = ['call/image-call.json', 'call/image-call.request.json', 'call/image-call.response.json', 'call/raw.png']
    if paid.get('status') != 'complete' or any(not (folder/name).is_file() for name in required):
        raise ValueError('A detail decision requires a complete durable image reply')
    _unchanged(folder/'call/raw.png', paid['output_sha256'])
    with Image.open(folder/'call/raw.png') as image:
        if list(image.size) != identity['canvas_size_px']:
            raise ValueError('Detail output must have the recorded full-resolution dimensions')
        candidate = image.convert('RGB').crop(identity['full_canvas_box_px'])
    _save_image(folder/'candidate.png', candidate)
    with Image.open(folder/'crop.png') as reference:
        comparison = compare_crop(reference, candidate)
    comparison.update(reference_sha256=sha(folder/'crop.png'), candidate_sha256=sha(folder/'candidate.png'))
    compared = folder/'comparison.json'
    if compared.exists() and _read(compared) != comparison:
        raise ValueError('A recovered detail comparison differs from its retained measurements')
    if not compared.exists():
        write_json(compared, comparison)
    selected = 'candidate.png' if comparison['accepted'] else 'upscale.png'
    _unchanged(source_path, expected_source_sha256)
    names = ['prepared.json', 'crop.png', 'upscale.png', 'input.png', 'mask.png', 'candidate.png', 'comparison.json', *required]
    result = {'schema': 'round_files_detail_decision/1', 'identity': identity, 'panel': panel_id,
        **comparison, 'selected': selected, 'selected_path': str(folder/selected), 'selected_sha256': sha(folder/selected),
        'reason': 'Detail meets both preservation thresholds' if comparison['accepted'] else 'Detail failed preservation; exact 2x crop retained',
        'reservation_id': paid['reservation_id'], 'cost_usd': paid.get('cost_usd'),
        'billing_state': paid.get('billing_state'), 'pins': {name: sha(folder/name) for name in names}}
    write_json(checkpoint, result)
    return result


def run_details(ctx, source_path, panels, outdir, *, expected_source_sha256):
    if set(panels) != set(CANVASES):
        raise ValueError('The detail stage requires the bottle front and stand header once each')
    return {'panels': {panel: detail_panel(ctx, panel, source_path, panels[panel], outdir,
        expected_source_sha256=expected_source_sha256) for panel in CANVASES}}
