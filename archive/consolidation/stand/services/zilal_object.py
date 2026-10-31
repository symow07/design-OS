"""Day 11 §2 — Ẓilāl's object (D-D11-4): the idea on every surface — the 18 shades are floated stones on indigo; the
Arabic leads in engraved rose gold.

The paid pictures: the lid's sides by ONE masked edit continuing the lid's marbling over its edges (the lid face stays
the preserved master); the inside of the lid and the tray by a sketch round of three each (gpt-image-2 high, the lid
master as the style reference, the logo the only other input), J1 ranking each three beside the lid. Every call goes
through the image guard and the ledger, and resumes: a picture already made is read back, never bought twice.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from contextlib import ExitStack
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from apps.pipeline.services import image_guard
from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import zilal_master as zm

OBJ = zm.DAY11 / 'zilal'
LID_FLAT = zm.OUT / 'lid-master-flat.png'          # the lid master as it prints (300 PPI): the style reference
IMAGE_PREFIX = zm.IMAGE_PREFIX
IMAGE_CAP_USD = zm.IMAGE_CAP_USD
SIZE = '1536x1024'
QUALITY = 'high'
BAND_PX = zm.BAND_PX
SIDE_MM = 12.0                                     # the brief's "190 × 120 × 12 mm closed" (⟪PROVISIONAL⟫)

IDEA = ('the 18 shades are floated stones on indigo; the Arabic leads in engraved rose gold')
FORMAT = ("FORMAT. Flat print artwork, seen exactly front-on and filling the frame edge to edge: the {what}, 190 × 120 mm. "
          "The artwork is the 1536 × 970 area between a 27 px band at the top and one at the bottom of the 1536 × 1024 "
          "frame; the bands continue the ground and hold nothing. Image 1 is the closed lid of the same palette — the "
          "house's chosen design and the style reference: the same floated-stone marbling (battal, ebru: colour floated "
          "on deep indigo and lifted onto paper, thin veins, crisp drag edges), the same indigo, the same colours. Image 2 "
          "is the BBROSE logo, for reference only — do not draw it.")
NEVER = ("No petals, flowers, roses, arches or frames; no 3D, no perspective, no shadow of a product, no props, no hands, no "
         "mockup; flat artwork only.")

INSIDE_PROMPTS = tuple(
    FORMAT.format(what='inside of the palette\'s lid') + "\n\nTHE INSIDE OF THE LID. The brief's \"soft lilac\" is the "
    "colour key: lilac floated stones drifting on a paler lilac ground — the lid's marbling made quiet, light and soft, "
    "%s. No words, no letters, no logo, no gold lettering. " % drift + NEVER
    for drift in ('a few large lilac stones drifting across the middle, the edges open and pale',
                  'a sparse drift of lilac stones from one corner, thinning to scattered small stones and fine veins',
                  'small lilac stones in a loose diagonal current with thin pale veins between them'))

TRAY_COLOUR_STORY = ("Row 1, left to right — roses: Petal Frost (pale petal pink, shimmer), Moonlit Rose (soft rose pink, "
                     "shimmer), Fairy Dust (pale peach-rose, shimmer), Rosewater (dusty rose, matte), Wild Rose (deep rose "
                     "pink, matte), Velvet Bloom (deep berry rose, matte). Row 2 — lilacs and violets: Lilac Mist (pale "
                     "lilac, shimmer), Gilded Petal (rose gold, shimmer), Spellbound (violet, shimmer), Enchanted (soft "
                     "orchid lilac, shimmer), Twilight (grey violet, matte), Briar (deep plum violet, matte). Row 3 — "
                     "teals: Dusk Garden (dusty teal, shimmer), Mystic (pale aqua teal, shimmer), Thorn (deep teal, matte), "
                     "Nightshade (teal ink, matte), Eternal (bright sea teal, shimmer), Midnight Bloom (deep midnight teal, "
                     "shimmer) — row 3 reads clearly TEAL, at least three pans plainly teal.")
TRAY_PROMPTS = tuple(
    FORMAT.format(what='open tray of the palette, seen from directly above') + "\n\nTHE TRAY. Its 18 pans sit as the "
    "stones: 18 square pans of pressed eyeshadow, all one size, in 3 rows of 6 in a neat even grid, set into the "
    "floated-stone marbling on deep indigo — %s. Each pan one flat shade showing its finish as named (matte: flat powder; "
    "shimmer: a soft sheen toward one corner; glitter: fine dense sparkle). %s Each shade's name printed under its own "
    "pan in clean small cream capitals, exactly as written. No logo, no other words. " % (ground, TRAY_COLOUR_STORY) + NEVER
    for ground in ('the marbling a quiet floated-stone ground around the grid, its stones smaller than the pans',
                   'the marbling flowing between the pans like the lid\'s veins, the pans its largest stones',
                   'a calm deep indigo field around the grid with floated stones drifting at its edges'))


def _guarded_edit(name, dest, items, prompt, *, client, mask=None, operation_suffix, size=None):
    """One gpt-image-2 high edit through the guard and the ledger; the paid picture saved as ``dest/picture.png``.
    ``size``: the picture's size (SIZE, landscape, when None)."""
    from django.conf import settings
    from apps.pipeline.services.spend_reservation import paid_operation
    if size is None:
        size = SIZE
    done = dest / 'result.json'
    if done.exists():
        return json.loads(done.read_text(encoding='utf-8'))
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'request.json').write_text(json.dumps({'model': settings.IMAGE_MODEL, 'quality': QUALITY, 'size': size,
                                                   'inputs': items, 'mask': None if mask is None else str(mask),
                                                   'prompt': prompt}, ensure_ascii=False, indent=1) + '\n')
    operation = IMAGE_PREFIX + operation_suffix

    def invoke(checked):
        api = client
        if api is None:
            from openai import OpenAI
            api = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0, timeout=400)
        with ExitStack() as stack:
            files = [stack.enter_context(open(i['path'], 'rb')) for i in checked]
            extra = {}
            if mask is not None:
                extra['mask'] = stack.enter_context(open(mask, 'rb'))
            response = paid_operation(api.images.edit, provider='openai', operation=operation,
                                      reservation_prefix=IMAGE_PREFIX, reservation_cap=IMAGE_CAP_USD,
                                      model=settings.IMAGE_MODEL, image=files, prompt=prompt, n=1, size=size,
                                      quality=QUALITY, **extra)
        saved = response._rescue_paid_images
        if len(saved) != 1:
            raise RuntimeError('the paid response is kept, but exactly one picture was not recovered')
        shutil.copyfile(saved[0], dest / 'picture.png')
        return {'reservation_id': response._rescue_reservation_id, 'usage': response.model_dump(mode='json')['usage'],
                'output_sha256': hashlib.sha256((dest / 'picture.png').read_bytes()).hexdigest()}

    result = image_guard.guarded_call(invoke, operation=operation, inputs=items, prompt=prompt, quality=QUALITY,
                                      size=size, picture=name)
    record = dict(result, picture=lm.rel(dest / 'picture.png'), prompt=prompt)
    done.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
    return record


def lid_middle(picture_png, out_png):
    """A 1536 × 1024 picture's 1536 × 970 middle (the artwork between its 27 px bands)."""
    full = np.asarray(Image.open(picture_png).convert('RGB'))
    if full.shape[:2] != (970 + 2 * BAND_PX, 1536):
        raise ValueError('%s is %d × %d, not 1536 × 1024' % (picture_png, full.shape[1], full.shape[0]))
    Image.fromarray(full[BAND_PX:-BAND_PX]).save(out_png)
    return out_png


def surface_sketch(kind, n, *, client):
    """A sketch of the inside of the lid ('inside') or the tray ('tray'), n 1–3: the lid master the style reference, the
    logo the only other input."""
    prompts = {'inside': INSIDE_PROMPTS, 'tray': TRAY_PROMPTS}[kind]
    dest = OBJ / {'inside': 'inside-lid', 'tray': 'tray'}[kind] / 'sketches' / ('S%d' % n)
    logo_path, _ = image_guard.APPROVED_LOGO
    items = [{'role': 'the Ẓilāl lid master — the style reference', 'path': str(LID_FLAT)},
             {'role': 'the approved BBROSE logo', 'path': str(logo_path)}]
    rec = _guarded_edit('zilal %s sketch S%d' % (kind, n), dest, items, prompts[n - 1], client=client,
                        operation_suffix='zilal/%s/S%d' % (kind, n))
    if not (dest / 'lid.png').exists():
        lid_middle(dest / 'picture.png', dest / 'lid.png')
    return rec


# --- the sides: one masked edit ----------------------------------------------------------------------------------------

SIDES = OBJ / 'sides'
SIDES_PROMPT = ("EDIT image 1. It is the closed lid of a prestige eyeshadow palette (the opaque middle: keep it exactly as "
                "it is) inside a transparent border. Fill ONLY the transparent border, all round, by continuing the lid's "
                "own floated-stone marbling and deep indigo ground outward past its edges, as if the same marbled paper "
                "wrapped over the lid's four 12 mm sides: the stones, veins and drag lines that reach an edge carry on "
                "across it; where the lid's edge is plain indigo, the border is plain indigo with at most a few small "
                "stones. Nothing new in the border: no letters, words, logo, gold lettering, frame, rule, shadow or "
                "border line; no 3D, no perspective. The marbling only.")


def sides_canvas():
    """The edit's input: the lid master (its 300 PPI flat brought to the canvas's scale) centred in a 1536 × 1024 canvas
    with a transparent border 12 mm wide all round (the lid's sides), and the mask (transparent where the edit may
    paint). Returns the paths and the geometry (px per mm, the lid's box on the canvas)."""
    w_mm, h_mm = zm.LID_MM[0] + 2 * SIDE_MM, zm.LID_MM[1] + 2 * SIDE_MM
    k = min(1536 / w_mm, 1024 / h_mm)
    lid_w, lid_h = int(round(zm.LID_MM[0] * k)), int(round(zm.LID_MM[1] * k))
    x0, y0 = (1536 - lid_w) // 2, (1024 - lid_h) // 2
    flat = Image.open(LID_FLAT).convert('RGB').resize((lid_w, lid_h), Image.LANCZOS)
    canvas = Image.new('RGBA', (1536, 1024), (0, 0, 0, 0))
    canvas.paste(flat.convert('RGBA'), (x0, y0))
    SIDES.mkdir(parents=True, exist_ok=True)
    canvas.save(SIDES / 'canvas.png')
    mask = Image.new('RGBA', (1536, 1024), (0, 0, 0, 0))
    mask.paste(Image.new('RGBA', (lid_w, lid_h), (0, 0, 0, 255)), (x0, y0))
    mask.save(SIDES / 'mask.png')
    return {'canvas': SIDES / 'canvas.png', 'mask': SIDES / 'mask.png', 'px_per_mm': k,
            'lid_box_px': [x0, y0, x0 + lid_w, y0 + lid_h]}


def sides_edit(*, client):
    """D-D11-4's sides: ONE masked edit continuing the lid's marbling over its edges (the canvas and its mask the only
    inputs)."""
    geom = sides_canvas()
    items = [{'role': 'the Ẓilāl lid master in a transparent 12 mm border (the edit\'s input)', 'path': str(geom['canvas'])}]
    rec = _guarded_edit('zilal sides', SIDES / 'edit', items, SIDES_PROMPT, client=client, mask=geom['mask'],
                        operation_suffix='zilal/sides')
    rec['geometry'] = dict(geom, canvas=lm.rel(geom['canvas']), mask=lm.rel(geom['mask']), px_per_mm=round(geom['px_per_mm'], 4))
    return rec


# --- J1 ranks each surface's three beside the lid ------------------------------------------------------------------------

def beside_the_lid(lid_png, sketch_png, out_png):
    """The lid (left) and a surface's sketch (right) side by side at one height, a white gap between: what J1 ranks."""
    a = Image.open(lid_png).convert('RGB')
    b = Image.open(sketch_png).convert('RGB')
    h = 970
    a = a.resize((int(a.width * h / a.height), h), Image.LANCZOS)
    b = b.resize((int(b.width * h / b.height), h), Image.LANCZOS)
    pair = Image.new('RGB', (a.width + 24 + b.width, h), 'white')
    pair.paste(a, (0, 0))
    pair.paste(b, (a.width + 24, 0))
    pair.save(out_png)
    return out_png


