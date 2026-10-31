"""Day 8 §6 — the palette pick page: the concepts that pass the jury, large; every sketch and build in a history tab;
the "below the bar" sheet when none passes. Read-only; every file hash-checked against its publication record.

Day 9 §6: Day 9's round sits on top of the same page (``dashboard/day9_pick_section.html``, its context under the one
key ``day9``) and Day 8's section below it, unchanged. A Day 9 record that is not there yet, has changed or cannot be
read is said in Day 9's section and never takes Day 8's page down; Day 9's files are served by ``day9_artifact``, each
re-hashed against its pin on every request."""
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse
from django.views.decorators.http import require_GET

from .fidelity_views import member
from apps.pipeline.services import day8_pick, day9_pick, day10_master

TABS = ('pick', 'history', 'jury')
INLINE = ('image/png', 'application/pdf', 'image/svg+xml', 'application/json')
CSS_PX_PER_INCH = 96              # CSS fixes 1 in = 96 px = 25.4 mm: a crop drawn at its dpi in these px is at 1 : 1
ENUM_ANSWERS = ('must_rebuild',)  # answers that are lists of code words (jury.MUST_REBUILD), shown as words


def _context(request, tab):
    member(request.user)
    if tab not in TABS:
        raise Http404
    try:
        record = day8_pick.checked()
    except (ValueError, KeyError, OSError):
        raise Http404
    url = {role: reverse('dashboard:day8_file', args=[role]) for role in record['downloads']}
    concepts = [dict(c, urls={k: url[r] for k, r in c['files'].items()}) for c in record['concepts']]
    by_id = {c['id']: c for c in concepts}
    shown = [by_id[i] for i in (record['passing'] or record['below_the_bar'])]
    sketches = [dict(s, url=url[s['file']]) for s in record['sketches']]
    return {'tab': tab, 'tabs': TABS, 'record': record, 'shown': shown, 'none_pass': not record['passing'],
            'concepts': concepts, 'sketches': sketches, 'contacts': [url.get(f'contact-{d}') for d in 'ABC'],
            'calibration_rows': [(k.replace('_', ' '), val) for k, val in (record.get('calibration') or {}).items()]
            if isinstance(record.get('calibration'), dict) else [],
            'day9': _day9(), 'day10': _day10()}


def _said(value):
    """An answer in words: yes or no, a list joined, a missing answer named."""
    if value is None:
        return 'not answered'
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    if isinstance(value, (list, tuple)):
        return '; '.join(str(v) for v in value) if value else 'none'
    return str(value)


def _op_said(op):
    """One lettering operation in words, from the fields lettering.logotype records (its measured geometry stays in
    build.json); an operation already said in words is kept as it is."""
    if isinstance(op, str):
        return op
    kind, at = op.get('op'), op.get('glyph') or op.get('at') or op.get('after') or '?'
    if kind == 'join':
        pair = op.get('pair') or at
        said = {'bridge': 'a bridge joining %s', 'overlap': '%s overlapped',
                'stem': '%s standing on one stem'}.get(op.get('kind'), '%s joined') % pair
    elif kind == 'cut_in' and op.get('shape') == 'knockout':
        said = '%s cut in under %s, a hairline between them' % (at, op.get('by', '?'))
    elif kind == 'cut_in':
        said = {'inline': 'an engraved inline in %s', 'slot': 'a slot cut through %s'}.get(op.get('shape'), 'a cut into %s') % at
    elif kind == 'swash':
        said = 'a swash from the %s terminal of %s' % (str(op.get('terminal', '')).replace('_', '-'), at)
    elif kind == 'alternate':
        said = 'the %s alternate of %s' % (op.get('feature', ''), at)
    else:
        said = '%s at %s' % (kind, at)
    if op.get('applied', True):
        return said
    return said + (' (not applied: %s)' % op['why'] if op.get('why') else ' (not applied)')


def _ops_said(lines):
    """The name's lettering in words: the build records one list of operations per line of the name; a line with none
    is set as its face draws it."""
    ops = [op for line in (lines or []) for op in (line if isinstance(line, (list, tuple)) else [line])]
    return '; '.join(_op_said(op) for op in ops) if ops else 'set as the face draws it (no lettering operation)'


def _rows(answers):
    """A juror's answer object as (question, answer) rows; nothing when there is no answer object."""
    if not isinstance(answers, dict):
        return []
    return [(k.replace('_', ' '), _said([str(x).replace('_', ' ') for x in v] if k in ENUM_ANSWERS and isinstance(v, list) else v))
            for k, v in answers.items()]


def _true_size(crop, dpi):
    """A 1 : 1 crop's width and height in CSS px (the page's width and height attributes; no inline style)."""
    width_px, height_px = crop['size_px']
    return {'width_px': round(width_px * CSS_PX_PER_INCH / dpi), 'height_px': round(height_px * CSS_PX_PER_INCH / dpi)}


