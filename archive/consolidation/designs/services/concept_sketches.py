"""Day 8 §5 Stage 1 — the sketches: ideas, never printed (D-D8-11). Six a direction along its spec's open choices
(``truthful_concept.options``), each ONE guarded gpt-image-2 edit at medium quality, 1536 × 1024 — the lid face as
flat print artwork, front-on, edge to edge, the lid the middle 970 rows (its 190 : 120 is read by cropping the 27 px
bands).

Inputs to each call, all drawn by our engine at the lid's own scale (≈ 8.08 px/mm) and place, each in the full frame:
the approved mark; the name set in the spec's face; the device — a geometric line system is never asked of the model
(D-D8-4). No house crop or library texture is attached (the owner allows at most one of each; the prompt names the
material instead). Never a web picture, never a rejected design: ``image_guard`` checks every input before payment and
logs every call.

The prompt is art direction in the owner's grammar: format → layout by zones → colours by role and hex → type by
letterform, the exact words in quotes → the device → texture and finish as flat marked zones → what stays empty → the
"do not" list. The Arabic in a sketch is a placeholder, judged for size and placement only.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from contextlib import ExitStack
from pathlib import Path

from django.conf import settings

from apps.pipeline.services import image_guard
from apps.pipeline.services import truthful_concept as tc

SKETCHES = tc.DAY8 / 'sketches'
INPUTS = tc.DAY8 / 'sketch-inputs'
PREFIX = 'day8/sketches/'
CAP_USD = 3.0                     # the owner's money plan: sketches and their ranking ≤ $3
QUALITY = 'medium'
SIZE = '%dx%d' % tc.FRAME_PX
TESSDATA = Path(settings.BASE_DIR) / 'var' / 'tessdata'
#: the copy a sketch should carry, as OCR reads Latin (the ℮ is drawn by the engine, the Arabic is a placeholder)
COPY_WORDS = ('Enchanted', 'Rose', 'EYESHADOW', 'PALETTE', '18', 'shades', '27', 'g', '0.95', 'oz')

GROUNDS = {
    'A': 'deep plum lacquer with a fine velvet grain, evenly lit, matte and flat',
    'B': 'a flat deep-teal spot colour, perfectly even, with no texture at all — nothing on this lid is a picture',
    'C': 'warm ivory cotton-rag board with a soft felt texture, evenly lit, matte and flat',
}
DO_NOT = ('no flowers, petals, leaves, gardens or any drawn rose; no arches, glow frames, halos, bokeh, sparkles or '
          'light rays; no lips or cherries; no botanical line art; no rosettes, cartouches or strapwork; no candy '
          'gradients; no script lettering; no pink on pink; no pattern behind the type; no centred stack of mark, name '
          'and descriptor; no logo in an oval or badge; nothing over the type and no type over the device; no frame or '
          'border round the lid; no word, letter, number or symbol that is not written in this brief; no second logo; '
          'no 3D, perspective, shadow, reflection, mockup, product, hands or props')
DO_NOT_MORE = {
    'A': 'no medallion at the centre (the lens has no edge); no foil across the whole field — one line carries it',
    'B': 'no foil and no metallic shine (ink, pressure and light carry this lid); no painted texture under the rings; '
         'no chrome capitals',
    'C': 'no second ornament anywhere; the instrument is never whole and never centred',
}


def _f(v, axis):
    return '%.2f' % (v / (tc.W if axis == 'x' else tc.H))


def _zone(b):
    return 'x %s–%s, y %s–%s' % (_f(b[0], 'x'), _f(b[2], 'x'), _f(b[1], 'y'), _f(b[3], 'y'))


def inputs(direction: str, option: dict) -> tuple:
    """The three engine renders for one option, each in the full 1536 × 1024 frame at its place on the lid."""
    lay = tc.layout(direction, option)
    out = INPUTS / option['id']
    ground = lay['ink']['dominant']
    made = [('the approved BBROSE mark, at its place', '1-mark.png', tc.document(lay, parts=('ground', 'logo'), only='logo')),
            ('the name set by our engine in the spec\'s face, at its place', '2-name.png',
             tc.document(lay, parts=('ground', 'type'), only='name')),
            ('the device drawn by our engine as vectors, at its place', '3-device.png', tc.document(lay, parts=('ground', 'device')))]
    items = []
    for role, name, doc in made:
        r = tc.render(doc, out / name, ground_hex=ground)
        items.append({'role': role, 'path': r['path'], 'sha256': r['sha256']})
    return lay, items


def prompt(direction: str, option: dict, lay: dict) -> str:
    s = tc.spec(direction)
    ink, b, ch = lay['ink'], lay['boxes'], option['choices']
    t = s['type']
    names = lay['lines']['name']
    name_words = ' over '.join('"%s"' % n['shown'] for n in names)
    lines = []
    lines.append('FORMAT. Flat print artwork of the closed lid of an eyeshadow palette, 190 × 120 mm, seen exactly '
                 'front-on and filling the frame edge to edge. The lid is the 1536 × 970 area between a 27 px band at '
                 'the top and one at the bottom of the 1536 × 1024 frame; the bands continue the ground and hold '
                 'nothing. A designer\'s sketch of the final artwork — not a photograph, not a product shot.')
    lines.append('THE THREE IMAGES. Image 1 is the BBROSE mark, image 2 is the name, image 3 is the device — each drawn '
                 'by our engine at its exact size and place on this lid. Reproduce all three faithfully, unchanged in '
                 'position, size, letterforms, line count and line weight.')
    zone = ['LAYOUT BY ZONES (fractions of the lid\'s width and height from its top-left corner).',
            '- The name: %s, %s, left-aligned, exactly as image 2.' % (_zone(tuple(min(n['box'][i] for n in names) if i < 2 else max(n['box'][i] for n in names) for i in range(4))),
                                                                          'one line' if len(names) == 1 else 'two lines'),
            '- "%s": %s, left-aligned.' % (lay['lines']['descriptor_en']['shown'], _zone(b['descriptor_en'])),
            '- The Arabic line "%s": %s, %s.' % (lay['lines']['descriptor_ar']['text'], _zone(b['descriptor_ar']),
                                                 'right-aligned, on the English line\'s baseline' if direction == 'A' else 'left-aligned under the English'),
            '- The mark: %s, exactly as image 1.' % _zone(b['logo']),
            '- "18 shades" and "27 g ℮ 0.95 oz": one line, %s.' % _zone((b['shades'][0], min(b['shades'][1], b['net'][1]),
                                                                        b['net'][2], max(b['shades'][3], b['net'][3])))]
    if lay.get('rule'):
        zone.append('- A hairline gold-foil rule: %s.' % _zone(lay['rule']))
    zone.append('- The device: exactly as image 3, never under or over the type.')
    lines.append('\n'.join(zone))
    roles = ['COLOURS BY ROLE.', '- Dominant, the ground: %s %s.' % (s['colours']['dominant']['name'].split(' (')[0], ink['dominant'])]
    if direction == 'A':
        roles += ['- Secondary, the field\'s fine lines: deep teal ink %s.' % ink['secondary'],
                  '- Accent, the hero line and the mark: rose-gold hot foil, shown flat as %s.' % ink['accent'],
                  '- Every word: Warm Cream %s.' % ink['type']]
    elif direction == 'B':
        printed = ink['secondary'] if ch['colour weighting'] == 'rose-led' else ink['accent']
        roles += ['- The printed ring family: %s %s.' % ('rose ink' if ch['colour weighting'] == 'rose-led' else 'blush ink', printed),
                  '- Its blind-debossed twin, shown flat as tone-on-tone lines: %s.' % ink['blind'],
                  '- The name: Warm Cream %s, raised by a blind emboss (shown flat).' % ink['type'],
                  '- The small lines and the mark: Blush %s.' % ink['accent']]
    else:
        roles += ['- The instrument, the rule and the mark: gold hot foil, shown flat as %s.' % ink['secondary'],
                  '- The wind-rose\'s hatched halves: rose-gold hot foil, shown flat as %s.' % ink['accent'],
                  '- Every word: deep plum ink %s.' % ink['type']]
    lines.append('\n'.join(roles))
    ty = ['TYPE (by letterform; the exact words in quotes).',
          '- The name %s: %s, %s, cap height %.0f mm.' % (name_words, t['display']['family'], t['display']['why'].split(' — ')[0],
                                                          names[0]['cap_mm']),
          '- "%s": %s, a geometric sans, capitals, letter-spaced wide, cap height %.1f mm.' % (
              lay['lines']['descriptor_en']['shown'], t['support']['family'], t['support']['cap_mm']),
          '- "%s": %s, alif %.1f mm — a placeholder, judged for size and placement only.' % (
              lay['lines']['descriptor_ar']['text'], t['arabic']['family'], t['arabic']['alif_mm']),
          '- "18 shades" and "27 g ℮ 0.95 oz": the same sans, cap height %.0f mm, written exactly so (lower-case units).' % t['info_cap_mm']]
    lines.append('\n'.join(ty))
    dev = s['device']
    extra = ''
    if direction == 'A':
        extra = (' Here the field fills %s; the lens sits at x %.2f, y %.2f.' % (
            'the lower two-thirds' if ch['device scale'].startswith('the lower') else 'the whole lid behind a cleared band that holds the type',
            *ch['lens position']))
    elif direction == 'B':
        extra = ' Here the rings\' centres lie %s; the field is one great circle that stops 2 mm short of every word.' % (
            'off the right edge' if 'right edge' in ch['ring field'] else 'off the bottom-right corner')
    else:
        extra = ' Here it is %d mm across, centred at x %.2f, y %.2f, cropped by the lid\'s edges.' % (
            ch['instrument scale'], *ch['instrument centre'])
    lines.append('THE DEVICE — %s. %s%s' % (dev['name'], dev['description'], extra))
    fin = {'A': 'Rose-gold hot foil (the hero line and the mark) is a flat zone of %s — no gradient, glare or glitter. The '
                'field\'s blind deboss shows only as its flat teal lines.' % ink['accent'],
           'B': 'No foil. The debossed twin family shows as flat tone-on-tone lines; the name\'s emboss shows as nothing '
                'but the cream letters themselves.',
           'C': 'Gold and rose-gold hot foil are flat zones of %s and %s — no gradient, glare or glitter. The deboss under '
                'the instrument shows as nothing.' % (ink['secondary'], ink['accent'])}[direction]
    lines.append('TEXTURE AND FINISH AS FLAT MARKED ZONES. The ground: %s. %s' % (GROUNDS[direction], fin))
    empty = {'A': 'Everything above the field except the type is plain ground; 2 mm round the mark and round the info '
                  'line stay clear of lines.',
             'B': 'The left of the lid round the type is plain teal; nothing but the ring field on the right.',
             'C': 'The text column and the ivory between it and the instrument stay plain; nothing else on the lid.'}[direction]
    lines.append('WHAT STAYS EMPTY. ' + empty)
    lines.append('DO NOT: ' + DO_NOT + '; ' + DO_NOT_MORE[direction] + '.')
    return '\n\n'.join(lines)


# --- OCR -----------------------------------------------------------------------------------------------------------

#: tesseract's TSV header: the twelve columns ``ocr_words`` reads by position
TSV_HEADER = 'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext'


class OCRFailed(RuntimeError):
    """Tesseract did not read the picture (a non-zero exit, or no TSV header): no word was read at all, which is never
    "no copy found"."""


def ocr_words(png, *, lang='eng', psm=11) -> list:
    """Tesseract's words on ``png`` (project tessdata): [(text, confidence, (x0, y0, x1, y1) px)]. Raises ``OCRFailed``
    with the exit code and stderr's tail when tesseract fails."""
    out = subprocess.run(['tesseract', str(png), '-', '--tessdata-dir', str(TESSDATA), '-l', lang, '--psm', str(psm), '-c', 'tessedit_create_tsv=1'],
                         capture_output=True, text=True, timeout=120)
    rows = out.stdout.splitlines()
    # The gate review of Day 8 (ocr_words): the exit code and the header are read. A failed read came back as no words:
    # "no copy found" on the plate proof (a false pass), "missing every word" on a sketch. Measured on tesseract 5.5.3:
    # an unreadable picture exits 1 yet prints the header; a language that does not load exits 1 and prints nothing.
    if out.returncode != 0 or rows[:1] != [TSV_HEADER]:
        tail = ' | '.join(out.stderr.strip().splitlines()[-3:])[-400:]
        raise OCRFailed('tesseract (%s, psm %s) did not read %s: exit %d, %s; stderr %r' % (
            lang, psm, Path(png).name, out.returncode, 'TSV header present' if rows[:1] == [TSV_HEADER] else 'no TSV header', tail))
    words = []
    for row in rows[1:]:
        parts = row.split('\t')
        if len(parts) == 12 and parts[11].strip() and float(parts[10]) > 0:
            x, y, w, h = (int(v) for v in parts[6:10])
            words.append((parts[11].strip(), float(parts[10]), (x, y, x + w, y + h)))
    return words


