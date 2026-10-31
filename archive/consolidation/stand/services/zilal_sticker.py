"""Day 11 §2, D-D11-4 — Ẓilāl's base sticker (182 × 112 mm), composed by the engine from the lid's assets at $0.

The owner's rule (D-D11-4): "a designed ground — the indigo field with a floated-stone border, the copy zone flat for
contrast (≥ 7 : 1); the copy EN / ES / AR with his corrected lines (D-D11-6); INCI and ℮ verbatim in every language."

The ground is the lid's own plate (``zilal/lid/engine/plate.png``: the marbling with the small type cleaned out) cut at
the sticker's frame — the lid less 4 mm all round, so every stone stands where it stands on the lid, at 1 : 1, never
scaled and never redrawn — with a flat zone in the plate's own indigo laid over its middle for the copy. The plate keeps
the sketch's raster under the hero and the name (the print's fallback beneath their foil): where a letter would show
outside the zone it is filled from its surround (Telea), as the sides' alternative does (``zilal_object.
mirror_alternative``), so no letter, hero or name pixel reaches the sticker. The copy is palette_sticker's machinery
(D-D11-6's lines, the house claims' rule, the unit wrap, the ℮ at its cap height, the per-language copy check) set in
the lid master's own faces inside the zone; every ink is read back from the files against the ground beneath it.

Every function here costs $0; ``sticker_look`` is passed the paid ``call`` (the designer's eye) and is exercised here
only with a stand-in that refuses before paying (``dry_precheck``).
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import palette_sticker as ps
from apps.pipeline.services import zilal_master as zm
from apps.pipeline.services import zilal_object as zo

OUT = zo.OBJ / 'sticker'
SCHEMA = 'day11_zilal_sticker/1'
SURFACE = 'apps/pipeline/services/zilal_sticker.py::build'
PLATE = zm.OUT / 'engine' / 'plate.png'
MASTER = zm.OUT / 'master.json'
MM_PER_PT = ps.MM_PER_PT

SIZE_MM = ps.SIZE_MM                # 182 × 112: the base (190 × 120) less 4 mm all round (D-D11-4)
BLEED_MM = ps.BLEED_MM              # the ground runs 2 mm past the die, as Day 10's
LID_INSET_MM = ((zm.LID_MM[0] - SIZE_MM[0]) / 2, (zm.LID_MM[1] - SIZE_MM[1]) / 2)   # the sticker's frame on the lid
TYPE_INSET_MM = 10.0                # the copy stands 10 mm in from the die: the border's stones and the zone's pad outside
ZONE_PAD_MM = 2.5                   # the flat zone reaches 2.5 mm past the copy all round …
ZONE_RADIUS_MM = 3.0                # … its corners rounded 3 mm (the die's own are 2 mm)
CONTRAST_MIN = 7.0                  # D-D11-4: every ink on the copy zone ≥ 7 : 1, read from the files
FLAT_DE_MAX = 0.5                   # the copy zone is flat: no ground pixel under the copy off the flat colour by > ΔE00 0.5
GROUND_SEED_DE = 6.0                # the flat colour: the median of the plate's pixels within ΔE00 6 of its clear ground …
GROUND_STRIDE = 4                   # … read on every 4th pixel each way
OFF_GROUND_DE = zm.OFF_GROUND_DE    # a pixel off the ground by over ΔE00 15 is ink or stone (the master's reading)
LETTER_GROW_PX = 7                  # a letter's mask grown 7 plate px (0.43 mm) to hold its anti-aliased edge
LETTER_BOX_GROW_MM = 0.5            # … and kept inside its element's ink box grown 0.5 mm (a vein beyond it is a stone's)
FILL_PAST_PX = zo.FILL_PAST_PX      # the fill reaches 40 px into the zone, so Telea never draws from a letter cut by it
TELEA_RADIUS_PX = 5
STONE_OPEN_PX = 3                   # a stone: off the ground and not rose gold, opened 3 px (the veins between taken away)
STONE_MIN_MM2 = 1.0                 # … listed when at least 1 mm² of it shows outside the zone
CONTRAST_GROW_MM = 0.3              # an ink's ground read over its box grown 0.3 mm …
CONTRAST_WORST_PCT = 99.5           # … against the lightest ground there (its 99.5th luminance percentile) and the median
READ_DPI = 300                      # the files are read back at print resolution
CROP_DPI = 600                      # the eye's 1 : 1 crops of the type, rendered from the PDF (6 pt at 600 PPI)
CROP_INK_MIN_PX = 200               # a crop of the copy holds its type: at least 200 ink pixels (a crop must render its thing)
CROP_STONE_MIN = 0.15               # a crop of the border holds its stones: at least 15 % of it off the flat colour

PALETTE_AR = ps.PALETTE_AR
PALETTE_AR_NEVER = ps.PALETTE_AR_NEVER
SEPARATOR = ps.SEPARATOR


# --- the ground: the plate's own window, the letters filled, the flat zone ---------------------------------------------

def plate_source():
    """The lid's plate (the marbling with its small type cleaned out; the hero and the name still in its raster), its
    sha256 and its scale (px per mm of the 190 mm lid)."""
    plate = np.asarray(Image.open(PLATE).convert('RGB'))
    return plate, {'file': lm.rel(PLATE), 'sha256': lm.sha256(PLATE), 'px': [int(plate.shape[1]), int(plate.shape[0])],
                   'px_per_mm': round(plate.shape[1] / zm.LID_MM[0], 6)}


def hex_of(rgb):
    return '#%02X%02X%02X' % tuple(int(round(float(v))) for v in rgb)


def rgb_of(hex_):
    return np.array([int(hex_[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float64)


def lab_of_hex(hex_):
    return lm.srgb_to_lab(rgb_of(hex_)[None, None].astype(np.uint8))[0, 0]


def ground_colour(plate):
    """The flat zone's colour, the lid's own indigo: the median of the plate's pixels within ΔE00 6 of its clear ground
    (the sketch's GROUND_BOX at the plate's scale, its median as the seed), read on every 4th pixel each way."""
    x0, y0, x1, y1 = (v * zm.UP for v in zm.GROUND_BOX)
    seed = np.median(plate[y0:y1, x0:x1].reshape(-1, 3), axis=0)
    seed_lab = lm.srgb_to_lab(seed[None, None].astype(np.uint8))[0, 0]
    sub = plate[::GROUND_STRIDE, ::GROUND_STRIDE]
    lab = lm.srgb_to_lab(sub)
    near = lm.delta_e00(lab, np.broadcast_to(seed_lab, lab.shape)) <= GROUND_SEED_DE
    flat = hex_of(np.median(sub[near], axis=0))
    return flat, {'hex': flat, 'seed': hex_of(seed), 'pixels_read': int(near.sum()), 'within_de00': GROUND_SEED_DE,
                  'read': 'the median of the plate\'s pixels within ΔE00 %.0f of its clear ground (the sketch\'s '
                          'GROUND_BOX), every %dth pixel each way' % (GROUND_SEED_DE, GROUND_STRIDE)}


def rose_gold(rgb):
    """The master's rose gold by colour (zilal_master.masks: L* > 30, chroma > 12, hue 38–75°), on any RGB array."""
    lab = lm.srgb_to_lab(rgb)
    light, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    hue = np.degrees(np.arctan2(b, a)) % 360
    return ((light > zm.ROSE_GOLD_L_MIN) & (np.hypot(a, b) > zm.ROSE_GOLD_C_MIN) & (hue > zm.ROSE_GOLD_HUE[0])
            & (hue < zm.ROSE_GOLD_HUE[1]))


def letter_mask(plate):
    """Every pixel of the lid's lettering the plate still carries — the hero and the name, kept in its raster as the
    print's fallback beneath their foil — on the plate's grid: each element's own mask from the pick (as the master grows
    it, ``zilal_master.element_mask_up``) and every rose-gold part wholly inside its window (a part touching the window's
    edge is a vein's), kept inside the element's ink box (master.json) grown 0.5 mm, then grown LETTER_GROW_PX. The small
    lines and the logo were cleaned out of the plate by the master: they are not in it."""
    pick = zm.load_master_pick()
    master = json.loads(MASTER.read_text(encoding='utf-8'))
    shape = plate.shape[:2]
    k = shape[1] / zm.LID_MM[0]
    out = np.zeros(shape, dtype=bool)
    for name in ('hero', 'name'):
        x0, y0, x1, y1 = (v * zm.UP for v in zm.WINDOWS[name])
        gold = rose_gold(plate[y0:y1, x0:x1]).astype(np.uint8)
        _, labels, _, _ = cv2.connectedComponentsWithStats(gold, connectivity=8)
        edge = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
        inside = (labels > 0) & ~np.isin(labels, edge)
        own = np.zeros(shape, dtype=bool)
        own[y0:y1, x0:x1] = inside
        own |= zm.element_mask_up(pick, name, shape)
        bx0, by0, bx1, by1 = master['element_boxes_mm'][name]
        box = np.zeros(shape, dtype=bool)
        g = LETTER_BOX_GROW_MM
        box[max(int(math.floor((by0 - g) * k)), 0):int(math.ceil((by1 + g) * k)),
            max(int(math.floor((bx0 - g) * k)), 0):int(math.ceil((bx1 + g) * k))] = True
        out |= own & box
    return cv2.dilate(out.astype(np.uint8), np.ones((LETTER_GROW_PX, LETTER_GROW_PX), np.uint8)).astype(bool)


