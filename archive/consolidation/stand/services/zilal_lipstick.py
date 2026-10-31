"""Day 11 §3 — the lipstick in Ẓilāl's language (D-D11-7): the sketch round.

Six sketches (gpt-image-2 high, 1024 × 1536 portrait) on a sheet holding the body wrap and the cap wrap as trim-lined
rectangles at their true proportion (64.8 × 42 mm, 1.543 : 1, each 900 px wide); the lid master the style reference
and the logo the only other inputs. Each sketch is cropped at its trim lines; an aspect error over 2 % disqualifies it,
nothing is stretched. J1 ranks the qualified sketches, each beside the lid. The facts are ⟪PROVISIONAL⟫, the owner's to
correct.
"""
from __future__ import annotations

import json

import cv2
import numpy as np
from PIL import Image, ImageDraw

from apps.pipeline.services import image_guard
from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import zilal_master as zm
from apps.pipeline.services import zilal_object as zo

LIP = zm.DAY11 / 'lipstick'
SKETCHES = LIP / 'sketches'
SHEET_SIZE = '1024x1536'
SHEET_PX = (1024, 1536)
WRAP_MM = (64.8, 42.0)              # the circumference (π × 20) plus a 2 mm overlap, by the visible 40 mm plus 1 mm bleed
ASPECT = WRAP_MM[0] / WRAP_MM[1]    # 1.543
WRAP_W_PX = 900
WRAP_H_PX = int(round(WRAP_W_PX / ASPECT))
ASPECT_ERROR_MAX = 0.02             # D-D11-7: an aspect error over 2 % disqualifies
TRIM_GREY = (150, 150, 150)
COUNT = 6
FACTS = ('THE LIPSTICK (D-D11-7, ⟪PROVISIONAL⟫ facts, the owner\'s to correct): a round case, closed 80 × Ø 20 mm; cap '
         '40 mm, body 40 mm; bullet 12.1 mm; net 3.5 g ℮ 0.12 oz; shade "Wild Rose". Wraps: body and cap, each 64.8 × '
         '42 mm (the circumference plus a 2 mm overlap, by the visible height plus 1 mm bleed top and bottom), the seam '
         'at the back. The copy: the cap holds the logo and the stones; the body the Arabic hero شفاه large with أحمر '
         'small (أحمر شفاه = lipstick), the logotype "Enchanted Rose", "Lipstick" and "3.5 g ℮ 0.12 oz".')


def rectangles():
    """The two wraps' boxes on the sheet (x0, y0, x1, y1): the body above, the cap below, centred, even gaps."""
    gap = (SHEET_PX[1] - 2 * WRAP_H_PX) // 3
    x0 = (SHEET_PX[0] - WRAP_W_PX) // 2
    body = (x0, gap, x0 + WRAP_W_PX, gap + WRAP_H_PX)
    cap = (x0, 2 * gap + WRAP_H_PX, x0 + WRAP_W_PX, 2 * gap + 2 * WRAP_H_PX)
    return {'body': body, 'cap': cap}


def sheet():
    """The sheet the sketches are drawn on: white, the two wraps' trim lines (1 px grey), nothing else."""
    SKETCHES.mkdir(parents=True, exist_ok=True)
    img = Image.new('RGB', SHEET_PX, 'white')
    draw = ImageDraw.Draw(img)
    for box in rectangles().values():
        draw.rectangle([box[0] - 1, box[1] - 1, box[2], box[3]], outline=TRIM_GREY, width=1)
    path = SKETCHES / 'sheet.png'
    img.save(path)
    return path


