"""Day 11 — Golden Hour closed as test one: its five fixes on its own files (D-D11-5), at $0.

Golden Hour is the owner's Day 10 pick, A-2.3 (``lid_master.PICK``). Its Day 10 files stay on disk untouched (D-D11-1:
nothing of Day 10 is deleted or overwritten); every file regenerated here goes under ``docs/audit/day-11/golden-hour/``
(``lid/``, ``sticker/``, ``tray/``, ``box/``). The fixes:

1. **Emboss the bars** — an owner override of D-D10-2.5, recorded in D-D11-5.1: the relief mask is the five bars' 50 %
   isoline region with a 0.3 mm minimum feature; the oval's glow is not embossed (``relief_mask``). Each bar is read
   station by station along its own axis: the across profile of L*, averaged over one engraving pitch (so the engraving
   does not split it); its level the bar's own (its core), its ground the glow between the bars (the trough); the bar
   is where the profile stands at or above halfway between them, walked out from its core. The mask is opened and
   closed so no part or gap under 0.3 mm remains, traced as vector rings (potrace, as the name is traced) and put on an
   EMBOSS plate (``lid_master.relief_carrier``) that the finish proof and the finish sheet read. It is measured on the
   emitted file's plate (``relief_limits``), against the 50 % isoline (``within_isoline``) and against the glow
   (``glow_probe``); a 1 : 1 crop of its edge drawn over the bars is written for the designer's eye (the lead pays).
2. **The tray's teal** — the code only (``palette_open``): the prompt states the colour story row by row with three
   teal pans or more in row 3, the picture under ``day-11/golden-hour/tray/``, and the pan rule (ΔE00 ≥ 10 from the case
   or lightened by the least L* step, listed). The lead pays for the picture.
3. **The sticker's lines** — D-D11-6, verbatim (``palette_sticker.corrected_copy``, shared with the Ẓilāl sticker).
4. **One Latin face** for the three small lines — the closest pooled over all three (``one_face``), D-D8-5's near-tie
   rule standing, listed; the lines refitted in it with their overlay proofs (1 mm, 3 %).
5. **The super-resolution attempt** — skipped (last in the cut order).
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates, maximum_filter1d, median_filter, uniform_filter1d

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services.round_files_faces import srgb_to_lab

GH = lm.REPO / 'docs' / 'audit' / 'day-11' / 'golden-hour'
LID = GH / 'lid'
STICKER = GH / 'sticker'
TRAY = GH / 'tray'
BOX = GH / 'box'
DAY10 = lm.REPO / 'docs' / 'audit' / 'day-10'
SCHEMA = 'day11_golden_hour_lid/1'
SUBJECT = 'Day 11 (D-D11-5): Golden Hour, test one: the master of A-2.3 with the bars embossed and one Latin face'

# --- 1. the relief mask -------------------------------------------------------------------------------------------------

RELIEF_MIN_MM = 0.3                 # D-D11-5.1 and the press limits (§8): relief 0.3 mm minimum feature, and gap
RELIEF_CONSTRUCT_MM = 0.33          # the mask is opened and closed at 0.33 mm: the limit plus about two trace pixels, so
                                    # the traced outline (potrace smooths by under a pixel) still holds 0.3 mm in the file
RELIEF_SCALE = 8                    # the mask is built on 8× the pick (64.7 px/mm), the grid the name is traced on
RELIEF_STEP_PX = 0.25               # the across profile sampled every quarter pick px (bar_edges' operator)
RELIEF_STATION_PX = 0.25            # a station every quarter pick px along the bar's axis
RELIEF_ALONG_MM = 0.5               # each profile averaged ± 0.5 mm along the bar's own axis: the plaster's grain thinned;
                                    # the long edges lie along the axis, so averaging along it does not move them
RELIEF_SMOOTH_MM = 1.0              # a station's level and grounds: running medians over ± 1 mm of the axis
RELIEF_REACH = 0.75                 # a profile reads out to 3/4 of the way to the next bar's centre
RELIEF_TROUGH = (0.25, 0.75)        # the glow between two bars: the least L* between 1/4 and 3/4 of the way to the next
RELIEF_OUTER_CAP_MM = 0.25          # an outer side (bar 1's top, bar 5's foot): the walk stops 0.25 mm past the bar's
                                    # own edge line where the halo beyond stands as bright as halfway
RELIEF_MIDDLE_MM = 10.0             # a bar's full contrast: its median over the middle ± 10 mm of its axis
RELIEF_END_SHARE = 0.5              # a station is in its bar while its contrast stands at half the full one or more …
RELIEF_STRIPE_CORE = 0.35           # … or its engraving does [repair 1, the eye's round 0: bar 5's stripes ran 5–7 mm past
                                    # its contrast's half]: the fine stripes read across the bar's core (± 0.35 of its
RELIEF_STRIPE_TREND_PX = 1.0        # width), the profile less its own trend (Gaussian σ 1 pick px), its RMS a running
                                    # median over ± 1 mm of the axis, against its median over the middle ± 10 mm
RELIEF_ENDS_BY_ENGRAVING = False    # repair 1's rule is NOT the files' rule: its look (relief-eye-repair1.json) found bar
                                    # 5's end mended but a new defect at bar 2's left end (a tab taking in glow; the
                                    # isoline check failed there too) and D-D11-10 allows no second repair, so the files
                                    # of record are built by round 0's rule (every measured check holds; the eye's round 0
                                    # defect stands: bar 5 short); the repaired build is kept under lid/repair1/
RELIEF_ROUNDS = 4                   # open–close rounds at most (the mask is taken when a round changes nothing)
RELIEF_WALK_SMOOTH_MM = 1.0         # each walked edge a running median over ± 1 mm of the axis
RELIEF_EDGE_NEAR_MM = 1.0           # the glow probe's own edges: each station's steepest rise or fall within ± 1 mm of
RELIEF_EDGE_SMOOTH_MM = 5.0         # the bar's mean edge, a running median over ± 5 mm of the axis (the bar's own line)
RELIEF_EDGE_DEGREE = 2              # … then a parabola fitted over the bar's run: the bars bow a little with the oval
RELIEF_LIMITS_DPI = 2000.0          # the emitted plate read at the foil limits' own dpi
WITHIN_TOL_MM = 0.2                 # a mask pixel outside the isoline lies within 0.2 mm of it: the closing's 0.165 mm
                                    # radius (it fills only gaps under the limit) plus the trace's smoothing
GLOW_TROUGH_MM = 0.5                # the glow probe: the gap between two bars from 0.5 mm inside each one's edge line …
GLOW_HALO_MM = 0.5                  # … the halo from 0.5 mm beyond an outer bar's edge line …
GLOW_END_MM = 1.0                   # … and each bar's own axis from 1 mm beyond the station its contrast fell to half
GLOW_AA_PX = 1                      # the probe's edge given one grid pixel of anti-aliasing (0.015 mm)
CONTROL_L = 70.0                    # the control: a plain L* ≥ 70 mask (the halo inside it) must fail the glow probe
REACH_CONTROL_MM = 0.5              # the reach check's control: the mask eroded by 0.5 mm must fail it


def _frame(lightness):
    """The bars' frame: the unit normal across them (the picture's structure tensor over the oval) and the tangent along
    them (pointing right), the centres' positions along the normal and their spacings (pick px)."""
    n = lm.structure_normal(lightness, lm.OVAL_BOX)
    t = np.array([n[1], -n[0]])
    if t[0] < 0:
        t = -t
    centres = np.asarray(lm.BAR_CENTRES, dtype=np.float64)
    along = (centres - centres[0]) @ n
    return np.asarray(n, dtype=np.float64), t, centres, np.diff(along)


def _profiles(lightness, centre, us, vs, t, n):
    """Across profiles of L* (rows: stations ``us`` along the axis; columns: ``vs`` across), each the mean over ± 0.5 mm
    along the axis (whole pick px) and then a box over one engraving pitch across."""
    reach = int(np.floor(RELIEF_ALONG_MM * lm.PX_PER_MM_SRC))
    xs = centre[0] + us[:, None] * t[0] + vs[None, :] * n[0]
    ys = centre[1] + us[:, None] * t[1] + vs[None, :] * n[1]
    total = np.zeros(xs.shape, dtype=np.float64)
    for off in range(-reach, reach + 1):
        total += map_coordinates(lightness, [ys + off * t[1], xs + off * t[0]], order=1, mode='nearest')
    box = int(round(lm.ENGRAVING_PITCH_PX / RELIEF_STEP_PX))
    return uniform_filter1d(total / (2 * reach + 1), box, axis=1, mode='nearest')


def _crossing(profile, start, step, threshold):
    """Walking from sample ``start`` by ``step`` (± 1), the fractional index where ``profile`` first falls below
    ``threshold`` (linear between samples); the profile's end when it never does."""
    i = start
    last = len(profile) - 1
    while 0 <= i + step <= last:
        j = i + step
        if profile[j] < threshold:
            a, b = profile[i], profile[j]
            return i + step * (a - threshold) / (a - b)
        i = j
    return float(i)


def _longest_run(flags):
    """The longest run of consecutive True: (start, stop) indices, stop exclusive; (0, 0) when there is none."""
    best = (0, 0)
    start = None
    for i, f in enumerate(list(flags) + [False]):
        if f and start is None:
            start = i
        if not f and start is not None:
            if i - start > best[1] - best[0]:
                best = (start, i)
            start = None
    return best