def rounded_alpha(shape, box_px, radius_px):
    """A rounded rectangle's coverage (0–1) on a pixel grid: its signed distance at each pixel's centre, anti-aliased
    over one pixel. ``box_px`` (x0, y0, x1, y1) in the grid's px, fractional; ``radius_px`` its corners."""
    x0, y0, x1, y1 = box_px
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = (x1 - x0) / 2 - radius_px, (y1 - y0) / 2 - radius_px
    qx = np.abs(np.arange(shape[1]) + 0.5 - cx)[None, :] - hx
    qy = np.abs(np.arange(shape[0]) + 0.5 - cy)[:, None] - hy
    outside = np.hypot(np.maximum(qx, 0.0), np.maximum(qy, 0.0))
    inside = np.minimum(np.maximum(qx, qy), 0.0)
    return np.clip(0.5 - (outside + inside - radius_px), 0.0, 1.0)


def compose(window, letters, zone_px, radius_px, flat_hex):
    """A surface's ground from its window of the lid's plate (1 : 1): the letters that would show outside the flat zone
    filled from their surround (Telea; the fill reaching FILL_PAST_PX into the zone so it never draws from a letter cut
    by the zone's edge), then the flat zone (``zone_px`` x0 y0 x1 y1 and ``radius_px`` in the window's px) laid over in
    the flat colour. ``zone_px`` None: no zone (the ends). Returns the ground (uint8 RGB), the zone's coverage (0–1) and
    the mask filled."""
    shape = window.shape[:2]
    alpha = np.zeros(shape, dtype=np.float64)
    reach = np.zeros(shape, dtype=bool)
    if zone_px is not None:
        alpha = rounded_alpha(shape, zone_px, radius_px)
        x0, y0, x1, y1 = zone_px
        inner = (x0 + FILL_PAST_PX, y0 + FILL_PAST_PX, x1 - FILL_PAST_PX, y1 - FILL_PAST_PX)
        reach = rounded_alpha(shape, inner, max(radius_px - FILL_PAST_PX, 0.0)) >= 0.5
    fill = letters & ~reach
    filled = window.copy()
    if fill.any():
        filled = cv2.inpaint(window, fill.astype(np.uint8), TELEA_RADIUS_PX, cv2.INPAINT_TELEA)
    flat = rgb_of(flat_hex)
    ground = filled.astype(np.float64) * (1.0 - alpha[..., None]) + flat[None, None, :] * alpha[..., None]
    return np.clip(np.round(ground), 0, 255).astype(np.uint8), alpha, fill


def letters_check(ground, window, letters, alpha):
    """No letter, hero or name pixel reaches the surface: of the letters' pixels that show (outside the flat zone), none
    is the plate's own pixel unchanged; the rose-gold pixels left in the letters' place are counted beside it (the fill
    draws from the veins around, so a few may read as rose gold without being a letter's)."""
    shows = letters & (alpha < 0.5)
    same = shows & np.all(ground == window, axis=2)
    # a letter's pixel is its ink, the master's rose gold: the mask is grown 7 px past the ink, so plain ground at its
    # edge that Telea returned as it was is counted beside, never as a letter left in place
    unchanged = same & rose_gold(window)
    gold_left = shows & rose_gold(ground)
    return {'letter_px_showing': int(shows.sum()), 'unchanged_letter_px': int(unchanged.sum()),
            'unchanged_ground_px_in_the_grown_edge': int((same & ~rose_gold(window)).sum()),
            'rose_gold_px_left_in_their_place': int(gold_left.sum()), 'holds': bool(unchanged.sum() == 0),
            'rule': 'no letter, hero or name pixel may reach the surface: every letter pixel (its rose-gold ink) '
                    'outside the flat zone is filled from its surround (Telea), none left as the plate drew it'}


def border_stones(ground, alpha, flat_hex, k, origin_lid_mm, turn):
    """The border's crops as they show: the stones (off the flat colour by over ΔE00 15 and not rose gold, opened 3 px so
    the veins between them fall away) with at least 1 mm² outside the zone, each its box in the lid's own mm (where it
    came from: ``origin_lid_mm`` the window's top-left on the lid, ``turn`` 'none' or how the window was turned), the
    area showing and whether the zone's edge or the window's edge cuts it; and the share of the border that is stone."""
    lab = lm.srgb_to_lab(ground)
    off = lm.delta_e00(lab, np.broadcast_to(lab_of_hex(flat_hex), lab.shape)) > OFF_GROUND_DE
    stones = off & ~rose_gold(ground)
    stones = cv2.morphologyEx(stones.astype(np.uint8), cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * STONE_OPEN_PX + 1,) * 2))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(stones, connectivity=8)
    outside = alpha < 0.5
    shown = np.bincount(labels[outside].ravel(), minlength=count)
    under = np.bincount(labels[~outside].ravel(), minlength=count)
    h, w = labels.shape
    rows = []
    for i in range(1, count):
        if shown[i] / k ** 2 < STONE_MIN_MM2:
            continue
        left, top, bw, bh = (int(v) for v in stats[i, :4])
        rows.append({'window_box_px': [left, top, left + bw, top + bh],
                     'lid_box_mm': [round(origin_lid_mm[0] + left / k, 2), round(origin_lid_mm[1] + top / k, 2),
                                    round(origin_lid_mm[0] + (left + bw) / k, 2),
                                    round(origin_lid_mm[1] + (top + bh) / k, 2)],
                     'shown_mm2': round(float(shown[i]) / k ** 2, 2),
                     'cut_by_the_zone': bool(under[i] > 0),
                     'cut_by_the_window': bool(left == 0 or top == 0 or left + bw == w or top + bh == h)})
    border = int(outside.sum())
    return {'stones': rows, 'count': len(rows), 'turn': turn,
            'stone_share_of_the_border': round(float((off & outside).sum()) / max(border, 1), 4),
            'read': 'stones off the flat colour by over ΔE00 %.0f and not rose gold, opened %d px; listed when %.0f mm² '
                    'or more shows outside the zone; box in the lid\'s own mm when the window is not turned' % (
                        OFF_GROUND_DE, STONE_OPEN_PX, STONE_MIN_MM2)}


# --- the copy, laid out in the zone (palette_sticker's machinery, the lid's faces) ---------------------------------------

def faces():
    """The lid master's faces (master.json type.faces), resolved by the engine as the master resolved them: its one
    Latin face (D-D11-3.4) for the heads, the body, the title and the ℮ line; its Arabic face for the Arabic."""
    from apps.ire import font_roles
    master = json.loads(MASTER.read_text(encoding='utf-8'))['type']['faces']
    latin = font_roles.resolve_line_face(master['latin']['stem'], master['latin']['weight'])
    arabic = font_roles.resolve_line_face(master['arabic']['stem'], master['arabic']['weight'])
    return {'regular': latin, 'medium': latin, 'arabic': arabic}


def palette_sticker_arabic():
    """palette_sticker's own Arabic face (Tajawal PF Medium), resolved: measured beside the lid's for the face decision."""
    from apps.ire import font_roles
    return font_roles.resolve_line_face(*ps.ARABIC)


def layout():
    """The sticker's frames in mm from the die's top-left: the copy's area (TYPE_INSET_MM in) and the flat zone (the
    copy's area grown ZONE_PAD_MM, corners ZONE_RADIUS_MM); the column width (three columns, palette_sticker's gaps)."""
    w, h = SIZE_MM
    t = (TYPE_INSET_MM, TYPE_INSET_MM, w - TYPE_INSET_MM, h - TYPE_INSET_MM)
    z = (t[0] - ZONE_PAD_MM, t[1] - ZONE_PAD_MM, t[2] + ZONE_PAD_MM, t[3] + ZONE_PAD_MM)
    return {'type_mm': t, 'zone_mm': z, 'radius_mm': ZONE_RADIUS_MM,
            'column_mm': (t[2] - t[0] - 2 * ps.COLUMN_GAP_MM) / 3}


def room_of(lay, net):
    """The columns' height: the copy's area less the title band, the foot band and the ℮ line's band (its own size)."""
    t = lay['type_mm']
    net_band = net['pt'] * MM_PER_PT * ps.LEAD + 1.0
    return (t[3] - t[1]) - ps.TITLE_BAND_MM - ps.FOOT_MM - net_band


def fit(blocks, fc, net, lay):
    """The body size, palette_sticker's rule in the zone: from 7 pt down in 0.25 pt steps to the 5 pt floor, the largest
    at which every column fits its room; at the floor when none does (then every overflowing line is reported, none
    dropped)."""
    column = lay['column_mm']
    room = room_of(lay, net)
    size = ps.BODY_START_PT
    while size >= ps.BODY_FLOOR_PT - 1e-9:
        heights = {lang: ps.column_height(rows, column, size, fc) for lang, rows in blocks.items()}
        if max(heights.values()) <= room:
            return {'size_pt': size, 'column_mm': column, 'room_mm': room, 'heights_mm': heights, 'fits': True}
        size -= ps.BODY_STEP_PT
    heights = {lang: ps.column_height(rows, column, ps.BODY_FLOOR_PT, fc) for lang, rows in blocks.items()}
    return {'size_pt': ps.BODY_FLOOR_PT, 'column_mm': column, 'room_mm': room, 'heights_mm': heights, 'fits': False}


def review_of(row):
    """A line's review mark, as palette_sticker gives it."""
    if 'owner_to_confirm' in row and row['owner_to_confirm']:
        return ps.OWNER_TO_CONFIRM
    if not row['verbatim'] and row['regulated']:
        return 'machine draft — for review'
    if not row['verbatim']:
        return 'machine translation — not regulated'
    return None


TITLE_GAP_MM = 8.0                  # the two names of the one title, 8 mm apart


