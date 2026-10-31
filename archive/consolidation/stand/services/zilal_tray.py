"""Day 12 §2 (D-D12-2) — the display tray's faces in Ẓilāl's language, composed by the engine from the lid's assets (its
stones and calm ground from the Day 12 lid's plate, ظلال's traced silhouette, the approved logo, the lid's faces for the
live words) onto the solved die (counter_tray_header): every printed face filled — no plain panel — and turned as it
folds (the die is drawn from the print side: the tray seen from below with x as the shopper sees it, the inserts seen
from above with x mirrored). The header's front leaf carries the header master. Writes the flat artwork on the die
(PDF: artwork, then the die's own cut and crease from die.pdf on top) and its picture.

Day 13 §1.2 (D-D13-8, the last repair) — the drifts cut along the lid's own banks: the lid's stones found once on its
plate and fused into its flowing banks; each face's drift one bank, set at the face's corner as the lid sets it at its
own (where the bank bleeds off the lid's edges, it bleeds off the face's cut edges), its mask the stones' own — a stone
is kept whole or not at all, so no edge of a drift is a straight fade — and no drift pixel within 3 mm of a fold line
(the creases a slot splits joined into the one fold), checked on every face before it is written. The inner back wall
(the return flap) carries a bank as the sides do. The marks (ظلال, the logo, the platforms' words, the header master)
stay where Day 12 placed them; the stones keep clear of them."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
from shapely import affinity
from shapely.geometry import LineString, Polygon, box as shp_box
from shapely.ops import unary_union

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import zilal_display as zd
from apps.pipeline.services import zilal_master as zm

OUT = zd.DISPLAY / 'tray'
DIE_PDF = zd.DISPLAY / 'die' / 'die.pdf'
K = 300.0 / lm.MM_PER_INCH                          # the faces composed at 300 PPI
BLEED_MM = 3.0
STONES_BOX_MM = (0.0, 0.0, 55.0, 70.0)              # the lid's upper-left drift: stones only (clear of ظلال and the name)
DRIFT_BOX_MM = (130.0, 75.0, 190.0, 120.0)          # the lid's lower-right drift
CALM_BOX_MM = (174.0, 16.0, 188.0, 50.0)            # the lid's calm indigo under its logo, right of ظ (p99 ΔE00 < 4)
FADE_MM = 6.0
CUT_RGB = (0.93, 0.0, 0.55)                         # the house's die colours (svg_exporter: #EC008C, #00AEEF)
CREASE_RGB = (0.0, 0.68, 0.94)
FACE_OVERLAP_MM = 0.3                               # each face clipped to its own outline grown 0.3 mm (no hairline gap)
UNDERLAY_PPMM = 150.0 / lm.MM_PER_INCH              # the bleed underlay at 150 PPI (calm ground only)
SURFACE = 'apps/pipeline/services/zilal_tray.py::build'

#: each printed face: (part, face) → (its turn on the sheet in quarter turns clockwise from upright, its design)
FACES = {
    ('tray', 'front skin'): (0, 'front'),
    ('tray', 'side skin R'): (1, 'side'),
    ('tray', 'side skin L'): (3, 'side'),
    ('tray', 'back wall'): (2, 'back'),
    ('tray', 'header rear leaf'): (2, 'back'),
    ('tray', 'header front leaf'): (0, 'header'),
    ('tray', 'return flap'): (0, 'stones'),
    ('tray', 'side liner R'): (1, 'stones'),
    ('tray', 'side liner L'): (3, 'stones'),
    ('tray', 'front liner'): (0, 'calm'),
    ('tray', 'front spine'): (0, 'calm'),
    ('tray', 'side spine R'): (1, 'calm'),
    ('tray', 'side spine L'): (3, 'calm'),
    ('slot insert', 'front leg'): (2, 'stones'),
    ('slot insert', 'bed'): (2, 'calm'),
    ('slot insert', 'backrest'): (2, 'calm'),
    ('slot insert', 'wing L'): (2, 'stones'),
    ('slot insert', 'wing R'): (2, 'stones'),
    ('front platform', 'front leg'): (2, 'name:balm'),
    ('front platform', 'plate'): (2, 'calm'),
    ('back platform', 'front leg'): (2, 'name:lipstick'),
    ('back platform', 'plate'): (2, 'calm'),
}
NAMES = {'balm': ('بلسم', 'LIP BALM'), 'lipstick': ('أحمر شفاه', 'LIPSTICK')}
NAME_CAP_MM = 4.0                                   # the platforms' words: the Latin cap 4 mm, the Arabic to match
LOGO_H_MM = {'front': 6.0, 'back': 8.0}


def lid_plate():
    return np.asarray(Image.open(zd.LID12 / 'engine' / 'plate.png').convert('RGB'))


def region(plate, box_mm):
    k = plate.shape[1] / lm.LID_MM[0]
    x0, y0, x1, y1 = box_mm
    return plate[int(y0 * k):int(y1 * k), int(x0 * k):int(x1 * k)]


def field(src, w_px, h_px, scale):
    """``src`` resampled by ``scale`` and mirror-tiled to w × h px (seamless: every tile meets its neighbour mirrored)."""
    t = cv2.resize(src, (max(int(src.shape[1] * scale), 1), max(int(src.shape[0] * scale), 1)), interpolation=cv2.INTER_AREA)
    reps_y, reps_x = h_px // t.shape[0] + 2, w_px // t.shape[1] + 2
    rows = []
    for i in range(reps_y):
        row = [t[::1 - 2 * (i % 2), ::1 - 2 * (j % 2)] for j in range(reps_x)]
        rows.append(np.concatenate(row, axis=1))
    return np.concatenate(rows, axis=0)[:h_px, :w_px]


GRAIN_SEED = 12                                    # the calm ground's grain: a fixed seed (the same faces, the same pixels)
GRAIN_SIGMA_PX = 0.6


def calm(plate, w_px, h_px):
    """The lid's calm indigo: the median colour of its calm box and grain of the same strength (the box's deviation
    from its 1 mm local mean, per channel), generated from a fixed seed — never a tiled patch, whose specks repeat."""
    src = region(plate, CALM_BOX_MM).astype(np.float32)
    k = plate.shape[1] / lm.LID_MM[0]
    local = cv2.GaussianBlur(src, (0, 0), k)
    sd = (src - local).reshape(-1, 3).std(axis=0)
    base = np.median(src.reshape(-1, 3), axis=0)
    rng = np.random.default_rng(GRAIN_SEED)
    noise = rng.standard_normal((h_px, w_px, 3)).astype(np.float32)
    noise = cv2.GaussianBlur(noise, (0, 0), GRAIN_SIGMA_PX)
    noise /= max(float(noise.std()), 1e-6)
    return np.clip(np.round(base[None, None, :] + noise * sd[None, None, :]), 0, 255).astype(np.uint8)


def stones(plate, w_px, h_px, box=STONES_BOX_MM):
    src = region(plate, box)
    return field(src, w_px, h_px, K / (plate.shape[1] / lm.LID_MM[0]))


def ramp(h_px, w_px, axis, start, end):
    """A 0 → 1 weight along ``axis`` (0: down, 1: across) from ``start`` to ``end`` (fractions of the side)."""
    n = h_px if axis == 0 else w_px
    t = np.clip((np.arange(n) / max(n - 1, 1) - start) / max(end - start, 1e-6), 0, 1)
    return np.repeat(t[:, None], w_px, axis=1) if axis == 0 else np.repeat(t[None, :], h_px, axis=0)


def mix(a, b, wgt):
    return a * (1 - wgt[..., None]) + b * wgt[..., None]


SIDE_DRIFT_SIZE = 0.4                               # the side's drift low at its back, ظلال on the calm above it
LOGO_ACROSS_X = {'l': 0.7, 'r': 0.3}                # the logo's centre across from the drift's corner (its share
LOGO_ACROSS_Y = {'t': 0.68, 'b': 0.32}              # of the face): a drift at the left puts it at 0.7, and so on
ARABIC_SIZE = 1.45                                  # the platforms' Arabic set 1.45 × the Latin's size (its x-height smaller)
DRIFT_FEATHER = 0.35                                # a drift's inner edges fade over 35 % of its size into the ground


DRIFT_INSET_MM = 2.0                                # a drift stands 2 mm inside its face's edges …
STONE_DE = 12.0                                     # [after the gate] a stone: ΔE00 over 12 from the calm ground …
STONE_SOFT_MM = 0.4                                 # … its mask softened 0.4 mm
FACE_KEEP_MM = 3.0                                  # [after the gate] every drift ends 3 mm inside its face: no fold cuts it
DRIFT_ISLAND_FEATHER = 0.3                          # … faded all round (30 % of its size): no stone cut at a crease


def drift(plate, box_mm, w_px, h_px, corner, size):
    """One of the lid's own drifts (``box_mm`` on the lid), never tiled: scaled so its larger side is ``size`` of the
    face's smaller side, standing 2 mm inside the face at ``corner`` (the upright frame's 'tl', 'tr', 'bl', 'br'),
    faded on every side — so no stone is sliced by a crease or a fold. Returns (picture, weight) at the face's size."""
    src = region(plate, box_mm).astype(np.float32)
    s = size * min(w_px, h_px) / max(src.shape[:2])
    dw, dh = max(int(src.shape[1] * s), 2), max(int(src.shape[0] * s), 2)
    dw, dh = min(dw, w_px), min(dh, h_px)
    src = cv2.resize(src, (dw, dh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    inset = int(round((BLEED_MM + DRIFT_INSET_MM) * K))
    x = inset if corner in ('tl', 'bl') else w_px - dw - inset
    y = inset if corner in ('tl', 'tr') else h_px - dh - inset
    x, y = min(max(x, 0), w_px - dw), min(max(y, 0), h_px - dh)
    n_x, n_y = max(int(dw * DRIFT_ISLAND_FEATHER), 1), max(int(dh * DRIFT_ISLAND_FEATHER), 1)
    fx = np.minimum(np.minimum(np.arange(dw) / n_x, np.arange(dw)[::-1] / n_x), 1.0)
    fy = np.minimum(np.minimum(np.arange(dh) / n_y, np.arange(dh)[::-1] / n_y), 1.0)
    # [after the gate, the eye's round 1: "rectangular vignettes … not the lid's flowing banks"] the weight follows the
    # stones' own contour: a pixel off the lid's calm ground (ΔE00 over 12) is a stone or vein, softened 0.4 mm and
    # opened into the bank's shape, times a gentle fade toward the face's middle
    lab = lm.srgb_to_lab(np.clip(src, 0, 255).astype(np.uint8))
    ground_lab = lm.srgb_to_lab(np.clip(np.median(region(plate, CALM_BOX_MM).reshape(-1, 3), axis=0), 0, 255)
                                .astype(np.uint8)[None, None, :])[0, 0]
    stone = (lm.delta_e00(lab, np.broadcast_to(ground_lab, lab.shape)) > STONE_DE).astype(np.float32)
    stone = cv2.morphologyEx(stone, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    stone = cv2.GaussianBlur(stone, (0, 0), STONE_SOFT_MM * K)
    pic = np.zeros((h_px, w_px, 3), np.float32)
    wgt = np.zeros((h_px, w_px), np.float32)
    pic[y:y + dh, x:x + dw] = src
    wgt[y:y + dh, x:x + dw] = np.clip(stone * np.outer(fy, fx) ** 0.35 * 1.15, 0, 1)
    return pic, wgt


#: each design's marks: the logo (its height, mm), ظلال (its width, a share of the face's), the platforms' words
MARKS = {'calm': [], 'stones': [], 'front': [('logo', LOGO_H_MM['front'])], 'side': [('hero', 0.42)],
         'back': [('logo', LOGO_H_MM['back'])], 'header': [], 'name:balm': [('name', 'balm')],
         'name:lipstick': [('name', 'lipstick')]}


def design(kind, w_mm, h_mm, plate, assets):
    """An upright face picture (w × h mm plus its bleed, at 300 PPI) and its vector marks: the face in the lid's
    language — the lid's calm indigo ground, one of the lid's own banks laid on it by its stones' own weight
    (``assets['drift']``: its picture and weight from ``bank_drift``, Day 13; None on a calm face), and its marks on
    the calm ground; the header's front leaf the header master."""
    if kind not in MARKS:
        raise ValueError('no design %r' % kind)
    W, H = int(round((w_mm + 2 * BLEED_MM) * K)), int(round((h_mm + 2 * BLEED_MM) * K))
    ground = calm(plate, W, H).astype(np.float32)
    drifted = assets['drift']
    if kind in DRIFT_KINDS and drifted is None:
        raise ValueError('a %s face with no drift would be a plain panel' % kind)
    if kind == 'header':
        hdr = np.asarray(Image.open(zd.HEADER / 'master' / 'header-flat.png').convert('RGB')).astype(np.float32)
        pic = cv2.resize(hdr, (W, H), interpolation=cv2.INTER_AREA)
    elif drifted is None:
        pic = ground
    else:
        pic = mix(ground, drifted[0], drifted[1])
    return np.clip(np.round(pic), 0, 255).astype(np.uint8), list(MARKS[kind])


#: the lid's drifts, taken in turn so neighbouring faces never show the same crop
DRIFT_BOXES_MM = (STONES_BOX_MM, DRIFT_BOX_MM, (25.0, 0.0, 65.0, 45.0), (100.0, 85.0, 190.0, 120.0))


def drift_boxes_clear(master):
    """Every drift crop clear of the lettering the lid's plate still carries (ظلال and the name, left in the raster
    under their foil; the live lines and the logo are cleaned from it): refused otherwise."""
    from shapely.geometry import box as shp_box
    words = [shp_box(*master['element_boxes_mm'][k]).buffer(2.0) for k in ('hero', 'name')]
    bad = [b for b in DRIFT_BOXES_MM + (CALM_BOX_MM,) if any(shp_box(*b).intersects(w) for w in words)]
    if bad:
        raise ValueError('a drift or calm crop touches the lid\'s lettering: %s' % bad)
    return True


# ---- Day 13 §1.2: the drifts cut along the lid's banks ------------------------------------------------------------------
# The eye's round 1 (docs/audit/day-12/display/tray/eye-r1.json): the side walls' drifts straddle the creases; the inner
# back wall largely plain; the drifts rectangular vignettes. The owner's repair, a different move from the two that
# failed: each crop re-anchored inside its visible wall area with its fade ending before any crease; the inner back wall
# carries a stone bank as the sides do; the drifts cut along the lid's flowing banks, their masks the stones' edges.

STONE_ERODE_MM = 0.25                               # the stones told apart: the stone mask eroded 0.25 mm (the veins break)
STONE_MIN_MM2 = 0.1                                 # … a stone or splatter dot at least 0.1 mm² (smaller: the plate's grain)
WORDS_CLEAR_MM = 2.0                                # a stone touching ظلال's or the name's box grown 2 mm is dropped whole
BANK_PX_PER_MM = 4.0                                # the banks found at 4 px/mm …
BANK_CLOSE_MM = 3.0                                 # … the stones and their splatter fused by a closing of 3 mm …
BANK_MIN_MM2 = 1500.0                               # … a bank a fused region of at least 1500 mm² (the lid's two: measured
#                                                     6201 and 3661 mm²; the next region 0 mm²)
BANK_REACH_MM = 6.0                                 # a stone or dot belongs to the bank within 6 mm of its centre
BANK_OUTLINE_MM = 0.5                               # a bank's outline recorded simplified to 0.5 mm
CORNER_MM = 20.0                                    # the lid corner a bank bleeds from: the one whose 20 mm square it fills most
CREASE_BAND_MM = 3.0                                # no drift pixel within 3 mm of a fold line, a die-cut hole or a slot …
CREASE_RAMP_MM = 1.5                                # … a kept stone stands 1.5 mm beyond that, where its soft edge ends
REACH_SKIP_MM = 10.0                                # a fold line more than 10 mm outside a face's picture cannot touch it
MARK_CLEAR_MM = 4.0                                 # a kept stone 4 mm clear of ظلال, the logo and the platforms' words …
MARK_RAMP_MM = 1.5                                  # … its soft edge gone 2.5 mm from them
BANK_HULL_MM = 2.0                                  # a drift's mask: its kept stones closed 2 mm (on the lid; at the
#                                                     bank's scale on the face), so the lid's own ground,
#                                                     veins and dots between them come with them (a marbled bank, not
#                                                     loose pebbles); its edge still the outer stones' edges
BANK_SCALE = 1.0                                    # a drift at the lid's own scale (the eye: "scaled like the lid's"); a
#                                                     face larger than the lid takes its bank at the lid's proportion —
#                                                     √(face area / lid area) — so it holds the share it holds of the lid …
NARROW_FACE_MM = 40.0                               # … a face narrower than 40 mm …
NARROW_BANK_SCALES = (0.5, 0.35)                    # … takes its bank at half the lid's scale or 0.35 (between two folds
#                                                     the smaller stones fit), whichever holds the more of the face
SUPPORT_CLOSE_MM = 3.0                              # the rectangle test: a drift's support closed 3 mm …
RECTANGLE_SHARE = 0.80                              # … covers under 80 % of its own bounding box (a rectangle covers ~100 %)
ALPHA_SUPPORT = 0.02                                # a drift pixel: alpha over 0.02

#: the anchor: Day 12's corner (the marks' corner, so every logo stays where Day 12 put it), except where the eye named
#: another — the inner back wall's bank "at its upper outer corner" (round 1); right of the lid's own upper-left bank on
#: the header above it, so the banks alternate down the back as they do across the lid
ANCHOR_OVERRIDES = {('tray', 'return flap'): 'tr'}
#: the banks taken in turn (neighbouring faces never show the same one), except the wall the eye found plain: the inner
#: back wall takes the lid's larger bank, its upper-left (never seen with the header's rear leaf, which faces away)
BANK_OVERRIDES = {('tray', 'return flap'): 1}
#: a pair's second face takes its first face's bank, mirrored (the eye: "mirror the left wall")
MIRROR_OF = {('tray', 'side skin L'): ('tray', 'side skin R'), ('tray', 'side liner L'): ('tray', 'side liner R'),
             ('slot insert', 'wing R'): ('slot insert', 'wing L')}
DRIFT_KINDS = ('front', 'side', 'back', 'stones', 'name:balm', 'name:lipstick')

VISIBLE_WALL_AREA = (
    'a face\'s visible wall area is its polygon on the die less a 3 mm band along every fold line of its part (the '
    'creases a slot splits joined into one fold), every die-cut hole, slot and slit; nothing else is subtracted, because '
    'no unprinted flap folds over a printed side: the back flaps (unprinted, 62.12 mm deep, hinged on the back wall\'s '
    'sides 1.50 mm inside the floor\'s side creases, their tops the side\'s height less the 2.00 mm clearance) fold into '
    'the 2.00 mm gap of the 5.00 mm doubled side wall (spine 5.00 − 2 × 1.5 mm board), between skin and liner; the side '
    'skins\' lock tabs lie between the back wall and the return flap (counter_tray_header: "the back, from outside in: '
    'the back wall, the side skins\' lock tabs, the header\'s return flap"); the corner flaps turn behind the front skin '
    'and the liner tabs go into the floor\'s slots. The eye\'s "diagonal gusset crease" is the side wall\'s top fold '
    '(skin / spine / liner), a fold line like any other here.')


def lid_banks(plate, master):
    """The lid's stones and its banks, found once on its plate: a stone pixel is off the lid's calm ground (ΔE00 over
    12, Day 12's drift rule); the stones told apart by eroding that mask 0.25 mm (the copper veins between them break)
    and grown back; a stone touching ظلال's or the name's box (grown 2 mm) is dropped whole. A bank: the kept stones
    fused by a closing of 3 mm, a region of at least 1500 mm²; each stone belongs to the bank within 6 mm of its centre.
    Returns the stone labels (plate px), the raw stone mask, each label's bank, and the banks (outline on the lid in mm,
    area, bounding box, the lid corner it bleeds from, its stones)."""
    k = plate.shape[1] / lm.LID_MM[0]
    lab = lm.srgb_to_lab(plate)
    ground = lm.srgb_to_lab(np.clip(np.median(region(plate, CALM_BOX_MM).reshape(-1, 3), axis=0), 0, 255)
                            .astype(np.uint8)[None, None, :])[0, 0]
    stone = lm.delta_e00(lab, np.broadcast_to(ground, lab.shape)) > STONE_DE
    words = np.zeros(stone.shape, bool)
    for key in ('hero', 'name'):
        x0, y0, x1, y1 = master['element_boxes_mm'][key]
        words[max(int((y0 - WORDS_CLEAR_MM) * k), 0):int(math.ceil((y1 + WORDS_CLEAR_MM) * k)),
              max(int((x0 - WORDS_CLEAR_MM) * k), 0):int(math.ceil((x1 + WORDS_CLEAR_MM) * k))] = True
    r = max(int(round(STONE_ERODE_MM * k)), 1)
    disk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    core = cv2.erode(stone.astype(np.uint8), disk)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(core, connectivity=8)
    if n > 65535:
        raise ValueError('%d stones: more than a 16-bit label holds' % n)
    keep = stats[:, cv2.CC_STAT_AREA] / k ** 2 >= STONE_MIN_MM2
    keep[0] = False
    keep[np.unique(labels[words & (labels > 0)])] = False
    labels = np.where(keep[labels], labels, 0).astype(np.uint16)
    labels = cv2.dilate(labels, disk) * stone.astype(np.uint16)
    stone &= ~words
    # the banks, at 4 px/mm: the kept stones fused
    bw, bh = int(round(lm.LID_MM[0] * BANK_PX_PER_MM)), int(round(lm.LID_MM[1] * BANK_PX_PER_MM))
    small = cv2.resize((labels > 0).astype(np.uint8), (bw, bh), interpolation=cv2.INTER_AREA)
    rc = int(round(BANK_CLOSE_MM * BANK_PX_PER_MM))
    fused = cv2.morphologyEx(small, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rc + 1, 2 * rc + 1)))
    nb, blabels, bstats, _ = cv2.connectedComponentsWithStats(fused, connectivity=8)
    big = sorted((i for i in range(1, nb) if bstats[i, cv2.CC_STAT_AREA] / BANK_PX_PER_MM ** 2 >= BANK_MIN_MM2),
                 key=lambda i: -bstats[i, cv2.CC_STAT_AREA])
    if len(big) < 2:
        raise ValueError('the lid\'s plate shows %d banks, not its two' % len(big))
    rr = int(round(BANK_REACH_MM * BANK_PX_PER_MM))
    reach_disk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rr + 1, 2 * rr + 1))
    near = np.zeros((bh, bw), np.uint8)
    banks = []
    for bank_id, i in enumerate(big, start=1):
        mask = (blabels == i).astype(np.uint8)
        grown = cv2.dilate(mask, reach_disk)
        near[(grown > 0) & (near == 0)] = bank_id
        c = int(round(CORNER_MM * BANK_PX_PER_MM))
        fills = {'tl': mask[:c, :c].mean(), 'tr': mask[:c, -c:].mean(), 'bl': mask[-c:, :c].mean(),
                 'br': mask[-c:, -c:].mean()}
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        outline = cv2.approxPolyDP(max(contours, key=cv2.contourArea), BANK_OUTLINE_MM * BANK_PX_PER_MM, True)
        x, y, w, h = bstats[i, :4]
        banks.append({'bank': bank_id, 'area_mm2': round(float(bstats[i, cv2.CC_STAT_AREA]) / BANK_PX_PER_MM ** 2, 1),
                      'box_mm': [round(float(v) / BANK_PX_PER_MM, 2) for v in (x, y, x + w, y + h)],
                      'lid_corner': max(fills, key=fills.get),
                      'corner_fill': {kk: round(float(v), 3) for kk, v in fills.items()},
                      'outline_mm': [[round(float(px) / BANK_PX_PER_MM, 2), round(float(py) / BANK_PX_PER_MM, 2)]
                                     for px, py in outline[:, 0, :]]})
    # each stone's bank: the bank within reach of its centre (a dot beyond every bank's reach belongs to none)
    bank_of = np.zeros(n, np.uint8)
    cx = np.clip((cents[:, 0] / k * BANK_PX_PER_MM).astype(int), 0, bw - 1)
    cy = np.clip((cents[:, 1] / k * BANK_PX_PER_MM).astype(int), 0, bh - 1)
    bank_of[keep] = near[cy[keep], cx[keep]]
    for b in banks:
        b['stones'] = int((bank_of == b['bank']).sum())
    if len({b['lid_corner'] for b in banks[:2]}) < 2:
        raise ValueError('the lid\'s two banks bleed from one corner: %s' % [b['lid_corner'] for b in banks[:2]])
    return {'k': k, 'labels': labels, 'stone': stone, 'bank_of': bank_of, 'banks': banks}


