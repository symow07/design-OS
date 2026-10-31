"""Day 9 — the finish proof (D-D9-6) and the measures of a lid's finishes (D-D9-3), read from the engine's own .ai.

The engine writes every finish plate on its own page after the artwork (``apps/ire/emitters/pdf_ai.py``): a 100 %
black mask in register with page 1, labelled at its top left "FINISH PLATE <PLATE> - <KIND> - IN REGISTER WITH PAGE 1"
(6 pt, x 4 mm, baseline 6 mm). Everything here reads those pages:

- ``render_proof(flat_png, ai_path, out_png, *, light=SOFTBOX)``: the deterministic finish proof. The flat lid,
  front-on, its finishes rendered as materials under one fixed softbox: foil as polished metal of its own colour with
  a fine anisotropic foil grain, emboss and deboss as relief (ink unchanged), metallic ink as a soft broad sheen, spot
  UV or gloss as a subtle gloss, the board's own texture everywhere. Computed from the plates' height and normal maps;
  no perspective, no scene, no shadow outside the relief, no Blender. The same inputs give the same PNG bytes. Where
  the flat depicts a clear finish or a metallic ink with paint page 1 does not print (a preview's tone-on-tone blind
  relief), page 1's print is shaded there instead: a finish is rendered once, as the press makes it.
- ``foil_limits(ai_path, *, min_line_mm, min_gap_mm, dpi)``: every FOIL plate against the press's limits at about
  2000 dpi: the parts a disk of the line limit cannot reach (what a morphological opening removes) and the gaps a disk
  of the gap limit bridges (what a closing adds). METALLIC_INK plates are reported apart: they have no foil limit.
- ``coverage(ai_path)``: each plate's share of the lid; foil + metallic ink and relief (emboss and deboss) as unions;
  D-D9-3's floor (metal on at least 10 % of the lid, or relief on at least 15 %).
- ``line_density(mask, *, px_per_mm)``: lines per cm where a mask is densest (10 mm windows; transects at 0, 45, 90
  and 135 degrees; every ink-to-background change counted, two to a line).
- ``plate_masks(ai_path, *, px_per_mm)``: each plate as a mask at a chosen scale (what ``line_density`` reads).
- ``prove_build(flat_png, ai_path, out_dir, *, light=SOFTBOX)``: all of it for one build: ``finish-proof.png`` and
  ``record.json``.

THE LABEL IS NEVER A FINISH. A plate's name and kind are read from its label by PyMuPDF's text extraction; the label's
own characters are then removed from the page in memory (a text-only redaction of each character's own box; no line
art and no image is touched), so a plate's drawing that runs under the label is kept whole. Two guards hold the removal
to the label: every other character of the page is still there in its place, and a render of the page changes nowhere
outside the label's own box. The file on disk is never written.

$0: nothing here calls a provider. Nothing is ever written under docs/audit/day-8 (Day 8's records are hash-pinned).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from apps.ire.container_finishes import CLEAR_FINISHES, FINISH_KINDS

MM_PER_PT = 25.4 / 72.0
MM_PER_INCH = 25.4
REPO = Path(__file__).resolve().parents[4]
DAY8_AUDIT = REPO / 'docs' / 'audit' / 'day-8'
SCHEMA = 'day9_finish_proof/1.0'
LIMITS_SCHEMA = 'day9_foil_limits/1.0'
COVERAGE_SCHEMA = 'day9_finish_coverage/1.0'
DENSITY_SCHEMA = 'day9_line_density/1.0'
#: the emitter's own label (``pdf_ai._draw_finish_plates``), read whole: a plate's name, then its kind in capitals
LABEL_RE = re.compile(r'^FINISH PLATE (?P<plate>.+) - (?P<kind>[A-Z_]+) - IN REGISTER WITH PAGE 1$')

# --- the grid ----------------------------------------------------------------------------------------------------------
#: a flat and its .ai agree in proportion within this share, or the flat is refused (never stretched): a framed
#: 1536 x 1024 render is not the 190 x 120 lid
ASPECT_TOLERANCE = 0.002
#: the proof's height field, normals and shading are computed at this multiple of the flat's grid, then averaged down
SHADE_SUPERSAMPLE = 2
#: a plate is rasterised at this multiple of the grid it is read at and averaged down, so its edges are fractional
EDGE_SUPERSAMPLE = 2
#: the grid ``coverage`` reads the plates at (x EDGE_SUPERSAMPLE for the edges: 32 px/mm)
COVERAGE_PX_PER_MM = 16.0
#: the label's removal is checked on a render at this scale: outside the label's own box (and this many pixels round
#: it) no pixel may move by more than GUARD_TOLERANCE_LEVELS of 255
GUARD_PX_PER_MM = 4.0
GUARD_MARGIN_PX = 2
GUARD_TOLERANCE_LEVELS = 8
#: and every other character of the page is still there, each within this of its place (pt)
CHAR_PLACE_TOLERANCE_PT = 0.05

# --- the relief ----------------------------------------------------------------------------------------------------------
#: a single-level brass die's common relief on carton board
EMBOSS_HEIGHT_MM = 0.30
DEBOSS_DEPTH_MM = 0.25
#: foil stands a hair proud of the board; a spot UV coat a little more
FOIL_HEIGHT_MM = 0.012
COAT_HEIGHT_MM = 0.02
#: the relief's shoulder: the 10-90 % rise of the die's bevel ("about 0.2-0.3 mm"). A Gaussian of sigma s rises 10-90 %
#: over 2.563 s, so the blur's sigma is SHOULDER_MM / GAUSS_RISE (about 0.1 mm): a 0.3 mm deboss line stays a groove
SHOULDER_MM = 0.25
GAUSS_RISE = 2.563
#: the board's own give over a relief: carton board stretches over the die, so a relief's edge rounds over a broader
#: reach than the die's bevel; PILLOW_SHARE of the height takes this broader Gaussian (sigma PILLOW_MM). A fine line is
#: narrower than the reach and keeps its groove; a letter's stem gains a soft dome
PILLOW_SHARE = 0.35
PILLOW_MM = 0.45
#: a foil's (and a coat's) own edge: crisp
FOIL_EDGE_MM = 0.03
#: the foil's colour is read from the flat where the plate covers a pixel whole (METAL_WHOLE or more); when fewer than
#: METAL_LEAST_WHOLE_PX are whole, a pixel covered from METAL_UNMIX_LEAST is un-mixed from the bare ground (under
#: METAL_BARE) within METAL_GROUND_REACH_PX, where that reach holds at least METAL_GROUND_LEAST of bare ground
METAL_WHOLE = 0.98
METAL_LEAST_WHOLE_PX = 64
METAL_UNMIX_LEAST = 0.75
METAL_BARE = 0.02
METAL_GROUND_REACH_PX = 3.0
METAL_GROUND_LEAST = 0.05
#: the flat against the .ai's own page 1 (what prints): a pixel differs when a channel moves by more than this many
#: levels; under a plate where more than FLAT_DEPICTS_PCT of the whole pixels differ, the flat DEPICTS the finish (a
#: preview's convention, such as a blind deboss drawn tone on tone) and paints there what the press will not lay
FLAT_PAGE1_LEVELS = 32
FLAT_DEPICTS_PCT = 10.0
#: under a depicted plate of these kinds the proof shades PAGE 1's print, not the flat's paint, within the plate's own
#: footprint and DEPICT_REACH_PX of the flat's pixels round it: a relief or a coat brings no ink (the press lays no
#: paint for it), and a metallic ink's sheen is the proof's to render, not the preview's. The reach is the flat's own
#: resampling smear (measured on Day 8's B3-r2: the ring field still differs on 8.4 % of its pixels at no reach, 4.1 %
#: at one pixel, 0.7 % at two, 0.18 % at three). Foil is never swapped: it is drawn as metal, its colour read from the
#: flat
PAGE_1_UNDER = ('metallic_ink',) + CLEAR_FINISHES
DEPICT_REACH_PX = 3
#: a deboss's floor sees less of the box than the board does: the cavity is read over this reach, darkened at most this
OCCLUSION_REACH_MM = 0.35
OCCLUSION = 0.35


@dataclass(frozen=True)
class Softbox:
    """The one fixed softbox. Its light comes from the same direction at every point of the lid: from ``azimuth_deg``
    (counter-clockwise from the lid's right edge, y up: 135 is the upper left) at ``elevation_deg`` above the lid; that
    constant direction lights the relief. The box is broad: what a surface reflects of it is full within ``radius_deg``
    of its centre and falls off smoothly to nothing over a further ``soft_deg`` (the area light's broad falloff); its
    hot core is ``core_deg`` across. Reflections are seen from a point ``view_mm`` above the lid's centre, so a flat foil
    sweeps from the box's light to the studio's dark across the lid; the image itself is orthographic and front-on, no
    perspective. ``ambient`` is the studio's fill: the share of a surface's light that does not depend on its tilt."""
    azimuth_deg: float
    elevation_deg: float
    radius_deg: float
    soft_deg: float
    core_deg: float
    view_mm: float
    ambient: float


SOFTBOX = Softbox(azimuth_deg=135.0, elevation_deg=50.0, radius_deg=15.0, soft_deg=40.0, core_deg=10.0,
                  view_mm=400.0, ambient=0.4)

# --- the materials (linear light) ------------------------------------------------------------------------------------
#: polished foil: its own colour times what it reflects of the studio's dark (FOIL_ROOM), and the box (FOIL_BOX) in a
#: colour FOIL_BOX_WHITEN of the way from the metal's to white; the box's hot core, caught by edges and grain, is
#: FOIL_HOT_WHITEN of the way to white
FOIL_ROOM = 0.42
FOIL_BOX = 1.0
FOIL_BOX_WHITEN = 0.12
FOIL_HOT = 0.8
FOIL_HOT_WHITEN = 0.6
#: the foil grain: a fine anisotropic micro-relief along the foil's run (the lid's x), streaks this long and this narrow,
#: this deep; and the same grain as a faint change of the foil's tone
FOIL_GRAIN_LENGTH_MM = 0.4
FOIL_GRAIN_WIDTH_MM = 0.03
FOIL_GRAIN_MM = 0.0008
FOIL_GRAIN_TONE = 0.015
#: metallic ink: a soft, broad sheen (the box's reflection, its fall half as wide again), tinted this share from the ink
#: to white; away from the box the ink is this much darker (a metallic ink goes grey off its angle); its flakes a fine
#: sparkle
METALLIC_SHEEN = 0.2
METALLIC_SOFTER = 1.5
METALLIC_OFF_ANGLE = 0.15
METALLIC_TINT = 0.35
METALLIC_FLAKE = 0.05
METALLIC_FLAKE_MM = 0.04
#: spot UV or gloss varnish: a clear coat's subtle reflection of the box, crisper than the board's (its fall over
#: GLOSS_SOFT_DEG); under it the ink is this much deeper (a gloss scatters less light than the bare board)
GLOSS = 0.12
GLOSS_SOFT_DEG = 12.0
GLOSS_DEEPEN = 0.06
#: the board: a coated board's faint sheen where the relief tilts it to catch more of the box than the flat board does;
#: its tooth (a fine micro-relief) and its fibre and mottle (a faint change of its whiteness)
BOARD_SHEEN = 0.06
BOARD_TOOTH_MM = 0.0008
BOARD_TOOTH_SIZE_MM = 0.05
BOARD_MOTTLE = 0.01
BOARD_MOTTLE_MM = 0.9
BOARD_FIBRE_MM = (0.06, 0.35)
#: every noise is drawn from its own fixed seed: the proof is the same every time
SEEDS = {'board_tooth': 9101, 'board_mottle': 9102, 'board_fibre': 9103, 'foil_grain': 9104, 'metallic_flake': 9105}

# --- the press's limits --------------------------------------------------------------------------------------------
MIN_FOIL_LINE_MM = 0.1
MIN_FOIL_GAP_MM = 0.2
LIMITS_DPI = 2000.0
#: THE ANTI-ALIASING TOLERANCE, in pixels at the limits' dpi (1 px is 0.0127 mm at 2000 dpi). A pixel is ink when the
#: plate covers half of it or more (grey at most INK_LEVEL); the disk that must fit is the limit LESS this tolerance,
#: so a line or a gap drawn exactly at its limit, at any angle and any sub-pixel phase, never fails on its own
#: anti-aliased edge. What the tolerance lets through is a band of this width below each limit, and no more.
AA_TOLERANCE_PX = 1.0
INK_LEVEL = 127
#: A PART IS NOT A CORNER. A disk rolled inside a shape never reaches the very point of a convex corner (a right angle
#: keeps a sliver about 0.4 of the disk's radius long), and a closing fills the point of every concave corner alike.
#: A thin part or a narrow gap counts when it runs at least VIOLATION_RUN times its own limit (0.2 mm for a 0.1 mm
#: line): a line, a hairline serif, a narrow counter or channel counts; a right angle, a bracketed serif or a join
#: does not. What is left out is counted and its area said ("ignored").
VIOLATION_RUN = 2.0
#: an unlabelled page is the inside artboard only as page 2 and only when it is colour art: rendered at PLATE_LIKE_DPI,
#: a page whose every inked pixel has its channels within PLATE_LIKE_CHROMA of each other (a 100 % black mask on white,
#: or nothing at all) reads as a plate, and an unlabelled plate is refused
PLATE_LIKE_DPI = 36
PLATE_LIKE_CHROMA = 12
#: a flat that differs from the .ai's page 1 on more than this share of the lid outside its depicted plates is not this
#: file's flat (Day 9's eight builds: 0.05-0.10 %)
FLAT_RESIDUAL_MAX_PCT = 5.0
#: the limits are measured tile by tile (pixels at the limits' dpi); the boxes reported are the largest this many
LIMITS_TILE_PX = 2048
MAX_BOXES = 20

# --- D-D9-3 ----------------------------------------------------------------------------------------------------------
D9_3_METAL_PCT = 10.0
D9_3_RELIEF_PCT = 15.0
D9_3_LINES_PER_CM = 12.0
#: line density: a window this wide, slid a cell at a time; the coarse map steps a window at a time
LINE_WINDOW_MM = 10.0
LINE_CELL_MM = 1.0
LINE_ANGLES = (0, 45, 90, 135)
#: how far one step along each transect goes, in pixels: a diagonal step is the square root of 2
LINE_STEP_PX = {0: 1.0, 45: math.sqrt(2.0), 90: 1.0, 135: math.sqrt(2.0)}
#: the scale ``prove_build`` reads a plate's lines at (a 0.3 mm pitch is 12 px)
LINE_DENSITY_PX_PER_MM = 40.0

RENDERED_AS = {
    'foil': 'polished metal of its own colour (the flat\'s median under the plate) reflecting the softbox, with a fine '
            'anisotropic foil grain; a hair proud of the board',
    'metallic_ink': 'the ink with a soft broad sheen of the softbox and a fine flake sparkle',
    'emboss': 'relief raised %.2f mm, a %.2f mm shoulder and the board\'s give over the die, lit and shadowed by the '
              'softbox; ink unchanged' % (EMBOSS_HEIGHT_MM, SHOULDER_MM),
    'deboss': 'relief sunk %.2f mm, a %.2f mm shoulder and the board\'s give over the die, lit, shadowed and darkened '
              'in its cavity; ink unchanged' % (DEBOSS_DEPTH_MM, SHOULDER_MM),
    'spot_uv': 'a subtle clear gloss reflecting the softbox; a hair proud of the board',
    'gloss_varnish': 'a subtle clear gloss reflecting the softbox; a hair proud of the board',
    'soft_touch': 'matte: the board\'s sheen removed, nothing added',
}


@dataclass(frozen=True)
class Plate:
    """One finish plate of an .ai: its name and kind as its label says them, its page (1 = the artwork), and the
    label's own box on the page (mm, y down)."""
    plate: str
    kind: str
    page: int
    label_box_mm: tuple


@dataclass
class _Read:
    doc: object
    page_w_mm: float
    page_h_mm: float
    plates: list
    skipped: list
    sha256: str
    pages: int


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _shown(path) -> str:
    """A path as a record says it: repo-relative when it is in the repository."""
    full = Path(path).resolve()
    if REPO in full.parents:
        return str(full.relative_to(REPO))
    return str(full)


def _refuse_day8(path) -> Path:
    """Nothing is written under docs/audit/day-8: a changed byte there breaks Day 8's hash-pinned page."""
    target = Path(path).resolve()
    pinned = DAY8_AUDIT.resolve()
    if target == pinned or pinned in target.parents:
        raise PermissionError('Day 8\'s records are hash-pinned; nothing is written under %s (asked: %s)'
                              % (_shown(pinned), target))
    return target


# =====================================================================================================================
# The plates: read by their labels, the labels removed in memory
# =====================================================================================================================

def _lines(page) -> list:
    """Every text line of a page as its characters, ``[(char, (x0, y0, x1, y1) in pt)]``."""
    out = []
    for block in page.get_text('rawdict')['blocks']:
        if block['type'] != 0:
            continue
        for line in block['lines']:
            out.append([(ch['c'], tuple(ch['bbox'])) for span in line['spans'] for ch in span['chars']])
    return out


def _text(chars) -> str:
    return ''.join(c for c, _box in chars).strip()


def _label(page, number: int):
    """The page's finish-plate label: ``(plate, kind, chars)``, or None when the page has none (not a plate)."""
    found = []
    for chars in _lines(page):
        match = LABEL_RE.match(_text(chars))
        if match is not None:
            found.append((match, chars))
    if not found:
        return None
    if len(found) > 1:
        raise ValueError('page %d carries %d finish-plate labels; a plate has one' % (number, len(found)))
    match, chars = found[0]
    kind = match.group('kind').lower()
    if kind not in FINISH_KINDS:
        raise ValueError('page %d\'s label names %r, a kind no finish has (%s)'
                         % (number, match.group('kind'), ', '.join(FINISH_KINDS)))
    return match.group('plate'), kind, chars


def _box_of(chars) -> tuple:
    return (min(b[0] for _c, b in chars), min(b[1] for _c, b in chars),
            max(b[2] for _c, b in chars), max(b[3] for _c, b in chars))


def _printing(lines) -> dict:
    """Every printing character of a page by what it is: ``{char: [box (pt), ...]}``, each list sorted."""
    out = {}
    for chars in lines:
        for c, box in chars:
            if c.strip():
                out.setdefault(c, []).append(box)
    return {c: sorted(boxes) for c, boxes in out.items()}


def _same_printing(before: dict, after: dict) -> bool:
    """The same characters, each in the same place within CHAR_PLACE_TOLERANCE_PT."""
    if before.keys() != after.keys():
        return False
    for c, boxes in before.items():
        if len(boxes) != len(after[c]):
            return False
        for one, two in zip(boxes, after[c]):
            if max(abs(u - v) for u, v in zip(one, two)) > CHAR_PLACE_TOLERANCE_PT:
                return False
    return True


def _grey(pix) -> np.ndarray:
    if pix.n != 1:
        raise RuntimeError('a plate is read in grey, one channel; got %d' % pix.n)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width)


def _remove_label(page, pristine, chars, number: int) -> None:
    """Remove the label's own characters from ``page`` (in memory) and prove that nothing else moved."""
    import fitz
    label_text = _text(chars)
    others = _printing([line for line in _lines(page) if _text(line) != label_text])
    for _c, box in chars:
        page.add_redact_annot(fitz.Rect(box), fill=False)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                          text=fitz.PDF_REDACT_TEXT_REMOVE)
    after = _lines(page)
    if any(LABEL_RE.match(_text(line)) for line in after):
        raise RuntimeError('page %d: the finish-plate label is still on the page after its removal' % number)
    if not _same_printing(others, _printing(after)):
        raise RuntimeError('page %d: removing the label took the plate\'s own lettering with it (it runs under the '
                           'label); the plate cannot be read whole' % number)
    zoom = GUARD_PX_PER_MM * MM_PER_PT
    matrix = fitz.Matrix(zoom, zoom)
    before_px = _grey(pristine.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY, alpha=False)).astype(np.int16)
    after_px = _grey(page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY, alpha=False)).astype(np.int16)
    if before_px.shape != after_px.shape:
        raise RuntimeError('page %d: the label\'s removal changed the page\'s size' % number)
    x0, y0, x1, y1 = _box_of(chars)
    outside = np.ones(before_px.shape, bool)
    outside[max(int(y0 * zoom) - GUARD_MARGIN_PX, 0):int(math.ceil(y1 * zoom)) + GUARD_MARGIN_PX,
            max(int(x0 * zoom) - GUARD_MARGIN_PX, 0):int(math.ceil(x1 * zoom)) + GUARD_MARGIN_PX] = False
    moved = int(np.abs(before_px - after_px)[outside].max())
    if moved > GUARD_TOLERANCE_LEVELS:
        raise RuntimeError('page %d: the label\'s removal moved the plate outside the label\'s own box (by %d levels)'
                           % (number, moved))


