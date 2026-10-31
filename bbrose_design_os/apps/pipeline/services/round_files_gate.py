"""The owner is the gate (owner, 2026-10-28). The unit is the FACE: each printed face is its own job — drawn (a
stand face cut straight from the flat painting of the engine's die, owner 2026-10-28 "die first"; a product face one
edit guided by the picked picture, no lettering), its live type and the approved logo placed, a flat preview made, and
for a drawn product face the eye's notes added once as advice, never a block. One face failing never blocks another. The owner Accepts or Redraws
each face (a Redraw is one edit at the owner's request, with an optional one-line note); "Make my files", enabled once
every face is Accepted, composes the accepted faces on the engine's die and writes the files — no review after it.

The board lives in the build row (``steps['faces']['board']``); the web and the worker each change one face at a time
under the row's lock, re-read fresh, so neither overwrites the other's click or drawing."""
from __future__ import annotations

import base64
import binascii
from copy import copy, deepcopy
from datetime import datetime, timedelta
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace
import zipfile

import numpy as np
from shapely.affinity import translate
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from apps.pipeline.models import Round, RoundMaster
from . import round_files_faces as faces
from . import round_flow as flow
from . import spend_reservation as spend
from .round_calls import IMAGE_MODEL, STREAM_PARTIAL_IMAGES, RoundContext, sha, streamed_edit

SCHEMA = 'owner_face_gate/1'
LABELS = {'queued': 'Waiting to be drawn', 'drawing': 'Being drawn', 'drawn': 'Drawn, awaiting your Accept',
          'accepted': 'Accepted', 'failed': 'Could not be drawn'}


# the image provider's refusal when its account has no credits left (round 4, 2026-10-29): billed nothing, and every
# later call meets the same refusal until the owner adds credits
NO_CREDITS = ('insufficient_quota', 'credit_balance_exhausted')
NO_CREDITS_WORDS = ('OpenAI refused the drawing: the account has no credits left, so nothing was drawn and nothing was '
                    'charged. Add credits to the OpenAI account, then press Redraw.')


def out_of_credits(error):
    return any(word in str(error) for word in NO_CREDITS)


def plain_error(error):
    """What the owner reads when a face's job failed: a lost call, the spend cap or an image account with no credits
    in its own words; anything else in plain words (the build's record keeps the reason)."""
    if not error:
        return ''
    if out_of_credits(error):
        return NO_CREDITS_WORDS
    if error.startswith('LostCall: '):
        return error[len('LostCall: '):] + ' Press Redraw to draw it again.'
    if error.startswith('BudgetExceededError: '):
        return 'The round\'s spend cap would be passed, so nothing was drawn.'
    return 'This face could not be finished this time; the reason is kept in the build\'s record. Press Redraw to try again.'


def root(build):
    return flow.round_root(build.round) / 'files'


def is_gate(build):
    return isinstance((build.steps.get('faces') or {}).get('board'), dict)


def board(build):
    return build.steps['faces']['board']


def current(row):
    return next((entry for entry in row['drawings'] if entry['n'] == row['drawing']), None)


def empty_face(key):
    return {'label': faces.FACES[key]['label'], 'state': 'queued', 'drawing': None, 'drawings': [], 'accepted': None,
            'note': '', 'suggested': '', 'error': ''}


def _rel(build, path):
    resolved, base = Path(path).resolve(), root(build).resolve()
    if not resolved.is_relative_to(base):
        raise ValueError('A face artifact escaped its build folder.')
    return str(resolved.relative_to(base))


def _change(build_id, change):
    """One change to the build row under its lock, on a fresh read; ``change(build)`` returns a value or raises."""
    with transaction.atomic():
        build = RoundMaster.objects.select_for_update().select_related('round').get(pk=build_id)
        value = change(build)
        build.save()
    return build, value


def _set_face(build_id, key, **fields):
    return _change(build_id, lambda build: board(build)[key].update(fields))[0]


def pending(row):
    """The next job a face has: 'draw', 'preview', 'eye', or None (it waits for the owner)."""
    if row['state'] in ('queued', 'drawing'):
        return 'draw'
    entry = current(row)
    if entry is None or row['state'] == 'failed':
        return None
    if entry.get('preview') is None:
        return None if entry.get('preview_error') else 'preview'
    if (entry.get('eye') or {}).get('state') == 'pending':
        return 'eye'
    return None


def die_sizes(build, die=None):
    """Each face's size on the die as it stands now (w × h mm, rounded to 0.1)."""
    if die is None:
        die = faces.die_of(json.loads((root(build) / 'stand.json').read_text()))
    brief = files_brief(build)
    return {key: [round(v, 1) for v in (lambda f: (f['w_mm'], f['h_mm']))(faces.face_geometry(key, brief, die))]
            for key in faces.FACES}


# --- one face's jobs (the worker) -------------------------------------------------------------------------------------

def flat_claim(build):
    """The flat stand this build's faces are cut from (owner, 2026-10-28), or None."""
    path = root(build) / 'flat' / 'claim.json'
    return json.loads(path.read_text()) if path.exists() else None


def claim_spend(build, claim):
    """What a flat claim's own calls have cost (billed, held, or lost with the outcome unknown, counted): its painting of
    the die and every face or net edit it recorded before sending (claim['operations'])."""
    slug = build.round.slug
    own = {'files/%s/image/flat/stand/%d' % (slug, int(claim['attempt']))}
    own |= {'files/%s/image/%s' % (slug, operation) for operation in claim.get('operations', [])}
    with spend._connect() as db:
        rows = [dict(row) for row in db.execute('SELECT operation, accounted FROM calls WHERE operation LIKE ?',
                                                ('files/' + slug + '/image/%',))]
    return sum(row['accounted'] for row in rows if row['operation'] in own) / 1e6


def claimed_call(ctx, claim, operation, hold):
    """Before a claim's paid edit: the call is refused in words if its hold would pass the claim's cap; else it is
    recorded on the claim (so it counts against it) and may be sent. A call already recorded is a resumed one."""
    path = root(ctx.build) / 'flat' / 'claim.json'
    saved = json.loads(path.read_text())
    if operation in saved.get('operations', []):
        return saved
    spent = claim_spend(ctx.build, saved)
    if spent + hold > saved['budget_usd'] + 1e-9:
        raise ValueError('This edit would pass the flat design\'s $%g cap ($%.2f spent, $%.2f held for it).'
                         % (saved['budget_usd'], spent, hold))
    saved['operations'] = saved.get('operations', []) + [operation]
    flow.write_json(path, saved)
    claim['operations'] = saved['operations']
    return saved


def _plain_faces(build, claim):
    """The stand faces the owner's policy names plain (its 'plain_faces': a list of face keys), read from his policy as
    it stands, else from the claim's copy of it; where neither names any, the stand faces plain in the picked painting
    itself (painted_plain, written once per painting to flat/plain.json)."""
    stands = json.loads(POLICY.read_text())['flat_stands']
    policy = stands[build.round.slug] if build.round.slug in stands else claim['policy']
    if 'plain_faces' in policy:
        return tuple(policy['plain_faces'])
    if 'plain_faces' in claim['policy']:
        return tuple(claim['policy']['plain_faces'])
    painting = faces.current_painting(root(build))
    if painting is None:
        return ()
    path = root(build) / 'flat' / 'plain.json'
    if path.exists() and read(path)['painting_sha256'] == painting['flat_sha256']:
        return tuple(read(path)['plain_faces'])
    geometry = read(root(build) / 'stand.json')
    checks = {key: faces.painted_plain(painting, key, geometry) for key in faces.FACES if faces.stand_face(key)}
    plain = [key for key, check in checks.items() if check['plain']]
    flow.write_json(path, {'schema': 'painted_plain_faces/1', 'painting_sha256': painting['flat_sha256'],
                           'plain_faces': plain, 'checks': checks})
    return tuple(plain)


def _panel_record(build, entry):
    return json.loads((root(build) / entry['record']).read_text())


def panel_flags(build, key, record, plain_faces):
    """Why a panel drawing is not yet what the owner should judge (the owner's goal of 2026-10-29): over the bar
    against its reference, drawn from a crop the painting did not keep, or not plain where the owner's policy says
    plain. A drawing made before these rules is measured now, the same way."""
    reasons = []
    check = record['against_painting']
    if check.get('revision') != faces.CHECK_REVISION:
        # measured before the check kept to the face's printed pixels: measured again, the same way as a new drawing
        check = faces.reference_check(record, read(root(build) / 'inspection.json'))
    if check['flagged']:
        reasons.append('against its reference ΔE00 median %.1f, p90 %.1f (bar %g, %g)'
                       % (check['median'], check['p90'], check['bar']['median'], check['bar']['p90']))
    reliability = record['reliability'] if 'reliability' in record else faces.crop_reliability(
        json.loads((Path(record['painting']).parent / 'record.json').read_text()), key,
        json.loads((root(build) / 'stand.json').read_text()))
    if record.get('reference_source') in (None, 'painting') and not reliability['reliable']:
        reasons.append('drawn from a crop the painting did not keep (coverage %.2f, %.0f%% left unpainted)'
                       % (reliability['coverage'], 100 * reliability['unpainted_share']))
    if key in plain_faces:
        plain = record['plain_check'] if record.get('plain_check') else faces.plain_check(record['face'], record['template'])
        if not plain['plain']:
            reasons.append('not plain: %.1f%% of it more than ΔE00 %g from its own colour (at most %.0f%%)'
                           % (100 * plain['share_over'], plain['threshold']['delta_e'], 100 * plain['threshold']['share']))
    return reasons


def _swatch(build, plain_faces):
    """A swatch of the stand's board for a plain face: the middle of the plainest plain face drawn so far from a crop
    the painting kept and within the bar against it (its edges left out, where a neighbour's art can cross a fold),
    written to flat/swatch/; None if there is none."""
    best = None
    for key in plain_faces:
        row = board(build).get(key)
        entry = current(row) if row else None
        if not entry or entry.get('source') != 'panel':
            continue
        record = _panel_record(build, entry)
        reliability = record['reliability'] if 'reliability' in record else faces.crop_reliability(
            read(Path(record['painting']).parent / 'record.json'), key, read(root(build) / 'stand.json'))
        if not reliability['reliable'] or record['against_painting']['flagged']:
            continue
        share = faces.plain_check(record['face'], record['template'])['share_over']
        if best is None or share < best[0]:
            best = (share, key, entry['n'], record['face'])
    if best is None:
        return None
    path = root(build) / 'flat' / 'swatch' / ('%s-%d.png' % (best[1], best[2]))
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(best[3]) as image:
            w, h = image.size
            image.convert('RGB').crop((int(w * .2), int(h * .2), int(w * .8), int(h * .8))).save(path)
    return str(path)


#: one system redraw per flagged panel, never a second: after it the face is the owner's (his Redraw)
SYSTEM_REDRAWS = 1


def _board_source(build, plain_faces, *, exclude):
    """The stand's plainest passing plain drawing (a panel record), for a board face: a current panel drawing of a
    stand face (the owner's plain faces first, then any stand face) that passes its reference check on its printed
    pixels and the plain check; None if there is none."""
    best = None
    for key in list(plain_faces) + [k for k in faces.FACES if faces.stand_face(k) and k not in plain_faces]:
        row = board(build).get(key)
        entry = current(row) if row and key != exclude else None
        if not entry or entry.get('source') != 'panel':
            continue
        record = _panel_record(build, entry)
        if panel_flags(build, key, record, (key,)):
            continue
        share = faces.plain_check(record['face'], record['template'])['share_over']
        if best is None or share < best[0]:
            best = (share, record)
    return best[1] if best else None


def _board_drawing(build, key, row, source, why):
    """A plain face's board drawing made now ($0, under the build's lock): the next free drawing number, appended to
    the face's drawings; the face waits for the owner as any drawn face does. Never twice (row['board_face'])."""
    listed = [entry['n'] for entry in row['drawings']]
    folders = [path for path in (root(build) / 'faces' / key / 'drawings').glob('*') if path.name.isdigit()]
    # a board drawing already made but never listed (a delivery that did not save) is the one, never a second
    made = [int(path.name) for path in folders if int(path.name) not in listed and (path / 'record.json').exists()
            and read(path / 'record.json').get('source') == 'board']
    n = min(made) if made else max(listed + [int(path.name) for path in folders] + [0]) + 1
    ctx = SimpleNamespace(root=root(build), brief=files_brief(build))
    record = faces.board_face(ctx, key, n, source, json.loads((root(build) / 'stand.json').read_text()), why=why)
    check = record['against_painting']
    row['drawings'].append({
        'n': n, 'record': _rel(build, faces.drawing_folder(ctx.root, key, n) / 'record.json'),
        'face': _rel(build, record['face']), 'face_sha256': record['face_sha256'],
        'reference': _rel(build, record['reference']['path']), 'reference_sha256': record['reference']['sha256'],
        'preview': None, 'preview_sha256': None, 'size_mm': None, 'facts': None,
        'eye': {'state': 'none', 'why': 'the stand\'s board (%s) tiled at its own pixels, $0: %s' % (
            record['board_face']['from'], why)},
        'source': 'board', 'native_ppi': record['native_ppi'], 'against_painting': check,
        'reference_source': 'board', 'plain_check': record['plain_check'], 'cost_usd': 0.0,
        'at': timezone.now().isoformat()})
    row.update(state='drawn', drawing=n, pending_n=None, accepted=None, error='',
               board_face={'n': n, 'from': record['board_face']['from'], 'why': why, 'at': timezone.now().isoformat()})
    return record


def stale_views(build):
    """In the worker, under the build's lock, $0: when every face is drawn but the proof sheet on record was made for
    other drawings or older rules (PROOF_REVISION, TYPE_REVISION), the build is queued so the faces job settles the
    views again. Returns True when it queued."""
    if not is_gate(build) or 'faces' not in build.steps or build.state != 'awaiting' or build.current_step != 'faces':
        return False
    rows = board(build)
    if any(current(row) is None or row['state'] not in ('drawn', 'accepted') for row in rows.values()):
        return False
    expected = digest(dict({key: current(row)['face_sha256'] for key, row in rows.items()}, type=faces.TYPE_REVISION,
                           proof=PROOF_REVISION))[:16]
    path = root(build) / 'proof' / 'current.json'
    if path.exists() and read(path).get('signature') == expected:
        return False
    build.steps['faces']['state'] = 'queued'
    build.state = 'queued'
    return True


def system_repaint(record_id, key, *, why, note='', restore=None):
    """One face drawn again by the system and not by the owner's word, ``why`` shown on its card in place of a note of his:
    repainted alone on the art it joins (``note``: what the painter is told), or at $0 its drawing ``restore`` with the plain
    area for its words put back."""
    with transaction.atomic():
        build = RoundMaster.objects.select_for_update().select_related('round').get(round_id=record_id)
        if not faces.stand_face(key) or build.state in ('queued', 'running'):
            raise ValueError('Only a stand face, with no job running, is drawn again.')
        row = board(build)[key]
        system = {'why': why, 'note': note, 'at': timezone.now().isoformat()}
        if restore is not None:
            source = next(entry for entry in row['drawings'] if entry['n'] == restore)
            panels = faces.stand_panels(read(root(build) / 'stand.json'))
            box = faces.lost_word_place(read(root(build) / source['record']), panels[key])
            if box is None:
                raise ValueError('That drawing has not lost a plain area for its words.')
            system.update(restore=restore, box=box)
        row.update(state='queued', accepted=None, error='', pending_n=None, system=system)
        build.steps['faces']['state'] = 'queued'
        _wake(build)
        build.save()


def word_repairs(build):
    """In the worker, under the build's lock, $0: on a wrap claim, a face that lost the plain area its words stand in has
    it put back once, at $0, from the art that had it (faces.restore_word_place): a repaint would move its bands. Still
    without one, its card says so. Returns the faces queued."""
    claim = flat_claim(build)
    if claim is None or not claim.get('wrap') or not is_gate(build) or build.current_step != 'faces':
        return []
    done = claim['wrap'].get('words_repainted', [])
    rows, queued = board(build), []
    if any(pending(row) for row in rows.values()) or any(current(row) is None for row in rows.values()):
        return []
    panels = faces.stand_panels(read(root(build) / 'stand.json'))
    for key, row in rows.items():
        entry = current(row)
        if key in done or not faces.stand_face(key) or entry.get('source') != 'wrap' or row['state'] != 'drawn':
            continue
        box = faces.lost_word_place(_panel_record(build, entry), panels[key])
        if box is None:
            continue
        row.update(state='queued', accepted=None, error='', pending_n=None, system={
            'why': 'the plain area its words stand in put back, at no cost: the wrap had filled it', 'restore': entry['n'],
            'box': box, 'note': '', 'at': timezone.now().isoformat()})
        queued.append(key)
    if queued:
        claim['wrap'] = dict(claim['wrap'], words_repainted=done + queued)
        flow.write_json(root(build) / 'flat' / 'claim.json', claim)
        build.steps['faces']['state'] = 'queued'
        if build.state == 'awaiting':
            build.state = 'queued'
    return queued


def ground_repairs(build):
    """In the worker, under the build's lock, $0: on a wrap claim, a panel measured off the design's ground is repainted
    once, on the art it joins, inside the round's cap (the owner, 2026-10-30). One that would pass the cap, or is still off
    after its repaint, stays as it is and the page says so. Returns the faces queued."""
    claim = flat_claim(build)
    if claim is None or not claim.get('wrap') or claim['wrap'].get('ground_repainted') or not is_gate(build):
        return []
    if build.current_step != 'faces' or 'faces' not in build.steps:
        return []
    made = _page_rules(build)
    if made is None or not made.get('ground') or made['ground']['holds']:
        return []
    from .round_calls import round_costs
    geometry = read(root(build) / 'stand.json')
    layout = faces.wrap_layout(faces.stand_panels(geometry), faces.STAND_WRAP)
    left = round_costs(build.round, {})['left_usd']
    queued, unaffordable = [], []
    for key in made['ground']['off']:
        row = board(build)[key]
        canvas = faces.wrap_canvas(layout, [key], context_mm=faces.WRAP_CONTEXT_MM)
        hold = _wrap_hold(canvas, faces.face_quality(build.round, key))
        if hold > left or row['state'] == 'accepted':
            unaffordable.append(key)
            continue
        left -= hold
        row.update(state='queued', pending_n=None, error='')
        queued.append(key)
    claim['wrap'] = dict(claim['wrap'], ground_repainted={'queued': queued, 'kept': unaffordable,
                                                          'at': timezone.now().isoformat()})
    flow.write_json(root(build) / 'flat' / 'claim.json', claim)
    if queued:
        build.steps['faces']['state'] = 'queued'
        if build.state == 'awaiting':
            build.state = 'queued'
    return queued


def retype(build):
    """In the worker, under the build's lock, $0: a face whose preview was placed under older type rules (the owner's
    ruling of 2026-10-29: English only) has its type placed again — its drawing kept, its preview made again by the
    faces job; an accepted face goes back to waiting, its words having changed. Returns the faces re-typed."""
    if not is_gate(build) or 'faces' not in build.steps:
        return []
    retyped = []
    for key, row in board(build).items():
        entry = current(row)
        if entry is None or not entry.get('preview') or entry.get('type_revision') == faces.TYPE_REVISION:
            continue
        entry.update(preview=None, preview_sha256=None, preview_error=None)
        if row['state'] == 'accepted':
            row.update(state='drawn', accepted=None)
        retyped.append(key)
    if retyped:
        build.steps['faces']['state'] = 'queued'
        if build.current_step == 'faces' and build.state == 'awaiting':
            build.state = 'queued'
    return retyped


def system_repairs(build):
    """In the worker, under the build's lock, $0 (the owner's goal of 2026-10-29): on a panels-'full' claim, each stand
    face whose current panel drawing panel_flags names, not accepted and not yet redrawn by the system, is queued for
    its one system redraw (under the claim's cap, checked at the call). Returns the faces queued."""
    claim = flat_claim(build)
    if claim is None or claim.get('panels') != 'full' or not is_gate(build) or 'faces' not in build.steps:
        return []
    plain_faces, queued = _plain_faces(build, claim), []
    for key, row in board(build).items():
        entry = current(row) if faces.stand_face(key) else None
        if entry is None or entry.get('source') != 'panel' or row['state'] != 'drawn' or row.get('outline_redraw'):
            continue                    # a face redrawn for its new outline had its one system action: the owner's now
        if not row.get('system_redraw'):
            reasons = panel_flags(build, key, _panel_record(build, entry), plain_faces)
            if reasons:
                row.update(state='queued', pending_n=None, error='',
                           system_redraw={'reason': '; '.join(reasons), 'of': row['drawing'],
                                          'at': timezone.now().isoformat()})
                queued.append(key)
        elif key in plain_faces and 'drawn' in row['system_redraw'] and not row.get('board_face'):
            # a plain face still not plain after its one redraw: its next drawing is the stand's board, at $0
            reasons = panel_flags(build, key, _panel_record(build, entry), plain_faces)
            source = _board_source(build, plain_faces, exclude=key) if reasons else None
            if source is not None and faces.board_fits(key, files_brief(build), read(root(build) / 'stand.json'), source):
                _board_drawing(build, key, row, source, '; '.join(reasons))
                queued.append(key)                      # saved with the build; its preview is the faces job's
    if queued:
        build.steps['faces']['state'] = 'queued'
        if build.current_step == 'faces' and build.state == 'awaiting':
            build.state = 'queued'
    return queued


def _board_entry(ctx, key, n, record, why):
    """The drawing entry of a board face (board_face): $0, the stand's board tiled over the face."""
    return {'n': n, 'record': _rel(ctx.build, faces.drawing_folder(ctx.root, key, n) / 'record.json'),
            'face': _rel(ctx.build, record['face']), 'face_sha256': record['face_sha256'],
            'reference': _rel(ctx.build, record['reference']['path']), 'reference_sha256': record['reference']['sha256'],
            'preview': None, 'preview_sha256': None, 'size_mm': None, 'facts': None, 'eye': {'state': 'none', 'why': why},
            'source': 'board', 'native_ppi': record['native_ppi'], 'against_painting': record['against_painting'],
            'reference_source': 'board', 'plain_check': record['plain_check'], 'cost_usd': 0.0,
            'at': timezone.now().isoformat()}


