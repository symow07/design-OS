"""Day 12 §2 (D-D12-2) — the family counter display's artwork in Ẓilāl's language: the header's sketch round (3,
gpt-image-2 high: the lid master as the style reference, the logo the only other input, the header's proportion from
the die, the safe area drawn on the sheet), J1's ranking of the three beside the lid, and the pick's crop. The sketch
sets the placement of the hero, the stones and the brand only: the master takes ظلال and "Enchanted Rose" as the lid's
own vectors, scaled (never re-traced)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from apps.pipeline.services import image_guard
from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import zilal_master as zm
from apps.pipeline.services import zilal_object as zo

DAY12 = zm.REPO / 'docs' / 'audit' / 'day-12'
DISPLAY = DAY12 / 'display'
HEADER = DISPLAY / 'header'
SKETCHES = HEADER / 'sketches'
DIE = DISPLAY / 'die' / 'die.json'
LID12 = DAY12 / 'zilal' / 'lid'
LID_FLAT = LID12 / 'lid-master-flat.png'          # the lid master re-traced by D-D12-9's reader: the style reference
SHEET_SIZE = '1536x1024'
SHEET_PX = (1536, 1024)
HEADER_W_PX = 1400                                 # the header's rectangle on the sheet, at the die's proportion
SAFE_DASH_PX = (6, 6)                              # the safe line drawn dashed: 6 px on, 6 px off
SAFE_GREY = (170, 170, 170, 255)
ASPECT_ERROR_MAX = 0.02                            # as D-D11-7: an aspect error over 2 % disqualifies
COUNT = 3


HEADER_SAFE_MM = 3.0                               # the die's safe and bleed (counter_tray_header.template_definition:
HEADER_BLEED_MM = 3.0                              # "each printed panel inset 3 mm", "each part's cut outline offset 3 mm")


def header_facts():
    """The header's trim from the solved die (die.json: the owner's 250 × 110, ⟪PROVISIONAL⟫), its bleed and safe the
    die's; never from a picture."""
    die = json.loads(DIE.read_text(encoding='utf-8'))
    w = die['owner_provisional']['header_width_mm']['value']
    h = die['owner_provisional']['header_height_mm']['value']
    return {'w_mm': w, 'h_mm': h, 'safe_mm': HEADER_SAFE_MM, 'bleed_mm': HEADER_BLEED_MM, 'source': lm.rel(DIE)}


def rectangle():
    """The header's rectangle on the sheet (x0, y0, x1, y1), centred, at the die's proportion; and its safe inset in
    px."""
    f = header_facts()
    w = HEADER_W_PX
    h = int(round(w * f['h_mm'] / f['w_mm']))
    x0 = (SHEET_PX[0] - w) // 2
    y0 = (SHEET_PX[1] - h) // 2
    inset = int(round(f['safe_mm'] * w / f['w_mm']))
    return (x0, y0, x0 + w, y0 + h), inset


def sheet():
    """The sheet the header's sketches are drawn on: white, the header's rectangle TRANSPARENT (what gpt-image-2 edits
    is the input's transparent part), its safe area drawn inside as a dashed grey line (opaque: kept by the edit at
    known pixels, cleaned from the master); the same picture is the mask."""
    SKETCHES.mkdir(parents=True, exist_ok=True)
    (x0, y0, x1, y1), inset = rectangle()
    img = Image.new('RGBA', SHEET_PX, (255, 255, 255, 255))
    img.paste(Image.new('RGBA', (x1 - x0, y1 - y0), (0, 0, 0, 0)), (x0, y0))
    draw = ImageDraw.Draw(img)
    on, off = SAFE_DASH_PX
    sx0, sy0, sx1, sy1 = x0 + inset, y0 + inset, x1 - inset - 1, y1 - inset - 1
    for x in range(sx0, sx1, on + off):
        draw.line([(x, sy0), (min(x + on - 1, sx1), sy0)], fill=SAFE_GREY)
        draw.line([(x, sy1), (min(x + on - 1, sx1), sy1)], fill=SAFE_GREY)
    for y in range(sy0, sy1, on + off):
        draw.line([(sx0, y), (sx0, min(y + on - 1, sy1))], fill=SAFE_GREY)
        draw.line([(sx1, y), (sx1, min(y + on - 1, sy1))], fill=SAFE_GREY)
    path = SKETCHES / 'sheet-transparent.png'
    img.save(path)
    return path


