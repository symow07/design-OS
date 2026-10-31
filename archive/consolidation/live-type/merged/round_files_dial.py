"""Live type placed from a drawn dial's own geometry (owner, 2026-10-28): each shade label centred on its own colour
band (found by the shade's colour in the drawn face, never from the photograph's boxes), and the brand and "ملمع شفاه"
along the free navy ring only, never over a band, the brand upright. Nothing is erased; the face is read, not changed.

Coordinates are the face picture's pixels (its bleed included); the caller divides by the template's px/mm."""
from __future__ import annotations

import math

import cv2
import numpy as np

from . import lid_master as lm

NAVY_HEX = '#1B2B4B'                              # a seed only: the drawn navy is read as the face's own dark ground
GOLD_HEX = '#D5AF59'
BAND_DE = 22.0                                    # a pixel belongs to a shade's band within ΔE00 22 of its seed …
BAND_OPEN_PX = 5                                  # … the band's thin gold rules and ticks opened away
BAND_PIECE_SHARE = 0.15                           # … every piece of it at least 15 % of its largest kept
LABEL_SHARE = 0.62                                # a label block stands in 62 % of its band's thickness …
LABEL_WIDTH_SHARE = 0.82                          # … and 82 % of the free width it is centred in
LINE_GAP_EM = 0.28                                # the Latin name over the Arabic, 0.28 em apart
RING_NAVY, RING_GOLD = 0.85, 0.03                 # a free ring: ≥ 85 % navy and ≤ 3 % gold at its radius
RING_MIN_MM = 2.5                                 # … at least 2.5 mm wide
RING_LETTER_SHARE = 0.62                          # the ring's letters fill 62 % of its width
OUTSIDE_GAP_MM, OUTSIDE_WIDTH_MM = 0.8, 6.0       # with no plain ring drawn: 0.8 mm outside the rim, 6 mm wide
RIM_GOLD, RIM_REACH_PX = 0.08, 8                # the ring is inside the gold rim: ≥ 8 % gold within 8 px beyond it
MIN_PT = 5.0