def _outline_redraw(ctx, key, row, n, painting, geometry, claim, plain_faces, outline):
    """A stand face whose outline the shape check changed, drawn once for its new outline: a plain face is the stand's
    board at $0 (board_face); any other is one paid edit refitting its own previous drawing to the new outline, with
    the owner's current words (the policy's keep), under the claim's cap."""
    previous = current(row)
    previous_face = ctx.root / previous['face'] if previous else None
    if key in plain_faces:
        source = _board_source(ctx.build, plain_faces, exclude=key)
        if source is not None and faces.board_fits(key, ctx.brief, geometry, source):
            record = faces.board_face(ctx, key, n, source, geometry, why='its outline changed: ' + outline['reason'])
            return dict(_board_entry(ctx, key, n, record, 'its new outline in the stand\'s board (%s), $0'
                                     % record['board_face']['from']), outline_redraw=outline)
    if previous_face is None:
        raise ValueError('A face whose outline changed has no earlier drawing to refit.')
    stands = json.loads(POLICY.read_text())['flat_stands']
    keep = claim['style']['keep']                   # the claim's words, unless the owner's policy has newer ones
    if ctx.build.round.slug in stands and 'keep' in stands[ctx.build.round.slug]:
        keep = stands[ctx.build.round.slug]['keep']
    claimed_call(ctx, claim, 'face/%s/%d' % (key, n), faces.edit_hold(faces.panel_canvas_size(key, ctx.brief, geometry)))
    record = faces.panel_face(ctx, key, n, painting, geometry, keep=keep, refit=str(previous_face),
                              rules=face_rules(ctx.build, row), quality=faces.face_quality(ctx.build.round, key))
    check = record['against_painting']
    return {'n': n, 'record': _rel(ctx.build, faces.drawing_folder(ctx.root, key, n) / 'record.json'),
            'face': _rel(ctx.build, record['face']), 'face_sha256': record['face_sha256'],
            'reference': _rel(ctx.build, record['reference']['path']), 'reference_sha256': record['reference']['sha256'],
            'painting_view': _rel(ctx.build, Path(painting['view'])),
            'preview': None, 'preview_sha256': None, 'size_mm': None, 'facts': None,
            'eye': {'state': 'none', 'why': 'refitted at %g PPI to its new outline from its drawing %s; against it ΔE00 '
                                            'median %.1f, p90 %.1f' % (record['native_ppi'], outline['of'],
                                                                      check['median'], check['p90'])},
            'source': 'panel', 'native_ppi': record['native_ppi'], 'against_painting': check,
            'reference_source': record['reference_source'], 'plain_check': record['plain_check'],
            'outline_redraw': outline, 'note': '', 'cost_usd': record.get('cost_usd'), 'at': timezone.now().isoformat()}


def _cut(ctx, key, row, n, geometry, claim):
    """A stand face's drawing ``n`` on a flat build: cut straight from the current painting ($0), or — the owner's
    Redraw — that one face repainted on the same template (one paid edit)."""
    painting = faces.current_painting(ctx.root)
    if painting is None:
        raise ValueError('The flat painting of the die is not made yet.')
    if claim.get('wrap'):
        return _wrap_cut(ctx, key, row, n, geometry, claim)
    if claim.get('panels') == 'full':
        previous = current(row)
        previous_face = str(ctx.root / previous['face']) if previous and row.get('note') else None
        plain_faces = _plain_faces(ctx.build, claim)
        plain = key in plain_faces
        outline = row.get('outline_redraw') if row.get('outline_redraw') and 'drawn' not in row['outline_redraw'] else None
        if outline is not None:
            return _outline_redraw(ctx, key, row, n, painting, geometry, claim, plain_faces, outline)
        redo = row.get('system_redraw') if row.get('system_redraw') and 'drawn' not in row['system_redraw'] else None
        if plain and not row.get('note'):
            # a plain face whose board another plain face already gives: tiled from it at $0, never painted (the
            # owner's ruling of 2026-10-29: no repainting of a face whose art is the board)
            source = _board_source(ctx.build, plain_faces, exclude=key)
            if source is not None and faces.board_fits(key, ctx.brief, geometry, source):
                record = faces.board_face(ctx, key, n, source, geometry, why='a plain face: the stand\'s board')
                return dict(_board_entry(ctx, key, n, record, 'a plain face: the stand\'s board (%s), $0'
                                         % record['board_face']['from']), system_redraw=redo)
        quality = faces.face_quality(ctx.build.round, key)
        claimed_call(ctx, claim, 'face/%s/%d' % (key, n),
                     faces.edit_hold(faces.panel_canvas_size(key, ctx.brief, geometry), quality))
        record = faces.panel_face(ctx, key, n, painting, geometry, note=row.get('note', ''), previous=previous_face,
                                  plain=plain, swatch=_swatch(ctx.build, plain_faces) if plain else None,
                                  keep=claim['style']['keep'], system_redraw=redo, rules=face_rules(ctx.build, row),
                                  pattern=_pattern(ctx.build, key), quality=quality)
        check = record['against_painting']
        flags = panel_flags(ctx.build, key, record, plain_faces)
        eye = {'state': 'none', 'why': 'drawn at %g PPI on its own outline from %s; against it ΔE00 median %.1f, p90 '
               '%.1f%s' % (record['native_ppi'], record['reference']['detail'], check['median'], check['p90'],
                           (' — ' + '; '.join(flags) + ': look closely') if flags else '')}
        return {'n': n, 'record': _rel(ctx.build, faces.drawing_folder(ctx.root, key, n) / 'record.json'),
                'face': _rel(ctx.build, record['face']), 'face_sha256': record['face_sha256'],
                'reference': _rel(ctx.build, record['reference']['path']), 'reference_sha256': record['reference']['sha256'],
                'painting_view': _rel(ctx.build, Path(painting['view'])),
                'preview': None, 'preview_sha256': None, 'size_mm': None, 'facts': None, 'eye': eye,
                'source': 'panel', 'native_ppi': record['native_ppi'], 'against_painting': check,
                'reference_source': record['reference_source'], 'plain_check': record['plain_check'],
                'system_redraw': redo, 'flags': flags,
                'note': record.get('note', ''), 'note_withheld': record.get('note_withheld'),
                'cost_usd': record.get('cost_usd'), 'at': timezone.now().isoformat()}
    if row.get('flat_cut'):
        record = faces.flat_face(ctx.root, key, n, painting, geometry)
        eye = {'state': 'none', 'why': 'cut straight from the flat design you see; nothing was drawn to check'}
    else:
        record = faces.repaint_face(ctx, key, n, painting, geometry, ruled_style(ctx.build, claim['style']),
                                    note=row.get('note', ''))
        eye = {'state': 'none', 'why': 'repainted on the flat die; you see it in place on the die'}
    return {'n': n, 'record': _rel(ctx.build, faces.drawing_folder(ctx.root, key, n) / 'record.json'),
            'face': _rel(ctx.build, record['face']), 'face_sha256': record['face_sha256'],
            'reference': _rel(ctx.build, record['face']), 'reference_sha256': record['face_sha256'],
            'painting_view': _rel(ctx.build, Path(record['painting']).parent / 'view.png'),
            'preview': None, 'preview_sha256': None, 'size_mm': None, 'facts': None, 'eye': eye,
            'source': 'flat' if row.get('flat_cut') else 'repainted', 'note': record.get('note', ''),
            'note_withheld': record.get('note_withheld'), 'cost_usd': record.get('cost_usd'),
            'at': timezone.now().isoformat()}


#: the wrap's open panels; the rest of the stand's faces are painted on it, each at its own quality (faces.HIGH_FACES)
def wrap_panels():
    return [key for key in faces.FACES if faces.stand_face(key) and key not in faces.HIGH_FACES]


def wrap_pictures(ctx, painting, geometry):
    """Each stand face's art as it stands, for a wrap's image 2: its current drawing, else its crop of the painting."""
    rows, out = board(RoundMaster.objects.get(pk=ctx.build.pk)), {}
    folder = faces.flat_root(ctx.root) / 'wraps' / 'art'
    folder.mkdir(parents=True, exist_ok=True)
    for key in faces.FACES:
        if faces.stand_face(key):
            entry = current(rows[key])
            if entry:
                out[key] = str(ctx.root / entry['face'])
            else:
                Image.fromarray(faces.painted_face(painting, key, geometry)[0]).save(folder / (key + '.png'))
                out[key] = str(folder / (key + '.png'))
    return out


def _ground(ctx):
    found = faces.design_ground(ctx.build.round)
    return {'ground_hex': found['hex'], 'ground_name': found['name']} if found else {}


def _wrap_rules(build):
    """The owner's hard rules for a painting of several faces: the round's, and every note on any of them."""
    notes = []
    for key, row in board(build).items():
        if faces.stand_face(key):
            for item in [entry.get('note') for entry in row['drawings']] + [row.get('note')]:
                text, withheld = faces.owner_note(item)
                if text and not withheld and text not in notes:
                    notes.append(text)
    from . import round_designer as designer
    return designer.record_rules(build.round, notes)


def _wrap_hold(canvas, quality):
    w, h = canvas['canvas_px']
    return faces.edit_hold(canvas['size'], quality, [(w, h)] * 2)


def _pieces(ctx, claim, geometry):
    """The round's motif library: one paid sheet of picture motifs, cut apart and saved once, its rhythm measured from the
    picked design ($0). A call that failed or was lost is never sent again on its own: the faces say so, and the owner's
    Redraw claims the next sheet."""
    n = int(claim['pieces'].get('sheet', 1))
    folder = faces.motifs_root(ctx.root) / ('sheet-%d' % n)
    if (folder / 'library.json').exists() and (faces.motifs_root(ctx.root) / 'rhythm.json').exists():
        return
    try:
        if any((folder / 'call').glob('image-call.lost.json')) or any((folder / 'call').glob('image-call.error.json')):
            raise ValueError(MOTIFS_LOST)
        painting = faces.current_painting(ctx.root)
        flow.write_json(faces.motifs_root(ctx.root) / 'rhythm.json', faces.measure_rhythm(painting, geometry))
        colours = faces.design_colours(ctx.build.round)
        claimed_call(ctx, claim, 'motif/sheet/%d' % n, faces.sheet_cost()['hold_usd'])
        build = RoundMaster.objects.get(pk=ctx.build.pk)
        faces.paint_sheet(ctx, n, colours=colours, rules=_wrap_rules(build), note=claim['pieces'].get('note', ''))
        flow.commit_artifacts(ctx.round, 'the motif sheet painted and cut')
    except flow.YieldRound:
        raise
    except Exception as exc:
        reason = MOTIFS_LOST if isinstance(exc, LostCall) else ('%s: %s' % (type(exc).__name__, exc))[:600]
        for key in faces.FACES:
            _change(ctx.build.pk, lambda build, key=key: board(build)[key].update(state='failed', error=reason)
                    if board(build)[key]['state'] in ('queued', 'drawing') else None)


MOTIFS_LOST = ('The round\'s motif sheet was lost: no picture came back, and it was checked once and closed. Press Redraw on a '
               'face to paint it again.')


def _plan_entry(ctx, key, row, n, geometry, claim, die):
    """A face's drawing ``n``: placed by the engine from the round's motif library ($0). A Redraw with no note places it again
    on the next seed."""
    library = faces.current_library(ctx.root)
    if library is None:
        raise ValueError('The round\'s motif library is not made yet.')
    rhythm = read(faces.motifs_root(ctx.root) / 'rhythm.json')
    record = faces.draw_plan(ctx.root, key, n, ctx.brief, die, geometry, library, rhythm, faces.design_colours(ctx.build.round), seed=n - 1)
    counts = record.get('counts') or {}
    return {'n': n, 'record': _rel(ctx.build, faces.drawing_folder(ctx.root, key, n) / 'record.json'),
            'face': _rel(ctx.build, record['face']), 'face_sha256': record['face_sha256'],
            'reference': _rel(ctx.build, record['reference']['path']), 'reference_sha256': record['reference']['sha256'],
            'preview': None, 'preview_sha256': None, 'size_mm': None, 'facts': None, 'source': 'plan', 'native_ppi': 300.0,
            'eye': {'state': 'none', 'why': 'placed by the engine from the motif library: %d picture, %d vector'
                                            % (counts.get('picture', 0), counts.get('vector', 0))},
            'press': record['press'], 'placement': record['placement'], 'note': row.get('note', ''), 'cost_usd': 0.0,
            'at': timezone.now().isoformat()}


def resettle(record_id):
    """The views made again, in the worker, at $0: the faces and their accepts untouched."""
    with transaction.atomic():
        build = RoundMaster.objects.select_for_update().select_related('round').get(round_id=record_id)
        if build.state != 'awaiting' or build.current_step != 'faces':
            raise ValueError('Only a build waiting on its faces is settled again.')
        build.steps['faces']['state'] = 'queued'
        _wake(build)
        build.save()


def rebuild_pieces(record_id):
    """The owner's order to rebuild a round through the separate pieces (2026-10-30, §7, round 4): every face back to be placed
    and to await his Accept; its made files stay on disk as history. Its cap is untouched: the sheet's hold is checked at the
    call."""
    with transaction.atomic():
        build = RoundMaster.objects.select_for_update().select_related('round').get(round_id=record_id)
        if not is_gate(build) or build.state in ('queued', 'running'):
            raise ValueError('A running job or a build off the gate is never rebuilt.')
        if flow.rejected(build.round):
            raise ValueError('A rejected round stays as it is.')
        claim = flat_claim(build)
        claim.pop('wrap', None)
        # the library it has is kept: only placing them again, at no cost; with none, its first sheet
        painted = [int(path.parent.name.split('-')[1]) for path in faces.motifs_root(root(build)).glob('sheet-*/library.json')]
        claim['pieces'] = {'sheet': max(painted + [1]), 'at': timezone.now().isoformat()}
        flow.write_json(root(build) / 'flat' / 'claim.json', claim)
        for key, row in board(build).items():
            row.update(state='queued', accepted=None, note='', suggested='', error='', pending_n=None, flat_cut=False, system=None)
        build.steps['files'] = dict(build.steps['files'], state='waiting')
        build.steps['faces']['state'] = 'queued'
        build.current_step, build.publication, build.error = 'faces', {}, ''
        build.state = 'awaiting'
        _wake(build)
        build.save()
    return claim['pieces']


def redie(record_id, *, words, stand_type='counter_tray_header'):
    """The owner's order to solve an existing round's stand on the family's template (part 2, 2026-10-31, §6), at $0: the old stand
    and its template sheet kept in files/superseded, the die solved from the brief and the rules, every face then placed again on
    its new panel from the round's own library (rebuild_pieces), to await his Accept. The picked design's own die (die/) stays as
    the history it is: the design was painted on it."""
    from apps.dielines.geometry import counter_display
    with transaction.atomic():
        build = RoundMaster.objects.select_for_update().select_related('round').get(round_id=record_id)
        if not is_gate(build) or build.state in ('queued', 'running'):
            raise ValueError('A running job or a build off the gate is never solved again.')
        if flow.rejected(build.round):
            raise ValueError('A rejected round stays as it is.')
        folder = root(build)
        old = json.loads((folder / 'stand.json').read_text())
        n = 1
        while (folder / 'superseded' / ('stand-before-%s-%d' % (stand_type, n))).exists():
            n += 1
        target = folder / 'superseded' / ('stand-before-%s-%d' % (stand_type, n))
        target.mkdir(parents=True)
        (folder / 'stand').rename(target / 'stand')
        (folder / 'stand.json').rename(target / 'stand.json')
        (target / 'flat-template').mkdir()
        for name in ('template.json', 'template.png', 'sheet.png', 'owner.npy'):
            if (folder / 'flat' / name).exists():
                (folder / 'flat' / name).rename(target / 'flat-template' / name)
        brief = dict(files_brief(build))
        brief['stand'] = dict(brief.get('stand') or {}, type=stand_type)
        # Illustrator never runs inside this lock: its own .ai is drawn after the build is released
        result = build_stand(brief, None, folder / 'stand', native_sheets=False)
        flow.write_json(folder / 'stand.json', result)
        build.steps['stand']['result'] = json.loads((folder / 'stand.json').read_text())
        faces.flat_setup(result, folder / 'flat')
        flow.write_json(folder / 'redie-claim.json', {
            'schema': 'owner_redie/1', 'at': timezone.now().isoformat(), 'words': words, 'from': old['record'].get('schema'),
            'to': counter_display.TEMPLATE_SCHEMA, 'template': result['record']['template'], 'moved_to': _rel(build, target),
            'changes': result['record'].get('changes', []), 'qualification_passed': result['qualification']['passed']})
        build.save()
    write_die_sheets(result['record'], folder / 'stand' / 'sheets')
    return rebuild_pieces(record_id)


def _wrap(ctx, claim, geometry):
    """The one paid edit a wrap claim's linked faces are cut from (the owner, 2026-10-30): panels that meet at a fold
    painted as one picture, under the round's cap. A call that failed or was lost is never sent again on its own: the
    faces say so, and the owner's Redraw claims the next attempt."""
    attempt = int(claim['wrap']['attempt'])
    if faces.current_wrap(ctx.root, attempt) is not None:
        return
    folder = faces.wrap_folder(ctx.root, 'stand', attempt)
    try:
        if any((folder / 'call').glob('image-call.lost.json')) or any((folder / 'call').glob('image-call.error.json')):
            raise ValueError(WRAP_LOST)
        painting = faces.current_painting(ctx.root)
        if painting is None:
            raise ValueError('The flat painting of the die is not made yet.')
        layout = faces.wrap_layout(faces.stand_panels(geometry), faces.STAND_WRAP)
        open_ = wrap_panels()
        quality = 'medium'
        claimed_call(ctx, claim, 'wrap/stand/%d' % attempt, _wrap_hold(faces.wrap_canvas(layout, open_), quality))
        build = RoundMaster.objects.get(pk=ctx.build.pk)
        faces.paint_wrap(ctx, 'stand', attempt, layout, open_, wrap_pictures(ctx, painting, geometry), keep=claim['style']['keep'],
                         rules=_wrap_rules(build), quality=quality, note=claim['wrap'].get('why', ''), **_ground(ctx))
        flow.commit_artifacts(ctx.round, 'the wrap painted')
    except flow.YieldRound:
        raise
    except Exception as exc:
        reason = WRAP_LOST if isinstance(exc, LostCall) else ('%s: %s' % (type(exc).__name__, exc))[:600]
        for key in wrap_panels():
            _change(ctx.build.pk, lambda build, key=key: board(build)[key].update(state='failed', error=reason)
                    if board(build)[key]['state'] in ('queued', 'drawing') else None)


WRAP_LOST = ('The stand\'s wrap was lost: no picture came back, and it was checked once and closed. Press Redraw on a '
             'stand face to paint it again.')


def _wrap_cut(ctx, key, row, n, geometry, claim):
    """A stand face's drawing ``n`` on a wrap claim: cut from the wrap ($0) the first time; otherwise (the header at its
    own quality, or a Redraw) this face alone repainted on the art it joins, one paid edit, every other face kept."""
    attempt = int(claim['wrap']['attempt'])
    wrap = faces.current_wrap(ctx.root, attempt)
    if wrap is None:
        raise ValueError('The stand\'s wrap is not painted yet.')
    layout = faces.wrap_layout(faces.stand_panels(geometry), faces.STAND_WRAP)
    previous = current(row)
    system = row.get('system') or {}
    if 'restore' in system:
        source = read(ctx.root / next(entry for entry in row['drawings'] if entry['n'] == system['restore'])['record'])
        record = faces.restore_word_place(ctx.root, key, n, source, system['box'], faces.stand_panels(geometry)[key])
        return {'n': n, 'record': _rel(ctx.build, faces.drawing_folder(ctx.root, key, n) / 'record.json'),
                'face': _rel(ctx.build, record['face']), 'face_sha256': record['face_sha256'],
                'reference': _rel(ctx.build, record['reference']['path']), 'reference_sha256': record['reference']['sha256'],
                'preview': None, 'preview_sha256': None, 'size_mm': None, 'facts': None,
                'eye': {'state': 'none', 'why': system['why']}, 'source': 'wrap', 'native_ppi': record['native_ppi'],
                'wrap_n': attempt, 'note': '', 'cost_usd': 0.0, 'at': timezone.now().isoformat()}
    if key in wrap['faces'] and not row.get('note') and (previous or {}).get('wrap_n') != attempt:
        cut = wrap
        why = 'cut from the wrap: nothing drawn again'
    else:
        build = RoundMaster.objects.get(pk=ctx.build.pk)
        rows = board(build)
        context = {other: str(ctx.root / current(rows[other])['face']) for other in faces.FACES
                   if other != key and faces.stand_face(other) and current(rows[other])
                   and current(rows[other]).get('source') == 'wrap'}
        missing = [other for other in wrap['faces'] if other != key and other not in context]
        if missing:
            raise ValueError('Its neighbours are not cut from the wrap yet: ' + ', '.join(missing))
        quality = faces.face_quality(ctx.build.round, key)
        canvas = faces.wrap_canvas(layout, [key], context_mm=faces.WRAP_CONTEXT_MM)
        claimed_call(ctx, claim, 'wrap/%s/%d' % (key, n), _wrap_hold(canvas, quality))
        painting = faces.current_painting(ctx.root)
        pictures = dict(wrap_pictures(ctx, painting, geometry), **context)
        cut = faces.paint_wrap(ctx, key, n, layout, [key], pictures, context=context, keep=claim['style']['keep'],
                               rules=face_rules(build, row), note=row.get('note') or (row.get('system') or {}).get('note', ''),
                               quality=quality, plain=(row.get('system') or {}).get('plain'), **_ground(ctx))
        why = (row.get('system') or {}).get('why') or 'painted on the art it joins, so its folds carry on'
    record = faces.wrap_face(ctx.root, key, n, cut, faces.stand_panels(geometry)[key]['outline'])
    return {'n': n, 'record': _rel(ctx.build, faces.drawing_folder(ctx.root, key, n) / 'record.json'),
            'face': _rel(ctx.build, record['face']), 'face_sha256': record['face_sha256'],
            'reference': _rel(ctx.build, record['reference']['path']), 'reference_sha256': record['reference']['sha256'],
            'preview': None, 'preview_sha256': None, 'size_mm': None, 'facts': None,
            'eye': {'state': 'none', 'why': why}, 'source': 'wrap', 'native_ppi': record['native_ppi'],
            'wrap_n': attempt, 'note': row.get('note', ''), 'cost_usd': cut.get('cost_usd') if cut is not wrap else 0.0,
            'at': timezone.now().isoformat()}


