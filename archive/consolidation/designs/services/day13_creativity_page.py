"""Day 13 §2e — the creativity check's page: the sheet and its nine files under their K names only, a text field for the
owner's own ranking, and the map sealed on the page until he has written his ("the map stays sealed on the page until I
have written mine").

The map (``docs/audit/day-13/creativity/map.json``, schema ``day13_creativity_map/1``, written by the sheet builder) is
read here and never served: it names each K's record file, its piece and so its day. Its sha256 per label, and the
sheet's, are the door's pins — ``checked_file`` serves a tile or the sheet only from the creativity folder, only while
its bytes are the ones the map pins (re-hashed on every request), and under its label's name, never the record's (the
record path names the day). ``state`` never raises, so the page always shows: until the owner's ranking opens the map it
hands the page the K names and nothing else of it, and every reason it gives names a label, never a path.

The owner's ranking is written ONCE, beside the running site (``var/day13/``, git-ignored; the site never writes into
docs/): his words, their sha256, his account, the time and the sha256 of the map he ranked against. A second write is
refused and the first is never overwritten (a hard link onto the store's name, which fails when the name exists). The
map is opened only while the stored words still hash to the stored sha256, the account is the owner's and the map is
still the one he ranked against; anything else keeps it sealed and says why.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

REPO = Path(settings.BASE_DIR).parent
CREATIVITY = REPO / 'docs' / 'audit' / 'day-13' / 'creativity'
MAP = CREATIVITY / 'map.json'
#: the owner's ranking: settings-derived and git-ignored (bbrose_design_os/.gitignore, ``var/``), never under docs/
STORE = Path(settings.BASE_DIR) / 'var' / 'day13' / 'creativity-owner-ranking.json'
MAP_SCHEMA = 'day13_creativity_map/1'
STORE_SCHEMA = 'day13_creativity_owner_ranking/1'
LABELS = tuple('K%d' % n for n in range(1, 10))
SHEET = 'sheet'
PIECES = ('lid', 'lipstick', 'balm', 'header', 'family')
MIME = 'image/png'
MAX_CHARACTERS = 4000
HASH_CHUNK_BYTES = 1 << 20
NOT_READY, UNREADABLE, CHANGED, READY = 'not ready', 'unreadable', 'changed', 'ready'
SEALED, OPEN, HELD = 'sealed', 'open', 'held'
ALREADY = 'Your ranking is already written. It is kept exactly as you wrote it and is never overwritten.'
#: the verdict rule's rows the page does not show: the name of the function that applies it (code, not words)
UNSHOWN_RULE_KEYS = ('function',)
_HEX = re.compile(r'[0-9a-f]{64}')
_DAY = re.compile(r'(?:^|/)docs/audit/day-(\d+)/')


class Changed(Exception):
    """A tile or the sheet that is gone, outside the creativity folder, or no longer the bytes the map pins."""


class Unreadable(ValueError):
    """The map is not in the shape this page reads (said in plain words, never with a value from the map)."""


class Refused(Exception):
    """The owner's ranking is not written; why, in plain words. Nothing was written."""


class NotReady(Refused):
    """There is no sheet to rank yet."""


class AlreadyWritten(Refused):
    """A ranking is already written; the first is never overwritten."""