def _lab_of_hex(hex_):
    rgb = np.array([[[int(hex_.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]]], np.uint8)
    return lm.srgb_to_lab(rgb)[0, 0]


def gold_of(lab):
    """The drawn gold: bright and yellow (b* over 22, L* over 50, a* under 25), grown 1 px so a thin anti-aliased
    tick or rule is seen."""
    gold = (lab[..., 2] > 22) & (lab[..., 0] > 50) & (lab[..., 1] < 25)
    return cv2.dilate(gold.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0


def navy_of(lab):
    """The face's own navy: within ΔE00 15 of the median of its dark bluish pixels."""
    dark = (lab[..., 0] < 32) & (lab[..., 2] < -4)
    seed = np.median(lab[dark], axis=0) if dark.sum() > 100 else _lab_of_hex(NAVY_HEX)
    return lm.delta_e00(lab, np.broadcast_to(seed, lab.shape)) < 15


def band_masks(rgb, shades, seed=7):
    """Each shade's band in the drawn face: the face's own colours clustered (k-means on the coloured pixels, neither
    navy nor gold), each cluster matched to the shade whose brief colour it is nearest (the matching with the least
    total ΔE00), opened, its sizeable pieces. A drawn colour is matched, never assumed to be the brief's hex."""
    from itertools import permutations
    lab = lm.srgb_to_lab(rgb)
    gold, navy = gold_of(lab), navy_of(lab)
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    coloured = ~gold & ~navy & (chroma > 12)
    points = lab[coloured].astype(np.float32)
    out = {field: np.zeros(rgb.shape[:2], bool) for field, _hex in shades}
    if len(points) < 100 * len(shades):
        return out, {'clusters': 0}
    rng = np.random.default_rng(seed)
    sample = points[rng.choice(len(points), min(len(points), 30000), replace=False)]
    cv2.setRNGSeed(seed)
    _c, _labels, centres = cv2.kmeans(sample, len(shades), None,
                                      (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.2), 5, cv2.KMEANS_PP_CENTERS)
    targets = [_lab_of_hex(hex_) for _field, hex_ in shades]
    cost = np.array([[float(lm.delta_e00(centre[None, None, :], target[None, None, :])[0, 0]) for target in targets]
                     for centre in centres])
    match = min(permutations(range(len(shades))), key=lambda order: sum(cost[i, j] for i, j in enumerate(order)))
    distances = np.stack([lm.delta_e00(lab, np.broadcast_to(centre, lab.shape)) for centre in centres])
    nearest = distances.argmin(axis=0)
    record = {'clusters': len(centres)}
    for cluster, shade in enumerate(match):
        field = shades[shade][0]
        mask = (coloured & (nearest == cluster) & (distances[cluster] < BAND_DE)).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((BAND_OPEN_PX,) * 2, np.uint8))
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        if n > 1:
            # the needle may cut a band in two: every piece of at least 15 % of its largest is the band
            areas = stats[1:, cv2.CC_STAT_AREA]
            keep = 1 + np.flatnonzero(areas >= BAND_PIECE_SHARE * areas.max())
            out[field] = np.isin(labels, keep)
        record[field] = {'drawn_lab': [round(float(v), 1) for v in centres[cluster]],
                         'delta_e00_to_brief': round(cost[cluster, shade], 1)}
    return out, record


def _circle(p):
    (x1, y1), (x2, y2), (x3, y3) = p
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-9:
        return None
    ux = ((x1 * x1 + y1 * y1) * (y2 - y3) + (x2 * x2 + y2 * y2) * (y3 - y1) + (x3 * x3 + y3 * y3) * (y1 - y2)) / d
    uy = ((x1 * x1 + y1 * y1) * (x3 - x2) + (x2 * x2 + y2 * y2) * (x1 - x3) + (x3 * x3 + y3 * y3) * (x2 - x1)) / d
    return ux, uy


def dial_centre(masks, seed=7):
    """The dial's centre: the bands' arcs are concentric, so a circle fitted (RANSAC, then least squares on its
    inliers) to their edges — a band's straight edges where the face cuts it are outliers."""
    points = []
    for mask in masks.values():
        if mask.any():
            contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            points += [c.reshape(-1, 2) for c in contours]
    pts = np.concatenate(points).astype(float)
    h, w = masks[next(iter(masks))].shape
    inside = (pts[:, 0] > 2) & (pts[:, 0] < w - 3) & (pts[:, 1] > 2) & (pts[:, 1] < h - 3)
    pts = pts[inside]
    rng = np.random.default_rng(seed)
    best, best_n = None, 0
    for _ in range(400):
        centre = _circle(pts[rng.choice(len(pts), 3, replace=False)])
        if centre is None:
            continue
        r = np.hypot(pts[:, 0] - centre[0], pts[:, 1] - centre[1])
        # one arc's inliers: the radius at which the most points agree
        hist, edges = np.histogram(r, bins=np.arange(0, r.max() + 3, 2.0))
        n = int(hist.max())
        if n > best_n:
            best, best_n = centre, n
    r = np.hypot(pts[:, 0] - best[0], pts[:, 1] - best[1])
    hist, edges = np.histogram(r, bins=np.arange(0, r.max() + 3, 2.0))
    radius = edges[int(hist.argmax())] + 1.0
    arc = pts[np.abs(r - radius) < 3.0]
    a = np.column_stack([2 * arc[:, 0], 2 * arc[:, 1], np.ones(len(arc))])
    b = arc[:, 0] ** 2 + arc[:, 1] ** 2
    cx, cy, _c = np.linalg.lstsq(a, b, rcond=None)[0]
    return float(cx), float(cy)


def _metric(copy, face):
    from .round_balm_master import glyph_metrics
    return glyph_metrics(copy, face)


def _face_for(copy):
    from .round_files_ornament import face_for
    return face_for(copy)


def label_windows(mask, block_h):
    """The widest horizontal window in which a block ``block_h`` px tall stands wholly inside the band: (width, y, x0,
    x1), or None."""
    h, w = mask.shape
    if block_h < 2 or block_h >= h:
        return None
    cs = np.vstack([np.zeros((1, w), np.int32), np.cumsum(mask.astype(np.int32), axis=0)])
    ok = (cs[block_h:] - cs[:-block_h]) == block_h
    best = None
    for y in range(ok.shape[0]):
        row = np.concatenate([[0], ok[y].astype(np.int8), [0]])
        edges = np.flatnonzero(np.diff(row))
        if not len(edges):
            continue
        starts, ends = edges[0::2], edges[1::2]
        i = int(np.argmax(ends - starts))
        if best is None or ends[i] - starts[i] > best[0]:
            best = (int(ends[i] - starts[i]), y, int(starts[i]), int(ends[i]))
    return best


def shade_labels(rgb, k, brief, fields, *, colour, safe_px):
    """Each shade's Latin name over its Arabic name, centred on its own band where the band runs widest and level."""
    from .round_files_export import PT
    shades = [('shade_%d' % i, shade['hex']) for i, shade in enumerate(brief['shades'])]
    masks, matched = band_masks(rgb, shades)
    x0s, y0s, x1s, y1s = safe_px
    rows, record, blocks = [], {}, []
    for i, shade in enumerate(brief['shades']):
        field = 'shade_%d' % i
        mask = masks[field].copy()
        mask[:, :x0s] = mask[:, x1s:] = False
        mask[:y0s] = mask[y1s:] = False
        if mask.sum() < 50:
            record[field] = {'placed': False, 'why': 'its band was not found in the drawn face'}
            continue
        thickness = 2 * float(cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5).max())
        lines = [(fields[field], 'latin')]
        if fields.get('arabic_' + field):
            lines.append((fields['arabic_' + field], 'arabic'))
        metrics = [_metric(copy, face) for copy, face in lines]
        ink = [m['box_em'][3] - m['box_em'][1] for m in metrics]
        block_em = sum(ink) + LINE_GAP_EM * (len(lines) - 1)
        block_h = int(thickness * LABEL_SHARE)
        window = label_windows(mask, block_h)
        if window is None:
            record[field] = {'placed': False, 'why': 'its band has no room for a label'}
            continue
        width, y, xa, xb = window
        size_px = min(block_h / block_em, width * LABEL_WIDTH_SHARE / max(m['advance_em'] for m in metrics))
        blocks.append((field, lines, metrics, ink, block_em, (xa + xb) / 2.0, y + block_h / 2.0, size_px))
        record[field] = {'placed': True, 'band_px': int(masks[field].sum()), 'thickness_px': round(thickness, 1),
                         'centre_px': [round((xa + xb) / 2.0, 1), round(y + block_h / 2, 1)]}
    # the labels are one set: every one at the size the tightest band allows
    size_px = min((block[-1] for block in blocks), default=0.0)
    for field, lines, metrics, ink, block_em, cx, cy, _own in blocks:
        top = cy - block_em * size_px / 2
        for (copy, face), metric, height in zip(lines, metrics, ink):
            rows.append({'name': 'header:' + ('arabic_' if face == 'arabic' else '') + field, 'copy': copy,
                         'face': face, 'center_mm': [cx / k, (top + height * size_px / 2) / k], 'angle_deg': 0.0,
                         'size_pt': max(MIN_PT, size_px / k * PT), 'color': colour, 'foil': False,
                         'copy_field': ('arabic_' if face == 'arabic' else '') + field})
            top += (height + LINE_GAP_EM) * size_px
        record[field]['size_pt'] = round(size_px / k * PT, 2)
    record['matched'] = matched
    return rows, masks, record


