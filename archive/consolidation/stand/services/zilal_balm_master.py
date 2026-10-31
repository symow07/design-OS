"""Day 12 §3 (D-D12-3) — the lip balm's master by the lipstick's path (D-D11-7, D-D12-1), at $0.

The pick is ``zilal_balm.the_pick()`` read when the build runs (the owner's PICK file, else J1's highest-ranked sketch
that passes the front-third check): a folder under ``docs/audit/day-12/balm/sketches/`` holding ``body.png`` and
``cap.png``, each cropped at its drawn trim, and ``crop.json`` (the crop's box on the sheet and the measured front-third
check). The facts are D-D11-8's (⟪PROVISIONAL⟫): a slim round stick Ø 18, the body wrap 58.5 × 42 mm and the cap wrap
58.5 × 32 mm (the circumference π · 18 plus a 1.951 mm overlap, by the visible 40 and 30 mm plus 1 mm bleed top and
bottom), a bottom label Ø 16.

Nothing is redrawn: the wraps are the sketch's own pixels made printable, by the lipstick's functions where they take
the picture's own scale (``zilal_lipstick_master``: the hero's reader and foil, the logotype's source and placing, the
cleaning's grain, the line's fit, the cap's logo), and by this module's own copies, sized by explicit parameters, where
the lipstick's read its 64.8 × 42 mm wrap, its Ø 20 overlap or its Ø 18 label (each copy names its original).

What the balm's sheet adds: the sheet's DASHED FRONT-THIRD BOX, which the model kept in both wraps (thin light dashes at
the pixels the sheet drew them, each with a darker rim) — not artwork. It is found from the picture (``find_dashes``:
each line's ridge of L* searched about the sheet's own position) and its dashes placed along each line (``dash_sites``),
then cleaned first, at the sketch's pixels (``clean_dashes``): a pixel is dash only where it is a thin ridge across the
line — lighter than EACH side by over 6 L* (a stone edge or a vein along the line is a step, lighter than one side
only) — with its rim (the pixels next to it across the line that stand off their own row beside the dash); each is
filled from the direction whose two clean ends agree and which, under the dash's own colour, best explains the pixel
as painted (so, on a stone, mostly the stone's own pixels; not always where the stone is a speck narrower than the
dash's band, nor where a thin vein crosses at a slant — those places are read by the proofs and looked at). Two
proofs on the final plate: ``dash_proof`` (the ridge per dash site before and after, against a stated bar, with the
uncleaned upscale as its control on every line; each site's peak recorded beside it) and ``stones_proof`` (the
stones of 0.3 mm² or more, the dash's ridge pixels taken out and eroded 2 px, unchanged by ΔE76 ≤ 2).

[Day 12, D-D12-8: the balm's one repair after the eye's round 0] The eye saw the cleaning's ghost: a faint darker
rectangle behind the stack (the word boxes filled tile by tile from calm ground, a tone step at their edges and at the
tiles' seams) and faint straight lines where the dashed box was (the fill's own trace, and the sketch's own tone step
across its guide). ``rebuild_ground`` rebuilds that ground on GROUND PIXELS ONLY (``ground_mask``: never a stone, a
vein, a letter or the hero's carried raster): the tone a smooth field fitted to the ground just outside (Laplace's
equation, held at the untouched ground's local tone, a first-order fit), the grain the ground's own texture from random 1 mm patches of
the untouched ground near by (variance-preserving weights, no tile repeated). ``ghost_proof`` proves no straight edge
is left: along each dash line and each cleaned box's sides (and the old fill's tile seams), on ground pixels, the step
across the edge and the line on it per 1 mm bin, against bars read on the uncleaned sketch's own ground on parallel
lines away from any edge — with the plate before the rebuild as its control (it fails where the eye saw the ghost).
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import zilal_balm as zb
from apps.pipeline.services import zilal_display as zd
from apps.pipeline.services import zilal_lipstick_master as zlm
from apps.pipeline.services import zilal_master as zm

REPO = lm.REPO
OUT = zb.BALM / 'master'
LID12 = zd.LID12                                  # the Day 12 lid master (D-D12-9's reader): its inks and measures
SURFACE = 'apps/pipeline/services/zilal_balm_master.py::build'

BODY_MM = zb.WRAPS_MM['body']                     # D-D12-3: 58.5 × 42 mm
CAP_MM = zb.WRAPS_MM['cap']                       # D-D12-3: 58.5 × 32 mm
CASE_D_MM = zb.CASE_D_MM                          # Ø 18 (⟪PROVISIONAL⟫)
CIRCUMFERENCE_MM = float(np.pi * CASE_D_MM)
OVERLAP_MM = BODY_MM[0] - CIRCUMFERENCE_MM        # 1.951 mm: the right end lies over the left start by this much
BLEED_TB_MM = zb.BLEED_TB_MM                      # 1 mm bleed top and bottom, inside each wrap's height
SAFE_TB_MM = zb.SAFE_TB_MM                        # nothing essential within 2 mm of the top and bottom
UP = lm.UP
CAP_FLOOR_SMALL_WRAP_MM = zlm.CAP_FLOOR_SMALL_WRAP_MM   # D-D12-1.1: on wraps of Ø ≤ 20 mm the cap floor is 2.5 mm
PROOF_PAGE_W_MM = zlm.PROOF_PAGE_W_MM             # the finish proof read on a wider copy of the page (its plate label)
LOGO_ASPECT = 0.20859051088028435                 # the approved logo's height over width (palette_box, lid_master)


def lid_master_record():
    """The Day 12 lid master's record (its inks, its name's measures, its logo's ink)."""
    return json.loads((LID12 / 'master.json').read_text(encoding='utf-8'))


def crop_record(folder):
    return json.loads((Path(folder) / 'crop.json').read_text(encoding='utf-8'))


# --- the trim (zilal_lipstick_master.trim_rows at the wrap's own size) -----------------------------------------------

