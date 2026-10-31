"""Day 10 §3 — the back sticker of the Enchanted Rose palette, in English, Spanish and Arabic.

Brief 124's back copy (description, ingredients with "May contain", how to use, warnings, Made in UAE), the net content
and the shade count, the house's four claims (``Brand.claims``), the product's name in English and Arabic, batch and
expiry fields and an EAN-13 placeholder frame with no number. Entered in English and translated to ES and AR by
``panel_translate.translate_panel_info`` (``docs/audit/day-10/sticker/translations.json``); the INCI list and the ℮ line
stay verbatim in every language. The Arabic is shaped by our engine, right to left, never mirrored.

The sticker is the palette's base less a 4 mm margin all round (182 × 112 mm), on the lid's shadow colour where the
type's contrast allows; its type in the master's faces (DM Sans; Tajawal PF Medium for the Arabic, proven line by
line). Every body line shares one size, from 7 pt down to the 5 pt floor (§W2) in steps until all three columns fit:
a line that does not fit gets smaller, never dropped and never moved (D-D8-9). The fit report lists every line.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import numpy as np

from apps.core.models import AR_UNCONFIRMED
from apps.pipeline.services import lid_master as lm

OUT = lm.REPO / 'docs' / 'audit' / 'day-10' / 'sticker'
TRANSLATIONS = OUT / 'translations.json'
SCHEMA = 'day10_sticker/1'
SURFACE = 'apps/pipeline/services/palette_sticker.py::build'

SIZE_MM = (182.0, 112.0)            # the base, 190 × 120, less 4 mm all round
BLEED_MM = 2.0                      # the ground runs 2 mm past the die
SAFE_MM = 3.5                       # no type within 3.5 mm of the die
CORNER_MM = 2.0                     # the die's corner radius (the house sticker's, back_info)
COLUMN_GAP_MM = 5.0
TITLE_PT = 10.0
BODY_START_PT = 7.0
BODY_FLOOR_PT = 5.0                 # §W2
BODY_STEP_PT = 0.25
LEAD = 1.25                         # line pitch as a share of the size
PARA_GAP = 0.55                     # a paragraph's gap, in lines
NET_PT = 9.0                        # the net content: figures over 2 mm (cap 2.1 mm at 9 pt in DM Sans)
SIGN_MM = 3.0                       # the ℮ at least 3 mm
EAN_MM = (29.83, 20.74)             # the EAN-13 symbol's frame at 80 % (the smallest magnification)
FOOT_MM = 24.0
TITLE_BAND_MM = 9.0
CONTRAST_MIN = 4.5
MM_PER_PT = 25.4 / 72.0
HARAKAT = re.compile('[\u064B-\u0652\u0670]')   # the short vowels, shadda, sukun and tanween

LATIN_REGULAR = ('fonts_dm-sans_dmsans-regular_1adb096acaa3d14f', 400.0)
LATIN_MEDIUM = (lm.SUPPORT_STEM, lm.SUPPORT_WEIGHT)
ARABIC = (lm.ARABIC_STEM, lm.ARABIC_WEIGHT)

INCI = 'Talc, Mica, Magnesium Stearate, Dimethicone, Phenoxyethanol. May contain: CI 77491, CI 77891, CI 77007.'
NET = '27 g ℮ 0.95 oz'
ENGLISH = {'description': 'An 18-shade eyeshadow palette of shimmers and mattes in dreamy rose, lilac and teal.',
           'how_to_use': 'apply with a brush or fingertip, build up for intensity.',
           'warnings': "For external use only. Avoid contact with eyes' inner rim.",
           'made_in': 'Made in UAE.', 'shades': '18 shades',
           'claims': 'Cruelty-free · 100% vegan · Dermatologist tested · Long-wear'}
NAME_EN = 'Enchanted Rose Eyeshadow Palette'
NAME_AR = 'باليت ظلال العيون إنشانتد روز'       # brief 124's own Arabic name, as written
HEADS_EN = {'description': 'Description', 'ingredients': 'Ingredients', 'how_to_use': 'How to use', 'warnings': 'Warnings'}
REGULATED = ('ingredients', 'how_to_use', 'warnings', 'made_in', 'net', 'claims')
# the house's Arabic claims on record (Brand.claims, BBROSE pk 1, each ar_source EXECUTOR_UNCONFIRMED; read 2026-10-23):
# printed in place of the machine draft, which added طبياً ("medically") to "Dermatologist tested" — a claim not made
HOUSE_CLAIMS_AR = ('خالٍ من القسوة', 'نباتي 100٪', 'مختبَر من أطباء الجلدية', 'ثبات طويل')
ORDER = ('description', 'ingredients', 'how_to_use', 'warnings', 'shades', 'claims', 'made_in', 'net')

#: [Day 11, D-D11-6] the sticker's corrected lines, the owner's, verbatim, both palettes (no tashkeel: labels are
#: unvowelled); every other line stands
CORRECTED = {
    'es': {'description': 'Paleta de sombras de ojos de 18 tonos, con acabados satinados y mates en rosas, lilas y '
                          'verdes azulados de ensueño.',
           'how_to_use': 'Aplicar con pincel o con la yema del dedo; añadir capas para mayor intensidad.',
           'claims': 'No testado en animales · 100 % vegano · Probado dermatológicamente · Larga duración'},
    'ar': {'description': 'باليت ظلال عيون من 18 درجة لونية، بلمسات لامعة ومطفأة بألوان الوردي والليلكي والأزرق المخضر '
                          'الحالمة.',
           'how_to_use': 'تطبق بالفرشاة أو بطرف الإصبع، مع زيادة الطبقات للحصول على لون أكثر كثافة.'},
}
#: D-D11-6: the AR claims are the house's (Brand.claims) printed exactly; if empty or unconfirmed, this line, marked
#: "owner to confirm" in the fit report
AR_CLAIMS_FALLBACK = 'غير مختبر على الحيوانات · نباتي 100% · مختبر من قبل أطباء الجلد · ثبات طويل الأمد'
OWNER_TO_CONFIRM = 'owner to confirm'
PALETTE_AR = 'باليت'                 # D-D11-6: باليت everywhere for palette …
PALETTE_AR_NEVER = 'لوحة'            # … never لوحة
SEPARATOR = '·'                      # a claims separator: never opens a line (D-D11-6)
GLUED = (SEPARATOR, '%', '٪')        # signs that stay on their word's line (never open one: "100 %" is one unit)
CORRECTED_SOURCE = 'the owner\'s line (D-D11-6), verbatim'


def copy(translations):
    """Each language's sections in order: {field, head, text, script, source, regulated, verbatim}."""
    calls = translations['calls']
    tr = {lang: {'description': calls['prose']['translations'][lang]['description'],
                 'how_to_use': calls['prose']['translations'][lang]['how_to_use'],
                 'warnings': calls['prose']['translations'][lang]['warnings'],
                 'made_in': calls['short lines']['translations'][lang]['description'],
                 'shades': calls['short lines']['translations'][lang]['how_to_use'],
                 'claims': calls['short lines']['translations'][lang]['warnings']} for lang in ('es', 'ar')}
    heads = {lang: {'ingredients': calls['headings']['translations'][lang]['product_name'],
                    'description': calls['headings']['translations'][lang]['description'],
                    'how_to_use': calls['headings']['translations'][lang]['how_to_use'],
                    'warnings': calls['headings']['translations'][lang]['warnings']} for lang in ('es', 'ar')}
    heads['en'] = HEADS_EN
    # the label's Arabic is set unvowelled, as printed labels are: the engine's Arabic path cannot place harakat as the
    # face does (measured: a kasratan drawn as a mark above its letter), so they are taken out of the machine draft
    for table in (tr['ar'], heads['ar']):
        for k in table:
            table[k] = HARAKAT.sub('', table[k])
    out = {}
    for lang in ('en', 'es', 'ar'):
        rows = []
        for field in ORDER:
            head = None
            if field in heads[lang]:
                head = heads[lang][field]
            if field == 'ingredients':
                text, source, verbatim = INCI, 'brief 124 (INCI, verbatim in every language)', True
            elif field == 'net':
                text, source, verbatim = NET, 'brief 124 (the ℮ line, verbatim in every language)', True
            elif lang == 'en':
                text, verbatim = ENGLISH[field], True
                source = 'brief 124'
                if field == 'claims':
                    source = 'the house\'s four claims (Brand.claims, §BH55(a))'
            elif lang == 'ar' and field == 'claims':
                text, verbatim = ' · '.join(HARAKAT.sub('', c) for c in HOUSE_CLAIMS_AR), False
                source = 'the house\'s Arabic claims on record (Brand.claims; executor-unconfirmed), harakat taken out'
            else:
                text, verbatim = tr[lang][field], False
                source = 'machine translation (panel_translate, %s)' % translations['model']
            script = 'arabic'
            if lang != 'ar' or field in ('ingredients', 'net'):
                script = 'latin'
            rows.append({'field': field, 'head': head, 'text': text, 'script': script, 'source': source,
                         'regulated': field in REGULATED, 'verbatim': verbatim, 'lang': lang})
        out[lang] = rows
    return out


