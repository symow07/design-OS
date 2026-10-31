"""Day 12 §3 (D-D12-3) — the lip balm in Ẓilāl's language, by the lipstick's path: one sketch round of 6 on Day 11's
transparent sheet (S3-retry's format) with the front third drawn on it and named in the prompt; J1's ranking with the
front-third check (measured: the hero's ink inside the front third of the Ø 18 case); if no sketch passes it, J1's top
is picked and scaled as D-D12-1.1 scales the lipstick's — no second round."""
from __future__ import annotations

import json

import cv2
import numpy as np
from PIL import Image, ImageDraw

from apps.pipeline.services import image_guard
from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import zilal_display as zd
from apps.pipeline.services import zilal_lipstick_master as zlm
from apps.pipeline.services import zilal_master as zm
from apps.pipeline.services import zilal_object as zo

BALM = zd.DAY12 / 'balm'
SKETCHES = BALM / 'sketches'
SHEET_SIZE = '1024x1536'
SHEET_PX = (1024, 1536)
CASE_D_MM = 18.0                                   # D-D11-8 / D-D12-3 (⟪PROVISIONAL⟫): closed 70 × Ø 18
WRAPS_MM = {'body': (58.5, 42.0), 'cap': (58.5, 32.0)}   # the visible 40 and 30 mm plus 1 mm bleed top and bottom
BLEED_TB_MM = 1.0
SAFE_TB_MM = 2.0
WRAP_W_PX = 900
TRIM_GREY = (150, 150, 150, 255)
THIRD_GREY = (120, 120, 120, 255)
DASH_PX = (6, 6)
ASPECT_ERROR_MAX = 0.02                            # D-D11-7: an aspect error over 2 % disqualifies
COUNT = 6
FACTS = ('THE LIP BALM (D-D11-8 / D-D12-3, ⟪PROVISIONAL⟫ facts, the owner\'s to correct): a slim round stick, closed 70 × '
         'Ø 18 mm; cap 30 mm, body 40 mm; net 4.5 g ℮ 0.15 oz; "Lip Balm", the hero بلسم, the tint "Rosewater". Wraps: '
         'the body 58.5 × 42 mm and the cap 58.5 × 32 mm (the circumference plus a 2 mm overlap, by the visible height '
         'plus 1 mm bleed top and bottom), the seam at the back; a bottom label Ø 16 (the tint and the net content).')


def wrap_px(key):
    w_mm, h_mm = WRAPS_MM[key]
    return WRAP_W_PX, int(round(WRAP_W_PX * h_mm / w_mm))


def rectangles():
    """The two wraps' boxes on the sheet (x0, y0, x1, y1): the body above, the cap below, centred, even gaps."""
    bw, bh = wrap_px('body')
    cw, ch = wrap_px('cap')
    gap = (SHEET_PX[1] - bh - ch) // 3
    x0 = (SHEET_PX[0] - WRAP_W_PX) // 2
    return {'body': (x0, gap, x0 + bw, gap + bh), 'cap': (x0, 2 * gap + bh, x0 + cw, 2 * gap + bh + ch)}


def front_third_px(key, box):
    """The wrap's front third on the sheet (px), within its top and bottom 2 mm safe margins."""
    third = zlm.front_third(WRAPS_MM[key][0], CASE_D_MM)
    k = (box[2] - box[0]) / WRAPS_MM[key][0]
    m = int(round((BLEED_TB_MM + SAFE_TB_MM) * k))
    return (box[0] + int(round(third['span_mm'][0] * k)), box[1] + m, box[0] + int(round(third['span_mm'][1] * k)),
            box[3] - m), third


def _dashed_rect(draw, box, fill):
    on, off = DASH_PX
    x0, y0, x1, y1 = box
    for x in range(x0, x1, on + off):
        draw.line([(x, y0), (min(x + on - 1, x1), y0)], fill=fill)
        draw.line([(x, y1), (min(x + on - 1, x1), y1)], fill=fill)
    for y in range(y0, y1, on + off):
        draw.line([(x0, y), (x0, min(y + on - 1, y1))], fill=fill)
        draw.line([(x1, y), (x1, min(y + on - 1, y1))], fill=fill)