def face_rules(build, row=None):
    """The owner's hard rules for a face's drawing (the owner, 2026-10-29, round 4: "My pick reason and my redraw
    notes must reach every face drawing as hard rules"): the round's banned motifs, the owner's lines on the round
    and every note the owner gave this face."""
    from . import round_designer as designer
    notes = []
    if row is not None:
        for item in [entry.get('note') for entry in row['drawings']] + [row.get('note')]:
            text, withheld = faces.owner_note(item)
            if text and not withheld and text not in notes:     # a note about the words is never drawn (owner_note)
                notes.append(text)
    return designer.record_rules(build.round, notes)


def ruled_style(build, style):
    """A painting's style with the owner's hard rules after its own words."""
    keep = [style[name] for name in ('keep',) if style.get(name)] + [face_rules(build)]
    return dict(style, keep='\n\n'.join(part for part in keep if part))


def _pattern(build, key):
    """The drawing a wall follows when it shares the back panel's pattern and the back is drawn: its record."""
    source = faces.WALL_PATTERN.get(key)
    if source is None:
        return None
    entry = current(board(build)[source])
    if entry is None or entry.get('source') != 'panel':
        return None
    return json.loads((root(build) / entry['record']).read_text())


def _draw(ctx, key, row, inspection, die, geometry=None):
    """The face's next drawing: a resumed one keeps its number (its folder knows whether it was paid for); a new one
    takes the next free folder, never one a lost call left behind."""
    used = [entry['n'] for entry in row['drawings']]
    used += [int(path.name) for path in (ctx.root / 'faces' / key / 'drawings').glob('*') if path.name.isdigit()]
    n = row.get('pending_n') or max(used + [0]) + 1
    _set_face(ctx.build.pk, key, state='drawing', pending_n=n, error='')
    claim = flat_claim(ctx.build)
    if claim is not None and claim.get('pieces'):
        entry = _plan_entry(ctx, key, row, n, geometry, claim, die)

        def placed(build):
            face = board(build)[key]
            face['drawings'].append(entry)
            face.update(state='drawn', drawing=n, pending_n=None, note='', suggested='', accepted=None, error='', flat_cut=False)
        _change(ctx.build.pk, placed)
        return
    if faces.stand_face(key):
        if claim is None:
            raise ValueError('A stand face is cut from the stand\'s flat design, and this build has none.')
        entry = _cut(ctx, key, row, n, geometry, claim)

        def cut(build):
            face = board(build)[key]
            face['drawings'].append(entry)
            face.update(state='drawn', drawing=n, pending_n=None, note='', suggested='', accepted=None, error='',
                        flat_cut=False, system=None)
            if entry.get('system_redraw'):
                face['system_redraw'] = dict(face['system_redraw'], drawn=n)     # made: the face is the owner's now
            if entry.get('outline_redraw'):
                face['outline_redraw'] = dict(face['outline_redraw'], drawn=n)   # drawn for its new outline, once
        _change(ctx.build.pk, cut)
        return
    previous = current(row)
    previous_face = (root(ctx.build) / previous['face']) if previous and row.get('note') else None
    if claim is not None and claim.get('product_nets'):
        # die-first for the products (the owner's goal of 2026-10-29): the face painted on its own flat net
        _die, setup = faces.net_setup(key, ctx.brief, faces.drawing_folder(ctx.root, key, n))
        quality = faces.face_quality(ctx.build.round, key)
        claimed_call(ctx, claim, 'face/%s/%d' % (key, n), faces.edit_hold(setup['frame']['size'], quality))
        previous_net = (root(ctx.build) / json.loads((root(ctx.build) / previous['record']).read_text())['net']['flat']
                        if previous_face and previous.get('source') == 'net' else previous_face)
        record = faces.draw_net(ctx, key, n, inspection, note=row.get('note'),
                                previous=str(previous_net) if previous_net else None, rules=face_rules(ctx.build, row),
                                quality=quality)
    else:
        record = faces.draw_face(ctx, key, n, faces.face_geometry(key, ctx.brief, die), inspection, note=row.get('note'),
                                 previous=str(previous_face) if previous_face else None, rules=face_rules(ctx.build, row))
    entry = {'n': n, 'record': _rel(ctx.build, faces.drawing_folder(ctx.root, key, n) / 'record.json'),
             'face': _rel(ctx.build, record['face']), 'face_sha256': record['face_sha256'],
             'reference': _rel(ctx.build, record['reference']['path']), 'reference_sha256': record['reference']['sha256'],
             'preview': None, 'preview_sha256': None, 'size_mm': None, 'facts': None,
             'eye': {'state': 'pending'}, 'source': 'net' if 'net' in record else 'drawn', 'note': record.get('note', ''),
             'note_withheld': record.get('note_withheld'), 'cost_usd': record.get('cost_usd'),
             'at': timezone.now().isoformat()}

    def done(build):
        face = board(build)[key]
        face['drawings'].append(entry)
        face.update(state='drawn', drawing=n, pending_n=None, note='', suggested='', accepted=None, error='')
    _change(ctx.build.pk, done)


def preview(ctx, key, entry, inspection, die):
    """The face as it will be written: its drawing, live type and logo through the writer (export_object, PDF-only:
    the Illustrator save-and-reopen is the files' own check), rendered flat at its trim, on white."""
    from .round_files_export import export_object, render_flat
    record = json.loads((ctx.root / entry['record']).read_text())
    if sha(record['face']) != record['face_sha256']:
        raise ValueError('A drawn face changed after it was cut.')
    folder = ctx.root / 'faces' / key / 'previews' / str(entry['n'])
    spec, trim = faces.face_spec(key, record, inspection, ctx.brief, die, 'preview-%s-%d' % (key, entry['n']))
    written = export_object(spec, folder, native=False)
    raw = folder / 'trim.png'
    render_flat(written['ai'], raw, dpi=200, clip_mm=trim)
    with Image.open(raw) as image:
        rgba = np.asarray(image.convert('RGBA')).astype(np.float64)
    alpha = rgba[..., 3:4] / 255
    out = folder / 'preview.png'
    Image.fromarray(np.round(rgba[..., :3] * alpha + 255 * (1 - alpha)).astype(np.uint8)).save(out)
    placed = faces.upright_marks(key, faces.upright_face(key, ctx.brief, die), inspection, ctx.brief, record).get('placement')
    return {'preview': _rel(ctx.build, out), 'preview_sha256': sha(out), 'size_mm': drawn_size(key, record),
            'type_revision': faces.TYPE_REVISION, 'words_lost': bool(placed and 'why' in placed),
            'facts': faces.face_facts(key, spec['type_runs'])}


def drawn_size(key, record):
    """The size (w × h mm, 0.1) the drawing was made for: its template's frame less the bleed (a face cut from the flat
    painting: its die face's). A die that changes the face's size marks it "needs Redraw (size changed)"."""
    bleed = faces.STAND_BLEED_MM if faces.stand_face(key) else 0.0
    W, H = record['template']['frame_mm']
    return [round(W - 2 * bleed, 1), round(H - 2 * bleed, 1)]


def advise(ctx, key, entry, geometry):
    """The eye's notes on one drawing: once, cheap, advice only."""
    count = '%d (%d rows × %d across)' % (geometry['count'], geometry['rows'], geometry['columns'])
    folder = faces.drawing_folder(ctx.root, key, entry['n'])
    call = ctx.text_call('eye/%s/%d' % (key, entry['n']), faces.advice_prompt(key, entry['facts'], count),
                         folder / 'eye.json', images=[('The picked picture, unchanged', ctx.root / 'source.png'),
                                                      ('The picture\'s view of this face', ctx.root / entry['reference']),
                                                      ('The face as built for print', ctx.root / entry['preview'])],
                         max_tokens=4096, ceiling=1.0)
    look = faces.validate_look(call['payload'])
    return dict(look, state='done', source='the eye on this drawing', cost_usd=call.get('cost_usd'))


PAINTING_LOST = ('The stand\'s flat painting was lost: no reply came back, and it was checked once and closed. '
                 'Press Redraw on a stand face to paint the die again.')


def _paint(ctx, claim, geometry):
    """The flat painting a flat build's stand faces are cut from: the claim's own attempt, one paid edit of the
    engine's die, under the claim's cap (``budget_usd``) inside the round's one cap. An attempt whose call failed or
    was lost is never sent again and never followed by another on its own: only the owner's say (a Redraw, or the
    policy's next attempt) claims the next. A failure marks the waiting stand faces with its reason; the bottle and
    cap go on."""
    n = int(claim.get('attempt', 1))
    folder = faces.flat_root(ctx.root) / 'paintings' / str(n)
    if (folder / 'record.json').exists():
        if faces.current_painting(ctx.root) is None:
            faces.paint_flat(ctx, n, geometry, ruled_style(ctx.build, claim['style']))
        return
    try:
        if any((folder / 'call').glob('image-call.lost.json')) or any((folder / 'call').glob('image-call.error.json')):
            raise ValueError(PAINTING_LOST)
        if not (folder / 'call' / 'image-call.json').exists():
            spent = claim_spend(ctx.build, claim)
            if spent + faces.EDIT_HOLD_USD > claim['budget_usd'] + 1e-9:
                raise ValueError('The flat painting would pass its $%g cap ($%.2f spent).' % (claim['budget_usd'], spent))
        painting = faces.paint_flat(ctx, n, geometry, ruled_style(ctx.build, claim['style']))
        flow.commit_artifacts(ctx.round, 'flat stand painted on the engine\'s die')
        flat_drawings(ctx, painting, geometry)
    except flow.YieldRound:
        raise
    except Exception as exc:
        reason = PAINTING_LOST if isinstance(exc, LostCall) else ('%s: %s' % (type(exc).__name__, exc))[:600]
        for key in faces.FACES:
            if faces.stand_face(key):
                _change(ctx.build.pk, lambda build, key=key: board(build)[key].update(state='failed', error=reason)
                        if board(build)[key]['state'] in ('queued', 'drawing') else None)


def _reset_stand(build):
    """Every stand face waits to be cut from the claim's painting."""
    rows = board(build)
    for key in faces.FACES:
        if faces.stand_face(key):
            row = rows.get(key) or empty_face(key)
            row.update(label=faces.FACES[key]['label'], state='queued', flat_cut=True, accepted=None, note='',
                       suggested='', error='', pending_n=None)
            rows[key] = row
    build.steps['faces']['board'] = {key: rows[key] for key in faces.FACES if key in rows}


def flat_drawings(ctx, painting, geometry):
    """Beside a flat painting, our own drawings of it ($0): the stand folded and empty, and loaded with the products
    (product_drawing; the bottle and cap as they are drawn now, without their words)."""
    from .round_files_faces import shade_loading
    folder = Path(painting['flat']).parent
    if (folder / 'drawings.json').exists():
        return json.loads((folder / 'drawings.json').read_text())
    views, cut = {}, folder / 'faces'
    cut.mkdir(parents=True, exist_ok=True)
    for key in faces.FACES:
        if faces.stand_face(key):
            upright, frame_mm, _box = faces.painted_face(painting, key, geometry)
            faces.trim_view(upright, frame_mm).save(cut / (key + '.png'))
            views[key] = str(cut / (key + '.png'))
    folded = faces.folded_drawing(views, geometry, folder / 'drawing')
    out = {'folded': _rel(ctx.build, folded['file']), 'folded_sha256': folded['sha256'], 'loaded': None}
    product = {key: current(row) for key, row in board(RoundMaster.objects.get(pk=ctx.build.pk)).items()
               if not faces.stand_face(key)}
    if all(entry and entry.get('face') for entry in product.values()):
        for key, entry in product.items():
            views[key] = str(ctx.root / entry['face'])
        inspection = json.loads((ctx.root / 'inspection.json').read_text())
        loaded = faces.drawing(views, ctx.brief, geometry, shade_loading(inspection, ctx.brief), folder / 'loaded')
        out.update(loaded=_rel(ctx.build, loaded['file']), loaded_sha256=loaded['sha256'])
    flow.write_json(folder / 'drawings.json', out)
    return out


def panel_drawings(ctx):
    """Once every stand face of a panels-'full' claim has its current panel drawing ($0, the owner's goal of
    2026-10-29): the stand folded, and loaded with the products, drawn again from those drawings — what will print —
    beside the painting's own drawings (flat/panels/<faces' digest>/; flat/panels/current.json the latest)."""
    from .round_files_faces import shade_loading
    claim, build = flat_claim(ctx.build), RoundMaster.objects.get(pk=ctx.build.pk)
    if claim is None or claim.get('panels') != 'full':
        return None
    rows = board(build)
    entries = {key: current(rows[key]) for key in faces.FACES if key in rows}
    stand = [key for key in faces.FACES if faces.stand_face(key)]
    if any(not entries.get(key) or entries[key].get('source') not in faces.UPRIGHT_SOURCES for key in stand):
        return None
    geometry = read(ctx.root / 'stand.json')
    # the views belong to the faces and to the die they fold on: a new die draws them again, at $0
    signature = digest(dict({key: entry['face_sha256'] for key, entry in entries.items() if entry}, die=digest(geometry['record']), views=VIEWS_REVISION))[:16]
    folder = ctx.root / 'flat' / 'panels' / signature
    if (folder / 'drawings.json').exists():
        return read(folder / 'drawings.json')
    found = faces.design_ground(ctx.build.round)
    ground_hex = found['hex'] if found else None
    views, cut = {}, folder / 'faces'
    cut.mkdir(parents=True, exist_ok=True)
    for key in stand:
        record = _panel_record(build, entries[key])
        with Image.open(record['face']) as image:
            upright = np.asarray(image.convert('RGB'))
        faces.trim_view(upright, record['template']['frame_mm']).save(cut / (key + '.png'))
        views[key] = str(cut / (key + '.png'))
    folded = faces.folded_drawing(views, geometry, folder / 'drawing', ground_hex=ground_hex)
    round_view = faces.three_quarter_drawing(views, geometry, folder / 'three-quarter', ground_hex=ground_hex)
    out = {'signature': signature, 'folded': _rel(build, folded['file']), 'folded_sha256': folded['sha256'],
           'three_quarter': _rel(build, round_view['file']), 'three_quarter_sha256': round_view['sha256'],
           'loaded': None, 'rule': 'drawn from the current panel drawings, accepted or not: what will print'}
    products = {key: _panel_record(build, entries[key]) for key in faces.FACES
                if not faces.stand_face(key) and entries.get(key) and entries[key].get('face')}
    if len(products) == len([key for key in faces.FACES if not faces.stand_face(key)]):
        for key, record in products.items():
            views[key] = record['face']
            if key in faces.CLEAR_FACES and record.get('source') == 'plan' and _liquid(ctx):
                views[key] = faces.on_liquid(record['face'], _liquid(ctx), cut / (key + '.png'))
        loaded = faces.drawing(views, ctx.brief, geometry, shade_loading(read(ctx.root / 'inspection.json'), ctx.brief),
                               folder / 'loaded', sides=faces.net_sides(products), ground_hex=ground_hex)
        out.update(loaded=_rel(build, loaded['file']), loaded_sha256=loaded['sha256'])
    flow.write_json(folder / 'drawings.json', out)
    flow.write_json(ctx.root / 'flat' / 'panels' / 'current.json', out)
    return out


MM = 72 / 25.4                                   # PDF points per millimetre


#: the folded and loaded views' own revision: the stand fitted to its frame; what stands behind the products
VIEWS_REVISION = 'fitted+inside-ground/2026-10-31'
#: the proof sheet's own revision (a sheet made before it is made again); a word on a net under LEGIBLE_PT is flagged
PROOF_REVISION = 'net-type/2026-10-29'
LEGIBLE_PT = 5.0


def proof_sheet(ctx):
    """The owner's proof before his Accept ($0, the owner's goal of 2026-10-29): one PDF page at real size with the
    stand's die at 1:1 (its cut and crease and its art composed at 300 PPI from the CURRENT drawings, with their live
    type, through the writer) and the bottle's and cap's nets at 1:1 with their lines, each labelled, a 10 mm scale bar
    and a title; a PNG preview beside it (proof/<faces' digest>/; proof/current.json the latest)."""
    import fitz
    from apps.dielines.geometry import counter_display as cd
    from .round_files_export import export_object
    build = RoundMaster.objects.get(pk=ctx.build.pk)
    rows = board(build)
    if any(pending(row) or current(row) is None for row in rows.values()):
        return None
    drawn = {key: _panel_record(build, current(row)) for key, row in rows.items()}
    signature = digest(dict({key: record['face_sha256'] for key, record in drawn.items()}, type=faces.TYPE_REVISION,
                            proof=PROOF_REVISION))[:16]
    folder = ctx.root / 'proof' / signature
    if (folder / 'proof.json').exists():
        made = read(folder / 'proof.json')
        flow.write_json(ctx.root / 'proof' / 'current.json', made)       # the round's proof is the one for these drawings
        return made
    folder.mkdir(parents=True, exist_ok=True)
    geometry, inspection = read(ctx.root / 'stand.json'), read(ctx.root / 'inspection.json')
    specs_, _placements = faces.specs(drawn, inspection, ctx.brief, geometry, folder / 'specs')
    stand_spec = next(spec for spec in specs_ if spec['id'] == 'stand')
    stand = export_object(stand_spec, folder / 'stand', native=False)
    W, H = geometry['sheet_mm']
    nets = []
    for key in ('bottle', 'cap'):
        record = drawn[key]
        if record.get('source') != 'net':
            continue
        template = read(Path(record['face']).parent / 'net.json')
        lines = cd.layer_geometry(faces.product_net(key, ctx.brief))
        nets.append({'key': key, 'art': record['net']['art'], 'frame': template['frame'], 'lines': lines,
                     'faces': template['faces'], 'type': [], 'logos': [],
                     'label': '%s net, 1:1 (%s)' % (faces.FACES[key]['label'].split()[0], record['net']['art'].rsplit('/', 1)[-1])})
    pieces = [(key, next(item for item in specs_ if item['id'] == faces.FACES[key]['object'])) for key in ('bottle', 'cap')
              if drawn[key].get('source') == 'plan']     # a placed product's front at 1:1, as its file makes it
    margin, title, gap = 10.0, 22.0, 15.0
    net_w = max([net['frame']['frame_mm'][2] - net['frame']['frame_mm'][0] for net in nets] + [0.0])
    net_h = sum(net['frame']['frame_mm'][3] - net['frame']['frame_mm'][1] + 12.0 for net in nets)
    net_w = max([net_w] + [spec['size_mm'][0] for _key, spec in pieces])
    net_h += sum(spec['size_mm'][1] + 12.0 for _key, spec in pieces)
    beside = [gap + net_w] if nets or pieces else []        # the products' column, when there are any
    page_w = margin + W + sum(beside) + margin
    page_h = title + max(H, net_h) + margin + 8.0
    doc = fitz.open()
    page = doc.new_page(width=page_w * MM, height=page_h * MM)
    with fitz.open(stand['ai']) as source:
        page.show_pdf_page(fitz.Rect(margin * MM, title * MM, (margin + W) * MM, (title + H) * MM), source, 0)
    template = geometry['record'].get('template') or {}
    page.insert_text((margin * MM, (title - 4) * MM), 'Stand die, 1:1 — %s/%s, its art at 300 ppi from the current drawings'
                     % (template.get('id', cd.TEMPLATE_ID), template.get('version', cd.VERSION)), fontsize=8)
    y = title
    for net in nets:
        fx0, fy0, fx1, fy1 = net['frame']['frame_mm']
        k, (ox, oy), (cw, ch) = net['frame']['px_per_mm'], net['frame']['offset_px'], net['frame']['canvas_px']
        nx = margin + W + gap - fx0
        ny = y + 4.0 - fy0
        page.insert_image(fitz.Rect((nx - ox / k) * MM, (ny - oy / k) * MM, (nx + (cw - ox) / k) * MM,
                                    (ny + (ch - oy) / k) * MM), filename=net['art'])
        for kind, dashes in (('cut', None), ('crease', '[2 2] 0')):
            for line in net['lines'][kind]:
                page.draw_polyline([fitz.Point((nx + px) * MM, (ny + py) * MM) for px, py in line], color=(0, 0, 0),
                                   width=0.4, dashes=dashes)
        # the product's front as its file makes it, on the net's front panel at 1:1: its painting, its live type and the
        # vector logo (the owner's goal of 2026-10-29, §5: the bottle's net shows the logo, the product and the shade)
        spec = next((item for item in specs_ if item['id'] == faces.FACES[net['key']]['object']), None)
        if spec is not None:
            bx0, by0, bx1, by1 = next(face for face in net['faces'] if face['name'] == 'front')['box_mm']
            made = export_object(spec, folder / ('net-' + net['key']), native=False)
            with fitz.open(made['ai']) as source:
                page.show_pdf_page(fitz.Rect((nx + bx0) * MM, (ny + by0) * MM, (nx + bx1) * MM, (ny + by1) * MM), source, 0)
            net['type'] = [{'copy': run['copy'], 'size_pt': round(run['size_pt'], 2), 'legible': run['size_pt'] >= LEGIBLE_PT}
                           for run in spec['type_runs']]
            net['logos'] = [{'box_mm': [round(v, 2) for v in logo['box_mm']],
                             'short_side_mm': round(min(logo['box_mm'][2] - logo['box_mm'][0],
                                                        logo['box_mm'][3] - logo['box_mm'][1]), 2)}
                            for logo in spec['logos']]
        page.insert_text(((margin + W + gap) * MM, (y + 2.5) * MM), net['label'], fontsize=7)
        y += fy1 - fy0 + 12.0
    for key, spec in pieces:
        made = export_object(spec, folder / ('front-' + key), native=False)
        w_, h_ = spec['size_mm']
        with fitz.open(made['ai']) as source:
            page.show_pdf_page(fitz.Rect((margin + W + gap) * MM, (y + 4.0) * MM, (margin + W + gap + w_) * MM, (y + 4.0 + h_) * MM), source, 0)
        page.insert_text(((margin + W + gap) * MM, (y + 2.5) * MM), '%s front, 1:1' % faces.FACES[key]['label'].split()[0], fontsize=7)
        y += h_ + 12.0
    x0, yb = margin, page_h - 6.0
    page.draw_line(fitz.Point(x0 * MM, yb * MM), fitz.Point((x0 + 10) * MM, yb * MM), color=(0, 0, 0), width=0.8)
    for tick in (0, 10):
        page.draw_line(fitz.Point((x0 + tick) * MM, (yb - 1.5) * MM), fitz.Point((x0 + tick) * MM, (yb + 1.5) * MM),
                       color=(0, 0, 0), width=0.8)
    page.insert_text(((x0 + 12) * MM, (yb + 1) * MM), '10 mm (print at 100%%: this page is %.0f × %.0f mm)' % (page_w, page_h),
                     fontsize=7)
    page.insert_text((margin * MM, 9 * MM), 'Proof — not yet accepted · %s · %s · %s' % (
        build.round.slug, timezone.localdate().isoformat(), 'every face as currently drawn'), fontsize=10)
    pdf, png = folder / 'proof-sheet.pdf', folder / 'proof-sheet.png'
    doc.save(pdf)
    page.get_pixmap(dpi=72).save(png)
    doc.close()
    out = {'schema': 'owner_proof_sheet/1', 'signature': signature, 'pdf': _rel(build, pdf), 'png': _rel(build, png),
           'pdf_sha256': sha(pdf), 'png_sha256': sha(png), 'page_mm': [round(page_w, 3), round(page_h, 3)],
           'stand_mm': [W, H], 'nets': [{'key': net['key'], 'frame_mm': net['frame']['frame_mm'],
                                         'dpi_at_1to1': net['frame']['dpi_at_1to1'], 'type': net['type'],
                                         'logos': net['logos'],
                                         'legible': all(row['legible'] for row in net['type'])} for net in nets],
           'faces': {key: record['face_sha256'] for key, record in drawn.items()},
           'accepted': {key: bool(row.get('accepted')) for key, row in rows.items()},
           'rule': 'real size: print at 100%; the stand art at 300 PPI; not yet accepted'}
    flow.write_json(folder / 'proof.json', out)
    flow.write_json(ctx.root / 'proof' / 'current.json', out)
    return out