def house_claims():
    """The house's claims as ``Brand.claims`` records them (the BBROSE brand: [{en, ar, ar_source}]) — the database read
    at build time, never a copy (D-D11-6 prints them exactly when they are confirmed)."""
    from apps.core.models import Brand
    return list(Brand.objects.get(name='BBROSE').claims)


def confirmed_arabic(row):
    """A Brand.claims row whose Arabic is confirmed: it carries an Arabic line and an explicit ``ar_source`` naming who
    confirmed it — present, not empty, and not the house's unconfirmed mark (``apps.core.models.AR_UNCONFIRMED``). A row
    with no ``ar_source`` is unconfirmed (it never fails open)."""
    return bool('ar' in row and row['ar'] and 'ar_source' in row and row['ar_source']
                and row['ar_source'] != AR_UNCONFIRMED)


def arabic_claims(claims):
    """D-D11-6's rule for the Arabic claims: the house's own (``claims``: Brand.claims rows) printed exactly, joined by
    the separator, when every row carries an Arabic line its maker confirmed (``confirmed_arabic``); when the list is
    empty or any row is unconfirmed (``ar_source`` missing, empty or AR_UNCONFIRMED) or carries no Arabic, the owner's
    fallback line, marked "owner to confirm". Returns (text, source, owner_to_confirm, why)."""
    rows = list(claims)
    unconfirmed = [r for r in rows if not confirmed_arabic(r)]
    if rows and not unconfirmed:
        return (' %s ' % SEPARATOR).join(r['ar'] for r in rows), 'the house\'s Arabic claims (Brand.claims), printed ' \
                                                                  'exactly (D-D11-6)', False, 'every claim confirmed'
    why = 'Brand.claims is empty'
    if rows:
        why = ('%d of %d Brand.claims rows unconfirmed (ar_source missing, empty or %s)'
               % (len(unconfirmed), len(rows), AR_UNCONFIRMED))
    return AR_CLAIMS_FALLBACK, 'the owner\'s fallback line (D-D11-6): %s' % why, True, why


def wrap_units(text, field):
    """A section's words as the units the wrap keeps together on one line: a claims line by claim, each claim with the
    separator after it (so a line breaks after a separator, never opening on one — D-D11-6); any other line word by
    word, a separator or a percent sign kept with the word before it ("100 %" never splits)."""
    words = text.split()
    units = []
    for w in words:
        if units and w in GLUED:
            units[-1].append(w)
        else:
            units.append([w])
    if field != 'claims':
        return units
    claims = [[]]
    for unit in units:
        claims[-1].extend(unit)
        if unit[-1] == SEPARATOR:
            claims.append([])
    return [c for c in claims if c]


