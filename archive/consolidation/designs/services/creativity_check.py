"""Day 13 §2b–d — the creativity check's sheet, its map and the two calls' requests (D-D13-5, D-D13-7).

The nine record files the owner listed (§2b, in his order) are copied byte for byte to ``tiles/K<n>.png`` under labels
K1–K9 given in a shuffled order: the seed is the sha256 of the nine records' sha256 digests joined in his order, and
``random.Random(int(seed, 16)).shuffle`` deals the labels, so anyone can re-derive them. ``sheet.png`` lays the nine
pictures out at one height (Lanczos), in K order, on a white ground, each with only its label under it, the whole sheet
1536 px wide and small enough (at most 1568 px a side and 1,150,000 px) that ``lid_master._image_block`` sends its own
bytes unchanged. ``map.json`` (label → file, sha256) carries the shuffle's rule and value and the verdict rule
pre-registered from the owner's words (§2f, CURRENT_DECISIONS.md:299), and is committed before any call.

The jury (J1 and J2, once) and the designer's eye (one look) are asked the same questions on the same sheet with the
same schema: the five lids ranked for the idea and, separately, for what a $1B house would show on a counter, each
lid's idea in ten words and design or decoration; for the lipstick, the balm and the header, the source lid and
carries or copies; whether the set reads as one collection. No rubric, no system prompt, no scores; nothing about days,
rounds, scores or authorship (D-D13-5: never to approve, reject, score or judge). The requests are written at $0 and
committed before the calls; the calls themselves are made only by the runners, never here at import or in a test.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
import re
import shutil
import subprocess
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from apps.pipeline.services import jury
from apps.pipeline.services import lid_master as lm
from apps.pipeline.services.spend_reservation import paid_operation

REPO = lm.REPO
OUT = REPO / 'docs' / 'audit' / 'day-13' / 'creativity'
SCHEMA = 'day13_creativity_map/1'

#: the nine record files, in the owner's order (§2b), with the piece each one is and the name the verdict rule keys on
RECORDS = (
    ('docs/audit/day-8/concepts/B3-r2/truthful.png', 'lid', 'B3-r2'),
    ('docs/audit/day-9/concepts/B-1.3-r1/truthful.png', 'lid', 'B-1.3-r1'),
    ('docs/audit/day-9/concepts/A-2.3-r1/truthful.png', 'lid', 'A-2.3-r1'),
    ('docs/audit/day-10/lid/lid-master-flat.png', 'lid', 'golden-hour'),
    ('docs/audit/day-11/zilal/lid/lid-master-flat.png', 'lid', 'zilal'),
    ('docs/audit/day-12/lipstick/closed/lipstick-drawing.png', 'lipstick', 'lipstick'),
    ('docs/audit/day-12/balm/master/balm-drawing.png', 'balm', 'balm'),
    ('docs/audit/day-12/display/header/master/header-flat.png', 'header', 'header'),
    ('docs/audit/day-12/display/family/family-sheet.png', 'family', 'family'),
)
ZILAL = 'docs/audit/day-11/zilal/lid/lid-master-flat.png'
EARLIER = ('docs/audit/day-8/concepts/B3-r2/truthful.png', 'docs/audit/day-9/concepts/B-1.3-r1/truthful.png',
           'docs/audit/day-9/concepts/A-2.3-r1/truthful.png')
PIECES = ('lipstick', 'balm', 'header')
READERS = ('J1', 'J2', 'eye')

SEED_RULE = ('seed = sha256 of the nine records\' sha256 hex digests (lower case) joined with no separator in the owner\'s '
             'listed order (order_listed_by_the_owner), as ASCII; positions = [0, 1, …, 8] shuffled in place by '
             'Python\'s random.Random(int(seed, 16)).shuffle; K<n> is the record at listed position positions[n − 1] '
             '(0-based)')

# --- the sheet's geometry -------------------------------------------------------------------------------------------
SHEET_LONG_PX = 1536                       # §2b: 1536 px on the long side in all (the width)
MARGIN_PX = 20
GAP_PX = 20                                # between tiles in a row and between rows
LABEL_BAND_PX = 24                         # under each row: the labels' strip
LABEL_FONT_PX = 15                         # small plain type
LABEL_DROP_PX = 4                          # the label's top under its tile
LABEL_FONT = REPO / 'bbrose_design_os' / 'static' / 'fonts' / 'NotoSans-Regular.ttf'
LABEL_INK = (40, 40, 40)
GROUND = (255, 255, 255)
PDF_PPI = 150                              # the PDF's one page: the sheet at 150 px per inch

# --- the calls ------------------------------------------------------------------------------------------------------
MODEL = 'claude-opus-5-5'                  # §2c: both jurors on claude-opus-5-5 (the eye on the jury's model too)
EFFORT = 'high'
#: thinking counts against it on this model; the worst case (every token used) stays inside the owner's lines: each
#: juror at about $0.23 (two inside the $0.70), the eye at about $0.23 (inside the $0.25)
MAX_TOKENS = 11000
JURY_PREFIX = 'day13/jury/'
JURY_CAP_USD = 1.50
JURY_LINE_USD = 0.70                       # the owner's line on what is paid (§2c)
EYE_PREFIX = 'day13/designer-eye/'
EYE_OPERATION = 'creativity/sheet'         # sent as EYE_PREFIX + EYE_OPERATION by zilal_master.make_eye_call
EYE_CAP_USD = 1.50
EYE_LINE_USD = 0.25                        # the owner's line for this look (§2d)
EYE_GUARD_PREFIX = EYE_PREFIX + 'creativity'
TEXT_BYTES_PER_TOKEN = 3                   # the worst-case estimate counts text at 3 bytes a token (fewer than it is)
IMAGE_PX_PER_TOKEN = 750                   # the provider's image size: about (width × height) / 750 tokens

EYE_VOICE = 'You are the designer\'s eye for BBROSE.'
SHEET_WORDS = (
    'ONE SHEET of nine pictures of one cosmetics brand\'s packaging, each marked by a label, K1 to K9, under its lower '
    'left corner; the labels are the only thing added to the pictures. {lids} are flat print artworks of the closed lid '
    'of an eyeshadow palette, 190 × 120 mm: five different lids. {lipstick} is a drawing of a closed lipstick, front and '
    'three-quarter. {balm} is a drawing of a closed lip balm, front and three-quarter. {header} is the header card of a '
    'counter display, 250 × 110 mm. {family} is a sheet of that counter display: its flat artwork on its die, its plan '
    'and elevation, and the products it holds at one scale.')
QUESTIONS = (
    'Answer three things.\n'
    '1. The five lids ({lids}). Rank them for the strength and originality of the idea, best first (idea_rank). '
    'Separately, rank them for what a $1B house would show on a counter, best first (counter_rank). For each lid, its '
    'idea in ten words (idea_in_ten_words) and one word, design or decoration (design_or_decoration).\n'
    '2. The lipstick ({lipstick}), the lip balm ({balm}) and the display header ({header}). For each: which lid is its '
    'source (source_lid, by its label); does it carry that lid\'s idea forward or only copy its parts '
    '(carries_or_copies), with one line why (line).\n'
    '3. Do the lipstick, the lip balm, the display header and the counter display ({family}), with the lid or lids they '
    'come from, read as one collection: yes or no, with one line why (one_collection).\n'
    'Rank and answer only what is asked. Each line at most 25 words. Answer with the JSON only.')

#: words that would tell a reader of days, rounds, scores, authorship or the collection's name: absent from every text
#: block written here (the jurors' roles are jury.py's own), and counted in each answer after its call
WITHHELD = re.compile(r'\b(?:days?|rounds?|scor\w*|rubric\w*|master\w*|sketch\w*|build\w*|built|repair\w*|judg\w*|'
                      r'verdict\w*|approv\w*|reject\w*|pick\w*|owner\w*|engine\w*|jur(?:y|or)\w*|zilal|golden hour)\b'
                      r'|ẓilāl|ظلال|D-D\d', re.IGNORECASE)

OWNER_RULE = ('improved if the Ẓilāl master ranks above Day 8\'s and both of Day 9\'s builds on the idea with both jurors '
              'and the eye; mixed if the lid improved but two of the three Day 12 pieces "copy"; not improved otherwise')


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def rel(path):
    """Repo-relative when the path is in the repository (every output of the real build), else absolute (a test's)."""
    path = Path(path).resolve()
    return str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)