def fold_lines(part):
    """A part's fold lines: each crease, and the runs a slot splits (``floor / side skin R 1``, ``… 2``, ``… 3``)
    joined into the one fold they lie on — a drift must clear the fold, not only its creased pieces."""
    groups = {}
    for name, line in part.creases:
        groups.setdefault(re.sub(r' \d+$', '', name), []).append(line)
    out = []
    for name, lines in groups.items():
        pts = np.array([c for ln in lines for c in ln.coords], float)
        a = pts[0]
        d = pts[1] - a
        length = float(np.hypot(*d))
        if len(lines) > 1 and length > 1e-9:
            u = d / length
            off = np.abs((pts[:, 0] - a[0]) * u[1] - (pts[:, 1] - a[1]) * u[0])
            if off.max() < 0.01:
                t = (pts - a) @ u
                out.append((name, LineString([tuple(a + t.min() * u), tuple(a + t.max() * u)])))
                continue
        out += [(name, ln) for ln in lines]
    return out


def keep_off(part):
    """What a drift keeps 3 mm off on a part: its fold lines, and the outlines of its die-cut holes, slots and slits —
    as (name, segments) with each segment ((x0, y0), (x1, y1)) in sheet mm, and the holes as (name, centre, radius)."""
    segs = []
    for name, line in fold_lines(part):
        c = list(line.coords)
        segs.append((name, list(zip(c[:-1], c[1:]))))
    for sl in part.slots:
        c = list(sl['polygon'].exterior.coords)
        segs.append(('slot ' + sl['id'], list(zip(c[:-1], c[1:]))))
    for name, line in part.slits:
        c = list(line.coords)
        segs.append(('slit ' + name, list(zip(c[:-1], c[1:]))))
    return segs, [(name, c, r) for name, c, r in part.holes]


