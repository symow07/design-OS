"""Day 9 §6 — the pick page's record for palette round 2 (D-D9-3 … D-D9-8): the builds that pass the jury, each with
its finish proof beside the flat lid; if none passes, the below-the-bar sheet (the best build of each direction by the
stricter juror's mean, a tie broken by both jurors' mean); the history of every Day 9 sketch and build; and the finish
proof's measured effect on Day 8's build. ``publish()`` writes ``docs/audit/day-9/pick/publication.json``: every file
the page shows is named by a role and pinned by its sha256, and the page serves a file only while its bytes still
match. Nothing is ever written under ``docs/audit/day-8`` (Day 8's publication is hash-pinned).

What it reads, exactly as Day 9's build writes it — no defaults; a build folder that lacks one of ``BUILD_FILES`` is not
on the page and is named in ``left_out`` with what it lacks:

- ``concepts/<id>/build.json`` (schema ``day9_build/1``) and ``concepts/<id>/jury/verdict.json`` — ``jury.judge``'s
  record under rubric v2p: ``jury.combine``'s shape, J1's desirability as the three flat fields of its review
  (``DESIRABILITY_KEYS``, jury.DESIRABILITY_FIELDS; a "no" is among the verdict's top issues, set there by the rules).
  The pass is the computed gate's own ``verdict.passed`` (``concept_quality.evaluate``); that record has no ``status``
  key — its state is ``verdict.review_status`` (accepted, rejected or review_pending). A pending verdict is in the
  history and never ranked.
- ``sketches/<sid>/lid.png`` and ``sketches/ranking-<A|B|C>.json`` — ``jury.rank_sketches_v2``'s record (kind
  ``sketch_ranking_v2``, flat rows: ``RANKING_ROW_KEYS``): a row's ``sketch`` is its 1-based number in the record's own
  ``sketches`` list, whose path names the sketch's folder. A ranking J1 did not answer, or that does not name each sketch
  once, is said for its direction and ranks none of its sketches (the record is immutable: a retry is a new file).
- ``jury/proof-effect.json`` — the finish proof's measured effect (absent: said on the page, never invented).

The 1 : 1 crops are read at ``CROP_DPI`` (``day8_pick.crop_true_size``'s resolution); their PNG headers say 96 dpi
(MuPDF's own) and are never read.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from PIL import Image

from apps.pipeline.services.concept_quality import CRITICAL, PASS_SCORE

REPO = Path(settings.BASE_DIR).parent
DAY8 = REPO / 'docs' / 'audit' / 'day-8'
DAY9 = REPO / 'docs' / 'audit' / 'day-9'
RECORD = DAY9 / 'pick' / 'publication.json'
SCHEMA = 'day9_pick/1'
BUILD_SCHEMA = 'day9_build/1'
DIRECTIONS = ('A', 'B', 'C')
LID_MM = (190.0, 120.0)
CROP_DPI = 600                    # the 1 : 1 crops' resolution (day8_pick.crop_true_size's own)
MM_PER_INCH = 25.4
FOIL_AREA_FLOOR_PCT = 10.0        # D-D9-3: foil or metallic ink on at least 10 % of the lid …
RELIEF_AREA_FLOOR_PCT = 15.0      # … or relief on at least 15 %
LINES_PER_CM_FLOOR = 12.0         # D-D9-3: the crafted ornament at least 12 lines per cm where it is densest
HASH_CHUNK_BYTES = 1 << 20
MIME = {'.png': 'image/png', '.json': 'application/json', '.pdf': 'application/pdf', '.ai': 'application/postscript',
        '.svg': 'image/svg+xml'}
#: every file of a build the page shows or offers: (key, file in the build's folder, what it is)
BUILD_FILE_ROLES = (
    ('truthful', 'truthful.png', '%s: the flat lid, 190 × 120 mm — what prints'),
    ('proof', 'finish-proof.png', '%s: the finish proof — the flat lid front-on, its finishes rendered from the finish plates'),
    ('name', 'name-1to1.png', '%s: the name at 1 : 1'),
    ('arabic', 'arabic-1to1.png', '%s: the Arabic line at 1 : 1'),
    ('finishes', 'finish-sheet.png', '%s: the finish sheet'),
    ('media', 'media-map.json', '%s: the media map'),
    ('checks', 'checks.json', '%s: the measured checks'),
    ('eye', 'designer-eye.json', "%s: the designer's eye — the build against its sketch"),
    ('ai', 'truthful.ai', '%s: the layered .ai (finish plates as pages)'),
    ('pdf', 'truthful.pdf', '%s: the same file as PDF'),
    ('svg', 'truthful.svg', '%s: the layered SVG'),
    ('build', 'build.json', "%s: the build's record"),
    ('verdict', 'jury/verdict.json', "%s: the jury's verdict"),
)
BUILD_FILES = tuple(name for _key, name, _words in BUILD_FILE_ROLES)
GATE_WORDS = ('mean ≥ %s on the scores that stand, every critical dimension (%s) ≥ 7, no hard failure '
              '(concept_quality.evaluate) · the stricter juror per dimension · caps after the raw scores · each build\'s '
              'rubric as its verdict records it'
              % (PASS_SCORE, ', '.join(c.replace('_', ' ') for c in CRITICAL)))
SHEET_RULE_WORDS = ("the best build of each direction by the stricter juror's mean (raw), a tie broken by both jurors' "
                    "mean; a tie on both keeps the builds' folder order")
#: the four states of Day 9 on the page
BEING_BUILT, PUBLISHED, CHANGED, UNREADABLE = 'being built', 'published', 'changed', 'unreadable'
#: J1's desirability answer, three flat fields of its review (jury.DESIRABILITY_FIELDS, D-D9-7)
DESIRABILITY_KEYS = ('would_buy_partly_for_the_lid', 'would_photograph_it', 'desirability_why')
#: what the page reads of a sketch-ranking row (jury.RANK_SCHEMA_V2's flat row)
RANKING_ROW_KEYS = ('sketch', 'rank', 'score', 'why', *DESIRABILITY_KEYS, 'must_rebuild', 'richness_survives_rebuild',
                    'buildability_why')
RANKING_KIND = 'sketch_ranking_v2'
#: the states of a direction's ranking
RANKED, NO_ANSWER, NOT_EACH_ONCE = 'ranked', 'no answer', 'not each sketch once'


class Changed(ValueError):
    """A pinned file is no longer the one published: its bytes moved, it is gone, or its path leaves Day 9."""


def _sha(path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        for chunk in iter(lambda: source.read(HASH_CHUNK_BYTES), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _picture(path) -> dict:
    """A lid picture's pixel size and how far its proportion is from the lid's 190 : 120."""
    with Image.open(path) as image:
        width_px, height_px = image.size
    return {'size_px': [width_px, height_px],
            'off_lid_proportion_pct': round(abs(width_px / height_px / (LID_MM[0] / LID_MM[1]) - 1) * 100, 3)}


def _crop(path) -> dict:
    """A 1 : 1 crop's pixel size and its size in millimetres at ``CROP_DPI``."""
    with Image.open(path) as image:
        width_px, height_px = image.size
    return {'size_px': [width_px, height_px], 'width_mm': round(width_px * MM_PER_INCH / CROP_DPI, 2),
            'height_mm': round(height_px * MM_PER_INCH / CROP_DPI, 2)}