# --- the records and the shuffle --------------------------------------------------------------------------------------

def records(repo=REPO):
    """The nine records in the owner's order: file, piece, name, sha256, bytes and pixel size, read from the files."""
    rows = []
    for file, piece, name in RECORDS:
        data = (Path(repo) / file).read_bytes()
        with Image.open(Path(repo) / file) as im:
            size = list(im.size)
        rows.append({'file': file, 'piece': piece, 'name': name, 'sha256': sha256_bytes(data), 'bytes': len(data),
                     'px': size})
    return rows


def seed_of(digests):
    """The shuffle's seed: the sha256 of the digests joined in the listed order (SEED_RULE)."""
    return sha256_bytes(''.join(digests).encode('ascii'))


def positions(seed, count):
    """The listed positions in label order: K<n> is the record at ``positions(seed, count)[n - 1]``."""
    order = list(range(count))
    random.Random(int(seed, 16)).shuffle(order)
    return order


def labelled(rows):
    """The records under their labels, in K order, and the seed that dealt them."""
    seed = seed_of([r['sha256'] for r in rows])
    return [('K%d' % (n + 1), rows[i]) for n, i in enumerate(positions(seed, len(rows)))], seed


# --- the layout -------------------------------------------------------------------------------------------------------

def _row_fits(sizes, row, h):
    widths = [round(h * sizes[i][0] / sizes[i][1]) for i in row]
    return sum(widths) + GAP_PX * (len(row) - 1) <= SHEET_LONG_PX - 2 * MARGIN_PX


