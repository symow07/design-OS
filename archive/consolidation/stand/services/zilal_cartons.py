"""Day 12 §4 (D-D12-5) and its one repair (D-D12-8; the designer's eye, round 0) — the stick cartons' fronts, composed
by the engine at $0 from the wrap's arrangement (D-D11-7: "front = the stones and the hero"), and the carton built by
``stick_carton.build`` in Ẓilāl's colours: the Day 12 box's record (its ground, its copy ink, its logo's ink), each
recorded with where it came from; the barcode's ground stays white by rule.

THE FRONT is one picture covering the front's ground box (600 PPI); nothing in it is drawn by a model and nothing is
redrawn — every pixel of art is the wrap's or the lid's own, scaled or moved:

- THE GROUND: one calm indigo in the carton's ground colour across the whole front, with a fine grain whose mean is that
  colour (zero-mean in L*, seeded): no patch, tile, mirror or vignette. It meets the other panels' flat ground at both
  folds, measured on the written file (``across_fold``: mean ΔE00 ≤ 2 across each fold).
- THE LOCKUP: the whole of أحمر شفاه, "Enchanted Rose" and LIPSTICK, carried from the closed wrap's own page (its PDF
  rendered: the painted hero pair, the traced logotype, the set line), cut by its own ink — a soft alpha from each
  pixel's ΔE to the wrap's ground, from the ground's grain ceiling up over 10 ΔE — and held to the words by the wrap's
  own vector silhouettes (the hero pair's carriers, the logotype; LIPSTICK, set as text, by its ink box), the hold
  full within 0.3 mm of them and gone by 0.5 mm, so no stone of the wrap comes with it and no box edge exists; the
  wrap's ground under a soft edge is exchanged for the carton's. It is scaled as one piece so its widest line (the
  alpha's own extent) fills 98 % of the front's safe width, centred, below the thumb notch's keep-out.
- THE DRIFT: beneath LIPSTICK, the lid's own small stones at LID SCALE (1 mm on the lid = 1 mm on the carton, never
  enlarged) from a region of the Day 12 lid's plate clear of every word (``refuse_near_words``: the lid's hero, name,
  logo and small lines, 2 mm), each stone cut by its own contour with a soft edge; a stone the region's edge would cut
  is left out, and so is anything larger than a small stone. The rest of the front is calm.
- THE DRIFT, Day 13 (§1.1, D-D13-8: the last repair, after the eye's round 1 read "three tiny flat pebbles, out of
  proportion with the hero ... About 60% of the front below them is empty indigo"): ``drift_source='wrap'`` cuts it from
  the closed wrap's own print plate instead — the same bank at the wrap's scale (1 mm on the wrap = 1 mm on the carton),
  ONE window of the wrap laid on the front as if the wrap had been unrolled onto it (no rotation, rescale, re-centring,
  tiling or mirror; read round the wrap's seam if the window crosses it), every pixel of the bank kept (the stones,
  their copper outlines and veins, the threads), cut by its own ink; the window's edge cuts a stone as the wrap's trim
  and seam cut it. The window, the coverage measure and its tolerance are written (drift-plan.json, ``write_plan``)
  BEFORE the front is built, and the front's record measures them back from the written picture.
  ``drift_source='lid'`` (the default) is Day 12's drift, unchanged.

The front's record (carton-front.json) carries the lockup's box on the panel, its scale and its clearance to each side
of the safe area and to the notch's keep-out; the drift's source (the lid's region, or the wrap's window) and its scale;
the fold continuity and the lockup read back from the written file — all computed (``lockup_clearance``,
``across_fold``, ``readback``)."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import stick_carton as sc
from apps.pipeline.services import zilal_lipstick_master as zlm

DAY12 = lm.REPO / 'docs' / 'audit' / 'day-12'
DAY13 = lm.REPO / 'docs' / 'audit' / 'day-13'
SCHEMA = 'day12_carton_front/2'                             # the front whose drift is the lid's (Day 12)
SCHEMA_WRAP = 'day13_carton_front/1'                        # the front whose drift is cut from the wrap (Day 13 §1.1)
DRIFT_SOURCES = ('lid', 'wrap')
BOX_RECORD = DAY12 / 'zilal' / 'box' / 'box.json'           # Ẓilāl's colours (the Day 12 box)
LID_PLATE = DAY12 / 'zilal' / 'lid' / 'engine' / 'plate.png'
LID_MASTER = DAY12 / 'zilal' / 'lid' / 'master.json'

FRONT_PPI = 600.0
FRONT_PX_PER_MM = FRONT_PPI / lm.MM_PER_INCH
SAFE_FILL = 0.98                     # the lockup's widest line fills 98 % of the front's safe width
ALPHA_SEEN = 1.0 / 255.0             # art counts as drawn where its alpha moves the ground by one 8-bit level

GRAIN_L = 0.5                        # the ground's grain: L* standard deviation, zero mean (the lid's own reads ~1)
GRAIN_BLUR_PX = 0.6                  # its grain size at 600 PPI (a fine paper tooth, not a texture)
GRAIN_SEED = 20261024

LOCKUP_PASSES = 4                    # the lockup read again (a little smaller) until its cut fits the 98 %
WRAP_READ_PX_PER_MM = 60.0           # the wrap's page read at 60 px/mm to measure its lockup (its painted pair: 27.65)
LOCKUP_PAD_MM = 1.2                  # the wrap's window: the words' boxes grown 1.2 mm (the alpha is 0 on its edge)
WORDS_HELD_MM = (0.3, 0.5)           # the alpha held to the words: whole within 0.3 mm of them, gone by 0.5 mm
GRAIN_RING_MM = 0.7                  # the ground's grain read in a ring this wide just past the hold
GRAIN_CEILING_PCT = 99.5             # ... its 99.5th percentile ΔE76 is the ink's floor (the ground's grain maps to 0)
GROUND_DE_MAX = 6.0                  # ... over its ground pixels: within 6 ΔE76 of the ground,
GROUND_CLEAR_MM = 0.2                # ... and 0.2 mm clear of any pixel farther (a stone, a thread, a letter)
INK_RAMP_DE = 10.0                   # the alpha rises from the floor to 1 over 10 ΔE76
LOCKUP_BELOW_NOTCH_MM = 2.0          # the lockup's top this far below the thumb notch's keep-out

LID_DRIFT_REGION_MM = (107.0, 78.0, 123.0, 90.0)   # on the 190 × 120 lid: its small scattered stones (lilac, copper,
                                                   # teal) between the hero and the lower drift; read by window search
LID_WORDS_CLEAR_MM = 2.0             # the region stands this far clear of every word box on the lid
STONE_DE = 6.0                       # a lid pixel this far (ΔE76) from the lid's ground belongs to a stone or a thread
STONE_MAX_MM = 4.5                   # a small stone: its box no larger than 4.5 mm either way
STONE_MIN_MM2 = 0.3                  # ... and no smaller than 0.3 mm² (a speck of shading is not a stone)
STONE_LIFT_L = 8.0                   # ... and lighter than the ground by 8 L* on average (a shadow is not a stone)
STONE_EDGE_MM = (0.1, 0.25)          # each stone's alpha held to its contour: whole within 0.1 mm, gone by 0.25 mm
STONE_BODY_EDGE_MM = 0.06            # each stone's body solid (its tooth is the stone's), its own edge soft over 0.06 mm
DRIFT_BELOW_LIPSTICK_MM = 2.5        # the drift's top this far below LIPSTICK's ink

FOLD_STRIP_MM = (0.75, 1.5)          # the fold read 0.75–1.5 mm each side of the crease (past the 0.5 mm overlap)
FOLD_BIN_MM = 1.0                    # per 1 mm of the fold's length
FOLD_END_MM = 1.0                    # the fold read from 1 mm below the panel's top to 1 mm above its foot
FOLD_PPI = 600.0
FOLD_DE00_MAX = 2.0
READBACK_DE00 = 3.0                  # the read-back lockup: pixels at least 3 ΔE00 off the ground
READBACK_TOL_MM = 0.05

# Day 13 §1.1 — the drift cut from the wrap's own plate (``drift_source='wrap'``)
PLAN_SCHEMA = 'day13_carton_drift_plan/1'
PLAN_NAME = 'drift-plan.json'        # the window and the coverage measure, written before the front is built
WRAP_WORDS_CLEAR_MM = zlm.STONE_TEXT_CLEAR_MM   # the words' zone on the wrap: their boxes grown 1.5 mm (the wrap's own
                                                # rule for reading stones clear of its words); no window pixel inside it
WRAP_TRIM_MM = (zlm.BLEED_TB_MM, zlm.WRAP_MM[1] - zlm.BLEED_TB_MM)   # the wrap's trim, y 1–41 mm (its 1 mm bleed off)
WRAP_TOOTH_MM2 = 0.01                # a hole in the stones' mask up to 0.01 mm² is the paper's tooth inside a stone
                                     # (filled); a larger one is ground between stones and veins (kept as ground, never
                                     # carried as a patch)
WRAP_READ_MARGIN_MM = 0.5            # the plate read 0.5 mm past the window, so each edge pixel's cut sees its neighbours
WRAP_BODY_ERODE_MM = 0.5             # the stones told apart (the tolerance's largest stone): the mask eroded 0.5 mm (the
                                     # copper outlines and veins away, and where two stones' outlines run together — at
                                     # 0.2 mm the lilac, teal and coral stones still read as one), the largest body grown
                                     # back 0.5 mm inside it
AREA_SUPERSAMPLE = 4                 # the plate drawn pixel by pixel on a grid 4× the front's, then averaged by area
MAP_CELL_MM = (8.0, 6.0)             # the wrap's stone map: its share per 8 mm column by 6 mm row
CANDIDATE_STEP_MM = 0.25             # the densest window of the same size looked for every 0.25 mm round the wrap


def products(day12=DAY12):
    """The two sticks' carton products (stick_carton.PRODUCTS) with their folders under the day's root ``day12`` (Day
    12's by default; ``build``'s ``out_root`` passes Day 13's)."""
    return {'lipstick': dict(sc.PRODUCTS['lipstick'], out=day12 / 'lipstick' / 'carton'),
            'lip_balm': dict(sc.PRODUCTS['lip_balm'], out=day12 / 'balm' / 'carton')}


# --- the colours -------------------------------------------------------------------------------------------------------

def carton_colours(box_record):
    """Ẓilāl's colours for the carton, from the Day 12 box's record: its ground, its copy ink and its logo's ink; the
    barcode's ground stays white (a symbol prints dark bars on a light ground). Returns (colours, where each came
    from)."""
    rec = json.loads(Path(box_record).read_text(encoding='utf-8'))
    colours = {'ground': rec['ground'], 'ink': rec['ink'], 'logo': rec['logo_ink'],
               'ean_ground': sc.PLACEHOLDER_COLOURS['ean_ground']}
    source = {'record': lm.rel(box_record), 'sha256': lm.sha256(box_record),
              'from': {'ground': 'box.json: ground', 'ink': 'box.json: ink', 'logo': 'box.json: logo_ink',
                       'ean_ground': 'white by rule (stick_carton: a symbol prints dark bars on a light ground) — '
                                     'the same white as the placeholder\'s, so stick_carton\'s by-value '
                                     'colours_placeholder lists it'}}
    return colours, source


def hex_rgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float64)


