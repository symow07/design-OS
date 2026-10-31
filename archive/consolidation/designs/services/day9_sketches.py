"""Day 9 §3 — the sketches: free, high quality, ideas never printed (D-D8-11). Three a idea along its spec's open choices
(18 in all), each ONE guarded gpt-image-2 edit at HIGH quality, 1536 × 1024 — the lid face as flat print artwork,
front-on and edge to edge, the lid the middle 970 rows (its 190 : 120 read by cropping the 27 px bands).

The only input is the approved logo — the approval's own source raster (image_guard.APPROVED_LOGO), never an engine
render (§3). The prompt is art direction in the owner's grammar, built from the idea's spec: format → composition with
its zones → the three layers → colours by hex → type character, with the exact words → finishes → what stays quiet →
the do-not list. Foil and relief are suggested lightly; it is not a 3D render.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from contextlib import ExitStack
from pathlib import Path

from django.conf import settings

from apps.pipeline.services import image_guard
from apps.pipeline.services import truthful_concept as tc

DAY9 = tc.REPO / 'docs' / 'audit' / 'day-9'
SPECS = DAY9 / 'directions'
SKETCHES = DAY9 / 'sketches'
PREFIX = 'day9/sketches/'
CAP_USD = 7.0                      # the owner's budget table: sketches ≤ $7
QUALITY = 'high'                   # §3: "gpt-image-2 high"
SIZE = '%dx%d' % tc.FRAME_PX
IDEAS = ('A-1', 'A-2', 'B-1', 'B-2', 'C-1', 'C-2')
#: three of a 2 × 2 × 2 grid of the spec's open choices: every axis takes both its values at least once
PATTERN = ((0, 0, 0), (1, 1, 0), (0, 1, 1))
COPY_LINES = ('"Enchanted Rose"', '"Eyeshadow Palette"', '"باليت ظلال العيون"', '"18 shades"', '"27 g ℮ 0.95 oz"')
#: the spec's refusals in picture words (the image model knows no Day 8 and builds nothing): what the sketch must not show
SKETCH_DO_NOT = ('the name at the top left with an ornament at the right; a centred name inside an ornate frame; logo, name '
                 'and descriptor piled on one centre line; a stock close-up of glass, silk, iridescence or bokeh as wallpaper; '
                 'concentric rings; fields of wavy lines; a compass or a clock dial; rose flowers, petals, gardens, arches, '
                 'glowing frames, lips or cherries; botanical line art; candy gradients or glowing halos; pink on pink; one '
                 'colour family everywhere; a busy pattern as wallpaper with type floating on it; type over other type; a logo '
                 'inside an oval; a generic script name; a six-pointed star; a rainbow; any religious symbol; plum, or deep '
                 'teal with rose lines, or cream with gold lines as the colour scheme')
DO_NOT_TAIL = ('no word, letter, number or symbol that is not in this brief; no second logo; no extra brand names; '
               'no 3D, perspective, shadow, reflection, product, hands, props or mockup — flat print artwork only')


def spec(idea: str) -> dict:
    return json.loads((SPECS / f'{idea}.json').read_text())


def options(idea: str) -> list:
    """The idea's three sketches along its open choices, in PATTERN order: ids like 'A-1.1'."""
    axes = spec(idea)['open_choices']
    out = []
    for n, levels in enumerate(PATTERN, 1):
        out.append({'id': f'{idea}.{n}', 'idea': idea, 'direction': idea[0],
                    'choices': {a['axis']: a['values'][k] for a, k in zip(axes, levels)}, 'levels': list(levels)})
    return out


def _zones(zones: dict) -> str:
    lines = []
    for key, value in zones.items():
        where = value if isinstance(value, str) else 'x %.2f–%.2f, y %.2f–%.2f' % (value[0], value[2], value[1], value[3])
        lines.append('- %s: %s' % (key.replace('_', ' '), where))
    return '\n'.join(lines)


def _shades(s: dict) -> str:
    """The 18 shades by family, for an idea that shows them (the spec's shade map: working values, names from the brief)."""
    rows = {}
    for sh in s['shade_map']:
        rows.setdefault(sh['row'], []).append(sh['hex'])
    fam = {1: 'rose', 2: 'lilac', 3: 'teal'}
    return ' The eighteen shades, which this lid shows: ' + '; '.join(
        '%s %s' % (fam[r], ', '.join(v)) for r, v in sorted(rows.items())) + '.'


def _layers(s: dict) -> str:
    """The three layers in art-direction words: the spec's sketch brief where it has one (no engine instructions)."""
    sk, lay = s.get('sketch'), s['layers']
    if sk:
        return ('THE THREE LAYERS.\n1. The picture: ' + sk['picture'] + '.\n2. The crafted ornament, drawn with machine '
                'precision (about %d lines per centimetre where densest): ' % lay['ornament']['lines_per_cm_densest']
                + sk['ornament'] + '.\n3. The finish: ' + sk['finish'] + '.')
    return ('THE THREE LAYERS.\n1. The picture: ' + lay['hero']['what'] + '.\n2. The crafted ornament: ' + lay['ornament']['what']
            + ' — drawn with machine precision, densest at about %d lines per centimetre.\n3. The finish: ' % lay['ornament']['lines_per_cm_densest']
            + lay['finish']['note'] + '.')


def _type(s: dict) -> str:
    sk = s.get('sketch') or {}
    name = sk.get('name') or s['lettering']['name']
    arabic = sk.get('arabic') or s['lettering']['arabic']
    small = sk.get('small') or s['lettering']['support'].split(' — ')[0]
    return ('TYPE CHARACTER, WITH THE EXACT WORDS. The name: ' + name + '. The Arabic: ' + arabic + ' — an equal of the '
            'English, never a subtitle. Small lines: ' + small + '. Image 1 is the BBROSE logo: reproduce it exactly, '
            'unchanged in its letterforms, in its zone. The only words on the lid are, exactly: ' + ' · '.join(COPY_LINES) + '.')


