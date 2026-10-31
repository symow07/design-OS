"""Day 11 §3 — the lipstick's master by the preservation path (D-D11-7), at $0.

The pick is a sketch folder under ``docs/audit/day-11/lipstick/sketches/`` holding ``body.png`` and ``cap.png``, each
cropped at its trim (64.8 × 42 mm: the circumference π · 20 plus the overlap, by the visible 40 mm plus 1 mm bleed top
and bottom). Nothing here is hard-wired to one sketch's pixels: every window is found from the picture (the hero by its
painted hatch, the small Arabic word and the logotype as the solid rose gold above and below it, the small lines as the
cream rows under them, the cap's logo as the solid rose gold the stones surround).

The wraps are the sketch's own pixels made printable — nothing is redrawn. The allowed differences are D-D11-7's
(the lid's path, D-D11-3, carried to the lipstick) and they are measured here:

1. resolution — each wrap upscaled Lanczos 2× (``lid_master.upscale``), proved at the pick's size;
2. the safe area — nothing essential within 2 mm of the top and bottom edges, a breach moved by the least amount;
3. the seam — the wrap closes at the back, its right end over its left start; a 2 mm feathered band, proven by ΔE00
   along the join (σ 0.5 mm), mean ≤ 2 after treatment;
4. the hero شفاه with أحمر — traced (0.3 mm), the hatch an engine line system, its strokes the rose-gold foil within
   the press limits, the silhouette the relief; the sketch's raster stays beneath;
5. "Enchanted Rose" — the LID's traced logotype vector, scaled and placed, never re-traced (source hash + transform);
6. the small lines live in the lid's face, the ℮ the house's sign at the figures' height (≥ 3 mm);
7. the cap's logo — the approved vector in the lid's rose-gold ink;
8. the bottom label Ø 18 — composed by the engine in the lid's language.

The executor's modules are imported, never edited. Where one of their functions reads the lid's own scale (8.084 px/mm),
its windows or its 190 × 120 page, it is mirrored here at the wrap's scale ``k`` (px/mm) with its method and constants
unchanged, and its docstring names the original. Every function costs $0; the eye's look is passed a paid ``call`` and
is never run here (its pictures are proved by a dry pre-check whose stand-in call raises before anything is paid).
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import zilal_lipstick as zl
from apps.pipeline.services import zilal_master as zm
from apps.pipeline.services import zilal_object as zo

REPO = lm.REPO
SKETCHES = zl.SKETCHES
OUT = zl.LIP / 'master'
LID = zm.OUT                                     # the lid master's records and files (docs/audit/day-11/zilal/lid)
LID_NAME_LAYER = LID / 'engine' / 'layer-name.ai'    # the lid's traced "Enchanted Rose" rings, the logotype's source
SURFACE = 'apps/pipeline/services/zilal_lipstick_master.py::build'

WRAP_MM = zl.WRAP_MM                             # D-D11-7: 64.8 × 42 mm, each wrap
CIRCUMFERENCE_MM = float(np.pi * 20.0)           # the round case, Ø 20 mm (⟪PROVISIONAL⟫ facts)
OVERLAP_MM = WRAP_MM[0] - CIRCUMFERENCE_MM       # 1.968 mm: the right end lies over the left start by this much
BLEED_TB_MM = 1.0                                # D-D11-7: 1 mm bleed top and bottom, inside the 42 mm
SAFE_TB_MM = 2.0                                 # D-D11-7's sketch rule: nothing essential within 2 mm of top and bottom
SAFE_MARGIN_MM = zm.SAFE_MARGIN_MM               # a move lands 2 µm past the line (rounding never falls short)

# --- the picture: the trim, the ground, the inks -----------------------------------------------------------------------


def load_wrap(folder, name):
    """A wrap's pixels as the sketch round cropped them (``<folder>/<name>.png``), with its sha256."""
    path = Path(folder) / ('%s.png' % name)
    return np.asarray(Image.open(path).convert('RGB')), lm.sha256(path), path