def _illustrator_proofs(ctx, build, folder):
    """The owner's proof before his Accept (§6), on copies in the worker: each file written through Illustrator's own save; then
    Illustrator lists every layer and object, moves three motifs, hides the ground and unlocks the die, a picture of each."""
    from .round_files_export import export_object, illustrator_proof
    if not ctx.native:
        return {'run': False, 'why': 'a fixture: Illustrator is not asked'}
    drawn = {key: _panel_record(build, current(row)) for key, row in board(build).items()}
    specs_, _p = faces.specs(drawn, read(ctx.root / 'inspection.json'), ctx.brief, read(ctx.root / 'stand.json'), folder / 'illustrator' / 'specs')
    out = {'run': True, 'files': []}
    for spec in specs_:
        made = export_object(spec, folder / 'illustrator' / spec['id'], native=True)
        motifs = spec.get('motifs', [])
        pictures = [item['name'] for item in motifs if item['kind'] == 'picture']
        vectors = [item['name'] for item in motifs if item['kind'] == 'vector'] + [item['name'] for item in spec.get('finishes', [])]
        chosen = (pictures[:2] + vectors[:1]) if len(pictures) >= 2 else (pictures + vectors)[:3]
        proof = illustrator_proof(made['ai'], folder / 'illustrator' / spec['id'] / 'proof', chosen)
        checked = read(folder / 'illustrator' / spec['id'] / (spec['id'] + '.print-check.json'))
        shots = []
        for name in proof.get('steps', []):
            path = folder / 'illustrator' / spec['id'] / 'proof' / (name + '.png')
            shots.append({'step': name, 'png': _rel(build, path), 'sha256': sha(path)})
        out['files'].append({'id': spec['id'], 'layers': proof.get('layers', []), 'moved': proof.get('moved', []), 'text_frames': proof.get('textFrames'),
                             'rasters': proof.get('rasters'), 'die_locked_as_saved': proof.get('die_locked_as_saved'), 'error': proof.get('error'),
                             'shots': shots, 'law': checked.get('law'), 'holds': checked['holds'], 'faults': checked['faults'],
                             'validated': made['readback']['native_illustrator_validated'], 'mb': round(Path(made['ai']).stat().st_size / 1e6, 1)})
    return out


def pieces_view(ctx):
    """The owner's "what you'll get" page ($0): the stand file's layers, each rendered alone, stacked and apart; the motif
    library, each piece; the house library's ranking; every check; the folds at 400 %. Made from the proof's own stand file."""
    import fitz
    from .round_files_export import LAYERS, PT, render_flat, set_layers
    build = RoundMaster.objects.get(pk=ctx.build.pk)
    claim, sheet = flat_claim(build), read(ctx.root / 'proof' / 'current.json') if (ctx.root / 'proof' / 'current.json').exists() else None
    if claim is None or not claim.get('pieces') or sheet is None:
        return None
    folder = ctx.root / 'pieces' / sheet['signature']
    made_path = ctx.root / 'pieces' / 'current.json'
    if (folder / 'pieces.json').exists():
        flow.write_json(made_path, read(folder / 'pieces.json'))
        return read(folder / 'pieces.json')
    folder.mkdir(parents=True, exist_ok=True)
    geometry = read(ctx.root / 'stand.json')
    stand_ai = ctx.root / 'proof' / sheet['signature'] / 'stand' / 'stand.ai'
    layers = []
    for name in LAYERS:
        with fitz.open(stand_ai) as doc:
            set_layers(doc, {name})
            with fitz.open(stream=doc.tobytes(), filetype='pdf') as fresh:
                pix = fresh[0].get_pixmap(dpi=60, alpha=True)
        out = folder / ('layer-%s.png' % name.lower())
        pix.save(out)
        layers.append({'layer': name, 'png': _rel(build, out), 'sha256': sha(out)})
    seams = faces.seam_proof(stand_ai, faces.die_of(geometry), folder / 'seams')
    for row in seams['creases']:
        row['picture'], row['sha256'] = _rel(build, Path(row['picture'])), sha(row['picture'])
    library = faces.current_library(ctx.root) or {}
    plans, checks = {}, {}
    rows = board(build)
    for key, row in rows.items():
        entry = current(row)
        record = _panel_record(build, entry)
        plan = read(record['plan'])
        plans[key] = {'motifs': len(plan['motifs']), 'pictures': (plan.get('counts') or {}).get('picture', 0),
                      'vectors': (plan.get('counts') or {}).get('vector', 0), 'finishes': len(plan['finishes']), 'zones': len(plan['zones'])}
        checks[key] = {'label': row['label'], 'quiet_zones_entered': sum(1 for fault in plan['placement']['faults'] if fault['rule'] == 'enters a quiet zone'),
                       'crossings': sum(1 for fault in plan['placement']['faults'] if fault['rule'] == 'crosses a fold or cut line'),
                       'collisions': sum(1 for fault in plan['placement']['faults'] if fault['rule'] == 'collides'),
                       'contrast': plan['placement']['contrast'], 'lowest_ppi': plan['press']['lowest_ppi'],
                       'dropped_to_ink': plan['press']['dropped_to_ink'], 'press_failed': plan['press']['failed'],
                       'placement_holds': plan['placement']['holds'], 'press_holds': plan['press']['holds']}
    pieces = []
    for piece in library.get('pictures', []):
        pieces.append({'id': piece['id'], 'name': piece['name'], 'register': piece['register'], 'png': _rel(build, Path(piece['file'])), 'sha256': piece['sha256'],
                       'max_mm': piece['max_mm'], 'colours': piece['colours']})
    made = {'schema': 'what_you_get/1', 'signature': sheet['signature'], 'layers': layers, 'library': pieces, 'dropped': library.get('dropped', []),
            'illustrator': _illustrator_proofs(ctx, build, folder),
            'sheet_cost_usd': library.get('cost_usd'), 'plans': plans, 'checks': checks, 'seams': seams,
            'rhythm': read(faces.motifs_root(ctx.root) / 'rhythm.json'), 'house_library': faces.library_supporting(build.round),
            'at': timezone.now().isoformat()}
    flow.write_json(folder / 'pieces.json', made)
    flow.write_json(made_path, made)
    return made


def rules_view(ctx):
    """The owner's painted rules on the raster that prints ($0, the owner, 2026-10-30): every panel's ground, every fold;
    the proof of what the wrap made, shown beside it (flat/rules.json)."""
    build = RoundMaster.objects.get(pk=ctx.build.pk)
    rows = board(build)
    if any(current(row) is None for key, row in rows.items() if faces.stand_face(key)):
        return None
    drawn = {key: _panel_record(build, current(row)) for key, row in rows.items() if faces.stand_face(key)}
    found = faces.design_ground(build.round)
    made = dict(faces.print_rules(drawn, read(ctx.root / 'stand.json'), found['hex'] if found else None),
                faces={key: record['face_sha256'] for key, record in drawn.items()}, own_ground=faces.OWN_GROUND,
                at=timezone.now().isoformat())
    flow.write_json(ctx.root / 'flat' / 'rules.json', made)
    return made


def _settled_view(make, ctx, name):
    """One $0 view made when the faces settle; its failure is recorded in words (proof/<name>-error.json) and shown,
    never blocking the owner's gate."""
    try:
        made = make(ctx)
        (ctx.root / 'proof' / ('%s-error.json' % name)).unlink(missing_ok=True)
        return made
    except flow.YieldRound:
        raise
    except Exception as exc:
        error = {'view': name, 'error': ('%s: %s' % (type(exc).__name__, exc))[:600], 'at': timezone.now().isoformat()}
        flow.write_json(ctx.root / 'proof' / ('%s-error.json' % name), error)
        return error


def settle_views(ctx):
    """When no face has a job left: the folded and loaded drawings from the panels, and the proof sheet ($0)."""
    return {'panels': _settled_view(panel_drawings, ctx, 'panels'), 'proof': _settled_view(proof_sheet, ctx, 'proof'),
            'rules': _settled_view(rules_view, ctx, 'rules'), 'pieces': _settled_view(pieces_view, ctx, 'pieces')}


def work(ctx):
    """One delivery of face work: each face's next job in order. A face that fails is marked, with its reason, and the
    others go on; YieldRound (one paid call per delivery) re-queues. Returns True while any face still has a job."""
    inspection = json.loads((ctx.root / 'inspection.json').read_text())
    geometry = json.loads((ctx.root / 'stand.json').read_text())
    die = faces.die_of(geometry)
    recheck_lost(ctx.build)                         # a lost call's outcome, asked again before anything is bought
    claim = flat_claim(ctx.build)
    if claim is not None:
        _paint(ctx, claim, geometry)
        if claim.get('wrap'):
            _wrap(ctx, claim, geometry)
        if claim.get('pieces'):
            _pieces(ctx, claim, geometry)
    refused = None
    # the back panel before the walls that share its pattern, so they follow its drawing (the owner, 2026-10-29); on a
    # wrap, the faces cut from it before any face painted on what they join
    order = (lambda name: name in faces.HIGH_FACES) if claim is not None and claim.get('wrap') else (
        lambda name: name in faces.WALL_PATTERN)
    for key in sorted(faces.FACES, key=order):
        row = board(RoundMaster.objects.get(pk=ctx.build.pk)).get(key)
        if row is None:                                   # a board from before every printed face was a face
            continue
        job = pending(row)
        if job == 'draw' and refused is not None:
            # the image account has no credits: no other face's call is sent in this delivery (round 4, 2026-10-29)
            _set_face(ctx.build.pk, key, state='failed', pending_n=None, error='Not sent: ' + refused)
            continue
        try:
            if job == 'draw':
                _draw(ctx, key, row, inspection, die, geometry)
                row = board(RoundMaster.objects.get(pk=ctx.build.pk))[key]
                job = pending(row)
            if job == 'preview':
                made = preview(ctx, key, current(row), inspection, die)
                n = row['drawing']
                _change(ctx.build.pk, lambda build: current(board(build)[key]).update(made)
                        if board(build)[key]['drawing'] == n else None)
                row = board(RoundMaster.objects.get(pk=ctx.build.pk))[key]
                job = pending(row)
            if job == 'eye':
                n = row['drawing']
                try:
                    eye = advise(ctx, key, current(row), geometry)
                except flow.YieldRound:
                    raise
                except Exception as exc:
                    eye = {'state': 'unavailable', 'error': str(exc)[:300]}
                _change(ctx.build.pk, lambda build: current(board(build)[key]).update(eye=eye)
                        if board(build)[key]['drawing'] == n else None)
        except flow.YieldRound:
            raise
        except Exception as exc:
            reason = ('%s: %s' % (type(exc).__name__, exc))[:600]
            if job == 'draw':
                _set_face(ctx.build.pk, key, state='failed', pending_n=None, error=reason)
                if out_of_credits(reason):
                    refused = reason
            else:
                n = row['drawing']
                _change(ctx.build.pk, lambda build: current(board(build)[key]).update(preview_error=reason)
                        if board(build)[key]['drawing'] == n else None)
    fresh = RoundMaster.objects.get(pk=ctx.build.pk)
    return any(pending(row) for row in board(fresh).values())


# --- the owner's actions (the web) ------------------------------------------------------------------------------------

def _owned_gate(record_id, user):
    build = RoundMaster.objects.select_for_update().select_related('round').get(round_id=record_id)
    flow._owner(build.round, user)
    if not is_gate(build):
        raise ValueError('These files are not built face by face.')
    return build


def _wake(build):
    if build.state not in ('queued', 'running'):
        build.state, build.error = 'queued', ''
        pk = build.pk
        transaction.on_commit(lambda: enqueue(pk))


def accept(record_id, user, key, n):
    with transaction.atomic():
        build = _owned_gate(record_id, user)
        row = board(build).get(key)
        entry = current(row) if row else None
        if row is None or row['state'] != 'drawn' or entry is None or entry['n'] != n:
            raise ValueError('That drawing is not the one awaiting your Accept.')
        if entry.get('preview') is None:
            raise ValueError('The face\'s preview is still being made.')
        size = die_sizes(build)[key]
        if entry['size_mm'] != size:
            raise ValueError('The die changed this face\'s size; it needs a Redraw.')
        row.update(state='accepted', accepted={'n': n, 'face_sha256': entry['face_sha256'], 'size_mm': size,
                                               'at': timezone.now().isoformat()})
        build.save()
    return build


def accept_all(record_id, user):
    """Every face awaiting its Accept accepted on its current drawing, in one step (the owner, 2026-10-30). A face still
    being drawn, or whose size changed, is left as it is and named. Returns (build, the accepted, the left)."""
    with transaction.atomic():
        build = _owned_gate(record_id, user)
        sizes = die_sizes(build)
        done, left = [], []
        for key, row in board(build).items():
            entry = current(row)
            if row['state'] == 'accepted':
                continue
            if row['state'] != 'drawn' or entry is None or entry.get('preview') is None or entry.get('size_mm') != sizes[key]:
                left.append(key)
                continue
            row.update(state='accepted', accepted={'n': entry['n'], 'face_sha256': entry['face_sha256'], 'size_mm': sizes[key],
                                                   'at': timezone.now().isoformat()})
            done.append(key)
        build.save()
    return build, done, left


def relink(record_id, *, cap_usd, words, ground_hex=None):
    """The owner's order to rebuild a round's stand on these rules (2026-10-30, round 4): its cap raised in his words, the
    panels it has measured first on the raster that prints (flat/rules-before.json); if they hold, they are kept, and if
    not the wrap is claimed once, under that cap, from their art; the files go back to the faces. Returns the measure."""
    with transaction.atomic():
        build = RoundMaster.objects.select_for_update().select_related('round').get(round_id=record_id)
        if not is_gate(build) or build.state in ('queued', 'running'):
            raise ValueError('A running job or a build off the gate is never rebuilt.')
        claim = flat_claim(build)
        rows = board(build)
        drawn = {key: _panel_record(build, current(row)) for key, row in rows.items() if faces.stand_face(key)}
        found = faces.design_ground(build.round)
        measured = faces.print_rules(drawn, read(root(build) / 'stand.json'), ground_hex or (found['hex'] if found else None))
        flow.write_json(root(build) / 'flat' / 'rules-before.json', measured)
        joined = measured['folds']['holds'] and (measured['ground'] is None or measured['ground']['holds'])
        raises = [name for name in claim if name.startswith('cap_raised')]
        was = float(build.budget_usd)
        claim.update(budget_usd=cap_usd, **{'cap_raised_%d' % (len(raises) + 1): {
            'cap_usd': cap_usd, 'was_usd': was, 'at': timezone.now().isoformat(), 'words': words}})
        if not joined:
            painted = [int(path.name.split('-')[1]) for path in (root(build) / 'flat' / 'wraps').glob('stand-*')]
            claim['wrap'] = {'attempt': max(painted + [0]) + 1, 'why': '',
                             'from': 'the faces as they stood (flat/rules-before.json)'}
            for key, row in rows.items():
                if faces.stand_face(key):
                    row.update(state='queued', accepted=None, note='', suggested='', error='', pending_n=None, flat_cut=False)
        flow.write_json(root(build) / 'flat' / 'claim.json', claim)
        build.budget_usd = cap_usd
        build.round.budget_usd = cap_usd
        build.round.save(update_fields=['budget_usd'])
        build.steps['files'] = dict(build.steps['files'], state='waiting')
        build.steps['faces']['state'] = 'queued'
        build.current_step, build.publication, build.error = 'faces', {}, ''
        build.state = 'awaiting'
        _wake(build)
        build.save()
    return measured


def redraw(record_id, user, key, note=''):
    with transaction.atomic():
        build = _owned_gate(record_id, user)
        row = board(build).get(key)
        if row is None or row['state'] not in ('drawn', 'accepted', 'failed'):
            raise ValueError('That face is already being drawn.')
        text, withheld = faces.owner_note(note)
        row.update(state='queued', note=text, accepted=None, error='', pending_n=None)
        claim = flat_claim(build)
        if claim is not None and faces.stand_face(key) and faces.current_painting(root(build)) is None:
            # the painting was lost: the owner's Redraw claims the next painting of the whole die, its note with it
            claim.update(attempt=int(claim.get('attempt', 1)) + 1, previous_attempts=claim.get('previous_attempts', []) +
                         [{'attempt': claim.get('attempt', 1), 'at': claim.get('at'), 'by': 'lost'}],
                         at=timezone.now().isoformat())
            if text and not withheld:
                claim['style'] = dict(claim['style'], keep=(claim['style']['keep'] + ' The owner asks: "%s".' % text).strip())
            flow.write_json(root(build) / 'flat' / 'claim.json', claim)
            _reset_stand(build)
        if claim is not None and claim.get('pieces') and text and not withheld:
            # the motifs are shared: a note asks for a new sheet, and every face that uses them is placed again
            claim['pieces'] = dict(claim['pieces'], sheet=int(claim['pieces'].get('sheet', 1)) + 1, note=text)
            flow.write_json(root(build) / 'flat' / 'claim.json', claim)
            for other in board(build).values():
                other.update(state='queued', accepted=None, error='', pending_n=None)
        if (claim is not None and claim.get('wrap') and key in wrap_panels() and
                faces.current_wrap(root(build), int(claim['wrap']['attempt'])) is None):
            # the wrap was lost: the owner's Redraw claims the next wrap, its note with it
            claim['wrap'] = dict(claim['wrap'], attempt=int(claim['wrap']['attempt']) + 1,
                                 why=text if text and not withheld else '')
            flow.write_json(root(build) / 'flat' / 'claim.json', claim)
            for other in wrap_panels():
                if board(build)[other]['state'] == 'failed':
                    board(build)[other].update(state='queued', error='', pending_n=None)
        if build.current_step == 'files' or build.state == 'complete':
            build.steps['files'].update(state='waiting')
            build.current_step = 'faces'
            build.publication = {}
            if build.state == 'complete':
                build.state = 'awaiting'
        if build.current_step == 'faces':
            build.steps['faces']['state'] = 'queued'
        _wake(build)
        build.save()
    return build


def ready(build, sizes=None):
    """Every face accepted on its current drawing, at its current size on the die."""
    sizes = sizes or die_sizes(build)
    for key, row in board(build).items():
        entry = current(row)
        accepted = row.get('accepted') or {}
        if (row['state'] != 'accepted' or entry is None or accepted.get('n') != entry['n'] or
                accepted.get('face_sha256') != entry['face_sha256'] or accepted.get('size_mm') != sizes[key]):
            return False
    return True


def make_files(record_id, user):
    with transaction.atomic():
        build = _owned_gate(record_id, user)
        if build.state in ('queued', 'running') or not ready(build):
            raise ValueError('Make my files opens once every face is Accepted.')
        build.steps['files'] = dict(build.steps['files'], state='queued', history=build.steps['files'].get('history', []))
        build.current_step = 'files'
        _wake(build)
        build.save()
    return build


# --- "Make my files" (the worker) -------------------------------------------------------------------------------------