def rgb_hex(rgb):
    return '#%02X%02X%02X' % tuple(int(round(v)) for v in rgb)


# --- the pieces --------------------------------------------------------------------------------------------------------

def held(mask, px_per_mm, full_mm, none_mm):
    """A weight held to ``mask``: 1 within ``full_mm`` of it, falling linearly to 0 at ``none_mm``."""
    dist = cv2.distanceTransform((~mask).astype(np.uint8), cv2.DIST_L2, 5) / px_per_mm
    return np.clip((none_mm - dist) / (none_mm - full_mm), 0.0, 1.0)


def ring(mask, px_per_mm, inner_mm, outer_mm):
    """The pixels between ``inner_mm`` and ``outer_mm`` of ``mask``."""
    dist = cv2.distanceTransform((~mask).astype(np.uint8), cv2.DIST_L2, 5) / px_per_mm
    return (dist > inner_mm) & (dist <= outer_mm)


def ink_alpha(rgb, ground_rgb, hold, floor_de):
    """The cut's alpha: each pixel's ΔE76 to the source's ground, 0 at the floor and 1 at the floor + INK_RAMP_DE,
    times the hold."""
    lab = lm.srgb_to_lab(rgb)
    dist = np.linalg.norm(lab - lm.srgb_to_lab(ground_rgb[None, :])[0], axis=-1)
    return np.clip((dist - floor_de) / INK_RAMP_DE, 0.0, 1.0) * hold


def premultiplied(rgb, alpha, ground_rgb, carton_ground_rgb):
    """The cut's colour premultiplied, the source's ground under a soft edge exchanged for the carton's
    (I + (1 − α)(G_carton − G_source): the edge meets the carton's ground, the solid ink is untouched)."""
    colour = rgb + (1.0 - alpha)[..., None] * (carton_ground_rgb - ground_rgb)
    return np.clip(colour, 0, 255) * alpha[..., None]


def ink_cut(rgb, ground_rgb, hold, floor_de, carton_ground_rgb):
    """The cut (``ink_alpha``) and its premultiplied colour (``premultiplied``)."""
    alpha = ink_alpha(rgb, ground_rgb, hold, floor_de)
    return premultiplied(rgb, alpha, ground_rgb, carton_ground_rgb), alpha


def solid(mask):
    """A stone's body: its mask closed (3 px) and its holes filled — the paper's tooth inside a stone is the stone."""
    closed = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    pad = np.pad(closed, 1)
    flood = pad.copy()
    cv2.floodFill(flood, np.zeros((pad.shape[0] + 2, pad.shape[1] + 2), np.uint8), (0, 0), 1)
    holes = (flood == 0)[1:-1, 1:-1]
    return (closed > 0) | holes


def border_alpha(alpha):
    """The largest alpha on the four edges of a cut's window: 0 means no edge of the window cuts the art."""
    return float(max(alpha[0].max(), alpha[-1].max(), alpha[:, 0].max(), alpha[:, -1].max()))


def extent(alpha, threshold):
    """The box (x0, y0, x1, y1, pixel edges) of the pixels whose alpha is over ``threshold``."""
    ys, xs = np.nonzero(alpha > threshold)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def render_page(page, clip_mm, px_per_mm, gray):
    """A PDF page's ``clip_mm`` rendered at ``px_per_mm`` (its first pixel on the grid): the pixels and the mm of the
    first pixel's corner."""
    import fitz
    k = px_per_mm * lm.MM_PER_INCH / 72.0
    pt = 72.0 / lm.MM_PER_INCH
    x0, y0 = np.floor(clip_mm[0] * px_per_mm) / px_per_mm, np.floor(clip_mm[1] * px_per_mm) / px_per_mm
    x1, y1 = np.ceil(clip_mm[2] * px_per_mm) / px_per_mm, np.ceil(clip_mm[3] * px_per_mm) / px_per_mm
    cs = fitz.csRGB
    if gray:
        cs = fitz.csGRAY
    pix = page.get_pixmap(matrix=fitz.Matrix(k, k), clip=fitz.Rect(x0 * pt, y0 * pt, x1 * pt, y1 * pt), alpha=False,
                          colorspace=cs)
    arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n).astype(np.float64)
    return arr, (pix.x / px_per_mm, pix.y / px_per_mm)


def word_silhouettes(page, boxes_mm):
    """The wrap's words as its own vectors draw them: every filled path on its page that stands on a word's box (the
    hero pair's carriers, the logotype), redrawn solid on a blank page of its size; a word with no path of its own (a
    line set as text) by its ink box. Returns the page (its document kept open with it) and the words drawn by box."""
    import fitz
    pt = 72.0 / lm.MM_PER_INCH
    doc = fitz.open()
    blank = doc.new_page(width=page.rect.width, height=page.rect.height)
    shape = blank.new_shape()
    by_path = set()
    for dr in page.get_drawings():
        if dr['type'] not in ('f', 'fs'):
            continue
        r = dr['rect']
        rmm = (r.x0 / pt, r.y0 / pt, r.x1 / pt, r.y1 / pt)
        on = [key for key, b in boxes_mm.items()
              if min(rmm[2], b[2]) - max(rmm[0], b[0]) > 0 and min(rmm[3], b[3]) - max(rmm[1], b[1]) > 0]
        if not on:
            continue
        by_path.update(on)
        for it in dr['items']:
            if it[0] == 'l':
                shape.draw_line(it[1], it[2])
            elif it[0] == 'c':
                shape.draw_bezier(it[1], it[2], it[3], it[4])
            elif it[0] == 're':
                shape.draw_rect(it[1])
            elif it[0] == 'qu':
                shape.draw_quad(it[1])
        shape.finish(fill=(0, 0, 0), color=None, even_odd=bool(dr['even_odd']))
    by_box = sorted(set(boxes_mm) - by_path)
    for key in by_box:
        b = boxes_mm[key]
        shape.draw_rect(fitz.Rect(b[0] * pt, b[1] * pt, b[2] * pt, b[3] * pt))
        shape.finish(fill=(0, 0, 0), color=None)
    shape.commit()
    return doc, {'by_its_paths': sorted(by_path), 'by_its_ink_box': by_box}


def wrap_window(wrap_pdf, boxes_mm, px_per_mm):
    """The wrap's lockup window (the words' boxes grown LOCKUP_PAD_MM) rendered at ``px_per_mm``: its pixels, the
    words' silhouette on the same grid, the window's origin (wrap mm) and how each word's silhouette was drawn."""
    import fitz
    window = (min(b[0] for b in boxes_mm.values()) - LOCKUP_PAD_MM, min(b[1] for b in boxes_mm.values()) - LOCKUP_PAD_MM,
              max(b[2] for b in boxes_mm.values()) + LOCKUP_PAD_MM, max(b[3] for b in boxes_mm.values()) + LOCKUP_PAD_MM)
    with fitz.open(str(wrap_pdf)) as doc:
        page = doc[0]
        rgb, origin = render_page(page, window, px_per_mm, False)
        sil_doc, drawn = word_silhouettes(page, boxes_mm)
        with sil_doc:
            sil, sil_origin = render_page(sil_doc[0], window, px_per_mm, True)
    if sil.shape[:2] != rgb.shape[:2] or sil_origin != origin:
        raise ValueError('the words\' silhouette is not on the wrap\'s own grid')
    return rgb, sil[..., 0] < 128, origin, drawn


def grain_ceiling(rgb, ground_rgb, mask, px_per_mm, inner_mm):
    """The source ground's grain: the GRAIN_CEILING_PCT percentile of ΔE76 to its ground over the ground's own pixels
    (within GROUND_DE_MAX of it and GROUND_CLEAR_MM clear of any pixel farther: no stone or thread of the source counts)
    in a ring GRAIN_RING_MM wide just past ``inner_mm`` from ``mask`` (the ground the cut's hold reaches nearest)."""
    lab = lm.srgb_to_lab(rgb)
    dist = np.linalg.norm(lab - lm.srgb_to_lab(ground_rgb[None, :])[0], axis=-1)
    near_ink = ring(dist > GROUND_DE_MAX, px_per_mm, -1.0, GROUND_CLEAR_MM)
    band = ring(mask, px_per_mm, inner_mm, inner_mm + GRAIN_RING_MM) & ~near_ink
    return float(np.percentile(dist[band], GRAIN_CEILING_PCT)), int(band.sum())