COMMON = (
    "Image 1 is the sheet to draw on: a white ground with one TRANSPARENT rectangle — the only place to draw — at the "
    "true proportion of a counter display's header card (%.0f × %.0f mm, %.3f : 1). Fill that rectangle EXACTLY, edge "
    "to edge, with flat print artwork; keep the white around it white; do not move, resize, tilt or round it. The thin "
    "dashed grey line inside it is the SAFE AREA (%.0f mm in from the trim): every letter and the logo stand wholly "
    "inside it; the stones may run under it to the trim; leave the dashed line itself as it is. No product, no "
    "palette, no lipstick, no display, no shadow, no ruler, no mockup, no labels. Image 2 is the closed lid of the same "
    "collection, Ẓilāl — the house's chosen design and the style reference: the deep indigo ground, the floated-stone "
    "marbling (battal, ebru: rose, coral, lilac, violet and teal stones with thin copper veins and crisp drag edges) and "
    "the Arabic name ظلال in engraved rose gold (a fine diagonal hatch inside a bevelled rose-gold rim), with \"Enchanted "
    "Rose\" in its rose-gold script. Image 3 is the BBROSE logo.\n\n"
    "THE HEADER stands above the display's back wall and carries the collection's name to the shopper: ظلال large, "
    "lettered exactly in the lid's manner (the same letters as image 2, larger), \"Enchanted Rose\" in the lid's own "
    "script, and the BBROSE logo (exactly as image 3, in rose gold), on the indigo ground with the floated stones. "
    "%s\n\n"
    "No other words. No petals, flowers, roses, arches, frames or borders; no 3D, no perspective; flat artwork only.")

PLACEMENTS = (
    'ظلال large and centred a little left of the middle, "Enchanted Rose" beneath it, the logo small at the upper right; '
    'the stones as one diagonal drift entering from the upper left corner and leaving along the bottom right, as on the '
    'lid, the lettering on open indigo.',
    'The logo small and centred at the top, ظلال large in the middle, "Enchanted Rose" centred beneath it; the stones '
    'as a band along the bottom edge, like the lid\'s lower drift, and a few small stones at the upper corners.',
    'ظلال large on the left half, "Enchanted Rose" and the logo stacked on the right half; the stones as a drift rising '
    'from the lower left behind the lettering\'s foot and a second smaller drift at the upper right, open indigo between.',
)


def prompt(n):
    f = header_facts()
    return COMMON % (f['w_mm'], f['h_mm'], f['w_mm'] / f['h_mm'], f['safe_mm'], PLACEMENTS[n - 1])


def sketch(n, *, client):
    """One header sketch on the transparent sheet (the sheet its own mask), then cropped at its trim."""
    dest = SKETCHES / ('S%d' % n)
    logo_path, _ = image_guard.APPROVED_LOGO
    sheet_png = sheet()
    items = [{'role': 'the sheet: the header\'s rectangle, transparent, its safe area dashed', 'path': str(sheet_png)},
             {'role': 'the Ẓilāl lid master — the style reference', 'path': str(LID_FLAT)},
             {'role': 'the approved BBROSE logo', 'path': str(logo_path)}]
    rec = zo._guarded_edit('header sketch S%d' % n, dest, items, prompt(n), client=client, mask=sheet_png,
                           operation_suffix='display/header/S%d' % n, size=SHEET_SIZE)
    rec['crop'] = crop(dest)
    return rec


PANEL_WHITE = 235                                  # the sheet's white: a pixel with every channel ≥ 235
PANEL_ROW_SHARE = 0.5                              # a row or column of the drawn panel is at least half non-white
LETTER_HUE = (44.0, 72.0)                          # the lettering's rose gold (the stones' coral lies under 44°)
LETTER_C_MIN = 14.0
LETTER_L_MIN = 38.0
LETTER_CLOSE_PX = 9                                # the hatch closed into solid letters …
LETTER_OPEN_PX = 3                                 # … specks opened away
LETTER_PART_MIN_PX = 300
LETTER_RING_PX = 21                                # a lettering part stands on open indigo: ≥ 60 % of a 10 px ring
LETTER_RING_GROUND = 0.6                           # around it is the ground (L* < 22, b* < −8), never among stones
GROUND_L_MAX = 22.0
GROUND_B_MAX = -8.0


PANEL_EDGE_PX = 2                                  # the drawn panel read 2 px inside its edge (its anti-aliased row
                                                   # against the white, as the wraps' trim line was dropped on Day 11)


def drawn_panel(picture):
    """The header as the model drew it: the box of the rows and columns at least half non-white, 2 px inside."""
    nonwhite = picture.min(axis=2) < PANEL_WHITE
    rows = np.nonzero(nonwhite.mean(axis=1) > PANEL_ROW_SHARE)[0]
    cols = np.nonzero(nonwhite.mean(axis=0) > PANEL_ROW_SHARE)[0]
    e = PANEL_EDGE_PX
    return [int(cols.min()) + e, int(rows.min()) + e, int(cols.max()) + 1 - e, int(rows.max()) + 1 - e]