def trim_rows(rgb):
    """The wrap at ONE scale, never stretched: ``k`` = its width over 64.8 mm (px/mm); the rows that make 42 mm at
    that scale kept, the excess cut evenly top and bottom (the sketch's aspect error is its own, at most 2 %; a
    shortfall is filled by the picture's own mirrored edge rows). Returns the picture and what was done."""
    h, w = rgb.shape[:2]
    k = w / WRAP_MM[0]
    rows = int(round(WRAP_MM[1] * k))
    cut = h - rows
    top = cut // 2
    if cut >= 0:
        out = rgb[top:top + rows]
        did = 'cut %d rows (%d top, %d bottom)' % (cut, top, cut - top)
    else:
        need = -cut
        out = cv2.copyMakeBorder(rgb, need // 2, need - need // 2, 0, 0, cv2.BORDER_REFLECT_101)
        did = 'filled %d rows by the picture\'s own mirrored edge rows' % need
    return out, {'px_per_mm': round(k, 5), 'sketch_px': [w, h], 'rows_kept': rows, 'rows_cut_top': max(top, 0),
                 'height_mm_at_k': round(rows / k, 4), 'did': did,
                 'aspect_of_the_sketch': round(w / h, 4), 'aspect_true': round(WRAP_MM[0] / WRAP_MM[1], 4),
                 'said': 'one scale for both axes (nothing stretched); the picture placed from the trim\'s top-left at '
                         '64.8 mm wide, its height %.3f mm at that scale (the page clips the %.3f mm below 42)' % (
                             rows / k, max(rows / k - WRAP_MM[1], 0.0))}


GROUND_DARK_SHARE = 0.25                         # the ground is read from the darkest quarter of the wrap's pixels …
GROUND_NEAR_DE = 10.0                            # … then refined over every pixel within ΔE00 10 of that first reading


def ground_lab(rgb):
    """The indigo ground's colour, found from the picture (no window): the median Lab of its darkest quarter (the
    stones, the veins and the gold are all lighter than the indigo), refined as the median of every pixel within ΔE00 10
    of that reading — robust where stones reach an edge (S4)."""
    lab = lm.srgb_to_lab(rgb)
    light = lab[..., 0]
    dark = light <= np.percentile(light, 100.0 * GROUND_DARK_SHARE)
    first = np.median(lab[dark], axis=0)
    near = lm.delta_e00(lab, np.broadcast_to(first, lab.shape)) <= GROUND_NEAR_DE
    return np.median(lab[near], axis=0)


def lab_hex(lab):
    """A Lab colour as sRGB hex (D65), clipped to the gamut."""
    return zo.lab_to_hex(lab)


def masks(rgb, ground):
    """The wrap's inks by colour, as ``zilal_master.masks`` reads the lid (its thresholds): the rose gold (L* > 30,
    chroma > 12, hue 38–75°), the cream type (L* > 60, chroma under 25), and every pixel off the ground by over ΔE00
    15 — the ground read from this picture (``ground_lab``), not the lid's window."""
    lab = lm.srgb_to_lab(rgb)
    light, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    hue = np.degrees(np.arctan2(b, a)) % 360
    gold = ((light > zm.ROSE_GOLD_L_MIN) & (np.hypot(a, b) > zm.ROSE_GOLD_C_MIN)
            & (hue > zm.ROSE_GOLD_HUE[0]) & (hue < zm.ROSE_GOLD_HUE[1]))
    cream = (light > 60) & (np.hypot(a, b) < 25)
    off = lm.delta_e00(lab, np.broadcast_to(ground, lab.shape)) > zm.OFF_GROUND_DE
    return {'gold': gold, 'cream': cream, 'off': off}


def odd_px(mm, k):
    """A structuring element's size (px, odd, at least 1) for ``mm`` at ``k`` px/mm."""
    return max(int(round(mm * k)) // 2 * 2 + 1, 1)


def disc(px):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (px, px))


# --- the hero: found by its painted hatch ------------------------------------------------------------------------------

#: zilal_master.ELEMENT_MORPH['hero'] carried to the wrap in mm: closed 9 px and opened 7 px at the lid's 8.084 px/mm —
#: strokes finer than 0.87 mm (أحمر, the logotype, the veins) open away, the hero's stems (≈ 1.8 mm) and dots stay
HERO_CLOSE_MM = 9 / lm.PX_PER_MM_SRC
HERO_OPEN_MM = 7 / lm.PX_PER_MM_SRC
HERO_PART_MIN_MM2 = 1.0                          # a hero part (a letter, a dot) is at least 1 mm² after the opening
HATCH_SHARE_MIN = 0.4                            # a part is the hero's when its hatch carries ≥ 40 % of the main part's
HERO_REACH_SHARE = 0.25                          # … and it lies within the main part's box grown by a quarter of its size
                                                 # (its other letters and dots; a hatched-looking stone further off is not)
HATCH_DEMOD_SIGMA_MM = 0.5                       # the hatch's local amplitude read over σ 0.5 mm (complex demodulation)
HATCH_BAND_PERIOD_PX = (1.5, 16.0)               # the FFT looks for the hatch between 1.5 and 16 px a period (the lid's
                                                 # hatch_measure looked at 2–8 px; the wraps' painted hatch is ~2 px)


def hatch_spectrum(light, inner, box):
    """The hero's hatch by FFT, as ``zilal_master.hatch_measure`` reads it: L* inside the letters (``inner``, the rims
    eroded away), mean removed, a Hann window; the dominant period in the band, refined by the 5 × 5 centroid. Returns
    the period (px), the wave vector's angle (°), the lines' angle in orn_b1's convention (0 level, rising to the right
    as it grows, y down — ``fit_hatch``'s reading of the wave), the peak's prominence over the band's median, and the
    log spectrum for the record."""
    x0, y0, x1, y1 = box
    sub, m = light[y0:y1, x0:x1].astype(np.float64), inner[y0:y1, x0:x1]
    v = np.where(m, sub - sub[m].mean(), 0.0)
    h, w = v.shape
    spec = np.abs(np.fft.fftshift(np.fft.fft2(v * np.outer(np.hanning(h), np.hanning(w))))) ** 2
    fy = (np.arange(h) - h // 2) / h
    fx = (np.arange(w) - w // 2) / w
    FY, FX = np.meshgrid(fy, fx, indexing='ij')
    radius = np.hypot(FX, FY)
    lo, hi = HATCH_BAND_PERIOD_PX
    sel = (radius > 1.0 / hi) & (radius < 1.0 / lo)
    band = np.where(sel, spec, 0)
    iy, ix = np.unravel_index(np.argmax(band), band.shape)
    nb = band[iy - 2:iy + 3, ix - 2:ix + 3]
    wy = float((FY[iy - 2:iy + 3, ix - 2:ix + 3] * nb).sum() / nb.sum())
    wx = float((FX[iy - 2:iy + 3, ix - 2:ix + 3] * nb).sum() / nb.sum())
    period = 1.0 / float(np.hypot(wx, wy))
    wave = float(np.degrees(np.arctan2(wy, wx)))
    return {'period_px': round(period, 4), 'wave_vector_deg': round(wave, 3),
            'line_angle_deg': round((90.0 - wave) % 180.0, 3),
            'prominence': round(float(band[iy, ix] / np.median(spec[sel])), 1),
            'wave_px': (wx, wy), 'crop_px': [int(v) for v in box], 'spectrum': spec}


def hatch_amplitude(light, wave_px, k):
    """The painted hatch's local amplitude at its own wave vector (complex demodulation of L* less its local mean,
    σ 0.5 mm): high where the hero's hatch is painted, low on solid gold, on stones and on the ground."""
    h, w = light.shape
    ys, xs = np.mgrid[0:h, 0:w]
    q = light - cv2.blur(light, (5, 5))
    z = q * np.exp(-2j * np.pi * (xs * wave_px[0] + ys * wave_px[1]))
    sigma = HATCH_DEMOD_SIGMA_MM * k
    return np.abs(gaussian_filter(z.real, sigma) + 1j * gaussian_filter(z.imag, sigma))


def find_hero(rgb, m, k):
    """The hero شفاه, found from the picture: the rose gold closed and opened at the hero's scale (strokes finer than
    0.87 mm open away), its largest part the main one; the hatch measured on it (``hatch_spectrum``); every other part
    of at least 1 mm² whose painted hatch carries at least 40 % of the main part's amplitude and whose box meets the main
    part's box grown by a quarter of its size belongs to the hero (its other letters and its dots) — a stone or a solid
    word carries no hatch. Returns the parts' mask (whole wrap), their
    boxes, the hatch reading and the window (the parts' box grown 1 mm)."""
    light = lm.srgb_to_lab(rgb)[..., 0].astype(np.float64)
    g = cv2.morphologyEx(m['gold'].astype(np.uint8), cv2.MORPH_CLOSE, np.ones((odd_px(HERO_CLOSE_MM, k),) * 2, np.uint8))
    g = cv2.morphologyEx(g, cv2.MORPH_OPEN, np.ones((odd_px(HERO_OPEN_MM, k),) * 2, np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(g, 8)
    if n < 2:
        raise ValueError('no rose-gold part as wide as the hero\'s stems: the hero is not found')
    main = 1 + int(np.argmax(stats[1:, 4]))
    x, y, w, h, _ = stats[main]
    inner = cv2.erode((labels == main).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    hatch = hatch_spectrum(light, inner, (x, y, x + w, y + h))
    amp = hatch_amplitude(light, hatch['wave_px'], k)
    main_amp = float(np.median(amp[inner]))
    parts = []
    for i in range(1, n):
        if stats[i, 4] < HERO_PART_MIN_MM2 * k * k:
            continue
        core = cv2.erode((labels == i).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        if not core.any():
            continue
        share = float(np.median(amp[core])) / main_amp
        bx, by, bw, bh, area = (int(v) for v in stats[i])
        rx, ry = HERO_REACH_SHARE * w, HERO_REACH_SHARE * h
        near = bx < x + w + rx and bx + bw > x - rx and by < y + h + ry and by + bh > y - ry
        parts.append({'label': i, 'box_px': [bx, by, bx + bw, by + bh], 'area_mm2': round(area / k / k, 2),
                      'hatch_share': round(share, 3), 'near_main': bool(near),
                      'hero': bool(share >= HATCH_SHARE_MIN and near)})
    keep = [p for p in parts if p['hero']]
    mask = np.isin(labels, [p['label'] for p in keep])
    ys, xs = np.nonzero(mask)
    pad = int(round(1.0 * k))
    hh, ww = rgb.shape[:2]
    window = [max(int(xs.min()) - pad, 0), max(int(ys.min()) - pad, 0), min(int(xs.max()) + 1 + pad, ww),
              min(int(ys.max()) + 1 + pad, hh)]
    return {'mask': mask, 'parts': parts, 'window_px': window, 'hatch': hatch, 'main_amplitude': round(main_amp, 3)}


# --- the solid rose gold (أحمر, the logotype, the cap's logo) and the cream lines ------------------------------------

VEIN_OPEN_PX = 3                                 # the stones' copper veins (1–2 px) opened away; the solid words' strokes
                                                 # (≥ 3 px at the wraps' 13.8 px/mm) stay
WORD_JOIN_MM = (1.2, 0.4)                        # a word's letters joined by 1.2 mm across and 0.4 mm down
ROW_JOIN_MM = 4.0                                # words on one row (their spans overlapping half their height) joined
                                                 # across a gap up to 4 mm (the logotype's two words)
HERO_CLEAR_MM = 0.5                              # the solid gold read outside the hero grown 0.5 mm (its rim's glints)
WORD_MIN_MM2 = 1.0


def solid_words(m, hero_mask, k):
    """The solid rose-gold words outside the hero: the gold, the hero grown 0.5 mm taken out, the veins opened away
    (3 px), the letters joined into words (1.2 × 0.4 mm), words on one row joined across a gap up to 4 mm. Each word's
    box (px), its gold area (mm²) and its mask (whole wrap)."""
    hero = cv2.dilate(hero_mask.astype(np.uint8), disc(odd_px(2 * HERO_CLEAR_MM, k))).astype(bool)
    gold = (m['gold'] & ~hero).astype(np.uint8)
    gold = cv2.morphologyEx(gold, cv2.MORPH_OPEN, disc(VEIN_OPEN_PX))
    jx, jy = (odd_px(v, k) for v in WORD_JOIN_MM)
    joined = cv2.dilate(gold, np.ones((jy, jx), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(joined, 8)
    words = []
    for i in range(1, n):
        own = (labels == i) & gold.astype(bool)
        area = float(own.sum()) / k / k
        if area < WORD_MIN_MM2:
            continue
        ys, xs = np.nonzero(own)
        words.append({'box_px': [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
                      'area_mm2': round(area, 2), 'mask': own})
    rows = []
    for wd in sorted(words, key=lambda r: r['box_px'][0]):
        for row in rows:
            r0, r1 = row['box_px'][1], row['box_px'][3]
            w0, w1 = wd['box_px'][1], wd['box_px'][3]
            overlap = min(r1, w1) - max(r0, w0)
            gap = wd['box_px'][0] - row['box_px'][2]
            if overlap >= 0.5 * min(r1 - r0, w1 - w0) and gap <= ROW_JOIN_MM * k:
                row['box_px'] = [min(row['box_px'][0], wd['box_px'][0]), min(r0, w0),
                                 max(row['box_px'][2], wd['box_px'][2]), max(r1, w1)]
                row['area_mm2'] = round(row['area_mm2'] + wd['area_mm2'], 2)
                row['mask'] = row['mask'] | wd['mask']
                row['words'] += 1
                break
        else:
            rows.append(dict(wd, words=1))
    return rows


def find_solid(m, hero, k):
    """أحمر and the logotype, found by their place beside the hero (D-D11-7's copy split as the sketches draw it):
    the logotype the widest solid row (at least three times as wide as tall) whose top lies below the hero's middle;
    أحمر the largest solid word whose foot lies above the hero's middle and within the hero's span grown by its own
    width. Each refused, with what was found, when absent."""
    rows = solid_words(m, hero['mask'], k)
    hx0, hy0, hx1, hy1 = hero['window_px']
    mid = (hy0 + hy1) / 2.0
    names = [r for r in rows if r['box_px'][1] > mid and (r['box_px'][2] - r['box_px'][0]) >= 3 * (r['box_px'][3] - r['box_px'][1])]
    if not names:
        raise ValueError('no logotype row below the hero: %s' % [r['box_px'] for r in rows])
    name = max(names, key=lambda r: r['box_px'][2] - r['box_px'][0])
    span = hx1 - hx0
    ahmars = [r for r in rows if r['box_px'][3] < mid and r['box_px'][2] > hx0 - span and r['box_px'][0] < hx1 + span]
    if not ahmars:
        raise ValueError('no small Arabic word above the hero\'s middle: %s' % [r['box_px'] for r in rows])
    ahmar = max(ahmars, key=lambda r: r['area_mm2'])
    return {'name': name, 'ahmar': ahmar, 'rows': [{k_: v for k_, v in r.items() if k_ != 'mask'} for r in rows]}


#: the small lines as the sketch draws them (D-D11-7): the runs each is fitted on, the copy each carries, capitals
#: or as written, and how many glyph units the sketch's line holds (the ℮ one of them, drawn by the engine)
LINES = {
    'lipstick': {'runs': ('LIPSTICK',), 'copy': 'Lipstick', 'upper': True, 'units': 8},
    'net': {'runs': ('3.5', 'g', lm.SIGN, '0.12', 'oz'), 'copy': '3.5 g ℮ 0.12 oz', 'upper': False, 'units': 11},
}
CREAM_OPEN_PX = 2                                # zilal_master.ELEMENT_MORPH['cream']: opened 2 px
CREAM_ROW_GAP_PX = 3                             # a line's rows run unbroken but for gaps up to 3 px
LINE_PAD_PX = zm.LINE_PAD_PX
GOLD_CLEAR_MM = 0.5                              # the cream is read outside the gold words grown 0.5 mm (their bevels'
                                                 # light); the cream type's own warm edges read as gold, so never all gold


def find_lines(rgb, m, k, below_px, gold_words):
    """The two small lines, found from the picture: the cream (opened 2 px) below ``below_px`` (the logotype's foot)
    and outside the gold words (``gold_words``, the hero's and the solid words' masks) grown 0.5 mm, cut into rows at
    gaps over 3 px; the two lowest rows of at least 1 mm² of cream, the upper "Lipstick", the lower the net line. Each
    line's ink box (px, x0 y0 x1 y1)."""
    gold = cv2.dilate(gold_words.astype(np.uint8), disc(odd_px(2 * GOLD_CLEAR_MM, k))).astype(bool)
    cream = cv2.morphologyEx((m['cream'] & ~gold).astype(np.uint8), cv2.MORPH_OPEN, np.ones((CREAM_OPEN_PX,) * 2, np.uint8))
    cream[:below_px] = 0
    rows = np.nonzero(cream.any(axis=1))[0]
    found = []
    for r in np.split(rows, np.nonzero(np.diff(rows) > CREAM_ROW_GAP_PX)[0] + 1):
        if not len(r):
            continue
        band = cream[r[0]:r[-1] + 1]
        if band.sum() < k * k:
            continue
        cols = np.nonzero(band.any(axis=0))[0]
        found.append([int(cols.min()), int(r[0]), int(cols.max()) + 1, int(r[-1]) + 1])
    if len(found) < 2:
        raise ValueError('the small lines are not found under the logotype: %s' % found)
    return {'lipstick': found[-2], 'net': found[-1]}


# --- tracing at the wrap's scale: the shared reader and trace (zilal_master, D-D12-9) ---------------------------------

def trace_alpha(alpha, window, k):
    """``zilal_master.trace_alpha`` at the wrap's scale (``k`` its px/mm; rings in mm, origin the trim's top-left)."""
    return zm.trace_alpha(alpha, window, k)


def prove_trace(alpha, window, rings, k):
    """``zilal_master.prove_trace`` at the wrap's scale."""
    return zm.prove_trace(alpha, window, rings, k)


def prove_outline_on_pick(rgb, rings, k):
    """``lid_master.prove_outline_on_pick`` at the wrap's scale: along the traced outline every 0.05 mm, the PICK's own
    L* along the outward normal (±0.6 mm at 0.005 mm, cubic), the strong fall nearest the outline — the edge as the
    sketch paints it, independent of the alpha the trace was cut from. Reported beside the trace's proof."""
    from shapely import contains_xy
    lightness = cv2.GaussianBlur(lm.srgb_to_lab(rgb)[..., 0].astype(np.float32), (0, 0), 0.5)
    geom = lm.rings_area(rings, 24)
    offs = np.arange(-lm.EDGE_WINDOW_MM, lm.EDGE_WINDOW_MM + 1e-9, 0.005)
    dists = []
    for g in lm.parts(geom):
        for ring in [g.exterior, *g.interiors]:
            n = max(int(ring.length / 0.05), 8)
            ts = np.linspace(0, ring.length, n, endpoint=False)
            pts = np.array([ring.interpolate(t).coords[0] for t in ts])
            ahead = np.array([ring.interpolate((t + 0.02) % ring.length).coords[0] for t in ts])
            tan = ahead - pts
            tn = np.hypot(tan[:, 0], tan[:, 1])
            ok = tn > 1e-9
            nx, ny = -tan[ok, 1] / tn[ok], tan[ok, 0] / tn[ok]
            px, py = pts[ok, 0], pts[ok, 1]
            inward = contains_xy(geom, px + 0.03 * nx, py + 0.03 * ny)
            nx = np.where(inward, -nx, nx)
            ny = np.where(inward, -ny, ny)
            xs = (px[:, None] + offs[None, :] * nx[:, None]) * k - 0.5
            ys = (py[:, None] + offs[None, :] * ny[:, None]) * k - 0.5
            prof = map_coordinates(lightness, [ys.ravel(), xs.ravel()], order=3, mode='nearest').reshape(xs.shape)
            fall = -np.diff(prof, axis=1)
            peak = (fall[:, 1:-1] >= fall[:, :-2]) & (fall[:, 1:-1] >= fall[:, 2:])
            strong = peak & (fall[:, 1:-1] >= lm.EDGE_STRONG * fall.max(axis=1, keepdims=True))
            at = np.abs(offs[1:-2] + 0.0025)
            dists.append(np.where(strong, at[None, :], np.inf).min(axis=1))
    every = np.concatenate(dists)
    d = every[np.isfinite(every)]
    unread = int((~np.isfinite(every)).sum())
    return {'reference': 'the pick\'s own L*: the strong fall nearest the outline along each outward normal',
            'points': int(len(every)), 'unread': unread, 'unread_share': round(unread / len(every), 5),
            'window_mm': lm.EDGE_WINDOW_MM, 'max_mm': round(float(d.max()), 4),
            'p99_mm': round(float(np.percentile(d, 99)), 4), 'median_mm': round(float(np.median(d)), 4),
            'within_0_3_mm_share': round(float(np.mean(d <= zm.TRACE_MAX_MM)), 5),
            'holds': bool(d.max() <= zm.TRACE_MAX_MM and unread / len(every) <= lm.EDGE_UNREAD_MAX)}


# --- the pieces that stand whatever the lower group's layout (the owner's question, master/QUESTION.json) -------------

def hero_master(rgb, m, k):
    """The hero شفاه as D-D11-3.1 makes the lid's: found by its painted hatch (``find_hero``), read and traced by the
    shared reader (``zilal_master.read_hero``, D-D12-9: the bevel's outer dark edge, its counters closed; 0.3 mm, IoU
    0.95) and proved again on the pick's own edges (Day 11's reading, beside); the hatch an engine line system at the
    painted hatch's angle (FFT) and pitch, coarsened by ``zilal_master.hatch_stroke`` to the press (stroke ≥ 0.15 mm,
    gap 0.22 mm) when the painted pitch cannot hold both — said; the foil the lid's (``zilal_master.hero_foil``: its
    0.40 mm rim, 0.22 mm groove, the strokes inside), the relief the silhouette."""
    hero = find_hero(rgb, m, k)
    window = hero['window_px']
    rings, proof = zm.read_hero(rgb, hero['mask'], window, k, zm.HOLE_FILL_MM2)
    proof['against_the_pick_itself'] = prove_outline_on_pick(rgb, rings, k)
    letters = zm.letters_geometry(rings)
    hatch = hero['hatch']
    fit = {'angle_deg': hatch['line_angle_deg'], 'pitch_mm': hatch['period_px'] / k, 'phase_mm': 0.0}
    stroke = zm.hatch_stroke(fit)
    foil = zm.hero_foil(letters, fit, stroke)
    return {'rings': rings, 'letters': letters, 'foil': foil['foil'], 'relief': foil['relief'], 'window_px': window,
            'record': {'trace': proof, 'parts': [{k_: p[k_] for k_ in ('box_px', 'area_mm2', 'hatch_share', 'hero')}
                                                 for p in hero['parts']],
                       'hatch': {'painted_period_px': hatch['period_px'],
                                 'painted_pitch_mm': round(hatch['period_px'] / k, 4),
                                 'angle_deg': hatch['line_angle_deg'], 'prominence': hatch['prominence'],
                                 'stroke': stroke,
                                 'said': 'the painted hatch at %.3f mm cannot hold a 0.15 mm stroke and a 0.22 mm gap: the '
                                         'engine\'s lines keep its angle at the press\'s pitch %.2f mm (D-D11-3.1: '
                                         'coarsened only if needed — it is)' % (hatch['period_px'] / k,
                                                                                 stroke['pitch_mm'])},
                       'foil_mm2': round(float(foil['foil'].area), 3), 'relief_mm2': round(float(letters.area), 3),
                       'foil_cleaning_moved_mm2': foil['moved_mm2']}}


AHMAR_PAD_MM = 2.0                               # أحمر's window: its box padded 2 mm, so the reader finds ground 1 mm out


def ahmar_master(rgb, m, hero, k):
    """أحمر: found beside the hero (``find_solid``), read and traced by the shared reader (``zilal_master.read_hero``,
    D-D12-9) and proved; foiled solid in rose gold (its strokes hold no hatch),
    cleaned to the press as the lid's foil is."""
    solid = find_solid(m, {'mask': hero['mask'], 'window_px': hero['window_px']}, k)
    word = solid['ahmar']
    x0, y0, x1, y1 = word['box_px']
    pad = int(round(AHMAR_PAD_MM * k))
    window = [max(x0 - pad, 0), max(y0 - pad, 0), min(x1 + pad, rgb.shape[1]), min(y1 + pad, rgb.shape[0])]
    rings, proof = zm.read_hero(rgb, word['mask'], window, k, zm.HOLE_FILL_MM2)
    proof['against_the_pick_itself'] = prove_outline_on_pick(rgb, rings, k)
    geom = zm.letters_geometry(rings)
    clean = geom.buffer(-zm.FOIL_OPEN_R_MM).buffer(zm.FOIL_OPEN_R_MM).buffer(zm.FOIL_CLOSE_R_MM).buffer(-zm.FOIL_CLOSE_R_MM)
    return {'rings': rings, 'foil': clean, 'solid': solid,
            'record': {'trace': proof, 'box_px': word['box_px'], 'foil_mm2': round(float(clean.area), 3),
                       'foil_cleaning_moved_mm2': round(float(clean.symmetric_difference(geom).area), 4)}}


def logotype_source():
    """"Enchanted Rose" as the LID's traced logotype (D-D11-7: never re-traced): zilal_master.trace_name on the lid's
    pick of record, pinned by that pick's sha256 (refine/pick.json); its rings in lid mm and their ink box."""
    pick = zm.load_master_pick()
    rings, _, proof = zm.trace_name(pick)
    geom = lm.rings_area(rings, 24)
    pinned = json.loads((zm.REFINE / 'pick.json').read_text(encoding='utf-8'))
    return rings, {'source': 'zilal_master.trace_name on the lid\'s pick of record', 'pick': lm.rel(zm.MASTER_PICK),
                   'pick_sha256': pinned['lid_sha256'], 'rings': len(rings),
                   'ink_box_lid_mm': [round(v, 3) for v in geom.bounds], 'trace_iou': proof['iou']}


CAP_LOGO_MIN_MM2 = 4.0                           # the cap's logo: a row of solid gold of at least 4 mm²


def cap_logo_box(rgb, m, k):
    """The cap's logo as the sketch places it: the solid rose gold (the veins opened away, letters joined into words)
    whose row is the widest — BBROSE® — its ink box (px and mm)."""
    rows = solid_words(m, np.zeros(m['gold'].shape, dtype=bool), k)
    rows = [r for r in rows if r['area_mm2'] >= CAP_LOGO_MIN_MM2]
    if not rows:
        raise ValueError('no solid rose-gold row on the cap: the logo is not found')
    best = max(rows, key=lambda r: r['box_px'][2] - r['box_px'][0])
    x0, y0, x1, y1 = best['box_px']
    mask = best['mask'].copy()
    # the mark's ® is a part of its own, small, just right of the row's end and at its top: taken with the logo (its box
    # and its cleaning), as the approved master carries it
    gold = cv2.morphologyEx(m['gold'].astype(np.uint8), cv2.MORPH_OPEN, disc(2))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(gold, 8)
    for i in range(1, n):
        bx, by, bw, bh, area = (int(v) for v in stats[i])
        if x1 - 1 <= bx <= x1 + int(round(REG_MARK_REACH_MM * k)) and by >= y0 - 2 and by + bh <= y0 + (y1 - y0) / 2 + 2:
            mask |= labels == i
            x1 = max(x1, bx + bw)
    return {'box_px': [x0, y0, x1, y1], 'box_mm': [round(v / k, 3) for v in (x0, y0, x1, y1)], 'mask': mask}


REG_MARK_REACH_MM = 2.5                          # the ® stands within 2.5 mm of the mark's last letter


SEAM_BAND_MM = 2.0                               # D-D11-7: the seam a 2 mm feathered band …
SEAM_READ_MM = 1.0                               # … read over 1 mm either side of the join …
SEAM_SIGMA_MM = 0.5                              # … each strip's colour along the join (σ 0.5 mm) …
SEAM_MEAN_MAX = 2.0                              # … mean ΔE00 ≤ 2 after treatment


def join_profile(rgb, k):
    """The two strips that meet when the wrap closes: the right end's last 1 mm (its edge lies outside, over the left
    start) and the left start's 1 mm just past the overlap it hides; each averaged across, smoothed along the join
    (σ 0.5 mm); ΔE00 at every row."""
    from scipy.ndimage import gaussian_filter1d
    ov = int(round(OVERLAP_MM * k))
    r = int(round(SEAM_READ_MM * k))
    left = gaussian_filter1d(rgb[:, ov:ov + r].astype(np.float64).mean(axis=1), SEAM_SIGMA_MM * k, axis=0)
    right = gaussian_filter1d(rgb[:, -r:].astype(np.float64).mean(axis=1), SEAM_SIGMA_MM * k, axis=0)
    return lm.delta_e00(lm.srgb_to_lab(np.clip(np.round(left), 0, 255).astype(np.uint8)[None]),
                        lm.srgb_to_lab(np.clip(np.round(right), 0, 255).astype(np.uint8)[None]))[0]


def treat_seam(rgb, k):
    """The seam (D-D11-7, an allowed difference): the right end's last 2 mm feathered, from none at 2 mm in to all at
    its edge, toward the left start's own pixels mirrored about the join (what the eye meets across it); proven by
    ``join_profile`` before and after (mean ≤ 2). Returns the treated picture and the record."""
    before = join_profile(rgb, k)
    band = int(round(SEAM_BAND_MM * k))
    ov = int(round(OVERLAP_MM * k))
    target = rgb[:, ov:ov + band][:, ::-1].astype(np.float64)
    w = np.linspace(0.0, 1.0, band)[None, :, None]
    out = rgb.astype(np.float64).copy()
    out[:, -band:] = out[:, -band:] * (1 - w) + target * w
    out = np.clip(np.round(out), 0, 255).astype(np.uint8)
    after = join_profile(out, k)
    return out, {'band_mm': SEAM_BAND_MM, 'read_mm': SEAM_READ_MM, 'sigma_mm': SEAM_SIGMA_MM,
                 'before': {'mean': round(float(before.mean()), 3), 'max': round(float(before.max()), 3)},
                 'after': {'mean': round(float(after.mean()), 3), 'max': round(float(after.max()), 3)},
                 'holds': bool(after.mean() <= SEAM_MEAN_MAX),
                 'rule': 'D-D11-7: the seam a 2 mm feathered band, an allowed difference, proven: mean ΔE00 ≤ 2 across '
                         'the join after treatment'}


# --- the master (D-D11-7 as the owner's answer of 24 October changed it: D-D11-11) -------------------------------------

UP = lm.UP                                       # the wraps upscaled Lanczos 2× (D-D10-2.1's baseline)
CLEAN_NEAR_MM = 0.5                              # a cleaned element: its own ink and every off-ground pixel within 0.5 mm
CLEAN_GROW_PX = 3                                # … grown 3 upscaled px (its anti-aliased edge)
TELEA_R_PX = 7
LABEL_D_MM = 18.0                                # D-D11-7: the bottom label Ø 18
LABEL_BLEED_MM = 1.0
LABEL_SAFE_MM = 1.0
LABEL_FIGURE_CAP_MM = 2.0                        # D-D11-11: on the label the figures ≥ 2 mm …
LABEL_SIGN_MM = 3.0                              # … and the ℮ at its legal 3 mm, though taller than its figures
LABEL_SHADE_CAP_MM = 1.5
LABEL_BATCH_CAP_MM = 1.15                       # 5.1 pt: over the 5 pt floor
LABEL_ROW_GAP_MM = 0.9
FLOOR_PT = 5.0
MM_PER_PT = lm.MM_PER_INCH / 72.0                # the conversions by their declared names (lid_master.PT_PER_MM and this),
                                                 # as unit_analysis.NAMED_CONSTANTS reads them


def own_near(own, m, k):
    """An element's pixels to clean: its own ink and every off-ground pixel within 0.5 mm of it (its bevel's shadow and
    light), not a stone's: the near band is kept only where it touches the ink (one connected stretch)."""
    near = cv2.dilate(own.astype(np.uint8), disc(odd_px(2 * CLEAN_NEAR_MM, k))).astype(bool)
    return own | (near & m['off'])


GRAIN_TONE_SIGMA_MM = 1.0                        # the fill's tone read from the untouched ground within about 1 mm …
GRAIN_CALM_DE = 6.0                              # … its grain from untouched ground within ΔE00 6 of the indigo (no stone,
GRAIN_SEARCH_MM = 1.0                            # no vein), the donor window searched every 1 mm across and down


GRAIN_TONE_WIDEN_MM = (1.0, 4.0, 12.0)          # the fill's tone: σ widened where the calm weight is thin …
GRAIN_TONE_WEIGHT_MIN = 0.05                     # … under 5 % (a spot deep in a wide footprint reads from further out)
GRAIN_TONE_DOWN_PX = 8                           # each wide σ read on a copy reduced by σ / 8 px (cv2, linear back up)


def calm_tone(img, keep, k_up):
    """The local tone of ``img`` from the ``keep`` pixels only: a normalised Gaussian at σ 1 mm, widened to 4 and 12 mm
    where the kept weight is under 5 %, the kept pixels' median past that — never a black tone where no kept pixel
    reaches."""
    h, w = keep.shape
    tone = np.zeros(img.shape, np.float64)
    done = np.zeros(keep.shape, dtype=bool)
    kf = keep.astype(np.float32)
    lit = (img * keep[..., None]).astype(np.float32)
    for s_mm in GRAIN_TONE_WIDEN_MM:
        s = s_mm * k_up
        f = max(int(s // GRAIN_TONE_DOWN_PX), 1)
        size = (max(w // f, 1), max(h // f, 1))
        wk = cv2.GaussianBlur(cv2.resize(kf, size, interpolation=cv2.INTER_AREA), (0, 0), s / f)
        num = cv2.GaussianBlur(cv2.resize(lit, size, interpolation=cv2.INTER_AREA), (0, 0), s / f)
        wk = cv2.resize(wk, (w, h), interpolation=cv2.INTER_LINEAR)
        num = cv2.resize(num, (w, h), interpolation=cv2.INTER_LINEAR)
        ok = (wk >= GRAIN_TONE_WEIGHT_MIN) & ~done
        tone[ok] = num[ok] / wk[ok][:, None]
        done |= ok
    if (~done).any():
        tone[~done] = np.median(img[keep], axis=0)
    return tone


def grain_fill(up, mask, ground, k_up):
    """A cleaned footprint filled as the sticker's border was (zilal_sticker.refill_bottom): each pixel the picture's own
    grain from one donor window — the footprint shifted (every 1 mm across and down) to where its pixels are most
    wholly calm, untouched ground (within ΔE00 6 of the indigo, outside the footprint) — its deviation from its local
    mean (σ 1 mm) laid on the local tone of the untouched pixels around the spot. Returns the filled picture, the shift
    (mm, across and down) and the donor's share that is not calm ground."""
    from scipy.ndimage import gaussian_filter
    ys, xs = np.nonzero(mask)
    lab = lm.srgb_to_lab(up)
    calm = lm.delta_e00(lab, np.broadcast_to(ground, lab.shape)) <= GRAIN_CALM_DE
    good = calm & ~mask
    h, w = mask.shape
    best, best_share = None, 2.0
    step = max(int(round(GRAIN_SEARCH_MM * k_up)), 1)
    for dy in range(-h, h, step):
        for dx in range(-w, w, step):
            if abs(dx) < step and abs(dy) < step:
                continue
            sx, sy = xs - dx, ys - dy
            if sx.min() < 0 or sx.max() >= w or sy.min() < 0 or sy.max() >= h:
                continue
            share = 1.0 - float(good[sy, sx].mean())
            if share < best_share:
                best, best_share = (dx, dy), share
    out = up.astype(np.float64)
    pad = int(round(2.0 * k_up))
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + 1 + pad, h)
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + 1 + pad, w)
    region = out[y0:y1, x0:x1]
    ry, rx = np.mgrid[y0:y1, x0:x1]
    donor = up[np.clip(ry - best[1], 0, h - 1), np.clip(rx - best[0], 0, w - 1)].astype(np.float64)
    sigma = GRAIN_TONE_SIGMA_MM * k_up
    # [Day 12, D-D12-7's grain-fill limit] the tone read from the untouched CALM ground only (no stone's colour taken
    # in), widened (1 → 4 → 12 mm) where a spot lies deep in a wide footprint (Day 11's single 1 mm read fell to black
    # past its 4σ reach); all untouched pixels only when the picture holds no calm ground at all
    keep = ~mask & calm
    if not keep.any():
        keep = ~mask
    tone = calm_tone(out, keep, k_up)[y0:y1, x0:x1]
    donor_tone = np.stack([gaussian_filter(donor[..., c], sigma) for c in range(3)], axis=-1)
    fill = donor - donor_tone + tone
    inside = mask[y0:y1, x0:x1][..., None]
    out[y0:y1, x0:x1] = np.where(inside, fill, region)
    return (np.clip(np.round(out), 0, 255).astype(np.uint8), [round(best[0] / k_up, 2), round(best[1] / k_up, 2)],
            round(best_share, 4))


RESIDUE_CALM_SIGMA_MM = 0.5                      # the cleaned pixels' local mean, as lid_master.residue reads it


def residue_calm(plate, mask, ground, k_up):
    """[Day 12] A cleaning's ghost against the CALM ground: the cleaned pixels' local mean (σ 0.5 mm) against the calm
    tone (``calm_tone`` over calm, untouched ground) — beside ``lid_master.residue``, whose ground is read from every
    pixel outside the mask (stones and re-set letters beside a cleaned area included)."""
    lab = lm.srgb_to_lab(plate)
    calm = (lm.delta_e00(lab, np.broadcast_to(ground, lab.shape)) <= GRAIN_CALM_DE) & ~mask
    p = plate.astype(np.float64)
    local = cv2.GaussianBlur(p, (0, 0), RESIDUE_CALM_SIGMA_MM * k_up)
    tone = calm_tone(p, calm, k_up)
    de = lm.delta_e00(lm.srgb_to_lab(np.clip(local[mask], 0, 255).astype(np.uint8)[None]),
                      lm.srgb_to_lab(np.clip(tone[mask], 0, 255).astype(np.uint8)[None]))
    return {'de00_mean': round(float(de.mean()), 3), 'de00_p99': round(float(np.percentile(de, 99)), 3),
            'de00_max': round(float(de.max()), 3), 'against': 'the calm ground\'s tone (calm_tone)'}


GRAIN_TILE_MM = 5.0                              # a wide footprint filled tile by tile, each tile its own donor


def grain_fill_tiled(up, mask, ground, k_up):
    """[Day 12] A cleaned footprint filled as ``grain_fill`` fills one, but tile by tile (5 mm): each tile's own donor —
    the placement of the tile's footprint over the picture (``cv2.matchTemplate``, every px) where its pixels are most
    wholly calm ground (within ΔE00 6 of the indigo) outside the whole footprint — its deviation from its local mean
    (σ 1 mm) laid on the calm tone (``calm_tone``). One donor for a whole wide footprint (the hero's 33 × 17 mm) found no
    calm window on a 64.8 mm wrap and carried stones and letters in as grain. Returns the filled picture and the tiles'
    record (count, the donors' worst and mean share that is not calm ground)."""
    from scipy.ndimage import gaussian_filter
    lab = lm.srgb_to_lab(up)
    calm = lm.delta_e00(lab, np.broadcast_to(ground, lab.shape)) <= GRAIN_CALM_DE
    good = (calm & ~mask).astype(np.float32)
    keep = calm & ~mask
    if not keep.any():
        keep = ~mask
    out = up.astype(np.float64)
    tone = calm_tone(out, keep, k_up)
    h, w = mask.shape
    t = max(int(round(GRAIN_TILE_MM * k_up)), 1)
    pad = int(round(2.0 * k_up))
    sigma = GRAIN_TONE_SIGMA_MM * k_up
    ys, xs = np.nonzero(mask)
    shares = []
    for ty in range(int(ys.min()), int(ys.max()) + 1, t):
        for tx in range(int(xs.min()), int(xs.max()) + 1, t):
            part = mask[ty:ty + t, tx:tx + t]
            if not part.any():
                continue
            py, px = np.nonzero(part)
            fy0, fy1, fx0, fx1 = py.min(), py.max() + 1, px.min(), px.max() + 1
            tmpl = part[fy0:fy1, fx0:fx1].astype(np.float32)
            score = cv2.matchTemplate(good, tmpl, cv2.TM_CCORR)
            by, bx = np.unravel_index(int(np.argmax(score)), score.shape)
            share = 1.0 - float(score[by, bx]) / float(tmpl.sum())
            dx, dy = (tx + fx0) - bx, (ty + fy0) - by                # the donor = the target − (dx, dy)
            y0, y1 = max(ty - pad, 0), min(ty + t + pad, h)
            x0, x1 = max(tx - pad, 0), min(tx + t + pad, w)
            ry, rx = np.mgrid[y0:y1, x0:x1]
            donor = up[np.clip(ry - dy, 0, h - 1), np.clip(rx - dx, 0, w - 1)].astype(np.float64)
            donor_tone = np.stack([gaussian_filter(donor[..., c], sigma) for c in range(3)], axis=-1)
            fill = donor - donor_tone + tone[y0:y1, x0:x1]
            inside = np.zeros((y1 - y0, x1 - x0), dtype=bool)
            inside[ty - y0:ty - y0 + part.shape[0], tx - x0:tx - x0 + part.shape[1]] = part
            region = out[y0:y1, x0:x1]
            out[y0:y1, x0:x1] = np.where(inside[..., None], fill, region)
            shares.append(share)
    return (np.clip(np.round(out), 0, 255).astype(np.uint8),
            {'tiles': len(shares), 'tile_mm': GRAIN_TILE_MM, 'donor_not_calm_share_max': round(max(shares), 4),
             'donor_not_calm_share_mean': round(float(np.mean(shares)), 4)})


BOX_GROW_MM = 0.6                                # a cleaned line: its whole box grown 0.6 mm (its painted drop shadow
                                                 # lies outside the ink), less any stone in it …
STONE_MIN_MM2 = 0.3                              # … a stone: off the ground, neither rose gold nor cream, 0.3 mm² or more
                                                 # (the type's own anti-aliased edges are smaller parts)


def box_mask(shape, box_px, k, m, rgb):
    """A painted line to clean on plain indigo: its ink box grown 0.6 mm, whole (the ink and its drop shadow), less the
    stones the box takes in."""
    g = int(round(BOX_GROW_MM * k))
    x0, y0, x1, y1 = box_px
    out = np.zeros(shape, dtype=bool)
    out[max(y0 - g, 0):y1 + g, max(x0 - g, 0):x1 + g] = True
    stone = (m['off'] & ~m['gold'] & ~m['cream']).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(stone, 8)
    big = np.zeros(n, dtype=bool)
    big[1:] = stats[1:, 4] >= STONE_MIN_MM2 * k * k
    stone = cv2.dilate(big[labels].astype(np.uint8), disc(3)).astype(bool)
    return out & ~stone


def clean_up(rgb, mask, ground):
    """The picture upscaled 2× (``lm.upscale``) and the cleaned elements filled on the upscaled grid (the mask grown 3
    upscaled px): Telea first (the inks' light gone), then the picture's own grain on the calm tone, tile by tile
    (``grain_fill_tiled``, Day 12) so no smear shows; the residue measured as the lid's (``lm.residue``)."""
    up = lm.upscale(rgb)
    big = cv2.resize(mask.astype(np.uint8), (up.shape[1], up.shape[0]), interpolation=cv2.INTER_NEAREST)
    big = cv2.dilate(big, disc(2 * CLEAN_GROW_PX + 1))
    plate = cv2.inpaint(up, big, TELEA_R_PX, cv2.INPAINT_TELEA)
    k_up = up.shape[1] / WRAP_MM[0]
    plate, _ = grain_fill_tiled(plate, big.astype(bool), ground, k_up)
    return up, plate, big.astype(bool)


def line_fit(text, box_px, k, face):
    """A live line in the lid's Latin face fitted to the sketch's ink box: its size from the box's height (the cap
    height, capitals), its tracking from the box's width (the drawn width read with the emitter's own measure), centred
    on the box, the baseline on its foot."""
    from fontTools.ttLib import TTFont
    font = TTFont(face['path'])
    cap = font['OS/2'].sCapHeight / font['head'].unitsPerEm
    x0, y0, x1, y1 = (v / k for v in box_px)
    size_mm = (y1 - y0) / cap
    size_pt = size_mm * lm.PT_PER_MM
    natural = zs_width(text, face, size_pt)
    tracking = ((x1 - x0) - natural) / (max(len(text) - 1, 1) * size_mm)
    return {'text': text, 'size_pt': round(size_pt, 3), 'cap_mm': round(y1 - y0, 3), 'tracking_em': round(tracking, 4),
            'x_centre_mm': round((x0 + x1) / 2, 3), 'baseline_mm': round(y1, 3), 'ink_mm': [round(v, 3) for v in (x0, y0, x1, y1)]}


def zs_width(text, face, size_pt):
    from apps.pipeline.services import palette_sticker as ps
    return ps.width_mm(text, face, size_pt)


def place_logotype(rings, src_record, box_px, k):
    """The lid's logotype rings placed on the sketch's own logotype (D-D11-7: never re-traced): one scale (the sketch's
    ink width over the lid's), centred on the sketch's ink box; the transform recorded and proved by mapping the placed
    rings back onto the source (IoU 1)."""
    gx0, gy0, gx1, gy1 = src_record['ink_box_lid_mm']
    x0, y0, x1, y1 = (v / k for v in box_px)
    s = (x1 - x0) / (gx1 - gx0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ox, oy = cx - s * (gx0 + gx1) / 2, cy - s * (gy0 + gy1) / 2
    placed = lm.map_rings(rings, lambda p: (ox + s * p[0], oy + s * p[1]))
    back = lm.map_rings(placed, lambda p: ((p[0] - ox) / s, (p[1] - oy) / s))
    a, b = lm.rings_area(back, 24), lm.rings_area(rings, 24)
    iou = float(a.intersection(b).area / a.union(b).area)
    pb_ = lm.rings_area(placed, 24).bounds
    return placed, {'scale': round(s, 6), 'offset_mm': [round(ox, 4), round(oy, 4)],
                    'placed_ink_mm': [round(v, 3) for v in pb_], 'sketch_ink_mm': [round(v, 3) for v in (x0, y0, x1, y1)],
                    'height_error_mm': round((pb_[3] - pb_[1]) - (y1 - y0), 3),
                    'inverse_iou_with_the_source': round(iou, 6)}


PROOF_PAGE_W_MM = 110.0                          # the finish proof's own copy of a wrap: the emitter's plate label (6 pt
                                                 # from 4 mm) needs ~66 mm, the wrap gives 64.8 — so the proof reads a copy
                                                 # on a wider page, the same content at the same place, cropped back


def wrap_document(plate_png, children, title, page_w=None):
    from apps.ire.graph import Document, Group, Image as GImage
    if page_w is None:
        page_w = WRAP_MM[0]
    picture = Group(name='PICTURE', role='background', children=[
        GImage(name='plate', src=str(plate_png), x=0.0, y=0.0, w=WRAP_MM[0], h=WRAP_MM[1])])
    return Document(page_w=page_w, page_h=WRAP_MM[1], title=title,
                    metadata={'typography_surface': SURFACE, 'logical_text/1.0': True},
                    root=Group(name=title.upper(), role='artwork', children=[picture] + children))


def files_of(out, stem, engine_ai, proof_ai, k):
    """A wrap's files from its engine document: the print PDF (trim 64.8 × 42, its 1 mm top and bottom bleed inside),
    the 300 PPI flat, the finish proof (finish_proof.prove_build reads the foil and relief plates from the engine)."""
    import fitz
    from apps.pipeline.services import finish_proof as fp
    pdf = fitz.open()
    with fitz.open(str(engine_ai)) as src:
        p = pdf.new_page(width=src[0].rect.width, height=src[0].rect.height)
        p.show_pdf_page(p.rect, src, 0)
    trim = fitz.Rect(0, lm.pt(BLEED_TB_MM), p.rect.width, p.rect.height - lm.pt(BLEED_TB_MM))
    p.set_bleedbox(p.rect)
    p.set_trimbox(trim)
    pdf.set_metadata({'title': 'the lipstick\'s %s wrap' % stem, 'creator': SURFACE})
    lm.tag_srgb(pdf)
    pdf.save(str(out / ('%s-wrap.pdf' % stem)), garbage=3, deflate=True)
    pdf.close()
    lm.render_png(out / ('%s-wrap.pdf' % stem), 0, 300, out / ('%s-flat.png' % stem))
    proof_dir = out / ('%s-proof' % stem)
    lm.render_png(proof_ai, 0, 300, out / 'engine' / ('%s-proof-flat.png' % stem))
    rec = fp.prove_build(out / 'engine' / ('%s-proof-flat.png' % stem), proof_ai, proof_dir, foil_drawn=True)
    wide = Image.open(proof_dir / 'finish-proof.png')
    keep = int(round(wide.width * WRAP_MM[0] / PROOF_PAGE_W_MM))
    wide.crop((0, 0, keep, wide.height)).save(out / ('%s-finish-proof.png' % stem))
    return {'pdf': lm.rel(out / ('%s-wrap.pdf' % stem)), 'flat': lm.rel(out / ('%s-flat.png' % stem)),
            'ai': lm.rel(engine_ai), 'finish_proof': lm.rel(out / ('%s-finish-proof.png' % stem)),
            'foil_limits': rec['foil_limits'], 'coverage': rec['coverage']}


def body_master(folder, out):
    """The body wrap: the hero (raster beneath, its foil and relief on carriers), أحمر (raster beneath, solid foil),
    "Enchanted Rose" the lid's vector in the lid's rose-gold ink over its cleaned painted logotype, "LIPSTICK" live in the
    lid's Latin face over its cleaned painted line, the painted net line cleaned out (D-D11-11), the seam treated."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Finish, Group, Path as GPath, SolidFill, TextRun
    raw, sha, path = load_wrap(folder, 'body')
    rgb, trim = trim_rows(raw)
    k = trim['px_per_mm']
    ground = ground_lab(rgb)
    m = masks(rgb, ground)
    hero = hero_master(rgb, m, k)
    found = find_hero(rgb, m, k)
    ahmar = ahmar_master(rgb, m, {'mask': found['mask'], 'window_px': found['window_px']}, k)
    solid = ahmar['solid']
    gold_words = found['mask'] | solid['name']['mask'] | solid['ahmar']['mask']
    lines = find_lines(rgb, m, k, solid['name']['box_px'][3], gold_words)
    master = json.loads((LID / 'master.json').read_text(encoding='utf-8'))
    inks = master['type']['inks']
    name_ink = master['name']['ink']
    hero_ink = master['hero']['ink']
    from apps.pipeline.services import zilal_sticker as zs
    face = zs.faces()['medium']
    lip = line_fit('LIPSTICK', lines['lipstick'], k, face)
    rings, src = logotype_source()
    placed, transform = place_logotype(rings, src, solid['name']['box_px'], k)
    transform['cap_height_mm'] = round(master['name']['measures']['cap_height_mm'] * transform['scale'], 3)
    transform['cap_at_least_3_mm'] = bool(transform['cap_height_mm'] >= 3.0)
    # the cleaning: the painted logotype, "LIPSTICK" and the net line (D-D11-11: cleaned out), each its ink and bevel
    cream = m['cream']
    def boxed(mask, box):
        x0, y0, x1, y1 = box
        out_ = np.zeros(mask.shape, dtype=bool)
        out_[y0:y1, x0:x1] = mask[y0:y1, x0:x1]
        return out_
    pad = int(round(0.6 * k))
    grow = lambda b: [b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad]
    # under the logotype and "LIPSTICK" (set again in place) their own ink and near shadow; the net line, which nothing
    # covers (D-D11-11), its whole box less the stones
    clean = (own_near(solid['name']['mask'], m, k) | own_near(boxed(cream, grow(lines['lipstick'])), m, k)
             | box_mask(cream.shape, lines['net'], k, m, rgb))
    up, plate, big = clean_up(rgb, clean, ground)
    proof_up = lm.prove_upscale(rgb, up, {})
    residue = lm.residue(plate, big)
    plate, seam = treat_seam(plate, k * UP)
    plate_png = out / 'engine' / 'body-plate.png'
    Image.fromarray(plate).save(plate_png)
    foil = Finish(kind='foil', plate=zm.FOIL_PLATE, appearance=Color.from_hex(hero_ink))
    emboss = Finish(kind='emboss', plate=zm.EMBOSS_PLATE)
    extra = {}
    if lip['tracking_em'] > 0:
        extra['tracking_em'] = lip['tracking_em']
    children = [
        Group(name='TYPE', role='typography', children=[
            TextRun(name='lipstick', text='Lipstick', x=lip['x_centre_mm'], y=lip['baseline_mm'], font=face['role'],
                    size_pt=lip['size_pt'], color=Color.from_hex(inks['eyeshadow']), align='center', text_case='upper',
                    **extra)]),
        Group(name='LOGOTYPE', role='typography', actual_text='Enchanted Rose', children=[
            GPath(name='Enchanted Rose', segments=lm.rings_segments(placed), fill=SolidFill(color=Color.from_hex(name_ink)),
                  fill_rule='evenodd')]),
        Group(name='HERO CARRIERS', role='effects', opacity=0.0, actual_text='أحمر شفاه', children=[
            GPath(name='أحمر (foil)', segments=zm.poly_segments(ahmar['foil']), fill=SolidFill(color=Color.from_hex(hero_ink)),
                  fill_rule='evenodd', finishes=[foil]),
            GPath(name='شفاه (foil)', segments=zm.poly_segments(hero['foil']), fill=SolidFill(color=Color.from_hex(hero_ink)),
                  fill_rule='evenodd', finishes=[foil]),
            GPath(name='شفاه (relief)', segments=zm.poly_segments(hero['relief']),
                  fill=SolidFill(color=Color.from_hex(hero_ink)), fill_rule='evenodd', finishes=[emboss])])]
    engine = out / 'engine' / 'body-engine.ai'
    emit_pdf_ai(wrap_document(plate_png, children, 'lipstick body wrap'), str(engine))
    proof_ai = out / 'engine' / 'body-proof-engine.ai'
    emit_pdf_ai(wrap_document(plate_png, children, 'lipstick body wrap', PROOF_PAGE_W_MM), str(proof_ai))
    files = files_of(out, 'body', engine, proof_ai, k)
    return {'sketch': {'path': lm.rel(path), 'sha256': sha}, 'trim': trim, 'ground': lab_hex(ground),
            'hero': hero['record'], 'ahmar': ahmar['record'], 'lipstick': lip, 'logotype': {'source': src, **transform},
            'net_line': {'cleaned_out': True, 'sketch_box_px': lines['net'],
                         'said': 'D-D11-11: the net content leaves the body for the bottom label (and the carton back)'},
            'cleaned_px_up': int(big.sum()), 'residue': residue, 'upscale': proof_up, 'seam': seam, 'files': files,
            'boxes_mm': {'hero': [round(v / k, 3) for v in hero['window_px']],
                         'ahmar': [round(v / k, 3) for v in solid['ahmar']['box_px']],
                         'logotype': transform['placed_ink_mm'], 'lipstick': lip['ink_mm']}}


# --- D-D12-1.1: the lipstick closed — the hero into the front third ------------------------------------------------

CASE_D_MM = 20.0                                  # the case Ø (D-D11-7, ⟪PROVISIONAL⟫)
HERO_SCALE = 0.63                                 # D-D12-1.1: شفاه and أحمر scaled together
LOGOTYPE_SCALE = 0.80                             # D-D12-1.1: the logotype (cap 3.405 → 2.72 mm)
CAP_FLOOR_SMALL_WRAP_MM = 2.5                     # D-D12-1.1: on wraps of Ø ≤ 20 mm the cap floor is 2.5 mm (℮ 3 mm)
PRESS_PITCH_MM = 0.37                             # PIECES.json: the hero's hatch at the press's pitch …
PRESS_ANGLE_DEG = 45.186                          # … and the painted hatch's angle (FFT)
HERO_CARRY_MM = 0.35                              # the hero's raster carried with its bevel's near shadow: the silhouette
HERO_FEATHER_MM = 0.25                            # grown 0.35 mm, feathered 0.25 mm into the cleaned ground
HERO_CLEAN_MM = 0.9                               # the painted hero cleaned: its silhouette grown 0.9 mm (bevel and shadow)
STACK_STEP_MM = 0.1                               # the stack lowered by 0.1 mm steps while a letter would cover a stone
STONE_TEXT_CLEAR_MM = 1.5                         # stones read 1.5 mm clear of the painted words (not their own bevels)


def front_third(wrap_w, d_mm):
    """The front third of a wrap closed round a case of Ø ``d_mm`` with its right end over its left start (the overlap
    ``wrap_w`` − πd): the front centre opposite the seam (the overlap + half the circumference) and the third of the
    circumference about it (mm on the wrap)."""
    circ = np.pi * d_mm
    centre = (wrap_w - circ) + circ / 2.0
    return {'circumference_mm': round(circ, 4), 'centre_mm': round(centre, 4),
            'span_mm': [round(centre - circ / 6.0, 4), round(centre + circ / 6.0, 4)], 'width_mm': round(circ / 3.0, 4)}


def stones_clear_of_words(m, words, k):
    """The sketch's stones: off the ground, neither rose gold nor cream, 0.3 mm² or more, read 1.5 mm clear of the
    painted words (their own bevels and shadows are not stones)."""
    clear = cv2.dilate(words.astype(np.uint8), disc(odd_px(2 * STONE_TEXT_CLEAR_MM, k))).astype(bool)
    stone = (m['off'] & ~m['gold'] & ~m['cream'] & ~clear).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(stone, 8)
    big = np.zeros(n, dtype=bool)
    big[1:] = stats[1:, 4] >= STONE_MIN_MM2 * k * k
    return big[labels]


def body_closed(folder, out):
    """D-D12-1.1: the body wrap closed — شفاه and أحمر scaled together × 0.63 into the front third (the painted pair
    cleaned out; its raster, with the bevel's near shadow, resampled and set again; its foil and relief vectors moved by
    the same affine; the hatch re-fitted on the scaled silhouette at the press's 0.37 mm and the painted 45.186°), the
    lid's logotype × 0.80 of its sketch scale (cap 2.72 mm, over the 2.5 mm floor of a Ø ≤ 20 wrap), "LIPSTICK" at its
    sketched size; the four re-stacked with the sketch's own gaps, centred on the front third across, their vertical
    centre the sketch's own, lowered by the least 0.1 mm step if a letter would cover a stone; the stones untouched."""
    from shapely import affinity
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Finish, Group, Path as GPath, SolidFill, TextRun
    from apps.pipeline.services import zilal_sticker as zs
    raw, sha, path = load_wrap(folder, 'body')
    rgb, trim = trim_rows(raw)
    k = trim['px_per_mm']
    ground = ground_lab(rgb)
    m = masks(rgb, ground)
    hero = hero_master(rgb, m, k)
    found = find_hero(rgb, m, k)
    ahmar = ahmar_master(rgb, m, {'mask': found['mask'], 'window_px': found['window_px']}, k)
    solid = ahmar['solid']
    gold_words = found['mask'] | solid['name']['mask'] | solid['ahmar']['mask']
    lines = find_lines(rgb, m, k, solid['name']['box_px'][3], gold_words)
    master = json.loads((LID / 'master.json').read_text(encoding='utf-8'))
    inks = master['type']['inks']
    name_ink = master['name']['ink']
    hero_ink = master['hero']['ink']
    face = zs.faces()['medium']
    lip = line_fit('LIPSTICK', lines['lipstick'], k, face)
    rings, src = logotype_source()
    _, sketch_logo = place_logotype(rings, src, solid['name']['box_px'], k)
    third = front_third(WRAP_MM[0], CASE_D_MM)
    xf = third['centre_mm']

    # the stack as sketched: the hero pair (شفاه with أحمر), the logotype, "LIPSTICK" — and its own gaps
    pair = zm.letters_geometry(hero['rings']).union(zm.letters_geometry(ahmar['rings']))
    gx0, gy0, gx1, gy1 = pair.bounds
    lx0, ly0, lx1, ly1 = sketch_logo['placed_ink_mm']
    px0, py0, px1, py1 = lip['ink_mm']
    gaps = [round(ly0 - gy1, 4), round(py0 - ly1, 4)]
    h_pair = (gy1 - gy0) * HERO_SCALE
    h_logo = (ly1 - ly0) * LOGOTYPE_SCALE
    height = h_pair + gaps[0] + h_logo + gaps[1] + (py1 - py0)
    sketch_centre = (gy0 + py1) / 2.0
    stones = stones_clear_of_words(m, gold_words | box_mask(m['cream'].shape, lines['lipstick'], k, m, rgb)
                                   | box_mask(m['cream'].shape, lines['net'], k, m, rgb), k)

    def layout(top):
        pair_t = affinity.translate(affinity.scale(pair, HERO_SCALE, HERO_SCALE, origin=(gx0, gy0)),
                                    xf - HERO_SCALE * (gx1 - gx0) / 2.0 - gx0, top - gy0)
        logo_top = top + h_pair + gaps[0]
        lip_base = logo_top + h_logo + gaps[1] + (py1 - py0)
        return pair_t, logo_top, lip_base

    top = sketch_centre - height / 2.0
    lowered = 0.0
    while True:
        pair_t, logo_top, lip_base = layout(top)
        cover = lm.raster_fill(pair_t, stones.shape, (0.0, 0.0), k) & stones
        if not cover.any():
            break
        top += STACK_STEP_MM
        lowered += STACK_STEP_MM
        if top + height > WRAP_MM[1] - BLEED_TB_MM - SAFE_TB_MM:
            raise ValueError('the closed stack cannot clear the stones inside the safe height')
    dx = xf - HERO_SCALE * (gx1 - gx0) / 2.0 - gx0
    dy = top - gy0

    def move(geom):
        return affinity.translate(affinity.scale(geom, HERO_SCALE, HERO_SCALE, origin=(gx0, gy0)), dx, dy)

    def move_rings(rs):
        return lm.map_rings(rs, lambda p: (gx0 + HERO_SCALE * (p[0] - gx0) + dx, gy0 + HERO_SCALE * (p[1] - gy0) + dy))

    hero_rings_t = move_rings(hero['rings'])
    letters_t = zm.letters_geometry(hero_rings_t)
    fit = {'angle_deg': PRESS_ANGLE_DEG, 'pitch_mm': PRESS_PITCH_MM, 'phase_mm': 0.0}
    stroke = zm.hatch_stroke(fit)
    foil_t = zm.hero_foil(letters_t, fit, stroke)
    ahmar_t = move(ahmar['foil'])
    ahmar_t = (ahmar_t.buffer(-zm.FOIL_OPEN_R_MM).buffer(zm.FOIL_OPEN_R_MM).buffer(zm.FOIL_CLOSE_R_MM)
               .buffer(-zm.FOIL_CLOSE_R_MM))

    # the logotype × 0.80 of its sketch scale, centred on the front third, its top where the stack puts it
    s_logo = sketch_logo['scale'] * LOGOTYPE_SCALE
    gl0, gl1 = src['ink_box_lid_mm'][0], src['ink_box_lid_mm'][2]
    ox = xf - s_logo * (gl0 + gl1) / 2.0
    oy = logo_top - s_logo * src['ink_box_lid_mm'][1]
    placed = lm.map_rings(rings, lambda p: (ox + s_logo * p[0], oy + s_logo * p[1]))
    back = lm.map_rings(placed, lambda p: ((p[0] - ox) / s_logo, (p[1] - oy) / s_logo))
    a_, b_ = lm.rings_area(back, 24), lm.rings_area(rings, 24)
    logo_rec = {'scale': round(s_logo, 6), 'sketch_scale': sketch_logo['scale'], 'times': LOGOTYPE_SCALE,
                'offset_mm': [round(ox, 4), round(oy, 4)], 'placed_ink_mm': [round(v, 3) for v in lm.rings_area(placed, 24).bounds],
                'inverse_iou_with_the_source': round(float(a_.intersection(b_).area / a_.union(b_).area), 6),
                'cap_height_mm': round(master['name']['measures']['cap_height_mm'] * s_logo, 3)}
    logo_rec['over_the_floor'] = bool(logo_rec['cap_height_mm'] >= CAP_FLOOR_SMALL_WRAP_MM)
    lb = logo_rec['placed_ink_mm']
    logo_rec['inside_the_front_third'] = bool(third['span_mm'][0] <= lb[0] and lb[2] <= third['span_mm'][1])

    # the cleaning: the painted pair (its silhouette grown 0.9 mm: bevel and shadow), the painted logotype and
    # "LIPSTICK" (their own ink and near shadow), the net line's box (D-D11-11) — then the pair set again, scaled
    cream = m['cream']
    def boxed(mask, box):
        x0, y0, x1, y1 = box
        out_ = np.zeros(mask.shape, dtype=bool)
        out_[y0:y1, x0:x1] = mask[y0:y1, x0:x1]
        return out_
    pad = int(round(0.6 * k))
    grow = lambda b: [b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad]
    pair_px = lm.raster_fill(pair, cream.shape, (0.0, 0.0), k)
    pair_clean = cv2.dilate(pair_px.astype(np.uint8), disc(odd_px(2 * HERO_CLEAN_MM, k))).astype(bool) & ~stones
    # the logotype and "LIPSTICK" move: their whole painted boxes (ink and drop shadow) cleaned, as the net line's
    clean = (pair_clean | box_mask(cream.shape, solid['name']['box_px'], k, m, rgb)
             | box_mask(cream.shape, lines['lipstick'], k, m, rgb) | box_mask(cream.shape, lines['net'], k, m, rgb))
    up, plate, big = clean_up(rgb, clean, ground)
    k_up = k * UP
    # the pair's raster: the upscaled sketch inside its silhouette grown 0.35 mm, feathered 0.25 mm, scaled × 0.63
    carry = lm.raster_fill(pair.buffer(HERO_CARRY_MM), up.shape[:2], (0.0, 0.0), k_up).astype(np.float32)
    carry = cv2.GaussianBlur(carry, (0, 0), HERO_FEATHER_MM * k_up / 2.0)
    bx0, by0, bx1, by1 = [int(np.floor(v * k_up)) for v in pair.buffer(HERO_CARRY_MM + HERO_FEATHER_MM).bounds]
    bx0, by0 = max(bx0, 0), max(by0, 0)
    bx1, by1 = min(bx1 + 1, up.shape[1]), min(by1 + 1, up.shape[0])
    src_rgb = up[by0:by1, bx0:bx1].astype(np.float32)
    src_a = carry[by0:by1, bx0:bx1]
    nw, nh = int(round((bx1 - bx0) * HERO_SCALE)), int(round((by1 - by0) * HERO_SCALE))
    small_rgb = cv2.resize(src_rgb, (nw, nh), interpolation=cv2.INTER_AREA)
    small_a = cv2.resize(src_a, (nw, nh), interpolation=cv2.INTER_AREA)[..., None]
    tx = int(round((gx0 + HERO_SCALE * (bx0 / k_up - gx0) + dx) * k_up))
    ty = int(round((gy0 + HERO_SCALE * (by0 / k_up - gy0) + dy) * k_up))
    if tx < 0 or ty < 0 or tx + nw > plate.shape[1] or ty + nh > plate.shape[0]:
        raise ValueError('the scaled pair would leave the wrap: %s' % [tx, ty, nw, nh])
    region = plate[ty:ty + nh, tx:tx + nw].astype(np.float32)
    plate = plate.copy()
    plate[ty:ty + nh, tx:tx + nw] = np.clip(np.round(region * (1 - small_a) + small_rgb * small_a), 0, 255).astype(np.uint8)
    pasted = np.zeros(big.shape, dtype=bool)
    pasted[ty:ty + nh, tx:tx + nw] = small_a[..., 0] > 0.01
    proof_up = lm.prove_upscale(rgb, up, {})
    residue = lm.residue(plate, big & ~pasted)          # the cleaning's residue where nothing is set again
    residue['calm'] = residue_calm(plate, big & ~pasted, ground, k_up)
    residue['said'] = ('lid_master.residue reads its ground from every pixel outside the mask — beside this cleaning the '
                       're-set copper pair and the stones; the calm reading is the ghost against the calm ground')
    plate, seam = treat_seam(plate, k_up)
    plate_png = out / 'engine' / 'body-plate.png'
    Image.fromarray(plate).save(plate_png)
    foil = Finish(kind='foil', plate=zm.FOIL_PLATE, appearance=Color.from_hex(hero_ink))
    emboss = Finish(kind='emboss', plate=zm.EMBOSS_PLATE)
    extra = {}
    if lip['tracking_em'] > 0:
        extra['tracking_em'] = lip['tracking_em']
    lip_closed = dict(lip, x_centre_mm=round(xf, 3), baseline_mm=round(lip_base, 3),
                      ink_mm=[round(xf - (px1 - px0) / 2, 3), round(lip_base - (py1 - py0), 3), round(xf + (px1 - px0) / 2, 3),
                              round(lip_base, 3)])
    children = [
        Group(name='TYPE', role='typography', children=[
            TextRun(name='lipstick', text='Lipstick', x=lip_closed['x_centre_mm'], y=lip_closed['baseline_mm'],
                    font=face['role'], size_pt=lip['size_pt'], color=Color.from_hex(inks['eyeshadow']), align='center',
                    text_case='upper', **extra)]),
        Group(name='LOGOTYPE', role='typography', actual_text='Enchanted Rose', children=[
            GPath(name='Enchanted Rose', segments=lm.rings_segments(placed), fill=SolidFill(color=Color.from_hex(name_ink)),
                  fill_rule='evenodd')]),
        Group(name='HERO CARRIERS', role='effects', opacity=0.0, actual_text='أحمر شفاه', children=[
            GPath(name='أحمر (foil)', segments=zm.poly_segments(ahmar_t), fill=SolidFill(color=Color.from_hex(hero_ink)),
                  fill_rule='evenodd', finishes=[foil]),
            GPath(name='شفاه (foil)', segments=zm.poly_segments(foil_t['foil']), fill=SolidFill(color=Color.from_hex(hero_ink)),
                  fill_rule='evenodd', finishes=[foil]),
            GPath(name='شفاه (relief)', segments=zm.poly_segments(letters_t),
                  fill=SolidFill(color=Color.from_hex(hero_ink)), fill_rule='evenodd', finishes=[emboss])])]
    engine = out / 'engine' / 'body-engine.ai'
    emit_pdf_ai(wrap_document(plate_png, children, 'lipstick body wrap'), str(engine))
    proof_ai = out / 'engine' / 'body-proof-engine.ai'
    emit_pdf_ai(wrap_document(plate_png, children, 'lipstick body wrap', PROOF_PAGE_W_MM), str(proof_ai))
    files = files_of(out, 'body', engine, proof_ai, k)
    pair_box = [round(v, 3) for v in move(pair).bounds]
    return {'sketch': {'path': lm.rel(path), 'sha256': sha}, 'trim': trim, 'ground': lab_hex(ground),
            'front_third': third,
            'closed': {'rule': 'D-D12-1.1', 'hero_scale': HERO_SCALE, 'logotype_times': LOGOTYPE_SCALE,
                       'sketch_gaps_mm': gaps, 'stack_height_mm': round(height, 3),
                       'sketch_stack_centre_mm': round(sketch_centre, 3), 'lowered_for_stones_mm': round(lowered, 2),
                       'pair_box_mm': pair_box, 'pair_width_mm': round(pair_box[2] - pair_box[0], 3),
                       'pair_inside_the_front_third': bool(third['span_mm'][0] <= pair_box[0] and pair_box[2] <= third['span_mm'][1]),
                       'pair_transform': {'scale': HERO_SCALE, 'origin_mm': [round(gx0, 4), round(gy0, 4)],
                                          'then_moved_mm': [round(dx, 4), round(dy, 4)]},
                       'raster': 'the painted pair cleaned (its silhouette grown %.1f mm, stones kept), its upscaled raster '
                                 'inside the silhouette grown %.2f mm (feathered %.2f mm) resampled × %.2f (area) and set '
                                 'again: the picked pair, not redrawn' % (HERO_CLEAN_MM, HERO_CARRY_MM, HERO_FEATHER_MM,
                                                                          HERO_SCALE),
                       'stones_untouched': 'the cleaning keeps every stone pixel (read 1.5 mm clear of the words); '
                                           'no scaled letter covers a stone',
                       'lipstick_cap_under_the_floor': {'cap_mm': lip['cap_mm'], 'floor_mm': CAP_FLOOR_SMALL_WRAP_MM,
                                                       'said': '"LIPSTICK" keeps its sketched size (D-D12-1.1) though under '
                                                               'the 2.5 mm floor the same decision sets: listed, not resolved'}},
            'hero': dict(hero['record'], closed={'letters_mm2': round(float(letters_t.area), 3),
                                                  'foil_mm2': round(float(foil_t['foil'].area), 3),
                                                  'hatch': {'fit': fit, 'stroke': stroke}}),
            'ahmar': dict(ahmar['record'], closed={'foil_mm2': round(float(ahmar_t.area), 3)}),
            'lipstick': lip_closed, 'logotype': {'source': src, **logo_rec},
            'net_line': {'cleaned_out': True, 'sketch_box_px': lines['net'],
                         'said': 'D-D11-11: the net content leaves the body for the bottom label (and the carton back)'},
            'cleaned_px_up': int(big.sum()), 'residue': residue, 'upscale': proof_up, 'seam': seam, 'files': files,
            'boxes_mm': {'hero': pair_box, 'logotype': logo_rec['placed_ink_mm'], 'lipstick': lip_closed['ink_mm']}}


def cap_master(folder, out):
    """The cap wrap: the stones as sketched, the painted logo cleaned and the approved logo set in the lid's rose-gold ink
    on the sketch's own box (its width, centred), the seam treated."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Group
    raw, sha, path = load_wrap(folder, 'cap')
    rgb, trim = trim_rows(raw)
    k = trim['px_per_mm']
    ground = ground_lab(rgb)
    m = masks(rgb, ground)
    logo = cap_logo_box(rgb, m, k)
    # the painted logo cleaned by its own ink and near shadow (a whole-box cleaning was tried for repair 1 and left a
    # lighter box behind the mark among the veins: not kept)
    up, plate, big = clean_up(rgb, own_near(logo['mask'], m, k), ground)
    proof_up = lm.prove_upscale(rgb, up, {})
    residue = lm.residue(plate, big)
    plate, seam = treat_seam(plate, k * UP)
    plate_png = out / 'engine' / 'cap-plate.png'
    Image.fromarray(plate).save(plate_png)
    master = json.loads((LID / 'master.json').read_text(encoding='utf-8'))
    x0, y0, x1, y1 = logo['box_mm']
    aspect = 0.20859051088028435                    # the approved logo's height over width (palette_box, lid_master)
    w = x1 - x0
    h = w * aspect
    cy = (y0 + y1) / 2
    box = (x0, cy - h / 2, w, h)
    children = [Group(name='LOGO', role='logo', children=lm.logo_parts(box, master['logo']['ink'], foil_letters=False))]
    engine = out / 'engine' / 'cap-engine.ai'
    emit_pdf_ai(wrap_document(plate_png, children, 'lipstick cap wrap'), str(engine))
    proof_ai = out / 'engine' / 'cap-proof-engine.ai'
    emit_pdf_ai(wrap_document(plate_png, children, 'lipstick cap wrap', PROOF_PAGE_W_MM), str(proof_ai))
    files = files_of(out, 'cap', engine, proof_ai, k)
    return {'sketch': {'path': lm.rel(path), 'sha256': sha}, 'trim': trim, 'ground': lab_hex(ground),
            'logo': {'sketch_box_mm': logo['box_mm'], 'placed_mm': [round(v, 3) for v in (x0, cy - h / 2, x1, cy + h / 2)],
                     'ink': master['logo']['ink']},
            'cleaned_px_up': int(big.sum()), 'residue': residue, 'upscale': proof_up, 'seam': seam, 'files': files}


def sign_aspect():
    """The house ℮'s ink width over its height (``estimated_sign.outline``, the glyph lid_master.sign_segments draws)."""
    from apps.ire import estimated_sign
    o = estimated_sign.outline()
    pts = [op[1:] for op in o['ops'] if op[0] != 'Z']
    xs = [v for p_ in pts for v in p_[0::2]]
    ys = [v for p_ in pts for v in p_[1::2]]
    return (max(xs) - min(xs)) / (max(ys) - min(ys))


def label_master(out, ground_hex, cream_hex):
    """The bottom label Ø 18 (D-D11-7 and D-D11-11), composed by the engine in the lid's language: the indigo ground,
    the shade "Wild Rose", the net content on two rows ("3.5 g ℮" / "0.12 oz": figures ≥ 2 mm, the ℮ at its legal 3 mm),
    a batch write-in field; every row inside the 1 mm safe ring (its width at its height measured against the
    circle's chord); the die circle on its own page."""
    import fitz
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, Path as GPath, Rect, SolidFill, TextRun
    from apps.pipeline.services import zilal_sticker as zs
    from fontTools.ttLib import TTFont
    face = zs.faces()['medium']
    font = TTFont(face['path'])
    cap = font['OS/2'].sCapHeight / font['head'].unitsPerEm
    page = LABEL_D_MM + 2 * LABEL_BLEED_MM
    c = page / 2
    r_safe = LABEL_D_MM / 2 - LABEL_SAFE_MM
    ink = Color.from_hex(cream_hex)

    def size_for(cap_mm):
        return cap_mm / cap * 72.0 / lm.MM_PER_INCH
    rows = [('shade', 'Wild Rose', LABEL_SHADE_CAP_MM), ('net-1', '3.5 g', LABEL_FIGURE_CAP_MM),
            ('net-2', '0.12 oz', LABEL_FIGURE_CAP_MM), ('batch', 'BATCH', LABEL_BATCH_CAP_MM)]
    heights = [LABEL_SIGN_MM if key == 'net-1' else capmm for key, _, capmm in rows]
    total = sum(heights) + LABEL_ROW_GAP_MM * (len(rows) - 1)
    y = c - total / 2
    nodes = [Rect(name='ground', x=0.0, y=0.0, w=page, h=page, fill=SolidFill(color=Color.from_hex(ground_hex)))]
    record = []
    for (key, text, capmm), hgt in zip(rows, heights):
        base = y + hgt
        pt = size_for(capmm)
        w = zs_width(text, face, pt)
        if key == 'net-1':
            gap = zs_width(' ', face, pt)
            sign_w = LABEL_SIGN_MM * sign_aspect()    # [after the gate] the sign's own width at 3 mm (it was boxed
                                                      # narrower, and spilled into the g)
            total_w = w + gap + sign_w
            x0 = c - total_w / 2
            nodes.append(TextRun(name='net:figures', text=text, x=x0, y=base, font=face['role'], size_pt=pt, color=ink))
            segs, _ = lm.sign_segments((x0 + w + gap, base - LABEL_SIGN_MM, x0 + w + gap + sign_w, base))
            nodes.append(Group(name='net:sign', actual_text=lm.SIGN, children=[
                GPath(name=lm.SIGN, segments=segs, fill=SolidFill(color=ink), fill_rule='nonzero')]))
            w = total_w
        elif key == 'batch':
            line_w = 4.0                            # [after the gate] shortened: clear of the safe ring with room
            total_w = w + 1.0 + line_w
            x0 = c - total_w / 2
            nodes.append(TextRun(name='batch', text=text, x=x0, y=base, font=face['role'], size_pt=pt, color=ink))
            nodes.append(Rect(name='batch line', x=x0 + w + 1.0, y=base - 0.1, w=line_w, h=0.12, fill=SolidFill(color=ink)))
            w = total_w
        else:
            nodes.append(TextRun(name=key, text=text, x=c, y=base, font=face['role'], size_pt=pt, color=ink, align='center'))
        x0 = c - w / 2
        worst = max(abs(y - c), abs(base - c))
        chord = 2.0 * float(np.sqrt(max(r_safe ** 2 - worst ** 2, 0.0)))
        corner = float(np.hypot(w / 2, worst))
        record.append({'row': key, 'text': text, 'cap_mm': hgt if key != 'net-1' else capmm, 'size_pt': round(pt, 2),
                       'width_mm': round(w, 2), 'chord_mm': round(chord, 2), 'inside_safe': bool(w <= chord),
                       'box_mm': [round(x0, 3), round(y, 3), round(x0 + w, 3), round(base, 3)],
                       'die_clearance_mm': round(LABEL_D_MM / 2 - corner, 3),
                       'above_floor': bool(pt >= FLOOR_PT)})
        y = base + LABEL_ROW_GAP_MM
    doc = Document(page_w=page, page_h=page, title='lipstick bottom label', metadata={'typography_surface': SURFACE,
                                                                                       'logical_text/1.0': True},
                   root=Group(name='LABEL', role='label', children=nodes))
    engine = out / 'engine' / 'label-engine.ai'
    emit_pdf_ai(doc, str(engine))
    pdf = fitz.open()
    with fitz.open(str(engine)) as src:
        p = pdf.new_page(width=src[0].rect.width, height=src[0].rect.height)
        p.show_pdf_page(p.rect, src, 0)
        p2 = pdf.new_page(width=src[0].rect.width, height=src[0].rect.height)
    centre = fitz.Point(lm.pt(c), lm.pt(c))
    p2.draw_circle(centre, lm.pt(LABEL_D_MM / 2), color=(0.85, 0, 0.55), width=0.5)
    p2.draw_circle(centre, lm.pt(r_safe), color=(0, 0.6, 0.9), width=0.3, dashes='[1 1] 0')
    for page_ in pdf:
        page_.set_bleedbox(page_.rect)
        page_.set_trimbox(fitz.Rect(lm.pt(LABEL_BLEED_MM), lm.pt(LABEL_BLEED_MM), lm.pt(page - LABEL_BLEED_MM),
                                    lm.pt(page - LABEL_BLEED_MM)))
    pdf.set_page_labels([{'startpage': 0, 'prefix': '1 the label ', 'style': ''},
                         {'startpage': 1, 'prefix': '2 die Ø 18 and the 1 mm safe ring ', 'style': ''}])
    pdf.set_metadata({'title': 'the lipstick\'s bottom label Ø 18', 'creator': SURFACE})
    pdf.save(str(out / 'label.pdf'), garbage=3, deflate=True)
    pdf.close()
    lm.render_png(out / 'label.pdf', 0, 600, out / 'label-flat.png')
    return {'diameter_mm': LABEL_D_MM, 'safe_mm': LABEL_SAFE_MM, 'rows': record,
            'holds': {'inside_safe': all(r['inside_safe'] for r in record), 'above_floor': all(r['above_floor'] for r in record),
                      'figures_2_mm': True, 'sign_3_mm': True},
            'said': 'D-D11-11: on the label the ℮ stands at its legal 3 mm though taller than its 2 mm figures (the law over '
                    'D-D11-6\'s "never larger")', 'files': {'pdf': lm.rel(out / 'label.pdf'), 'flat': lm.rel(out / 'label-flat.png')}}


def a4_page(out):
    """One A4 page at 100 %: the body wrap, the cap wrap and the label at true size, each with its name; crop marks at
    the wraps' trims (the 1 mm bleed outside them)."""
    import fitz
    pdf = fitz.open()
    page = pdf.new_page(width=lm.pt(297.0), height=lm.pt(210.0))
    places = [('body-wrap.pdf', 20.0, 30.0, 'body wrap 64.8 × 42 mm (the seam at the back: the right end over the left start)'),
              ('cap-wrap.pdf', 20.0, 110.0, 'cap wrap 64.8 × 42 mm'),
              ('label.pdf', 120.0, 30.0, 'bottom label Ø 18 mm')]
    for name, x, y, words in places:
        with fitz.open(str(out / name)) as src:
            w_mm, h_mm = src[0].rect.width * MM_PER_PT, src[0].rect.height * MM_PER_PT
            rect = fitz.Rect(lm.pt(x), lm.pt(y), lm.pt(x + w_mm), lm.pt(y + h_mm))
            page.show_pdf_page(rect, src, 0)
        page.insert_text(fitz.Point(lm.pt(x), lm.pt(y - 3)), words, fontsize=7, fontname='helv')
        for cx, cy in ((x, y), (x + w_mm, y), (x, y + h_mm), (x + w_mm, y + h_mm)):
            page.draw_line(fitz.Point(lm.pt(cx - 6), lm.pt(cy)), fitz.Point(lm.pt(cx - 2), lm.pt(cy)), width=0.3)
            page.draw_line(fitz.Point(lm.pt(cx), lm.pt(cy - 6)), fitz.Point(lm.pt(cx), lm.pt(cy - 2)), width=0.3)
    page.draw_line(fitz.Point(lm.pt(20), lm.pt(195)), fitz.Point(lm.pt(120), lm.pt(195)), width=0.5)
    page.insert_text(fitz.Point(lm.pt(20), lm.pt(192)), '100 mm (print at 100 %)', fontsize=7, fontname='helv')
    pdf.set_metadata({'title': 'the lipstick at 100 %', 'creator': SURFACE})
    pdf.save(str(out / 'lipstick-1to1-A4.pdf'), garbage=3, deflate=True)
    pdf.close()
    return lm.rel(out / 'lipstick-1to1-A4.pdf')


def build(folder, out_dir):
    """The lipstick master at $0 for a pick folder: body.json-like record lipstick.json with the body, the cap, the label,
    the A4 page, the finish sheet."""
    out = Path(out_dir)
    (out / 'engine').mkdir(parents=True, exist_ok=True)
    body = body_master(folder, out)
    cap = cap_master(folder, out)
    master = json.loads((LID / 'master.json').read_text(encoding='utf-8'))
    label = label_master(out, body['ground'], master['type']['inks']['eyeshadow'])
    a4 = a4_page(out)
    plates = [{'plate': 'print', 'what': 'process colour on the wrap paper: the picked sketch upscaled (Lanczos 2×), the '
                                         'logotype the lid\'s vector in the lid\'s rose-gold ink, "LIPSTICK" live'},
              {'plate': 'foil (rose gold)', 'what': 'شفاه: its rim and its hatch at the press\'s pitch; أحمر solid'},
              {'plate': 'relief (emboss)', 'what': 'شفاه\'s silhouette'},
              {'plate': 'label', 'what': 'the bottom label Ø 18: the shade, the net content on two rows, a batch field'}]
    from apps.pipeline.services import zilal_object as zo_
    zo_.finish_sheet('the lipstick', zm.REPO / body['files']['flat'], plates, out)
    record = {'schema': 'day11_lipstick_master/1', 'surface': SURFACE, 'pick': lm.rel(folder),
              'rule': 'D-D11-7 as D-D11-11 changed it: the body keeps the hero, أحمر, the logotype and "LIPSTICK" as '
                      'sketched, the painted net line cleaned out; the net content on the bottom label (and the carton back)',
              'body': body, 'cap': cap, 'label': label, 'a4': a4, 'plates': plates,
              'finish_sheet': lm.rel(out / 'finish-sheet.png')}
    lm.write_json(out / 'lipstick.json', record)
    return record


def sign_ink(segs):
    """A path's true ink box (mm): its lines' ends and its cubics sampled (not their control points)."""
    pts, cur = [], None
    t = np.linspace(0, 1, 201)[:, None]
    for sg in segs:
        kind = type(sg).__name__
        if kind in ('MoveTo', 'LineTo'):
            cur = (sg.x, sg.y)
            pts.append(cur)
        elif kind == 'CubicTo':
            p0, p1, p2, p3 = (np.array(cur), np.array((sg.x1, sg.y1)), np.array((sg.x2, sg.y2)), np.array((sg.x, sg.y)))
            pts.extend(map(tuple, (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3))
            cur = (sg.x, sg.y)
    p = np.asarray(pts)
    return [float(p[:, 0].min()), float(p[:, 1].min()), float(p[:, 0].max()), float(p[:, 1].max())]


def label_sign_proof(label_rec):
    """D-D12-1.2 read on the label as built: its ℮ is the lid's own sign (``lid_master.sign_segments``, the glyph the
    lid's net line draws — the same outline, scaled), its ink exactly 3 mm, standing on the figures' baseline, a word
    space after the figures."""
    from apps.pipeline.services import zilal_sticker as zs
    face = zs.faces()['medium']
    row = next(r for r in label_rec['rows'] if r['row'] == 'net-1')
    x0, y0, x1, base = row['box_mm']
    pt = row['size_pt']
    w = zs_width('3.5 g', face, pt)
    gap = zs_width(' ', face, pt)
    sign_w = LABEL_SIGN_MM * sign_aspect()
    segs, _ = lm.sign_segments((x0 + w + gap, base - LABEL_SIGN_MM, x0 + w + gap + sign_w, base))
    ink = sign_ink(segs)
    lid_segs, _ = lm.sign_segments((0.0, 0.0, 1.0, 1.0))
    a = np.array(sign_ink(lid_segs))
    same = len(segs) == len(lid_segs) and [type(s).__name__ for s in segs] == [type(s).__name__ for s in lid_segs]
    return {'rule': 'D-D12-1.2', 'the_lids_sign': bool(same), 'sign_source': 'lid_master.sign_segments (estimated_sign: the '
                                                                            'glyph the lid\'s net line "27 g ℮ 0.95 oz" draws)',
            'ink_height_mm': round(ink[3] - ink[1], 4), 'exactly_3_mm': bool(abs((ink[3] - ink[1]) - LABEL_SIGN_MM) < 0.001),
            'ink_bottom_mm': round(ink[3], 4), 'figures_baseline_mm': round(base, 4),
            'on_the_baseline': bool(abs(ink[3] - base) < 0.001), 'word_space_mm': round(gap, 4),
            'figures_cap_mm': LABEL_FIGURE_CAP_MM, 'unit_box_ink': [round(v, 4) for v in a]}


def build_closed(folder, out_dir):
    """D-D12-1: the lipstick closed at $0 — the body with the hero in the front third (``body_closed``), the cap as
    Day 11 built it, the bottom label (its ℮ the lid's sign at exactly 3 mm on the figures' baseline: proved), the A4 at
    100 %, the finish sheet, and the product drawing (D-D12-1.4: front and three-quarter, "drawing, not a render")."""
    from apps.pipeline.services import product_drawing as pdw
    from apps.pipeline.services import zilal_object as zo_
    out = Path(out_dir)
    (out / 'engine').mkdir(parents=True, exist_ok=True)
    body = body_closed(folder, out)
    cap = cap_master(folder, out)
    master = json.loads((LID / 'master.json').read_text(encoding='utf-8'))
    label = label_master(out, body['ground'], master['type']['inks']['eyeshadow'])
    label['sign'] = label_sign_proof(label)
    a4 = a4_page(out)
    plates = [{'plate': 'print', 'what': 'process colour on the wrap paper: the picked sketch upscaled (Lanczos 2×), the '
                                         'hero pair scaled × 0.63 into the front third, the logotype the lid\'s vector × '
                                         '0.80 in the lid\'s rose-gold ink, "LIPSTICK" live'},
              {'plate': 'foil (rose gold)', 'what': 'شفاه: its rim and its hatch re-fitted at the press\'s 0.37 mm; أحمر solid'},
              {'plate': 'relief (emboss)', 'what': 'شفاه\'s scaled silhouette'},
              {'plate': 'label', 'what': 'the bottom label Ø 18: the shade, the net content on two rows, a batch field'}]
    zo_.finish_sheet('the lipstick', zm.REPO / body['files']['flat'], plates, out)
    third = body['front_third']
    drawing = pdw.draw('the Enchanted Rose lipstick', [
        ('body', zm.REPO / body['files']['finish_proof'], WRAP_MM, BLEED_TB_MM, WRAP_MM[1] - 2 * BLEED_TB_MM),
        ('cap', zm.REPO / cap['files']['finish_proof'], WRAP_MM, BLEED_TB_MM, WRAP_MM[1] - 2 * BLEED_TB_MM)],
        CASE_D_MM, third['centre_mm'], WRAP_MM[0] - third['circumference_mm'], cap['ground'], out / 'lipstick-drawing.png')
    pdw.write_record(drawing, out / 'lipstick-drawing.json')
    record = {'schema': 'day12_lipstick_closed/1', 'surface': SURFACE, 'pick': lm.rel(folder),
              'rule': 'D-D12-1: the hero pair × 0.63 into the 20.9 mm front third, the logotype × 0.80, "LIPSTICK" kept, '
                      're-stacked with the sketch\'s gaps; the label\'s ℮ the lid\'s sign at exactly 3 mm; the product drawing',
              'allowed_differences': [
                  'شفاه and أحمر scaled together × 0.63 (the picked pair resampled, not redrawn) and moved into the front third',
                  'the logotype × 0.80 of its sketch scale (cap %.3f mm, over the 2.5 mm floor of a Ø ≤ 20 wrap)'
                  % body['logotype']['cap_height_mm'],
                  'the four re-stacked with the sketch\'s own gaps (%s mm), centred on the front third' % body['closed']['sketch_gaps_mm'],
                  'the hero\'s hatch re-fitted on the scaled silhouette at the press\'s 0.37 mm and 45.186°',
                  'the painted pair cleaned from its sketched place (the stones kept)'],
              'listed': ['"LIPSTICK" keeps its sketched cap %.3f mm, under the 2.5 mm floor the same decision sets'
                         % body['lipstick']['cap_mm']],
              'body': body, 'cap': cap, 'label': label, 'a4': a4, 'plates': plates,
              'finish_sheet': lm.rel(out / 'finish-sheet.png'), 'drawing': drawing}
    lm.write_json(out / 'lipstick.json', record)
    return record


def closed_gate(out):
    """D-D12-1.3: the closed lipstick's record given its eye look (``eye-r0.json``, and ``eye-r1.json`` after a repair)
    and, for the record, the jury's re-judging (``jury/verdict.json``) beside Day 11's 6.1."""
    out = Path(out)
    rec = json.loads((out / 'lipstick.json').read_text(encoding='utf-8'))
    rounds = []
    for label in ('r0', 'r1'):
        path = out / ('eye-%s.json' % label)
        if path.exists():
            e = json.loads(path.read_text(encoding='utf-8'))
            rounds.append({'round': label, 'holds': e['holds'], 'defects': e['defects'], 'cost_usd': e['look']['cost_usd'],
                           'record': lm.rel(path)})
    rec['gate'] = {'rule': 'D-D12-1.3: one eye look on the body and the label, repair ≤ 1', 'rounds': rounds,
                   'holds': bool(rounds and rounds[-1]['holds'])}
    verdict = out / 'jury' / 'verdict.json'
    if verdict.exists():
        v = json.loads(verdict.read_text(encoding='utf-8'))
        day11 = json.loads((OUT / 'jury' / 'verdict.json').read_text(encoding='utf-8'))
        rec['jury'] = {'rule': 'D-D12-1.3: one re-judging for the record, the sheet labelled "J1\'s pick, by default"',
                       'stricter_mean': v['raw']['stricter_mean'], 'means': v['raw']['means'], 'cost_usd': v.get('cost_usd'),
                       'top_issues': v.get('top_issues'), 'record': lm.rel(verdict),
                       'day11': {'stricter_mean': day11['raw']['stricter_mean'], 'record': lm.rel(OUT / 'jury' / 'verdict.json')}}
    lm.write_json(out / 'lipstick.json', rec)
    return rec


# --- the eye's gate (D-D11-7; the owner's answer of 24 October, 2: round 0 plus one repair) -------------------------

LOOK_DPI = 300


STACK_GAP_PX = 8                                 # the white rule between a pick's crop and the master's


def _stack(a, b):
    """Two pictures one above the other, a white rule between, the narrower padded white on its right."""
    gap = STACK_GAP_PX
    w = max(a.shape[1], b.shape[1])
    pad = lambda x: np.concatenate([x, np.full((x.shape[0], w - x.shape[1], 3), 255, np.uint8)], 1)
    return np.concatenate([pad(a), np.full((gap, w, 3), 255, np.uint8), pad(b)], 0)


def _pick_at(rgb_pick, k_pick, box_mm, k_out):
    """A window of the pick (mm on the wrap) at ``k_out`` px/mm: the pick's own pixels repeated (no interpolation)."""
    x0, y0, x1, y1 = box_mm
    s = rgb_pick[int(round(y0 * k_pick)):int(round(y1 * k_pick)), int(round(x0 * k_pick)):int(round(x1 * k_pick))]
    return cv2.resize(s, (int(round((x1 - x0) * k_out)), int(round((y1 - y0) * k_out))), interpolation=cv2.INTER_NEAREST)


def look_images(record, out):
    """The look's seven pictures (each checked under the eye's limits): the lid (the language); the pick's two wraps and
    the master's two wraps (fitted); the hero, and the logotype with "LIPSTICK" and where the net line was, each at
    1 : 1 (300 PPI) with the pick above and the master below; the body's finish proof; the cap's logo beside the label."""
    from apps.pipeline.services import zilal_object as zo_
    folder = zm.REPO / record['pick']
    crops = out / 'crops'
    crops.mkdir(parents=True, exist_ok=True)
    pb_, _ = trim_rows(load_wrap(folder, 'body')[0])
    pc_, _ = trim_rows(load_wrap(folder, 'cap')[0])
    k_pick = pb_.shape[1] / WRAP_MM[0]
    mb = np.asarray(Image.open(zm.REPO / record['body']['files']['flat']).convert('RGB'))
    mc = np.asarray(Image.open(zm.REPO / record['cap']['files']['flat']).convert('RGB'))
    k_out = mb.shape[1] / WRAP_MM[0]
    pick_pair = zo_.fitted(_stack(pb_, pc_), crops / 'pick-wraps.png')
    master_pair = zo_.fitted(_stack(mb, mc), crops / 'master-wraps.png')
    images = [zo_.lid_language(out),
              (pick_pair, 'THE PICK: the body wrap above the cap wrap, as sketched (fitted)'),
              (master_pair, 'THE MASTER: the body wrap above the cap wrap, as printed (fitted)')]
    boxes = record['body']['boxes_mm']
    hx0, hy0, hx1, hy1 = boxes['hero']
    lx0, ly0, lx1, ly1 = boxes['logotype']
    net = [v / k_pick for v in record['body']['net_line']['sketch_box_px']]
    lower = (min(lx0, net[0]) - 2, ly0 - 1, max(lx1, net[2]) + 2, min(net[3] + 1.5, WRAP_MM[1]))
    for name, box, words in (('hero', (hx0, hy0, hx1, hy1), 'the hero شفاه with أحمر at 1 : 1: the pick above, the master '
                                                             'below (its foil and relief show only in the finish proof)'),
                             ('lower', lower, 'the logotype, "LIPSTICK" and where the net line was, at 1 : 1: the pick '
                                              'above, the master below')):
        a = _pick_at(pb_, k_pick, box, k_out)
        x0, y0, x1, y1 = box
        b = mb[int(round(y0 * k_out)):int(round(y1 * k_out)), int(round(x0 * k_out)):int(round(x1 * k_out))]
        path = crops / ('look-%s.png' % name)
        Image.fromarray(_stack(a, b[:a.shape[0], :a.shape[1]])).save(path, dpi=(LOOK_DPI, LOOK_DPI))
        lm._image_block(path)
        images.append((path, words))
    images.append((zo_.fitted(zm.REPO / record['body']['files']['finish_proof'], crops / 'body-finish-proof.png'),
                   'the body\'s finish proof: the foil (rose gold) and the relief rendered as material'))
    cx0, cy0, cx1, cy1 = record['cap']['logo']['placed_mm']
    cap_crop = mc[int((cy0 - 3) * k_out):int((cy1 + 3) * k_out), int((cx0 - 3) * k_out):int((cx1 + 3) * k_out)]
    cap_big = cv2.resize(cap_crop, (cap_crop.shape[1] * 2, cap_crop.shape[0] * 2), interpolation=cv2.INTER_NEAREST)
    master_logo = approved_logo_alone(record, cap_big.shape, crops)
    label = label_with_die(record, crops, cap_big.shape[0] * 2 + 16)
    left = np.concatenate([cap_big, np.full((16, cap_big.shape[1], 3), 255, np.uint8), master_logo], 0)
    h = max(left.shape[0], label.shape[0])
    pad = lambda x: np.concatenate([x, np.full((h - x.shape[0], x.shape[1], 3), 255, np.uint8)], 0)
    side = np.concatenate([pad(left), np.full((h, 16, 3), 255, np.uint8), pad(label)], 1)
    path = crops / 'look-cap-logo-and-label.png'
    Image.fromarray(side).save(path)
    lm._image_block(path)
    images.append((path, 'left: the cap\'s logo (2× print) above the approved logo master drawn alone at the same scale; '
                         'right: the bottom label Ø 18 with its die (magenta) and its 1 mm safe ring (blue, dashed) drawn'))
    return images


def approved_logo_alone(record, shape, crops):
    """The approved logo master drawn alone (lm.logo_parts, the same ink, on the indigo) at the cap's placed size, 2×
    the print scale — what the cap's logo is, to read its own strokes against."""
    import fitz
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, Rect, SolidFill
    x0, y0, x1, y1 = record['cap']['logo']['placed_mm']
    w, h = x1 - x0 + 6, y1 - y0 + 6
    doc = Document(page_w=w, page_h=h, metadata={'typography_surface': SURFACE}, root=Group(name='LOGO', children=[
        Rect(name='ground', x=0.0, y=0.0, w=w, h=h, fill=SolidFill(color=Color.from_hex(record['body']['ground']))),
        Group(name='logo', role='logo', children=lm.logo_parts((3.0, 3.0, x1 - x0, y1 - y0), record['cap']['logo']['ink'],
                                                               foil_letters=False))]))
    path = crops / 'approved-logo-alone.ai'
    emit_pdf_ai(doc, str(path))
    png = crops / 'approved-logo-alone.png'
    with fitz.open(str(path)) as d:
        pix = d[0].get_pixmap(dpi=int(round(2 * LOOK_DPI)), alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    img = cv2.resize(img, (shape[1], shape[0]), interpolation=cv2.INTER_AREA)
    Image.fromarray(img).save(png)
    return img


def label_with_die(record, crops, height):
    """The label's flat with its die circle (magenta) and its 1 mm safe ring (blue, dashed) drawn over it."""
    label = np.asarray(Image.open(zm.REPO / record['label']['files']['flat']).convert('RGB')).copy()
    k = label.shape[1] / (LABEL_D_MM + 2 * LABEL_BLEED_MM)
    c = (int(round(label.shape[1] / 2)), int(round(label.shape[0] / 2)))
    cv2.circle(label, c, int(round(LABEL_D_MM / 2 * k)), (220, 0, 140), 3, lineType=cv2.LINE_AA)
    r = int(round((LABEL_D_MM / 2 - LABEL_SAFE_MM) * k))
    for a in range(0, 360, 12):
        cv2.ellipse(label, c, (r, r), 0, a, a + 6, (0, 150, 230), 2, lineType=cv2.LINE_AA)
    out = cv2.resize(label, (height, height), interpolation=cv2.INTER_AREA)
    Image.fromarray(out).save(crops / 'label-with-die.png')
    return out


def lipstick_look(record, call, round_no, label=None):
    """The lipstick's eye round: the seven pictures and the owner's rule with what is allowed; notes kept short so the
    answer fits."""
    from apps.pipeline.services import zilal_object as zo_
    out = OUT
    images = look_images(record, out)
    b = record['body']
    text = ('THE LIPSTICK GATE (Day 11, D-D11-7 and D-D11-11). A round lipstick, Ø 20 mm, its body and cap wrapped in '
            'printed paper (each 64.8 × 42 mm, closing at a seam at the back), a bottom label Ø 18. THE OWNER\'S RULE: '
            'the master by the preservation path from his pick (shown); the body keeps the hero شفاه with أحمر, the '
            'logotype and "LIPSTICK" exactly as sketched, and the sketch\'s painted net line is cleaned out — the net '
            'content goes to the bottom label on two rows ("3.5 g ℮" / "0.12 oz", figures ≥ 2 mm, the ℮ at its legal 3 mm '
            'though taller than its figures); the cap the stones and the logo. The lid\'s idea: %s. Images: %s.\n\n'
            'ALLOWED (the path): the pictures enlarged 2× by Lanczos and their softness; شفاه traced from the sketch '
            '(within 0.3 mm) and foiled in rose gold as the lid\'s hero — a rim, a groove and a hatch at the sketch\'s '
            'angle but at the press\'s pitch %.2f mm (the painted hatch is %.2f mm, under what foil holds), its silhouette '
            'embossed, the sketch\'s raster beneath; أحمر foiled solid; "Enchanted Rose" the LID\'s own vector scaled ×%.3f '
            'onto the sketch\'s logotype (cap height %.2f mm) in the lid\'s rose-gold ink, its painted letters cleaned '
            'beneath; "LIPSTICK" live in the lid\'s face at the sketch\'s size and place; the net line\'s place filled '
            'with the ground; the seam a 2 mm feathered band at the back (mean ΔE00 %.2f across the join); the cap\'s '
            'logo the approved vector in ink over its cleaned painted logo; the label composed in the lid\'s language. '
            'ANYTHING ELSE is a defect: a letter, stone or colour changed or lost; a ghost of a cleaned element; a '
            'misplaced or wrongly sized logotype or line; a seam or a white line; anything off the lid\'s language. '
            'Judge every image as a senior packaging designer, in AT MOST TWO SENTENCES per image, and list every defect '
            'with its place, severity and the smallest repair. Answer in JSON.' % (
                zo_.IDEA, '; '.join('%d %s' % (i + 1, w_) for i, (_, w_) in enumerate(images)),
                b['hero']['hatch']['stroke']['pitch_mm'], b['hero']['hatch']['painted_pitch_mm'],
                b['logotype']['scale'], b['logotype']['cap_height_mm'], b['seam']['after']['mean']))
    text += ('\n\nTHE LABEL, in D-D11-7\'s own words: "a bottom label Ø 18 with the shade and a batch field"; its facts '
             'name the shade "Wild Rose" (⟪PROVISIONAL⟫, the owner\'s to correct). D-D11-11 adds the net content on two rows.')
    if round_no >= 1:
        rows = record['label']['rows']
        text += ('\n\nREPAIR 1 (after round 0 named the label\'s "Wild Rose", a doubled stem at the cap logo\'s R and the '
                 'label\'s undrawn die): (1) "Wild Rose" is the shade D-D11-7 names (above); (2) the approved logo master '
                 'is drawn alone beside the cap\'s logo at the same scale — the thin stroke beside the R is the master\'s '
                 'own drawing; (3) the label\'s die and its 1 mm safe ring are '
                 'drawn: every row stands inside the ring, the nearest corner %.2f mm inside the die. Judge whether each is '
                 'answered and whether anything new is wrong.' % min(r_['die_clearance_mm'] for r_ in rows))
    return zo_.surface_look(out, 'lipstick', images, text, call, round_no, label)


def gate_record():
    """The lipstick's gate as the eye's rounds say it (eye-r0.json, eye-r1.json), merged into lipstick.json: each round's
    verdict and defects; the $0 corrections made after the gate (the label's ℮ boxed at its own width, so a word space
    stands between it and the g; the batch rule shortened clear of the safe ring), not looked at again; and where the
    eye and a measurement disagree (the ℮ is the house's sign as the lid draws it)."""
    rounds = []
    for name in ('eye-r0.json', 'eye-r1.json'):
        rec = json.loads((OUT / name).read_text(encoding='utf-8'))
        rounds.append({'file': lm.rel(OUT / name), 'round': rec['round'], 'answered': rec['answered'],
                       'holds': rec['holds'], 'cost_usd': rec['look']['cost_usd'],
                       'defects': [{k: d[k] for k in ('where', 'what', 'severity')} for d in rec['defects']]})
    record = json.loads((OUT / 'lipstick.json').read_text(encoding='utf-8'))
    rows = record['label']['rows']
    record['gate'] = {
        'rounds': rounds, 'holds': rounds[-1]['holds'], 'repairs': 1,
        'after_the_gate': {'fixed': ['the ℮ abutting the g: the sign is now boxed at its own width (%.3f of its height), '
                                     'a word space before it' % sign_aspect(),
                                     'the batch rule shortened to 4 mm: its row stands %.2f mm inside the die, %.2f mm '
                                     'inside the 1 mm safe ring' % ([r for r in rows if r['row'] == 'batch'][0]['die_clearance_mm'],
                                                                     [r for r in rows if r['row'] == 'batch'][0]['die_clearance_mm'] - LABEL_SAFE_MM)],
                           'said': 'corrected at $0 after round 1 (the one repair spent), not looked at again — listed '
                                   'for the owner'},
        'measured_vs_eye': {'the_sign': 'the label\'s ℮ is lid_master.sign_segments — the house\'s estimated sign '
                                        '(Montserrat Regular\'s ℮), the very glyph the lid\'s net line draws; the eye read '
                                        'it, at 3 mm beside 2 mm figures, as a serif "e"'},
        'rule': 'D-D11-7: the eye as the gate, repair ≤ 1; D-D11-10: no third round; the owner\'s answer of 24 October, 2: '
                'the eye past its soft line for this gate'}
    lm.write_json(OUT / 'lipstick.json', record)
    return record['gate']
