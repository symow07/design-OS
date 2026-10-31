"""Day 7 §8: where the Day 6 critic (a vision model's verdict) and the Day 6 instrument (measured placement, colour, gesture,
grammar; the bottle's placement, colour and swoosh SSIM) disagree — recorded, surface by surface, in critic-calibration.json.
No model is called; the records are read as written on Day 6.
"""
from pathlib import Path
import datetime, json
from . import fidelity_assets as fa

ROOT = fa.ROOT
DAY6 = ROOT / 'docs/audit/day-6'
OUT = ROOT / 'docs/audit/day-7/critic-calibration.json'
CRITIC_BAR = 8.0   # the critic's own pass bar on Day 6: every verdict with score below it carried passed=False


def _load(path):
    return json.loads(Path(path).read_text(encoding='utf-8')) if Path(path).exists() else None


def surface_rows():
    summary = _load(DAY6 / 'stand/surfaces-r2/fidelity-summary.json') or {'rows': []}
    rows = []
    for s in summary['rows']:
        sid = s['surface_id']; critic = _load(DAY6 / 'stand/surfaces-r2' / sid / 'critic.json'); verdict = (critic or {}).get('verdict') or {}
        axes = {k: s.get(k) for k in ('placement', 'ink_colour', 'field', 'gesture', 'grammar') if s.get(k) is not None}
        measured = bool(s.get('measured')); instrument_pass = measured and all(v == 'PASS' for v in axes.values())
        dims = {k: v.get('score') for k, v in (verdict.get('dimensions') or {}).items()}
        notes = []
        if not measured:
            notes.append('instrument: composed, not measured (no measured element on this face by the measurement\'s declaration)')
            if dims.get('typography') is not None and dims['typography'] <= 3:
                notes.append('critic scores typography %s on a face declared to carry no type — it penalises a declared absence' % dims['typography'])
        if measured:
            for axis, state in axes.items():
                if state == 'FAIL':
                    notes.append('instrument FAIL on %s (%s)' % (axis, {'field': 'field ΔE2000 max %.1f, %s of %s samples failing' % (s.get('field_delta_e_max') or 0, s.get('field_failing'), s.get('field_total'))}.get(axis, 'see summary')))
            if instrument_pass and verdict and not verdict.get('passed'):
                notes.append('instrument within every threshold; critic rejects at %.1f' % (verdict.get('score') or 0))
            if not instrument_pass and verdict and verdict.get('passed'):
                notes.append('critic passes a face the instrument fails')
        if verdict and (verdict.get('hard_failures') or []):
            notes.append('critic hard failures: ' + '; '.join(str(h)[:80] for h in verdict['hard_failures'][:3]))
        agree = None if not verdict or not measured else (instrument_pass == bool(verdict.get('passed')))
        rows.append({'surface_id': sid, 'instrument': {'status': s.get('status'), 'measured': measured, 'axes': axes, 'pass': instrument_pass,
                                                       'placement_worst_offset_mm': s.get('placement_worst_offset_mm'), 'ink_delta_e_max': s.get('ink_delta_e_max'),
                                                       'field_delta_e_max': s.get('field_delta_e_max'), 'gesture_max_mm': s.get('gesture_max_mm')},
                     'critic': {'present': bool(verdict), 'score': verdict.get('score'), 'passed': verdict.get('passed'), 'review_status': verdict.get('review_status'), 'dimensions': dims},
                     'agree_on_release': agree, 'notes': notes})
    return rows


def bottle_rows():
    rows = []
    for rev, folder in (('4', DAY6 / 'bottle/revision-4'), ('3-rescore', DAY6 / 'bottle/revision-3-rescore')):
        check = _load(folder / 'fidelity-check.json') or _load(DAY6 / 'bottle/revision-4/fidelity-check.json') or {}
        critic = _load(folder / 'critic.json'); verdict = (critic or {}).get('verdict') or {}
        failing = [p.get('id') for p in check.get('placement') or [] if p.get('passed') is False]
        instrument = {'placement_passed': check.get('placement_passed'), 'placement_failing': failing, 'colour_passed': check.get('colour_passed'),
                      'swoosh_passed': check.get('swoosh_passed'), 'swoosh_ssim': check.get('swoosh_ssim'), 'swoosh_threshold': check.get('swoosh_threshold'),
                      'named_deviation': check.get('named_deviation')}
        dims = {k: v.get('score') for k, v in (verdict.get('dimensions') or {}).items()}; ill = (critic or {}).get('illustration_dimension')
        notes = []
        if rev == '4':
            if check.get('swoosh_passed') and ill and dims.get(ill, 10) < 7:
                notes.append('instrument passes the swoosh (SSIM %.3f ≥ %.2f); the critic\'s illustration dimension (%s) scores %s — the F4 stop rule closed the swoosh on the critic' % (check.get('swoosh_ssim') or 0, check.get('swoosh_threshold') or 0, ill, dims.get(ill)))
            if check.get('placement_passed') is False and dims.get('typography', 0) >= 7:
                notes.append('instrument fails placement (%s) while the critic scores typography %s — a sub-millimetre miss the critic cannot see' % (', '.join(map(str, failing)) or 'see record', dims.get('typography')))
        rows.append({'bottle_revision': rev, 'instrument': instrument, 'critic': {'present': bool(verdict), 'score': verdict.get('score'), 'passed': verdict.get('passed'), 'dimensions': dims, 'illustration_dimension': ill},
                     'agree_on_release': None if not verdict else (bool(check.get('placement_passed') and check.get('colour_passed') and check.get('swoosh_passed')) == bool(verdict.get('passed'))), 'notes': notes})
    return rows


def build():
    surfaces = surface_rows(); bottle = bottle_rows()
    disagreements = [r for r in surfaces + bottle if r.get('agree_on_release') is False or any('penalises' in n or 'cannot see' in n or 'closed the swoosh' in n for n in r['notes'])]
    record = {'schema': 'day7_critic_calibration/1', 'reading': 'The Day 6 critic and the Day 6 instrument measure different things: the instrument reproduces the measurement (placement, colour, gesture, '
              'grammar, the swoosh SSIM); the critic judges the picture as a shelf reads it. Where they disagree the instrument is the fidelity record and the critic a second '
              'opinion on design quality; the critic penalises declared absences (composed faces) and misses sub-millimetre placement, and it closed the swoosh the instrument passed.',
              'critic_bar': CRITIC_BAR, 'surfaces': surfaces, 'bottle': bottle, 'disagreements': len(disagreements),
              'summary': [{'id': r.get('surface_id') or ('bottle r' + r['bottle_revision']), 'instrument_pass': r['instrument'].get('pass', r['instrument'].get('placement_passed')),
                           'critic_score': r['critic'].get('score'), 'critic_passed': r['critic'].get('passed'), 'notes': r['notes']} for r in surfaces + bottle],
              'built_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    OUT.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
    return {'surfaces': len(surfaces), 'bottle': len(bottle), 'disagreements': len(disagreements)}


if __name__ == '__main__':
    print(json.dumps(build()))