def corrected_copy(translations, claims):
    """[Day 11, D-D11-6] Each language's sections with the owner's corrected lines, shared by both palettes (Golden
    Hour's sticker and Ẓilāl's): ES description, how to use and claims, and AR description and how to use, verbatim;
    the AR claims by ``arabic_claims`` (``claims``: Brand.claims rows); every other line as ``copy`` has it. Each row
    carries its wrap units (``wrap_units``) and, for the AR claims fallback, ``owner_to_confirm``. Refused when an Arabic
    line still says لوحة for the palette (باليت everywhere)."""
    out = copy(translations)
    ar_claims, ar_source, confirm, why = arabic_claims(claims)
    for lang, rows in out.items():
        for row in rows:
            row['owner_to_confirm'] = False
            if lang in CORRECTED and row['field'] in CORRECTED[lang]:
                row.update(text=CORRECTED[lang][row['field']], source=CORRECTED_SOURCE, verbatim=True)
            elif lang == 'ar' and row['field'] == 'claims':
                # printed exactly either way (the house's record, or the owner's own fallback line)
                row.update(text=ar_claims, source=ar_source, verbatim=True, owner_to_confirm=confirm, confirm_why=why)
            row['units'] = wrap_units(row['text'], row['field'])
            if lang == 'ar' and PALETTE_AR_NEVER in ' '.join(x for x in (row['text'], row['head']) if x):
                raise ValueError('the Arabic %s says %s for the palette (D-D11-6: %s everywhere)' % (
                    row['field'], PALETTE_AR_NEVER, PALETTE_AR))
    return out


def faces():
    """The sticker's faces as the engine resolves them (their reportlab labels registered)."""
    from apps.ire import font_roles
    return {name: font_roles.resolve_line_face(stem, weight)
            for name, (stem, weight) in (('regular', LATIN_REGULAR), ('medium', LATIN_MEDIUM), ('arabic', ARABIC))}


def width_mm(text, face, size_pt):
    """The width the emitter draws ``text`` at (mm): its advances widened by any ink past them; Arabic as the
    presentation forms the emitter shapes."""
    from apps.dielines.exporters.text_intl import shape_ar
    from apps.ire.text_metrics import drawn_width_mm
    drawn = text
    if re.search('[؀-ۿ]', text):
        drawn = shape_ar(text, keep_harakat=True)
    w = drawn_width_mm(drawn, size_pt * MM_PER_PT, face['label'])
    if w is None:
        raise ValueError('%r does not measure in %s' % (text, face['label']))
    return w


def wrap(row, column_mm, size_pt, fc):
    """One section wrapped to the column on its words: lines of segments [(face key, text)]; the head (in the medium
    face for Latin, the Arabic face for Arabic) opens the first line, followed by a colon. [Day 11] A row that carries
    ``units`` (``wrap_units``) is wrapped unit by unit: a unit goes whole to the next line when it does not fit the
    rest of this one, and only a unit longer than the column breaks between its words (a glued sign still never opens
    a line); a row without them wraps word by word, as on Day 10."""
    body_face = 'regular'
    head_face = 'medium'
    if row['script'] == 'arabic':
        body_face = 'arabic'
    if row['head'] is not None and re.search('[\u0600-\u06FF]', row['head']):
        head_face = 'arabic'                     # a head in its own script's face (the Arabic head over the Latin INCI)
    groups = []
    if row['head'] is not None:
        head_words = (row['head'] + ':').split()
        groups += [[(head_face, w)] for w in head_words]
        if row['field'] == 'ingredients' and row['lang'] == 'ar':
            groups.append([('break', '')])         # the Latin INCI under its Arabic head
    if 'units' in row:
        groups += [[(body_face, w) for w in unit] for unit in row['units']]
    else:
        groups += [[(body_face, w)] for w in row['text'].split()]
    lines = [[]]
    width = 0.0

    def span(group, opening):
        """A group's width set on a line: its words with the spaces between (and one before it unless it opens)."""
        total = sum(width_mm(w, fc[f], size_pt) for f, w in group)
        total += sum(width_mm(' ', fc[f], size_pt) for f, _ in group[1:])
        if not opening:
            total += width_mm(' ', fc[group[0][0]], size_pt)
        return total

    for group in groups:
        if group[0][0] == 'break':
            lines.append([])
            width = 0.0
            continue
        if not lines[-1] or width + span(group, False) <= column_mm:
            width += span(group, not lines[-1])
            lines[-1].extend(group)
            continue
        if span(group, True) <= column_mm or len(group) == 1:
            lines.append(list(group))
            width = span(group, True)
            continue
        # a unit longer than the column: its words one by one, a glued sign kept on its word's line — when it does not
        # fit there, the word goes down with it (a sign never opens a line, even past the column's edge)
        for face_key, word in group:
            piece = [(face_key, word)]
            if word in GLUED and lines[-1]:
                if width + span(piece, False) > column_mm and len(lines[-1]) > 1:
                    moved = lines[-1].pop()
                    lines.append([moved])
                    width = span([moved], True)
                width += span(piece, False)
                lines[-1].extend(piece)
                continue
            if lines[-1] and width + span(piece, False) > column_mm:
                lines.append(piece)
                width = span(piece, True)
            else:
                width += span(piece, not lines[-1])
                lines[-1].extend(piece)
    return [merge(line) for line in lines if line]


def merge(line):
    """Consecutive words in one face joined into one segment."""
    segs = []
    for face_key, word in line:
        if segs and segs[-1][0] == face_key:
            segs[-1] = (face_key, segs[-1][1] + ' ' + word)
        else:
            segs.append((face_key, word))
    return segs


def column_height(rows, column_mm, size_pt, fc):
    lines = sum(len(wrap(r, column_mm, size_pt, fc)) for r in rows if r['field'] != 'net')
    paras = len([r for r in rows if r['field'] != 'net'])
    pitch = size_pt * MM_PER_PT * LEAD
    return lines * pitch + (paras - 1) * PARA_GAP * pitch


def fit(blocks, fc, net=None):
    """The body size: from 7 pt down in 0.25 pt steps to the 5 pt floor, the largest at which every column's sections
    fit its height; at the floor when none does (said, never dropped). The ℮ line's band is its own size's (``net``:
    ``net_line``'s record [Day 11]; Day 10's 9 pt when None)."""
    w, h = SIZE_MM
    column = (w - 2 * SAFE_MM - 2 * COLUMN_GAP_MM) / 3
    net_pt = NET_PT
    if net is not None:
        net_pt = net['pt']
    net_band = net_pt * MM_PER_PT * LEAD + 1.0
    room = h - 2 * SAFE_MM - TITLE_BAND_MM - FOOT_MM - net_band
    size = BODY_START_PT
    while size >= BODY_FLOOR_PT - 1e-9:
        heights = {lang: column_height(rows, column, size, fc) for lang, rows in blocks.items()}
        if max(heights.values()) <= room:
            return {'size_pt': size, 'column_mm': column, 'room_mm': room, 'heights_mm': heights, 'fits': True}
        size -= BODY_STEP_PT
    heights = {lang: column_height(rows, column, BODY_FLOOR_PT, fc) for lang, rows in blocks.items()}
    return {'size_pt': BODY_FLOOR_PT, 'column_mm': column, 'room_mm': room, 'heights_mm': heights, 'fits': False}