def layout(sizes):
    """Every tile at one height h, in K order, in rows broken where h comes out largest; the sheet SHEET_LONG_PX wide
    and no taller than the call's limits allow (lid_master's 1568 px a side and 1,150,000 px), the rows centred.
    Returns h, the rows, the sheet's pixel size and each tile's box (x, y, w, h) and label point (x, y)."""
    height_max = min(lm.EYE_IMAGE_EDGE_MAX, lm.EYE_PIXELS_MAX // SHEET_LONG_PX, SHEET_LONG_PX)
    count = len(sizes)
    best = None
    for r in range(1, count + 1):
        for cuts in combinations(range(1, count), r - 1):
            rows = [list(range(a, b)) for a, b in zip((0,) + cuts, cuts + (count,))]
            by_height = (height_max - 2 * MARGIN_PX - GAP_PX * (r - 1)) // r - LABEL_BAND_PX
            by_width = min((SHEET_LONG_PX - 2 * MARGIN_PX - GAP_PX * (len(row) - 1))
                           / sum(sizes[i][0] / sizes[i][1] for i in row) for row in rows)
            h = int(min(by_height, by_width))
            while h > 0 and not all(_row_fits(sizes, row, h) for row in rows):
                h -= 1
            if best is None or h > best[0]:
                best = (h, rows)
    h, rows = best
    height = 2 * MARGIN_PX + len(rows) * (h + LABEL_BAND_PX) + GAP_PX * (len(rows) - 1)
    boxes, labels = [None] * count, [None] * count
    y = MARGIN_PX
    for row in rows:
        widths = [round(h * sizes[i][0] / sizes[i][1]) for i in row]
        x = (SHEET_LONG_PX - sum(widths) - GAP_PX * (len(row) - 1)) // 2
        for i, w in zip(row, widths):
            boxes[i] = (x, y, w, h)
            labels[i] = (x, y + h + LABEL_DROP_PX)
            x += w + GAP_PX
        y += h + LABEL_BAND_PX + GAP_PX
    return {'h': h, 'rows': rows, 'px': [SHEET_LONG_PX, height], 'boxes': boxes, 'labels': labels}


def compose(tiles, out_png):
    """The sheet: each (label, picture path) resized by Lanczos into its box on the white ground, its label under it and
    nothing else; saved as a plain RGB PNG (no dpi, no text chunk), so a re-save of its pixels gives the same bytes."""
    sizes = []
    for _, path in tiles:
        with Image.open(path) as im:
            sizes.append(im.size)
    plan = layout(sizes)
    sheet = Image.new('RGB', tuple(plan['px']), GROUND)
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(LABEL_FONT), LABEL_FONT_PX)
    for (label, path), (x, y, w, h), point in zip(tiles, plan['boxes'], plan['labels']):
        with Image.open(path) as im:
            sheet.paste(im.convert('RGB').resize((w, h), Image.Resampling.LANCZOS), (x, y))
        draw.text(point, label, font=font, fill=LABEL_INK, anchor='la')
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_png)
    return plan


def write_pdf(png, pdf):
    """The same sheet on one page (its pixels embedded losslessly), the page at PDF_PPI, with no metadata."""
    import fitz
    with Image.open(png) as im:
        w, h = im.size
    doc = fitz.open()
    try:
        page = doc.new_page(width=w * 72.0 / PDF_PPI, height=h * 72.0 / PDF_PPI)
        page.insert_image(page.rect, filename=str(png))
        doc.set_metadata({})
        doc.save(str(pdf), garbage=4, deflate=True)
    finally:
        doc.close()
    return {'page_pt': [round(w * 72.0 / PDF_PPI, 3), round(h * 72.0 / PDF_PPI, 3)], 'ppi': PDF_PPI}