def widowless(lines, column, size, fc):
    """A paragraph never ends on one word (the eye's round 0: the Arabic description's last line held one word): when
    its last line holds a single word and the line before holds three or more, that line's last word (the wrap merges a
    line's words into one run per face) moves down, if the new last line still fits the column and the word is not a
    glued sign. Returns the lines (unchanged otherwise)."""
    if len(lines) < 2 or not lines[-1] or not lines[-2]:
        return lines
    prev, last = lines[-2], lines[-1]
    if prev[-1][0] == 'break' or any(f == 'break' for f, _ in last):
        return lines
    if sum(len(t.split()) for _, t in last) != 1 or sum(len(t.split()) for _, t in prev) < 3:
        return lines
    face, text = prev[-1]
    head, _, word = text.rpartition(' ')
    if not head or word in ps.GLUED:
        return lines
    new_last = [(face, word)] + last
    if last[0][0] == face:
        new_last = [(face, word + ' ' + last[0][1])] + last[1:]
    width = (sum(ps.width_mm(t, fc[f], size) for f, t in new_last)
             + ps.width_mm(' ', fc['regular'], size) * (len(new_last) - 1))
    if width > column:
        return lines
    return lines[:-2] + [prev[:-1] + [(face, head)], new_last]


def glue_ci(blocks):
    """Every colour index travels with its number (the eye's round 0: "CI" broken from "77007." in the Arabic INCI): in
    each ingredients row, a wrap unit "CI" is joined with the unit after it; the words, and so the printed text, are
    unchanged."""
    for rows in blocks.values():
        for row in rows:
            if row['field'] != 'ingredients':
                continue
            units = row['units'] if 'units' in row else ps.wrap_units(row['text'], row['field'])
            joined = []
            for unit in units:
                if joined and joined[-1] == ['CI']:
                    joined[-1] = joined[-1] + unit
                else:
                    joined.append(list(unit))
            row['units'] = joined
    return blocks


BOTTOM_ROW = ('shades', 'net')      # the lid's bottom row: cleaned out of the plate, its pockets in the sticker's border
POCKET_GROW_MM = 1.0                # the row's windows grown 1 mm …
CLEANED_DE = 3.0                    # … where the plate stands off the pick (upscaled) by over ΔE00 3: the cleaning's footprint
CLEANED_GROW_PX = 4
POCKET_FEATHER_MM = 0.25
TONE_SIGMA_MM = 1.0                 # the refill's tone read from the untouched ground within about 1 mm


def refill_bottom(ground, alpha, plate, origin_px, k, flat_hex):
    """The lid's bottom row (18 SHADES, the ℮ line) was cleaned out of its plate by inpainting, which reads as a dark
    smear where the sticker's border shows it (the eye's round 0). Its footprint — inside the row's windows
    (zilal_master.WINDOWS, grown 1 mm), where the plate stands off the pick enlarged as the plate was (ΔE00 > 3), grown
    4 px, outside the flat zone — takes the plate's own pixels from the same rows shifted sideways by the one shift
    whose source pixels are calmest (the fewest off the flat colour by over ΔE00 15), feathered 0.5 mm; nothing else
    changes. Returns the ground and the record."""
    from scipy.ndimage import gaussian_filter
    ox, oy = origin_px
    h, w = ground.shape[:2]
    up = lm.upscale(zm.load_master_pick())
    windows = np.zeros((h, w), dtype=bool)
    for name in BOTTOM_ROW:
        x0, y0, x1, y1 = (v * zm.UP for v in zm.WINDOWS[name])
        g = int(round(POCKET_GROW_MM * k))
        windows[max(y0 - g - oy, 0):min(y1 + g - oy, h), max(x0 - g - ox, 0):min(x1 + g - ox, w)] = True
    ys, xs = np.nonzero(windows)
    sub = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
    py = slice(oy + ys.min(), oy + ys.max() + 1)
    px = slice(ox + xs.min(), ox + xs.max() + 1)
    changed = np.zeros((h, w), dtype=bool)
    de = lm.delta_e00(lm.srgb_to_lab(plate[py, px]).reshape(-1, 3), lm.srgb_to_lab(up[py, px]).reshape(-1, 3))
    changed[sub] = de.reshape(plate[py, px].shape[:2]) > CLEANED_DE
    changed = cv2.dilate(changed.astype(np.uint8), np.ones((2 * CLEANED_GROW_PX + 1,) * 2, np.uint8)).astype(bool)
    target = changed & windows & (alpha < 0.5)
    ty, tx = np.nonzero(target)
    if not len(ty):
        return ground, {'filled_px': 0}
    flat_lab = lm.srgb_to_lab(rgb_of(flat_hex)[None, None, :].astype(np.uint8))[0, 0]
    plate_lab = lm.srgb_to_lab(plate)
    calm = lm.delta_e00(plate_lab.reshape(-1, 3), np.broadcast_to(flat_lab, (plate.shape[0] * plate.shape[1], 3)))
    calm = calm.reshape(plate.shape[:2]) <= OFF_GROUND_DE
    # a source pixel is calm ground AND untouched by the cleaning (the plate equal to the enlarged pick there): the
    # smear itself is dark indigo, so calm alone would let it be its own donor
    rows_ = slice(oy + ty.min(), oy + ty.max() + 1)
    untouched = np.ones(plate.shape[:2], dtype=bool)
    band = lm.delta_e00(plate_lab[rows_].reshape(-1, 3), lm.srgb_to_lab(up[rows_]).reshape(-1, 3))
    untouched[rows_] = cv2.dilate((band.reshape(plate[rows_].shape[:2]) > CLEANED_DE).astype(np.uint8),
                                  np.ones((2 * CLEANED_GROW_PX + 1,) * 2, np.uint8)) == 0
    good = calm & untouched
    best, best_share = None, 2.0
    for shift in range(int(k), int(ox + tx.min()), int(k)):
        share = 1.0 - float(good[oy + ty, ox + tx - shift].mean())
        if share < best_share:
            best, best_share = shift, share
    # the donor brings its grain, not its tone: each pixel the donor's own deviation from its local mean (σ 1 mm) laid on
    # the local tone of the untouched ground around the spot (normalised convolution, σ 1 mm, the footprint left out)
    y0, y1, x0, x1 = ty.min() - 2 * int(k), ty.max() + 1 + 2 * int(k), tx.min() - 2 * int(k), tx.max() + 1 + 2 * int(k)
    y0, x0, y1, x1 = max(y0, 0), max(x0, 0), min(y1, h), min(x1, w)
    region = ground[y0:y1, x0:x1].astype(np.float64)
    keep = (~target[y0:y1, x0:x1]).astype(np.float64)
    ry, rx = np.mgrid[y0:y1, x0:x1]
    donor = plate[np.clip(oy + ry, 0, plate.shape[0] - 1), np.clip(ox + rx - best, 0, plate.shape[1] - 1)]
    donor = donor.astype(np.float64)
    sigma = TONE_SIGMA_MM * k
    weight_keep = np.maximum(gaussian_filter(keep, sigma), 1e-6)
    tone = np.stack([gaussian_filter(region[..., c] * keep, sigma) / weight_keep for c in range(3)], axis=-1)
    donor_tone = np.stack([gaussian_filter(donor[..., c], sigma) for c in range(3)], axis=-1)
    fill = donor - donor_tone + tone
    soft = gaussian_filter(target[y0:y1, x0:x1].astype(np.float64), POCKET_FEATHER_MM * k)
    soft = np.where(target[y0:y1, x0:x1], 1.0, np.minimum(soft * 2.0, 1.0))[..., None]
    out = ground.astype(np.float64)
    out[y0:y1, x0:x1] = region * (1 - soft) + fill * soft
    return np.clip(np.round(out), 0, 255).astype(np.uint8), {
        'windows': list(BOTTOM_ROW), 'filled_px': int(target.sum()), 'shift_px': int(best),
        'shift_mm': round(best / k, 2), 'source_not_calm_untouched_share': round(best_share, 4),
        'rule': 'the lid\'s bottom row\'s cleaning footprint (the plate off the enlarged pick by over ΔE00 3, grown '
                '4 px) in the border takes the plate\'s own pixels from the same rows, shifted sideways to the source '
                'with the most calm ground the cleaning never touched; nothing else changes'}


def widows_in(rows):
    """Every paragraph (a language's field) whose last drawn line holds one word, read from the drawn rows."""
    last = {}
    for r in rows:
        if r['field'] in ('product name', 'net', 'foot', 'claims'):
            continue
        last[(r['lang'], r['field'])] = r['text']
    found = ['%s %s: "%s"' % (lang, field, text) for (lang, field), text in last.items() if items_of(text) == 1]
    return {'found': found, 'paragraphs': len(last),
            'rule': 'no paragraph ends on a line of one item (the eye\'s rounds: a word, or a colour index with its '
                    'number, "CI 77007."); a claims line wraps claim by claim, so a one-word claim (Long-wear) stays '
                    'whole and is not counted'}


def items_of(text):
    """A line's items as the eye counts them: its words, a colour index and its number ("CI 77007.") one item."""
    return len([w for w in re.sub(r'\bCI (?=\d)', 'CI\u00a0', text).split(' ') if w])


AR_INCI_STEP_MM = 0.5               # [the owner's answer of 24 October, 4] the Arabic INCI wrapped narrower by 0.5 mm steps …
AR_INCI_TRIM_MAX_MM = 8.0           # … at most 8 mm, until its last line holds two items or more (the words verbatim)


def inci_wrap(row, column, size, fc):
    """The Arabic column's INCI paragraph wrapped by the column's width only (the owner's answer of 24 October, 4):
    the least narrowing, in 0.5 mm steps up to 8 mm, at which its last line holds two items or more (a colour index
    with its number one item); its right edge stays the column's. Returns the width used and the lines (the full
    column's when no narrowing resolves it)."""
    width = column
    lines = ps.wrap(row, width, size, fc)
    while items_of(' '.join(t for f, t in lines[-1] if f != 'break')) < 2 and width > column - AR_INCI_TRIM_MAX_MM:
        width = round(width - AR_INCI_STEP_MM, 3)
        lines = ps.wrap(row, width, size, fc)
    if items_of(' '.join(t for f, t in lines[-1] if f != 'break')) < 2:
        return column, ps.wrap(row, column, size, fc)
    return width, lines