def make(ctx):
    """The accepted faces composed on the engine's die and written: bottle, cap and stand (.ai with the die locked,
    live type, the approved logo; Illustrator's own save and reopen), flat previews, the built drawing and a zip."""
    build = ctx.build
    if not ready(build):
        raise ValueError('Every face must be Accepted, on its current drawing, before the files are made.')
    drawn = {}
    for key, row in board(build).items():
        record = json.loads((ctx.root / current(row)['record']).read_text())
        if sha(record['face']) != row['accepted']['face_sha256']:
            raise ValueError('An accepted face changed after its Accept: ' + key)
        drawn[key] = record
    revisions = ctx.root / 'revisions'
    revision = max([int(path.name) for path in revisions.glob('*') if path.name.isdigit()] + [0]) + 1
    outputs = build_outputs(ctx, drawn, revision)
    claim = flat_claim(build)
    members = []
    for item in outputs['objects']:
        members.extend((Path(item['ai']), Path(item['png'])))
    members.append(ctx.root / outputs['drawing'])
    stand_record = json.loads((ctx.root / 'stand.json').read_text())['record']
    die_files = None
    from apps.dielines.geometry import counter_display
    if stand_record.get('schema') in (counter_display.SCHEMA, counter_display.TEMPLATE_SCHEMA):
        # the die-maker's files: the layered die (true 1:1 mm, spot cut and crease), DXF, CF2, the assembly drawing
        from apps.dielines.exporters import counter_display_files
        die_folder = revisions / str(revision) / 'die'
        stand_spec = next(item for item in outputs['specs'] if item['id'] == 'stand')
        stand_art = stand_spec['artwork']
        die_files = counter_display_files.write_all(stand_record, die_folder, artwork=stand_art[0]
                                                    if claim is not None and stand_art else None)
        members.extend(die_folder / name for name in die_files['files'])
    destination = ctx.root / 'files.zip'
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in members:
            archive.write(path, path.name)
    geometry = json.loads((ctx.root / 'stand.json').read_text())
    spent = scoped_spend(build)
    method = ('Method: each printed face drawn front-on as one edit guided by the picked picture, with no lettering; its '
              'live type and the approved logo placed from the brief\'s COPY; Accepted by the owner, face by face; '
              'composed on the engine\'s die (PIPELINE.md, "Execution: the face method").')
    if claim is not None:
        method = ('Method: the stand designed flat (owner, 2026-10-28): the engine\'s die drawn first, one painting of '
                  'its printed faces and their bleed, the die applied again (flat/paintings/*/proof.json), each stand '
                  'face cut straight from it; the bottle and cap each drawn front-on as one edit guided by the picked '
                  'picture, with no lettering; live type and the approved logo from the brief\'s COPY; Accepted by the '
                  'owner, face by face; the stand\'s one flat raster placed on the die at 1:1 (die.pdf, ARTWORK).')
        if claim.get('wrap'):
            method += (' The faces that meet at a fold were painted as one wrap and cut along the die (flat/wraps/); the '
                       'painting prints whole, with no fitted vector over it (each file\'s .print-check.json).')
    lines = ['# Built files', '',
             f"Picked picture: {build.inputs['pick']['id']} · unchanged SHA-256 {build.inputs['picture_sha256']}.",
             method,
             f"Stand: {geometry['rows']} rows × {geometry['columns']} columns = {geometry['count']} products; "
             'measurements are provisional (stand/stand-geometry.json).', '', 'Faces, as accepted:']
    for key, row in board(build).items():
        entry = current(row)
        eye = entry.get('eye') or {}
        advice = ('; '.join(eye.get('findings') or []) or 'no notes') if eye.get('state') in ('done', 'carried') else \
            'none (' + eye.get('state', 'pending') + ')'
        lines.append(f"- {row['label']}: drawing {entry['n']} ({entry['source']}), accepted "
                     f"{row['accepted']['at'][:16].replace('T', ' ')}. Eye (advice): {eye.get('verdict', '—')} — {advice}")
    if die_files:
        best = die_files['nest']['best']
        template = stand_record.get('template') or {'id': counter_display.TEMPLATE_ID, 'version': counter_display.VERSION}
        lines += ['', 'Die (%s %s): die.pdf (CUT, CREASE, PERF, HALF-CUT, GLUE, SAFE, BLEED, ARTWORK, DIMENSIONS; '
                  'CutContour and Crease spots, 1:1 mm), %s, die.cf2 (not yet opened in a die shop\'s CAD). Nest: %d per %d × %d sheet, yield %.0f %%.' % (
                      template['id'], template['version'], ', '.join(name for name in die_files['files'] if name != 'die.pdf' and not name.endswith('.png') and name != 'die.cf2'),
                      best['sets'], best['sheet_mm'][0], best['sheet_mm'][1], best['yield'] * 100)]
    lines += ['', f"Spend: ${spent['actual_usd']:.4f} billed, ${spent['unknown_usd']:.4f} lost with its outcome unknown "
                  f"(counted), ${spent['held_usd']:.4f} held; one cap ${spent['budget_usd']:g} for the round's files.",
              f"Download: /dashboard/rounds/{ctx.round.pk}/built-files/download/files.zip"]
    (ctx.root / 'README.md').write_text('\n'.join(lines) + '\n')
    names = {'files.zip', 'README.md', 'source.png', outputs['drawing'], *outputs['views'].values()}
    result = {'schema': SCHEMA, 'revision': revision, 'download': 'files.zip', 'report': 'README.md',
              'drawing': outputs['drawing'], 'views': outputs['views'], 'spend': spent,
              'files': {name: sha(ctx.root / name) for name in sorted(names)},
              'accepted': {key: row['accepted'] for key, row in board(build).items()}}
    flow.write_json(ctx.root / 'publication.json', result)
    return result


def pins(build):
    """Every file the files page may serve: the picture, each face's current crop and preview, and the made files."""
    folder = root(build)
    out = {}
    source = folder / 'source.png'
    if source.exists():
        out['source.png'] = build.inputs['picture_sha256']
    for row in board(build).values():
        entry = current(row)
        if entry:
            out[entry['reference']] = entry['reference_sha256']
            if entry.get('preview'):
                out[entry['preview']] = entry['preview_sha256']
    out.update(flat_pins(build))
    made = build.publication if build.state == 'complete' else {}
    out.update(made.get('files', {}))
    return out


def flat_pins(build):
    """A flat build's own pictures the files page may serve: the template sheet, the current painting's die view, its
    folded and loaded drawings."""
    folder, out = root(build), {}
    claim = flat_claim(build)
    if (folder / 'stand' / 'sheets' / 'report.json').exists():    # a template die's own sheets
        out.update({'stand/sheets/' + name: value for name, value in read(folder / 'stand' / 'sheets' / 'report.json').get('pins', {}).items()})
    if claim is None:
        return out
    if (folder / 'flat' / 'template.json').exists():           # gone with an old die until the new one's is drawn
        out['flat/sheet.png'] = read(folder / 'flat' / 'template.json')['sheet_sha256']
    painting = faces.current_painting(folder)
    if painting is not None:
        out[_rel(build, painting['view'])] = painting['view_sha256']
        drawings = Path(painting['view']).parent / 'drawings.json'
        if drawings.exists():
            saved = json.loads(drawings.read_text())
            for name in ('folded', 'loaded'):
                if saved.get(name):
                    out[saved[name]] = saved[name + '_sha256']
    # the views drawn from the current panels and the proof sheet (the owner's goal of 2026-10-29), by their own records
    panels, sheet = folder / 'flat' / 'panels' / 'current.json', folder / 'proof' / 'current.json'
    if panels.exists():
        saved = read(panels)
        for name in ('folded', 'loaded', 'three_quarter'):
            if saved.get(name):
                out[saved[name]] = saved[name + '_sha256']
    if sheet.exists():
        saved = read(sheet)
        out[saved['pdf']], out[saved['png']] = saved['pdf_sha256'], saved['png_sha256']
    saved = _page_pieces(build)
    if saved:
        shots = [shot for item in (saved.get('illustrator') or {}).get('files', []) for shot in item['shots']]
        for row in saved['layers'] + saved['library'] + saved['seams']['creases'] + shots:
            out[row.get('png') or row['picture']] = row['sha256']
    return out


def _page_pieces(build):
    """The "what you'll get" record, only when it is of the faces as they stand now: never an older placement's."""
    what, proof = root(build) / 'pieces' / 'current.json', root(build) / 'proof' / 'current.json'
    if not what.exists() or not proof.exists():
        return None
    made = read(what)
    return made if made.get('signature') == read(proof).get('signature') else None


def _page_rules(build):
    """The painted rules' record as the page shows it, only when measured on the faces as they stand now."""
    path = root(build) / 'flat' / 'rules.json'
    if not path.exists():
        return None
    made, rows = read(path), board(build)
    if any(key not in rows or current(rows[key]) is None or current(rows[key])['face_sha256'] != value
           for key, value in made['faces'].items()):
        return None
    return dict(made, ground_rows=[dict(row, name=faces.FACES[key]['label']) for key, row in
                                   (made['ground'] or {'panels': {}})['panels'].items()])


def flat_page(build):
    """What the files page shows of a flat build: the die with its artwork, the template sheet, the drawings, the
    die-match proof and the colour across each fold."""
    claim = flat_claim(build)
    painting = faces.current_painting(root(build)) if claim else None
    sheet_shown = None
    if (root(build) / 'flat' / 'template.json').exists():
        sheet_shown = 'flat/sheet.png'
    if painting is None:
        if not claim:
            return None
        lost = any(row.get('error') == PAINTING_LOST for row in board(build).values())
        return {'claim': claim, 'sheet': sheet_shown, 'lost': PAINTING_LOST if lost else '',
                'attempt': claim.get('attempt', 1)}
    folder = Path(painting['view']).parent
    drawings = json.loads((folder / 'drawings.json').read_text()) if (folder / 'drawings.json').exists() else {}
    panels_path, proof_path = root(build) / 'flat' / 'panels' / 'current.json', root(build) / 'proof' / 'current.json'
    panels = read(panels_path) if panels_path.exists() else None
    sheet = read(proof_path) if proof_path.exists() else None
    return {'claim': claim, 'view': _rel(build, painting['view']), 'sheet': sheet_shown,
            'folded': drawings.get('folded'), 'loaded': drawings.get('loaded'), 'proof': painting['proof'],
            'continuity': painting['continuity']['seams'], 'n': painting['n'], 'panels': claim.get('panels') == 'full',
            'panel_folded': panels['folded'] if panels else None, 'panel_loaded': panels['loaded'] if panels else None,
            'three_quarter': panels.get('three_quarter') if panels else None, 'proof_sheet': sheet,
            'pieces': _page_pieces(build),
            'rules': _page_rules(build), 'wrap': bool(claim.get('wrap'))}


# --- the stand designed flat (owner, 2026-10-28): round 3 --------------------------------------------------------------

#: the painting's words when the owner's policy gives none: the picked picture is the style reference
FLAT_STYLE = {'style_reference': 'source.png',
              'style_words': 'the owner\'s picked design, a picture of the product and its loaded counter stand. Paint '
                             'each face of the stand as the picture shows it: its board colours, its header artwork on '
                             'the header front, its front strip on the front panel, its walls and back as it shows them.',
              'keep': ''}


def _flat_claim(build, policy, geometry):
    """The claim a flat stand's painting follows, written once: the engine's flat die drawn first ($0), the style
    reference (the build's own picked picture, by its SHA-256), the words, and the cap (the policy's, else the
    round's one cap)."""
    from apps.dielines.geometry import counter_display
    folder = root(build)
    if geometry['record'].get('schema') not in (counter_display.SCHEMA, counter_display.TEMPLATE_SCHEMA):
        raise ValueError('The flat stand needs the production die (counter_tray_header 1.0) first.')
    style = folder / policy['style_reference']
    if not style.resolve().is_relative_to(folder.resolve()) or sha(style) != build.inputs['picture_sha256']:
        raise ValueError('The flat stand\'s style reference is not the picked picture.')
    setup = faces.flat_setup(geometry, folder / 'flat')
    claim = {'schema': 'owner_flat_stand_claim/1', 'at': timezone.now().isoformat(), 'policy': policy,
             'style': {'path': str(style.resolve()), 'sha256': build.inputs['picture_sha256'],
                       'role': 'style reference', 'words': policy['style_words'], 'keep': policy['keep']},
             'budget_usd': float(policy.get('budget_usd') or build.budget_usd), 'attempt': int(policy.get('attempt', 1)),
             'panels': policy.get('panels', 'cut'), 'product_nets': bool(policy.get('product_nets')), 'operations': [],
             'template_sha256': setup['template_sha256'],
             'die': '%s/%s' % (counter_display.TEMPLATE_ID, counter_display.VERSION)}
    flow.write_json(folder / 'flat' / 'claim.json', claim)
    return claim


def install_pick(build, claim):
    """A flat pick's painting installed as the build's flat painting, $0: its bytes as picked (the pick page's SHA-256),
    on the same template; the stand faces are then drawn per panel from it."""
    folder, picked = root(build), flow.round_root(build.round)
    painting_path = picked / build.inputs['flat_pick']['painting']
    painting = read(painting_path)
    if painting['flat_sha256'] != build.inputs['picture_sha256'] or sha(folder / 'source.png') != painting['flat_sha256']:
        raise ValueError('The picked flat design is not the painting the pick page published.')
    template = read(picked / Path(build.inputs['flat_pick']['die']).parent / 'flat' / 'template.json')
    if template['template_sha256'] != claim['template_sha256']:
        raise ValueError('The picked flat design was painted on another template than this build\'s die.')
    target = faces.flat_root(folder) / 'paintings' / '1'
    target.mkdir(parents=True, exist_ok=True)
    record = dict(painting, n=1, cost_usd=0.0, installed_from=build.inputs['flat_pick']['painting'],
                  rule='the picked flat design installed as the build\'s painting at $0, its bytes as picked')
    for name in ('flat', 'art', 'view'):
        source = painting_path.parent / (name + '.png')
        if sha(source) != painting[name + '_sha256']:
            raise ValueError('The picked flat design changed after it was picked: ' + name)
        shutil.copyfile(source, target / (name + '.png'))
        record[name] = str(target / (name + '.png'))
    flow.write_json(target / 'record.json', record)
    faces._set_current(folder, target / 'record.json')
    return record


FLAT_PICK_WRAP = False


def open_flat(build):
    """When the faces open, the stand is designed flat (owner, 2026-10-28): the claim written and every stand face of
    the new board marked to be cut from the painting. A flat pick's painting is the one picked, installed at $0, and
    each stand face and product is drawn from it per panel and on its net (the owner's goal of 2026-10-29)."""
    if build.inputs.get('flat_pick'):
        policy = dict(FLAT_STYLE, panels='full', product_nets=True,
                      style_words='the owner\'s picked flat design of the stand, as he picked it.')
        claim = _flat_claim(build, policy, json.loads((root(build) / 'stand.json').read_text()))
        if FLAT_PICK_WRAP:                              # part 1's path, held for a build already on it
            claim['wrap'] = {'attempt': 1}
        else:
            claim['pieces'] = {'sheet': 1, 'at': timezone.now().isoformat()}   # separate pieces (the owner, 2026-10-30, part 1B)
        flow.write_json(root(build) / 'flat' / 'claim.json', claim)
        install_pick(build, claim)
    else:
        policy = json.loads(POLICY.read_text()).get('flat_stands', {}).get(build.round.slug) or FLAT_STYLE
        _flat_claim(build, policy, json.loads((root(build) / 'stand.json').read_text()))
    for key, row in board(build).items():
        if faces.stand_face(key):
            row['flat_cut'] = True


def flatten(build):
    """In the worker, under the build's lock, $0: a gate build the owner's policy names under ``flat_stands`` has its
    stand designed flat. Every printed face of the die becomes a face of the board, reset to be cut from one painting
    of the engine's flat die, its earlier drawings kept as history; the bottle and cap keep theirs. The paid painting
    is the faces job's, under the policy's own cap. Returns the faces reset, or None."""
    policy = json.loads(POLICY.read_text()).get('flat_stands', {}).get(build.round.slug)
    folder = root(build)
    if policy is None or not is_gate(build):
        return None
    before = flat_claim(build)
    if before is not None and int(before.get('attempt', 1)) >= int(policy.get('attempt', 1)):
        return None
    if sha(folder / policy['style_reference']) != policy['picture_sha256']:
        raise ValueError('The flat stand\'s style reference is not the one the owner named.')
    claim = _flat_claim(build, policy, json.loads((folder / 'stand.json').read_text()))
    if before is not None:
        claim['previous_attempts'] = before.get('previous_attempts', []) + [
            {key: before.get(key) for key in ('attempt', 'at', 'budget_usd')}]
    _reset_stand(build)
    reset = [key for key in faces.FACES if faces.stand_face(key)]
    if policy.get('product_nets'):
        # die-first for the products too (the owner's goal of 2026-10-29): the bottle and cap drawn again, each on its
        # own flat net; their earlier drawings stay on their records as history
        rows = board(build)
        for key in faces.FACES:
            if not faces.stand_face(key) and key in rows:
                rows[key].update(state='queued', accepted=None, note='', suggested='', error='', pending_n=None)
                reset.append(key)
    build.steps['faces']['state'] = 'queued'
    build.steps['files'] = dict(build.steps['files'], state='waiting')
    build.current_step, build.publication, build.error, build.state = 'faces', {}, '', 'queued'
    flow.write_json(folder / 'flat' / 'claim.json', dict(
        claim, faces_reset=reset, faces_kept=[key for key in faces.FACES if key not in reset],
        history='each stand face\'s earlier drawings stay on its record as history'))
    return reset


# --- a face-path build moved onto the gate (round 3) ------------------------------------------------------------------

#: the faces the retired face path drew (attempts 1–3 on round 3): what migrate moves onto the gate
FACE_PATH_KEYS = ('header', 'front', 'side', 'back', 'bottle', 'cap')


def _latest_claim(folder):
    claims = sorted(folder.glob('faces-attempt-*.json'), key=lambda path: int(path.stem.rsplit('-', 1)[1]))
    return json.loads(claims[-1].read_text()) if claims else None


def _moved(record, folder, prefix):
    """A drawing record whose files moved under ``prefix`` (superseded/face-N): its paths re-pointed and checked."""
    out = json.loads(json.dumps(record))
    for path_key in ('face',):
        relative = Path(out[path_key]).resolve().relative_to(folder.resolve())
        out[path_key] = str(folder / prefix / relative) if prefix and not (folder / relative).exists() else \
            str(folder / relative)
    for nested in ('template', 'reference'):
        if isinstance(out.get(nested), dict):
            name = 'template' if nested == 'template' else 'path'
            relative = Path(out[nested][name]).resolve().relative_to(folder.resolve())
            if not (folder / relative).exists() and prefix:
                out[nested][name] = str(folder / prefix / relative)
    if sha(out['face']) != out['face_sha256']:
        raise ValueError('A drawn face changed before it reached the gate: ' + out['key'])
    return out


def _last_look(review, key):
    looks = sorted(review.glob(key + '-*.json'), key=lambda path: int(path.stem.rsplit('-', 1)[1])
                   if path.stem.rsplit('-', 1)[1].isdigit() else -1)
    for path in reversed(looks):
        if not path.stem.rsplit('-', 1)[1].isdigit():
            continue
        saved = json.loads(path.read_text())
        if saved.get('status') == 'complete' and isinstance(saved.get('payload'), dict):
            return faces.validate_look(saved['payload'])
    return None


def migrate(build):
    """In the worker, under the build's lock: a build of the face path (drawn, then looked at and repaired by the eye)
    moved onto the gate, $0, no call. Each face's latest drawing becomes its drawing 1, with the eye's last look on it
    as advice; a face whose last look needed attention is marked "Redraw suggested". A face edit whose outcome is
    unknown is checked once and closed (spend.close_unknown), its folder kept aside. Steps: read and stand kept;
    faces holds the board; files waits for "Make my files"."""
    from . import spend_reservation as spend
    folder = root(build)
    claim = _latest_claim(folder)
    attempt = claim['attempt'] if claim else 1
    previous = 'superseded/face-%d' % (attempt - 1) if claim else ''
    drawn = {}
    looks = {}
    # the attempt that drew each face's latest drawing: a kept face's, from the claims before the latest; a face the
    # latest attempt was redrawing still holds the drawing from the attempt before it (its own edit never finished)
    attempts_of = {}
    for path in sorted(folder.glob('faces-attempt-*.json'), key=lambda path: int(path.stem.rsplit('-', 1)[1])):
        record = json.loads(path.read_text())
        if record['attempt'] == attempt:
            break
        for key in record['redraw']:
            attempts_of[key] = record['attempt']
    if claim:
        attempts_of.update({key: attempt - 1 for key in claim['redraw']})
    lost = []
    for key in FACE_PATH_KEYS:
        if claim and key in claim['kept']:
            drawn[key] = _moved(claim['kept'][key], folder, '')
            kept = claim['kept_looks'].get(key) or []
            looks[key] = kept[-1] if kept else None
        else:
            base = folder / previous / 'faces' / key if previous else folder / 'faces' / key
            record_path = base / 'repair' / 'record.json'
            record_path = record_path if record_path.exists() else base / 'record.json'
            drawn[key] = _moved(json.loads(record_path.read_text()), folder, previous)
            looks[key] = _last_look(folder / previous / 'review' if previous else folder / 'review', key)
        call = folder / 'faces' / key / 'call'
        request = call / 'image-call.request.json'
        if request.exists() and not (call / 'image-call.json').exists():
            held = json.loads(request.read_text())
            check = provider_check('openai', held['reservation_id'])
            spend.close_unknown(held['reservation_id'], dict(check, error='started, nothing saved (moved to the gate)'))
            aside = folder / 'faces' / key / ('lost-' + held['reservation_id'])
            call.rename(aside)
            flow.write_json(aside / 'image-call.lost.json', {'reservation_id': held['reservation_id'], 'check': check,
                            'rule': 'checked once against the provider, then closed; never sent twice'})
            lost.append({'face': key, 'reservation_id': held['reservation_id'], 'check': check,
                         'kept_at': _rel(build, aside)})
    rows = {}
    for key in FACE_PATH_KEYS:
        record = dict(drawn[key], n=1, source='attempt %d' % attempts_of.get(key, 1))
        target = faces.drawing_folder(folder, key, 1)
        target.mkdir(parents=True, exist_ok=True)
        flow.write_json(target / 'record.json', record)
        look = looks[key]
        eye = dict(look, state='carried', source="the eye's last look in attempt %d, on that build of this face"
                   % attempts_of.get(key, 1)) if look else {'state': 'none'}
        row = empty_face(key)
        row.update(state='drawn', drawing=1, drawings=[{
            'n': 1, 'record': _rel(build, target / 'record.json'), 'face': _rel(build, record['face']),
            'face_sha256': record['face_sha256'], 'reference': _rel(build, record['reference']['path']),
            'reference_sha256': sha(record['reference']['path']), 'preview': None, 'preview_sha256': None,
            'size_mm': None, 'facts': None, 'eye': eye, 'source': record['source'], 'note': '', 'cost_usd': None,
            'at': timezone.now().isoformat()}])
        if look and look['verdict'] != 'pass':
            row['suggested'] = 'Redraw suggested: the eye\'s last look needed attention.'
        rows[key] = row
    flow.write_json(folder / 'gate-claim.json', {
        'schema': 'owner_face_gate_claim/1', 'at': timezone.now().isoformat(), 'from_attempt': attempt,
        'previous_steps': {name: {k: v for k, v in step.items() if k != 'result'} for name, step in build.steps.items()},
        'previous_current_step': build.current_step, 'lost_calls': lost,
        'faces': {key: {'drawing': rows[key]['drawings'][0]['face'], 'suggested': rows[key]['suggested'],
                        'eye': rows[key]['drawings'][0]['eye']} for key in FACE_PATH_KEYS}})
    steps = {name: build.steps[name] for name in ('read', 'stand')}
    steps['faces'] = {'state': 'queued', 'attempts': 0, 'dispatches': 0, 'history': [], 'result': {}, 'board': rows,
                      'claim': 'gate-claim.json'}
    steps['files'] = {'state': 'waiting', 'attempts': 0, 'dispatches': 0, 'history': [], 'result': {}}
    build.steps, build.current_step, build.error, build.publication = steps, 'faces', '', {}
    build.state = 'queued'
    return lost