def sheet():
    """The sheet (Day 11's S3-retry format): white, each wrap's rectangle TRANSPARENT inside a 1 px grey trim line,
    the front third drawn inside each as a dashed box (opaque grey, kept by the edit at known pixels); the same picture
    is the mask."""
    SKETCHES.mkdir(parents=True, exist_ok=True)
    img = Image.new('RGBA', SHEET_PX, (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    for key, box in rectangles().items():
        draw.rectangle([box[0] - 1, box[1] - 1, box[2], box[3]], outline=TRIM_GREY, width=1)
        img.paste(Image.new('RGBA', (box[2] - box[0], box[3] - box[1]), (0, 0, 0, 0)), (box[0], box[1]))
        third, _ = front_third_px(key, box)
        _dashed_rect(draw, third, THIRD_GREY)
    path = SKETCHES / 'sheet-transparent.png'
    img.save(path)
    return path


COMMON = (
    "Image 1's two rectangles are TRANSPARENT: they are the only places to draw, and each must be filled exactly, edge to "
    "edge, at its own size and proportion; the white around them stays white. Image 1 is the sheet to draw on: a white "
    "ground with two rectangles outlined by thin grey trim lines, each 900 px wide at the true proportion of a lip balm's "
    "wrap: the TOP one the body (58.5 × 42 mm, 1.393 : 1), the BOTTOM one the cap (58.5 × 32 mm, 1.828 : 1). Fill each "
    "EXACTLY to its trim lines with flat print artwork, edge to edge; draw nothing outside the rectangles; do not move, "
    "resize, tilt or round them. No product, no tube, no shadow, no ruler, no mockup, no labels. Inside each rectangle a "
    "DASHED BOX marks THE FRONT THIRD of the round stick (Ø 18 mm): the wrap closes at the back, so only the front third "
    "is seen at once — the hero word and every other word stand WHOLLY INSIDE the dashed box; leave the dashed lines as "
    "they are. Image 2 is the closed lid of the same collection, Ẓilāl — the house's chosen design and the style "
    "reference: the deep indigo ground, the floated-stone marbling (battal, ebru: rose, coral, lilac, violet and teal "
    "stones with thin copper veins and crisp drag edges) and the Arabic name in engraved rose gold (a fine diagonal hatch "
    "inside a bevelled rose-gold rim). Image 3 is the BBROSE logo.\n\n"
    "THE BODY (top): the hero Arabic word بلسم (balm), large but wholly inside the dashed front third, in the lid's "
    "engraved rose gold, lettered in the lid's manner; \"Enchanted Rose\" in the lid's own rose-gold script, small, "
    "under the hero inside the front third; \"Lip Balm\" in small clean cream capitals under it. Nothing essential within "
    "2 mm of the top and bottom edges. The stones: %s.\n\n"
    "THE CAP (bottom): only the stones and the BBROSE logo (exactly as image 3, small, in rose gold, centred in the front "
    "third); no other words. The stones: %s.\n\n"
    "THE SEAM (the most important physical rule): on BOTH wraps, the outer sixth at the left and the outer sixth at the "
    "right are PLAIN FLAT INDIGO — no stone, vein or letter reaches either side edge, because the two side edges meet at "
    "the back. No petals, flowers, roses, arches or frames; no 3D, no perspective; flat artwork only.")

STONES = (
    ('a band of floated stones sweeping diagonally behind the front third, thinning to plain indigo at both edges',
     'a matching diagonal drift of small stones behind the logo'),
    ('a band of floated stones along the bottom of the body like the lid\'s lower drift, the hero on calm indigo above',
     'a band of stones along the top of the cap'),
    ('a narrow river of small stones running across above the hero, a few stones drifting below it',
     'a small cluster of stones round the logo, open indigo toward both edges'),
    ('two drifts of stones entering the front third from its upper left and lower right, as the lid\'s two drifts, the '
     'hero between them on open indigo', 'one drift crossing behind the logo'),
    ('large floated stones gathered at the top of the front third, the hero below them on open indigo, small scattered '
     'stones toward the edges', 'an arc of small stones above the logo'),
    ('sparse floated stones scattered lightly, the hero dominant inside the front third',
     'a dense cluster of stones in the front third with the logo beneath it'),
)


def prompt(n):
    body, cap = STONES[n - 1]
    return COMMON % (body, cap)


def sketch(n, *, client):
    """Sketch n (1–6) on the transparent sheet (its own mask), then cropped at its trim lines."""
    dest = SKETCHES / ('S%d' % n)
    logo_path, _ = image_guard.APPROVED_LOGO
    sheet_png = sheet()
    items = [{'role': 'the sheet: the two wraps\' rectangles, transparent, the front third dashed', 'path': str(sheet_png)},
             {'role': 'the Ẓilāl lid master — the style reference', 'path': str(zd.LID_FLAT)},
             {'role': 'the approved BBROSE logo', 'path': str(logo_path)}]
    rec = zo._guarded_edit('balm sketch S%d' % n, dest, items, prompt(n), client=client, mask=sheet_png,
                           operation_suffix='balm/S%d' % n, size=SHEET_SIZE)
    rec['crop'] = crop_wraps(dest)
    return rec


def drawn_box(picture, box):
    """A wrap as the model drew it near where the sheet put it: the non-white region (min channel < 200, closed 5 px)
    overlapping the sheet's box most; 2 px inside its edge (the trim line's anti-aliased row dropped)."""
    near = picture.min(axis=2) < 200
    near = cv2.morphologyEx(near.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(near, connectivity=8)
    best, best_overlap = None, 0
    for i in range(1, n):
        left, top, w, h, _ = stats[i]
        ox = max(0, min(left + w, box[2]) - max(left, box[0]))
        oy = max(0, min(top + h, box[3]) - max(top, box[1]))
        if ox * oy > best_overlap:
            best, best_overlap = (int(left) + 2, int(top) + 2, int(left + w) - 2, int(top + h) - 2), ox * oy
    return best


def crop_wraps(dest):
    """Each wrap cropped at its drawn trim (never stretched): its aspect against the true one (2 %), the sketch
    qualifying when both hold; the body's front-third check measured (``front_third_check``)."""
    picture = np.asarray(Image.open(dest / 'picture.png').convert('RGB'))
    rows = {}
    for key, box in rectangles().items():
        found = drawn_box(picture, box)
        if found is None:
            rows[key] = {'found': False, 'qualifies': False}
            continue
        x0, y0, x1, y1 = found
        Image.fromarray(picture[y0:y1, x0:x1]).save(dest / ('%s.png' % key))
        true = WRAPS_MM[key][0] / WRAPS_MM[key][1]
        aspect = (x1 - x0) / (y1 - y0)
        error = abs(aspect - true) / true
        rows[key] = {'found': True, 'box_px': [x0, y0, x1, y1], 'sheet_box_px': list(box), 'aspect': round(aspect, 4),
                     'aspect_true': round(true, 4), 'aspect_error': round(error, 4),
                     'qualifies': bool(error <= ASPECT_ERROR_MAX), 'file': lm.rel(dest / ('%s.png' % key))}
    record = {'wraps': rows, 'qualifies': all(r['qualifies'] for r in rows.values()),
              'rule': 'D-D11-7: cropped at the drawn trim; an aspect error over 2 % disqualifies; nothing stretched'}
    if rows['body'].get('found'):
        record['front_third'] = front_third_check(dest / 'body.png')
    lm.write_json(dest / 'crop.json', record)
    return record


def front_third_check(body_png):
    """D-D12-1.1's rule, measured on the body as drawn: the hero (the tallest rose-gold word on open indigo) and its ink
    box against the front third of the Ø 18 case (mm on the 58.5 mm wrap)."""
    from apps.pipeline.services import zilal_header as zh
    rgb = np.asarray(Image.open(body_png).convert('RGB'))
    k = rgb.shape[1] / WRAPS_MM['body'][0]
    _, hero = zh.gold_words(rgb, k)
    third = zlm.front_third(WRAPS_MM['body'][0], CASE_D_MM)
    if hero is None:
        return {'hero_found': False, 'passes': False, 'span_mm': third['span_mm']}
    x0, y0, x1, y1 = [v / k for v in hero['box_px']]
    lo, hi = third['span_mm']
    return {'hero_found': True, 'hero_ink_mm': [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
            'hero_width_mm': round(x1 - x0, 2), 'span_mm': third['span_mm'], 'width_mm': third['width_mm'],
            'passes': bool(lo <= x0 and x1 <= hi), 'scale_to_fit': round(min(1.0, third['width_mm'] / (x1 - x0)), 4)}


def beside_the_lid(dest):
    """The lid (left) and a sketch's two wraps stacked as cropped (right, body above cap), at the lid's height."""
    lid = Image.open(zd.LID_FLAT).convert('RGB')
    h = 900
    lid = lid.resize((int(lid.width * h / lid.height), h), Image.LANCZOS)
    body = Image.open(dest / 'body.png').convert('RGB')
    cap = Image.open(dest / 'cap.png').convert('RGB')
    bh = int((h - 24) * 42 / 74)
    ch = h - 24 - bh
    body = body.resize((int(body.width * bh / body.height), bh), Image.LANCZOS)
    cap = cap.resize((int(cap.width * ch / cap.height), ch), Image.LANCZOS)
    right = max(body.width, cap.width)
    pair = Image.new('RGB', (lid.width + 24 + right, h), 'white')
    pair.paste(lid, (0, 0))
    pair.paste(body, (lid.width + 24, 0))
    pair.paste(cap, (lid.width + 24, bh + 24))
    path = SKETCHES / ('%s-beside-the-lid.png' % dest.name)
    pair.save(path)
    return path


def front_third_of(crop_record):
    """A sketch's measured front-third check (``crop_wraps``); a sketch whose body was not found has none: it fails."""
    if 'front_third' in crop_record:
        return crop_record['front_third']
    return {'hero_found': False, 'passes': False}


def rank(*, client):
    """J1 ranks the qualified sketches, each beside the lid, with the anchors (rubric v2) and each one's measured
    front-third check; a disqualified sketch is not shown and is recorded."""
    from apps.pipeline.services import jury
    shown, dropped = [], []
    for n in range(1, COUNT + 1):
        dest = SKETCHES / ('S%d' % n)
        rec = json.loads((dest / 'crop.json').read_text(encoding='utf-8'))
        (shown if rec['qualifies'] else dropped).append((n, dest, rec))
    if not shown:
        raise ValueError('no balm sketch qualifies')
    pictures = [str(beside_the_lid(dest)) for _, dest, _ in shown]
    checks = []
    for n, dest, rec in shown:
        ft = front_third_of(rec)
        checks.append('S%d: body %.3f / cap %.3f (true 1.393 / 1.828); front third: %s' % (
            n, rec['wraps']['body']['aspect'], rec['wraps']['cap']['aspect'],
            ('the hero %.1f mm wide, %s the front third (%.1f–%.1f mm)' % (ft['hero_width_mm'], 'inside' if ft['passes']
                                                                          else 'NOT inside', *ft['span_mm']))
            if ft.get('hero_found') else 'no hero read'))
    direction = json.loads((zm.REPO / 'docs' / 'audit' / 'day-9' / 'directions' / 'B-1.json').read_text(encoding='utf-8'))
    spec = ('THE ROUND (Day 12, D-D12-3). Each image shows THE LID MASTER on the left (the collection\'s chosen design, '
            'for reference — not ranked) and ONE SKETCH on the right: the lip balm\'s body wrap above its cap wrap, each '
            'flat, closing at a seam at the back. THE FRONT-THIRD RULE (D-D12-1.1, binding every wrap from now): on a Ø 18 '
            'stick only the front third (18.8 mm of the 56.5 mm round) is seen at once, so the hero بلسم must sit wholly '
            'inside it — each sketch\'s measured front-third check is given. Rank the sketches: which carries the lid\'s '
            'language (%s) onto a lip balm best, keeps the front-third rule, and is the best to build? A sketch that '
            'breaks the rule or the language, puts a letter or stone across the seam, or draws petals or frames ranks '
            'lower.' % zo.IDEA)
    rec = jury.rank_sketches_v2(pictures, anchors=zm.anchors(), facts=FACTS + '\n' + zm.BAR, spec=spec,
                                direction_idea='B-1: ' + direction['idea'], operation=zm.RANK_PREFIX + 'balm',
                                destination=SKETCHES / 'ranking.json', rubric_version='v2', effort='medium',
                                reservation_prefix=zm.RANK_PREFIX, reservation_cap=zm.RANK_CAP_USD, checks=checks,
                                client=client)
    order = [{'sketch': 'S%d' % shown[r['sketch'] - 1][0], 'rank': r['rank'], 'score': r['score'],
              'front_third_passes': front_third_of(shown[r['sketch'] - 1][2])['passes']}
             for r in rec['payload']['ranking']]
    lm.write_json(SKETCHES / 'ranking-map.json', {'shown': ['S%d' % n for n, _, _ in shown],
                                                  'dropped': {'S%d' % n: r['wraps'] for n, _, r in dropped},
                                                  'order': order, 'checks': checks})
    return rec, order


def the_pick():
    """D-D12-3: the owner's PICK file (one line) in the 20 minutes, else J1's highest-ranked sketch that passes the
    front-third check, else J1's top — then scaled as D-D12-1.1 scales the lipstick's (no second round)."""
    ranking = json.loads((SKETCHES / 'ranking-map.json').read_text(encoding='utf-8'))
    pick_file = SKETCHES / 'PICK'
    if pick_file.exists():
        return pick_file.read_text(encoding='utf-8').strip().upper(), 'the owner\'s PICK file', None
    order = sorted(ranking['order'], key=lambda r: r['rank'])
    passing = [r for r in order if r['front_third_passes']]
    if passing:
        return passing[0]['sketch'], 'J1\'s highest-ranked sketch that passes the front-third check', None
    return order[0]['sketch'], 'J1\'s top: no sketch passes the front-third check (D-D12-3: scaled as D-D12-1.1)', 'scale'