def document(blocks, fitted, fc, ink_hex, net, lay, ground):
    """The sticker as an engine document (page = the die plus 2 mm bleed): ``ground`` ({'png', 'box_mm'} in page mm, or
    None for the type alone); the title (the name in English at the left, in Arabic at the right); three columns, EN |
    ES | AR (right to left), each closing on the ℮ line at its cap height (``net``); the foot (batch and expiry write-in
    fields, the EAN-13 placeholder frame, no number) — all inside the copy's area. Returns the document and every drawn
    line's row, each with its place (page mm) and whether it overflows its column."""
    from apps.ire.graph import Color, Document, Group, Image as GImage, Rect, SolidFill, Stroke, TextRun
    b = BLEED_MM
    t = lay['type_mm']
    ink = Color.from_hex(ink_hex)
    size = fitted['size_pt']
    pitch = size * MM_PER_PT * ps.LEAD
    column = fitted['column_mm']
    nodes = []
    if ground is not None:
        x, y, w, h = ground['box_mm']
        nodes.append(Group(name='GROUND', role='background', children=[
            GImage(name='ground: the lid\'s plate, its flat zone', src=str(ground['png']), x=x, y=y, w=w, h=h)]))
    rows = []
    top = b + t[1] + ps.TITLE_PT * MM_PER_PT
    # the title: the two names the owner gave (English, Arabic) set as ONE title centred over the three columns, so no
    # column carries a head the others lack (the eye's round 0: "the Spanish column has no head"; no Spanish name is
    # given, and none is invented)
    widths = {'en': ps.width_mm(ps.NAME_EN, fc['medium'], ps.TITLE_PT),
              'ar': ps.width_mm(ps.NAME_AR, fc['arabic'], ps.TITLE_PT)}
    total = widths['en'] + TITLE_GAP_MM + widths['ar']
    start = b + (t[0] + t[2]) / 2 - total / 2
    nodes.append(TextRun(name='name:en', text=ps.NAME_EN, x=start, y=top, font=fc['medium']['role'],
                         size_pt=ps.TITLE_PT, color=ink))
    nodes.append(TextRun(name='name:ar', text=ps.NAME_AR, x=start + total, y=top, font=fc['arabic']['role'],
                         size_pt=ps.TITLE_PT, color=ink, align='right', rtl=True))
    for lang, text in (('en', ps.NAME_EN), ('ar', ps.NAME_AR)):
        x0 = start
        if lang == 'ar':
            x0 = start + total - widths['ar']
        rows.append({'lang': lang, 'field': 'product name', 'text': text, 'size_pt': ps.TITLE_PT,
                     'width_mm': round(widths[lang], 2), 'room_mm': round(t[2] - t[0], 2),
                     'fits': total <= t[2] - t[0], 'shrunk': False, 'source': 'brief 124', 'review': None,
                     'overflows': False,
                     'box_mm': [round(x0, 3), round(top - ps.TITLE_PT * MM_PER_PT, 3), round(x0 + widths[lang], 3),
                                round(top + 0.3 * ps.TITLE_PT * MM_PER_PT, 3)]})
    region_top = b + t[1] + ps.TITLE_BAND_MM
    region_bottom = region_top + fitted['room_mm']
    for i, lang in enumerate(('en', 'es', 'ar')):
        x_left = b + t[0] + i * (column + ps.COLUMN_GAP_MM)
        x_right = x_left + column
        slot = region_top
        for row in blocks[lang]:
            if row['field'] == 'net':
                continue
            wrap_mm = column
            lines = ps.wrap(row, column, size, fc)
            if lang == 'ar' and row['field'] == 'ingredients':
                wrap_mm, lines = inci_wrap(row, column, size, fc)
            if row['field'] != 'claims':           # a claims line wraps claim by claim: a one-word claim stays whole
                lines = widowless(lines, wrap_mm, size, fc)
            for line in lines:
                y = slot + size * MM_PER_PT
                if lang == 'ar':
                    x = x_right
                    for face_key, text in line:
                        nodes.append(TextRun(name='%s:%s' % (lang, row['field']), text=text, x=x, y=y,
                                             font=fc[face_key]['role'], size_pt=size, color=ink, align='right',
                                             rtl=face_key == 'arabic'))
                        x -= ps.width_mm(text, fc[face_key], size) + ps.width_mm(' ', fc[face_key], size)
                else:
                    x = x_left
                    for face_key, text in line:
                        nodes.append(TextRun(name='%s:%s' % (lang, row['field']), text=text, x=x, y=y,
                                             font=fc[face_key]['role'], size_pt=size, color=ink))
                        x += ps.width_mm(text, fc[face_key], size) + ps.width_mm(' ', fc[face_key], size)
                drawn = ' '.join(tx for _, tx in line)
                line_w = (sum(ps.width_mm(tx, fc[kk], size) for kk, tx in line)
                          + ps.width_mm(' ', fc['regular'], size) * (len(line) - 1))
                lx0 = x_left
                if lang == 'ar':
                    lx0 = x_right - line_w
                rtl_line = lang == 'ar' and line[0][0] == 'arabic'
                rows.append({'lang': lang, 'field': row['field'], 'text': drawn, 'size_pt': size,
                             'width_mm': round(line_w, 2), 'room_mm': round(column, 2),
                             'fits': line_w <= column + 1e-6, 'shrunk': size < ps.BODY_START_PT,
                             'source': row['source'], 'review': review_of(row),
                             'direction': 'right to left' if rtl_line else 'left to right',
                             'overflows': bool(slot + pitch > region_bottom + 1e-6),
                             'box_mm': [round(lx0, 3), round(y - size * MM_PER_PT, 3), round(lx0 + line_w, 3),
                                        round(y + 0.3 * size * MM_PER_PT, 3)]})
                slot += pitch
            slot += ps.PARA_GAP * pitch
        net_y = b + t[3] - ps.FOOT_MM - 1.0
        anchor = x_left
        if lang == 'ar':
            anchor = x_right
        net_drawn, total = ps.net_nodes(anchor, net_y, lang == 'ar', fc, ink, lang, net)
        nodes += net_drawn
        nx0 = anchor
        if lang == 'ar':
            nx0 = anchor - total
        rows.append({'lang': lang, 'field': 'net', 'text': ps.NET, 'size_pt': net['pt'], 'sign_mm': net['sign_mm'],
                     'width_mm': round(total, 2), 'room_mm': round(column, 2), 'fits': total <= column,
                     'shrunk': False, 'source': 'brief 124 (the ℮ line, verbatim in every language)', 'review': None,
                     'direction': 'left to right', 'overflows': False,
                     'box_mm': [round(nx0, 3), round(net_y - net['cap_mm'], 3), round(nx0 + total, 3),
                                round(net_y + 0.25 * net['cap_mm'], 3)]})
    foot_top = b + t[3] - ps.FOOT_MM + 2.0
    for j, (word, key) in enumerate((('BATCH', 'lot'), ('EXP', 'expiry'))):
        fy = foot_top + 6.0 + j * 7.0
        nodes.append(TextRun(name='foot:%s' % key, text=word, x=b + t[0], y=fy, font=fc['medium']['role'], size_pt=7.0,
                             color=ink))
        wd = ps.width_mm(word, fc['medium'], 7.0)
        rows.append({'lang': 'en', 'field': 'foot', 'text': word, 'size_pt': 7.0, 'width_mm': round(wd, 2),
                     'room_mm': 14.0, 'fits': wd <= 14.0, 'shrunk': False, 'source': 'the write-in field\'s label',
                     'review': None, 'direction': 'left to right', 'overflows': False,
                     'box_mm': [round(b + t[0], 3), round(fy - 7.0 * MM_PER_PT, 3), round(b + t[0] + 54.0, 3),
                                round(fy + 0.8, 3)]})
        nodes.append(Rect(name='foot:%s line' % key, x=b + t[0] + 14.0, y=fy + 0.6, w=40.0, h=0.15,
                          fill=SolidFill(color=ink)))
    ex, ey = b + t[2] - ps.EAN_MM[0], b + t[3] - ps.EAN_MM[1]
    nodes.append(Rect(name='EAN-13 placeholder frame (no number)', x=ex, y=ey, w=ps.EAN_MM[0], h=ps.EAN_MM[1],
                      stroke=Stroke(color=ink, width_mm=0.15)))
    # the frame prints empty: no number is invented and no label prints in it (the eye's round 0)
    doc = Document(page_w=SIZE_MM[0] + 2 * b, page_h=SIZE_MM[1] + 2 * b, title='Ẓilāl back sticker',
                   metadata={'typography_surface': SURFACE, 'logical_text/1.0': True},
                   root=Group(name='STICKER', role='label', children=nodes))
    return doc, rows


# --- the checks, each read from the files -----------------------------------------------------------------------------

def file_inks(pdf_path):
    """Every ink page 1 prints: each text span (its box and colour) and each filled or stroked path (its box and
    colour), in pt as the file draws them."""
    import fitz
    out = []
    with fitz.open(str(pdf_path)) as d:
        page = d[0]
        for block in page.get_text('dict')['blocks']:
            if block['type'] != 0:
                continue
            for line in block['lines']:
                for span in line['spans']:
                    if span['text'].strip():
                        out.append({'what': 'text', 'text': span['text'], 'bbox_pt': [round(v, 3) for v in span['bbox']],
                                    'ink': '#%06X' % span['color']})
        for dr in page.get_drawings():
            colour = dr['fill']
            how = 'fill'
            if colour is None:
                colour, how = dr['color'], 'stroke'
            if colour is None:
                continue
            out.append({'what': 'path (%s)' % how, 'text': None, 'bbox_pt': [round(v, 3) for v in dr['rect']],
                        'ink': hex_of([c * 255.0 for c in colour[:3]])})
    return out