def finish_numbers(finish) -> dict:
    """The build's own finish numbers, read exactly, with D-D9-3's floors computed beside them (None: not measured)."""
    foil_pct, relief_pct = finish['foil_metallic_pct'], finish['relief_pct']
    lines_per_cm = finish['lines_per_cm_densest']
    met = [value >= floor for value, floor in ((foil_pct, FOIL_AREA_FLOOR_PCT), (relief_pct, RELIEF_AREA_FLOOR_PCT))
           if value is not None]
    return {'foil_metallic_pct': foil_pct, 'relief_pct': relief_pct, 'lines_per_cm_densest': lines_per_cm,
            'foil_limits_hold': finish['foil_limits_hold'],
            'area_floor_holds': True if any(met) else (False if len(met) == 2 else None),
            'lines_floor_holds': None if lines_per_cm is None else lines_per_cm >= LINES_PER_CM_FLOOR}


def jury_reading(verdict) -> dict:
    """What the page shows of a verdict: both jurors' raw scores per dimension, the scores that stand, both jurors'
    own top findings and J1's desirability answer; a pending review is named and carries no score."""
    gate = verdict['verdict']
    if gate['review_status'] == 'review_pending':
        return {'judged': False, 'pending_why': gate['issues'], 'raw_means': None, 'stricter_mean': None,
                'both_mean': None, 'capped_mean': None, 'scores': None, 'caps': verdict['caps_applied'],
                'hard_failures': gate['hard_failures'], 'top_issues': [], 'juror_issues': None, 'rule_issues': [],
                'desirability': None}
    raw, capped = verdict['raw'], verdict['capped']
    means, j1 = raw['means'], raw['J1']
    own = raw['J1']['top_issues'] + raw['J2']['top_issues']
    return {'judged': True, 'pending_why': None, 'raw_means': {'J1': means['J1'], 'J2': means['J2']},
            'stricter_mean': raw['stricter_mean'], 'both_mean': round((means['J1'] + means['J2']) / 2, 3),
            'capped_mean': gate['score'],
            'scores': {n: {'J1': raw['scores']['J1'][n], 'J2': raw['scores']['J2'][n], 'stands': capped[n]} for n in capped},
            'caps': verdict['caps_applied'], 'hard_failures': gate['hard_failures'], 'top_issues': verdict['top_issues'],
            'juror_issues': {j: raw[j]['top_issues'] for j in ('J1', 'J2')},
            'rule_issues': [i for i in verdict['top_issues'] if i not in own],
            'desirability': {'would_buy_partly_for_the_lid': j1['would_buy_partly_for_the_lid'],
                             'would_photograph_it': j1['would_photograph_it'], 'why': j1['desirability_why']}}