def _near(a, b):
    a, b = a.lower().strip('.,;:·'), b.lower()
    if a == b:
        return True
    if len(b) < 5 or abs(len(a) - len(b)) > 1:
        return False
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def copy_check(png) -> dict:
    """Which of the brief's Latin words OCR finds on a sketch (presence only — the engine resets every word). When the
    OCR fails nothing was read: 'ocr_failed' names why, and 'found', 'missing' and 'ocr_words' are None."""
    # the gate review of Day 8 (copy_check): a failed read is recorded, never "missing every word"; and it is not
    # raised, since make() calls this after the paid edit and before result.json is written
    try:
        words = ocr_words(png)
    except OCRFailed as failed:
        return {'found': None, 'missing': None, 'ocr_failed': str(failed), 'ocr_words': None}
    joined = ''.join(t for t, _c, _b in words).lower().replace(' ', '')

    def present(w):
        if any(_near(t, w) for t, _c, _b in words):
            return True
        if w == 'g':                                   # "27 g" read as one token
            return '27g' in joined
        return w.lower() in joined or (w == 'oz' and '0z' in joined)
    found = {w: present(w) for w in COPY_WORDS}
    return {'found': [w for w, ok in found.items() if ok], 'missing': [w for w, ok in found.items() if not ok],
            'ocr_words': [t for t, c, _b in words if c >= 50][:40]}