def contrast_rows(elements, ground, px_per_mm):
    """Each ink against the ground beneath it: the ground read over the element's box grown 0.3 mm on ``ground`` (an
    RGB array at ``px_per_mm`` over the same page), the ratio against its median and against its lightest pixel (the
    99.5th luminance percentile — a stone or vein under a line shows there). Holds when the worst is ≥ 7 : 1."""
    lin = ground.astype(np.float64) / 255.0
    lin = np.where(lin <= 0.03928, lin / 12.92, ((lin + 0.055) / 1.055) ** 2.4)
    lum = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]
    grow = CONTRAST_GROW_MM * px_per_mm
    h, w = lum.shape
    rows = []
    for e in elements:
        x0, y0, x1, y1 = (v * px_per_mm * lm.MM_PER_INCH / 72.0 for v in e['bbox_pt'])
        c0, r0 = max(int(math.floor(x0 - grow)), 0), max(int(math.floor(y0 - grow)), 0)
        c1, r1 = min(int(math.ceil(x1 + grow)), w), min(int(math.ceil(y1 + grow)), h)
        if c1 <= c0 or r1 <= r0:
            raise ValueError('the ink %r lies off the ground read (%s)' % (e['text'], e['bbox_pt']))
        patch = lum[r0:r1, c0:c1]
        rgb = ground[r0:r1, c0:c1].reshape(-1, 3)
        worst = rgb[int(np.argmin(np.abs(patch.ravel() - np.percentile(patch, CONTRAST_WORST_PCT))))]
        median = np.median(rgb, axis=0)
        ratio_worst = lm.contrast_ratio(e['ink'], hex_of(worst))
        rows.append(dict(e, ground_median=hex_of(median), ground_worst=hex_of(worst),
                         ratio_median=round(lm.contrast_ratio(e['ink'], hex_of(median)), 2),
                         ratio_worst=round(ratio_worst, 2), holds=bool(ratio_worst >= CONTRAST_MIN)))
    return rows


def contrast_by_ink(rows):
    """The contrast rows gathered per ink: how many elements, the worst and the median ratio, and whether all hold."""
    out = {}
    for r in rows:
        if r['ink'] not in out:
            out[r['ink']] = []
        out[r['ink']].append(r)
    return {ink: {'elements': len(rs), 'worst_ratio': min(x['ratio_worst'] for x in rs),
                  'median_ratio': float(np.median([x['ratio_median'] for x in rs])),
                  'holds': all(x['holds'] for x in rs)} for ink, rs in out.items()}


def render(pdf_path, dpi, clip_pt):
    """A page 1 rendered (RGB array) at ``dpi``, over ``clip_pt`` (a fitz.Rect, or None for the page)."""
    import fitz
    with fitz.open(str(pdf_path)) as d:
        pix = d[0].get_pixmap(dpi=int(dpi), clip=clip_pt, alpha=False)
        return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3].copy()


def flat_zone_check(ground_render, flat_hex, box_mm, px_per_mm):
    """The copy zone is flat: every ground pixel under the copy's area (``box_mm``, page mm) within ΔE00 0.5 of the flat
    colour, read on the ground file's render."""
    x0, y0, x1, y1 = (int(round(v * px_per_mm)) for v in box_mm)
    patch = ground_render[y0:y1, x0:x1]
    lab = lm.srgb_to_lab(patch)
    de = lm.delta_e00(lab, np.broadcast_to(lab_of_hex(flat_hex), lab.shape))
    return {'box_mm': [round(v, 3) for v in box_mm], 'de00_max': round(float(de.max()), 3),
            'pixels_off': int((de > FLAT_DE_MAX).sum()), 'holds': bool(de.max() <= FLAT_DE_MAX),
            'rule': 'the copy zone flat: no ground pixel under the copy off the flat colour by over ΔE00 %.1f' % FLAT_DE_MAX}


def opening_on_separator(rows, spans):
    """D-D11-6: the drawn lines and the file's spans that open on "·" (none may)."""
    lines = [r['text'] for r in rows if r['text'].lstrip().startswith(SEPARATOR)]
    opened = [sp for sp in spans if sp.lstrip().startswith(SEPARATOR)]
    return {'lines_opening_on_it': lines, 'spans_opening_on_it': opened, 'holds': not lines and not opened}


def palette_word(spans_by_lang):
    """D-D11-6: باليت everywhere for palette, never لوحة — counted in every language's own spans."""
    rows = {lang: {'never': sum(sp.count(PALETTE_AR_NEVER) for sp in spans),
                   'palette': sum(sp.count(PALETTE_AR) for sp in spans)} for lang, spans in spans_by_lang.items()}
    return {'per_language': rows, 'holds': all(r['never'] == 0 for r in rows.values()),
            'arabic_says_baliyt': bool('ar' in rows and rows['ar']['palette'] > 0)}


def spans_by_lang(pdf_path, names):
    """The file's ActualText spans, each paired with the drawn node it belongs to ('<lang>:<field>'), by language."""
    spans = lm.actual_texts(pdf_path, 0)
    if len(spans) != len(names):
        raise ValueError('%d ActualText spans for %d named nodes' % (len(spans), len(names)))
    out = {}
    for n, sp in zip(names, spans):
        lang = n.split(':')[0]
        if lang not in out:
            out[lang] = []
        out[lang].append(sp)
    return out


def verbatim_per_language(checked, langs):
    """INCI and the ℮ line verbatim in EVERY language, each read from that language's own spans (copy_check's rows):
    per language, per element — so no column stands for another."""
    rows = {lang: {field: any(r['found'] for r in checked['rows'] if r['lang'] == lang and r['field'] == field)
                   for field in ('ingredients', 'net')} for lang in langs}
    return {'per_language': rows, 'holds': all(all(v.values()) for v in rows.values())}


def floor_and_drops(fitted, rows, checked):
    """Type shrinks evenly to the 5 pt floor and never drops: one body size for every body line, none under the floor,
    no section without its spans (copy_check's dropped), and every line that overflows its column listed by itself."""
    body = [r for r in rows if r['field'] not in ('product name', 'net', 'foot')]
    sizes = sorted({r['size_pt'] for r in body})
    overflow = [{k: r[k] for k in ('lang', 'field', 'text', 'size_pt')} for r in rows if r['overflows']]
    return {'body_sizes_pt': sizes, 'one_body_size': len(sizes) == 1, 'floor_pt': ps.BODY_FLOOR_PT,
            'above_the_floor': bool(min(r['size_pt'] for r in rows) >= ps.BODY_FLOOR_PT - 1e-9),
            'fits': fitted['fits'], 'dropped': checked['dropped'], 'overflow': overflow,
            'holds': bool(len(sizes) == 1 and not checked['dropped']
                          and min(r['size_pt'] for r in rows) >= ps.BODY_FLOOR_PT - 1e-9)}


def arabic_face_decision(rows, fc):
    """The lid's Arabic face stands unless palette_sticker's measured proofs require its own (Tajawal PF Medium): the
    per-line test (``palette_sticker.arabic_proofs``) read for both; the sticker's own face is required only when it
    holds every Arabic line and the lid's does not."""
    lid = ps.arabic_proofs(rows, fc)
    own = ps.arabic_proofs(rows, {'arabic': palette_sticker_arabic()})
    own_all = all(p['faithful'] for p in own)
    lid_all = all(p['faithful'] for p in lid)
    required = bool(own_all and not lid_all)
    face = fc['arabic']['label']
    if required:
        face = palette_sticker_arabic()['label']
    return {'face': face, 'palette_stickers_face_required': required,
            'lid_face': {'label': fc['arabic']['label'], 'faithful': sum(1 for p in lid if p['faithful']),
                         'lines': len(lid), 'iou': [p['iou'] for p in lid]},
            'palette_sticker_face': {'label': palette_sticker_arabic()['label'],
                                     'faithful': sum(1 for p in own if p['faithful']), 'lines': len(own),
                                     'iou': [p['iou'] for p in own]},
            'rule': 'the lid master\'s Arabic face stands unless palette_sticker\'s face holds every line where the '
                    'lid\'s does not'}, lid


# --- the build ---------------------------------------------------------------------------------------------------------

def window_px(k):
    """The sticker's page (die plus bleed) on the plate's grid: the lid less (4 − 2) mm all round, whole pixels that
    cover it (floor at the top-left, ceil at the bottom-right)."""
    x0 = (LID_INSET_MM[0] - BLEED_MM) * k
    y0 = (LID_INSET_MM[1] - BLEED_MM) * k
    x1 = (LID_INSET_MM[0] + SIZE_MM[0] + BLEED_MM) * k
    y1 = (LID_INSET_MM[1] + SIZE_MM[1] + BLEED_MM) * k
    return int(math.floor(x0)), int(math.floor(y0)), int(math.ceil(x1)), int(math.ceil(y1))


