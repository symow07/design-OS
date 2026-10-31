"""Day 8 §6 — the pick page's record (D-D8-6): the concepts that pass the jury, large, with everything the owner
weighs; a history of every sketch and build with its verdict; and, if none passes, the three best on a "below the
bar" sheet with the jury's findings. ``publish()`` writes ``docs/audit/day-8/pick/publication.json``: every file the
page shows is named by a role and pinned by its sha256 — the page serves a file only while its bytes still match."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from apps.pipeline.services import truthful_concept as tc

DAY8 = tc.DAY8
PICK = DAY8 / 'pick'
RECORD = PICK / 'publication.json'
MIME = {'.png': 'image/png', '.json': 'application/json', '.pdf': 'application/pdf', '.ai': 'application/postscript',
        '.svg': 'image/svg+xml', '.md': 'text/markdown'}
FACE_ROLES = (('display', 'Latin display'), ('support', 'Latin support'), ('arabic', 'Arabic'))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _licences() -> dict:
    book = json.loads((DAY8 / 'fonts' / 'type-book.json').read_text())
    out = {}
    for group in ('latin', 'arabic'):
        for fams in book[group].values():
            for f in fams:
                out[f['family']] = f['files'][0].get('licence') or f.get('licence')
    return out


def crop_true_size(concept_dir, box_mm, out_png, *, dpi=600, pad_mm=1.5) -> dict:
    """A 1 : 1 crop of the build's .ai (the page shows it at its width in millimetres)."""
    import fitz
    pdf = fitz.open(str(Path(concept_dir) / 'truthful.ai'))
    page = pdf[0]
    k = 72 / 25.4
    x0, y0, x1, y1 = box_mm
    clip = fitz.Rect((x0 - pad_mm) * k, (y0 - pad_mm) * k, (x1 + pad_mm) * k, (y1 + pad_mm) * k)
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), clip=clip, alpha=False)
    pix.save(str(out_png))
    return {'path': str(out_png), 'width_mm': round(x1 - x0 + 2 * pad_mm, 2)}