def _plate_like(page) -> bool:
    """A finish plate is a 100 % black mask on white (``pdf_ai._draw_finish_plates``); the inside artboard is colour
    art. True when every inked pixel at PLATE_LIKE_DPI is without colour, or when nothing is inked."""
    import fitz
    pix = page.get_pixmap(dpi=PLATE_LIKE_DPI, colorspace=fitz.csRGB, alpha=False)
    rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3).astype(np.int16)
    ink = rgb.min(axis=-1) < 250
    if not ink.any():
        return True
    chroma = rgb.max(axis=-1) - rgb.min(axis=-1)
    return bool((chroma[ink] <= PLATE_LIKE_CHROMA).all())


def _read_plates(ai_path) -> _Read:
    """The .ai's finish plates (pages 2...), each named by its label, the labels removed in memory. A page with no
    label is the inside artboard only as page 2, before every plate, and only when it is colour art (``_plate_like``):
    skipped and said. Raises for any other unlabelled page — a plate is read by its label, never taken for the inside
    or for nothing — and when a label is unreadable or names no finish kind."""
    import fitz
    ai_path = Path(ai_path)
    doc = fitz.open(str(ai_path))
    pristine = fitz.open(str(ai_path))
    try:
        if doc.page_count < 1:
            raise ValueError('%s has no page' % ai_path)
        rect = doc[0].rect
        plates, skipped = [], []
        for index in range(1, doc.page_count):
            number = index + 1
            page = doc[index]
            if page.rect != rect:
                raise ValueError('page %d of %s is not page 1\'s size: a plate is in register with page 1'
                                 % (number, ai_path.name))
            label = _label(page, number)
            if label is None:
                if plates or number != 2:
                    raise ValueError('page %d of %s has no finish-plate label: only page 2, the inside artboard, may '
                                     'have none; plates are read by their labels' % (number, ai_path.name))
                if _plate_like(page):
                    raise ValueError('page 2 of %s has no finish-plate label and is drawn as a plate (black on white '
                                     'alone, or empty): a plate is read by its label, never taken for the inside'
                                     % ai_path.name)
                skipped.append({'page': number, 'why': 'no finish-plate label, and colour art: the inside artboard, not a plate'})
                continue
            name, kind, chars = label
            _remove_label(page, pristine[index], chars, number)
            plates.append(Plate(plate=name, kind=kind, page=number,
                                label_box_mm=tuple(round(v * MM_PER_PT, 3) for v in _box_of(chars))))
        page_w_mm = rect.width * MM_PER_PT
        page_h_mm = rect.height * MM_PER_PT
        read = _Read(doc=doc, page_w_mm=page_w_mm, page_h_mm=page_h_mm, plates=plates, skipped=skipped,
                     sha256=_sha(ai_path), pages=doc.page_count)
    except BaseException:
        doc.close()
        raise
    finally:
        pristine.close()
    return read