def guides(page, trim, zone, support, oc):
    """Page 2 and the guides layer: the die (182 × 112, r 2), the safe line (3.5 mm) and the flat zone's edge."""
    import fitz
    page.draw_rect(trim, color=(0.85, 0, 0.55), width=0.25, radius=lm.pt(ps.CORNER_MM) / min(trim.width, trim.height),
                   oc=oc)
    safe = fitz.Rect(trim.x0 + lm.pt(ps.SAFE_MM), trim.y0 + lm.pt(ps.SAFE_MM), trim.x1 - lm.pt(ps.SAFE_MM),
                     trim.y1 - lm.pt(ps.SAFE_MM))
    page.draw_rect(safe, color=(0, 0.6, 0.9), width=0.25, dashes='[1 2] 0', oc=oc)
    page.draw_rect(zone, color=(0.9, 0.5, 0), width=0.25, dashes='[2 2] 0', oc=oc,
                   radius=lm.pt(ZONE_RADIUS_MM) / min(zone.width, zone.height))
    page.insert_font(fontname='support', fontfile=str(support))
    page.insert_text((trim.x0 + lm.pt(1), trim.y1 - lm.pt(1)), 'DIE 182 x 112 mm, corners r 2 mm - BLEED 2 mm - SAFE '
                     '3.5 mm - FLAT ZONE (orange)', fontname='support', fontsize=5, color=(0.85, 0, 0.55), oc=oc)


def build(out_dir, *, claims):
    """§2's sticker at $0 (the translations already made): engine/ (the ground, the engine's documents), sticker.pdf (page
    1 the artwork with its 2 mm bleed, page 2 the die, the safe line and the flat zone), sticker.ai (layers: ground,
    type, guides — the type live, its faces embedded), sticker-flat.png at 300 PPI, fit-report.json, finish-proof.png and
    the finish sheet, arabic-engine-vs-face.png, sticker.json. ``claims``: Brand.claims rows (the database's when None)."""
    import fitz
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Document, Group, Image as GImage
    out = Path(out_dir)
    eng = out / 'engine'
    eng.mkdir(parents=True, exist_ok=True)
    if claims is None:
        claims = ps.house_claims()
    master = json.loads(MASTER.read_text(encoding='utf-8'))
    ink = master['type']['inks']['eyeshadow']
    translations = json.loads(ps.TRANSLATIONS.read_text(encoding='utf-8'))
    fc = faces()
    blocks = glue_ci(ps.corrected_copy(translations, claims))
    net = ps.net_line(fc)
    lay = layout()
    fitted = fit(blocks, fc, net, lay)

    # the ground: the plate's window at 1 : 1, the letters filled outside the zone, the flat zone over the middle
    plate, plate_rec = plate_source()
    k = plate.shape[1] / zm.LID_MM[0]
    flat_hex, flat_rec = ground_colour(plate)
    wx0, wy0, wx1, wy1 = window_px(k)
    window = plate[wy0:wy1, wx0:wx1]
    letters = letter_mask(plate)[wy0:wy1, wx0:wx1]
    shift = (LID_INSET_MM[0] - BLEED_MM, LID_INSET_MM[1] - BLEED_MM)       # page mm → lid mm
    z = lay['zone_mm']
    zone_px = tuple((v + BLEED_MM + shift[i % 2]) * k - (wx0, wy0)[i % 2] for i, v in enumerate(z))
    ground, alpha, filled = compose(window, letters, zone_px, ZONE_RADIUS_MM * k, flat_hex)
    ground, refilled = refill_bottom(ground, alpha, plate, (wx0, wy0), k, flat_hex)
    ground_png = eng / 'ground.png'
    Image.fromarray(ground).save(ground_png)
    box_mm = (wx0 / k - shift[0], wy0 / k - shift[1], (wx1 - wx0) / k, (wy1 - wy0) / k)
    lettered = letters_check(ground, window, letters, alpha)
    stones = border_stones(ground, alpha, flat_hex, k, (wx0 / k, wy0 / k), 'none')

    # the engine's documents: the whole sticker, the ground alone, the type alone
    doc, rows = document(blocks, fitted, fc, ink, net, lay, {'png': ground_png, 'box_mm': box_mm})
    type_doc, _ = document(blocks, fitted, fc, ink, net, lay, None)
    page_w, page_h = SIZE_MM[0] + 2 * BLEED_MM, SIZE_MM[1] + 2 * BLEED_MM
    ground_doc = Document(page_w=page_w, page_h=page_h, title='Ẓilāl back sticker: ground',
                          metadata={'typography_surface': SURFACE},
                          root=Group(name='GROUND', role='background', children=[
                              GImage(name='ground', src=str(ground_png), x=box_mm[0], y=box_mm[1], w=box_mm[2],
                                     h=box_mm[3])]))
    art, type_ai, ground_ai = eng / 'sticker-engine.ai', eng / 'sticker-type.ai', eng / 'sticker-ground.ai'
    usage = {}
    emit_pdf_ai(doc, str(art), usage_out=usage)
    emit_pdf_ai(type_doc, str(type_ai))
    emit_pdf_ai(ground_doc, str(ground_ai))

    w, h = SIZE_MM
    trim = fitz.Rect(lm.pt(BLEED_MM), lm.pt(BLEED_MM), lm.pt(BLEED_MM + w), lm.pt(BLEED_MM + h))
    zone_rect = fitz.Rect(*(lm.pt(BLEED_MM + v) for v in z))
    support = fc['medium']['path']
    src = fitz.open(str(art))
    pdf = fitz.open()
    p = pdf.new_page(width=src[0].rect.width, height=src[0].rect.height)
    p.show_pdf_page(p.rect, src, 0)
    p = pdf.new_page(width=src[0].rect.width, height=src[0].rect.height)
    guides(p, trim, zone_rect, support, 0)
    for page in pdf:
        page.set_bleedbox(page.rect)
        page.set_trimbox(trim)
    pdf.set_page_labels([{'startpage': 0, 'prefix': '1 artwork ', 'style': ''},
                         {'startpage': 1, 'prefix': '2 die, safe line and flat zone ', 'style': ''}])
    pdf.set_metadata({'title': 'Ẓilāl back sticker', 'creator': SURFACE})
    lm.tag_srgb(pdf)
    pdf.save(str(out / 'sticker.pdf'), garbage=3, deflate=True)
    pdf.close()
    src.close()
    ai = fitz.open()
    ocg = {name: ai.add_ocg(name, on=True) for name in ('ground', 'type', 'guides')}
    p = ai.new_page(width=lm.pt(page_w), height=lm.pt(page_h))
    with fitz.open(str(ground_ai)) as g, fitz.open(str(type_ai)) as ty:
        p.show_pdf_page(p.rect, g, 0, oc=ocg['ground'])
        p.show_pdf_page(p.rect, ty, 0, oc=ocg['type'])
    guides(p, trim, zone_rect, support, ocg['guides'])
    p.set_bleedbox(p.rect)
    p.set_trimbox(trim)
    ai.set_metadata({'title': 'Ẓilāl back sticker (layers)', 'creator': SURFACE})
    lm.tag_srgb(ai)
    ai.save(str(out / 'sticker.ai'), garbage=3, deflate=True)
    ai.close()
    with fitz.open(str(art)) as d:
        pix = d[0].get_pixmap(dpi=READ_DPI, clip=trim, alpha=False)
        pix.set_dpi(READ_DPI, READ_DPI)
        pix.save(str(out / 'sticker-flat.png'))

    # the checks, read from the files
    names = ps.drawn_names(doc)
    checked = ps.copy_check(art, blocks, names)
    corrected = ps.corrected_report(art, doc, rows, blocks, net, ink)
    by_lang = spans_by_lang(art, names)
    ppm = READ_DPI / lm.MM_PER_INCH
    ground_render = render(ground_ai, READ_DPI, None)
    contrast = contrast_rows(file_inks(art), ground_render, ppm)
    t = lay['type_mm']
    flat_check = flat_zone_check(ground_render, flat_hex, tuple(BLEED_MM + v for v in t), ppm)
    face_decision, proofs = arabic_face_decision(rows, fc)
    shown = ps.arabic_side_by_side(proofs, fc, out / 'arabic-engine-vs-face.png')
    fonts = {}
    with fitz.open(str(out / 'sticker.pdf')) as d:
        for f in d[0].get_fonts(full=True):
            fonts[f[3]] = {'embedded': f[1] not in ('', 'n/a'), 'type': f[2]}
    with fitz.open(str(out / 'sticker.ai')) as d:
        layers = [o['name'] for o in d.get_ocgs().values()]
    floor = floor_and_drops(fitted, rows, checked)
    opening = opening_on_separator(rows, lm.actual_texts(art, 0))
    word = palette_word(by_lang)
    verbatim = verbatim_per_language(checked, sorted(blocks))
    signs = corrected['net']

    shutil_copy(out / 'sticker-flat.png', out / 'finish-proof.png')
    plates = [{'plate': 'print', 'what': 'the lid\'s plate at 1 : 1 (its stones where the lid has them) with a flat zone '
                                        'in the lid\'s indigo %s; the copy live in %s and %s, cream %s' % (
                                            flat_hex, fc['medium']['label'], fc['arabic']['label'], ink)},
              {'plate': 'die', 'what': '182 × 112 mm, corners r 2 mm (page 2)'},
              {'plate': 'foil', 'what': 'none'}, {'plate': 'relief', 'what': 'none'}]
    zo.finish_sheet('the base sticker', out / 'sticker-flat.png', plates, out)

    report = {
        'schema': ps.SCHEMA + '+day11-zilal', 'size_mm': list(SIZE_MM), 'bleed_mm': BLEED_MM, 'safe_mm': ps.SAFE_MM,
        'type_inset_mm': TYPE_INSET_MM, 'zone_mm': [round(v, 3) for v in z], 'ground': flat_hex, 'ink': ink,
        'faces': {kk: v['label'] for kk, v in fc.items()},
        'body': {'size_pt': fitted['size_pt'], 'start_pt': ps.BODY_START_PT, 'floor_pt': ps.BODY_FLOOR_PT,
                 'fits': fitted['fits'], 'column_mm': round(fitted['column_mm'], 2),
                 'room_mm': round(fitted['room_mm'], 2),
                 'heights_mm': {kk: round(v, 2) for kk, v in fitted['heights_mm'].items()}},
        'smallest_pt': min(r['size_pt'] for r in rows), 'lines': rows, 'dropped': checked['dropped'],
        'moved': checked['moved'], 'overflow': floor['overflow'],
        'for_review': [r for r in rows if r['review'] == 'machine draft — for review'],
        'owner_to_confirm': corrected['owner_to_confirm'], 'copy': checked}
    lm.write_json(out / 'fit-report.json', report)
    record = {
        'schema': SCHEMA, 'surface': 'the base sticker (D-D11-4)',
        'rule': 'D-D11-4: "a designed ground — the indigo field with a floated-stone border, the copy zone flat for '
                'contrast (≥ 7 : 1); the copy EN / ES / AR with his corrected lines (D-D11-6); INCI and ℮ verbatim in '
                'every language"',
        'sources': {'plate': plate_rec, 'master': {'file': lm.rel(MASTER), 'sha256': lm.sha256(MASTER)},
                    'pick': {'file': lm.rel(zm.MASTER_PICK), 'sha256': lm.sha256(zm.MASTER_PICK),
                             'used_for': 'the letters\' masks only (element_mask_up)'},
                    'translations': {'file': lm.rel(ps.TRANSLATIONS), 'sha256': lm.sha256(ps.TRANSLATIONS)},
                    'claims': {'read': 'Brand.claims (BBROSE)', 'rows': claims}},
        'ground': {'method': 'the lid\'s plate cut at the sticker\'s frame (the lid less 4 mm, plus the 2 mm bleed), '
                             '1 : 1 — never scaled, never redrawn; the letters outside the zone filled (Telea); the flat '
                             'zone in the plate\'s own indigo laid over the middle',
                   'window_px': [wx0, wy0, wx1, wy1], 'window_lid_mm': [round(v / k, 3) for v in (wx0, wy0, wx1, wy1)],
                   'scale': 1.0, 'px_per_mm': round(k, 6), 'ppi': round(k * lm.MM_PER_INCH, 1),
                   'placed_page_mm': [round(v, 4) for v in box_mm], 'file': lm.rel(ground_png),
                   'sha256': lm.sha256(ground_png), 'flat': flat_rec,
                   'zone': {'mm': [round(v, 3) for v in z], 'radius_mm': ZONE_RADIUS_MM, 'pad_mm': ZONE_PAD_MM,
                            'type_mm': [round(v, 3) for v in t]},
                   'letters_filled_px': int(filled.sum()), 'letters': lettered, 'bottom_refill': refilled,
                   'border': stones,
                   'flat_zone': flat_check},
        'faces': {'latin': fc['medium']['label'], 'arabic': fc['arabic']['label'], 'decision': face_decision,
                  'why': 'the lid master\'s faces (master.json type.faces): its one Latin face for every Latin line '
                         '(heads, body, title, ℮ line) and its Arabic face; palette_sticker\'s own Arabic face is not '
                         'required by the measured proofs (%d of %d lines hold in the lid\'s, %d of %d in '
                         'palette_sticker\'s)' % (face_decision['lid_face']['faithful'],
                                                  face_decision['lid_face']['lines'],
                                                  face_decision['palette_sticker_face']['faithful'],
                                                  face_decision['palette_sticker_face']['lines'])},
        'arabic_lines': proofs, 'arabic_shown': shown,
        'contrast': {'rule': 'D-D11-4: every ink on the copy zone ≥ 7 : 1, read from the files (the inks from the '
                             'artwork\'s spans and paths, the ground from the ground file rendered at %d PPI)' % READ_DPI,
                     'per_ink': contrast_by_ink(contrast), 'elements': contrast,
                     'holds': all(r['holds'] for r in contrast)},
        'copy': {'per_language': checked['rows'], 'all_found': checked['all_found'], 'verbatim': verbatim,
                 'corrected_lines': corrected['corrected_lines'], 'arabic_claims': corrected['arabic_claims'],
                 'owner_to_confirm': corrected['owner_to_confirm'], 'palette_word': word, 'separator': opening,
                 'floor_and_drops': floor},
        'net': signs,
        'fit': {'size_pt': fitted['size_pt'], 'fits': fitted['fits'], 'column_mm': round(fitted['column_mm'], 2),
                'room_mm': round(fitted['room_mm'], 2), 'overflow': floor['overflow']},
        'fonts': fonts, 'fonts_embedded': all(f['embedded'] for n, f in fonts.items() if n != 'Helvetica'),
        'layers': layers,
        'finish': {'proof': lm.rel(out / 'finish-proof.png'), 'is': 'the print flat itself: the sticker carries no foil '
                                                                     'or relief', 'plates': plates},
        'files': {n: {'file': lm.rel(out / n), 'sha256': lm.sha256(out / n)} for n in (
            'sticker.pdf', 'sticker.ai', 'sticker-flat.png', 'fit-report.json', 'finish-proof.png', 'finish-sheet.pdf',
            'finish-sheet.png')},
        'engine': {n: lm.rel(eng / n) for n in ('sticker-engine.ai', 'sticker-type.ai', 'sticker-ground.ai',
                                                'ground.png')},
        'notes': ['the copy machinery is palette_sticker\'s (corrected_copy, house claims, wrap, the ℮ line at its cap '
                  'height, copy_check, corrected_report) set inside the zone; Day 10\'s title rule is left out (the '
                  'lid draws no rule)',
                  'batch and expiry are write-in fields; the EAN-13 frame holds no number (none is invented)',
                  'the warnings and "Made in" lines stand as Day 10 printed them (machine drafts, for review)'],
        'usage': usage}
    record['widows'] = widows_in(rows)
    ar_inci = [r for r in blocks['ar'] if r['field'] == 'ingredients'][0]
    inci_w, _ = inci_wrap(ar_inci, fitted['column_mm'], fitted['size_pt'], fc)
    record['inci_wrap'] = {'column_mm': fitted['column_mm'], 'wrap_mm': inci_w,
                           'narrowed_mm': round(fitted['column_mm'] - inci_w, 3),
                           'rule': 'the owner\'s answer of 24 October, 4: the lone "CI 77007." fixed by the Arabic '
                                   'column\'s width only, the INCI verbatim, $0'}
    holds = {'contrast': record['contrast']['holds'], 'letters': lettered['holds'], 'flat_zone': flat_check['holds'],
             'no_widow': not record['widows']['found'],
             'copy_found': checked['all_found'], 'inci_and_net_every_language': verbatim['holds'],
             'corrected_lines': corrected['corrected_lines']['all_verbatim'], 'palette_word': word['holds'],
             'separator': opening['holds'], 'net_sign': signs['signs_hold'], 'floor_and_drops': floor['holds'],
             'fonts_embedded': record['fonts_embedded']}
    record['holds'] = holds
    record['all_hold'] = all(holds.values())
    lm.write_json(out / 'sticker.json', record)
    return record