COMMON = (
    "Image 1 is the sheet to draw on: a white ground with two empty rectangles outlined by thin grey trim lines, each "
    "900 px wide at the true proportion of a lipstick's wrap (64.8 × 42 mm, 1.543 : 1). Fill each rectangle EXACTLY to "
    "its trim lines with flat print artwork, edge to edge; keep the white ground white and draw nothing outside the "
    "rectangles; do not move, resize, tilt or round them. No product, no tube, no shadow, no ruler, no mockup, no "
    "labels. Image 2 is the closed lid of the same collection — the house's chosen design and the style reference: the "
    "deep indigo ground, the floated-stone marbling (battal, ebru: rose, coral, lilac, violet and teal stones with thin "
    "copper veins and crisp drag edges) and the Arabic name in engraved rose gold (a fine diagonal hatch inside a "
    "bevelled rose-gold rim). Image 3 is the BBROSE logo.\n\n"
    "THE TOP RECTANGLE is the BODY wrap of a round lipstick (Ø 20 mm). It wraps once round the tube and closes at the "
    "back: its left and right edges meet at the seam, so BOTH EDGES FALL IN PLAIN FLAT INDIGO and everything that "
    "matters sits in its middle third (the front). Nothing essential within 2 mm (28 px) of its top and bottom edges. On "
    "it: the hero Arabic word شفاه, large, in the lid's engraved rose gold, with أحمر small above or beside it (أحمر "
    "شفاه = lipstick), lettered in the lid's manner; \"Enchanted Rose\" in the lid's own rose-gold script, either running "
    "vertically along the body or small inside the front third; \"Lipstick\" and \"3.5 g ℮ 0.12 oz\" in small clean "
    "cream capitals in the front third. The stones: %s.\n\n"
    "THE BOTTOM RECTANGLE is the CAP wrap, the same size: only the stones and the BBROSE logo (exactly as image 3, "
    "small, in rose gold, centred in the front third); both edges plain indigo; no other words. The stones: %s.\n\n"
    "No petals, flowers, roses, arches or frames; no 3D, no perspective; flat artwork only.")

STONES = (
    ('a band of floated stones sweeping diagonally behind the front third, thinning to plain indigo at both edges',
     'a matching diagonal drift of small stones behind the logo'),
    ('a band of floated stones along the bottom of the body like the lid\'s lower drift, the hero on calm indigo above it',
     'a band of stones along the top of the cap'),
    ('a narrow river of small stones running across above the hero, a few stones drifting below it',
     'a small cluster of stones round the logo, open indigo toward both edges'),
    ('two drifts of stones entering the front third from its upper left and lower right, as the lid\'s two drifts, the '
     'hero between them on open indigo', 'one drift crossing behind the logo'),
    ('large floated stones gathered in the lower half of the front third, the hero standing above them, small scattered '
     'stones toward the edges', 'an arc of small stones above the logo'),
    ('sparse floated stones scattered lightly, the hero very large and dominant',
     'a dense cluster of stones in the front third with the logo beneath it'),
)


def prompt(n):
    body, cap = STONES[n - 1]
    return COMMON % (body, cap)


RETRY_LEAD = (
    "Image 1's two rectangles are TRANSPARENT: they are the only places to draw, and each must be filled exactly, edge to "
    "edge, at its own size and proportion; the white around them stays white. ")
RETRY_SEAM = (
    "\n\nTHE SEAM (the most important physical rule): on BOTH wraps, the outer sixth at the left and the outer sixth at "
    "the right are PLAIN FLAT INDIGO — no stone, vein or letter reaches either side edge, because the two side edges "
    "meet at the back.")


def retry_prompt(n):
    """The retry's prompt: the first round's, led by the transparent rectangles and closed by the seam rule."""
    return RETRY_LEAD + prompt(n) + RETRY_SEAM


def sheet_transparent():
    """The retry's sheet: white, the two wraps' rectangles transparent (what gpt-image-2 edits is the input's
    transparent part — the sides' lesson), and the mask the same."""
    SKETCHES.mkdir(parents=True, exist_ok=True)
    img = Image.new('RGBA', SHEET_PX, (255, 255, 255, 255))
    for box in rectangles().values():
        img.paste(Image.new('RGBA', (box[2] - box[0], box[3] - box[1]), (0, 0, 0, 0)), (box[0], box[1]))
    path = SKETCHES / 'sheet-transparent.png'
    img.save(path)
    return path