def _segment_distance(X, Y, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    length2 = dx * dx + dy * dy
    if length2 < 1e-12:
        return np.hypot(X - ax, Y - ay)
    t = np.clip(((X - ax) * dx + (Y - ay) * dy) / length2, 0.0, 1.0)
    return np.hypot(X - ax - t * dx, Y - ay - t * dy)


def sheet_distance(part, frame_mm, shape):
    """Every pixel's distance (mm) to the nearest fold line, die-cut hole, slot or slit of ``part``, in a face's picture
    as it lies on the sheet: ``frame_mm`` (x, y, width, height) its box on the sheet (the face grown by its bleed),
    ``shape`` its pixels (rows, columns); the pixel centres measured exactly against each segment."""
    ox, oy, fw, fh = frame_mm
    rows, cols = shape
    xs = (ox + (np.arange(cols, dtype=np.float64) + 0.5) * (fw / cols)).astype(np.float32)
    ys = (oy + (np.arange(rows, dtype=np.float64) + 0.5) * (fh / rows)).astype(np.float32)
    X, Y = np.meshgrid(xs, ys)
    frame = shp_box(ox, oy, ox + fw, oy + fh)
    dist = np.full(shape, np.inf, np.float32)
    segs, holes = keep_off(part)
    for _name, pieces in segs:
        for a, b in pieces:
            if LineString([a, b]).distance(frame) <= REACH_SKIP_MM:
                dist = np.minimum(dist, _segment_distance(X, Y, a, b))
    for _name, (cx, cy), r in holes:
        if frame.distance(shp_box(cx - r, cy - r, cx + r, cy + r)) <= REACH_SKIP_MM:
            dist = np.minimum(dist, np.abs(np.hypot(X - cx, Y - cy) - r))
    return dist


def raster(geom, shape, origin_mm, px_per_mm):
    """A polygon (or several, holes kept) filled into a mask of ``shape`` px, ``origin_mm`` at the top-left pixel's
    corner, at ``px_per_mm`` (one number, or (across, down))."""
    kx, ky = (px_per_mm, px_per_mm) if np.isscalar(px_per_mm) else px_per_mm
    img = Image.new('L', (shape[1], shape[0]), 0)
    draw = ImageDraw.Draw(img)
    for g in lm.parts(geom):
        if g.is_empty:
            continue
        draw.polygon([((x - origin_mm[0]) * kx, (y - origin_mm[1]) * ky) for x, y in g.exterior.coords], fill=255)
        for ring in g.interiors:
            draw.polygon([((x - origin_mm[0]) * kx, (y - origin_mm[1]) * ky) for x, y in ring.coords], fill=0)
    return np.asarray(img) > 0


def print_clip(part, poly):
    """Where a face's picture prints: the face grown 0.3 mm (Day 12's no-hairline overlap), and beyond its cut edges the
    3 mm bleed — never past a fold into a neighbouring face."""
    others = unary_union([f for _n, f, _p in part.faces if not f.equals(poly)])
    grown = poly.buffer(FACE_OVERLAP_MM, join_style=2)
    return grown.union(poly.buffer(BLEED_MM, join_style=2).difference(others))


def _mirror_corner(corner):
    return corner[0] + {'l': 'r', 'r': 'l'}[corner[1]]


def oriented(arr, lid_corner, corner, mirror, reflect):
    """``arr`` (the lid's plate at the face's scale) turned by quarter turns — after a mirror across its diagonal when
    ``reflect`` — so that ``lid_corner`` (where its bank bleeds off the lid) lands at the face's ``corner``: of a bank's
    two edges on the lid, the reflection swaps which lies along which edge of the face. The second face of a mirrored
    pair takes its partner's turn, then mirrored left to right. Returns (array, quarter turns counter-clockwise)."""
    target = _mirror_corner(corner) if mirror else corner
    marker = np.array([['tl', 'tr'], ['bl', 'br']])
    if reflect:
        marker_r, arr = marker.T, np.swapaxes(arr, 0, 1)
    else:
        marker_r = marker
    for q in range(4):
        pos = np.argwhere(np.rot90(marker_r, q) == lid_corner)[0]
        if marker[pos[0], pos[1]] == target:
            out = np.rot90(arr, q)
            return np.ascontiguousarray(out[:, ::-1] if mirror else out), q
    raise ValueError('no quarter turn takes the lid\'s %s to %s' % (lid_corner, target))


def upright_to_sheet_corner(corner, quarters):
    """The sheet corner (u, v ∈ {0, 1}) an upright corner lies at once the face is turned onto the sheet."""
    for u in (0, 1):
        for v in (0, 1):
            if sheet_corner_to_upright(u, v, quarters) == corner:
                return u, v
    raise ValueError(corner)


def bank_drift(scaled, banks, bank, corner, mirror, reflect, dist, forbidden, mark_dist):
    """One face's drift cut along a lid bank: the lid at the face's scale (``scaled``: picture, stone labels, scale)
    turned so the bank's own corner lies at the face's ``corner`` (the picture's corner, its bleed included), the bank's
    two edges on the lid along the face's two edges one way or, ``reflect``, the other; of the bank's stones, each kept
    whole when every pixel of it stands 4.5 mm (3 + 1.5) from every fold line, hole and slot (``dist``, mm), off every
    neighbouring face (``forbidden``) and 4 mm clear of the marks (``mark_dist``, mm); the kept stones closed 2 mm at
    the lid's scale, so the lid's own ground, veins and dots between them come too. The weight is that mask softened
    0.4 mm, times a hard zero within 3 mm of a fold line and 2.5 mm of a mark. Returns (picture, weight, facts)."""
    rgb, lab, scale = scaled
    H, W = dist.shape
    lid_corner = banks['banks'][bank - 1]['lid_corner']
    rgb_o, q = oriented(rgb, lid_corner, corner, mirror, reflect)
    lab_o, _ = oriented(lab, lid_corner, corner, mirror, reflect)
    hp, wp = lab_o.shape
    x0 = 0 if corner[1] == 'l' else W - wp
    y0 = 0 if corner[0] == 't' else H - hp
    fx0, fx1, fy0, fy1 = max(x0, 0), min(x0 + wp, W), max(y0, 0), min(y0 + hp, H)
    pic = np.zeros((H, W, 3), np.float32)
    labels = np.zeros((H, W), lab.dtype)
    pic[fy0:fy1, fx0:fx1] = rgb_o[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    labels[fy0:fy1, fx0:fx1] = lab_o[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    ids = np.unique(labels[labels > 0])
    ids = ids[banks['bank_of'][ids] == bank]
    facts = {'stones_in_reach': int(ids.size)}
    keep_ids = ids[:0]
    if ids.size:
        dmin = np.asarray(ndimage.minimum(dist, labels, ids))
        across = np.asarray(ndimage.maximum(forbidden.astype(np.uint8), labels, ids)) > 0
        mmin = np.asarray(ndimage.minimum(mark_dist, labels, ids))
        near_fold = dmin < CREASE_BAND_MM + CREASE_RAMP_MM
        near_mark = mmin < MARK_CLEAR_MM
        keep_ids = ids[~near_fold & ~across & ~near_mark]
        facts['stones_dropped'] = {'near_a_fold': int(near_fold.sum()), 'into_a_neighbouring_face': int(across.sum()),
                                   'near_a_mark': int(near_mark.sum())}
    kept = np.isin(labels, keep_ids)
    rv = max(int(round(BANK_HULL_MM * scale * K)), 1)          # the lid's gaps, at the bank's scale
    hull = cv2.morphologyEx(kept.astype(np.uint8), cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rv + 1, 2 * rv + 1))) > 0
    mask = (kept | hull) & ~forbidden
    soft = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), STONE_SOFT_MM * K)
    fade = (np.clip((dist - CREASE_BAND_MM) / CREASE_RAMP_MM, 0.0, 1.0)
            * np.clip((mark_dist - (MARK_CLEAR_MM - MARK_RAMP_MM)) / MARK_RAMP_MM, 0.0, 1.0))
    wgt = (soft * fade).astype(np.float32)
    total = float(soft.sum())
    facts.update({'stones_kept': int(keep_ids.size), 'lid_turn_quarters_ccw': int(q), 'reflected': bool(reflect),
                  'mirrored': bool(mirror),
                  'fade_removed_share': round(1.0 - float(wgt.sum()) / total, 4) if total > 0 else None})
    return pic, wgt, facts