def pdf_pixels_equal(pdf, png):
    """Whether the PDF's one page holds one image whose pixels are the PNG's."""
    import fitz
    doc = fitz.open(str(pdf))
    try:
        images = doc[0].get_images(full=True)
        if len(doc) != 1 or len(images) != 1:
            return False
        pix = fitz.Pixmap(doc, images[0][0])
        with Image.open(png) as im:
            rgb = im.convert('RGB')
            return (pix.width, pix.height) == rgb.size and pix.n == 3 and pix.samples == rgb.tobytes()
    finally:
        doc.close()


# --- the verdict rule, pre-registered ---------------------------------------------------------------------------------

def verdict_rule(labels):
    """The owner's rule (§2f) made exact before the call, with the labels it reads."""
    by_file = {row['file']: label for label, row in labels}
    by_piece = {row['piece']: label for label, row in labels}
    return {
        'owner': OWNER_RULE,
        'owner_source': 'CURRENT_DECISIONS.md:299 (the Day 13 prompt, §2f, as transcribed)',
        'readers': list(READERS),
        'reading_read': ('a reader\'s answer is read when it ended its turn (stop_reason end_turn), parsed, its '
                         'idea_rank names each of the five lid labels exactly once and its pieces name each of the '
                         'three piece labels exactly once with carries or copies; any other answer is unread'),
        'lid_improved': ('in the IDEA ranking (idea_rank) the Ẓilāl master\'s label ranks above the labels of B3-r2, of '
                         'B-1.3-r1 and of A-2.3-r1, for J1 AND J2 AND the eye (all three); the Golden Hour lid\'s place '
                         'is not read'),
        'piece_copies': 'a piece (lipstick, balm, header) copies when at least two of the three readers answer "copies"',
        'verdict': ('"improved" if lid_improved and fewer than two pieces copy; "mixed" if lid_improved and two or more '
                    'copy; "not improved" otherwise. A read answer that ranks the Ẓilāl master below any of the three '
                    'earlier lids decides "not improved" whatever the others say; otherwise an unread answer leaves '
                    'the verdict "pending", never "not improved". Nothing is re-asked (D-D13-7: the jury once, the '
                    'eye once)'),
        'function': 'apps.pipeline.services.creativity_check.verdict',
        'labels': {
            'lids': sorted((label for label, row in labels if row['piece'] == 'lid'), key=_k_number),
            'zilal_master': {'file': ZILAL, 'label': by_file[ZILAL]},
            'earlier_lids': [{'file': f, 'label': by_file[f]} for f in EARLIER],
            'pieces': [{'piece': p, 'label': by_piece[p]} for p in PIECES],
        },
    }


def _read(payload, lids, pieces):
    """Why the answer is unread ('' when it is read): the rule's reading_read."""
    if not isinstance(payload, dict):
        return 'no answer'
    rank = payload['idea_rank'] if 'idea_rank' in payload else None
    if not isinstance(rank, list) or sorted(map(str, rank)) != sorted(lids) or len(rank) != len(lids):
        return 'idea_rank does not name each of the five lids once'
    rows = payload['pieces'] if 'pieces' in payload else None
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return 'no pieces'
    named = [row['label'] if 'label' in row else None for row in rows]
    answers = [row['carries_or_copies'] if 'carries_or_copies' in row else None for row in rows]
    if sorted(map(str, named)) != sorted(pieces) or len(named) != len(pieces):
        return 'pieces do not name each of the three pieces once'
    if not all(a in ('carries', 'copies') for a in answers):
        return 'a piece is not answered carries or copies'
    return ''