def rank_surface(kind, *, client, checks=None):
    """J1 ranks a surface's three sketches, each shown beside the lid master, with the fixed anchors (rubric v2)."""
    from apps.pipeline.services import jury
    folder = OBJ / {'inside': 'inside-lid', 'tray': 'tray'}[kind] / 'sketches'
    pairs = [beside_the_lid(LID_FLAT, folder / ('S%d' % n) / 'lid.png', folder / ('S%d-beside-the-lid.png' % n))
             for n in (1, 2, 3)]
    direction = json.loads((zm.REPO / 'docs' / 'audit' / 'day-9' / 'directions' / 'B-1.json').read_text(encoding='utf-8'))
    what = {'inside': 'the inside of the lid (the brief: "inside the lid, a soft lilac" — lilac stones drifting on a paler '
                      'ground, no petals, no words)',
            'tray': 'the open tray (18 square pans in 3 rows of 6 as the stones, each shade named under its pan; row 3 '
                    'must carry at least three plainly teal pans — the brief\'s palette is rose, lilac and teal)'}[kind]
    spec = ('THE ROUND (Day 11, D-D11-4). Each image shows THE LID MASTER on the left (the owner\'s pick, for reference — not '
            'ranked) and ONE SKETCH of %s on the right. Rank the three sketches: which belongs to the lid\'s language '
            '(%s) and is the best %s to build? A sketch that breaks the language, draws petals or words where none are '
            'asked, or (for the tray) misses the teal row ranks lower.' % (what, IDEA, kind))
    return jury.rank_sketches_v2(pairs, anchors=zm.anchors(), facts=direction['facts'] + '\n' + zm.BAR, spec=spec,
                                 direction_idea='B-1: ' + direction['idea'], operation=zm.RANK_PREFIX + 'zilal-%s' % kind,
                                 destination=folder / 'ranking.json', rubric_version='v2', effort='medium',
                                 reservation_prefix=zm.RANK_PREFIX, reservation_cap=zm.RANK_CAP_USD, checks=checks,
                                 client=client)


# --- the sides built: the four bands, the continuity across each fold ----------------------------------------------------

STRIP_MM = 1.0                      # D-D11-4: continuity across each fold read over a 1 mm strip either side
ALONG_SIGMA_MM = 0.5                # each side's strip read as its local colour along the edge (σ 0.5 mm)
CONTINUITY_MEAN_MAX = 3.0
CONTINUITY_MAX = 8.0
BAND_UP = 2                         # the bands brought to print resolution: Lanczos 2× (14.2 px/mm, 361 PPI)
PRINT_PX_PER_MM = 2245 / 190.0      # the lid master's flat (300 PPI): the unfolded print flat is made at its scale
REGISTRATION_MIN_RESPONSE = 0.3     # a phase-correlation peak below this is no lock: the edit is not moved


def lid_at_canvas(geom):
    """The master's flat brought to the canvas's scale (the lid's box on the edit's canvas)."""
    x0, y0, x1, y1 = geom['lid_box_px']
    return np.asarray(Image.open(LID_FLAT).convert('RGB').resize((x1 - x0, y1 - y0), Image.LANCZOS))


def register_edit(edit, geom):
    """The edit's lid area registered on the master: the offset read by phase correlation (the master's flat at the
    canvas's scale against the edit's lid area, grey, Hann window), the whole edit moved back by it (Lanczos,
    sub-pixel) and the offset read again. A peak below REGISTRATION_MIN_RESPONSE is no lock (the edit's lid area is
    not the master's): the edit is left where it is and the record says so. Returns the edit and the record."""
    x0, y0, x1, y1 = geom['lid_box_px']
    master = cv2.cvtColor(lid_at_canvas(geom).astype(np.float32), cv2.COLOR_RGB2GRAY)
    window = cv2.createHanningWindow((x1 - x0, y1 - y0), cv2.CV_32F)

    def offset(img):
        grey = cv2.cvtColor(img[y0:y1, x0:x1].astype(np.float32), cv2.COLOR_RGB2GRAY)
        (dx, dy), response = cv2.phaseCorrelate(master, grey, window)
        return dx, dy, response
    dx, dy, response = offset(edit)
    if response < REGISTRATION_MIN_RESPONSE:
        return edit, {'method': 'phase correlation of the edit\'s lid area on the master\'s flat at the canvas\'s '
                                'scale', 'locked': False, 'offset_px': [round(dx, 3), round(dy, 3)],
                      'response': round(response, 3), 'min_response': REGISTRATION_MIN_RESPONSE,
                      'moved': 'no: below the lock threshold the edit\'s lid area does not hold the master'}
    moved = cv2.warpAffine(edit, np.float32([[1, 0, -dx], [0, 1, -dy]]), (edit.shape[1], edit.shape[0]),
                           flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)
    after = offset(moved)
    return moved, {'method': 'phase correlation of the edit\'s lid area on the master\'s flat at the canvas\'s scale; '
                             'the edit moved back by the offset (Lanczos)', 'locked': True,
                   'offset_px': [round(dx, 3), round(dy, 3)], 'response': round(response, 3),
                   'min_response': REGISTRATION_MIN_RESPONSE,
                   'after_px': [round(after[0], 3), round(after[1], 3)]}


def bands_of(canvas, geom):
    """The four 12 mm bands cropped from a canvas against the lid's box."""
    x0, y0, x1, y1 = geom['lid_box_px']
    band = int(round(SIDE_MM * geom['px_per_mm']))
    return {'top': canvas[y0 - band:y0, x0:x1], 'bottom': canvas[y1:y1 + band, x0:x1],
            'left': canvas[y0:y1, x0 - band:x0], 'right': canvas[y0:y1, x1:x1 + band]}


def fold_continuity(bands, lid, k):
    """D-D11-4's continuity across each fold: the band's 1 mm strip next to the lid against the MASTER's own 1 mm strip
    inside the lid's edge, each averaged across its width and read as its colour along the edge (σ 0.5 mm), ΔE00 at
    every position along the fold: mean ≤ 3 and max ≤ 8."""
    from scipy.ndimage import gaussian_filter1d
    strip = max(int(round(STRIP_MM * k)), 1)
    pairs = {'top': (bands['top'][-strip:], lid[:strip], 0), 'bottom': (bands['bottom'][:strip], lid[-strip:], 0),
             'left': (bands['left'][:, -strip:], lid[:, :strip], 1), 'right': (bands['right'][:, :strip], lid[:, -strip:], 1)}
    sigma = ALONG_SIGMA_MM * k
    rows = {}
    for side, (b, m, axis) in pairs.items():
        bm = gaussian_filter1d(b.astype(np.float64).mean(axis=axis), sigma, axis=0)
        mm_ = gaussian_filter1d(m.astype(np.float64).mean(axis=axis), sigma, axis=0)
        de = lm.delta_e00(lm.srgb_to_lab(np.clip(np.round(bm), 0, 255).astype(np.uint8)[None]),
                          lm.srgb_to_lab(np.clip(np.round(mm_), 0, 255).astype(np.uint8)[None]))[0]
        rows[side] = {'positions': int(len(de)), 'de00_mean': round(float(de.mean()), 3),
                      'de00_max': round(float(de.max()), 3),
                      'worst_at_mm': round(float(np.argmax(de)) / k, 1),
                      'holds': bool(de.mean() <= CONTINUITY_MEAN_MAX and de.max() <= CONTINUITY_MAX)}
    return rows


def unfolded_print(bands):
    """The lid with its four sides unfolded, at the master's own 300 PPI: the master's flat untouched in the middle,
    each band brought to its 12 mm by Lanczos; the corners (cut away on the case) white."""
    lid = np.asarray(Image.open(LID_FLAT).convert('RGB'))
    h, w = lid.shape[:2]
    band = int(round(SIDE_MM * PRINT_PX_PER_MM))

    def fit(a, size):
        return np.asarray(Image.fromarray(a).resize(size, Image.LANCZOS))
    flat = np.full((h + 2 * band, w + 2 * band, 3), 255, dtype=np.uint8)
    flat[band:-band, band:-band] = lid
    flat[:band, band:-band] = fit(bands['top'], (w, band))
    flat[-band:, band:-band] = fit(bands['bottom'], (w, band))
    flat[band:-band, :band] = fit(bands['left'], (band, h))
    flat[band:-band, -band:] = fit(bands['right'], (band, h))
    return flat, band


def sides_build(edit_record, out):
    """D-D11-4's sides: the edit registered on the master (``register_edit``), the four 12 mm bands cropped from it
    (top and bottom 190 × 12 mm, left and right 12 × 120 mm) and brought to print resolution (Lanczos 2×); the
    continuity across each fold (``fold_continuity``); the lid face is the master, untouched (its files' hashes read
    before and after). Writes the bands, the unfolded flat at the canvas's scale and at the master's 300 PPI, and
    continuity.json, in ``out``."""
    geom = edit_record['geometry']
    k = geom['px_per_mm']
    raw = np.asarray(Image.open(zm.REPO / edit_record['picture']).convert('RGB'))
    master_before = {p.name: lm.sha256(p) for p in sorted(zm.OUT.glob('lid-master*')) if p.is_file()}
    edit, registration = register_edit(raw, geom)
    lid = lid_at_canvas(geom)
    bands = bands_of(edit, geom)
    rows = fold_continuity(bands, lid, k)
    unregistered = fold_continuity(bands_of(raw, geom), lid, k)
    x0, y0, x1, y1 = geom['lid_box_px']
    kept = lm.delta_e00(lm.srgb_to_lab(edit[y0:y1, x0:x1]), lm.srgb_to_lab(lid))
    out.mkdir(parents=True, exist_ok=True)
    made = {}
    for side, b in bands.items():
        up = cv2.resize(b, (b.shape[1] * BAND_UP, b.shape[0] * BAND_UP), interpolation=cv2.INTER_LANCZOS4)
        path = out / ('band-%s.png' % side)
        Image.fromarray(up).save(path, dpi=(25.4 * k * BAND_UP,) * 2)
        made[side] = {'file': lm.rel(path), 'px': [int(up.shape[1]), int(up.shape[0])],
                      'mm': [round(up.shape[1] / (k * BAND_UP), 2), round(up.shape[0] / (k * BAND_UP), 2)]}
    band = int(round(SIDE_MM * k))
    unfolded = np.full((y1 - y0 + 2 * band, x1 - x0 + 2 * band, 3), 255, dtype=np.uint8)
    unfolded[band:-band, band:-band] = lid
    unfolded[:band, band:-band] = bands['top']
    unfolded[-band:, band:-band] = bands['bottom']
    unfolded[band:-band, :band] = bands['left']
    unfolded[band:-band, -band:] = bands['right']
    Image.fromarray(unfolded).save(out / 'sides-unfolded.png')
    flat, print_band = unfolded_print(bands)
    Image.fromarray(flat).save(out / 'sides-unfolded-print.png', dpi=(300, 300))
    master_after = {p.name: lm.sha256(p) for p in sorted(zm.OUT.glob('lid-master*')) if p.is_file()}
    record = {'schema': 'day11_zilal_sides/2', 'edit': {k_: edit_record[k_] for k_ in ('picture', 'reservation_id', 'output_sha256')},
              'geometry': geom, 'registration': registration, 'band_mm': SIDE_MM, 'bands': made,
              'edit_kept_the_lid': {'de00_mean': round(float(kept.mean()), 2),
                                    'de00_p95': round(float(np.percentile(kept, 95)), 2),
                                    'reads': 'the edit\'s own lid area against the master at the canvas\'s scale (the '
                                             'files use the master, never the edit\'s lid; this says what the edit '
                                             'kept beside its bands)'},
              'continuity': {'rule': 'D-D11-4: across each fold, mean ΔE00 ≤ 3 and max ≤ 8 over a 1 mm strip (each '
                                     'strip read as its colour along the edge, σ 0.5 mm; the band\'s strip against the '
                                     'master\'s own)', 'sides': rows, 'holds': all(r['holds'] for r in rows.values()),
                             'before_registration': unregistered},
              'lid_face_untouched': {'holds': master_before == master_after, 'files': master_after},
              'resolution': 'the edit at %.2f px/mm (%.0f PPI), the bands brought to %.0f PPI by Lanczos 2×; the '
                            'unfolded print flat at the master\'s 300 PPI (%d px bands)' % (
                                k, 25.4 * k, 25.4 * k * BAND_UP, print_band),
              'provisional': 'the sides\' 12 mm are the brief\'s "190 × 120 × 12 mm closed": ⟪PROVISIONAL⟫ until the case '
                             'is measured',
              'unfolded': lm.rel(out / 'sides-unfolded.png'), 'unfolded_print': lm.rel(out / 'sides-unfolded-print.png')}
    lm.write_json(out / 'continuity.json', record)
    return record


