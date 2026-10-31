"""Day 13 §2e — the creativity check's page (apps/dashboard/day13_views.py, apps/pipeline/services/day13_creativity_page.py).

Built against a planted map and planted tiles in a temporary folder, laid out as the sheet builder lays out the real ones
(docs/audit/day-13/creativity/: map.json, sheet.png, tiles/K1.png … K9.png), with the nine record paths of the prompt's
§2b in the map so that the sealed page is scanned for every one of them. The page answers a member; nothing of the map
reaches the HTML until the owner's ranking is written and verifies; the files door serves the tile bytes under their K
names and refuses a changed byte; the ranking is the owner's alone, shown before it is written, written once and never
overwritten; and the page says plainly when the sheet is not ready (never a 500)."""
import hashlib
import html as markup
import io
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.conf import settings as django_settings
from django.test import Client
from PIL import Image

from apps.pipeline.services import day13_creativity_page as cp

#: the nine record files of the prompt's §2b, in its order, and their pieces
RECORDS = ('docs/audit/day-8/concepts/B3-r2/truthful.png', 'docs/audit/day-9/concepts/B-1.3-r1/truthful.png',
           'docs/audit/day-9/concepts/A-2.3-r1/truthful.png', 'docs/audit/day-10/lid/lid-master-flat.png',
           'docs/audit/day-11/zilal/lid/lid-master-flat.png', 'docs/audit/day-12/lipstick/closed/lipstick-drawing.png',
           'docs/audit/day-12/balm/master/balm-drawing.png', 'docs/audit/day-12/display/header/master/header-flat.png',
           'docs/audit/day-12/display/family/family-sheet.png')
PIECES = ('lid',) * 5 + ('lipstick', 'balm', 'header', 'family')
SHUFFLE = (6, 2, 9, 4, 1, 8, 3, 7, 5)          # a planted shuffle: the i-th record is K<SHUFFLE[i]>
#: what the HTML must not carry while the map is sealed (every record path is scanned for too)
SEALED_WORDS = ('day-', 'B3', 'B-1.3', 'A-2.3', 'r1', 'Golden', 'concepts', 'Day ')
OWNER, MEMBER = 'house-owner', 'house-member'
PAGE, RANKING = '/dashboard/creativity/', '/dashboard/creativity/ranking/'
WORDS = 'K4 first, the idea is its own\r\nK9 second\r\nthe rest after'
#: a CSRF token is 64 random letters and digits and may hold "r1" or "B3" by chance: its value is not scanned
_TOKEN = re.compile(r'name="csrfmiddlewaretoken" value="[^"]*"')


def _png(colour, size) -> bytes:
    out = io.BytesIO()
    Image.new('RGB', size, colour).save(out, 'PNG')
    return out.getvalue()


def _sha(data) -> str:
    return hashlib.sha256(data).hexdigest()


def _leaks(html) -> list:
    """Every sealed word or record path the page carries, read both as sent and with its entities unescaped."""
    html = _TOKEN.sub('', html)
    return [word for word in SEALED_WORDS + RECORDS if word in html or word in markup.unescape(html)]


def _door(label) -> str:
    return '/dashboard/creativity/files/%s/' % label