def free_ring(rgb, masks, shades, centre, safe_px):
    """The free navy runs outside the outermost band: the radii at which the face is ≥ 85 % navy and ≤ 3 % gold
    (clear of the tick scale), each with how much gold bounds it outward (the rim). Returns (candidates, the outermost
    band's radius), in px."""
    lab = lm.srgb_to_lab(rgb)
    gold_px, navy_px = gold_of(lab), navy_of(lab)
    h, w = gold_px.shape
    cx, cy = centre
    outer = max(float(np.percentile(np.hypot(*(np.argwhere(m)[:, ::-1] - (cx, cy)).T), 99)) for m in masks.values() if m.any())
    thetas = np.radians(np.arange(0, 360, 0.5))
    radii = np.arange(int(outer) + 2, int(math.hypot(w, h)) + 2)
    X = cx + radii[:, None] * np.cos(thetas)[None, :]
    Y = cy - radii[:, None] * np.sin(thetas)[None, :]
    x0s, y0s, x1s, y1s = safe_px
    valid = (X >= x0s) & (X < x1s) & (Y >= y0s) & (Y < y1s)
    xi, yi = np.clip(np.round(X).astype(int), 0, w - 1), np.clip(np.round(Y).astype(int), 0, h - 1)
    count = valid.sum(axis=1)
    navy = (navy_px[yi, xi] & valid).sum(axis=1) / np.maximum(count, 1)
    gold = (gold_px[yi, xi] & valid).sum(axis=1) / np.maximum(count, 1)
    free = (navy >= RING_NAVY) & (gold <= RING_GOLD) & (count >= 20)
    runs, start = [], None
    for i, flag in enumerate(np.append(free, False)):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            runs.append((start, i - 1))
            start = None
    candidates = []
    for a, b in runs:
        r_in, r_out = float(radii[a]), float(radii[b])
        rim = gold[b + 1:b + 1 + RIM_REACH_PX].max() if b + 1 < len(gold) else 0.0
        candidates.append({'r_in': r_in, 'r_out': r_out, 'width_px': r_out - r_in, 'rim_gold': round(float(rim), 3)})
    return candidates, outer