def _coverage(page, *, width_px: int, height_px: int, supersample: int) -> np.ndarray:
    """The plate's share of every pixel (0..1) on a ``width_px`` x ``height_px`` grid over the whole page: rendered at
    ``supersample`` times that grid (each axis scaled on its own, so the grid is met exactly) and averaged down."""
    import fitz
    rect = page.rect
    big_w, big_h = width_px * supersample, height_px * supersample
    pix = page.get_pixmap(matrix=fitz.Matrix(big_w / rect.width, big_h / rect.height), colorspace=fitz.csGRAY,
                          alpha=False)
    grey = _grey(pix)
    if grey.shape[0] < big_h or grey.shape[1] < big_w:
        raise RuntimeError('the plate rendered %s, short of the %d x %d asked' % (grey.shape, big_h, big_w))
    total = grey[:big_h, :big_w].reshape(height_px, supersample, width_px, supersample).sum(axis=(1, 3), dtype=np.int32)
    return (1.0 - total.astype(np.float32) / float(255 * supersample * supersample)).astype(np.float32)


def _page_one(doc, *, width_px: int, height_px: int, supersample: int) -> np.ndarray:
    """The .ai's page 1 (what prints) as 0..255 RGB on the flat's grid, rendered at ``supersample`` times and averaged
    down."""
    import fitz
    page = doc[0]
    rect = page.rect
    big_w, big_h = width_px * supersample, height_px * supersample
    pix = page.get_pixmap(matrix=fitz.Matrix(big_w / rect.width, big_h / rect.height), colorspace=fitz.csRGB,
                          alpha=False)
    rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
    if rgb.shape[0] < big_h or rgb.shape[1] < big_w:
        raise RuntimeError('page 1 rendered %s, short of the %d x %d asked' % (rgb.shape, big_h, big_w))
    total = rgb[:big_h, :big_w, :3].reshape(height_px, supersample, width_px, supersample, 3).sum(axis=(1, 3),
                                                                                                    dtype=np.int32)
    return total.astype(np.float32) / float(supersample * supersample)


def _disk(radius_px: int) -> np.ndarray:
    yy, xx = np.mgrid[-radius_px:radius_px + 1, -radius_px:radius_px + 1]
    return xx * xx + yy * yy <= radius_px * radius_px