def shutil_copy(src, dst):
    import shutil
    shutil.copyfile(src, dst)
    return dst


# --- the eye (D-D11-4: the lid as the language, the surface fitted, then 1 : 1 crops) -----------------------------------

CORNER_CROP_MM = (46.0, 32.0)           # a corner of the border: 46 × 32 mm at 300 PPI (543 × 378 px)


def crop_from_pdf(pdf_path, box_mm, dpi, path):
    """A crop of page 1 rendered at ``dpi`` over ``box_mm`` (page mm), saved and checked under the eye's limits."""
    import fitz
    clip = fitz.Rect(*(lm.pt(v) for v in box_mm))
    img = render(pdf_path, dpi, clip)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(path, dpi=(dpi, dpi))
    lm._image_block(path)
    return path, img


def ink_px(img, flat_hex):
    """The type's pixels in a crop: far from the flat ground (ΔE00 > 30) and light (L* > 60)."""
    lab = lm.srgb_to_lab(img)
    de = lm.delta_e00(lab, np.broadcast_to(lab_of_hex(flat_hex), lab.shape))
    return int(((de > 30.0) & (lab[..., 0] > 60.0)).sum())


def stone_share(img, flat_hex):
    lab = lm.srgb_to_lab(img)
    return float((lm.delta_e00(lab, np.broadcast_to(lab_of_hex(flat_hex), lab.shape)) > OFF_GROUND_DE).mean())