@pytest.fixture
def planted(tmp_path, monkeypatch, settings):
    repo = tmp_path / 'repo'
    folder = repo / 'docs' / 'audit' / 'day-13' / 'creativity'
    (folder / 'tiles').mkdir(parents=True)
    labels, tiles = {}, {}
    for i, (record, piece) in enumerate(zip(RECORDS, PIECES)):
        data = _png((25 * i, 70, 140), (40 + i, 30))
        label = 'K%d' % SHUFFLE[i]
        tile = 'docs/audit/day-13/creativity/tiles/%s.png' % label
        (repo / tile).write_bytes(data)
        (repo / record).parent.mkdir(parents=True, exist_ok=True)
        (repo / record).write_bytes(data)                       # the record, byte-equal to its tile
        labels[label] = {'piece': piece, 'file': record, 'sha256': _sha(data), 'bytes': len(data), 'tile': tile,
                         'px': [40 + i, 30]}
        tiles[label] = data
    sheet = _png((230, 220, 210), (96, 60))
    (folder / 'sheet.png').write_bytes(sheet)
    record = {'schema': cp.MAP_SCHEMA, 'labels': labels, 'order_listed_by_the_owner': list(RECORDS),
              'seed': {'rule': 'planted for the test', 'value': '5eed' * 4},
              'sheet': {'png': 'docs/audit/day-13/creativity/sheet.png', 'png_sha256': _sha(sheet),
                        'pdf': 'docs/audit/day-13/creativity/sheet.pdf', 'px': [96, 60]},
              'verdict_rule': {'improved': 'the planted master ranks above the planted three',
                               'readers': ['J1', 'J2', 'eye'], 'labels': {'lids': ['K1', 'K2']},
                               'function': 'apps.pipeline.services.creativity_check.verdict'},
              'written_at': '2026-10-24T16:00:00+00:00'}
    (folder / 'map.json').write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(cp, 'REPO', repo)
    monkeypatch.setattr(cp, 'CREATIVITY', folder)
    monkeypatch.setattr(cp, 'MAP', folder / 'map.json')
    monkeypatch.setattr(cp, 'STORE', tmp_path / 'var' / 'day13' / 'creativity-owner-ranking.json')
    settings.OWNER_ACCOUNT = OWNER
    return SimpleNamespace(repo=repo, folder=folder, map=folder / 'map.json', tiles=tiles, sheet=sheet, record=record)


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_superuser(OWNER, 'owner@example.com', 'x')


@pytest.fixture
def member(django_user_model):
    return django_user_model.objects.create_superuser(MEMBER, 'member@example.com', 'x')


# --- the service, without the database --------------------------------------------------------------------------------

def test_state_never_raises_and_names_no_path(planted):
    """A map that is not JSON, or not in shape, is said in plain words that name no path; until the ranking opens the
    map, only the K names (and the map's own hash) leave the state."""
    said = cp.state()
    assert said['state'] == cp.READY and said['seal'] == cp.SEALED
    assert set(said) == {'state', 'labels', 'map_sha256', 'seal'} and said['labels'] == cp.LABELS
    planted.map.write_text('{not json', encoding='utf-8')
    said = cp.state()
    assert said['state'] == cp.UNREADABLE and 'day-' not in said['why']
    broken = dict(planted.record, labels={k: v for k, v in planted.record['labels'].items() if k != 'K5'})
    planted.map.write_text(json.dumps(broken), encoding='utf-8')
    said = cp.state()
    assert said['state'] == cp.UNREADABLE and 'exactly K1 to K9' in said['why']
    planted.map.unlink()
    assert cp.state() == {'state': cp.NOT_READY}


def test_the_ranking_store_is_beside_the_site_and_ignored_by_git():
    """The running site never writes into docs/: the store is under the Django root's var/, which git ignores."""
    base = Path(django_settings.BASE_DIR).resolve()
    store = cp.STORE.resolve()
    assert store.is_relative_to(base / 'var') and not store.is_relative_to(cp.REPO.resolve() / 'docs')
    ignored = subprocess.run(['git', '-C', str(base), 'check-ignore', '-q', str(store)])
    assert ignored.returncode == 0


def test_a_ranking_is_written_once_and_never_overwritten(planted):
    words, sha256 = cp.prepared(WORDS)
    assert words == WORDS.replace('\r\n', '\n') and sha256 == cp.words_sha256(words)
    with pytest.raises(cp.Refused, match='not the words whose hash'):
        cp.write(OWNER, WORDS, '0' * 64)
    assert not cp.STORE.exists()
    written = cp.write(OWNER, WORDS, sha256)
    first = cp.STORE.read_bytes()
    with pytest.raises(cp.AlreadyWritten):
        cp.write(OWNER, 'other words', cp.words_sha256('other words'))
    assert cp.STORE.read_bytes() == first and json.loads(first) == written
    assert [p.name for p in cp.STORE.parent.iterdir()] == [cp.STORE.name]      # no temporary file left behind