def _print_under_depictions(flat: np.ndarray, page_one: np.ndarray, shares) -> tuple:
    """The colours the proof shades, and the record of where they came from. The flat (0..1) is the source; page 1
    (0..255, what prints) is compared with it under every plate. Under a plate the flat depicts (more than
    FLAT_DEPICTS_PCT of its whole pixels differ by more than FLAT_PAGE1_LEVELS) whose kind is in PAGE_1_UNDER, page 1's
    print is taken within the plate's footprint and DEPICT_REACH_PX round it, so a blind relief is seen as relief and
    never as paint the press will not lay. What still differs outside what was taken is said (the residual)."""
    from scipy.ndimage import binary_dilation
    differs = np.abs(flat * 255.0 - page_one).max(axis=2) > FLAT_PAGE1_LEVELS
    taken = np.zeros(differs.shape, bool)
    rows, said = [], []
    for plate, share in shares:
        whole = share >= METAL_WHOLE
        if not whole.any():
            continue
        pct = round(float(differs[whole].mean()) * 100.0, 2)
        depicted = pct > FLAT_DEPICTS_PCT
        swapped = depicted and plate.kind in PAGE_1_UNDER
        rows.append({'plate': plate.plate, 'kind': plate.kind, 'differs_pct': pct, 'page_1_taken': swapped})
        if swapped:
            taken |= binary_dilation(share > 0.0, structure=_disk(DEPICT_REACH_PX))
            said.append('under %s the flat paints what page 1 does not print on %.1f %% of the plate (a preview\'s '
                        'depiction of the %s); the proof shades page 1\'s print there, within %d px of the plate, so '
                        'the %s is seen as the press makes it and not as paint' % (plate.plate, pct, plate.kind,
                                                                                    DEPICT_REACH_PX, plate.kind))
        elif depicted:
            said.append('under %s the flat paints what page 1 does not print on %.1f %% of the plate; the foil is '
                        'drawn as metal there, its colour read from the flat' % (plate.plate, pct))
    shaded = np.where(taken[..., None], page_one / 255.0, flat).astype(np.float32)
    return shaded, {'level': FLAT_PAGE1_LEVELS, 'depicts_pct': FLAT_DEPICTS_PCT,
                    'lid_differs_pct': round(float(differs.mean()) * 100.0, 3), 'plates': rows,
                    'page_1_taken': {'kinds': list(PAGE_1_UNDER), 'reach_px': DEPICT_REACH_PX,
                                     'lid_pct': round(float(taken.mean()) * 100.0, 3)},
                    'residual_differs_pct': round(float((differs & ~taken).mean()) * 100.0, 3),
                    'said': said}


def _plate_row(plate: Plate) -> dict:
    return {'plate': plate.plate, 'kind': plate.kind, 'page': plate.page, 'label_box_mm': list(plate.label_box_mm)}


def _union(layers, kinds, shape) -> np.ndarray:
    out = np.zeros(shape, np.float32)
    for plate, share in layers:
        if plate.kind in kinds:
            np.maximum(out, share, out=out)
    return out


def _coverage_record(read: _Read, layers, *, px_per_mm: float) -> dict:
    lid_mm2 = read.page_w_mm * read.page_h_mm
    if not layers:
        # no plate read: the finish is not measured here — never 0 % (whether any was drawn is the emitter's to say)
        return {'schema': COVERAGE_SCHEMA, 'lid_mm': [round(read.page_w_mm, 3), round(read.page_h_mm, 3)], 'plates': [],
                'foil_and_metallic_pct': None, 'relief_pct': None, 'meets_d9_3': None, 'met_by': [],
                'floors': {'foil_and_metallic_pct': D9_3_METAL_PCT, 'relief_pct': D9_3_RELIEF_PCT},
                'said': 'no plate read: the finish is not measured'}
    rows = []
    for plate, share in layers:
        rows.append(dict(_plate_row(plate), area_pct=round(float(share.mean()) * 100.0, 4),
                         area_mm2=round(float(share.mean()) * lid_mm2, 3)))
    shape = layers[0][1].shape if layers else (1, 1)
    metal = float(_union(layers, ('foil', 'metallic_ink'), shape).mean()) * 100.0
    relief = float(_union(layers, ('emboss', 'deboss'), shape).mean()) * 100.0
    by = [name for name, held in (('metal', metal >= D9_3_METAL_PCT), ('relief', relief >= D9_3_RELIEF_PCT)) if held]
    return {'schema': COVERAGE_SCHEMA, 'lid_mm': [round(read.page_w_mm, 3), round(read.page_h_mm, 3)],
            'plates': rows, 'foil_and_metallic_pct': round(metal, 4), 'relief_pct': round(relief, 4),
            'meets_d9_3': bool(by), 'met_by': by,
            'floors': {'foil_and_metallic_pct': D9_3_METAL_PCT, 'relief_pct': D9_3_RELIEF_PCT},
            'method': 'each plate rasterised at %.1f px/mm (x%d for its edges, averaged down) and its share of every '
                      'pixel summed over the lid (the page); foil + metallic ink and emboss + deboss are unions (the '
                      'larger share of each pixel), never sums; the label removed, never counted' % (
                          px_per_mm, EDGE_SUPERSAMPLE)}


def coverage(ai_path) -> dict:
    """Each plate's area per cent of the lid (the .ai's page); foil + metallic ink and relief (emboss and deboss) as
    unions; ``meets_d9_3``: foil + metallic ink on at least 10 % of the lid, or relief on at least 15 %."""
    read = _read_plates(ai_path)
    try:
        cols_px = int(round(read.page_w_mm * COVERAGE_PX_PER_MM))
        rows_px = int(round(read.page_h_mm * COVERAGE_PX_PER_MM))
        layers = [(plate, _coverage(read.doc[plate.page - 1], width_px=cols_px, height_px=rows_px,
                                    supersample=EDGE_SUPERSAMPLE)) for plate in read.plates]
    finally:
        read.doc.close()
    record = _coverage_record(read, layers, px_per_mm=COVERAGE_PX_PER_MM)
    record['ai'] = {'path': _shown(ai_path), 'sha256': read.sha256, 'pages': read.pages}
    record['skipped_pages'] = read.skipped
    return record


def plate_masks(ai_path, *, px_per_mm: float) -> list:
    """Each plate as a mask (True where the plate covers half a pixel or more) at ``px_per_mm``:
    ``[{"plate", "kind", "page", "label_box_mm", "mask"}]``. What ``line_density`` reads."""
    import fitz
    if px_per_mm is None or not px_per_mm > 0:
        raise ValueError('px_per_mm must be a positive scale; got %r' % (px_per_mm,))
    read = _read_plates(ai_path)
    try:
        cols_px = int(round(read.page_w_mm * px_per_mm))
        rows_px = int(round(read.page_h_mm * px_per_mm))
        out = []
        for plate in read.plates:
            page = read.doc[plate.page - 1]
            rect = page.rect
            grey = _grey(page.get_pixmap(matrix=fitz.Matrix(cols_px / rect.width, rows_px / rect.height),
                                         colorspace=fitz.csGRAY, alpha=False))
            if grey.shape[0] < rows_px or grey.shape[1] < cols_px:
                raise RuntimeError('the plate rendered %s, short of the %d x %d asked' % (grey.shape, rows_px, cols_px))
            out.append(dict(_plate_row(plate), mask=grey[:rows_px, :cols_px] <= INK_LEVEL))
    finally:
        read.doc.close()
    return out


# =====================================================================================================================
# The press's limits: a foil's thin parts and narrow gaps
# =====================================================================================================================

def _opened(mask: np.ndarray, radius_px: float) -> np.ndarray:
    """The morphological opening of ``mask`` by a Euclidean disk of ``radius_px``: every pixel a disk of that radius,
    lying wholly inside the mask, covers. Exact distances (no polygonal kernel), so the radius need not be whole."""
    import cv2
    inner = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) > radius_px
    if not inner.any():
        return inner
    return cv2.distanceTransform((~inner).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) <= radius_px


def _window(listing, zoom: float, rows: tuple, cols: tuple, page_px: tuple) -> np.ndarray:
    """Rows ``rows`` and columns ``cols`` (page pixels at ``zoom`` px/pt) of a plate, grey; outside the page white."""
    import fitz
    r0, r1 = rows
    c0, c1 = cols
    page_rows, page_cols = page_px
    grey = np.full((r1 - r0, c1 - c0), 255, np.uint8)
    pr0, pr1, pc0, pc1 = max(r0, 0), min(r1, page_rows), max(c0, 0), min(c1, page_cols)
    if pr0 >= pr1 or pc0 >= pc1:
        return grey
    pix = listing.get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csGRAY, alpha=False,
                             clip=fitz.Rect(pc0 / zoom, pr0 / zoom, pc1 / zoom, pr1 / zoom))
    got = _grey(pix)
    top, left = int(pix.y), int(pix.x)
    gr0, gr1 = max(pr0, top), min(pr1, top + got.shape[0])
    gc0, gc1 = max(pc0, left), min(pc1, left + got.shape[1])
    grey[gr0 - r0:gr1 - r0, gc0 - c0:gc1 - c0] = got[gr0 - top:gr1 - top, gc0 - left:gc1 - left]
    return grey


def _edge_runs(edge: np.ndarray) -> dict:
    """``{component: [positions]}`` along one edge of a tile's core (0 is no component)."""
    out = {}
    for position in np.nonzero(edge)[0]:
        out.setdefault(int(edge[position]), []).append(int(position))
    return out


def _feret_px(mask: np.ndarray) -> float:
    """A component's run: its Feret length — the longest distance between two of its pixels, over their outer
    corners (a single pixel runs 1; a diagonal hairline its length, not its box's side)."""
    import cv2
    ys, xs = np.nonzero(mask)
    corners = np.concatenate([np.stack([xs + dx, ys + dy], axis=1) for dx in (0, 1) for dy in (0, 1)]).astype(np.float32)
    hull = cv2.convexHull(corners)[:, 0, :].astype(np.float64)
    d = hull[:, None, :] - hull[None, :, :]
    return float(np.sqrt((d ** 2).sum(-1)).max())