def look_crops(record, out):
    """The eye's crops, each rendered from sticker.pdf over the place the record says the thing stands: the border at its
    top-left and bottom-right corners (300 PPI), each column's head (its first lines) and its claims, and the ℮ lines
    (600 PPI). A crop of the copy must hold its type and a crop of the border its stones, or it is refused."""
    pdf = zm.REPO / record['files']['sticker.pdf']['file']
    flat = record['ground']['flat']['hex']
    lines = json.loads((zm.REPO / record['files']['fit-report.json']['file']).read_text(encoding='utf-8'))['lines']
    page_w, page_h = SIZE_MM[0] + 2 * BLEED_MM, SIZE_MM[1] + 2 * BLEED_MM
    made = []
    cw, ch = CORNER_CROP_MM
    for name, box in (('corner-top-left', (0.0, 0.0, cw, ch)),
                      ('corner-bottom-right', (page_w - cw, page_h - ch, page_w, page_h))):
        path, img = crop_from_pdf(pdf, box, READ_DPI, out / 'crops' / ('sticker-%s.png' % name))
        share = stone_share(img, flat)
        if share < CROP_STONE_MIN:
            raise ValueError('the %s crop shows %.0f %% stone: it does not render the border' % (name, 100 * share))
        made.append((path, 'the border at its %s corner (1 : 1, 300 PPI, %g × %g mm from the bleed\'s edge): the lid\'s '
                           'stones at their own place and size, the flat zone\'s edge' % (name[7:].replace('-', ' '),
                                                                                         cw, ch)))
    lang_names = {'en': 'English', 'es': 'Spanish', 'ar': 'Arabic'}
    for lang in ('en', 'es', 'ar'):
        mine = [r for r in lines if r['lang'] == lang and r['field'] not in ('product name', 'net', 'foot')]
        heads = mine[:4]
        claims = [r for r in mine if r['field'] == 'claims']
        for part, rows_ in (('head', heads), ('claims', claims)):
            x0 = min(r['box_mm'][0] for r in rows_) - 1.0
            y0 = min(r['box_mm'][1] for r in rows_) - 1.0
            x1 = max(r['box_mm'][2] for r in rows_) + 1.0
            y1 = max(r['box_mm'][3] for r in rows_) + 1.0
            path, img = crop_from_pdf(pdf, (x0, y0, x1, y1), CROP_DPI, out / 'crops' / ('sticker-%s-%s.png' % (lang, part)))
            if ink_px(img, flat) < CROP_INK_MIN_PX:
                raise ValueError('the %s %s crop holds no type: it does not render the thing judged' % (lang, part))
            what = {'head': 'its first lines (the description under its head)', 'claims': 'the four claims'}[part]
            made.append((path, 'the %s column, %s (1 : 1, %d PPI)' % (lang_names[lang], what, CROP_DPI)))
    nets = [r for r in lines if r['field'] == 'net']
    for r in nets:
        x0, y0, x1, y1 = r['box_mm']
        path, img = crop_from_pdf(pdf, (x0 - 1.0, y0 - 1.0, x1 + 1.0, y1 + 1.0), CROP_DPI,
                                  out / 'crops' / ('sticker-net-%s.png' % r['lang']))
        if ink_px(img, flat) < CROP_INK_MIN_PX:
            raise ValueError('the %s ℮ crop holds no type' % r['lang'])
        made.append((path, 'the %s column\'s ℮ line, "27 g ℮ 0.95 oz" (1 : 1, %d PPI)' % (lang_names[r['lang']],
                                                                                          CROP_DPI)))
    return made


def sticker_look(record, call, round_no, label=None):
    """The sticker's eye round (D-D11-4): the lid master first (the language), the sticker's flat fitted, then 1 : 1 crops
    — the border at two corners, each column's head and claims, the ℮ lines — against the owner's rule and what the
    composition allows; anything else is a defect. Every picture is made and size-checked before ``call`` is reached."""
    out = OUT
    flat = zm.REPO / record['files']['sticker-flat.png']['file']
    images = [zo.lid_language(out),
              (zo.fitted(flat, out / 'crops' / 'sticker-fitted.png'), 'THE BASE STICKER\'s flat (182 × 112 mm, the die; '
                                                                      'fitted)')]
    images += look_crops(record, out)
    c = record['contrast']['per_ink']
    text = ('THE BASE STICKER GATE (Day 11, D-D11-4). The sticker under the palette, composed by our engine from the '
            'lid\'s own assets (no picture made for it). THE OWNER\'S RULE: "the base sticker (182 × 112): a designed '
            'ground — the indigo field with a floated-stone border, the copy zone flat for contrast (≥ 7 : 1); the copy '
            'EN / ES / AR with his corrected lines; INCI and ℮ verbatim in every language"; the lid\'s idea: %s. '
            'Images: %s.\n\nALLOWED (the composition): the border is the lid\'s own plate cut at the sticker\'s frame '
            '(the lid less 4 mm all round) at 1 : 1, so its stones stand exactly where and as large as on the lid — two '
            'drifts, at the top left and the bottom right, the other corners calm indigo, as on the lid; the flat zone '
            'in the lid\'s own indigo %s over the middle (rounded 3 mm), its edge crossing the stones; where the lid\'s '
            'name would show at the left edge it is filled from the marbling around; the copy in the lid\'s faces (%s '
            'for Latin, %s for Arabic) in the lid\'s cream %s at one body size %.2f pt (contrast read from the file: '
            '%s); the ℮ at the line\'s cap height (≥ 3 mm); batch and expiry as write-in fields, the EAN-13 frame '
            'empty (no number is invented); the Arabic unvowelled. ANYTHING ELSE is a defect: a stone redrawn, '
            'stretched or of a colour not the lid\'s; any letter, logo or gold lettering in the border; a seam or '
            'mirror line; a stone or vein under the copy; type illegible, crowded or misaligned; a line opening on '
            '"·"; لوحة for palette; a motif, rule, frame or colour outside the lid\'s language. As a senior packaging '
            'designer, judge every image — does the sticker read as part of the same object as the lid, and as '
            'considered as the front? — and list every defect with its place, severity and the smallest repair. '
            'Answer in JSON.' % (
                zo.IDEA, '; '.join('%d %s' % (i + 1, w_) for i, (_, w_) in enumerate(images)),
                record['ground']['flat']['hex'], record['faces']['latin'], record['faces']['arabic'],
                json.loads((zm.REPO / record['files']['fit-report.json']['file']).read_text(encoding='utf-8'))['ink'],
                record['fit']['size_pt'], ', '.join('%s %.1f : 1 at worst' % (ink, v['worst_ratio'])
                                                    for ink, v in c.items())))
    if round_no >= 1:
        refill = record['ground']['bottom_refill']
        text += ('\n\nREPAIR 1 (after round 0 named five defects): (1) the Spanish column had no head — no Spanish name '
                 'of the product was given by the owner and none is invented, so the two names he gave (English, Arabic) '
                 'now stand as ONE title centred over the three columns, and every column opens on its description; (2) '
                 '"CI" broken from "77007." — every colour index now travels with its number in all three columns (the '
                 'words unchanged); (3) the Arabic description ended on a one-word line — no paragraph ends on one word '
                 'now (a claims line still wraps claim by claim, so the one-word claim "Long-wear" stays whole); (4) the '
                 'dark smear in the bottom border — it was the lid\'s own bottom row (18 SHADES, the ℮ line) cleaned out '
                 'of the lid\'s plate by inpainting; that footprint alone (%d px) now carries the plate\'s own indigo '
                 'grain from the same rows (%.1f mm along), laid on the tone of the ground around it, every stone and '
                 'vein untouched; (5) the EAN-13 frame now prints empty, no label. Judge whether each is answered and '
                 'whether anything new is wrong.' % (refill['filled_px'], refill['shift_mm']))
    return zo.surface_look(out, 'sticker', images, text, call, round_no, label)


class DryRun(RuntimeError):
    """The stand-in call's refusal: raised before anything is paid."""


def stand_in(seen):
    """A stand-in for the eye's paid call that refuses before paying: it records what it was handed (the images' sizes
    and the text's length) in ``seen`` and raises DryRun."""
    def call(operation, content, schema):
        import base64
        import io
        sizes = []
        for block in content:
            if block['type'] == 'image':
                with Image.open(io.BytesIO(base64.b64decode(block['source']['data']))) as im:
                    sizes.append(list(im.size))
        seen.update(operation=operation, images=sizes, text_chars=sum(len(b['text']) for b in content
                                                                     if b['type'] == 'text'),
                    schema_keys=sorted(schema['properties']))
        raise DryRun('dry pre-check: the eye is not called ($0)')
    return call


def dry_precheck(look, record):
    """A $0 pre-check of a look's pictures: the look run with a stand-in call that refuses before paying, so every picture
    is made and checked under the eye's limits (``lid_master._image_block`` refuses any the API would resample) and no
    eye record is written. Returns what the call would have been handed."""
    seen = {}
    try:
        look(record, stand_in(seen), 0, 'dry-precheck')
    except DryRun:
        return dict(seen, refused_before_paying=True,
                    within_limits=all(max(s) <= lm.EYE_IMAGE_EDGE_MAX and s[0] * s[1] <= lm.EYE_PIXELS_MAX
                                      for s in seen['images']))
    raise RuntimeError('the stand-in call was never reached: the look did not get to its call')


def gate_record(out=None):
    """The sticker's gate as the eye's rounds say it (eye-r0.json, eye-r1.json), merged into sticker.json under 'gate':
    each round's verdict and defects, what stays open, and where a measured check and the eye disagree (the no-widow
    count reads "CI 77007." as two words; the eye reads it as one item alone on its line). Never changes the artwork."""
    if out is None:
        out = OUT
    rounds = []
    for path in sorted(Path(out).glob('eye-r*.json')):
        rec = json.loads(path.read_text(encoding='utf-8'))
        rounds.append({'round': rec['round'], 'file': lm.rel(path), 'holds': rec['holds'],
                       'defects': [{k: d[k] for k in ('where', 'what', 'severity')} for d in rec['defects']]})
    last = rounds[-1]
    record = json.loads((Path(out) / 'sticker.json').read_text(encoding='utf-8'))
    open_ = last['defects']
    after = None
    if 'inci_wrap' in record and not record['widows']['found']:
        after = {'fixed': [d['what'] for d in open_], 'how': record['inci_wrap'],
                 'said': 'fixed after the gate on the owner\'s word (his answer of 24 October, 4), at $0, not looked at '
                         'again: the Arabic INCI now ends on "CI 77891, CI 77007." (two items)'}
        open_ = []
    record['gate'] = {'rounds': rounds, 'holds': last['holds'], 'open': open_, 'after_the_gate': after,
                      'repairs': len(rounds) - 1,
                      'measured_vs_eye': 'holds.no_widow counts words: "CI 77007." reads as two words, so the check '
                                         'holds while the eye (round %d) reads the Arabic INCI\'s last line as one item '
                                         'alone — the check is not the proof of that line' % last['round'],
                      'rule': 'D-D11-4: the eye as the gate, repair ≤ 1; D-D11-10: no third round'}
    lm.write_json(Path(out) / 'sticker.json', record)
    return record['gate']