def verdict(readings, rule):
    """The verdict by the pre-registered rule from the three readers' payloads (``readings``: reader → payload or None).
    Returns the verdict ("improved", "mixed", "not improved" or "pending") and how each reader read."""
    labels = rule['labels']
    zilal = labels['zilal_master']['label']
    earlier = [row['label'] for row in labels['earlier_lids']]
    pieces = {row['piece']: row['label'] for row in labels['pieces']}
    lids = list(labels['lids'])
    per_reader, unread = {}, []
    for reader in READERS:
        payload = readings[reader] if reader in readings else None
        why = _read(payload, lids, list(pieces.values()))
        if why:
            per_reader[reader] = {'read': False, 'why': why}
            unread.append(reader)
            continue
        rank = [str(k) for k in payload['idea_rank']]
        above = all(rank.index(zilal) < rank.index(k) for k in earlier)
        answers = {str(row['label']): row['carries_or_copies'] for row in payload['pieces']}
        # the rule keys a piece by its label (the readers were told which label is which piece); a row whose piece
        # word differs from the label's is kept as a note, never used to re-key the answer
        otherwise = sorted(str(row['label']) for row in payload['pieces']
                           if 'piece' in row and (row['piece'] not in pieces or pieces[row['piece']] != str(row['label'])))
        per_reader[reader] = {'read': True, 'zilal_above_the_three': above, 'idea_rank': rank,
                              'copies': sorted(p for p, k in pieces.items() if answers[k] == 'copies'),
                              'piece_word_not_the_labels': otherwise}
    against = [r for r in READERS if per_reader[r]['read'] and not per_reader[r]['zilal_above_the_three']]
    copies = {p: sum(1 for r in READERS if per_reader[r]['read'] and p in per_reader[r]['copies']) for p in PIECES}
    copying = sorted(p for p, n in copies.items() if n >= 2)
    if against:
        word, lid_improved = 'not improved', False
    elif unread:
        word, lid_improved = 'pending', None
    else:
        lid_improved = True
        word = 'mixed' if len(copying) >= 2 else 'improved'
    return {'verdict': word, 'lid_improved': lid_improved, 'readers': per_reader, 'unread': unread,
            'ranked_the_zilal_master_below': against, 'copies_by_piece': copies, 'pieces_copying': copying}


# --- the requests -----------------------------------------------------------------------------------------------------

def _k_number(label):
    return int(label[1:])


def lid_labels(map_rec):
    return sorted((k for k, row in map_rec['labels'].items() if row['piece'] == 'lid'), key=_k_number)


def piece_label(map_rec, piece):
    found = [k for k, row in map_rec['labels'].items() if row['piece'] == piece]
    if len(found) != 1:
        raise ValueError('the map names %d labels for %s' % (len(found), piece))
    return found[0]


def _listed(labels):
    return ', '.join(labels[:-1]) + ' and ' + labels[-1]


def asked_text(map_rec):
    """The words both jurors and the eye read after the sheet: what the pictures are (the design, never the day) and
    the three questions."""
    names = {'lids': _listed(lid_labels(map_rec))}
    for piece in PIECES + ('family',):
        names[piece] = piece_label(map_rec, piece)
    return SHEET_WORDS.format(**names) + '\n\n' + QUESTIONS.format(**names)


def answer_schema(map_rec):
    """The one answer schema for all three readers: rankings, ten-word ideas, design or decoration, carries or copies
    and one collection; no number anywhere in it, no rubric field."""
    lid = {'type': 'string', 'enum': lid_labels(map_rec)}
    piece = {'type': 'string', 'enum': [piece_label(map_rec, p) for p in PIECES]}
    return {
        'type': 'object', 'additionalProperties': False,
        'required': ['idea_rank', 'counter_rank', 'lids', 'pieces', 'one_collection'],
        'properties': {
            'idea_rank': {'type': 'array', 'items': lid},
            'counter_rank': {'type': 'array', 'items': lid},
            'lids': {'type': 'array', 'items': {
                'type': 'object', 'additionalProperties': False,
                'required': ['label', 'idea_in_ten_words', 'design_or_decoration'],
                'properties': {'label': lid, 'idea_in_ten_words': {'type': 'string'},
                               'design_or_decoration': {'type': 'string', 'enum': ['design', 'decoration']}}}},
            'pieces': {'type': 'array', 'items': {
                'type': 'object', 'additionalProperties': False,
                'required': ['label', 'piece', 'source_lid', 'carries_or_copies', 'line'],
                'properties': {'label': piece, 'piece': {'type': 'string', 'enum': list(PIECES)},
                               'source_lid': lid,
                               'carries_or_copies': {'type': 'string', 'enum': ['carries', 'copies']},
                               'line': {'type': 'string'}}}},
            'one_collection': {
                'type': 'object', 'additionalProperties': False, 'required': ['answer', 'line'],
                'properties': {'answer': {'type': 'string', 'enum': ['yes', 'no']}, 'line': {'type': 'string'}}},
        }}