def lettering_box(picture):
    """The box of the sketch's lettering (the hero, the name, the logo): its rose-gold parts (hue 44–72°, the hatch
    closed) that stand on open indigo — a stone's coppery edge among stones is not a letter."""
    import cv2
    lab = lm.srgb_to_lab(picture)
    light, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    chroma = np.hypot(a, b)
    hue = np.degrees(np.arctan2(b, a)) % 360
    gold = ((hue >= LETTER_HUE[0]) & (hue <= LETTER_HUE[1]) & (chroma >= LETTER_C_MIN) & (light >= LETTER_L_MIN))
    gold = cv2.morphologyEx(gold.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((LETTER_CLOSE_PX,) * 2, np.uint8))
    gold = cv2.morphologyEx(gold, cv2.MORPH_OPEN, np.ones((LETTER_OPEN_PX,) * 2, np.uint8))
    ground = (light < GROUND_L_MAX) & (b < GROUND_B_MAX)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(gold, 8)
    boxes = []
    for i in range(1, n):
        if stats[i, 4] < LETTER_PART_MIN_PX:
            continue
        part = (labels == i).astype(np.uint8)
        ring = cv2.dilate(part, np.ones((LETTER_RING_PX,) * 2, np.uint8)).astype(bool) & (gold == 0)
        if ground[ring].mean() >= LETTER_RING_GROUND:
            x, y, w, h, _ = stats[i]
            boxes.append((x, y, x + w, y + h))
    return [int(min(v[0] for v in boxes)), int(min(v[1] for v in boxes)), int(max(v[2] for v in boxes)),
            int(max(v[3] for v in boxes))], len(boxes)


def crop(dest):
    """The header framed at the die's proportion. The sketch's drawn panel is read (the model may not keep to the
    sheet's rectangle) and its aspect error recorded; the frame is the largest window of the die's proportion inside
    the drawn panel that holds every letter and the logo inside the 3 mm safe area — centred on the lettering, kept
    inside the panel — cropped, never stretched. A sketch whose lettering cannot stand in such a frame is disqualified
    (its placement does not fit the header)."""
    picture = np.asarray(Image.open(dest / 'picture.png').convert('RGB'))
    if picture.shape[1] != SHEET_PX[0] or picture.shape[0] != SHEET_PX[1]:
        raise ValueError('the sketch is %s px, not the sheet\'s %s' % (picture.shape[1::-1], SHEET_PX))
    f = header_facts()
    true = f['w_mm'] / f['h_mm']
    px0, py0, px1, py1 = drawn_panel(picture)
    pw, ph = px1 - px0, py1 - py0
    letters, parts = lettering_box(picture)
    fw = min(float(pw), ph * true)
    fh = fw / true
    safe = f['safe_mm'] * fw / f['w_mm']
    need = [letters[2] - letters[0] + 2 * safe, letters[3] - letters[1] + 2 * safe]
    record = {'sheet_box_px': list(rectangle()[0]), 'drawn_panel_px': [px0, py0, px1, py1],
              'drawn_aspect': round(pw / ph, 4), 'aspect_true': round(true, 4),
              'drawn_aspect_error': round(abs(pw / ph - true) / true, 4), 'lettering_box_px': letters,
              'lettering_parts': parts, 'frame_max_px': [round(fw, 1), round(fh, 1)],
              'lettering_needs_px': [round(v, 1) for v in need],
              'rule': 'the drawn panel framed at the die\'s 250 : 110 by the least crop that holds every letter and the '
                      'logo inside the 3 mm safe area; nothing stretched; a sketch whose lettering cannot stand in that '
                      'frame is disqualified (D-D12-8: no second round)'}
    if need[0] > fw or need[1] > fh:
        short = [name for name, n_, f_ in (('width', need[0], fw), ('height', need[1], fh)) if n_ > f_]
        record.update({'qualifies': False, 'fails_on': short,
                       'why': 'its lettering needs %.0f × %.0f px with the safe area; a frame of the header\'s proportion '
                              'inside its drawn panel is %.0f × %.0f: short in %s' % (need[0], need[1], fw, fh,
                                                                                      ' and '.join(short))})
        lm.write_json(dest / 'crop.json', record)
        return record
    cx, cy = (letters[0] + letters[2]) / 2.0, (letters[1] + letters[3]) / 2.0
    x0 = min(max(cx - fw / 2.0, letters[2] + safe - fw, px0), letters[0] - safe, px1 - fw)
    y0 = min(max(cy - fh / 2.0, letters[3] + safe - fh, py0), letters[1] - safe, py1 - fh)
    box = [int(round(x0)), int(round(y0)), int(round(x0 + fw)), int(round(y0 + fh))]
    out = picture[box[1]:box[3], box[0]:box[2]]
    Image.fromarray(out).save(dest / 'header.png')
    w_px = box[2] - box[0]
    record.update({'qualifies': True, 'box_px': box, 'aspect': round(w_px / (box[3] - box[1]), 4),
                   'aspect_error': round(abs(w_px / (box[3] - box[1]) - true) / true, 4),
                   'safe_inset_px': round(safe, 1), 'px_per_mm': round(w_px / f['w_mm'], 4),
                   'ppi': round(w_px / f['w_mm'] * lm.MM_PER_INCH, 1),
                   'lettering_inside_safe': bool(box[0] + safe <= letters[0] and letters[2] <= box[2] - safe
                                                 and box[1] + safe <= letters[1] and letters[3] <= box[3] - safe),
                   'file': lm.rel(dest / 'header.png')})
    lm.write_json(dest / 'crop.json', record)
    return record