# --- the page ---------------------------------------------------------------------------------------------------------

@pytest.mark.django_db
def test_the_page_says_the_sheet_is_not_ready_without_a_map(client, planted, owner):
    planted.map.unlink()
    client.force_login(owner)
    page = client.get(PAGE)
    html = page.content.decode()
    assert page.status_code == 200 and 'The sheet is not ready yet' in html
    assert 'name="ranking"' not in html and 'style=' not in html
    assert client.get(_door('K1')).status_code == 404 and client.get(_door('sheet')).status_code == 404


@pytest.mark.django_db
def test_the_page_shows_the_sheet_and_the_nine_files_with_the_map_sealed(client, planted, owner, member):
    client.force_login(member)
    page = client.get(PAGE)
    html = page.content.decode()
    assert page.status_code == 200
    assert all(_door(label) in html for label in cp.LABELS + (cp.SHEET,))
    assert 'The map is sealed' in html and _leaks(html) == [] and 'style=' not in html
    assert "Only the owner's account writes the ranking here" in html and 'name="ranking"' not in html
    client.force_login(owner)
    html = client.get(PAGE).content.decode()
    assert 'name="ranking"' in html and _leaks(html) == [] and 'style=' not in html
    client.logout()
    assert client.get(PAGE).status_code == 302                  # signed out: to the sign-in page


@pytest.mark.django_db
def test_the_door_serves_each_file_under_its_label_and_refuses_a_changed_byte(client, planted, member):
    client.force_login(member)
    for label, data in list(planted.tiles.items()) + [(cp.SHEET, planted.sheet)]:
        answer = client.get(_door(label))
        assert answer.status_code == 200 and answer['Content-Type'] == 'image/png'
        assert b''.join(answer.streaming_content) == data
        said = answer['Content-Disposition']
        assert '%s.png' % label in said and 'day-' not in said and 'tiles' not in said
    for nothing in ('map', 'K10', 'K0', 'sheet-pdf'):
        assert client.get(_door(nothing)).status_code == 404
    tile = planted.folder / 'tiles' / 'K3.png'
    changed = bytearray(tile.read_bytes())
    changed[-1] ^= 1
    tile.write_bytes(bytes(changed))
    assert client.get(_door('K3')).status_code == 404
    answer = client.get(_door('K4'))
    # reading a streamed answer to its end closes it as the test client does (a bare close() here would fire
    # request_finished and close the test's database connection)
    assert answer.status_code == 200 and b''.join(answer.streaming_content) == planted.tiles['K4']
    html = client.get(PAGE).content.decode()
    assert 'K3 is not the file the sheet was made from' in html and _leaks(html) == [] and 'style=' not in html


@pytest.mark.django_db
def test_a_file_outside_the_sheets_folder_is_never_served(client, planted, member):
    """A map entry that points at a record file (its hash right) is refused: the door serves the sheet's folder only."""
    moved = json.loads(planted.map.read_text(encoding='utf-8'))
    moved['labels']['K1']['tile'] = moved['labels']['K1']['file']
    planted.map.write_text(json.dumps(moved), encoding='utf-8')
    client.force_login(member)
    assert client.get(_door('K1')).status_code == 404
    html = client.get(PAGE).content.decode()
    assert "K1 is not a picture in the sheet's own folder" in markup.unescape(html) and _leaks(html) == []


@pytest.mark.django_db
def test_only_the_owner_writes_the_ranking(client, planted, member):
    client.force_login(member)
    answer = client.post(RANKING, {'ranking': WORDS, 'confirm': 'yes', 'sha256': cp.words_sha256(cp.normalised(WORDS))})
    assert answer.status_code == 403 and "Only the owner's account" in answer.content.decode()
    assert not cp.STORE.exists()
    assert client.get(RANKING).status_code == 405


