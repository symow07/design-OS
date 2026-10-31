"""Day 9 §4 — the plate paths of a rich lid (D-D9-3, D-D9-4): the picture is the image model's; every word, mark,
metallic or countable element is our engine's, laid over it; and the plate is proven to carry no copy of any of them.

- ``clean_small(plate_rgb, mask, *, avoid_mask)``: a small element (lettering, a logo, a thin gold line) taken out of
  the picture by Poisson blending (``cv2.seamlessClone``) from the plate itself, shifted by the offset whose region
  holds no element and whose texture (mean and standard deviation in Lab) is nearest the ground round the element. $0.
- ``clean_large(plate_rgb, mask, *, edit_fn, prompt, style_ref, out_dir)``: a large or detailed area repainted by ONE
  injected image edit (gpt-image-2: an RGBA mask whose transparent pixels are editable — the removal mask grown 2 mm),
  pasted back only inside the removal mask, Poisson-blended at its edge.
- ``paint_free_areas(layout_rgb, free_mask, *, edit_fn, prompt, style_ref, out_dir)``: the engine-first path — the
  model paints only the free areas (enamel inside engine-built cells); every other pixel is the layout's.
- ``prove_rich_plate(plate_rgb, *, removed_masks, pasted_regions, structure_rgb, structure_mask, px_per_mm, ocr,
  mark_matcher)``: over the whole plate, (a) no doubled word or mark, (b) no doubled structure, (c) no fine-line
  residue where an element was removed, (d) no colour step across a pasted seam (CIEDE2000 < 3). What is not measured
  is named, and the proof does not hold on it.
- ``ciede2000(lab1, lab2)`` and ``srgb_to_lab(rgb)``: the colour difference (Sharma, Wu and Dalal 2005) and the D65
  sRGB → CIELAB conversion the seam check reads.
- helpers: ``seam_ready(mask)`` (a pasted region whose every seam arc can be read: narrow inlets closed, small islands
  filled — ``fill_small_holes``), ``seam_delta_e(plate_rgb, region, *, px_per_mm)`` (the seam measure alone, e.g. on
  the plate before a paste: the picture's own floor) and ``jsonable(record)``.

No provider is called here. ``edit_fn``, ``ocr`` and ``mark_matcher`` are injected: production binds them to the
guarded gpt-image-2 edit, ``concept_sketches.ocr_words`` itself (``ocr(png, *, lang, psm)``, called once per read of
OCR_READS) and a closure over ``truthful_concept.find_mark(png, lay, out_dir)``; the tests bind fakes, and run the real
``ocr_words`` once. Arrays are the lid's own grid (``truthful_concept.LID_PX``, 1536 × 970 at ``PX_PER_MM``), RGB uint8,
y down; masks are boolean arrays of the same rows and columns.

Measured on OpenCV 5.0.0 (this venv), and built around:
- ``cv2.seamlessClone`` WRITES INTO ITS MASK ARGUMENT (eroded and inverted inside the ROI): a mask reused for a second
  call clones nothing, every other call. Every call here gets a fresh copy of the mask, the source and the destination.
- it takes its guidance from the source only 3 px or more inside the mask (3 erosions of 3 × 3): a line 0–2 px inside
  the mask's edge is not carried. The clone mask is therefore the pasted region grown by ``GUIDE_MARGIN_PX`` (a 9 × 9
  square), so every pixel of the region is the source's; the result is then kept ONLY inside the region.
- its point ``p`` is the centre of the mask's bounding box in the destination, ``(x + w // 2, y + h // 2)``, which
  registers source and destination pixel for pixel (checked on odd and even boxes).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np

from apps.pipeline.services import truthful_concept as tc

#: the lid's working scale and grid (190 × 120 mm at 1536 px across ≈ 8.08 px/mm), the image model's frame and its bands
PX_PER_MM = tc.PX_PER_MM
LID_PX = tc.LID_PX
FRAME_PX = tc.FRAME_PX
BAND_PX = tc.BAND_PX

# --- the cleaning paths ------------------------------------------------------------------------------------------
#: a small element's mask is grown this much before it is replaced (its anti-aliased edge and halo go with it)
SMALL_GROW_MM = 1.0
#: the image edit may repaint the removal mask grown this much (transparent in its RGBA mask); the paste stays inside
EDIT_GROW_MM = 2.0
#: the shifted source is looked for within this distance of the element, along each axis
SOURCE_SEARCH_MM = 30.0
#: the ground the source's texture must match: a ring this wide round the grown mask, clear of every element
TEXTURE_RING_MM = 2.0
#: cv2.seamlessClone erodes its mask 3 times by a 3 × 3 square before reading the source's gradients (measured)
CLONE_EROSION_PX = 3
#: the clone mask is the pasted region grown by this (a square): the erosion, and one pixel for the edge's gradient
GUIDE_MARGIN_PX = CLONE_EROSION_PX + 1
#: every array is reflect-padded this much before cloning, so a region at the plate's edge is cloned too (the clone
#: mask never reaches the padded border, whose pixels OpenCV clears)
PAD_PX = 2 * GUIDE_MARGIN_PX
#: a candidate whose region meets an element by less than this many (interpolated) pixels is clear of it
OVERLAP_PX_MAX = 0.5
#: an island of original pixels inside a pasted region smaller than this (a letter's counter closed by the 1 mm grow)
#: is pasted too: its seam is too short to read (measured: a grown "Enchanted" left islands of 0.75 and 0.03 mm²,
#: whose arcs the seam check could not read)
HOLE_FILL_MM2 = 2.0
#: an inlet of a pasted region narrower than two seam bands (between two grown letters) is closed — pasted too: an arc
#: along it has no room for its outer band (measured: one such arc of the grown "Enchanted" held 14 px against 16;
#: closed by this radius, six lettering regions kept no unreadable arc, adding 19–582 px)
INLET_CLOSE_MM = 1.0

# --- the proof ---------------------------------------------------------------------------------------------------
#: the band-pass every check reads: a difference of Gaussians (≈ 1 px and 4 px at the lid's scale), periods of about
#: 0.4–1.7 mm — a 0.1 mm foil line, an engraving at 12 lines/cm (0.83 mm) and a lettering stroke all fall in it
BAND_FINE_MM = 0.125
BAND_COARSE_MM = 0.5
#: (a) an OCR word counts at this confidence or more; our mark is on the plate at this match score or more (Day 8's)
OCR_CONFIDENCE_MIN = 40.0
MARK_SCORE_MAX = 0.45
#: (b) the structure's footprint grown this much for the in-place correlation (a line's band-pass reaches past it)
STRUCTURE_GROW_MM = 1.0
#: (b) |r| at or above these is a doubled structure: in place, and at any other shift. Measured (20 Oct, a rosette at
#: 0.7 mm pitch and 0.75 mm stripes against Day 8's 18 painted sketches and 6 painted plates): in place the pictures
#: read ≤ 0.007 and a copy at 35 % opacity 0.64–0.69; shifted, the pictures read ≤ 0.18 (the A sketches' own wave
#: fields) and copies 0.68–0.97 (a quarter of the rosette moved 70 mm: 0.88). A copy 2 px off reads 0.04 in place and
#: 0.93 shifted — why only the zero shift is left out of the search.
IN_PLACE_NCC_MAX = 0.2
SHIFTED_NCC_MAX = 0.3
#: (b) the structure is searched for elsewhere tile by tile (a lid-wide girih is never one template); a tile counts
#: when the footprint covers this much of it
TILE_MM = 24.0
TILE_COVER_MIN = 0.02
#: (b) a plate window whose L* band-pass varies less than this (L* units, RMS) is flat: no copy of a structure can be
#: in it, and its normalised correlation (a ratio of near-zero quantities, high on 8-bit banding) is not read
WINDOW_BAND_STD_MIN = 0.15
#: (c) the ring round a removed mask: this far out, this wide; the residue ratio holds at or below RESIDUE_RATIO_MAX
RESIDUE_GAP_MM = 0.5
RESIDUE_RING_MM = 2.0
RESIDUE_RATIO_MAX = 1.5
#: (c) read locally too: the band-pass RMS of every RESIDUE_TILE_MM tile holding at least RESIDUE_TILE_COVER_MIN of a
#: piece (or of its ring), the piece's most energetic tile against its ring's most energetic tile — a word or a rule
#: left in a corner of a large cleaned area is not averaged away by the clean rest of it. Measured on Day 9's
#: B-1.3 plate (busy marbling): the sketch's uncleaned logo, باليت, العيون and 18 SHADES boxes and a 20 x 20 mm gold
#: hatch read 1.6-2.9, the eight real plates at most 1.05; a lone 0.2 mm gold rule reads 1.02 — one hairline on a busy
#: picture is beyond an energy reading (the words and the mark are read by their own checks)
RESIDUE_TILE_MM = 4.0
RESIDUE_TILE_COVER_MIN = 0.25
#: (d) the seam: mean Lab of a band this deep on each side, per boundary segment this long, CIEDE2000 below the max
SEAM_BAND_MM = 1.0
SEAM_SEGMENT_MM = 2.0
SEAM_DELTA_E_MAX = 3.0
#: (d) a segment's band is read when it holds at least this area on its side of the seam
SEAM_BAND_MIN_MM2 = 0.25
#: energies and spreads at or below this are zero (a flat picture)
FLAT = 1e-6
#: (a) the OCR reads: Day 8's three (language, tesseract page segmentation mode, the script its words are matched in).
#: Each read's words are matched only against its own script's copy, as Day 8's plate proof did: the Arabic read's
#: digit noise is never Latin copy. Measured 20 Oct (real tesseract 5.5.3): matched as one list, the Arabic read's '27'
#: (68.8) and '18' (44.9-57.9) failed three of six clean velvet grounds and Day 8's A5 plate, where the two English
#: reads found no copy word on any of them
OCR_READS = (('eng', 11, 'latin'), ('eng', 6, 'latin'), ('ara', 11, 'arabic'))
#: (a) a Latin-read word of three letters or more that is not copy, read at this confidence, is listed (lettering the
#: model drew, for the eye) and does not fail the check
OTHER_WORD_CONFIDENCE_MIN = 80.0

# --- colour ------------------------------------------------------------------------------------------------------
#: sRGB (IEC 61966-2-1) linear RGB → XYZ, and the D65 white the CIELAB conversion divides by
SRGB_TO_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                        [0.2126729, 0.7151522, 0.0721750],
                        [0.0193339, 0.1191920, 0.9503041]])
WHITE_D65 = np.array([0.95047, 1.0, 1.08883])
CIE_EPSILON = 216.0 / 24389.0
CIE_KAPPA = 24389.0 / 27.0
#: CIEDE2000's parametric factors, all 1 (the reference conditions)
K_L = 1.0
K_C = 1.0
K_H = 1.0
POW25_7 = 25.0 ** 7

THRESHOLDS = {'ocr_confidence_min': OCR_CONFIDENCE_MIN, 'mark_score_max': MARK_SCORE_MAX,
              'in_place_ncc_max': IN_PLACE_NCC_MAX, 'shifted_ncc_max': SHIFTED_NCC_MAX,
              'window_band_std_min_lstar': WINDOW_BAND_STD_MIN, 'residue_ratio_max': RESIDUE_RATIO_MAX,
              'seam_delta_e_2000_max': SEAM_DELTA_E_MAX, 'seam_band_mm': SEAM_BAND_MM, 'seam_segment_mm': SEAM_SEGMENT_MM,
              'band_fine_mm': BAND_FINE_MM, 'band_coarse_mm': BAND_COARSE_MM, 'tile_mm': TILE_MM,
              'tile_cover_min': TILE_COVER_MIN, 'structure_grow_mm': STRUCTURE_GROW_MM,
              'residue_gap_mm': RESIDUE_GAP_MM, 'residue_ring_mm': RESIDUE_RING_MM,
              'residue_tile_mm': RESIDUE_TILE_MM, 'residue_tile_cover_min': RESIDUE_TILE_COVER_MIN,
              'seam_band_min_mm2': SEAM_BAND_MIN_MM2, 'other_word_confidence_min': OTHER_WORD_CONFIDENCE_MIN,
              'ocr_reads': [list(r) for r in OCR_READS]}


class NoCleanSource(ValueError):
    """``clean_small`` found no shifted region of the plate clear of every element (or no clean ground round the
    element to match): the element is not removed by this path, and the caller takes it to ``clean_large``."""


# =====================================================================================================================
# colour: sRGB → CIELAB (D65) and CIEDE2000
# =====================================================================================================================

def srgb_to_lab(rgb) -> np.ndarray:
    """CIELAB (D65) of sRGB values 0–255, element-wise over the last axis (any leading shape)."""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    linear = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = (linear @ SRGB_TO_XYZ.T) / WHITE_D65
    f = np.where(xyz > CIE_EPSILON, np.cbrt(xyz), (CIE_KAPPA * xyz + 16.0) / 116.0)
    return np.stack([116.0 * f[..., 1] - 16.0, 500.0 * (f[..., 0] - f[..., 1]), 200.0 * (f[..., 1] - f[..., 2])], axis=-1)


def ciede2000(lab1, lab2) -> np.ndarray:
    """CIEDE2000 colour difference between CIELAB colours, element-wise over the last axis — Sharma, Wu and Dalal,
    "The CIEDE2000 Color-Difference Formula: Implementation Notes, Supplementary Test Data, and Mathematical
    Observations", Color Res. Appl. 30 (2005) 21–30, equations 1–22 with kL = kC = kH = 1. Hue angles in degrees; a
    hue of zero chroma is 0 (eq. 4); the hue difference and the mean hue follow the paper's branches (eqs. 10, 14)."""
    L1, a1, b1 = np.moveaxis(np.asarray(lab1, dtype=np.float64), -1, 0)
    L2, a2, b2 = np.moveaxis(np.asarray(lab2, dtype=np.float64), -1, 0)
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    mean_c7 = ((C1 + C2) / 2.0) ** 7
    G = 0.5 * (1.0 - np.sqrt(mean_c7 / (mean_c7 + POW25_7)))
    a1p, a2p = (1.0 + G) * a1, (1.0 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360.0           # arctan2(0, 0) is 0: eq. 4's zero-chroma hue
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360.0
    chroma_product = C1p * C2p
    zero_chroma = chroma_product == 0
    dL = L2 - L1
    dC = C2p - C1p
    dh = h2p - h1p                                           # eq. 10
    dh = np.where(dh > 180.0, dh - 360.0, dh)
    dh = np.where(dh < -180.0, dh + 360.0, dh)
    dh = np.where(zero_chroma, np.zeros_like(dh), dh)
    dH = 2.0 * np.sqrt(chroma_product) * np.sin(np.radians(dh / 2.0))
    mean_L = (L1 + L2) / 2.0
    mean_Cp = (C1p + C2p) / 2.0
    hue_sum = h1p + h2p                                      # eq. 14
    far = np.abs(h1p - h2p) > 180.0
    mean_h = np.where(far & (hue_sum < 360.0), (hue_sum + 360.0) / 2.0, hue_sum / 2.0)
    mean_h = np.where(far & (hue_sum >= 360.0), (hue_sum - 360.0) / 2.0, mean_h)
    mean_h = np.where(zero_chroma, hue_sum, mean_h)
    T = (1.0 - 0.17 * np.cos(np.radians(mean_h - 30.0)) + 0.24 * np.cos(np.radians(2.0 * mean_h))
         + 0.32 * np.cos(np.radians(3.0 * mean_h + 6.0)) - 0.20 * np.cos(np.radians(4.0 * mean_h - 63.0)))
    d_theta = 30.0 * np.exp(-(((mean_h - 275.0) / 25.0) ** 2))
    mean_cp7 = mean_Cp ** 7
    R_C = 2.0 * np.sqrt(mean_cp7 / (mean_cp7 + POW25_7))
    S_L = 1.0 + 0.015 * (mean_L - 50.0) ** 2 / np.sqrt(20.0 + (mean_L - 50.0) ** 2)
    S_C = 1.0 + 0.045 * mean_Cp
    S_H = 1.0 + 0.015 * mean_Cp * T
    R_T = -np.sin(np.radians(2.0 * d_theta)) * R_C
    tL, tC, tH = dL / (K_L * S_L), dC / (K_C * S_C), dH / (K_H * S_H)
    return np.sqrt(tL ** 2 + tC ** 2 + tH ** 2 + R_T * tC * tH)


# =====================================================================================================================
# shared pieces
# =====================================================================================================================

def _rgb(array, name: str) -> np.ndarray:
    a = np.asarray(array)
    if a.ndim != 3 or a.shape[2] != 3 or a.dtype != np.uint8:
        raise ValueError('%s must be an RGB uint8 array (rows, columns, 3); it is %s %s' % (name, a.dtype, a.shape))
    return a


def _lid(array, name: str) -> np.ndarray:
    a = _rgb(array, name)
    if a.shape[:2] != (LID_PX[1], LID_PX[0]):
        raise ValueError('%s must be the lid at its working scale, %d rows × %d columns; it is %d × %d — the image '
                         'model edits the 1536 × 1024 frame, so any other grid would come back out of register'
                         % (name, LID_PX[1], LID_PX[0], a.shape[0], a.shape[1]))
    return a


def _mask(array, shape, name: str) -> np.ndarray:
    m = np.asarray(array)
    if m.shape != tuple(shape):
        raise ValueError('%s must have the plate\'s rows and columns %s; it has %s' % (name, tuple(shape), m.shape))
    return m != 0


def _disk(radius_px: int) -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius_px + 1, 2 * radius_px + 1))