def sketch_retry(n, *, client):
    """A disqualified sketch made once more on the transparent sheet (the same as its mask); then cropped at its trim."""
    dest = SKETCHES / ('S%d-retry' % n)
    logo_path, _ = image_guard.APPROVED_LOGO
    sheet_png = sheet_transparent()
    items = [{'role': 'the sheet: the two wraps\' rectangles, transparent', 'path': str(sheet_png)},
             {'role': 'the Ẓilāl lid master — the style reference', 'path': str(zo.LID_FLAT)},
             {'role': 'the approved BBROSE logo', 'path': str(logo_path)}]
    rec = zo._guarded_edit('lipstick sketch S%d retry' % n, dest, items, retry_prompt(n), client=client, mask=sheet_png,
                           operation_suffix='lipstick/S%d-retry' % n, size=SHEET_SIZE)
    rec['crop'] = crop_wraps(dest)
    return rec


def candidate(n):
    """Sketch n as it stands for the ranking: its first round if that qualifies, else its retry if made and qualifying,
    else None; with the folder and both rounds' records."""
    first = SKETCHES / ('S%d' % n)
    crop = json.loads((first / 'crop.json').read_text(encoding='utf-8'))
    if crop['qualifies']:
        return first, {'first': crop}
    retry = SKETCHES / ('S%d-retry' % n)
    rows = {'first': crop}
    if (retry / 'crop.json').exists():
        rows['retry'] = json.loads((retry / 'crop.json').read_text(encoding='utf-8'))
        if rows['retry']['qualifies']:
            return retry, rows
    return None, rows


def sketch(n, *, client):
    """Sketch n (1–6): the sheet, the lid master (style reference) and the logo; then cropped at its trim lines."""
    dest = SKETCHES / ('S%d' % n)
    logo_path, _ = image_guard.APPROVED_LOGO
    items = [{'role': 'the sheet: the two wraps\' trim-lined rectangles', 'path': str(sheet())},
             {'role': 'the Ẓilāl lid master — the style reference', 'path': str(zo.LID_FLAT)},
             {'role': 'the approved BBROSE logo', 'path': str(logo_path)}]
    rec = zo._guarded_edit('lipstick sketch S%d' % n, dest, items, prompt(n), client=client,
                           operation_suffix='lipstick/S%d' % n, size=SHEET_SIZE)
    rec['crop'] = crop_wraps(dest)
    return rec