# --- a build moved onto a new die (counter_tray_header 1.0, owner 2026-10-28) -----------------------------------------

def write_die_sheets(record, folder, *, native=None):
    """A template die's sheets and files, and what the page may serve of them. ``native``: as counter_display_files.write_template."""
    from apps.dielines.exporters import counter_display_files
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    made = counter_display_files.write_template(faces.die_of({'record': record}), record, folder, native=native)
    made['pins'] = {name: sha(folder / name) for name in made['files']}
    flow.write_json(folder / 'report.json', made)
    return made


def build_stand(brief, inspection, outdir, *, include_enclosure=False, rear_visibility='inside', picture=None, native_sheets=None):
    """The stand solved from the brief (and the picture's reading, if any) by the die solver
    (counter_display.solve_stand), its record and its fold and sightline reports written into outdir."""
    from apps.dielines.geometry.counter_display import solve_stand
    result = solve_stand(brief, inspection, include_enclosure=include_enclosure, rear_visibility=rear_visibility,
                         picture=picture)
    root = Path(outdir)
    root.mkdir(parents=True, exist_ok=True)
    flow.write_json(root / 'stand-geometry.json', result)
    flow.write_json(root / 'stand-die.json', result['record'])
    flow.write_json(root / 'stand-fold-check.json', result['fold_check'])
    flow.write_json(root / 'stand-sightlines.json', result['sightlines'])
    flow.write_json(root / 'shape-check.json', result['shape_check'])        # picture vs die, matched or fixed
    from apps.dielines.geometry import counter_display
    if result['record'].get('schema') == counter_display.TEMPLATE_SCHEMA:
        # the die's own sheets (its files, its fold-up, its assembly, its nest) from the day it is solved: the page shows them
        write_die_sheets(result['record'], root / 'sheets', native=native_sheets)
    return result


SHADE_PICK_MINUTES = 20                         # how long a further shade waits for the owner (his part 3, §2)
SHADE_DEFAULT_WORDS = 'owner to confirm'


def _shade_paths(record):
    folder = flow.round_root(record)
    return folder / 'shade-proposals.json', folder / 'shade-pick.json', folder / 'PICK'


def propose_shade(record, *, columns):
    """A further shade where a stand has more columns than the brief has shades: three candidates by rule ($0, no model), kept in the round's
    folder apart from its brief, whose digest binds the round. Starts the owner's wait once: asked again it returns what stands."""
    proposals, _pick, pick_file = _shade_paths(record)
    if proposals.exists():
        return read(proposals)
    colours = faces.design_colours(record)
    family = list(execution_brief(record.product_brief).get('shades') or [])
    now = timezone.now()
    out = {'schema': 'shade_proposals/1', 'at': now.isoformat(), 'deadline': (now + timedelta(minutes=SHADE_PICK_MINUTES)).isoformat(), 'columns': columns,
           'family': family, 'ground': colours['ground'], 'candidates': faces.shade_candidates(family, colours['ground']),
           'how': 'by rule, from the family and the design\'s ground, at $0; the owner picks by his message or a PICK file (%s) in the round\'s folder '
                  'holding 1, 2 or 3, or a name, or a name and a #hex' % pick_file.name}
    if len(out['candidates']) < 1:
        raise ValueError('No colour on record fits this family: the owner names the shade.')
    flow.write_json(proposals, out)
    return out


def _read_pick(words, candidates):
    """The owner's PICK file: 1, 2 or 3; a candidate's name or hex; or his own name and #hex. None if it says none of those."""
    words = ' '.join(str(words).split())
    if words.isdigit() and 1 <= int(words) <= len(candidates):
        return dict(candidates[int(words) - 1])
    for row in candidates:
        if words.lower() in (row['name'].lower(), row['hex'].lower()):
            return dict(row)
    found = re.fullmatch(r'(.+?)\s+(#[0-9a-fA-F]{6})', words)
    return {'name': found.group(1), 'hex': found.group(2).upper()} if found else None


def resolve_shade(record, *, now=None, choice=None, source=''):
    """The further shade as it stands: the owner's word (``choice``, or the PICK file), else after his 20 minutes the engine's first, marked
    "owner to confirm", which his later word still replaces; None while he has time. Written once per decision."""
    proposals_path, pick_path, pick_file = _shade_paths(record)
    if not proposals_path.exists():
        return None
    proposals = read(proposals_path)
    held = read(pick_path) if pick_path.exists() else None
    if held and held['status'] == 'owner':
        return held
    words = choice if choice is not None else (pick_file.read_text(encoding='utf8') if pick_file.exists() else None)
    if words is not None:
        shade = _read_pick(words, proposals['candidates'])
        if shade is None:
            raise ValueError('The PICK says "%s": it names no shade (1, 2 or 3, a name, or a name and a #hex).' % ' '.join(str(words).split())[:80])
        out = {'schema': 'shade_pick/1', 'status': 'owner', 'at': timezone.now().isoformat(), 'source': source or 'the PICK file', 'shade': {'name': shade['name'], 'hex': shade['hex']}}
    elif held:
        return held
    elif (now or timezone.now()) >= datetime.fromisoformat(proposals['deadline']):
        first = proposals['candidates'][0]
        out = {'schema': 'shade_pick/1', 'status': SHADE_DEFAULT_WORDS, 'at': timezone.now().isoformat(), 'source': 'the engine\'s first, the owner\'s 20 minutes having passed',
               'shade': {'name': first['name'], 'hex': first['hex']}}
    else:
        return None
    flow.write_json(pick_path, out)
    return out


def shades_of(record, brief=None):
    """The round's shades: its brief's, and a further one if it has been decided."""
    shades = list((brief or execution_brief(record.product_brief)).get('shades') or [])
    _proposals, pick_path, _file = _shade_paths(record)
    if pick_path.exists():
        pick = read(pick_path)
        if not any(shade['hex'].upper() == pick['shade']['hex'].upper() for shade in shades):
            shades.append(dict(pick['shade'], fourth_status=pick['status']))
    return shades


def shade_page(record):
    """What the round's page shows of a further shade: the proposals, and the pick as it stands."""
    proposals_path, pick_path, _file = _shade_paths(record)
    if not proposals_path.exists():
        return None
    proposals = read(proposals_path)
    return dict(proposals, pick=read(pick_path) if pick_path.exists() else None, folder=str(flow.round_root(record).relative_to(flow.REPO)))


def die_page(build):
    """What the files page shows of a template die: its sheets, its checks, its downloads, with paths relative to the build."""
    folder = root(build) / 'stand' / 'sheets'
    if not (folder / 'report.json').exists():
        return None
    from apps.dielines.geometry import stand_types
    report = read(folder / 'report.json')
    geometry = read(root(build) / 'stand.json')
    record = geometry['record']
    q = report['qualification']
    eyes = q['sightlines']['eyes']
    return {'label': stand_types.label(record['template']['id']), 'version': record['template']['version'], 'closed_mm': q['fold']['dimensions']['closed_mm'],
            'changes': record.get('changes', []), 'layout': record['layout'], 'board': record['board']['name'], 'grain': record['production']['grain'],
            'glue': record['production'].get('glue', ''), 'joints': len(q['fold']['joints']['joints']), 'locks': q['fold']['locks']['count'], 'fits': q['fold']['fit']['count'],
            'clearance_mm': q['fold']['fit']['clearance_mm'], 'collisions': len(q['fold']['collisions']), 'passed': q['passed'], 'along_grain': q['grain']['along_grain'],
            'eyes': [{'in_front': eye['eye_mm']['in_front'], 'above': eye['eye_mm']['above_counter'], 'least': min(row['top_band_mm'] for row in eye['products']),
                      'header': round(100 * eye.get('header', {'seen_share': 1})['seen_share'])} for eye in eyes], 'bar_mm': q['sightlines']['face_bar_mm'],
            'shades': q.get('shades'), 'view': q.get('view'), 'testers': len((record['geometry'].get('tester_holes') or [])),
            'nest': report['nest']['best'], 'tiles': report['cut_and_fold']['tiles'], 'better': q['better_than_house']['rows'], 'strength': q['strength'], 'opens': report['open_check'],
            'notes': record.get('provisional_notes', []), 'compensation': record['production']['compensation'],
            'files': [{'name': name, 'path': 'stand/sheets/' + name} for name in report['files'] if not name.endswith('.png')],
            'die_png': 'stand/sheets/die.png', 'fold_png': 'stand/sheets/fold-up.png', 'assembly_png': 'stand/sheets/assembly.png', 'nest_png': 'stand/sheets/nest.png'}


#: a face whose outline on the die moved more than this (its shape, its position aside) is drawn again
OUTLINE_CHANGED_MM2 = 1.0

RESTAND_FLAT = ('The stand\'s die was solved again, so its flat design must be painted again on the new die: the '
                'owner\'s next flat attempt paints it.')


def restand(build):
    """In the worker, under the build's lock, $0: a build whose stand was solved on an older die is solved again on the
    current one (the same brief and reading). The old stand folder moves to superseded/stand-<schema>; each stand
    face's preview is made again on the new die. A face whose size on the die changed keeps its drawing and is marked
    "needs Redraw (size changed)" (its drawing was made for the old size); the others need no redraw."""
    from apps.dielines.geometry import counter_display
    folder = root(build)
    if not (folder / 'stand.json').exists():
        return None
    stand = json.loads((folder / 'stand.json').read_text())
    old = stand['record'].get('schema')
    revision = stand.get('sightline_revision')
    if old == counter_display.TEMPLATE_SCHEMA:                   # on the family's templates: solved again only by the owner's order
        return None
    # also a stand solved before the solver moved its rows inside the ruled size (the owner's goal of 2026-10-29)
    if old == counter_display.SCHEMA and revision == counter_display.SIGHTLINE_REVISION:
        return None
    inspection = json.loads((folder / 'inspection.json').read_text())
    name = old.replace('/', '-') if old != counter_display.SCHEMA else 'sightline-' + str(revision).replace('/', '-')
    target = folder / 'superseded' / ('stand-' + name)
    n = 1
    while target.exists():
        n += 1
        target = folder / 'superseded' / ('stand-%s-%d' % (name, n))
    target.mkdir(parents=True)
    if (folder / 'stand').exists():
        (folder / 'stand').rename(target / 'stand')
    (folder / 'stand.json').rename(target / 'stand.json')
    # a stand designed flat was painted on the old die's template. Drawn per panel (each face on its own outline from
    # its own reference), only the template goes with the old stand and only the faces whose outline changed are drawn
    # again (the shape check, 2026-10-29); cut from the painting, the flat folder goes with it and the stand faces wait
    # for a painting on the new die (the owner's next flat attempt)
    flat = (folder / 'flat').exists()
    claim = flat_claim(build) if flat else None
    per_panel = claim is not None and claim.get('panels') == 'full'
    old_die = faces.die_of(stand) if per_panel else None
    if per_panel:
        (target / 'flat-template').mkdir()
        for name in ('template.json', 'template.png', 'sheet.png', 'owner.npy'):
            if (folder / 'flat' / name).exists():
                (folder / 'flat' / name).rename(target / 'flat-template' / name)
    elif flat:
        (folder / 'flat').rename(target / 'flat')
    result = build_stand(files_brief(build), inspection, folder / 'stand', picture=folder / 'source.png')
    flow.write_json(folder / 'stand.json', result)
    build.steps['stand']['result'] = json.loads((folder / 'stand.json').read_text())
    if per_panel:
        faces.flat_setup(result, folder / 'flat')           # the template sheet on the new die, at $0 (the files page's)
    sizes = die_sizes(build, faces.die_of(result))
    changed, outlines = [], []
    new_die = faces.die_of(result)
    for key, row in board(build).items():
        if not faces.stand_face(key):
            continue
        if per_panel:
            _part, before = faces.die_face(old_die, faces.FACES[key]['die'])
            _part, after = faces.die_face(new_die, faces.FACES[key]['die'])
            moved = translate(after, before.bounds[0] - after.bounds[0], before.bounds[1] - after.bounds[1])
            if before.symmetric_difference(moved).area > OUTLINE_CHANGED_MM2:
                outlines.append(key)
                row.update(state='queued', accepted=None, pending_n=None, error='',
                           outline_redraw={'of': row.get('drawing'), 'at': timezone.now().isoformat(),
                                           'reason': 'the die was cut to the picked picture\'s outline (the shape check)',
                                           'area_changed_mm2': round(before.symmetric_difference(moved).area, 1)})
        elif flat:
            row.update(state='failed', accepted=None, pending_n=None, error=RESTAND_FLAT)
        entry = current(row)
        if entry is None:
            continue
        entry.update(preview=None, preview_sha256=None, preview_error=None)
        record = json.loads((folder / entry['record']).read_text())
        if drawn_size(key, record) != sizes[key]:
            changed.append({'face': key, 'drawn_for_mm': drawn_size(key, record), 'die_mm': sizes[key]})
            if row['state'] == 'accepted':
                row.update(state='drawn', accepted=None)
    if outlines:
        # the owner's cap for what the new outlines need (the policy's outline_redraw_usd), on top of what the claim
        # had spent: each redraw reserved before it is sent (claimed_call)
        stands = json.loads(POLICY.read_text())['flat_stands']
        added, source = 0.0, 'none: the owner\'s policy names no cap for the new outlines, so their redraws are refused'
        if build.round.slug in stands and 'outline_redraw_usd' in stands[build.round.slug]:
            added = float(stands[build.round.slug]['outline_redraw_usd'])
            source = 'the owner\'s policy for this round (it names no source)'
            if 'outline_redraw_source' in stands[build.round.slug]:
                source = stands[build.round.slug]['outline_redraw_source']
        saved = flat_claim(build)
        spent = claim_spend(build, saved)
        saved.update(budget_usd=round(spent + added, 6), outline_redraw={
            'faces': outlines, 'added_usd': added, 'spent_before_usd': round(spent, 6), 'at': timezone.now().isoformat(),
            'source': source})
        flow.write_json(folder / 'flat' / 'claim.json', saved)
    build.steps['faces']['state'] = 'queued'
    if build.current_step == 'faces' and build.state == 'awaiting':
        build.state = 'queued'                                   # saved with the build; the faces job draws again
    flow.write_json(folder / 'restand-claim.json', {
        'schema': 'owner_face_gate_restand/1', 'at': timezone.now().isoformat(), 'from': old,
        'to': counter_display.SCHEMA, 'template': '%s/%s' % (counter_display.TEMPLATE_ID, counter_display.VERSION),
        'sightline_revision': {'from': revision, 'to': counter_display.SIGHTLINE_REVISION},
        'moved_to': _rel(build, target), 'size_changed': changed, 'flat_moved': flat and not per_panel,
        'outline_changed': outlines, 'shape_check': result.get('shape_check'),
        'fold_passed': result['fold_check']['passed'], 'sightlines_passed': result['sightlines']['passed'],
        'header_clear': result['sightlines']['header_clear']})
    return changed


# --- the files build: start, queue, run, fail (from round_files_flow, 2026-10-28) -------------------------------------
# Execution-half outbox: the owner starts; each face is drawn as its own job and the owner is the gate — Accept or
# Redraw per face, then "Make my files" (owner, 2026-10-28; round_files_gate). Only queued jobs build files.

FILES_SCHEMA = 'picked_picture_files/1'
STEPS = ('read', 'stand', 'faces', 'files')
#: the face path's steps before the owner became the gate (2026-10-27/28): its builds move onto the gate
FACE_PATH_STEPS = ('read', 'stand', 'faces', 'files', 'eye', 'publish')
#: the retired picture-tracing path's steps (docs/rounds/reuse-plan.md): its builds are kept and shown, never run
V1_STEPS = ('read', 'crops', 'stand', 'files', 'eye', 'publish')
STEP_LABELS = {'read': 'Reading your picture', 'crops': 'Preparing the artwork', 'stand': 'Building the stand',
          'faces': 'Your faces: accept or redraw each', 'files': 'Making your files', 'eye': 'Designer’s review',
          'publish': 'Preparing your download'}
RETIRED = ('This build ran on the retired picture-tracing path (docs/rounds/reuse-plan.md); '
           'its saved files stay as they were.')
POLICY = flow.REPO / 'docs/rounds/files-build-policy.json'


COPY_RECORD = 'files-copy.json'




def files_brief(build):
    """The frozen brief, plus the round's committed Arabic shade names where the brief has none.

    The record binds to the brief by digest. Names it supplies are marked by
    their source; executor-written names stay unconfirmed until the owner says.
    """
    import hashlib
    import json
    import re
    from copy import deepcopy
    brief = deepcopy(build.inputs['brief'])
    brief['shades'] = shades_of(build.round, brief)     # a further shade, once decided, kept in its own record
    path = flow.round_root(build.round) / COPY_RECORD
    if not path.exists() or not faces.ARABIC_TYPE:
        return brief            # English only (the owner, 2026-10-29): the round's Arabic names stay on record, not set
    record = json.loads(path.read_text())
    if record.get('schema') != 'round_files_copy/1' or record.get('brief_sha256') != build.inputs['brief_sha256']:
        raise ValueError('The round’s added copy belongs to another brief.')
    names = record.get('arabic_shade_names') or {}
    if set(names) - {shade['name'] for shade in brief['shades']}:
        raise ValueError('The round’s added copy names a shade the brief does not have.')
    supplied = {}
    for shade in brief['shades']:
        value = names.get(shade['name'])
        if shade.get('name_arabic') or not value:
            continue
        if (not isinstance(value, str) or value != ' '.join(value.split()) or
                re.search(r'[A-Za-z]', value) or not re.search(r'[\u0600-\u06ff]', value)):
            raise ValueError('An added Arabic shade name must be one line of Arabic letters.')
        shade['name_arabic'] = supplied[shade['name']] = value
    if supplied:
        brief['copy_sources'] = {'arabic_shade_names': {
            'path': COPY_RECORD, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'names': supplied,
            'source': record.get('source', ''), 'confirmed': record.get('confirmed') is True}}
    return brief


def steps_of(build):
    if 'faces' not in build.steps:
        return V1_STEPS
    return STEPS if 'eye' not in build.steps else FACE_PATH_STEPS


def reading_notes(build):
    """Plain-words notes for the files page: what the reading repaired or dropped, the stand grid and added copy."""
    notes = []
    read = (build.steps.get('read') or {}).get('result') or {}
    for row in read.get('reading_findings', []) if isinstance(read, dict) else []:
        verb = {'dropped': 'left out', 'normalised': 'kept', 'replaced': 'replaced'}.get(row['action'], row['action'])
        notes.append(f"{row['label']}: {row['item']} {verb} — {row['why']}.")
    stand = (build.steps.get('stand') or {}).get('result') or {}
    layout = stand.get('layout') if isinstance(stand, dict) else None
    if layout and layout.get('note'):
        notes.append(layout['note'])
    drawn = (build.steps.get('faces') or {}).get('result') or {}
    if isinstance(drawn, dict) and drawn.get('header_leaves'):
        notes.append(drawn['header_leaves'])
    try:
        sources = files_brief(build).get('copy_sources', {})
    except (ValueError, KeyError, OSError) as exc:
        # [the owner's message of 2026-10-29, the old reds fixed, §R4] said, never silent: without the brief the page
        # cannot know whether any copy was added unconfirmed
        notes.append('The brief could not be read (%s), so whether any copy was added without your confirmation is '
                     'unknown.' % type(exc).__name__)
        sources = {}
    added = sources.get('arabic_shade_names')
    if added and not added['confirmed']:
        notes.append('Arabic shade names written by Claude, not yet confirmed by you: ' +
                     ' · '.join(f'{name} {value}' for name, value in added['names'].items()) + '.')
    return notes


def flat_pick(record):
    """Whether the round's sealed pick is a flat die (round_designer's flat_die_handoff/1)."""
    import json
    path = flow.round_root(record) / 'handoff.json'
    return path.exists() and json.loads(path.read_text()).get('schema') == 'flat_die_handoff/1'