def _build(folder, pin) -> dict:
    cid = folder.name
    build = _json(folder / 'build.json')
    if build['schema'] != BUILD_SCHEMA:
        raise ValueError('%s: build.json is %r, not %s' % (cid, build['schema'], BUILD_SCHEMA))
    if build['concept'] != cid:
        raise ValueError('%s: build.json names the build %r' % (cid, build['concept']))
    if build['direction'] not in DIRECTIONS:
        raise ValueError('%s: build.json names direction %r' % (cid, build['direction']))
    verdict = _json(folder / 'jury' / 'verdict.json')
    gate = verdict['verdict']
    return {'id': cid, 'idea': build['idea'], 'direction': build['direction'], 'idea_name': build['idea_name'],
            'idea_line': build['idea_line'], 'sketch': build['sketch'], 'plate_path': build['plate_path'],
            'lettering': {k: build['lettering'][k] for k in ('face', 'stem', 'licence', 'ops', 'cap_mm')},
            'arabic': {k: build['arabic'][k] for k in ('face', 'stem', 'licence')},
            'checks_hold': build['checks_hold'], 'issues': build['issues'], 'cannot_meet': build['cannot_meet'],
            'repair_of': build['repair_of'],
            'finish': finish_numbers(build['finish']), 'status': gate['review_status'], 'passes': gate['passed'] is True,
            'rubric': verdict['rubric_version'],
            **jury_reading(verdict),
            'pictures': {'truthful': _picture(folder / 'truthful.png'), 'proof': _picture(folder / 'finish-proof.png')},
            'name_crop': _crop(folder / 'name-1to1.png'), 'arabic_crop': _crop(folder / 'arabic-1to1.png'),
            'files': {key: pin('%s-%s' % (cid, key), folder / name, words % cid) for key, name, words in BUILD_FILE_ROLES}}


def ranked(builds) -> list:
    """The judged builds, best first: by the stricter juror's mean, a tie broken by both jurors' mean; a tie on both
    keeps the order given (the builds' folder order)."""
    return sorted((b for b in builds if b['judged']), key=lambda b: (-b['stricter_mean'], -b['both_mean']))


def best_of_each_direction(builds) -> list:
    """The below-the-bar sheet: the best judged build of each direction (``ranked``'s rule), in that same order."""
    order = ranked(builds)
    best = {}
    for b in order:
        best.setdefault(b['direction'], b['id'])
    return [b['id'] for b in order if best[b['direction']] == b['id']]