def read_bars(pick):
    """Each bar read along its own axis (D-D11-5.1): its mean profile's edges (the steepest rise and fall: its centre
    line and width), then at every station its level (the core: the profile's mean over the middle half of the bar),
    its grounds (each side's: the glow between the bars — the trough — or, on an outer side, the halo just beyond the
    bar's mean edge), each a running median over ± 1 mm of the axis; its contrast over the glow; the run of stations
    where that contrast stands at half the bar's full one or more (the bar's ends, by the same 50 % rule); and its two
    edges, walked out from the core to where the profile first falls below halfway between the level and that side's
    ground. Returns the frame and one record per bar with its arrays (stations, edges, thresholds, profiles)."""
    lightness = srgb_to_lab(pick)[..., 0].astype(np.float32)
    n, t, centres, spacing = _frame(lightness)
    x0, y0, x1, y1 = lm.OVAL_BOX
    smooth = int(round(RELIEF_SMOOTH_MM * lm.PX_PER_MM_SRC / RELIEF_STATION_PX)) * 2 + 1
    bars = []
    for k, centre in enumerate(centres):
        sides = {-1: None, 1: None}
        if k > 0:
            sides[-1] = float(spacing[k - 1])
        if k < len(centres) - 1:
            sides[1] = float(spacing[k])
        known = [v for v in sides.values() if v is not None]
        reach = RELIEF_REACH * max(known)
        vs = np.arange(-reach, reach + 1e-9, RELIEF_STEP_PX)
        us = np.arange(-500.0, 500.0, RELIEF_STATION_PX)
        px, py = centre[0] + us * t[0], centre[1] + us * t[1]
        us = us[(px >= x0) & (px < x1) & (py >= y0) & (py < y1)]
        prof = _profiles(lightness, centre, us, vs, t, n)
        middle = np.abs(us) <= RELIEF_MIDDLE_MM * lm.PX_PER_MM_SRC
        mean = prof[middle].mean(axis=0)
        grad = np.gradient(mean)
        half = 0.5 * min(known)
        lo_win = (vs < 0) & (vs > -half)
        hi_win = (vs > 0) & (vs < half)
        edge_lo = float(vs[lo_win][int(np.argmax(grad[lo_win]))])
        edge_hi = float(vs[hi_win][int(np.argmin(grad[hi_win]))])
        mid_v = (edge_lo + edge_hi) / 2
        width = edge_hi - edge_lo
        core = np.abs(vs - mid_v) <= width / 4
        level = prof[:, core].mean(axis=1)
        grounds = {}
        ground_how = {}
        for side, gap in sides.items():
            if gap is not None:
                lo, hi = RELIEF_TROUGH
                window = (side * (vs - mid_v) >= lo * gap) & (side * (vs - mid_v) <= hi * gap)
                grounds[side] = prof[:, window].min(axis=1)
                ground_how[side] = 'the glow between the bars: the least L* from 1/4 to 3/4 of the way to the next bar'
        level = median_filter(level, size=smooth, mode='nearest')
        for side in grounds:
            grounds[side] = median_filter(grounds[side], size=smooth, mode='nearest')
        inner = [grounds[s] for s, gap in sides.items() if gap is not None]
        contrast = level - np.mean(inner, axis=0)
        full = float(np.median(contrast[middle]))
        contrast_run = _longest_run(contrast >= RELIEF_END_SHARE * full)
        stripes, stripe_pitch = stripe_strength(prof, vs, mid_v, width, middle, smooth)
        full_stripes = float(np.median(stripes[middle]))
        stripe_run = _longest_run(stripes >= RELIEF_END_SHARE * full_stripes)
        # [repair 1] ONE end rule for all five bars: a station is in its bar while its contrast OR its engraving stands
        # at half its full one or more — the bar ends where both have fallen under half
        start, stop = contrast_run
        if RELIEF_ENDS_BY_ENGRAVING:
            start, stop = _longest_run((contrast >= RELIEF_END_SHARE * full)
                                       | (stripes >= RELIEF_END_SHARE * full_stripes))
        # the bar's edges by another operator, for the glow probe (never the mask): each station's steepest rise and fall
        # near the mean edges, a running median over ± 5 mm of the axis — the bar's own line where it leans off the mean
        g = np.gradient(prof, axis=1)
        near = int(round(RELIEF_EDGE_NEAR_MM * lm.PX_PER_MM_SRC / RELIEF_STEP_PX))
        i_lo, i_hi = int(np.argmin(np.abs(vs - edge_lo))), int(np.argmin(np.abs(vs - edge_hi)))
        grad_lo = vs[i_lo - near + np.argmax(g[:, i_lo - near:i_lo + near + 1], axis=1)]
        grad_hi = vs[i_hi - near + np.argmin(g[:, i_hi - near:i_hi + near + 1], axis=1)]
        wide = int(round(RELIEF_EDGE_SMOOTH_MM * lm.PX_PER_MM_SRC / RELIEF_STATION_PX)) * 2 + 1
        grad_lo = median_filter(grad_lo, size=wide, mode='nearest')
        grad_hi = median_filter(grad_hi, size=wide, mode='nearest')
        c0, c1 = contrast_run
        if c1 - c0 > wide:
            # the long edges are gentle arcs (the bars bow a little with the oval): each a parabola fitted over the run
            # where the bar's contrast stands (repair 1: never over the fading ends the engraving adds)
            grad_lo = np.polyval(np.polyfit(us[c0:c1], grad_lo[c0:c1], RELIEF_EDGE_DEGREE), us)
            grad_hi = np.polyval(np.polyfit(us[c0:c1], grad_hi[c0:c1], RELIEF_EDGE_DEGREE), us)
        # an outer side (bar 1's top, bar 5's foot) has no glow between bars beside it: its ground the glow between the
        # bars on the inner side (the rule's own ground); the halo beyond it stands as bright as halfway in places, so
        # there the walk is stopped at the bar's own edge line (its steepest fall) and RELIEF_OUTER_CAP_MM beyond
        bound = {}
        for side, gap in sides.items():
            if gap is None:
                grounds[side] = np.mean(inner, axis=0)
                line = grad_hi
                if side < 0:
                    line = grad_lo
                bound[side] = line + side * RELIEF_OUTER_CAP_MM * lm.PX_PER_MM_SRC
                ground_how[side] = ('no glow between bars on this side: the glow between the bars on the inner side, '
                                    'the walk stopped at the bar\'s own edge line (its steepest fall, a parabola over '
                                    'the run) and %.2f mm beyond, where the halo stands as bright as halfway'
                                    % RELIEF_OUTER_CAP_MM)
        lo_edge = np.full(len(us), np.nan)
        hi_edge = np.full(len(us), np.nan)
        thr = {side: (level + grounds[side]) / 2 for side in grounds}
        core_idx = np.flatnonzero(core)
        capped = 0
        capped_at = {side: np.zeros(len(us), dtype=bool) for side in bound}     # the stations stopped at the line
        extended = 0
        for i in range(start, stop):
            c = int(core_idx[int(np.argmax(prof[i, core_idx]))])
            lo_edge[i] = vs[0] + _crossing(prof[i], c, -1, thr[-1][i]) * RELIEF_STEP_PX
            hi_edge[i] = vs[0] + _crossing(prof[i], c, 1, thr[1][i]) * RELIEF_STEP_PX
            if -1 in bound and lo_edge[i] < bound[-1][i]:
                lo_edge[i] = bound[-1][i]
                capped_at[-1][i] = True
                capped += 1
            if 1 in bound and hi_edge[i] > bound[1][i]:
                hi_edge[i] = bound[1][i]
                capped_at[1][i] = True
                capped += 1
            if i < c0 or i >= c1:
                # [repair 1] where only the engraving carries the bar (its contrast under half), the walk at that low
                # contrast is held within the bar's own edge lines: it never spreads into the glow beside the end
                lo_edge[i] = max(lo_edge[i], grad_lo[i])
                hi_edge[i] = min(hi_edge[i], grad_hi[i])
                extended += 1
        # each walked edge a running median over ± 1 mm of the axis: a crossing a grain of plaster moved is put back on
        # its neighbours' line (the bars' long edges run smooth; the within-isoline proof measures what it moves)
        if stop > start:
            walk = int(round(RELIEF_WALK_SMOOTH_MM * lm.PX_PER_MM_SRC / RELIEF_STATION_PX)) * 2 + 1
            lo_edge[start:stop] = median_filter(lo_edge[start:stop], size=walk, mode='nearest')
            hi_edge[start:stop] = median_filter(hi_edge[start:stop], size=walk, mode='nearest')
        bars.append({'k': k, 'centre_px': centre, 'us': us, 'vs': vs, 'profiles': prof, 'level': level,
                     'grounds': grounds, 'thresholds': thr, 'contrast': contrast, 'full_contrast': full,
                     'run': (start, stop), 'lo': lo_edge, 'hi': hi_edge, 'mid_v': mid_v, 'width_px': width,
                     'mean_edges_px': (edge_lo, edge_hi), 'grad_edges_px': (grad_lo, grad_hi), 'sides': sides,
                     'ground_how': ground_how, 'outer_stations_stopped_at_the_edge_line': capped,
                     'capped': capped_at, 'contrast_run': contrast_run, 'stripe_run': stripe_run,
                     'stations_carried_by_the_engraving': extended,
                     'stripes': stripes, 'full_stripes': full_stripes, 'stripe_pitch_px': stripe_pitch})
    return {'normal': n, 'tangent': t, 'spacing_px': spacing, 'bars': bars}


def stripe_strength(prof, vs, mid_v, width, middle, smooth):
    """A bar's engraving along its axis [repair 1]: at each station the RMS of its across-profile less the profile's own
    trend (Gaussian σ 1 pick px) over the bar's core (± 0.35 of its width about its centre line) — the fine stripes the
    bar is engraved with — a running median over ± 1 mm of the axis; and the stripes' pitch (pick px), the strongest
    frequency of the middle's mean spectrum (a record of what is read, not a threshold)."""
    from scipy.ndimage import gaussian_filter1d
    core = np.abs(vs - mid_v) <= RELIEF_STRIPE_CORE * width
    sub = prof[:, core]
    fine = sub - gaussian_filter1d(sub, RELIEF_STRIPE_TREND_PX / RELIEF_STEP_PX, axis=1)
    rms = median_filter(fine.std(axis=1), size=smooth, mode='nearest')
    spectrum = np.abs(np.fft.rfft(fine[middle] - fine[middle].mean(axis=1, keepdims=True), axis=1)).mean(axis=0)
    freqs = np.fft.rfftfreq(fine.shape[1], d=RELIEF_STEP_PX)
    peak = int(np.argmax(spectrum[1:])) + 1
    return rms, float(1.0 / freqs[peak])


def _grid():
    """The 8× grid over the oval's box: its shape and each pixel's centre in pick px (pixel-centre coordinates)."""
    x0, y0, x1, y1 = lm.OVAL_BOX
    s = RELIEF_SCALE
    return ((y1 - y0) * s, (x1 - x0) * s), (x0 + (np.arange((x1 - x0) * s) + 0.5) / s - 0.5,
                                           y0 + (np.arange((y1 - y0) * s) + 0.5) / s - 0.5)


def _bar_window(bar, frame):
    """A bar's reach on the 8× grid (its stations' span along the axis by its profiles' span across): the grid's row and
    column slices that hold it, and its own coordinates there (u along its axis, v across, pick px from its centre)."""
    shape, (gx, gy) = _grid()
    n, t = frame['normal'], frame['tangent']
    cx, cy = bar['centre_px']
    corners = [np.array([cx, cy]) + u * t + v * n for u in (bar['us'][0], bar['us'][-1]) for v in (bar['vs'][0], bar['vs'][-1])]
    xs, ys = [p[0] for p in corners], [p[1] for p in corners]
    x0, y0, _, _ = lm.OVAL_BOX
    s = RELIEF_SCALE
    c0 = int(np.clip(np.floor((min(xs) - x0) * s), 0, shape[1]))
    c1 = int(np.clip(np.ceil((max(xs) - x0 + 1) * s), 0, shape[1]))
    r0 = int(np.clip(np.floor((min(ys) - y0) * s), 0, shape[0]))
    r1 = int(np.clip(np.ceil((max(ys) - y0 + 1) * s), 0, shape[0]))
    dx = (gx[c0:c1] - cx).astype(np.float32)[None, :]
    dy = (gy[r0:r1] - cy).astype(np.float32)[:, None]
    return (slice(r0, r1), slice(c0, c1)), dx * np.float32(t[0]) + dy * np.float32(t[1]), \
        dx * np.float32(n[0]) + dy * np.float32(n[1])