def _model():
    model = jury.jury_model()
    if model != MODEL:
        raise ValueError('the jury model is %s, not %s (§2c)' % (model, MODEL))
    return model


def _content(first, sheet, map_rec):
    block, sent = lm._image_block(sheet)
    return [{'type': 'text', 'text': first}, block, {'type': 'text', 'text': asked_text(map_rec)}], sent


def jury_kwargs(juror, map_rec, sheet):
    """One juror's ``messages.create`` arguments: the juror's role (jury.py's, no scale), the sheet as its own bytes,
    the questions; structured output, effort high; no ``system`` (that is the rubric's place, and it is not sent).
    Returns the arguments and what was sent (the sheet's path, sha256 and pixels)."""
    if juror not in ('J1', 'J2'):
        raise ValueError('the jurors are J1 and J2')
    content, sent = _content(jury._role(juror)['text'], sheet, map_rec)
    kwargs = {'model': _model(), 'max_tokens': MAX_TOKENS,
              'output_config': {'effort': EFFORT, 'format': {'type': 'json_schema', 'schema': answer_schema(map_rec)}},
              'messages': [{'role': 'user', 'content': content}]}
    return kwargs, sent


def eye_content(map_rec, sheet):
    """The eye's content for ``zilal_master.make_eye_call``'s ``call(EYE_OPERATION, content, schema)``: its own voice,
    the same sheet and the same words as the jurors."""
    return _content(EYE_VOICE, sheet, map_rec)


def eye_kwargs(map_rec, sheet):
    """The arguments ``zilal_master.make_eye_call`` sends (with its EYE_MAX_TOKENS set to MAX_TOKENS at runtime)."""
    content, sent = eye_content(map_rec, sheet)
    kwargs = {'model': _model(), 'max_tokens': MAX_TOKENS,
              'output_config': {'effort': EFFORT, 'format': {'type': 'json_schema', 'schema': answer_schema(map_rec)}},
              'messages': [{'role': 'user', 'content': content}]}
    return kwargs, sent


def redacted(kwargs):
    """The arguments with each image's bytes replaced by their sha256, size and length: what a commit can show."""
    import base64
    shown = copy.deepcopy(kwargs)
    for message in shown['messages']:
        for block in message['content']:
            if block['type'] == 'image':
                data = base64.b64decode(block['source']['data'])
                block['source'] = {'type': 'base64', 'media_type': block['source']['media_type'],
                                   'data_sha256': sha256_bytes(data), 'data_bytes': len(data)}
    return shown


def request_sha256(kwargs):
    return sha256_bytes(json.dumps(redacted(kwargs), sort_keys=True, ensure_ascii=False).encode('utf-8'))


def texts_of(kwargs):
    return [b['text'] for m in kwargs['messages'] for b in m['content'] if b['type'] == 'text']


def withheld_in(text):
    """The withheld words a text carries (WITHHELD), in order."""
    return [m.group(0) for m in WITHHELD.finditer(text)]