def drift_clear_of_creases(wgt, part, poly, quarters):
    """Refuses a drift with any pixel (weight over 0) within 3 mm of a fold line, die-cut hole, slot or slit of its part,
    measured on the sheet: the weight turned onto the sheet as the picture is, at the face's box grown by its bleed.
    Returns the least distance (mm) of a drift pixel, or None for a face with no drift pixel."""
    x0, y0, x1, y1 = poly.bounds
    on_sheet = turn(wgt, quarters)
    dist = sheet_distance(part, (x0 - BLEED_MM, y0 - BLEED_MM, x1 - x0 + 2 * BLEED_MM, y1 - y0 + 2 * BLEED_MM),
                          on_sheet.shape)
    drift_px = on_sheet > 0
    if not drift_px.any():
        return None
    least = float(dist[drift_px].min())
    if least < CREASE_BAND_MM:
        raise ValueError('a drift pixel %.2f mm from a fold line of %s (the band is %.1f mm)'
                         % (least, part.name, CREASE_BAND_MM))
    return least


def support_over_box(wgt, px_per_mm):
    """The rectangle test's measure: a drift's support (weight over 0.02) closed 3 mm, over its own bounding box — a
    rectangular vignette covers about all of its box, a bank's flowing edge far less. None for no support."""
    sup = (wgt > ALPHA_SUPPORT).astype(np.uint8)
    if not sup.any():
        return None
    r = max(int(round(SUPPORT_CLOSE_MM * px_per_mm)), 1)
    closed = cv2.morphologyEx(sup, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    ys, xs = np.nonzero(closed)
    box_px = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
    return float(closed.sum()) / float(box_px)


def far_corner(poly, quarters, w, h, creases):
    """The upright corner ('tl', 'tr', 'bl', 'br') of a face farthest from the creases that bound it: a drift there
    meets the trim, not a fold."""
    from shapely.ops import unary_union
    touching = [c for c in creases if c.distance(poly) < 0.05]
    if not touching:
        return 'br'
    lines = unary_union(touching)
    best, best_d = 'br', -1.0
    x0, y0, x1, y1 = poly.bounds
    for label, (X, Y) in (('a', (x0, y0)), ('b', (x1, y0)), ('c', (x0, y1)), ('d', (x1, y1))):
        from shapely.geometry import Point
        pt_ = Point(X, Y)
        if poly.buffer(1.0).contains(pt_):
            d = lines.distance(pt_)
        else:
            d = lines.distance(poly.exterior.interpolate(poly.exterior.project(pt_)))
        if d > best_d:
            best, best_d = sheet_corner_to_upright((X - x0) / max(x1 - x0, 1e-9), (Y - y0) / max(y1 - y0, 1e-9), quarters), d
    return best


def sheet_corner_to_upright(u, v, quarters):
    """A sheet corner (u, v ∈ {0, 1}: 0 left/top) in the upright frame: the sheet turned back by ``quarters``."""
    for _ in range(quarters % 4):
        u, v = v, 1 - u
    return ('t' if v < 0.5 else 'b') + ('l' if u < 0.5 else 'r')


HERO_INSET_MM = 8.0                                 # ظلال on a side: 8 mm inside the face's edges …
HERO_STEP_MM = 1.0                                  # … searched in 1 mm steps from the back (the tall end) down


def upright_polygon(poly, quarters, w, h):
    """A face's polygon in its upright frame (origin the picture's top-left, the bleed included): the sheet turned back
    by ``quarters`` counter-clockwise."""
    x0, y0, x1, y1 = poly.bounds
    W, H = w + 2 * BLEED_MM, h + 2 * BLEED_MM
    pts = []
    for X, Y in poly.exterior.coords:
        x, y = X - (x0 - BLEED_MM), Y - (y0 - BLEED_MM)
        for i in range(quarters % 4):
            # the inverse of to_sheet's step: a clockwise turn of a frame (fw × fh) maps (x, y) → (fh − y, x)
            x, y = y, (H if (quarters - 1 - i) % 2 == 0 else W) - x
        pts.append((x, y))
    return Polygon(pts)


def tall_end(upright):
    """Which end of a side face's upright polygon is the tall back: the side whose edge reaches higher."""
    ux0, uy0, ux1, uy1 = upright.bounds
    left = min(y for x, y in upright.exterior.coords if abs(x - ux0) < 1e-6)
    right = min(y for x, y in upright.exterior.coords if abs(x - ux1) < 1e-6)
    return 'right' if right < left else 'left'


def place_hero(letters, upright, width_mm):
    """ظلال (the lid's own silhouette) scaled to ``width_mm`` and placed in the face's upright polygon: its right edge
    8 mm inside the face's right (the tall back), lowered from the top in 1 mm steps until it stands wholly inside the
    face 8 mm in. Returns the placed geometry."""
    hx0, hy0, hx1, hy1 = letters.bounds
    s = width_mm / (hx1 - hx0)
    inner = upright.buffer(-HERO_INSET_MM)
    ux0, uy0, ux1, uy1 = upright.bounds
    if tall_end(upright) == 'right':
        tx = ux1 - HERO_INSET_MM - s * hx1
    else:
        tx = ux0 + HERO_INSET_MM - s * hx0
    y = uy0
    while y < uy1:
        geom = affinity.affine_transform(letters, [s, 0, 0, s, tx, y - s * hy0])
        if inner.contains(geom.envelope):
            return geom
        y += HERO_STEP_MM
    raise ValueError('ظلال at %.1f mm wide does not fit the face' % width_mm)


def turn(img, quarters):
    return np.ascontiguousarray(np.rot90(img, -quarters))


def face_mm_size(poly, quarters):
    x0, y0, x1, y1 = poly.bounds
    w, h = x1 - x0, y1 - y0
    return (w, h) if quarters % 2 == 0 else (h, w)


MM_PER_PT = 1.0 / lm.PT_PER_MM
OWNER_REPAIR = ('each crop re-anchored inside its visible wall area with its fade ending before any crease (a test in '
                'the engine: no drift pixel across a crease line); the inner back wall carries a stone bank as the sides '
                'do; the drifts cut along the lid\'s flowing banks, their masks following the stones\' edges, not '
                'rectangles')


def scaled_lid(plate, banks, scale):
    """The lid's plate and its stone labels at ``scale`` of the lid's own size on a face at 300 PPI (and the scale)."""
    f = scale * K / banks['k']
    w, h = int(round(plate.shape[1] * f)), int(round(plate.shape[0] * f))
    rgb = cv2.resize(plate, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32)
    labels = cv2.resize(banks['labels'], (w, h), interpolation=cv2.INTER_NEAREST)
    return rgb, labels, scale


def marks_distance(placed, shape):
    """Every pixel's distance (mm) to a face's marks in its upright picture — ظلال's letters, the logo's box, the
    platforms' words' drawn box; infinite on a face with none."""
    geoms = []
    for kind, geom in placed:
        if kind == 'hero':
            geoms.append(geom)
        elif kind == 'logo':
            lx, ly, lw, lh = geom
            geoms.append(shp_box(lx, ly, lx + lw, ly + lh))
        elif kind == 'name':
            geoms.append(shp_box(*geom[3]))
    if not geoms:
        return np.full(shape, np.inf, np.float32)
    mask = raster(unary_union(geoms), shape, (0.0, 0.0), K)
    return (cv2.distanceTransform((~mask).astype(np.uint8), cv2.DIST_L2, 5) / K).astype(np.float32)


def visible_wall_area(part, poly):
    """A face's visible wall area on the sheet (``VISIBLE_WALL_AREA``): the face less the 3 mm band along its part's fold
    lines and round its holes, slots and slits."""
    from shapely.geometry import Point
    keep = [ln for _n, ln in fold_lines(part)] + [sl['polygon'].exterior for sl in part.slots]
    keep += [ln for _n, ln in part.slits] + [Point(c).buffer(r).exterior for _n, c, r in part.holes]
    return poly.difference(unary_union(keep).buffer(CREASE_BAND_MM))


def build(out_dir, die_json=None):
    """The tray's faces composed and laid on the die (``die_json``: the die's record; Day 12's when None). Writes
    display-artwork.pdf (page 1 the artwork with the die's cut and crease over it; each face's picture cut to the face,
    and past its cut edges to its bleed), display-flat.png (100 PPI), the faces' pictures and drift weights under
    engine/, tray.json. Day 12's tray folder is the record and is never written."""
    import fitz
    from apps.dielines.geometry import counter_tray_header as cth
    out = Path(out_dir)
    if out.resolve() == OUT.resolve():
        raise ValueError('Day 12\'s tray is the record: the faces are built into a folder of their own')
    die_json = zd.DISPLAY / 'die' / 'die.json' if die_json is None else Path(die_json)
    die_pdf = die_json.parent / 'die.pdf'
    (out / 'engine').mkdir(parents=True, exist_ok=True)
    record = json.loads(die_json.read_text(encoding='utf-8'))
    die = cth.build_die(record)
    geometry = Path(cth.__file__).resolve()                 # the die's code, named with its hash in the record
    plate = lid_plate()
    master = json.loads((zd.LID12 / 'master.json').read_text(encoding='utf-8'))
    drift_boxes_clear(master)
    banks = lid_banks(plate, master)
    scaled = {}
    hero_rings, _, _ = zm.trace_hero(zm.load_master_pick())
    letters = zm.letters_geometry(hero_rings)
    faces = master['type']['faces']
    hero_ink, logo_ink, cream = master['hero']['ink'], master['logo']['ink'], master['type']['inks']['eyeshadow']
    doc = fitz.open()
    page = doc.new_page(width=lm.pt(die.sheet_w), height=lm.pt(die.sheet_h))
    rows = []
    # the bleed: each part's outline grown 3 mm under its faces, in the lid's calm indigo
    for part in die.parts:
        outline = part.outline().buffer(BLEED_MM, join_style=2)
        bx0, by0, bx1, by1 = outline.bounds
        W_, H_ = int(round((bx1 - bx0) * UNDERLAY_PPMM)), int(round((by1 - by0) * UNDERLAY_PPMM))
        img_ = cv2.resize(calm(plate, int((bx1 - bx0) * K), int((by1 - by0) * K)), (W_, H_), interpolation=cv2.INTER_AREA)
        mask = Image.new('L', (W_, H_), 0)
        geoms = list(outline.geoms) if hasattr(outline, 'geoms') else [outline]
        for g in geoms:
            ImageDraw.Draw(mask).polygon([((X - bx0) * UNDERLAY_PPMM, (Y - by0) * UNDERLAY_PPMM)
                                          for X, Y in g.exterior.coords], fill=255)
        upath = out / 'engine' / ('%s--underlay.png' % part.name.replace(' ', '-'))
        Image.fromarray(np.dstack([img_, np.asarray(mask)]), 'RGBA').save(upath)
        page.insert_image(fitz.Rect(lm.pt(bx0), lm.pt(by0), lm.pt(bx1), lm.pt(by1)), filename=str(upath),
                          keep_proportion=False)
    turns_of = {}
    for (pname, _fname), (q_, _kind) in FACES.items():
        turns_of.setdefault(pname, set()).add(q_)
    chosen = {}
    banked = 0
    new_faces = []
    for part in die.parts:
        for name, poly, printed in part.faces:
            if not printed:
                continue
            key = (part.name, name)
            stem = '%s--%s' % (part.name.replace(' ', '-'), name.replace(' ', '-'))
            if key in FACES:
                quarters, kind = FACES[key]
            else:
                # a printed face the die gained after Day 12 (the slot insert's remedy): calm, turned as its part
                if part.name not in turns_of or len(turns_of[part.name]) != 1:
                    raise ValueError('a new printed face on a part with no single turn: %s / %s' % key)
                quarters, kind = next(iter(turns_of[part.name])), 'calm'
                new_faces.append({'part': part.name, 'face': name, 'design': kind, 'turn_quarters_cw': quarters,
                                  'said': 'a printed face the die gained after Day 12: calm (D-D13-7, nothing new '
                                          'designed), turned as its part\'s faces'})
            w, h = face_mm_size(poly, quarters)
            creases = [c for _n, c in part.creases]
            upright = upright_polygon(poly, quarters, w, h)
            if kind == 'side':
                marks_corner = 'br' if tall_end(upright) == 'right' else 'bl'
            else:
                marks_corner = far_corner(poly, quarters, w, h, creases)
            # the marks where Day 12 placed them — before the drift, so its stones keep clear of them
            placed = []
            for mark in MARKS[kind]:
                if mark[0] == 'logo':
                    lh = mark[1]
                    lw = lh / zd_logo_aspect()
                    # [after the gate] the logo away from the face's drift: across from its corner
                    fx_ = 0.5 if kind == 'front' else LOGO_ACROSS_X[marks_corner[1]]
                    fy_ = 0.5 if kind == 'front' else LOGO_ACROSS_Y[marks_corner[0]]
                    placed.append(('logo', (fx_ * w - lw / 2 + BLEED_MM, fy_ * h - lh / 2 + BLEED_MM, lw, lh)))
                elif mark[0] == 'hero':
                    placed.append(('hero', place_hero(letters, upright, mark[1] * w)))
                elif mark[0] == 'name':
                    ar, la = NAMES[mark[1]]
                    words = _words_pdf(ar, la, w, h, cream, out)
                    placed.append(('name', (ar, la, words, words_box(words))))
            W, H = int(round((w + 2 * BLEED_MM) * K)), int(round((h + 2 * BLEED_MM) * K))
            x0, y0, x1, y1 = poly.bounds
            frame = (x0 - BLEED_MM, y0 - BLEED_MM, x1 - x0 + 2 * BLEED_MM, y1 - y0 + 2 * BLEED_MM)
            sheet_shape = (H, W) if quarters % 2 == 0 else (W, H)
            kxy = (sheet_shape[1] / frame[2], sheet_shape[0] / frame[3])
            clip = print_clip(part, poly)
            drifted, drift_rec = None, None
            if kind in DRIFT_KINDS:
                dist = np.ascontiguousarray(np.rot90(sheet_distance(part, frame, sheet_shape), quarters))
                others = unary_union([f for _n, f, _p in part.faces if not f.equals(poly)])
                forbidden = np.ascontiguousarray(np.rot90(raster(others, sheet_shape, frame[:2], kxy), quarters))
                mark_dist = marks_distance(placed, (H, W))
                corner = ANCHOR_OVERRIDES[key] if key in ANCHOR_OVERRIDES else marks_corner
                mirror = key in MIRROR_OF
                face_px = np.ascontiguousarray(np.rot90(raster(poly, sheet_shape, frame[:2], kxy), quarters))
                if min(w, h) < NARROW_FACE_MM:
                    scales = NARROW_BANK_SCALES
                else:
                    scales = (round(max(BANK_SCALE, math.sqrt(poly.area / (lm.LID_MM[0] * lm.LID_MM[1]))), 3),)
                if mirror:
                    bank, partner_corner, reflect, scale = chosen[MIRROR_OF[key]]
                    if _mirror_corner(partner_corner) != corner:
                        raise ValueError('%s / %s is not its partner\'s mirror: %s against %s'
                                         % (key + (corner, partner_corner)))
                    ways = [(reflect, scale)]
                else:
                    bank = BANK_OVERRIDES[key] if key in BANK_OVERRIDES else 1 + banked % 2
                    banked += 1
                    ways = [(r_, s_) for s_ in scales for r_ in (False, True)]
                # of the bank's two edges on the lid, the one that lies along the face's cut edge keeps its stones:
                # both ways are cut (and a narrow face's two scales) and the one that holds the more of the face is kept
                tried = []
                for reflect, scale in ways:
                    if scale not in scaled:
                        scaled[scale] = scaled_lid(plate, banks, scale)
                    cut = bank_drift(scaled[scale], banks, bank, corner, mirror, reflect, dist, forbidden, mark_dist)
                    tried.append((float(cut[1][face_px].mean()), reflect, scale, cut))
                share, reflect, scale, (dpic, wgt, facts) = max(tried, key=lambda t: t[0])
                chosen[key] = (bank, corner, reflect, scale)
                facts['tried'] = [{'reflected': r_, 'scale_of_the_lid': c_, 'stone_share': round(s_, 4)}
                                  for s_, r_, c_, _cut in tried]
                least = drift_clear_of_creases(wgt, part, poly, quarters)
                alpha = out / 'engine' / ('%s--drift-alpha.png' % stem)
                Image.fromarray(np.round(wgt * 255).astype(np.uint8)).save(alpha)
                inside_clip = np.ascontiguousarray(np.rot90(raster(clip, sheet_shape, frame[:2], kxy), quarters))
                u, v = upright_to_sheet_corner(corner, quarters)
                ratio = support_over_box(wgt, K)
                drifted = (dpic, wgt)
                drift_rec = dict(facts, **{
                    'bank': bank, 'lid_corner': banks['banks'][bank - 1]['lid_corner'], 'corner': corner,
                    'marks_corner': marks_corner, 'scale_of_the_lid': scale,
                    'anchor_sheet_mm': [round(frame[0] + u * frame[2], 2), round(frame[1] + v * frame[3], 2)],
                    'min_distance_to_a_crease_mm': None if least is None else round(least, 3),
                    'stone_share': round(float(wgt[face_px].mean()), 4),
                    'support_closed_over_box': None if ratio is None else round(ratio, 4),
                    'visible_wall_area_mm2': round(visible_wall_area(part, poly).area, 1),
                    'face_area_mm2': round(poly.area, 1),
                    'drift_pixels_in_a_neighbouring_face': int(((wgt > 0) & forbidden & inside_clip).sum()),
                    'alpha': lm.rel(alpha)})
            img, _marks = design(kind, w, h, plate, {'drift': drifted})
            src = out / 'engine' / ('%s.png' % stem)
            Image.fromarray(img).save(src)
            # the picture placed turned onto the face's box grown by the bleed, cut to the face and, past its cut
            # edges, to its bleed (never past a fold)
            rect = fitz.Rect(lm.pt(frame[0]), lm.pt(frame[1]), lm.pt(frame[0] + frame[2]), lm.pt(frame[1] + frame[3]))
            turned = out / 'engine' / ('%s--on-die.png' % stem)
            rgb = turn(img, quarters)
            mask = raster(clip, rgb.shape[:2], frame[:2], (rgb.shape[1] / frame[2], rgb.shape[0] / frame[3]))
            Image.fromarray(np.dstack([rgb, mask.astype(np.uint8) * 255]), 'RGBA').save(turned)
            page.insert_image(rect, filename=str(turned), keep_proportion=False)
            rows.append({'part': part.name, 'face': name, 'design': kind, 'turn_quarters_cw': quarters,
                         'size_mm': [round(w, 2), round(h, 2)], 'frame_mm': [round(v_, 3) for v_ in frame],
                         'picture': lm.rel(src), 'marks': [m[0] for m in placed], 'drift': drift_rec})
            _draw_marks(page, placed, poly, quarters, w, h, hero_ink, logo_ink, cream, faces, out)
    doc.save(str(out / 'engine' / 'display-art-only.pdf'), garbage=3, deflate=True)
    doc.close()
    for name in ('display-artwork.pdf', 'display-artwork.ai'):
        layered(out / 'engine' / 'display-art-only.pdf', die, out / name)
    lm.render_png(out / 'display-artwork.pdf', 0, 100, out / 'display-flat.png')
    header = json.loads((zd.HEADER / 'master' / 'header.json').read_text(encoding='utf-8'))
    eye_r1 = json.loads((OUT / 'eye-r1.json').read_text(encoding='utf-8'))
    lx1 = header['logotype']['placed_box_mm'][2]
    rec = {'schema': 'day13_display_tray/1', 'surface': SURFACE, 'die': lm.rel(die_pdf), 'die_json': lm.rel(die_json),
           'die_json_sha256': lm.sha256(die_json),
           'geometry': {'module': lm.rel(geometry) if geometry.is_relative_to(lm.REPO) else str(geometry),
                        'sha256': lm.sha256(geometry)},
           'faces': rows, 'faces_new_on_this_die': new_faces,
           'repair': {
               'rule': 'D-D13-8: the last repair — one repair and one look; what fails its look prints on Day 14 as it '
                       'stands and is listed open at close',
               'eye_r1': {'record': lm.rel(OUT / 'eye-r1.json'), 'holds': eye_r1['holds'],
                          'defects': eye_r1['defects']},
               'owner_repair': {'words': OWNER_REPAIR, 'source': 'CURRENT_DECISIONS.md, Day 13, §1 (2)'},
               'move': 'the drifts cut along the lid\'s two banks (found once on its plate), each bank set at its '
                       'face\'s corner as the lid sets it at its own, its stones kept whole or not at all (so a drift\'s '
                       'edge is its stones\' edges), none within %.1f mm of a fold line, the left of each pair its '
                       'right\'s mirror; the inner back wall a bank at its upper outer corner' % CREASE_BAND_MM,
               'not_mended': [{
                   'eye': eye_r1['defects'][-1]['what'],
                   'measured': 'the header master\'s logotype ends at %.3f of its %.1f mm leaf (%.3f mm from the leaf\'s '
                               'right edge, a cut edge — the leaf\'s folds are its top and bottom), its safe area %.1f mm'
                               % (lx1, header['size_mm'][0], header['size_mm'][0] - lx1, header['safe_mm']),
                   'said': 'not a placement constant of the tray: the header master\'s own layout, through its own gate; '
                           'left as it stands (D-D13-7: nothing new is designed)'}]},
           'banks': {'plate': lm.rel(zd.LID12 / 'engine' / 'plate.png'),
                     'plate_sha256': lm.sha256(zd.LID12 / 'engine' / 'plate.png'),
                     'stones': int(np.count_nonzero(np.bincount(banks['labels'].ravel())[1:])),
                     'banks': banks['banks']},
           'engine': {'stone_de00': STONE_DE, 'stone_erode_mm': STONE_ERODE_MM, 'stone_min_mm2': STONE_MIN_MM2,
                      'words_clear_mm': WORDS_CLEAR_MM, 'bank_close_mm': BANK_CLOSE_MM, 'bank_min_mm2': BANK_MIN_MM2,
                      'bank_reach_mm': BANK_REACH_MM, 'crease_band_mm': CREASE_BAND_MM,
                      'crease_band_px': round(CREASE_BAND_MM * K, 2), 'crease_ramp_mm': CREASE_RAMP_MM,
                      'px_per_mm': round(K, 4), 'mark_clear_mm': MARK_CLEAR_MM, 'bank_hull_mm': BANK_HULL_MM,
                      'stone_soft_mm': STONE_SOFT_MM, 'bank_scale': BANK_SCALE, 'narrow_face_mm': NARROW_FACE_MM,
                      'narrow_bank_scales': list(NARROW_BANK_SCALES), 'support_close_mm': SUPPORT_CLOSE_MM,
                      'rectangle_share': RECTANGLE_SHARE, 'anchor_overrides': {' / '.join(k_): v_ for k_, v_ in
                                                                               ANCHOR_OVERRIDES.items()},
                      'mirrored': {' / '.join(k_): ' / '.join(v_) for k_, v_ in MIRROR_OF.items()}},
           'visible_wall_area': VISIBLE_WALL_AREA,
           'assets': {'lid_plate': lm.rel(zd.LID12 / 'engine' / 'plate.png'), 'calm_box_mm': list(CALM_BOX_MM),
                      'hero': 'zilal_master.trace_hero on the lid\'s pick of record (the lid\'s own silhouette, scaled)',
                      'header': lm.rel(zd.HEADER / 'master' / 'header-flat.png')},
           'files': {'pdf': lm.rel(out / 'display-artwork.pdf'), 'ai': lm.rel(out / 'display-artwork.ai'),
                     'flat': lm.rel(out / 'display-flat.png')}}
    lm.write_json(out / 'tray.json', rec)
    return rec


def layered(art_pdf, die, dest):
    """The artwork on its die with named layers, as the cartons' (stick_carton.write_artwork): 'artwork' the art alone,
    'cut' and 'crease' drawn from the die's own geometry (counter_tray_header: never its working words) and locked.
    Written as the PDF and as its PDF-compatible .ai."""
    import fitz
    src = fitz.open(str(art_pdf))
    pdf = fitz.open()
    layers = {name: pdf.add_ocg(name, on=True) for name in ('artwork', 'cut', 'crease')}
    page = pdf.new_page(width=src[0].rect.width, height=src[0].rect.height)
    page.show_pdf_page(page.rect, src, 0, oc=layers['artwork'])
    for part in die.parts:
        for line in part.cut_lines():
            page.draw_polyline([fitz.Point(lm.pt(x), lm.pt(y)) for x, y in line.coords], color=CUT_RGB, width=0.5,
                               oc=layers['cut'])
        for _n, line in part.creases:
            page.draw_polyline([fitz.Point(lm.pt(x), lm.pt(y)) for x, y in line.coords], color=CREASE_RGB, width=0.5,
                               dashes='[3 2] 0', oc=layers['crease'])
        for _n, (cx, cy), r in part.holes:
            page.draw_circle(fitz.Point(lm.pt(cx), lm.pt(cy)), lm.pt(r), color=CUT_RGB, width=0.5, oc=layers['cut'])
        for sl in part.slots:
            page.draw_polyline([fitz.Point(lm.pt(x), lm.pt(y)) for x, y in sl['polygon'].exterior.coords], color=CUT_RGB,
                               width=0.5, oc=layers['cut'])
    pdf.set_layer(-1, locked=[layers['cut'], layers['crease']])
    pdf.set_metadata({'title': 'the Ẓilāl family counter display — flat artwork on its die', 'creator': SURFACE})
    lm.tag_srgb(pdf)
    pdf.save(str(dest), garbage=3, deflate=True)
    pdf.close()
    src.close()
    return dest


def zd_logo_aspect():
    from apps.pipeline.services import zilal_header as zh
    return zh.LOGO_ASPECT


def _draw_marks(page, placed, poly, quarters, w, h, hero_ink, logo_ink, cream, faces, out):
    """The vector marks drawn on the sheet: each mark's upright-frame geometry turned with its face (the logo's and the
    words' files written in ``out``/engine)."""
    import fitz
    x0, y0, x1, y1 = poly.bounds
    W, H = w + 2 * BLEED_MM, h + 2 * BLEED_MM

    def to_sheet(x, y):
        # upright frame (origin the picture's top-left, bleed included) → the sheet, turned clockwise by quarters
        for _ in range(quarters % 4):
            x, y = (H if _ % 2 == 0 else W) - y, x
        return x0 - BLEED_MM + x, y0 - BLEED_MM + y

    def rgb(hex_):
        return tuple(int(hex_.lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4))

    for kind, geom in placed:
        if kind == 'hero':
            for g in lm.parts(geom):
                shape = page.new_shape()
                pts = [fitz.Point(*(lm.pt(v) for v in to_sheet(px_, py_))) for px_, py_ in g.exterior.coords]
                shape.draw_polyline(pts)
                for ring in g.interiors:
                    shape.draw_polyline([fitz.Point(*(lm.pt(v) for v in to_sheet(px_, py_))) for px_, py_ in ring.coords])
                shape.finish(fill=rgb(hero_ink), color=None, even_odd=True, closePath=True)
                shape.commit()
        elif kind == 'logo':
            lx, ly, lw, lh = geom
            corners = [to_sheet(lx, ly), to_sheet(lx + lw, ly + lh)]
            xs, ys = [c[0] for c in corners], [c[1] for c in corners]
            rect = fitz.Rect(lm.pt(min(xs)), lm.pt(min(ys)), lm.pt(max(xs)), lm.pt(max(ys)))
            logo_pdf = fitz.open(str(_logo_pdf(logo_ink, out)))
            page.show_pdf_page(rect, logo_pdf, 0, rotate=-90 * quarters)
            logo_pdf.close()
        elif kind == 'name':
            _name_strip(page, geom[2], to_sheet, quarters, w, h)


_LOGO_CACHE = {}


def _logo_pdf(ink, out):
    """The approved logo alone in ``ink`` as a one-page PDF (lid_master.logo_parts through the emitter), written in
    ``out``/engine and cached per folder."""
    key = (str(Path(out).resolve()), ink)
    if key in _LOGO_CACHE:
        return _LOGO_CACHE[key]
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Document, Group
    w = 100.0
    h = w * zd_logo_aspect()
    doc = Document(page_w=w, page_h=h, title='BBROSE logo', metadata={'typography_surface': SURFACE},
                   root=Group(name='LOGO', role='logo', children=lm.logo_parts((0.0, 0.0, w, h), ink, foil_letters=False)))
    path = Path(out) / 'engine' / ('logo-%s.ai' % ink.lstrip('#'))
    emit_pdf_ai(doc, str(path))
    _LOGO_CACHE[key] = path
    return path


def _words_pdf(ar, la, w, h, cream, out):
    """A platform's words, live in the lid's faces (the Arabic and the Latin), cream, centred on the leg, as a small
    engine document the size of the leg's upright picture (its bleed included), written in ``out``/engine."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, TextRun
    from apps.pipeline.services import zilal_sticker as zs
    medium = zs.faces()['medium']
    arabic = zs.faces()['arabic'] if 'arabic' in zs.faces() else medium
    size_pt = NAME_CAP_MM / 0.7 * lm.PT_PER_MM
    W, H = w + 2 * BLEED_MM, h + 2 * BLEED_MM
    base = BLEED_MM + h / 2 + NAME_CAP_MM / 2
    doc = Document(page_w=W, page_h=H, title='platform words', metadata={'typography_surface': SURFACE,
                                                                       'logical_text/1.0': True},
                   root=Group(name='WORDS', role='typography', children=[
                       TextRun(name='arabic', text=ar, x=W / 2 - 4.0, y=base, font=arabic['role'], size_pt=size_pt * ARABIC_SIZE,
                               color=Color.from_hex(cream), align='right'),
                       TextRun(name='latin', text=la, x=W / 2 + 4.0, y=base, font=medium['role'], size_pt=size_pt,
                               color=Color.from_hex(cream), align='left', tracking_em=0.12)]))
    path = Path(out) / 'engine' / ('words-%s.ai' % la.replace(' ', '-').lower())
    emit_pdf_ai(doc, str(path))
    return path


def words_box(path):
    """The words' drawn box (x0, y0, x1, y1 mm on their own page — the leg's upright picture), read from their file: the
    text's blocks, or, where the words are drawn as outlines, their drawings."""
    import fitz
    with fitz.open(str(path)) as d:
        p = d[0]
        rects = [fitz.Rect(b['bbox']) for b in p.get_text('dict')['blocks']]
        if not rects:
            rects = [dr['rect'] for dr in p.get_drawings()]
        if not rects:
            raise ValueError('the words file %s draws nothing' % path)
        r = fitz.Rect(rects[0])
        for x in rects[1:]:
            r |= x
    return (r.x0 * MM_PER_PT, r.y0 * MM_PER_PT, r.x1 * MM_PER_PT, r.y1 * MM_PER_PT)


