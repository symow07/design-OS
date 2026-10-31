"""D-R1B-7: recover two named fork mistakes from their existing unoccluded raw.

No new image, no redraw and no alteration of the pinned design inputs or exact
2× plates. The owner specifically authorized these two interrupted side strokes
for local repair after pointing them out in screenshots.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt

from . import round_balm_preservation as p

RAW_SHA256 = '530c1e3ef5b03d7649e15d69e3ebd8954b707b37d44ff6cfb4bd9f4a559de0b9'
RECTANGLES = {'side_left': (23, 110, 48, 189), 'side_right': (60, 93, 86, 183)}
HALO_SOURCE_PX = 4


def build(out=p.OUT):
    p.verify_sources()
    raw_path = p.SOURCE / 'raw.png'
    if p.lid.sha256(raw_path) != RAW_SHA256:
        raise ValueError('pinned D1/A raw recovery source mismatch')
    raw = Image.open(raw_path).convert('RGB')
    geometry = json.loads((p.SOURCE / 'crop.json').read_text())['panels']
    reports = {}
    proof = Image.new('RGB', (1500, 1000), '#f8f6f0')
    draw = ImageDraw.Draw(proof)
    font = lambda size: ImageFont.load_default(size=size)
    draw.text((30, 22), 'Two local fork repairs / existing raw painting recovered', font=font(32), fill='#332428')
    draw.text((30, 68), 'Owner-authorized side fragments only. No newly drawn strokes; other panel pixels stay unchanged.', font=font(20), fill='#332428')
    for index, (panel, box) in enumerate(RECTANGLES.items()):
        source_crop = np.array(Image.open(p.SOURCE / f'{panel}.png').convert('RGB'))
        raw_crop = np.array(raw.crop(geometry[panel]['box_px']))
        if raw_crop.shape != source_crop.shape:
            raise AssertionError('raw crop no longer shares pinned panel coordinates')
        raw_plate = p.lid.upscale(raw_crop)
        before_path = out / 'cleaning' / f'{panel}-after.png'
        before = np.array(Image.open(before_path).convert('RGB'))
        x0, y0, x1, y1 = box
        core = np.zeros(before.shape[:2], bool)
        core[2*y0:2*y1, 2*x0:2*x1] = True
        distance = distance_transform_edt(~core)
        alpha = np.clip(1 - distance / (HALO_SOURCE_PX * 2), 0, 1)
        alpha[core] = 1
        after = np.rint(before * (1 - alpha[..., None]) + raw_plate * alpha[..., None]).astype('uint8')
        changed = np.any(after != before, axis=2)
        outside = alpha == 0
        if not np.array_equal(after[outside], before[outside]):
            raise AssertionError('repair escaped authorized local support')
        if not np.array_equal(after[core], raw_plate[core]):
            raise AssertionError('rectangle does not recover raw pixels exactly')
        folder = out / 'repair'
        for suffix, image in [('before', before), ('after', after), ('mask', changed * 255),
                              ('core-mask', core * 255), ('blend-alpha', np.rint(alpha * 255)), ('raw-recovery-source', raw_plate)]:
            p.save(folder / f'{panel}-{suffix}.png', image)
        intended_source = source_crop[y0:y1, x0:x1]
        behind = raw_crop[y0:y1, x0:x1]
        source_difference = np.any(intended_source != behind, axis=2)
        protected = np.array(Image.open(out / 'cleaning' / f'{panel}-protected-ink.png')) > 0
        reports[panel] = {'authorized_source_rectangle_px': list(box),
                          'source_rectangle_pixels': int(source_difference.size),
                          'source_rectangle_differing_from_raw_pixels': int(source_difference.sum()),
                          'raw_sheet_crop_box_px': geometry[panel]['box_px'],
                          'raw_sheet_recovered_rectangle_px': [geometry[panel]['box_px'][0] + x0, geometry[panel]['box_px'][1] + y0,
                                                              geometry[panel]['box_px'][0] + x1, geometry[panel]['box_px'][1] + y1],
                          'raw_crop_matches_panel_geometry': True,
                          'before': f'repair/{panel}-before.png', 'after': f'repair/{panel}-after.png',
                          'mask': f'repair/{panel}-mask.png', 'core_mask': f'repair/{panel}-core-mask.png',
                          'blend_alpha': f'repair/{panel}-blend-alpha.png',
                          'before_sha256': p.lid.sha256(before_path), 'after_sha256': p.lid.sha256(folder / f'{panel}-after.png'),
                          'changed_pixels_2x': int(changed.sum()), 'total_panel_pixels_2x': int(changed.size),
                          'changed_share_of_panel': float(changed.mean()),
                          'recovered_core_pixels_2x': int(core.sum()),
                          'boundary_blended_changed_pixels_2x': int((changed & ~core).sum()),
                          'formerly_protected_paint_pixels_changed_under_new_ruling': int((changed & protected).sum()),
                          'raw_exact_inside_rectangle': True, 'outside_local_support_byte_identical': True,
                          'halo_source_px': HALO_SOURCE_PX,
                          'method': 'Original raw panel sampled at the same coordinates, exactly2×INTER_LANCZOS4. Rectangle core copied exactly; 4sourcepixel halo blends existing raw into the cleaned plate to absorb interpolation/cleaning edges.',
                          'newly_drawn_or_generated_strokes': 0,
                          'meaning': 'This restores already-existing paint hidden by the protected-fork paste. It intentionally supersedes preservation of the mistaken pasted fragment only in this local region.'}
        for column, (title, image) in enumerate([('before', before), ('recovered raw paint', after), ('changed area', np.repeat((changed * 255)[..., None], 3, axis=2).astype('uint8'))]):
            x = 30 + index * 740 + column * 235
            tile = Image.fromarray(image)
            tile.thumbnail((210, 760), Image.Resampling.LANCZOS)
            draw.text((x, 125), panel + ' / ' + title, font=font(16), fill='#332428')
            proof.paste(tile, (x, 158))
    p.save(out / 'repair/side-repair-proof.png', np.array(proof))
    report = {'schema': 'hayat_local_side_recovery/1', 'authority': 'D-R1B-7 / owner screenshot clarification',
              'raw_source': str(raw_path.relative_to(p.REPO)), 'raw_sha256': RAW_SHA256,
              'scope': 'side_left and side_right pasted-fork rectangles only',
              'source_and_exact_upscale_plates_unchanged': True,
              'fidelity_scope': 'fidelity.json remains the exact2× proof of pinned D1/A panels; this separately disclosed local repair is not claimed pixel-identical to the pasted fork.',
              'paid_calls': 0, 'newly_drawn_strokes': 0, 'panels': reports,
              'proof': 'repair/side-repair-proof.png',
              'visual_status': 'Prepared for builder visual inspection before downstream carton rebuild.'}
    p.write_json(out / 'repair/repair.json', report)
    return report


if __name__ == '__main__':
    build()