def _day9():
    """Day 9's section: being built, changed, unreadable or published — never an exception, so Day 8 always shows."""
    now = day9_pick.state()
    if now['state'] != day9_pick.PUBLISHED:
        return now
    try:
        return _day9_published(now['record'])
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        return {'state': day9_pick.UNREADABLE, 'why': '%s: %s' % (type(error).__name__, error)}


def _day9_published(record):
    url = {role: reverse('dashboard:day9_file', args=[role]) for role in record['downloads']}
    sketches = [dict(s, url=url[s['file']], desirability_said=_rows(s['desirability']),
                     buildability_said=_rows(s['buildability'])) for s in record['sketches']]
    by_sketch = {s['id']: s for s in sketches}
    dpi = record['crop_dpi']
    builds = [dict(b, urls={k: url[r] for k, r in b['files'].items()}, sketch_row=by_sketch.get(b['sketch']),
                   ops_said=_ops_said(b['lettering']['ops']), cannot_meet_said=_said(b['cannot_meet']),
                   issues_said=_said(b['issues']),
                   status_said=b['status'].replace('_', ' '),
                   score_rows=[(n.replace('_', ' '), s) for n, s in b['scores'].items()] if b['judged'] else [],
                   name_css=_true_size(b['name_crop'], dpi), arabic_css=_true_size(b['arabic_crop'], dpi))
              for b in record['builds']]
    by_id = {b['id']: b for b in builds}
    proof = record['proof_effect']
    return {'state': day9_pick.PUBLISHED, 'record': record, 'shown': [by_id[i] for i in record['shown']],
            'builds': builds, 'sketches': sketches, 'none_pass': not record['passing'], 'proof': proof,
            'proof_url': None if proof is None else url[proof['file']],
            'unranked_directions': [d for d in day9_pick.DIRECTIONS if record['rankings'][d] is None],
            'ranking_notes': [(d, r['why'], url[r['file']], r['state'] != day9_pick.RANKED)
                              for d, r in ((d, record['rankings'][d]) for d in day9_pick.DIRECTIONS)
                              if r is not None and r['why'] is not None]}


def _day10():
    """Day 10's section (the master of the owner's pick): being built, changed, unreadable or published — never an
    exception, so Day 9 and Day 8 always show."""
    now = day10_master.state()
    if now['state'] != day10_master.PUBLISHED:
        return now
    try:
        return _day10_published(now['record'])
    except (KeyError, TypeError, ValueError, AttributeError, NoReverseMatch) as error:
        return {'state': day10_master.UNREADABLE, 'why': '%s: %s' % (type(error).__name__, error)}


def _day10_published(record):
    url = {role: reverse('dashboard:day10_file', args=[role]) for role in record['downloads']}
    pieces = []
    for piece in record['pieces']:
        pieces.append(dict(piece, picture_url=url[piece['picture']], layered_url=url[piece['layered']],
                           layered_words=record['downloads'][piece['layered']]['words'],
                           others=[{'url': url[o], 'words': record['downloads'][o]['words']} for o in piece['others']]))
    by_key = {p['key']: p for p in pieces}
    pick_url = reverse('dashboard:day9_file', args=[record['pick']['day9_role']])
    return {'state': day10_master.PUBLISHED, 'record': record, 'facts': record['facts'], 'pick': record['pick'],
            'pick_url': pick_url, 'lid': by_key['lid'], 'pieces': [p for p in pieces if p['key'] != 'lid']}


@login_required
@require_GET
def pick(request):
    return render(request, 'dashboard/day8_pick.html', _context(request, request.GET.get('tab', 'pick')))


@login_required
@require_GET
def artifact(request, role):
    member(request.user)
    try:
        record = day8_pick.checked()
        item = record['downloads'][role]
    except (ValueError, KeyError, OSError):
        raise Http404
    path = (day8_pick.DAY8 / item['path']).resolve()
    if not path.is_relative_to(day8_pick.DAY8.resolve()):
        raise Http404
    return FileResponse(path.open('rb'), content_type=item['mime'], as_attachment=item['mime'] not in INLINE, filename=path.name)


@login_required
@require_GET
def day10_artifact(request, role):
    """A file Day 10's publication pins, served only while its bytes are the ones published (re-hashed each request)."""
    member(request.user)
    try:
        path, item = day10_master.checked_file(role)
    except (ValueError, KeyError, OSError, day10_master.Changed):     # a changed file is not served (never a 500)
        raise Http404
    return FileResponse(path.open('rb'), content_type=item['mime'], as_attachment=item['mime'] not in INLINE, filename=path.name)


@login_required
@require_GET
def day9_artifact(request, role):
    """A file Day 9's publication pins, served only while its bytes are the ones published (re-hashed each request)."""
    member(request.user)
    try:
        path, item = day9_pick.checked_file(role)
    except (ValueError, KeyError, OSError):
        raise Http404
    return FileResponse(path.open('rb'), content_type=item['mime'], as_attachment=item['mime'] not in INLINE, filename=path.name)