def ring_type(rgb, k, brief, fields, masks, *, colour, safe_px):
    """The brand upright where the free ring runs most nearly level, then "ملمع شفاه" along the rest of the ring
    (round_files_ornament.layout_runs), both on the navy ring only."""
    from .round_files_export import PT
    from .round_files_ornament import layout_runs
    shades = [('shade_%d' % i, shade['hex']) for i, shade in enumerate(brief['shades'])]
    centre = dial_centre(masks)
    candidates, outer = free_ring(rgb, masks, shades, centre, safe_px)
    ringed = [c for c in candidates if c['width_px'] >= RING_MIN_MM * k and c['rim_gold'] >= RIM_GOLD]
    record = {'centre_px': [round(centre[0], 1), round(centre[1], 1)], 'outer_band_px': round(outer, 1),
              'candidates': candidates}
    if ringed:
        ring = dict(max(ringed, key=lambda c: c['r_out']), kind='the free navy ring inside the rim')
    else:
        # no plain ring inside the rim was drawn: the navy just outside it, never a band (recorded for the eye)
        wide = [c for c in candidates if c['width_px'] >= RING_MIN_MM * k]
        if not wide:
            record.update(placed=False, why='no free navy ring at least %.1f mm wide was found in the drawn face'
                                            % RING_MIN_MM)
            return [], record
        first = min(wide, key=lambda c: c['r_in'])
        r_in = first['r_in'] + OUTSIDE_GAP_MM * k
        ring = {'r_in': r_in, 'r_out': min(first['r_out'], r_in + OUTSIDE_WIDTH_MM * k), 'rim_gold': first['rim_gold'],
                'kind': 'the navy just outside the gold rim (the drawn face has no plain ring inside it)'}
        ring['width_px'] = ring['r_out'] - ring['r_in']
    record['ring_kind'] = ring['kind']
    r_mid = (ring['r_in'] + ring['r_out']) / 2
    letters = ring['width_px'] * RING_LETTER_SHARE
    cx, cy = centre
    x0s, y0s, x1s, y1s = safe_px
    inside = [t for t in np.arange(180.0, -180.0, -0.25)
              if all(x0s <= cx + r * math.cos(math.radians(t)) < x1s and y0s <= cy - r * math.sin(math.radians(t)) < y1s
                     for r in (ring['r_in'], ring['r_out']))]
    if len(inside) < 8:
        record.update(placed=False, why='the free ring does not lie inside the safe area')
        return [], record
    # the longest run of consecutive angles inside, from the top of the arc down (the path's direction)
    spans, run = [], [inside[0]]
    for t in inside[1:]:
        if abs(run[-1] - t - 0.25) < 1e-6:
            run.append(t)
        else:
            spans.append(run)
            run = [t]
    spans.append(run)
    span = max(spans, key=len)
    brand = brief['copy']['brand']
    metric = _metric(brand, 'latin')
    ink = metric['box_em'][3] - metric['box_em'][1]
    # the brand upright where the ring is most nearly level (its tangent closest to horizontal): its corners on the ring
    level = min(span, key=lambda t: abs(abs(t) - 90))
    size_px = letters / ink
    rows = []
    for _ in range(40):
        advance = metric['advance_em'] * size_px
        corners_ok, at = False, None
        for t in sorted(span, key=lambda t: abs(t - level)):
            px, py = cx + r_mid * math.cos(math.radians(t)), cy - r_mid * math.sin(math.radians(t))
            box = [px + metric['box_em'][0] * size_px - advance / 2, py - ink * size_px / 2,
                   px + metric['box_em'][2] * size_px - advance / 2, py + ink * size_px / 2]
            corners = [(box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])]
            if all(ring['r_in'] <= math.hypot(x - cx, y - cy) <= ring['r_out'] and x0s <= x < x1s and y0s <= y < y1s
                   for x, y in corners):
                corners_ok, at = True, (t, px, py, advance)
                break
        if corners_ok or size_px / k * PT <= MIN_PT:
            break
        size_px *= 0.92
    if at is None:
        record.update(placed=False, why='the brand cannot stand upright on the ring at 5 pt or more')
        return [], record
    t_brand, px, py, advance = at
    rows.append({'name': 'header:ring:brand', 'copy': brand, 'face': 'latin', 'center_mm': [px / k, py / k],
                 'angle_deg': 0.0, 'size_pt': size_px / k * PT, 'color': colour, 'foil': False, 'copy_field': 'brand',
                 'ornament': True})
    # "ملمع شفاه" along the ring straight after the brand, on the longer side of it, at the brand's size
    brand_pt = size_px / k * PT
    half = math.degrees((advance / 2 + letters * 0.6) / r_mid)
    before = [t for t in span if t > t_brand + half]
    after = [t for t in span if t < t_brand - half]
    rest = max((before, after), key=len)
    record.update(placed=True, ring_px=[ring['r_in'], ring['r_out']], brand_angle_on_ring=round(t_brand, 2),
                  brand_size_pt=round(brand_pt, 2))
    phrase = fields.get('product_arabic')
    if len(rest) < 8 or not phrase:
        record['product_arabic'] = 'no room on the ring past the brand'
        return rows, record
    from .round_files_ornament import INK_SHARE, WORD_GAP_EM
    words = [_metric(word, 'arabic') for word in phrase.split()]
    top = max(m['box_em'][3] for m in words)
    bottom = min(m['box_em'][1] for m in words)
    length_px = (sum(m['advance_em'] for m in words) + WORD_GAP_EM * (len(words) - 1)) * size_px * 1.02
    sweep = math.degrees(length_px / r_mid)
    ordered = sorted(rest, reverse=rest is after)               # from the brand outward along the ring
    taken = [t for t in ordered if abs(t - ordered[0]) <= sweep]
    if abs(taken[-1] - taken[0]) < sweep * 0.98:
        record['product_arabic'] = 'no room on the ring past the brand at the brand\'s size'
        return rows, record
    h, w = rgb.shape[:2]
    path = [((cx + r_mid * math.cos(math.radians(t))) / w, (cy - r_mid * math.sin(math.radians(t))) / h)
            for t in sorted(taken, reverse=True)]
    height_px = size_px * (top - bottom) / INK_SHARE
    zone = {'path_norm': path, 'height_norm': height_px / h, 'color': colour,
            'copy': [{'field': 'product_arabic', 'copy': phrase, 'face': 'arabic'}]}
    runs, laid = layout_runs('header', 0, zone, [0.0, 0.0, w / k, h / k])
    rows.extend(dict(run, name='header:ring:' + run['name'].split(':', 2)[2]) for run in runs)
    record['product_arabic'] = laid
    return rows, record


def header_type(face_png, k, face, brief, fields, *, label_colour, ring_colour):
    """The header's live type from its drawn face: the shade labels on their bands, the brand and ملمع شفاه on the
    navy ring. Returns (rows in the upright frame's mm, record)."""
    from PIL import Image
    with Image.open(face_png) as image:
        rgb = np.asarray(image.convert('RGB'))
    b, s = face['bleed_mm'], face['safe_mm']
    safe_px = [int(math.ceil((b + s) * k)), int(math.ceil((b + s) * k)),
               int((b + face['w_mm'] - s) * k), int((b + face['h_mm'] - s) * k)]
    labels, masks, label_record = shade_labels(rgb, k, brief, fields, colour=label_colour, safe_px=safe_px)
    ring, ring_record = ring_type(rgb, k, brief, fields, masks, colour=ring_colour, safe_px=safe_px)
    return labels + ring, {'labels': label_record, 'ring': ring_record, 'px_per_mm': k,
                           'rule': 'placed from the drawn face: each label on its own colour band, the brand upright '
                                   'and ملمع شفاه on the free navy ring'}