# --- the sides' repair: the border pre-filled by the master's own mirror, the same mask --------------------------------

SIDES_REPAIR_PROMPT = (
    "EDIT image 1. It is ONE continuous sheet of floated-stone marbled paper (battal, ebru) on deep indigo: the closed "
    "lid of a prestige eyeshadow palette in the middle (keep the middle exactly as it is) and, all round it, a 12 mm "
    "border that is the same sheet wrapping over the lid's four sides. The border now holds a mirror image of the lid's "
    "own edge, a guide only. Repaint ONLY the border as the real continuation of the sheet: every stone, vein and drag "
    "line that meets the lid's edge carries straight on across it, unbroken, in the edge's own colours and at the same "
    "place along the edge; where the lid's edge is plain indigo, the border stays plain indigo. It is one sheet: no edge, "
    "rim, frame, lift, bevel, card, shadow or line where the middle meets the border, and nothing new — no letters, "
    "words, logo, gold lettering or rule; no 3D, no perspective. The marbling only.")


def mirror_canvas(geom, out):
    """The repair's input: the master at the canvas's scale with the border filled by its own reflection at each edge
    (corners reflected on both axes), and the same mask as the first edit (the border editable, the lid kept)."""
    x0, y0, x1, y1 = geom['lid_box_px']
    lid = lid_at_canvas(geom)
    canvas = cv2.copyMakeBorder(lid, y0, 1024 - y1, x0, 1536 - x1, cv2.BORDER_REFLECT)
    out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(canvas).save(out / 'canvas.png')
    shutil.copyfile(SIDES / 'mask.png', out / 'mask.png')
    return {'canvas': out / 'canvas.png', 'mask': out / 'mask.png', 'array': canvas}


def sides_repair_edit(geom, *, client):
    """The sides' one repair: the masked edit again, its border pre-filled by the master's mirror so that the input
    holds no boundary to draw (the first edit drew the lid as a card with its own edge)."""
    out = SIDES / 'repair1'
    made = mirror_canvas(geom, out)
    items = [{'role': 'the Ẓilāl lid master with its border filled by its own mirror (the repair\'s input)',
              'path': str(made['canvas'])}]
    rec = _guarded_edit('zilal sides repair 1', out / 'edit', items, SIDES_REPAIR_PROMPT, client=client,
                        mask=made['mask'], operation_suffix='zilal/sides/repair1')
    rec['geometry'] = dict(geom)
    return rec


# --- every surface's eye gate (D-D11-4: the eye as the gate, repair ≤ 1) -------------------------------------------------

SURFACE_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['images', 'defects', 'holds_the_lids_language', 'summary'],
    'properties': {
        'images': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['image', 'verdict', 'notes'],
            'properties': {'image': {'type': 'integer'}, 'verdict': {'type': 'string', 'enum': ['holds', 'defect']},
                           'notes': {'type': 'string'}}}},
        'defects': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['where', 'what', 'severity', 'repair'],
            'properties': {'where': {'type': 'string'}, 'what': {'type': 'string'},
                           'severity': {'type': 'string', 'enum': ['blocking', 'major', 'minor']},
                           'repair': {'type': 'string'}}}},
        'holds_the_lids_language': {'type': 'boolean'},
        'summary': {'type': 'string'}}}