def worst_case_usd(kwargs):
    """The call's cost if every one of max_tokens is used: the image at (width × height) / 750 tokens, the text at 3
    bytes a token, at the ledger's tariff."""
    from apps.pipeline.services.cost_ledger import claude_cost_usd
    import base64
    tokens = 0
    for message in kwargs['messages']:
        for block in message['content']:
            if block['type'] == 'image':
                with Image.open(_bytes_io(base64.b64decode(block['source']['data']))) as im:
                    tokens += -(-im.size[0] * im.size[1] // IMAGE_PX_PER_TOKEN)
            else:
                tokens += -(-len(block['text'].encode('utf-8')) // TEXT_BYTES_PER_TOKEN)
    tokens += -(-len(json.dumps(kwargs['output_config']).encode('utf-8')) // TEXT_BYTES_PER_TOKEN)
    return round(float(claude_cost_usd(kwargs['model'], tokens, kwargs['max_tokens'])), 4)


def _bytes_io(data):
    import io
    return io.BytesIO(data)


# --- the paid calls (made by the runners only) ------------------------------------------------------------------------

def answer_fields(response, model):
    """A response's record fields, as ``jury._ask_j1`` returns them: the stop reason, the payload (None unless the turn
    ended and its text parsed), the parse error, the usage, its cost, the reservation and the response artifact."""
    text = ''.join(b.text for b in response.content if jury._attribute(b, 'type') == 'text')
    if response.stop_reason == 'end_turn':
        payload, parse_error = jury._parsed(text)
    else:
        payload, parse_error = None, ''
    usage = response.model_dump(mode='json')['usage']
    return {'stop_reason': response.stop_reason, 'parse_error': parse_error, 'payload': payload, 'usage': usage,
            'cost_usd': jury.cost_usd(model, usage), 'model': model,
            'reservation_id': jury._attribute(response, '_rescue_reservation_id'),
            'response_artifact': jury._attribute(response, '_rescue_response_artifact')}


def call_juror(juror, kwargs, *, client):
    """ONE paid juror call through the ledger (reserved before it is made, under the jury's prefix and cap), directly on
    ``messages.create`` with no system prompt. ``client``: the provider client (the Anthropic client when None)."""
    if 'system' in kwargs:
        raise ValueError('the creativity check sends no system prompt')
    create = jury._client().messages.create if client is None else client.messages.create
    response = paid_operation(create, provider='anthropic', operation=JURY_PREFIX + 'creativity/' + juror,
                              reservation_prefix=JURY_PREFIX, reservation_cap=JURY_CAP_USD, **kwargs)
    return answer_fields(response, kwargs['model'])


# --- the seal ---------------------------------------------------------------------------------------------------------

def committed_at(path):
    """git's commit time of the last commit touching ``path`` (ISO 8601 with its offset), or '' when none has."""
    done = subprocess.run(['git', 'log', '-1', '--format=%cI', '--', str(path)], cwd=REPO, capture_output=True,
                          text=True, check=True)
    return done.stdout.strip()


def uncommitted(paths):
    """The paths git sees changed or untracked (an empty list when every one is committed as it stands)."""
    done = subprocess.run(['git', 'status', '--porcelain', '--'] + [str(p) for p in paths], cwd=REPO,
                          capture_output=True, text=True, check=True)
    return [line for line in done.stdout.splitlines() if line.strip()]


def map_problems(map_rec, repo=REPO):
    """What does not hold between the map and the files: each tile and its record byte-equal to the map's sha256, the
    sheet's sha256 and size as recorded and inside the call's limits. An empty list when everything holds."""
    problems = []
    for label, row in map_rec['labels'].items():
        for key in ('file', 'tile'):
            path = Path(repo) / row[key]
            if not path.exists() or lm.sha256(path) != row['sha256']:
                problems.append('%s: %s is not the recorded bytes' % (label, row[key]))
    png = Path(repo) / map_rec['sheet']['png']
    if not png.exists() or lm.sha256(png) != map_rec['sheet']['png_sha256']:
        problems.append('the sheet is not the recorded bytes')
        return problems
    with Image.open(png) as im:
        w, h = im.size
    if [w, h] != map_rec['sheet']['px'] or max(w, h) != SHEET_LONG_PX or max(w, h) > lm.EYE_IMAGE_EDGE_MAX \
            or w * h > lm.EYE_PIXELS_MAX:
        problems.append('the sheet is %d × %d px' % (w, h))
    return problems


# --- the build (at $0) ------------------------------------------------------------------------------------------------

def build(out=OUT):
    """The tiles, the sheet and its PDF, map.json and the two requests, written once: refused when map.json is there (a
    second build would move its time and break the seal). Returns the map."""
    out = Path(out)
    if (out / 'map.json').exists():
        raise ValueError('map.json is written once: %s' % (out / 'map.json'))
    rows = records()
    labels, seed = labelled(rows)
    (out / 'tiles').mkdir(parents=True, exist_ok=True)
    entries, tiles = {}, []
    for label, row in labels:
        tile = out / 'tiles' / ('%s.png' % label)
        shutil.copyfile(REPO / row['file'], tile)
        if lm.sha256(tile) != row['sha256']:
            raise ValueError('%s is not a byte copy of %s' % (tile, row['file']))
        entries[label] = {'piece': row['piece'], 'file': row['file'], 'sha256': row['sha256'], 'bytes': row['bytes'],
                          'tile': rel(tile), 'px': row['px']}
        tiles.append((label, tile))
    png, pdf = out / 'sheet.png', out / 'sheet.pdf'
    plan = compose(tiles, png)
    page = write_pdf(png, pdf)
    if not pdf_pixels_equal(pdf, png):
        raise ValueError('the PDF does not hold the sheet\'s pixels')
    map_rec = {
        'schema': SCHEMA,
        'labels': entries,
        'order_listed_by_the_owner': [r['file'] for r in rows],
        'seed': {'rule': SEED_RULE, 'value': seed, 'positions': positions(seed, len(rows))},
        'sheet': {'png': rel(png), 'png_sha256': lm.sha256(png), 'pdf': rel(pdf), 'pdf_sha256': lm.sha256(pdf),
                  'px': plan['px'], 'tile_height_px': plan['h'],
                  'rows': [['K%d' % (i + 1) for i in row] for row in plan['rows']],
                  'boxes': {'K%d' % (i + 1): list(box) for i, box in enumerate(plan['boxes'])},
                  'tile_scale': {label: round(plan['h'] / row['px'][1], 4) for label, row in entries.items()},
                  'pdf_page': page, 'label_font': rel(LABEL_FONT), 'label_font_px': LABEL_FONT_PX},
        'verdict_rule': verdict_rule(labels),
        'written_at': now_utc(),
    }
    problems = map_problems(map_rec)
    if problems:
        raise ValueError('; '.join(problems))
    for juror in ('J1', 'J2'):                    # every request builds (the sheet inside the call's limits, the
        jury_kwargs(juror, map_rec, png)          # model the jury's) before map.json is written once
    eye_kwargs(map_rec, png)
    lm.write_json(out / 'map.json', map_rec)
    map_sha = lm.sha256(out / 'map.json')
    lm.write_json(out / 'jury-request.json', jury_request(map_rec, png, map_sha))
    lm.write_json(out / 'eye-request.json', eye_request(map_rec, png, map_sha))
    return map_rec


def jury_request(map_rec, sheet, map_sha):
    """jury-request.json: both jurors' exact requests (the image as its sha256), how they are paid and the lines."""
    jurors, worst, scanned = {}, {}, []
    for juror in ('J1', 'J2'):
        kwargs, sent = jury_kwargs(juror, map_rec, sheet)
        jurors[juror] = {'operation': JURY_PREFIX + 'creativity/' + juror, 'request': redacted(kwargs),
                         'request_sha256': request_sha256(kwargs), 'sent': sent}
        worst[juror] = worst_case_usd(kwargs)
        scanned += [w for t in texts_of(kwargs)[1:] for w in withheld_in(t)]
    return {'schema': 'day13_creativity_jury_request/1', 'written_at': now_utc(), 'map_sha256': map_sha,
            'sheet': {'png': map_rec['sheet']['png'], 'png_sha256': map_rec['sheet']['png_sha256'],
                      'px': map_rec['sheet']['px']},
            'call': ('spend_reservation.paid_operation(jury._client().messages.create, provider="anthropic", '
                     'operation=<the juror\'s>, reservation_prefix="%s", reservation_cap=%.2f, **request) — no system '
                     'prompt, no rubric, no anchors' % (JURY_PREFIX, JURY_CAP_USD)),
            'roles': 'jury.ROLE_J1 and jury.ROLE_J2 (jury._role), the jurors\' identities; no scale is sent',
            'guard': {'prefix': JURY_PREFIX, 'owner_line_usd': JURY_LINE_USD,
                      'worst_case_usd': worst, 'worst_case_both_usd': round(sum(worst.values()), 4)},
            'withheld_words_in_the_asked_text': scanned, 'jurors': jurors}


def eye_request(map_rec, sheet, map_sha):
    """eye-request.json: the eye's exact request as make_eye_call sends it (the image as its sha256) and its line."""
    kwargs, sent = eye_kwargs(map_rec, sheet)
    return {'schema': 'day13_creativity_eye_request/1', 'written_at': now_utc(), 'map_sha256': map_sha,
            'sheet': {'png': map_rec['sheet']['png'], 'png_sha256': map_rec['sheet']['png_sha256'],
                      'px': map_rec['sheet']['px']},
            'call': ('zilal_master.make_eye_call(cap_usd=%.2f, client=None) with zilal_master.EYE_PREFIX = "%s" and '
                     'zilal_master.EYE_MAX_TOKENS = %d set at runtime; call("%s", content, schema)'
                     % (EYE_CAP_USD, EYE_PREFIX, MAX_TOKENS, EYE_OPERATION)),
            'operation': EYE_PREFIX + EYE_OPERATION,
            'guard': {'prefix': EYE_GUARD_PREFIX, 'owner_line_usd': EYE_LINE_USD,
                      'worst_case_usd': worst_case_usd(kwargs)},
            'withheld_words_in_the_asked_text': [w for t in texts_of(kwargs) for w in withheld_in(t)],
            'request': redacted(kwargs), 'request_sha256': request_sha256(kwargs), 'sent': sent}