def isoline_raster(frame):
    """Two rasters on the 8× grid: the walked bars (each station's run between its two edges, the bar's 50 % isoline
    as walked from its core) and the isoline region itself (every pixel of a bar's stations, within its reach, whose
    profile stands at or above its side's threshold — the walk's superset, where a bright halo beyond a dip counts)."""
    shape, _ = _grid()
    walked = np.zeros(shape, dtype=bool)
    region = np.zeros(shape, dtype=bool)
    for bar in frame['bars']:
        start, stop = bar['run']
        if stop <= start:
            continue
        win, u, v = _bar_window(bar, frame)
        us, vs = bar['us'], bar['vs']
        lo = np.interp(u, us, bar['lo'], left=np.nan, right=np.nan)
        hi = np.interp(u, us, bar['hi'], left=np.nan, right=np.nan)
        walked[win] |= (v >= lo) & (v <= hi)
        si = (u - us[0]) / RELIEF_STATION_PX
        vi = (v - vs[0]) / RELIEF_STEP_PX
        inside = (si >= start) & (si <= stop - 1) & (vi >= 0) & (vi <= len(vs) - 1)
        value = map_coordinates(bar['profiles'], [np.clip(si, 0, len(us) - 1), np.clip(vi, 0, len(vs) - 1)], order=1)
        station = np.clip(np.round(si).astype(int), 0, len(us) - 1)
        thr = np.where(v < bar['mid_v'], bar['thresholds'][-1][station], bar['thresholds'][1][station])
        region[win] |= inside & (value >= thr)
    return walked, region


def _opened(mask, radius_px):
    from apps.pipeline.services import finish_proof
    return finish_proof._opened(mask, radius_px)


def open_close(mask, diameter_mm):
    """The mask opened and closed by an exact Euclidean disk of ``diameter_mm`` until a round changes nothing (at most
    four rounds): no part narrower than the disk, no gap narrower than it. Returns the mask and the rounds taken."""
    r = diameter_mm * lm.PX_PER_MM_SRC * RELIEF_SCALE / 2
    for rounds in range(1, RELIEF_ROUNDS + 1):
        after = ~_opened(~_opened(mask, r), r)
        if np.array_equal(after, mask):
            return after, rounds
        mask = after
    return mask, RELIEF_ROUNDS


def _core_pixels(frame):
    """Each bar's core at the middle of its run, as a grid pixel (row, col)."""
    x0, y0, _, _ = lm.OVAL_BOX
    n, t = frame['normal'], frame['tangent']
    out = []
    for bar in frame['bars']:
        start, stop = bar['run']
        i = (start + stop) // 2
        p = bar['centre_px'] + bar['us'][i] * t + bar['mid_v'] * n
        out.append((int(round((p[1] - y0 + 0.5) * RELIEF_SCALE - 0.5)), int(round((p[0] - x0 + 0.5) * RELIEF_SCALE - 0.5))))
    return out


def keep_the_bars(mask, frame):
    """Of the opened and closed mask, the five components that hold a bar's core; every other component dropped and
    counted (a speck of plaster above the threshold beyond a bar's end is not a bar)."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    keep = set()
    for r, c in _core_pixels(frame):
        if labels[r, c] == 0:
            raise ValueError('a bar\'s core at grid pixel (%d, %d) is outside the mask' % (r, c))
        keep.add(int(labels[r, c]))
    if len(keep) != len(frame['bars']):
        raise ValueError('the five bars read as %d components' % len(keep))
    dropped = [k for k in range(1, count) if k not in keep]
    mm2 = (lm.PX_PER_MM_SRC * RELIEF_SCALE) ** 2
    return np.isin(labels, sorted(keep)), {'components_dropped': len(dropped),
                                           'area_dropped_mm2': round(float(sum(stats[k, 4] for k in dropped)) / mm2, 3)}


def rings_to_mm(rings_px):
    """potrace's rings on the 8× grid (pixel corners) → lid mm."""
    x0, y0, _, _ = lm.OVAL_BOX
    s = RELIEF_SCALE
    return lm.map_rings(rings_px, lambda p: ((x0 + p[0] / s) / lm.PX_PER_MM_SRC, (y0 + p[1] / s) / lm.PX_PER_MM_SRC))


def rings_raster(rings_mm):
    """Vector rings (mm) back on the 8× grid over the oval's box."""
    x0, y0, _, _ = lm.OVAL_BOX
    shape, _ = _grid()
    return lm.raster_fill(lm.rings_area(rings_mm, 24), shape, (x0 / lm.PX_PER_MM_SRC, y0 / lm.PX_PER_MM_SRC),
                          lm.PX_PER_MM_SRC * RELIEF_SCALE)