def prompt(option: dict) -> str:
    s = spec(option['idea'])
    choices = '; '.join('%s: %s' % (k, v) for k, v in option['choices'].items())
    parts = [
        'FORMAT. Flat print artwork of the closed lid of a prestige eyeshadow palette, 190 × 120 mm, seen exactly front-on '
        'and filling the frame edge to edge. The lid is the 1536 × 970 area between a 27 px band at the top and one at the '
        'bottom of the 1536 × 1024 frame; the bands continue the ground and hold nothing. A designer\'s high-quality sketch '
        'of the finished printed lid: foil and relief suggested lightly, as flat metallic colour and soft relief light — '
        'not a 3D render.',
        'THE IDEA. ' + s['idea'],
        'COMPOSITION WITH ITS ZONES (fractions of the lid\'s width and height from its top-left corner). '
        + s['composition'] + ' This sketch: ' + choices + '.\n' + _zones(s['zones']) + '\nQuiet by design: ' + s['quiet'] + '.',
        _layers(s),
        'COLOURS BY HEX. ' + '; '.join('%s %s' % (k.replace('_', ' '), v) for k, v in s['colours'].items()) + '.'
        + (_shades(s) if s.get('shows_18_shades') else ''),
        _type(s),
        'FINISHES (the house\'s own): gold hot foil, rose-gold hot foil, emboss and deboss — shown as flat metallic colour '
        'and soft relief, never as glare or glitter; no other metallic.',
        'WHAT STAYS QUIET. ' + s['quiet'] + '.',
        'DO NOT: ' + SKETCH_DO_NOT + '; ' + DO_NOT_TAIL + '.',
    ]
    return '\n\n'.join(parts)


def _attribute(obj, name):
    """``obj.name``, or None when the object has none (a response the spend reservation never marked): a missing record
    is said as None and refused by the caller, never read as an empty list."""
    return getattr(obj, name) if hasattr(obj, name) else None


def make(option: dict, *, client=None) -> dict:
    """One sketch: the logo checked by the guard, one high-quality gpt-image-2 edit paid through the ledger, the lid cropped
    from the frame. Resumes: a sketch already made is read back, never bought twice."""
    from PIL import Image
    from apps.pipeline.services.spend_reservation import paid_operation
    dest = SKETCHES / option['id']
    done = dest / 'result.json'
    if done.exists():
        return json.loads(done.read_text())
    text = prompt(option)
    logo_path, logo_sha = image_guard.APPROVED_LOGO
    items = [{'role': 'the approved BBROSE logo', 'path': str(logo_path)}]
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'request.json').write_text(json.dumps({'option': option, 'model': settings.IMAGE_MODEL, 'quality': QUALITY,
                                                   'size': SIZE, 'inputs': items, 'logo_sha256': logo_sha, 'prompt': text},
                                                  ensure_ascii=False, indent=1) + '\n')
    operation = PREFIX + option['id']

    def invoke(checked):
        api = client
        if api is None:
            from openai import OpenAI
            api = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0, timeout=400)
        with ExitStack() as stack:
            files = [stack.enter_context(open(i['path'], 'rb')) for i in checked]
            response = paid_operation(api.images.edit, provider='openai', operation=operation, reservation_prefix=PREFIX,
                                      reservation_cap=CAP_USD, model=settings.IMAGE_MODEL, image=files, prompt=text,
                                      n=1, size=SIZE, quality=QUALITY)
        saved = _attribute(response, '_rescue_paid_images')
        if saved is None or len(saved) != 1:
            raise RuntimeError('the paid response is kept, but exactly one picture was not recovered')
        shutil.copyfile(saved[0], dest / 'sketch.png')
        return {'reservation_id': _attribute(response, '_rescue_reservation_id'),
                'usage': response.model_dump(mode='json').get('usage'),
                'output_sha256': hashlib.sha256((dest / 'sketch.png').read_bytes()).hexdigest()}

    result = image_guard.guarded_call(invoke, operation=operation, inputs=items, prompt=text, quality=QUALITY, size=SIZE,
                                      option=option['id'])
    with Image.open(dest / 'sketch.png') as im:
        frame = im.convert('RGB')
        if frame.size != tc.FRAME_PX:
            frame = frame.resize(tc.FRAME_PX, Image.LANCZOS)
        frame.crop((0, tc.BAND_PX, tc.FRAME_PX[0], tc.BAND_PX + tc.LID_PX[1])).save(dest / 'lid.png')
    record = dict(result, option=option, lid=str(dest / 'lid.png'))
    done.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
    return record


def contact_sheet(ids, out_png, *, width_px) -> str:
    """The sketches side by side (three columns: one idea a row), each labelled by its id."""
    from PIL import Image, ImageDraw, ImageFont
    tiles = [Image.open(SKETCHES / i / 'lid.png').convert('RGB') for i in ids]
    tw = width_px // 3
    th = round(tw * tc.LID_PX[1] / tc.LID_PX[0])
    rows = (len(tiles) + 2) // 3
    sheet = Image.new('RGB', (width_px, rows * (th + 26)), '#FFFFFF')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(Path(settings.BASE_DIR) / 'static' / 'fonts' / 'NotoSans-Bold.ttf'), 17)
    for k, (i, tile) in enumerate(zip(ids, tiles)):
        x, y = (k % 3) * tw, (k // 3) * (th + 26)
        sheet.paste(tile.resize((tw, th), Image.LANCZOS), (x, y + 26))
        draw.text((x + 6, y + 4), i, fill='#000000', font=font)
    sheet.save(out_png)
    return str(out_png)