def trim_rows(rgb, wrap_mm):
    """``zilal_lipstick_master.trim_rows`` for a wrap of ``wrap_mm`` (w, h): ONE scale ``k`` = the picture's width over
    the wrap's (px/mm), the rows that make its height at that scale kept, the excess cut evenly top and bottom (a
    shortfall filled by the picture's own mirrored edge rows). Returns the picture and what was done, with the rows the
    picture moved by (``shift_rows_px``: the sketch's row y is the trimmed picture's y + shift)."""
    h, w = rgb.shape[:2]
    k = w / wrap_mm[0]
    rows = int(round(wrap_mm[1] * k))
    cut = h - rows
    top = cut // 2
    if cut >= 0:
        out = rgb[top:top + rows]
        did = 'cut %d rows (%d top, %d bottom)' % (cut, top, cut - top)
        shift = top
    else:
        need = -cut
        out = cv2.copyMakeBorder(rgb, need // 2, need - need // 2, 0, 0, cv2.BORDER_REFLECT_101)
        did = 'filled %d rows by the picture\'s own mirrored edge rows' % need
        shift = -(need // 2)
    return out, {'px_per_mm': round(k, 5), 'sketch_px': [w, h], 'rows_kept': rows, 'shift_rows_px': int(shift),
                 'height_mm_at_k': round(rows / k, 4), 'did': did, 'wrap_mm': list(wrap_mm),
                 'aspect_of_the_sketch': round(w / h, 4), 'aspect_true': round(wrap_mm[0] / wrap_mm[1], 4),
                 'said': 'one scale for both axes (nothing stretched); the picture placed from the trim\'s top-left at '
                         '%.1f mm wide, its height %.3f mm at that scale' % (wrap_mm[0], rows / k)}


# --- the sheet's dashed front-third box: found, cleaned, proved gone --------------------------------------------------

DASH_SEARCH_PX = 4                                # each line searched ±4 px about the sheet's own position
DASH_FLANK_PX = 4                                 # the finder's ridge: L* on the line less the mean of L* 4 px either side
DASH_BAND_PX = 2                                  # the band cleaned: the found line ±2 px across
DASH_SIDE_PX = (3, 4)                             # each side read 3 and 4 px from the line (the darker of the two)
DASH_RIDGE_L = 6.0                                # a dash pixel: lighter than EACH side by over 6 L*
DASH_RIM_L = 3.0                                  # its rim: next to it across the line, off its own row by over 3 L*
DASH_ROW_READ_PX = 3                              # a row's own level: its median 3 px along either side of the zone
DASH_ON_PX = zb.DASH_PX[0]                        # a dash 6 px long (the sheet's)
DASH_RUN_PX = (4, 9)                              # an anchor: a run of ridge 4 to 9 px long …
DASH_QUIET_PX = 3                                 # … with no ridge over half the margin 3 px either side
DASH_PERIOD_READ_PX = (9, 15)                     # the anchors' gaps read as one period (the sheet's 12 px)
DASH_ZONE_PX = 2                                  # a dash's zone: its site ±2 px along the line
DASH_REFINE_PX = 3                                # a site between anchors moved up to ±3 px onto its own dash …
DASH_SITE_GAP_PX = 4                              # … never within 4 px of the next site
DASH_REACH_PX = 10                                # the fill walks up to 10 px each way to a clean pixel
DASH_DIRECTIONS = ((1, 0), (0, 1), (1, 1), (1, -1), (2, 1), (2, -1), (1, 2), (1, -2), (3, 1), (3, -1))   # (along, across)
DASH_EXPLAIN_WEIGHT = 2.0                         # the fill's score: the ends' disagreement + 2 × the pixel unexplained
DASH_SMOOTH_PX = 1                                # each score summed with the next pixel's either side along the line
DASH_PASSES = 2                                   # twice: at a corner one line's dash is the other's side until cleaned
DASH_COLOUR_GRID = tuple(range(150, 256, 5))      # the dash's own colour searched on this grid of sRGB levels
DASH_COLOUR_AGREE = 12.0                          # its samples: a dash whose row either side agrees within 12 levels
DASH_GONE_L = 6.0                                 # gone: no dash site over 6 L* of ridge (the cleaning's own margin)
STONE_ERODE_PX = 2                                # the stones read 2 px inside their edges (and the dash's ridge)
STONE_DE76_MAX = 2.0                              # unchanged: ΔE76 ≤ 2


def expected_dash_box(crop, key, trim):
    """The sheet's dashed box (``zilal_balm.front_third_px`` on the sheet's box) in the trimmed picture's pixels: less
    the crop's origin on the sheet, less the rows the trim moved."""
    wrap = crop['wraps'][key]
    sheet_box = wrap['sheet_box_px']
    third, _ = zb.front_third_px(key, tuple(sheet_box))
    ox, oy = wrap['box_px'][0], wrap['box_px'][1] + trim['shift_rows_px']
    return [int(third[0] - ox), int(third[1] - oy), int(third[2] - ox), int(third[3] - oy)]


def _lines_of(box):
    """A box's four sides as lines: (name, orientation, position, from, to) in px; 'v' a column, 'h' a row."""
    x0, y0, x1, y1 = box
    return [('left', 'v', x0, y0, y1), ('right', 'v', x1, y0, y1), ('top', 'h', y0, x0, x1), ('bottom', 'h', y1, x0, x1)]


def ridge(light, orient, pos, lo, hi, flank):
    """The finder's reading: L* along a line (a column ``pos`` from row ``lo`` to ``hi`` for 'v', a row for 'h') less
    the mean of the lines ``flank`` px either side: a thin light line reads as a positive ridge."""
    if orient == 'v':
        return light[lo:hi, pos] - 0.5 * (light[lo:hi, pos - flank] + light[lo:hi, pos + flank])
    return light[pos, lo:hi] - 0.5 * (light[pos - flank, lo:hi] + light[pos + flank, lo:hi])


def find_dashes(rgb, box):
    """Each side of the dashed box found from the picture: the column (or row) within ±4 px of the sheet's position
    whose ridge (``ridge``) has the largest mean along the side, from corner to corner."""
    light = lm.srgb_to_lab(rgb)[..., 0].astype(np.float64)
    lines = []
    for name, orient, pos, lo, hi in _lines_of(box):
        best, best_mean = None, None
        for p in range(pos - DASH_SEARCH_PX, pos + DASH_SEARCH_PX + 1):
            mean = float(ridge(light, orient, p, lo, hi, DASH_FLANK_PX).mean())
            if best_mean is None or mean > best_mean:
                best, best_mean = p, mean
        lines.append({'side': name, 'orient': orient, 'sheet_pos_px': int(pos), 'found_pos_px': int(best),
                      'from_px': int(lo), 'to_px': int(hi), 'ridge_mean': round(best_mean, 3)})
    return lines


def line_px(line, offset, lo, hi):
    """The pixels (rows, columns) of the line moved ``offset`` px across, from ``lo`` to ``hi`` px along."""
    t = np.arange(lo, hi)
    p = np.full_like(t, line['found_pos_px'] + offset)
    return (t, p) if line['orient'] == 'v' else (p, t)


def line_ridge(light, line):
    """L* on the band's rows (the line ±2 px across, along its whole length) and each row's ridge: its L* less the
    LARGER of its two sides (each side the darker of the pixels 3 and 4 px from the line) — over 0 only where the
    pixel is lighter than each side separately."""
    lo, hi = line['from_px'], line['to_px']

    def at(d):
        return light[line_px(line, d, lo, hi)]
    side_a = np.minimum(at(-DASH_SIDE_PX[0]), at(-DASH_SIDE_PX[1]))
    side_b = np.minimum(at(DASH_SIDE_PX[0]), at(DASH_SIDE_PX[1]))
    rows = np.stack([at(d) for d in range(-DASH_BAND_PX, DASH_BAND_PX + 1)])
    return rows, rows - np.maximum(side_a, side_b)


def _runs(flags):
    """The runs of True in a 1-D array: (start, end) pairs."""
    runs, t, n = [], 0, len(flags)
    while t < n:
        if flags[t]:
            u = t
            while u < n and flags[u]:
                u += 1
            runs.append((t, u))
            t = u
        else:
            t += 1
    return runs


def dash_sites(light, line):
    """Where each dash lies along a line (px from its start, each 6 px long), read on the uncleaned sketch: the
    ANCHORS are the dashes plain to see (a run of ridge over 6 L* on the line ±1 px, 4 to 9 px long, nothing over half
    that 3 px either side); the period is the anchors' median gap of about one period; between two anchors the dashes
    are spaced evenly at that period, then each moved up to ±3 px onto its own ridge (never within 4 px of the next);
    before the first and after the last, at the period."""
    _, ridge_rows = line_ridge(light, line)
    r = ridge_rows[DASH_BAND_PX - 1:DASH_BAND_PX + 2].max(axis=0)
    n = len(r)
    anchors = []
    for a, b in _runs(r > DASH_RIDGE_L):
        quiet = np.r_[max(a - DASH_QUIET_PX, 0):a, b:min(b + DASH_QUIET_PX, n)]
        if DASH_RUN_PX[0] <= b - a <= DASH_RUN_PX[1] and len(quiet) and not (r[quiet] > DASH_RIDGE_L / 2).any():
            anchors.append((a + b) / 2.0)
    if len(anchors) < 2:
        raise ValueError('the %s line shows %d plain dashes: its period cannot be read' % (line['side'], len(anchors)))
    gaps = np.diff(anchors)
    one = gaps[(gaps > DASH_PERIOD_READ_PX[0]) & (gaps < DASH_PERIOD_READ_PX[1])]
    if not len(one):
        raise ValueError('the %s line\'s plain dashes are never one period apart' % line['side'])
    period = float(np.median(one))
    centres = [[anchors[0], True]]
    for c0, c1 in zip(anchors[:-1], anchors[1:]):
        m = max(int(round((c1 - c0) / period)), 1)
        centres += [[c0 + (c1 - c0) * j / m, False] for j in range(1, m)]
        centres.append([c1, True])
    while centres[0][0] - period + DASH_ON_PX / 2.0 > 0:
        centres.insert(0, [centres[0][0] - period, False])
    while centres[-1][0] + period - DASH_ON_PX / 2.0 < n:
        centres.append([centres[-1][0] + period, False])
    sites = [[int(round(c - DASH_ON_PX / 2.0)), int(round(c + DASH_ON_PX / 2.0)), anchored] for c, anchored in centres]
    lifted = np.clip(r, 0.0, None)
    for i, s in enumerate(sites):
        if s[2]:
            continue
        best = None
        for shift in range(-DASH_REFINE_PX, DASH_REFINE_PX + 1):
            a, b = s[0] + shift, s[1] + shift
            if (i > 0 and a - sites[i - 1][1] < DASH_SITE_GAP_PX) or (i + 1 < len(sites)
                                                                       and sites[i + 1][0] - b < DASH_SITE_GAP_PX):
                continue
            seg = lifted[max(a, 0):max(min(b, n), 0)]
            if len(seg) < DASH_ON_PX // 2:
                continue
            if best is None or float(seg.mean()) > best[0]:
                best = (float(seg.mean()), a, b)
        if best is not None:
            s[0], s[1] = best[1], best[2]
    return {'sites': [(int(a), int(b)) for a, b, _ in sites], 'anchors': len(anchors), 'period_px': round(period, 3)}


def _zone(sites, n):
    zone = np.zeros(n, dtype=bool)
    for a, b in sites:
        zone[max(a - DASH_ZONE_PX, 0):max(min(b + DASH_ZONE_PX, n), 0)] = True
    return zone


def _row_gaps(sites, zone, n):
    """Each site's zone (from, to) and the clean pixels 3 px along either side of it (its row's own level)."""
    out = []
    for a, b in sites:
        z0, z1 = max(a - DASH_ZONE_PX, 0), max(min(b + DASH_ZONE_PX, n), 0)
        g = np.r_[max(z0 - DASH_ROW_READ_PX, 0):z0, z1:min(z1 + DASH_ROW_READ_PX, n)]
        out.append((z0, z1, g[~zone[g]]))
    return out


def dash_pixels(rgb, lines, sites):
    """The dash's pixels on one pass: in each dash's zone (its site ±2 px along, the line ±2 px across), the RIDGE
    pixels — lighter than each side by over 6 L* (``line_ridge``) — and their RIM: the pixels next to a ridge pixel
    across the line that stand off their own row's level beside the dash (the median of the clean pixels 3 px along
    either side of the zone) by over 3 L* (the dash's anti-aliased edge and its darker halo). Returns (ridge, rim)."""
    light = lm.srgb_to_lab(rgb)[..., 0].astype(np.float64)
    core = np.zeros(rgb.shape[:2], dtype=bool)
    rim = np.zeros(rgb.shape[:2], dtype=bool)
    for ln in lines:
        lo, hi = ln['from_px'], ln['to_px']
        n = hi - lo
        rows, ridge_rows = line_ridge(light, ln)
        zone = _zone(sites[ln['side']], n)
        c = (ridge_rows > DASH_RIDGE_L) & zone[None, :]
        off = np.zeros_like(c)
        for z0, z1, g in _row_gaps(sites[ln['side']], zone, n):
            if len(g) and z1 > z0:
                level = np.median(rows[:, g], axis=1)[:, None]
                off[:, z0:z1] = np.abs(rows[:, z0:z1] - level) > DASH_RIM_L
        beside = np.zeros_like(c)
        beside[1:] |= c[:-1]
        beside[:-1] |= c[1:]
        e = beside & off & ~c
        for i, d in enumerate(range(-DASH_BAND_PX, DASH_BAND_PX + 1)):
            rr, cc = line_px(ln, d, lo, hi)
            core[rr[c[i]], cc[c[i]]] = True
            rim[rr[e[i]], cc[e[i]]] = True
    return core, rim


def dash_colour(rgb, lines, sites):
    """The dash's own colour W, read from the picture: at each site whose row either side agrees (within 12 sRGB
    levels), the dash's strongest row read as W laid over what lies beside it at some opacity a (painted = a W +
    (1 − a) beside); W the grid colour whose fit leaves the least median residual. Returns W and its fit."""
    f = rgb.astype(np.float64)
    light = lm.srgb_to_lab(rgb)[..., 0].astype(np.float64)
    painted, beside = [], []
    for ln in lines:
        lo, hi = ln['from_px'], ln['to_px']
        _, ridge_rows = line_ridge(light, ln)
        for a, b in sites[ln['side']]:
            if a < DASH_ON_PX // 2 or b > hi - lo - DASH_ON_PX // 2:
                continue
            d = int(np.argmax(ridge_rows[:, a:b].mean(axis=1))) - DASH_BAND_PX
            rr, cc = line_px(ln, d, lo, hi)
            left = f[rr[a - 3:a - 1], cc[a - 3:a - 1]].mean(axis=0)
            right = f[rr[b + 1:b + 3], cc[b + 1:b + 3]].mean(axis=0)
            if np.abs(left - right).max() > DASH_COLOUR_AGREE:
                continue
            painted.append(f[rr[a + 1:b - 1], cc[a + 1:b - 1]].mean(axis=0))
            beside.append((left + right) / 2.0)
    painted, beside = np.array(painted), np.array(beside)
    best = None
    for w in ((x, y, z) for x in DASH_COLOUR_GRID for y in DASH_COLOUR_GRID for z in DASH_COLOUR_GRID):
        tv = np.array(w, np.float64) - beside
        a = ((painted - beside) * tv).sum(axis=1) / (tv * tv).sum(axis=1)
        res = float(np.median(np.linalg.norm(painted - beside - a[:, None] * tv, axis=1)))
        if best is None or res < best[0]:
            best = (res, w, float(np.median(a)))
    return best[1], {'rgb': list(best[1]), 'opacity_median': round(best[2], 3), 'residual_median': round(best[0], 2),
                     'samples': int(len(painted)),
                     'said': 'the dash read as its own colour laid over what lies beside it (fitted on a %d-level grid)'
                             % len(DASH_COLOUR_GRID)}


def _seg_dist(p, a, b):
    """How far the colour ``p`` lies from the segment of colours ``a`` → ``b``."""
    ab = b - a
    t = float(np.clip(np.dot(p - a, ab) / max(float(np.dot(ab, ab)), 1e-9), 0.0, 1.0))
    return float(np.linalg.norm(p - (a + t * ab)))


def fill_dashes(rgb, mask, vertical, colour):
    """Each dash pixel filled from a direction (along the line, across it, or one of eight slants): along it, the first
    clean pixel each way (within 10 px) and the value between them; the score the two ends' disagreement plus twice the
    distance of the painted pixel from that value lightened toward the dash's own colour (or darkened, for its rim) —
    so where the dash crossed a stone its own pixels usually explain it best (the ground explains a dash laid on a
    stone poorly, but not never: the ends' disagreement can outweigh it at a speck narrower than the band, or where a
    thin vein crosses at a slant none of the directions follows); the scores summed with the next dash pixel's either
    side along the line (one direction through a run); the least taken. (A pixel with no clean end in any direction
    within 10 px is left as painted.) Returns the picture and the pixels so left."""
    f = rgb.astype(np.float64)
    h, w = mask.shape
    ys, xs = np.nonzero(mask)
    index = -np.ones(mask.shape, dtype=int)
    index[ys, xs] = np.arange(len(ys))
    nd = len(DASH_DIRECTIONS)
    score = np.full((len(ys), nd), np.inf)
    value = np.zeros((len(ys), nd, 3))
    white = np.asarray(colour, np.float64)
    black = np.zeros(3)
    for i, (y, x) in enumerate(zip(ys, xs)):
        obs = f[y, x]
        for j, (along, across) in enumerate(DASH_DIRECTIONS):
            dy, dx = (along, across) if vertical[y, x] else (across, along)
            ends = []
            for sgn in (1, -1):
                k = 1
                while k <= DASH_REACH_PX:
                    yy, xx = y + sgn * k * dy, x + sgn * k * dx
                    if not (0 <= yy < h and 0 <= xx < w) or not mask[yy, xx]:
                        break
                    k += 1
                yy, xx = y + sgn * k * dy, x + sgn * k * dx
                if k <= DASH_REACH_PX and 0 <= yy < h and 0 <= xx < w:
                    ends.append((k, f[yy, xx]))
            if len(ends) < 2:
                continue
            (k1, e1), (k2, e2) = ends
            v = (e1 * k2 + e2 * k1) / (k1 + k2)
            score[i, j] = float(np.linalg.norm(e1 - e2)) + DASH_EXPLAIN_WEIGHT * min(_seg_dist(obs, v, white),
                                                                                     _seg_dist(obs, v, black))
            value[i, j] = v
    out = f.copy()
    kept = np.zeros(mask.shape, dtype=bool)
    for i, (y, x) in enumerate(zip(ys, xs)):
        sy, sx = (1, 0) if vertical[y, x] else (0, 1)
        total = score[i].copy()
        for s in range(1, DASH_SMOOTH_PX + 1):
            for sgn in (1, -1):
                yy, xx = y + sgn * s * sy, x + sgn * s * sx
                if 0 <= yy < h and 0 <= xx < w and index[yy, xx] >= 0:
                    nb = score[index[yy, xx]]
                    total = total + np.where(np.isfinite(nb), nb, 0.0)
        total = np.where(np.isfinite(score[i]), total, np.inf)
        if not np.isfinite(total).any():
            kept[y, x] = True
            continue
        out[y, x] = value[i, int(np.argmin(total))]
    return np.clip(np.round(out), 0, 255).astype(np.uint8), kept


def clean_dashes(rgb, lines):
    """The dashes cleaned at the sketch's pixels, first (so nothing after reads them as ink or stone): the sites
    (``dash_sites``, read once on the uncleaned sketch), the dash's own colour (``dash_colour``), then twice (a corner's
    dash is the other line's side until that line is cleaned) its ridge and rim pixels (``dash_pixels``) filled
    (``fill_dashes``). Returns the cleaned picture, every ridge pixel, every pixel filled, the sites and the record."""
    light = lm.srgb_to_lab(rgb)[..., 0].astype(np.float64)
    read = {ln['side']: dash_sites(light, ln) for ln in lines}
    sites = {k_: v['sites'] for k_, v in read.items()}
    colour, colour_rec = dash_colour(rgb, lines, sites)
    vertical = np.zeros(rgb.shape[:2], dtype=bool)
    for ln in lines:
        if ln['orient'] == 'v':
            p = ln['found_pos_px']
            vertical[max(ln['from_px'] - DASH_BAND_PX, 0):ln['to_px'] + DASH_BAND_PX + 1,
                     p - DASH_BAND_PX:p + DASH_BAND_PX + 1] = True
    out = rgb
    ridge_all = np.zeros(rgb.shape[:2], dtype=bool)
    filled = np.zeros(rgb.shape[:2], dtype=bool)
    passes = []
    for _ in range(DASH_PASSES):
        core, rim = dash_pixels(out, lines, sites)
        out, kept = fill_dashes(out, core | rim, vertical, colour)
        ridge_all |= core & ~kept
        filled |= (core | rim) & ~kept
        passes.append({'ridge_px': int(core.sum()), 'rim_px': int(rim.sum()), 'left_as_painted_px': int(kept.sum())})
    rec = {'sites': {k_: {'count': len(v['sites']), 'anchors': v['anchors'], 'period_px': v['period_px']}
                     for k_, v in read.items()},
           'colour': colour_rec, 'passes': passes, 'ridge_px': int(ridge_all.sum()),
           'rim_px': int((filled & ~ridge_all).sum()), 'filled_px': int(filled.sum())}
    return out, ridge_all, filled, sites, rec


def dash_readings(light, line, sites, scale):
    """The ridge per dash site on a picture at ``scale`` × the sketch's pixels: along the line, L* on the line (the
    lightest of its rows ±1 sketch px) less the LARGER of its two sides (``DASH_SIDE_PX``, each the darker of its two);
    each site's reading the median of that ridge over the dash's 6 px less the median over the clean pixels 3 px
    either side of its zone (where that is over 0: a vein running along the line reads in both and cancels), and its
    peak (the largest single value over the dash's 6 px: a speck, or a vein crossing the line). Returns (reading, peak)
    per site, None where the site lies off the line."""
    p = int(round(line['found_pos_px'] * scale + (scale - 1) / 2.0))
    lo, hi = int(round(line['from_px'] * scale)), int(round(line['to_px'] * scale))
    t = np.arange(lo, hi)

    def at(d):
        q = np.full_like(t, p + d)
        return light[(t, q)] if line['orient'] == 'v' else light[(q, t)]
    s0, s1 = (int(round(v * scale)) for v in DASH_SIDE_PX)
    sides = np.maximum(np.minimum(at(-s0), at(-s1)), np.minimum(at(s0), at(s1)))
    band = int(round(scale))
    r = np.max(np.stack([at(d) for d in range(-band, band + 1)]), axis=0) - sides
    n = len(r)
    zone = np.zeros(n, dtype=bool)
    for a, b in sites:
        zone[max(int(round((a - DASH_ZONE_PX) * scale)), 0):max(min(int(round((b + DASH_ZONE_PX) * scale)), n), 0)] = True
    out = []
    for a, b in sites:
        a_, b_ = max(int(round(a * scale)), 0), max(min(int(round(b * scale)), n), 0)
        z0 = max(int(round((a - DASH_ZONE_PX) * scale)), 0)
        z1 = max(min(int(round((b + DASH_ZONE_PX) * scale)), n), 0)
        reach = int(round(DASH_ROW_READ_PX * scale))
        g = np.r_[max(z0 - reach, 0):z0, z1:min(z1 + reach, n)]
        g = g[~zone[g]]
        if b_ - a_ < DASH_ON_PX // 2 or not len(g):
            out.append(None)
            continue
        out.append((float(np.median(r[a_:b_]) - max(float(np.median(r[g])), 0.0)), float(r[a_:b_].max())))
    return out


def dash_proof(sketch_rgb, plate, lines, sites, wrap_w_mm):
    """The dashes proved gone on the final plate (2× the sketch): each line's ridge per dash site (``dash_readings``)
    on the plate (after) and on the uncleaned sketch upscaled the same way (before, the control). A line is GONE when
    no site reads over 6 L* after AND the uncleaned upscale's worst site reads over 6 L* (the proof fails there: it can
    see this line's dashes); when the uncleaned one does not, the proof is not competent on that line (never "gone").
    Sites whose dash reads 6 L* or less even uncleaned (over a vein or a pale stone) are counted: the proof cannot see
    them."""
    before_plate = lm.upscale(sketch_rgb)
    light0 = lm.srgb_to_lab(before_plate)[..., 0].astype(np.float64)
    light1 = lm.srgb_to_lab(plate)[..., 0].astype(np.float64)
    scale = plate.shape[1] / sketch_rgb.shape[1]
    k_up = plate.shape[1] / wrap_w_mm
    rows = []
    for ln in lines:
        s = sites[ln['side']]
        b = dash_readings(light0, ln, s, scale)
        a = dash_readings(light1, ln, s, scale)
        pairs = [(i, b_[0], a_[0]) for i, (b_, a_) in enumerate(zip(b, a)) if b_ is not None and a_ is not None]
        peaks = [(i, a_[1]) for i, (b_, a_) in enumerate(zip(b, a)) if b_ is not None and a_ is not None]
        worst = max(pairs, key=lambda q: q[2])
        before_max = max(q[1] for q in pairs)
        competent = bool(before_max > DASH_GONE_L)
        over = [q for q in pairs if q[2] > DASH_GONE_L]
        blind = [q for q in pairs if q[1] <= DASH_GONE_L]

        def at_mm(i):
            mid = ln['from_px'] + (s[i][0] + s[i][1]) / 2.0
            return round(mid * scale / k_up, 2)
        rows.append({'side': ln['side'], 'sites_read': len(pairs), 'before_max_L': round(before_max, 2),
                     'before_median_L': round(float(np.median([q[1] for q in pairs])), 2),
                     'after_max_L': round(worst[2], 2), 'after_worst_site_at_mm': at_mm(worst[0]),
                     'after_median_L': round(float(np.median([q[2] for q in pairs])), 2),
                     'sites_over_the_bar_after': [{'at_mm': at_mm(q[0]), 'after_L': round(q[2], 2),
                                                   'before_L': round(q[1], 2)} for q in over],
                     'sites_the_proof_cannot_see': [{'at_mm': at_mm(q[0]), 'before_L': round(q[1], 2)} for q in blind],
                     'after_peak_max_L': round(max(q[1] for q in peaks), 2),
                     'sites_with_a_peak_over_the_bar_after': [{'at_mm': at_mm(i), 'peak_L': round(v, 2)}
                                                              for i, v in peaks if v > DASH_GONE_L],
                     'uncleaned_fails': competent, 'competent': competent,
                     'gone': bool(competent and not over)})
    return {'rule': 'per dash site: the ridge (L* on the line less the larger of its two sides) as the median over the '
                    'dash less that over the clean pixels beside it; gone when no site reads over %.0f L* on the final '
                    'plate and the same proof on the uncleaned upscale fails (a site over %.0f L*)'
                    % (DASH_GONE_L, DASH_GONE_L),
            'bar_L': DASH_GONE_L, 'along_mm': 'the site\'s middle along its line, mm on the wrap (x for top and bottom, '
                                              'y for left and right)',
            'peaks': 'each site\'s largest single ridge value after, recorded beside the rule (not in it): a speck left, '
                     'or a vein crossing the line, reads there — each such place is to be looked at',
            'lines': rows, 'gone': all(r['gone'] for r in rows)}


def stones_proof(sketch_rgb, cleaned, ridge_px, words, plate, k, seam_px, wrap_w_mm):
    """The stones untouched: every stone pixel of the uncleaned sketch (``zlm.stones_clear_of_words`` on its own
    reading: off the ground, neither rose gold nor cream, 0.3 mm² or more, 1.5 mm clear of the painted words) less the
    dash's ridge pixels, eroded 2 px (the sketch's pixels), read on the final plate against the uncleaned sketch
    upscaled the same way with only its ridge pixels as cleaned (so the Lanczos reach of the dash's own correction is
    not counted, and every other pixel — the dash's rim included — is held to the sketch); unchanged when ΔE76 ≤ 2.
    The seam's band (its own proof) is left out. Also the plain reading against the uncleaned upscale, for the
    record."""
    m0 = zlm.masks(sketch_rgb, zlm.ground_lab(sketch_rgb))
    stones = zlm.stones_clear_of_words(m0, words, k) & ~ridge_px
    inner = cv2.erode(stones.astype(np.uint8), zlm.disc(2 * STONE_ERODE_PX + 1)).astype(bool)
    big = cv2.resize(inner.astype(np.uint8), (plate.shape[1], plate.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
    big[:, plate.shape[1] - seam_px:] = False
    got = lm.srgb_to_lab(plate)
    k_up = plate.shape[1] / wrap_w_mm
    readings = {}
    for name, base in (('held', np.where(ridge_px[..., None], cleaned, sketch_rgb)), ('plain', sketch_rgb)):
        de = np.linalg.norm(lm.srgb_to_lab(lm.upscale(base)) - got, axis=-1)
        d = de[big]
        ys, xs = np.nonzero(big & (de > STONE_DE76_MAX))
        i = int(np.argmax(np.where(big, de, -1.0)))
        readings[name] = {'max': round(float(d.max()), 3), 'p99': round(float(np.percentile(d, 99)), 3),
                          'over_2': int(len(ys)),
                          'worst_at_mm': [round((i % plate.shape[1]) / k_up, 2), round((i // plate.shape[1]) / k_up, 2)],
                          'over_2_at_mm': [list(q) for q in sorted({(round(x / k_up, 1), round(y / k_up, 1))
                                                                    for y, x in zip(ys, xs)})[:40]]}
    return {'rule': 'the stones\' pixels (the uncleaned sketch\'s, less the dash\'s ridge pixels, eroded %d px) unchanged '
                    'on the final plate (ΔE76 ≤ %.0f) against the sketch upscaled the same way with only its ridge '
                    'pixels as cleaned; the seam\'s %.0f mm band apart' % (STONE_ERODE_PX, STONE_DE76_MAX,
                                                                          zlm.SEAM_BAND_MM),
            'stone_px_read': int(big.sum()), **readings['held'], 'holds': bool(readings['held']['max'] <= STONE_DE76_MAX),
            'plain': dict(readings['plain'], said='against the uncleaned upscale itself: the Lanczos kernel carries the '
                                                  'ridge pixels\' own correction up to 4 px; read, not the rule')}


# --- the ghost of the cleaning: the ground rebuilt across every cleaned edge, proved without a straight edge ----------

GROUND_DE = 3.0                                   # ground: within ΔE00 3 of its local calm tone (σ 1 mm) on the dash-cleaned
                                                  # sketch — a faint vein, a stone's halo or a letter's shadow is not
GROUND_CLEAR_PX = 2                               # what is not ground kept 2 sketch px clear of any rebuilt pixel
SPECK_CLEAR_PX = 4                                # a speck wholly in the dash's filled pixels, nothing else off the ground
                                                  # within 4 px but such specks: the dash's own (a vein runs on past it)
REBUILD_BOX_MM = 0.3                              # a cleaned box rebuilt to 0.3 mm past its edge (its old edge inside)
REBUILD_LINE_MM = 0.6                             # a dash line's band rebuilt ±0.6 mm across: the dash, its rim, its fill
                                                  # and its halo through the upscale (read to ±0.47 mm on the sketch's
                                                  # 2×), the feather beyond it on ground the dash never reached
REBUILD_TONE_LINE_MM = 1.2                        # … and its tone made continuous ±1.2 mm across (the sketch's own step)
REBUILD_TONE_SIGMA_MM = 0.25                      # the ground's tone: its local plane at σ 0.25 mm, ground pixels only
REBUILD_PATCH_MM = 1.0                            # the grain: 1 mm patches of the ground's own texture …
REBUILD_REACH_MM = 3.0                            # … each from a random place within 3 mm, wholly on untouched ground …
REBUILD_FEATHER_MM = 0.1                          # … feathered 0.1 mm into the ground kept
REBUILD_SEED = 1208                               # the patches' places drawn from one fixed seed (the build reproducible)
REBUILD_PULL = 1e-3                               # the tone's weak pull toward the wide calm tone (a part no ground bounds)
GHOST_STRIP_MM = 0.3                              # the proof: a 0.3 mm strip each side of the edge …
GHOST_CORE_MM = 0.15                              # … beyond the edge's own strip ±0.15 mm (a line's own tone) …
GHOST_BIN_MM = 1.0                                # … binned every 1 mm along it …
GHOST_GROUND_SHARE = 0.5                          # … a strip read where at least half its pixels are ground
GHOST_AWAY_MM = 1.0                               # the bars: the same readings on the uncleaned sketch's ground on lines
GHOST_SPACING_MM = 0.5                            # every 0.5 mm, parallel to the edges, 1 mm or more from any of them …
GHOST_BAR_PERCENTILE = 95.0                       # … its 95th percentile (the median's bar) and its worst (the worst's bar)
GHOST_PARALLEL_MM = (-3.0, -2.5, -2.0, -1.5, -1.0, 1.0, 1.5, 2.0, 2.5, 3.0)   # the rule's own control: parallel copies


def ground_mask(rgb, ground, cleaned, keep, filled, k):
    """The ground on the sketch's grid, read on the dash-cleaned sketch: every pixel within ΔE00 3 of its local calm
    tone (``zlm.calm_tone`` over the calm pixels outside the cleaned boxes, σ 1 mm), the cleaned boxes ground whatever
    was painted there; what is not ground — a stone, a vein, a letter, the hero's carried raster ``keep`` — kept 2 px
    clear. In the dash's filled pixels (grown 1 px) a pixel off the ground only by being DARKER than its tone is the
    dash's dark rim left by the fill (a stone or a vein is lighter than the indigo; a vein's own dark edge lies within
    the 2 px kept clear of it): ground. A speck off the ground lying wholly in those pixels with nothing else off the
    ground within 4 px but other such specks is the dash's own residue (a vein crossing the line runs on past the band,
    and anything near one is kept): ground. Returns the mask and its record."""
    lab = lm.srgb_to_lab(rgb)
    calm = lm.delta_e00(lab, np.broadcast_to(ground, lab.shape)) <= zlm.GRAIN_CALM_DE
    tone = zlm.calm_tone(rgb.astype(np.float64), calm & ~cleaned, k)
    tone_lab = lm.srgb_to_lab(np.clip(np.round(tone), 0, 255).astype(np.uint8))
    de = lm.delta_e00(lab, tone_lab)
    band = cv2.dilate(filled.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    rim = (de > GROUND_DE) & ~cleaned & band & (lab[..., 0] < tone_lab[..., 0])
    off = (de > GROUND_DE) & ~cleaned & ~rim
    n, labels = cv2.connectedComponents(off.astype(np.uint8), connectivity=8)
    runs_on = np.zeros(n, dtype=bool)
    runs_on[np.unique(labels[off & ~band])] = True
    h, w = off.shape
    runs_on[0] = False
    specks = []
    for i in range(1, n):
        if runs_on[i]:
            continue
        ys, xs = np.nonzero(labels == i)
        y0, y1 = max(int(ys.min()) - SPECK_CLEAR_PX, 0), min(int(ys.max()) + SPECK_CLEAR_PX + 1, h)
        x0, x1 = max(int(xs.min()) - SPECK_CLEAR_PX, 0), min(int(xs.max()) + SPECK_CLEAR_PX + 1, w)
        if not runs_on[labels[y0:y1, x0:x1]].any():          # nothing near but the dash's own specks
            specks.append(i)
    residue = np.isin(labels, specks)
    not_ground = cv2.dilate(((off & ~residue) | keep).astype(np.uint8), zlm.disc(2 * GROUND_CLEAR_PX + 1)).astype(bool)
    out = ~not_ground
    return out, {'rule': 'ground: within ΔE00 %.0f of its local calm tone on the dash-cleaned sketch, the cleaned boxes '
                         'whole; what is not ground (stone, vein, letter, the hero\'s carried raster) kept %d px clear; '
                         'in the dash\'s filled pixels its dark rim (darker than the tone) and its isolated specks '
                         'taken as ground' % (GROUND_DE, GROUND_CLEAR_PX),
                 'ground_share': round(float(out.mean()), 4), 'dash_rim_px_taken_as_ground': int(rim.sum()),
                 'dash_specks_taken_as_ground': len(specks), 'dash_specks_px': int(residue.sum()),
                 'specks_said': 'a speck off the ground wholly in the dash\'s filled pixels with nothing else off the '
                                'ground within %d px but other such specks: the dash\'s own residue' % SPECK_CLEAR_PX}


def _line_middle_px(line):
    """A dash line's middle on the plate (the sketch's column or row ``found_pos_px`` covers ``UP`` plate pixels)."""
    return UP * line['found_pos_px'] + UP / 2.0


def rebuild_regions(shape, big, lines, k_up):
    """On the plate's grid: the pixels whose ground is rebuilt, tone and grain (each cleaned box ``big`` grown 0.3 mm,
    each dash line's band ±``REBUILD_LINE_MM`` from 2 sketch px before its start to 2 past its end), and those whose
    tone only is made continuous (each line's band ±``REBUILD_TONE_LINE_MM``). Returns (grain, tone)."""
    h, w = shape
    g = int(round(REBUILD_BOX_MM * k_up))
    box = cv2.dilate(big.astype(np.uint8), zlm.disc(2 * g + 1)).astype(bool)

    def bands(half_mm):
        out = np.zeros(shape, dtype=bool)
        half = int(round(half_mm * k_up))
        for ln in lines:
            p = int(round(_line_middle_px(ln)))
            lo, hi = max(UP * (ln['from_px'] - DASH_BAND_PX), 0), UP * (ln['to_px'] + DASH_BAND_PX + 1)
            if ln['orient'] == 'v':
                out[lo:min(hi, h), max(p - half, 0):min(p + half, w)] = True
            else:
                out[max(p - half, 0):min(p + half, h), lo:min(hi, w)] = True
        return out
    grain = box | bands(REBUILD_LINE_MM)
    return grain, grain | bands(REBUILD_TONE_LINE_MM)


PLANE_COND_MIN = 1e-3                             # the local plane's fit: its moments' determinant over the weight's cube
                                                  # and σ⁴ at least this (else the plain local mean)


def local_plane(img, weight, sigma_px):
    """The local tone of ``img`` over the ``weight`` pixels only: at each pixel the value there of the plane fitted to
    the weight pixels around it by Gaussian-weighted least squares (σ px; first-order normalised convolution) — beside a
    cleaned band, where the weight lies on one side only, a plain local mean drifts by the ground's gradient times
    about σ (a light or dark streak along the band's edge); the plane does not. Where the fit is ill-conditioned (the
    weight thin or on a line), the plain local mean. Returns the tone and the weight it saw."""
    h, w = weight.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    wf = weight.astype(np.float64)

    def blur(a):
        return cv2.GaussianBlur(a, (0, 0), sigma_px)
    s0 = blur(wf)
    gx, gy = blur(wf * xx), blur(wf * yy)
    sx, sy = gx - xx * s0, gy - yy * s0
    sxx = blur(wf * xx * xx) - 2.0 * xx * gx + xx * xx * s0
    syy = blur(wf * yy * yy) - 2.0 * yy * gy + yy * yy * s0
    sxy = blur(wf * xx * yy) - xx * gy - yy * gx + xx * yy * s0
    c00, c01, c02 = sxx * syy - sxy * sxy, sy * sxy - sx * syy, sx * sxy - sy * sxx
    det = s0 * c00 + sx * c01 + sy * c02
    ok = (s0 > 1e-6) & (np.abs(det) >= PLANE_COND_MIN * np.maximum(s0, 1e-6) ** 3 * sigma_px ** 4)
    out = np.zeros(img.shape, np.float64)
    for c in range(img.shape[2]):
        f = img[..., c].astype(np.float64)
        b0 = blur(wf * f)
        bx, by = blur(wf * f * xx) - xx * b0, blur(wf * f * yy) - yy * b0
        plane = (c00 * b0 + c01 * bx + c02 * by) / np.where(ok, det, 1.0)
        out[..., c] = np.where(ok, plane, b0 / np.maximum(s0, 1e-6))
    return out, s0


def harmonic_fill(values, inside, fixed, pull_to):
    """A smooth field on ``inside``: Laplace's equation on the 4-neighbours, held at ``values`` on every ``fixed``
    neighbour (the untouched ground), free across a neighbour that is neither (a stone's, a vein's or a letter's edge: no
    flux), with a weak pull toward ``pull_to`` (``REBUILD_PULL``) so a part no fixed pixel bounds is still defined.
    Returns the rows, the columns and the field's values there."""
    import scipy.sparse as sp
    from scipy.sparse.linalg import splu
    h, w = inside.shape
    ys, xs = np.nonzero(inside)
    n = len(ys)
    index = -np.ones((h, w), dtype=np.int64)
    index[ys, xs] = np.arange(n)
    diag = np.full(n, REBUILD_PULL)
    rhs = REBUILD_PULL * pull_to[ys, xs]
    rows, cols = [np.arange(n)], [np.arange(n)]
    data = []
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        yy, xx = ys + dy, xs + dx
        on = (yy >= 0) & (yy < h) & (xx >= 0) & (xx < w)
        yy, xx = np.clip(yy, 0, h - 1), np.clip(xx, 0, w - 1)
        free = on & inside[yy, xx]
        held = on & ~inside[yy, xx] & fixed[yy, xx]
        diag += free.astype(np.float64) + held.astype(np.float64)
        rows.append(np.nonzero(free)[0])
        cols.append(index[yy[free], xx[free]])
        data.append(-np.ones(int(free.sum())))
        rhs[held] += values[yy[held], xx[held]]
    a = sp.csc_matrix((np.concatenate([diag] + data), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
    lu = splu(a)
    return ys, xs, np.stack([lu.solve(np.ascontiguousarray(rhs[:, c])) for c in range(values.shape[2])], axis=-1)


def rebuild_ground(plate, grain, tone, ground_up, k_up):
    """The cleaned ground rebuilt on GROUND PIXELS ONLY (``ground_up``; everything else, and every pixel outside
    ``tone``, as it was):

    - its TONE: the ground's local tone (``local_plane``, a first-order fit at σ ``REBUILD_TONE_SIGMA_MM`` over the ground
      outside ``grain``) replaced inside ``tone`` by a smooth field (``harmonic_fill``) held at that tone on the untouched
      ground just outside — so the tone is continuous across every cleaned edge, and across the guide line the
      sketch's own step is spread over ±``REBUILD_TONE_LINE_MM``;
    - its GRAIN: inside ``grain``, the ground's own texture (each pixel less that local tone) from random 1 mm patches of
      the untouched ground within 3 mm (wholly ground), laid at half-patch steps with weights whose squares sum to one
      (no tile repeated, the grain's strength kept), feathered 0.1 mm into the ground kept by the same rule; between
      ``grain`` and ``tone``'s edge each pixel keeps its own texture on the new tone (an additive smooth correction).

    Returns the plate and the record."""
    from scipy.ndimage import distance_transform_edt
    f = plate.astype(np.float64)
    h, w = ground_up.shape
    grain = grain & ground_up
    tone = (tone & ground_up) | grain
    kept = ground_up & ~tone
    mean, seen = local_plane(f, ground_up & ~grain, REBUILD_TONE_SIGMA_MM * k_up)
    wide = zlm.calm_tone(f, kept, k_up)
    mean = np.where((seen >= zlm.GRAIN_TONE_WEIGHT_MIN)[..., None], mean, wide)
    ys, xs, field = harmonic_fill(mean, tone, kept, wide)
    smooth = mean.copy()
    smooth[ys, xs] = field
    own = f - mean
    p = int(round(REBUILD_PATCH_MM * k_up)) // 2 * 2
    half = p // 2
    sums = cv2.integral(kept.astype(np.uint8))
    whole = (sums[p:, p:] - sums[:-p, p:] - sums[p:, :-p] + sums[:-p, :-p]) == p * p
    rng = np.random.default_rng(REBUILD_SEED)
    ramp = np.sin(np.pi * (np.arange(p) + 0.5) / p)
    weight = np.outer(ramp, ramp)[..., None]
    laid = np.zeros_like(f)
    gy, gx = np.nonzero(grain)
    reach0 = int(round(REBUILD_REACH_MM * k_up))
    patches, widened = 0, 0
    for py in range(int(gy.min()) - p, int(gy.max()) + 1, half):
        for px in range(int(gx.min()) - p, int(gx.max()) + 1, half):
            a0, a1, b0, b1 = max(py, 0), min(py + p, h), max(px, 0), min(px + p, w)
            if a0 >= a1 or b0 >= b1 or not grain[a0:a1, b0:b1].any():
                continue
            reach = reach0
            while True:
                cy0, cy1 = max(py - reach, 0), min(py + reach, whole.shape[0])
                cx0, cx1 = max(px - reach, 0), min(px + reach, whole.shape[1])
                cy, cx = np.nonzero(whole[cy0:cy1, cx0:cx1])
                if len(cy) or reach > max(h, w):
                    break
                reach *= 2
            if not len(cy):
                raise ValueError('no patch of untouched ground %d px square anywhere on the plate' % p)
            widened += int(reach > reach0)
            j = int(rng.integers(len(cy)))
            sy, sx = cy0 + int(cy[j]), cx0 + int(cx[j])
            laid[a0:a1, b0:b1] += (weight * own[sy:sy + p, sx:sx + p])[a0 - py:a1 - py, b0 - px:b1 - px]
            patches += 1
    feather = np.clip(distance_transform_edt(~(ground_up & ~grain)) / (REBUILD_FEATHER_MM * k_up), 0.0, 1.0)[..., None]
    texture = np.where(grain[..., None], feather * laid + np.sqrt(1.0 - feather * feather) * own, own)
    out = f.copy()
    out[tone] = (smooth + texture)[tone]
    out = np.clip(np.round(out), 0, 255).astype(np.uint8)
    return out, {'rule': 'on ground pixels only: the tone a smooth field (Laplace) held at the untouched ground\'s local '
                         'tone (a first-order fit, σ %.2f mm) just outside; the grain the ground\'s own texture from '
                         'random %.1f mm patches '
                         'of the untouched ground within %.0f mm, weights whose squares sum to one, feathered %.1f mm'
                         % (REBUILD_TONE_SIGMA_MM, REBUILD_PATCH_MM, REBUILD_REACH_MM, REBUILD_FEATHER_MM),
                 'grain_px': int(grain.sum()), 'tone_px': int(tone.sum()), 'patches': patches, 'patch_px': p,
                 'patches_from_further': widened, 'seed': REBUILD_SEED,
                 'pixels_changed_off_the_ground': int((out != plate).any(axis=-1)[~ground_up].sum())}


def ghost_edges(lines, boxes, k, big):
    """The edges the proof reads, on the plate's grid: each dash line (its middle, from end to end); each cleaned box's
    four sides (``boxes``: (name, ink box px); grown ``zlm.BOX_GROW_MM`` as ``word_box_mask`` grew it, × ``UP``, grown
    ``zlm.CLEAN_GROW_PX`` as ``clean_up`` grew it); and the seams where the old fill's 5 mm tiles met inside them
    (``zlm.grain_fill_tiled`` laid its tiles from the cleaned mask's top-left)."""
    edges = [{'name': 'dash %s' % ln['side'], 'kind': 'dash line', 'orient': ln['orient'], 'pos_px': _line_middle_px(ln),
              'from_px': UP * ln['from_px'], 'to_px': UP * ln['to_px']} for ln in lines]
    g = int(round(zlm.BOX_GROW_MM * k))
    grow = zlm.CLEAN_GROW_PX
    sides = []
    for name, (x0, y0, x1, y1) in boxes:
        bx0, by0 = UP * max(x0 - g, 0) - grow, UP * max(y0 - g, 0) - grow
        bx1, by1 = UP * (x1 + g) + grow, UP * (y1 + g) + grow
        sides.append((name, bx0, by0, bx1, by1))
        for side, orient, pos, lo, hi in (('left', 'v', bx0, by0, by1), ('right', 'v', bx1, by0, by1),
                                          ('top', 'h', by0, bx0, bx1), ('bottom', 'h', by1, bx0, bx1)):
            edges.append({'name': '%s %s' % (name, side), 'kind': 'box side', 'orient': orient, 'pos_px': float(pos),
                          'from_px': int(lo), 'to_px': int(hi)})
    if big.any():
        k_up = k * UP
        t = max(int(round(zlm.GRAIN_TILE_MM * k_up)), 1)
        ys, xs = np.nonzero(big)
        for name, bx0, by0, bx1, by1 in sides:
            for x in range(int(xs.min()) + t, int(xs.max()) + 1, t):
                if bx0 < x < bx1:
                    edges.append({'name': '%s seam x %.1f mm' % (name, x / k_up), 'kind': 'old tile seam',
                                  'orient': 'v', 'pos_px': float(x), 'from_px': int(by0), 'to_px': int(by1)})
            for y in range(int(ys.min()) + t, int(ys.max()) + 1, t):
                if by0 < y < by1:
                    edges.append({'name': '%s seam y %.1f mm' % (name, y / k_up), 'kind': 'old tile seam',
                                  'orient': 'h', 'pos_px': float(y), 'from_px': int(bx0), 'to_px': int(bx1)})
    return edges


def ghost_readings(light, ground_up, edge, k_up):
    """Along an edge, per 1 mm bin: the mean L* over the ground pixels of three strips across it — 0.3 mm on each side
    (from 0.15 to 0.45 mm out) and the edge's own ±0.15 mm — read where each strip is at least half ground. Each bin's
    STEP is the two sides' difference, its LINE the edge's own strip against the sides' mean (a thin line lighter or
    darker than both). Returns per bin (step, line, middle along the edge in mm), None where a strip is not ground."""
    s, c, b = GHOST_STRIP_MM * k_up, GHOST_CORE_MM * k_up, GHOST_BIN_MM * k_up
    p = edge['pos_px']
    strips = [(int(round(p - c - s)), int(round(p - c))), (int(round(p - c)), int(round(p + c))),
              (int(round(p + c)), int(round(p + c + s)))]
    h, w = light.shape
    out = []
    t = float(edge['from_px'])
    while t + b <= edge['to_px'] + 0.5:
        t0, t1 = int(round(t)), int(round(t + b))
        means = []
        for a0, a1 in strips:
            a0, a1 = max(a0, 0), min(a1, w if edge['orient'] == 'v' else h)
            if edge['orient'] == 'v':
                win, on = light[t0:t1, a0:a1], ground_up[t0:t1, a0:a1]
            else:
                win, on = light[a0:a1, t0:t1], ground_up[a0:a1, t0:t1]
            means.append(float(win[on].mean()) if on.size and on.mean() >= GHOST_GROUND_SHARE else None)
        if None in means:
            out.append(None)
        else:
            out.append((abs(means[0] - means[2]), abs(means[1] - (means[0] + means[2]) / 2.0), (t0 + t1) / 2.0 / k_up))
        t += b
    return out


def ghost_bars(light0, ground_up, edges, big, k_up, seam_px):
    """The bars, read on the UNCLEANED sketch's own ground (its upscale ``light0``): the same two readings on every
    vertical and horizontal line (parallel to the edges) every 0.5 mm across the plate, in bins whose strips are ground
    and lie 1 mm or more from any edge the proof reads and from the cleaned boxes (the seam's band apart); the bar for
    an edge's median bin is their 95th percentile, for its worst bin their worst."""
    h, w = light0.shape
    avoid = big.astype(np.uint8).copy()
    for e in edges:
        p = int(round(e['pos_px']))
        if e['orient'] == 'v':
            avoid[e['from_px']:e['to_px'], max(p - 1, 0):p + 2] = 1
        else:
            avoid[max(p - 1, 0):p + 2, e['from_px']:e['to_px']] = 1
    reach = int(round((GHOST_AWAY_MM + GHOST_CORE_MM + GHOST_STRIP_MM) * k_up))
    away = ground_up & ~cv2.dilate(avoid, zlm.disc(2 * reach + 1)).astype(bool)
    away[:, w - seam_px:] = False
    step, line = [], []
    every = int(round(GHOST_SPACING_MM * k_up))
    margin = int(round(GHOST_AWAY_MM * k_up))
    for orient, n, m in (('v', w, h), ('h', h, w)):
        for pos in range(margin, n - margin, every):
            for q in ghost_readings(light0, away, {'orient': orient, 'pos_px': float(pos), 'from_px': 0, 'to_px': m},
                                    k_up):
                if q is not None:
                    step.append(q[0])
                    line.append(q[1])
    step, line = np.array(step), np.array(line)
    return {'bins_read': int(len(step)), 'away_mm': GHOST_AWAY_MM, 'spacing_mm': GHOST_SPACING_MM,
            'step_median_bar_L': round(float(np.percentile(step, GHOST_BAR_PERCENTILE)), 3),
            'step_worst_bar_L': round(float(step.max()), 3),
            'line_median_bar_L': round(float(np.percentile(line, GHOST_BAR_PERCENTILE)), 3),
            'line_worst_bar_L': round(float(line.max()), 3),
            'step_median_L': round(float(np.median(step)), 3), 'line_median_L': round(float(np.median(line)), 3),
            'said': 'read on the uncleaned sketch\'s own ground (its 2× upscale): the median\'s bar its %.0fth '
                    'percentile, the worst bin\'s bar its worst' % GHOST_BAR_PERCENTILE}, away


def ghost_judge(bins, bars):
    """An edge judged by its bins (``ghost_readings``): it holds when, for the step and for the line, its median bin is
    within the median's bar and its worst within the worst's bar. None when no bin is ground."""
    read = [q for q in bins if q is not None]
    if not read:
        return None
    step = np.array([q[0] for q in read])
    line = np.array([q[1] for q in read])
    worst = max(read, key=lambda q: max(q[0] - bars['step_median_bar_L'], q[1] - bars['line_median_bar_L']))
    checks = {'step_median': bool(np.median(step) <= bars['step_median_bar_L']),
              'step_worst': bool(step.max() <= bars['step_worst_bar_L']),
              'line_median': bool(np.median(line) <= bars['line_median_bar_L']),
              'line_worst': bool(line.max() <= bars['line_worst_bar_L'])}
    return {'bins_read': len(read), 'bins': len(bins), 'step_median_L': round(float(np.median(step)), 3),
            'step_max_L': round(float(step.max()), 3), 'line_median_L': round(float(np.median(line)), 3),
            'line_max_L': round(float(line.max()), 3),
            'bins_over_a_median_bar': int(sum(q[0] > bars['step_median_bar_L'] or q[1] > bars['line_median_bar_L']
                                              for q in read)),
            'worst_bin_at_mm': round(worst[2], 2), 'checks': checks, 'holds': all(checks.values())}


def ghost_proof(plate, control, up0, ground_up, edges, big, k_up, seam_px):
    """No straight edge left (D-D12-8): every edge (``ghost_edges``) read on ground pixels (``ghost_readings``) on the
    final plate and on ``control`` (the same plate before the rebuild, the plate the eye saw), each judged against bars
    from the uncleaned sketch's own ground (``ghost_bars``, ``ghost_judge``). The rule's own control in the passing
    direction: each edge's parallel copies 1 to 3 mm off it on the uncleaned sketch (bins 1 mm or more from any edge)
    judged by the same rule — the share that holds. Holds when every edge read holds; an edge with no ground bin is
    named, never counted as holding."""
    light = lm.srgb_to_lab(plate)[..., 0]
    light_c = lm.srgb_to_lab(control)[..., 0]
    light0 = lm.srgb_to_lab(up0)[..., 0]
    bars, away = ghost_bars(light0, ground_up, edges, big, k_up, seam_px)
    rows = []
    for e in edges:
        after = ghost_judge(ghost_readings(light, ground_up, e, k_up), bars)
        before = ghost_judge(ghost_readings(light_c, ground_up, e, k_up), bars)
        rows.append({'edge': e['name'], 'kind': e['kind'], 'at_px': round(e['pos_px'], 1),
                     'at_mm': round(e['pos_px'] / k_up, 3), 'along_mm': [round(e['from_px'] / k_up, 2),
                                                                          round(e['to_px'] / k_up, 2)],
                     'after': after, 'before': before})
    copies, held, failing = 0, 0, []
    for e in edges:
        for off_mm in GHOST_PARALLEL_MM:
            judged = ghost_judge(ghost_readings(light0, away, dict(e, pos_px=e['pos_px'] + off_mm * k_up), k_up), bars)
            if judged is not None:
                copies += 1
                held += int(judged['holds'])
                if not judged['holds']:
                    failing.append({'edge': e['name'], 'off_mm': off_mm, 'bins_read': judged['bins_read'],
                                    'step_median_L': judged['step_median_L'], 'line_median_L': judged['line_median_L'],
                                    'failed': [k_ for k_, v in judged['checks'].items() if not v]})
    read = [r for r in rows if r['after'] is not None]
    return {'rule': 'per edge, on ground pixels: per 1 mm bin the step across it (the mean L* of a %.1f mm strip each '
                    'side, from %.2f mm out) and the line on it (its own ±%.2f mm strip against the sides\' mean); it '
                    'holds when its median bin is within the 95th percentile and its worst bin within the worst of the '
                    'same readings on the uncleaned sketch\'s ground on parallel lines %.0f mm or more from any edge'
                    % (GHOST_STRIP_MM, GHOST_CORE_MM, GHOST_CORE_MM, GHOST_AWAY_MM),
            'bars': bars, 'edges': rows,
            'edges_read': len(read), 'edges_not_read': [r['edge'] for r in rows if r['after'] is None],
            'edges_failing_after': [r['edge'] for r in read if not r['after']['holds']],
            'edges_failing_on_the_control': [r['edge'] for r in rows if r['before'] is not None
                                             and not r['before']['holds']],
            'parallel_control': {'copies_read': copies, 'copies_holding': held,
                                 'share_holding': round(held / copies, 4) if copies else None,
                                 'copies_failing': failing,
                                 'said': 'the rule on each edge\'s parallel copies %s mm off it on the uncleaned '
                                         'sketch\'s ground (bins %.0f mm or more from any edge): %d of %d hold — the '
                                         'rule\'s false alarms on untouched ground beside these edges are the %d '
                                         'listed (their bins read: %s)' % (
                                             ', '.join('%+.1f' % v for v in GHOST_PARALLEL_MM), GHOST_AWAY_MM, held,
                                             copies, len(failing),
                                             ', '.join(str(q['bins_read']) for q in failing))},
            'holds': bool(read and all(r['after']['holds'] for r in read))}


def repair_ghost(rgb, plate, big, cleaned, keep, filled, lines, ground, k, boxes, seam_px):
    """D-D12-8 on a wrap's cleaned plate (before its seam): its ground (``ground_mask``) on the plate's grid, the regions
    (``rebuild_regions``, the seam's band apart: its own treatment follows), the rebuild (``rebuild_ground``). Returns
    the rebuilt plate, the ground on the plate's grid, the edges the proof reads (``ghost_edges``) and the record."""
    ground_px, ground_rec = ground_mask(rgb, ground, cleaned, keep, filled, k)
    ground_up = cv2.resize(ground_px.astype(np.uint8), (plate.shape[1], plate.shape[0]),
                           interpolation=cv2.INTER_NEAREST).astype(bool)
    grain, tone = rebuild_regions(ground_up.shape, big, lines, k * UP)
    grain[:, plate.shape[1] - seam_px:] = False
    tone[:, plate.shape[1] - seam_px:] = False
    rebuilt, rec = rebuild_ground(plate, grain, tone, ground_up, k * UP)
    return rebuilt, ground_up, ghost_edges(lines, boxes, k, big), dict(rec, ground=ground_rec)


def prove_ghost(rec, plate, control, rgb0, ground_up, edges, big, k_up, seam_px, control_png):
    """The repair's proof on the final plate (``ghost_proof``) with its control — the same plate without the rebuild,
    its seam treated alike (the plate the eye saw) — kept beside the plate (``control_png``) with its sha256."""
    Image.fromarray(control).save(control_png)
    return dict(rec, control_plate=lm.rel(control_png), control_sha256=lm.sha256(control_png),
                proof=ghost_proof(plate, control, lm.upscale(rgb0), ground_up, edges, big, k_up, seam_px))


# --- the body's words: the logotype and the cream line (the balm has no أحمر and one cream line) ---------------------

def find_logotype(m, hero, k):
    """"Enchanted Rose" as the sketch paints it: the widest solid rose-gold row (``zlm.solid_words``, the hero grown
    0.5 mm taken out) at least three times as wide as tall whose top lies below the hero's middle."""
    rows = zlm.solid_words(m, hero['mask'], k)
    hx0, hy0, hx1, hy1 = hero['window_px']
    mid = (hy0 + hy1) / 2.0
    names = [r for r in rows if r['box_px'][1] > mid and (r['box_px'][2] - r['box_px'][0]) >= 3 * (r['box_px'][3] - r['box_px'][1])]
    if not names:
        raise ValueError('no logotype row below the hero: %s' % [r['box_px'] for r in rows])
    return max(names, key=lambda r: r['box_px'][2] - r['box_px'][0])


def find_line(m, k, below_px, gold_words, span_px):
    """"LIP BALM" as the sketch paints it: the cream (opened 2 px) below ``below_px`` (the logotype's foot), outside
    the gold words grown 0.5 mm and within the front third's columns ``span_px`` (no stone counts), cut into rows at
    gaps over 3 px; the first row of at least 1 mm² of cream. Its ink box (px)."""
    gold = cv2.dilate(gold_words.astype(np.uint8), zlm.disc(zlm.odd_px(2 * zlm.GOLD_CLEAR_MM, k))).astype(bool)
    cream = cv2.morphologyEx((m['cream'] & ~gold).astype(np.uint8), cv2.MORPH_OPEN,
                             np.ones((zlm.CREAM_OPEN_PX,) * 2, np.uint8))
    cream[:below_px] = 0
    cream[:, :span_px[0]] = 0
    cream[:, span_px[1]:] = 0
    rows = np.nonzero(cream.any(axis=1))[0]
    for r in np.split(rows, np.nonzero(np.diff(rows) > zlm.CREAM_ROW_GAP_PX)[0] + 1):
        if not len(r):
            continue
        band = cream[r[0]:r[-1] + 1]
        if band.sum() < k * k:
            continue
        cols = np.nonzero(band.any(axis=0))[0]
        return [int(cols.min()), int(r[0]), int(cols.max()) + 1, int(r[-1]) + 1]
    raise ValueError('no cream line under the logotype inside the front third')


# --- the cleaning and the seam (the lipstick's, at the balm's size) --------------------------------------------------

def word_box_mask(shape, box_px, k, m, words):
    """``zilal_lipstick_master.box_mask`` with its stones read 1.5 mm clear of the painted words
    (``zlm.stones_clear_of_words``): a word's box grown 0.6 mm, whole (its ink, its hairlines, its anti-aliased copper
    edge, its drop shadow), less only the true stones in it — a letter's own off-hue stroke is not a stone (the plain
    ``box_mask`` kept the cap logo's R-stem sliver as one)."""
    g = int(round(zlm.BOX_GROW_MM * k))
    x0, y0, x1, y1 = box_px
    out = np.zeros(shape, dtype=bool)
    out[max(y0 - g, 0):y1 + g, max(x0 - g, 0):x1 + g] = True
    stones = zlm.stones_clear_of_words(m, words, k)
    stones = cv2.dilate(stones.astype(np.uint8), zlm.disc(3)).astype(bool)
    return out & ~stones


def clean_up(rgb, mask, ground, wrap_w_mm):
    """``zilal_lipstick_master.clean_up`` at the wrap's own width: the picture upscaled 2× (``lm.upscale``), the mask
    grown 3 upscaled px, Telea, then the picture's own grain on the calm tone tile by tile (``zlm.grain_fill_tiled``)."""
    up = lm.upscale(rgb)
    big = cv2.resize(mask.astype(np.uint8), (up.shape[1], up.shape[0]), interpolation=cv2.INTER_NEAREST)
    big = cv2.dilate(big, zlm.disc(2 * zlm.CLEAN_GROW_PX + 1))
    plate = cv2.inpaint(up, big, zlm.TELEA_R_PX, cv2.INPAINT_TELEA)
    k_up = up.shape[1] / wrap_w_mm
    if big.any():
        plate, tiles = zlm.grain_fill_tiled(plate, big.astype(bool), ground, k_up)
    else:
        tiles = {'tiles': 0}
    return up, plate, big.astype(bool), tiles


def join_profile(rgb, k, overlap_mm):
    """``zilal_lipstick_master.join_profile`` at the balm's overlap: the right end's last 1 mm and the left start's
    1 mm just past the overlap, each averaged across, smoothed along the join (σ 0.5 mm); ΔE00 at every row."""
    from scipy.ndimage import gaussian_filter1d
    ov = int(round(overlap_mm * k))
    r = int(round(zlm.SEAM_READ_MM * k))
    left = gaussian_filter1d(rgb[:, ov:ov + r].astype(np.float64).mean(axis=1), zlm.SEAM_SIGMA_MM * k, axis=0)
    right = gaussian_filter1d(rgb[:, -r:].astype(np.float64).mean(axis=1), zlm.SEAM_SIGMA_MM * k, axis=0)
    return lm.delta_e00(lm.srgb_to_lab(np.clip(np.round(left), 0, 255).astype(np.uint8)[None]),
                        lm.srgb_to_lab(np.clip(np.round(right), 0, 255).astype(np.uint8)[None]))[0]


def treat_seam(rgb, k, overlap_mm):
    """``zilal_lipstick_master.treat_seam`` at the balm's overlap: the right end's last 2 mm feathered toward the left
    start's own pixels mirrored about the join; proven before and after (mean ΔE00 ≤ 2)."""
    before = join_profile(rgb, k, overlap_mm)
    band = int(round(zlm.SEAM_BAND_MM * k))
    ov = int(round(overlap_mm * k))
    target = rgb[:, ov:ov + band][:, ::-1].astype(np.float64)
    w = np.linspace(0.0, 1.0, band)[None, :, None]
    out = rgb.astype(np.float64).copy()
    out[:, -band:] = out[:, -band:] * (1 - w) + target * w
    out = np.clip(np.round(out), 0, 255).astype(np.uint8)
    after = join_profile(out, k, overlap_mm)
    return out, {'band_mm': zlm.SEAM_BAND_MM, 'read_mm': zlm.SEAM_READ_MM, 'sigma_mm': zlm.SEAM_SIGMA_MM,
                 'overlap_mm': round(overlap_mm, 4),
                 'before': {'mean': round(float(before.mean()), 3), 'max': round(float(before.max()), 3)},
                 'after': {'mean': round(float(after.mean()), 3), 'max': round(float(after.max()), 3)},
                 'holds': bool(after.mean() <= zlm.SEAM_MEAN_MAX),
                 'rule': 'D-D11-7: the seam a 2 mm feathered band, an allowed difference, proven: mean ΔE00 ≤ 2 across '
                         'the join after treatment'}


# --- the documents and files (the lipstick's, at the balm's sizes) ---------------------------------------------------

def wrap_document(plate_png, children, title, wrap_mm, page_w_mm):
    """``zilal_lipstick_master.wrap_document`` at the wrap's size: the plate at the trim's top-left, the page
    ``page_w_mm`` wide (the wrap's own width, or the proof's wider copy) and the wrap's height."""
    from apps.ire.graph import Document, Group, Image as GImage
    picture = Group(name='PICTURE', role='background', children=[
        GImage(name='plate', src=str(plate_png), x=0.0, y=0.0, w=wrap_mm[0], h=wrap_mm[1])])
    return Document(page_w=page_w_mm, page_h=wrap_mm[1], title=title,
                    metadata={'typography_surface': SURFACE, 'logical_text/1.0': True},
                    root=Group(name=title.upper(), role='artwork', children=[picture] + children))


def files_of(out, stem, engine_ai, proof_ai, wrap_mm, foil_drawn):
    """``zilal_lipstick_master.files_of`` at the wrap's size: the print PDF (its trim box inside the 1 mm top and bottom
    bleed), the 300 PPI flat, the finish proof (``finish_proof.prove_build`` on the wider proof page, cropped back to the
    wrap's width); ``foil_drawn`` is passed to the foil limits as it is: True for the body; None for the cap, which
    draws no foil — its limits then read None, "not measured", as the lipstick's cap reads (no check passes on
    nothing)."""
    import fitz
    from apps.pipeline.services import finish_proof as fp
    pdf = fitz.open()
    with fitz.open(str(engine_ai)) as src:
        p = pdf.new_page(width=src[0].rect.width, height=src[0].rect.height)
        p.show_pdf_page(p.rect, src, 0)
    trim = fitz.Rect(0, lm.pt(BLEED_TB_MM), p.rect.width, p.rect.height - lm.pt(BLEED_TB_MM))
    p.set_bleedbox(p.rect)
    p.set_trimbox(trim)
    pdf.set_metadata({'title': 'the lip balm\'s %s wrap' % stem, 'creator': SURFACE})
    lm.tag_srgb(pdf)
    pdf.save(str(out / ('%s-wrap.pdf' % stem)), garbage=3, deflate=True)
    pdf.close()
    lm.render_png(out / ('%s-wrap.pdf' % stem), 0, 300, out / ('%s-flat.png' % stem))
    proof_dir = out / ('%s-proof' % stem)
    lm.render_png(proof_ai, 0, 300, out / 'engine' / ('%s-proof-flat.png' % stem))
    rec = fp.prove_build(out / 'engine' / ('%s-proof-flat.png' % stem), proof_ai, proof_dir, foil_drawn=foil_drawn)
    wide = Image.open(proof_dir / 'finish-proof.png')
    keep = int(round(wide.width * wrap_mm[0] / PROOF_PAGE_W_MM))
    wide.crop((0, 0, keep, wide.height)).save(out / ('%s-finish-proof.png' % stem))
    with Image.open(out / ('%s-flat.png' % stem)) as flat:
        ppi = flat.width / (wrap_mm[0] / lm.MM_PER_INCH)
    return {'pdf': lm.rel(out / ('%s-wrap.pdf' % stem)), 'flat': lm.rel(out / ('%s-flat.png' % stem)),
            'flat_ppi': round(ppi, 2), 'ai': lm.rel(engine_ai), 'finish_proof': lm.rel(out / ('%s-finish-proof.png' % stem)),
            'trim_box_pt': [round(v, 3) for v in trim], 'foil_limits': rec['foil_limits'], 'coverage': rec['coverage']}


def dash_zones(lines):
    """Each found line's band (±2 px across, ±2 px past its ends) as a box in the sketch's px, for the upscale proof's
    count of where its pixels over the bar lie."""
    out = {}
    for ln in lines:
        p, lo, hi = ln['found_pos_px'], ln['from_px'], ln['to_px']
        if ln['orient'] == 'v':
            out['dash ' + ln['side']] = (p - DASH_BAND_PX, lo - DASH_BAND_PX, p + DASH_BAND_PX + 1, hi + DASH_BAND_PX + 1)
        else:
            out['dash ' + ln['side']] = (lo - DASH_BAND_PX, p - DASH_BAND_PX, hi + DASH_BAND_PX + 1, p + DASH_BAND_PX + 1)
    return out


def plate_ppi(plate, wrap_mm):
    """The plate's resolution at print size (px per inch across the wrap)."""
    return round(plate.shape[1] / (wrap_mm[0] / lm.MM_PER_INCH), 2)


# --- the body ---------------------------------------------------------------------------------------------------------

def body_words(rgb, m, k):
    """The body's painted words as the master reads them on the dash-cleaned sketch: the hero (``zlm.find_hero``), the
    logotype row below it (``find_logotype``), "LIP BALM" under that inside the front third (``find_line``) and its
    cream ink; the gold words (hero and logotype) and every word's ink (the stones are read clear of these)."""
    found = zlm.find_hero(rgb, m, k)
    name = find_logotype(m, found, k)
    third = zlm.front_third(BODY_MM[0], CASE_D_MM)
    span_px = [int(np.floor(third['span_mm'][0] * k)), int(np.ceil(third['span_mm'][1] * k))]
    gold_words = found['mask'] | name['mask']
    line_box = find_line(m, k, name['box_px'][3], gold_words, span_px)
    lx0, ly0, lx1, ly1 = line_box
    line_ink = np.zeros(rgb.shape[:2], dtype=bool)
    line_ink[ly0:ly1, lx0:lx1] = m['cream'][ly0:ly1, lx0:lx1]
    return {'found': found, 'name': name, 'third': third, 'line_box': line_box, 'gold_words': gold_words,
            'line_ink': line_ink, 'words': gold_words | line_ink}


def logotype_floor(rings, placed, transform, cap_lid_mm, third, hero_bottom_mm, lip_ink_mm):
    """D-D12-1.1's floor for "Enchanted Rose" (on wraps of Ø ≤ 20 mm the cap floor is 2.5 mm): its cap at the sketch's
    scale is the lid's cap × the placing's scale; raised to 2.5 mm by scaling the placed rings about their own ink
    box's centre, and kept raised only if the raised box stays inside the front third and keeps the sketch's stack —
    clear of the hero above, and of "LIP BALM" below, which moves down by as much as the gap closes while it stays
    inside the safe height. Returns the rings to emit, the move for "LIP BALM" (mm, down) and the record."""
    cap_mm = cap_lid_mm * transform['scale']
    s = CAP_FLOOR_SMALL_WRAP_MM / cap_mm
    bx0, by0, bx1, by1 = lm.rings_area(placed, 24).bounds
    cx, cy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
    raised = lm.map_rings(placed, lambda p: (cx + s * (p[0] - cx), cy + s * (p[1] - cy)))
    rx0, ry0, rx1, ry1 = lm.rings_area(raised, 24).bounds
    lo, hi = third['span_mm']
    move_mm = max(ry1 - by1, 0.0)
    safe_bottom_mm = BODY_MM[1] - BLEED_TB_MM - SAFE_TB_MM
    checks = {'inside_the_front_third': bool(lo <= rx0 and rx1 <= hi),
              'clear_of_the_hero': bool(ry0 >= hero_bottom_mm),
              'lip_balm_inside_the_safe_height_after_its_move': bool(lip_ink_mm[3] + move_mm <= safe_bottom_mm)}
    raise_it = all(checks.values())
    rec = {'rule': 'D-D12-1.1: on wraps of Ø ≤ 20 mm the cap floor is %.1f mm' % CAP_FLOOR_SMALL_WRAP_MM,
           'cap_at_the_sketch_scale_mm': round(cap_mm, 4), 'scale_to_the_floor': round(s, 5),
           'about_the_box_centre_mm': [round(cx, 4), round(cy, 4)],
           'box_at_the_sketch_scale_mm': [round(v, 3) for v in (bx0, by0, bx1, by1)],
           'box_at_the_floor_mm': [round(v, 3) for v in (rx0, ry0, rx1, ry1)], 'span_mm': list(third['span_mm']),
           'front_third_clearance_at_the_floor_mm': {'left': round(rx0 - lo, 3), 'right': round(hi - rx1, 3)},
           'front_third_clearance_at_the_sketch_scale_mm': {'left': round(bx0 - lo, 3), 'right': round(hi - bx1, 3)},
           'gap_to_the_hero_at_the_floor_mm': round(ry0 - hero_bottom_mm, 3),
           'lip_balm_move_down_mm': round(move_mm, 3), **checks, 'raised': raise_it}
    if not raise_it:
        rec['why'] = 'kept at the sketch\'s scale: ' + ', '.join('not %s' % k_.replace('_', ' ')
                                                                 for k_, v in checks.items() if not v)
        return placed, 0.0, rec
    back = lm.map_rings(raised, lambda p: (((cx + (p[0] - cx) / s) - transform['offset_mm'][0]) / transform['scale'],
                                           ((cy + (p[1] - cy) / s) - transform['offset_mm'][1]) / transform['scale']))
    a_, b_ = lm.rings_area(back, 24), lm.rings_area(rings, 24)
    rec['inverse_iou_with_the_source'] = round(float(a_.intersection(b_).area / a_.union(b_).area), 6)
    return raised, move_mm, rec


def body_master(folder, out, crop):
    """The body wrap (58.5 × 42): the dashes cleaned first; the hero بلسم read and traced by the shared reader (raster
    beneath, its foil and relief on carriers at opacity 0); "Enchanted Rose" the lid's own vector on the sketch's
    logotype box in the lid's rose-gold ink over its cleaned painted letters (raised to the 2.5 mm cap floor where it
    then still fits, ``logotype_floor``); "LIP BALM" live in the lid's Latin medium face over its cleaned painted line;
    the seam treated; the dashes and the stones proved on the plate. A pick whose hero breaks the front third (its
    crop.json check) is refused: the scaled path cleaned the painted hero with the stones beside it."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Finish, Group, Path as GPath, SolidFill, TextRun
    from apps.pipeline.services import zilal_sticker as zs
    ft = crop['front_third']
    if not ft['passes']:
        raise ValueError('the pick\'s hero breaks the front third as sketched (crop.json front_third: %s): the scaled '
                         'path is refused — it cleaned the painted hero with the stones near it (an indigo hole)' % ft)
    raw, sha, path = zlm.load_wrap(folder, 'body')
    rgb0, trim = trim_rows(raw, BODY_MM)
    k = trim['px_per_mm']
    dashes = find_dashes(rgb0, expected_dash_box(crop, 'body', trim))
    rgb, ridge_px, dash_px, sites, cleaning = clean_dashes(rgb0, dashes)
    ground = zlm.ground_lab(rgb)
    m = zlm.masks(rgb, ground)
    hero = zlm.hero_master(rgb, m, k)
    bw = body_words(rgb, m, k)
    found, name, third, line_box, gold_words = bw['found'], bw['name'], bw['third'], bw['line_box'], bw['gold_words']
    master = lid_master_record()
    inks = master['type']['inks']
    name_ink = master['name']['ink']
    hero_ink = master['hero']['ink']
    face = zs.faces()['medium']
    lip = zlm.line_fit('LIP BALM', line_box, k, face)
    rings, src = zlm.logotype_source()
    placed, transform = zlm.place_logotype(rings, src, name['box_px'], k)
    emitted, lip_move_mm, floor_rec = logotype_floor(rings, placed, transform,
                                                     master['name']['measures']['cap_height_mm'], third,
                                                     hero['letters'].bounds[3], lip['ink_mm'])
    if floor_rec['raised']:
        lip = dict(lip, baseline_mm=round(lip['baseline_mm'] + lip_move_mm, 4),
                   ink_mm=[lip['ink_mm'][0], round(lip['ink_mm'][1] + lip_move_mm, 4), lip['ink_mm'][2],
                           round(lip['ink_mm'][3] + lip_move_mm, 4)], moved_down_mm=round(lip_move_mm, 4))
        transform['cap_height_mm'] = round(CAP_FLOOR_SMALL_WRAP_MM, 3)
        transform['placed_ink_mm'] = floor_rec['box_at_the_floor_mm']
    else:
        transform['cap_height_mm'] = round(floor_rec['cap_at_the_sketch_scale_mm'], 3)
    transform['over_the_floor'] = bool(transform['cap_height_mm'] >= CAP_FLOOR_SMALL_WRAP_MM)
    lb = transform['placed_ink_mm']
    transform['inside_the_front_third'] = bool(third['span_mm'][0] <= lb[0] and lb[2] <= third['span_mm'][1])
    transform['floor'] = floor_rec

    # the cleaning: the painted logotype and "LIP BALM" (each its whole box grown 0.6 mm — ink, hairlines and drop
    # shadow — less the stones), never the hero's own raster (its silhouette grown 0.35 mm kept)
    hero_px = lm.raster_fill(hero['letters'], rgb.shape[:2], (0.0, 0.0), k)
    words = bw['words']
    words_box = (word_box_mask(rgb.shape[:2], name['box_px'], k, m, words)
                 | word_box_mask(rgb.shape[:2], line_box, k, m, words))
    keep = cv2.dilate(hero_px.astype(np.uint8), zlm.disc(zlm.odd_px(2 * zlm.HERO_CARRY_MM, k))).astype(bool)
    cleaned = words_box & ~keep
    up, plate, big, tiles = clean_up(rgb, cleaned, ground, BODY_MM[0])
    k_up = k * UP
    seam_px = int(round(zlm.SEAM_BAND_MM * k_up))
    letters_t = hero['letters']
    foil_geom, relief_geom = hero['foil'], hero['relief']
    closed = {'rule': 'D-D12-1.1', 'scaled': False,
              'said': 'the pick\'s hero passes the front-third check as sketched (crop.json): not scaled, its raster '
                      'kept in place beneath its foil and relief (as zilal_lipstick_master.body_master)'}
    proof_up = lm.prove_upscale(rgb, up, dash_zones(dashes))
    # [D-D12-8] the cleaning's ghost rebuilt on ground pixels (the word boxes and the dash lines); the plate as it was
    # kept as the proof's control
    control = plate
    plate, ground_up, edges, ghost = repair_ghost(rgb, control, big, cleaned, keep, dash_px, dashes, ground, k,
                                                  [('logotype box', name['box_px']), ('LIP BALM box', line_box)],
                                                  seam_px)
    residue = lm.residue(plate, big)
    residue['calm'] = zlm.residue_calm(plate, big, ground, k_up)
    residue['said'] = ('lid_master.residue reads its ground from every pixel outside the mask (stones and the hero beside '
                       'the cleaning included); the calm reading is the ghost against the calm ground; read after the '
                       'rebuild (D-D12-8)')
    plate, seam = treat_seam(plate, k_up, OVERLAP_MM)
    control, _ = treat_seam(control, k_up, OVERLAP_MM)
    ghost = prove_ghost(ghost, plate, control, rgb0, ground_up, edges, big, k_up, seam_px,
                        out / 'engine' / 'body-plate-control.png')
    dash = dash_proof(rgb0, plate, dashes, sites, BODY_MM[0])
    stones = stones_proof(rgb0, rgb, ridge_px, words, plate, k, seam_px, BODY_MM[0])
    plate_png = out / 'engine' / 'body-plate.png'
    Image.fromarray(plate).save(plate_png)
    foil = Finish(kind='foil', plate=zm.FOIL_PLATE, appearance=Color.from_hex(hero_ink))
    emboss = Finish(kind='emboss', plate=zm.EMBOSS_PLATE)
    extra = {}
    if lip['tracking_em'] > 0:
        extra['tracking_em'] = lip['tracking_em']
    children = [
        Group(name='TYPE', role='typography', children=[
            TextRun(name='lip balm', text='Lip Balm', x=lip['x_centre_mm'], y=lip['baseline_mm'], font=face['role'],
                    size_pt=lip['size_pt'], color=Color.from_hex(inks['eyeshadow']), align='center', text_case='upper',
                    **extra)]),
        Group(name='LOGOTYPE', role='typography', actual_text='Enchanted Rose', children=[
            GPath(name='Enchanted Rose', segments=lm.rings_segments(emitted), fill=SolidFill(color=Color.from_hex(name_ink)),
                  fill_rule='evenodd')]),
        Group(name='HERO CARRIERS', role='effects', opacity=0.0, actual_text='بلسم', children=[
            GPath(name='بلسم (foil)', segments=zm.poly_segments(foil_geom), fill=SolidFill(color=Color.from_hex(hero_ink)),
                  fill_rule='evenodd', finishes=[foil]),
            GPath(name='بلسم (relief)', segments=zm.poly_segments(relief_geom),
                  fill=SolidFill(color=Color.from_hex(hero_ink)), fill_rule='evenodd', finishes=[emboss])])]
    engine = out / 'engine' / 'body-engine.ai'
    emit_pdf_ai(wrap_document(plate_png, children, 'lip balm body wrap', BODY_MM, BODY_MM[0]), str(engine))
    proof_ai = out / 'engine' / 'body-proof-engine.ai'
    emit_pdf_ai(wrap_document(plate_png, children, 'lip balm body wrap', BODY_MM, PROOF_PAGE_W_MM), str(proof_ai))
    files = files_of(out, 'body', engine, proof_ai, BODY_MM, True)
    hx0, hy0, hx1, hy1 = letters_t.bounds
    lo, hi = third['span_mm']
    hero_third = {'rule': 'D-D12-1.1: the hero in the front third, re-measured on the master\'s own hero vectors',
                  'hero_vectors_mm': [round(hx0, 3), round(hy0, 3), round(hx1, 3), round(hy1, 3)],
                  'hero_width_mm': round(hx1 - hx0, 3), 'span_mm': third['span_mm'],
                  'left_clearance_mm': round(hx0 - lo, 3), 'right_clearance_mm': round(hi - hx1, 3),
                  'inside': bool(lo <= hx0 and hx1 <= hi),
                  'inside_the_safe_height': bool(hy0 >= BLEED_TB_MM + SAFE_TB_MM
                                                 and hy1 <= BODY_MM[1] - BLEED_TB_MM - SAFE_TB_MM),
                  'sketch_check': ft}
    parts = [{'bounds_mm': [round(v, 3) for v in g.bounds], 'area_mm2': round(float(g.area), 3), 'holes': len(g.interiors)}
             for g in lm.parts(hero['letters'])]
    lip['inside_the_front_third'] = bool(lo <= lip['ink_mm'][0] and lip['ink_mm'][2] <= hi)
    lip['cap_over_the_floor'] = bool(lip['cap_mm'] >= CAP_FLOOR_SMALL_WRAP_MM)
    lip['size_over_5_pt'] = bool(lip['size_pt'] >= zlm.FLOOR_PT)
    return {'sketch': {'path': lm.rel(path), 'sha256': sha}, 'trim': trim, 'ground': zlm.lab_hex(ground),
            'front_third': third, 'hero_in_the_front_third': hero_third, 'closed': closed,
            'hero': dict(hero['record'], letter_parts=parts, letters_mm2=round(float(hero['letters'].area), 3),
                         scaled_letters_mm2=round(float(letters_t.area), 3), foil_set_mm2=round(float(foil_geom.area), 3)),
            'logotype': {'source': src, 'sketch_box_px': name['box_px'], **transform},
            'lip_balm': dict(lip, sketch_box_px=line_box, ink=inks['eyeshadow'], face=face['role']),
            'dashes': {'found': dashes, 'cleaning': cleaning, **dash}, 'stones': stones,
            'cleaned': {'words': 'the painted logotype and "LIP BALM": each box grown %.1f mm (ink, hairlines, drop shadow) '
                                 'less the stones, the hero\'s silhouette grown %.2f mm kept' % (zlm.BOX_GROW_MM,
                                                                                                zlm.HERO_CARRY_MM),
                        'px_up': int(big.sum()), 'tiles': tiles},
            'residue': residue, 'ghost': ghost, 'upscale': proof_up, 'seam': seam,
            'plate_ppi': plate_ppi(plate, BODY_MM), 'files': files,
            'boxes_mm': {'hero': [round(v, 3) for v in letters_t.bounds], 'logotype': transform['placed_ink_mm'],
                         'lip_balm': lip['ink_mm']}}


# --- the cap ----------------------------------------------------------------------------------------------------------

def cap_master(folder, out, crop):
    """The cap wrap (58.5 × 32): the dashes cleaned first; the stones as sketched; the painted logo cleaned by its box
    (``word_box_mask``) and the approved logo set by ``lm.logo_parts`` in the lid's logo ink on the sketch's box
    (``zlm.cap_logo_box``: its width, centred); the seam treated."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Group
    raw, sha, path = zlm.load_wrap(folder, 'cap')
    rgb0, trim = trim_rows(raw, CAP_MM)
    k = trim['px_per_mm']
    dashes = find_dashes(rgb0, expected_dash_box(crop, 'cap', trim))
    rgb, ridge_px, dash_px, sites, cleaning = clean_dashes(rgb0, dashes)
    ground = zlm.ground_lab(rgb)
    m = zlm.masks(rgb, ground)
    logo = zlm.cap_logo_box(rgb, m, k)
    # the painted logo cleaned by its whole box grown 0.6 mm less the stones (``word_box_mask``: its ink, its
    # anti-aliased copper edge and its drop shadow, which is darker than the ground and not "off" it) — ``zlm.own_near`` left the
    # shadow's letter shapes and copper specks behind here; the logo stands on open indigo, clear of the veins
    cleaned = word_box_mask(rgb.shape[:2], logo['box_px'], k, m, logo['mask'])
    up, plate, big, tiles = clean_up(rgb, cleaned, ground, CAP_MM[0])
    k_up = k * UP
    seam_px = int(round(zlm.SEAM_BAND_MM * k_up))
    proof_up = lm.prove_upscale(rgb, up, dash_zones(dashes))
    # [D-D12-8] the cleaning's ghost rebuilt on ground pixels (the logo's box and the dash lines), as the body's
    control = plate
    plate, ground_up, edges, ghost = repair_ghost(rgb, control, big, cleaned, np.zeros(rgb.shape[:2], dtype=bool),
                                                  dash_px, dashes, ground, k, [('logo box', logo['box_px'])], seam_px)
    residue = lm.residue(plate, big)
    residue['calm'] = zlm.residue_calm(plate, big, ground, k_up)
    plate, seam = treat_seam(plate, k_up, OVERLAP_MM)
    control, _ = treat_seam(control, k_up, OVERLAP_MM)
    ghost = prove_ghost(ghost, plate, control, rgb0, ground_up, edges, big, k_up, seam_px,
                        out / 'engine' / 'cap-plate-control.png')
    dash = dash_proof(rgb0, plate, dashes, sites, CAP_MM[0])
    stones = stones_proof(rgb0, rgb, ridge_px, logo['mask'], plate, k, seam_px, CAP_MM[0])
    plate_png = out / 'engine' / 'cap-plate.png'
    Image.fromarray(plate).save(plate_png)
    master = lid_master_record()
    x0, y0, x1, y1 = logo['box_mm']
    w = x1 - x0
    h = w * LOGO_ASPECT
    cy = (y0 + y1) / 2
    box = (x0, cy - h / 2, w, h)
    children = [Group(name='LOGO', role='logo', children=lm.logo_parts(box, master['logo']['ink'], foil_letters=False))]
    engine = out / 'engine' / 'cap-engine.ai'
    emit_pdf_ai(wrap_document(plate_png, children, 'lip balm cap wrap', CAP_MM, CAP_MM[0]), str(engine))
    proof_ai = out / 'engine' / 'cap-proof-engine.ai'
    emit_pdf_ai(wrap_document(plate_png, children, 'lip balm cap wrap', CAP_MM, PROOF_PAGE_W_MM), str(proof_ai))
    files = files_of(out, 'cap', engine, proof_ai, CAP_MM, None)
    third = zlm.front_third(CAP_MM[0], CASE_D_MM)
    placed = [round(v, 3) for v in (x0, cy - h / 2, x1, cy + h / 2)]
    return {'sketch': {'path': lm.rel(path), 'sha256': sha}, 'trim': trim, 'ground': zlm.lab_hex(ground),
            'logo': {'sketch_box_mm': logo['box_mm'], 'placed_mm': placed, 'ink': master['logo']['ink'],
                     'inside_the_front_third': bool(third['span_mm'][0] <= placed[0] and placed[2] <= third['span_mm'][1])},
            'dashes': {'found': dashes, 'cleaning': cleaning, **dash}, 'stones': stones,
            'cleaned': {'logo': 'its box grown %.1f mm less the stones (ink, copper edge, drop shadow)' % zlm.BOX_GROW_MM,
                        'px_up': int(big.sum()), 'tiles': tiles}, 'residue': residue, 'ghost': ghost,
            'upscale': proof_up, 'seam': seam,
            'plate_ppi': plate_ppi(plate, CAP_MM), 'files': files}


# --- the bottom label Ø 16 (zilal_lipstick_master.label_master at the balm's size and copy) --------------------------

LABEL_D_MM = 16.0                                 # D-D12-3: the bottom label Ø 16
LABEL_BLEED_MM = 1.0
LABEL_SAFE_MM = 1.0
LABEL_TINT = 'Rosewater'                          # D-D11-8's tint (⟪PROVISIONAL⟫)
LABEL_NET_G = '4.5 g'                             # D-D11-8: 4.5 g ℮ 0.15 oz, on two rows (D-D11-11)
LABEL_NET_OZ = '0.15 oz'
LABEL_TINT_CAP_MM = zlm.LABEL_SHADE_CAP_MM        # 1.5 mm, shrunk evenly where the chord asks (never under 5 pt)
LABEL_FIGURE_CAP_MM = zlm.LABEL_FIGURE_CAP_MM     # the figures 2 mm (D-D12-3)
LABEL_SIGN_MM = zlm.LABEL_SIGN_MM                 # the ℮ exactly 3 mm (D-D12-1.2)
LABEL_BATCH_CAP_MM = zlm.LABEL_BATCH_CAP_MM       # 5.1 pt: over the 5 pt floor
LABEL_ROW_GAP_MM = zlm.LABEL_ROW_GAP_MM
LABEL_BATCH_GAP_MM = 1.0                          # "BATCH" to its write-in rule
LABEL_BATCH_RULE_MM = 4.0                         # the lipstick's rule, shortened to the chord where the ring asks
LABEL_BATCH_RULE_MIN_MM = 2.0                     # a write-in rule shorter than 2 mm is listed
LABEL_RULE_THICK_MM = 0.12
LABEL_RULE_CLEAR_MM = 0.2                         # the shortened rule ends 0.2 mm inside the chord's room
LABEL_SHRINK_STEP_MM = 0.01                       # the tint shrunk evenly by 0.01 mm of cap height a step
FLOOR_PT = zlm.FLOOR_PT


def cap_ratio(face):
    from fontTools.ttLib import TTFont
    font = TTFont(face['path'])
    return font['OS/2'].sCapHeight / font['head'].unitsPerEm


def label_rows(face, ratio, tint_cap_mm, rule_mm):
    """The label's four rows stacked about the circle's centre (row gap 0.9 mm): each its size, its width, its box and
    the safe circle's chord at its farthest edge from the centre (the row inside the ring when its width ≤ the chord)."""
    page = LABEL_D_MM + 2 * LABEL_BLEED_MM
    c = page / 2
    r_safe = LABEL_D_MM / 2 - LABEL_SAFE_MM
    spec = [('tint', LABEL_TINT, tint_cap_mm, tint_cap_mm), ('net-1', LABEL_NET_G, LABEL_FIGURE_CAP_MM, LABEL_SIGN_MM),
            ('net-2', LABEL_NET_OZ, LABEL_FIGURE_CAP_MM, LABEL_FIGURE_CAP_MM),
            ('batch', 'BATCH', LABEL_BATCH_CAP_MM, LABEL_BATCH_CAP_MM)]
    total = sum(s[3] for s in spec) + LABEL_ROW_GAP_MM * (len(spec) - 1)
    y = c - total / 2
    rows = []
    for key, text, cap_mm, height_mm in spec:
        base = y + height_mm
        size_pt = cap_mm / ratio * lm.PT_PER_MM
        text_w = zlm.zs_width(text, face, size_pt)
        row = {'row': key, 'text': text, 'cap_mm': round(cap_mm, 4), 'height_mm': height_mm, 'size_pt': round(size_pt, 3),
               'text_width_mm': round(text_w, 3)}
        if key == 'net-1':
            space = zlm.zs_width(' ', face, size_pt)
            sign_w = LABEL_SIGN_MM * zlm.sign_aspect()
            width = text_w + space + sign_w
            row.update(space_mm=round(space, 4), sign_w_mm=round(sign_w, 4))
        elif key == 'batch':
            width = text_w + LABEL_BATCH_GAP_MM + rule_mm
            row.update(rule_mm=round(rule_mm, 3))
        else:
            width = text_w
        worst = max(abs(y - c), abs(base - c))
        chord = 2.0 * float(np.sqrt(max(r_safe ** 2 - worst ** 2, 0.0)))
        x0 = c - width / 2
        row.update(width_mm=round(width, 3), chord_mm=round(chord, 3), inside_safe=bool(width <= chord),
                   box_mm=[round(x0, 4), round(y, 4), round(x0 + width, 4), round(base, 4)], top_mm=y, base_mm=base,
                   x0_mm=x0, chord_raw_mm=chord, text_raw_mm=text_w, die_clearance_mm=round(LABEL_D_MM / 2 - float(np.hypot(width / 2, worst)), 3),
                   above_floor=bool(size_pt >= FLOOR_PT))
        rows.append(row)
        y = base + LABEL_ROW_GAP_MM
    return rows


def fit_label(face):
    """The rows fitted to the safe ring: the tint (1.5 mm cap) shrunk evenly by 0.01 mm steps while wider than its chord,
    never under the 5 pt floor (if still too wide: reported, never dropped); the batch rule the lipstick's 4 mm, or the
    room its chord leaves (listed when under 2 mm). The figures (2 mm) and the ℮ (3 mm) are never shrunk."""
    ratio = cap_ratio(face)
    floor_cap_mm = FLOOR_PT / lm.PT_PER_MM * ratio
    tint = LABEL_TINT_CAP_MM
    steps = 0
    while True:
        rows = label_rows(face, ratio, tint, LABEL_BATCH_RULE_MM)
        if rows[0]['inside_safe'] or tint - LABEL_SHRINK_STEP_MM < floor_cap_mm:
            break
        tint -= LABEL_SHRINK_STEP_MM
        steps += 1
    batch = rows[3]
    room = batch['chord_raw_mm'] - batch['text_raw_mm'] - LABEL_BATCH_GAP_MM
    rule = min(LABEL_BATCH_RULE_MM, float(np.floor((room - LABEL_RULE_CLEAR_MM) * 100.0) / 100.0))
    rows = label_rows(face, ratio, tint, rule)
    return rows, {'tint_cap_mm': round(tint, 3), 'tint_shrunk_by_mm': round(LABEL_TINT_CAP_MM - tint, 3),
                  'tint_steps': steps, 'tint_floor_cap_mm': round(floor_cap_mm, 4), 'tint_fits': rows[0]['inside_safe'],
                  'batch_rule_mm': round(rule, 3), 'batch_rule_room_mm': round(room, 3),
                  'batch_rule_shortened': bool(rule < LABEL_BATCH_RULE_MM),
                  'batch_rule_over_the_minimum': bool(rule >= LABEL_BATCH_RULE_MIN_MM), 'cap_ratio': round(ratio, 5)}


def sign_proof(segs, base_mm, space_mm):
    """D-D12-1.2 read on the ℮ as emitted: the lid's own sign (``lid_master.sign_segments``: the same outline, its
    segments' kinds and order, scaled), its ink exactly 3 mm, standing on the figures' baseline, a word space after the
    figures."""
    ink = zlm.sign_ink(segs)
    lid_segs, _ = lm.sign_segments((0.0, 0.0, 1.0, 1.0))
    same = len(segs) == len(lid_segs) and [type(s).__name__ for s in segs] == [type(s).__name__ for s in lid_segs]
    unit = zlm.sign_ink(lid_segs)
    # the emitted outline mapped back onto the unit box's ink: the same shape point for point
    sx = (ink[2] - ink[0]) / (unit[2] - unit[0])
    sy = (ink[3] - ink[1]) / (unit[3] - unit[1])
    worst = 0.0
    for a, b in zip(segs, lid_segs):
        for fx, fy in (('x', 'y'), ('x1', 'y1'), ('x2', 'y2')):
            if hasattr(b, fx):
                ax = (getattr(a, fx) - ink[0]) / sx + unit[0]
                ay = (getattr(a, fy) - ink[1]) / sy + unit[1]
                worst = max(worst, abs(ax - getattr(b, fx)), abs(ay - getattr(b, fy)))
    return {'rule': 'D-D12-1.2', 'the_lids_sign': bool(same and worst < 1e-6), 'shape_error_unit': float(worst),
            'sign_source': 'lid_master.sign_segments (estimated_sign: the glyph the lid\'s net line "27 g ℮ 0.95 oz" draws)',
            'ink_height_mm': round(ink[3] - ink[1], 4), 'exactly_3_mm': bool(abs((ink[3] - ink[1]) - LABEL_SIGN_MM) < 0.001),
            'ink_bottom_mm': round(ink[3], 4), 'figures_baseline_mm': round(base_mm, 4),
            'on_the_baseline': bool(abs(ink[3] - base_mm) < 0.001), 'word_space_mm': round(space_mm, 4),
            'figures_cap_mm': LABEL_FIGURE_CAP_MM, 'ink_box_mm': [round(v, 4) for v in ink]}


def label_master(out, ground_hex, cream_hex):
    """The bottom label Ø 16 (D-D12-3), composed by the engine in the lid's language: the indigo ground, the tint
    "Rosewater", the net content on two rows ("4.5 g ℮" / "0.15 oz": figures 2 mm, the ℮ exactly 3 mm, the lid's sign),
    a batch write-in field; every row inside the 1 mm safe ring (its chord); page 2 the die circle and the safe ring."""
    import fitz
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, Path as GPath, Rect, SolidFill, TextRun
    from apps.pipeline.services import zilal_sticker as zs
    face = zs.faces()['medium']
    rows, fit = fit_label(face)
    page = LABEL_D_MM + 2 * LABEL_BLEED_MM
    c = page / 2
    r_safe = LABEL_D_MM / 2 - LABEL_SAFE_MM
    ink = Color.from_hex(cream_hex)
    nodes = [Rect(name='ground', x=0.0, y=0.0, w=page, h=page, fill=SolidFill(color=Color.from_hex(ground_hex)))]
    sign = None
    for row in rows:
        x0, base, size_pt = row['x0_mm'], row['base_mm'], row['size_pt']
        if row['row'] == 'net-1':
            nodes.append(TextRun(name='net:figures', text=row['text'], x=x0, y=base, font=face['role'], size_pt=size_pt,
                                 color=ink))
            sx0 = x0 + row['text_width_mm'] + row['space_mm']
            segs, _ = lm.sign_segments((sx0, base - LABEL_SIGN_MM, sx0 + row['sign_w_mm'], base))
            nodes.append(Group(name='net:sign', actual_text=lm.SIGN, children=[
                GPath(name=lm.SIGN, segments=segs, fill=SolidFill(color=ink), fill_rule='nonzero')]))
            sign = sign_proof(segs, base, row['space_mm'])
        elif row['row'] == 'batch':
            nodes.append(TextRun(name='batch', text=row['text'], x=x0, y=base, font=face['role'], size_pt=size_pt, color=ink))
            nodes.append(Rect(name='batch line', x=x0 + row['text_width_mm'] + LABEL_BATCH_GAP_MM, y=base - 0.1,
                              w=row['rule_mm'], h=LABEL_RULE_THICK_MM, fill=SolidFill(color=ink)))
        else:
            nodes.append(TextRun(name=row['row'], text=row['text'], x=c, y=base, font=face['role'], size_pt=size_pt,
                                 color=ink, align='center'))
    doc = Document(page_w=page, page_h=page, title='lip balm bottom label', metadata={'typography_surface': SURFACE,
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
                         {'startpage': 1, 'prefix': '2 die Ø 16 and the 1 mm safe ring ', 'style': ''}])
    pdf.set_metadata({'title': 'the lip balm\'s bottom label Ø 16', 'creator': SURFACE})
    pdf.save(str(out / 'label.pdf'), garbage=3, deflate=True)
    pdf.close()
    lm.render_png(out / 'label.pdf', 0, 600, out / 'label-flat.png')
    with_die = label_with_die(out / 'label-flat.png', out / 'label-with-die.png')
    record = [{k_: v for k_, v in r.items() if k_ not in ('top_mm', 'base_mm', 'x0_mm', 'chord_raw_mm', 'text_raw_mm')} for r in rows]
    return {'diameter_mm': LABEL_D_MM, 'bleed_mm': LABEL_BLEED_MM, 'safe_mm': LABEL_SAFE_MM, 'rows': record, 'fit': fit,
            'sign': sign,
            'holds': {'inside_safe': all(r['inside_safe'] for r in rows), 'above_floor': all(r['above_floor'] for r in rows),
                      'figures_2_mm': all(r['cap_mm'] == LABEL_FIGURE_CAP_MM for r in rows if r['row'] in ('net-1', 'net-2')),
                      'sign_3_mm': bool(sign['exactly_3_mm']), 'sign_on_the_baseline': bool(sign['on_the_baseline']),
                      'the_lids_sign': bool(sign['the_lids_sign'])},
            'said': 'D-D11-11 / D-D12-3: on the label the ℮ stands at its legal 3 mm though taller than its 2 mm figures',
            'files': {'pdf': lm.rel(out / 'label.pdf'), 'flat': lm.rel(out / 'label-flat.png'), 'with_die': lm.rel(with_die)}}


def label_with_die(flat_png, dest):
    """The label's flat with its die circle (magenta) and its 1 mm safe ring (blue, dashed) drawn over it (to look)."""
    label = np.asarray(Image.open(flat_png).convert('RGB')).copy()
    k = label.shape[1] / (LABEL_D_MM + 2 * LABEL_BLEED_MM)
    c = (int(round(label.shape[1] / 2)), int(round(label.shape[0] / 2)))
    cv2.circle(label, c, int(round(LABEL_D_MM / 2 * k)), (220, 0, 140), 3, lineType=cv2.LINE_AA)
    r = int(round((LABEL_D_MM / 2 - LABEL_SAFE_MM) * k))
    for a in range(0, 360, 12):
        cv2.ellipse(label, c, (r, r), 0, a, a + 6, (0, 150, 230), 2, lineType=cv2.LINE_AA)
    Image.fromarray(label).save(dest)
    return dest


# --- the A4 at 100 % ---------------------------------------------------------------------------------------------------

def a4_page(out):
    """One A4 page at 100 %: the body wrap, the cap wrap and the label at true size, each with its name; crop marks at
    each PDF's trim box (the bleed outside them); a 100 mm bar to check the print."""
    import fitz
    pdf = fitz.open()
    page = pdf.new_page(width=lm.pt(297.0), height=lm.pt(210.0))
    places = [('body-wrap.pdf', 20.0, 30.0, 'body wrap %.1f × %.0f mm (the seam at the back: the right end over the left '
                                             'start)' % BODY_MM),
              ('cap-wrap.pdf', 20.0, 95.0, 'cap wrap %.1f × %.0f mm' % CAP_MM),
              ('label.pdf', 110.0, 30.0, 'bottom label Ø %.0f mm' % LABEL_D_MM)]
    marks = []
    for name, x, y, words in places:
        with fitz.open(str(out / name)) as src:
            t = src[0].trimbox
            w_mm, h_mm = src[0].rect.width * zlm.MM_PER_PT, src[0].rect.height * zlm.MM_PER_PT
            tx0, ty0 = x + t.x0 * zlm.MM_PER_PT, y + t.y0 * zlm.MM_PER_PT
            tx1, ty1 = x + t.x1 * zlm.MM_PER_PT, y + t.y1 * zlm.MM_PER_PT
            page.show_pdf_page(fitz.Rect(lm.pt(x), lm.pt(y), lm.pt(x + w_mm), lm.pt(y + h_mm)), src, 0)
        page.insert_text(fitz.Point(lm.pt(x), lm.pt(y - 8)), words, fontsize=7, fontname='helv')   # above the marks
        for cx, cy, sx, sy in ((tx0, ty0, -1, -1), (tx1, ty0, 1, -1), (tx0, ty1, -1, 1), (tx1, ty1, 1, 1)):
            page.draw_line(fitz.Point(lm.pt(cx + sx * 6), lm.pt(cy)), fitz.Point(lm.pt(cx + sx * 2), lm.pt(cy)), width=0.3)
            page.draw_line(fitz.Point(lm.pt(cx), lm.pt(cy + sy * 6)), fitz.Point(lm.pt(cx), lm.pt(cy + sy * 2)), width=0.3)
        marks.append({'file': name, 'at_mm': [x, y], 'trim_mm': [round(v, 3) for v in (tx0, ty0, tx1, ty1)]})
    page.draw_line(fitz.Point(lm.pt(20), lm.pt(195)), fitz.Point(lm.pt(120), lm.pt(195)), width=0.5)
    page.insert_text(fitz.Point(lm.pt(20), lm.pt(192)), '100 mm (print at 100 %)', fontsize=7, fontname='helv')
    pdf.set_metadata({'title': 'the lip balm at 100 %', 'creator': SURFACE})
    pdf.save(str(out / 'balm-1to1-A4.pdf'), garbage=3, deflate=True)
    pdf.close()
    lm.render_png(out / 'balm-1to1-A4.pdf', 0, 150, out / 'balm-1to1-A4.png')
    return {'pdf': lm.rel(out / 'balm-1to1-A4.pdf'), 'png': lm.rel(out / 'balm-1to1-A4.png'), 'placed': marks,
            'bar_mm': 100.0}


# --- the build ---------------------------------------------------------------------------------------------------------

def build(out_dir):
    """D-D12-3 at $0 for the pick ``zilal_balm.the_pick()`` returns when it runs: the body, the cap, the bottom label
    (its ℮ proved), the A4 at 100 %, the finish sheet, the product drawing (D-D12-1.4); the record balm.json."""
    from apps.pipeline.services import product_drawing as pdw
    from apps.pipeline.services import zilal_object as zo
    pick, why, pick_flag = zb.the_pick()
    folder = zb.SKETCHES / pick
    checkpoint = zb.SKETCHES / 'pick.json'
    if checkpoint.exists():
        cp = json.loads(checkpoint.read_text(encoding='utf-8'))
        checkpoint_rec = dict({k_: cp[k_] for k_ in ('opened_at', 'closed_at', 'outcome', 'pick') if k_ in cp},
                              record=lm.rel(checkpoint), agrees=bool('pick' in cp and cp['pick'] == pick))
    else:
        checkpoint_rec = {'record': None, 'said': 'no checkpoint record (pick.json) when the build ran'}
    crop = crop_record(folder)
    out = Path(out_dir)
    (out / 'engine').mkdir(parents=True, exist_ok=True)
    body = body_master(folder, out, crop)
    cap = cap_master(folder, out, crop)
    master = lid_master_record()
    label = label_master(out, body['ground'], master['type']['inks']['eyeshadow'])
    a4 = a4_page(out)
    scaled = not crop['front_third']['passes']
    # the finish sheet lays its words out as HTML (zilal_object.finish_sheet): the hero named in its own letters
    plates = [{'plate': 'print (body)', 'what': 'the sketch upscaled 2×, its dashed box cleaned, the cleaned ground '
                                                'rebuilt'},
              {'plate': 'type (body)', 'what': 'the logotype the lid\'s vector; "LIP BALM" live'},
              {'plate': 'print (cap)', 'what': 'the sketch upscaled 2×, its dashed box cleaned, the cleaned ground '
                                               'rebuilt; the approved logo'},
              {'plate': 'foil (rose gold)', 'what': 'the hero بلسم: its rim and hatch, pitch %.2f mm'
                                                    % body['hero']['hatch']['stroke']['pitch_mm']},
              {'plate': 'relief (emboss)', 'what': 'the hero بلسم: its silhouette'},
              {'plate': 'label', 'what': 'Ø 16: the tint, the net content on two rows, a batch field'}]
    zo.finish_sheet('the lip balm', REPO / body['files']['flat'], plates, out)
    third = body['front_third']
    bands = [('body', REPO / body['files']['finish_proof'], BODY_MM, BLEED_TB_MM, BODY_MM[1] - 2 * BLEED_TB_MM),
             ('cap', REPO / cap['files']['finish_proof'], CAP_MM, BLEED_TB_MM, CAP_MM[1] - 2 * BLEED_TB_MM)]
    drawing = pdw.draw('the Enchanted Rose lip balm', bands, CASE_D_MM, third['centre_mm'], OVERLAP_MM, cap['ground'],
                       out / 'balm-drawing.png')
    pdw.write_record(drawing, out / 'balm-drawing.json')
    lt = body['logotype']
    lb = body['lip_balm']
    fit = label['fit']
    every_line = [('%s %s' % (side, r['side']), r['gone']) for side, rec in (('body', body), ('cap', cap))
                  for r in rec['dashes']['lines']]
    not_gone = [name_ for name_, gone in every_line if not gone]
    held = [rec['stones'] for rec in (body, cap)]
    cleaned_px = [rec['dashes']['cleaning'] for rec in (body, cap)]
    allowed = [
        'each wrap upscaled Lanczos 2× (%.0f PPI at print size; the sketch %.0f)' % (
            body['plate_ppi'], body['plate_ppi'] / UP),
        'the sheet\'s dashed front-third box cleaned out of both wraps at the sketch\'s pixels: %d and %d ridge pixels '
        '(lighter than each side by over %.0f L*) with their %d and %d rim pixels (body, cap), each filled from the '
        'direction whose clean ends agree and explain it under the dash\'s own colour; by the ridge proof (bar %.0f L* '
        'per dash site) gone on %d of %d lines%s; the stones\' pixels %s (max ΔE76 %.2f body, %.2f cap, bar %.0f; '
        'against the uncleaned upscale itself %.2f and %.2f)' % (
            cleaned_px[0]['ridge_px'], cleaned_px[1]['ridge_px'], DASH_RIDGE_L, cleaned_px[0]['rim_px'],
            cleaned_px[1]['rim_px'], DASH_GONE_L, len(every_line) - len(not_gone), len(every_line),
            '' if not not_gone else ' (not proved: %s)' % ', '.join(not_gone),
            'unchanged — the stones of 0.3 mm² or more, read 2 px inside their edges and clear of the dash\'s ridge '
            'pixels (a smaller speck, or a vein thinner than that, is not read)' if all(h['holds'] for h in held)
            else 'NOT all unchanged',
            held[0]['max'], held[1]['max'], STONE_DE76_MAX, held[0]['plain']['max'], held[1]['plain']['max']),
        'بلسم traced by the shared reader (D-D12-9) and foiled as the lid\'s hero: its rim, groove and hatch at the '
        'painted %.2f° but the press\'s pitch %.2f mm (painted %.3f mm), its silhouette the relief; its raster beneath' % (
            body['hero']['hatch']['angle_deg'], body['hero']['hatch']['stroke']['pitch_mm'],
            body['hero']['hatch']['painted_pitch_mm']),
        '"Enchanted Rose" the lid\'s own vector × %.4f on the sketch\'s logotype box (inverse IoU %.1f), in the lid\'s '
        'rose-gold ink, its painted letters cleaned beneath' % (lt['scale'], lt['inverse_iou_with_the_source']),
        '"LIP BALM" live in the lid\'s Latin medium face at the sketch\'s size and place (cap %.3f mm), its painted '
        'line cleaned beneath' % lb['cap_mm'],
        'the cap\'s painted logo cleaned and the approved logo set on its box in the lid\'s logo ink',
        'each seam a 2 mm feathered band at the back (mean ΔE00 %.2f body, %.2f cap)' % (
            body['seam']['after']['mean'], cap['seam']['after']['mean'])]
    ghosts = [rec['ghost'] for rec in (body, cap)]
    proofs = [g['proof'] for g in ghosts]
    allowed.append(
        'the cleaning\'s ghost (D-D12-8, the eye\'s round 0) rebuilt on ground pixels only — never a stone, a vein, a '
        'letter or the hero: each cleaned box grown %.1f mm and each dash line ±%.1f mm (its tone ±%.1f mm), the tone a '
        'smooth field held at the untouched ground\'s local tone (a first-order fit, σ %.2f mm) just outside, the grain '
        'the ground\'s own from random %.0f mm patches of the untouched ground near by (%d and %d px rebuilt, body and '
        'cap, with %d and %d px of the dash\'s dark rim and %d and %d of its specks); by the ghost proof no straight edge '
        'on %d of %d edges read (body) and %d of %d (cap; on each wrap the top dash line runs through the stones and '
        'reads no ground), against bars from the uncleaned sketch\'s own ground (the median bin\'s step %.2f and %.2f '
        'L*, line %.2f and %.2f L*), the plate before the rebuild failing it on %d and %d edges; the same rule holds on '
        '%d of %d and %d of %d parallel copies of the edges on the uncleaned ground (its false alarms there)' % (
            REBUILD_BOX_MM, REBUILD_LINE_MM, REBUILD_TONE_LINE_MM, REBUILD_TONE_SIGMA_MM, REBUILD_PATCH_MM,
            ghosts[0]['grain_px'], ghosts[1]['grain_px'], ghosts[0]['ground']['dash_rim_px_taken_as_ground'],
            ghosts[1]['ground']['dash_rim_px_taken_as_ground'], ghosts[0]['ground']['dash_specks_taken_as_ground'],
            ghosts[1]['ground']['dash_specks_taken_as_ground'],
            proofs[0]['edges_read'] - len(proofs[0]['edges_failing_after']), proofs[0]['edges_read'],
            proofs[1]['edges_read'] - len(proofs[1]['edges_failing_after']), proofs[1]['edges_read'],
            proofs[0]['bars']['step_median_bar_L'], proofs[1]['bars']['step_median_bar_L'],
            proofs[0]['bars']['line_median_bar_L'], proofs[1]['bars']['line_median_bar_L'],
            len(proofs[0]['edges_failing_on_the_control']), len(proofs[1]['edges_failing_on_the_control']),
            proofs[0]['parallel_control']['copies_holding'], proofs[0]['parallel_control']['copies_read'],
            proofs[1]['parallel_control']['copies_holding'], proofs[1]['parallel_control']['copies_read']))
    floor = lt['floor']
    if floor['raised']:
        allowed.append('"Enchanted Rose" raised × %.5f about its own box centre to the %.1f mm cap floor (D-D12-1.1), '
                       'inside the front third (clear %.3f / %.3f mm), "LIP BALM" moved down %.3f mm' % (
                           floor['scale_to_the_floor'], CAP_FLOOR_SMALL_WRAP_MM,
                           floor['front_third_clearance_at_the_floor_mm']['left'],
                           floor['front_third_clearance_at_the_floor_mm']['right'], floor['lip_balm_move_down_mm']))
    if fit['tint_shrunk_by_mm'] > 0:
        allowed.append('"%s" shrunk evenly to a %.2f mm cap (%.2f pt) to stand inside the safe ring' % (
            LABEL_TINT, fit['tint_cap_mm'], label['rows'][0]['size_pt']))
    if fit['batch_rule_shortened']:
        allowed.append('the batch write-in rule %.2f mm (the lipstick\'s 4 mm does not fit the Ø 16 ring\'s chord)'
                       % fit['batch_rule_mm'])
    listed = []
    if not lt['over_the_floor']:
        listed.append('"Enchanted Rose" keeps the sketch\'s scale, its cap %.3f mm under the %.1f mm floor (D-D12-1.1): '
                      'raised × %.5f about its own box centre it would span %.3f–%.3f mm against the front third\'s '
                      '%.3f–%.3f (clear %.3f mm left, %.3f mm right); %s' % (
                          lt['cap_height_mm'], CAP_FLOOR_SMALL_WRAP_MM, floor['scale_to_the_floor'],
                          floor['box_at_the_floor_mm'][0], floor['box_at_the_floor_mm'][2], floor['span_mm'][0],
                          floor['span_mm'][1], floor['front_third_clearance_at_the_floor_mm']['left'],
                          floor['front_third_clearance_at_the_floor_mm']['right'], floor['why']))
    if not lb['cap_over_the_floor']:
        listed.append('"LIP BALM" keeps its sketched cap %.3f mm (%.2f pt), under the 2.5 mm floor (as the lipstick\'s '
                      '"LIPSTICK"): listed, not resolved' % (lb['cap_mm'], lb['size_pt']))
    if not lb['size_over_5_pt']:
        listed.append('"LIP BALM" at %.2f pt is under the 5 pt floor' % lb['size_pt'])
    outer = body['hero']['trace']['outer_dark_edge']
    if not outer['holds']:
        listed.append('the hero\'s outer-dark-edge proof does not hold everywhere: max %.3f mm, %d of %d points over '
                      '0.3 mm (%.2f %% within) — recorded as read (the lipstick\'s also did not hold)' % (
                          outer['max_mm'], outer['over_0_3_mm'], outer['points'], 100 * outer['within_0_3_mm_share']))
    if not fit['tint_fits']:
        listed.append('"%s" does not fit the safe ring even at the 5 pt floor: reported, not dropped' % LABEL_TINT)
    if not fit['batch_rule_over_the_minimum']:
        listed.append('the batch write-in rule is %.2f mm, under 2 mm' % fit['batch_rule_mm'])
    if not crop['qualifies']:
        listed.append('the pick %s does not qualify on aspect (crop.json): built as the owner picked it' % pick)
    for side, rec in (('body', body), ('cap', cap)):
        if not all(rec['upscale']['holds'].values()):
            where = rec['upscale']['pixels_over_max_where']
            listed.append('the %s\'s upscale proof: %s over its bar (max ΔE00 %.2f against %.0f; mean %.3f, SSIM %.4f) — as '
                          'the lipstick\'s; of its %d pixels over the bar, %d lie in the dash bands (%s)' % (
                              side, [k_ for k_, v in rec['upscale']['holds'].items() if not v],
                              rec['upscale']['de00_max'], rec['upscale']['bars']['de00_max_lt'],
                              rec['upscale']['de00_mean'], rec['upscale']['ssim'], rec['upscale']['pixels_over_max'],
                              sum(v for k_, v in where.items() if k_.startswith('dash ')),
                              ', '.join('%s %d' % (k_, v) for k_, v in where.items())))
        if rec['files']['foil_limits']['holds'] is False:
            listed.append('the %s\'s foil limits do not hold' % side)
        for r in rec['dashes']['lines']:
            if not r['competent']:
                listed.append('the %s\'s %s dashed line: the ridge proof is not competent there (the uncleaned upscale '
                              'reads %.2f L*, not over the %.0f L* bar): not proved gone' % (
                                  side, r['side'], r['before_max_L'], DASH_GONE_L))
            elif not r['gone']:
                listed.append('the %s\'s %s dashed line is not proved gone: %d dash site(s) over %.0f L* after (%s)' % (
                    side, r['side'], len(r['sites_over_the_bar_after']), DASH_GONE_L,
                    ', '.join('%.2f L* at %.2f mm' % (q['after_L'], q['at_mm']) for q in r['sites_over_the_bar_after'])))
            if r['sites_with_a_peak_over_the_bar_after']:
                listed.append('the %s\'s %s dashed line: a single-pixel ridge over %.0f L* remains at %d dash site(s) after '
                              '(%s) — a speck of the dash or a vein crossing the line; the ridge proof cannot tell which' % (
                                  side, r['side'], DASH_GONE_L, len(r['sites_with_a_peak_over_the_bar_after']),
                                  ', '.join('%.2f L* at %.2f mm' % (q['peak_L'], q['at_mm'])
                                            for q in r['sites_with_a_peak_over_the_bar_after'])))
            if r['sites_the_proof_cannot_see']:
                listed.append('the %s\'s %s dashed line: %d of %d dash sites read %.0f L* or less even uncleaned (the '
                              'proof cannot see them there), at %s mm' % (
                                  side, r['side'], len(r['sites_the_proof_cannot_see']), r['sites_read'], DASH_GONE_L,
                                  ', '.join('%.2f' % q['at_mm'] for q in r['sites_the_proof_cannot_see'])))
        if not rec['stones']['holds']:
            listed.append('the %s\'s stones are not untouched: %d stone pixels over ΔE76 %.0f (max %.2f at %s mm)' % (
                side, rec['stones']['over_2'], STONE_DE76_MAX, rec['stones']['max'], rec['stones']['worst_at_mm']))
        if not rec['seam']['holds']:
            listed.append('the %s\'s seam does not hold (mean ΔE00 %.2f)' % (side, rec['seam']['after']['mean']))
        gp = rec['ghost']['proof']
        if gp['edges_not_read']:
            listed.append('the %s\'s ghost proof reads no ground bin along %s (stones or veins all along): not read, '
                          'not counted as holding' % (side, ', '.join(gp['edges_not_read'])))
        for r in gp['edges']:
            if r['after'] is not None and not r['after']['holds']:
                listed.append('the %s\'s %s: a straight edge is left by the ghost proof (step median %.2f, worst %.2f; '
                              'line median %.2f, worst %.2f L*; worst bin at %.2f mm)' % (
                                  side, r['edge'], r['after']['step_median_L'], r['after']['step_max_L'],
                                  r['after']['line_median_L'], r['after']['line_max_L'], r['after']['worst_bin_at_mm']))
        if not gp['edges_failing_on_the_control']:
            listed.append('the %s\'s ghost proof: the plate before the rebuild fails it on no edge (the control does '
                          'not show its power there)' % side)
        if rec['ghost']['pixels_changed_off_the_ground']:
            listed.append('the %s\'s rebuild changed %d pixels off the ground' % (
                side, rec['ghost']['pixels_changed_off_the_ground']))
    record = {'schema': 'day12_balm_master/1', 'surface': SURFACE,
              'pick': {'sketch': pick, 'folder': lm.rel(folder), 'why': why, 'the_pick_flag': pick_flag,
                       'front_third_passes_as_sketched': bool(crop['front_third']['passes']),
                       'hero_scaled': scaled, 'qualifies': bool(crop['qualifies']), 'checkpoint': checkpoint_rec},
              'rule': 'D-D12-3 by the lipstick\'s path: the master by the preservation path from the pick; the body keeps '
                      'the hero بلسم, the logotype and "LIP BALM" as sketched; the cap the stones and the logo; the net '
                      'content on the bottom label Ø 16 (two rows, figures 2 mm, the ℮ exactly 3 mm, the lid\'s sign); the '
                      'product drawing (D-D12-1.4)',
              'facts': {'case_d_mm': CASE_D_MM, 'body_wrap_mm': list(BODY_MM), 'cap_wrap_mm': list(CAP_MM),
                        'overlap_mm': round(OVERLAP_MM, 4), 'bleed_tb_mm': BLEED_TB_MM, 'safe_tb_mm': SAFE_TB_MM,
                        'label_d_mm': LABEL_D_MM, 'provisional': 'D-D11-8 ⟪PROVISIONAL⟫'},
              'allowed_differences': allowed, 'listed': listed,
              'body': body, 'cap': cap, 'label': label, 'a4': a4, 'plates': plates,
              'finish_sheet': lm.rel(out / 'finish-sheet.png'), 'drawing': drawing, 'cost_usd': 0.0}
    lm.write_json(out / 'balm.json', record)
    return record


#: [after the gate] what the gate's rounds named and how each was answered (D-D12-8: one repair, then the look)
GATE_ANSWERS = [
    'round 0, the ghost of the removed guide box (major): repair 1 — the plain ground rebuilt along the cleaned guide '
    'lines and word boxes (its tone held at the untouched ground\'s just outside, its grain from that ground\'s own '
    'patches), proved by prove_ghost against the uncleaned sketch\'s own ground; round 1 holds',
    'round 0, the ℮ "lifted off the baseline" and "a serif e" (two majors): contradicted by the measured file — the '
    'lid\'s own sign (shape error 3e-16), its ink exactly 3.000 mm, its foot on the figures\' baseline — kept by the '
    'owner\'s rule and not changed; round 1 names no defect on it',
]


def gate_record(out_dir=OUT):
    """The balm master's eye gate (D-D12-3: the master, its eye gate; repair ≤ 1) merged into balm.json: each round
    as its record says it, the repairs spent, and how each named defect was answered."""
    out = Path(out_dir)
    rec = json.loads((out / 'balm.json').read_text(encoding='utf-8'))
    rounds = []
    for label in ('r0', 'r1'):
        path = out / ('eye-%s.json' % label)
        if path.exists():
            e = json.loads(path.read_text(encoding='utf-8'))
            rounds.append({'round': label, 'holds': e['holds'], 'defects': e['defects'], 'cost_usd': e['look']['cost_usd'],
                           'record': lm.rel(path)})
    rec['gate'] = {'rule': 'D-D12-3: the master\'s eye gate; one repair (D-D12-8)', 'rounds': rounds,
                   'holds': bool(rounds and rounds[-1]['holds']), 'repairs': max(len(rounds) - 1, 0),
                   'answers': GATE_ANSWERS}
    lm.write_json(out / 'balm.json', rec)
    return rec