def _grow(mask: np.ndarray, grow_mm: float, px_per_mm: float) -> np.ndarray:
    """``mask`` grown by ``grow_mm`` (a disc, at least one pixel)."""
    radius_px = max(1, int(round(grow_mm * px_per_mm)))
    return cv2.dilate(mask.astype(np.uint8), _disk(radius_px)) > 0


def _guide(region: np.ndarray) -> np.ndarray:
    """The clone mask of a region: grown by GUIDE_MARGIN_PX (a square, matching OpenCV's square erosion), so the
    source's gradients govern every pixel of the region."""
    side = 2 * GUIDE_MARGIN_PX + 1
    return cv2.dilate(region.astype(np.uint8), np.ones((side, side), np.uint8)) > 0


def fill_small_holes(mask) -> np.ndarray:
    """``mask`` (boolean, the lid's grid) with every hole smaller than HOLE_FILL_MM2 filled — a component of its
    complement (4-connected) that does not reach the plate's edge (part of ``seam_ready``)."""
    m = np.asarray(mask) != 0
    rows, cols = m.shape
    _count, labels, stats, _centres = cv2.connectedComponentsWithStats((~m).astype(np.uint8), connectivity=4)
    x0, y0 = stats[:, cv2.CC_STAT_LEFT], stats[:, cv2.CC_STAT_TOP]
    x1, y1 = x0 + stats[:, cv2.CC_STAT_WIDTH], y0 + stats[:, cv2.CC_STAT_HEIGHT]
    inland = (x0 > 0) & (y0 > 0) & (x1 < cols) & (y1 < rows)
    small = stats[:, cv2.CC_STAT_AREA] < HOLE_FILL_MM2 * PX_PER_MM ** 2
    fill = inland & small
    fill[0] = False                       # label 0 is the mask itself
    return m | fill[labels]