def _is_number(number, count) -> bool:
    """Whether a ranking's sketch number is one of its ``count`` sketches (1-based; a bool is not a number)."""
    return isinstance(number, int) and not isinstance(number, bool) and 1 <= number <= count


def _numbered(order, number, path) -> str:
    """A ranking row's sketch: its 1-based number in the ranking record's own ``sketches`` list."""
    if not _is_number(number, len(order)):
        raise ValueError('%s: sketch number %r is not one of its %d sketches' % (path.name, number, len(order)))
    return order[number - 1]


def _sketches(pin, builds) -> tuple:
    """Every Day 9 sketch with J1's ranking where there is one, and each direction's ranking (None: not ranked yet)."""
    root = DAY9 / 'sketches'
    rows, rankings, ranked_rows, ranked_sha = [], {}, {}, {}
    for d in DIRECTIONS:
        path = root / ('ranking-%s.json' % d)
        if not path.is_file():
            rankings[d] = None
            continue
        record = _json(path)
        if record['kind'] != RANKING_KIND:
            raise ValueError('%s is a %r record, not %s' % (path.name, record['kind'], RANKING_KIND))
        order = [Path(s['path']).parent.name for s in record['sketches']]
        ranked_sha.update({Path(s['path']).parent.name: s['sha256'] for s in record['sketches']})
        payload, role = record['payload'], pin('ranking-%s' % d, path, "J1's ranking of direction %s's sketches" % d)
        if payload is None:
            rankings[d] = {'file': role, 'state': NO_ANSWER, 'best_two': [],
                           'why': "J1's ranking returned no answer (stop reason %s%s)"
                                  % (record['stop_reason'], '; %s' % record['parse_error'] if record['parse_error'] else '')}
            continue
        if record['ranked_every_sketch_once'] is not True:
            rankings[d] = {'file': role, 'state': NOT_EACH_ONCE, 'best_two': [],
                           'why': "J1's ranking does not name each of its %d sketches once" % len(order)}
            continue
        stray = [n for n in payload['best_two'] if not _is_number(n, len(order))]
        best = [order[n - 1] for n in payload['best_two'] if _is_number(n, len(order))]
        for row in payload['ranking']:
            sid = _numbered(order, row['sketch'], path)
            if sid in ranked_rows:
                raise ValueError('sketch %s is ranked twice (%s)' % (sid, path.name))
            ranked_rows[sid] = {'ranked': True, 'direction': d, 'rank': row['rank'], 'score': row['score'], 'why': row['why'],
                                'desirability': {'would_buy_partly_for_the_lid': row['would_buy_partly_for_the_lid'],
                                                 'would_photograph_it': row['would_photograph_it'],
                                                 'why': row['desirability_why']},
                                'buildability': {'must_rebuild': row['must_rebuild'],
                                                 'richness_survives_rebuild': row['richness_survives_rebuild'],
                                                 'why': row['buildability_why']},
                                'went_on': sid in best}
        rankings[d] = {'file': role, 'state': RANKED, 'best_two': best,
                       'why': None if not stray else "J1's best two name %s, not among its %d sketches"
                                                     % (', '.join(repr(n) for n in stray), len(order))}
    folders = sorted(p.name for p in root.iterdir() if p.is_dir() and (p / 'lid.png').is_file()) if root.is_dir() else []
    lost = sorted(set(ranked_rows) - set(folders))
    if lost:
        raise ValueError('a ranking names sketches whose lid.png is not in %s: %s' % (root, ', '.join(lost)))
    built = {}
    for b in builds:
        built.setdefault(b['sketch'], []).append(b['id'])
    for sid in folders:
        role = pin('sketch-%s' % sid, root / sid / 'lid.png', 'sketch %s (an idea from the image model, never printed)' % sid)
        row = ranked_rows[sid] if sid in ranked_rows else {'ranked': False, 'direction': None, 'rank': None, 'score': None,
                                                           'why': None, 'desirability': None, 'buildability': None,
                                                           'went_on': False}
        rows.append({'id': sid, **row, 'built_as': built[sid] if sid in built else [], 'file': role,
                     'ranked_bytes_hold': ranked_sha[sid] == _sha(root / sid / 'lid.png') if sid in ranked_sha else None})
    rows.sort(key=lambda r: (0, r['direction'], r['rank'], r['id']) if r['ranked'] else (1, '', 0, r['id']))
    return rows, rankings


