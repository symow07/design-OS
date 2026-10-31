"""Day 13 §2b–d — the creativity check's sheet, map and the two calls' requests (D-D13-5, D-D13-7): the tiles are byte
copies of the owner's nine records, the sheet is 1536 px on its long side and inside the call's limits so the call sends
its own bytes, the shuffle re-derives from its rule, the verdict rule decides planted rankings as pre-registered, the
requests carry the sheet's bytes and no system prompt, rubric or score, and map.json was committed before the jury asked.
Nothing here pays: the call paths run on a fake client through the ledger the test isolates (conftest)."""
import base64
import hashlib
import json
import sqlite3
from datetime import datetime

import pytest
from django.conf import settings
from PIL import Image

from apps.pipeline.services import creativity_check as cc
from apps.pipeline.services import jury
from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import zilal_master as zm
from apps.pipeline.services import zilal_object as zo

MAP = cc.OUT / 'map.json'
built = pytest.mark.skipif(not MAP.exists(), reason='the creativity sheet is not built here')
JURY_RECORDS = [cc.OUT / 'jury' / 'J1.json', cc.OUT / 'jury' / 'J2.json']
EYE_RECORD = cc.OUT / 'eye.json'

#: the nine records' sha256 prefixes as transcribed at receipt (CURRENT_DECISIONS.md:310), an independent check
PREFIXES = {
    'docs/audit/day-8/concepts/B3-r2/truthful.png': '897a08796e5c30fa',
    'docs/audit/day-9/concepts/B-1.3-r1/truthful.png': '56ef3aa0d54639ac',
    'docs/audit/day-9/concepts/A-2.3-r1/truthful.png': 'ac82c04a70088cb3',
    'docs/audit/day-10/lid/lid-master-flat.png': '533c0f60f5cda442',
    'docs/audit/day-11/zilal/lid/lid-master-flat.png': '95783abe098c3f14',
    'docs/audit/day-12/lipstick/closed/lipstick-drawing.png': 'd8c9a88a0e935db5',
    'docs/audit/day-12/balm/master/balm-drawing.png': '000844ebdda62d96',
    'docs/audit/day-12/display/header/master/header-flat.png': 'd95dac761a8cdcc5',
    'docs/audit/day-12/display/family/family-sheet.png': 'dc32cf270883fa0e',
}
SIZES = {   # the nine records' pixels (read from the files on Day 13), for the layout's planted test
    'lid': (1536, 970), 'lid-master': (2245, 1418), 'lipstick': (932, 1294), 'balm': (908, 1172),
    'header': (3025, 1372), 'family': (2481, 1754)}


def _map():
    return json.loads(MAP.read_text(encoding='utf-8'))


def _planted_rows():
    """The nine records as rows with planted digests (no file read): the owner's order, the pieces, the names."""
    return [{'file': f, 'piece': p, 'name': n, 'sha256': hashlib.sha256(f.encode()).hexdigest(), 'bytes': 1,
             'px': [10, 10]} for f, p, n in cc.RECORDS]


def _planted_map(sheet):
    labels, seed = cc.labelled(_planted_rows())
    return {'labels': {k: {'piece': r['piece'], 'file': r['file'], 'sha256': r['sha256']} for k, r in labels},
            'sheet': {'png': str(sheet)}, 'verdict_rule': cc.verdict_rule(labels)}


def _walk_keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_keys(v)