def seam_ready(mask) -> np.ndarray:
    """``mask`` as a pasted region whose every seam arc ``prove_rich_plate`` can read: its inlets narrower than two
    seam bands closed (a disc of INLET_CLOSE_MM; the plate's edge does not erode it) and its islands under
    HOLE_FILL_MM2 filled. ``clean_small`` pastes its grown region so; a caller of ``clean_large`` passes its removal
    mask through it first."""
    m = np.asarray(mask) != 0
    radius_px = max(1, int(round(INLET_CLOSE_MM * PX_PER_MM)))
    padded = cv2.copyMakeBorder(m.astype(np.uint8), radius_px, radius_px, radius_px, radius_px, cv2.BORDER_REPLICATE)
    closed = cv2.morphologyEx(padded, cv2.MORPH_CLOSE, _disk(radius_px))[radius_px:-radius_px, radius_px:-radius_px] > 0
    return fill_small_holes(m | closed)


def _mask_sha256(mask: np.ndarray) -> str:
    return hashlib.sha256(('%dx%d:' % mask.shape).encode() + np.packbits(mask).tobytes()).hexdigest()


def _array_sha256(array: np.ndarray) -> str:
    return hashlib.sha256(('%s:%s:' % (array.dtype, array.shape)).encode() + np.ascontiguousarray(array).tobytes()).hexdigest()


def _region_record(mask: np.ndarray, px_per_mm: float) -> dict:
    """Where a region is: its box (px and mm, x0 y0 x1 y1), its area and its bits' sha256."""
    ys, xs = np.nonzero(mask)
    box_px = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    count_px = int(mask.sum())
    return {'box_px': box_px, 'box_mm': [round(v / px_per_mm, 3) for v in box_px], 'area_px': count_px,
            'area_mm2': round(count_px / px_per_mm ** 2, 3), 'sha256': _mask_sha256(mask)}


def jsonable(record: dict) -> dict:
    """A record for json.dumps: every array in it (the pasted region's mask) is replaced by its shape, its count of
    set pixels and its sha256."""
    out = {}
    for key, value in record.items():
        if isinstance(value, np.ndarray):
            out[key] = {'shape': list(value.shape), 'set_px': int(np.count_nonzero(value)),
                        'sha256': _mask_sha256(value) if value.dtype == bool else _array_sha256(value)}
        elif isinstance(value, dict):
            out[key] = jsonable(value)
        else:
            out[key] = value
    return out