def _name_strip(page, path, to_sheet, quarters, w, h):
    """A platform's words (their engine document, ``_words_pdf``) placed on the sheet turned with the face."""
    import fitz
    W, H = w + 2 * BLEED_MM, h + 2 * BLEED_MM
    a = to_sheet(0, 0)
    b = to_sheet(W, H)
    rect = fitz.Rect(lm.pt(min(a[0], b[0])), lm.pt(min(a[1], b[1])), lm.pt(max(a[0], b[0])), lm.pt(max(a[1], b[1])))
    with fitz.open(str(path)) as src:
        page.show_pdf_page(rect, src, 0, rotate=-90 * quarters)


AFTER_THE_GATE = [
    'the die\'s cut and crease drawn from its own geometry, so none of its working words reach the artwork (round 0\'s blocking)',
    'each drift a single crop, a different one on neighbouring faces, anchored at the face\'s corner farthest from its '
    'creases, clear of ظلال and the name (round 0)',
    '[after round 1, at $0, not looked at again] each drift masked by its own stones\' contour; every drift ending 3 mm '
    'inside its face so no fold cuts it; the back faces\' drift larger (0.6); each logo across from its face\'s drift; '
    'one drift per platform (the plates calm)',
    '[after the die\'s second fix, at $0, not looked at again] the faces re-composed on the final die (the platforms\' '
    'plates 28.5 and 30.5 deep, their key slots moved; the tray\'s outline and its printed faces\' shapes unchanged); '
    'the artwork written layered — artwork, and the cut and crease locked — as the PDF and its .ai',
]


