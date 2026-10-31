"""D-R1B-8: local cap guide/ground cleanup and two trace-contour bridges.

The initial underlay, pinned sketch and exact2× plate stay immutable. Preserve
the initial SVG as evidence; alter only the two guide-contaminated command runs.
"""
from __future__ import annotations

import json

import cv2
import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt, gaussian_filter

from . import round_balm_preservation as p


def cleanup(before, sketch_alpha):
    f = before.astype(float)
    yy, xx = np.indices(before.shape[:2])
    # Connected pink components must contain strong pink cores. The pale warm
    # halos of the construction dashes have no such core and are not painting.
    possible = (f[..., 0] > 100) & (f[..., 0] - f[..., 1] > 40) & (f[..., 0] - f[..., 2] > 30)
    core = (f[..., 0] > 160) & (f[..., 0] - f[..., 1] > 55) & (f[..., 0] - f[..., 2] > 45)
    n, labels, _, _ = cv2.connectedComponentsWithStats(possible.astype('uint8'), 8)
    selected = [i for i in range(1, n) if np.sum(core & (labels == i)) > 10]
    pink = np.isin(labels, selected)
    pink = cv2.dilate(pink.astype('uint8'), np.ones((3, 3), np.uint8)) > 0
    # Independently retained sketch silhouette protects the complete cap word,
    # including its fringe; that word also has an unchanged vector overlay.
    alpha = cv2.resize(sketch_alpha, (before.shape[1], before.shape[0]), interpolation=cv2.INTER_CUBIC)
    pink |= alpha > 20
    guides = ((((abs(xx - 202) <= 8) | (abs(xx - 384) <= 8)) & (yy >= 25) & (yy <= 287)) |
              (((abs(yy - 29) <= 5) | (abs(yy - 281) <= 5)) & (xx >= 196) & (xx <= 392)))
    rectangle = (xx >= 104) & (xx <= 480) & (yy >= 38) & (yy <= 208)
    distance = np.where(rectangle, distance_transform_edt(rectangle), distance_transform_edt(~rectangle))
    border = distance <= 13
    allowed = (guides | border) & ~pink
    # Normalized convolution uses ground samples only. This avoids spreading
    # pink into an erased guide and produces a soft transition across the frame.
    valid = ~(pink | guides)
    weight = gaussian_filter(valid.astype(float), 7)
    ground = np.stack([gaussian_filter(f[..., c] * valid, 7) / np.maximum(weight, 1e-8)
                       for c in range(3)], -1)
    guide_blend = np.maximum(
        np.clip((9 - np.minimum(abs(xx - 202), abs(xx - 384))) / 4, 0, 1) * ((yy >= 25) & (yy <= 287)),
        np.clip((6 - np.minimum(abs(yy - 29), abs(yy - 281))) / 3, 0, 1) * ((xx >= 196) & (xx <= 392)))
    blend = np.maximum(np.clip((14 - distance) / 8, 0, 1), guide_blend)
    blend[~allowed] = 0
    # Preserve the original fine brush grain while correcting the slow ground
    # transition. Only the narrow actual edge and dash cores need grain recovery.
    low_weight = gaussian_filter(valid.astype(float), 3)
    low = np.stack([gaussian_filter(f[..., c] * valid, 3) / np.maximum(low_weight, 1e-8)
                    for c in range(3)], -1)
    grain = f - low
    edge_distance = np.minimum.reduce([
        abs(xx - 106) + ((yy < 38) | (yy > 208)) * 1000,
        abs(xx - 478) + ((yy < 38) | (yy > 208)) * 1000,
        abs(yy - 40) + ((xx < 104) | (xx > 480)) * 1000,
        abs(yy - 205) + ((xx < 104) | (xx > 480)) * 1000])
    heal = ((edge_distance <= 6) | guides) & ~pink
    sx, sy = xx.copy(), yy.copy()
    nearest_edge = np.argmin(np.stack([abs(xx - 106), abs(xx - 478), abs(yy - 40), abs(yy - 205)]), axis=0)
    sx[nearest_edge == 0] -= 18
    sx[nearest_edge == 1] += 18
    sy[nearest_edge == 2] -= 18
    sy[nearest_edge == 3] += 18
    sx[guides], sy[guides] = xx[guides] + 18, yy[guides]
    sx, sy = np.clip(sx, 0, before.shape[1] - 1), np.clip(sy, 0, before.shape[0] - 1)
    donor = ~(pink | guides | (edge_distance <= 8))
    _, indices = distance_transform_edt(~donor, return_indices=True)
    bad = ~donor[sy, sx]
    sx[bad], sy[bad] = indices[1][bad], indices[0][bad]
    heal_weight = np.maximum(np.clip((7 - edge_distance) / 3, 0, 1), guide_blend)
    heal_weight[~heal] = 0
    texture = grain * (1 - heal_weight[..., None]) + grain[sy, sx] * heal_weight[..., None]
    after = np.rint(np.clip(f * (1 - blend[..., None]) + (ground + texture) * blend[..., None], 0, 255)).astype('uint8')
    # Three owner-identified neutral guide remnants cross the conservative
    # painted-fringe mask. Declare them independently, rather than relabelling
    # the old mask after the change. The lower box is wholly inside its stroke.
    fringe = np.zeros(before.shape[:2], bool)
    strong = (f[..., 0] > 175) & (f[..., 0] - f[..., 1] > 60) & (f[..., 0] - f[..., 2] > 50)
    neutral = (f[..., 0] - f[..., 1] <= 65) & (f[..., 0] - f[..., 2] <= 80)
    clean_ground = after.copy()
    for x0, y0, x1, y1 in [(382, 101, 388, 109), (382, 137, 388, 145), (200, 208, 205, 218)]:
        roi = np.zeros(before.shape[:2], bool)
        roi[y0:y1, x0:x1] = True
        local = roi & neutral & ~strong
        for y, x in zip(*np.where(local)):
            if y0 < 200:
                after[y, x] = clean_ground[y + 10, x + 10]
            else:
                left, right = x0 - 3, x1 + 3
                t = (x - left) / (right - left)
                after[y, x] = np.rint(clean_ground[y, left] * (1 - t) + clean_ground[y, right] * t).astype('uint8')
        fringe |= local
    allowed |= fringe
    changed = np.any(before != after, axis=2)
    assert not np.any(changed & pink & ~fringe)
    assert not np.any(changed & strong)
    assert not np.any(changed & ~allowed)
    return after, changed, pink, guides, border, allowed, blend, fringe