def within_isoline(mask, region):
    """D-D11-5.1's "within the bars' 50 % isoline", measured: the mask's share outside the isoline region and how far
    outside it reaches (mm); it holds within WITHIN_TOL_MM (the closing fills gaps under the limit; potrace smooths by
    under a pixel)."""
    outside = mask & ~region
    dist = cv2.distanceTransform((~region).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    px_per_mm = lm.PX_PER_MM_SRC * RELIEF_SCALE
    reach = 0.0
    if outside.any():
        reach = float(dist[outside].max()) / px_per_mm
    return {'mask_mm2': round(float(mask.sum()) / px_per_mm ** 2, 2),
            'outside_mm2': round(float(outside.sum()) / px_per_mm ** 2, 3),
            'outside_share': round(float(outside.sum()) / float(mask.sum()), 5),
            'reaches_outside_mm': round(reach, 4), 'tolerance_mm': WITHIN_TOL_MM,
            'holds': bool(reach <= WITHIN_TOL_MM)}


SIDE_NAMES = {-1: 'upper', 1: 'lower'}     # a bar's side by the normal's sign: bar 1's top is its upper, bar 5's foot


def reach_raster(frame):
    """The walked isoline the mask must reach (the review of Day 11: ``within_isoline`` and the glow probe only look
    outward, so a mask that falls short of the bars passed both). On the 8× grid: each bar's stations between its two
    walked edges, as ``isoline_raster`` walks them — except on an outer side capped at the bar's own edge line (bar 1's
    top, bar 5's foot), where the edge is that line plus 0.25 mm and not the isoline: at every station the cap reaches
    (a capped station, and those within the walk's ± 1 mm running median of one, which spreads the cap) that side is
    left out from the bar's core line outward, so the reach is never measured against a line the mask was built from.
    Returns the raster and, per capped side, the stations capped and left out."""
    shape, _ = _grid()
    raster = np.zeros(shape, dtype=bool)
    walk = int(round(RELIEF_WALK_SMOOTH_MM * lm.PX_PER_MM_SRC / RELIEF_STATION_PX)) * 2 + 1
    left_out = []
    for bar in frame['bars']:
        start, stop = bar['run']
        if stop <= start:
            continue
        lo, hi = bar['lo'].copy(), bar['hi'].copy()
        for side, flags in bar['capped'].items():
            spread = maximum_filter1d(flags.astype(np.uint8), size=walk, mode='constant') > 0
            if side < 0:
                lo[spread] = bar['mid_v']
            else:
                hi[spread] = bar['mid_v']
            left_out.append({'bar': bar['k'] + 1, 'side': SIDE_NAMES[side], 'stations': int(stop - start),
                             'stations_capped': int(flags.sum()), 'stations_left_out': int(spread[start:stop].sum())})
        win, u, v = _bar_window(bar, frame)
        us = bar['us']
        lo_i = np.interp(u, us, lo, left=np.nan, right=np.nan)
        hi_i = np.interp(u, us, hi, left=np.nan, right=np.nan)
        raster[win] |= (v >= lo_i) & (v <= hi_i)
    return raster, left_out


def _erode(mask, radius_mm):
    """The mask eroded by an exact Euclidean disk of ``radius_mm`` (on the 8× grid; outside the grid counts as
    outside the mask)."""
    padded = cv2.copyMakeBorder(mask.astype(np.uint8), 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    dist = cv2.distanceTransform(padded, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)[1:-1, 1:-1]
    return dist > radius_mm * lm.PX_PER_MM_SRC * RELIEF_SCALE


def reach_check(mask, reach):
    """The mask reaches the bars: the walked isoline (``reach_raster``, the capped outer sides left out) eroded by
    WITHIN_TOL_MM — the same tolerance the outward check grants, the closing's and the trace's — lies inside the mask.
    Measured: the eroded isoline's area outside the mask and how far the mask falls short (the farthest such pixel's
    distance to the mask, mm); it holds at none."""
    px_per_mm = lm.PX_PER_MM_SRC * RELIEF_SCALE
    inner = _erode(reach, WITHIN_TOL_MM)
    short = inner & ~mask
    by = 0.0
    if short.any():
        padded = cv2.copyMakeBorder((~mask).astype(np.uint8), 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=1)
        dist = cv2.distanceTransform(padded, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)[1:-1, 1:-1]
        by = float(dist[short].max()) / px_per_mm
    return {'walked_mm2': round(float(reach.sum()) / px_per_mm ** 2, 2),
            'eroded_mm2': round(float(inner.sum()) / px_per_mm ** 2, 2), 'eroded_by_mm': WITHIN_TOL_MM,
            'short_mm2': round(float(short.sum()) / px_per_mm ** 2, 4),
            'falls_short_by_mm': round(by, 4), 'holds': bool(not short.any())}


def glow_probe(frame):
    """The oval's glow, defined without the mask (from the bars' own edge lines — each station's steepest rise and fall,
    a running median over ± 5 mm — never from the 50 % walk): the glow between each two bars (from 0.5 mm past one bar's
    edge to 0.5 mm short of the next one's, where the first bar stands), the halo from 0.5 mm beyond an outer bar's edge
    to the reach, and each bar's own band from 1 mm beyond the stations where its contrast fell under half (its fading
    ends). A raster on the 8× grid."""
    shape, _ = _grid()
    glow = np.zeros(shape, dtype=bool)
    k = lm.PX_PER_MM_SRC
    bars = frame['bars']
    t = frame['tangent']
    for bar in bars:
        win, u, v = _bar_window(bar, frame)
        us, vs = bar['us'], bar['vs']
        start, stop = bar['run']
        on_axis = (u >= us[0]) & (u <= us[-1])
        in_run = (u >= us[start]) & (u <= us[stop - 1])
        lo_line = np.interp(u, us, bar['grad_edges_px'][0])
        hi_line = np.interp(u, us, bar['grad_edges_px'][1])
        for side, gap in bar['sides'].items():
            if gap is not None and side > 0:
                # the next bar's upper edge in this bar's frame: its centre lies ``gap`` on along the normal and
                # ``shift`` along the axis
                nxt = bars[bar['k'] + 1]
                shift = float((nxt['centre_px'] - bar['centre_px']) @ t)
                far = gap + np.interp(u - shift, nxt['us'], nxt['grad_edges_px'][0]) - GLOW_TROUGH_MM * k
                glow[win] |= in_run & (v >= hi_line + GLOW_TROUGH_MM * k) & (v <= far)
            if gap is None:
                edge, far = hi_line, vs[-1]
                if side < 0:
                    edge, far = lo_line, vs[0]
                d = side * (v - edge)
                glow[win] |= on_axis & (d >= GLOW_HALO_MM * k) & (side * (v - far) <= 0)
        band = np.abs(v - bar['mid_v']) <= bar['width_px'] / 2
        beyond = (u < us[start] - GLOW_END_MM * k) | (u > us[stop - 1] + GLOW_END_MM * k)
        glow[win] |= on_axis & band & beyond
    return glow


def glow_check(mask, glow):
    """The glow outside the mask: the mask's pixels on the glow probe (its edge given the raster's own anti-aliasing,
    one grid pixel, 0.015 mm — as the foil limits allow theirs), as an area; holds at none."""
    px_per_mm = lm.PX_PER_MM_SRC * RELIEF_SCALE
    probe = cv2.erode(glow.astype(np.uint8), np.ones((2 * GLOW_AA_PX + 1, 2 * GLOW_AA_PX + 1), np.uint8)).astype(bool)
    hit = mask & probe
    return {'glow_mm2': round(float(glow.sum()) / px_per_mm ** 2, 2),
            'mask_on_glow_mm2': round(float(hit.sum()) / px_per_mm ** 2, 4), 'holds': bool(not hit.any())}


def control_mask(pick):
    """The glow probe's control: the oval read by L* alone (smoothed over one pitch), L* ≥ 70 — the halo inside it."""
    lightness = srgb_to_lab(pick)[..., 0].astype(np.float32)
    x0, y0, x1, y1 = lm.OVAL_BOX
    crop = cv2.blur(lightness, (3, 3))[y0:y1, x0:x1] >= CONTROL_L
    shape, _ = _grid()
    return cv2.resize(crop.astype(np.uint8), (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)


def relief_limits(ai_path):
    """The relief plate as the file carries it, against the 0.3 mm limit (§8: relief ≥ 0.3 mm; D-D11-5.1): every
    EMBOSS or DEBOSS plate read at 2000 dpi by the foil limits' own reader (``finish_proof._limits_of``: the parts a
    0.3 mm disk's opening removes, the gaps its closing fills, a part counting when it runs twice the limit — a corner is
    not a part). ``holds`` None when the file carries no relief plate (never a pass on nothing)."""
    from apps.pipeline.services import finish_proof as fp
    px_per_mm = RELIEF_LIMITS_DPI / lm.MM_PER_INCH
    r = (RELIEF_MIN_MM * px_per_mm - fp.AA_TOLERANCE_PX) / 2.0
    run = fp.VIOLATION_RUN * RELIEF_MIN_MM * px_per_mm
    read = fp._read_plates(ai_path)
    rows = []
    try:
        for plate in read.plates:
            if plate.kind not in ('emboss', 'deboss'):
                continue
            rows.append(dict(fp._plate_row(plate), **fp._limits_of(read.doc[plate.page - 1], px_per_mm=px_per_mm,
                                                                   line_r_px=r, gap_r_px=r, line_run_px=run,
                                                                   gap_run_px=run)))
    finally:
        read.doc.close()
    holds = None
    if rows:
        holds = all(row['holds'] for row in rows)
    return {'limit_mm': RELIEF_MIN_MM, 'dpi': RELIEF_LIMITS_DPI, 'disk_mm': round(2 * r / px_per_mm, 4),
            'run_mm': round(run / px_per_mm, 4), 'plates': rows, 'holds': holds,
            'read': 'finish_proof\'s foil-limit reader on the relief plate: parts under 0.3 mm (the opening\'s residue) '
                    'and gaps under 0.3 mm (the closing\'s), each counting when it runs 0.6 mm or more'}


def bars_record(frame):
    """Per bar, what was read (mm): its width, level, full contrast, the run of its stations, and its grounds."""
    k = lm.PX_PER_MM_SRC
    rows = []
    for bar in frame['bars']:
        start, stop = bar['run']
        rows.append({'bar': bar['k'] + 1, 'centre_px': [int(v) for v in bar['centre_px']],
                     'width_mm': round(bar['width_px'] / k, 3),
                     'level_l_median': round(float(np.median(bar['level'][start:stop])), 2),
                     'full_contrast_l': round(bar['full_contrast'], 2),
                     'run_mm': [round(float(bar['us'][start]) / k, 2), round(float(bar['us'][stop - 1]) / k, 2)],
                     'length_mm': round(float(bar['us'][stop - 1] - bar['us'][start]) / k, 2),
                     'ends_by': {'contrast_run_mm': [round(float(bar['us'][bar['contrast_run'][0]]) / k, 2),
                                                     round(float(bar['us'][bar['contrast_run'][1] - 1]) / k, 2)],
                                 'stripe_run_mm': [round(float(bar['us'][bar['stripe_run'][0]]) / k, 2),
                                                   round(float(bar['us'][bar['stripe_run'][1] - 1]) / k, 2)],
                                 'stripe_pitch_mm': round(bar['stripe_pitch_px'] / k, 3),
                                 'stations_carried_by_the_engraving': bar['stations_carried_by_the_engraving'],
                                 'rule': 'repair 1: the bar runs while its contrast or its engraving stands at half its '
                                         'full one or more'},
                     'grounds': {('upper' if side < 0 else 'lower'): bar['ground_how'][side] for side in bar['ground_how']},
                     'outer_stations_stopped_at_the_edge_line': bar['outer_stations_stopped_at_the_edge_line'],
                     'stations_stopped_by_side': {SIDE_NAMES[side]: int(flags.sum())
                                                  for side, flags in bar['capped'].items()},
                     'stations': int(stop - start)})
    return rows


EDGE_WORDS = {'upper': 'top', 'lower': 'bottom'}     # a capped side as the eye sees it on the lid


def outline_said(bars):
    """The relief's outline in words, from the record (``bars_record``): each bar's 50 % isoline, except on the outer
    sides where the walk was stopped at the bar's own edge line — which bar, which edge, on how many of its stations —
    and that there the outline is that line plus 0.25 mm, not the isoline (the review of Day 11: the eye's prompt and
    the master's facts said "the 50 % isoline" everywhere)."""
    parts = []
    for b in bars:
        for side, n in b['stations_stopped_by_side'].items():
            if n:
                parts.append('bar %d\'s %s edge (%d of its %d stations, %.0f %% of its length)' % (
                    b['bar'], EDGE_WORDS[side], n, b['stations'], 100.0 * n / b['stations']))
    said = ('The emboss outline is each bar\'s 50 % isoline — where the bar stands at or above halfway between its own '
            'brightness and the glow between the bars — with no part or gap under 0.3 mm; each bar runs along its length '
            'while its contrast stands at half its full one or more')
    if RELIEF_ENDS_BY_ENGRAVING:
        said = said.replace('while its contrast stands at half its full one or more',
                            'while its contrast or its engraved stripes stand at half their full strength or more')
    if not parts:
        return said + '.'
    return said + ('; except on %s, the outer edges facing away from the other bars, where the halo beyond the bar '
                   'stands as bright as halfway: there the outline is NOT the isoline but the bar\'s own edge line (its '
                   'steepest fall, a smooth curve fitted along the bar) plus %.2f mm.' % (
                       ' and '.join(parts), RELIEF_OUTER_CAP_MM))


def relief_mask(pick):
    """D-D11-5.1 at $0: the bars read (``read_bars``), the walked isoline rastered on the 8× grid, opened and closed at
    0.33 mm, its five bars kept, traced (potrace, the name's settings) to rings in lid mm, and measured back from the
    rings: within the isoline region, reaching the walked isoline, off the glow. What no instrument here can fail — the
    capped outer edges and the bars' ends, which hold by construction — is recorded as holds None, and the eye's
    verdict (D-D11-5.1's proof) as None until it looks (``merge_relief_eye``). Returns {'rings_mm', 'record', 'said'} —
    what ``lid_master.build`` takes as its ``relief``; the file's own plate is measured after the build
    (``relief_limits``)."""
    frame = read_bars(pick)
    walked, region = isoline_raster(frame)
    cleaned, rounds = open_close(walked, RELIEF_CONSTRUCT_MM)
    bars_only, dropped = keep_the_bars(cleaned, frame)
    rings_mm = rings_to_mm(lm.potrace_rings(bars_only))
    traced = rings_raster(rings_mm)
    glow = glow_probe(frame)
    within = within_isoline(traced, region)
    reach_band, left_out = reach_raster(frame)
    reaches = reach_check(traced, reach_band)
    reach_control = reach_check(_erode(traced, REACH_CONTROL_MM), reach_band)
    off_glow = glow_check(traced, glow)
    control = glow_check(control_mask(pick), glow)
    geom = lm.rings_area(rings_mm, 24)
    bars = bars_record(frame)
    capped_said = '; '.join('bar %d\'s %s edge on %d of %d stations' % (r['bar'], EDGE_WORDS[r['side']],
                                                                          r['stations_capped'], r['stations'])
                            for r in left_out)
    record = {
        'frame': {'normal': [round(float(v), 6) for v in frame['normal']],
                  'tangent': [round(float(v), 6) for v in frame['tangent']]},
        'rule': 'D-D11-5.1 (an owner override of D-D10-2.5): the relief mask is the five bars\' 50 % isoline region, '
                '0.3 mm minimum feature; the oval\'s glow is not embossed',
        'read': 'each bar along its own axis (the structure tensor\'s normal %s), a station every %.2f pick px: the '
                'across profile of L* averaged over one engraving pitch (%.2f px) and over ± %.1f mm along the axis (a '
                'departure from the stated reading, said: it thins the plaster\'s grain and moves no long edge, which '
                'lies along the axis); level the bar\'s core (the middle half of its width), ground the glow between '
                'the bars (each side\'s trough; on the outer sides of bars 1 and 5, where no glow lies between bars, '
                'the inner side\'s, the walk there stopped 0.25 mm past the bar\'s own edge line, its steepest fall, '
                'where the halo stands as bright as halfway), each a running median over ± %.1f mm; the bar where the '
                'profile stands at or above halfway between them, walked out from the core, each walked edge a running '
                'median over ± %.1f mm of the axis (a second departure, said: a crossing one grain of plaster moved is '
                'put back on its neighbours\' line); its ends where its contrast over the glow falls under half its '
                'full one' % ([round(float(v), 4) for v in frame['normal']], RELIEF_STATION_PX, lm.ENGRAVING_PITCH_PX,
                              RELIEF_ALONG_MM, RELIEF_SMOOTH_MM, RELIEF_WALK_SMOOTH_MM),
        'bars': bars,
        'outline_said': outline_said(bars),
        'construction': {'grid_px_per_mm': round(lm.PX_PER_MM_SRC * RELIEF_SCALE, 3),
                         'opened_and_closed_mm': RELIEF_CONSTRUCT_MM, 'rounds': rounds,
                         'components_kept': len(frame['bars']), **dropped,
                         'tracer': 'potrace 1.16, the name\'s settings (alphamax %s, opttolerance %s, turdsize %s)' % (
                             lm.NAME_ALPHAMAX, lm.NAME_OPTTOLERANCE, lm.NAME_TURDSIZE)},
        'rings': len(rings_mm), 'area_mm2': round(float(geom.area), 2),
        'share_of_lid_pct': round(100.0 * float(geom.area) / (lm.LID_MM[0] * lm.LID_MM[1]), 3),
        'bounds_mm': [round(float(v), 3) for v in geom.bounds],
        'within_isoline': within,
        'reach': dict(reaches, left_out=left_out,
                      rule='the mask reaches the bars: the walked isoline eroded by %.1f mm lies inside it; on the '
                           'capped outer sides (and the stations the walk\'s ± %.0f mm median spreads the cap to) the '
                           'side is left out from the core line outward' % (WITHIN_TOL_MM, RELIEF_WALK_SMOOTH_MM)),
        'reach_control': dict(reach_control, mask='the mask eroded by %.1f mm: it must fail' % REACH_CONTROL_MM),
        'glow': off_glow,
        'glow_control': dict(control, mask='L* ≥ %g over the oval (the halo inside it): it must fail' % CONTROL_L),
        'by_construction': {
            'capped_outer_edges': 'not measured — %s: the edge there is the bar\'s own edge line plus %.2f mm, not the '
                                  'isoline; the isoline region there takes in the halo, so within_the_isoline cannot '
                                  'fail there; the reach check leaves those sides out; the glow probe\'s halo starts '
                                  '%.2f mm beyond the edge line, %.2f mm past the mask by construction. Their proof is '
                                  'the eye\'s' % (capped_said, RELIEF_OUTER_CAP_MM, GLOW_HALO_MM,
                                                  GLOW_HALO_MM - RELIEF_OUTER_CAP_MM),
            'bar_ends': 'not measured — the mask stops at the station where a bar\'s contrast falls under half its '
                        'full one (repair 1\'s rule by the engraving is not the files\' rule: see lid/repair1/), the '
                        'walked isoline the reach is checked against stops at the same station, and the '
                        'glow probe starts %.1f mm beyond it: where a bar ends, and an overshoot under that, are not '
                        'measured (a bar cut short by more is refused by the reach). Their proof is the eye\'s'
                        % GLOW_END_MM},
        'eye': {'holds': None, 'state': 'pending',
                'said': 'not looked at: D-D11-5.1\'s proof is the designer\'s eye on the edge crops; the lead pays for '
                        'the look (docs/audit/rescue_runtime/day11/gh_relief_eye_run.py)'},
        'holds': {'within_the_isoline': within['holds'], 'reaches_the_isoline': reaches['holds'],
                  'off_the_glow': off_glow['holds'], 'the_control_fails': not control['holds'],
                  'the_reach_control_fails': not reach_control['holds'],
                  'capped_outer_edges': None, 'bar_ends': None, 'eye': None},
    }
    said = ('the five bars embossed (D-D11-5.1, an owner override of D-D10-2.5): their 50 %% isoline, read along each '
            'bar on L* averaged over one engraving pitch, its level the bar\'s own and its ground the glow between the '
            'bars (on %s, where the halo is as bright as halfway, the bar\'s own edge line plus %.2f mm, not the '
            'isoline); opened and closed at %.2f mm so no part or gap under 0.3 mm remains; %.1f mm² of blind emboss on '
            'the EMBOSS plate, traced as vector rings; the oval\'s glow not embossed (%.4f mm² of the mask on the glow '
            'probe)' % (capped_said, RELIEF_OUTER_CAP_MM, RELIEF_CONSTRUCT_MM, geom.area, off_glow['mask_on_glow_mm2']))
    return {'rings_mm': rings_mm, 'record': record, 'said': said}


# --- 1b. the relief in the files: its edge for the eye, the finish sheet ----------------------------------------------

EDGE_CROP_DPI = 600.0               # D-D11-5.1: a 1 : 1 crop at 600 dpi of the mask's edge drawn over the bars
EDGE_CROP_MM = (34.0, 22.0)         # each piece 34 × 22 mm: two rows of it (the bars, then the bars with the edge)
                                    # stay under the eye's 1.15 MP, so the model sees the crop at its own pixels
EDGE_CROP_GAP_PX = 6
EDGE_OVERVIEW_PX = (1240, 922)      # the whole oval with the edge, for orientation (not 1 : 1), under 1.15 MP


def edge_windows(record):
    """The crops' windows (x0, y0, x1, y1 mm on the lid): the middle bar's middle (both long edges and their glow), the
    top and bottom bars' right ends (an outer edge against the halo, a fading end), and the second and fourth bars'
    left ends — each 34 × 22 mm, kept on the lid."""
    t = np.asarray(record['frame']['tangent'])
    bars = record['bars']
    picks = {'bar-3-middle': (bars[2], 0.0), 'bar-1-right-end': (bars[0], bars[0]['run_mm'][1]),
             'bar-5-right-end': (bars[4], bars[4]['run_mm'][1]), 'bar-2-left-end': (bars[1], bars[1]['run_mm'][0]),
             'bar-4-left-end': (bars[3], bars[3]['run_mm'][0])}
    out = {}
    w, h = EDGE_CROP_MM
    for name, (bar, u_mm) in picks.items():
        cx, cy = (np.asarray(bar['centre_px'], dtype=np.float64) + u_mm * lm.PX_PER_MM_SRC * t) / lm.PX_PER_MM_SRC
        x0 = float(np.clip(cx - w / 2, 0.0, lm.LID_MM[0] - w))
        y0 = float(np.clip(cy - h / 2, 0.0, lm.LID_MM[1] - h))
        out[name] = (round(x0, 3), round(y0, 3), round(x0 + w, 3), round(y0 + h, 3))
    return out


def _edge_polylines(rings_mm, origin_mm, px_per_mm):
    """The relief's rings as polylines in a render's pixels (16× sub-pixel, for cv2's shift 4)."""
    ox, oy = origin_mm
    return [np.round((lm.flatten(ring, 16) - [ox, oy]) * px_per_mm * 16).astype(np.int32) for ring in rings_mm]


def _render_window(ai_path, window_mm, dpi):
    import fitz
    x0, y0, x1, y1 = window_mm
    with fitz.open(str(ai_path)) as doc:
        pix = doc[0].get_pixmap(dpi=int(dpi), clip=fitz.Rect(lm.pt(x0), lm.pt(y0), lm.pt(x1), lm.pt(y1)), alpha=False)
        return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3].copy()


def relief_edge_crops(out, rings_mm, record):
    """D-D11-5.1's proof for the eye (the lead pays for the look): each window at 600 dpi from the master's own page
    (the picture, the type, the logo), above it the same with the relief mask's edge drawn as a one-pixel cyan line
    (0.042 mm), so the eye reads the bars bare and with the edge; and the whole oval with the edge, for orientation.
    Writes ``crops/relief-edge-*.png`` and ``relief-edge-crops.json``; returns the index."""
    engine_ai = Path(out) / 'engine' / 'lid-engine.ai'
    k = EDGE_CROP_DPI / lm.MM_PER_INCH
    made = []
    for name, window in edge_windows(record).items():
        bare = _render_window(engine_ai, window, EDGE_CROP_DPI)
        drawn = bare.copy()
        cv2.polylines(drawn, _edge_polylines(rings_mm, window[:2], k), True, lm.NAME_OUTLINE_RGB, 1, cv2.LINE_AA, shift=4)
        gap = np.full((EDGE_CROP_GAP_PX, bare.shape[1], 3), 255, dtype=np.uint8)
        path = Path(out) / 'crops' / ('relief-edge-%s.png' % name)
        Image.fromarray(np.concatenate([bare, gap, drawn], axis=0)).save(path, dpi=(EDGE_CROP_DPI, EDGE_CROP_DPI))
        size = Image.open(path).size
        made.append({'piece': name, 'file': lm.rel(path), 'window_mm': list(window), 'dpi': EDGE_CROP_DPI, 'px': list(size),
                     'under_the_eyes_limits': bool(max(size) <= lm.EYE_IMAGE_EDGE_MAX
                                                   and size[0] * size[1] <= lm.EYE_PIXELS_MAX)})
    x0, y0, x1, y1 = (v / lm.PX_PER_MM_SRC for v in lm.OVAL_BOX)
    dpi = EDGE_OVERVIEW_PX[0] / (x1 - x0) * lm.MM_PER_INCH
    over = _render_window(engine_ai, (x0, y0, x1, y1), dpi)
    cv2.polylines(over, _edge_polylines(rings_mm, (x0, y0), dpi / lm.MM_PER_INCH), True, lm.NAME_OUTLINE_RGB, 1,
                  cv2.LINE_AA, shift=4)
    path = Path(out) / 'crops' / 'relief-edge-overview.png'
    Image.fromarray(over).save(path)
    index = {'schema': 'day11_relief_edge_crops/1', 'rule': 'D-D11-5.1: the proof is the designer\'s eye\'s verdict on a '
             '1 : 1 crop of the mask\'s edge drawn over the bars', 'line': 'one pixel at 600 dpi (0.042 mm), cyan %s, '
             'anti-aliased' % (lm.NAME_OUTLINE_RGB,), 'rows': 'each piece: top the master as it prints (no line), below '
             'the same with the relief\'s edge', 'pieces': made,
             'overview': {'file': lm.rel(path), 'px': list(Image.open(path).size), 'dpi': round(dpi, 1),
                          'note': 'the whole oval with the edge, for orientation; not 1 : 1'},
             'eye': 'not looked at: the lead pays for the look (docs/audit/rescue_runtime/day11/gh_relief_eye_run.py)'}
    lm.write_json(Path(out) / 'relief-edge-crops.json', index)
    return index


SHEET_COLOURS = {'FOIL_GOLD': (203, 168, 125), 'FOIL_ROSE_GOLD': (201, 154, 132), 'EMBOSS': (60, 110, 170),
                 'DEBOSS': (70, 70, 80)}       # truthful_concept.finish_sheet's colours, plate by plate
SHEET_OTHER = (120, 120, 120)
SHEET_BAND_PX = 60                  # the legend's band above the lid


def finish_sheet(out):
    """The lid's finish sheet: every finish plate of the engine's page (``finish_proof.plate_masks``, each plate's label
    taken out by the reader itself) drawn over the lid's outline in its own colour at the pick's grid (1536 × 970),
    with a legend — the gold foil and, now, the bars' emboss. (``truthful_concept.finish_sheet`` blanks the top 9 ×
    110 mm of every plate as its label, which here would cut off the top bar's emboss.)"""
    from PIL import ImageDraw, ImageFont
    from django.conf import settings
    from apps.pipeline.services import finish_proof
    plates = finish_proof.plate_masks(Path(out) / 'engine' / 'lid-engine.ai', px_per_mm=lm.PX_PER_MM_SRC)
    h, w = plates[0]['mask'].shape
    sheet = np.full((h + SHEET_BAND_PX, w, 3), 246, dtype=np.uint8)
    legend = []
    for p in plates:
        colour = SHEET_OTHER
        if p['plate'] in SHEET_COLOURS:
            colour = SHEET_COLOURS[p['plate']]
        sheet[SHEET_BAND_PX:][p['mask']] = colour
        legend.append((p['plate'], colour, int(p['mask'].sum())))
    im = Image.fromarray(sheet)
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, SHEET_BAND_PX, w - 1, SHEET_BAND_PX + h - 1), outline=(0, 0, 0))
    font = ImageFont.truetype(str(Path(settings.BASE_DIR) / 'static' / 'fonts' / 'NotoSans-Bold.ttf'), 22)
    x = 10
    for name, colour, _ in legend:
        draw.rectangle((x, 18, x + 28, 42), fill=colour)
        draw.text((x + 36, 16), name, fill=(0, 0, 0), font=font)
        x += 60 + int(draw.textlength(name, font=font))
    path = Path(out) / 'finish-sheet.png'
    im.save(path)
    return {'file': lm.rel(path), 'px': [w, h], 'plates': [{'plate': n, 'pixels': c} for n, _, c in legend]}