def start(round_id, user):
    with transaction.atomic():
        record = Round.objects.select_for_update().get(pk=round_id)
        flow._owner(record, user)
        if record.state != 'complete' or not flow.is_designer_round(record):
            raise ValueError('Record your picture choice before building the files.')
        previous = RoundMaster.objects.filter(round=record).first()
        if previous is not None:
            if previous.inputs.get('schema') != FILES_SCHEMA:
                raise ValueError('This round already has a different build.')
            return previous
        snapshot = input_snapshot(record)
        snapshot['owner_start'] = {'user_id': user.pk, 'at': timezone.now().isoformat()}
        build = RoundMaster.objects.create(round=record, inputs=snapshot, budget_usd=record.budget_usd,
            current_step=STEPS[0], steps={name: {'state': 'queued' if i == 0 else 'waiting',
                'attempts': 0, 'dispatches': 0, 'history': [], 'result': {}} for i, name in enumerate(STEPS)})
        transaction.on_commit(lambda: enqueue(build.pk))
    return build


def enqueue(build_id):
    from apps.pipeline.round_tasks import run_round_files
    try:
        run_round_files.delay(build_id)
    except Exception as exc:
        fail(build_id, exc, kind='queue delivery', expected='queued')


def recover(build):
    """The page's nudge: a queued build is enqueued again; a face-path build waiting on a stop is queued so the worker
    moves it onto the gate ($0, no call). A rejected round is left as it is."""
    build.refresh_from_db()
    if flow.rejected(build.round):
        return
    if 'eye' in build.steps and 'faces' in build.steps and build.state == 'failed':
        with transaction.atomic():
            locked = RoundMaster.objects.select_for_update().get(pk=build.pk)
            if locked.state == 'failed':
                locked.state, locked.error = 'queued', ''
                locked.save()
        build.refresh_from_db()
    if build.state == 'queued':
        enqueue(build.pk)


def retry(round_id, user):
    with transaction.atomic():
        build = RoundMaster.objects.select_for_update().select_related('round').get(round_id=round_id)
        flow._owner(build.round, user)
        if build.inputs.get('schema') != FILES_SCHEMA or build.state != 'failed':
            raise ValueError('There is no failed files step to retry.')
        if 'faces' not in build.steps:
            raise ValueError(RETIRED)
        step = build.steps[build.current_step]
        step.update(attempts=step['attempts'] + 1, state='queued')
        build.state, build.error = 'queued', ''
        build.save()
        transaction.on_commit(lambda: enqueue(build.pk))
    return build


def retain_failure(build, event):
    flow.write_json(root(build) / 'failures' / (event['id'] + '.json'), event)
    job = SimpleNamespace(pk='files-' + str(build.pk), name=event['step'],
                          attempts=event['attempt'], history=[event])
    flow.record_break(build.round, job, event['error'])
    flow.commit_artifacts(build.round, 'files stop recorded')


def fail(build_id, exc, *, kind='worker', expected=None):
    with transaction.atomic():
        build = RoundMaster.objects.select_for_update().select_related('round').get(pk=build_id)
        if expected is not None and build.state != expected:
            return {'status': build.state}
        step = build.steps[build.current_step]
        event = {'step': build.current_step, 'error': f'{type(exc).__name__}: {exc}',
                 'attempt': step['attempts'], 'dispatch': step['dispatches'],
                 'kind': kind, 'at': timezone.now().isoformat()}
        event['id'] = digest(event)[:20]
        step['history'].append(event)
        step['state'] = 'failed'
        build.state, build.error = 'failed', event['error']
        build.save()
    try:
        retain_failure(build, event)
    except Exception as evidence_error:
        with transaction.atomic():
            current = RoundMaster.objects.select_for_update().get(pk=build.pk)
            current.steps[event['step']]['history'][-1]['evidence_error'] = str(evidence_error)
            current.save(update_fields=['steps', 'updated_at'])
    return {'status': 'failed', 'error': build.error}


def run(build_id):
    from . import round_files_gate as gate
    build = RoundMaster.objects.select_related('round').get(pk=build_id)
    if build.inputs.get('schema') != FILES_SCHEMA:
        raise ValueError('This is not a picture-to-files build.')
    if flow.rejected(build.round):
        return {'status': 'rejected', 'error': flow.rejected_words(build.round)}
    if build.state == 'complete':
        tag_completed(build)
        return {'status': 'complete'}
    queued = False
    with flow._job_lock(build.round) as claimed:
        if not claimed:
            return {'status': 'already_running'}
        with transaction.atomic():
            build = RoundMaster.objects.select_for_update().select_related('round').get(pk=build_id)
            if 'faces' not in build.steps:
                return {'status': 'retired'}
            if 'eye' in build.steps:
                gate.migrate(build)
            if gate.is_gate(build):
                gate.restand(build)
                gate.flatten(build)
                gate.system_repairs(build)
                gate.retype(build)
                gate.ground_repairs(build)
                gate.word_repairs(build)
                gate.stale_views(build)
            if build.state not in ('queued', 'running'):
                return {'status': build.state}
            step = build.steps[build.current_step]
            step.update(state='running', dispatches=step['dispatches'] + 1)
            build.state = 'running'
            build.save()
        try:
            context = FilesContext(build, SimpleNamespace(**step))
            context.root.mkdir(parents=True, exist_ok=True)
            for item in build.steps.values():
                for event in item['history']:
                    retain_failure(build, event)
            name = build.current_step
            if name == 'faces':
                # Each face's next job; the build then waits for the owner (Accept or Redraw per face).
                more = gate.work(context)
                if not more:
                    gate.settle_views(context)            # $0: the views from the panels and the proof sheet
                flow.commit_artifacts(build.round, 'files faces worked')
                with transaction.atomic():
                    current = RoundMaster.objects.select_for_update().get(pk=build.pk)
                    if not more:                      # settled and measured: the one repair each rule allows
                        gate.ground_repairs(current)
                        gate.word_repairs(current)
                    more = more or any(gate.pending(row) for row in gate.board(current).values())
                    current.steps['faces']['state'] = 'running' if more else 'complete'
                    if current.current_step == 'faces':
                        current.state, queued = ('queued', True) if more else ('awaiting', False)
                    current.save()
            else:
                result = gate.make(context) if name == 'files' else run_step(name, context)
                flow.write_json(context.root / 'steps' / (name + '.json'), result)
                flow.commit_artifacts(build.round, 'files ' + name + ' complete')
                with transaction.atomic():
                    current = RoundMaster.objects.select_for_update().get(pk=build.pk)
                    current.steps[name].update(state='complete', result=result)
                    if name == 'files':
                        current.state, current.publication = 'complete', result
                    else:
                        current.current_step = STEPS[STEPS.index(name) + 1]
                        if current.current_step == 'faces':
                            from .round_files_faces import FACES
                            current.steps['faces']['board'] = {key: gate.empty_face(key) for key in FACES}
                            gate.open_flat(current)
                        current.steps[current.current_step]['state'] = 'queued'
                        current.state, queued = 'queued', True
                    current.error = ''
                    current.save()
                if current.state == 'complete':
                    tag_completed(current)
        except flow.YieldRound:
            try:
                flow.commit_artifacts(build.round, 'files paid reply retained; continuing')
                with transaction.atomic():
                    current = RoundMaster.objects.select_for_update().get(pk=build.pk)
                    current.steps[current.current_step]['state'] = 'queued'
                    current.state = 'queued'
                    current.save()
                queued = True
            except Exception as exc:
                return fail(build_id, exc)
        except Exception as exc:
            return fail(build_id, exc)
    if queued:
        enqueue(build_id)
    return {'status': 'queued' if queued else current.state}


def progress(build):
    return [{'label': STEP_LABELS[name], 'state': build.steps[name]['state']} for name in steps_of(build)]


# --- the build's steps and its paid context (from round_files_job, 2026-10-28) ----------------------------------------
# Picked picture to print files. The picture is the design intent (owner, 2026-10-27): each flat face is drawn
# front-on as one edit guided by the picture, its live type and the approved logo placed, and the owner accepts or redraws
# it (owner, 2026-10-28; round_files_gate); the accepted faces are composed on the engine's die and written with the die
# locked (round_files_faces, docs/rounds/reuse-plan.md). One spend cap per round; a call whose outcome is unknown is
# checked once against the provider and closed, never a permanent stop.

#: every prefix the round's files have been paid under: the reading's and the drawings' (files/), and the retired face
#: path's attempts (files-faces/, files-faces-2/, ...). Their sum is held to the build's one cap.
FILES_PREFIXES = "operation LIKE 'files/%' OR operation LIKE 'files-faces%'"


class LostCall(ValueError):
    """A paid call whose outcome is unknown: checked once against the provider, then closed; never sent twice."""


def provider_check(provider, reservation_id):
    """The one check of a lost call against the provider. OpenAI reports image usage only to an organisation admin
    key (OPENAI_ADMIN_KEY); Anthropic offers no lookup of a request that returned nothing. Without a lookup, the check
    is recorded as unavailable and the hold stays counted."""
    key = getattr(settings, 'OPENAI_ADMIN_KEY', '') if provider == 'openai' else ''
    if not key:
        return {'checked': False, 'billed': None, 'why': (
            'OpenAI\'s usage records need an organisation admin key, which this app does not hold (the project key '
            'is refused: 403)' if provider == 'openai' else 'Anthropic offers no lookup of a request that returned '
            'nothing')}
    import httpx
    from datetime import datetime, timedelta
    with spend._connect() as db:
        started = datetime.fromisoformat(db.execute('SELECT started_at FROM calls WHERE id=?',
                                                    (reservation_id,)).fetchone()[0])
        window = (started - timedelta(minutes=1), started + timedelta(minutes=15))
        # the app's own other image calls that came back in the window: their images are not this call's
        own = sum(1 for (settled,) in db.execute(
            "SELECT settled_at FROM calls WHERE provider='openai' AND state='usage_recorded' AND id<>? AND "
            "operation LIKE '%image/%' AND settled_at IS NOT NULL", (reservation_id,))
            if window[0] <= datetime.fromisoformat(settled) <= window[1])
    if datetime.now(started.tzinfo) < window[1] + timedelta(minutes=USAGE_SETTLE_MINUTES):
        return {'checked': False, 'billed': None, 'pending': True,
                'why': 'OpenAI\'s usage for the call\'s window is final after %s; it is checked again then'
                       % (window[1] + timedelta(minutes=USAGE_SETTLE_MINUTES)).isoformat(timespec='minutes')}
    try:
        reply = httpx.get('https://api.openai.com/v1/organization/usage/images', timeout=30,
                          headers={'Authorization': 'Bearer ' + key},
                          params={'start_time': int((started - timedelta(minutes=1)).timestamp()),
                                  'end_time': int((started + timedelta(minutes=15)).timestamp()),
                                  'bucket_width': '1m', 'models': IMAGE_MODEL})
        reply.raise_for_status()
        # [the owner's message of 2026-10-29, the old reds fixed, §R4] every field read, none defaulted: a reply without
        # its data, a bucket without its results or a row without its count is a failed lookup (the hold stays counted),
        # never "nothing billed" (close_unknown releases a hold only on billed False)
        images = sum(row['images'] for bucket in reply.json()['data'] for row in bucket['results'])
        if isinstance(images, bool) or not isinstance(images, int):
            raise TypeError('the usage reply\'s image count is not a whole number')
    except Exception as exc:
        return {'checked': False, 'billed': None, 'why': 'the usage lookup failed: ' + type(exc).__name__}
    return {'checked': True, 'billed': images > own, 'images_in_window': images, 'own_images_in_window': own,
            'why': 'OpenAI\'s image usage in the call\'s window, beyond the app\'s own other calls there'}


USAGE_SETTLE_MINUTES = 10                     # OpenAI's per-minute usage settles some minutes after the window


def recheck_lost(build):
    """Every call of this build closed with its outcome unknown and not yet answered by the provider, checked again
    (the owner, 2026-10-30: "check its outcome with the provider before giving up, so it's never charged twice"):
    released to $0 when OpenAI's final usage shows it was not billed; kept counted, its answer recorded, when it was;
    left for the next delivery while the answer is not final or cannot be had. Returns each call's check."""
    slug = build.round.slug
    with spend._connect() as db:
        rows = [dict(row) for row in db.execute(
            "SELECT id, usage FROM calls WHERE state='outcome_unknown' AND provider='openai' AND operation LIKE ?",
            ('files/' + slug + '/image/%',))]
    checks = {}
    for row in rows:
        before = json.loads(row['usage']) if row['usage'] else {}
        if before.get('checked') is True:
            continue
        check = provider_check('openai', row['id'])
        checks[row['id']] = check
        if check['checked']:
            spend.release_unknown(row['id'], check)
    return checks


def read(path):
    return json.loads(Path(path).read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def execution_brief(brief):
    """Missing physical dimensions become explicit provisional estimates."""
    result = deepcopy(brief)
    values = result['dimensions_mm']
    estimates = {}
    for key, estimate in (('width', 15.), ('height', 100.)):
        if values.get(key) is None:
            values[key] = estimate
            estimates[key] = estimate
    for key, estimate in (('depth', values['width']), ('cap_height', values['height'] * .3)):
        if values.get(key) is None:
            values[key] = estimate
            estimates[key] = estimate
    if estimates:
        result['measurements_provisional'] = True
    result['execution_estimates_mm'] = estimates
    return result


def input_snapshot(record):
    from .round_files_export import LOGO, LOGO_SHA256, font_records
    from apps.dashboard.product_round_views import publication
    folder = flow.round_root(record)
    handoff = read(folder / 'handoff.json')
    published = publication(record)
    if (record.pick.get('merge') or handoff['id'] != record.pick['id'] or
            handoff['source_round'] != record.pk or handoff['reason'] != record.pick['reason']):
        raise ValueError('The recorded choice and frozen picture handoff must agree.')
    picture = (folder / handoff['picture']).resolve()
    if (not picture.is_relative_to(folder) or published['files'].get(handoff['picture']) != handoff['picture_sha256']
            or sha(picture) != handoff['picture_sha256']):
        raise ValueError('The chosen picture no longer matches its publication.')
    if sha(LOGO) != LOGO_SHA256:
        raise ValueError('The approved logo changed.')
    policy = read(flow.REPO / 'docs/rounds/files-build-policy.json')
    snapshot = {'schema': FILES_SCHEMA, 'contract': handoff['contract'], 'picture': handoff['picture'],
            'picture_sha256': handoff['picture_sha256'], 'handoff_sha256': sha(folder / 'handoff.json'),
            'pick': deepcopy(record.pick), 'brief': execution_brief(record.product_brief),
            'brief_sha256': digest(record.product_brief), 'logo_sha256': LOGO_SHA256,
            'fonts': font_records(), 'policy': deepcopy(policy['default']),
            'completion_tag': policy['completion_tags'].get(record.slug, ''), 'budget_usd': float(record.budget_usd)}
    if handoff['schema'] == 'flat_die_handoff/1':
        # a flat pick (the owner's goal of 2026-10-29: the chain's one break closed): the painting it was and its die
        snapshot['flat_pick'] = {'painting': handoff['painting'], 'die': handoff['die']}
    return snapshot



class FilesContext(RoundContext):
    def __init__(self, build, job=None, *, text_client=None, image_client=None, native=True):
        super().__init__(build.round, job, text_client=text_client, image_client=image_client)
        self.build = build
        self.round = copy(build.round)
        self.round.budget_usd = build.budget_usd
        self.root = flow.round_root(build.round) / 'files'
        self.prefix = f'files/{build.round.slug}/'
        # One spend cap per round (owner, 2026-10-28): new calls go under files/<slug>/, held to what the build's cap
        # leaves after the retired attempts' prefixes; no separate image-count cap.
        spent = scoped_spend(build)
        self.round.budget_usd = max(float(build.budget_usd) - (spent['accounted_usd'] - spent['this_prefix_usd']), 0.01)
        self.image_attempt_cap = 10_000
        self.brief = files_brief(build)
        self.native = native
        if not native and 'pytest' not in sys.modules:
            raise ValueError('Only isolated fixtures may omit the Illustrator save/reopen.')

    def _unknown_outcome(self, destination, request, provider):
        self._close_lost(destination, request['reservation_id'], provider)

    def _close_lost(self, destination, reservation_id, provider, error=None):
        """A call whose outcome is unknown: checked once against the provider, closed, and reported; the face it
        belongs to is marked failed and only the owner's Redraw buys a new drawing."""
        check = provider_check(provider, reservation_id)
        spend.close_unknown(reservation_id, dict(check, error=error or 'started, nothing saved'))
        flow.write_json(Path(destination).with_suffix('.lost.json'), {
            'reservation_id': reservation_id, 'provider': provider, 'check': check, 'error': error,
            'rule': 'checked once against the provider, then closed; never sent twice (owner, 2026-10-28)'})
        flow.commit_artifacts(self.round, 'a lost call checked once and closed')
        raise LostCall('The call\'s outcome is unknown (nothing came back). It was checked once and closed: '
                       + check['why'] + '.')

    def image_call(self, *args, **kwargs):
        raise ValueError('The execution half draws only its flat faces, through face_edit.')

    def text_call(self, operation, prompt, destination, **kwargs):
        if not operation.startswith('eye/'):
            return super().text_call(operation, prompt, destination, **kwargs)
        _, key, n = (operation.split('/') + ['', ''])[:3]
        if key not in faces.FACES or not n.isdigit():
            raise ValueError('The eye looks only at a drawn face.')
        expected = (faces.drawing_folder(self.root, key, int(n)) / 'eye.json').resolve()
        if Path(destination).resolve() != expected:
            raise ValueError('The eye\'s notes on a drawing use its own durable record.')
        try:
            return super().text_call(operation, prompt, destination, **kwargs)
        except (LostCall, flow.YieldRound):
            raise
        except Exception as exc:
            request = expected.with_suffix('.request.json')
            errors = sorted(expected.parent.glob(expected.stem + '.error-*.json'))
            if (request.exists() and errors and read(errors[-1]).get('http_status') is None and
                    _ledger_state(read(request)['reservation_id']) == 'reserved'):
                self._close_lost(expected, read(request)['reservation_id'], 'anthropic', type(exc).__name__)
            raise

    def face_edit(self, operation, prompt, folder, *, template, references, size, quality='high'):
        """One gpt-image-2 edit, high or (``quality``) medium: image 1 its template (its own mask), then its references. ``face/<key>/<n>``: a
        product face guided by the picked picture's view of it (and, for a Redraw with the owner's note, the previous
        drawing), or a stand face repainted on the flat die; ``flat/stand/<n>``: the whole flat die painted, image 2
        the style reference. Saved replies are never bought twice; one new call per delivery."""
        return self._face_edit(operation, prompt, folder, template=template, references=references, size=size,
                               quality=quality)

    def _face_edit(self, operation, prompt, folder, *, template, references, size, quality):
        from . import round_calls as image_guard
        kind, key, n = (operation.split('/') + ['', ''])[:3]
        if kind == 'flat' and key == 'stand' and n.isdigit():
            expected = (faces.flat_root(self.root) / 'paintings' / n / 'call').resolve()
            sheet = faces.flat_root(self.root).resolve() / 'template.png'
        elif kind == 'face' and key in faces.FACES and n.isdigit():
            expected = (faces.drawing_folder(self.root, key, int(n)) / 'call').resolve()
            sheet = expected.parent / 'template.png'
        elif kind == 'motif' and key == 'sheet' and n.isdigit():
            expected = (faces.motifs_root(self.root) / ('sheet-' + n) / 'call').resolve()
            sheet = expected.parent / 'template.png'
        elif kind == 'wrap' and (key == 'stand' or key in faces.FACES) and n.isdigit():
            expected = (faces.wrap_folder(self.root, key, int(n)) / 'call').resolve()
            sheet = expected.parent / 'template.png'
        else:
            raise ValueError('Only a face\'s own drawing, a wrap or the flat die\'s painting may be drawn.')
        destination = self._destination(Path(folder) / 'image-call.json')
        if destination.parent != expected:
            raise ValueError('A face edit must use its own durable folder.')
        template = Path(template).resolve()
        paths = [template] + [Path(path).resolve() for path in references]
        if template != sheet or not 1 <= len(references) <= 2:
            raise ValueError('A face edit uses its own template and its reference.')
        if settings.IMAGE_MODEL != IMAGE_MODEL or image_guard.competitor_in(prompt):
            raise ValueError('The face edit requires gpt-image-2 and a permitted prompt.')
        if size not in ('1536x1024', '1024x1536') and not (kind == 'face' and faces.is_panel_size(size)) and not (
                kind == 'wrap' and faces.is_wrap_size(size)):
            raise ValueError('A face edit requires a supported full-resolution canvas.')
        inputs = [self._input(path) for path in paths]
        if inputs[0]['px'] != [int(value) for value in size.split('x')]:
            raise ValueError('A face template must be its full-resolution canvas.')
        with Image.open(template) as image:
            if image.mode != 'RGBA' or image.getchannel('A').getextrema() != (0, 255):
                raise ValueError('A face template needs both its transparent face and protected white.')
        if quality not in faces.OUTPUT_TOKENS_PER_MP:
            raise ValueError('A face edit is drawn at high or medium quality.')
        identity = {'model': IMAGE_MODEL, 'quality': quality, 'size': size, 'prompt': prompt, 'inputs': inputs,
                    'mask': inputs[0], 'protocol': 'picture-face-edit/1',
                    'stream': {'partial_images': STREAM_PARTIAL_IMAGES}}
        op = 'image/' + operation
        cached, request, request_path = self._request(destination, identity, provider='openai', operation=op,
                                                      estimate=faces.edit_hold(size, quality,
                                                                               [item['px'] for item in inputs],
                                                                               prompt))
        if cached is not None:
            if sha(destination.parent / 'raw.png') != cached['output_sha256']:
                raise ValueError('A saved face edit changed; no repurchase.')
            return cached
        raw_path = destination.with_suffix('.response.json')
        if raw_path.exists():
            raw = read(raw_path)
        else:
            if request['started_attempts']:
                self._unknown_outcome(destination, request, 'openai')
            if request['reservation_id'] not in self.active_calls:
                self._one_call()
                self.active_calls.add(request['reservation_id'])
            request['started_attempts'] = [0]
            flow.write_json(request_path, request)
            if self.image_client is None:
                if 'pytest' in sys.modules:
                    raise RuntimeError('Files fixtures require an explicit fake image client.')
                from openai import OpenAI
                self.image_client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0, timeout=400)
            try:
                opened = [path.open('rb') for path in paths]
                mask = template.open('rb')
                try:
                    raw = streamed_edit(self.image_client, destination.with_suffix('.stream.json'), model=IMAGE_MODEL,
                                        quality=quality, size=size, prompt=prompt, n=1, image=opened, mask=mask)
                finally:
                    for handle in opened + [mask]:
                        handle.close()
            except Exception as exc:
                status = spend.rejected_status(exc)
                if status is not None:
                    spend.release_rejected(request['reservation_id'], status, exc)
                flow.write_json(destination.with_suffix('.error.json'), {'error_type': type(exc).__name__,
                                'http_status': status, 'reservation_id': request['reservation_id']})
                flow.commit_artifacts(self.round, f'{op}: provider failure retained')
                if status is None:
                    self._close_lost(destination, request['reservation_id'], 'openai', type(exc).__name__)
                raise
            flow.write_json(raw_path, raw)
            flow.commit_artifacts(self.round, f'{op}: raw face edit retained')
        spend.settle(request['reservation_id'], raw, raw_path, provider='openai', model=IMAGE_MODEL)

        def reject_image(reason):
            self._finish(destination, request, dict(identity, status='validation_failed', usage=raw.get('usage'),
                         validation_error=str(reason)), operation=op, image=True)
            raise ValueError('Invalid face edit reply retained: ' + str(reason))

        image_url = None
        try:
            data = raw['data']
            if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError('One edited image is required')
            if data[0].get('b64_json'):
                image_bytes = base64.b64decode(data[0]['b64_json'], validate=True)
            elif data[0].get('url'):
                image_url = data[0]['url']
            else:
                raise ValueError('Edited image bytes missing')
        except (KeyError, TypeError, ValueError, binascii.Error) as exc:
            reject_image(exc)
        if image_url is not None:
            from .round_calls import download_image_bytes
            image_bytes = download_image_bytes(image_url)
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                image.load()
                if list(image.size) != inputs[0]['px']:
                    raise ValueError('Edited image has incorrect dimensions')
        except (TypeError, ValueError, UnidentifiedImageError, OSError) as exc:
            reject_image(exc)
        (destination.parent / 'raw.png').write_bytes(image_bytes)
        return self._finish(destination, request, dict(identity, status='complete',
                            output_sha256=sha(destination.parent / 'raw.png'), usage=raw.get('usage')),
                            operation=op, image=True)