def _sha(path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        for chunk in iter(lambda: source.read(HASH_CHUNK_BYTES), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _hex(value) -> bool:
    return isinstance(value, str) and _HEX.fullmatch(value) is not None


def words_sha256(text) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def normalised(text) -> str:
    """The words as they are stored and hashed: every line end one newline (a browser sends a text field's as CR LF),
    the ends trimmed."""
    return text.replace('\r\n', '\n').replace('\r', '\n').strip()


def owner_account() -> str:
    """The owner's account, read where the owner check reads it (apps/dashboard/explorations.py)."""
    from apps.dashboard import explorations
    return explorations.owner_account()


def _map() -> tuple:
    """(the map, the sha256 of its bytes), read once; FileNotFoundError while the sheet builder has not written it,
    Unreadable when it is not in the shape the page reads."""
    raw = MAP.read_bytes()
    record = json.loads(raw.decode('utf-8'))
    if not isinstance(record, dict) or record.get('schema') != MAP_SCHEMA:
        raise Unreadable('the map is not the sheet\'s map in the form this page reads')
    labels = record.get('labels')
    if not isinstance(labels, dict) or set(labels) != set(LABELS):
        raise Unreadable('the map does not name exactly K1 to K9')
    for label in LABELS:
        entry = labels[label]
        if not (isinstance(entry, dict) and isinstance(entry.get('tile'), str) and _hex(entry.get('sha256'))
                and isinstance(entry.get('file'), str) and entry.get('piece') in PIECES):
            raise Unreadable('%s is not in the form this page reads' % label)
    sheet = record.get('sheet')
    if not (isinstance(sheet, dict) and isinstance(sheet.get('png'), str) and _hex(sheet.get('png_sha256'))):
        raise Unreadable('the sheet is not in the form this page reads')
    return record, hashlib.sha256(raw).hexdigest()


def pins(record) -> dict:
    """label -> (repo-relative path, sha256): the nine tiles and the sheet, as the map pins them."""
    out = {label: (record['labels'][label]['tile'], record['labels'][label]['sha256']) for label in LABELS}
    out[SHEET] = (record['sheet']['png'], record['sheet']['png_sha256'])
    return out


def _verify(label, rel_path, sha256) -> Path:
    root = CREATIVITY.resolve()
    path = (REPO / rel_path).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != '.png':
        raise Changed('%s is not a picture in the sheet\'s own folder' % label)
    if not path.is_file():
        raise Changed('%s is gone since the sheet was made' % label)
    if _sha(path) != sha256:
        raise Changed('%s is not the file the sheet was made from (its bytes changed)' % label)
    return path


def checked_file(label) -> tuple:
    """One of the nine files or the sheet, re-hashed against the map's pin: (its path, the name it is served under — its
    label's, never the record's). KeyError for any other label; Changed when its bytes are not the pinned ones;
    FileNotFoundError while there is no map; Unreadable when the map is not in shape."""
    if label not in LABELS + (SHEET,):
        raise KeyError(label)
    rel_path, sha256 = pins(_map()[0])[label]
    return _verify(label, rel_path, sha256), '%s.png' % label


def stored():
    """The owner's ranking as written, or None while none is; ValueError or OSError when the store cannot be read."""
    if not STORE.exists():
        return None
    return json.loads(STORE.read_text(encoding='utf-8'))


def _held_because(ranking, map_sha256):
    """None when the stored ranking opens the map; else why it does not, in plain words."""
    if not (isinstance(ranking, dict) and ranking.get('schema') == STORE_SCHEMA and isinstance(ranking.get('text'), str)):
        return 'the stored ranking is not in the form this page writes'
    if words_sha256(ranking['text']) != ranking.get('sha256'):
        return 'the stored words no longer match the hash written with them'
    if not owner_account() or ranking.get('user') != owner_account():
        return 'the stored ranking was not written by the owner\'s account'
    if ranking.get('map_sha256') != map_sha256:
        return 'the map has changed since your ranking was written'
    return None


def _words(value) -> str:
    """A value of the map in words: a list joined, a table as "name: words", yes or no, a missing value named."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    if value is None:
        return 'none'
    if isinstance(value, (list, tuple)):
        return '; '.join(_words(v) for v in value)
    if isinstance(value, dict):
        return '; '.join('%s: %s' % (str(k).replace('_', ' '), _words(v)) for k, v in value.items())
    return str(value)


def _record_holds(entry) -> str:
    """Whether the record file is still the bytes its tile was pinned to, in a word."""
    try:
        path = (REPO / entry['file']).resolve()
        if not path.is_relative_to((REPO / 'docs' / 'audit').resolve()) or not path.is_file():
            return 'not on this machine'
        return 'yes' if _sha(path) == entry['sha256'] else 'no'
    except (OSError, ValueError):
        return 'unreadable'


def opened(record) -> dict:
    """The map in plain words, for the page once the owner's ranking has opened it."""
    rows = []
    for label in LABELS:
        entry = record['labels'][label]
        day = _DAY.search(entry['file'])
        rows.append({'label': label, 'piece': entry['piece'], 'file': entry['file'],
                     'day': int(day.group(1)) if day else None, 'record_holds': _record_holds(entry)})
    order = record.get('order_listed_by_the_owner')
    seed = record.get('seed')
    rule = record.get('verdict_rule')
    return {'rows': rows, 'order': [str(p) for p in order] if isinstance(order, list) else [],
            'seed': [(str(k), _words(v)) for k, v in seed.items()] if isinstance(seed, dict) else [],
            'verdict_rule': ([(str(k).replace('_', ' '), _words(v)) for k, v in rule.items()
                              if k not in UNSHOWN_RULE_KEYS] if isinstance(rule, dict) else [('rule', _words(rule))]),
            'written_at': _words(record.get('written_at'))}


def state() -> dict:
    """The page's state; never raises. Until the owner's ranking opens the map, only the K names leave this function
    (and the map's own sha256, which the ranking is written against)."""
    try:
        record, map_sha256 = _map()
    except FileNotFoundError:
        return {'state': NOT_READY}
    except Unreadable as error:
        return {'state': UNREADABLE, 'why': str(error)}
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        return {'state': UNREADABLE, 'why': 'the map cannot be read (%s)' % type(error).__name__}
    try:
        for label, (rel_path, sha256) in pins(record).items():
            _verify(label, rel_path, sha256)
    except Changed as error:
        return {'state': CHANGED, 'why': str(error)}
    except (ValueError, OSError) as error:
        return {'state': UNREADABLE, 'why': 'a file of the sheet cannot be read (%s)' % type(error).__name__}
    said = {'state': READY, 'labels': LABELS, 'map_sha256': map_sha256, 'seal': SEALED}
    try:
        ranking = stored()
    except (ValueError, OSError) as error:
        return dict(said, seal=HELD, why='the stored ranking cannot be read (%s)' % type(error).__name__)
    if ranking is None:
        return said
    held = _held_because(ranking, map_sha256)
    if held:
        return dict(said, seal=HELD, why=held)
    return dict(said, seal=OPEN, ranking=ranking, map=opened(record))


def _writable() -> dict:
    said = state()
    if said['state'] != READY:
        raise NotReady('The sheet is not ready, so there is nothing to rank yet. Nothing was written.')
    if said['seal'] != SEALED:
        raise AlreadyWritten(ALREADY)
    return said


def _prepared(text) -> tuple:
    said = _writable()
    if not isinstance(text, str) or not normalised(text):
        raise Refused('No words were written. Write your ranking in the box first.')
    words = normalised(text)
    if len(words) > MAX_CHARACTERS:
        raise Refused('The ranking is longer than %d characters. Nothing was written.' % MAX_CHARACTERS)
    return said, words, words_sha256(words)


def prepared(text) -> tuple:
    """(the words as they would be written, their sha256) for the page to show before he writes them; refused when there
    is no sheet, when a ranking is already written, or when the words are blank or too long. Writes nothing."""
    _said, words, sha256 = _prepared(text)
    return words, sha256


def _write_once(record) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix='.ranking-', suffix='.json', dir=STORE.parent)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as out:
            out.write(json.dumps(record, indent=1, ensure_ascii=False) + '\n')
        os.link(temporary, STORE)                # fails when the name exists: the first ranking is never overwritten
    except FileExistsError:
        raise AlreadyWritten(ALREADY)
    finally:
        os.unlink(temporary)


def write(user_name, text, shown_sha256) -> dict:
    """The owner's ranking, written once (the view has checked the account is the owner's): his words, their sha256, his
    account, the time and the sha256 of the map he ranked against. Refused, writing nothing, when ``prepared`` refuses or
    when the words are not the ones whose sha256 the page showed him."""
    said, words, sha256 = _prepared(text)
    if shown_sha256 != sha256:
        raise Refused('These are not the words whose hash the page showed you. Nothing was written; show them again.')
    record = {'schema': STORE_SCHEMA, 'text': words, 'sha256': sha256, 'user': user_name,
              'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'map_sha256': said['map_sha256']}
    _write_once(record)
    return record