def gate_record(out_dir=OUT):
    """The tray's eye gate merged into tray.json. Day 12's folder (D-D12-2: checked by the eye beside the lid and the
    header; repair ≤ 1): its round 0 and round 1, and what was mended after the gate (listed, not looked at again). A Day
    13 folder (D-D13-8, the last repair): Day 12's two rounds, read from Day 12's records, then its own round 2 once it
    is looked at — one repair, one look, never another."""
    out = Path(out_dir)
    rec = json.loads((out / 'tray.json').read_text(encoding='utf-8'))
    day12 = out.resolve() == OUT.resolve()
    sources = [(label, OUT / ('eye-%s.json' % label)) for label in ('r0', 'r1')]
    if not day12:
        sources.append(('r2', out / 'eye-r2.json'))
    rounds = []
    for label, path in sources:
        if path.exists():
            e = json.loads(path.read_text(encoding='utf-8'))
            rounds.append({'round': label, 'holds': e['holds'], 'defects': e['defects'], 'cost_usd': e['look']['cost_usd'],
                           'record': lm.rel(path)})
    if day12:
        rec['gate'] = {'rule': 'D-D12-2: the tray\'s faces checked by the eye beside the lid and the header, repair ≤ 1',
                       'rounds': rounds, 'holds': bool(rounds and rounds[-1]['holds']), 'repairs': max(len(rounds) - 1, 0),
                       'after_the_gate': AFTER_THE_GATE}
    else:
        looked = any(r['round'] == 'r2' for r in rounds)
        rec['gate'] = {'rule': 'D-D13-8: the last repair — one repair, one look; what fails its look prints on Day 14 as it '
                               'stands, listed open at close with the eye\'s words',
                       'rounds': rounds, 'looked': looked, 'holds': bool(looked and rounds[-1]['holds']),
                       'repairs': max(len(rounds) - 1, 0), 'after_the_gate_day12': AFTER_THE_GATE}
    lm.write_json(out / 'tray.json', rec)
    return rec