def publish(*, passing_rule=None) -> dict:
    """The record the page reads, from the files Stages 1–3 wrote."""
    from apps.pipeline.services import concept_sketches as cs
    downloads, licences = {}, _licences()

    def pin(role, path, words):
        path = Path(path)
        downloads[role] = {'path': str(path.relative_to(DAY8)), 'sha256': _sha(path), 'mime': MIME.get(path.suffix, 'application/octet-stream'),
                           'words': words}
        return role

    sketches = []
    for d in 'ABC':
        ranking = json.loads((cs.SKETCHES / f'ranking-{d}.json').read_text())
        ids = [o['id'] for o in tc.options(d)]
        rows = {r['sketch']: r for r in (ranking.get('payload') or {}).get('ranking', [])}
        best = [ids[i - 1] for i in (ranking.get('payload') or {}).get('best_two', []) if 1 <= i <= 6]
        for k, sid in enumerate(ids, 1):
            rec = json.loads((cs.SKETCHES / sid / 'result.json').read_text())
            r = rows.get(k, {})
            sketches.append({'id': sid, 'direction': d, 'choices': rec['option']['choices'], 'rank': r.get('rank'), 'score': r.get('score'),
                             'why': r.get('why'), 'ai_artefacts': r.get('ai_artefacts'), 'copy': rec['copy']['found'],
                             'went_on': sid in best, 'file': pin(f'sketch-{sid}', cs.SKETCHES / sid / 'lid.png', f'sketch {sid} (an idea, never printed)')})
        pin(f'contact-{d}', cs.SKETCHES / f'contact-{d}.png', f'the six sketches of direction {d}')
    concepts = []
    for folder in sorted(p for p in tc.CONCEPTS.iterdir() if (p / 'build.json').exists() and (p / 'jury' / 'verdict.json').exists()):
        build = json.loads((folder / 'build.json').read_text())
        verdict = json.loads((folder / 'jury' / 'verdict.json').read_text())
        d = build['direction']
        s = tc.spec(d)
        lay = tc.layout(d, build['option'], anchors=json.loads((folder / 'designer-eye.json').read_text())['read']['anchors'],
                        overrides=build.get('overrides') or None)
        cid = folder.name
        name_box = [min(lay['boxes'][k][0] for k in lay['boxes'] if k.startswith('name')), min(lay['boxes'][k][1] for k in lay['boxes'] if k.startswith('name')),
                    max(lay['boxes'][k][2] for k in lay['boxes'] if k.startswith('name')), max(lay['boxes'][k][3] for k in lay['boxes'] if k.startswith('name'))]
        name_crop = crop_true_size(folder, name_box, folder / 'name-1to1.png')
        ar_crop = crop_true_size(folder, lay['boxes']['descriptor_ar'], folder / 'arabic-1to1.png')
        raw = verdict.get('raw') or {}
        scores = {n: {'J1': raw.get('scores', {}).get('J1', {}).get(n), 'J2': raw.get('scores', {}).get('J2', {}).get(n),
                      'stands': (verdict.get('capped') or {}).get(n)} for n in (verdict.get('capped') or {})}
        status = (verdict.get('verdict') or {}).get('status')
        concepts.append({
            'id': cid, 'direction': d, 'name': s['name'], 'role': s['role'], 'idea': s['idea'], 'story': s['story'],
            'option': build['option'], 'sketch': build['sketch'], 'status': status,
            'passes': status == 'pass' if passing_rule is None else passing_rule(verdict),
            'raw_means': raw.get('means'), 'stricter_mean': raw.get('stricter_mean'),
            'capped_mean': round(sum((verdict.get('capped') or {}).values()) / max(1, len(verdict.get('capped') or {})), 2) if verdict.get('capped') else None,
            'scores': scores, 'caps': verdict.get('caps_applied'), 'hard_failures': (verdict.get('verdict') or {}).get('hard_failures'),
            'top_issues': verdict.get('top_issues'), 'reads': {j: [(raw.get(j) or {}).get('reads_first'), (raw.get(j) or {}).get('reads_second'), (raw.get(j) or {}).get('reads_third')] for j in ('J1', 'J2')},
            'idea_read': {j: (raw.get(j) or {}).get('idea_read') for j in ('J1', 'J2')}, 'cost_usd': verdict.get('cost_usd'),
            'checks': json.loads((folder / 'checks.json').read_text()), 'designer_eye': json.loads((folder / 'designer-eye.json').read_text())['differences'],
            'fonts': [{'role': label, 'family': s['type'][k]['family'], 'stem': s['type'][k]['stem'], 'licence': licences.get(s['type'][k]['family'])}
                      for k, label in FACE_ROLES],
            'takes': s['takes'], 'extends': s['extends'], 'finishes': s['finishes'], 'proposals_flagged': s['proposals_flagged'],
            'repairs': build.get('overrides') or {}, 'name_crop_width_mm': name_crop['width_mm'], 'arabic_crop_width_mm': ar_crop['width_mm'],
            'files': {k: pin(f'{cid}-{k}', folder / f, w) for k, f, w in (
                ('truthful', 'truthful.png', f'{cid}: the truthful lid, 190 × 120 mm (≈ 205 PPI; Day 9 brings the plate to ≥ 300)'),
                ('name', 'name-1to1.png', f'{cid}: the name at 1 : 1'), ('arabic', 'arabic-1to1.png', f'{cid}: the Arabic at 1 : 1'),
                ('finishes', 'finish-sheet.png', f'{cid}: the finish sheet (foil and deboss masks)'),
                ('media', 'media-map.json', f'{cid}: the media map'), ('ai', 'truthful.ai', f'{cid}: the layered .ai (finish plates as pages)'),
                ('pdf', 'truthful.pdf', f'{cid}: the same file as PDF'), ('svg', 'truthful.svg', f'{cid}: the layered SVG'),
                ('checks', 'checks.json', f'{cid}: the measured checks'), ('verdict', 'jury/verdict.json', f'{cid}: the jury\'s verdict'))
                if (folder / f).exists()},
        })
    passing = [c['id'] for c in concepts if c['passes']]
    # ranked by the stricter juror's mean, a tie broken by both jurors' mean
    ranked = sorted(concepts, key=lambda c: (-(c['stricter_mean'] or 0), -sum((c['raw_means'] or {}).values()) / 2))
    # the "below the bar" sheet: the best build of each direction (three versions of one direction are not a choice);
    # the three highest scores overall are kept beside it in the record
    best_of = {}
    for c in ranked:
        best_of.setdefault(c['direction'], c)
    sheet = [c['id'] for c in sorted(best_of.values(), key=lambda c: -(c['stricter_mean'] or 0))]
    anchors = json.loads((DAY8 / 'jury' / 'anchors.json').read_text())['anchors']
    record = {'schema': 'day8_pick/1.0', 'made_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
              'gate': 'rubric v2 · mean ≥ 8, every critical ≥ 7, no hard failure (concept_quality.evaluate) · the stricter juror per dimension · caps after raw scores',
              'calibration': json.loads((DAY8 / 'jury' / 'critic-calibration-v2.json').read_text()).get('decision')
              if (DAY8 / 'jury' / 'critic-calibration-v2.json').exists() else None,
              'passing': passing, 'below_the_bar': [] if passing else sheet,
              'below_the_bar_rule': 'the best build of each direction by the stricter juror\'s mean (raw), a tie broken by both jurors\' mean',
              'top_three_overall': [c['id'] for c in ranked[:3]],
              'concepts': concepts, 'sketches': sketches,
              'anchors': [{'brand': a['brand'], 'product': a['product'], 'page': a['page'], 'role': a['role']} for a in anchors],
              'downloads': downloads}
    PICK.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
    return record


def checked() -> dict:
    """The record, with every pinned file re-hashed; raises ValueError when one has changed."""
    record = json.loads(RECORD.read_text())
    for role, item in record['downloads'].items():
        if _sha(DAY8 / item['path']) != item['sha256']:
            raise ValueError('%s changed since it was published' % role)
    return record