# --- 4. one Latin face ---------------------------------------------------------------------------------------------------

ONE_FACE_LINES = ('descriptor_en', 'shades', 'net')
ONE_FACE_TEXTS = {'descriptor_en': 'EYESHADOW PALETTE', 'shades': '18 SHADES', 'net': '27g0.95oz'}


def one_face_units(pick):
    """The three small Latin lines' glyph units as the sketch draws them (the ℮ left out: the engine draws the sign)."""
    units = {}
    for key in ONE_FACE_LINES:
        u, _ = lm.line_units(pick, key)
        if key == 'net':
            u = [x for r in lm.runs_of(key, u) if r['text'] != lm.SIGN for x in r['units']]
        units[key] = u
    return units


def pooled_distance(units, path, wght):
    """A face's pooled outline distance over the three lines (mm), unrounded — ``rank_pooled``'s measure."""
    sums = [lm.score_face(units[k], path, ONE_FACE_TEXTS[k], wght, False) for k in ONE_FACE_LINES]
    return sum(x['dist_sum_px'] for x in sums) / sum(x['edge_px'] for x in sums) / (lm.PX_PER_MM_SRC * lm.MATCH_SCALE)


def static_weight(path):
    """A static face's weight as it names itself (OS/2 usWeightClass): what its line-face role is named at."""
    from fontTools.ttLib import TTFont
    with TTFont(path, lazy=True) as font:
        return float(font['OS/2'].usWeightClass)