def _poisson_paste(source_rgb: np.ndarray, dest_rgb: np.ndarray, region: np.ndarray) -> np.ndarray:
    """``source_rgb`` cloned into ``dest_rgb`` by ``cv2.seamlessClone`` (NORMAL_CLONE) and kept ONLY inside
    ``region``: every pixel outside it is the destination's, byte for byte.

    The clone mask is the region grown by GUIDE_MARGIN_PX, so every region pixel is governed by the source's gradients
    (OpenCV reads them only 3 px inside its mask). All three arrays are reflect-padded by PAD_PX so a region at the
    plate's edge is cloned too, and the destination's padding is the source's: no boundary value outside the plate
    carries what is being removed. Each call gets fresh copies — OpenCV 5.0.0 writes into its mask argument."""
    pad = PAD_PX
    src = cv2.copyMakeBorder(np.ascontiguousarray(source_rgb), pad, pad, pad, pad, cv2.BORDER_REFLECT_101)
    dst = src.copy()
    dst[pad:-pad, pad:-pad] = dest_rgb
    grown = np.zeros(src.shape[:2], bool)
    grown[pad:-pad, pad:-pad] = region
    clone = _guide(grown)
    x, y, w, h = cv2.boundingRect(clone.astype(np.uint8))
    blended = cv2.seamlessClone(src.copy(), dst.copy(), clone.astype(np.uint8) * 255, (x + w // 2, y + h // 2),
                                cv2.NORMAL_CLONE)[pad:-pad, pad:-pad]
    out = dest_rgb.copy()
    out[region] = blended[region]
    return out


def _changed_px(a: np.ndarray, b: np.ndarray, where: np.ndarray) -> int:
    return int(((a != b).any(axis=2) & where).sum())


# =====================================================================================================================
# 1. clean_small — Poisson blending from the plate itself, shifted
# =====================================================================================================================

def _texture_search(lab: np.ndarray, grown: np.ndarray, support: np.ndarray, forbidden: np.ndarray,
                    target_mean: np.ndarray, target_std: np.ndarray, window_px: int) -> dict:
    """Every offset within ``window_px`` (each axis) whose shifted ``support`` lies inside the plate: the Lab mean and
    standard deviation of the plate under the shifted ``grown`` region (by correlation, ``cv2.matchTemplate``
    TM_CCORR), how much of ``forbidden`` the shifted support meets, and the texture distance to the target."""
    rows, cols = grown.shape
    ys, xs = np.nonzero(support)
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1
    cy0, cy1 = max(0, y0 - window_px), min(rows, y1 + window_px)
    cx0, cx1 = max(0, x0 - window_px), min(cols, x1 + window_px)
    region_t = grown[y0:y1, x0:x1].astype(np.float32)
    support_t = support[y0:y1, x0:x1].astype(np.float32)
    count = float(region_t.sum())
    crop = lab[cy0:cy1, cx0:cx1]
    means, stds = [], []
    for c in range(3):
        centre = float(crop[..., c].mean())                 # centred, so the float32 sums keep their precision
        channel = (crop[..., c] - centre).astype(np.float32)
        first = cv2.matchTemplate(channel, region_t, cv2.TM_CCORR) / count
        second = cv2.matchTemplate(channel * channel, region_t, cv2.TM_CCORR) / count
        means.append(first + centre)
        stds.append(np.sqrt(np.maximum(second - first * first, 0.0)))
    meets = cv2.matchTemplate(forbidden[cy0:cy1, cx0:cx1].astype(np.float32), support_t, cv2.TM_CCORR)
    distance = np.sqrt(sum((means[c] - target_mean[c]) ** 2 + (stds[c] - target_std[c]) ** 2 for c in range(3)))
    dy = (np.arange(meets.shape[0]) + cy0 - y0)[:, None] * np.ones((1, meets.shape[1]), int)
    dx = (np.arange(meets.shape[1]) + cx0 - x0)[None, :] * np.ones((meets.shape[0], 1), int)
    return {'means': means, 'stds': stds, 'meets': meets, 'distance': distance, 'dy': dy, 'dx': dx}


def clean_small(plate_rgb, mask, *, avoid_mask) -> tuple:
    """A small element (lettering, a logo, a thin gold line) removed from the picture by Poisson blending, $0.

    The element's ``mask`` is grown SMALL_GROW_MM (1 mm) and made seam-ready (``seam_ready``: its narrow inlets closed
    and small islands filled, never onto another element); the source is the plate itself, shifted by the offset whose
    region (with the clone's margin) lies inside the plate, meets no element (``avoid_mask`` and the element itself,
    each grown 1 mm) and whose texture — the mean and standard deviation of L*, a* and b* under the grown region — is
    nearest the texture of a TEXTURE_RING_MM ring of clean ground round it; ties go to the shorter offset. The source
    is cloned in by ``cv2.seamlessClone`` and kept only inside the grown region.

    Returns ``(plate, record)``: the cleaned plate (a new array; every pixel outside the grown region is the input's)
    and what was done — the region (box, area, sha256), the offset (px and mm), the method, the textures compared and
    the candidates counted. ``record['region_mask']`` is the grown region itself (the pasted region and the removed
    mask ``prove_rich_plate`` reads); ``jsonable(record)`` drops it for a file. Raises ``NoCleanSource`` when no offset
    within SOURCE_SEARCH_MM is clear of every element, or no clean ground surrounds the element; ``ValueError`` for an
    empty mask or arrays that do not match."""
    plate = _rgb(plate_rgb, 'plate_rgb')
    shape = plate.shape[:2]
    element = _mask(mask, shape, 'mask')
    if not element.any():
        raise ValueError('the element mask is empty: there is nothing to remove')
    others = _mask(avoid_mask, shape, 'avoid_mask')
    grown_only = _grow(element, SMALL_GROW_MM, PX_PER_MM)
    grown = grown_only | (seam_ready(grown_only) & ~others)    # never spread onto another element
    support = _guide(grown)
    forbidden = _grow(others | element, SMALL_GROW_MM, PX_PER_MM)
    ring = _grow(grown, TEXTURE_RING_MM, PX_PER_MM) & ~grown & ~forbidden
    if not ring.any():
        raise NoCleanSource('no clean ground surrounds the element (its %.0f mm ring is all elements): there is no '
                            'texture to match' % TEXTURE_RING_MM)
    lab = srgb_to_lab(plate)
    target_mean, target_std = lab[ring].mean(axis=0), lab[ring].std(axis=0)
    window_px = int(round(SOURCE_SEARCH_MM * PX_PER_MM))
    found = _texture_search(lab, grown, support, forbidden, target_mean, target_std, window_px)
    clear = found['meets'] < OVERLAP_PX_MAX
    if not clear.any():
        raise NoCleanSource('no offset within %.0f mm puts the element\'s region (grown %.0f mm, with the clone\'s '
                            '%d px margin) inside the plate and clear of every element: %d offsets tried'
                            % (SOURCE_SEARCH_MM, SMALL_GROW_MM, GUIDE_MARGIN_PX, clear.size))
    reach2 = found['dx'] ** 2 + found['dy'] ** 2
    distance = np.where(clear, found['distance'], np.inf)
    order = np.lexsort((reach2.ravel(), np.round(distance, 6).ravel()))
    best = np.unravel_index(order[0], distance.shape)
    dy, dx = int(found['dy'][best]), int(found['dx'][best])
    ys, xs = np.nonzero(support)
    source = plate.copy()
    source[ys, xs] = plate[ys + dy, xs + dx]
    cleaned = _poisson_paste(source, plate, grown)
    record = {
        'method': 'Poisson blending (cv2.seamlessClone, NORMAL_CLONE) from the plate itself shifted by an offset; '
                  'kept only inside the element\'s mask grown %.1f mm' % SMALL_GROW_MM,
        'region': _region_record(grown, PX_PER_MM), 'element': _region_record(element, PX_PER_MM),
        'grown_mm': SMALL_GROW_MM, 'seam_ready_px': int((grown & ~grown_only).sum()), 'offset_px': [dx, dy],
        'offset_mm': [round(dx / PX_PER_MM, 3), round(dy / PX_PER_MM, 3)],
        'texture': {'target_ring_mm': TEXTURE_RING_MM,
                    'target_mean_lab': [round(float(v), 3) for v in target_mean],
                    'target_std_lab': [round(float(v), 3) for v in target_std],
                    'source_mean_lab': [round(float(found['means'][c][best]), 3) for c in range(3)],
                    'source_std_lab': [round(float(found['stds'][c][best]), 3) for c in range(3)],
                    'distance': round(float(found['distance'][best]), 4)},
        'candidates': {'search_mm': SOURCE_SEARCH_MM, 'offsets_in_plate': int(clear.size), 'clear': int(clear.sum())},
        'changed_outside_region_px': _changed_px(cleaned, plate, ~grown),
        'region_mask': grown,
    }
    return cleaned, record


# =====================================================================================================================
# 2. and 3. the image edit: clean_large and paint_free_areas
# =====================================================================================================================

def _edit(lid: np.ndarray, editable: np.ndarray, edit_fn, prompt: str, style_ref, out_dir, stem: str) -> dict:
    """ONE call of the injected ``edit_fn(image_png_path, mask_png_path, prompt, style_ref)``: the lid in the image
    model's 1536 × 1024 frame (its 27 px bands continue the lid's edge rows) and an RGBA mask of the frame whose
    alpha is 0 — editable — exactly on ``editable`` and 255 everywhere else (the bands included). The edited frame must
    come back as an RGB uint8 array of the frame's size; any other shape is refused, never resized."""
    from PIL import Image as PILImage
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bottom = FRAME_PX[1] - LID_PX[1] - BAND_PX
    frame = cv2.copyMakeBorder(np.ascontiguousarray(lid), BAND_PX, bottom, 0, 0, cv2.BORDER_REPLICATE)
    alpha = np.full(frame.shape[:2], 255, np.uint8)
    alpha[BAND_PX:BAND_PX + LID_PX[1]][editable] = 0
    rgba = np.dstack([np.zeros_like(alpha)] * 3 + [alpha])
    image_png, mask_png = out_dir / ('%s-image.png' % stem), out_dir / ('%s-mask.png' % stem)
    PILImage.fromarray(frame).save(image_png)
    PILImage.fromarray(rgba).save(mask_png)
    edited = np.asarray(edit_fn(image_png, mask_png, prompt, style_ref))
    if edited.shape != frame.shape or edited.dtype != np.uint8:
        raise ValueError('the edit came back as %s %s; the frame sent was %s uint8 (RGB) — an edit of another size '
                         'is refused, never resized into register' % (edited.dtype, edited.shape, frame.shape))
    return {'edited_lid': edited[BAND_PX:BAND_PX + LID_PX[1]],
            'call': {'image_png': str(image_png), 'mask_png': str(mask_png),
                     'image_sha256': hashlib.sha256(image_png.read_bytes()).hexdigest(),
                     'mask_sha256': hashlib.sha256(mask_png.read_bytes()).hexdigest(),
                     'edited_sha256': _array_sha256(edited), 'frame_px': [FRAME_PX[0], FRAME_PX[1]],
                     'lid_rows': [BAND_PX, BAND_PX + LID_PX[1]], 'editable_px': int(editable.sum()),
                     'prompt': prompt, 'style_ref': None if style_ref is None else str(style_ref)}}


def clean_large(plate_rgb, mask, *, edit_fn, prompt, style_ref, out_dir) -> tuple:
    """A large or detailed area cleaned by ONE injected image edit, pasted back only inside the removal mask.

    The edit mask is the removal ``mask`` grown EDIT_GROW_MM (2 mm), transparent (alpha 0, editable) there and opaque
    elsewhere, over the lid in the image model's 1536 × 1024 frame; ``edit_fn(image_png_path, mask_png_path, prompt,
    style_ref)`` returns the edited frame (an RGB array). Its lid is Poisson-blended into the plate
    (``cv2.seamlessClone``, the edited pixels the source) and kept ONLY inside ``mask``: every pixel outside it is the
    plate's, byte for byte, whatever the model did there. The PNGs the call reads are written to ``out_dir`` (production
    passes a folder the image guard allows, under ``docs/audit/day-9/concepts``). The mask is honoured exactly: an island
    or a narrow inlet of original pixels left in it (a letter's counter, the gap between two letters) keeps a seam too
    short to read, so the caller passes its mask through ``seam_ready`` first or the seam check names it unmeasured.

    Returns ``(plate, record)``: the record holds the region, the method, the call (both PNGs' paths and sha256s, the
    edited frame's sha256, the prompt, the style reference), the pixels changed inside and outside the region (0) and
    ``region_mask`` (the pasted region; ``jsonable`` drops it). Raises ``ValueError`` for an empty mask, a plate that is
    not the 1536 × 970 lid, or an edit of another size. No provider is called here."""
    plate = _lid(plate_rgb, 'plate_rgb')
    region = _mask(mask, plate.shape[:2], 'mask')
    if not region.any():
        raise ValueError('the removal mask is empty: there is nothing to clean')
    editable = _grow(region, EDIT_GROW_MM, PX_PER_MM)
    sent = _edit(plate, editable, edit_fn, prompt, style_ref, out_dir, 'clean-large')
    cleaned = _poisson_paste(sent['edited_lid'], plate, region)
    record = {
        'method': 'one image edit (transparent = editable: the removal mask grown %.1f mm), Poisson-blended back '
                  '(cv2.seamlessClone, NORMAL_CLONE, the edited pixels the source) and kept only inside the removal '
                  'mask' % EDIT_GROW_MM,
        'region': _region_record(region, PX_PER_MM), 'edit_grown_mm': EDIT_GROW_MM, 'call': sent['call'],
        'changed_px': _changed_px(cleaned, plate, region),
        'changed_outside_region_px': _changed_px(cleaned, plate, ~region),
        'region_mask': region,
    }
    return cleaned, record


def paint_free_areas(layout_rgb, free_mask, *, edit_fn, prompt, style_ref, out_dir) -> tuple:
    """The engine-first path: our layout (the engine's cells, frames and borders drawn) goes to the image model with an
    RGBA mask transparent exactly on ``free_mask`` (the free areas — enamel inside engine-built cells), and the model's
    pixels are kept ONLY inside ``free_mask``; every other pixel is the layout's, byte for byte. No blending: the free
    areas meet the engine's own edges.

    Returns ``(plate, record)``: the record holds the free areas (box, area, share of the lid), the call (as
    ``clean_large``'s), the pixels the model changed inside them and the pixels changed outside (0). Raises
    ``ValueError`` for an empty ``free_mask``, a layout that is not the 1536 × 970 lid, or an edit of another size."""
    layout = _lid(layout_rgb, 'layout_rgb')
    free = _mask(free_mask, layout.shape[:2], 'free_mask')
    if not free.any():
        raise ValueError('the free mask is empty: the model has nowhere to paint')
    sent = _edit(layout, free, edit_fn, prompt, style_ref, out_dir, 'free-areas')
    plate = layout.copy()
    plate[free] = sent['edited_lid'][free]
    record = {
        'method': 'engine first: the model paints only the free areas (transparent in its mask); every other pixel '
                  'is the layout\'s',
        'free': _region_record(free, PX_PER_MM), 'free_share': round(float(free.mean()), 4), 'call': sent['call'],
        'changed_px': _changed_px(plate, layout, free),
        'changed_outside_free_px': _changed_px(plate, layout, ~free),
    }
    return plate, record


# =====================================================================================================================
# 4. prove_rich_plate
# =====================================================================================================================

def _called(what: str, fn, *args, **kwargs) -> tuple:
    """``fn(*args, **kwargs)`` as (result, None), or (None, why) when it raised: the proof names the failure and does
    not hold (a failed read is never "nothing found")."""
    try:
        return fn(*args, **kwargs), None
    except Exception as failed:  # the injected reader's own failure (OCRFailed, a missing binary, ...) is named
        why = str(failed)
        if not why:
            why = 'raised %s without a message' % type(failed).__name__
        return None, '%s failed (%s): %s' % (what, type(failed).__name__, why)


def _ocr_reads(ocr, png) -> list:
    """Every read of OCR_READS through the injected ``ocr(png, *, lang, psm)`` (production: ``ocr_words`` itself), each
    on its own: {'lang', 'psm', 'script', 'words' (None when the read failed), 'failed' (why, or None)}."""
    reads = []
    for lang, psm, script in OCR_READS:
        words, failed = _called('the OCR read (%s, psm %d)' % (lang, psm), ocr, png, lang=lang, psm=psm)
        reads.append({'lang': lang, 'psm': psm, 'script': script, 'words': words, 'failed': failed})
    return reads


def _words_check(reads) -> dict:
    """(a) the brief's words and the house name: none may be on the plate (the engine sets every word over it). The
    Latin copy and BBROSE are matched only in the Latin reads' words, the Arabic descriptor only in the Arabic read's
    (``concept_sketches._near``, at OCR_CONFIDENCE_MIN or more; a Latin find has two characters or more, as Day 8's).
    A read that failed is named and the check does not hold; the other reads' finds still stand. A script none of whose
    reads came back has None found, never "nothing found"."""
    from apps.pipeline.services.concept_sketches import COPY_WORDS, _near
    targets = {'latin': tuple(COPY_WORDS) + ('BBROSE',), 'arabic': tuple(tc.COPY['descriptor_ar'].split())}
    found = {'latin': None, 'arabic': None}
    other, rows, not_measured = [], [], []
    for read in reads:
        rows.append({'lang': read['lang'], 'psm': read['psm'], 'script': read['script'],
                     'words_read': None if read['words'] is None else len(read['words'])})
        if read['words'] is None:
            not_measured.append(read['failed'])
            continue
        script = read['script']
        if found[script] is None:
            found[script] = []
        for text, confidence, _box in read['words']:
            text = str(text)
            if float(confidence) < OCR_CONFIDENCE_MIN:
                continue
            if (script == 'arabic' or len(text) >= 2) and any(_near(text, w) for w in targets[script]):
                found[script].append(text)
            elif script == 'latin' and len(text) >= 3 and float(confidence) >= OTHER_WORD_CONFIDENCE_MIN:
                other.append(text)
    holds = not not_measured and found['latin'] == [] and found['arabic'] == []
    return {'holds': holds, 'latin_found': found['latin'], 'arabic_found': found['arabic'],
            'other_confident_words': other[:40], 'reads': rows, 'not_measured': not_measured}


def _mark_check(found, failed) -> dict:
    """(a) our mark: matched nowhere on the plate at MARK_SCORE_MAX or more. A matcher that could not look (no score)
    is not a pass."""
    if failed is not None:
        return {'holds': False, 'best_score': None, 'not_measured': [failed]}
    if not isinstance(found, dict):
        return {'holds': False, 'best_score': None,
                'not_measured': ['the mark matcher returned a %s, not find_mark\'s dict' % type(found).__name__]}
    score = found.get('score')
    if score is None:
        why = found.get('not_measured')
        if why is None:
            why = 'the mark matcher returned no score'
        return {'holds': False, 'best_score': None, 'not_measured': ['our mark could not be looked for: %s' % why]}
    if float(score) < 0:
        # the best match of a search over a whole plate is never below 0: a negative best is a sentinel, not a search
        # (Day 8's -1.0 for "matched at no scale" was read as "not on the plate" and passed)
        return {'holds': False, 'best_score': round(float(score), 4),
                'not_measured': ['the mark matcher\'s best score over the whole plate is %.3f, below 0: no search '
                                 'returns that, so our mark was not looked for' % float(score)]}
    return {'holds': float(score) < MARK_SCORE_MAX, 'best_score': round(float(score), 4), 'box_mm': found.get('box_mm'),
            'not_measured': []}


def _band(channel: np.ndarray, px_per_mm: float) -> np.ndarray:
    """The signed band-pass of one channel: a difference of Gaussians at BAND_FINE_MM and BAND_COARSE_MM, in float64
    (in float32 a perfectly flat picture keeps ~1e-6 of rounding in its band, and never reads as flat)."""
    c = channel.astype(np.float64)
    return (cv2.GaussianBlur(c, (0, 0), BAND_FINE_MM * px_per_mm)
            - cv2.GaussianBlur(c, (0, 0), BAND_COARSE_MM * px_per_mm))


def _pearson(a: np.ndarray, b: np.ndarray) -> float | None:
    """Pearson's r, or None when either side does not vary (no correlation to state)."""
    if a.std() <= FLAT or b.std() <= FLAT:
        return None
    r = float(np.corrcoef(a.astype(np.float64), b.astype(np.float64))[0, 1])
    if not np.isfinite(r):
        return None
    return r


def _structure_check(plate_band: np.ndarray, structure_rgb, structure_mask, shape, px_per_mm: float) -> dict:
    """(b) no doubled structure: the engine structure's signed L* band-pass correlated with the plate's — over its own
    footprint (grown STRUCTURE_GROW_MM), and tile by tile (TILE_MM) at every other shift over the whole plate
    (``cv2.matchTemplate`` TM_CCOEFF_NORMED, |r|: a copy in the opposite contrast counts). Only the zero shift is left
    out of the search — that one is the in-place measurement, so every shift is read by one of the two. Plate windows
    flatter than WINDOW_BAND_STD_MIN are not read (no copy can be in them)."""
    footprint = _mask(structure_mask, shape, 'structure_mask')
    structure = _rgb(structure_rgb, 'structure_rgb')
    if structure.shape[:2] != tuple(shape):
        raise ValueError('structure_rgb must have the plate\'s rows and columns %s; it has %s' % (tuple(shape), structure.shape[:2]))
    out = {'holds': False, 'in_place_ncc': None, 'shifted_best_ncc': None, 'not_measured': []}
    if not footprint.any():
        out['not_measured'].append('the structure mask is empty: no structure to look for')
        return out
    structure_band = _band(srgb_to_lab(structure)[..., 0], px_per_mm)
    over = _grow(footprint, STRUCTURE_GROW_MM, px_per_mm)
    if structure_band[over].std() <= FLAT:
        out['not_measured'].append('the structure has no band-pass detail over its footprint (flat in L*): its '
                                   'pattern cannot be looked for')
        return out
    if plate_band[over].std() <= FLAT:
        in_place = 0.0                       # the plate is flat under the structure: a measured absence, it holds
        out['in_place_flat'] = True
    else:
        r = _pearson(plate_band[over], structure_band[over])
        if r is None:
            out['not_measured'].append('the in-place correlation is not a number')
            return out
        in_place = abs(r)
    out['in_place_ncc'] = round(in_place, 4)
    # the shifted search, tile by tile
    tile_px = max(8, int(round(TILE_MM * px_per_mm)))
    ys, xs = np.nonzero(footprint)
    rows, cols = shape
    best, where, tiles, flat_tiles = None, None, 0, 0
    b = plate_band.astype(np.float32)
    # each placement's window spread, from box means over the tile's own size (a box's anchor is its centre, so the
    # window whose top-left is (i, j) is read at (i + half, j + half))
    half = tile_px // 2
    mean_b = cv2.boxFilter(b, -1, (tile_px, tile_px), normalize=True, borderType=cv2.BORDER_CONSTANT)
    mean_b2 = cv2.boxFilter(b * b, -1, (tile_px, tile_px), normalize=True, borderType=cv2.BORDER_CONSTANT)
    spread = np.sqrt(np.maximum(mean_b2 - mean_b * mean_b, 0.0))[half:half + rows - tile_px + 1, half:half + cols - tile_px + 1]
    readable = spread >= WINDOW_BAND_STD_MIN
    for ty0 in range(int(ys.min()), int(ys.max()) + 1, tile_px):
        for tx0 in range(int(xs.min()), int(xs.max()) + 1, tile_px):
            ty0c, tx0c = min(ty0, rows - tile_px), min(tx0, cols - tile_px)
            if ty0c < 0 or tx0c < 0:
                continue
            cover = footprint[ty0c:ty0c + tile_px, tx0c:tx0c + tile_px].mean()
            if cover < TILE_COVER_MIN:
                continue
            template = structure_band[ty0c:ty0c + tile_px, tx0c:tx0c + tile_px].astype(np.float32)
            if template.std() <= FLAT:
                flat_tiles += 1
                continue
            tiles += 1
            score = np.abs(cv2.matchTemplate(b, template, cv2.TM_CCOEFF_NORMED))
            score = np.where(readable, score, np.zeros_like(score))
            score[ty0c, tx0c] = -1.0          # the zero shift: the in-place measurement's own
            if not np.isfinite(score).all():
                out['not_measured'].append('the shifted correlation of a tile is not a number')
                return out
            k = np.unravel_index(int(np.argmax(score)), score.shape)
            if best is None or score[k] > best:
                best, where = float(score[k]), (int(k[1]) - tx0c, int(k[0]) - ty0c)
    out['tiles'] = tiles
    out['flat_tiles'] = flat_tiles
    if tiles == 0:
        out['not_measured'].append('no tile of the structure has band-pass detail: it is not searched for elsewhere')
        return out
    best = max(best, 0.0)
    out['shifted_best_ncc'] = round(best, 4)
    out['shifted_best_at_mm'] = [round(where[0] / px_per_mm, 2), round(where[1] / px_per_mm, 2)]
    out['flat_window_share'] = round(float(1.0 - readable.mean()), 4)
    out['holds'] = in_place < IN_PLACE_NCC_MAX and best < SHIFTED_NCC_MAX
    return out


def _masks(masks, shape, name: str) -> tuple:
    """A list of masks as booleans, and why it measures nothing (None when it measures)."""
    if masks is None:
        return [], 'no %s were given: nothing is measured' % name
    out = [_mask(m, shape, '%s[%d]' % (name, i)) for i, m in enumerate(masks)]
    if not out:
        return out, 'the list of %s is empty: nothing is measured' % name
    return out, None


def _tile_rms(band_energy: np.ndarray, mask: np.ndarray, px_per_mm: float) -> list:
    """The band-pass RMS over ``mask`` in each RESIDUE_TILE_MM square tile holding at least RESIDUE_TILE_COVER_MIN of
    the mask's pixels: [(rms, (x_mm, y_mm) of the tile's centre)]."""
    t = max(1, int(round(RESIDUE_TILE_MM * px_per_mm)))
    ys, xs = np.nonzero(mask)
    out = []
    for y in range(int(ys.min()) // t * t, int(ys.max()) + 1, t):
        for x in range(int(xs.min()) // t * t, int(xs.max()) + 1, t):
            m = mask[y:y + t, x:x + t]
            if m.sum() >= RESIDUE_TILE_COVER_MIN * t * t:
                out.append((float(np.sqrt(np.mean(band_energy[y:y + t, x:x + t][m]))),
                            (round((x + t / 2) / px_per_mm, 2), round((y + t / 2) / px_per_mm, 2))))
    return out


def _residue_check(band_energy: np.ndarray, removed_masks, shape, px_per_mm: float) -> dict:
    """(c) no fine-line residue where an element was removed. Each removed mask is read piece by piece (its connected
    parts): the band-pass energy (RMS of the Lab band-pass magnitude) inside the piece against a ring round it
    (RESIDUE_GAP_MM out, RESIDUE_RING_MM wide, clear of every removed mask), the ratio at or below RESIDUE_RATIO_MAX —
    and locally, the piece's most energetic RESIDUE_TILE_MM tile against its ring's most energetic tile, at or below the
    same bound, so a residue in a small share of a large piece is not averaged away. Energy inside and none in the ring
    is a measured residue (no ratio to state); none in either is a flat picture, a measured 0. A piece with no clear
    ring, or too small to hold a tile, is not measured there."""
    masks, empty = _masks(removed_masks, shape, 'removed masks')
    out = {'holds': False, 'regions': [], 'not_measured': []}
    if empty is not None:
        out['not_measured'].append(empty)
        return out
    union = np.zeros(shape, bool)
    for m in masks:
        union |= m
    for i, m in enumerate(masks):
        if not m.any():
            out['regions'].append({'index': i, 'piece': None, 'inside_energy': None, 'ring_energy': None, 'ratio': None, 'holds': False})
            out['not_measured'].append('removed mask %d is empty: no residue is measured there' % i)
            continue
        count, labels = cv2.connectedComponents(m.astype(np.uint8), connectivity=8)
        for piece in range(1, count):
            p = labels == piece
            row = {'index': i, 'piece': piece, 'inside_energy': None, 'ring_energy': None, 'ratio': None,
                   'local_ratio': None, 'holds': False}
            out['regions'].append(row)
            ring = (_grow(p, RESIDUE_GAP_MM + RESIDUE_RING_MM, px_per_mm) & ~_grow(p, RESIDUE_GAP_MM, px_per_mm)
                    & ~union)
            if not ring.any():
                out['not_measured'].append('removed mask %d, piece %d, has no clear ring round it to compare with' % (i, piece))
                continue
            inside = float(np.sqrt(np.mean(band_energy[p])))
            around = float(np.sqrt(np.mean(band_energy[ring])))
            row.update(inside_energy=round(inside, 5), ring_energy=round(around, 5), region=_region_record(p, px_per_mm))
            inside_tiles, ring_tiles = _tile_rms(band_energy, p, px_per_mm), _tile_rms(band_energy, ring, px_per_mm)
            if around > FLAT:
                ratio = inside / around
                row['ratio'] = round(ratio, 4)
                whole = ratio <= RESIDUE_RATIO_MAX
            elif inside <= FLAT:
                row['ratio'] = 0.0                # flat inside and round it: nothing left, measured
                whole = True
            else:
                row['residue_on_flat_ground'] = True   # detail inside, none round it: a measured residue, no ratio
                whole = False
            if not inside_tiles or not ring_tiles:
                # too small to hold a tile: the whole-piece reading is the local one
                row['local_ratio'] = row['ratio']
                row['holds'] = whole
                continue
            top_in = max(inside_tiles)
            top_ring = max(r for r, _ in ring_tiles)
            if top_ring > FLAT:
                row['local_ratio'] = round(top_in[0] / top_ring, 4)
                row['local_at_mm'] = list(top_in[1])
                row['holds'] = whole and row['local_ratio'] <= RESIDUE_RATIO_MAX
            elif top_in[0] <= FLAT:
                row['local_ratio'] = 0.0
                row['holds'] = whole
            else:
                row['residue_on_flat_ground'] = True
                row['local_at_mm'] = list(top_in[1])
    out['holds'] = not out['not_measured'] and all(r['holds'] for r in out['regions'])
    return out


def _seam_one(lab: np.ndarray, region: np.ndarray, px_per_mm: float, *, before_lab=None, cover=None) -> dict:
    """One pasted region's seam: its boundary (every contour, holes included) cut into SEAM_SEGMENT_MM arcs; each band
    pixel within SEAM_BAND_MM of the boundary, inside and outside, belongs to the arc of its nearest boundary pixel;
    per arc, CIEDE2000 between the mean Lab of the inner and the outer band.

    ``before_lab`` (the plate before any paste, in Lab): each arc is read there too, on the same pixels, and judged on
    its RISE over the picture's own variation across that line — a busy picture's own edges are not a seam.
    ``cover`` (True where something opaque is laid over the plate in the print): only the pixels that print are read;
    an arc whose printing bands hold too little is 'covered' (its seam does not print), never 'unmeasured'.
    Every arc judged at or over SEAM_DELTA_E_MAX is counted ('over_count') and listed, worst first, with its place
    ('over'): a reader can tell an arc on the lid's edge from one inland."""
    from scipy.ndimage import distance_transform_edt
    rows, cols = region.shape
    band_px = SEAM_BAND_MM * px_per_mm
    margin = int(np.ceil(band_px)) + 2
    ys, xs = np.nonzero(region)
    y0, y1 = max(0, int(ys.min()) - margin), min(rows, int(ys.max()) + 1 + margin)
    x0, x1 = max(0, int(xs.min()) - margin), min(cols, int(xs.max()) + 1 + margin)
    r = region[y0:y1, x0:x1]
    contours, _hierarchy = cv2.findContours(r.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    arc_of = np.full(r.shape, -1, np.int64)
    arc_count = 0
    segment_px = SEAM_SEGMENT_MM * px_per_mm
    for contour in contours:
        pts = contour[:, 0, :]
        steps = np.hypot(np.diff(pts[:, 0], append=pts[0, 0]), np.diff(pts[:, 1], append=pts[0, 1]))
        total = float(steps.sum())
        n = max(1, int(round(total / segment_px)))
        along = np.concatenate([[0.0], np.cumsum(steps)[:-1]])
        if total > 0:
            ids = np.minimum((along / total * n).astype(np.int64), n - 1)
        else:
            ids = np.zeros(len(pts), np.int64)
        arc_of[pts[:, 1], pts[:, 0]] = ids + arc_count
        arc_count += n
    inner = r & (distance_transform_edt(r) <= band_px)
    outer = ~r & (distance_transform_edt(~r) <= band_px)
    _d, (iy, ix) = distance_transform_edt(arc_of < 0, return_indices=True)
    nearest = arc_of[iy, ix]
    reads = {'after': lab[y0:y1, x0:x1]}
    if before_lab is not None:
        reads['before'] = before_lab[y0:y1, x0:x1]

    def tally(sel):
        arcs = nearest[sel]
        count = np.bincount(arcs, minlength=arc_count)
        sums = {k: np.stack([np.bincount(arcs, weights=v[..., c][sel], minlength=arc_count) for c in range(3)], axis=-1)
                for k, v in reads.items()}
        return count, sums
    full = {side: tally(sel) for side, sel in (('inner', inner), ('outer', outer))}
    if cover is None:
        used = full
    else:
        prints = ~cover[y0:y1, x0:x1]
        used = {side: tally(sel & prints) for side, sel in (('inner', inner), ('outer', outer))}
    least_px = SEAM_BAND_MIN_MM2 * px_per_mm ** 2
    readable_full = (full['inner'][0] >= least_px) & (full['outer'][0] >= least_px)
    readable = (used['inner'][0] >= least_px) & (used['outer'][0] >= least_px)
    # an arc on the plate's own edge has no outside: it is no seam, and it is counted
    edge_arc = np.zeros(arc_count, bool)
    on_edge = (arc_of >= 0)
    ey, ex = np.nonzero(on_edge)
    touching = (ey + y0 == 0) | (ey + y0 == rows - 1) | (ex + x0 == 0) | (ex + x0 == cols - 1)
    edge_arc[np.unique(arc_of[ey[touching], ex[touching]])] = True
    unread = ~readable_full & ~edge_arc
    if cover is not None:
        # the print hides an arc whose bands it covers (readable on the plate, not on what prints), and an arc too small
        # to read on the plate of which nothing prints; an arc too small to read of which something prints is unmeasured
        nothing_prints = (used['inner'][0] + used['outer'][0]) == 0
        covered = (readable_full & ~readable) | (unread & nothing_prints)
        unread = unread & ~nothing_prints
    result = {'arcs': int(arc_count), 'measured': int(readable.sum()), 'at_plate_edge': int((~readable_full & edge_arc).sum()),
              'unmeasured': int(unread.sum()), 'max_delta_e': None, 'worst_at_mm': None,
              'judged_on': 'the rise over the plate before the paste' if before_lab is not None else 'the colour across the seam',
              'max_judged': None, 'over_count': 0, 'over': []}
    if cover is not None:
        result['covered'] = int(covered.sum())
    if readable.any():
        ids = np.nonzero(readable)[0]

        def across(which):
            inner_mean = used['inner'][1][which][ids] / used['inner'][0][ids][:, None]
            outer_mean = used['outer'][1][which][ids] / used['outer'][0][ids][:, None]
            return ciede2000(inner_mean, outer_mean)
        de = across('after')
        before = across('before') if before_lab is not None else None
        judged = de - before if before is not None else de
        by, bx = np.nonzero(arc_of >= 0)
        on = arc_of[by, bx]
        n_on = np.maximum(np.bincount(on, minlength=arc_count), 1)
        cx = (np.bincount(on, weights=bx, minlength=arc_count) / n_on + x0) / px_per_mm
        cy = (np.bincount(on, weights=by, minlength=arc_count) / n_on + y0) / px_per_mm
        k = int(np.argmax(de))
        result['max_delta_e'] = round(float(de[k]), 4)
        result['worst_at_mm'] = [round(float(cx[ids[k]]), 2), round(float(cy[ids[k]]), 2)]
        result['delta_e_p50'] = round(float(np.median(de)), 4)
        result['max_judged'] = round(float(judged.max()), 4)
        if before is not None:
            result['rise_p50'] = round(float(np.median(judged)), 4)
        over = np.nonzero(judged >= SEAM_DELTA_E_MAX)[0]
        over = over[np.argsort(-judged[over])]
        result['over_count'] = int(len(over))
        for j in over:
            row = {'at_mm': [round(float(cx[ids[j]]), 2), round(float(cy[ids[j]]), 2)], 'delta_e': round(float(de[j]), 4)}
            if before is not None:
                row.update(before_delta_e=round(float(before[j]), 4), rise=round(float(judged[j]), 4))
            result['over'].append(row)
    return result


def seam_delta_e(plate_rgb, region, *, px_per_mm, before_rgb=None, cover=None) -> dict:
    """(d) for one region on any plate — the seam measure of ``prove_rich_plate`` alone: per SEAM_SEGMENT_MM arc,
    CIEDE2000 between the mean Lab of the SEAM_BAND_MM band inside and outside; {'arcs', 'measured', 'at_plate_edge',
    'unmeasured', 'max_delta_e', 'worst_at_mm', 'delta_e_p50', 'judged_on', 'max_judged', 'over_count', 'over'}.
    ``before_rgb`` (the plate before the paste) judges each arc on its rise over the picture's own variation across the
    same line; ``cover`` (a mask, True where the print lays something opaque over the plate) reads only what prints and
    counts the arcs it hides as 'covered'. Raises ``ValueError`` for an empty region or one that covers the whole plate
    (there is no seam)."""
    plate = _rgb(plate_rgb, 'plate_rgb')
    r = _mask(region, plate.shape[:2], 'region')
    if not r.any() or r.all():
        raise ValueError('the region is %s: it has no seam' % ('empty' if not r.any() else 'the whole plate'))
    if not px_per_mm > 0:
        raise ValueError('px_per_mm must be a positive scale; it is %r' % (px_per_mm,))
    before_lab = srgb_to_lab(_rgb(before_rgb, 'before_rgb')) if before_rgb is not None else None
    if before_lab is not None and before_lab.shape[:2] != plate.shape[:2]:
        raise ValueError('before_rgb is %s, the plate %s: the same pixels must be read' % (before_lab.shape[:2], plate.shape[:2]))
    hidden = _mask(cover, plate.shape[:2], 'cover') if cover is not None else None
    return _seam_one(srgb_to_lab(plate), r, px_per_mm, before_lab=before_lab, cover=hidden)


def _seam_check(lab: np.ndarray, pasted_regions, shape, px_per_mm: float, before_lab=None) -> dict:
    """(d) the colour across every pasted seam: CIEDE2000 between the mean Lab of a SEAM_BAND_MM inner band and outer
    band, per SEAM_SEGMENT_MM boundary arc, every arc of every region judged below SEAM_DELTA_E_MAX — on its rise over
    the plate before the paste where ``before_lab`` is given, else on the colour across it. An arc whose bands hold too
    little (other than on the plate's own edge) is not measured, and the proof does not hold."""
    regions, empty = _masks(pasted_regions, shape, 'pasted regions')
    out = {'holds': False, 'max_delta_e': None, 'max_judged': None, 'over_count': 0, 'regions': [], 'not_measured': [],
           'judged_on': 'the rise over the plate before the paste' if before_lab is not None else 'the colour across the seam'}
    if empty is not None:
        out['not_measured'].append(empty)
        return out
    worst = None
    for i, region in enumerate(regions):
        if not region.any():
            out['regions'].append({'index': i, 'max_delta_e': None})
            out['not_measured'].append('pasted region %d is empty: no seam is measured there' % i)
            continue
        if region.all():
            out['regions'].append({'index': i, 'max_delta_e': None})
            out['not_measured'].append('pasted region %d covers the whole plate: it has no seam to measure' % i)
            continue
        row = dict(_seam_one(lab, region, px_per_mm, before_lab=before_lab), index=i)
        out['regions'].append(row)
        if row['measured'] == 0:
            out['not_measured'].append('pasted region %d: no arc of its seam has both bands to read' % i)
            continue
        if row['unmeasured']:
            out['not_measured'].append('pasted region %d: %d of its %d seam arcs (away from the plate\'s edge) have a '
                                       'band too small to read' % (i, row['unmeasured'], row['arcs']))
        if out['max_delta_e'] is None or row['max_delta_e'] > out['max_delta_e']:
            out['max_delta_e'] = row['max_delta_e']
        if worst is None or row['max_judged'] > worst:
            worst = row['max_judged']
        out['over_count'] += row['over_count']
    out['max_judged'] = worst
    out['holds'] = not out['not_measured'] and worst is not None and worst < SEAM_DELTA_E_MAX
    return out


def prove_rich_plate(plate_rgb, *, removed_masks, pasted_regions, structure_rgb, structure_mask, px_per_mm, ocr,
                     mark_matcher, before_rgb=None) -> dict:
    """Over the WHOLE plate (the picture alone, before our vectors are laid on it):

    (a) no doubled word or mark — ``ocr(png_path, *, lang, psm)`` (production: ``concept_sketches.ocr_words``), called
        once per read of OCR_READS, finds none of the brief's words or the house name at OCR_CONFIDENCE_MIN (the Latin
        copy in the English reads, the Arabic descriptor in the Arabic read), and ``mark_matcher(png_path)``
        (production: ``lambda png: truthful_concept.find_mark(png, lay, out_dir)``) scores our mark below
        MARK_SCORE_MAX;
    (b) no doubled structure — the engine structure (``structure_rgb``, its footprint ``structure_mask``) is correlated
        with the plate in band-pass, in place (|r| < IN_PLACE_NCC_MAX) and at every other shift tile by tile
        (|r| < SHIFTED_NCC_MAX);
    (c) no fine-line residue in each of ``removed_masks``: band-pass energy inside against a ring round it, ratio at or
        below RESIDUE_RATIO_MAX;
    (d) every seam of ``pasted_regions`` below ΔE00 SEAM_DELTA_E_MAX (1 mm bands, 2 mm arcs, every arc judged): with
        ``before_rgb`` (the plate before any paste) each arc is judged on its rise over the picture's own variation
        across the same line, so a busy picture's own edges are not read as a seam; every arc over the bound is counted.

    ``px_per_mm`` is the plate's scale. Returns {'holds', 'words', 'mark', 'structure', 'residue', 'seams',
    'not_measured', 'thresholds'}; each part carries its own 'holds' and 'not_measured'. Anything not measured — a
    reader that failed, our mark matched at no scale, an empty list or an empty mask, a flat structure, a seam arc too
    small to read — is named under 'not_measured' and the proof does not hold: never a pass on nothing."""
    import tempfile
    from PIL import Image as PILImage
    plate = _rgb(plate_rgb, 'plate_rgb')
    shape = plate.shape[:2]
    if not px_per_mm > 0:
        raise ValueError('px_per_mm must be a positive scale; it is %r' % (px_per_mm,))
    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / 'plate.png'
        PILImage.fromarray(np.ascontiguousarray(plate)).save(png)
        reads = _ocr_reads(ocr, png)
        found, mark_failed = _called('the mark matcher', mark_matcher, png)
    lab = srgb_to_lab(plate)
    before_lab = None
    if before_rgb is not None:
        before_lab = srgb_to_lab(_rgb(before_rgb, 'before_rgb'))
        if before_lab.shape[:2] != shape:
            raise ValueError('before_rgb is %s, the plate %s: the same pixels must be read' % (before_lab.shape[:2], shape))
    bands = [_band(lab[..., c], px_per_mm) for c in range(3)]
    energy = bands[0] ** 2 + bands[1] ** 2 + bands[2] ** 2
    parts = {
        'words': _words_check(reads),
        'mark': _mark_check(found, mark_failed),
        'structure': _structure_check(bands[0], structure_rgb, structure_mask, shape, px_per_mm),
        'residue': _residue_check(energy, removed_masks, shape, px_per_mm),
        'seams': _seam_check(lab, pasted_regions, shape, px_per_mm, before_lab=before_lab),
    }
    not_measured = ['%s: %s' % (name, why) for name, part in parts.items() for why in part['not_measured']]
    holds = not not_measured and all(part['holds'] is True for part in parts.values())
    return dict(parts, holds=holds, not_measured=not_measured, thresholds=dict(THRESHOLDS), px_per_mm=px_per_mm)