def _collect(residue, *, core_rows: int, core_cols: int, valid: int, run_px: float, origin: tuple, acc: dict) -> None:
    """The residue's components that reach the tile's core, judged in the core and ``valid`` pixels round it: one that
    runs ``run_px`` or more counts (a piece: its core pixels, its box, and where it meets the core's edges, so the
    pieces of one part cut by a tile's edge are stitched back exactly), a shorter one is a corner's or an edge's and is
    ignored (counted apart). The run is the component's Feret length (``_feret_px``), so a diagonal part is judged on
    its length. A component longer than ``valid`` runs past it, so it is judged alike in every tile. A gap's closing
    residue stops short of its channel's mouths by about the anti-aliasing tolerance, so a channel within that of the
    run is read as shorter than it is."""
    import cv2
    if not residue.any():
        return
    count, labels, stats, _centres = cv2.connectedComponentsWithStats(residue.astype(np.uint8), connectivity=8)
    inner = labels[valid:valid + core_rows, valid:valid + core_cols]
    in_core = np.bincount(inner.ravel(), minlength=count)
    top, left = origin
    edges = {'top': _edge_runs(inner[0, :]), 'bottom': _edge_runs(inner[-1, :]),
             'left': _edge_runs(inner[:, 0]), 'right': _edge_runs(inner[:, -1])}
    for k in range(1, count):
        pixels = int(in_core[k])
        if pixels == 0:
            continue
        x, y = int(stats[k, cv2.CC_STAT_LEFT]), int(stats[k, cv2.CC_STAT_TOP])
        w, h = int(stats[k, cv2.CC_STAT_WIDTH]), int(stats[k, cv2.CC_STAT_HEIGHT])
        if max(w, h) < run_px:
            run = _feret_px(labels[y:y + h, x:x + w] == k)
            if run < run_px:
                acc['ignored_pieces'] += 1
                acc['ignored_px'] += pixels
                acc['ignored_run_px'] = max(acc['ignored_run_px'], run)
                continue
        acc['px'] += pixels
        bx0, by0 = max(x, valid), max(y, valid)
        bx1, by1 = min(x + w, valid + core_cols), min(y + h, valid + core_rows)
        piece = len(acc['pieces'])
        acc['pieces'].append([pixels, left + bx0 - valid, top + by0 - valid, left + bx1 - valid, top + by1 - valid])
        # where the piece meets the core's edges, keyed by the seam (the page's row or column between two tiles)
        for side, seam, along in (('top', ('h', top), left), ('bottom', ('h', top + core_rows), left),
                                  ('left', ('v', left), top), ('right', ('v', left + core_cols), top)):
            if k not in edges[side]:
                continue
            for position in edges[side][k]:
                acc['seams'].append((seam, side in ('top', 'left'), along + position, piece))