def one_face(pick):
    """D-D11-5.4: ONE Latin face for "EYESHADOW PALETTE", "18 SHADES" and "27 g ℮ 0.95 oz" — the closest licensed face
    pooled over all three lines' glyphs (``lid_master.rank_pooled``), D-D8-5's near-tie rule standing (a house face
    within 5 % wins), read on the ranking's rounded distances as the rule has always been and again unrounded (said
    when the two differ). Returns the faces the build sets the lines in and the faces record: the per-line rankings
    kept as information (``face_record``), each Latin line's choice the pooled one."""
    latin = lm.licensed_faces(False)
    units = one_face_units(pick)
    pooled = lm.rank_pooled([(units[k], ONE_FACE_TEXTS[k]) for k in ONE_FACE_LINES], latin)
    chosen = lm.choose_face(pooled)
    best = pooled['ranked'][0]
    house = [r for r in pooled['ranked'] if r['house']][0]
    d_best = pooled_distance(units, latin[best['stem']]['path'], best['wght'])
    d_house = pooled_distance(units, latin[house['stem']]['path'], house['wght'])
    unrounded = best['stem']
    if not best['house'] and d_house <= d_best * (1 + lm.NEAR_TIE):
        unrounded = house['stem']
    weight = chosen['wght']
    if weight is None:
        weight = static_weight(latin[chosen['stem']]['path'])
    faces = {key: (chosen['stem'], weight) for key in ONE_FACE_LINES}
    record = lm.face_record(pick)
    for key in ONE_FACE_LINES:
        record[key]['per_line_chosen (information)'] = record[key]['chosen']
        record[key]['chosen'] = chosen
    record[lm.ONE_FACE_KEY] = {
        'lines': list(ONE_FACE_LINES), 'chosen': chosen, 'weight': weight, 'top': pooled['ranked'][:10],
        'measured': pooled['measured'],
        'near_tie': {'closest': {'stem': best['stem'], 'house': best['house'], 'distance_mm': round(d_best, 6)},
                     'closest_house': {'stem': house['stem'], 'distance_mm': round(d_house, 6)},
                     'bound_mm': round(d_best * (1 + lm.NEAR_TIE), 6),
                     'rounded_choice': chosen['stem'], 'unrounded_choice': unrounded,
                     'agree': unrounded == chosen['stem']},
        'said': 'D-D11-5.4: one Latin face for the three small lines, the closest pooled over all three lines\' glyphs '
                '(%d faces and weights measured): %s (%s); the closest house face, %s, reads %.4f mm against %.4f, '
                'outside D-D8-5\'s 5 %% near-tie (%.4f) — %s' % (
                    pooled['measured'], chosen['stem'], chosen['reason'], house['stem'], d_house, d_best,
                    d_best * (1 + lm.NEAR_TIE),
                    'the same choice read unrounded' if unrounded == chosen['stem'] else
                    'READ UNROUNDED THE NEAR-TIE GIVES %s: the rounded rule stands, and this is said' % unrounded)}
    record['distance'] = record['distance'] + '; the one face (D-D11-5.4) pooled over the three Latin lines'
    return faces, record


# --- the build: Golden Hour's files under day-11/golden-hour/, at $0 ------------------------------------------------------

def build_lid(out=LID):
    """The lid master with its relief plate and the one face (``lid_master.build`` with D-D11-5.1 and .4), its finish
    proof (the engine's page, foil and emboss), the finish sheet and the relief's edge crops for the eye."""
    pick = lm.load_pick(lm.PICK)
    relief = relief_mask(pick)

    def measure(engine_ai):
        limits = relief_limits(engine_ai)
        return {'plate_limits': limits, 'holds': dict(relief['record']['holds'], plate_0_3_mm=limits['holds'])}
    relief['measure'] = measure
    faces, record = one_face(pick)
    rec = lm.build(out, faces=faces, faces_record=record, relief=relief, schema=SCHEMA, subject=SUBJECT)
    sheet = finish_sheet(out)
    crops = relief_edge_crops(out, relief['rings_mm'], relief['record'])
    master = json.loads((Path(out) / 'master.json').read_text())
    master['finish_sheet'] = sheet
    master['relief_edge_crops'] = lm.rel(Path(out) / 'relief-edge-crops.json')
    master['super_resolution'] = SUPER_RESOLUTION
    # the files written after the build recorded its own (master.json's 'files'), pinned the same way
    later = [Path(out) / 'finish-sheet.png', Path(out) / 'relief-edge-crops.json'] + sorted(
        (Path(out) / 'crops').glob('relief-edge-*.png'))
    master['files_after_build'] = {lm.rel(p): {'sha256': lm.sha256(p), 'bytes': p.stat().st_size} for p in later}
    lm.write_json(Path(out) / 'master.json', master)
    rec.update(finish_sheet=sheet, relief_edge_crops=crops)
    return rec


SUPER_RESOLUTION = ('D-D11-5.5: skipped — the bounded super-resolution attempt is last in Day 11\'s cut order; 205 PPI is '
                    'accepted (D-D11-5.5) and the plate stays Lanczos 2×, as on Day 10')


def build_sticker(out=STICKER, lid_dir=LID):
    """The back sticker with D-D11-6's corrected lines (``palette_sticker.build``, corrected), its ground and ink from
    Golden Hour's Day 11 lid."""
    from apps.pipeline.services import palette_sticker as ps
    return ps.build(out, corrected=True, lid_dir=lid_dir)


def build_box(out=BOX, lid_dir=LID, sticker_dir=STICKER):
    """The box on its die with the Day 11 lid as its front (its relief on page 3) and the corrected sticker as its back."""
    from apps.pipeline.services import palette_box as pb
    return pb.build(out, lid_dir=lid_dir, sticker_dir=sticker_dir, schema='day11_golden_hour_box/1')


def tree_digest(root):
    """Every file under ``root`` by its path (from ``root``) and sha256: what proves a folder untouched."""
    return {str(p.relative_to(root)): lm.sha256(p) for p in sorted(Path(root).rglob('*')) if p.is_file()}


def digest_of(tree):
    """One sha256 over a folder's files and their sha256s (``tree_digest``), sorted: the folder as a whole."""
    import hashlib
    return hashlib.sha256(json.dumps(tree, sort_keys=True).encode()).hexdigest()


def checks_summary(checks):
    """The lid's checks as golden-hour.json carries them: its issues, the proofs that do not hold, and the proofs not
    measured (None: the eye's verdict pending, or what holds only by construction) — the last never read as held nor
    counted as failed."""
    pending = lm.pending_proofs(checks['proofs'], '')
    return {'issues': checks['issues'],
            'proofs_failed': [p for p in lm.failed_proofs(checks['proofs'], '') if p not in pending],
            'proofs_not_measured': pending}