def _proof_effect(pin):
    """The finish proof's measured effect on Day 8's build, read exactly; None while it is not measured."""
    path = DAY9 / 'jury' / 'proof-effect.json'
    if not path.is_file():
        return None
    effect = _json(path)
    return {**{k: effect[k] for k in ('build', 'before_stricter_mean', 'after_stricter_mean', 'delta', 'rubric', 'jury_spread_note')},
            'file': pin('proof-effect', path, "the finish proof's measured effect on Day 8's %s" % effect['build'])}


def publish() -> dict:
    """The record the page reads, from the files Day 9's build wrote; refuses while no build folder is complete."""
    if RECORD.resolve().is_relative_to(DAY8.resolve()):
        raise ValueError("Day 8's records are hash-pinned: the Day 9 publication is never written under %s" % DAY8)
    concepts = DAY9 / 'concepts'
    if not concepts.is_dir():
        raise ValueError('no Day 9 build yet: %s does not exist' % concepts)
    downloads = {}

    def pin(role, path, words):
        if role in downloads:
            raise ValueError('two files claim the role %s' % role)
        downloads[role] = {'path': path.relative_to(DAY9).as_posix(), 'sha256': _sha(path), 'mime': MIME[path.suffix],
                           'words': words}
        return role

    builds, left_out = [], []
    for folder in sorted(p for p in concepts.iterdir() if p.is_dir() and not p.name.startswith('.')):
        missing = [name for name in BUILD_FILES if not (folder / name).is_file()]
        if missing:
            left_out.append({'id': folder.name, 'missing': missing})
            continue
        builds.append(_build(folder, pin))
    if not builds:
        raise ValueError('no Day 9 build is complete yet (%d folders, each missing a file)' % len(left_out))
    sketches, rankings = _sketches(pin, builds)
    passing = [b['id'] for b in builds if b['passes']]
    sheet = [] if passing else best_of_each_direction(builds)
    record = {'schema': SCHEMA, 'made_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), 'gate': GATE_WORDS,
              'passing': passing, 'below_the_bar': sheet, 'below_the_bar_rule': SHEET_RULE_WORDS,
              'shown': passing if passing else sheet, 'ranking': [b['id'] for b in ranked(builds)],
              'builds': builds, 'left_out': left_out, 'sketches': sketches, 'rankings': rankings,
              'proof_effect': _proof_effect(pin), 'crop_dpi': CROP_DPI,
              'floors': {'foil_metallic_pct': FOIL_AREA_FLOOR_PCT, 'relief_pct': RELIEF_AREA_FLOOR_PCT,
                         'lines_per_cm': LINES_PER_CM_FLOOR},
              'downloads': downloads}
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    partial = RECORD.with_name(RECORD.name + '.partial')
    partial.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    os.replace(partial, RECORD)
    return record


def _verify(role, item) -> Path:
    root = DAY9.resolve()
    path = (root / item['path']).resolve()
    if not path.is_relative_to(root):
        raise Changed('%s points outside Day 9 (%s)' % (role, item['path']))
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
    """One pinned file, re-hashed: (its path, its entry); ``KeyError`` when no file has that role, ``Changed`` when
    its bytes are not the ones published."""
    item = _json(RECORD)['downloads'][role]
    return _verify(role, item), item


def state() -> dict:
    """Day 9 on the page: being built (no publication yet), changed (a pinned file is not the one published — named,
    never shown), unreadable (the record itself), or published with the checked record. Never raises, so Day 8's
    section below always shows."""
    if not RECORD.exists():
        return {'state': BEING_BUILT}
    try:
        return {'state': PUBLISHED, 'record': checked()}
    except Changed as error:
        return {'state': CHANGED, 'why': str(error)}
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        return {'state': UNREADABLE, 'why': '%s: %s' % (type(error).__name__, error)}