def _stitched(pieces: list, seams: list) -> list:
    """The parts: pieces of one component cut by a tile's edge, stitched where they touch across the seam (8-neighbours),
    as ``[pixels, x0, y0, x1, y1]``. Exact, and linear in the seam pixels."""
    parent = list(range(len(pieces)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    before = {}
    for seam, after_seam, position, piece in seams:
        if not after_seam:
            before.setdefault((seam, position), []).append(piece)
    for seam, after_seam, position, piece in seams:
        if after_seam:
            for near in (position - 1, position, position + 1):
                if (seam, near) not in before:
                    continue
                for other in before[(seam, near)]:
                    a, b = root(piece), root(other)
                    if a != b:
                        parent[a] = b
    parts = {}
    for i, (pixels, x0, y0, x1, y1) in enumerate(pieces):
        part = parts.setdefault(root(i), [0, x0, y0, x1, y1])
        part[0] += pixels
        part[1], part[2] = min(part[1], x0), min(part[2], y0)
        part[3], part[4] = max(part[3], x1), max(part[4], y1)
    return list(parts.values())


def _limits_of(page, *, px_per_mm: float, line_r_px: float, gap_r_px: float, line_run_px: float,
               gap_run_px: float) -> dict:
    """One foil plate's thin parts and narrow gaps, tile by tile at ``px_per_mm``."""
    zoom = px_per_mm * MM_PER_PT
    rect = page.rect
    page_cols = int(math.ceil(rect.width * zoom - 1e-6))
    page_rows = int(math.ceil(rect.height * zoom - 1e-6))
    listing = page.get_displaylist()
    valid = int(math.ceil(max(line_run_px, gap_run_px))) + 2
    margin = valid + int(math.ceil(2.0 * max(line_r_px, gap_r_px))) + 2
    acc = {name: {'px': 0, 'pieces': [], 'seams': [], 'ignored_pieces': 0, 'ignored_px': 0, 'ignored_run_px': 0}
           for name in ('thin', 'gaps')}
    ink_px = 0
    for r0 in range(0, page_rows, LIMITS_TILE_PX):
        for c0 in range(0, page_cols, LIMITS_TILE_PX):
            r1, c1 = min(r0 + LIMITS_TILE_PX, page_rows), min(c0 + LIMITS_TILE_PX, page_cols)
            grey = _window(listing, zoom, (r0 - margin, r1 + margin), (c0 - margin, c1 + margin),
                           (page_rows, page_cols))
            ink = grey <= INK_LEVEL
            if not ink.any():
                continue
            core_rows, core_cols = r1 - r0, c1 - c0
            ink_px += int(ink[margin:margin + core_rows, margin:margin + core_cols].sum())
            judged = slice(margin - valid, margin + core_rows + valid), slice(margin - valid, margin + core_cols + valid)
            thin = (ink & ~_opened(ink, line_r_px))[judged]
            gaps = (~ink & ~_opened(~ink, gap_r_px))[judged]
            for name, residue, run_px in (('thin', thin, line_run_px), ('gaps', gaps, gap_run_px)):
                _collect(residue, core_rows=core_rows, core_cols=core_cols, valid=valid, run_px=run_px,
                         origin=(r0, c0), acc=acc[name])
    mm2_per_px = 1.0 / (px_per_mm * px_per_mm)
    out = {'foil_area_mm2': round(ink_px * mm2_per_px, 4)}
    for name, found in acc.items():
        boxes = sorted(_stitched(found['pieces'], found['seams']), key=lambda b: (-b[0], b[2], b[1]))
        out[name] = {'area_mm2': round(found['px'] * mm2_per_px, 4), 'parts': len(boxes),
                     'boxes_mm': [{'box_mm': [round(v / px_per_mm, 3) for v in b[1:]],
                                   'area_mm2': round(b[0] * mm2_per_px, 4)} for b in boxes[:MAX_BOXES]],
                     'ignored': {'pieces': found['ignored_pieces'],
                                 'area_mm2': round(found['ignored_px'] * mm2_per_px, 4),
                                 'longest_mm': round(found['ignored_run_px'] / px_per_mm, 4)}}
    out['holds'] = out['thin']['parts'] == 0 and out['gaps']['parts'] == 0
    return out


def foil_limits(ai_path, *, min_line_mm=MIN_FOIL_LINE_MM, min_gap_mm=MIN_FOIL_GAP_MM, dpi=LIMITS_DPI, foil_drawn=None) -> dict:
    """Every FOIL plate against the press's limits (D-D9-3: foil lines at least ``min_line_mm``, gaps at least
    ``min_gap_mm``), read at ``dpi``: the parts thinner than the line limit (the pixels a morphological opening with a
    disk of that diameter removes) and the gaps narrower than the gap limit (the pixels a closing with a disk of that
    diameter adds), each as an area in mm2, its parts, up to 20 boxes in mm (largest first) and what the tolerance left
    out. ``holds`` when no foil plate has either. METALLIC_INK plates are reported apart, with their areas: they have no
    foil limit (what is finer than the foil's goes to metallic ink). The anti-aliasing tolerance (AA_TOLERANCE_PX) and
    the run a part must have to count (VIOLATION_RUN) are stated in ``tolerance``. With no foil plate read, ``holds``
    is None (not measured) unless the caller states the build draws no foil (``foil_drawn=False``): a check never passes
    on nothing."""
    for name, value in (('min_line_mm', min_line_mm), ('min_gap_mm', min_gap_mm), ('dpi', dpi)):
        if value is None or not value > 0:
            raise ValueError('%s must be a positive number; got %r' % (name, value))
    px_per_mm = dpi / MM_PER_INCH
    line_r_px = (min_line_mm * px_per_mm - AA_TOLERANCE_PX) / 2.0
    gap_r_px = (min_gap_mm * px_per_mm - AA_TOLERANCE_PX) / 2.0
    if line_r_px < 1.0 or gap_r_px < 1.0:
        raise ValueError('%g dpi is too coarse to read a %g mm line or a %g mm gap' % (dpi, min_line_mm, min_gap_mm))
    line_run_px = VIOLATION_RUN * min_line_mm * px_per_mm
    gap_run_px = VIOLATION_RUN * min_gap_mm * px_per_mm
    read = _read_plates(ai_path)
    foil, metallic, others = [], [], []
    try:
        for plate in read.plates:
            page = read.doc[plate.page - 1]
            if plate.kind == 'foil':
                foil.append(dict(_plate_row(plate), **_limits_of(page, px_per_mm=px_per_mm, line_r_px=line_r_px,
                                                                 gap_r_px=gap_r_px, line_run_px=line_run_px,
                                                                 gap_run_px=gap_run_px)))
            elif plate.kind == 'metallic_ink':
                cols_px = int(round(read.page_w_mm * COVERAGE_PX_PER_MM))
                rows_px = int(round(read.page_h_mm * COVERAGE_PX_PER_MM))
                share = _coverage(page, width_px=cols_px, height_px=rows_px, supersample=EDGE_SUPERSAMPLE)
                metallic.append(dict(_plate_row(plate), area_mm2=round(float(share.mean()) * read.page_w_mm
                                                                       * read.page_h_mm, 3),
                                     limit='none: metallic ink is printed, not stamped; what is finer than the '
                                           'foil\'s limits goes to it'))
            else:
                others.append(_plate_row(plate))
    finally:
        read.doc.close()
    if foil:
        holds = all(row['holds'] for row in foil)
        said = '%d foil plate(s) read' % len(foil)
        failing = ['%s (%d thin part(s), %d gap part(s))' % (row['plate'], row['thin']['parts'], row['gaps']['parts'])
                   for row in foil if not row['holds']]
        if failing:
            said += '; over the limits: ' + ', '.join(failing)
    elif foil_drawn is False:
        holds, said = True, 'no foil drawn (the caller says so): nothing to hold to the foil limits'
    else:
        holds, said = None, 'not measured: no foil plate read'
        if foil_drawn:
            said += ', though the build draws foil'
    return {'schema': LIMITS_SCHEMA, 'ai': {'path': _shown(ai_path), 'sha256': read.sha256, 'pages': read.pages},
            'limits': {'min_line_mm': min_line_mm, 'min_gap_mm': min_gap_mm, 'dpi': dpi},
            'tolerance': {'aa_tolerance_px': AA_TOLERANCE_PX,
                          'aa_tolerance_mm': round(AA_TOLERANCE_PX / px_per_mm, 4),
                          'ink_when_covered': 0.5,
                          'line_disk_mm': round(2.0 * line_r_px / px_per_mm, 4),
                          'gap_disk_mm': round(2.0 * gap_r_px / px_per_mm, 4),
                          'violation_run': VIOLATION_RUN,
                          'line_run_mm': round(line_run_px / px_per_mm, 4),
                          'gap_run_mm': round(gap_run_px / px_per_mm, 4)},
            'foil_plates': foil, 'metallic_ink_plates': metallic, 'other_plates': others,
            'holds': holds, 'said': said}


# =====================================================================================================================
# Line density
# =====================================================================================================================

def _bounds(length_px: int, cell_px: float, cells: int) -> np.ndarray:
    return np.minimum(np.round(np.arange(cells + 1) * cell_px).astype(np.int64), length_px)


def _transitions(ink: np.ndarray, row_bounds: np.ndarray, col_bounds: np.ndarray) -> dict:
    """Per cell and per angle: the ink-to-background changes between neighbouring pixels along the angle, and the
    steps looked at. 0: along x; 90: along y; 45: up and to the right; 135: down and to the right."""
    rows_px = ink.shape[0]
    n_r, n_c = len(row_bounds) - 1, len(col_bounds) - 1
    found = {a: np.zeros((n_r, n_c), np.int64) for a in LINE_ANGLES}
    steps = {a: np.zeros((n_r, n_c), np.int64) for a in LINE_ANGLES}
    for i in range(n_r):
        r0, r1 = int(row_bounds[i]), int(row_bounds[i + 1])
        r1_pair = min(r1, rows_px - 1)
        strip = ink[r0:r1]
        nxt = ink[r0 + 1:r1_pair + 1]
        cur = ink[r0:r1_pair]
        changes = {0: strip[:, 1:] != strip[:, :-1]}
        if r1_pair > r0:
            changes[90] = nxt != cur
            changes[45] = nxt[:, :-1] != cur[:, 1:]
            changes[135] = nxt[:, 1:] != cur[:, :-1]
        for angle, change in changes.items():
            width = change.shape[1]
            starts = np.minimum(col_bounds[:-1], width)
            ends = np.minimum(col_bounds[1:], width)
            column = change.sum(axis=0, dtype=np.int64)
            cum = np.concatenate([[0], np.cumsum(column)])
            found[angle][i] = cum[ends] - cum[starts]
            steps[angle][i] = (ends - starts) * change.shape[0]
    return {'found': found, 'steps': steps}


def _box_sums(a: np.ndarray, k_r: int, k_c: int) -> np.ndarray:
    total = np.zeros((a.shape[0] + 1, a.shape[1] + 1), np.int64)
    total[1:, 1:] = a.cumsum(axis=0).cumsum(axis=1)
    return total[k_r:, k_c:] - total[:-k_r, k_c:] - total[k_r:, :-k_c] + total[:-k_r, :-k_c]


def line_density(mask, *, px_per_mm: float) -> dict:
    """Lines per cm where ``mask`` is densest. A 10 mm window slides over the mask a millimetre at a time; in it, the
    ink-to-background changes along transects at 0, 45, 90 and 135 degrees are counted (every change, both ways, so a
    line is two) and read per centimetre of transect: lines per cm = changes / 2 per 1 cm (a diagonal step is the
    square root of 2 pixels long). Returns the maximum, its window (mm, y down), its angle, and a coarse map of the
    windows a window apart. A float mask is ink where it is 0.5 or more. Read a mask at 40 px/mm or finer: at the
    flat's 8 px/mm a 0.3 mm pitch is barely two pixels. The window's steps are each counted in the row (or column) it
    starts in, so a window's last step reaches one pixel past it — an edge just outside the window is counted (on Day
    9's B-1.3 that one step gives 10.326 lines/cm where the steps wholly inside give 9.851)."""
    if px_per_mm is None or not px_per_mm > 0:
        raise ValueError('px_per_mm must be a positive scale; got %r' % (px_per_mm,))
    ink = np.asarray(mask)
    if ink.ndim != 2:
        raise ValueError('a mask is two-dimensional; got %d dimensions' % ink.ndim)
    if ink.dtype != np.bool_:
        ink = ink >= 0.5
    rows_px, cols_px = ink.shape
    cell_px = LINE_CELL_MM * px_per_mm
    n_r, n_c = int(rows_px // cell_px), int(cols_px // cell_px)
    if n_r < 1 or n_c < 1:
        raise ValueError('the mask (%d x %d px) is smaller than one %.1f mm cell' % (rows_px, cols_px, LINE_CELL_MM))
    counted = _transitions(ink, _bounds(rows_px, cell_px, n_r), _bounds(cols_px, cell_px, n_c))
    cells = int(round(LINE_WINDOW_MM / LINE_CELL_MM))
    k_r, k_c = min(cells, n_r), min(cells, n_c)
    per_cm = {}
    for angle in LINE_ANGLES:
        step_mm = LINE_STEP_PX[angle] / px_per_mm
        found = _box_sums(counted['found'][angle], k_r, k_c).astype(np.float64)
        steps = _box_sums(counted['steps'][angle], k_r, k_c).astype(np.float64)
        with np.errstate(divide='ignore', invalid='ignore'):
            per_cm[angle] = np.where(steps > 0, found / (steps * step_mm) * 10.0 / 2.0, np.nan)
    stack = np.stack([per_cm[a] for a in LINE_ANGLES])
    if np.all(np.isnan(stack)):
        raise ValueError('no transect could be read in the mask')
    best = np.nanargmax(stack)
    a_i, w_i, w_j = np.unravel_index(best, stack.shape)
    best_value = float(stack[a_i, w_i, w_j])
    window = [round(float(w_j) * LINE_CELL_MM, 3), round(float(w_i) * LINE_CELL_MM, 3),
              round(float(w_j + k_c) * LINE_CELL_MM, 3), round(float(w_i + k_r) * LINE_CELL_MM, 3)]
    read = ~np.all(np.isnan(stack), axis=0)
    best_of = np.max(np.where(np.isnan(stack), -1.0, stack), axis=0)
    angle_of = np.take(np.array(LINE_ANGLES), np.argmax(np.where(np.isnan(stack), -1.0, stack), axis=0))
    rows_at = list(range(0, best_of.shape[0], cells))
    cols_at = list(range(0, best_of.shape[1], cells))
    return {'schema': DENSITY_SCHEMA, 'px_per_mm': px_per_mm, 'max_lines_per_cm': round(best_value, 3),
            'window_mm': window, 'angle_deg': int(LINE_ANGLES[a_i]),
            'by_angle': {str(a): round(float(per_cm[a][w_i, w_j]), 3) for a in LINE_ANGLES},
            'window_clipped': bool(k_r < cells or k_c < cells),
            'map': {'step_mm': cells * LINE_CELL_MM, 'window_mm': LINE_WINDOW_MM,
                    'lines_per_cm': [[round(float(best_of[i, j]), 1) if read[i, j] else None for j in cols_at]
                                     for i in rows_at],
                    'angle_deg': [[int(angle_of[i, j]) if read[i, j] else None for j in cols_at] for i in rows_at]},
            'meets_d9_3': best_value >= D9_3_LINES_PER_CM, 'floor_lines_per_cm': D9_3_LINES_PER_CM}


# =====================================================================================================================
# The finish proof
# =====================================================================================================================

def _linear(srgb: np.ndarray) -> np.ndarray:
    return np.where(srgb <= 0.04045, srgb / 12.92, np.power((srgb + 0.055) / 1.055, 2.4)).astype(np.float32)


def _encoded(lin: np.ndarray) -> np.ndarray:
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1.0 / 2.4) - 0.055)


def _noise(seed: int, shape: tuple, sigma_px) -> np.ndarray:
    """A deterministic noise field of unit spread: white noise from ``seed``, blurred by ``sigma_px`` (rows, cols)."""
    from scipy.ndimage import gaussian_filter
    field = gaussian_filter(np.random.default_rng(seed).standard_normal(shape, dtype=np.float32), sigma_px,
                            mode='wrap')
    spread = float(field.std())
    if not spread > 0:
        raise RuntimeError('a noise field of seed %d came out flat' % seed)
    return field / spread


def _down(a: np.ndarray, factor: int) -> np.ndarray:
    rows, cols = a.shape[0] // factor, a.shape[1] // factor
    return a.reshape(rows, factor, cols, factor).mean(axis=(1, 3))


def _same_proportion(cols_px: int, rows_px: int, read: _Read) -> None:
    flat_ratio = cols_px / rows_px
    page_ratio = read.page_w_mm / read.page_h_mm
    if abs(flat_ratio / page_ratio - 1.0) > ASPECT_TOLERANCE:
        raise ValueError('the flat (%d x %d px, %.4f) is not the .ai\'s page (%.2f x %.2f mm, %.4f) in proportion; a '
                         'framed render must be cropped to the lid first, never stretched'
                         % (cols_px, rows_px, flat_ratio, read.page_w_mm, read.page_h_mm, page_ratio))


def _direction(light: Softbox) -> tuple:
    """The light's direction in the image's own axes (x right, y down, z towards the viewer), as plain floats (a numpy
    float64 would turn every float32 field it touches into float64)."""
    az, el = math.radians(light.azimuth_deg), math.radians(light.elevation_deg)
    return math.cos(el) * math.cos(az), -math.cos(el) * math.sin(az), math.sin(el)


def _smooth(lo: float, hi: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _box(cos_to_box: np.ndarray, radius_deg: float, soft_deg: float) -> np.ndarray:
    """What a reflection sees of the box: 1 within ``radius_deg`` of its centre, nothing past a further ``soft_deg``."""
    return _smooth(math.cos(math.radians(radius_deg + soft_deg)), math.cos(math.radians(radius_deg)), cos_to_box)


def _metal_colour(flat: np.ndarray, share: np.ndarray):
    """The foil's own colour: the flat's median under the plate, read where the plate covers a pixel whole. A plate with
    fewer than METAL_LEAST_WHOLE_PX whole pixels (fine foil lines, never a whole pixel wide at the flat's scale) adds
    the pixels it covers from METAL_UNMIX_LEAST, each un-mixed from the bare ground beside it (the flat's colour where
    the plate is not, within METAL_GROUND_REACH_PX), so a guilloche of 0.12 mm foil lines is read as its metal and not
    as metal blended with the ground. None when no pixel can be read."""
    from scipy.ndimage import gaussian_filter
    whole = share >= METAL_WHOLE
    if int(whole.sum()) >= METAL_LEAST_WHOLE_PX:
        return np.median(flat[whole], axis=0)
    part = (share >= METAL_UNMIX_LEAST) & ~whole
    bare = (share < METAL_BARE).astype(np.float32)
    reach = gaussian_filter(bare, METAL_GROUND_REACH_PX, mode='nearest')
    ground = np.stack([gaussian_filter(flat[..., c] * bare, METAL_GROUND_REACH_PX, mode='nearest') for c in range(3)],
                      axis=-1)
    readable = part & (reach >= METAL_GROUND_LEAST)
    s = share[readable][:, None]
    beside = ground[readable] / reach[readable][:, None]
    unmixed = np.clip((flat[readable] - (1.0 - s) * beside) / s, 0.0, 1.0)
    samples = np.concatenate([flat[whole], unmixed], axis=0)
    if samples.shape[0] == 0:
        return None
    return np.median(samples, axis=0)


def _shade(layers, *, shape: tuple, px_per_mm: float, page_mm: tuple, light: Softbox, factor: int) -> dict:
    """The height field (mm) on the fine grid, its normals, and every shading term, each averaged down by ``factor``
    to the flat's grid before it is kept. float32 throughout; the large fields are let go as soon as they are used."""
    from scipy.ndimage import gaussian_filter
    relief_sigma_px = SHOULDER_MM / GAUSS_RISE * px_per_mm
    pillow_px = PILLOW_MM * px_per_mm
    edge_sigma_px = FOIL_EDGE_MM * px_per_mm

    def shaped(share):
        return ((1.0 - PILLOW_SHARE) * gaussian_filter(share, relief_sigma_px, mode='nearest')
                + PILLOW_SHARE * gaussian_filter(share, pillow_px, mode='nearest'))

    relief = (EMBOSS_HEIGHT_MM * shaped(_union(layers, ('emboss',), shape))
              - DEBOSS_DEPTH_MM * shaped(_union(layers, ('deboss',), shape)))
    height = relief + COAT_HEIGHT_MM * gaussian_filter(_union(layers, ('spot_uv', 'gloss_varnish'), shape),
                                                       edge_sigma_px, mode='nearest')
    tooth_px = BOARD_TOOTH_SIZE_MM * px_per_mm
    height += BOARD_TOOTH_MM * _noise(SEEDS['board_tooth'], shape, (tooth_px, tooth_px))
    kept = {}
    foil = _union(layers, ('foil',), shape)
    if foil.any():
        height += FOIL_HEIGHT_MM * gaussian_filter(foil, edge_sigma_px, mode='nearest')
        grain = _noise(SEEDS['foil_grain'], shape, (FOIL_GRAIN_WIDTH_MM * px_per_mm, FOIL_GRAIN_LENGTH_MM * px_per_mm))
        height += FOIL_GRAIN_MM * grain * foil
        kept['foil_tone'] = _down(1.0 + FOIL_GRAIN_TONE * grain, factor)
        del grain
    del foil
    cavity = np.clip((gaussian_filter(relief, OCCLUSION_REACH_MM * px_per_mm, mode='nearest') - relief)
                     / DEBOSS_DEPTH_MM, 0.0, 1.0) * np.clip(-relief / (0.1 * DEBOSS_DEPTH_MM), 0.0, 1.0)
    del relief
    slope_y, slope_x = np.gradient(height, 1.0 / px_per_mm)
    del height
    nz = 1.0 / np.sqrt(slope_x * slope_x + slope_y * slope_y + 1.0)
    nx, ny = -slope_x * nz, -slope_y * nz
    del slope_x, slope_y
    lx, ly, lz = _direction(light)
    n_dot_l = nx * lx + ny * ly + nz * lz
    kept['diffuse'] = _down((light.ambient + (1.0 - light.ambient) * np.maximum(n_dot_l, 0.0) / lz)
                            * (1.0 - OCCLUSION * cavity), factor)
    del cavity
    # reflections, seen from a point straight above the lid's centre (the image itself stays orthographic): with v the
    # unit vector to that point, the reflection is r = 2 (n.v) n - v, so r.l = 2 (n.v)(n.l) - v.l
    rows, cols = shape
    w_mm, h_mm = page_mm
    vx = ((w_mm / 2.0 - (np.arange(cols, dtype=np.float32) + 0.5) / px_per_mm) / light.view_mm)[None, :]
    vy = ((h_mm / 2.0 - (np.arange(rows, dtype=np.float32) + 0.5) / px_per_mm) / light.view_mm)[:, None]
    inv_len = 1.0 / np.sqrt(vx * vx + vy * vy + 1.0)
    v_dot_l = (vx * lx + vy * ly + lz) * inv_len
    n_dot_v = (nx * vx + ny * vy + nz) * inv_len
    del nx, ny, nz
    cos_box = 2.0 * n_dot_v * n_dot_l - v_dot_l
    flat_cos_box = 2.0 * inv_len * lz - v_dot_l
    del n_dot_v, n_dot_l, v_dot_l, inv_len
    box = _box(cos_box, light.radius_deg, light.soft_deg)
    kept['board_sheen'] = _down(BOARD_SHEEN * np.maximum(box - _box(flat_cos_box, light.radius_deg, light.soft_deg),
                                                         0.0), factor)
    kept['foil_box'] = _down(FOIL_BOX * box, factor)
    del box, flat_cos_box
    kept['foil_hot'] = _down(FOIL_HOT * _box(cos_box, light.core_deg, light.core_deg), factor)
    kept['metallic_box'] = _down(_box(cos_box, light.radius_deg, METALLIC_SOFTER * light.soft_deg), factor)
    kept['gloss'] = _down(GLOSS * _box(cos_box, light.radius_deg, GLOSS_SOFT_DEG), factor)
    del cos_box
    fibre = _noise(SEEDS['board_fibre'], shape, (BOARD_FIBRE_MM[0] * px_per_mm, BOARD_FIBRE_MM[1] * px_per_mm))
    mottle_px = BOARD_MOTTLE_MM * px_per_mm
    fibre += _noise(SEEDS['board_mottle'], shape, (mottle_px, mottle_px))
    kept['albedo'] = _down(1.0 + BOARD_MOTTLE / math.sqrt(2.0) * fibre, factor)
    del fibre
    if any(plate.kind == 'metallic_ink' for plate, _share in layers):
        flake_px = METALLIC_FLAKE_MM * px_per_mm
        kept['flake'] = _down(1.0 + METALLIC_FLAKE * _noise(SEEDS['metallic_flake'], shape, (flake_px, flake_px)),
                              factor)
    return kept


def render_proof(flat_png, ai_path, out_png, *, light=SOFTBOX) -> dict:
    """D-D9-6: the finish proof of a build: its flat lid (``flat_png``, the .ai's page 1 rendered, uncropped and
    unframed) front-on, its finishes rendered as materials from the .ai's finish plates under ONE fixed softbox
    (``light``): foil as polished metal of its own colour (the flat's median under the foil) with a strong reflection
    of the softbox and a fine anisotropic foil grain; metallic ink as a soft broad sheen; emboss and deboss as relief,
    lit and shadowed, the ink unchanged; spot UV or gloss as a subtle gloss; the board's fine texture everywhere. A
    height field (board 0, emboss up, deboss down, soft shoulders; foil a hair up) gives the normals; the shading is
    computed at SHADE_SUPERSAMPLE x the flat's grid and averaged down. No perspective, no scene, no shadow outside the
    relief; fixed seeds and no time in the file, so the same inputs write the same bytes. The flat's colours are shaded,
    except under a plate the flat DEPICTS (it paints there what the .ai's page 1 does not print, such as a blind deboss
    drawn tone on tone): for a clear finish or a metallic ink, page 1's print is shaded there instead, so the finish is
    rendered once, as the press makes it, and never as paint (foil is never swapped). Returns the record: the plates
    read (name, kind, area per cent), the light, the seeds and the output's sha256; and ``flat_against_page_1``: where
    the flat and page 1 differ, what was taken from page 1, and what still differs outside it."""
    from PIL import Image as PILImage
    out_png = _refuse_day8(out_png)
    flat_png, ai_path = Path(flat_png), Path(ai_path)
    with PILImage.open(flat_png) as im:
        flat = np.asarray(im.convert('RGB'), dtype=np.float32) / 255.0
    rows_px, cols_px = flat.shape[:2]
    read = _read_plates(ai_path)
    try:
        _same_proportion(cols_px, rows_px, read)
        ss = SHADE_SUPERSAMPLE
        fine = (rows_px * ss, cols_px * ss)
        layers = [(plate, _coverage(read.doc[plate.page - 1], width_px=fine[1], height_px=fine[0],
                                    supersample=EDGE_SUPERSAMPLE)) for plate in read.plates]
        page_one = _page_one(read.doc, width_px=cols_px, height_px=rows_px, supersample=EDGE_SUPERSAMPLE * ss)
    finally:
        read.doc.close()
    page_mm = (read.page_w_mm, read.page_h_mm)
    px_per_mm = (fine[1] / read.page_w_mm + fine[0] / read.page_h_mm) / 2.0
    terms = _shade(layers, shape=fine, px_per_mm=px_per_mm, page_mm=page_mm, light=light, factor=ss)
    at = {name: term[..., None] for name, term in terms.items()}
    shares = [(plate, _down(share, ss)) for plate, share in layers]
    soft = _down(_union(layers, ('soft_touch',), fine), ss)[..., None]
    coat = _down(_union(layers, ('spot_uv', 'gloss_varnish'), fine), ss)[..., None]
    shaded, against = _print_under_depictions(flat, page_one, shares)
    if against['residual_differs_pct'] > FLAT_RESIDUAL_MAX_PCT:
        raise ValueError('the flat differs from the .ai\'s page 1 on %.1f %% of the lid outside its depicted plates '
                         '(bound %.0f %%): it is not this file\'s flat' % (against['residual_differs_pct'], FLAT_RESIDUAL_MAX_PCT))
    base = _linear(shaded)
    out = base * at['diffuse'] * at['albedo'] + at['board_sheen'] * (1.0 - soft)
    metals = []
    for plate, share in shares:
        if plate.kind == 'metallic_ink':
            tint = base + METALLIC_TINT * (1.0 - base)
            inked = (out * (1.0 - METALLIC_OFF_ANGLE * (1.0 - at['metallic_box']))
                     + METALLIC_SHEEN * at['metallic_box'] * tint) * at['flake']
            out = out * (1.0 - share[..., None]) + inked * share[..., None]
    out = out * (1.0 - GLOSS_DEEPEN * coat) + coat * at['gloss']
    for plate, share in shares:
        if plate.kind != 'foil':
            continue
        colour = _metal_colour(flat, share)
        if colour is None:
            metals.append({'plate': plate.plate, 'metal': None, 'said': 'the plate covers no pixel: nothing drawn'})
            continue
        metal = _linear(np.asarray(colour, np.float32))
        lit = metal + FOIL_BOX_WHITEN * (1.0 - metal)
        hot = metal + FOIL_HOT_WHITEN * (1.0 - metal)
        foil_rgb = (metal * FOIL_ROOM + lit * at['foil_box']) * at['foil_tone'] + hot * at['foil_hot']
        out = out * (1.0 - share[..., None]) + foil_rgb * share[..., None]
        metals.append({'plate': plate.plate, 'metal': '#%02X%02X%02X' % tuple(int(round(v * 255)) for v in colour)})
    pixels = np.rint(_encoded(out) * 255.0).astype(np.uint8)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    PILImage.fromarray(pixels, 'RGB').save(out_png, format='PNG', compress_level=9)
    to_light = _direction(light)
    coverage_part = _coverage_record(read, layers, px_per_mm=px_per_mm)
    from_page_1 = {row['plate'] for row in against['plates'] if row['page_1_taken']}
    plates = []
    for row in coverage_part['plates']:
        plates.append(dict(row, rendered_as=RENDERED_AS[row['kind']],
                           colours_from=('page 1\'s print (the flat depicts this finish)'
                                         if row['plate'] in from_page_1 else 'the flat')))
    return {'schema': SCHEMA,
            'flat': {'path': _shown(flat_png), 'sha256': _sha(flat_png), 'size_px': [cols_px, rows_px]},
            'ai': {'path': _shown(ai_path), 'sha256': read.sha256, 'pages': read.pages},
            'lid_mm': coverage_part['lid_mm'],
            'grid': {'px_per_mm': round(cols_px / read.page_w_mm, 4), 'shade_supersample': ss,
                     'edge_supersample': EDGE_SUPERSAMPLE},
            'plates': plates, 'metals': metals, 'skipped_pages': read.skipped,
            'flat_against_page_1': against,
            'coverage': {k: coverage_part[k] for k in ('foil_and_metallic_pct', 'relief_pct', 'meets_d9_3', 'met_by')},
            'light': dict(asdict(light), kind='one fixed softbox',
                          direction=[round(float(v), 6) for v in to_light],
                          camera='orthographic, front-on: no perspective, no scene; reflections seen from view_mm '
                                 'above the lid\'s centre'),
            'seeds': dict(SEEDS),
            'relief': {'emboss_height_mm': EMBOSS_HEIGHT_MM, 'deboss_depth_mm': DEBOSS_DEPTH_MM,
                       'foil_height_mm': FOIL_HEIGHT_MM, 'coat_height_mm': COAT_HEIGHT_MM,
                       'shoulder_10_90_mm': SHOULDER_MM, 'shoulder_sigma_mm': round(SHOULDER_MM / GAUSS_RISE, 4),
                       'pillow_share': PILLOW_SHARE, 'pillow_sigma_mm': PILLOW_MM,
                       'foil_edge_sigma_mm': FOIL_EDGE_MM},
            'out': {'path': _shown(out_png), 'sha256': _sha(out_png), 'size_px': [cols_px, rows_px]}}


def prove_build(flat_png, ai_path, out_dir, *, light=SOFTBOX, foil_drawn=None) -> dict:
    """D-D9-6 and D-D9-3 for one build: ``out_dir/finish-proof.png`` (``render_proof``) and ``out_dir/record.json``:
    the proof's record, the plates' coverage, the foil limits, and each plate's line density read at
    LINE_DENSITY_PX_PER_MM. Never under docs/audit/day-8."""
    out_dir = _refuse_day8(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    record = render_proof(flat_png, ai_path, out_dir / 'finish-proof.png', light=light)
    record['coverage'] = coverage(ai_path)
    record['foil_limits'] = foil_limits(ai_path, foil_drawn=foil_drawn)
    record['line_density'] = []
    for row in plate_masks(ai_path, px_per_mm=LINE_DENSITY_PX_PER_MM):
        mask = row.pop('mask')
        if mask.any():
            row.update(line_density(mask, px_per_mm=LINE_DENSITY_PX_PER_MM))
        else:
            row['said'] = 'the plate covers nothing at this scale'
        record['line_density'].append(row)
    (out_dir / 'record.json').write_text(json.dumps(record, indent=1, sort_keys=True, ensure_ascii=False) + '\n')
    return record