def lockup(wrap_pdf, boxes_mm, wrap_ground_hex, carton_ground_hex, safe_w_mm):
    """The whole lockup cut from the wrap at the scale that sets its widest line at SAFE_FILL of ``safe_w_mm``:
    read once at WRAP_READ_PX_PER_MM to measure its alpha's extent and the ground's grain, then again at twice the
    front's pixels per scaled mm and halved by area (premultiplied), so its scale on the front is exact. Returns the
    premultiplied colour, the alpha (front pixels), and the record."""
    gw, gc = hex_rgb(wrap_ground_hex), hex_rgb(carton_ground_hex)
    k0 = WRAP_READ_PX_PER_MM
    rgb, sil, origin, drawn = wrap_window(wrap_pdf, boxes_mm, k0)
    floor_de, ring_px = grain_ceiling(rgb, gw, sil, k0, WORDS_HELD_MM[1])
    _, alpha = ink_cut(rgb, gw, held(sil, k0, *WORDS_HELD_MM), floor_de, gc)
    ex = extent(alpha, ALPHA_SEEN)
    ink_mm = [origin[0] + ex[0] / k0, origin[1] + ex[1] / k0, origin[0] + ex[2] / k0, origin[1] + ex[3] / k0]
    scale = SAFE_FILL * safe_w_mm / (ink_mm[2] - ink_mm[0])
    target_mm = SAFE_FILL * safe_w_mm
    target_px = int(np.floor(target_mm * FRONT_PX_PER_MM))
    passes = []
    for _ in range(LOCKUP_PASSES):
        k2 = 2.0 * scale * FRONT_PX_PER_MM
        rgb2, sil2, origin2, _ = wrap_window(wrap_pdf, boxes_mm, k2)
        pre2, alpha2 = ink_cut(rgb2, gw, held(sil2, k2, *WORDS_HELD_MM), floor_de, gc)
        h, w = alpha2.shape
        h, w = h - h % 2, w - w % 2
        pre = cv2.resize(pre2[:h, :w], (w // 2, h // 2), interpolation=cv2.INTER_AREA)
        alpha = cv2.resize(alpha2[:h, :w], (w // 2, h // 2), interpolation=cv2.INTER_AREA)
        ex2 = extent(alpha, ALPHA_SEEN)
        width_px = ex2[2] - ex2[0]
        width_mm = width_px / FRONT_PX_PER_MM
        passes.append({'scale': round(scale, 6), 'width_on_the_front_px': width_px, 'width_on_the_front_mm': round(width_mm, 4)})
        if width_px <= target_px:
            break
        scale *= target_px / width_px
    if width_px > target_px:
        raise ValueError('the lockup does not come to %.3f mm wide in %d passes (%.3f mm)'
                         % (target_mm, LOCKUP_PASSES, width_mm))
    rec = {'from': lm.rel(wrap_pdf), 'page': 1, 'words_boxes_on_the_wrap_mm': boxes_mm,
           'widest_box_mm': round(max(b[2] - b[0] for b in boxes_mm.values()), 3),
           'ink_on_the_wrap_mm': [round(v, 3) for v in ink_mm], 'ink_width_on_the_wrap_mm': round(ink_mm[2] - ink_mm[0], 3),
           'scale': round(scale, 6), 'safe_fill': SAFE_FILL, 'passes': passes,
           'said_scale': 'the wrap\'s mm to the front\'s mm: the page read at twice the front\'s pixels per scaled mm '
                         'and halved by area; a pass whose cut (its pixels rounding at the edge) came wider than %.0f %% '
                         'of the safe width is read again a little smaller' % (SAFE_FILL * 100),
           'read_px_per_mm': [k0, round(k2, 4)], 'front_px_per_wrap_mm': round(k2 / 2.0, 4),
           'ground_of_the_wrap': wrap_ground_hex, 'ink_floor_de76': round(floor_de, 3), 'ink_ramp_de76': INK_RAMP_DE,
           'grain_ring_px': ring_px, 'held_to_the_words_mm': list(WORDS_HELD_MM), 'silhouettes': drawn,
           'window_edge_alpha': [border_alpha(alpha2), border_alpha(alpha)],
           'cut': 'by its own ink: alpha from each pixel\'s ΔE76 to the wrap\'s ground (%.2f → %.2f), held to the '
                  'words\' own vector silhouettes (LIPSTICK, set as text, by its ink box) whole within %.1f mm and '
                  'gone by %.1f mm; the window\'s edges carry no alpha (never a box)'
                  % (floor_de, floor_de + INK_RAMP_DE, WORDS_HELD_MM[0], WORDS_HELD_MM[1])}
    return pre, alpha, origin2, rec


def lid_word_boxes(master):
    """Every word box on the lid (its master's element and line boxes): its hero, name, logo and small lines."""
    out = {'element %s' % k: v for k, v in master['element_boxes_mm'].items()}
    out.update({'line %s' % k: v for k, v in master['line_boxes_mm'].items()})
    return out


def refuse_near_words(region_mm, boxes, clear_mm):
    """The region's clearance (mm) from every word box on the lid; refused (ValueError, naming the box) when one is
    nearer than ``clear_mm`` or under it."""
    x0, y0, x1, y1 = region_mm
    clear = {}
    for name, b in boxes.items():
        dx = max(b[0] - x1, x0 - b[2], 0.0)
        dy = max(b[1] - y1, y0 - b[3], 0.0)
        gap = float(np.hypot(dx, dy))
        if dx == 0.0 and dy == 0.0:
            gap = -min(x1 - b[0], b[2] - x0, y1 - b[1], b[3] - y0)
        clear[name] = round(gap, 3)
        if gap < clear_mm:
            raise ValueError('the drift region %s touches the lid\'s %s %s (%.2f mm; %.1f mm asked)'
                             % (list(region_mm), name, [round(v, 3) for v in b], gap, clear_mm))
    return clear


def lid_drift(plate_png, region_mm, master, carton_ground_hex):
    """The lid's own small stones in ``region_mm`` (lid mm), refused near a word; each stone (STONE_DE from the lid's
    ground, small, lighter than the ground, wholly inside the region) cut by its own contour with a soft edge.
    Returns the premultiplied colour and the alpha on the plate's own pixels, the region's pixel origin (lid mm) and
    the plate's pixels per mm (x, y), and the record."""
    clear = refuse_near_words(region_mm, lid_word_boxes(master), LID_WORDS_CLEAR_MM)
    plate = np.asarray(Image.open(plate_png).convert('RGB')).astype(np.float64)
    kx, ky = plate.shape[1] / lm.LID_MM[0], plate.shape[0] / lm.LID_MM[1]
    px0, py0 = int(round(region_mm[0] * kx)), int(round(region_mm[1] * ky))
    px1, py1 = int(round(region_mm[2] * kx)), int(round(region_mm[3] * ky))
    rgb = plate[py0:py1, px0:px1]
    lab = lm.srgb_to_lab(rgb)
    ground = np.median(rgb.reshape(-1, 3), axis=0)
    g_lab = lm.srgb_to_lab(ground[None, :])[0]
    dist = np.linalg.norm(lab - g_lab, axis=-1)
    n, lbl, st, _ = cv2.connectedComponentsWithStats((dist > STONE_DE).astype(np.uint8), 8)
    kept, dropped = [], {'touches the region\'s edge': 0, 'larger than a small stone': 0, 'a speck': 0,
                         'a shadow (darker than a stone)': 0}
    keep = np.zeros(n, bool)
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in st[i])
        size_mm = max(w / kx, h / ky)
        area_mm2 = area / (kx * ky)
        lift = float(lab[lbl == i][:, 0].mean() - g_lab[0])
        if x == 0 or y == 0 or x + w >= rgb.shape[1] or y + h >= rgb.shape[0]:
            dropped['touches the region\'s edge'] += 1
        elif size_mm > STONE_MAX_MM:
            dropped['larger than a small stone'] += 1
        elif area_mm2 < STONE_MIN_MM2:
            dropped['a speck'] += 1
        elif lift < STONE_LIFT_L:
            dropped['a shadow (darker than a stone)'] += 1
        else:
            keep[i] = True
            kept.append({'box_on_the_lid_mm': [round((px0 + x) / kx, 3), round((py0 + y) / ky, 3),
                                               round((px0 + x + w) / kx, 3), round((py0 + y + h) / ky, 3)],
                         'size_mm': round(size_mm, 3), 'area_mm2': round(area_mm2, 3),
                         'colour': rgb_hex(rgb[lbl == i].mean(axis=0)), 'lighter_than_the_ground_L': round(lift, 2)})
    if len(kept) < 3:
        raise ValueError('the drift region %s holds %d small stones, not a drift' % (list(region_mm), len(kept)))
    stones = keep[lbl]
    k = (kx + ky) / 2
    floor_de, ring_px = grain_ceiling(rgb, ground, stones, k, STONE_EDGE_MM[1])
    hold = held(stones, k, *STONE_EDGE_MM)
    body = held(solid(stones), k, 0.0, STONE_BODY_EDGE_MM)
    alpha = np.maximum(ink_alpha(rgb, ground, hold, floor_de), body * hold)
    pre = premultiplied(rgb, alpha, ground, hex_rgb(carton_ground_hex))
    union = [min(s['box_on_the_lid_mm'][0] for s in kept), min(s['box_on_the_lid_mm'][1] for s in kept),
             max(s['box_on_the_lid_mm'][2] for s in kept), max(s['box_on_the_lid_mm'][3] for s in kept)]
    rec = {'from': lm.rel(plate_png), 'lid_mm': list(lm.LID_MM), 'plate_px_per_mm': [round(kx, 4), round(ky, 4)],
           'plate_ppi': round(kx * lm.MM_PER_INCH, 1),
           'region_on_the_lid_mm': list(region_mm),
           'region_read_px': [px0, py0, px1, py1],
           'clear_of_the_lids_words_mm': clear, 'words_clear_min_mm': LID_WORDS_CLEAR_MM,
           'ground_of_the_lid': rgb_hex(ground), 'stones': kept, 'stones_union_on_the_lid_mm': union,
           'left_out': dropped, 'stone_rule': {'de76_over': STONE_DE, 'max_mm': STONE_MAX_MM, 'min_mm2': STONE_MIN_MM2,
                                               'lighter_by_L': STONE_LIFT_L},
           'ink_floor_de76': round(floor_de, 3), 'grain_ring_px': ring_px,
           'held_to_each_stone_mm': list(STONE_EDGE_MM), 'region_edge_alpha': border_alpha(alpha),
           'cut': 'each stone by its own contour (its alpha from its ΔE to the lid\'s ground, its body solid, held to '
                  'the stone whole within %.2f mm and gone by %.2f mm); a stone the region\'s edge would cut is left '
                  'out; the region\'s edges carry no alpha (never a rectangle)' % STONE_EDGE_MM}
    return pre, alpha, (px0 / kx, py0 / ky), (kx, ky), rec


def ground_canvas(w_px, h_px, ground_hex):
    """The front's ground: the carton's ground colour with a fine zero-mean grain in L* (seeded), every pixel."""
    rng = np.random.default_rng(GRAIN_SEED)
    noise = cv2.GaussianBlur(rng.standard_normal((h_px, w_px)), (0, 0), GRAIN_BLUR_PX)
    noise = (noise - noise.mean()) / noise.std() * GRAIN_L
    g = hex_rgb(ground_hex)
    # L* about the ground: the RGB step that moves L* by 1, measured on the ground itself (its a*, b* barely move)
    step = g * 0.01
    dl = float(lm.srgb_to_lab((g + step)[None, :])[0, 0] - lm.srgb_to_lab(g[None, :])[0, 0])
    canvas = g[None, None, :] + noise[..., None] * (step / dl)[None, None, :]
    return canvas


def paste(canvas, cover, pre, alpha, x_px, y_px):
    """``pre``/``alpha`` laid over ``canvas`` (and ``cover``, the art's own alpha) at integer pixels."""
    h, w = alpha.shape
    canvas[y_px:y_px + h, x_px:x_px + w] = pre + (1.0 - alpha[..., None]) * canvas[y_px:y_px + h, x_px:x_px + w]
    cover[y_px:y_px + h, x_px:x_px + w] = alpha + (1.0 - alpha) * cover[y_px:y_px + h, x_px:x_px + w]


def warp_paste(canvas, cover, pre, alpha, src_px_per_mm, src_origin_mm, dst_origin_mm):
    """``pre``/``alpha`` (on a source grid of ``src_px_per_mm`` (x, y) whose first pixel's corner is at
    ``src_origin_mm``) laid over the canvas at the SAME mm size — 1 mm of the source is 1 mm of the front — moved so the
    source's mm ``src_origin_mm`` lands on the front's ``dst_origin_mm`` (canvas mm). Returns the matrix's scale (mm per
    mm, x and y)."""
    k = FRONT_PX_PER_MM
    sx, sy = k / src_px_per_mm[0], k / src_px_per_mm[1]
    tx, ty = dst_origin_mm[0] * k, dst_origin_mm[1] * k
    m = np.array([[sx, 0.0, tx + 0.5 * sx - 0.5], [0.0, sy, ty + 0.5 * sy - 0.5]])
    size = (canvas.shape[1], canvas.shape[0])
    a = np.clip(cv2.warpAffine(alpha, m, size, flags=cv2.INTER_CUBIC, borderValue=0.0), 0.0, 1.0)
    p = cv2.warpAffine(pre, m, size, flags=cv2.INTER_CUBIC, borderValue=(0.0, 0.0, 0.0))
    p = np.clip(p, 0.0, 255.0 * a[..., None])
    canvas[:] = p + (1.0 - a[..., None]) * canvas
    cover[:] = a + (1.0 - a) * cover
    return a, (sx / k * src_px_per_mm[0], sy / k * src_px_per_mm[1])


# --- the drift cut from the wrap's own plate (Day 13 §1.1) ---------------------------------------------------------------

def plate_scale(shape):
    """The wrap plate's pixels per mm: one scale for both axes (the plate laid from the trim's top-left at the wrap's
    width; lipstick.json body.trim: "one scale for both axes (nothing stretched)")."""
    return shape[1] / zlm.WRAP_MM[0]


def words_zone(boxes_mm, clear_mm):
    """The words' zone on the wrap: each word's box grown ``clear_mm``."""
    return {name: [b[0] - clear_mm, b[1] - clear_mm, b[2] + clear_mm, b[3] + clear_mm] for name, b in boxes_mm.items()}


def centres_mm(n, k, origin_mm):
    """The centres (mm) of ``n`` pixels at ``k`` px/mm whose first pixel's corner is at ``origin_mm``."""
    return origin_mm + (np.arange(n) + 0.5) / k


def in_rect(xs, ys, rect):
    """The pixels (by centre) inside ``rect`` (x0, y0, x1, y1; x0 and y0 included)."""
    return (((ys >= rect[1]) & (ys < rect[3]))[:, None]) & (((xs >= rect[0]) & (xs < rect[2]))[None, :])


def window_pixels(window_mm, k, width_px):
    """The plate's pixels whose centres lie in ``window_mm`` (wrap mm): its rows, and its columns read round the seam
    (a column past the plate's width is the same column from its start), with the first pixel's corner (wrap mm)."""
    c0, c1 = int(np.ceil(window_mm[0] * k - 0.5)), int(np.ceil(window_mm[2] * k - 0.5))
    r0, r1 = int(np.ceil(window_mm[1] * k - 0.5)), int(np.ceil(window_mm[3] * k - 0.5))
    return np.arange(r0, r1), np.arange(c0, c1) % width_px, (c0 / k, r0 / k)


def plate_distance(rgb, ground_rgb):
    """Each pixel's ΔE76 to the plate's ground."""
    return np.linalg.norm(lm.srgb_to_lab(rgb) - lm.srgb_to_lab(ground_rgb[None, :])[0], axis=-1)


def tooth_filled(stones, k):
    """The stones' mask with its holes up to WRAP_TOOTH_MM2 filled (the paper's tooth inside a stone), and the holes
    counted: filled (count, mm², the largest) and kept as ground (count, mm²). A hole is a 4-connected piece of the
    mask's complement that does not reach the read's edge."""
    n, lbl, st, _ = cv2.connectedComponentsWithStats((~stones).astype(np.uint8), 4)
    h, w = stones.shape
    filled = stones.copy()
    tooth, kept = [], []
    for i in range(1, n):
        x, y, bw, bh, area = (int(v) for v in st[i])
        if x == 0 or y == 0 or x + bw >= w or y + bh >= h:
            continue
        area_mm2 = area / (k * k)
        if area_mm2 <= WRAP_TOOTH_MM2:
            filled[lbl == i] = True
            tooth.append(area_mm2)
        else:
            kept.append(area_mm2)
    largest = 0.0
    if tooth:
        largest = max(tooth)
    return filled, {'tooth_holes_filled': {'count': len(tooth), 'area_mm2': round(float(sum(tooth)), 4),
                                           'largest_mm2': round(float(largest), 5), 'up_to_mm2': WRAP_TOOTH_MM2},
                    'gaps_kept_as_ground': {'count': len(kept), 'area_mm2': round(float(sum(kept)), 3)}}


def edge_alpha(alpha):
    """The largest alpha on each edge of a cut's window (top, right, bottom, left)."""
    return {'top': float(alpha[0].max()), 'right': float(alpha[:, -1].max()), 'bottom': float(alpha[-1].max()),
            'left': float(alpha[:, 0].max())}


def wrap_drift(plate_png, window_mm, carton_ground_hex):
    """The wrap's own stones in ``window_mm`` (wrap mm: x0, y0, x1, y1; x may run past the wrap's width, round its
    seam): every pixel STONE_DE (ΔE76) or more from the plate's ground — the stones, their copper outlines and veins,
    the threads — cut by its own ink (``lid_drift``'s cut: its alpha from its ΔE to the ground, its body solid but for
    gaps larger than the tooth, held to the mask whole within 0.1 mm and gone by 0.25 mm), no stone left out for its
    size, its lightness or the window's edge: the window cuts a stone as the wrap's trim and seam cut it. The plate is
    read WRAP_READ_MARGIN_MM past the window (each edge pixel's cut sees its neighbours); the paste keeps the window.
    Returns the premultiplied colour and the alpha on the plate's own pixels, the read's first pixel corner (wrap mm),
    the plate's pixels per mm (x, y), the window's pixels in the read, and the record."""
    plate = np.asarray(Image.open(plate_png).convert('RGB')).astype(np.float64)
    k = plate_scale(plate.shape)
    m = WRAP_READ_MARGIN_MM
    read_mm = (window_mm[0] - m, window_mm[1] - m, window_mm[2] + m, window_mm[3] + m)
    rows, cols, origin = window_pixels(read_mm, k, plate.shape[1])
    if rows[0] < 0 or rows[-1] >= plate.shape[0]:
        raise ValueError('the window %s runs off the plate\'s height (%.3f mm)' % (list(window_mm), plate.shape[0] / k))
    rgb = plate[rows][:, cols]
    ground = np.median(plate.reshape(-1, 3), axis=0)
    dist = plate_distance(rgb, ground)
    stones = dist > STONE_DE
    filled, holes = tooth_filled(stones, k)
    floor_de, ring_px = grain_ceiling(rgb, ground, stones, k, STONE_EDGE_MM[1])
    hold = held(stones, k, *STONE_EDGE_MM)
    body = held(filled, k, 0.0, STONE_BODY_EDGE_MM)
    alpha = np.maximum(ink_alpha(rgb, ground, hold, floor_de), body * hold)
    pre = premultiplied(rgb, alpha, ground, hex_rgb(carton_ground_hex))
    inside = in_rect(centres_mm(rgb.shape[1], k, origin[0]), centres_mm(rgb.shape[0], k, origin[1]), window_mm)
    rr, cc = np.nonzero(inside.any(axis=1))[0], np.nonzero(inside.any(axis=0))[0]
    win_alpha = alpha[rr[0]:rr[-1] + 1, cc[0]:cc[-1] + 1]
    win_stones = stones[rr[0]:rr[-1] + 1, cc[0]:cc[-1] + 1]
    carried = (alpha >= 0.999) & (dist <= GROUND_DE_MAX) & ~(filled & ~stones) & inside
    crosses = bool(window_mm[0] < 0.0 or window_mm[2] > zlm.WRAP_MM[0])
    rec = {'from': lm.rel(plate_png), 'wrap_mm': list(zlm.WRAP_MM), 'plate_px': [plate.shape[1], plate.shape[0]],
           'plate_px_per_mm': [round(k, 4), round(k, 4)], 'plate_ppi': round(k * lm.MM_PER_INCH, 1),
           'window_on_the_wrap_mm': [round(v, 4) for v in window_mm],
           'window_px': [int(win_alpha.shape[1]), int(win_alpha.shape[0])],
           'read_margin_mm': WRAP_READ_MARGIN_MM, 'crosses_the_seam': crosses,
           'ground_of_the_wrap': rgb_hex(ground),
           'stone_rule': {'de76_over': STONE_DE, 'kept': 'every pixel over the rule (stones, outlines, veins, threads): '
                                                        'no stone left out for its size, lightness or the window\'s edge',
                          'tooth_mm2': WRAP_TOOTH_MM2},
           'holes': holes, 'ground_carried_px': int(carried.sum()),
           'stone_area_in_the_window_mm2': round(float(win_stones.sum() / (k * k)), 3),
           'stone_share_of_the_window': round(float(win_stones.mean()), 4),
           'ink_floor_de76': round(floor_de, 3), 'grain_ring_px': ring_px,
           'held_to_each_stone_mm': list(STONE_EDGE_MM),
           'window_edge_alpha_on_the_plate': {e: round(v, 4) for e, v in edge_alpha(win_alpha).items()},
           'cut': 'every pixel of the bank by its own ink (its alpha from its ΔE to the wrap\'s ground, its body solid but '
                  'for gaps larger than %.2f mm², held to the mask whole within %.2f mm and gone by %.2f mm); the '
                  'window\'s edges cut the bank as the wrap\'s trim and seam cut it (no stone left out, none moved)'
                  % ((WRAP_TOOTH_MM2,) + STONE_EDGE_MM)}
    return pre, alpha, origin, (k, k), inside, rec


def area_paste(canvas, cover, pre, alpha, src_px_per_mm, src_origin_mm, dst_origin_mm, clip_mm):
    """``pre``/``alpha`` laid over the canvas at the SAME mm size, as ``warp_paste`` lays them (the source's mm
    ``src_origin_mm`` lands on the front's ``dst_origin_mm``, canvas mm), but resampled by area: each source pixel drawn
    as its own square on a grid AREA_SUPERSAMPLE times the front's, over ``clip_mm`` only (canvas mm, on the front's
    pixel edges: the window's own edges, nothing drawn past them), then averaged down by area — a box filter, so a vein
    one or two source pixels wide is never broken into dashes. Returns the art's alpha on the canvas and the matrix's
    scale (mm per mm, x and y)."""
    k = FRONT_PX_PER_MM
    f = AREA_SUPERSAMPLE
    kf = k * f
    box = [int(round(v * k)) for v in clip_mm]
    if max(abs(b - v * k) for b, v in zip(box, clip_mm)) > 1e-6:
        raise ValueError('the clip %s is not on the front\'s pixel edges' % list(clip_mm))
    bx0, by0, bx1, by1 = box
    sx, sy = kf / src_px_per_mm[0], kf / src_px_per_mm[1]
    tx, ty = (dst_origin_mm[0] - bx0 / k) * kf, (dst_origin_mm[1] - by0 / k) * kf
    m = np.array([[sx, 0.0, tx + 0.5 * sx - 0.5], [0.0, sy, ty + 0.5 * sy - 0.5]])
    size = ((bx1 - bx0) * f, (by1 - by0) * f)
    a = cv2.warpAffine(alpha.astype(np.float32), m, size, flags=cv2.INTER_NEAREST, borderValue=0.0)
    p = cv2.warpAffine(pre.astype(np.float32), m, size, flags=cv2.INTER_NEAREST, borderValue=(0.0, 0.0, 0.0))
    a = np.clip(cv2.resize(a, (bx1 - bx0, by1 - by0), interpolation=cv2.INTER_AREA).astype(np.float64), 0.0, 1.0)
    p = cv2.resize(p, (bx1 - bx0, by1 - by0), interpolation=cv2.INTER_AREA).astype(np.float64)
    p = np.clip(p, 0.0, 255.0 * a[..., None])
    full = np.zeros(canvas.shape[:2])
    full[by0:by1, bx0:bx1] = a
    canvas[by0:by1, bx0:bx1] = p + (1.0 - a[..., None]) * canvas[by0:by1, bx0:bx1]
    cover[by0:by1, bx0:bx1] = a + (1.0 - a) * cover[by0:by1, bx0:bx1]
    return full, (sx / kf * src_px_per_mm[0], sy / kf * src_px_per_mm[1])


def largest_stone(stones, k):
    """The largest stone in a mask: the mask eroded WRAP_BODY_ERODE_MM (the copper outlines and veins away, so each
    stone stands alone), its largest body grown back as far inside the mask. Returns its area (mm²) and box (pixels)."""
    d = zlm.odd_px(2.0 * WRAP_BODY_ERODE_MM, k)
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (d, d))
    core = cv2.erode(stones.astype(np.uint8), ker)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(core, 8)
    if n < 2:
        raise ValueError('no stone stands alone in the window')
    i = 1 + int(np.argmax(st[1:, 4]))
    grown = cv2.dilate((lbl == i).astype(np.uint8), ker).astype(bool) & stones
    ys, xs = np.nonzero(grown)
    return float(grown.sum() / (k * k)), [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def front_frame(product):
    """The front's frame for its picture: its face (stick_carton.faces), its safe area and the notch's keep-out (panel
    mm, origin the panel's top-left), the panel's top-left on the picture (mm) and the picture's size (px)."""
    coords, _ = sc.die(product)
    face = sc.faces(coords)['front']
    bx0, by0, bx1, by1 = face['box']
    gx0, gy0, gx1, gy1 = face['ground']
    k = FRONT_PX_PER_MM
    return {'face': face,
            'safe': [face['safe'][0] - bx0, face['safe'][1] - by0, face['safe'][2] - bx0, face['safe'][3] - by0],
            'notch': dict(face['keep_out'], cx=face['keep_out']['cx'] - bx0, cy=face['keep_out']['cy'] - by0),
            'ox': bx0 - gx0, 'oy': by0 - gy0,
            'W': int(round((gx1 - gx0) * k)), 'H': int(round((gy1 - gy0) * k))}


def lockup_at(frame, alpha):
    """Where ``front_picture`` lays the lockup: centred across the safe area, its top LOCKUP_BELOW_NOTCH_MM below the
    notch's keep-out (the same arithmetic). Returns its pixel offset on the picture and its box on the panel (mm, the
    alpha's own extent)."""
    k = FRONT_PX_PER_MM
    safe, notch, ox, oy = frame['safe'], frame['notch'], frame['ox'], frame['oy']
    ex = extent(alpha, ALPHA_SEEN)
    lock_w_mm = (ex[2] - ex[0]) / k
    top_mm = notch['cy'] + notch['r_mm'] + LOCKUP_BELOW_NOTCH_MM
    left_mm = (safe[0] + safe[2]) / 2 - lock_w_mm / 2
    x_px = int(round((ox + left_mm) * k)) - ex[0]
    y_px = int(round((oy + top_mm) * k)) - ex[1]
    return x_px, y_px, [(x_px + ex[0]) / k - ox, (y_px + ex[1]) / k - oy, (x_px + ex[2]) / k - ox, (y_px + ex[3]) / k - oy]


def stone_map(stones, k, body):
    """The wrap's stone share per MAP_CELL_MM cell (columns across, rows down) over ``body`` (None where a cell holds
    none of it: the words' zone)."""
    cw, ch = MAP_CELL_MM
    xs = centres_mm(stones.shape[1], k, 0.0)
    ys = centres_mm(stones.shape[0], k, 0.0)
    cols = list(np.arange(0.0, zlm.WRAP_MM[0], cw))
    rows = list(np.arange(WRAP_TRIM_MM[0], WRAP_TRIM_MM[1], ch))
    share = []
    for r in rows:
        line = []
        for c in cols:
            cell = in_rect(xs, ys, (c, r, c + cw, min(r + ch, WRAP_TRIM_MM[1]))) & body
            if cell.any():
                line.append(round(100.0 * float(stones[cell].mean()), 1))
            else:
                line.append(None)
        share.append(line)
    return {'cell_mm': list(MAP_CELL_MM), 'columns_from_mm': [round(float(c), 2) for c in cols],
            'rows_from_mm': [round(float(r), 2) for r in rows], 'stone_share_pct': share,
            'said': 'None where the cell lies wholly in the words\' zone'}


def densest_window(stones, k, body, width_mm, height_mm):
    """The window of the chosen size (its top on the trim) holding the most stone round the wrap, the words' zone
    counted as no stone: its left edge (wrap mm), its share, and how much of it lies in the words' zone (mm²)."""
    best = None
    ys = centres_mm(stones.shape[0], k, 0.0)
    rows = (ys >= WRAP_TRIM_MM[0]) & (ys < WRAP_TRIM_MM[0] + height_mm)
    s, b = stones[rows], body[rows]
    for x0 in np.arange(0.0, zlm.WRAP_MM[0], CANDIDATE_STEP_MM):
        _, cols, _ = window_pixels((x0, 0.0, x0 + width_mm, 1.0), k, stones.shape[1])
        got = float((s[:, cols] & b[:, cols]).mean())
        if best is None or got > best[1]:
            best = (float(x0), got, float((~b[:, cols]).sum() / (k * k)))
    return {'left_mm': round(best[0], 2), 'stone_share': round(best[1], 4), 'in_the_words_zone_mm2': round(best[2], 2)}


def wrap_drift_plan(product, wrap, colours):
    """The drift's window and its coverage measure, defined BEFORE the front is built (``write_plan`` writes it). The
    window: the front's lower safe area (below the lockup's box + DRIFT_BELOW_LIPSTICK_MM, on whole pixels of the
    picture) is as wide as the window; on the wrap it ends where the words' zone begins (no word, and no box cut by the
    words' zone, carried) and starts on the wrap's top trim, as tall as the trim allows or the lower front holds. The
    measure: the stone share (pixels over STONE_DE ΔE76 from their own ground) of the lower front, read from the written
    picture, against the wrap body's (inside its trim, the words' zone out) and the window's. ``wrap``: the closed
    wrap's page (pdf), its words' boxes, its ground and its print plate (plate)."""
    frame = front_frame(product)
    k = FRONT_PX_PER_MM
    safe, ox, oy = frame['safe'], frame['ox'], frame['oy']
    _, alpha, _, _ = lockup(wrap['pdf'], wrap['boxes_mm'], wrap['ground'], colours['ground'], safe[2] - safe[0])
    _, _, lock_box = lockup_at(frame, alpha)
    lower = [safe[0], lock_box[3] + DRIFT_BELOW_LIPSTICK_MM, safe[2], safe[3]]
    fx0 = float(np.ceil((lower[0] + ox) * k)) / k - ox
    fx1 = float(np.floor((lower[2] + ox) * k)) / k - ox
    fy0 = float(np.ceil((lower[1] + oy) * k)) / k - oy
    trim_h = WRAP_TRIM_MM[1] - WRAP_TRIM_MM[0]
    fy1 = float(np.floor((min(lower[3], fy0 + trim_h) + oy) * k)) / k - oy
    width, height = fx1 - fx0, fy1 - fy0
    zone = words_zone(wrap['boxes_mm'], WRAP_WORDS_CLEAR_MM)
    wx1 = min(z[0] for z in zone.values())
    window = [wx1 - width, WRAP_TRIM_MM[0], wx1, WRAP_TRIM_MM[0] + height]
    plate = np.asarray(Image.open(wrap['plate']).convert('RGB')).astype(np.float64)
    kp = plate_scale(plate.shape)
    ground = np.median(plate.reshape(-1, 3), axis=0)
    stones = plate_distance(plate, ground) > STONE_DE
    xs, ys = centres_mm(plate.shape[1], kp, 0.0), centres_mm(plate.shape[0], kp, 0.0)
    in_zone = np.zeros(stones.shape, bool)
    for z in zone.values():
        in_zone |= in_rect(xs, ys, z)
    body = in_rect(xs, ys, (0.0, WRAP_TRIM_MM[0], zlm.WRAP_MM[0], WRAP_TRIM_MM[1])) & ~in_zone
    rows, cols, _ = window_pixels(window, kp, plate.shape[1])
    win_stones = stones[rows][:, cols]
    if in_zone[rows][:, cols].any():
        raise ValueError('the window %s reaches into the words\' zone' % window)
    lower_area = (lower[2] - lower[0]) * (lower[3] - lower[1])
    win_stone_mm2 = float(win_stones.sum() / (kp * kp))
    big_mm2, big_px = largest_stone(win_stones, kp)
    tolerance = big_mm2 / lower_area
    third = zlm.front_third(zlm.WRAP_MM[0], zlm.CASE_D_MM)
    under = [third['centre_mm'] - width / 2, wrap['boxes_mm']['lipstick'][3] + DRIFT_BELOW_LIPSTICK_MM,
             third['centre_mm'] + width / 2, WRAP_TRIM_MM[1]]
    u_rows, u_cols, _ = window_pixels(under, kp, plate.shape[1])
    dense = densest_window(stones, kp, body, width, height)
    bleed_rows = ys > WRAP_TRIM_MM[1]
    return {
        'schema': PLAN_SCHEMA, 'product': product['key'], 'written': 'before the front is built (Day 13 §1.1)',
        'plate': lm.rel(wrap['plate']), 'plate_sha256': lm.sha256(wrap['plate']),
        'plate_px_per_mm': round(kp, 4), 'ground_of_the_wrap': rgb_hex(ground), 'ground_in_the_wraps_record': wrap['ground'],
        'words_zone_on_the_wrap_mm': {n: [round(v, 3) for v in z] for n, z in zone.items()},
        'words_clear_mm': WRAP_WORDS_CLEAR_MM, 'trim_on_the_wrap_mm': list(WRAP_TRIM_MM),
        'stone_map': stone_map(stones, kp, body),
        'window': {
            'on_the_wrap_mm': [round(v, 4) for v in window], 'size_mm': [round(width, 4), round(height, 4)],
            'on_the_front_mm': [round(v, 4) for v in (fx0, fy0, fx1, fy1)],
            'lockup_box_on_the_front_mm': [round(v, 4) for v in lock_box],
            'scale': 1.0, 'rotation_deg': 0.0, 'mirrored': False, 'tiled': False,
            'crosses_the_seam': bool(window[0] < 0.0 or window[2] > zlm.WRAP_MM[0]),
            'placed': 'its top-left on the front\'s lower safe area\'s top-left (on whole pixels of the picture): the '
                      'wrap\'s top trim %.1f mm under LIPSTICK, its left on the safe area\'s left' % DRIFT_BELOW_LIPSTICK_MM,
            'edges_that_cut': {'top': 'the wrap\'s own top trim (y %.1f mm): the bank runs off the wrap there, and it '
                                      'runs off the window here' % WRAP_TRIM_MM[0],
                               'right': 'the front\'s safe line, %.1f mm in from the right fold: on the wrap, where the '
                                        'window meets the words\' %.1f mm zone' % (sc.SAFE_MM, WRAP_WORDS_CLEAR_MM)},
            'edges_that_must_not_cut': ['left', 'bottom'],
            'reason': 'the wrap\'s stone map (stone_map) holds its bank in the top rows from x 12 to 52 mm and round the '
                      'hero; its lower body is all but empty. Left of the words the bank descends from the large rose, '
                      'lilac and teal ovals at the top trim to small satellites, with a cluster of satellites near the '
                      'foot: the diagonal chain tapering to satellites the eye\'s round 1 asked for, cut whole from the '
                      'wrap with no stone moved. The window is as wide as the front\'s safe area and ends where the '
                      'words\' zone begins, so no letter and no rectangle cut by the words\' zone is carried; its share '
                      'was also read before the choice (below)',
            'not_chosen': {
                'the_densest_window_of_this_size': dict(dense, why='its right part lies in the words\' zone: cut there, '
                                                                   'the bank would carry a rectangle'),
                'the_front_third_below_lipstick': {'on_the_wrap_mm': [round(v, 3) for v in under],
                                                   'stone_share': round(float(stones[u_rows][:, u_cols].mean()), 4),
                                                   'why': 'the wrap\'s own column under its words: a few satellites'}}},
        'coverage': {
            'measure': 'stone share: the share of an area\'s pixels (each by its centre) at least %.1f ΔE76 from their '
                       'own ground — the plate\'s median ground on the wrap, the carton\'s ground colour on the front '
                       '(the same rule as the cut)' % STONE_DE,
            'wrap_body': 'the plate inside its trim (y %.1f–%.1f mm; the 1 mm bleed off top and bottom, where the plate\'s '
                         'last rows read off-ground: its edge, not a stone), its whole width, the words\' zone out'
                         % WRAP_TRIM_MM,
            'window': 'the window\'s own pixels on the plate',
            'lower_front': 'the front\'s safe area below the lockup\'s box + %.1f mm, read from the written front picture'
                           % DRIFT_BELOW_LIPSTICK_MM,
            'lower_front_mm': [round(v, 4) for v in lower], 'lower_front_area_mm2': round(lower_area, 3),
            'compared': 'the lower front\'s share against the wrap body\'s, within the tolerance',
            'wrap_body_share': round(float(stones[body].mean()), 4),
            'wrap_body_share_with_the_bleed': round(float(stones[~in_zone].mean()), 4),
            'bleed_rows_off_ground_share': round(float(stones[bleed_rows].mean()), 4),
            'window_share': round(float(win_stones.mean()), 4),
            'window_stone_mm2': round(win_stone_mm2, 3),
            'predicted_lower_front_share': round(win_stone_mm2 / lower_area, 4),
            'largest_stone_in_the_window_mm2': round(big_mm2, 3),
            'largest_stone_box_on_the_wrap_mm': [round(window[0] + big_px[0] / kp, 3), round(window[1] + big_px[1] / kp, 3),
                                                 round(window[0] + big_px[2] / kp, 3), round(window[1] + big_px[3] / kp, 3)],
            'tolerance': round(tolerance, 4),
            'tolerance_said': 'the share moves only by whole stones (none is moved, rescaled, added or tiled), so the '
                              'front comes as near the wrap\'s share as one stone more or fewer: the largest stone in '
                              'the window (told apart by the mask eroded %.1f mm — the copper outlines and veins away, and '
                              'where two stones\' outlines run together — and grown back %.1f mm inside it) over the lower '
                              'front\'s area'
                              % (WRAP_BODY_ERODE_MM, WRAP_BODY_ERODE_MM)}}


def write_plan(product, wrap, colours, revisions=None):
    """The plan written into the product's folder (PLAN_NAME) before the front is built — never rewritten: a plan on
    disk is kept when it is the same as this one (its ``revisions`` aside), refused (ValueError) when it differs.
    ``revisions``: what changed since a plan this one supersedes, and why (kept in the plan). Returns the plan on disk."""
    plan = json.loads(json.dumps(wrap_drift_plan(product, wrap, colours), ensure_ascii=False))
    path = Path(product['out']) / PLAN_NAME
    if path.exists():
        held_plan = json.loads(path.read_text(encoding='utf-8'))
        if {k: v for k, v in held_plan.items() if k != 'revisions'} != plan:
            raise ValueError('%s differs from the plan computed now: the coverage measure is written once, before the '
                             'build' % lm.rel(path))
        return held_plan
    if revisions is not None:
        plan['revisions'] = revisions
    lm.write_json(path, plan)
    return plan


def read_plan(path):
    """The plan written before the build (``write_plan``); refused when absent."""
    if not Path(path).exists():
        raise FileNotFoundError('%s is absent: the drift\'s window and coverage measure are written before the front is '
                                'built (write_plan)' % path)
    plan = json.loads(Path(path).read_text(encoding='utf-8'))
    if plan['schema'] != PLAN_SCHEMA:
        raise ValueError('%s is not a %s file' % (path, PLAN_SCHEMA))
    return plan


# --- the checks (pure) ------------------------------------------------------------------------------------------------

def pieces_mm(alpha, px_per_mm_xy, origin_mm):
    """The pieces of an alpha over one half (each at least STONE_MIN_MM2): their centres (mm, from ``origin_mm``, the
    first pixel's corner) and areas (mm²)."""
    n, _, st, cen = cv2.connectedComponentsWithStats((alpha > 0.5).astype(np.uint8), 8)
    out = []
    for i in range(1, n):
        area_mm2 = st[i, 4] / (px_per_mm_xy[0] * px_per_mm_xy[1])
        if area_mm2 >= STONE_MIN_MM2:
            out.append((origin_mm[0] + (cen[i][0] + 0.5) / px_per_mm_xy[0],
                        origin_mm[1] + (cen[i][1] + 0.5) / px_per_mm_xy[1], area_mm2))
    return out


def measured_scale(lid_pieces, front_pieces, shift_mm):
    """The drift's scale read from the pixels, not the matrix: each stone on the lid matched to the front's piece
    nearest its place after ``shift_mm``; the sum of the stones' pairwise distances on the front over the same sum on
    the lid, each stone's area on the front over its area on the lid, and the farthest a stone landed from its place."""
    pairs = []
    for x, y, a in lid_pieces:
        f = min(front_pieces, key=lambda p: np.hypot(p[0] - x - shift_mm[0], p[1] - y - shift_mm[1]))
        pairs.append(((x, y, a), f))
    lid_d = sum(np.hypot(p[0][0] - q[0][0], p[0][1] - q[0][1]) for i, p in enumerate(pairs) for q in pairs[i + 1:])
    front_d = sum(np.hypot(p[1][0] - q[1][0], p[1][1] - q[1][1]) for i, p in enumerate(pairs) for q in pairs[i + 1:])
    off = max(np.hypot(f[0] - l[0] - shift_mm[0], f[1] - l[1] - shift_mm[1]) for l, f in pairs)
    return {'stones_matched': len(pairs), 'pieces_on_the_front': len(front_pieces),
            'distance_ratio': round(float(front_d / lid_d), 5),
            'area_ratios': [round(float(f[2] / l[2]), 4) for l, f in pairs],
            'farthest_from_its_place_mm': round(float(off), 4)}

def lockup_clearance(box_mm, safe_mm, keep_out):
    """A box on the panel (mm, origin the panel's top-left) against the front's safe area and the notch's keep-out
    disc (``keep_out``: cx, cy, r_mm on the panel): its clearance to each side of the safe area and to the disc
    (stick_carton.keep_out_clear_mm, the carton's own measure); holds when none is negative."""
    clear = {'left': box_mm[0] - safe_mm[0], 'top': box_mm[1] - safe_mm[1], 'right': safe_mm[2] - box_mm[2],
             'bottom': safe_mm[3] - box_mm[3], 'notch': sc.keep_out_clear_mm(box_mm, keep_out)}
    clear = {k: round(float(v), 3) for k, v in clear.items()}
    return {'clearance_mm': clear, 'inside_safe': min(clear['left'], clear['top'], clear['right'], clear['bottom']) >= 0,
            'below_the_notch': clear['notch'] >= 0 and box_mm[1] >= keep_out['cy'] + keep_out['r_mm'],
            'holds': min(clear.values()) >= 0 and box_mm[1] >= keep_out['cy'] + keep_out['r_mm']}


def across_fold(rgb, fold_px, px_per_mm, front_side):
    """The ground's continuity across a fold at column ``fold_px`` of an RGB render: per FOLD_BIN_MM of its length the
    ΔE00 between the mean colour of a strip FOLD_STRIP_MM off the fold on each side, and the ΔE00 of every pixel pair
    mirrored about it; holds when both means are at most FOLD_DE00_MAX. ``front_side`` ('left' or 'right') says which
    side is the front (recorded)."""
    near, far = int(round(FOLD_STRIP_MM[0] * px_per_mm)), int(round(FOLD_STRIP_MM[1] * px_per_mm))
    left = rgb[:, fold_px - far:fold_px - near][:, ::-1].astype(np.float64)
    right = rgb[:, fold_px + near:fold_px + far].astype(np.float64)
    pairs = lm.delta_e00(lm.srgb_to_lab(left), lm.srgb_to_lab(right))
    step = int(round(FOLD_BIN_MM * px_per_mm))
    bins = rgb.shape[0] // step
    lm_ = left[:bins * step].reshape(bins, -1, 3).mean(axis=1)
    rm_ = right[:bins * step].reshape(bins, -1, 3).mean(axis=1)
    binned = lm.delta_e00(lm.srgb_to_lab(lm_), lm.srgb_to_lab(rm_))
    front, side = rm_, lm_
    if front_side == 'left':
        front, side = lm_, rm_
    return {'front_side': front_side, 'strips_mm': list(FOLD_STRIP_MM), 'bins': int(bins), 'bin_mm': FOLD_BIN_MM,
            'binned_mean_de00': round(float(binned.mean()), 3), 'binned_max_de00': round(float(binned.max()), 3),
            'pairs_mean_de00': round(float(pairs.mean()), 3), 'pairs_p99_de00': round(float(np.percentile(pairs, 99)), 3),
            'front_mean': rgb_hex(front.mean(axis=0)), 'side_mean': rgb_hex(side.mean(axis=0)),
            'max_de00': FOLD_DE00_MAX,
            'holds': bool(binned.mean() <= FOLD_DE00_MAX and pairs.mean() <= FOLD_DE00_MAX)}


# --- the front ---------------------------------------------------------------------------------------------------------

def front_picture(product, wrap, lid_plate, lid_master, colours, out_png, drift_source='lid', plan=None):
    """The front picture (see the module's text). ``wrap``: the closed wrap's page (pdf), its words' boxes on it
    (boxes_mm, the lockup's lines top to bottom) and its ground (and its print plate, plate, for the wrap's drift).
    ``drift_source``: 'lid' (Day 12's drift) or 'wrap' (Day 13 §1.1: by ``plan``, written before the build). Returns the
    record — the boxes measured on the panel (mm, origin its top-left)."""
    if drift_source not in DRIFT_SOURCES:
        raise ValueError('the drift\'s source is %r, not one of %s' % (drift_source, DRIFT_SOURCES))
    coords, _ = sc.die(product)
    face = sc.faces(coords)['front']
    bx0, by0, bx1, by1 = face['box']
    gx0, gy0, gx1, gy1 = face['ground']
    safe = [face['safe'][0] - bx0, face['safe'][1] - by0, face['safe'][2] - bx0, face['safe'][3] - by0]
    notch = dict(face['keep_out'], cx=face['keep_out']['cx'] - bx0, cy=face['keep_out']['cy'] - by0)
    k = FRONT_PX_PER_MM
    W, H = int(round((gx1 - gx0) * k)), int(round((gy1 - gy0) * k))
    ox, oy = bx0 - gx0, by0 - gy0                     # the panel's top-left on the picture (mm)
    canvas = ground_canvas(W, H, colours['ground'])
    cover = np.zeros((H, W))
    # the lockup, as one piece: centred across the safe area, its top LOCKUP_BELOW_NOTCH_MM below the notch's keep-out
    pre, alpha, _, lock = lockup(wrap['pdf'], wrap['boxes_mm'], wrap['ground'], colours['ground'], safe[2] - safe[0])
    if drift_source == 'lid':
        master = json.loads(Path(lid_master).read_text(encoding='utf-8'))
        dpre, dalpha, dorigin, dk, drift = lid_drift(lid_plate, LID_DRIFT_REGION_MM, master, colours['ground'])
    ex = extent(alpha, ALPHA_SEEN)
    lock_w_mm = (ex[2] - ex[0]) / k
    room_top = notch['cy'] + notch['r_mm']
    top_mm = room_top + LOCKUP_BELOW_NOTCH_MM
    left_mm = (safe[0] + safe[2]) / 2 - lock_w_mm / 2
    x_px = int(round((ox + left_mm) * k)) - ex[0]
    y_px = int(round((oy + top_mm) * k)) - ex[1]
    lock_cover = np.zeros((H, W))
    paste(canvas, lock_cover, pre, alpha, x_px, y_px)
    cover = lock_cover.copy()
    le = extent(lock_cover, ALPHA_SEEN)
    lock_box = [le[0] / k - ox, le[1] / k - oy, le[2] / k - ox, le[3] / k - oy]
    if drift_source == 'lid':
        # the drift: the stones' union centred under the lockup, its top DRIFT_BELOW_LIPSTICK_MM under LIPSTICK's ink
        du = drift['stones_union_on_the_lid_mm']
        dst = ((lock_box[0] + lock_box[2]) / 2 - (du[2] - du[0]) / 2 + ox, lock_box[3] + DRIFT_BELOW_LIPSTICK_MM + oy)
        shift = (dst[0] - du[0], dst[1] - du[1])          # lid mm → picture mm
        drift_cover, scale_xy = warp_paste(canvas, cover, dpre, dalpha, dk, dorigin,
                                           (dorigin[0] + shift[0], dorigin[1] + shift[1]))
        src_alpha = dalpha
    else:
        # the drift: the plan's window of the wrap, its top-left on the lower front's top-left, 1 mm = 1 mm
        win = plan['window']
        if [round(v, 4) for v in lock_box] != win['lockup_box_on_the_front_mm']:
            raise ValueError('the lockup on the front %s is not the one the drift plan was written for %s'
                             % ([round(v, 4) for v in lock_box], win['lockup_box_on_the_front_mm']))
        wwin, fwin = win['on_the_wrap_mm'], win['on_the_front_mm']
        dpre, dalpha, dorigin, dk, inside, drift = wrap_drift(wrap['plate'], wwin, colours['ground'])
        shift = (fwin[0] + ox - wwin[0], fwin[1] + oy - wwin[1])        # wrap mm → picture mm
        clip = (fwin[0] + ox, fwin[1] + oy, fwin[2] + ox, fwin[3] + oy)
        clip = tuple(round(v * k) / k for v in clip)                     # the plan's rounding put back on the pixel edges
        drift_cover, scale_xy = area_paste(canvas, cover, dpre, dalpha, dk, dorigin,
                                           (dorigin[0] + shift[0], dorigin[1] + shift[1]), clip)
        src_alpha = dalpha * inside                                      # the window's own pixels on the plate
    de = extent(drift_cover, ALPHA_SEEN)
    drift_box = [de[0] / k - ox, de[1] / k - oy, de[2] / k - ox, de[3] / k - oy]
    le_ = extent(src_alpha, ALPHA_SEEN)                 # the same alpha at its source, the same threshold: 1:1 boxes
    lid_box = [dorigin[0] + le_[0] / dk[0], dorigin[1] + le_[1] / dk[1], dorigin[0] + le_[2] / dk[0],
               dorigin[1] + le_[3] / dk[1]]
    read = measured_scale(pieces_mm(src_alpha, dk, dorigin), pieces_mm(drift_cover, (k, k), (0.0, 0.0)), shift)
    Image.fromarray(np.clip(np.round(canvas), 0, 255).astype(np.uint8)).save(out_png, dpi=(FRONT_PPI, FRONT_PPI))
    # nothing drawn outside the safe area or inside the notch's keep-out (every pixel of the art's alpha)
    yy, xx = np.mgrid[0:H, 0:W]
    px_mm_x, px_mm_y = (xx + 0.5) / k - ox, (yy + 0.5) / k - oy
    half = 0.5 / k
    outside = ((px_mm_x + half <= safe[0]) | (px_mm_x - half >= safe[2]) | (px_mm_y + half <= safe[1])
               | (px_mm_y - half >= safe[3]))
    in_notch = np.hypot(px_mm_x - notch['cx'], px_mm_y - notch['cy']) + half < notch['r_mm']
    seen = cover > ALPHA_SEEN
    lock['scale_on_the_front'] = {'x': round((ex[2] - ex[0]) / k / lock['ink_width_on_the_wrap_mm'], 4),
                                  'said': 'the cut\'s own extent on the front over its extent on the wrap (its pixels '
                                          'round at the edge)'}
    lock.update({'box_on_the_front_mm': [round(v, 3) for v in lock_box],
                 'width_mm': round(lock_box[2] - lock_box[0], 3), 'height_mm': round(lock_box[3] - lock_box[1], 3),
                 'fills_of_the_safe_width': round((lock_box[2] - lock_box[0]) / (safe[2] - safe[0]), 4),
                 'check': lockup_clearance(lock_box, safe, notch),
                 'placed': 'centred across the safe area, its top %.1f mm below the notch\'s keep-out (%.3f mm)'
                           % (LOCKUP_BELOW_NOTCH_MM, room_top)})
    if drift_source == 'lid':
        drift.update({'scale': round(float(np.mean(scale_xy)), 6), 'scale_xy': [round(v, 9) for v in scale_xy],
                      'scale_said': '1 mm on the lid = 1 mm on the carton: the plate\'s pixels laid on the front\'s by '
                                    'their own mm (%.2f → %.2f px/mm, upsampled; never enlarged in mm) — the matrix\'s '
                                    'scale; scale_measured reads it back from the pixels' % (dk[0], k),
                      'scale_measured': read['distance_ratio'], 'scale_read_from_the_pixels': read,
                      'box_on_the_lid_at_the_same_alpha_mm': [round(v, 3) for v in lid_box],
                      'box_size_ratio_front_over_lid': [round((drift_box[2] - drift_box[0]) / (lid_box[2] - lid_box[0]), 4),
                                                        round((drift_box[3] - drift_box[1]) / (lid_box[3] - lid_box[1]), 4)],
                      'shift_lid_to_panel_mm': [round(shift[0] - ox, 3), round(shift[1] - oy, 3)],
                      'box_on_the_front_mm': [round(v, 3) for v in drift_box],
                      'below_lipstick_mm': round(drift_box[1] - lock_box[3], 3),
                      'check': lockup_clearance(drift_box, safe, notch)})
    else:
        # the coverage, as the plan defined it before the build: the lower front's stone share read from the written
        # picture (its pixels over STONE_DE ΔE76 from the carton's ground) against the wrap body's
        cov = dict(plan['coverage'])
        lower = cov['lower_front_mm']
        in_lower = (px_mm_x >= lower[0]) & (px_mm_x < lower[2]) & (px_mm_y >= lower[1]) & (px_mm_y < lower[3])
        written = np.asarray(Image.open(out_png).convert('RGB')).astype(np.float64)
        on_front = plate_distance(written, hex_rgb(colours['ground'])) > STONE_DE
        front_share = float(on_front[in_lower].mean())
        cov.update({'lower_front_share': round(front_share, 4), 'lower_front_px': int(in_lower.sum()),
                    'lower_front_share_of_the_cut_alpha': round(float((drift_cover > 0.5)[in_lower].mean()), 4),
                    'difference_from_the_wrap_body': round(front_share - cov['wrap_body_share'], 4),
                    'read_from': lm.rel(out_png)})
        cov['holds'] = bool(abs(front_share - cov['wrap_body_share']) <= cov['tolerance'])
        cx0, cy0, cx1, cy1 = (int(round(v * k)) for v in clip)
        front_edges = edge_alpha(drift_cover[cy0:cy1, cx0:cx1])
        must_not = win['edges_that_must_not_cut']
        on_trim = bool(abs(wwin[1] - WRAP_TRIM_MM[0]) < 1e-9)
        on_safe = bool(0.0 <= safe[2] - fwin[2] < 1.0 / k)
        whole = set(win['edges_that_cut']) | set(must_not) == {'top', 'right', 'bottom', 'left'}
        drift.update({'scale': round(float(np.mean(scale_xy)), 6), 'scale_xy': [round(v, 9) for v in scale_xy],
                      'scale_said': '1 mm on the wrap = 1 mm on the carton: the plate\'s pixels laid on the front\'s by '
                                    'their own mm (%.2f → %.2f px/mm, downsampled by area: each plate pixel its own '
                                    'square on a grid %d× the front\'s, averaged; never rescaled in mm) — the matrix\'s '
                                    'scale; scale_measured reads it back from the pixels' % (dk[0], k, AREA_SUPERSAMPLE),
                      'scale_measured': read['distance_ratio'], 'scale_read_from_the_pixels': read,
                      'area_read_by_alpha_mm2': {
                          'on_the_wrap': round(float(src_alpha.sum() / (dk[0] * dk[1])), 3),
                          'on_the_front': round(float(drift_cover.sum() / (k * k)), 3),
                          'ratio': round(float((drift_cover.sum() / (k * k)) / (src_alpha.sum() / (dk[0] * dk[1]))), 5),
                          'said': 'the art\'s alpha summed (its area as printed) on the front over the same on the '
                                  'wrap: the box filter keeps it; the pieces\' areas above, counted where alpha > 0.5, '
                                  'read a little larger on the front because averaging lifts a soft edge\'s low tail '
                                  'past 0.5'},
                      'box_on_the_wrap_at_the_same_alpha_mm': [round(v, 3) for v in lid_box],
                      'box_size_ratio_front_over_wrap': [
                          round((drift_box[2] - drift_box[0]) / (lid_box[2] - lid_box[0]), 4),
                          round((drift_box[3] - drift_box[1]) / (lid_box[3] - lid_box[1]), 4)],
                      'shift_wrap_to_panel_mm': [round(shift[0] - ox, 4), round(shift[1] - oy, 4)],
                      'window_on_the_front_mm': fwin, 'placed': win['placed'],
                      'unrolled': {'one_window': True, 'scale': 1.0, 'rotation_deg': 0.0, 'mirrored': False,
                                   'tiled': False, 'stones_moved': 0,
                                   'said': 'the window laid whole by one shift: nothing turned, flipped, repeated, '
                                           're-centred or rescaled'},
                      'box_on_the_front_mm': [round(v, 3) for v in drift_box],
                      'below_lipstick_mm': round(drift_box[1] - lock_box[3], 3),
                      'window_edge_alpha_on_the_front': {e: round(v, 4) for e, v in front_edges.items()},
                      'edges': {'that_cut': win['edges_that_cut'], 'that_must_not_cut': must_not,
                                'top_on_the_wraps_trim': on_trim, 'right_on_the_safe_line': on_safe,
                                'holds': bool(whole and on_trim and on_safe
                                              and all(front_edges[e] == 0.0 for e in must_not)),
                                'said': 'an edge may cut the bank only where the wrap\'s own trim cuts it (top) or on '
                                        'the front\'s safe line (right); every other edge carries no alpha'},
                      'coverage': cov,
                      'check': lockup_clearance(drift_box, safe, notch)})
    g_lab = lm.srgb_to_lab(hex_rgb(colours['ground'])[None, :])[0]
    saved = np.asarray(Image.open(out_png).convert('RGB')).astype(np.float64)[~seen]      # the calm ground, as written
    grain = saved.mean(axis=0)
    calm = lm.delta_e00(lm.srgb_to_lab(saved), g_lab[None, :])
    schema, said = SCHEMA, ('composed by the engine at $0 from the closed wrap\'s own page (the whole lockup, cut by its '
                            'ink, scaled as one piece) and the Day 12 lid\'s own stones (cut by their contours, at lid '
                            'scale) on one calm ground in the carton\'s colour; the hero printed in process colour (its '
                            'foil not carried)')
    if drift_source == 'wrap':
        schema, said = SCHEMA_WRAP, ('composed by the engine at $0 from the closed wrap\'s own page (the whole lockup, '
                                     'cut by its ink, scaled as one piece — as Day 12 placed it) and, beneath it, the '
                                     'wrap\'s own stone bank cut from its print plate at the wrap\'s scale (1 mm on the '
                                     'wrap = 1 mm on the carton; one window of the wrap laid as if unrolled onto the '
                                     'front: not turned, flipped, tiled or rescaled, no stone moved) on one calm ground '
                                     'in the carton\'s colour; the hero printed in process colour (its foil not carried)')
    rec = {'schema': schema, 'picture': lm.rel(out_png), 'px': [W, H], 'ppi': FRONT_PPI,
           'panel_mm': [round(bx1 - bx0, 3), round(by1 - by0, 3)], 'panel_on_the_picture_mm': [round(ox, 3), round(oy, 3)],
           'front_safe_mm': [round(v, 3) for v in safe],
           'notch_keep_out': {'cx': round(notch['cx'], 3), 'cy': round(notch['cy'], 3), 'r_mm': round(notch['r_mm'], 3),
                              'bottom_mm': round(room_top, 3),
                              'said': 'the thumb notch\'s radius plus stick_carton.NOTCH_CLEAR_MM (faces()); round 0 '
                                      'counted the 4 mm twice (12.041)'},
           'ground': {'colour': colours['ground'], 'grain_L_sd': GRAIN_L, 'grain_px': GRAIN_BLUR_PX,
                      'seed': GRAIN_SEED, 'grain_mean': rgb_hex(grain),
                      'grain_mean_de00': round(float(lm.delta_e00(lm.srgb_to_lab(grain[None, :]), g_lab[None, :])[0]), 4),
                      'calm_de00_mean': round(float(calm.mean()), 3), 'calm_de00_p99': round(float(np.percentile(calm, 99)), 3),
                      'said': 'one ground over the whole front, no patch, tile, mirror or vignette: the carton\'s ground '
                              'colour with a zero-mean grain in L*'},
           'lockup': lock, 'drift': drift,
           'art_outside_the_safe_area_px': int((seen & outside).sum()), 'art_in_the_notch_keep_out_px': int((seen & in_notch).sum()),
           'nothing_crosses': bool(not (seen & outside).any() and not (seen & in_notch).any()),
           'said': said}
    if drift_source == 'wrap':
        rec['drift_source'] = 'wrap'
    return rec


def readback(out, rec, faces_rec):
    """The front read back from the written engine file (engine/carton-engine.ai page 1, the flat on its 3 mm bleed):
    the ground's continuity across both folds (``across_fold``), and the lockup's ink (ΔE00 ≥ READBACK_DE00 off the
    ground, in its own rows) inside the box the composition measured."""
    import fitz
    bleed = sc.BLEED_MM
    front = faces_rec['front']['box_mm']
    k = FOLD_PPI / lm.MM_PER_INCH
    folds = {}
    with fitz.open(str(Path(out) / 'engine' / 'carton-engine.ai')) as doc:
        page = doc[0]
        for name, x_mm, front_side in (('left', front[0], 'right'), ('right', front[2], 'left')):
            clip = (x_mm + bleed - 2.0, front[1] + bleed + FOLD_END_MM, x_mm + bleed + 2.0, front[3] + bleed - FOLD_END_MM)
            rgb, origin = render_page(page, clip, k, False)
            fold_px = int(round((x_mm + bleed - origin[0]) * k))
            folds[name] = dict(across_fold(rgb, fold_px, k, front_side), fold_x_mm=round(x_mm, 3))
        rgb, origin = render_page(page, (front[0] + bleed, front[1] + bleed, front[2] + bleed, front[3] + bleed), k, False)
    box = rec['lockup']['box_on_the_front_mm']
    g_lab = lm.srgb_to_lab(hex_rgb(rec['ground']['colour'])[None, :])[0]
    off = (origin[0] - bleed - front[0], origin[1] - bleed - front[1])     # the render's first pixel, panel mm
    r0, r1 = int(np.floor((box[1] - 1.0 - off[1]) * k)), int(np.ceil((box[3] + 1.0 - off[1]) * k))
    band = rgb[max(r0, 0):r1]
    ink = lm.delta_e00(lm.srgb_to_lab(band), g_lab[None, None, :]) >= READBACK_DE00
    ys, xs = np.nonzero(ink)
    got = [off[0] + xs.min() / k, off[1] + (ys.min() + max(r0, 0)) / k, off[0] + (xs.max() + 1) / k,
           off[1] + (ys.max() + 1 + max(r0, 0)) / k]
    inside = (got[0] >= box[0] - READBACK_TOL_MM and got[1] >= box[1] - READBACK_TOL_MM
              and got[2] <= box[2] + READBACK_TOL_MM and got[3] <= box[3] + READBACK_TOL_MM)
    return {'read_from': lm.rel(Path(out) / 'engine' / 'carton-engine.ai'), 'ppi': FOLD_PPI,
            'folds': folds, 'folds_hold': all(f['holds'] for f in folds.values()),
            'lockup_read_mm': [round(v, 3) for v in got], 'lockup_composed_mm': box,
            'lockup_inside_its_box': bool(inside), 'tolerance_mm': READBACK_TOL_MM,
            'lockup_read_by': 'pixels at least %.1f ΔE00 off the ground in the lockup\'s rows (± 1 mm)' % READBACK_DE00}


def product_for(key, day12=DAY12, out_root=None):
    """The carton product with its folder: under ``out_root`` when passed (Day 13's), else under ``day12``."""
    root = Path(day12)
    if out_root is not None:
        root = Path(out_root)
    return products(root)[key]


def build(key, wrap, *, claims, day12=DAY12, out_root=None, drift_source='lid'):
    """One stick's carton at $0: Ẓilāl's colours from the Day 12 box's record, the front picture, ``stick_carton.build``
    into its folder (translations there), then the front read back from the written file. ``wrap``: the closed wrap's
    page (pdf), its words' boxes (boxes_mm), its ground, and for the wrap's drift its print plate (plate).
    ``out_root``: the day's folder the carton is written under (its product's folder there; Day 12's when None — the
    colours and the lid's plate are Day 12's either way). ``drift_source``: 'lid' (Day 12's drift) or 'wrap' (Day 13
    §1.1: by the plan ``write_plan`` wrote into the product's folder before this build; refused without it).
    Returns (record, report, front)."""
    if drift_source not in DRIFT_SOURCES:
        raise ValueError('the drift\'s source is %r, not one of %s' % (drift_source, DRIFT_SOURCES))
    product = product_for(key, day12, out_root)
    out = Path(product['out'])
    (out / 'engine').mkdir(parents=True, exist_ok=True)
    colours, source = carton_colours(day12 / 'zilal' / 'box' / 'box.json')
    plan = None
    if drift_source == 'wrap':
        plan = read_plan(out / PLAN_NAME)
    front = front_picture(product, wrap, day12 / 'zilal' / 'lid' / 'engine' / 'plate.png',
                          day12 / 'zilal' / 'lid' / 'master.json', colours, out / 'front-picture.png',
                          drift_source=drift_source, plan=plan)
    record, report = sc.build(out, product=product, picture=out / 'front-picture.png', colours=colours, claims=claims)
    front['colours'] = {'passed': colours, 'source': source, 'carton_record_colours': record['colours'],
                        'carton_record_colours_placeholder': record['colours_placeholder']}
    front['placed_by_the_carton_mm'] = record['front']['picture']['placed_mm']
    front['readback'] = readback(out, front, record['faces'])
    composed = bool(front['lockup']['check']['holds'] and front['drift']['check']['holds']
                    and front['nothing_crosses'] and front['readback']['folds_hold']
                    and front['readback']['lockup_inside_its_box'] and front['lockup']['window_edge_alpha'][1] == 0.0)
    if drift_source == 'lid':
        front['holds'] = bool(composed and front['drift']['region_edge_alpha'] == 0.0)
    else:
        path = out / PLAN_NAME
        front['drift']['plan'] = {'path': lm.rel(path), 'sha256': lm.sha256(path),
                                  'written_before_the_picture': bool(path.stat().st_mtime_ns
                                                                     < (out / 'front-picture.png').stat().st_mtime_ns)}
        front['holds'] = bool(composed and front['drift']['edges']['holds']
                              and front['drift']['coverage']['holds'] and front['drift']['ground_carried_px'] == 0
                              and front['drift']['plan']['written_before_the_picture'])
    record['front_composed'] = front
    lm.write_json(out / 'carton-front.json', front)
    return record, report, front
