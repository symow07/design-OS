"""Day 10 §6 — the master of the owner's pick on the pick page, above Day 9's section.

``publish`` writes ``docs/audit/day-10/master/publication.json``: the owner's pick recorded as an override and a
calibration datum (D-D8-6), what the master is (its fidelity verdict, its finishes, the jury's number for the record), and
every file the page shows or offers, each pinned by its sha256 (the lid master, its finish proof and print files, the
open tray, the inside of the lid, the back sticker, the box and the board). ``state`` never raises, so the sections
below always show; ``checked_file`` serves a pinned file only while its bytes are the ones published.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings

REPO = Path(settings.BASE_DIR).parent
DAY10 = REPO / 'docs' / 'audit' / 'day-10'
RECORD = DAY10 / 'master' / 'publication.json'
SCHEMA = 'day10_master/1'
HASH_CHUNK_BYTES = 1 << 20
MIME = {'.png': 'image/png', '.json': 'application/json', '.pdf': 'application/pdf', '.ai': 'application/postscript'}
BEING_BUILT, PUBLISHED, CHANGED, UNREADABLE = 'being built', 'published', 'changed', 'unreadable'
PICK = {'sketch': 'A-2.3', 'path': 'docs/audit/day-9/sketches/A-2.3/lid.png',
        'sha256': '4293fe8b20a8c39e9776e433267fd6b36bfa89ca72f4381710f32a639f797de8', 'day9_role': 'sketch-A-2.3',
        'kind': 'an owner override and a calibration datum (D-D8-6)', 'idea': 'A-2 Golden Hour',
        'decisions': 'D-D10-1 … D-D10-5 (CURRENT_DECISIONS.md, Day 10)', 'recorded_at_commit': '0aa7146'}

#: the page's pieces: (key, title, the picture it shows, the layered file Download offers first, the other formats)
PIECES = (
    ('lid', 'The lid master', 'lid/lid-master-flat.png', 'lid/lid-master.ai',
     ('lid/lid-master.pdf', 'lid/lid-1to1-A4.pdf', 'lid/finish-proof.png', 'lid/checks.json', 'lid/fidelity.json')),
    ('proof', 'Its finish proof', 'lid/finish-proof.png', 'lid/lid-1to1-A4.pdf', ()),
    ('tray', 'The open tray', 'tray/tray-proof.png', 'tray/tray-artwork.pdf', ('tray/picture.png', 'tray/pans.json')),
    ('inside', 'Inside the lid', 'inside-lid/inside-lid-flat.png', 'inside-lid/inside-lid.pdf', ('inside-lid/picture.png',)),
    ('sticker', 'The back sticker', 'sticker/sticker-flat.png', 'sticker/sticker.ai',
     ('sticker/sticker.pdf', 'sticker/fit-report.json')),
    ('box', 'The box', 'box/box-flat.png', 'box/box-artwork.ai',
     ('box/box-artwork.pdf', 'box/box-1to1-A3.pdf', 'box/box-fold-check.json')),
    ('board', 'The board', 'board/palette-board.png', 'board/palette-board.pdf', ()),
)
WORDS = {'.png': 'picture', '.pdf': 'PDF', '.ai': 'layered file (.ai)', '.json': 'record'}


class Changed(Exception):
    """A pinned file that is gone or no longer the one published."""


def _sha(path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        for chunk in iter(lambda: source.read(HASH_CHUNK_BYTES), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def role_of(rel_path) -> str:
    return rel_path.replace('/', '-').replace('.', '-')


def _pin(rel_path) -> dict:
    path = DAY10 / rel_path
    suffix = path.suffix
    return {'path': rel_path, 'sha256': _sha(path), 'mime': MIME[suffix], 'words': '%s · %s' % (path.name, WORDS[suffix])}


def facts() -> dict:
    """What the page says about the master, read from its records."""
    master = _json(DAY10 / 'lid' / 'master.json')
    fidelity = _json(DAY10 / 'lid' / 'fidelity.json')
    verdict = _json(DAY10 / 'lid' / 'jury' / 'verdict.json')
    sticker = _json(DAY10 / 'sticker' / 'fit-report.json')
    pans = _json(DAY10 / 'tray' / 'pans.json')
    box = _json(DAY10 / 'box' / 'box-fold-check.json')
    up = master['upscale']
    return {
        'fidelity_holds': fidelity['verdict']['holds'], 'fidelity_said': fidelity['verdict']['said'],
        'repairs_used': fidelity['verdict']['repairs_used'],
        'upscale': {'mean': up['de00_mean'], 'max': up['de00_max'], 'ssim': up['ssim'],
                    'ppi': master['sharpness']['resampled_ppi'], 'effective_ppi': master['sharpness']['effective_ppi']},
        'foil_pct': master['finishes']['coverage']['foil_and_metallic_pct'],
        'faces': {k: v['label'] for k, v in master['type']['faces'].items()},
        'jury_for_the_record': {'stricter': verdict['raw']['stricter_mean'], 'J1': verdict['raw']['means']['J1'],
                                'J2': verdict['raw']['means']['J2']},
        'sticker': {'body_pt': sticker['body']['size_pt'], 'for_review': len(sticker['for_review'])},
        'tray': {'counts': pans['counts'], 'flagged': len(pans['flagged'])},
        'box': {'inside_safe': box['all_inside_safe'], 'die_untouched': box['die_untouched']['holds']},
    }


def publish() -> dict:
    """The publication record (written whole); every file the page shows or offers pinned by its sha256."""
    downloads = {}
    for _key, _title, picture, layered, others in PIECES:
        for rel_path in (picture, layered) + tuple(others):
            downloads[role_of(rel_path)] = _pin(rel_path)
    record = {'schema': SCHEMA, 'pick': PICK, 'facts': facts(), 'downloads': downloads,
              'pieces': [{'key': k, 'title': t, 'picture': role_of(p), 'layered': role_of(lay),
                          'others': [role_of(o) for o in others]} for k, t, p, lay, others in PIECES],
              'published_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()}
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(record, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    return record


def _verify(role, item) -> Path:
    root = DAY10.resolve()
    path = (root / item['path']).resolve()
    if not path.is_relative_to(root):
        raise Changed('%s points outside Day 10 (%s)' % (role, item['path']))
    if not path.is_file():
        raise Changed('%s (%s) is gone since it was published' % (role, item['path']))
    if _sha(path) != item['sha256']:
        raise Changed('%s (%s) changed since it was published' % (role, item['path']))
    return path


def checked() -> dict:
    """The record, with every pinned file re-hashed; raises ``Changed`` naming the first that changed or is gone."""
    record = _json(RECORD)
    for role, item in record['downloads'].items():
        _verify(role, item)
    return record


def checked_file(role) -> tuple:
    """One pinned file, re-hashed: (its path, its entry); ``KeyError`` when no file has that role, ``Changed`` when its
    bytes are not the ones published."""
    item = _json(RECORD)['downloads'][role]
    return _verify(role, item), item


def state() -> dict:
    """Day 10 on the page: being built, changed, unreadable, or published with the checked record. Never raises."""
    if not RECORD.exists():
        return {'state': BEING_BUILT}
    try:
        return {'state': PUBLISHED, 'record': checked()}
    except Changed as error:
        return {'state': CHANGED, 'why': str(error)}
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        return {'state': UNREADABLE, 'why': '%s: %s' % (type(error).__name__, error)}