@pytest.mark.django_db
def test_the_ranking_is_shown_then_written_once_and_the_map_opens(client, planted, owner):
    client.force_login(owner)
    words = cp.normalised(WORDS)
    shown = client.post(RANKING, {'ranking': WORDS})
    html = shown.content.decode()
    assert shown.status_code == 200 and cp.words_sha256(words) in html and 'K9 second' in html
    assert not cp.STORE.exists() and _leaks(html) == [] and 'The map is sealed' in html
    written = client.post(RANKING, {'ranking': words, 'confirm': 'yes', 'sha256': cp.words_sha256(words)})
    assert written.status_code == 302 and written['Location'] == PAGE + '#map'
    stored = json.loads(cp.STORE.read_text(encoding='utf-8'))
    assert stored['text'] == words and stored['sha256'] == cp.words_sha256(words) and stored['user'] == OWNER
    assert stored['map_sha256'] == _sha(planted.map.read_bytes()) and datetime.fromisoformat(stored['at']).tzinfo
    first = cp.STORE.read_bytes()
    html = client.get(PAGE).content.decode()
    assert all(record in html for record in RECORDS) and 'Day 8' in html and 'Day 12' in html
    assert 'the planted master ranks above the planted three' in html and 'K9 second' in html
    assert 'J1; J2; eye' in html and 'lids: K1; K2' in html and 'apps.pipeline' not in html    # words, not code
    assert html.count('<td>yes</td>') == len(cp.LABELS) and 'style=' not in html
    again = client.post(RANKING, {'ranking': 'other words', 'confirm': 'yes', 'sha256': cp.words_sha256('other words')})
    assert again.status_code == 409 and 'already written' in again.content.decode()
    assert client.post(RANKING, {'ranking': 'other words'}).status_code == 409
    assert cp.STORE.read_bytes() == first


@pytest.mark.django_db
def test_words_that_are_not_the_shown_ones_or_blank_write_nothing(client, planted, owner):
    client.force_login(owner)
    answer = client.post(RANKING, {'ranking': WORDS, 'confirm': 'yes', 'sha256': '0' * 64})
    assert answer.status_code == 400 and 'Nothing was written' in answer.content.decode()
    assert client.post(RANKING, {'ranking': '   '}).status_code == 400
    assert client.post(RANKING, {}).status_code == 400
    assert not cp.STORE.exists()


@pytest.mark.django_db
def test_a_ranking_before_the_sheet_is_ready_writes_nothing(client, planted, owner):
    planted.map.unlink()
    client.force_login(owner)
    words = cp.normalised(WORDS)
    answer = client.post(RANKING, {'ranking': words, 'confirm': 'yes', 'sha256': cp.words_sha256(words)})
    assert answer.status_code == 409 and 'not ready' in answer.content.decode()
    assert not cp.STORE.exists()


@pytest.mark.django_db
def test_a_stored_ranking_that_does_not_verify_keeps_the_map_sealed(client, planted, owner):
    words = cp.normalised(WORDS)
    cp.write(OWNER, words, cp.words_sha256(words))
    good = cp.STORE.read_text(encoding='utf-8')
    client.force_login(owner)
    for broken, said in ((dict(json.loads(good), text=words + ' (changed)'), 'no longer match the hash'),
                         (dict(json.loads(good), user=MEMBER), "not written by the owner's account")):
        cp.STORE.write_text(json.dumps(broken), encoding='utf-8')
        html = client.get(PAGE).content.decode()
        assert said in markup.unescape(html) and _leaks(html) == []
    cp.STORE.write_text(good, encoding='utf-8')
    planted.map.write_text(json.dumps(dict(planted.record, written_at='2026-10-24T17:00:00+00:00')), encoding='utf-8')
    html = client.get(PAGE).content.decode()
    assert 'the map has changed since your ranking was written' in html and _leaks(html) == []


@pytest.mark.django_db
def test_the_form_carries_its_csrf_token_and_a_post_without_it_is_refused(planted, owner):
    client = Client(enforce_csrf_checks=True)
    client.force_login(owner)
    assert 'csrfmiddlewaretoken' in client.get(PAGE).content.decode()
    words = cp.normalised(WORDS)
    answer = client.post(RANKING, {'ranking': words, 'confirm': 'yes', 'sha256': cp.words_sha256(words)})
    assert answer.status_code == 403 and not cp.STORE.exists()