def ground_and_ink(lid_dir=None):
    """The lid's shadow (the ground the master's small lines stand on) and its small type's ink, if their contrast
    holds (≥ 4.5 : 1); otherwise white with the shadow as ink. Read from the lid master's checks in ``lid_dir`` (Day
    10's lid when None)."""
    if lid_dir is None:
        lid_dir = lm.OUT
    checks = json.loads((Path(lid_dir) / 'checks.json').read_text())
    row = [r for r in checks['contrast'] if r['line'] == 'descriptor_en'][0]
    ratio = lm.contrast_ratio(row['ink'], row['under'])
    if ratio >= CONTRAST_MIN:
        return row['under'], row['ink'], ratio, 'the lid\'s shadow, its small type\'s ink'
    return '#FFFFFF', row['under'], lm.contrast_ratio(row['under'], '#FFFFFF'), 'white (the shadow\'s contrast fails)'


NET_LEFT, NET_RIGHT = '27 g', '0.95 oz'     # the ℮ line's words either side of the sign


def net_line(fc):
    """[Day 11, D-D11-6] The ℮ line's size and sign: "the ℮ at the line's cap height (≥ 3 mm), never larger than its
    neighbours". The line's size the least, in 0.25 pt steps up from 9 pt, at which the medium face's own cap height
    (OS/2) reaches 3 mm; the sign's ink height that cap height; its neighbours' ink above the baseline ("27 g", "0.95 oz",
    the face's own outlines) measured beside it, so the sign is never taller than the figures it stands between."""
    from apps.ire.text_metrics import cap_height_em_measured, ink_extent_em
    path = fc['medium']['path']
    cap_em = cap_height_em_measured(path)
    size = NET_PT
    while cap_em * size * MM_PER_PT < SIGN_MM - 1e-9:
        size += BODY_STEP_PT
    cap_mm = cap_em * size * MM_PER_PT
    neighbours = {text: round(ink_extent_em(text, path)[0] * size * MM_PER_PT, 4) for text in (NET_LEFT, NET_RIGHT)}
    return {'pt': size, 'sign_mm': round(cap_mm, 4), 'cap_mm': round(cap_mm, 4), 'cap_em': cap_em,
            'neighbour_ink_mm': neighbours, 'face': fc['medium']['label'],
            'holds': {'cap_at_least_3_mm': bool(cap_mm >= SIGN_MM - 1e-9),
                      'cap_never_larger_than_the_neighbours': bool(cap_mm <= min(neighbours.values()) + 1e-9)},
            'rule': 'D-D11-6: the ℮ at the line\'s cap height (≥ 3 mm), never larger than its neighbours'}


SIGN_READ_TOL_MM = 0.02             # the ℮ read back from the file stands at the cap height within 0.02 mm
SIGN_ASPECT_MAX = 1.5               # a drawn path read as a sign: no wider than 1.5 times its height