def regenerate():
    """Golden Hour's files regenerated at $0 under day-11/golden-hour/ (lid, sticker, box; the tray waits for the
    lead's picture), Day 10's folder proven untouched (every file's sha256 before and after), and the run's record
    ``golden-hour.json``: the lid's record read back from its files once the eye's verdict on the relief, where one
    stands on these very crops, is merged in (``merge_relief_eye``); the looks still to be paid listed as pending."""
    before = tree_digest(DAY10)
    build_lid()
    sticker = build_sticker()
    box = build_box()
    merge_relief_eye(LID, None)
    after = tree_digest(DAY10)
    changed = sorted(k for k in set(before) | set(after) if k not in before or k not in after or before[k] != after[k])
    lid = json.loads((LID / 'master.json').read_text())
    fin = lid['finishes']
    record = {
        'schema': 'day11_golden_hour/1', 'pick': lid['pick'], 'test': 'Golden Hour, test one (D-D11-5)',
        'fixes': {
            '1 emboss the bars': {'files': [lm.rel(LID / n) for n in ('lid-master.pdf', 'lid-master.ai', 'finish-proof.png',
                                                                     'finish-sheet.png', 'relief-edge-crops.json')],
                                  'area_mm2': fin['relief_mask']['area_mm2'], 'holds': fin['relief_mask']['holds'],
                                  'eye': fin['relief_mask']['eye'],
                                  'safe_margin': fin['relief_mask']['safe_margin']['said']},
            '2 the tray\'s teal': {'state': 'the code only: the picture waits for the lead (gh_tray_run.py)',
                                    'prompt': 'palette_open.tray_story_prompt', 'pan_rule': 'palette_open.lift_from_case'},
            '3 the sticker\'s lines': {'files': [lm.rel(STICKER / 'fit-report.json'), lm.rel(STICKER / 'sticker.pdf')],
                                        'all_verbatim': sticker['corrected_lines']['all_verbatim'],
                                        'palette_word': sticker['palette_word']['holds'],
                                        'separator': sticker['separator']['holds'], 'net': sticker['net']['signs_hold'],
                                        'owner_to_confirm': [r['text'] for r in sticker['owner_to_confirm']]},
            '4 one Latin face': {'face': lid['faces'][lm.ONE_FACE_KEY]['chosen'],
                                 'near_tie': lid['faces'][lm.ONE_FACE_KEY]['near_tie'],
                                 'overlay': {k: lid['type']['overlay'][k]['holds'] for k in lm.LINES}},
            '5 super-resolution': SUPER_RESOLUTION},
        'box': {'files': [lm.rel(BOX / n) for n in ('box-artwork.pdf', 'box-artwork.ai', 'box-flat.png', 'box-fold-check.json',
                                                     'box-1to1-A3.pdf')],
                'fold_check': box['fold_check'], 'die_untouched': box['die_untouched']['holds'],
                'clean': box['clean']['holds'], 'relief': box['sources']['relief']},
        'checks': checks_summary(lid['checks']),
        'pending': pending_looks(LID),
        'day10_untouched': {'files': len(before), 'changed': changed, 'holds': not changed,
                            'tree_sha256': digest_of(after)},
        'files': {sub: tree_digest(GH / sub) for sub in ('lid', 'sticker', 'box')},
        'cost_usd': 0.0,
    }
    lm.write_json(GH / 'golden-hour.json', record)
    return record


# --- the paid steps' code paths (the lead runs them: docs/audit/rescue_runtime/day11/gh_*.py) -------------------------

EYE_PREFIX = 'day11/designer-eye/golden-hour/'
TRAY_PREFIX = 'day11/images/golden-hour/tray/'
TRAY_ATTEMPTS = 3                   # D-D11-5.2: one new tray picture, at most two retries
TRAY_CAP_USD = 1.70                 # the reservation cap under the prefix: the owner's $0.60 plus the $1.00 a gpt-image-2
                                    # call reserves (the $0.60 itself is held on settled spend by the runner's guard)
RELIEF_LOOK_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['pieces', 'follows_the_bars', 'glow_inside', 'cuts_into_a_bar', 'verdict', 'notes'],
    'properties': {
        'pieces': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['piece', 'follows_the_bars', 'glow_inside', 'cuts_into_a_bar', 'note'],
            'properties': {'piece': {'type': 'string'}, 'follows_the_bars': {'type': 'boolean'},
                           'glow_inside': {'type': 'boolean'}, 'cuts_into_a_bar': {'type': 'boolean'},
                           'note': {'type': 'string'}}}},
        'follows_the_bars': {'type': 'boolean'}, 'glow_inside': {'type': 'boolean'},
        'cuts_into_a_bar': {'type': 'boolean'}, 'verdict': {'type': 'string', 'enum': ['holds', 'defect']},
        'notes': {'type': 'string'}}}


def relief_look_text(outline):
    """The eye's question on the relief's edge, the outline said as the record has it (``outline_said``: the isoline,
    and the two outer edges where it is the bar's edge line plus 0.25 mm instead)."""
    return ('THE RELIEF OF THE BARS (Golden Hour, Day 11). The owner has asked that the five painted bars of light on '
            'this lid be blind-embossed (raised 0.3 mm); the oval\'s soft glow around and between them is NOT to be '
            'embossed. The bars are numbered 1 (top) to 5 (bottom). ' + outline + ' Each image below is one piece of '
            'the lid at 600 dpi (1 : 1 print scale, 1 mm = 23.6 px): on top the lid as it prints, below the same with '
            'the emboss mask\'s edge drawn as a thin cyan line. Then the whole oval with the line, for orientation (not '
            '1 : 1). For each piece answer: does the line follow the bar\'s own edge as you see it; does it take in any '
            'of the glow (a band of glow inside the line); does it cut into a bar (a part of a bar outside the line). '
            'Then the verdict: holds, or defect (say where). Answer in JSON.')


RELIEF_EYE_FILES = ('relief-eye.json', 'relief-eye-repair1.json')   # round 0, then repair 1's look (D-D11-10: one)
RELIEF_REPAIR_SAID = ('REPAIR 1 OF 1 (D-D11-10: one repair per item). Round 0 of this look named one defect: bar 5\'s '
                      'right end stopped about 5–7 mm short of where its engraved stripes visibly end, while every other '
                      'end and edge held. The repair changed ONE rule for all five bars: a bar now runs along its length '
                      'while its contrast OR its engraved stripes (their strength read across the bar\'s core) stand at '
                      'half their full strength or more, so every end follows the engraving; where only the engraving '
                      'carries a bar, its outline is held within the bar\'s own edge lines; the long edges elsewhere are '
                      'unchanged. Judge every piece again, the ends above all.')


def relief_eye_file(out):
    """The relief's look as it stands for the crops built now: the newest of RELIEF_EYE_FILES whose sent crops are the
    crops on disk (by sha256); else the newest written (it will read stale); else round 0's name (pending)."""
    made = [Path(out) / name for name in RELIEF_EYE_FILES if (Path(out) / name).exists()]
    if not made:
        return Path(out) / RELIEF_EYE_FILES[0]
    index = json.loads((Path(out) / 'relief-edge-crops.json').read_text())
    now = {p['piece']: lm.sha256(lm.REPO / p['file']) for p in index['pieces']}
    now['overview'] = lm.sha256(lm.REPO / index['overview']['file'])
    for path in reversed(made):
        sent = {x['piece']: x['sha256'] for x in json.loads(path.read_text())['sent']}
        if sent == now:
            return path
    return made[-1]


def relief_look(out, call, record_path=None, repair=None):
    """D-D11-5.1's proof: the designer's eye on the 1 : 1 crops of the relief mask's edge drawn over the bars (and the
    oval with the edge, for orientation) — does the edge follow each bar's own edge, does it take in any of the oval's
    glow, does it cut into a bar. ``call`` is ``lid_master.make_eye_call``'s (one paid look). Written once to
    ``relief-eye.json``; a look already written is read back, never paid twice. Either way its verdict is merged into
    the lid's master.json and checks.json and into ``record_path`` (golden-hour.json beside the lid's folder when
    None): ``merge_relief_eye``."""
    dest = Path(out) / RELIEF_EYE_FILES[0]
    if repair is not None:
        dest = Path(out) / ('relief-eye-%s.json' % repair)
    if record_path is None:
        record_path = Path(out).parent / 'golden-hour.json'
    if dest.exists():
        record = json.loads(dest.read_text())
        merge_relief_eye(out, record_path)
        return record
    index = json.loads((Path(out) / 'relief-edge-crops.json').read_text())
    master = json.loads((Path(out) / 'master.json').read_text())
    text = relief_look_text(master['finishes']['relief_mask']['outline_said'])
    if repair is not None:
        text = RELIEF_REPAIR_SAID + '\n\n' + text
    content = [{'type': 'text', 'text': text}]
    sent = []
    for piece in index['pieces']:
        block, info = lm._image_block(lm.REPO / piece['file'])
        content += [{'type': 'text', 'text': 'Piece %s (window %s mm):' % (piece['piece'], piece['window_mm'])}, block]
        sent.append(dict(info, piece=piece['piece']))
    block, info = lm._image_block(lm.REPO / index['overview']['file'])
    content += [{'type': 'text', 'text': 'The whole oval with the emboss edge (orientation only):'}, block]
    sent.append(dict(info, piece='overview'))
    operation = 'relief-edge'
    if repair is not None:
        operation = 'relief-edge/%s' % repair
    look = call(operation, content, RELIEF_LOOK_SCHEMA)
    record = {'schema': 'day11_relief_eye/1', 'round': repair, 'rule': index['rule'], 'text': text, 'sent': sent,
              'look': look,
              'holds': bool(look['payload'] is not None and look['payload']['verdict'] == 'holds')}
    lm.write_json(dest, record)
    merge_relief_eye(out, record_path)
    return record


def relief_eye_state(out):
    """The eye's verdict on the relief as it stands for the mask now built: pending (no look), looked (holds True or
    False, from ``relief-eye.json``), unanswered (the call returned no verdict: None), or stale (the look was sent other
    crops than the mask's edge as built now, by their sha256: None — its verdict is not this mask's)."""
    dest = relief_eye_file(out)
    if not dest.exists():
        return {'holds': None, 'state': 'pending',
                'said': 'not looked at: D-D11-5.1\'s proof is the designer\'s eye on the edge crops; the lead pays for '
                        'the look (docs/audit/rescue_runtime/day11/gh_relief_eye_run.py)'}
    look = json.loads(dest.read_text())
    index = json.loads((Path(out) / 'relief-edge-crops.json').read_text())
    now = {p['piece']: lm.sha256(lm.REPO / p['file']) for p in index['pieces']}
    now['overview'] = lm.sha256(lm.REPO / index['overview']['file'])
    sent = {s['piece']: s['sha256'] for s in look['sent']}
    if sent != now:
        return {'holds': None, 'state': 'stale', 'file': lm.rel(dest),
                'said': 'the eye looked at other crops than the mask\'s edge as built now (their sha256 differ): its '
                        'verdict is not this mask\'s; the look waits for the lead again'}
    payload = look['look']['payload']
    if payload is None:
        return {'holds': None, 'state': 'unanswered', 'file': lm.rel(dest),
                'said': 'the look returned no verdict (stop reason %s)' % look['look']['stop_reason']}
    return {'holds': bool(look['holds']), 'state': 'looked', 'file': lm.rel(dest), 'verdict': payload['verdict'],
            'said': 'the designer\'s eye on the edge crops: %s — %s' % (payload['verdict'], payload['notes'])}