# --- the paid call --------------------------------------------------------------------------------------------------

def make(direction: str, option: dict, *, client=None) -> dict:
    """One sketch: the inputs rendered, checked by the guard, one medium gpt-image-2 edit paid through the ledger,
    the lid cropped from the frame, its copy read. Resumes: a sketch already made is read back, never re-bought."""
    from apps.pipeline.services.spend_reservation import paid_operation
    dest = SKETCHES / option['id']
    done = dest / 'result.json'
    if done.exists():
        return json.loads(done.read_text())
    lay, items = inputs(direction, option)
    text = prompt(direction, option, lay)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'request.json').write_text(json.dumps({'option': option, 'model': settings.IMAGE_MODEL, 'quality': QUALITY,
                                                   'size': SIZE, 'inputs': items, 'prompt': text}, ensure_ascii=False, indent=1) + '\n')
    operation = PREFIX + option['id']

    def invoke(checked):
        if client is None:
            from openai import OpenAI
            api = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0, timeout=300)
        else:
            api = client
        with ExitStack() as stack:
            files = [stack.enter_context(open(i['path'], 'rb')) for i in checked]
            response = paid_operation(api.images.edit, provider='openai', operation=operation, reservation_prefix=PREFIX,
                                      reservation_cap=CAP_USD, model=settings.IMAGE_MODEL, image=files, prompt=text,
                                      n=1, size=SIZE, quality=QUALITY)
        saved = getattr(response, '_rescue_paid_images', [])
        if len(saved) != 1:
            raise RuntimeError('the paid response is kept, but exactly one picture was not recovered')
        shutil.copyfile(saved[0], dest / 'sketch.png')
        usage = response.model_dump(mode='json').get('usage')
        return {'reservation_id': getattr(response, '_rescue_reservation_id', None), 'usage': usage,
                'output_sha256': hashlib.sha256((dest / 'sketch.png').read_bytes()).hexdigest()}

    result = image_guard.guarded_call(invoke, operation=operation, inputs=items, prompt=text, quality=QUALITY, size=SIZE,
                                      option=option['id'])
    from PIL import Image
    with Image.open(dest / 'sketch.png') as im:
        frame = im.convert('RGB')
        if frame.size != tc.FRAME_PX:
            frame = frame.resize(tc.FRAME_PX, Image.LANCZOS)
        frame.crop((0, tc.BAND_PX, tc.FRAME_PX[0], tc.BAND_PX + tc.LID_PX[1])).save(dest / 'lid.png')
    record = dict(result, option=option, lid=str(dest / 'lid.png'), copy=copy_check(dest / 'lid.png'))
    done.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
    return record