def fitted(src, path):
    """A picture fitted under the eye's limits (1568 px a side, 1.15 MP) by Lanczos, saved for the call."""
    img = Image.open(src).convert('RGB') if not isinstance(src, np.ndarray) else Image.fromarray(src)
    k = min(1.0, lm.EYE_IMAGE_EDGE_MAX / max(img.size), (lm.EYE_PIXELS_MAX / (img.size[0] * img.size[1])) ** 0.5)
    if k < 1.0:
        img = img.resize((int(img.size[0] * k), int(img.size[1] * k)), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


LANGUAGE = ('THE LID MASTER — the language every surface is judged in (D-D11-4: the eye is given the lid as the '
            'language); for reference, not judged')


def lid_language(out):
    """The lid master's flat, fitted, as the first picture of every surface's look (D-D11-4)."""
    return fitted(LID_FLAT, out / 'crops' / 'lid-language.png'), LANGUAGE


def surface_look(out, surface, images, text, call, round_no, label=None):
    """One eye round on a surface: the pictures (each made and size-checked before anything is paid) and the surface's
    rule; the round holds when the eye answered, no image is a defect and no defect is named. Written the moment it
    returns, as eye-r<round>.json (or eye-<label>.json for a re-look)."""
    if label is None:
        label = 'r%d' % round_no
    blocks = [lm._image_block(p) for p, _ in images]
    look = call('zilal/%s/%s' % (surface, label), [{'type': 'text', 'text': text}] + [b for b, _ in blocks],
                SURFACE_SCHEMA)
    look['sent'] = [dict(i, shows=words) for (_, i), (_, words) in zip(blocks, images)]
    p = look['payload']
    answered = p is not None
    defects = []
    image_defects = []
    if answered:
        defects = list(p['defects'])
        image_defects = [i for i in p['images'] if i['verdict'] == 'defect']
    record = {'schema': 'day11_zilal_surface_eye/1', 'surface': surface, 'round': round_no, 'label': label, 'look': look,
              'answered': answered, 'defects': defects, 'image_defects': image_defects,
              'holds': bool(answered and not defects and not image_defects),
              'decided': 'in code: the round holds when the eye answered, no image is a defect and no defect is named'}
    lm.write_json(out / ('eye-%s.json' % label), record)
    return record


FOLD_ACROSS_MM = 24.0               # a fold crop: the 12 mm band and 12 mm of the lid beside it
FOLD_ALONG_MM = 50.0
FOLD_PLACES = {'top': (1 / 6, 1 / 2, 5 / 6), 'bottom': (1 / 6, 1 / 2, 5 / 6), 'left': (1 / 4, 3 / 4),
               'right': (1 / 4, 3 / 4)}


def fold_crops(flat, band, out):
    """Crops at print size (300 PPI) across each fold of the unfolded print flat: 12 mm of band and 12 mm of lid, 50 mm
    along the fold, three along each long side and two along each short side."""
    k = PRINT_PX_PER_MM
    h, w = flat.shape[:2]
    lid_w, lid_h = w - 2 * band, h - 2 * band
    across = int(round(FOLD_ACROSS_MM * k))
    along = int(round(FOLD_ALONG_MM * k))
    made = []
    for side, places in FOLD_PLACES.items():
        for n, f in enumerate(places, 1):
            if side in ('top', 'bottom'):
                cx = band + int(round(f * lid_w))
                xa = min(max(cx - along // 2, band), band + lid_w - along)
                ya = 0
                if side == 'bottom':
                    ya = h - across
                crop = flat[ya:ya + across, xa:xa + along]
            else:
                cy = band + int(round(f * lid_h))
                ya = min(max(cy - along // 2, band), band + lid_h - along)
                xa = 0
                if side == 'right':
                    xa = w - across
                crop = flat[ya:ya + along, xa:xa + across]
            path = out / 'crops' / ('fold-%s-%d.png' % (side, n))
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(crop).save(path, dpi=(300, 300))
            made.append((path, 'the %s fold, crop %d of %d (print size, 300 PPI): the band (%s) and the lid beside it'
                         % (side, n, len(places), {'top': 'above', 'bottom': 'below', 'left': 'left',
                                                   'right': 'right'}[side])))
    return made


def sides_look(build_record, out, call, round_no):
    """The sides' eye round: the unfolded flat (fitted) and the fold crops at print size, with the rule and the
    measured continuity."""
    flat = np.asarray(Image.open(zm.REPO / build_record['unfolded_print']).convert('RGB'))
    band = int(round(SIDE_MM * PRINT_PX_PER_MM))
    images = [(fitted(flat, out / 'crops' / 'unfolded-fitted.png'),
               'the lid with its four 12 mm sides unfolded flat (the corners, white, are cut away on the case)')]
    images += fold_crops(flat, band, out)
    cont = build_record['continuity']['sides']
    text = ('THE SIDES GATE (Day 11, D-D11-4). The palette\'s lid is 190 × 120 mm with four 12 mm sides. The lid face is '
            'THE LID MASTER, finished and preserved (its files untouched, proven by their hashes); the four sides were '
            'made by one masked image edit continuing the lid\'s marbling over its edges. Image 1 is the lid with its '
            'sides unfolded flat; images 2–%d are crops at print size across each fold (the fold is where a band meets '
            'the lid): %s.\n\nTHE RULE (the owner\'s): the sides continue the lid\'s floated-stone marbling on deep '
            'indigo across each fold as ONE sheet wrapping over the edge — every stone, vein and drag line that meets '
            'the fold carries on across it; no edge, rim, frame, shadow, bevel or line at the fold; no stone cut off at '
            'the fold that does not continue; nothing new (no letters, words, logo, gold lettering, rule); no motif or '
            'colour outside the lid\'s language. Measured continuity across each fold (mean / max ΔE00 over a 1 mm strip '
            'either side, the owner\'s limits 3 / 8): %s.\n\nAs a senior packaging designer, judge every image: does '
            'each fold read as one continuous sheet, and does each band belong to the lid\'s language? List every defect '
            'with its place, severity and the smallest repair. Answer in JSON.' % (
                len(images), '; '.join('%d %s' % (i + 2, w_) for i, (_, w_) in enumerate(images[1:])),
                '; '.join('%s %.2f / %.2f' % (s, r['de00_mean'], r['de00_max']) for s, r in cont.items())))
    return surface_look(out, 'sides', images, text, call, round_no)


# --- a $0 alternative for the owner's call (NOT D-D11-4's method): the sides by edge extension ---------------------------

FILL_PAST_PX = 40


def mirror_alternative():
    """The sides made by the bleed's own method, edge extension: each band the lid plate's outer 12 mm (the marbling
    with the type removed) mirrored at its fold, beside the master's flat untouched, at 300 PPI; the corners white.
    For the owner's call only — D-D11-4 names one masked edit, and its continuity is not a pass: it holds by
    construction, so it is recorded as unmeasured (None)."""
    out = SIDES / 'alternative-mirror'
    out.mkdir(parents=True, exist_ok=True)
    plate_png = zm.OUT / 'engine' / 'plate.png'
    plate = np.asarray(Image.open(plate_png).convert('RGB'))
    k_plate = plate.shape[1] / zm.LID_MM[0]
    deep = int(round(SIDE_MM * k_plate))
    # the plate keeps the sketch's raster under the name, which starts inside 12 mm of the left edge: in the outer
    # 12 mm only, the name's own mask and every rose-gold part inside its window (the window holds no vein; parts
    # touching the window's edge are a vein's and kept), grown 3 px, are filled from their surround (Telea), so no letter
    # is mirrored
    # (the fill reaches FILL_PAST_PX past the 12 mm line, so Telea never draws from a letter cut by that line)
    frame = np.ones(plate.shape[:2], dtype=bool)
    frame[deep + FILL_PAST_PX:-deep - FILL_PAST_PX, deep + FILL_PAST_PX:-deep - FILL_PAST_PX] = False
    x0, y0, x1, y1 = (v * zm.UP for v in zm.WINDOWS['name'])
    gold = np.zeros(plate.shape[:2], dtype=np.uint8)
    gold[y0:y1, x0:x1] = zm.masks(plate[y0:y1, x0:x1])['gold']
    count, labels, stats, _ = cv2.connectedComponentsWithStats(gold, connectivity=8)
    for i in range(1, count):
        left, top, w, h = stats[i, :4]
        if left <= x0 or top <= y0 or left + w >= x1 or top + h >= y1:
            gold[labels == i] = 0
    name = zm.element_mask_up(zm.load_master_pick(), 'name', plate.shape[:2]).astype(np.uint8) | gold
    name = cv2.dilate(name, np.ones((7, 7), np.uint8))
    filled_mask = (name.astype(bool) & frame).astype(np.uint8)
    plate = cv2.inpaint(plate, filled_mask, 5, cv2.INPAINT_TELEA)
    bands = {'top': plate[:deep][::-1], 'bottom': plate[-deep:][::-1],
             'left': plate[:, :deep][:, ::-1], 'right': plate[:, -deep:][:, ::-1]}
    flat, band = unfolded_print(bands)
    Image.fromarray(flat).save(out / 'sides-unfolded-print.png', dpi=(300, 300))
    record = {'schema': 'day11_zilal_sides_alternative/1',
              'method': 'edge extension (the bleed\'s method, D-D10-2.6): each band the lid plate\'s outer 12 mm '
                        'mirrored at its fold; the plate is the marbling with the small type removed',
              'not_the_owners_method': 'D-D11-4 names ONE masked edit for the sides; that edit and its one repair '
                                       'failed (sides/continuity.json, eye-r0.json, repair1/). This is a printable '
                                       'option for the owner\'s call, outside the jury and the box.',
              'source': {'plate': lm.rel(plate_png), 'sha256': lm.sha256(plate_png), 'px_per_mm': round(k_plate, 3)},
              'name_filled_in_the_bands_mm2': round(float(filled_mask[:, :deep].sum() + filled_mask[:, -deep:].sum()
                                                          + filled_mask[:deep, deep:-deep].sum()
                                                          + filled_mask[-deep:, deep:-deep].sum()) / k_plate ** 2, 2),
              'continuity': {'holds': None, 'why': 'by construction: a mirror repeats the lid\'s own edge, so the '
                                                   'measure would read 0 whatever the sides look like'},
              'unfolded_print': lm.rel(out / 'sides-unfolded-print.png'), 'band_px': band}
    lm.write_json(out / 'alternative.json', record)
    return record


# --- the inside lid and the tray: the picked sketch by the preservation path --------------------------------------------

INSIDE = OBJ / 'inside-lid'
TRAY = OBJ / 'tray'
INSIDE_MM = (184.0, 114.0)          # the lid's inside face: 3 mm in from each edge of the 190 × 120 lid (palette_open)


def surface_pick(kind):
    """A surface's pick: J1's first of its three (ranking.json), the sketch's 1536 × 970 middle and its sha256."""
    folder = OBJ / {'inside': 'inside-lid', 'tray': 'tray'}[kind] / 'sketches'
    ranking = json.loads((folder / 'ranking.json').read_text(encoding='utf-8'))
    first = sorted(ranking['payload']['ranking'], key=lambda r: r['rank'])[0]
    path = folder / ('S%d' % first['sketch']) / 'lid.png'
    return {'sketch': first['sketch'], 'score': first['score'], 'path': path, 'sha256': lm.sha256(path)}


def print_pdf(plate_bleed, size_mm, bleed_px, px_per_mm, out_pdf, title):
    """A plate as print: the bled picture on a page the size of the trim plus 3 mm, trim and bleed boxes set, the image
    tagged sRGB; returns the trim rectangle (points)."""
    import fitz
    page_w, page_h = size_mm[0] + 2 * lm.BLEED_MM, size_mm[1] + 2 * lm.BLEED_MM
    pdf = fitz.open()
    p = pdf.new_page(width=lm.pt(page_w), height=lm.pt(page_h))
    bm = bleed_px / px_per_mm
    p.insert_image(fitz.Rect(lm.pt(lm.BLEED_MM - bm), lm.pt(lm.BLEED_MM - bm), lm.pt(lm.BLEED_MM + size_mm[0] + bm),
                             lm.pt(lm.BLEED_MM + size_mm[1] + bm)), filename=str(plate_bleed))
    trim = fitz.Rect(lm.pt(lm.BLEED_MM), lm.pt(lm.BLEED_MM), lm.pt(lm.BLEED_MM + size_mm[0]),
                     lm.pt(lm.BLEED_MM + size_mm[1]))
    p.set_bleedbox(p.rect)
    p.set_trimbox(trim)
    pdf.set_metadata({'title': title, 'creator': 'apps/pipeline/services/zilal_object.py'})
    lm.tag_srgb(pdf)
    pdf.save(str(out_pdf), garbage=3, deflate=True)
    pdf.close()
    return trim


def flat_of(pdf_path, trim, out_png):
    """The trimmed print flat at 300 PPI, rendered from the PDF itself."""
    import fitz
    with fitz.open(str(pdf_path)) as d:
        pix = d[0].get_pixmap(dpi=300, clip=trim, alpha=False)
        pix.set_dpi(300, 300)
        pix.save(str(out_png))
    return out_png


def finish_sheet(surface, flat_png, plates, out):
    """The surface's finish sheet: one page, its flat beside the list of what each part is made of (finish_sheet.pdf
    and a 150 PPI png of it), and the same list as JSON. [Day 12] The words are laid out as HTML (MuPDF shapes them
    with its own fonts): set in Helvetica, the title's Ẓ and ā and every Arabic word in a plate's row printed as dots,
    and a long row ran off the page; now each row wraps in its column, and a list too long for the page refuses."""
    import html

    import fitz
    pdf = fitz.open()
    p = pdf.new_page(width=lm.pt(297), height=lm.pt(210))
    p.insert_htmlbox(fitz.Rect(lm.pt(12), lm.pt(7), lm.pt(285), lm.pt(19)),
                     '<p style="font-family: sans-serif; font-size: 14pt; margin: 0">%s</p>'
                     % html.escape('Ẓilāl — %s: finish sheet' % surface), scale_low=1)
    with Image.open(flat_png) as im:
        w, h = im.size
    box_w = 170.0
    box_h = box_w * h / w
    p.insert_image(fitz.Rect(lm.pt(12), lm.pt(22), lm.pt(12 + box_w), lm.pt(22 + box_h)), filename=str(flat_png))
    rows = ''.join('<p style="margin: 0 0 5pt 0">%s: %s</p>' % (html.escape(row['plate']), html.escape(row['what']))
                   for row in plates)
    spare, _ = p.insert_htmlbox(fitz.Rect(lm.pt(190), lm.pt(22), lm.pt(285), lm.pt(200)),
                                '<div style="font-family: sans-serif; font-size: 8.5pt">%s</div>' % rows, scale_low=1)
    if spare < 0:
        raise ValueError('the finish sheet of %s: its plates do not fit the page' % surface)
    pdf.save(str(out / 'finish-sheet.pdf'), garbage=3, deflate=True)
    pdf.close()
    lm.render_png(out / 'finish-sheet.pdf', 0, 150, out / 'finish-sheet.png')
    lm.write_json(out / 'finish-sheet.json', {'surface': surface, 'plates': plates})
    return out / 'finish-sheet.png'


def pair_crops(pick, pick_k, flat, flat_k, boxes_mm, offset_mm, out, prefix):
    """1 : 1 crops: each box (mm, in the master's trimmed frame) cut from the master's flat and from the pick (its own
    pixels repeated to the flat's scale; ``offset_mm`` the master's origin in the pick's frame), the pick above a white
    rule and the master below; each checked under the eye's limits."""
    made = []
    for name, (x0, y0, x1, y1) in boxes_mm.items():
        f = flat[int(round(y0 * flat_k)):int(round(y1 * flat_k)), int(round(x0 * flat_k)):int(round(x1 * flat_k))]
        px0, py0 = (x0 + offset_mm[0]) * pick_k, (y0 + offset_mm[1]) * pick_k
        px1, py1 = (x1 + offset_mm[0]) * pick_k, (y1 + offset_mm[1]) * pick_k
        s = pick[int(round(py0)):int(round(py1)), int(round(px0)):int(round(px1))]
        s = cv2.resize(s, (f.shape[1], f.shape[0]), interpolation=cv2.INTER_NEAREST)
        pair = np.concatenate([s, np.full((8, f.shape[1], 3), 255, dtype=np.uint8), f], axis=0)
        path = out / 'crops' / ('%s-%s.png' % (prefix, name))
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(pair).save(path, dpi=(300, 300))
        lm._image_block(path)
        made.append((path, name))
    return made


BLEED_EDGE_DE_MAX = 2.0


def bleed_outside_trim(flat_png, plate):
    """The bleed lies wholly outside the trim: the flat rendered from the PDF's trim box against the unbled plate brought
    to the flat's size, read along each edge's outer 1 mm (a mirror line inside the trim would show there as a jump)."""
    flat = np.asarray(Image.open(flat_png).convert('RGB'))
    ref = np.asarray(Image.fromarray(plate).resize((flat.shape[1], flat.shape[0]), Image.LANCZOS))
    de = lm.delta_e00(lm.srgb_to_lab(flat), lm.srgb_to_lab(ref))
    e = int(round(300 / lm.MM_PER_INCH))
    edges = {'top': de[:e], 'bottom': de[-e:], 'left': de[:, :e], 'right': de[:, -e:]}
    rows = {k: round(float(v.mean()), 3) for k, v in edges.items()}
    return {'read': 'the trimmed flat (from the PDF) against the plate before its bleed, each edge\'s outer 1 mm, mean '
                    'ΔE00', 'edges': rows, 'whole_mean': round(float(de.mean()), 3),
            'holds': all(v <= BLEED_EDGE_DE_MAX for v in rows.values())}


def inside_master():
    """The inside lid by the preservation path: the picked sketch's middle (190 × 120 mm) cropped 3 mm in from each edge
    to the inside face (184 × 114), upscaled Lanczos 2× (proved at the pick's size), 3 mm of bleed by mirroring;
    inside-lid.pdf (the plate, sRGB) and its 300 PPI flat. Nothing redrawn; print only (no foil, no relief)."""
    pick = surface_pick('inside')
    out = INSIDE / 'master'
    out.mkdir(parents=True, exist_ok=True)
    src = np.asarray(Image.open(pick['path']).convert('RGB'))
    h, w = src.shape[:2]
    k = w / zm.LID_MM[0]
    cw, ch = int(round(INSIDE_MM[0] * k)), int(round(INSIDE_MM[1] * k))
    x0, y0 = (w - cw) // 2, (h - ch) // 2
    crop = src[y0:y0 + ch, x0:x0 + cw]
    up = lm.upscale(crop)
    proof = lm.prove_upscale(crop, up, {})
    px_per_mm = up.shape[1] / INSIDE_MM[0]
    b = int(np.ceil(lm.BLEED_MM * px_per_mm))
    bled = cv2.copyMakeBorder(up, b, b, b, b, cv2.BORDER_REFLECT_101)
    Image.fromarray(bled).save(out / 'inside-plate-bleed.png')
    trim = print_pdf(out / 'inside-plate-bleed.png', INSIDE_MM, b, px_per_mm, out / 'inside-lid.pdf',
                     'Ẓilāl inside lid')
    flat_of(out / 'inside-lid.pdf', trim, out / 'inside-lid-flat.png')
    bleed_check = bleed_outside_trim(out / 'inside-lid-flat.png', up)
    plates = [{'plate': 'print', 'what': 'the picked sketch, upscaled (Lanczos 2×), in process colour on the lid board'},
              {'plate': 'foil', 'what': 'none'}, {'plate': 'relief', 'what': 'none'}]
    shutil.copyfile(out / 'inside-lid-flat.png', out / 'finish-proof.png')
    finish_sheet('the inside of the lid', out / 'inside-lid-flat.png', plates, out)
    record = {'schema': 'day11_zilal_inside_lid/1', 'pick': {k_: (lm.rel(v) if k_ == 'path' else v) for k_, v in pick.items()},
              'crop_px': [x0, y0, x0 + cw, y0 + ch], 'crop_why': 'the inside face sits 3 mm in from each edge of the '
              '190 × 120 lid the sketch was drawn at', 'size_mm': list(INSIDE_MM), 'upscale': proof,
              'ppi': round(px_per_mm * lm.MM_PER_INCH, 1), 'effective_ppi': round(k * lm.MM_PER_INCH, 1),
              'bleed_px': b, 'bleed_outside_trim': bleed_check, 'plates': plates,
              'finish_proof': lm.rel(out / 'finish-proof.png'),
              'finish_proof_is': 'the print flat itself: the inside carries no foil or relief',
              'files': {n: lm.rel(out / n) for n in ('inside-lid.pdf', 'inside-lid-flat.png', 'inside-plate-bleed.png',
                                                      'finish-sheet.pdf', 'finish-sheet.png')}}
    lm.write_json(out / 'inside-lid.json', record)
    return record


INSIDE_BOXES_MM = {'upper-left': (6.0, 6.0, 66.0, 46.0), 'middle': (62.0, 37.0, 122.0, 77.0),
                   'lower-right': (118.0, 68.0, 178.0, 108.0)}


def inside_look(record, call, round_no, label=None):
    """The inside lid's eye round: the pick and the master's flat (fitted) and three 1 : 1 crops (pick above, master
    below), against the owner's rule and what the path allows."""
    out = INSIDE / 'master'
    pick = np.asarray(Image.open(zm.REPO / record['pick']['path']).convert('RGB'))
    flat = np.asarray(Image.open(zm.REPO / record['files']['inside-lid-flat.png']).convert('RGB'))
    k = pick.shape[1] / zm.LID_MM[0]
    images = [lid_language(out),
              (fitted(pick, out / 'crops' / 'pick-fitted.png'), 'THE PICK (the sketch, 190 × 120 mm as drawn)'),
              (fitted(flat, out / 'crops' / 'master-fitted.png'), 'THE MASTER\'s flat (the inside face, 184 × 114 mm)')]
    offset = ((zm.LID_MM[0] - INSIDE_MM[0]) / 2, (zm.LID_MM[1] - INSIDE_MM[1]) / 2)
    images += [(p, '1 : 1 crop, %s: the pick above, the master below' % n)
               for p, n in pair_crops(pick, k, flat, 300 / lm.MM_PER_INCH, INSIDE_BOXES_MM, offset, out, 'inside')]
    text = ('THE INSIDE-LID GATE (Day 11, D-D11-4). The inside of the palette\'s lid, by the preservation path: the '
            'owner\'s rule is "inside lid (soft lilac: lilac stones on a paler ground, no petals or words) … built by the '
            'preservation path", the eye the gate. Images: %s.\n\nALLOWED (the path): the crop to the inside face, 3 mm '
            'off each edge of the sketch\'s 190 × 120 frame (the inside sits 3 mm in from the lid\'s edge); the upscale '
            '(Lanczos 2×, measured at the pick\'s size: mean ΔE00 %.2f, max %.2f, SSIM %.4f) and the softness it brings at '
            'print size; the 3 mm bleed by mirroring (outside the flat). ANYTHING ELSE is a defect: a stone, vein or '
            'colour changed, added or lost; any petal, word or letter; a seam; a colour shift. As a senior packaging '
            'designer judge every image and list every defect with its place, severity and the smallest repair. Answer '
            'in JSON.' % ('; '.join('%d %s' % (i + 1, w_) for i, (_, w_) in enumerate(images)),
                          record['upscale']['de00_mean'], record['upscale']['de00_max'], record['upscale']['ssim']))
    return surface_look(out, 'inside', images, text, call, round_no, label)


# --- the tray: J1's S3 by the preservation path, its pans read flat into pans.json, the names live, the cut page ----------

TRAY_INSERT_MM = (184.0, 114.0)     # the insert (palette_open.INSIDE_MM); the sketch's 190 × 120 frame its 3 mm bleed
SURROUND_PX = (6, 16)               # a pan's surround: its left and right sides, 6–16 pick px outside its box
PAN_SURROUND_DE_MIN = 10.0          # D-D11-4: every pan ΔE00 ≥ 10 from its surround, lightened if needed
LIFT_STEP_L = 0.5                   # … by the least L* step that reaches it (as palette_open's lift_from_case)
TEAL_HUE = (150.0, 250.0)           # a teal pan: CIELAB hue 150–250° and chroma ≥ 10 (palette_open's teal_pans)
TEAL_CHROMA_MIN = 10.0
TEAL_ROW_MIN = 3
NAME_BAND_PX = (4, 36)              # a pan's name: cream ink in the band 4–36 pick px under its box
NAME_SIDE_PX = 40                   # the band reaches 40 px past the pan each side (a long name is wider than its pan)
CREAM_L_MIN = 55.0
CREAM_C_MAX = 30.0
CUT_STROKE_MM = 0.25
CUT_HEX = '#C69559'                 # the cut lines' colour on the dieline page, as Day 10's (never printed)


def lab_to_hex(lab):
    """CIELAB (D65) to an sRGB hex, clipped to the gamut."""
    light, a, b = (float(v) for v in lab)
    fy = (light + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200

    def inv(t):
        if t ** 3 > 0.008856:
            return t ** 3
        return (t - 16 / 116) / 7.787
    x, y, z = 0.95047 * inv(fx), 1.0 * inv(fy), 1.08883 * inv(fz)
    rgb = np.array([3.2404542 * x - 1.5371385 * y - 0.4985314 * z, -0.9692660 * x + 1.8760108 * y + 0.0415560 * z,
                    0.0556434 * x - 0.2040259 * y + 1.0572252 * z])
    out = np.where(rgb <= 0.0031308, 12.92 * rgb, 1.055 * np.power(np.clip(rgb, 0, None), 1 / 2.4) - 0.055)
    vals = np.clip(np.round(out * 255), 0, 255).astype(int)
    return '#%02X%02X%02X' % tuple(vals)


def hex_lab(hex_):
    return lm.srgb_to_lab(np.array([[[int(hex_[i:i + 2], 16) for i in (1, 3, 5)]]], dtype=np.uint8))[0, 0]


def tray_names():
    """The brief's 18 names, row by row (palette_tray reads them from brief 124, as Day 10 did)."""
    from apps.ire import palette_tray
    brief = (zm.REPO / 'bbrose_design_os' / 'apps' / 'pipeline' / 'tests' / 'fixtures_124' / 'brief_124.txt').read_text()
    return palette_tray.read_tray(brief)['names']


def lift(pan_hex, surround_hex):
    """The least lightening (L* in 0.5 steps, a* b* kept) that brings a pan ΔE00 ≥ 10 from its surround, checked again on
    the hex it prints as. Returns the hex and the step (0 when none is needed)."""
    base = hex_lab(pan_hex)
    around = hex_lab(surround_hex)
    step = 0.0
    hex_ = pan_hex
    while float(lm.delta_e00(hex_lab(hex_)[None], around[None])[0]) < PAN_SURROUND_DE_MIN:
        step += LIFT_STEP_L
        if base[0] + step > 100:
            raise ValueError('%s cannot be lifted to ΔE00 10 from %s' % (pan_hex, surround_hex))
        hex_ = lab_to_hex((base[0] + step, base[1], base[2]))
    return hex_, step


WELL_OFF_DE = 15.0                  # a pan's well: the pixels off its surround by over ΔE00 15, the part holding its centre
WELL_SIZE_SPREAD_PX = 8             # a well more than 8 px off the wells' median size ran into its ground: the reader's box
RIM_INSET_MM = 0.5                  # the copper rim: the swatch is the well 0.5 mm in, all round
READ_INSET = 0.10                   # the colour is read 10 % further in, clear of the rim's shadow


def well_of(lab, box, surround):
    """A pan's well: its box grown 15 px, the pixels off the surround by over ΔE00 15, the part holding the centre; its
    bounding box (pick px) and its mask."""
    x0, y0, x1, y1 = box
    g = 15
    win = lab[y0 - g:y1 + g, x0 - g:x1 + g]
    off = lm.delta_e00(win.reshape(-1, 3), np.broadcast_to(surround, (win.shape[0] * win.shape[1], 3)))
    off = (off.reshape(win.shape[:2]) > WELL_OFF_DE).astype(np.uint8)
    _, labels, stats, _ = cv2.connectedComponentsWithStats(off, connectivity=8)
    c = labels[win.shape[0] // 2, win.shape[1] // 2]
    left, top, w, h, _ = stats[c]
    return [int(x0 - g + left), int(y0 - g + top), int(x0 - g + left + w), int(y0 - g + top + h)], labels[
        top:top + h, left:left + w] == c


def corner_radius(mask):
    """A well's corner radius (px): along each corner's diagonal, the steps from the box's corner to the mask, d, and
    r = d / (√2 − 1); the median of the four."""
    h, w = mask.shape
    ds = []
    for flip_y, flip_x in ((False, False), (False, True), (True, False), (True, True)):
        m = mask[::-1] if flip_y else mask
        m = m[:, ::-1] if flip_x else m
        d = 0
        while d < min(h, w) // 2 and not m[d, d]:
            d += 1
        ds.append(d)
    return float(np.median(ds)) / (2 ** 0.5 - 1)


def tray_pans(pick):
    """pans.json's rows from the pick: each pan found by the reader (tray_picture.read_tray_picture, its finish too);
    its well measured (the pixels off its surround, the wells' median size the check), the swatch the well 0.5 mm in
    with the wells' measured corner radius; its colour the CIELAB mean over the swatch 10 % further in (the reader's
    median kept beside it); its surround (the median of its sides 6–16 px out), ΔE00 between them and the least lift to
    10; its name's ink box under it; row 3's teal pans counted."""
    from apps.pipeline.targets.container import tray_picture as tp
    buf = cv2.imencode('.png', cv2.cvtColor(pick, cv2.COLOR_RGB2BGR))[1].tobytes()
    read = tp.read_tray_picture(buf, 3, 6)
    if read['state'] != tp.READ:
        raise ValueError('the tray pick was not read: %s' % read['why'])
    names = tray_names()
    lab = lm.srgb_to_lab(pick)
    light, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    cream = (light > CREAM_L_MIN) & (np.hypot(a, b) < CREAM_C_MAX)
    k = pick.shape[1] / zm.LID_MM[0]
    found = []
    for r, row in enumerate(read['pans']):
        for c, pan in enumerate(row):
            x, y, w, h = pan['box_px']
            sides = np.concatenate([pick[y:y + h, x - SURROUND_PX[1]:x - SURROUND_PX[0]].reshape(-1, 3),
                                    pick[y:y + h, x + w + SURROUND_PX[0]:x + w + SURROUND_PX[1]].reshape(-1, 3)])
            surround = '#%02X%02X%02X' % tuple(int(v) for v in np.median(sides, axis=0))
            well, mask = well_of(lab, [x, y, x + w, y + h], hex_lab(surround))
            found.append((r, c, pan, surround, well, mask))
    # the grid's edges: each column's left and right and each row's top and bottom the median of its measured wells
    # (a well that ran into its dark ground — larger than the reader's box by over 8 px on a side — left out)
    def plausible(f):
        x, y, w, h = f[2]['box_px']
        well = f[4]
        return (well[0] >= x - WELL_SIZE_SPREAD_PX and well[1] >= y - WELL_SIZE_SPREAD_PX
                and well[2] <= x + w + WELL_SIZE_SPREAD_PX and well[3] <= y + h + WELL_SIZE_SPREAD_PX)
    good = [f for f in found if plausible(f)]
    cols = {c: [float(np.median([f[4][i] for f in good if f[1] == c])) for i in (0, 2)] for c in range(6)}
    rws = {r: [float(np.median([f[4][i] for f in good if f[0] == r])) for i in (1, 3)] for r in range(3)}
    radius_px = float(np.median([corner_radius(f[5]) for f in good]))
    size = [float(np.median([cols[c][1] - cols[c][0] for c in cols])), float(np.median([rws[r][1] - rws[r][0] for r in rws]))]
    rim = RIM_INSET_MM * k
    rows = []
    for r, c, pan, surround, measured, _ in found:
        x, y, w, h = pan['box_px']
        well = [cols[c][0], rws[r][0], cols[c][1], rws[r][1]]
        well_from = 'the grid: its column\'s and row\'s median edges over the measured wells'
        inner = [well[0] + rim, well[1] + rim, well[2] - rim, well[3] - rim]
        iw, ih = inner[2] - inner[0], inner[3] - inner[1]
        rx0, ry0 = int(round(inner[0] + READ_INSET * iw)), int(round(inner[1] + READ_INSET * ih))
        rx1, ry1 = int(round(inner[2] - READ_INSET * iw)), int(round(inner[3] - READ_INSET * ih))
        mean_hex = lab_to_hex(lab[ry0:ry1, rx0:rx1].reshape(-1, 3).mean(axis=0))
        de = float(lm.delta_e00(hex_lab(mean_hex)[None], hex_lab(surround)[None])[0])
        lifted, step = lift(mean_hex, surround)
        band = cream[y + h + NAME_BAND_PX[0]:y + h + NAME_BAND_PX[1], x - NAME_SIDE_PX:x + w + NAME_SIDE_PX]
        ys, xs = np.nonzero(band)
        name_box = None
        if len(ys):
            name_box = [int(x - NAME_SIDE_PX + xs.min()), int(y + h + NAME_BAND_PX[0] + ys.min()),
                        int(x - NAME_SIDE_PX + xs.max() + 1), int(y + h + NAME_BAND_PX[0] + ys.max() + 1)]
        pl = hex_lab(mean_hex)
        hue = float(np.degrees(np.arctan2(pl[2], pl[1])) % 360)
        chroma = float(np.hypot(pl[1], pl[2]))
        rows.append({'row': r + 1, 'col': c + 1, 'name': names[r][c], 'box_px': [x, y, x + w, y + h],
                     'well_px': [round(v, 1) for v in well], 'well_measured_px': [int(v) for v in measured],
                     'well_from': well_from,
                     'box_mm': [round(v / k, 3) for v in well], 'swatch_mm': [round(v / k, 3) for v in inner],
                     'hex_read': pan['hex'], 'hex_mean': mean_hex, 'finish': pan['finish'],
                     'finish_measures': pan['measures'], 'surround': surround, 'de00_to_surround': round(de, 2),
                     'lift_l': step, 'hex': lifted,
                     'de00_after': round(float(lm.delta_e00(hex_lab(lifted)[None], hex_lab(surround)[None])[0]), 2),
                     'hue_deg': round(hue, 1), 'chroma': round(chroma, 1),
                     'teal': bool(TEAL_HUE[0] <= hue <= TEAL_HUE[1] and chroma >= TEAL_CHROMA_MIN),
                     'name_box_px': name_box})
    teal = [p['name'] for p in rows if p['row'] == 3 and p['teal']]
    geometry = {'well_size_px': [float(v) for v in size], 'corner_radius_mm': round(radius_px / k, 3),
                'rim_inset_mm': RIM_INSET_MM, 'swatch_radius_mm': round(max(radius_px / k - RIM_INSET_MM, 0.0), 3),
                'colour': 'the CIELAB mean over the swatch, 10 % in from its edge (clear of the rim\'s shadow)'}
    return rows, read, {'count': len(teal), 'names': teal, 'holds': len(teal) >= TEAL_ROW_MIN,
                        'rule': 'D-D11-4: row 3 ≥ 3 teal pans (CIELAB hue 150–250°, chroma ≥ 10)'}, geometry


def name_boxes(pick, rows):
    """The names' ink, read as one type: each row's cap top and baseline the median of its six names' (a stone's light
    edge caught in one band cannot move it), each name's ink left and right read between them."""
    lab = lm.srgb_to_lab(pick)
    cream = (lab[..., 0] > CREAM_L_MIN) & (np.hypot(lab[..., 1], lab[..., 2]) < CREAM_C_MAX)
    boxes = {}
    for r in (1, 2, 3):
        mine = [p for p in rows if p['row'] == r and p['name_box_px'] is not None]
        top = int(np.median([p['name_box_px'][1] for p in mine]))
        foot = int(np.median([p['name_box_px'][3] for p in mine]))
        for p in mine:
            x0, _, x1, _ = p['box_px']
            cols = np.nonzero(cream[top:foot, x0 - NAME_SIDE_PX:x1 + NAME_SIDE_PX].any(axis=0))[0]
            cols = main_cluster(cols)
            boxes[p['name']] = [int(x0 - NAME_SIDE_PX + cols.min()), top, int(x0 - NAME_SIDE_PX + cols.max() + 1), foot]
    return boxes


NAME_GAP_PX = 20                    # word spaces read 11–14 px (1.7 mm at most); a gap over 2.5 mm is not the name's


def main_cluster(cols):
    """The name's own columns: the run of ink columns joined by gaps of at most 20 px that holds the most ink."""
    return main_cluster_gap(cols, NAME_GAP_PX)


def main_cluster_gap(cols, gap):
    """The run of columns joined by gaps of at most ``gap`` that holds the most."""
    breaks = np.nonzero(np.diff(cols) > gap)[0]
    groups = np.split(cols, breaks + 1)
    return max(groups, key=len)


def name_fit(name, box_px, cap_px, k, face_path):
    """A name set live under its pan in the small-line face: one size for every name (its cap height the names' median
    ink height, ``cap_px``), the tracking that gives the sketch's ink width, centred on the sketch's ink; the baseline
    on the row's foot."""
    from fontTools.ttLib import TTFont
    font = TTFont(face_path)
    upm = font['head'].unitsPerEm
    cap = font['OS/2'].sCapHeight / upm
    cmap = font.getBestCmap()
    hmtx = font['hmtx']
    text = name.upper()
    advance = sum(hmtx[cmap[ord(ch)]][0] for ch in text) / upm
    x0, y0, x1, y1 = (v / k for v in box_px)
    size_mm = cap_px / k / cap
    gaps = len(text) - 1
    tracking = ((x1 - x0) - advance * size_mm) / (gaps * size_mm)
    return {'name': name, 'size_pt': round(size_mm * 72 / lm.MM_PER_INCH, 3), 'size_mm': round(size_mm, 4),
            'tracking_em': round(max(tracking, 0.0), 4), 'tracking_fitted_em': round(tracking, 4),
            'x_centre_mm': round((x0 + x1) / 2, 3), 'baseline_mm': round(y1, 3), 'ink_mm': [round(v, 3) for v in (x0, y0, x1, y1)]}


NAME_OVERLAY_MM = 0.25             # a name's rendered ink within 0.25 mm (two of the sketch's pixels) of its width and centre


def names_overlay(flat_png, fits, inset):
    """Each name's rendered ink read from the print flat (300 PPI, the insert's frame): the cream columns in its band
    (its own cluster), against the sketch's ink box — the width and centre differences (mm)."""
    flat = np.asarray(Image.open(flat_png).convert('RGB'))
    lab = lm.srgb_to_lab(flat)
    cream = (lab[..., 0] > CREAM_L_MIN) & (np.hypot(lab[..., 1], lab[..., 2]) < CREAM_C_MAX)
    k = 300 / lm.MM_PER_INCH
    rows = []
    for f in fits:
        x0, y0, x1, y1 = f['ink_mm']
        r0, r1 = int((y0 - inset[1] - 0.4) * k), int((y1 - inset[1] + 0.4) * k)
        c0 = int((x0 - inset[0] - 4.0) * k)
        cols = np.nonzero(cream[r0:r1, c0:int((x1 - inset[0] + 4.0) * k)].any(axis=0))[0]
        cols = main_cluster_gap(cols, int(round(NAME_GAP_PX * k / (zm.PICK_PX[0] / zm.LID_MM[0]))))
        rx0, rx1 = (c0 + cols.min()) / k + inset[0], (c0 + cols.max() + 1) / k + inset[0]
        rows.append({'name': f['name'], 'sketch_mm': [round(x0, 3), round(x1, 3)], 'rendered_mm': [round(rx0, 3), round(rx1, 3)],
                     'd_width_mm': round((rx1 - rx0) - (x1 - x0), 3),
                     'd_centre_mm': round((rx0 + rx1) / 2 - (x0 + x1) / 2, 3)})
    return rows


def refit(fit, overlay):
    """One correction from the read: the tracking that closes the width difference over the name's gaps, the centre
    moved by the centre difference."""
    gaps = len(fit['name']) - 1
    tracking = fit['tracking_fitted_em'] - overlay['d_width_mm'] / (gaps * fit['size_mm'])
    return dict(fit, tracking_em=round(max(tracking, 0.0), 4), tracking_fitted_em=round(tracking, 4),
                x_centre_mm=round(fit['x_centre_mm'] - overlay['d_centre_mm'], 3))


def tray_master():
    """The tray by the preservation path: J1's pick upscaled (Lanczos 2×, proved), its printed names cleaned (Telea) and
    set live in the lid's small-line face; the sketch's 190 × 120 frame is the insert (184 × 114) and its 3 mm bleed.
    pans.json (each pan flat: its mean colour and finish, lifted to ΔE00 10 from its surround where needed; row 3's teal
    counted); tray-artwork.pdf (page 1 the print: the plate and the live names; page 2 the cut: the insert's outline and
    the 18 wells, as Day 10's); tray-proof.png (the pans drawn flat in their colours over the print — shown, never
    printed); the finish proof and sheet."""
    import fitz
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, Image as GImage, Rect, SolidFill, Stroke, TextRun
    pick_rec = surface_pick('tray')
    out = TRAY / 'master'
    (out / 'engine').mkdir(parents=True, exist_ok=True)
    pick = np.asarray(Image.open(pick_rec['path']).convert('RGB'))
    k = pick.shape[1] / zm.LID_MM[0]
    rows, read, teal, geometry = tray_pans(pick)
    master = json.loads((zm.OUT / 'master.json').read_text(encoding='utf-8'))
    face = master['type']['faces']['latin']
    ink = master['type']['inks']['eyeshadow']
    # the plate: the pick upscaled, its names cleaned where they are set live
    up = lm.upscale(pick)
    proof_up = lm.prove_upscale(pick, up, {})
    K = up.shape[1] / zm.LID_MM[0]
    lab = lm.srgb_to_lab(up)
    cream = (lab[..., 0] > CREAM_L_MIN) & (np.hypot(lab[..., 1], lab[..., 2]) < CREAM_C_MAX)
    clean = np.zeros(up.shape[:2], dtype=np.uint8)
    for p in rows:
        if p['name_box_px'] is not None:
            x0, y0, x1, y1 = (int(v * lm.UP) for v in p['name_box_px'])
            clean[y0 - 6:y1 + 6, x0 - 6:x1 + 6] = cream[y0 - 6:y1 + 6, x0 - 6:x1 + 6]
    clean = cv2.dilate(clean, np.ones((7, 7), np.uint8))
    plate = cv2.inpaint(up, clean, 7, cv2.INPAINT_TELEA)
    Image.fromarray(plate).save(out / 'engine' / 'plate.png')
    boxes = name_boxes(pick, rows)
    cap_px = float(np.median([b[3] - b[1] for b in boxes.values()]))
    fits = [name_fit(p['name'], boxes[p['name']], cap_px, k, face['path']) for p in rows]
    def emit_all(fits):
        """The engine's three documents, tray-artwork.pdf (print and cut pages) and its print flat, from ``fits``."""
        names = Group(name='SHADE NAMES', role='typography', children=[
            TextRun(name=f['name'], text=f['name'], x=f['x_centre_mm'], y=f['baseline_mm'], font=face['role'],
                    size_pt=f['size_pt'], color=Color.from_hex(ink), align='center', text_case='upper',
                    **({'tracking_em': f['tracking_em']} if f['tracking_em'] > 0 else {}))
            for f in fits])
        picture = Group(name='PICTURE', role='background', children=[
            GImage(name='plate', src=str(out / 'engine' / 'plate.png'), x=0.0, y=0.0, w=zm.LID_MM[0], h=zm.LID_MM[1])])
        inset = ((zm.LID_MM[0] - TRAY_INSERT_MM[0]) / 2, (zm.LID_MM[1] - TRAY_INSERT_MM[1]) / 2)
        cut_stroke = Stroke(color=Color.from_hex(CUT_HEX), width_mm=CUT_STROKE_MM)
        outline = Rect(name='insert outline (cut)', x=inset[0], y=inset[1], w=TRAY_INSERT_MM[0], h=TRAY_INSERT_MM[1],
                       fill=None, stroke=cut_stroke)
        wells = Group(name='PAN WELLS (cut)', children=[
            Rect(name='well %s' % p['name'], x=p['box_mm'][0], y=p['box_mm'][1], w=p['box_mm'][2] - p['box_mm'][0],
                 h=p['box_mm'][3] - p['box_mm'][1], radius_mm=geometry['corner_radius_mm'], fill=None, stroke=cut_stroke)
            for p in rows])
        pans_flat = Group(name='PANS (flat, proof only)', children=[
            Rect(name=p['name'], x=p['swatch_mm'][0], y=p['swatch_mm'][1], w=p['swatch_mm'][2] - p['swatch_mm'][0],
                 h=p['swatch_mm'][3] - p['swatch_mm'][1], radius_mm=geometry['swatch_radius_mm'],
                 fill=SolidFill(color=Color.from_hex(p['hex']))) for p in rows])
        meta = {'typography_surface': 'apps/pipeline/services/zilal_object.py::tray_master', 'logical_text/1.0': True}
        docs = {'tray-print.ai': [picture, names], 'tray-cut.ai': [outline, wells], 'tray-proof.ai': [picture, pans_flat, names]}
        for fname, children in docs.items():
            emit_pdf_ai(Document(page_w=zm.LID_MM[0], page_h=zm.LID_MM[1], metadata=meta,
                                 root=Group(name=fname[:-3].upper(), children=children)), str(out / 'engine' / fname))
        pdf = fitz.open()
        trim = fitz.Rect(lm.pt(inset[0]), lm.pt(inset[1]), lm.pt(inset[0] + TRAY_INSERT_MM[0]),
                         lm.pt(inset[1] + TRAY_INSERT_MM[1]))
        for fname in ('tray-print.ai', 'tray-cut.ai'):
            with fitz.open(str(out / 'engine' / fname)) as src:
                pg = pdf.new_page(width=src[0].rect.width, height=src[0].rect.height)
                pg.show_pdf_page(pg.rect, src, 0)
            pg.set_bleedbox(pg.rect)
            pg.set_trimbox(trim)
        pdf.set_page_labels([{'startpage': 0, 'prefix': '1 print: the plate and the names ', 'style': ''},
                             {'startpage': 1, 'prefix': '2 cut: insert and wells ', 'style': ''}])
        pdf.set_metadata({'title': 'Ẓilāl open tray', 'creator': meta['typography_surface']})
        lm.tag_srgb(pdf)
        pdf.save(str(out / 'tray-artwork.pdf'), garbage=3, deflate=True)
        pdf.close()
        flat_of(out / 'tray-artwork.pdf', trim, out / 'tray-flat.png')
        return trim, inset

    trim, inset = emit_all(fits)
    first = names_overlay(out / 'tray-flat.png', fits, inset)
    fits = [refit(f, o) for f, o in zip(fits, first)]
    trim, inset = emit_all(fits)
    second = names_overlay(out / 'tray-flat.png', fits, inset)
    lm.render_png(out / 'engine' / 'tray-proof.ai', 0, 300, out / 'tray-proof.png')
    spans = lm.actual_texts(out / 'engine' / 'tray-print.ai', 0)
    want = [p['name'] for p in rows]
    with fitz.open(str(out / 'tray-artwork.pdf')) as d:
        cut = d[1].get_drawings()
        fonts = {f[3]: f[1] not in ('', 'n/a') for f in d[0].get_fonts(full=True)}
        used = sorted({sp['font'] for b in d[0].get_text('dict')['blocks'] if b['type'] == 0 for ln in b['lines']
                       for sp in ln['spans']})
    shutil.copyfile(out / 'tray-proof.png', out / 'finish-proof.png')
    plates = [{'plate': 'print', 'what': 'the picked sketch upscaled (Lanczos 2×), its names live in %s, process colour'
                                        % face['label']},
              {'plate': 'cut', 'what': 'the insert\'s outline and the 18 wells (page 2)'},
              {'plate': 'pans', 'what': 'pressed powder in the wells, each its mean colour and finish (pans.json) — the '
                                        'proof draws them flat'},
              {'plate': 'foil', 'what': 'none'}, {'plate': 'relief', 'what': 'none'}]
    finish_sheet('the tray', out / 'tray-proof.png', plates, out)
    lifted = [p for p in rows if p['lift_l'] > 0]
    pans_record = {'schema': 'container_tray_pans/1.0+day11-zilal', 'grid': [3, 6], 'shape': 'square',
                   'pick': {k_: (lm.rel(v) if k_ == 'path' else v) for k_, v in pick_rec.items()},
                   'read': {k_: read[k_] for k_ in ('state', 'params', 'rim', 'glow', 'names_ink')},
                   'geometry': geometry, 'pans': rows, 'teal_row_3': teal,
                   'lifted': [{'name': p['name'], 'from': p['hex_read'], 'to': p['hex'], 'l_step': p['lift_l'],
                               'de00_before': p['de00_to_surround'], 'de00_after': p['de00_after']} for p in lifted],
                   'counts': {f: sum(1 for p in rows if p['finish'] == f) for f in ('matte', 'shimmer', 'glitter')},
                   'rule': 'D-D11-4: the pans flat, their mean colour and finish; every pan ΔE00 ≥ 10 from its '
                           'surround, lightened by the least L* step where needed',
                   'all_off_the_surround': all(p['de00_after'] >= PAN_SURROUND_DE_MIN for p in rows)}
    lm.write_json(out / 'pans.json', pans_record)
    record = {'schema': 'day11_zilal_tray/1', 'pick': pans_record['pick'], 'upscale': proof_up,
              'ppi': round(K * lm.MM_PER_INCH, 1), 'effective_ppi': round(k * lm.MM_PER_INCH, 1),
              'names': {'face': face['label'], 'ink': ink, 'fits': fits, 'live': spans,
                        'word_for_word': [s for s in spans if s] == want, 'fonts_embedded': fonts,
                        'fonts_used_by_the_text': used,
                        'unused_resource': 'the emitter lists Helvetica (unembedded) on every page, as on Day 10\'s '
                                           'tray; no text uses it',
                        'one_size_pt': fits[0]['size_pt'],
                        'overlay': {'read': 'each name\'s rendered ink in the print flat (300 PPI) against the sketch\'s '
                                            'ink: width and centre (mm); the first setting corrected once (tracking '
                                            'and centre) and read again', 'tolerance_mm': NAME_OVERLAY_MM,
                                    'first': first, 'second': second,
                                    'holds': all(abs(o['d_width_mm']) <= NAME_OVERLAY_MM
                                                 and abs(o['d_centre_mm']) <= NAME_OVERLAY_MM for o in second)},
                        'cleaned_px': int(clean.sum())},
              'cut': {'paths': len(cut), 'wells': len(rows),
                      'insert_outline': any(abs(c['rect'].width * lm.MM_PER_INCH / 72.0 - TRAY_INSERT_MM[0]) < 0.05
                                            and abs(c['rect'].height * lm.MM_PER_INCH / 72.0 - TRAY_INSERT_MM[1]) < 0.05
                                            for c in cut)},
              'teal_row_3': teal, 'lifted': pans_record['lifted'], 'geometry': geometry, 'plates': plates,
              'files': {n: lm.rel(out / n) for n in ('tray-artwork.pdf', 'tray-flat.png', 'tray-proof.png', 'pans.json',
                                                      'finish-sheet.pdf', 'finish-sheet.png')}}
    lm.write_json(out / 'tray.json', record)
    return record


def tray_look(record, call, round_no, label=None):
    """The tray's eye round: the pick, the master's proof (the pans flat over the print) and its print flat (fitted),
    and 1 : 1 crops of each row's names in two halves and of the marbling (pick above, the print flat below)."""
    out = TRAY / 'master'
    pick = np.asarray(Image.open(zm.REPO / record['pick']['path']).convert('RGB'))
    flat = np.asarray(Image.open(zm.REPO / record['files']['tray-flat.png']).convert('RGB'))
    proof = np.asarray(Image.open(zm.REPO / record['files']['tray-proof.png']).convert('RGB'))
    k = pick.shape[1] / zm.LID_MM[0]
    inset = ((zm.LID_MM[0] - TRAY_INSERT_MM[0]) / 2, (zm.LID_MM[1] - TRAY_INSERT_MM[1]) / 2)
    images = [lid_language(out),
              (fitted(pick, out / 'crops' / 'pick-fitted.png'), 'THE PICK (the sketch, 190 × 120 mm as drawn)'),
              (fitted(proof, out / 'crops' / 'proof-fitted.png'), 'THE MASTER\'s proof: the print with the 18 pans drawn '
                                                                  'flat in their read colours (190 × 120 mm, the '
                                                                  'insert and its 3 mm bleed)'),
              (fitted(flat, out / 'crops' / 'flat-fitted.png'), 'THE MASTER\'s print flat (the insert, 184 × 114 mm; '
                                                                 'the wells are cut, so the pans show as the sketch drew '
                                                                 'them here)')]
    boxes = {}
    baselines = sorted({f['baseline_mm'] for f in record['names']['fits']})
    for r, base in enumerate(baselines, 1):
        for half, (x0, x1) in (('left', (0.0, 92.0)), ('right', (92.0, 184.0))):
            boxes['row%d-%s' % (r, half)] = (x0, base - 8.0 - inset[1], x1, base + 3.0 - inset[1])
    boxes['marbling'] = (130.0, 2.0, 184.0, 22.0)
    images += [(p, '1 : 1 crop, %s: the pick above, the master\'s print below' % n)
               for p, n in pair_crops(pick, k, flat, 300 / lm.MM_PER_INCH, boxes, inset, out, 'tray')]
    half = np.asarray(Image.fromarray(proof).resize((proof.shape[1] // 2, proof.shape[0] // 2), Image.LANCZOS))
    pans = json.loads((zm.REPO / record['files']['pans.json']).read_text(encoding='utf-8'))['pans']
    pan_boxes = {}
    for r in (1, 2, 3):
        mine = [q for q in pans if q['row'] == r]
        pan_boxes['pans-row%d' % r] = (min(q['box_mm'][0] for q in mine) - 2.0, min(q['box_mm'][1] for q in mine) - 1.0,
                                       max(q['box_mm'][2] for q in mine) + 2.0, max(q['box_mm'][3] for q in mine) + 1.0)
    images += [(p, 'row %s\'s pans at 150 PPI: the pick\'s pans above, the proof\'s flat swatches below' % n[-1])
               for p, n in pair_crops(pick, k, half, 150 / lm.MM_PER_INCH, pan_boxes, (0.0, 0.0), out, 'tray')]
    lifted = record['lifted']
    repair = ''
    if round_no >= 1:
        ov = record['names']['overlay']['second']
        rose = [q for q in pans if q['name'] == 'Rosewater'][0]
        repair = ('\n\nREPAIR 1 (after round 0 named Rosewater\'s colour, the swatches\' extents and Velvet Bloom\'s '
                  'setting): every pan\'s colour is read by ONE rule, the CIELAB mean over its swatch 10 %% in from '
                  'the edge — Rosewater reads %s by that rule and %s by the reader\'s median, so the swatch is the '
                  'sketch\'s own mean (the last three images show every pan above its swatch); every swatch is drawn to '
                  'ONE contour, its well (the grid\'s median column and row edges) %.1f mm in, corners %.2f mm (the '
                  'wells\' measured %.2f mm less the rim); every name was read back from the print and corrected once '
                  '(tracking and centre): now within %.2f mm in width and %.2f mm in centre of the sketch\'s ink '
                  '(Velvet Bloom %+.3f / %+.3f mm).' % (
                      rose['hex_mean'], rose['hex_read'], record['geometry']['rim_inset_mm'],
                      record['geometry']['swatch_radius_mm'], record['geometry']['corner_radius_mm'],
                      max(abs(o['d_width_mm']) for o in ov), max(abs(o['d_centre_mm']) for o in ov),
                      [o for o in ov if o['name'] == 'Velvet Bloom'][0]['d_width_mm'],
                      [o for o in ov if o['name'] == 'Velvet Bloom'][0]['d_centre_mm']))
    text = ('THE TRAY GATE (Day 11, D-D11-4). The open tray of the palette, by the preservation path: the owner\'s rule is '
            '"tray (18 pans as stones, 3×6, names under pans in the small-line face) … built by the preservation path; '
            'tray pans flat, mean colour and finish into pans.json; row 3 ≥ 3 teal pans; every pan ΔE00 ≥ 10 from its '
            'surround, lightened if needed", the eye the gate. Images: %s.\n\nALLOWED (the path): the upscale (Lanczos '
            '2×; mean ΔE00 %.2f, max %.2f, SSIM %.4f at the pick\'s size) and its softness; the 18 names reset as live '
            'type in the lid\'s small-line face (%s, one size %.1f pt, in the lid\'s cream, centred on the sketch\'s '
            'names, each tracked to the sketch\'s width) and the sketch\'s painted names cleaned under them; the pans '
            'drawn flat in the proof in the colour read from each pan (%s); the frame\'s outer 3 mm is bleed (the '
            'insert is 184 × 114 mm). Row 3 reads %d teal pans (%s). ANYTHING ELSE is a defect: a name misspelt, '
            'misplaced or in another face; a pan\'s colour not the sketch\'s; a stone, vein or colour of the marbling '
            'changed, added or lost; a ghost of a painted name; a seam. As a senior packaging designer judge every image '
            'and list every defect with its place, severity and the smallest repair. Answer in JSON.%s' % (
                '; '.join('%d %s' % (i + 1, w_) for i, (_, w_) in enumerate(images)), record['upscale']['de00_mean'],
                record['upscale']['de00_max'], record['upscale']['ssim'], record['names']['face'],
                record['names']['one_size_pt'],
                'none lifted: every pan stands ΔE00 %.1f or more from its surround' % min(
                    q['de00_after'] for q in pans)
                if not lifted else 'lifted: ' + ', '.join('%s +%.1f L*' % (x['name'], x['l_step']) for x in lifted),
                record['teal_row_3']['count'], ', '.join(record['teal_row_3']['names']), repair))
    return surface_look(out, 'tray', images, text, call, round_no, label)


RELOOK_DPI = 1200
GUIDE_RGB = (0, 200, 255)


def name_evidence(record, name, out):
    """One name at 1200 dpi: the pick's own pixels (repeated) above, the master's print (rendered from
    tray-artwork.pdf at 1200 dpi) below, a thin cyan line at the pick's ink extents through both; and the extents read
    from each half (mm, the insert's frame)."""
    import fitz
    fit = [f for f in record['names']['fits'] if f['name'] == name][0]
    inset = ((zm.LID_MM[0] - TRAY_INSERT_MM[0]) / 2, (zm.LID_MM[1] - TRAY_INSERT_MM[1]) / 2)
    x0, y0, x1, y1 = fit['ink_mm']
    box = (x0 - 1.5, y0 - 1.0, x1 + 1.5, y1 + 1.0)                    # the pick's frame (mm)
    k = RELOOK_DPI / lm.MM_PER_INCH
    with fitz.open(str(zm.REPO / record['files']['tray-artwork.pdf'])) as d:
        clip = fitz.Rect(lm.pt(box[0]), lm.pt(box[1]), lm.pt(box[2]), lm.pt(box[3]))
        pix = d[0].get_pixmap(dpi=RELOOK_DPI, clip=clip, alpha=False)
        master = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()
    pick = np.asarray(Image.open(zm.REPO / record['pick']['path']).convert('RGB'))
    pk = pick.shape[1] / zm.LID_MM[0]
    s = pick[int(round(box[1] * pk)):int(round(box[3] * pk)), int(round(box[0] * pk)):int(round(box[2] * pk))]
    s = cv2.resize(s, (master.shape[1], master.shape[0]), interpolation=cv2.INTER_NEAREST).copy()
    reads = {}
    for half_name, half in (('pick', s), ('master', master)):
        lab = lm.srgb_to_lab(half)
        cream = (lab[..., 0] > CREAM_L_MIN) & (np.hypot(lab[..., 1], lab[..., 2]) < CREAM_C_MAX)
        cols = np.nonzero(cream.any(axis=0))[0]
        cols = main_cluster_gap(cols, int(round(2.0 * k)))
        reads[half_name] = [round(box[0] + cols.min() / k - inset[0], 3), round(box[0] + (cols.max() + 1) / k - inset[0], 3)]
    for half in (s, master):
        for xm in (x0, x1):
            c = int(round((xm - box[0]) * k))
            half[:, max(c - 1, 0):c + 1] = GUIDE_RGB
    pair = np.concatenate([s, np.full((12, master.shape[1], 3), 255, dtype=np.uint8), master], axis=0)
    path = out / 'crops' / ('evidence-%s.png' % name.lower().replace(' ', '-'))
    Image.fromarray(pair).save(path, dpi=(RELOOK_DPI, RELOOK_DPI))
    lm._image_block(path)
    return path, reads


def tray_name_relook(record, call, name, finding):
    """The tray's re-look on corrected evidence: one name the look given the lid named as a defect, shown at 1200 dpi
    with its extents read from both halves; the gate's verdict on that name."""
    out = TRAY / 'master'
    path, reads = name_evidence(record, name, out)
    images = [lid_language(out), (path, '%s at 1200 dpi: the pick above, the master\'s print below; the cyan lines '
                                        'mark the pick\'s ink extents in both' % name.upper())]
    text = ('THE TRAY GATE, A RE-LOOK ON CORRECTED EVIDENCE (Day 11, D-D11-4). The look given the lid as the language '
            'named one defect: "%s". Read from the very crop it was judged on, and again here at 1200 dpi, the name\'s '
            'ink spans %.2f–%.2f mm in the pick and %.2f–%.2f mm in the master (the insert\'s frame); the print\'s own '
            'read-back gives %+.3f mm in width and %+.3f mm in centre. Images: %s. Is the master\'s %s the sketch\'s '
            'width and centre, in the lid\'s small-line face, size and cream? Judge this name only; list a defect only '
            'if you see one here. Answer in JSON.' % (
                finding, reads['pick'][0], reads['pick'][1], reads['master'][0], reads['master'][1],
                [o for o in record['names']['overlay']['second'] if o['name'] == name][0]['d_width_mm'],
                [o for o in record['names']['overlay']['second'] if o['name'] == name][0]['d_centre_mm'],
                '; '.join('%d %s' % (i + 1, w_) for i, (_, w_) in enumerate(images)), name.upper()))
    rec = surface_look(out, 'tray', images, text, call, 1, label='relook-%s' % name.lower().replace(' ', '-'))
    rec['evidence'] = {'reads_mm': reads, 'finding': finding}
    lm.write_json(out / ('eye-relook-%s.json' % name.lower().replace(' ', '-')), rec)
    return rec


NAME_SHADOW_RING_PX = (2, 8)        # the painted names' dark rim: 2–8 upscaled px outside what the cleaning took


def tray_names_residue():
    """What the cleaning left of the sketch's painted names, measured on the tray's plate (lid_master.residue: the
    plate's local mean against the ground read from outside, ΔE00): inside the cleaned pixels, and in the ring 2–8
    upscaled px outside them where the painted letters' dark rim sat (the cleaning took the cream, not that rim). Written
    beside the tray's record as names-residue.json."""
    out = TRAY / 'master'
    pans = json.loads((out / 'pans.json').read_text(encoding='utf-8'))['pans']
    plate = np.asarray(Image.open(out / 'engine' / 'plate.png').convert('RGB'))
    pick = np.asarray(Image.open(zm.REPO / json.loads((out / 'tray.json').read_text(encoding='utf-8'))['pick']['path'])
                      .convert('RGB'))
    up = lm.upscale(pick)
    lab = lm.srgb_to_lab(up)
    cream = (lab[..., 0] > CREAM_L_MIN) & (np.hypot(lab[..., 1], lab[..., 2]) < CREAM_C_MAX)
    clean = np.zeros(up.shape[:2], dtype=np.uint8)
    for p in pans:
        if p['name_box_px'] is not None:
            x0, y0, x1, y1 = (int(v * lm.UP) for v in p['name_box_px'])
            clean[y0 - 6:y1 + 6, x0 - 6:x1 + 6] = cream[y0 - 6:y1 + 6, x0 - 6:x1 + 6]
    taken = cv2.dilate(clean, np.ones((7, 7), np.uint8)).astype(bool)
    outer = cv2.dilate(taken.astype(np.uint8), np.ones((2 * NAME_SHADOW_RING_PX[1] + 1,) * 2, np.uint8)).astype(bool)
    inner = cv2.dilate(taken.astype(np.uint8), np.ones((2 * NAME_SHADOW_RING_PX[0] + 1,) * 2, np.uint8)).astype(bool)
    ring = outer & ~inner
    record = {'read': 'lid_master.residue on the tray plate: the local mean (σ 0.5 mm) against the ground read from '
                      'outside the mask, ΔE00', 'cleaned': lm.residue(plate, taken), 'shadow_ring': lm.residue(plate, ring),
              'ring_px': list(NAME_SHADOW_RING_PX),
              'said': 'measured after the gate held; the eye read the faint dark mottling as the ground\'s texture'}
    lm.write_json(out / 'names-residue.json', record)
    return record


# --- the whole object on one sheet, for the jury once (D-D11-4) ----------------------------------------------------------

SHEET = OBJ / 'object'
SHEET_W_PX = 3300                   # the sheet's width; the jury sends it at its own long edge
SHEET_GAP_PX = 60
SHEET_LABEL_PX = 34


def object_sheet(rows, name=None):
    """Every surface on one sheet (D-D11-4: "the jury judges the whole object once, for the record, on a sheet of every
    surface — the back and the sides must read as considered as the front"): ``name`` the sheet's file stem ('sheet'
    when None; a re-judged object gets its own, the first kept); ``rows`` a list of rows, each a list of
    (picture, words); each row scaled to one height so it fills the sheet's width, the words set under each picture in
    the lid's Latin face; white ground. Writes object/sheet.png and sheet.json (every picture by sha256)."""
    from PIL import ImageDraw, ImageFont
    face = json.loads((zm.OUT / 'master.json').read_text(encoding='utf-8'))['type']['faces']['latin']['path']
    font = ImageFont.truetype(face, SHEET_LABEL_PX)
    placed = []
    for row in rows:
        ims = [Image.open(zm.REPO / p if not Path(p).is_absolute() else p).convert('RGB') for p, _ in row]
        room = SHEET_W_PX - SHEET_GAP_PX * (len(ims) + 1)
        h = int(room / sum(im.width / im.height for im in ims))
        placed.append([(im.resize((int(im.width * h / im.height), h), Image.LANCZOS), p, w) for im, (p, w) in zip(ims, row)])
    total_h = SHEET_GAP_PX + sum(r[0][0].height + SHEET_LABEL_PX * 2 + SHEET_GAP_PX for r in placed)
    sheet = Image.new('RGB', (SHEET_W_PX, total_h), 'white')
    draw = ImageDraw.Draw(sheet)
    y = SHEET_GAP_PX
    record = []
    for r in placed:
        x = SHEET_GAP_PX
        for im, p, words in r:
            sheet.paste(im, (x, y))
            draw.text((x, y + im.height + SHEET_LABEL_PX // 3), words, font=font, fill=(40, 40, 60))
            path = zm.REPO / p if not Path(p).is_absolute() else Path(p)
            record.append({'picture': lm.rel(path), 'sha256': lm.sha256(path), 'words': words})
            x += im.width + SHEET_GAP_PX
        y += r[0][0].height + SHEET_LABEL_PX * 2 + SHEET_GAP_PX
    if name is None:
        name = 'sheet'
    SHEET.mkdir(parents=True, exist_ok=True)
    sheet.save(SHEET / ('%s.png' % name))
    lm.write_json(SHEET / ('%s.json' % name), {'schema': 'day11_zilal_object_sheet/1', 'surfaces': record,
                                               'rule': 'D-D11-4: the whole object once, for the record, on a sheet of '
                                                       'every surface'})
    return SHEET / ('%s.png' % name)


def adopt_mirror_sides():
    """The owner's answer of 24 October, 3: the mirror-wrap (edge extension, the bleed's own method) is the sides of
    record; the masked edit and its repair stay as the failed method (D-D11-4's "one masked edit" superseded for the
    sides). Writes sides/sides-of-record.json and marks the alternative's own record adopted (its earlier words kept)."""
    alt = SIDES / 'alternative-mirror' / 'alternative.json'
    record = json.loads(alt.read_text(encoding='utf-8'))
    record['adopted'] = {'by': 'the owner\'s answer of 24 October, 3 (CURRENT_DECISIONS.md)',
                         'said': 'the sides of record; its continuity stays unmeasured (it holds by construction); no eye '
                                 'round on it (his answer names the object\'s re-judging only)'}
    lm.write_json(alt, record)
    of_record = {'schema': 'day11_zilal_sides_of_record/1', 'sides': lm.rel(SIDES / 'alternative-mirror'),
                 'unfolded_print': lm.rel(SIDES / 'alternative-mirror' / 'sides-unfolded-print.png'),
                 'page': lm.rel(SIDES / 'alternative-mirror' / 'sides-alternative-mirror.pdf'),
                 'method': record['method'], 'continuity': record['continuity'],
                 'failed_method': {'edit': lm.rel(SIDES / 'continuity.json'), 'repair': lm.rel(SIDES / 'repair1' / 'continuity.json'),
                                   'eye': [lm.rel(SIDES / 'eye-r0.json'), lm.rel(SIDES / 'repair1' / 'eye-r1.json')],
                                   'said': 'one masked edit and its one repair, both failing continuity and the eye'},
                 'decided_by': record['adopted']['by']}
    lm.write_json(SIDES / 'sides-of-record.json', of_record)
    return of_record


def sides_pdf(build_dir):
    """The sides' unfolded print flat as a PDF page (214 × 144 mm: the lid and its four 12 mm sides, 300 PPI, sRGB), so
    the sides have a page of their own where a page is asked for (the design task's drawing)."""
    import fitz
    png = Path(build_dir) / 'sides-unfolded-print.png'
    w_mm, h_mm = zm.LID_MM[0] + 2 * SIDE_MM, zm.LID_MM[1] + 2 * SIDE_MM
    pdf = fitz.open()
    page = pdf.new_page(width=lm.pt(w_mm), height=lm.pt(h_mm))
    page.insert_image(page.rect, filename=str(png))
    pdf.set_metadata({'title': 'Ẓilāl: the lid and its four sides, unfolded', 'creator': 'apps/pipeline/services/zilal_object.py'})
    lm.tag_srgb(pdf)
    out = Path(build_dir) / 'sides-unfolded.pdf'
    pdf.save(str(out), garbage=3, deflate=True)
    pdf.close()
    return out