def wrap_box(picture, box):
    """A wrap's drawn box near where the sheet put it: the non-white region (min channel < 200, closed 5 px) whose
    bounding box overlaps the sheet's box most; its own bounding box."""
    near = picture.min(axis=2) < 200
    near = cv2.morphologyEx(near.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(near, connectivity=8)
    best, best_overlap = None, 0
    for i in range(1, count):
        left, top, w, h, _ = stats[i]
        ox = max(0, min(left + w, box[2]) - max(left, box[0]))
        oy = max(0, min(top + h, box[3]) - max(top, box[1]))
        if ox * oy > best_overlap:
            best, best_overlap = (int(left), int(top), int(left + w), int(top + h)), ox * oy
    return best


def crop_wraps(dest):
    """Each wrap cropped at its trim lines (its drawn box, 2 px inside to drop the line), never stretched; its aspect
    against 1.543 and whether the sketch qualifies (both within 2 %)."""
    picture = np.asarray(Image.open(dest / 'picture.png').convert('RGB'))
    rows = {}
    for name, box in rectangles().items():
        found = wrap_box(picture, box)
        if found is None:
            rows[name] = {'found': False, 'qualifies': False}
            continue
        x0, y0, x1, y1 = found[0] + 2, found[1] + 2, found[2] - 2, found[3] - 2
        crop = picture[y0:y1, x0:x1]
        Image.fromarray(crop).save(dest / ('%s.png' % name))
        aspect = (x1 - x0) / (y1 - y0)
        error = abs(aspect - ASPECT) / ASPECT
        rows[name] = {'found': True, 'box_px': [x0, y0, x1, y1], 'sheet_box_px': list(box), 'aspect': round(aspect, 4),
                      'aspect_error': round(error, 4), 'qualifies': bool(error <= ASPECT_ERROR_MAX),
                      'file': lm.rel(dest / ('%s.png' % name))}
    record = {'wraps': rows, 'qualifies': all(r['qualifies'] for r in rows.values()),
              'rule': 'D-D11-7: cropped at the trim lines; an aspect error over 2 % disqualifies; nothing stretched'}
    lm.write_json(dest / 'crop.json', record)
    return record


def beside_the_lid(dest):
    """The lid (left) and a sketch's two wraps stacked as cropped (right, body above cap), at the lid's height."""
    lid = Image.open(zo.LID_FLAT).convert('RGB')
    h = 970
    lid = lid.resize((int(lid.width * h / lid.height), h), Image.LANCZOS)
    body = Image.open(dest / 'body.png').convert('RGB')
    cap = Image.open(dest / 'cap.png').convert('RGB')
    each = (h - 24) // 2
    body = body.resize((int(body.width * each / body.height), each), Image.LANCZOS)
    cap = cap.resize((int(cap.width * each / cap.height), each), Image.LANCZOS)
    right = max(body.width, cap.width)
    pair = Image.new('RGB', (lid.width + 24 + right, h), 'white')
    pair.paste(lid, (0, 0))
    pair.paste(body, (lid.width + 24, 0))
    pair.paste(cap, (lid.width + 24, each + 24))
    path = SKETCHES / ('%s-beside-the-lid.png' % dest.name)
    pair.save(path)
    return path


def rank(*, client, name=None):
    """J1 ranks the qualified sketches, each beside the lid, with the anchors (rubric v2); a disqualified sketch is not
    shown and is recorded. ``name``: the record's name (ranking when None; a jury record is never overwritten, so the
    ranking after the retry is its own record)."""
    from apps.pipeline.services import jury
    if name is None:
        name = 'ranking'
    qualified, dropped = [], []
    for n in range(1, COUNT + 1):
        folder, rows = candidate(n)
        if folder is None:
            dropped.append({'sketch': n, 'crops': rows})
        else:
            qualified.append((n, folder))
    pairs = [beside_the_lid(folder) for _, folder in qualified]
    checks = ['body aspect %.3f, cap aspect %.3f (true 1.543)' % tuple(
        json.loads((folder / 'crop.json').read_text(encoding='utf-8'))['wraps'][w]['aspect'] for w in ('body', 'cap'))
        for _, folder in qualified]
    direction = json.loads((zm.REPO / 'docs' / 'audit' / 'day-9' / 'directions' / 'B-1.json').read_text(encoding='utf-8'))
    spec = ('THE ROUND (Day 11, D-D11-7). Each image shows THE LID MASTER on the left (the collection\'s chosen design, '
            'for reference — not ranked) and ONE SKETCH on the right: the lipstick\'s body wrap above its cap wrap, each '
            'flat, 64.8 × 42 mm, closing at a seam at the back (both side edges meet there, so they must be plain '
            'indigo and the hero must sit in the middle third, the front). Rank the sketches: which carries the lid\'s '
            'language (%s) onto a lipstick best, and which is the best to build? A sketch that breaks the language, '
            'puts the hero or a stone across the seam, crowds the top or bottom 2 mm, or draws petals or frames ranks '
            'lower.' % zo.IDEA)
    record = jury.rank_sketches_v2(pairs, anchors=zm.anchors(), facts=FACTS + '\n' + zm.BAR, spec=spec,
                                   direction_idea='B-1: ' + direction['idea'], operation=zm.RANK_PREFIX + 'lipstick',
                                   destination=SKETCHES / ('%s.json' % name), rubric_version='v2', effort='medium',
                                   reservation_prefix=zm.RANK_PREFIX, reservation_cap=zm.RANK_CAP_USD, checks=checks,
                                   client=client)
    shown = {'shown_as': {str(i + 1): {'sketch': n, 'folder': lm.rel(folder)} for i, (n, folder) in enumerate(qualified)},
             'disqualified': dropped}
    lm.write_json(SKETCHES / ('%s-map.json' % name), shown)
    record['map'] = shown
    return record