def merge_relief_eye(out, record_path):
    """The eye's verdict (``relief_eye_state``) merged where the relief's proof is read: master.json (the relief's
    ``eye`` and ``holds.eye``, and its checks), checks.json (``proofs.relief_mask.eye``, the proofs' issues said again,
    ``checks_hold``, ``proofs_not_measured``) and, when ``record_path`` is given and exists, golden-hour.json (fix 1's
    holds and eye, its checks, the pending looks and the lid folder's sha256s, re-pinned after the writes). Returns the
    state."""
    out = Path(out)
    state = relief_eye_state(out)
    master = json.loads((out / 'master.json').read_text())
    checks = master['checks']
    if json.loads((out / 'checks.json').read_text()) != checks:
        raise ValueError('checks.json is not the master\'s own checks: not merged')
    old = lm.proof_issues(checks['proofs'], master['upscale'])
    keep = len(checks['issues']) - len(old)
    if checks['issues'][keep:] != old:
        raise ValueError('the checks\' last issues are not their proofs\': not merged')
    relief = master['finishes']['relief_mask']
    relief['eye'] = state
    relief['holds']['eye'] = state['holds']
    checks['proofs']['relief_mask'] = relief['holds']
    checks['issues'] = checks['issues'][:keep] + lm.proof_issues(checks['proofs'], master['upscale'])
    checks['checks_hold'] = not checks['issues']
    pending = lm.pending_proofs(checks['proofs'], '')
    if pending:
        checks['proofs_not_measured'] = pending
    elif 'proofs_not_measured' in checks:
        del checks['proofs_not_measured']
    lm.write_json(out / 'checks.json', checks)
    lm.write_json(out / 'master.json', master)
    if record_path is not None and Path(record_path).exists():
        record = json.loads(Path(record_path).read_text())
        fix = record['fixes']['1 emboss the bars']
        fix['holds'] = relief['holds']
        fix['eye'] = state
        record['checks'] = checks_summary(checks)
        record['pending'] = pending_looks(out)
        record['files']['lid'] = tree_digest(out)
        lm.write_json(Path(record_path), record)
    return state


LID_LOOK_ROUND = 0                  # the eye once on Golden Hour's lid: its own round 0 (fidelity-r0.json under its lid)
LID_EVIDENCE = ('engine/flat-1536.png', 'finish-proof.png')    # what the look's gate is shown of the master


def lid_evidence(out):
    """The master the whole-lid look judges, pinned: the flat and the finish proof its gate is shown, by sha256."""
    return {name: lm.sha256(Path(out) / name) for name in LID_EVIDENCE}


def lid_look(out, call):
    """D-D11-5's "the eye once on its lid": ``lid_master.fidelity_look`` once on Golden Hour's Day 11 lid (the gate —
    the pick, the master's flat, its finish proof — and the 1 : 1 crops, each difference classified allowed or a defect
    against D-D10-2's list; the master's facts say the one face and the emboss with its outline), round 0 of its own,
    written beside the lid (``fidelity-r0.json``). The master it judges is pinned before the call (``lid-eye.json``: the
    flat's and the finish proof's sha256), so a rebuild after the look reads as stale. Never twice: a look begun is
    read back, never paid again. ``call`` is ``lid_master.make_eye_call``'s (two paid calls)."""
    out = Path(out)
    pin = out / 'lid-eye.json'
    if pin.exists():
        return json.loads(pin.read_text())
    rec = json.loads((out / 'master.json').read_text())
    pick = lm.load_pick(lm.PICK)
    sketch = {key: lm.line_units(pick, key)[0] for key in lm.LINES}
    record = {'schema': 'day11_golden_hour_lid_eye/1',
              'rule': 'D-D11-5: the eye once on its lid (D-D10-3\'s gate and crops, D-D10-2\'s allowed differences)',
              'round': LID_LOOK_ROUND, 'file': lm.rel(out / ('fidelity-r%d.json' % LID_LOOK_ROUND)),
              'evidence': lid_evidence(out), 'holds': None, 'answered': None}
    lm.write_json(pin, record)                       # begun: never paid twice, even if the look does not return
    look = lm.fidelity_look(out, rec, sketch, call, LID_LOOK_ROUND)
    record.update(holds=look['holds'], answered=look['answered'], defects=look['defects'])
    lm.write_json(pin, record)
    refresh_record(out, out.parent / 'golden-hour.json')
    return record


def refresh_record(out, record_path):
    """golden-hour.json after a paid look: the pending looks as they stand now and the lid folder re-pinned."""
    if not Path(record_path).exists():
        return None
    record = json.loads(Path(record_path).read_text())
    record['pending'] = pending_looks(out)
    record['files']['lid'] = tree_digest(out)
    lm.write_json(Path(record_path), record)
    return record


def lid_look_state(out):
    """The whole-lid look as it stands for the lid built now: pending (not begun), begun (begun and not returned: never
    paid again; the lead reads fidelity-r0.json), stale (the master changed since: its flat or finish proof differs),
    or looked (holds True or False)."""
    pin = Path(out) / 'lid-eye.json'
    if not pin.exists():
        return {'holds': None, 'state': 'pending',
                'said': 'the designer\'s eye once on the lid (D-D11-5) waits for the lead '
                        '(docs/audit/rescue_runtime/day11/gh_lid_eye_run.py)'}
    record = json.loads(pin.read_text())
    if record['evidence'] != lid_evidence(out):
        return {'holds': None, 'state': 'stale', 'file': lm.rel(pin),
                'said': 'the eye looked at another build of the lid (its flat or finish proof differs since)'}
    if record['answered'] is None:
        return {'holds': None, 'state': 'begun', 'file': lm.rel(pin),
                'said': 'a look was begun and did not return: never paid again; the lead reads %s' % record['file']}
    if not record['answered']:
        return {'holds': None, 'state': 'unanswered', 'file': lm.rel(pin),
                'said': 'the look returned without a verdict (no defects named): never paid twice; the lead reads %s'
                        % record['file']}
    return {'holds': bool(record['holds']), 'state': 'looked', 'file': lm.rel(pin),
            'said': 'the eye once on the lid: %s' % ({True: 'holds', False: 'defects named'}[bool(record['holds'])])}


def pending_looks(out):
    """The paid steps not yet made (golden-hour.json's ``pending``): the eye on the relief's edge, the eye once on the
    whole lid, and the tray's picture — each with its runner and its state now."""
    looks = [{'what': 'the designer\'s eye on the relief\'s edge (D-D11-5.1\'s proof)',
              'runner': 'docs/audit/rescue_runtime/day11/gh_relief_eye_run.py', **relief_eye_state(out)},
             {'what': 'the designer\'s eye once on the lid (D-D11-5: the one face and the emboss reach it)',
              'runner': 'docs/audit/rescue_runtime/day11/gh_lid_eye_run.py', **lid_look_state(out)}]
    tray = {'what': 'the tray\'s new picture (D-D11-5.2)', 'runner': 'docs/audit/rescue_runtime/day11/gh_tray_run.py',
            'state': 'pending', 'said': 'the code only: the picture waits for the lead'}
    if (TRAY / 'attempts.json').exists():
        tray.update(state='made', said='attempts.json written')
    looks.append(tray)
    return [x for x in looks if x['state'] != 'looked' and x['state'] != 'made']


def make_tray(client, before_each):
    """D-D11-5.2's tray picture: one gpt-image-2 edit (the pick A-2.3 and the approved logo its only inputs, through the
    image guard and the ledger; ``palette_open.make_picture``) with the colour story row by row
    (``palette_open.tray_story_prompt``), read at $0 (``tray_picture.read_tray_picture``, 3 × 6) and its row 3's teal
    counted (``palette_open.teal_pans``); a retry only when the picture is not read or holds under three teal pans, two
    at most. ``before_each(name)`` runs before every paid call (the runner's ledger guard) and returns False when that
    call would pass the owner's limit: the round then stops, said, and is built from the pictures already made. Then
    the pans (every pan ΔE00 ≥ 10 from the case or lightened, listed) and the tray artwork under
    ``day-11/golden-hour/tray/``, from the readable picture with the most teal in row 3. Returns the record."""
    from apps.pipeline.services import palette_open as po
    from apps.pipeline.targets.container import tray_picture as tp
    prompt = po.tray_story_prompt(po.tray_names())
    attempts = []
    stopped = None
    for n in range(1, TRAY_ATTEMPTS + 1):
        name = 'picture-%d' % n
        if not (TRAY / name / 'picture.json').exists() and not before_each(name):
            stopped = '%s not bought: it would pass the owner\'s limit on settled spend' % name
            break
        made = po.make_picture(name, prompt, client=client, out=TRAY, prefix=TRAY_PREFIX, cap_usd=TRAY_CAP_USD)
        read = tp.read_tray_picture((TRAY / name / 'picture.png').read_bytes(), 3, 6)
        teal = po.teal_pans(read)
        attempts.append({'name': name, 'picture': made['picture'], 'reservation_id': made['reservation_id'],
                         'read': read['state'], 'teal_row_3': teal, 'read_record': read})
        if read['state'] == tp.READ and teal['holds']:
            break
    readable = [a for a in attempts if a['read'] == tp.READ]
    if not readable:
        lm.write_json(TRAY / 'attempts.json', {'attempts': [{k: a[k] for k in a if k != 'read_record'} for a in attempts],
                                               'chosen': None, 'stopped': stopped,
                                               'said': 'no picture could be read as 18 square pans'})
        raise ValueError('no tray picture was read as 18 square pans in %d attempts' % len(attempts))
    chosen = max(readable, key=lambda a: a['teal_row_3']['count'])
    record = po.build_tray(chosen['read_record'], out_dir=TRAY, picture_dir=TRAY / chosen['name'], lid_dir=LID, lift=True)
    lm.write_json(TRAY / 'attempts.json', {
        'rule': 'D-D11-5.2: one new tray picture whose prompt states the colour story row by row with at least three '
                'teal pans in row 3, at most two retries',
        'prompt': prompt, 'attempts': [{k: a[k] for k in a if k != 'read_record'} for a in attempts],
        'chosen': chosen['name'], 'teal_holds': chosen['teal_row_3']['holds'], 'stopped': stopped})
    return record