def _ledger_state(reservation_id):
    with spend._connect() as db:
        row = db.execute('SELECT state FROM calls WHERE id=?', (reservation_id,)).fetchone()
    return row['state'] if row else None


def scoped_spend(build):
    """The round's files spend against its one cap: every files prefix of the round (FILES_PREFIXES) — what was billed,
    what is held, what was lost with its outcome unknown — and, apart, the share under files/<slug>/."""
    slug = build.round.slug
    with spend._connect() as db:
        rows = [dict(row) for row in db.execute('SELECT * FROM calls WHERE (' + FILES_PREFIXES + ') AND operation LIKE ?',
                                                ('%/' + slug + '/%',))]
    rows = [row for row in rows if row['operation'].split('/', 2)[1] == slug]
    usd = lambda picked: sum(row['accounted'] for row in picked) / 1e6
    return {'actual_usd': usd(r for r in rows if r['state'] == 'usage_recorded'),
            'held_usd': usd(r for r in rows if r['state'] in ('reserved', 'billing_unresolved')),
            'unknown_usd': usd(r for r in rows if r['state'] == 'outcome_unknown'),
            'accounted_usd': usd(rows), 'calls': len(rows), 'budget_usd': float(build.budget_usd),
            'this_prefix_usd': usd(r for r in rows if r['operation'].startswith('files/' + slug + '/')),
            'flat_usd': usd(r for r in rows if r['operation'].startswith('files/' + slug + '/image/flat/')),
            'reading_usd': usd(r for r in rows if r['operation'].startswith('files/' + slug + '/reading'))}


def checked_inputs(ctx):
    from .round_files_export import LOGO, font_records
    inputs = ctx.build.inputs
    folder = flow.round_root(ctx.build.round)
    if (digest(ctx.build.round.product_brief) != inputs['brief_sha256'] or
            ctx.build.round.pick != inputs['pick'] or sha(folder / 'handoff.json') != inputs['handoff_sha256'] or
            sha(folder / inputs['picture']) != inputs['picture_sha256'] or
            sha(LOGO) != inputs['logo_sha256'] or font_records() != inputs['fonts']):
        raise ValueError('A frozen picture, brief, pick, logo or granted font changed.')
    return folder / inputs['picture']



FLAT_READING_NOTE = ('A flat pick, read at $0 from its own die: each stand panel is its face on the die; the bottle and '
                     'the cap follow the header\'s design (the flat design shows no product); no words were read, so '
                     'its faces carry no live type yet; which shade stands at which seat is unresolved.')


def flat_reading(ctx):
    """A flat pick's reading, $0 and no call: the picked flat die's own printed faces as the panels (from the round's
    die template), the bottle's and cap's panels the header (their style), every seat's shade unresolved."""
    from .round_files_faces import validate_inspection
    source = checked_inputs(ctx)
    copied = ctx.root / 'source.png'
    if not copied.exists():
        shutil.copyfile(source, copied)
    if sha(copied) != ctx.build.inputs['picture_sha256']:
        raise ValueError('The retained picked picture changed.')
    flow.write_json(ctx.root / 'inputs.json', ctx.build.inputs)
    with Image.open(copied) as image:
        size = list(image.size)
    setup = read(flow.round_root(ctx.round) / Path(ctx.build.inputs['flat_pick']['die']).parent / 'flat' / 'template.json')
    boxes = {face['name']: face['box_px'] for face in setup['faces'] if face['printed']}

    def panel(name, **extra):
        x0, y0, x1, y1 = (int(round(v)) for v in boxes[name])
        return dict({'crop_px': [x0, y0, x1, y1], 'print_polygon_px': [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
                     'text': [], 'marks': []}, **extra)
    layout = ctx.brief['stand']['layout']
    rows, columns = int(layout['rows']), int(layout['columns'])
    inspection = {'image_size_px': size, 'flat_pick': True, 'unprinted_faces': [], 'notes': [FLAT_READING_NOTE],
                  'panels': {'stand_header': panel('header front'), 'stand_base': panel('front panel'),
                             'body_front': panel('header front', style_only=True),
                             'cap_front': panel('header front', style_only=True)},
                  'stand': {'rows': rows, 'columns': columns, 'count': rows * columns,
                            'bottles': [{'row': r, 'column': c, 'box_px': [0, 0, 1, 1], 'shade_field': None}
                                        for r in range(rows) for c in range(columns)]}}
    inspection = validate_inspection(inspection, size, ctx.brief)
    flow.write_json(ctx.root / 'inspection.json', inspection)
    return inspection


def read_picture(ctx):
    from .round_files_faces import copy_fields, normalise_reading, validate_inspection
    if ctx.build.inputs.get('flat_pick'):
        return flat_reading(ctx)
    source = checked_inputs(ctx)
    copied = ctx.root / 'source.png'
    if copied.exists() and sha(copied) != ctx.build.inputs['picture_sha256']:
        raise ValueError('The retained picked picture changed.')
    if not copied.exists():
        shutil.copyfile(source, copied)
    flow.write_json(ctx.root / 'inputs.json', ctx.build.inputs)
    with Image.open(copied) as image:
        size = list(image.size)
    prompt = (
        'Read this one picked picture for print-file extraction. Do NOT design, redraw, repaint or improve it. '
        'Locate the large standalone hero product body FRONT (excluding cap), cap FRONT, '
        'the stand header printed front and stand base strip printed front. Return absolute integer '
        'pixel coordinates in the original image coordinate system. Crop only each printed planar face, '
        'excluding surroundings, perspective side walls and physical thickness. '
        'For the stand header, crop the printed interior artwork, excluding any physical gold arched trim, '
        'metallic rim or surrounding frame. Its print_polygon_px must follow the visible printed-art boundary '
        'inside that trim. If this printed interior is arched, use its full rectangular bounding box and '
        'record the actual arched silhouette; do not include the physical trim in line-art regions. '
        'The squared header corners will be filled only by extending the printed artwork’s own nearest '
        'silhouette-edge pixels. Preserve its interior without stretching, repainting or copying the gold rim. '
        'Count the actual loaded products shown on the stand, including partially occluded back rows; '
        'never substitute the intake stand count. Ignore the standalone hero and loose wand. '
        'Record a box for every loaded bottle, including the visible portion of a partly occluded bottle. '
        'Rows are zero-based from front to back and columns are zero-based from left to right; '
        'count must equal rows times columns. Each bottle must include shade_field naming the supplied '
        'shade_N COPY field that matches its observed shade, or null when unresolved. Never cycle or guess '
        'shades to fill the grid. Identify the hero bottle shade only through its actual shade_N text entry; '
        'if its shade name cannot be read, do not invent a shade text entry. '
        'Separate line art from letters/logo and physical metallic edges. Mark tight line-art regions; '
        'exclude physical cap reflections, acrylic edges, liquid and surrounding frame thickness. '
        'Give a tight box for EVERY visible word or logo, with enough room to cover antialiased lettering. '
        'Words are specified ONLY by the COPY field key below, never instructions or invented text. '
        'A printed word that means a COPY field takes that field even when the picture misspells it; '
        'the files set the field’s exact words. '
        'Use multiple entries for separate Latin and Arabic lines. Every BBROSE mark is kind logo. '
        'rotation is the turn of the lettering as seen: 0 upright, 90 reads bottom to top, '
        '180 upside down, 270 reads top to bottom. For a word set at another angle or along a curve, '
        'give its tight bounding box, the nearest of those turns, and "angle_deg" or "arc": true. '
        'Lettering the picture invented that matches no COPY field (pseudo-script, a decorative calligraphy band) '
        'is neither text nor line art: list it under that panel’s ornament_lettering as '
        '{"path_px":[[x,y],...] along the centre line of the lettering band, in the direction its letters advance '
        '(letter tops on the left-hand side of travel), "height_px": the band’s letter height, "color":"#RRGGBB"}. '
        'Never transcribe it; keep it out of lineart_boxes_px. '
        'colour_print_boxes_px identifies actual decorative colour ink on the body, never the liquid or clear acrylic. '
        'The cap substrate is metal: it is not colour ink. Record hidden/back/side faces as unprinted unless visible '
        'decoration proves otherwise. The one owner change is a square header top; do not invent new artwork. '
        'Return JSON only, following this valid example structure: '
        '{"image_size_px":[1536,1024],"stand":{"rows":2,"columns":3,"count":6,'
        '"bottles":[{"row":0,"column":0,"box_px":[650,500,700,800],"shade_field":"shade_0"},'
        '{"row":0,"column":1,"box_px":[800,500,850,800],"shade_field":"shade_1"},'
        '{"row":0,"column":2,"box_px":[950,500,1000,800],"shade_field":null},'
        '{"row":1,"column":0,"box_px":[675,450,725,750],"shade_field":"shade_0"},'
        '{"row":1,"column":1,"box_px":[825,450,875,750],"shade_field":"shade_1"},'
        '{"row":1,"column":2,"box_px":[975,450,1025,750],"shade_field":null}]},'
        '"panels":{"body_front":{"crop_px":[100,300,200,800],'
        '"print_polygon_px":[[100,300],[200,300],[200,800],[100,800]],'
        '"text":[{"field":"product_latin","box_px":[110,650,190,680],"color":"#D5AF59","rotation":0},'
        '{"field":"shade_0","box_px":[110,700,190,725],"color":"#D5AF59","rotation":0}],'
        '"marks":[],"lineart_boxes_px":[[110,350,190,620]],"colour_print_boxes_px":[]},'
        '"cap_front":{"crop_px":[100,100,200,300],'
        '"print_polygon_px":[[100,100],[200,100],[200,300],[100,300]],"text":[], '
        '"marks":[{"kind":"logo","box_px":[125,150,175,200],"color":"#D5AF59","rotation":0}],'
        '"lineart_boxes_px":[],"colour_print_boxes_px":[]},'
        '"stand_header":{"crop_px":[600,100,1200,400],'
        '"print_polygon_px":[[600,200],[750,125],[900,100],[1050,125],[1200,200],[1200,400],[600,400]],'
        '"text":[{"field":"product_latin","box_px":[700,300,1100,340],"color":"#D5AF59","rotation":0}],'
        '"marks":[],"lineart_boxes_px":[],"colour_print_boxes_px":[],'
        '"ornament_lettering":[{"path_px":[[620,190],[900,112],[1180,190]],"height_px":28,"color":"#D5AF59"}]},'
        '"stand_base":{"crop_px":[600,800,1200,900],'
        '"print_polygon_px":[[600,800],[1200,800],[1200,900],[600,900]],'
        '"text":[],"marks":[],"lineart_boxes_px":[],"colour_print_boxes_px":[],"ornament_lettering":[]}},'
        '"unprinted_faces":[{"face":"back","reason":"not shown"}],"notes":["observed facts only"]}. '
        'Only list observations you can locate in the picture. Every coordinate, count, field and arrangement '
        'in the example is illustrative: measure this picture and use only the available COPY fields below. '
        'Return all four panel objects with these fields; use empty arrays when no such element is observed '
        '(ornament_lettering may be omitted where there is none). '
        '\nIMAGE SIZE: ' + json.dumps(size) +
        '\nCOPY FIELDS: ' + json.dumps(copy_fields(ctx.brief), ensure_ascii=False) +
        '\nPRODUCT MATERIAL: ' + ctx.brief['material'])
    destination = ctx.root / 'reading-call.json'
    call = ctx.text_call('locate-picture', prompt, destination, images=[('Picked picture, unchanged', copied)],
                         max_tokens=16384, ceiling=2.0)
    try:
        inspection = validate_inspection(normalise_reading(call['payload'], size, ctx.brief), size, ctx.brief)
        stand = inspection['stand']
        if (any(not isinstance(stand[key], int) or isinstance(stand[key], bool) or stand[key] < 1
                for key in ('rows', 'columns', 'count')) or stand['rows'] * stand['columns'] != stand['count']
                or stand['count'] > 100):
            raise ValueError('The observed rows, columns and product count must agree.')
        if not isinstance(inspection.get('unprinted_faces'), list) or not isinstance(inspection.get('notes'), list):
            raise ValueError('The reading must list unprinted faces and observed findings.')
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        ctx.reject_result(destination, str(exc))
        raise
    flow.write_json(ctx.root / 'inspection.json', inspection)
    return inspection


def prepare_stand(ctx):
    from .round_files_gate import build_stand
    if ctx.build.inputs.get('flat_pick'):
        # the die solved again from the brief alone, as the designer drew it first; it must be the die it was painted on
        result = build_stand(ctx.brief, None, ctx.root / 'stand')
        painted_on = read(flow.round_root(ctx.round) / ctx.build.inputs['flat_pick']['die'])
        if digest(result['record']) != digest(painted_on['record']):
            raise ValueError('The stand solved again from your brief is not the die your pick was painted on; nothing '
                             'was drawn.')
        flow.write_json(ctx.root / 'stand.json', result)
        return result
    result = build_stand(ctx.brief, read(ctx.root / 'inspection.json'), ctx.root / 'stand', picture=ctx.root / 'source.png')
    flow.write_json(ctx.root / 'stand.json', result)
    return result


def _relative(ctx, path):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(ctx.root.resolve()):
        raise ValueError('A files artifact escaped its build folder.')
    return str(resolved.relative_to(ctx.root.resolve()))


def _liquid(ctx):
    shades = ctx.brief.get('shades') or []
    return shades[0]['hex'] if shades and shades[0].get('hex') else None


def build_outputs(ctx, drawn, revision):
    """The faces composed and written: bottle front, cap and stand through the writer (native Illustrator save and
    reopen in the worker), each face rendered back from its file for the eye, and the built drawing."""
    from .round_files_export import export_object
    from .round_files_faces import shade_loading
    folder = ctx.root / 'revisions' / str(revision)
    manifest = folder / 'outputs.json'
    inspection, geometry = read(ctx.root / 'inspection.json'), read(ctx.root / 'stand.json')
    binding = {'faces': digest({key: row['face_sha256'] for key, row in drawn.items()}),
               'source': ctx.build.inputs['picture_sha256'], 'native': ctx.native, 'inspection': digest(inspection),
               'geometry': digest(geometry), 'contract': 'picture_design_intent/1'}
    if ctx.brief.get('copy_sources'):
        from .round_files_faces import copy_fields
        binding['copy'] = digest(copy_fields(ctx.brief))
    if manifest.exists():
        prior = read(manifest)
        if prior['binding'] != binding or any(sha(ctx.root / path) != value for path, value in prior['pins'].items()):
            raise ValueError('A retained files revision changed.')
        return prior
    folder.mkdir(parents=True, exist_ok=True)
    specs, placements = faces.specs(drawn, inspection, ctx.brief, geometry, folder)
    flow.write_json(folder / 'specs.json', specs)
    objects = [export_object(spec, folder, native=ctx.native) for spec in specs]
    views = faces.face_views(objects, placements, folder / 'views', liquid=_liquid(ctx))
    loading = shade_loading(inspection, ctx.brief)
    found = faces.design_ground(ctx.build.round)
    drawing_record = faces.drawing(views, ctx.brief, geometry, loading, folder / 'drawing', sides=faces.net_sides(drawn), ground_hex=found['hex'] if found else None)
    pins = {_relative(ctx, path): sha(path) for path in folder.rglob('*') if path.is_file()}
    result = {'binding': binding, 'revision': revision, 'specs': specs, 'objects': objects,
              'placements': placements, 'views': {key: _relative(ctx, path) for key, path in views.items()},
              'drawing': _relative(ctx, drawing_record['file']), 'drawing_record': drawing_record, 'pins': pins}
    flow.write_json(manifest, result)
    return result


def tag_completed(build):
    import fcntl
    name = build.inputs['completion_tag']
    if not name or build.state != 'complete' or 'pytest' in sys.modules or not getattr(settings, 'ROUND_COMMIT_ARTIFACTS', True):
        return
    if name != 'round-gloss-files-a':
        raise ValueError('Unrecognized owner-requested closing tag.')
    with (flow.REPO/'.git/round-artifacts.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        exists = subprocess.run(['git', 'rev-parse', '--verify', 'refs/tags/'+name], cwd=flow.REPO, capture_output=True)
        if exists.returncode == 0:
            relative = str((flow.round_root(build.round)/'files/publication.json').relative_to(flow.REPO))
            saved = subprocess.run(['git', 'show', name+':'+relative], cwd=flow.REPO, check=True, capture_output=True)
            if json.loads(saved.stdout) != build.publication:
                raise ValueError('The closing tag belongs to different files; it will not move.')
            return
        subprocess.run(['git', 'tag', '-a', name, '-m', 'Owner-picked picture built through the app; files and designer verdict retained'],
                       cwd=flow.REPO, check=True, capture_output=True)



def run_step(name, ctx):
    """The reading and the die; the faces and the files are the gate's (round_files_gate)."""
    checked_inputs(ctx)
    for step_name, path in (('read', 'inspection.json'), ('stand', 'stand.json')):
        saved = ctx.build.steps[step_name]
        if saved['state'] == 'complete' and read(ctx.root / path) != saved['result']:
            raise ValueError('A completed files step changed: ' + step_name)
    return {'read': read_picture, 'stand': prepare_stand}[name](ctx)


# --- the chain's own preflight (the owner's goal of 2026-10-29, §5: the restart's check moved off the ARIA preflight) --

CHAIN_ENGINES = ('apps.dielines.geometry.engine', 'apps.dielines.geometry.counter_display',
                 'apps.dielines.exporters.counter_display_files', 'apps.pipeline.services.round_designer',
                 'apps.pipeline.services.round_flow', 'apps.pipeline.services.round_calls',
                 'apps.pipeline.services.spend_reservation', 'apps.pipeline.services.round_files_gate',
                 'apps.pipeline.services.round_files_faces', 'apps.pipeline.services.round_files_export',
                 'apps.pipeline.services.product_drawing')


def chain_preflight():
    """What the house restart script checks before a worker serves the chain ($0, read-only): every engine of the chain
    imports; the stand die resolves at its production version; the writer's pinned fonts and approved logo are the
    bytes they were pinned as; the image model and its tariff are set; the spend ledger answers. READY or BLOCKED,
    with each check's reason."""
    import importlib
    from apps.dielines import registry
    from apps.dielines.geometry import counter_display
    from . import round_files_export as export
    from . import spend_reservation as spend
    checks = {}

    def check(name, fn):
        try:
            value = fn()
            checks[name] = {'ok': True, 'detail': value}
        except Exception as exc:
            checks[name] = {'ok': False, 'detail': ('%s: %s' % (type(exc).__name__, exc))[:300]}

    check('engines_import', lambda: [importlib.import_module(name).__name__.rsplit('.', 1)[1] for name in CHAIN_ENGINES])
    check('stand_die_resolves', lambda: '%s %s' % (counter_display.TEMPLATE_ID,
                                                    registry.resolve(counter_display.TEMPLATE_ID, counter_display.VERSION).version))
    check('pinned_fonts', lambda: sorted(export.font_records()))

    def logo():
        if sha(export.LOGO) != export.LOGO_SHA256:
            raise ValueError('the approved logo is not its pinned bytes')
        return export.LOGO.name
    check('approved_logo', logo)

    def image_model():
        from .round_calls import IMAGE_MODEL
        if settings.IMAGE_MODEL != IMAGE_MODEL or IMAGE_MODEL not in settings.OPENAI_IMAGE_PRICES:
            raise ValueError('the image model or its tariff is not the chain\'s')
        return IMAGE_MODEL
    check('image_model', image_model)

    def ledger():
        with spend._connect() as db:
            return db.execute('SELECT COUNT(*) FROM calls').fetchone()[0]
    check('spend_ledger', ledger)
    return {'schema': 'chain_preflight/1', 'result': 'READY' if all(row['ok'] for row in checks.values()) else 'BLOCKED',
            'checks': checks}