def _items(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k, v
            yield from _items(v)
    elif isinstance(node, list):
        for v in node:
            yield from _items(v)


# --- the shuffle and the layout (planted) -----------------------------------------------------------------------------

def test_the_shuffle_rederives_from_its_rule():
    rows = _planted_rows()
    digests = [r['sha256'] for r in rows]
    seed = cc.seed_of(digests)
    assert seed == hashlib.sha256(''.join(digests).encode('ascii')).hexdigest()
    order = cc.positions(seed, 9)
    assert sorted(order) == list(range(9)) and order == cc.positions(seed, 9)
    labels, again = cc.labelled(rows)
    assert again == seed
    assert [k for k, _ in labels] == ['K%d' % n for n in range(1, 10)]
    assert [r['file'] for _, r in labels] == [rows[i]['file'] for i in order]
    # a different digest deals differently: the seed is the records' own
    rows[0]['sha256'] = '0' * 64
    assert cc.labelled(rows)[1] != seed


def test_the_layout_keeps_one_height_k_order_and_the_calls_limits():
    sizes = [SIZES['lid']] * 3 + [SIZES['lid-master']] * 2 + [SIZES['lipstick'], SIZES['balm'], SIZES['header'],
                                                               SIZES['family']]
    plan = cc.layout(sizes)
    w, h = plan['px']
    assert w == cc.SHEET_LONG_PX and h <= w
    assert w * h <= lm.EYE_PIXELS_MAX and max(w, h) <= lm.EYE_IMAGE_EDGE_MAX
    assert {box[3] for box in plan['boxes']} == {plan['h']}
    # in K order: left to right in each row, rows top to bottom, every box inside the margins
    flat = [i for row in plan['rows'] for i in row]
    assert flat == list(range(9))
    for row in plan['rows']:
        xs = [plan['boxes'][i][0] for i in row]
        assert xs == sorted(xs) and len({plan['boxes'][i][1] for i in row}) == 1
    for x, y, bw, bh in plan['boxes']:
        assert x >= cc.MARGIN_PX and x + bw <= w - cc.MARGIN_PX and y >= cc.MARGIN_PX
        assert y + bh + cc.LABEL_BAND_PX <= h - cc.MARGIN_PX
    for (x, y, bw, bh), i in zip(plan['boxes'], range(9)):        # each tile keeps its record's proportions
        assert abs(bw / bh - sizes[i][0] / sizes[i][1]) < 0.01


# --- the built sheet and map --------------------------------------------------------------------------------------------

@built
def test_the_tiles_are_byte_copies_of_their_records():
    m = _map()
    assert m['schema'] == cc.SCHEMA
    assert sorted(m['labels'], key=lambda k: int(k[1:])) == ['K%d' % n for n in range(1, 10)]
    assert sorted(row['file'] for row in m['labels'].values()) == sorted(PREFIXES)
    for label, row in m['labels'].items():
        record, tile = (cc.REPO / row['file']).read_bytes(), (cc.REPO / row['tile']).read_bytes()
        assert tile == record, label
        assert hashlib.sha256(tile).hexdigest() == row['sha256'] and row['sha256'].startswith(PREFIXES[row['file']])
        assert len(tile) == row['bytes'] and row['tile'] == 'docs/audit/day-13/creativity/tiles/%s.png' % label
        with Image.open(cc.REPO / row['tile']) as im:
            assert list(im.size) == row['px']
    assert cc.map_problems(m) == []


@built
def test_the_map_rederives_its_labels_from_the_records():
    m = _map()
    assert m['order_listed_by_the_owner'] == [f for f, _, _ in cc.RECORDS]
    digests = [hashlib.sha256((cc.REPO / f).read_bytes()).hexdigest() for f in m['order_listed_by_the_owner']]
    assert m['seed']['value'] == cc.seed_of(digests)
    order = cc.positions(m['seed']['value'], 9)
    assert m['seed']['positions'] == order
    assert [m['labels']['K%d' % (n + 1)]['file'] for n in range(9)] == [m['order_listed_by_the_owner'][i] for i in order]


@built
def test_the_sheet_is_1536_on_its_long_side_inside_the_limits_and_sent_as_its_own_bytes(tmp_path):
    m = _map()
    png = cc.REPO / m['sheet']['png']
    data = png.read_bytes()
    assert hashlib.sha256(data).hexdigest() == m['sheet']['png_sha256']
    with Image.open(png) as im:
        w, h = im.size
        assert im.mode == 'RGB' and not im.text                      # no text chunk
    assert [w, h] == m['sheet']['px'] and max(w, h) == 1536
    assert w * h <= 1_150_000 and max(w, h) <= 1568
    block, sent = lm._image_block(png)                                # the call's image block: the sheet's own bytes
    assert base64.b64decode(block['source']['data']) == data and sent['sha256'] == m['sheet']['png_sha256']
    assert lm.sha256(zo.fitted(png, tmp_path / 'refit.png')) == m['sheet']['png_sha256']
    assert cc.pdf_pixels_equal(cc.REPO / m['sheet']['pdf'], png)


@built
def test_the_committed_requests_are_what_the_builders_send():
    m = _map()
    png = cc.REPO / m['sheet']['png']
    map_sha = lm.sha256(MAP)
    asked = json.loads((cc.OUT / 'jury-request.json').read_text(encoding='utf-8'))
    assert asked['map_sha256'] == map_sha and asked['sheet']['png_sha256'] == m['sheet']['png_sha256']
    for juror in ('J1', 'J2'):
        kwargs, sent = cc.jury_kwargs(juror, m, png)
        assert cc.request_sha256(kwargs) == asked['jurors'][juror]['request_sha256']
        assert asked['jurors'][juror]['request'] == json.loads(json.dumps(cc.redacted(kwargs), ensure_ascii=False))
    assert asked['guard']['worst_case_both_usd'] <= cc.JURY_LINE_USD
    eye = json.loads((cc.OUT / 'eye-request.json').read_text(encoding='utf-8'))
    kwargs, _ = cc.eye_kwargs(m, png)
    assert eye['map_sha256'] == map_sha and cc.request_sha256(kwargs) == eye['request_sha256']
    assert eye['guard']['worst_case_usd'] <= cc.EYE_LINE_USD
    assert asked['withheld_words_in_the_asked_text'] == [] and eye['withheld_words_in_the_asked_text'] == []


# --- the requests (planted sheet) ---------------------------------------------------------------------------------------

@pytest.fixture
def planted(tmp_path, monkeypatch):
    sheet = tmp_path / 'sheet.png'
    Image.new('RGB', (640, 220), (255, 255, 255)).save(sheet)
    monkeypatch.setattr(lm, 'rel', str)                              # the planted sheet lies outside the repository
    return sheet, _planted_map(sheet)


def test_the_requests_send_the_sheets_bytes_and_no_system_prompt_rubric_or_score(planted):
    sheet, m = planted
    data = sheet.read_bytes()
    texts = []
    for juror in ('J1', 'J2'):
        kwargs, sent = cc.jury_kwargs(juror, m, sheet)
        assert 'system' not in kwargs
        assert kwargs['model'] == 'claude-opus-5-5' == jury.jury_model()
        assert kwargs['output_config']['effort'] == 'high' and kwargs['output_config']['format']['type'] == 'json_schema'
        content = kwargs['messages'][0]['content']
        assert [b['type'] for b in content] == ['text', 'image', 'text']
        assert base64.b64decode(content[1]['source']['data']) == data and sent['sha256'] == lm.sha256(sheet)
        # the juror's identity is jury.py's own role, never the Day 9 audience role or any rubric text
        assert content[0]['text'] == 'YOUR ROLE. ' + (jury.ROLE_J1 if juror == 'J1' else jury.ROLE_J2)
        assert all(r not in json.dumps(kwargs, ensure_ascii=False) for r in jury.RUBRICS.values())
        texts.append(content[2]['text'])
        schema = kwargs['output_config']['format']['schema']
        keys = [k.lower() for k in _walk_keys(schema)]
        assert not [k for k in keys if 'score' in k or 'rubric' in k or 'verdict' in k or 'pass' in k]
        assert not {'number', 'integer'} & {v for k, v in _items(schema) if k == 'type' and isinstance(v, str)}
        assert schema == cc.answer_schema(m)
    assert texts[0] == texts[1]
    # nothing in the asked words names a day, round, score, authorship or the collection
    assert cc.withheld_in(texts[0]) == []
    lids = cc.lid_labels(m)
    for label in lids + [cc.piece_label(m, p) for p in ('lipstick', 'balm', 'header', 'family')]:
        assert label in texts[0]
    # the eye: its own voice, the same sheet, the same words and the same schema
    eye, sent = cc.eye_kwargs(m, sheet)
    content = eye['messages'][0]['content']
    assert 'system' not in eye and content[0]['text'] == cc.EYE_VOICE and cc.withheld_in(cc.EYE_VOICE) == []
    assert base64.b64decode(content[1]['source']['data']) == data and content[2]['text'] == texts[0]
    assert eye['output_config'] == kwargs['output_config'] and eye['max_tokens'] == kwargs['max_tokens']


def test_a_planted_withheld_word_is_found():
    assert cc.withheld_in('the Day 8 build scored 6.65 by the jury') == ['Day', 'build', 'scored', 'jury']
    assert cc.withheld_in('ظلال on the lid') == ['ظلال']
    assert cc.withheld_in('five different lids, a counter display and its ground') == []


class _Block:
    def __init__(self, text):
        self.type, self.text = 'text', text


class _Response:
    def __init__(self, text):
        self.content, self.stop_reason, self.text = [_Block(text)], 'end_turn', text

    def model_dump(self, mode):
        return {'content': [{'type': 'text', 'text': self.text}], 'stop_reason': self.stop_reason,
                'usage': {'input_tokens': 1800, 'output_tokens': 900}}


class _Client:
    def __init__(self, answer):
        self.sent, self.answer, self.messages = [], answer, self

    def create(self, **kwargs):
        self.sent.append(kwargs)
        return _Response(json.dumps(self.answer))


def _answer(m, rank=None, copies=()):
    lids = cc.lid_labels(m)
    return {'idea_rank': rank or lids, 'counter_rank': lids,
            'lids': [{'label': k, 'idea_in_ten_words': 'an idea', 'design_or_decoration': 'design'} for k in lids],
            'pieces': [{'label': cc.piece_label(m, p), 'piece': p, 'source_lid': lids[0],
                        'carries_or_copies': 'copies' if p in copies else 'carries', 'line': 'a line'}
                       for p in cc.PIECES],
            'one_collection': {'answer': 'yes', 'line': 'a line'}}


def _ledger_operations():
    with sqlite3.connect(settings.RESCUE_SPEND_ROOT / 'ledger.sqlite3') as db:
        return [tuple(r) for r in db.execute('SELECT operation, state FROM calls')]


def test_the_jury_call_sends_the_built_request_through_the_ledger(planted):
    """The juror's call on a fake client through the real ledger path (isolated to this test's folder by conftest)."""
    sheet, m = planted
    kwargs, _ = cc.jury_kwargs('J1', m, sheet)
    client = _Client(_answer(m))
    fields = cc.call_juror('J1', kwargs, client=client)
    assert client.sent == [kwargs] and 'system' not in client.sent[0]
    assert fields['stop_reason'] == 'end_turn' and fields['payload'] == _answer(m) and fields['parse_error'] == ''
    assert fields['cost_usd'] == jury.cost_usd('claude-opus-5-5', {'input_tokens': 1800, 'output_tokens': 900})
    assert fields['reservation_id'] and fields['response_artifact']
    assert _ledger_operations() == [('day13/jury/creativity/J1', 'usage_recorded')]
    with pytest.raises(ValueError, match='system'):
        cc.call_juror('J2', dict(kwargs, system='a rubric'), client=client)


def test_the_eye_call_through_make_eye_call_sends_the_built_request(planted, monkeypatch):
    sheet, m = planted
    monkeypatch.setattr(zm, 'EYE_PREFIX', cc.EYE_PREFIX)
    monkeypatch.setattr(zm, 'EYE_MAX_TOKENS', cc.MAX_TOKENS)
    content, _ = cc.eye_content(m, sheet)
    kwargs, _ = cc.eye_kwargs(m, sheet)
    client = _Client(_answer(m))
    look = zm.make_eye_call(cap_usd=cc.EYE_CAP_USD, client=client)(
        cc.EYE_OPERATION, content, kwargs['output_config']['format']['schema'])
    assert client.sent == [kwargs]
    assert look['payload'] == _answer(m) and look['model'] == 'claude-opus-5-5'
    assert _ledger_operations() == [('day13/designer-eye/creativity/sheet', 'usage_recorded')]
    assert ('day13/designer-eye/creativity/sheet').startswith(cc.EYE_GUARD_PREFIX)


# --- the verdict rule (planted rankings) --------------------------------------------------------------------------------

def _rule_and_labels():
    m = _planted_map('sheet.png')
    return m, m['verdict_rule'], {row['name']: k for k, row in cc.labelled(_planted_rows())[0]}


def test_the_verdict_rule_decides_planted_rankings_as_pre_registered():
    m, rule, k = _rule_and_labels()
    assert rule['labels']['zilal_master']['label'] == k['zilal']
    assert [r['label'] for r in rule['labels']['earlier_lids']] == [k['B3-r2'], k['B-1.3-r1'], k['A-2.3-r1']]
    assert sorted(rule['labels']['lids']) == sorted([k['B3-r2'], k['B-1.3-r1'], k['A-2.3-r1'], k['golden-hour'],
                                                     k['zilal']])
    first = [k['zilal'], k['golden-hour'], k['B-1.3-r1'], k['A-2.3-r1'], k['B3-r2']]
    # the Golden Hour lid's place is not read: the Ẓilāl master second behind it, above the three, still improves
    behind_gh = [k['golden-hour'], k['zilal'], k['B3-r2'], k['B-1.3-r1'], k['A-2.3-r1']]
    below = [k['B-1.3-r1'], k['zilal'], k['golden-hour'], k['A-2.3-r1'], k['B3-r2']]

    def judge(j1, j2, eye):
        return cc.verdict({'J1': j1, 'J2': j2, 'eye': eye}, rule)

    improved = judge(_answer(m, first), _answer(m, behind_gh), _answer(m, first))
    assert improved['verdict'] == 'improved' and improved['lid_improved'] is True
    # one piece copied by two readers: still improved (fewer than two pieces copy)
    one = judge(_answer(m, first, ['lipstick']), _answer(m, first, ['lipstick']), _answer(m, first))
    assert one['verdict'] == 'improved' and one['pieces_copying'] == ['lipstick']
    # two pieces each copied by two readers: mixed; three readers on three pieces: mixed
    mixed = judge(_answer(m, first, ['lipstick', 'balm']), _answer(m, first, ['balm']), _answer(m, first, ['lipstick']))
    assert mixed['verdict'] == 'mixed' and mixed['pieces_copying'] == ['balm', 'lipstick']
    assert judge(*[_answer(m, first, cc.PIECES)] * 3)['verdict'] == 'mixed'
    # a piece one reader says copies is not a copying piece
    spread = judge(_answer(m, first, ['lipstick']), _answer(m, first, ['balm']), _answer(m, first, ['header']))
    assert spread['verdict'] == 'improved' and spread['copies_by_piece'] == {'lipstick': 1, 'balm': 1, 'header': 1}
    # one reader ranking the Ẓilāl master below an earlier lid: not improved, whatever the pieces
    assert judge(_answer(m, first), _answer(m, below), _answer(m, first))['verdict'] == 'not improved'
    assert judge(_answer(m, below, cc.PIECES), _answer(m, first), _answer(m, first))['verdict'] == 'not improved'
    # an unread answer leaves it pending, unless a read one already decides "not improved"
    pending = judge(_answer(m, first), _answer(m, first), None)
    assert pending['verdict'] == 'pending' and pending['lid_improved'] is None and pending['unread'] == ['eye']
    assert judge(_answer(m, below), _answer(m, first), None)['verdict'] == 'not improved'
    short = _answer(m, first[:4])                                     # a ranking that drops a lid is unread
    assert judge(short, _answer(m, first), _answer(m, first))['verdict'] == 'pending'
    twice = _answer(m, first)
    twice['pieces'] = twice['pieces'][:2] + twice['pieces'][:1]       # a piece answered twice, one missing: unread
    assert judge(twice, _answer(m, first), _answer(m, first))['readers']['J1']['read'] is False


# --- the seal: map.json committed before the jury asked ------------------------------------------------------------------

@pytest.mark.skipif(not all(p.exists() for p in JURY_RECORDS), reason='the jury has not answered yet')
def test_map_json_was_committed_before_the_jury_asked():
    committed = cc.committed_at(MAP)
    assert committed, 'the jury records exist but map.json was never committed'
    committed_at = datetime.fromisoformat(committed)
    map_sha = lm.sha256(MAP)
    records = [json.loads(p.read_text(encoding='utf-8')) for p in JURY_RECORDS]
    if EYE_RECORD.exists():
        records.append(json.loads(EYE_RECORD.read_text(encoding='utf-8')))
    for rec in records:
        assert committed_at < datetime.fromisoformat(rec['asked_at'])
        assert rec['sent']['map_sha256'] == map_sha
        assert rec['sent']['sheet']['sha256'] == _map()['sheet']['png_sha256']
    log = [json.loads(line) for line in (cc.OUT / 'calls.jsonl').read_text(encoding='utf-8').splitlines()]
    asked = [line for line in log if line['event'] == 'asked']
    assert asked and all(line['sheet_sha256'] == _map()['sheet']['png_sha256'] for line in asked)
    assert all(committed_at < datetime.fromisoformat(line['time']) for line in asked)