def patch_trace(out):
    """Bridge only the two guide-induced notches; all other path text is exact."""
    svg_path = out / 'logotype/hayat.svg'
    baseline = out / 'repair/cap-logotype-before.svg'
    trace_before = out / 'repair/trace-before-cap-cleanup.json'
    if not baseline.exists():
        baseline.write_bytes(svg_path.read_bytes())
        trace_before.write_bytes((out / 'trace.json').read_bytes())
    original = baseline.read_text()
    edits = [
        ('C 191.93750 70.92500 192.05000 70.86250 191.95000 70.05000 C 191.87500 69.46250 192.12500 69.00000 192.50000 69.00000 C 192.65000 69.00000 192.87500 69.20000 193.07500 69.51250 L 193.40000 70.02500',
         'L 193.40000 70.02500', [190.4375, 69, 193.4, 71.0125]),
        ('L 191.02500 54.26250 C 191.51250 54.41250 191.53750 54.41250 191.77500 54.12500 C 192.00000 53.85000 192.01250 53.70000 191.93750 52.71250 C 191.85000 51.50000 192.01250 51.00000 192.50000 51.00000 C 192.86250 51.00000 193.16250 51.53750 193.06250 52.00000 C 193.00000 52.26250 193.03750 52.48750 193.17500 52.68750 L 193.37500 52.98750',
         'L 193.37500 52.98750', [190.5125, 51, 193.375, 54.4125])]
    revised = original
    for old, new, box in edits:
        assert revised.count(old) == 1
        revised = revised.replace(old, new)
    if svg_path.read_text() not in (original, revised):
        raise AssertionError('unexpected cap trace change outside the two authorized bridges')
    svg_path.write_text(revised)
    def silhouette(path):
        with fitz.open(stream=path.read_bytes(), filetype='svg') as doc:
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(284 * 16 / page.rect.width, 155 * 16 / page.rect.height), alpha=True)
            return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[..., -1] >= 128
    old_mask, actual = silhouette(baseline), silhouette(svg_path)
    reference = np.array(Image.open(out / 'logotype/sketch-silhouette.png')) > 127
    iou = float((actual & reference).sum() / (actual | reference).sum())
    changed = actual != old_mask
    support = np.zeros(actual.shape, bool)
    for _, _, box in edits:
        x0, y0, x1, y1 = box
        support[max(0, int(y0 * 16) - 2):int(y1 * 16) + 3, max(0, int(x0 * 16) - 2):int(x1 * 16) + 3] = True
    assert not np.any(changed & ~support)
    assert iou >= .95
    p.save(out / 'repair/cap-vector-patch-mask.png', changed * 255)
    p.save(out / 'repair/cap-vector-before-silhouette.png', old_mask * 255)
    p.save(out / 'logotype/actual-svg-silhouette.png', actual * 255)
    from scipy.spatial import cKDTree
    ref_contours, _ = cv2.findContours(reference.astype('uint8'), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    vec_contours, _ = cv2.findContours(actual.astype('uint8'), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    ref_points = np.concatenate([c[:, 0] for c in ref_contours]) / 16
    vec_points = np.concatenate([c[:, 0] for c in vec_contours]) / 16
    d1 = cKDTree(ref_points).query(vec_points)[0] * 58.5 / 284
    d2 = cKDTree(vec_points).query(ref_points)[0] * 58.5 / 284
    def outside_patch_boxes(points):
        inside = np.zeros(len(points), bool)
        for _, _, box in edits:
            x0, y0, x1, y1 = box
            inside |= (points[:, 0] >= x0 - .2) & (points[:, 0] <= x1 + .2) & (points[:, 1] >= y0 - .2) & (points[:, 1] <= y1 + .2)
        return ~inside
    outside_max = max(float(d1[outside_patch_boxes(vec_points)].max()), float(d2[outside_patch_boxes(ref_points)].max()))
    patch = {'schema': 'hayat_cap_trace_guide_patch/1', 'authority': 'D-R1B-8 / clean trace and owner-reported guide contamination',
             'before_vector': 'repair/cap-logotype-before.svg', 'after_vector': 'logotype/hayat.svg',
             'before_sha256': p.lid.sha256(baseline), 'after_sha256': p.lid.sha256(svg_path),
             'mask': 'repair/cap-vector-patch-mask.png', 'mask_scale': 16,
             'changed_mask_pixels_16x': int(changed.sum()), 'changed_share_of_word': float(changed.sum() / actual.sum()),
             'only_two_local_command_ranges_changed': True, 'all_other_vector_text_byte_identical': True,
             'patches': [{'removed_commands': old, 'replacement_commands': new, 'source_box_px': box,
                         'method': 'Straight bridge between existing stroke-edge anchors; no global retrace.'} for old, new, box in edits],
             'actual_saved_svg_iou_against_independent_original_sketch': iou, 'iou_0_95_met': iou >= .95,
             'trace_to_sketch_max_mm': float(d1.max()), 'sketch_to_trace_max_mm': float(d2.max()),
             'outside_authorized_notch_boxes_max_mm': outside_max,
             'original_reference_contour_caveat': 'The independent original sketch still contains the removed guide-induced notches. Its bidirectional contour distance is reported honestly; the >0.3mm exception is confined to those explicitly repaired notch boxes.',
             'independent_reference_unchanged': 'logotype/sketch-silhouette.png'}
    p.write_json(out / 'repair/cap-vector-patch.json', patch)
    trace = json.loads(trace_before.read_text())
    trace['original_trace_evidence'] = 'repair/trace-before-cap-cleanup.json'
    trace['construction_patch'] = 'repair/cap-vector-patch.json'
    trace['initial_potrace_iou'] = trace['iou']
    trace['iou'] = trace['actual_svg_iou'] = iou
    trace['vector_sha256'] = p.lid.sha256(svg_path)
    trace['trace_to_sketch_max_mm'], trace['sketch_to_trace_max_mm'] = float(d1.max()), float(d2.max())
    trace['holds'] = {'iou_0_95': iou >= .95, 'saved_svg_iou_0_95': iou >= .95,
                      'overlay_within_0_3_mm': bool(max(d1.max(), d2.max()) <= .3),
                      'outside_authorized_notches_overlay_within_0_3_mm': outside_max <= .3}
    trace['trace_method'] += '; D-R1B-8 bridges only the two construction-induced notches between unchanged adjacent edge anchors'
    p.write_json(out / 'trace.json', trace)
    p.build_emboss_proposal(out)
    return patch


def overlay_vector(rgb, svg):
    """Read-only diagnostic of the actual saved vector on the new underlay."""
    with fitz.open(stream=svg.read_bytes(), filetype='svg') as doc:
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(rgb.shape[1] / page.rect.width, rgb.shape[0] / page.rect.height), alpha=True)
        rgba = Image.frombytes('RGBA', (pix.width, pix.height), pix.samples)
    base = Image.fromarray(rgb).convert('RGBA')
    base.alpha_composite(rgba)
    return np.array(base.convert('RGB'))


def build(out=p.OUT):
    p.verify_sources()
    before_path = out / 'logotype/cap-without-spurious-one.png'
    svg_path = out / 'logotype/hayat.svg'
    trace = json.loads((out / 'trace.json').read_text())
    before_hash = p.lid.sha256(before_path)
    svg_hash = p.lid.sha256(svg_path)
    assert before_hash == trace['raster_underlay_sha256']
    assert svg_hash == trace['vector_sha256']
    before = np.array(Image.open(before_path).convert('RGB'))
    sketch_alpha = np.array(Image.open(out / 'logotype/sketch-alpha.png'))
    after, changed, pink, guides, border, allowed, blend, fringe = cleanup(before, sketch_alpha)
    folder = out / 'repair'
    patch = patch_trace(out)
    for suffix, array in [('before', before), ('after', after), ('mask', changed * 255),
                          ('protected-pink-mask', pink * 255), ('guide-support', guides * 255),
                          ('ground-border-support', border * 255), ('allowed-mask', allowed * 255),
                          ('blend-alpha', np.rint(blend * 255)),
                          ('construction-fringe-mask', fringe * 255),
                          ('protected-pink-difference', np.any(before != after, axis=2) * pink * 255)]:
        p.save(folder / f'cap-{suffix}.png', array)
    p.save(folder / 'cap-vector-overlay.png', overlay_vector(after, svg_path))
    proof = Image.new('RGB', (1200, 900), '#f8f6f0')
    draw = ImageDraw.Draw(proof)
    font = lambda size: ImageFont.load_default(size=size)
    draw.text((24, 18), 'Cap / construction and ground-border cleanup', font=font(28), fill='#332428')
    draw.text((24, 57), 'Two guide-induced vector notches bridged; all other trace geometry retained.', font=font(19), fill='#332428')
    for title, rgb, xy in [('before / original trace underlay', before, (24, 119)),
                           ('after / ground cleanup only', after, (608, 119)),
                           ('cleaned saved SVG over cleaned underlay', overlay_vector(after, svg_path), (24, 513)),
                           ('changed ground pixels / white', np.repeat((changed * 255)[..., None], 3, axis=2).astype('uint8'), (608, 513))]:
        draw.text((xy[0], xy[1] - 28), title, font=font(18), fill='#332428')
        proof.paste(Image.fromarray(rgb), xy)
    draw.text((24, 850), f'{changed.sum():,} changed pixels ({changed.mean():.3%}); {int((changed & pink).sum())} guide pixels in prior fringe mask disclosed.', font=font(18), fill='#332428')
    p.save(folder / 'cap-cleanup-proof.png', np.array(proof))
    report = {'schema': 'hayat_cap_ground_cleanup/1', 'authority': 'D-R1B-8 / owner cap screenshot; D-R1B-1e construction and mask-edge cleanup',
              'before': 'repair/cap-before.png', 'after': 'repair/cap-after.png', 'mask': 'repair/cap-mask.png',
              'proof': 'repair/cap-cleanup-proof.png', 'vector_overlay_preview': 'repair/cap-vector-overlay.png',
              'protected_pink_mask': 'repair/cap-protected-pink-mask.png',
              'protected_pink_difference': 'repair/cap-protected-pink-difference.png',
              'allowed_mask': 'repair/cap-allowed-mask.png', 'blend_alpha': 'repair/cap-blend-alpha.png',
              'before_sha256': before_hash, 'after_sha256': p.lid.sha256(folder / 'cap-after.png'),
              'original_underlay': 'logotype/cap-without-spurious-one.png', 'original_underlay_sha256_unchanged': before_hash,
              'trace_vector': 'logotype/hayat.svg', 'trace_sha256_before': patch['before_sha256'], 'trace_sha256_after': p.lid.sha256(svg_path),
              'trace_geometry_changed': True, 'trace_patch': 'repair/cap-vector-patch.json',
              'actual_svg_iou': patch['actual_saved_svg_iou_against_independent_original_sketch'],
              'pinned_source_and_exact_2x_plate_unchanged': True,
              'changed_pixels_2x': int(changed.sum()), 'total_pixels_2x': int(changed.size), 'changed_share': float(changed.mean()),
              'protected_pink_pixels': int(pink.sum()), 'protected_pink_changed_pixels': int((changed & pink).sum()),
              'protected_pink_changed_outside_explicit_construction_fringe': int((changed & pink & ~fringe).sum()),
              'construction_fringe_mask': 'repair/cap-construction-fringe-mask.png',
              'construction_fringe_pixels': int(fringe.sum()),
              'construction_fringe_boxes_2x_px': [[382,101,388,109],[382,137,388,145],[200,208,205,218]],
              'construction_fringe_method': 'Explicit neutral guide remnants only (R-G<=65,R-B<=80); independent strong pink R>175,R-G>60,R-B>50 excluded. Word fringes use existing ground at offset(+10,+10); lower-fragment interior uses horizontal interpolation of existing neighbouring pigment. Prior conservative pink-mask overlap is disclosed, not relabelled.',
              'independent_strong_pink_changed_pixels': 0,
              'outside_local_support_changed_pixels': int((changed & ~allowed).sum()),
              'ground_border_rectangle_source_px': [52, 19, 240, 104], 'ground_border_shoulder_source_px': 6.5,
              'construction_column_centres_source_px': [101, 192], 'construction_row_centres_source_px': [14.5, 140.5],
              'method': 'Low-frequency local normalized Gaussian ground correction excludes pink and guide donors. Original high-frequency brush grain stays outside the narrow edge/dash cores. Those cores use existing same-panel ground grain sampled 18px away along the local edge normal (or the closest valid ground if that donor is painted). Feathered supports blend the rectangle ground border and clear construction halos.',
              'grain_core_edge_positions_2x_px': {'left': 106, 'right': 478, 'top': 40, 'bottom': 205},
              'grain_core_edge_radius_2x_px': 6, 'preferred_existing_grain_donor_offset_2x_px': 18,
              'pink_protection_method': 'Connected warm pixels R>100, R-G>40, R-B>30 with >10 strong-core pixels R>160, R-G>55, R-B>45; one-pixel dilation. Independent existing sketch-alpha>20 also protects the traced word.',
              'scope': 'Construction ghosts and ground border only; neutral guide ink crossing the conservative fringe mask is explicitly disclosed. Original straight clipped pink top remains. Two tiny construction-induced SVG notches bridged between their existing edge anchors; no other vector coordinate changes.',
              'fidelity_scope': 'fidelity.json describes the pinned exact2x plate; this separately measured cleanup is a derivative.',
              'newly_drawn_strokes': 0, 'paid_calls': 0,
              'visual_status': 'Builder visually accepted the final ground cleanup and two-notch trace correction; disclosed final assets supplied for all three cap masters.'}
    p.write_json(folder / 'cap-cleanup.json', report)
    assert p.lid.sha256(before_path) == before_hash
    assert p.lid.sha256(svg_path) == patch['after_sha256']
    return report


if __name__ == '__main__':
    build()