def safe_line_mask():
    """The safe line's pixels inside the header's crop (the sheet's opaque grey dashes), to be cleaned."""
    sheet_png = SKETCHES / 'sheet-transparent.png'
    img = np.asarray(Image.open(sheet_png).convert('RGBA'))
    (x0, y0, x1, y1), _ = rectangle()
    return img[y0:y1, x0:x1, 3] > 0


def beside_the_lid(dest):
    """The lid (left) and the header (right) at the lid's height, for J1."""
    lid = Image.open(LID_FLAT).convert('RGB')
    h = 640
    lid = lid.resize((int(lid.width * h / lid.height), h), Image.LANCZOS)
    header = Image.open(dest / 'header.png').convert('RGB')
    header = header.resize((int(header.width * h / header.height * 0.62), int(h * 0.62)), Image.LANCZOS)
    pair = Image.new('RGB', (lid.width + 24 + header.width, h), 'white')
    pair.paste(lid, (0, 0))
    pair.paste(header, (lid.width + 24, (h - header.height) // 2))
    path = SKETCHES / ('%s-beside-the-lid.png' % dest.name)
    pair.save(path)
    return path


FACTS = ('THE DISPLAY (D-D12-2, ⟪PROVISIONAL⟫ dimensions, the owner\'s to correct): the family counter display, the '
         'house\'s own form — a tapered counter tray with a header; footprint 250 × 160 mm; the header 250 × 110 mm '
         'above the back wall; it holds two Ẓilāl palettes in a slot at the back and two rows of six sticks (the lip '
         'balm in front, the lipstick behind). The header carries ظلال, "Enchanted Rose" and the BBROSE logo on the '
         'lid\'s indigo with its floated stones; its master takes ظلال and "Enchanted Rose" as the lid\'s own vectors.')


def rank(*, client):
    """J1 ranks the qualified header sketches, each beside the lid, with the anchors (rubric v2)."""
    from apps.pipeline.services import jury
    shown, dropped = [], []
    for n in range(1, COUNT + 1):
        dest = SKETCHES / ('S%d' % n)
        rec = json.loads((dest / 'crop.json').read_text(encoding='utf-8'))
        (shown if rec['qualifies'] else dropped).append((n, dest, rec))
    if not shown:
        raise ValueError('no header sketch qualifies')
    pictures = [str(beside_the_lid(dest)) for _, dest, _ in shown]
    checks = ['header sketch S%d beside the lid (left): placement — %s' % (n, PLACEMENTS[n - 1]) for n, _, _ in shown]
    direction = json.loads((zm.REPO / 'docs' / 'audit' / 'day-9' / 'directions' / 'B-1.json').read_text(encoding='utf-8'))
    spec = ('Rank the header sketches for the counter display of the Ẓilāl collection. Each is shown beside the lid (left), '
            'the design of record. The header must read as the same collection at a glance from 500 mm: ظلال large and '
            'legible, lettered in the lid\'s manner; the logo and "Enchanted Rose" clear; the stones in the lid\'s '
            'floated manner, not wallpaper; every letter inside the safe area. A sketch that loses the hero, the words or '
            'the lid\'s colours ranks below.')
    rec = jury.rank_sketches_v2(pictures, anchors=zm.anchors(), facts=FACTS + '\n' + zm.BAR, spec=spec,
                                direction_idea='B-1: ' + direction['idea'], operation=zm.RANK_PREFIX + 'display-header',
                                destination=SKETCHES / 'ranking.json', rubric_version='v2', effort='medium',
                                reservation_prefix=zm.RANK_PREFIX, reservation_cap=zm.RANK_CAP_USD, checks=checks,
                                client=client)
    order = [{'sketch': 'S%d' % shown[r['sketch'] - 1][0], 'rank': r['rank'], 'score': r['score']}
             for r in rec['payload']['ranking']]
    lm.write_json(SKETCHES / 'ranking-map.json', {'shown': ['S%d' % n for n, _, _ in shown],
                                                  'dropped': ['S%d' % n for n, _, _ in dropped], 'order': order})
    return rec, order