def checks_line(record: dict) -> str:
    """What the code measured on a sketch, for J1's ranking: the brief's words OCR found and missed, or that the OCR
    failed (the gate review of Day 8: a failed read is never "found 0")."""
    c = record['copy']
    if 'ocr_failed' in c:
        return 'OCR failed on this sketch, so its copy was not read (%s).' % c['ocr_failed']
    return 'OCR found %d of the brief\'s %d Latin words%s.' % (
        len(c['found']), len(COPY_WORDS), '' if not c['missing'] else '; missing: ' + ', '.join(c['missing']))


def contact_sheet(ids, out_png, *, width=1536) -> str:
    """The sketches side by side (two columns), each labelled by its option id."""
    from PIL import Image, ImageDraw, ImageFont
    tiles = [Image.open(SKETCHES / i / 'lid.png').convert('RGB') for i in ids]
    tw = width // 2
    th = round(tw * tc.LID_PX[1] / tc.LID_PX[0])
    rows = (len(tiles) + 1) // 2
    sheet = Image.new('RGB', (width, rows * (th + 28)), '#FFFFFF')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(Path(settings.BASE_DIR) / 'static' / 'fonts' / 'NotoSans-Bold.ttf'), 18)
    for k, (i, tile) in enumerate(zip(ids, tiles)):
        x, y = (k % 2) * tw, (k // 2) * (th + 28)
        sheet.paste(tile.resize((tw, th), Image.LANCZOS), (x, y + 28))
        draw.text((x + 8, y + 4), i, fill='#000000', font=font)
    sheet.save(out_png)
    return str(out_png)