def signs_in_file(pdf_path, ink_hex, net):
    """The ℮ signs as the file draws them (D-D11-6, read back): every filled path in the line's ink whose box is as
    tall as a sign can be (1–6 mm) and no wider than half again its height (the house's ℮ is 1.11 times as wide as it
    is tall; the rules and the frame are far wider) — each one's height against the line's cap height and its
    neighbours' ink."""
    import fitz
    ink = tuple(int(ink_hex[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    rows = []
    with fitz.open(str(pdf_path)) as doc:
        for d in doc[0].get_drawings():
            if d['fill'] is None or max(abs(a - b) for a, b in zip(d['fill'], ink)) > 0.01:
                continue
            r = d['rect']                    # PDF points: its corners, so the box's sides are read in pt
            h, w = (r.y1 - r.y0) * MM_PER_PT, (r.x1 - r.x0) * MM_PER_PT
            if 1.0 <= h <= 6.0 and w <= SIGN_ASPECT_MAX * h:
                rows.append({'height_mm': round(h, 4), 'width_mm': round(w, 4),
                             'at_the_cap_height': bool(abs(h - net['cap_mm']) <= SIGN_READ_TOL_MM),
                             'at_least_3_mm': bool(h >= SIGN_MM - SIGN_READ_TOL_MM),
                             'never_larger_than_its_neighbours': bool(h <= min(net['neighbour_ink_mm'].values())
                                                                      + SIGN_READ_TOL_MM)})
    return rows


def net_nodes(x_mm, baseline, align_right, fc, colour, lang, net=None):
    """The ℮ line verbatim: "27 g", the house's sign at 3 mm, "0.95 oz", in the medium face at 9 pt (or at ``net``'s size
    with the sign at its cap height [Day 11, ``net_line``]); from x (left) or to x (right); its nodes named for their
    column's language."""
    from apps.ire.graph import Group, Path, SolidFill, TextRun
    net_pt, sign_mm = NET_PT, SIGN_MM
    if net is not None:
        net_pt, sign_mm = net['pt'], net['sign_mm']
    left_text, right_text = NET_LEFT, NET_RIGHT
    gap = width_mm(' ', fc['medium'], net_pt)
    lw = width_mm(left_text, fc['medium'], net_pt)
    rw = width_mm(right_text, fc['medium'], net_pt)
    _, sign = lm.sign_segments((0.0, 0.0, 1.0, sign_mm))
    total = lw + gap + sign['width_mm'] + gap + rw
    x0 = x_mm
    if align_right:
        x0 = x_mm - total
    sx0 = x0 + lw + gap
    segs, _ = lm.sign_segments((sx0, baseline - sign_mm, sx0 + sign['width_mm'], baseline))
    return [TextRun(name='%s:net:a' % lang, text=left_text, x=x0, y=baseline, font=fc['medium']['role'], size_pt=net_pt,
                    color=colour),
            Group(name='%s:net:sign' % lang, actual_text=lm.SIGN, children=[Path(
                name=lm.SIGN, segments=segs, fill=SolidFill(color=colour), fill_rule='nonzero')]),
            TextRun(name='%s:net:b' % lang, text=right_text, x=sx0 + sign['width_mm'] + gap, y=baseline, font=fc['medium']['role'],
                    size_pt=net_pt, color=colour)], total


def document(blocks, fitted, fc, ground_hex, ink_hex, net=None):
    """The sticker as an engine document (page = the die plus 2 mm bleed): the ground; the title band (the name in
    English at the left, in Arabic at the right); three columns, EN | ES | AR (right to left), each closing on the ℮
    line (at ``net``'s size and sign [Day 11]; Day 10's 9 pt and 3 mm when None); the foot band (batch and expiry
    write-in fields, the EAN-13 placeholder frame). Returns the document and the fit report's rows (every drawn line)."""
    from apps.ire.graph import Color, Document, Group, Rect, SolidFill, Stroke, TextRun
    w, h = SIZE_MM
    b = BLEED_MM
    ink = Color.from_hex(ink_hex)
    size = fitted['size_pt']
    pitch = size * MM_PER_PT * LEAD
    column = fitted['column_mm']
    nodes = [Rect(name='ground', x=0.0, y=0.0, w=w + 2 * b, h=h + 2 * b, fill=SolidFill(color=Color.from_hex(ground_hex)))]
    rows = []
    top = b + SAFE_MM + TITLE_PT * MM_PER_PT
    nodes.append(TextRun(name='name:en', text=NAME_EN, x=b + SAFE_MM, y=top, font=fc['medium']['role'], size_pt=TITLE_PT,
                         color=ink))
    nodes.append(TextRun(name='name:ar', text=NAME_AR, x=b + w - SAFE_MM, y=top, font=fc['arabic']['role'], size_pt=TITLE_PT,
                         color=ink, align='right', rtl=True))
    for lang, text, face in (('en', NAME_EN, 'medium'), ('ar', NAME_AR, 'arabic')):
        rows.append({'lang': lang, 'field': 'product name', 'text': text, 'size_pt': TITLE_PT,
                     'width_mm': round(width_mm(text, fc[face], TITLE_PT), 2), 'room_mm': round(w / 2 - SAFE_MM, 2),
                     'fits': width_mm(text, fc[face], TITLE_PT) <= w / 2 - SAFE_MM, 'shrunk': False,
                     'source': 'brief 124', 'review': None})
    rule_y = b + SAFE_MM + TITLE_BAND_MM - 1.5
    nodes.append(Rect(name='title rule', x=b + SAFE_MM, y=rule_y, w=w - 2 * SAFE_MM, h=0.15, fill=SolidFill(color=ink)))
    col_top = b + SAFE_MM + TITLE_BAND_MM + size * MM_PER_PT
    for i, lang in enumerate(('en', 'es', 'ar')):
        x_left = b + SAFE_MM + i * (column + COLUMN_GAP_MM)
        x_right = x_left + column
        y = col_top
        for row in blocks[lang]:
            if row['field'] == 'net':
                continue
            for line in wrap(row, column, size, fc):
                x = x_left
                rtl_line = lang == 'ar' and line[0][0] == 'arabic'
                if lang == 'ar':
                    x = x_right
                    for face_key, text in line:
                        nodes.append(TextRun(name='%s:%s' % (lang, row['field']), text=text, x=x, y=y,
                                             font=fc[face_key]['role'], size_pt=size, color=ink, align='right',
                                             rtl=face_key == 'arabic'))
                        x -= width_mm(text, fc[face_key], size) + width_mm(' ', fc[face_key], size)
                else:
                    for face_key, text in line:
                        nodes.append(TextRun(name='%s:%s' % (lang, row['field']), text=text, x=x, y=y,
                                             font=fc[face_key]['role'], size_pt=size, color=ink))
                        x += width_mm(text, fc[face_key], size) + width_mm(' ', fc[face_key], size)
                drawn = ' '.join(t for _, t in line)
                line_w = sum(width_mm(t, fc[k], size) for k, t in line) + width_mm(' ', fc['regular'], size) * (len(line) - 1)
                review = None
                if 'owner_to_confirm' in row and row['owner_to_confirm']:
                    review = OWNER_TO_CONFIRM                 # [Day 11] D-D11-6's AR claims fallback
                elif not row['verbatim'] and row['regulated']:
                    review = 'machine draft — for review'
                elif not row['verbatim']:
                    review = 'machine translation — not regulated'
                rows.append({'lang': lang, 'field': row['field'], 'text': drawn, 'size_pt': size,
                             'width_mm': round(line_w, 2), 'room_mm': round(column, 2), 'fits': line_w <= column + 1e-6,
                             'shrunk': size < BODY_START_PT, 'source': row['source'], 'review': review,
                             'direction': 'right to left' if rtl_line else 'left to right'})
                y += pitch
            y += PARA_GAP * pitch
        net_y = b + h - SAFE_MM - FOOT_MM - 1.0
        net_drawn, total = net_nodes(x_right if lang == 'ar' else x_left, net_y, lang == 'ar', fc, ink, lang, net)
        nodes += net_drawn
        net_pt, sign_mm = NET_PT, SIGN_MM
        if net is not None:
            net_pt, sign_mm = net['pt'], net['sign_mm']
        rows.append({'lang': lang, 'field': 'net', 'text': NET, 'size_pt': net_pt, 'sign_mm': sign_mm,
                     'width_mm': round(total, 2), 'room_mm': round(column, 2), 'fits': total <= column, 'shrunk': False,
                     'source': 'brief 124 (the ℮ line, verbatim in every language)', 'review': None,
                     'direction': 'left to right'})
    # the foot band: batch and expiry write-ins at the left, the EAN-13 frame at the right
    foot_top = b + h - SAFE_MM - FOOT_MM + 2.0
    fields = (('BATCH', 'lot'), ('EXP', 'expiry'))
    for j, (word, key) in enumerate(fields):
        fy = foot_top + 6.0 + j * 7.0
        nodes.append(TextRun(name='foot:%s' % key, text=word, x=b + SAFE_MM, y=fy, font=fc['medium']['role'], size_pt=7.0,
                             color=ink))
        rows.append({'lang': 'en', 'field': 'foot', 'text': word, 'size_pt': 7.0,
                     'width_mm': round(width_mm(word, fc['medium'], 7.0), 2), 'room_mm': 14.0,
                     'fits': width_mm(word, fc['medium'], 7.0) <= 14.0, 'shrunk': False,
                     'source': 'the write-in field\'s label', 'review': None, 'direction': 'left to right'})
        nodes.append(Rect(name='foot:%s line' % key, x=b + SAFE_MM + 14.0, y=fy + 0.6, w=40.0, h=0.15,
                          fill=SolidFill(color=ink)))
    ex, ey = b + w - SAFE_MM - EAN_MM[0], b + h - SAFE_MM - EAN_MM[1]
    nodes.append(Rect(name='EAN-13 placeholder frame (no number)', x=ex, y=ey, w=EAN_MM[0], h=EAN_MM[1],
                      stroke=Stroke(color=ink, width_mm=0.15)))
    nodes.append(TextRun(name='foot:ean', text='EAN-13', x=ex + EAN_MM[0] / 2, y=ey + EAN_MM[1] / 2 + 1.0,
                         font=fc['regular']['role'], size_pt=6.0, color=ink, align='center'))
    rows.append({'lang': 'en', 'field': 'foot', 'text': 'EAN-13', 'size_pt': 6.0,
                 'width_mm': round(width_mm('EAN-13', fc['regular'], 6.0), 2), 'room_mm': EAN_MM[0],
                 'fits': width_mm('EAN-13', fc['regular'], 6.0) <= EAN_MM[0], 'shrunk': False,
                 'source': 'the placeholder frame\'s label (no number)', 'review': None, 'direction': 'left to right'})
    doc = Document(page_w=w + 2 * b, page_h=h + 2 * b, title='Enchanted Rose back sticker',
                   metadata={'typography_surface': SURFACE, 'logical_text/1.0': True},
                   root=Group(name='STICKER', role='label', children=nodes))
    return doc, rows


def arabic_proofs(rows, fc):
    """Each Arabic line as the emitter draws it against the face's own shaping (``arabic_display.compare``: raqm with
    the granted Tajawal Medium against the derived face's presentation forms): IoU and the ink components."""
    from apps.dielines.exporters.text_intl import shape_ar
    from apps.ire import arabic_display as ad
    source = fc['arabic']['granted_path']
    drawn = fc['arabic']['path']
    out = []
    for r in rows:
        if r['lang'] != 'ar' or not re.search('[؀-ۿ]', r['text']):
            continue
        ref = ad.supersampled(ad.render_reference, source, r['text'], em_px=ad.MEASURE_EM_PX)
        got = ad.supersampled(ad.render_basic, drawn, shape_ar(r['text'], keep_harakat=True), em_px=ad.MEASURE_EM_PX)
        c = ad.compare(ref, got)
        parts = c['components']
        whole = parts['missing'] == 0 and parts['split'] == 0 and parts['extra'] == 0 and parts['merged'] == 0
        out.append({'text': r['text'], 'iou': c['iou'], 'components': parts,
                    'faithful': bool(c['iou'] >= ad.IOU_FAITHFUL and whole)})
    return out


def _norm(text):
    return ' '.join(unicodedata.normalize('NFKC', text).split())


def drawn_names(doc):
    """The names of the sticker's nodes that carry words, in drawing order — one per ActualText span the emitter
    writes (each TextRun, and the ℮'s group)."""
    from apps.ire.graph import Group, TextRun
    return [n.name for n in doc.root.children if isinstance(n, TextRun) or (isinstance(n, Group) and n.actual_text)]


def copy_check(pdf, blocks, names):
    """Word for word, each language against ITS OWN spans only: the file's ActualText spans paired with the drawn
    nodes' names (``names``, '<lang>:<field>…', in drawing order); each section's spans joined must BE its copy, the
    head with it (INCI and the ℮ line verbatim in every column, so one column cannot stand for another — the review of
    Day 10). A section with no span is dropped; sections drawn out of the copy's order are moved."""
    spans = lm.actual_texts(pdf, 0)
    if len(spans) != len(names):
        raise ValueError('%d ActualText spans for %d named nodes' % (len(spans), len(names)))
    out, dropped, moved = [], [], []
    for lang, rows in blocks.items():
        mine = [(n.split(':')[1], sp) for n, sp in zip(names, spans) if n.split(':')[0] == lang]
        for r in rows:
            words = r['text']
            if r['head'] is not None:
                words = r['head'] + ': ' + r['text']
            own = [sp for field, sp in mine if field == r['field']]
            found = bool(own) and _norm(' '.join(own)) == _norm(words)
            out.append({'lang': lang, 'field': r['field'], 'found': found, 'verbatim': r['verbatim']})
            if not own:
                dropped.append('%s:%s' % (lang, r['field']))
        drawn_order = []
        for field, _ in mine:
            if not drawn_order or drawn_order[-1] != field:
                drawn_order.append(field)
        copy_order = [r['field'] for r in rows if r['field'] in drawn_order]
        if drawn_order != copy_order:
            moved.append({'lang': lang, 'drawn': drawn_order, 'copy': copy_order})
    return {'rows': out, 'all_found': all(x['found'] for x in out), 'dropped': dropped, 'moved': moved,
            'inci_in_every_language': sorted(x['lang'] for x in out if x['field'] == 'ingredients' and x['found'])
            == sorted(blocks),
            'net_in_every_language': sorted(x['lang'] for x in out if x['field'] == 'net' and x['found']) == sorted(blocks),
            'span_names': names}


def build(out_dir, *, corrected=False, claims=None, lid_dir=None):
    """§3 at $0 (the translations already made): sticker.pdf (page 1 the artwork with its 2 mm bleed, page 2 the die and
    the safe area), sticker.ai (layers: ground, type, guides), sticker-flat.png at 300 PPI, fit-report.json.

    [Day 11] With ``corrected``, D-D11-6's lines (``corrected_copy``; the AR claims by ``claims``, Brand.claims as the
    database holds them when None), wrapped unit by unit, and the ℮ line at its cap height (``net_line``); the ground
    and ink read from the lid master in ``lid_dir`` (Day 10's when None). Day 10's sticker is built without them."""
    import fitz
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    out = Path(out_dir)
    translations = json.loads(TRANSLATIONS.read_text())
    fc = faces()
    net = None
    if corrected:
        if claims is None:
            claims = house_claims()
        blocks = corrected_copy(translations, claims)
        net = net_line(fc)
    else:
        blocks = copy(translations)
    fitted = fit(blocks, fc, net)
    ground, ink, ratio, why = ground_and_ink(lid_dir)
    doc, rows = document(blocks, fitted, fc, ground, ink, net)
    usage = {}
    engine = out / 'engine'
    engine.mkdir(parents=True, exist_ok=True)
    art = engine / 'sticker-engine.ai'
    emit_pdf_ai(doc, str(art), usage_out=usage)
    w, h = SIZE_MM
    trim = fitz.Rect(lm.pt(BLEED_MM), lm.pt(BLEED_MM), lm.pt(BLEED_MM + w), lm.pt(BLEED_MM + h))
    src = fitz.open(str(art))
    support = fc['regular']['path']

    def guides(page, oc):
        page.draw_rect(trim, color=(0.85, 0, 0.55), width=0.25, radius=lm.pt(CORNER_MM) / min(trim.width, trim.height),
                       oc=oc)
        safe = fitz.Rect(trim.x0 + lm.pt(SAFE_MM), trim.y0 + lm.pt(SAFE_MM), trim.x1 - lm.pt(SAFE_MM), trim.y1 - lm.pt(SAFE_MM))
        page.draw_rect(safe, color=(0, 0.6, 0.9), width=0.25, dashes='[1 2] 0', oc=oc)
        page.insert_font(fontname='support', fontfile=str(support))
        page.insert_text((trim.x0 + lm.pt(1), trim.y1 - lm.pt(1)), 'DIE 182 x 112 mm, corners r 2 mm - BLEED 2 mm - SAFE 3.5 mm',
                         fontname='support', fontsize=5, color=(0.85, 0, 0.55), oc=oc)

    pdf = fitz.open()
    p = pdf.new_page(width=src[0].rect.width, height=src[0].rect.height)
    p.show_pdf_page(p.rect, src, 0)
    p = pdf.new_page(width=src[0].rect.width, height=src[0].rect.height)
    guides(p, 0)
    for page in pdf:
        page.set_bleedbox(page.rect)
        page.set_trimbox(trim)
    pdf.set_page_labels([{'startpage': 0, 'prefix': '1 artwork ', 'style': ''},
                         {'startpage': 1, 'prefix': '2 die and safe area ', 'style': ''}])
    pdf.set_metadata({'title': 'Enchanted Rose back sticker', 'creator': SURFACE})
    pdf.save(str(out / 'sticker.pdf'), garbage=3, deflate=True)
    pdf.close()
    ai = fitz.open()
    ocg = {name: ai.add_ocg(name, on=True) for name in ('artwork', 'guides')}
    p = ai.new_page(width=src[0].rect.width, height=src[0].rect.height)
    p.show_pdf_page(p.rect, src, 0, oc=ocg['artwork'])
    guides(p, ocg['guides'])
    p.set_bleedbox(p.rect)
    p.set_trimbox(trim)
    ai.set_metadata({'title': 'Enchanted Rose back sticker (layers)', 'creator': SURFACE})
    ai.save(str(out / 'sticker.ai'), garbage=3, deflate=True)
    ai.close()
    src.close()
    with fitz.open(str(art)) as d:
        pix = d[0].get_pixmap(dpi=300, clip=trim, alpha=False)
        pix.set_dpi(300, 300)
        pix.save(str(out / 'sticker-flat.png'))
    fonts = {}
    with fitz.open(str(out / 'sticker.pdf')) as d:
        for f in d[0].get_fonts(full=True):
            fonts[f[3]] = {'embedded': f[1] not in ('', 'n/a'), 'type': f[2]}
    checked = copy_check(art, blocks, drawn_names(doc))
    proofs = arabic_proofs(rows, fc)
    shown = arabic_side_by_side(proofs, fc, out / 'arabic-engine-vs-face.png')
    smallest = min(r['size_pt'] for r in rows)
    longest = max(rows, key=lambda r: r['width_mm'])
    report = {
        'schema': SCHEMA, 'size_mm': list(SIZE_MM), 'bleed_mm': BLEED_MM, 'safe_mm': SAFE_MM,
        'ground': ground, 'ink': ink, 'contrast': round(ratio, 2), 'ground_why': why,
        'faces': {k: v['label'] for k, v in fc.items()},
        'body': {'size_pt': fitted['size_pt'], 'start_pt': BODY_START_PT, 'floor_pt': BODY_FLOOR_PT,
                 'fits': fitted['fits'], 'column_mm': round(fitted['column_mm'], 2), 'room_mm': round(fitted['room_mm'], 2),
                 'heights_mm': {k: round(v, 2) for k, v in fitted['heights_mm'].items()}},
        'smallest_pt': smallest, 'longest_line': {k: longest[k] for k in ('lang', 'field', 'text', 'width_mm')},
        'lines': rows, 'dropped': checked['dropped'], 'moved': checked['moved'],
        'for_review': [r for r in rows if r['review'] == 'machine draft — for review'],
        'notes': ['the Arabic description calls the palette لوحة where the lid and the brief\'s Arabic name say باليت '
                  '(machine translation; for review)',
                  'the Spanish how-to-use says "superposicionar" (machine translation; "superponer" reads more naturally; '
                  'for review)',
                  'batch and expiry are write-in fields; the EAN-13 frame holds no number (none is invented)',
                  'the Arabic claims are the house\'s on record (Brand.claims, executor-unconfirmed), harakat taken '
                  'out: the machine draft added طبياً ("medically") to "Dermatologist tested", a claim not made, and '
                  'said "long-term" for "Long-wear" (the review of Day 10); every translated claim is for review',
                  'the Arabic is set without harakat: the machine draft carried them, and the engine\'s Arabic path drew '
                  'a kasratan as a mark above its letter; printed labels are unvowelled'],
        'arabic_lines': proofs, 'arabic_all_faithful': all(x['faithful'] for x in proofs),
        'arabic_said': 'the house\'s per-line test (arabic_display.compare at 160 px to the em, IoU 0.95 and every ink '
                       'component) reads the engine\'s drawing against the face\'s own shaping: %d of %d lines hold; the '
                       'rest differ by the face\'s kerning, which the engine\'s Arabic path does not apply — the same letters '
                       'and joins, shown for the three lowest in arabic-engine-vs-face.png (face above, engine below)' % (
                           sum(1 for x in proofs if x['faithful']), len(proofs)),
        'arabic_shown': shown,
        'copy': checked, 'fonts': fonts,
        'fonts_embedded': all(f['embedded'] for name, f in fonts.items() if name != 'Helvetica'),
        'translations': {'file': lm.rel(TRANSLATIONS), 'model': translations['model'], 'spend': translations['spend']},
    }
    if corrected:
        report.update(corrected_report(art, doc, rows, blocks, net, ink))
    lm.write_json(out / 'fit-report.json', report)
    return report


def corrected_report(art, doc, rows, blocks, net, ink_hex):
    """[Day 11] D-D11-6 read back from the sticker's own file: the corrected lines found word for word in their own
    language's spans; no لوحة in any Arabic span (باليت everywhere); no drawn line and no span opening on the separator;
    the ℮ signs as drawn against the line's cap height and their neighbours; the lines the owner is to confirm."""
    spans = lm.actual_texts(art, 0)
    names = drawn_names(doc)
    arabic_spans = [sp for n, sp in zip(names, spans) if n.split(':')[0] in ('ar', 'name')]
    by_section = {}
    for n, sp in zip(names, spans):
        by_section.setdefault(tuple(n.split(':')[:2]), []).append(sp)
    lines = []
    for lang, table in CORRECTED.items():
        heads = {r['field']: r['head'] for r in blocks[lang]}
        for field, text in table.items():
            words = text
            if heads[field] is not None:
                words = heads[field] + ': ' + text
            lines.append({'lang': lang, 'field': field, 'text': text,
                          'verbatim_in_the_file': _norm(' '.join(by_section[(lang, field)])) == _norm(words)})
    claims_ar = [r for r in blocks['ar'] if r['field'] == 'claims'][0]
    signs = signs_in_file(art, ink_hex, net)
    opening = [r['text'] for r in rows if r['text'].startswith(SEPARATOR)]
    return {
        'schema': 'day11_sticker/1',
        'corrected_lines': {'rule': 'D-D11-6, verbatim, both palettes (no tashkeel)', 'lines': lines,
                            'all_verbatim': all(x['verbatim_in_the_file'] for x in lines)},
        'arabic_claims': {'text': claims_ar['text'], 'source': claims_ar['source'],
                          'owner_to_confirm': claims_ar['owner_to_confirm'], 'why': claims_ar['confirm_why']},
        'owner_to_confirm': [r for r in rows if r['review'] == OWNER_TO_CONFIRM],
        'palette_word': {'never': PALETTE_AR_NEVER, 'found_in_arabic_spans': sum(sp.count(PALETTE_AR_NEVER) for sp in arabic_spans),
                         'palette_in_arabic_spans': sum(sp.count(PALETTE_AR) for sp in arabic_spans),
                         'holds': not any(PALETTE_AR_NEVER in sp for sp in spans)},
        'separator': {'lines_opening_on_it': opening,
                      'spans_opening_on_it': [sp for sp in spans if sp.lstrip().startswith(SEPARATOR)],
                      'holds': not opening and not any(sp.lstrip().startswith(SEPARATOR) for sp in spans),
                      'rule': 'no line opens on "·": a claims line breaks after a separator, the separator kept at the '
                              'end of its line (the claims wrap claim by claim)'},
        'net': dict(net, signs_in_file=signs,
                    signs_hold=bool(len(signs) == len(blocks) and all(
                        s_['at_the_cap_height'] and s_['at_least_3_mm'] and s_['never_larger_than_its_neighbours']
                        for s_ in signs))),
        'notes': ['D-D11-6: the owner\'s corrected lines printed verbatim (ES description, how to use and claims; AR '
                  'description and how to use); باليت for palette, never لوحة',
                  'the AR claims: %s — %s' % (claims_ar['source'], OWNER_TO_CONFIRM if claims_ar['owner_to_confirm']
                                              else 'confirmed'),
                  'the ℮ line set at %.2f pt so the sign stands at the medium face\'s cap height, %.3f mm (≥ 3 mm), '
                  'no taller than the figures beside it (%s mm)' % (net['pt'], net['cap_mm'], ', '.join(
                      '%.3f' % v for v in net['neighbour_ink_mm'].values())),
                  'batch and expiry are write-in fields; the EAN-13 frame holds no number (none is invented)',
                  'the warnings and "Made in" lines stand as Day 10 printed them (machine drafts, for review)',
                  'the Arabic is set without harakat: printed labels are unvowelled'],
    }


SIDE_BY_SIDE_EM_PX = 60


def arabic_side_by_side(proofs, fc, path):
    """The Arabic lines the pixel test reads lowest (three), each the face's own shaping (raqm, the granted Tajawal
    Medium) above the engine's drawing (the derived face's presentation forms), for the eye: what the number measures."""
    from PIL import Image
    from apps.dielines.exporters.text_intl import shape_ar
    from apps.ire import arabic_display as ad
    worst = sorted(proofs, key=lambda p: p['iou'])[:3]
    rows = []
    for p in worst:
        for im in (ad.render_reference(fc['arabic']['granted_path'], p['text'], em_px=SIDE_BY_SIDE_EM_PX),
                   ad.render_basic(fc['arabic']['path'], shape_ar(p['text'], keep_harakat=True), em_px=SIDE_BY_SIDE_EM_PX)):
            a = np.asarray(im)
            if a.dtype == bool:
                a = a.astype(np.uint8) * 255
            rows.append(255 - a.astype(np.uint8))
        rows.append(np.full((16, 4), 255, dtype=np.uint8))
    width = max(r.shape[1] for r in rows)
    Image.fromarray(np.concatenate([np.pad(r, ((4, 4), (0, width - r.shape[1])), constant_values=255) for r in rows],
                                   axis=0)).save(path)
    return [p['text'] for p in worst]
